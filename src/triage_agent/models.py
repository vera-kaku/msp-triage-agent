"""Data types shared across the package."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Ticket:
    id: str
    subject: str
    body: str

    def text(self) -> str:
        return f"Subject: {self.subject}\n\n{self.body}"


@dataclass
class Triage:
    ticket_type: str
    queue: str
    priority: str
    confidence: float
    summary: str
    draft_reply: str
    kb_articles: list[str] = field(default_factory=list)
    escalate: bool = False
    escalation_reasons: list[str] = field(default_factory=list)


@dataclass
class Step:
    tool: str
    arguments: dict
    result: str
    is_error: bool = False


@dataclass
class RunResult:
    ticket_id: str
    mode: str
    model: str
    triage: Triage
    steps: list[Step]
    model_calls: int
    input_tokens: int
    output_tokens: int
    seconds: float
    rejected_submissions: int
    stop_reason: str  # "submitted", "step_limit" or "error"

    def to_dict(self) -> dict:
        return asdict(self)
