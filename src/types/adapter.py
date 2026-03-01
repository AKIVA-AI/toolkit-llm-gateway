from litellm.integrations.custom_logger import CustomLogger
from typing_extensions import TypedDict


class AdapterItem(TypedDict):
    id: str
    adapter: CustomLogger
