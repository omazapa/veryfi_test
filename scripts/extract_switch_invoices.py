#!/usr/bin/env python3
"""Wrapper around the verify_extract console script for convenience."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from veryfi_test.extract_cli import main as cli_main


if __name__ == "__main__":
    raise SystemExit(cli_main())
