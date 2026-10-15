# Evaluation: deepseek/deepseek-flash/thinking-disabled

Tickets: eval/tickets.jsonl

| Metric | agent, dev (30) | agent, holdout (10) | workflow, dev (30) | workflow, holdout (10) |
|---|---|---|---|---|
| Ticket type | 87% | 80% | 100% | 80% |
| Queue | 100% | 100% | 100% | 100% |
| Priority (exact) | 80% | 70% | 77% | 60% |
| Priority (within one level) | 100% | 100% | 100% | 100% |
| Expected KB article cited | 100% | 100% | 100% | 75% |
| Escalation precision | 100% | 75% | 100% | 60% |
| Escalation recall | 100% | 100% | 100% | 100% |
| Model calls per ticket | 2.17 | 2.3 | 1.0 | 1.0 |
| Tool calls per ticket | 2.07 | 2.2 | 2.07 | 2.1 |
| Rejected submissions | 0 | 0 | 0 | 0 |
| Hit step limit | 0 | 0 | 0 | 0 |
| Input tokens (total) | 122903 | 44338 | 58191 | 19581 |
| Output tokens (total) | 13383 | 4716 | 10858 | 3641 |
| Seconds per ticket | 4.08 | 4.32 | 2.67 | 2.68 |
