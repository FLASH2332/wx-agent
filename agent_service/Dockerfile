# Weather Buddy agent. Build from the REPO ROOT:
#   docker build -f agent_service/Dockerfile -t weatherbuddy-agent .
# The LLM is NOT in this image: it is reached over an API (LLM_MODEL_ID / LLM_BASE_URL / LLM_API_KEY).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    TTS_CACHE_DIR=/tmp/tts

WORKDIR /app

# Dependencies first so code-only changes reuse the cached layer.
COPY agent_service/requirements.txt agent_service/requirements-server.txt agent_service/
RUN pip install -r agent_service/requirements-server.txt

COPY agent_service/ agent_service/
RUN rm -rf agent_service/tests \
    && useradd --system --uid 10001 --no-create-home app \
    && chown -R app /app
USER app

EXPOSE 8080

# Same probe the ALB target group uses.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8080'), timeout=4)" || exit 1

CMD ["python", "-m", "agent_service"]
