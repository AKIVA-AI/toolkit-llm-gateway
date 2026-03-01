from litellm.llms.custom_llm import CustomLLM
from typing_extensions import TypedDict


class CustomLLMItem(TypedDict):
    provider: str
    custom_handler: CustomLLM
