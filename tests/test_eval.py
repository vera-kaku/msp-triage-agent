import json
from pathlib import Path

from triage_agent.cli import main
from triage_agent.knowledge import KnowledgeBase
from triage_agent.runner import load_tickets

ROOT = Path(__file__).resolve().parents[1]


def test_labelled_tickets_are_valid(config):
    rows = load_tickets(ROOT / "eval" / "tickets.jsonl")
    kb = KnowledgeBase(config.path("kb_dir"))
    ids = [r["id"] for r in rows]
    assert len(ids) == len(set(ids)) == 40
    assert {r["split"] for r in rows} == {"dev", "holdout"}
    for row in rows:
        exp = row["expected"]
        assert exp["type"] in config.ticket_types, row["id"]
        assert exp["queue"] in config.queues, row["id"]
        assert exp["priority"] in config.priorities, row["id"]
        assert all(a in kb.articles for a in exp["kb"]), row["id"]
        if exp["priority"] == "P1":
            assert exp["escalate"], f"{row['id']}: P1 tickets must be labelled for escalation"
    assert {r["expected"]["queue"] for r in rows} == set(config.queues)


def test_batch_reads_powershell_output_with_bom(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    imported = tmp_path / "imported.jsonl"
    row = {"id": "mail-001", "subject": "Printer offline", "body": "Nobody can print.",
           "from": "someone@example.co.nz", "date": "Thu, 15 Oct 2026 09:00:00 +1300"}
    imported.write_text(json.dumps(row) + "\n", encoding="utf-8-sig")
    out = tmp_path / "triaged.jsonl"
    main(["batch", "--provider", "keyword", "--tickets", str(imported), "--out", str(out)])
    result = json.loads(out.read_text().splitlines()[0])
    assert result["ticket_id"] == "mail-001" and result["triage"]["queue"] == "service-desk"
    assert "Triaged 1 tickets" in capsys.readouterr().out


def test_split_scores_only_count_their_own_runs(config):
    from triage_agent.evaluate import run_all, score
    from triage_agent.llm.keyword_model import KeywordModel
    from triage_agent.runner import Triager

    rows = load_tickets(ROOT / "eval" / "tickets.jsonl")
    runs = run_all(Triager(config, KeywordModel(config)), rows, "agent")
    holdout = [r for r in rows if r["split"] == "holdout"]
    assert score(holdout, runs, config.priority_order)["summary"]["tickets"] == 10


def test_eval_command_runs_offline(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    main(["eval", "--provider", "keyword", "--mode", "both", "--out", str(tmp_path)])
    output = capsys.readouterr().out
    assert "| Queue |" in output
    saved = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert set(saved["runs"]) == {"agent", "workflow"}
    assert len(saved["runs"]["agent"]) == 40
