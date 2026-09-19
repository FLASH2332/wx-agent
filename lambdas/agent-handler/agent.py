"""Strands agent setup for Weather Buddy.

The Bedrock model client is built once at module level (rule 4). A fresh Agent is
created per request, seeded with the frontend-owned conversation history, so the
updated history can be read back out and returned (rules 15-16).
"""

import os

from strands import Agent
from strands.models import BedrockModel

from prompts import SYSTEM_PROMPT
from tools import (
    activity_advisor,
    get_alerts,
    get_current_weather,
    get_forecast,
)

BEDROCK_MODEL_ID = os.environ["BEDROCK_MODEL_ID"]
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

TOOLS = [get_current_weather, get_forecast, get_alerts, activity_advisor]

MODEL = BedrockModel(region_name=AWS_REGION, model_id=BEDROCK_MODEL_ID)


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


def run_agent(text, messages=None):
    """Run one turn against English `text`, returning (response_text, updated_messages).

    `messages` is the Bedrock Converse-format history owned by the frontend. The
    returned history includes the new user turn and assistant turn(s).
    """
    agent = Agent(
        model=MODEL,
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        messages=list(messages or []),
    )
    result = agent(text)
    return _extract_text(result.message), agent.messages
