"""Direct (non-agent) LLM calls through LiteLLM: router step and LLM translation.

Provider-agnostic: only LLM_MODEL_ID / LLM_BASE_URL / LLM_API_KEY decide the backend.
"""

from __future__ import annotations

from .config import Settings
from .textutil import strip_think


def is_rate_limit(exc: BaseException) -> bool:
    """True if the exception (or anything in its cause chain) is a provider rate limit."""
    seen = 0
    while exc is not None and seen < 6:
        name = type(exc).__name__
        if name in {"RateLimitError", "ModelThrottledException"} or "429" in str(exc)[:200]:
            return True
        exc = exc.__cause__ or exc.__context__
        seen += 1
    return False


def provider_kwargs(settings: Settings, model_id: str | None = None) -> dict:
    """Connection kwargs for a model. The shared key/base URL only go to the same provider as
    LLM_MODEL_ID (a router model on another provider must not receive that key); Bedrock
    authenticates with AWS credentials and needs an explicit region (LiteLLM would guess one)."""
    model = model_id or settings.llm_model_id
    kwargs: dict = {}
    same_provider = model.split("/")[0] == settings.llm_model_id.split("/")[0]
    if model.startswith("bedrock/"):
        kwargs["aws_region_name"] = settings.aws_region
    elif same_provider:
        if settings.llm_api_key:
            kwargs["api_key"] = settings.llm_api_key
        if settings.llm_base_url:
            kwargs["api_base"] = settings.llm_base_url
    return kwargs


def completion_kwargs(settings: Settings, model_id: str | None = None) -> dict:
    kwargs = {"model": model_id or settings.llm_model_id, "num_retries": settings.llm_num_retries}
    kwargs.update(provider_kwargs(settings, model_id))
    if settings.llm_reasoning_effort:
        kwargs["reasoning_effort"] = settings.llm_reasoning_effort
    return kwargs


def complete(settings: Settings, system: str, user: str, *, max_tokens: int, json_mode: bool = False,
             model_id: str | None = None) -> str:
    import litellm

    litellm.drop_params = True  # silently drop params a provider does not support
    kwargs = completion_kwargs(settings, model_id)
    kwargs.update(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=max_tokens,
        temperature=0,
        timeout=60,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = litellm.completion(**kwargs)
    return strip_think(response.choices[0].message.content or "")
