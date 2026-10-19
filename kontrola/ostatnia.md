# Kontrola strony — 19.10.2026, 11:24 (czas polski)

**Wynik: BŁĄD**

❌ Błędów: 2 — wymagają uwagi (szczegóły niżej).

**Co zrobić:**
- Część automatu nie działa od ponad doby (szczegóły niżej) — napisz do Claude tak, jak podpowiada wiersz błędu.
- Zbieracz od kilku dni zgłasza błędy — napisz do Claude: „napraw błędy zbieracza z kontroli”.

- Strona główna: działa (HTTP 200, 570 ms).
- Ostatni przebieg automatu: 19.10.2026, 11:20 — sprzed 3 min; źródeł: 256, bez odpowiedzi: interw_br, meksyk, obce_br, rwa-emitenci; błędów zbieracza: 3.
- Czas tego przebiegu automatu: 2 min 44 s; najdłużej: meksyk 90 s, wieloryby 20 s, trendy 11 s.
- Strona w przeglądarce (bez okna, ekran telefonu 390 px): zrzut po 7,0 s — grafik 502, wykresów liniowych 31; błędów JavaScriptu: 0 ✅.
- Strona jak u czytelnika (bez ?pelna=1 — pliki CRYPTO dopiero po otwarciu zakładki): zrzut po 6,0 s; błędów JavaScriptu: 0 ✅.
- Przebiegi Actions w 24 h: 120 (in_progress: 1, cancelled: 1, success: 118).
- Najdłuższy udany przebieg w 24 h: 28,1 min (od startu do końca, z czekaniem na maszyny); samo zadanie budowy najdłużej 18,1 min z limitu 25 min.
- Strażnik harmonogramów (raz w tygodniu): przepływy z harmonogramem czynne 5 z 5; ostatni przebieg strażnika dziś (success); ostatni commit w repozytorium dziś ✅.
- Ostrzeżenia GitHuba o przestarzałych akcjach (ostatni przebieg każdego z 5 przepływów): brak ✅.
- Pliki danych (wiek): etf 0h41, trendy 0h03, oecd 3h12, rynki 0h25, dzwignia 0h03, wieloryby 0h03, energia 5h25, surowce 0h16, surowce-hist 0h16, usa-makro 3h36, bilans-usa 11h12, krypto 0h41, krypto-top10 0h23, cmc 0h03, instytucje 0h41, tic 9h42, cm 0h25, fred 0h41, cftc 6h01, ceny 0h41, indeksy 0h52, ceny-krypto 0h52, snb 1h14, ici 0h25, fed 0h03, lancuch 0h03, wycena 0h02, insider 0h03, nastroj 3h36, stres 5h48, aukcje 2h12, swiat-dzien 0h03, swiat-dziennik 0h01, surowce-dziennik 0h00, premie 0h03, dolar 0h16, stopy 3h12, jpx 2h11, rwa 2h59, zloto-krypto 0h01, szlaki 0h03, polska 0h16, surowce-raporty 35h32, dzis 0h03, fundusze 0h03, obce 0h52, krypto-top10-logo 0h23, eer 3h12, meksyk 7h46, kursy 6h34, bis 9h42, rezerwy 9h42, cofer 9h34, bilans 6h22, safe 6h22, ue 4h34, kanada 19h40, korea 3h22, spw 2h23, pip 2h37, fundusze-przeplywy 0h03, zboza-dzien 1h05, metale 2h22, azja2 HTTP 404, ng-dziennik 0h00, ng-ceny 0h03, fw-dziennik 0h00, porty 43h11, lng 2h47, rosja 10h34, polska-rynek 0h03, polska-kapital 0h03, polska-dlug 0h03, polska-2 0h03, bis2 9h54, gieldy 0h16, dex 0h16, target 18h54, mica 18h54, etf-zapas 5h09, soma-sklad 1h05, eurosystem 1h05, hedge 4h45, krzywe 1h27, stable-emitenci 0h41, inflacja 10h49, koniunktura 3h46, prad 0h00, niepewnosc 1h27, kalendarz 0h03, kalendarz2 3h36, nowcasty 0h41, usdt-skarbiec 0h25, europa-fundusze 1h39, plynnosc-usa 0h52, skarb-usa 1h39, usda-eksport 0h41, premie-stable 0h03, energia-usa 0h41, dzwignia2 0h52, indie 0h41, chiny-tw 0h03, interwencje 0h41, defi2 7h16, eth-lancuch 0h41, ucits-przeplywy 0h03, kanada-dlug 0h03, fred2 1h05, kapitalizacje 0h03, krypto-firmy 21h20, fed-ddp 0h03, short-eu 1h50, ropa-swiat 14h03, iip 14h03, usa-pakiet 2h12, surowce-247 0h41, waluty 2h12, zloto-uk HTTP 404, hl-aave HTTP 404, nastroje HTTP 404, sec-13f HTTP 404, nastroje-gosp HTTP 404, em2 HTTP 404, klimat HTTP 404, zmiennosc 0h03, krypto-dzien 0h03, krypto-dziennik 0h01, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200, count.js HTTP 200, sw.js HTTP 200.
- Awarie części automatu — trwają: ilm od 19.10.2026, 10:42 (0 godz., nieudanych przebiegów: 1) ℹ️; interw_br od 18.10.2026, 11:17 (1 dzień 0 godz., nieudanych przebiegów: 120) ℹ️ (interwencje i rezerwy — część z błędem zostaje z ostatnimi danymi i datą (v401); wiek pobrania i rytm publikacji w wierszach świeżości); m3 od 19.10.2026, 10:42 (0 godz., nieudanych przebiegów: 1) ℹ️; meksyk od 19.10.2026, 09:44 (1 godz., nieudanych przebiegów: 9) ℹ️; obce_br od 18.10.2026, 09:23 (1 dzień 2 godz., nieudanych przebiegów: 129) ❌; rwa-emitenci od 18.10.2026, 17:03 (18 godz., nieudanych przebiegów: 91) ⚠️; tgb od 19.10.2026, 10:42 (0 godz., nieudanych przebiegów: 1) ℹ️.
- Naprawiły się same (24 h): chtw_csi 19.10.2026, 06:23 – 19.10.2026, 06:49 (0 godz., nieudanych przebiegów: 2) ℹ️; chtw_tw 18.10.2026, 20:31 – 19.10.2026, 00:48 (4 godz., nieudanych przebiegów: 19) ℹ️; chtw_tw 19.10.2026, 05:12 – 19.10.2026, 07:27 (2 godz., nieudanych przebiegów: 12) ℹ️; metale_sh 19.10.2026, 08:22 – 19.10.2026, 09:00 (0 godz., nieudanych przebiegów: 1) ℹ️; premie_fx 18.10.2026, 19:02 – 18.10.2026, 23:38 (4 godz., nieudanych przebiegów: 21) ℹ️; premie_up 18.10.2026, 19:02 – 18.10.2026, 23:38 (4 godz., nieudanych przebiegów: 21) ℹ️.
- Zużycie darmowych planów (licznik automatu — dolna granica): CoinGecko (Demo) — zapytań w tym miesiącu (od 06.10.2026, 09:16): 2 249, prognoza na miesiąc ok. 5 328 z limitu 10 000 (53%) ✅; CoinMarketCap (Basic) — zapytań w tym miesiącu (od 06.10.2026, 09:16): 1 851, prognoza na miesiąc ok. 4 385 z limitu 15 000 (29%); według dostawcy w miesiącu: 2 251 z 15 000 (15%, stan 19.10.2026, 08:01) ✅; Twelve Data (Basic) — kredytów wczoraj (doba UTC): 338 z limitu 800 (42%); w bieżącej dobie (od północy UTC): 136 ✅; FMP (darmowy) — zapytań wczoraj (doba UTC): 0 z limitu 250 (0%); w bieżącej dobie (od północy UTC): 1 ✅.
- Notatki automatu: BANXICO_TOKEN odrzucony przed wysłaniem: to nie jest token Banxico (64 litery i cyfry) — Meksyk z formularza · fundusze EWZ: błąd pliku źródła w wierszach 2026-10-05 — aktywa ponad 2× od sąsiednich dni; przepływ i zwrot tego dnia i następnego = brak (nie zero).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 25 min | 2026-10-19T08:58:34+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 05 min | 2026-10-19T09:19 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 33 h 24 min | 2026-10-15 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 9 h 24 min | 2026-10-16 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 9 h 24 min | 2026-10-16 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 9 h | 2026-10-15 | — |
| CFTC (raport tygodniowy) | ✅ | 5 d 9 h | 2026-10-13 | — |
| FRED tygodniowe (WALCL) | ✅ | 4 d 9 h | 2026-10-14 | — |
| TIC (miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| OECD (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| BLS (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 02 min | 2026-10-19T09:21:18+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 9 h 24 min | 2026-10-18 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 9 h | 2026-10-12 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 16 min | 2026-10-19T09:07:47+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 11 d 9 h | 2026-10-07 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 4 d 9 h | 2026-10-14 | — |
| surowce: ropa i gaz dziennie (strona dzienna T+1, API co tydzień) | ✅ | 33 h 24 min | 2026-10-15 | — |
| surowce: złoto dziennie (LBMA PM wyliczona) | ✅ | 33 h 24 min | 2026-10-15 | — |
| surowce: złoto teraz (notowanie co godzinę) | ✅ | 0 h 17 min | 2026-10-19T09:07:00+00:00 | — |
| surowce: zapasy w USA (tydzień do piątku, publ. w środę) | ✅ | 9 d 9 h | 2026-10-09 | — |
| surowce: ceny miesięczne (publ. ok. 2. dnia roboczego) | ✅ | 18 d 9 h | 2026-09 | — |
| surowce: pozycje funduszy (stan na wtorek, publ. w piątek) | ✅ | 5 d 9 h | 2026-10-13 | — |
| surowce: pozycje funduszy — USA, 30 rynków + fundusze indeksowe + indeks (stan na wtorek, publ. w piątek) | ✅ | 5 d 9 h | 2026-10-13 | — |
| surowce: pozycje funduszy — Londyn (stan na wtorek, publ. w piątek) | ✅ | 5 d 9 h | 2026-10-13 | — |
| surowce: pozycje producentów — ropa Murban, Abu Zabi (stan na wtorek, publ. w piątek) | ✅ | 5 d 9 h | 2026-10-13 | — |
| surowce: złoto w funduszach (tony; po sesji w USA) | ✅ | 33 h 24 min | 2026-10-15 | — |
| surowce: złoto banków centralnych (miesięcznie; każdy kraj ze swoim miesiącem) | ℹ️ | 18 d 9 h | 2026-09 | bez progu (MFW publikuje kraje w różnych dniach) |
| szlaki: ruch statków w 8 cieśninach (dziennie, publ. we wtorek) | ✅ | 7 d 9 h | 2026-10-11 | — |
| szlaki: wskaźnik presji w łańcuchach dostaw (miesięcznie, publ. ok. 4. dnia roboczego) | ✅ | 18 d 9 h | 2026-09 | — |
| szlaki: indeks cen surowców (tydzień do środy, publ. ok. tydzień później) | ✅ | 4 d 9 h | 2026-10-14 | — |
| porty: świat wg ładunku (dziennie, publ. raz w tygodniu) | ✅ | 9 d 9 h | 2026-10-09 | — |
| porty: 20 dużych portów (dziennie, publ. raz w tygodniu) | ✅ | 9 d 9 h | 2026-10-09 | — |
| gaz i LNG: Świnoujście, dobowa wysyłka z terminalu (doba gazowa) | ✅ | 9 h 24 min | 2026-10-18 | — |
| gaz i LNG: terminale UE razem, dobowa wysyłka (doba kompletna) | ✅ | 33 h 24 min | 2026-10-17 | — |
| gaz i LNG: import LNG do UE27 wg pochodzenia (miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| gaz i LNG: import LNG do Polski (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| gaz i LNG: zapasy gazu w magazynach UE27 (miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| gaz i LNG: zapasy gazu w magazynach Polski (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| zmienność: VIX (S&P 500, 30 dni; dni robocze USA) | ✅ | 33 h 24 min | 2026-10-15 | — |
| zmienność: VIX 3M (S&P 500, 3 miesiące; dni robocze USA) | ✅ | 33 h 24 min | 2026-10-15 | — |
| zmienność: Nasdaq 100 (dni robocze USA) | ✅ | 33 h 24 min | 2026-10-15 | — |
| zmienność: rynki wschodzące (dni robocze USA) | ✅ | 33 h 24 min | 2026-10-15 | — |
| zmienność: ropa (dni robocze USA) | ✅ | 33 h 24 min | 2026-10-15 | — |
| zmienność: złoto (dni robocze USA) | ✅ | 33 h 24 min | 2026-10-15 | — |
| put/call: wskaźniki dzienne giełdy opcji USA (sesje USA) | ✅ | 9 h 24 min | 2026-10-16 | — |
| indeks stresu finansowego USA (dni robocze, opóźnienie 2 dni) | ✅ | 2 d 9 h | 2026-10-14 | — |
| Rosja: handel UE z Rosją (miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| Rosja: należności banków świata (kwartalnie) | ✅ | 201 d 9 h | 2026-Q1 | — |
| Rosja: handel Rosji wg partnerów (miesięcznie) | ✅ | 110 d 9 h | 2026-06 | — |
| Rosja: rezerwy walutowe (miesięcznie) | ⚠️ | 322 d 9 h | 2025-11 | próg 180 d 0 h — najwyżej uwaga; spodziewana zmiana 19.10.2026, 16:31; źródło międzynarodowe publikuje rezerwy Rosji z dużym opóźnieniem (nowy miesiąc zależy od Rosji, nie od zbieracza) — ostatni miesiąc w tabeli międzynarodowej widać w kolumnie daty |
| Rosja: złoto banku centralnego w tonach (miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| Polska: indeksy giełdy w Warszawie (dziennie) | ✅ | 9 h 24 min | 2026-10-16 | — |
| Polska: krzywa rentowności obligacji skarbowych (dziennie) | ✅ | 9 h 24 min | 2026-10-16 | — |
| Polska: przepływy do funduszy inwestycyjnych (miesięcznie) | ✅ | 18 d 9 h | 2026-09-30 | — |
| Polska: członkowie giełdy w obrotach akcjami (miesięcznie) | ✅ | 18 d 9 h | 2026-09-30 | — |
| Polska: inwestycje bezpośrednie według kraju (kwartalnie) | ✅ | 110 d 9 h | 2026-06-30 | — |
| Polska: wypłaty z budżetu UE 2021–2027 (dziennie w dni robocze) | ✅ | 3 h 34 min | 2026-10-19 | — |
| Polska: kto trzyma dług skarbowy (struktura posiadaczy, miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| Polska: sprzedaż obligacji detalicznych (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| Polska 2: dług zagraniczny i pozycja inwestycyjna (kwartalnie) | ✅ | 110 d 9 h | 2026-Q2 | — |
| Polska 2: oficjalne rezerwy i złoto (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| Polska 2: indeks cen konsumpcyjnych od 1999 (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| Polska 2: depozyty i kredyty banków (miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| Polska 2: WIBID i WIBOR (dziennie) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Polska 2: WIRON i POLSTR (dziennie) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Polska 2: ceny mieszkań (kwartalnie) | ✅ | 110 d 9 h | 2026-Q2 | — |
| Giełdy: salda i przepływy netto giełd scentralizowanych (szacunek z portfeli) | ✅ | 1 h 10 min | 2026-10-19T08:13:30+00:00 | — |
| DEX: obrót ostatniej pełnej doby UTC | ✅ | 9 h 24 min | 2026-10-18 | — |
| Kontrakty na łańcuchu: otwarte pozycje | ✅ | 0 h 16 min | 2026-10-19T09:07:39+00:00 | — |
| surowce: podaż ropy OPEC+ (raport miesięczny — szacunek i prognoza) | ✅ | 12 d 9 h | 2026-10-06 | — |
| surowce: bilans zbóż świata i USA (raport miesięczny) | ✅ | 9 d 9 h | 2026-10-09 | — |
| surowce: uran — średnia branżowa z końca miesiąca | ✅ | 18 d 9 h | 2026-09-30 | — |
| zboża: indeks dzienny (dni robocze, dane z poprzedniego dnia roboczego) | ✅ | 33 h 24 min | 2026-10-15 | — |
| zboża: indeks frachtu (tygodniowo, środa, dane za wtorek) | ✅ | 5 d 9 h | 2026-10-13 | — |
| żywność: podindeksy cen FAO (miesięcznie, publ. ok. 1. piątku) | ✅ | 18 d 9 h | 2026-09 | — |
| zboża i rzepak w UE: ceny tygodniowe (czwartek, tydzień do niedzieli) | ✅ | 7 d 9 h | 2026-10-11 | — |
| nawozy w UE (miesięcznie, publ. ok. 10. dnia) | ✅ | 18 d 9 h | 2026-09 | — |
| Meksyk: obligacje rządu u nierezydentów (dziennie, opóźnienie ok. 1,5 tygodnia) | ✅ | 11 d 9 h | 2026-10-07 | — |
| Polska: nierezydenci w obligacjach skarbowych (miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| Korea Płd.: inwestorzy zagraniczni w akcjach i obligacjach (komunikat miesięczny) | ✅ | 48 d 9 h | 2026-08 | — |
| MFW PIP — Polska jako emitent (półrocze) | ✅ | 291 d 9 h | 2025-S2 | — |
| MFW PIP — 20 największych par (półrocze) | ✅ | 291 d 9 h | 2025-S2 | — |
| MFW PIP — kto trzyma polskie papiery: suma = świat | ✅ | — | 193.3 vs 193.3 mld USD (2025-S2) | — |
| MFW PIP — Polska jako inwestor: suma = świat | ✅ | — | 94.3 vs 94.3 mld USD (2025-S2) | — |
| Dźwignia — krzywa terminowa Deribit (BTC, ETH) | ✅ | 0 h 40 min | 2026-10-19T08:43:55+00:00 | — |
| Dźwignia — Coinbase USA (kontrakty BTC, ETH) | ✅ | 0 h 40 min | 2026-10-19T08:43:59+00:00 | — |
| Dźwignia — basis Deribit vs OKX (ten sam termin) | ✅ | — | BTC: 6 terminów, największa różnica 0.01 pp (tolerancja 1.07); ETH: 6 terminów, największa różnica 0.05 pp (tolerancja 1.07) | — |
| Dźwignia — Bitget (BTC, ETH) | ✅ | 0 h 40 min | 2026-10-19T08:44:02+00:00 | — |
| Dźwignia — Gate (BTC, ETH, likwidacje) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Dźwignia — KuCoin (BTC, ETH) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Dźwignia — MEXC (BTC, ETH) | ✅ | 0 h 40 min | 2026-10-19T08:44:03+00:00 | — |
| Dźwignia — HTX (BTC, ETH) | ✅ | 0 h 39 min | 2026-10-19T08:44:07+00:00 | — |
| Dźwignia — suma otwartych pozycji, wobec poprzedniego zestawu giełd (informacja) | ✅ | — | BTC: 11 giełd 18.38 mld USD (2026-10-19), poprzednio 5 giełd 5.91 mld USD (2026-10-12); ETH: 11 giełd 11.09 mld USD (2026-10-19), poprzednio 5 giełd 4.22 mld USD (2026-10-12) | — |
| metale: giełda w Londynie — ceny i zapasy (dziennie, publ. wieczorem UTC) | ✅ | 2 d 9 h | 2026-10-16 | — |
| metale: giełda w Szanghaju — ceny (dziennie, ok. 07:30 UTC) | ✅ | 0 h 00 min | 2026-10-19 | — |
| metale: giełda w Szanghaju — kwity magazynowe (dziennie) | ✅ | 2 d 9 h | 2026-10-16 | — |
| metale: giełda w Szanghaju — zapasy w magazynach (tygodniowo) | ✅ | 2 d 9 h | 2026-10-16 | — |
| metale: raport tygodniowy o zapasach miedzi (Londyn, USA, Chiny) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Fundusze ETF (USA) — fundusze z ostatnią sesją (State Street, iShares) | ✅ | — | 94 z 94 (100%) — oczekiwana sesja: iShares 2026-10-16, State Street 2026-10-15 | — |
| Fundusze ETF (USA) — NAV a zamknięcie na giełdzie (kontrola krzyżowa) | ✅ | — | 12 funduszy, największa różnica 0,63% (EWJ, 2026-10-16) | — |
| Polska: złoto w zł/g (dni robocze w Polsce) | ✅ | 0 h 00 min | 2026-10-19 | — |
| Polska: ceny hurtowe paliw (dni obowiązywania wt–sob) | ✅ | 9 h 24 min | 2026-10-17 | — |
| Polska: gaz i prąd z giełdy (dzień dostawy, 7 dni w tygodniu) | ✅ | 0 h 00 min | 2026-10-19 | — |
| Polska: ceny na stacjach na tle UE (poniedziałki, pobierane w nocy) | ✅ | 6 d 9 h | 2026-10-12 | — |
| Polska: pszenica (tydzień do niedzieli, publ. w czwartek) | ✅ | 7 d 9 h | 2026-10-11 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 9 d 9 h | 2026-10-09 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ✅ | 2 d 9 h | 2026-10-16 | — |
| TRENDY świat — ostatnia sesja z wynikiem sygnałów | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY surowce — ostatni dzień z wynikiem reguł w cieniu | ✅ | 2 d 9 h | 2026-10-16 | — |
| TRENDY surowce — ceny 7 funduszy surowcowych (sesja w USA; reguły w cieniu) | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY surowce — NAV i jednostki 3 funduszy surowcowych (reguły w cieniu) | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY nowe grupy — ostatni dzień z wynikiem reguł w cieniu | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY nowe grupy — fundusze: ostatni dzień z wynikiem reguł w cieniu | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY nowe grupy — rynek polski: ostatni dzień z wynikiem reguł w cieniu | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY nowe grupy — metale: ostatni dzień z wynikiem reguł w cieniu | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY nowe grupy — zboża: ostatni dzień z wynikiem reguł w cieniu | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY nowe grupy — ceny 14 funduszy wyników (sesja w USA; reguły w cieniu) | ✅ | 9 h 24 min | 2026-10-16 | — |
| TRENDY najnowsze źródła — ostatni dzień z wynikiem reguł w cieniu | — | — | — | dziennik rusza 2026-10-19 — pierwsze wyniki po pierwszym sprawdzeniu |
| tokenizowane aktywa RWA (co 3 h) | ✅ | 2 h 59 min | 2026-10-19T06:24:55+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 3 h) | ✅ | 2 h 59 min | 2026-10-19T06:24:55+00:00 | — |
| tokenizowane aktywa — dane emitentów (co 3 h) | ✅ | 2 h 59 min | 2026-10-19T06:24:55+00:00 | — |
| TARGET: salda krajów strefy euro (EBC, miesięcznie) | ✅ | 48 d 9 h | 2026-08 | — |
| Rejestry MiCA: wykaz firm z licencją CASP (plik zmieniany nieregularnie) | ✅ | 2 d 17 h | 2026-10-16 | — |
| Rejestry MiCA: wykaz emitentów tokenów powiązanych z walutą (EMT) | ✅ | 2 d 17 h | 2026-10-16 | — |
| Portfel papierów Fed: skład (tygodniowo, stan na środę) | ✅ | 4 d 9 h | 2026-10-14 | — |
| Bilans Eurosystemu: główne pozycje (tygodniowo, stan na piątek) | ✅ | 9 d 9 h | 2026-10-09 | — |
| Fundusze hedgingowe w USA: aktywa (kwartalnie) | ✅ | 110 d 9 h | 2026-06-30 | — |
| Stablecoiny — raport Tether (zobowiązania, sieci) | ⚠️ | 2 d 9 h | 2026-10-16 23:30 UTC | raport starszy niż 30 h — emitent nie odświeża pliku albo adres się zmienił; najwyżej uwaga |
| Stablecoiny — raport Circle (USDC, EURC) | ✅ | 0 h 39 min | 2026-10-19 08:45 UTC | — |
| USDT skarbiec — odczyt sieci Ethereum | ✅ | 0 h 25 min | 2026-10-19 08:58 UTC | — |
| USDT skarbiec — odczyt sieci Tron | ✅ | 0 h 52 min | 2026-10-19 08:31 UTC | — |
| Dźwignia 2 — odczyt statystyk dziennych giełdy OKX | ✅ | 0 h 52 min | 2026-10-19 08:31 UTC | — |
| Dźwignia 2 — odczyt stanów Bitfinex | ✅ | 0 h 52 min | 2026-10-19 08:31 UTC | — |
| Ethereum — odczyt kolejek stakingu | ✅ | 6 h 01 min | 2026-10-19 03:22 UTC | — |
| Ethereum — odczyt spalania i podaży | ✅ | 1 h 39 min | 2026-10-19 07:44 UTC | — |
| Sieci L2 — odczyt aktywności | ✅ | 2 h 48 min | 2026-10-19 06:36 UTC | — |
| Sieci L2 — odczyt drugiego źródła TVL | ✅ | 2 h 48 min | 2026-10-19 06:36 UTC | — |
| Fundusze ETF — odczyt kursów walut | ✅ | 1 h 27 min | 2026-10-19 07:57 UTC | — |
| Fundusze ETF — odczyt zestawienia funduszy | ✅ | 0 h 03 min | 2026-10-19 09:20 UTC | — |
| Fundusze ETF — pliki historii funduszy | ✅ | 25 h 39 min | najstarszy plik sprzed 25 h 39 min | — |
| DeFi 2 — opłaty i przychody protokołów (doba danych) | ✅ | 9 h 24 min | 2026-10-18 | — |
| DeFi 2 — ceny stablecoinów (doba danych) | ✅ | 0 h 00 min | 2026-10-19 | — |
| DeFi 2 — lista włamań (pobranie) | ✅ | 7 h 16 min | 2026-10-19 02:07 UTC | — |
| DeFi 2 — opcje na zdecentralizowanych giełdach (doba danych) | ✅ | 9 h 24 min | 2026-10-18 | — |
| Indie — odczyt wyceny indeksów | ✅ | 0 h 41 min | sesja 2026-10-16 · sprawdzone 2026-10-19 08:42 UTC | — |
| Indie — odczyt pozycji w kontraktach | ✅ | 0 h 41 min | sesja 2026-10-16 · sprawdzone 2026-10-19 08:42 UTC | — |
| Indie — odczyt dostaw akcji | ✅ | 0 h 41 min | sesja 2026-10-16 · sprawdzone 2026-10-19 08:42 UTC | — |
| Premia USDT — Turcja | ✅ | — | — | jeszcze bez pierwszego odczytu (plik od 2026-10-17) |
| Premia USDT — Brazylia | ✅ | — | — | jeszcze bez pierwszego odczytu (plik od 2026-10-17) |
| Premia USDT — RPA | ✅ | — | — | jeszcze bez pierwszego odczytu (plik od 2026-10-17) |
| Premia USDT — Indonezja | ✅ | — | — | jeszcze bez pierwszego odczytu (plik od 2026-10-17) |
| Premia USDT — Indie | ✅ | — | — | jeszcze bez pierwszego odczytu (plik od 2026-10-17) |
| Premia USDT — Meksyk | ✅ | — | — | jeszcze bez pierwszego odczytu (plik od 2026-10-17) |
| Krzywa rentowności USA (dni robocze) | ✅ | 9 h 24 min | 2026-10-16 | — |
| Krzywa rentowności Niemiec (dni robocze) | ✅ | 9 h 24 min | 2026-10-16 | — |
| Krzywa rentowności Japonii (dni robocze) | ✅ | 9 h 24 min | 2026-10-16 | — |
| Krzywa rentowności strefy euro (dni robocze) | ✅ | 33 h 24 min | 2026-10-15 | — |
| Krzywa rentowności Kanady (dni robocze) | ✅ | 33 h 24 min | 2026-10-15 | — |
| BIS: luka kredytowa (kwartalnie) | ✅ | 201 d 9 h | 2026-Q1 | — |
| BIS: obsługa długu (kwartalnie) | ✅ | 201 d 9 h | 2026-Q1 | — |
| BIS: ceny mieszkań (kwartalnie) | ✅ | 110 d 9 h | 2026-Q2 | — |
| BIS: należności banków wobec rynków wschodzących (kwartalnie) | ✅ | 201 d 9 h | 2026-Q1 | — |
| BIS: emisje obligacji międzynarodowych (kwartalnie) | ✅ | 110 d 9 h | 2026-Q2 | — |
| BIS: płynność globalna (kwartalnie) | ✅ | 201 d 9 h | 2026-Q1 | — |
| BIS: aktywa banków centralnych (miesięcznie) | ✅ | 79 d 9 h | 2026-07 | — |
| Inflacja r/r (miesięcznie, najnowszy miesiąc) | ✅ | 48 d 9 h | 2026-08 | — |
| Koniunktura: zaufanie konsumentów i firm (miesięcznie) | ✅ | 18 d 9 h | 2026-09 | — |
| Prąd w Polsce: cena w kwadransach, dziś i jutro (dziennie) | ✅ | 0 h 00 min | 2026-10-19 | — |
| Prąd i CO2: cena uprawnień do emisji (dziennie, także w weekend) | ✅ | 9 h 24 min | 2026-10-18 | — |
| Prąd w Europie: ceny w 15 strefach (dziś i jutro) | ✅ | 0 h 00 min | 2026-10-19 | — |
| Prąd w Europie: miks produkcji Niemiec, Polski i Francji (co 2 h na kraj) | ✅ | 4 h 39 min | 2026-10-19T04:45:00+00:00 | — |
| Prąd w Polsce: przepływy z sąsiadami (co godzinę) | ✅ | 4 h 24 min | 2026-10-19T05:00:00+00:00 | — |
| Prąd w Wielkiej Brytanii: miks i emisyjność (co 30 min) | ✅ | 0 h 00 min | 2026-10-19T09:23:24+00:00 | — |
| Stres i niepewność: stres systemowy CISS (strefa euro; dni robocze) | ✅ | 33 h 24 min | 2026-10-15 | — |
| Stres i niepewność: niepewność polityki USA (EPU) | ✅ | 9 h 24 min | 2026-10-18 | — |
| Stres i niepewność: ryzyko geopolityczne (GPR) | ✅ | 3 d 9 h | 2026-10-13 | — |
| Kalendarz: terminarz Rezerwy Federalnej (pobranie) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| Kalendarz: terminarz PKB i inflacji PCE USA (pobranie) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| Kalendarz: terminarz sprzedaży i budownictwa USA (pobranie) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| Kalendarz: terminarz statystyk strefy euro (pobranie) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| Kalendarz: terminarz posiedzeń EBC (pobranie) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| Kalendarz 2: terminy inflacji i zatrudnienia USA (pobranie) | ✅ | 3 h 36 min | 2026-10-19T05:47:56+00:00 | — |
| Kalendarz 2: kalendarz danych Polski (pobranie) | ✅ | 3 h 36 min | 2026-10-19T05:47:56+00:00 | — |
| Kalendarz 2: terminy decyzji banku Anglii (pobranie) | ✅ | 3 h 36 min | 2026-10-19T05:47:56+00:00 | — |
| Kalendarz 2: terminy posiedzeń banku Japonii (pobranie) | ✅ | 3 h 36 min | 2026-10-19T05:47:56+00:00 | — |
| Nowcasty: szacunek PKB USA (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Nowcasty: szacunek PKB USA (rytm aktualizacji) | ⚠️ | 10 d 9 h | 2026-10-08 | zapowiedziana aktualizacja 2026-10-15 nie nastąpiła (+3 dni zapasu); ostatni szacunek z 2026-10-08 |
| Nowcasty: szacunek inflacji CPI USA (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Nowcasty: szacunek inflacji CPI USA (rytm aktualizacji) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Europa fundusze: napływy do funduszy (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Europa fundusze: napływy do funduszy (rytm publikacji) | ✅ | 48 d 9 h | 2026-08 | — |
| Europa fundusze: oszczędności gospodarstw domowych (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Europa fundusze: oszczędności gospodarstw domowych (rytm publikacji) | ✅ | 110 d 9 h | 2026-Q2 | — |
| Płynność USA: stopy SOFR (pobranie) | ✅ | 0 h 52 min | 2026-10-19T08:31:31+00:00 | — |
| Płynność USA: SOFR (najnowszy dzień) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Płynność USA: operacje repo Fed (pobranie) | ✅ | 0 h 52 min | 2026-10-19T08:31:31+00:00 | — |
| Płynność USA: operacje repo (najnowszy dzień) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Płynność USA: wolumeny repo (pobranie) | ✅ | 0 h 52 min | 2026-10-19T08:31:31+00:00 | — |
| Płynność USA: wolumeny repo (najnowszy dzień) | ✅ | 4 d 9 h | 2026-10-14 | — |
| Skarb USA: wpływy dzienne — cła i podatki (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Skarb USA: wpływy dzienne (rytm publikacji) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Skarb USA: emisje i umorzenia długu (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Skarb USA: dług dzienny (rytm publikacji) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Skarb USA: wykupy papierów z rynku (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Skarb USA: wykupy (rytm operacji) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Eksport zbóż USA (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Eksport zbóż USA (rytm publikacji tygodniowej) | ⚠️ | 17 d 9 h | 2026-10-01 | ostatni tydzień sprawozdawczy zakończony 2026-10-01 sprzed 17 d 9 h (zbiór ładuje się raz w tygodniu, w czwartek; zwykle najwyżej 13,7 doby) — źródło spóźnione |
| Energia USA: raport ropy (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Energia USA: raport ropy (rytm publikacji) | ✅ | 9 d 9 h | 2026-10-09 | — |
| Energia USA: stopniodni (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Energia USA: stopniodni (rytm publikacji) | ✅ | 33 h 24 min | 2026-10-17 | — |
| Chiny: krzywa rentowności (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Chiny: krzywa rentowności (rytm sesji) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Chiny: Shibor (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Chiny: Shibor (rytm sesji) | ✅ | 0 h 00 min | 2026-10-19 | — |
| Tajwan: put/call i pozycje (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Tajwan: put/call i pozycje — put/call (rytm sesji) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Tajwan: put/call i pozycje — pozycje (rytm sesji) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Hongkong: krótka sprzedaż (rytm sesji) | ✅ | — | — | jeszcze bez pierwszego odczytu sesji |
| Chiny: indeks CSI 300 (pobranie) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| Chiny: indeks CSI 300 (rytm sesji) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Interwencje i rezerwy: Japonia (pobranie) | ✅ | 6 h 34 min | 2026-10-19T02:49:21+00:00 | — |
| Interwencje i rezerwy: Japonia (rytm publikacji) | ✅ | 20 d 9 h | 2026-09-28 | — |
| Interwencje i rezerwy: Hongkong (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Interwencje i rezerwy: Hongkong (rytm publikacji) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Interwencje i rezerwy: Argentyna (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Interwencje i rezerwy: Argentyna (rytm publikacji) | ✅ | 4 d 9 h | 2026-10-14 | — |
| Interwencje i rezerwy: Brazylia (pobranie) | ⚠️ | 31 h 19 min | 2026-10-18T02:04:55+00:00 | pobranie starsze niż 24 h 00 min (odświeżanie co 3 h) — dane mogą być nieaktualne; najwyżej uwaga |
| Interwencje i rezerwy: Brazylia (rytm publikacji) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Interwencje i rezerwy: Kanada (pobranie) | ✅ | 6 h 34 min | 2026-10-19T02:49:21+00:00 | — |
| Interwencje i rezerwy: Kanada (rytm publikacji) | ✅ | 19 d 9 h | 2026-09-29 | — |
| Interwencje i rezerwy: oczekiwania w Brazylii (pobranie) | ✅ | 6 h 34 min | 2026-10-19T02:49:21+00:00 | — |
| Interwencje i rezerwy: oczekiwania w Brazylii (rytm publikacji) | ⚠️ | 9 d 9 h | 2026-10-09 | ostatni odczyt 2026-10-09 sprzed 9 d 9 h (próg 8 dób z testu wstecznego rytmu publikacji) |
| Kanada: aukcje obligacji (pobranie) | ✅ | 0 h 03 min | 2026-10-19T09:20:42+00:00 | — |
| Kanada: aukcje obligacji (rytm danych) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Kanada: posiadacze długu rządu (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Kanada: posiadacze długu rządu (rytm danych) | ✅ | 4 d 9 h | 2026-10-14 | — |
| Kanada: stawka CORRA (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Kanada: stawka CORRA (rytm danych) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Kanada: bilans Banku Kanady (pobranie) | ✅ | 0 h 41 min | 2026-10-19T08:42:18+00:00 | — |
| Kanada: bilans Banku Kanady (rytm danych) | ✅ | 4 d 9 h | 2026-10-14 | — |
| Kanada: ropociągi (Keystone, Trans Mountain) (pobranie) | ✅ | 1 h 39 min | 2026-10-19T07:44:48+00:00 | — |
| Kanada: ropociągi (Keystone, Trans Mountain) (rytm danych) | ✅ | 110 d 9 h | 2026-06 | — |
| FRED 2: serie (pobranie) | ✅ | 1 h 05 min | 2026-10-19T08:18:40+00:00 | — |
| FRED 2: serie (rytm publikacji) | ✅ | 15 d 9 h | 2026-10-03 | — |
| Kapitalizacje: USA (pobranie) | ✅ | 21 h 20 min | 2026-10-18T12:03:43+00:00 | — |
| Kapitalizacje: USA (rytm danych) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Kapitalizacje: Europa (7 krajów) (pobranie) | ✅ | 21 h 20 min | 2026-10-18T12:03:43+00:00 | — |
| Kapitalizacje: Europa (7 krajów) (rytm danych) | ✅ | 110 d 9 h | 2026-06-30 | — |
| Kapitalizacje: Japonia (pobranie) | ✅ | 9 h 03 min | 2026-10-19T00:20:48+00:00 | — |
| Kapitalizacje: Japonia (rytm danych) | ✅ | 18 d 9 h | 2026-09-30 | — |
| Skarbce spółek — BTC w spółkach publicznych (pobranie) | ✅ | 21 h 20 min | 2026-10-18 12:03 UTC | — |
| Skarbce spółek — ETH w spółkach publicznych (pobranie) | ✅ | 21 h 20 min | 2026-10-18 12:03 UTC | — |
| Wnioski o fundusze krypto w kolejce urzędu (pobranie) | ✅ | 21 h 20 min | 2026-10-18 12:03 UTC | — |
| Fed: banki komercyjne w USA (tygodniowo) (pobranie) | ✅ | 8 h 51 min | 2026-10-19T00:32:05+00:00 | — |
| Fed: banki komercyjne w USA (tygodniowo) (rytm danych) | ✅ | 11 d 9 h | 2026-10-07 | — |
| Fed: papiery komercyjne (pobranie) | ✅ | 8 h 51 min | 2026-10-19T00:32:05+00:00 | — |
| Fed: papiery komercyjne (rytm danych) | ✅ | 4 d 9 h | 2026-10-14 | — |
| Fed: papiery komercyjne (rytm stawek) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Fed: ankieta dealerów (fundusze hedgingowe) (pobranie) | ✅ | 21 h 20 min | 2026-10-18T12:03:43+00:00 | — |
| Fed: ankieta dealerów (fundusze hedgingowe) (rytm danych) | ✅ | 24 d 9 h | 2026-09-24 | — |
| Fed: ankieta kredytowa banków (pobranie) | ✅ | 21 h 20 min | 2026-10-18T12:03:43+00:00 | — |
| Fed: ankieta kredytowa banków (rytm danych) | ✅ | 80 d 9 h | 2026-07-30 | — |
| Krótka sprzedaż — Wielka Brytania (pobranie) | ✅ | 1 h 50 min | 2026-10-19 07:34 UTC | — |
| Krótka sprzedaż — Wielka Brytania (data pozycji) | ✅ | 3 d 9 h | 2026-10-15 | — |
| Krótka sprzedaż — Szwecja (pobranie) | ✅ | 1 h 50 min | 2026-10-19 07:34 UTC | — |
| Krótka sprzedaż — Szwecja (data pozycji) | ✅ | 2 d 9 h | 2026-10-16 | — |
| Ropa świata — bilans krajów (sprawdzenie źródła) | ✅ | 14 h 03 min | 2026-10-18 19:20 UTC | — |
| Ropa świata — bilans krajów (ostatni miesiąc danych) | ✅ | 79 d 9 h | 2026-07 | — |
| Ropa świata — zapasy w Europie (sprawdzenie źródła) | ✅ | 14 h 03 min | 2026-10-18 19:20 UTC | — |
| Ropa świata — zapasy UE27 (ostatni miesiąc danych) | ✅ | 110 d 9 h | 2026-06 | — |
| USA zadłużenie gospodarstw (pobranie) | ✅ | 2 h 12 min | 2026-10-19 07:11 UTC | — |
| USA zadłużenie gospodarstw (data danych) | ✅ | 110 d 9 h | 2026-06-30 | — |
| USA stopy hipoteczne (pobranie) | ✅ | 2 h 12 min | 2026-10-19 07:11 UTC | — |
| USA stopy hipoteczne (data danych) | ✅ | 3 d 9 h | 2026-10-15 | — |
| USA niepewność handlowa (pobranie) | ✅ | 2 h 12 min | 2026-10-19 07:11 UTC | — |
| USA niepewność handlowa (data danych) | ✅ | 9 h 24 min | 2026-10-18 | — |
| USA przewozy (pobranie) | ✅ | 2 h 12 min | 2026-10-19 07:11 UTC | — |
| USA przewozy (data danych) | ✅ | 48 d 9 h | 2026-08 | — |
| Waluty świata — kursy wobec dolara (pobranie) | ✅ | 2 h 12 min | 2026-10-19 07:11 UTC | — |
| Waluty świata — kursy wobec dolara (dzień danych) | ✅ | 0 h 00 min | 2026-10-19 | — |
| Waluty świata — kurs centralny juana (pobranie) | ✅ | 2 h 12 min | 2026-10-19 07:11 UTC | — |
| Waluty świata — kurs centralny juana (dzień danych) | ✅ | 0 h 00 min | 2026-10-19 | — |
| Waluty świata — gilty i inflacja oczekiwana (pobranie) | ✅ | 2 h 12 min | 2026-10-19 07:11 UTC | — |
| Waluty świata — gilty i inflacja oczekiwana (dzień danych) | ✅ | 4 d 9 h | 2026-10-14 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś — — ? brak odczytu.
- TGA 2026-10-14: Fiscal Data 885 823 vs FRED 885 823 mln USD — różnica 0.00% — ✅ próg stały 1% (stan na środę = saldo zamknięcia tego dnia).
- Podaż stablecoinów, dwa źródła: 304.6 vs 282.3 mld USD — różnica dziś +7.92%, norma (mediana 13 dni) +9.56% — ✅ odchylenie od mediany 1.64 pkt proc. (progi 2).
- Rentowność 10L USA (Skarb USA vs H.15 — Fed, te same dni): porównane 9 dat (do 2026-10-15), różnice > 0.02 pkt proc.: 0 ✅.
- Stopy banków centralnych (strona vs źródło banku, ten sam dzień): Fed 3,875% = 3,875% (NY Fed) ✅; EBC 2,5% = 2,5% (EBC) ✅; Bank Anglii 3,75% = 3,75% (BoE) ✅; Bank Szwajcarii 0% = 0% (SNB) ✅; Bank Szwecji 1,75% = 1,75% (Riksbank) ✅; Bank Norwegii 4,5% = 4,5% (Norges Bank) ✅; NBP 3,75% = 3,75% (NBP) ✅; Bank Kanady 2,25% = 2,25% (BoC) ✅; Bank Brazylii: brak porównania (nie odczytano źródła — BCB: The read operation timed out) ℹ️.
- Kursy walut (strona: kurs EBC; H.10: Fed, Nowy Jork; te same dni): 2025-10-16 — 20 walut, mediana różnicy 0,13%, najwięcej CHF +0,35%; 2026-07-16 — 20 walut, mediana różnicy 0,11%, najwięcej SEK -0,22%; 2026-09-16 — 20 walut, mediana różnicy 0,02%, najwięcej SEK +0,10%; 2026-10-09 — 20 walut, mediana różnicy 0,05%, najwięcej MXN -1,08% ✅.
- Indeksy giełdowe: świeże 22 z 24 (do 2026-10-19); opóźnione: AEX (2026-10-15) ℹ️; bez danych (dostawca nie podaje): JTOPI ℹ️; zamknięcia poprawione przez dostawcę po pobraniu (7 dni): MXX 2026-10-15 +0,72%, MXX 2026-10-14 +0,20%, MXX 2026-10-13 -0,27%, GDAXI 2026-10-13 +0,04%, BSESN 2026-10-13 +0,10%, HSI 2026-10-13 +0,07%, KS11 2026-10-13 +0,29%, MXX 2026-10-12 +0,51% (+2); ostatnia sesja pobrana za wcześnie: BSESN, GDAXI, HSI, KS11, MXX, SSEC ℹ️; pora pobierania przesunięta (nauczone z poprawek i spóźnień dostawcy): AEX +3 h, BSESN +2 h, GDAXI +2 h, HSI +1 h, KS11 +2 h, MXX +1 h, SSEC +1 h, XU100 +1 h ℹ️.
- Indeksy vs wydawcy (FRED, 45 dni): S&P 500 — zgodne 30 z 30 sesji (wydawca do 2026-10-16) ✅ · Nasdaq Composite — zgodne 29 z 29 sesji (wydawca do 2026-10-15) ✅ · Dow Jones — zgodne 30 z 30 sesji (wydawca do 2026-10-16) ✅ · Nikkei 225 — zgodne 27 z 27 sesji (wydawca do 2026-10-16) ✅.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-19 vs 2026-10-18: 13 par giełda/aktywo (salda z migawek o północy UTC: 13), rozbieżności nietypowe (> 5% i > 3× zwykłej): 0 ✅.
- Listy portfeli giełd z raportów miesięcznych (wiek): OKX 41 dni, Bybit 26 dni, KuCoin 49 dni ⚠️.
- Nowe raporty dowodu rezerw giełd (listy portfeli; sprawdzone dziś): OKX — brak nowszego w dniach 2026-09-28–2026-10-19 ✅; Bybit — brak nowszego w dniach 2026-10-13–2026-10-19 ✅; KuCoin — audyt z 2026-09-30, raport z listą portfeli jeszcze niedostępny ℹ️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.88% (2026-10-12), norma (mediana 54 dni) +0.79% — ✅ odchylenie najnowszego dnia od normy 0.09 pkt proc. (próg 1.5), norma +0.78% (próg ±3%).
- Premie krypto: USA BTC +0.00% (przez USDC -0.02%, różnica 0.02 pkt proc.); Korea BTC +0.95% (kurs z 2026-10-16); kurs KRW/USD 2026-10-16: wprost 1332.098, w pliku rynki 1332.100 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 5 (2026-10-09 – 2026-10-15), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-16, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-16) · ETHA ✅ porównane sesje: 5 (2026-10-09 – 2026-10-15), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-16, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-16).
- ETF bitcoina — druga, niezależna kontrola przepływu ARKB (zmiana liczby BTC w pliku emitenta × cena z pliku vs przepływ na stronie; próg max 1 mln USD / 10%): ✅ porównane sesje: 4 (2026-10-14 – 2026-10-19), różnic ponad próg: 0; plik emitenta do 2026-10-19.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.01%, MEP ✅ 0.38%, CCL ✅ 0.45%; hurtowy vs bank centralny (2026-10-16) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-10-07: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-10-14: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.813 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-10-09: giełda +1431.8 vs MOF +3521.5 mld JPY.
- Surowce (porównania z pliku strony): złoto 2026-09 (archiwum funduszu vs MFW): -0,32% (próg 0,75%) ✅ · ropa Brent 2026-09 (EIA vs Bank Światowy): -2,26% (próg 4%) ✅ · ropa WTI 2026-09 (EIA vs Bank Światowy): +0,20% (próg 4%) ✅ · miedź 2026-09 (MFW vs Bank Światowy): -0,01% (próg 1%) ✅ · zapasy ropy i paliw: plik raportu vs API, 2026-10-09: porównane 5 serii, zgodne ✅ · gaz w magazynach: plik raportu vs API, 2026-10-09: porównane 1 serii, zgodne ✅ · ceny: strona dzienna vs API, 2026-10-14: porównane 5 serii, zgodne ✅ · gaz w magazynach USA, średnia 5 lat 2026-10-09: wyliczona 3 520 vs EIA 3 522 Bcf (-0,06%) ℹ️ · Brent dostawa fizyczna vs kontrakt, zmiany dzienne z 30 wspólnych dni: największa różnica 2026-10-02 (+18,0% vs -0,1%) ℹ️ · fundusze: GLD 2026-10-15 — wartość aktywów ÷ (uncje × cena złota) − 1 = -0,017% (próg 0,1%) ✅ · fundusze: GLDM 2026-10-15 — wartość aktywów ÷ (uncje × cena złota) − 1 = -0,004% (próg 0,1%) ✅ · banki: Chiny — MFW vs SAFE, 6 wspólnych mies. (do 2026-06): zgodne ℹ️ · banki: Polska — druga tabela MFW wobec głównej, 6 wspólnych mies. (do 2026-08): zgodne ✅ · banki: Rosja — druga tabela MFW wobec głównej, 6 wspólnych mies. (do 2025-11): zgodne ✅ · banki: odczyt Rosji 2026-08 (druga tabela MFW), 1 mies. za najnowszym odczytem na liście (próg 4) ✅ · banki: skok zapasu o ponad 50 t w miesiącu u kraju bez wcześniejszych ruchów (55 krajów) — brak ✅ · pozycje: rynków z bieżącego raportu — USA 30, Londyn 7, fundusze indeksowe 13, indeks 1, Abu Zabi 1 ℹ️.
- Szlaki handlowe i łańcuchy dostaw (z pliku strony): cieśniny: sumy i zakres ✅ · wskaźnik presji: zakres i skoki ✅ · indeks cen surowców: skoki tygodniowe ✅.
- Porty świata (z pliku strony): świat wg ładunku: zmiany i zakres ✅ · porty: zmiany i zakres ✅.
- Metale przemysłowe (z plików strony): miedź w Londynie 2026-10-16: raport tygodniowy vs zapas dzienny ✅ · miedź w Szanghaju (tydzień 2026-10-16): raport tygodniowy vs raport giełdy ✅ · Szanghaj 2026-10-16: kwity tygodniowe = dzienne ✅ · średnie miesięczne cen (6 metali) vs Bank Światowy ✅.
- Gaz i LNG (z pliku strony): terminale UE: zakres i skoki dobowe ✅ · Świnoujście: zakres ✅ · suma dób miesiąca: terminale UE razem wobec importu UE27 ✅ · suma dób miesiąca: Świnoujście wobec importu Polski ✅.
- Rosja (z pliku strony): import UE z Rosji (UE, EUR) ↔ eksport Rosji do UE (Rosja, USD) 2026-06: iloraz 1,02 ✅ · eksport UE do Rosji ↔ import Rosji z UE 2026-06: iloraz 2,69 (inna metoda — informacja) ℹ️ · cena uncji z wartości złota w rezerwach i tonażu 2025-11: 4 191 USD ✅ · kopia złota zgodna ze źródłem 2026-08 ✅.
- Polska na rynku: giełda, obligacje, fundusze (z pliku strony): WIG20 2026-10-16: giełda 4247,22 ↔ drugi dostawca 4247,22 (różnica 0,00%) ✅ · krzywa 2026-10-16: „10 lat” minus „2 lata” = 1,41 pp ✅ · krzywa 2026-10-16: „10 lat” minus 10 lat Niemiec (3,45%) = 2,81 pp ✅ · krzywa 2026-10-15 → 2026-10-16: średnia zmiana rentowności serii 0,02 pp ✅ · członkowie giełdy 2026-09: siedziba za granicą 63,0% · w Polsce 35,8% · nieustalona 1,2% (obroty razem 118811 mln zł) ✅.
- Polska: kapitał z zagranicy i wypłaty UE (z pliku strony): 2026-Q2 do Polski: kwartał 4 430 mln EUR ↔ suma 3 miesięcy z pliku miesięcznego 2 252 mln EUR (różnica -2 178) ✅ · 2026-Q2 z Polski: kwartał 482 mln EUR ↔ suma 3 miesięcy z pliku miesięcznego -13 mln EUR (różnica -496) ✅.
- Polska: dług skarbowy i obligacje detaliczne (z pliku strony): Zagranica: 25 wspólnych miesięcy z plikiem nierezydentów, największa różnica 0,05 mln zł (2025-05: struktura 157 223,7 ↔ nierezydenci 157 223,7) ✅.
- Polska 2: dług zagraniczny, depozyty, WIBOR, WIRON, ceny mieszkań (z pliku strony): bez sprzeczności ✅.
- Giełdy scentralizowane, DEX i kontrakty na łańcuchu (z plików strony): podejrzany skok listy portfeli (próg planu F6Z1): brak ✅ · przepływ 7 dni ponad 25% salda (saldo ≥ 10 mln USD): Poloniex, VALR, BigONE, Zoomex, Okcoin — poza sumą 7 dni ℹ️ · przepływ 30 dni ponad 50% salda (saldo ≥ 10 mln USD): Poloniex, Bitvavo, Biconomy.com, CoinEx, BitVenus, Gate US — poza sumą 30 dni ℹ️ · suma sald między dobami 2026-10-18 → 2026-10-19: +1,2% ✅ · znak przepływu 7 dni: giełdy z listy (wszystkie aktywa) plus; BTC + ETH z drugiego źródła (do 2026-10-18) plus (inne zbiory portfeli i aktywów — tylko informacja) ✅ · obrót DEX doby ÷ obrót spot giełd scentralizowanych (kroczące 24 h): 0,13 ✅.
- Salda TARGET krajów strefy euro (z pliku strony; porównanie z panelem „dane urzędowe”): spójność pliku (miesiące rosnące, suma sald = 0) ✅ · zgodność z panelem „dane urzędowe” (27 porównań kraj-miesiąc) ✅.
- Rejestry MiCA (z pliku strony): spójność pliku (sumy w krajach, usługi, szereg) ✅.
- BIS: kredyt, obsługa długu, wierzyciele i płynność (z pliku strony): porównanie zmiany r/r kredytu w trzech walutach: zgodne ✅.
- Indie, wycena indeksów, pozycje w kontraktach i dostawy akcji (z pliku strony): spójność pliku (wycena, pozycje, dostawy, historia) ✅.
- DeFi 2, opłaty, ceny stablecoinów, włamania i opcje (z pliku strony; porównanie podaży USDT z plikiem emitentów tylko informacyjnie): niespójności w pliku: opłaty: kategorie razem większe niż suma serwisu ⚠️ · spójność pliku (sumy, sortowanie, serie, lata) ⚠️ · podaż USDT zgodna z plikiem emitentów ✅.
- Dźwignia krypto 2, nastroje detalu i kredyt marżowy (z pliku strony; porównanie z dzwignia.json tylko informacyjnie): spójność pliku (doby, pasma, wolumeny, pozycje, historia) ✅ · stosunek kont long/short różni się od dzwignia.json (BTC: 1,47 i 1,45; ETH: 1,94 i 1,91) ℹ️.
- Fundusze ETF w Europie, dzienne przepływy netto pięciu grup (z pliku strony; wiek części, dzień danych, historia największych funduszy): spójność pliku (zestawienie, największe fundusze, historia, szereg przepływów) ✅ · dzień danych zestawienia 2026-10-16 jest 3 d przed dobą kontroli ✅ · odrzucone skoki liczby jednostek: 0 z 4128 par notowań (0,0%) ✅ · grupy z gotowym szeregiem przepływów: 5 z 5 ✅.
- Ethereum i warstwa 2, kolejki stakingu, podaż i sieci L2 (z pliku strony; porównanie TVL z drugim źródłem): spójność pliku (kolejki, spalanie, podaż, sieci L2) ✅ · dzień danych sieci L2 2026-10-18 ma 1 d wobec doby odczytu ✅ · TVL sieci L2 zgodny z drugim źródłem (stosunek 0,94) ✅ · największe sieci zgodne z drugim źródłem ✅.
- Skarbce spółek (BTC, ETH) i wnioski o fundusze krypto w kolejce urzędu (z pliku strony; cena BTC z posiadania spółek wobec pliku cen krypto tylko informacyjnie): spójność pliku (sumy, sortowanie, cena, historia, zrzuty, wnioski) ✅.
- Krótka sprzedaż w Europie: pozycje netto w Wielkiej Brytanii i w Szwecji (z pliku strony): spójność pliku (liczniki, ranking, rozkład, zmiana od zrzutu, historia, zrzuty) ✅.
- Ropa świata (bilans krajów i zapasy ropy i paliw w Europie; z pliku strony; wydobycie USA i zapasy Polski z drugim źródłem tylko informacyjnie): spójność pliku (miesiące, długości serii, zakresy, suma UE27 = suma 27 państw) ✅.
- Sektory krypto i Top 10 w scenie CRYPTO (z plików strony; kontrola tylko raportuje, niczego nie zmienia): każda moneta w jednym sektorze (znane sektory, bez powtórzeń) ✅ · identyfikatory i wiersze (bez stablecoinów, BTC i ETH w L1) ✅ · kolejność i zgodność kapitalizacji z rankingiem ogólnym ✅ · komplet monet w sektorach ✅ · świeżość składu sektorów ✅ · logo monet ✅ · poza rankingiem ogólnym mimo kapitalizacji powyżej jego dolnej granicy: FIGR_HELOC, 币安人生 ℹ️.
- USA: zadłużenie gospodarstw, stopy hipoteczne, niepewność handlowa i przewozy (z pliku strony): spójność pliku (zadłużenie, stopy hipoteczne, niepewność handlowa, przewozy) ✅.
- Waluty świata, kurs centralny juana, gilty i inflacja oczekiwana (z pliku strony): spójność pliku (waluty, kurs centralny juana, gilty i inflacja oczekiwana) ✅.
- USDT na żywo, skarbiec emitenta (z pliku strony; porównanie z raportem emitenta tylko informacyjnie): spójność pliku (saldo, podaż, 30 dób, zdarzenia, historia) ✅ · Ethereum: skarbiec w sieci 2,22 mld, w raporcie emitenta 2,13 mld (z 2026-10-16), różnica 88 mln — ruch po raporcie; podaż w sieci 88,30 mld a „wybite” w raporcie 88,30 mld (+0,000%, bez emisji i umorzeń po raporcie) ℹ️ · Tron: skarbiec w sieci 1,40 mld, w raporcie emitenta 1,28 mld (z 2026-10-16), różnica 118 mln — ruch po raporcie ℹ️.
- Premie USDT na lokalnych giełdach (z pliku strony; jeden odczyt na dzień roboczy po opublikowaniu kursu referencyjnego): spójność pliku (doby, premie, minuty, koszyk) ✅.
- Emitenci stablecoinów (z pliku strony; porównania z drugim źródłem tylko informacyjnie): spójność pliku (sieci, kapitał, sumy, zabezpieczenie) ✅ · suma emitentów a podaż z drugiego źródła: różnica dziś +8.45% (norma +8.50%, mediana 6 dni) — historia 6 z 7 dni — bez oceny ℹ️ · USDC: raport Circle a lista monet: różnica dziś -0.18% (norma -0.12%, mediana 6 dni) — historia 6 z 7 dni — bez oceny ℹ️ · USDT: zobowiązania w raporcie Tether a lista monet: różnica dziś +0.11% (norma +0.12%, mediana 6 dni) — historia 6 z 7 dni — bez oceny ℹ️.
- Płynność dolara i euro oraz fundusze hedgingowe (z plików strony; porównanie z panelem „dane urzędowe”): portfel Fed razem: zgodność z panelem „dane urzędowe” (12 wspólnych tygodni) ✅ · aktywa Eurosystemu razem: zgodność z panelem „dane urzędowe” (13 wspólnych tygodni) ✅ · spójność plików (dni rosnące, sumy grup, szczyt, brutto ≥ netto) ✅.
- Krzywe rentowności (z plików strony; porównanie 10L USA i Niemiec z rynki.json): rentowność 10L USA: zgodność z plikiem rynki (2 wspólne dni) ✅ · rentowność 10L Niemcy: zgodność z plikiem rynki (2 wspólne dni) ✅ · spójność pliku (dni, „miesiąc temu”, liczby, różnice nominalna − realna, wszyscy − AAA) ✅.
- Inflacja, koniunktura i stopy realne (z plików strony; inflacja USA a CPI-U z pliku usa-makro tylko informacyjnie): inflacja USA 2026-08: 3.40 % (plik inflacja) a 3.4 % (CPI-U z pliku usa-makro) — tylko informacja ✅ · stopa realna policzona dla 34 z 37 banków (reszta: brak inflacji albo starsza niż 3 mies. od stanu stopy) ✅ · spójność plików (miesiące, liczby, Polska w obu miarach zaufania) ✅.
- Prąd i CO2 (z pliku strony): Polska 2026-10-19: średnia 841.7 zł/MWh, minimum 547.0, maksimum 1549.4; kwadransów z ceną ujemną: 0 (dozwolone — tylko informacja) ℹ️ · Polska 2026-10-19: RCE 192.8 €/MWh (po kursie z ceny CO2) wobec strefy Polska 204.6 €/MWh — różnica 5.8% ⚠️ · Polska 2026-10-19: RCE 841.7 zł/MWh wobec indeksu giełdowego 835.3 zł/MWh (inny rynek) — różnica 0.8% ✅ · Miks DE 2026-10-19: odnawialne 52.9% z podziału wobec 53.8% z serii źródła — różnica 0.9 pkt proc. ✅ · Miks PL 2026-10-19: odnawialne 24.5% z podziału wobec 24.5% z serii źródła — różnica 0.0 pkt proc. ✅ · Miks FR 2026-10-19: odnawialne 11.7% z podziału wobec 12.1% z serii źródła — różnica 0.4 pkt proc. ✅ · Przepływy Polski 2026-10-19T05:00:00+00:00: saldo -373 MW (eksport; tylko informacja) ℹ️ · Wielka Brytania 2026-10-19T08:30Z: emisyjność 170 gCO2/kWh, skala „high” (tylko informacja) ℹ️.
- Stres i niepewność (CISS, EPU, GPR; z pliku strony; CISS USA a indeks stresu USA tylko informacyjnie): niespójności w pliku: CISS: daty głównych obszarów rozjeżdżają się o więcej niż 5 dni ⚠️ · CISS USA a indeks stresu USA (plik stres): korelacja poziomów 0.20 na 259 wspólnych dniach — tylko informacja ℹ️ · spójność pliku (zakresy, skoki dzienne, wykresy, percentyle, komplet obszarów) ⚠️.
- Kalendarz (z pliku strony): terminy w następnych 14 dniach: 12 (w tym wagi 3: 5) ✅ · decyzja FOMC: terminarz 2026-10-28 a rynek zakładów 2026-10-28 ✅.
- Kalendarz 2 (z pliku strony): terminy: FRED 2, GUS 4, BoE 1, BoJ 1 ✅.
- Nowcasty (z pliku strony): PKB: szacunek dla 2026-Q3 (3.6%) a ostatni odczyt 2026-Q2 (2.2%) ✅ · CPI: szacunek dla 2026-10 a ostatni odczyt 2026-09 (3.7% r/r) ✅ · CPI r/r: szacunek 3.77% a ostatni odczyt 3.7% (różnica 0.07 pp) ✅ · CPI: ostatni odczyt 2026-09 0.65% m/m (szacunek przed odczytem 0.53%) ✅.
- Europa: fundusze i oszczędności domowe (z pliku strony): gospodarstwa domowe: 7 krajów z kwartałem 2026-Q2 ✅ · fundusze: razem w strefie euro 2026-08 = 65052.5 mln EUR (wstępnie) ✅.
- Płynność USA (z pliku strony): SOFR: bank nowojorski 3.89% / lustro urzędu badań 3.89% (2026-10-15; zgodność w 10 z 10 dni) ✅ · SOFR: lista 3.89% i najnowszy odczyt stóp 3.89% (2026-10-15) ✅ · EFFR 3.88% a korytarz docelowy 3.75–4.0% (2026-10-15) ✅ · SOFR − EFFR: +0.01 pp (informacyjnie; duży rozstęp bywa prawdziwym napięciem rynku, nie błędem danych) ✅ · stałe repo: stopa minimalna 4.0% a górna granica korytarza 4.0% ✅ · odwrotne repo: stopa 3.75% a dolna granica korytarza 3.75% (2026-10-16) ✅.
- Skarb USA, wpływy i dług dzienne, wykupy (z pliku strony): dzień wpływów a saldo konta Skarbu ✅ · wykupy a umorzenia obligacji (15 operacji) ✅.
- Eksport zbóż i soi z USA wg kraju kupującego (z pliku strony): tożsamość wysyłek (22 tygodni) ✅.
- Energia USA, rafinerie, zapasy, import ropy i stopniodni (z pliku strony): zapas benz a surowce (us_gasoline) ✅ · zapas dest a surowce (us_dist) ✅ · zapas nafta a surowce (us_jet) ✅ · tydzień raportu a surowce ✅.
- Chiny, Tajwan, Hongkong: obligacje, Shibor, CSI 300, put/call, krótka sprzedaż (z pliku strony): CSI 300: zamknięcie a zmiana % w kolejnych sesjach ✅.
- Interwencje walutowe i rezerwy banków centralnych (z pliku strony): rezerwy Brazylii 2026-09: dziennie a MFW ✅ · rezerwy Brazylii 2026-08: dziennie a MFW ✅ · rezerwy Brazylii 2026-07: dziennie a MFW ✅.
- Kanada: aukcje obligacji, posiadacze długu, CORRA, bilans Banku Kanady, ropociągi (z pliku strony): Bank Kanady: papiery w posiadaczach długu a w bilansie (2026-10-14) ✅.
- FRED 2, premia terminowa, dolar, spready kredytowe, warunki finansowe i zasiłki (z pliku strony): oczekiwana inflacja 10 lat (nominalna − realna) a krzywa USA ✅.
- Kapitalizacje rynków akcji, USA / siedem krajów Europy / Japonia (z pliku strony): —.
- Fed: banki komercyjne USA, papiery komercyjne, ankieta dealerów, ankieta kredytowa banków (z pliku strony): banki komercyjne w USA (tygodniowo) 2026-10-07 ✅ · papiery komercyjne 2026-10-14 ✅ · papiery komercyjne stawki 2026-10-15 ✅ · ankieta dealerów (fundusze hedgingowe) 2026-09-24 ✅ · ankieta kredytowa banków 2026-07-30 ✅.
- Wierzyciele i dłużnicy świata, pozycja inwestycyjna ok. 100 gospodarek (z pliku strony): IIP: kwartał 2026-Q2, 99 krajów ✅.
- Surowce całą dobę, kontrakty na ropę, gaz, złoto, srebro i miedź (z pliku strony): Surowce 24/7: 6 z 6 kontraktów, najstarszy odczyt sprzed 0.7 h (złoto) ✅.
- Surowce — raporty miesięczne (podaż ropy, zboża, uran; z plików strony): ropa: wydanie 2026-10-06, szacunki do 2026-09, prognoza od 2026-10; OPEC+ = objęci porozumieniem + pozostali uczestnicy, cały OPEC ≥ objęci ✅ · zboża: raport 2026-10 (nr 676), sezon 2026/27; z poprzednim raportem: 8 z 8 wpisów ℹ️ · uran: brak wspólnego dnia (wycena funduszu od 2026-10-07, ostatni koniec miesiąca średniej branżowej 2026-09-30) — porównanie od pierwszego końca miesiąca z wyceną funduszu ℹ️.
- Zboża dziennie i koszt transportu (z plików strony): indeks dzienny: skoki dnia ✅ · indeks frachtu: skoki tygodnia ✅ · podindeksy żywności: skoki miesiąca ✅ · ceny w UE: skoki tygodnia ✅ · nawozy w UE: skoki miesiąca ✅ · indeks dzienny: tabela źródła vs seria ⚠️ · indeks dzienny vs podindeks zbóż w żywności (zmiany miesięczne) ✅ · indeks dzienny vs indeks zbóż świata (zmiany miesięczne) ✅ · azot w UE vs indeks nawozów świata (zmiany miesięczne) ✅ · pszenica w Polsce: ten sam portal w dwóch plikach ✅.
- Surowce — pozycje funduszy USA, plik tygodniowy vs drugi kanał urzędu (ten sam raport): raport 2026-10-13: 29 rynków × 14 liczb i 349 wcześniejszych wpisów rynków (open interest i netto funduszy zarządzających) — zgodne ✅.
- Polska (porównanie z plików strony): złoto w Polsce 2026-10-19 (zł/g) vs cena w USD z 2026-10-15 × kurs USD/PLN: +0,45% (próg 3%) ✅ · ceny na stacjach: tydzień 2026-10-12 — obniżony VAT na paliwa (akcyza i opłaty, jakie musiałyby być w cenie benzyny przy VAT 23%: 0,752 zł/l, mniej niż 0,85 × minimalna akcyza UE 1,574 zł/l); strona to opisuje ℹ️.
- Tokenizowane aktywa (RWA): zmiana 7 dni produktów z listy: własna -0.81% vs źródło -0.46% (różnica 0.35 pkt proc.) ✅; ℹ️ produkty spoza listy z wartością 0 (próg 20) — źródło nie podaje ich wartości od 2026-10-05 (14 dni, stan trwały); bez bieżącej wyceny 1,6% sumy — bez uwagi; bez bieżącej wyceny 2% wartości (0.4 mld USD, liczba produktów 13: 13 bez wartości od 2026-10-05), z bieżącą wyceną 26.2 mld USD ℹ️; skoków sumy ponad 25% w tygodniu: brak ✅.
- Tokenizowane aktywa — odczyt własny z łańcucha: podaż 24 h: zmian ponad 50% brak ✅; wartość vs ostatnio znana: w paśmie 1/3–3× ✅; w sumach z odczytu własnego: 7 z 7 produktów, 10.7 mld USD.
- Tokenizowane aktywa — dane emitentów: w sumach wg emitentów: 14 z 14 produktów, 11.5 mld USD; inny zakres niż ostatnio znana (opisane na stronie): Centrifuge Protocol 961 mln USD vs ostatnio znana 1482 mln (0.65×); Ondo Global Markets 1318 mln USD vs ostatnio znana 966 mln (1.36×); Securitize Tokenized AAA CLO Fund 283 mln USD vs ostatnio znana 104 mln (2.73×); xStocks 935 mln USD vs ostatnio znana 438 mln (2.13×) ℹ️; xStocks: reszta listy emitenta poza odczytem (459 tokenów) najwyżej 527.3 tys. USD (0.056% wartości) ℹ️; xStocks: pominięte tokeny bez dowodu rezerw u emitenta — 40 tokenów (np. WBDx, MSAx, PBx), w obiegu łącznie 6436.62 — najwyżej 454.3 tys. USD (0.049% wartości), odczyt 2026-10-18 11:52 UTC ℹ️; ostatni odczyt niepełny ⚠️.

## Kontrola zakładek GLOBAL, CRYPTO i TRENDY (przeglądarka bez okna, ekran telefonu 390 px)

- Zakres: przełączanie zakładek, przełączniki i zakresy, rozwijanie bloków, wykresy, błędy JavaScriptu, napisy-błędy, czas pierwszego widoku; potem to samo przy 7 podmienionych plikach danych (kopia strony, żywa strona bez zmian). Kroków: 110; czas: 94,8 s.

### GLOBAL
- ✅ przełączenie zakładki
- ✅ rysowanie wykresów (132, w 53 panelach)
- ✅ napisy-błędy (NaN, undefined…)
- ✅ czas pierwszego widoku (1,1 s)
- ✅ powrót do zakładki GLOBAL (wykresów 1 z 1)
- ✅ Przełączniki i zakresy (9): Okres (GLOBAL): DZIŚ, 1T, 1KW, 1R · Kalendarz makro (Okres kalendarza): Dzień, Miesiąc · Widok: Karty / Wykresy: Wykresy · Archiwum własne — świat (Okno czasu): 30 dni, 365 dni
- ✅ Rozwijane bloki (45): Gdzie warunki sprzyjają wzrostom, a gdzie spa…, Fed: czego spodziewa się rynek zakładów, Krzywe rentowności obligacji rządowych, Jakość danych mapy, Strach i chciwość GLOBALi, Przepływy kapitału USA ↔ świat, Przepływy bankowe między regionami (pomiar kw…, Dokąd płynie kapitał portfelowy, Kto trzyma czyje papiery, Pozycje w kontraktach na euro i inne rynki, Surowce — paliwo gospodarki, USA: energia, gospodarka i przepływ kapitału, Kto kupuje amerykańskie zboże i soję, USA: kredyty hipoteczne, długi gospodarstw, n…, USA: dokąd płyną pieniądze inwestorów — fundu…, Indeksy giełdowe świata, Archiwum własne — świat, Aukcje papierów skarbowych USA: popyt (stosun…, Kanada: kto kupuje i trzyma dług, stopa na je…, Banki USA: kredyty, papiery komercyjne i waru…, Wielkość rynków akcji: USA, Europa, Japonia —…, Szwajcaria: depozyty banków w banku centralny…, Interwencje walutowe i rezerwy banków central…, Brazylia: czego oczekuje rynek, Stres finansowy USA i nastroje na opcjach, Zmienność rynków, Stres i niepewność, Kalendarz: najbliższe 14 dni, Szacunek na bieżąco vs ostatni odczyt, Oszczędności i fundusze w Europie, Wybrane fundusze ETF w Europie: dokąd płyną p…, Premia terminowa, dolar, stres kredytowy i za…, Płynność USA, Skarb USA: wpływy, dług i wykupy dziennie, Insiderzy spółek USA: zakupy i sprzedaż na ry…, Krótka sprzedaż w Europie: pozycje netto w Wi…, Energia USA: rafinerie, import ropy i pogoda, Ropa świata: kraje i zapasy, Surowce całą dobę: ropa, gaz, złoto, srebro i…, Chiny, Hongkong i Tajwan: obligacje, indeks i…, Waluty świata i koszt pieniądza, Ameryka Łacińska: ile więcej kosztuje dolar p…, Prosto od banków centralnych, rządów i giełd:…, Napływy ETF do krypto, Gdzie płynie kapitał? (przycisk „Widok”)

### CRYPTO
- ✅ przełączenie zakładki
- ✅ rysowanie wykresów (23, w 35 panelach)
- ✅ napisy-błędy (NaN, undefined…)
- ✅ czas pierwszego widoku (0,3 s)
- ✅ Przełączniki i zakresy (25): Okres (CRYPTO): 7D, 30D, 1R · Scena krypto (TOP 10, pełny ekran): Pełny ekran, TOP 10, TOP 100 · Sektory krypto (chipy): Giełdy, BTC, ETH, L1/L2, AI, DeFi, Memecoiny, Stablecoiny • 0,0%, Gaming, DePIN, RWA · Widok: Karty / Wykresy: Wykresy · Archiwum własne — krypto (Okno czasu): 30 dni, 365 dni · Kapitał w krypto: Giełdy → BTC +14 821 mln …, Giełdy → ETH +2096 mln US…, Giełdy → L1/L2 +1152 mln …, Giełdy → AI +262 mln USD ›, Giełdy → DeFi +216 mln US…
- ✅ Rozwijane bloki (22): Czy bitcoin i ether płyną na giełdy (pomiar), Wieloryby: portfele giełd na Ethereum, Giełdy: salda i przepływy netto, Obrót na giełdach zdecentralizowanych, Kontrakty na łańcuchu, Na które sieci płyną stablecoiny, Emitenci stablecoinów, Rejestry MiCA: kto w Europie ma licencję na k…, Skarbce spółek: krypto w spółkach publicznych…, Tokenizowane aktywa: obligacje, fundusze i zł…, Złoto i surowce a krypto, DeFi: opłaty, stres stablecoinów i włamania, Kontrakty na Bitcoin i Ether (CME), Dźwignia i pozycje w krypto, Premie cenowe krypto: Korea i USA, Archiwum własne — krypto, Zamknięcia dzienne 10 kryptowalut, Sieć Bitcoin: opłaty, kolejka transakcji i mo…, Ethereum: staking, podaż i sieci warstwy 2, Bitcoin: wycena z łańcucha bloków, Rynek krypto: kapitalizacja i udziały, Rynek krypto: kontrakty i DeFi

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
- część automatu „obce_br” nie działa od 18.10.2026, 09:23 (1 dzień 1 godz., nieudanych przebiegów z rzędu: 129) — automat nie naprawił tego sam; co zrobić: napisz do Claude „napraw część obce_br”
- zbieracz zgłasza błędy w 3 kolejnych dniach kontroli (Banxico: The read operation timed out; Tokenizowane aktywa — dane emitentów: xStocks: TimeoutError: krok lista: The read operation timed out [lista 25.1 s z błędem; lista 25.0 s z błędem])

## Uwagi
- źródła bez odpowiedzi w ostatnim przebiegu: interw_br, meksyk, obce_br, rwa-emitenci
- błąd zbieracza: Banxico: The read operation timed out
- błąd zbieracza: Tokenizowane aktywa — dane emitentów: xStocks: TimeoutError: krok lista: The read operation timed out [lista 25.1 s z błędem; lista 25.0 s z błędem]
- błąd zbieracza: Interwencje i rezerwy Brazylia: HTTP Error 500: Internal Server Error
- część automatu „rwa-emitenci” nie działa od 18.10.2026, 17:03 (18 godz., nieudanych przebiegów z rzędu: 91) — automat ponawia sam; dane tej części mają swój wiek na stronie
- obce.json: części bez odpowiedzi: br
- azja2.json: HTTP 404 (brak pliku)
- interwencje.json: części bez odpowiedzi: br
- zloto-uk.json: HTTP 404 (brak pliku)
- hl-aave.json: HTTP 404 (brak pliku)
- nastroje.json: HTTP 404 (brak pliku)
- sec-13f.json: HTTP 404 (brak pliku)
- nastroje-gosp.json: HTTP 404 (brak pliku)
- em2.json: HTTP 404 (brak pliku)
- klimat.json: HTTP 404 (brak pliku)
- spis plików (data/manifest.json): HTTP 404 — strona działa na własnych zegarach modułów
- Rosja: rezerwy walutowe (miesięcznie): dane z 2025-11 — 322 d 9 h temu (próg 180 d 0 h — najwyżej uwaga; spodziewana zmiana 19.10.2026, 16:31; źródło międzynarodowe publikuje rezerwy Rosji z dużym opóźnieniem (nowy miesiąc zależy od Rosji, nie od zbieracza) — ostatni miesiąc w tabeli międzynarodowej widać w kolumnie daty)
- Stablecoiny — raport Tether (zobowiązania, sieci): raport z 2026-10-16 23:30 UTC — 2 d 9 h temu (raport starszy niż 30 h — emitent nie odświeża pliku albo adres się zmienił; najwyżej uwaga)
- DeFi 2 (defi2.json): opłaty: kategorie razem większe niż suma serwisu
- Prąd w Polsce 2026-10-19: RCE 192.8 €/MWh a strefa Polska 204.6 €/MWh — różnica 5.8% (próg 5%)
- stres i niepewność (v368): CISS: daty głównych obszarów rozjeżdżają się o więcej niż 5 dni
- Nowcasty: szacunek PKB USA (rytm aktualizacji): dane z 2026-10-08 — 10 d 9 h temu (zapowiedziana aktualizacja 2026-10-15 nie nastąpiła (+3 dni zapasu); ostatni szacunek z 2026-10-08)
- Eksport zbóż USA (rytm publikacji tygodniowej): dane z 2026-10-01 — 17 d 9 h temu (ostatni tydzień sprawozdawczy zakończony 2026-10-01 sprzed 17 d 9 h (zbiór ładuje się raz w tygodniu, w czwartek; zwykle najwyżej 13,7 doby) — źródło spóźnione)
- Interwencje i rezerwy: Brazylia (pobranie): dane z 2026-10-18T02:04:55+00:00 — 31 h 19 min temu (pobranie starsze niż 24 h 00 min (odświeżanie co 3 h) — dane mogą być nieaktualne; najwyżej uwaga)
- Interwencje i rezerwy: oczekiwania w Brazylii (rytm publikacji): dane z 2026-10-09 — 9 d 9 h temu (ostatni odczyt 2026-10-09 sprzed 9 d 9 h (próg 8 dób z testu wstecznego rytmu publikacji))
- zgodność kapitalizacji: brak odczytu (HTTP Error 429: Too Many Requests)
- zgodność cen BTC/ETH: brak odczytu (HTTP Error 429: Too Many Requests)
- lista portfeli giełdy KuCoin z 2026-08-31 ma 49 dni — portfele dodane przez giełdę od tego czasu nie są liczone; co zrobić: napisz do Claude „odśwież listę portfeli KuCoin z nowego raportu dowodu rezerw”
- surowce: Brent 2026-10-05 – 2026-10-12 — cena zostaje na poziomie po nietypowym ruchu (6 ses.), kontrakt tego nie potwierdza — ciąg już się skończył (od 2026-10-13 cena bez oznaczenia)
- zboża dziennie: tabela źródła vs seria — indeks ogółem d1: tabela -2, seria -1,19 (tolerancja zaokrągleń: ostatnia ±0,6, zmiana dnia ±0,6, roczna ±1,6 pkt, przedział ±1) — sprawdzić
- tokenizowane aktywa (dane emitentów): ostatni odczyt niepełny — xStocks: TimeoutError: krok lista: The read operation timed out [lista 25.1 s z błędem; lista 25.0 s z błędem] — poprzedni odczyt (stan 2026-10-18T11:37:35+00:0 (poprzednie odczyty z ich stanem; tylko uwaga)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
