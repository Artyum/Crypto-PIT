# Portfel

[Spis dokumentacji](README.md)

Zakładka **Portfel** to lista pozycji zapisanych osobno od transakcji. Pozycja ma symbol, identyfikator coina, lokalizację i ilość. Wycena w oknie jest liczona z kursu pobranego dla tej pozycji. Te pozycje nie wchodzą do [rozliczenia lat](rozliczenie-lat.md) ani do [pól PIT-38](pit-38.md).

## Pozycje

**Dodaj…**, **Edytuj…**, **Usuń** i dwuklik dotyczą zaznaczonej pozycji. Bez zaznaczenia edycja i usuwanie pokazują „Wybierz pozycję.”

Okno pozycji:

1. Pole wyszukiwania. Podpowiedź w oknie: „Wpisz ticker lub nazwę (np. BTC)”. **Szukaj** albo Enter wysyła zapytanie do CoinGecko.
2. Lista wyników. Wiersz ma postać `SYMBOL — nazwa (id)`, na przykład z identyfikatorem coina z API.
3. **Lokalizacja** — wymagany tekst. Puste pole kończy się komunikatem „Podaj lokalizację.”
4. **Ilość** — liczba nieujemna. Zapis bez wybranego coina pokazuje „Wybierz coin z listy.”

Para identyfikator coina i lokalizacja jest unikalna. Drugi zapis tej samej pary pokazuje: „{symbol} w lokalizacji „{lokalizacja}” jest już na liście.” Ten sam coin z inną lokalizacją jest osobną pozycją.

Usuwanie pyta: „Usunąć {symbol} ({lokalizacja}) z portfela?”

## Kursy

Kolumny: Waluta, Lokalizacja, Ilość, Wartość USD, Wartość PLN, Status.

Przy pierwszym wejściu na zakładkę, gdy są pozycje, program pobiera kursy. **Odśwież teraz** pobiera je ponownie. Puste portfolio i ten przycisk ustawiają status „Brak pozycji — dodaj coiny.”

Zapytanie o kursy zawiera identyfikatory coinów (`ids`) oraz waluty `usd,pln`. Wartość USD wiersza to ilość razy kurs USD. Wartość PLN wiersza to ilość razy kurs PLN. Do sumy pod tabelą wchodzą tylko wiersze ze statusem OK. Napis ma postać „Pozycje: … | Suma: … USD | … PLN”.

Status wiersza:

| Stan | Status |
| --- | --- |
| Trwa pobieranie | Pobieranie… |
| Kurs jeszcze nie był pobierany | Oczekuje na kurs |
| Po pobraniu brak ceny w pamięci | Brak kursu |
| API nie ma tego coina | Nieznany coin / brak w API |
| Brak jednego z kursów USD albo PLN | Brak kursu USD lub PLN |
| Oba kursy są | OK |
| Błąd połączenia, limit 429 albo inny status HTTP przy kursach | ten komunikat błędu w kolumnie Status |

Po zakończeniu pobierania kursów pasek narzędzi pokazuje „Kursy zaktualizowane”. Błąd wyszukiwania coina jest osobnym oknem z komunikatem z zapytania (połączenie, limit 429 albo status HTTP). Lista wyszukiwania ma najwyżej 40 pozycji.

Kursy są trzymane w pamięci programu do zamknięcia okna. W bazie zostają identyfikator coina, symbol, ilość i lokalizacja. Po ponownym uruchomieniu kursy są pobierane znowu przy wejściu na zakładkę.

Powrót do [spisu](README.md).
