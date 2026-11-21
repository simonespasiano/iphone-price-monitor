"""Esegue un controllo completo: scraping dei siti, salvataggio storico, avvisi, rigenerazione dashboard.

Uso:  python -m monitor.run [--sites amazon,backmarket,trendevice] [--no-alerts] [--headed]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from .alerts import load_state, save_state, select_new_hits, send
from .build_site import build
from . import telegram
from .debug import reset as reset_debug
from .config import load_config
from .rules import is_eligible
from .storage import save
from .scrapers import amazon, backmarket, trendevice

SCRAPERS = {"amazon": amazon, "backmarket": backmarket, "trendevice": trendevice}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sites", default=",".join(SCRAPERS))
    ap.add_argument("--no-alerts", action="store_true")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args(argv)

    from playwright.sync_api import sync_playwright

    cfg = load_config()
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    offers, runs = [], []
    reset_debug()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed, args=["--disable-blink-features=AutomationControlled"])
        for name in args.sites.split(","):
            if not cfg["sources"].get(name, {}).get("enabled"):
                continue
            ctx = browser.new_context(locale="it-IT", timezone_id="Europe/Rome", user_agent=UA,
                                      viewport={"width": 1366, "height": 900},
                                      extra_http_headers={"Accept-Language": "it-IT,it;q=0.9,en;q=0.6"})
            page = ctx.new_page()
            try:
                o, r = SCRAPERS[name].scrape(page, cfg)
            except Exception as e:  # noqa: BLE001
                o, r = [], [dict(site=name, target="*", status="errore", n=0, error=str(e)[:200], secs=0)]
            offers += o
            runs += r
            ctx.close()
            print(f"[{name}] {len(o)} offerte, esiti: " + ", ".join(f"{x['target']}={x['status']}" for x in r), flush=True)
        browser.close()

    for o in offers:
        ok, why = is_eligible(o, cfg)
        o.eligible = ok
        if why:
            o.notes = (o.notes + "; " if o.notes else "") + "non idonea: " + why
    save(ts, offers, runs)

    if not args.no_alerts:
        state = load_state()
        hits = select_new_hits(offers, cfg, now, state)
        sent = send(hits, cfg, now) if hits else []
        print("avvisi:", sent or ("nessuna offerta sotto soglia" if not hits else "nessun canale configurato"))
        if cfg["alerts"].get("telegram_every_run") and telegram.enabled(cfg):
            print("riepilogo:", telegram.send_text(telegram.build_report(offers, runs, hits, cfg)))
        # lo stato anti-ripetizione si aggiorna solo se l'avviso è partito davvero
        save_state(state, hits if any(x.split()[-1].startswith("2") for x in sent) else [], now)

    build(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
