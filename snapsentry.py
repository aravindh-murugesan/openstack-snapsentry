from src.openstack_snapsentry.cli.snapsentry_cli import app
import structlog

if __name__ == "__main__":
    structlog.configure(
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
        context_class=dict,
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.CallsiteParameterAdder(
                [
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.MODULE,
                ]
            ),
            structlog.processors.KeyValueRenderer(
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
            ),
        ],
    )
    app()
