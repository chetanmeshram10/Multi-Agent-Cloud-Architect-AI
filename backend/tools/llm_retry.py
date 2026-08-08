"""
Retry helper for two distinct transient Groq failure modes:

1. Rate limits (HTTP 429/413, tokens-per-minute) — Groq's lower tiers cap total
   tokens per minute across your whole account. A pipeline firing several LLM
   calls back-to-back (revision loop, retry loop) can bump into that ceiling
   even with conservative per-call budgets. The fix is to wait out roughly a
   full per-minute window and retry.

2. Malformed tool-call generation ("tool_use_failed" — either the model didn't
   call the tool, or it called it with JSON that doesn't parse). This is a
   one-off sampling glitch, not a quota issue — regenerating with the same
   prompt almost always succeeds, so it only needs a short retry, not a wait.

Both are transient. The wrong response is to let either one kill the whole
pipeline stage.
"""

from __future__ import annotations

import time


def _classify_error(msg: str) -> str | None:
    """Return 'rate_limit', 'malformed', or None (not retryable)."""
    lower = msg.lower()
    if "rate_limit_exceeded" in lower or "429" in msg or "413" in msg or "tokens per minute" in lower:
        return "rate_limit"
    if "tool_use_failed" in lower or "failed to parse tool call" in lower or "did not call a tool" in lower:
        return "malformed"
    return None


def invoke_with_retry(structured_llm, messages, max_attempts: int = 4, base_delay: float = 20.0):
    """Call structured_llm.invoke(messages), retrying on transient Groq failures."""
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            return structured_llm.invoke(messages)
        except Exception as exc:  # noqa: BLE001
            kind = _classify_error(str(exc))
            if kind is None or attempt == max_attempts:
                raise
            last_exc = exc
            if kind == "rate_limit":
                delay = base_delay * attempt
                print(
                    f"[RATE LIMIT] Groq rate limit hit (attempt {attempt}/{max_attempts}). "
                    f"Waiting {delay:.0f}s before retrying..."
                )
            else:
                delay = 3.0
                print(
                    f"[RETRY] Model produced a malformed tool call (attempt {attempt}/{max_attempts}). "
                    f"Regenerating in {delay:.0f}s..."
                )
            time.sleep(delay)
    raise last_exc  # pragma: no cover — unreachable, satisfies type checkers