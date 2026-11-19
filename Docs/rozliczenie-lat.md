# Rozliczenie lat

[Spis dokumentacji](README.md)

Zakładka **Rozliczenie lat** pokazuje jeden wiersz na każdy rok kalendarzowy od najstarszej do najnowszej transakcji. Lata pomiędzy, w których nie było transakcji, też są na liście, żeby koszty mogły się przenieść.

Kliknięcie wiersza ustawia ten sam rok na zakładce [Pola PIT-38](pit-38.md).

## Kolumny

Kwoty w tej tabeli są zaokrąglone do pełnych złotych: od 0,50 w górę (`ROUND_HALF_UP`).

| Kolumna | Znaczenie |
| --- | --- |
| Przychód | Suma przychodów ze sprzedaży w roku |
| Koszty roku | Koszty kupna plus prowizje sprzedaży w tym roku |
| Koszty lat ub. | Koszty nierozliczone, przeniesione z poprzedniego roku |
| Razem | Koszty roku + koszty lat ubiegłych |
| Dochód | Przychód minus koszty razem, albo 0 gdy koszty są wyższe |
| Do przeniesienia | Nadwyżka kosztów nad przychodem, która przechodzi na kolejny rok |
| Podatek 19% | Orientacyjna kwota od dochodu. Nie jest polem części E |
| Liczba transakcji | Wszystkie wpisy z tego roku, także typ „Inne” |

## Kolejność liczenia

Dla każdego roku po kolei:

1. Przychód = suma wartości sprzedaży w PLN.
2. Koszty bieżące = suma wartości kupna w PLN oraz prowizji sprzedaży w PLN.
3. Do kosztów doliczane są koszty nierozliczone z lat poprzednich.
4. Gdy koszty razem są większe niż przychód: dochód = 0, różnica przechodzi na następny rok.
5. W przeciwnym razie: dochód = przychód − koszty razem i nic nie przechodzi dalej.
6. Podatek 19% jest liczony od dochodu i zaokrąglany do pełnych złotych.

Program sumuje wartości z [transakcji](transakcje.md) w każdym roku. Nie wiąże sprzedaży z konkretnym kupnem.

W terminalu `python -m crypto_pit --cli` dla każdego roku wypisywane są: przychód, koszty bieżące, koszty lat ubiegłych, dochód, koszty do przeniesienia i podatek 19%. Kolumn Razem i Liczba transakcji w tym wydruku nie ma.

Powrót do [spisu](README.md).
