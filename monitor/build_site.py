"""Genera i JSON letti dalla dashboard (docs/) a partire dallo storico CSV."""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from .analytics import model_stats, parse_ts, threshold_hits
from .config import DOCS, load_config
from .normalize import SIM_LABEL
from .storage import read_all

SERIES_DAYS = 120
DETAIL_DAYS = 45

# colonne compatte per i file giornalieri
DAY_COLS = ["ts", "site", "model", "sim", "color", "grade", "grade_rank", "price", "seller",
            "seller_positive", "price_source", "eligible", "notes", "url"]


def build(cfg: dict | None = None, now: datetime | None = None):
    cfg = cfg or load_config()
    now = now or datetime.now(timezone.utc)
    rows = read_all("offers")
    runs = read_all("runs")
    out = DOCS / "data"
    (out / "days").mkdir(parents=True, exist_ok=True)

    # serie: minimo per (ora, modello, sito, sim, grado) sulle sole offerte idonee
    lim = now - timedelta(days=SERIES_DAYS)
    agg: dict[tuple, dict] = {}
    for r in rows:
        if r["eligible"] != "1" or parse_ts(r["ts"]) < lim:
            continue
        k = (r["ts"], r["model"], r["site"], r["sim"], float(r["grade_rank"]))
        if k not in agg or float(r["price"]) < agg[k][5]:
            agg[k] = [r["ts"], r["model"], r["site"], r["sim"], float(r["grade_rank"]), float(r["price"]),
                      r["color"], r["seller"]]
    series = sorted(agg.values())

    # dettaglio giornaliero (tutte le offerte, anche non idonee) per la vista ora per ora
    by_day = defaultdict(list)
    dlim = now - timedelta(days=DETAIL_DAYS)
    for r in rows:
        if parse_ts(r["ts"]) >= dlim:
            by_day[r["ts"][:10]].append([r.get(c, "") for c in DAY_COLS])
    for day, items in by_day.items():
        (out / "days" / f"{day}.json").write_text(json.dumps({"cols": DAY_COLS, "rows": items}, ensure_ascii=False, separators=(",", ":")))
    for f in (out / "days").glob("*.json"):
        if f.stem not in by_day:
            f.unlink()

    # esiti dei controlli
    run_agg = defaultdict(lambda: {"ok": 0, "tot": 0, "errors": []})
    for r in runs:
        if parse_ts(r["ts"]) < now - timedelta(days=14):
            continue
        a = run_agg[(r["ts"], r["site"])]
        a["tot"] += 1
        if r["status"] == "ok":
            a["ok"] += 1
        elif r["error"] or r["status"] != "ok":
            a["errors"].append(f"{r['target']}: {r['status']} {r['error']}".strip())
    run_list = [{"ts": k[0], "site": k[1], **v} for k, v in sorted(run_agg.items())]

    hours = sorted({r["ts"] for r in rows} | {r["ts"] for r in runs})
    meta = {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timezone": cfg.get("timezone", "Europe/Rome"),
        "models": cfg["models"], "thresholds": cfg["thresholds"], "requirements": cfg["requirements"],
        "sim_labels": SIM_LABEL, "sites": sorted({r["site"] for r in rows}),
        "hours": hours, "days": sorted(by_day),
        "series_cols": ["ts", "model", "site", "sim", "grade_rank", "price", "color", "seller"],
    }
    stats = {m["key"]: model_stats(rows, cfg, m["key"], now) for m in cfg["models"]}
    recent_hits = [h for h in threshold_hits(rows, cfg) if parse_ts(h["ts"]) >= now - timedelta(days=14)]

    def dump(name, obj):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))

    dump("meta.json", meta)
    dump("series.json", series)
    dump("runs.json", run_list)
    dump("stats.json", stats)
    dump("hits.json", sorted(recent_hits, key=lambda h: (h["ts"], float(h["price"])), reverse=True)[:300])
    print(f"dashboard: {len(series)} punti serie, {len(by_day)} giorni di dettaglio, {len(hours)} ore")


if __name__ == "__main__":
    build()
