# Kontrola strony — 04.10.2026, 15:50 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 392 ms).
- Ostatni przebieg automatu: 04.10.2026, 15:35 — sprzed 15 min; źródeł: 75, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 46 (success: 46).
- Pliki danych (wiek): etf 0h38, trendy 0h15, oecd 1h08, rynki 0h38, dzwignia 0h15, wieloryby 0h15, energia 5h34, usa-makro 5h34, bilans-usa 18h41, krypto 0h38, krypto-top10 0h28, instytucje 0h38, tic 15h34, cm 0h38, fred 0h38, cftc 0h38, ceny 0h38, indeksy 0h38, ceny-krypto 0h38, snb 4h29, ici 11h45, fed 0h25, lancuch 0h15, wycena 2h24, insider HTTP 404, nastroj 0h15, stres 5h34, aukcje 5h34, swiat-dzien 0h15, swiat-dziennik 0h14, premie 0h15, dolar 0h28, jpx 0h14, rwa 3h38, krypto-dzien 0h15, krypto-dziennik 0h14, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 0 h 38 min | 2026-10-04T13:12:10+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 15 min | 2026-10-04T13:35:08+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 0 h 38 min | 2026-10-04T13:12:10+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 16 min | 2026-10-04T13:34 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 4 d 13 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 4 d 13 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 3 d 13 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 64 d 13 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 33 d 13 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 33 d 13 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 24 min | 2026-10-04T13:26:02+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 13 h 50 min | 2026-10-03 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 13 h | 2026-09-27 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 28 min | 2026-10-04T13:22:06+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 10 d 13 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 3 d 13 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 8 d 13 h | 2026-09-25 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ✅ | 2 d 13 h | 2026-10-01 | — |
| TRENDY świat — ostatnia sesja z wynikiem sygnałów | — | — | — | dziennik rusza 2026-10-05 — pierwsze wyniki po pierwszym sprawdzeniu |
| tokenizowane aktywa RWA (co 6 h) | ✅ | 3 h 38 min | 2026-10-04T10:12:11+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 6 h) | ✅ | 3 h 38 min | 2026-10-04T10:12:11+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.23%, norma (mediana 8 dni) 4.33% — ✅ odchylenie od mediany 0.10 pkt proc. (progi 2 / 5).
- Cena BTC: 85,255 vs 85,263 USD — różnica 0.01% ✅.
- Cena ETH: 2,698 vs 2,698 USD — różnica 0.01% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 8 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-04 vs 2026-10-03: 13 par giełda/aktywo, rozbieżności > 5%: 6 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.81% (2026-09-27), norma (mediana 54 dni) +0.81% — ✅ odchylenie najnowszego dnia od normy 0.00 pkt proc. (próg 1.5), norma +0.81% (próg ±3%).
- Premie krypto: USA BTC +0.00% (przez USDC -0.01%, różnica 0.01 pkt proc.); Korea BTC +0.61% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-09-23: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-09-30: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.834 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-09-25: giełda -93.0 vs MOF -362.0 mld JPY.
- Tokenizowane aktywa (RWA): ℹ️ zapisów sum 2 (od 2026-10-03) — porównanie zmiany 7 dni od 8. dnia; bez bieżącej wyceny 58% wartości (15.3 mld USD, liczba produktów 30: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 11.2 mld USD ⚠️; ℹ️ 2026-10-04: zmiana zbioru produktów z odczytu własnego (0.0 → 6.5 mld USD) — skok sumy liczony bez nich; skoków sumy ponad 25% w tygodniu: brak ✅.
- Tokenizowane aktywa — odczyt własny z łańcucha: podaż 24 h: zmian ponad 50% brak ✅; wartość vs ostatnio znana: w paśmie 1/3–3× ✅; w sumach z odczytu własnego: 3 z 3 produktów, 6.5 mld USD.

## Uwagi
- insider.json: HTTP 404 (brak pliku)
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Binance USDT, Bitfinex USDT, Bybit USDT, KuCoin USDT, OKX USDC — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)
- tokenizowane aktywa: bez bieżącej wyceny 58% wartości (15.3 mld USD, liczba produktów 30: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 11.2 mld USD — sumy na stronie obejmują tylko wartości bieżące (próg 50%; tylko uwaga)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
