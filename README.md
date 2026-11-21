# Monitor prezzi iPhone ricondizionati

Controlla **ogni ora** Amazon.it, Back Market e TrenDevice per gli iPhone configurati, salva tutto lo storico
nel repository e pubblica una **dashboard** su GitHub Pages per vedere la situazione ora per ora e fare analisi.
Quando un'offerta idonea scende sotto soglia apre una **issue GitHub** (ti arriva email/notifica) e, se configurato,
manda un messaggio **Telegram**.

## Cosa trovi nella dashboard

- **Prezzo minimo ora per ora** per sito, con le linee delle soglie. Clic su un punto → dettaglio di quell'ora.
- **Situazione ora per ora**: tutte le offerte di un controllo (anche quelle non idonee, con il motivo), variazione
  rispetto al controllo precedente, export CSV.
- **KPI**: miglior prezzo attuale, distanza dalla soglia, variazione 24 h, minimo/media del periodo, ore sotto soglia.
- **Confronto siti** (minimo attuale per modello), **media per ora del giorno**, **storico offerte sotto soglia**,
  **stato dei controlli** (per capire subito se un sito ha bloccato lo scraper).

Filtri: modello, SIM (qualsiasi / solo eSIM / SIM fisica), grado minimo (Eccellente+ / Premium), periodo.

## Regole

Definite in [`config.yaml`](config.yaml):

- **Requisiti minimi** (offerta "idonea"): grado ≥ Eccellente (Amazon Eccellente/Premium, Back Market
  Eccellente/Premium, TrenDevice A/A+), garanzia 12 mesi, venditore Amazon con ≥ 80% di valutazioni positive.
- **SIM**: `solo eSIM` (modelli USA senza slot) oppure `SIM fisica (+ eSIM)`.
- **Soglie** "offerta interessante" per modello/SIM/grado.

Su Back Market il prezzo accanto alle opzioni cambia dopo il clic: lo scraper seleziona memoria → grado → SIM e
legge il **prezzo finale** dal riepilogo; per gli altri colori salva il prezzo del selettore (marcato
`selettore`) e verifica con un clic il colore più economico.

## Installazione (una volta)

Serve [GitHub CLI](https://cli.github.com/) autenticata (`gh auth login`). Dalla cartella del progetto:

```bash
./pubblica.sh
```

Lo script crea il repository pubblico `iphone-price-monitor`, carica i file, attiva GitHub Pages e avvia il
primo controllo. In alternativa, a mano:

1. Crea un repository pubblico vuoto su github.com e carica i file del progetto.
2. *Settings → Pages → Build and deployment → Source:* **GitHub Actions**.
3. *Actions → Monitor prezzi (ogni ora) → Run workflow* per il primo giro.

### Telegram (facoltativo)

1. Su Telegram scrivi a **@BotFather** → `/newbot` → copia il token.
2. Scrivi un messaggio qualsiasi al tuo bot, poi apri
   `https://api.telegram.org/bot<TOKEN>/getUpdates` e copia `chat.id`.
3. Nel repository: *Settings → Secrets and variables → Actions → New repository secret*:
   `TELEGRAM_BOT_TOKEN` e `TELEGRAM_CHAT_ID`.

Senza i secret gli avvisi arrivano solo come issue GitHub.

## Analisi da terminale

```bash
pip install -r requirements.txt && python -m playwright install chromium
python -m monitor.analyze                                   # riepilogo di tutti i modelli
python -m monitor.analyze --model 16pro-128                 # un modello
python -m monitor.analyze --model 15pro-128 --hour 2026-11-21T20 --all   # tutte le offerte di un'ora (UTC)
python -m monitor.run --sites backmarket --no-alerts --headed            # controllo manuale visibile
```

Ogni esecuzione oraria scrive anche il report nel riepilogo del workflow (tab *Actions*).

## Dati

| File | Contenuto |
|---|---|
| `data/offers/AAAA-MM.csv` | ogni offerta letta: ora, sito, modello, SIM, colore, grado, prezzo, venditore, % positivi, fonte prezzo, idoneità, URL |
| `data/runs/AAAA-MM.csv` | esito di ogni pagina controllata (ok / vuoto / bloccato / errore) |
| `data/alert_state.json` | avvisi già inviati (evita ripetizioni: di nuovo solo dopo 24 h o con un calo ≥ 5 €) |
| `docs/data/*.json` | dati aggregati per la dashboard (rigenerati a ogni giro) |

I CSV si aprono direttamente in Excel/Google Sheets (separatore virgola, UTF-8).

## Limiti da conoscere

- I runner di GitHub hanno IP di data center: **Amazon a volte risponde con un captcha** e Back Market può
  attivare la protezione anti-bot. Succede in modo intermittente: il controllo viene registrato come `bloccato`
  (quadratino rosso nella dashboard) e si riprova l'ora successiva. Se un sito resta bloccato a lungo,
  conviene eseguire lo scraper da un computer di casa (`python -m monitor.run`) con un *self-hosted runner*.
- I cron di GitHub Actions possono partire con qualche minuto di ritardo e vengono sospesi dopo 60 giorni senza
  attività nel repository (i commit orari dei dati lo tengono attivo).
- Se i siti cambiano layout, i parser in `monitor/scrapers/` vanno aggiornati: i test in `tests/` usano testi
  reali delle pagine (`pytest`).

## Aggiungere un modello

1. In `config.yaml` aggiungi la voce in `models` (es. `key: 17pro-256`).
2. Aggiungi le soglie in `thresholds`, gli ASIN Amazon (o lascia che li trovi la ricerca), la pagina modello
   Back Market e TrenDevice.
