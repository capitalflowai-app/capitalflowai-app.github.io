# Kontrola strony — 27.09.2026, 12:52 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 2 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 186 ms).
- Ostatni przebieg automatu: 27.09.2026, 12:51 — sprzed 1 min; źródeł: 58, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 86 (success: 82, failure: 4).
- Nieudane przebiegi (24 h): 27.09.2026, 12:47 — zbuduj / Test bramki strony dla plików widoków silnika; 26.09.2026, 20:46 — publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba); 26.09.2026, 15:37 — zbuduj / Test bramki strony dla plików widoków silnika; 26.09.2026, 15:25 — zbuduj / Testy zbieracza. Od ostatniej porażki 1 udanych przebiegów z rzędu.
- Pliki danych (wiek): etf 0h50, trendy 0h01, oecd 0h01, rynki 0h50, dzwignia 0h50, wieloryby 0h01, energia 3h49, usa-makro 3h49, bilans-usa 16h05, krypto 0h07, instytucje 0h07, tic 13h09, cm 0h50, fred 0h50, cftc 0h07, ceny 0h50, indeksy 0h07, ceny-krypto 0h50, snb 0h01, lancuch 0h01, insider HTTP 404, stres 4h02, aukcje 4h02, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta) · poprzedni lancuch.json: brak na stronie (404) · poprzedni snb.json: brak na stronie (404).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 50 min | 2026-09-27T10:02:48+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 01 min | 2026-09-27T10:51:36+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 50 min | 2026-09-27T10:02:48+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-09-24 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 0 h 00 min | 2026-09-25 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-09-25 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 4 d 10 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 4 d 10 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 3 d 10 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 57 d 10 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 26 d 10 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 26 d 10 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.08%, norma (mediana 1 dni) 4.30% — ℹ️ historia 1 z 7 dni — bez oceny.
- Cena BTC: 84,824 vs 84,832 USD — różnica 0.01% ✅.
- Cena ETH: 2,709 vs 2,710 USD — różnica 0.03% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 1 dni) 3.05% — ℹ️ historia 1 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-27 vs 2026-09-26: 0 par giełda/aktywo, rozbieżności > 5%: 0 ✅.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- 4 nieudane przebiegi automatu w 24 h — już naprawione: od ostatniej porażki 1 udanych z rzędu (27.09 12:47 (zbuduj / Test bramki strony dla plików widoków silnika), 26.09 20:46 (publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba)), 26.09 15:37 (zbuduj / Test bramki strony dla plików widoków silnika), 26.09 15:25 (zbuduj / Testy zbieracza))

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
