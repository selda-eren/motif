"""Structured-output clients.

`MetaModelClient` calls Meta Model API's OpenAI-compatible Chat Completions endpoint
(POST {base}/chat/completions, Bearer auth) with `response_format: {"type": "json_schema"}`,
as documented at https://dev.meta.ai/docs/structured-output. Every completed call is cached
in SQLite, keyed by a hash of the full request, so re-running never pays twice. Every call's
token usage and cost is logged, and a local budget stops requests before they could exceed it.

`FixtureClient` replays a hand-authored demo file for offline testing. Its output is
labelled as such everywhere it surfaces; it is never presented as model output.
"""
from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from typing import Callable, Protocol

import httpx

from .config import Settings
from .store import Store
from .usage import BudgetExceeded, Usage, cost_usd, prices_for, worst_case_usd

__all__ = ["BudgetExceeded", "FixtureClient", "LLMError", "MetaModelClient"]


class LLMError(RuntimeError):
    pass


class StructuredClient(Protocol):
    provenance: str  # stored with the book: e.g. "model" or "demo-fixture"
    model: str | None

    def complete(self, *, task: str, key: str, system: str, user: str,
                 schema_name: str, schema: dict) -> dict: ...


class MetaModelClient:
    """Calls Meta Model API. Every call is logged with token usage and cost in `store.usage_log`.

    Order of operations per call: cache lookup (free) -> budget check against the worst-case
    cost -> one HTTP request (more only if MOTIF_MAX_ATTEMPTS > 1, and only for 429/5xx/network
    errors) -> log usage -> validate -> cache.
    """
    provenance = "model"

    def __init__(self, settings: Settings, store: Store, http: httpx.Client | None = None,
                 run_id: str | None = None, log: Callable[[str], None] = lambda _: None):
        if not settings.api_key:
            raise LLMError("MODEL_API_KEY is not set. Put it in .env or the environment, or use --offline.")
        prices_for(settings.model)  # refuse unknown models before spending anything
        self.settings = settings
        self.model = settings.model
        self.store = store
        self.http = http or httpx.Client(timeout=settings.timeout_s)
        self.run_id = run_id or time.strftime("%Y%m%d-%H%M%S")
        self.log = log

    def _body(self, system: str, user: str, schema_name: str, schema: dict) -> dict:
        return {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": schema_name, "schema": schema}},
            "reasoning_effort": self.settings.reasoning_effort,
            "max_completion_tokens": self.settings.max_completion_tokens,
        }

    def _record(self, task: str, key: str, status: str, usage: Usage | None = None, cost: float = 0.0,
                latency: float = 0.0, finish_reason: str | None = None, detail: str | None = None) -> None:
        u = usage or Usage(0, 0, 0, 0)
        self.store.log_usage(
            ts=time.time(), run_id=self.run_id, task=task, key=key, model=self.model,
            reasoning_effort=self.settings.reasoning_effort, status=status,
            prompt_tokens=u.prompt_tokens, cached_tokens=u.cached_tokens,
            completion_tokens=u.completion_tokens, reasoning_tokens=u.reasoning_tokens,
            cost_usd=cost, latency_s=round(latency, 2), finish_reason=finish_reason, detail=detail)
        if status != "cache_hit":
            self.log(f"  {task}/{key}: {status}  in={u.prompt_tokens} (cached {u.cached_tokens}) "
                     f"out={u.completion_tokens} (reasoning {u.reasoning_tokens})  ${cost:.4f}  {latency:.1f}s")

    def complete(self, *, task: str, key: str, system: str, user: str,
                 schema_name: str, schema: dict) -> dict:
        body = self._body(system, user, schema_name, schema)
        cache_key = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
        if (hit := self.store.cache_get(cache_key)) is not None:
            self._record(task, key, "cache_hit")
            return hit

        spent = self.store.total_spend_usd()
        estimate = worst_case_usd(self.model, len(json.dumps(body)), self.settings.max_completion_tokens)
        # Calls that timed out may still have been billed: count what they could have cost at most.
        exposure = self.store.uncertain_exposure_usd()
        if spent + exposure + estimate > self.settings.budget_usd:
            self._record(task, key, "blocked_budget", detail=f"spent={spent:.4f} uncertain={exposure:.4f} worst_case={estimate:.4f}")
            raise BudgetExceeded(
                f"Budget stop before {task}/{key}: spent ${spent:.4f} + uncertain ${exposure:.4f} + worst case ${estimate:.4f} "
                f"> budget ${self.settings.budget_usd:.2f} (MOTIF_BUDGET_USD).")

        started = time.monotonic()
        data = self._post(task, key, body)
        latency = time.monotonic() - started
        usage = Usage.from_response(data)
        cost = cost_usd(self.model, usage)
        choice = (data.get("choices") or [{}])[0]
        finish = choice.get("finish_reason")
        try:
            parsed = json.loads(choice["message"]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            self._record(task, key, "invalid_output", usage, cost, latency, finish, str(data)[:500])
            hint = " (hit max_completion_tokens; raise MOTIF_MAX_COMPLETION_TOKENS)" if finish == "length" else ""
            raise LLMError(f"Unparseable output for {task}/{key}{hint}: {str(choice)[:300]}") from exc
        self._record(task, key, "ok", usage, cost, latency, finish)
        self.store.cache_put(cache_key, self.model, task, body, parsed)
        return parsed

    def _exposure(self, body: dict) -> float:
        return worst_case_usd(self.model, len(json.dumps(body)), self.settings.max_completion_tokens)

    def _post(self, task: str, key: str, body: dict) -> dict:
        url = f"{self.settings.api_base}/chat/completions"
        headers = {"Authorization": f"Bearer {self.settings.api_key}", "Content-Type": "application/json"}
        attempts = max(1, self.settings.max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                resp = self.http.post(url, json=body, headers=headers)
            except httpx.TransportError as exc:
                self._record(task, key, "network_error", detail=f"{str(exc)[:250]} | billing_uncertain worst_case_usd={self._exposure(body):.4f}")
                if attempt == attempts:
                    raise LLMError(f"Network error calling {url}: {exc}") from exc
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 200:
                return resp.json()
            uncertain = f" | billing_uncertain worst_case_usd={self._exposure(body):.4f}" if resp.status_code >= 500 else ""
            self._record(task, key, f"http_{resp.status_code}", detail=resp.text[:250] + uncertain)
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < attempts:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                time.sleep(delay + random.random())
                continue
            raise LLMError(f"HTTP {resp.status_code} from {url}: {resp.text[:800]}")
        raise LLMError("Exhausted attempts")


class FixtureClient:
    """Replays hand-authored responses from data/demo/<book>.fixture.json (offline demo mode)."""
    provenance = "demo-fixture"
    model = None

    def __init__(self, fixture_path: Path):
        self.path = fixture_path
        self.data = json.loads(fixture_path.read_text())

    def complete(self, *, task: str, key: str, system: str, user: str,
                 schema_name: str, schema: dict) -> dict:
        try:
            return self.data[task][key]
        except KeyError as exc:
            raise LLMError(f"Demo fixture {self.path.name} has no entry for {task}/{key}") from exc
