"""The verification loop every producer runs in (design spec section 5).

producer → code gate → verifier, at most `max_retries + 1` attempts. Gate issues go straight back
to the producer; verifier issues too. Nothing raises: an item that is still disputed at the end
comes back with `resolved=False` and its open issues.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from app.agents.factory import AgentSpec
from app.compliance.ledger import Ledger
from app.llm import AgentOutputError, BudgetExceeded, Prompt
from app.models import Issue, Review
from app.pipeline.calls import AgentCall

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class LoopSpec(Generic[T]):
    name: str
    producer: AgentSpec
    output_schema: type[T]
    build_prompt: Callable[[Any, list[Issue]], Prompt]
    gate: Callable[[Any, T], list[Issue]]
    verifier: AgentSpec | None
    build_review_prompt: Callable[[Any, T], Prompt] | None
    max_retries: int
    needs_review: Callable[[Any, T], bool] | None = None  # None = always review


@dataclass
class Attempt:
    number: int
    gate_issues: list[Issue] = field(default_factory=list)
    review_issues: list[Issue] = field(default_factory=list)
    error: str | None = None


@dataclass
class LoopResult(Generic[T]):
    output: T | None
    resolved: bool
    attempts: list[Attempt]
    open_issues: list[Issue]
    last_output: T | None = None  # the last producer output, even if it failed the gate

    def summary(self) -> dict:
        return {"resolved": self.resolved, "attempts": len(self.attempts),
                "open_issues": [i.model_dump() for i in self.open_issues]}


def _issue(type_: str, target: str, reason: str) -> Issue:
    return Issue(type=type_, target_id=target, reason=reason, evidence=[], proposed=None)


def _issues(issues: list[Issue]) -> list[dict]:
    return [i.model_dump() for i in issues]


async def run_verified(spec: LoopSpec[T], payload: Any, call: AgentCall, ledger: Ledger | None) -> LoopResult[T]:
    attempts: list[Attempt] = []
    feedback: list[Issue] = []
    best: T | None = None
    last: Any = None
    open_issues: list[Issue] = []
    resolved = False

    def record(kind: str, actor: str, output: Any, meta: dict) -> None:
        if ledger is not None:
            ledger.append(kind, actor, {"loop": spec.name}, output, meta)  # type: ignore[arg-type]

    for number in range(1, spec.max_retries + 2):
        attempt = Attempt(number=number)
        attempts.append(attempt)
        try:
            output = await call(spec.producer, spec.build_prompt(payload, feedback))
        except BudgetExceeded as exc:
            attempt.error = exc.message
            open_issues = [_issue("budget", spec.producer.name, exc.message)]
            record("gate", "gate:" + spec.name, None, {"attempt": number, "issues": _issues(open_issues)})
            break
        except AgentOutputError as exc:
            attempt.error = exc.message
            attempt.gate_issues = [_issue("schema", spec.producer.name, exc.message)]
            feedback = open_issues = attempt.gate_issues
            record("gate", "gate:" + spec.name, None, {"attempt": number, "issues": _issues(feedback)})
            continue

        last = output
        attempt.gate_issues = spec.gate(payload, output)
        record("gate", "gate:" + spec.name, None, {"attempt": number, "issues": _issues(attempt.gate_issues)})
        if attempt.gate_issues:
            feedback = open_issues = attempt.gate_issues
            continue
        best = output  # type: ignore[assignment]
        if spec.verifier is None or spec.build_review_prompt is None or (
                spec.needs_review is not None and not spec.needs_review(payload, output)):
            resolved, open_issues = True, []
            break
        try:
            review = await call(spec.verifier, spec.build_review_prompt(payload, output))
        except AgentOutputError as exc:
            open_issues = [_issue("verifier_error", spec.verifier.name, exc.message)]
            record("review", spec.verifier.name, None, {"attempt": number, "error": exc.message})
            break
        assert isinstance(review, Review)
        record("review", spec.verifier.name, review, {"attempt": number, "verdict": review.verdict})
        if review.verdict == "pass" or not review.issues:
            resolved, open_issues = True, []
            break
        attempt.review_issues = list(review.issues)
        feedback = open_issues = attempt.review_issues

    result = LoopResult(output=best, resolved=resolved, attempts=attempts, open_issues=open_issues,
                        last_output=last)
    record("loop_result", spec.name, None, result.summary())
    return result
