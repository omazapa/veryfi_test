"""Console script for extracting Switch invoice fields from a directory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Sequence

from .extractor import extract_switch_invoice

DEFAULT_OUTPUT_DIR = Path("outputs-extracted")


def _iter_json_files(input_dir: Path) -> List[Path]:
    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)
    return sorted(
        path
        for path in input_dir.iterdir()
        if path.is_file() and path.suffix.lower() == ".json"
    )


def _save_payload(output_dir: Path, source: Path, payload: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"extracted_{source.name}"
    destination.write_text(json.dumps(payload, indent=2))
    return destination


def _process_file(source: Path, output_dir: Path) -> tuple[bool, str]:
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
    parser = argparse.ArgumentParser(
        description="Extract Switch invoice fields from all JSON files in a directory."
    )
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


def run_extraction(input_dir: Path, output_dir: Path) -> dict:
    files = _iter_json_files(input_dir)
    summary = {"processed": len(files), "saved": [], "skipped": {}}

    for source in files:
        success, reason = _process_file(source, output_dir)
        if success:
            summary["saved"].append(str(source))
        else:
            summary["skipped"][str(source)] = reason

    return summary


def main(argv: Sequence[str] | None = None) -> int:
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
