import calendar
from datetime import time, date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator
from whenever import Instant, ZonedDateTime, PlainDateTime, available_timezones

from src.openstack_snapsentry.models.settings import application_settings
from src.openstack_snapsentry.models.base import OpenstackBaseModel


class SnapshotSchedule(OpenstackBaseModel):
    is_due: bool = Field(
        description="Indicates if the snapshot windows is active or not"
    )
    scheduled_time_utc: ZonedDateTime = Field(
        description="Records the expected snapshot due date/time in UTC. Computing logic are based on this converted value",
    )
    scheduled_time_local: ZonedDateTime = Field(
        description="Records the expected snapshot due date/time in user's preferred timezone for easier reference",
    )
    current_time_utc: Instant = Field(
        default_factory=Instant.now,
        description="Current time when schedule was evaluated",
    )
    reason: Optional[str] = Field(
        default=None, description="Human readable reason for the decision"
    )


class BaseSnapshotPolicy(OpenstackBaseModel):
    model_config = {
        "populate_by_name": True,
    }

    is_enabled: bool = Field(
        default=False,
        description="Indicates if daily snapshot workflow is expected for the volume",
    )
    start_time: time = Field(
        default=time.fromisoformat("23:29"),
        description="Time when snapshot should trigger (24-hour format)",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone for schedule interpretation",
    )
    retention_days: int = Field(
        ge=1,
        le=3650,  # 10 years max
        description="Number of days to retain snapshots",
    )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Ensure timezone is valid IANA timezone."""
        if v not in available_timezones():
            raise ValueError(f"Invalid timezone '{v}'. Must be a valid IANA timezone.")
        return v

    def compute_scheduled_times(
        self, now: Optional[Instant] = None
    ) -> tuple[ZonedDateTime, ZonedDateTime]:
        """
        Computes the scheduled snapshot times in both UTC and the user's preferred timezone.

        Args:
            now (Optional[Instant]): The current time as an Instant object. If None, uses the current time.

        Returns:
            tuple[ZonedDateTime, ZonedDateTime]: A tuple containing the scheduled time in UTC and in the user's timezone.
        """
        if now is None:
            now = Instant.now()

        today: date = now.py_datetime().date()

        scheduled_timeframe: datetime = datetime.combine(today, self.start_time)

        local_time: ZonedDateTime = PlainDateTime.from_py_datetime(
            scheduled_timeframe
        ).assume_tz(self.timezone)

        utc_time: ZonedDateTime = local_time.to_tz("UTC")

        return (utc_time, local_time)

    def timeframe_validation(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        if now is None:
            now = Instant.now()

        scheduled_timeframe_utc, scheduled_timeframe_zoned = (
            self.compute_scheduled_times(now=now)
        )
        is_due = now >= scheduled_timeframe_utc
        return SnapshotSchedule(
            is_due=is_due,
            scheduled_time_local=scheduled_timeframe_zoned,
            scheduled_time_utc=scheduled_timeframe_utc,
        )

    def is_snapshot_due(self) -> SnapshotSchedule:
        raise NotImplementedError("Must be implemented in subclass")


class DailySnapshotSchedule(BaseSnapshotPolicy):
    model_config = {
        "populate_by_name": True,
    }
    is_enabled: bool = Field(
        default=False,
        description="Indicates if daily snapshot workflow is expected for the volume",
        alias=application_settings.get_alias(key="daily-enabled"),
    )
    start_time: time = Field(
        default=time.fromisoformat("23:29"),
        description="Time for the snapshot to trigger.",
        alias=application_settings.get_alias(key="daily-start-time"),
    )
    timezone: str = Field(
        default="UTC",
        description="Indicates the timezone for the snapshot schedule",
        alias=application_settings.get_alias(key="daily-timezone"),
    )
    retention_type: Literal["time"] = Field(
        default="time",
        description="Indicates how the expiry has to be handled",
        alias=application_settings.get_alias(key="daily-retention-type"),
    )
    retention_days: int = Field(
        default=7,
        description="Indicates how long the snapshot has to be stored.",
        alias=application_settings.get_alias(key="daily-retention-days"),
    )

    def is_snapshot_due(self) -> SnapshotSchedule:
        is_time = self.timeframe_validation()
        is_time.reason = (
            f"Snapshot window matched: current time '{is_time.current_time_utc}' overlaps with scheduled window '{is_time.scheduled_time_utc}'. "
            "Proceeding with snapshot operation."
            if is_time.is_due
            else f"Snapshot window mismatch: current time '{is_time.current_time_utc}' is outside scheduled window '{is_time.scheduled_time_utc}'. "
            "Skipping snapshot operation."
        )
        return is_time


class WeeklySnapshotSchedule(BaseSnapshotPolicy):
    model_config = {
        "populate_by_name": True,
    }
    is_enabled: bool = Field(
        default=False,
        description="Indicates if weekly snapshot workflow is expected for the volume",
        alias=application_settings.get_alias(key="weekly-enabled"),
    )
    start_time: time = Field(
        default=time.fromisoformat("23:29"),
        description="Time for the snapshot to trigger.",
        alias=application_settings.get_alias(key="weekly-start-time"),
    )
    start_day: Literal[
        "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
    ] = Field(
        default="sunday",
        alias=application_settings.get_alias(key="weekly-start-day"),
        description="Indicates the starting day of the week for weekly snapshots.",
    )
    timezone: str = Field(
        default="UTC",
        description="Indicates the timezone for the snapshot schedule",
        alias=application_settings.get_alias(key="weekly-timezone"),
    )
    retention_type: Literal["time"] = Field(
        default="time",
        description="Indicates how the expiry has to be handled",
        alias=application_settings.get_alias(key="weekly-retention-type"),
    )
    retention_days: int = Field(
        default=30,
        description="Indicates how long the snapshot has to be stored.",
        alias=application_settings.get_alias(key="weekly-retention-days"),
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
        is_time = self.timeframe_validation()
        is_time.reason = (
            f"Snapshot window matched: current time '{is_time.current_time_utc}' and current day '{current_weekday}' overlaps with scheduled window '{is_time.scheduled_time_utc}' every '{self.start_day}'. "
            "Proceeding with snapshot operation."
            if is_time.is_due
            else f"Snapshot window mismatch: current time '{is_time.current_time_utc}' and current day '{current_weekday}' is outside scheduled window '{is_time.scheduled_time_utc}' every '{self.start_day}'. "
            "Skipping snapshot operation."
        )
        return is_time


class MonthlySnapshotSchedule(BaseSnapshotPolicy):
    model_config = {
        "populate_by_name": True,
    }
    is_enabled: bool = Field(
        default=False,
        description="Indicates if monthly snapshot workflow is expected for the volume",
        alias=application_settings.get_alias(key="monthly-enabled"),
    )
    start_time: time = Field(
        default=time.fromisoformat("23:29"),
        description="Time for the snapshot to trigger.",
        alias=application_settings.get_alias(key="monthly-start-time"),
    )
    start_date: int = Field(
        default=1,
        ge=1,
        le=31,
        alias=application_settings.get_alias(key="monthly-start-date"),
        description="Indicates the starting day of the week for monthly snapshots.",
    )
    timezone: str = Field(
        default="UTC",
        description="Indicates the timezone for the snapshot schedule",
        alias=application_settings.get_alias(key="monthly-timezone"),
    )
    retention_type: Literal["time"] = Field(
        default="time",
        description="Indicates how the expiry has to be handled",
        alias=application_settings.get_alias(key="monthly-retention-type"),
    )
    retention_days: int = Field(
        default=90,
        description="Indicates how long the snapshot has to be stored.",
        alias=application_settings.get_alias(key="monthly-retention-days"),
    )

    def is_snapshot_due(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        if now is None:
            now = Instant.now()

        today = now.py_datetime().date()

        ## Check 1: We are doing this validation earlier, since this already computes the
        # scheduled timeframe window that we can use for date checks
        is_time = self.timeframe_validation()

        try:
            ## User can provide any day of the month. So we try to replace the date from our
            # time based calculations.
            expected_date = is_time.scheduled_time_utc.replace(day=self.start_date)
        except ValueError:
            ## If the date is invalid, say 31 on months that only has 30, this replaces it
            # with the last valid day of the month.
            last_date = calendar.monthrange(today.year, today.month)[1]
            expected_date = is_time.scheduled_time_utc.replace(day=last_date)

        ## Check 1: Check current date matches expected date
        is_due = today.day == expected_date.day
        if is_due is False:
            return SnapshotSchedule(
                is_due=False,
                reason=f"Snapshot day mismatch: current day '{today.day}' does not match scheduled start day '{expected_date.day}'.",
            )

        ## Check 2: Time window matches the snapshot's desired start time.
        is_time.reason = (
            f"Snapshot window matched: current time '{is_time.current_time_utc}' and current date '{today.day}' overlaps with scheduled window '{is_time.scheduled_time_utc}' every '{self.start_date}'. "
            "Proceeding with snapshot operation."
            if is_time.is_due
            else f"Snapshot window mismatch: current time '{is_time.current_time_utc}' and current date '{today.day}' is outside scheduled window '{is_time.scheduled_time_utc}' every '{self.start_date}'. "
            "Skipping snapshot operation."
        )
        return is_time
