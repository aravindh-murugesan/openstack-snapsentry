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

    def _compute_scheduled_times(
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
        scheduled_dt: datetime = datetime.combine(today, self.start_time)

        local_time: ZonedDateTime = PlainDateTime.from_py_datetime(
            scheduled_dt
        ).assume_tz(self.timezone)
        utc_time: ZonedDateTime = local_time.to_tz("UTC")

        return (utc_time, local_time)

    def _is_time_window_active(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        if now is None:
            now = Instant.now()

        scheduled_utc, scheduled_local = self._compute_scheduled_times(now=now)
        is_due: bool = now >= scheduled_utc

        reason = (
            f"Current time {now} is {'within' if is_due else 'before'} "
            f"scheduled window {scheduled_utc}"
        )

        return SnapshotSchedule(
            is_due=is_due,
            scheduled_time_utc=scheduled_utc,
            scheduled_time_local=scheduled_local,
            current_time_utc=now,
            reason=reason,
        )

    def get_schedule(self) -> SnapshotSchedule:
        """
        Determine if snapshot should be created now.

        Returns:
            SnapshotSchedule with decision and reasoning
        """
        raise NotImplementedError("Must be implemented by subclass")


class DailySnapshotSchedule(BaseSnapshotPolicy):
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

    def get_schedule(self) -> SnapshotSchedule:
        """Daily snapshots only check time window."""
        return self._is_time_window_active()


class WeeklySnapshotSchedule(BaseSnapshotPolicy):
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

    def get_schedule(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        """Weekly snapshots check day and time."""
        if now is None:
            now = Instant.now()

        current_day = calendar.day_name[now.py_datetime().weekday()].lower()

        if current_day != self.start_day:
            scheduled_utc, scheduled_local = self._compute_scheduled_times(now)
            return SnapshotSchedule(
                is_due=False,
                scheduled_time_utc=scheduled_utc,
                scheduled_time_local=scheduled_local,
                current_time_utc=now,
                reason=f"Current day '{current_day}' does not match scheduled day '{self.start_day}'",
            )

        schedule: SnapshotSchedule = self._is_time_window_active(now)
        schedule.reason = (
            f"Day matches ('{current_day}') and time {now} "
            f"{'is within' if schedule.is_due else 'is before'} scheduled window {schedule.scheduled_time_utc}"
        )
        return schedule


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

    def get_schedule(self, now: Optional[Instant] = None) -> SnapshotSchedule:
        if now is None:
            now = Instant.now()

        today = now.py_datetime().date()
        schedule: SnapshotSchedule = self._is_time_window_active(now)

        try:
            expected_day = self.start_date
            datetime(today.year, today.month, expected_day)
        except ValueError:
            expected_day = calendar.monthrange(today.year, today.month)[1]

        if today.day != expected_day:
            schedule.is_due = False
            schedule.reason = (
                f"Current date (day {today.day}) does not match "
                f"scheduled date (day {expected_day})"
            )
        else:
            schedule.reason = (
                f"Date matches (day {today.day}) and time {now}"
                f"{'is within' if schedule.is_due else 'is before'} scheduled window {schedule.scheduled_time_utc}"
            )

        return schedule
