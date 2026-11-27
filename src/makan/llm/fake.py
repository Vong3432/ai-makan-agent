"""Test double for LLMProvider: canned responses keyed by job name."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from makan.llm.base import LLMError, T

Responder = BaseModel | dict[str, Any] | Callable[[str], BaseModel | dict[str, Any]]


@dataclass
class Call:
    job: str
    system: str
    user: str


@dataclass
class FakeLLM:
    """`responses[job]` is a model/dict, or a callable taking the user prompt."""

    responses: dict[str, Responder] = field(default_factory=dict)
    calls: list[Call] = field(default_factory=list)

    async def structured(self, *, job: str, system: str, user: str, schema: type[T]) -> T:
        self.calls.append(Call(job, system, user))
        if job not in self.responses:
            raise LLMError(f"FakeLLM has no response for job {job!r}")
        r = self.responses[job]
        if callable(r) and not isinstance(r, BaseModel):
            r = r(user)
        if isinstance(r, BaseModel):
            r = r.model_dump()
        return schema.model_validate(r)
