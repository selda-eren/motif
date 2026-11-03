import json
from dataclasses import replace

import httpx
import pytest

from motif.llm import BudgetExceeded, LLMError, MetaModelClient
from motif.store import Store
from motif.usage import Usage, cost_usd

USAGE = {"prompt_tokens": 2000, "completion_tokens": 3000, "total_tokens": 5000,
         "prompt_tokens_details": {"cached_tokens": 500},
         "completion_tokens_details": {"reasoning_tokens": 2400}}


def _client(settings, handler, store=None, **overrides):
    s = replace(settings, api_key="test-key", api_base="https://example.test/v1", model="muse-spark-1.3",
                reasoning_effort="medium", max_completion_tokens=12000, max_attempts=1, budget_usd=2.0)
    s = replace(s, **overrides)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    return MetaModelClient(s, store or Store(":memory:"), http=http, run_id="test-run")


def _ok(payload, usage=USAGE, finish="stop"):
    return httpx.Response(200, json={"choices": [{"finish_reason": finish, "message": {
        "role": "assistant", "content": payload if isinstance(payload, str) else json.dumps(payload)}}],
        "usage": usage})


KW = dict(task="perception", key="p0", system="sys", user="usr", schema_name="S", schema={"type": "object"})


def test_cost_uses_standard_spark_prices():
    # 1500 uncached input @ $1.25/M + 500 cached @ $0.15/M + 3000 output (incl. reasoning) @ $4.25/M
    expected = (1500 * 1.25 + 500 * 0.15 + 3000 * 4.25) / 1e6
    assert cost_usd("muse-spark-1.3", Usage.from_response({"usage": USAGE})) == pytest.approx(expected)


def test_request_shape_usage_log_and_cache(settings):
    calls = []

    def handler(request):
        calls.append(request)
        return _ok({"answer": 42})

    client = _client(settings, handler)
    assert client.complete(**KW) == {"answer": 42}
    assert client.complete(**KW) == {"answer": 42}
    assert len(calls) == 1, "second identical call must be served from cache"

    body = json.loads(calls[0].content)
    assert str(calls[0].url) == "https://example.test/v1/chat/completions"
    assert calls[0].headers["Authorization"] == "Bearer test-key"
    assert body["reasoning_effort"] == "medium"
    assert body["max_completion_tokens"] == 12000
    assert body["response_format"]["type"] == "json_schema"

    rows = client.store.usage_rows("test-run")
    assert [r["status"] for r in rows] == ["ok", "cache_hit"]
    assert (rows[0]["prompt_tokens"], rows[0]["cached_tokens"], rows[0]["completion_tokens"],
            rows[0]["reasoning_tokens"]) == (2000, 500, 3000, 2400)
    assert rows[0]["cost_usd"] > 0 and rows[1]["cost_usd"] == 0
    assert client.store.total_spend_usd() == pytest.approx(rows[0]["cost_usd"])


def test_budget_blocks_request_before_sending(settings):
    calls = []
    client = _client(settings, lambda r: calls.append(r) or _ok({}), budget_usd=0.01)
    with pytest.raises(BudgetExceeded, match="Budget stop"):
        client.complete(**KW)
    assert calls == []
    assert client.store.usage_rows()[0]["status"] == "blocked_budget"


def test_budget_counts_previous_spending(settings):
    store = Store(":memory:")
    store.log_usage(ts=0, run_id="old", task="t", key="k", model="muse-spark-1.3", status="ok", cost_usd=1.98)
    client = _client(settings, lambda r: _ok({}), store=store)
    with pytest.raises(BudgetExceeded):
        client.complete(**KW)


def test_no_automatic_retry_by_default(settings):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "1"}, json={})

    client = _client(settings, handler)
    with pytest.raises(LLMError, match="HTTP 429"):
        client.complete(**KW)
    assert len(calls) == 1
    assert client.store.usage_rows()[0]["status"] == "http_429"


def test_truncated_output_is_billed_logged_and_not_cached(settings):
    client = _client(settings, lambda r: _ok('{"units": [', finish="length"))
    with pytest.raises(LLMError, match="max_completion_tokens"):
        client.complete(**KW)
    row = client.store.usage_rows()[0]
    assert row["status"] == "invalid_output" and row["cost_usd"] > 0
    assert client.store.cache_get("anything") is None


def test_missing_key_and_unknown_model_fail_before_spending(settings):
    with pytest.raises(LLMError, match="MODEL_API_KEY"):
        MetaModelClient(replace(settings, api_key=None), Store(":memory:"))
    with pytest.raises(BudgetExceeded, match="No price known"):
        MetaModelClient(replace(settings, api_key="k", model="mystery-model"), Store(":memory:"))
