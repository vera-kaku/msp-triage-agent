"""Run a ticket through the agent loop or the fixed workflow, then apply the rules."""

from __future__ import annotations

import json
import time

from .config import Config
from .kev import KevCatalog, find_cves
from .knowledge import KnowledgeBase, TicketHistory
from .llm.base import ChatModel, Message, ToolResult, Usage
from .models import RunResult, Step, Ticket, Triage
from .prompts import (
    PLANNER_SYSTEM_PROMPT,
    agent_system_prompt,
    workflow_system_prompt,
    wrap_ticket,
)
from .redact import redact
from .tools import RunState, Toolbox, plan_spec, research_specs, submit_spec

MODES = ("agent", "workflow", "hybrid")
VULNERABILITY_REASON = "mentions a vulnerability without a CVE number"


class Triager:
    def __init__(self, config: Config, model: ChatModel):
        self.config = config
        self.model = model
        self.kb = KnowledgeBase(config.path("kb_dir"))
        self.history = TicketHistory(config.path("history"))
        self.kev = KevCatalog(config.path("kev"), config.path("kev_fallback"))
        self.toolbox = Toolbox(config, self.kb, self.history, self.kev)

    # ------------------------------------------------------------------ public

    def run(self, ticket: Ticket, mode: str = "agent") -> RunResult:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        text, _ = redact(ticket.text())
        started = time.perf_counter()
        usage = Usage()
        state = RunState()
        steps: list[Step] = []
        if mode == "agent":
            outcome = self._agent(text, state, steps, usage)
        else:
            outcome = self._workflow(text, state, steps, usage, hybrid=mode == "hybrid")
        triage, model_calls, rejected, stop_reason = outcome
        triage = self._apply_policy(triage, state, ticket.text())
        return RunResult(
            ticket_id=ticket.id, mode=mode, model=self.model.name, triage=triage, steps=steps,
            model_calls=model_calls, input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            seconds=round(time.perf_counter() - started, 2),
            rejected_submissions=rejected, stop_reason=stop_reason,
        )

    # ------------------------------------------------------------------ modes

    def _agent(self, text: str, state: RunState, steps: list[Step], usage: Usage):
        system = agent_system_prompt(self.config)
        tools = research_specs() + [submit_spec(self.config)]
        messages = [Message("user", text=wrap_ticket(text))]
        rejected = 0
        max_steps = self.config.limits["max_steps"]

        for call_number in range(1, max_steps + 1):
            # On the last step only submitting is allowed.
            last = call_number == max_steps
            offered = [tools[-1]] if last else tools
            offered_names = {t.name for t in offered}
            reply = self.model.complete(
                system, messages, offered,
                tool_choice="submit_triage" if last else "any",
            )
            _add(usage, reply.usage)
            messages.append(Message("assistant", text=reply.text,
                                    tool_calls=reply.tool_calls, extra=reply.extra))
            if not reply.tool_calls:
                messages.append(Message("user", text="Use a tool. Finish with submit_triage."))
                continue

            results = []
            for call in reply.tool_calls:
                if call.name not in offered_names:
                    content = f"{call.name} is not available now. Call submit_triage."
                    steps.append(Step(call.name, call.arguments, content, True))
                    results.append(ToolResult(call.id, content, True))
                elif call.name == "submit_triage":
                    triage, errors = self._validate(call.arguments, state)
                    steps.append(Step(call.name, call.arguments,
                                      "; ".join(errors) or "accepted", bool(errors)))
                    if not errors:
                        return triage, call_number, rejected, "submitted"
                    rejected += 1
                    results.append(ToolResult(call.id, "Rejected: " + "; ".join(errors), True))
                else:
                    content, is_error = self.toolbox.run(call.name, call.arguments, state)
                    steps.append(Step(call.name, call.arguments, content, is_error))
                    results.append(ToolResult(call.id, content, is_error))
            messages.append(Message("tool", tool_results=results))

        return self.fallback("The agent reached its step limit."), max_steps, rejected, \
            "step_limit"

    def _workflow(self, text: str, state: RunState, steps: list[Step], usage: Usage,
                  hybrid: bool = False):
        """Fixed steps chosen by code: search, look up CVEs in the text, then one model call.

        Hybrid mode searches with the subject and the full text and merges the results. Only
        when that looks weak does it ask the model for search terms, which costs one extra
        call."""
        context = {}
        planner_calls = 0
        if hybrid:
            limits = self.config.limits
            subject = text.split("\n", 1)[0].removeprefix("Subject: ")
            queries = [subject, text]
            kb_hits = self.kb.search(queries, limits["kb_results"])
            reasons = self._plan_reasons(text, kb_hits)
            plan = {}
            if reasons:
                plan = self._plan(text, usage)
                planner_calls = 1
                steps.append(Step("plan_searches", plan, "; ".join(reasons)))
            history = self.history.search(queries, limits["history_results"])
            shown = "<subject> | <ticket text>"
            if plan.get("kb_query"):
                # The planner only runs when the code's own search looked weak, so its results
                # go first and the earlier results fill any remaining places.
                kb_hits = _merge(self.kb.search(plan["kb_query"], limits["kb_results"]), kb_hits)
                history = _merge(self.history.search(plan["kb_query"],
                                                     limits["history_results"]), history)
                shown += f" | {plan['kb_query']}"
            state.kb_ids_seen.update(h["id"] for h in kb_hits)
            for name, hits, empty in [("search_kb", kb_hits, "No matching articles."),
                                      ("find_similar_tickets", history, "No similar tickets.")]:
                context[name] = hits or empty
                steps.append(Step(name, {"query": shown}, json.dumps(context[name])))
            # Look up a product only for a vulnerability question, not every product named.
            product = plan.get("product") if any(r.startswith(VULNERABILITY_REASON)
                                                 for r in reasons) else None
            kev_queries = [q for q in (" ".join(find_cves(text)), product) if q]
        else:
            for name, query in [("search_kb", text), ("find_similar_tickets", text)]:
                content, _ = self.toolbox.run(name, {"query": query}, state)
                steps.append(Step(name, {"query": "<ticket text>"}, content))
                context[name] = json.loads(content)
            kev_queries = [" ".join(find_cves(text))] if find_cves(text) else []
        lookups = []
        for query in kev_queries:
            content, _ = self.toolbox.run("check_known_exploited", {"query": query}, state)
            steps.append(Step("check_known_exploited", {"query": query}, content))
            lookups.append(json.loads(content))
        if lookups:
            context["check_known_exploited"] = lookups[0] if len(lookups) == 1 else lookups

        rendered = "\n\n".join(f"{name} results:\n{json.dumps(value)}"
                               for name, value in context.items())
        messages = [Message("user", text=f"{wrap_ticket(text)}\n\nRetrieved context:\n{rendered}")]
        spec = submit_spec(self.config)
        rejected = 0
        for attempt in (1, 2):  # one retry if the answer breaks a rule
            reply = self.model.complete(workflow_system_prompt(self.config), messages, [spec],
                                        tool_choice=spec.name)
            _add(usage, reply.usage)
            call = next((c for c in reply.tool_calls if c.name == spec.name), None)
            if call is None:
                errors = ["No submit_triage call."]
            else:
                triage, errors = self._validate(call.arguments, state)
                steps.append(Step(call.name, call.arguments, "; ".join(errors) or "accepted",
                                  bool(errors)))
                if not errors:
                    return triage, attempt + planner_calls, rejected, "submitted"
            rejected += 1
            messages.append(Message("assistant", text=reply.text, tool_calls=reply.tool_calls,
                                    extra=reply.extra))
            messages.append(Message("tool", tool_results=[
                ToolResult(c.id, "Rejected: " + "; ".join(errors), True)
                for c in reply.tool_calls
            ]) if reply.tool_calls else Message("user", text="Call submit_triage."))
        return self.fallback("The model did not return a valid triage."), 2 + planner_calls, \
            rejected, "step_limit"

    def _plan_reasons(self, text: str, kb_hits: list[dict]) -> list[str]:
        """Why hybrid mode should ask the model for search terms. Empty means it should not."""
        rules = self.config.hybrid
        reasons = []
        best = kb_hits[0]["score"] if kb_hits else 0.0
        if best < rules.get("rewrite_below_kb_score", 0):
            reasons.append(f"weak knowledge base match (best score {best})")
        lowered = text.lower()
        if not find_cves(text) and any(w in lowered for w in rules.get("vulnerability_words", [])):
            reasons.append(VULNERABILITY_REASON)
        return reasons

    def _plan(self, text: str, usage: Usage) -> dict:
        """One small model call for search terms. A bad answer just means no extra search."""
        spec = plan_spec()
        reply = self.model.complete(PLANNER_SYSTEM_PROMPT,
                                    [Message("user", text=wrap_ticket(text))], [spec],
                                    tool_choice=spec.name)
        _add(usage, reply.usage)
        call = next((c for c in reply.tool_calls if c.name == spec.name), None)
        args = call.arguments if call else {}
        return {key: value.strip() for key in ("kb_query", "product")
                if isinstance(value := args.get(key), str) and value.strip()}

    # ------------------------------------------------------------------ checks

    def _validate(self, args: dict, state: RunState) -> tuple[Triage | None, list[str]]:
        errors = []
        if "_invalid_json" in args:
            return None, ["Arguments were not valid JSON."]
        checks = [
            ("ticket_type", self.config.ticket_types),
            ("queue", self.config.queues),
            ("priority", self.config.priorities),
        ]
        for key, allowed in checks:
            if args.get(key) not in allowed:
                errors.append(f"{key} must be one of {', '.join(allowed)}")
        try:
            confidence = float(args.get("confidence"))
            if not 0 <= confidence <= 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append("confidence must be a number between 0 and 1")
            confidence = 0.0
        kb_articles = args.get("kb_articles") or []
        if not isinstance(kb_articles, list):
            errors.append("kb_articles must be a list")
            kb_articles = []
        unseen = [a for a in kb_articles if a not in state.kb_ids_seen]
        if unseen:
            errors.append(f"cited articles that were not in search results: {', '.join(unseen)}")
        for key in ("summary", "draft_reply"):
            if not str(args.get(key) or "").strip():
                errors.append(f"{key} must not be empty")
        if errors:
            return None, errors

        reasons = []
        if args.get("escalate"):
            reasons.append("Model: " + (str(args.get("escalation_reason") or "").strip()
                                        or "escalation requested"))
        return Triage(
            ticket_type=args["ticket_type"], queue=args["queue"], priority=args["priority"],
            confidence=confidence, summary=str(args["summary"]).strip(),
            draft_reply=str(args["draft_reply"]).strip(), kb_articles=kb_articles,
            escalate=bool(reasons), escalation_reasons=reasons,
        ), []

    def _apply_policy(self, triage: Triage, state: RunState, original_text: str) -> Triage:
        """Rules from the YAML file. They can add an escalation but never remove one."""
        rules = self.config.escalation
        reasons = list(triage.escalation_reasons)
        if triage.priority in rules.get("always_escalate_priorities", []):
            reasons.append(f"Rule: {triage.priority} tickets always go to a technician.")
        if triage.queue in rules.get("always_escalate_queues", []):
            reasons.append(f"Rule: {triage.queue} tickets always go to a technician.")
        if rules.get("escalate_on_known_exploited"):
            in_ticket = set(find_cves(original_text))
            hits = sorted({m["cveID"] for m in state.kev_matches if m["cveID"] in in_ticket})
            if hits:
                reasons.append(f"Rule: {', '.join(hits)} is in the CISA KEV catalog.")
        if triage.confidence < rules.get("min_confidence", 0):
            reasons.append(f"Rule: confidence {triage.confidence:.2f} is below "
                           f"{rules['min_confidence']}.")
        triage.escalation_reasons = reasons
        triage.escalate = bool(reasons)
        return triage

    def fallback(self, reason: str) -> Triage:
        return Triage(
            ticket_type="incident", queue="service-desk", priority="P3", confidence=0.0,
            summary=reason, draft_reply="", escalate=True,
            escalation_reasons=[f"Rule: {reason} A technician will triage it."],
        )


def _merge(first: list[dict], then: list[dict]) -> list[dict]:
    """Results from both lists without duplicates, as many as the longer list had."""
    seen, merged = set(), []
    for hit in first + then:
        if hit["id"] not in seen:
            seen.add(hit["id"])
            merged.append(hit)
    return merged[:max(len(first), len(then))]


def _add(total: Usage, part: Usage) -> None:
    total.input_tokens += part.input_tokens
    total.output_tokens += part.output_tokens


def load_tickets(path) -> list[dict]:
    # utf-8-sig also reads files written by Windows PowerShell, which start with a BOM.
    with open(path, encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]
