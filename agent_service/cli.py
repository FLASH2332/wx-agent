"""Interactive CLI for the agent without the frontend.

    python -m agent_service.cli            # chat; history kept across turns
    python -m agent_service.cli --lang fr  # answer in French
Commands: 'reset' clears history, 'exit' quits.
"""

from __future__ import annotations

import argparse
import logging

from . import service
from .config import get_settings, load_dotenv_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Weather Buddy CLI")
    parser.add_argument("--lang", default="en")
    args = parser.parse_args()
    load_dotenv_file()
    logging.basicConfig(level=logging.WARNING)
    settings = get_settings()
    messages: list = []
    print(f"Weather Buddy CLI (model={settings.llm_model_id}). 'reset' clears history, 'exit' quits.")
    while True:
        try:
            text = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text in {"exit", "quit"}:
            break
        if text == "reset":
            messages = []
            print("(history cleared)")
            continue
        if not text:
            continue
        status, body = service.handle_query({"text": text, "lang": args.lang, "messages": messages}, settings)
        if status != 200:
            print(f"[{status}] {body.get('error')}")
            continue
        messages = body["messages"]
        print(f"\nbuddy> {body['response_text']}\n[ui_mode={body['ui_mode']} tools={body['meta']['tools']}]")


if __name__ == "__main__":
    main()
