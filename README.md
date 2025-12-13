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

Each manifest entry must include a `path` and can optionally define `categories`/`topics` (string or list). You may also wrap the list in an object with a `documents` key. Every processed document generates a JSON file whose name matches the original input (e.g., `invoice.pdf` → `invoice.json`) and stores the Veryfi response payload. You can also invoke the CLI without installing by running `python -m veryfi_test.cli documents.json`.
