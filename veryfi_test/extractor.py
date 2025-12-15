"""Structured data extraction helpers for Switch invoices."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional
import re


@dataclass
class InvoiceFields:
    """Structured subset of the Switch invoice payload.

    Attributes
    ----------
    vendor_name : str
        Official vendor name ("Switch").
    vendor_address : str
        Mailing address found next to the logo.
    bill_to_name : str
        Customer name in the "bill to" block.
    bill_to_address : str
        Customer address (all address lines collapsed into one string).
    invoice_number : str
        Value displayed in the "Invoice No." column.
    invoice_date : str
        Invoice date as rendered on the document (MM/DD/YY).
    """

    vendor_name: str
    vendor_address: str
    bill_to_name: str
    bill_to_address: str
    invoice_number: str
    invoice_date: str
    line_items: List["InvoiceLineItem"]

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-friendly representation of the fields."""

        return asdict(self)


@dataclass
class InvoiceLineItem:
    """Parsed table row inside the invoice body.

    Attributes
    ----------
    sku : str or None
        Short identifier derived from the description (e.g., "Transport").
    description : str
        Full description displayed inside the row.
    quantity : str
        Quantity column (kept as text to preserve formatting).
    price : str
        Unit price/rate column.
    total : str
        Amount column.
    tax_rate : str or None
        Placeholder for tax rate. Switch invoices do not list this value
        explicitly, so it remains ``None``.
    """

    sku: Optional[str]
    description: str
    quantity: str
    price: str
    total: str
    tax_rate: Optional[str] = None

    def to_dict(self) -> Dict[str, Optional[str]]:
        """Return a JSON-serializable representation of the line item."""

        return asdict(self)


_VENDOR_PATTERN = re.compile(
    r"(?im)^switch\s+(?P<city_state>[^\n]+)\nPO Box\s+(?P<po>\d+)",
)

_INVOICE_PATTERN = re.compile(
    r"Invoice Date\s+Due Date\s+Invoice No\.\s*\n"
    r"\s*(?P<invoice_date>\d{2}/\d{2}/\d{2})"
    r"\s+\d{2}/\d{2}/\d{2}\s+(?P<invoice_no>\d+)",
    flags=re.IGNORECASE,
)

_BILL_TO_PATTERN = re.compile(
    r"Invoice No\.[\s\S]*?\n"
    r"\s*\d{2}/\d{2}/\d{2}\s+\d{2}/\d{2}/\d{2}\s+\d+\s*\n+"
    r"(?P<bill_block>.+?)\n+Account No\.",
    flags=re.IGNORECASE | re.DOTALL,
)

_LINE_PATTERN = re.compile(
    r"^(?P<desc>.+?)"
    r"(?:\t+|\s{2,})"
    r"(?P<qty>-?[\d,]+(?:\.\d+)?)"
    r"(?:\t+|\s{2,})"
    r"(?P<price>-?[\d,]+(?:\.\d+)?)"
    r"(?:\t+|\s{2,})"
    r"(?P<total>-?[\d,]+(?:\.\d+)?)$"
)


def extract_switch_invoice(ocr_text: str) -> Optional[InvoiceFields]:
    """Extract the Switch invoice fields from raw OCR text.

    Parameters
    ----------
    ocr_text : str
        Plain-text representation of the PDF (``veryfi_response.ocr_text``).

    Returns
    -------
    InvoiceFields or None
        Populated fields if the layout matches Switch invoices, otherwise ``None``.
    """

    if not ocr_text:
        return None

    text = ocr_text.replace("\r", "")

    vendor_match = _VENDOR_PATTERN.search(text)
    if not vendor_match:
        return None

    invoice_match = _INVOICE_PATTERN.search(text)
    bill_match = _BILL_TO_PATTERN.search(text)
    if not invoice_match or not bill_match:
        return None

    bill_lines = [line.strip() for line in bill_match.group("bill_block").splitlines() if line.strip()]
    if not bill_lines:
        return None

    vendor_address = f"PO Box {vendor_match.group('po')} {vendor_match.group('city_state').strip()}"
    bill_to_name = bill_lines[0]
    bill_to_address = ", ".join(bill_lines[1:]) if len(bill_lines) > 1 else ""
    line_items = _parse_line_items(text)

    return InvoiceFields(
        vendor_name="Switch",
        vendor_address=vendor_address,
        bill_to_name=bill_to_name,
        bill_to_address=bill_to_address,
        invoice_number=invoice_match.group("invoice_no"),
        invoice_date=invoice_match.group("invoice_date"),
        line_items=line_items,
    )


def _parse_line_items(text: str) -> List[InvoiceLineItem]:
    """Parse the line-item table from the OCR text stream.

    Parameters
    ----------
    text : str
        Full OCR output that contains the invoice table with headers.

    Returns
    -------
    list of InvoiceLineItem
        Structured representation for each parsed row.
    """

    items: List[InvoiceLineItem] = []
    capture = False
    buffer: List[str] = []
    last_item: Optional[InvoiceLineItem] = None
    allow_continuation = False

    for raw_line in text.splitlines():
        line = raw_line.replace("\f", "").strip()
        if not line:
            continue

        if "Description" in line and "Quantity" in line and "Amount" in line:
            capture = True
            buffer.clear()
            continue

        if capture and line.startswith("Total USD"):
            capture = False
            buffer.clear()
            continue

        if not capture:
            continue

        match = _LINE_PATTERN.match(raw_line.rstrip())
        if match:
            description_parts = [part.strip() for part in buffer if part.strip()]
            description_parts.append(match.group("desc").strip())
            description = " ".join(description_parts)
            buffer.clear()
            sku = _derive_sku(description)
            last_item = InvoiceLineItem(
                sku=sku,
                description=description,
                quantity=_standardize_number(match.group("qty")),
                price=_standardize_number(match.group("price")),
                total=_standardize_number(match.group("total")),
                tax_rate=None,
            )
            items.append(last_item)
            allow_continuation = True
        else:
            if allow_continuation and last_item:
                last_item.description = f"{last_item.description} {line}"
                refreshed = _derive_sku(last_item.description)
                if refreshed:
                    last_item.sku = refreshed
            else:
                buffer.append(line)
                allow_continuation = False

    return items


def _derive_sku(description: str) -> Optional[str]:
    """Infer the SKU identifier from a line-item description.

    Parameters
    ----------
    description : str
        Full description extracted from the table row.

    Returns
    -------
    str or None
        Eight-character token (or prefix before a ``|``) when present, otherwise ``None``.
    """

    if not description:
        return None

    matches = re.findall(r"\(([A-Za-z0-9]{8})\)", description)
    if matches:
        return matches[-1].strip().upper()

    return None


def _standardize_number(value: str) -> str:
    """Normalize numeric strings by trimming whitespace and commas."""

    return value.replace(",", "").strip()


__all__ = ["InvoiceFields", "InvoiceLineItem", "extract_switch_invoice"]
