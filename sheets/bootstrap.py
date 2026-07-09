"""
sheets/bootstrap.py
───────────────────
Detect an empty / uninitialized spreadsheet and create the CyanTrack tab skeleton.
"""

from __future__ import annotations

import logging

import gspread

from sheets.batches import HEADERS as BATCHES_HEADERS, TAB as BATCHES_TAB
from sheets.connection import clear_worksheet_cache, get_spreadsheet
from sheets.inventory import HEADERS as INVENTORY_HEADERS, TAB as INVENTORY_TAB
from sheets.treatments import HEADERS as TREATMENTS_HEADERS, TAB as TREATMENTS_TAB

log = logging.getLogger(__name__)

# Default blank tab Google creates for new spreadsheets
DEFAULT_SHEET_TAB = "Sheet1"

# Required tabs in display order
TAB_SCHEMA: dict[str, list[str]] = {
    BATCHES_TAB:    BATCHES_HEADERS,
    TREATMENTS_TAB: TREATMENTS_HEADERS,
    INVENTORY_TAB:  INVENTORY_HEADERS,
}


def _col_letter(n: int) -> str:
    """1-based column index → letter (A, B, …). Fine for our ≤11 columns."""
    return chr(64 + n)


def is_spreadsheet_empty(sh: gspread.Spreadsheet | None = None) -> bool:
    """
    True when the spreadsheet has no CyanTrack data tabs set up yet.

    Triggers bootstrap when:
      - any required tab (Batches / Treatments / Inventory) is missing
      - a required tab exists but row 1 is not the expected header row
      - only the default Sheet1 exists (brand-new spreadsheet)
    """
    sh = sh or get_spreadsheet()
    titles = {ws.title for ws in sh.worksheets()}

    if not set(TAB_SCHEMA).issubset(titles):
        return True

    if titles == {DEFAULT_SHEET_TAB}:
        return True

    for tab, headers in TAB_SCHEMA.items():
        row1 = sh.worksheet(tab).row_values(1)
        if row1 != headers:
            return True

    return False


def _format_header_row(ws: gspread.Worksheet, num_cols: int) -> None:
    """Bold header row and freeze it for scrolling."""
    end_col = _col_letter(num_cols)
    ws.freeze(rows=1)
    ws.format(
        f"A1:{end_col}1",
        {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.93, "green": 0.93, "blue": 0.93},
        },
    )


def _setup_worksheet(sh: gspread.Spreadsheet, tab: str, headers: list[str]) -> gspread.Worksheet:
    """Create tab if missing and ensure header row matches schema."""
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        log.info("Creating worksheet %r", tab)
        ws = sh.add_worksheet(title=tab, rows=1000, cols=len(headers))

    row1 = ws.row_values(1)
    if row1 != headers:
        log.info("Writing headers for %r", tab)
        ws.update([headers], "A1", value_input_option="USER_ENTERED")

    _format_header_row(ws, len(headers))
    return ws


def _remove_default_sheet_if_empty(sh: gspread.Spreadsheet) -> None:
    """Delete the blank Sheet1 tab left over from a new spreadsheet."""
    try:
        default = sh.worksheet(DEFAULT_SHEET_TAB)
    except gspread.WorksheetNotFound:
        return

    values = default.get_all_values()
    if values and any(cell.strip() for row in values for cell in row):
        log.info("Keeping %r — it contains data", DEFAULT_SHEET_TAB)
        return

    if len(sh.worksheets()) <= 1:
        log.info("Skipping delete of %r — must keep at least one tab", DEFAULT_SHEET_TAB)
        return

    log.info("Removing empty default worksheet %r", DEFAULT_SHEET_TAB)
    sh.del_worksheet(default)


def bootstrap_spreadsheet(force: bool = False) -> bool:
    """
    Create CyanTrack tabs and header rows if the sheet is empty or uninitialized.

    Returns True if bootstrap ran, False if the spreadsheet was already set up.
    """
    sh = get_spreadsheet()

    if not force and not is_spreadsheet_empty(sh):
        log.debug("Spreadsheet already initialized — skipping bootstrap")
        return False

    log.info("Bootstrapping spreadsheet skeleton...")

    for tab, headers in TAB_SCHEMA.items():
        _setup_worksheet(sh, tab, headers)

    _remove_default_sheet_if_empty(sh)
    clear_worksheet_cache()
    _reset_module_caches()

    log.info("Spreadsheet skeleton ready: %s", ", ".join(TAB_SCHEMA))
    return True


def bootstrap_if_needed() -> bool:
    """Convenience wrapper — bootstrap only when the sheet needs it."""
    return bootstrap_spreadsheet(force=False)


def reset_spreadsheet_data() -> None:
    """
    Wipe all data rows and restore header-only skeleton.
    Use before production go-live or to discard pilot/test data.
    """
    sh = get_spreadsheet()
    log.info("Resetting spreadsheet — clearing all data rows...")

    for tab, headers in TAB_SCHEMA.items():
        try:
            ws = sh.worksheet(tab)
        except gspread.WorksheetNotFound:
            log.warning("Tab %r missing — will be created", tab)
            _setup_worksheet(sh, tab, headers)
            continue

        ws.clear()
        ws.update([headers], "A1", value_input_option="USER_ENTERED")
        _format_header_row(ws, len(headers))

    _remove_default_sheet_if_empty(sh)
    clear_worksheet_cache()
    _reset_module_caches()
    log.info("Spreadsheet reset complete — headers only, no data rows")


def _reset_module_caches() -> None:
    """Clear per-module worksheet singletons after tabs are created/recreated."""
    from sheets import batches, inventory, treatments

    batches._ws = None
    treatments._ws = None
    inventory._ws = None
