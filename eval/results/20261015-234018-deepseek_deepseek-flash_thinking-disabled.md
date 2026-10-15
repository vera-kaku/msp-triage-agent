# Evaluation: deepseek/deepseek-flash/thinking-disabled

Tickets: eval/tickets.jsonl

| Metric | agent, dev (30) | agent, holdout (10) | workflow, dev (30) | workflow, holdout (10) | hybrid, dev (30) | hybrid, holdout (10) |
|---|---|---|---|---|---|---|
| Ticket type | 100% | 90% | 100% | 90% | 100% | 90% |
| Queue | 100% | 100% | 100% | 100% | 100% | 100% |
| Priority (exact) | 97% | 90% | 90% | 90% | 90% | 90% |
| Priority (within one level) | 100% | 100% | 100% | 100% | 100% | 100% |
| Expected KB article cited | 100% | 100% | 100% | 75% | 100% | 100% |
| Escalation precision | 100% | 60% | 100% | 75% | 100% | 75% |
| Escalation recall | 100% | 100% | 100% | 100% | 100% | 100% |
| Model calls per ticket | 2.07 | 2.2 | 1.0 | 1.0 | 1.37 | 1.7 |
| Tool calls per ticket | 2.07 | 2.2 | 2.07 | 2.1 | 2.5 | 2.8 |
| Rejected submissions | 0 | 0 | 0 | 0 | 0 | 0 |
| Hit step limit | 0 | 0 | 0 | 0 | 0 | 0 |
| Failed runs | 0 | 0 | 0 | 0 | 0 | 0 |
| Input tokens (total) | 129470 | 46950 | 64101 | 21551 | 69113 | 24422 |
| Output tokens (total) | 13223 | 4584 | 10740 | 3781 | 11378 | 4050 |
| Seconds per ticket | 3.78 | 3.75 | 2.43 | 2.54 | 2.83 | 3.24 |
