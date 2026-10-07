.PHONY: build validate deploy deploy-guided test run docker-run deploy-check deploy-container

# Build the Lambdas via the makefile method (uv installs deps).
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

# Offline unit tests (no network, no AWS, no LLM keys needed).
test:
	python -m pytest -q agent_service/tests

# Local API server on http://127.0.0.1:3001
run:
	python -m agent_service

# Container image (agent_service/Dockerfile) and AWS deployment (docs/05-container-deploy.md)
docker-run:
	docker compose up --build

ENV ?= lab-new
deploy-check:
	python scripts/deploy.py check $(ENV)

deploy-container:
	python scripts/deploy.py deploy $(ENV)
