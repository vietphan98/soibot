import pytest

from soibot import data, synthetic
from soibot.cli import main
from soibot.telegram import send_summary


def test_telegram_dry_run_without_env(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    out = send_summary("xin chào", dry_run=True)
    assert "dry-run" in out and "xin chào" in out


def test_telegram_missing_env_does_not_send(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert send_summary("x").startswith("Bỏ qua Telegram")


def test_synthetic_is_deterministic_and_labelled():
    a = synthetic.prices("GL01")
    synthetic.universe.cache_clear()
    b = synthetic.prices("GL01")
    assert a.equals(b) and "GIẢ LẬP" in synthetic.LABEL
    with pytest.raises(KeyError):
        synthetic.prices("FPT")


def test_yahoo_rejects_index_clearly():
    with pytest.raises(ValueError, match="không có lịch sử chỉ số"):
        data._yahoo("VNINDEX", "2025-01-01", "2025-02-01")


def test_cli_demo_on_synthetic_triggers_warning(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setenv("SOIBOT_CACHE", str(tmp_path))
    rep = main(["samples/bot_may_man.csv", "--hold", "15", "--source", "gialap",
                "--html", str(tmp_path / "r.html"), "--telegram-dry-run"])
    out = capsys.readouterr().out
    assert rep.warnings and rep.warnings[0].startswith("⚠")
    assert "DỮ LIỆU GIẢ LẬP" in out and "dry-run" in out
    assert "DỮ LIỆU GIẢ LẬP" in (tmp_path / "r.html").read_text(encoding="utf-8")
