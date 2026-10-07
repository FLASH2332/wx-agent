"""Ordered provider fallback with a short cooldown for failing providers.

Cost/latency decision: a provider that just failed (e.g. Transcribe timing out) is
skipped for PROVIDER_COOLDOWN_SECONDS instead of making every request wait for it
again. `ProviderUnavailable` (not configured / unsupported language) skips with no
cooldown. A `ServiceError` raised by a provider is a client error and is not retried.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Sequence

from ..errors import AllProvidersFailed, ProviderUnavailable, ServiceError

logger = logging.getLogger(__name__)


class ProviderChain:
    def __init__(self, kind: str, providers: Sequence, cooldown_seconds: int = 60,
                 clock: Callable[[], float] = time.monotonic):
        self.kind = kind
        self._providers = list(providers)
        self._cooldown = cooldown_seconds
        self._clock = clock
        self._cool_until: dict[str, float] = {}

    @property
    def names(self) -> list[str]:
        return [p.name for p in self._providers]

    def run(self, call: Callable):
        """Call `call(provider)` on each provider in order; return (result, provider_name)."""
        errors: list[tuple[str, str]] = []
        now = self._clock()
        candidates = [p for p in self._providers if self._cool_until.get(p.name, 0) <= now]
        for provider in candidates or self._providers:
            try:
                return call(provider), provider.name
            except ProviderUnavailable as exc:
                errors.append((provider.name, f"unavailable: {exc}"))
            except ServiceError:
                raise
            except Exception as exc:  # noqa: BLE001 - any provider failure falls through
                logger.warning("%s provider %s failed: %s: %s", self.kind, provider.name, type(exc).__name__, str(exc)[:200])
                self._cool_until[provider.name] = now + self._cooldown
                errors.append((provider.name, f"{type(exc).__name__}: {str(exc)[:200]}"))
        raise AllProvidersFailed(self.kind, errors)
