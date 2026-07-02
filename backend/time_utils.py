"""East Africa Time helpers (Africa/Dar_es_Salaam)."""

import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Africa/Dar_es_Salaam")


def now_local() -> datetime.datetime:
    """Naive local datetime for DB storage (Dar es Salaam wall clock)."""
    return datetime.datetime.now(TZ).replace(tzinfo=None)


def now_local_iso() -> str:
    return datetime.datetime.now(TZ).isoformat()


def format_local(dt: datetime.datetime | None = None, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    if dt is None:
        dt = now_local()
    return dt.strftime(fmt)
