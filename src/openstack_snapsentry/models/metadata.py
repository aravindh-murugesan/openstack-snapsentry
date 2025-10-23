from typing import Optional

from pydantic import BaseModel, Field

from src.openstack_snapsentry.models.frequency import (
    DailySnapshotSchedule,
    MonthlySnapshotSchedule,
    WeeklySnapshotSchedule,
)
from src.openstack_snapsentry.models.settings import application_settings


class VolumeSubscriptionInfo(BaseModel):
    model_config = {
        "populate_by_name": True,
    }
    is_enabled: bool = Field(
        default=False,
        description="Indicates if this volume has to be managed by SnapSentry",
        alias=application_settings.get_alias("snapsentry-managed"),
    )
    snapshot_policy_daily: Optional[DailySnapshotSchedule] = None
    snapshot_policy_weekly: Optional[WeeklySnapshotSchedule] = None
    snapshot_policy_monthly: Optional[MonthlySnapshotSchedule] = None

    @classmethod
    def load_fields_from_dict(cls, data: dict):
        snapshot_policy_daily = DailySnapshotSchedule(**data)
        snapshot_policy_weekly = WeeklySnapshotSchedule(**data)
        snapshot_policy_monthly = MonthlySnapshotSchedule(**data)

        return cls(
            **data,
            snapshot_policy_daily=snapshot_policy_daily
            if snapshot_policy_daily.is_enabled
            else None,
            snapshot_policy_weekly=WeeklySnapshotSchedule(**data)
            if snapshot_policy_weekly.is_enabled
            else None,
            snapshot_policy_monthly=MonthlySnapshotSchedule(**data)
            if snapshot_policy_monthly.is_enabled
            else None,
        )
