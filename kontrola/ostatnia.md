# Kontrola strony — 06.11.2026, 10:55 (czas polski)

**Wynik: BŁĄD**

❌ Błędów: 2 — wymagają uwagi (szczegóły niżej).

**Co zrobić:**
- Automat nie odświeża danych od ponad 3 godzin — zegar zapasowy też nie pomógł. Najczęściej to przerwa po stronie GitHub (stan: githubstatus.com); jeśli trwa ponad 6 godzin: uruchom naprawę (np. Claude) z plikiem kontrola/ostatnia.md albo poproś osobę techniczną.
- Dane źródła są dużo starsze niż zwykle (ponad dwa razy dłużej niż norma; weekendy już odliczone) — źródło przestało publikować (np. przerwa w pracy urzędu) albo automat nie może ich pobrać. Jeśli trwa dłużej niż 3 dni: uruchom naprawę (np. Claude) z plikiem kontrola/ostatnia.md albo poproś osobę techniczną.

**Ostrzeżenia o źródłach danych: 8** ⚠️ — strona i publikacja działają, dane tych źródeł mają swój wiek na stronie (pełna lista z czasem trwania: sekcja „Uwagi” niżej). Jeśli trwa dłużej niż 3 dni: uruchom naprawę (np. Claude) z plikiem kontrola/ostatnia.md albo poproś osobę techniczną.

- Strona główna: działa (HTTP 200, 288 ms).
- Ostatni przebieg automatu: 06.11.2026, 04:12 — sprzed 403 min; źródeł: 290, bez odpowiedzi: defi2_fees, dzwignia_cb, kalendarz2_dane_pl; błędów zbieracza: 3.
- Czas tego przebiegu automatu: 2 min 10 s; najdłużej: etf 56 s, wieloryby 21 s, trendy 7 s.
- Strona w przeglądarce (bez okna, ekran telefonu 390 px): zrzut po 8,0 s — grafik 524, wykresów liniowych 38; błędów JavaScriptu: 0 ✅; nieudane wczytania: 1 (api.coingecko.com) ℹ️.
- Strona jak u czytelnika (bez ?pelna=1 — pliki CRYPTO dopiero po otwarciu zakładki): zrzut po 7,0 s; błędów JavaScriptu: 0 ✅.
- Przebiegi Actions w 24 h: 87 (in_progress: 1, failure: 50, success: 35, cancelled: 1).
- Najdłuższy udany przebieg w 24 h: 23,5 min (od startu do końca, z czekaniem na maszyny); samo zadanie budowy najdłużej 23,1 min z limitu 25 min ⚠️ blisko limitu.
- Nieudane przebiegi (24 h): 06.11.2026, 04:15; 05.11.2026, 19:54 — zbuduj / Testy zbieracza; 05.11.2026, 19:44 — zbuduj / Testy zbieracza; 05.11.2026, 19:34 — zbuduj / Testy zbieracza; 05.11.2026, 19:24 — zbuduj / Testy zbieracza; 05.11.2026, 19:14; 05.11.2026, 19:04; 05.11.2026, 18:53; 05.11.2026, 18:43; 05.11.2026, 18:33. Ostatni zakończony przebieg nieudany.
- Strażnik harmonogramów (raz w tygodniu): przepływy z harmonogramem czynne 8 z 8; ostatni przebieg strażnika 3 dni temu (success); ostatni commit w repozytorium dziś ✅.
- Ostrzeżenia GitHuba o przestarzałych akcjach (ostatni przebieg każdego z 6 przepływów): brak ✅.
- Pliki danych (wiek): etf 6h43, trendy 6h43, oecd 8h37, rynki 7h23, dzwignia 6h43, wieloryby 6h43, energia 8h21, surowce 6h53, surowce-hist 6h53, usa-makro 8h21, bilans-usa 14h16, krypto 6h43, krypto-top10 7h18, cmc 6h43, instytucje 7h23, tic 14h42, cm 7h23, fred 7h23, cftc 8h37, ceny 7h23, indeksy 6h43, ceny-krypto 7h23, snb 14h42, ici 12h36, fed 6h43, lancuch 6h43, wycena 6h52, insider 6h43, nastroj 8h21, stres 8h37, aukcje 8h37, swiat-dzien 6h43, swiat-dziennik 6h41, surowce-dziennik 6h41, premie 6h43, dolar 7h19, stopy 8h37, jpx 14h09, rwa 7h59, zloto-krypto 6h41, szlaki 14h36, polska 8h18, surowce-raporty 8h36, dzis 6h43, fundusze 6h43, obce 7h23, krypto-top10-logo 7h18, eer 8h37, meksyk 8h37, kursy 14h42, bis 14h42, rezerwy 14h42, cofer 14h42, bilans 14h42, safe 14h42, ue 14h42, kanada 14h42, korea 14h42, spw 14h42, pip 14h42, fundusze-przeplywy 6h43, zboza-dzien 6h53, metale 9h05, azja2 8h37, ng-dziennik 6h41, ng-ceny 6h43, fw-dziennik 6h41, porty 10h33, lng 8h36, rosja 14h35, polska-rynek 6h43, polska-kapital 6h43, polska-dlug 6h43, polska-2 6h43, bis2 14h42, gieldy 7h19, dex 6h53, target 14h16, mica 14h16, etf-zapas 8h37, soma-sklad 8h01, eurosystem 8h01, hedge 14h16, krzywe 8h51, stable-emitenci 6h43, inflacja 14h42, koniunktura 8h37, prad 6h41, niepewnosc 8h21, kalendarz 8h21, kalendarz2 7h23, nowcasty 8h01, usdt-skarbiec 6h53, europa-fundusze 8h21, plynnosc-usa 8h01, skarb-usa 8h01, usda-eksport 8h01, premie-stable 6h43, energia-usa 8h01, dzwignia2 6h53, indie 6h53, chiny-tw 7h06, interwencje 8h01, defi2 6h43, eth-lancuch 6h53, ucits-przeplywy 6h43, kanada-dlug 7h06, fred2 8h01, kapitalizacje 6h53, krypto-firmy 14h42, fed-ddp 7h06, short-eu 8h37, ropa-swiat 14h42, iip 8h37, usa-pakiet 8h37, surowce-247 7h23, waluty 8h37, zloto-uk 14h42, hl-aave 8h01, nastroje 6h53, sec-13f 14h42, nastroje-gosp 8h37, em2 8h01, klimat 8h37, zmiennosc 8h21, krypto-dzien 6h43, krypto-dziennik 6h41, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200, count.js HTTP 200, sw.js HTTP 200.
- Awarie części automatu — trwają: defi2_fees od 06.11.2026, 03:08 (1 godz., nieudanych przebiegów: 6) ℹ️ (DeFi 2 — część z błędem zostaje z datą (v402); wiek danych w wierszach świeżości); dzwignia_cb od 20.10.2026, 19:20 (16 dni 9 godz., nieudanych przebiegów: 952) ⚠️; kalendarz2_dane_pl od 30.10.2026, 13:12 (6 dni 15 godz., nieudanych przebiegów: 131) ℹ️ (kalendarz 2 — część z błędem zostaje ze starymi terminami i datą (v375); wiek pobrania w wierszach świeżości); metale_cu od 23.10.2026, 19:58 (13 dni 9 godz., nieudanych przebiegów: 32) ℹ️ (metale — część z błędem zostaje z datą (v339); wiek danych w wierszach świeżości); porty_pt od 31.10.2026, 09:50 (5 dni 18 godz., nieudanych przebiegów: 5) ℹ️ (porty świata — część z błędem zostaje z datą (v393); wiek danych w wierszach świeżości); szlaki_cies od 05.11.2026, 21:29 (6 godz., nieudanych przebiegów: 7) ℹ️ (szlaki — część z błędem zostaje z datą (v305); wiek danych w wierszach świeżości); szlaki_presja od 05.11.2026, 23:22 (4 godz., nieudanych przebiegów: 2) ℹ️ (szlaki — część z błędem zostaje z datą (v305); wiek danych w wierszach świeżości).
- Naprawiły się same (24 h): bop 06.11.2026, 01:41 – 06.11.2026, 02:34 (0 godz., nieudanych przebiegów: 1) ℹ️; eth_wal 21.10.2026, 21:24 – 05.11.2026, 21:41 (15 dni 1 godz., nieudanych przebiegów: 803) ℹ️; lng_dz 05.11.2026, 20:39 – 06.11.2026, 02:17 (5 godz., nieudanych przebiegów: 26) ℹ️; m3 06.11.2026, 01:41 – 06.11.2026, 02:34 (0 godz., nieudanych przebiegów: 1) ℹ️; mof 06.11.2026, 01:41 – 06.11.2026, 02:34 (0 godz., nieudanych przebiegów: 1) ℹ️; polska_hurt 05.11.2026, 23:59 – 06.11.2026, 02:04 (2 godz., nieudanych przebiegów: 1) ℹ️; porty_sw 05.11.2026, 22:19 – 06.11.2026, 00:21 (2 godz., nieudanych przebiegów: 1) ℹ️; rwa-emitenci 31.10.2026, 18:17 – 05.11.2026, 20:39 (5 dni 2 godz., nieudanych przebiegów: 23) ℹ️; sosovalue 21.10.2026, 20:16 – 05.11.2026, 21:14 (15 dni 2 godz., nieudanych przebiegów: 803) ℹ️; tgb 06.11.2026, 01:41 – 06.11.2026, 02:34 (0 godz., nieudanych przebiegów: 1) ℹ️; usdt_eth 06.11.2026, 01:25 – 06.11.2026, 02:04 (0 godz., nieudanych przebiegów: 1) ℹ️; wycena_bg 05.11.2026, 20:39 – 06.11.2026, 04:01 (7 godz., nieudanych przebiegów: 33) ℹ️.
- Zużycie darmowych planów (licznik automatu — dolna granica): CoinGecko (Demo) — zapytań w tym miesiącu: 75, prognoza na miesiąc ok. 438 z limitu 10 000 (4%) ✅; CoinMarketCap (Basic) — zapytań w tym miesiącu: 38, prognoza na miesiąc ok. 222 z limitu 15 000 (1%); według dostawcy w miesiącu: 23 z 15 000 (0%, stan 06.11.2026, 01:12) ✅; Twelve Data (Basic) — kredytów wczoraj (doba UTC): 60 z limitu 800 (8%); w bieżącej dobie (od północy UTC): 45 ✅; FMP (darmowy) — zapytań wczoraj (doba UTC): 6 z limitu 250 (2%); w bieżącej dobie (od północy UTC): 0 ✅.

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ❌ | 7 h 23 min | 2026-11-06T02:32:02+00:00 | próg 3 h 00 min, ponad 2× progu |
| wieloryby (salda portfeli giełd) | ⚠️ | 6 h 43 min | 2026-11-06T03:12:02+00:00 | próg 3 h 00 min, ponad 2× progu |
| dźwignia (giełdy pochodnych) | ⚠️ | 7 h 23 min | 2026-11-06T02:32:02+00:00 | próg 3 h 00 min, ponad 2× progu |
| premie krypto (minuty giełd) | ⚠️ | 6 h 43 min | 2026-11-06T03:12 | próg 3 h 00 min, ponad 2× progu |
| TGA (Fiscal Data, dziennie) | ✅ | 33 h 55 min | 2026-11-04 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 33 h 55 min | 2026-11-04 – 2026-11-05 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 9 h 55 min | 2026-11-05 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 33 h 55 min | 2026-11-04 | — |
| CFTC (raport tygodniowy) | ✅ | 9 d 9 h | 2026-10-27 | — |
| FRED tygodniowe (WALCL) | ✅ | 33 h 55 min | 2026-11-04 | — |
| TIC (miesięcznie) | ✅ | 66 d 9 h | 2026-08 | — |
| OECD (miesięcznie) | ✅ | 5 d 9 h | 2026-10 | — |
| BLS (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| szanse decyzji Fed (rynek zakładów) | ⚠️ | 6 h 42 min | 2026-11-06T03:13:40+00:00 | próg 1 h 30 min, ponad 2× progu |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 9 h 55 min | 2026-11-05 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 9 h | 2026-10-30 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ⚠️ | 7 h 19 min | 2026-11-06T02:36:40+00:00 | próg 3 h 00 min, ponad 2× progu — tylko uwaga |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 8 d 9 h | 2026-10-28 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 33 h 55 min | 2026-11-04 | — |
| surowce: ropa i gaz dziennie (strona dzienna T+1, API co tydzień) | ✅ | 33 h 55 min | 2026-11-04 | — |
| surowce: złoto dziennie (LBMA PM wyliczona) | ✅ | 33 h 55 min | 2026-11-04 | — |
| surowce: złoto teraz (notowanie co godzinę) | ⚠️ | 6 h 53 min | 2026-11-06T03:02:00+00:00 | próg 3 h 00 min — najwyżej uwaga |
| surowce: zapasy w USA (tydzień do piątku, publ. w środę) | ✅ | 6 d 9 h | 2026-10-30 | — |
| surowce: ceny miesięczne (publ. ok. 2. dnia roboczego) | ✅ | 5 d 9 h | 2026-10 | — |
| surowce: pozycje funduszy (stan na wtorek, publ. w piątek) | ✅ | 9 d 9 h | 2026-10-27 | — |
| surowce: pozycje funduszy — USA, 30 rynków + fundusze indeksowe + indeks (stan na wtorek, publ. w piątek) | ✅ | 9 d 9 h | 2026-10-27 | — |
| surowce: pozycje funduszy — Londyn (stan na wtorek, publ. w piątek) | ✅ | 9 d 9 h | 2026-10-27 | — |
| surowce: pozycje producentów — ropa Murban, Abu Zabi (stan na wtorek, publ. w piątek) | ✅ | 9 d 9 h | 2026-10-27 | — |
| surowce: złoto w funduszach (tony; po sesji w USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| surowce: złoto banków centralnych (miesięcznie; każdy kraj ze swoim miesiącem) | ℹ️ | 5 d 9 h | 2026-10 | bez progu (MFW publikuje kraje w różnych dniach); dane starsze niż 120 dni: KG 2026-06 |
| szlaki: ruch statków w 8 cieśninach (dziennie, publ. we wtorek) | ⚠️ | 11 d 9 h | 2026-10-25 | próg 10 d 0 h — najwyżej uwaga; spodziewana publikacja 03.11.2026, 13:10 — zaległa (przerwa u źródła?) |
| szlaki: wskaźnik presji w łańcuchach dostaw (miesięcznie, publ. ok. 4. dnia roboczego) | ✅ | 36 d 9 h | 2026-09 | — |
| szlaki: indeks cen surowców (tydzień do środy, publ. ok. tydzień później) | ✅ | 33 h 55 min | 2026-11-04 | — |
| porty: świat wg ładunku (dziennie, publ. raz w tygodniu) | ✅ | 6 d 9 h | 2026-10-30 | — |
| porty: 20 dużych portów (dziennie, publ. raz w tygodniu) | ⚠️ | 13 d 9 h | 2026-10-23 | porty w tyle za najnowszym dniem (2026-10-23): Singapur — brak w pliku, Szanghaj (Yangshan) — brak w pliku, Ningbo — brak w pliku, Hongkong — brak w pliku, Busan — brak w pliku, Port Klang — brak w pliku, Nhava Sheva — brak w pliku, Port Hedland — brak w pliku, Antwerpia — brak w pliku, Hamburg — brak w pliku, Algeciras — brak w pliku, Gdańsk — brak w pliku, Los Angeles i Long Beach — brak w pliku, Houston — brak w pliku, Santos — brak w pliku (próg 7 dni; w historii 2024–2026: 0) — najwyżej uwaga |
| gaz i LNG: Świnoujście, dobowa wysyłka z terminalu (doba gazowa) | ✅ | 33 h 55 min | 2026-11-04 | — |
| gaz i LNG: terminale UE razem, dobowa wysyłka (doba kompletna) | ✅ | 33 h 55 min | 2026-11-04 | — |
| gaz i LNG: import LNG do UE27 wg pochodzenia (miesięcznie) | ✅ | 66 d 9 h | 2026-08 | — |
| gaz i LNG: import LNG do Polski (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| gaz i LNG: zapasy gazu w magazynach UE27 (miesięcznie) | ✅ | 66 d 9 h | 2026-08 | — |
| gaz i LNG: zapasy gazu w magazynach Polski (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| zmienność: VIX (S&P 500, 30 dni; dni robocze USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| zmienność: VIX 3M (S&P 500, 3 miesiące; dni robocze USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| zmienność: Nasdaq 100 (dni robocze USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| zmienność: rynki wschodzące (dni robocze USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| zmienność: ropa (dni robocze USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| zmienność: złoto (dni robocze USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| put/call: wskaźniki dzienne giełdy opcji USA (sesje USA) | ✅ | 33 h 55 min | 2026-11-04 | — |
| indeks stresu finansowego USA (dni robocze, opóźnienie 2 dni) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Rosja: handel UE z Rosją (miesięcznie) | ✅ | 66 d 9 h | 2026-08 | — |
| Rosja: należności banków świata (kwartalnie) | ✅ | 128 d 9 h | 2026-Q2 | — |
| Rosja: handel Rosji wg partnerów (miesięcznie) | ✅ | 97 d 9 h | 2026-07 | — |
| Rosja: rezerwy walutowe (miesięcznie) | ⚠️ | 340 d 9 h | 2025-11 | próg 180 d 0 h — najwyżej uwaga; spodziewana zmiana 06.11.2026, 20:20; źródło międzynarodowe publikuje rezerwy Rosji z dużym opóźnieniem (nowy miesiąc zależy od Rosji, nie od zbieracza) — ostatni miesiąc w tabeli międzynarodowej widać w kolumnie daty |
| Rosja: złoto banku centralnego w tonach (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Polska: indeksy giełdy w Warszawie (dziennie) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Polska: krzywa rentowności obligacji skarbowych (dziennie) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Polska: przepływy do funduszy inwestycyjnych (miesięcznie) | ✅ | 36 d 9 h | 2026-09-30 | — |
| Polska: członkowie giełdy w obrotach akcjami (miesięcznie) | ✅ | 5 d 9 h | 2026-10-31 | — |
| Polska: inwestycje bezpośrednie według kraju (kwartalnie) | ✅ | 128 d 9 h | 2026-06-30 | — |
| Polska: wypłaty z budżetu UE 2021–2027 (dziennie w dni robocze) | ✅ | 17 h 36 min | 2026-11-05 | — |
| Polska: kto trzyma dług skarbowy (struktura posiadaczy, miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Polska: sprzedaż obligacji detalicznych (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Polska 2: dług zagraniczny i pozycja inwestycyjna (kwartalnie) | ✅ | 128 d 9 h | 2026-Q2 | — |
| Polska 2: oficjalne rezerwy i złoto (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Polska 2: indeks cen konsumpcyjnych od 1999 (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Polska 2: depozyty i kredyty banków (miesięcznie) | ✅ | 66 d 9 h | 2026-08 | — |
| Polska 2: WIBID i WIBOR (dziennie) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Polska 2: WIRON i POLSTR (dziennie) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Polska 2: ceny mieszkań (kwartalnie) | ✅ | 128 d 9 h | 2026-Q2 | — |
| Giełdy: salda i przepływy netto giełd scentralizowanych (szacunek z portfeli) | ⚠️ | 8 h 10 min | 2026-11-06T01:45:43+00:00 | próg 4 h 00 min — najwyżej uwaga |
| DEX: obrót ostatniej pełnej doby UTC | ✅ | 9 h 55 min | 2026-11-05 | — |
| Kontrakty na łańcuchu: otwarte pozycje | ⚠️ | 7 h 35 min | 2026-11-06T02:20:18+00:00 | próg 4 h 00 min — najwyżej uwaga |
| surowce: podaż ropy OPEC+ (raport miesięczny — szacunek i prognoza) | ✅ | 30 d 9 h | 2026-10-06 | — |
| surowce: bilans zbóż świata i USA (raport miesięczny) | ✅ | 27 d 9 h | 2026-10-09 | — |
| surowce: uran — średnia branżowa z końca miesiąca | ✅ | 6 d 9 h | 2026-10-30 | — |
| zboża: indeks dzienny (dni robocze, dane z poprzedniego dnia roboczego) | ✅ | 33 h 55 min | 2026-11-04 | — |
| zboża: indeks frachtu (tygodniowo, środa, dane za wtorek) | ✅ | 9 d 9 h | 2026-10-27 | — |
| żywność: podindeksy cen FAO (miesięcznie, publ. ok. 1. piątku) | ✅ | 36 d 9 h | 2026-09 | — |
| zboża i rzepak w UE: ceny tygodniowe (czwartek, tydzień do niedzieli) | ✅ | 4 d 9 h | 2026-11-01 | — |
| nawozy w UE (miesięcznie, publ. ok. 10. dnia) | ✅ | 36 d 9 h | 2026-09 | — |
| Meksyk: obligacje rządu u nierezydentów (dziennie, opóźnienie ok. 1,5 tygodnia) | ✅ | 10 d 9 h | 2026-10-26 | — |
| Polska: nierezydenci w obligacjach skarbowych (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Korea Płd.: inwestorzy zagraniczni w akcjach i obligacjach (komunikat miesięczny) | ✅ | 36 d 9 h | 2026-09 | — |
| MFW PIP — Polska jako emitent (półrocze) | ✅ | 309 d 9 h | 2025-S2 | — |
| MFW PIP — 20 największych par (półrocze) | ✅ | 309 d 9 h | 2025-S2 | — |
| MFW PIP — kto trzyma polskie papiery: suma = świat | ✅ | — | 193.3 vs 193.3 mld USD (2025-S2) | — |
| MFW PIP — Polska jako inwestor: suma = świat | ✅ | — | 94.3 vs 94.3 mld USD (2025-S2) | — |
| Dźwignia — krzywa terminowa Deribit (BTC, ETH) | ⚠️ | 7 h 20 min | 2026-11-06T02:35:52+00:00 | odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min) |
| Dźwignia — Coinbase USA (kontrakty BTC, ETH) | ⚠️ | 7 h 19 min | 2026-11-06T02:35:56+00:00 | odczyt starszy niż 180 min |
| Dźwignia — basis Deribit vs OKX (ten sam termin) | ✅ | — | BTC: 5 terminów, największa różnica 0.00 pp (tolerancja 1.13); ETH: 5 terminów, największa różnica 0.02 pp (tolerancja 1.13) | — |
| Dźwignia — Bitget (BTC, ETH) | ⚠️ | 7 h 19 min | 2026-11-06T02:35:57+00:00 | odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min) |
| Dźwignia — Gate (BTC, ETH, likwidacje) | ⚠️ | 7 h 23 min | 2026-11-06T02:32:02+00:00 | odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min); likwidacje starsze niż 360 min |
| Dźwignia — KuCoin (BTC, ETH) | ⚠️ | 7 h 23 min | 2026-11-06T02:32:02+00:00 | odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min) |
| Dźwignia — MEXC (BTC, ETH) | ⚠️ | 7 h 19 min | 2026-11-06T02:35:59+00:00 | odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min) |
| Dźwignia — HTX (BTC, ETH) | ⚠️ | 7 h 19 min | 2026-11-06T02:36:04+00:00 | odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min) |
| Dźwignia — suma otwartych pozycji, wobec poprzedniego zestawu giełd (informacja) | ✅ | — | BTC: 11 giełd 18.81 mld USD (2026-11-06), poprzednio 5 giełd 5.91 mld USD (2026-10-12); ETH: 11 giełd 9.60 mld USD (2026-11-06), poprzednio 5 giełd 4.22 mld USD (2026-10-12) | — |
| metale: giełda w Londynie — ceny i zapasy (dziennie, publ. wieczorem UTC) | ✅ | 33 h 55 min | 2026-11-04 | — |
| metale: giełda w Szanghaju — ceny (dziennie, ok. 07:30 UTC) | ✅ | 9 h 55 min | 2026-11-05 | — |
| metale: giełda w Szanghaju — kwity magazynowe (dziennie) | ✅ | 9 h 55 min | 2026-11-05 | — |
| metale: giełda w Szanghaju — zapasy w magazynach (tygodniowo) | ✅ | 6 d 9 h | 2026-10-30 | — |
| metale: raport tygodniowy o zapasach miedzi (Londyn, USA, Chiny) | ⚠️ | 20 d 9 h | 2026-10-16 | próg 14 d 0 h — najwyżej uwaga; spodziewana publikacja 30.10.2026, 19:00 — zaległa (święto albo przerwa u źródła?) |
| Fundusze ETF (USA) — fundusze z ostatnią sesją (State Street, iShares) | ⚠️ | — | 46 z 94 (49%) — oczekiwana sesja: iShares 2026-11-04, State Street 2026-11-04 | mniej niż 95% funduszy z ostatnią sesją; bez danych 3+ sesji: EWP (ostatni dzień 2026-10-30, brak 4 sesji), EWS (ostatni dzień 2026-10-30, brak 4 sesji), EWW (ostatni dzień 2026-10-30, brak 4 sesji), EWG (ostatni dzień 2026-10-30, brak 4 sesji), EWA (ostatni dzień 2026-10-30, brak 4 sesji), EWH (ostatni dzień 2026-10-30, brak 4 sesji), EWI (ostatni dzień 2026-10-30, brak 4 sesji), EWD (ostatni dzień 2026-10-30, brak 4 sesji) i 40 więcej (tylko uwaga) |
| Fundusze ETF (USA) — NAV a zamknięcie na giełdzie (kontrola krzyżowa) | ✅ | — | 12 funduszy, największa różnica 1,44% (EWY, 2026-11-05) | — |
| Polska: złoto w zł/g (dni robocze w Polsce) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Polska: ceny hurtowe paliw (dni obowiązywania wt–sob) | ✅ | 0 h 00 min | 2026-11-06 | — |
| Polska: gaz i prąd z giełdy (dzień dostawy, 7 dni w tygodniu) | ✅ | 0 h 00 min | 2026-11-06 | — |
| Polska: ceny na stacjach na tle UE (poniedziałki, pobierane w nocy) | ✅ | 3 d 9 h | 2026-11-02 | — |
| Polska: pszenica (tydzień do niedzieli, publ. w czwartek) | ✅ | 4 d 9 h | 2026-11-01 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 13 d 9 h | 2026-10-23 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ⚠️ | 6 d 9 h | 2026-10-30 | próg 4 d 0 h — wyniki sygnałów przestały dochodzić (tylko uwaga) |
| TRENDY świat — ostatnia sesja z wynikiem sygnałów | ⚠️ | 4 d 9 h | 2026-10-30 | próg 2 d 0 h — wyniki sygnałów przestały dochodzić (tylko uwaga) |
| TRENDY surowce — ostatni dzień z wynikiem reguł w cieniu | ✅ | 9 h 55 min | 2026-11-05 | — |
| TRENDY surowce — ceny 7 funduszy surowcowych (sesja w USA; reguły w cieniu) | ✅ | 9 h 55 min | 2026-11-05 | — |
| TRENDY surowce — NAV i jednostki 3 funduszy surowcowych (reguły w cieniu) | ✅ | 9 h 55 min | 2026-11-05 | — |
| TRENDY nowe grupy — ostatni dzień z wynikiem reguł w cieniu | ⚠️ | 3 d 9 h | 2026-11-02 | próg 2 d 12 h (godziny robocze) — wyniki reguł w cieniu przestały dochodzić (tylko uwaga) |
| TRENDY nowe grupy — fundusze: ostatni dzień z wynikiem reguł w cieniu | ✅ | 3 d 9 h | 2026-11-02 | — |
| TRENDY nowe grupy — rynek polski: ostatni dzień z wynikiem reguł w cieniu | ✅ | 3 d 9 h | 2026-11-02 | — |
| TRENDY nowe grupy — metale: ostatni dzień z wynikiem reguł w cieniu | ✅ | 3 d 9 h | 2026-11-02 | — |
| TRENDY nowe grupy — zboża: ostatni dzień z wynikiem reguł w cieniu | ⚠️ | 4 d 9 h | 2026-10-30 | próg 4 d 0 h (godziny robocze) — wyniki tej grupy przestały dochodzić, pozostałe grupy mogą być świeże (tylko uwaga) |
| TRENDY nowe grupy — ceny 14 funduszy wyników (sesja w USA; reguły w cieniu) | ✅ | 9 h 55 min | 2026-11-05 | — |
| TRENDY najnowsze źródła — ostatni dzień z wynikiem reguł w cieniu | ⚠️ | 3 d 9 h | 2026-11-02 | próg 2 d 12 h (godziny robocze) — wyniki reguł w cieniu przestały dochodzić (tylko uwaga) |
| tokenizowane aktywa RWA (co 3 h) | ✅ | 7 h 59 min | 2026-11-06T01:55:56+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 3 h) | ✅ | 7 h 59 min | 2026-11-06T01:55:56+00:00 | — |
| tokenizowane aktywa — dane emitentów (co 3 h) | ✅ | 7 h 59 min | 2026-11-06T01:55:56+00:00 | — |
| TARGET: salda krajów strefy euro (EBC, miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Rejestry MiCA: wykaz firm z licencją CASP (plik zmieniany nieregularnie) | ✅ | 19 h 48 min | 2026-11-05 | — |
| Rejestry MiCA: wykaz emitentów tokenów powiązanych z walutą (EMT) | ✅ | 19 h 47 min | 2026-11-05 | — |
| Portfel papierów Fed: skład (tygodniowo, stan na środę) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Bilans Eurosystemu: główne pozycje (tygodniowo, stan na piątek) | ✅ | 6 d 9 h | 2026-10-30 | — |
| Fundusze hedgingowe w USA: aktywa (kwartalnie) | ✅ | 128 d 9 h | 2026-06-30 | — |
| Stablecoiny — raport Tether (zobowiązania, sieci) | ✅ | 10 h 25 min | 2026-11-05 23:30 UTC | — |
| Stablecoiny — raport Circle (USDC, EURC) | ⚠️ | 6 h 43 min | 2026-11-06 03:12 UTC | raport starszy niż 2 h — emitent nie odświeża pliku albo adres się zmienił; najwyżej uwaga |
| USDT skarbiec — odczyt sieci Ethereum | ⚠️ | 6 h 53 min | 2026-11-06 03:01 UTC | odczyt starszy niż 3 h — źródło nie odpowiada albo adres się zmienił; najwyżej uwaga |
| USDT skarbiec — odczyt sieci Tron | ⚠️ | 7 h 47 min | 2026-11-06 02:08 UTC | odczyt starszy niż 3 h — źródło nie odpowiada albo adres się zmienił; najwyżej uwaga |
| Dźwignia 2 — odczyt statystyk dziennych giełdy OKX | ⚠️ | 6 h 53 min | 2026-11-06 03:01 UTC | najstarszy odczyt starszy niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga |
| Dźwignia 2 — odczyt stanów Bitfinex | ⚠️ | 6 h 53 min | 2026-11-06 03:01 UTC | najstarszy odczyt starszy niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga |
| Ethereum — odczyt kolejek stakingu | ✅ | 6 h 53 min | 2026-11-06 03:01 UTC | — |
| Ethereum — odczyt spalania i podaży | ⚠️ | 6 h 53 min | 2026-11-06 03:01 UTC | odczyt starszy niż 4 h — źródło nie odpowiada albo zmieniło odpowiedź; najwyżej uwaga |
| Sieci L2 — odczyt aktywności | ✅ | 8 h 01 min | 2026-11-06 01:54 UTC | — |
| Sieci L2 — odczyt drugiego źródła TVL | ✅ | 8 h 01 min | 2026-11-06 01:54 UTC | — |
| Fundusze ETF — odczyt kursów walut | ✅ | 14 h 16 min | 2026-11-05 19:39 UTC | — |
| Fundusze ETF — odczyt zestawienia funduszy | ⚠️ | 8 h 01 min | 2026-11-06 01:54 UTC | odczyt starszy niż 6 h — źródło nie odpowiada albo zmieniło odpowiedź; najwyżej uwaga |
| Fundusze ETF — pliki historii funduszy | ✅ | 14 h 16 min | najstarszy plik sprzed 14 h 16 min | — |
| Hyperliquid — ranking kont (pobranie) | ✅ | 14 h 16 min | 2026-11-05 19:39 UTC | — |
| Hyperliquid — ranking kont (plik wydawcy) | ✅ | 15 h 00 min | 2026-11-05 18:55 UTC | — |
| Pożyczki DeFi (Aave) (pobranie) | ✅ | 8 h 01 min | 2026-11-06 01:54 UTC | — |
| DeFi 2 — opłaty i przychody protokołów (doba danych) | ✅ | 33 h 55 min | 2026-11-04 | — |
| DeFi 2 — ceny stablecoinów (doba danych) | ✅ | 0 h 00 min | 2026-11-06 | — |
| DeFi 2 — lista włamań (pobranie) | ✅ | 7 h 47 min | 2026-11-06 02:08 UTC | — |
| DeFi 2 — opcje na zdecentralizowanych giełdach (doba danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Indie — odczyt wyceny indeksów | ⚠️ | 6 h 53 min | sesja 2026-11-05 · sprawdzone 2026-11-06 03:01 UTC | ostatnie udane sprawdzenie starsze niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga |
| Indie — odczyt pozycji w kontraktach | ⚠️ | 6 h 53 min | sesja 2026-11-05 · sprawdzone 2026-11-06 03:01 UTC | ostatnie udane sprawdzenie starsze niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga |
| Indie — odczyt dostaw akcji | ⚠️ | 6 h 53 min | sesja 2026-11-05 · sprawdzone 2026-11-06 03:01 UTC | ostatnie udane sprawdzenie starsze niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga |
| Premia USDT — Turcja | ✅ | 8 d 0 h | 2026-10-29 | — |
| Premia USDT — Brazylia | ✅ | 8 d 0 h | 2026-10-29 | — |
| Premia USDT — RPA | ✅ | 8 d 0 h | 2026-10-29 | — |
| Premia USDT — Indonezja | ✅ | 8 d 0 h | 2026-10-29 | — |
| Premia USDT — Indie | ✅ | 8 d 0 h | 2026-10-29 | — |
| Premia USDT — Meksyk | ✅ | 8 d 0 h | 2026-10-29 | — |
| Krzywa rentowności USA (dni robocze) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Krzywa rentowności Niemiec (dni robocze) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Krzywa rentowności Japonii (dni robocze) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Krzywa rentowności strefy euro (dni robocze) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Krzywa rentowności Kanady (dni robocze) | ✅ | 33 h 55 min | 2026-11-04 | — |
| BIS: luka kredytowa (kwartalnie) | ✅ | 219 d 9 h | 2026-Q1 | — |
| BIS: obsługa długu (kwartalnie) | ✅ | 219 d 9 h | 2026-Q1 | — |
| BIS: ceny mieszkań (kwartalnie) | ✅ | 128 d 9 h | 2026-Q2 | — |
| BIS: należności banków wobec rynków wschodzących (kwartalnie) | ✅ | 128 d 9 h | 2026-Q2 | — |
| BIS: emisje obligacji międzynarodowych (kwartalnie) | ✅ | 128 d 9 h | 2026-Q2 | — |
| BIS: płynność globalna (kwartalnie) | ✅ | 128 d 9 h | 2026-Q2 | — |
| BIS: aktywa banków centralnych (miesięcznie) | ✅ | 97 d 9 h | 2026-07 | — |
| Inflacja r/r (miesięcznie, najnowszy miesiąc) | ✅ | 36 d 9 h | 2026-09 | — |
| Koniunktura: zaufanie konsumentów i firm (miesięcznie) | ✅ | 36 d 9 h | 2026-09 | — |
| Prąd w Polsce: cena w kwadransach, dziś i jutro (dziennie) | ✅ | 0 h 00 min | 2026-11-06 | — |
| Prąd i CO2: cena uprawnień do emisji (dziennie, także w weekend) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Prąd w Europie: ceny w 15 strefach (dziś i jutro) | ⚠️ | 0 h 00 min | 2026-11-06 | tylko 0 z 15 stref odświeżonych w ciągu 6 h (próg 10) — najwyżej uwaga (limit zapytań źródła: jedna strefa na przebieg) |
| Prąd w Europie: miks produkcji Niemiec, Polski i Francji (co 2 h na kraj) | ⚠️ | 11 h 10 min | 2026-11-05T22:45:00+00:00 | dane pobrane dawniej niż 8 h: DE, PL — najwyżej uwaga (limit zapytań źródła: jedno na przebieg) |
| Prąd w Polsce: przepływy z sąsiadami (co godzinę) | ⚠️ | 11 h 40 min | 2026-11-05T22:15:00+00:00 | dane pobrane dawniej niż 4 h — najwyżej uwaga (limit zapytań źródła: jedno na przebieg) |
| Prąd w Wielkiej Brytanii: miks i emisyjność (co 30 min) | ⚠️ | 6 h 51 min | 2026-11-06T03:04:42+00:00 | dane pobrane dawniej niż 3 h — najwyżej uwaga (limit zapytań źródła: jedno na przebieg) |
| Stres i niepewność: stres systemowy CISS (strefa euro; dni robocze) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Stres i niepewność: niepewność polityki USA (EPU) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Stres i niepewność: ryzyko geopolityczne (GPR) | ✅ | 3 d 9 h | 2026-11-02 | — |
| Kalendarz: terminarz Rezerwy Federalnej (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Kalendarz: terminarz PKB i inflacji PCE USA (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Kalendarz: terminarz sprzedaży i budownictwa USA (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Kalendarz: terminarz statystyk strefy euro (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Kalendarz: terminarz posiedzeń EBC (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Kalendarz 2: terminy inflacji i zatrudnienia USA (pobranie) | ✅ | 7 h 23 min | 2026-11-06T02:32:02+00:00 | — |
| Kalendarz 2: kalendarz danych Polski (pobranie) | ⚠️ | 7 d 3 h | 2026-10-30T06:06:17+00:00 | pobranie starsze niż 24 h 00 min (odświeżanie co 6 h) — terminy mogą być nieaktualne; najwyżej uwaga |
| Kalendarz 2: terminy decyzji banku Anglii (pobranie) | ✅ | 7 h 23 min | 2026-11-06T02:32:02+00:00 | — |
| Kalendarz 2: terminy posiedzeń banku Japonii (pobranie) | ✅ | 7 h 23 min | 2026-11-06T02:32:02+00:00 | — |
| Nowcasty: szacunek PKB USA (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Nowcasty: szacunek PKB USA (rytm aktualizacji) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Nowcasty: szacunek inflacji CPI USA (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Nowcasty: szacunek inflacji CPI USA (rytm aktualizacji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Europa fundusze: napływy do funduszy (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Europa fundusze: napływy do funduszy (rytm publikacji) | ✅ | 66 d 9 h | 2026-08 | — |
| Europa fundusze: oszczędności gospodarstw domowych (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Europa fundusze: oszczędności gospodarstw domowych (rytm publikacji) | ✅ | 128 d 9 h | 2026-Q2 | — |
| Płynność USA: stopy SOFR (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Płynność USA: SOFR (najnowszy dzień) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Płynność USA: operacje repo Fed (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Płynność USA: operacje repo (najnowszy dzień) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Płynność USA: wolumeny repo (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Płynność USA: wolumeny repo (najnowszy dzień) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Skarb USA: wpływy dzienne — cła i podatki (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Skarb USA: wpływy dzienne (rytm publikacji) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Skarb USA: emisje i umorzenia długu (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Skarb USA: dług dzienny (rytm publikacji) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Skarb USA: wykupy papierów z rynku (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Skarb USA: wykupy (rytm operacji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Eksport zbóż USA (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Eksport zbóż USA (rytm publikacji tygodniowej) | ✅ | 7 d 9 h | 2026-10-29 | — |
| Energia USA: raport ropy (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Energia USA: raport ropy (rytm publikacji) | ✅ | 6 d 9 h | 2026-10-30 | — |
| Energia USA: stopniodni (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Energia USA: stopniodni (rytm publikacji) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Azja: kontrakty w Japonii wg typu inwestora (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Azja: kontrakty w Japonii wg typu inwestora (data danych) | ✅ | 13 d 9 h | 2026-10-23 | — |
| Azja: stan posiadania zagranicy w Korei (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Azja: stan posiadania zagranicy w Korei (data danych) | ✅ | 36 d 9 h | 2026-09 | — |
| Azja: Shenzhen i ETF Chin (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Azja: Shenzhen i ETF Chin (data danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Azja: Shenzhen i ETF Chin — lista ETF (data danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Brazylia: fundusze (wpłaty i wypłaty) (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Brazylia: fundusze (wpłaty i wypłaty) (data danych) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Chiny: krzywa rentowności (pobranie) | ✅ | 7 h 47 min | 2026-11-06T02:08:33+00:00 | — |
| Chiny: krzywa rentowności (rytm sesji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Chiny: Shibor (pobranie) | ✅ | 7 h 47 min | 2026-11-06T02:08:33+00:00 | — |
| Chiny: Shibor (rytm sesji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Tajwan: put/call i pozycje (pobranie) | ✅ | 9 h 29 min | 2026-11-06T00:25:55+00:00 | — |
| Tajwan: put/call i pozycje — put/call (rytm sesji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Tajwan: put/call i pozycje — pozycje (rytm sesji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Hongkong: krótka sprzedaż (rytm sesji) | ✅ | 6 d 9 h | 2026-10-30 | — |
| Chiny: indeks CSI 300 (pobranie) | ✅ | 7 h 47 min | 2026-11-06T02:08:33+00:00 | — |
| Chiny: indeks CSI 300 (rytm sesji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Interwencje i rezerwy: Japonia (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Interwencje i rezerwy: Japonia (rytm publikacji) | ✅ | 8 d 9 h | 2026-10-28 | — |
| Interwencje i rezerwy: Hongkong (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Interwencje i rezerwy: Hongkong (rytm publikacji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Interwencje i rezerwy: Argentyna (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Interwencje i rezerwy: Argentyna (rytm publikacji) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Interwencje i rezerwy: Brazylia (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| Interwencje i rezerwy: Brazylia (rytm publikacji) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Interwencje i rezerwy: Kanada (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Interwencje i rezerwy: Kanada (rytm publikacji) | ✅ | 6 d 9 h | 2026-10-30 | — |
| Interwencje i rezerwy: oczekiwania w Brazylii (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Interwencje i rezerwy: oczekiwania w Brazylii (rytm publikacji) | ✅ | 6 d 9 h | 2026-10-30 | — |
| Kanada: aukcje obligacji (pobranie) | ✅ | 9 h 56 min | 2026-11-05T23:59:35+00:00 | — |
| Kanada: aukcje obligacji (rytm danych) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Kanada: posiadacze długu rządu (pobranie) | ✅ | 7 h 47 min | 2026-11-06T02:08:33+00:00 | — |
| Kanada: posiadacze długu rządu (rytm danych) | ✅ | 8 d 9 h | 2026-10-28 | — |
| Kanada: stawka CORRA (pobranie) | ✅ | 7 h 47 min | 2026-11-06T02:08:33+00:00 | — |
| Kanada: stawka CORRA (rytm danych) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Kanada: bilans Banku Kanady (pobranie) | ✅ | 7 h 47 min | 2026-11-06T02:08:33+00:00 | — |
| Kanada: bilans Banku Kanady (rytm danych) | ✅ | 8 d 9 h | 2026-10-28 | — |
| Kanada: ropociągi (Keystone, Trans Mountain) (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Kanada: ropociągi (Keystone, Trans Mountain) (rytm danych) | ✅ | 128 d 9 h | 2026-06 | — |
| FRED 2: serie (pobranie) | ✅ | 8 h 01 min | 2026-11-06T01:54:15+00:00 | — |
| FRED 2: serie (rytm publikacji) | ✅ | 12 d 9 h | 2026-10-24 | — |
| Kapitalizacje: USA (pobranie) | ✅ | 8 h 21 min | 2026-11-06T01:34:03+00:00 | — |
| Kapitalizacje: USA (rytm danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Kapitalizacje: Europa (7 krajów) (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Kapitalizacje: Europa (7 krajów) (rytm danych) | ✅ | 128 d 9 h | 2026-06-30 | — |
| Kapitalizacje: Japonia (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Kapitalizacje: Japonia (rytm danych) | ✅ | 6 d 9 h | 2026-10-30 | — |
| Skarbce spółek — BTC w spółkach publicznych (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Skarbce spółek — ETH w spółkach publicznych (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Wnioski o fundusze krypto w kolejce urzędu (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Fed: banki komercyjne w USA (tygodniowo) (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Fed: banki komercyjne w USA (tygodniowo) (rytm danych) | ✅ | 15 d 9 h | 2026-10-21 | — |
| Fed: papiery komercyjne (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Fed: papiery komercyjne (rytm danych) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Fed: papiery komercyjne (rytm stawek) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Fed: ankieta dealerów (fundusze hedgingowe) (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Fed: ankieta dealerów (fundusze hedgingowe) (rytm danych) | ✅ | 42 d 9 h | 2026-09-24 | — |
| Fed: ankieta kredytowa banków (pobranie) | ✅ | 14 h 16 min | 2026-11-05T19:39:03+00:00 | — |
| Fed: ankieta kredytowa banków (rytm danych) | ✅ | 7 d 9 h | 2026-10-29 | — |
| Krótka sprzedaż — Wielka Brytania (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Krótka sprzedaż — Wielka Brytania (data pozycji) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Krótka sprzedaż — Szwecja (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Krótka sprzedaż — Szwecja (data pozycji) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Rynki prognoz — cena BTC i ETH (pobranie) | ✅ | 6 h 53 min | 2026-11-06 03:01 UTC | — |
| Uwaga detalu — odsłony artykułów (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Uwaga detalu — odsłony artykułów (dzień danych) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Indeks sezonu altcoinów (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Indeks sezonu altcoinów (dzień danych) | ✅ | 0 h 00 min | 2026-11-06 | — |
| Ropa świata — bilans krajów (sprawdzenie źródła) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Ropa świata — bilans krajów (ostatni miesiąc danych) | ✅ | 66 d 9 h | 2026-08 | — |
| Ropa świata — zapasy w Europie (sprawdzenie źródła) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Ropa świata — zapasy UE27 (ostatni miesiąc danych) | ✅ | 97 d 9 h | 2026-07 | — |
| Złoto Wielkiej Brytanii (sprawdzenie źródła) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Złoto Wielkiej Brytanii (ostatni miesiąc danych) | ✅ | 66 d 9 h | 2026-08 | — |
| USA zadłużenie gospodarstw (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| USA zadłużenie gospodarstw (data danych) | ✅ | 128 d 9 h | 2026-06-30 | — |
| USA stopy hipoteczne (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| USA stopy hipoteczne (data danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| USA niepewność handlowa (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| USA niepewność handlowa (data danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| USA przewozy (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| USA przewozy (data danych) | ✅ | 66 d 9 h | 2026-08 | — |
| Waluty świata — kursy wobec dolara (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Waluty świata — kursy wobec dolara (dzień danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Waluty świata — kurs centralny juana (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Waluty świata — kurs centralny juana (dzień danych) | ✅ | 9 h 55 min | 2026-11-05 | — |
| Waluty świata — gilty i inflacja oczekiwana (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Waluty świata — gilty i inflacja oczekiwana (dzień danych) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Pozycje instytucji USA (13F) (sprawdzenie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Pozycje instytucji USA (13F) (dzień danych) | ✅ | 128 d 9 h | 2026-06-30 | — |
| Niedostarczone akcje USA (sprawdzenie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Niedostarczone akcje USA (dzień danych) | ✅ | 36 d 9 h | 2026-09-30 | — |
| USA nastroje konsumentów (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| USA nastroje konsumentów (data danych) | ✅ | 5 d 9 h | 2026-10 | — |
| USA oczekiwana inflacja gospodarstw (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| USA oczekiwana inflacja gospodarstw (data danych) | ✅ | 36 d 9 h | 2026-09 | — |
| Strefa euro oczekiwana inflacja (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Strefa euro oczekiwana inflacja (data danych) | ✅ | 36 d 9 h | 2026-09 | — |
| USA zadłużenie marżowe (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| USA zadłużenie marżowe (data danych) | ✅ | 36 d 9 h | 2026-09 | — |
| RPA (pobranie) | ✅ | 8 h 01 min | 2026-11-06 01:54 UTC | — |
| RPA (data danych) | ✅ | 2 d 9 h | 2026-11-03 | — |
| RPA inflacja (data danych) | ✅ | 36 d 9 h | 2026-09 | — |
| Indie płynność banków (pobranie) | ✅ | 8 h 01 min | 2026-11-06 01:54 UTC | — |
| Indie płynność banków (data danych) | ✅ | 33 h 55 min | 2026-11-04 | — |
| Izrael fundusze (pobranie) | ✅ | 14 h 16 min | 2026-11-05 19:39 UTC | — |
| Izrael fundusze (data danych) | ✅ | 36 d 9 h | 2026-09 | — |
| Przekazy migrantów (pobranie) | ✅ | 14 h 16 min | 2026-11-05 19:39 UTC | — |
| Przekazy migrantów (data danych) | ✅ | 309 d 9 h | 2025-12 | — |
| Pogoda: El Niño (ONI) (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Pogoda: El Niño (ONI) (data danych) | ✅ | 36 d 9 h | 2026-09 | — |
| Pogoda: susza w USA (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Pogoda: susza w USA (data danych) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Pogoda: Ren w Kaub (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Pogoda: Ren w Kaub (data danych) | ✅ | 0 h 00 min | 2026-11-06 | — |
| Pogoda: Missisipi (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Pogoda: Missisipi (data danych) | ✅ | 2 d 9 h | 2026-11-03 | — |
| Pogoda: temperatura świata (pobranie) | ✅ | 14 h 42 min | 2026-11-05 19:12 UTC | — |
| Pogoda: temperatura świata (data danych) | ✅ | 6 d 9 h | 2026-10-30 | — |
| Pogoda: pas kukurydzy USA (pobranie) | ✅ | 8 h 37 min | 2026-11-06 01:17 UTC | — |
| Pogoda: pas kukurydzy USA (data danych) | ✅ | 0 h 00 min | 2026-11-06 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś — — ? brak odczytu.
- TGA 2026-11-04: Fiscal Data 936 248 vs FRED 936 248 mln USD — różnica 0.00% — ✅ próg stały 1% (stan na środę = saldo zamknięcia tego dnia).
- Podaż stablecoinów, dwa źródła: 293.7 vs 273.4 mld USD — różnica dziś +7.42%, norma (mediana 30 dni) +7.89% — ✅ odchylenie od mediany 0.47 pkt proc. (progi 2).
- Rentowność 10L USA (Skarb USA vs H.15 — Fed, te same dni): porównane 9 dat (do 2026-11-04), różnice > 0.02 pkt proc.: 0 ✅.
- Stopy banków centralnych (strona vs źródło banku, ten sam dzień): Fed 3,875% = 3,875% (NY Fed) ✅; EBC 2,5% = 2,5% (EBC) ✅; Bank Anglii 3,75% = 3,75% (BoE) ℹ️ (zmiana 2026-11-05 na 4% — strona jeszcze bez niej); Bank Szwajcarii 0% = 0% (SNB) ✅; Bank Szwecji 1,75% = 1,75% (Riksbank) ✅; Bank Norwegii 4,5% = 4,5% (Norges Bank) ✅; NBP 3,75% = 3,75% (NBP) ✅; Bank Kanady 2,5% = 2,5% (BoC) ✅; Bank Brazylii 13,75% = 13,75% (BCB) ✅.
- Kursy walut (strona: kurs EBC; H.10: Fed, Nowy Jork; te same dni): 2025-11-05 — 20 walut, mediana różnicy 0,14%, najwięcej BRL +0,80%; 2026-08-05 — 20 walut, mediana różnicy 0,06%, najwięcej NOK -0,22%; 2026-10-05 — 20 walut, mediana różnicy 0,06%, najwięcej ZAR -0,22%; 2026-10-29 — 20 walut, mediana różnicy 0,16%, najwięcej BRL -0,80% ✅.
- Indeksy giełdowe: świeże 23 z 24 (do 2026-11-05); bez danych (dostawca nie podaje): JTOPI ℹ️; zamknięcia poprawione przez dostawcę po pobraniu (7 dni): DJI 2026-11-05 -0,44%, GSPC 2026-11-05 -0,54%, IXIC 2026-11-05 -0,68%, MXX 2026-10-30 +0,11%, MXX 2026-10-29 +0,50%, GDAXI 2026-10-29 -0,05%, FTSE 2026-10-29 -0,04%; ostatnia sesja pobrana za wcześnie: DJI, FTSE, GDAXI, GSPC, IXIC, MXX ℹ️; pora pobierania przesunięta (nauczone z poprawek i spóźnień dostawcy): AEX +3 h, BSESN +1 h, FTSE +1 h, GDAXI +2 h, KS11 +1 h, MXX +1 h, TA125 +1 h, XU100 +1 h ℹ️.
- Indeksy vs wydawcy (FRED, 45 dni): S&P 500 — zgodne 32 z 32 sesji (wydawca do 2026-11-04) ✅ · Nasdaq Composite — zgodne 32 z 32 sesji (wydawca do 2026-11-04) ✅ · Dow Jones — zgodne 33 z 33 sesji (wydawca do 2026-11-05) ✅ · Nikkei 225 — zgodne 29 z 29 sesji (wydawca do 2026-11-05) ✅.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-11-06 vs 2026-11-05: nowa lista portfeli — bez porównania: Bybit, OKX; odstęp migawek 123.0 h — porównanie z przepływami 24 h tylko przy ok. dobie; migawki o północy brak albo później niż 2 h po północy UTC: 2026-11-05 — Binance, Bitfinex, Bybit, KuCoin, OKX ℹ️.
- Listy portfeli giełd z raportów miesięcznych (wiek): OKX 5 dni, Bybit 10 dni, KuCoin 67 dni ℹ️ — starzenie bez alarmu: strona pokazuje datę listy i jej wiek (⚠️ po 180 dniach).
- Nowe raporty dowodu rezerw giełd (listy portfeli; sprawdzone dziś): OKX — sprawdzanie od 2026-11-21 (raport miesięczny); Bybit — sprawdzanie od 2026-11-16 (raport miesięczny); KuCoin — audyt z 2026-10-31, raport z listą portfeli jeszcze niedostępny ℹ️.
- Samodzielne odświeżanie list portfeli giełd z raportów PDF (Bybit, KuCoin; codziennie): Bybit — raport miesięczny — sprawdzanie od 2026-11-16 ✅; KuCoin — audyt z 2026-10-31 jest, link do raportu jeszcze niepodany ℹ️.
- Lista portfeli OKX (z 2026-11-01): automat odświeża sam (ostatni przebieg 2026-11-05); ostrzeżenie, gdy odświeżenie zawodzi > 7 dni ✅.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.33% (2026-10-30), norma (mediana 54 dni) +0.14% — ✅ odchylenie najnowszego dnia od normy 0.19 pkt proc. (próg 1.5), norma +0.14% (próg ±3%).
- Premie krypto: USA BTC -0.01% (przez USDC -0.03%, różnica 0.02 pkt proc.); Korea BTC +1.25% (kurs z 2026-11-05); kurs KRW/USD 2026-11-05: wprost 1344.690, w pliku rynki 1344.690 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 5 (2026-10-15 – 2026-11-04), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-11-05, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 5 (2026-10-15 – 2026-11-04), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-11-05, nowszych sesji na stronie: 0; czeka na porównanie: 0.
- ETF bitcoina — druga, niezależna kontrola przepływu ARKB (zmiana liczby BTC w pliku emitenta × cena z pliku vs przepływ na stronie; próg max 1 mln USD / 10%): ℹ️ porównane sesje: 2 (2026-11-04 – 2026-11-05), różnic ponad próg: 2 — 2026-11-04: -18.9 mln USD; 2026-11-05: -38.8 mln USD; pominięte: 2026-11-02 (brak przepływu strony z tego dnia), 2026-11-03 (brak przepływu strony z tego dnia), 2026-11-06 (brak przepływu strony z tego dnia); plik emitenta do 2026-11-06.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.32%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.12%, MEP ✅ 0.78%, CCL ✅ 1.60%; hurtowy vs bank centralny (2026-11-05) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-10-28: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-11-04: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.779 z 25 tygodni, ten sam kierunek w 22 z 22 (oba ≥ 50 mld JPY); ostatni tydzień 2026-10-23: giełda +24.4 vs MOF +1182.2 mld JPY.
- Surowce (porównania z pliku strony): złoto 2026-09 (archiwum funduszu vs MFW): -0,32% (próg 0,75%) ✅ · ropa Brent 2026-10 (EIA vs Bank Światowy): -0,86% (próg 4%) ✅ · ropa WTI 2026-10 (EIA vs Bank Światowy): +4,47% (próg 4%) ⚠️ · miedź 2026-09 (MFW vs Bank Światowy): -0,01% (próg 1%) ✅ · zapasy ropy i paliw: plik raportu vs API, 2026-10-30: porównane 5 serii, zgodne ✅ · gaz w magazynach: plik raportu vs API, 2026-10-30: porównane 1 serii, zgodne ✅ · ceny: strona dzienna vs API, 2026-10-29: porównane 5 serii, zgodne ✅ · gaz w magazynach USA, średnia 5 lat 2026-10-30: wyliczona 3 745 vs EIA 3 747 Bcf (-0,06%) ℹ️ · Brent dostawa fizyczna vs kontrakt, zmiany dzienne z 30 wspólnych dni: największa różnica 2026-10-02 (+18,0% vs -0,1%) ℹ️ · fundusze: GLD 2026-11-04 — wartość aktywów ÷ (uncje × cena złota) − 1 = -0,039% (próg 0,1%) ✅ · fundusze: GLDM 2026-11-04 — wartość aktywów ÷ (uncje × cena złota) − 1 = -0,010% (próg 0,1%) ✅ · banki: Chiny — MFW vs SAFE, 6 wspólnych mies. (do 2026-06): zgodne ℹ️ · banki: Polska — druga tabela MFW wobec głównej, 6 wspólnych mies. (do 2026-09): zgodne ✅ · banki: Rosja — druga tabela MFW wobec głównej, 6 wspólnych mies. (do 2025-11): zgodne ✅ · banki: odczyt Rosji 2026-09 (druga tabela MFW), 1 mies. za najnowszym odczytem na liście (próg 4) ✅ · banki: skok zapasu o ponad 50 t w miesiącu u kraju bez wcześniejszych ruchów (55 krajów) — brak ✅ · pozycje: rynków z bieżącego raportu — USA 30, Londyn 7, fundusze indeksowe 13, indeks 1, Abu Zabi 1 ℹ️.
- Szlaki handlowe i łańcuchy dostaw (z pliku strony): cieśniny: sumy i zakres ✅ · wskaźnik presji: zakres i skoki ✅ · indeks cen surowców: skoki tygodniowe ✅.
- Porty świata (z pliku strony): świat wg ładunku: zmiany i zakres ✅ · porty: zmiany i zakres ✅.
- Metale przemysłowe (z plików strony): miedź w Londynie 2026-10-16: raport tygodniowy vs zapas dzienny ✅ · miedź w Szanghaju (tydzień 2026-10-16): raport tygodniowy vs raport giełdy ✅ · średnie miesięczne cen (6 metali) vs Bank Światowy ✅.
- Gaz i LNG (z pliku strony): terminale UE: zakres i skoki dobowe ✅ · Świnoujście: zakres ✅ · suma dób miesiąca: terminale UE razem wobec importu UE27 ✅ · suma dób miesiąca: Świnoujście wobec importu Polski ✅.
- Rosja (z pliku strony): import UE z Rosji (UE, EUR) ↔ eksport Rosji do UE (Rosja, USD) 2026-07: iloraz 1,04 ✅ · eksport UE do Rosji ↔ import Rosji z UE 2026-07: iloraz 1,09 (inna metoda — informacja) ⚠️ · cena uncji z wartości złota w rezerwach i tonażu 2025-11: 4 191 USD ✅ · kopia złota zgodna ze źródłem 2026-09 ✅.
- Polska na rynku: giełda, obligacje, fundusze (z pliku strony): WIG20 2026-11-05: giełda 4209,15 ↔ drugi dostawca 4209,15 (różnica 0,00%) ✅ · krzywa 2026-11-05: „10 lat” minus „2 lata” = 1,48 pp ✅ · krzywa 2026-11-05: „10 lat” minus 10 lat Niemiec (3,31%) = 2,78 pp ✅ · krzywa 2026-11-04 → 2026-11-05: średnia zmiana rentowności serii 0,05 pp ✅ · członkowie giełdy 2026-10: siedziba za granicą 66,3% · w Polsce 32,8% · nieustalona 0,9% (obroty razem 115154 mln zł) ✅.
- Polska: kapitał z zagranicy i wypłaty UE (z pliku strony): 2026-Q2 do Polski: kwartał 4 430 mln EUR ↔ suma 3 miesięcy z pliku miesięcznego 4 436 mln EUR (różnica 6) ✅ · 2026-Q2 z Polski: kwartał 482 mln EUR ↔ suma 3 miesięcy z pliku miesięcznego 482 mln EUR (różnica 0) ✅.
- Polska: dług skarbowy i obligacje detaliczne (z pliku strony): Zagranica: 25 wspólnych miesięcy z plikiem nierezydentów, największa różnica 0,05 mln zł (2025-05: struktura 157 223,7 ↔ nierezydenci 157 223,7) ✅.
- Polska 2: dług zagraniczny, depozyty, WIBOR, WIRON, ceny mieszkań (z pliku strony): bez sprzeczności ✅.
- Giełdy scentralizowane, DEX i kontrakty na łańcuchu (z plików strony): podejrzany skok listy portfeli (próg planu F6Z1): brak ✅ · przepływ 7 dni ponad 25% salda (saldo ≥ 10 mln USD): VALR, BitKan, Zoomex — poza sumą 7 dni ℹ️ · przepływ 30 dni ponad 50% salda (saldo ≥ 10 mln USD): Poloniex, Gate US, CoinEx — poza sumą 30 dni ℹ️ · suma sald między dobami 2026-11-05 → 2026-11-06: +0,3% ✅ · znak przepływu 7 dni: giełdy z listy (wszystkie aktywa) minus; BTC + ETH z drugiego źródła (do 2026-11-05) minus (inne zbiory portfeli i aktywów — tylko informacja) ✅ · obrót DEX doby ÷ obrót spot giełd scentralizowanych (kroczące 24 h): 0,14 ✅.
- Salda TARGET krajów strefy euro (z pliku strony; porównanie z panelem „dane urzędowe”): spójność pliku (miesiące rosnące, suma sald = 0) ✅ · zgodność z panelem „dane urzędowe” (27 porównań kraj-miesiąc) ✅.
- Rejestry MiCA (z pliku strony): spójność pliku (sumy w krajach, usługi, szereg) ✅.
- BIS: kredyt, obsługa długu, wierzyciele i płynność (z pliku strony): porównanie zmiany r/r kredytu w trzech walutach: zgodne ✅.
- Indie, wycena indeksów, pozycje w kontraktach i dostawy akcji (z pliku strony): spójność pliku (wycena, pozycje, dostawy, historia) ✅.
- Hyperliquid (ranking kont, pozycje) i pożyczki DeFi (z pliku strony): spójność pliku (ranking kont Hyperliquid, pozycje, pożyczki DeFi) ✅.
- DeFi 2, opłaty, ceny stablecoinów, włamania i opcje (z pliku strony; porównanie podaży USDT z plikiem emitentów tylko informacyjnie): niespójności w pliku: opłaty: kategorie razem większe niż suma serwisu ⚠️ · spójność pliku (sumy, sortowanie, serie, lata) ⚠️ · podaż USDT zgodna z plikiem emitentów ✅.
- Dźwignia krypto 2, nastroje detalu i kredyt marżowy (z pliku strony; porównanie z dzwignia.json tylko informacyjnie): spójność pliku (doby, pasma, wolumeny, pozycje, historia) ✅ · stosunek kont long/short różni się od dzwignia.json (ETH: 3,41 i 3,38) ℹ️.
- Fundusze ETF w Europie, dzienne przepływy netto pięciu grup (z pliku strony; wiek części, dzień danych, historia największych funduszy): spójność pliku (zestawienie, największe fundusze, historia, szereg przepływów) ✅ · dzień danych zestawienia 2026-11-04 jest 2 d przed dobą kontroli ✅ · odrzucone skoki liczby jednostek: 0 z 4128 par notowań (0,0%) ✅ · grupy z gotowym szeregiem przepływów: 5 z 5 ✅.
- Ethereum i warstwa 2, kolejki stakingu, podaż i sieci L2 (z pliku strony; porównanie TVL z drugim źródłem): spójność pliku (kolejki, spalanie, podaż, sieci L2) ✅ · dzień danych sieci L2 2026-11-04 ma 2 d wobec doby odczytu ✅ · TVL sieci L2 zgodny z drugim źródłem (stosunek 0,96) ✅ · największe sieci zgodne z drugim źródłem ✅.
- Skarbce spółek (BTC, ETH) i wnioski o fundusze krypto w kolejce urzędu (z pliku strony; cena BTC z posiadania spółek wobec pliku cen krypto tylko informacyjnie): spójność pliku (sumy, sortowanie, cena, historia, zrzuty, wnioski) ✅.
- Azja i Brazylia: kontrakty w Japonii, stan posiadania zagranicy w Korei, Shenzhen i ETF Chin oraz fundusze w Brazylii (z pliku strony): spójność pliku (Japonia, Korea, Shenzhen i ETF, fundusze w Brazylii) ✅.
- Krótka sprzedaż w Europie: pozycje netto w Wielkiej Brytanii i w Szwecji (z pliku strony): spójność pliku (liczniki, ranking, rozkład, zmiana od zrzutu, historia, zrzuty) ✅.
- Rynki prognoz i uwaga detalu: cena BTC i ETH według rynku prognoz, odsłony artykułów, indeks sezonu altcoinów (z pliku strony): spójność pliku (drabiny progów, serie odsłon, średnie, indeks altcoinów) ✅.
- Ropa świata (bilans krajów i zapasy ropy i paliw w Europie; z pliku strony; wydobycie USA i zapasy Polski z drugim źródłem tylko informacyjnie): spójność pliku (miesiące, długości serii, zakresy, suma UE27 = suma 27 państw) ✅.
- Złoto w handlu Wielkiej Brytanii, import i eksport wg miesięcy i krajów (z pliku strony): spójność pliku (miesiące, długości serii, zakresy, kraje wobec sumy) ✅.
- Sektory krypto i Top 10 w scenie CRYPTO (z plików strony; kontrola tylko raportuje, niczego nie zmienia): każda moneta w jednym sektorze (znane sektory, bez powtórzeń) ✅ · identyfikatory i wiersze (bez stablecoinów, BTC i ETH w L1) ✅ · kolejność i zgodność kapitalizacji z rankingiem ogólnym ✅ · komplet monet w sektorach ✅ · świeżość składu sektorów ✅ · logo monet ✅ · poza rankingiem ogólnym mimo kapitalizacji powyżej jego dolnej granicy: FIGR_HELOC, 币安人生 ℹ️.
- USA: zadłużenie gospodarstw, stopy hipoteczne, niepewność handlowa i przewozy (z pliku strony): spójność pliku (zadłużenie, stopy hipoteczne, niepewność handlowa, przewozy) ✅.
- Waluty świata, kurs centralny juana, gilty i inflacja oczekiwana (z pliku strony): spójność pliku (waluty, kurs centralny juana, gilty i inflacja oczekiwana) ✅.
- Pozycje instytucji USA (13F) i niedostarczone akcje (z pliku strony): spójność pliku (pozycje instytucji USA, niedostarczone akcje) ✅.
- Nastroje konsumentów, oczekiwana inflacja i zadłużenie marżowe (z pliku strony): spójność pliku (nastroje konsumentów, oczekiwana inflacja, zadłużenie marżowe) ✅.
- Rynki wschodzące: RPA, płynność banków Indii, fundusze Izraela i przekazy migrantów (z pliku strony): spójność pliku (RPA, płynność banków Indii, fundusze Izraela, przekazy migrantów) ✅.
- Pogoda i klimat: El Niño, susza w USA, Ren, Missisipi, temperatura świata i pas kukurydzy (z pliku strony): spójność pliku (El Niño, susza, Ren, Missisipi, temperatura świata, pas kukurydzy) ✅.
- USDT na żywo, skarbiec emitenta (z pliku strony; porównanie z raportem emitenta tylko informacyjnie): spójność pliku (saldo, podaż, 30 dób, zdarzenia, historia) ✅ · Ethereum: skarbiec w sieci 3,50 mld, w raporcie emitenta 3,29 mld (z 2026-11-05), różnica 206 mln — ruch po raporcie; podaż w sieci 84,30 mld a „wybite” w raporcie 84,30 mld (+0,000%, bez emisji i umorzeń po raporcie) ℹ️ · Tron: skarbiec w sieci 1,71 mld, w raporcie emitenta 1,71 mld (z 2026-11-05), różnica −1 mln — ruch po raporcie ℹ️.
- Premie USDT na lokalnych giełdach (z pliku strony; jeden odczyt na dzień roboczy po opublikowaniu kursu referencyjnego): spójność pliku (doby, premie, minuty, koszyk) ✅.
- Emitenci stablecoinów (z pliku strony; porównania z drugim źródłem tylko informacyjnie): spójność pliku (sieci, kapitał, sumy, zabezpieczenie) ✅ · suma emitentów a podaż z drugiego źródła: różnica dziś +7.52% (norma +8.30%, mediana 24 dni) — odchylenie od mediany 0.78 pkt proc. (progi 2) ✅ · USDC: raport Circle a lista monet: różnica dziś -0.32% (norma -0.19%, mediana 24 dni) — odchylenie od mediany 0.13 pkt proc. (progi 1) ✅ · USDT: zobowiązania w raporcie Tether a lista monet: różnica dziś +0.16% (norma +0.13%, mediana 24 dni) — odchylenie od mediany 0.03 pkt proc. (progi 1) ✅.
- Płynność dolara i euro oraz fundusze hedgingowe (z plików strony; porównanie z panelem „dane urzędowe”): portfel Fed razem: zgodność z panelem „dane urzędowe” (12 wspólnych tygodni) ✅ · aktywa Eurosystemu razem: zgodność z panelem „dane urzędowe” (13 wspólnych tygodni) ✅ · spójność plików (dni rosnące, sumy grup, szczyt, brutto ≥ netto) ✅.
- Krzywe rentowności (z plików strony; porównanie 10L USA i Niemiec z rynki.json): rentowność 10L USA: zgodność z plikiem rynki (2 wspólne dni) ✅ · rentowność 10L Niemcy: zgodność z plikiem rynki (2 wspólne dni) ✅ · spójność pliku (dni, „miesiąc temu”, liczby, różnice nominalna − realna, wszyscy − AAA) ✅.
- Inflacja, koniunktura i stopy realne (z plików strony; inflacja USA a CPI-U z pliku usa-makro tylko informacyjnie): inflacja USA 2026-09: 3.74 % (plik inflacja) a 3.7 % (CPI-U z pliku usa-makro) — tylko informacja ✅ · stopa realna policzona dla 35 z 37 banków (reszta: brak inflacji albo starsza niż 3 mies. od stanu stopy) ✅ · spójność plików (miesiące, liczby, Polska w obu miarach zaufania) ✅.
- Prąd i CO2 (z pliku strony): Polska 2026-11-06: średnia 1237.9 zł/MWh, minimum 614.2, maksimum 2706.1; kwadransów z ceną ujemną: 0 (dozwolone — tylko informacja) ℹ️ · Polska 2026-11-06: RCE 281.9 €/MWh (po kursie z ceny CO2) wobec strefy Polska 267.9 €/MWh — różnica 5.2% ⚠️ · Polska 2026-11-06: RCE 1237.9 zł/MWh wobec indeksu giełdowego 1254.8 zł/MWh (inny rynek) — różnica 1.3% ✅ · Miks DE 2026-11-06: odnawialne 39.4% z podziału wobec 40.7% z serii źródła — różnica 1.3 pkt proc. ✅ · Miks PL 2026-11-05: odnawialne 11.6% z podziału wobec 11.6% z serii źródła — różnica 0.0 pkt proc. ✅ · Miks FR 2026-11-06: odnawialne 7.6% z podziału wobec 8.0% z serii źródła — różnica 0.4 pkt proc. ✅ · Przepływy Polski 2026-11-05T22:15:00+00:00: saldo -850 MW (eksport; tylko informacja) ℹ️ · Wielka Brytania 2026-11-06T02:30Z: emisyjność 229 gCO2/kWh, skala „high” (tylko informacja) ℹ️.
- Stres i niepewność (CISS, EPU, GPR; z pliku strony; CISS USA a indeks stresu USA tylko informacyjnie): CISS USA a indeks stresu USA (plik stres): korelacja poziomów 0.23 na 259 wspólnych dniach — tylko informacja ℹ️ · spójność pliku (zakresy, skoki dzienne, wykresy, percentyle, komplet obszarów) ✅.
- Kalendarz (z pliku strony): terminy w następnych 14 dniach: 10 (w tym wagi 3: 1) ✅.
- Kalendarz 2 (z pliku strony): terminy: FRED 4, GUS 4, BoE 1, BoJ 0 ✅.
- Nowcasty (z pliku strony): PKB: szacunek dla 2026-Q4 (3.4%) a ostatni odczyt 2026-Q3 (3.4%) ✅ · CPI: szacunek dla 2026-10 a ostatni odczyt 2026-09 (3.7% r/r) ✅ · CPI r/r: szacunek 3.74% a ostatni odczyt 3.7% (różnica 0.04 pp) ✅ · CPI: ostatni odczyt 2026-09 0.65% m/m (szacunek przed odczytem 0.53%) ✅.
- Europa: fundusze i oszczędności domowe (z pliku strony): gospodarstwa domowe: 7 krajów z kwartałem 2026-Q2 ✅ · fundusze: razem w strefie euro 2026-08 = 65052.5 mln EUR (wstępnie) ✅.
- Płynność USA (z pliku strony): SOFR: bank nowojorski 3.94% / lustro urzędu badań 3.94% (2026-11-04; zgodność w 10 z 10 dni) ✅ · SOFR: lista 3.94% i najnowszy odczyt stóp 3.94% (2026-11-04) ✅ · EFFR 3.88% a korytarz docelowy 3.75–4.0% (2026-11-04) ✅ · SOFR − EFFR: +0.06 pp (informacyjnie; duży rozstęp bywa prawdziwym napięciem rynku, nie błędem danych) ✅ · stałe repo: stopa minimalna 4.0% a górna granica korytarza 4.0% ✅ · odwrotne repo: stopa 3.75% a dolna granica korytarza 3.75% (2026-11-05) ✅.
- Skarb USA, wpływy i dług dzienne, wykupy (z pliku strony): dzień wpływów a saldo konta Skarbu ✅ · wykupy a umorzenia obligacji (13 operacji) ✅.
- Eksport zbóż i soi z USA wg kraju kupującego (z pliku strony): tożsamość wysyłek (24 tygodni) ✅ · nazwy krajów bez kodu ⚠️.
- Energia USA, rafinerie, zapasy, import ropy i stopniodni (z pliku strony): zapas benz a surowce (us_gasoline) ✅ · zapas dest a surowce (us_dist) ✅ · zapas nafta a surowce (us_jet) ✅ · tydzień raportu a surowce ✅.
- Chiny, Tajwan, Hongkong: obligacje, Shibor, CSI 300, put/call, krótka sprzedaż (z pliku strony): CSI 300: zamknięcie a zmiana % w kolejnych sesjach ✅.
- Interwencje walutowe i rezerwy banków centralnych (z pliku strony): rezerwy Brazylii 2026-09: dziennie a MFW ✅ · rezerwy Brazylii 2026-08: dziennie a MFW ✅ · rezerwy Brazylii 2026-07: dziennie a MFW ✅.
- Kanada: aukcje obligacji, posiadacze długu, CORRA, bilans Banku Kanady, ropociągi (z pliku strony): Bank Kanady: papiery w posiadaczach długu a w bilansie (2026-10-28) ✅.
- FRED 2, premia terminowa, dolar, spready kredytowe, warunki finansowe i zasiłki (z pliku strony): oczekiwana inflacja 10 lat (nominalna − realna) a krzywa USA ✅.
- Kapitalizacje rynków akcji, USA / siedem krajów Europy / Japonia (z pliku strony): —.
- Fed: banki komercyjne USA, papiery komercyjne, ankieta dealerów, ankieta kredytowa banków (z pliku strony): banki komercyjne w USA (tygodniowo) 2026-10-21 ✅ · papiery komercyjne 2026-11-04 ✅ · papiery komercyjne stawki 2026-11-04 ✅ · ankieta dealerów (fundusze hedgingowe) 2026-09-24 ✅ · ankieta kredytowa banków 2026-10-29 ✅.
- Wierzyciele i dłużnicy świata, pozycja inwestycyjna ok. 100 gospodarek (z pliku strony): IIP: kwartał 2026-Q2, 102 krajów ✅.
- Surowce całą dobę, kontrakty na ropę, gaz, złoto, srebro i miedź (z pliku strony): Surowce 24/7: 6 z 6 kontraktów, najstarszy odczyt sprzed 7.3 h (złoto) ⚠️.
- Surowce — raporty miesięczne (podaż ropy, zboża, uran; z plików strony): ropa: wydanie 2026-10-06, szacunki do 2026-09, prognoza od 2026-10; OPEC+ = objęci porozumieniem + pozostali uczestnicy, cały OPEC ≥ objęci ✅ · zboża: raport 2026-10 (nr 676), sezon 2026/27; z poprzednim raportem: 8 z 8 wpisów ℹ️ · uran 2026-10-30: wycena funduszu fizycznego (2026-10-30) 92,74 vs średnia branżowa 91,55 USD/lb (+1,30%) — informacja (inne definicje i chwile wyceny), bez progu ℹ️.
- Zboża dziennie i koszt transportu (z plików strony): indeks dzienny: skoki dnia ✅ · indeks frachtu: skoki tygodnia ✅ · podindeksy żywności: skoki miesiąca ✅ · ceny w UE: skoki tygodnia ✅ · nawozy w UE: skoki miesiąca ✅ · indeks dzienny: tabela źródła vs seria ✅ · indeks dzienny vs podindeks zbóż w żywności (zmiany miesięczne) ✅ · indeks dzienny vs indeks zbóż świata (zmiany miesięczne) ✅ · azot w UE vs indeks nawozów świata (zmiany miesięczne) ✅ · pszenica w Polsce: ten sam portal w dwóch plikach ✅.
- Surowce — pozycje funduszy USA, plik tygodniowy vs drugi kanał urzędu (ten sam raport): raport 2026-10-27: 29 rynków × 14 liczb i 349 wcześniejszych wpisów rynków (open interest i netto funduszy zarządzających) — zgodne ✅.
- Polska (porównanie z plików strony): złoto w Polsce 2026-11-05 (zł/g) vs cena w USD z 2026-11-04 × kurs USD/PLN: +0,22% (próg 3%) ✅ · ceny na stacjach: tydzień 2026-11-02 — obniżony VAT na paliwa (akcyza i opłaty, jakie musiałyby być w cenie benzyny przy VAT 23%: 0,803 zł/l, mniej niż 0,85 × minimalna akcyza UE 1,586 zł/l); strona to opisuje ℹ️.
- Tokenizowane aktywa (RWA): zmiana 7 dni produktów z listy: własna -6.05% vs źródło -4.38% (różnica 1.67 pkt proc.) ⚠️; ℹ️ produkty spoza listy z wartością 0 (próg 20) — źródło nie podaje ich wartości od 2026-10-05 (32 dni, stan trwały); bez bieżącej wyceny 0,0% sumy — bez uwagi; produkty spoza listy: z bieżącą wartością 0, bez bieżącej wyceny 0 ✅; skoków sumy ponad 25% w tygodniu: brak ✅.
- Tokenizowane aktywa — odczyt własny z łańcucha: podaż 24 h: zmian ponad 50% brak ✅; wartość vs ostatnio znana: w paśmie 1/3–3× ✅; w sumach z odczytu własnego: 7 z 7 produktów, 9.8 mld USD.
- Tokenizowane aktywa — dane emitentów: w sumach wg emitentów: 14 z 14 produktów, 11.7 mld USD; inny zakres niż ostatnio znana (opisane na stronie): Centrifuge Protocol 732 mln USD vs ostatnio znana 1482 mln (0.49×); Ondo Global Markets 1373 mln USD vs ostatnio znana 966 mln (1.42×); Securitize Tokenized AAA CLO Fund 284 mln USD vs ostatnio znana 104 mln (2.74×); xStocks 1068 mln USD vs ostatnio znana 438 mln (2.44×) ℹ️; Ondo Global Markets: punkt dnia emitenta (2026-11-05) 1373 mln USD vs liczba w nagłówku jego strony 1365 mln (+0.54%) — w sumach punkt dnia (nagłówek bez daty) ℹ️; xStocks: reszta listy emitenta poza odczytem (515 tokenów) najwyżej 4.93 mln USD (0.461% wartości) ℹ️; xStocks: pominięte tokeny bez dowodu rezerw u emitenta — 3 tokeny (np. WBDx, KVUEx, MSGSx), w obiegu łącznie 2358.93 — najwyżej 149.3 tys. USD (0.014% wartości), odczyt 2026-11-06 01:55 UTC ℹ️.

## Kontrola zakładek GLOBAL, CRYPTO i TRENDY (przeglądarka bez okna, ekran telefonu 390 px)

- Zakres: przełączanie zakładek, przełączniki i zakresy, rozwijanie bloków, wykresy, błędy JavaScriptu, napisy-błędy, czas pierwszego widoku; potem to samo przy 7 podmienionych plikach danych (kopia strony, żywa strona bez zmian). Kroków: 119; czas: 79,8 s.

### GLOBAL
- ✅ przełączenie zakładki
- ✅ rysowanie wykresów (159, w 58 panelach)
- ✅ napisy-błędy (NaN, undefined…)
- ✅ czas pierwszego widoku (1,0 s)
- ✅ powrót do zakładki GLOBAL (wykresów 1 z 1)
- ✅ Przełączniki i zakresy (9): Okres (GLOBAL): DZIŚ, 1T, 1KW, 1R · Kalendarz makro (Okres kalendarza): Dzień, Miesiąc · Widok: Karty / Wykresy: Wykresy · Archiwum własne — świat (Okno czasu): 30 dni, 365 dni
- ✅ Rozwijane bloki (50): Gdzie warunki sprzyjają wzrostom, a gdzie spa…, Krzywe rentowności obligacji rządowych, Jakość danych mapy, Strach i chciwość GLOBALi, Przepływy kapitału USA ↔ świat, Przepływy bankowe między regionami (pomiar kw…, Dokąd płynie kapitał portfelowy, Kto trzyma czyje papiery, Pozycje w kontraktach na euro i inne rynki, Surowce — paliwo gospodarki, USA: energia, gospodarka i przepływ kapitału, Kto kupuje amerykańskie zboże i soję, USA: kredyty hipoteczne, długi gospodarstw, n…, USA: dokąd płyną pieniądze inwestorów — fundu…, Indeksy giełdowe świata, Archiwum własne — świat, Aukcje papierów skarbowych USA: popyt (stosun…, Kanada: kto kupuje i trzyma dług, stopa na je…, Banki USA: kredyty, papiery komercyjne i waru…, Wielkość rynków akcji: USA, Europa, Japonia —…, Szwajcaria: depozyty banków w banku centralny…, Interwencje walutowe i rezerwy banków central…, Brazylia: czego oczekuje rynek, Rynki wschodzące: RPA, Indie, Izrael i przeka…, Stres finansowy USA i nastroje na opcjach, Zmienność rynków, Stres i niepewność, Kalendarz: najbliższe 14 dni, Szacunek na bieżąco vs ostatni odczyt, Oszczędności i fundusze w Europie, Wybrane fundusze ETF w Europie: dokąd płyną p…, Premia terminowa, dolar, stres kredytowy i za…, Płynność USA, Skarb USA: wpływy, dług i wykupy dziennie, Insiderzy spółek USA: zakupy i sprzedaż na ry…, Krótka sprzedaż w Europie: pozycje netto w Wi…, Energia USA: rafinerie, import ropy i pogoda, Ropa świata: kraje i zapasy, Pogoda i klimat: El Niño, susza, rzeki, Surowce całą dobę: ropa, gaz, złoto, srebro i…, Złoto w handlu Wielkiej Brytanii, Chiny, Hongkong i Tajwan: obligacje, indeks i…, Azja i Brazylia: kto kupuje i sprzedaje, Nastroje konsumentów, oczekiwana inflacja i d…, Instytucje i niedostarczone akcje w USA, Waluty świata i koszt pieniądza, Ameryka Łacińska: ile więcej kosztuje dolar p…, Prosto od banków centralnych, rządów i giełd:…, Napływy ETF do krypto, Gdzie płynie kapitał? (przycisk „Widok”)

### CRYPTO
- ✅ przełączenie zakładki
- ✅ rysowanie wykresów (28, w 38 panelach)
- ✅ napisy-błędy (NaN, undefined…)
- ✅ czas pierwszego widoku (0,3 s)
- ✅ Przełączniki i zakresy (25): Okres (CRYPTO): 7D, 30D, 1R · Scena krypto (TOP 10, pełny ekran): Pełny ekran, TOP 10, TOP 100 · Sektory krypto (chipy): Giełdy, BTC, ETH, L1/L2, Stablecoiny, Memecoiny, AI, DeFi, RWA, DePIN, Gaming · Widok: Karty / Wykresy: Wykresy · Archiwum własne — krypto (Okno czasu): 30 dni, 365 dni · Kapitał w krypto: BTC → Giełdy −85 347 mln …, ETH → Giełdy −22 051 mln …, L1/L2 → Giełdy −4643 mln …, Stablecoiny → Giełdy −108…, Memecoiny → Giełdy −920 m…
- ✅ Rozwijane bloki (26): Czy bitcoin i ether płyną na giełdy (pomiar), Wieloryby: portfele giełd na Ethereum, Giełdy: salda i przepływy netto, Obrót na giełdach zdecentralizowanych, Kontrakty na łańcuchu, Na które sieci płyną stablecoiny, Emitenci stablecoinów, Rejestry MiCA: kto w Europie ma licencję na k…, Skarbce spółek: krypto w spółkach publicznych…, Tokenizowane aktywa: obligacje, fundusze i zł…, Złoto i surowce a krypto, DeFi: opłaty, stres stablecoinów i włamania, Hyperliquid: największe konta, Aave: pożyczki w DeFi, Kontrakty na Bitcoin i Ether (CME), Dźwignia i pozycje w krypto, Premie cenowe krypto: Korea i USA, Archiwum własne — krypto, Zamknięcia dzienne 10 kryptowalut, Sieć Bitcoin: opłaty, kolejka transakcji i mo…, Ethereum: staking, podaż i sieci warstwy 2, Bitcoin: wycena z łańcucha bloków, Rynki prognoz i uwaga detalu, Rynek krypto: kapitalizacja i udziały, Rynek krypto: kontrakty i DeFi, Widok (przycisk „Widok”)

### TRENDY
- ✅ przełączenie zakładki
- ✅ rysowanie wykresów (48, w 2 panelach)
- ✅ napisy-błędy (NaN, undefined…)
- ✅ czas pierwszego widoku (0,1 s)
- ✅ Przełączniki i zakresy (1): Trendy: Global / Krypto: Trendy krypto
- ✅ Rozwijane bloki (8): ● Bez wyraźnego kierunku, Jak czytać wskaźnik 1–10, Nauka: postęp do oceny sygnałów, Szczegóły: wszystkie sygnały, Bez sygnału dziś, Jak mocne były powody w historii tej strony, Jak czytać sygnały dzienne, Jak czytać TRENDY

### Cała strona
- ✅ błędy JavaScriptu na stronie (0)

### Brakujące, puste, stare i niepełne pliki danych (podmiana jednego pliku w kopii strony)
- ✅ plik „krypto”: plik pusty ({}): bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają; ℹ️ plik zasila większość strony — utrata wykresów jest oczekiwana, liczą się błędy powyżej
- ✅ plik „rynki”: plik nie istnieje (HTTP 404): bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają; ℹ️ plik zasila większość strony — utrata wykresów jest oczekiwana, liczą się błędy powyżej
- ✅ plik „trendy”: plik bez wierszy (wszystkie listy puste): bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają; ℹ️ plik zasila większość strony — utrata wykresów jest oczekiwana, liczą się błędy powyżej
- ✅ plik „swiat-dziennik”: plik niepełny (ucięty w połowie): bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają
- ✅ plik „krypto-dziennik”: plik niepełny (ucięty w połowie): bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają
- ✅ plik „ceny”: plik bez wierszy (wszystkie listy puste): bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają
- ✅ plik „meta”: plik z datami sprzed 14 dni: bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają; ✅ pasek o nieaktualnych danych serwera

## Błędy (wymagają uwagi)
- automat nie odświeżył danych od 6 godz. (ostatni przebieg 06.11.2026, 04:12)
- rynki (kursy EBC, rentowności): dane z 2026-11-06T02:32:02+00:00 — 7 h 23 min temu (próg 3 h 00 min, ponad 2× progu)

## Uwagi
- część automatu „dzwignia_cb” nie działa od 20.10.2026, 19:20 (16 dni 9 godz., nieudanych przebiegów z rzędu: 952) — automat nie naprawił tego sam; jeśli trwa dłużej niż 3 dni: uruchom naprawę (np. Claude) z plikiem kontrola/ostatnia.md albo poproś osobę techniczną (zadanie: „napraw część dzwignia_cb”)
- wieloryby (salda portfeli giełd): dane z 2026-11-06T03:12:02+00:00 — 6 h 43 min temu (próg 3 h 00 min, ponad 2× progu)
- dźwignia (giełdy pochodnych): dane z 2026-11-06T02:32:02+00:00 — 7 h 23 min temu (próg 3 h 00 min, ponad 2× progu)
- premie krypto (minuty giełd): dane z 2026-11-06T03:12 — 6 h 43 min temu (próg 3 h 00 min, ponad 2× progu)
- szanse decyzji Fed (rynek zakładów): dane z 2026-11-06T03:13:40+00:00 — 6 h 42 min temu (próg 1 h 30 min, ponad 2× progu)
- USDT skarbiec: odczyt sieci Ethereum sprzed 6 h 53 min (źródło nie odpowiada od ponad 6 godz.)
- USDT skarbiec: odczyt sieci Tron sprzed 7 h 47 min (źródło nie odpowiada od ponad 6 godz.)
- źródła bez odpowiedzi w ostatnim przebiegu: defi2_fees, dzwignia_cb, kalendarz2_dane_pl
- błąd zbieracza: Dźwignia: Coinbase: BTC: HTTP Error 502: Bad Gateway; ETH: HTTP Error 502: Bad Gateway
- błąd zbieracza: DeFi 2: fees: doba total24h nie pasuje do wykresu
- błąd zbieracza: Kalendarz 2 GUS: HTTP Error 404: Not Found
- etf.json sprzed 6 godz. 43 min (limit 3 godz.)
- trendy.json sprzed 6 godz. 43 min (limit 3 godz.)
- rynki.json sprzed 7 godz. 23 min (limit 3 godz.)
- dzwignia.json sprzed 6 godz. 43 min (limit 3 godz.)
- dzwignia.json: części bez odpowiedzi: cb
- wieloryby.json sprzed 6 godz. 43 min (limit 1 godz.)
- krypto.json sprzed 6 godz. 43 min (limit 3 godz.)
- krypto-top10.json sprzed 7 godz. 18 min (limit 3 godz.)
- cmc.json sprzed 6 godz. 43 min (limit 1 godz.)
- instytucje.json sprzed 7 godz. 23 min (limit 3 godz.)
- cm.json sprzed 7 godz. 23 min (limit 3 godz.)
- fred.json sprzed 7 godz. 23 min (limit 3 godz.)
- ceny.json sprzed 7 godz. 23 min (limit 3 godz.)
- ceny-krypto.json sprzed 7 godz. 23 min (limit 3 godz.)
- fed.json sprzed 6 godz. 43 min (limit 1 godz.)
- lancuch.json sprzed 6 godz. 43 min (limit 1 godz.)
- swiat-dzien.json sprzed 6 godz. 43 min (limit 3 godz.)
- swiat-dziennik.json sprzed 6 godz. 41 min (limit 3 godz.)
- surowce-dziennik.json sprzed 6 godz. 41 min (limit 3 godz.)
- premie.json sprzed 6 godz. 43 min (limit 1 godz.)
- dolar.json sprzed 7 godz. 19 min (limit 3 godz.)
- zloto-krypto.json sprzed 6 godz. 41 min (limit 1 godz.)
- dzis.json sprzed 6 godz. 43 min (limit 3 godz.)
- fundusze.json sprzed 6 godz. 43 min (limit 3 godz.)
- obce.json sprzed 7 godz. 23 min (limit 3 godz.)
- krypto-top10-logo.json sprzed 7 godz. 18 min (limit 3 godz.)
- fundusze-przeplywy.json sprzed 6 godz. 43 min (limit 3 godz.)
- ng-dziennik.json sprzed 6 godz. 41 min (limit 3 godz.)
- ng-ceny.json sprzed 6 godz. 43 min (limit 3 godz.)
- fw-dziennik.json sprzed 6 godz. 41 min (limit 3 godz.)
- polska-rynek.json sprzed 6 godz. 43 min (limit 3 godz.)
- polska-kapital.json sprzed 6 godz. 43 min (limit 3 godz.)
- polska-dlug.json sprzed 6 godz. 43 min (limit 3 godz.)
- polska-2.json sprzed 6 godz. 43 min (limit 3 godz.)
- gieldy.json sprzed 7 godz. 19 min (limit 3 godz.)
- dex.json sprzed 6 godz. 53 min (limit 3 godz.)
- krzywe.json sprzed 8 godz. 51 min (limit 8 godz.)
- stable-emitenci.json sprzed 6 godz. 43 min (limit 3 godz.)
- kalendarz2.json: części bez odpowiedzi: dane_pl
- usdt-skarbiec.json sprzed 6 godz. 53 min (limit 3 godz.)
- premie-stable.json sprzed 6 godz. 43 min (limit 3 godz.)
- dzwignia2.json sprzed 6 godz. 53 min (limit 4 godz.)
- indie.json sprzed 6 godz. 53 min (limit 4 godz.)
- chiny-tw.json sprzed 7 godz. 6 min (limit 6 godz.)
- defi2.json: części bez odpowiedzi: fees
- eth-lancuch.json sprzed 6 godz. 53 min (limit 4 godz.)
- ucits-przeplywy.json sprzed 6 godz. 43 min (limit 4 godz.)
- kanada-dlug.json sprzed 7 godz. 6 min (limit 6 godz.)
- kapitalizacje.json sprzed 6 godz. 53 min (limit 6 godz.)
- fed-ddp.json sprzed 7 godz. 6 min (limit 6 godz.)
- surowce-247.json sprzed 7 godz. 23 min (limit 3 godz.)
- hl-aave.json sprzed 8 godz. 1 min (limit 8 godz.)
- nastroje.json sprzed 6 godz. 53 min (limit 6 godz.)
- krypto-dzien.json sprzed 6 godz. 43 min (limit 3 godz.)
- krypto-dziennik.json sprzed 6 godz. 41 min (limit 3 godz.)
- spis plików sprzed 6 godz. 41 min (publikacja co 10 min)
- kursy dolara Ameryki Łacińskiej (co godzinę): dane z 2026-11-06T02:36:40+00:00 — 7 h 19 min temu (próg 3 h 00 min, ponad 2× progu — tylko uwaga)
- surowce: złoto teraz (notowanie co godzinę): dane z 2026-11-06T03:02:00+00:00 — 6 h 53 min temu (próg 3 h 00 min — najwyżej uwaga)
- szlaki: ruch statków w 8 cieśninach (dziennie, publ. we wtorek): dane z 2026-10-25 — 11 d 9 h temu (próg 10 d 0 h — najwyżej uwaga; spodziewana publikacja 03.11.2026, 13:10 — zaległa (przerwa u źródła?))
- porty: 20 dużych portów (dziennie, publ. raz w tygodniu): dane z 2026-10-23 — 13 d 9 h temu (porty w tyle za najnowszym dniem (2026-10-23): Singapur — brak w pliku, Szanghaj (Yangshan) — brak w pliku, Ningbo — brak w pliku, Hongkong — brak w pliku, Busan — brak w pliku, Port Klang — brak w pliku, Nhava Sheva — brak w pliku, Port Hedland — brak w pliku, Antwerpia — brak w pliku, Hamburg — brak w pliku, Algeciras — brak w pliku, Gdańsk — brak w pliku, Los Angeles i Long Beach — brak w pliku, Houston — brak w pliku, Santos — brak w pliku (próg 7 dni; w historii 2024–2026: 0) — najwyżej uwaga)
- Rosja: rezerwy walutowe (miesięcznie): dane z 2025-11 — 340 d 9 h temu (próg 180 d 0 h — najwyżej uwaga; spodziewana zmiana 06.11.2026, 20:20; źródło międzynarodowe publikuje rezerwy Rosji z dużym opóźnieniem (nowy miesiąc zależy od Rosji, nie od zbieracza) — ostatni miesiąc w tabeli międzynarodowej widać w kolumnie daty)
- Giełdy: salda i przepływy netto giełd scentralizowanych (szacunek z portfeli): dane z 2026-11-06T01:45:43+00:00 — 8 h 10 min temu (próg 4 h 00 min — najwyżej uwaga)
- Kontrakty na łańcuchu: otwarte pozycje: dane z 2026-11-06T02:20:18+00:00 — 7 h 35 min temu (próg 4 h 00 min — najwyżej uwaga)
- Dźwignia — krzywa terminowa Deribit (BTC, ETH): dane z 2026-11-06T02:35:52+00:00 — 7 h 20 min temu (odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min))
- Dźwignia — Coinbase USA (kontrakty BTC, ETH): dane z 2026-11-06T02:35:56+00:00 — 7 h 19 min temu (odczyt starszy niż 180 min)
- Dźwignia — Bitget (BTC, ETH): dane z 2026-11-06T02:35:57+00:00 — 7 h 19 min temu (odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min))
- Dźwignia — Gate (BTC, ETH, likwidacje): dane z 2026-11-06T02:32:02+00:00 — 7 h 23 min temu (odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min); likwidacje starsze niż 360 min)
- Dźwignia — KuCoin (BTC, ETH): dane z 2026-11-06T02:32:02+00:00 — 7 h 23 min temu (odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min))
- Dźwignia — MEXC (BTC, ETH): dane z 2026-11-06T02:35:59+00:00 — 7 h 19 min temu (odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min))
- Dźwignia — HTX (BTC, ETH): dane z 2026-11-06T02:36:04+00:00 — 7 h 19 min temu (odczyt starszy niż 180 min (zbieracz odświeża co ok. 55 min))
- metale: raport tygodniowy o zapasach miedzi (Londyn, USA, Chiny): dane z 2026-10-16 — 20 d 9 h temu (próg 14 d 0 h — najwyżej uwaga; spodziewana publikacja 30.10.2026, 19:00 — zaległa (święto albo przerwa u źródła?))
- Fundusze ETF (USA) — fundusze z ostatnią sesją (State Street, iShares): 46 z 94 (49%) — oczekiwana sesja: iShares 2026-11-04, State Street 2026-11-04 — mniej niż 95% funduszy z ostatnią sesją; bez danych 3+ sesji: EWP (ostatni dzień 2026-10-30, brak 4 sesji), EWS (ostatni dzień 2026-10-30, brak 4 sesji), EWW (ostatni dzień 2026-10-30, brak 4 sesji), EWG (ostatni dzień 2026-10-30, brak 4 sesji), EWA (ostatni dzień 2026-10-30, brak 4 sesji), EWH (ostatni dzień 2026-10-30, brak 4 sesji), EWI (ostatni dzień 2026-10-30, brak 4 sesji), EWD (ostatni dzień 2026-10-30, brak 4 sesji) i 40 więcej (tylko uwaga)
- TRENDY krypto — ostatni dzień z wynikiem sygnałów: ostatni wynik z 2026-10-30 — 6 d 9 h temu (próg 4 d 0 h — wyniki sygnałów przestały dochodzić (tylko uwaga))
- TRENDY świat — ostatnia sesja z wynikiem sygnałów: ostatni wynik z 2026-10-30 — 4 d 9 h temu (próg 2 d 0 h — wyniki sygnałów przestały dochodzić (tylko uwaga))
- TRENDY nowe grupy — ostatni dzień z wynikiem reguł w cieniu: ostatni wynik z 2026-11-02 — 3 d 9 h temu (próg 2 d 12 h (godziny robocze) — wyniki reguł w cieniu przestały dochodzić (tylko uwaga))
- TRENDY nowe grupy — zboża: ostatni dzień z wynikiem reguł w cieniu: ostatni wynik z 2026-10-30 — 4 d 9 h temu (próg 4 d 0 h (godziny robocze) — wyniki tej grupy przestały dochodzić, pozostałe grupy mogą być świeże (tylko uwaga))
- TRENDY najnowsze źródła — ostatni dzień z wynikiem reguł w cieniu: ostatni wynik z 2026-11-02 — 3 d 9 h temu (próg 2 d 12 h (godziny robocze) — wyniki reguł w cieniu przestały dochodzić (tylko uwaga))
- Stablecoiny — raport Circle (USDC, EURC): raport z 2026-11-06 03:12 UTC — 6 h 43 min temu (raport starszy niż 2 h — emitent nie odświeża pliku albo adres się zmienił; najwyżej uwaga)
- USDT skarbiec — odczyt sieci Ethereum: odczyt z 2026-11-06 03:01 UTC — 6 h 53 min temu (odczyt starszy niż 3 h — źródło nie odpowiada albo adres się zmienił; najwyżej uwaga)
- USDT skarbiec — odczyt sieci Tron: odczyt z 2026-11-06 02:08 UTC — 7 h 47 min temu (odczyt starszy niż 3 h — źródło nie odpowiada albo adres się zmienił; najwyżej uwaga)
- Dźwignia 2 — odczyt statystyk dziennych giełdy OKX: najstarszy odczyt z 2026-11-06 03:01 UTC — 6 h 53 min temu (najstarszy odczyt starszy niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga)
- Dźwignia 2 — odczyt stanów Bitfinex: najstarszy odczyt z 2026-11-06 03:01 UTC — 6 h 53 min temu (najstarszy odczyt starszy niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga)
- Ethereum — odczyt spalania i podaży: odczyt z 2026-11-06 03:01 UTC — 6 h 53 min temu (odczyt starszy niż 4 h — źródło nie odpowiada albo zmieniło odpowiedź; najwyżej uwaga)
- Fundusze ETF — odczyt zestawienia funduszy: odczyt z 2026-11-06 01:54 UTC — 8 h 01 min temu (odczyt starszy niż 6 h — źródło nie odpowiada albo zmieniło odpowiedź; najwyżej uwaga)
- DeFi 2 (defi2.json): opłaty: kategorie razem większe niż suma serwisu
- Indie — odczyt wyceny indeksów: ostatnie udane sprawdzenie starsze niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga
- Indie — odczyt pozycji w kontraktach: ostatnie udane sprawdzenie starsze niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga
- Indie — odczyt dostaw akcji: ostatnie udane sprawdzenie starsze niż 4 h — giełda nie odpowiada albo zmieniła odpowiedź; najwyżej uwaga
- Prąd w Europie: ceny w 15 strefach (dziś i jutro): dane z 2026-11-06 — 0 h 00 min temu (tylko 0 z 15 stref odświeżonych w ciągu 6 h (próg 10) — najwyżej uwaga (limit zapytań źródła: jedna strefa na przebieg))
- Prąd w Europie: miks produkcji Niemiec, Polski i Francji (co 2 h na kraj): dane z 2026-11-05T22:45:00+00:00 — 11 h 10 min temu (dane pobrane dawniej niż 8 h: DE, PL — najwyżej uwaga (limit zapytań źródła: jedno na przebieg))
- Prąd w Polsce: przepływy z sąsiadami (co godzinę): dane z 2026-11-05T22:15:00+00:00 — 11 h 40 min temu (dane pobrane dawniej niż 4 h — najwyżej uwaga (limit zapytań źródła: jedno na przebieg))
- Prąd w Wielkiej Brytanii: miks i emisyjność (co 30 min): dane z 2026-11-06T03:04:42+00:00 — 6 h 51 min temu (dane pobrane dawniej niż 3 h — najwyżej uwaga (limit zapytań źródła: jedno na przebieg))
- Prąd w Polsce 2026-11-06: RCE 281.9 €/MWh a strefa Polska 267.9 €/MWh — różnica 5.2% (próg 5%)
- Kalendarz 2: kalendarz danych Polski (pobranie): dane z 2026-10-30T06:06:17+00:00 — 7 d 3 h temu (pobranie starsze niż 24 h 00 min (odświeżanie co 6 h) — terminy mogą być nieaktualne; najwyżej uwaga)
- eksport zbóż USA: 1 nazw krajów bez kodu w sumach (OTHER PACIFIC ISLANDS, NEC) — dopisać do tabeli krajów
- surowce-247.json: odczyt złoto sprzed 7.3 h (próg 6 h)
- zgodność kapitalizacji: brak odczytu (HTTP Error 429: Too Many Requests)
- zgodność cen BTC/ETH: brak odczytu (HTTP Error 429: Too Many Requests)
- surowce: ropa WTI 2026-10 — średnia miesiąca z dwóch źródeł różni się o +4,47% (próg 4% z testu wstecznego) — sprawdzić
- Rosja: iloraz importu Rosji z UE do eksportu UE do Rosji 1,09 poza pasmem 1,20–6,00 (2026-07) — najwyżej uwaga
- tokenizowane aktywa: zmiana 7 dni produktów z listy — własna -6.05% vs źródło -4.38% (różnica 1.67 pkt proc., próg 1); źródło liczy od punktu godzinowego sprzed 168 h, my od dziennego zapisu z chwili pobrania — sprawdzić, czy różnica się utrzymuje
- ostatni przebieg automatu nieudany (06.11 04:15, 05.11 19:54 (zbuduj / Testy zbieracza), 05.11 19:44 (zbuduj / Testy zbieracza), 05.11 19:34 (zbuduj / Testy zbieracza), 05.11 19:24 (zbuduj / Testy zbieracza) i 45 wcześniejsze) — kolejny za ok. 10 min; dwa nieudane z rzędu = błąd; wcześniejsze porażki z 24 h już naprawione
- zbieracz zgłasza błędy w 15 kolejnych dniach kontroli (Dźwignia: Coinbase: BTC: HTTP Error 502: Bad Gateway; ETH: HTTP Error 502: Bad Gateway; DeFi 2: fees: doba total24h nie pasuje do wykresu) — strona i publikacja działają; jeśli trwa dłużej niż 3 dni: uruchom naprawę (np. Claude) z plikiem kontrola/ostatnia.md albo poproś osobę techniczną

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
