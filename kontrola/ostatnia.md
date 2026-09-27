# Kontrola strony — 27.09.2026, 08:37 (czas polski)

**Wynik: BŁĄD**

❌ Błędów: 1 — wymagają uwagi (szczegóły niżej).

- Strona główna: działa (HTTP 200, 202 ms).
- Ostatni przebieg automatu: 27.09.2026, 08:33 — sprzed 4 min; źródeł: 55, bez odpowiedzi: żadne; błędów zbieracza: 1.
- Przebiegi Actions w 24 h: 83 (success: 79, failure: 4).
- Pliki danych (wiek): etf 0h34, trendy 0h04, oecd 1h51, rynki 0h34, dzwignia 0h34, wieloryby 0h04, energia 5h47, usa-makro 5h47, bilans-usa 11h50, krypto 0h52, instytucje 0h52, tic 8h54, cm 0h34, fred 0h34, cftc 2h09, ceny 0h34, indeksy 0h52, ceny-krypto 0h34, insider HTTP 404, stres 6h01, aukcje 6h01, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 34 min | 2026-09-27T06:03:23+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-09-27T06:33:07+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 34 min | 2026-09-27T06:03:23+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-09-24 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 0 h 00 min | 2026-09-25 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-09-25 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 4 d 6 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 4 d 6 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 3 d 6 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 57 d 6 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 26 d 6 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 26 d 6 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.14%, norma (mediana 1 dni) 4.30% — ℹ️ historia 1 z 7 dni — bez oceny.
- Cena BTC: 84,521 vs 84,513 USD — różnica 0.01% ✅.
- Cena ETH: 2,707 vs 2,707 USD — różnica 0.01% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 1 dni) 3.05% — ℹ️ historia 1 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-27 vs 2026-09-26: 0 par giełda/aktywo, rozbieżności > 5%: 0 ✅.

## Błędy (wymagają uwagi)
- 4 nieudanych przebiegów automatu w 24 h

## Uwagi
- błąd zbieracza: BCB: 1 serie bez odpowiedzi, np. 13968: The read operation timed out
- insider.json: HTTP 404 (brak pliku)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
