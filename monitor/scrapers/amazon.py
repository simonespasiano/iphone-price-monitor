"""Amazon.it: elenco "tutte le offerte" (?aod=1) per ogni ASIN + ricerca per scoprire nuovi colori."""
from __future__ import annotations

import re
import time

from ..config import model_key
from ..debug import dump
from ..normalize import Offer, parse_price, model_from_title, color_from_title, SIM_FISICA

SITE = "Amazon"

# Stessa logica verificata a mano nel browser (pannello AOD).
AOD_JS = r"""
() => [...document.querySelectorAll('#aod-pinned-offer, #aod-offer')].map(o => {
  const pe = o.querySelector('.a-price');
  let price = '';
  if (pe) price = (pe.querySelector('.a-price-whole')?.innerText || '') + ',' + (pe.querySelector('.a-price-fraction')?.innerText || '00');
  if (!price.replace(',', '').trim()) price = o.querySelector('.a-price .a-offscreen')?.textContent || '';
  const heading = (o.querySelector('#aod-offer-heading')?.innerText || '').replace(/\s+/g, ' ');
  const sb = o.querySelector('#aod-offer-soldBy');
  const seller = (sb?.querySelector('a')?.innerText || sb?.querySelector('.a-col-right')?.innerText || '').trim();
  const txt = o.textContent.replace(/\s+/g, ' ');
  const pos = (txt.match(/(\d+)% positiv/) || [])[1] || '';
  const ship = (txt.match(/(Spedizione|Consegna)[^€]{0,60}?(\d+,\d{2})\s?€/) || [])[2] || '';
  return {heading, price: price.replace(/\n/g, ''), seller, positive: pos, shipping: ship};
})
"""

SEARCH_JS = r"""
() => [...document.querySelectorAll('[data-component-type="s-search-result"]')].map(e => ({
  asin: e.dataset.asin, title: e.querySelector('img')?.alt || e.querySelector('h2')?.innerText || '',
  price: e.querySelector('.a-price .a-offscreen')?.textContent || ''
}))
"""


def is_blocked(page) -> bool:
    url = page.url
    if "validateCaptcha" in url or "/errors/" in url:
        return True
    try:
        body = page.inner_text("body", timeout=3000)[:3000]
    except Exception:
        return False
    return bool(re.search(r"Inserisci i caratteri|caratteri che vedi|Type the characters|robot", body, re.I))


def reject_cookies(page):
    try:
        btn = page.locator("#sp-cc-rejectall-link")
        if btn.count():
            btn.first.click(timeout=2000)
    except Exception:
        pass


def set_location(page, postcode: str) -> str:
    """Imposta un CAP italiano: senza, dai server esteri Amazon mostra solo le offerte che spediscono all'estero."""
    try:
        page.goto("https://www.amazon.it/", wait_until="domcontentloaded", timeout=45000)
        reject_cookies(page)
        page.click("#nav-global-location-popover-link", timeout=8000)
        page.fill("#GLUXZipUpdateInput", postcode, timeout=8000)
        page.click("#GLUXZipUpdate input, #GLUXZipUpdate", timeout=5000)
        page.wait_for_timeout(2500)
        page.reload(wait_until="domcontentloaded")
        loc = page.locator("#glow-ingress-line2").inner_text(timeout=5000)
        return loc.strip()
    except Exception as e:  # noqa: BLE001
        return f"CAP non impostato: {str(e)[:120]}"


def parse_aod(raw: list[dict], model: str, storage: int, color: str, asin: str) -> list[Offer]:
    out = []
    url = f"https://www.amazon.it/dp/{asin}?aod=1"
    for r in raw:
        price = parse_price(r.get("price"))
        if not price:
            continue
        ship = parse_price(r.get("shipping")) or 0
        grade = re.sub(r"(?i)ricondizionat[oa]\s*:?", "", r.get("heading", "")).strip()
        pos = r.get("positive")
        out.append(Offer(
            site=SITE, model=model, storage=storage, sim=SIM_FISICA, color=color, grade=grade,
            price=round(price + ship, 2), seller=(r.get("seller") or "").strip(),
            seller_positive=int(pos) if str(pos).isdigit() else None,
            battery="≥80% (Amazon Renewed)", price_source="finale", url=url,
            notes=f"spedizione {ship:.2f} €" if ship else "",
        ))
    return out


def discover(raw: list[dict], cfg: dict, known: set[str]) -> list[dict]:
    new = []
    for r in raw:
        if not r.get("asin") or r["asin"] in known:
            continue
        if "ricondizionat" not in r.get("title", "").lower():
            continue
        mt = model_from_title(r["title"])
        if not mt:
            continue
        key = model_key(cfg, *mt)
        if key:
            new.append({"asin": r["asin"], "model": key, "color": color_from_title(r["title"])})
            known.add(r["asin"])
    return new


def scrape(page, cfg: dict) -> tuple[list[Offer], list[dict]]:
    src = cfg["sources"]["amazon"]
    offers, runs = [], []
    targets = list(src.get("asins", []))
    known = {t["asin"] for t in targets}
    models = {m["key"]: m for m in cfg["models"]}
    loc = set_location(page, str(src.get("postcode", "20121")))
    print(f"[amazon] consegna: {loc}", flush=True)
    if "non impostato" in loc:
        dump(page, "amazon home (CAP)", 1200)
    runs.append(dict(site=SITE, target="cap", status="ok" if src.get("postcode", "20121") in loc else "avviso", n=0, error=loc[:150], secs=0))

    for url in src.get("searches", []):
        t0 = time.time()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            reject_cookies(page)
            if is_blocked(page):
                runs.append(dict(site=SITE, target=url, status="bloccato", n=0, error="captcha", secs=round(time.time() - t0)))
                continue
            page.wait_for_timeout(2500)
            raw_s = page.evaluate(SEARCH_JS)
            if not raw_s:
                dump(page, f"amazon ricerca {url}")
            found = discover(raw_s, cfg, known)
            targets += found
            runs.append(dict(site=SITE, target=url, status="ok", n=len(found), error="", secs=round(time.time() - t0)))
        except Exception as e:  # noqa: BLE001
            runs.append(dict(site=SITE, target=url, status="errore", n=0, error=str(e)[:200], secs=round(time.time() - t0)))

    for t in targets:
        url = f"https://www.amazon.it/dp/{t['asin']}?aod=1"
        t0 = time.time()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            reject_cookies(page)
            if is_blocked(page):
                runs.append(dict(site=SITE, target=t["asin"], status="bloccato", n=0, error="captcha", secs=round(time.time() - t0)))
                continue
            try:
                page.wait_for_selector("#aod-offer, #aod-pinned-offer", timeout=12000)
            except Exception:
                pass
            page.wait_for_timeout(3000)   # le offerte AOD si caricano in modo asincrono
            raw = page.evaluate(AOD_JS)
            m = models[t["model"]]
            got = parse_aod(raw, t["model"], int(m["storage"]), t.get("color", ""), t["asin"])
            if len(got) < 3:
                dump(page, f"amazon {t['asin']} ({len(got)} offerte)")
            offers += got
            runs.append(dict(site=SITE, target=t["asin"], status="ok" if got else "vuoto", n=len(got), error="", secs=round(time.time() - t0)))
        except Exception as e:  # noqa: BLE001
            runs.append(dict(site=SITE, target=t["asin"], status="errore", n=0, error=str(e)[:200], secs=round(time.time() - t0)))
    return offers, runs
