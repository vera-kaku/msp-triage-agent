"""Download the current CISA Known Exploited Vulnerabilities catalog to data/kev.json.

    python scripts/download_kev.py
"""

import json
import urllib.request
from pathlib import Path

URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
OUT = Path(__file__).resolve().parents[1] / "data" / "kev.json"


def main() -> None:
    request = urllib.request.Request(URL, headers={"User-Agent": "msp-triage-agent"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = json.load(response)
    OUT.write_text(json.dumps(data), encoding="utf-8")
    print(f"Saved {data['count']} entries (catalog {data['catalogVersion']}) to {OUT}")


if __name__ == "__main__":
    main()
