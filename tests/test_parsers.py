"""Test su testi reali letti dalle pagine il 21/11/2026."""
from datetime import datetime, timezone

from monitor.config import load_config
from monitor.normalize import Offer, parse_price, grade_rank, sim_from_text, model_from_title, color_from_title, SIM_ESIM, SIM_FISICA
from monitor.rules import is_eligible, matching_threshold
from monitor.scrapers import amazon, backmarket, trendevice
from monitor.alerts import select_new_hits

CFG = load_config()


def lines(s):  # i testi sono stati copiati con " | " come separatore di riga
    return s.replace(" | ", "\n")


BM_TEXT = lines(
    "Seleziona la condizione | Ogni dispositivo viene controllato da professionisti. Confronta le condizioni. | Buono | 558,00 € | "
    "Ottimo | 588,00 € | Eccellente | 625,00 € | Popolare | Premium | 730,00 € | Seleziona la batteria | Batteria standard | 625,00 € | "
    "Ottima per un uso quotidiano medio | Batteria nuova | 661,00 € | Seleziona lo spazio di archiviazione | 128 GB | 625,00 € | "
    "256 GB | 715,00 € | Seleziona il tipo di SIM | Quale tipo di SIM è adatto a te? | Dual SIM fisica | 669,00 € | "
    "2 slot SIM fisici (senza eSIM e senza Apple Intelligence) | eSIM | 560,00 € | 2 slot SIM virtuali (nessuno slot SIM fisico) | "
    "SIM fisica + eSIM | 625,00 € | 1 slot SIM fisico + 1 slot SIM virtuale | 1 / 3. | Seleziona il colore | Titanio nero | 631,00 € | "
    "Titanio blu | 625,00 € | Titanio naturale | 627,00 € | Titanio bianco | 612,00 € | Risparmia di più con Trade-in | "
    "Nessuna permuta | 1 / 3. | iPhone 15 Pro | Eccellente | Batteria standard | 128 GB | SIM fisica + eSIM | Titanio blu | 625,00 € | "
    "1239,00 € nuovo | Risparmia 614,00 € | Acquista | Hai 30 giorni per cambiare idea | Prodotto ricondizionato da Dloop (Paesi Bassi)"
)

TD_TEXT = lines(
    "Filtri | 29 | Promo | Risparmia 50€ | iPhone 15 Pro | 128 GB | Titanio blu | A Eccellente | Sim Card (include slot sim) | "
    "A partire da | €669,00 | €619,00 | Promo | Risparmia 50€ | iPhone 15 Pro | 128 GB | Titanio bianco | Sim Card (include slot sim) | "
    "A+ Come nuovo | A partire da | €779,90 | €729,90 | Promo | iPhone 15 Pro | 256 GB | Colore a sorpresa | Sim Card (include slot sim) | "
    "C Smart | A partire da | €749,00 | €699,00 | Preordina | iPhone 15 Pro | 512 GB | Titanio nero | e-Sim (no sim fisica) | "
    "A Eccellente | A partire da | €1.129,90 | €1.079,90"
)


def test_price_and_grade():
    assert parse_price("1.049,90 €") == 1049.9
    assert parse_price("€669,00") == 669.0
    assert parse_price("568,64") == 568.64
    assert grade_rank("Ricondizionato: eccellente") == 3
    assert grade_rank("A+ Come nuovo") == 4
    assert grade_rank("A Eccellente") == 3
    assert grade_rank("Ottimo") < grade_rank("Eccellente")
    assert grade_rank("C Smart") == 1


def test_sim_and_titles():
    assert sim_from_text("eSIM") == SIM_ESIM
    assert sim_from_text("SIM fisica + eSIM") == SIM_FISICA
    assert model_from_title("Apple iPhone 16 Pro, 128GB, Titanio Nero (Ricondizionato)") == ("iPhone 16 Pro", 128)
    assert model_from_title("Apple iPhone 15 Pro Max 256GB - Titanio Nero (Ricondizionato)") is None
    assert color_from_title("Apple iPhone 15 Pro 256 GB - Titan Schwarz (Ricondizionato)") == "Titanio Nero"


def test_trendevice_esim_label():
    assert sim_from_text("e-Sim (no sim fisica)") == SIM_ESIM


def test_backmarket_summary_and_selectors():
    s = backmarket.parse_summary(BM_TEXT)
    assert s == {"grade": "Eccellente", "battery": "Batteria standard", "storage": 128, "sim": "SIM fisica + eSIM",
                 "color": "Titanio blu", "price": 625.0, "seller": "Dloop (Paesi Bassi)"}
    sel = backmarket.parse_selectors(BM_TEXT)
    assert ("Titanio bianco", 612.0) in sel["colore"]
    assert ("eSIM", 560.0) in sel["sim"]
    assert dict(sel["condizione"])["Premium"] == 730.0


def test_trendevice_listing():
    items = trendevice.parse_listing(TD_TEXT, "iPhone 15 Pro")
    assert len(items) == 4
    assert items[0]["storage"] == 128 and items[0]["grade"] == "A Eccellente" and min(items[0]["prices"]) == 619.0
    assert items[1]["grade"].startswith("A+")
    assert items[2]["preorder"] is True
    assert min(items[3]["prices"]) == 1079.9


def test_amazon_aod_and_eligibility():
    raw = [{"heading": "Ricondizionato: eccellente", "price": "568,64", "seller": "Tech and Life", "positive": "100", "shipping": ""},
           {"heading": "Ricondizionato: eccellente", "price": "572,00", "seller": "Wcell EU", "positive": "50", "shipping": ""},
           {"heading": "Ricondizionato: buono", "price": "560,00", "seller": "Phone-Buddy", "positive": "88", "shipping": ""},
           {"heading": "Ricondizionato: premium", "price": "545,00", "seller": "Welback!", "positive": "", "shipping": "4,99"}]
    offers = amazon.parse_aod(raw, "15pro-128", 128, "Titanio Blu", "B0CVJ5WF3K")
    assert [o.price for o in offers] == [568.64, 572.0, 560.0, 549.99]
    res = [is_eligible(o, CFG)[0] for o in offers]
    assert res == [True, False, False, True]          # Wcell 50% positivi, Phone-Buddy grado buono
    for o, ok in zip(offers, res):
        o.eligible = ok
    assert matching_threshold(offers[0], CFG) is None  # 568,64 non è < 550
    assert matching_threshold(offers[3], CFG)["price"] == 550


def test_thresholds_sim_specific():
    # soglie fisse di prova: il test non dipende da quelle scelte in config.yaml
    CFG = dict(load_config(), thresholds=[
        {"model": "16pro-128", "sim": "esim", "grade": "eccellente", "op": "<", "price": 600},
        {"model": "16pro-128", "sim": "fisica", "grade": "eccellente", "op": "<=", "price": 660},
    ])
    o = Offer("Back Market", "16pro-128", 128, SIM_ESIM, "Titanio Nero", "Eccellente", 599)
    o.eligible = True
    assert matching_threshold(o, CFG)["sim"] == "esim"
    o2 = Offer("Back Market", "16pro-128", 128, SIM_FISICA, "Titanio Nero", "Eccellente", 660)
    o2.eligible = True
    assert matching_threshold(o2, CFG)["sim"] == "fisica"
    o3 = Offer("Back Market", "16pro-128", 128, SIM_ESIM, "Titanio Nero", "Eccellente", 600)
    o3.eligible = True
    assert matching_threshold(o3, CFG) is None


def test_alert_dedupe():
    now = datetime(2026, 11, 22, 10, tzinfo=timezone.utc)
    o = Offer("Amazon", "15pro-128", 128, SIM_FISICA, "Titanio Blu", "Eccellente", 545, "X", 95)
    o.eligible = True
    assert len(select_new_hits([o], CFG, now, {})) == 1
    key = "Amazon|15pro-128|fisica|Eccellente|Titanio Blu|X"
    state = {key: {"ts": "2026-11-22T05:00:00+00:00", "price": 545}}
    assert select_new_hits([o], CFG, now, state) == []        # già avvisato da poco
    o.price = 539
    assert len(select_new_hits([o], CFG, now, state)) == 1     # calo ulteriore ≥ 5 €


def test_trendevice_listing_inline_format():
    """Formato visto nel browser headless di GitHub: campi sulla stessa riga separati da ' | '."""
    txt = ("Filtri\n29\nPromo\nRisparmia 50€\niPhone 16 Pro\n128 GB | Colore a sorpresa | Sim Card (include slot sim) | C Smart\n"
           "A partire da\n€769,90\n€719,90\nPreordina\nPromo\nRisparmia 50€\niPhone 16 Pro\n128 GB | Titanio naturale | "
           "Sim Card (include slot sim) | A Eccellente\nA partire da\n€809,90\n€759,90\nPromo\niPhone 16 Pro Max\n256 GB | Titanio nero | "
           "Sim Card (include slot sim) | A Eccellente\nA partire da\n€999,90\n€949,90\nPromo\niPhone 16 Pro\n256 GB | Titanio sabbia | "
           "e-Sim (no sim fisica) | A+ Come nuovo\nA partire da €1.049,90 €999,90")
    items = trendevice.parse_listing(txt, "iPhone 16 Pro")
    assert [(i["storage"], i["grade"], min(i["prices"])) for i in items] == [
        (128, "C Smart", 719.9), (128, "A Eccellente", 759.9), (256, "A+ Come nuovo", 999.9)]
    assert items[1]["color"] == "Titanio naturale" and items[0]["preorder"]
    assert sim_from_text(items[2]["sim"]) == SIM_ESIM
