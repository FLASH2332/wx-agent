"""Strands model wiring: a plain LiteLLMModel, provider chosen only by env.

The old `_ModelProxy` wrapped invoke()/__call__(), which Strands never calls (it calls
`stream()`), so none of it ever ran. It is gone. Verified against strands-agents 1.56:
the OpenAI-compatible formatter already drops `reasoningContent` from multi-turn history
(see test_stock_model_never_sends_reasoning_blocks, which will fail if that changes).
What the proxy was really missing is `<think>` text stripping; that now happens where
text is consumed (`messages.extract_text` and the router).
"""

from __future__ import annotations

from strands.models.litellm import LiteLLMModel

from ..config import Settings
from ..llm import provider_kwargs

_cached: dict[tuple, LiteLLMModel] = {}


def get_model(settings: Settings) -> LiteLLMModel:
    key = (settings.llm_model_id, settings.llm_base_url, settings.llm_api_key, settings.llm_max_tokens,
           settings.llm_num_retries, settings.llm_reasoning_effort, settings.aws_region)
    model = _cached.get(key)
    if model is None:
        import litellm

        litellm.drop_params = True  # drop request params a given provider does not support
        params = {"max_tokens": settings.llm_max_tokens, "num_retries": settings.llm_num_retries}
        if settings.llm_reasoning_effort:
            params["reasoning_effort"] = settings.llm_reasoning_effort
        model = LiteLLMModel(client_args=provider_kwargs(settings), model_id=settings.llm_model_id, params=params)
        _cached[key] = model
    return model
