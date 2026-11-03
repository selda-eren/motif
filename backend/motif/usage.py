"""Token accounting, cost, and a local spending budget for Meta Model API calls.

Prices are USD per 1M tokens, Standard mode, from https://dev.meta.ai/docs/pricing-rate-limits
(checked 2026-10-26). Reasoning tokens are billed as output tokens; cached prompt tokens are
billed at the cached-input rate.
"""
from __future__ import annotations

from dataclasses import dataclass

PRICES_PER_M: dict[str, dict[str, float]] = {
    "muse-spark-1.3": {"input": 1.25, "cached_input": 0.15, "output": 4.25},
    "muse-spark-1.2": {"input": 1.25, "cached_input": 0.15, "output": 4.25},
    "muse-spark-1.1": {"input": 1.25, "cached_input": 0.15, "output": 4.25},
    "muse-spark-1.3-contributor": {"input": 0.10, "cached_input": 0.002, "output": 0.20},
    "muse-spark-1.2-contributor": {"input": 0.10, "cached_input": 0.002, "output": 0.20},
    "muse-wonder-1.0": {"input": 4.00, "cached_input": 0.20, "output": 20.00},
}

# Conservative characters-per-token used only for the pre-request budget estimate.
CHARS_PER_TOKEN_ESTIMATE = 3.0


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    cached_tokens: int
    completion_tokens: int  # includes reasoning tokens
    reasoning_tokens: int

    @classmethod
    def from_response(cls, data: dict) -> "Usage":
        u = data.get("usage") or {}
        return cls(
            prompt_tokens=int(u.get("prompt_tokens") or 0),
            cached_tokens=int((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0),
            completion_tokens=int(u.get("completion_tokens") or 0),
            reasoning_tokens=int((u.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0),
        )


def prices_for(model: str) -> dict[str, float]:
    if model not in PRICES_PER_M:
        raise BudgetExceeded(f"No price known for model {model!r}; add it to motif/usage.py before spending.")
    return PRICES_PER_M[model]


def cost_usd(model: str, u: Usage) -> float:
    p = prices_for(model)
    uncached = max(0, u.prompt_tokens - u.cached_tokens)
    return (uncached * p["input"] + u.cached_tokens * p["cached_input"] + u.completion_tokens * p["output"]) / 1e6


def worst_case_usd(model: str, request_chars: int, max_completion_tokens: int) -> float:
    """Upper-bound estimate before sending: all input uncached, output at its hard cap."""
    p = prices_for(model)
    est_input = request_chars / CHARS_PER_TOKEN_ESTIMATE
    return (est_input * p["input"] + max_completion_tokens * p["output"]) / 1e6
