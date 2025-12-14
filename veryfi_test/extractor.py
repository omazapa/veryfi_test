"""Structured data extraction helpers for Switch invoices."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Optional
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

    def to_dict(self) -> Dict[str, str]:
        """Return a JSON-friendly representation of the fields."""

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

    bill_lines = [
        line.strip()
        for line in bill_match.group("bill_block").splitlines()
        if line.strip()
    ]
    if not bill_lines:
        return None

    vendor_address = f"PO Box {vendor_match.group('po')} {vendor_match.group('city_state').strip()}"
    bill_to_name = bill_lines[0]
    bill_to_address = ", ".join(bill_lines[1:]) if len(bill_lines) > 1 else ""

    return InvoiceFields(
        vendor_name="Switch",
        vendor_address=vendor_address,
        bill_to_name=bill_to_name,
        bill_to_address=bill_to_address,
        invoice_number=invoice_match.group("invoice_no"),
        invoice_date=invoice_match.group("invoice_date"),
    )


__all__ = ["InvoiceFields", "extract_switch_invoice"]
