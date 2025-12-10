from notifiers import get_notifier
from src.openstack_snapsentry.models.settings import application_settings, EmailAlert
from typing import Literal, Optional
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import structlog


class EmailTemplater:
    def __init__(self):
        self.template_path = Path(__file__).parent / "templates"

    def render_single_alert(
        self,
        status: Literal["success", "failure"],
        volume_id: str,
        project_name: str,
        snapshot_frequency: str,
        operation_time: str,
        snapshot_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> str:
        template_file = "email_single_alert.html.j2"
        env = Environment(loader=FileSystemLoader(self.template_path))
        template = env.get_template(template_file)

        return template.render(
            status=status,
            volume_id=volume_id,
            project_name=project_name,
            snapshot_frequency=snapshot_frequency,
            operation_time=operation_time,
            snapshot_id=snapshot_id,
            failure_reason=failure_reason,
        )


class EmailNotification:
    def __init__(
        self,
        subject: str,
        message: str,
        is_html: bool = False,
        email: EmailAlert = application_settings.alerts.email,
    ):
        self.email = email
        self.subject = subject
        self.message = message
        self.is_html = is_html
        self.logger = structlog.get_logger(__name__).bind()

    def send(self):
        provider = get_notifier(provider_name="email")

        parameters = self.email.model_dump(by_alias=True)
        try:
            if parameters.get("cc"):
                parameters.pop("cc")
            if parameters.get("bcc"):
                parameters.pop("bcc")

            provider.notify(
                **parameters,
                raise_on_errors=True,
                subject=self.subject,
                html=self.is_html,
                message=self.message,
            )
        except Exception as e:
            self.logger.error(
                f"Failed to send email due to {e}",
                to=self.email.to,
                subject=self.subject,
            )
