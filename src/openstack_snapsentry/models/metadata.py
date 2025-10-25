from typing import Optional, Literal

from pydantic import BaseModel, Field

from src.openstack_snapsentry.models.frequency import (
    DailySnapshotSchedule,
    MonthlySnapshotSchedule,
    WeeklySnapshotSchedule,
)
from src.openstack_snapsentry.models.settings import application_settings


class SnapshotMetadata(BaseModel):
    model_config = {
        "populate_by_name": True,
    }
    is_managed: Literal["true", "false"] = Field(
        description="Indicates if this volume has to be managed by SnapSentry",
        alias=application_settings.get_alias("snapsentry-managed"),
    )
    retention_expiry_time: str = Field(
        description="Indicates when this snapshot has to be retired in ISO8601 Format. Valid only for retention_type=time.",
        alias=application_settings.get_alias("snapshot-expiry-date"),
    )
    retention_expiry_time_zoned: str = Field(
        description="Indicates when this snapshot has to be retired in ISO8601 Format. Valid only for retention_type=time.",
        alias=application_settings.get_alias("snapshot-expiry-date-zoned"),
    )
    retention_days: str = Field(
        description="Indicates how long the snapshot has to be stored.",
        alias=application_settings.get_alias("snapshot-retention-days"),
    )
    retention_type: Literal["count", "time"] = Field(
        description="Indicates the rentention logic to be applied.",
        default="time",
        alias=application_settings.get_alias("snapshot-retention-type"),
    )
    frequency_type: Literal["daily", "monthly", "weekly"] = Field(
        alias=application_settings.get_alias("snapshot-frequency-type"),
    )


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

    def dump_flat_str_dict(self) -> dict[str, str]:
        """Recursively flatten model to a flat dict using only leaf keys, converting values to strings."""

        def to_str(v):
            if isinstance(v, BaseModel):
                return v.model_dump()
            elif isinstance(v, bool):
                return "true" if v else "false"
            elif isinstance(v, int):
                return str(v)
            elif v is None:
                return None
            return str(v)

        def flatten(value, out: dict):
            """Recurse through dicts and models, but keep only leaf keys."""
            if isinstance(value, BaseModel):
                value = value.model_dump()
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, (BaseModel, dict)):
                        flatten(v, out)
                    elif isinstance(v, list):
                        for item in v:
                            flatten(item, out)
                    else:
                        str_val = to_str(v)
                        if str_val is not None:  # skip None values
                            out[k] = str_val

        flat: dict[str, str] = {}
        flatten(self.model_dump(by_alias=True), flat)
        return flat

    def to_openstack_metadata(self) -> dict[str, str]:
        """Return OpenStack-compatible flattened metadata."""
        return self.dump_flat_str_dict()


class OpenstackVolume(BaseModel):
    model_config = {
        "populate_by_name": True,
    }

    id: str = Field(description="Unique id of the volume in openstack")
    name: Optional[str] = Field(default=None, description="Name of the volume")
    status: str = Field(description="Status of the openstack volume")
    snapshot_subscription: VolumeSubscriptionInfo = Field(
        description="Automated snapshot subscription information"
    )
