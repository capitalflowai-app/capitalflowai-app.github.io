# Kontrola strony — 30.09.2026, 08:40 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 280 ms).
- Ostatni przebieg automatu: 30.09.2026, 08:36 — sprzed 4 min; źródeł: 60, bez odpowiedzi: żadne; błędów zbieracza: 1.
- Przebiegi Actions w 24 h: 72 (success: 72).
- Pliki danych (wiek): etf 0h36, trendy 0h04, oecd 1h36, rynki 0h36, dzwignia 0h04, wieloryby 0h04, energia 5h33, usa-makro 5h33, bilans-usa 11h48, krypto 0h36, instytucje 0h36, tic 8h53, cm 0h36, fred 0h36, cftc 1h36, ceny 0h36, indeksy 0h36, ceny-krypto 0h36, snb 10h36, lancuch 0h04, insider HTTP 404, stres 5h33, aukcje 5h33, krypto-dzien 0h04, krypto-dziennik 0h03, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 36 min | 2026-09-30T06:04:15+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-09-30T06:36:31+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 36 min | 2026-09-30T06:04:15+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 30 h 40 min | 2026-09-28 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 6 h 40 min | 2026-09-29 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 6 h 40 min | 2026-09-29 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 7 d 6 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 7 d 6 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 6 d 6 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 60 d 6 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 29 d 6 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 29 d 6 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.27%, norma (mediana 4 dni) 4.66% — ℹ️ historia 4 z 7 dni — bez oceny.
- Cena BTC: 83,062 vs 83,031 USD — różnica 0.04% ✅.
- Cena ETH: 2,663 vs 2,663 USD — różnica 0.00% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 4 dni) 3.05% — ℹ️ historia 4 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-30 vs 2026-09-29: 9 par giełda/aktywo, rozbieżności > 5%: 6 ⚠️.

## Uwagi
- błąd zbieracza: BCB bilans płatniczy: 1 serie bez odpowiedzi, np. 23001: HTTP Error 502: Bad Gateway
- insider.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance USDT, Bitfinex USDT, Bybit USDT, KuCoin USDC, KuCoin USDT, OKX USDC — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
