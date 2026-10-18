# Reguły „w cieniu” dla danych z fal 1–3 planu tygodnia — rejestracja z góry (17 października 2026, przed jakimkolwiek wynikiem)

Blok `TD_SH_FW` w TRENDACH (zadanie F11Z22 planu tygodnia źródeł). Obejmuje sześć nowych szeregów dziennych, które strona zbiera od fal 1–3 (wersje v382, v394, v399, v400):
płynność rynku pieniężnego USA (stopa SOFR i jej rozrzut), pozycje zagranicznych inwestorów w kontraktach na Tajwanie i w Indiach, wskaźnik put/call na Tajwanie,
indeks CSI 300 w Chinach oraz lokalne premie stablecoinu USDT w sześciu krajach. Zasada jest ta sama co przy dziale SUROWCE (`REGULY_SUROWCE_2026-10-08_PL.md`,
SHA-256 79d4eef1…fe5b) i przy nowych grupach danych (`REGULY_NOWE_GRUPY_2026-10-14_PL.md`, SHA-256 79dfa4a6…ec41e): reguła jest zapisana z góry, liczy się „w cieniu”,
niczego nie pokazuje jako sygnał kupna ani sprzedaży, a wyjście z cienia wymaga oceny na żywo. To nie jest porada inwestycyjna — to uczciwy test, czy te dane
mają jakąkolwiek wartość prognostyczną.

## Zasady (obowiązują wszystkie linie)
1. **Lista zamknięta dzisiaj** (sześć linii poniżej). Nowa linia, zmiana kierunku, progu, wejścia, funduszu wyniku albo publikacji = nowa rejestracja z nową datą
   i nowym numerem wersji bloku; oceny starej wersji się nie zmieniają. Reguły głównych sygnałów dziennych (`TD_RULES`, `TD_SH_W`, `TD_SH_CR`), blok SUROWCE
   (`TD_SH_SU`, `SUT_SHA`), blok nowych grup (`TD_SH_NG`, `NGT_SHA`), listy rynków (`TD_W_SYMS` = 44, `TR_FE`) i mapa GLOBAL pozostają bez zmian.
2. **Progi wyłącznie z istniejących stałych** reguł dziennych, nic nowego i nic dostrajanego: z z najwyżej 60 poprzednich wartości, co najmniej 40
   (`TD_LB`, `TD_MIN`); wejście „strzela” przy |z| ≥ 1 (`TD_Z1`); dolna granica rozrzutu zmian pozycji 0,25 typowego dnia (`TD_FLOOR`); przerwa w danych
   dłuższa niż 4 dni kalendarzowe = brak zmiany (`TD_GAP`). Kierunek każdej linii jest podany w tabeli i nie zmienia się po zobaczeniu danych.
3. **Horyzont wszystkich linii: jedna sesja** giełdy w Nowym Jorku (NYSE), od otwarcia do zamknięcia, pierwsza sesja, której granica karty (9:00 w Nowym
   Jorku) jest po publikacji wejścia. Wynik = zmiana ceny funduszu (otwarcie → zamknięcie) w %; wynik 0 = bez oceny. Wszystkie pięć funduszy wyników
   (INDA, EWT, MCHI, SPY, EEM) ma już dziś ceny w pliku „świat dziennie”; nowych zapytań o ceny ten blok nie dodaje.
4. **Miara skuteczności:** trafienie = znak wyniku równy kierunkowi głosu. Skuteczność linii = udział trafień w sesjach z sygnałem, z zakresem Wilsona liczonym
   na niezależnych obserwacjach (ta sama metoda co reguły główne, SUROWCE i nowe grupy: `_tdw_stat`, n_eff z grupowaniem po sesji) wobec „zwykłej sesji”
   (max(50%, udział sesji wzrostowych w okresie, udział w 250 sesjach przed parą)), obie połowy okresu po tej samej stronie progu.
5. **Poprawka na wiele testów (Bonferroni):** m = 6 linii × 3 oceny = **18**, z = 2,9913 (zakres 99,7%). Liczymy wszystkie linie, także te, które jeszcze
   nie mają danych (ostrożniej, nie łagodniej). Ta poprawka dotyczy tylko tego bloku; wcześniejsze bloki liczą swoje m osobno i zostają bez zmian.
6. **Punkty kontrolne** 100 / 200 / 400 sesji z sygnałem (`TD_W_LOOKS`); sesja wchodzi do punktu, gdy ma co najmniej 4 dni (`TD_W_SETTLE`); ocena zapisywana raz
   i zamrażana. Werdykty: przewaga / bez przewagi / odwrotnie / za mało danych (jak w SUROWCE).
7. **Kryterium wyjścia z cienia:** werdykt „przewaga” w punkcie kontrolnym 200 sesji z sygnałem. Wyjście z cienia znaczy tylko, że linia może zostać pokazana na
   stronie jako obserwacja; **ten blok niczego nie ujawnia** (strona pokazuje wyłącznie opis, datę rejestracji i licznik sesji z sygnałem do najbliższej oceny).
   Ujawnienie linii albo włączenie jej do sygnałów to osobna decyzja właściciela i osobna zmiana kodu. Decyduje ostatnia ocena: przewaga w punkcie 200 i brak
   przewagi w punkcie 400 = linię wycofujemy.
8. **Żadnego testu w próbie przed startem.** Wejścia mają dziś od jednej do 60 sesji historii, więc nie ma na czym uczciwie sprawdzić reguł wstecz. Ewentualny test
   wsteczny z dłuższych historii publicznych (np. SOFR i CSI 300) byłby osobnym dokumentem wyników, informacyjnym: nie skraca cienia, nie jest oceną w punkcie
   kontrolnym i nie może zmienić żadnej reguły z tego dokumentu.

## Linie (kierunek ustalony z góry)
| nazwa | wejście z dnia danych D | wynik | próg | kierunek |
|---|---|---|---|---|
| `fw.in.fii` | Indie: zmiana pozycji netto zagranicznych inwestorów instytucjonalnych w kontraktach terminowych na indeksy (długie − krótkie, w kontraktach), z dziennych plików giełdy w Indiach (grupa FII, `indie` → `fao`) | fundusz Indii INDA w sesji docelowej T | \|z\| ≥ 1 | +1: przybywa pozycji długich netto → wzrost, ubywa → spadek |
| `fw.tw.fn` | Tajwan: zmiana wartości pozycji netto (otwarte pozycje długie − krótkie, mln TWD) zagranicznych inwestorów w kontraktach terminowych (`chiny-tw` → `tw` → `in`, kolumna zagranicznych) | fundusz Tajwanu EWT w sesji T | \|z\| ≥ 1 | +1 |
| `fw.tw.pc` | Tajwan: zmiana (%) stosunku wolumenu opcji sprzedaży do wolumenu opcji kupna na indeks (`chiny-tw` → `tw` → `pc`) | EWT w sesji T | \|z\| ≥ 1 | **−1**: rośnie zapotrzebowanie na zabezpieczenia (więcej opcji sprzedaży) → słabsza sesja |
| `fw.cn.csi` | Chiny: zmiana (%) zamknięcia indeksu CSI 300 w sesji D (`chiny-tw` → `csi`) | fundusz Chin MCHI w sesji T | \|z\| ≥ 1 | +1: pęd — po dużym wzroście indeksu następna sesja funduszu też w górę |
| `fw.us.sofr` | USA: zmiana „ogona” stopy SOFR w dniu D, czyli różnicy między 99. percentylem transakcji a samą stopą SOFR (punkty procentowe; `plynnosc-usa` → `stopy` → `sofr`) | fundusz akcji USA SPY w sesji T | \|z\| ≥ 1 | **−1**: ogon się wydłuża (napięcie na rynku repo) → słabsza sesja |
| `fw.st.pr` | Stablecoiny: zmiana mediany lokalnych premii USDT wobec kursu referencyjnego dolara (koszyk co najmniej 4 z 6 krajów: Turcja, Brazylia, RPA, Indonezja, Indie, Meksyk; punkty procentowe; `premie-stable` → `kosz`) | fundusz rynków wschodzących EEM w sesji T | \|z\| ≥ 1 | **−1**: rośnie lokalne zapotrzebowanie na dolary w krypto (ucieczka z lokalnej waluty) → słabsza sesja funduszu rynków wschodzących |

Dlaczego te linie (z góry, bez danych): zagraniczni inwestorzy w kontraktach terminowych bywają pierwsi w ruchu kapitału do rynku (Indie, Tajwan) — mechanizm taki jak
w przepływach do funduszy z reguł głównych; wzrost zapotrzebowania na opcje sprzedaży to klasyczny miernik obaw (kierunek odwrotny); CSI 300 sprawdza pęd chińskich akcji
w następnej sesji funduszu notowanego w USA; wydłużony ogon SOFR to najprostszy sygnał napięcia płynności na rynku repo, zwykle czytany jako zapowiedź słabszych nastrojów;
wysoka premia USDT w krajach o słabej walucie to znak ucieczki do dolara. Hipotezy `fw.tw.pc`, `fw.cn.csi` i `fw.st.pr` są słabe i zapisane jako słabe.

## Jak liczymy (część rejestracji)
- **Zmiana dnia D.** Pozycje, ogon SOFR i premie (typ „przepływ”): wartość D − wartość poprzedniego dnia z wartością, w jednostkach wejścia (kontrakty, mln TWD albo punkty
  procentowe). Stosunek put/call i zamknięcie CSI (typ „ruch”): (wartość D ÷ wartość poprzedniego dnia − 1) × 100%. Poprzedni dzień dalej niż 4 dni kalendarzowe =
  brak zmiany. Pozycja netto Indii = długie − krótkie z jednego dnia pliku grupy FII (kontrakty terminowe na indeksy); ogon SOFR = 99. percentyl − stopa, oba z jednego
  dnia publikacji banku Rezerwy Federalnej w Nowym Jorku; put/call = wolumen opcji sprzedaży ÷ wolumen opcji kupna (giełda kontraktów na Tajwanie); koszyk premii = mediana
  premii krajów tej doby (co najmniej 4 kraje, jak w pliku).
- **z.** „Przepływ” (fii, fn, sofr, pr): (zmiana − średnia) ÷ max(rozrzut, 0,25 × typowy |dzień|) z najwyżej 60 poprzednich zmian (jak przepływy do funduszy reguł głównych).
  „Ruch” (pc, csi): zmiana ÷ pierwiastek ze średniego kwadratu najwyżej 60 poprzednich zmian, bez odejmowania średniej (jak ruch ceny reguł głównych). Mniej niż 40
  poprzednich zmian = brak z (karta się nie liczy). Brak to brak, nigdy zero. Stan liczności na dzień rejestracji (to nie jest wynik): SOFR 60 dni, CSI 300 49 dni,
  Indie 23 dni, put/call Tajwanu 20 dni, pozycje zagranicznych inwestorów na Tajwanie 1 dzień, premie USDT 0 dni — linie z mniejszą liczbą dni **startują same**, gdy plik
  będzie miał ich dość (licznik zaczyna się od pierwszej karty z głosem), a pliki rosną o jeden dzień na dobę roboczą.
- **Wynik** to otwarcie → zamknięcie sesji T funduszu z kolumny „wynik”, z pliku „świat dziennie”, według tego samego kalendarza sesji i tej samej zasady „pierwsza publikacja
  dnia z czasem zapisu” co reguły główne.
- **Ocena w punkcie kontrolnym** — jak w SUROWCE i w nowych grupach: zakres Wilsona przy z = 2,9913 wobec „zwykłej sesji”.

## Przyczynowość — co i kiedy wolno użyć
- **Wejście ma datę PUBLIKACJI, nie datę stanu**, i każda publikacja jest zapisana ostrożnie (zapas, nigdy zbyt wcześnie): dzień danych D z Indii, Tajwanu i Chin — dopiero po
  20:00 UTC dnia D (pliki giełd azjatyckich są gotowe wcześniej, ale kartę wolno nimi karmić najwcześniej w następnej sesji NYSE); SOFR dnia D — o 08:30 w Nowym Jorku
  następnego dnia roboczego (bank publikuje o 8:00); premie USDT dnia D — po 21:00 UTC dnia D (okno zapytań kończy się latem ok. 17:10 UTC, zimą ok. 18:10 UTC). W tygodniu ze świętem (dzień bez sesji
  NYSE między dniem danych a publikacją) — ostrożnie dzień roboczy później.
- **Dzień danych głosuje w sesji późniejszej niż D** (nigdy w sesji D): pierwsza sesja, której granica karty (9:00 w Nowym Jorku) jest po publikacji.
- **Karta jest liczona na żywo i zamrażana na granicy:** 9:00 w Nowym Jorku w dniu sesji T. Każdy przebieg automatu przed granicą liczy kartę od nowa z danych,
  które w tej chwili są w plikach strony (pole `saved_at`); po granicy karta się nie zmienia (dochodzi tylko wynik). Karta, której przed granicą nie było,
  trafia do dziennika „po czasie” — bez głosu, tylko gdy dziennik istniał przed tą granicą; wiersze „po czasie” nie wchodzą do ocen.
- **Każdy dzień danych głosuje najwyżej raz** w danej linii i symbolu, w pierwszej karcie po jego pojawieniu się w plikach strony; za stary dzień danych nie
  głosuje (pierwsza sesja, w której mógł zagłosować po publikacji, wcześniejsza niż sesja tuż przed sesją T). To granice dostępności danych, nie progi sygnału.
- **Filtry tylko na danych wcześniejszych** (lekcja v223): z, zmiana i odrzucanie braków używają wyłącznie dni ≤ D. Test: ziarna 1–30 — głos dla dnia D policzony
  z danych do D i z danych z dniami po D musi być identyczny; dziennik zapisuje wiersz raz.
- Historia „w próbie” w punktach kontrolnych nie jest używana wcale: jedynym źródłem ocen jest dziennik kart zapisanych na żywo od wdrożenia (pierwsza karta: sesja
  poniedziałek 19.10.2026).

## Gdzie to jest w kodzie (po wdrożeniu)
`zbieraj_dane.py` (wydanie v413): stałe `TD_SH_FW` i `FWT_*`, funkcje `_fwt_*`; dziennik `data/fw-dziennik.json` (kopia dzienna w `archiwum/`); pole `fw` pliku
`data/trendy.json` (tylko licznik i data rejestracji); suma SHA-256 tego dokumentu zapisana w kodzie (`FWT_SHA`). Blok czyta pliki `plynnosc-usa`, `chiny-tw`, `indie`
i `premie-stable` z tego samego przebiegu, a gdy ich w nim jeszcze nie ma — z pamięci poprzedniego przebiegu (najwyżej kilkanaście minut starszej); bez zapytań do sieci.

## Czego tu nie rejestrujemy (z powodu)
- Porty świata, eksport rolny USA według kupujących, energetyka USA (dane tygodniowe, jedna wartość na tydzień — co najmniej 40 poprzednich wartości to prawie rok).
- Wpływy i emisje długu Skarbu USA dzień po dniu (silna sezonowość dnia miesiąca: z mierzyłoby kalendarz, nie nowość), operacje repo (plik trzyma 30 dni, czyli mniej niż
  wymagane 40 poprzednich wartości, więc linia nigdy by nie ruszyła).
- DeFi, łańcuch Ethereum, Tron, dźwignia na giełdach: wynik w kryptowalutach (doba 06:00–06:00 UTC), więc wymagają osobnej rejestracji z kartami krypto.
- Dane miesięczne i kwartalne (Polska, Europa, kredyt i płynność w gospodarkach wschodzących, krzywa Chin, Shibor): za rzadkie na test dzienny.

## Czego to nie robi
- Nie zmienia żadnej istniejącej reguły ani jej wyniku, nie dodaje funduszy do `TD_W_SYMS`, nie zmienia mapy GLOBAL.
- Nie pokazuje wyników, procentów ani ocen i nie przełącza sygnałów na stronie. Nie jest rekomendacją kupna ani sprzedaży.

## Ograniczenia, które trzeba znać
- Surowy plik dziennika (`data/fw-dziennik.json`) jest publiczny — zamrożone oceny w punktach 100 i 200 da się w nim odczytać przed ujawnieniem; strona ich nie pokazuje.
- Wynik `fw.in.fii` i `fw.tw.fn` dotyczy funduszy notowanych w USA, a rynki Indii i Tajwanu zamykają się przed otwarciem NYSE: fundusz w sesji T częściowo powtarza ruch lokalny
  z sesji T. Głos powstaje jednak wyłącznie z dni ≤ D, a karta jest zamrożona o 9:00 w Nowym Jorku przed sesją T.
- Premie USDT: pierwsze karty dopiero po 40 dniach roboczych od startu zbierania (połowa grudnia 2026); kraje, w których giełda milczy, zmniejszają koszyk (co najmniej 4 kraje).
- Plik płynności USA odświeża się co ok. 2 godziny, a bank publikuje SOFR o 8:00 w Nowym Jorku, czyli tuż przed granicą karty (9:00): gdy dzień D nie zdąży do pliku przed granicą, karta
  użyje najnowszego dnia, który tam jest (dzień wcześniejszy, jeśli nie był jeszcze użyty), a dzień D zagłosuje w następnej karcie albo wcale. To reguła „najnowszy niewykorzystany dzień
  przed granicą”, wspólna dla wszystkich linii; nie zmienia kierunku ani progu, tylko opóźnia głos o sesję.
- Szereg SOFR ma tylko 60 sesji w pliku; jeśli bank zmieni układ danych, linia czeka na nowy plik (błąd części zgłasza kontrola).
