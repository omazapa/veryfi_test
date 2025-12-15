"""Console script for extracting Switch invoice fields from a directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Sequence, TypedDict

from .extractor import extract_switch_invoice

DEFAULT_OUTPUT_DIR = Path("outputs-extracted")


def _iter_json_files(input_dir: Path) -> List[Path]:
    """Return all JSON files directly under ``input_dir``.

    Parameters
    ----------
    input_dir : pathlib.Path
        Directory containing the Veryfi output files.

    Returns
    -------
    list of pathlib.Path
        Sorted list of ``*.json`` files.

    Raises
    ------
    NotADirectoryError
        If ``input_dir`` is not a directory.
    """

    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)
    return sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".json")


def _save_payload(output_dir: Path, source: Path, payload: dict) -> Path:
    """Persist the extracted payload alongside the original name.

    Parameters
    ----------
    output_dir : pathlib.Path
        Destination directory for extracted JSON files.
    source : pathlib.Path
        Original Veryfi JSON file; its name is reused with ``extracted_`` prefix.
    payload : dict
        JSON-serializable data to write.

    Returns
    -------
    pathlib.Path
        Path to the saved file.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"extracted_{source.name}"
    destination.write_text(json.dumps(payload, indent=2))
    return destination


def _process_file(source: Path, output_dir: Path) -> tuple[bool, str]:
    """Process a single Veryfi JSON file.

    Parameters
    ----------
    source : pathlib.Path
        Input JSON file containing ``veryfi_response``.
    output_dir : pathlib.Path
        Directory where the extracted payload should be written if parsing succeeds.

    Returns
    -------
    tuple
        ``(True, \"ok\")`` when the file is saved, or ``(False, reason)`` describing why it was skipped.
    """

    try:
        data = json.loads(source.read_text())
    except FileNotFoundError:
        return False, "missing file"
    except json.JSONDecodeError:
        return False, "invalid JSON"

    if not isinstance(data, dict):
        return False, "unsupported JSON structure"

    payload = data.get("veryfi_response") or {}
    fields = extract_switch_invoice(payload.get("ocr_text", ""))
    if not fields:
        return False, "layout mismatch"

    result = fields.to_dict()
    result["source"] = str(source)
    _save_payload(output_dir, source, result)
    return True, "ok"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Parameters
    ----------
    argv : sequence of str or None, optional
        Custom argument list; defaults to ``sys.argv`` when ``None``.

    Returns
    -------
    argparse.Namespace
        Parsed values (input directory, output directory).
    """

    parser = argparse.ArgumentParser(description="Extract Switch invoice fields from all JSON files in a directory.")
    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing Veryfi JSON outputs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for extracted JSON files (default: ./output_extract).",
    )
    return parser.parse_args(argv)


class ExtractionSummary(TypedDict):
    processed: int
    saved: List[str]
    skipped: Dict[str, str]


def run_extraction(input_dir: Path, output_dir: Path) -> ExtractionSummary:
    """Extract all supported documents inside ``input_dir``.

    Parameters
    ----------
    input_dir : pathlib.Path
        Directory with Veryfi OCR JSON files.
    output_dir : pathlib.Path
        Destination directory for per-document extracts.

    Returns
    -------
    dict
        Summary payload with ``processed``, ``saved`` (list of paths), and ``skipped`` mapping.
    """

    files = _iter_json_files(input_dir)
    summary: ExtractionSummary = {"processed": len(files), "saved": [], "skipped": {}}

    for source in files:
        success, reason = _process_file(source, output_dir)
        if success:
            summary["saved"].append(str(source))
        else:
            summary["skipped"][str(source)] = reason

    return summary


def main(argv: Sequence[str] | None = None) -> int:
    """Console-script entry point for the directory extractor."""

    args = parse_args(argv)
    output_dir = args.output_dir.expanduser()
    summary = run_extraction(args.input_dir.expanduser(), output_dir)

    print(
        json.dumps(
            {
                "processed": summary["processed"],
                "saved": summary["saved"],
                "skipped": summary["skipped"],
                "output_dir": str(output_dir),
            },
            indent=2,
        )
    )
    return 0


__all__ = ["main", "run_extraction"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
