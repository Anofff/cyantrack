"""
sheets/client.py
────────────────
Google Sheets persistence — same public API as data/store.py.

Handlers import via data/api.py (or directly from here when SPREADSHEET_ID is set).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from config import DISPLAY_TZ
from data.exceptions import (
    ActiveBatchError,
    InsufficientStockError,
    InvalidBatchStateError,
    SheetsWriteError,
)
from sheets.bootstrap import bootstrap_if_needed, bootstrap_spreadsheet, is_spreadsheet_empty
from sheets import batches as sh_batches
from sheets import inventory as sh_inventory
from sheets import treatments as sh_treatments

log = logging.getLogger(__name__)

_batches: list[dict] = []
_treatments: list[dict] = []
_inventory: list[dict] = []
_hydrated = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_display(dt: datetime) -> str:
    local = dt.astimezone(ZoneInfo(DISPLAY_TZ))
    tz_label = local.strftime("%Z") or DISPLAY_TZ
    return local.strftime(f"%d %b %Y, %H:%M {tz_label}")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _month_key(iso_str: str) -> str:
    return datetime.fromisoformat(iso_str).strftime("%Y-%m")


def _next_id(rows: list[dict], prefix: str, id_field: str) -> str:
    nums = []
    for row in rows:
        row_id = row.get(id_field, "")
        if row_id.startswith(prefix):
            try:
                nums.append(int(row_id[len(prefix):]))
            except ValueError:
                pass
    return f"{prefix}{max(nums, default=0) + 1:03d}"


def _current_stock() -> int:
    if not _inventory:
        return 0
    return _inventory[-1]["stock_after"]


def _ensure_hydrated() -> None:
    if not _hydrated:
        hydrate()


def hydrate() -> None:
    """Load all sheet data into memory. Call once at bot startup."""
    global _batches, _treatments, _inventory, _hydrated
    log.info("Hydrating state from Google Sheets...")
    bootstrap_if_needed()
    _batches = sh_batches.load_all()
    _treatments = sh_treatments.load_all()
    _inventory = sh_inventory.load_all()
    _hydrated = True
    log.info(
        "Hydrated: %d batches, %d treatments, %d inventory rows, stock=%d",
        len(_batches), len(_treatments), len(_inventory), _current_stock(),
    )


# ── BATCHES ───────────────────────────────────────────────────────────────────

def log_arrival(volume: float, logged_by: str, notes: str = "") -> dict:
    _ensure_hydrated()
    active = get_active_batch()
    if active:
        raise ActiveBatchError(active)

    now = _utc_now()
    batch = {
        "batch_id":       _next_id(_batches, "B", "batch_id"),
        "arrived_at":     _format_display(now),
        "arrived_at_iso": _iso(now),
        "volume_l":       volume,
        "logged_by":      logged_by,
        "status":         "pending",
        "notes":          notes,
    }
    try:
        sh_batches.append_batch(batch)
    except Exception as e:
        log.error("Failed to write batch to Sheets: %s", e)
        raise SheetsWriteError(f"Could not save arrival: {e}") from e
    _batches.append(batch)
    return batch


def get_active_batch() -> Optional[dict]:
    _ensure_hydrated()
    for batch in reversed(_batches):
        if batch["status"] in ("pending", "treating"):
            return batch
    return None


def update_batch_status(batch_id: str, status: str) -> None:
    _ensure_hydrated()
    for batch in _batches:
        if batch["batch_id"] == batch_id:
            batch["status"] = status
            try:
                sh_batches.update_batch(batch_id, {"status": status})
            except Exception as e:
                log.error("Failed to update batch status in Sheets: %s", e)
                raise SheetsWriteError(f"Could not update batch: {e}") from e
            return


def get_all_batches() -> list[dict]:
    _ensure_hydrated()
    return list(reversed(_batches))


# ── TREATMENTS ────────────────────────────────────────────────────────────────

def start_treatment(batch_id: str, logged_by: str) -> dict:
    _ensure_hydrated()
    batch = next((b for b in _batches if b["batch_id"] == batch_id), None)
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")
    if batch["status"] != "pending":
        raise InvalidBatchStateError(batch_id, batch["status"])
    if get_active_treatment(batch_id):
        raise InvalidBatchStateError(batch_id, "treating")

    now = _utc_now()
    treatment = {
        "treatment_id":         _next_id(_treatments, "T", "treatment_id"),
        "batch_id":             batch_id,
        "started_at":           _format_display(now),
        "started_at_iso":       _iso(now),
        "started_at_raw":       now,
        "ended_at":             None,
        "ended_at_iso":         None,
        "duration_minutes":     None,
        "hypochlorite_buckets": None,
        "staff_count":          None,
        "logged_by":            logged_by,
        "notes":                "",
    }
    try:
        sh_treatments.append_treatment(treatment)
        sh_batches.update_batch(batch_id, {"status": "treating"})
    except Exception as e:
        log.error("Failed to start treatment in Sheets: %s", e)
        raise SheetsWriteError(f"Could not start treatment: {e}") from e
    _treatments.append(treatment)
    batch["status"] = "treating"
    return treatment


def get_active_treatment(batch_id: str) -> Optional[dict]:
    _ensure_hydrated()
    for t in reversed(_treatments):
        if t["batch_id"] == batch_id and t["ended_at"] is None:
            return t
    return None


def end_treatment(
    treatment_id: str,
    buckets: int,
    staff: int,
    logged_by: str,
    notes: str = "",
) -> dict:
    _ensure_hydrated()
    for t in _treatments:
        if t["treatment_id"] != treatment_id:
            continue

        stock_err = validate_stock_deduction(buckets)
        if stock_err:
            raise InsufficientStockError(buckets, _current_stock())

        now = _utc_now()
        started = t["started_at_raw"]
        duration = round((now - started).total_seconds() / 60, 1)
        current = _current_stock()
        new_stock = current - buckets
        batch_id = t["batch_id"]

        sheet_fields = {
            "ended_at":             _format_display(now),
            "ended_at_iso":         _iso(now),
            "duration_minutes":     duration,
            "hypochlorite_buckets": buckets,
            "staff_count":          staff,
            "logged_by":            logged_by,
            "notes":                notes,
        }
        inv_entry = {
            "recorded_at":     _format_display(now),
            "recorded_at_iso": _iso(now),
            "event_type":      "usage",
            "change":          -buckets,
            "stock_after":     new_stock,
            "treatment_id":    treatment_id,
            "logged_by":       logged_by,
            "notes":           "",
        }

        try:
            sh_treatments.update_treatment(treatment_id, sheet_fields)
            sh_inventory.append_entry(inv_entry)
            sh_batches.update_batch(batch_id, {"status": "treated"})
        except Exception as e:
            log.error("Failed to complete treatment in Sheets: %s", e)
            raise SheetsWriteError(f"Could not save treatment: {e}") from e

        t.update(sheet_fields)
        t["new_stock"] = new_stock
        _inventory.append(inv_entry)
        for batch in _batches:
            if batch["batch_id"] == batch_id:
                batch["status"] = "treated"
                break
        return t

    raise ValueError(f"Treatment {treatment_id} not found")


# ── INVENTORY ─────────────────────────────────────────────────────────────────

def get_stock() -> int:
    _ensure_hydrated()
    return _current_stock()


def validate_stock_deduction(buckets: int) -> Optional[str]:
    _ensure_hydrated()
    current = _current_stock()
    if buckets > current:
        return (
            f"Not enough hypochlorite: *{buckets} buckets* needed, "
            f"only *{current}* in stock.\n\nRestock before completing treatment."
        )
    return None


def add_stock(buckets: int, logged_by: str, notes: str = "") -> int:
    _ensure_hydrated()
    current = _current_stock()
    new_stock = current + buckets
    now = _utc_now()
    entry = {
        "recorded_at":     _format_display(now),
        "recorded_at_iso": _iso(now),
        "event_type":      "restock",
        "change":          +buckets,
        "stock_after":     new_stock,
        "treatment_id":    None,
        "logged_by":       logged_by,
        "notes":           notes,
    }
    try:
        sh_inventory.append_entry(entry)
    except Exception as e:
        log.error("Failed to add stock in Sheets: %s", e)
        raise SheetsWriteError(f"Could not save stock: {e}") from e
    _inventory.append(entry)
    return new_stock


# ── REPORTS ───────────────────────────────────────────────────────────────────

def monthly_report(month: int, year: int) -> dict:
    _ensure_hydrated()
    month_str = f"{year}-{month:02d}"

    batches = [
        b for b in _batches
        if b.get("arrived_at_iso") and _month_key(b["arrived_at_iso"]) == month_str
    ]
    treatments = [
        t for t in _treatments
        if t.get("ended_at_iso") and _month_key(t["ended_at_iso"]) == month_str
    ]

    durations = [t["duration_minutes"] for t in treatments if t["duration_minutes"]]
    buckets_list = [t["hypochlorite_buckets"] for t in treatments if t["hypochlorite_buckets"]]
    staff_list = [t["staff_count"] for t in treatments if t["staff_count"]]

    return {
        "arrivals":          len(batches),
        "total_volume":      sum(b["volume_l"] for b in batches),
        "treatments_done":   len(treatments),
        "total_buckets":     sum(buckets_list),
        "avg_duration_mins": round(sum(durations) / len(durations), 1) if durations else 0,
        "min_duration":      min(durations) if durations else 0,
        "max_duration":      max(durations) if durations else 0,
        "avg_staff":         round(sum(staff_list) / len(staff_list), 1) if staff_list else 0,
        "current_stock":     _current_stock(),
    }
