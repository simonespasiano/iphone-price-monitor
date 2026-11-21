"""Archivio storico: un CSV al mese per le offerte e uno per l'esito di ogni controllo."""
from __future__ import annotations

import csv
from pathlib import Path

from .config import DATA
from .normalize import CSV_FIELDS

RUN_FIELDS = ["ts", "site", "target", "status", "n", "error", "secs"]


def _append(path: Path, fields: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerows(rows)


def save(ts: str, offers: list, runs: list[dict], root: Path = DATA):
    month = ts[:7]
    for o in offers:
        o.ts = ts
    _append(root / "offers" / f"{month}.csv", CSV_FIELDS, [o.row() for o in offers])
    _append(root / "runs" / f"{month}.csv", RUN_FIELDS, [{**r, "ts": ts} for r in runs])


def read_all(kind: str, root: Path = DATA) -> list[dict]:
    rows = []
    for p in sorted((root / kind).glob("*.csv")):
        with open(p, encoding="utf-8") as f:
            rows += list(csv.DictReader(f))
    return rows
