"""Analisi sullo storico: serie orarie, statistiche per modello, pattern per ora del giorno."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from zoneinfo import ZoneInfo

from .normalize import Offer, SIM_ESIM
from .rules import matching_threshold, sim_matches, threshold_for
from .normalize import grade_rank


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def to_offer(r: dict) -> Offer:
    o = Offer(site=r["site"], model=r["model"], storage=int(r["storage"]), sim=r["sim"], color=r["color"],
              grade=r["grade"], price=float(r["price"]), seller=r["seller"],
              seller_positive=int(r["seller_positive"]) if r.get("seller_positive") else None,
              battery=r.get("battery", ""), price_source=r.get("price_source", ""), url=r.get("url", ""),
              notes=r.get("notes", ""), ts=r["ts"])
    o.eligible = str(r.get("eligible")) in ("1", "True", "true")
    return o


def hourly_min(rows: list[dict], model: str, sim: str = "any", min_grade: str = "eccellente",
               site: str | None = None) -> dict[str, dict]:
    """{ts: riga dell'offerta idonea più economica} per filtro dato."""
    best: dict[str, dict] = {}
    g = grade_rank(min_grade)
    for r in rows:
        if r["model"] != model or str(r["eligible"]) != "1" or float(r["grade_rank"]) < g:
            continue
        if not sim_matches(sim, r["sim"]) or (site and r["site"] != site):
            continue
        if r["ts"] not in best or float(r["price"]) < float(best[r["ts"]]["price"]):
            best[r["ts"]] = r
    return dict(sorted(best.items()))


def model_stats(rows: list[dict], cfg: dict, model: str, now: datetime | None = None) -> dict:
    tz = ZoneInfo(cfg.get("timezone", "Europe/Rome"))
    now = now or datetime.now(timezone.utc)
    out = {"model": model, "filters": []}
    filters = [("any", "eccellente", "Qualsiasi SIM"), ("esim", "eccellente", "solo eSIM"),
               ("fisica", "eccellente", "SIM fisica"), ("any", "premium", "Premium")]
    for sim, grade, label in filters:
        series = hourly_min(rows, model, sim, grade)
        if not series:
            continue
        ts_list = list(series)
        last_ts = ts_list[-1]
        cur = series[last_ts]

        def window(h):
            lim = now - timedelta(hours=h)
            return [float(v["price"]) for k, v in series.items() if parse_ts(k) >= lim]

        d24, d7 = window(24), window(24 * 7)
        prev24 = [float(v["price"]) for k, v in series.items()
                  if timedelta(hours=23) <= parse_ts(last_ts) - parse_ts(k) <= timedelta(hours=25)]
        allp = [float(v["price"]) for v in series.values()]
        sites = defaultdict(int)
        for v in series.values():
            sites[v["site"]] += 1
        by_hour = defaultdict(list)
        for k, v in series.items():
            by_hour[parse_ts(k).astimezone(tz).hour].append(float(v["price"]))
        hod = {h: round(mean(p), 2) for h, p in sorted(by_hour.items())}
        ths = [t for t in threshold_for(cfg, model) if (t["sim"] == sim or (sim == "any" and t["sim"] == "any"))
               and t["grade"] == grade]
        under = None
        if ths:
            t = ths[0]
            under = sum(1 for p in allp if (p < t["price"] if t["op"] == "<" else p <= t["price"]))
        out["filters"].append({
            "label": label, "sim": sim, "grade": grade,
            "current": {"ts": last_ts, "price": float(cur["price"]), "site": cur["site"], "seller": cur["seller"],
                        "color": cur["color"], "grade": cur["grade"], "sim": cur["sim"], "url": cur["url"],
                        "source": cur["price_source"]},
            "threshold": ths[0] if ths else None,
            "gap_to_threshold": round(float(cur["price"]) - ths[0]["price"], 2) if ths else None,
            "change_24h": round(float(cur["price"]) - prev24[0], 2) if prev24 else None,
            "min_24h": min(d24) if d24 else None, "avg_24h": round(mean(d24), 2) if d24 else None,
            "min_7d": min(d7) if d7 else None, "avg_7d": round(mean(d7), 2) if d7 else None,
            "min_all": min(allp), "max_all": max(allp), "hours": len(allp),
            "hours_under_threshold": under,
            "best_site_share": {s: round(n / len(allp) * 100) for s, n in sorted(sites.items(), key=lambda x: -x[1])},
            "hour_of_day_avg": hod,
            "cheapest_hour": min(hod, key=hod.get) if len(hod) > 1 else None,
        })
    return out


def threshold_hits(rows: list[dict], cfg: dict) -> list[dict]:
    hits = []
    for r in rows:
        if str(r["eligible"]) != "1":
            continue
        o = to_offer(r)
        t = matching_threshold(o, cfg)
        if t:
            hits.append({**r, "threshold": f"{t['op']} {t['price']}"})
    return hits
