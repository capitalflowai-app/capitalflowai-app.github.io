# CapitalFlowAI — strona publiczna

Jeden plik `index.html` (strona) + `zbieraj_dane.py` (zbieranie danych wymagających klucza).
GitHub Actions co 20 minut uruchamia skrypt, składa stronę z katalogiem `data/` i publikuje ją na GitHub Pages.
Widz nie wpisuje żadnych kluczy — dane z SoSoValue (napływy ETF) i Finnhub (okres DZIŚ) leżą w `data/*.json`.
Pozostałe źródła (OECD, BIS, US Treasury, Bundesbank, EBC/Frankfurter, Bank Światowy, CoinGecko, DefiLlama, CoinPaprika)
strona pobiera sama, w przeglądarce widza — bez klucza.

Klucze: Settings → Secrets and variables → Actions: `SOSOVALUE_KEY`, `COINGECKO_KEY`, `FINNHUB_KEY`, `TWELVEDATA_KEY`, `COINMARKETCAP_KEY`, `FRED_KEY` (wartości nigdy w repozytorium; zbieracz maskuje je w komunikatach).
Uwaga: GitHub wyłącza harmonogram po 60 dniach bez żadnego commitu w repozytorium — wystarczy wtedy dowolna zmiana (np. nowa wersja strony).
Nowa wersja strony: uruchom `opublikuj-strone.command` w katalogu CapitalFlowAI (kopiuje `strona/index.html`, robi commit i push).

Adres strony od 24.09.2026: https://capitalflowai-app.github.io/ (repozytorium przeniesione na konto `capitalflowai-app`
i nazwane `capitalflowai-app.github.io`, więc jest to strona użytkownika bez ścieżki w adresie). Stary adres
`cryptoportalpwpw.github.io/capitalflowai` już nie działa.

## Service Worker (v351)

Plik `sw.js` (kopiowany do `_site/` w kroku „Złóż stronę”, rejestrowany w `index.html`) przyspiesza powroty na stronę:
czcionki, obrazki, słowniki języków i skrypt licznika wchodzą z pamięci przeglądarki (w tle odświeżane po godzinie).
Strona (HTML) i pliki `data/*.json` są zawsze pobierane najpierw z sieci — świeżość danych jest taka sama jak bez Service Workera;
kopia z pamięci pojawia się tylko wtedy, gdy sieć w ogóle nie odpowiada, a strona pokazuje wtedy pasek z datą i wiekiem kopii.
Service Worker nie dotyka obcych domen (źródeł danych ani licznika odwiedzin) i niczego nie wysyła.
Wydanie: publikacja podstawia pod `__WYDANIE__` skrót zawartości złożonej strony; pamięć nazywa się `cf-<skrót>`, stare pamięci `cf-*` są kasowane.

Wyłączniki awaryjne:
- u jednego widza: adres strony z dopiskiem `?sw=off` (wyrejestrowuje Service Workera, kasuje pamięć `cf-*` i zapamiętuje wybór w kluczu `cf-sw-off`);
  `?sw=on` przywraca;
- dla wszystkich: w `sw.js` zmienić `WYLACZONY` na `true` i opublikować (przeglądarki sprawdzają ten plik przy każdym wejściu;
  wyłączony Service Worker nie przechwytuje niczego, kasuje pamięci `cf-*` i sam się wyrejestrowuje).

Kontrola dzienna sprawdza, że `sw.js` na żywej stronie odpowiada (HTTP 200).

Automat działa sam w chmurze GitHub; od v354 raz w tygodniu pilnuje go przepływ „Strażnik harmonogramów” (dba o aktywność repozytorium — commit po 30 dniach ciszy — i próbuje włączyć przepływy wyłączone przez GitHub). Opis, co robić gdy coś stanie, i jak odtworzyć dane: `docs/ODTWORZENIE.md`.
