# Kontrola strony — 28.09.2026, 08:42 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 215 ms).
- Ostatni przebieg automatu: 28.09.2026, 08:38 — sprzed 4 min; źródeł: 60, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 84 (success: 83, failure: 1).
- Nieudane przebiegi (24 h): 27.09.2026, 12:47 — zbuduj / Test bramki strony dla plików widoków silnika. Od ostatniej porażki 70 udanych przebiegów z rzędu.
- Pliki danych (wiek): etf 0h38, trendy 0h04, oecd 1h38, rynki 0h38, dzwignia 0h04, wieloryby 0h04, energia 5h38, usa-makro 5h38, bilans-usa 11h55, krypto 0h38, instytucje 0h38, tic 8h58, cm 0h38, fred 0h38, cftc 1h38, ceny 0h38, indeksy 0h38, ceny-krypto 0h38, snb 7h39, lancuch 0h04, insider HTTP 404, stres 5h38, aukcje 5h38, krypto-dzien 0h04, krypto-dziennik 0h04, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 38 min | 2026-09-28T06:03:56+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-09-28T06:38:11+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 38 min | 2026-09-28T06:03:56+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 30 h 42 min | 2026-09-24 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 6 h 42 min | 2026-09-25 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 6 h 42 min | 2026-09-25 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 5 d 6 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 5 d 6 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 4 d 6 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 58 d 6 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 27 d 6 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 27 d 6 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.01%, norma (mediana 2 dni) 4.71% — ℹ️ historia 2 z 7 dni — bez oceny.
- Cena BTC: 83,122 vs 83,086 USD — różnica 0.04% ✅.
- Cena ETH: 2,649 vs 2,647 USD — różnica 0.06% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 2 dni) 3.05% — ℹ️ historia 2 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-28 vs 2026-09-27: 9 par giełda/aktywo, rozbieżności > 5%: 6 ⚠️.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance USDT, Bitfinex USDC, Bitfinex USDT, Bybit USDT, KuCoin USDC, OKX USDC — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)
- 1 nieudany przebieg automatu w 24 h — już naprawione: od ostatniej porażki 70 udanych przebiegów z rzędu (27.09 12:47 (zbuduj / Test bramki strony dla plików widoków silnika))

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
