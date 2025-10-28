import typer
from typing import Annotated
from src.openstack_snapsentry.orchestrator import SnapSentryOrchestrator

app = typer.Typer(
    name="CLI for Openstack Snapsentry",
    no_args_is_help=True,
    epilog="This CLI tool automates the creation and expiry of snapshots in OpenStack. "
    "Please ensure you have an external scheduler configured to run snapsentry",
)


@app.command(
    name="create-volume-snapshots",
    short_help="Creates Snapshot for volumes with snapsentry subscription metadata. Scoped to a project",
)
def create_volume_snapshots(
    cloud_name: Annotated[
        str,
        typer.Option(
            metavar="cloud-name", help="Name of cloud as in openstack's cloud.yaml file"
        ),
    ],
    timeout: int = 10,
):
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
            metavar="cloud-name", help="Name of cloud as in openstack's cloud.yaml file"
        ),
    ],
    timeout: int = 10,
):
    """
    Expires volume snapshots based on expiry configuration.

    Deletes expired snapshots based on the snapshot expiry configuration defined in snapsentry metadata.
    The expiry is scoped to a project level.
    """

    orchestrator = SnapSentryOrchestrator(cloud_name=cloud_name, timeout=timeout)
    orchestrator.run_expiry_workflow()
