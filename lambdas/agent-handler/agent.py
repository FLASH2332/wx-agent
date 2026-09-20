"""Strands agent setup for Weather Buddy.

The LLM is reached through LiteLLM, configured entirely from env vars so the
provider/model can be swapped without code changes — just change the three env
vars below. LiteLLM routes by the model-id prefix, for example:
  - openai/<model>  + LLM_BASE_URL  -> a self-hosted OpenAI-compatible endpoint
                                        (Ollama on EC2), LLM_API_KEY="ollama"
  - groq/<model>                    -> Groq (LLM_BASE_URL left empty)
  - anthropic/<model>, bedrock/<model>, gpt-4o, ...

The model is built lazily and cached; a fresh Agent is created per request,
seeded with the frontend-owned conversation history (rules 15-16).
"""

import os

from strands import Agent
from strands.models.litellm import LiteLLMModel

from prompts import SYSTEM_PROMPT
from tools import (
    activity_advisor,
    get_alerts,
    get_current_weather,
    get_forecast,
)

_cached_model = None

TOOLS = [get_current_weather, get_forecast, get_alerts, activity_advisor]


def _build_model():
    """Construct the LiteLLM model from env. Only this object differs between
    providers; the agent loop and tools are identical either way."""
    client_args = {}
    api_key = os.environ.get("LLM_API_KEY", "")
    base_url = os.environ.get("LLM_BASE_URL", "")
    if api_key:
        client_args["api_key"] = api_key
    if base_url:
        client_args["api_base"] = base_url
    return LiteLLMModel(client_args=client_args, model_id=os.environ["LLM_MODEL_ID"])


def get_model():
    """Construct or return the cached LLM model object."""
    global _cached_model
    if _cached_model is None:
        _cached_model = _build_model()
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


def run_agent(text, messages=None, user_lang="en", context_location=None):
    """Run one turn against English `text`, returning (response_text, updated_messages).

    `messages` is the Bedrock Converse-format history owned by the frontend. The
    returned history includes the new user turn and assistant turn(s).
    """
    prompt = SYSTEM_PROMPT
    prompt += f"\n\nIMPORTANT INSTRUCTION: You must ALWAYS respond in the language corresponding to the ISO-639-1 code '{user_lang}'. When calling tools, you MUST pass the parameter lang='{user_lang}' so the data is translated natively."
    if context_location:
        prompt += f"\n\nContext: The user is currently viewing the dashboard for {context_location}. If they ask a question without specifying a location, assume they mean {context_location}."
        
    agent = Agent(
        model=get_model(),
        tools=TOOLS,
        system_prompt=prompt,
        messages=list(messages or []),
        callback_handler=None,
    )
    result = agent(text)
    return _extract_text(result.message), agent.messages
