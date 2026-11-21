"""Back Market: seleziona memoria -> grado -> SIM -> colore e legge il prezzo FINALE dal riepilogo.

I prezzi accanto alle opzioni del selettore cambiano dopo il clic, quindi vengono salvati solo
come price_source="selettore" e il prezzo affidabile è quello del riepilogo dopo la selezione.
"""
from __future__ import annotations

import re
import time

from ..debug import dump
from ..normalize import Offer, parse_price, sim_from_text, norm_color

SITE = "Back Market"
GRADES = ["Buono", "Ottimo", "Eccellente", "Premium"]
GROUPS = {
    "Seleziona la condizione": "condizione",
    "Seleziona la batteria": "batteria",
    "Seleziona lo spazio di archiviazione": "memoria",
    "Seleziona il tipo di SIM": "sim",
    "Seleziona il colore": "colore",
}
PRICE_RE = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}\s?€$")


def parse_selectors(text: str) -> dict[str, list[tuple[str, float]]]:
    """Dal testo della pagina estrae le opzioni dei selettori con il prezzo indicato accanto."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    out: dict[str, list[tuple[str, float]]] = {}
    group = None
    for i, line in enumerate(lines):
        if line in GROUPS:
            group = GROUPS[line]
            out[group] = []
            continue
        if line.startswith("Risparmia di più") or line.startswith("Hai 30 giorni"):
            group = None
            continue
        if group and PRICE_RE.match(line) and i > 0:
            name = lines[i - 1]
            if not PRICE_RE.match(name):
                out[group].append((name, parse_price(line)))
    return out


def parse_summary(text: str) -> dict | None:
    """Riepilogo prodotto selezionato: grado, batteria, memoria, SIM, colore, prezzo, venditore."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i in range(len(lines) - 6):
        if lines[i] in GRADES and lines[i + 1].startswith("Batteria") and re.match(r"^\d+ GB$", lines[i + 2]):
            if not PRICE_RE.match(lines[i + 5]):
                continue
            seller = ""
            m = re.search(r"[Rr]icondizionato da ([^\n]+)", text)
            if m:
                seller = m.group(1).strip()
            return {
                "grade": lines[i], "battery": lines[i + 1], "storage": int(lines[i + 2].split()[0]),
                "sim": lines[i + 3], "color": lines[i + 4], "price": parse_price(lines[i + 5]),
                "seller": seller,
            }
    return None


def _click_option(page, name: str) -> bool:
    pattern = re.compile(r"^\s*" + re.escape(name) + r"\s*(\n|\d|$)", re.I)
    loc = page.locator("label").filter(has_text=pattern)
    if not loc.count():
        return False
    before = page.url
    loc.first.scroll_into_view_if_needed(timeout=5000)
    loc.first.click(timeout=8000)
    for _ in range(20):          # la selezione cambia URL (pagina /p/go/...) e ricarica il riepilogo
        page.wait_for_timeout(500)
        if page.url != before:
            break
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2500)
    return True


def _reject_cookies(page):
    for label in ["Rifiuta tutto", "Rifiuta", "Continua senza accettare", "Solo essenziali"]:
        try:
            b = page.get_by_role("button", name=re.compile(label, re.I))
            if b.count():
                b.first.click(timeout=2000)
                page.wait_for_timeout(500)
                return
        except Exception:
            pass


def _text(page) -> str:
    return page.inner_text("body", timeout=15000)


def scrape(page, cfg: dict) -> tuple[list[Offer], list[dict]]:
    src = cfg["sources"]["backmarket"]
    models = {m["key"]: m for m in cfg["models"]}
    offers: list[Offer] = []
    runs: list[dict] = []
    for p in src["pages"]:
        for key in p["models"]:
            storage = int(models[key]["storage"])
            for grade in src["grades"]:
                for sim in src["sims"]:
                    target = f"{key} {grade} {sim}"
                    t0 = time.time()
                    try:
                        page.goto(p["url"], wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(2500)
                        _reject_cookies(page)
                        if "Just a moment" in page.title() or "Attention Required" in page.title():
                            runs.append(dict(site=SITE, target=target, status="bloccato", n=0, error="anti-bot", secs=round(time.time() - t0)))
                            continue
                        ok = _click_option(page, f"{storage} GB") and _click_option(page, grade) and _click_option(page, sim)
                        txt = _text(page)
                        summ = parse_summary(txt)
                        got = []
                        if ok and summ and summ["grade"] == grade and summ["storage"] == storage and sim_from_text(summ["sim"]) == sim_from_text(sim):
                            got.append(_offer(key, summ, page.url))
                            # colori: prezzo da selettore, poi verifica del più economico con clic
                            colors = parse_selectors(txt).get("colore", [])
                            for cname, cprice in colors:
                                if norm_color(cname) != norm_color(summ["color"]) and cprice:
                                    o = _offer(key, {**summ, "color": cname, "price": cprice, "seller": ""}, page.url)
                                    o.price_source = "selettore"
                                    got.append(o)
                            cheaper = sorted([c for c in colors if c[1] and c[1] < summ["price"]], key=lambda c: c[1])
                            if cheaper and _click_option(page, cheaper[0][0]):
                                s2 = parse_summary(_text(page))
                                if s2 and s2["grade"] == grade and s2["storage"] == storage:
                                    got = [g for g in got if norm_color(g.color) != norm_color(s2["color"])]
                                    got.append(_offer(key, s2, page.url))
                        if not got:
                            dump(page, f"backmarket {target} click={ok}")
                        offers += got
                        runs.append(dict(site=SITE, target=target, status="ok" if got else "vuoto", n=len(got),
                                         error="" if got else "combinazione non disponibile o non letta", secs=round(time.time() - t0)))
                    except Exception as e:  # noqa: BLE001
                        runs.append(dict(site=SITE, target=target, status="errore", n=0, error=str(e)[:200], secs=round(time.time() - t0)))
    return offers, runs


def _offer(key: str, s: dict, url: str) -> Offer:
    return Offer(
        site=SITE, model=key, storage=s["storage"], sim=sim_from_text(s["sim"]), color=norm_color(s["color"]),
        grade=s["grade"], price=s["price"], seller=s.get("seller", ""), battery=s.get("battery", ""),
        price_source="finale", url=url.split("#")[0],
    )
