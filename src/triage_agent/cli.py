"""Command line interface.

  triage run  --provider deepseek --subject "VPN down" --body "Nobody can connect"
  triage run  --provider keyword --ticket T21
  triage batch --provider deepseek --tickets data/imported.jsonl --out triaged.jsonl
  triage eval --provider deepseek --mode both --workers 4
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from .config import DEFAULT_CONFIG, load_config
from .evaluate import markdown_table, run_all, score
from .llm import PROVIDERS, make_model
from .models import RunResult, Ticket
from .runner import MODES, Triager, load_tickets

DEFAULT_TICKETS = Path("eval/tickets.jsonl")


def _load_dotenv(path: Path = Path(".env")) -> None:
    """Read KEY=value lines from .env. Values in .env take priority over the shell."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if value[:1] in ("'", '"') and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]  # KEY="value" or KEY='value'
        elif " #" in value:
            value = value.split(" #", 1)[0].strip()  # KEY=value  # comment
        if value:
            os.environ[key] = value


def _print_run(result: RunResult) -> None:
    t = result.triage
    print(f"\n{result.ticket_id}  [{result.mode}, {result.model}]")
    for step in result.steps:
        flag = " (error)" if step.is_error else ""
        args = step.arguments.get("query", "") if step.tool != "submit_triage" else ""
        print(f"  -> {step.tool}{flag} {args[:70]}")
    print(f"  Type: {t.ticket_type}   Queue: {t.queue}   Priority: {t.priority}   "
          f"Confidence: {t.confidence:.2f}")
    print(f"  Escalate: {'yes' if t.escalate else 'no'}")
    for reason in t.escalation_reasons:
        print(f"    - {reason}")
    print(f"  KB: {', '.join(t.kb_articles) or 'none'}")
    print(f"  Summary: {t.summary}")
    if t.draft_reply:
        print("  Draft reply (for technician review):")
        for line in t.draft_reply.splitlines():
            print(f"    {line}")
    print(f"  Model calls: {result.model_calls}   Tokens: {result.input_tokens} in, "
          f"{result.output_tokens} out   {result.seconds}s")


def cmd_run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    triager = Triager(config, make_model(args.provider, config, args.model))
    if args.ticket:
        rows = {r["id"]: r for r in load_tickets(args.tickets)}
        if args.ticket not in rows:
            sys.exit(f"No ticket {args.ticket} in {args.tickets}")
        row = rows[args.ticket]
        ticket = Ticket(row["id"], row["subject"], row["body"])
    elif args.subject and args.body:
        ticket = Ticket("cli", args.subject, args.body)
    else:
        sys.exit("Give --ticket ID, or both --subject and --body.")
    modes = MODES if args.mode == "both" else (args.mode,)
    for mode in modes:
        result = triager.run(ticket, mode)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            _print_run(result)


def cmd_batch(args: argparse.Namespace) -> None:
    """Triage every ticket in a JSON Lines file, for example one made by Import-Tickets.ps1."""
    config = load_config(args.config)
    triager = Triager(config, make_model(args.provider, config, args.model))
    rows = load_tickets(args.tickets)
    mode = "agent" if args.mode == "both" else args.mode
    runs = run_all(triager, rows, mode, args.workers, progress=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        for run in runs:
            handle.write(json.dumps(run.to_dict()) + "\n")
    escalated = sum(r.triage.escalate for r in runs)
    print(f"Triaged {len(runs)} tickets, {escalated} escalated. Saved to {args.out}")


def cmd_eval(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    model = make_model(args.provider, config, args.model)
    triager = Triager(config, model)
    rows = load_tickets(args.tickets)
    splits = sorted({r.get("split", "all") for r in rows}) if args.split == "each" else [args.split]
    modes = MODES if args.mode == "both" else (args.mode,)

    results, all_runs = {}, {}
    for mode in modes:
        runs = run_all(triager, rows, mode, args.workers, progress=True)
        all_runs[mode] = [r.to_dict() for r in runs]
        for split in splits:
            subset = rows if split == "all" else [r for r in rows if r.get("split") == split]
            if subset:
                results[f"{mode}, {split} ({len(subset)})"] = score(subset, runs,
                                                                     config.priority_order)

    table = markdown_table(results)
    print(f"\nModel: {model.name}   KB articles: {len(triager.kb.articles)}   "
          f"KEV: {triager.kev.source}\n")
    print(table)
    for column, result in results.items():
        if result["misses"]:
            print(f"\nMisses, {column}:")
            for miss in result["misses"]:
                print(f"  {miss['id']} {miss['subject']}: {'; '.join(miss['wrong'])}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    slug = model.name.replace("/", "_")
    (out / f"{stamp}-{slug}.json").write_text(
        json.dumps({"model": model.name, "results": results, "runs": all_runs}, indent=2),
        encoding="utf-8")
    (out / f"{stamp}-{slug}.md").write_text(
        f"# Evaluation: {model.name}\n\nTickets: {args.tickets}\n\n{table}\n", encoding="utf-8")
    print(f"\nSaved to {out}/{stamp}-{slug}.json and .md")


def main(argv: list[str] | None = None) -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(prog="triage", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--provider", choices=PROVIDERS, default="keyword")
        p.add_argument("--model", help="Model or deployment name. Overrides TRIAGE_MODEL.")
        p.add_argument("--mode", choices=(*MODES, "both"), default="agent")
        p.add_argument("--tickets", default=str(DEFAULT_TICKETS))

    run = sub.add_parser("run", help="Triage one ticket and print the result.")
    common(run)
    run.add_argument("--ticket", help="Ticket id from the tickets file, such as T12.")
    run.add_argument("--subject")
    run.add_argument("--body")
    run.add_argument("--json", action="store_true")
    run.set_defaults(func=cmd_run)

    batch = sub.add_parser("batch", help="Triage every ticket in a file and save the results.")
    common(batch)
    batch.add_argument("--workers", type=int, default=1)
    batch.add_argument("--out", default="triaged.jsonl")
    batch.set_defaults(func=cmd_batch)

    ev = sub.add_parser("eval", help="Score a provider on the labelled tickets.")
    common(ev)
    ev.add_argument("--split", default="each", help="dev, holdout, all, or each (default).")
    ev.add_argument("--workers", type=int, default=1)
    ev.add_argument("--out", default="eval/results")
    ev.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    try:
        args.func(args)
    except Exception as err:
        if type(err).__name__ == "AuthenticationError":
            sys.exit(f"The {args.provider} API rejected the key. Check the key in .env: no "
                     f"quotes or spaces, and not expired or deleted.\nDetails: {err}")
        raise


if __name__ == "__main__":
    main()
