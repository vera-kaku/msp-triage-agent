# Evaluation: deepseek/deepseek-flash/thinking-disabled

Tickets: eval/tickets.jsonl

| Metric | hybrid, dev (30) | hybrid, holdout (10) |
|---|---|---|
| Ticket type | 100% | 90% |
| Queue | 100% | 100% |
| Priority (exact) | 90% | 90% |
| Priority (within one level) | 100% | 100% |
| Expected KB article cited | 100% | 100% |
| Escalation precision | 100% | 75% |
| Escalation recall | 100% | 100% |
| Model calls per ticket | 1.37 | 1.7 |
| Tool calls per ticket | 2.47 | 2.8 |
| Rejected submissions | 0 | 0 |
| Hit step limit | 0 | 0 |
| Failed runs | 0 | 0 |
| Input tokens (total) | 68971 | 24422 |
| Output tokens (total) | 11272 | 4126 |
| Seconds per ticket | 2.86 | 3.28 |
