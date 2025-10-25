from pydantic import BaseModel, ConfigDict


class OpenstackBaseModel(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )
