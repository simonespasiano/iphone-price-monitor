"""Telegram: invio messaggi, riepilogo di ogni verifica e messaggio di prova.

Test manuale:  python -m monitor.telegram   (richiede TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID)
"""
from __future__ import annotations

import html
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


def send_text(text: str, as_html: bool = False) -> str:
    """Invia un messaggio (testo semplice o HTML di Telegram). Restituisce 'telegram <codice HTTP>'."""
    bot, chat = credentials()
    payload = {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}
    if as_html:
        payload["parse_mode"] = "HTML"
    r = requests.post(API.format(token=bot, method="sendMessage"), timeout=20, json=payload)
    if r.status_code != 200:
        print(f"telegram errore {r.status_code}: {r.text[:300]}", flush=True)
    return f"telegram {r.status_code}"


GIORNI = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]


def esc(x) -> str:
    return html.escape(str(x or ""), quote=True)


def link(url: str, label: str = "apri offerta") -> str:
    return f'<a href="{esc(url)}">{label}</a>' if url else ""


def eur(x: float) -> str:
    return f"{x:.0f} €" if abs(x - round(x)) < 0.005 else f"{x:.2f} €".replace(".", ",")


def _site_status(runs: list[dict]) -> str:
    by_site: dict[str, list[dict]] = {}
    for r in runs:
        by_site.setdefault(r["site"], []).append(r)
    parts = []
    for site, rs in by_site.items():
        ok = sum(1 for r in rs if r["status"] == "ok")
        if ok == len(rs):
            parts.append(f"✅ {esc(site)}")
        elif ok == 0:
            why = rs[0].get("error") or rs[0].get("status") or "errore"
            parts.append(f"⛔ {esc(site)} non letto ({esc(why)})")
        else:
            parts.append(f"⚠️ {esc(site)} letto in parte ({ok} pagine su {len(rs)})")
    return "\n".join(parts) or "nessun sito controllato"


def _variant(t: dict) -> str:
    if t["grade"] == "premium":
        return "Premium" + ("" if t["sim"] == "any" else f", {SIM_RULE_LABEL[t['sim']]}")
    return "" if t["sim"] == "any" else SIM_RULE_LABEL.get(t["sim"], t["sim"])


def build_report(offers, runs, hits, cfg) -> str:
    """Riepilogo di una verifica: esito, prezzi per modello rispetto all'obiettivo, stato dei siti."""
    from .rules import sim_matches

    now = datetime.now(ZoneInfo(cfg.get("timezone", "Europe/Rome")))
    rows, under_count = [], 0
    for t in cfg["thresholds"]:
        cands = [o for o in offers if o.eligible and o.model == t["model"]
                 and sim_matches(t["sim"], o.sim) and o.grade_rank >= grade_rank(t["grade"])]
        best = min(cands, key=lambda o: o.price) if cands else None
        under = bool(best) and (best.price < t["price"] if t["op"] == "<" else best.price <= t["price"])
        under_count += under
        rows.append((t, best, under))

    lines = [f"📱 <b>Monitor iPhone</b> · {GIORNI[now.weekday()]} {now:%d/%m} ore {now:%H:%M}"]
    if hits:
        lines.append(f"🔥 {len(hits)} OFFERTE NUOVE SOTTO L'OBIETTIVO: link nel messaggio qui sotto")
    elif under_count:
        lines.append("🔥 Prezzi sotto l'obiettivo (già segnalati)")
    else:
        lines.append("😴 Nessuna offerta sotto l'obiettivo")
    lines.append("")

    for m in cfg["models"]:
        mine = [r for r in rows if r[0]["model"] == m["key"]]
        if not mine:
            continue
        lines.append(f"<b>{esc(m['label'])}</b>")
        for t, best, under in mine:
            v = _variant(t)
            head = f"{'🔥' if under else '•'} {v + ': ' if v else ''}"
            if not best:
                lines.append(f"{head}nessuna offerta · obiettivo {eur(t['price'])}")
                continue
            diff = best.price - t["price"]
            gap = f"{eur(-diff)} sotto ✅" if diff <= 0 else f"mancano {eur(diff)}"
            lines.append(f"{head}<b>{eur(best.price)}</b> su {esc(best.site)} · obiettivo {eur(t['price'])} · {gap}"
                         + (f" · 👉 {link(best.url)}" if best.url else ""))
        lines.append("")

    lines.append("Siti controllati:")
    lines.append(_site_status(runs))
    lines.append("")
    lines.append("Prezzi minimi in grado Eccellente o superiore, garanzia 12 mesi.")
    return "\n".join(lines)


def format_hits(hits, cfg, title: str = "") -> str:
    out = ["🔥 <b>OFFERTA SOTTO L'OBIETTIVO</b>" if len(hits) == 1 else f"🔥 <b>{len(hits)} OFFERTE SOTTO L'OBIETTIVO</b>"]
    for o, t in hits[:8]:
        details = " · ".join(x for x in (o.grade, o.color, o.seller) if x)
        out += ["",
                f"<b>{esc(model_info(cfg, o.model)['label'])} · {esc(SIM_LABEL[o.sim])}</b>",
                f"💶 <b>{eur(o.price)}</b> su {esc(o.site)} (obiettivo {eur(t['price'])}, {eur(t['price'] - o.price)} in meno)",
                esc(details),
                f"👉 {link(o.url, 'Apri l’offerta')}"]
    out += ["", "Prima di comprare controlla batteria, condizioni e garanzia sulla pagina."]
    return "\n".join(out)


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
