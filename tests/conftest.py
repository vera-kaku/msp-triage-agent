from pathlib import Path

import pytest

from triage_agent.config import load_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def config():
    cfg = load_config(ROOT / "config" / "triage.yaml")
    # Tests always use the small fixture, even if the full catalog has been downloaded.
    cfg.paths["kev"] = cfg.paths["kev_fallback"]
    return cfg


def submit_args(**overrides):
    args = {
        "ticket_type": "incident",
        "queue": "identity-access",
        "priority": "P3",
        "confidence": 0.9,
        "summary": "User forgot their password.",
        "kb_articles": [],
        "draft_reply": "You can reset your password at https://aka.ms/sspr.",
        "escalate": False,
        "escalation_reason": "",
    }
    args.update(overrides)
    return args
