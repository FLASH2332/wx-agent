"""Root conftest: makes `import tools`/`import agent` work and loads test config.

Real secrets for live tests come from the repo-root .env (loaded here once via
python-dotenv, so individual tests never resolve paths to it). The setdefault
lines below are fallbacks so offline tests run even without a .env.
"""

import os

from dotenv import find_dotenv, load_dotenv

# Load the repo-root .env if present (does not override already-set env vars).
load_dotenv(find_dotenv(usecwd=False))

os.environ.setdefault("OWM_API_KEY", "test-key")
os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("TTS_LAMBDA_NAME", "tts-handler-test")
