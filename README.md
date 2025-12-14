# veryfi_test

<p align="center">
  <img src="https://avatars.githubusercontent.com/u/64030334?s=200&v=4" alt="Veryfi Logo" />
</p>

<p align="center">
  <strong>Veryfi’s Data Annotations Engineer Test</strong>
</p>

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
verify_extract outputs-ocr
```

This command scans every `*.json` file under `outputs-ocr`, extracts the supported
fields, and writes one output file per invoice inside `outputs-extracted/`
(`extracted_<original-name>.json`). A summary resembling the following is printed:

```json
{
  "processed": 6,
  "saved": [
    "outputs-ocr/synth-switch_v5-14.json",
    "outputs-ocr/synth-switch_v5-4.json",
    "outputs-ocr/synth-switch_v5-68.json",
    "outputs-ocr/synth-switch_v5-79.json",
    "outputs-ocr/synth-switch_v5-7.json"
  ],
  "skipped": {
    "outputs-ocr/random.json": "layout mismatch"
  },
  "output_dir": "outputs-extracted"
}
```

Each saved file contains the `InvoiceFields` payload plus the `source` path, ready
for downstream tooling. Any JSON that does not match the Switch layout (for example
`examples/non_switch.json`) is listed under `skipped` with the reason it was ignored.
