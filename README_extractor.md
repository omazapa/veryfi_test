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

3. The CLI scans every `*.json` file inside the provided directory, writes one extracted document per match under `outputs-extracted/` (file names prefixed with `extracted_`), and prints a summary JSON that enumerates the saved files plus any skipped inputs. Each saved file includes the structured metadata and the parsed line items described below.

`examples/non_switch.json` demonstrates the skip path—its OCR snippet lacks the
Switch banner and is deliberately ignored. This satisfies the “exclude other
documents” constraint while still reporting which sources were rejected.

## How the Extractor Works (Detailed)

The extractor is intentionally deterministic so that every decision can be traced back to a specific heuristic. When you run `verify_extract outputs-ocr` the following steps occur for **each** JSON file in that directory:

1. **Load Veryfi response** – We open the JSON, grab the `veryfi_response` object, and read `ocr_text`. If the top-level JSON is not an object, the file is skipped with the reason `unsupported JSON structure`. Missing or malformed files are reported as `missing file` or `invalid JSON`.
2. **Vendor identification** – `ocr_text` is first normalized (CRs removed) and sent through `_VENDOR_PATTERN`. If the text does not begin with the Switch banner (`switch … / PO Box …`), the file is skipped (`layout mismatch`). This ensures we never parse other vendors by mistake.
3. **Invoice metadata** – `_INVOICE_PATTERN` is applied to capture `invoice_date` and `invoice_number`. The pattern matches the “Invoice Date / Due Date / Invoice No.” header followed by one row of values. Without this header the extractor refuses to continue because the document structure is not the expected Switch format.
4. **Bill-to block** – `_BILL_TO_PATTERN` slices everything between the metadata row and the next `Account No.` heading. The first non-empty line becomes `bill_to_name` and the remainder is concatenated with commas to form `bill_to_address`. This logic keeps multi-line addresses intact.
5. **Line-item parsing** – Once the boilerplate sections are validated, the parser streams through every line between the header row (`Description … Quantity … Rate … Amount`) and the `Total USD` footer. Each table row is decoded using `_LINE_PATTERN`, which expects tab- or space-separated columns. Wrapped descriptions are handled by buffering the text until the next numeric row is seen.
6. **Structured payload construction** – For each decoded row we create an `InvoiceLineItem` object:
   - `sku` is derived by scanning the description for alphanumeric tokens of exactly eight characters inside parentheses (e.g., `(YSPG4VFH)`). The last such token is uppercased and used as a SKU. If no match exists (for discount lines, for example), `sku` is `null`.
   - `description` holds the full text (including wrapped portions).
   - `quantity`, `price`, and `total` come straight from the table, with commas removed to simplify downstream parsing.
   - `tax_rate` is always `null` because Switch invoices do not expose a separate tax column and it cannot be derived reliably from the OCR text.

Because the extractor always runs through these checks in order, any failure (missing banner, missing metadata, empty bill-to block, etc.) results in that file being listed under `skipped` with a precise reason. Valid Switch invoices end up under `outputs-extracted/extracted_<name>.json` and contain the vendor metadata, bill-to info, and the enriched `line_items` array.

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
"tax_rate": null
}
```

The parser walks every row between the `Description … Quantity … Amount` header and the `Total USD` footer, keeping wrapped descriptions intact and normalizing the numeric columns (commas removed). The SKU is computed as the last alphanumeric token with **exactly eight** characters enclosed in parentheses (converted to uppercase); if no such token exists for a line item, `sku` is set to `null`. Because the invoices provide no tax-rate column, the extractor leaves `tax_rate` set to `null`.
