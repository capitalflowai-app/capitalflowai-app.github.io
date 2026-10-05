# Kontrola strony — 05.10.2026, 10:33 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 176 ms).
- Ostatni przebieg automatu: 05.10.2026, 10:28 — sprzed 4 min; źródeł: 76, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 34 (in_progress: 1, success: 32, cancelled: 1).
- Pliki danych (wiek): etf 0h59, trendy 0h04, oecd 1h18, rynki 0h59, dzwignia 0h04, wieloryby 0h04, energia 0h09, usa-makro 0h09, bilans-usa 13h21, krypto 0h09, krypto-top10 0h49, instytucje 0h09, tic 10h13, cm 0h59, fred 0h59, cftc 0h59, ceny 0h59, indeksy 0h09, ceny-krypto 0h59, snb 0h32, ici 6h11, fed 0h09, lancuch 0h09, wycena 5h25, insider wyłączone, nastroj 0h32, stres 0h09, aukcje 0h09, swiat-dzien 0h04, swiat-dziennik HTTP 503, premie 0h04, dolar 0h49, jpx 6h54, rwa 0h40, krypto-dzien 0h04, krypto-dziennik 0h03, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 59 min | 2026-10-05T07:33:54+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-10-05T08:28:38+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 59 min | 2026-10-05T07:33:54+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 06 min | 2026-10-05T08:27 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 32 h 33 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 8 h 33 min | 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 8 h 33 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 5 d 8 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 5 d 8 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 4 d 8 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 65 d 8 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 4 d 8 h | 2026-09 | — |
| BLS (miesięcznie) | ✅ | 34 d 8 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 08 min | 2026-10-05T08:24:35+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 8 h 33 min | 2026-10-04 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 8 h | 2026-09-28 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 49 min | 2026-10-05T07:43:50+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 11 d 8 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 4 d 8 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 9 d 8 h | 2026-09-25 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ✅ | 2 d 8 h | 2026-10-02 | — |
| tokenizowane aktywa RWA (co 3 h) | ✅ | 0 h 40 min | 2026-10-05T07:52:32+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 3 h) | ✅ | 0 h 40 min | 2026-10-05T07:52:32+00:00 | — |
| tokenizowane aktywa — dane emitentów (co 3 h) | ✅ | 0 h 40 min | 2026-10-05T07:52:32+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.96%, norma (mediana 9 dni) 4.30% — ✅ odchylenie od mediany 0.66 pkt proc. (progi 2 / 5).
- Cena BTC: 86,434 vs 86,425 USD — różnica 0.01% ✅.
- Cena ETH: 2,727 vs 2,726 USD — różnica 0.02% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 9 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-05 vs 2026-10-04: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.82% (2026-09-28), norma (mediana 54 dni) +0.81% — ✅ odchylenie najnowszego dnia od normy 0.01 pkt proc. (próg 1.5), norma +0.81% (próg ±3%).
- Premie krypto: USA BTC +0.01% (przez USDC +0.00%, różnica 0.01 pkt proc.); Korea BTC +0.12% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-02) · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-02).
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-09-23: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-09-30: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.834 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-09-25: giełda -93.0 vs MOF -362.0 mld JPY.
- Tokenizowane aktywa (RWA): ℹ️ zapisów sum 3 (od 2026-10-03) — porównanie zmiany 7 dni od 8. dnia; bez bieżącej wyceny 18% wartości (4.7 mld USD, liczba produktów 17: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 21.6 mld USD ℹ️; ℹ️ 2026-10-04: zmiana zbioru produktów z odczytu własnego albo danych emitentów (0.0 → 10.6 mld USD) — skok sumy liczony bez nich; ℹ️ 2026-10-05: zmiana zbioru produktów z odczytu własnego albo danych emitentów (10.6 → 16.9 mld USD) — skok sumy liczony bez nich; skoków sumy ponad 25% w tygodniu: brak ✅.
- Tokenizowane aktywa — odczyt własny z łańcucha: podaż 24 h: zmian ponad 50% brak ✅; wartość vs ostatnio znana: w paśmie 1/3–3× ✅; w sumach z odczytu własnego: 6 z 6 produktów, 10.7 mld USD.
- Tokenizowane aktywa — dane emitentów: w sumach wg emitentów: 10 z 11 produktów, 6.2 mld USD; inny zakres niż ostatnio znana (opisane na stronie): Centrifuge Protocol 966 mln USD vs ostatnio znana 1482 mln (0.65×); Securitize Tokenized AAA CLO Fund 282 mln USD vs ostatnio znana 104 mln (2.72×) ℹ️; bez bieżących danych emitenta (poza sumami): Mantle Index Four Fund: TimeoutError: The read operation timed out ℹ️; ostatni odczyt niepełny ⚠️.

## Uwagi
- swiat-dziennik.json: HTTP 503 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Binance USDT, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)
- tokenizowane aktywa (dane emitentów): ostatni odczyt niepełny — Mantle Index Four Fund: TimeoutError: The read operation timed out — bez wartości (poprzednie odczyty z ich stanem; tylko uwaga)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
