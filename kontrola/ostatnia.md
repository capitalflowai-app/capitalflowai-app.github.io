# Kontrola strony — 27.09.2026, 12:59 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 2 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 162 ms).
- Ostatni przebieg automatu: 27.09.2026, 12:54 — sprzed 4 min; źródeł: 58, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Przebiegi Actions w 24 h: 86 (success: 82, failure: 4).
- Nieudane przebiegi (24 h): 27.09.2026, 12:47 — zbuduj / Test bramki strony dla plików widoków silnika; 26.09.2026, 20:46 — publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba); 26.09.2026, 15:37 — zbuduj / Test bramki strony dla plików widoków silnika; 26.09.2026, 15:25 — zbuduj / Testy zbieracza. Od ostatniej porażki 2 udane przebiegi z rzędu.
- Pliki danych (wiek): etf 0h56, trendy 0h04, oecd 0h07, rynki 0h56, dzwignia 0h56, wieloryby 0h04, energia 3h56, usa-makro 3h56, bilans-usa 16h12, krypto 0h14, instytucje 0h14, tic 13h15, cm 0h56, fred 0h56, cftc 0h14, ceny 0h56, indeksy 0h14, ceny-krypto 0h56, snb 0h07, lancuch 0h07, insider HTTP 404, stres 4h09, aukcje 4h09, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 56 min | 2026-09-27T10:02:48+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-09-27T10:54:33+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 56 min | 2026-09-27T10:02:48+00:00 | — |
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

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.07%, norma (mediana 1 dni) 4.30% — ℹ️ historia 1 z 7 dni — bez oceny.
- Cena BTC: 84,823 vs 84,777 USD — różnica 0.05% ✅.
- Cena ETH: 2,709 vs 2,709 USD — różnica 0.00% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 1 dni) 3.05% — ℹ️ historia 1 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-09-27 vs 2026-09-26: 0 par giełda/aktywo, rozbieżności > 5%: 0 ✅.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- 4 nieudane przebiegi automatu w 24 h — już naprawione: od ostatniej porażki 2 udane przebiegi z rzędu (27.09 12:47 (zbuduj / Test bramki strony dla plików widoków silnika), 26.09 20:46 (publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba)), 26.09 15:37 (zbuduj / Test bramki strony dla plików widoków silnika), 26.09 15:25 (zbuduj / Testy zbieracza))

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
