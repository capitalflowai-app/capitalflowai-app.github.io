# Kontrola strony — 04.10.2026, 14:25 (czas polski)

**Wynik: UWAGA**

⚠️ Uwag: 5 — nic nie wymaga natychmiastowej reakcji.

- Strona główna: działa (HTTP 200, 301 ms).
- Ostatni przebieg automatu: 04.10.2026, 13:55 — sprzed 30 min; źródeł: 75, bez odpowiedzi: premie_fx; błędów zbieracza: 0.
- Słowniki języków de–ja (osobne pliki strony): 8 z 8 plików odpowiada, skróty zgodne.
- Przebiegi Actions w 24 h: 47 (pending: 1, in_progress: 1, success: 45).
- Pliki danych (wiek): etf 1h09, trendy 0h30, oecd 5h50, rynki 1h09, dzwignia 0h30, wieloryby 0h30, energia 4h09, usa-makro 4h09, bilans-usa 17h16, krypto 1h09, krypto-top10 0h58, instytucje 1h09, tic 14h09, cm 1h09, fred 1h09, cftc 5h10, ceny 1h09, indeksy 1h09, ceny-krypto 1h09, snb 3h04, ici 10h21, fed 0h30, lancuch 0h30, wycena 0h59, insider HTTP 404, nastroj 4h50, stres 4h09, aukcje 4h09, swiat-dzien 0h30, swiat-dziennik 0h29, premie 0h30, dolar 0h59, jpx 10h58, rwa 2h13, krypto-dzien 0h30, krypto-dziennik 0h29, robots.txt HTTP 200, sitemap.xml HTTP 200, google433f7c24524100a9.html HTTP 200.
- Notatki automatu: Premie krypto: kurs wymiany z poprzedniego odczytu (2026-10-02) — kurs EBC wprost niedostępny · Premie krypto: historia Korei przerwana — limit czasu (20 s); reszta w następnym przebiegu · Premie krypto: EBC: The read operation timed out — ponowienie w następnym przebiegu · poprzedni insider.json: brak na stronie (404) · brak SEC_CONTACT — insiderzy (zgłoszenia Form 4) wyłączeni · Stres: część put/call wyłączona (zmienna CBOE_ZGODA pusta).

## Świeżość źródeł

| Źródło | Status | Wiek danych | Data danych | Uwaga |
|---|---|---|---|---|
| rynki (kursy EBC, rentowności) | ✅ | 1 h 09 min | 2026-10-04T11:16:25+00:00 | — |
| wieloryby (salda portfeli giełd) | ✅ | 0 h 30 min | 2026-10-04T11:55:32+00:00 | — |
| dźwignia (giełdy pochodnych) | ✅ | 1 h 09 min | 2026-10-04T11:16:25+00:00 | — |
| premie krypto (minuty giełd) | ✅ | 0 h 31 min | 2026-10-04T11:54 | — |
| TGA (Fiscal Data, dziennie) | ✅ | 24 h 00 min | 2026-10-01 | — |
| ETF krypto (SoSoValue, dziennie) | ✅ | 24 h 00 min | 2026-10-01 – 2026-10-02 | — |
| FRED dzienne (RRPONTSYD) | ✅ | 0 h 00 min | 2026-10-02 | — |
| EIA ceny dzienne (publikowane co tydzień) | ✅ | 4 d 12 h | 2026-09-29 | — |
| CFTC (raport tygodniowy) | ✅ | 4 d 12 h | 2026-09-29 | — |
| FRED tygodniowe (WALCL) | ✅ | 3 d 12 h | 2026-09-30 | — |
| TIC (miesięcznie) | ✅ | 64 d 12 h | 2026-07 | — |
| OECD (miesięcznie) | ✅ | 33 d 12 h | 2026-08 | — |
| BLS (miesięcznie) | ✅ | 33 d 12 h | 2026-08 | — |
| szanse decyzji Fed (rynek zakładów) | ✅ | 0 h 29 min | 2026-10-04T11:56:22+00:00 | — |
| wycena BTC — MVRV, średnia cena zakupu (dziennie) | ✅ | 12 h 25 min | 2026-10-03 | — |
| SOPR BTC (źródło opóźnia 7 dni) | ✅ | 6 d 12 h | 2026-09-27 | — |
| kursy dolara Ameryki Łacińskiej (co godzinę) | ✅ | 0 h 59 min | 2026-10-04T11:26:14+00:00 | — |
| Fundusze USA: napływy (tydzień do środy, publ. w środę) | ✅ | 10 d 12 h | 2026-09-23 | — |
| Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek) | ✅ | 3 d 12 h | 2026-09-30 | — |
| Japonia: kto handluje akcjami na giełdzie (tydzień) | ✅ | 8 d 12 h | 2026-09-25 | — |
| tokenizowane aktywa RWA (co 6 h) | ✅ | 2 h 13 min | 2026-10-04T10:12:11+00:00 | — |
| tokenizowane aktywa — odczyt własny z łańcucha (co 6 h) | ✅ | 2 h 13 min | 2026-10-04T10:12:11+00:00 | — |

## Zgodność liczb (porównania krzyżowe)

- Kapitalizacja krypto, dwa źródła: różnica dziś 5.33%, norma (mediana 8 dni) 4.33% — ✅ odchylenie od mediany 1.00 pkt proc. (progi 2 / 5).
- Cena BTC: 85,276 vs 85,292 USD — różnica 0.02% ✅.
- Cena ETH: 2,701 vs 2,701 USD — różnica 0.01% ✅.
- TGA 2026-09-30: Fiscal Data 984,046 vs FRED 948,674 mln USD — różnica 3.73%, norma (mediana 8 dni) 3.05% — ✅ odchylenie od mediany 0.68 pkt proc. (progi 1).
- ETF mapy (dwa źródła, ta sama data): porównane 14 symboli, różnice > 1%: 0 ✅.
- Wieloryby 2026-10-04 vs 2026-10-03: 13 par giełda/aktywo, rozbieżności > 5%: 6 ⚠️.
- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia +0.81% (2026-09-27), norma (mediana 54 dni) +0.81% — ✅ odchylenie najnowszego dnia od normy 0.00 pkt proc. (próg 1.5), norma +0.81% (próg ±3%).
- Premie krypto: USA BTC +0.01% (przez USDC -0.01%, różnica 0.02 pkt proc.); Korea BTC +0.71% (kurs z 2026-10-02); kurs KRW/USD 2026-10-02: wprost 1348.276, w pliku rynki 1348.280 (różnica 0.000%) ✅.
- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; próg max 0.5 mln USD / 2%): IBIT ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0 · ETHA ✅ porównane sesje: 1 (2026-10-01), różnic ponad próg: 0, największa różnica 0.0 mln USD; plik emitenta do 2026-10-02, nowszych sesji na stronie: 0; czeka na porównanie: 0.
- Argentyna — dwa odczyty tych samych kursów: blue ✅ 0.00%, hurtowy ✅ 0.00%, oficjalny w banku ✅ 0.21%, MEP ✅ 0.17%, CCL ✅ 0.08%; hurtowy vs bank centralny (2026-10-02) ✅ 0.00%; główne luki: AR ✅, VE ✅, BO ✅.
- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): napływy 2026-09-23: ✅ akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup · rynek pieniężny 2026-09-30: ✅ razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie).
- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: ✅ r = 0.834 z 26 tygodni, ten sam kierunek w 24 z 24 (oba ≥ 50 mld JPY); ostatni tydzień 2026-09-25: giełda -93.0 vs MOF -362.0 mld JPY.
- Tokenizowane aktywa (RWA): ℹ️ zapisów sum 2 (od 2026-10-03) — porównanie zmiany 7 dni od 8. dnia; bez bieżącej wyceny 58% wartości (15.3 mld USD, liczba produktów 30: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 11.2 mld USD ⚠️; ℹ️ 2026-10-04: zmiana zbioru produktów z odczytu własnego (0.0 → 6.5 mld USD) — skok sumy liczony bez nich; skoków sumy ponad 25% w tygodniu: brak ✅.
- Tokenizowane aktywa — odczyt własny z łańcucha: podaż 24 h: zmian ponad 50% brak ✅; wartość vs ostatnio znana: w paśmie 1/3–3× ✅; w sumach z odczytu własnego: 3 z 3 produktów, 6.5 mld USD.

## Uwagi
- źródła bez odpowiedzi w ostatnim przebiegu: premie_fx
- insider.json: HTTP 404 (brak pliku)
- premie.json: części bez odpowiedzi: fx
- wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla Binance ETH, Binance USDT, Bitfinex USDT, Bybit USDT, KuCoin USDT, OKX USDC — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)
- tokenizowane aktywa: bez bieżącej wyceny 58% wartości (15.3 mld USD, liczba produktów 30: niezmienione co najmniej od 2026-09-27 — źródło stoi), z bieżącą wyceną 11.2 mld USD — sumy na stronie obejmują tylko wartości bieżące (próg 50%; tylko uwaga)

Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.
