"""A rule-based stand-in for a model. It needs no API key, so the CLI and tests can run
offline, and it gives the evaluation a non-AI baseline to beat."""

from __future__ import annotations

import json
import re
import uuid

from ..config import Config
from ..kev import find_cves
from ..prompts import unwrap_ticket
from .base import Message, ModelReply, ToolCall, ToolSpec, Usage

_KB_HIT = re.compile(r'"id": "(KB-\d{3})", "title": "([^"]*)", "queue": "([a-z-]+)"')
_SECURITY_WORDS = ("vulnerab", "cve", "fortigate", "fortinet", "citrix", "netscaler", "log4j",
                   "moveit", "exploit")


class KeywordModel:
    name = "keyword-baseline"

    def __init__(self, config: Config):
        self.config = config

    def complete(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec],
        tool_choice: str | None = None,
    ) -> ModelReply:
        ticket = unwrap_ticket(messages[0].text)
        lowered = ticket.lower()
        available = {t.name for t in tools}
        called = {c.name for m in messages if m.role == "assistant" for c in m.tool_calls}

        if "plan_searches" in available:
            security = any(w in lowered for w in _SECURITY_WORDS)
            return self._call("plan_searches", {"kb_query": _subject(ticket),
                                                "product": _subject(ticket) if security else ""})
        if ("check_known_exploited" in available and "check_known_exploited" not in called
                and any(w in lowered for w in _SECURITY_WORDS)):
            query = " ".join(find_cves(ticket)) or _subject(ticket)
            return self._call("check_known_exploited", {"query": query})
        if "search_kb" in available and "search_kb" not in called:
            return self._call("search_kb", {"query": ticket[:400]})
        return self._call("submit_triage", self._classify(ticket, messages))

    def _classify(self, ticket: str, messages: list[Message]) -> dict:
        text = ticket.lower()
        scores = {
            queue: sum(text.count(word) for word in spec.get("keywords", []))
            for queue, spec in self.config.queues.items()
        }
        queue = max(scores, key=lambda q: scores[q])
        if scores[queue] == 0:
            queue = "service-desk"

        rules = self.config.keyword_baseline
        priority = next(
            (p for p in ("P1", "P2", "P4") if any(w in text for w in rules["priority"].get(p, []))),
            "P3",
        )
        ticket_type = next(
            (t for t in ("change", "problem", "request")
             if any(w in text for w in rules["type"].get(t, []))),
            "incident",
        )

        seen = "\n".join(
            [m.text for m in messages]
            + [r.content for m in messages for r in m.tool_results]
        )
        cited = [(kb_id, title) for kb_id, title, kb_queue in _KB_HIT.findall(seen)
                 if kb_queue == queue][:1]
        reply = (f"Thanks for getting in touch about \"{_subject(ticket)}\". "
                 "A technician will review it.")
        if cited:
            reply += f" In the meantime, this article may help: {cited[0][1]} ({cited[0][0]})."
        return {
            "ticket_type": ticket_type,
            "queue": queue,
            "priority": priority,
            "confidence": 0.8 if scores[queue] > 0 else 0.4,
            "summary": _subject(ticket),
            "kb_articles": [kb_id for kb_id, _ in cited],
            "draft_reply": reply,
            "escalate": False,
            "escalation_reason": "",
        }

    @staticmethod
    def _call(name: str, arguments: dict) -> ModelReply:
        call = ToolCall(f"kw_{uuid.uuid4().hex[:8]}", name, json.loads(json.dumps(arguments)))
        return ModelReply("", [call], Usage())


def _subject(ticket: str) -> str:
    first = ticket.splitlines()[0] if ticket else ""
    match = re.search(r"Subject: (.*)", ticket)
    return (match.group(1) if match else first).strip()
