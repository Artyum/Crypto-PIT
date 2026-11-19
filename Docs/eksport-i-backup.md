# Eksport i backup

[Spis dokumentacji](README.md)

Polecenia są w menu **Plik**.

## Raport CSV

**Eksport raportu CSV…** zapisuje plik (domyślnie `pit38-raport.csv`):

- kodowanie UTF-8 z BOM;
- separator kolumn: średnik `;`;
- separator dziesiętny: przecinek.

W pliku są dwie sekcje:

1. **TRANSAKCJE** — kolumny: ID, Data, Typ, Walor, Ilość, Waluta, Kurs, Cena, Wartość PLN, Prowizja PLN, Prowizja (walor), Przychód PIT, Koszt PIT, Uwagi.
2. **ROZLICZENIE LAT (PIT-38)** — kolumny jak na zakładce [Rozliczenie lat](rozliczenie-lat.md): Rok, Przychód, Koszty roku, Koszty lat ub., Razem, Dochód, Do przeniesienia, Podatek 19%, Liczba transakcji.

Przywracanie danych do bazy idzie przez backup ZIP opisany niżej.

## Backup ZIP

**Eksport backupu…** zapisuje archiwum (domyślnie `crypto-pit-backup.zip`) z dwoma plikami CSV:

- `transactions.csv` — transakcje,
- `holdings.csv` — pozycje portfela (identyfikator coina, symbol, ilość, lokalizacja).

Po zapisie program podaje, ile rekordów trafiło do pliku.

**Import backupu…** czyta ZIP, a potem zastępuje transakcje i portfel w bieżącej bazie. Przed zapisem jest pytanie z liczbą rekordów w pliku i w obecnej bazie. Anulowanie nic nie zmienia. Po udanym imporcie listy są odświeżane, a komunikat brzmi „Przywrócono … transakcji i … pozycji portfela.”

Plik, który nie jest ZIP-em, kończy się komunikatem „Backup musi być plikiem ZIP (transakcje + portfel).” Archiwum bez `transactions.csv` albo bez `holdings.csv` kończy się komunikatem, że archiwum musi zawierać oba pliki. Gdy zapis do bazy zgłosi błąd, zmiana jest wycofywana i dotychczasowe transakcje oraz portfel zostają.

W imporcie pusta lokalizacja pozycji dostaje tekst „Nieokreślone”. Powtórzona para Coin ID i lokalizacja w pliku przerywa import komunikatem o duplikacie.

## Pliki i sieć

W bazie SQLite oraz w ZIP są transakcje i pozycje portfela.

`.gitignore` wyklucza katalog `data/`, pliki `*.db`, katalog `report/` i `.venv`. Okno zapisu CSV i ZIP pozwala wybrać dowolną ścieżkę. Pliki `*.csv` i `*.zip` nie są wpisane w `.gitignore`.

Program sam wysyła zapytania HTTP bez klucza API:

- `api.nbp.pl` — przycisk **NBP** w transakcji; w adresie jest kod waluty i data;
- `api.coingecko.com` — **Szukaj** w portfelu (tekst zapytania) oraz pobranie kursów (identyfikatory coinów, waluty `usd,pln`).

W menu **Pomoc → O programie** jest adres `https://github.com/Artyum`. Kliknięcie otwiera go w przeglądarce. Szczegóły uruchomienia są w [instrukcji instalacji](instalacja.md).

Powrót do [spisu](README.md).
