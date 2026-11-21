"""Carica nello storico i due controlli manuali del 21/11/2026 (mattina e sera), così la dashboard
parte già con dati reali. Si esegue una sola volta: python scripts/seed_initial_data.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitor.config import load_config  # noqa: E402
from monitor.normalize import Offer, SIM_ESIM as E, SIM_FISICA as F  # noqa: E402
from monitor.rules import is_eligible  # noqa: E402
from monitor.storage import save  # noqa: E402
from monitor.build_site import build  # noqa: E402

AZ = "https://www.amazon.it/dp/{}?aod=1"
BM16 = "https://www.backmarket.it/it-it/p/iphone-16-pro"
BM15 = "https://www.backmarket.it/it-it/p/iphone-15-pro"
TD16 = "https://www.trendevice.com/prodotti/iphone/serie-16/iphone-16-pro/"
TD15 = "https://www.trendevice.com/prodotti/iphone/serie-15/iphone-15-pro/"
NOTE = "controllo manuale iniziale"

MORNING = [  # 21/11 mattina (riferimenti)
    Offer("Back Market", "16pro-128", 128, E, "", "Eccellente", 683, url=BM16, notes=NOTE),
    Offer("Back Market", "16pro-128", 128, F, "", "Eccellente", 709, url=BM16, notes=NOTE),
    Offer("Amazon", "15pro-256", 256, F, "Titanio Blu", "Eccellente", 625, "Phone-Buddy", 88, url=AZ.format("B0CVK3WMT3"), notes=NOTE),
    Offer("Amazon", "15pro-128", 128, F, "Titanio Blu", "Eccellente", 568.64, "Tech and Life", 100, url=AZ.format("B0CVJ5WF3K"), notes=NOTE),
    Offer("Back Market", "15pro-128", 128, F, "", "Eccellente", 599, url=BM15, notes=NOTE),
    Offer("Back Market", "15pro-128", 128, E, "", "Eccellente", 571, price_source="selettore", url=BM15, notes=NOTE),
]


def az(asin, model, st, color, rows):
    return [Offer("Amazon", model, st, F, color, g, p, s, r, url=AZ.format(asin), notes=NOTE) for g, p, s, r in rows]


EVENING = (
    az("B0CVJ5WF3K", "15pro-128", 128, "Titanio Blu", [
        ("Premium", 660, "Welback!", 90), ("Accettabile", 534.15, "Geekmarket tech", 50), ("Buono", 560, "Phone-Buddy", 88),
        ("Eccellente", 568.64, "Tech and Life", 100), ("Eccellente", 572, "Wcell EU", 50), ("Eccellente", 598.14, "Orlado Tech", 67),
        ("Eccellente", 600, "Eniro Mall", 29), ("Eccellente", 615, "ReNewed SRL", 53)])
    + az("B0CVJ2RLP5", "15pro-128", 128, "Titanio Nero", [
        ("Premium", 660, "Welback!", 90), ("Eccellente", 594.69, "Orlado Tech", 67), ("Eccellente", 595, "Phone-Buddy", 88),
        ("Eccellente", 597, "DIDO-TECHNOLOGIE", None), ("Eccellente", 599, "iFonki", 90), ("Eccellente", 620, "Welback!", 90)])
    + az("B0CVK3WMT3", "15pro-256", 256, "Titanio Blu", [
        ("Premium", 725, "Phone-Buddy", 88), ("Accettabile", 559.76, "Geekmarket tech", 50), ("Buono", 585, "Phone-Buddy", 88),
        ("Eccellente", 625, "Phone-Buddy", 88), ("Eccellente", 629, "SEEPPLE", 81), ("Eccellente", 629.99, "Reswipe", 88),
        ("Eccellente", 643, "iMuda Investiments SL", 97)])
    + az("B0CVJVJNQS", "15pro-256", 256, "Titanio Nero", [
        ("Premium", 720, "Phone-Buddy", 88), ("Eccellente", 625, "Phone-Buddy", 88), ("Eccellente", 629, "SEEPPLE", 81),
        ("Eccellente", 629, "ReNewed SRL", 53), ("Eccellente", 670, "Welback!", 90)])
    + az("B0DHYDBXJ9", "16pro-128", 128, "Titanio Nero", [
        ("Eccellente", 737, "iFonki", 90), ("Accettabile", 664, "Loop-Mobile EU", 76), ("Accettabile", 689.99, "rebuy recommerce GmbH IT", 83),
        ("Eccellente", 745, "Orlado Tech", 67), ("Eccellente", 748, "Alloccaz", 60), ("Eccellente", 749.20, "Wcell EU", 50)])
    + az("B0DHYFYZ5K", "16pro-128", 128, "Titanio Naturale", [
        ("Premium", 800, "Phone-Buddy", 88), ("Eccellente", 702, "Loop-Mobile EU", 76), ("Eccellente", 729, "Nest Green", 41),
        ("Eccellente", 729, "Phone-Buddy", 88), ("Eccellente", 730, "Alloccaz", 60)])
    + az("B0DHYF2KQG", "16pro-128", 128, "Titanio Sabbia", [
        ("Premium", 850, "Welback Srl", None), ("Eccellente", 702, "Loop-Mobile EU", 76), ("Eccellente", 699.99, "Reswipe", 88),
        ("Eccellente", 706, "e-recover", 57), ("Eccellente", 719, "iMuda Investiments SL", 97)])
    + az("B0DHYDMJ1W", "16pro-256", 256, "Titanio Nero", [
        ("Premium", 900, "Phone-Buddy", 88), ("Eccellente", 770, "ComTechCore", 100), ("Eccellente", 783, "KRIPNOVA", 96),
        ("Eccellente", 786, "Phone-Buddy", 88)])
    + [
        Offer("Back Market", "16pro-128", 128, E, "Titanio Nero", "Eccellente", 693, "NexVoya (Germania)", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-128", 128, E, "Titanio Bianco", "Eccellente", 694, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-128", 128, E, "Titanio Sabbia", "Eccellente", 697, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-128", 128, E, "Titanio Naturale", "Eccellente", 698, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-128", 128, F, "Titanio Nero", "Eccellente", 746, "Dloop (Paesi Bassi)", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-128", 128, F, "Titanio Naturale", "Eccellente", 724, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-128", 128, F, "Titanio Sabbia", "Eccellente", 724, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-128", 128, E, "", "Premium", 789, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-256", 256, E, "", "Eccellente", 769, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "16pro-256", 256, F, "", "Eccellente", 801, price_source="selettore", url=BM16, notes=NOTE),
        Offer("Back Market", "15pro-128", 128, E, "Titanio Blu", "Eccellente", 560, url=BM15, notes=NOTE),
        Offer("Back Market", "15pro-128", 128, E, "Titanio Bianco", "Eccellente", 561, price_source="selettore", url=BM15, notes=NOTE),
        Offer("Back Market", "15pro-128", 128, F, "Titanio Blu", "Eccellente", 625, url=BM15, notes=NOTE),
        Offer("Back Market", "15pro-128", 128, F, "Titanio Bianco", "Eccellente", 612, price_source="selettore", url=BM15, notes=NOTE),
        Offer("Back Market", "15pro-128", 128, E, "", "Premium", 689, price_source="selettore", url=BM15, notes=NOTE),
        Offer("Back Market", "15pro-256", 256, E, "", "Eccellente", 612, price_source="selettore", url=BM15, notes=NOTE),
        Offer("Back Market", "15pro-256", 256, F, "", "Eccellente", 715, price_source="selettore", url=BM15, notes=NOTE),
        Offer("TrenDevice", "16pro-128", 128, F, "Titanio Naturale", "Eccellente", 759.90, "TrenDevice", url=TD16, notes=NOTE),
        Offer("TrenDevice", "16pro-128", 128, F, "Titanio Sabbia", "Premium", 839.90, "TrenDevice", url=TD16, notes=NOTE),
        Offer("TrenDevice", "16pro-256", 256, F, "Titanio Naturale", "Eccellente", 859.90, "TrenDevice", url=TD16, notes=NOTE),
        Offer("TrenDevice", "15pro-128", 128, F, "Titanio Blu", "Eccellente", 619, "TrenDevice", url=TD15, notes=NOTE),
        Offer("TrenDevice", "15pro-128", 128, F, "Titanio Bianco", "Premium", 729.90, "TrenDevice", url=TD15, notes=NOTE),
        Offer("TrenDevice", "15pro-256", 256, F, "Titanio Nero", "Eccellente", 699, "TrenDevice", url=TD15, notes=NOTE),
    ]
)

if __name__ == "__main__":
    cfg = load_config()
    for ts, offers in [("2026-11-21T08:00:00Z", MORNING), ("2026-11-21T20:00:00Z", EVENING)]:
        for o in offers:
            ok, why = is_eligible(o, cfg)
            o.eligible = ok
            if why:
                o.notes += "; non idonea: " + why
        runs = [dict(site=s, target="manuale", status="ok", n=sum(1 for o in offers if o.site == s), error="", secs=0)
                for s in sorted({o.site for o in offers})]
        save(ts, offers, runs)
    build(cfg)
