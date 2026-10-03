# Kontrola strony — 04.10.2026, 00:58 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 4 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 157 ms).
- Ostatni przebieg automatu: 04.10.2026, 00:54 — sprzed 4 min; źródeł: 73, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 56 (success: 56).
- Pliki danych (wiek): etf 0h43, trendy 0h04, oecd 4h22, rynki 0h43, dzwignia 0h04, wieloryby 0h04, energia 2h49, usa-makro 2h49, bilans-usa 3h49, krypto 0h43, krypto-top10 0h32, instytucje 0h43, tic 0h43, cm 0h43, fred 0h43, cftc 4h22, ceny 0h43, indeksy 0h43, ceny-krypto 0h43, snb 2h03, ici 8h59, fed 0h04, lancuch 0h04, wycena 2h03, insider HTTP 404, nastroj 3h29, stres 2h49, aukcje 2h49, swiat-dzien 0h04, swiat-dziennik 0h03, premie 0h04, dolar 0h33, jpx 4h41, rwa 1h20, krypto-dzien 0h04, krypto-dziennik 0h03, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 43 min | 2026-10-03T22:15:50+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 04 min | 2026-10-03T22:54:51+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 43 min | 2026-10-03T22:15:50+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 05 min | 2026-10-03T22:53 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 3 d 22 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 3 d 22 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 2 d 22 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 63 d 22 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 32 d 22 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 32 d 22 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 03 min | 2026-10-03T22:55:35+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 22 h 58 min | 2026-10-02 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ? | — | — | brak dnia danych SOPR w pliku |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 33 min | 2026-10-03T22:25:41+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 9 d 22 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 2 d 22 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 7 d 22 h | 2026-09-25 | — |
| tokenizowane aktywa RWA (co 6 h) | ✅ | 1 h 20 min | 2026-10-03T21:38:29+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 6 h) | — | — | — | brak odczytu własnego w pliku (przed pierwszym odczytem po wdrożeniu v150) |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.25%, norma (mediana 7 dni) 4.35% — ✅ odchylenie od mediany 0.10 pkt proc. (progi 2 / 5).
- Cena BTC: 84,773 vs 84,789 USD — różnica 0.02% ✅.
- Cena ETH: 2,687 vs 2,687 USD — różnica 0.02% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 7 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-03 vs 2026-10-02: 13 par giełda/aktywo, rozbieżności > 5%: 9 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia —, norma (mediana 0 dni) — — ℹ️ wspólnych dni 0 z 20 — bez oceny.
- Premie krypto: USA BTC +0.00% (przez USDC +0.00%, różnica 0.00 pkt proc.); Korea BTC +0.81% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-09-23: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-09-30: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.834 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-09-25: giełda -93.0 vs MOF -362.0 mld JPY.
- Tokenizowane aktywa (RWA): ℹ️ zapisów sum 1 (od 2026-10-03) — porównanie zmiany 7 dni od 8. dnia; bez bieżącej wyceny 83% wartości (23.2 mld USD, liczba produktów 33: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 4.7 mld USD ⚠️.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- SOPR BTC (źródło opóźnia 7 dni): brak dnia danych SOPR w pliku
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Bitfinex ETH, Bitfinex USDT, Bybit ETH, Bybit USDC, Bybit USDT — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)
- tokenizowane aktywa: bez bieżącej wyceny 83% wartości (23.2 mld USD, liczba produktów 33: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 4.7 mld USD — sumy na stronie obejmują tylko wartości bieżące (próg 50%; tylko uwaga)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
