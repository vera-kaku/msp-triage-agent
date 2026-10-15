"""OpenAI Chat Completions adapter. Also used for Azure OpenAI and DeepSeek,
which accept the same request format."""

from __future__ import annotations

import json
from typing import Any

from .base import Message, ModelReply, ToolCall, ToolSpec, Usage


class OpenAICompatibleModel:
    def __init__(self, client: Any, model: str, name: str, extra_body: dict | None = None,
                 temperature: float | None = None):
        self.client = client
        self.model = model
        self.name = name
        self.extra_body = extra_body or {}
        self.temperature = temperature  # None leaves the provider default
        self._tool_choice_supported = True

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        tool_choice: str | None = None,
    ) -> ModelReply:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": self._to_wire(system, messages),
            "tools": [
                {"type": "function",
                 "function": {"name": t.name, "description": t.description,
                              "parameters": t.parameters}}
                for t in tools
            ],
        }
        if tool_choice and self._tool_choice_supported:
            kwargs["tool_choice"] = (
                "required" if tool_choice == "any"
                else {"type": "function", "function": {"name": tool_choice}}
            )
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body

        try:
            response = self.client.chat.completions.create(**kwargs)
        except Exception as err:  # some compatible APIs reject tool_choice
            if "tool_choice" in kwargs and "tool_choice" in str(err):
                self._tool_choice_supported = False
                kwargs.pop("tool_choice")
                response = self.client.chat.completions.create(**kwargs)
            else:
                raise

        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = None
            if not isinstance(args, dict):
                args = {"_invalid_json": call.function.arguments}
            calls.append(ToolCall(call.id, call.function.name, args))

        extra = {}
        reasoning = getattr(message, "reasoning_content", None)
        if reasoning is None and getattr(message, "model_extra", None):
            reasoning = message.model_extra.get("reasoning_content")
        if reasoning:
            extra["reasoning_content"] = reasoning

        usage = Usage()
        if response.usage:
            usage = Usage(response.usage.prompt_tokens, response.usage.completion_tokens)
        return ModelReply(message.content or "", calls, usage, extra)

    @staticmethod
    def _to_wire(system: str, messages: list[Message]) -> list[dict]:
        wire: list[dict] = [{"role": "system", "content": system}]
        for m in messages:
            if m.role == "user":
                wire.append({"role": "user", "content": m.text})
            elif m.role == "assistant":
                item: dict[str, Any] = {"role": "assistant", "content": m.text or None}
                if m.tool_calls:
                    item["tool_calls"] = [
                        {"id": c.id, "type": "function",
                         "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                        for c in m.tool_calls
                    ]
                if "reasoning_content" in m.extra:
                    item["reasoning_content"] = m.extra["reasoning_content"]
                wire.append(item)
            else:
                wire.extend(
                    {"role": "tool", "tool_call_id": r.call_id, "content": r.content}
                    for r in m.tool_results
                )
        return wire
