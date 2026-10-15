# Evaluation: deepseek/deepseek-flash/thinking-disabled

Tickets: eval/tickets.jsonl

| Metric | agent, dev (30) | agent, holdout (10) | workflow, dev (30) | workflow, holdout (10) |
|---|---|---|---|---|
| Ticket type | 100% | 80% | 100% | 90% |
| Queue | 100% | 100% | 100% | 100% |
| Priority (exact) | 97% | 90% | 93% | 90% |
| Priority (within one level) | 100% | 100% | 100% | 100% |
| Expected KB article cited | 100% | 100% | 100% | 75% |
| Escalation precision | 100% | 75% | 100% | 75% |
| Escalation recall | 100% | 100% | 100% | 100% |
| Model calls per ticket | 2.07 | 2.1 | 1.0 | 1.0 |
| Tool calls per ticket | 2.07 | 2.1 | 2.07 | 2.1 |
| Rejected submissions | 0 | 0 | 0 | 0 |
| Hit step limit | 0 | 0 | 0 | 0 |
| Failed runs | 0 | 0 | 0 | 0 |
| Input tokens (total) | 129735 | 43802 | 64101 | 21551 |
| Output tokens (total) | 13333 | 4488 | 10627 | 3645 |
| Seconds per ticket | 3.98 | 3.97 | 2.58 | 2.65 |
