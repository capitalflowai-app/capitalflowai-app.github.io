# Kontrola strony — 03.10.2026, 12:18 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 448 ms).
- Ostatni przebieg automatu: 03.10.2026, 12:15 — sprzed 3 min; źródeł: 70, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 81 (success: 81).
- Pliki danych (wiek): etf 0h15, trendy 0h03, oecd 4h17, rynki 0h48, dzwignia 0h03, wieloryby 0h03, energia 2h14, usa-makro 2h14, bilans-usa 15h13, krypto 0h15, krypto-top10 0h02, instytucje 0h15, tic 12h15, cm 0h15, fred 0h15, cftc 4h17, ceny 0h15, indeksy 0h15, ceny-krypto 0h15, snb 1h27, fed 0h03, lancuch 0h15, wycena 1h55, insider HTTP 404, nastroj 3h09, stres 2h14, aukcje 2h14, swiat-dzien 0h03, swiat-dziennik 0h02, premie 0h03, dolar 0h02, krypto-dzien 0h03, krypto-dziennik 0h02, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: Premie krypto: historia Korei przerwana — limit czasu (20 s); reszta w następnym przebiegu · poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni krypto-top10.json: brak na stronie (404) · poprzedni krypto-top10-logo.json: brak na stronie (404).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 48 min | 2026-10-03T09:30:46+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 03 min | 2026-10-03T10:15:05+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 15 min | 2026-10-03T10:03:21+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 04 min | 2026-10-03T10:14 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 10 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 10 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 10 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 63 d 10 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 32 d 10 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 32 d 10 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 02 min | 2026-10-03T10:15:50+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 10 h 18 min | 2026-10-02 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ? | — | — | brak dnia danych SOPR w pliku |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 02 min | 2026-10-03T10:15:52+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.07%, norma (mediana 7 dni) 4.35% — ✅ odchylenie od mediany 0.72 pkt proc. (progi 2 / 5).
- Cena BTC: 84,568 vs 84,574 USD — różnica 0.01% ✅.
- Cena ETH: 2,681 vs 2,682 USD — różnica 0.03% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 7 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-03 vs 2026-10-02: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia —, norma (mediana 0 dni) — — ℹ️ wspólnych dni 0 z 20 — bez oceny.
- Premie krypto: USA BTC +0.00% (przez USDC +0.00%, różnica 0.00 pkt proc.); Korea BTC +0.92% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- SOPR BTC (źródło opóźnia 7 dni): brak dnia danych SOPR w pliku
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDC, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
