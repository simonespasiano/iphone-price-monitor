"""TrenDevice: pagina elenco modello (gradi A Eccellente e A+ Come nuovo)."""
from __future__ import annotations

import re
import time

from ..config import model_key
from ..debug import dump
from ..normalize import Offer, parse_price, sim_from_text, norm_color

SITE = "TrenDevice"
GRADE_RE = re.compile(r"^(A\+|A|B|C)\s+\w")
EURO_RE = re.compile(r"^€\s?\d")


def parse_listing(text: str, model: str) -> list[dict]:
    """Ogni scheda: <modello> / <NN GB> / colore / SIM / grado / 'A partire da' / €prezzo pieno / €prezzo promo."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    items = []
    for i, line in enumerate(lines):
        if line != model or i + 1 >= len(lines) or not re.match(r"^\d+ GB$", lines[i + 1]):
            continue
        it = {"storage": int(lines[i + 1].split()[0]), "color": "", "sim": "", "grade": "", "prices": [], "preorder": False}
        for tok in lines[i + 2:i + 14]:
            if tok == model or tok in ("Promo",) or tok.startswith("Risparmia"):
                break
            if tok.lower() in ("a partire da", "da"):
                continue
            if EURO_RE.match(tok):
                it["prices"].append(parse_price(tok))
            elif GRADE_RE.match(tok):
                it["grade"] = tok
            elif "sim" in tok.lower():
                it["sim"] = tok
            elif tok.lower() == "preordina":
                it["preorder"] = True
            elif not it["color"] and not it["prices"]:
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
