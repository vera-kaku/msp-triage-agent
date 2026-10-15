"""A provider-neutral interface for chat models that can call tools."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON schema


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


@dataclass
class Message:
    role: Literal["user", "assistant", "tool"]
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    # Provider data that must be sent back on the next request,
    # such as DeepSeek's reasoning_content in thinking mode.
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ModelReply:
    text: str
    tool_calls: list[ToolCall]
    usage: Usage
    extra: dict[str, Any] = field(default_factory=dict)


class ChatModel(Protocol):
    name: str

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        tool_choice: str | None = None,
    ) -> ModelReply:
        """tool_choice: None lets the model decide, "any" requires a tool call,
        any other value forces that tool."""
        ...
