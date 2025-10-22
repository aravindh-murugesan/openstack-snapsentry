from datetime import date, datetime, time
from typing import Optional

from whenever import Instant, PlainDateTime, ZonedDateTime


def compute_scheduled_times(
    start_time: time,
    timezone: str = "UTC",
    now: Optional[Instant] = None,
) -> dict[str, ZonedDateTime]:
    """Returns local and UTC scheduled snapshot timeframe for the day"""

    if now is None:
        now = Instant.now()

    today: date = now.py_datetime().date()
    scheduled_time: date = datetime.combine(today, start_time)

    local_time: ZonedDateTime = PlainDateTime.from_py_datetime(
        scheduled_time
    ).assume_tz(timezone)
    print(f"{local_time=}")

    utc_time: ZonedDateTime = local_time.to_tz("UTC")
    print(f"{utc_time=}")

    return {"local": local_time, "utc": utc_time}
