"""Gửi tóm tắt qua Telegram (chỉ khi có biến môi trường và dùng cờ --telegram)."""
import os

import requests


def send_summary(text: str, dry_run: bool = False) -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return "Bỏ qua Telegram: thiếu TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID."
    if dry_run:
        return "Telegram (dry-run, không gửi):\n" + text
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=15)
    return "Đã gửi Telegram." if r.ok else f"Gửi Telegram lỗi: {r.status_code}"
