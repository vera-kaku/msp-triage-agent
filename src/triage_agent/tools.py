"""Tools the agent can call, and the schema for its final answer."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .config import Config
from .kev import KevCatalog
from .knowledge import KnowledgeBase, TicketHistory
from .llm.base import ToolSpec


def _query_schema(description: str) -> dict:
    return {
        "type": "object",
        "properties": {"query": {"type": "string", "description": description}},
        "required": ["query"],
    }


def submit_spec(config: Config) -> ToolSpec:
    return ToolSpec(
        name="submit_triage",
        description="Submit the final triage decision and the draft reply. This ends the run.",
        parameters={
            "type": "object",
            "properties": {
                "ticket_type": {"type": "string", "enum": list(config.ticket_types)},
                "queue": {"type": "string", "enum": list(config.queues)},
                "priority": {"type": "string", "enum": list(config.priorities)},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "summary": {"type": "string", "description": "One sentence for the technician."},
                "kb_articles": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Ids of knowledge base articles used in the reply.",
                },
                "draft_reply": {"type": "string", "description": "Reply to the customer."},
                "escalate": {"type": "boolean"},
                "escalation_reason": {"type": "string"},
            },
            "required": ["ticket_type", "queue", "priority", "confidence", "summary",
                         "kb_articles", "draft_reply", "escalate"],
        },
    )


def plan_spec() -> ToolSpec:
    """Used by hybrid mode when the code's own searches look weak."""
    return ToolSpec(
        name="plan_searches",
        description="Suggest search terms for this ticket.",
        parameters={
            "type": "object",
            "properties": {
                "kb_query": {
                    "type": "string",
                    "description": "Keywords for the knowledge base, in the standard IT terms "
                                   "an article title would use rather than the customer's "
                                   "own wording.",
                },
                "product": {
                    "type": "string",
                    "description": "Vendor and product name of software or a device that the "
                                   "ticket says may have a vulnerability. Empty if none.",
                },
            },
            "required": ["kb_query", "product"],
        },
    )


def research_specs() -> list[ToolSpec]:
    return [
        ToolSpec("search_kb",
                 "Search the knowledge base of how-to and troubleshooting articles.",
                 _query_schema("Keywords describing the problem or request.")),
        ToolSpec("find_similar_tickets",
                 "Find resolved past tickets that look similar, with their queue, priority "
                 "and resolution.",
                 _query_schema("Keywords describing the ticket.")),
        ToolSpec("check_known_exploited",
                 "Check the CISA Known Exploited Vulnerabilities catalog by CVE number or by "
                 "vendor and product name.",
                 _query_schema("One or more CVE numbers, or a vendor and product name.")),
    ]


@dataclass
class RunState:
    """What the agent has seen so far. Used to check its final answer."""

    kb_ids_seen: set[str] = field(default_factory=set)
    kev_matches: list[dict] = field(default_factory=list)
    calls_per_tool: dict[str, int] = field(default_factory=dict)


class Toolbox:
    def __init__(self, config: Config, kb: KnowledgeBase, history: TicketHistory,
                 kev: KevCatalog):
        self.config = config
        self.kb = kb
        self.history = history
        self.kev = kev

    def run(self, name: str, arguments: dict, state: RunState) -> tuple[str, bool]:
        """Return (content, is_error)."""
        limit = self.config.limits["max_calls_per_tool"]
        count = state.calls_per_tool.get(name, 0)
        if count >= limit:
            return f"{name} has already been called {limit} times. Submit your triage now.", True
        query = arguments.get("query")
        if not isinstance(query, str) or not query.strip():
            return "The query argument must be a non-empty string.", True
        state.calls_per_tool[name] = count + 1

        if name == "search_kb":
            hits = self.kb.search(query, self.config.limits["kb_results"])
            state.kb_ids_seen.update(h["id"] for h in hits)
            return json.dumps(hits or "No matching articles."), False
        if name == "find_similar_tickets":
            hits = self.history.search(query, self.config.limits["history_results"])
            return json.dumps(hits or "No similar tickets."), False
        if name == "check_known_exploited":
            result = self.kev.lookup(query)
            if result["match_type"] == "cve":
                # Only exact CVE matches trigger the escalation rule. Product matches are
                # information for the model to weigh.
                state.kev_matches.extend(result["matches"])
            return json.dumps(result), False
        return f"Unknown tool {name}.", True
