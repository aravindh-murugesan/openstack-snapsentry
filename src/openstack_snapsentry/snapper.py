import json
from typing import List, Optional

import openstack
import structlog
from openstack.block_storage.v3.snapshot import Snapshot
from openstack.block_storage.v3.volume import Volume
from openstack.connection import Connection

from src.openstack_snapsentry.helpers.utils import connect_to_openstack
from src.openstack_snapsentry.models.settings import application_settings
from src.openstack_snapsentry.models.metadata import (
    OpenstackVolume,
    VolumeSubscriptionInfo,
)


class VolumeSnapshotFeature:
    def __init__(self, cloud_name: str):
        self.cloud_name = cloud_name
        self._connect_to_cloud()

    def _connect_to_cloud(self):
        self.connection = connect_to_openstack(cloud_name=self.cloud_name, timeout=10)
        self.logger = structlog.get_logger(__name__).bind(
            cloud=self.cloud_name,
            project_id=self.connection.current_project_id,
            user_id=self.connection.current_user_id,
        )

    def subscribe_for_snapshot(
        self, volume_id: str, subscription: VolumeSubscriptionInfo
    ) -> None:
        if not subscription.is_enabled:
            return

        openstack_metadata = subscription.to_openstack_metadata()

        try:
            self.logger.debug(
                "Subscribe volume to periodic managed snapshot",
                volume_id=volume_id,
                status="started",
            )

            self.connection.block_storage.set_volume_metadata(
                volume=volume_id,
                **openstack_metadata,
            )
            self.logger.info(
                "Subscribe volume to periodic managed snapshot",
                volume_id=volume_id,
                status="success",
            )
        except Exception as e:
            self.logger.error(
                "Subscribe volume to periodic managed snapshot",
                volume_id=volume_id,
                status="failed",
                reason=str(e),
            )

    def _project_volumes(self, retries: int = 2) -> Optional[List[Volume]]:
        self.logger.debug(
            "Fetch volumes in a project",
            status="started",
        )

        try:
            volumes: List[Volume] = self.connection.list_volumes()
            self.logger.info(
                "Fetch volumes in a project", status="success", count=len(volumes)
            )
            return volumes
        except Exception as e:
            self.logger.error(
                "Fetch volumes in a project",
                status="failed",
                reason=str(e),
            )
            if "timed out" in str(e).lower() and retries > 0:
                connect_to_openstack(cloud_name=self.cloud_name, retries=retries - 1)

            return None

    def volumes_with_snapshot_subscription(self) -> Optional[List[OpenstackVolume]]:
        volumes = self._project_volumes(retries=2)
        if not volumes:
            return

        subscribed_for_snapshot: List[OpenstackVolume] = []
        for volume in volumes:
            subscription = VolumeSubscriptionInfo(
                **volume.metadata
            ).load_fields_from_dict(volume.metadata)
            if not subscription.is_enabled:
                self.logger.debug(
                    "Volume snapshot subscription validation",
                    volume_id=volume.id,
                    status="skipped",
                    reason=f"Volume lacks subscription metadata. {subscription.model_dump_json()}",
                )
                continue

            self.logger.info(
                "Volume snapshot subscription validation",
                volume_id=volume.id,
                status="accepted",
                reason=f"Volume has subscription metadata. {subscription.model_dump_json()}",
            )

            subscribed_for_snapshot.append(
                OpenstackVolume(
                    id=volume.id,
                    name=volume.id,
                    snapshot_subscription=subscription,
                    status=volume.status,
                )
            )
        self.logger.info(
            "Volume snapshot subscription validation summary",
            status="completed",
            subscribed_for_snapshot=len(subscribed_for_snapshot),
        )
