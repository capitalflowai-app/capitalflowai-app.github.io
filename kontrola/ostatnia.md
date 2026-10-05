# Kontrola strony — 05.10.2026, 10:44 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 1 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 393 ms).
- Ostatni przebieg automatu: 05.10.2026, 10:28 — sprzed 15 min; źródeł: 76, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 35 (pending: 1, cancelled: 1, in_progress: 1, success: 32).
- Pliki danych (wiek): etf 1h10, trendy 0h15, oecd 1h29, rynki 1h10, dzwignia 0h15, wieloryby 0h15, energia 0h20, usa-makro 0h20, bilans-usa 13h32, krypto 0h20, krypto-top10 1h00, instytucje 0h20, tic 10h24, cm 1h10, fred 1h10, cftc 1h10, ceny 1h10, indeksy 0h20, ceny-krypto 1h10, snb 0h43, ici 6h23, fed 0h20, lancuch 0h20, wycena 5h36, insider wyłączone, nastroj 0h43, stres 0h20, aukcje 0h20, swiat-dzien 0h15, swiat-dziennik 0h15, premie 0h15, dolar 1h00, jpx 7h05, rwa 0h51, krypto-dzien 0h15, krypto-dziennik 0h15, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 1 h 10 min | 2026-10-05T07:33:54+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 15 min | 2026-10-05T08:28:38+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 1 h 10 min | 2026-10-05T07:33:54+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 17 min | 2026-10-05T08:27 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 32 h 44 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 8 h 44 min | 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 8 h 44 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 5 d 8 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 5 d 8 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 4 d 8 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 65 d 8 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 4 d 8 h | 2026-09 | — |
| BLS (miesięcznie) | ✅ | 34 d 8 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 19 min | 2026-10-05T08:24:35+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 8 h 44 min | 2026-10-04 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 8 h | 2026-09-28 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 1 h 00 min | 2026-10-05T07:43:50+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 11 d 8 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 4 d 8 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 9 d 8 h | 2026-09-25 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ✅ | 2 d 8 h | 2026-10-02 | — |
| TRENDY świat — ostatnia sesja z wynikiem sygnałów | — | — | — | dziennik rusza 2026-10-05 — pierwsze wyniki po pierwszym sprawdzeniu |
| tokenizowane aktywa RWA (co 3 h) | ✅ | 0 h 51 min | 2026-10-05T07:52:32+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 3 h) | ✅ | 0 h 51 min | 2026-10-05T07:52:32+00:00 | — |
| tokenizowane aktywa — dane emitentów (co 3 h) | ✅ | 0 h 51 min | 2026-10-05T07:52:32+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.15%, norma (mediana 9 dni) 4.30% — ✅ odchylenie od mediany 0.85 pkt proc. (progi 2 / 5).
- Cena BTC: 86,269 vs 86,254 USD — różnica 0.02% ✅.
- Cena ETH: 2,722 vs 2,722 USD — różnica 0.01% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 9 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-05 vs 2026-10-04: odstęp migawek 27.0 h — porównanie z przepływami 24 h tylko przy ok. dobie ℹ️.
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
- tokenizowane aktywa (dane emitentów): ostatni odczyt niepełny — Mantle Index Four Fund: TimeoutError: The read operation timed out — bez wartości (poprzednie odczyty z ich stanem; tylko uwaga)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
