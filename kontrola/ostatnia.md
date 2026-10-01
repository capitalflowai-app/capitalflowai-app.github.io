# Kontrola strony — 01.10.2026, 08:42 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 2 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 103 ms).
- Ostatni przebieg automatu: 01.10.2026, 08:38 — sprzed 4 min; źródeł: 60, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 72 (success: 72).
- Pliki danych (wiek): etf 0h53, trendy 0h04, oecd 1h12, rynki 0h53, dzwignia 0h04, wieloryby 0h04, energia 4h54, usa-makro 4h54, bilans-usa 11h49, krypto 0h53, instytucje 0h53, tic 8h53, cm 0h53, fred 0h53, cftc 1h12, ceny 0h53, indeksy 0h53, ceny-krypto 0h53, snb 10h12, lancuch 0h04, insider HTTP 404, stres 4h54, aukcje 4h54, krypto-dzien 0h04, krypto-dziennik 0h03, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 53 min | 2026-10-01T05:48:44+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-10-01T06:38:22+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 53 min | 2026-10-01T05:48:44+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 30 h 42 min | 2026-09-29 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 6 h 42 min | 2026-09-30 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 6 h 42 min | 2026-09-30 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 30 h 42 min | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 8 d 6 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 7 d 6 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 61 d 6 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 30 d 6 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 30 d 6 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.40%, norma (mediana 5 dni) 4.30% — ℹ️ historia 5 z 7 dni — bez oceny.
- Cena BTC: 84,119 vs 84,115 USD — różnica 0.01% ✅.
- Cena ETH: 2,714 vs 2,714 USD — różnica 0.02% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 5 dni) 3.05% — ℹ️ historia 5 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-01 vs 2026-09-30: 9 par giełda/aktywo, rozbieżności > 5%: 7 ⚠️.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance USDT, Bitfinex USDC, Bitfinex USDT, Bybit USDT, KuCoin USDC, KuCoin USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
