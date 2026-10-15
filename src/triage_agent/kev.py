"""Look up the CISA Known Exploited Vulnerabilities (KEV) catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .search import tokenize

CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)


def find_cves(text: str) -> list[str]:
    return sorted({m.upper() for m in CVE_PATTERN.findall(text)})


class KevCatalog:
    def __init__(self, path: Path, fallback: Path | None = None) -> None:
        source = path if path.exists() else fallback
        if source is None or not source.exists():
            raise FileNotFoundError(f"No KEV catalog at {path}")
        data = json.loads(source.read_text(encoding="utf-8"))
        self.source = source.name
        self.version = data.get("catalogVersion", "unknown")
        self.entries = data["vulnerabilities"]
        self.by_cve = {e["cveID"].upper(): e for e in self.entries}

    def lookup(self, query: str, limit: int = 5) -> dict:
        """Accepts CVE numbers or a vendor or product name, such as 'FortiGate SSL VPN'."""
        cves = find_cves(query)
        if cves:
            matches = [self.by_cve[c] for c in cves if c in self.by_cve]
            missing = [c for c in cves if c not in self.by_cve]
        else:
            matches, missing = self._search_products(query, limit), []
        return {
            "catalog": f"CISA KEV ({self.source}, version {self.version})",
            # "cve" means the exact CVE is in the catalog. "product" means entries for a
            # similar vendor or product, which may or may not apply to this customer.
            "match_type": "cve" if cves else "product",
            "matches": [self._summary(e) for e in matches[:limit]],
            "not_in_catalog": missing,
        }

    def _search_products(self, query: str, limit: int) -> list[dict]:
        terms = set(tokenize(query))
        # Common product names that do not match the vendor's catalog spelling.
        if "fortigate" in terms:
            terms |= {"fortinet", "fortio"}
        scored = []
        for entry in self.entries:
            vendor_product = set(tokenize(f"{entry['vendorProject']} {entry['product']}"))
            if not vendor_product & terms:
                continue
            words = vendor_product | set(tokenize(entry["vulnerabilityName"]))
            words |= set(tokenize(entry.get("shortDescription", "")))
            scored.append((len(words & terms), entry["dateAdded"], entry))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [entry for _, _, entry in scored[:limit]]

    @staticmethod
    def _summary(entry: dict) -> dict:
        keys = ("cveID", "vendorProject", "product", "vulnerabilityName", "dateAdded",
                "requiredAction", "dueDate", "knownRansomwareCampaignUse")
        return {k: entry.get(k, "") for k in keys}
