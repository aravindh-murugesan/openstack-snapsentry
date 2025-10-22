from pydantic import BaseModel, Field
from typing import Literal
import os
from pathlib import Path


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

    def get_alias(self, key: str) -> str:
        return f"x-{self.organization}-{key}"


application_settings = Settings()
