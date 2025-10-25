from typing import List

import structlog
from openstack.block_storage.v3.volume import Volume
from openstack.connection import Connection

from src.openstack_snapsentry.models.metadata import (
    OpenstackVolume,
    VolumeSubscriptionInfo,
)


class VolumeRepository:
    """
    Repository for interacting with OpenStack block storage volumes for listing,
    managing snapshot subscription metadata.

    This class is a thin wrapper around an openstacksdk Connection that provides
    convenience methods for:
    - listing all volumes in the current project,
    - discovering volumes that have a snapshot subscription encoded in their
      metadata, and
    - updating a volume's metadata to reflect snapshot subscription information.
    """

    def __init__(self, connection: Connection) -> None:
        self.connection: Connection = connection
        self.logger: structlog.BoundLogger = structlog.get_logger(__name__).bind(
            project_id=connection.current_project_id
        )

    def _parse_subscription(self, volume: Volume) -> VolumeSubscriptionInfo:
        """
        Parse subscription information from a volume's metadata.

        This method extracts subscription configuration from volume metadata and converts it
        into a VolumeSubscriptionInfo object.

        Args:
          volume (Volume): The volume object containing metadata to parse

        Returns:
          VolumeSubscriptionInfo: Object containing parsed subscription configuration.
          If no metadata exists, returns a VolumeSubscriptionInfo with is_enabled=False.
        """
        if not volume.metadata:
            return VolumeSubscriptionInfo(is_enabled=False)

        return VolumeSubscriptionInfo.load_fields_from_dict(volume.metadata)

    def get_all_volumes(self) -> List[Volume]:
        """
        Retrieves all volumes from the OpenStack project.

        Returns:
          List[Volume]: A list of Volume objects representing all volumes in the project.

        Raises:
          Exception: If there is an error fetching the volumes from OpenStack.
        """
        self.logger.debug("Attempting to get all the volumes in project")

        try:
            volumes: List[Volume] = list(self.connection.list_volumes())
            self.logger.info(
                "Fetched volumes in project successfully",
                status="success",
                count=len(volumes),
            )
            return volumes
        except Exception as e:
            self.logger.error(
                "Failed to fetch volumes in project", status="failed", reason=str(e)
            )
            raise

    def get_volumes_with_snapshot_subscription(self) -> List[OpenstackVolume]:
        """
        Filters and returns a list of OpenStack volumes that have an active snapshot subscription.

        This method scans through all available volumes and checks each for a valid snapshot
        subscription configuration. It processes the subscription metadata and constructs
        OpenStackVolume objects for volumes with enabled subscriptions.

        Returns:
          List[OpenstackVolume]: A list of OpenstackVolume objects representing volumes with
          active snapshot subscriptions. Each object contains the volume's ID, name, status
          and snapshot subscription details.

        Note:
          Volumes with invalid or failed subscription parsing are skipped and logged as errors,
          but do not interrupt the overall processing of other volumes.
        """
        self.logger.debug("Attempting to filter volumes with snapshot subscription")

        volumes: List[Volume] = self.get_all_volumes()
        subscribed_volumes: List[OpenstackVolume] = []

        for volume in volumes:
            try:
                subscription = self._parse_subscription(volume)

                if not subscription.is_enabled:
                    self.logger.debug(
                        "Volume lacks snapshot subscription",
                        volume_id=volume.id,
                        status="skipped",
                    )
                    continue

                self.logger.info(
                    "Volume has valid snapshot subscription",
                    volume_id=volume.id,
                    status="accepted",
                )

                subscribed_volumes.append(
                    OpenstackVolume(
                        id=volume.id,
                        name=volume.name,
                        snapshot_subscription=subscription,
                        status=volume.status,
                    )
                )

            except Exception as e:
                self.logger.error(
                    "Failed to parse volume subscription",
                    status="failed",
                    volume_id=volume.id,
                    reason=str(e),
                )
                continue

        self.logger.info(
            "Volume subscription scan completed",
            status="completed",
            total_volumes=len(volumes),
            subscribed_volumes=len(subscribed_volumes),
        )

        return subscribed_volumes

    def update_subscription_info(self, volume_id: str, metadata: dict):
        """Updates the metadata of a volume with snapshot subscription information.

        This method attempts to update the metadata of a specified volume with subscription
        information for snapshots.

        Args:
          volume_id (str): The unique identifier of the volume to update.
          metadata (dict): Dictionary containing the metadata key-value pairs to set on the volume.

        Raises:
          Exception: If the metadata update operation fails.
        """
        self.logger.debug(
            "Attempting to update volume metadata with snapshot subscription info",
            volume_id=volume_id,
        )
        try:
            self.connection.block_storage.set_volume_metadata(  # pyright: ignore[reportAttributeAccessIssue]
                volume=volume_id, **metadata
            )
            self.logger.info(
                "Updated volume metadata with snapshot subscription info",
                volume_id=volume_id,
                status="success",
            )
        except Exception as e:
            self.logger.error(
                "Failed to update volume metadata with snapshot subscription info",
                volume_id=volume_id,
                reason=str(e),
            )
