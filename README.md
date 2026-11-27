# Monitor prezzi iPhone ricondizionati

Controlla **ogni ora** Amazon.it, Back Market, TrenDevice, Swappie e Refurbed per gli iPhone configurati, salva tutto lo storico
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

4. **Prova:** *Actions → Test Telegram → Run workflow*. Ricevi un messaggio di prova e un
   riepilogo di esempio; se qualcosa non va, il log del job dice cosa correggere
   (secret mancante, token non valido, chat ID errato o bot non avviato).

Di default (`telegram_every_run: false`) Telegram scrive **solo quando c'è un'offerta sotto soglia**.
Con `telegram_every_run: true` in `config.yaml` ricevi un **riepilogo a ogni verifica**
(esito, miglior prezzo per modello con link «apri offerta» e distanza dall’obiettivo, stato dei siti) più un messaggio
separato con i link quando c'è un'offerta nuova. Con `false` ricevi solo gli avvisi.

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

## Siti e gradi

| Sito | Gradi considerati idonei | Note |
|---|---|---|
| Amazon.it | Eccellente, Premium | venditore ≥ 80% positivi; batteria ≥ 80% (Premium ≥ 90%) |
| Back Market | Eccellente, Premium | prezzo finale dopo la selezione; batteria ≥ 80% (Premium ≥ 90%, parti originali) |
| TrenDevice | A Eccellente, A+ Come nuovo | batteria ≥ 80% |
| Swappie | Eccellente, Premium | batteria ≥ 86% (Premium ≥ 95%) |
| Refurbed | Ottimo (= Eccellente) | "Molto buono" ammette micrograffi sul display: non idoneo; batteria non dichiarata |

Gli scraper di Swappie e Refurbed sono stati aggiunti il 27/11/2026: se nella dashboard compaiono come `vuoto`,
il file `data/diagnostica_ultimo_giro.txt` mostra il testo letto per adattare il parser.

## Limiti da conoscere

- I runner di GitHub hanno IP di data center. **Amazon.it** funziona (lo scraper imposta il CAP di consegna,
  altrimenti Amazon mostra solo le offerte che spediscono all'estero). **Back Market** al momento risponde ai
  server GitHub con la sua verifica anti-bot: il giro viene registrato come `bloccato` (quadratino rosso nella
  dashboard), lo scraper non insiste e riprova l'ora successiva. Per avere Back Market con continuità conviene
  eseguire il workflow da un computer di casa con un
  [self-hosted runner](https://docs.github.com/actions/hosting-your-own-runners): registra il PC come runner
  (*Settings → Actions → Runners → New self-hosted runner*, servono Python 3.12 e Git Bash) e crea la variabile
  di repository `MONITOR_RUNNER` = `self-hosted`. Senza la variabile il workflow continua a usare `ubuntu-latest`.
- **Amazon** a volte risponde ai server GitHub con una pagina "Continua con gli acquisti" e il CAP non si imposta:
  lo scraper ora riprova una volta con un contesto nuovo dopo 45 secondi invece di saltare il giro.
- Ogni giro sostituisce i dati della stessa ora per i siti controllati (nessun doppione se lo rilanci a mano).
- Il file `data/diagnostica_ultimo_giro.txt` riporta titolo e inizio del testo delle pagine che non hanno
  restituito offerte: serve a capire subito se si tratta di un blocco o di un cambio di layout.
- **I cron di GitHub non sono puntuali**: dal 21 al 27/11, con un cron ogni 3 ore, sono partiti 17 giri su 56.
  Per questo il workflow ora ha due cron all'ora (minuto 7 e 37): se uno viene saltato, parte l'altro.
- I cron di GitHub Actions possono partire con qualche minuto di ritardo e vengono sospesi dopo 60 giorni senza
  attività nel repository (i commit orari dei dati lo tengono attivo).
- Se i siti cambiano layout, i parser in `monitor/scrapers/` vanno aggiornati: i test in `tests/` usano testi
  reali delle pagine (`pytest`).

## Aggiungere un modello

1. In `config.yaml` aggiungi la voce in `models` (es. `key: 17pro-256`).
2. Aggiungi le soglie in `thresholds`, gli ASIN Amazon (o lascia che li trovi la ricerca), la pagina modello
   Back Market e TrenDevice.
