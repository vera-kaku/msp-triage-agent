"""A model that replays prepared replies. Used in tests to drive the agent loop."""

from __future__ import annotations

from collections.abc import Callable

from .base import Message, ModelReply, ToolCall, ToolSpec, Usage

Step = ModelReply | Callable[[list[Message]], ModelReply]


def tool_reply(name: str, arguments: dict, call_id: str | None = None) -> ModelReply:
    return ModelReply("", [ToolCall(call_id or f"call_{name}", name, arguments)], Usage(10, 5))


class ScriptedModel:
    name = "scripted"

    def __init__(self, steps: list[Step]):
        self.steps = list(steps)
        self.requests: list[dict] = []

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        tool_choice: str | None = None,
    ) -> ModelReply:
        self.requests.append({"messages": list(messages), "tools": [t.name for t in tools],
                              "tool_choice": tool_choice})
        if not self.steps:
            raise AssertionError("ScriptedModel ran out of replies")
        step = self.steps.pop(0)
        return step(messages) if callable(step) else step
