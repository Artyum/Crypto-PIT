# Dokumentacja Crypto-PIT

Instrukcja obsługi aplikacji desktopowej do ewidencji transakcji kryptowalut i przygotowania kwot do **PIT-38** (część E — waluty wirtualne).

Dane są w lokalnym pliku SQLite. Połączenia wychodzące, które program wykonuje sam, to kurs waluty z API NBP oraz wyszukiwanie i kursy coinów w CoinGecko. Do tych zapytań idzie kod waluty i data albo tekst wyszukiwania i identyfikatory coinów z portfela.

## Zastrzeżenie

Program liczy kwoty według reguł opisanych w tej dokumentacji. Przed złożeniem zeznania zweryfikuj wyniki samodzielnie albo z księgowym.

## Spis treści

| Dokument | O czym jest |
| --- | --- |
| [Instalacja i uruchomienie](instalacja.md) | Python, środowisko, Windows, Linux, macOS, tryb GUI i terminal |
| [Transakcje](transakcje.md) | Dodawanie kupna i sprzedaży, profile giełd, kurs NBP |
| [DCA](dca.md) | Średni koszt zakupu w wybranym zakresie dat |
| [Portfel](portfel.md) | Stany walorów według lokalizacji i wycena CoinGecko |
| [Rozliczenie lat](rozliczenie-lat.md) | Przychód, koszty, przeniesienie nadwyżki, podatek 19% |
| [Pola PIT-38](pit-38.md) | Mapowanie kwot na część E formularza |
| [Eksport i backup](eksport-i-backup.md) | Raport CSV, kopia ZIP, import i prywatność |

Powrót do [opisu projektu](../README.md).
