import typer
from typing import Annotated, Optional, Literal
from src.openstack_snapsentry.orchestrator import SnapSentryOrchestrator
from src.openstack_snapsentry.models.metadata import VolumeSubscriptionInfo
from src.openstack_snapsentry.models.frequency import (
    DailySnapshotSchedule,
    WeeklySnapshotSchedule,
)


class GlobalState:
    cloud_name: Optional[str] = None
    timeout: int = 10


global_state = GlobalState()


app = typer.Typer(
    name="CLI for Openstack Snapsentry",
    no_args_is_help=True,
    epilog="This CLI tool automates the creation and expiry of snapshots in OpenStack. "
    "Please ensure you have an external scheduler configured to run snapsentry",
)


subscribe = typer.Typer(no_args_is_help=True)
app.add_typer(subscribe, name="create-snapshot-subscription", no_args_is_help=True)


@subscribe.command(
    name="daily", help="Configures a daily snapshot policy for the volume"
)
def daily_subscription(
    cloud_name: Annotated[
        str,
        typer.Option(
            "--cloud-name",
            metavar="cloud-name",
            help="Name of cloud as in openstack's cloud.yaml file",
        ),
    ],
    volume_id: Annotated[
        str,
        typer.Option(
            metavar="volume-id", help="OpenStack volume ID to configure snapshots for"
        ),
    ],
    start_time: Annotated[
        str,
        typer.Option(
            metavar="start-time", help="Time for the snapshot to trigger (HH:MM format)"
        ),
    ],
    enabled: Annotated[
        bool,
        typer.Option(
            "--enabled/--disabled", help="Enable or disable daily snapshot workflow"
        ),
    ] = True,
    timezone: Annotated[
        str,
        typer.Option(
            metavar="timezone",
            help="Timezone for snapshot schedule (TZ identifier, e.g., Asia/Kolkata)",
        ),
    ] = "UTC",
    retention_type: Annotated[
        str,
        typer.Option(metavar="retention-type", help="How expiry is handled"),
    ] = "time",
    retention_days: Annotated[
        int,
        typer.Option(
            metavar="retention-days", help="Number of days to store snapshots"
        ),
    ] = 7,
    timeout: int = typer.Option(10, "--timeout", help="Operation timeout in seconds"),
) -> None:
    """
    Configure daily snapshot policy for an OpenStack volume.

    This command sets up automated daily snapshots with customizable timing,
    retention, and timezone handling.
    """
    typer.echo(
        f"Configuring daily snapshots for volume {volume_id} on cloud {cloud_name}..."
    )
    orchestrator = SnapSentryOrchestrator(cloud_name=cloud_name, timeout=timeout)

    subscription_info = VolumeSubscriptionInfo(
        is_enabled=True,
        snapshot_policy_daily=DailySnapshotSchedule(
            is_enabled=enabled,
            start_time=start_time,
            retention_days=retention_days,
            timezone=timezone,
        ),
    )

    daily_subscription_info = subscription_info.to_openstack_metadata()

    orchestrator.volume_repo.update_subscription_info(
        volume_id=volume_id, metadata=daily_subscription_info
    )


@subscribe.command(
    name="weekly", help="Configures a weekly snapshot policy for the volume"
)
def weekly_subscription(
    cloud_name: Annotated[
        str,
        typer.Option(
            "--cloud-name",
            metavar="cloud-name",
            help="Name of cloud as in openstack's cloud.yaml file",
        ),
    ],
    volume_id: Annotated[
        str,
        typer.Option(
            metavar="volume-id", help="OpenStack volume ID to configure snapshots for"
        ),
    ],
    start_time: Annotated[
        str,
        typer.Option(
            metavar="start-time", help="Time for the snapshot to trigger (HH:MM format)"
        ),
    ],
    enabled: Annotated[
        bool,
        typer.Option(
            "--enabled/--disabled", help="Enable or disable daily snapshot workflow"
        ),
    ] = True,
    timezone: Annotated[
        str,
        typer.Option(
            metavar="timezone",
            help="Timezone for snapshot schedule (TZ identifier, e.g., Asia/Kolkata)",
        ),
    ] = "UTC",
    start_day: Annotated[
        Literal[
            "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"
        ],
        typer.Option(metavar="start-day", help="How expiry is handled"),
    ] = "sunday",
    retention_type: Annotated[
        str,
        typer.Option(metavar="retention-type", help="How expiry is handled"),
    ] = "time",
    retention_days: Annotated[
        int,
        typer.Option(
            metavar="retention-days", help="Number of days to store snapshots"
        ),
    ] = 30,
    timeout: int = typer.Option(10, "--timeout", help="Operation timeout in seconds"),
) -> None:
    """
    Configure daily snapshot policy for an OpenStack volume.

    This command sets up automated daily snapshots with customizable timing,
    retention, and timezone handling.
    """
    typer.echo(
        f"Configuring daily snapshots for volume {volume_id} on cloud {cloud_name}..."
    )
    orchestrator = SnapSentryOrchestrator(cloud_name=cloud_name, timeout=timeout)

    subscription_info = VolumeSubscriptionInfo(
        is_enabled=True,
        snapshot_policy_weekly=WeeklySnapshotSchedule(
            is_enabled=enabled,
            start_time=start_time,
            retention_days=retention_days,
            timezone=timezone,
            start_day=start_day,
        ),
    )

    week_subscription_info = subscription_info.to_openstack_metadata()

    orchestrator.volume_repo.update_subscription_info(
        volume_id=volume_id, metadata=week_subscription_info
    )


@app.command(
    name="create-volume-snapshots",
    short_help="Creates Snapshot for volumes with snapsentry subscription metadata. Scoped to a project",
)
def create_volume_snapshots(
    cloud_name: Annotated[
        str,
        typer.Option(
            "--cloud-name",
            metavar="cloud-name",
            help="Name of cloud as in openstack's cloud.yaml file",
        ),
    ],
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Operation timeout in seconds"),
    ] = 10,
) -> None:
    """
    Creates volume snapshots for a specified cloud environment.

    Only manages the volumes with snapsentry metadata with information regarding snapsentry subcription info.
    Volume scans are scoped to a project level.
    """
    orchestrator = SnapSentryOrchestrator(cloud_name=cloud_name, timeout=timeout)
    orchestrator.run_snapshot_workflow()


@app.command(
    name="expire-volume-snapshots",
    short_help="Expires volume snapshots based on expiry configuration. Scoped to project level",
)
def expire_volume_snapshots(
    cloud_name: Annotated[
        str,
        typer.Option(
            "--cloud-name",
            metavar="cloud-name",
            help="Name of cloud as in openstack's cloud.yaml file",
        ),
    ],
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Operation timeout in seconds"),
    ] = 10,
) -> None:
    """
    Expires volume snapshots based on expiry configuration.

    Deletes expired snapshots based on the snapshot expiry configuration defined in snapsentry metadata.
    The expiry is scoped to a project level.
    """
    orchestrator = SnapSentryOrchestrator(cloud_name=cloud_name, timeout=timeout)
    orchestrator.run_expiry_workflow()


if __name__ == "__main__":
    app()
