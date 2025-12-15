# Tests

This project bundles an end-to-end regression suite that exercises the full
Veryfi pipeline against real fixture PDFs located in the
`tests/veryfi_private_data` submodule.

## Prerequisites

1. Clone the repository and initialize the submodule:

   ```bash
   git clone git@github.com:omazapa/veryfi_test.git
   cd veryfi_test
   git submodule update --init --recursive
   ```

2. Create/activate a Python 3.11 environment and install the project:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .[dev]
   ```

3. Export the Veryfi credentials (matching the keys used in `.env`):

   ```bash
   export VERYFI_API_URL="https://api.veryfi.com/"
   export VERYFI_CLIENT_ID="..."
   export VERYFI_CLIENT_SECRET="..."
   export VERYFI_USERNAME="..."
   export VERYFI_API_KEY="..."
   ```

## Running the pipeline tests

The integration suite lives in `tests/test_pipeline.py` and can be run directly
with pytest:

```bash
pytest -vv -s tests/test_pipeline.py
```

The test spins up the manifest, uploads every PDF to Veryfi, validates the OCR
JSON, runs the extractor, validates the extracted JSON, and finally emits a
pipeline report so you can inspect the summary in the logs.

> **GitHub Actions** – Because the fixtures live in a private submodule, CI needs
> a personal access token with read access to `omazapa/veryfi_private_data`. Add
> it to the repository secrets as `VERYFI_PRIVATE_DATA_PAT` so the
> `integration.yml` workflow can clone the submodule automatically.

## Installing pre-commit hooks

This repository uses `pre-commit` to keep formatting and typing consistent.
Install and enable the hooks with:

```bash
pip install pre-commit
pre-commit install
```

After that, the hooks (autoflake, Black, mypy) will run automatically whenever
you commit changes. You can also trigger them manually via
`pre-commit run --all-files`.
