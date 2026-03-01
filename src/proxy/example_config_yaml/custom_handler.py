import litellm
from litellm import CustomLLM
from litellm.types.utils import ModelResponse


class MyCustomLLM(CustomLLM):
    def completion(self, *args, **kwargs) -> ModelResponse:
        return litellm.completion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello world"}],
            mock_response="Hi!",
        )  # type: ignore

    async def acompletion(self, *args, **kwargs) -> litellm.ModelResponse:
        return litellm.completion(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello world"}],
            mock_response="Hi!",
        )  # type: ignore


my_custom_llm = MyCustomLLM()
