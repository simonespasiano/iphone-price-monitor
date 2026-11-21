"""Telegram: invio messaggi, riepilogo di ogni verifica e messaggio di prova.

Test manuale:  python -m monitor.telegram   (richiede TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID)
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from .config import model_info
from .normalize import SIM_LABEL, grade_rank

API = "https://api.telegram.org/bot{token}/{method}"
SIM_RULE_LABEL = {"esim": "solo eSIM", "fisica": "SIM fisica", "any": "qualsiasi SIM"}
GRADE_RULE_LABEL = {"eccellente": "Eccellente+", "premium": "Premium"}


def credentials() -> tuple[str | None, str | None]:
    return os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")


def enabled(cfg: dict) -> bool:
    bot, chat = credentials()
    return bool(cfg["alerts"].get("telegram") and bot and chat)


def send_text(text: str) -> str:
    """Invia un messaggio di testo semplice. Restituisce 'telegram <codice HTTP>'."""
    bot, chat = credentials()
    r = requests.post(API.format(token=bot, method="sendMessage"), timeout=20,
                      json={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True})
    if r.status_code != 200:
        print(f"telegram errore {r.status_code}: {r.text[:300]}", flush=True)
    return f"telegram {r.status_code}"


def _site_status(runs: list[dict]) -> str:
    by_site: dict[str, list[dict]] = {}
    for r in runs:
        by_site.setdefault(r["site"], []).append(r)
    parts = []
    for site, rs in by_site.items():
        ok = sum(1 for r in rs if r["status"] == "ok")
        if ok == len(rs):
            parts.append(f"{site} ✅")
        elif ok == 0:
            why = rs[0].get("status") or "errore"
            parts.append(f"{site} ⛔ {why}")
        else:
            parts.append(f"{site} ⚠️ {ok}/{len(rs)}")
    return " · ".join(parts) or "nessun sito controllato"


def build_report(offers, runs, hits, cfg) -> str:
    """Riepilogo di una verifica: stato dei siti e miglior prezzo per ciascuna soglia."""
    from .rules import sim_matches

    now = datetime.now(ZoneInfo(cfg.get("timezone", "Europe/Rome")))
    lines = [f"📊 Verifica del {now:%d/%m alle %H:%M}", _site_status(runs), ""]
    lines.append("Miglior prezzo idoneo per soglia:")
    for t in cfg["thresholds"]:
        cands = [o for o in offers if o.eligible and o.model == t["model"]
                 and sim_matches(t["sim"], o.sim) and o.grade_rank >= grade_rank(t["grade"])]
        label = (f"{model_info(cfg, t['model'])['label'].replace('iPhone ', '')} "
                 f"{SIM_RULE_LABEL.get(t['sim'], t['sim'])} {GRADE_RULE_LABEL.get(t['grade'], t['grade'])}")
        target = f"soglia {'≤' if t['op'] == '<=' else '<'} {t['price']} €"
        if not cands:
            lines.append(f"▫️ {label}: nessuna offerta ({target})")
            continue
        best = min(cands, key=lambda o: o.price)
        under = best.price < t["price"] if t["op"] == "<" else best.price <= t["price"]
        mark = "🔥" if under else "▫️"
        lines.append(f"{mark} {label}: {best.price:.0f} € {best.site} ({target})")
    lines.append("")
    if hits:
        lines.append(f"🔥 {len(hits)} offerte nuove sotto soglia: dettagli e link nel messaggio di avviso.")
    else:
        lines.append("Nessuna nuova offerta sotto soglia.")
    lines.append(f"Offerte lette: {len(offers)}, idonee: {sum(1 for o in offers if o.eligible)}")
    return "\n".join(lines)


def format_hits(hits, cfg, title: str) -> str:
    return "🔥 " + title + "\n\n" + "\n".join(
        f"• {model_info(cfg, o.model)['label']} {o.grade} {SIM_LABEL[o.sim]} {o.color} — "
        f"{o.price:.2f} € — {o.seller} ({o.site})\n{o.url}"
        for o, _ in hits[:8])


def test() -> int:
    """Verifica token e chat ID e invia un messaggio di prova."""
    bot, chat = credentials()
    if not bot or not chat:
        print("❌ Mancano i secret: " + ", ".join(
            n for n, v in (("TELEGRAM_BOT_TOKEN", bot), ("TELEGRAM_CHAT_ID", chat)) if not v))
        print("Aggiungili in Settings → Secrets and variables → Actions.")
        return 1
    me = requests.get(API.format(token=bot, method="getMe"), timeout=20)
    if me.status_code != 200:
        print(f"❌ Token non valido (HTTP {me.status_code}). Rigenera il token con @BotFather e aggiorna il secret.")
        return 1
    name = me.json()["result"].get("username", "?")
    print(f"✅ Token valido: bot @{name}")
    now = datetime.now(ZoneInfo("Europe/Rome"))
    res = send_text(f"✅ Test riuscito: il monitor prezzi iPhone può scriverti qui.\n"
                    f"Bot @{name}, {now:%d/%m/%Y %H:%M}.\n"
                    f"Da ora riceverai un riepilogo a ogni verifica oraria.")
    if res != "telegram 200":
        print("❌ Invio fallito: controlla il chat ID e di aver premuto «Avvia» nella chat con il bot.")
        return 1
    print("✅ Messaggio di prova inviato. Controlla Telegram.")
    return 0


if __name__ == "__main__":
    sys.exit(test())
