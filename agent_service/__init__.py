"""Weather Buddy agent service.

Self-contained and framework-agnostic: nothing in here imports Lambda, API Gateway
or a web framework, except `agent_service.api` (Starlette) which is the only HTTP
entrypoint. The same code runs from the Lambda adapter, the local server, or a
container (later: a Dockerfile in this directory).
"""

import os

# LiteLLM calls load_dotenv() itself on import unless LITELLM_MODE is not "DEV". That second, uncontrolled
# loader re-injected stale AWS keys from .env over AWS_PROFILE. config.load_dotenv_file() is the only loader.
os.environ.setdefault("LITELLM_MODE", "PRODUCTION")
