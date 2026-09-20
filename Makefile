.PHONY: build validate deploy deploy-guided test

# Build both Lambdas via the makefile method (uv installs deps).
build:
	sam build

# Lint/validate the SAM template.
validate:
	sam validate --lint

# First-time interactive deploy.
deploy-guided: build
	sam deploy --guided

# Subsequent deploys (uses saved samconfig.toml).
deploy: build
	sam deploy

# Run the offline unit tests for both Lambdas.
test:
	cd lambdas/agent-handler && .venv/Scripts/python -m pytest -q
	cd lambdas/tts-handler && .venv/Scripts/python -m pytest -q
