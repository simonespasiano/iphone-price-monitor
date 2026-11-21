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


def _drop_ts(path: Path, ts: str, sites: set[str]):
    """Un nuovo giro nella stessa ora sostituisce i dati di quell'ora per i siti controllati."""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fields = list(rows[0].keys()) if rows else None
    keep = [r for r in rows if not (r["ts"] == ts and r["site"] in sites)]
    if fields and len(keep) != len(rows):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(keep)


def save(ts: str, offers: list, runs: list[dict], root: Path = DATA):
    month = ts[:7]
    sites = {r["site"] for r in runs} | {o.site for o in offers}
    _drop_ts(root / "offers" / f"{month}.csv", ts, sites)
    _drop_ts(root / "runs" / f"{month}.csv", ts, sites)
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
