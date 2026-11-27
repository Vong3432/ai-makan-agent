"""LLM provider interface. Every agent job asks for one validated pydantic object."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The model could not produce a usable answer (refusal, truncation, invalid output)."""


class LLMProvider(Protocol):
    async def structured(self, *, job: str, system: str, user: str, schema: type[T]) -> T:
        """Run one request and return an instance of `schema`.

        `job` names the agent job (for logging and test fakes). `system` must be stable
        across calls of the same job so it can be prompt-cached; per-request data goes
        in `user`.
        """
        ...
