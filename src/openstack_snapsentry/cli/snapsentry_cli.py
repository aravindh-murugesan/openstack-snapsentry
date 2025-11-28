import logging
import typer
import structlog
from typing import Annotated, Optional, Literal
from src.openstack_snapsentry.orchestrator import SnapSentryOrchestrator
from src.openstack_snapsentry.models.metadata import VolumeSubscriptionInfo
from src.openstack_snapsentry.models.frequency import (
    DailySnapshotSchedule,
    WeeklySnapshotSchedule,
    MonthlySnapshotSchedule,
)


def configure_logging(
    format: Literal["console", "keyvalue"] = "console",
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO",
):
    """Configure structlog with specified format."""

    # Choose renderer based on format
    if format == "console":
        renderer = structlog.dev.ConsoleRenderer(colors=True)
    else:
        renderer = structlog.processors.KeyValueRenderer(
            sort_keys=True,
            drop_missing=True,
            key_order=[
                "timestamp",
                "level",
                "module",
                "func_name",
                "event",
                "frequency",
                "status",
                "cloud",
                "project_id",
                "volume_id",
                "volume_count",
                "snapshot_id",
                "snapshot_count",
                "count",
                "due_utc",
                "due_zoned",
            ],
        )

    structlog.configure(
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
        cache_logger_on_first_use=True,
        context_class=dict,
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.MODULE,
                ]
            ),
            renderer,
        ],
    )


class GlobalState:
    cloud_name: Optional[str] = None
    timeout: int = 10
    log_format: Literal["console", "keyvalue"] = "console"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


global_state = GlobalState()


def global_callback(
    cloud_name: Annotated[
        str,
        typer.Option(
            "--cloud-name",
            metavar="cloud-name",
            help="Name of cloud as in openstack's cloud.yaml file",
        ),
    ],
    log_format: Annotated[
        Literal["console", "keyvalue"],
        typer.Option(
            "--log-format",
            help="Log output format (console for human-readable, keyvalue for structured logs)",
            show_default=True,
            envvar="SNAPSENTRY_LOG_FORMAT",
        ),
    ] = "console",
    log_level: Annotated[
        Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        typer.Option(
            default="--log-level",
            show_default=True,
            envvar="SNAPSENTRY_LOG_FORMAT",
        ),
    ] = "INFO",
):
    """Global options that apply to all commands."""
    global_state.cloud_name = cloud_name
    global_state.log_format = log_format
    configure_logging(format=log_format, log_level=log_level)


app = typer.Typer(
    name="CLI for Openstack Snapsentry",
    no_args_is_help=True,
    callback=global_callback,
    epilog="This CLI tool automates the creation and expiry of snapshots in OpenStack. "
    "Please ensure you have an external scheduler configured to run snapsentry",
)


subscribe = typer.Typer(no_args_is_help=True)
app.add_typer(subscribe, name="create-snapshot-subscription", no_args_is_help=True)


@subscribe.command(
    name="daily", help="Configures a daily snapshot policy for the volume"
)
def daily_subscription(
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
        f"Configuring daily snapshots for volume {volume_id} on cloud {global_state.cloud_name}..."
    )
    orchestrator = SnapSentryOrchestrator(
        cloud_name=global_state.cloud_name, timeout=timeout
    )

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
            "--enabled/--disabled", help="Enable or disable weekly snapshot workflow"
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
        typer.Option(metavar="start-day", help="Day of week to start snapshots"),
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
    Configure weekly snapshot policy for an OpenStack volume.

    This command sets up automated weekly snapshots with customizable timing,
    retention, and timezone handling.
    """
    typer.echo(
        f"Configuring weekly snapshots for volume {volume_id} on cloud {global_state.cloud_name}..."
    )
    orchestrator = SnapSentryOrchestrator(
        cloud_name=global_state.cloud_name, timeout=timeout
    )

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


@subscribe.command(
    "monthly", help="Configures a monthly snapshot policy for the volume"
)
def monthly_subscription(
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
            "--enabled/--disabled", help="Enable or disable weekly snapshot workflow"
        ),
    ] = True,
    timezone: Annotated[
        str,
        typer.Option(
            metavar="timezone",
            help="Timezone for snapshot schedule (TZ identifier, e.g., Asia/Kolkata)",
        ),
    ] = "UTC",
    start_date: Annotated[
        int,
        typer.Option(
            metavar="start-day", help="Day of week to start snapshots", min=1, max=31
        ),
    ] = 1,
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
    Configure monthly snapshot policy for an OpenStack volume.

    This command sets up automated monthly snapshots with customizable timing,
    retention, and timezone handling.
    """
    typer.echo(
        f"Configuring weekly snapshots for volume {volume_id} on cloud {global_state.cloud_name}..."
    )
    orchestrator = SnapSentryOrchestrator(
        cloud_name=global_state.cloud_name, timeout=timeout
    )

    subscription_info = VolumeSubscriptionInfo(
        is_enabled=True,
        snapshot_policy_monthly=MonthlySnapshotSchedule(
            is_enabled=enabled,
            start_time=start_time,
            retention_days=retention_days,
            timezone=timezone,
            start_date=start_date,
        ),
    )

    monthly_subscription_info = subscription_info.to_openstack_metadata()

    orchestrator.volume_repo.update_subscription_info(
        volume_id=volume_id, metadata=monthly_subscription_info
    )


@app.command(
    name="create-volume-snapshots",
    short_help="Creates Snapshot for volumes with snapsentry subscription metadata. Scoped to a project",
)
def create_volume_snapshots(
    timeout: Annotated[
        int,
        typer.Option("--timeout", help="Operation timeout in seconds"),
    ] = 10,
) -> None:
    """
    Creates volume snapshots for a specified cloud environment.

    Only manages the volumes with snapsentry metadata with information regarding snapsentry subscription info.
    Volume scans are scoped to a project level.
    """
    orchestrator = SnapSentryOrchestrator(
        cloud_name=global_state.cloud_name, timeout=timeout
    )
    orchestrator.run_snapshot_workflow()


@app.command(
    name="expire-volume-snapshots",
    short_help="Expires volume snapshots based on expiry configuration. Scoped to project level",
)
def expire_volume_snapshots(
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
    orchestrator = SnapSentryOrchestrator(
        cloud_name=global_state.cloud_name, timeout=timeout
    )
    orchestrator.run_expiry_workflow()


if __name__ == "__main__":
    app()
