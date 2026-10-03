# Kontrola strony — 03.10.2026, 07:53 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 5 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 157 ms).
- Ostatni przebieg automatu: 03.10.2026, 07:52 — sprzed 1 min; źródeł: 61, bez odpowiedzi: obce_br; błędów zbieracza: 1.
- Przebiegi Actions w 24 h: 74 (in_progress: 1, success: 73).
- Pliki danych (wiek): etf 0h50, trendy 0h01, oecd 5h50, rynki 0h50, dzwignia 0h01, wieloryby 0h01, energia 3h51, usa-makro 3h51, bilans-usa 10h48, krypto 0h50, instytucje 0h50, tic 7h50, cm 0h50, fred 0h50, cftc 5h50, ceny 0h50, indeksy 0h50, ceny-krypto 0h50, snb 9h04, lancuch 0h15, insider HTTP 404, stres 3h51, aukcje 3h51, swiat-dzien 0h01, swiat-dziennik HTTP 404, krypto-dzien 0h01, krypto-dziennik 0h00, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni swiat-dziennik.json: brak na stronie (404).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 50 min | 2026-10-03T05:03:17+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 01 min | 2026-10-03T05:52:47+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 50 min | 2026-10-03T05:03:17+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 5 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 5 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 5 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 63 d 5 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 32 d 5 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 32 d 5 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.21%, norma (mediana 7 dni) 4.35% — ✅ odchylenie od mediany 0.14 pkt proc. (progi 2 / 5).
- Cena BTC: 84,636 vs 84,634 USD — różnica 0.00% ✅.
- Cena ETH: 2,677 vs 2,677 USD — różnica 0.02% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 7 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-03 vs 2026-10-02: 9 par giełda/aktywo, rozbieżności > 5%: 7 ⚠️.

## Uwagi
- źródła bez odpowiedzi w ostatnim przebiegu: obce_br
- błąd zbieracza: BCB: brak dni (13970: <urlopen error [Errno -2] Name or service not known>)
- insider.json: HTTP 404 (brak pliku)
- swiat-dziennik.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Bitfinex USDC, Bitfinex USDT, Bybit USDC, Bybit USDT, KuCoin USDC, KuCoin USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
