# Kontrola strony — 27.09.2026, 21:16 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 1064 ms).
- Ostatni przebieg automatu: 27.09.2026, 21:12 — sprzed 3 min; źródeł: 60, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 82 (in_progress: 1, success: 80, failure: 1).
- Nieudane przebiegi (24 h): 27.09.2026, 12:47 — zbuduj / Test bramki strony dla plików widoków silnika. Od ostatniej porażki 32 udane przebiegi z rzędu.
- Pliki danych (wiek): etf 0h14, trendy 0h03, oecd 2h24, rynki 0h14, dzwignia 0h03, wieloryby 0h03, energia 0h14, usa-makro 0h14, bilans-usa 0h28, krypto 0h28, instytucje 0h28, tic 21h32, cm 0h14, fred 0h14, cftc 2h30, ceny 0h14, indeksy 0h28, ceny-krypto 0h14, snb 8h24, lancuch 0h14, insider HTTP 404, stres 0h14, aukcje 0h14, krypto-dzien 0h03, krypto-dziennik HTTP 404, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni krypto-dziennik.json: brak na stronie (404).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 14 min | 2026-09-27T19:02:17+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 03 min | 2026-09-27T19:12:59+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 14 min | 2026-09-27T19:02:17+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-09-24 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 0 h 00 min | 2026-09-25 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-09-25 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 4 d 19 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 4 d 19 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 3 d 19 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 57 d 19 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 26 d 19 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 26 d 19 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.11%, norma (mediana 1 dni) 4.30% — ℹ️ historia 1 z 7 dni — bez oceny.
- Cena BTC: 84,782 vs 84,767 USD — różnica 0.02% ✅.
- Cena ETH: 2,695 vs 2,695 USD — różnica 0.01% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 1 dni) 3.05% — ℹ️ historia 1 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-27 vs 2026-09-26: 0 par giełda/aktywo, rozbieżności > 5%: 0 ✅.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- krypto-dziennik.json: HTTP 404 (brak pliku)
- 1 nieudany przebieg automatu w 24 h — już naprawione: od ostatniej porażki 32 udane przebiegi z rzędu (27.09 12:47 (zbuduj / Test bramki strony dla plików widoków silnika))

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
