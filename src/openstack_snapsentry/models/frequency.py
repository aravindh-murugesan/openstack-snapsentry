import calendar
from datetime import time
from typing import Literal, Optional

from pydantic import BaseModel, Field
from whenever import Instant, ZonedDateTime

from src.openstack_snapsentry.helpers.snapshot import compute_scheduled_times
from src.openstack_snapsentry.models.settings import application_settings


class SnapshotSchedule(BaseModel):
    model_config = {
        "populate_by_name": True,
    }
    is_due: bool = Field(
        description="Indicates if the snapshot windows is active or not"
    )
    next_time_utc: Optional[ZonedDateTime] = Field(
        default=None,
        description="Records the expected snapshot due date/time in UTC. Computing logic are based on this converted value",
    )
    next_time_zoned: Optional[ZonedDateTime] = Field(
        default=None,
        description="Records the expected snapshot due date/time in user's preferred timezone for easier reference",
    )
    current_time_utc: Instant = Field(default=Instant.now())
    reason: Optional[str] = Field(default="")


class DailySnapshotSchedule(BaseModel):
    model_config = {
        "populate_by_name": True,
    }
    is_enabled: bool = Field(
        default=False,
        description="Indicates if daily snapshot workflow is expected for the volume",
        alias=f"x-{application_settings.organization}-daily-enabled",
    )
    start_time: time = Field(
        default=time.fromisoformat("23:29"),
        description="Time for the snapshot to trigger.",
        alias=f"x-{application_settings.organization}-daily-start-time",
    )
    timezone: str = Field(
        default="UTC",
        description="Indicates the timezone for the snapshot schedule",
        alias=f"x-{application_settings.organization}-daily-timezone",
    )
    retention_type: Literal["time"] = Field(
        default="time",
        description="Indicates how the expiry has to be handled",
        alias=f"x-{application_settings.organization}-daily-retention-type",
    )
    retention_days: int = Field(
        default=7,
        description="Indicates how long the snapshot has to be stored.",
        alias=f"x-{application_settings.organization}-daily-retention-days",
    )

    def is_snapshot_due(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        if now is None:
            now = Instant.now()

        scheduled_time = compute_scheduled_times(
            start_time=self.start_time, timezone=self.timezone
        )
        is_due = now >= scheduled_time.get("utc")  # type: ignore
        return SnapshotSchedule(
            is_due=is_due,
            next_time_zoned=scheduled_time.get("local"),
            next_time_utc=scheduled_time.get("utc"),
            reason=(
                f"Snapshot window matched: current time '{now}' overlaps with scheduled window '{scheduled_time.get('utc')}'. "
                "Proceeding with snapshot operation."
                if is_due
                else f"Snapshot window mismatch: current time '{now}' is outside scheduled window '{scheduled_time.get('utc')}'. "
                "Skipping snapshot operation."
            ),
        )


class WeeklySnapshotSchedule(BaseModel):
    model_config = {
        "populate_by_name": True,
    }
    is_enabled: bool = Field(
        default=False,
        description="Indicates if weekly snapshot workflow is expected for the volume",
        alias=f"x-{application_settings.organization}-weekly-enabled",
    )
    start_time: time = Field(
        default=time.fromisoformat("23:29"),
        description="Time for the snapshot to trigger.",
        alias=f"x-{application_settings.organization}-weekly-start-time",
    )
    start_day: Literal[
        "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
    ] = Field(
        default="sunday",
        alias=f"x-{application_settings.organization}-weekly-start-day",
        description="Indicates the starting day of the week for weekly snapshots.",
    )
    timezone: str = Field(
        default="UTC",
        description="Indicates the timezone for the snapshot schedule",
        alias=f"x-{application_settings.organization}-weekly-timezone",
    )
    retention_type: Literal["time"] = Field(
        default="time",
        description="Indicates how the expiry has to be handled",
        alias=f"x-{application_settings.organization}-weekly-retention-type",
    )
    retention_days: int = Field(
        default=7,
        description="Indicates how long the snapshot has to be stored.",
        alias=f"x-{application_settings.organization}-weekly-retention-days",
    )

    def is_snapshot_due(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        if now is None:
            now = Instant.now()

        current_weekday_number = now.py_datetime().weekday()
        current_weekday = calendar.day_name[current_weekday_number].lower()

        ## Check 1: Current day matches scheduled day
        is_due = current_weekday == self.start_day
        if is_due is False:
            return SnapshotSchedule(
                is_due=False,
                reason=f"Snapshot day mismatch: current day '{current_weekday}' does not match scheduled start day '{self.start_day}'.",
            )

        ## Check 2: Time window matches the snapshot's desired start time.
        scheduled_time = compute_scheduled_times(
            start_time=self.start_time, timezone=self.timezone
        )

        is_due = now >= scheduled_time.get("utc")  # type: ignore
        return SnapshotSchedule(
            is_due=is_due,
            next_time_zoned=scheduled_time.get("local"),
            next_time_utc=scheduled_time.get("utc"),
            reason=(
                f"Snapshot window matched: current time '{now}' and current day '{current_weekday}' overlaps with scheduled window '{scheduled_time.get('utc')}' every '{self.start_day}'. "
                "Proceeding with snapshot operation."
                if is_due
                else f"Snapshot window mismatch: current time '{now}' and current day '{current_weekday}' is outside scheduled window '{scheduled_time.get('utc')}' every '{self.start_day}'. "
                "Skipping snapshot operation."
            ),
        )


class MonthlySnapshotSchedule(BaseModel):
    model_config = {
        "populate_by_name": True,
    }
    is_enabled: bool = Field(
        default=False,
        description="Indicates if monthly snapshot workflow is expected for the volume",
        alias=f"x-{application_settings.organization}-monthly-enabled",
    )
    start_time: time = Field(
        default=time.fromisoformat("23:29"),
        description="Time for the snapshot to trigger.",
        alias=f"x-{application_settings.organization}-monthly-start-time",
    )
    start_date: int = Field(
        default=1,
        ge=1,
        le=31,
        alias=f"x-{application_settings.organization}-monthly-start-date",
        description="Indicates the starting day of the week for monthly snapshots.",
    )
    timezone: str = Field(
        default="UTC",
        description="Indicates the timezone for the snapshot schedule",
        alias=f"x-{application_settings.organization}-monthly-timezone",
    )
    retention_type: Literal["time"] = Field(
        default="time",
        description="Indicates how the expiry has to be handled",
        alias=f"x-{application_settings.organization}-monthly-retention-type",
    )
    retention_days: int = Field(
        default=7,
        description="Indicates how long the snapshot has to be stored.",
        alias=f"x-{application_settings.organization}-monthly-retention-days",
    )

    def is_snapshot_due(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        if now is None:
            now = Instant.now()

        today = now.py_datetime().date()
        scheduled_time = compute_scheduled_times(
            start_time=self.start_time, timezone=self.timezone
        )

        try:
            expected_date = scheduled_time.get("utc").replace(day=self.start_date)
        except ValueError:
            last_date = calendar.monthrange(today.year, today.month)[1]
            expected_date = scheduled_time.get("utc").replace(day=last_date)

        ## Check 1: Check current date matches expected date
        is_due = today.day == expected_date.day
        if is_due is False:
            return SnapshotSchedule(
                is_due=False,
                reason=f"Snapshot day mismatch: current day '{today.day}' does not match scheduled start day '{expected_date.day}'.",
            )

        ## Check 2: Time window matches the snapshot's desired start time.
        is_due = now >= scheduled_time.get("utc")  # type: ignore
        return SnapshotSchedule(
            is_due=is_due,
            next_time_zoned=scheduled_time.get("local"),
            next_time_utc=scheduled_time.get("utc"),
            reason=(
                f"Snapshot window matched: current time '{now}' and current date '{today.day}' overlaps with scheduled window '{scheduled_time.get('utc')}' every '{expected_date.day}'. "
                "Proceeding with snapshot operation."
                if is_due
                else f"Snapshot window mismatch: current time '{now}' and current date '{today.day}' is outside scheduled window '{scheduled_time.get('utc')}' every '{expected_date.day}'. "
                "Skipping snapshot operation."
            ),
        )
