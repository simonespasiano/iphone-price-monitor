"""Invia su Telegram un riepilogo di esempio costruito sull'ultima verifica salvata in data/.

Uso:  python -m monitor.telegram_sample          (invia)
      python -m monitor.telegram_sample --print  (mostra soltanto il testo)
"""
from __future__ import annotations

import sys

from . import telegram
from .config import load_config
from .normalize import Offer
from .storage import read_all


def last_run():
    offers, runs = read_all("offers"), read_all("runs")
    if not runs:
        return [], [], ""
    ts = max(r["ts"] for r in runs)
    o = []
    for r in offers:
        if r["ts"] != ts:
            continue
        x = Offer(site=r["site"], model=r["model"], storage=int(r["storage"] or 0), sim=r["sim"],
                  color=r["color"], grade=r["grade"], price=float(r["price"]), seller=r["seller"],
                  price_source=r["price_source"], url=r["url"])
        x.eligible = r["eligible"] in ("1", "True", "true")
        o.append(x)
    return o, [r for r in runs if r["ts"] == ts], ts


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = load_config()
    offers, runs, ts = last_run()
    text = "🧪 ESEMPIO con i dati dell'ultima verifica salvata\n\n" + telegram.build_report(offers, runs, [], cfg)
    if "--print" in argv:
        print(text)
        return 0
    res = telegram.send_text(text)
    print(res)
    return 0 if res == "telegram 200" else 1


if __name__ == "__main__":
    sys.exit(main())
