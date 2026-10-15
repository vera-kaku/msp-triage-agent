"""Check the request and response formats of the provider adapters with fake clients."""

import json
from types import SimpleNamespace as NS

from triage_agent.llm.anthropic_model import AnthropicModel
from triage_agent.llm.base import Message, ToolCall, ToolResult, ToolSpec
from triage_agent.llm.openai_compat import OpenAICompatibleModel

SPEC = ToolSpec("search_kb", "Search", {"type": "object", "properties": {}})
HISTORY = [
    Message("user", text="<ticket>hi</ticket>"),
    Message("assistant", tool_calls=[ToolCall("c1", "search_kb", {"query": "vpn"})],
            extra={"reasoning_content": "thinking..."}),
    Message("tool", tool_results=[ToolResult("c1", "[]", False)]),
]


class FakeOpenAI:
    def __init__(self, fail_on_tool_choice=False):
        self.calls = []
        self.fail_on_tool_choice = fail_on_tool_choice
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_on_tool_choice and "tool_choice" in kwargs:
            raise ValueError("tool_choice is not supported")
        call = NS(id="c2", function=NS(name="submit_triage", arguments='{"queue": "network"}'))
        message = NS(content=None, tool_calls=[call], reasoning_content="more thinking")
        return NS(choices=[NS(message=message)],
                  usage=NS(prompt_tokens=100, completion_tokens=20))


def test_openai_wire_format_and_reply():
    client = FakeOpenAI()
    model = OpenAICompatibleModel(client, "deepseek-flash", "deepseek",
                                  extra_body={"thinking": {"type": "disabled"}})
    reply = model.complete("system", HISTORY, [SPEC], tool_choice="any")

    sent = client.calls[0]
    assert sent["tool_choice"] == "required"
    assert sent["extra_body"] == {"thinking": {"type": "disabled"}}
    roles = [m["role"] for m in sent["messages"]]
    assert roles == ["system", "user", "assistant", "tool"]
    assistant = sent["messages"][2]
    assert assistant["reasoning_content"] == "thinking..."
    assert json.loads(assistant["tool_calls"][0]["function"]["arguments"]) == {"query": "vpn"}
    assert sent["messages"][3]["tool_call_id"] == "c1"

    assert reply.tool_calls[0].arguments == {"queue": "network"}
    assert reply.extra["reasoning_content"] == "more thinking"
    assert (reply.usage.input_tokens, reply.usage.output_tokens) == (100, 20)


def test_openai_named_tool_choice_and_fallback():
    client = FakeOpenAI(fail_on_tool_choice=True)
    model = OpenAICompatibleModel(client, "m", "m")
    model.complete("system", HISTORY, [SPEC], tool_choice="submit_triage")
    assert client.calls[0]["tool_choice"]["function"]["name"] == "submit_triage"
    assert "tool_choice" not in client.calls[1]
    model.complete("system", HISTORY, [SPEC], tool_choice="any")
    assert "tool_choice" not in client.calls[2]  # remembered


def test_full_agent_run_through_openai_adapter(config):
    """Every tool call id the model sends must get a matching tool message back."""
    from conftest import submit_args

    from triage_agent.models import Ticket
    from triage_agent.runner import Triager

    replies = [
        [("a1", "search_kb", {"query": "vpn"}), ("a2", "find_similar_tickets", {"query": "vpn"})],
        [("a3", "submit_triage", submit_args(queue="network", kb_articles=["KB-008"]))],
    ]
    sent = []

    def create(**kwargs):
        sent.append(kwargs)
        calls = [NS(id=i, function=NS(name=n, arguments=json.dumps(a)))
                 for i, n, a in replies[len(sent) - 1]]
        return NS(choices=[NS(message=NS(content=None, tool_calls=calls))],
                  usage=NS(prompt_tokens=200, completion_tokens=30))

    model = OpenAICompatibleModel(NS(chat=NS(completions=NS(create=create))), "m", "fake")
    result = Triager(config, model).run(Ticket("t", "VPN", "VPN will not connect"), "agent")

    assert result.triage.kb_articles == ["KB-008"]
    assert (result.input_tokens, result.output_tokens) == (400, 60)
    second = sent[1]["messages"]
    tool_ids = [m["tool_call_id"] for m in second if m["role"] == "tool"]
    assert tool_ids == ["a1", "a2"]


def test_anthropic_wire_format_and_reply():
    sent = {}

    def create(**kwargs):
        sent.update(kwargs)
        return NS(content=[NS(type="text", text="Checking."),
                           NS(type="tool_use", id="t9", name="search_kb", input={"query": "x"})],
                  usage=NS(input_tokens=50, output_tokens=10))

    model = AnthropicModel(NS(messages=NS(create=create)), "claude-haiku-5-5")
    reply = model.complete("system", HISTORY, [SPEC], tool_choice="search_kb")

    assert sent["tool_choice"] == {"type": "tool", "name": "search_kb"}
    assert sent["tools"][0]["input_schema"] == SPEC.parameters
    assert sent["messages"][1]["content"][0]["type"] == "tool_use"
    result = sent["messages"][2]
    assert result["role"] == "user" and result["content"][0]["tool_use_id"] == "c1"
    assert reply.text == "Checking." and reply.tool_calls[0].id == "t9"
