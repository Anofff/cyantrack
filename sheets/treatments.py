"""Treatments worksheet — read/write helpers."""

from __future__ import annotations

from datetime import datetime

from sheets.connection import dict_to_row, get_worksheet, row_to_dict

TAB = "Treatments"
HEADERS = [
    "treatment_id",
    "batch_id",
    "started_at",
    "started_at_iso",
    "ended_at",
    "ended_at_iso",
    "duration_minutes",
    "hypochlorite_buckets",
    "staff_count",
    "logged_by",
    "notes",
]

_ws = None
_row_index: dict[str, int] = {}


def worksheet():
    global _ws
    if _ws is None:
        _ws = get_worksheet(TAB, HEADERS)
    return _ws


def rebuild_index(rows: list[dict]) -> None:
    global _row_index
    _row_index = {r["treatment_id"]: i + 2 for i, r in enumerate(rows)}


def _parse_row(d: dict) -> dict:
    iso = d.get("started_at_iso", "")
    d["started_at_raw"] = datetime.fromisoformat(iso) if iso else None
    for field in ("duration_minutes", "hypochlorite_buckets", "staff_count"):
        val = d.get(field, "")
        if val == "" or val is None:
            d[field] = None
        else:
            d[field] = float(val) if field == "duration_minutes" else int(float(val))
    if not d.get("ended_at"):
        d["ended_at"] = None
    if not d.get("ended_at_iso"):
        d["ended_at_iso"] = None
    return d


def load_all() -> list[dict]:
    ws = worksheet()
    values = ws.get_all_values()
    if len(values) <= 1:
        rebuild_index([])
        return []
    rows = []
    for row in values[1:]:
        if not row or not row[0]:
            continue
        rows.append(_parse_row(row_to_dict(HEADERS, row)))
    rebuild_index(rows)
    return rows


def append_treatment(treatment: dict) -> None:
    ws = worksheet()
    row = {k: treatment.get(k, "") for k in HEADERS}
    row.pop("started_at_raw", None)
    ws.append_row(dict_to_row(HEADERS, row), value_input_option="USER_ENTERED")
    _row_index[treatment["treatment_id"]] = len(ws.get_all_values())


def update_treatment(treatment_id: str, fields: dict) -> None:
    ws = worksheet()
    row_num = _row_index.get(treatment_id)
    if not row_num:
        values = ws.get_all_values()
        for i, row in enumerate(values[1:], start=2):
            if row and row[0] == treatment_id:
                row_num = i
                _row_index[treatment_id] = i
                break
    if not row_num:
        raise KeyError(f"Treatment {treatment_id} not found in sheet")

    current = row_to_dict(HEADERS, ws.row_values(row_num))
    current.update({k: v for k, v in fields.items() if k in HEADERS})
    ws.update([dict_to_row(HEADERS, current)], f"A{row_num}")
