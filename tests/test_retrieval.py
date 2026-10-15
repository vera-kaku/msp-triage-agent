from triage_agent.kev import KevCatalog, find_cves
from triage_agent.knowledge import KnowledgeBase, TicketHistory
from triage_agent.redact import redact
from triage_agent.search import BM25Index, tokenize


def test_stemming_matches_word_forms():
    assert tokenize("printers printing synced") == tokenize("printer print syncing")


def test_bm25_ranks_relevant_document_first():
    index = BM25Index()
    index.add("a", "printer offline paper jam toner")
    index.add("b", "vpn will not connect from home")
    assert index.search("printers are offline")[0][0] == "a"
    assert index.search("nothing relevant here zebra") == []


def test_kb_finds_expected_articles(config):
    kb = KnowledgeBase(config.path("kb_dir"))
    assert len(kb.articles) == 20
    assert kb.search("forgot my password")[0]["id"] == "KB-001"
    assert kb.search("onedrive red cross not syncing")[0]["id"] == "KB-006"
    assert kb.search("clicked a link and entered my password")[0]["id"] == "KB-011"


def test_history_search(config):
    history = TicketHistory(config.path("history"))
    assert history.search("whole office no internet")[0]["id"] == "H-103"


def test_kev_exact_cve_and_missing(config):
    kev = KevCatalog(config.path("kev"), config.path("kev_fallback"))
    result = kev.lookup("CVE-2021-44228 and cve-2020-00001")
    assert result["match_type"] == "cve"
    assert [m["cveID"] for m in result["matches"]] == ["CVE-2021-44228"]
    assert result["not_in_catalog"] == ["CVE-2020-00001"]


def test_kev_product_search_maps_fortigate(config):
    kev = KevCatalog(config.path("kev"), config.path("kev_fallback"))
    result = kev.lookup("FortiGate SSL VPN")
    assert result["match_type"] == "product"
    assert result["matches"][0]["cveID"] == "CVE-2024-21762"


def test_find_cves():
    assert find_cves("see cve-2023-4966, CVE-2023-4966 and CVE-2021-44228") == [
        "CVE-2021-44228", "CVE-2023-4966"]


def test_redact_emails_phones_and_secrets():
    text = ("Email mere.tane@harbourlaw.co.nz or call 021 555 0142 or +64 21 987 6543. "
            "My password: Summer2026! Allow 203.0.113.0/24 on FILESRV01.")
    cleaned, counts = redact(text)
    assert "harbourlaw" not in cleaned and "555 0142" not in cleaned and "Summer" not in cleaned
    assert counts == {"[EMAIL]": 1, "[PHONE]": 2, "[SECRET]": 1}
    assert "203.0.113.0/24" in cleaned and "FILESRV01" in cleaned


def test_redact_keeps_cve_numbers():
    text = "CVE-2023-4966, cve-2021-44228 and CVE-2024-21762"
    assert redact(text) == (text, {})


def test_redact_leaves_ordinary_password_sentences():
    cleaned, counts = redact("It says my password is expired.")
    assert cleaned == "It says my password is expired." and counts == {}
