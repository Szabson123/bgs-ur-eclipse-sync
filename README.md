# BGS-ur-eclipse-sync

Mikroserwis dla **BGS::UR → Licznik cykli** (UR::Cycle Guard), bliźniak BGS-ur-analitycs (FastAPI + pyodbc).

Co minutę (APScheduler) sprawdza w Eclipse najnowszy `NumQA` dla każdego BoxingCode z kanałów stanowisk
i przekazuje go do BGS. **Zmiana NumQA = nowa paczka QA → BGS zeruje licznik tego kanału** (polecenie dla
aplikacji master na stanowisku, zdarzenie „Nowa paczka QA w Eclipse” w Historii).

```
BGS  GET  /api/ur/cycle-guard/eclipse/channels/   →  BoxingCode kanałów aktywnych stanowisk
Eclipse   SELECT BoxingCode, MAX(NumQA) FROM [Eclipse].[qav].[Batch] WHERE BoxingCode IN (...) GROUP BY BoxingCode
BGS  POST /api/ur/cycle-guard/eclipse/num-qa/     →  {kod: baseline | unchanged | reset | unknown | inactive}
```

- Jedno zapytanie do Eclipse na wszystkie kanały, bez `NOLOCK` (wycofana paczka nie wyzeruje licznika).
- O zerowaniu decyduje BGS: pierwszy odczyt kodu to tylko punkt odniesienia, każdy inny NumQA niż poprzedni
  zeruje kanał. Zmiana BoxingCode kanału w panelu ustawia punkt odniesienia od nowa.
- Kody bez żadnej paczki w Eclipse są pomijane (ostrzeżenie w logu).
- Błąd Eclipse / BGS nie zatrzymuje harmonogramu – widać go w `/health`, następne odpytanie próbuje znowu.
  Odpytania nie nakładają się (`max_instances=1`), zaległe nie nadrabiają się seriami (`coalesce`).

## Endpointy

| | |
|---|---|
| `GET /health` | `status` (ok / error / starting), czas ostatniego odpytania i sukcesu, błąd, liczba kanałów, wyniki, ostatnie zerowania |
| `POST /sync/run` | odpytanie natychmiast, np. po dodaniu kanału w panelu |

## Konfiguracja (`.env`, wzór w `.env.example`)

- `ECLIPSE_HOST`, `ECLIPSE_NAME`, `ECLIPSE_USER`, `ECLIPSE_PASSWORD` – jak w BGS-ur-analitycs (ODBC Driver 18).
- `BGS_URL` – adres bazowy BGS-backend bez `/api`, np. `http://127.0.0.1:8000`.
- `BGS_API_KEY` – ten sam klucz co `CYCLE_GUARD_ECLIPSE_API_KEY` w `.env` BGS-backend
  (pusty klucz w backendzie = endpointy serwisu wyłączone).
- `SYNC_INTERVAL_SECONDS` (60), `SYNC_ENABLED` (true).

## Uruchomienie

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m uvicorn main:app --port 8003
```

Porty BGS lokalnie: backend 8000, analytics 8001, konwerter 8002, ten serwis 8003.
Uruchamiaj **jeden** proces (bez `--workers`) – każdy worker miałby własny harmonogram.
