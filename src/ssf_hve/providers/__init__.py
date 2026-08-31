from __future__ import annotations

from ssf_hve.providers.base import ModelResponse, Provider

DEFAULT_MODEL = "claude-opus-5"


def get_provider(*, live: bool, model: str = DEFAULT_MODEL) -> Provider:
    """Replay is the default. Live is reached only by explicit request."""
    if live:
        from ssf_hve.providers.live import LiveProvider
        return LiveProvider(model)
    from ssf_hve.providers.replay import ReplayProvider
    return ReplayProvider(model)


__all__ = ["ModelResponse", "Provider", "get_provider", "DEFAULT_MODEL"]
