"""Load the YAML triage rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG = Path("config/triage.yaml")


@dataclass
class Config:
    root: Path
    ticket_types: dict[str, str]
    queues: dict[str, dict]
    priorities: dict[str, str]
    keyword_baseline: dict
    escalation: dict
    limits: dict
    paths: dict[str, str] = field(default_factory=dict)
    hybrid: dict = field(default_factory=dict)

    def path(self, key: str) -> Path:
        return self.root / self.paths[key]

    @property
    def priority_order(self) -> list[str]:
        return list(self.priorities)


def load_config(path: str | Path = DEFAULT_CONFIG) -> Config:
    path = Path(path).resolve()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Config(
        root=path.parent.parent,
        ticket_types=data["ticket_types"],
        queues=data["queues"],
        priorities=data["priorities"],
        keyword_baseline=data.get("keyword_baseline", {}),
        escalation=data["escalation"],
        limits=data["limits"],
        paths=data["paths"],
        hybrid=data.get("hybrid", {}),
    )
