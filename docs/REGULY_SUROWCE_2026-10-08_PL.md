# Reguły „w cieniu” działu SUROWCE — rejestracja z góry (8 października 2026, przed jakimkolwiek wynikiem)

Blok `TD_SH_SU` w TRENDACH (dział SUROWCE, etap 7; plan `checkpoints/PLAN_SUROWCE_2026-10-07_PL.md`, sekcja „TRENDY”).
Cel: sprawdzić uczciwie, czy ruchy surowców pomagają przewidzieć rynki. Strona testuje reguły na własnym dzienniku, bez pokazywania
wyników, i ujawnia tylko regułę, która przejdzie surowy test. Żeby to była nauka, a nie dopasowanie do danych:

1. **Lista zamknięta dzisiaj** (cztery linie poniżej), zanim policzono jakikolwiek wynik. Nowa linia albo zmiana linii = nowa rejestracja
   z nową datą i nową wersją bloku; wyniki starej wersji się nie zmieniają.
2. **Żadnego wyniku z historii.** Trafności tych linii nie liczymy na danych sprzed wdrożenia — ani przed zapisaniem tego dokumentu, ani po nim
   (nie ma testu „w próbie” dla tego bloku). Jedyne źródło ocen to dziennik kart zapisanych na żywo od wdrożenia.
3. **Progi wyłącznie z istniejących stałych** reguł dziennych (nic nowego, nic dostrajanego): okno 60 poprzednich wartości, co najmniej 40
   (`TD_LB`, `TD_MIN`); wejście „strzela” przy |z| ≥ 1 (`TD_Z1`), „mocno” przy |z| ≥ 2 (`TD_Z2`); dolna granica rozrzutu przepływów 0,25
   typowego dnia (`TD_FLOOR`); przerwa w danych dłuższa niż 4 dni kalendarzowe = brak zmiany (`TD_GAP`).
4. **Własna poprawka na wiele testów (Bonferroni):** m = 4 linie × 3 oceny = **12**, z = 2,8653 (zakres 99,6%). Liczymy wszystkie 4 linie,
   także te, które jeszcze nie mają danych (ostrożniej, nie łagodniej).
5. **Punkty kontrolne** 100 / 200 / 400 dni z sygnałem (`TD_W_LOOKS`); ocena zapisywana raz i zamrażana.
6. **Ujawnienie** linii na stronie dopiero z werdyktem „przewaga” w punkcie 200 (`TD_SH_JAWNE`). Decyduje ostatnia ocena: przewaga w punkcie 200
   i brak przewagi w punkcie 400 = strona pisze, że regułę wycofujemy. Włączenie reguły do sygnałów — decyzja właściciela, nie automat.

## Linie (kierunek ustalony z góry)
| nazwa | wejście z dnia danych D | wynik | próg | kierunek |
|---|---|---|---|---|
| `su.cm.p` | ruch ceny funduszu surowcowego (GSG, CMDY, COMT, DBC, USO, CPER, DBA): zamknięcie D wobec poprzedniego zamknięcia | ten sam fundusz w sesji docelowej T, od otwarcia do zamknięcia NYSE | \|z\| ≥ 1 | +1 (ten sam kierunek) |
| `su.cm.f` | przepływ do funduszu (GSG, CMDY, COMT): zmiana liczby jednostek × NAV z dnia D (jak przepływy funduszy reguł głównych) | cena tego funduszu w sesji T, od otwarcia do zamknięcia | \|z\| ≥ 1 | +1 |
| `su.eq.cu` | zmiana stosunku miedź/złoto w dniu D (miedź: wycena dnia; złoto: cena LBMA PM wyliczona z archiwum funduszu GLD) | fundusze akcji (rodzina eq) w sesji T, od otwarcia do zamknięcia | \|z\| ≥ 1 | +1: miedź/złoto w górę = akcje w górę |
| `su.cr.au` | zmiana ceny złota LBMA PM w dniu D | bitcoin w oknie 06:00 UTC doby D′+1 → 06:00 UTC doby D′+2 (D′ = doba karty krypto) | \|z\| ≥ 2 | +1 — słaba hipoteza „ochrony przed słabnącym pieniądzem”, zapisana wprost jako słaba |

Dlaczego te linie (z góry, bez danych): fundusze surowcowe mają pęd ceny i przepływów jak fundusze akcji (`eq.p`, `eq.f`); miedź/złoto to
najprostszy wskaźnik apetytu na ryzyko; złoto i bitcoin bywają opisywane jako ochrona przed słabnącym pieniądzem.

## Jak liczymy (szczegóły, które też są częścią rejestracji)
- **Zmiana dnia D** = (wartość D ÷ wartość poprzedniego dnia z wartością − 1) × 100%; poprzedni dzień dalej niż 4 dni kalendarzowe = brak
  zmiany. Stosunek miedź/złoto tylko z dni, w których są obie ceny. Ceny funduszy: iloraz zamknięć bliski ułamkowi podziału jednostek
  (1,5; 2; 3; 4; 5; 10 albo odwrotność, ±2%) = brak (`TD_W_SPLIT`, jak reguły świata).
- **z ruchu ceny** (cm.p, eq.cu, cr.au) = zmiana ÷ pierwiastek ze średniego kwadratu najwyżej 60 poprzednich zmian (bez odejmowania średniej —
  jak wejście „ruch ceny” reguł głównych); **z przepływu** (cm.f) = (przepływ − średnia) ÷ max(rozrzut, 0,25 × typowy |dzień|).
  Mniej niż 40 poprzednich wartości = brak z (karta się nie liczy). Brak to brak, nigdy zero.
- **Wynik:** cm.p, cm.f — otwarcie→zamknięcie tego funduszu w sesji T; eq.cu — średnia otwarcie→zamknięcie wszystkich rynków rodziny „eq”
  (33 rynki świata z reguł głównych, bez obligacji i metali), gdy mają ją wszystkie, a po 48 godzinach — gdy ma ją co najmniej 90% z nich
  (`WD_MIN_SHARE`); cr.au — bitcoin w oknie 06:00 → 06:00 UTC, jak krypto. Wynik 0 = bez oceny. Trafienie = znak wyniku równy kierunkowi głosu.
- **Ocena w punkcie kontrolnym** — ta sama metoda co linie główne: zakres Wilsona przy z = 2,8653 wobec „zwykłej sesji/doby”
  (świat: max(50%, udział sesji wzrostowych w okresie, udział w 250 sesjach przed parą); krypto: max(50%, udział dób wzrostowych w okresie)),
  liczba niezależnych obserwacji jak w liniach głównych (świat: najwyżej liczba sesji z sygnałem — mniej, gdy wyniki kilku funduszy tej samej
  sesji są ze sobą zgodne; krypto: doby z sygnałem), obie połowy okresu po tej samej stronie progu. Werdykty: przewaga / bez przewagi /
  odwrotnie / za mało danych. Sesja (doba) wchodzi do punktu kontrolnego, gdy ma co najmniej 4 dni (świat) albo 5 dni (krypto).

## Przyczynowość — co i kiedy wolno użyć
- **Wejście ma datę PUBLIKACJI, nie datę stanu.** Dzień danych D może zagłosować tylko w karcie, której granica jest po publikacji:
  zamknięcie dnia i wycena dnia D — po 16:00 w Nowym Jorku dnia D; LBMA PM dnia D — po 15:00 UTC dnia D; pliki wydawców funduszy (NAV,
  liczba jednostek) dnia D — po 23:59 w Nowym Jorku dnia D; gdyby do bloku weszły kiedyś raporty tygodniowe (nowa rejestracja): CFTC i ICE
  (stan na wtorek) — od piątku 15:30 w Nowym Jorku, czyli najwcześniej w następnej sesji (zwykle poniedziałek); EIA WPSR (stan na piątek) —
  od środy 10:30 w Nowym Jorku, czyli najwcześniej w czwartek; w tygodniu ze świętem (dzień bez sesji między stanem a publikacją) — ostrożnie
  dzień roboczy później; dane miesięczne — od dnia publikacji z kalendarza.
- **Karta jest liczona na żywo i zamrażana na granicy:** świat — 09:00 w Nowym Jorku w dniu sesji T; krypto — 05:30 UTC doby po dobie karty.
  Każdy przebieg automatu przed granicą liczy kartę od nowa z danych, które w tej chwili są w plikach strony (pole `saved_at` = chwila
  wyliczenia); po granicy karta się nie zmienia (dochodzi tylko wynik). Gdy przed granicą karty nie było (przerwa automatu albo dane,
  które przyszły dopiero po granicy), wiersz „po czasie” — bez głosu — zapisuje pierwszy przebieg automatu po granicy, jeśli ma już dane
  do tej karty, wypada przed końcem karty (świat: 16:15 w Nowym Jorku, w sesji skróconej 13:15; krypto: 06:00 UTC dwie doby po dobie karty)
  i dziennik istniał już przed granicą. Bez takiego przebiegu wiersza „po czasie” nie ma. Wiersze „po czasie” nie głosują i nie wchodzą
  do ocen; ich dzień danych może zagłosować w następnej karcie.
- **Każdy dzień danych głosuje najwyżej raz** w danej linii: w pierwszej karcie po jego pojawieniu się w plikach strony (najnowszy dzień,
  którego wcześniejsza karta jeszcze nie użyła). Za stary dzień danych nie głosuje: świat — gdy pierwsza sesja, w której mógł zagłosować
  po publikacji, jest wcześniejsza niż sesja tuż przed sesją T (dla zamknięć dnia i ceny złota: dzień danych najwyżej 2 sesje przed T);
  krypto — gdy pierwsza doba, w której mógł zagłosować, jest więcej niż 3 doby przed dobą karty (to granice dostępności danych, nie progi
  sygnału). Dzisiejsze opóźnienia źródła: cena złota z archiwum funduszu GLD dla dnia D bywa w plikach strony dopiero ok. 13:00 UTC dnia
  D+1, więc latem złoto z D głosuje zwykle w sesji D+2 (zimą D+1), a w krypto — w karcie doby D+1 (okno 06:00 D+2 → 06:00 D+3).
- **Filtry tylko na danych wcześniejszych** (lekcja v223): z, zmiana, podział jednostek i odrzucanie złych wierszy plików wydawców
  (mediana aktywów 10 dni PRZED wierszem) używają wyłącznie dni ≤ D. Test: ziarna 1–30 — wynik dla dnia D policzony z danych do D
  i z danych z dniami po D musi być identyczny.
- Historia „w próbie” nie jest liczona wcale (punkt 2).

## Linie su.cm.p i su.cm.f — decyzja o danych
Funduszy surowcowych (GSG, CMDY, COMT, DBC, USO, CPER, DBA) nie ma dziś w danych strony (sprawdzone 08.10.2026: ani w pliku cen, ani
w pliku funduszy, ani w pliku dziennym świata). Decyzja: **obie linie są zarejestrowane teraz, z regułą zapisaną w kodzie, i startują same,
gdy dane będą** — ich licznik zaczyna się od pierwszej karty z danymi. Zbieranie tych danych to osobny, późniejszy krok (dane, nie reguły):
otwarcia i zamknięcia 7 funduszy w części `px`, a NAV i liczba jednostek GSG, CMDY i COMT w części `fl` pliku dziennego świata (ten sam
kształt wierszy co 44 rynki reguł głównych, z czasem zapisu). Ten krok nie może zmienić `TR_FE`, `TD_W_SYMS` (44), mapy GLOBAL ani
żadnej linii już zarejestrowanej. Do tego czasu w poprawce Bonferroniego liczymy wszystkie 4 linie (punkt 4).
Linia su.eq.cu potrzebuje 40 poprzednich zmian miedzi — historia dziennej wyceny miedzi zaczyna się 07.10.2026, więc pierwsze karty
z głosem będą ok. grudnia 2026. Linia su.cr.au korzysta z ceny złota w pliku cen strony, który trzyma 90 ostatnich sesji
(w pliku z 08.10.2026: od 29.05.2026, czyli 89 zmian — więcej niż wymagane 40), więc rusza od razu.

## Strona do czasu werdyktu
Tylko krótki opis („sprawdzamy, czy ruchy surowców pomagają przewidzieć rynki”), data rejestracji, licznik dni z sygnałem każdej linii
(do najbliższej oceny) i stan dziennika z datą. Bez wyników, bez procentów, bez ocen przed punktem 200.

## Gdzie to jest w kodzie
`zbieraj_dane.py` (wydanie v303): stałe `TD_SH_SU` i `SUT_*`, funkcje `_sut_*`; dziennik `data/surowce-dziennik.json`; pole `su` pliku
`data/trendy.json` (tylko licznik i data rejestracji — oceny dopiero po ujawnieniu); suma SHA-256 tego dokumentu zapisana w kodzie (`SUT_SHA`).

## Czego to nie robi
- Nie zmienia reguł głównych ani reguł „w cieniu” z 06.10 (`TD_SH_W`, `TD_SH_CR`), ich progów (`TD_W_ZLS`, `TD_CR_ZLS`), list rynków
  (`TD_W_SYMS` = 44, `TR_FE`) ani mapy GLOBAL.
- Nie pokazuje wyników przed punktem 200 i nie przełącza sygnałów na stronie.
- Wiersze tygodniowe TRENDÓW (opis, nie sygnały): do 4 rynków CFTC (`TR_CS`: złoto, srebro, miedź, WTI) świadomie dochodzi 6 wierszy
  pozycji funduszy zarządzających z części „pozycje” pliku surowców: ropa Brent (ICE), gaz ziemny (NYMEX), kukurydza, pszenica, soja (CBOT),
  platyna (NYMEX) — reguła tygodniowa bez zmian, przybywa tylko wierszy.

## Ograniczenia, które trzeba znać
- Surowy plik dziennika (`data/surowce-dziennik.json`) jest publiczny — zamrożone oceny w punktach 100 i 200 da się w nim odczytać przed
  ujawnieniem; strona ich nie pokazuje.
- Kopia dzienna dziennika w archiwum (`archiwum/surowce-dziennik.csv`) przechowuje wiersze kart; po odtworzeniu zgubionego dziennika oceny
  liczone są ponownie z tych samych wierszy (te same liczby, inna tylko chwila wyliczenia).
- Wycena miedzi pochodzi z funduszu fizycznej miedzi (cena metalu w jego wycenie dziennej), a cena złota jest wyliczona z archiwum funduszu
  GLD — to przybliżenia „zamknięcia dnia” i „LBMA PM”, opisane jako takie.

## Poprawki opisu przed wdrożeniem (08.10.2026)
Dokument zapisano i zahashowano przed kodem. Po przeglądzie kodu, nadal przed wdrożeniem i przed jakimkolwiek wynikiem (nie policzono żadnej
karty ani oceny na danych), poprawiono dwa zdania, które nie zgadzały się z kodem: historia złota w linii su.cr.au (90 sesji w pliku cen,
a nie „od 2025 r.”) i opis zapisu wiersza „po czasie” (zapisuje go pierwszy przebieg po granicy). Lista linii, kierunki, progi, poprawka
na wiele testów, punkty kontrolne i zasady ujawnienia — bez zmian. Suma SHA-256 w kodzie (`SUT_SHA`) dotyczy tej wersji dokumentu.
