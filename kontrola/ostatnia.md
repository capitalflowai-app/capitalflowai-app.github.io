# Kontrola strony — 03.10.2026, 08:59 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 903 ms).
- Ostatni przebieg automatu: 03.10.2026, 08:54 — sprzed 4 min; źródeł: 62, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 76 (success: 76).
- Pliki danych (wiek): etf 0h57, trendy 0h04, oecd 0h57, rynki 0h57, dzwignia 0h04, wieloryby 0h04, energia 4h56, usa-makro 4h56, bilans-usa 11h54, krypto 0h57, instytucje 0h57, tic 8h56, cm 0h57, fred 0h57, cftc 0h57, ceny 0h57, indeksy 0h57, ceny-krypto 0h57, snb 10h10, fed 0h04, lancuch 0h14, insider HTTP 404, stres 4h56, aukcje 4h56, swiat-dzien 0h04, swiat-dziennik HTTP 404, krypto-dzien 0h04, krypto-dziennik 0h03, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni fed.json: brak na stronie (404) · poprzedni swiat-dziennik.json: brak na stronie (404).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 57 min | 2026-10-03T06:01:28+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-10-03T06:54:53+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 57 min | 2026-10-03T06:01:28+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 6 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 6 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 6 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 63 d 6 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 32 d 6 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 32 d 6 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 04 min | 2026-10-03T06:55:20+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.15%, norma (mediana 7 dni) 4.35% — ✅ odchylenie od mediany 0.20 pkt proc. (progi 2 / 5).
- Cena BTC: 84,562 vs 84,571 USD — różnica 0.01% ✅.
- Cena ETH: 2,679 vs 2,681 USD — różnica 0.06% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 7 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-03 vs 2026-10-02: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- swiat-dziennik.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDC, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
