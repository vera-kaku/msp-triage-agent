"""Anthropic Messages API adapter."""

from __future__ import annotations

from typing import Any

from .base import Message, ModelReply, ToolCall, ToolSpec, Usage


class AnthropicModel:
    def __init__(self, client: Any, model: str, max_tokens: int = 1500):
        self.client = client
        self.model = model
        self.name = f"anthropic/{model}"
        self.max_tokens = max_tokens

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        tool_choice: str | None = None,
    ) -> ModelReply:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": self._to_wire(messages),
            "tools": [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ],
        }
        if tool_choice == "any":
            kwargs["tool_choice"] = {"type": "any"}
        elif tool_choice:
            kwargs["tool_choice"] = {"type": "tool", "name": tool_choice}

        response = self.client.messages.create(**kwargs)
        text, calls = [], []
        for block in response.content:
            if block.type == "text":
                text.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(block.id, block.name, dict(block.input)))
        usage = Usage(response.usage.input_tokens, response.usage.output_tokens)
        return ModelReply("\n".join(text), calls, usage)

    @staticmethod
    def _to_wire(messages: list[Message]) -> list[dict]:
        wire: list[dict] = []
        for m in messages:
            if m.role == "user":
                wire.append({"role": "user", "content": m.text})
            elif m.role == "assistant":
                content: list[dict] = []
                if m.text:
                    content.append({"type": "text", "text": m.text})
                content.extend(
                    {"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments}
                    for c in m.tool_calls
                )
                wire.append({"role": "assistant", "content": content})
            else:
                wire.append({"role": "user", "content": [
                    {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content,
                     "is_error": r.is_error}
                    for r in m.tool_results
                ]})
        return wire
