"""Telegram delivery. Setup (one-time, ~3 min):
  1. Message @BotFather -> /newbot -> copy the token
  2. Message your new bot once (any text), then open
     https://api.telegram.org/bot<TOKEN>/getUpdates and copy chat.id
  3. Store both as env vars / GitHub Secrets:
     TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
"""
from __future__ import annotations

import os

import httpx

from scrapers.base import Offer


def format_message(grouped: dict[str, list[Offer]], total_cost: float,
                   baseline: tuple[str, float] | None,
                   missing: list[str]) -> str:
    lines = ["🛒 <b>Dzisiejszy plan zakupów</b>\n"]
    for store, items in sorted(grouped.items()):
        lines.append(f"📍 <b>{store}</b>")
        for o in sorted(items, key=lambda x: x.product_name):
            promo = " 🔥" if o.is_promo else ""
            up = f" ({o.unit_price} zł/{o.unit})" if o.unit_price else ""
            lines.append(f"  • {o.product_name} — <b>{o.price:.2f} zł</b>{up}{promo}")
        lines.append("")
    lines.append(f"💰 Razem: <b>{total_cost:.2f} zł</b>")
    if baseline:
        store, cost = baseline
        saved = round(cost - total_cost, 2)
        if saved > 0:
            lines.append(f"📊 Oszczędność vs {store}: <b>{saved:.2f} zł</b>")
    if missing:
        lines.append(f"\n⚠️ Brak danych dziś: {', '.join(missing)}")
    return "\n".join(lines)


def send(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    r = httpx.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=20,
    )
    r.raise_for_status()
