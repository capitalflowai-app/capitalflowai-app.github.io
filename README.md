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

## Szybkość strony, etap 5 (v412)

- Pierwszy widok: lista plików kafelków i mapy (T0: oecd, rynki, ceny, kursy, dzis, krypto, cmc, surowce, nastroj, etf, meta) jest w jednym miejscu (`srvJSON.t0` w `index.html`). Na starcie każdy inny plik `data/*.json` i `archiwum/seria.json` idzie z `priority:'low'`; faza kończy się po pobraniu T0 (najpóźniej po 8 s), przy otwarciu CRYPTO/TRENDÓW i od razu przy `?pelna=1`. Kafelki Złoto i Ropa Brent (od v321) rysują się dopiero po `surowce.json`, dlatego jest w T0.
- Komentarze programisty są wycinane tylko z opublikowanej kopii (`narzedzia/bez_komentarzy.py`, krok „Złóż stronę” w `strona.yml`): tokenizator JavaScriptu, ten sam ciąg tokenów, składnia sprawdzona w silniku JS; błąd = zostaje wersja z komentarzami i ostrzeżenie. Źródło w repozytorium zostaje z komentarzami. W opublikowanej stronie `<meta name="cf-wydanie">` podaje skrót commitu, który jest na żywo (numery wersji z komentarzy nie są już w opublikowanym kodzie).

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
