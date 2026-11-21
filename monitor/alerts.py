"""Avvisi per offerte sotto soglia: issue GitHub (email/app) e Telegram opzionale."""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import requests

from .config import DATA, model_info
from .normalize import SIM_LABEL
from .rules import matching_threshold

STATE = DATA / "alert_state.json"


def _key(o) -> str:
    return f"{o.site}|{o.model}|{o.sim}|{o.grade}|{o.color}|{o.seller}"


def select_new_hits(offers, cfg, now: datetime, state: dict) -> list:
    a = cfg["alerts"]
    hits = []
    for o in offers:
        t = matching_threshold(o, cfg)
        if not t:
            continue
        prev = state.get(_key(o))
        if prev:
            when = datetime.fromisoformat(prev["ts"])
            recent = now - when < timedelta(hours=a["repeat_after_hours"])
            if recent and o.price > prev["price"] - a["repeat_if_drop_eur"]:
                continue
        hits.append((o, t))
    hits.sort(key=lambda h: h[0].price)
    return hits


def format_hits(hits, cfg) -> tuple[str, str]:
    best = hits[0][0]
    title = f"Offerta: {model_info(cfg, best.model)['label']} {best.grade} {SIM_LABEL[best.sim]} a {best.price:.2f} € ({best.site})"
    lines = ["| Modello | Grado | SIM | Colore | Prezzo | Soglia | Venditore | Sito |", "|---|---|---|---|---|---|---|---|"]
    for o, t in hits:
        lines.append(
            f"| {model_info(cfg, o.model)['label']} | {o.grade} | {SIM_LABEL[o.sim]} | {o.color or '-'} | "
            f"**{o.price:.2f} €** | {t['op']} {t['price']} € | {o.seller or '-'} | [{o.site}]({o.url}) |"
        )
    note = []
    if any(o.price_source == "selettore" for o, _ in hits):
        note.append("I prezzi «selettore» di Back Market vanno confermati cliccando la variante.")
    body = "\n".join(lines) + "\n\n" + " ".join(note) + "\n\nVerifica sempre condizioni, batteria e garanzia sulla pagina prima di acquistare."
    return title, body


def send(hits, cfg, now: datetime) -> list[str]:
    if not hits:
        return []
    title, body = format_hits(hits, cfg)
    done = []
    repo, token = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if cfg["alerts"].get("github_issue") and repo and token:
        h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        r = requests.post(f"https://api.github.com/repos/{repo}/issues", headers=h, timeout=20,
                          json={"title": title, "body": body, "labels": ["offerta"]})
        done.append(f"issue {r.status_code}")
    bot, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if cfg["alerts"].get("telegram") and bot and chat:
        text = title + "\n\n" + "\n".join(
            f"• {model_info(cfg, o.model)['label']} {o.grade} {SIM_LABEL[o.sim]} {o.color} — {o.price:.2f} € — {o.seller} ({o.site})\n{o.url}"
            for o, _ in hits[:8])
        r = requests.post(f"https://api.telegram.org/bot{bot}/sendMessage", timeout=20,
                          json={"chat_id": chat, "text": text, "disable_web_page_preview": True})
        done.append(f"telegram {r.status_code}")
    return done


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict, hits, now: datetime):
    for o, _ in hits:
        state[_key(o)] = {"ts": now.isoformat(), "price": o.price}
    cutoff = now - timedelta(days=14)
    state = {k: v for k, v in state.items() if datetime.fromisoformat(v["ts"]) > cutoff}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=1, ensure_ascii=False))
