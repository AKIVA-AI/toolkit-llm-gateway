from typing import Optional

from pydantic import BaseModel

from .arize import Protocol


class ArizePhoenixConfig(BaseModel):
    otlp_auth_headers: Optional[str] = None
    protocol: Protocol
    endpoint: str
    project_name: Optional[str] = None
