# Pola PIT-38

[Spis dokumentacji](README.md)

Zakładka **Pola PIT-38** pokazuje kwoty z [rozliczenia lat](rozliczenie-lat.md). Nagłówek ramki to „PIT-38 część E — waluty wirtualne”. Numery pól są przypisane w programie.

Wybierz **rok podatkowy**. Numery pól zależą od roku formularza:

| Wybrany rok | Numery pól |
| --- | --- |
| do 2024 włącznie | 34–38 |
| od 2025 | 36–40 |

## Pola pokazywane w programie

Kolejność wierszy jest taka sama w obu numeracjach. W tabeli niżej numery od 2025; dla roku wcześniejszego program używa numerów mniejszych o 2.

| Pole od 2025 | Pole do 2024 | Opis | Skąd bierze się kwota |
| --- | --- | --- | --- |
| 36 | 34 | Przychód | suma sprzedaży |
| 37 | 35 | Koszty poniesione w roku podatkowym | kupna i prowizje sprzedaży tego roku |
| 38 | 36 | Koszty z lat ubiegłych, niepotrącone w poprzednim roku | przeniesione z poprzedniego rozliczenia |
| 39 | 37 | Dochód | przychód minus koszty razem; 0, gdy koszty są większe |
| 40 | 38 | Koszty niepotrącone w roku | koszty razem minus przychód; 0, gdy przychód jest większy albo równy |

Gdy przychód i koszty razem są równe, dochód i koszty do przeniesienia wynoszą 0. Gdy jedna z tych kwot jest większa od zera, druga wynosi 0.

Wiersz **Podatek 19%** ma w kolumnie numeru „—”. Wzór przy tym wierszu to „poza częścią E — orientacyjnie”. Kwota to 19% dochodu, zaokrąglone do pełnych złotych.

Stopka zakładki podaje zakres numerów dla wybranego roku i tekst: „Numery pól (…) odpowiadają pozycjom w wierszu walut wirtualnych w części E PIT-38. Podwójne kliknięcie wartości kopiuje ją do schowka.”

## Kopiowanie

Podwójne kliknięcie wartości kopiuje ją do schowka w postaci z przecinkiem dziesiętnym, bez spacji przy tysiącach (na przykład `1234,50`). Stopka zmienia się wtedy na „Skopiowano do schowka: …”. Widok w tabeli zostaje z odstępem przy tysiącach.

Powrót do [spisu](README.md).
