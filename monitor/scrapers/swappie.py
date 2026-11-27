"""Swappie: pagina modello con selettori Capacità e Condizione.

Lo scraper clicca memoria e condizione e legge il riepilogo mostrato, es.
'128 GB | Titanio naturale | Eccellente ... € 689 | € 715 | Prezzo di lancio Apple: € 1 239'.
Gradi: Buono < Molto buono < Eccellente < Premium. Batteria standard ≥ 86% (Premium ≥ 95%).
"""
from __future__ import annotations

import re
import time

from ..config import model_key
from ..debug import dump
from ..normalize import Offer, parse_price, SIM_FISICA

SITE = "Swappie"

SUMMARY = re.compile(r"(\d{3,4}|1)\s*(GB|TB)\s*\|\s*([^|]{3,30}?)\s*\|\s*(Buono|Molto buono|Eccellente|Premium)\b")
PRICE = re.compile(r"€\s?(\d{1,3}(?:[ .  ]\d{3})*(?:,\d{2})?)")


def flatten(text: str) -> str:
    flat = re.sub(r"[ \t]*\n[ \t]*", " | ", text)
    return re.sub(r"(\s*\|\s*)+", " | ", flat)


def parse_selected(text: str) -> dict | None:
    """Configurazione mostrata e suo prezzo; None se non disponibile o non leggibile."""
    flat = flatten(text)
    if re.search(r"non è più disponibile|esaurit", flat, re.I):
        return None
    m = SUMMARY.search(flat)
    if not m:
        return None
    end = flat.find("Prezzo di lancio", m.end())
    window = flat[m.end(): end if end > 0 else m.end() + 300]
    prices = [parse_price(p) for p in PRICE.findall(window)]
    prices = [p for p in prices if p and p > 100]
    if not prices:
        return None
    storage = 1000 if m.group(2) == "TB" else int(m.group(1))
    return {"storage": storage, "color": m.group(3).strip(), "grade": m.group(4), "price": prices[0]}


DELTA = re.compile(r"(Buono|Molto buono|Eccellente|Premium)(?:\s*\+\s*€\s?(\d{1,3}(?:[ .\u00a0\u202f]\d{3})*))?")


def parse_grade_deltas(text: str) -> list[dict]:
    """Ripiego senza clic: prezzo dei gradi alla memoria e al colore già selezionati, dai supplementi
    della sezione Condizione (es. 'Buono Molto buono Eccellente + € 90 Premium').
    Restituisce solo i gradi con un supplemento esplicito (quelli senza supplemento possono essere esauriti)."""
    sel = parse_selected(text)
    if not sel:
        return []
    flat = flatten(text).replace(" | ", " ")
    i = flat.find("Condizione")
    j = flat.find("Batteria", i)
    if i < 0 or j < 0:
        return []
    out = []
    for m in DELTA.finditer(flat[i:j]):
        grade, delta = m.group(1), m.group(2)
        if grade == sel["grade"] or not delta:
            continue
        out.append({**sel, "grade": grade, "price": round(sel["price"] + parse_price(delta), 2)})
    return out


def _click(page, text: str) -> bool:
    for role in ("radio", "button", "link", "option"):
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
    src = cfg["sources"]["swappie"]
    offers, runs = [], []
    for p in src["pages"]:
        t0 = time.time()
        got, misses = [], []
        try:
            page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            title = page.title()
            if "ci siamo quasi" in title.lower() or "just a moment" in title.lower():
                # verifica anti-bot Cloudflare (succede dai server GitHub): non insistere
                runs.append(dict(site=SITE, target=p["model"], status="bloccato", n=0,
                                 error="verifica anti-bot del sito", secs=round(time.time() - t0)))
                continue
            for label in ["Rifiuta", "Rifiuta tutto", "Solo necessari", "Accetta solo i necessari"]:
                b = page.get_by_role("button", name=re.compile(label, re.I))
                if b.count():
                    try:
                        b.first.click(timeout=2000)
                    except Exception:
                        pass
                    break
            for storage in src.get("storages", [128, 256]):
                key = model_key(cfg, p["model"], storage)
                if not key:
                    continue
                if not _click(page, f"{storage} GB"):
                    misses.append(f"{storage} GB")
                    continue
                page.wait_for_timeout(1500)
                for grade in src.get("grades", ["Eccellente", "Premium"]):
                    if not _click(page, grade):
                        misses.append(f"{storage} GB {grade}")
                        continue
                    page.wait_for_timeout(2000)
                    sel = parse_selected(page.inner_text("body"))
                    if not sel or sel["storage"] != storage or sel["grade"] != grade:
                        misses.append(f"{storage} GB {grade}")
                        continue
                    got.append(Offer(
                        site=SITE, model=key, storage=storage, sim=SIM_FISICA, color=sel["color"],
                        grade=grade, price=sel["price"], seller="Swappie", price_source="finale",
                        battery="≥95%" if grade == "Premium" else "≥86%", url=page.url,
                        notes="SIM da verificare (modelli EU: Nano-SIM + eSIM)",
                    ))
            if not got:
                # i clic non hanno funzionato: usa i supplementi mostrati per memoria/colore preselezionati
                page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                wanted = set(src.get("grades", ["Eccellente", "Premium"]))
                for d in parse_grade_deltas(page.inner_text("body")):
                    key = model_key(cfg, p["model"], d["storage"])
                    if key and d["grade"] in wanted:
                        got.append(Offer(
                            site=SITE, model=key, storage=d["storage"], sim=SIM_FISICA, color=d["color"],
                            grade=d["grade"], price=d["price"], seller="Swappie", price_source="selettore",
                            battery="≥95%" if d["grade"] == "Premium" else "≥86%", url=p["url"],
                            notes="prezzo calcolato dal supplemento del grado; SIM da verificare",
                        ))
            if not got:
                dump(page, f"swappie {p['model']}", 1500)
            offers += got
            runs.append(dict(site=SITE, target=p["model"], status="ok" if got else "vuoto", n=len(got),
                             error=("non trovati: " + ", ".join(misses))[:200] if misses else "",
                             secs=round(time.time() - t0)))
        except Exception as e:  # noqa: BLE001
            runs.append(dict(site=SITE, target=p["model"], status="errore", n=0, error=str(e)[:200],
                             secs=round(time.time() - t0)))
    return offers, runs
