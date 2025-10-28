from datetime import datetime
from typing import List, Optional

import structlog
from openstack.block_storage.v3.snapshot import Snapshot
from openstack.connection import Connection
from whenever import PlainDateTime, ZonedDateTime

from src.openstack_snapsentry.models.frequency import SnapshotSchedule
from src.openstack_snapsentry.models.metadata import OpenstackVolume, SnapshotMetadata
from src.openstack_snapsentry.models.settings import application_settings


class SnapshotCreationError(Exception):
    """Raised when snapshot creation fails."""

    pass


class SnapshotFrequency:
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @classmethod
    def all(cls) -> List[str]:
        return [cls.DAILY, cls.WEEKLY, cls.MONTHLY]


class SnapshotScheduler:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.logger: structlog.BoundLogger = structlog.get_logger(__name__).bind(
            project_id=connection.current_project_id
        )

    def _get_policy(self, volume: OpenstackVolume, frequency: str):
        policy_map = {
            SnapshotFrequency.DAILY: volume.snapshot_subscription.snapshot_policy_daily,
            SnapshotFrequency.WEEKLY: volume.snapshot_subscription.snapshot_policy_weekly,
            SnapshotFrequency.MONTHLY: volume.snapshot_subscription.snapshot_policy_monthly,
        }

        return policy_map.get(frequency)

    def _get_existing_managed_snapshots(
        self, volume_id: str, frequency: str
    ) -> List[Snapshot]:
        self.logger.debug(
            "Attempting to fetch managed snapshots for the volume", volume_id=volume_id
        )
        try:
            snapshots: List[Snapshot] = list(
                self.connection.list_volume_snapshots(
                    filters={
                        "volume_id": volume_id,
                        "status": "available",
                        "metadata": {
                            application_settings.get_alias(
                                "snapsentry-managed"
                            ): "true",
                            application_settings.get_alias(
                                "snapshot-frequency-type"
                            ): frequency,
                        },
                    }
                )
            )
            self.logger.info(
                "Successfully fetched managed snapshots for the volume",
                volume_id=volume_id,
                snapshot_count=len(snapshots),
                status="success",
            )
            return snapshots
        except Exception as e:
            self.logger.error(
                "Failed to get managed snapshots for the volume",
                volume_id=volume_id,
                status="failed",
                reason=str(e),
            )
            return []

    @staticmethod
    def _parse_snapshot_time(created_at: str) -> ZonedDateTime:
        """Parse snapshot creation time to ZonedDateTime in UTC."""
        dt = datetime.fromisoformat(created_at)
        return PlainDateTime.from_py_datetime(dt).assume_tz("UTC")

    def _snapshot_exists_in_window(
        self, volume_id: str, frequency: str, schedule: SnapshotSchedule
    ) -> bool:
        managed_snapshots = self._get_existing_managed_snapshots(
            volume_id=volume_id, frequency=frequency
        )

        if not managed_snapshots:
            return False

        window_start: ZonedDateTime = schedule.scheduled_time_utc  # pyright: ignore[reportAssignmentType]
        window_end_map = {
            "daily": window_start.add(days=1),
            "weekly": window_start.add(days=7),
            "monthly": window_start.add(months=1),
        }
        window_end: Optional[ZonedDateTime] = window_end_map[frequency]

        for snapshot in managed_snapshots:
            snapshot_time = self._parse_snapshot_time(snapshot.created_at)

            # Check if snapshot falls within window (inclusive on both ends)
            if window_start <= snapshot_time <= window_end:
                self.logger.info(
                    "Found an existing snapshot in current snapshot window",
                    volume_id=volume_id,
                    snapshot_id=snapshot.id,
                    snapshot_date=snapshot.created_at,
                    window_start=window_start,
                    window_end=window_end,
                )
                return True
            else:
                self.logger.info(
                    "Snapshot outside current window",
                    snapshot_id=snapshot.id,
                    snapshot_created_at=snapshot_time,
                    window_start=window_start,
                    window_end=window_end,
                )

        return False

    def should_create_snapshot(
        self, volume: OpenstackVolume, frequency: str
    ) -> tuple[bool, Optional[SnapshotSchedule]]:
        policy = self._get_policy(frequency=frequency, volume=volume)

        ## 1. Checks if the policy is enabled
        if not policy or not policy.is_enabled:
            self.logger.info(
                "Snapshot policy is disabled",
                volume_id=volume.id,
                status="disabled",
                frequency=frequency,
            )
            return False, None

        self.logger.info(
            "Snapshot policy is enabled",
            volume_id=volume.id,
            status="enabled",
            frequency=frequency,
        )

        ## 2. Check if the policy is due
        schedule: SnapshotSchedule = policy.get_schedule()
        if not schedule.is_due:
            self.logger.info(
                "Snapshot is not due as per schedule",
                volume_id=volume.id,
                frequency=frequency,
                status="skipped",
                reason=schedule.reason,
                due_utc=schedule.scheduled_time_utc,
                due_zoned=schedule.scheduled_time_local,
            )
            return False, None

        self.logger.info(
            "Snapshot is due as per schedule",
            volume_id=volume.id,
            frequency=frequency,
            status="due",
            reason=schedule.reason,
            due_utc=schedule.scheduled_time_utc,
            due_zoned=schedule.scheduled_time_local,
        )

        if self._snapshot_exists_in_window(
            volume_id=volume.id, frequency=frequency, schedule=schedule
        ):
            self.logger.info(
                "Snapshot already exists in window",
                volume_id=volume.id,
                frequency=frequency,
                status="skipped",
            )
            return False, None

        return True, schedule

    def should_expire_snapshot(self, snapshot: Snapshot, frequency: str) -> bool:
        metadata = SnapshotMetadata(**snapshot.metadata)
        return metadata.is_expired()


class SnapshotManager:
    def __init__(self, connection: Connection):
        self.connection = connection
        self.logger: structlog.BoundLogger = structlog.get_logger(__name__).bind(
            project_id=connection.current_project_id
        )

    @staticmethod
    def _generate_snapshot_name(
        volume_id: str, frequency: str, schedule: SnapshotSchedule
    ) -> str:
        timestamp = schedule.scheduled_time_local.format_iso()
        return f"managed-{frequency}-{volume_id}-{timestamp}"

    @staticmethod
    def _generate_metadata(
        frequency: str, schedule: SnapshotSchedule, retention_days: int
    ) -> dict:
        expiry_zoned: str = schedule.scheduled_time_local.add(
            days=retention_days
        ).format_iso()
        expiry_utc: str = (
            schedule.scheduled_time_utc.add(days=retention_days)
            .to_instant()
            .format_iso()
        )

        metadata = SnapshotMetadata(
            is_managed="true",
            retention_days=str(retention_days),
            retention_expiry_time=expiry_utc,
            retention_expiry_time_zoned=expiry_zoned,
            retention_type="time",
            frequency_type=frequency,
        )

        return metadata.model_dump(by_alias=True)

    def _clean_up_snapshot(self, snapshot_id: str, timeout: int = 60) -> None:
        try:
            self.logger.debug(
                "Cleaning up snapshot", snapshot_id=snapshot_id, status="started"
            )

            self.connection.delete_volume_snapshot(
                name_or_id=snapshot_id, wait=True, timeout=timeout
            )
            self.logger.info(
                "Snapshot cleanup completed", snapshot_id=snapshot_id, timeout=timeout
            )
        except Exception as e:
            self.logger.error(
                "Snapshot cleanup failed", snapshot_id=snapshot_id, timeout=timeout
            )

    def _inject_metadata(
        self, snapshot_id: str, volume_id: str, metadata: dict
    ) -> None:
        try:
            self.logger.debug(
                "Attempting to inject snapshot metadata for subscription",
                snapshot_id=snapshot_id,
                volume_id=volume_id,
            )
            self.connection.block_storage.set_snapshot_metadata(
                snapshot=snapshot_id, **metadata
            )
            self.logger.info(
                "Snapshot metadata injected",
                volume_id=volume_id,
                snapshot_id=snapshot_id,
                status="success",
            )
        except Exception as e:
            self.logger.error(
                "Snapshot metadata injection failed",
                volume_id=volume_id,
                snapshot_id=snapshot_id,
                status="failed",
                reason=str(e),
            )
            raise

    def _create_snapshot(
        self, volume_id: str, name: str, frequency: str, force: bool = True
    ) -> Snapshot:
        try:
            self.logger.debug(
                "Attempting to create snapshot",
                volume_id=volume_id,
                frequency=frequency,
                snapshot_name=name,
            )
            snapshot = self.connection.create_volume_snapshot(
                volume_id=volume_id,
                force=force,
                name=name,
                timeout=60,
                wait=True,
                description=f"Created and managed by {application_settings.organization} SnapSentry",
            )
            self.logger.info(
                "Snapshot created successfully",
                volume_id=volume_id,
                snapshot_id=snapshot.id,
                frequency=frequency,
                status="success",
            )

            return snapshot
        except Exception as e:
            self.logger.error(
                "Snapshot creation failed",
                volume_id=volume_id,
                frequency=frequency,
                status="failed",
                reason=str(e),
            )
            raise

    def create_snapshot_with_metadata(
        self,
        volume_id: str,
        frequency: str,
        schedule: SnapshotSchedule,
        retention_days: int,
    ) -> Snapshot:
        name: str = self._generate_snapshot_name(
            volume_id=volume_id, frequency=frequency, schedule=schedule
        )
        metadata: dict = self._generate_metadata(
            frequency=frequency, schedule=schedule, retention_days=retention_days
        )

        ## Create the snapshot
        snapshot = self._create_snapshot(
            volume_id=volume_id, name=name, frequency=frequency, force=True
        )
        try:
            self._inject_metadata(
                volume_id=volume_id, snapshot_id=snapshot.id, metadata=metadata
            )
        except Exception as e:
            self.logger.error(
                "Metadata injection failed, rolling back",
                snapshot_id=snapshot.id,
                volume_id=volume_id,
                reason=str(e),
            )
            self._clean_up_snapshot(snapshot.id)
            raise SnapshotCreationError(
                f"Failed to inject metadata for snapshot {snapshot.id}: {e}"
            ) from e

        return snapshot


class SnapshotRepository:
    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.logger: structlog.BoundLogger = structlog.get_logger(__name__).bind(
            project_id=connection.current_project_id
        )

    def get_managed_snapshots(self) -> List[Snapshot]:
        self.logger.debug("Attempting to get all the volumes in project")

        try:
            snapshots: List[Snapshot] = list(
                self.connection.list_volume_snapshots(
                    detailed=True,
                    filters={
                        "metadata": {
                            application_settings.get_alias("snapsentry-managed"): "true"
                        }
                    },
                )
            )
            self.logger.info(
                "Fetched snapshots in project successfully",
                status="success",
                count=len(snapshots),
            )
            return snapshots
        except Exception as e:
            self.logger.error(
                "Failed to fetch snapshots in project", status="failed", reason=str(e)
            )
            raise
