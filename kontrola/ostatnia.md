# Kontrola strony — 03.10.2026, 22:18 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 5 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 113 ms).
- Ostatni przebieg automatu: 03.10.2026, 21:49 — sprzed 29 min; źródeł: 72, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 67 (pending: 1, in_progress: 1, success: 65).
- Pliki danych (wiek): etf 1h09, trendy 0h29, oecd 1h42, rynki 1h09, dzwignia 0h29, wieloryby 0h29, energia 6h18, usa-makro 6h18, bilans-usa 1h09, krypto 1h09, krypto-top10 0h59, instytucje 1h09, tic 22h15, cm 1h09, fred 1h09, cftc 1h42, ceny 1h09, indeksy 1h09, ceny-krypto 1h09, snb 11h27, ici 6h18, fed 0h29, lancuch 0h29, wycena 5h38, insider HTTP 404, nastroj 0h49, stres 6h18, aukcje 6h18, swiat-dzien 0h29, swiat-dziennik 0h28, premie 0h29, dolar 0h59, jpx 2h00, rwa HTTP 404, krypto-dzien 0h29, krypto-dziennik 0h28, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 1 h 09 min | 2026-10-03T19:09:30+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 29 min | 2026-10-03T19:49:31+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 1 h 09 min | 2026-10-03T19:09:30+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 30 min | 2026-10-03T19:48 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 20 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 20 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 20 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 63 d 20 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 32 d 20 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 32 d 20 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 28 min | 2026-10-03T19:50:18+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 20 h 18 min | 2026-10-02 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ? | — | — | brak dnia danych SOPR w pliku |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 59 min | 2026-10-03T19:19:20+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 9 d 20 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 2 d 20 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 7 d 20 h | 2026-09-25 | — |
| tokenizowane aktywa RWA (co 6 h) | ⚠️ | — | — | brak pliku data/rwa.json — panel na stronie ukryty (tylko uwaga) |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.19%, norma (mediana 7 dni) 4.35% — ✅ odchylenie od mediany 0.16 pkt proc. (progi 2 / 5).
- Cena BTC: 84,878 vs 84,881 USD — różnica 0.00% ✅.
- Cena ETH: 2,687 vs 2,688 USD — różnica 0.04% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 7 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-03 vs 2026-10-02: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia —, norma (mediana 0 dni) — — ℹ️ wspólnych dni 0 z 20 — bez oceny.
- Premie krypto: USA BTC +0.00% (przez USDC -0.00%, różnica 0.01 pkt proc.); Korea BTC +0.80% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-09-23: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-09-30: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.834 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-09-25: giełda -93.0 vs MOF -362.0 mld JPY.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- rwa.json: HTTP 404 (brak pliku)
- SOPR BTC (źródło opóźnia 7 dni): brak dnia danych SOPR w pliku
- tokenizowane aktywa RWA (co 6 h): brak pliku data/rwa.json — panel na stronie ukryty (tylko uwaga)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDC, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
