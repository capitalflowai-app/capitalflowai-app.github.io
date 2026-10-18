# Jak CapitalFlowAI działa sam w GitHub — i co zrobić, gdy coś stanie

Dokument dla każdego, także dla osoby, która nie programuje. Stan na 13.10.2026 (wersja v354). To nie jest porada inwestycyjna.

## 1. Najważniejsze w trzech zdaniach

- Cała strona i wszystkie dane powstają w darmowej chmurze GitHub (GitHub Actions i GitHub Pages) — komputer właściciela nie jest do niczego potrzebny
  (służy tylko do pracy nad nowymi wersjami; wyłączony nic nie zatrzymuje).
- Automat sam się pilnuje: zegar zapasowy uruchamia przebieg, gdy harmonogram GitHuba stoi, kontrola co dzień sprawdza stronę i dane, a strażnik raz
  w tygodniu dba o to, żeby GitHub nie wyłączył harmonogramów z powodu braku aktywności (po 60 dniach bez żadnego commitu GitHub wyłącza takie przepływy).
- Adres strony: https://capitalflowai-app.github.io/ — repozytorium: `capitalflowai-app/capitalflowai-app.github.io` (publiczne). Kontakt: przycisk „Skontaktuj się” w zakładkach Źródła i Metodologia (wiadomość trafia do formularza właściciela; adresu e-mail nie ma w żadnym pliku strony).

## 2. Przepływy (katalog `.github/workflows/`) i ich rytm

| Plik | Nazwa w zakładce Actions | Rytm (czas UTC) | Co robi |
|---|---|---|---|
| `strona.yml` | Strona i dane | co 10 minut (7, 17, 27, 37, 47, 57 po pełnej godzinie) oraz po każdej zmianie w gałęzi main | testy → zbieranie danych → złożenie strony → publikacja na GitHub Pages; testy nieudane = publikacja staje (strona zostaje w ostatnim dobrym stanie) |
| `zegar.yml` | Zegar zapasowy | minuty 13, 33, 53 każdej godziny i na końcu każdego przebiegu strony | gdy harmonogram `strona.yml` stoi (zdarza się, GitHub nie uruchamia wszystkich terminów), uruchamia go ręcznie; uruchamia też kontrolę i archiwum, jeśli ich harmonogram nie ruszył; odblokowuje przebieg zawieszony w stanie „waiting” |
| `kontrola.yml` | Kontrola strony | codziennie 06:20 | sprawdza stronę, wiek plików danych, zgodność liczb z drugim źródłem, przebiegi i stan przepływów; wynik w `kontrola/ostatnia.md` |
| `archiwum.yml` | Archiwum własne | codziennie 01:20 | dopisuje dzienne wiersze do `archiwum/*.csv` (commit `[skip ci]`) |
| `straznik.yml` | Strażnik harmonogramów | poniedziałek 04:41 | gdy w repozytorium nie było commitu od ponad 30 dni, robi malutki commit aktywności (`kontrola/straznik.json`) — to główna ochrona przed wyłączeniem harmonogramów; próbuje też włączyć przepływy wyłączone przez GitHub |
| `sondy.yml`, `sondy_v128.yml` | Sondy źródeł | tylko ręcznie | jednorazowe sprawdzenia nowych źródeł; nie są potrzebne do działania strony |

Wszystkie przepływy używają przypiętego systemu `ubuntu-24.04` i zatwierdzonych wersji akcji — zmiana tylko świadomie, po teście.
Uwaga: gdy GitHub mimo wszystko wyłączy wszystkie zaplanowane przepływy naraz (po 60 dniach bez aktywności), stoi też sam strażnik — wtedy trzeba go włączyć ręcznie (Actions → „Enable workflow”, patrz część 7).
Kolejne przebiegi nie nakładają się (`concurrency`), a nieudany przebieg kontroli, archiwum lub strażnika kończy się e-mailem od GitHuba do właściciela repozytorium.

## 3. Sekrety i zmienne (tylko nazwy — wartości nigdy nie trafiają do repozytorium)

Ustawia się je w GitHub: Settings → Secrets and variables → Actions. Brak sekretu nie zatrzymuje automatu — dane z tego źródła są wtedy oznaczone
„brak” w zakładce Źródła (nigdy zerem). Wartość sekretu można w każdej chwili wymienić (np. po wygaśnięciu klucza) — nazwa zostaje ta sama.

- Klucze danych: `SOSOVALUE_KEY`, `COINGECKO_KEY`, `FINNHUB_KEY`, `TWELVEDATA_KEY`, `COINMARKETCAP_KEY`, `FRED_KEY`, `EIA_KEY`, `BLS_KEY`, `BEA_KEY`,
  `CENSUS_KEY`, `COINALYZE_KEY`, `BANXICO_TOKEN`, `EVDS_KEY`; z drugą dopuszczalną nazwą: `EODHD` albo `EODHD_KEY`, `MASSIVEPOLYGON` albo `MASSIVE_KEY`,
  `TIINGO` albo `TIINGO_KEY`, `FINANCIALMODELINGPREP` albo `FMP_KEY`, `ALPHAVANTAGE` albo `ALPHAVANTAGE_KEY`, `ETHERSCAN` albo `ETHERSCAN_KEY`,
  `CRYPTOPANIC` albo `CRYPTOPANIC_KEY`.
- `SEC_CONTACT` — adres kontaktowy do nagłówka zapytań do urzędowego serwisu spółek giełdowych USA (wymóg tego serwisu); wartość nigdy nie trafia na stronę.
- `GITHUB_TOKEN` — tymczasowy token każdego przebiegu, nadawany przez GitHub (nie trzeba go tworzyć); każdy przepływ ma tylko uprawnienia, których potrzebuje.
- Zmienne (Variables) — wyłączniki awaryjne, wpisuje się `1`: `ZEGAR_OFF` (cały zegar zapasowy), `ZEGAR_DZIENNE_OFF` (tylko zadania dzienne zegara),
  `STRAZNIK_OFF` (strażnik), `STRAZNIK_RECZNIE` (strażnik włącza także przepływy wyłączone ręcznie), `KALSHI_OFF`, `WYCENA_BG_OFF`, `RWA_OFF`, `RWA_CHAIN_OFF`,
  `RWA_EM_OFF` (wyłączają pojedyncze źródła). Pusta zmienna = działa normalnie.
- Straż kluczy: przed każdą publikacją `narzedzia/straz_kluczy.py` sprawdza, czy wartość któregokolwiek sekretu nie znalazła się w plikach strony; znalezisko przerywa publikację.

## 4. Gdzie są dane i archiwum

- Pliki danych `data/*.json` powstają w każdym przebiegu i są publikowane na stronie: `https://capitalflowai-app.github.io/data/<nazwa>.json`.
  Nie leżą w repozytorium (są w `.gitignore`); ich ostatni stan trzyma pamięć Actions (`pamiec-danych`, przeżywa nieudaną publikację) oraz opublikowana strona.
  Zbieracz przy każdym przebiegu bierze nowszy z dwóch: z pamięci Actions albo z opublikowanej strony — dlatego chwilowa awaria źródła lub pamięci nie kasuje danych.
- Archiwum własne: `archiwum/*.csv` i `archiwum/indeks.json` w repozytorium (zapis co dzień 01:20), tylko dane z domeny publicznej, otwartych licencji i nasze obliczenia.
  Zawiera m.in. salda portfeli giełd, podaż stablecoinów, płynność Fed, przepływy TIC, pozycje CFTC, rentowności oraz dzienniki sygnałów (krypto, świat, surowce).
- Kontrola: `kontrola/ostatnia.md` (czytelny raport po polsku: werdykt, świeżość źródeł, zgodność liczb, stan przepływów i strażnika), `ostatnia.json`, `historia.json`, `zgodnosc.csv`.
- Reguły sygnałów zarejestrowane z góry (przed wynikami) — katalog `docs/`: pliki `REGULY_*_PL.md` i ich sumy kontrolne `.sha256`. Suma SHA-256 dokumentu surowców jest też
  wpisana w kodzie zbieracza; test sprawdza, że dokument się nie zmienił. Sprawdzenie ręczne: `cd docs && shasum -a 256 -c REGULY_SUROWCE_2026-10-08_PL.md.sha256`.
  Suma `.sha256` jest przy dokumencie surowców (i w kodzie zbieracza). Dokument „w cieniu” (`REGULY_W_CIENIU_2026-10-06_PL.md`) nie ma pliku `.sha256`: ma poprawki opisane w samej treści,
  a jego suma jest przypięta w teście od wersji v354 (13.10.2026), więc dowodzi stanu z tego dnia, nie z 06.10.
  Nie zmieniaj tych plików — zmiana reguły to nowy dokument z nową datą.

## 5. Licznik odwiedzin

Licznik bez ciasteczek (GoatCounter); skrypt `count.js` leży w naszym repozytorium i jest publikowany razem ze stroną (nie ładuje się z obcej domeny),
jego treść jest przypięta skrótem w teście. Zlicza wejścia na stronę, nie śledzi osób.
Wyłączenie: usunąć linię ze skryptem `count.js` w `index.html` (strona działa bez niego).

## 6. Service Worker (pamięć strony w przeglądarce) i jego wyłącznik

Service Worker (plik `sw.js`) trzyma w przeglądarce czytelnika samą stronę, czcionki i obrazki do następnego wydania strony, żeby powrót na stronę był szybki.
Nigdy nie obsługuje plików danych (`data/*`, `archiwum/*`) ani obcych adresów — dane zawsze idą prosto z sieci. Stan na dziś: w przygotowaniu (wydanie v351, po zgodzie właściciela);
jeśli `sw.js` nie jest jeszcze opublikowany pod adresem strony, ten punkt jest nieaktywny.
Wyłącznik awaryjny (gdyby kiedyś pokazywał starą stronę): opublikować `sw.js`, który przy aktywacji kasuje wszystkie pamięci o nazwach zaczynających się od `cf-` i wyrejestrowuje się sam —
przeglądarki pobierają nowy `sw.js` przy najbliższym wejściu i same się czyszczą. U pojedynczej osoby pomaga też ręczne wyczyszczenie danych witryny
(Chrome: ikona obok adresu → Ustawienia witryny → Wyczyść dane; Safari na telefonie: Ustawienia → Safari → Zaawansowane → Dane witryn → usuń wpis strony).
Dokładny opis działania i wyłącznika znajduje się w komentarzu na początku pliku `sw.js`.

## 7. Co zrobić, gdy coś stanie

Zawsze po kolei, od najprostszego. W razie wątpliwości nic nie usuwaj — dane i historia są w repozytorium.

1. Sprawdź `kontrola/ostatnia.md` w repozytorium (albo zakładkę „Źródła” na stronie): wiersz „Wynik”, lista błędów i dopisek „Co zrobić”.
2. Zakładka Actions → „Strona i dane”: kiedy był ostatni przebieg? Jeśli starszy niż ok. 30 minut — kliknij „Run workflow” (zegar zapasowy zwykle robi to sam).
3. Przy zielonym przebiegu, a starych danych w jednym źródle: to zwykle chwilowa awaria tego źródła (zakładka Źródła pokazuje wiek danych). Poczekaj kilka godzin; przy braku
   poprawy sprawdź, czy klucz nie wygasł (Settings → Secrets) i wymień jego wartość.
4. Przebieg czerwony w kroku „Testy”: publikacja zatrzymana celowo (strona zostaje w ostatnim dobrym stanie). Wymaga poprawki kodu — napisz do Claude: „napraw testy po ostatniej zmianie”.
5. Przebieg czerwony w kroku publikacji (GitHub Pages): zwykle chwilowa awaria GitHuba — „Re-run failed jobs”; zegar sam uruchomi następny przebieg.
6. Przebieg w stanie „waiting” ponad kwadrans: zegar anuluje go sam; ręcznie: Cancel workflow, potem „Run workflow”.
7. Baner „This scheduled workflow is disabled because there hasn't been activity in this repository for at least 60 days”: w zakładce Actions wejdź w każdy przepływ
   i kliknij „Enable workflow”; potem uruchom „Strażnik harmonogramów” (Run workflow) — doda commit aktywności, jeśli trzeba. Gdy GitHub wyłączy wszystko naraz, strażnik też stoi i tylko ręczne „Enable workflow” go wznowi.
   Do tego nie powinno dojść: strażnik co tydzień pilnuje, żeby od ostatniego commitu nie minęło więcej niż 30 dni (limit GitHuba to 60), a kontrola i archiwum robią commity codziennie.
8. Nic nie pomaga, a strona pokazuje błąd: Settings → Pages → Build and deployment → Source musi być ustawione na „GitHub Actions”; Settings → Environments → `github-pages` bez wymaganych recenzentów.
9. Konto GitHub zablokowane albo repozytorium usunięte: patrz część 8 (odtworzenie od zera).

## 8. Jak przywrócić dane i projekt z archiwum

- Pojedynczy plik danych zniknął lub jest zepsuty: nic nie trzeba robić — następny przebieg (za ok. 10 minut) pobiera go od nowa ze źródła; wykresy historyczne korzystają z `archiwum/`.
  Zgubiony dziennik sygnałów zbieracz odtwarza sam z `archiwum/krypto-dziennik.csv`, `swiat-dziennik.csv`, `swiat-dziennik-pk.csv`, `surowce-dziennik.csv`, `ng-dziennik.csv` i `fw-dziennik.csv`.
- Zły commit w repozytorium: na stronie GitHub otwórz commit → „Revert”; powstaje nowy commit przywracający poprzedni stan i automat publikuje stronę ponownie.
  Historia plików (w tym `archiwum/` i `kontrola/`) jest w całej historii repozytorium — każdą wersję pliku można otworzyć z listy commitów.
- Archiwum z wybranego dnia: w repozytorium otwórz `archiwum/<plik>.csv` → History → wybrany commit → „View file” → Raw. CSV otwiera się w arkuszu kalkulacyjnym.
- Całe repozytorium utracone: każda kopia robocza (`git clone`) zawiera pełną historię. Kroki: (1) załóż na koncie `capitalflowai-app` repozytorium o nazwie
  `capitalflowai-app.github.io`; (2) wyślij do niego kopię (`git push --mirror`); (3) wpisz od nowa sekrety z części 3 (wartości pochodzą z paneli dostawców, nie z repozytorium);
  (4) Settings → Pages → Source: „GitHub Actions”; (5) uruchom „Strona i dane” ręcznie. Po pierwszym przebiegu pamięć danych jest pusta, więc część plików powstanie od zera —
  historia sygnałów wraca z `archiwum/`.
- Sumy kontrolne dokumentów rejestracji z `docs/` pozwalają udowodnić, że reguły nie zostały zmienione po wynikach (część 4).
