# Kontrola strony — 05.10.2026, 09:22 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 2 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 303 ms).
- Ostatni przebieg automatu: 05.10.2026, 09:19 — sprzed 3 min; źródeł: 89, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 34 (success: 33, cancelled: 1).
- Pliki danych (wiek): etf 0h58, trendy 0h03, oecd 0h08, rynki 0h58, dzwignia 0h03, wieloryby 0h03, energia 5h01, usa-makro 5h01, bilans-usa 12h11, krypto 0h03, krypto-top10 0h47, instytucje 0h03, tic 9h02, cm 0h58, fred 0h58, cftc 5h44, ceny 0h58, indeksy 0h03, ceny-krypto 0h58, snb 9h53, ici 5h01, fed 0h08, lancuch 0h08, wycena 4h15, insider HTTP 404, nastroj 5h27, stres 5h01, aukcje 5h01, swiat-dzien 0h03, swiat-dziennik 0h02, premie 0h03, dolar 0h48, jpx 5h44, rwa 1h48, krypto-dzien 0h03, krypto-dziennik 0h02, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 58 min | 2026-10-05T06:24:29+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 03 min | 2026-10-05T07:19:22+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 58 min | 2026-10-05T06:24:29+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 04 min | 2026-10-05T07:18 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 31 h 22 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 7 h 22 min | 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 7 h 22 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 5 d 7 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 5 d 7 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 4 d 7 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 65 d 7 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 4 d 7 h | 2026-09 | — |
| BLS (miesięcznie) | ✅ | 34 d 7 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 07 min | 2026-10-05T07:15:18+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 7 h 22 min | 2026-10-04 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 7 h | 2026-09-28 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 48 min | 2026-10-05T06:34:17+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 11 d 7 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 4 d 7 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 9 d 7 h | 2026-09-25 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ✅ | 2 d 7 h | 2026-10-02 | — |
| TRENDY świat — ostatnia sesja z wynikiem sygnałów | — | — | — | dziennik rusza 2026-10-05 — pierwsze wyniki po pierwszym sprawdzeniu |
| tokenizowane aktywa RWA (co 6 h) | ✅ | 1 h 48 min | 2026-10-05T05:34:41+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 6 h) | ✅ | 1 h 48 min | 2026-10-05T05:34:41+00:00 | — |
| tokenizowane aktywa — dane emitentów (co 6 h) | — | — | — | brak danych emitentów w pliku (przed pierwszym odczytem po wdrożeniu v169) |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.23%, norma (mediana 9 dni) 4.30% — ✅ odchylenie od mediany 0.92 pkt proc. (progi 2 / 5).
- Cena BTC: 86,258 vs 86,241 USD — różnica 0.02% ✅.
- Cena ETH: 2,722 vs 2,728 USD — różnica 0.19% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 9 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-05 vs 2026-10-04: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.82% (2026-09-28), norma (mediana 54 dni) +0.81% — ✅ odchylenie najnowszego dnia od normy 0.01 pkt proc. (próg 1.5), norma +0.81% (próg ±3%).
- Premie krypto: USA BTC -0.00% (przez USDC -0.01%, różnica 0.01 pkt proc.); Korea BTC +0.23% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-02) · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 1 (2026-10-02).
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-09-23: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-09-30: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.834 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-09-25: giełda -93.0 vs MOF -362.0 mld JPY.
- Tokenizowane aktywa (RWA): ℹ️ zapisów sum 3 (od 2026-10-03) — porównanie zmiany 7 dni od 8. dnia; bez bieżącej wyceny 42% wartości (11.0 mld USD, liczba produktów 28: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 15.3 mld USD ℹ️; ℹ️ 2026-10-04: zmiana zbioru produktów z odczytu własnego albo danych emitentów (0.0 → 10.6 mld USD) — skok sumy liczony bez nich; skoków sumy ponad 25% w tygodniu: brak ✅.
- Tokenizowane aktywa — odczyt własny z łańcucha: podaż 24 h: zmian ponad 50% brak ✅; wartość vs ostatnio znana: w paśmie 1/3–3× ✅; w sumach z odczytu własnego: 5 z 5 produktów, 10.6 mld USD.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Binance USDT, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
