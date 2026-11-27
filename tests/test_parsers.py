"""Test su testi reali letti dalle pagine il 21/11/2026."""
from datetime import datetime, timezone

from monitor.config import load_config
from monitor.normalize import Offer, parse_price, grade_rank, sim_from_text, model_from_title, color_from_title, SIM_ESIM, SIM_FISICA
from monitor.rules import is_eligible, matching_threshold
from monitor.scrapers import amazon, backmarket, refurbed, swappie, trendevice
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
    assert matching_threshold(offers[0], CFG) is None  # 568,64 è sopra la soglia del 15 Pro 128
    assert matching_threshold(offers[3], CFG) is None  # 549,99 anche
    offers[3].price = 539.0
    assert matching_threshold(offers[3], CFG)["price"] == 540


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
    o = Offer("Amazon", "15pro-128", 128, SIM_FISICA, "Titanio Blu", "Eccellente", 539, "X", 95)
    o.eligible = True
    assert len(select_new_hits([o], CFG, now, {})) == 1
    key = "Amazon|15pro-128|fisica|Eccellente|Titanio Blu|X"
    state = {key: {"ts": "2026-11-22T05:00:00+00:00", "price": 539}}
    assert select_new_hits([o], CFG, now, state) == []        # già avvisato da poco
    o.price = 533
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


def test_refurbed_listing():
    """Testo della pagina Refurbed (varianti suggerite), 20/11/2026."""
    txt = ("iPhone 15 Pro bianco 128 GB Molto buono 568,99 € placeholder\n"
           "iPhone 15 Pro nero 256 GB Molto buono 647,99 € Più spazio di archiviazione\n"
           "iPhone 15 Pro blu 256 GB Ottimo 681,99 € 1+ miglioramenti\n"
           "iPhone 15 Pro grigio 128 GB Ottimo 765,99 € Aspetto migliore\n"
           "iPhone 16 Pro grigio 256 GB Ottimo 759,81 €")
    items = refurbed.parse_listing(txt, "iPhone 15 Pro")
    got = sorted((i["storage"], i["grade_src"], i["color"], i["price"]) for i in items)
    assert got == [(128, "Molto buono", "bianco", 568.99), (128, "Ottimo", "grigio", 765.99),
                   (256, "Molto buono", "nero", 647.99), (256, "Ottimo", "blu", 681.99)]
    assert refurbed.GRADE_MAP["ottimo"] == "Eccellente" and grade_rank(refurbed.GRADE_MAP["molto buono"]) < 3


def test_swappie_selected():
    txt = ("Swappie Care\nSolo 1 pezzi disponibili\n256 GB | Titanio naturale | Molto buono\n€ 609\n€ 629\n€ -20\n"
           "Prezzo di lancio Apple: € 1 369\ntasse incl.")
    assert swappie.parse_selected(txt) == {"storage": 256, "color": "Titanio naturale", "grade": "Molto buono", "price": 609.0}
    txt2 = "128 GB | Titanio bianco | Premium\nPrezzo a tempo limitato\n€ 1 099\nPrezzo di lancio Apple: € 1 239"
    assert swappie.parse_selected(txt2)["price"] == 1099.0
    assert swappie.parse_selected("Oops, sfortunatamente questo prodotto non è più disponibile") is None


def test_refurbed_suggested_real():
    """Testo reale letto dal runner GitHub il 27/11/2026."""
    txt = ("Migliore offerta 683,37 € Nuovo: 1.199,00 € (-43%) Confronta le configurazioni suggerite marrone 128 GB Molto buono "
           "683,37 € grigio 128 GB Ottimo 725,77 € Aspetto migliore nero 256 GB Molto buono 752,07 € Più spazio di archiviazione "
           "grigio 256 GB Ottimo 820,77 € 1+ miglioramenti bianco 256 GB Ottimo 829,00 € Caratteristiche Specifiche tecniche "
           "Colore marrone Memoria 128 GB")
    got = sorted((i["storage"], i["grade_src"], i["color"], i["price"]) for i in refurbed.parse_listing(txt, "iPhone 16 Pro"))
    assert got == [(128, "Molto buono", "marrone", 683.37), (128, "Ottimo", "grigio", 725.77),
                   (256, "Molto buono", "nero", 752.07), (256, "Ottimo", "bianco", 829.0), (256, "Ottimo", "grigio", 820.77)]


def test_refurbed_configurator():
    txt = ("⚡ Offerta Flash! Risparmia l'8% EXTRA sulle serie iPhone 16 e 17 con il codice IPHONE8OFF · Acquista QUI ora "
           "Home Prodotti iPhone 16 Pro 128 GB | Dual-SIM (2 x eSIM) | Titanio deserto (4,8/5) Immagine a solo scopo "
           "illustrativo Scegli grado estetico (Info) Molto buono Ottimo Più venduto Premium Come nuovo \n695,62 €\nNuovo: 1.199,00 €")
    sel = refurbed.parse_selected(txt)
    assert sel["storage"] == 128 and sel["price"] == 695.62 and sel["color"] == "Titanio deserto"
    assert sel["coupon"] == {"pct": 8, "code": "IPHONE8OFF"}
    assert sim_from_text(sel["sim_text"]) == SIM_ESIM
    txt15 = txt.replace("iPhone 16 Pro 128 GB | Dual-SIM (2 x eSIM)", "iPhone 15 Pro 128 GB | Dual-SIM (eSIM, Nano-SIM)")
    sel15 = refurbed.parse_selected(txt15)
    assert sel15["coupon"] is None and sim_from_text(sel15["sim_text"]) == SIM_FISICA
