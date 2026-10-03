# Kontrola strony — 03.10.2026, 13:59 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 4 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 308 ms).
- Ostatni przebieg automatu: 03.10.2026, 13:55 — sprzed 4 min; źródeł: 70, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 79 (success: 79).
- Pliki danych (wiek): etf 0h53, trendy 0h04, oecd 5h58, rynki 0h53, dzwignia 0h04, wieloryby 0h04, energia 3h55, usa-makro 3h55, bilans-usa 16h54, krypto 0h53, krypto-top10 0h43, instytucje 0h53, tic 13h56, cm 0h53, fred 0h53, cftc 5h58, ceny 0h53, indeksy 0h53, ceny-krypto 0h53, snb 3h07, ici HTTP 404, fed 0h04, lancuch 0h04, wycena 3h36, insider HTTP 404, nastroj 4h50, stres 3h55, aukcje 3h55, swiat-dzien 0h04, swiat-dziennik 0h03, premie 0h04, dolar 0h43, krypto-dzien 0h04, krypto-dziennik 0h03, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: Premie krypto: historia Korei przerwana — limit czasu (20 s); reszta w następnym przebiegu · poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni ici.json: brak na stronie (404) · Fundusze USA: brak poprzedniego pliku — próba w pierwszym przebiegu pełnej godziny.

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 53 min | 2026-10-03T11:06:08+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-10-03T11:55:27+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 53 min | 2026-10-03T11:06:08+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 05 min | 2026-10-03T11:54 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 11 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 11 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 11 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 63 d 11 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 32 d 11 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 32 d 11 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 03 min | 2026-10-03T11:56:16+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 11 h 59 min | 2026-10-02 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ? | — | — | brak dnia danych SOPR w pliku |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 43 min | 2026-10-03T11:16:01+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.05%, norma (mediana 7 dni) 4.35% — ✅ odchylenie od mediany 0.70 pkt proc. (progi 2 / 5).
- Cena BTC: 84,668 vs 84,665 USD — różnica 0.00% ✅.
- Cena ETH: 2,685 vs 2,686 USD — różnica 0.05% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 7 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-03 vs 2026-10-02: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia —, norma (mediana 0 dni) — — ℹ️ wspólnych dni 0 z 20 — bez oceny.
- Premie krypto: USA BTC +0.01% (przez USDC -0.00%, różnica 0.01 pkt proc.); Korea BTC +0.93% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.

## Uwagi
- ici.json: HTTP 404 (brak pliku)
- insider.json: HTTP 404 (brak pliku)
- SOPR BTC (źródło opóźnia 7 dni): brak dnia danych SOPR w pliku
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDC, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
