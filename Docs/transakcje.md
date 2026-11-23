# Transakcje

[Spis dokumentacji](README.md)

Zakładka **Transakcje** to lista zapisanych transakcji. Z niej liczone jest [rozliczenie lat](rozliczenie-lat.md) i [pola PIT-38](pit-38.md).

## Lista

Na górze są filtry **Rok** i **Typ**. Typ ma wartości: Wszystkie, Kupno, Sprzedaż, Inne. Przyciski **Dodaj…**, **Edytuj…** i **Usuń** są też w menu **Transakcje**. Dwuklik wiersza otwiera edycję. Bez zaznaczenia edycja i usuwanie pokazują „Wybierz transakcję.”

Kolumny: Lp., Giełda, Data, Typ, Walor, Ilość, Waluta, Wartość, Cena, Kurs, Wartość PLN, Prowizja PLN, Prowizja (walor), Finalna ilość.

Pod tabelą jest tekst w postaci „Widoczne: … | suma przychodów: … PLN | suma kosztów: … PLN”. Sumy przychodu i kosztu widocznych wierszy są zaokrąglone do 2 miejsc po przecinku.

Usunięcie transakcji pyta: „Usunąć transakcję Lp. …?”. Przy zaznaczonym **Zatwierdzone** program pokazuje: „Transakcja jest zatwierdzona. Odznacz „Zatwierdzone” w edycji, aby ją usunąć.” i zostawia wpis na liście.

## Nowa transakcja

Okno ma sekcje **Podstawowe dane**, **Dane transakcji**, **Wyniki (automatycznie)** i **Opis / uwagi**.

### Podstawowe dane

- **Giełda** — lista tylko do odczytu: Binance, Coinbase, Kanga, Kraken, OKX, Zonda. Od giełdy i typu zależy, które pola są widoczne.
- **Typ** — w tym oknie tylko Kupno albo Sprzedaż.
- **Data i godzina** — format `RRRR-MM-DD GG:MM`. Przycisk **Wybierz…** otwiera okno „Wybór daty i godziny”. Rok z tej daty jest rokiem podatkowym wpisu.
- **Walor** — wpisywany tekst jest od razu zamieniany na wielkie litery.
- **Waluta** — lista: PLN, USD, EUR, GBP, CHF. Pole można też wpisać ręcznie.
- **Kurs** — złote za 1 jednostkę waluty. Dla PLN program ustawia `1`, wyłącza pole kursu i przycisk **NBP** oraz pokazuje „Dla PLN kurs = 1”.
- **Wartość** — kwota w wybranej walucie. Przy kupnie etykieta to „Wartość”, a podpowiedź: „Pełna kwota obciążenia konta (z prowizją w walucie).” Przy sprzedaży etykieta to „Wartość sprzedaży brutto”, a podpowiedź: „Kwota uzyskana ze sprzedaży przed potrąceniem prowizji.”

Gdy w polu wartości albo w polu wejściowym profilu jest tekst, przy etykiecie pojawia się gwiazdka.

### Kurs NBP

Przycisk **NBP** pobiera kurs średni z tabeli A. Dzień końcowy zakresu to dzień poprzedzający datę transakcji. Program pyta API o tabele z 10 dni kończących się tym dniem i bierze najnowszą. Gdy w tym zakresie nie ma tabeli, pokazuje błąd. Przejściowy błąd bramki (odpowiedź 404 ze stroną HTML) jest ponawiany.

Po udanym pobraniu obok kursu widać skrót „NBP: 1 … = … PLN (data tabeli)” oraz przycisk **i**. Przycisk **i** pokazuje nazwę waluty, kurs średni, datę tabeli, numer tabeli i datę, od której zaczęło się szukanie.

Gdy pobranie się nie uda, program pokazuje treść błędu i dopisek „Możesz wpisać kurs ręcznie.”

Wartość w PLN to wpisana wartość pomnożona przez kurs, zaokrąglona do 2 miejsc. Tak samo prowizja w walucie i cena są przeliczane na PLN.

Pobranie idzie w osobnym wątku. Na czas oczekiwania przycisk **NBP** pokazuje „…”.

### Dane transakcji

Widoczne pola zależą od giełdy i typu. Nazwy w oknie:

| Giełda | Kupno | Sprzedaż |
| --- | --- | --- |
| Binance, Coinbase, Kraken, OKX | Finalna ilość waloru, Prowizja (waluta) | Ilość waloru, Prowizja (waluta) |
| Zonda | Ilość waloru, Prowizja (walor) | Ilość waloru, Prowizja (waluta) |
| Kanga | Finalna ilość waloru, Prowizja (walor) | pola profilu ukryte; zapis pokazuje „Brak profilu kalkulacji dla Kanga / Sprzedaż” |

Dla Kangi i sprzedaży zapis pokazuje: „Brak profilu kalkulacji dla Kanga / Sprzedaż”.

Sekcja **Wyniki (automatycznie)** pokazuje: Cena, Cena PLN, Wartość, Wartość PLN, Prowizja (w walucie), Prowizja PLN, Ilość waloru, Finalna ilość. Zapis bez wyliczonego wyniku pokazuje: „Uzupełnij pola tak, aby dało się wyliczyć wartość i ilość”. Wyliczenie wymaga wartości większej od zera, nieujemnej prowizji, dodatniej ilości, dodatniej ceny, dodatniej finalnej ilości i kursu większego od zera.

### Opis i zatwierdzenie

**Opis / uwagi** jest zapisywane przy transakcji i trafia do kolumny „Uwagi” w [eksporcie](eksport-i-backup.md).

**Zatwierdzone** blokuje pola okna (giełdę, typ, datę, walor, walutę, kurs, wartość, pola profilu i uwagi). Odznaczenie z powrotem je odblokowuje. Usunięcie z listy działa po odznaczeniu tego pola w edycji.

## Kwoty używane w rozliczeniu

Rozliczenie sumuje kwoty z transakcji w roku.

| Typ | Przychód | Koszt roku |
| --- | --- | --- |
| Kupno | 0 | wartość bezwzględna wartości w PLN |
| Sprzedaż | wartość bezwzględna wartości w PLN | wartość bezwzględna prowizji w PLN |
| Inne | 0 | 0 |

Typ **Inne** jest w filtrze listy. Do bazy trafia z [importu backupu](eksport-i-backup.md), gdy kolumna Typ jest pusta, ma wartość `inne` / `other`, albo inną wartość spoza kupna i sprzedaży. W oknie dodawania typ to Kupno albo Sprzedaż.

Szczegóły przenoszenia kosztów między latami są w [rozliczeniu lat](rozliczenie-lat.md).

Powrót do [spisu](README.md).
