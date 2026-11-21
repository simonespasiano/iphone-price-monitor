"""Requisiti minimi e soglie "offerta interessante"."""
from __future__ import annotations

from .normalize import Offer, grade_rank, SIM_ESIM, SIM_FISICA


def is_eligible(o: Offer, cfg: dict) -> tuple[bool, str]:
    req = cfg["requirements"]
    reasons = []
    if o.grade_rank < grade_rank(req["min_grade"]):
        reasons.append("grado")
    if o.seller_positive is not None and o.seller_positive < req["min_seller_positive"]:
        reasons.append(f"venditore {o.seller_positive}%")
    if o.warranty_months and o.warranty_months < req["warranty_months"]:
        reasons.append("garanzia")
    return (not reasons), ", ".join(reasons)


def sim_matches(rule_sim: str, sim: str) -> bool:
    if rule_sim == "any":
        return True
    if rule_sim == "esim":
        return sim == SIM_ESIM
    if rule_sim == "fisica":
        return sim != SIM_ESIM
    return False


def matching_threshold(o: Offer, cfg: dict) -> dict | None:
    """Restituisce la prima soglia rispettata dall'offerta (solo offerte idonee)."""
    if not o.eligible:
        return None
    for t in cfg["thresholds"]:
        if t["model"] != o.model or not sim_matches(t["sim"], o.sim):
            continue
        if o.grade_rank < grade_rank(t["grade"]):
            continue
        ok = o.price < t["price"] if t["op"] == "<" else o.price <= t["price"]
        if ok:
            return t
    return None


def threshold_for(cfg: dict, model: str) -> list[dict]:
    return [t for t in cfg["thresholds"] if t["model"] == model]
