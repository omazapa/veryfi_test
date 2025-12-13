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
veryfi-process documents.json
```

Options:

- `--output-dir processed/` stores JSON responses under a custom directory (default: `./outputs`).
- `--env-file /custom/path/.env` points to another dotenv file if needed.

Each manifest entry must include a `path` and can optionally define `categories`/`topics` (string or list). You may also wrap the list in an object with a `documents` key. Every processed document generates a JSON file whose name matches the original input (e.g., `invoice.pdf` → `invoice.json`) and stores the Veryfi response payload. You can also invoke the CLI without installing by running `python -m veryfi_test.cli documents.json`.
