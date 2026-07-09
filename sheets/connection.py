"""Google Sheets connection and worksheet bootstrap."""

from __future__ import annotations

import json
import logging

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_CREDENTIALS_JSON, GOOGLE_CREDENTIALS_PATH, SPREADSHEET_ID

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_spreadsheet: gspread.Spreadsheet | None = None
_worksheets: dict[str, gspread.Worksheet] = {}


def clear_worksheet_cache() -> None:
    """Reset cached worksheet handles (e.g. after bootstrap creates new tabs)."""
    _worksheets.clear()


def _get_credentials() -> Credentials:
    json_str = GOOGLE_CREDENTIALS_JSON.strip()
    if json_str:
        return Credentials.from_service_account_info(json.loads(json_str), scopes=SCOPES)
    return Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)


def get_spreadsheet() -> gspread.Spreadsheet:
    global _spreadsheet
    if _spreadsheet is None:
        if not SPREADSHEET_ID:
            raise RuntimeError("SPREADSHEET_ID is not set in .env")
        creds = _get_credentials()
        _spreadsheet = gspread.authorize(creds).open_by_key(SPREADSHEET_ID)
        log.info("Connected to spreadsheet: %s", _spreadsheet.title)
    return _spreadsheet


def get_worksheet(name: str, headers: list[str]) -> gspread.Worksheet:
    if name in _worksheets:
        return _worksheets[name]

    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(name)
    except gspread.WorksheetNotFound:
        log.info("Creating worksheet %r", name)
        ws = sh.add_worksheet(title=name, rows=1000, cols=len(headers))

    existing = ws.row_values(1)
    if not existing:
        ws.append_row(headers, value_input_option="USER_ENTERED")
    elif existing != headers:
        log.warning("Worksheet %r headers differ from expected — leaving as-is", name)

    _worksheets[name] = ws
    return ws


def row_to_dict(headers: list[str], row: list) -> dict:
    padded = row + [""] * (len(headers) - len(row))
    return dict(zip(headers, padded[: len(headers)]))


def dict_to_row(headers: list[str], data: dict) -> list:
    return [data.get(h, "") if data.get(h) is not None else "" for h in headers]
