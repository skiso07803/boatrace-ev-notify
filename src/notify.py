# -*- coding: utf-8 -*-
"""Discord Webhook 通知"""
import os
import requests

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")


def send(content: str = "", embeds: list[dict] | None = None) -> bool:
    if not WEBHOOK:
        print("[ERROR] DISCORD_WEBHOOK_URL が未設定です")
        print(content)
        return False
    payload: dict = {}
    if content:
        payload["content"] = content[:1900]
    if embeds:
        payload["embeds"] = embeds[:10]  # Discordの上限
    r = requests.post(WEBHOOK, json=payload, timeout=15)
    if r.status_code >= 300:
        print(f"[ERROR] Discord送信失敗: {r.status_code} {r.text[:200]}")
        return False
    return True


def ev_embed(venue: str, rno: int, res, provisional: bool) -> dict:
    """EVResult 1件をDiscord embedに変換"""
    tag = "⚠️暫定" if provisional else "✅確定版"
    return {
        "title": f"{venue} {rno}R  3連単 {res.label}",
        "description": "\n".join(f"・{x}" for x in res.reasons) or "―",
        "color": 0xE67E22 if provisional else 0x2ECC71,
        "fields": [
            {"name": "EV", "value": f"**{res.ev:.2f}** {tag}", "inline": True},
            {"name": "オッズ", "value": f"{res.odds:.1f}", "inline": True},
            {"name": "モデル確率", "value": f"{res.p_model*100:.1f}%", "inline": True},
        ],
    }
