"""Interactive CLI for testing the Weather Buddy agent locally.

Type a question, get the text answer printed, and (unless --no-audio) the spoken
MP3 saved to an output folder. Runs the real /query handler pipeline (language
detection, translation, agent, TTS), with TTS done locally via the tts-handler
code instead of invoking a deployed Lambda. Conversation history is kept across
turns so follow-up questions work.

Usage (from lambdas/agent-handler, using its venv):
    .venv/Scripts/python cli.py                 # full pipeline, saves audio
    .venv/Scripts/python cli.py --no-audio      # text only
    .venv/Scripts/python cli.py --out some/dir  # choose audio output folder

Config is read from the repo-root .env (OWM_API_KEY, LLM_MODEL_ID, LLM_BASE_URL,
LLM_API_KEY, plus AWS creds for Comprehend/Translate/Polly).
Commands inside the CLI: 'exit'/'quit' to leave, 'reset' to clear history.
"""

import argparse
import base64
import importlib.util
import json
import os
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parents[1]
_TTS_HANDLER_PATH = _HERE.parent / "tts-handler" / "handler.py"


def _load_tts_module():
    spec = importlib.util.spec_from_file_location("tts_handler_cli", _TTS_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summarize_weather(data):
    if not data:
        return ""
    parts = []
    if data.get("temp") is not None:
        parts.append(f"{data['temp']}°")
    if data.get("description"):
        parts.append(data["description"])
    if data.get("location"):
        parts.append(f"@ {data['location']}")
    return "  [" + ", ".join(parts) + "]" if parts else ""


def main():
    parser = argparse.ArgumentParser(description="Weather Buddy test CLI")
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "cli_audio"),
        help="folder to save MP3 replies (default: <repo>/cli_audio)",
    )
    parser.add_argument("--no-audio", action="store_true", help="skip TTS/audio")
    args = parser.parse_args()

    # Windows consoles default to cp1252, which can't encode characters the model
    # or non-English replies emit; force UTF-8 so printing never crashes.
    for stream in (sys.stdout, sys.stdin):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    load_dotenv(find_dotenv(usecwd=False))
    if not os.environ.get("OWM_API_KEY"):
        sys.exit("OWM_API_KEY is not set (add it to the repo-root .env).")
    # handler reads this at import; TTS is routed locally below, so any value works.
    os.environ.setdefault("TTS_LAMBDA_NAME", "local-cli-tts")
    os.environ.setdefault("AWS_REGION", "us-east-1")

    import handler

    if not args.no_audio:
        tts = _load_tts_module()
        handler._synthesize = lambda text, lang: tts.handler(
            {"text": text, "lang": lang}
        ).get("audio_b64", "")
    else:
        handler._synthesize = lambda text, lang: ""

    out_dir = Path(args.out)
    if not args.no_audio:
        out_dir.mkdir(parents=True, exist_ok=True)

    model_id = os.environ.get("LLM_MODEL_ID", "?")
    print(f"Weather Buddy CLI  |  model={model_id}  |  audio={'off' if args.no_audio else out_dir}")
    print("Type a question, or 'reset' to clear history, 'exit' to quit.\n")

    messages = []
    turn = 0
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            continue
        if text.lower() in {"exit", "quit"}:
            break
        if text.lower() == "reset":
            messages = []
            print("(history cleared)\n")
            continue

        event = {"body": json.dumps({"text": text, "lang": "en", "messages": messages})}
        result = handler.handler(event)
        body = json.loads(result["body"])

        if result["statusCode"] != 200:
            print(f"[error {result['statusCode']}] {body.get('error')}\n")
            continue

        turn += 1
        messages = body.get("messages", messages)
        print(f"bot [{body.get('lang')}]> {body.get('response_text')}"
              f"{_summarize_weather(body.get('weather_data'))}")

        audio_b64 = body.get("audio_b64")
        if not args.no_audio and audio_b64:
            path = out_dir / f"turn_{turn:03d}_{body.get('lang', 'xx')}.mp3"
            path.write_bytes(base64.b64decode(audio_b64))
            print(f"     audio -> {path}")
        print()

    print("bye.")


if __name__ == "__main__":
    main()
