"""Root conftest: puts the handler dir on sys.path so `import tools` works, and
ensures OWM_API_KEY exists for import-time (offline tests stub the HTTP layer).
"""

import os

os.environ.setdefault("OWM_API_KEY", "test-key")
os.environ.setdefault("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("TTS_LAMBDA_NAME", "tts-handler-test")
