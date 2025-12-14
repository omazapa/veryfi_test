# Switch Invoice Extractor

This repository contains a tiny parser (`veryfi_test/extractor.py`) that
turns the raw OCR text produced by Veryfi into structured JSON describing key
fields in Switch invoices. The goal is to automate the tedious copy/paste work
while still guaranteeing that only the intended layout is parsed.

## Workflow Overview

1. Run the Veryfi CLI (`veryfi-ocr` or `python -m veryfi_test.ocr_cli`) to produce
   JSON files in `outputs-ocr/*.json`. Each file holds the API response under
   `veryfi_response`; the full OCR text is inside `veryfi_response.ocr_text`.
2. Feed those files to the extractor CLI (available as the `verify_extract`
   console script and mirrored by `scripts/extract_switch_invoices.py`):

   ```bash
   verify_extract outputs-ocr
   ```

3. The CLI scans every `*.json` file inside the provided directory, writes one
   extracted document per match under `outputs-extracted/` (file names prefixed
   with `extracted_`), and prints a summary JSON that enumerates the saved files
   plus any skipped inputs.

`examples/non_switch.json` demonstrates the skip path—its OCR snippet lacks the
Switch banner and is deliberately ignored. This satisfies the “exclude other
documents” constraint while still reporting which sources were rejected.

## Regular Expressions Explained

The extractor relies on three regexes declared in `veryfi_test/extractor.py`.
They operate on a normalized (CR-stripped) version of the OCR text.

### `_VENDOR_PATTERN`

```python
re.compile(r"(?im)^switch\s+(?P<city_state>[^\n]+)\nPO Box\s+(?P<po>\d+)")
```

- `(?im)` enables case-insensitive and multiline matching.
- `^switch` anchors to the start of a line that spells “switch” (the vendor
  logo).
- `(?P<city_state>[^\n]+)` grabs the city/state line that follows.
- The `PO Box …` line captures the numeric PO box value (`po` group).

If this pattern is not found the file is rejected immediately—this ensures the
logic only runs on Switch-branded invoices.

### `_INVOICE_PATTERN`

```python
re.compile(
    r"Invoice Date\s+Due Date\s+Invoice No\.\s*\n"
    r"\s*(?P<invoice_date>\d{2}/\d{2}/\d{2})"
    r"\s+\d{2}/\d{2}/\d{2}\s+(?P<invoice_no>\d+)",
    flags=re.IGNORECASE,
)
```

- Matches the metadata row that displays the invoice date, due date, and
  invoice number.
- Uses `(?P<invoice_date>…)` to capture the first MM/DD/YY date and
  `(?P<invoice_no>…)` to capture the trailing digits.
- The second date (due date) is skipped because the exercise only requires the
  invoice date and number.

### `_BILL_TO_PATTERN`

```python
re.compile(
    r"Invoice No\.[\s\S]*?\n"
    r"\s*\d{2}/\d{2}/\d{2}\s+\d{2}/\d{2}/\d{2}\s+\d+\s*\n+"
    r"(?P<bill_block>.+?)\n+Account No\.",
    flags=re.IGNORECASE | re.DOTALL,
)
```

- Starts near the metadata row and lazily consumes text until it passes the
  date/date/number line (`\d{2}/…` pattern).
- `(?P<bill_block>.+?)` captures everything between that line and the next
  `Account No.` header, effectively isolating the “bill to” block.
- The block is subsequently split by lines: the first becomes `bill_to_name`
  and the rest (if any) are joined with commas to form `bill_to_address`.

These three patterns together uniquely capture the vendor information,
invoice metadata, and customer block. If any of them fail to match, the parser
returns `None`, signaling that the file should be skipped.

## Output Format

Each successful extraction produces an `InvoiceFields` dataclass that is saved
as `outputs-extracted/extracted_<original>.json` with the following structure:

```json
{
  "vendor_name": "Switch",
  "vendor_address": "PO Box 674592 Dallas, TX 75267-4592",
  "bill_to_name": "Dataiku, Inc.",
  "bill_to_address": "8442 Distinctive Dr, San Diego, CA 92108",
  "invoice_number": "699581195",
  "invoice_date": "11/18/23"
}
```

Line items appear under `line_items`:

```json
{
"sku": "YSPG4VFH",
  "description": "Installation of Cross Connect | 395 Gbps Fiber to AE9qC3",
  "quantity": "579.10",
  "price": "1750.30",
  "total": "1013598.73",
"tax_rate": "1750.30"
}
```

The parser walks every row between the `Description … Quantity … Amount` header and the `Total USD` footer, keeping wrapped descriptions intact and normalizing the numeric columns (commas removed). The SKU is computed as the last alphanumeric token with **exactly eight** characters enclosed in parentheses (converted to uppercase); if no such token exists for a line item, `sku` is set to `null`. The `tax_rate` field mirrors the Rate column, matching the specification for the test.
