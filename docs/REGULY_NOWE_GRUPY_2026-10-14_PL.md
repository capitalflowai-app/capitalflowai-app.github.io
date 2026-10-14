# Reguły „w cieniu” dla nowych grup danych — rejestracja z góry (14 października 2026, przed jakimkolwiek wynikiem)

Blok `TD_SH_NG` w TRENDACH (zadania F1Z2 i F5Z4 planu źródeł). Obejmuje dwie nowe grupy danych: (a) fundusze ETF według regionów i sektorów oraz fundusz
Polski (plik `fundusze-przeplywy`, v342) i (b) Polskę, zapasy metali i zboża (indeksy giełdy w Warszawie, zapasy miedzi w magazynach giełdy metali
w Londynie, dzienny indeks cen zbóż). Zasada jest ta sama co przy dziale SUROWCE (`REGULY_SUROWCE_2026-10-08_PL.md`, SHA-256 79d4eef1…fe5b): reguła jest
zapisana z góry, liczy się „w cieniu”, niczego nie pokazuje jako sygnał kupna ani sprzedaży, a wyjście z cienia wymaga oceny na żywo. To nie jest
porada inwestycyjna — to uczciwy test, czy te dane mają jakąkolwiek wartość prognostyczną.

## Zasady (obowiązują wszystkie linie)
1. **Lista zamknięta dzisiaj** (sześć linii poniżej). Nowa linia, zmiana kierunku, progu, wejścia albo wyniku = nowa rejestracja z nową datą i nowym numerem
   wersji bloku; oceny starej wersji się nie zmieniają. Reguły głównych sygnałów dziennych (`TD_RULES`, `TD_SH_W`, `TD_SH_CR`), blok SUROWCE (`TD_SH_SU`,
   `SUT_SHA`), listy rynków (`TD_W_SYMS` = 44, `TR_FE`) i mapa GLOBAL pozostają bez zmian.
2. **Progi wyłącznie z istniejących stałych** reguł dziennych, nic nowego i nic dostrajanego: z z najwyżej 60 poprzednich wartości, co najmniej 40
   (`TD_LB`, `TD_MIN`); wejście „strzela” przy |z| ≥ 1 (`TD_Z1`); dolna granica rozrzutu przepływów 0,25 typowego dnia (`TD_FLOOR`); przerwa w danych
   dłuższa niż 4 dni kalendarzowe = brak zmiany (`TD_GAP`). Kierunek każdej linii jest podany w tabeli i nie zmienia się po zobaczeniu danych.
3. **Horyzont wszystkich linii: jedna sesja** giełdy w Nowym Jorku (NYSE), od otwarcia do zamknięcia, pierwsza sesja, której granica karty (9:00 w Nowym
   Jorku) jest po publikacji wejścia. Wynik = zmiana ceny funduszu (otwarcie → zamknięcie) w %; wynik 0 = bez oceny.
4. **Miara skuteczności:** trafienie = znak wyniku równy kierunkowi głosu. Skuteczność linii = udział trafień w sesjach z sygnałem, z zakresem
   Wilsona liczonym na niezależnych obserwacjach (ta sama metoda co reguły główne i SUROWCE: `_tdw_stat`, n_eff z grupowaniem po sesji) wobec „zwykłej sesji”
   (max(50%, udział sesji wzrostowych w okresie, udział w 250 sesjach przed parą)), obie połowy okresu po tej samej stronie progu.
5. **Poprawka na wiele testów (Bonferroni):** m = 6 linii × 3 oceny = **18**, z = 2,9913 (zakres 99,7%). Liczymy wszystkie linie, także te, które jeszcze
   nie mają danych (ostrożniej, nie łagodniej).
6. **Punkty kontrolne** 100 / 200 / 400 sesji z sygnałem (`TD_W_LOOKS`); sesja wchodzi do punktu, gdy ma co najmniej 4 dni (`TD_W_SETTLE`); ocena zapisywana raz
   i zamrażana. Werdykty: przewaga / bez przewagi / odwrotnie / za mało danych (jak w SUROWCE).
7. **Kryterium wyjścia z cienia:** werdykt „przewaga” w punkcie kontrolnym 200 sesji z sygnałem. Wyjście z cienia znaczy tylko, że linia może zostać pokazana na
   stronie jako obserwacja; **ten blok niczego nie ujawnia** (strona pokazuje wyłącznie opis, datę rejestracji i licznik sesji z sygnałem do najbliższej oceny).
   Ujawnienie linii albo włączenie jej do sygnałów to osobna decyzja właściciela i osobna zmiana kodu. Decyduje ostatnia ocena: przewaga w punkcie 200 i brak
   przewagi w punkcie 400 = linię wycofujemy.
8. **Test wsteczny (informacyjny, osobna sekcja poniżej)** nie skraca cienia, nie jest oceną w punkcie kontrolnym i nie może zmienić żadnej reguły z tego
   dokumentu. Reguła, która wypadła w nim słabo albo dobrze, zostaje taka sama i przechodzi tę samą ocenę na żywo.

## Linie (kierunek ustalony z góry)
| nazwa | wejście z dnia danych D | wynik | próg | kierunek |
|---|---|---|---|---|
| `ng.rg.f` | przepływ pieniędzy do funduszu regionu lub kraju: zmiana liczby jednostek × NAV z dnia D (EWC, EWW, ECH, ILF, KSA, UAE, QAT, KWT, TUR, EIS, EZA, EWS, EIDO, THD, EWM, EPHE, EWA — 17 funduszy) | ten sam fundusz w sesji docelowej T | \|z\| ≥ 1 | +1: napływ → wzrost, odpływ → spadek |
| `ng.sk.f` | przepływ do funduszu sektorowego, którego nie ma w regułach głównych (XLB — materiały, XLRE — nieruchomości, XLC — komunikacja) | ten sam fundusz w sesji T | \|z\| ≥ 1 | +1 |
| `ng.pl.f` | przepływ do funduszu Polski (EPOL) | EPOL w sesji T | \|z\| ≥ 1 | +1 |
| `ng.pl.ix` | zmiana zamknięcia indeksu giełdy w Warszawie w sesji D (WIG20, WIG, mWIG40, sWIG80; każdy indeks osobno) | EPOL w sesji T | \|z\| ≥ 1 | +1: pęd — po dużym wzroście indeksu następna sesja funduszu Polski też w górę |
| `ng.me.cu` | zmiana stanu zapasów miedzi w magazynach giełdy metali w Londynie na koniec dnia D (%) | CPER (fundusz miedzi) w sesji T | \|z\| ≥ 1 | **−1**: spadek zapasów → wzrost ceny, wzrost zapasów → spadek |
| `ng.zb.goi` | zmiana dziennego indeksu cen zbóż (GOI) w dniu D (%) | DBA (fundusz surowców rolnych) w sesji T | \|z\| ≥ 1 | +1: pęd |

Dlaczego te linie (z góry, bez danych): fundusze regionów i sektorów mają taki sam mechanizm jak fundusze reguł głównych (napływ pieniędzy podtrzymuje popyt
w następnej sesji) — pytanie, czy działa także tam, gdzie wcześniej nie liczyliśmy przepływów; Polska ma własny fundusz i własny indeks, więc sprawdzamy oba
wejścia na jednym wyniku; mniejsze zapasy metalu w magazynach są klasycznym wskaźnikiem napięcia podaży (kierunek odwrotny, bo to zapas, nie popyt); indeks
zbóż jest szeregiem o dużej bezwładności, więc pęd jest najprostszą hipotezą. Hipotezy `ng.pl.ix` i `ng.zb.goi` są słabe i zapisane jako słabe.

## Jak liczymy (część rejestracji)
- **Zmiana dnia D** = (wartość D ÷ wartość poprzedniego dnia z wartością − 1) × 100%; poprzedni dzień dalej niż 4 dni kalendarzowe = brak zmiany. Ceny i indeksy:
  iloraz zamknięć bliski ułamkowi podziału jednostek (1,5; 2; 3; 4; 5; 10 albo odwrotność, ±2%) = brak (`TD_W_SPLIT`). Zapasy metalu — bez tego filtra.
- **z ruchu** (indeksy, zapasy, indeks zbóż) = zmiana ÷ pierwiastek ze średniego kwadratu najwyżej 60 poprzednich zmian (bez odejmowania średniej);
  **z przepływu** = (przepływ − średnia) ÷ max(rozrzut, 0,25 × typowy |dzień|); przepływ liczony z wierszy wydawcy funduszu tymi samymi funkcjami co reguły
  główne (złe wiersze i podziały jednostek wykrywane tylko z dni wcześniejszych). Mniej niż 40 poprzednich wartości = brak z (karta się nie liczy). Brak to
  brak, nigdy zero.
- **Wynik** to otwarcie → zamknięcie sesji T funduszu z kolumny „wynik”. Ceny 14 funduszy, których nie ma w pliku świat dziennie (EPOL, EWW, ECH, UAE, QAT, KWT, EWS,
  EIDO, THD, EWM, EPHE, XLB, XLRE, XLC), zbiera osobny budowniczy tą samą publiczną drogą bez klucza, według tego samego kalendarza sesji i tej samej zasady „pierwsza
  publikacja dnia z czasem zapisu” co 44 rynki reguł głównych; fundusze bez serii cen dostają ją od wdrożenia kodu (linia czeka na dane i rusza sama). Wyniki sesji
  sprzed wdrożenia pochodzą z serii wstępnej i nie mają wpływu na głosy, które były zapisane wcześniej (głos powstaje przed sesją, wynik po niej).
- **Ocena w punkcie kontrolnym** — jak w SUROWCE: zakres Wilsona przy z = 2,9913 wobec „zwykłej sesji”.

## Przyczynowość — co i kiedy wolno użyć
- **Wejście ma datę PUBLIKACJI, nie datę stanu.** Dzień danych D może zagłosować w karcie, której granica jest po publikacji: pliki iShares dnia D — po
  23:59 w Nowym Jorku dnia D; pliki State Street dnia D — po 08:00 UTC następnego dnia roboczego (plik pojawia się ok. 06:00 UTC); zamknięcie sesji w Warszawie
  dnia D — po 18:00 UTC dnia D; zapasy w magazynach metali na koniec dnia D — po 06:00 UTC następnego dnia roboczego; dzienny indeks zbóż dnia D — po
  10:00 UTC następnego dnia roboczego. W tygodniu ze świętem (dzień bez sesji NYSE między dniem danych a publikacją) — ostrożnie dzień roboczy później.
- **Karta jest liczona na żywo i zamrażana na granicy:** 9:00 w Nowym Jorku w dniu sesji T. Każdy przebieg automatu przed granicą liczy kartę od nowa z danych,
  które w tej chwili są w plikach strony (pole `saved_at`); po granicy karta się nie zmienia (dochodzi tylko wynik). Karta, której przed granicą nie było,
  trafia do dziennika „po czasie” — bez głosu, tylko gdy dziennik istniał przed tą granicą; wiersze „po czasie” nie wchodzą do ocen.
- **Każdy dzień danych głosuje najwyżej raz** w danej linii i symbolu, w pierwszej karcie po jego pojawieniu się w plikach strony; za stary dzień danych nie
  głosuje (pierwsza sesja, w której mógł zagłosować po publikacji, wcześniejsza niż sesja tuż przed sesją T). To granice dostępności danych, nie progi sygnału.
- **Filtry tylko na danych wcześniejszych** (lekcja v223): z, zmiana, podział jednostek i odrzucanie złych wierszy wydawców używają wyłącznie dni ≤ D.
  Test: ziarna 1–30 — wynik dla dnia D policzony z danych do D i z danych z dniami po D musi być identyczny; dziennik zapisuje wiersz raz, a próba testu
  wstecznego jest jego podzbiorem (powstaje z tych samych kart, liczonych na przeciętych danych).
- Historia „w próbie” w punktach kontrolnych nie jest używana wcale: jedynym źródłem ocen jest dziennik kart zapisanych na żywo od wdrożenia.

## Gdzie to jest w kodzie (po wdrożeniu)
`zbieraj_dane.py` (wydanie v373): stałe `TD_SH_NG` i `NGT_*`, funkcje `_ngt_*`; dziennik `data/ng-dziennik.json` (kopia dzienna w `archiwum/`); pole `ng` pliku
`data/trendy.json` (tylko licznik i data rejestracji); suma SHA-256 tego dokumentu zapisana w kodzie (`NGT_SHA`). Dodatkowe ceny 14 funduszy (EPOL, EWW, ECH,
UAE, QAT, KWT, EWS, EIDO, THD, EWM, EPHE, XLB, XLRE, XLC) zbiera osobny budowniczy `build_ng_ceny` (`WD_NG_PX`, plik `data/ng-ceny.json`) — te fundusze nie należą do
`TD_W_SYMS`, a plik świat dziennie (gotowość, karty i wyniki reguł głównych) pozostaje bez zmian.

## Test wsteczny — plan zapisany z góry (wyniki w osobnym pliku, nie w tym dokumencie)
Wykonywany dopiero po wdrożeniu kodu i po zapisaniu sumy SHA-256 tego dokumentu; wyniki trafiają do `REGULY_NOWE_GRUPY_2026-10-14_WYNIKI_PL.md` i niczego tu nie zmieniają.
- **Dane:** wszystko, co jest publicznie dostępne bez logowania i bez obchodzenia blokad: 300 sesji NAV i jednostek funduszy z pliku `fundusze`; ok. 250 sesji
  indeksów z pliku `polska-rynek`; dłuższe historie z tych samych publicznych źródeł (indeksy giełdy w Warszawie od 1994 r., tabele roczne zapasów i cen metali
  od 2008 r., dzienny indeks zbóż od 2000 r.) — jeśli się dadzą pobrać oszczędnie i legalnie.
- **Metoda:** te same funkcje kart co kod na żywo, uruchamiane dla każdej sesji historycznej na danych przyciętych do dnia poprzedzającego (próba ⊆ dziennik);
  te same progi, kierunki, publikacje i miara skuteczności. Wynik historyczny jest przybliżeniem (brak otwarć w historii): fundusze — zmiana NAV w sesji T;
  `ng.pl.ix` — zmiana NAV funduszu EPOL albo własna następna sesja indeksu; `ng.me.cu` — zmiana ceny miedzi na giełdzie w Londynie; `ng.zb.goi` — zmiana własnego indeksu
  w następnym dniu. Każde przybliżenie zostanie nazwane w wynikach.
- **Przyczynowość:** ziarna 1–30 (losowe przycięcia danych) muszą dać identyczne głosy; brak podglądania przyszłości jest warunkiem uznania wyniku.
- **Raportujemy:** liczba sesji z sygnałem, trafienia, zakres 95% i zakres przy z = 2,9913, połowy okresu, „zwykła sesja”; bez wyboru najlepszego podzbioru,
  bez zmiany progów po obejrzeniu wyniku.

## Czego to nie robi
- Nie zmienia żadnej istniejącej reguły ani jej wyniku, nie dodaje funduszy do `TD_W_SYMS`, nie zmienia mapy GLOBAL.
- Nie pokazuje wyników, procentów ani ocen i nie przełącza sygnałów na stronie. Nie jest rekomendacją kupna ani sprzedaży.
- Nie obejmuje zadłużenia wobec nierezydentów w polskich obligacjach dzień po dniu (plan F5Z4): dziennego szeregu w danych strony jeszcze nie ma, więc linii
  nie rejestrujemy; osobna rejestracja po pojawieniu się szeregu.

## Ograniczenia, które trzeba znać
- Surowy plik dziennika (`data/ng-dziennik.json`) jest publiczny — zamrożone oceny w punktach 100 i 200 da się w nim odczytać przed ujawnieniem; strona ich nie pokazuje.
- Fundusze mniejszych krajów (QAT, KWT, KSA, TUR, EIS) mają przepływy rzadkie (przez tygodnie bez zmiany liczby jednostek); reguła `_td_z` daje wtedy ±2 przy każdym
  niezerowym dniu — to znane zachowanie reguł głównych, nie wyjątek tego bloku.
- Cena EPOL jest notowana w Nowym Jorku (13:30–20:00 UTC), a indeksy w Warszawie zamykają się o ok. 15:05 UTC: sesja T funduszu Polski nakłada się częściowo na sesję
  w Warszawie dnia T. Wejście `ng.pl.ix` pochodzi jednak z sesji D (nie T), a karta jest zamrożona o 9:00 w Nowym Jorku przed sesją T, więc żadna dana z dnia T nie wchodzi do głosu.
