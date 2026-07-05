"""
data/store.py
─────────────
In-memory data store for CyanTrack.

Every function here has the EXACT same signature that sheets/client.py
will implement later. When you're ready to go live with Google Sheets,
you swap the import in each handler from:

    from data.store import ...
to:
    from sheets.client import ...

Zero changes to bot code.
"""

from datetime import datetime, timezone
from typing import Optional


class ActiveBatchError(Exception):
    """Raised when logging arrival while a batch is still pending or treating."""

    def __init__(self, batch: dict):
        self.batch = batch
        super().__init__(batch["batch_id"])


class InsufficientStockError(Exception):
    """Raised when a treatment would deduct more buckets than available."""

    def __init__(self, buckets: int, current: int):
        self.buckets = buckets
        self.current = current
        super().__init__(f"need {buckets}, have {current}")


class InvalidBatchStateError(Exception):
    """Raised when starting treatment on a batch that is not pending."""

    def __init__(self, batch_id: str, status: str):
        self.batch_id = batch_id
        self.status = status
        super().__init__(f"batch {batch_id} is {status}")

# ── in-memory tables ──────────────────────────────────────────────────────────

_batches: list[dict] = []
_treatments: list[dict] = []
_inventory: list[dict] = []

# ── helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")

def _next_id(table: list, prefix: str, id_field: str) -> str:
    nums = []
    for row in table:
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

# ── BATCHES ───────────────────────────────────────────────────────────────────

def log_arrival(volume: float, logged_by: str, notes: str = "") -> dict:
    active = get_active_batch()
    if active:
        raise ActiveBatchError(active)

    batch = {
        "batch_id":   _next_id(_batches, "B", "batch_id"),
        "arrived_at": _now(),
        "volume_l":   volume,
        "logged_by":  logged_by,
        "status":     "pending",
        "notes":      notes,
    }
    _batches.append(batch)
    return batch


def get_active_batch() -> Optional[dict]:
    """Return the most recent batch that is pending or being treated."""
    for batch in reversed(_batches):
        if batch["status"] in ("pending", "treating"):
            return batch
    return None


def update_batch_status(batch_id: str, status: str) -> None:
    for batch in _batches:
        if batch["batch_id"] == batch_id:
            batch["status"] = status
            return


def get_all_batches() -> list[dict]:
    return list(reversed(_batches))

# ── TREATMENTS ────────────────────────────────────────────────────────────────

def start_treatment(batch_id: str, logged_by: str) -> dict:
    batch = next((b for b in _batches if b["batch_id"] == batch_id), None)
    if not batch:
        raise ValueError(f"Batch {batch_id} not found")
    if batch["status"] != "pending":
        raise InvalidBatchStateError(batch_id, batch["status"])
    if get_active_treatment(batch_id):
        raise InvalidBatchStateError(batch_id, "treating")

    treatment = {
        "treatment_id":          _next_id(_treatments, "T", "treatment_id"),
        "batch_id":              batch_id,
        "started_at":            _now(),
        "started_at_raw":        datetime.now(timezone.utc),
        "ended_at":              None,
        "duration_minutes":      None,
        "hypochlorite_buckets":  None,
        "staff_count":           None,
        "logged_by":             logged_by,
        "notes":                 "",
    }
    _treatments.append(treatment)
    update_batch_status(batch_id, "treating")
    return treatment


def get_active_treatment(batch_id: str) -> Optional[dict]:
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
    for t in _treatments:
        if t["treatment_id"] == treatment_id:
            stock_err = validate_stock_deduction(buckets)
            if stock_err:
                raise InsufficientStockError(buckets, _current_stock())

            now = datetime.now(timezone.utc)
            started = t["started_at_raw"]
            duration = round((now - started).total_seconds() / 60, 1)

            t["ended_at"]             = now.strftime("%d %b %Y, %H:%M UTC")
            t["duration_minutes"]     = duration
            t["hypochlorite_buckets"] = buckets
            t["staff_count"]          = staff
            t["logged_by"]            = logged_by
            t["notes"]                = notes

            # deduct from inventory
            current = _current_stock()
            new_stock = current - buckets
            _inventory.append({
                "recorded_at":   now.strftime("%d %b %Y, %H:%M UTC"),
                "event_type":    "usage",
                "change":        -buckets,
                "stock_after":   new_stock,
                "treatment_id":  treatment_id,
                "logged_by":     logged_by,
                "notes":         "",
            })

            # mark batch treated
            update_batch_status(t["batch_id"], "treated")
            t["new_stock"] = new_stock
            return t

    raise ValueError(f"Treatment {treatment_id} not found")

# ── INVENTORY ─────────────────────────────────────────────────────────────────

def get_stock() -> int:
    return _current_stock()


def validate_stock_deduction(buckets: int) -> Optional[str]:
    """Return an error message if buckets cannot be deducted, else None."""
    current = _current_stock()
    if buckets > current:
        return (
            f"Not enough hypochlorite: *{buckets} buckets* needed, "
            f"only *{current}* in stock.\n\nRestock before completing treatment."
        )
    return None


def add_stock(buckets: int, logged_by: str, notes: str = "") -> int:
    current = _current_stock()
    new_stock = current + buckets
    _inventory.append({
        "recorded_at":  _now(),
        "event_type":   "restock",
        "change":       +buckets,
        "stock_after":  new_stock,
        "treatment_id": None,
        "logged_by":    logged_by,
        "notes":        notes,
    })
    return new_stock

# ── REPORTS ───────────────────────────────────────────────────────────────────

def monthly_report(month: int, year: int) -> dict:
    month_str = f"{year}-{month:02d}"

    batches = [
        b for b in _batches
        if b["arrived_at"] and datetime.strptime(
            b["arrived_at"], "%d %b %Y, %H:%M UTC"
        ).strftime("%Y-%m") == month_str
    ]

    treatments = [
        t for t in _treatments
        if t["ended_at"] and datetime.strptime(
            t["ended_at"], "%d %b %Y, %H:%M UTC"
        ).strftime("%Y-%m") == month_str
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
