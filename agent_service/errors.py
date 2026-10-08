"""Exception types shared across the service."""

from __future__ import annotations


class ServiceError(Exception):
    """An error with a client-facing HTTP status and a safe message."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ConfigError(Exception):
    """Required configuration is missing or invalid."""


class LocationNotFoundError(Exception):
    """The weather geocoder returned no match for a location."""


class UpstreamError(Exception):
    """A third-party HTTP API (e.g. OpenWeatherMap) failed or is unreachable."""


class ProviderUnavailable(Exception):
    """A provider cannot handle this request (not configured, unsupported language...).

    Expected and cheap: the chain moves to the next provider without a cooldown.
    """


class AllProvidersFailed(Exception):
    def __init__(self, kind: str, errors: list[tuple[str, str]]):
        super().__init__(f"all {kind} providers failed")
        self.kind = kind
        self.errors = errors
