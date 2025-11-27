import os
import re
from typing import List, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class EmailAlert(BaseModel):
    to: List[EmailStr] = Field(
        default_factory=lambda: [
            email.strip()
            for email in os.environ.get("SNAPSENTRY_ALERT_EMAIL_TO", "").split(",")
            if email.strip()
        ],
        description="Comma separated emails when passed from environment variables",
    )
    cc: List[EmailStr] = Field(
        default_factory=lambda: [
            email.strip()
            for email in os.environ.get("SNAPSENTRY_ALERT_EMAIL_CC", "").split(",")
            if email.strip()
        ],
        description="Comma separated emails when passed from environment variables",
    )
    bcc: List[EmailStr] = Field(
        default_factory=lambda: [
            email.strip()
            for email in os.environ.get("SNAPSENTRY_ALERT_EMAIL_BCC", "").split(",")
            if email.strip()
        ],
        description="Comma separated emails when passed from environment variables",
    )
    from_override: EmailStr = Field(
        default_factory=lambda: f"snapsentry@{os.environ.get('SNAPSENTRY_ORGANIZATION', 'snapsentry')}.com",
        description="From email address, uses organization name from environment",
    )


class Alert(BaseModel):
    enabled: bool = Field(default=False)
    type: str | Literal["email"] = Field(
        default=os.environ.get("SNAPSENTRY_ALERT_TYPE", "email"),
    )
    email: EmailAlert = Field(default=EmailAlert())


## Yet to implement config file method
class Settings(BaseModel):
    organization: str = Field(
        default=os.environ.get("SNAPSENTRY_ORGANIZATION", "snapsentry"),
        description="Organization name on the metadata. Ideal of whitelabeling",
    )
    log_level: Literal["INFO", "ERROR", "DEBUG"] = Field(
        default="INFO",
        description="Log level for the application",
    )
    alerts: Alert = Field(default=Alert())

    def get_alias(self, key: str) -> str:
        return f"x-{self.organization}-{key}"


application_settings = Settings()
