# CapitalFlowAI — strona publiczna

Jeden plik `index.html` (strona) + `zbieraj_dane.py` (zbieranie danych wymagających klucza).
GitHub Actions co 20 minut uruchamia skrypt, składa stronę z katalogiem `data/` i publikuje ją na GitHub Pages.
Widz nie wpisuje żadnych kluczy — dane z SoSoValue (napływy ETF) i Finnhub (okres DZIŚ) leżą w `data/*.json`.
Pozostałe źródła (OECD, BIS, US Treasury, Bundesbank, EBC/Frankfurter, Bank Światowy, CoinGecko, DefiLlama, CoinPaprika)
strona pobiera sama, w przeglądarce widza — bez klucza.

Klucze: Settings → Secrets and variables → Actions: `SOSOVALUE_KEY`, `FINNHUB_KEY`, `COINGECKO_KEY`.
Uwaga: GitHub wyłącza harmonogram po 60 dniach bez żadnego commitu w repozytorium — wystarczy wtedy dowolna zmiana (np. nowa wersja strony).
Nowa wersja strony: uruchom `opublikuj-strone.command` w katalogu CapitalFlowAI (kopiuje `strona/index.html`, robi commit i push).
