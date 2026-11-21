"""Diagnostica: quando una pagina non restituisce offerte stampa nel log del workflow
titolo, URL e inizio del testo, così si capisce se è un blocco anti-bot o un cambio di layout."""
from __future__ import annotations

import os
import re


def dump(page, tag: str, chars: int = 700):
    try:
        title = page.title()
        url = page.url
        body = re.sub(r"\s+", " ", page.inner_text("body", timeout=5000))[:chars]
    except Exception as e:  # noqa: BLE001
        title, url, body = "?", "?", f"(testo non leggibile: {e})"
    print(f"::group::DEBUG {tag}\ntitolo: {title}\nurl: {url}\ntesto: {body}\n::endgroup::", flush=True)
    if os.getenv("DEBUG_SCREENSHOTS"):
        os.makedirs("debug", exist_ok=True)
        try:
            page.screenshot(path=f"debug/{re.sub(r'[^A-Za-z0-9_-]+', '_', tag)[:80]}.png")
        except Exception:
            pass
