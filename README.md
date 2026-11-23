# Crypto-PIT

Aplikacja desktopowa do ewidencji transakcji kryptowalut i przygotowania kwot do **PIT-38** (część E — przychody z kapitałów pieniężnych, w tym z odpłatnego zbycia walut wirtualnych).

Dane trzymane są lokalnie w SQLite. Program sam odpytuje API NBP o kurs waluty oraz CoinGecko o wycenę portfela i wyszukiwanie coinów.

## Zastrzeżenie

Program wylicza kwoty według reguł z tej dokumentacji. Numeracja pól PIT-38, zaokrąglenia i sposób ujęcia kosztów mogą się zmieniać wraz z formularzem i interpretacjami. Przed złożeniem zeznania zweryfikuj wyniki samodzielnie albo z księgowym.

## Co robi program

- **Transakcje** — ręczne dodawanie kupna i sprzedaży z profilami giełd (Binance, Coinbase, Kanga, Kraken, OKX, Zonda). Dla wybranej giełdy program dolicza ilość, cenę, prowizję w walorze i wartości w PLN.
- **Kurs NBP** — dla waluty innej niż PLN pobiera kurs średni z tabeli A. Pyta o zakres 10 dni kończący się w dniu poprzedzającym transakcję i bierze najnowszą tabelę z tego zakresu.
- **Portfel** — stany walorów według lokalizacji, z opcjonalną wyceną USD/PLN z CoinGecko.
- **Rozliczenie lat** — przychód ze sprzedaży, koszty roku, koszty przeniesione z lat ubiegłych, dochód albo koszty do przeniesienia, orientacyjny podatek 19%.
- **Pola PIT-38** — mapowanie na część E (numery pól zależą od roku: do 2024 to 34–38, od 2025 to 36–40).
- **Eksport CSV** — raport transakcji i rozliczeń (separator `;`, przecinek dziesiętny).
- **Backup ZIP** — eksport i import transakcji oraz portfela (import **zastępuje** całą bazę).

## Dokumentacja

Instrukcja po polsku, w katalogu [`Docs/`](Docs/README.md):

- [Instalacja i uruchomienie](Docs/instalacja.md)
- [Transakcje](Docs/transakcje.md)
- [DCA](Docs/dca.md)
- [Portfel](Docs/portfel.md)
- [Rozliczenie lat](Docs/rozliczenie-lat.md)
- [Pola PIT-38](Docs/pit-38.md)
- [Eksport i backup](Docs/eksport-i-backup.md)

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

Skrypt utworzy `.venv`, zainstaluje `requirements.txt` i uruchomi GUI przez `pythonw`.

Ręcznie:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m crypto_pit
```

Albo: `python crypto-pit.py`.

## Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m crypto_pit
```

Na Linuxie zainstaluj pakiet Tkinter systemu, jeśli `import tkinter` kończy się błędem.

## Uruchomienie

| Tryb | Polecenie |
| --- | --- |
| GUI | `python -m crypto_pit` |
| Podsumowanie lat w terminalu | `python -m crypto_pit --cli` |
| Inna baza SQLite | `python -m crypto_pit --db sciezka/do/pliku.db` |

Domyślna baza: istniejący plik `data/crypto_pit.db`, a gdy go nie ma — katalog danych użytkownika (`%LOCALAPPDATA%\Crypto-PIT\crypto_pit.db` w Windows). Katalog `data/` jest w `.gitignore`.

## Jak liczone jest PIT

Kwoty w zeznaniu są zaokrąglane do pełnych złotych (od 50 gr w górę).

Dla każdej transakcji:

- **Kupno** — kosztem podatkowym jest wartość bezwzględna pola `value_pln` (w oknie kupna podpowiedź mówi o pełnej kwocie obciążenia konta, z prowizją w walucie).
- **Sprzedaż** — przychodem jest wartość sprzedaży w PLN; kosztem roku jest prowizja sprzedaży w PLN.
- **Inne** — przychód i koszt roku wynoszą 0.

Rozliczenie idzie chronologicznie po latach kalendarzowych:

1. Przychód roku = suma przychodów ze sprzedaży.
2. Koszty bieżące = koszty kupna + prowizje sprzedaży w tym roku.
3. Do kosztów doliczane są koszty nierozliczone z lat poprzednich.
4. Jeśli koszty > przychód: dochód = 0, nadwyżka przechodzi na następny rok.
5. W przeciwnym razie: dochód = przychód − koszty, koszty do przeniesienia = 0.
6. Podatek 19% jest **orientacyjny** (wzór w programie: „poza częścią E — orientacyjnie”).

Program sumuje wartości w roku.

### Profile giełd (autokalkulacja)

Użytkownik podaje m.in. giełdę, typ, datę, walor, walutę i wartość. Reszta zależy od profilu:

| Giełda | Kupno (pola źródłowe) | Sprzedaż |
| --- | --- | --- |
| Binance, Coinbase, Kraken, OKX | prowizja w walucie + finalna ilość | ilość + prowizja w walucie |
| Zonda | ilość + prowizja w walorze | ilość + prowizja w walucie |
| Kanga | finalna ilość + prowizja w walorze | zapis pokazuje „Brak profilu kalkulacji dla Kanga / Sprzedaż” |

`value_pln = value × kurs NBP` (dla PLN kurs = 1).

## Prywatność i dane

- Baza i backupy zawierają historię transakcji i pozycje portfela. Pliki `.db`, katalog `data/` i ZIP-y z backupem zostają poza repozytorium.
- Kursy: NBP (`api.nbp.pl`) i CoinGecko (`api.coingecko.com`). Zapytania idą bez klucza API.

## Struktura repozytorium

```
Docs/                  # instrukcja obsługi (Markdown, widoczna na GitHubie)
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
run_all_checks.ps1
```

## Testy, lint, audyt zależności

Wymagane lokalne `.venv`.

```powershell
.\run_all_checks.ps1
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

- **Testy** — rozliczenie PIT, profile giełd, pola PIT-38, backup, migracja schematu; log w `report/tests.log`.
- **Lint** — `run_lint_check.ps1` formatuje kod, uruchamia `ruff check --fix` i basedpyright; log w `report/lint_check.log`.
- **Audit** — `pip-audit` na przypiętych plikach `requirements.txt` i `requirements-dev.txt`; log w `report/audit.log`. Katalog `report/` jest ignorowany przez git.

Pojedynczy plik testów: `.\run_tests.ps1 tests\test_tax_calculation.py`.

## Publikacja na GitHub

Repozytorium jest gotowe do publicznego zdalnego originu. Poza repozytorium zostają:

- `data/`, `*.db`, backupów ZIP
- `report/`, `.venv`, `.coverage`
- katalogu `! Docs/` (notatki lokalne, m.in. ścieżki na dysku)

Katalog [`Docs/`](Docs/README.md) to publiczna instrukcja i ma trafić do repozytorium. Folder `! Docs/` (z wykrzyknikiem w nazwie) to osobne notatki lokalne i jest w `.gitignore`.

Po utworzeniu pustego repozytorium na GitHubie:

```powershell
git remote add origin https://github.com/<UZYTKOWNIK>/Crypto-PIT.git
git push -u origin main
```

## Licencja

[MIT](LICENSE)
