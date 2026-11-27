"""Refurbed: la pagina modello elenca le varianti come testo, es.
'iPhone 16 Pro nero 256 GB Ottimo 759,81 €'.

Gradi Refurbed -> scala del progetto:
- Ottimo: nessun graffio visibile a 30 cm su scocca e display  -> Eccellente
- Molto buono: micrograffi sul display invisibili a schermo acceso -> Buono (non idoneo)
- Buono: segni d'uso visibili                                     -> Accettabile
Refurbed non dichiara una capacità minima della batteria: lo segnaliamo nelle note.
"""
from __future__ import annotations

import re
import time

from ..config import model_key
from ..debug import dump
from ..normalize import Offer, parse_price, SIM_FISICA

SITE = "Refurbed"
GRADE_MAP = {"ottimo": "Eccellente", "molto buono": "Buono", "buono": "Accettabile", "discreto": "Accettabile"}

ITEM = re.compile(
    r"iPhone (\d{2}) Pro(?! Max)\s+([a-zàèéìòù]+(?: [a-zàèéìòù]+)?)\s+(\d{3,4}|1)\s*(GB|TB)\s+"
    r"(Ottimo|Molto buono|Buono|Discreto)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*€",
)


def parse_listing(text: str, model: str) -> list[dict]:
    """Restituisce le varianti del modello richiesto, senza doppioni (minimo per memoria/grado/colore)."""
    flat = re.sub(r"\s+", " ", text)
    want = re.search(r"iPhone (\d{2}) Pro", model).group(1)
    best: dict[tuple, dict] = {}
    for m in ITEM.finditer(flat):
        if m.group(1) != want:
            continue
        storage = 1000 if m.group(4) == "TB" else int(m.group(3))
        color = m.group(2).strip()
        grade_src = m.group(5)
        price = parse_price(m.group(6))
        k = (storage, grade_src.lower(), color)
        if k not in best or price < best[k]["price"]:
            best[k] = {"storage": storage, "color": color, "grade_src": grade_src, "price": price}
    return list(best.values())


def scrape(page, cfg: dict) -> tuple[list[Offer], list[dict]]:
    offers, runs = [], []
    for p in cfg["sources"]["refurbed"]["pages"]:
        t0 = time.time()
        try:
            page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            for label in ["Rifiuta", "Rifiuta tutto", "Solo necessari", "Accetta solo"]:
                b = page.get_by_role("button", name=re.compile(label, re.I))
                if b.count():
                    try:
                        b.first.click(timeout=2000)
                    except Exception:
                        pass
                    break
            for _ in range(3):
                page.mouse.wheel(0, 3000)
                page.wait_for_timeout(600)
            items = parse_listing(page.inner_text("body"), p["model"])
            got = []
            for it in items:
                key = model_key(cfg, p["model"], it["storage"])
                if not key:
                    continue
                got.append(Offer(
                    site=SITE, model=key, storage=it["storage"], sim=SIM_FISICA, color=it["color"].capitalize(),
                    grade=GRADE_MAP[it["grade_src"].lower()], price=it["price"], seller="Refurbed",
                    price_source="elenco", battery="non dichiarata", url=p["url"],
                    notes=f"grado Refurbed: {it['grade_src']}; SIM da verificare (di solito Nano-SIM + eSIM)",
                ))
            if not got:
                dump(page, f"refurbed {p['model']}", 1500)
            offers += got
            runs.append(dict(site=SITE, target=p["model"], status="ok" if got else "vuoto", n=len(got), error="",
                             secs=round(time.time() - t0)))
        except Exception as e:  # noqa: BLE001
            runs.append(dict(site=SITE, target=p["model"], status="errore", n=0, error=str(e)[:200],
                             secs=round(time.time() - t0)))
    return offers, runs
