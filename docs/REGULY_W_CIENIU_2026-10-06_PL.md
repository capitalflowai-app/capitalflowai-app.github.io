# Reguły „w cieniu” — rejestracja z góry (6 października 2026, przed jakimkolwiek wynikiem)

Cel (właściciel 06.10: „by projekt mógł sam się uczyć”): strona sama testuje nowe reguły sygnałów na swoich dziennikach, bez pokazywania
ich, i ujawnia tylko te, które przejdą ten sam rygorystyczny test co reguły główne. Żeby to była uczciwa nauka, a nie dopasowanie do danych:

1. **Lista kandydatów zamknięta dzisiaj** (poniżej) — przed policzeniem czegokolwiek. Nowy kandydat = nowa rejestracja z datą; wyniki
   starej listy się nie zmieniają.
2. **Te same dane i ta sama metoda co reguły główne:** wiersze dziennika (karty zapisane tak, jak były na stronie), wynik doby/sesji
   jak w dzienniku, punkty kontrolne 100 / 200 / 400 dni z sygnałem, ocena zapisywana raz i zamrażana.
3. **Surowszy próg:** poprawka Bonferroniego na wszystkie linie naraz (główne + w cieniu) i 3 oceny — krypto 7 + 4 = 11 linii, świat 7 + 3 = 10.
4. **Ujawnienie** dopiero, gdy kandydat ma werdykt „przewaga” w punkcie 200 dni (dwie oceny po drodze — 100 i 200 — obie zapisane);
   wcześniej strona mówi tylko, ile reguł jest testowanych i jak daleko do oceny.
5. Kandydaci są liczeni z głosów składników, które dziennik już zapisuje (bez nowych danych i zapytań).

## Kandydaci — krypto (dziennik `krypto-dziennik.json`, głosy p, t, e, s, h)
| nazwa | reguła | dlaczego (z góry, bez danych) |
|---|---|---|
| `pt` | ruch ceny (p) i trend (t) zgodne, oba ≠ 0 | dwa wskaźniki pędu w tę samą stronę — klasyczne podążanie za trendem |
| `ph` | ruch ceny (p) i premia kontraktów (h) zgodne | pęd ceny potwierdzony przez rynek kontraktów (głos h ma już kierunek z założenia) |
| `es` | przepływy na giełdy (e) i stablecoiny (s) zgodne | dwa pomiary przepływu kapitału w tę samą stronę (tylko BTC i ETH mają e) |
| `n3` | co najmniej 3 głosy w tę samą stronę (\|N\| ≥ 3) | silny konsensus składników |

## Kandydaci — świat (dziennik `swiat-dziennik.json`, głosy p, f, o)
| nazwa | reguła | dlaczego |
|---|---|---|
| `eq.pf` | akcje: ruch ceny (p) i przepływ do funduszu (f) zgodne | cena potwierdzona przez napływ/odpływ pieniędzy |
| `eq.fo` | akcje: przepływ do funduszu (f) i zagraniczni (o) zgodne | dwa pomiary przepływu kapitału w tę samą stronę |
| `eq.n2` | akcje: co najmniej 2 głosy w tę samą stronę | konsensus składników dla rynków akcji |

## Czego to nie robi
- Nie zmienia reguł głównych, ich kolorów ani punktów kontrolnych.
- Nie pokazuje wyników kandydatów przed punktem 200 dni (żeby nikt — także właściciel — nie wybierał reguły „po wynikach”).
- Nie przełącza automatycznie sygnałów na stronie na nową regułę — po ujawnieniu decyzja o włączeniu należy do właściciela.

## Poprawka 1 — 6 października 2026, przed jakąkolwiek oceną (świat: 1 dzień z sygnałem, krypto: 0–3 dni; żadnego punktu kontrolnego)
Po niezależnym przeglądzie (v216–v219), zanim istnieje jakikolwiek wynik do oceny:
1. **`eq.n2` usunięty.** Dla 30 z 33 funduszy akcji (bez głosu „zagraniczni”) reguła „co najmniej 2 głosy w tę samą stronę” to dokładnie
   `eq.pf` — zajmowała miejsce w poprawce Bonferroniego bez nowej informacji. Świat: 7 + 2 = 9 linii × 3 oceny.
2. **`n3` = przewaga |N| ≥ 3** (jak w tabeli wyżej; netto, nie „3 głosy”: p+ t+ s+ h− to N = 2, więc nie n3). Podpis na stronie poprawiony.
3. **Decyduje ostatnia ocena:** kandydat z przewagą w punkcie 200 dni i bez przewagi w punkcie 400 — strona pisze, że go wycofujemy.
4. **Ograniczenia, które trzeba znać:** surowe pliki dzienników (`data/*-dziennik.json`) są publiczne — oceny kandydatów (pole `cs`) da się
   w nich odczytać przed 200 dniami; strona ich nie pokazuje. Archiwum dzienne nie przechowuje jeszcze `cs` — po odtworzeniu zgubionego dziennika
   oceny kandydatów liczone są ponownie z tych samych wierszy (te same liczby; inna tylko chwila wyliczenia), a oceny starszej wersji reguł giną.

## Poprawka 2 — 7 października 2026 (tylko nazwa, reguła bez zmian; żadnego punktu kontrolnego)
Audyt „strona ↔ dane” (agenci 07.10, ustalenie T13): w krypto składnik **`t`** to na stronie **„agresywne kupno/sprzedaż”** (przewaga kupna
lub sprzedaży „po rynku” na kontraktach), nie „trend”. Opis kandydata `pt` w tabeli wyżej brzmi więc: **„ruch ceny (p) i agresywne
kupno/sprzedaż (t) zgodne, oba ≠ 0”**. Reguła, głosy, dane, progi i poprawka Bonferroniego — bez żadnej zmiany; zmienia się tylko etykieta.
