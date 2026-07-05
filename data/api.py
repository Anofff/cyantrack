"""
data/api.py
───────────
Single import point for the data layer.

Uses Google Sheets when SPREADSHEET_ID is set, otherwise in-memory store.
"""

from config import SPREADSHEET_ID

if SPREADSHEET_ID:
    from sheets.bootstrap import bootstrap_if_needed  # noqa: F401
    from sheets.client import (  # noqa: F401
        hydrate,
        log_arrival,
        get_active_batch,
        update_batch_status,
        get_all_batches,
        start_treatment,
        get_active_treatment,
        end_treatment,
        get_stock,
        validate_stock_deduction,
        add_stock,
        monthly_report,
    )
    from data.exceptions import (  # noqa: F401
        ActiveBatchError,
        InsufficientStockError,
        InvalidBatchStateError,
        SheetsWriteError,
    )
else:
    from data.store import (  # noqa: F401
        log_arrival,
        get_active_batch,
        update_batch_status,
        get_all_batches,
        start_treatment,
        get_active_treatment,
        end_treatment,
        get_stock,
        validate_stock_deduction,
        add_stock,
        monthly_report,
    )
    from data.exceptions import (  # noqa: F401
        ActiveBatchError,
        InsufficientStockError,
        InvalidBatchStateError,
        SheetsWriteError,
    )

    def hydrate() -> None:
        return

    def bootstrap_if_needed() -> bool:
        return False
