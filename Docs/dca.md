# DCA

[Spis dokumentacji](README.md)

Zakładka **DCA** pokazuje średni koszt zakupu wyliczony z transakcji typu **Kupno**. Wynik jest tylko na tej zakładce: program nie zapisuje go w rozliczeniu lat.

## Jak czytać wynik

Dla każdego waloru w wybranym zakresie dat:

- **Zakupy** — liczba transakcji kupna,
- **Suma PLN** — suma wartości w PLN (`value_pln`),
- **Ilość** — suma pola finalnej ilości (`final_coin`),
- **DCA PLN** — suma PLN podzielona przez ilość.

Kliknięcie wiersza pokazuje pod spodem poszczególne zakupy: datę, ilość, wartość w PLN i cenę jednostkową w PLN (wartość podzielona przez finalną ilość).

## Zakres dat

- **Rok** — „Wszystkie” ustawia zakres od daty pierwszego kupna do daty ostatniego kupna. Gdy nie ma żadnego kupna, pole „Data od” zostaje puste, a „Data do” dostaje dzisiejszą datę. Wybrany rok ustawia 1 stycznia–31 grudnia tego roku.
- **Data od** i **Data do** — dzień w formacie `RRRR-MM-DD`. Przycisk **Wybierz…** otwiera okno „Wybór daty i godziny”; do pola zapisywany jest sam dzień. Dzień końcowy jest wliczany.
- Gdy data od jest późniejsza niż data do, lista zostaje pusta i na dole pojawia się komunikat.

Do średniej wchodzi kupno, które ma symbol waloru, dodatnią wartość w PLN i dodatnią finalną ilość. Sprzedaż, typ Inne oraz kupna bez tych kwot nie wchodzą do wierszy.

Średnia używa wartości zapisanych przy transakcjach (`value_pln` i `final_coin`).

Komunikaty na dole po prawej: „Podaj datę do.”, „Podaj datę od.”, „Nieprawidłowa data.”, „Data od jest późniejsza niż data do.”, „Brak zakupów.”, „W tym zakresie nie ma zakupów.” Po lewej jest liczba zakupów wliczonych do tabeli.

Powrót do [spisu](README.md).
