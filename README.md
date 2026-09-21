# Crypto-PIT

Aplikacja desktopowa do ewidencji transakcji kryptowalut i przygotowania kwot do **PIT-38** (część E — przychody z kapitałów pieniężnych, w tym z odpłatnego zbycia walut wirtualnych).

Dane trzymane są lokalnie w SQLite. Program nie wysyła Twojej historii transakcji nigdzie poza dwoma opcjonalnymi zapytaniami: kurs waluty z API NBP oraz wycena portfela z CoinGecko.

## Zastrzeżenie

To narzędzie pomocnicze, **nie poradnictwo podatkowe**. Numeracja pól PIT-38, zaokrąglenia i sposób ujęcia kosztów mogą się zmieniać wraz z formularzem i interpretacjami. Przed złożeniem zeznania zweryfikuj wyniki samodzielnie albo z księgowym. Autorzy nie ponoszą odpowiedzialności za decyzje podatkowe podjęte na podstawie tego programu.

## Co robi program

- **Transakcje** — ręczne dodawanie kupna i sprzedaży z profilami giełd (Binance, Coinbase, Kanga, Kraken, OKX, Zonda). Dla wybranej giełdy program dolicza ilość, cenę, prowizję w walorze i wartości w PLN.
- **Kurs NBP** — dla waluty innej niż PLN pobiera kurs średni z tabeli A z dnia poprzedzającego transakcję (z cofnięciem o dni wolne).
- **Portfel** — stany walorów według lokalizacji, z opcjonalną wyceną USD/PLN z CoinGecko.
- **Rozliczenie lat** — przychód ze sprzedaży, koszty roku, koszty przeniesione z lat ubiegłych, dochód albo koszty do przeniesienia, orientacyjny podatek 19%.
- **Pola PIT-38** — mapowanie na część E (numery pól zależą od roku: do 2024 to 34–38, od 2025 to 36–40).
- **Eksport CSV** — raport transakcji i rozliczeń (separator `;`, przecinek dziesiętny).
- **Backup ZIP** — eksport i import transakcji oraz portfela (import **zastępuje** całą bazę).

## Wymagania

- **Python 3.12+** (na Windows wygodnie przez instalator python.org z `py` w PATH)
- Biblioteka **Tkinter** (w instalatorze Windows jest zazwyczaj wbudowana; na Debian/Ubuntu: `python3-tk`)
- Połączenie z internetem tylko do kursów NBP i CoinGecko

Zależności runtime: `requests`. Narzędzia deweloperskie: `ruff`, `basedpyright`, `pytest`, `pytest-cov`, `pip-audit`.

## Szybki start (Windows)

W katalogu projektu:

```powershell
.\start_app.ps1
```

Skrypt utworzy `.venv`, zainstaluje `requirements.txt` i uruchomi GUI przez `pythonw` (bez okna konsoli).

Ręcznie:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python -m crypto_pit
```

Albo: `python crypto-pit.py`.

## Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m crypto_pit
```

Na Linuxie zainstaluj pakiet Tkinter systemu, jeśli `import tkinter` kończy się błędem.

## Uruchomienie

| Tryb | Polecenie |
| --- | --- |
| GUI | `python -m crypto_pit` |
| Tylko podsumowanie lat w terminalu | `python -m crypto_pit --cli` |
| Inna baza SQLite | `python -m crypto_pit --db sciezka/do/pliku.db` |

Domyślna baza: `data/crypto_pit.db` (katalog `data/` jest w `.gitignore` i **nie trafia** na GitHub).

## Jak liczone jest PIT

Kwoty w zeznaniu są zaokrąglane do pełnych złotych (od 50 gr w górę).

Dla każdej transakcji:

- **Kupno** — kosztem podatkowym jest wartość w PLN obciążenia konta (`value_pln`, zwykle z prowizją w cenie nabycia).
- **Sprzedaż** — przychodem jest wartość sprzedaży w PLN; kosztem roku jest prowizja sprzedaży w PLN.
- **Inne** — nie wchodzi do przychodu ani kosztów PIT.

Rozliczenie idzie chronologicznie po latach kalendarzowych:

1. Przychód roku = suma przychodów ze sprzedaży.
2. Koszty bieżące = koszty kupna + prowizje sprzedaży w tym roku.
3. Do kosztów doliczane są koszty nierozliczone z lat poprzednich.
4. Jeśli koszty > przychód: dochód = 0, nadwyżka przechodzi na następny rok.
5. W przeciwnym razie: dochód = przychód − koszty, nic nie przechodzi dalej.
6. Podatek 19% jest **orientacyjny** (poza częścią E formularza).

To uproszczenie FIFO/identyfikacji konkretnych partii — program sumuje wartości, nie paruje każdej sprzedaży z konkretnym zakupem.

### Profile giełd (autokalkulacja)

Użytkownik podaje m.in. giełdę, typ, datę, walor, walutę i wartość. Reszta zależy od profilu:

| Giełda | Kupno (pola źródłowe) | Sprzedaż |
| --- | --- | --- |
| Binance, Coinbase, Kraken, OKX | prowizja w walucie + finalna ilość | ilość + prowizja w walucie |
| Zonda | ilość + prowizja w walorze | ilość + prowizja w walucie |
| Kanga | finalna ilość + prowizja w walorze | — (brak profilu sprzedaży) |

`value_pln = value × kurs NBP` (dla PLN kurs = 1).

## Prywatność i dane

- Baza i backupy zawierają Twoją historię — **nie commituj** plików `.db`, katalogu `data/` ani ZIP-ów z backupem.
- Kursy: NBP (`api.nbp.pl`) i CoinGecko (`api.coingecko.com`) — bez klucza API.
- Aplikacja nie ma kont, chmury ani telemetrii.

## Struktura repozytorium

```
crypto-pit.py          # cienki launcher
crypto_pit/
  __main__.py          # CLI / GUI
  config.py            # ścieżka bazy, stawka 19%
  domain/              # modele, PIT-38, profile giełd
  infrastructure/      # SQLite
  services/            # rozliczenie, NBP, CoinGecko, CSV, backup
  gui/                 # Tkinter
tests/
start_app.ps1
run_tests.ps1
run_lint_check.ps1
run_audit.ps1 / run_audit.sh
```

## Testy, lint, audyt zależności

Wymagane lokalne `.venv`.

```powershell
.\run_tests.ps1
.\run_lint_check.ps1
.\run_audit.ps1
```

Na Linuxie / macOS:

```bash
python -m pytest tests/ -v --tb=line --cov=crypto_pit --cov-report=term-missing
chmod +x run_audit.sh
./run_audit.sh
```

- **Testy** — rozliczenie PIT, profile giełd, pola PIT-38, backup, migracja schematu.
- **Lint** — Ruff (format + check) i basedpyright; log w `report/lint_check.log`.
- **Audit** — aktualizuje `pip`, potem `pip-audit` na `requirements.txt` i na pakietach w `.venv`; log w `report/audit.log`. Katalog `report/` jest ignorowany przez git.

Pojedynczy plik testów: `.\run_tests.ps1 tests\test_tax_calculation.py`.

## Publikacja na GitHub

Repozytorium jest gotowe do publicznego zdalnego originu. Nie wypychaj:

- `data/`, `*.db`, backupów ZIP
- `report/`, `.venv`, `.coverage`
- katalogu `! Docs/` (notatki lokalne, m.in. ścieżki na dysku)

Po utworzeniu pustego repozytorium na GitHubie:

```powershell
git remote add origin https://github.com/<UZYTKOWNIK>/Crypto-PIT.git
git push -u origin main
```

## Licencja

[MIT](LICENSE)
