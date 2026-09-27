# Kontrola strony — 27.09.2026, 19:49 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 198 ms).
- Ostatni przebieg automatu: 27.09.2026, 19:46 — sprzed 3 min; źródeł: 59, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 81 (success: 79, failure: 2).
- Nieudane przebiegi (24 h): 27.09.2026, 12:47 — zbuduj / Test bramki strony dla plików widoków silnika; 26.09.2026, 20:46 — publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba). Od ostatniej porażki 27 udanych przebiegów z rzędu.
- Pliki danych (wiek): etf 0h47, trendy 0h03, oecd 0h57, rynki 0h47, dzwignia 0h47, wieloryby 0h03, energia 4h46, usa-makro 4h46, bilans-usa 23h02, krypto 0h05, instytucje 0h05, tic 20h05, cm 0h47, fred 0h47, cftc 1h03, ceny 0h47, indeksy 0h05, ceny-krypto 0h47, snb 6h58, lancuch 0h05, insider HTTP 404, stres 4h59, aukcje 4h59, krypto-dzien 0h03, krypto-dziennik HTTP 404, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni krypto-dzien.json: brak na stronie (404) · Krypto dziennie: limit czasu budowniczego (60 s) — reszta w następnym przebiegu · poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni krypto-dziennik.json: brak na stronie (404).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 47 min | 2026-09-27T17:02:35+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 03 min | 2026-09-27T17:46:05+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 47 min | 2026-09-27T17:02:35+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-09-24 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 0 h 00 min | 2026-09-25 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-09-25 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 4 d 17 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 4 d 17 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 3 d 17 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 57 d 17 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 26 d 17 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 26 d 17 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.13%, norma (mediana 1 dni) 4.30% — ℹ️ historia 1 z 7 dni — bez oceny.
- Cena BTC: 84,489 vs 84,497 USD — różnica 0.01% ✅.
- Cena ETH: 2,688 vs 2,689 USD — różnica 0.03% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 1 dni) 3.05% — ℹ️ historia 1 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-27 vs 2026-09-26: 0 par giełda/aktywo, rozbieżności > 5%: 0 ✅.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- krypto-dziennik.json: HTTP 404 (brak pliku)
- 2 nieudane przebiegi automatu w 24 h — już naprawione: od ostatniej porażki 27 udanych przebiegów z rzędu (27.09 12:47 (zbuduj / Test bramki strony dla plików widoków silnika), 26.09 20:46 (publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba)))

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
