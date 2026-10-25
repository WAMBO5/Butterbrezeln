"""The scripted stand-in model: responders per agent name return JSON text (no API calls)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class FakeRequest:
    agent_name: str
    system: str
    prompt: str
    n_images: int


@dataclass(frozen=True)
class FakeCall:
    prompt: str
    n_contents: int
    system: str


Responder = Callable[[str, FakeRequest], str]

RESPONDERS: dict[str, Responder] = {}
CALLS: dict[str, list[FakeCall]] = {}


def register_responders(responders: dict[str, Responder]) -> None:
    RESPONDERS.update(responders)


def fake_respond(agent_name: str, system: str, prompt: str, n_images: int, n_contents: int) -> str:
    CALLS.setdefault(agent_name, []).append(FakeCall(prompt=prompt, n_contents=n_contents, system=system))
    responder = RESPONDERS.get(agent_name)
    if responder is None:
        return "{}"
    return responder(prompt, FakeRequest(agent_name=agent_name, system=system, prompt=prompt, n_images=n_images))
