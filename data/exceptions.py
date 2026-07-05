"""Shared store exceptions (in-memory and Sheets backends)."""


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


class SheetsWriteError(Exception):
    """Raised when a Google Sheets write fails."""
