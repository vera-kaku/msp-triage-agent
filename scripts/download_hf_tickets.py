"""Download a sample of English tickets from the Tobi-Bueck/customer-support-tickets dataset
on Hugging Face, for a larger check of ticket type classification.

The dataset is licensed CC BY-NC 4.0 (non-commercial) and appears to be synthetic.
It is not committed to this repository.

    pip install -e ".[hf]"
    python scripts/download_hf_tickets.py --n 200
    triage eval --provider deepseek --mode workflow --tickets data/hf_tickets.jsonl --split all
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from datasets import load_dataset

OUT = Path(__file__).resolve().parents[1] / "data" / "hf_tickets.jsonl"
TYPES = {"incident", "request", "problem", "change"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    data = load_dataset("Tobi-Bueck/customer-support-tickets", split="train")
    data = data.filter(lambda row: row.get("language") == "en" and row.get("body"))
    data = data.shuffle(seed=args.seed).select(range(min(args.n, len(data))))

    written = 0
    with OUT.open("w", encoding="utf-8") as handle:
        for i, row in enumerate(data):
            ticket_type = str(row.get("type") or "").strip().lower()
            if ticket_type not in TYPES:
                continue
            handle.write(json.dumps({
                "id": f"HF-{i:04d}",
                "split": "hf",
                "subject": row.get("subject") or "(no subject)",
                "body": row["body"],
                # Only the ticket type maps onto this project's labels. The dataset's queues
                # and priorities use a different scheme, so they are kept for reference only.
                "expected": {"type": ticket_type},
                "source_queue": row.get("queue"),
                "source_priority": row.get("priority"),
            }) + "\n")
            written += 1

    print(f"Saved {written} tickets to {OUT}")
    print("Types:", dict(Counter(r.get("type") for r in data)))
    print("Priorities:", dict(Counter(r.get("priority") for r in data)))


if __name__ == "__main__":
    main()
