"""Claude implementation of LLMProvider (structured outputs via messages.parse)."""

import logging

import anthropic
from pydantic import ValidationError

from makan.config import Settings
from makan.llm.base import LLMError, T

log = logging.getLogger(__name__)

MAX_TOKENS = 4000
TIMEOUT_S = 60.0  # first use of a new schema adds compile time (cached 24h)
# Effort per job (default "low"). Haiku 5.5 rejects non-default temperature, so more
# thinking is the lever for steadier verdicts on the safety-critical check.
JOB_EFFORT = {"check_safety": "medium"}


class AnthropicProvider:
    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None) -> None:
        key = settings.anthropic_api_key.get_secret_value() or None
        self.client = client or anthropic.AsyncAnthropic(
            api_key=key, timeout=TIMEOUT_S, max_retries=2
        )
        self.model = settings.llm_model

    async def structured(self, *, job: str, system: str, user: str, schema: type[T]) -> T:
        last_error: Exception | None = None
        for attempt in (1, 2):  # retry once on invalid output (P3-T9)
            try:
                return await self._once(job=job, system=system, user=user, schema=schema)
            except (ValidationError, LLMError) as e:
                last_error = e
                log.warning("llm job=%s attempt=%d failed: %s", job, attempt, e)
        raise LLMError(f"{job}: no valid answer after retry ({last_error})") from last_error

    async def _once(self, *, job: str, system: str, user: str, schema: type[T]) -> T:
        response = await self.client.messages.parse(
            model=self.model,
            max_tokens=MAX_TOKENS,
            # Stable per-job system prompt first, marked for caching.
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
            output_config={"effort": JOB_EFFORT.get(job, "low")},
            output_format=schema,
        )
        log.info(
            "llm job=%s model=%s in=%s out=%s cache_read=%s request_id=%s",
            job,
            self.model,
            response.usage.input_tokens,
            response.usage.output_tokens,
            response.usage.cache_read_input_tokens,
            response._request_id,
        )
        if response.stop_reason == "refusal":
            category = response.stop_details.category if response.stop_details else None
            raise LLMError(f"{job}: model refused (category={category})")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"{job}: output truncated at max_tokens")
        if response.parsed_output is None:
            raise LLMError(f"{job}: no structured output returned")
        return response.parsed_output
