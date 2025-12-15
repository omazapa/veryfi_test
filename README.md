# veryfi_test

<p align="center">
  <a href="https://github.com/omazapa/veryfi_test/actions/workflows/quality.yml">
    <img src="https://github.com/omazapa/veryfi_test/actions/workflows/quality.yml/badge.svg" alt="Code Quality badge" />
  </a>
  <a href="https://github.com/omazapa/veryfi_test/actions/workflows/integration.yml">
    <img src="https://github.com/omazapa/veryfi_test/actions/workflows/integration.yml/badge.svg" alt="Integration Tests badge" />
  </a>
  <a href="https://github.com/omazapa/veryfi_test/actions/workflows/python-publish.yml">
    <img src="https://github.com/omazapa/veryfi_test/actions/workflows/python-publish.yml/badge.svg" alt="Publish badge" />
  </a>
</p>

<p align="center">
  <img src="https://avatars.githubusercontent.com/u/64030334?s=200&v=4" alt="Veryfi Logo" />
</p>

<p align="center">
  <strong>Veryfi’s Data Annotations Engineer Test</strong>
</p>

## Contents

- [Overview](#overview)
- [Processing Pipeline](#processing-pipeline)
- [Quick Start](#quick-start)
- [Credentials Setup](#credentials-setup)
- [CLI Usage](#cli-usage)
- [Structured Field Extraction](#structured-field-extraction)
- [Extraction Assumptions](#extraction-assumptions)

## Overview

- **What it does** – Provides two CLIs (`veryfi-ocr` and `veryfi-extract`) that turn Switch-branded invoices into structured JSON. The first uploads PDFs to Veryfi and stores the raw OCR payload; the second parses that payload into canonical invoice fields.
- **Why it exists** – Automates the Switch use case end to end so annotation engineers can validate layouts, run regression suites, and feed downstream systems without writing bespoke scripts.
- **Scope** – Focused on Switch invoices only. Non-Switch layouts are explicitly skipped (`layout mismatch`). The pipeline expects OCR manifests (JSON) and produces structured fields plus itemized line items.
- **Further reading** – See [`README_approach.md`](README_approach.md) for architecture/trade-offs and [`README_extractor.md`](README_extractor.md) for a deep dive into the parsing logic.

## Processing Pipeline

```
documents.json
   ↓
veryfi-ocr
   ↓
Raw Veryfi OCR JSON (outputs-ocr/)
   ↓
veryfi-extract
   ↓
Structured invoice fields (outputs-extracted/)
```

## Quick Start

```bash
git clone https://github.com/omazapa/veryfi_test
cd veryfi_test
pip install -e .
cp .env.example .env
# edit .env with your Veryfi credentials
# drop your Switch PDFs under ./data/ or adjust the manifest paths accordingly
veryfi-ocr examples/documents.json
veryfi-extract outputs-ocr/
```

## Credentials Setup

Store your Veryfi keys in environment variables so they never end up in Git:

```bash
cp .env.example .env
```

Edit `.env` and fill in the values:

- `VERYFI_API_URL` (defaults to `https://api.veryfi.com/` if omitted)
- `VERYFI_CLIENT_ID`
- `VERYFI_CLIENT_SECRET`
- `VERYFI_USERNAME`
- `VERYFI_API_KEY`

The application can then load them via `veryfi_test.config.load_credentials`, which prefers the actual environment over the `.env` file. Keep `.env` local—`.gitignore` already excludes it.

## CLI Usage

Install the project (editable mode recommended during development):

```bash
pip install -e .
```

After your credentials are set, describe the documents in a JSON manifest:

```json
[
  {"path": "invoices/jan.pdf", "categories": ["Food", "Hotel"]},
  {"path": "receipts/mar.jpg", "categories": ["Receipts"]}
]
```

Then run the CLI against that manifest:

```bash
veryfi-ocr documents.json
```

Example output when using `examples/documents.json`:

```text
(home) ozapatam@tuxito:~/Projects/Veryfi/veryfi_test$ veryfi-ocr examples/documents.json
Processed data/synth-switch_v5-14.pdf (document id: 385142953) -> outputs-ocr/synth-switch_v5-14.json
Processed data/synth-switch_v5-4.pdf (document id: 385142969) -> outputs-ocr/synth-switch_v5-4.json
Processed data/synth-switch_v5-68.pdf (document id: 385142983) -> outputs-ocr/synth-switch_v5-68.json
Processed data/synth-switch_v5-7.pdf (document id: 385142997) -> outputs-ocr/synth-switch_v5-7.json
Processed data/synth-switch_v5-79.pdf (document id: 385143009) -> outputs-ocr/synth-switch_v5-79.json
```

Options:

- `--output-ocr-dir processed/` stores JSON responses under a custom directory (default: `./outputs-ocr`).
- `--env-file /custom/path/.env` points to another dotenv file if needed.

Each manifest entry must include a `path` and can optionally define `categories`/`topics` (string or list). You may also wrap the list in an object with a `documents` key. Every processed document generates a JSON file whose name matches the original input (e.g., `invoice.pdf` → `invoice.json`) and stores the Veryfi response payload. You can also invoke the CLI without installing by running `python -m veryfi_test.ocr_cli documents.json`.

## Structured Field Extraction

Every Veryfi response contains the OCR text under `veryfi_response.ocr_text`. The helper in `veryfi_test/extractor.py` uses the following cues to make sense of Switch-branded invoices:

1. It first locates the vendor banner (`switch …` + `PO Box 674592 …`). Files that do not match this header are rejected immediately so other layouts are ignored.
2. The invoice metadata row is parsed with a regex that captures the **Invoice Date** and **Invoice No.** fields. The first date becomes `invoice_date` and the number becomes `invoice_number`.
3. The `bill to` block is the text between the invoice metadata row and `Account No.`. The first line turns into `bill_to_name` and the rest are collapsed (comma‑separated) into `bill_to_address`.
4. The vendor address is reconstructed from the city/state line and the `PO Box` line that were previously matched.

Run the extraction CLI against a directory full of Veryfi JSON files:

```bash
veryfi-extract outputs-ocr/
```

This command scans every `*.json` file under `outputs-ocr`, extracts the supported
fields, and writes one output file per invoice inside `outputs-extracted/`
(`extracted_<original-name>.json`). Each saved file contains the `InvoiceFields`
payload plus the `source` path, ready for downstream tooling. The payload now
includes a `line_items` array where each row captures (assuming SKUs are
represented by the last alphanumeric token of exactly eight characters that
appears inside parentheses):

- `sku`: identifier derived from that eight-character token (uppercased); `null` if absent
- `description`: full text, including any wrapped lines
- `quantity`: Quantity column straight from the invoice
- `price`: Rate column
- `total`: Amount column
- `tax_rate`: null (not derivable from the invoice)

Any JSON that does not match the Switch layout (for example `examples/non_switch.json`) is listed under `skipped` with the reason it was ignored. Running `veryfi-extract outputs-ocr/` against a mix of approved and unapproved layouts prints a summary like:

```json
{
  "processed": 7,
  "saved": [
    "outputs-ocr/synth-switch_v5-14.json",
    "outputs-ocr/synth-switch_v5-4.json",
    "outputs-ocr/synth-switch_v5-68.json",
    "outputs-ocr/synth-switch_v5-7.json",
    "outputs-ocr/synth-switch_v5-79.json"
  ],
  "skipped": {
    "outputs-ocr/non-switch-invoice.json": "layout mismatch",
    "outputs-ocr/non-switch-invoice2.json": "layout mismatch"
  },
  "output_dir": "outputs-extracted"
}
```

The extractor labels each non-Switch document with `layout mismatch`, so it never produces structured data for layouts we have not vetted.

### Extraction Assumptions

1. **SKU Identification** – When parsing line items we assume that the SKU is encoded as the last alphanumeric token with exactly eight characters enclosed in parentheses. The extractor uppercases that token and assigns it to `sku`. Items that lack such a token keep `sku: null`.
2. **Quantity** – The quantity we store is exactly the value shown under the `Quantity` column (e.g., units, hours, bandwidth). We do not attempt to normalize units or convert them.
3. **Price** – `price` comes directly from the `Rate` column, representing the unit price for the line item.
4. **Total** – `total` is copied from the `Amount` column (the total per line, already calculated by the invoice and inclusive of any adjustments or discounts).
5. **Tax Rate** – The invoices do not expose a dedicated tax-rate column and the OCR text does not provide enough information to derive one. Consequently, `tax_rate` is assumed to be unavailable and is always set to `null`.
