# Kontrola strony — 03.10.2026, 10:26 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 4 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 433 ms).
- Ostatni przebieg automatu: 03.10.2026, 10:21 — sprzed 4 min; źródeł: 68, bez odpowiedzi: żadne; błędów zbieracza: 1.
- Przebiegi Actions w 24 h: 78 (success: 78).
- Pliki danych (wiek): etf 0h21, trendy 0h04, oecd 2h24, rynki 0h04, dzwignia 0h04, wieloryby 0h04, energia 0h21, usa-makro 0h21, bilans-usa 13h21, krypto 0h21, instytucje 0h21, tic 10h23, cm 0h21, fred 0h21, cftc 2h24, ceny 0h21, indeksy 0h21, ceny-krypto 0h21, snb 11h36, fed 0h04, lancuch 0h04, wycena 0h03, insider HTTP 404, nastroj 1h16, stres 0h21, aukcje 0h21, swiat-dzien 0h04, swiat-dziennik 0h03, premie 0h04, krypto-dzien 0h04, krypto-dziennik 0h03, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni wycena.json: brak na stronie (404) · poprzedni swiat-dziennik.json: brak na stronie (404).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 04 min | 2026-10-03T08:21:56+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-10-03T08:21:56+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 21 min | 2026-10-03T08:04:11+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 05 min | 2026-10-03T08:21 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 8 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 8 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 8 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 63 d 8 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 32 d 8 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 32 d 8 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 03 min | 2026-10-03T08:22:50+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 8 h 26 min | 2026-10-02 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ? | — | — | brak dnia danych SOPR w pliku |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.30%, norma (mediana 7 dni) 4.35% — ✅ odchylenie od mediany 0.05 pkt proc. (progi 2 / 5).
- Cena BTC: 84,576 vs 84,578 USD — różnica 0.00% ✅.
- Cena ETH: 2,679 vs 2,681 USD — różnica 0.07% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 7 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-03 vs 2026-10-02: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia —, norma (mediana 0 dni) — — ℹ️ wspólnych dni 0 z 20 — bez oceny.
- Premie krypto: USA BTC +0.00% (przez USDC +0.00%, różnica 0.00 pkt proc.); Korea BTC +0.94% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.

## Uwagi
- błąd zbieracza: Premie krypto: historia Korei: The read operation timed out
- insider.json: HTTP 404 (brak pliku)
- SOPR BTC (źródło opóźnia 7 dni): brak dnia danych SOPR w pliku
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDC, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
