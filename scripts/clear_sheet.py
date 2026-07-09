#!/usr/bin/env python3
"""Clear all CyanTrack data from Google Sheets (headers remain)."""

import logging
import sys
from pathlib import Path

# Allow running as `uv run python scripts/clear_sheet.py`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sheets.bootstrap import reset_spreadsheet_data

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        level=logging.INFO,
    )
    reset_spreadsheet_data()
    print("Done — spreadsheet cleared (headers only).")
