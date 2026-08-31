"""Live provider. Off by default; reached only through an explicit --live flag.

The API key is read from the environment and is never written to a log, a
fixture, a result file or a trajectory.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from ssf_hve.providers.base import ModelResponse, Provider
from ssf_hve.replay.store import FixtureStore

API_KEY_ENV = "SSF_HVE_API_KEY"
ENDPOINT_ENV = "SSF_HVE_API_URL"
ENDPOINT_OPT_IN_ENV = "SSF_HVE_ALLOW_CUSTOM_ENDPOINT"
DEFAULT_ENDPOINT = "https://api.anthropic.com/v1/messages"


class LiveProviderUnavailable(RuntimeError):
    pass


class UnsafeEndpoint(LiveProviderUnavailable):
    """Raised for an endpoint this provider will not send an API key to."""


def resolve_endpoint(env: "dict[str, str] | None" = None) -> str:
    """Decide where the API key may be sent. Refuses rather than warns.

    The key travels in a request header, so the endpoint is a credential-
    disclosure decision, not a configuration convenience. Three rules:

    1. Unset means the default endpoint. The common path needs no decision.
    2. A custom endpoint must be HTTPS. Plain HTTP would put the key on the
       wire in clear text, and a typo in an environment variable is not a
       reason to do that.
    3. A custom endpoint must be opted into explicitly, by setting
       SSF_HVE_ALLOW_CUSTOM_ENDPOINT=1 as well. An environment variable
       picked up from a shell profile, a CI job or an inherited container
       environment should not silently redirect a key to another host.
    """
    env = os.environ if env is None else env
    raw = (env.get(ENDPOINT_ENV) or "").strip()
    if not raw:
        return DEFAULT_ENDPOINT
    if raw == DEFAULT_ENDPOINT:
        return raw
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme != "https":
        raise UnsafeEndpoint(
            f"{ENDPOINT_ENV} must use https (got {parsed.scheme or 'no scheme'!r}). "
            "The API key is sent in a request header and will not be put on a "
            "plaintext connection.")
    if not parsed.hostname:
        raise UnsafeEndpoint(f"{ENDPOINT_ENV} has no host: {raw!r}")
    if (env.get(ENDPOINT_OPT_IN_ENV) or "").strip() not in ("1", "true", "yes"):
        raise UnsafeEndpoint(
            f"{ENDPOINT_ENV} points at {parsed.hostname}, which is not the "
            f"default endpoint. Redirecting the API key to another host must be "
            f"deliberate: set {ENDPOINT_OPT_IN_ENV}=1 as well if that is what "
            "you intend.")
    return raw


class LiveProvider(Provider):
    name = "live"

    def __init__(self, model: str, store: FixtureStore | None = None,
                 max_tokens: int = 4096, temperature: float = 0.0):
        super().__init__(model)
        self.store = store or FixtureStore()
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._key = os.environ.get(API_KEY_ENV, "").strip()
        if not self._key:
            raise LiveProviderUnavailable(
                f"live mode requires {API_KEY_ENV} in the environment. "
                "Replay mode is the default and needs no key.")
        self.endpoint = resolve_endpoint()

    def complete(self, *, role: str, prompt: str) -> ModelResponse:
        body = json.dumps({
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }).encode("utf-8")
        req = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"content-type": "application/json",
                     "anthropic-version": "2023-06-01",
                     "x-api-key": self._key})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Never echo headers; they carry the key.
            raise RuntimeError(f"live provider HTTP {exc.code}") from None
        except urllib.error.URLError as exc:
            raise RuntimeError(f"live provider unreachable: {exc.reason}") from None
        parts = payload.get("content") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
        usage = payload.get("usage") or {}
        fx = self.store.record(
            role=role, model=self.model, rendered_prompt=prompt,
            response_text=text, provenance="live-api",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            note="captured via LiveProvider")
        return ModelResponse(
            text=text, model=self.model, provenance="live-api",
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"), from_fixture=False,
            fixture_key=fx.key)
