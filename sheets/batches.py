"""Batches worksheet — read/write helpers."""

from __future__ import annotations

from sheets.connection import dict_to_row, get_worksheet, row_to_dict

TAB = "Batches"
HEADERS = [
    "batch_id",
    "arrived_at",
    "arrived_at_iso",
    "volume_l",
    "logged_by",
    "status",
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
    _row_index = {r["batch_id"]: i + 2 for i, r in enumerate(rows)}


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
        d = row_to_dict(HEADERS, row)
        d["volume_l"] = float(d["volume_l"]) if d["volume_l"] else 0.0
        rows.append(d)
    rebuild_index(rows)
    return rows


def append_batch(batch: dict) -> None:
    ws = worksheet()
    ws.append_row(dict_to_row(HEADERS, batch), value_input_option="USER_ENTERED")
    _row_index[batch["batch_id"]] = len(ws.get_all_values())


def update_batch(batch_id: str, fields: dict) -> None:
    ws = worksheet()
    row_num = _row_index.get(batch_id)
    if not row_num:
        values = ws.get_all_values()
        for i, row in enumerate(values[1:], start=2):
            if row and row[0] == batch_id:
                row_num = i
                _row_index[batch_id] = i
                break
    if not row_num:
        raise KeyError(f"Batch {batch_id} not found in sheet")

    current = row_to_dict(HEADERS, ws.row_values(row_num))
    current.update(fields)
    ws.update([dict_to_row(HEADERS, current)], f"A{row_num}")
