# Kontrola strony — 02.10.2026, 08:41 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 2 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 439 ms).
- Ostatni przebieg automatu: 02.10.2026, 08:36 — sprzed 5 min; źródeł: 60, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 72 (success: 72).
- Pliki danych (wiek): etf 0h37, trendy 0h05, oecd 0h53, rynki 0h37, dzwignia 0h05, wieloryby 0h05, energia 4h37, usa-makro 4h37, bilans-usa 11h49, krypto 0h37, instytucje 0h37, tic 8h52, cm 0h37, fred 0h37, cftc 0h37, ceny 0h37, indeksy 0h37, ceny-krypto 0h37, snb 9h52, lancuch 0h05, insider HTTP 404, stres 4h37, aukcje 4h37, krypto-dzien 0h05, krypto-dziennik 0h04, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 37 min | 2026-10-02T06:04:43+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 05 min | 2026-10-02T06:36:41+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 37 min | 2026-10-02T06:04:43+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 30 h 41 min | 2026-09-30 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 6 h 41 min | 2026-10-01 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 6 h 41 min | 2026-10-01 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 2 d 6 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 9 d 6 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 30 h 41 min | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 62 d 6 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 31 d 6 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 31 d 6 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.35%, norma (mediana 6 dni) 4.35% — ℹ️ historia 6 z 7 dni — bez oceny.
- Cena BTC: 85,966 vs 85,913 USD — różnica 0.06% ✅.
- Cena ETH: 2,731 vs 2,730 USD — różnica 0.01% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 6 dni) 3.05% — ℹ️ historia 6 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-02 vs 2026-10-01: 9 par giełda/aktywo, rozbieżności > 5%: 6 ⚠️.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Bitfinex USDC, Bitfinex USDT, Bybit USDC, Bybit USDT, KuCoin USDC, OKX USDC — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
