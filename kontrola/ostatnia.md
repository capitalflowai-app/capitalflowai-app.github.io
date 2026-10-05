# Kontrola strony — 05.10.2026, 14:03 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 1 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 235 ms).
- Ostatni przebieg automatu: 05.10.2026, 14:00 — sprzed 2 min; źródeł: 76, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 101 (in_progress: 1, success: 95, cancelled: 5).
- Pliki danych (wiek): etf 0h17, trendy 0h02, oecd 4h48, rynki 0h17, dzwignia 0h05, wieloryby 0h02, energia 3h39, usa-makro 3h39, bilans-usa 16h51, krypto 0h42, krypto-top10 0h07, instytucje 0h42, tic 13h43, cm 0h17, fred 0h17, cftc 4h29, ceny 0h17, indeksy 0h42, ceny-krypto 0h17, snb 4h02, ici 9h42, fed 0h05, lancuch 0h05, wycena 2h51, insider wyłączone, nastroj 4h02, stres 3h39, aukcje 3h39, swiat-dzien 0h02, swiat-dziennik 0h02, premie 0h02, dolar 0h07, jpx 10h24, rwa 2h10, krypto-dzien 0h02, krypto-dziennik 0h02, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 17 min | 2026-10-05T11:45:49+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 02 min | 2026-10-05T12:00:58+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 17 min | 2026-10-05T11:45:49+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 03 min | 2026-10-05T12:00 | — |
| TGA (Fiscal Data, dziennie) | ⚠️ | 36 h 03 min | 2026-10-01 | próg 36 h 00 min (godziny robocze) |
| ETF krypto (SoSoValue, dziennie) | ✅ | 12 h 03 min | 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 12 h 03 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 5 d 12 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 5 d 12 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 4 d 12 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 65 d 12 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 4 d 12 h | 2026-09 | — |
| BLS (miesięcznie) | ✅ | 34 d 12 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 04 min | 2026-10-05T11:58:52+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 12 h 03 min | 2026-10-04 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 12 h | 2026-09-28 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 07 min | 2026-10-05T11:55:45+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 11 d 12 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 4 d 12 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 9 d 12 h | 2026-09-25 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ✅ | 2 d 12 h | 2026-10-02 | — |
| TRENDY świat — ostatnia sesja z wynikiem sygnałów | — | — | — | dziennik rusza 2026-10-05 — pierwsze wyniki po pierwszym sprawdzeniu |
| tokenizowane aktywa RWA (co 3 h) | ✅ | 2 h 10 min | 2026-10-05T09:52:50+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 3 h) | ✅ | 2 h 10 min | 2026-10-05T09:52:50+00:00 | — |
| tokenizowane aktywa — dane emitentów (co 3 h) | ✅ | 2 h 10 min | 2026-10-05T09:52:50+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.92%, norma (mediana 9 dni) 4.30% — ✅ odchylenie od mediany 0.61 pkt proc. (progi 2 / 5).
- Cena BTC: 86,154 vs 86,113 USD — różnica 0.05% ✅.
- Cena ETH: 2,716 vs 2,719 USD — różnica 0.08% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 9 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-05 vs 2026-10-04: odstęp migawek 27.0 h — porównanie z przepływami 24 h tylko przy ok. dobie ℹ️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.82% (2026-09-28), norma (mediana 54 dni) +0.81% — ✅ odchylenie najnowszego dnia od normy 0.01 pkt proc. (próg 1.5), norma +0.81% (próg ±3%).
- Premie krypto: USA BTC +0.00% (przez USDC -0.01%, różnica 0.01 pkt proc.); Korea BTC +0.23% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-02) · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-02).
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-09-23: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-09-30: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.834 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-09-25: giełda -93.0 vs MOF -362.0 mld JPY.
- Tokenizowane aktywa (RWA): ℹ️ zapisów sum 3 (od 2026-10-03) — porównanie zmiany 7 dni od 8. dnia; bez bieżącej wyceny 2% wartości (0.4 mld USD, liczba produktów 12: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 26.7 mld USD ℹ️; ℹ️ 2026-10-04: zmiana zbioru produktów z odczytu własnego albo danych emitentów (0.0 → 10.6 mld USD) — skok sumy liczony bez nich; ℹ️ 2026-10-05: zmiana zbioru produktów z odczytu własnego albo danych emitentów (10.6 → 22.0 mld USD) — skok sumy liczony bez nich; skoków sumy ponad 25% w tygodniu: brak ✅.
- Tokenizowane aktywa — odczyt własny z łańcucha: podaż 24 h: zmian ponad 50% brak ✅; wartość vs ostatnio znana: w paśmie 1/3–3× ✅; w sumach z odczytu własnego: 7 z 7 produktów, 10.9 mld USD.
- Tokenizowane aktywa — dane emitentów: w sumach wg emitentów: 14 z 14 produktów, 11.1 mld USD; inny zakres niż ostatnio znana (opisane na stronie): Centrifuge Protocol 966 mln USD vs ostatnio znana 1482 mln (0.65×); Ondo Global Markets 1285 mln USD vs ostatnio znana 966 mln (1.33×); Securitize Tokenized AAA CLO Fund 282 mln USD vs ostatnio znana 104 mln (2.72×); xStocks 922 mln USD vs ostatnio znana 438 mln (2.11×) ℹ️.

## Uwagi
- TGA (Fiscal Data, dziennie): dane z 2026-10-01 — 36 h 03 min temu (próg 36 h 00 min (godziny robocze))

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
