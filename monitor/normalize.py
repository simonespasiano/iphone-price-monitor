"""Normalizzazione di gradi, SIM, prezzi e modelli comuni a tutti i siti."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

GRADE_RANK = {
    "accettabile": 1, "discreto": 1, "c": 1, "c smart": 1,
    "buono": 2, "b": 2, "b buono": 2,
    "ottimo": 2.5,
    "eccellente": 3, "a": 3, "a eccellente": 3,
    "premium": 4, "a+": 4, "a+ come nuovo": 4, "come nuovo": 4,
}
GRADE_LABEL = {1: "Accettabile", 2: "Buono", 2.5: "Ottimo", 3: "Eccellente", 4: "Premium"}

SIM_ESIM = "esim"          # solo eSIM (modelli USA, nessuno slot fisico)
SIM_FISICA = "fisica"      # SIM fisica (+ eSIM)
SIM_DUAL = "dual-fisica"   # 2 SIM fisiche (modelli asiatici, senza eSIM)
SIM_LABEL = {SIM_ESIM: "solo eSIM", SIM_FISICA: "SIM fisica (+ eSIM)", SIM_DUAL: "Dual SIM fisica"}

CSV_FIELDS = [
    "ts", "site", "model", "storage", "sim", "color", "grade", "grade_rank", "price",
    "seller", "seller_positive", "battery", "warranty_months", "price_source",
    "eligible", "notes", "url",
]


@dataclass
class Offer:
    site: str
    model: str            # chiave modello di config, es. 16pro-128
    storage: int
    sim: str
    color: str
    grade: str
    price: float
    seller: str = ""
    seller_positive: Optional[int] = None
    battery: str = ""
    warranty_months: int = 12
    price_source: str = "finale"     # finale | selettore | elenco
    url: str = ""
    notes: str = ""
    ts: str = ""
    eligible: bool = False
    grade_rank: float = field(default=0)

    def __post_init__(self):
        self.grade_rank = grade_rank(self.grade)
        self.grade = GRADE_LABEL.get(self.grade_rank, self.grade)

    def row(self) -> dict:
        d = asdict(self)
        d["eligible"] = int(bool(self.eligible))
        d["seller_positive"] = "" if self.seller_positive is None else self.seller_positive
        return {k: d[k] for k in CSV_FIELDS}


def grade_rank(text: str) -> float:
    t = re.sub(r"\s+", " ", (text or "").strip().lower())
    t = t.replace("ricondizionato:", "").strip()
    if t in GRADE_RANK:
        return GRADE_RANK[t]
    for key in sorted(GRADE_RANK, key=len, reverse=True):
        if len(key) > 2 and key in t:
            return GRADE_RANK[key]
    return 0


def parse_price(text: str) -> Optional[float]:
    """'1.049,90 €' -> 1049.9 ; '€669,00' -> 669.0 ; '660,00' -> 660.0"""
    if text is None:
        return None
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})*|\d+)(?:,(\d{1,2}))?", str(text).replace("\xa0", " "))
    if not m:
        return None
    whole = re.sub(r"[.\s]", "", m.group(1))
    frac = m.group(2) or "0"
    return round(float(f"{whole}.{frac}"), 2)


def sim_from_text(text: str) -> str:
    t = (text or "").lower()
    if "dual sim fisica" in t:
        return SIM_DUAL
    if "nano-sim" in t or "nano sim" in t:   # Refurbed: "Dual-SIM (eSIM, Nano-SIM)"
        return SIM_FISICA
    if "no sim fisica" in t or "nessuno slot sim" in t or t.startswith("e-sim") or t.strip() == "esim":
        return SIM_ESIM
    if "fisica" in t or "sim card" in t or "slot sim" in t or "include slot" in t:
        return SIM_FISICA
    if "esim" in t or "e-sim" in t:
        return SIM_ESIM
    return SIM_FISICA


def model_from_title(title: str) -> Optional[tuple[str, int]]:
    """'Apple iPhone 16 Pro, 128GB, Titanio Nero (Ricondizionato)' -> ('iPhone 16 Pro', 128). Esclude Max/Plus/e."""
    t = title or ""
    m = re.search(r"iPhone\s+(1[3-9])\s+Pro(?!\s*Max)\b", t, re.I)
    if not m:
        return None
    s = re.search(r"(\d{3,4})\s*GB", t, re.I) or re.search(r"\b(1)\s*TB", t, re.I)
    if not s:
        return None
    storage = int(s.group(1))
    if storage == 1:
        storage = 1000
    return f"iPhone {m.group(1)} Pro", storage


def color_from_title(title: str) -> str:
    m = re.search(r"Titan(?:io)?\s+(\w+)", title or "", re.I)
    if not m:
        return ""
    c = m.group(1).lower()
    c = {"schwarz": "nero", "natur": "naturale", "weiss": "bianco", "blau": "blu"}.get(c, c)
    return f"Titanio {c.capitalize()}"


def norm_color(c: str) -> str:
    c = re.sub(r"\s+", " ", (c or "").strip())
    if not c:
        return ""
    if c.lower().startswith("titan"):
        return color_from_title(c) or c
    return c[:1].upper() + c[1:]
