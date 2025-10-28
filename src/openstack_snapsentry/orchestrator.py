from typing import List

import structlog
from openstack.block_storage.v3.snapshot import Snapshot

from src.openstack_snapsentry.connection import OpenstackConnectionManager
from src.openstack_snapsentry.models.metadata import (
    OpenstackVolume,
    VolumeSubscriptionInfo,
    SnapshotMetadata,
)
from src.openstack_snapsentry.snapshot import (
    SnapshotCreationError,
    SnapshotFrequency,
    SnapshotManager,
    SnapshotRepository,
    SnapshotScheduler,
)
from src.openstack_snapsentry.volume import VolumeRepository


class SnapSentryOrchestrator:
    def __init__(self, cloud_name: str, timeout: int, max_retries: int = 3) -> None:
        self.cloud_name = cloud_name
        self.logger = structlog.get_logger(__name__).bind(cloud=cloud_name)

        self.connection_manager = OpenstackConnectionManager(
            cloud_name, timeout, max_retries
        )
        connection = self.connection_manager.connection
        self.logger = structlog.get_logger(__name__).bind(
            cloud=cloud_name, project_id=connection.current_project_id
        )
        self.volume_repo = VolumeRepository(connection)
        self.snapshot_repo: SnapshotRepository = SnapshotRepository(
            connection=connection
        )
        self.scheduler = SnapshotScheduler(connection)
        self.snapshot_manager = SnapshotManager(connection)

        self.logger.info(
            "Snapshot orchestrator initialized",
            project_id=connection.current_project_id,
            user_id=connection.current_user_id,
        )

    def _create_snapshot_if_due(self, volume: OpenstackVolume, frequency: str):
        should_create, schedule = self.scheduler.should_create_snapshot(
            volume, frequency
        )
        if not should_create or not schedule:
            return False

        policy = self.scheduler._get_policy(volume, frequency)
        if not policy:
            self.logger.warning(
                "Policy not found despite passing validation",
                volume_id=volume.id,
                frequency=frequency,
            )
            return False

        # Create the snapshot
        self.snapshot_manager.create_snapshot_with_metadata(
            volume_id=volume.id,
            frequency=frequency,
            schedule=schedule,
            retention_days=policy.retention_days,
        )

        return True

    def modify_snapsentry_subscription(
        self, volume_id: str, subscription: VolumeSubscriptionInfo
    ) -> None:
        if not subscription.is_enabled:
            self.logger.info(
                "Subscription disabled, skipping",
                volume_id=volume_id,
            )
            return

        metadata = subscription.to_openstack_metadata()

        try:
            self.volume_repo.update_subscription_info(volume_id, metadata)
            self.logger.info(
                "Volume subscribed to snapshot management",
                volume_id=volume_id,
                status="success",
            )
        except Exception as e:
            self.logger.error(
                "Failed to subscribe volume",
                volume_id=volume_id,
                status="failed",
                reason=str(e),
            )
            raise

    def get_subscribed_volumes(self) -> List[OpenstackVolume]:
        return self.volume_repo.get_volumes_with_snapshot_subscription()

    def get_managed_snapshot(self) -> List[Snapshot]:
        return self.snapshot_repo.get_managed_snapshots()

    def process_snapshot_expiry(self, snapshot: Snapshot):
        metadata: SnapshotMetadata = SnapshotMetadata(**snapshot.metadata)
        if not metadata.is_expired():
            self.logger.info(
                "Snapshot is in active retention period",
                snapshot_id=snapshot.id,
                expiry_date=metadata.retention_expiry_time,
                frequency=metadata.frequency_type,
                volume_id=snapshot.volume_id,
            )
            return

        self.logger.info(
            "Snapshot has reached expiry date",
            snapshot_id=snapshot.id,
            frequency=metadata.frequency_type,
            volume_id=snapshot.volume_id,
            expiry_date=metadata.retention_expiry_time,
        )

        try:
            self.snapshot_manager._clean_up_snapshot(snapshot_id=snapshot.id)
            self.logger.info(
                "Snapshot expired successfully",
                status="success",
                snapshot_id=snapshot.id,
                volume_id=snapshot.volume_id,
                frequency=metadata.frequency_type,
                expiry_date=metadata.retention_expiry_time,
            )
        except Exception as e:
            self.logger.error(
                "Snapshot expiration failed",
                status="failed",
                volume_id=snapshot.volume_id,
                snapshot_id=snapshot.id,
                expiry_date=metadata.retention_expiry_time,
                frequency=metadata.frequency_type,
                reason=str(e),
            )
            raise

    def process_volume_snapshots(self, volume: OpenstackVolume):
        self.logger.info(
            "Processing volume snapshots",
            volume_id=volume.id,
            status="started",
        )

        success_count = 0
        skip_count = 0
        error_count = 0

        for frequency in SnapshotFrequency.all():
            try:
                if self._create_snapshot_if_due(volume, frequency):
                    success_count += 1
                else:
                    skip_count += 1
            except SnapshotCreationError as e:
                error_count += 1
                self.logger.error(
                    "Snapshot creation failed",
                    volume_id=volume.id,
                    frequency=frequency,
                    reason=str(e),
                )
        self.logger.info(
            "Volume snapshot processing completed",
            volume_id=volume.id,
            status="completed",
            created=success_count,
            skipped=skip_count,
            errors=error_count,
        )

    def run_snapshot_workflow(self):
        try:
            volumes = self.get_subscribed_volumes()

            if not volumes:
                self.logger.info("No volumes with active subscriptions found")
                return

            self.logger.info(
                "Processing subscribed volumes",
                total_volumes=len(volumes),
            )

            for volume in volumes:
                try:
                    self.process_volume_snapshots(volume)
                except Exception as e:
                    self.logger.error(
                        "Failed to process volume",
                        volume_id=volume.id,
                        reason=str(e),
                    )

            self.logger.info("Snapshot workflow completed")
        except Exception as e:
            self.logger.error(
                "Snapshot workflow failed",
                reason=str(e),
            )
            raise

    def run_expiry_workflow(self):
        try:
            snapshots: List[Snapshot] = self.snapshot_repo.get_managed_snapshots()

            if not snapshots:
                self.logger.info("No managed snapshots found")
                return

            self.logger.info(
                "Processing managed snapshots for expiry",
                total_snapshots=len(snapshots),
            )

            for snapshot in snapshots:
                try:
                    self.process_snapshot_expiry(snapshot=snapshot)
                except Exception as e:
                    self.logger.error(
                        "Failed to process snapshot",
                        snapshot_id=snapshot.id,
                        reason=str(e),
                    )
        except Exception as e:
            self.logger.error("Snapshot Reaper workflow failed", reason=str(e))
            raise
