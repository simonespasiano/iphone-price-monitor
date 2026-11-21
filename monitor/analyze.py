"""Report da terminale sullo storico.

  python -m monitor.analyze                      # riepilogo di tutti i modelli
  python -m monitor.analyze --model 16pro-128    # un modello
  python -m monitor.analyze --model 16pro-128 --hour 2026-11-21T20   # tutte le offerte di quell'ora (UTC)
"""
from __future__ import annotations

import argparse

from .analytics import model_stats, threshold_hits
from .config import load_config, model_info
from .normalize import SIM_LABEL
from .storage import read_all


def eur(v):
    return "-" if v is None else f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--hour", help="prefisso timestamp UTC, es. 2026-11-21T20")
    ap.add_argument("--all", action="store_true", help="con --hour mostra anche offerte non idonee")
    a = ap.parse_args(argv)
    cfg = load_config()
    rows = read_all("offers")
    if not rows:
        print("Nessun dato ancora raccolto.")
        return
    models = [a.model] if a.model else [m["key"] for m in cfg["models"]]

    if a.hour:
        sel = [r for r in rows if r["ts"].startswith(a.hour) and r["model"] in models and (a.all or r["eligible"] == "1")]
        sel.sort(key=lambda r: float(r["price"]))
        print(f"{len(sel)} offerte alle {a.hour} UTC")
        for r in sel:
            print(f"{eur(float(r['price'])):>11}  {r['model']:<10} {r['grade']:<11} {SIM_LABEL.get(r['sim'], r['sim']):<20} "
                  f"{r['color']:<18} {r['site']:<12} {r['seller'][:24]:<24} {r['price_source']}")
        return

    for key in models:
        st = model_stats(rows, cfg, key)
        print(f"\n=== {model_info(cfg, key)['label']} ===")
        for f in st["filters"]:
            c = f["current"]
            th = f["threshold"]
            print(f"  [{f['label']}] ora {eur(c['price'])} ({c['site']}, {c['color']}, {c['seller']})"
                  + (f" | soglia {th['op']} {th['price']} € (distanza {eur(f['gap_to_threshold'])})" if th else ""))
            print(f"     24h min {eur(f['min_24h'])} media {eur(f['avg_24h'])} | 7g min {eur(f['min_7d'])} media {eur(f['avg_7d'])}"
                  f" | storico min {eur(f['min_all'])} su {f['hours']} ore"
                  + (f" | ore sotto soglia {f['hours_under_threshold']}" if th else ""))
            print(f"     sito più conveniente: " + ", ".join(f"{s} {p}%" for s, p in f["best_site_share"].items())
                  + (f" | ora del giorno mediamente più bassa: {f['cheapest_hour']}:00" if f["cheapest_hour"] is not None else ""))
    hits = threshold_hits(rows, cfg)
    print(f"\nOfferte sotto soglia nello storico: {len(hits)}")
    for h in sorted(hits, key=lambda h: h["ts"], reverse=True)[:10]:
        print(f"  {h['ts']} {h['model']} {h['grade']} {SIM_LABEL.get(h['sim'])} {eur(float(h['price']))} {h['site']} {h['seller']}")


if __name__ == "__main__":
    main()
