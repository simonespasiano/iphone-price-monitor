"""TrenDevice: pagina elenco modello (gradi A Eccellente e A+ Come nuovo)."""
from __future__ import annotations

import re
import time

from ..config import model_key
from ..debug import dump
from ..normalize import Offer, parse_price, sim_from_text, norm_color

SITE = "TrenDevice"


PRICE_ALL = re.compile(r"€\s?(\d{1,3}(?:\.\d{3})*,\d{2})")
GRADE_FIND = re.compile(r"(?:^|[\s|])(A\+ Come nuovo|A Eccellente|B Buono|C Smart|A\+|A|B|C)(?=$|[\s|])")


def parse_listing(text: str, model: str) -> list[dict]:
    """Schede elenco. Funziona sia con un campo per riga sia con campi separati da ' | '.
    Es.: 'iPhone 15 Pro | 128 GB | Titanio blu | A Eccellente | Sim Card (include slot sim) | A partire da | €669,00 | €619,00'"""
    flat = re.sub(r"[ \t]*\n[ \t]*", " | ", text)
    flat = re.sub(r"(\s*\|\s*)+", " | ", flat)
    starts = [m for m in re.finditer(re.escape(model) + r"(?! Max| Plus)\s*\|?\s*(\d+)\s*(GB|TB)\b", flat)]
    items = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else m.end() + 400
        chunk = flat[m.end():end]
        cut = re.search(r"\|\s*(Promo|Risparmia|TrenDevice Club|Vendi il tuo usato)\b", chunk)
        if cut:
            chunk = chunk[:cut.start()]
        toks = [t.strip() for t in chunk.split("|") if t.strip()]
        storage = int(m.group(1)) * (1000 if m.group(2) == "TB" else 1)
        it = {"storage": storage, "color": "", "sim": "", "grade": "", "prices": [], "preorder": False}
        for tok in toks:
            low = tok.lower()
            prices = [parse_price(p) for p in PRICE_ALL.findall(tok)]
            if prices:
                it["prices"] += prices
                continue
            if low in ("a partire da", "da"):
                continue
            if "preordina" in low:
                it["preorder"] = True
                continue
            if "sim" in low:
                it["sim"] = tok
                continue
            g = GRADE_FIND.search(tok)
            if g and len(tok) <= 16 and not it["grade"]:
                it["grade"] = g.group(1)
                continue
            if not it["color"] and not it["prices"] and len(tok) < 40:
                it["color"] = tok
        if it["prices"] and it["grade"]:
            items.append(it)
    return items


def scrape(page, cfg: dict) -> tuple[list[Offer], list[dict]]:
    offers, runs = [], []
    for p in cfg["sources"]["trendevice"]["pages"]:
        t0 = time.time()
        try:
            page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            for label in ["Rifiuta", "Rifiuta tutto", "Solo necessari"]:
                b = page.get_by_role("button", name=re.compile(label, re.I))
                if b.count():
                    try:
                        b.first.click(timeout=2000)
                    except Exception:
                        pass
                    break
            # carica eventuali schede pigre
            for _ in range(4):
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(700)
            items = parse_listing(page.inner_text("body"), p["model"])
            got = []
            for it in items:
                key = model_key(cfg, p["model"], it["storage"])
                if not key:
                    continue
                color = "Colore a sorpresa" if "sorpresa" in it["color"].lower() else norm_color(it["color"])
                got.append(Offer(
                    site=SITE, model=key, storage=it["storage"], sim=sim_from_text(it["sim"]), color=color,
                    grade=it["grade"], price=min(it["prices"]), seller="TrenDevice", price_source="elenco",
                    battery="", url=p["url"], notes="preordine" if it["preorder"] else "",
                ))
            if not got:
                dump(page, f"trendevice {p['model']}", 1500)
            offers += got
            runs.append(dict(site=SITE, target=p["model"], status="ok" if got else "vuoto", n=len(got), error="", secs=round(time.time() - t0)))
        except Exception as e:  # noqa: BLE001
            runs.append(dict(site=SITE, target=p["model"], status="errore", n=0, error=str(e)[:200], secs=round(time.time() - t0)))
    return offers, runs
