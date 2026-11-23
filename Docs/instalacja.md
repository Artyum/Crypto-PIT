# Instalacja i uruchomienie

[Spis dokumentacji](README.md)

## Wymagania

- **Python 3.12** albo nowszy. Na Windows wygodnie przez instalator z [python.org](https://www.python.org/downloads/) z opcją dodania `py` do PATH.
- Biblioteka **Tkinter**. Na Debianie i Ubuntu pakiet systemowy to `python3-tk`:

  ```bash
  sudo apt install python3-tk
  ```

- Połączenie z internetem tylko wtedy, gdy pobierasz kurs NBP albo wycenę z CoinGecko.

Kod programu importuje `requests`. `requirements.txt` zawiera zależność uruchomieniową, a dokładne wersje przejściowe są w `requirements.lock`. Narzędzia `pytest`, `pytest-cov`, `ruff`, `basedpyright` i `pip-audit` są w `requirements-dev.txt`.

## Windows — najprościej

W katalogu projektu (tam, gdzie leży `start_app.ps1`):

```powershell
.\start_app.ps1
```

Skrypt:

1. tworzy lokalne środowisko `.venv`, jeśli go jeszcze nie ma (`py -3`, a w razie braku `python`);
2. instaluje pakiety z `requirements.txt`;
3. uruchamia okno programu przez `pythonw`.

Dodatkowe argumenty są przekazywane do programu, na przykład inna baza:

```powershell
.\start_app.ps1 --db D:\dane\moja-baza.db
```

Jeśli Python nie jest w PATH, pojawi się okno z komunikatem błędu. Wtedy zainstaluj Pythona albo uruchom ręcznie według kroków poniżej.

## Windows — ręcznie

```powershell
py -3 -m venv .venv
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m crypto_pit
```

Ten sam efekt daje `python crypto-pit.py` po aktywacji środowiska (albo z pełną ścieżką do interpretera w `.venv`).

## Linux i macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m crypto_pit
```

Gdy `import tkinter` kończy się błędem, doinstaluj Tkintera. Na Debianie i Ubuntu pakiet nazywa się `python3-tk`.

## Sposoby uruchomienia

Polecenia zakładają aktywne środowisko albo interpreter z `.venv`.

| Tryb | Polecenie | Efekt |
| --- | --- | --- |
| Okno programu | `python -m crypto_pit` | Zakładki: Transakcje, DCA, Portfel, Rozliczenie lat, Pola PIT-38 |
| Podsumowanie w terminalu | `python -m crypto_pit --cli` | Wypisuje rozliczenie każdego roku w terminalu |
| Inna baza | `python -m crypto_pit --db sciezka/do/pliku.db` | Zapis w podanym pliku SQLite |
| Cienki launcher | `python crypto-pit.py` | To samo co `python -m crypto_pit` |

Przełączniki `--cli` i `--db` można podać razem:

```powershell
.\.venv\Scripts\python -m crypto_pit --cli --db data\kopia.db
```

## Gdzie lądują dane

Jeśli w projekcie istnieje `data/crypto_pit.db`, program nadal używa tego pliku. W przeciwnym razie tworzy bazę w katalogu danych użytkownika: `%LOCALAPPDATA%\Crypto-PIT\crypto_pit.db` w Windows. Katalog `data/` i pliki `*.db` są w `.gitignore`. Import kopii zapasowej wymaga poprawnych wartości i odrzuca uszkodzone wiersze przed zmianą bazy.

Nowa baza jest pusta. Wpisy dodaje się w oknie programu albo wczytuje z [backupu ZIP](eksport-i-backup.md).

Gdy `start_app.ps1` nie znajdzie Pythona, pokazuje okno: „Nie znaleziono Pythona. Zainstaluj Python 3 lub upewnij sie, ze 'py' / 'python' jest w PATH.”

Powrót do [spisu](README.md).
