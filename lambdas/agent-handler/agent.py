"""Strands agent setup for Weather Buddy.

The Bedrock model client is built once at module level (rule 4). A fresh Agent is
created per request, seeded with the frontend-owned conversation history, so the
updated history can be read back out and returned (rules 15-16).
"""

import os
import asyncio

from strands import Agent
from strands.models import BedrockModel

try:
    from strands.middlewares import RetryMiddleware
    RETRY_MW = RetryMiddleware(exponential_backoff=True)
except ImportError:
    try:
        from strands._middleware.retry import RetryMiddleware
        RETRY_MW = RetryMiddleware(exponential_backoff=True)
    except ImportError:
        RETRY_MW = None

from prompts import ANALYST_PROMPT, ROUTER_PROMPT
from tools import build_tools

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
# Provider is Bedrock by default (the pinned production path). Set MODEL_PROVIDER=groq
# to run the same agent/tools against Groq's OpenAI-compatible API for local testing.
_cached_model = None

class _ModelProxy:
    """Wraps the underlying model to strip reasoningContent dynamically during multi-turn chat."""
    def __init__(self, model):
        self._model = model

    def __getattr__(self, name):
        return getattr(self._model, name)

    def _clean_messages(self, kwargs, args):
        messages = kwargs.get("messages")
        if messages is None and len(args) > 0:
            messages = args[0]
            args = list(args)
            
        if messages:
            def _deep_clean(d):
                if isinstance(d, dict):
                    return {k: _deep_clean(v) for k, v in d.items() if k not in ("reasoningContent", "reasoning_content")}
                elif isinstance(d, list):
                    return [_deep_clean(v) for v in d if not (isinstance(v, dict) and v.get("type") in ("reasoningContent", "reasoning_content"))]
                return d
                
            safe_messages = []
            for msg in messages:
                if isinstance(msg, dict):
                    safe_messages.append(_deep_clean(msg))
                else:
                    if hasattr(msg, "reasoningContent"):
                        try: delattr(msg, "reasoningContent")
                        except Exception: msg.reasoningContent = None
                    if hasattr(msg, "reasoning_content"):
                        try: delattr(msg, "reasoning_content")
                        except Exception: msg.reasoning_content = None
                        
                    for field_set in ("model_fields_set", "__fields_set__", "__pydantic_fields_set__"):
                        if hasattr(msg, field_set):
                            fs = getattr(msg, field_set)
                            if isinstance(fs, set):
                                fs.discard("reasoningContent")
                                fs.discard("reasoning_content")
                        
                    for attr in ("model_extra", "__pydantic_extra__", "additional_kwargs", "kwargs"):
                        if hasattr(msg, attr) and isinstance(getattr(msg, attr), dict):
                            getattr(msg, attr).pop("reasoningContent", None)
                            getattr(msg, attr).pop("reasoning_content", None)
                        
                    if hasattr(msg, "content") and isinstance(msg.content, list):
                        new_content = []
                        for b in msg.content:
                            if isinstance(b, dict):
                                if b.get("type") not in ("reasoning_content", "reasoningContent"):
                                    new_content.append(b)
                            else:
                                b_type = getattr(b, "type", getattr(b, "type_", None))
                                if b_type not in ("reasoning_content", "reasoningContent"):
                                    new_content.append(b)
                        msg.content = new_content
                    safe_messages.append(msg)
            
            if "messages" in kwargs:
                kwargs["messages"] = safe_messages
            else:
                args[0] = safe_messages

        return args, kwargs

    def _clean_response(self, response):
        """Strip <think> blocks and reasoning fields from the model's response."""
        import re
        if not response: return response
        
        msg = getattr(response, "message", response)
        
        if isinstance(msg, dict):
            msg.pop("reasoningContent", None)
            msg.pop("reasoning_content", None)
        else:
            if hasattr(msg, "reasoningContent"):
                try: delattr(msg, "reasoningContent")
                except Exception: msg.reasoningContent = None
            if hasattr(msg, "reasoning_content"):
                try: delattr(msg, "reasoning_content")
                except Exception: msg.reasoning_content = None
                
            for field_set in ("model_fields_set", "__fields_set__", "__pydantic_fields_set__"):
                if hasattr(msg, field_set):
                    fs = getattr(msg, field_set)
                    if isinstance(fs, set):
                        fs.discard("reasoningContent")
                        fs.discard("reasoning_content")
                
            for attr in ("model_extra", "__pydantic_extra__", "additional_kwargs", "kwargs"):
                if hasattr(msg, attr) and isinstance(getattr(msg, attr), dict):
                    getattr(msg, attr).pop("reasoningContent", None)
                    getattr(msg, attr).pop("reasoning_content", None)
        
        if hasattr(msg, "content"):
            if isinstance(msg.content, str):
                msg.content = re.sub(r'<think>.*?</think>', '', msg.content, flags=re.DOTALL).strip()
            elif isinstance(msg.content, list):
                for b in msg.content:
                    if isinstance(b, dict) and b.get("type") == "text" and "text" in b:
                        b["text"] = re.sub(r'<think>.*?</think>', '', b["text"], flags=re.DOTALL).strip()
        elif isinstance(msg, dict) and "content" in msg:
            if isinstance(msg["content"], str):
                msg["content"] = re.sub(r'<think>.*?</think>', '', msg["content"], flags=re.DOTALL).strip()
            elif isinstance(msg["content"], list):
                for b in msg["content"]:
                    if isinstance(b, dict) and b.get("type") == "text" and "text" in b:
                        b["text"] = re.sub(r'<think>.*?</think>', '', b["text"], flags=re.DOTALL).strip()
        return response

    async def invoke(self, *args, **kwargs):
        args, kwargs = self._clean_messages(kwargs, args)
        res = await self._model.invoke(*args, **kwargs)
        return self._clean_response(res)

    async def invoke_async(self, *args, **kwargs):
        args, kwargs = self._clean_messages(kwargs, args)
        res = await self._model.invoke_async(*args, **kwargs)
        return self._clean_response(res)

    async def invoke_stream(self, *args, **kwargs):
        args, kwargs = self._clean_messages(kwargs, args)
        # Streams are harder to intercept cleanly without breaking the async generator.
        # But usually strands uses invoke_async for tool calling.
        return await self._model.invoke_stream(*args, **kwargs)

    async def __call__(self, *args, **kwargs):
        args, kwargs = self._clean_messages(kwargs, args)
        res = await self._model(*args, **kwargs)
        return self._clean_response(res)


def _build_model():
    """Construct the LLM model object for the configured provider.

    Only this object differs between providers; the agent loop and tools are
    identical either way.
    """
    provider = os.environ.get("MODEL_PROVIDER", "bedrock").lower()
    if provider == "groq":
        from strands.models.openai import OpenAIModel

        return OpenAIModel(
            client_args={
                "api_key": os.environ["GROQ_API_KEY"],
                "base_url": "https://api.groq.com/openai/v1",
            },
            model_id=os.environ.get("GROQ_MODEL_ID", "llama-3.3-70b-versatile"),
            max_tokens=32768
        )
    return BedrockModel(
        region_name=AWS_REGION, model_id=os.environ["BEDROCK_MODEL_ID"],
        max_tokens=32768
    )


def get_model():
    """Construct or return the LLM model object for the configured provider."""
    global _cached_model
    if _cached_model is None:
        _cached_model = _ModelProxy(_build_model())
    return _cached_model


def _extract_text(message):
    """Concatenate the text blocks of a Bedrock Converse message."""
    if not message:
        return ""
    parts = [
        block["text"]
        for block in message.get("content", [])
        if isinstance(block, dict) and "text" in block
    ]
    return " ".join(p.strip() for p in parts if p and p.strip()).strip()


def _iter_tool_results(messages):
    """Yield tool-result payloads (dicts) from a Converse-format message list."""
    for message in messages or []:
        for block in message.get("content", []) if isinstance(message, dict) else []:
            if not isinstance(block, dict):
                continue
            tool_result = block.get("toolResult")
            if not tool_result:
                continue
            for item in tool_result.get("content", []):
                if isinstance(item, dict):
                    if isinstance(item.get("json"), dict):
                        yield item["json"]
                    elif isinstance(item.get("text"), str):
                        try:
                            import json

                            parsed = json.loads(item["text"])
                            if isinstance(parsed, dict):
                                yield parsed
                        except (ValueError, TypeError):
                            continue


def latest_weather_data(messages):
    """Return the most recent current-weather dict from tool results, or {}.

    Used to populate the API response's `weather_data` so the frontend WeatherCard
    can render. Matches get_current_weather output (and the nested weather that
    activity_advisor returns).
    """
    found = {}
    for payload in _iter_tool_results(messages):
        if {"temp", "humidity", "description"} <= payload.keys():
            found = payload
        elif isinstance(payload.get("weather"), dict) and {
            "temp",
            "humidity",
        } <= payload["weather"].keys():
            found = payload["weather"]
    return found


def latest_forecast_data(messages):
    """Return the most recent forecast dict from tool results, or {}.
    
    Used to populate the API response's `forecast_data` so the frontend can 
    render the 5-day forecast and hourly timeline without parsing chat messages.
    """
    found = {}
    for payload in _iter_tool_results(messages):
        if "days" in payload.keys():
            found = payload
    return found


def run_agent(text, messages=None, user_lang="en", context_location=None, user_lat=None, user_lon=None, local_time=None):
    """Run one turn against English `text`, returning (ui_payload, updated_messages).

    The ui_payload contains: ui_mode, short_answer, comparison_data.
    """
    prompt = ANALYST_PROMPT
    prompt += f"\n\nIMPORTANT INSTRUCTION: You must ALWAYS respond in the language corresponding to the ISO-639-1 code '{user_lang}'. When calling tools, you MUST pass the parameter lang='{user_lang}' so the data is translated natively."
    
    if local_time:
        prompt += f"\n\nTime Context: The user's current local time is {local_time}. When the user says 'tonight', 'tomorrow', 'this weekend', etc., you MUST use this local time to calculate precise unix timestamps and pass them to the get_hourly_window tool."
        
    if user_lat and user_lon:
        prompt += f"\n\nLocation Context: The user is currently located at coordinates ({user_lat}, {user_lon}). When the user mentions ambiguous locations like 'Springfield', use the resolve_location tool which will automatically disambiguate based on proximity. If the tool resolves ambiguity, you must briefly state your reasoning (e.g. 'I am going with Springfield, Illinois because it is 20km away from you.')."
        
    if context_location:
        prompt += f"\n\nContext: The user is currently viewing the dashboard for {context_location}. If they ask a question without specifying a location, assume they mean {context_location}."
        
    tools = build_tools(user_lat, user_lon, local_time)
        
    # Ignore historical messages to force single-turn conversations
    safe_messages = []

    agent_kwargs = {
        "model": get_model(),
        "tools": tools,
        "system_prompt": prompt,
        "messages": safe_messages,
        "callback_handler": None,
    }
    if RETRY_MW:
        agent_kwargs["middlewares"] = [RETRY_MW]

    # Step 1: Analyst Agent
    analyst_agent = Agent(**agent_kwargs)
    try:
        result = analyst_agent(text)
        last_msg = result.message
    except Exception as e:
        err_str = str(e).lower()
        if type(e).__name__ == "MaxTokensReachedException" or "maximum token limit" in err_str:
            last_msg = analyst_agent.messages[-1] if analyst_agent.messages else None
        elif "rate limit" in err_str or "429" in err_str:
            return {
                "ui_mode": "dashboard",
                "short_answer": "I'm currently receiving too many requests. Please wait a few seconds and try again!",
                "comparison_data": None
            }, analyst_agent.messages
        else:
            raise
    analyst_response = _extract_text(last_msg)
    updated_messages = analyst_agent.messages
    
    # Step 2: UI Router Agent
    import json
    router_prompt = ROUTER_PROMPT
    router_kwargs = {
        "model": get_model(),
        "system_prompt": router_prompt,
    }
    if RETRY_MW:
        router_kwargs["middlewares"] = [RETRY_MW]
    router_agent = Agent(**router_kwargs)
    routing_input = f"User Query: {text}\n\nAnalyst Response:\n{analyst_response}"
    try:
        router_result = router_agent(routing_input)
        router_text = _extract_text(router_result.message)
    except Exception as e:
        err_str = str(e).lower()
        if type(e).__name__ == "MaxTokensReachedException" or "maximum token limit" in err_str:
            router_text = _extract_text(router_agent.messages[-1] if router_agent.messages else None)
        elif "rate limit" in err_str or "429" in err_str:
            # If router gets rate limited, fall back to dashboard layout since we already have analyst's response
            router_text = "{}"
        else:
            raise
    
    # Parse JSON from Router
    import re
    try:
        # Robustly extract JSON object from the response
        match = re.search(r'\{.*\}', router_text, re.DOTALL)
        if match:
            json_str = match.group(0)
            ui_payload = json.loads(json_str)
        else:
            raise ValueError("No JSON object found in router response")
    except Exception as e:
        print(f"Failed to parse Router JSON: {e}\nRouter output was: {router_text}")
        # Fallback to dashboard mode
        ui_payload = {
            "ui_mode": "dashboard",
            "short_answer": "I have analyzed the weather for your activity, but had trouble formatting the display. The conditions are generally covered in my analysis.",
            "comparison_data": None
        }

    return ui_payload, updated_messages
