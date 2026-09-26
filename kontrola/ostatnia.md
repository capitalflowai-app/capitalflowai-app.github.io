# Kontrola strony — 26.09.2026, 15:31 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 4 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 135 ms).
- Ostatni przebieg automatu: 26.09.2026, 15:26 — sprzed 4 min; źródeł: 52, bez odpowiedzi: indeksy_ix; błędów zbieracza: 1.
- Przebiegi Actions w 24 h: 83 (in_progress: 1, success: 79, failure: 2, cancelled: 1).
- Pliki danych (wiek): etf 0h47, trendy 0h04, oecd 2h47, rynki 0h47, dzwignia 0h28, wieloryby 0h04, energia 0h47, usa-makro 0h47, bilans-usa 18h48, krypto 0h47, instytucje 0h28, tic 16h03, cm 0h47, fred 0h28, cftc 3h28, ceny 0h28, indeksy 0h04, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 47 min | 2026-09-26T12:43:24+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-09-26T13:26:18+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 28 min | 2026-09-26T13:02:12+00:00 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-09-24 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 0 h 00 min | 2026-09-25 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-09-25 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 13 h | 2026-09-22 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 13 h | 2026-09-22 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 13 h | 2026-09-23 | — |
| TIC (miesięcznie) | ✅ | 56 d 13 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 25 d 13 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 25 d 13 h | 2026-08 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.45%, norma (mediana 0 dni) — — ℹ️ historia 0 z 7 dni — bez oceny.
- Cena BTC: 83,884 vs 83,910 USD — różnica 0.03% ✅.
- Cena ETH: 2,683 vs 2,684 USD — różnica 0.02% ✅.
- TGA 2026-09-23: Fiscal Data 947,317 vs FRED 977,084 mln USD — różnica 3.05%, norma (mediana 0 dni) — — ℹ️ historia 0 z 7 dni — bez oceny.
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby: archiwum ma mniej niż dwa dni — porównanie od jutra.

## Uwagi
- źródła bez odpowiedzi w ostatnim przebiegu: indeksy_ix
- błąd zbieracza: Indeksy: FTSE: pusta odpowiedź; EODHD HTTP 404 — nieznany kod FTMIB.INDX
- indeksy.json: części bez odpowiedzi: ix
- 2 nieudany przebieg automatu w 24 h (ostatni: 26.09.2026, 15:25)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
