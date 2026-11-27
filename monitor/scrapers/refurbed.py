"""Refurbed: la pagina modello elenca le varianti come testo, es.
'iPhone 16 Pro nero 256 GB Ottimo 759,81 €'.

Gradi Refurbed -> scala del progetto:
- Ottimo: nessun graffio visibile a 30 cm su scocca e display  -> Eccellente
- Molto buono: micrograffi sul display invisibili a schermo acceso -> Buono (non idoneo)
- Buono: segni d'uso visibili                                     -> Accettabile
- Premium (Come nuovo)                                            -> Premium
Lo scraper legge l'elenco "Confronta le configurazioni suggerite" (prezzo minimo per memoria/grado/colore).
La SIM delle varianti non è indicata: per prudenza vengono confrontate con le soglie "solo eSIM" (le più basse).
Refurbed non dichiara una capacità minima della batteria: lo segnaliamo nelle note.
"""
from __future__ import annotations

import re
import time

from ..config import model_key
from ..debug import dump
from ..normalize import Offer, parse_price, SIM_ESIM

SITE = "Refurbed"
GRADE_MAP = {"premium": "Premium", "ottimo": "Eccellente", "molto buono": "Buono", "buono": "Accettabile", "discreto": "Accettabile"}

ITEM = re.compile(
    r"(?:iPhone (\d{2}) Pro(?! Max)\s+)?([a-zàèéìòù]+)\s+(\d{3,4})\s*GB\s+"
    r"(Premium|Ottimo|Molto buono|Buono|Discreto)\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s*€",
)


def parse_listing(text: str, model: str) -> list[dict]:
    """Varianti della sezione "Confronta le configurazioni suggerite" (es. 'grigio 128 GB Ottimo 725,77 €'),
    senza doppioni (minimo per memoria/grado/colore). Il prefisso 'iPhone 16 Pro' può esserci o no."""
    flat = re.sub(r"\s+", " ", text)
    i = flat.find("configurazioni suggerite")
    if i >= 0:
        j = flat.find("Caratteristiche", i)
        flat = flat[i: j if j > 0 else i + 3000]
    want = re.search(r"iPhone (\d{2}) Pro", model).group(1)
    best: dict[tuple, dict] = {}
    for m in ITEM.finditer(flat):
        if m.group(1) and m.group(1) != want:
            continue
        storage = int(m.group(3))
        color, grade_src, price = m.group(2).strip(), m.group(4), parse_price(m.group(5))
        k = (storage, grade_src.lower(), color)
        if k not in best or price < best[k]["price"]:
            best[k] = {"storage": storage, "color": color, "grade_src": grade_src, "price": price}
    return list(best.values())


HEADER = re.compile(r"iPhone (\d{2}) Pro(?! Max)\s+(\d{3,4}|1)\s*(GB|TB)\s*\|\s*([^|]+?)\s*\|\s*([^|(]+?)\s*\(")
MAIN_PRICE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})\s*€\s*(?:\|\s*)?Nuovo")
COUPON = re.compile(r"Risparmia l'(\d+)% EXTRA sulle serie ([^·]+?) con il codice ([A-Z0-9]+)")


def parse_selected(text: str) -> dict | None:
    """Configurazione selezionata nel configuratore, es.
    'iPhone 16 Pro 128 GB | Dual-SIM (2 x eSIM) | Titanio deserto (4,8/5) ... 695,62 € Nuovo: 1.199,00 €'"""
    flat = re.sub(r"\s+", " ", text)
    h = HEADER.search(flat)
    p = MAIN_PRICE.search(flat, h.end() if h else 0)
    if not h or not p:
        return None
    storage = 1000 if h.group(3) == "TB" else int(h.group(2))
    coupon = None
    c = COUPON.search(flat)
    if c and h.group(1) in c.group(2):
        coupon = {"pct": int(c.group(1)), "code": c.group(3)}
    return {"model_no": h.group(1), "storage": storage, "sim_text": h.group(4), "color": h.group(5).strip(),
            "price": parse_price(p.group(1)), "coupon": coupon}


def _click(page, text: str) -> bool:
    for role in ("radio", "button", "link", "option", "tab"):
        loc = page.get_by_role(role, name=re.compile(rf"^\s*{re.escape(text)}\b", re.I))
        if loc.count():
            try:
                loc.first.click(timeout=4000)
                return True
            except Exception:
                continue
    loc = page.get_by_text(text, exact=True)
    if loc.count():
        try:
            loc.first.click(timeout=4000)
            return True
        except Exception:
            pass
    return False


def scrape(page, cfg: dict) -> tuple[list[Offer], list[dict]]:
    offers, runs = [], []
    for p in cfg["sources"]["refurbed"]["pages"]:
        t0 = time.time()
        try:
            page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            for label in ["Uso ristretto", "Rifiuta", "Rifiuta tutto", "Solo necessari"]:
                b = page.get_by_role("button", name=re.compile(label, re.I))
                if b.count():
                    try:
                        b.first.click(timeout=2000)
                    except Exception:
                        pass
                    break
            got, misses = [], []
            text = page.inner_text("body")
            sel = parse_selected(text)
            coupon = sel["coupon"] if sel else None
            for it in parse_listing(text, p["model"]):
                key = model_key(cfg, p["model"], it["storage"])
                if not key:
                    continue
                note = f"grado Refurbed: {it['grade_src']}; SIM da verificare sulla pagina"
                if coupon:
                    net = round(it["price"] * (1 - coupon["pct"] / 100), 2)
                    note += f"; con codice {coupon['code']} (-{coupon['pct']}%): {net:.2f} €"
                got.append(Offer(
                    site=SITE, model=key, storage=it["storage"], sim=SIM_ESIM, color=it["color"].capitalize(),
                    grade=GRADE_MAP[it["grade_src"].lower()], price=it["price"], seller="Refurbed",
                    price_source="elenco", battery="non dichiarata", url=p["url"], notes=note,
                ))
            if not got:
                dump(page, f"refurbed {p['model']}", 8000)
            offers += got
            runs.append(dict(site=SITE, target=p["model"], status="ok" if got else "vuoto", n=len(got),
                             error=("non trovati: " + ", ".join(misses))[:200] if misses else "",
                             secs=round(time.time() - t0)))
        except Exception as e:  # noqa: BLE001
            runs.append(dict(site=SITE, target=p["model"], status="errore", n=0, error=str(e)[:200],
                             secs=round(time.time() - t0)))
    return offers, runs
