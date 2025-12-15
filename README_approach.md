# Project Approach and Practices

## Architecture & Code Paradigm

- **Layered pipeline** – The project separates concerns into configuration, OCR ingestion, and Switch-specific extraction. `veryfi_test/ocr_cli.py` talks to the Veryfi API, while `veryfi_test/extractor.py` stays pure and testable. `veryfi_test/extract_cli.py` orchestrates filesystem I/O and delegates business rules to the extractor.
- **Functional/OO hybrid** – Data structures (`InvoiceFields`, `InvoiceLineItem`) are dataclasses for clarity, while most behavior is implemented with pure helper functions. This keeps parsing logic stateless and easy to test.
- **Static typing** – The codebase targets Python 3.11 with type hints across modules (`TypedDict` summaries, dataset specs). CI runs `mypy` to catch regressions early.
- **CLIs over frameworks** – Instead of a web API, we expose narrow console entry points (`veryfi-ocr`, `veryfi-extract`). This keeps the paradigm simple and focused on batch processing.
- **SOLID-inspired** – While not a full Clean Architecture, the modules respect Single Responsibility (each CLI focuses on one concern), Open/Closed (extractor heuristics can grow without touching the rest), and Dependency Inversion (CLIs depend on pure helpers/dataclasses rather than hard-wired implementations).

## Approach Highlights

1. **Manifest-driven OCR** – Users describe documents in JSON (with flexible aliases for `path` and `categories`). The OCR CLI loads credentials securely, calls Veryfi document-by-document, and preserves the raw payload per PDF inside `outputs-ocr/`.
2. **Strict layout validation** – The extractor combines regexes to ensure only Switch-branded layouts are parsed. Files that fail the banner/metadata checks are marked `layout mismatch` and never produce structured output.
3. **Line-item heuristics** – The parser reconstructs multi-line descriptions, normalizes numbers, and derives SKUs from eight-character tokens (or prefixes before pipes), keeping assumptions explicit in `README.md`.
4. **Private fixtures** – Real PDFs live in the `tests/veryfi_private_data` submodule so end-to-end tests can replay the workflow without relying on synthetic data.

## Assumptions

- The OCR responses use Veryfi’s default schema (`veryfi_response.ocr_text`). If Veryfi changes field names, the extractor would need updating.
- Switch invoices always contain the recognizable header, `Invoice Date / Invoice No.` row, and tabular layout described in the README.
- SKUs appear either as eight-character alphanumeric tokens inside parentheses. Otherwise, `sku` is `null`.
- The provided Veryfi credentials have sufficient quota and permissions to process the fixture PDFs whenever CI runs.

## Coding Best Practices

- **Environment isolation** – Credentials are loaded via `veryfi_test.config.load_credentials`, prioritizing env vars over `.env`. Sensitive data never lives in source control.
- **Formatting & linting** – `pre-commit` enforces `autoflake`, `black`, and `mypy` locally. GitHub Actions (`.github/workflows/quality.yml`) runs Black and mypy on every push/PR.
- **Documentation** – All public helpers, fixtures, and tests use NumPy-style docstrings. `README.md` and `tests/README.md` explain the workflow, assumptions, and how to set up pre-commit.
- **Automation** – The `integration.yml` workflow checks out submodules, installs dependencies, injects Veryfi secrets, and runs the verbose pipeline test in CI.

## Testing Strategy

- **End-to-end pytest suite** – `tests/test_pipeline.py` splits the pipeline into five tests:
  1. Run the OCR CLI and assert the exit code/files produced.
  2. Validate that every OCR JSON contains `file`, `document_id`, and `veryfi_response.ocr_text`.
  3. Run `veryfi-extract` and verify processed/saved/skipped counts.
  4. Inspect the extracted JSONs (`extracted_*.json`) to ensure metadata and line items are populated.
  5. Generate a pipeline report (`pipeline_report.json`) and print it for debugging.
- **CI parity** – The integration workflow mirrors these steps, guaranteeing the reported behavior matches what is tested locally.
## How to Extend

- Add new layouts by introducing additional extractor modules and routing logic inside `extract_cli`.
- Enhance testing by adding unit-level assertions for `_parse_line_items` or mocking the Veryfi client.
- Expand the pre-commit suite with additional linters (e.g., `ruff`) if stricter style checks are desired.

## Trade-offs

- **Real API integration vs. speed** – The pipeline tests hit Veryfi’s production API using the actual PDFs. Fidelity is excellent, but each run takes ~30 seconds and requires secrets/quota. We accept the slower feedback cycle to guarantee the CLI continues working with real data.
- **Two-step CLI workflow** – Running `veryfi-ocr` and `veryfi-extract` separately keeps responsibilities isolated (API vs. parsing) yet requires handling intermediate directories such as `outputs-ocr/`. A single “all-in-one” command would be simpler but harder to debug/extend, and it would likely re-hit the Veryfi API every time you want to re-run extraction (even if OCR artifacts already existed).
- **Regex-based extractor** – Crafting heuristics with regular expressions made implementation faster and easier to reason about, though it couples the code tightly to the current Switch layout. Supporting new templates means adjusting those regexes directly.
- **Private fixture submodule** – Shipping PDFs through `tests/veryfi_private_data` keeps the main repo clean and avoids leaking documents, but it adds the extra step of cloning/initing the submodule before running tests.
- **Heavy pre-commit hooks** – Enforcing autoflake, Black, and mypy on every commit guarantees consistent style/type safety but can feel slower or require cache tweaks in restricted environments.
- **PR-only integration tests** – The pipeline suite runs only on pull requests to minimize Veryfi API calls and quota consumption. This safeguards API limits, but individual feature branches don’t get automated integration feedback until they open a PR.
