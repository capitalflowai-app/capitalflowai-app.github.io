# Kontrola strony — 04.10.2026, 15:18 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 3 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 264 ms).
- Ostatni przebieg automatu: 04.10.2026, 14:52 — sprzed 26 min; źródeł: 75, bez odpowiedzi: żadne; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 47 (pending: 1, in_progress: 1, success: 45).
- Pliki danych (wiek): etf 1h02, trendy 0h26, oecd 0h36, rynki 1h02, dzwignia 0h26, wieloryby 0h26, energia 5h02, usa-makro 5h02, bilans-usa 18h09, krypto 1h02, krypto-top10 0h53, instytucje 1h02, tic 15h02, cm 1h02, fred 1h02, cftc 6h03, ceny 1h02, indeksy 1h02, ceny-krypto 1h02, snb 3h57, ici 11h14, fed 0h36, lancuch 0h36, wycena 1h52, insider HTTP 404, nastroj 5h43, stres 5h02, aukcje 5h02, swiat-dzien 0h26, swiat-dziennik 0h25, premie 0h26, dolar 0h53, jpx 11h51, rwa 3h06, krypto-dzien 0h26, krypto-dziennik 0h25, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 1 h 02 min | 2026-10-04T12:15:40+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 26 min | 2026-10-04T12:52:34+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 1 h 02 min | 2026-10-04T12:15:40+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 27 min | 2026-10-04T12:51 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 4 d 13 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 4 d 13 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 3 d 13 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 64 d 13 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 33 d 13 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 33 d 13 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 35 min | 2026-10-04T12:42:56+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 13 h 18 min | 2026-10-03 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 13 h | 2026-09-27 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 53 min | 2026-10-04T12:25:27+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 10 d 13 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 3 d 13 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 8 d 13 h | 2026-09-25 | — |
| TRENDY krypto — ostatni dzień z wynikiem sygnałów | ✅ | 2 d 13 h | 2026-10-01 | — |
| TRENDY świat — ostatnia sesja z wynikiem sygnałów | — | — | — | dziennik rusza 2026-10-05 — pierwsze wyniki po pierwszym sprawdzeniu |
| tokenizowane aktywa RWA (co 6 h) | ✅ | 3 h 06 min | 2026-10-04T10:12:11+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 6 h) | ✅ | 3 h 06 min | 2026-10-04T10:12:11+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 4.23%, norma (mediana 8 dni) 4.33% — ✅ odchylenie od mediany 0.10 pkt proc. (progi 2 / 5).
- Cena BTC: 85,163 vs 85,147 USD — różnica 0.02% ✅.
- Cena ETH: 2,697 vs 2,698 USD — różnica 0.01% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 8 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-04 vs 2026-10-03: 13 par giełda/aktywo, rozbieżności > 5%: 6 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.81% (2026-09-27), norma (mediana 54 dni) +0.81% — ✅ odchylenie najnowszego dnia od normy 0.00 pkt proc. (próg 1.5), norma +0.81% (próg ±3%).
- Premie krypto: USA BTC +0.00% (przez USDC -0.01%, różnica 0.01 pkt proc.); Korea BTC +0.69% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
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
