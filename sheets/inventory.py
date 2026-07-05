"""Inventory worksheet — read/write helpers."""

from __future__ import annotations

from sheets.connection import dict_to_row, get_worksheet, row_to_dict

TAB = "Inventory"
HEADERS = [
    "recorded_at",
    "recorded_at_iso",
    "event_type",
    "change",
    "stock_after",
    "treatment_id",
    "logged_by",
    "notes",
]

_ws = None


def worksheet():
    global _ws
    if _ws is None:
        _ws = get_worksheet(TAB, HEADERS)
    return _ws


def load_all() -> list[dict]:
    ws = worksheet()
    values = ws.get_all_values()
    if len(values) <= 1:
        return []
    rows = []
    for row in values[1:]:
        if not row or not row[2]:
            continue
        d = row_to_dict(HEADERS, row)
        d["change"] = int(float(d["change"])) if d["change"] else 0
        d["stock_after"] = int(float(d["stock_after"])) if d["stock_after"] else 0
        if not d.get("treatment_id"):
            d["treatment_id"] = None
        rows.append(d)
    return rows


def append_entry(entry: dict) -> None:
    ws = worksheet()
    ws.append_row(dict_to_row(HEADERS, entry), value_input_option="USER_ENTERED")
