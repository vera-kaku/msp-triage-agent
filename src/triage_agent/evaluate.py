"""Score triage runs against labelled tickets and compare modes."""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

from .models import RunResult, Ticket
from .runner import Triager


def run_all(triager: Triager, rows: list[dict], mode: str, workers: int = 1,
            progress: bool = False) -> list[RunResult]:
    tickets = [Ticket(r["id"], r["subject"], r["body"]) for r in rows]
    done = 0
    lock = threading.Lock()

    def run_one(ticket: Ticket) -> RunResult:
        nonlocal done
        try:
            result = triager.run(ticket, mode)
        except Exception as err:
            if type(err).__name__ == "AuthenticationError":
                raise  # every other ticket would fail the same way
            # One failed request should not lose the rest of the batch. The ticket goes to
            # a technician like any other run that ends without a valid triage.
            result = RunResult(
                ticket_id=ticket.id, mode=mode, model=triager.model.name,
                triage=triager.fallback(f"The run failed: {type(err).__name__}: {err}"),
                steps=[], model_calls=0, input_tokens=0, output_tokens=0, seconds=0.0,
                rejected_submissions=0, stop_reason="error",
            )
        if progress:
            with lock:
                done += 1
                t = result.triage
                print(f"[{mode} {done}/{len(tickets)}] {ticket.id} {t.queue} {t.priority}"
                      f"{' escalate' if t.escalate else ''}  {result.model_calls} calls, "
                      f"{result.seconds}s", file=sys.stderr, flush=True)
        return result

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(run_one, tickets))


def _rate(hits: int, total: int) -> float | None:
    return round(hits / total, 3) if total else None


def score(rows: list[dict], runs: Iterable[RunResult], priority_order: list[str]) -> dict:
    wanted = {row["id"] for row in rows}
    # Only the runs for these rows, so cost and speed figures match the split.
    by_id = {r.ticket_id: r for r in runs if r.ticket_id in wanted}
    counts = {k: [0, 0] for k in ("type", "queue", "priority", "priority_within_one", "kb_hit")}
    esc = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    misses = []

    for row in rows:
        expected = row.get("expected", {})
        run = by_id[row["id"]]
        got = run.triage
        wrong = []
        for key, value in (("type", got.ticket_type), ("queue", got.queue),
                           ("priority", got.priority)):
            if key in expected:
                counts[key][1] += 1
                if value == expected[key]:
                    counts[key][0] += 1
                else:
                    wrong.append(f"{key} {value} (expected {expected[key]})")
        if "priority" in expected:
            counts["priority_within_one"][1] += 1
            gap = abs(priority_order.index(got.priority)
                      - priority_order.index(expected["priority"]))
            counts["priority_within_one"][0] += gap <= 1
        if expected.get("kb"):
            counts["kb_hit"][1] += 1
            if set(got.kb_articles) & set(expected["kb"]):
                counts["kb_hit"][0] += 1
            else:
                wrong.append(f"kb {got.kb_articles or 'none'} (expected {expected['kb']})")
        if "escalate" in expected:
            key = ("t" if got.escalate == expected["escalate"] else "f") + \
                  ("p" if got.escalate else "n")
            esc[key] += 1
            if got.escalate != expected["escalate"]:
                wrong.append(f"escalate {got.escalate} (expected {expected['escalate']})")
        if wrong:
            misses.append({"id": row["id"], "subject": row["subject"], "wrong": wrong,
                           "reasons": got.escalation_reasons})

    runs = list(by_id.values())
    n = len(runs) or 1
    tool_calls = sum(sum(1 for s in r.steps if s.tool != "submit_triage") for r in runs)
    summary = {
        "tickets": len(runs),
        "type_accuracy": _rate(*counts["type"]),
        "queue_accuracy": _rate(*counts["queue"]),
        "priority_accuracy": _rate(*counts["priority"]),
        "priority_within_one": _rate(*counts["priority_within_one"]),
        "kb_hit_rate": _rate(*counts["kb_hit"]),
        "escalation_precision": _rate(esc["tp"], esc["tp"] + esc["fp"]),
        "escalation_recall": _rate(esc["tp"], esc["tp"] + esc["fn"]),
        "escalation_counts": esc,
        "avg_model_calls": round(sum(r.model_calls for r in runs) / n, 2),
        "avg_tool_calls": round(tool_calls / n, 2),
        "rejected_submissions": sum(r.rejected_submissions for r in runs),
        "hit_step_limit": sum(r.stop_reason == "step_limit" for r in runs),
        "errors": sum(r.stop_reason == "error" for r in runs),
        "input_tokens": sum(r.input_tokens for r in runs),
        "output_tokens": sum(r.output_tokens for r in runs),
        "avg_seconds": round(sum(r.seconds for r in runs) / n, 2),
    }
    return {"summary": summary, "misses": misses}


_ROWS = [
    ("Ticket type", "type_accuracy"),
    ("Queue", "queue_accuracy"),
    ("Priority (exact)", "priority_accuracy"),
    ("Priority (within one level)", "priority_within_one"),
    ("Expected KB article cited", "kb_hit_rate"),
    ("Escalation precision", "escalation_precision"),
    ("Escalation recall", "escalation_recall"),
    ("Model calls per ticket", "avg_model_calls"),
    ("Tool calls per ticket", "avg_tool_calls"),
    ("Rejected submissions", "rejected_submissions"),
    ("Hit step limit", "hit_step_limit"),
    ("Failed runs", "errors"),
    ("Input tokens (total)", "input_tokens"),
    ("Output tokens (total)", "output_tokens"),
    ("Seconds per ticket", "avg_seconds"),
]


def markdown_table(results: dict[str, dict]) -> str:
    """results maps a column name (for example 'agent, dev') to a score() result."""
    columns = list(results)
    lines = ["| Metric | " + " | ".join(columns) + " |",
             "|---|" + "---|" * len(columns)]
    for label, key in _ROWS:
        cells = []
        for column in columns:
            value = results[column]["summary"][key]
            if value is None:
                cells.append("n/a")
            elif isinstance(value, float) and key.endswith(("accuracy", "rate", "precision",
                                                            "recall", "within_one")):
                cells.append(f"{value:.0%}")
            else:
                cells.append(str(value))
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)
