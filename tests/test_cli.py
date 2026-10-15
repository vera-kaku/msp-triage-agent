import os

from triage_agent.cli import _load_dotenv


def test_dotenv_strips_quotes_comments_and_export(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "DEEPSEEK_API_KEY='sk-single'\n"
        'OPENAI_API_KEY="sk-double"\n'
        "export TRIAGE_MODEL=deepseek-flash  # cheap model\n"
        "ANTHROPIC_API_KEY=\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DEEPSEEK_API_KEY", "old-value-from-shell")
    for key in ("OPENAI_API_KEY", "TRIAGE_MODEL", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(key, raising=False)

    _load_dotenv(env)

    assert os.environ["DEEPSEEK_API_KEY"] == "sk-single"  # .env wins over the shell
    assert os.environ["OPENAI_API_KEY"] == "sk-double"
    assert os.environ["TRIAGE_MODEL"] == "deepseek-flash"
    assert "ANTHROPIC_API_KEY" not in os.environ
