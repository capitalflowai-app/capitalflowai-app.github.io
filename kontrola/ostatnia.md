# Kontrola strony — 29.09.2026, 08:40 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 316 ms).
- Ostatni przebieg automatu: 29.09.2026, 08:35 — sprzed 4 min; źródeł: 60, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 72 (success: 72).
- Pliki danych (wiek): etf 0h36, trendy 0h04, oecd 1h36, rynki 0h36, dzwignia 0h04, wieloryby 0h04, energia 5h34, usa-makro 5h34, bilans-usa 11h48, krypto 0h36, instytucje 0h36, tic 8h54, cm 0h36, fred 0h36, cftc 1h36, ceny 0h36, indeksy 0h36, ceny-krypto 0h36, snb 10h37, lancuch 0h04, insider HTTP 404, stres 5h34, aukcje 5h34, krypto-dzien 0h04, krypto-dziennik 0h04, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 36 min | 2026-09-29T06:04:16+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-09-29T06:35:56+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 36 min | 2026-09-29T06:04:16+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 30 h 40 min | 2026-09-25 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 6 h 40 min | 2026-09-28 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 6 h 40 min | 2026-09-28 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 6 d 6 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 6 d 6 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 5 d 6 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 59 d 6 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 28 d 6 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 28 d 6 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 3.98%, norma (mediana 3 dni) 5.01% — ℹ️ historia 3 z 7 dni — bez oceny.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 3 dni) 3.05% — ℹ️ historia 3 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-29 vs 2026-09-28: 9 par giełda/aktywo, rozbieżności > 5%: 7 ⚠️.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- zgodność cen BTC/ETH: brak odczytu (HTTP Error 403: Forbidden)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance USDT, Bitfinex USDC, Bitfinex USDT, Bybit USDT, KuCoin USDC, KuCoin USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
