#!/usr/bin/env python3
"""Codzienna kontrola strony — uruchamiana w GitHub Actions (ma dostęp do sieci), nie w chmurze Claude (tam brak dostępu do strony).
Sprawdza: stronę główną, plik stanu automatu (meta.json: wiek, błędy, źródła bez odpowiedzi), wiek plików danych, pliki dla wyszukiwarek,
przebiegi Actions z 24 h; v115 (część C zadania z 26.09.2026): świeżość źródeł wg kategorii (godzinowe / dzienne w dni robocze / tygodniowe
/ miesięczne; żółte po przekroczeniu progu, czerwone po 2×), błędy zbieracza w 3 kolejnych uruchomieniach = czerwone (kontrola/historia.json),
zgodność liczb (kapitalizacja krypto CoinGecko vs CoinPaprika — różnica dnia wobec mediany 30 dni w kontrola/zgodnosc.csv; ceny BTC/ETH;
TGA Fiscal Data vs FRED; wieloryby: zmiana salda vs przelewy z archiwum).
Zapisuje `kontrola/ostatnia.md` (po polsku: nagłówek i linia „Wynik:” w stałym formacie — czyta je zadanie w chmurze; potem werdykt
✅/⚠️/❌ i tabela źródło → status → wiek danych → uwaga), `kontrola/ostatnia.json`, `kontrola/zgodnosc.csv`, `kontrola/historia.json`.
Kod wyjścia 1 = BŁĄD (GitHub wysyła właścicielowi e-mail o nieudanym przebiegu). Bez kluczy, tylko odczyt. Python 3.12, sama biblioteka standardowa.
Uwaga: komunikat commita bota zawiera „[skip ci]” — GitHub pomija wtedy przebiegi wyzwalane pushem (dlatego commit dodający ten plik
nie może mieć tego napisu w treści — pierwszy przebieg nie ruszył właśnie z tego powodu).
v133: tokenizowane aktywa RWA (data/rwa.json): świeżość listy osobnym wierszem (próg 12 h; najwyżej ⚠️) i porównania z pliku strony bez zapytań — własna zmiana 7 dni vs podana przez źródło, produkty spoza głównej listy, skok sumy dzień do dnia (najwyżej ⚠️).
v137: Japonia — kto handluje akcjami na giełdzie (data/jpx.json): świeżość wg kalendarza publikacji źródła (4. dzień roboczy następnego tygodnia, święta w Japonii; najwyżej ⚠️) i zgodność kierunku zagranicy z danymi tygodniowymi MOF (z plików strony, bez zapytań; najwyżej ⚠️).
v136: kursy dolara Ameryki Łacińskiej (data/dolar.json) — świeżość osobnym wierszem (najwyżej ⚠️), dwa odczyty kursów Argentyny z pliku i kurs hurtowy vs API banku centralnego Argentyny (1 zapytanie); tylko uwagi, nigdy BŁĄD.
v130: ETF krypto u źródła — przepływy IBIT i ETHA na stronie vs wyliczenie z plików emitenta (liczba jednostek × NAV); zapis sesji ze strony w `kontrola/etf-emitent.csv`.
v134: fundusze USA (data/ici.json) — świeżość części osobnymi wierszami (najwyżej ⚠️; lista SWIEZOSC bez zmian), tożsamości sum ostatniego
tygodnia w pliku strony i poprawki wydawcy (informacja); bez sieci, nigdy BŁĄD.
v135: fundusze rynku pieniężnego (ta sama data/ici.json, część mm) — osobny wiersz świeżości (próg 10 dni, najwyżej ⚠️) i sumy ostatniego tygodnia.
v150: tokenizowane aktywa — odczyt własny z łańcucha (blok onchain w data/rwa.json): wiersz świeżości (próg 12 h, najwyżej ⚠️; wyłącznik
RWA_CHAIN_OFF = „—”) i porównania bez sieci — podaż produktu dzień do dnia (> 50% = ⚠️), wartość z łańcucha vs ostatnio znana wartość
źródła v133 (poza 1/3–3× = ⚠️), produkty bez pełnego odczytu, odczyt niepełny; skok sumy RWA w dniu zmiany zbioru produktów z odczytu
własnego liczony bez nich (zmiana zakresu, nie rynku)."""
import csv
import datetime as dt
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

SITE = os.environ.get('SITE_URL', 'https://capitalflowai-app.github.io').rstrip('/')
REPO = os.environ.get('GITHUB_REPOSITORY', 'capitalflowai-app/capitalflowai-app.github.io')
TOKEN = os.environ.get('GITHUB_TOKEN', '')          # tylko do odczytu listy przebiegów (API publiczne działa też bez niego)
OUT_DIR = os.environ.get('KONTROLA_DIR', 'kontrola')
ARCH_DIR = os.environ.get('KONTROLA_ARCH', 'archiwum')   # archiwum własne z tego samego checkoutu (v113)
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
PLIKI = ['meta', 'etf', 'trendy', 'oecd', 'rynki', 'dzwignia', 'wieloryby', 'energia', 'surowce', 'surowce-hist', 'usa-makro', 'bilans-usa', 'krypto', 'krypto-top10', 'cmc', 'instytucje', 'tic', 'cm', 'fred', 'cftc', 'ceny', 'indeksy', 'ceny-krypto', 'snb', 'ici', 'fed', 'lancuch', 'wycena', 'insider', 'nastroj', 'stres', 'aukcje', 'swiat-dzien', 'swiat-dziennik', 'surowce-dziennik', 'premie', 'dolar', 'stopy', 'jpx', 'rwa', 'zloto-krypto', 'szlaki', 'krypto-dzien', 'krypto-dziennik']
LIMIT_MIN = {'stopy': 24 * 60, 'meta': 90, 'etf': 180, 'trendy': 180, 'oecd': 24 * 60, 'rynki': 180, 'dzwignia': 180, 'wieloryby': 90, 'energia': 24 * 60, 'surowce': 24 * 60, 'surowce-hist': 48 * 60,
             'usa-makro': 24 * 60, 'bilans-usa': 48 * 60, 'krypto': 180, 'krypto-top10': 180, 'cmc': 90, 'instytucje': 180, 'tic': 48 * 60, 'cm': 180, 'fred': 180, 'cftc': 24 * 60, 'ceny': 180, 'indeksy': 24 * 60, 'ceny-krypto': 180, 'snb': 24 * 60, 'ici': 24 * 60, 'fed': 90, 'lancuch': 90, 'wycena': 8 * 60, 'insider': 48 * 60, 'nastroj': 12 * 60, 'stres': 24 * 60, 'aukcje': 24 * 60, 'swiat-dzien': 180, 'swiat-dziennik': 180, 'surowce-dziennik': 180, 'premie': 90, 'dolar': 180, 'jpx': 26 * 60, 'rwa': 12 * 60, 'zloto-krypto': 90, 'szlaki': 26 * 60, 'krypto-dzien': 180, 'krypto-dziennik': 180}
PLIKI.insert(PLIKI.index('krypto-dzien'), 'polska')   # v304: Polska (data/polska.json) — przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['polska'] = 48 * 60   # v304: plik zmienia się przy każdym udanym pobraniu części (gaz i prąd z giełdy codziennie, także w weekend)
PLIKI.insert(PLIKI.index('krypto-dzien'), 'surowce-raporty')   # v320: raporty miesięczne o surowcach — przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['surowce-raporty'] = 8 * 24 * 60   # v320: każde źródło sprawdzane co najmniej raz na 7 dni (dane miesięczne) — starszy plik = automat go nie dotyka
# v327 (KON-08): 16 plików zbieracza dotąd bez kontroli wieku. Limit wg rytmu zapisu w main() zbieracza (fresh(poprzedni, C) albo co przebieg) z tym
# samym zapasem co pliki o tym rytmie: co przebieg i co godzinę (C ≤ 60 min) → 3 h (jak swiat-dzien, krypto); co 6 h i co 12 h → doba (jak oecd, cftc,
# snb); raz na dobę → 2 doby (jak tic). Test wsteczny: migawki audytu m1–m8, migawka na żywo 10.10 i 121 raportów kontroli 26.09–10.10 (wiek ostatniego
# przebiegu i pamięć awarii części) — 0 uwag bez awarii; uwaga dopiero, gdy część zbieracza nie działa dłużej niż (limit − C).
PLIKI_V327 = (('dzis', 180), ('fundusze', 180), ('obce', 180), ('krypto-top10-logo', 180), ('eer', 24 * 60), ('meksyk', 24 * 60), ('kursy', 24 * 60),
              ('bis', 48 * 60), ('rezerwy', 48 * 60), ('cofer', 48 * 60), ('bilans', 48 * 60), ('safe', 48 * 60), ('ue', 48 * 60), ('kanada', 48 * 60),
              ('korea', 48 * 60), ('spw', 48 * 60))
for _n, _m in PLIKI_V327:
    PLIKI.insert(PLIKI.index('krypto-dzien'), _n)   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
    LIMIT_MIN[_n] = _m
PLIKI_BEZ = {}   # v327 (KON-08): plik zbieracza świadomie bez kontroli wieku — {nazwa: powód}; dziś żaden (test: każdy zapisywany plik jest w PLIKI albo tu)
# v337 (F2Z4): MFW PIP — kto trzyma czyje papiery (data/pip.json, półrocznie). Wiek PLIKU jak bilans (zapis raz na dobę → limit 2 doby). Wiek
# OKRESU: półrocze starsze niż PIP_OKRES_MIES miesięcy od jego końca = ⚠️ (MFW publikuje półrocze z opóźnieniem ok. 9 mies.; 10.10.2026: 2025-S2,
# a 2025-S1 miałoby już 15,3 mies.). Zgodność: suma posiadaczy (gospodarki + rezerwy banków centralnych i organizacje + nieprzypisane) ≈ wiersz
# świata — różnica ponad max(PIP_SUMA_TOL_MLN, PIP_SUMA_TOL_PCT % świata) = ⚠️ (10.10.2026: Polska 193,3 = 193,3; Polska jako inwestor 94,3 = 94,3).
# Najwyżej ⚠️, nigdy ❌ ani BŁĄD. Wiersze w tabeli świeżości (lista SWIEZOSC bez zmian).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'pip')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['pip'] = 48 * 60
# v342 (F1Z2): fundusze ETF w USA (data/fundusze.json, część 'f': 20 funduszy State Street, 74 iShares — lista oczekiwanych w polu 'lista') i plik
# strony data/fundusze-przeplywy.json (wiek pliku: zapis co przebieg → limit 3 h jak plik fundusze). Wiersze (lista SWIEZOSC bez zmian), najwyżej uwaga (⚠):
# (1) fundusze z ostatnią sesją: dla każdego wydawcy oczekiwana sesja = ostatnia sesja NYSE S, której dane powinny już być w pliku (model
#     publikacji z zapasem: iShares — S + 1 dzień 14:00 UTC (zestawienie z nowym dniem zaobserwowane 00:02–12:03 UTC, 05–09.10.2026);
#     State Street — następna sesja po S, 12:00 UTC (pliki publikowane w dni robocze ok. 04:55 UTC, pobierane po publikacji)); fundusz ma
#     ostatnią sesję, gdy jego najnowszy dzień (bez powtórzonych wierszy — dzień wolny w pliku złota) ≥ oczekiwanej sesji. Mniej niż FU_UDZIAL %
#     funduszy z listy = uwaga (⚠). Fundusz bez danych FU_SESJE sesji (albo bez historii) = uwaga (⚠) z nazwą — brak liczony od OSTATNIEJ ZAMKNIĘTEJ
#     sesji NYSE (_fu_ost: dzień sesji po FU_ZAMK_H UTC), nie od oczekiwanej (recenzja v342: od oczekiwanej ostrzeżenie przychodziło dopiero przy
#     ok. 4 brakujących sesjach); zdrowy fundusz o 06:20 UTC ma brak 0–1 (sesja z poprzedniego dnia jeszcze w drodze). Test wsteczny (ws53/v342-fundusze/bt/bt_sesje.py i
#     bt_kontrola.py): 47 funduszy (37 z migawki 10.10.2026 i 10 nagranych) × 234 sesje NYSE (11.2025–10.2026) — każda sesja w każdym pliku
#     (0 dni z udziałem < 95%, 0 funduszy bez 3 sesji); 25 zapisanych plików fundusze z 27.09–11.10.2026 (27 ocen: w chwili zapisu i o 06:20 UTC,
#     gdy plik miał ≤ 3 h) — 0 fałszywych ostrzeżeń; model ma zapas wobec zaobserwowanych pór (iShares 12:03 → 14:00, State Street ok. 05:00–11:10 → 12:00);
#     brak sesji od ostatniej zamkniętej sesji (bt/bt_brak_sesji.py, te same 25 plików, 1 056 ocen funduszy): największy 1 (iShares 46, State Street
#     345 ocen) — próg 3 ma zapas 2 sesji.
# (2) kontrola krzyżowa: NAV z pliku wydawcy a zamknięcie na giełdzie z pliku ceny (inne źródło) w ostatnim wspólnym dniu — różnica ponad
#     FU_NAV_PROG % = uwaga (⚠; błąd pliku, np. NAV 0,001328 EWZ 05.10.2026). Test wsteczny (bt/bt_nav_ceny.py): 9 funduszy × ok. 260 dni = 2 337 par,
#     największa różnica 6,98% (EWY 04.03.2026 — giełda w Seulu zamknięta 8 h wcześniej niż Nowy Jork), ponad 8% — 0 (fałszywych 0%).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'fundusze-przeplywy')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['fundusze-przeplywy'] = 180
FU_NYSE_ZAMK = frozenset(('2026-01-01', '2026-01-19', '2026-02-16', '2026-04-03', '2026-05-25', '2026-06-19', '2026-07-03', '2026-09-07',
                          '2026-11-26', '2026-12-25', '2027-01-01', '2027-01-18', '2027-02-15', '2027-03-26', '2027-05-31', '2027-06-18',
                          '2027-07-05', '2027-09-06', '2027-11-25', '2027-12-24'))   # = TD_NYSE_CLOSED w zbieraj_dane.py (test pilnuje zgodności)
FU_UDZIAL = 95.0
FU_SESJE = 3
FU_ZAMK_H = 21   # godz. UTC — sesja NYSE zamknięta (16:00 w Nowym Jorku: 20:00 UTC latem, 21:00 zimą)
FU_NAV_PROG = 8.0
FU_ETYKIETA = {'sesja': 'Fundusze ETF (USA) — fundusze z ostatnią sesją (State Street, iShares)',
               'nav': 'Fundusze ETF (USA) — NAV a zamknięcie na giełdzie (kontrola krzyżowa)'}
PLIKI.insert(PLIKI.index('krypto-dzien'), 'zboza-dzien')   # v341 (F5Z3): zboża dziennie i koszt transportu — przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['zboza-dzien'] = 100 * 60   # v341: plik zmienia się, gdy źródło ma nowe dane (indeks dzienny w dni robocze — przez weekend i święto do ok. 4 dni); wiek części ocenia wiersz świeżości
PIP_OKRES_MIES = 15
PIP_SUMA_TOL_MLN, PIP_SUMA_TOL_PCT = 500.0, 1.0
PIP_ETYKIETA = {'pol_e': 'MFW PIP — Polska jako emitent (półrocze)', 'pary': 'MFW PIP — 20 największych par (półrocze)',
                'suma_e': 'MFW PIP — kto trzyma polskie papiery: suma = świat', 'suma_p': 'MFW PIP — Polska jako inwestor: suma = świat'}


def _pip_koniec(h):
    """'2025-S2' → (miesiąc końca '2025-12', ostatni dzień półrocza 2025-12-31 UTC jako datetime) albo None."""
    m = re.match(r'^(\d{4})-S([12])$', str(h or ''))
    if not m:
        return None
    y, mm = int(m.group(1)), (6 if m.group(2) == '1' else 12)
    return f'{y}-{mm:02d}', dt.datetime(y + (mm == 12), mm % 12 + 1, 1, tzinfo=dt.timezone.utc)


def pip_kontrola(j, now=None):
    """data/pip.json → {'rows': [(etykieta, status, wiek min, data, uwaga)], 'uwagi': [...]}; brak pliku = bez wierszy (wiek pliku i brak
    pliku zgłasza pętla PLIKI). Półrocze: ✅ / ⚠️ wg PIP_OKRES_MIES; suma: ✅ / ⚠️ wg tolerancji; brak części = '?'."""
    now = now or NOW
    out = {'rows': [], 'uwagi': []}
    if not isinstance(j, dict):
        return out
    for k in ('pol_e', 'pary'):
        lab, P = PIP_ETYKIETA[k], j.get(k) if isinstance(j.get(k), dict) else None
        ko = _pip_koniec(P.get('okres')) if P else None
        if not ko:
            out['rows'].append((lab, '?', None, None, 'brak tej części w pliku'))
            out['uwagi'].append(f'{lab}: brak tej części w pliku'); continue
        mies, koniec = ko
        w = wiek_danych(mies, 'month', 'k', now)
        lim = dt.datetime(koniec.year + (koniec.month - 1 + PIP_OKRES_MIES) // 12, (koniec.month - 1 + PIP_OKRES_MIES) % 12 + 1, 1, tzinfo=dt.timezone.utc)
        st = '⚠️' if now >= lim else '✅'
        note = '' if st == '✅' else (f'półrocze starsze niż {PIP_OKRES_MIES} mies. od końca — nowe półrocze nie dotarło '
                                      '(publikacja co pół roku, z opóźnieniem ok. 9 mies.); najwyżej uwaga')
        out['rows'].append((lab, st, w, P['okres'], note))
        if st == '⚠️':
            out['uwagi'].append(f'{lab}: dane z {P["okres"]} — {fmt_wiek(w)} temu ({note})')
    for k, s in (('pol_e', 'suma_e'), ('pol_p', 'suma_p')):
        lab, P = PIP_ETYKIETA[s], j.get(k) if isinstance(j.get(k), dict) else None
        a, b = (P.get('suma'), P.get('swiat')) if P else (None, None)
        if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (a, b)):
            out['rows'].append((lab, '?', None, None, 'brak sumy albo wiersza świata')); continue
        tol = max(PIP_SUMA_TOL_MLN, abs(b) * PIP_SUMA_TOL_PCT / 100)
        st = '✅' if abs(a - b) <= tol else '⚠️'
        txt = f'{a / 1000:.1f} vs {b / 1000:.1f} mld USD ({P.get("okres")})'
        note = '' if st == '✅' else f'różnica {abs(a - b) / 1000:.1f} mld USD — ponad {tol / 1000:.1f} mld (zmiana listy agregatów u źródła?)'
        out['rows'].append((lab, st, None, txt, note))
        if st == '⚠️':
            out['uwagi'].append(f'{lab}: {txt} — {note}')
    return out




# ---------------------------------------------------------------- v339 (F4Z1+F4Z2): metale przemysłowe (data/metale.json) ----------------------------------------------------------------
# Wiek PLIKU (pole at = najnowsza przebudowana część): części zmieniają się w dni handlu w Londynie (wieczorem UTC), w Szanghaju (ok. 07:30 UTC)
# i w sobotę (raport tygodniowy o miedzi). Najdłuższa przerwa bez żadnej nowej części w modelu kalendarza 2026 (Wielkanoc: Londyn zamknięty
# 3 i 6.04, Szanghaj 4–6.04, raport o miedzi w czwartek 2.04): ok. 96 h → limit 5 dni. Świeżość KAŻDEJ części osobnym wierszem (lista SWIEZOSC
# bez zmian), najwyżej ⚠️ — progi (wiek od końca dnia danych):
#   Londyn 6 dni — test wsteczny na dniach handlu 2020-01 – 2026-10 (1712 sesji z tabel rocznych; najdłuższa przerwa 5 dni — Wielkanoc i
#     Boże Narodzenie): kontrola co godzinę, publikacja do D + 30 h — najwyższy wiek 5 d 5 h, ⚠️ 0 z 59 136 godzin (z dodatkowym dniem
#     spóźnienia: 65 = 0,11%);
#   Szanghaj, ceny i kwity dzienne — 12 dni: model kalendarza (weekendy i zamknięcia giełd w Chinach; najdłuższa przerwa między sesjami —
#     Święto Wiosny, do 11 dni; w nagraniach 30.09 → 8.10.2026 = 8 dni). Bez pełnej historii sesji — próg do przeglądu po roku danych w pliku;
#   Szanghaj, zapasy tygodniowe — 15 dni (raport z ostatniego dnia handlu tygodnia; przy Święcie Wiosny dwa tygodnie bez raportu = do 14 dni);
#   raport tygodniowy o miedzi — 14 dni: 146 raportów 2024-01 – 2026-10 z listy wydawcy, najdłuższa przerwa między dniami raportów 10 dni (święta
#     we wrześniu), publikacja do 3 dni po dniu raportu → najwyższy wiek 12 dni, ⚠️ 0.
# Porównania (najwyżej ⚠️, nigdy ❌): (1) miedź w Londynie z raportu tygodniowego = zapas dzienny tego samego dnia; (2) miedź w Szanghaju
# z raportu tygodniowego = zapas z tygodniowego raportu giełdy z TEGO SAMEGO tygodnia ISO (przy świętach raport giełdy bywa z wtorku albo
# środy); tolerancja MT_K_TOL_PCT % — nagrania 25.09, 2.10, 9.10.2026: 3 + 2 pary równe co do tony; (3) kwity z raportu tygodniowego
# giełdy w Szanghaju = kwity z raportu dziennego tego samego dnia (9.10.2026: 6 z 6 równych); (4) średnia miesięczna cen cash z pliku wobec
# średniej miesięcznej Banku Światowego (surowce-hist.json / surowce.json) — próg MT_K_MIES_PCT %: 126 par miesięcy (miedź 2020-01 – 2026-09,
# pozostałe metale 2026-01 – 2026-09) — największa różnica 0,74% (cyna 01.2026), ⚠️ 0. ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku
# (daty nie rosną, cena ≤ 0, zapas ujemny, suma giełd ≠ razem w raporcie o miedzi, zmiana ≠ cena / poprzednia).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'metale')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['metale'] = 5 * 24 * 60
MT_K_ETYKIETA = {'lme': 'metale: giełda w Londynie — ceny i zapasy (dziennie, publ. wieczorem UTC)',
                 'sh': 'metale: giełda w Szanghaju — ceny (dziennie, ok. 07:30 UTC)',
                 'shd': 'metale: giełda w Szanghaju — kwity magazynowe (dziennie)',
                 'shw': 'metale: giełda w Szanghaju — zapasy w magazynach (tygodniowo)',
                 'cu': 'metale: raport tygodniowy o zapasach miedzi (Londyn, USA, Chiny)'}
MT_K_PROG = {'lme': 6 * 24 * 60, 'sh': 12 * 24 * 60, 'shd': 12 * 24 * 60, 'shw': 15 * 24 * 60, 'cu': 14 * 24 * 60}
MT_K_TOL_PCT = 0.1       # % — zapasy miedzi: raport tygodniowy vs dane giełdy
MT_K_MIES_PCT = 1.0      # % — średnia miesięczna cash vs Bank Światowy
MT_K_WB = {'cu': 'miedz', 'al': 'aluminium', 'ni': 'nikiel', 'zn': 'cynk', 'pb': 'olow', 'sn': 'cyna'}
MT_K_NAZWY = {'cu': 'miedź', 'al': 'aluminium', 'ni': 'nikiel', 'zn': 'cynk', 'pb': 'ołów', 'sn': 'cyna'}


def _mt_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf')


def _mt_k_tydz(d):
    try:
        y, w, _ = dt.date.fromisoformat(str(d)[:10]).isocalendar()
        return (y, w)
    except ValueError:
        return None


def metale_swiezosc(j, now=None):
    """Wiersze świeżości części pliku metale.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️,
    nigdy ❌; brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    rows = []
    for p, label in MT_K_ETYKIETA.items():
        P = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = P.get('asof') if isinstance(P.get('asof'), str) else None
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(txt, 'day', 'k', now)
        prog = MT_K_PROG[p]
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            nt = nx.get(p); pt = _aw_t(nt) if isinstance(nt, str) else None
            note = f'próg {fmt_wiek(prog)} — najwyżej uwaga' + (
                f'; spodziewana publikacja {czas_pl(nt)}' + (' — zaległa (święto albo przerwa u źródła?)' if pt and pt < now else '') if pt else '')
        rows.append((label, st, w, txt, note))
    return rows


def _mt_k_rosna(rows):
    ds = [str(r[0]) for r in rows if isinstance(r, list) and r]
    return ds == sorted(set(ds))


def metale_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w metalach) → lista opisów."""
    zle = []
    L = ((j.get('lme') or {}).get('m') or {}) if isinstance(j.get('lme'), dict) else {}
    for m, e in (L.items() if isinstance(L, dict) else ()):
        if not isinstance(e, dict):
            continue
        for k in ('d', 'tz', 'wyk', 'mies'):
            if isinstance(e.get(k), list) and not _mt_k_rosna(e[k]):
                zle.append(f'lme.{m}.{k}: daty nie rosną albo się powtarzają')
        for r in e.get('d') or []:
            if isinstance(r, list) and len(r) == 4 and ((r[1] is not None and not (_mt_k_num(r[1]) and r[1] > 0))
                                                       or (r[3] is not None and not (_mt_k_num(r[3]) and r[3] >= 0))):
                zle.append(f'lme.{m}: {r[0]} — cena ≤ 0 albo zapas ujemny'); break
        c, pc, ch = e.get('c'), e.get('pc'), e.get('ch')
        if _mt_k_num(c) and _mt_k_num(pc) and pc > 0 and _mt_k_num(ch) and abs((c / pc - 1) * 100 - ch) > 0.002:
            zle.append(f'lme.{m}: zmiana {ch}% ≠ {(c / pc - 1) * 100:.3f}% z ceny i poprzedniej ceny')
    S = ((j.get('sh') or {}).get('m') or {}) if isinstance(j.get('sh'), dict) else {}
    for m, e in (S.items() if isinstance(S, dict) else ()):
        if isinstance(e, dict) and isinstance(e.get('d'), list) and not _mt_k_rosna(e['d']):
            zle.append(f'sh.{m}.d: daty nie rosną albo się powtarzają')
    C = j.get('cu') if isinstance(j.get('cu'), dict) else {}
    if C and all(_mt_k_num(C.get(k)) for k in ('lme', 'comex', 'shfe', 'razem')) and abs(C['lme'] + C['comex'] + C['shfe'] - C['razem']) > 3:
        zle.append('cu: suma giełd ≠ razem')
    if isinstance(C.get('d'), list) and not _mt_k_rosna(C['d']):
        zle.append('cu.d: daty nie rosną albo się powtarzają')
    return zle


def _mt_k_wb(files, wid):
    """Średnie miesięczne Banku Światowego {RRRR-MM: cena} z surowce.json (mies.s) i surowce-hist.json (m) — nowsze z surowce.json."""
    out = {}
    h = files.get('surowce-hist') if isinstance(files.get('surowce-hist'), dict) else {}
    for r in ((h.get('m') or {}).get(wid) or []) if isinstance(h.get('m'), dict) else []:
        if isinstance(r, list) and len(r) == 2 and _mt_k_num(r[1]):
            out[r[0]] = r[1]
    s = files.get('surowce') if isinstance(files.get('surowce'), dict) else {}
    S = ((s.get('mies') or {}).get('s') or {}) if isinstance(s.get('mies'), dict) else {}
    for r in ((S.get(wid) or {}).get('d') or []) if isinstance(S.get(wid), dict) else []:
        if isinstance(r, list) and len(r) == 2 and _mt_k_num(r[1]):
            out[r[0]] = r[1]
    return out


def metale_porownania(j, files):
    """Porównania z progami (najwyżej ⚠️) → {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    W, U = [], []
    C = j.get('cu') if isinstance(j.get('cu'), dict) else {}
    L = ((j.get('lme') or {}).get('m') or {}) if isinstance(j.get('lme'), dict) else {}
    tol = lambda a, b: abs(a - b) <= max(1, abs(b) * MT_K_TOL_PCT / 100)  # noqa: E731
    if C.get('asof') and _mt_k_num(C.get('lme')):
        D = {r[0]: r[3] for r in ((L.get('cu') or {}).get('d') or []) if isinstance(r, list) and len(r) == 4}
        b = D.get(C['asof'])
        if _mt_k_num(b):
            ok = tol(C['lme'], b)
            W.append((f'miedź w Londynie {C["asof"]}: raport tygodniowy vs zapas dzienny', '✅' if ok else '⚠️'))
            if not ok:
                U.append(f'metale: miedź w Londynie {C["asof"]} — raport tygodniowy {C["lme"]} t vs zapas dzienny {b} t '
                         f'(tolerancja {MT_K_TOL_PCT:g}%, w nagraniach 3 z 3 równe) — sprawdzić')
    if C.get('asof') and _mt_k_num(C.get('shfe')):
        SW = ((((j.get('shw') or {}).get('m') or {}).get('cu') or {}).get('d') or []) if isinstance(j.get('shw'), dict) else []
        tc = _mt_k_tydz(C['asof'])
        x = [r for r in SW if isinstance(r, list) and len(r) == 2 and _mt_k_tydz(r[0]) == tc and _mt_k_num(r[1])]
        if x:
            ok = tol(C['shfe'], x[-1][1])
            W.append((f'miedź w Szanghaju (tydzień {C["asof"]}): raport tygodniowy vs raport giełdy', '✅' if ok else '⚠️'))
            if not ok:
                U.append(f'metale: miedź w Szanghaju — raport tygodniowy z {C["asof"]} {C["shfe"]} t vs raport giełdy z {x[-1][0]} {x[-1][1]} t '
                         f'(tolerancja {MT_K_TOL_PCT:g}%, w nagraniach 2 z 2 równe) — sprawdzić')
    SW, SD = j.get('shw') if isinstance(j.get('shw'), dict) else {}, j.get('shd') if isinstance(j.get('shd'), dict) else {}
    if SW.get('asof') and SW.get('asof') == SD.get('asof'):
        zle = [m for m in MT_K_NAZWY if _mt_k_num(((SW.get('m') or {}).get(m) or {}).get('w')) and _mt_k_num(((SD.get('m') or {}).get(m) or {}).get('w'))
               and SW['m'][m]['w'] != SD['m'][m]['w']]
        W.append((f'Szanghaj {SW["asof"]}: kwity tygodniowe = dzienne', '⚠️' if zle else '✅'))
        if zle:
            U.append(f'metale: Szanghaj {SW["asof"]} — kwity w raporcie tygodniowym ≠ dziennym: ' + ', '.join(MT_K_NAZWY[m] for m in zle)
                     + ' (9.10.2026: 6 z 6 równych) — sprawdzić')
    roz, ile = [], 0
    for m, wid in MT_K_WB.items():
        M = {r[0]: r[1] for r in ((L.get(m) or {}).get('mies') or []) if isinstance(r, list) and len(r) == 3 and _mt_k_num(r[1])}
        wb = _mt_k_wb(files, wid)
        wsp = sorted(set(M) & set(wb))
        if not wsp or not (wb[wsp[-1]] > 0):
            continue
        ym = wsp[-1]
        r = (M[ym] / wb[ym] - 1) * 100
        ile += 1
        if abs(r) > MT_K_MIES_PCT:
            roz.append(f'{MT_K_NAZWY[m]} {ym}: {r:+.2f}%'.replace('.', ','))
    if ile:
        W.append((f'średnie miesięczne cen ({ile} metali) vs Bank Światowy', '⚠️' if roz else '✅'))
        if roz:
            U.append('metale: średnia miesięczna cen w Londynie vs Bank Światowy ponad ' + f'{MT_K_MIES_PCT:g}'.replace('.', ',') + '% — '
                     + '; '.join(roz) + ' (126 par miesięcy 2020–2026: najwyżej 0,74%) — sprawdzić')
    return {'wiersze': W, 'uwagi': U}


def metale_kontrola(files, R):
    """Kontrola pliku metale.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i porównania z progami (najwyżej ⚠️). Brak pliku albo inna wersja
    = None (raport bez linii)."""
    j = files.get('metale')
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = metale_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'metale.json: sprzeczność w pliku — {z}')
    P = metale_porownania(j, files)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


def _fu_sesja(d):
    return d.weekday() < 5 and d.isoformat() not in FU_NYSE_ZAMK


def _fu_oczek(iss, now):
    """v342: oczekiwana sesja wydawcy (patrz FU_*): ostatnia sesja NYSE S, której publikacja w modelu ≤ now → 'RRRR-MM-DD' albo None."""
    d0 = now.date()
    for k in range(0, 20):
        S = d0 - dt.timedelta(days=k)
        if not _fu_sesja(S):
            continue
        if iss == 'ssga':
            n = S + dt.timedelta(days=1)
            while not _fu_sesja(n):
                n += dt.timedelta(days=1)
            P = dt.datetime(n.year, n.month, n.day, 12, 0, tzinfo=dt.timezone.utc)
        else:
            n = S + dt.timedelta(days=1)
            P = dt.datetime(n.year, n.month, n.day, 14, 0, tzinfo=dt.timezone.utc)
        if P <= now:
            return S.isoformat()
    return None


def _fu_ost(now):
    """v342 (recenzja): ostatnia zamknięta sesja NYSE ≤ now (dzień sesji po FU_ZAMK_H:00 UTC — po zamknięciu giełdy także zimą; wcześniej —
    poprzednia sesja) → data. Od niej liczy się „bez danych FU_SESJE sesji” (sesje po ostatnim dniu funduszu do tej sesji włącznie)."""
    d = now.date() if now.hour >= FU_ZAMK_H else now.date() - dt.timedelta(days=1)
    while not _fu_sesja(d):
        d -= dt.timedelta(days=1)
    return d


def _fu_dni(h):
    """v342: dni historii funduszu z liczbami (NAV i liczba jednostek > 0) bez wierszy powtórzonych (ten sam NAV i ta sama liczba jednostek co
    dzień wcześniej — dzień wolny w pliku złota), rosnąco."""
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 < v < float('inf')  # noqa: E731
    R = sorted((r for r in (h if isinstance(h, list) else []) if isinstance(r, list) and len(r) == 3 and isinstance(r[0], str)
                and _DZ_DZIEN.match(r[0]) and num(r[1]) and num(r[2])), key=lambda r: r[0])
    return [b[0] for a, b in zip([None] + R, R) if a is None or (a[1], a[2]) != (b[1], b[2])]


def fundusze_kontrola(fu, ceny=None, now=None):
    """v342 (F1Z2): data/fundusze.json (+ data/ceny.json) → {'rows': [(etykieta, status, wiek min, tekst, uwaga)], 'uwagi': [...]}; brak pliku =
    bez wierszy (brak pliku zgłasza pętla PLIKI)."""
    now = now or NOW
    out = {'rows': [], 'uwagi': []}
    F = fu.get('f') if isinstance(fu, dict) and isinstance(fu.get('f'), dict) else None
    if F is None:
        return out
    L = fu.get('lista') if isinstance(fu.get('lista'), dict) else None
    if L is None:   # plik sprzed v342 — fundusze z pliku według wydawcy
        L = {}
        for t, e in sorted(F.items()):
            if isinstance(e, dict) and e.get('iss') in ('ssga', 'ishares'):
                L.setdefault(e['iss'], []).append(t)
    ok, n, stare, brak, oczek = 0, 0, [], [], {}
    ost = _fu_ost(now)
    for iss in ('ishares', 'ssga'):
        syms = [t for t in (L.get(iss) or []) if isinstance(t, str)]
        if not syms:
            continue
        E = _fu_oczek(iss, now); oczek[iss] = E
        for t in syms:
            n += 1
            ds = _fu_dni((F.get(t) or {}).get('h') if isinstance(F.get(t), dict) else None)
            if not ds:
                brak.append(t); continue
            last = ds[-1]
            ok += not E or last >= E   # udział: fundusz ma oczekiwaną sesję wydawcy (model publikacji z zapasem)
            # brak sesji liczony od ostatniej zamkniętej sesji NYSE (nie od oczekiwanej): sesje po ostatnim dniu funduszu do niej włącznie
            lag, d = 0, dt.date.fromisoformat(last) + dt.timedelta(days=1)
            while d <= ost:
                lag += _fu_sesja(d); d += dt.timedelta(days=1)
            if lag >= FU_SESJE:
                stare.append(f'{t} (ostatni dzień {last}, brak {lag} sesji)')
    if n:
        pct = 100.0 * ok / n
        st = '\u26a0\ufe0f' if pct < FU_UDZIAL or stare or brak else '\u2705'
        txt = (f'{ok} z {n} ({pct:.0f}%) — oczekiwana sesja: iShares {oczek.get("ishares") or "—"}, State Street {oczek.get("ssga") or "—"}'
               .replace('.', ','))
        u = []
        if pct < FU_UDZIAL:
            u.append(f'mniej niż {FU_UDZIAL:g}% funduszy z ostatnią sesją'.replace('.', ','))
        if stare:
            u.append(f'bez danych {FU_SESJE}+ sesji: ' + ', '.join(stare[:8]) + (f' i {len(stare) - 8} więcej' if len(stare) > 8 else ''))
        if brak:
            u.append('bez historii w pliku: ' + ', '.join(brak[:8]) + (f' i {len(brak) - 8} więcej' if len(brak) > 8 else ''))
        note = '; '.join(u) + (' (tylko uwaga)' if u else '')
        out['rows'].append((FU_ETYKIETA['sesja'], st, None, txt, note))
        if u:
            out['uwagi'].append(f'{FU_ETYKIETA["sesja"]}: {txt} — {note}')
    Q = ceny.get('q') if isinstance(ceny, dict) and isinstance(ceny.get('q'), dict) else {}
    par = []
    for t in sorted(set(Q) & set(F)):
        nav = {r[0]: r[1] for r in ((F.get(t) or {}).get('h') or []) if isinstance(r, list) and len(r) == 3 and isinstance(r[1], (int, float)) and r[1] > 0}
        zam = {r[0]: r[1] for r in ((Q.get(t) or {}).get('d') or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[1], (int, float)) and r[1] > 0}
        wsp = sorted(set(nav) & set(zam))
        if wsp:
            d = wsp[-1]; par.append((abs(zam[d] / nav[d] - 1) * 100, t, d))
    if par:
        par.sort(reverse=True)
        zle = [x for x in par if x[0] > FU_NAV_PROG]
        st = '\u26a0\ufe0f' if zle else '\u2705'
        txt = f'{len(par)} funduszy, największa różnica {par[0][0]:.2f}% ({par[0][1]}, {par[0][2]})'.replace('.', ',', 1)
        note = ('NAV i cena różnią się ponad ' + f'{FU_NAV_PROG:g}% — błąd pliku wydawcy albo cen: '.replace('.', ',')
                + ', '.join(f'{t} {d} {x:.1f}%'.replace('.', ',') for x, t, d in zle[:6]) + ' (tylko uwaga)') if zle else ''
        out['rows'].append((FU_ETYKIETA['nav'], st, None, txt, note))
        if zle:
            out['uwagi'].append(f'{FU_ETYKIETA["nav"]}: {note}')
    return out


# ---------------------------------------------------------------- v343 (F1Z3): dźwignia — krzywa terminowa i basis ----------------------------------------------------------------
# Plik data/dzwignia.json (zbieracz co ok. 55 min): krzywa kontraktów z datą Deribit (dr.<moneta>.fut), Coinbase USA (część cde) i — tylko do tej kontroli —
# krzywa kontraktów z datą OKX (okx.<moneta>.fut). Wiersze: wiek odczytu liczony z CZASU Z ODPOWIEDZI giełdy (pole t), nie z czasu pliku; próg DZW_WIEK_MIN.
# Zgodność: basis roczny Deribit vs OKX w tym samym terminie rozliczenia (oba o 08:00 UTC), tylko terminy ≥ 7 dni (krótsze zbieracz pomija: szum w skali roku);
# odczyty z różnych chwil (> DZW_ROZNICA_MIN) nie są porównywane. Tolerancja = max(DZW_BASIS_PP pp rocznie, DZW_BASIS_CENA_PCT % ceny w przeliczeniu na rok
# dla danego terminu): ta sama rozbieżność cen (indeksów i cen kontraktów obu giełd) daje w skali roku tym większą różnicę, im krótszy termin, więc stała
# tolerancja w pp dawałaby fałszywe ostrzeżenia przy terminach do miesiąca (plan zadania: 1 pp rocznie — dla 19 dni to zaledwie 0,05 % ceny).
# TEST WSTECZNY (11.10.2026, nagrania godzinowe z ostatnich ~4 dób: 100 godzin × 6 kontraktów — BTC 4 terminy, ETH 2; w testach: _F1Z3_BACKTEST):
# różnica cen Deribit (ceny transakcji — bardziej zaszumione niż ceny znacznikowe z odczytu zbieracza, więc próg jest ostrożny) vs OKX (cena znacznikowa i indeks
# godzinowy): mediana 0,09 %, p95 0,38 %, p99 0,65 %, maks. 1,66 % (ETH 30.10). Próg ceny 1,0 % = 1 godzina z 200 z ostrzeżeniem (0,5 % < 1 %); próg 0,25 % dawałby
# 18,5 % fałszywych ostrzeżeń, 0,5 % — 4 %. Żywy odczyt zbieracza (cena znacznikowa vs znacznikowa) 11.10: różnice ≤ 0,09 % (BTC) i ≤ 0,3 % (ETH, cienki
# kontrakt wrzesień 2027). Kontrola zapisuje największą różnicę w tabeli — po kilku tygodniach prawdziwej historii próg można zaostrzyć. Najwyżej ostrzeżenie.
DZW_WIEK_MIN = 180
DZW_ROZNICA_MIN = 120
DZW_BASIS_PP = 1.0
DZW_BASIS_CENA_PCT = 1.0
DZW_TERMINY_MIN = 4
DZW_W = '\u26a0\ufe0f'   # to samo znak ostrzeżenia co w reszcie kontroli (selektor wariantu zapisany ucieczką)
DZW_OK = '\u2705'
DZW_ETYKIETA = {'dr': 'Dźwignia — krzywa terminowa Deribit (BTC, ETH)', 'cde': 'Dźwignia — Coinbase USA (kontrakty BTC, ETH)',
                'por': 'Dźwignia — basis Deribit vs OKX (ten sam termin)'}


def _dzw_t(x):
    try:
        t = dt.datetime.fromisoformat(str(x).replace('Z', '+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def _dzw_terminy(f, klucz='y'):
    """{data rozliczenia: (basis roczny, dni)} z listy terminów krzywej; wiersze bez liczb pomijane."""
    out = {}
    for z in (f.get('terms') if isinstance(f, dict) and isinstance(f.get('terms'), list) else []):
        if isinstance(z, dict) and isinstance(z.get('d'), str) and all(isinstance(z.get(k), (int, float)) and not isinstance(z.get(k), bool) for k in (klucz, 'dni')):
            out[z['d']] = (float(z[klucz]), float(z['dni']))
    return out


def dzw_tolerancja(dni):
    """Tolerancja różnicy basis rocznego (pp) między giełdami dla terminu o danej liczbie dni do rozliczenia."""
    return max(DZW_BASIS_PP, DZW_BASIS_CENA_PCT * 365 / dni)


def dzw_kontrola(j, now=None):
    """data/dzwignia.json → {'rows': [(etykieta, status, wiek min, data, uwaga)], 'uwagi': [...], 'por': {moneta: {...}}}; brak pliku = bez wierszy
    (wiek pliku i brak pliku zgłasza pętla PLIKI). status: zgodne / ostrzeżenie / '?' (brak części — np. pierwsze godziny po wdrożeniu)."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'por': {}}
    if not isinstance(j, dict):
        return out
    dr = j.get('dr') if isinstance(j.get('dr'), dict) else {}
    # 1. krzywa Deribit: wiek odczytu i liczba terminów
    ts, ile, brak = [], [], []
    for c in ('BTC', 'ETH'):
        f = dr.get(c, {}).get('fut') if isinstance(dr.get(c), dict) else None
        t = _dzw_t(f.get('t')) if isinstance(f, dict) else None
        if t is None:
            brak.append(c); continue
        ts.append(t); ile.append(len(_dzw_terminy(f)))
    lab = DZW_ETYKIETA['dr']
    if brak:
        out['rows'].append((lab, '?', None, None, 'brak krzywej: ' + ', '.join(brak)))
        out['uwagi'].append(f'{lab}: brak krzywej w pliku ({", ".join(brak)})')
    else:
        w = int((now - min(ts)).total_seconds() // 60)
        st, nota = DZW_OK, ''
        if w > DZW_WIEK_MIN:
            st, nota = DZW_W, f'odczyt starszy niż {DZW_WIEK_MIN} min (zbieracz odświeża co ok. 55 min)'
        elif min(ile) < DZW_TERMINY_MIN:
            st, nota = DZW_W, f'tylko {min(ile)} terminów z basis (oczekiwane ≥ {DZW_TERMINY_MIN}) — giełda zmieniła listę kontraktów?'
        out['rows'].append((lab, st, w, min(ts).isoformat(), nota))
        if st == DZW_W:
            out['uwagi'].append(f'{lab}: dane z {min(ts).isoformat()} — {fmt_wiek(w)} temu ({nota})')
    # 2. Coinbase USA: wiek odczytu
    cde = j.get('cde') if isinstance(j.get('cde'), dict) else None
    lab = DZW_ETYKIETA['cde']
    t = _dzw_t(cde.get('t')) if cde else None
    if t is None:
        out['rows'].append((lab, '?', None, None, 'brak części w pliku'))
        out['uwagi'].append(f'{lab}: brak części w pliku')
    else:
        w = int((now - t).total_seconds() // 60)
        st = DZW_W if w > DZW_WIEK_MIN else DZW_OK
        nota = '' if st == DZW_OK else f'odczyt starszy niż {DZW_WIEK_MIN} min'
        out['rows'].append((lab, st, w, t.isoformat(), nota))
        if st == DZW_W:
            out['uwagi'].append(f'{lab}: dane z {t.isoformat()} — {fmt_wiek(w)} temu ({nota})')
    # 3. zgodność: basis roczny Deribit vs OKX w tym samym terminie
    lab = DZW_ETYKIETA['por']
    okx = j.get('okx') if isinstance(j.get('okx'), dict) else {}
    zle, ok_n, nic = [], 0, []
    for c in ('BTC', 'ETH'):
        fd = dr.get(c, {}).get('fut') if isinstance(dr.get(c), dict) else None
        fo = okx.get(c, {}).get('fut') if isinstance(okx.get(c), dict) else None
        td, to = (_dzw_t(fd.get('t')) if isinstance(fd, dict) else None), (_dzw_t(fo.get('t')) if isinstance(fo, dict) else None)
        if td is None or to is None:
            nic.append(f'{c}: brak krzywej {"Deribit" if td is None else "OKX"}'); continue
        if abs((td - to).total_seconds()) / 60 > DZW_ROZNICA_MIN:
            nic.append(f'{c}: odczyty z różnych chwil (> {DZW_ROZNICA_MIN} min)'); continue
        A, B = _dzw_terminy(fd), _dzw_terminy(fo)
        wsp = sorted(set(A) & set(B))
        if not wsp:
            nic.append(f'{c}: brak wspólnych terminów'); continue
        rz = []
        for d in wsp:
            (ya, dni), (yb, _d2) = A[d], B[d]
            tol = dzw_tolerancja(dni)
            rz.append((abs(ya - yb) - tol, abs(ya - yb), tol, d, ya, yb))
        ok_n += 1
        najg = max(rz)
        out['por'][c] = {'terminy': len(wsp), 'max_roznica_pp': round(najg[1], 2), 'tolerancja_pp': round(najg[2], 2), 'termin': najg[3]}
        if najg[0] > 0:
            zle.append(f'{c} {najg[3]}: Deribit {najg[4]:.2f}% vs OKX {najg[5]:.2f}% rocznie (różnica {najg[1]:.2f} pp, tolerancja {najg[2]:.2f} pp)')
    if zle:
        out['rows'].append((lab, DZW_W, None, None, '; '.join(zle)))
        out['uwagi'].append(f'{lab}: ' + '; '.join(zle) + ' — jedna z giełd ma błędną cenę kontraktu, indeks albo termin?')
    elif ok_n:
        txt = '; '.join(f'{c}: {v["terminy"]} terminów, największa różnica {v["max_roznica_pp"]:.2f} pp (tolerancja {v["tolerancja_pp"]:.2f})' for c, v in out['por'].items())
        out['rows'].append((lab, DZW_OK, None, txt, '' if not nic else '; '.join(nic)))
    else:
        out['rows'].append((lab, '?', None, None, '; '.join(nic) or 'brak danych'))
        out['uwagi'].append(f'{lab}: {"; ".join(nic) or "brak danych"}')
    return out




# v369 (F6Z2): dźwignia — pięć dalszych giełd (Bitget, Gate, KuCoin, MEXC, HTX) w sumie „wszystkie giełdy razem”. Osobne wiersze (lista SWIEZOSC bez zmian):
# wiek odczytu każdej giełdy (czas z jej odpowiedzi albo przebiegu zbieracza, próg DZW_WIEK_MIN), kompletność BTC i ETH (otwarte pozycje w USD) oraz — TYLKO INFORMACJA,
# bez progu i bez ostrzeżenia — suma otwartych pozycji z historii dziennej wobec sumy z poprzedniego zestawu giełd (przed dołączeniem tych pięciu: 4 giełdy).
# Najwyżej ostrzeżenie, nigdy błąd krytyczny ani BŁĄD. Część nieobecna w pliku to '?' bez uwagi (giełda mogła zablokować serwery GitHub albo część jeszcze się nie pojawiła).
DZW9_ETYKIETA = {'bg': 'Dźwignia — Bitget (BTC, ETH)', 'gt': 'Dźwignia — Gate (BTC, ETH, likwidacje)', 'kc': 'Dźwignia — KuCoin (BTC, ETH)',
                 'mx': 'Dźwignia — MEXC (BTC, ETH)', 'hx': 'Dźwignia — HTX (BTC, ETH)'}
DZW9_SUMA = 'Dźwignia — suma otwartych pozycji, wobec poprzedniego zestawu giełd (informacja)'
DZW9_LIQ_MIN = 360     # minuty: likwidacje Gate (okno kończy się na pełnej godzinie) starsze niż tyle — uwaga w wierszu Gate


def _dzw9_oi(r):
    v = r.get('oi_usd') if isinstance(r, dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def dzw9_suma(j):
    """Historia dzienna (hist) → {'BTC': {...}, 'ETH': {...}}: ostatnia suma otwartych pozycji (all_<moneta>, zestaw all_<moneta>_v) i ostatnia suma INNEGO zestawu giełd
    sprzed niej; brak historii albo tylko jeden zestaw → bez porównania. Tylko informacja."""
    H = [h for h in (j.get('hist') if isinstance(j, dict) and isinstance(j.get('hist'), list) else []) if isinstance(h, dict) and isinstance(h.get('d'), str)]
    H.sort(key=lambda h: h['d'])
    out = {}
    for c in ('btc', 'eth'):
        k = 'all_' + c
        L = [h for h in H if isinstance(h.get(k), (int, float)) and not isinstance(h.get(k), bool) and h[k] > 0 and isinstance(h.get(k + '_v'), str)]
        if not L:
            continue
        cur = L[-1]
        e = {'d': cur['d'], 'usd': float(cur[k]), 'n': len([x for x in cur[k + '_v'].split(',') if x]), 'v': cur[k + '_v']}
        prev = next((h for h in reversed(L[:-1]) if h[k + '_v'] != cur[k + '_v']), None)
        if prev:
            e['poprz'] = {'d': prev['d'], 'usd': float(prev[k]), 'n': len([x for x in prev[k + '_v'].split(',') if x])}
        out[c.upper()] = e
    return out


def dzw9_kontrola(j, now=None):
    """data/dzwignia.json → {'rows': [(etykieta, status, wiek min, data, uwaga)], 'uwagi': [...], 'suma': {...}}; brak pliku = bez wierszy.
    status: zgodne / ostrzeżenie (odczyt starszy niż DZW_WIEK_MIN albo brak pozycji w USD dla monety) / '?' (części nie ma w pliku)."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'suma': {}}
    if not isinstance(j, dict):
        return out
    for k, lab in DZW9_ETYKIETA.items():
        P = j.get(k) if isinstance(j.get(k), dict) else None
        ts = [_dzw_t(P[c].get('t')) for c in ('BTC', 'ETH') if P and isinstance(P.get(c), dict)]
        ts = [t for t in ts if t is not None]
        if not ts:
            out['rows'].append((lab, '?', None, None, 'brak części w pliku (giełda mogła zablokować serwery GitHub albo część jeszcze się nie pojawiła)'))
            continue
        t0 = min(ts)
        w = int((now - t0).total_seconds() // 60)
        brak = [c for c in ('BTC', 'ETH') if _dzw9_oi(P.get(c)) is None]
        notes = []
        if w > DZW_WIEK_MIN:
            notes.append(f'odczyt starszy niż {DZW_WIEK_MIN} min (zbieracz odświeża co ok. 55 min)')
        if brak:
            notes.append('brak otwartych pozycji w USD: ' + ', '.join(brak))
        if k == 'gt':
            lq = [_dzw_t((P.get(c) or {}).get('liq', {}).get('t')) for c in ('BTC', 'ETH') if isinstance(P.get(c), dict) and isinstance(P[c].get('liq'), dict)]
            lq = [t for t in lq if t is not None]
            if not lq:
                notes.append('brak likwidacji godzinowych')
            elif int((now - min(lq)).total_seconds() // 60) > DZW9_LIQ_MIN:
                notes.append(f'likwidacje starsze niż {DZW9_LIQ_MIN} min')
        st = DZW_W if notes else DZW_OK
        out['rows'].append((lab, st, w, t0.isoformat(), '; '.join(notes)))
        if st == DZW_W:
            out['uwagi'].append(f'{lab}: dane z {t0.isoformat()} — {fmt_wiek(w)} temu ({"; ".join(notes)})')
    S = dzw9_suma(j)
    out['suma'] = S
    if S:
        parts = []
        for c, e in S.items():
            p = e.get('poprz')
            parts.append(f'{c}: {e["n"]} giełd {e["usd"] / 1e9:.2f} mld USD ({e["d"]})' + (f', poprzednio {p["n"]} giełd {p["usd"] / 1e9:.2f} mld USD ({p["d"]})' if p else ', brak sumy z innego zestawu giełd'))
        out['rows'].append((DZW9_SUMA, DZW_OK, None, '; '.join(parts), ''))
    else:
        out['rows'].append((DZW9_SUMA, '?', None, None, 'brak historii sum w pliku'))
    return out


def pliki_bez_nadzoru(src):
    """v327 (KON-08): nazwy plików data/*.json zapisywanych przez zbieracz (save('nazwa', …) i pętla budowniczych z kluczem w main()) bez wpisu w PLIKI
    i bez powodu w PLIKI_BEZ — test pilnuje, żeby nowy plik nie został bez kontroli wieku."""
    nazwy = set(re.findall(r"\bsave\(['\"]([\w-]+)['\"]", src)) | set(re.findall(r"\(['\"]([\w-]+)['\"], build_\w+, \w+, \d", src))
    return sorted(n for n in nazwy if n not in PLIKI and n not in PLIKI_BEZ)
# v171: części zbieracza wyłączone celowo (notatka w meta.json) — brak pliku to wtedy stan, nie usterka: w raporcie „wyłączone”, bez uwagi
WYLACZONE = {'insider': ('brak SEC_CONTACT', 'SEC_CONTACT to nie adres e-mail')}


def wylaczone(meta):
    """v171: {plik: notatka zbieracza} dla części wyłączonych celowo (np. brak sekretu SEC_CONTACT — urząd wymaga adresu w zapytaniu);
    brak pliku stanu albo notatki = {}."""
    N = [x for x in (meta.get('notes') or []) if isinstance(x, str)] if isinstance(meta, dict) else []
    out = {}
    for n, F in WYLACZONE.items():
        for x in N:
            if any(f in x for f in F):
                out[n] = x[:160]
                break
    return out


# v115: świeżość ŹRÓDEŁ (data danych, nie czas pliku). (etykieta, plik, kategoria, próg w minutach). Kategorie: 'h' = godzinowe (czas części
# pliku), 'd' = dzienne w dni robocze (koniec dnia danych, liczone godzinami roboczymi bez sobót i niedziel), 'w' = tygodniowe (koniec dnia danych),
# 'm' = miesięczne (koniec miesiąca danych). Progi z zadania: 3 h / 36 h / 9 dni / 45 dni; CFTC 13 dni (raport wtorkowy publikowany w piątek, a w tygodniu
# ze świętem w USA w poniedziałek — o 06:20 UTC wiek 12 d 6 h; v327 (KON-02): było 9 + 3 = 12 dni → fałszywe ⚠️ 16.11, 30.11, 28.12.2026; 13 dni jak
# SU_PROG['markets'] i SU3_PROG['pozycje'] z tych samych danych — test wsteczny v298: 0 z 4206 kontroli 2021–2026, maks. wiek przed publikacją 12,88 d),
# TIC +40 dni (Skarb USA publikuje dane miesiąca 46–51 dni po jego końcu; tuż przed publikacją wiek = 30 + 51 = 81 dni) — inaczej żółte świeciłoby co miesiąc bez powodu.
# EIA: ceny dzienne ropy są publikowane raz w tygodniu (środa, za poprzedni tydzień) — próg tygodniowy 9 dni, nie 36 h (26.09: dane z wtorku w sobotę = 3 dni).
# v182: TGA — zestawienie Skarbu USA za dzień D ukazuje się o 16:00 czasu nowojorskiego NASTĘPNEGO dnia roboczego (20:00 UTC latem, 21:00 zimą), więc
# przed publikacją najnowsze jest D−2 dni robocze: normalny wiek do ok. 45 h roboczych (+ do 1 h na odświeżenie pliku). Próg 36 h dawał ⚠️ w każdy
# dzień roboczy od 12:00 do ok. 21:00 UTC (05.10, 12:03 UTC: „36 h 03 min”) — teraz 48 h; święto federalne USA = ⚠️ (informacja, nigdy BŁĄD).
SWIEZOSC = [
    ('rynki (kursy EBC, rentowności)', 'rynki', 'h', 180), ('wieloryby (salda portfeli giełd)', 'wieloryby', 'h', 180), ('dźwignia (giełdy pochodnych)', 'dzwignia', 'h', 180),
    ('premie krypto (minuty giełd)', 'premie', 'h', 180),
    ('TGA (Fiscal Data, dziennie)', 'instytucje', 'd', 48 * 60), ('ETF krypto (SoSoValue, dziennie)', 'etf', 'd', 36 * 60),
    ('FRED dzienne (RRPONTSYD)', 'fred', 'd', 36 * 60), ('EIA ceny dzienne (publikowane co tydzień)', 'energia', 'w', 9 * 24 * 60),
    ('CFTC (raport tygodniowy)', 'cftc', 'w', 13 * 24 * 60), ('FRED tygodniowe (WALCL)', 'fred', 'w', 9 * 24 * 60),
    ('TIC (miesięcznie)', 'tic', 'm', (45 + 40) * 24 * 60), ('OECD (miesięcznie)', 'oecd', 'm', 45 * 24 * 60), ('BLS (miesięcznie)', 'usa-makro', 'm', 45 * 24 * 60),
]
CG_GLOBAL = 'https://api.coingecko.com/api/v3/global'
CP_GLOBAL = 'https://api.coinpaprika.com/v1/global'
CG_PRICE = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd'
CP_TICKER = 'https://api.coinpaprika.com/v1/tickers/{id}?quotes=USD'
ZG_DNI = 30          # mediana z ostatnich 30 dni różnicy kapitalizacji
ZG_MIN = 7           # do zebrania tylu dni historii — tylko informacja, bez koloru
ZG_ZOLTE, ZG_CZERWONE = 2.0, 5.0   # pkt proc. odchylenia od mediany
ZG_CMC_MAX_MIN = 30   # v277: min — plik cmc.json starszy niż tyle od chwili kontroli = bez rozstrzygania (inna chwila rynku)
ZG_CMC_ROZ = 1.0      # v277: pkt proc. — różnica CoinMarketCap/CoinGecko w swojej normie (mediana dni) = oba źródła strony zgodne jak zwykle
ZG_CMC_BEZ = 1.5      # v277: % — bez historii tej różnicy (< ZG_MIN dni): oba źródła strony zgodne, gdy |różnica| mniejsza

# v209: podaż stablecoinów — dwa pliki strony (bez zapytań); rentowność 10L USA — plik strony vs H.15 (FRED, bez klucza)
STAB_ZOLTE = 2.0     # pkt proc. — odchylenie dzisiejszej różnicy (DefiLlama vs CoinMarketCap) od mediany ZG_DNI dni = ⚠️ (nigdy ❌)
STAB_MAX_H = 6.0     # h — pliki krypto.json i cmc.json pobrane dalej od siebie = bez porównania (informacja)
UST_FRED = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd={od}'   # H.15: Rada Gubernatorów Fed — domena publiczna, bez klucza
UST_FED = ('https://www.federalreserve.gov/datadownload/Output.aspx?rel=H15&series=bf17364827e38702b42a58cf8eaa3f78&lastobs=15&from=&to='
           '&filetype=csv&label=include&layout=seriescolumn&type=package')   # v211: H.15 u wydawcy (stałe zapadalności, dni robocze) — najpierw to, FRED zapasem
UST_FED_KOL = 'RIFLGFCY10_N.B'   # v211: kolumna 10 lat w pliku H.15 (06.10: 24.09 5,18 = DGS10 5,18 = plik strony)
UST_PROG = 0.02      # pkt proc. — ta sama data: plik strony (Skarb USA) vs H.15; większa różnica = ⚠️
UST_DNI = 10         # tyle ostatnich dat z pliku strony porównujemy (H.15 wychodzi z ok. 1-dniowym opóźnieniem)
UST_OD_DNI = 21      # FRED: plik od tylu dni wstecz (mały — ok. 200 B)
# v241: stopy Fed i EBC — plik strony (stopy.json) vs FRED (bez klucza), ten sam dzień; zmiana stopy, której strona jeszcze nie ma
STOPY_FRED = {'US': (('DFEDTARL', 'DFEDTARU'), 'Fed'), 'XM': (('ECBDFR',), 'EBC')}   # zapas (FRED): Fed — środek przedziału celu; EBC — stopa depozytowa
# v242: najpierw źródło banku, bez klucza (FRED z serwerów GitHub nie odpowiedział w 30 s): Fed — przedział celu z danych EFFR nowojorskiego Fed,
# EBC — stopa depozytowa z portalu danych EBC; kolejność wariantów = pierwszeństwo
STOPY_SERIE = {'US': ((('NYFED_LO', 'NYFED_HI'), 'Fed', 'NY Fed'), (('DFEDTARL', 'DFEDTARU'), 'Fed', 'FRED')),
               'XM': ((('ECB_DFR',), 'EBC', 'EBC'), (('ECBDFR',), 'EBC', 'FRED')),
               # v244: sześć kolejnych banków u źródła, bez klucza (06.10.2026 wszystkie zgodne ze stroną); bez zapasu FRED (brak serii dziennych)
               'GB': ((('BOE_BR',), 'Bank Anglii', 'BoE'),), 'CH': ((('SNB_LZ',), 'Bank Szwajcarii', 'SNB'),),
               'SE': ((('RB_POL',), 'Bank Szwecji', 'Riksbank'),), 'NO': ((('NB_KPRA',), 'Bank Norwegii', 'Norges Bank'),),
               'PL': ((('NBP_REF',), 'NBP', 'NBP'),), 'CA': ((('BOC_V39079',), 'Bank Kanady', 'BoC'),),
               'BR': ((('BCB_SELIC',), 'Bank Brazylii', 'BCB'),)}   # v245: Selic — cel stopy (SGS 432)
STOPY_NYFED = 'https://markets.newyorkfed.org/api/rates/unsecured/effr/last/100.json'
STOPY_ECB = 'https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?lastNObservations=150&format=csvdata'
# v244: adresy kolejnych banków ({od} = dzień początkowy, {do} = dziś; Bank Anglii — data „08/Jun/2026”). Bank Australii odrzuca automaty
# (403 — zabezpieczenie) — pominięty.
STOPY_BOE = ('https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom={od}&Dateto=now'
             '&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N')
STOPY_SNB = 'https://data.snb.ch/api/cube/snbgwdzid/data/csv/en?dimSel=D0(LZ)&fromDate={od}'
STOPY_RIKS = 'https://api.riksbank.se/swea/v1/Observations/SECBREPOEFF/{od}/{do}'
STOPY_NORGES = 'https://data.norges-bank.no/api/data/IR/B.KPRA.SD.R?format=csv&startPeriod={od}&locale=en'
STOPY_NBP = 'https://static.nbp.pl/dane/stopy/stopy_procentowe.xml'   # tylko stopa obowiązująca i dzień, od którego obowiązuje (archiwum do 2015)
STOPY_BOC = 'https://www.bankofcanada.ca/valet/observations/V39079/json?start_date={od}'
STOPY_BCB = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json&dataInicial={od}&dataFinal={do}'   # v245: daty dd/mm/rrrr
STOPY_MIES_EN = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
STOPY_BUDZET_S = 90    # v245: cały blok stóp (źródła banków, ponowienia, zapas FRED) — zapytanie tylko, gdy zmieści się w budżecie (krok kontroli
#                        ok. 90 s; zadanie ma 12 min, w tym do 5 min czekania na publikację)
STOPY_PAUZA_S = 3      # v245: przerwa przed jedną ponowną próbą po błędzie serwera (5xx) albo przekroczeniu czasu
STOPY_ZAPAS_S = 5      # v248: twardy limit jednego zapytania = jego limit + tyle (urllib liczy limit na operację gniazda; DNS bez limitu)
STOPY_FRED_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}&cosd={od}'
STOPY_OD_DNI = 120    # FRED: plik od tylu dni wstecz (data stopy na stronie bywa sprzed kilku tygodni — np. RBI)
STOPY_PROG = 0.01     # pkt proc. — większa różnica w tym samym dniu = ⚠️
STOPY_ZWLOKA_DNI = 10  # zmiana stopy starsza niż tyle dni, a strona jej nie ma = ⚠️ (v243: źródło stóp strony spóźnia się 7–8 dni; przy 3 każda
#                        decyzja Fed/EBC dawałaby kilka dni UWAGI)


def _stopa_fred(S, d):
    """Stopa z serii FRED (lista {dzień: %}) w dniu d = średnia ostatnich obserwacji ≤ d każdej serii; brak którejś = None."""
    v = []
    for s in S:
        dn = [k for k in s if k <= d]
        if not dn:
            return None
        v.append(s[max(dn)])
    return sum(v) / len(v)


def stopy_nyfed(body):
    """v242: JSON EFFR nowojorskiego Fed → {'NYFED_LO': {dzień: dolna granica celu}, 'NYFED_HI': {dzień: górna}}; pusto = wyjątek."""
    j = json.loads(body)
    lo, hi = {}, {}
    for r in (j.get('refRates') or []) if isinstance(j, dict) else []:
        d, a, b = (r.get('effectiveDate'), r.get('targetRateFrom'), r.get('targetRateTo')) if isinstance(r, dict) else (None, None, None)
        if isinstance(d, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', d) and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) < 1e6 for x in (a, b)):
            lo[d], hi[d] = float(a), float(b)
    if not lo:
        raise ValueError('brak przedziału celu')
    return {'NYFED_LO': lo, 'NYFED_HI': hi}


def stopy_ecb_csv(body, sep=','):
    """v242: CSV portalu danych EBC (kolumny TIME_PERIOD, OBS_VALUE) → {dzień: stopa}; puste wartości pominięte; pusto = wyjątek.
    v244: sep=';' — ten sam układ SDMX u Norges Bank; znacznik BOM pominięty."""
    L = (body.decode('utf-8-sig', 'replace') if isinstance(body, (bytes, bytearray)) else str(body)).splitlines()
    h = L[0].split(sep) if L else []
    if 'TIME_PERIOD' not in h or 'OBS_VALUE' not in h:
        raise ValueError('nieznany nagłówek')
    i, j, out = h.index('TIME_PERIOD'), h.index('OBS_VALUE'), {}
    for line in L[1:]:
        p = line.split(sep)
        if len(p) > max(i, j) and re.match(r'^\d{4}-\d{2}-\d{2}$', p[i]):
            try:
                v = float(p[j])
            except ValueError:
                continue
            if v == v and abs(v) < 1e6:   # v243: NaN i nieskończoność odrzucone
                out[p[i]] = v
    if not out:
        raise ValueError('plik bez liczb')
    return out


def _stopy_tekst(body):
    """v244: treść odpowiedzi jako tekst, bez znacznika BOM."""
    return body.decode('utf-8-sig', 'replace') if isinstance(body, (bytes, bytearray)) else str(body).lstrip('\ufeff')


def _stopy_liczba(x):
    """v244: stopa z liczby albo tekstu („3,75” i „3.75”); NaN, nieskończoność, wartości absurdalne i typ bool = None."""
    if isinstance(x, bool):
        return None
    if isinstance(x, str):
        try:
            x = float(x.strip().replace(',', '.'))
        except ValueError:
            return None
    return float(x) if isinstance(x, (int, float)) and x == x and abs(x) < 1e6 else None


def stopy_boe(body):
    """v244: CSV bazy danych Banku Anglii (DATE,IUDBEDR; wiersze „05 Oct 2026,3.75”) → {'BOE_BR': {dzień: stopa}}; inny nagłówek (np. strona
    błędu z kodem 200) = wyjątek; skróty miesięcy po angielsku bez ustawień regionalnych."""
    L = _stopy_tekst(body).splitlines()
    if not L or L[0].replace(' ', '') != 'DATE,IUDBEDR':
        raise ValueError('nieznany nagłówek')
    out = {}
    for line in L[1:]:
        p = line.split(',')
        m = re.match(r'^(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})$', p[0].strip()) if len(p) == 2 else None
        v = _stopy_liczba(p[1]) if m and m.group(2) in STOPY_MIES_EN else None
        if v is not None:
            out[f'{m.group(3)}-{STOPY_MIES_EN.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}'] = v
    if not out:
        raise ValueError('plik bez liczb')
    return {'BOE_BR': out}


def stopy_snb(body):
    """v244: CSV portalu danych SNB (średniki, cudzysłowy: „"2026-10-02";"LZ";"0"”) → {'SNB_LZ': {dzień: stopa}} — tylko wymiar LZ (stopa SNB)."""
    out = {}
    for line in _stopy_tekst(body).splitlines():
        p = [x.strip().strip('"') for x in line.split(';')]
        if len(p) == 3 and p[1] == 'LZ' and re.match(r'^\d{4}-\d{2}-\d{2}$', p[0]):
            v = _stopy_liczba(p[2])
            if v is not None:
                out[p[0]] = v
    if not out:
        raise ValueError('plik bez liczb')
    return {'SNB_LZ': out}


def stopy_riksbank(body):
    """v244: JSON Riksbanku (lista {date, value}) → {'RB_POL': {dzień: stopa}}."""
    j = json.loads(body)
    out = {}
    for r in j if isinstance(j, list) else []:
        d, v = (r.get('date'), _stopy_liczba(r.get('value'))) if isinstance(r, dict) else (None, None)
        if isinstance(d, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', d) and v is not None:
            out[d] = v
    if not out:
        raise ValueError('brak stóp')
    return {'RB_POL': out}


def stopy_norges(body):
    """v244: CSV Norges Bank (SDMX, średniki; kolumny TIME_PERIOD, OBS_VALUE) → {'NB_KPRA': {dzień: stopa}}."""
    return {'NB_KPRA': stopy_ecb_csv(body, sep=';')}


def stopy_nbp(body):
    """v244: XML stóp NBP — tylko stopa obowiązująca (pozycja id="ref", „3,75”) i dzień, od którego obowiązuje → {'NBP_REF': {dzień: stopa}}:
    seria schodkowa z jednym punktem (ta stopa na każdy dzień od tej daty; dzień strony sprzed niej — bez porównania, ale ze zmianą)."""
    for m in re.finditer(r'<pozycja\b([^>]*)>', _stopy_tekst(body)):
        a = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', m.group(1)))
        if a.get('id') == 'ref':
            d, v = a.get('obowiazuje_od', ''), _stopy_liczba(a.get('oprocentowanie', ''))
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', d) or v is None:
                raise ValueError('zła stopa referencyjna')
            return {'NBP_REF': {d: v}}
    raise ValueError('brak stopy referencyjnej')


def stopy_boc(body):
    """v244: JSON Banku Kanady (Valet: observations [{d, V39079: {v: "2.25"}}]) → {'BOC_V39079': {dzień: stopa}}."""
    j = json.loads(body)
    out = {}
    for r in (j.get('observations') or []) if isinstance(j, dict) else []:
        o = r.get('V39079') if isinstance(r, dict) else None
        d, v = (r.get('d'), _stopy_liczba(o.get('v'))) if isinstance(o, dict) else (None, None)
        if isinstance(d, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', d) and v is not None:
            out[d] = v
    if not out:
        raise ValueError('brak stóp')
    return {'BOC_V39079': out}


def stopy_bcb(body):
    """v245: JSON Banku Brazylii (SGS 432 — cel stopy Selic, dziennie; [{"data": "29/09/2026", "valor": "13.75"}]) → {'BCB_SELIC': {dzień:
    stopa}}; obiekt z błędem (np. okno ponad 10 lat) = wyjątek."""
    j = json.loads(body)
    out = {}
    for r in j if isinstance(j, list) else []:
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', r.get('data', '')) if isinstance(r, dict) and isinstance(r.get('data'), str) else None
        v = _stopy_liczba(r.get('valor')) if m else None
        if v is not None:
            out[f'{m.group(3)}-{m.group(2)}-{m.group(1)}'] = v
    if not out:
        raise ValueError('brak stóp' if isinstance(j, list) else f'odpowiedź bez listy ({str(j)[:40]})')
    return {'BCB_SELIC': out}


def stopy_adresy(now=None):
    """v244: (nazwa źródła, adres, parser, serie) kolejnych banków — od STOPY_OD_DNI dni wstecz do dziś (v246: serie — do powodu banku przy
    błędzie odczytu)."""
    now = now or NOW
    d0, d1 = now.date() - dt.timedelta(days=STOPY_OD_DNI), now.date()
    od = d0.isoformat()
    return (('BoE', STOPY_BOE.format(od=f'{d0.day:02d}/{STOPY_MIES_EN[d0.month - 1]}/{d0.year}'), stopy_boe, ('BOE_BR',)),
            ('SNB', STOPY_SNB.format(od=od), stopy_snb, ('SNB_LZ',)),
            ('Riksbank', STOPY_RIKS.format(od=od, do=d1.isoformat()), stopy_riksbank, ('RB_POL',)),
            ('Norges Bank', STOPY_NORGES.format(od=od), stopy_norges, ('NB_KPRA',)),
            ('NBP', STOPY_NBP, stopy_nbp, ('NBP_REF',)),
            ('BoC', STOPY_BOC.format(od=od), stopy_boc, ('BOC_V39079',)),
            ('BCB', STOPY_BCB.format(od=d0.strftime('%d/%m/%Y'), do=d1.strftime('%d/%m/%Y')), stopy_bcb, ('BCB_SELIC',)))


def stopy_ponowic(e):
    """v245: błąd chwilowy, który warto raz ponowić — kod 5xx serwera albo przekroczenie czasu (także owinięte w URLError)."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500
    if isinstance(e, urllib.error.URLError):
        return isinstance(e.reason, TimeoutError)
    return isinstance(e, TimeoutError)


def _stopy_raz(url, timeout, headers=None, pobierz=None, zapas=None):
    """v248: jedno zapytanie z twardym limitem łącznego czasu (timeout + STOPY_ZAPAS_S) — urllib liczy limit na operację gniazda, nie na całość
    (wolno sączący serwer, DNS); wątek w tle po przekroczeniu jest porzucany (kończy się sam albo z procesem)."""
    pobierz = pobierz or get
    zapas = STOPY_ZAPAS_S if zapas is None else zapas
    wyn = {}

    def run():
        try:
            wyn['b'] = pobierz(url, timeout=timeout, headers=headers)[1]
        except Exception as e:  # noqa
            wyn['e'] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout + zapas)
    if t.is_alive():
        raise TimeoutError(f'brak całej odpowiedzi w {timeout + zapas:g} s')
    if 'e' in wyn:
        raise wyn['e']
    return wyn['b']


def _dzien(s):
    """v248: 'RRRR-MM-DD' tylko prawdziwego dnia kalendarza (np. 31.09 = None) — daty źródeł trafiają później do date.fromisoformat."""
    if not isinstance(s, str) or not re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return None
    try:
        dt.date.fromisoformat(s)
    except ValueError:
        return None
    return s


def stopy_porownanie(stopy, fred, now=None, bledy=None):
    """v241/v243: stopy.json (rows[kraj] = {rate, date}) i serie ({id: {dzień: %}}) → jedna pozycja na bank: porównanie {'bank', 'zrodlo',
    'data', 'strona', 'fred', 'zgodne', 'zmiana': [dzień, nowa stopa] albo None} albo {'bank', 'brak': powód, 'powod'} — bank bez porównania
    nie znika z wiersza raportu (v243). Wariant serii: pierwszy, który obejmuje dzień strony (źródło banku, potem FRED). Brak pliku strony = [].
    v246: bledy = {id serii: 'źródło: błąd'} — bank bez żadnej serii: powód z błędów odczytu ('powod': 'odczyt', 'bledy'); „brak serii
    obejmującej dzień strony” tylko, gdy seria jest, ale zaczyna się po dniu strony ('powod': 'seria') — wtedy pierwsza inna stopa w całej
    serii ('zmiana'); inna już na początku danych = 'od_poczatku' (dzień zmiany nieznany; NBP — jedyny dzień to dzień, od którego obowiązuje)."""
    now = now or NOW
    if not isinstance(stopy, dict):
        return []
    rows = stopy.get('rows') if isinstance(stopy.get('rows'), dict) else {}
    F = {i: {d: v for d, v in s.items() if _dzien(d)} for i, s in fred.items() if isinstance(s, dict)} if isinstance(fred, dict) else {}   # v248: tylko prawdziwe dni
    B = bledy if isinstance(bledy, dict) else {}
    out = []
    for a, warianty in STOPY_SERIE.items():
        nazwa = warianty[0][1]
        r = rows.get(a)
        rate = r.get('rate') if isinstance(r, dict) else None
        if not isinstance(rate, (int, float)) or isinstance(rate, bool) or rate != rate or abs(rate) > 1e6:
            out.append({'bank': nazwa, 'brak': 'brak stopy w pliku strony', 'powod': 'strona'})
            continue
        if not _dzien(r.get('date')):   # v248: także 30.02 to nie dzień
            out.append({'bank': nazwa, 'brak': ('brak daty w pliku strony' if r.get('date') in (None, '')   # v327 (KON-06): bez „None” w raporcie
                                                else f'data w pliku strony „{str(r.get("date"))[:10]}” to nie dzień'), 'powod': 'strona'})
            continue
        jest = [(ids, zr) for ids, _, zr in warianty if all(isinstance(F.get(i), dict) and F.get(i) for i in ids)]
        wyb = None
        for ids, zr in jest:
            S = [F[i] for i in ids]
            f = _stopa_fred(S, r['date'])
            if f is not None:
                wyb = (S, zr, f)
                break
        if not jest:   # v246: żadne źródło nie dało serii — powód z błędów odczytu (było „brak serii obejmującej dzień strony”)
            bl = list(dict.fromkeys(B[i] for ids, _, _ in warianty for i in ids if i in B))
            out.append({'bank': nazwa, 'brak': ('nie odczytano źródła — ' + '; '.join(bl)) if bl else 'brak danych ze źródła', 'powod': 'odczyt',
                        'bledy': bl})
            continue
        if wyb is None:   # seria jest, ale zaczyna się po dniu strony (NBP podaje tylko stopę obowiązującą; okno pobierania ok. 4 mies.)
            ids, zr = jest[0]
            S = [F[i] for i in ids]
            d0 = max(min(s) for s in S)
            o = {'bank': nazwa, 'brak': f'brak serii obejmującej dzień strony ({r["date"]})', 'powod': 'seria'}
            for d in sorted({k for s in S for k in s if k >= d0}):   # v246: pierwsza inna stopa w całej serii (było: tylko pierwszy dzień)
                v = _stopa_fred(S, d)
                if v is not None and abs(v - rate) >= STOPY_PROG:
                    o.update(zrodlo=zr, data=r['date'], strona=float(rate), zmiana=[d, round(v, 4)],
                             od_poczatku=d == d0 and any(len(s) > 1 for s in S))
                    break
            out.append(o)
            continue
        S, zr, f = wyb
        o = {'bank': nazwa, 'zrodlo': zr, 'data': r['date'], 'strona': float(rate), 'fred': round(f, 4), 'zgodne': abs(rate - f) < STOPY_PROG, 'zmiana': None}
        dni = sorted({k for s in S for k in s if k > r['date']})
        for d in dni:
            v = _stopa_fred(S, d)
            if v is not None and abs(v - f) >= STOPY_PROG:
                o['zmiana'] = [d, round(v, 4)]
                break
        out.append(o)
    return out


def stopy_sprawdz(stopy, now=None, zegar=time.monotonic, spij=time.sleep):
    """v246: blok stóp kontroli (wyjęty z kontrola(), żeby testy szły przez prawdziwy przebieg): źródła banków w budżecie STOPY_BUDZET_S,
    zapas FRED dla banków bez porównania, błąd odczytu każdej serii → powód „brak porównania” banku. v248: faza 1 — każde źródło raz;
    faza 2 — jedno ponowienie źródeł z błędem chwilowym (5xx, przekroczenie czasu) w tym, co zostało z budżetu (ponowienia pierwszych źródeł
    nie zabierają czasu pozostałym); każde zapytanie z twardym limitem łącznego czasu (_stopy_raz).
    → ({'wyniki': [...], 'brak': błędy odczytu nieujęte w powodach banków albo None}, uwagi)."""
    now = now or NOW
    Fs, bs, Bl = {}, [], {}
    t0 = zegar()

    def blad(nm, ids, e):
        t = f'{nm}: {str(e)[:60]}'
        bs.append(t)
        Bl.update({i: t for i in ids})
    zr = [('NY Fed', STOPY_NYFED, stopy_nyfed, ('NYFED_LO', 'NYFED_HI'), 20, None),   # v242: źródło banku najpierw, bez klucza
          ('EBC', STOPY_ECB, lambda b: {'ECB_DFR': stopy_ecb_csv(b)}, ('ECB_DFR',), 20, {'Accept': 'text/csv'})]
    zr += [(nm, url, fn, ids, 15, None) for nm, url, fn, ids in stopy_adresy(now)]   # v244: kolejne banki u źródła
    ponow = []
    for z in zr:   # faza 1: każde źródło raz
        nm, url, fn, ids, tm, hd = z
        if zegar() - t0 + tm > STOPY_BUDZET_S:
            blad(nm, ids, 'pominięte — limit czasu kontroli stóp')
            continue
        try:
            Fs.update(fn(_stopy_raz(url, tm, hd)))
        except Exception as e:  # noqa
            if stopy_ponowic(e):
                ponow.append((z, e))
            else:
                blad(nm, ids, e)
    if ponow:   # faza 2 (v245/v248): jedno ponowienie błędów chwilowych, w tym, co zostało z budżetu
        spij(STOPY_PAUZA_S)
    for (nm, url, fn, ids, tm, hd), e0 in ponow:
        if zegar() - t0 + tm > STOPY_BUDZET_S:
            blad(nm, ids, e0)   # brak czasu na ponowienie — pierwotny błąd
            continue
        try:
            Fs.update(fn(_stopy_raz(url, tm, hd)))
        except Exception as e:  # noqa
            blad(nm, ids, e)
    Ps = stopy_porownanie(stopy, Fs, now, bledy=Bl)
    bez = {o['bank'] for o in Ps if o.get('powod') in ('odczyt', 'seria')}   # v243/v246: seria nie sięga dnia strony albo źródło nieodczytane
    od_s = (now.date() - dt.timedelta(days=STOPY_OD_DNI)).isoformat()
    ids_f = sorted({i for a, (ids, nm) in STOPY_FRED.items() if nm in bez for i in ids if i not in Fs})
    for sid in ids_f:   # zapas FRED tylko dla banków bez porównania (v245: w budżecie, bez ponowienia — z serwerów GitHub zwykle nie odpowiada)
        try:
            if zegar() - t0 + 30 > STOPY_BUDZET_S:
                raise TimeoutError('pominięte — limit czasu kontroli stóp')
            x = ust_fred_csv(_stopy_raz(STOPY_FRED_URL.format(id=sid, od=od_s), 30).decode('utf-8', 'replace'))
            if not x:   # v246: strona HTML z kodem 200 — błąd, nie cisza
                raise ValueError('plik bez liczb')
            Fs[sid] = x
        except Exception as e:  # noqa
            blad(sid, (sid,), e)
    if ids_f:
        Ps = stopy_porownanie(stopy, Fs, now, bledy=Bl)
    uz = {e for o in Ps for e in o.get('bledy') or []}   # v246: błędy ujęte w powodach banków nie powtarzają się na końcu wiersza; bez ucinania
    reszta = [e for e in dict.fromkeys(bs) if e not in uz]
    return {'wyniki': Ps, 'brak': '; '.join(reszta) if reszta else None}, stopy_uwagi(Ps, now)


def stopy_wiersz(sp, now=None):
    """v241: wiersz raportu z Z['stopy'] — porównanie albo brak odczytu (informacja, nigdy „zgodne”); zmiana stopy, której strona jeszcze nie
    ma: ℹ️ do STOPY_ZWLOKA_DNI dni, potem ⚠️ (jak uwaga). v243: bank bez porównania widoczny, z powodem. v244: zmiana także przy braku
    porównania (seria banku zaczyna się po dniu strony — NBP podaje tylko stopę obowiązującą)."""
    now = now or NOW
    n = lambda x: format(x, 'g').replace('.', ',')  # noqa: E731
    W = sp.get('wyniki') or []
    if not W:
        return f'- Stopy banków centralnych (strona vs źródło banku): brak odczytu ({sp.get("brak") or "brak wspólnych danych"}) ℹ️.'

    def stara(o):
        z = o.get('zmiana')
        return bool(z) and (now.date() - dt.date.fromisoformat(z[0])).days > STOPY_ZWLOKA_DNI

    def poz(o):
        z = o.get('zmiana')
        if z and o.get('od_poczatku'):   # v246: inna stopa już na początku danych źródła — dzień zmiany nieznany
            zm = f' (już {n(z[1])}% na początku danych źródła ({z[0]}) — strona jeszcze bez tej stopy)'
        else:
            zm = f' (zmiana {z[0]} na {n(z[1])}% — strona jeszcze bez niej)' if z else ''
        if o.get('brak'):
            return f'{o["bank"]}: brak porównania ({o["brak"]}) ' + ('⚠️' if stara(o) else 'ℹ️') + zm
        znak = '⚠️' if not o['zgodne'] or stara(o) else ('ℹ️' if z else '✅')
        return (f'{o["bank"]} {n(o["strona"])}% ' + ('= ' if o['zgodne'] else '≠ ') + f'{n(o["fred"])}% ({o.get("zrodlo") or "FRED"}) '
                + znak + zm)
    bez = [o for o in W if o.get('brak')]
    return ('- Stopy banków centralnych (strona vs źródło banku, ten sam dzień): '
            + '; '.join(poz(o) for o in [o for o in W if not o.get('brak')] + bez)
            + (f'; błędy odczytu: {sp["brak"]}' if bez and sp.get('brak') else '') + '.')


def stopy_uwagi(P, now=None):
    """v241: uwagi z wyniku stopy_porownanie — różnica w tym samym dniu; zmiana stopy starsza niż STOPY_ZWLOKA_DNI, której strona nie ma
    (v244: także przy braku porównania — seria banku zaczyna się po dniu strony). Bank bez porównania i bez zmiany — tylko informacja (v243)."""
    now = now or NOW
    n = lambda x: format(x, 'g').replace('.', ',')  # noqa: E731
    out = []
    for o in P or []:
        if not o.get('brak') and not o.get('zgodne'):
            out.append(f'stopy banków centralnych: {o["bank"]} na stronie {n(o["strona"])}% vs {o.get("zrodlo") or "FRED"} {n(o["fred"])}% ({o["data"]}) — sprawdzić plik stóp strony')
        z = o.get('zmiana')
        if z and o.get('od_poczatku'):   # v246: dzień zmiany nieznany — plik strony nie ma stopy tego banku od miesięcy (uwaga od razu)
            out.append(f'stopy banków centralnych: {o["bank"]} — źródło podaje {n(z[1])}% już na początku swoich danych ({z[0]}), strona pokazuje '
                       f'stopę z {o["data"]} ({n(o["strona"])}%); plik stóp strony nie aktualizuje tego banku od miesięcy — sprawdzić')
        elif z and (now.date() - dt.date.fromisoformat(z[0])).days > STOPY_ZWLOKA_DNI:
            out.append(f'stopy banków centralnych: {o["bank"]} zmienił stopę {z[0]} na {n(z[1])}% — strona pokazuje stopę z {o["data"]} '
                       f'({n(o["strona"])}%); źródło strony spóźnia się — zwykle samo się wyrówna')
    return out


# v225: kursy walut — migawki pliku strony (rynki.json fx: now/1D/1T/1M/1Q/1R, waluta za 1 USD; kurs EBC przez serwis pośredni) vs H.10 Fed
# (kursy w południe w Nowym Jorku, wydawane raz w tygodniu; bez klucza) — te same dni. Inna godzina ustalenia kursu (EBC 14:15 we Frankfurcie),
# więc małe różnice są normalne (06.10.2026: 3 daty × 20 walut, mediana 0,09%, najwięcej 0,79% — peso meksykańskie). v227: progi z 5 lat
# poprawnych danych (1 234 wspólne daty 10.2021–10.2026): największa różnica waluty 3,65% (jen 21.10.2022 — interwencja), najwyższa mediana dnia
# 1,85% (10.11.2022 — dane o inflacji w USA między ustaleniami kursów); progi 1,5% / 0,4% z v225 dawały ⚠️ w ok. 10% dni.
FX_H10 = ('https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&series=60f32914ab61dfab590e0e470153e3ae&lastobs=300&from=&to='
          '&filetype=csv&label=include&layout=seriescolumn&type=package')   # v227: 300 obserwacji (ok. 14 mies., ok. 57 KB) — też migawki 1Q i 1R
FX_PROG = 5.0      # % — waluta ponad tyle od H.10 tego samego dnia = ⚠️ (grube błędy: odwrócony kurs, zła jednostka; nigdy ❌)
FX_MED = 2.5       # % — mediana różnic jednej daty ponad tyle = ⚠️ (np. waluta bazowa źle podpisana); migawka sprzed tygodnia/miesiąca
#                    prawie nigdy nie przekracza progów (sprawdzone v231) — to kontrola grubych błędów, nie dat
FX_MIN_N = 5       # najmniej wspólnych walut, żeby oceniać medianę dnia
FX_MIGAWKI = ('now', '1D', '1T', '1M', '1Q', '1R')
CENA_PROG = 1.0      # % różnicy cen BTC/ETH między źródłami
ETF_PROG = 1.0       # % różnicy zamknięcia ETF tej samej daty: Twelve Data (ceny.json, mapa) vs Massive/Tiingo (indeksy.json → etf) — v117.1
TGA_PROG = 1.0       # pkt proc. — v293: przy WDTGAL (stan na środę) próg stały różnicy; przy WTREGEN (plik sprzed v293) — odchylenie dzisiejszej różnicy TGA (Fiscal Data vs FRED WTREGEN, ta sama data) od mediany 30 dni; różnica sama w sobie
                     # jest stała (~3%: H.4.1 liczy zobowiązanie Fed na środę, DTS — gotówkę operacyjną Skarbu), więc próg 1% na poziomach świeciłby codziennie
                     # v296 (runda 2, test wsteczny progu stałego 1%, 07.10.2026): 554 wspólne środy 06.01.2016–30.09.2026 — FRED WDTGAL wobec salda
                     # zamknięcia TGA z DTS (do 09.2021 „Federal Reserve Account”, 10.2021–04.2022 „Treasury General Account (TGA)”, od 18.04.2022
                     # „TGA Closing Balance”): różnica > 1%: 0 (0,00%), różnica ≠ 0: 0 — równe co do jednostki; środy świąteczne (19.06.2024, 25.12.2024,
                     # 01.01.2025): FRED podaje saldo z dnia roboczego przed nią, DTS nie ma wiersza — porównanie bierze poprzednią wspólną środę
WH_PROG = 5.0        # % — |zmiana salda − przelewy netto| wobec większej z tych liczb
WH_MIN_USD = 1e6     # poniżej miliona USD rozbieżność nie jest uwagą (przelewy < 1 mln nie są skanowane)
HIST_N = 30          # przechowywane przebiegi w historia.json
HIST_CZERWONE = 3    # tyle kolejnych przebiegów z błędami zbieracza = czerwone
# v130: ETF krypto u źródła (bez klucza). Pliki funduszy emitenta IBIT i ETHA (Excel 2003 XML, arkusz „Historical”: As Of, NAV per Share,
# Shares Outstanding) → przepływ dnia D = (jednostki z wiersza D+1 − jednostki z wiersza D) × NAV z dnia D: wiersz „As Of” D+1 zawiera
# jednostki utworzone w sesji D (sprawdzone 27.09 na 7 sesjach IBIT i 2 ETHA). Strona pokazuje przepływ funduszu tylko dla ostatniej sesji
# (data/etf.json → assets[btc|eth].funds[].d1 dla `asof`), więc każdy przebieg zapisuje go w kontrola/etf-emitent.csv, a porównanie dnia D
# rusza, gdy plik emitenta ma już wiersz następnej sesji (przy kontroli o 06:20 UTC zwykle dzień po zapisie). Wynik najwyżej ⚠️ (nigdy ❌
# ani BŁĄD); do raportu idą tylko różnice i daty. Zestawienie niezależnego serwisu z planu v128 odrzucone: sonda z serwera GitHub w USA
# (27.09) dostała 403 (wyzwanie Cloudflare) dla każdego identyfikatora — z Actions nie da się go odczytać, a zabezpieczeń nie obchodzimy.
EM_DOC = ('https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appType=PRODUCT_PAGE'
          '&appSubType=ISHARES&targetSite=us-ishares&locale=en_US&portfolioId={pid}&component=fundDownload&userType=individual')
EM_FUNDS = (('IBIT', 'btc', '333011'), ('ETHA', 'eth', '337614'))   # symbol, aktywo w etf.json, numer pliku funduszu (jak w zbieraczu, v90)
EM_CSV = 'etf-emitent.csv'
EM_KOL = ['date', 'ticker', 'site_flow_musd', 'read_at']   # tylko liczby ze strony (pusta komórka = brak, nigdy 0) i czas ich odczytu
EM_DNI = 60            # tyle ostatnich dat trzyma zapis
EM_SESJE = 5           # okno porównania: ostatnie zapisane sesje, które plik emitenta już rozlicza (różnica w oknie = ⚠️ przez ok. tydzień)
EM_TOL_MLN, EM_TOL_PCT = 0.5, 2.0    # zgodne, gdy |strona − emitent| ≤ max(0,5 mln USD; 2% |emitent|)
EM_NAV_SKOK = 30.0     # % — większy skok NAV między sąsiednimi wierszami = podział jednostek albo błąd pliku: dzień pominięty
EM_PRZERWA = 5         # dni — następny wiersz pliku dalej niż to = dzień pominięty (brak wierszy w pliku)
EM_ZALEGLOSC = 2       # sesje — strona ma więcej sesji nowszych niż ostatni wiersz pliku emitenta = plik nieaktualny (zwykle 0; 1 = wiersz jeszcze
                       # nieopublikowany): status „?” i uwaga, bo porównanie obejmuje wtedy tylko stare sesje, a nowsze czekają bez sprawdzenia
EM_TIMEOUT = 45        # s na plik (ok. 250 KB; z USA ok. 0,6 s)
EM_PAUZA = 1.0         # s przerwy między dwoma zapytaniami do tego samego serwera


# v327 (KON-04): wspólny termin całej kontroli (zegar monotoniczny). Zadanie ma limit 12 min, a po pushu najpierw czeka 300 s na publikację;
# przy wiszącej stronie ok. 56 zapytań po 25 s trwało 20–24 min — GitHub zabijał zadanie i nie powstawał ani raport, ani wpis w historii.
# Teraz każde zapytanie dostaje najwyżej tyle czasu, ile zostało do terminu; po terminie zapytania nie wychodzą (KoniecCzasu), po 3 kolejnych
# przekroczeniach czasu przy stronie reszta jej plików jest pomijana jedną uwagą, a raport (także częściowy) zapisuje main() zawsze — z BŁĘDEM
# „kontrola przerwana: limit czasu”. Zwykle kontrola trwa ok. 1 min (przeglądarka do 2 × 90 s).
TERMIN_S = 480           # s — zwykły przebieg: 12 min zadania minus maszyna, zapis wyniku i przerwanie awaryjne
TERMIN_PUSH_S = 300      # s — przebieg po pushu: po czekaniu 300 s zostaje 420 s
TERMIN_TWARDY_S = 45     # s po terminie — przerwanie awaryjne sygnałem (jedno zapytanie albo przeglądarka nie oddały sterowania)
TERMIN_MIN_S = 2         # s — mniej do terminu = zapytanie już nie wychodzi
SITE_PRZEKR_MAX = 3      # kolejne przekroczenia czasu przy stronie = reszta jej plików pominięta (jedna uwaga zamiast kilkudziesięciu)
PONOW_S = 7              # v327 (KON-05): s — przerwa przed jedną ponowną próbą strony głównej i pliku stanu (5xx albo przekroczenie czasu)
_TERMIN = {'t0': None, 's': None, 'przekroczony': False, 'site_przekr': 0}
_R_BIEZACY = [None]      # v327: wynik kontroli w toku — przy przerwaniu raport częściowy z tego, co już sprawdzono


class KoniecCzasu(TimeoutError):
    """v327 (KON-04): zapytanie po terminie całej kontroli albo przerwanie awaryjne — kontrola kończy się raportem częściowym."""


def termin_start(s=None):
    """v327: początek odliczania (kontrola() na starcie); s=None — TERMIN_PUSH_S po pushu (GITHUB_EVENT_NAME), inaczej TERMIN_S."""
    if s is None:
        s = TERMIN_PUSH_S if os.environ.get('GITHUB_EVENT_NAME') == 'push' else TERMIN_S
    _TERMIN.update(t0=time.monotonic(), s=float(s), przekroczony=False, site_przekr=0)
    return s


def termin_zostalo():
    """v327: sekundy do terminu całej kontroli; None — termin nie ustawiony."""
    if _TERMIN['t0'] is None:
        return None
    return _TERMIN['s'] - (time.monotonic() - _TERMIN['t0'])


def termin_czas(s, zapas=30):
    """v327: najwyżej s sekund, ale tak, żeby przed terminem zostało jeszcze `zapas` s (przeglądarka); bez terminu — s."""
    z = termin_zostalo()
    return s if z is None else max(0.0, min(s, z - zapas))


def _przekroczenie(e):
    """v327: przekroczenie czasu (także owinięte w URLError) — nie błąd serwera."""
    return isinstance(e, TimeoutError) or (isinstance(e, urllib.error.URLError) and isinstance(e.reason, TimeoutError))


def site_pomin():
    """v327: powód pominięcia kolejnego zapytania do strony (strona wisi albo minął termin) albo None."""
    if _TERMIN['przekroczony']:
        return 'limit czasu całej kontroli'
    if _TERMIN['site_przekr'] >= SITE_PRZEKR_MAX:
        return f'strona nie odpowiada w czasie — {SITE_PRZEKR_MAX} kolejne przekroczenia czasu'
    return None


def get(url, timeout=25, headers=None, limit=None):
    zost = termin_zostalo()   # v327 (KON-04): limit zapytania skrócony do czasu, który został do terminu całej kontroli
    if zost is not None:
        if zost < TERMIN_MIN_S:
            _TERMIN['przekroczony'] = True
            raise KoniecCzasu(f'limit czasu całej kontroli ({_TERMIN["s"]:g} s)')
        timeout = min(timeout, zost)
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalFlowAI-kontrola/1.0', **(headers or {})})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read() if limit is None else r.read(limit)   # v237: limit — najwyżej tyle bajtów (sprawdzanie, czy plik jest)
            st = r.status
    except Exception as e:
        if url.startswith(SITE) and _przekroczenie(e):   # v327: kolejne przekroczenia czasu przy stronie (inna odpowiedź zeruje licznik)
            _TERMIN['site_przekr'] += 1
        elif url.startswith(SITE):
            _TERMIN['site_przekr'] = 0
        raise
    if url.startswith(SITE):
        _TERMIN['site_przekr'] = 0
    return st, body, int((time.monotonic() - t0) * 1000)


def get_ponow(url, ponow_s=None):
    """v327 (KON-05): strona główna i plik stanu — jedno ponowienie po PONOW_S s przy błędzie chwilowym (5xx albo przekroczenie czasu), jeśli
    zmieści się przed terminem kontroli; BŁĄD dopiero po drugiej porażce (dotąd jeden chwilowy 503 GitHub Pages = czerwony e-mail). Inne błędy
    (404, błąd sieci, termin) — od razu, jak dotąd."""
    ponow_s = PONOW_S if ponow_s is None else ponow_s
    try:
        return get(url)
    except KoniecCzasu:
        raise
    except Exception as e:  # noqa
        zost = termin_zostalo()
        if not stopy_ponowic(e) or (zost is not None and zost < ponow_s + TERMIN_MIN_S + 1):
            raise
    time.sleep(ponow_s)
    return get(url)


def get_json(url, timeout=25):
    return json.loads(get(url, timeout)[1])


def wiek_min(iso):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return max(0, int((NOW - t).total_seconds() // 60))
    except Exception:
        return None


def _pl_przesuniecie_h(u):
    """v202: przesunięcie czasu polskiego bez bazy stref (reguła UE): czas letni od ostatniej niedzieli marca do ostatniej niedzieli października,
    zmiana o 01:00 UTC → 2, inaczej 1. `u` — chwila ze strefą."""
    u = u.astimezone(dt.timezone.utc)

    def last_sun(y, m):
        d = dt.date(y, m, 31)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    a = dt.datetime.combine(last_sun(u.year, 3), dt.time(1), dt.timezone.utc)
    b = dt.datetime.combine(last_sun(u.year, 10), dt.time(1), dt.timezone.utc)
    return 2 if a <= u < b else 1


def czas_pl(iso):
    """Czas polski (v202: Europe/Warsaw — latem UTC+2, zimą UTC+1; dotąd stałe UTC+2); zapis bez strefy = UTC; zły zapis = „—”."""
    try:
        t = dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            t = t.astimezone(ZoneInfo('Europe/Warsaw'))
        except Exception:   # brak bazy stref — reguła UE
            t = t.astimezone(dt.timezone(dt.timedelta(hours=_pl_przesuniecie_h(t))))
        return t.strftime('%d.%m.%Y, %H:%M')
    except Exception:
        return '—'


AW_UWAGA_H = 3        # v207: część automatu nie działa co najmniej tyle godzin (seria trwa) = ⚠️ z datą początku
AW_BLAD_H = 48        # v207: … co najmniej tyle godzin = BŁĄD (e-mail do właściciela): automat nie naprawił tego sam
AW_INFO_H = 24        # v207: awarie naprawione w ostatnich tylu godzinach — informacja ℹ️ (samonaprawa widoczna w raporcie)
AW_KLUCZ = re.compile(r'klucz\w*(?:\s+\S+)?\s+odrzuc|zły klucz|unauthori[sz]ed|HTTP\D{0,7}401\b|(?:invalid|incorrect) api ?key', re.I)
AW_LIMIT = re.compile(r'HTTP\D{0,7}(?:429|402)\b|too many requests|rate limit|credits|limit zapytań(?! w przebiegu)|dobowy limit|limit planu', re.I)   # v211: bez własnego limitu zbieracza
AW_BEZ_BLEDU = {   # v211/v215: części bez czerwieni z serii awarii — seria tylko informacją (wiek danych ocenia wiersz świeżości); v215: snb usunięte (False = błąd pobrania)
    'ici': 'fundusze USA — z założenia bez czerwieni (v134); wiek danych w wierszu świeżości', 'jpx': 'Japonia — tydzień czeka na publikację giełdy',
    'wycena_bg': 'dodatek SOPR — limit planu źródła (v132)',
    'surowce_ceny': 'surowce — część z błędem zostaje z datą (v295); wiek danych w wierszach świeżości',
    'surowce_zapasy': 'surowce — część z błędem zostaje z datą (v295); wiek danych w wierszach świeżości',
    'surowce_mies': 'surowce — część z błędem zostaje z datą (v295); wiek danych w wierszach świeżości',
    'surowce_pozycje': 'surowce — część z błędem zostaje z datą (v298); wiek danych w wierszach świeżości',
    'surowce_fundusze': 'surowce — część z błędem zostaje z datą (v298); wiek danych w wierszach świeżości',
    'surowce_banki': 'surowce — część z błędem zostaje z datą (v298); wiek danych w wierszach świeżości'}


AW_BEZ_BLEDU.update({'szlaki_' + p: 'szlaki — część z błędem zostaje z datą (v305); wiek danych w wierszach świeżości'
                     for p in ('cies', 'presja', 'bcpi')})

AW_BEZ_BLEDU.update({'polska_' + p: 'Polska — część z błędem zostaje z datą (v304); wiek danych w wierszach świeżości'
                     for p in ('zloto', 'hurt', 'energia', 'stacje', 'pszenica')})

AW_BEZ_BLEDU.update({'surowce_raporty_' + p: 'surowce — raport miesięczny z błędem zostaje z datą (v320); wiek danych w wierszach świeżości'
                     for p in ('ropa', 'zboza', 'uran')})

AW_BEZ_BLEDU.update({'zboza_dzien_' + p: 'zboża dziennie — część z błędem zostaje z datą (v341); wiek danych w wierszach świeżości'
                     for p in ('goi', 'fracht', 'fao', 'ue', 'nawozy')})
AW_BEZ_BLEDU.update({'metale_' + p: 'metale — część z błędem zostaje z datą (v339); wiek danych w wierszach świeżości'
                     for p in ('lme', 'sh', 'shd', 'shw', 'cu')})


def _aw_t(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t.astimezone(dt.timezone.utc) if t.tzinfo else None


def _aw_h(h):
    """Godziny → „5 godz.” albo „3 dni 2 godz.” (pełne godziny w dół)."""
    h = int(h)
    return f'{h // 24} {"dzień" if h // 24 == 1 else "dni"} {h % 24} godz.' if h >= 24 else f'{h} godz.'


def awaria_rodzaj(e):
    """v207: błąd zbieracza → dopisek dla właściciela: odrzucony klucz (automat sam tego nie naprawi), limit planu (zwykle mija sam) albo ''."""
    e = str(e)
    if AW_KLUCZ.search(e):
        return ' — wygląda na odrzucony klucz: automat sam tego nie naprawi (co zrobić: napisz do Claude „sprawdź klucz z tego błędu”)'
    if AW_LIMIT.search(e):
        return ' — limit darmowego planu: zwykle mija sam (automat ponawia); jeśli trwa ponad 2 dni — napisz do Claude'
    return ''


def awarie_ocena(meta, now=None):
    """v207/v211: pole 'awarie' z meta.json (pamięć zbieracza między przebiegami) → {'trwa', 'naprawione', 'zniknely', 'uwagi', 'bledy'};
    element: {'czesc', 'od', 'ost', 'n', 'do', 'h'[, 'bez']} (h — godziny serii: do ostatniego przebiegu automatu (meta.at; nie dalej niż
    teraz) albo do końca serii). Seria trwa ≥ AW_BLAD_H h = błąd (automat nie naprawił tego sam), ≥ AW_UWAGA_H h = uwaga, krótsza —
    informacja; części z AW_BEZ_BLEDU — zawsze informacja ('bez'); zamknięte w ostatnich AW_INFO_H h — „naprawione” albo „zniknęły” (zn);
    poprzednia zamknięta seria (prev) — także w „naprawionych”. Brak pola (zbieracz sprzed v207) albo zły typ = None; złe wpisy pomijane."""
    now = now or NOW
    aw = meta.get('awarie') if isinstance(meta, dict) else None
    if not isinstance(aw, dict):
        return None
    ma = _aw_t(meta.get('at'))
    kon = min(now, ma) if ma else now
    Z = {'trwa': [], 'naprawione': [], 'zniknely': [], 'uwagi': [], 'bledy': []}
    for k, w in sorted(aw.items()):
        if not isinstance(w, dict):
            continue
        od, ost, n = _aw_t(w.get('od')), _aw_t(w.get('ost')), w.get('n')
        do = _aw_t(w.get('do')) if w.get('do') is not None else None
        if od is None or ost is None or not isinstance(n, int) or isinstance(n, bool) or n < 1 or (w.get('do') is not None and do is None):
            continue
        h = max(0.0, ((do or kon) - od).total_seconds() / 3600)
        x = {'czesc': str(k)[:40], 'od': w['od'], 'ost': w['ost'], 'n': n, 'do': w.get('do'), 'h': round(h, 1)}
        if do is None:
            x['bez'] = k in AW_BEZ_BLEDU
            Z['trwa'].append(x)
            opis = f'część automatu „{x["czesc"]}” nie działa od {czas_pl(w["od"])} ({_aw_h(h)}, nieudanych przebiegów z rzędu: {n})'
            if x['bez']:
                pass
            elif h >= AW_BLAD_H:
                Z['bledy'].append(opis + ' — automat nie naprawił tego sam; co zrobić: napisz do Claude „napraw część ' + x['czesc'] + '”')
            elif h >= AW_UWAGA_H:
                Z['uwagi'].append(opis + ' — automat ponawia sam; dane tej części mają swój wiek na stronie')
        elif (now - do).total_seconds() <= AW_INFO_H * 3600:
            Z['zniknely' if w.get('zn') is True else 'naprawione'].append(x)
        p = w.get('prev')
        if isinstance(p, list) and len(p) == 3:
            po, pd_, pn = _aw_t(p[0]), _aw_t(p[1]), p[2]
            if (po and pd_ and pd_ >= po and isinstance(pn, int) and not isinstance(pn, bool) and pn >= 1
                    and (now - pd_).total_seconds() <= AW_INFO_H * 3600):
                Z['naprawione'].append({'czesc': str(k)[:40], 'od': p[0], 'ost': p[1], 'n': pn, 'do': p[1], 'h': round((pd_ - po).total_seconds() / 3600, 1)})
    Z['naprawione'].sort(key=lambda x: (x['czesc'], x['od']))
    return Z


# v212: rodzaj BŁĘDU (początek treści) → co zrobić — prostymi słowami dla właściciela; kolejność = pierwszeństwo dopasowania
CO_ZROBIC = (   # v215: dopasowania po przeglądzie — „HTTP 200” i „bez czasu” osobno, publikacja Pages osobno, świeżość bez „to normalne”
    (re.compile(r'^strona główna: HTTP 200'),
     'Strona odpowiada, ale jej treść jest niepełna (nieudana publikacja) — napisz do Claude: „strona ma złą treść — sprawdź kontrolę”.'),
    (re.compile(r'^(strona główna|plik stanu \(meta\.json\) nie odpowiada)'),
     'Strona albo jej plik stanu nie odpowiada. Zwykle to chwilowa awaria serwera GitHub — sprawdź stronę za godzinę (stan serwera: githubstatus.com). '
     'Jeśli trwa ponad 3 godziny, napisz do Claude: „strona nie działa — sprawdź kontrolę”.'),
    (re.compile(r'^plik stanu bez czasu'),
     'Plik stanu automatu jest uszkodzony (bez czasu przebiegu) — to błąd w kodzie, sam się nie naprawi. Napisz do Claude: „plik stanu bez czasu”.'),
    (re.compile(r'^automat nie odświeżył danych'),
     'Automat nie odświeża danych od ponad 3 godzin — zegar zapasowy też nie pomógł. Najczęściej to przerwa po stronie GitHub (stan: githubstatus.com); '
     'jeśli trwa ponad 6 godzin, napisz do Claude: „automat stoi”.'),
    (re.compile(r'^publikacja zawieszona'),   # v232: przebieg czeka na środowisko, choć nikt nie musi zatwierdzać
     'Przebieg publikacji czeka na „zatwierdzenie”, którego nikt nie wymaga (usterka po stronie GitHub), a zegar zapasowy go nie anulował — '
     'dopóki czeka, strona nie dostaje nowych danych. Otwórz na GitHub zakładkę Actions, przebieg „Strona i dane” ze stanem „Waiting” '
     '→ „Cancel workflow”; następny przebieg ruszy sam w ciągu 10–20 min. Jeśli to wraca, napisz do Claude: „publikacja zawieszona”.'),
    (re.compile(r'^automat nie działa \(publikacja GitHub Pages\)'),   # v219: tylko seria samych porażek publikacji (przebiegi_ocena)
     'Ostatnie przebiegi padły na publikacji strony — to zwykle chwilowa awaria po stronie GitHub. Sprawdź za 1–2 godziny; jeśli trwa dłużej, '
     'napisz do Claude: „publikacja strony nie działa”.'),
    (re.compile(r'^automat nie działa'),
     'Ostatnie przebiegi automatu kończą się błędem. Napisz do Claude: „przebiegi automatu kończą się błędem”.'),
    (re.compile(r'^część automatu „'),
     'Część automatu nie działa od ponad 2 dni (szczegóły niżej) — napisz do Claude tak, jak podpowiada wiersz błędu.'),
    (re.compile(r'^zbieracz zgłasza błędy'),
     'Zbieracz od kilku dni zgłasza błędy — napisz do Claude: „napraw błędy zbieracza z kontroli”.'),
    (re.compile(r'^kapitalizacja krypto'),
     'Dwa źródła tej samej liczby bardzo się różnią — jedno może podawać złe dane. Napisz do Claude: „sprawdź różnicę źródeł z kontroli”.'),
    (re.compile(r': dane z .* temu \('),
     'Dane źródła są dużo starsze niż zwykle (ponad dwa razy dłużej niż norma; weekendy już odliczone) — źródło przestało publikować '
     '(np. przerwa w pracy urzędu) albo automat nie może ich pobrać. Napisz do Claude: „sprawdź źródło z kontroli”.'),
    (re.compile(r'^limit planu '),   # v222: licznik zużycia darmowych planów
     'Darmowy plan jednego źródła danych jest (prawie) wyczerpany — część liczb może chwilowo zniknąć, aż limit się odnowi (o północy UTC '
     'albo z nowym miesiącem); nic nie psuje się na stałe. Napisz do Claude: „zmniejsz liczbę zapytań — limit planu z kontroli”.'),
    (re.compile(r'^kontrola przerwana'),   # v327 (KON-04): wspólny termin kontroli albo nieoczekiwana awaria samej kontroli
     'Kontrola nie zdążyła sprawdzić wszystkiego (strona albo serwery odpowiadały bardzo wolno) — raport jest częściowy. Zwykle to chwilowe; '
     'sprawdź stronę za godzinę. Jeśli powtarza się kilka dni, napisz do Claude: „kontrola przerwana — sprawdź”.'),
)
CO_ZROBIC_INNE = 'Napisz do Claude: „sprawdź błąd z kontroli” — w raporcie niżej jest jego treść.'
WAIT_UWAGA_MIN, WAIT_BLAD_MIN = 30, 120   # v232: przebieg „Strona i dane” w stanie waiting tak długo — uwaga / błąd (zegar anuluje po 15 min)


def co_zrobic(bledy):
    """v212: treści BŁĘDÓW → lista podpowiedzi „co zrobić” (każda raz, w kolejności pierwszego błędu danego rodzaju; nieznany — ogólna)."""
    out = []
    for b in bledy or []:
        h = next((x for r, x in CO_ZROBIC if r.search(str(b))), CO_ZROBIC_INNE)
        if h not in out:
            out.append(h)
    return out


def fmt_wiek(m):
    """Minuty → „0 h 34 min” / „2 d 3 h” / „—”."""
    if m is None:
        return '—'
    if m < 60 * 48:
        return f'{m // 60} h {m % 60:02d} min'
    return f'{m // 1440} d {(m % 1440) // 60} h'


# ---------------------------------------------------------------- v115: świeżość źródeł ----------------------------------------------------------------
def godziny_robocze(od, do):
    """Godziny między od i do (UTC) bez sobót i niedziel — dane dzienne nie starzeją się przez weekend."""
    if do <= od:
        return 0.0
    h, t = 0.0, od
    while t < do:
        nxt = min(do, (t + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))
        if t.weekday() < 5:
            h += (nxt - t).total_seconds() / 3600
        t = nxt
    return h


def data_danych(name, j):
    """Data/czas danych z pliku wg jego kształtu → (tekst daty, rodzaj: 'ts' | 'day' | 'month') albo None."""
    try:
        if name in ('rynki', 'dzwignia'):
            pa = j.get('part_at') or {}
            if name == 'dzwignia':   # v126: część `cz` (źródło zbiorcze, dobierana co przebieg) nie świadczy o świeżości odczytów bezpośrednich
                pa = {k: x for k, x in pa.items() if k != 'cz'}
            v = max((x for x in pa.values() if isinstance(x, str)), default=None)
            return (v, 'ts') if v else None
        if name == 'premie':   # v128: najnowsza minuta odczytu na żywo (koniec okna) spośród bloków now.*
            N = j.get('now') or {}
            v = max((B['win'][1] for B in N.values() if isinstance(B, dict) and isinstance(B.get('win'), list) and len(B['win']) == 2
                     and isinstance(B['win'][1], str)), default=None)
            return (v, 'ts') if v else None
        if name == 'wieloryby':
            v = (j.get('part_at') or {}).get('salda') or j.get('at')
            return (v, 'ts') if isinstance(v, str) else None
        if name == 'instytucje':
            return (j['tga']['asof'], 'day')
        if name == 'etf':
            return (j['asof'], 'day')
        if name == 'energia':
            d = j['s']['wti']['d']; return (d[-1][0], 'day')
        if name == 'cftc':
            return (j['asof'], 'day')
        if name == 'tic':
            return (j['asof'], 'month')
        if name == 'oecd':
            last = None
            for part in ('cli', 'irlt', 'share'):
                for rows in (j.get(part) or {}).values():
                    if rows and isinstance(rows[-1], list):
                        last = max(last or '', str(rows[-1][0]))
            return (last, 'month') if last else None
        if name == 'usa-makro':
            d = j['s']['cpi']['d']; return (d[-1][0], 'month')
    except Exception:
        return None
    return None


def wiek_danych(txt, kind, kat, now=None):
    """Wiek danych w minutach dla kategorii progu: 'ts' → od znacznika czasu; 'day' → od końca dnia danych; 'month' → od końca
    miesiąca danych; kategoria 'd' liczy godziny robocze (bez sobót i niedziel). None = nie da się policzyć."""
    now = now or NOW
    try:
        if kind == 'ts':
            t = dt.datetime.fromisoformat(str(txt).replace('Z', '+00:00'))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return max(0, int((now - t).total_seconds() // 60))
        if kind == 'day':
            d = dt.datetime.fromisoformat(str(txt)[:10]).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
        else:   # month 'YYYY-MM' → pierwszy dzień następnego miesiąca
            y, m = int(str(txt)[:4]), int(str(txt)[5:7])
            d = dt.datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=dt.timezone.utc)
        if kat == 'd':
            return int(godziny_robocze(d, now) * 60)
        return max(0, int((now - d).total_seconds() // 60))
    except Exception:
        return None


def ocena(wiek, prog):
    if wiek is None:
        return '?'
    return '❌' if wiek > 2 * prog else ('⚠️' if wiek > prog else '✅')


def swiezosc(files, now=None):
    """files: nazwa → wczytany JSON (albo None). Zwraca listę wierszy tabeli: (etykieta, status, wiek min, data danych, uwaga)."""
    rows = []
    for label, name, kat, prog in SWIEZOSC:
        j = files.get(name)
        if not isinstance(j, dict):
            rows.append((label, '?', None, None, 'plik nie wczytany')); continue
        if name == 'fred':
            sid = 'RRPONTSYD' if kat == 'd' else 'WALCL'
            try:
                txt, kind = j['series'][sid]['asof'], 'day'
            except Exception:
                rows.append((label, '?', None, None, f'brak serii {sid}')); continue
        else:
            dd = data_danych(name, j)
            if not dd:
                rows.append((label, '?', None, None, 'brak daty danych w pliku')); continue
            txt, kind = dd
        w = wiek_danych(txt, kind, kat, now)
        st = ocena(w, prog)
        note = '' if st == '✅' else (f'próg {fmt_wiek(prog)}' + (' (godziny robocze)' if kat == 'd' else '') + (', ponad 2× progu' if st == '❌' else ''))
        rows.append((label, st, w, txt, note))
    return rows


# ---------------------------------------------------------------- v327 (KON-08): zastój źródeł sprawdzanych tylko przy budowie pliku ----------------------------------------------------------------
# Zbieracz zgłasza „brak nowego dnia/miesiąca/komunikatu” tylko w przebiegu, który buduje plik (Meksyk co 6 h, SPW i Korea raz na dobę); potem
# plik „cached” bez błędu w meta.json, więc kontrola trafiała na to zgłoszenie w ok. 3% dni (Meksyk), < 1% (SPW, Korea). Wiek DANYCH w pliku
# strony z tymi samymi progami co zbieracz (osobne wiersze — lista SWIEZOSC bez zmian). Najwyżej ⚠️, nigdy ❌ ani BŁĄD: trwały zastój źródła to nie
# awaria strony, a ❌ z wiersza świeżości po HIST_CZERWONE dniach zrobiłby czerwony wynik.
ZASTOJ = (('Meksyk: obligacje rządu u nierezydentów (dziennie, opóźnienie ok. 1,5 tygodnia)', 'meksyk', 'day'),
          ('Polska: nierezydenci w obligacjach skarbowych (miesięcznie)', 'spw', 'month'),
          ('Korea Płd.: inwestorzy zagraniczni w akcjach i obligacjach (komunikat miesięczny)', 'korea', 'month'))
ZASTOJ_MX_DNI = 21    # = MX_STALE zbieracza: dni bez nowego dnia danych
ZASTOJ_SPW_DNI = 70   # = SPW_STALE zbieracza: dni po końcu najnowszego miesiąca
ZASTOJ_FSS_DNI = 34   # = termin FSS zbieracza: 1. dzień drugiego miesiąca po miesiącu danych + 34 dni


def zastoj_prog(name, txt):
    """v327: próg w minutach od końca dnia/miesiąca danych (jak wiek_danych) — od tej chwili zbieracz zgłasza błąd zastoju; (próg, opis)."""
    if name == 'meksyk':
        return ZASTOJ_MX_DNI * 1440, f'próg {ZASTOJ_MX_DNI} dni bez nowego dnia — jak zbieracz'
    if name == 'spw':
        return ZASTOJ_SPW_DNI * 1440, f'próg {ZASTOJ_SPW_DNI} dni po końcu miesiąca — jak zbieracz'
    y, m = int(txt[:4]), int(txt[5:7])
    nast = dt.date(y + (m == 12), m % 12 + 1, 1)                                  # koniec miesiąca danych (od tej chwili liczy wiek_danych)
    t = y * 12 + m - 1 + 2
    due = dt.date(t // 12, t % 12 + 1, 1) + dt.timedelta(days=ZASTOJ_FSS_DNI)      # zbieracz: błąd, gdy dziś > due
    return ((due - nast).days + 1) * 1440, f'termin komunikatu {due.day:02d}.{due.month:02d}.{due.year} — jak zbieracz'


def zastoj_swiezosc(files, now=None):
    """v327 (KON-08): wiersze (etykieta, status, wiek min, data danych, uwaga) dla plików z ZASTOJ; pliku brak — bez wiersza (brak pliku zgłasza pętla
    plików); brak albo zła data w pliku — „?”. Status najwyżej ⚠️."""
    out = []
    for label, name, kind in ZASTOJ:
        j = files.get(name) if isinstance(files, dict) else None
        if not isinstance(j, dict):
            continue
        txt = j.get('asof')
        wzor = r'^\d{4}-\d{2}-\d{2}$' if kind == 'day' else r'^\d{4}-(0[1-9]|1[0-2])$'
        if not (isinstance(txt, str) and re.match(wzor, txt)) or (kind == 'day' and not _dzien(txt)):
            out.append((label, '?', None, None, 'brak daty danych w pliku')); continue
        prog, opis = zastoj_prog(name, txt)
        w = wiek_danych(txt, kind, 'w', now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        out.append((label, st, w, txt, '' if st == '✅' else opis))
    return out


# ---------------------------------------------------------------- v131: szanse decyzji Fed (rynek zakładów) ----------------------------------------------------------------
FED_ETYKIETA = 'szanse decyzji Fed (rynek zakładów)'
FED_PROG = 90              # min — wiek cen (part_at.ks; automat co 10 min): żółte po progu, czerwone po 2× — osobny wiersz, lista SWIEZOSC bez zmian
FED_SUMA = (0.90, 1.10)    # suma surowych cen wyników posiedzenia poza tym pasmem = uwaga (informacja o jakości cen, bez koloru)


def fed_swiezosc(j, now=None):
    """Wiersz świeżości szans Fed (data/fed.json → part_at.ks) w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data, uwaga);
    brak pliku = None (wiersz pominięty; brak pliku zgłasza pętla wieku plików); wyłącznik KALSHI_OFF = status „—” z opisem (bez uwagi)."""
    if not isinstance(j, dict):
        return None
    if (j.get('ok') or {}).get('ks') == 'off':
        return (FED_ETYKIETA, '—', None, None, 'wyłączone (KALSHI_OFF)')
    v = (j.get('part_at') or {}).get('ks')
    if not isinstance(v, str):
        return (FED_ETYKIETA, '?', None, None, 'brak czasu cen w pliku')
    w = wiek_danych(v, 'ts', 'h', now)
    st = ocena(w, FED_PROG)
    note = '' if st == '✅' else (f'próg {fmt_wiek(FED_PROG)}' + (', ponad 2× progu' if st == '❌' else ''))
    return (FED_ETYKIETA, st, w, v, note)


def fed_uwagi(j):
    """Uwagi o jakości cen Fed (informacja): nieznane wyniki, brak ceny któregoś wyniku albo suma surowych cen posiedzenia poza FED_SUMA."""
    K = j.get('ks') if isinstance(j, dict) and isinstance(j.get('ks'), dict) else {}
    out = []
    for m in K.get('meetings') or []:
        if not isinstance(m, dict):
            continue
        d, s = str(m.get('date') or '?'), m.get('sum_raw')
        if m.get('unknown'):
            out.append(f'Fed {d}: nieznane wyniki ({len(m["unknown"])}) — szanse bez przeliczenia do 100%')
        if s is None:
            out.append(f'Fed {d}: nie każdy wynik ma cenę — surowe ceny bez przeliczenia do 100%')
        elif isinstance(s, (int, float)) and not FED_SUMA[0] <= s <= FED_SUMA[1]:
            out.append(f'Fed {d}: suma surowych cen {s:.3f} poza pasmem {FED_SUMA[0]:.2f}–{FED_SUMA[1]:.2f}')
    return out


# ---------------------------------------------------------------- v132: wycena BTC z łańcucha bloków (MVRV, SOPR) ----------------------------------------------------------------
# Dwa osobne wiersze świeżości (lista SWIEZOSC bez zmian): część cm (MVRV, średnia cena zakupu — dzień danych z wczoraj; dzień D pełny u źródła
# w D+1 ok. 03 UTC) i część bg (SOPR — źródło opóźnia darmowy plan o 7 dni, więc wiek ~6–7 dni jest normą; ten wiersz najwyżej ⚠️, nigdy ❌:
# to dodatek z darmowego planu, jego brak nie jest awarią strony). MVRV z dwóch źródeł (drugie źródło pobierane tylko do tej kontroli): różnica
# r = (drugie / główne − 1) × 100 dla wspólnych dni; norma = mediana r z okna (pomiar 27.09.2026 z 90 dni: mediana +0,84%, zakres +0,60…+1,63%,
# zmiana dzień do dnia p95 0,24 pkt proc.). ✅ gdy |r najnowszego dnia − mediana| ≤ WY_ZG_PP i |mediana| ≤ WY_ZG_MED; inaczej ⚠️ (nigdy błąd).
# Dodatkowe ⚠️, gdy po przesunięciu dat o ±1 dzień mediana |r| spada poniżej WY_ZG_SHIFT × mediany |r| bez przesunięcia — tak wyglądała historia
# drugiego źródła 2023-10…2025-08 (dzień d = dzień d+1 głównego); na historii od 2025-10 reguła nie zgłasza nic (sprawdzone na 341 oknach).
WY_ETYKIETA_CM = 'wycena BTC — MVRV, średnia cena zakupu (dziennie)'
WY_ETYKIETA_BG = 'SOPR BTC (źródło opóźnia 7 dni)'
WY_PROG_CM = 36 * 60          # min od końca dnia danych (kontrola o 06:20 UTC widzi zwykle wczoraj: ~6 h); ❌ po 2× progu
WY_PROG_BG = 9 * 24 * 60      # min od końca dnia danych SOPR (norma ~6 d 6 h); tylko ⚠️
WY_ZG_MIN = 20                # wspólnych dni MVRV — mniej = tylko informacja, bez koloru
WY_ZG_PP = 1.5                # pkt proc.
WY_ZG_MED = 3.0               # %
WY_ZG_SHIFT = 0.67            # przesunięcie dat: mediana |r| po przesunięciu < 0,67 × bez przesunięcia
WY_OPOZN = 7                  # dni opóźnienia darmowego planu drugiego źródła (pomiar 27.09.2026)


def wycena_swiezosc(j, now=None):
    """Wiersze świeżości wyceny BTC w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). Brak pliku = [] (brak
    pliku zgłasza pętla wieku plików); SOPR wyłączony (WYCENA_BG_OFF) = status „—” z opisem (bez uwagi); SOPR nigdy ❌ (najwyżej ⚠️)."""
    if not isinstance(j, dict):
        return []
    rows = []
    C = j.get('cm') if isinstance(j.get('cm'), dict) else {}
    a = C.get('asof')
    if not isinstance(a, str) or len(a) != 10:
        rows.append((WY_ETYKIETA_CM, '?', None, None, 'brak dnia danych w pliku'))
    else:
        w = wiek_danych(a, 'day', 'c', now)      # 'c' = dni kalendarzowe (krypto bez przerwy na weekend)
        st = ocena(w, WY_PROG_CM)
        rows.append((WY_ETYKIETA_CM, st, w, a, '' if st == '✅' else f'próg {fmt_wiek(WY_PROG_CM)}' + (', ponad 2× progu' if st == '❌' else '')))
    B = j.get('bg') if isinstance(j.get('bg'), dict) else {}
    if B.get('off') or (j.get('ok') or {}).get('bg') == 'off':
        rows.append((WY_ETYKIETA_BG, '—', None, None, 'wyłączone (WYCENA_BG_OFF)'))
        return rows
    s = (B.get('sopr') or {}).get('asof') if isinstance(B.get('sopr'), dict) else None
    if not isinstance(s, str) or len(s) != 10:
        rows.append((WY_ETYKIETA_BG, '?', None, None, 'brak dnia danych SOPR w pliku'))
    else:
        w = wiek_danych(s, 'day', 'c', now)
        st = ocena(w, WY_PROG_BG)
        st = '⚠️' if st == '❌' else st
        rows.append((WY_ETYKIETA_BG, st, w, s, '' if st == '✅' else f'próg {fmt_wiek(WY_PROG_BG)} (dodatek z darmowego planu — najwyżej uwaga)'))
    return rows


def wycena_mvrv(j):
    """MVRV z dwóch źródeł (data/wycena.json: cm.d i bg.mvrv.d) → {'status', 'n', 'mediana_pct', 'dzien', 'roznica_pct', 'przesuniecie',
    'opoznienie_d', 'opis', 'uwagi'}. Tylko różnice procentowe i daty (bez liczb drugiego źródła); uwagi najwyżej ⚠️ — nigdy błąd."""
    out = {'status': '?', 'n': 0, 'mediana_pct': None, 'dzien': None, 'roznica_pct': None, 'przesuniecie': False, 'opoznienie_d': None,
           'opis': 'plik nie wczytany', 'uwagi': []}
    if not isinstance(j, dict):
        return out
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') and v > 0   # noqa: E731
    C = j.get('cm') if isinstance(j.get('cm'), dict) else {}
    B = j.get('bg') if isinstance(j.get('bg'), dict) else {}
    if B.get('off'):
        out.update(status='—', opis='drugie źródło wyłączone (WYCENA_BG_OFF)')
        return out
    a = {r[0]: float(r[1]) for r in (C.get('d') or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and num(r[1])}
    M = B.get('mvrv') if isinstance(B.get('mvrv'), dict) else {}
    b = {r[0]: float(r[1]) for r in (M.get('d') or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and num(r[1])}
    dl = B.get('delay_d')
    if isinstance(dl, int) and not isinstance(dl, bool):
        out['opoznienie_d'] = dl
        if dl != WY_OPOZN:
            out['uwagi'].append(f'SOPR BTC: źródło zmieniło opóźnienie planu darmowego: {dl} dni (było {WY_OPOZN})')
    wsp = sorted(set(a) & set(b))
    out['n'] = len(wsp)
    if len(wsp) < WY_ZG_MIN:
        out.update(status='ℹ️', opis=f'wspólnych dni {len(wsp)} z {WY_ZG_MIN} — bez oceny')
        return out
    r = [(b[d] / a[d] - 1) * 100 for d in wsp]
    med, last = statistics.median(r), r[-1]
    out.update(mediana_pct=round(med, 3), dzien=wsp[-1], roznica_pct=round(last, 3))

    def mabs(k):
        v = [abs(b[d] / a[x] - 1) * 100 for d in wsp for x in [(dt.date.fromisoformat(d) + dt.timedelta(days=k)).isoformat()] if x in a]
        return statistics.median(v) if v else None
    m0, mk = mabs(0), [m for m in (mabs(-1), mabs(1)) if m is not None]
    out['przesuniecie'] = bool(mk) and m0 is not None and min(mk) < WY_ZG_SHIFT * m0
    ok = abs(last - med) <= WY_ZG_PP and abs(med) <= WY_ZG_MED
    out['status'] = '✅' if ok and not out['przesuniecie'] else '⚠️'
    out['opis'] = f'odchylenie najnowszego dnia od normy {abs(last - med):.2f} pkt proc. (próg {WY_ZG_PP:g}), norma {med:+.2f}% (próg ±{WY_ZG_MED:g}%)'
    if not ok:
        out['uwagi'].append(f'MVRV: dwa źródła różnią się o {last:+.2f}% ({wsp[-1]}) wobec normy {med:+.2f}% (mediana {len(wsp)} dni)')
    if out['przesuniecie']:
        out['uwagi'].append('MVRV: możliwe przesunięcie dat o 1 dzień u jednego ze źródeł (po przesunięciu różnice wyraźnie mniejsze)')
    return out


# ---------------------------------------------------------------- v115: zgodność liczb ----------------------------------------------------------------
ZG_KOL = ['date', 'cap_gap_pct', 'tga_gap_pct', 'stab_gap_pct', 'cmc_gap_pct']   # kontrola/zgodnosc.csv: tylko różnice procentowe (bez wartości źródeł); puste pole = brak odczytu (v209: + stablecoiny)


def zgodnosc_csv(path):
    """{dzień: {'cap': %, 'tga': %, 'stab': %, 'cmc': %}} — pusta komórka albo brak kolumny (plik sprzed v209/v277) = brak (klucz pominięty)."""
    rows = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8', newline='') as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) >= 2 and row[0] != 'date':
                    rec = {}
                    for i, kk in ((1, 'cap'), (2, 'tga'), (3, 'stab'), (4, 'cmc')):
                        try:
                            rec[kk] = float(row[i])
                        except (ValueError, IndexError):
                            pass
                    rows[row[0]] = rec
    return rows


def zgodnosc_zapisz(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        wtr = csv.writer(f, lineterminator='\n'); wtr.writerow(ZG_KOL)
        for d in sorted(rows):
            wtr.writerow([d] + [('%.3f' % rows[d][kk]) if isinstance(rows[d].get(kk), (int, float)) else '' for kk in ('cap', 'tga', 'stab', 'cmc')])


def mediana_ocena(rows, kk, gap, today, zolte, czerwone):
    """rows: dzień → {kk: różnica %} z poprzednich dni; gap: dzisiejsza różnica. Zwraca (status, mediana, n, opis) — żółte/czerwone,
    gdy dzisiejsza różnica odbiega od mediany ostatnich ZG_DNI dni o więcej niż progi (pkt proc.); < ZG_MIN dni historii = tylko informacja."""
    hist = [v[kk] for d, v in sorted(rows.items()) if d < today and isinstance(v.get(kk), (int, float))][-ZG_DNI:]
    if gap is None:
        return '?', None, len(hist), 'brak odczytu'
    if len(hist) < ZG_MIN:
        return 'ℹ️', (statistics.median(hist) if hist else None), len(hist), f'historia {len(hist)} z {ZG_MIN} dni — bez oceny'
    med = statistics.median(hist)
    d = abs(gap - med)
    st = '❌' if (czerwone is not None and d > czerwone) else ('⚠️' if d > zolte else '✅')
    return st, med, len(hist), f'odchylenie od mediany {d:.2f} pkt proc. (progi {zolte:g}' + (f' / {czerwone:g}' if czerwone is not None else '') + ')'


def kapitalizacja(rows, gap, today):
    return mediana_ocena(rows, 'cap', gap, today, ZG_ZOLTE, ZG_CZERWONE)


def cmc_roznica(cmc, cg, now):
    """v277: różnica kapitalizacji z pliku cmc.json strony wobec CoinGecko z chwili kontroli, % ((cmc − cg) / cg × 100) — None, gdy brak liczby
    albo plik starszy niż ZG_CMC_MAX_MIN min (inna chwila rynku)."""
    try:
        v, t = cmc.get('total_mcap'), dt.datetime.fromisoformat(str(cmc.get('at')).replace('Z', '+00:00'))
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not v > 0 or not t.tzinfo or not float(cg) > 0:
            return None
        if abs((now - t).total_seconds()) > ZG_CMC_MAX_MIN * 60:
            return None
        return round((float(v) - float(cg)) / float(cg) * 100.0, 3)
    except (AttributeError, TypeError, ValueError):
        return None


def kapitalizacja_trzecie(rows, st, opis, d_cmc, today):
    """v277: ⚠️/❌ różnicy CoinGecko–CoinPaprika rozstrzygane trzecim źródłem strony (CoinMarketCap, cmc_roznica): CoinMarketCap wobec
    CoinGecko w swojej normie (mediana ostatnich ZG_DNI dni, gdy ≥ ZG_MIN; inaczej |różnica| < ZG_CMC_BEZ) = oba źródła strony zgodne jak zwykle
    — odstaje źródło kontrolne → ℹ️ z opisem; inaczej status bez zmian (z dopiskiem). → (status, opis)."""
    if st not in ('⚠️', '❌') or d_cmc is None:
        return st, opis
    hist = [v['cmc'] for d, v in sorted(rows.items()) if d < today and isinstance(v.get('cmc'), (int, float))][-ZG_DNI:]
    if len(hist) >= ZG_MIN:
        med = statistics.median(hist)
        zgodne, norma = abs(d_cmc - med) < ZG_CMC_ROZ, f'norma {med:+.2f}%'
    else:
        zgodne, norma = abs(d_cmc) < ZG_CMC_BEZ, f'bez normy — próg ±{ZG_CMC_BEZ:g}%'
    if zgodne:
        return 'ℹ️', (f'{opis}; odstaje źródło kontrolne (CoinPaprika) — dwa źródła strony zgodne jak zwykle: CoinMarketCap wobec CoinGecko '
                      f'{d_cmc:+.2f}% ({norma}); liczby strony bez zmian')
    return st, f'{opis}; CoinMarketCap wobec CoinGecko też odstaje: {d_cmc:+.2f}% ({norma})'


def procent(a, b):
    try:
        return abs(a - b) / abs(b) * 100.0 if b else None
    except Exception:
        return None


def stab_porownanie(krypto, cmc):
    """v209: podaż stablecoinów z dwóch plików strony → {'a': DefiLlama (krypto.json stabh.cur, USD), 'b': CoinMarketCap (cmc.json stable_mcap),
    'roznica_pct': (a − b) / b × 100, 'odstep_h': odstęp pobrań plików, 'data': stabh.asof} albo None (brak liczby). Odstęp > STAB_MAX_H —
    'roznica_pct' None (bez porównania; liczby różnych chwil)."""
    st = krypto.get('stabh') if isinstance(krypto, dict) and isinstance(krypto.get('stabh'), dict) else {}
    a, b = st.get('cur'), (cmc.get('stable_mcap') if isinstance(cmc, dict) else None)
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0  # noqa: E731
    if not (num(a) and num(b)):
        return None
    try:
        pa = krypto.get('part_at') if isinstance(krypto.get('part_at'), dict) else {}   # v281 (przegląd v276): czas części 'stabh', nie całego pliku
        t1 = dt.datetime.fromisoformat(str(pa.get('stabh') or krypto.get('at')).replace('Z', '+00:00')); t2 = dt.datetime.fromisoformat(str(cmc.get('at')).replace('Z', '+00:00'))
        h = abs((t1 - t2).total_seconds()) / 3600 if t1.tzinfo and t2.tzinfo else None
    except (TypeError, ValueError):
        h = None
    r = round((a - b) / b * 100.0, 3) if h is not None and h <= STAB_MAX_H else None
    return {'a': float(a), 'b': float(b), 'roznica_pct': r, 'odstep_h': (round(h, 1) if h is not None else None), 'data': st.get('asof')}


def ust_fred_csv(txt):
    """v209: CSV z FRED (observation_date,DGS10) → {dzień: rentowność}; '.' albo puste (święto) i złe wiersze pominięte."""
    out = {}
    for line in str(txt or '').splitlines()[1:]:
        p = line.strip().split(',')
        if len(p) == 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', p[0]):
            try:
                out[p[0]] = float(p[1])
            except ValueError:
                pass
    return out


def ust_fed_csv(txt):
    """v211: CSV H.15 z serwisu danych Rady Gubernatorów Fed (wiersze opisu, potem „Time Period” z kodami serii, potem dni) → {dzień: rentowność
    10L}; 'ND' (brak notowania) i złe wiersze pominięte; brak kolumny 10L albo nagłówka = {}."""
    out, col = {}, None
    for r in csv.reader(str(txt or '').splitlines()):
        if not r:
            continue
        if r[0].strip() == 'Time Period':
            col = r.index(UST_FED_KOL) if UST_FED_KOL in r else None
            continue
        if col is not None and len(r) > col and re.match(r'^\d{4}-\d{2}-\d{2}$', r[0]):
            try:
                out[r[0]] = float(r[col])
            except ValueError:
                pass
    return out


def fx_h10_csv(txt):
    """v225: CSV H.10 z serwisu danych Rady Gubernatorów Fed (wiersze opisu — „Currency:” z kodami walut, „Unique Identifier:” z kodami serii:
    RXI$US = USD za jednostkę waluty, RXI = waluta za 1 USD; potem dni) → {dzień: {waluta: ile waluty za 1 USD}}; 'ND' (brak notowania), zera,
    kody spoza trzech liter i złe wiersze pominięte; bez wierszy walut = {}."""
    cur, inv, out = None, None, {}
    for r in csv.reader(str(txt or '').splitlines()):
        if not r:
            continue
        k = r[0].strip()
        if k == 'Currency:':
            cur = [c.strip() for c in r[1:]]
            continue
        if k.startswith('Unique Identifier'):
            inv = ['$US' in c for c in r[1:]]
            continue
        if cur and inv and len(inv) == len(cur) and re.match(r'^\d{4}-\d{2}-\d{2}$', k):
            d = {}
            for c, i, v in zip(cur, inv, r[1:]):
                try:
                    x = float(v)
                except ValueError:
                    continue
                if x > 0 and re.match(r'^[A-Z]{3}$', c):
                    d[c] = 1 / x if i else x
            if d:
                out[k] = d
    return out


def fx_uwagi(f):
    """v227: uwagi kontroli z wyniku fx_porownanie — liczby z przecinkiem dziesiętnym (nazwa „H.10” bez zmian)."""
    n = lambda x, fmt: format(x, fmt).replace('.', ',')  # noqa: E731
    out = []
    if isinstance(f, dict) and f.get('zle'):
        out.append(f'kursy walut: plik strony vs H.10 (Fed) różnią się ponad {n(FX_PROG, "g")}%: '
                   + ', '.join(f'{c} {d}: {n(v, "g")} vs {n(h, "g")} ({n(r, "+.2f")}%)' for d, c, v, h, r in f['zle'][:6]))
    if isinstance(f, dict) and f.get('baza'):   # v231
        out.append('kursy walut: migawki z walutą bazową inną niż USD: ' + ', '.join(f'{k} ({b})' for k, b in f['baza'])
                   + ' — strona przyjmuje tylko USD (te kursy pominie); sprawdzić serwis pośredni kursów')
    if isinstance(f, dict) and f.get('med_zle'):
        out.append(f'kursy walut: mediana różnic z H.10 (Fed) ponad {n(FX_MED, "g")}% dla ' + ', '.join(f'{d} ({n(m, ".2f")}%)' for d, m in f['med_zle'])
                   + ' — sprawdzić walutę bazową i datę migawki')
    return out


def fx_baza(rynki):
    """v235: migawki kursów pliku strony z polem base innym niż USD → [[migawka, waluta albo „brak”], …] — niezależnie od H.10 (gdy H.10 nie
    odpowiada, ostrzeżenie zostaje; strona takie migawki odrzuca). Bez pola base (stary format) — bez uwagi."""
    fx = rynki.get('fx') if isinstance(rynki, dict) else None
    if not isinstance(fx, dict):
        return []
    return [[k, fx[k]['base'][:8] if isinstance(fx[k].get('base'), str) and fx[k]['base'] else 'brak'] for k in FX_MIGAWKI
            if isinstance(fx.get(k), dict) and 'base' in fx[k] and fx[k].get('base') != 'USD']


def fx_porownanie(rynki, h10):
    """v225: migawki kursów pliku strony (rynki.json → fx[now|1D|1T|1M|1Q|1R] = {date, base: USD, rates: {waluta: ile za 1 USD}}) vs H.10 z tych
    samych dni → {'daty': [[dzień, n walut, mediana |%|, waluta z największą różnicą, jej %], …], 'zle': [[dzień, waluta, strona, H.10, %], …]
    (ponad FX_PROG), 'med_zle': [[dzień, mediana %], …] (ponad FX_MED przy co najmniej FX_MIN_N walutach)}; brak migawek albo H.10 = None.
    Ta sama data w kilku migawkach — porównana raz (pierwsza w kolejności FX_MIGAWKI)."""
    fx = rynki.get('fx') if isinstance(rynki, dict) else None
    baza = fx_baza(rynki)   # v231/v233/v235: migawka z inną walutą bazową (także pusta) — ⚠️, także bez H.10
    if not isinstance(fx, dict) or not isinstance(h10, dict) or not h10:
        return {'daty': [], 'zle': [], 'med_zle': [], 'baza': baza} if baza else None
    by = {}
    for k in FX_MIGAWKI:
        s = fx.get(k)
        if isinstance(s, dict) and s.get('base') == 'USD' and isinstance(s.get('date'), str) and isinstance(s.get('rates'), dict):
            by.setdefault(s['date'], s['rates'])
    if not by and not baza:
        return None
    out = {'daty': [], 'zle': [], 'med_zle': [], 'baza': baza}
    for d in sorted(by):
        H = h10.get(d)
        if not isinstance(H, dict):
            continue
        rs = [(c, float(v), H[c], (float(v) / H[c] - 1) * 100) for c, v in by[d].items()
              if c in H and isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
        if not rs:
            continue
        med = statistics.median(abs(x[3]) for x in rs)
        mx = max(rs, key=lambda x: abs(x[3]))
        out['daty'].append([d, len(rs), round(med, 3), mx[0], round(mx[3], 3)])
        out['zle'] += [[d, c, v, round(h, 6), round(r, 3)] for c, v, h, r in rs if abs(r) > FX_PROG]
        if len(rs) >= FX_MIN_N and med > FX_MED:
            out['med_zle'].append([d, round(med, 3)])
    return out


def ust_porownanie(rynki, fred):
    """v209: rentowność 10L USA — plik strony (rynki.json ust: [[dzień, %], …]) vs H.15 (DGS10, {dzień: %}) z tych samych dni, ostatnie UST_DNI dat
    pliku strony → {'porownane': n, 'do': ostatnia wspólna data, 'roznice': [[dzień, a, b, |a − b|], …] ponad UST_PROG} albo None (brak serii)."""
    s = rynki.get('ust') if isinstance(rynki, dict) else None
    if not isinstance(s, list) or not isinstance(fred, dict):
        return None
    ost = [r for r in s if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str) and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)][-UST_DNI:]
    wsp = [(d, float(v), fred[d]) for d, v in ost if d in fred]
    return {'porownane': len(wsp), 'do': (wsp[-1][0] if wsp else None),
            'roznice': [[d, a, b, round(abs(a - b), 3)] for d, a, b in wsp if abs(a - b) > UST_PROG + 1e-9]}


def tga_seria(fred):
    """v293 (audyt G2): seria TGA w fred.json — WDTGAL (stan na środę, od v293) albo WTREGEN (średnia tygodnia, plik sprzed v293); brak — None."""
    S = fred.get('series') if isinstance(fred, dict) else None
    for sid in ('WDTGAL', 'WTREGEN'):
        if isinstance(S, dict) and isinstance(S.get(sid), dict) and isinstance(S[sid].get('d'), list) and S[sid]['d']:
            return sid
    return None


def tga_porownanie(inst, fred):
    """Ostatnia wspólna data Fiscal Data (instytucje.tga.d) i FRED (tga_seria: WDTGAL, w pliku sprzed v293 WTREGEN; obie w mln USD) → (data, fiscal, fred, różnica %)."""
    try:
        a = {str(r[0]): float(r[1]) for r in inst['tga']['d'] if isinstance(r, list) and len(r) >= 2 and r[1] is not None}
        b = {str(r[0]): float(r[1]) for r in fred['series'][tga_seria(fred)]['d'] if isinstance(r, list) and len(r) >= 2 and r[1] is not None}
    except Exception:
        return None
    wspolne = sorted(set(a) & set(b))
    if not wspolne:
        return None
    d = wspolne[-1]
    return d, a[d], b[d], procent(a[d], b[d])


def tga_ocena(rows, inst, fred, today):
    """v293 (audyt G2): porównanie TGA z oceną → słownik raportu (Z['tga']) albo None; dzisiejsza różnica trafia do rows[today]['tga'].
    WDTGAL (stan na środę) = saldo zamknięcia z dziennego zestawienia Skarbu tego samego dnia (test wsteczny v296: 554 środy 2016–2026, wszystkie
    równe co do jednostki — opis przy TGA_PROG) — różnica powinna być bliska zeru, więc próg stały TGA_PROG, bez mediany (historia różnic sprzed v293 to średnia tygodnia, inna
    miara: ok. 3–4% — mediana z niej dawałaby fałszywe ⚠️ przez dwa tygodnie). Plik sprzed v293 (tylko WTREGEN) — mediana jak dotąd."""
    t = tga_porownanie(inst, fred)
    if not t:
        return None
    d, a, b, r = t
    if r is not None:
        rows.setdefault(today, {})['tga'] = round(r, 3)
    if tga_seria(fred) == 'WDTGAL':
        st2, med2, n2, opis2 = ('?', None, 0, 'brak odczytu') if r is None else (('⚠️' if r > TGA_PROG else '✅'), None, 0, f'próg stały {TGA_PROG:g}% (stan na środę = saldo zamknięcia tego dnia)')
    else:
        st2, med2, n2, opis2 = mediana_ocena(rows, 'tga', r, today, TGA_PROG, None)
    return {'data': d, 'fiscal_mln': a, 'fred_mln': b, 'roznica_pct': (round(r, 3) if r is not None else None), 'status': st2,
            'mediana_pct': (round(med2, 3) if med2 is not None else None), 'dni': n2, 'opis': opis2}


def etf_porownanie(ceny, ix):
    """14 symboli ETF mapy: ostatnia wspólna data zamknięcia w ceny.json (Twelve Data, `q[SYM].d = [[data, close, wolumen]]`) i w indeksy.json
    (`etf.q[SYM] = [[data, close]]`, Massive/Tiingo) → lista (symbol, data, a, b, różnica %); symbol bez wspólnej daty = pominięty. None = brak plików."""
    try:
        q1, q2 = ceny['q'], ix['etf']['q']
    except Exception:
        return None
    out = []
    for sym, rec in q1.items():
        d1 = {str(r[0]): float(r[1]) for r in ((rec.get('d') if isinstance(rec, dict) else None) or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[1], (int, float))}
        d2 = {str(r[0]): float(r[1]) for r in (q2.get(sym) or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[1], (int, float))}
        wsp = sorted(set(d1) & set(d2))
        if wsp:
            d = wsp[-1]; out.append((sym, d, d1[d], d2[d], procent(d1[d], d2[d])))
    return out


def wieloryby_porownanie(path):
    """archiwum/wieloryby.csv: dla ostatniego dnia z poprzednim dniem — |zmiana salda − przelewy netto| na giełdę i aktywo; zmiana salda liczona
    w jednostkach aktywa po dzisiejszym kursie (saldo w USD zmienia się też przez kurs ETH, a to nie przelew). Pusta komórka przepływów (brak sum
    dobowych) = para pominięta. Zwraca (dzień, poprzedni, lista (giełda, aktywo, zmiana, netto, rozbieżność) ponad progiem, liczba porównanych) albo None."""
    if not os.path.exists(path):
        return None
    by = {}
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f); head = next(r, None)
        if not head or head[:5] != ['date', 'exchange', 'asset', 'balance', 'balance_usd']:
            return None
        for row in r:
            if len(row) >= 8:
                by.setdefault(row[0], {})[(row[1], row[2])] = row
    days = sorted(by)
    if len(days) < 2:
        return None
    d, p = days[-1], days[-2]
    zle, n = [], 0
    for k, row in by[d].items():
        prev = by[p].get(k)
        if not prev:
            continue
        try:
            u, u0, usd, net = float(row[3]), float(prev[3]), float(row[4]), float(row[7])
        except ValueError:
            continue
        if not u:
            continue
        n += 1
        delta = (u - u0) * (usd / u)   # zmiana w jednostkach × dzisiejszy kurs — ruch kursu ETH nie jest przelewem (v117)
        roz = abs(delta - net)
        if roz > WH_MIN_USD and roz > WH_PROG / 100 * max(abs(delta), abs(net), WH_MIN_USD):
            zle.append((k[0], k[1], delta, net, roz))
    return d, p, zle, n


WH_DOBA_BLOKI = (6900, 7500)   # v174: migawki oddalone o ok. dobę (12 s na blok Ethereum: 23–25 h) — inny odstęp: sald nie porównujemy z przepływami 24 h
WH_RAZY = 3.0                  # v174: rozbieżność pary ponad tyle × jej mediana z wcześniejszych porównywalnych dni = uwaga (zwykła rozbieżność to norma)
WH_HIST_MIN = 3                # v174: mniej wcześniejszych porównywalnych dni pary = bez oceny (informacja)


def _wh_csv(path):
    """v174/v175: archiwum/wieloryby.csv → {dzień: {(giełda, aktywo): wiersz}}; zły nagłówek albo brak pliku = None."""
    if not os.path.exists(path):
        return None
    by = {}
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        head = next(r, None)
        if not head or head[:5] != ['date', 'exchange', 'asset', 'balance', 'balance_usd']:
            return None
        for row in r:
            if len(row) >= 9:
                by.setdefault(row[0], {})[(row[1], row[2])] = row
    return by


def _wh_rozb(a, b):
    """v174/v175: rozbieżności par dnia `b` wobec dnia `a` → {(giełda, aktywo): (zmiana, netto, |zmiana − netto|, odstęp w blokach albo None)};
    odstęp z bloków WŁASNYCH migawek pary (giełda bez nowego odczytu ma w archiwum blok poprzedniego)."""
    out = {}
    for k, row in b.items():
        prev = a.get(k)
        if not prev:
            continue
        try:
            u, u0, usd, net = float(row[3]), float(prev[3]), float(row[4]), float(row[7])
        except ValueError:
            continue
        if not u:
            continue
        delta = (u - u0) * (usd / u)
        sp = int(row[8]) - int(prev[8]) if row[8].isdigit() and prev[8].isdigit() else None
        out[k] = (delta, net, abs(delta - net), sp)
    return out


ZUZ_PLANY = (('cg', 'CoinGecko (Demo)', 'mies', 10000, 'zapytań'),        # v222: limity darmowych planów (stan 06.10.2026; inny plan = zmiana tutaj)
             ('cmc', 'CoinMarketCap (Basic)', 'mies', 15000, 'zapytań'),       # v226: 15 000 według dostawcy (06.10.2026)
             ('td', 'Twelve Data (Basic)', 'doba', 800, 'kredytów'),
             ('fmp', 'FMP (darmowy)', 'doba', 250, 'zapytań'))       # v295: indeksy (v273) i surowce (srebro, kontrolnie Brent i złoto)
ZUZ_UWAGA = 0.8       # v222: prognoza miesiąca albo wczorajsza doba ≥ 80% limitu = ⚠️
ZUZ_BLAD = 0.95       # v222: zużyte w miesiącu ≥ 95% limitu albo wczoraj ≥ 100% limitu doby = ❌
ZUZ_PROG_H = 24       # v222: prognoza miesiąca dopiero po dobie liczenia
ZUZ_MP_DNI = 7       # v226: w pierwszych tylu dniach miesiąca oceniany też koniec poprzedniego (przekroczenie po ostatniej kontroli)


def _zuz_l(n):
    return f'{n:,.0f}'.replace(',', ' ')


def _norma(med, dni, fmt='{:.2f}%'):
    """v245: „, norma (mediana N dni) X%” do wierszy porównań — bez mediany (za krótka historia) pusto (było „norma (mediana 0 dni) — —”)."""
    return f', norma (mediana {dni} dni) {fmt.format(med)}' if med is not None else ''


def _zuz_ok(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def zuzycie_ocena(meta):
    """v222: licznik zużycia darmowych planów (meta.json → zuzycie) → {'plany': [{'k', 'tekst', 'znak'}], 'uwagi', 'bledy'}; plik bez pola
    (zbieracz sprzed v222) albo bez czasu = None. Liczby automatu to dolna granica (przebieg bez zapisu stanu nie dolicza się); CoinMarketCap
    także według samego dostawcy (raport co 6 h). Miesiąc i doba — kalendarz UTC."""
    z = meta.get('zuzycie') if isinstance(meta, dict) else None
    at = _aw_t(meta.get('at')) if isinstance(meta, dict) else None
    if not isinstance(z, dict) or at is None:
        return None
    out = {'plany': [], 'uwagi': [], 'bledy': []}
    for k, nazwa, okres, lim, jedn in ZUZ_PLANY:
        q = z.get(k) if isinstance(z.get(k), dict) else None
        od = _aw_t(q.get('od')) if q else None
        if od is None:
            continue
        krotko, znak = nazwa.split(' (')[0], '✅'
        ds0 = q.get('dost') if isinstance(q.get('dost'), dict) else {}
        ml = ds0.get('mies') if isinstance(ds0.get('mies'), list) and len(ds0['mies']) == 3 else [None] * 3
        if okres == 'mies' and _zuz_ok(ml[2]) and ml[2] > 0:
            lim = ml[2]   # v223: limit miesiąca według samego dostawcy (CoinMarketCap 06.10: 15 000, nie 10 000)
        rada = f'co zrobić: napisz do Claude „zmniejsz liczbę zapytań do {krotko}”'
        if okres == 'mies':
            ms = at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if q.get('m') != at.strftime('%Y-%m') or not _zuz_ok(q.get('nm')):
                out['plany'].append({'k': k, 'tekst': f'{nazwa} — brak licznika w tym miesiącu', 'znak': 'ℹ️'})
                continue
            nm, start = q['nm'], max(ms, od)
            t = f'{nazwa} — {jedn} w tym miesiącu' + (f' (od {czas_pl(od.isoformat())})' if od > ms else '') + f': {_zuz_l(nm)}'
            h = (at - start).total_seconds() / 3600
            if h >= ZUZ_PROG_H:
                dni = ((ms + dt.timedelta(days=32)).replace(day=1) - ms).days
                prog = nm / h * dni * 24
                t += f', prognoza na miesiąc ok. {_zuz_l(prog)} z limitu {_zuz_l(lim)} ({prog / lim * 100:.0f}%)'
                if prog >= ZUZ_UWAGA * lim:
                    znak = '⚠️'
                    out['uwagi'].append(f'{nazwa}: prognoza zużycia planu w miesiącu ok. {_zuz_l(prog)} z {_zuz_l(lim)} {jedn} — '
                                        + ('ponad limit' if prog >= lim else 'zapas maleje') + f'; {rada}')
            else:
                t += ' (prognoza po pierwszej dobie liczenia)'
            if nm >= ZUZ_BLAD * lim:
                znak = '❌'
                out['bledy'].append(f'limit planu {nazwa} prawie wyczerpany: {_zuz_l(nm)} z {_zuz_l(lim)} {jedn} w tym miesiącu (licznik automatu)')
            mp, pm_ = q.get('mp'), (ms - dt.timedelta(days=1)).strftime('%Y-%m')
            if at.day <= ZUZ_MP_DNI and isinstance(mp, list) and len(mp) == 2 and mp[0] == pm_ and _zuz_ok(mp[1]) and mp[1] >= ZUZ_BLAD * lim:
                znak = '❌' if znak == '❌' else '⚠️'   # v226: koniec poprzedniego miesiąca (przekroczenie mogło przyjść po ostatniej kontroli)
                out['uwagi'].append(f'{nazwa}: w poprzednim miesiącu ({mp[0]}) automat zużył {_zuz_l(mp[1])} z {_zuz_l(lim)} {jedn} — limit był prawie '
                                    f'wyczerpany, część liczb mogła zniknąć pod koniec miesiąca; {rada}')
        else:
            dp, wcz = q.get('dp'), (at - dt.timedelta(days=1)).strftime('%Y-%m-%d')
            if isinstance(dp, list) and len(dp) == 2 and dp[0] == wcz and _zuz_ok(dp[1]) and dp[0] > od.strftime('%Y-%m-%d'):
                t = f'{nazwa} — {jedn} wczoraj (doba UTC): {_zuz_l(dp[1])} z limitu {_zuz_l(lim)} ({dp[1] / lim * 100:.0f}%)'
                if dp[1] >= lim:
                    znak = '❌'
                    out['bledy'].append(f'limit planu {nazwa} wyczerpany wczoraj: {_zuz_l(dp[1])} z {_zuz_l(lim)} {jedn} (licznik automatu) — '
                                        'część notowań mogła nie przyjść')
                elif dp[1] >= ZUZ_UWAGA * lim:
                    znak = '⚠️'
                    out['uwagi'].append(f'{nazwa}: wczoraj {_zuz_l(dp[1])} z {_zuz_l(lim)} {jedn} limitu doby — zapas maleje; {rada}')
            else:
                t = f'{nazwa} — {jedn} wczoraj: brak pełnej doby licznika'
            if q.get('d') == at.strftime('%Y-%m-%d') and _zuz_ok(q.get('n')):
                t += f'; w bieżącej dobie (od północy UTC): {_zuz_l(q["n"])}'
        ds = q.get('dost') if isinstance(q.get('dost'), dict) else None
        if ds and ds.get('blad'):
            t += f'; raport dostawcy niedostępny ({str(ds["blad"])[:80]})'
        elif ds:
            def trzy(x):
                return (list(x) + [None] * 3)[:3] if isinstance(x, list) else [None] * 3
            u, left, lm = trzy(ds.get('mies'))
            lm = lm if _zuz_ok(lm) and lm > 0 else (u + left if _zuz_ok(u) and _zuz_ok(left) and u + left > 0 else None)
            if _zuz_ok(u) and lm:
                t += f'; według dostawcy w miesiącu: {_zuz_l(u)} z {_zuz_l(lm)} ({u / lm * 100:.0f}%, stan {czas_pl(ds.get("at"))})'
                if u >= ZUZ_BLAD * lm:
                    znak = '❌'
                    out['bledy'].append(f'limit planu {nazwa} prawie wyczerpany według dostawcy: {_zuz_l(u)} z {_zuz_l(lm)} w tym miesiącu')
                elif u >= ZUZ_UWAGA * lm:
                    znak = '❌' if znak == '❌' else '⚠️'
                    out['uwagi'].append(f'{nazwa}: według dostawcy zużyto {_zuz_l(u)} z {_zuz_l(lm)} w tym miesiącu — zapas maleje; {rada}')
            du, dleft, dlm = trzy(ds.get('dz'))
            if _zuz_ok(du) and _zuz_ok(dlm) and dlm > 0 and du >= dlm:
                znak = '❌' if znak == '❌' else '⚠️'
                out['uwagi'].append(f'{nazwa}: według dostawcy dzienny limit wyczerpany ({_zuz_l(du)} z {_zuz_l(dlm)}, stan {czas_pl(ds.get("at"))}) — '
                                    f'część liczb może poczekać do północy UTC; {rada}')
        out['plany'].append({'k': k, 'tekst': t, 'znak': znak})
    return out


WH_LISTY_MIES = ('OKX', 'Bybit', 'KuCoin')   # v218: giełdy z comiesięcznym raportem dowodu rezerw (wieloryby.json → gieldy[*].since) — listy do odświeżania
WH_LISTY_DNI = 45                             # v218: lista starsza = uwaga (portfele dodane przez giełdę od tego czasu nie są liczone)


def wh_listy_ocena(j, now=None):
    """v218: wiek list portfeli giełd z miesięcznym raportem dowodu rezerw → {'wszystkie': [(giełda, data, dni)], 'stare': [… > WH_LISTY_DNI]};
    brak pliku albo pola gieldy = None; giełda bez poprawnej daty RRRR-MM-DD pominięta."""
    now = now or NOW
    G = j.get('gieldy') if isinstance(j, dict) and isinstance(j.get('gieldy'), dict) else None
    if G is None:
        return None
    A = []
    for g in WH_LISTY_MIES:
        s = G[g].get('since') if isinstance(G.get(g), dict) else None
        try:
            A.append((g, s, (now.date() - dt.date.fromisoformat(s)).days))
        except (TypeError, ValueError):
            continue
    return {'wszystkie': A, 'stare': [x for x in A if x[2] > WH_LISTY_DNI]}


# v237/v242: nowe raporty dowodu rezerw giełd (listy portfeli wielorybów) — sprawdzanie codzienne, bez pobierania całych plików
WH_NOWE_OD_DNI = 20        # nowszego raportu szukamy od tylu dni po dacie obecnej listy (raporty miesięczne)
WH_NOWE_MAX = 30           # najwyżej tyle dat na giełdę, od najnowszej
WH_NOWE_BUDZET_S = 60      # nowe zapytanie tylko, gdy od początku minęło mniej niż tyle sekund minus jego limit (całość ok. 60–70 s)
WH_NOWE_ADRESY = {'OKX': 'https://static.okx.com/cdn/okx/por/chain/por_csv_{r}{mm}{dd}00_V1.zip',
                  'Bybit': 'https://www.bybit.com/common-static/cht-static/por/Bybit_PoR_Audit_{r}_{mies}_{dd}.pdf'}
WH_NOWE_SYGN = {'OKX': b'PK\x03\x04', 'Bybit': b'%PDF'}   # v242: trafienie tylko z podpisem pliku (strona HTML z kodem 200 to nie plik)
WH_NOWE_BRAK = {'OKX': (404,), 'Bybit': (403, 404)}       # v242: „nie ma pliku” wg giełdy (OKX: 404 XML; Bybit: 403 ze stroną WWW); inne = nie wiadomo
WH_NOWE_PAUZA_S = 0.3      # v242: przerwa między zapytaniami do tej samej giełdy
WH_NOWE_KUCOIN = 'https://www.kucoin.com/_api/asset-front/proof-of-reserves/asset-reserve'
MIES_EN = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def wh_plik_jest(url, g=None):
    """v237/v242: czy plik istnieje — tylko pierwsze 1 024 bajty (Range): 200/206 z podpisem pliku giełdy = jest; kod „nie ma pliku” tej giełdy
    (WH_NOWE_BRAK) = nie ma; wszystko inne (blokada, limit, sieć, strona HTML z kodem 200) = None (nie wiadomo)."""
    try:
        st, body, _ = get(url, timeout=10, headers={'Range': 'bytes=0-1023'}, limit=1024)
    except urllib.error.HTTPError as e:
        if e.code not in WH_NOWE_BRAK.get(g, (404,)):
            return None
        if g == 'Bybit' and e.code == 403:   # v243: 403 = „nie ma pliku” tylko ze stroną brakującego pliku (Server: AmazonS3); blokada wygląda inaczej
            srv = (e.headers.get('Server') if e.headers is not None and hasattr(e.headers, 'get') else None) or ''
            return False if 'AmazonS3' in str(srv) else None
        return False
    except Exception:  # noqa — sieć, limit czasu, zaślepka testu bez parametru limit
        return None
    if st not in (200, 206):
        return None
    sg = WH_NOWE_SYGN.get(g)
    return True if sg is None or (isinstance(body, (bytes, bytearray)) and bytes(body[:len(sg)]) == sg) else None


def wh_nowe_adresy(g, d):
    """v237: adresy pliku giełdy g z dnia d (Bybit: dzień jednocyfrowy w dwóch zapisach — „05” i „5”)."""
    w = WH_NOWE_ADRESY[g]
    dd = [f'{d.day:02d}'] + ([str(d.day)] if g == 'Bybit' and d.day < 10 else [])
    return [w.format(r=d.year, mm=f'{d.month:02d}', dd=x, mies=MIES_EN[d.month - 1]) for x in dd]


def wh_nowe_raporty(gieldy, now=None, budzet_s=WH_NOWE_BUDZET_S, zegar=time.monotonic, spij=time.sleep):
    """v237/v242: listy portfeli giełd z raportów miesięcznych (wieloryby.json → gieldy[g].since, .url) → {giełda: {'od', 'nowy' (data nowszego
    raportu albo None), 'lista' (True — plik z adresami jest; False — audyt bez raportu z listą), 'prob' (dat sprawdzonych), 'zakres' ([od, do]
    sprawdzonych dni), 'kontrola' (plik obecnej listy: True — odpowiedział plikiem, 'brak' — nie, None — nie sprawdzany), 'nie_wiadomo', 'przerwane'}}. OKX i Bybit: najpierw
    plik obecnej listy — gdy nie odpowiada plikiem (blokada serwera, limit), „nie wiadomo”, nigdy „brak nowszego”."""
    now = now or NOW
    G = gieldy if isinstance(gieldy, dict) else {}
    t0, out = zegar(), {}
    czas_ok = lambda lim: zegar() - t0 + lim <= budzet_s  # noqa: E731
    for g in WH_LISTY_MIES:
        c = G.get(g) if isinstance(G.get(g), dict) else {}
        try:
            od = dt.date.fromisoformat(c.get('since'))
        except (TypeError, ValueError):
            continue
        o = {'od': c['since'], 'nowy': None, 'lista': None, 'prob': 0, 'zakres': None, 'kontrola': None, 'nie_wiadomo': 0, 'przerwane': False}
        out[g] = o
        if g == 'KuCoin':
            if not czas_ok(15):
                o['przerwane'] = True
                continue
            try:
                j = json.loads(get(WH_NOWE_KUCOIN, timeout=15)[1])
                d = j.get('data') if isinstance(j, dict) and isinstance(j.get('data'), dict) else {}
                ms = d.get('latestAuditDate')
                if not isinstance(ms, (int, float)) or isinstance(ms, bool):
                    raise ValueError('brak daty audytu')
                o['prob'] = 1
                a = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()
                if a > od:
                    u = d.get('auditReportUrl')
                    o['nowy'], o['lista'] = a.isoformat(), bool(u) and u != c.get('url')   # v242: ten sam link co obecna lista — nic nowego
            except Exception:  # noqa
                o['nie_wiadomo'] += 1
            continue
        if g not in WH_NOWE_ADRESY:
            continue
        dni = [od + dt.timedelta(days=i) for i in range(WH_NOWE_OD_DNI, (now.date() - od).days + 1)][::-1][:WH_NOWE_MAX]
        if not dni:
            continue
        ku = c.get('url') if g == 'Bybit' and isinstance(c.get('url'), str) and c['url'].startswith('https://') else wh_nowe_adresy(g, od)[0]
        if not czas_ok(10):
            o['przerwane'] = True
            continue
        o['kontrola'] = True if wh_plik_jest(ku, g) is True else 'brak'   # v242: próba kontrolna — plik obecnej listy musi odpowiedzieć plikiem
        if o['kontrola'] != True:  # noqa: E712
            o['nie_wiadomo'] += 1
            continue
        ciagly = True   # v246: zakres tylko z ciągłych dni od najnowszego — dzień bez odpowiedzi go zamyka
        for d in dni:
            if not czas_ok(20):
                o['przerwane'] = True
                break
            spij(WH_NOWE_PAUZA_S)
            o['prob'] += 1
            wyn = []
            for u in wh_nowe_adresy(g, d):
                wyn.append(wh_plik_jest(u, g))
                if wyn[-1] is True:
                    break
            if True in wyn:
                o['nowy'], o['lista'] = d.isoformat(), True
                break
            if None in wyn:
                o['nie_wiadomo'] += 1
                ciagly = False
            elif ciagly:   # v243: zakres „brak nowszego” tylko z dni, na które każda odpowiedź brzmiała „nie ma pliku” (v246: ciągłych)
                o['zakres'] = [d.isoformat(), o['zakres'][1] if o['zakres'] else d.isoformat()]
        if o['prob'] and not o['nowy'] and czas_ok(10) and wh_plik_jest(ku, g) is not True:   # v243: druga próba kontrolna — blokada w trakcie
            o['kontrola'] = 'brak'
            o['nie_wiadomo'] += 1
    return out


def wh_nowe_wiersz(W):
    """v237/v242: wiersz raportu „Nowe raporty dowodu rezerw giełd” — zakres naprawdę sprawdzonych dni; „nie wiadomo” i „przerwane” osobno."""
    if W.get('_blad'):   # v243: błąd całego sprawdzania — wiersz zostaje, „nie wiadomo”
        return f'- Nowe raporty dowodu rezerw giełd (listy portfeli): nie wiadomo (błąd sprawdzania: {str(W["_blad"])[:80]}) ℹ️.'
    cz = []
    for g, o in W.items():
        if o.get('nowy') and o.get('lista'):
            cz.append(f'{g} — nowy raport z listą portfeli z {o["nowy"]} (obecna z {o["od"]}) ⚠️')
        elif o.get('nowy'):
            cz.append(f'{g} — audyt z {o["nowy"]}, raport z listą portfeli jeszcze niedostępny ℹ️')
        elif o.get('kontrola') == 'brak':
            cz.append(f'{g} — nie wiadomo (plik obecnej listy nie odpowiada plikiem — możliwa blokada serwera) ℹ️')
        elif o.get('przerwane'):
            cz.append(f'{g} — sprawdzanie przerwane (limit czasu)' + (f'; brak nowszego w dniach {o["zakres"][0]}–{o["zakres"][1]}' if o.get('zakres') else '')
                      + (f'; dni bez odpowiedzi: {o["nie_wiadomo"]}' if o.get('nie_wiadomo') else '') + ' ℹ️')
        elif o.get('nie_wiadomo'):
            cz.append(f'{g} — nie wiadomo (źródło nie odpowiedziało albo odpowiedź niejasna) ℹ️')
        elif not o.get('prob'):
            cz.append(f'{g} — sprawdzanie od {(dt.date.fromisoformat(o["od"]) + dt.timedelta(days=WH_NOWE_OD_DNI)).isoformat()} (raport miesięczny)')
        elif o.get('zakres'):
            cz.append(f'{g} — brak nowszego w dniach {o["zakres"][0]}–{o["zakres"][1]} ✅')
        else:
            cz.append(f'{g} — brak nowszego niż {o["od"]} ✅')
    return '- Nowe raporty dowodu rezerw giełd (listy portfeli; sprawdzone dziś): ' + '; '.join(cz) + '.'


def wh_zmiany(j):
    """v230: wieloryby.json → {giełda: dzień zmiany listy portfeli (gieldy[g].zmiana)}; brak = {}."""
    G = j.get('gieldy') if isinstance(j, dict) and isinstance(j.get('gieldy'), dict) else {}
    return {g: v['zmiana'] for g, v in G.items() if isinstance(v, dict) and isinstance(v.get('zmiana'), str) and re.match(r'^\d{4}-\d{2}-\d{2}$', v['zmiana'])}


WH_POLNOC_H = 2       # v249: migawka „pierwsza z doby” z pliku wielorybów (hist) — tylko wykonana do tylu godzin po północy UTC
WH_POLNOC_SP = 7200   # v249: para z migawek o północy = pełna doba (24 h w blokach po 12 s) — spełnia WH_DOBA_BLOKI


def _wh_polnoc(hist):
    """v249: data/wieloryby.json → hist ({giełda: [[dzień, czas bloku, eth, usdt, usdc, wersja listy], …]}) → {dzień: {(giełda, aktywo): (jednostki,
    czas, wersja listy)}}; tylko migawki z tego samego dnia, wykonane do WH_POLNOC_H h po północy UTC (zbieracz zapisuje pierwszą z doby —
    po awarii mogła być później)."""
    out = {}
    for g, rows in (hist.items() if isinstance(hist, dict) else ()):
        for r in rows if isinstance(rows, list) else ():
            if not (isinstance(r, list) and len(r) >= 5 and _dzien(r[0]) and isinstance(r[1], str) and r[1][:10] == r[0]):
                continue
            try:
                if int(r[1][11:13]) >= WH_POLNOC_H:
                    continue
            except ValueError:
                continue
            for a, i in (('ETH', 2), ('USDT', 3), ('USDC', 4)):
                if isinstance(r[i], (int, float)) and not isinstance(r[i], bool) and r[i] == r[i]:
                    out.setdefault(r[0], {})[(g, a)] = (float(r[i]), r[1], r[5] if len(r) > 5 else None)
    return out


def _wh_rozb_polnoc(H, d, row_d):
    """v249: pary dnia archiwum `d` z migawek o północy: zmiana salda między migawkami z d − 1 i d (cała doba d − 1; ta sama wersja listy portfeli)
    vs przelewy netto z wiersza archiwum d (suma pełnej doby d − 1) → {(giełda, aktywo): (zmiana, netto, |zmiana − netto|, WH_POLNOC_SP)};
    zmiana w jednostkach po kursie z wiersza archiwum (saldo USD / jednostki) — ruch kursu ETH nie jest przelewem."""
    if not _dzien(d):
        return {}
    A = H.get((dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()) or {}
    B = H.get(d) or {}
    out = {}
    for k, row in row_d.items():
        if k not in A or k not in B or A[k][2] != B[k][2]:
            continue
        try:
            u, usd, net = float(row[3]), float(row[4]), float(row[7])
        except ValueError:
            continue
        if not u:
            continue
        delta = (B[k][0] - A[k][0]) * (usd / u)
        out[k] = (delta, net, abs(delta - net), WH_POLNOC_SP)
    return out


IXF_SERIE = (('GSPC', 'SP500', 'S&P 500'), ('IXIC', 'NASDAQCOM', 'Nasdaq Composite'), ('DJI', 'DJIA', 'Dow Jones'),
             ('N225', 'NIKKEI225', 'Nikkei 225'))   # v257: indeksy strony, które FRED podaje od ich wydawców (bez klucza)
IXF_DNI = 45       # v257: okno porównania — dni kalendarzowe wstecz od dziś
IXF_TOL = 0.02     # v257: % — różnica do tylu = zgodne (zaokrąglenia: dostawca strony podaje zamknięcia do 4 miejsc)
IXF_ZLE = 0.1      # v257: % — starsza sesja różna o więcej = ⚠️ (kolejne pobranie z zakładką 10 dni powinno ją już poprawić)
IXF_WYD_STARE_H = 36   # v261: dane wydawcy pobrane dawniej (zbieracz odświeża co 3 h) = informacja zamiast ✅


def ixf_porownanie(rows, F, od):
    """v257: seria strony [[dzień, zamknięcie], …] vs {dzień: zamknięcie} wydawcy od dnia `od` → {'n', 'zgodne', 'ost', 'ost_roz',
    'roznice': [(dzień, strona, wydawca, %)], 'bez_sesji': [dni strony, których wydawca nie ma, choć ma późniejsze], 'luki': [dni wydawcy
    bez wiersza strony, do ostatniego dnia strony]} albo None. Ostatni dzień strony osobno (ost_roz) — może być zamknięciem wstępnym."""
    S = {r[0]: r[1] for r in (rows or []) if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str) and r[0] >= od
         and isinstance(r[1], (int, float)) and not isinstance(r[1], bool) and 0 < r[1] < float('inf')}
    F = {d: v for d, v in (F or {}).items() if d >= od and isinstance(v, (int, float)) and 0 < v < float('inf')}
    if not S or not F:
        return None
    ost, fmax = max(S), max(F)
    out = {'n': 0, 'zgodne': 0, 'ost': ost, 'ost_roz': None, 'roznice': [], 'bez_sesji': [], 'luki': [], 'wyd_do': fmax}   # v261: do kiedy dane wydawcy
    for d in sorted(S):
        if d in F:
            out['n'] += 1
            p = round((S[d] / F[d] - 1) * 100, 3)
            if abs(p) <= IXF_TOL:
                out['zgodne'] += 1
            elif d == ost:
                out['ost_roz'] = (d, S[d], F[d], p)
            else:
                out['roznice'].append((d, S[d], F[d], p))
        elif d < fmax:
            out['bez_sesji'].append(d)
    out['luki'] = [d for d in sorted(F) if d <= ost and d not in S]
    return out


def ixf_sprawdz(ix, wyd=None, now=None):
    """v257/v259: 4 indeksy strony vs wydawcy → {'od', 'wyniki': [{'s', 'nazwa', 'at', 'wyd_at', … ixf_porownanie albo 'brak'}]}. v259: serie
    wydawców z pliku indeksów (część 'wyd' — zbieracz pobiera je z FRED z kluczem co 3 h); v257 pytała FRED bez klucza, ale z maszyn GitHub
    FRED nie odpowiadał w 30 s (06.10 18:09 UTC — wszystkie 4 „brak porównania”). Ten blok kontroli działa bez sieci."""
    now = now or NOW
    od = (now.date() - dt.timedelta(days=IXF_DNI)).isoformat()
    W = wyd.get('d') if isinstance(wyd, dict) and isinstance(wyd.get('d'), dict) else {}
    WA = wyd.get('at_s') if isinstance(wyd, dict) and isinstance(wyd.get('at_s'), dict) else {}
    wyn = []
    for s, fid, nazwa in IXF_SERIE:
        rec = ix.get(s) if isinstance(ix, dict) and isinstance(ix.get(s), dict) else {}
        w = {'s': s, 'nazwa': nazwa, 'at': rec.get('at') if isinstance(rec.get('at'), str) else None,
             'wyd_at': WA.get(s) if isinstance(WA.get(s), str) else None}
        F = {r[0]: r[1] for r in (W.get(s) if isinstance(W.get(s), list) else []) if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str)
             and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)}
        if not F:
            w['brak'] = f'zbieracz nie podał serii wydawcy {fid}'
        else:
            c = ixf_porownanie(rec.get('d') if isinstance(rec.get('d'), list) else [], F, od)
            if c is None:
                w['brak'] = 'seria strony albo wydawcy bez sesji w oknie porównania'
            else:
                w.update(c)
        if w['wyd_at'] and not w.get('brak'):   # v261 (przegląd v259): dane wydawcy, które przestały się odświeżać — nie „zgodne ✅”
            try:
                t = dt.datetime.fromisoformat(w['wyd_at'])
                t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
                w['wyd_stare'] = (now - t).total_seconds() > IXF_WYD_STARE_H * 3600
            except ValueError:
                pass
        wyn.append(w)
    return {'od': od, 'wyniki': wyn}


def _ixf_n(x):
    return f'{x:,.2f}'.replace(',', ' ').replace('.', ',')


def _ixf_p(p):
    return f'{p:+.2f}%'.replace('.', ',')


def ixf_uwagi(o):
    """v257: uwaga tylko dla starszej sesji różnej o więcej niż IXF_ZLE (ponowne pobranie jej nie poprawiło); reszta — informacja w wierszu."""
    u = []
    for w in (o or {}).get('wyniki') or []:
        zle = [r for r in w.get('roznice') or [] if abs(r[3]) > IXF_ZLE]
        if zle:
            u.append(f"indeks {w['nazwa']}: zamknięcie na stronie różni się od wydawcy ponad {IXF_ZLE:g}% także po ponownym pobraniu: ".replace('.', ',')
                     + ', '.join(f'{d}: {_ixf_n(a)} vs {_ixf_n(b)} ({_ixf_p(p)})' for d, a, b, p in zle[:3])
                     + ' — sprawdzić dane dostawcy indeksów')
    return u


def ixf_wiersz(o):
    """v257: wiersz raportu „Indeksy vs wydawcy”: zgodne sesje, różne (⚠️ ponad IXF_ZLE, inaczej ℹ️), ostatnia sesja różna (ℹ️, z godziną
    pobrania), sesje bez odpowiednika (ℹ️); brak porównania — ℹ️. Brak wyniku — None (wiersza nie ma)."""
    if not isinstance(o, dict):
        return None
    if o.get('brak'):
        return f'- Indeksy vs wydawcy (FRED): brak porównania ({o["brak"]}) ℹ️.'
    cz, zle = [], False
    for w in o.get('wyniki') or []:
        if w.get('brak'):
            cz.append(f"{w['nazwa']} — brak porównania ({w['brak']}) ℹ️")
            continue
        x = []
        if w.get('roznice'):
            z = any(abs(r[3]) > IXF_ZLE for r in w['roznice'])
            zle = zle or z
            x.append('różne: ' + ', '.join(f'{d} {_ixf_p(p)}' for d, a, b, p in w['roznice'][:5]) + (' ⚠️' if z else ' ℹ️'))
        if w.get('ost_roz'):
            d, a, b, p = w['ost_roz']
            kiedy = str(w.get('at') or '')[:16].replace('T', ' ')
            x.append(f'ostatnia sesja {d}: {_ixf_n(a)} vs {_ixf_n(b)} ({_ixf_p(p)})' + (f' — pobrana {kiedy} UTC' if kiedy else '')
                     + ', możliwe zamknięcie wstępne; następne pobranie ją nadpisze ℹ️')
        if w.get('bez_sesji'):
            x.append('sesje, których wydawca nie ma: ' + ', '.join(w['bez_sesji'][:5]) + ' ℹ️')
        if w.get('luki'):
            x.append('sesje wydawcy bez wiersza na stronie: ' + ', '.join(w['luki'][:5]) + ' ℹ️')
        if w.get('wyd_stare'):   # v261
            x.append(f"dane wydawcy pobrane {str(w['wyd_at'])[:16].replace('T', ' ')} UTC — ponad {IXF_WYD_STARE_H} h temu ℹ️")
        cz.append(f"{w['nazwa']} — zgodne {w['zgodne']} z {w['n']} sesji" + (f" (wydawca do {w['wyd_do']})" if w.get('wyd_do') else '')
                  + ('; ' + '; '.join(x) if x else ' ✅'))
    return f'- Indeksy vs wydawcy (FRED, {IXF_DNI} dni): ' + ' · '.join(cz) + '.'


IX_OPOZ_DNI = 1      # v254/v258: seria indeksu starsza od dnia odniesienia o więcej DNI ROBOCZYCH (pn–pt) = „opóźniona” (informacja: rotacja, święto)
IX_STARE_DNI = 9     # v258: … o więcej niż tyle dni roboczych = ⚠️ (seria się zacięła). Przegląd v254: 10 dni kalendarzowych to mniej niż prawdziwe
                     # przerwy giełd — Szanghaj, Święto Wiosny 2026: bez sesji 13.02–24.02 (7 dni roboczych); Indonezja 2025: 8; z jednym nieudanym
                     # pobraniem w dniu otwarcia — 9
IX_WSZYSTKIE_DNI = 3   # v258: najnowsza sesja wszystkich serii starsza od dziś o więcej dni roboczych = ⚠️ (dostawca stoi, choć plik jest świeży)
IX_GRUPA_MIN = 3       # v263: świeżość serii wobec jej dostawcy, gdy ma co najmniej tyle serii (inaczej wobec wszystkich)


def _dni_rob(a, b):
    """v258: dni robocze (pn–pt) po dniu a do dnia b włącznie (daty); b ≤ a → 0."""
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        n += d.weekday() < 5
    return n


IX_ZMIANY_DNI = 7    # v260: poprawki dostawcy indeksów z tylu ostatnich dni w raporcie


def indeksy_zmiany(ix, now=None):
    """v260: poprawki dostawcy z pola 'rew' serii (zbieracz, v260) z ostatnich IX_ZMIANY_DNI dni → [(symbol, dzień, stare, nowe albo None,
    zmiana % albo None, czy ostatnia sesja pobrania, czas poprzedniego pobrania)], od najnowszej poprawki."""
    od = (now or NOW) - dt.timedelta(days=IX_ZMIANY_DNI)
    out = []
    for s, v in sorted((ix or {}).items()):
        for r in (v.get('rew') if isinstance(v, dict) and isinstance(v.get('rew'), list) else []):
            if not (isinstance(r, list) and len(r) == 6 and _dzien(r[0]) and isinstance(r[1], (int, float)) and r[1] > 0):
                continue
            try:
                t = dt.datetime.fromisoformat(str(r[4]))
            except ValueError:
                continue
            if (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)) < od:
                continue
            nowe = r[2] if isinstance(r[2], (int, float)) and not isinstance(r[2], bool) else None
            out.append((s, r[0], r[1], nowe, round((nowe / r[1] - 1) * 100, 3) if nowe is not None else None, r[5] is True,
                        r[3] if isinstance(r[3], str) else None, str(r[4])))
    out.sort(key=lambda x: x[7], reverse=True)
    return [x[:7] for x in out]


def _odm(n, f1, f2, f5):
    """v261: polska odmiana po liczebniku — 1 seria, 3 serie, 22 serie, 5 serii, 12 serii."""
    return f1 if n == 1 else f2 if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else f5


def _serie(n):
    return _odm(n, 'seria', 'serie', 'serii')


def _dni_r(n):
    """v263: „1 dzień roboczy”, „4 dni robocze”, „5 dni roboczych”."""
    return f'{n} {_odm(n, "dzień roboczy", "dni robocze", "dni roboczych")}'


def _ix_swiezy(t, now=None):
    """v261: czas ISO z ostatnich IX_ZMIANY_DNI dni (ślad 'luka' w kontroli)."""
    try:
        x = dt.datetime.fromisoformat(str(t))
    except ValueError:
        return False
    return (x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc)) >= (now or NOW) - dt.timedelta(days=IX_ZMIANY_DNI)


def indeksy_ocena(ix, now=None):
    """v254/v258: świeżość każdej serii indeksów (indeksy.json → ix: {symbol: {'d': [[dzień, zamknięcie], …], 'bad_at'?}}) → {'n', 'swieze',
    'najnowsza', 'opoznione': [(symbol, dzień, dni robocze)], 'stare': [...], 'puste': [(symbol, od)], 'przyszle': [(symbol, dzień)],
    'wszystkie': dni robocze od najnowszej sesji do dziś} albo None. v258 (przegląd): dzień odniesienia = najnowsza sesja wszystkich serii, ale
    nie później niż dziś (UTC) — sesja z przyszłości (błąd dostawcy) osobno i pominięta w ocenie; odstępy w dniach roboczych (pn–pt)."""
    if not isinstance(ix, dict) or not ix:
        return None
    dzis = (now or NOW).date()
    ost, puste, przyszle = {}, [], []
    for s, v in sorted(ix.items()):
        d = v.get('d') if isinstance(v, dict) else None
        dd = [r[0] for r in d if isinstance(r, list) and len(r) >= 2 and _dzien(r[0]) and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)
              and r[1] == r[1]] if isinstance(d, list) else []
        fut = [x for x in dd if dt.date.fromisoformat(x) > dzis]
        if fut:
            przyszle.append((s, max(fut)))
            dd = [x for x in dd if x not in fut]
        if dd:
            ost[s] = max(dd)
        elif not fut:
            puste.append((s, str(v.get('bad_at') or v.get('fmp_bad_at') or '')[:10] if isinstance(v, dict) else ''))   # v273: przerwa FMP
    out = {'n': len(ix), 'swieze': 0, 'najnowsza': None, 'opoznione': [], 'stare': [], 'puste': puste, 'przyszle': przyszle, 'wszystkie': None,
           'zmiany': indeksy_zmiany(ix, now),
           'pozniej': [(s, v['h+']) for s, v in sorted(ix.items()) if isinstance(v, dict) and isinstance(v.get('h+'), int)
                       and not isinstance(v.get('h+'), bool) and v['h+'] > 0]}   # v262: nauczone przesunięcia pory pobierania
    if not ost:
        return out
    najn = max(ost.values())
    out['najnowsza'] = najn
    gr = {}   # v261 (przegląd v258): „dostawca stoi” z najnowszej sesji GŁÓWNEGO dostawcy — FTSE z drugiego (src 'fmp') nie zasłania przestoju
    for s, x in ost.items():
        gr.setdefault(str(ix[s].get('src') or '') if isinstance(ix.get(s), dict) else '', []).append(x)
    gl = max(gr.values(), key=len)
    out['n_gl'], out['najnowsza_gl'] = len(gl), max(gl)
    # v278 (przegląd v273): grupa drugiego dostawcy (≥ IX_GRUPA_MIN serii) ponad IX_WSZYSTKIE_DNI dni roboczych za najnowszą sesją wszystkich —
    # cały ten dostawca stoi (wcześniej mierzony tylko do własnej najnowszej sesji: przestój 6 serii FMP dawał jedynie ℹ️ „opóźnione”)
    out['grupy_stoja'] = sorted((zr0 or 'główny', max(g), len(g), _dni_rob(dt.date.fromisoformat(max(g)), dt.date.fromisoformat(najn)))
                                for zr0, g in gr.items() if g is not gl and len(g) >= IX_GRUPA_MIN
                                and _dni_rob(dt.date.fromisoformat(max(g)), dt.date.fromisoformat(najn)) > IX_WSZYSTKIE_DNI)
    out['wszystkie'] = _dni_rob(dt.date.fromisoformat(max(gl)), dzis)
    out['luki_odp'] = [(s, str(v['luka'][0]), v['luka'][1], v['luka'][2], v['luka'][3]) for s, v in sorted(ix.items())   # v261: odpowiedzi z luką
                       if isinstance(v, dict) and isinstance(v.get('luka'), list) and len(v['luka']) == 4 and _ix_swiezy(v['luka'][0], now)]
    zr = lambda s: str(ix[s].get('src') or '') if isinstance(ix.get(s), dict) else ''  # noqa: E731
    for s, x in sorted(ost.items()):   # v263 (przegląd v261): świeżość wobec najnowszej sesji WŁASNEGO dostawcy (grupa ≥ IX_GRUPA_MIN serii)
        g = gr[zr(s)]
        duza = len(g) >= IX_GRUPA_MIN
        n = _dni_rob(dt.date.fromisoformat(x), dt.date.fromisoformat(max(g) if duza else najn))
        if n > IX_STARE_DNI:   # v267 (przegląd v264): zacięcie wobec własnego dostawcy najpierw — nie ginie, gdy cały dostawca jest w tyle
            out['stare'].append((s, x, n))
        elif duza and _dni_rob(dt.date.fromisoformat(max(g)), dt.date.fromisoformat(najn)) > IX_OPOZ_DNI:   # v264 (przegląd v263): cały dostawca w tyle —
            out['opoznione'].append((s, x, _dni_rob(dt.date.fromisoformat(x), dt.date.fromisoformat(najn))))   # seria opóźniona wobec wszystkich, bez osobnej ⚠️
        elif n > IX_OPOZ_DNI:
            out['opoznione'].append((s, x, n))
        else:
            out['swieze'] += 1
    return out


def indeksy_uwagi(o):
    """v254/v258: uwagi — seria zacięta, sesja z przyszłości, dostawca stoi (wszystkie serie bez nowych sesji)."""
    o = o or {}
    u = [f'indeksy giełdowe: {s} bez nowych sesji od {x} ({_dni_r(n)} wobec najnowszej sesji innych indeksów) — sprawdzić pobieranie tego indeksu'
         for s, x, n in o.get('stare') or []]
    u += [f'indeksy giełdowe: {s} ma sesję z datą z przyszłości ({x}) — błąd danych dostawcy (strona może pokazywać ją jako ostatnią); w ocenie świeżości pominięta'
          for s, x in o.get('przyszle') or []]
    for zr0, x, n, d in o.get('grupy_stoja') or []:   # v278: drugi dostawca stoi
        u.append(f'indeksy giełdowe: drugi dostawca indeksów ({zr0}, {n} {_serie(n)}) — najnowsza sesja {x}, {_dni_r(d)} za pozostałymi; '
                 'dostawca oddaje stare dane albo pobieranie stoi (zapas — gdy FMP nie da sesji w ciągu 2 h 15 min, raz na sesję i tylko z wolnego limitu)')   # 2 h 15 min = IX_ZAPAS_PO zbieracza (test v290)
    if (o.get('wszystkie') or 0) > IX_WSZYSTKIE_DNI:   # v261: główny dostawca (grupa z największą liczbą serii)
        n = o.get('n_gl') or 0
        u.append(f'indeksy giełdowe: najnowsza sesja głównego dostawcy indeksów ({n} {_serie(n)}) to {o.get("najnowsza_gl") or o["najnowsza"]} — '
                 f'{_dni_r(o["wszystkie"])} bez nowych sesji; dostawca oddaje stare dane albo pobieranie stoi')
    return u


def indeksy_wiersz(o):
    """v254/v258: wiersz raportu „Indeksy giełdowe” — świeże, opóźnione (ℹ️), zacięte (⚠️), z przyszłości (⚠️), wszystkie stare (⚠️), bez danych (ℹ️)."""
    if not isinstance(o, dict):
        return '- Indeksy giełdowe: plik bez serii indeksów ℹ️.'
    cz = [f'świeże {o["swieze"]} z {o["n"]}' + (f' (do {o["najnowsza"]})' if o.get('najnowsza') else '')]
    zle = (o.get('wszystkie') or 0) > IX_WSZYSTKIE_DNI
    if zle:   # v261: główny dostawca
        n = o.get('n_gl') or 0
        cz.append(f'najnowsza sesja głównego dostawcy ({n} {_serie(n)}) {_dni_r(o["wszystkie"])} temu ⚠️')
    for zr0, x, n, d in o.get('grupy_stoja') or []:   # v278
        cz.append(f'drugi dostawca ({zr0}, {n} {_serie(n)}) stoi: najnowsza sesja {x}, {_dni_r(d)} za pozostałymi ⚠️')
    if o.get('przyszle'):
        cz.append('sesja z datą z przyszłości: ' + ', '.join(f'{s} ({x})' for s, x in o['przyszle']) + ' ⚠️')
    if o.get('stare'):
        cz.append('bez nowych sesji ponad ' + f'{IX_STARE_DNI} dni roboczych: ' + ', '.join(f'{s} (od {x})' for s, x, n in o['stare']) + ' ⚠️')
    if o.get('opoznione'):
        op = o['opoznione']   # v264: najwyżej 8 nazw (przy przestoju dostawcy byłoby 22)
        cz.append('opóźnione: ' + ', '.join(f'{s} ({x})' for s, x, n in op[:8]) + (f' (+{len(op) - 8})' if len(op) > 8 else '') + ' ℹ️')
    if o.get('puste'):
        cz.append('bez danych (dostawca nie podaje): ' + ', '.join(s for s, od in o['puste']) + ' ℹ️')
    if o.get('zmiany'):   # v260: poprawki dostawcy po naszym pobraniu (informacja; ostatnia sesja = pobrana za wcześnie)
        zz = o['zmiany']
        ost = sorted({s for s, d, a, b, p, last, at in zz if last})
        cz.append(f'zamknięcia poprawione przez dostawcę po pobraniu ({IX_ZMIANY_DNI} dni): '
                  + ', '.join(f'{s} {d} ' + (f'{p:+.2f}%'.replace('.', ',') if p is not None else 'usunięta') for s, d, a, b, p, last, at in zz[:8])
                  + (f' (+{len(zz) - 8})' if len(zz) > 8 else '')
                  + (f'; ostatnia sesja pobrana za wcześnie: {", ".join(ost)}' if ost else '') + ' ℹ️')
    if o.get('luki_odp'):   # v261: odpowiedź dostawcy z wieloma brakującymi sesjami — nic nie usunięto
        cz.append('odpowiedź dostawcy z luką (sesje zostawione): ' + ', '.join(f'{s} ({n} {_odm(n, "sesja", "sesje", "sesji")}, {a}–{b})'
                                                                             for s, t, n, a, b in o['luki_odp'][:5]) + ' ℹ️')
    if o.get('pozniej'):   # v262: samouczenie — indeksy pobierane później, bo dostawca poprawiał zamknięcia pobrane tuż po sesji
        cz.append('pora pobierania przesunięta (nauczone z poprawek i spóźnień dostawcy): ' + ', '.join(f'{s} +{h} h' for s, h in o['pozniej']) + ' ℹ️')
    return '- Indeksy giełdowe: ' + '; '.join(cz) + ('.' if (zle or o.get('przyszle') or o.get('stare') or o.get('opoznione') or o.get('puste')
                                                       or o.get('zmiany') or o.get('luki_odp') or o.get('pozniej')) else ' ✅.')


def wieloryby_ocena(path, zmiany=None, hist=None):
    """v174: zgodność sald i przepływów wielorybów na tle historii. Przepływy to tylko przelewy ≥ 1 mln USD w oknie 24 h, a migawki sald dzieli
    tyle, ile minęło między zapisami archiwum (05.10: od 7,7 do 28 h) — rozbieżność jest normalna. Uwaga tylko, gdy migawki pary dzieli ok. doba
    (WH_DOBA_BLOKI) i jej rozbieżność przekracza zwykły próg (WH_PROG %, WH_MIN_USD) ORAZ WH_RAZY × medianę jej rozbieżności z co najmniej
    WH_HIST_MIN wcześniejszych porównywalnych dni. v175: odstęp liczony dla KAŻDEJ pary z jej własnych bloków — para z innym odstępem pominięta
    (pole pominiete), reszta porównana; żadnej pary o dobę = bez porównania (powód w 'pomin'). Mniej niż dwa dni archiwum = None.
    → {'dzien', 'poprzedni', 'poprzedni_pokaz', 'porownane', 'pominiete', 'odstep_h' (mediana par), 'pomin', 'zle': [(giełda, aktywo, zmiana,
    netto, rozb., mediana)], 'bez_historii', 'lista', 'polnoc'}. v230: zmiany = {giełda: dzień zmiany listy portfeli} — pary tej giełdy
    obejmujące ten dzień (także jako dzień poprzedni: migawka archiwum mogła być przed zmianą) pominięte — nowe portfele to skok salda bez
    przelewów. v249: hist = pole hist pliku wielorybów — para z migawek o północy UTC (zgrana z dobą przelewów) zastępuje dziś parę z migawek
    archiwum ('polnoc' — ile dziś takich par). v250: historia (norma pary) liczona osobno dla par z północy i z archiwum — para dnia oceniana
    normą swojego rodzaju (rozbieżności par z archiwum są zwykle większe); 'poprzedni_pokaz' — przy samych parach z północy dzień d − 1."""
    by = _wh_csv(path)
    if not by:
        return None
    days = sorted(by)
    if len(days) < 2:
        return None
    d, p = days[-1], days[-2]
    doba = lambda sp: sp is not None and WH_DOBA_BLOKI[0] <= sp <= WH_DOBA_BLOKI[1]  # noqa: E731
    Hn = _wh_polnoc(hist) if hist else {}

    def obie(a, b):   # v250: pary z archiwum ('a') i z migawek o północy ('p') osobno
        return ({k: v + ('a',) for k, v in _wh_rozb(by[a], by[b]).items()},
                {k: v + ('p',) for k, v in _wh_rozb_polnoc(Hn, b, by[b]).items()})
    A, Pn = obie(p, d)
    dzis = dict(A)
    dzis.update(Pn)   # v249: para z migawek o północy zastępuje dziś parę z migawek archiwum (te robione są o różnych porach)
    zm = lambda g, a, b: isinstance(zmiany, dict) and isinstance(zmiany.get(g), str) and a <= zmiany[g] <= b  # noqa: E731 — v230
    lista = sorted({k[0] for k in dzis if zm(k[0], p, d)})
    dzis = {k: v for k, v in dzis.items() if not zm(k[0], p, d)}
    S = sorted(x[3] for x in dzis.values() if x[3] is not None)
    dm1 = (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat() if _dzien(d) else p
    out = {'dzien': d, 'poprzedni': p, 'porownane': sum(1 for x in dzis.values() if doba(x[3])),
           'pominiete': sum(1 for x in dzis.values() if not doba(x[3])),
           'odstep_h': round(S[len(S) // 2] * 12 / 3600, 1) if S else None, 'pomin': None, 'zle': [], 'bez_historii': 0, 'lista': lista,
           'polnoc': sum(1 for x in dzis.values() if x[4] == 'p')}
    out['poprzedni_pokaz'] = dm1 if out['polnoc'] and out['polnoc'] == out['porownane'] else p   # v250: podpis zgodny z porównanymi migawkami
    if not out['porownane']:   # v253: powód z faktycznych danych (nie zgadywany)
        pw = []
        if lista:   # v258 (przegląd): pary giełd z nową listą portfeli odpadły — powód zawsze wymieniony (wpadało w „brak numeru bloku”)
            pw.append('nowa lista portfeli — bez porównania: ' + ', '.join(lista))
        reszta = [r for k, r in by[d].items() if k[0] not in lista]   # v258: giełdy bez nowej listy
        if reszta and all(len(r) > 7 and not str(r[7]).strip() for r in reszta):
            pw.append('archiwum bez sum przelewów doby (doba niepełna albo sum brak)')
        elif out['odstep_h'] is not None:
            pw.append(f"odstęp migawek {out['odstep_h']:.1f} h — porównanie z przepływami 24 h tylko przy ok. dobie")
        elif dzis:   # v258: pary są, ale żadna nie ma numerów bloków obu migawek
            pw.append('brak numeru bloku migawki — bez porównania')
        elif reszta:   # v258: żadnej pary giełda/aktywo z liczbami w obu dniach
            pw.append(f'brak wspólnych par giełda/aktywo z liczbami w dniach {p} i {d}')
        if hist and not out['polnoc']:   # v250/v253: migawki o północy — dzień i giełdy, których migawki brak albo jest późna; inna wersja listy
            A, B = Hn.get(dm1) or {}, Hn.get(d) or {}
            ga = sorted({k[0] for k in by[d] if k not in A})
            gb = sorted({k[0] for k in by[d] if k not in B})
            gw = sorted({k[0] for k in by[d] if k in A and k in B and A[k][2] != B[k][2]})
            cz = [f'{x} — {", ".join(g)}' for x, g in ((dm1, ga), (d, gb)) if g]
            if cz:
                pw.append(f'migawki o północy brak albo później niż {WH_POLNOC_H} h po północy UTC: ' + '; '.join(cz))
            if gw:
                pw.append('inna wersja listy portfeli w migawkach o północy: ' + ', '.join(gw))
        out['pomin'] = '; '.join(pw)
        return out
    norma = {}
    for a, b in zip(days[:-2], days[1:-1]):
        for X in obie(a, b):
            for k, (_dl, _n, r, sp, rd) in X.items():
                if doba(sp) and not zm(k[0], a, b):
                    norma.setdefault((k, rd), []).append(r)
    for k, (delta, net, roz, sp, rd) in sorted(dzis.items()):
        if not doba(sp) or not (roz > WH_MIN_USD and roz > WH_PROG / 100 * max(abs(delta), abs(net), WH_MIN_USD)):
            continue
        h = sorted(norma.get((k, rd), []))   # v250: norma z par tego samego rodzaju
        if len(h) < WH_HIST_MIN:
            out['bez_historii'] += 1
            continue
        med = h[len(h) // 2] if len(h) % 2 else (h[len(h) // 2 - 1] + h[len(h) // 2]) / 2
        if roz > WH_RAZY * med:
            out['zle'].append((k[0], k[1], delta, net, roz, med))
    return out


PR_USDC_PP = 0.10    # v128: pkt proc. — premia USA przez USDT (poprawiona) vs przez parę z USDC; większa różnica = uwaga (kurs USDT albo USDC odbiega od dolara?)
PR_CB_MAX = 2.0      # % — |premia USA| ponad to = możliwy zły odczyt (uwaga)
PR_STARE_H = 3       # h — ostatnia minuta odczytu starsza, choć plik młody = giełdy nie odpowiadają (uwaga)
PR_KR_MAX, PR_USDT_MAX = 10.0, 5.0   # v129: % — |premia Korei BTC/ETH| i |USDT w Korei| ponad to = możliwy zły odczyt (uwaga)
PR_FX_PCT = 0.01     # v129: % — kurs KRW/USD wprost vs ten sam kurs w pliku rynki (ta sama data); większa różnica = uwaga


def premie_porownanie(prem, rynki=None, now=None):
    """v128: zgodność premii krypto bez sieci (plik premie.json; v129 także rynki.json) → {'opis', 'uwagi', 'cb_usdc_pp'}.
    Tylko uwagi (⚠️), nigdy błąd: dziwny rynek to nie awaria strony."""
    now = now or NOW
    out = {'opis': '', 'uwagi': [], 'cb_usdc_pp': None}
    if not isinstance(prem, dict):
        out['opis'] = 'plik nie wczytany'
        return out
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731
    N = prem.get('now') if isinstance(prem.get('now'), dict) else {}
    cb = N.get('cb') if isinstance(N.get('cb'), dict) else {}
    txt = []
    b = cb.get('btc') if isinstance(cb.get('btc'), dict) else {}
    p, u = b.get('p'), b.get('usdc')
    if num(p) and num(u):
        g = round(abs(p - u), 3); out['cb_usdc_pp'] = g
        txt.append(f'USA BTC {p:+.2f}% (przez USDC {u:+.2f}%, różnica {g:.2f} pkt proc.)')
        if g > PR_USDC_PP:
            out['uwagi'].append(f'premia USA: przeliczenie przez USDT i przez USDC różni się o {g:.2f} pkt proc. (próg {PR_USDC_PP:g}) — kurs USDT albo USDC odbiega od dolara?')
    for c in ('btc', 'eth'):
        x = (cb.get(c) or {}).get('p') if isinstance(cb.get(c), dict) else None
        if num(x) and abs(x) > PR_CB_MAX:
            out['uwagi'].append(f'premia USA {c.upper()} {x:+.2f}% (ponad ±{PR_CB_MAX:g}%) — możliwy zły odczyt')
    last = max((B['win'][1] for B in N.values() if isinstance(B, dict) and isinstance(B.get('win'), list) and len(B['win']) == 2
                and isinstance(B['win'][1], str)), default=None)
    wp = wiek_danych(prem.get('at'), 'ts', 'h', now) if isinstance(prem.get('at'), str) else None
    wm = wiek_danych(last, 'ts', 'h', now) if last else None
    if wp is not None and wp <= LIMIT_MIN['premie'] and (wm is None or wm > PR_STARE_H * 60):
        out['uwagi'].append('premie krypto: giełdy nie odpowiadają — ' + (f'ostatnia minuta odczytu {last} UTC ({fmt_wiek(wm)} temu)' if last else 'brak odczytu') + ', choć plik jest świeży')
    # v129: Korea — (c) |premia BTC/ETH| > PR_KR_MAX %, |USDT| > PR_USDT_MAX % = możliwy zły odczyt; (b) kurs EBC wprost vs ten sam kurs
    # w pliku rynki (ta sama data): różnica > PR_FX_PCT % = uwaga (plik rynki zmienił metodę kursu?)
    kr = N.get('kr') if isinstance(N.get('kr'), dict) else {}
    for c, lim in (('btc', PR_KR_MAX), ('eth', PR_KR_MAX), ('usdt', PR_USDT_MAX)):
        x = (kr.get(c) or {}).get('p') if isinstance(kr.get(c), dict) else None
        if num(x):
            if c == 'btc':
                txt.append(f'Korea BTC {x:+.2f}% (kurs z {kr.get("fx_d") or "—"})')
            if abs(x) > lim:
                out['uwagi'].append(f'premia Korei {c.upper()} {x:+.2f}% (ponad ±{lim:g}%) — możliwy zły odczyt')
    fx = prem.get('fx') if isinstance(prem.get('fx'), dict) else {}
    fr = ((rynki.get('fx') or {}).get('now') or {}) if isinstance(rynki, dict) and isinstance(rynki.get('fx'), dict) else {}
    a, b2 = fx.get('v'), (fr.get('rates') or {}).get('KRW') if isinstance(fr.get('rates'), dict) else None
    out['fx_gap_pct'] = None
    if fx.get('src') == 'ecb' and num(a) and num(b2) and b2 > 0 and fx.get('d') == fr.get('date'):
        g = abs(a / b2 - 1) * 100; out['fx_gap_pct'] = round(g, 4)
        txt.append(f'kurs KRW/USD {fx["d"]}: wprost {a:.3f}, w pliku rynki {b2:.3f} (różnica {g:.3f}%)')
        if g > PR_FX_PCT:
            out['uwagi'].append(f'kurs KRW/USD {fx["d"]}: kurs wprost {a:.3f} i kurs z pliku rynki {b2:.3f} różnią się o {g:.3f}% (próg {PR_FX_PCT:g}%) — plik rynki zmienił metodę kursu?')
    out['opis'] = '; '.join(txt) or 'brak odczytu'
    return out


def czerwone_z_historii(hist, n=None):
    """Błędy zbieracza w n kolejnych kontrolach z RÓŻNYCH dni UTC (kontrola rusza też po pushu — kilka przebiegów jednego dnia to nie „3 dni z rzędu”)."""
    n = HIST_CZERWONE if n is None else n
    ost = {}
    for h in hist:
        if isinstance(h, dict) and isinstance(h.get('at'), str):
            ost[h['at'][:10]] = h   # ostatni przebieg dnia
    dni = sorted(ost)[-n:]
    return len(dni) >= n and all((ost[d].get('bledy_zbieracza') or 0) > 0 for d in dni)


def historia(path, wpis):
    """Dopisuje wpis do kontrola/historia.json (ostatnie HIST_N) i zwraca całą listę (najnowszy na końcu)."""
    hist = []
    try:
        with open(path, encoding='utf-8') as f:
            hist = json.load(f)
        if not isinstance(hist, list):
            hist = []
    except Exception:
        hist = []
    hist = [h for h in hist if isinstance(h, dict) and h.get('at') != wpis.get('at')] + [wpis]
    hist = hist[-HIST_N:]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=0)
    return hist


def pl_przebiegi(n):
    """Liczebnik: 1 nieudany przebieg / 2–4 nieudane przebiegi / 5+ (i 12–14) nieudanych przebiegów."""
    if n == 1:
        return '1 nieudany przebieg'
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f'{n} nieudane przebiegi'
    return f'{n} nieudanych przebiegów'


def pl_udane(n):
    """Liczebnik: 1 udany przebieg / 2–4 udane przebiegi / 0, 5+ (i 12–14) udanych przebiegów."""
    if n == 1:
        return '1 udany przebieg'
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f'{n} udane przebiegi'
    return f'{n} udanych przebiegów'


GH_OSTRZ_WF = ('strona.yml', 'zegar.yml', 'kontrola.yml', 'archiwum.yml', 'sondy.yml')   # v291: czynne przepływy (sondy_v128 — archiwalny)
GH_OSTRZ_RE = re.compile(r'deprecat|no longer supported|will be removed|will stop working|end of life|is being retired', re.I)
GH_OSTRZ_BUDZET_S = 30   # s — najdłużej odczyt adnotacji (5 przepływów: lista, zadania, adnotacje — ok. 15 zapytań)


def ostrzezenia_github(ann):
    """v291: {przepływ: [adnotacje ostatniego zakończonego przebiegu]} → [(przepływ, tekst)] — ostrzeżenia GitHuba (poziom „warning”) o
    przestarzałych akcjach albo systemie (np. „Node.js 20 is deprecated…”); bez powtórzeń tej samej treści w przepływie, tekst ≤ 160 znaków.
    Własne adnotacje kontroli i sond mają poziom „notice” — nie liczą się."""
    out, seen = [], set()
    for wf, L in (ann or {}).items():
        for a in L if isinstance(L, list) else []:
            if not isinstance(a, dict) or a.get('annotation_level') != 'warning':
                continue
            msg = ' '.join(str(a.get('message') or '').split())
            if not GH_OSTRZ_RE.search(msg) or (wf, msg[:80]) in seen:
                continue
            seen.add((wf, msg[:80])); out.append((wf, msg[:160]))
    return out


def github_ostrz_odczyt(hdr, getf=None):
    """v291/v292: adnotacje ostatniego zakończonego przebiegu każdego przepływu z GH_OSTRZ_WF → {'sprawdzone': liczba odczytanych przepływów,
    'znalezione': ostrzezenia_github(...), 'bledne': ['przepływ (błąd)', …]}. Każdy przepływ osobno — błąd jednego (404 po usunięciu, 5xx)
    nie przerywa pozostałych; wszystkie nieudane = RuntimeError. Budżet czasu GH_OSTRZ_BUDZET_S; `getf` — atrapa w testach."""
    getf = getf or get
    ann, t_g, nwf, bledne = {}, time.monotonic(), 0, []
    for wf in GH_OSTRZ_WF:
        if time.monotonic() - t_g > GH_OSTRZ_BUDZET_S:
            break
        try:
            _, bw, _ = getf(f'https://api.github.com/repos/{REPO}/actions/workflows/{wf}/runs?per_page=1&status=completed', headers=hdr)
            rr = [r for r in (json.loads(bw).get('workflow_runs') or []) if isinstance(r, dict) and r.get('id')]
            if not rr:
                continue
            _, bj, _ = getf(f'https://api.github.com/repos/{REPO}/actions/runs/{rr[0]["id"]}/jobs', headers=hdr)
            A_wf = []
            for j in [j for j in (json.loads(bj).get('jobs') or []) if isinstance(j, dict) and j.get('id')][:4]:
                _, ba, _ = getf(f'https://api.github.com/repos/{REPO}/check-runs/{j["id"]}/annotations', headers=hdr)
                A = json.loads(ba)
                A_wf += [x for x in (A if isinstance(A, list) else []) if isinstance(x, dict)]
            ann[wf] = A_wf; nwf += 1
        except Exception as e:  # noqa
            bledne.append(f'{wf} ({str(e)[:40] or type(e).__name__})')
    if bledne and not nwf:
        raise RuntimeError('; '.join(bledne)[:120])
    return {'sprawdzone': nwf, 'znalezione': ostrzezenia_github(ann), 'bledne': bledne}


STRAZNIK_WF = ('strona.yml', 'zegar.yml', 'kontrola.yml', 'archiwum.yml', 'straznik.yml')   # v354: przepływy z harmonogramem (jak ZAPLANOWANE w narzedzia/straznik.py; test pilnuje zgodności)
STRAZNIK_PRZEBIEG_DNI = 16   # v354: strażnik działa raz w tygodniu — 2 tygodnie + 2 dni zapasu: jeden pominięty poniedziałek nie jest alarmem (zapas do 60 dni jest ogromny)
STRAZNIK_COMMIT_DNI = 45     # v354: strażnik robi commit aktywności po 30 dniach bez commitu; 45 = nie zadziałał (GitHub wyłącza harmonogramy po 60)


def _straznik_t(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None


def _straznik_dni(s, now):
    t = _straznik_t(s)
    return None if t is None else max(0, (now - t).days)


def straznik_ocena(workflows, runs, commit_iso, now):
    """v354: lista przepływów repozytorium (API: pole state), zakończone przebiegi „Strażnika harmonogramów” (None = nieczytelne), data ostatniego
    commitu i chwila → {'czynne', 'razem', 'wylaczone', 'brak', 'przebieg_dni', 'przebieg_wynik', 'commit_dni', 'uwagi'}. Uwagi (nigdy błąd): przepływ z harmonogramem
    wyłączony albo nieobecny; strażnik nie działał dłużej niż STRAZNIK_PRZEBIEG_DNI (albo nigdy, choć przepływ istnieje dłużej) albo ostatni przebieg nieudany;
    ostatni commit starszy niż STRAZNIK_COMMIT_DNI."""
    stany, utw = {}, None
    for w in workflows if isinstance(workflows, list) else []:
        if isinstance(w, dict):
            n = os.path.basename(str(w.get('path') or ''))
            if n in STRAZNIK_WF:
                stany[n] = w.get('state')
                if n == 'straznik.yml':
                    utw = w.get('created_at')
    brak = [n for n in STRAZNIK_WF if n not in stany]
    wyl = [f'{n} ({stany[n]})' for n in STRAZNIK_WF if n in stany and stany[n] != 'active']
    S = {'czynne': sum(1 for v in stany.values() if v == 'active'), 'razem': len(STRAZNIK_WF), 'wylaczone': wyl, 'brak': brak,
         'przebieg_dni': None, 'przebieg_wynik': None, 'commit_dni': _straznik_dni(commit_iso, now), 'uwagi': []}
    u = S['uwagi']
    if wyl:
        u.append('wyłączone przepływy z harmonogramem: ' + ', '.join(wyl) + ' (Actions, Enable workflow; wyłączone przez GitHub strażnik włącza w poniedziałki, o ile sam działa)')
    if brak:
        u.append('brak w repozytorium przepływów: ' + ', '.join(brak))
    if runs is not None:
        gotowe = [(_straznik_t(r.get('created_at')), r) for r in runs if isinstance(r, dict) and r.get('status') == 'completed' and _straznik_t(r.get('created_at'))]
        if gotowe:
            t_ost, r_ost = max(gotowe, key=lambda x: x[0])
            S['przebieg_dni'], S['przebieg_wynik'] = max(0, (now - t_ost).days), r_ost.get('conclusion')
            if S['przebieg_dni'] > STRAZNIK_PRZEBIEG_DNI:
                u.append(f'strażnik nie działał od {S["przebieg_dni"]} dni (powinien raz w tygodniu)')
            if S['przebieg_wynik'] != 'success':
                u.append(f'ostatni przebieg strażnika zakończył się wynikiem „{S["przebieg_wynik"]}”')
        elif 'straznik.yml' in stany and (_straznik_dni(utw, now) or 0) > STRAZNIK_PRZEBIEG_DNI:
            u.append('strażnik nie miał jeszcze żadnego przebiegu, choć przepływ istnieje od ponad ' + str(STRAZNIK_PRZEBIEG_DNI) + ' dni')
    if S['commit_dni'] is not None and S['commit_dni'] > STRAZNIK_COMMIT_DNI:
        u.append(f'ostatni commit w repozytorium sprzed {S["commit_dni"]} dni (limit GitHuba 60; strażnik robi commit po 30)')
    return S


def straznik_odczyt(hdr, now, getf=None):
    """v354: 3 zapytania do API GitHuba (lista przepływów, zakończone przebiegi strażnika, ostatni commit) → straznik_ocena. Nieczytelna lista przepływów
    = wyjątek („?” w raporcie); nieczytelne przebiegi albo commit — pole None (bez uwagi o tym). `getf` — atrapa w testach."""
    getf = getf or get
    _, b, _ = getf(f'https://api.github.com/repos/{REPO}/actions/workflows?per_page=100', headers=hdr)
    wfs = json.loads(b).get('workflows') or []
    runs = commit = None
    try:
        _, b2, _ = getf(f'https://api.github.com/repos/{REPO}/actions/workflows/straznik.yml/runs?per_page=5&status=completed', headers=hdr)
        runs = json.loads(b2).get('workflow_runs') or []
    except Exception:  # noqa
        pass
    try:
        _, b3, _ = getf(f'https://api.github.com/repos/{REPO}/commits?per_page=1', headers=hdr)
        c = (json.loads(b3)[0].get('commit') or {})
        commit = (c.get('committer') or {}).get('date') or (c.get('author') or {}).get('date')
    except Exception:  # noqa
        pass
    return straznik_ocena(wfs, runs, commit, now)


def _straznik_temu(n):
    return '?' if n is None else ('dziś' if n == 0 else '1 dzień temu' if n == 1 else f'{n} dni temu')


def straznik_wiersz(S):
    """v354: wiersz raportu — przepływy czynne, ostatni przebieg strażnika, wiek ostatniego commitu; ⚠️ przy uwagach."""
    if S.get('blad'):
        return f'- Strażnik harmonogramów: ? (odczyt przerwany: {str(S["blad"])[:60]}).'
    pr = (f'ostatni przebieg strażnika {_straznik_temu(S.get("przebieg_dni"))} ({S.get("przebieg_wynik")})' if S.get('przebieg_dni') is not None
          else 'strażnik: brak zakończonego przebiegu (albo odczyt nieudany)')
    return (f'- Strażnik harmonogramów (raz w tygodniu): przepływy z harmonogramem czynne {S.get("czynne", 0)} z {S.get("razem", 0)}; {pr}; '
            f'ostatni commit w repozytorium {_straznik_temu(S.get("commit_dni"))} ' + ('⚠️ ' + '; '.join(S['uwagi']) + '.' if S.get('uwagi') else '✅.'))


def opis_kroku(zadanie, krok):
    """Nazwa nieudanego kroku po ludzku: publikacja GitHub Pages to zwykle chwilowa awaria po stronie GitHuba; długie nazwy kroków
    z workflow skrócone do części przed nawiasem / myślnikiem."""
    if not krok:
        return zadanie or None
    if 'deploy-pages' in krok:
        return 'publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba)'
    k = krok.split(' (')[0].split(' — ')[0].strip()
    return f'{zadanie} / {k}' if zadanie else k


def najdluzsze_udane(runs, now, n=3):
    """v194: identyfikatory n najdłuższych udanych przebiegów „Strona i dane” z ostatnich 24 h (od startu do ostatniej zmiany), malejąco."""
    od, out = now - dt.timedelta(hours=24), []
    for r in runs if isinstance(runs, list) else []:
        if not (isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and r.get('status') == 'completed' and r.get('conclusion') == 'success'):
            continue
        try:
            a = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
            b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
        except Exception:
            continue
        a, b = (x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc) for x in (a, b))
        if a >= od and b >= a:
            out.append(((b - a).total_seconds(), r.get('id')))
    return [i for _, i in sorted(out, key=lambda x: -x[0])[:n]]


BUDOWA_BUDZET_S = 90   # v205: s — odczyt czasów zadania budowy (API zadań) najwyżej tyle; limit całego zadania kontroli 12 min


def przebieg_min(r):
    """v205: minuty od startu do ostatniej zmiany przebiegu; zły zapis = None."""
    try:
        a = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
        b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
        return (b - a).total_seconds() / 60
    except Exception:
        return None


def budowa_kandydaci(runs, now, n=3, prog_min=20, cap=40):   # v203: cap 40 (było 10) — każdy udany > 20 min
    """v199: przebiegi do odczytu czasu zadania budowy: n najdłuższych udanych z 24 h i każdy udany dłuższy niż prog_min min (razem najwyżej cap)
    — przy czekaniu w kolejce najdłuższa budowa nie musi być wśród 3 najdłuższych przebiegów (przegląd 06.10)."""
    ids = najdluzsze_udane(runs, now, len(runs) if isinstance(runs, list) else 0)
    dl = {}
    for r in runs if isinstance(runs, list) else []:
        try:
            a = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
            b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
            dl[r.get('id')] = (b - a).total_seconds() / 60
        except Exception:
            continue
    return [i for k, i in enumerate(ids) if k < n or dl.get(i, 0) > prog_min][:cap]


def zadanie_min(jobs, nazwa):
    """v194: minuty zadania o tej nazwie (od startu zadania do końca, bez czekania w kolejce); brak albo zły czas = None."""
    for j in jobs if isinstance(jobs, list) else []:
        if isinstance(j, dict) and j.get('name') == nazwa:
            try:
                a = dt.datetime.fromisoformat(str(j.get('started_at')).replace('Z', '+00:00'))
                b = dt.datetime.fromisoformat(str(j.get('completed_at')).replace('Z', '+00:00'))
                m = (b - a).total_seconds() / 60
            except Exception:
                return None
            return m if m >= 0 else None
    return None


PRZ_OKNO = 6          # v327 (KON-01): tyle ostatnich zakończonych przebiegów (ok. godzina) ocenia „automat działa z przerwami”
PRZ_OKNO_BLAD = 3     # v327 (KON-01): tyle porażek w oknie (i ostatni zakończony nieudany) = BŁĄD; mniej = uwaga


def przebiegi_ocena(runs, now, kroki=None, pend=None):
    """v124.1: przebiegi automatu („Strona i dane”) z ostatnich 24 h → (actions, bledy, uwagi).
    v327 (KON-01): BŁĄD tylko, gdy automat NADAL nie działa: dwa ostatnie zakończone przebiegi nieudane albo ≥ PRZ_OKNO_BLAD porażek wśród
    PRZ_OKNO ostatnich zakończonych i ostatni też nieudany (było: ≥ 3 porażki w całej dobie — 06.10.2026 jedna świeża porażka po naprawionych
    sprzed 23 h dała fałszywy czerwony e-mail). Dawniej: dwa ostatnie zakończone przebiegi nieudane albo ≥ 3 porażki w 24 h i ostatni zakończony
    też nieudany. Jedna świeża porażka = uwaga („kolejny przebieg za ok. 20 min”). Porażki już naprawione (po ostatniej same udane) =
    uwaga z godzinami, krokiem i liczbą udanych przebiegów od ostatniej porażki. Przebiegi w toku i anulowane nie liczą się do serii.
    kroki: {id przebiegu: opis kroku} dla porażek (z API zadań; może brakować — wtedy sama godzina).
    v235: pend — {id przebiegu: oczekujące wdrożenia} dla przebiegów „waiting”: czeka na osobę (recenzent) = uwaga „zatwierdź”, nie błąd."""
    kroki = kroki or {}
    od = now - dt.timedelta(hours=24)

    def czas(r):
        try:
            t = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
            return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        except Exception:
            return None
    ost = [r for r in runs if isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and czas(r) is not None and czas(r) >= od]
    ost.sort(key=czas, reverse=True)
    z = {}
    for r in ost:
        w = r.get('conclusion') or r.get('status')
        z[w] = z.get(w, 0) + 1
    zak = [r for r in ost if r.get('status') == 'completed' and r.get('conclusion') in ('success', 'failure')]
    por = [r for r in ost if r.get('conclusion') == 'failure']
    z_rzedu = next((i for i, r in enumerate(zak) if r.get('conclusion') != 'failure'), len(zak))
    udane_po = next((i for i, r in enumerate(zak) if r.get('conclusion') == 'failure'), len(zak)) if por else None
    def trwanie(r):   # v190: minuty od startu do końca przebiegu (z czekaniem na maszyny); zły czas = None
        try:
            b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
            b = b if b.tzinfo else b.replace(tzinfo=dt.timezone.utc)
            return (b - czas(r)).total_seconds() / 60
        except Exception:
            return None
    trw = [x for x in (trwanie(r) for r in ost if r.get('status') == 'completed' and r.get('conclusion') == 'success') if x is not None and x >= 0]
    A = {'przebiegi_24h': len(ost), 'wg_wyniku': z, 'ostatni': ost[0].get('run_started_at') if ost else None,
         'najdluzszy_min': round(max(trw), 1) if trw else None,   # v190: najdłuższy udany przebieg w 24 h
         'ostatnia_porazka': por[0].get('run_started_at') if por else None, 'porazki_z_rzedu': z_rzedu, 'udane_po_porazce': udane_po,
         'porazki': [{'at': r.get('run_started_at'), 'krok': kroki.get(r.get('id'))} for r in por[:10]]}
    bledy, uwagi = [], []
    if por:
        c = [czas_pl(p['at']) for p in A['porazki'][:5]]
        lista = ', '.join((x[:5] + ' ' + x[-5:] if x != '—' else x) + (f' ({p["krok"]})' if p.get('krok') else '') for x, p in zip(c, A['porazki']))
        lista += f' i {len(por) - 5} wcześniejsze' if len(por) > 5 else ''
        okno = [r for r in zak[:PRZ_OKNO] if r.get('conclusion') == 'failure']   # v327 (KON-01): porażki wśród ostatnich zakończonych
        if z_rzedu >= 2 or (z_rzedu == 1 and len(okno) >= PRZ_OKNO_BLAD):
            seria = zak[:min(z_rzedu, 5)] if z_rzedu >= 2 else okno[:5]
            pages = all('GitHub Pages' in str(kroki.get(r.get('id')) or '') for r in seria)   # v219/v221: 5 najnowszych porażek serii (tylko one mają opis kroku)
            if z_rzedu >= 2:
                bledy.append(f'automat nie działa{" (publikacja GitHub Pages)" if pages else ""}: {pl_przebiegi(len(por))} w 24 h, ostatnie {z_rzedu} z rzędu — strona nie odświeża danych ({lista})')
            else:   # v327: bez „ostatnie 1 z rzędu”
                bledy.append(f'automat nie działa{" (publikacja GitHub Pages)" if pages else ""}: {pl_przebiegi(len(okno))} wśród {PRZ_OKNO} ostatnich, w tym ostatni — '
                             f'strona odświeża dane tylko z przerwami ({pl_przebiegi(len(por))} w 24 h: {lista})')
        elif z_rzedu == 1:
            uwagi.append(f'ostatni przebieg automatu nieudany ({lista}) — kolejny za ok. 10 min; dwa nieudane z rzędu = błąd'
                         + ('; wcześniejsze porażki z 24 h już naprawione' if len(por) > 1 else ''))   # v327 (KON-01)
        else:
            uwagi.append(f'{pl_przebiegi(len(por))} automatu w 24 h — już naprawione: od ostatniej porażki {pl_udane(udane_po)} z rzędu ({lista})')
    if len(ost) < 20:
        uwagi.append(f'tylko {len(ost)} przebiegów w 24 h (harmonogram co 10 min ≈ 144; GitHub bywa opóźniony)')
    # v232: przebieg w stanie waiting (zadanie „opublikuj” czeka na środowisko) trzyma grupę „pages” — żadna publikacja nie przejdzie;
    # wszystkie przebiegi z listy (także starsze niż doba), czas czekania od updated_at; zła data = bez zgadywania
    def czeka_min(r):
        try:
            t = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
            t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        except Exception:
            return None
        return int((now - t).total_seconds() // 60)
    cz = [(czeka_min(r), r) for r in runs if isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and r.get('status') == 'waiting']
    cz = sorted(((m, r) for m, r in cz if m is not None and m >= WAIT_UWAGA_MIN), key=lambda x: -x[0])
    if cz:
        m, r = cz[0]
        kiedy = czas_pl(r.get('run_started_at'))
        pd_ = (pend or {}).get(r.get('id'))
        if isinstance(pd_, list) and any(isinstance(p, dict) and p.get('reviewers') for p in pd_):   # v235: wymóg zatwierdzenia przez osobę
            uwagi.append(f'publikacja czeka od {m} min na zatwierdzenie przez osobę (przebieg z {kiedy}; wymóg w ustawieniach środowiska '
                         'github-pages) — zatwierdź w Actions („Review deployments”) albo usuń ten wymóg; zegar zapasowy takiego przebiegu nie anuluje')
        elif m >= WAIT_BLAD_MIN:
            bledy.append(f'publikacja zawieszona: przebieg z {kiedy} czeka od {m // 60} godz. {m % 60} min na wdrożenie strony (stan „waiting”), '
                         'a zegar zapasowy go nie anulował — strona bez nowych danych')
        else:
            uwagi.append(f'publikacja czeka od {m} min (przebieg z {kiedy}, stan „waiting”) — zegar zapasowy anuluje taki przebieg sam '
                         f'(po 15 min, przy najbliższym czuwaniu), jeśli środowisko publikacji nie wymaga zatwierdzenia; od {WAIT_BLAD_MIN // 60} godz. to błąd')
    return A, bledy, uwagi


# ---------------------------------------------------------------- v130: ETF krypto u źródła (pliki emitenta) ----------------------------------------------------------------
def _em_liczba(s):
    """'1,234.56' → 1234.56; '--', '', 'N/A', zero, ujemne, nieskończone → None (brak, nie zero)."""
    try:
        v = float(str(s).replace(',', '').strip())
    except ValueError:
        return None
    return v if 0 < v < float('inf') else None


def _em_skonczona(v):
    """Liczba skończona (bez bool, NaN, ∞) albo None."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def emitent_historia(raw):
    """Plik funduszu emitenta (Excel 2003 XML, bajty) → {data ISO: (NAV, liczba jednostek)} z arkusza „Historical”. Wiersze z „--”, pustą
    komórką albo złą datą pominięte; komórki z ss:Index (przerwa w wierszu) na właściwym miejscu. Wyjątek, gdy brak arkusza albo nagłówka."""
    ns = '{urn:schemas-microsoft-com:office:spreadsheet}'
    txt = raw.decode('utf-8-sig', 'replace') if isinstance(raw, bytes) else str(raw)
    txt = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', txt)   # gołe „&” w nazwach spółek (jak w zbieraczu)
    ws = next((w for w in ET.fromstring(txt).iter(ns + 'Worksheet') if w.get(ns + 'Name') == 'Historical'), None)
    if ws is None:
        raise ValueError('brak arkusza Historical')
    head, out = None, {}
    for row in ws.iter(ns + 'Row'):
        c = []
        for x in row.iter(ns + 'Cell'):
            ix = x.get(ns + 'Index')
            if ix and ix.isdigit():
                c += [''] * max(0, int(ix) - 1 - len(c))
            d = x.find(ns + 'Data')
            c.append(((d.text if d is not None else '') or '').strip())
        if head is None:
            if 'As Of' in c and 'NAV per Share' in c and 'Shares Outstanding' in c:
                head = (c.index('As Of'), c.index('NAV per Share'), c.index('Shares Outstanding'))
            continue
        try:
            d = dt.datetime.strptime(c[head[0]], '%b %d, %Y').date().isoformat()
        except (ValueError, IndexError):
            continue
        nav = _em_liczba(c[head[1]]) if len(c) > head[1] else None
        sh = _em_liczba(c[head[2]]) if len(c) > head[2] else None
        if nav and sh:
            out[d] = (nav, sh)
    if head is None:
        raise ValueError('arkusz Historical bez nagłówka As Of / NAV per Share / Shares Outstanding')
    return out


def emitent_sesje(etf, a):
    """Daty sesji z data/etf.json (assets[a].day = [[znacznik północy UTC, mln]]) — kalendarz do wykrycia braku wiersza w pliku emitenta."""
    out = set()
    A = ((etf.get('assets') if isinstance(etf, dict) else None) or {})
    A = A.get(a) if isinstance(A, dict) else None
    for r in ((A.get('day') if isinstance(A, dict) else None) or []):
        try:
            out.add(dt.datetime.fromtimestamp(r[0], dt.timezone.utc).date().isoformat())
        except (TypeError, ValueError, OverflowError, OSError, IndexError, KeyError):
            pass
    return out


def emitent_przeplywy(hist, sesje=()):
    """{data: (NAV, jednostki)} → ({dzień D: przepływ w mln USD}, {dzień D: powód pominięcia}); D = (S[D+1] − S[D]) × NAV[D] / 1e6, gdzie D+1
    to następny wiersz pliku. Wiersz identyczny z poprzednim (dzień wolny w USA) usunięty; ostatni wiersz bez przepływu (jeszcze go nie ma).
    Pominięty dzień, gdy następny wiersz jest dalej niż EM_PRZERWA dni albo między nimi jest sesja z `sesje` (brak wiersza w pliku), albo gdy
    NAV skacze o więcej niż EM_NAV_SKOK % (podział jednostek?)."""
    rows = sorted(hist.items())
    rows = rows[:1] + [b for a, b in zip(rows, rows[1:]) if b[1] != a[1]]
    ss = sorted(sesje)
    out, pom = {}, {}
    for (d, (nav, sh)), (n, (nav2, sh2)) in zip(rows, rows[1:]):
        if (dt.date.fromisoformat(n) - dt.date.fromisoformat(d)).days > EM_PRZERWA or any(d < s < n for s in ss):
            pom[d] = f'w pliku emitenta brak sesji po {d}'
        elif abs(nav2 / nav - 1) * 100 > EM_NAV_SKOK:
            pom[d] = 'skok NAV (podział jednostek?)'
        else:
            out[d] = (sh2 - sh) * nav / 1e6
    return out, pom


def emitent_zapis(path):
    """kontrola/etf-emitent.csv → {(data, symbol): [liczba ze strony | None, czas odczytu | None]}; pusta komórka = brak (nie zero).
    Inny nagłówek = zapis od nowa (bez mieszania kolumn)."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        if next(r, None) != EM_KOL:
            return rows
        for row in r:
            if len(row) < 4 or not row[1]:
                continue
            try:
                d = dt.date.fromisoformat(row[0]).isoformat()
                v = _em_skonczona(float(row[2])) if row[2] != '' else None
            except ValueError:
                continue
            rows[(d, row[1])] = [v, row[3] or None]
    return rows


def emitent_zapis_zapisz(path, rows):
    """Zapis ostatnich EM_DNI dat, rosnąco po dacie i symbolu; brak = pusta komórka."""
    daty = set(sorted({d for d, _ in rows})[-EM_DNI:])
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(EM_KOL)
        for d, t in sorted(k for k in rows if k[0] in daty):
            v, at = rows[(d, t)]
            w.writerow([d, t, (('%.6f' % (round(v, 6) + 0.0)).rstrip('0').rstrip('.') if v is not None else ''), at or ''])


def emitent_odczyt(rows, etf):
    """Dopisuje do zapisu przepływy funduszy EM_FUNDS pokazane na stronie (etf.json, `asof` aktywa). Ta sama data i symbol = nadpisanie
    (wygrywa najpóźniejszy odczyt), ale brak (None) nie kasuje liczby zapisanej wcześniej. Zwraca symbole, których nie ma na liście funduszy strony."""
    brak = []
    if not isinstance(etf, dict):
        return brak
    at = etf.get('at') if isinstance(etf.get('at'), str) else None
    assets = etf.get('assets') if isinstance(etf.get('assets'), dict) else {}
    for t, a, _ in EM_FUNDS:
        A = assets.get(a)
        if not isinstance(A, dict) or not isinstance(A.get('asof'), str):
            continue
        try:
            d = dt.date.fromisoformat(A['asof'][:10]).isoformat()
        except ValueError:
            continue
        funds = [f for f in (A.get('funds') if isinstance(A.get('funds'), list) else []) if isinstance(f, dict)]
        f = next((f for f in funds if f.get('t') == t), None)
        if f is None and funds:
            brak.append(t)
        v = _em_skonczona(f.get('d1')) if f else None
        old = rows.get((d, t))
        if v is not None or old is None or old[0] is None:
            rows[(d, t)] = [v, at]
    return brak


def emitent_porownanie(zap, przep, pom, plik_do, sesje=()):
    """zap: {data: [liczba ze strony | None, czas odczytu]} jednego funduszu; przep, pom: z emitent_przeplywy; plik_do: ostatni dzień pliku;
    sesje: kalendarz sesji strony (emitent_sesje). Okno = ostatnie EM_SESJE zapisanych dat sprzed plik_do (późniejsze czekają na następny wiersz
    pliku). Brak liczby na stronie albo dzień bez wyliczenia = pominięty z powodem (nigdy 0). Zaległość = sesje strony (kalendarz i zapis) nowsze
    niż plik_do; ponad EM_ZALEGLOSC = plik nieaktualny (np. stara kopia pliku z kodem 200) — wtedy okno to tylko stare sesje, a nowsze czekają.
    Status: ✅ zgodne; ⚠️ różnica ponad próg w oknie; ℹ️ jeszcze nic do porównania; ? są daty w oknie, ale żadnej nie da się porównać, albo plik
    nieaktualny (różnica ⚠️ ma pierwszeństwo). Tylko różnice i daty (bez liczb emitenta)."""
    okno = sorted(d for d in zap if d < plik_do)[-EM_SESJE:]
    daty, pomin, roz, maxr = [], [], [], None
    for d in okno:
        a = zap[d][0]
        if a is None:
            pomin.append({'data': d, 'powod': 'brak liczby na stronie'}); continue
        if d not in przep:
            pomin.append({'data': d, 'powod': pom.get(d, 'brak tej sesji w pliku emitenta')}); continue
        b = przep[d]; r = a - b
        daty.append(d); maxr = abs(r) if maxr is None else max(maxr, abs(r))
        if abs(r) > max(EM_TOL_MLN, EM_TOL_PCT / 100 * abs(b)):
            roz.append({'data': d, 'roznica_mln': round(r, 1) + 0.0, 'roznica_pct': (round(r / abs(b) * 100, 1) + 0.0) if b else None,
                        'strona_zero': a == 0})
    po = sorted({d for d in zap if d > plik_do} | {s for s in sesje if s > plik_do})   # sesje strony, których plik emitenta jeszcze nie ma
    stary = len(po) > EM_ZALEGLOSC
    st = ('⚠️' if roz else '✅') if daty else ('?' if pomin else 'ℹ️')
    if stary and st != '⚠️':
        st = '?'
    return {'status': st, 'porownane': len(daty), 'od': daty[0] if daty else None, 'do': daty[-1] if daty else None,
            'max_roznica_mln': (round(maxr, 2) + 0.0) if maxr is not None else None, 'roznice': roz, 'pominiete': pomin,
            'czeka': sorted(d for d in zap if d >= plik_do), 'plik_do': plik_do, 'zaleglosc': len(po), 'strona_do': po[-1] if po else None,
            'nieaktualny': stary}


def _em_roznica(x):
    return (f'{x["data"]}: {x["roznica_mln"]:+.1f} mln USD' + (f' ({x["roznica_pct"]:+.1f}%)' if x.get('roznica_pct') is not None else '')
            + (' — strona pokazywała 0.0 (możliwe opóźnienie publikacji funduszu)' if x.get('strona_zero') else ''))


def emitent_linia(t, F):
    """Fragment linii raportu dla jednego funduszu: status, porównane sesje, różnice i pominięte daty, a zawsze też ostatni dzień pliku emitenta,
    liczba nowszych sesji strony (zaległość pliku) i zapisane sesje czekające na porównanie. Brak = „—”; bez liczb emitenta."""
    if F.get('blad'):
        return f'{t} ? brak odczytu pliku ({F["blad"]})'
    st, pom, cz = F.get('status') or '?', F.get('pominiete') or [], F.get('czeka') or []
    if F.get('porownane'):
        mx = f'{F["max_roznica_mln"]:.1f} mln USD' if F.get('max_roznica_mln') is not None else '—'
        okr = F['od'] if F.get('od') == F.get('do') else f'{F["od"]} – {F["do"]}'
        s = (f'{t} {st} porównane sesje: {F["porownane"]} ({okr}), różnic ponad próg: {len(F["roznice"])}, największa różnica {mx}'
             + (' — ' + '; '.join(_em_roznica(x) for x in F['roznice'][-EM_SESJE:]) if F['roznice'] else ''))
        if pom:
            s += '; pominięte: ' + ', '.join(f'{x["data"]} ({x["powod"]})' for x in pom[-3:])
    elif pom:
        s = f'{t} {st} zapisane sesje bez porównania: ' + ', '.join(f'{x["data"]} ({x["powod"]})' for x in pom[-3:])
    else:
        s = f'{t} {st} jeszcze bez porównania'
    s += f'; plik emitenta do {F.get("plik_do") or "—"}, nowszych sesji na stronie: ' + (str(F['zaleglosc']) if F.get('zaleglosc') is not None else '—')
    if F.get('nieaktualny'):
        s += f' — plik nieaktualny (próg {EM_ZALEGLOSC}), te sesje bez porównania'
    return s + f'; czeka na porównanie: {len(cz)}' + (' (' + ('…, ' if len(cz) > 3 else '') + ', '.join(cz[-3:]) + ')' if cz else '')


def etf_emitent(files, R):
    """Krok 3e kontroli: zapis przepływów IBIT i ETHA ze strony, 2 zapytania o pliki emitenta (bez ponawiania), porównanie → słownik do
    R['zgodnosc']['etf_emitent']; uwagi dopisane do R['uwagi'] (nigdy do listy błędów)."""
    path = os.path.join(OUT_DIR, EM_CSV)
    zap = emitent_zapis(path)
    for t in emitent_odczyt(zap, files.get('etf')):
        R['uwagi'].append(f'ETF {t}: funduszu nie ma na liście funduszy strony (etf.json) — lista ucięta albo zmiana symbolu')
    try:
        emitent_zapis_zapisz(path, zap)
    except Exception as e:  # noqa
        R['uwagi'].append(f'{EM_CSV}: nie zapisano ({str(e)[:80]})')
    E = {'fundusze': {}, 'zapis_dni': len({d for d, _ in zap})}
    for i, (t, a, pid) in enumerate(EM_FUNDS):
        if i:
            time.sleep(EM_PAUZA)
        try:
            st, body, ms = get(EM_DOC.format(pid=pid), timeout=EM_TIMEOUT)
            hist = emitent_historia(body)
            if not hist:
                raise ValueError('arkusz Historical bez wierszy z liczbami')
        except urllib.error.HTTPError as e:
            F = {'status': '?', 'blad': f'HTTP {e.code}'}
        except Exception as e:  # noqa
            F = {'status': '?', 'blad': (str(e) or type(e).__name__)[:120]}
        else:
            ses = emitent_sesje(files.get('etf'), a)
            przep, pom = emitent_przeplywy(hist, ses)
            F = emitent_porownanie({d: v for (d, tt), v in zap.items() if tt == t}, przep, pom, max(hist), ses)
            F['ms'] = ms
        E['fundusze'][t] = F
        if F.get('blad'):
            R['uwagi'].append(f'ETF {t}: plik emitenta — brak odczytu ({F["blad"]}); porównanie przepływów pominięte')
            continue
        if F['status'] == '⚠️':
            R['uwagi'].append(f'ETF {t}: przepływ na stronie ≠ wyliczenie z pliku emitenta (próg max {EM_TOL_MLN:g} mln USD / {EM_TOL_PCT:g}%) — '
                              + '; '.join(_em_roznica(x) for x in F['roznice'][-3:]))
        elif F['pominiete'] and not F['porownane']:
            R['uwagi'].append(f'ETF {t}: zapisanych sesji nie da się porównać z plikiem emitenta — '
                              + ', '.join(f'{x["data"]} ({x["powod"]})' for x in F['pominiete'][-3:]))
        if F['nieaktualny']:   # stara kopia pliku (kod 200) nie może dawać wiecznego ✅ na starych sesjach
            R['uwagi'].append(f'ETF {t}: plik emitenta kończy się na {F["plik_do"]}, a strona ma już {F["zaleglosc"]} nowszych sesji (do {F["strona_do"]}) — '
                              f'plik nieaktualny (próg {EM_ZALEGLOSC}), te sesje bez porównania')
    sts = [F['status'] for F in E['fundusze'].values()]
    E['status'] = next((s for s in ('⚠️', '?', '✅') if s in sts), 'ℹ️')
    return E


# ---------------------------------------------------------------- v136: kursy dolara Ameryki Łacińskiej (data/dolar.json) ----------------------------------------------------------------
DL_ETYKIETA = 'kursy dolara Ameryki Łacińskiej (co godzinę)'
DL_PROG = 180              # min — wiek najnowszej części pliku (part_at.ar/ve/bo; automat co 55 min): po progu ⚠️, nigdy ❌ — osobny wiersz, lista SWIEZOSC bez zmian
# v286: próg blue 1,5% z testu wstecznego 2 lat (dwa niezależne zapisy dziennego kursu blue, dni robocze od 2025: > 0,5% w 5,9% dni, > 1,5% — 0,
# p99 1,15%, najwięcej 1,38%; od 2024: > 1,5% w 0,3% dni) — rynek nieformalny notowany krokami 5–10 peso, dwa serwisy różnią się często o jeden krok
DL_PARY = (('blue', 'blue', 1.5), ('mayorista', 'hurtowy', 0.5), ('oficial', 'oficjalny w banku', 0.5), ('bolsa', 'MEP', 2.0), ('contadoconliqui', 'CCL', 2.0))
DL_DUZA = {0.5: 1.5, 1.5: 3.0, 2.0: 4.0}   # % — ponad to różnica dwóch odczytów jest „duża” (dopisek przy ⚠️; nigdy ❌ ani BŁĄD)
DL_DNI = 3                 # dni — znaczniki dwóch odczytów dalej od siebie = „?” (bez oceny: porównanie różnych sesji)
DL_BCRA = 'https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD?fechadesde={a}&fechahasta={b}'   # bez klucza, dni robocze
DL_BCRA_PROG = 0.3         # % — kurs hurtowy z pliku vs kurs banku centralnego Argentyny z tego samego dnia (27.09: 1525,5 = 1525,5)
DL_LUKA_MAX = {'ar': 60.0, 've': 300.0}   # % — większa luka = możliwy błąd skali, który przeszedł przez zakres stosunku kursów (uwaga)
DL_LUKA_DNI = 4            # dni — najstarszy kurs głównej luki (AR: CCL i hurtowy, VE: równoległy i data kursu banku, BO: USDT i oficjalny) starszy = ⚠️
DL_KRAJE = (('ar', 'Argentyna'), ('ve', 'Wenezuela'), ('bo', 'Boliwia'))
DL_TZ_K = {'ar': -3, 've': -4, 'bo': -4}   # jak w zbieraczu: kurs „sama data” (północ UTC) liczony od końca tego dnia w kraju


def _dl_kurs(q):
    """Kurs z pliku: [kupno | None, sprzedaż > 0, znacznik, …]."""
    return isinstance(q, list) and len(q) >= 3 and isinstance(q[1], (int, float)) and not isinstance(q[1], bool) and q[1] > 0


def _dl_czas(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return t if t.tzinfo else None
    except (TypeError, ValueError):
        return None


def _dl_od(stamp, cc):
    """Chwila, od której liczymy wiek kursu (jak dl_qtime w zbieraczu): znacznik; „sama data” (północ UTC albo RRRR-MM-DD) — koniec tego dnia w kraju."""
    s = str(stamp or '')
    if len(s) == 10:
        s += 'T00:00:00Z'
    t = _dl_czas(s)
    if t is not None and t.utcoffset() == dt.timedelta(0) and (t.hour, t.minute, t.second, t.microsecond) == (0, 0, 0, 0):
        return t + dt.timedelta(days=1) - dt.timedelta(hours=DL_TZ_K[cc])
    return t


def dolar_luki(dl, now=None):
    """v136, przegląd: główne luki strony (AR: CCL wobec hurtowego, VE, BO) — ⚠️, gdy luki brak (strona pokazuje „—”) albo gdy najstarszy z jej
    kursów jest starszy niż DL_LUKA_DNI dni W CHWILI KONTROLI (wiek z dat samych kursów, nie z part_at — kraj z błędem ma stary part_at, ale też
    kraj bez błędu może mieć zatrzymane kursy). Tylko uwagi, nigdy ❌. → ({kraj: {'status', 'wiek_dni', 'uwaga'}}, [uwagi])"""
    now = now or NOW
    out, uw = {}, []
    for cc, nm in DL_KRAJE:
        P = dl.get(cc) if isinstance(dl, dict) and isinstance(dl.get(cc), dict) else {}
        q = P.get('q') if isinstance(P.get('q'), dict) else {}
        if cc == 'ar':
            g = (P.get('gap') or {}).get('contadoconliqui') if isinstance(P.get('gap'), dict) else None
            st = [x[2] for x in (q.get('contadoconliqui'), q.get('mayorista')) if _dl_kurs(x)]
            need = 2
        elif cc == 've':
            g = P.get('gap'); b = P.get('base') if isinstance(P.get('base'), list) and len(P.get('base')) >= 4 else None
            st = ([q['paralelo'][2]] if _dl_kurs(q.get('paralelo')) else []) + ([b[3]] if b and b[3] else [])
            need = 2
        else:
            g = P.get('gap')
            st = [x[2] for x in (q.get('usdt'), q.get('oficial')) if _dl_kurs(x)]
            need = 2
        ts = [_dl_od(x, cc) for x in st]
        dni = (now - min(ts)).total_seconds() / 86400 if ts and None not in ts else None
        wiek = round(dni, 1) if dni is not None else None
        num = isinstance(g, (int, float)) and not isinstance(g, bool)
        if not num:
            K = {'status': '⚠️', 'wiek_dni': wiek, 'uwaga': 'główna luka bez wartości (na stronie „—”)'}
        elif len(ts) < need or None in ts:
            K = {'status': '⚠️', 'wiek_dni': wiek, 'uwaga': 'brak daty któregoś kursu głównej luki'}
        elif dni > DL_LUKA_DNI:
            K = {'status': '⚠️', 'wiek_dni': wiek, 'uwaga': f'najstarszy kurs głównej luki sprzed {wiek:.1f} dni (próg {DL_LUKA_DNI})'}
        else:
            K = {'status': '✅', 'wiek_dni': wiek}
        out[cc] = K
        if K['status'] == '⚠️':
            uw.append(f'kursy dolara — {nm}: {K["uwaga"]}')
    return out, uw


def _dl_bcra_kurs(j, d):
    """Odpowiedź API banku centralnego Argentyny (Cotizaciones/USD) → kurs dnia d (RRRR-MM-DD) albo None."""
    for x in ((j.get('results') if isinstance(j, dict) else None) or []):
        if isinstance(x, dict) and x.get('fecha') == d:
            for y in x.get('detalle') or []:
                v = y.get('tipoCotizacion') if isinstance(y, dict) else None
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 and (y.get('codigoMoneda') or 'USD') == 'USD':
                    return float(v)
    return None


# ---------------------------------------------------------------- v162: dzienniki sygnałów TRENDÓW — ostatni dzień z wynikiem ----------------------------------------------------------------
# Plik dziennika jest przepisywany w każdym przebiegu (wiek pliku zawsze mały), więc pętla wieku plików nie widzi, że wyniki przestały dochodzić.
# Tu: najnowszy dzień (sesja) z liczbą w polu wyniku (wiersz [dzień, symbol, N, stan, głosy, czas, y]). Krypto: wynik doby D dochodzi ok. D+3
# 00:30 UTC (pliki dzienne archiwum cen; wynik potrzebuje otwarcia 06:00 doby D+2) — norma 2–3 dni od końca doby, próg 4 dni kalendarzowe.
# Świat: wynik sesji dochodzi tego samego wieczoru — próg 48 h roboczych (święto w USA się mieści). Najwyżej ⚠️, nigdy ❌ ani BŁĄD; przed
# startem dziennika (since) albo w pierwszych dniach bez wyniku — „—”; brak pliku albo plik bez wierszy — None (brak pliku zgłasza pętla wieku plików).
DZ_SPEC = (('krypto-dziennik', 'TRENDY krypto — ostatni dzień z wynikiem sygnałów', 'w', 4 * 24 * 60),
           ('swiat-dziennik', 'TRENDY świat — ostatnia sesja z wynikiem sygnałów', 'd', 48 * 60))
_DZ_DZIEN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def dziennik_swiezosc(j, plik, now=None):
    """v162: wiersz świeżości dziennika sygnałów (data/<plik>.json) w kształcie wierszy swiezosc(): (etykieta, status, wiek min, dzień, uwaga)
    albo None (inny plik, brak pliku, plik bez listy wierszy). Wynik = liczba skończona w polu y (bool, None, NaN — nie)."""
    spec = next((x for x in DZ_SPEC if x[0] == plik), None)
    if spec is None or not isinstance(j, dict) or not isinstance(j.get('rows'), list):
        return None
    _p, lab, kat, prog = spec
    now = now or NOW
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))  # noqa: E731
    dni = [r[0] for r in j['rows'] if isinstance(r, list) and len(r) == 7 and isinstance(r[0], str) and _DZ_DZIEN.match(r[0]) and num(r[6])]
    since = j.get('since') if isinstance(j.get('since'), str) and _DZ_DZIEN.match(j['since']) else None
    if not dni:
        if since and now.date().isoformat() <= since:
            return (lab, '—', None, None, f'dziennik rusza {since} — pierwsze wyniki po pierwszym sprawdzeniu')
        w0 = wiek_danych(since, 'day', kat, now) if since else None
        if w0 is not None and w0 <= prog:
            return (lab, '—', None, None, f'dziennik od {since} — czekamy na pierwsze wyniki')
        return (lab, '⚠️', w0, None, 'brak dnia z wynikiem w dzienniku' + (f' (od {since})' if since else '') + ' (tylko uwaga)')
    d = max(dni)
    w = wiek_danych(d, 'day', kat, now)
    if w is None:
        return (lab, '?', None, d, 'zły zapis dnia')
    if w <= prog:
        return (lab, '✅', w, d, '')
    return (lab, '⚠️', w, d, f'próg {fmt_wiek(prog)} — wyniki sygnałów przestały dochodzić (tylko uwaga)')


# v303: dziennik reguł „w cieniu” działu SUROWCE (data/surowce-dziennik.json; wiersz [dzień, linia, symbol, głos, stan, z, zapisano, y,
# dzień danych]) — ostatni dzień z wynikiem. Plik jest przepisywany w każdym przebiegu (wiek pliku zawsze mały), więc tu: najnowszy dzień
# z liczbą w polu wyniku. Wyniki dochodzą z linii krypto (złoto → bitcoin: doba karty ≈ dzień złota + 1, wynik po otwarciu 06:00 UTC doby + 2
# i pliku dziennym świec, ok. 3 doby później) i — od grudnia 2026 — z linii świata (sesja, ten sam wieczór). Próg 14 dni kalendarzowych:
# test wsteczny na kalendarzu sesji NYSE 2004–2026 (dni złota = sesje funduszu złota, z zamknięciami nadzwyczajnymi) z najgorszym
# opóźnieniem archiwum złota (dzień złota w plikach dopiero o 13:05 UTC następnego dnia roboczego) i kontrolą codziennie o 06:20 UTC
# (kontrola.yml): najwyższy wiek 7 dni 6 h (kontrola 06.01.2007: Nowy Rok i dzień żałoby po prezydencie Fordzie), fałszywych ⚠️ 0 z 8 285
# kontroli (surowce/projekt/test_wsteczny_su_dz.py i .out, 08.10.2026).
# Najwyżej ⚠️, nigdy ❌ ani BŁĄD; przed startem dziennika albo w pierwszych dniach bez wyniku — „—”.
SUT_DZ = ('surowce-dziennik', 'TRENDY surowce — ostatni dzień z wynikiem reguł w cieniu', 'w', 14 * 24 * 60)


def su_dziennik_swiezosc(j, now=None):
    """v303: wiersz świeżości dziennika reguł „w cieniu” SUROWCE w kształcie wierszy swiezosc(): (etykieta, status, wiek min, dzień, uwaga)
    albo None (brak pliku albo plik bez listy wierszy). Wynik = liczba skończona w polu y (indeks 7; bool, None, NaN — nie)."""
    if not isinstance(j, dict) or not isinstance(j.get('rows'), list):
        return None
    _p, lab, kat, prog = SUT_DZ
    now = now or NOW
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))  # noqa: E731
    dni = [r[0] for r in j['rows'] if isinstance(r, list) and len(r) == 9 and isinstance(r[0], str) and _DZ_DZIEN.match(r[0]) and num(r[7])]
    since = j.get('since') if isinstance(j.get('since'), str) and _DZ_DZIEN.match(j['since']) else None
    if not dni:
        if since and now.date().isoformat() <= since:
            return (lab, '—', None, None, f'dziennik rusza {since} — pierwsze wyniki po pierwszym sprawdzeniu')
        w0 = wiek_danych(since, 'day', kat, now) if since else None
        if w0 is not None and w0 <= prog:
            return (lab, '—', None, None, f'dziennik od {since} — czekamy na pierwsze wyniki')
        return (lab, '⚠️', w0, None, 'brak dnia z wynikiem w dzienniku' + (f' (od {since})' if since else '') + ' (tylko uwaga)')
    d = max(dni)
    w = wiek_danych(d, 'day', kat, now)
    if w is None:
        return (lab, '?', None, d, 'zły zapis dnia')
    if w <= prog:
        return (lab, '✅', w, d, '')
    return (lab, '⚠️', w, d, f'próg {fmt_wiek(prog)} — wyniki reguł w cieniu przestały dochodzić (tylko uwaga)')


# v309: TRENDY surowce — dane funduszy surowcowych w pliku data/swiat-dzien.json (wejścia linii su.cm.p i su.cm.f reguł „w cieniu” SUROWCE,
# rejestracja 08.10.2026): część px — otwarcia i zamknięcia 7 funduszy (sesja w USA, ta sama droga co 44 rynki), część fl — NAV i liczba
# jednostek 3 funduszy (zestawienie wydawcy co 2 h, przez plik fundusze). Plik jest przepisywany w każdym przebiegu (wiek pliku zawsze mały),
# więc tu: najnowszy dzień z liczbą w każdym funduszu; wiek NAJSTARSZEGO z nich (zalegający fundusz wymieniony w uwadze). Fundusz bez serii
# w pliku — „?” z nazwą (pierwsze pobranie po wdrożeniu albo awaria), bez progu. Dwa osobne wiersze (lista SWIEZOSC bez zmian), najwyżej ⚠️,
# nigdy ❌ ani BŁĄD (dane reguł w cieniu, nie liczby strony). Próg 60 h roboczych (kategoria 'd') — test wsteczny (ws53/v309-fundusze-su/bt309/
# bt_swiezosc_su.py i .out, 10.10.2026): sesje NYSE 2004 – 09.10.2026 z zamknięciami nadzwyczajnymi; dzień D w pliku: ceny — zaobserwowane
# 00:58–02:05 UTC D+1 (05–09.10.2026), model 03:05 UTC D+1 (zimą 04:05) i pesymistyczny 13:00 UTC D+1; NAV — zaobserwowane 00:02–12:03 UTC D+1,
# model 14:00 UTC D+1 (zawsze po kontroli 06:20); kontrola codziennie o 06:20 UTC (kontrola.yml) i — górna granica — co godzinę:
# fałszywych ⚠️ przy 60 h najwyżej 0,024% kontroli dziennych i 0,201% godzinnych (tylko dwudniowe zamknięcia giełdy 2007 i 2012 oraz poranki
# po święcie w modelu pesymistycznym); przy 48 h — do 2,15% / 1,26%, przy 36 h — do 2,55% / 7,17% (za dużo).
SUF_PROG = 60 * 60
SUF_CZ = (('px', 'TRENDY surowce — ceny 7 funduszy surowcowych (sesja w USA; reguły w cieniu)', ('GSG', 'CMDY', 'COMT', 'DBC', 'USO', 'CPER', 'DBA')),
          ('fl', 'TRENDY surowce — NAV i jednostki 3 funduszy surowcowych (reguły w cieniu)', ('GSG', 'CMDY', 'COMT')))


def su_fundusze_swiezosc(wd, now=None):
    """v309: wiersze świeżości danych funduszy surowcowych w pliku swiat-dzien (części px i fl) w kształcie wierszy swiezosc(): (etykieta,
    status, wiek min, dzień, uwaga); brak pliku — [] (brak pliku zgłasza pętla wieku plików). Najnowszy dzień funduszu = największa data
    wiersza z liczbą (px: zamknięcie; fl: NAV i liczba jednostek); status i wiek z najstarszego z tych dni (zalegający fundusz widać)."""
    if not isinstance(wd, dict):
        return []
    now = now or NOW
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 < v < float('inf')  # noqa: E731
    rows = []
    for cz, lab, syms in SUF_CZ:
        P = wd.get(cz) if isinstance(wd.get(cz), dict) else {}
        ost = {}
        for s in syms:
            e = P.get(s) if isinstance(P.get(s), dict) else {}
            ds = [r[0] for r in (e.get('d') if isinstance(e.get('d'), list) else []) if isinstance(r, list) and len(r) >= 3
                  and isinstance(r[0], str) and _DZ_DZIEN.match(r[0]) and num(r[2]) and (cz == 'px' or num(r[1]))]
            if ds:
                ost[s] = max(ds)
        brak = [s for s in syms if s not in ost]
        if not ost:
            rows.append((lab, '?', None, None, 'brak serii w pliku: ' + ', '.join(brak) + ' (pierwsze pobranie po wdrożeniu albo awaria — tylko uwaga)'))
            continue
        d = min(ost.values())
        w = wiek_danych(d, 'day', 'd', now)
        if w is None:
            rows.append((lab, '?', None, d, 'zły zapis dnia')); continue
        st, u = ('⚠️' if w > SUF_PROG else '✅'), []
        if st == '⚠️':
            u.append(f'próg {fmt_wiek(SUF_PROG)} (godziny robocze) — dane przestały dochodzić: ' + ', '.join(sorted(s for s, x in ost.items() if x == d))
                     + ' (tylko uwaga)')
        if brak:
            u.append('brak serii w pliku: ' + ', '.join(brak))
            st = '⚠️' if st == '⚠️' else '?'
        rows.append((lab, st, w, d, '; '.join(u)))
    return rows


# v373: nowe grupy w TRENDACH — dziennik reguł „w cieniu” TD_SH_NG (data/ng-dziennik.json; wiersz [dzień, linia, symbol, głos, stan, z, zapisano, y,
# dzień danych], rejestracja 14.10.2026) i ceny 14 dodatkowych funduszy wyników (data/ng-ceny.json). Oba pliki są przepisywane w każdym przebiegu (wiek pliku
# zawsze mały), więc tu: najnowszy dzień z wynikiem w dzienniku i najnowszy dzień z ceną w każdym z funduszy. Wynik sesji pojawia się wieczorem tej samej sesji
# (tak jak cena funduszu w pliku świat dziennie), więc próg i kategoria jak w v309 (ceny funduszy surowcowych): 60 godzin roboczych, kategoria 'd' — test wsteczny
# v309 (sesje NYSE 2004–2026 z zamknięciami nadzwyczajnymi; ceny zaobserwowane 00:58–02:05 UTC D+1, model pesymistyczny 13:00 UTC D+1; kontrola codziennie o 06:20 UTC
# i — górna granica — co godzinę): fałszywych ⚠️ najwyżej 0,024% kontroli dziennych i 0,201% godzinnych. Najwyżej ⚠️, nigdy ❌ ani BŁĄD; przed startem
# dziennika albo w pierwszych dniach bez wyniku — „—”. Dziennik bez żadnego wyniku po 14 dniach od startu — ⚠️ (linie bez cen funduszy nie dają wyników).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'ng-dziennik')   # v373: dziennik reguł „w cieniu” nowych grup — przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['ng-dziennik'] = 180
PLIKI.insert(PLIKI.index('krypto-dzien'), 'ng-ceny')   # v373: ceny 14 dodatkowych funduszy wyników
LIMIT_MIN['ng-ceny'] = 180
NGK_PROG = 60 * 60              # min = 60 godzin roboczych (kategoria 'd')
NGK_START_DNI = 14              # dziennik bez wyniku dłużej niż tyle dni od startu — uwaga
NGK_PX = ('EPOL', 'EWW', 'ECH', 'UAE', 'QAT', 'KWT', 'EWS', 'EIDO', 'THD', 'EWM', 'EPHE', 'XLB', 'XLRE', 'XLC')   # = WD_NG_PX w zbieraj_dane.py (test pilnuje zgodności)
NGK_DZ = ('ng-dziennik', 'TRENDY nowe grupy — ostatni dzień z wynikiem reguł w cieniu')
NGK_CZ = ('TRENDY nowe grupy — ceny 14 funduszy wyników (sesja w USA; reguły w cieniu)', NGK_PX)


def ng_dziennik_swiezosc(j, now=None):
    """v373: wiersz świeżości dziennika reguł „w cieniu” nowych grup w kształcie wierszy swiezosc(): (etykieta, status, wiek min, dzień, uwaga) albo None
    (brak pliku albo plik bez listy wierszy). Wynik = liczba skończona w polu y (indeks 7; bool, None, NaN — nie)."""
    if not isinstance(j, dict) or not isinstance(j.get('rows'), list):
        return None
    lab = NGK_DZ[1]
    now = now or NOW
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))  # noqa: E731
    dni = [r[0] for r in j['rows'] if isinstance(r, list) and len(r) == 9 and isinstance(r[0], str) and _DZ_DZIEN.match(r[0]) and num(r[7])]
    since = j.get('since') if isinstance(j.get('since'), str) and _DZ_DZIEN.match(j['since']) else None
    if not dni:
        if since and now.date().isoformat() <= since:
            return (lab, '—', None, None, f'dziennik rusza {since} — pierwsze wyniki po pierwszym sprawdzeniu')
        okres = (now.date() - dt.date.fromisoformat(since)).days if since else None
        if okres is not None and okres <= NGK_START_DNI:
            return (lab, '—', None, None, f'dziennik od {since} — czekamy na pierwsze wyniki')
        return (lab, '⚠️', None, None, 'brak dnia z wynikiem w dzienniku' + (f' (od {since})' if since else '') + ' (tylko uwaga)')
    d = max(dni)
    w = wiek_danych(d, 'day', 'd', now)
    if w is None:
        return (lab, '?', None, d, 'zły zapis dnia')
    if w <= NGK_PROG:
        return (lab, '✅', w, d, '')
    return (lab, '⚠️', w, d, f'próg {fmt_wiek(NGK_PROG)} (godziny robocze) — wyniki reguł w cieniu przestały dochodzić (tylko uwaga)')


def ng_ceny_swiezosc(nc, now=None):
    """v373: wiersz świeżości cen 14 funduszy wyników w pliku ng-ceny w kształcie wierszy swiezosc(); brak pliku — [] (brak pliku zgłasza pętla wieku plików).
    Najnowszy dzień funduszu = największa data wiersza z liczbą (zamknięcie); status i wiek z najstarszego z tych dni (zalegający fundusz wymieniony w uwadze);
    fundusz bez serii — „?” z nazwą (pierwsze pobranie po wdrożeniu albo awaria), bez progu."""
    if not isinstance(nc, dict):
        return []
    lab, syms = NGK_CZ
    now = now or NOW
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and 0 < v < float('inf')  # noqa: E731
    P = nc.get('px') if isinstance(nc.get('px'), dict) else {}
    ost = {}
    for s in syms:
        e = P.get(s) if isinstance(P.get(s), dict) else {}
        ds = [r[0] for r in (e.get('d') if isinstance(e.get('d'), list) else []) if isinstance(r, list) and len(r) >= 3 and isinstance(r[0], str)
              and _DZ_DZIEN.match(r[0]) and num(r[2])]
        if ds:
            ost[s] = max(ds)
    brak = [s for s in syms if s not in ost]
    if not ost:
        return [(lab, '?', None, None, 'brak serii w pliku: ' + ', '.join(brak) + ' (pierwsze pobranie po wdrożeniu albo awaria — tylko uwaga)')]
    d = min(ost.values())
    w = wiek_danych(d, 'day', 'd', now)
    if w is None:
        return [(lab, '?', None, d, 'zły zapis dnia')]
    st, u = ('⚠️' if w > NGK_PROG else '✅'), []
    if st == '⚠️':
        u.append(f'próg {fmt_wiek(NGK_PROG)} (godziny robocze) — dane przestały dochodzić: ' + ', '.join(sorted(s for s, x in ost.items() if x == d)) + ' (tylko uwaga)')
    if brak:
        u.append('brak serii w pliku: ' + ', '.join(brak))
        st = '⚠️' if st == '⚠️' else '?'
    return [(lab, st, w, d, '; '.join(u))]


def dolar_swiezosc(j, now=None):
    """Wiersz świeżości kursów dolara (data/dolar.json → najnowsza z part_at.ar/ve/bo) w kształcie wierszy swiezosc(): (etykieta, status, wiek min,
    data, uwaga); brak pliku = None (brak pliku zgłasza pętla wieku plików). Najwyżej ⚠️ — nieoficjalny serwis kursów to nie awaria strony."""
    if not isinstance(j, dict):
        return None
    pa = j.get('part_at') if isinstance(j.get('part_at'), dict) else {}
    v = max((pa[k] for k in ('ar', 've', 'bo') if isinstance(pa.get(k), str)), default=None)
    if not v:
        return (DL_ETYKIETA, '?', None, None, 'brak czasu części w pliku')
    w = wiek_danych(v, 'ts', 'h', now)
    if w is None:
        return (DL_ETYKIETA, '?', None, v, 'zły zapis czasu części')
    st = '✅' if w <= DL_PROG else '⚠️'
    note = '' if st == '✅' else f'próg {fmt_wiek(DL_PROG)}' + (', ponad 2× progu — tylko uwaga' if w > 2 * DL_PROG else '')
    return (DL_ETYKIETA, st, w, v, note)


def dolar_porownanie(dl, bcra=None, now=None):
    """v136: Argentyna — dwa odczyty tych samych kursów z pliku dolar.json (ar.q vs ar.amb, sprzedaż) i kurs hurtowy vs kurs banku centralnego
    z tego samego dnia w Argentynie (UTC−3; bcra = odpowiedź API banku albo None) → {'status', 'pary', 'bcra', 'uwagi', 'opis'}. Para: ✅ w progu,
    ⚠️ ponad próg (nigdy ❌), „?” = brak któregoś odczytu albo znaczniki dalej niż DL_DNI dni. Do raportu tylko różnice w % i daty (bez kursów)."""
    out = {'status': '?', 'pary': [], 'bcra': None, 'uwagi': [], 'opis': ''}
    A = dl.get('ar') if isinstance(dl, dict) and isinstance(dl.get('ar'), dict) else {}
    q = A.get('q') if isinstance(A.get('q'), dict) else {}
    amb = A.get('amb') if isinstance(A.get('amb'), dict) else {}
    txt = []
    for k, nm, prog in DL_PARY:
        a, b = q.get(k), amb.get(k)
        P = {'kurs': nm, 'status': '?', 'roznica_pct': None, 'prog': prog}
        ta, tb = (_dl_czas(a[2]) if _dl_kurs(a) else None), (_dl_czas(b[2]) if _dl_kurs(b) else None)
        if ta is None or tb is None:
            P['uwaga'] = 'brak odczytu'
        elif abs(ta - tb) > dt.timedelta(days=DL_DNI):
            P['uwaga'] = f'odczyty dalej niż {DL_DNI} dni od siebie'
        else:   # v267 (przegląd v266): bez odstępu ze znaczników — drugie źródło podaje najpewniej czas Buenos Aires oznaczony jako UTC (ok. 3 h)
            r = abs(a[1] - b[1]) / b[1] * 100
            P['roznica_pct'] = round(r, 2) + 0.0
            P['status'] = '✅' if r <= prog else '⚠️'
            if r > prog:
                out['uwagi'].append(f'Argentyna, kurs {nm}: dwa odczyty różnią się o {r:.2f}% (próg {prog:g}%'
                                    + (f'; ponad {DL_DUZA[prog]:g}% — duża różnica' if r > DL_DUZA[prog] else '') + ')')
        out['pary'].append(P)
        txt.append(f'{nm} {P["status"]} ' + (f'{P["roznica_pct"]:.2f}%' if P['roznica_pct'] is not None else f'({P["uwaga"]})'))
    m = q.get('mayorista')
    B = {'status': '?', 'data': None, 'roznica_pct': None}
    t = _dl_czas(m[2]) if _dl_kurs(m) else None
    if t is None:
        B['uwaga'] = 'brak kursu hurtowego w pliku'
    else:
        B['data'] = (t - dt.timedelta(hours=3)).date().isoformat()
        v = _dl_bcra_kurs(bcra, B['data'])
        if v is None:
            B['uwaga'] = 'brak tego dnia w odpowiedzi banku' if isinstance(bcra, dict) else 'brak odczytu banku'
        else:
            r = abs(m[1] - v) / v * 100
            B['roznica_pct'] = round(r, 2) + 0.0; B['status'] = '✅' if r <= DL_BCRA_PROG else '⚠️'
            if r > DL_BCRA_PROG:
                out['uwagi'].append(f'Argentyna {B["data"]}: kurs hurtowy w pliku ≠ kurs banku centralnego o {r:.2f}% (próg {DL_BCRA_PROG:g}%)')
    out['bcra'] = B
    txt_b = f'hurtowy vs bank centralny ({B["data"] or "—"}) {B["status"]} ' + (f'{B["roznica_pct"]:.2f}%' if B['roznica_pct'] is not None else f'({B["uwaga"]})')
    gaps = {('ar', k): v for k, v in (A.get('gap') or {}).items()} if isinstance(A.get('gap'), dict) else {}
    V = dl.get('ve') if isinstance(dl, dict) and isinstance(dl.get('ve'), dict) else {}
    gaps[('ve', 'paralelo')] = V.get('gap')
    for (cc, k), g in gaps.items():
        if isinstance(g, (int, float)) and not isinstance(g, bool) and g > DL_LUKA_MAX[cc]:
            out['uwagi'].append(f'kursy dolara: luka {cc.upper()} {k} {g:+.1f}% ponad {DL_LUKA_MAX[cc]:g}% — możliwy błąd skali kursu')
    if isinstance(dl, dict):   # główne luki strony: brak albo stare kursy (wiek z dat kursów) = ⚠️
        out['luki'], uw = dolar_luki(dl, now)
        out['uwagi'] += uw
        txt_b += '; główne luki: ' + ', '.join(f'{cc.upper()} {K["status"]}' + (f' ({K["uwaga"]})' if K.get('uwaga') else '') for cc, K in out['luki'].items())
    sts = [P['status'] for P in out['pary']] + [B['status']]
    out['status'] = '⚠️' if '⚠️' in sts or out['uwagi'] else ('✅' if '✅' in sts else '?')
    out['opis'] = ', '.join(txt) + '; ' + txt_b
    return out


def dolar_kontrola(dl, R):
    """Krok 3f kontroli: 1 zapytanie do API banku centralnego Argentyny (10 dni do dnia kursu hurtowego; tylko gdy plik ma ten kurs z datą)
    i porównanie dolar_porownanie; uwagi dopisane do R['uwagi'] (nigdy do listy błędów). Brak pliku = None."""
    if not isinstance(dl, dict):
        return None
    A = dl.get('ar') if isinstance(dl.get('ar'), dict) else {}
    m = (A.get('q') or {}).get('mayorista') if isinstance(A.get('q'), dict) else None
    t = _dl_czas(m[2]) if _dl_kurs(m) else None
    bcra = None
    if t is not None:
        d = (t - dt.timedelta(hours=3)).date()
        try:
            bcra = get_json(DL_BCRA.format(a=(d - dt.timedelta(days=10)).isoformat(), b=d.isoformat()))
        except Exception as e:  # noqa
            R['uwagi'].append(f'kurs hurtowy Argentyny vs bank centralny: brak odczytu ({str(e)[:80]})')
    Z = dolar_porownanie(dl, bcra)
    R['uwagi'].extend(Z['uwagi'])
    return Z


# ---------------------------------------------------------------- v134: fundusze USA (data/ici.json) ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem tabeli (lista SWIEZOSC bez zmian — test liczy jej wiersze) i tożsamości sum ostatniego tygodnia
# w opublikowanym pliku. Wszystko najwyżej ⚠️ (uwaga), nigdy ❌ ani BŁĄD: tygodniowe dane wydawcy spóźniają się przez święta w USA, a zbieracz
# i tak odrzuca pliki z niezgodnymi sumami — niezgodność w pliku strony to sygnał do sprawdzenia, nie awaria strony.
ICI_ETYKIETA = {'lt': 'Fundusze USA: napływy (tydzień do środy, publ. w środę)'}
ICI_KROTKO = {'lt': 'napływy'}
# progi wieku danych (od końca dnia tygodnia danych): napływy w dniu publikacji mają już 7 dni, tuż przed następną 14 dni + ok. 14 h;
# 16 dni = 1,5 doby zapasu na przesunięcie publikacji (święto w USA) i godzinne okno zbieracza
ICI_PROG = {'lt': 16 * 24 * 60}
ICI_TOL = (3, 5)     # mln USD: tolerancja zaokrągleń (składniki grupy, suma grup) — jak w zbieraczu
ICI_SUMY = {'lt': (('eq', ('dom', 'wld'), 0), ('bd', ('tax', 'muni'), 0), ('total', ('eq', 'hyb', 'bd', 'com'), 1))}
ICI_OPIS = {'lt': 'akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup'}
# v135: rynek pieniężny (część „mm” pliku ici.json; publikacja w czwartek za tydzień do środy): w dniu publikacji dane mają 1 dzień, tuż przed
# następną — 7 dni i ok. 20 h; próg 10 dni = ok. 2 doby zapasu na przesunięcie publikacji (czwartki świąteczne w USA: Święto Dziękczynienia,
# Wigilia, Sylwester) i godzinne okno zbieracza. Najwyżej ⚠️, nigdy ❌ — jak napływy.
ICI_ETYKIETA['mm'] = 'Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek)'
ICI_KROTKO['mm'] = 'rynek pieniężny'
ICI_PROG['mm'] = 10 * 24 * 60
ICI_SUMY['mm'] = (('tot', ('gov', 'prime', 'te'), 0), ('tot', ('inst', 'ret'), 0), ('inst', ('gov_i', 'prime_i', 'te_i'), 0), ('ret', ('gov_r', 'prime_r', 'te_r'), 0))
ICI_OPIS['mm'] = 'razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie)'


def ici_swiezosc(j, now=None):
    """Wiersze świeżości części pliku ici.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, tydzień, uwaga). Najwyżej ⚠️
    (próg ICI_PROG), nigdy ❌; brak pliku = brak wierszy (brak pliku zgłasza pętla wieku plików); brak tygodnia części = „?”."""
    if not isinstance(j, dict):
        return []
    rows = []
    for k, label in ICI_ETYKIETA.items():
        P = j.get(k) if isinstance(j.get(k), dict) else {}
        w = P.get('week')
        if not (isinstance(w, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', w)):
            rows.append((label, '?', None, None, 'brak tygodnia w pliku')); continue
        wiek, prog = wiek_danych(w, 'day', 'w', now), ICI_PROG[k]
        st = '?' if wiek is None else ('⚠️' if wiek > prog else '✅')
        note = '' if st == '✅' else (f'próg {fmt_wiek(prog)} (tydzień danych + publikacja + święta w USA) — najwyżej uwaga' if st == '⚠️' else 'zła data tygodnia')
        rows.append((label, st, wiek, w, note))
    return rows


def ici_sumy(j):
    """Tożsamości sum w ostatnim tygodniu każdej części (ten sam wzór co zbieracz) i zgodność sumy 4 tygodni z wierszami pliku.
    → {część: {'tydzien', 'status' ✅/⚠️/?, 'opis'}}; brak liczby nie jest niezgodnością (sprawdzamy tylko pary z liczbami)."""
    out = {}
    for k, reguly in ICI_SUMY.items():
        P = j.get(k) if isinstance(j, dict) and isinstance(j.get(k), dict) else None
        cols, w = (P or {}).get('cols'), (P or {}).get('w')
        if not (isinstance(cols, list) and isinstance(w, list) and w and isinstance(w[-1], list) and len(w[-1]) == len(cols) + 1):
            out[k] = {'tydzien': None, 'status': '?', 'opis': 'brak wierszy w pliku'}; continue
        r = dict(zip(cols, w[-1][1:]))
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731
        zle = []
        for cel, czesci, t in reguly:
            if num(r.get(cel)) and all(num(r.get(c)) for c in czesci) and abs(r[cel] - sum(r[c] for c in czesci)) > ICI_TOL[t]:
                zle.append(f'{cel} {r[cel]:,.0f} ≠ {" + ".join(czesci)} {sum(r[c] for c in czesci):,.0f}'.replace(',', ' '))
        s4 = P.get('sum4')
        if isinstance(s4, dict) and isinstance(s4.get('v'), list) and len(w) >= 4 and s4.get('to') == w[-1][0]:
            for i, c in enumerate(cols):
                vals = [x[i + 1] if isinstance(x, list) and len(x) > i + 1 else None for x in w[-4:]]
                if i < len(s4['v']) and num(s4['v'][i]) and all(num(v) for v in vals) and abs(s4['v'][i] - sum(vals)) > 0.5:
                    zle.append(f'suma 4 tyg. {c}'); break
        out[k] = {'tydzien': w[-1][0], 'status': '⚠️' if zle else '✅', 'opis': '; '.join(zle) if zle else ICI_OPIS.get(k, 'sumy grup')}
    return out


def ici_kontrola(j, R):
    """Kontrola pliku ici.json bez sieci: tożsamości sum (⚠️ = uwaga) i informacja o dużej poprawce danych przez wydawcę (rev — bez koloru,
    tylko w raporcie). Brak pliku = None (raport bez linii)."""
    if not isinstance(j, dict):
        return None
    S = ici_sumy(j)
    for k, s in S.items():
        if s['status'] == '⚠️':
            R['uwagi'].append(f'{ICI_ETYKIETA.get(k, k)}: sumy w pliku strony niezgodne w tygodniu {s["tydzien"]} ({s["opis"]})')
    rev = []
    for k in ICI_ETYKIETA:
        r = (j.get(k) or {}).get('rev') if isinstance(j.get(k), dict) else None
        if isinstance(r, dict) and all(isinstance(r.get(x), (int, float)) for x in ('old', 'new')):
            rev.append(f'{ICI_KROTKO.get(k, k)}: wydawca poprawił tydzień {r.get("week")}: {r["old"]:,.0f} → {r["new"]:,.0f} mln USD'.replace(',', ' '))
    return {'sumy': S, 'rev': rev}


# ---------------------------------------------------------------- v137: Japonia — kto handluje akcjami na giełdzie (data/jpx.json) ----------------------------------------------------------------
JPX_ETYKIETA = 'Japonia: kto handluje akcjami na giełdzie (tydzień)'
JPX_ZWLOKA_H = 26          # h po spodziewanej publikacji następnego tygodnia (06:30 UTC) bez nowego tygodnia w pliku = ⚠️ (nigdy ❌ ani BŁĄD)
JPX_PARY = 26              # tyle ostatnich par tygodni porównujemy z danymi tygodniowymi MOF (plik instytucje trzyma 26 tygodni)
JPX_MIN_N = 8              # mniej par = „?” (za mało do oceny)
JPX_R_MIN = 0.6            # korelacja netto zagranicy (giełda vs MOF) poniżej progu = ⚠️; stan 27.09.2026: 0,909 z 26 par, kierunek 34 z 36 tygodni 2026
JPX_DUZE = 300.0           # mld JPY — w ostatnich 4 parach oba |netto| ≥ próg i przeciwne znaki = ⚠️
JPX_ZNAK = 50.0            # mld JPY — zgodność znaków liczona dla par, w których oba |netto| ≥ próg
JPX_KOREKTA_DNI = 7        # informacja o korekcie danych źródła z pliku jpx.json — uwaga w raporcie przez 7 dni
# dni bez sesji w Tokio poza weekendem — ta sama tabela co JPX_SWIETA w zbieraj_dane.py (test pilnuje zgodności); 31.12 i 1–3.01 — reguła.
# Po JPX_SWIETA_DO święta nie są znane: spodziewana publikacja wychodzi za wcześnie i świeżość może pokazać fałszywe ⚠️ (Złoty Tydzień: ok. 4 dni)
# — dlatego od 1 grudnia ostatniego roku tabeli raport ma uwagę „dopisać święta”.
JPX_SWIETA = frozenset((
    '2026-01-12', '2026-02-11', '2026-02-23', '2026-03-20', '2026-04-29', '2026-05-04', '2026-05-05', '2026-05-06', '2026-07-20',
    '2026-08-11', '2026-09-21', '2026-09-22', '2026-09-23', '2026-10-12', '2026-11-03', '2026-11-23',
    '2027-01-11', '2027-02-11', '2027-02-23', '2027-03-22', '2027-04-29', '2027-05-03', '2027-05-04', '2027-05-05', '2027-07-19',
    '2027-08-11', '2027-09-20', '2027-09-23', '2027-10-11', '2027-11-03', '2027-11-23',
    '2028-01-10', '2028-02-11', '2028-02-23', '2028-03-20', '2028-05-03', '2028-05-04', '2028-05-05', '2028-07-17', '2028-08-11',
    '2028-09-18', '2028-09-22', '2028-10-09', '2028-11-03', '2028-11-23',
    '2029-01-08', '2029-02-12', '2029-02-23', '2029-03-20', '2029-04-30', '2029-05-03', '2029-05-04', '2029-07-16', '2029-09-17',
    '2029-09-24', '2029-10-08', '2029-11-23',
    '2030-01-14', '2030-02-11', '2030-03-20', '2030-04-29', '2030-05-03', '2030-05-06', '2030-07-15', '2030-08-12', '2030-09-16',
    '2030-09-23', '2030-10-14', '2030-11-04'))
JPX_SWIETA_DO = 2030       # ostatni rok tabeli świąt


def jpx_swieta_uwaga(now=None):
    """Uwaga od 1 grudnia ostatniego roku tabeli świąt (i później): bez nowego roku kalendarz publikacji liczy święta jak dni sesji."""
    now = now or NOW
    if now.date() >= dt.date(JPX_SWIETA_DO, 12, 1):
        return (f'Japonia — tabela świąt giełdy w Tokio (JPX_SWIETA w zbieraj_dane.py i narzedzia/kontrola.py) kończy się na {JPX_SWIETA_DO} r. — '
                'dopisać kolejny rok, inaczej kalendarz publikacji liczy święta jak dni sesji (fałszywe ⚠️ świeżości)')
    return None


def jpx_bday(d):
    return d.weekday() < 5 and d.isoformat() not in JPX_SWIETA and not ((d.month == 12 and d.day == 31) or (d.month == 1 and d.day <= 3))


def jpx_release(day):
    """Publikacja danych tygodnia zawierającego `day`: 4. dzień roboczy od poniedziałku następnego tygodnia (jak w zbieraczu)."""
    d, n = day - dt.timedelta(days=day.weekday()) + dt.timedelta(days=7), 0
    for _ in range(40):
        if jpx_bday(d):
            n += 1
            if n == 4:
                return d
        d += dt.timedelta(days=1)
    return d


def jpx_next_release(asof):
    """Spodziewana publikacja następnego tygodnia z sesjami po tygodniu kończącym się `asof`."""
    m = asof - dt.timedelta(days=asof.weekday()) + dt.timedelta(days=7)
    for k in range(6):
        w0 = m + dt.timedelta(days=7 * k)
        if any(jpx_bday(w0 + dt.timedelta(days=i)) for i in range(5)):
            return jpx_release(w0)
    return jpx_release(m)


def jpx_swiezosc(j, now=None):
    """Wiersz świeżości (etykieta, status, wiek min, data, uwaga) wg kalendarza publikacji: ⚠️ dopiero JPX_ZWLOKA_H h po spodziewanej publikacji
    następnego tygodnia (4. dzień roboczy, ok. 06:30 UTC; święta w Japonii przesuwają termin); nigdy ❌. Brak pliku = ⚠️ „brak danych”
    (zbieracz bez poprzedniego pliku i bez danych nie zapisuje pliku — notatka w META, nie błąd)."""
    if not isinstance(j, dict):
        return (JPX_ETYKIETA, '⚠️', None, None, 'brak pliku data/jpx.json — brak danych, blok na stronie ukryty (tylko uwaga)')
    a = str(j.get('asof') or '')
    try:
        d = dt.date.fromisoformat(a[:10])
    except ValueError:
        return (JPX_ETYKIETA, '?', None, None, 'brak daty danych w pliku')
    now = now or NOW
    w = wiek_danych(a, 'day', 'w', now)
    nx = jpx_next_release(d)
    pub = dt.datetime(nx.year, nx.month, nx.day, 6, 30, tzinfo=dt.timezone.utc)
    if now <= pub + dt.timedelta(hours=JPX_ZWLOKA_H):
        return (JPX_ETYKIETA, '✅', w, a, '')
    late = int((now - pub).total_seconds() // 60)
    return (JPX_ETYKIETA, '⚠️', w, a, f'następny tydzień spodziewany {nx.isoformat()} ok. 06:30 UTC, brak od {fmt_wiek(late)} (kalendarz świąt w Japonii) — tylko uwaga')


def jpx_mof_porownanie(inst, jx):
    """Zagranica w japońskich akcjach: giełda (data/jpx.json, tylko handel na giełdzie, pon–pt) vs MOF (instytucje.json → mof, wszystkie akcje
    i fundusze, także poza giełdą, nd–sob). Para tygodni: sobota MOF = koniec tygodnia giełdy + (5 − dzień tygodnia). Netto w mld JPY: giełda
    (for_b − for_s) / 1000, MOF liabilities.equity_net / 10. Ostatnie ≤ JPX_PARY par: korelacja Pearsona, zgodność znaków (oba |netto| ≥ JPX_ZNAK),
    ostatnia para. ✅: n ≥ JPX_MIN_N, r ≥ JPX_R_MIN i w ostatnich 4 parach żadnej dużej (oba ≥ JPX_DUZE) z przeciwnym znakiem; „?”: n < JPX_MIN_N;
    inaczej ⚠️. Nigdy ❌ — to różne miary, a różnica to nie awaria strony."""
    Z = {'status': '?', 'n': 0, 'r': None, 'znak': None, 'ostatnia': None, 'opis': '', 'uwagi': []}
    if not isinstance(jx, dict):
        return None
    cols = jx.get('cols') if isinstance(jx.get('cols'), list) else []
    if not all(c in cols for c in ('to', 'for_s', 'for_b')):
        Z['opis'] = '? plik giełdy bez kolumn'; return Z
    i_t, i_s, i_b = cols.index('to'), cols.index('for_s'), cols.index('for_b')
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v   # noqa: E731
    G = {}
    for r in jx.get('d') or []:
        try:
            t = dt.date.fromisoformat(str(r[i_t])[:10])
        except (TypeError, ValueError, IndexError):
            continue
        if num(r[i_s]) and num(r[i_b]):
            G[(t + dt.timedelta(days=5 - t.weekday())).isoformat()] = (str(r[i_t]), (r[i_b] - r[i_s]) / 1000)
    M = {}
    mof = ((inst or {}).get('mof') or {}).get('d') if isinstance(inst, dict) else None
    for w in mof or []:
        v = ((w or {}).get('liabilities') or {}).get('equity_net') if isinstance(w, dict) else None
        if isinstance(w, dict) and num(v) and isinstance(w.get('to'), str):
            M[w['to'][:10]] = v / 10
    pary = [(G[k][0], G[k][1], M[k]) for k in sorted(set(G) & set(M))][-JPX_PARY:]
    Z['n'] = n = len(pary)
    if pary:
        Z['ostatnia'] = {'tydzien': pary[-1][0], 'gielda_mld': round(pary[-1][1], 1), 'mof_mld': round(pary[-1][2], 1)}
    if n < JPX_MIN_N:
        Z['opis'] = f'? za mało wspólnych tygodni ({n}, potrzeba {JPX_MIN_N})'; return Z
    a, b = [p[1] for p in pary], [p[2] for p in pary]
    try:
        Z['r'] = round(statistics.correlation(a, b), 3)
    except (statistics.StatisticsError, ValueError, ZeroDivisionError):
        Z['r'] = None
    big = [(x, y) for _, x, y in pary if abs(x) >= JPX_ZNAK and abs(y) >= JPX_ZNAK]
    Z['znak'] = [sum(1 for x, y in big if x * y > 0), len(big)]
    zle = [p for p in pary[-4:] if abs(p[1]) >= JPX_DUZE and abs(p[2]) >= JPX_DUZE and p[1] * p[2] < 0]
    Z['status'] = '✅' if Z['r'] is not None and Z['r'] >= JPX_R_MIN and not zle else '⚠️'
    o = Z['ostatnia']
    Z['opis'] = (f'{Z["status"]} r = {Z["r"] if Z["r"] is not None else "—"} z {n} tygodni, ten sam kierunek w {Z["znak"][0]} z {Z["znak"][1]} '
                 f'(oba ≥ {JPX_ZNAK:g} mld JPY); ostatni tydzień {o["tydzien"]}: giełda {o["gielda_mld"]:+.1f} vs MOF {o["mof_mld"]:+.1f} mld JPY')
    if Z['status'] == '⚠️':
        Z['uwagi'].append('Japonia — zagranica w akcjach, giełda vs MOF: ' + Z['opis'][3:]
                          + ('; przeciwny kierunek w dużym tygodniu ' + ', '.join(p[0] for p in zle) if zle else '') + ' — różne miary, tylko uwaga')
    return Z


def jpx_korekty(jx, now=None):
    """Informacje o korekcie danych źródła zapisane przez zbieracz (jpx.json → korekty: [czas, tekst]) z ostatnich JPX_KOREKTA_DNI dni → uwagi.
    Zbieracz nie poprawia jeszcze zapisanych tygodni na ich podstawie (następna wersja) — uwaga mówi, że trzeba sprawdzić ręcznie."""
    now = now or NOW
    out = []
    for k in (jx.get('korekty') or []) if isinstance(jx, dict) and isinstance(jx.get('korekty'), list) else []:
        if not (isinstance(k, list) and len(k) == 2 and isinstance(k[1], str)):
            continue
        try:
            t = dt.datetime.fromisoformat(str(k[0]))
        except ValueError:
            continue
        t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        if now - t < dt.timedelta(days=JPX_KOREKTA_DNI):
            out.append(f'Japonia — giełda ({czas_pl(k[0])}): {k[1][:200]}')
    return out


def jpx_kontrola(files, R):
    """Krok kontroli v137 (bez sieci): porównanie giełda vs MOF i informacje o korektach źródła; uwagi do R['uwagi'] (nigdy do błędów).
    Brak pliku jpx = None."""
    Z = jpx_mof_porownanie(files.get('instytucje'), files.get('jpx'))
    if Z:
        R['uwagi'].extend(Z['uwagi'])
        Z['korekty'] = jpx_korekty(files.get('jpx'))
        R['uwagi'].extend(Z['korekty'])
    return Z


# ---------------------------------------------------------------- v247: strona w przeglądarce bez okna (Chrome, ekran telefonu) -----------
# Kontrola otwiera stronę jak telefon, czeka na dane i wykresy (czas wirtualny strony), zapisuje stronę i komunikaty konsoli. Nieobsłużony błąd
# JavaScriptu = ⚠️ (testy strony liczą na danych zastępczych — tu prawdziwe). 06.10.2026 lokalnie: zrzut po 10 s, 170 grafik, konsola pusta.
PRZEGL_PROGRAMY = ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser',
                   '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
PRZEGL_CZAS_S = 90          # najdłużej tyle czekamy na zrzut strony — potem przeglądarka jest zamykana („nie sprawdzono”)
PRZEGL_BUDZET_MS = 20000    # czas wirtualny strony przed zrzutem (dane, wykresy, liczniki odświeżania)
PRZEGL_OKNO = '390,844'     # ekran telefonu
PRZEGL_KONSOLA = re.compile(r':CONSOLE(?::\d+\]|\(\d+\)\]) "(.*)", source: (\S*) \((\d+)\)\s*$', re.S)   # v248: też CONSOLE(N); wiele linii
PRZEGL_REKORD = re.compile(r'\n(?=\[\d+:\d+:\d{4}/)')   # v248: nowy wpis logu zaczyna się od „[proces:wątek:MMDD/” — komunikat bywa wielowierszowy
PRZEGL_ZNACZNIK = 'const EXTRA'   # v248: zrzut to nasza strona (ten sam znacznik co pobranie index.html), nie np. strona 404
PRZEGL_BLAD = re.compile(r'^(Uncaught (\(in promise\) )?)?(\[object \w*(Error|Exception)\]|\w*(Error|Exception)\b)')   # v250/v252: nazwa błędu JS (też DOMException, „[object DOMException]”)
PRZEGL_KONSOLA_LUZ = re.compile(r':CONSOLE(?::\d+\]|\(\d+\)\]) "(.*?)", source: (\S*) \((\d+)\)', re.S)   # v252: wpis z doklejoną obcą linią
PRZEGL_POPRZ_H = 30   # v250: „drugi raz z rzędu” — poprzednia kontrola z przeglądarką nie starsza niż tyle godzin
PRZEGL_MIN_WYKRESY = 10   # v248: wykresów liniowych poza tekstem skryptów — 06.10: 20 z danymi, 0 bez danych (strona z pliku, dane niedostępne)
# v356: „Infinity” tylko jako artefakt liczbowy — ze znakiem (+, -, minus U+2212, półpauza U+2013) przed nim, z „%”, walutą albo jednostką (mld, mln, tys, bln, USD, EUR, PLN, pkt)
# zaraz po nim, albo gdy przed nim nie stoi wyraz (np. „Zmiana: Infinity”); „PancakeSwap Infinity” (nazwa protokołu w panelu DEX) to nazwa własna, nie błąd
PRZEGL_INF = (r'(?<=[+\-−–])\bInfinity\b|(?<![^\W\d_] )\bInfinity\b|\bInfinity\b(?=\s?(?:%|[$€£]|(?:mld|mln|tys|bln|USD|EUR|PLN|pkt)\b))')
PRZEGL_ARTEFAKTY = re.compile(r'\bNaN\b|\bundefined\b|\[object Object\]|' + PRZEGL_INF + r'|\bnull\b|∞|Invalid Date')   # v252: „∞” — Intl dla Infinity; v356: „Infinity” patrz wyżej
#   # v250: napisy-błędy (06.10: 0 na całej stronie)


def przegladarka_artefakty(tresc):
    """v250: napisy-błędy w tekście narysowanej strony (bez skryptów — już usunięte —, stylów, znaczników i atrybutów): „NaN”, „undefined”,
    „[object Object]”, „Infinity”, „null” — objaw błędu na prawdziwych danych → fragmenty tekstu z otoczeniem (gdzie).
    v356: „Infinity” tylko jako artefakt liczbowy — nazwa protokołu „PancakeSwap Infinity” nie jest błędem (PRZEGL_INF)."""
    t = re.sub(r'<style\b[^>]*>.*?</style>', ' ', str(tresc or ''), flags=re.S | re.I)
    t = ' '.join(re.sub(r'<[^>]+>', ' ', t).split())
    return [t[max(0, m.start() - 40):m.end() + 20] for m in PRZEGL_ARTEFAKTY.finditer(t)]


def przegladarka_program(kandydaci=PRZEGL_PROGRAMY, szukaj=None):
    """v247: ścieżka przeglądarki — zmienna KONTROLA_CHROME albo pierwszy znaleziony program; brak = None."""
    szukaj = szukaj or shutil.which
    env = os.environ.get('KONTROLA_CHROME')
    for k in ((env,) if env else ()) + tuple(kandydaci):
        p = (k if os.path.exists(k) else None) if os.path.isabs(k) else szukaj(k)
        if p:
            return p
    return None


def przegladarka_konsola(log):
    """v247: komunikaty konsoli z logu przeglądarki → {'bledy': nieobsłużone wyjątki („Uncaught …”, także odrzucone obietnice),
    'zasoby': nieudane wczytania i zapytania zablokowane (adres; 06.10 lokalnie: źródło cen krypto po kilku próbach — strona ma zapas),
    'inne': pozostałe komunikaty (console.error/warn/log), 'nieczytelne': liczba wpisów konsoli, których nie udało się odczytać}.
    v248: log dzielony na wpisy tylko przed nowym wpisem — komunikat z nową linią (np. błąd JSON.parse z treścią strony błędu) nie ginie."""
    out = {'bledy': [], 'zasoby': [], 'inne': [], 'nieczytelne': 0}
    for rek in PRZEGL_REKORD.split(str(log or '')):
        if ':CONSOLE' not in rek[:120]:
            continue
        m = PRZEGL_KONSOLA.search(rek) or PRZEGL_KONSOLA_LUZ.search(rek)   # v252: obca linia doklejona do wpisu — wpis nadal odczytany
        if not m:
            if re.search(r':CONSOLE[^\]]*\] "Uncaught', rek):   # v250: obca linia doklejona do wpisu z błędem — nadal błąd
                out['bledy'].append('nieczytelny wpis z „Uncaught” (zob. log przeglądarki)')
            else:
                out['nieczytelne'] += 1
            continue
        msg, src, nr = ' '.join(m.group(1).split()), m.group(2), m.group(3)   # wiele linii → jedna
        if msg.startswith('Uncaught') or PRZEGL_BLAD.match(msg):   # v250: też błąd złapany przez stronę i wypisany przez console.error
            out['bledy'].append(f'{msg[:160]} ({src.split("?")[0].rsplit("/", 1)[-1][:40] or "strona"}:{nr})')
        elif msg.startswith('Failed to load resource'):
            out['zasoby'].append(src[:160])
        elif msg.startswith("Access to fetch at '"):   # zapytanie zablokowane przez przeglądarkę (CORS — zwykle limit źródła: odpowiedź bez nagłówka)
            out['zasoby'].append(msg[len("Access to fetch at '"):].split("'", 1)[0][:160])
        else:
            out['inne'].append(msg[:160])
    return out


def strona_przegladarka(url, czas_s=PRZEGL_CZAS_S, program=None, zegar=time.monotonic, spij=time.sleep):
    """v247: strona w przeglądarce bez okna. v248 → {'stan': 'ok', 'ok': True, 'czas_s', 'bajty', 'svg', 'wykresy' (bez tekstu skryptów),
    'bledy', 'zasoby', 'inne', 'nieczytelne'} albo {'stan': 'brak_programu' | 'zakonczona' (awaria: kod i ostatni wpis błędu) | 'zawieszona'
    (przeglądarka działa, strony brak — zawieszona strona albo źródło, które nie odpowiada) | 'inna_strona' (brak znacznika), 'brak': opis, …}.
    Osobny profil tymczasowy; po zrzucie albo czas_s — zamknięcie całej grupy procesów."""
    c = termin_czas(czas_s)   # v327 (KON-04): przeglądarka w terminie całej kontroli (z zapasem 30 s); za mało czasu — bez uruchamiania
    if c < czas_s:
        if c < 10:
            return {'stan': 'blad', 'brak': 'pominięta — kończy się czas całej kontroli'}
        czas_s = c
    program = program or przegladarka_program()
    if not program:
        return {'stan': 'brak_programu', 'brak': 'brak przeglądarki na maszynie kontroli'}
    with tempfile.TemporaryDirectory(prefix='kontrola-przegl-') as tmp:
        args = [program, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
                '--disable-dev-shm-usage', f'--user-data-dir={os.path.join(tmp, "profil")}', '--enable-logging=stderr', '--v=1',
                f'--virtual-time-budget={PRZEGL_BUDZET_MS}', f'--window-size={PRZEGL_OKNO}', '--dump-dom', url]
        if sys.platform.startswith('linux'):
            args.insert(1, '--no-sandbox')   # maszyny GitHub (ubuntu) nie dają piaskownicy jądra; otwieramy tylko własną stronę
        po, pe = os.path.join(tmp, 'strona.html'), os.path.join(tmp, 'konsola.log')
        t0, rc = zegar(), None
        with open(po, 'wb') as fo, open(pe, 'wb') as fe:
            p = subprocess.Popen(args, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                while zegar() - t0 < czas_s and p.poll() is None:
                    try:
                        with open(po, 'rb') as f:
                            f.seek(max(0, os.path.getsize(po) - 64))
                            if b'</html>' in f.read():
                                break
                    except OSError:
                        pass
                    spij(1)
            finally:
                rc = p.poll()   # v248: zakończona sama (awaria) czy nadal działa
                try:
                    os.killpg(p.pid, signal.SIGKILL)   # przeglądarka nie zamyka się sama (liczniki strony) — cała grupa procesów
                except OSError:
                    pass
                try:
                    p.wait(timeout=10)
                except Exception:  # noqa
                    pass
        czas = round(zegar() - t0, 1)
        with open(po, 'rb') as f:
            dom = f.read().decode('utf-8', 'replace')
        with open(pe, 'rb') as f:
            log = f.read().decode('utf-8', 'replace')
    K = przegladarka_konsola(log)
    if '</html>' not in dom[-64:]:
        if rc is not None:   # v248: przeglądarka zakończyła się sama bez strony — awaria (kod i ostatni wpis błędu)
            L = [x.strip() for x in log.splitlines() if x.strip()]
            ost = next((x for x in reversed(L) if ':ERROR:' in x or ':FATAL:' in x), L[-1] if L else '')
            return {'stan': 'zakonczona', 'brak': f'przeglądarka zakończyła się po {czas:g} s bez strony, kod {rc}'.replace('.', ',')
                    + (f': {ost[-100:]}' if ost else ''), 'czas_s': czas, **K}
        return {'stan': 'zawieszona', 'brak': f'strona nie oddała się w {czas_s} s — zawieszona strona albo źródło, które nie odpowiada',
                'czas_s': czas, **K}
    if PRZEGL_ZNACZNIK not in dom:
        return {'stan': 'inna_strona', 'brak': 'przeglądarka dostała inną stronę (bez znacznika strony)', 'czas_s': czas, **K}
    tresc = re.sub(r'<script\b[^>]*>.*?</script>', '', dom, flags=re.S | re.I)   # v248: tylko narysowana strona, nie tekst skryptów
    A = przegladarka_artefakty(tresc)   # v250: napisy-błędy w tekście strony
    return {'stan': 'ok', 'ok': True, 'czas_s': czas, 'bajty': len(dom), 'svg': tresc.count('<svg'), 'wykresy': tresc.count('class="arc-gr"'),
            'artefakty': A[:5], 'artefakty_n': len(A), **K}


def przegladarka_poprzedni(path, now=None):
    """v248: stan przeglądarki z ostatniej kontroli, która ją uruchamiała (kontrola/historia.json, pole 'przegl') albo None. v250: tylko
    z kontroli z ostatnich PRZEGL_POPRZ_H h (dwie szybkie publikacje mogą nadpisać wpis historii — stary stan nie liczy się „z rzędu”)."""
    now = now or NOW
    try:
        with open(path, encoding='utf-8') as f:
            H = json.load(f)
    except Exception:  # noqa
        return None
    for h in reversed(H) if isinstance(H, list) else ():
        if isinstance(h, dict) and h.get('przegl'):
            try:
                if (now - dt.datetime.fromisoformat(str(h.get('at')))).total_seconds() > PRZEGL_POPRZ_H * 3600:
                    return None
            except (TypeError, ValueError):
                pass
            return h['przegl']
    return None


def przegladarka_uwagi(P, poprzedni=None):
    """v247/v248: uwagi tylko z pełnego zrzutu: nieobsłużone błędy JavaScriptu, za mało wykresów liniowych (PRZEGL_MIN_WYKRESY). Strona,
    która się nie oddała (zawieszona albo wiszące źródło) — uwaga dopiero, gdy poprzednia kontrola z przeglądarką skończyła się tak samo."""
    if not isinstance(P, dict):
        return []
    out = []
    if P.get('ok'):
        if P.get('bledy'):
            out.append(f'strona w przeglądarce: błędów JavaScriptu {len(P["bledy"])} — pierwszy: {P["bledy"][0]}')
        if P.get('artefakty_n'):   # v250
            out.append(f'strona w przeglądarce: napisy-błędy w tekście strony (NaN, undefined…): {P["artefakty_n"]} — pierwszy: „{(P.get("artefakty") or ["—"])[0]}”')
        if isinstance(P.get('wykresy'), int) and P['wykresy'] < PRZEGL_MIN_WYKRESY:
            out.append(f'strona w przeglądarce: narysowanych wykresów liniowych tylko {P["wykresy"]} (zwykle ok. 20) — dane mogły się nie wczytać')
    elif P.get('stan') == 'zawieszona' and poprzedni == 'zawieszona':
        out.append(f'strona w przeglądarce: drugi raz z rzędu nie oddała się w {PRZEGL_CZAS_S} s — możliwa zawieszona strona (pętla w skrypcie) '
                   'albo źródło, które nie odpowiada')
    return out


def przegladarka_wiersz(P):
    """v247/v248: wiersz raportu „Strona w przeglądarce” — błędy JS i za mało wykresów ⚠️; nieudane wczytania, inne i nieczytelne komunikaty
    konsoli ℹ️; bez pełnego zrzutu „nie sprawdzono” ℹ️ (drugi raz z rzędu bez strony — ⚠️), z błędami z logu do przerwania jako informacją."""
    if not P.get('ok'):
        b = P.get('bledy') or []
        return (f'- Strona w przeglądarce (bez okna, ekran telefonu): nie sprawdzono ({P.get("brak") or "—"})'
                + (f'; w logu do przerwania błędów JavaScriptu: {len(b)}' if b else '') + (' ⚠️.' if P.get('powtorka') else ' ℹ️.'))
    b, z, i, nc = P.get('bledy') or [], P.get('zasoby') or [], P.get('inne') or [], P.get('nieczytelne') or 0
    malo = isinstance(P.get('wykresy'), int) and P['wykresy'] < PRZEGL_MIN_WYKRESY
    hosty = sorted({u.split('/')[2] if '://' in u else u for u in z})
    return (f'- Strona w przeglądarce (bez okna, ekran telefonu 390 px): zrzut po {str(P.get("czas_s", "—")).replace(".", ",")} s — grafik '
            f'{P.get("svg", 0)}, wykresów liniowych {P.get("wykresy", 0)}' + (' ⚠️ (zwykle ok. 20)' if malo else '')
            + f'; błędów JavaScriptu: {len(b)} ' + ('⚠️' if b else ('ℹ️' if nc else '✅'))
            + (f' (wpisów konsoli nieczytelnych: {nc})' if nc else '')
            + (f'; napisy-błędy w tekście (NaN, undefined…): {P["artefakty_n"]} ⚠️' if P.get('artefakty_n') else '')   # v250
            + (f'; nieudane wczytania: {len(z)} ({", ".join(hosty[:4])}) ℹ️' if z else '')
            + (f'; inne komunikaty konsoli: {len(i)} (pierwszy: {i[0][:80]}) ℹ️' if i else '') + '.')


# ---------------------------------------------------------------- v308: strona jak u czytelnika — druga, lekka runda przeglądarki ----------------
# Od v308 strona pobiera pliki zakładki CRYPTO (karty, scena: grupa 'c') dopiero przy pierwszym otwarciu CRYPTO albo TRENDÓW. Runda pełna otwiera
# stronę z ?pelna=1 (wszystko od razu, jak dawniej — te same wykresy i karty, ten sam próg PRZEGL_MIN_WYKRESY); druga, lekka runda — bez dopisku,
# jak u czytelnika: tylko błędy JavaScriptu i napisy-błędy (bez progu wykresów — karty CRYPTO celowo czekają na otwarcie zakładki).
PRZEGL_PELNA = '&pelna=1'


def przegladarka_lekka(site, pelna, otworz=None):
    """v308: druga runda — strona bez ?pelna=1 (jak u czytelnika). Tylko po pełnym zrzucie rundy pełnej: bez niego stan strony ocenia runda pełna
    (zawieszona strona albo brak przeglądarki) i nie czekamy drugi raz do PRZEGL_CZAS_S → {'stan': 'pominieta', 'brak': powód}."""
    if not (isinstance(pelna, dict) and pelna.get('ok')):
        return {'stan': 'pominieta', 'brak': 'runda pełna bez zrzutu strony'}
    try:
        return (otworz or strona_przegladarka)(f'{site}/?nc={int(time.time())}')
    except Exception as e:  # noqa
        return {'stan': 'blad', 'brak': f'błąd sprawdzania: {type(e).__name__}'}


def przegladarka_uwagi_lekka(P):
    """v308: uwagi z rundy bez ?pelna=1 (strona jak u czytelnika): nieobsłużone błędy JavaScriptu i napisy-błędy w tekście strony; bez pełnego
    zrzutu — bez uwagi (stan strony ocenia runda pełna). Mniej wykresów niż w rundzie pełnej to nie błąd — karty CRYPTO czekają na otwarcie zakładki."""
    if not (isinstance(P, dict) and P.get('ok')):
        return []
    out = []
    if P.get('bledy'):
        out.append(f'strona jak u czytelnika (bez ?pelna=1): błędów JavaScriptu {len(P["bledy"])} — pierwszy: {P["bledy"][0]}')
    if P.get('artefakty_n'):
        out.append(f'strona jak u czytelnika (bez ?pelna=1): napisy-błędy w tekście strony (NaN, undefined…): {P["artefakty_n"]} — pierwszy: „{(P.get("artefakty") or ["—"])[0]}”')
    return out


def przegladarka_wiersz_lekka(P):
    """v308: wiersz raportu rundy bez ?pelna=1 — błędy JavaScriptu i napisy-błędy ⚠️ (wpisy konsoli nieczytelne ℹ️); bez pełnego zrzutu
    „nie sprawdzono” ℹ️ (nigdy cichy ✅)."""
    h = '- Strona jak u czytelnika (bez ?pelna=1 — pliki CRYPTO dopiero po otwarciu zakładki): '
    if not (isinstance(P, dict) and P.get('ok')):
        return h + f'nie sprawdzono ({(P if isinstance(P, dict) else {}).get("brak") or "—"}) ℹ️.'
    b, nc = P.get('bledy') or [], P.get('nieczytelne') or 0
    return (h + f'zrzut po {str(P.get("czas_s", "—")).replace(".", ",")} s; błędów JavaScriptu: {len(b)} ' + ('⚠️' if b else ('ℹ️' if nc else '✅'))
            + (f' (pierwszy: {b[0][:80]})' if b else '') + (f' (wpisów konsoli nieczytelnych: {nc})' if nc else '')
            + (f'; napisy-błędy w tekście (NaN, undefined…): {P["artefakty_n"]} ⚠️' if P.get('artefakty_n') else '') + '.')


# ---------------------------------------------------------------- v141: lżejsza strona — pliki słowników języków (i18n/<język>.<skrót>.js) ----------------------------------------------------------------
I18N_MAPA = re.compile(r'const CF_I18N_H=(\{[^{}]*\})[;,]')
I18N_JEZYKI = ('de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja')


def i18n_skrot(jezyk, d_json):
    """Ten sam wzór co narzedzia/odchudz_strone.py (skrot): sha256(język + '\\n' + JSON słownika z pliku)[:8]."""
    import hashlib
    return hashlib.sha256((jezyk + '\n' + d_json).encode('utf-8')).hexdigest()[:8]


def i18n_kontrola(body, R, pobierz=None):
    """v141: index.html na żywo. Mapa plików słowników (CF_I18N_H) — każdy plik HTTP 200, treść window.CF_I18N_X tego języka i skrótu,
    skrót w nazwie = treść. Brak mapy = na żywo PEŁNA strona (przekształcenie przy publikacji odmówiło — publikacja dalej działa, ale strona
    jest cięższa; szczegóły w ostrzeżeniu „lżejsza strona” przebiegu „Strona i dane”). Tylko uwagi (najwyżej ⚠️, nigdy błąd).
    Wynik w R['strona']['i18n'] (linia raportu pod „Strona główna”)."""
    if body is None:
        return None
    pobierz = pobierz or get
    txt = body.decode('utf-8', 'replace') if isinstance(body, bytes) else str(body)
    m = I18N_MAPA.search(txt)
    if not m:
        R['strona']['i18n'] = {'pelna': True, 'opis': 'pełna strona (bez osobnych plików słowników)'}
        R['uwagi'].append('strona główna to PEŁNA wersja (bez osobnych plików słowników v141) — przekształcenie przy publikacji odmówiło; '
                          'zobacz ostrzeżenie „lżejsza strona” w przebiegu „Strona i dane”')
        return R['strona']['i18n']
    try:
        mapa = json.loads(m.group(1))
    except ValueError:
        mapa = {}
    zle, ok = [], 0
    for j in I18N_JEZYKI:
        h = mapa.get(j)
        if not (isinstance(h, str) and re.fullmatch(r'[0-9a-f]{8}', h)):
            zle.append(f'{j}: brak w mapie'); continue
        try:
            st, b, ms = pobierz(f'{SITE}/i18n/{j}.{h}.js')
        except urllib.error.HTTPError as e:
            zle.append(f'{j}.{h}.js: HTTP {e.code}'); continue
        except Exception as e:  # noqa
            zle.append(f'{j}.{h}.js: {str(e)[:60]}'); continue
        t = b.decode('utf-8', 'replace') if isinstance(b, bytes) else str(b)
        pre = f'window.CF_I18N_X={{"lang":"{j}","h":"{h}","d":'
        if st != 200:
            zle.append(f'{j}.{h}.js: HTTP {st}')
        elif not (t.startswith(pre) and t.endswith('};\n')) or i18n_skrot(j, t[len(pre):-3]) != h:
            zle.append(f'{j}.{h}.js: treść nie zgadza się ze skrótem w nazwie')
        else:
            ok += 1
    R['strona']['i18n'] = {'pelna': False, 'plikow': len(I18N_JEZYKI), 'ok': ok, 'zle': zle,
                           'opis': f'{ok} z {len(I18N_JEZYKI)} plików odpowiada, skróty zgodne' if not zle else f'{ok} z {len(I18N_JEZYKI)} w porządku'}
    if zle:
        R['uwagi'].append('pliki słowników języków (lżejsza strona): ' + '; '.join(zle) + ' — widz w tym języku dostanie angielski zapas')
    return R['strona']['i18n']


# ---------------------------------------------------------------- v133: tokenizowane aktywa RWA (data/rwa.json) ----------------------------------------------------------------
RWA_ETYKIETA = 'tokenizowane aktywa RWA (co 3 h)'   # v172: było co 6 h
RWA_SWIEZ_MIN = 12 * 60    # min — lista starsza (plik co 3 h od v172, część z błędem ponawiana po godzinie) = ⚠️; nigdy ❌ ani BŁĄD
RWA_PP = 1.0               # pkt proc. — |własna zmiana 7 dni − zmiana 7 dni podana przez źródło| (produkty z listy) większa = ⚠️
RWA_HIST_MIN = 8           # dni własnych zapisów sum potrzebnych do porównania zmian 7 dni (wcześniej tylko informacja)
RWA_SKOK = 25.0            # % — zmiana sumy między dwoma kolejnymi dniami zapisów większa = ⚠️ (dni z ostatniego tygodnia)
RWA_HID_MIN = 20           # mniej produktów spoza głównej listy z jakąkolwiek wartością w ostatnim pobraniu = ⚠️ (27.09: 33 z 47) — źródło
                           # przestało podawać ich wartości (pusty tekst, „0”, 400, 404); plan v128 §4.4
RWA_FZ_PROG = 50.0         # % — udział wartości bez bieżącej wyceny w (bieżące + bez wyceny) większy = ⚠️ (właściciel widzi to w raporcie; tylko uwaga)
RWA_HID_DNI = 3            # v196: dni od najmłodszego „brak od” produktów spoza listy — potem stan trwały (źródło zmieniło zakres danych)
RWA_HID_FZ = 5.0           # v196: % „bez bieżącej wyceny”, do którego trwały brak wartości spoza listy jest tylko informacją ℹ️ (06.10: 1,6%)


def rwa_swiezosc(j, now=None):
    """Wiersz świeżości (etykieta, status, wiek min, data, uwaga): czas listy (part_at.list, inaczej at); starszy niż RWA_SWIEZ_MIN = ⚠️, nigdy ❌.
    Brak pliku = ⚠️ „brak danych” (zbieracz bez poprzedniego pliku i bez danych nie zapisuje pliku — notatka w META, nie błąd)."""
    if not isinstance(j, dict):
        return (RWA_ETYKIETA, '⚠️', None, None, 'brak pliku data/rwa.json — panel na stronie ukryty (tylko uwaga)')
    pa = j.get('part_at') if isinstance(j.get('part_at'), dict) else {}
    ts = pa.get('list') if isinstance(pa.get('list'), str) else j.get('at')
    w = wiek_danych(ts, 'ts', 'h', now or NOW) if isinstance(ts, str) else None
    if w is None:
        return (RWA_ETYKIETA, '?', None, None, 'brak czasu danych w pliku')
    if w <= RWA_SWIEZ_MIN:
        return (RWA_ETYKIETA, '✅', w, ts, '')
    return (RWA_ETYKIETA, '⚠️', w, ts, f'lista starsza niż {RWA_SWIEZ_MIN // 60} h (plik co 3 h) — tylko uwaga')


def _rwa_hist(j):
    """Wiersze historii sum [dzień, suma, …] z prawdziwą datą i liczbą sumy (mln USD), rosnąco, bez powtórzeń."""
    out = {}
    for r in j.get('hist') or []:
        if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and isinstance(r[1], (int, float)) and not isinstance(r[1], bool) and r[1] > 0:
            try:
                dt.date.fromisoformat(r[0])
            except ValueError:
                continue
            out[r[0]] = float(r[1])
    return sorted(out.items())


def rwa_brak_od(j):
    """v196: najmłodszy dzień „brak od” w zapisach produktów spoza listy (hv: [wartość, dzień tej samej wartości, zmiana, odczyty, brak od]);
    brak zapisów albo dat = None."""
    hv = j.get('hv') if isinstance(j, dict) and isinstance(j.get('hv'), dict) else {}
    d = [r[4] for r in hv.values() if isinstance(r, list) and len(r) > 4 and isinstance(r[4], str) and re.match(r'^\d{4}-\d{2}-\d{2}$', r[4])]
    return max(d) if d else None


def rwa_porownanie(j, now=None):
    """Kontrola pliku RWA bez sieci (najwyżej ⚠️): (1) po ≥ RWA_HIST_MIN dniach zapisów — własna zmiana 7 dni produktów z listy vs zmiana 7 dni
    podana przez źródło (ważona wartością); źródło porównuje punkt godzinowy sprzed 168 h, my dzienne zapisy z chwil naszych pobrań, więc
    drobna różnica jest normalna; (2) produkty spoza głównej listy: ostatnie pobranie przerwane = ⚠️; ile ma bieżącą wartość, a ile wartość
    niezmienioną od dnia X (poza sumami zbieracza — źródło przestało je odświeżać; stan od 27.09.2026); udział wartości bez bieżącej wyceny
    w (bieżące + bez wyceny) ponad RWA_FZ_PROG % = ⚠️, inaczej informacja ℹ️;
    (3) skok sumy > RWA_SKOK % między dwoma kolejnymi dniami zapisów z ostatniego tygodnia. → {'status', 'opis', 'uwagi', …}."""
    now = now or NOW
    Z = {'status': '✅', 'opis': '', 'uwagi': []}
    if not isinstance(j, dict):
        return None
    H = _rwa_hist(j)
    chk = j.get('chk') if isinstance(j.get('chk'), dict) else {}
    n = j.get('n') if isinstance(j.get('n'), dict) else {}
    ok = j.get('ok') if isinstance(j.get('ok'), dict) else {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    cz = []
    span = (dt.date.fromisoformat(H[-1][0]) - dt.date.fromisoformat(H[0][0])).days + 1 if H else 0
    a, b = chk.get('c7_api_listed'), chk.get('c7_own_listed')
    Z['c7_api'], Z['c7_own'] = (a if num(a) else None), (b if num(b) else None)
    if span < RWA_HIST_MIN:
        cz.append(f'ℹ️ zapisów sum {len(H)} (od {H[0][0] if H else "—"}) — porównanie zmiany 7 dni od {RWA_HIST_MIN}. dnia')
    elif not (num(a) and num(b)):
        cz.append('ℹ️ zmiana 7 dni: brak jednej z liczb (własnej albo źródła) — bez oceny')
    else:
        d = abs(b - a)
        Z['c7_roznica_pp'] = round(d, 3)
        if d > RWA_PP:
            Z['status'] = '⚠️'
            Z['uwagi'].append(f'tokenizowane aktywa: zmiana 7 dni produktów z listy — własna {b:+.2f}% vs źródło {a:+.2f}% (różnica {d:.2f} pkt proc., próg {RWA_PP:g}); '
                              'źródło liczy od punktu godzinowego sprzed 168 h, my od dziennego zapisu z chwili pobrania — sprawdzić, czy różnica się utrzymuje')
        cz.append(f'zmiana 7 dni produktów z listy: własna {b:+.2f}% vs źródło {a:+.2f}% (różnica {d:.2f} pkt proc.) {"⚠️" if d > RWA_PP else "✅"}')
    hv, kept = n.get('hidden_valued'), n.get('kept')
    if ok.get('hidden') is False:
        Z['status'] = '⚠️'
        Z['uwagi'].append(f'tokenizowane aktywa: ostatnie pobranie wartości produktów spoza głównej listy przerwane — z poprzedniego dnia: {kept if num(kept) else "—"} '
                          '(ponowienie po 1 h, 2 h, potem co 3 h; tylko uwaga)')
        cz.append(f'produkty spoza listy: pobranie przerwane, z poprzedniego dnia {kept if num(kept) else "—"} ⚠️')
    if num(hv) and hv < RWA_HID_MIN:
        # v196: stan trwały (≥ RWA_HID_DNI dni od najmłodszego „brak od”) przy małym udziale „bez bieżącej wyceny” — tylko informacja, nie codzienna uwaga
        bo = rwa_brak_od(j)
        s0 = j.get('stale') if isinstance(j.get('stale'), dict) else {}
        sv0 = s0.get('v') if num(s0.get('v')) and s0.get('v') > 0 else 0.0
        cv0 = ((j.get('seg') or {}).get('all') or {}).get('v') if isinstance((j.get('seg') or {}).get('all'), dict) else None
        cv0 = cv0 if num(cv0) and cv0 > 0 else 0.0
        p0 = sv0 / (cv0 + sv0) * 100 if cv0 + sv0 > 0 else 0.0
        dni = (now.date() - dt.date.fromisoformat(bo)).days if bo else None
        if dni is not None and dni >= RWA_HID_DNI and p0 <= RWA_HID_FZ:
            cz.append(f'ℹ️ produkty spoza listy z wartością {hv} (próg {RWA_HID_MIN}) — źródło nie podaje ich wartości od {bo} ({dni} dni, stan trwały); '
                      + f'bez bieżącej wyceny {p0:.1f}% sumy'.replace('.', ',') + ' — bez uwagi')
        else:
            Z['status'] = '⚠️'
            Z['uwagi'].append(f'tokenizowane aktywa: produkty spoza głównej listy z jakąkolwiek wartością — tylko {hv} (próg {RWA_HID_MIN}) — źródło przestało '
                              'podawać ich wartości; ostatnio znane są w grupie „bez bieżącej wyceny”, sumy spadną (tylko uwaga)')
            cz.append(f'produkty spoza listy z wartością {hv} (próg {RWA_HID_MIN}) ⚠️')
    st = j.get('stale') if isinstance(j.get('stale'), dict) else {}
    sv = st.get('v') if num(st.get('v')) and st.get('v') > 0 else 0.0
    seg = j.get('seg') if isinstance(j.get('seg'), dict) else {}
    cv = (seg.get('all') or {}).get('v') if isinstance(seg.get('all'), dict) else None
    cv = cv if num(cv) and cv > 0 else 0.0
    if sv > 0:
        p = sv / (cv + sv) * 100
        Z['fz_pct'] = round(p, 1)
        ng = st.get('ng') if num(st.get('ng')) else 0
        kom = (f'bez bieżącej wyceny {p:.0f}% wartości ({sv / 1e9:.1f} mld USD, liczba produktów {st.get("n") if num(st.get("n")) else "—"}: '
               + (f'niezmienione co najmniej od {st.get("last") or "—"}' + (' — źródło stoi' if st.get('src') is True else '') if st.get('nf') or not ng else '')
               + (f'{", " if st.get("nf") else ""}{ng} bez wartości od {st.get("gone") or "—"}' if ng else '')
               + f'), z bieżącą wyceną {cv / 1e9:.1f} mld USD')
        if p > RWA_FZ_PROG:
            Z['status'] = '⚠️'
            Z['uwagi'].append(f'tokenizowane aktywa: {kom} — sumy na stronie obejmują tylko wartości bieżące (próg {RWA_FZ_PROG:g}%; tylko uwaga)')
        cz.append(kom + (' ⚠️' if p > RWA_FZ_PROG else ' ℹ️'))
    elif num(hv):
        cz.append(f'produkty spoza listy: z bieżącą wartością {hv}, bez bieżącej wyceny 0 ✅')
    lo = (now.date() - dt.timedelta(days=7)).isoformat()
    skoki = []
    hd = rwc_hd(j)   # v150: dzień zmiany zbioru produktów z odczytu własnego — skok liczony bez nich (zmiana zakresu danych, nie rynku)
    for d, x in rwe_hd(j).items():   # v169: dane emitentów tak samo (produkty z przedrostkiem e:, żeby zbiory się nie myliły)
        a = hd.get(d, (0.0, frozenset()))
        hd[d] = (a[0] + x[0], a[1] | frozenset('e:' + s for s in x[1]))
    for (d0, v0), (d1, v1) in zip(H, H[1:]):
        if d1 >= lo and (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days == 1:
            a0, a1 = hd.get(d0, (0.0, frozenset())), hd.get(d1, (0.0, frozenset()))
            if a0[1] != a1[1] and v0 - a0[0] > 0:
                p = ((v1 - a1[0]) / (v0 - a0[0]) - 1) * 100
                cz.append(f'ℹ️ {d1}: zmiana zbioru produktów z odczytu własnego albo danych emitentów ({a0[0] / 1e3:.1f} → {a1[0] / 1e3:.1f} mld USD) — skok sumy liczony bez nich')
            else:
                p = (v1 / v0 - 1) * 100
            if abs(p) > RWA_SKOK:
                skoki.append(f'{d0} → {d1}: {p:+.1f}%')
    Z['skoki'] = skoki
    if skoki:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa: skok sumy dzień do dnia ponad ' + f'{RWA_SKOK:g}%: ' + '; '.join(skoki[:3]) + ' — sprawdzić, czy to nie zmiana zakresu danych')
        cz.append('skok sumy: ' + '; '.join(skoki[:3]) + ' ⚠️')
    elif len(H) >= 2:
        cz.append(f'skoków sumy ponad {RWA_SKOK:g}% w tygodniu: brak ✅')
    Z['opis'] = '; '.join(cz)
    return Z


def rwa_kontrola(files, R):
    """Wynik porównań RWA do raportu (zgodność) i uwag; brak pliku = None (wiersz świeżości i tak mówi „brak pliku”)."""
    Z = rwa_porownanie(files.get('rwa'))
    if Z:
        R['uwagi'].extend(Z['uwagi'])
    return Z


# ---------------------------------------------------------------- v150: tokenizowane aktywa — odczyt własny z łańcucha (blok onchain w data/rwa.json) ----------------------------------------------------------------
RWC_ETYKIETA = 'tokenizowane aktywa — odczyt własny z łańcucha (co 3 h)'
RWC_SWIEZ_MIN = 12 * 60    # min — odczyt starszy (plik co 3 h od v172) = ⚠️; nigdy ❌ ani BŁĄD (zbieracz i tak nie liczy odczytów starszych niż 12 h)
RWC_SKOK_POD = 50.0        # % — zmiana podaży produktu między dwoma kolejnymi dniami zapisów (24 h) większa = ⚠️ (zły kontrakt albo zmiana emisji)
RWC_RAZY = 3.0             # wartość z łańcucha vs ostatnio znana wartość źródła v133 tego produktu: więcej niż 3× albo mniej niż 1/3 = ⚠️


def rwc_swiezosc(j, now=None):
    """Wiersz świeżości odczytu własnego (etykieta, status, wiek min, data, uwaga) — czas bloku onchain (at). Brak pliku = None (wiersz RWA mówi
    „brak pliku”); plik bez bloku (przed pierwszym odczytem po wdrożeniu v150) albo wyłącznik RWA_CHAIN_OFF = status „—” z opisem, bez uwagi;
    starszy niż RWC_SWIEZ_MIN = ⚠️, nigdy ❌."""
    if not isinstance(j, dict):
        return None
    oc = j.get('onchain')
    if not isinstance(oc, dict):
        return (RWC_ETYKIETA, '—', None, None, 'brak odczytu własnego w pliku (przed pierwszym odczytem po wdrożeniu v150)')
    if oc.get('off'):
        return (RWC_ETYKIETA, '—', None, None, 'wyłączone (RWA_CHAIN_OFF)')
    ts = oc.get('at')
    w = wiek_danych(ts, 'ts', 'h', now or NOW) if isinstance(ts, str) else None
    if w is None:
        return (RWC_ETYKIETA, '?', None, None, 'brak czasu odczytu w pliku')
    if w <= RWC_SWIEZ_MIN:
        return (RWC_ETYKIETA, '✅', w, ts, '')
    return (RWC_ETYKIETA, '⚠️', w, ts, f'odczyt starszy niż {RWC_SWIEZ_MIN // 60} h (plik co 3 h) — produkty z odczytu własnego wracają do „bez bieżącej wyceny”')


def rwc_hd(j):
    """Dzienny zapis odczytu własnego z pliku: {dzień: (mln USD w sumach, zbiór produktów)} — tylko poprawne wiersze."""
    oc = j.get('onchain') if isinstance(j, dict) else None
    hd = oc.get('hd') if isinstance(oc, dict) and isinstance(oc.get('hd'), dict) else {}
    out = {}
    for d, x in hd.items():
        if (isinstance(d, str) and isinstance(x, list) and len(x) == 2 and isinstance(x[0], (int, float)) and not isinstance(x[0], bool)
                and x[0] >= 0 and isinstance(x[1], list)):
            out[d] = (float(x[0]), frozenset(s for s in x[1] if isinstance(s, str)))
    return out


def rwc_porownanie(j, now=None):
    """Kontrola odczytu własnego bez sieci (najwyżej ⚠️): (1) podaż produktu — zmiana między dwoma kolejnymi dniami zapisów (24 h) ponad
    RWC_SKOK_POD % = ⚠️; (2) wartość z łańcucha vs ostatnio znana wartość źródła v133 (zapis hv) — poza [1/RWC_RAZY, RWC_RAZY] = ⚠️ (zły
    adres, zła reguła ceny albo miejsca dziesiętne); (3) produkty z listy bez pełnego odczytu (sieci bez liczby albo cena nieświeża) — ⚠️ gdy
    wypadły z sum, ℹ️ gdy to stały brak sieci, której nie czytamy; (4) sieci bez odpowiedzi w ostatnim odczycie (ok False) = ⚠️.
    Brak pliku albo bloku = None; wyłącznik = opis „wyłączone”. → {'status', 'opis', 'uwagi', …}."""
    if not isinstance(j, dict) or not isinstance(j.get('onchain'), dict):
        return None
    oc = j['onchain']
    Z = {'status': '✅', 'opis': '', 'uwagi': []}
    if oc.get('off'):
        Z['opis'] = 'wyłączone (RWA_CHAIN_OFF) — sumy bez odczytu własnego'
        return Z
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    P = oc.get('p') if isinstance(oc.get('p'), dict) else {}
    used = oc.get('used') if isinstance(oc.get('used'), dict) else {}
    hv = j.get('hv') if isinstance(j.get('hv'), dict) else {}
    cz, skoki, razy, braki = [], [], [], []
    for s, p in sorted(P.items()):
        if not isinstance(p, dict):
            continue
        nm = p.get('name') if isinstance(p.get('name'), str) else s
        H = sorted((x for x in ((oc.get('hs') or {}).get(s) or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and num(x[1])),
                   key=lambda x: x[0])
        if len(H) >= 2:
            (d0, a), (d1, b) = H[-2], H[-1]
            try:
                kol = (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days == 1
            except ValueError:
                kol = False
            if kol and a > 0 and abs(b / a - 1) * 100 > RWC_SKOK_POD:
                skoki.append(f'{nm} {d0} → {d1}: {(b / a - 1) * 100:+.0f}%')
        v = p.get('v') if num(p.get('v')) else None
        r = hv.get(s)
        if v and isinstance(r, list) and r and num(r[0]) and r[0] > 0 and not (1 / RWC_RAZY <= v / r[0] <= RWC_RAZY):
            razy.append(f'{nm}: z łańcucha {v / 1e9:.2f} mld USD vs ostatnio znana {r[0] / 1e9:.2f} mld USD ({v / r[0]:.1f}×)')
        if s not in used:
            n, nr = p.get('n'), p.get('nr')
            if num(n) and num(nr) and nr < n:
                braki.append(f'{nm}: {nr} z {n} kontraktów' + (f' (bez liczby: {", ".join(p.get("un") or [])})' if p.get('un') else ''))
            elif p.get('px_ok') is False:
                braki.append(f'{nm}: cena nieświeża ({p.get("px_at") or "—"})')
            elif 'rez' in p and not (isinstance(p.get('rez'), dict) and p['rez'].get('ok') is True):
                braki.append(f'{nm}: brak bieżących danych emitenta o rezerwie (wybite, niewydane)')   # v160: Tether Gold
    if skoki:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): podaż zmieniła się w ciągu doby o ponad ' + f'{RWC_SKOK_POD:g}%: ' + '; '.join(skoki[:3])
                          + ' — sprawdzić kontrakt i emisję')
        cz.append('podaż 24 h: ' + '; '.join(skoki[:3]) + ' ⚠️')
    else:
        cz.append(f'podaż 24 h: zmian ponad {RWC_SKOK_POD:g}% brak ✅')
    if razy:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): wartość z łańcucha daleko od ostatnio znanej: ' + '; '.join(razy[:3]) + ' — sprawdzić adresy i regułę ceny')
        cz.append('wartość vs ostatnio znana: ' + '; '.join(razy[:3]) + ' ⚠️')
    elif P:
        cz.append(f'wartość vs ostatnio znana: w paśmie 1/{RWC_RAZY:g}–{RWC_RAZY:g}× ✅')
    tot = sum(x for x in used.values() if num(x))
    cz.append(f'w sumach z odczytu własnego: {len(used)} z {len(P)} produktów, {tot / 1e9:.1f} mld USD')
    if braki:
        cz.append('bez pełnego odczytu (poza sumami): ' + '; '.join(braki[:4]) + ' ℹ️')
    hd = rwc_hd(j)
    dzis = (oc.get('at') or '')[:10]
    wcz = [d for d in sorted(hd) if d < dzis]
    wyp = sorted(s for s in (hd[wcz[-1]][1] if wcz else ()) if s not in used)
    if wyp:
        Z['status'] = '⚠️'
        nm = lambda s: (P.get(s) or {}).get('name') if isinstance(P.get(s), dict) and isinstance((P.get(s) or {}).get('name'), str) else s  # noqa: E731
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): po ' + wcz[-1] + ' już nie liczone z łańcucha: ' + ', '.join(nm(s) for s in wyp)
                          + ' — odczyt niepełny, cena nieświeża albo źródło v133 znów podaje bieżącą wartość (tylko uwaga)')
        cz.append('już nie z łańcucha: ' + ', '.join(nm(s) for s in wyp) + ' ⚠️')
    if oc.get('ok') is False:
        Z['status'] = '⚠️'
        nt = [x for x in (oc.get('notes') or []) if isinstance(x, str)]
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): ostatni odczyt niepełny — ' + ('; '.join(nt[:2]) if nt else 'brak szczegółów')
                          + ' (wartości z poprzedniego odczytu najwyżej 12 h; tylko uwaga)')
        cz.append('ostatni odczyt niepełny ⚠️')
    Z['skoki_podazy'], Z['razy'], Z['braki'], Z['wypadly'] = skoki, razy, braki, wyp
    Z['opis'] = '; '.join(cz)
    return Z


def rwc_kontrola(files, R):
    """Wynik porównań odczytu własnego do raportu (zgodność) i uwag; brak pliku albo bloku = None."""
    Z = rwc_porownanie(files.get('rwa'))
    if Z:
        R['uwagi'].extend(Z['uwagi'])
    return Z


# ---------------------------------------------------------------- v169: tokenizowane aktywa — dane emitentów (blok issuer w data/rwa.json) ----------------------------------------------------------------
RWE_ETYKIETA = 'tokenizowane aktywa — dane emitentów (co 3 h)'
RWE_SWIEZ_MIN = 12 * 60    # min — odczyt starszy (plik co 3 h od v172) = ⚠️; nigdy ❌ ani BŁĄD
RWE_ZAKRES = (0.8, 1.25)   # wartość wg emitenta vs ostatnio znana źródła v133 poza tym pasmem = informacja ℹ️ (inny zakres liczenia albo prawdziwa zmiana)
RWE_K_BEZ_UWAGA = 0.05     # v311: % wartości produktu — granica pominiętych tokenów bez dowodu rezerw od tylu = ⚠️ (tylko uwaga). Test wsteczny
                           # (ws53/v311-xstocks/bt/bt_xs311.out): żywe 10.10.2026 — 58 tokenów, ok. 0,003% (ceny akcji ok. 150 USD; 0,11% nawet przy
                           # 5 870 USD za każdą); token „pusty” jak dzisiejsze przy najwyższej cenie akcji na stronie — 0,0037% (0 fałszywych ⚠️ z 1000);
                           # brak dowodu u prawdziwego tokenu w obiegu — ⚠️ od ok. 234 tys. USD wartości (92 z 713 takich przypadków na nagraniu 05.10)
RWE_SEC_OKNO = (19 * 60, 21 * 60)   # v315 (recenzja v311): to samo okno co RWE_SEC_OKNO w zbieraj_dane.py (test pilnuje zgodności) — opis z wartości


def rwe_swiezosc(j, now=None):
    """Wiersz świeżości danych emitentów (etykieta, status, wiek min, data, uwaga) — czas bloku issuer (at). Brak pliku = None (wiersz RWA mówi
    „brak pliku”); plik bez bloku (przed pierwszym odczytem po wdrożeniu v169) albo wyłącznik RWA_EM_OFF = status „—” z opisem, bez uwagi;
    starszy niż RWE_SWIEZ_MIN = ⚠️, nigdy ❌."""
    if not isinstance(j, dict):
        return None
    em = j.get('issuer')
    if not isinstance(em, dict):
        return (RWE_ETYKIETA, '—', None, None, 'brak danych emitentów w pliku (przed pierwszym odczytem po wdrożeniu v169)')
    if em.get('off'):
        return (RWE_ETYKIETA, '—', None, None, 'wyłączone (RWA_EM_OFF)')
    ts = em.get('at')
    w = wiek_danych(ts, 'ts', 'h', now or NOW) if isinstance(ts, str) else None
    if w is None:
        return (RWE_ETYKIETA, '?', None, None, 'brak czasu odczytu w pliku')
    if w <= RWE_SWIEZ_MIN:
        return (RWE_ETYKIETA, '✅', w, ts, '')
    return (RWE_ETYKIETA, '⚠️', w, ts, f'odczyt starszy niż {RWE_SWIEZ_MIN // 60} h (plik co 3 h) — produkty wg emitentów wracają do „bez bieżącej wyceny”')


def rwe_hd(j):
    """Dzienny zapis danych emitentów z pliku: {dzień: (mln USD w sumach, zbiór produktów)} — tylko poprawne wiersze."""
    em = j.get('issuer') if isinstance(j, dict) else None
    hd = em.get('hd') if isinstance(em, dict) and isinstance(em.get('hd'), dict) else {}
    out = {}
    for d, x in hd.items():
        if (isinstance(d, str) and isinstance(x, list) and len(x) == 2 and isinstance(x[0], (int, float)) and not isinstance(x[0], bool)
                and x[0] >= 0 and isinstance(x[1], list)):
            out[d] = (float(x[0]), frozenset(s for s in x[1] if isinstance(s, str)))
    return out


def rwe_porownanie(j, now=None):
    """Kontrola danych emitentów bez sieci (najwyżej ⚠️): (1) w sumach wg emitentów — ile produktów i ile mld USD; (2) produkty bez bieżących danych
    emitenta (poza sumami) z powodem — ℹ️; (3) wartość wg emitenta vs ostatnio znana źródła v133 poza pasmem RWE_ZAKRES — ℹ️ (różnica zakresu,
    np. STAC z klasą na Solanie, Centrifuge bez tokenów-opakowań — opisane na stronie); (4) produkty liczone poprzedniego dnia wg emitenta, a teraz
    już nie (zapis hd) — ⚠️; (5) ostatni odczyt niepełny (ok False) — ⚠️. Brak pliku albo bloku = None; wyłącznik = opis „wyłączone”.
    → {'status', 'opis', 'uwagi', 'braki', 'zakres', 'wypadly'}."""
    if not isinstance(j, dict) or not isinstance(j.get('issuer'), dict):
        return None
    em = j['issuer']
    Z = {'status': '✅', 'opis': '', 'uwagi': []}
    if em.get('off'):
        Z['opis'] = 'wyłączone (RWA_EM_OFF) — sumy bez danych emitentów'
        return Z
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    P = em.get('p') if isinstance(em.get('p'), dict) else {}
    used = em.get('used') if isinstance(em.get('used'), dict) else {}
    nm = lambda s: P[s]['name'] if isinstance(P.get(s), dict) and isinstance(P[s].get('name'), str) else s  # noqa: E731
    cz, braki, zakres = [], [], []
    tot = sum(x for x in used.values() if num(x))
    cz.append(f'w sumach wg emitentów: {len(used)} z {len(P)} produktów, {tot / 1e9:.1f} mld USD')
    for s, p in sorted(P.items()):
        if not isinstance(p, dict):
            continue
        st = p.get('stan')   # v175: stan produktu w sumach (pliki od v175); starsze — wg pełnego odczytu
        if st == 'brak':
            braki.append(f'{nm(s)}: nie ma go na liście źródła v133 — nie liczony')
        elif (st == 'poza' if isinstance(st, str) else p.get('full') is not True):
            why = p.get('err') if isinstance(p.get('err'), str) else ('stan emitenta za stary albo brak ceny' if num(p.get('v')) else 'brak wartości')
            braki.append(f'{nm(s)}: {why[:120]}')
        v, r = used.get(s), p.get('ref')
        if num(v) and num(r) and r > 0 and not RWE_ZAKRES[0] <= v / r <= RWE_ZAKRES[1]:
            zakres.append(f'{nm(s)} {v / 1e6:.0f} mln USD vs ostatnio znana {r / 1e6:.0f} mln ({v / r:.2f}×)')
    if zakres:
        cz.append('inny zakres niż ostatnio znana (opisane na stronie): ' + '; '.join(zakres[:4]) + ' ℹ️')
    for s, p in sorted(P.items()):   # v302: liczba dnia emitenta a liczba z nagłówka jego strony (Ondo Global Markets; nagłówek bez daty) — informacja
        if isinstance(p, dict) and num(p.get('hl')) and p['hl'] > 0 and num(p.get('v')) and abs(p['v'] / p['hl'] - 1) > 0.005:
            cz.append(f"{nm(s)}: punkt dnia emitenta ({str(p.get('as_of'))[:10]}) {p['v'] / 1e6:.0f} mln USD vs liczba w nagłówku jego strony "
                      f"{p['hl'] / 1e6:.0f} mln ({(p['v'] / p['hl'] - 1) * 100:+.2f}%) — w sumach punkt dnia (nagłówek bez daty) ℹ️")
    for s, p in sorted(P.items()):   # v267: reszta listy emitenta poza odczytem (xStocks: lista dłuższa niż strona odpowiedzi) — informacja
        og = p.get('ogon') if isinstance(p, dict) and isinstance(p.get('ogon'), dict) else None
        if og and num(og.get('n')) and num(og.get('max_usd')):
            x = og['max_usd']   # v268: odmiana i małe kwoty (było „1 tokenów … 0.00 mln USD”)
            kw = (f'{x / 1e6:.2f} mln USD' if round(x / 1e3, 1) >= 1000 else f'{x / 1e3:.1f} tys. USD' if round(x) >= 1000
                  else f'{x:.0f} USD')   # v270: jednostka po zaokrągleniu (999 960 → 1.00 mln, nie „1000.0 tys.”)
            pr = og['max_usd'] / p['v'] * 100 if num(p.get('v')) and p['v'] > 0 else None
            cz.append(f"{nm(s)}: reszta listy emitenta poza odczytem ({og['n']} {_odm(og['n'], 'token', 'tokeny', 'tokenów')}) najwyżej {kw}"
                      + ((f' ({pr:.3f}% wartości)' if pr >= 0.001 else ' (<0.001% wartości)') if pr is not None else '') + ' ℹ️')
    for s, p in sorted(P.items()):   # v311: tokeny bez dowodu rezerw pominięte z górną granicą wartości (xStocks) — ℹ️, od RWE_K_BEZ_UWAGA % — ⚠️
        bz = p.get('bez') if isinstance(p, dict) and isinstance(p.get('bez'), dict) else None
        if bz and num(bz.get('n')) and bz['n'] >= 1 and num(bz.get('max_usd')) and bz['max_usd'] >= 0:
            x, nb = bz['max_usd'], int(bz['n'])
            kw = (f'{x / 1e6:.2f} mln USD' if round(x / 1e3, 1) >= 1000 else f'{x / 1e3:.1f} tys. USD' if round(x) >= 1000 else f'{x:.0f} USD')
            pr = x / p['v'] * 100 if num(p.get('v')) and p['v'] > 0 else None
            sy = [y for y in (bz['sym'] if isinstance(bz.get('sym'), list) else []) if isinstance(y, str)][:3]
            duzo = pr is not None and pr >= RWE_K_BEZ_UWAGA
            cz.append(f"{nm(s)}: pominięte tokeny bez dowodu rezerw u emitenta — {nb} {_odm(nb, 'token', 'tokeny', 'tokenów')}"
                      + (f" (np. {', '.join(sy)})" if sy else '') + (f", w obiegu łącznie {bz['obieg']:g}" if num(bz.get('obieg')) else '')
                      + f' — najwyżej {kw}' + ((f' ({pr:.3f}% wartości)' if pr >= 0.001 else ' (<0.001% wartości)') if pr is not None else '')
                      + (f", odczyt {p['read'][:16].replace('T', ' ')} UTC" if isinstance(p.get('read'), str) else '') + (' ⚠️' if duzo else ' ℹ️'))
            if duzo:
                Z['status'] = '⚠️'
                Z['uwagi'].append(f'tokenizowane aktywa (dane emitentów): {nm(s)} — pominięte tokeny bez dowodu rezerw mogą być warte do {kw} ({pr:.3f}% '
                                  'wartości produktu): emitent może nie publikować dowodu dla tokenów w obiegu; produkt dalej w sumach (tylko uwaga)')
    bnn = [(nm(s), p['bn']) for s, p in sorted(P.items()) if isinstance(p, dict) and p.get('bn') in ('gm', 'okno')]
    if bnn:   # v311: ostatni odczyt bez nowych danych (nie błąd — w sumach poprzedni odczyt z jego stanem) — informacja
        cz.append('bez nowych danych w ostatnim odczycie (to nie błąd, w sumach poprzedni odczyt): ' + '; '.join(
            f'{n} — ' + ('punkt dnia taki sam jak przyjęty wcześniej tej doby' if b == 'gm' else
                         f'pusta lista kanału w znanym oknie dziennym {RWE_SEC_OKNO[0] // 60}–{RWE_SEC_OKNO[1] // 60} UTC')   # v315: z wartości okna
            for n, b in bnn) + ' ℹ️')
    if braki:
        cz.append('bez bieżących danych emitenta (poza sumami): ' + '; '.join(braki[:4]) + ' ℹ️')
    hd = rwe_hd(j)
    dzis = (em.get('at') or '')[:10]
    wcz = [d for d in sorted(hd) if d < dzis]
    wyp = sorted(s for s in (hd[wcz[-1]][1] if wcz else ()) if s not in used)
    inne = [s for s in wyp if isinstance(P.get(s), dict) and P[s].get('stan') in ('l', 'o')]   # v175: liczony innym źródłem — informacja, nie uwaga
    if inne:
        cz.append('liczone teraz innym źródłem (bieżąca wartość źródła v133 albo odczyt z łańcucha): ' + ', '.join(nm(s) for s in inne) + ' ℹ️')
    wyp = [s for s in wyp if s not in inne]
    if wyp:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa (dane emitentów): po ' + wcz[-1] + ' już nie liczone wg emitenta: ' + ', '.join(nm(s) for s in wyp)
                          + ' — odczyt nieudany, stan za stary albo źródło v133 znów podaje bieżącą wartość (tylko uwaga)')
        cz.append('już nie wg emitenta: ' + ', '.join(nm(s) for s in wyp) + ' ⚠️')
    if em.get('ok') is False:
        Z['status'] = '⚠️'
        nt = [x for x in (em.get('notes') or []) if isinstance(x, str)]
        Z['uwagi'].append('tokenizowane aktywa (dane emitentów): ostatni odczyt niepełny — ' + ('; '.join(x[:160] for x in nt[:2]) if nt else 'brak szczegółów')
                          + ' (poprzednie odczyty z ich stanem; tylko uwaga)')
        cz.append('ostatni odczyt niepełny ⚠️')
    Z['braki'], Z['zakres'], Z['wypadly'] = braki, zakres, wyp
    Z['opis'] = '; '.join(cz)
    return Z


def rwe_kontrola(files, R):
    """Wynik kontroli danych emitentów do raportu i uwag; brak pliku albo bloku = None."""
    Z = rwe_porownanie(files.get('rwa'))
    if Z:
        R['uwagi'].extend(Z['uwagi'])
    return Z


# ---------------------------------------------------------------- v295: surowce (data/surowce.json w wersji 2) ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian — test liczy jej wiersze), najwyżej ⚠️: przerwy w publikacji (święta w USA,
# przerwa w pracy urzędu, święta ACER) to nie awaria strony; pole next pliku mówi, kiedy spodziewana jest publikacja. Porównania z progami
# z testów wstecznych (surowce/projekt/testy_wsteczne.py, 07.10.2026) — tylko uwagi. ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku
# (zła jednostka, zero zamiast braku, daty nie rosną, pasmo 5 lat z min > max).
SU_ETYKIETA = {'ceny': 'surowce: ropa i gaz dziennie (strona dzienna T+1, API co tydzień)', 'zloto': 'surowce: złoto dziennie (LBMA PM wyliczona)',
               'live': 'surowce: złoto teraz (notowanie co godzinę)', 'zapasy': 'surowce: zapasy w USA (tydzień do piątku, publ. w środę)',
               'mies': 'surowce: ceny miesięczne (publ. ok. 2. dnia roboczego)', 'markets': 'surowce: pozycje funduszy (stan na wtorek, publ. w piątek)'}
SU_PROG = {'ceny': ('d', 36 * 60), 'zloto': ('d', 36 * 60), 'live': ('h', 3 * 60), 'zapasy': ('w', 13 * 24 * 60), 'mies': ('m', 45 * 24 * 60),
           'markets': ('w', 13 * 24 * 60)}   # v298: 13 dni (było 12 — 1,14% kontroli z ⚠️ w poniedziałki po święcie; test wsteczny: SU3_PROG)
# zapasy: tydzień kończy się w piątek, raport w środę 10:30 czasu Nowego Jorku (w tygodniu ze świętem pn–śr: czwartek 11:00) — wiek od końca
# dnia danych tuż przed kolejnym raportem 11,6 dnia (ze świętem 12,7). Próg 13 dni = 7 dni cyklu + 5 do publikacji + 1 na święto. Test wsteczny
# (model kalendarza 2021–10.2026: środa / czwartek po święcie, czas letni i zimowy, kontrola 06:20 i 08:36 UTC oraz co godzinę): 9 dni — ⚠️ w 45%
# kontroli (pn–śr każdego tygodnia), 12 dni — 2%, 13 dni — 0%. Raport opóźniony o 2 dni (np. święto w środę) = ⚠️ z dopiskiem „zaległa”.
SU_ZLOTO_PROG = 0.75   # % — średnia miesiąca złota (z archiwum GLD) wobec MFW: 262 miesiące, p99 0,40%, maks. 0,61%
SU_ROPA_PROG = 4.0     # % — średnia miesiąca ropy (EIA) wobec Banku Światowego: 5 lat WTI maks. 3,55%, Brent 2,78%
SU_MIEDZ_PROG = 1.0    # % — miedź MFW wobec Banku Światowego: 417 miesięcy, p99 0,70%, maks. 1,22% (5 lat maks. 0,48%)
SU_MIN_SESJI = 15      # sesji w miesiącu — mniej = bez porównania średniej
SU_Q_DNI = 14          # dni — punkt do sprawdzenia bez potwierdzenia drugim źródłem młodszy niż tyle = uwaga
SU_DZ_TOL = 0.01       # USD — strona dzienna (2 miejsca po przecinku) wobec API tego samego dnia
SU_FUT_WTI = 0.01      # USD — v301: kontrakt Brenta (seria kontrolna) równy WTI z tego samego dnia (|różnica| < 0,01) = podejrzany punkt dostawcy
                       # (29.09.2026: 96,16 = WTI przy zmianie miesiąca kontraktu); zbieracz: SU_Q_FUT_WTI (w regule q jak brak notowania);
                       # tylko ℹ️ — test wsteczny 07.2007–10.2026: 2 takie dni na 4706 (2007, różnica Brent–WTI bliska zera)
SU_JEDN = {'brent': 'USD/bbl', 'wti': 'USD/bbl', 'hh': 'USD/MMBtu', 'ttf': 'EUR/MWh', 'lng_eu': 'EUR/MWh', 'ulsd_nyh': 'USD/gal', 'gas_nyh': 'USD/gal',
           'jet_gulf': 'USD/gal', 'propan': 'USD/gal', 'crack321': 'USD/bbl', 'gold': 'USD/oz', 'silver': 'USD/oz', 'copper': 'USD/t',
           'uran': 'USD/lb', 'brent_fut': 'USD/bbl', 'gold_fut': 'USD/oz', 'us_crude': 'mln bbl', 'us_spr': 'mln bbl', 'us_gasoline': 'mln bbl',
           'us_dist': 'mln bbl', 'us_jet': 'mln bbl', 'us_cushing': 'mln bbl', 'us_gas': 'Bcf'}


def _su_ostatni(e):
    d = e.get('d') if isinstance(e, dict) else None
    r = [x for x in d if isinstance(x, list) and len(x) == 2 and isinstance(x[1], (int, float)) and not isinstance(x[1], bool)] if isinstance(d, list) else []
    return r[-1] if r else None


def _su_handel(now):
    wd = now.weekday()
    return not (wd == 5 or (wd == 6 and now.hour < 22) or (wd == 4 and now.hour >= 22))


def surowce_swiezosc(j, now=None):
    """Wiersze świeżości części pliku surowce.json (v2) w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga).
    Najwyżej ⚠️, nigdy ❌; plik sprzed wersji 2 albo brak pliku = brak wierszy; złoto teraz — tylko w czasie handlu."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 2:
        return []
    C, Z, M = j.get('ceny') or {}, j.get('zapasy') or {}, j.get('mies') or {}
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    rows = []
    for k, label in SU_ETYKIETA.items():
        if k == 'live' and not _su_handel(now):
            continue
        if k == 'ceny':
            ls = [x for x in (_su_ostatni(C.get('brent')), _su_ostatni(C.get('wti'))) if x]
            txt, kind = (max(x[0] for x in ls), 'day') if ls else (None, None)
        elif k == 'zloto':
            x = _su_ostatni(C.get('gold')); txt, kind = (x[0], 'day') if x else (None, None)
        elif k == 'live':
            lv = (C.get('gold') or {}).get('live') if isinstance(C.get('gold'), dict) else None
            txt, kind = (lv.get('at'), 'ts') if isinstance(lv, dict) and isinstance(lv.get('at'), str) else (None, None)
        elif k == 'zapasy':
            x = _su_ostatni(Z.get('us_crude')); txt, kind = (x[0], 'day') if x else (None, None)
        elif k == 'mies':
            txt, kind = (M.get('asof'), 'month') if isinstance(M.get('asof'), str) else (None, None)
        else:
            txt, kind = (j.get('asof'), 'day') if isinstance(j.get('asof'), str) else (None, None)
        kat, prog = SU_PROG[k]
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(txt, kind, kat, now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            p = nx.get(k) if k in ('ceny', 'zapasy', 'mies', 'markets') else None   # złoto: archiwum funduszu i notowania — bez kalendarza w pliku
            pt = _aw_t(p) if isinstance(p, str) else None
            note = f'próg {fmt_wiek(prog)}' + (' (godziny robocze)' if kat == 'd' else '') + ' — najwyżej uwaga' + (
                f'; spodziewana publikacja {czas_pl(p)}' + (' — zaległa (święto albo przerwa w pracy urzędu?)' if pt and pt < now else '') if pt else '')
        rows.append((label, st, w, txt, note))
    return rows


def _su_mies_srednie(e, n=SU_MIN_SESJI):
    """Średnie miesięczne serii dziennej (tylko pełne miesiące z co najmniej n sesjami z liczbą) → {RRRR-MM: średnia}."""
    m = {}
    for x in (e.get('d') or []) if isinstance(e, dict) else []:
        if isinstance(x, list) and len(x) == 2 and isinstance(x[1], (int, float)) and not isinstance(x[1], bool):
            m.setdefault(str(x[0])[:7], []).append(x[1])
    ks = sorted(m)
    return {k: sum(v) / len(v) for k, v in m.items() if len(v) >= n and k != (ks[-1] if ks else None)}   # ostatni miesiąc pliku — niepełny


def _su_mies_wiersz(e):
    return {str(x[0]): x[1] for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[1], (int, float))} if isinstance(e, dict) else {}


def surowce_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w dziale surowce): jednostka inna niż w umowie pliku, zero zamiast braku (poza seriami
    wyliczonymi — x 'wyl'), daty nie rosną, pasmo 5 lat z min > średnia albo średnia > max. → lista opisów."""
    zle = []
    for part in ('ceny', 'zapasy'):
        for cid, e in ((j.get(part) or {}).items() if isinstance(j.get(part), dict) else ()):
            if not isinstance(e, dict):
                continue
            if cid in SU_JEDN and e.get('u') != SU_JEDN[cid]:
                zle.append(f'{part}.{cid}: jednostka {e.get("u")} zamiast {SU_JEDN[cid]}')
            d = [x for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2]
            ds = [str(x[0]) for x in d]
            if ds != sorted(set(ds)):
                zle.append(f'{part}.{cid}: daty nie rosną albo się powtarzają')
            if 'wyl' not in (e.get('x') or ()) and any(x[1] == 0 and not isinstance(x[1], bool) for x in d):   # wyliczone (marża 3:2:1, TTF) —
                zle.append(f'{part}.{cid}: wartość 0 (brak ma być null)')                                       # 0,00 możliwe, bez ❌
            for a in e.get('avg5') or []:
                if isinstance(a, list) and len(a) == 4 and all(isinstance(v, (int, float)) for v in a[1:]) and not (a[1] <= a[2] <= a[3]):
                    zle.append(f'{part}.{cid}: pasmo 5 lat {a[0]} min/średnia/max w złej kolejności'); break
    for grp in ('s', 'ix', 'k'):
        for cid, e in (((j.get('mies') or {}).get(grp) or {}).items() if isinstance((j.get('mies') or {}).get(grp), dict) else ()):
            ds = [str(x[0]) for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2] if isinstance(e, dict) else []
            if ds != sorted(set(ds)):
                zle.append(f'mies.{grp}.{cid}: miesiące nie rosną albo się powtarzają')
    return zle


def surowce_porownania(j, now=None):
    """Porównania z pliku strony (bez sieci): złoto (GLD) vs MFW, ropa EIA vs Bank Światowy, miedź MFW vs Bank Światowy (średnie miesięcy),
    plik raportu tygodniowego vs API (ten sam tydzień — identycznie), strona dzienna vs API (ten sam dzień, do 0,01 USD), średnia 5 lat gazu
    wyliczona vs EIA, Brent fizyczny vs kontrakt (zmiany dzienne) i punkty do sprawdzenia. → {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    now = now or NOW
    C, M, K = j.get('ceny') or {}, j.get('mies') or {}, j.get('kontr') or {}
    W, U = [], []

    def mies(nazwa, dz, mm, prog, zrodla):
        a, b = _su_mies_srednie(dz), _su_mies_wiersz(mm)
        wsp = sorted(set(a) & set(b))
        if not wsp:
            W.append((f'{nazwa} ({zrodla}): brak wspólnego pełnego miesiąca', 'ℹ️')); return
        k = wsp[-1]
        r = (a[k] / b[k] - 1) * 100 if b[k] else None
        if r is None:
            return
        zn = '⚠️' if abs(r) > prog else '✅'
        W.append((f'{nazwa} {k} ({zrodla}): {r:+.2f}% (próg {prog:g}%)'.replace('.', ','), zn))
        if zn == '⚠️':
            U.append(f'surowce: {nazwa} {k} — średnia miesiąca z dwóch źródeł różni się o {r:+.2f}% (próg {prog:g}% z testu wstecznego) — sprawdzić'.replace('.', ','))
    mies('złoto', C.get('gold'), (M.get('k') or {}).get('zloto_mfw'), SU_ZLOTO_PROG, 'archiwum funduszu vs MFW')
    mies('ropa Brent', C.get('brent'), (M.get('s') or {}).get('ropa_brent'), SU_ROPA_PROG, 'EIA vs Bank Światowy')
    mies('ropa WTI', C.get('wti'), (M.get('s') or {}).get('ropa_wti'), SU_ROPA_PROG, 'EIA vs Bank Światowy')
    a, b = _su_mies_wiersz((M.get('k') or {}).get('miedz_mfw')), _su_mies_wiersz((M.get('s') or {}).get('miedz'))
    wsp = sorted(set(a) & set(b))
    if wsp and b[wsp[-1]]:
        r = (a[wsp[-1]] / b[wsp[-1]] - 1) * 100
        zn = '⚠️' if abs(r) > SU_MIEDZ_PROG else '✅'
        W.append((f'miedź {wsp[-1]} (MFW vs Bank Światowy): {r:+.2f}% (próg {SU_MIEDZ_PROG:g}%)'.replace('.', ','), zn))
        if zn == '⚠️':
            U.append(f'surowce: miedź {wsp[-1]} — MFW i Bank Światowy różnią się o {r:+.2f}% (próg {SU_MIEDZ_PROG:g}%) — sprawdzić'.replace('.', ','))
    for k, nazwa, tol in (('wpsr', 'zapasy ropy i paliw: plik raportu vs API', 0.0005), ('wngsr', 'gaz w magazynach: plik raportu vs API', 0.5),
                          ('eia_dz', 'ceny: strona dzienna vs API', SU_DZ_TOL)):
        x = K.get(k) if isinstance(K.get(k), dict) else None
        if not x or not isinstance(x.get('wst'), dict) or not isinstance(x.get('api'), dict):
            continue
        rz = [(c, x['wst'][c], x['api'].get(c)) for c in sorted(x['wst']) if isinstance(x['api'].get(c), (int, float))]
        zle = [(c, p, q) for c, p, q in rz if abs(p - q) > tol]
        zn = '⚠️' if zle else '✅'
        W.append((f'{nazwa}, {x.get("d")}: porównane {len(rz)} serii' + (', różne: ' + ', '.join(f'{c} {p:g} vs {q:g}' for c, p, q in zle[:4]) if zle else ', zgodne'), zn))
        if zle:
            U.append(f'surowce: {nazwa} ({x.get("d")}) — różne liczby: ' + ', '.join(f'{c} {p:g} vs {q:g}' for c, p, q in zle[:4]))
    g = (j.get('zapasy') or {}).get('us_gas') if isinstance(j.get('zapasy'), dict) else None
    if isinstance(g, dict) and isinstance(g.get('avg5_zr'), list) and len(g['avg5_zr']) == 2:
        w, ez = g['avg5_zr']
        own = next((a5[2] for a5 in (g.get('avg5') or []) if isinstance(a5, list) and a5 and a5[0] == w), None)
        if isinstance(own, (int, float)) and isinstance(ez, (int, float)) and ez:
            W.append((f'gaz w magazynach USA, średnia 5 lat {w}: wyliczona {_zuz_l(own)} vs EIA {_zuz_l(ez)} Bcf ('
                      + f'{(own / ez - 1) * 100:+.2f}%)'.replace('.', ','), 'ℹ️'))
    wt, bk, rwa = C.get('wti'), C.get('brent_fut'), set()   # v301: kontrakt równy WTI z tego samego dnia — informacja (w regule q jak brak
    if isinstance(wt, dict) and isinstance(bk, dict):        # notowania); rwa — wszystkie takie dni (poza porównaniem zmian dziennych niżej)
        num = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool)   # noqa: E731
        wd = {x[0]: x[1] for x in (wt.get('d') or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and num(x[1])}
        rw = [(x[0], x[1]) for x in (bk.get('d') or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and num(x[1])
              and num(wd.get(x[0])) and round(abs(x[1] - wd[x[0]]), 6) < SU_FUT_WTI]
        rwa = {d for d, _ in rw}
        rn = []   # v301 (przegląd): ℹ️ tylko dla dni z ostatnich SU_Q_DNI dni (jak uwagi o punktach) — inaczej ten sam dzień codziennie przez
        for d, v in rw:   # całe okno serii (90 sesji, ok. 4 miesiące)
            try:
                if 0 <= (now.date() - dt.date.fromisoformat(d)).days <= SU_Q_DNI:
                    rn.append((d, v))
            except ValueError:
                continue
        if rn:
            W.append(((f'Brent — kontrakt równy cenie WTI z tego samego dnia: ' + ', '.join(f'{d} ({v:.2f})' for d, v in rn[-3:])
                       + (f' (razem {len(rn)} dni)' if len(rn) > 3 else '') + ' — podejrzany punkt dostawcy (zmiana miesiąca kontraktu?); '
                       'w regule punktów do sprawdzenia jak brak notowania').replace('.', ','), 'ℹ️'))
    br, bf = C.get('brent'), C.get('brent_fut')
    if isinstance(br, dict) and isinstance(bf, dict):
        # v301 (przegląd): bez — dni kontraktu równego WTI (rwa); bez zmiany do takiego dnia i z niego (podejrzany punkt nie wskaże „największej
        # różnicy”, a zmiana kontraktu z dwóch sesji nie jest porównywana z jednodniową zmianą Brenta fizycznego)
        def zm(e, bez=frozenset()):
            d = [x for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[1], (int, float)) and x[1] > 0]
            return {d[i][0]: (d[i][1] / d[i - 1][1] - 1) * 100 for i in range(1, len(d)) if not (d[i][0] in bez or d[i - 1][0] in bez)}
        a, b = zm(br), zm(bf, rwa)
        wsp = sorted(set(a) & set(b))[-30:]
        if wsp:
            mx = max(wsp, key=lambda d: abs(a[d] - b[d]))
            W.append((f'Brent dostawa fizyczna vs kontrakt, zmiany dzienne z {len(wsp)} wspólnych dni: największa różnica {mx} '
                      f'({a[mx]:+.1f}% vs {b[mx]:+.1f}%)'.replace('.', ','), 'ℹ️'))
    for cid, nazwa in (('brent', 'Brent'), ('wti', 'WTI')):
        tr, pk = [], set()   # v297g: kolejne sesje po punkcie bez potwierdzenia (wpisy q 'trwa'); v300: wszystkie (ciąg dłuższy niż SU_Q_DNI dni
                             # ma w uwadze swój początek), uwaga dla ciągu z ostatnim dniem młodszym niż SU_Q_DNI dni; pk — dni punktów bez potwierdzenia
        for q in ((C.get(cid) or {}).get('q') or []) if isinstance(C.get(cid), dict) else []:
            if not (isinstance(q, list) and len(q) == 3):
                continue
            try:
                age = (now.date() - dt.date.fromisoformat(str(q[0]))).days
            except ValueError:
                continue
            if q[2] == 'niepotw' and age >= 0:
                (tr.append if q[1] == 'trwa' else pk.add)(str(q[0]))
            if q[1] == 'trwa':
                continue
            if q[2] == 'niepotw' and 0 <= age <= SU_Q_DNI:
                U.append(f'surowce: {nazwa} {q[0]} — punkt do sprawdzenia ({"skok z odwrotem" if q[1] == "skok" else "rozjazd z drugą ropą"}), '
                         + ('kontrakt nie potwierdza ruchu' if cid == 'brent' else 'brak drugiego źródła') + ' — wartość zostaje na stronie z oznaczeniem')
        if tr:   # v300: osobna uwaga dla każdego ciągu (kolejne sesje serii); zdanie o stronie tylko dla ciągu, który trwa do ostatniej ceny
            ds = sorted({str(x[0]) for x in ((C.get(cid) or {}).get('d') or []) if isinstance(x, list) and len(x) == 2
                         and isinstance(x[1], (int, float)) and not isinstance(x[1], bool)})
            zb = sorted(set(tr) | pk)   # dni bez potwierdzenia (ciągi i punkty) — co jest po końcu ciągu
            for a, b, n, nast, ost in _su_ciagi(sorted(set(tr)), ds):
                if (now.date() - dt.date.fromisoformat(b)).days > SU_Q_DNI:
                    continue
                z = next((x for x in zb if nast and x >= nast), None)
                U.append(f'surowce: {nazwa} {a}' + (f' – {b}' if b != a else '') + f' — cena zostaje na poziomie po nietypowym ruchu ({n} ses.), '
                         + ('kontrakt tego nie potwierdza' if cid == 'brent' else 'brak drugiego źródła')
                         + (' — na stronie uwaga przy kaflu, a zmiana tygodnia jest „—”' if ost else
                            '' if not nast else
                            f' — ciąg już się skończył ({nast} — nowy punkt do sprawdzenia)' if z == nast else
                            f' — ciąg już się skończył (od {nast} cena bez oznaczenia, znów bez potwierdzenia od {z})' if z else
                            f' — ciąg już się skończył (od {nast} cena bez oznaczenia)'))
        lim = (C.get(cid) or {}).get('q_lim') if isinstance(C.get(cid), dict) else None
        if isinstance(lim, list) and len(lim) == 2 and isinstance(lim[1], int) and not isinstance(lim[1], bool):
            try:
                age = (now.date() - dt.date.fromisoformat(str(lim[0]))).days
            except ValueError:
                age = None
            if age is not None and 0 <= age <= SU_Q_DNI:   # v300: ciąg ucięty bezpiecznikiem, a cena dalej bez potwierdzenia — bez oznaczenia na stronie
                U.append(f'surowce: {nazwa} {lim[0]} — ciąg cen bez potwierdzenia doszedł do bezpiecznika ({lim[1]} sesji); dalsze sesje na nowym '
                         'poziomie są na stronie bez oznaczenia — sprawdzić ręcznie, czy cena jest prawdziwa')
    return {'wiersze': W, 'uwagi': U}


def _su_ciagi(dni, ds):
    """v300: dni z wpisem q 'trwa' (rosnąco) → ciągi kolejnych sesji serii ds (dni z ceną, rosnąco): [(pierwszy, ostatni, liczba sesji,
    następna sesja serii po ciągu albo None, czy ciąg kończy się na ostatniej cenie serii)]. Dzień spoza ds — osobny ciąg bez następnej sesji."""
    pos = {d: i for i, d in enumerate(ds)}
    G = []
    for d in dni:
        i = pos.get(d)
        if G and i is not None and G[-1][3] is not None and i == G[-1][3] + 1:
            G[-1][1], G[-1][2], G[-1][3] = d, G[-1][2] + 1, i
        else:
            G.append([d, d, 1, i])
    return [(a, b, n, ds[j + 1] if j is not None and j + 1 < len(ds) else None, j is not None and j == len(ds) - 1) for a, b, n, j in G]


def surowce_kontrola(j, R):
    """Kontrola pliku surowce.json bez sieci: sprzeczności wewnątrz pliku (❌ = BŁĄD) i porównania (najwyżej ⚠️). Brak pliku albo plik
    sprzed wersji 2 = None (raport bez linii)."""
    if not isinstance(j, dict) or j.get('v') != 2:
        return None
    zle = surowce_spojnosc(j) + surowce_spojnosc3(j)   # v298: + pozycje, fundusze, banki
    for z in zle[:5]:
        R['bledy'].append(f'surowce.json: sprzeczność w pliku — {z}')
    P = surowce_porownania(j)
    P3 = surowce_porownania3(j)   # v298: etap 3
    P = {'wiersze': P['wiersze'] + P3['wiersze'], 'uwagi': P['uwagi'] + P3['uwagi']}
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v298: surowce — etap 3 (pozycje, fundusze, banki) ----------------------------------------------------------------
# Świeżość: osobne wiersze (lista SWIEZOSC i wiersze surowce_swiezosc bez zmian), najwyżej ⚠️; banki — tylko ℹ️ (MFW publikuje kraje w różnych
# dniach i nie ma historii terminów publikacji, z której dałoby się policzyć próg — kraj starszy niż SU3_BANKI_STARE dni jest wymieniony
# w uwadze wiersza). Progi z testu wstecznego modelu kalendarza 2021 – 10.2026 (ws53/v298-dane3/bt/bt_pozycje.py; model CFTC odtwarza
# wszystkie 6 przesuniętych publikacji z harmonogramu 2026): CFTC — 12 dni dawało ⚠️ w 1,14% kontroli (poniedziałki po święcie w tygodniu
# publikacji), 13 dni — 0%; ICE (model pesymistyczny: piątek 18:45 UTC, po Wielkim Piątku wtorek) — 13 dni 0,29%, 14 dni — 0%.
# Fundusze złota — ten sam plik i próg co wiersz „złoto dziennie” (36 h robocze). ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku:
# suma pozycji grup ≠ open interest, netto lub udział niezgodne z pozycjami, tony ≠ uncje ÷ 32 150,7466 (±0,01 t), daty nie rosną, zero zamiast braku.
SU3_ETYKIETA = {'pozycje': 'surowce: pozycje funduszy — USA, 30 rynków + fundusze indeksowe + indeks (stan na wtorek, publ. w piątek)',
                'pozycje_ice': 'surowce: pozycje funduszy — Londyn (stan na wtorek, publ. w piątek)',
                'fundusze': 'surowce: złoto w funduszach (tony; po sesji w USA)',
                'banki': 'surowce: złoto banków centralnych (miesięcznie; każdy kraj ze swoim miesiącem)'}
SU3_PROG = {'pozycje': ('w', 13 * 24 * 60), 'pozycje_ice': ('w', 14 * 24 * 60), 'fundusze': ('d', 36 * 60)}
SU3_BANKI_STARE = 120   # dni od końca miesiąca danych — kraj z danymi starszymi wymieniony w uwadze wiersza banków (bez ⚠️)
SU3_OZ_T = 32150.7466   # uncji trojańskich w tonie metrycznej
SU3_NAV_PROG = 0.1      # % — wartość aktywów funduszu GLD/GLDM ÷ (uncje × cena złota z tego pliku) − 1; test wsteczny na archiwach
                        # (ws53/v298-dane3/bt/bt_fundusze.py): GLD 2005–10.2026 — 5473 dni, p99 0,056%, ponad 0,1% tylko 10.04.2026 (−0,34%);
                        # GLDM 2018–10.2026 — 2081 dni, maks. 0,023% → ⚠️ powyżej 0,1% (1 dzień na 7554 dni funduszu)
SU3_TFF_TOL = (5, 0.005)   # TFF: tolerancja sumy jak w cftc_consistent zbieracza (max 5 kontraktów, 0,5% OI)
SU3_CIT_TOL = 5            # CIT: zaokrąglenia CFTC (2026: 354 z 507 wierszy różni się o 1–2 kontrakty) — jak SU_CIT_TOL zbieracza; pozostałe — dokładnie


def surowce_swiezosc3(j, now=None):
    """Wiersze świeżości części etapu 3 (v298) w kształcie wierszy swiezosc(); tylko części obecne w pliku (plik sprzed v298 — bez wierszy)."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 2:
        return []
    rows = []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    P = j.get('pozycje') if isinstance(j.get('pozycje'), dict) else None

    def wiersz(k, txt, kind, part):
        label = SU3_ETYKIETA[k]
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); return
        kat, prog = SU3_PROG[k]
        w = wiek_danych(txt, kind, kat, now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            p = nx.get(part) if part else None
            pt = _aw_t(p) if isinstance(p, str) else None
            note = f'próg {fmt_wiek(prog)}' + (' (godziny robocze)' if kat == 'd' else '') + ' — najwyżej uwaga' + (
                f'; spodziewana publikacja {czas_pl(p)}' + (' — zaległa (święto albo przerwa w pracy urzędu?)' if pt and pt < now else '') if pt else '')
        rows.append((label, st, w, txt, note))
    if P is not None:
        cz = lambda s: P[s] if isinstance(P.get(s), dict) else {}   # noqa: E731 — v301: podczęść, która nie jest słownikiem (uszkodzony plik) = brak
        a = [max(e['asof'] for e in cz(sub).values() if isinstance(e, dict) and isinstance(e.get('asof'), str))
             for sub in ('cftc', 'cit', 'tff') if any(isinstance(e, dict) and isinstance(e.get('asof'), str) for e in cz(sub).values())]
        wiersz('pozycje', min(a) if a else None, 'day', 'pozycje')   # najstarsza z trzech części tego samego raportu CFTC — zalegająca część widać
        ice = [e['asof'] for e in cz('ice').values() if isinstance(e, dict) and isinstance(e.get('asof'), str)]
        wiersz('pozycje_ice', max(ice) if ice else None, 'day', None)
    F = j.get('fundusze') if isinstance(j.get('fundusze'), dict) else None
    if F is not None:
        g = F['f'].get('GLD') if isinstance(F.get('f'), dict) else None
        g = g if isinstance(g, dict) else {}   # v301: wpis, który nie jest słownikiem — brak
        wiersz('fundusze', g.get('asof') if isinstance(g.get('asof'), str) else None, 'day', 'fundusze')
    B = j.get('banki') if isinstance(j.get('banki'), dict) else None
    if B is not None:
        kr = {k: e for k, e in (B.get('kr') or {}).items() if isinstance(e, dict) and isinstance(e.get('asof'), str)} if isinstance(B.get('kr'), dict) else {}
        if not kr:
            rows.append((SU3_ETYKIETA['banki'], '?', None, None, 'brak danych tej części w pliku'))
        else:
            mx = max(e['asof'] for e in kr.values())
            stare = sorted((k, e['asof']) for k, e in kr.items() if (wiek_danych(e['asof'], 'month', 'm', now) or 0) > SU3_BANKI_STARE * 24 * 60)
            note = 'bez progu (MFW publikuje kraje w różnych dniach)' + (
                '; dane starsze niż ' + str(SU3_BANKI_STARE) + ' dni: ' + ', '.join(f'{k} {a}' for k, a in stare) if stare else '')
            rows.append((SU3_ETYKIETA['banki'], 'ℹ️', wiek_danych(mx, 'month', 'm', now), mx, note))
    return rows


def _su3_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def surowce_spojnosc3(j):
    """Sprzeczności wewnątrz części etapu 3 (❌): suma pozycji grup ≠ open interest (long + spread i short + spread), netto ≠ long − short grupy
    głównej, udział niezgodny z netto ÷ open interest, historia z datami nie rosnącymi albo listami różnej długości; tony ≠ ilość ÷ przelicznik
    (±0,01 t; mln funtów ±0,001), daty nie rosną, zero zamiast braku. → lista opisów."""
    zle = []
    if not isinstance(j, dict):
        return zle
    P = j.get('pozycje') if isinstance(j.get('pozycje'), dict) else {}
    glowna = {'cftc': 'mm', 'ice': 'mm', 'cit': 'cit', 'tff': 'asset_mgr'}
    for sub, gk in glowna.items():
        for k, e in ((P.get(sub) or {}).items() if isinstance(P.get(sub), dict) else ()):
            if not isinstance(e, dict):
                continue
            pos, oi = e.get('pos'), e.get('oi')
            if isinstance(pos, dict) and _su3_num(oi) and all(isinstance(x, list) and len(x) == 3 and _su3_num(x[0]) and _su3_num(x[1]) for x in pos.values()):
                L = sum(x[0] + (x[2] or 0) for x in pos.values())
                S = sum(x[1] + (x[2] or 0) for x in pos.values())
                tol = max(SU3_TFF_TOL[0], oi * SU3_TFF_TOL[1]) if sub == 'tff' else (SU3_CIT_TOL if sub == 'cit' else 0)
                if abs(L - oi) > tol or abs(S - oi) > tol:
                    zle.append(f'pozycje.{sub}.{k}: suma pozycji (long {L}, short {S}) ≠ open interest {oi}')
                g = pos.get(gk)
                if isinstance(g, list) and _su3_num(e.get('net')) and e['net'] != g[0] - g[1]:
                    zle.append(f'pozycje.{sub}.{k}: netto {e["net"]} ≠ long − short ({g[0] - g[1]})')
                if _su3_num(e.get('pct')) and _su3_num(e.get('net')) and oi and abs(e['pct'] - 100.0 * e['net'] / oi) > 0.051:
                    zle.append(f'pozycje.{sub}.{k}: udział {e["pct"]}% ≠ netto ÷ open interest')
            h = e.get('h') if isinstance(e.get('h'), dict) else {}
            ds = h.get('d') if isinstance(h.get('d'), list) else []
            if [str(x) for x in ds] != sorted(set(str(x) for x in ds)) or any(isinstance(v, list) and len(v) != len(ds) for v in h.values()):
                zle.append(f'pozycje.{sub}.{k}: historia — daty nie rosną albo listy różnej długości')
    F = j.get('fundusze') if isinstance(j.get('fundusze'), dict) else {}
    for k, e in ((F.get('f') or {}).items() if isinstance(F.get('f'), dict) else ()):
        if not isinstance(e, dict):
            continue
        d = [x for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2]
        if [str(x[0]) for x in d] != sorted(set(str(x[0]) for x in d)):
            zle.append(f'fundusze.{k}: daty nie rosną albo się powtarzają')
        if any(x[1] == 0 and _su3_num(x[1]) for x in d):
            zle.append(f'fundusze.{k}: wartość 0 (brak ma być null)')
        q, qu = e.get('q'), e.get('qu')
        if d and isinstance(q, list) and len(q) == 2 and q[0] == d[-1][0] and _su3_num(q[1]) and _su3_num(d[-1][1]):
            want = q[1] / SU3_OZ_T if qu == 'oz' else (q[1] / 1e6 if qu == 'lb' else q[1])
            if abs(d[-1][1] - want) > (0.001 if qu == 'lb' else 0.01):
                zle.append(f'fundusze.{k}: {d[-1][1]} {e.get("u")} ≠ ilość ze źródła przeliczona ({want:.3f})')
    for sid, e in ((F.get('suma') or {}).items() if isinstance(F.get('suma'), dict) else ()):
        d = [x for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2] if isinstance(e, dict) else []
        if [str(x[0]) for x in d] != sorted(set(str(x[0]) for x in d)):
            zle.append(f'fundusze.suma.{sid}: daty nie rosną albo się powtarzają')
    B = j.get('banki') if isinstance(j.get('banki'), dict) else {}
    for k, e in ((B.get('kr') or {}).items() if isinstance(B.get('kr'), dict) else ()):
        if not isinstance(e, dict):
            continue
        d = [x for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2]
        if e.get('u') != 't':
            zle.append(f'banki.{k}: jednostka {e.get("u")} zamiast t')
        if [str(x[0]) for x in d] != sorted(set(str(x[0]) for x in d)):
            zle.append(f'banki.{k}: miesiące nie rosną albo się powtarzają')
        if any(x[1] == 0 and _su3_num(x[1]) for x in d):
            zle.append(f'banki.{k}: wartość 0 (brak ma być null)')
        if d and d[-1][0] == e.get('asof') and _su3_num(e.get('oz')) and _su3_num(d[-1][1]) and abs(d[-1][1] - e['oz'] / SU3_OZ_T) > 0.01:
            zle.append(f'banki.{k}: {d[-1][1]} t ≠ uncje ÷ 32 150,7466 ({e["oz"] / SU3_OZ_T:.3f})')
    return zle


# v338 (F1Z4): złoto banków centralnych — druga tabela MFW wobec głównej i skok zapasu u kraju bez wcześniejszych ruchów.
# Skok: zmiana zapasu w ostatnim miesiącu danych kraju o ponad SU3_SKOK_T t, gdy w co najmniej SU3_SPOKOJ_N poprzednich kolejnych miesiącach (do 12)
# zapas zmieniał się najwyżej o SU3_SPOKOJ_T t (zaokrąglenia) = ⚠ „do sprawdzenia” — nie błąd (bank mógł naprawdę kupić albo sprzedać; kraj mógł też
# zmienić sposób raportowania). Test wsteczny (ws53/v338-f1z4/bt_skok.py) na historii 2016–2026 55 krajów z listy strony (6544 zmiany miesięczne,
# MFW IL RGV_REVS, nagranie 10.10.2026): reguła wskazuje 2 miesiące — Węgry III 2021 (+63,0 t, zapas 32 → 95 t: prawdziwy zakup) i Japonia III 2021
# (+80,8 t: zmiana sposobu raportowania) — ok. 0,03% miesięcy kraju. Sam próg 50 t, bez warunku „bez wcześniejszych ruchów”, wskazałby 7 miesięcy
# (w tym 4 sprzedaże Turcji i Polskę VI 2019, które mają wcześniejsze ruchy); z warunkiem próg 30 t daje 7 trafień, próg 100 t — żadnego.
SU3_SKOK_T = 50.0
SU3_SPOKOJ_T = 1.0
SU3_SPOKOJ_N = 3
SU3_TABELE_TOL = (5000, 0.001)   # uncje i ułamek — druga tabela wobec głównej w miesiącu wspólnym (zaokrąglenia drugiej: Polska do 1000 uncji, Rosja do 100 000)
SU3_TABELE_KRAJE = (('PL', 'Polska'), ('RU', 'Rosja'))
SU3_RU_ZALEGLOSC = 4   # miesięcy — o tyle ostatni odczyt Rosji może być starszy od najnowszego odczytu na liście (druga tabela MFW: zwykle 1–2 mies., IL: 10)


def _su3_mies(m):
    try:
        return int(m[:4]) * 12 + int(m[5:7])
    except (TypeError, ValueError):
        return None


def su3_skok(e):
    """(miesiąc, zmiana w t) ostatniego miesiąca kraju z wpisu banki.kr[kraj], gdy to skok u kraju bez wcześniejszych ruchów (zob. SU3_SKOK_T);
    inaczej None. Miesiące muszą być kolejne — przerwa w szeregu wśród poprzednich miesięcy = brak oceny."""
    d = [x for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and _su3_num(x[1])] if isinstance(e, dict) else []
    dz = []
    for a, b in zip(d, d[1:]):
        ma, mb = _su3_mies(a[0]), _su3_mies(b[0])
        dz.append((b[0], b[1] - a[1] if ma is not None and mb == ma + 1 else None))
    if len(dz) < SU3_SPOKOJ_N + 1 or dz[-1][1] is None or abs(dz[-1][1]) <= SU3_SKOK_T:
        return None
    wcz = [y for _, y in dz[-13:-1]]
    if len(wcz) < SU3_SPOKOJ_N or any(y is None or abs(y) > SU3_SPOKOJ_T for y in wcz):
        return None
    return dz[-1][0], dz[-1][1]


def surowce_banki_porownania(j):
    """v338 (F1Z4): wiersze porównań złota banków centralnych → ([(opis, znak)], [uwagi]): Polska i Rosja — druga tabela MFW (IRFCL) wobec głównej (IL)
    w miesiącach wspólnych (✅ zgodne, ⚠ różnica powyżej SU3_TABELE_TOL) oraz skok zapasu u kraju bez wcześniejszych ruchów (⚠ do sprawdzenia)."""
    W, U = [], []
    kr = ((j.get('banki') or {}).get('kr')) if isinstance(j, dict) and isinstance(j.get('banki'), dict) else None
    if not isinstance(kr, dict):
        return W, U
    for kod, nazwa in SU3_TABELE_KRAJE:
        e = kr.get(kod)
        k = [x for x in (e.get('kontr') or []) if isinstance(x, list) and len(x) == 3 and _su3_num(x[1]) and _su3_num(x[2])] if isinstance(e, dict) else []
        if not k:
            continue
        zle = [x for x in k if abs(x[1] - x[2]) > max(SU3_TABELE_TOL[0], SU3_TABELE_TOL[1] * x[1])]
        W.append((f'banki: {nazwa} — druga tabela MFW wobec głównej, {len(k)} wspólnych mies. (do {k[-1][0]}): '
                  + ('różne: ' + ', '.join(f'{x[0]} {x[1] / SU3_OZ_T:.1f} vs {x[2] / SU3_OZ_T:.1f} t' for x in zle[:3]) if zle else 'zgodne').replace('.', ','),
                  '\u26a0\ufe0f' if zle else '✅'))
        if zle:
            U.append(f'surowce: banki — {nazwa}: druga tabela MFW różni się od głównej w {zle[-1][0]} ({zle[-1][1] / SU3_OZ_T:.1f} vs {zle[-1][2] / SU3_OZ_T:.1f} t) '
                     '— sprawdzić, czy to zmiana skali albo rewizja danych'.replace('.', ','))
    ru = kr.get('RU')   # świeżość Rosji: druga tabela MFW zasila ją tylko, gdy przejdzie sprawdzenie skali — gdy jest stale odrzucana albo MFW jej nie publikuje,
    mr = _su3_mies(ru.get('asof')) if isinstance(ru, dict) else None   # Rosja zostaje na ostatnim odczycie (w META tylko notatka), więc liczymy zaległość wobec reszty listy
    mx = max((x for x in (_su3_mies(e.get('asof')) for e in kr.values() if isinstance(e, dict)) if x is not None), default=None)
    if mr is not None and mx is not None:
        zal = mx - mr
        ostatni = ru['asof']
        zr = 'druga tabela MFW' if ru.get('z') == 'irfcl' else 'główna tabela MFW'
        W.append((f'banki: odczyt Rosji {ostatni} ({zr}), {zal} mies. za najnowszym odczytem na liście (próg {SU3_RU_ZALEGLOSC})',
                  '\u26a0\ufe0f' if zal > SU3_RU_ZALEGLOSC else '✅'))
        if zal > SU3_RU_ZALEGLOSC:
            U.append(f'surowce: banki — Rosja: ostatni odczyt {ostatni} ({zr}), {zal} mies. za resztą listy — druga tabela MFW nie odświeża Rosji '
                     '(odrzucona przy sprawdzeniu skali albo MFW jej nie publikuje) — sprawdzić notatki zbieracza (irfcl)')
    sk = []
    for kod, e in sorted(kr.items()):
        s = su3_skok(e)
        if s:
            sk.append((kod, s[0], s[1]))
    W.append((f'banki: skok zapasu o ponad {SU3_SKOK_T:g} t w miesiącu u kraju bez wcześniejszych ruchów ({len(kr)} krajów) — '
              + (', '.join(f'{k} {m} {x:+.1f} t' for k, m, x in sk) if sk else 'brak').replace('.', ','), '\u26a0\ufe0f' if sk else '✅'))
    for k, m, x in sk:
        U.append(f'surowce: banki — {k} {m}: zapas zmienił się o {x:+.1f} t w jednym miesiącu, choć wcześniej stał w miejscu — do sprawdzenia '
                 '(prawdziwy zakup albo sprzedaż, zmiana sposobu raportowania albo zmiana skali; nie musi być błędem)'.replace('.', ','))
    return W, U


def surowce_porownania3(j):
    """Porównania etapu 3 z pliku strony (bez sieci): wartość aktywów GLD/GLDM wobec uncji × ceny (⚠️ powyżej SU3_NAV_PROG, test wsteczny
    w komentarzu stałej), złoto Chin — MFW wobec SAFE w tych samych miesiącach (ℹ️: SAFE podaje 万盎司 — zgodność do 5000 uncji; za krótka
    historia na próg ⚠️), liczba rynków w pozycjach (ℹ️). → {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    W, U = [], []
    if not isinstance(j, dict):
        return {'wiersze': W, 'uwagi': U}
    F = (j.get('fundusze') or {}).get('f') if isinstance(j.get('fundusze'), dict) else None
    for k in ('GLD', 'GLDM'):
        e = (F or {}).get(k) if isinstance(F, dict) else None
        if isinstance(e, dict) and _su3_num(e.get('nav_r')):
            r = e['nav_r']
            zn = '⚠️' if abs(r) > SU3_NAV_PROG else '✅'
            W.append((f'fundusze: {k} {e.get("asof")} — wartość aktywów ÷ (uncje × cena złota) − 1 = {r:+.3f}% (próg {SU3_NAV_PROG:g}%)'.replace('.', ','), zn))
            if zn == '⚠️':
                U.append(f'surowce: fundusz {k} {e.get("asof")} — wartość aktywów nie zgadza się z ilością złota × ceną ({r:+.3f}%) — sprawdzić archiwum funduszu'.replace('.', ','))
    g, i = ((F or {}).get('GLD') or {}) if isinstance(F, dict) else {}, ((F or {}).get('IAU') or {}) if isinstance(F, dict) else {}
    if isinstance(g.get('asof'), str) and isinstance(i.get('asof'), str) and g['asof'] > i['asof']:
        try:
            dni = (dt.date.fromisoformat(g['asof']) - dt.date.fromisoformat(i['asof'])).days
        except ValueError:
            dni = 0
        if dni > 4:   # IAU liczony z pliku funduszy strony (pamięć automatu) — dłuższa zaległość = suma złota w funduszach stoi (bez progu ⚠️)
            W.append((f'fundusze: IAU z {i["asof"]}, GLD z {g["asof"]} — suma złota w funduszach czeka na IAU ({dni} dni)', 'ℹ️'))
    cn = (((j.get('banki') or {}).get('kr') or {}).get('CN')) if isinstance(j.get('banki'), dict) and isinstance((j.get('banki') or {}).get('kr'), dict) else None
    if isinstance(cn, dict) and isinstance(cn.get('kontr'), list) and cn['kontr']:
        zle = [x for x in cn['kontr'] if isinstance(x, list) and len(x) == 3 and _su3_num(x[1]) and _su3_num(x[2]) and abs(x[1] - x[2]) > 5000]
        W.append((f'banki: Chiny — MFW vs SAFE, {len(cn["kontr"])} wspólnych mies. (do {cn["kontr"][-1][0]}): '
                  + ('różne: ' + ', '.join(f'{x[0]} {x[1] / SU3_OZ_T:.1f} vs {x[2] / SU3_OZ_T:.1f} t' for x in zle[:3]) if zle else 'zgodne')
                  .replace('.', ','), 'ℹ️'))
    Wb, Ub = surowce_banki_porownania(j)   # v338 (F1Z4): Polska i Rosja — druga tabela wobec głównej; skok zapasu u kraju bez wcześniejszych ruchów
    W += Wb
    U += Ub
    P = j.get('pozycje') if isinstance(j.get('pozycje'), dict) else None
    if P is not None:
        cz = []
        for sub, nazwa in (('cftc', 'USA'), ('ice', 'Londyn'), ('cit', 'fundusze indeksowe'), ('tff', 'indeks')):
            x = P.get(sub) if isinstance(P.get(sub), dict) else {}
            kept = [k for k, e in x.items() if isinstance(e, dict) and e.get('kept')]
            cz.append(f'{nazwa} {len(x) - len(kept)}' + (f' (+{len(kept)} z poprzedniego raportu)' if kept else ''))
        W.append(('pozycje: rynków z bieżącego raportu — ' + ', '.join(cz), 'ℹ️'))
    return {'wiersze': W, 'uwagi': U}


# ---------------------------------------------------------------- v305: szlaki handlowe i łańcuchy dostaw (data/szlaki.json) ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠️ — pole next pliku mówi, kiedy spodziewana jest publikacja.
# Progi z testu wstecznego na modelu kalendarza (ws53/v305-szlaki/bt/bt_swiezosc.py, 2021-01 – 2026-10, kontrola co godzinę): cieśniny —
# publikacja we wtorek ok. 12:10 UTC z danymi do niedzieli, najwyższy wiek 8 d 12 h (spóźnienie o dzień: 9 d 12 h) → próg 10 dni, ⚠️ 0%;
# indeks cen surowców — środa publikowana ok. tydzień później, najwyższy wiek 13 d 11 h (+2 dni: 15 d 11 h) → 16 dni, 0%; wskaźnik presji —
# 4. dzień roboczy miesiąca, najwyższy wiek 36 d 14 h (+5 dni: 41 d 14 h) → 45 dni, 0%.
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (daty nie rosną, średnia 7 dni ≠ średnia dni z wykresu, zmiana ≠ s7 / r7, tankowców
# więcej niż statków, indeks ≤ 0). Progi ⚠️ danych (bt/bt_progi.py na historii z nagrań 08.10.2026): suma statków ≠ tankowce + pozostałe —
# 0 z 22 672 wierszy 2019–2026; dzień > SZ_K_MAX statków — 0 (najwięcej 298, Malakka); wskaźnik presji |v| > SZ_K_P_MAX — 0 z 18 589 wartości
# 58 wydań (zakres −1,8 … 4,78); |zmiana m/m| > SZ_K_P_SKOK — 0 z 18 531 (najwyżej 1,70); indeks cen surowców |zmiana tygodnia| > SZ_K_B_SKOK % —
# 0 z 2855 tygodni od 1972 (najwyżej 24,95%, maj 2020). Spadki ruchu statków (np. Ormuz od 03.2026, Kanał Sueski 03.2021) to zdarzenia, nie
# błędy danych — bez progu (reguła „dzień < 25% mediany 28 dni” dawała ⚠️ w ok. 5% tygodni, prawie zawsze przy prawdziwych zdarzeniach).
SZ_K_ETYKIETA = {'cies': 'szlaki: ruch statków w 8 cieśninach (dziennie, publ. we wtorek)',
                 'presja': 'szlaki: wskaźnik presji w łańcuchach dostaw (miesięcznie, publ. ok. 4. dnia roboczego)',
                 'bcpi': 'szlaki: indeks cen surowców (tydzień do środy, publ. ok. tydzień później)'}
SZ_K_PROG = {'cies': ('w', 10 * 24 * 60), 'presja': ('m', 45 * 24 * 60), 'bcpi': ('w', 16 * 24 * 60)}
SZ_K_MAX = 500          # statków dziennie w jednej cieśninie
SZ_K_P_MAX = 6.0        # wskaźnik presji (odchylenia standardowe)
SZ_K_P_SKOK = 2.5       # zmiana wskaźnika presji miesiąc do miesiąca
SZ_K_B_SKOK = 30.0      # % — zmiana tygodniowa indeksu cen surowców (całość)
SZ_K_TOL = 0.011        # tolerancja zaokrągleń średnich (2 miejsca po przecinku) i zmiany w %
SZ_K_OPOZN = 7          # v307: dni — ostatni dzień cieśniny starszy niż najnowszy dzień części (cies.asof) o więcej = ⚠️ w wierszu świeżości
                        # (jedna cieśnina przestała się aktualizować; cies.asof = max ze wszystkich). Test wsteczny ws53/v307-drobne/bt/
                        # bt_cies_opozn.py na historii 2019-01-01 – 2026-10-04 (nagranie v305): 2804 dni i 401 paczek tygodniowych — 0 ⚠️ przy
                        # progach 3–14 dni (8 cieśnin publikowanych razem, bez luk); brak cieśniny w pliku — też ⚠️ (w historii: 0)
SZ_K_NAZWY = {'ormuz': 'Ormuz', 'bab': 'Bab el-Mandeb', 'suez': 'Kanał Sueski', 'bosfor': 'Bosfor', 'panama': 'Kanał Panamski', 'malakka': 'Malakka',
              'gibraltar': 'Gibraltar', 'przyladek': 'Przylądek Dobrej Nadziei'}


def _sz_k_wiersze(e):
    d = e.get('d') if isinstance(e, dict) else None
    return [x for x in d if isinstance(x, list) and len(x) == 2] if isinstance(d, list) else []


def _sz_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _sz_k_statki(v):
    """v307: liczba statków z rzeczownikiem po polsku — liczba całkowita: zwykła odmiana (1 statek, 2 statki, 5 statków, 12 statków,
    22 statki, 502 statki); z ułamkiem: dopełniacz liczby pojedynczej (2,7 statku)."""
    if _sz_k_num(v) and abs(v) != float('inf') and float(v) == int(v):
        return f'{int(v)} {_odm(abs(int(v)), "statek", "statki", "statków")}'
    return (f'{v:g}'.replace('.', ',') if _sz_k_num(v) else str(v)) + ' statku'


def _sz_k_dzien(s):
    """'RRRR-MM-DD…' → data; inaczej None."""
    try:
        return dt.date.fromisoformat(s[:10]) if isinstance(s, str) else None
    except ValueError:
        return None


def _sz_k_dni(a, b):
    """v307: dni od a do b ('RRRR-MM-DD'); zła data = None."""
    x, y = _sz_k_dzien(a), _sz_k_dzien(b)
    return (y - x).days if x and y else None


def _sz_k_nast_mies(a, b):
    """v307: czy miesiąc b ('RRRR-MM') jest zaraz po miesiącu a (także grudzień → styczeń)."""
    m = re.match(r'^(\d{4})-(\d{2})$', str(a)), re.match(r'^(\d{4})-(\d{2})$', str(b))
    if not (m[0] and m[1]):
        return False
    (ya, ma), (yb, mb) = (int(x) for x in m[0].groups()), (int(x) for x in m[1].groups())
    return yb * 12 + mb == ya * 12 + ma + 1


def _sz_k_opozn(C):
    """v307: cieśniny, których ostatni dzień (k.<id>.asof) jest o ponad SZ_K_OPOZN dni starszy niż najnowszy dzień części (cies.asof), bez daty
    albo nieobecne w pliku → lista opisów (pusta = wszystkie aktualne; część bez daty albo bez cieśnin — pusta, opisuje to wiersz świeżości)."""
    a = _sz_k_dzien(C.get('asof')) if isinstance(C, dict) else None
    K = C.get('k') if isinstance(C, dict) else None
    if a is None or not isinstance(K, dict) or not K:
        return []
    out = []
    for cid, nazwa in SZ_K_NAZWY.items():
        e = K.get(cid)
        d = _sz_k_dzien(e.get('asof')) if isinstance(e, dict) else None
        if not isinstance(e, dict):
            out.append(f'{nazwa} — brak w pliku')
        elif d is None:
            out.append(f'{nazwa} — brak daty ostatniego dnia')
        elif (a - d).days > SZ_K_OPOZN:
            out.append(f'{nazwa} — ostatni dzień {d.isoformat()}, {(a - d).days} dni wcześniej')
    return out


def szlaki_swiezosc(j, now=None):
    """Wiersze świeżości części pliku szlaki.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga).
    Najwyżej ⚠️, nigdy ❌; brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    rows = []
    for p, label in SZ_K_ETYKIETA.items():
        P = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = P.get('asof') if isinstance(P.get('asof'), str) else None
        kat, prog = SZ_K_PROG[p]
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(txt, 'month' if p == 'presja' else 'day', kat, now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            nt = nx.get(p); pt = _aw_t(nt) if isinstance(nt, str) else None
            note = f'próg {fmt_wiek(prog)} — najwyżej uwaga' + (
                f'; spodziewana publikacja {czas_pl(nt)}' + (' — zaległa (przerwa u źródła?)' if pt and pt < now else '') if pt else '')
        if p == 'cies' and st != '?':   # v307: jedna cieśnina w tyle (cies.asof = max ze wszystkich) — najwyżej ⚠️
            op = _sz_k_opozn(P)
            if op:
                st = '⚠️'
                note = '; '.join(x for x in (note, f'cieśniny w tyle za najnowszym dniem ({txt}): ' + ', '.join(op)
                                              + f' (próg {SZ_K_OPOZN} dni; w historii 2019–2026: 0) — najwyżej uwaga') if x)
        rows.append((label, st, w, txt, note))
    return rows


def szlaki_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w szlakach) → lista opisów."""
    zle = []
    K = ((j.get('cies') or {}).get('k') or {}) if isinstance(j.get('cies'), dict) else {}
    for cid, e in (K.items() if isinstance(K, dict) else ()):
        if not isinstance(e, dict):
            continue
        d = _sz_k_wiersze(e)
        ds = [str(x[0]) for x in d]
        if ds != sorted(set(ds)):
            zle.append(f'cies.{SZ_K_NAZWY.get(cid, cid)}: daty nie rosną albo się powtarzają')
        if any(x[1] is not None and not (_sz_k_num(x[1]) and x[1] >= 0) for x in d):
            zle.append(f'cies.{SZ_K_NAZWY.get(cid, cid)}: liczba statków ujemna albo nie-liczba')
        s7, t7, r7, chg, ok = e.get('s7'), e.get('t7'), e.get('r7'), e.get('chg'), e.get('okno')
        if _sz_k_num(s7) and isinstance(ok, list) and len(ok) == 2:
            V = [x[1] for x in d if ok[0] <= str(x[0]) <= ok[1]]
            if len(V) == 7 and all(_sz_k_num(v) for v in V) and abs(sum(V) / 7 - s7) > SZ_K_TOL:
                zle.append(f'cies.{SZ_K_NAZWY.get(cid, cid)}: średnia 7 dni {s7} ≠ średnia dni z wykresu {sum(V) / 7:.2f}')
        if _sz_k_num(s7) and _sz_k_num(t7) and t7 > s7 + SZ_K_TOL:
            zle.append(f'cies.{SZ_K_NAZWY.get(cid, cid)}: tankowców ({t7}) więcej niż wszystkich statków ({s7})')
        if _sz_k_num(chg) and _sz_k_num(s7) and _sz_k_num(r7) and r7 > 0 and abs((s7 / r7 - 1) * 100 - chg) > SZ_K_TOL:
            zle.append(f'cies.{SZ_K_NAZWY.get(cid, cid)}: zmiana {chg}% ≠ {(s7 / r7 - 1) * 100:.2f}% z s7 / r7')
    P = j.get('presja') if isinstance(j.get('presja'), dict) else {}
    ms = [str(x[0]) for x in _sz_k_wiersze(P)]
    if ms != sorted(set(ms)):
        zle.append('presja: miesiące nie rosną albo się powtarzają')
    S = ((j.get('bcpi') or {}).get('s') or {}) if isinstance(j.get('bcpi'), dict) else {}
    for cid, e in (S.items() if isinstance(S, dict) else ()):
        d = _sz_k_wiersze(e)
        ds = [str(x[0]) for x in d]
        if ds != sorted(set(ds)):
            zle.append(f'bcpi.{cid}: daty nie rosną albo się powtarzają')
        if any(x[1] is not None and not (_sz_k_num(x[1]) and x[1] > 0) for x in d):
            zle.append(f'bcpi.{cid}: wartość ≤ 0 albo nie-liczba (brak ma być null)')
    return zle


def szlaki_porownania(j):
    """Progi z testów wstecznych (najwyżej ⚠️): sumy statków u źródła, zakres liczby statków, skoki wskaźnika presji i indeksu cen surowców.
    → {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    W, U = [], []
    C = j.get('cies') if isinstance(j.get('cies'), dict) else {}
    K = C.get('k') if isinstance(C.get('k'), dict) else {}
    if K:
        nz = C.get('nz')
        duze = [(cid, x[0], x[1]) for cid, e in K.items() if isinstance(e, dict) for x in _sz_k_wiersze(e) if _sz_k_num(x[1]) and x[1] > SZ_K_MAX]
        if _sz_k_num(nz) and nz > 0:
            U.append(f'szlaki: {int(nz)} {_odm(int(nz), "wiersz", "wiersze", "wierszy")} źródła z sumą statków ≠ tankowce + pozostałe — sprawdzić '
                     f'(w historii 2019–2026: 0)')   # v307: odmiana
        for cid, d, v in duze[:3]:
            U.append(f'szlaki: {SZ_K_NAZWY.get(cid, cid)} {d} — {_sz_k_statki(v)} w jednym dniu (próg {SZ_K_MAX}; w historii najwyżej 298) — sprawdzić')
        W.append(('cieśniny: sumy i zakres', '⚠️' if (_sz_k_num(nz) and nz > 0) or duze else '✅'))
    P = _sz_k_wiersze(j.get('presja'))
    V = [(str(m), v) for m, v in P if _sz_k_num(v)]
    if V:
        zle = [(m, v) for m, v in V if abs(v) > SZ_K_P_MAX]
        sk = [(b[0], b[1] - a[1]) for a, b in zip(V, V[1:]) if _sz_k_nast_mies(a[0], b[0]) and abs(b[1] - a[1]) > SZ_K_P_SKOK]   # v307: sąsiednie miesiące
        for m, v in zle[:2]:
            U.append(f'szlaki: wskaźnik presji {m} = {v:+.2f} — poza zakresem ±{SZ_K_P_MAX:g} (w historii −1,8 … 4,78) — sprawdzić'.replace('.', ','))
        for m, c in sk[:2]:
            U.append(f'szlaki: wskaźnik presji {m} — zmiana o {c:+.2f} w miesiąc (próg {SZ_K_P_SKOK:g}; w historii najwyżej 1,70) — sprawdzić'.replace('.', ','))
        W.append(('wskaźnik presji: zakres i skoki', '⚠️' if zle or sk else '✅'))
    B = _sz_k_wiersze(((j.get('bcpi') or {}).get('s') or {}).get('calosc') if isinstance(j.get('bcpi'), dict) else None)
    V = [(str(d), v) for d, v in B if _sz_k_num(v) and v > 0]
    if V:
        sk = [(b[0], (b[1] / a[1] - 1) * 100) for a, b in zip(V, V[1:])
              if _sz_k_dni(a[0], b[0]) == 7 and abs(b[1] / a[1] - 1) * 100 > SZ_K_B_SKOK]   # v307: tylko tydzień dokładnie sprzed 7 dni (luka ≠ skok)
        for d, c in sk[:2]:
            U.append(f'szlaki: indeks cen surowców {d} — zmiana o {c:+.1f}% w tydzień (próg {SZ_K_B_SKOK:g}%; od 1972 najwyżej 24,95%) — sprawdzić'.replace('.', ','))
        W.append(('indeks cen surowców: skoki tygodniowe', '⚠️' if sk else '✅'))
    return {'wiersze': W, 'uwagi': U}


def szlaki_kontrola(j, R):
    """Kontrola pliku szlaki.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i progi z testów wstecznych (najwyżej ⚠️). Brak pliku albo inna
    wersja = None (raport bez linii)."""
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = szlaki_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'szlaki.json: sprzeczność w pliku — {z}')
    P = szlaki_porownania(j)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v340: gaz i LNG (data/lng.json) ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠️ — pole next pliku mówi, kiedy spodziewana jest zmiana.
# Progi z testu wstecznego (ws53/v340-lng/bt/, historia 2023-01-01 – 2026-10-10: 1379 dób, 30 punktów wejścia, nagrania 11.10.2026):
# * (kategoria 'w' — wiek kalendarzowy: gaz płynie, a dane powstają także w soboty i niedziele)
# * Świnoujście: wynik doby D pojawia się ok. 07:03 czasu polskiego dnia D+1 (wiek doby na koniec jej ostatniego dnia: 7 h – 31 h); w historii 0 braków
#   doby z 1379 → próg 3 dni (plan F5Z1: „Świnoujście bez danych 3 dni = ostrzeżenie”), ⚠️ także przy 3 i więcej brakach doby w ostatnich 30 dniach;
# * terminale UE razem: doba kompletna, gdy raportują wszyscy operatorzy (ostatni ok. 19:56 czasu polskiego dnia D+1) → zwykły wiek ostatniej doby
#   do ok. 43 h; w historii 23 niekompletne doby z 1379, najwyżej 2 kolejne → najgorszy wiek ok. 91 h < próg 5 dni (⚠️ 0%); braki doby UE w oknie
#   30 dni: najwięcej 2 → ⚠️ powyżej 5;
# * dane miesięczne urzędowej statystyki: rozporządzenie wymaga danych w 2 miesiące po miesiącu, agregat UE27 pojawia się później od krajów
#   (10.10.2026: UE27 do lipca = 70 dni od końca miesiąca, Polska do sierpnia = 40 dni) → próg 120 dni dla UE27 i 90 dni dla Polski.
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (daty nie rosną, suma UE < Świnoujście w tej samej dobie, suma terminali ≠ suma UE, hist ≠ d,
# pasmo poza porządkiem, suma partnerów ≠ suma importu, mln m³ niezgodne z TJ). Progi ⚠️ danych (test wsteczny na 1379 dobach): suma UE poza
# [800, 8000] GWh/d (w historii 1 914 – 4 919), skok sumy UE o ponad 60% z doby na dobę (w historii −23% … +39%, 0 z 1366), Świnoujście ponad
# 600 GWh/d (w historii do 272; zmiany doba do doby bez progu — wyłączenia terminalu to zdarzenia: min 0, skok z 0); suma dób miesiąca terminali UE
# wobec importu UE27 z miesięcznej statystyki poza [0,60; 1,10] (w historii 43 miesiące: 0,742 – 0,976, średnio 0,85 — Dunkierka nie publikuje
# tych danych), Świnoujście wobec importu Polski poza [0,60; 1,40] (w historii 0,753 – 1,244). Porównanie tylko dla miesięcy z kompletnymi
# dobami (brak najwyżej 3 dób — średnia z dostępnych).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'lng')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['lng'] = 26 * 60
AW_BEZ_BLEDU.update({'lng_' + p: 'gaz i LNG — część z błędem zostaje z datą (v340); wiek danych w wierszach świeżości' for p in ('dz', 'skad', 'zapasy')})
LNG_K_ETYKIETA = {'pl': 'gaz i LNG: Świnoujście, dobowa wysyłka z terminalu (doba gazowa)',
                  'ue': 'gaz i LNG: terminale UE razem, dobowa wysyłka (doba kompletna)',
                  'skad': 'gaz i LNG: import LNG do UE27 wg pochodzenia (miesięcznie)',
                  'skad_pl': 'gaz i LNG: import LNG do Polski (miesięcznie)',
                  'zap': 'gaz i LNG: zapasy gazu w magazynach UE27 (miesięcznie)',
                  'zap_pl': 'gaz i LNG: zapasy gazu w magazynach Polski (miesięcznie)'}
LNG_K_PROG = {'pl': ('w', 3 * 1440), 'ue': ('w', 5 * 1440), 'skad': ('m', 120 * 1440), 'skad_pl': ('m', 90 * 1440), 'zap': ('m', 120 * 1440), 'zap_pl': ('m', 90 * 1440)}
LNG_K_UE_MIN, LNG_K_UE_MAX = 800.0, 8000.0   # GWh/d — suma UE
LNG_K_UE_SKOK = 60.0                         # % — zmiana sumy UE z doby na dobę
LNG_K_PL_MAX = 600.0                         # GWh/d — Świnoujście
LNG_K_BRAKI_UE, LNG_K_BRAKI_PL = 5, 2        # dób bez wartości w ostatnich 30 dniach: ⚠️ powyżej (UE) / od 3 (PL)
LNG_K_RAZEM = (0.60, 1.10)                   # suma dób miesiąca (GWh × 3,6 = TJ) wobec importu UE27
LNG_K_RAZEM_PL = (0.60, 1.40)                # … Świnoujście wobec importu Polski
LNG_K_TOL = 0.06                             # GWh — zaokrąglenia do 0,1


def _lng_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))


def _lng_k_wiersze(e):
    d = e.get('d') if isinstance(e, dict) else None
    return [x for x in d if isinstance(x, list) and len(x) >= 2] if isinstance(d, list) else []


def lng_swiezosc(j, now=None):
    """Wiersze świeżości części pliku lng.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️, nigdy ❌;
    brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?'. Dla dz: dodatkowo ⚠️ przy brakach dób w ostatnich 30 dniach."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    dz, sk, zp = (j.get(p) if isinstance(j.get(p), dict) else {} for p in ('dz', 'skad', 'zapasy'))
    zrodlo = {'pl': ((dz.get('pl') or {}).get('asof'), 'dz', 'day'), 'ue': ((dz.get('ue') or {}).get('asof'), 'dz', 'day'),
              'skad': ((sk.get('ue') or {}).get('m'), 'skad', 'month'), 'skad_pl': ((sk.get('pl') or {}).get('m'), 'skad', 'month'),
              'zap': ((((zp.get('k') or {}).get('EU27_2020') or {}).get('m')), 'zapasy', 'month'),
              'zap_pl': ((((zp.get('k') or {}).get('PL') or {}).get('m')), 'zapasy', 'month')}
    rows = []
    for p, label in LNG_K_ETYKIETA.items():
        txt, czesc, kind = zrodlo[p]
        kat, prog = LNG_K_PROG[p]
        if not isinstance(txt, str) or not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(txt, kind, kat, now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            nt = nx.get(czesc); pt = _aw_t(nt) if isinstance(nt, str) else None
            note = f'próg {fmt_wiek(prog)} — najwyżej uwaga' + (
                f'; spodziewana zmiana {czas_pl(nt)}' + (' — zaległa (przerwa u źródła?)' if pt and pt < now else '') if pt else '')
        if p in ('pl', 'ue') and st != '?':   # braki dób w ostatnich 30 dniach wykresu
            V = [x[1] for x in _lng_k_wiersze(dz.get(p))][-30:]
            n = sum(1 for v in V if v is None)
            lim = LNG_K_BRAKI_PL if p == 'pl' else LNG_K_BRAKI_UE
            if len(V) >= 30 and n > lim:
                st = '⚠️'
                note = '; '.join(x for x in (note, f'{n} z ostatnich 30 dób bez wartości (próg {lim}; w historii 2023–2026 najwyżej {0 if p == "pl" else 2}) — najwyżej uwaga') if x)
        rows.append((label, st, w, txt, note))
    return rows


def lng_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w gazie i LNG) → lista opisów."""
    zle = []
    dz = j.get('dz') if isinstance(j.get('dz'), dict) else {}
    S = {}
    for p in ('pl', 'ue'):
        e = dz.get(p) if isinstance(dz.get(p), dict) else None
        if e is None:
            continue
        R = _lng_k_wiersze(e)
        ds = [str(x[0]) for x in R]
        if ds != sorted(set(ds)):
            zle.append(f'dz.{p}: doby nie rosną albo się powtarzają')
        if any(x[1] is not None and not (_lng_k_num(x[1]) and x[1] >= 0) for x in R):
            zle.append(f'dz.{p}: wartość ujemna albo nie-liczba (brak ma być null)')
        S[p] = {str(x[0]): x[1] for x in R if _lng_k_num(x[1])}
        if R and e.get('asof') != R[-1][0]:
            zle.append(f'dz.{p}: asof {e.get("asof")} ≠ ostatnia doba wykresu {R[-1][0]}')
        pas = e.get('pasmo')
        if pas is not None:
            for x in (pas if isinstance(pas, list) else [None]):
                if not (isinstance(x, list) and len(x) == 4 and all(_lng_k_num(v) for v in x[1:]) and x[1] <= x[2] <= x[3] and str(x[0]) in {*ds}):
                    zle.append(f'dz.{p}: pasmo poza porządkiem (najmniej ≤ mediana ≤ najwięcej) albo doba spoza wykresu'); break
    for d, u in (S.get('ue') or {}).items():
        v = (S.get('pl') or {}).get(d)
        if v is not None and u < v - LNG_K_TOL:
            zle.append(f'dz: suma terminali UE ({u}) mniejsza niż Świnoujście ({v}) w dobie {d}'); break
    T = dz.get('term') if isinstance(dz.get('term'), dict) else None
    if T is not None:
        rows = [r for r in (T.get('r') or []) if isinstance(r, list) and len(r) == 3 and _lng_k_num(r[2])]
        s = sum(r[2] for r in rows)
        u = (S.get('ue') or {}).get(T.get('d'))
        if u is not None and abs(s - u) > 0.05 * (len(rows) + 1) + 0.01:
            zle.append(f'dz.term: suma terminali {s:.1f} ≠ suma UE {u} w dobie {T.get("d")}')
        pw = [r[2] for r in rows if r[0] == 'Świnoujście']
        v = (S.get('pl') or {}).get(T.get('d'))
        if pw and v is not None and abs(pw[0] - v) > LNG_K_TOL:
            zle.append(f'dz.term: Świnoujście {pw[0]} ≠ {v} w dobie {T.get("d")}')
    h = dz.get('hist') if isinstance(dz.get('hist'), dict) else None
    if h is not None:
        if not (isinstance(h.get('pl'), list) and isinstance(h.get('ue'), list) and len(h['pl']) == len(h['ue'])):
            zle.append('dz.hist: serie różnej długości')
        else:
            d0 = _sz_k_dzien(h.get('od'))
            for p in ('pl', 'ue'):
                for d, v in (S.get(p) or {}).items():
                    dd = _sz_k_dzien(d)
                    i = (dd - d0).days if dd and d0 else -1
                    if not (0 <= i < len(h[p])) or not _lng_k_num(h[p][i]) or abs(h[p][i] - v) > LNG_K_TOL:
                        zle.append(f'dz.hist: {p} {d} ≠ wykres'); break
                else:
                    continue
                break
    sk = j.get('skad') if isinstance(j.get('skad'), dict) else {}
    for g in ('ue', 'pl'):
        e = sk.get(g) if isinstance(sk.get(g), dict) else None
        if e is None:
            continue
        K = [x for x in (e.get('k') or []) if isinstance(x, list) and len(x) == 2 and _lng_k_num(x[1])]
        if _lng_k_num(e.get('razem')) and sum(x[1] for x in K) > e['razem'] * 1.03:
            zle.append(f'skad.{g}: suma partnerów {sum(x[1] for x in K):.0f} większa niż suma importu {e["razem"]}')
        H = [x for x in (e.get('hist') or []) if isinstance(x, list) and len(x) == 2]
        if H and (H[-1][0] != e.get('m') or H[-1][1] != e.get('razem')):
            zle.append(f'skad.{g}: ostatni miesiąc szeregu ≠ miesiąc i suma importu')
    zp = ((j.get('zapasy') or {}).get('k') or {}) if isinstance(j.get('zapasy'), dict) else {}
    for g, e in (zp.items() if isinstance(zp, dict) else ()):
        R = _lng_k_wiersze(e)
        ms = [str(x[0]) for x in R]
        if ms != sorted(set(ms)):
            zle.append(f'zapasy.{g}: miesiące nie rosną albo się powtarzają')
        for x in R:
            if len(x) >= 3 and _lng_k_num(x[1]) and _lng_k_num(x[2]) and not 30 <= x[1] / x[2] <= 45:
                zle.append(f'zapasy.{g} {x[0]}: TJ / mln m³ = {x[1] / x[2]:.1f} poza 30–45'); break
        if R and e.get('m') != R[-1][0]:
            zle.append(f'zapasy.{g}: m {e.get("m")} ≠ ostatni miesiąc szeregu {R[-1][0]}')
    return zle


def _lng_k_razem(H, d0, miesiace):
    """Sumy dób miesiąca terminali (GWh) przeliczone na TJ (× 3,6), wobec importu miesiąca: [(miesiąc, stosunek)] dla miesięcy z co najwyżej 3 brakami."""
    out = []
    for m, tj in miesiace:
        if not (_lng_k_num(tj) and tj > 0 and re.match(r'^\d{4}-\d{2}$', str(m))):
            continue
        y, mo = int(m[:4]), int(m[5:7])
        n = (dt.date(y + (mo == 12), mo % 12 + 1, 1) - dt.date(y, mo, 1)).days
        V = []
        for k in range(n):
            i = (dt.date(y, mo, 1) + dt.timedelta(days=k) - d0).days
            if 0 <= i < len(H) and _lng_k_num(H[i]):
                V.append(H[i])
        if len(V) >= n - 3 and V:
            out.append((str(m), sum(V) / len(V) * n * 3.6 / tj))
    return out


def lng_porownania(j):
    """Progi z testów wstecznych (najwyżej ⚠️): zakres i skoki sumy UE, Świnoujście, suma dób miesiąca wobec importu miesięcznej statystyki.
    → {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    W, U = [], []
    dz = j.get('dz') if isinstance(j.get('dz'), dict) else {}
    ue = [(str(x[0]), x[1]) for x in _lng_k_wiersze(dz.get('ue')) if _lng_k_num(x[1])]
    pl = [(str(x[0]), x[1]) for x in _lng_k_wiersze(dz.get('pl')) if _lng_k_num(x[1])]
    if ue:
        poza = [(d, v) for d, v in ue if not LNG_K_UE_MIN <= v <= LNG_K_UE_MAX]
        sk = [(b[0], (b[1] / a[1] - 1) * 100) for a, b in zip(ue, ue[1:]) if a[1] > 0 and _sz_k_dni(a[0], b[0]) == 1 and abs(b[1] / a[1] - 1) * 100 > LNG_K_UE_SKOK]
        for d, v in poza[:2]:
            U.append(f'gaz i LNG: terminale UE razem {d} = {v:.0f} GWh/d — poza zakresem {LNG_K_UE_MIN:.0f}–{LNG_K_UE_MAX:.0f} (w historii 1 914–4 919) — sprawdzić')
        for d, c in sk[:2]:
            U.append(f'gaz i LNG: terminale UE razem {d} — zmiana o {c:+.0f}% z doby na dobę (próg {LNG_K_UE_SKOK:.0f}%; w historii −23% … +39%) — sprawdzić'.replace('.', ','))
        W.append(('terminale UE: zakres i skoki dobowe', '⚠️' if poza or sk else '✅'))
    if pl:
        duze = [(d, v) for d, v in pl if v > LNG_K_PL_MAX]
        for d, v in duze[:2]:
            U.append(f'gaz i LNG: Świnoujście {d} = {v:.0f} GWh/d — powyżej {LNG_K_PL_MAX:.0f} (w historii najwyżej 272) — sprawdzić')
        W.append(('Świnoujście: zakres', '⚠️' if duze else '✅'))
    h = dz.get('hist') if isinstance(dz.get('hist'), dict) else None
    d0 = _sz_k_dzien(h.get('od')) if h else None
    sk_ = j.get('skad') if isinstance(j.get('skad'), dict) else {}
    for nm, g, lim, etyk in (('ue', 'ue', LNG_K_RAZEM, 'terminale UE razem wobec importu UE27'), ('pl', 'pl', LNG_K_RAZEM_PL, 'Świnoujście wobec importu Polski')):
        H = h.get(nm) if h else None
        e = sk_.get(g) if isinstance(sk_.get(g), dict) else None
        if not (d0 and isinstance(H, list) and e and isinstance(e.get('hist'), list)):
            continue
        R = _lng_k_razem(H, d0, [(x[0], x[1]) for x in e['hist'] if isinstance(x, list) and len(x) == 2])
        if not R:
            continue
        zle = [(m, r) for m, r in R if not lim[0] <= r <= lim[1]]
        for m, r in zle[:2]:
            U.append(f'gaz i LNG: {etyk}, {m}: stosunek {r:.2f} poza przedziałem {lim[0]:.2f}–{lim[1]:.2f} (w historii 2023–2026: '
                     f'{"0,74–0,98" if nm == "ue" else "0,75–1,24"}; to rząd wielkości, nie rozliczenie) — sprawdzić'.replace('.', ','))
        W.append((f'suma dób miesiąca: {etyk}', '⚠️' if zle else '✅'))
    return {'wiersze': W, 'uwagi': U}


def lng_kontrola(j, R):
    """Kontrola pliku lng.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i progi z testów wstecznych (najwyżej ⚠️). Brak pliku albo inna wersja =
    None (raport bez linii)."""
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = lng_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'lng.json: sprzeczność w pliku — {z}')
    P = lng_porownania(j)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v353: Rosja (data/rosja.json) ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠️ — pole next pliku mówi, kiedy spodziewana jest zmiana. Progi wieku danych
# (dni od końca miesiąca albo kwartału danych) z obserwacji na nagraniach 11.10.2026 + zapas: handel UE (publikacja ok. 15. dnia, dane sprzed 2 miesięcy:
# 15.09.2026 lipiec = 46 dni; najstarszy wiek tuż przed kolejną publikacją ok. 76 dni) → próg 95 dni; handel Rosji (MFW): 11.10.2026 czerwiec = 103 dni
# → próg 150 dni; należności banków (kwartalnie): 11.10.2026 pierwszy kwartał = 194 dni → próg 240 dni; rezerwy Rosji w MFW: 11.10.2026 listopad 2025 = 315 dni
# (Rosja publikuje tam z dużym opóźnieniem) → próg 400 dni; złoto w tonach (kopia z pliku surowce): 11.10.2026 sierpień = 41 dni → próg 90 dni.
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (saldo ≠ eksport − import, szereg nie kończy się na ostatnim okresie, kolejność kwartałów, kraje
# razem większe niż suma wszystkich, UE większe niż świat, złoto w rezerwach większe niż całość…). Porównania danych (najwyżej ⚠️, ℹ️):
# (1) import UE z Rosji (statystyka UE, mln EUR) a eksport Rosji do UE (dane zgłoszone przez Rosję, MFW, mld USD) w tym samym miesiącu: iloraz USD/EUR
#     w 13 miesiącach z nagrania 11.10.2026: 1,003 – 1,074 → pasmo ⚠️ [0,80; 1,35] (kurs euro plus różnice terminów); (2) eksport UE do Rosji a import Rosji
#     z UE: iloraz 2,26 – 3,62 (znana duża różnica metod: kraj pochodzenia a wysyłki, ceny CIF i FOB, przesyłki przez kraje trzecie) → tylko ℹ️, ⚠️ poza
#     [1,2; 6,0]; (3) cena uncji wynikająca z wartości złota w rezerwach (MFW) i tonażu z pliku surowce w tym samym miesiącu poza [500; 20 000] USD = ⚠️
#     (listopad 2025: ok. 4 190 USD); (4) kopia złota w rosja.json starsza niż źródło w surowce.json albo z inną wartością = ⚠️.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'rosja')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['rosja'] = 30 * 60
AW_BEZ_BLEDU.update({k: 'Rosja — część z błędem zostaje z datą (v353); wiek danych w wierszach świeżości' for k in ('rosja', 'rosja_ue', 'rosja_bis', 'rosja_imts', 'rosja_rez')})
RU_K_ETYKIETA = {'ue': 'Rosja: handel UE z Rosją (miesięcznie)', 'bis': 'Rosja: należności banków świata (kwartalnie)',
                 'imts': 'Rosja: handel Rosji wg partnerów (miesięcznie)', 'rez': 'Rosja: rezerwy walutowe (miesięcznie)',
                 'zloto': 'Rosja: złoto banku centralnego w tonach (miesięcznie)'}
RU_K_PROG_DNI = {'ue': 95, 'bis': 240, 'imts': 150, 'rez': 400, 'zloto': 90}
RU_K_IMP_PASMO = (0.80, 1.35)    # eksport Rosji do UE (mld USD × 1000) / import UE z Rosji (mln EUR)
RU_K_EKSP_PASMO = (1.2, 6.0)     # import Rosji z UE / eksport UE do Rosji — znana duża różnica metod, tylko ostrzeżenie poza pasmem
RU_K_CENA_PASMO = (500.0, 20000.0)   # USD za uncję trojańską
RU_K_UNCJA_T = 32150.7466        # uncji trojańskich w tonie


def _ru_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))


def _ru_k_f(x, d=2):
    return f'{x:.{d}f}'.replace('.', ',')


def _ru_k_mies(txt):
    """'RRRR-MM' → ten sam; 'RRRR-Qn' → ostatni miesiąc kwartału; inny zapis → None."""
    s = str(txt or '')
    if re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', s):
        return s
    m = re.fullmatch(r'(\d{4})-Q([1-4])', s)
    return f'{m.group(1)}-{int(m.group(2)) * 3:02d}' if m else None


def rosja_swiezosc(j, now=None):
    """Wiersze świeżości części pliku rosja.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️, nigdy ❌;
    brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    rows = []
    for p, label in RU_K_ETYKIETA.items():
        e = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = e.get('asof')
        mm = _ru_k_mies(txt)
        if mm is None:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(mm, 'month', 'm', now)
        prog = RU_K_PROG_DNI[p] * 1440
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            nt = nx.get(p); pt = _aw_t(nt) if isinstance(nt, str) else None
            note = f'próg {fmt_wiek(prog)} — najwyżej uwaga' + (
                f'; spodziewana zmiana {czas_pl(nt)}' + (' — zaległa (przerwa u źródła?)' if pt and pt < now else '') if pt else '')
        rows.append((label, st, w, str(txt), note))
    return rows


def rosja_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w danych o Rosji) → lista opisów."""
    zle = []
    U = j.get('ue') if isinstance(j.get('ue'), dict) else None
    if U:
        h = U.get('h') if isinstance(U.get('h'), list) else []
        ms = [str(x[0]) for x in h if isinstance(x, list) and len(x) == 3]
        if ms != sorted(set(ms)):
            zle.append('ue.h: miesiące nie rosną albo się powtarzają')
        if h and (not isinstance(h[-1], list) or h[-1][0] != U.get('asof')):
            zle.append(f'ue: asof {U.get("asof")} ≠ ostatni miesiąc szeregu')
        if any(not (_ru_k_num(x[1]) and _ru_k_num(x[2]) and x[1] >= 0 and x[2] >= 0) for x in h if isinstance(x, list) and len(x) == 3):
            zle.append('ue.h: wartość ujemna albo nie-liczba')
        if all(_ru_k_num(U.get(k)) for k in ('imp', 'exp', 'bal')) and abs(U['bal'] - (U['exp'] - U['imp'])) > 0.25:
            zle.append(f'ue: saldo {U["bal"]} ≠ eksport − import {round(U["exp"] - U["imp"], 1)} mln EUR')
        if h and isinstance(h[-1], list) and len(h[-1]) == 3 and _ru_k_num(U.get('imp')) and (h[-1][1] != U['imp'] or h[-1][2] != U['exp']):
            zle.append('ue: import/eksport ≠ ostatni wiersz szeregu')
    B = j.get('bis') if isinstance(j.get('bis'), dict) else None
    if B:
        R = [x for x in (B.get('razem') or []) if isinstance(x, list) and len(x) >= 2]
        qs = [str(x[0]) for x in R]
        if qs != sorted(set(qs)) or not all(re.fullmatch(r'\d{4}-Q[1-4]', q) for q in qs):
            zle.append('bis.razem: kwartały nie rosną albo mają zły zapis')
        if R and (R[-1][0] != B.get('asof')):
            zle.append(f'bis: asof {B.get("asof")} ≠ ostatni kwartał szeregu')
        if any(not (_ru_k_num(x[1]) and x[1] >= 0) for x in R):
            zle.append('bis.razem: wartość ujemna albo nie-liczba')
        T = [x for x in (B.get('top') or []) if isinstance(x, list) and len(x) >= 2]
        if [x[1] for x in T] != sorted((x[1] for x in T), reverse=True):
            zle.append('bis.top: kraje nie są posortowane malejąco')
        if R and T and _ru_k_num(R[-1][1]) and sum(x[1] for x in T if _ru_k_num(x[1])) > R[-1][1] * 1.02:
            zle.append('bis: suma największych krajów większa niż suma wszystkich krajów raportujących')
    I = j.get('imts') if isinstance(j.get('imts'), dict) else None
    if I and isinstance(I.get('p'), dict):
        P = I['p']
        for k, p in P.items():
            if not isinstance(p, dict) or not all(_ru_k_num(p.get(f)) for f in ('x', 'm', 'b')):
                zle.append(f'imts.{k}: brak eksportu, importu albo salda'); continue
            if abs(p['b'] - (p['x'] - p['m'])) > 0.005:
                zle.append(f'imts.{k}: saldo {p["b"]} ≠ eksport − import {round(p["x"] - p["m"], 3)} mld USD')
            if isinstance(p.get('h'), list) and p['h'] and (p['h'][-1][0] != I.get('asof') or p['h'][-1][1] != p['x'] or p['h'][-1][2] != p['m']):
                zle.append(f'imts.{k}: ostatni wiersz szeregu ≠ eksport/import')
        w = P.get('G001')
        if isinstance(w, dict) and _ru_k_num(w.get('x')) and _ru_k_num(w.get('m')):
            for k, p in P.items():
                if k != 'G001' and isinstance(p, dict) and _ru_k_num(p.get('x')) and _ru_k_num(p.get('m')) and (p['x'] > w['x'] + 0.01 or p['m'] > w['m'] + 0.01):
                    zle.append(f'imts.{k}: wartość większa niż świata razem')
    Z = j.get('rez') if isinstance(j.get('rez'), dict) else None
    if Z and all(_ru_k_num(Z.get(k)) for k in ('razem', 'bez_zlota')):
        if Z['bez_zlota'] > Z['razem'] + 0.05:
            zle.append('rez: rezerwy bez złota większe niż rezerwy razem')
        if _ru_k_num(Z.get('waluty')) and Z['waluty'] > Z['bez_zlota'] + 0.05:
            zle.append('rez: waluty obce większe niż rezerwy bez złota')
        if _ru_k_num(Z.get('zloto_war')) and abs(Z['zloto_war'] - (Z['razem'] - Z['bez_zlota'])) > 0.15:
            zle.append('rez: złoto ≠ razem − bez złota')
    G = j.get('zloto') if isinstance(j.get('zloto'), dict) else None
    if G and not (_ru_k_num(G.get('t')) and 100 <= G['t'] <= 20000 and _ru_k_mies(G.get('asof'))):
        zle.append('zloto: tonaż poza zakresem albo zły miesiąc')
    return zle


def rosja_porownania(j, files):
    """Porównania z innymi danymi i z drugim źródłem (najwyżej ⚠️): {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    wier, uw = [], []
    U, I = j.get('ue'), j.get('imts')
    if isinstance(U, dict) and isinstance(I, dict) and isinstance(I.get('p'), dict) and isinstance(I['p'].get('G998'), dict):
        E = I['p']['G998']
        h = {x[0]: x for x in (U.get('h') or []) if isinstance(x, list) and len(x) == 3}
        r = h.get(I.get('asof'))
        if r and r[1] and r[2] and _ru_k_num(E.get('x')) and _ru_k_num(E.get('m')):
            a, b = E['x'] * 1000 / r[1], E['m'] * 1000 / r[2]
            sa = '⚠️' if not RU_K_IMP_PASMO[0] <= a <= RU_K_IMP_PASMO[1] else '✅'
            sb = '⚠️' if not RU_K_EKSP_PASMO[0] <= b <= RU_K_EKSP_PASMO[1] else 'ℹ️'
            wier.append((f'import UE z Rosji (UE, EUR) ↔ eksport Rosji do UE (Rosja, USD) {I["asof"]}: iloraz {_ru_k_f(a)}', sa))
            wier.append((f'eksport UE do Rosji ↔ import Rosji z UE {I["asof"]}: iloraz {_ru_k_f(b)} (inna metoda — informacja)', sb))
            if sa == '⚠️':
                uw.append(f'Rosja: iloraz eksportu Rosji do UE (USD) do importu UE z Rosji (EUR) {_ru_k_f(a)} poza pasmem {_ru_k_f(RU_K_IMP_PASMO[0])}–{_ru_k_f(RU_K_IMP_PASMO[1])} ({I["asof"]}) — najwyżej uwaga')
            if sb == '⚠️':
                uw.append(f'Rosja: iloraz importu Rosji z UE do eksportu UE do Rosji {_ru_k_f(b)} poza pasmem {_ru_k_f(RU_K_EKSP_PASMO[0])}–{_ru_k_f(RU_K_EKSP_PASMO[1])} ({I["asof"]}) — najwyżej uwaga')
    su = files.get('surowce') if isinstance(files, dict) else None
    try:
        d = {r[0]: float(r[1]) for r in su['banki']['kr']['RU']['d'] if isinstance(r, list) and len(r) >= 2 and _ru_k_num(r[1])}
    except (KeyError, TypeError, IndexError, ValueError):
        d = {}
    Z, G = j.get('rez'), j.get('zloto')
    if isinstance(Z, dict) and _ru_k_num(Z.get('zloto_war')) and Z.get('asof') in d:
        cena = Z['zloto_war'] * 1e9 / (d[Z['asof']] * RU_K_UNCJA_T)
        sc = '✅' if RU_K_CENA_PASMO[0] <= cena <= RU_K_CENA_PASMO[1] else '⚠️'
        wier.append((f'cena uncji z wartości złota w rezerwach i tonażu {Z["asof"]}: {cena:,.0f} USD'.replace(',', ' '), sc))
        if sc == '⚠️':
            uw.append(f'Rosja: cena uncji z rezerw ({cena:,.0f} USD, {Z["asof"]}) poza {RU_K_CENA_PASMO[0]:.0f}–{RU_K_CENA_PASMO[1]:.0f} USD — sprawdź jednostki'.replace(',', ' '))
    if isinstance(G, dict) and d:
        a = max(d)
        if str(G.get('asof') or '') < a:
            wier.append((f'kopia złota (rosja.json {G.get("asof")}) starsza niż źródło ({a})', '⚠️'))
            uw.append(f'Rosja: kopia złota w rosja.json ({G.get("asof")}) starsza niż źródło w surowce.json ({a}) — najwyżej uwaga')
        elif G.get('asof') == a and _ru_k_num(G.get('t')) and abs(G['t'] - d[a]) > 0.15:
            wier.append((f'kopia złota {a}: {G["t"]} t ≠ źródło {round(d[a], 1)} t', '⚠️'))
            uw.append(f'Rosja: kopia złota w rosja.json ({G["t"]} t) ≠ źródło w surowce.json ({round(d[a], 1)} t) dla {a} — najwyżej uwaga')
        else:
            wier.append((f'kopia złota zgodna ze źródłem {a}', '✅'))
    return {'wiersze': wier, 'uwagi': uw}


def rosja_kontrola(files, R):
    """Kontrola pliku rosja.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i porównania (najwyżej ⚠️). Brak pliku albo inna wersja = None (raport bez linii)."""
    j = files.get('rosja') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = rosja_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'rosja.json: sprzeczność w pliku — {z}')
    P = rosja_porownania(j, files)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v361 (F3Z2): Polska na rynku dziennie (data/polska-rynek.json) ----------------------------------------------------------------
# Świeżość trzech części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠️. Progi z testu wstecznego na historii WIG20 z nagrania 10.10.2026 (kanał wykresów giełdy,
# 1 445 przerw między sesjami od 2021): największy wiek dnia danych tuż przed spodziewaną publikacją następnej sesji (16:45 UTC) = 88,75 godz. roboczych (Boże Narodzenie:
# sesja we wtorek 23.12, następna w poniedziałek 29.12; kolejne: 64,75 godz. przy Wielkanocy i Nowym Roku; 95. percentyl 16,75 godz.) → próg ⚠️ 100 godz. roboczych dla
# indeksów i krzywej. Raport przepływów funduszy: dzień danych = koniec miesiąca, nowy plik ok. 11. dnia drugiego miesiąca po nim (plik za sierpień był na liście raportów
# 10.10.2026, czyli 41 dni po końcu miesiąca) → próg ⚠️ 60 dni od końca miesiąca danych. ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (daty nie rosną, wartość spoza
# skali, stałe terminy krzywej ≠ przeliczenie z serii, suma typów funduszy ≠ razem, netto ≠ wpływy − wypływy, miesiące niekolejne). Porównania (najwyżej ⚠️, ℹ️):
# (1) WIG20 z kanału wykresów giełdy a WIG20 z pliku indeksy.json (drugi dostawca) w tym samym dniu: 09.10.2026 4 185,52 = 4 185,52 → ⚠️ powyżej 0,3% różnicy;
# (2) dzienna zmiana indeksu o ponad 10% (WIG20: −12% w marcu 2020, w ostatnich 400 dniach największa poniżej 5%) = ⚠️; (3) średnia dzienna zmiana rentowności
# obligacji o ponad 0,5 pp (typowo 0,02–0,10 pp; zbieracz odrzuca dzień powyżej 1,5 pp) = ⚠️; (4) rentowność „10 lat” minus „2 lata” poza [−2; +5] pp = ⚠️;
# (5) różnica „10 lat” do 10-latek Niemiec (plik rynki.json) poza [0,3; 6,0] pp = ⚠️ (09.10.2026: 6,27 − 3,50 = 2,77 pp).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'polska-rynek')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['polska-rynek'] = 180   # plik zapisywany co przebieg (części mają własny rytm); wiek dnia danych każdej części ocenia wiersz świeżości
AW_BEZ_BLEDU.update({'polska_rynek_' + p: 'Polska na rynku — część z błędem zostaje z datą (v361); wiek danych w wierszach świeżości' for p in ('gpw', 'krzywa', 'fundusze')})
PLR_K_ETYKIETA = {'gpw': 'Polska: indeksy giełdy w Warszawie (dziennie)', 'krzywa': 'Polska: krzywa rentowności obligacji skarbowych (dziennie)',
                  'fundusze': 'Polska: przepływy do funduszy inwestycyjnych (miesięcznie)'}
PLR_K_PROG_GODZ = {'gpw': 100, 'krzywa': 100}    # godziny robocze od końca dnia danych
PLR_K_PROG_DNI_FUND = 60                          # dni od końca miesiąca danych
PLR_K_IDX = ('WIG', 'WIG20', 'mWIG40', 'sWIG80', 'TBSP')
PLR_K_WIG20_TOL = 0.003
PLR_K_SKOK = 0.10
PLR_K_KRZYWA_SKOK_PP = 0.5
PLR_K_NACHYLENIE = (-2.0, 5.0)
PLR_K_BUND = (0.3, 6.0)
PLR_K_TOL_MLN = 5.0


def _plr_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))


def _plr_k_f(x, d=2):
    return f'{x:.{d}f}'.replace('.', ',')


def _plr_k_dzien(s):
    try:
        return dt.date.fromisoformat(str(s)) if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(s)) else None
    except ValueError:
        return None


def plr_k_cm(p):
    """Niezależne przeliczenie stałych terminów 2, 5 i 10 lat z serii [[lata, rentowność, kod], …] (rosnąco): [y2, y5, y10, lata serii „10 lat” albo None]."""
    def interp(T):
        for a, b in zip(p, p[1:]):
            if a[0] <= T <= b[0]:
                return round(a[1] + (b[1] - a[1]) * (T - a[0]) / (b[0] - a[0]), 2) if b[0] > a[0] else round(a[1], 2)
        return None
    y = [interp(2.0), interp(5.0), interp(10.0)]
    l10 = None
    if y[2] is None and p and 9.0 <= p[-1][0] < 10.0:
        y[2], l10 = round(p[-1][1], 2), round(p[-1][0], 1)
    return y + [l10]


def polska_rynek_swiezosc(j, now=None):
    """Wiersze świeżości trzech części pliku polska-rynek.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️, nigdy ❌;
    brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?' (część, której plik jeszcze nie ma, bo źródło ani razu nie odpowiedziało)."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    rows = []
    for p, label in PLR_K_ETYKIETA.items():
        e = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = e.get('asof')
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        if p == 'fundusze':
            w = wiek_danych(str(txt)[:7], 'month', 'm', now)
            prog = PLR_K_PROG_DNI_FUND * 1440
            opis = f'próg {PLR_K_PROG_DNI_FUND} dni od końca miesiąca danych — najwyżej uwaga (nowy raport ok. 11. dnia drugiego miesiąca po miesiącu danych)'
        else:
            w = wiek_danych(txt, 'day', 'd', now)
            prog = PLR_K_PROG_GODZ[p] * 60
            opis = f'próg {PLR_K_PROG_GODZ[p]} godz. roboczych — najwyżej uwaga (święta bez sesji wydłużają przerwę do ok. 89 godz.)'
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        rows.append((label, st, w, str(txt), opis if st == '⚠️' else ''))
    return rows


def polska_rynek_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w danych o Polsce na rynku) → lista opisów."""
    zle = []
    G = j.get('gpw') if isinstance(j.get('gpw'), dict) else None
    if G and isinstance(G.get('idx'), dict):
        for n in PLR_K_IDX:
            d = (G['idx'].get(n) or {}).get('d') if isinstance(G['idx'].get(n), dict) else None
            if not isinstance(d, list) or not d:
                zle.append(f'gpw.{n}: brak serii'); continue
            if any(not (isinstance(x, list) and len(x) == 2 and _plr_k_dzien(x[0]) and _plr_k_num(x[1]) and x[1] > 0) for x in d):
                zle.append(f'gpw.{n}: wiersz spoza układu [dzień, zamknięcie > 0]'); continue
            if [x[0] for x in d] != sorted({x[0] for x in d}):
                zle.append(f'gpw.{n}: dni nie rosną albo się powtarzają')
            if min(x[0] for x in [d[-1]]) < (G.get('asof') or ''):
                zle.append(f'gpw.{n}: ostatni dzień {d[-1][0]} wcześniejszy niż dzień danych {G.get("asof")}')
    K = j.get('krzywa') if isinstance(j.get('krzywa'), dict) else None
    if K and isinstance(K.get('k'), dict) and K['k']:
        if K.get('asof') != max(K['k']):
            zle.append(f'krzywa: dzień danych {K.get("asof")} ≠ ostatni dzień szeregu {max(K["k"])}')
        for dz, e in K['k'].items():
            p = e.get('p') if isinstance(e, dict) else None
            if not (_plr_k_dzien(dz) and isinstance(p, list) and len(p) >= 8 and all(isinstance(x, list) and len(x) == 3 and _plr_k_num(x[0]) and _plr_k_num(x[1]) for x in p)):
                zle.append(f'krzywa {dz}: układ serii'); continue
            if any(a[0] >= b[0] for a, b in zip(p, p[1:])):
                zle.append(f'krzywa {dz}: lata do wykupu nie rosną')
            if any(not 0.3 <= x[1] <= 15 for x in p):
                zle.append(f'krzywa {dz}: rentowność poza 0,3–15%')
            cm = e.get('cm')
            if not (isinstance(cm, list) and len(cm) == 4) or any(a != b and not (a is not None and b is not None and abs(a - b) <= 0.011) for a, b in zip(cm, plr_k_cm(p))):
                zle.append(f'krzywa {dz}: stałe terminy {cm} ≠ przeliczenie z serii {plr_k_cm(p)}')
    F = j.get('fundusze') if isinstance(j.get('fundusze'), dict) else None
    if F and isinstance(F.get('m'), list) and F['m']:
        m = F['m']
        if any(not (isinstance(x, list) and len(x) == 5 and re.fullmatch(r'\d{4}-\d{2}', str(x[0])) and all(_plr_k_num(v) for v in x[1:])) for x in m):
            zle.append('fundusze.m: wiersz spoza układu [miesiąc, aktywa, wpływy, wypływy, netto]')
        else:
            n = [int(x[0][:4]) * 12 + int(x[0][5:]) for x in m]
            if any(b - a != 1 for a, b in zip(n, n[1:])):
                zle.append('fundusze.m: miesiące niekolejne')
            if m[-1][0] != str(F.get('asof'))[:7]:
                zle.append(f'fundusze: dzień danych {F.get("asof")} ≠ ostatni miesiąc szeregu {m[-1][0]}')
            for x in m:
                if abs(x[2] - x[3] - x[4]) > 0.006:
                    zle.append(f'fundusze {x[0]}: netto {x[4]} ≠ wpływy − wypływy {round(x[2] - x[3], 3)} mld zł'); break
            p = F.get('p')
            if isinstance(p, list) and p and all(isinstance(x, list) and len(x) == 3 and _plr_k_num(x[1]) and _plr_k_num(x[2]) for x in p):
                if abs(sum(x[1] for x in p) - m[-1][1] * 1000) > PLR_K_TOL_MLN:
                    zle.append(f'fundusze: suma aktywów typów {round(sum(x[1] for x in p))} mln ≠ razem {round(m[-1][1] * 1000)} mln zł')
                if abs(sum(x[2] for x in p) - m[-1][4] * 1000) > PLR_K_TOL_MLN:
                    zle.append(f'fundusze: suma netto typów {round(sum(x[2] for x in p), 1)} mln ≠ razem {round(m[-1][4] * 1000, 1)} mln zł')
            else:
                zle.append('fundusze.p: brak typów funduszy albo zły układ')
    return zle


def polska_rynek_porownania(j, files):
    """Porównania z innymi danymi i z drugim dostawcą (najwyżej ⚠️): {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    wier, uw = [], []
    G = j.get('gpw') if isinstance(j.get('gpw'), dict) else None
    ix = files.get('indeksy') if isinstance(files, dict) else None
    try:
        w20 = {r[0]: r[1] for r in G['idx']['WIG20']['d']}
        dr = {r[0]: r[1] for r in ix['ix']['WIG20']['d'] if isinstance(r, list) and len(r) >= 2 and _plr_k_num(r[1])}
    except (KeyError, TypeError, IndexError, AttributeError):
        w20, dr = {}, {}
    wsp = sorted(set(w20) & set(dr))
    if wsp:
        d = wsp[-1]
        roz = abs(w20[d] / dr[d] - 1)
        s = '✅' if roz <= PLR_K_WIG20_TOL else '⚠️'
        wier.append((f'WIG20 {d}: giełda {_plr_k_f(w20[d])} ↔ drugi dostawca {_plr_k_f(dr[d])} (różnica {_plr_k_f(roz * 100, 2)}%)', s))
        if s == '⚠️':
            uw.append(f'Polska: WIG20 {d} z giełdy ({_plr_k_f(w20[d])}) ≠ z indeksy.json ({_plr_k_f(dr[d])}) — różnica {_plr_k_f(roz * 100, 2)}% powyżej {_plr_k_f(PLR_K_WIG20_TOL * 100, 1)}% — najwyżej uwaga')
    elif G and w20:
        wier.append(('WIG20: brak wspólnego dnia z indeksy.json do porównania', 'ℹ️'))
    if G and isinstance(G.get('idx'), dict):
        for n in PLR_K_IDX:
            d = (G['idx'].get(n) or {}).get('d') if isinstance(G['idx'].get(n), dict) else None
            if isinstance(d, list) and len(d) > 1 and all(isinstance(x, list) and len(x) == 2 and _plr_k_num(x[1]) and x[1] > 0 for x in d[-30:]):
                r = d[-30:]
                z = max(((abs(b[1] / a[1] - 1), b[0]) for a, b in zip(r, r[1:])), default=(0, ''))
                if z[0] > PLR_K_SKOK:
                    wier.append((f'{n}: dzienna zmiana {_plr_k_f(z[0] * 100, 1)}% ({z[1]})', '⚠️'))
                    uw.append(f'Polska: {n} zmienił się o {_plr_k_f(z[0] * 100, 1)}% w dniu {z[1]} (próg {_plr_k_f(PLR_K_SKOK * 100, 0)}%) — sprawdź, czy to nie błąd skali — najwyżej uwaga')
    K = j.get('krzywa') if isinstance(j.get('krzywa'), dict) else None
    if K and isinstance(K.get('k'), dict) and K['k']:
        dni = sorted(K['k'])
        e = K['k'][dni[-1]]
        cm = e.get('cm') if isinstance(e, dict) else None
        if isinstance(cm, list) and len(cm) == 4 and _plr_k_num(cm[0]) and _plr_k_num(cm[2]):
            nach = cm[2] - cm[0]
            s = '✅' if PLR_K_NACHYLENIE[0] <= nach <= PLR_K_NACHYLENIE[1] else '⚠️'
            wier.append((f'krzywa {dni[-1]}: „10 lat” minus „2 lata” = {_plr_k_f(nach)} pp', s))
            if s == '⚠️':
                uw.append(f'Polska: różnica rentowności 10 lat − 2 lata {_plr_k_f(nach)} pp ({dni[-1]}) poza pasmem {PLR_K_NACHYLENIE[0]}–{PLR_K_NACHYLENIE[1]} pp — najwyżej uwaga')
            ry = files.get('rynki') if isinstance(files, dict) else None
            try:
                bund = {r[0]: r[1] for r in ry['buba'] if isinstance(r, list) and len(r) >= 2 and _plr_k_num(r[1])}
            except (KeyError, TypeError, IndexError):
                bund = {}
            if _plr_k_num(cm[2]) and dni[-1] in bund:
                roz = cm[2] - bund[dni[-1]]
                sb = '✅' if PLR_K_BUND[0] <= roz <= PLR_K_BUND[1] else '⚠️'
                wier.append((f'krzywa {dni[-1]}: „10 lat” minus 10 lat Niemiec ({_plr_k_f(bund[dni[-1]])}%) = {_plr_k_f(roz)} pp', sb))
                if sb == '⚠️':
                    uw.append(f'Polska: różnica rentowności do Niemiec {_plr_k_f(roz)} pp ({dni[-1]}) poza pasmem {PLR_K_BUND[0]}–{PLR_K_BUND[1]} pp — najwyżej uwaga')
        if len(dni) > 1:
            a, b = K['k'][dni[-2]], K['k'][dni[-1]]
            try:
                A, B = {x[2]: x[1] for x in a['p']}, {x[2]: x[1] for x in b['p']}
                wsp = sorted(set(A) & set(B))
                if len(wsp) >= 5:
                    sk = sum(abs(A[k] - B[k]) for k in wsp) / len(wsp)
                    s = '✅' if sk <= PLR_K_KRZYWA_SKOK_PP else '⚠️'
                    wier.append((f'krzywa {dni[-2]} → {dni[-1]}: średnia zmiana rentowności serii {_plr_k_f(sk)} pp', s))
                    if s == '⚠️':
                        uw.append(f'Polska: średnia zmiana rentowności obligacji {_plr_k_f(sk)} pp między {dni[-2]} a {dni[-1]} (próg {_plr_k_f(PLR_K_KRZYWA_SKOK_PP)} pp) — najwyżej uwaga')
            except (KeyError, TypeError, IndexError):
                pass
    return {'wiersze': wier, 'uwagi': uw}


def polska_rynek_kontrola(files, R):
    """Kontrola pliku polska-rynek.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i porównania (najwyżej ⚠️). Brak pliku albo inna wersja = None (raport bez linii)."""
    j = files.get('polska-rynek') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = polska_rynek_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'polska-rynek.json: sprzeczność w pliku — {z}')
    P = polska_rynek_porownania(j, files)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v365 (F3Z3): Polska — kapitał z zagranicy i wypłaty UE (data/polska-kapital.json) ----------------------------------------------------------------
# Świeżość każdej z dwóch części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠️, nigdy ❌. Progi: (a) inwestycje bezpośrednie według kraju (kwartalnie): wiek = dni od końca
# ostatniego kwartału danych. Obserwacja 13.10.2026: dane za II kwartał (koniec 30.06) pojawiły się 02.10, czyli 94 dni po końcu kwartału; następny kwartał dojdzie po kolejnych ~92 dniach →
# największy wiek tuż przed nową publikacją ≈ 186 dni; próg ⚠️ 200 dni od końca kwartału (14 dni zapasu). Test wsteczny: źródło nie publikuje kalendarza wydań, więc próg opiera się na
# jednej obserwowanej publikacji i rytmie kwartalnym — do weryfikacji po następnej publikacji (styczeń 2027).
# (b) wypłaty UE (zbiór odświeżany w dni robocze rano; w styczniu 2025 źródło ogłosiło zawieszenie odświeżania na czas testów nowego systemu księgowego): wiek = od chwili ostatniej
# aktualizacji zbioru (nagłówek odpowiedzi); typowa przerwa to weekend (3 dni), z świętami do ok. 5 dni → próg ⚠️ 10 dni (informacja: zawieszenie po stronie źródła, nie awaria automatu).
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (kwartały nie kolejne, świat ≠ UE27 + poza UE27, długości serii, suma funduszy lub programów ≠ razem, wypłaty > plan + 2%,
# skumulowane lata maleją, historia sumy nie kończy się dniem danych). Porównanie (najwyżej ⚠️, ℹ️): kwartalny świat z plikiem miesięcznym (ue.json, pasywa i aktywa bezpośrednie):
# suma trzech miesięcy ostatniego kwartału vs wartość kwartalna. Test wsteczny na 50 kwartałach (2014-Q1…2026-Q2): mediana różnicy 12 mln EUR, najwięcej 2 178 mln EUR (II kw. 2026, dane
# miesięczne wstępne), znak różny tylko w jednym kwartale przy wartości kwartalnej 482 mln EUR → ⚠️ dopiero przy różnicy ponad 5 000 mln EUR albo przy różnym znaku i wartości
# kwartalnej powyżej 1 000 mln EUR (0 przekroczeń w 50 kwartałach).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'polska-kapital')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['polska-kapital'] = 180   # plik zapisywany co przebieg (części mają własny rytm); wiek danych każdej części ocenia wiersz świeżości
AW_BEZ_BLEDU.update({'polska_kapital_' + p: 'Polska — kapitał z zagranicy i wypłaty UE: część z błędem zostaje z datą (v365); wiek danych w wierszach świeżości' for p in ('fdi', 'ue')})
PK_K_ETYKIETA = {'fdi': 'Polska: inwestycje bezpośrednie według kraju (kwartalnie)', 'ue': 'Polska: wypłaty z budżetu UE 2021–2027 (dziennie w dni robocze)'}
PK_K_PROG_DNI_FDI = 200      # dni od końca kwartału danych
PK_K_PROG_DNI_UE = 10        # dni od ostatniej aktualizacji zbioru
PK_K_TOL_MLN, PK_K_TOL_PCT = 1.0, 0.5   # świat = UE27 + poza UE27 (jak w zbieraczu)
PK_K_MIES_ROZ, PK_K_MIES_ZNAK = 5000.0, 1000.0


def _pk_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))


def _pk_k_f(x, d=1):
    return f'{x:,.{d}f}'.replace(',', ' ').replace('.', ',')


def _pk_k_kw(s):
    m = re.fullmatch(r'(\d{4})-Q([1-4])', str(s))
    return int(m.group(1)) * 4 + int(m.group(2)) - 1 if m else None


def polska_kapital_swiezosc(j, now=None):
    """Wiersze świeżości dwóch części pliku polska-kapital.json (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️; brak pliku albo inna wersja = brak wierszy;
    część bez daty danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    rows = []
    for p, label in PK_K_ETYKIETA.items():
        e = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = e.get('asof')
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        if p == 'fdi':
            w, prog = wiek_danych(str(txt), 'day', 'k', now), PK_K_PROG_DNI_FDI * 1440
            opis = f'próg {PK_K_PROG_DNI_FDI} dni od końca kwartału danych — najwyżej uwaga (kwartał pojawia się ok. 94 dni po jego końcu)'
        else:
            w, prog = wiek_danych(str(e.get('t') or txt), 'ts', 'k', now), PK_K_PROG_DNI_UE * 1440
            opis = f'próg {PK_K_PROG_DNI_UE} dni od ostatniej aktualizacji zbioru — najwyżej uwaga (źródło potrafi zawiesić odświeżanie; w styczniu 2025 ogłosiło przerwę na czas testów nowego systemu księgowego)'
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        rows.append((label, st, w, str(txt), opis if st == '⚠️' else ''))
    return rows


def polska_kapital_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w danych o kapitale w Polsce) → lista opisów."""
    zle = []
    F = j.get('fdi') if isinstance(j.get('fdi'), dict) else None
    if F:
        q = F.get('q')
        qi = [_pk_k_kw(x) for x in q] if isinstance(q, list) else []
        if len(qi) < 6 or None in qi or any(b - a != 1 for a, b in zip(qi, qi[1:])):
            zle.append('fdi: kwartały nie są kolejne albo jest ich mniej niż 6')
        else:
            if F.get('last') != q[-1]:
                zle.append(f'fdi: ostatni kwartał {F.get("last")} ≠ ostatni z listy {q[-1]}')
            for kier in ('in', 'out'):
                B = F.get(kier) if isinstance(F.get(kier), dict) else None
                if not B:
                    zle.append(f'fdi.{kier}: brak bloku'); continue
                for k in ('w', 'eu', 'x'):
                    s = B.get(k)
                    if not (isinstance(s, list) and len(s) == len(q) and all(x is None or _pk_k_num(x) for x in s)):
                        zle.append(f'fdi.{kier}.{k}: układ serii'); break
                else:
                    if B['w'][-1] is None:
                        zle.append(f'fdi.{kier}: świat nie ma wartości w ostatnim kwartale')
                    for i, qq in enumerate(q):
                        a, b, c = B['w'][i], B['eu'][i], B['x'][i]
                        if None not in (a, b, c) and abs(a - (b + c)) > max(PK_K_TOL_MLN, abs(a) * PK_K_TOL_PCT / 100):
                            zle.append(f'fdi.{kier} {qq}: świat {_pk_k_f(a)} ≠ UE27 {_pk_k_f(b)} + poza UE27 {_pk_k_f(c)}'); break
                C = B.get('c')
                if not (isinstance(C, dict) and C and all(isinstance(r, list) and len(r) == len(q) and all(x is None or _pk_k_num(x) for x in r) for r in C.values())):
                    zle.append(f'fdi.{kier}.c: układ krajów')
    U = j.get('ue') if isinstance(j.get('ue'), dict) else None
    if U:
        tot, plan = U.get('total'), U.get('plan')
        if not (_pk_k_num(tot) and _pk_k_num(plan) and plan > 0 and tot >= 0):
            zle.append('ue: suma wypłat albo plan spoza układu')
        else:
            if tot > plan * 1.02:
                zle.append(f'ue: wypłaty {_pk_k_f(tot)} mln EUR > plan {_pk_k_f(plan)} mln EUR + 2%')
            for k, i in (('funds', 1), ('prog', 1)):
                L = U.get(k)
                if not (isinstance(L, list) and L and all(isinstance(r, list) and len(r) == 3 and _pk_k_num(r[1]) and _pk_k_num(r[2]) for r in L)):
                    zle.append(f'ue.{k}: układ listy'); continue
                if abs(sum(r[1] for r in L) - tot) > 0.1 * len(L) + 0.1:
                    zle.append(f'ue.{k}: suma wypłat {_pk_k_f(sum(r[1] for r in L))} ≠ razem {_pk_k_f(tot)}')
                if abs(sum(r[2] for r in L) - plan) > 0.1 * len(L) + 0.1:
                    zle.append(f'ue.{k}: suma planu {_pk_k_f(sum(r[2] for r in L))} ≠ razem {_pk_k_f(plan)}')
            yd = U.get('ydr')
            if isinstance(yd, dict):
                v = [yd[k] for k in sorted(yd)]
                if not all(_pk_k_num(x) for x in v) or any(b < a * 0.99 for a, b in zip(v, v[1:] + [tot])):
                    zle.append('ue.ydr: suma skumulowana maleje między latami')
            else:
                zle.append('ue.ydr: brak')
            h = U.get('hist')
            if isinstance(h, list) and h:
                if [r[0] for r in h] != sorted({r[0] for r in h}):
                    zle.append('ue.hist: dni nie rosną albo się powtarzają')
                if h[-1][0] != U.get('asof') or abs(h[-1][1] - tot) > 0.15:
                    zle.append('ue.hist: ostatni punkt ≠ dzień danych i suma')
            if str(U.get('t') or '')[:10] != U.get('asof'):
                zle.append(f'ue: dzień danych {U.get("asof")} ≠ dzień chwili aktualizacji {U.get("t")}')
    return zle


def polska_kapital_porownania(j, files):
    """Porównanie kwartalnego świata z sumą trzech miesięcy z pliku miesięcznego (ue.json); najwyżej ⚠️: {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    wier, uw = [], []
    F = j.get('fdi') if isinstance(j.get('fdi'), dict) else None
    ue = files.get('ue') if isinstance(files, dict) else None
    try:
        S = ue['rows']['PL']['s']
    except (KeyError, TypeError):
        S = None
    if not F or not S or not isinstance(F.get('q'), list) or not F['q']:
        return {'wiersze': wier, 'uwagi': uw}
    q = F['q'][-1]
    i = _pk_k_kw(q)
    if i is None:
        return {'wiersze': wier, 'uwagi': uw}
    y, k = i // 4, i % 4
    mies = [f'{y}-{k * 3 + n:02d}' for n in (1, 2, 3)]
    for kier, klucz, nazwa in (('in', 'in_d', 'do Polski'), ('out', 'out_d', 'z Polski')):
        try:
            M = {r[0]: r[1] for r in S[klucz] if isinstance(r, list) and len(r) >= 2 and _pk_k_num(r[1])}
            qv = F[kier]['w'][-1]
        except (KeyError, TypeError):
            continue
        if not _pk_k_num(qv) or not all(m in M for m in mies):
            wier.append((f'{q} {nazwa}: brak trzech miesięcy w pliku miesięcznym do porównania', 'ℹ️')); continue
        s = sum(M[m] for m in mies)
        roz = s - qv
        zle = abs(roz) > PK_K_MIES_ROZ or (s * qv < 0 and abs(qv) > PK_K_MIES_ZNAK)
        wier.append((f'{q} {nazwa}: kwartał {_pk_k_f(qv, 0)} mln EUR ↔ suma 3 miesięcy z pliku miesięcznego {_pk_k_f(s, 0)} mln EUR (różnica {_pk_k_f(roz, 0)})', '⚠️' if zle else '✅'))
        if zle:
            uw.append(f'Polska kapitał: {q} {nazwa} — kwartalnie {_pk_k_f(qv, 0)} mln EUR, a suma 3 miesięcy z ue.json {_pk_k_f(s, 0)} mln EUR (różnica {_pk_k_f(roz, 0)}, próg {_pk_k_f(PK_K_MIES_ROZ, 0)}) — najwyżej uwaga')
    return {'wiersze': wier, 'uwagi': uw}


def polska_kapital_kontrola(files, R):
    """Kontrola pliku polska-kapital.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i porównanie (najwyżej ⚠️). Brak pliku albo inna wersja = None (raport bez linii)."""
    j = files.get('polska-kapital') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = polska_kapital_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'polska-kapital.json: sprzeczność w pliku — {z}')
    P = polska_kapital_porownania(j, files)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v371 (F3Z1): Polska — kto trzyma dług skarbowy i sprzedaż obligacji detalicznych (data/polska-dlug.json) ----------------------------------------------------------------
# Świeżość każdej z dwóch części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠️, nigdy ❌: oba pliki wydawcy są miesięczne, więc wiek liczymy od końca miesiąca danych i oceniamy
# według RYTMU PUBLIKACJI, nie dnia (plik miesięczny nie może dawać alarmu przez cały miesiąc).
# (a) struktura posiadaczy (miesiąc M): plik pojawia się ok. 28. dnia miesiąca M+1 (obserwacja 13.10.2026: plik za sierpień zmieniony 28.09, czyli 28 dni po końcu sierpnia); następny
# dojdzie ok. 28 dni po końcu września, więc wiek danych tuż przed nową publikacją to ok. 58–62 dni od końca miesiąca (z weekendem i ostatnim dniem roboczym do ok. 62). Próg ⚠️ 70 dni od
# końca miesiąca danych = ten sam próg, którego zbieracz używa dla pliku nierezydentów tego samego wydawcy i tej samej strony (SPW_STALE) — 8 dni zapasu.
# (b) sprzedaż obligacji detalicznych (miesiąc M): plik zmieniony 09.10.2026 (dziewiąty dzień miesiąca) z danymi za wrzesień; następny ok. 9.11, czyli wiek danych tuż przed nową
# publikacją ok. 40 dni od końca miesiąca (ze świętami i weekendem do ok. 42). Próg ⚠️ 55 dni (ok. 13 dni zapasu, publikacja po 22. dniu miesiąca dopiero daje uwagę).
# Obie publikacje znamy z jednej obserwacji na część plus rytmu miesięcznego — źródło nie ma kalendarza wydań; do weryfikacji po kolejnych publikacjach (listopad–grudzień 2026).
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (miesiące nie kolejne, długości serii, suma grup ≠ „Razem”, zamiana > sprzedaż, sumy według typów ≠ suma miesięcy).
# Porównanie (najwyżej ⚠️, ℹ️): udział inwestorów zagranicznych w strukturze posiadaczy a plik nierezydentów (spw.json, ten sam wydawca): kwoty tych samych miesięcy (do 25) muszą się
# zgadzać z dokładnością do zaokrągleń — pierwotny odczyt 10.10.2026: 25 z 25 miesięcy bez różnicy; ⚠️ dopiero przy różnicy ponad 1,5 mln zł w którymkolwiek wspólnym miesiącu.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'polska-dlug')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['polska-dlug'] = 180   # plik zapisywany co przebieg (części mają własny rytm); wiek danych każdej części ocenia wiersz świeżości
AW_BEZ_BLEDU.update({'polska_dlug_' + p: 'Polska — kto trzyma dług skarbowy i obligacje detaliczne: część z błędem zostaje z datą (v371); wiek danych w wierszach świeżości' for p in ('pos', 'det')})
PD_K_ETYKIETA = {'pos': 'Polska: kto trzyma dług skarbowy (struktura posiadaczy, miesięcznie)', 'det': 'Polska: sprzedaż obligacji detalicznych (miesięcznie)'}
PD_K_PROG_DNI = {'pos': 70, 'det': 55}      # dni od końca miesiąca danych
PD_K_TOL_MLN = 1.5                          # suma grup = „Razem”: 1 mln zł zbieracza + zaokrąglenia do 0,1 mln zł w 10 liczbach
PD_K_ZAGR_MLN = 1.5                         # zagranica w obu plikach tego samego wydawcy


def _pd_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))


def _pd_k_f(x, d=1):
    return f'{x:,.{d}f}'.replace(',', ' ').replace('.', ',')


def _pd_k_mi(m):
    x = re.fullmatch(r'(\d{4})-(0[1-9]|1[0-2])', str(m))
    return int(x.group(1)) * 12 + int(x.group(2)) - 1 if x else None


def polska_dlug_swiezosc(j, now=None):
    """Wiersze świeżości dwóch części pliku polska-dlug.json (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️; brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    rows = []
    for p, label in PD_K_ETYKIETA.items():
        e = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = e.get('asof')
        if not (isinstance(txt, str) and _pd_k_mi(txt) is not None):
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w, prog = wiek_danych(txt, 'month', 'k', now), PD_K_PROG_DNI[p] * 1440
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        rows.append((label, st, w, txt, f'próg {PD_K_PROG_DNI[p]} dni od końca miesiąca danych — najwyżej uwaga (plik miesięczny, rytm publikacji opisany w kodzie kontroli)' if st == '⚠️' else ''))
    return rows


def polska_dlug_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w danych o długu w Polsce) → lista opisów."""
    zle = []
    P = j.get('pos') if isinstance(j.get('pos'), dict) else None
    if P:
        m, s = P.get('m'), P.get('s')
        mi = [_pd_k_mi(x) for x in m] if isinstance(m, list) else []
        if len(mi) < 24 or None in mi or any(b - a != 1 for a, b in zip(mi, mi[1:])):
            zle.append('pos: miesiące nie są kolejne albo jest ich mniej niż 24')
        elif P.get('asof') != m[-1]:
            zle.append(f'pos: miesiąc danych {P.get("asof")} ≠ ostatni z listy {m[-1]}')
        kl = ('banki', 'zagr', 'ubez', 'emer', 'inwe', 'gosp', 'przed', 'inst', 'inne')
        if not (isinstance(s, dict) and all(isinstance(s.get(k), list) and len(s[k]) == len(mi) and all(x is None or (_pd_k_num(x) and x >= 0) for x in s[k]) for k in kl + ('razem',))):
            zle.append('pos.s: układ serii (długości, wartości ujemne)')
        elif mi and None not in mi:
            if any(x is None for x in s['razem']):
                zle.append('pos.s.razem: brak wartości')
            else:
                for i, mm in enumerate(m):
                    a = sum(s[k][i] for k in kl if s[k][i] is not None)
                    if abs(a - s['razem'][i]) > PD_K_TOL_MLN:
                        zle.append(f'pos {mm}: suma grup {_pd_k_f(a)} ≠ razem {_pd_k_f(s["razem"][i])} mln zł'); break
            if any(s[k][-1] is None for k in kl):
                zle.append('pos: brak wartości grupy w ostatnim miesiącu')
    D = j.get('det') if isinstance(j.get('det'), dict) else None
    if D:
        m, b, z = D.get('m'), D.get('b'), D.get('z')
        mi = [_pd_k_mi(x) for x in m] if isinstance(m, list) else []
        if len(mi) < 24 or None in mi or any(y - x != 1 for x, y in zip(mi, mi[1:])):
            zle.append('det: miesiące nie są kolejne albo jest ich mniej niż 24')
        else:
            if D.get('asof') != m[-1]:
                zle.append(f'det: miesiąc danych {D.get("asof")} ≠ ostatni z listy {m[-1]}')
            if not (isinstance(b, list) and isinstance(z, list) and len(b) == len(z) == len(m) and all(_pd_k_num(x) and x > 0 for x in b) and all(_pd_k_num(x) and x >= 0 for x in z)):
                zle.append('det: układ serii sprzedaży i zamiany')
            else:
                if any(zz > bb + 0.05 for bb, zz in zip(b, z)):
                    zle.append('det: zamiana większa od sprzedaży łącznej')
                T = D.get('t')
                if isinstance(T, dict) and T:
                    ok = all(isinstance(r, list) and len(r) == 4 and all(_pd_k_num(x) and x >= 0 for x in r) for r in T.values())
                    if not ok:
                        zle.append('det.t: układ typów')
                    else:
                        for k, nm in ((0, 'sprzedaż 12 mies.'), (1, 'zamiana 12 mies.'), (2, 'sprzedaż poprzednich 12 mies.'), (3, 'zamiana poprzednich 12 mies.')):
                            ref = sum((b if k % 2 == 0 else z)[-12:] if k < 2 else (b if k % 2 == 0 else z)[-24:-12])
                            if abs(sum(r[k] for r in T.values()) - ref) > 0.1 * len(T) + 0.1:
                                zle.append(f'det.t: suma według typów ({nm}) ≠ suma miesięcy'); break
                else:
                    zle.append('det.t: brak podziału według typów')
    return zle


def polska_dlug_porownania(j, files):
    """Zagranica w strukturze posiadaczy a plik nierezydentów (spw.json): {'wiersze': [(opis, znak)], 'uwagi': [...]}. Najwyżej ⚠️."""
    wier, uw = [], []
    P = j.get('pos') if isinstance(j.get('pos'), dict) else None
    S = files.get('spw') if isinstance(files, dict) else None
    if not P or not isinstance(S, dict) or not isinstance(S.get('m'), list) or not isinstance(P.get('m'), list) or not isinstance((P.get('s') or {}).get('zagr'), list):
        return {'wiersze': wier, 'uwagi': uw}
    zg = dict(zip(P['m'], P['s']['zagr']))
    roz, n = [], 0
    for r in S['m']:
        if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and _pd_k_num(r[1]) and _pd_k_num(zg.get(r[0])):
            n += 1
            roz.append((abs(zg[r[0]] - r[1]), r[0], zg[r[0]], r[1]))
    if n < 3:
        wier.append(('Zagranica: za mało wspólnych miesięcy z plikiem nierezydentów do porównania', 'ℹ️'))
        return {'wiersze': wier, 'uwagi': uw}
    mx = max(roz)
    zle = mx[0] > PD_K_ZAGR_MLN
    wier.append((f'Zagranica: {n} wspólnych miesięcy z plikiem nierezydentów, największa różnica {_pd_k_f(mx[0], 2)} mln zł ({mx[1]}: struktura {_pd_k_f(mx[2])} ↔ nierezydenci {_pd_k_f(mx[3])})', '⚠️' if zle else '✅'))
    if zle:
        uw.append(f'Polska dług: inwestorzy zagraniczni {mx[1]} — {_pd_k_f(mx[2])} mln zł w strukturze posiadaczy, a {_pd_k_f(mx[3])} mln zł w pliku nierezydentów (różnica {_pd_k_f(mx[0])}, próg {_pd_k_f(PD_K_ZAGR_MLN)}) — najwyżej uwaga')
    return {'wiersze': wier, 'uwagi': uw}


def polska_dlug_kontrola(files, R):
    """Kontrola pliku polska-dlug.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i porównanie (najwyżej ⚠️). Brak pliku albo inna wersja = None (raport bez linii)."""
    j = files.get('polska-dlug') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = polska_dlug_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'polska-dlug.json: sprzeczność w pliku — {z}')
    P = polska_dlug_porownania(j, files)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v341 (F5Z3): zboża dziennie i koszt transportu (data/zboza-dzien.json) ----------------------------------------------------------------
# Świeżość każdej z pięciu części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠ — pole next pliku mówi, kiedy spodziewana jest publikacja.
# Progi z testu wstecznego na modelu kalendarza publikacji i prawdziwych datach wierszy z nagrań 10–11.10.2026 (ws53/v341-zboza-dz/bt/bt_swiezosc.py, sprawdzenia
# co 2 h albo co 1 h): indeks dzienny — dane z dnia roboczego D dostępne od następnego dnia roboczego ok. 08:20 UTC; 26 lat (2000–2026), 116 958 sprawdzeń:
# najwyższy wiek 80 godzin roboczych (Wielkanoc 2025), ponad 84 — 0%, próg 96 godz. roboczych (kategoria 'd': soboty i niedziele się nie liczą), 0%;
# indeks frachtu (99 tygodni): najwyższy wiek 14,3 dnia (jeden 14-dniowy odstęp między punktami), próg 14 dni — 0,06% sprawdzeń; ceny w UE (60 tygodni
# bez luk): najwyższy wiek 10,5 dnia, próg 14 dni — 0%; podindeksy żywności (441 miesięcy bez luk, publikacja w pierwszy piątek miesiąca): najwyższy
# wiek 36 dni, próg 45 dni — 0%; nawozy (93 miesiące bez luk, publikacja ok. 10. dnia): próg 50 dni.
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (daty nie rosną, wartość ≤ 0, st.last ≠ ostatni punkt serii, zmiana dnia ≠ wyliczona z serii,
# ostatni indeks poza przedziałem 365 dni, asof ≠ ostatni dzień danych). Progi ⚠ (test wsteczny, ws53/v341-zboza-dz/bt/):
#   — skok w jednym kroku serii: indeks dzienny (26 lat, 6968 dni) najwyżej 14,4% (jęczmień 2010) → próg 20%; indeks frachtu (99 tygodni) najwyżej 26,7%
#     (Australia) → 45%; podindeksy żywności (441 miesięcy) najwyżej 26,6% (cukier) → 40%; ceny w UE (60 tygodni, 12 serii zbóż) najwyżej 30,1% (jęczmień
#     w Rumunii, 18.01.2026) → 45%; nawozy (93 miesiące) najwyżej 68% → 90%. W historii 0 przekroczeń;
#   — zmiany miesięczne indeksu dziennego (średnie miesięczne) vs podindeks zbóż w żywności (te same dane źródła w innym przetworzeniu, 320 miesięcy
#     2000–2026): korelacja 0,91, zgodny znak 85% miesięcy; w oknach kroczących 36 miesięcy najniżej 0,78 (285 okien) → ⚠ poniżej 0,6 (0% okien);
#   — zmiany miesięczne indeksu dziennego vs indeks zbóż świata (z surowce.json, 35 miesięcy 10.2023–09.2026): korelacja 0,74, w oknach 24-miesięcznych
#     najniżej 0,66 → ⚠ poniżej 0,4; azot (N) w UE vs indeks nawozów świata (35 miesięcy): korelacja 0,80, w oknach 24-miesięcznych najniżej 0,59
#     → ⚠ poniżej 0,3 (fosfor i potas nie są sprawdzane — korelacja 0,40 i 0,15: indeks świata to głównie azot i fosforany z innych rynków);
#   — tabela wartości na stronie źródła (liczby całkowite) vs seria: ostatnia wartość ±0,6, zmiana dnia ±0,6, zmiana roczna ±1,6 pkt proc., najniższy
#     i najwyższy z 52 tygodni ±1,0 (10.10.2026: wszystkie sześć serii mieści się w tych granicach; różnice wynikają z zaokrągleń do liczb całkowitych);
#   — pszenica w Polsce (ceny w UE) vs pszenica w polska.json (ten sam portal, dwa pobrania): ostatni wspólny tydzień ±0,011 EUR/t (10.10.2026: 26 wspólnych
#     tygodni, różnica 0,00).
ZD_K_ETYKIETA = {'goi': 'zboża: indeks dzienny (dni robocze, dane z poprzedniego dnia roboczego)',
                 'fracht': 'zboża: indeks frachtu (tygodniowo, środa, dane za wtorek)',
                 'fao': 'żywność: podindeksy cen FAO (miesięcznie, publ. ok. 1. piątku)',
                 'ue': 'zboża i rzepak w UE: ceny tygodniowe (czwartek, tydzień do niedzieli)',
                 'nawozy': 'nawozy w UE (miesięcznie, publ. ok. 10. dnia)'}
ZD_K_PROG = {'goi': ('d', 96 * 60), 'fracht': ('w', 14 * 24 * 60), 'fao': ('m', 45 * 24 * 60), 'ue': ('w', 14 * 24 * 60), 'nawozy': ('m', 50 * 24 * 60)}
ZD_K_SKOK = {'goi': 20.0, 'fracht': 45.0, 'fao': 40.0, 'ue': 45.0, 'nawozy': 90.0}   # % w jednym kroku serii
ZD_K_KOR = {'fao': 0.6, 'wb_zboza': 0.4, 'wb_nawozy': 0.3}   # korelacja zmian miesięcznych — poniżej = ⚠
ZD_K_KOR_MIN = 24       # najmniej par zmian miesięcznych do policzenia korelacji
ZD_K_TOL = 0.011        # zaokrąglenie do 2 miejsc po przecinku
ZD_K_HIST = {'goi': '14,4', 'fracht': '26,7', 'fao': '26,6', 'ue': '30,1', 'nawozy': '68'}   # % — największy skok w kroku w historii (progi wyżej)
ZD_K_TAB = {'last': 0.6, 'd1': 0.6, 'y1': 1.6, 'lo': 1.0, 'hi': 1.0}   # tolerancje tabeli źródła (liczby całkowite)
ZD_K_NAZWY = {'goi': 'indeks ogółem', 'pszenica': 'pszenica', 'kukurydza': 'kukurydza', 'jeczmien': 'jęczmień', 'soja': 'soja', 'ryz': 'ryż',
              'gofi': 'fracht ogółem', 'argentyna': 'Argentyna', 'australia': 'Australia', 'brazylia': 'Brazylia', 'czarne': 'Morze Czarne', 'kanada': 'Kanada',
              'europa': 'Europa', 'usa': 'USA', 'ogolem': 'indeks ogólny', 'mieso': 'mięso', 'nabial': 'nabiał', 'zboza': 'zboża', 'oleje': 'oleje',
              'cukier': 'cukier', 'N': 'azot', 'P': 'fosfor', 'K': 'potas', 'sruta': 'śruta rzepakowa', 'olej': 'olej rzepakowy'}


def _zd_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf')


def _zd_k_wiersze(e):
    d = e.get('d') if isinstance(e, dict) else None
    return [x for x in d if isinstance(x, list) and len(x) == 2] if isinstance(d, list) else []


def _zd_k_seria(j, sciezka):
    """Obiekt serii z pliku po ścieżce 'goi/s/goi' (brak = None)."""
    e = j
    for p in sciezka.split('/'):
        e = e.get(p) if isinstance(e, dict) else None
    return e if isinstance(e, dict) else None


def _zd_k_serie(j):
    """Wszystkie serie pliku: {nazwa do raportu: (ścieżka, wiersze)} — z wartościami wierszy jako [dzień lub miesiąc, liczba|None]."""
    out = {}
    for p in ('goi', 'fracht'):
        P = j.get(p) if isinstance(j.get(p), dict) else {}
        for cid, e in (P.get('s') or {}).items() if isinstance(P.get('s'), dict) else ():
            out[f'{p}.{ZD_K_NAZWY.get(cid, cid)}'] = (f'{p}/s/{cid}', _zd_k_wiersze(e))
    for p in ('fao', 'nawozy'):
        P = j.get(p) if isinstance(j.get(p), dict) else {}
        for cid, e in (P.get('s') or {}).items() if isinstance(P.get('s'), dict) else ():
            out[f'{p}.{ZD_K_NAZWY.get(cid, cid)}'] = (f'{p}/s/{cid}', _zd_k_wiersze(e))
    U = j.get('ue') if isinstance(j.get('ue'), dict) else {}
    for pr, v in (U.get('zb') or {}).items() if isinstance(U.get('zb'), dict) else ():
        for c, e in (v or {}).items() if isinstance(v, dict) else ():
            out[f'ue.{pr}.{c}'] = (f'ue/zb/{pr}/{c}', _zd_k_wiersze(e))
    for g in ('rz', 'pl'):
        for c, e in (U.get(g) or {}).items() if isinstance(U.get(g), dict) else ():
            out[f'ue.{g}.{c}'] = (f'ue/{g}/{c}', _zd_k_wiersze(e))
    return out


def zboza_swiezosc(j, now=None):
    """Wiersze świeżości części pliku zboza-dzien.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga).
    Najwyżej ⚠, nigdy ❌; brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    rows = []
    for p, label in ZD_K_ETYKIETA.items():
        P = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = P.get('asof') if isinstance(P.get('asof'), str) else None
        kat, prog = ZD_K_PROG[p]
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(txt, 'month' if p in ('fao', 'nawozy') else 'day', kat, now)
        st = '?' if w is None else ('\u26a0\ufe0f' if w > prog else '✅')
        note = ''
        if st == '\u26a0\ufe0f':
            nt = nx.get(p); pt = _aw_t(nt) if isinstance(nt, str) else None
            note = f'próg {fmt_wiek(prog)}{" roboczych" if kat == "d" else ""} — najwyżej uwaga' + (
                f'; spodziewana publikacja {czas_pl(nt)}' + (' — zaległa (przerwa u źródła?)' if pt and pt < now else '') if pt else '')
        rows.append((label, st, w, txt, note))
    return rows


def zboza_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w zbożach) → lista opisów."""
    zle = []
    for nazwa, (sc, d) in _zd_k_serie(j).items():
        ds = [str(x[0]) for x in d]
        if ds != sorted(set(ds)):
            zle.append(f'{nazwa}: daty nie rosną albo się powtarzają')
        if any(not (_zd_k_num(x[1]) and x[1] > 0) for x in d):
            zle.append(f'{nazwa}: wartość ≤ 0 albo nie-liczba (brak ma być brakiem punktu)')
    for p in ('goi', 'fracht'):
        P = j.get(p) if isinstance(j.get(p), dict) else {}
        for cid, e in (P.get('s') or {}).items() if isinstance(P.get('s'), dict) else ():
            d, st = _zd_k_wiersze(e), (e.get('st') if isinstance(e, dict) else None)
            nm = f'{p}.{ZD_K_NAZWY.get(cid, cid)}'
            if not isinstance(st, dict) or not d:
                continue
            if st.get('dt') != d[-1][0] or (_zd_k_num(st.get('last')) and abs(st['last'] - d[-1][1]) > ZD_K_TOL):
                zle.append(f'{nm}: st.last {st.get("last")} z dnia {st.get("dt")} ≠ ostatni punkt serii {d[-1][1]} z {d[-1][0]}')
            if len(d) > 1 and _zd_k_num(st.get('p1')) and d[-2][1] > 0 and abs((d[-1][1] / d[-2][1] - 1) * 100 - st['p1']) > ZD_K_TOL:
                zle.append(f'{nm}: zmiana kroku {st["p1"]}% ≠ {(d[-1][1] / d[-2][1] - 1) * 100:.2f}% z serii')
            if all(_zd_k_num(st.get(x)) for x in ('lo', 'hi', 'last')) and not (st['lo'] - ZD_K_TOL <= st['last'] <= st['hi'] + ZD_K_TOL):
                zle.append(f'{nm}: ostatni indeks {st["last"]} poza przedziałem 365 dni {st["lo"]}–{st["hi"]}')
            if _zd_k_num(st.get('pos')) and not (0 <= st['pos'] <= 100):
                zle.append(f'{nm}: położenie w przedziale {st["pos"]}% poza 0–100')
        if P.get('asof') and isinstance(P.get('s'), dict):
            e = P['s'].get('goi' if p == 'goi' else 'gofi')
            d = _zd_k_wiersze(e)
            if d and P['asof'] != d[-1][0]:
                zle.append(f'{p}: asof {P["asof"]} ≠ ostatni dzień indeksu ogółem {d[-1][0]}')
    U = j.get('ue') if isinstance(j.get('ue'), dict) else {}
    pl = _zd_k_wiersze(((U.get('zb') or {}).get('pszenica') or {}).get('PL')) if isinstance(U.get('zb'), dict) else []
    if pl and U.get('asof') != pl[-1][0]:
        zle.append(f'ue: asof {U.get("asof")} ≠ ostatni tydzień pszenicy w Polsce {pl[-1][0]}')
    return zle


def _zd_k_zmiany(rows, krok_dni=None, miesiac=False):
    """Zmiany % między sąsiednimi punktami: [(koniec odcinka, zmiana %)]; krok_dni — tylko odstęp dokładnie tylu dni (luka ≠ skok), miesiac — tylko
    kolejne miesiące."""
    out = []
    for a, b in zip(rows, rows[1:]):
        if not (_zd_k_num(a[1]) and _zd_k_num(b[1]) and a[1] > 0):
            continue
        if miesiac:
            ok = str(b[0])[:4].isdigit() and str(a[0])[:4].isdigit() and (int(b[0][:4]) * 12 + int(b[0][5:7])) - (int(a[0][:4]) * 12 + int(a[0][5:7])) == 1
        elif krok_dni:
            ok = _sz_k_dni(a[0], b[0]) == krok_dni
        else:
            ok = _sz_k_dni(a[0], b[0]) is not None
        if ok:
            out.append((b[0], (b[1] / a[1] - 1) * 100))
    return out


def _zd_k_korelacja(a, b):
    n = len(a)
    if n < 3 or n != len(b):
        return None
    ma, mb = sum(a) / n, sum(b) / n
    sa, sb = sum((x - ma) ** 2 for x in a) ** 0.5, sum((y - mb) ** 2 for y in b) ** 0.5
    return None if sa == 0 or sb == 0 else sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


def _zd_k_kor_serii(A, B, ostatnie=36):
    """Korelacja zmian miesięcznych dwóch serii miesięcznych ([[RRRR-MM, liczba]]) na wspólnych kolejnych miesiącach (ostatnie `ostatnie` miesięcy wspólnych);
    → (korelacja, liczba par, zgodnych znaków) albo None, gdy par jest mniej niż ZD_K_KOR_MIN."""
    a = {x[0]: x[1] for x in A if _zd_k_num(x[1]) and x[1] > 0}
    b = {x[0]: x[1] for x in B if _zd_k_num(x[1]) and x[1] > 0}
    ms = sorted(set(a) & set(b))[-ostatnie:]
    za = dict(_zd_k_zmiany([[m, a[m]] for m in ms], miesiac=True))
    zb = dict(_zd_k_zmiany([[m, b[m]] for m in ms], miesiac=True))
    kk = sorted(set(za) & set(zb))
    if len(kk) < ZD_K_KOR_MIN:
        return None
    x, y = [za[m] for m in kk], [zb[m] for m in kk]
    r = _zd_k_korelacja(x, y)
    return None if r is None else (r, len(kk), sum(1 for p, q in zip(x, y) if (p > 0) == (q > 0)))


def _zd_k_pl(r):
    return f'{r:+.2f}'.replace('.', ',')


def zboza_porownania(j, files=None):
    """Progi z testów wstecznych (najwyżej ⚠): skoki w jednym kroku serii, tabela źródła vs seria, korelacje zmian miesięcznych (podindeks zbóż w żywności,
    indeks zbóż świata, indeks nawozów świata) i pszenica w Polsce vs polska.json. → {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    W, U = [], []
    files = files if isinstance(files, dict) else {}
    S = _zd_k_serie(j)
    # skoki
    for grupa, prefiksy, krok, mies, etyk in (('goi', ('goi.',), None, False, 'indeks dzienny: skoki dnia'), ('fracht', ('fracht.',), 7, False, 'indeks frachtu: skoki tygodnia'),
                                                ('fao', ('fao.',), None, True, 'podindeksy żywności: skoki miesiąca'),
                                                ('ue', ('ue.',), 7, False, 'ceny w UE: skoki tygodnia'), ('nawozy', ('nawozy.',), None, True, 'nawozy w UE: skoki miesiąca')):
        ser = {k: v for k, v in S.items() if k.startswith(prefiksy)}
        if not ser:
            continue
        zle = []
        for nazwa, (sc, d) in ser.items():
            for dz, c in _zd_k_zmiany(d, krok, mies):
                if abs(c) > ZD_K_SKOK[grupa]:
                    zle.append((nazwa, dz, c))
        for nazwa, dz, c in zle[:2]:
            zm = f'{c:+.1f}'.replace('.', ',')
            U.append(f'zboża dziennie: {nazwa} {dz} — zmiana o {zm}% w jednym kroku (próg {ZD_K_SKOK[grupa]:g}%; w historii najwyżej {ZD_K_HIST[grupa]}%) — sprawdzić')
        W.append((etyk, '\u26a0\ufe0f' if zle else '✅'))
    # tabela źródła vs seria — tylko indeks dzienny. Tabela frachtu NIE służy do kontroli: 11.10.2026 ma w wierszu Europa zmianę roczną 20 (seria: +10,4%, jak z punktu
    # sprzed 52 tygodni) i w wierszu USA najniższy / najwyższy z 52 tygodni skopiowane z Europy (124 / 170; seria: 112,5 / 157,3) — błędy po stronie źródła; odczyt
    # ostatniej wartości frachtu sprawdza zbieracz przy każdym pobraniu (RuntimeError przy niezgodności), a zmianę roczną całej serii (19,6% wobec 20 w tabeli) dał test ręczny
    # tabela źródła vs seria
    G = j.get('goi') if isinstance(j.get('goi'), dict) else {}
    T = G.get('tab') if isinstance(G.get('tab'), dict) else {}
    rozne = []
    for cid, t in T.items():
        e = (G.get('s') or {}).get(cid) if isinstance(G.get('s'), dict) else None
        st = e.get('st') if isinstance(e, dict) else None
        if not isinstance(st, dict) or not isinstance(t, list) or len(t) != 5:
            continue
        for x, k_ in zip(t, ('last', 'd1', 'y1', 'lo', 'hi')):
            if _zd_k_num(x) and _zd_k_num(st.get(k_)) and abs(x - st[k_]) > ZD_K_TAB[k_]:
                rozne.append(f'{ZD_K_NAZWY.get(cid, cid)} {k_}: tabela {x:g}, seria {st[k_]:g}')
    if T:
        for x in rozne[:2]:
            U.append(f'zboża dziennie: tabela źródła vs seria — {x} (tolerancja zaokrągleń: ostatnia ±0,6, zmiana dnia ±0,6, roczna ±1,6 pkt, przedział ±1) — sprawdzić'.replace('.', ','))
        W.append(('indeks dzienny: tabela źródła vs seria', '\u26a0\ufe0f' if rozne else '✅'))
    # korelacje miesięczne
    gm = ((G.get('s') or {}).get('goi') or {}).get('m') if isinstance(G.get('s'), dict) else None
    fz = _zd_k_wiersze(((j.get('fao') or {}).get('s') or {}).get('zboza')) if isinstance(j.get('fao'), dict) and isinstance(j['fao'].get('s'), dict) else []
    if isinstance(gm, list) and fz:
        r = _zd_k_kor_serii(gm, fz)
        if r:
            zle = r[0] < ZD_K_KOR['fao']
            if zle:
                U.append(f'zboża dziennie: zmiany miesięczne indeksu dziennego vs podindeks zbóż w żywności — korelacja {_zd_k_pl(r[0])} z {r[1]} miesięcy '
                         f'(próg {_zd_k_pl(ZD_K_KOR["fao"])}; w historii 2000–2026 najniżej +0,78) — sprawdzić')
            W.append(('indeks dzienny vs podindeks zbóż w żywności (zmiany miesięczne)', '\u26a0\ufe0f' if zle else '✅'))
    sw = files.get('surowce') if isinstance(files.get('surowce'), dict) else {}
    ix = (((sw.get('mies') or {}).get('ix')) if isinstance(sw.get('mies'), dict) else None) or {}
    wz = _zd_k_wiersze(ix.get('zboza')) if isinstance(ix, dict) else []
    if isinstance(gm, list) and wz:
        r = _zd_k_kor_serii(gm, wz)
        if r:
            zle = r[0] < ZD_K_KOR['wb_zboza']
            if zle:
                U.append(f'zboża dziennie: zmiany miesięczne indeksu dziennego vs indeks zbóż świata (surowce) — korelacja {_zd_k_pl(r[0])} z {r[1]} miesięcy '
                         f'(próg {_zd_k_pl(ZD_K_KOR["wb_zboza"])}; w 35 miesiącach 10.2023–09.2026 najniżej +0,66 w oknach 24 mies.) — sprawdzić')
            W.append(('indeks dzienny vs indeks zbóż świata (zmiany miesięczne)', '\u26a0\ufe0f' if zle else '✅'))
    nw = _zd_k_wiersze(ix.get('nawozy')) if isinstance(ix, dict) else []
    nn = _zd_k_wiersze((((j.get('nawozy') or {}).get('s')) or {}).get('N')) if isinstance(j.get('nawozy'), dict) and isinstance(j['nawozy'].get('s'), dict) else []
    if nn and nw:
        r = _zd_k_kor_serii(nn, nw)
        if r:
            zle = r[0] < ZD_K_KOR['wb_nawozy']
            if zle:
                U.append(f'zboża dziennie: azot w UE vs indeks nawozów świata (zmiany miesięczne) — korelacja {_zd_k_pl(r[0])} z {r[1]} miesięcy '
                         f'(próg {_zd_k_pl(ZD_K_KOR["wb_nawozy"])}; w 35 miesiącach najniżej +0,59 w oknach 24 mies.) — sprawdzić')
            W.append(('azot w UE vs indeks nawozów świata (zmiany miesięczne)', '\u26a0\ufe0f' if zle else '✅'))
    # pszenica w Polsce: dwa pobrania z tego samego portalu
    mine = _zd_k_wiersze((((j.get('ue') or {}).get('zb') or {}).get('pszenica') or {}).get('PL')) if isinstance(j.get('ue'), dict) and isinstance(j['ue'].get('zb'), dict) else []
    po = files.get('polska') if isinstance(files.get('polska'), dict) else {}
    other = {x[0]: x[1] for x in _zd_k_wiersze(po.get('pszenica')) if _zd_k_num(x[1])}
    wsp = [(x[0], x[1], other[x[0]]) for x in mine if x[0] in other and _zd_k_num(x[1])]
    if wsp:
        d, a, b = wsp[-1]
        zle = abs(a - b) > ZD_K_TOL
        if zle:
            U.append(f'zboża dziennie: pszenica w Polsce {d} — {a:g} EUR/t tu, {b:g} EUR/t w danych o Polsce (ten sam portal; poprawka źródła w jednym z pobrań?) — sprawdzić'.replace('.', ','))
        W.append(('pszenica w Polsce: ten sam portal w dwóch plikach', '\u26a0\ufe0f' if zle else '✅'))
    return {'wiersze': W, 'uwagi': U}


def zboza_kontrola(j, files, R):
    """Kontrola pliku zboza-dzien.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i progi z testów wstecznych (najwyżej ⚠). Brak pliku albo inna wersja =
    None (raport bez linii)."""
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = zboza_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'zboza-dzien.json: sprzeczność w pliku — {z}')
    P = zboza_porownania(j, files)
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v349: giełdy scentralizowane, DEX i otwarte pozycje (data/gieldy.json, data/dex.json) ----------------------------------------------------------------
# Pliki w PLIKI (przed plikami krypto dziennie; wiek pliku wg rytmu: zapis co przebieg, część giełd co 55 min, otwarte pozycje co 55 min → 3 h) i wiersze świeżości
# (lista SWIEZOSC bez zmian), najwyżej ⚠️: salda i przepływy giełd — wiek odczytu źródła (czas z nagłówków odpowiedzi: Date − Age, nie później niż Last-Modified)
# do 4 h (źródło odświeża co ok. 30 min, my co 55 min, ponowienie po błędzie co 25 min); obrót DEX — doba danych (ostatnia pełna doba UTC, zwykle gotowa ok. 03:00 UTC
# następnego dnia → normalny wiek 3–27 h) do 60 h (jedna opuszczona doba); otwarte pozycje — jak giełdy (4 h).
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (suma sald ≠ suma wierszy, wiersze nie malejąco, migawka dobowa ≠ odczyt, udziały sieci ≠ 100%, suma
# największych protokołów ponad sumę, suma rodzajów otwartych pozycji ≠ suma). Informacje ℹ️ w raporcie (nigdy ⚠️/❌, bo progi NIE mają testu wstecznego):
# * podejrzany skok listy portfeli — przepływ 24 h > 10% salda i większy niż cały obrót spot giełdy (dz = 2 w pliku; litera planu F6Z1 „obrót < 1% salda” jest
#   podzbiorem i nie łapie przykładu planu — Bitstamp 10.10.2026) oraz przepływ > 10% salda przy saldzie ≥ 100 mln USD w innym układzie obrotu (dz = 1).
#   Historii obrotu spot źródło nie daje, więc próg nie ma testu wstecznego; z historii sald (nagrania 10.10.2026) dzienna zmiana salda o ponad 10%
#   zdarzała się w 2,6% dób Bitstamp i 0,7% dób OKX — dlatego tylko informacja;
# * znak przepływu 7 dni wszystkich giełd (bez wykluczonych) wobec znaku sumy przepływów BTC + ETH z drugiego źródła (cm.json, ostatnie 7 dób) — OBA ZBIORY RÓŻNE
#   (inne portfele, wszystkie aktywa wobec dwóch monet, inne okno), więc rozbieżność znaku to tylko informacja, nigdy błąd i nigdy jedna liczba;
# * przepływ okna 7 dni ponad 25% salda i okna 30 dni ponad 50% salda przy saldzie ≥ 10 mln USD (flagi dz7 i dz30 = 2: giełda poza sumą tego okna; źródło nie daje obrotu z tych
#   okien, więc tylko próg względem salda; odczyt 13.10.2026: Bitstamp +1,27 mld w 7 dni po skoku z 9–10.10, Bitvavo −0,37 mld w 30 dni przy saldzie 0,26 mld) — informacja;
# * skok sumy sald o ponad 15% między dwiema kolejnymi dobami migawki (zmiana listy portfeli albo krach) — informacja;
# * obrót DEX wobec obrotu spot giełd scentralizowanych poza przedziałem 0,03–0,60 (dwa odczyty: 0,09 przy sobocie 10.10 i 0,16 przy dniu roboczym 13.10 wobec
#   okna kroczącego 24 h) — informacja; doba szacunkowa (brak punktu szeregu zgodnego z podsumowaniem) — informacja.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'gieldy')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['gieldy'] = 180
PLIKI.insert(PLIKI.index('krypto-dzien'), 'dex')      # v349: DEX i otwarte pozycje — przed plikami krypto dziennie
LIMIT_MIN['dex'] = 180
AW_BEZ_BLEDU.update({k: 'giełdy i DEX — część z błędem zostaje z datą (v349); wiek danych w wierszach świeżości' for k in ('gieldy', 'dex', 'dex_oi')})
GX_K_ETYKIETA = {'cex': 'Giełdy: salda i przepływy netto giełd scentralizowanych (szacunek z portfeli)',
                 'dex': 'DEX: obrót ostatniej pełnej doby UTC', 'oi': 'Kontrakty na łańcuchu: otwarte pozycje'}
GX_K_PROG = {'cex': ('ts', 240), 'dex': ('day', 3600), 'oi': ('ts', 240)}
GX_K_SKOK_SUMY = 15.0        # % — zmiana sumy sald między dwiema kolejnymi dobami migawki (informacja)
GX_K_DEX_CEX = (0.03, 0.60)  # obrót DEX doby ÷ obrót spot giełd scentralizowanych (okno kroczące 24 h) — informacja
GX_K_TOL_UDZIAL = 0.6        # pkt proc. — suma udziałów sieci wobec 100 (zaokrąglenia do 0,01 × 11 pozycji)


def _gx_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))


def gx_swiezosc(gx, dx, now=None):
    """Wiersze świeżości trzech części: (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️, nigdy ❌; plik albo część bez daty — '?' (brak pliku
    = brak wierszy, plik jest już w PLIKI i raport pokaże „plik nie wczytany”)."""
    now = now or NOW
    zr = {'cex': ((gx or {}).get('cex') or {}).get('src_at') if isinstance(gx, dict) else None,
          'dex': ((dx or {}).get('dex') or {}).get('day') if isinstance(dx, dict) else None,
          'oi': ((dx or {}).get('oi') or {}).get('src_at') if isinstance(dx, dict) else None}
    rows = []
    for p, label in GX_K_ETYKIETA.items():
        pl = gx if p == 'cex' else dx
        if not isinstance(pl, dict) or pl.get('v') != 1:
            continue
        txt = zr[p]
        if not isinstance(txt, str) or not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        kind, prog = GX_K_PROG[p]
        w = wiek_danych(txt, kind, 'k', now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = f'próg {fmt_wiek(prog)} — najwyżej uwaga' if st == '⚠️' else ''
        err = (pl.get('err') or {}).get(p) if isinstance(pl.get('err'), dict) else None
        if err and st == '⚠️':
            note += f'; ostatni błąd pobrania: {str(err)[:80]}'
        rows.append((label, st, w, txt, note))
    return rows


def gx_spojnosc(gx, dx):
    """Sprzeczności wewnątrz plików (jedyny powód ❌ w giełdach i DEX) → lista opisów."""
    zle = []
    c = gx.get('cex') if isinstance(gx, dict) and isinstance(gx.get('cex'), dict) else None
    if c is not None:
        R = [r for r in (c.get('rows') or []) if isinstance(r, dict)]
        z = c.get('razem') if isinstance(c.get('razem'), dict) else {}
        B = [r['bal'] for r in R if _gx_k_num(r.get('bal')) and r['bal'] > 0]
        if _gx_k_num(z.get('bal')) and abs(sum(B) - z['bal']) > len(B):
            zle.append(f'giełdy: suma sald {z["bal"]} ≠ suma wierszy {sum(B)}')
        if z.get('n') != len(R) or z.get('n_bal') != len(B):
            zle.append(f'giełdy: liczby giełd w sumach ({z.get("n")}, {z.get("n_bal")}) ≠ wiersze ({len(R)}, {len(B)})')
        if B != sorted(B, reverse=True):
            zle.append('giełdy: wiersze nie malejąco wg salda')
        h = gx.get('hist') if isinstance(gx.get('hist'), list) else []
        ds = [str(x[0]) for x in h if isinstance(x, list) and x]
        if ds != sorted(set(ds)):
            zle.append('giełdy: migawka dobowa — doby nie rosną albo się powtarzają')
        if h and isinstance(h[-1], list) and len(h[-1]) >= 3 and (str(h[-1][0]) != str(c.get('src_at'))[:10] or h[-1][1] != z.get('bal')):
            zle.append(f'giełdy: ostatnia migawka dobowa {h[-1][:2]} ≠ odczyt ({str(c.get("src_at"))[:10]}, {z.get("bal")})')
    d = dx.get('dex') if isinstance(dx, dict) and isinstance(dx.get('dex'), dict) else None
    if d is not None:
        if _gx_k_num(d.get('s24')) and d['s24'] > 0:
            T = [r for r in (d.get('top') or []) if isinstance(r, list) and len(r) >= 4 and _gx_k_num(r[1])]
            if sum(r[1] for r in T) > d['s24'] * 1.001:
                zle.append('DEX: suma największych protokołów większa niż suma doby')
            if any(_gx_k_num(r[3]) and abs(r[3] - r[1] / d['s24'] * 100) > 0.011 for r in T):
                zle.append('DEX: udział protokołu ≠ wartość ÷ suma doby')
        S = d.get('sieci')
        if isinstance(S, list) and S:
            sh = sum(r[3] for r in S if isinstance(r, list) and len(r) >= 4 and _gx_k_num(r[3]))
            if abs(sh - 100) > GX_K_TOL_UDZIAL:
                zle.append(f'DEX: udziały sieci sumują się do {sh:.2f}%')
            if _gx_k_num(d.get('sieci_sum')) and _gx_k_num(d.get('s30')) and abs(d['sieci_sum'] / d['s30'] - 1) > 0.011:
                zle.append('DEX: suma sieci ≠ suma 30 dób')
        h = dx.get('hist') if isinstance(dx.get('hist'), list) else []
        ds = [str(x[0]) for x in h if isinstance(x, list) and x]
        if ds != sorted(set(ds)):
            zle.append('DEX: szereg dobowy — doby nie rosną albo się powtarzają')
        L = [x for x in h if isinstance(x, list) and len(x) >= 3 and x[0] == d.get('day')]
        if h and (not L or L[0][1] != d.get('s24')):
            zle.append(f'DEX: szereg dobowy nie ma doby {d.get("day")} z sumą odczytu')
        if _gx_k_num(d.get('n')) and _gx_k_num(d.get('n_act')) and d['n_act'] > d['n']:
            zle.append('DEX: protokołów z obrotem więcej niż protokołów')
    o = dx.get('oi') if isinstance(dx, dict) and isinstance(dx.get('oi'), dict) else None
    if o is not None and _gx_k_num(o.get('on')):
        T = [r for r in (o.get('top') or []) if isinstance(r, list) and len(r) >= 3 and _gx_k_num(r[2])]
        if sum(r[2] for r in T) > o['on'] * 1.001:
            zle.append('kontrakty: suma największych protokołów większa niż suma na łańcuchu')
        if [r[2] for r in T] != sorted((r[2] for r in T), reverse=True):
            zle.append('kontrakty: protokoły nie malejąco')
        K = o.get('kinds') if isinstance(o.get('kinds'), dict) else {}
        if K and abs(sum(v for v in K.values() if _gx_k_num(v)) - o['on']) > (o.get('n_on') or 0) + len(K):
            zle.append('kontrakty: suma rodzajów ≠ suma na łańcuchu')
    return zle


def gx_cm_znak(cm, asof_max=7):
    """Suma przepływów netto BTC + ETH w USD z ostatnich 7 wierszy każdego aktywa w cm.json (kolumna net_usd) → (suma, ostatnia doba) albo None."""
    if not isinstance(cm, dict) or not isinstance(cm.get('assets'), dict) or not isinstance(cm.get('cols'), list) or 'net_usd' not in cm['cols']:
        return None
    i = cm['cols'].index('net_usd')
    s, last = 0.0, None
    for a in ('btc', 'eth'):
        d = (cm['assets'].get(a) or {}).get('d') if isinstance(cm['assets'].get(a), dict) else None
        V = [r for r in (d or []) if isinstance(r, list) and len(r) > i and _gx_k_num(r[i])][-asof_max:]
        if len(V) < asof_max:
            return None
        s += sum(r[i] for r in V)
        last = max(last or '', str(V[-1][0]))
    return s, last


def gx_porownania(gx, dx, cm):
    """Informacje ℹ️ (bez ⚠️/❌, progi bez testu wstecznego) → {'wiersze': [(opis, znak)]}."""
    W = []
    c = gx.get('cex') if isinstance(gx, dict) and isinstance(gx.get('cex'), dict) else None
    if c is not None:
        R = [r for r in (c.get('rows') or []) if isinstance(r, dict)]
        s2 = [r['name'] for r in R if r.get('dz') == 2]
        s1 = [r['name'] for r in R if r.get('dz') == 1]
        W.append((('podejrzany skok listy portfeli (przepływ 24 h > 10% salda i większy niż obrót spot): ' + ', '.join(s2[:5]) + ' — wykluczone z sum przepływów') if s2
                  else 'podejrzany skok listy portfeli (próg planu F6Z1): brak', 'ℹ️' if s2 else '✅'))
        if s1:
            W.append(('przepływ 24 h ponad 10% salda (saldo ≥ 100 mln USD): ' + ', '.join(s1[:5]) + ' — do sprawdzenia, czy to nie zmiana listy portfeli', 'ℹ️'))
        for p_, nm_, lim_ in (('dz7', '7 dni', 25), ('dz30', '30 dni', 50)):
            sw = [r['name'] for r in R if r.get(p_) == 2 and r.get('dz') != 2]
            if sw:
                W.append((f'przepływ {nm_} ponad {lim_}% salda (saldo ≥ 10 mln USD): ' + ', '.join(sw[:6]) + (f' (+{len(sw) - 6})' if len(sw) > 6 else '') + f' — poza sumą {nm_}', 'ℹ️'))
        z = c.get('razem') if isinstance(c.get('razem'), dict) else {}
        h = gx.get('hist') if isinstance(gx.get('hist'), list) else []
        if len(h) >= 2 and all(isinstance(x, list) and len(x) >= 2 and _gx_k_num(x[1]) and x[1] > 0 for x in h[-2:]):
            ch = (h[-1][1] / h[-2][1] - 1) * 100
            W.append((f'suma sald między dobami {h[-2][0]} → {h[-1][0]}: {ch:+.1f}%'.replace('.', ','),
                      'ℹ️' if abs(ch) > GX_K_SKOK_SUMY else '✅'))
        zc = gx_cm_znak(cm)
        if zc and _gx_k_num(z.get('in7')):
            a, b = z['in7'], zc[0]
            W.append((f'znak przepływu 7 dni: giełdy z listy (wszystkie aktywa) {"plus" if a > 0 else "minus" if a < 0 else "zero"}; BTC + ETH z drugiego źródła '
                      f'(do {zc[1]}) {"plus" if b > 0 else "minus" if b < 0 else "zero"} (inne zbiory portfeli i aktywów — tylko informacja)',
                      '✅' if (a > 0) == (b > 0) or a == 0 or b == 0 else 'ℹ️'))
    d = dx.get('dex') if isinstance(dx, dict) and isinstance(dx.get('dex'), dict) else None
    if d is not None:
        if d.get('est'):
            W.append((f'DEX: doba {d.get("day")} szacunkowa (brak punktu szeregu zgodnego z podsumowaniem odpowiedzi)', 'ℹ️'))
        sp = ((gx or {}).get('cex') or {}).get('razem', {}).get('spot') if isinstance(gx, dict) and isinstance(gx.get('cex'), dict) else None
        if _gx_k_num(d.get('s24')) and _gx_k_num(sp) and sp > 0:
            r = d['s24'] / sp
            W.append((f'obrót DEX doby ÷ obrót spot giełd scentralizowanych (kroczące 24 h): {r:.2f}'.replace('.', ','), 'ℹ️' if not GX_K_DEX_CEX[0] <= r <= GX_K_DEX_CEX[1] else '✅'))
    return {'wiersze': W}


def gx_kontrola(files, R):
    """Kontrola plików gieldy.json i dex.json bez sieci: sprzeczności w plikach (❌ = BŁĄD) i informacje ℹ️. Brak obu plików = None (raport bez linii)."""
    gx, dx = files.get('gieldy'), files.get('dex')
    gx = gx if isinstance(gx, dict) and gx.get('v') == 1 else None
    dx = dx if isinstance(dx, dict) and dx.get('v') == 1 else None
    if gx is None and dx is None:
        return None
    zle = gx_spojnosc(gx, dx)
    for z in zle[:5]:
        R['bledy'].append(f'giełdy i DEX: sprzeczność w pliku — {z}')
    P = gx_porownania(gx, dx, files.get('cm'))
    nie = []
    for pl in (gx, dx):
        ok = pl.get('ok') if pl else None
        if isinstance(ok, dict):
            nie += sorted(k for k, v in ok.items() if v is False)
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v320: surowce — raporty miesięczne (data/surowce-raporty.json) i drugi kanał pozycji CFTC ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian), najwyżej ⚠️; data danych = dzień wydania raportu (ropa, zboża) albo koniec
# miesiąca ceny (uran). Progi z testu wstecznego (ws53/v320-surowce46/bt/bt_swiezosc.py, 10.10.2026; wiek jak wiek_danych, kontrola co godzinę
# i o 06:20 UTC): ropa — kalendarz z oficjalnej reguły wydawcy 2010–2027 (zgodny z 24 terminami 2026–2027), najwyższy wiek tuż przed nowym
# wydaniem 35,76 dnia → próg 38 dni: 0 ⚠️ (35 dni — 57 kontroli, 0,04%); zboża — kalendarz 2026 (najwyżej 35,06 dnia) i model najgorszego
# przypadku (raport 8.–12. dnia, plik CSV do następnego dnia roboczego: 38,08 dnia) → próg 40 dni: 0 ⚠️ poza przerwą w pracy urzędu (raport
# odwołany: X 2013, I 2019, X 2025 — wtedy ⚠️ jest prawdziwe); uran — publikacja do 7. dnia następnego miesiąca (07.10.2026 był już wrzesień),
# najwyżej 38,22 dnia → próg 45 dni: 0 ⚠️ (zapas 7 dni na późniejszą publikację). ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (wolne
# moce ≠ zdolność − wydobycie, kraje OPEC poza porozumieniem ≠ cały OPEC − objęci porozumieniem, zapasy w % zużycia ≠ zapasy ÷ zużycie, pierwszy
# miesiąc prognozy ≠ miesiąc wydania, miesiące nie rosną, zero albo wartość ujemna zamiast braku, zła jednostka). Podział OPEC+ (v320 po
# przeglądzie; OPEC+ urzędu = tylko kraje objęte porozumieniem, cały OPEC — także Iran, Libia, Wenezuela): OPEC+ = objęci + pozostali uczestnicy
# (±SR_K_TOL) i cały OPEC ≥ objęci — inaczej ⚠️ (źródło niespójne); test wsteczny ws53/v320-surowce46/bt/bt_opecplus.py (arkusze 5 wydań
# 10.2024–10.2026, 207 miesięcy): 0 ⚠️ (fałszywych 0%). Wcześniejsze „OPEC+ ≥ OPEC” usunięte — zła przesłanka. Uran z funduszu fizycznego (ceny.uran w surowce.json) wobec średniej branżowej z końca miesiąca —
# tylko ℹ️: inne definicje i chwile wyceny (fundusz wycenia uran po cenach dnia; średnia branżowa — koniec miesiąca), bez progu.
# Pozycje funduszy USA (pozycje.cftc w surowce.json, plik tygodniowy urzędu) wobec tego samego raportu w drugim kanale urzędu (zbiór danych
# Socrata 72hh-3qpy, futures only; jedno zapytanie GET bez klucza, ok. 0,2 MB): open interest i 13 pozycji grup ostatniego raportu oraz open
# interest i netto funduszy zarządzających z 13 tygodni. Test wsteczny (ws53/v320-surowce46/bt/bt_cftc_socrata.py): pliki roczne 2024–2026 wobec
# drugiego kanału, 30 rynków, 145 tygodni (02.01.2024 – 06.10.2026), 4208 raportów, 58 912 liczb — 0 różnic, 0 raportów tylko w jednym kanale
# → KAŻDA różnica = ⚠️ (fałszywych 0%). Drugi kanał bez tego raportu (publikuje później) albo bez odpowiedzi — ℹ️, nigdy ❌.
import urllib.parse   # v320: adres zapytania drugiego kanału (biblioteka standardowa; ponowny import jest nieszkodliwy)

SR_K_ETYKIETA = {'ropa': 'surowce: podaż ropy OPEC+ (raport miesięczny — szacunek i prognoza)', 'zboza': 'surowce: bilans zbóż świata i USA (raport miesięczny)',
                 'uran': 'surowce: uran — średnia branżowa z końca miesiąca'}
SR_K_PROG = {'ropa': ('w', 38 * 24 * 60), 'zboza': ('w', 40 * 24 * 60), 'uran': ('w', 45 * 24 * 60)}
SR_K_DATA = {'ropa': 'wyd', 'zboza': 'wyd', 'uran': 'asof'}
SR_K_TOL = 0.011         # zaokrąglenia: wolne moce (3 miejsca), zapasy w % zużycia (2 miejsca)
SR_K_URAN_DNI = 4        # dni — wycena funduszu najwyżej tyle przed końcem miesiąca (koniec miesiąca w weekend albo w święto w Kanadzie)
SR_K_TOWARY = {'pszenica': 'pszenica', 'kukurydza': 'kukurydza', 'ryz': 'ryż', 'soja': 'soja'}
SR_K_SOC_URL = 'https://publicreporting.cftc.gov/resource/72hh-3qpy.json'
SR_K_SOC_POLA = (('oi', None, 'open_interest_all'), ('prod', 0, 'prod_merc_positions_long'), ('prod', 1, 'prod_merc_positions_short'),
                 ('swap', 0, 'swap_positions_long_all'), ('swap', 1, 'swap__positions_short_all'), ('swap', 2, 'swap__positions_spread_all'),
                 ('mm', 0, 'm_money_positions_long_all'), ('mm', 1, 'm_money_positions_short_all'), ('mm', 2, 'm_money_positions_spread'),
                 ('other', 0, 'other_rept_positions_long'), ('other', 1, 'other_rept_positions_short'), ('other', 2, 'other_rept_positions_spread'),
                 ('nonrept', 0, 'nonrept_positions_long_all'), ('nonrept', 1, 'nonrept_positions_short_all'))
SR_K_SOC_DNI = 13 * 7    # dni wstecz od ostatniego raportu (13 tygodni historii w pliku strony)
SR_K_SOC_S = 30          # s — limit zapytania (10.10.2026: 0,2 MB w 1,7 s)


def _sr_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf')


def _sr_k_wiersze(rows):
    return [x for x in rows if isinstance(x, list) and len(x) == 2] if isinstance(rows, list) else []


def surowce_raporty_swiezosc(j, now=None):
    """Wiersze świeżości części pliku surowce-raporty.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga).
    Najwyżej ⚠️, nigdy ❌; brak pliku albo inna wersja = brak wierszy; część bez daty danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    rows = []
    for p, label in SR_K_ETYKIETA.items():
        P = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = P.get(SR_K_DATA[p]) if isinstance(P.get(SR_K_DATA[p]), str) else None
        kat, prog = SR_K_PROG[p]
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(txt, 'day', kat, now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            nt = nx.get(p); pt = _aw_t(nt) if isinstance(nt, str) else None
            note = f'próg {fmt_wiek(prog)} — najwyżej uwaga' + (
                f'; spodziewana publikacja {czas_pl(nt)}' + (' — zaległa (przerwa w pracy urzędu?)' if pt and pt < now else '') if pt else '')
        rows.append((label, st, w, txt, note))
    return rows


def surowce_raporty_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w raportach miesięcznych) → lista opisów."""
    zle = []
    R = j.get('ropa') if isinstance(j.get('ropa'), dict) else None
    if R:
        if R.get('u') != 'mln b/d':
            zle.append(f'ropa: jednostka {R.get("u")} zamiast mln b/d')
        if isinstance(R.get('wyd'), str) and R.get('pr_od') != R['wyd'][:7]:
            zle.append(f'ropa: pierwszy miesiąc prognozy {R.get("pr_od")} ≠ miesiąc wydania {R["wyd"][:7]}')
        S = R.get('s') if isinstance(R.get('s'), dict) else {}
        for cid, rows in S.items():
            d = _sr_k_wiersze(rows)
            ms = [str(x[0]) for x in d]
            if ms != sorted(set(ms)):
                zle.append(f'ropa.{cid}: miesiące nie rosną albo się powtarzają')
            zero = cid in ('wolne', 'poza')   # wyliczone różnice: 0 dozwolone (zaokrąglenie), wydobycie i zdolność > 0
            if any(x[1] is not None and not (_sr_k_num(x[1]) and (x[1] >= 0 if zero else x[1] > 0)) for x in d):
                zle.append(f'ropa.{cid}: wartość ' + ('ujemna' if zero else '≤ 0') + ' albo nie-liczba (brak ma być null)')
        O, C, B = ({str(x[0]): x[1] for x in _sr_k_wiersze(S.get(k)) if _sr_k_num(x[1]) and x[1] > 0} for k in ('opec', 'moce', 'objeci'))   # złe liczby — wyżej
        for m, v in ({str(x[0]): x[1] for x in _sr_k_wiersze(S.get('wolne'))}).items():
            if _sr_k_num(v) and m in O and m in C and abs(max(C[m] - O[m], 0.0) - v) > SR_K_TOL:
                zle.append(f'ropa: wolne moce {m} = {v} ≠ zdolność − wydobycie ({C[m] - O[m]:.3f})'); break
        for m, v in ({str(x[0]): x[1] for x in _sr_k_wiersze(S.get('poza'))}).items():
            if _sr_k_num(v) and m in O and m in B and abs(max(O[m] - B[m], 0.0) - v) > SR_K_TOL:
                zle.append(f'ropa: kraje OPEC poza porozumieniem {m} = {v} ≠ cały OPEC − objęci porozumieniem ({O[m] - B[m]:.3f})'); break
    Zb = j.get('zboza') if isinstance(j.get('zboza'), dict) else None
    if Zb:
        if Zb.get('u') != 'mln t':
            zle.append(f'zboza: jednostka {Zb.get("u")} zamiast mln t')
        for cid, regs in ((Zb.get('k') or {}).items() if isinstance(Zb.get('k'), dict) else ()):
            for reg, e in ((regs or {}).items() if isinstance(regs, dict) else ()):
                for nazwa, x in (('bieżący', e), ('poprzedni', e.get('p') if isinstance(e, dict) else None), ('sezon wcześniej', e.get('r0') if isinstance(e, dict) else None)):
                    if not isinstance(x, dict):
                        continue
                    if any(x.get(a) is not None and not (_sr_k_num(x.get(a)) and x[a] >= 0) for a in ('prod', 'uzycie', 'zapasy', 'su', 'eksp')):
                        zle.append(f'zboza.{cid}.{reg} ({nazwa}): wartość ujemna albo nie-liczba'); continue
                    su, zp, uz = x.get('su'), x.get('zapasy'), x.get('uzycie')
                    if _sr_k_num(su) and _sr_k_num(zp) and _sr_k_num(uz) and uz > 0 and abs(zp / uz * 100 - su) > SR_K_TOL:
                        zle.append(f'zboza.{cid}.{reg} ({nazwa}): zapasy w % zużycia {su} ≠ {zp / uz * 100:.2f}')
    U = j.get('uran') if isinstance(j.get('uran'), dict) else None
    if U:
        for k in ('d', 'lt'):
            d = _sr_k_wiersze(U.get(k))
            ds = [str(x[0]) for x in d]
            if ds != sorted(set(ds)):
                zle.append(f'uran.{k}: daty nie rosną albo się powtarzają')
            if any(x[1] is not None and not (_sr_k_num(x[1]) and x[1] > 0) for x in d):
                zle.append(f'uran.{k}: wartość ≤ 0 albo nie-liczba (brak ma być null)')
    return zle


def surowce_raporty_porownania(j, su=None, sh=None):
    """Porównania z plików strony (bez sieci, najwyżej ⚠️): uran z funduszu fizycznego (dzień wyceny najwyżej SR_K_URAN_DNI dni przed końcem
    miesiąca) wobec średniej branżowej z tego końca miesiąca — ℹ️; podział OPEC+: OPEC+ = objęci porozumieniem + pozostali uczestnicy (±SR_K_TOL)
    i cały OPEC ≥ objęci, brak podziału w pliku — ⚠️ (źródło niespójne albo zły identyfikator serii); podsumowanie raportów.
    → {'wiersze': [(opis, znak)], 'uwagi': [...]}."""
    W, U = [], []
    R = j.get('ropa') if isinstance(j.get('ropa'), dict) else None
    if R:
        S = R.get('s') if isinstance(R.get('s'), dict) else {}
        O, P, B, I = ({str(x[0]): x[1] for x in _sr_k_wiersze(S.get(k)) if _sr_k_num(x[1])} for k in ('opec', 'opec_plus', 'objeci', 'inni'))
        suma = sorted(m for m in set(P) & set(B) & set(I) if abs(P[m] - B[m] - I[m]) > SR_K_TOL)
        mn = sorted(m for m in set(O) & set(B) if O[m] < B[m] - SR_K_TOL)
        bez = not (B and I)
        if suma:
            U.append('surowce: podaż ropy — OPEC+ ≠ kraje OPEC objęte porozumieniem + pozostali uczestnicy w miesiącach ' + ', '.join(suma[:4])
                     + ' (źródło niespójne) — sprawdzić')
        if mn:
            U.append('surowce: podaż ropy — cały OPEC mniejszy niż kraje OPEC objęte porozumieniem w miesiącach ' + ', '.join(mn[:4])
                     + ' (źródło niespójne) — sprawdzić')
        if bez:
            U.append('surowce: podaż ropy — w pliku brak podziału OPEC+ (kraje OPEC objęte porozumieniem, pozostali uczestnicy) — sprawdzić')
        W.append((f'ropa: wydanie {R.get("wyd") or "—"}, szacunki do {R.get("asof") or "—"}, prognoza od {R.get("pr_od") or "—"}; '
                  'OPEC+ = objęci porozumieniem + pozostali uczestnicy, cały OPEC ≥ objęci', '⚠️' if suma or mn or bez else '✅'))
    Zb = j.get('zboza') if isinstance(j.get('zboza'), dict) else None
    if Zb:
        K = Zb.get('k') if isinstance(Zb.get('k'), dict) else {}
        bez = [SR_K_TOWARY.get(c, c) for c in SR_K_TOWARY if c not in K]
        npw = sum(1 for R2 in K.values() if isinstance(R2, dict) for e in R2.values() if isinstance(e, dict) and isinstance(e.get('p'), dict))
        W.append((f'zboża: raport {Zb.get("mies") or "—"} (nr {Zb.get("nr") or "—"}), sezon {Zb.get("rok") or "—"}; z poprzednim raportem: {npw} z 8 wpisów'
                  + (f'; brak: {", ".join(bez)}' if bez else ''), 'ℹ️'))
    Ur = j.get('uran') if isinstance(j.get('uran'), dict) else None
    if Ur:
        C = {str(x[0]): x[1] for x in _sr_k_wiersze(Ur.get('d')) if _sr_k_num(x[1])}
        F = {}
        for src in (((sh or {}).get('d') or {}).get('uran') if isinstance(sh, dict) and isinstance(sh.get('d'), dict) else None,
                    (((su or {}).get('ceny') or {}).get('uran') or {}).get('d') if isinstance(su, dict) and isinstance(su.get('ceny'), dict) else None):
            for x in _sr_k_wiersze(src):
                if isinstance(x[0], str) and _sr_k_num(x[1]):
                    F[x[0][:10]] = x[1]
        para = None
        for d in sorted(C, reverse=True):
            try:
                k0 = dt.date.fromisoformat(d)
            except ValueError:
                continue
            f = max((x for x in F if (k0 - dt.timedelta(days=SR_K_URAN_DNI)).isoformat() <= x <= d), default=None)
            if f:
                para = (d, C[d], f, F[f]); break
        if para:
            r = (para[3] / para[1] - 1) * 100
            W.append((f'uran {para[0]}: wycena funduszu fizycznego ({para[2]}) {para[3]:.2f} vs średnia branżowa {para[1]:.2f} USD/lb ({r:+.2f}%) — '
                      'informacja (inne definicje i chwile wyceny), bez progu'.replace('.', ','), 'ℹ️'))
        else:
            od = min(F) if F else None
            W.append((f'uran: brak wspólnego dnia (wycena funduszu od {od or "—"}, ostatni koniec miesiąca średniej branżowej {max(C) if C else "—"}) — '
                      'porównanie od pierwszego końca miesiąca z wyceną funduszu', 'ℹ️'))
    return {'wiersze': W, 'uwagi': U}


def surowce_raporty_kontrola(files, R):
    """Kontrola pliku surowce-raporty.json bez sieci: sprzeczności w pliku (❌ = BŁĄD) i porównania (najwyżej ⚠️). Brak pliku albo inna wersja =
    None (raport bez linii)."""
    j = files.get('surowce-raporty') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = surowce_raporty_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'surowce-raporty.json: sprzeczność w pliku — {z}')
    P = surowce_raporty_porownania(j, files.get('surowce'), files.get('surowce-hist'))
    R['uwagi'] += P['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'], 'czesci_bez_odpowiedzi': nie}


def surowce_cftc_url(kody, od):
    """Zapytanie drugiego kanału: wiersze rynków `kody` od dnia `od`, tylko pola porównania, rosnąco (bez klucza)."""
    q = {'$select': 'cftc_contract_market_code,report_date_as_yyyy_mm_dd,' + ','.join(c for _, _, c in SR_K_SOC_POLA),
         '$where': 'cftc_contract_market_code in(' + ','.join(f"'{c}'" for c in kody) + f") AND report_date_as_yyyy_mm_dd >= '{od}T00:00:00.000'",
         '$order': 'report_date_as_yyyy_mm_dd,cftc_contract_market_code', '$limit': '5000'}
    return SR_K_SOC_URL + '?' + urllib.parse.urlencode(q, quote_via=urllib.parse.quote)


def surowce_cftc_porownanie(C, wiersze):
    """Pozycje USA z pliku strony (pozycje.cftc: {rynek: {code, asof, oi, pos, h}}) wobec wierszy drugiego kanału → {'wiersze', 'uwagi', 'raport'}:
    ostatni raport — open interest i 13 pozycji grup każdego rynku; historia — open interest i netto funduszy zarządzających (h). Każda różnica = ⚠️;
    rynek bez wiersza w drugim kanale — ℹ️ (kanał publikuje później)."""
    I = {}
    for r in wiersze if isinstance(wiersze, list) else []:
        if isinstance(r, dict) and isinstance(r.get('cftc_contract_market_code'), str) and isinstance(r.get('report_date_as_yyyy_mm_dd'), str):
            I[(r['cftc_contract_market_code'].strip(), r['report_date_as_yyyy_mm_dd'][:10])] = r

    def n(r, c):
        try:
            return int(str(r.get(c)).strip())
        except (TypeError, ValueError):
            return None
    E = {k: e for k, e in C.items() if isinstance(e, dict) and isinstance(e.get('code'), str) and isinstance(e.get('asof'), str)}
    w = max((e['asof'] for e in E.values()), default=None)
    rozne, brak, nl, nh = [], [], 0, 0
    for k, e in sorted(E.items()):
        if e['asof'] == w:
            r = I.get((e['code'], w))
            if r is None:
                brak.append(k)
            else:
                pos = e.get('pos') if isinstance(e.get('pos'), dict) else {}
                for g, i, col in SR_K_SOC_POLA:
                    a = e.get('oi') if g == 'oi' else ((pos.get(g) or [None] * 3)[i] if isinstance(pos.get(g), list) and len(pos.get(g)) > i else None)
                    b = n(r, col)
                    nl += 1
                    if a != b:
                        rozne.append(f'{k} {w} {g if i is None else g + "." + ("long", "short", "spread")[i]}: plik {a} vs {b}')
        h = e.get('h') if isinstance(e.get('h'), dict) else {}
        for d, oi, net in zip(h.get('d') or [], h.get('oi') or [], h.get('net') or []):
            r = I.get((e['code'], str(d)))
            if r is None or d == e['asof']:
                continue
            nh += 1
            ml, ms_ = n(r, 'm_money_positions_long_all'), n(r, 'm_money_positions_short_all')
            if oi != n(r, 'open_interest_all') or (ml is None or ms_ is None or net != ml - ms_):
                rozne.append(f'{k} {d} historia: OI {oi} / netto {net} vs {n(r, "open_interest_all")} / {(ml - ms_) if ml is not None and ms_ is not None else None}')
    W, U = [], []
    if w is None:
        return {'wiersze': [], 'uwagi': [], 'raport': None}
    hist = f'{nh} {_odm(nh, "wcześniejszy wpis", "wcześniejsze wpisy", "wcześniejszych wpisów")} rynków (open interest i netto funduszy zarządzających)'
    wyn = f' — różne liczby: {len(rozne)}' if rozne else ' — zgodne'
    if brak and len(brak) == len([e for e in E.values() if e['asof'] == w]):
        W.append((f'raport {w}: drugi kanał nie ma jeszcze tego raportu (publikuje później); porównano {hist}{wyn}', '⚠️' if rozne else 'ℹ️'))
    else:
        ile = len([e for e in E.values() if e['asof'] == w]) - len(brak)
        W.append((f'raport {w}: {ile} {_odm(ile, "rynek", "rynki", "rynków")} × {len(SR_K_SOC_POLA)} liczb i {hist}'
                  + (f'; bez wiersza w drugim kanale: {", ".join(brak[:5])}' if brak else '') + wyn,
                  '⚠️' if rozne else ('ℹ️' if brak else '✅')))
    if rozne:
        U.append(f'surowce: pozycje funduszy USA — plik tygodniowy i drugi kanał urzędu różnią się ({len(rozne)} {_odm(len(rozne), "liczba", "liczby", "liczb")}, np. ' + '; '.join(rozne[:3])
                 + ') — w 2024–2026 kanały były identyczne; sprawdzić, czy urząd nie poprawił raportu')
    return {'wiersze': W, 'uwagi': U, 'raport': w}


def surowce_cftc_kontrola(j, R, pobierz=None):
    """Drugi kanał pozycji USA — jedno zapytanie GET bez klucza (pobierz(url) → bajty; domyślnie get). Brak pliku v2 albo pozycji = None (bez
    zapytania, raport bez linii); błąd zapytania — ℹ️ z opisem, nigdy ❌."""
    C = (((j or {}).get('pozycje') or {}).get('cftc') if isinstance(j, dict) and j.get('v') == 2 and isinstance(j.get('pozycje'), dict) else None)
    if not isinstance(C, dict) or not any(isinstance(e, dict) and isinstance(e.get('asof'), str) and isinstance(e.get('code'), str) for e in C.values()):
        return None
    w = max(e['asof'] for e in C.values() if isinstance(e, dict) and isinstance(e.get('asof'), str))
    try:
        od = (dt.date.fromisoformat(w) - dt.timedelta(days=SR_K_SOC_DNI)).isoformat()
    except ValueError:
        return None
    kody = sorted({e['code'] for e in C.values() if isinstance(e, dict) and isinstance(e.get('code'), str) and re.fullmatch(r'[0-9A-Z]{6}', e['code'])})
    try:
        b = pobierz(surowce_cftc_url(kody, od)) if pobierz else get(surowce_cftc_url(kody, od), timeout=SR_K_SOC_S)[1]
        rows = json.loads(b)
        if not isinstance(rows, list):
            raise ValueError('odpowiedź nie jest listą')
    except Exception as e:  # noqa
        return {'wiersze': [(f'raport {w}: drugi kanał nie odpowiada ({str(e)[:80]}) — bez porównania', 'ℹ️')], 'uwagi': [], 'raport': w}
    P = surowce_cftc_porownanie(C, rows)
    R['uwagi'] += P['uwagi']
    return P


# ---------------------------------------------------------------- v304: Polska (data/polska.json) ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian — test liczy jej wiersze), najwyżej ⚠️; pole next pliku mówi, kiedy
# spodziewana jest publikacja. Progi z testu wstecznego (ws53/v304-polska/bt/bt_swiezosc.py, 08.10.2026; wiek liczony wiek_danych jak tu;
# kontrola o 06:20 UTC i — po pushu — o dowolnej godzinie; modele dostępności pesymistyczne):
#  złoto (dni robocze w Polsce, 2014–10.2026): 36 h robocze — ⚠️ w 0,26% kontroli o 06:20 i 0,71% godzinowych (święta: Wigilia + 2 dni Bożego
#    Narodzenia, Wielkanoc); 48 h — 0,21% / 0,17%;
#  ceny hurtowe (dni obowiązywania wt–sob, 2019–10.2026): 36 h robocze — 0,39% / 1,13% (ponad 1%), 48 h — 0,32% / 0,29% → 48 h;
#  gaz i prąd (dostawa codziennie, także w święta): v304b — 6 h kalendarzowych od końca dnia ostatniej dostawy (recenzja v304: 24 h dawało ⚠️ dopiero
#    po drugiej brakującej publikacji); ws53/v304b-polska/bt2/bt_swiezosc.out: 0% kontroli ponad próg także przy publikacji o 22:00 UTC (zwykle
#    indeksy na jutro są ok. 13:50–15:30 czasu polskiego, a wiek najnowszej dostawy wynosi 0); jeden brak publikacji = ⚠️ już o 06:20 (6 h 20 min);
#  stacje (poniedziałki, pobranie w nocy po środzie, 2016–10.2026): 9 dni — 3,0%, 11 dni — 2,3% (do 2022 biuletyn nie wychodził w tygodnie
#    Wielkanocy i Bożego Narodzenia: przerwy 14–21 dni), 16 dni — 0,69% / 0,70% → 16 dni (od 06.2022 bez przerw: 9–16 dni — 0%); model: plik
#    powstaje w środę po południu, pobranie w nocy ze środy na czwartek (ten sam dzień co bramka zbieracza i pole next — v304b);
#  pszenica (tydzień do niedzieli, publikacja w czwartek, 2016–10.2026): 13 dni — 0% poza prawdziwą przerwą źródła (07–09.2021: 12 tygodni
#    bez danych — tam ⚠️ jest słuszny).
# Porównanie (najwyżej ⚠️): złoto w zł/g (dzień D) wobec ceny złota w USD/oz z pliku surowców (LBMA PM z archiwum funduszu) × kurs USD/PLN z pliku
# rynków (kursy referencyjne EBC) ÷ 31,1034768 — z OSTATNIEJ sesji przed D, w której są obie liczby (cena dnia D jest liczona z cen poprzedniej
# sesji: mediana różnicy 0,16%, a z ceną tego samego dnia — 0,60%). Test wsteczny 2013–10.2026 (bt/bt_zloto.py, 3345 dni): p99 1,45%, maks.
# 4,45%; próg 3,0% — ponad próg 0,09% dni (5 lat: 0,25%, ostatnie 12 mies. przy zmiennym złocie 2026: 0,83%); próg 2,0% dawałby 4,55% w
# ostatnich 12 mies. ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (zła jednostka, zero zamiast braku, daty nie rosną, średnia UE z innego
# tygodnia niż cena Polski, cena bez podatków nie niższa niż z podatkami, zły wpis q, lista v8 niezgodna z podatkami w cenach z pliku).
# v304b — ceny na stacjach: ⚠️, gdy NAJNOWSZY tydzień paliwa ma oznaczenie q (zbieracz: cena sprzeczna z ceną hurtową przy każdej stawce VAT
# stosowanej w Polsce — test wsteczny 2019–10.2026: 0 z 792 tygodni, ws53/v304b-polska/bt2/bt_q.py), ℹ️ dla starszych tygodni z q w pliku; ℹ️, gdy
# podatki w cenie najnowszego tygodnia zmieniły się o ≥ 10% wobec tygodnia wcześniej (bt2/bt_podatki.py, 2005–10.2026: 0,93% / 0,84% tygodni
# benzyny / oleju — wyłącznie przy zmianach podatków: 2010 akcyza na olej, 02.2022 VAT 8%, 01.2023 koniec obniżki, 2026 kolejne edycje obniżki
# VAT i akcyzy) — to opis, nie błąd; ℹ️, gdy najnowszy tydzień jest na liście v8 (obniżony VAT na paliwa — zbieracz rozpoznaje go z podatków
# w cenie benzyny: akcyza i opłaty przy VAT 23% poniżej 0,85 × minimalnej akcyzy UE; test wsteczny 2005–10.2026: 0 pomyłek, bt3/bt_vat.py).
# v312 (recenzja v304b): PIERWSZY tydzień nowej serii v8 (tydzień wcześniej w pliku — bez obniżonego VAT albo brak wcześniejszego tygodnia) = ⚠️
# „początek obniżki VAT na paliwa — potwierdzić, że obniżka obowiązuje”, raz na serię (kolejne tygodnie serii — ℹ️ jak dotąd): reguła v8 zależy od
# kursu złotego i nie odróżnia obniżki VAT od ceny zaniżonej przez źródło (opis przy PL_V8_* w zbieraczu). Test wsteczny 2005–10.2026
# (ws53/v312-drobne6/bt/bt_v312.py, 1087 tygodni): 4 takie tygodnie (07.02.2022, 06.04.2026, 17.08.2026, 05.10.2026 — wszystkie prawdziwe obniżki;
# 0,37% tygodni), poza nimi 0. ⚠️, gdy w najnowszym tygodniu benzyny albo oleju nie ma ceny bez podatków (brak arkusza albo kolumn w biuletynie —
# zbieracz zgłasza wtedy częściowy błąd części „stacje”; strona traci cenę bez podatków, opis zmiany podatków i obniżony VAT); test wsteczny: 0 z 1087.
import bisect   # v304: ostatnia sesja przed dniem ceny (biblioteka standardowa; ponowny import jest nieszkodliwy)
PL_ETYKIETA = {'zloto': 'Polska: złoto w zł/g (dni robocze w Polsce)', 'hurt': 'Polska: ceny hurtowe paliw (dni obowiązywania wt–sob)',
               'energia': 'Polska: gaz i prąd z giełdy (dzień dostawy, 7 dni w tygodniu)',
               'stacje': 'Polska: ceny na stacjach na tle UE (poniedziałki, pobierane w nocy)',
               'pszenica': 'Polska: pszenica (tydzień do niedzieli, publ. w czwartek)'}
PL_PROG = {'zloto': ('d', 36 * 60), 'hurt': ('d', 48 * 60), 'energia': ('w', 6 * 60), 'stacje': ('w', 16 * 24 * 60), 'pszenica': ('w', 13 * 24 * 60)}
PL_SERIE = {'zloto': (None,), 'hurt': ('pb95', 'on'), 'energia': ('gaz', 'prad'), 'stacje': ('pb95', 'on'), 'pszenica': (None,)}
PL_JEDN = {'zloto': 'PLN/g', 'hurt': 'PLN/l', 'energia': 'PLN/MWh', 'stacje': 'PLN/l', 'pszenica': 'EUR/t'}
PL_ZLOTO_PROG = 3.0      # % — patrz komentarz wyżej (test wsteczny)
PL_ZLOTO_DNI = 10        # najnowszych notowań złota w zł/g, wśród których szukamy pary do porównania (starsze — bez porównania)
PL_OZ = 31.1034768       # g w uncji trojańskiej
PL_POD_PROG = 10.0       # % — zmiana podatków w cenie na stacjach tydzień do tygodnia (opis ℹ️; test wsteczny wyżej)
PL_PALIWO = {'pb95': 'benzyna 95', 'on': 'olej napędowy'}
PL_QOPIS = {'nisko': 'niższa niż cena hurtowa z VAT', 'wysoko': 'o ponad 30% wyższa niż cena hurtowa z 23% VAT'}
PL_V8 = (23.0, 359.0, 0.85)   # v304b: stawka podstawowa VAT %, minimalna akcyza UE na benzynę (EUR/1000 l), próg — jak w zbieraczu (opis wiersza ℹ️)
# v312: próg w euro, podatki w złotych — reguła zależy od kursu złotego (opis przy PL_V8_* w zbieraczu); stąd ⚠️ dla pierwszego tygodnia serii


def _pl_e(j, p, k):
    P = j.get(p) if isinstance(j.get(p), dict) else None
    if P is None:
        return None
    e = P if k is None else P.get(k)
    return e if isinstance(e, dict) else None


def polska_swiezosc(j, now=None):
    """Wiersze świeżości części pliku polska.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). Data części
    z dwiema seriami = starsza z ich ostatnich dat (obie mają być świeże). Najwyżej ⚠️, nigdy ❌; brak pliku albo inna wersja = brak wierszy."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    nx = j.get('next') if isinstance(j.get('next'), dict) else {}
    rows = []
    for p, label in PL_ETYKIETA.items():
        ls = [_su_ostatni(_pl_e(j, p, k)) for k in PL_SERIE[p]]
        if not any(ls):
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        txt = min(x[0] for x in ls if x)
        kat, prog = PL_PROG[p]
        w = wiek_danych(txt, 'day', kat, now)
        st = '?' if w is None else ('⚠️' if w > prog else '✅')
        note = ''
        if st == '⚠️':
            pt = _aw_t(nx.get(p)) if isinstance(nx.get(p), str) else None
            note = f'próg {fmt_wiek(prog)}' + (' (godziny robocze)' if kat == 'd' else '') + ' — najwyżej uwaga' + (
                f'; spodziewana publikacja {czas_pl(nx[p])}' + (' — zaległa (święto albo przerwa źródła?)' if pt < now else '') if pt else '')
        if not all(ls):
            note = (note + '; ' if note else '') + 'jedna z dwóch serii bez danych'
        rows.append((label, st, w, txt, note))
    return rows


def polska_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w części Polska): jednostka inna niż w umowie pliku, zero zamiast braku (poza prądem — średnia
    doby może wynieść 0,00), daty nie rosną albo się powtarzają, średnia UE z tygodnia, którego nie ma w cenach Polski, kurs ≤ 0; v304b: ceny bez
    podatków, wpisy q, lista v8 (tygodnie z obniżonym VAT — ta sama reguła co w zbieraczu, policzona z liczb pliku). → lista opisów."""
    zle = []
    if not isinstance(j, dict):
        return zle
    for p, ks in PL_SERIE.items():
        for k in ks:
            e = _pl_e(j, p, k)
            if e is None:
                continue
            n = p if k is None else f'{p}.{k}'
            if e.get('u') != PL_JEDN[p]:
                zle.append(f'{n}: jednostka {e.get("u")} zamiast {PL_JEDN[p]}')
            d = [x for x in (e.get('d') or []) if isinstance(x, list) and len(x) == 2]
            ds = [str(x[0]) for x in d]
            if ds != sorted(set(ds)):
                zle.append(f'{n}: daty nie rosną albo się powtarzają')
            if k != 'prad' and any(x[1] == 0 and not isinstance(x[1], bool) for x in d):
                zle.append(f'{n}: wartość 0 (brak ma być null)')
            if p == 'stacje':
                ue = [x for x in (e.get('ue') or []) if isinstance(x, list) and len(x) == 2]
                if any(str(x[0]) not in set(ds) for x in ue):
                    zle.append(f'{n}: średnia UE z tygodnia bez ceny Polski')
                if any(x[1] == 0 and not isinstance(x[1], bool) for x in ue):
                    zle.append(f'{n}: średnia UE 0 (brak ma być null)')
                # v304b: ceny bez podatków (Polska, UE) — tylko z tygodni z ceną Polski, dodatnie i niższe niż ceny z podatkami; wpisy q
                V = {str(x[0]): x[1] for x in d}
                U = {str(x[0]): x[1] for x in ue}
                for kk, ref, opis in (('n', V, 'cena bez podatków'), ('ue_n', U, 'średnia UE bez podatków')):
                    xs = [x for x in (e.get(kk) or []) if isinstance(x, list) and len(x) == 2]
                    if any(str(x[0]) not in V for x in xs):
                        zle.append(f'{n}: {opis} z tygodnia bez ceny Polski')
                    if any(not isinstance(x[1], (int, float)) or isinstance(x[1], bool) or x[1] <= 0 for x in xs):
                        zle.append(f'{n}: {opis} ≤ 0 albo nie liczba')
                    elif any(isinstance(ref.get(str(x[0])), (int, float)) and x[1] >= ref[str(x[0])] for x in xs):
                        zle.append(f'{n}: {opis} nie niższa niż z podatkami')
                q = e.get('q')
                if q is not None and (not isinstance(q, list) or any(not isinstance(x, list) or len(x) != 4 or str(x[0]) not in V
                                                                     or x[1] not in PL_QOPIS for x in q)):
                    zle.append(f'{n}: zły wpis q (tydzień niepewny)')
    S8 = j.get('stacje') if isinstance(j.get('stacje'), dict) else {}
    e95 = _pl_e(j, 'stacje', 'pb95')
    if 'v8' in S8 or e95:   # v304b: tygodnie z obniżonym VAT — poniedziałki z cenami benzyny, zgodne z podatkami w cenie z tego samego pliku
        D95 = {str(x[0]): x[1] for x in ((e95 or {}).get('d') or []) if isinstance(x, list) and len(x) == 2}
        v8 = S8.get('v8', [])
        if not isinstance(v8, list) or any(not isinstance(x, str) or x not in D95 for x in v8) or v8 != sorted(set(v8)):
            zle.append('stacje.v8: zły wpis (tydzień spoza cen benzyny w Polsce, powtórzony albo daty nie rosną)')
        else:
            jest = polska_v8(j)
            if jest is not None and jest != v8:
                zle.append('stacje.v8: lista tygodni z obniżonym VAT niezgodna z podatkami w cenach z pliku (' + ', '.join(sorted(set(jest) ^ set(v8))[:3]) + ')')
    ku = _pl_e(j, 'stacje', 'kurs')
    if ku and any(isinstance(x, list) and len(x) == 2 and isinstance(x[1], (int, float)) and not isinstance(x[1], bool) and x[1] <= 0 for x in ku.get('d') or []):
        zle.append('stacje.kurs: kurs ≤ 0')
    return zle


def polska_v8(j):
    """v304b: tygodnie z obniżonym VAT na paliwa policzone z liczb pliku (benzyna 95: z podatkami, bez podatków, kurs — ta sama reguła i stałe co
    w zbieraczu, PL_V8) → posortowana lista poniedziałków; None, gdy pliku nie da się tak sprawdzić (brak cen benzyny)."""
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731
    e = _pl_e(j, 'stacje', 'pb95')
    if e is None:
        return None
    N = {str(x[0]): x[1] for x in (e.get('n') or []) if isinstance(x, list) and len(x) == 2 and num(x[1])}
    K = {str(x[0]): x[1] for x in ((_pl_e(j, 'stacje', 'kurs') or {}).get('d') or []) if isinstance(x, list) and len(x) == 2 and num(x[1])}
    out = []
    for x in (e.get('d') or []):
        if not (isinstance(x, list) and len(x) == 2 and num(x[1])):
            continue
        d, p = str(x[0]), x[1]
        n, k = N.get(d), K.get(d)
        if num(n) and num(k) and 0 < n < p and k > 0 and (p - n) - p * PL_V8[0] / (100 + PL_V8[0]) < PL_V8[2] * PL_V8[1] * k / 1000:
            out.append(d)
    return sorted(out)


def polska_zloto(j, su, rynki):
    """Złoto w zł/g wobec ceny w USD/oz × kurs USD/PLN ÷ 31,1034768 z ostatniej sesji przed dniem ceny, w której są obie liczby (pliki strony,
    bez zapytań). → {'wiersze': [(opis, znak)], 'uwagi': [...]}"""
    Z = [x for x in ((_pl_e(j, 'zloto', None) or {}).get('d') or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[1], (int, float))
         and not isinstance(x[1], bool) and x[1] > 0]
    gd = (((su or {}).get('ceny') or {}).get('gold') or {}).get('d') if isinstance(su, dict) and isinstance(su.get('ceny'), dict) else None
    G = {str(x[0]): x[1] for x in (gd or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[1], (int, float)) and not isinstance(x[1], bool) and x[1] > 0}
    FX = {}
    for v in (((rynki or {}).get('fx') or {}).values() if isinstance(rynki, dict) and isinstance(rynki.get('fx'), dict) else ()):
        r = v.get('rates') if isinstance(v, dict) and isinstance(v.get('rates'), dict) else {}
        if v.get('base') == 'USD' and isinstance(r.get('PLN'), (int, float)) and not isinstance(r.get('PLN'), bool) and r['PLN'] > 0 and isinstance(v.get('date'), str):
            FX[v['date'][:10]] = r['PLN']
    gs = sorted(G)
    for D, v in reversed(Z[-PL_ZLOTO_DNI:]):
        i = bisect.bisect_left(gs, str(D))
        f = gs[i - 1] if i else None
        if f is None or f not in FX:
            continue
        r = (v / (G[f] * FX[f] / PL_OZ) - 1) * 100
        zn = '⚠️' if abs(r) > PL_ZLOTO_PROG else '✅'
        W = [(f'złoto w Polsce {D} (zł/g) vs cena w USD z {f} × kurs USD/PLN: {r:+.2f}% (próg {PL_ZLOTO_PROG:g}%)'.replace('.', ','), zn)]
        U = [f'Polska: złoto {D} — cena w zł/g różni się o {r:+.2f}% od ceny w USD × kurs z {f} (próg {PL_ZLOTO_PROG:g}% z testu wstecznego) — sprawdzić'
             .replace('.', ',')] if zn == '⚠️' else []
        return {'wiersze': W, 'uwagi': U}
    return {'wiersze': [('złoto w Polsce: bez porównania — w plikach strony brak sesji z ceną w USD i kursem USD/PLN tuż przed najnowszymi cenami w zł', 'ℹ️')],
            'uwagi': []}


def polska_stacje(j):
    """v304b: ceny na stacjach — oznaczenia q z pliku (⚠️ najnowszy tydzień paliwa, ℹ️ starsze tygodnie) i zmiana podatków w cenie najnowszego
    tygodnia wobec tygodnia wcześniej (≥ PL_POD_PROG %, przerwa ≤ 14 dni; ℹ️ — opis zmiany, nie błąd). → {'wiersze': [(opis, znak)], 'uwagi': [...]}"""
    W, U, bez_n = [], [], []
    f3 = lambda v: f'{v:.3f}'.replace('.', ',')   # noqa: E731
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731
    for c, nazwa in PL_PALIWO.items():
        e = _pl_e(j, 'stacje', c)
        d = [x for x in ((e or {}).get('d') or []) if isinstance(x, list) and len(x) == 2 and num(x[1])]
        if not d:
            continue
        V = {str(x[0]): x[1] for x in d}
        last = str(d[-1][0])
        q = [x for x in (e.get('q') if isinstance(e.get('q'), list) else []) if isinstance(x, list) and len(x) == 4 and x[1] in PL_QOPIS
             and str(x[0]) in V]
        for x in sorted(q, key=lambda y: str(y[0]), reverse=True):
            h = f3(x[3]) if num(x[3]) else '—'
            txt = (f'ceny na stacjach: {nazwa} z {x[0]} — {f3(V[str(x[0])])} zł/l, cena ze źródła {PL_QOPIS[x[1]]} (hurt z {x[2]}: {h} zł/l bez VAT)'
                   ' — tydzień oznaczony jako niepewny')
            if str(x[0]) == last:
                W.append((txt, '⚠️'))
                U.append(f'Polska: {txt} (strona pokazuje cenę z dopiskiem, bez zmiany w tygodniu) — sprawdzić biuletyn')
            else:
                W.append((txt + ' (starszy tydzień w pliku)', 'ℹ️'))
        N = {str(x[0]): x[1] for x in (e.get('n') or []) if isinstance(x, list) and len(x) == 2 and num(x[1])}
        if last not in N:   # v312 (recenzja v304b): najnowszy tydzień paliwa bez ceny bez podatków — wiersz ⚠️ niżej (jeden dla obu paliw)
            bez_n.append(f'{nazwa} ({last})')
        if len(d) < 2:
            continue
        pr = str(d[-2][0])
        try:
            gap = (dt.date.fromisoformat(last[:10]) - dt.date.fromisoformat(pr[:10])).days
        except ValueError:
            continue
        if last not in N or pr not in N or gap > 14:
            continue
        ta, tb = V[pr] - N[pr], V[last] - N[last]
        if not (ta > 0 and tb > 0 and N[pr] > 0):
            continue
        r, rn = (tb / ta - 1) * 100, (N[last] / N[pr] - 1) * 100
        if abs(r) >= PL_POD_PROG:
            pc = lambda v: f'{v:+.1f}%'.replace('.', ',')   # noqa: E731
            W.append((f'ceny na stacjach: {nazwa} {last} — podatki w cenie {f3(ta)} → {f3(tb)} zł/l ({pc(r)}), cena bez podatków {pc(rn)}'
                      f' (próg {PL_POD_PROG:g}% — zmiana podatków; strona ją opisuje)', 'ℹ️'))
    if bez_n:
        txt = ('ceny na stacjach: w najnowszym tygodniu brak ceny bez podatków — ' + ', '.join(bez_n) + '; nie było jej w biuletynie (zmiana pliku'
               ' źródła?) — strona nie pokaże ceny bez podatków, opisu zmiany podatków ani obniżonego VAT')
        W.append((txt, '⚠️'))
        U.append(f'Polska: {txt} — sprawdzić biuletyn (arkusz cen bez podatków)')
    S8 = j.get('stacje') if isinstance(j.get('stacje'), dict) else {}
    e = _pl_e(j, 'stacje', 'pb95')
    d = [x for x in ((e or {}).get('d') or []) if isinstance(x, list) and len(x) == 2 and num(x[1])]
    q95 = {str(x[0]) for x in ((e or {}).get('q') if isinstance((e or {}).get('q'), list) else []) if isinstance(x, list) and len(x) == 4}
    if d and isinstance(S8.get('v8'), list) and str(d[-1][0]) in S8['v8'] and str(d[-1][0]) not in q95:   # v304b: najnowszy tydzień z obniżonym VAT — opis
        last = str(d[-1][0])
        N = {str(x[0]): x[1] for x in (e.get('n') or []) if isinstance(x, list) and len(x) == 2 and num(x[1])}
        K = {str(x[0]): x[1] for x in ((_pl_e(j, 'stacje', 'kurs') or {}).get('d') or []) if isinstance(x, list) and len(x) == 2 and num(x[1])}
        p, n, k = d[-1][1], N.get(last), K.get(last)
        ile, pr = '', f'{PL_V8[2]:g}'.replace('.', ',')
        if num(n) and num(k) and k > 0:
            ile = (f' (akcyza i opłaty, jakie musiałyby być w cenie benzyny przy VAT {PL_V8[0]:g}%: {f3((p - n) - p * PL_V8[0] / (100 + PL_V8[0]))} zł/l,'
                   f' mniej niż {pr} × minimalna akcyza UE {f3(PL_V8[1] * k / 1000)} zł/l)')
        txt = f'ceny na stacjach: tydzień {last} — obniżony VAT na paliwa{ile}; strona to opisuje'
        pw = str(d[-2][0]) if len(d) > 1 else None   # v312 (recenzja v304b): tydzień wcześniej w pliku — ta sama seria v8 czy jej początek
        if pw is not None and pw in S8['v8']:
            W.append((txt, 'ℹ️'))
        else:   # pierwszy tydzień nowej serii (raz na serię) — reguła v8 zależy od kursu złotego i nie odróżnia obniżki od ceny zaniżonej przez źródło
            txt += (' — początek obniżki VAT na paliwa (' + (f'tydzień wcześniej, {pw}, bez obniżonego VAT' if pw else 'w pliku brak wcześniejszego tygodnia')
                    + '): potwierdzić, że obniżka obowiązuje')
            W.append((txt, '⚠️'))
            U.append(f'Polska: {txt} (to wniosek z podatków w cenie benzyny w biuletynie; tak samo wyglądałaby cena zaniżona przez źródło albo duże osłabienie złotego)')
    return {'wiersze': W, 'uwagi': U}


def polska_kontrola(files, R):
    """Kontrola pliku polska.json bez sieci: sprzeczności wewnątrz pliku (❌ = BŁĄD) i porównanie złota (najwyżej ⚠️). Brak pliku = None."""
    j = files.get('polska')
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    zle = polska_spojnosc(j)
    for z in zle[:5]:
        R['bledy'].append(f'polska.json: sprzeczność w pliku — {z}')
    P = polska_zloto(j, files.get('surowce'), files.get('rynki'))
    S = polska_stacje(j)   # v304b: tygodnie niepewne (q) i zmiana podatków w cenach na stacjach
    R['uwagi'] += P['uwagi'] + S['uwagi']
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': zle, 'wiersze': P['wiersze'] + S['wiersze'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v295c: złoto i surowce a krypto (data/zloto-krypto.json) ----------------------------------------------------------------
# Zasoby wydobytego złota do szacunku wielkości rynku (słupek „Złoto (szacunek)”) to stała z datą stanu w zbieraczu (ZK_ZLOTO), aktualizowana ręcznie
# co najmniej raz w roku (wydawca publikuje co kwartał). Stan starszy niż ZK_ZASOBY_MAX_MIES miesięcy = uwaga (przypomnienie, nigdy błąd); data
# stanu z pliku strony (ryn.zloto.t_d) — bez sieci i bez czytania kodu zbieracza.
ZK_ZASOBY_MAX_MIES = 13   # v297c: 13 miesięcy kalendarzowych od daty stanu (dotąd 456 dni ≈ 15 miesięcy): stała aktualizowana co najmniej raz
                          # w roku + miesiąc zapasu; wydawca publikuje co kwartał (z kwartalnym raportem popytu) — po 13 miesiącach są już
                          # co najmniej 3 nowsze stany, więc uwaga nie bywa przedwczesna


def _zk_plus_mies(d, m):
    """Data d + m miesięcy kalendarzowych; dzień, którego nie ma w miesiącu docelowym → ostatni dzień miesiąca (31.01 + 1 = 28.02 / 29.02)."""
    y, k = divmod(d.month - 1 + m, 12)
    y, k = d.year + y, k + 1
    nast = dt.date(y + (k == 12), k % 12 + 1, 1)
    return dt.date(y, k, min(d.day, (nast - dt.timedelta(days=1)).day))


def zk_kontrola(j, R, now=None):
    """Plik zloto-krypto.json → None (brak pliku albo części ryn.zloto z prawdziwą datą stanu) albo {'zasoby_d', 'wiek_dni', 'termin', 'status'};
    dziś później niż data stanu + ZK_ZASOBY_MAX_MIES miesięcy (termin) — uwaga w R['uwagi'] (⚠️, nigdy ❌ ani BŁĄD)."""
    ryn = j.get('ryn') if isinstance(j, dict) else None
    z = ryn.get('zloto') if isinstance(ryn, dict) else None
    d = _dzien(z.get('t_d')) if isinstance(z, dict) else None
    if d is None:
        return None
    d0, dzis = dt.date.fromisoformat(d), (now or NOW).date()
    termin, n = _zk_plus_mies(d0, ZK_ZASOBY_MAX_MIES), (dzis - d0).days
    st = '⚠️' if dzis > termin else '✅'
    if st == '⚠️':
        R['uwagi'].append(f'złoto i surowce a krypto: zasoby wydobytego złota (szacunek wielkości rynku) są ze stanu na {d} — {n} dni temu '
                          f'(ponad {ZK_ZASOBY_MAX_MIES} miesięcy, termin {termin.isoformat()}); zaktualizować stałą ZK_ZLOTO w zbieraj_dane.py '
                          f'najnowszym szacunkiem (wydawca publikuje co kwartał)')
    return {'zasoby_d': d, 'wiek_dni': n, 'termin': termin.isoformat(), 'status': st}


# ---------------------------------------------------------------- kontrola ----------------------------------------------------------------
# ---------------------------------------------------------------- v355 (zwiad 2): TARGET krajów strefy euro, rejestry MiCA, druga kontrola ETF ARKB ----------------------------------------------------------------
# (1) data/target.json (EBC, miesięcznie): miesiąc danych nie starszy niż TG_K_OKRES_DNI dni od końca miesiąca (publikacja ok. 31 dni po końcu miesiąca: dane
#     za sierpień 2026 — Last-Modified 1.10.2026; kolejne wydania wypadają więc ok. 1. dnia drugiego miesiąca po miesiącu danych; ponad 50 dni = źródło spóźnione
#     o 19 dni — bez dłuższego testu wstecznego, bo w nagraniach jest jedno wydanie); suma sald wszystkich krajów, EBC i banków spoza strefy = 0 (w danych
#     2026-08: −0,00001 mln EUR; uwaga dopiero od TG_K_SUMA mln EUR); ten sam miesiąc i kraj w data/instytucje.json (panel „dane urzędowe”, 9 krajów, to samo
#     źródło, inne zapytanie) — różnica ponad TG_K_ZGODNE mln EUR = uwaga. Najwyżej ⚠️, nigdy ❌ ani BŁĄD.
# (2) data/mica.json (rejestry MiCA): wiek pliku wykazu (nagłówek Last-Modified) nie większy niż MC_K_PLIK_DNI dni (w nagraniach 11.10.2026: plik z 7.10, najnowsze
#     wpisy z końca sierpnia — wykaz zmienia się nieregularnie, więc próg szeroki); spójność: suma firm w krajach = liczba firm, liczba firm ≤ liczba wierszy,
#     usługi ≤ liczba firm, szereg narastający kończy się liczbą firm z poprawną datą; udział wierszy z błędną datą ≤ MC_K_ZLE_PCT %. Najwyżej ⚠️.
# (3) ARKB (druga, niezależna kontrola przepływów ETF bitcoina; BEZ nowej liczby na stronie): plik emitenta ma tylko jeden dzień (liczba BTC w funduszu i wartość),
#     więc każdy przebieg zapisuje go w kontrola/ark-arkb.csv razem z przepływem ARKB pokazanym na stronie (etf.json). Przepływ dnia D = (BTC[D] − BTC[poprzedni
#     zapisany dzień]) × cena BTC z pliku [D] — porównanie z przepływem strony z dnia D albo z sesji poprzedzającej D (do zbadania, z którym dniem emitent zgłasza
#     zmianę; do czasu zebrania historii obie możliwości są zgodne). Zgodne, gdy różnica ≤ max(ARK_TOL_MLN; ARK_TOL_PCT % |wyliczenia|). ⚠️ dopiero przy ≥ ARK_MIN_POR
#     porównaniach z ostatnich ARK_OKNO i większości poza progiem; pojedyncza różnica to ℹ️. Plik nieaktualny (ostatni dzień o ponad ARK_PLIK_DNI dni przed ostatnią
#     sesją strony) = ⚠️. Zapis dni: ARK_DNI. Najwyżej ⚠️ (nigdy ❌ ani BŁĄD); w raporcie tylko różnice i daty (bez liczb emitenta).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'target')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['target'] = 48 * 60   # zapis co przebieg (a sprawdzenie źródła raz na dobę) — wiek pliku; wiek miesiąca danych ocenia wiersz świeżości
PLIKI.insert(PLIKI.index('krypto-dzien'), 'mica')
LIMIT_MIN['mica'] = 48 * 60
PLIKI.insert(PLIKI.index('krypto-dzien'), 'etf-zapas')   # v360: zapas przepływów ETF krypto z plików emitenta — przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['etf-zapas'] = 12 * 60   # odświeżany co 6 h (co godzinę, gdy źródło główne ETF milczy); wiek dnia danych ocenia wiersz „ETF krypto” w świeżości
AW_BEZ_BLEDU.update({'target': 'TARGET (EBC) — część z błędem zostaje z datą (v355); wiek danych w wierszu świeżości',
                     'mica': 'rejestry MiCA — część z błędem zostaje z datą (v355); wiek danych w wierszach świeżości'})
TG_K_ETYKIETA = 'TARGET: salda krajów strefy euro (EBC, miesięcznie)'
TG_K_OKRES_DNI = 50
TG_K_SUMA = 50.0      # mln EUR — uwaga, gdy suma sald różni się od zera o więcej (w danych 0,00001; bramka zbieracza 1000)
TG_K_ZGODNE = 0.5     # mln EUR — dwa pliki tego samego źródła (zaokrąglenie do 2 miejsc: różnica 0)
MC_K_ETYKIETA = {'casp': 'Rejestry MiCA: wykaz firm z licencją CASP (plik zmieniany nieregularnie)',
                 'emt': 'Rejestry MiCA: wykaz emitentów tokenów powiązanych z walutą (EMT)'}
MC_K_PLIK_DNI = 45
MC_K_ZLE_PCT = 10.0   # % wierszy z datą spoza okna obowiązywania MiCA (w nagraniu 11.10.2026: 5 z 370 = 1,4%)
ARK_URL = 'https://assets.ark-funds.com/fund-documents/funds-etf-csv/ARK_21SHARES_BITCOIN_ETF_ARKB_HOLDINGS.csv'
ARK_CSV = 'ark-arkb.csv'
ARK_KOL = ['date', 'btc', 'usd', 'site_flow_musd', 'read_at']   # pusta komórka = brak (nigdy 0)
ARK_DNI = 60
ARK_OKNO = 5
ARK_MIN_POR = 3
ARK_TOL_MLN, ARK_TOL_PCT = 1.0, 10.0
ARK_PRZERWA = 5        # dni — dwa zapisane dni dalej od siebie nie tworzą pary
ARK_PLIK_DNI = 4
ARK_TIMEOUT = 30
ARK_LIMIT = 300000     # bajtów odczytu (plik ma ok. 4 KB)


def _tg_k_ym_koniec(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    return dt.datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=dt.timezone.utc)


def _tg_k_num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def target_kontrola(j, inst=None, now=None):
    """data/target.json → {'rows': [(etykieta, status, wiek min, miesiąc, uwaga)], 'uwagi': [...], 'wiersze': [(opis, znak)], 'spojnosc': [...]}; brak pliku
    albo inna wersja = puste (wiek pliku i brak pliku zgłasza pętla PLIKI). Najwyżej ⚠️."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'wiersze': [], 'spojnosc': []}
    if not isinstance(j, dict) or j.get('v') != 1 or not isinstance(j.get('k'), dict) or not j['k']:
        return out
    asof = j.get('asof') if isinstance(j.get('asof'), str) and re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', j['asof']) else None
    if not asof:
        out['rows'].append((TG_K_ETYKIETA, '?', None, None, 'brak miesiąca danych w pliku'))
        out['uwagi'].append(f'{TG_K_ETYKIETA}: brak miesiąca danych w pliku')
        return out
    w = wiek_danych(asof, 'month', 'm', now)
    st = '⚠️' if (w is not None and w > TG_K_OKRES_DNI * 1440) else '✅'
    note = '' if st == '✅' else f'miesiąc danych starszy niż {TG_K_OKRES_DNI} dni od końca — źródło spóźnia się z publikacją (zwykle ok. 31 dni); najwyżej uwaga'
    out['rows'].append((TG_K_ETYKIETA, st, w, asof, note))
    if st == '⚠️':
        out['uwagi'].append(f'{TG_K_ETYKIETA}: dane z {asof} — {fmt_wiek(w)} temu ({note})')
    # spójność w pliku
    zle = []
    S = {a: s for a, s in j['k'].items() if isinstance(s, list)}
    for a in ('ecb', 'ne'):
        if isinstance(j.get(a), list):
            S[a] = j[a]
    last = {}
    for a, s in S.items():
        ms = [r[0] for r in s if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str)]
        vs = [_tg_k_num(r[1]) for r in s if isinstance(r, list) and len(r) == 2]
        if len(ms) != len(s) or any(v is None for v in vs):
            zle.append(f'{a}: nieczytelny punkt serii'); continue
        if ms != sorted(set(ms)):
            zle.append(f'{a}: miesiące nie rosną')
        if ms:
            last[a] = (ms[-1], vs[-1])
    pozno = sorted(a for a, (m, _) in last.items() if a in j['k'] and m != asof)
    if pozno:
        zle.append('miesiąc ostatniego punktu ≠ miesiąc danych pliku: ' + ', '.join(pozno[:5]))
    if all(a in last and last[a][0] == asof for a in S) and 'ecb' in S and 'ne' in S:
        suma = sum(v for _, v in last.values())
        if abs(suma) > TG_K_SUMA:
            zle.append(f'suma sald {asof} = {suma:+.1f} mln EUR zamiast zera')
    out['spojnosc'] = zle
    for z in zle[:4]:
        out['uwagi'].append(f'TARGET (target.json): {z}')
    out['wiersze'].append(('spójność pliku (miesiące rosnące, suma sald = 0)', '⚠️' if zle else '✅'))
    # ten sam miesiąc i kraj w panelu „dane urzędowe” (instytucje.json → tgb.q) — to samo źródło, osobne zapytanie
    Q = ((inst or {}).get('tgb') or {}).get('q') if isinstance(inst, dict) else None
    if isinstance(Q, dict):
        roz, ile = [], 0
        for a, s in Q.items():
            if a not in j['k'] or not isinstance(s, list) or not s:
                continue
            mine = {r[0]: _tg_k_num(r[1]) for r in j['k'][a] if isinstance(r, list) and len(r) == 2}
            for r in s[-3:]:
                if isinstance(r, list) and len(r) >= 2 and r[0] in mine and mine[r[0]] is not None and _tg_k_num(r[1]) is not None:
                    ile += 1
                    if abs(mine[r[0]] - r[1]) > TG_K_ZGODNE:
                        roz.append(f'{a} {r[0]}')
        if ile:
            out['wiersze'].append((f'zgodność z panelem „dane urzędowe” ({ile} porównań kraj-miesiąc)', '⚠️' if roz else '✅'))
            if roz:
                out['uwagi'].append('TARGET: target.json różni się od instytucje.json (to samo źródło): ' + ', '.join(roz[:5]))
    return out


def mica_kontrola(j, now=None):
    """data/mica.json → {'rows', 'uwagi', 'wiersze', 'spojnosc'} jak target_kontrola; wiek pliku wykazu z Last-Modified."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'wiersze': [], 'spojnosc': []}
    if not isinstance(j, dict) or j.get('v') != 1:
        return out
    zle = []
    for k in ('casp', 'emt'):
        P = j.get(k) if isinstance(j.get(k), dict) else None
        lab = MC_K_ETYKIETA[k]
        if not P:
            out['rows'].append((lab, '?', None, None, 'brak tej części w pliku'))
            out['uwagi'].append(f'{lab}: brak tej części w pliku'); continue
        pa = P.get('plik_at')
        w = wiek_danych(pa, 'ts', 'k', now) if isinstance(pa, str) else None
        if w is None:
            out['rows'].append((lab, '?', None, None, 'brak czasu pliku wykazu (nagłówek Last-Modified)'))
        else:
            st = '⚠️' if w > MC_K_PLIK_DNI * 1440 else '✅'
            note = '' if st == '✅' else f'plik wykazu starszy niż {MC_K_PLIK_DNI} dni — urząd przestał go odświeżać albo adres się zmienił; najwyżej uwaga'
            out['rows'].append((lab, st, w, pa[:10], note))
            if st == '⚠️':
                out['uwagi'].append(f'{lab}: plik z {pa[:10]} — {fmt_wiek(w)} temu ({note})')
        n = P.get('n')
        K = [r for r in (P.get('kraje') or []) if isinstance(r, list) and len(r) == 2 and isinstance(r[1], int)]
        if not isinstance(n, int) or n < 1:
            zle.append(f'{k}: brak liczby firm'); continue
        if sum(r[1] for r in K) != n:
            zle.append(f'{k}: suma firm w krajach {sum(r[1] for r in K)} ≠ liczba firm {n}')
        if isinstance(P.get('wiersze'), int) and n > P['wiersze']:
            zle.append(f'{k}: firm {n} więcej niż wierszy {P["wiersze"]}')
        if k == 'casp':
            us = P.get('uslugi') or {}
            if any(not isinstance(v, int) or v > n for v in us.values()):
                zle.append('casp: usługa u większej liczby firm niż wszystkich firm')
            se = P.get('seria') or []
            if se and (se[-1][1] != P.get('z_data') or any(b[1] < a[1] for a, b in zip(se, se[1:]))):
                zle.append('casp: szereg narastający nie kończy się liczbą firm z poprawną datą albo maleje')
            if isinstance(P.get('zle_daty'), int) and isinstance(P.get('wiersze'), int) and P['wiersze'] and P['zle_daty'] / P['wiersze'] * 100 > MC_K_ZLE_PCT:
                zle.append(f'casp: {P["zle_daty"]} z {P["wiersze"]} wierszy ma datę spoza okna obowiązywania MiCA (ponad {MC_K_ZLE_PCT:g}%)')
    out['spojnosc'] = zle
    for z in zle[:4]:
        out['uwagi'].append(f'MiCA (mica.json): {z}')
    if j.get('casp') or j.get('emt'):
        out['wiersze'].append(('spójność pliku (sumy w krajach, usługi, szereg)', '⚠️' if zle else '✅'))
    return out


def ark_odczyt(body):
    """Plik emitenta ARKB (CSV: date, fund, company, ticker, cusip, shares, market value ($), weight (%) + stopka z zastrzeżeniami) → (dzień ISO, BTC, wartość USD)
    z wiersza ARKB / BTC. Zła postać, zerowe albo nieskończone liczby, dzień z przyszłości = wyjątek (brak, nie zero)."""
    txt = body.decode('utf-8-sig', 'replace') if isinstance(body, bytes) else str(body)
    rd = csv.reader(txt.splitlines())
    head = None
    for row in rd:
        if head is None:
            low = [c.strip().lower() for c in row]
            if 'date' in low and 'ticker' in low and 'shares' in low and any(c.startswith('market value') for c in low):
                head = (low.index('date'), low.index('fund') if 'fund' in low else None, low.index('ticker'), low.index('shares'),
                        next(i for i, c in enumerate(low) if c.startswith('market value')))
            continue
        if len(row) <= max(h for h in head if h is not None):
            continue
        if row[head[2]].strip().upper() != 'BTC' or (head[1] is not None and row[head[1]].strip().upper() != 'ARKB'):
            continue
        m = re.fullmatch(r'\s*(\d{2})/(\d{2})/(\d{4})\s*', row[head[0]])
        if not m:
            raise ValueError('ARKB: zła data wiersza')
        d = dt.date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        btc, usd = _em_liczba(row[head[3]].replace('$', '')), _em_liczba(row[head[4]].replace('$', ''))
        if btc is None or usd is None:
            raise ValueError('ARKB: brak liczby BTC albo wartości')
        if d > NOW.date() + dt.timedelta(days=1):
            raise ValueError('ARKB: dzień z przyszłości')
        return d.isoformat(), btc, usd
    raise ValueError('ARKB: brak wiersza BTC (plik zmienił układ?)')


def ark_zapis(path):
    """kontrola/ark-arkb.csv → {dzień: {'btc', 'usd', 'flow', 'at'}}; brak = None; inny nagłówek = zapis od nowa."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        if next(r, None) != ARK_KOL:
            return rows
        for row in r:
            if len(row) < 5:
                continue
            try:
                d = dt.date.fromisoformat(row[0]).isoformat()
            except ValueError:
                continue
            def num(x):
                try:
                    return _em_skonczona(float(x)) if x != '' else None
                except ValueError:
                    return None
            rows[d] = {'btc': num(row[1]), 'usd': num(row[2]), 'flow': num(row[3]), 'at': row[4] or None}
    return rows


def ark_zapis_zapisz(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(ARK_KOL)
        for d in sorted(rows)[-ARK_DNI:]:
            x = rows[d]
            def fm(v):
                return ('%.6f' % (round(v, 6) + 0.0)).rstrip('0').rstrip('.') if v is not None else ''
            w.writerow([d, fm(x['btc']), fm(x['usd']), fm(x['flow']), x['at'] or ''])


def ark_przeplywy(rows, sesje=()):
    """{dzień D: wyliczony przepływ w mln USD} = (BTC[D] − BTC[poprzedni zapisany dzień P]) × cena z pliku w D; para tylko, gdy D − P ≤ ARK_PRZERWA dni
    i między P a D nie ma sesji strony (brak zapisu z tej sesji). → (wyliczenia, {D: powód pominięcia})."""
    ds = sorted(d for d, x in rows.items() if x.get('btc') and x.get('usd'))
    ss = sorted(sesje)
    out, pom = {}, {}
    for p, d in zip(ds, ds[1:]):
        if (dt.date.fromisoformat(d) - dt.date.fromisoformat(p)).days > ARK_PRZERWA or any(p < s < d for s in ss):
            pom[d] = f'brak zapisanej sesji między {p} a {d}'; continue
        out[d] = (rows[d]['btc'] - rows[p]['btc']) * rows[d]['usd'] / rows[d]['btc'] / 1e6
    return out, pom


def ark_porownanie(rows, sesje=()):
    """Porównanie wyliczeń (ark_przeplywy) z przepływem strony: dzień D albo sesja poprzedzająca D (zapis przepływu strony: rows[d]['flow']). Okno = ostatnie
    ARK_OKNO par. → słownik: status (✅ wszystkie zgodne; ⚠️ ≥ ARK_MIN_POR par i większość poza progiem; ℹ️ inaczej, w tym brak par), pary, roznice (dzień, różnica mln,
    strona_zero), pominiete."""
    est, pom = ark_przeplywy(rows, sesje)
    dni = sorted(set(rows) | set(sesje))
    pary, roz, pomin = [], [], [{'data': d, 'powod': p} for d, p in sorted(pom.items())][-3:]
    for d in sorted(est)[-ARK_OKNO:]:
        prev = max((s for s in dni if s < d), default=None)
        a0 = (rows.get(d) or {}).get('flow')
        a1 = (rows.get(prev) or {}).get('flow') if prev else None
        if a0 is None and a1 is None:
            pomin.append({'data': d, 'powod': 'brak przepływu strony z tego dnia'}); continue
        e = est[d]
        tol = max(ARK_TOL_MLN, ARK_TOL_PCT / 100 * abs(e))
        pary.append(d)
        if not any(a is not None and abs(a - e) <= tol for a in (a0, a1)):
            a = a0 if a0 is not None else a1
            roz.append({'data': d, 'roznica_mln': round(a - e, 1) + 0.0, 'strona_zero': a == 0})
    st = 'ℹ️'
    if pary and not roz:
        st = '✅'
    elif len(pary) >= ARK_MIN_POR and len(roz) * 2 > len(pary):
        st = '⚠️'
    return {'status': st, 'porownane': len(pary), 'od': pary[0] if pary else None, 'do': pary[-1] if pary else None, 'roznice': roz, 'pominiete': pomin}


def arkb_kontrola(files, R):
    """Krok 3e': drugi, niezależny odczyt przepływów ETF bitcoina — plik emitenta ARKB (1 zapytanie, bez ponawiania) i przepływ ARKB ze strony (etf.json); zapis
    w kontrola/ark-arkb.csv; wynik do R['zgodnosc']['arkb']; uwagi do R['uwagi'] (nigdy do listy błędów)."""
    path = os.path.join(OUT_DIR, ARK_CSV)
    rows = ark_zapis(path)
    etf = files.get('etf')
    A = ((etf.get('assets') if isinstance(etf, dict) else None) or {}).get('btc')
    A = A if isinstance(A, dict) else {}
    at = etf.get('at') if isinstance(etf, dict) and isinstance(etf.get('at'), str) else None
    sesje = emitent_sesje(etf, 'btc')
    asof = None
    try:
        asof = dt.date.fromisoformat(str(A.get('asof'))[:10]).isoformat()
    except ValueError:
        pass
    f = next((x for x in (A.get('funds') if isinstance(A.get('funds'), list) else []) if isinstance(x, dict) and x.get('t') == 'ARKB'), None)
    v = _em_skonczona(f.get('d1')) if f else None
    if asof and v is not None:
        x = rows.setdefault(asof, {'btc': None, 'usd': None, 'flow': None, 'at': None})
        x['flow'] = v; x['at'] = at or x['at']
    E = {'status': '?', 'bez_funduszu': bool(asof and f is None)}   # fundusz spoza listy strony: tylko zapis pliku wydawcy, bez porównania (informacja w linii raportu, bez uwagi)
    try:
        st, body, ms = get(ARK_URL, timeout=ARK_TIMEOUT, limit=ARK_LIMIT)
        d, btc, usd = ark_odczyt(body)
        x = rows.setdefault(d, {'btc': None, 'usd': None, 'flow': None, 'at': None})
        x['btc'], x['usd'] = btc, usd
        x['at'] = x['at'] or (at or NOW.isoformat())
        E['plik_do'] = d
    except Exception as e:  # noqa
        E['blad'] = (str(e) or type(e).__name__)[:120]
        R['uwagi'].append(f'ARKB (druga kontrola przepływów ETF bitcoina): plik wydawcy funduszu — brak odczytu ({E["blad"]}); kontrola pominięta')
    try:
        ark_zapis_zapisz(path, rows)
    except Exception as e:  # noqa
        R['uwagi'].append(f'{ARK_CSV}: nie zapisano ({str(e)[:80]})')
    E.update(ark_porownanie(rows, sesje))
    E['zapis_dni'] = len(rows)
    E['plik_do'] = E.get('plik_do') or max((d for d, x in rows.items() if x.get('btc')), default=None)
    if E.get('blad') and not E['porownane']:
        E['status'] = '?'
    nowy = bool(E['plik_do'] and asof and (dt.date.fromisoformat(asof) - dt.date.fromisoformat(E['plik_do'])).days > ARK_PLIK_DNI)
    E['nieaktualny'] = nowy
    if nowy:
        E['status'] = '⚠️'
        R['uwagi'].append(f'ARKB (druga kontrola przepływów ETF bitcoina): plik wydawcy kończy się na {E["plik_do"]}, a strona ma już sesję {asof} — plik nieaktualny (próg {ARK_PLIK_DNI} dni), nowsze sesje bez kontroli')
    elif E['status'] == '⚠️':
        R['uwagi'].append('ARKB (druga kontrola przepływów ETF bitcoina): przepływ na stronie ≠ zmiana liczby BTC w pliku wydawcy w większości z ostatnich ' + f'{E["porownane"]} sesji (próg max {ARK_TOL_MLN:g} mln USD / {ARK_TOL_PCT:g}%) — '
                          + '; '.join(f'{x["data"]}: {x["roznica_mln"]:+.1f} mln USD' for x in E['roznice'][-3:]))
    return E


def arkb_linia(E):
    """Linia raportu: status, liczba porównanych sesji, daty różnic (z kwotami różnic, bez liczb emitenta), ostatni dzień pliku; brak = „—”."""
    if not E:
        return '—'
    if E.get('porownane'):
        okr = E['od'] if E['od'] == E['do'] else f'{E["od"]} – {E["do"]}'
        s = f'{E["status"]} porównane sesje: {E["porownane"]} ({okr}), różnic ponad próg: {len(E["roznice"])}' + (
            ' — ' + '; '.join(f'{x["data"]}: {x["roznica_mln"]:+.1f} mln USD' + (' (strona pokazywała 0.0)' if x.get('strona_zero') else '') for x in E['roznice'][-3:]) if E['roznice'] else '')
    else:
        s = f'{E.get("status", "?")} jeszcze bez porównania (zapisanych dni: {E.get("zapis_dni", 0)}; para wymaga dwóch kolejnych dni pliku emitenta)'
    if E.get('pominiete'):
        s += '; pominięte: ' + ', '.join(f'{x["data"]} ({x["powod"]})' for x in E['pominiete'][-3:])
    s += f'; plik emitenta do {E.get("plik_do") or "—"}' + (f' — plik nieaktualny (próg {ARK_PLIK_DNI} dni)' if E.get('nieaktualny') else '')
    if E.get('bez_funduszu'):
        s += '; ARKB nie jest na liście funduszy strony (etf.json) — tylko zapis pliku, bez porównania'
    return s + (f' (brak odczytu: {E["blad"]})' if E.get('blad') else '')


# ---------------------------------------------------------------- v357 (zwiad 3): skład portfela Fed, pozycje bilansu Eurosystemu, fundusze hedgingowe ----------------------------------------------------------------
# Trzy pliki zbieracza (data/soma-sklad.json, data/eurosystem.json, data/hedge.json): kontrola dzienna czyta je z plików strony (bez zapytań do sieci) i sprawdza
# (1) wiek dnia danych — portfel Fed (stan na środę, wydanie w czwartek) nie starszy niż PL_K_SOMA_DNI dni (w nagraniu 1214 tygodni od 2003: największa przerwa między
#     dniami danych 8 dni, więc przed wydaniem następnego tygodnia wiek sięga ok. 10 dni; 11 dni = 0 fałszywych ostrzeżeń na całej historii, jedno pominięte wydanie = ⚠️);
#     bilans Eurosystemu (stan na piątek, wydanie we wtorek) nie starszy niż PL_K_EBC_DNI dni (56 kolejnych tygodni w nagraniu 13.10.2026, bez luk; największy wiek
#     tuż przed wydaniem ok. 10,5 dnia); fundusze hedgingowe (kwartalnie) nie starsze niż PL_K_HF_DNI dni od końca dnia danych (dane za II kwartał 2026 były 13.10.2026,
#     105 dni po końcu; jedno wydanie w nagraniach, więc próg szeroki — 150 dni, bez dłuższego testu wstecznego);
# (2) spójność w pliku: dni rosnące i bez powtórzeń, ostatni dzień = dzień danych pliku, suma grup portfela = razem (do PL_K_SUMA_MLN mln z zaokrągleń), szczyt portfela
#     nie mniejszy od ostatniej wartości, aktywa brutto funduszy ≥ netto, pozycje bilansu cząstkowe ≤ suma;
# (3) zgodność z plikiem instytucje.json (panel „dane urzędowe”: portfel Fed razem i aktywa Eurosystemu razem — to samo źródło, osobne zapytanie): ten sam dzień = ta sama
#     liczba (różnica ponad PL_K_ZGODA_MLN mln = uwaga; inne dni nie są porównywane — pliki odświeżają się niezależnie).
# Najwyżej ⚠️ (nigdy błąd przebiegu); brak pliku zgłasza pętla PLIKI.
for _n_ in ('soma-sklad', 'eurosystem', 'hedge'):
    PLIKI.insert(PLIKI.index('krypto-dzien'), _n_)   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
    LIMIT_MIN[_n_] = 48 * 60   # zapis co przebieg, odpytanie źródła najwyżej raz na dobę (przed wydaniem) — wiek pliku; wiek dnia danych ocenia wiersz świeżości
AW_BEZ_BLEDU.update({'soma_sklad': 'skład portfela Fed — część z błędem zostaje z datą (v357); wiek danych w wierszu świeżości',
                     'eurosystem': 'bilans Eurosystemu — część z błędem zostaje z datą (v357); wiek danych w wierszu świeżości',
                     'hedge': 'fundusze hedgingowe — część z błędem zostaje z datą (v357); wiek danych w wierszu świeżości'})
PL_K_ETYKIETA = {'soma-sklad': 'Portfel papierów Fed: skład (tygodniowo, stan na środę)', 'eurosystem': 'Bilans Eurosystemu: główne pozycje (tygodniowo, stan na piątek)',
                 'hedge': 'Fundusze hedgingowe w USA: aktywa (kwartalnie)'}
PL_K_SOMA_DNI, PL_K_EBC_DNI, PL_K_HF_DNI = 11, 14, 150
PL_K_SUMA_MLN = 5.0     # mln: suma pięciu grup portfela a „razem” (każda liczba zaokrąglona do miliona; w danych 7.10.2026: 0)
PL_K_ZGODA_MLN = 1.0    # mln: ten sam dzień w dwóch plikach tego samego źródła (zaokrąglenie do miliona: różnica 0)


def _pl_k_num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def _pl_k_dzien(s):
    try:
        return dt.date.fromisoformat(s).isoformat() if isinstance(s, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', s) else None
    except ValueError:
        return None


def _pl_k_wiersz(out, nazwa, asof, limit_dni):
    """Dodaje wiersz świeżości (wiek od końca dnia danych); zwraca status."""
    lab = PL_K_ETYKIETA[nazwa]
    d = _pl_k_dzien(asof)
    if d is None:
        out['rows'].append((lab, '?', None, None, 'brak dnia danych w pliku'))
        out['uwagi'].append(f'{lab}: brak dnia danych w pliku')
        return '?'
    w = wiek_danych(d, 'day', 'k', out['_now'])
    st = '⚠️' if (w is not None and w > limit_dni * 1440) else '✅'
    note = '' if st == '✅' else f'dzień danych starszy niż {limit_dni} dni — źródło spóźnia się z publikacją albo plik przestał się odświeżać; najwyżej uwaga'
    out['rows'].append((lab, st, w, d, note))
    if st == '⚠️':
        out['uwagi'].append(f'{lab}: dane z {d} — {fmt_wiek(w)} temu ({note})')
    return st


def _pl_k_seria_dni(S, zle, nazwa):
    """Dni rosnące, bez powtórzeń i prawdziwe daty; zwraca listę dni albo None."""
    dni = [r[0] for r in S if isinstance(r, list) and r and _pl_k_dzien(r[0])]
    if len(dni) != len(S) or dni != sorted(set(dni)):
        zle.append(f'{nazwa}: dni nie rosną, powtarzają się albo nie są datami')
        return None
    return dni


def plynnosc_kontrola(soma, eu, hf, inst=None, now=None):
    """Pliki v357 → {'rows': [(etykieta, status, wiek min, dzień, uwaga)], 'uwagi': [...], 'wiersze': [(opis, znak)], 'spojnosc': [...]}; brak pliku albo inna wersja = brak
    wiersza (wiek pliku i brak pliku zgłasza pętla PLIKI). Najwyżej ⚠️."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'wiersze': [], 'spojnosc': [], '_now': now}
    zle = []
    I = inst if isinstance(inst, dict) else {}
    # ---- portfel Fed ----
    if isinstance(soma, dict) and soma.get('v') == 1 and isinstance(soma.get('d'), list) and soma['d']:
        _pl_k_wiersz(out, 'soma-sklad', soma.get('asof'), PL_K_SOMA_DNI)
        D = soma['d']
        dni = _pl_k_seria_dni(D, zle, 'portfel Fed')
        if dni and dni[-1] != soma.get('asof'):
            zle.append('portfel Fed: ostatni dzień serii ≠ dzień danych pliku')
        for r in D:
            v = [_pl_k_num(x) for x in r[1:]] if isinstance(r, list) and len(r) == 7 else None
            if v is None or any(x is None for x in v):
                zle.append('portfel Fed: nieczytelny wiersz serii'); break
            if abs(sum(v[1:]) - v[0]) > PL_K_SUMA_MLN:
                zle.append(f'portfel Fed {r[0]}: suma grup {sum(v[1:]):.0f} ≠ razem {v[0]:.0f} mln USD'); break
        pk = soma.get('peak')
        if not (isinstance(pk, list) and len(pk) == 2 and _pl_k_num(pk[1]) is not None and _pl_k_dzien(pk[0])):
            zle.append('portfel Fed: brak szczytu')
        elif isinstance(D[-1], list) and _pl_k_num(D[-1][1]) is not None and pk[1] < D[-1][1]:
            zle.append('portfel Fed: szczyt mniejszy od ostatniej wartości')
        W = ((I.get('soma') or {}).get('d')) if isinstance(I.get('soma'), dict) else None
        if isinstance(W, list) and isinstance(D[-1], list):
            mine = {r[0]: _pl_k_num(r[1]) for r in D if isinstance(r, list) and len(r) >= 2}
            por = [(r[0], mine[r[0]], _pl_k_num(r[1])) for r in W if isinstance(r, list) and len(r) >= 2 and r[0] in mine and mine[r[0]] is not None and _pl_k_num(r[1]) is not None]
            if por:
                roz = [d for d, a, b in por if abs(a - b) > PL_K_ZGODA_MLN]
                out['wiersze'].append((f'portfel Fed razem: zgodność z panelem „dane urzędowe” ({len(por)} wspólnych tygodni)', '⚠️' if roz else '✅'))
                if roz:
                    out['uwagi'].append('portfel Fed: soma-sklad.json różni się od instytucje.json (to samo źródło) w dniach ' + ', '.join(roz[:4]))
    # ---- bilans Eurosystemu ----
    if isinstance(eu, dict) and eu.get('v') == 1 and isinstance(eu.get('k'), dict) and eu['k']:
        _pl_k_wiersz(out, 'eurosystem', eu.get('asof'), PL_K_EBC_DNI)
        K = eu['k']
        ost = {}
        for k, S in K.items():
            if not isinstance(S, list) or not S:
                zle.append(f'bilans Eurosystemu {k}: pusta seria'); continue
            dni = _pl_k_seria_dni(S, zle, f'bilans Eurosystemu {k}')
            if dni is None:
                continue
            vs = [_pl_k_num(r[1]) if len(r) >= 2 else None for r in S]
            if any(x is None for x in vs):
                zle.append(f'bilans Eurosystemu {k}: nieczytelny punkt serii'); continue
            ost[k] = (dni[-1], vs[-1])
        if 'total' not in ost:
            zle.append('bilans Eurosystemu: brak sumy aktywów')
        else:
            if ost['total'][0] != eu.get('asof'):
                zle.append('bilans Eurosystemu: ostatni dzień sumy ≠ dzień danych pliku')
            tot = ost['total'][1]
            for grupa in (('qe', 'zloto', 'kredyt'), ('banknoty', 'depozyty', 'rachunki', 'rzady')):
                s = sum(ost[k][1] for k in grupa if k in ost and ost[k][0] == ost['total'][0])
                if s > tot * 1.001:
                    zle.append(f'bilans Eurosystemu: pozycje {"+".join(grupa)} większe od sumy bilansu')
        W = ((I.get('ilm') or {}).get('d')) if isinstance(I.get('ilm'), dict) else None
        if isinstance(W, list) and isinstance(K.get('total'), list):
            mine = {r[0]: _pl_k_num(r[1]) for r in K['total'] if isinstance(r, list) and len(r) >= 2}
            por = [(r[0], mine[r[0]], _pl_k_num(r[1])) for r in W if isinstance(r, list) and len(r) >= 2 and r[0] in mine and mine[r[0]] is not None and _pl_k_num(r[1]) is not None]
            if por:
                roz = [d for d, a, b in por if abs(a - b) > PL_K_ZGODA_MLN]
                out['wiersze'].append((f'aktywa Eurosystemu razem: zgodność z panelem „dane urzędowe” ({len(por)} wspólnych tygodni)', '⚠️' if roz else '✅'))
                if roz:
                    out['uwagi'].append('bilans Eurosystemu: eurosystem.json różni się od instytucje.json (to samo źródło) w dniach ' + ', '.join(roz[:4]))
    # ---- fundusze hedgingowe ----
    if isinstance(hf, dict) and hf.get('v') == 1 and isinstance(hf.get('d'), list) and hf['d']:
        _pl_k_wiersz(out, 'hedge', hf.get('asof'), PL_K_HF_DNI)
        D = hf['d']
        dni = _pl_k_seria_dni(D, zle, 'fundusze hedgingowe')
        if dni and dni[-1] != hf.get('asof'):
            zle.append('fundusze hedgingowe: ostatni dzień serii ≠ dzień danych pliku')
        for r in D:
            g, n = (_pl_k_num(r[1]), _pl_k_num(r[2])) if isinstance(r, list) and len(r) == 3 else (None, None)
            if g is None or n is None or n <= 0:
                zle.append('fundusze hedgingowe: nieczytelny wiersz serii'); break
            if g < n or g / n > 10:
                zle.append(f'fundusze hedgingowe {r[0]}: aktywa brutto {g:.0f} i netto {n:.0f} mln USD niespójne'); break
    out['spojnosc'] = zle
    for z in zle[:4]:
        out['uwagi'].append(f'płynność i fundusze (v357): {z}')
    if out['rows']:
        out['wiersze'].append(('spójność plików (dni rosnące, sumy grup, szczyt, brutto ≥ netto)', '⚠️' if zle else '✅'))
    del out['_now']
    return out


# ---------------------------------------------------------------- v362 (F2Z1): krzywe rentowności (USA, Niemcy, Japonia, strefa euro, Kanada) ----------------------------------------------------------------
# Plik zbieracza data/krzywe.json: kontrola dzienna czyta go z pliku strony (bez zapytań do sieci) i sprawdza
# (1) wiek dnia danych każdej krzywej w godzinach roboczych (bez sobót i niedziel; od końca dnia danych). Progi z testu wstecznego — największy wiek tuż przed ukazaniem się
#     kolejnego dnia danych (publikacja: USA ok. 21:00 UTC tego dnia, Niemcy ok. 10:10 UTC tego dnia, Japonia ok. 23:30 UTC tego dnia, EBC i Kanada następnego dnia rano/w południe):
#     USA 45 h (444 dni od 2025), Niemcy 82 h (274 dni od 2025; przerwa świąteczna 23–29 grudnia), Japonia 119,5 h (1403 dni od 2021; Nowy Rok 30 grudnia–6 stycznia),
#     strefa euro 82 h (1478 dni od 2021), Kanada 84 h (1438 dni od 2021) — progi 72 / 96 / 144 / 96 / 96 h dają 0 fałszywych ⚠ w całej historii; ⚠ = źródło spóźnia się albo plik
#     nie odświeża się;
# (2) spójność w pliku: dzień danych jest datą, „miesiąc temu” wcześniejszy o 20–45 dni (dzień roboczy sprzed daty − 1 miesiąc), liczby są liczbami w granicach, 2L i 10L w każdej
#     krzywej nominalnej, różnice (inflacja oczekiwana, premia strefy euro) = różnica krzywych z tych samych dni (do KR_K_ZGODA pp z zaokrągleń);
# (3) zgodność z plikiem rynki.json (to samo źródło, osobne zapytanie): rentowność 10L USA i 10L Niemiec w tych samych dniach = te same liczby (do KR_K_ZGODA pp).
# Najwyżej ⚠ (nigdy błąd przebiegu); brak pliku zgłasza pętla PLIKI.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'krzywe')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['krzywe'] = 8 * 60   # zapis co przebieg, odpytanie źródeł co ok. 170 min (część z błędem: co godzinę) — wiek pliku; wiek dnia danych ocenia wiersz świeżości
AW_BEZ_BLEDU.update({'krzywe_' + _k_: 'krzywe rentowności — część z błędem zostaje z datą (v362); wiek danych w wierszach świeżości' for _k_ in ('us', 'de', 'jp', 'ea', 'ca')})
KR_K_ETYKIETA = {'us': 'Krzywa rentowności USA (dni robocze)', 'de': 'Krzywa rentowności Niemiec (dni robocze)', 'jp': 'Krzywa rentowności Japonii (dni robocze)',
                 'ea': 'Krzywa rentowności strefy euro (dni robocze)', 'ca': 'Krzywa rentowności Kanady (dni robocze)'}
KR_K_PROG = {'us': 72 * 60, 'de': 96 * 60, 'jp': 144 * 60, 'ea': 96 * 60, 'ca': 96 * 60}   # minuty roboczych godzin (test wsteczny wyżej)
KR_K_ZGODA = 0.0051     # pp: ta sama rentowność w dwóch plikach tego samego źródła (źródła podają 2 miejsca po przecinku; w danych 13.10.2026 różnica 0)
KR_K_PREV_DNI = (20, 45)   # dni między „miesiąc temu” a dniem danych (miesiąc kalendarzowy 28–31 dni + do KRZ_OKNO_PREV dni wstecz do dnia roboczego)
KR_K_ZAKRES = (-2.0, 25.0)


def _kr_k_num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def _kr_k_dzien(s):
    try:
        return dt.date.fromisoformat(s) if isinstance(s, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', s) else None
    except ValueError:
        return None


def krzywe_kontrola(kr, ry=None, now=None):
    """Plik data/krzywe.json (+ rynki.json) → {'rows': [(etykieta, status, wiek min, dzień, uwaga)], 'uwagi': [...], 'wiersze': [(opis, znak)], 'spojnosc': [...]}; brak pliku albo inna
    wersja = brak wierszy (wiek pliku i brak pliku zgłasza pętla PLIKI). Najwyżej ⚠."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'wiersze': [], 'spojnosc': []}
    if not (isinstance(kr, dict) and kr.get('v') == 1 and isinstance(kr.get('c'), dict)):
        return out
    C = kr['c']
    zle = out['spojnosc']
    # ---- wiek dnia danych ----
    for k, lab in KR_K_ETYKIETA.items():
        o = C.get(k)
        asof = o.get('asof') if isinstance(o, dict) else None
        if _kr_k_dzien(asof) is None:
            out['rows'].append((lab, '?', None, None, 'brak krzywej w pliku'))
            out['uwagi'].append(f'{lab}: brak krzywej w pliku')
            continue
        w = wiek_danych(asof, 'day', 'd', now)
        prog = KR_K_PROG[k]
        st = '?' if w is None else ('\u26a0\ufe0f' if w > prog else '✅')
        note = f'dzień danych starszy niż {fmt_wiek(prog)} roboczych — źródło spóźnia się z publikacją albo plik przestał się odświeżać; najwyżej uwaga' if st == '\u26a0\ufe0f' else ''
        out['rows'].append((lab, st, w, asof, note))
        if st == '\u26a0\ufe0f':
            out['uwagi'].append(f'{lab}: dane z {asof} — {fmt_wiek(w)} temu ({note})')
    # ---- spójność w pliku ----
    for key, o in C.items():
        if not isinstance(o, dict):
            zle.append(f'krzywe {key}: nie jest obiektem'); continue
        a, p = _kr_k_dzien(o.get('asof')), o.get('pasof')
        if a is None:
            zle.append(f'krzywe {key}: zły dzień danych'); continue
        if p is not None:
            pd = _kr_k_dzien(p)
            if pd is None or not (KR_K_PREV_DNI[0] <= (a - pd).days <= KR_K_PREV_DNI[1]):
                zle.append(f'krzywe {key}: dzień „miesiąc temu” {p} nie jest 20–45 dni przed {a}')
        elif o.get('prev') is not None:
            zle.append(f'krzywe {key}: „miesiąc temu” bez dnia')
        for w_ in ('now', 'prev'):
            v = o.get(w_)
            if v is None and w_ == 'prev':
                continue
            if not isinstance(v, dict) or not v:
                zle.append(f'krzywe {key}: pusta krzywa {w_}'); continue
            bad = [l for l, x in v.items() if _kr_k_num(x) is None or (not key.endswith(('_be', '_prem', '_de')) and not KR_K_ZAKRES[0] <= x <= KR_K_ZAKRES[1])]
            if bad:
                zle.append(f'krzywe {key}: zła liczba w {w_} ({", ".join(bad[:3])})')
        if key in KR_K_ETYKIETA and isinstance(o.get('now'), dict) and not all(_kr_k_num(o['now'].get(l)) is not None for l in ('2Y', '10Y')):
            zle.append(f'krzywe {key}: brak 2L albo 10L')

    def licz(nom, rea, be, lab):
        """różnica nom − rea w tych samych dniach = be (do KR_K_ZGODA); dni różne = pomijamy (liczone w zbieraczu ze wspólnych dni wierszy, których tu nie ma w całości)"""
        N, R_, B = C.get(nom), C.get(rea), C.get(be)
        if not (isinstance(N, dict) and isinstance(R_, dict) and isinstance(B, dict)):
            return
        for w_, da in (('now', 'asof'), ('prev', 'pasof')):
            if B.get(da) and N.get(da) == B.get(da) == R_.get(da) and isinstance(B.get(w_), dict) and isinstance(N.get(w_), dict) and isinstance(R_.get(w_), dict):
                for l, x in B[w_].items():
                    a_, b_ = _kr_k_num(N[w_].get(l)), _kr_k_num(R_[w_].get(l))
                    if a_ is not None and b_ is not None and abs((a_ - b_) - x) > KR_K_ZGODA:
                        zle.append(f'{lab} {l} ({B[da]}): zapisana różnica {x} ≠ {a_ - b_:.3f}')
    licz('us', 'us_real', 'us_be', 'inflacja oczekiwana USA')
    licz('ea', 'ea_aaa', 'ea_prem', 'premia strefy euro')
    licz('ca', 'ca_real', 'ca_be', 'inflacja oczekiwana Kanady')
    # ---- zgodność z rynki.json (10L USA i Niemiec) ----
    R = ry if isinstance(ry, dict) else {}
    for kraj, klucz, lab in (('us', 'ust', 'USA'), ('de', 'buba', 'Niemcy')):
        O, S = C.get(kraj), R.get(klucz)
        if not (isinstance(O, dict) and isinstance(S, list) and S):
            continue
        sv = {r[0]: _kr_k_num(r[1]) for r in S if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str)}
        por = []
        for w_, da in (('now', 'asof'), ('prev', 'pasof')):
            d, x = O.get(da), (O.get(w_) or {}).get('10Y') if isinstance(O.get(w_), dict) else None
            if isinstance(d, str) and _kr_k_num(x) is not None and sv.get(d) is not None:
                por.append((d, x, sv[d]))
        if por:
            roz = [d for d, a, b in por if abs(a - b) > KR_K_ZGODA]
            out['wiersze'].append((f'rentowność 10L {lab}: zgodność z plikiem rynki ({len(por)} wspólne dni)', '\u26a0\ufe0f' if roz else '✅'))
            if roz:
                out['uwagi'].append(f'krzywe: 10L {lab} różni się od rynki.json (to samo źródło) w dniach ' + ', '.join(roz[:4]))
    for z in zle[:4]:
        out['uwagi'].append(f'krzywe rentowności (v362): {z}')
    if out['rows']:
        out['wiersze'].append(('spójność pliku (dni, „miesiąc temu”, liczby, różnice nominalna − realna, wszyscy − AAA)', '\u26a0\ufe0f' if zle else '✅'))
    return out


# ---------------------------------------------------------------- v363 (F2Z3): EMITENCI STABLECOINÓW (data/stable-emitenci.json) --------------------------------------------------
# Plik: lista monet dolarowych (udziały, zmiany), raport Tether (zobowiązania, sieci) i raport Circle (USDC, EURC). Wiek (wiersze świeżości, najwyżej ⚠️): raport Tether — migawka dobowa
# o 23:30 UTC, więc wiek ≤ STE_K_TETHER_H h (doba + 6 h zapasu); aktualizacja USDC u Circle — ≤ STE_K_CIRCLE_H h (plik odświeżany co ~55 min, część po błędzie zostaje najwyżej 3 h).
# Spójność w pliku (⚠️): obieg Tether w sieciach = zobowiązania, kapitał = aktywa − zobowiązania, sieci Circle + reszta = podaż, monety + reszta = suma, zabezpieczenie = suma.
# Porównania (TYLKO informacja, najwyżej ⚠️ — nigdy ❌ ani BŁĄD): (a) suma emitentów (lista monet) a podaż stablecoinów z drugiego źródła (cmc.json: stable_mcap; różne definicje monet — stała różnica
# ok. +10%: 13.10.2026 suma emitentów +10,5%, a cała podaż z historii dziennej +9,8% — zob. STAB_ZOLTE), (b) USDC u Circle a USDC na liście monet, (c) zobowiązania Tether a USDT na liście monet. Ocena = odchylenie dzisiejszej różnicy od mediany ostatnich ZG_DNI dni
# (kontrola/stable-emitenci.csv, jak zgodnosc.csv); do zebrania ZG_MIN dni historii — tylko informacja. Próg (b) i (c): STE_K_ZOLTE pkt proc. — test wsteczny na 365 dobach (stablecoincharts,
# 13.10.2026): dzienna zmiana podaży USDT p99 0,60% (max 0,89%), USDC p99 1,45% (max 2,84%); raport Tether jest o 0–24 h starszy niż lista monet, USDC u Circle o godziny — odchylenie od mediany
# powyżej 1 pkt proc. to więcej niż zwykła dobowa zmiana USDT i niż 3 h zmian USDC. Próg (a): STAB_ZOLTE (pokrewna seria — cała podaż z historii dziennej a to samo drugie źródło, 8 dni: odchylenie od mediany najwyżej 0,18 pkt proc.).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'stable-emitenci')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['stable-emitenci'] = 3 * 60   # zapis co przebieg lub co ~55 min — wiek pliku; wiek raportów emitentów ocenia wiersz świeżości
STE_K_TETHER_H = 30     # h — wiek migawki raportu Tether (pole id = 23:30 UTC dnia)
STE_K_CIRCLE_H = 2      # h — wiek najnowszej aktualizacji USDC u Circle
STE_K_ZOLTE = 1.0       # pkt proc. — odchylenie różnicy emitent ↔ lista monet od mediany = ⚠️ (nigdy ❌)
STE_K_OKNO_H = 3.0      # h — raport Circle i lista monet pobrane dalej od siebie = bez porównania (informacja)
STE_K_SPOJ_PCT = 0.5    # % — zgodność sum w pliku (zaokrąglenia do pełnych USD są o rzędy mniejsze)
STE_K_KOL = ['date', 'emit_cmc_pct', 'usdc_pct', 'usdt_pct']   # kontrola/stable-emitenci.csv: tylko różnice procentowe; puste pole = brak odczytu
STE_K_ETYKIETA = {'tether': 'Stablecoiny — raport Tether (zobowiązania, sieci)', 'circle': 'Stablecoiny — raport Circle (USDC, EURC)'}


def ste_k_csv(path):
    """{dzień: {'emc': %, 'usdc': %, 'usdt': %}} — pusta komórka albo brak pliku = brak (klucz pominięty)."""
    rows = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8', newline='') as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) >= 2 and row[0] != 'date':
                    rec = {}
                    for i, kk in ((1, 'emc'), (2, 'usdc'), (3, 'usdt')):
                        try:
                            rec[kk] = float(row[i])
                        except (ValueError, IndexError):
                            pass
                    rows[row[0]] = rec
    return rows


def ste_k_zapisz(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        wtr = csv.writer(f, lineterminator='\n'); wtr.writerow(STE_K_KOL)
        for d in sorted(rows):
            wtr.writerow([d] + [('%.3f' % rows[d][kk]) if isinstance(rows[d].get(kk), (int, float)) else '' for kk in ('emc', 'usdc', 'usdt')])


def _ste_k_l(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def ste_kontrola(j, cmc, rows, today, now=None):
    """data/stable-emitenci.json → {'rows': [(etykieta, status, wiek min, dane, uwaga)], 'uwagi': [...], 'wiersze': [(opis, znak)], 'spojnosc': [...]}; brak pliku albo inna wersja = puste.
    rows — historia różnic z kontrola/stable-emitenci.csv (uzupełniana o dzisiejsze różnice w rows[today]). Najwyżej ⚠️."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'wiersze': [], 'spojnosc': []}
    if not isinstance(j, dict) or j.get('v') != 1:
        return out
    zle = []
    E, T, C = (j.get(k) if isinstance(j.get(k), dict) else None for k in ('emit', 'tether', 'circle'))
    pat = j.get('part_at') if isinstance(j.get('part_at'), dict) else {}
    # ---- wiek raportów emitentów ----
    for k, P, t, lim in (('tether', T, T.get('t') if T else None, STE_K_TETHER_H), ('circle', C, (C.get('usdc') or {}).get('upd') if C else None, STE_K_CIRCLE_H)):
        lab = STE_K_ETYKIETA[k]
        if P is None:
            out['rows'].append((lab, '?', None, None, 'brak tej części w pliku'))
            out['uwagi'].append(f'{lab}: brak tej części w pliku (źródło nie odpowiada od ponad {"36" if k == "tether" else "3"} h)')
            continue
        w = wiek_danych(t, 'ts', 'k', now) if isinstance(t, str) else None
        if w is None:
            out['rows'].append((lab, '?', None, None, 'brak czasu raportu'))
            continue
        st = '⚠️' if w > lim * 60 else '✅'
        note = '' if st == '✅' else f'raport starszy niż {lim} h — emitent nie odświeża pliku albo adres się zmienił; najwyżej uwaga'
        out['rows'].append((lab, st, w, str(t)[:16].replace('T', ' ') + ' UTC', note))
        if st == '⚠️':
            out['uwagi'].append(f'{lab}: raport z {str(t)[:16].replace("T", " ")} UTC — {fmt_wiek(w)} temu ({note})')
    # ---- spójność w pliku ----
    if T:
        nets = [r for r in (T.get('nets') or []) if isinstance(r, list) and len(r) == 5 and all(_ste_k_l(x) is not None for x in r[1:])]
        liab = _ste_k_l(T.get('liab'))
        if not nets or not liab or liab <= 0:
            zle.append('Tether: brak sieci albo zobowiązań')
        else:
            if abs(sum(r[4] for r in nets) - liab) / liab * 100 > STE_K_SPOJ_PCT:
                zle.append('Tether: suma obiegu w sieciach różni się od zobowiązań')
            if any(r[4] < 0 or abs(r[1] - r[2] - r[3] - r[4]) > 2 for r in nets):
                zle.append('Tether: w sieci wybite − skarbiec − kwarantanna ≠ w obiegu')
            a, e = _ste_k_l(T.get('assets')), _ste_k_l(T.get('eq'))
            if a is None or e is None or abs(a - e - liab) / liab * 100 > STE_K_SPOJ_PCT:
                zle.append('Tether: aktywa − kapitał ≠ zobowiązania')
    if C:
        for k in ('usdc', 'eurc'):
            M = C.get(k) if isinstance(C.get(k), dict) else None
            if M is None:
                continue
            tot, rw = _ste_k_l(M.get('tot')), [r for r in (M.get('rows') or []) if isinstance(r, list) and len(r) == 2 and _ste_k_l(r[1]) is not None]
            s = sum(r[1] for r in rw) + (_ste_k_l((M.get('inne') or [0])[0]) or 0)
            if not tot or tot <= 0 or abs(s - tot) / tot * 100 > STE_K_SPOJ_PCT:
                zle.append(f'Circle {k.upper()}: suma sieci różni się od łącznej podaży')
    if E:
        rw = [r for r in (E.get('rows') or []) if isinstance(r, list) and len(r) == 7 and _ste_k_l(r[2]) is not None]
        tot = _ste_k_l(E.get('total'))
        s = sum(r[2] for r in rw) + (_ste_k_l((E.get('inne') or [0])[0]) or 0)
        if not tot or tot <= 0 or abs(s - tot) / tot * 100 > STE_K_SPOJ_PCT:
            zle.append('lista monet: suma monet i reszty różni się od sumy podaży')
        mh = E.get('mech') if isinstance(E.get('mech'), dict) else {}
        if tot and mh and abs(sum(_ste_k_l(v[0]) or 0 for v in mh.values() if isinstance(v, list) and v) - tot) / tot * 100 > STE_K_SPOJ_PCT:
            zle.append('lista monet: podział wg zabezpieczenia nie sumuje się do całości')
    out['spojnosc'] = zle
    for z in zle[:4]:
        out['uwagi'].append(f'emitenci stablecoinów (stable-emitenci.json): {z}')
    if T or C or E:
        out['wiersze'].append(('spójność pliku (sieci, kapitał, sumy, zabezpieczenie)', '⚠️' if zle else '✅'))
    # ---- porównania z drugim źródłem ----
    def cz(k):
        t = _ix_dt_k(pat.get(k) or j.get('at'))
        return t

    def norma(med, n, fm='{:+.2f}%'):
        return f' (norma {fm.format(med)}, mediana {n} dni)' if med is not None and n else ''

    r1 = {r[0]: r for r in (E.get('rows') if E else []) if isinstance(r, list) and len(r) == 7}
    cmc_v = _ste_k_l(cmc.get('stable_mcap')) if isinstance(cmc, dict) else None
    tl, tc = cz('llama'), _ix_dt_k(cmc.get('at') if isinstance(cmc, dict) else None)
    por = []
    if E and _ste_k_l(E.get('total')) and cmc_v and cmc_v > 0:
        h = abs((tl - tc).total_seconds()) / 3600 if tl and tc else None
        por.append(('emc', 'suma emitentów a podaż z drugiego źródła', round((E['total'] - cmc_v) / cmc_v * 100, 3) if h is not None and h <= STAB_MAX_H else None, STAB_ZOLTE,
                    f'pliki pobrane w odstępie {h:.1f} h' if h is not None else 'brak czasu pobrania'))
    if C and 'USDC' in r1 and _ste_k_l((C.get('usdc') or {}).get('tot')):
        tu = _ix_dt_k((C.get('usdc') or {}).get('upd'))
        h = abs((tl - tu).total_seconds()) / 3600 if tl and tu else None
        por.append(('usdc', 'USDC: raport Circle a lista monet', round((C['usdc']['tot'] - r1['USDC'][2]) / r1['USDC'][2] * 100, 3) if h is not None and h <= STE_K_OKNO_H else None, STE_K_ZOLTE,
                    f'odstęp czasu {h:.1f} h' if h is not None else 'brak czasu'))
    if T and 'USDT' in r1 and _ste_k_l(T.get('liab')):
        por.append(('usdt', 'USDT: zobowiązania w raporcie Tether a lista monet', round((T['liab'] - r1['USDT'][2]) / r1['USDT'][2] * 100, 3), STE_K_ZOLTE, ''))
    for kk, opis, gap, zolte, powod in por:
        if gap is None:
            out['wiersze'].append((f'{opis}: bez porównania ({powod})', 'ℹ️'))
            continue
        rows.setdefault(today, {})[kk] = gap
        st, med, n, op = mediana_ocena(rows, kk, gap, today, zolte, None)
        out['wiersze'].append((f'{opis}: różnica dziś {gap:+.2f}%{norma(med, n)} — {op}', st))
        if st == '⚠️':
            out['uwagi'].append(f'emitenci stablecoinów: {opis} — różnica dziś {gap:+.2f}% wobec normy {med:+.2f}% ({op}); sprawdzić, czy któreś źródło nie pominęło sieci albo monety (tylko informacja)')
    return out


def _ix_dt_k(s):
    """Czas ISO → datetime UTC; brak albo zepsuty = None."""
    try:
        d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- v366 (F2Z2): inflacja (BIS), koniunktura (OECD) i stopy realne ----------------------------------------------------------------
# Dwa nowe pliki zbieracza: data/inflacja.json (inflacja CPI r/r, ok. 63 gospodarek) i data/koniunktura.json (zaufanie konsumentów i firm, ok. 25 krajów z Polską). Kontrola dzienna czyta je
# z plików strony (bez zapytań do sieci) i sprawdza:
# (1) wiek najnowszego miesiąca danych (od końca miesiąca) — BIS dopisuje miesiąc inflacji 4–7 tygodni po jego końcu (stan 13.10.2026: sierpień u większości krajów, wrzesień nie), więc
#     tuż przed ukazaniem się kolejnego miesiąca najnowszy miesiąc ma ok. 45 + 31 = 76 dni; próg 100 dni (RL_K_INFL_PROG) ma zapas ok. 3 tygodni. OECD: zaufanie za miesiąc ukazuje się ok.
#     10. dnia następnego (13.10.2026: wrzesień u większości krajów), więc przed kolejną publikacją najnowszy miesiąc ma ok. 40 dni; próg 55 dni (RL_K_KON_PROG). Progi wynikają z kalendarza
#     publikacji, nie z testu wstecznego na latach danych (źródła nie udostępniają dat wydań), dlatego z zapasem — ⚠ = źródło spóźnia się albo plik przestał się odświeżać;
# (2) spójność w pliku: miesiące 'RRRR-MM' rosnąco bez powtórzeń, liczby w granicach (inflacja −30…1000 % r/r, zaufanie 50…150), ostatni miesiąc kraju = pola m/v, pole asof = najnowszy
#     miesiąc, w koniunkturze Polska w obu miarach (po to ta część powstała) i dwie miary nie są tą samą serią (pułapka: oecd_parse zapytania łączącego miary nadpisuje jedną drugą);
# (3) TYLKO INFORMACJA: inflacja USA z BIS a inflacja r/r z CPI-U (BLS) z pliku usa-makro.json w tym samym miesiącu (11.10: BIS 3,3965 % a BLS 3,4 %) — różnica do RL_K_BLS pp ✅, większa
#     tylko jako informacja (nigdy ⚠); i pokrycie stopy realnej: dla ilu banków z stopy.json da się ją policzyć (miesiąc inflacji nie starszy niż 3 mies. od miesiąca stanu stopy) — poniżej
#     połowy banków ⚠ (kolumna na stronie byłaby prawie pusta).
# Najwyżej ⚠ (nigdy błąd przebiegu); brak pliku zgłasza pętla PLIKI.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'inflacja')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
PLIKI.insert(PLIKI.index('krypto-dzien'), 'koniunktura')
LIMIT_MIN['inflacja'] = 30 * 60      # zapis co przebieg; odpytanie BIS co ok. 20 h (zapas na nieudane próby) — wiek pliku; wiek miesiąca ocenia wiersz świeżości
LIMIT_MIN['koniunktura'] = 12 * 60   # odpytanie OECD co 6 h (część z błędem: co godzinę)
AW_BEZ_BLEDU.update({'inflacja': 'inflacja — błąd zostaje z poprzednim plikiem i datą (v366); wiek miesiąca w wierszu świeżości',
                     'koniunktura': 'koniunktura — część z błędem zostaje z datą (v366); wiek miesiąca w wierszu świeżości'})
RL_K_INFL_PROG = 100 * 24 * 60   # min — wiek najnowszego miesiąca inflacji od jego końca (kalendarz publikacji wyżej)
RL_K_KON_PROG = 55 * 24 * 60     # min — to samo dla zaufania konsumentów i firm
RL_K_BLS = 0.15                  # pp — inflacja USA: BIS (3 miejsca) a BLS (1 miejsce po przecinku, zaokrąglenie ±0,05) w tym samym miesiącu
RL_K_INFL_ZAKRES = (-30.0, 1000.0)
RL_K_KON_ZAKRES = (50.0, 150.0)
RL_K_MAX_MIES = 3                # stopa realna tylko przy inflacji nie starszej niż tyle miesięcy od miesiąca stanu stopy (jak na stronie)


def _rl_k_mi(s):
    m = re.fullmatch(r'(\d{4})-(0[1-9]|1[0-2])', s) if isinstance(s, str) else None
    return int(m.group(1)) * 12 + int(m.group(2)) - 1 if m else None


def _rl_k_num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def _rl_k_seria(s, zakres, nazwa, zle):
    """lista [[miesiąc, liczba], …]: miesiące rosnąco bez powtórzeń, liczby w zakresie; zwraca ostatnią parę albo None"""
    if not isinstance(s, list) or not s:
        zle.append(f'{nazwa}: pusta seria'); return None
    prev = None
    for p in s:
        if not (isinstance(p, list) and len(p) == 2 and _rl_k_mi(p[0]) is not None and _rl_k_num(p[1]) is not None):
            zle.append(f'{nazwa}: zły wiersz serii'); return None
        if prev is not None and _rl_k_mi(p[0]) <= prev:
            zle.append(f'{nazwa}: miesiące nie rosną'); return None
        if not zakres[0] <= p[1] <= zakres[1]:
            zle.append(f'{nazwa}: liczba {p[1]} poza zakresem'); return None
        prev = _rl_k_mi(p[0])
    return s[-1]


def stopy_realne_kontrola(infl, kon, usam=None, stopy=None, now=None):
    """Pliki data/inflacja.json, data/koniunktura.json (+ usa-makro.json, stopy.json) → {'rows': [(etykieta, status, wiek min, miesiąc, uwaga)], 'uwagi': [...], 'wiersze': [(opis, znak)],
    'spojnosc': [...]}; brak pliku albo inna wersja = brak wierszy tej części (wiek pliku i brak pliku zgłasza pętla PLIKI). Najwyżej ⚠."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'wiersze': [], 'spojnosc': []}
    zle = out['spojnosc']
    # ---- inflacja ----
    ic = infl.get('c') if isinstance(infl, dict) and infl.get('v') == 1 and isinstance(infl.get('c'), dict) else None
    ost = {}
    if ic:
        for a, o in ic.items():
            if not (isinstance(o, dict) and _rl_k_mi(o.get('m')) is not None and _rl_k_num(o.get('v')) is not None):
                zle.append(f'inflacja {a}: zły miesiąc albo liczba'); continue
            last = _rl_k_seria(o.get('s'), RL_K_INFL_ZAKRES, f'inflacja {a}', zle)
            if last is not None and (last[0] != o['m'] or abs(last[1] - o['v']) > 1e-9):
                zle.append(f'inflacja {a}: ostatni punkt serii różni się od pól m/v')
            ost[a] = o
        if ost:
            asof = max((o['m'] for o in ost.values()), key=_rl_k_mi)
            if infl.get('asof') != asof:
                zle.append(f'inflacja: pole asof {infl.get("asof")} ≠ najnowszy miesiąc {asof}')
            w = wiek_danych(asof, 'month', 'm', now)
            st = '?' if w is None else ('⚠\ufe0f' if w > RL_K_INFL_PROG else '✅')
            note = f'najnowszy miesiąc starszy niż {fmt_wiek(RL_K_INFL_PROG)} — źródło spóźnia się z miesiącem albo plik przestał się odświeżać; najwyżej uwaga' if st == '⚠\ufe0f' else ''
            out['rows'].append(('Inflacja r/r (miesięcznie, najnowszy miesiąc)', st, w, asof, note))
            if st == '⚠\ufe0f':
                out['uwagi'].append(f'Inflacja r/r: najnowszy miesiąc {asof} — {fmt_wiek(w)} temu ({note})')
        else:
            out['rows'].append(('Inflacja r/r (miesięcznie, najnowszy miesiąc)', '?', None, None, 'brak poprawnej inflacji w pliku'))
    # ---- tylko informacja: USA — BIS a BLS ----
    try:
        us = ost.get('US')
        yoy = ((usam or {}).get('s') or {}).get('cpi', {}).get('yoy') if isinstance(usam, dict) else None
        if us and isinstance(yoy, list):
            bl = {r[0]: _rl_k_num(r[1]) for r in yoy if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str)}
            x = bl.get(us['m'])
            if x is not None:
                roz = abs(us['v'] - x)
                out['wiersze'].append((f'inflacja USA {us["m"]}: {us["v"]:.2f} % (plik inflacja) a {x:.1f} % (CPI-U z pliku usa-makro) — tylko informacja', '✅' if roz <= RL_K_BLS else '\u2139\ufe0f'))
    except Exception as e:  # noqa
        zle.append(f'porównanie USA: {str(e)[:60]}')
    # ---- pokrycie stopy realnej ----
    if ost and isinstance(stopy, dict) and isinstance(stopy.get('rows'), dict):
        n = k = 0
        for a, r in stopy['rows'].items():
            if not (isinstance(r, dict) and _rl_k_num(r.get('rate')) is not None):
                continue
            k += 1
            o, m = ost.get(a), _rl_k_mi(str(r.get('date'))[:7])
            if o and m is not None and m - _rl_k_mi(o['m']) <= RL_K_MAX_MIES:
                n += 1
        if k:
            slabo = n * 2 < k
            out['wiersze'].append((f'stopa realna policzona dla {n} z {k} banków (reszta: brak inflacji albo starsza niż {RL_K_MAX_MIES} mies. od stanu stopy)', '⚠\ufe0f' if slabo else '✅'))
            if slabo:
                out['uwagi'].append(f'Stopa realna: tylko {n} z {k} banków ma inflację nie starszą niż {RL_K_MAX_MIES} mies. — kolumna na stronie prawie pusta')
    # ---- koniunktura ----
    kc = kon.get('c') if isinstance(kon, dict) and kon.get('v') == 1 and isinstance(kon.get('c'), dict) else None
    if kc:
        miesiace, ost_k = [], {}
        for cz in ('cci', 'bci'):
            P = kc.get(cz)
            if not isinstance(P, dict) or not P:
                zle.append(f'koniunktura {cz}: brak części'); continue
            for iso, s in P.items():
                last = _rl_k_seria(s, RL_K_KON_ZAKRES, f'koniunktura {cz} {iso}', zle)
                if last is not None:
                    miesiace.append(last[0]); ost_k[(cz, iso)] = last
            if 'POL' not in P:
                zle.append(f'koniunktura {cz}: brak Polski')
        if ('cci', 'POL') in ost_k and ('bci', 'POL') in ost_k:
            wsp = [i for (c_, i) in ost_k if c_ == 'cci' and ('bci', i) in ost_k]
            if len(wsp) >= 5 and all(ost_k[('cci', i)] == ost_k[('bci', i)] for i in wsp):
                zle.append('koniunktura: zaufanie konsumentów i firm to ta sama seria (jedna miara nadpisała drugą)')
        if miesiace:
            asof = max(miesiace, key=_rl_k_mi)
            w = wiek_danych(asof, 'month', 'm', now)
            st = '?' if w is None else ('⚠\ufe0f' if w > RL_K_KON_PROG else '✅')
            note = f'najnowszy miesiąc starszy niż {fmt_wiek(RL_K_KON_PROG)} — źródło spóźnia się z miesiącem albo plik przestał się odświeżać; najwyżej uwaga' if st == '⚠\ufe0f' else ''
            out['rows'].append(('Koniunktura: zaufanie konsumentów i firm (miesięcznie)', st, w, asof, note))
            if st == '⚠\ufe0f':
                out['uwagi'].append(f'Koniunktura: najnowszy miesiąc {asof} — {fmt_wiek(w)} temu ({note})')
    elif isinstance(kon, dict) and kon.get('v') == 1:
        out['rows'].append(('Koniunktura: zaufanie konsumentów i firm (miesięcznie)', '?', None, None, 'brak części w pliku'))
    for z in zle[:4]:
        out['uwagi'].append(f'inflacja i koniunktura (v366): {z}')
    if out['rows']:
        out['wiersze'].append(('spójność plików (miesiące, liczby, Polska w obu miarach zaufania)', '⚠\ufe0f' if zle else '✅'))
    return out


# ---------------------------------------------------------------- v367 (F5Z2): prąd i CO2 (data/prad.json) ----------------------------------------------------------------
# Plik: pl (Polska: cena energii w kwadransach doby, dziś i jutro, zł/MWh), co2 (cena uprawnień do emisji, €/t i zł/t, dziennie także w weekendy), str (15 stref Europy:
# dzień dzisiejszy i jutrzejszy jako [średnia, min, max, liczba okresów], €/MWh). Świeżość trzech części osobnymi wierszami (lista SWIEZOSC bez zmian), najwyżej ⚠️.
# Progi (nagrania 13–14.10.2026; publikacje: jutrzejsza doba Polski 13.10 o 13:58 czasu polskiego, ceny CO2 co dzień także w sobotę i niedzielę 10–11.10):
# * jutro w Polsce: dopiero po PRAD_K_JUTRO_UTC (15:00 UTC = 17:00 latem / 16:00 zimą w Polsce; publikacja ok. 13:45 czasu polskiego) — wcześniej brak jutrzejszej doby NIE jest uwagą;
# * ceny ujemne są dozwolone (nadmiar wiatru i słońca) — tylko informacja o liczbie kwadransów; uwagą dopiero średnia doby poniżej −500 albo powyżej 3000 zł/MWh;
# * CO2: dzień danych starszy niż 3 doby (dane powstają co dzień, także w weekend);
# * strefy: mniej niż 10 z 15 stref z danymi odświeżonymi w ciągu 6 h albo — po 18:00 UTC — mniej niż 8 stref z jutrzejszą dobą (źródło publikuje dobę następną w strefach
#   w różnych godzinach; 13.10 wieczorem część stref nie miała jeszcze doby następnej);
# * RCE Polski a cena w strefie Polska ze źródła europejskiego (ta sama doba, po kursie z ceny CO2): ponad 5% różnicy = uwaga (13.10: 0,7%);
# * RCE a indeks prądu z giełdy w polska.json (inny rynek): ponad 12% różnicy tej samej doby = uwaga (plan: 0,8% dla 11.10).
# ❌ / BŁĄD wyłącznie przy sprzeczności wewnątrz pliku (liczba kwadransów ≠ n albo spoza 92/96/100, średnia dobowa w hist ≠ średnia z kwadransów ±0,01, asof ≠ najnowszy dzień,
# dni nie rosną, minimum > średnia > maksimum w strefie, cena CO2 poza zakresem).
PLIKI.insert(PLIKI.index('krypto-dzien'), 'prad')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['prad'] = 8 * 60   # plik zapisywany co przebieg; strefy odświeżane co ok. 10 min (jedna na przebieg), Polska i CO2 co 3 h — wiek dnia danych ocenia wiersz świeżości
AW_BEZ_BLEDU.update({k_: 'prąd i CO2 — część z błędem zostaje z datą (v367); wiek danych w wierszach świeżości' for k_ in ('prad', 'prad_pl', 'prad_co2', 'prad_str')})
PRAD_K_JUTRO_UTC = 15          # godzina UTC, po której jutrzejsza doba Polski powinna być w pliku
PRAD_K_STR_JUTRO_UTC = 18      # godzina UTC, po której co najmniej PRAD_K_STR_JUTRO stref powinno mieć jutrzejszą dobę
PRAD_K_STR_JUTRO, PRAD_K_STR_SW, PRAD_K_STR_SW_H = 8, 10, 6
PRAD_K_CO2_DNI = 3
PRAD_K_ETYKIETA = {'pl': 'Prąd w Polsce: cena w kwadransach, dziś i jutro (dziennie)', 'co2': 'Prąd i CO2: cena uprawnień do emisji (dziennie, także w weekend)',
                 'str': 'Prąd w Europie: ceny w 15 strefach (dziś i jutro)'}
PRAD_K_RCE_STREFA, PRAD_K_RCE_TGE = 0.05, 0.12   # względna różnica RCE do strefy Polska / do indeksu giełdowego (tylko uwaga)
PRAD_K_AVG_MIN, PRAD_K_AVG_MAX = -500.0, 3000.0  # zł/MWh — średnia doby (uwaga)


def _prad_k_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))


def _prad_k_dzien(s):
    try:
        return dt.date.fromisoformat(s) if isinstance(s, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', s) else None
    except ValueError:
        return None


def _prad_k_dzis(now):
    """Dzień polski dla 'now' bez bazy stref: UTC + 1 h (zima) albo 2 h (lato: od ostatniej niedzieli marca do ostatniej niedzieli października, 01:00 UTC)."""
    def ost_nd(y, m):
        d = dt.date(y, m, 31)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    a = dt.datetime.combine(ost_nd(now.year, 3), dt.time(1), dt.timezone.utc)
    b = dt.datetime.combine(ost_nd(now.year, 10), dt.time(1), dt.timezone.utc)
    return (now + dt.timedelta(hours=2 if a <= now < b else 1)).date()


def prad_swiezosc(j, now=None):
    """Wiersze świeżości trzech części pliku prad.json (etykieta, status, wiek min, data danych, uwaga). Najwyżej ⚠️; brak pliku albo inna wersja = brak wierszy; część bez dnia
    danych — '?'."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    rows = []
    dzis = _prad_k_dzis(now)
    jutro = dzis + dt.timedelta(days=1)
    for p, label in PRAD_K_ETYKIETA.items():
        e = j.get(p) if isinstance(j.get(p), dict) else {}
        txt = e.get('asof')
        if not txt:
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); continue
        w = wiek_danych(str(txt), 'day', 'k', now)
        if p == 'pl':
            d = e.get('d') if isinstance(e.get('d'), dict) else {}
            if dzis.isoformat() not in d:
                st, note = '⚠️', f'brak dzisiejszej doby ({dzis.isoformat()}) — ostatnia {txt}; najwyżej uwaga'
            elif jutro.isoformat() not in d and now.hour >= PRAD_K_JUTRO_UTC:
                st, note = '⚠️', f'jutrzejsza doba ({jutro.isoformat()}) jeszcze nie opublikowana po godzinie publikacji (ok. 13:45 czasu polskiego; sprawdzenie po {PRAD_K_JUTRO_UTC}:00 UTC) — najwyżej uwaga'
            else:
                st, note = '✅', ''
        elif p == 'co2':
            st = '?' if w is None else ('⚠️' if w > PRAD_K_CO2_DNI * 1440 else '✅')
            note = f'dzień danych starszy niż {PRAD_K_CO2_DNI} doby (źródło publikuje co dzień, także w weekend) — najwyżej uwaga' if st == '⚠️' else ''
        else:
            Z = e.get('z') if isinstance(e.get('z'), dict) else {}
            sw = sum(1 for v in Z.values() if isinstance(v, dict) and isinstance(v.get('at'), str) and wiek_danych(v['at'], 'ts', 'k', now) is not None
                     and wiek_danych(v['at'], 'ts', 'k', now) <= PRAD_K_STR_SW_H * 60)
            zj = sum(1 for v in Z.values() if isinstance(v, dict) and isinstance(v.get('d'), dict) and jutro.isoformat() in v['d'])
            zle = []
            if sw < PRAD_K_STR_SW:
                zle.append(f'tylko {sw} z 15 stref odświeżonych w ciągu {PRAD_K_STR_SW_H} h (próg {PRAD_K_STR_SW})')
            if now.hour >= PRAD_K_STR_JUTRO_UTC and zj < PRAD_K_STR_JUTRO:
                zle.append(f'jutrzejszą dobę ma {zj} z 15 stref po {PRAD_K_STR_JUTRO_UTC}:00 UTC (próg {PRAD_K_STR_JUTRO})')
            st = '⚠️' if zle else '✅'
            note = '; '.join(zle) + (' — najwyżej uwaga (limit zapytań źródła: jedna strefa na przebieg)' if zle else '')
        rows.append((label, st, w, str(txt), note))
    return rows


def prad_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w prądzie i CO2) → lista opisów."""
    zle = []
    pl = j.get('pl') if isinstance(j.get('pl'), dict) else {}
    d = pl.get('d') if isinstance(pl.get('d'), dict) else {}
    hist = pl.get('hist') if isinstance(pl.get('hist'), list) else []
    hd = {r[0]: r[1] for r in hist if isinstance(r, list) and len(r) == 2}
    if pl and d and pl.get('asof') != max(d):
        zle.append(f'pl: asof {pl.get("asof")} ≠ najnowszy dzień {max(d)}')
    for k, v in d.items():
        p = v.get('p') if isinstance(v, dict) else None
        if _prad_k_dzien(k) is None or not isinstance(p, list) or v.get('n') != len(p) or len(p) not in (92, 96, 100) or not all(_prad_k_num(x) for x in p):
            zle.append(f'pl {k}: liczba kwadransów ≠ n albo spoza 92/96/100 albo brak liczby'); continue
        sr = sum(p) / len(p)
        if k in hd and _prad_k_num(hd[k]) and abs(hd[k] - sr) > 0.011:
            zle.append(f'pl {k}: średnia dobowa w hist {hd[k]} ≠ średnia z kwadransów {sr:.2f}')
    ds = [r[0] for r in hist if isinstance(r, list) and r]
    if ds != sorted(set(ds)):
        zle.append('pl: hist — dni nie rosną')
    c = j.get('co2') if isinstance(j.get('co2'), dict) else {}
    cd = c.get('d') if isinstance(c.get('d'), list) else []
    dd = [r[0] for r in cd if isinstance(r, list) and r]
    if dd != sorted(set(dd)) or (cd and c.get('asof') != dd[-1]):
        zle.append('co2: dni nie rosną albo asof ≠ ostatni dzień')
    for r in cd:
        if not (isinstance(r, list) and len(r) == 3 and _prad_k_dzien(r[0]) and _prad_k_num(r[1]) and 5.0 <= r[1] <= 500.0 and (r[2] is None or (_prad_k_num(r[2]) and r[2] > 0))):
            zle.append(f'co2 {r[0] if isinstance(r, list) and r else "?"}: zła pozycja'); break
    s = j.get('str') if isinstance(j.get('str'), dict) else {}
    for z, e in (s.get('z') or {}).items() if isinstance(s.get('z'), dict) else []:
        for k, v in ((e.get('d') or {}) if isinstance(e, dict) and isinstance(e.get('d'), dict) else {}).items():
            if not (isinstance(v, list) and len(v) == 4 and all(_prad_k_num(x) for x in v) and v[1] <= v[0] <= v[2] and v[3] in (23, 24, 25, 92, 96, 100) and _prad_k_dzien(k)):
                zle.append(f'str {z} {k}: zła pozycja (średnia poza minimum–maksimum albo zła liczba okresów)')
    return zle


def prad_porownania(j, files, now=None):
    """Tylko informacje i uwagi ⚠️ (nigdy ❌): ceny ujemne, średnia doby poza zakresem, RCE a strefa Polska, RCE a indeks giełdowy z polska.json. → {'wiersze': [(opis, znak)], 'uwagi': [...]}"""
    now = now or NOW
    out = {'wiersze': [], 'uwagi': []}
    pl = j.get('pl') if isinstance(j.get('pl'), dict) else {}
    d = pl.get('d') if isinstance(pl.get('d'), dict) else {}
    c = j.get('co2') if isinstance(j.get('co2'), dict) else {}
    kurs = {}
    for r in (c.get('d') or []) if isinstance(c.get('d'), list) else []:
        if isinstance(r, list) and len(r) == 3 and _prad_k_num(r[1]) and _prad_k_num(r[2]) and r[1] > 0 and r[2] > 0:
            kurs[r[0]] = r[2] / r[1]
    dzis = _prad_k_dzis(now).isoformat()
    for k in sorted(d):
        v = d[k]
        p = v.get('p') if isinstance(v, dict) else None
        if not (isinstance(p, list) and p and all(_prad_k_num(x) for x in p)):
            continue
        sr = sum(p) / len(p)
        ujem = sum(1 for x in p if x < 0)
        if k == dzis or k == max(d):
            out['wiersze'].append((f'Polska {k}: średnia {sr:.1f} zł/MWh, minimum {min(p):.1f}, maksimum {max(p):.1f}; kwadransów z ceną ujemną: {ujem} (dozwolone — tylko informacja)', 'ℹ️'))
        if not (PRAD_K_AVG_MIN <= sr <= PRAD_K_AVG_MAX):
            out['wiersze'].append((f'Polska {k}: średnia doby {sr:.1f} zł/MWh poza zakresem [{PRAD_K_AVG_MIN:.0f}; {PRAD_K_AVG_MAX:.0f}]', '⚠️'))
            out['uwagi'].append(f'Prąd w Polsce {k}: średnia doby {sr:.1f} zł/MWh poza zakresem [{PRAD_K_AVG_MIN:.0f}; {PRAD_K_AVG_MAX:.0f}] — sprawdź źródło')
        # RCE wobec strefy Polska ze źródła europejskiego (ta sama doba, kurs z ceny CO2 tego dnia albo najbliższego wcześniejszego)
        ec = ((((j.get('str') or {}).get('z') or {}).get('PL') or {}).get('d') or {}).get(k) if isinstance(j.get('str'), dict) and isinstance((j.get('str') or {}).get('z'), dict) else None
        kr = kurs.get(k) or (kurs[max(x for x in kurs if x <= k)] if any(x <= k for x in kurs) else None)
        if isinstance(ec, list) and len(ec) == 4 and _prad_k_num(ec[0]) and ec[0] > 0 and kr:
            eur = sr / kr
            roz = abs(eur - ec[0]) / ec[0]
            ok = roz <= PRAD_K_RCE_STREFA
            out['wiersze'].append((f'Polska {k}: RCE {eur:.1f} €/MWh (po kursie z ceny CO2) wobec strefy Polska {ec[0]:.1f} €/MWh — różnica {roz * 100:.1f}%', '✅' if ok else '⚠️'))
            if not ok:
                out['uwagi'].append(f'Prąd w Polsce {k}: RCE {eur:.1f} €/MWh a strefa Polska {ec[0]:.1f} €/MWh — różnica {roz * 100:.1f}% (próg {PRAD_K_RCE_STREFA * 100:.0f}%)')
        # RCE wobec indeksu giełdowego (polska.json: energia.prad.d = [[dzień, zł/MWh]])
        pj = files.get('polska') if isinstance(files, dict) else None
        tge = ((((pj or {}).get('energia') or {}).get('prad') or {}).get('d')) if isinstance(pj, dict) and isinstance(pj.get('energia'), dict) else None
        if isinstance(tge, list):
            t = {r[0]: r[1] for r in tge if isinstance(r, list) and len(r) == 2 and _prad_k_num(r[1])}
            if k in t and t[k] > 0:
                roz = abs(sr - t[k]) / t[k]
                ok = roz <= PRAD_K_RCE_TGE
                out['wiersze'].append((f'Polska {k}: RCE {sr:.1f} zł/MWh wobec indeksu giełdowego {t[k]:.1f} zł/MWh (inny rynek) — różnica {roz * 100:.1f}%', '✅' if ok else '⚠️'))
                if not ok:
                    out['uwagi'].append(f'Prąd w Polsce {k}: RCE {sr:.1f} zł/MWh a indeks giełdowy {t[k]:.1f} zł/MWh — różnica {roz * 100:.1f}% (próg {PRAD_K_RCE_TGE * 100:.0f}%; inny rynek)')
    return out


def prad_kontrola(files, now=None):
    """Kontrola pliku prad.json bez sieci: sprzeczności w pliku (❌ = BŁĄD, zapisuje je hook w kontrola()) i progi (najwyżej ⚠️). Brak pliku albo inna wersja = None (raport bez linii).
    → {'spojnosc': [...], 'wiersze': [(opis, znak)], 'uwagi': [...], 'czesci_bez_odpowiedzi': [...]}"""
    j = files.get('prad') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    P = prad_porownania(j, files, now)
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': prad_spojnosc(j), 'wiersze': P['wiersze'], 'uwagi': P['uwagi'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v368 (F8Z4): stres i niepewność (data/niepewnosc.json) ----------------------------------------------------------------
# Trzy części jednego pliku zbieracza: ciss (złożony wskaźnik stresu systemowego, 14 obszarów, dni robocze), epu (niepewność polityki gospodarczej USA, wszystkie dni kalendarza) i gpr
# (ryzyko geopolityczne, wszystkie dni kalendarza); dla epu i gpr strona pokazuje średnią 30 dni. Kontrola czyta plik ze strony (bez zapytań do sieci) i sprawdza:
# (1) wiek dnia danych każdej części osobnym wierszem (godziny robocze, bez sobót i niedziel). Stan 13.10.2026: CISS ukazuje się z opóźnieniem 2 dni roboczych (we wtorek wieczorem najnowszy
#     jest piątek, ok. 46 godzin roboczych), EPU i GPR z opóźnieniem do 1 dnia. Progi z kalendarza publikacji, nie z testu wstecznego (źródła nie udostępniają dat wydań): CISS 144 h roboczych
#     (3 dni zwykłego opóźnienia + 2 dni przerwy w święta EBC, np. Wielki Piątek i Poniedziałek Wielkanocny, + zapas), EPU i GPR 96 h roboczych; ⚠ = źródło spóźnia się albo część przestała się
#     odświeżać (najwyżej uwaga, nigdy błąd przebiegu);
# (2) spójność w pliku z progami z ROZKŁADU HISTORII (test wsteczny na całych danych źródeł, 13.10.2026): największy dzienny skok CISS w 5 latach 14 obszarów to 0,112 (próg 0,2), największa
#     dzienna zmiana średniej 30 dni w latach 1985–2026 to 29,1 (EPU) i 33,1 (GPR) — progi 45 i 50 (1,5 raza więcej), zmiana średniej 30 dni wobec średniej sprzed 30 dni nie większa niż 600 (EPU; maksimum historii 386) i 900 (GPR; maksimum 618) — prawdziwe kryzysy (wrzesień 2001, kwiecień 2020) NIE są alarmem,
#     dzienna wartość nie większa niż 1,5 raza historyczne maksimum (ok. 1050 → 1600),
#     średnia 30 dni w granicach obejmujących całą historię z marginesem (co najwyżej 0,6 minimum i co najmniej 1,4 maksimum: EPU 33,6–585,8 → 15–900; GPR 39,1–681,7 → 20–1000). W całej historii obu serii takie progi dają 0 alarmów — także dla zmiany 30 dni (zob. test i bt_progi.py), a błąd
#     skali, przesunięta kolumna albo wartość utknięta (30 dni tych samych liczb) i tak je przekroczą. Do tego: dni rosnące bez powtórzeń, ostatni punkt wykresu = pola date i v/ma30, percentyle 0–100,
#     cztery główne obszary CISS z wykresem, komplet 14 obszarów, daty głównych obszarów nie rozjeżdżają się o więcej niż 5 dni;
# (3) TYLKO INFORMACJA: CISS USA a indeks stresu USA z pliku stres.json (inne źródło): korelacja poziomów na wspólnych dniach (13.10.2026: 0,75 na 400 dniach; w oknach 120-dniowych od −0,2 do 0,87,
#     więc żaden próg nie byłby uczciwy — podajemy liczbę, bez oceny).
# Najwyżej ⚠ (nigdy błąd przebiegu); brak pliku zgłasza pętla PLIKI.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'niepewnosc')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['niepewnosc'] = 12 * 60   # odpytanie co 6 h (część z błędem: co godzinę) — wiek pliku; wiek dnia danych ocenia wiersz świeżości
AW_BEZ_BLEDU.update({'niepewnosc_' + p_: 'stres i niepewność — część z błędem zostaje z datą (v368); wiek danych w wierszach świeżości' for p_ in ('ciss', 'epu', 'gpr')})
NP_K_PROG = {'ciss': 144 * 60, 'epu': 96 * 60, 'gpr': 96 * 60}   # min roboczych — wiek dnia danych (kalendarz publikacji wyżej)
NP_K_ETYKIETA = {'ciss': 'Stres i niepewność: stres systemowy CISS (strefa euro; dni robocze)', 'epu': 'Stres i niepewność: niepewność polityki USA (EPU)',
                 'gpr': 'Stres i niepewność: ryzyko geopolityczne (GPR)'}
NP_K_SKOK_CISS = 0.2              # dzienna zmiana CISS (test wsteczny: maksimum 0,112)
NP_K_SKOK_MA = {'epu': 45.0, 'gpr': 50.0}                 # dzienna zmiana średniej 30 dni (maksimum 1985–2026: 29,1 i 33,1)
NP_K_D30 = {'epu': 600.0, 'gpr': 900.0}                 # zmiana średniej 30 dni wobec średniej sprzed 30 dni (maksimum 1985–2026: EPU 386, GPR 618 — próg ponad maksimum z marginesem ≥ 1,4 raza)
NP_K_DZIEN_MAX = 1600.0           # dzienna wartość EPU / GPR (maksimum 1985–2026: ok. 1050)
NP_K_MA_ZAKRES = {'epu': (15.0, 900.0), 'gpr': (20.0, 1000.0)}   # średnia 30 dni (historia: EPU 33,6–585,8; GPR 39,1–681,7)
NP_K_OBSZARY = ('U2', 'US', 'GB', 'CN', 'AT', 'BE', 'DE', 'ES', 'FI', 'FR', 'IE', 'IT', 'NL', 'PT')
NP_K_GLOWNE = ('U2', 'US', 'GB', 'CN')
NP_K_ROZJAZD_D = 5                # dni — rozjazd dat głównych obszarów CISS
NP_K_UTKNIETA = 30                # tyle takich samych liczb z rzędu w wykresie = wartość utknięta


def _np_k_num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def _np_k_dzien(s):
    return dt.date.fromisoformat(s) if isinstance(s, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', s) else None


def _np_k_hist(h, nazwa, zakres, skok, zle, minlen):
    """wykres [[dzień, liczba], …]: dni ściśle rosnące, liczby w zakresie, dzienne zmiany nie większe niż skok, wartość nie utknięta; zwraca ostatnią parę albo None"""
    if not isinstance(h, list) or len(h) < minlen:
        zle.append(f'{nazwa}: wykres krótszy niż {minlen} dni'); return None
    prev = None
    run = 1
    for i, p in enumerate(h):
        if not (isinstance(p, list) and len(p) == 2 and _np_k_dzien(p[0]) and _np_k_num(p[1]) is not None):
            zle.append(f'{nazwa}: zły punkt wykresu'); return None
        if prev is not None:
            if p[0] <= prev[0]:
                zle.append(f'{nazwa}: dni wykresu nie rosną'); return None
            if abs(p[1] - prev[1]) > skok:
                zle.append(f'{nazwa}: skok {abs(p[1] - prev[1]):.3f} między {prev[0]} a {p[0]} ponad progiem {skok}'); return None
            run = run + 1 if p[1] == prev[1] else 1
            if run >= NP_K_UTKNIETA:
                zle.append(f'{nazwa}: {run} takich samych liczb z rzędu (wartość utknięta)'); return None
        if not zakres[0] <= p[1] <= zakres[1]:
            zle.append(f'{nazwa}: liczba {p[1]} poza zakresem'); return None
        prev = p
    return h[-1]


def niepewnosc_kontrola(np_, stres=None, now=None):
    """Plik data/niepewnosc.json (+ stres.json) → {'rows': [(etykieta, status, wiek min, dzień, uwaga)], 'uwagi': [...], 'wiersze': [(opis, znak)], 'spojnosc': [...]}; brak pliku albo inna
    wersja = brak wierszy (wiek pliku i brak pliku zgłasza pętla PLIKI). Część bez danych w pliku = wiersz '?'. Najwyżej ⚠."""
    now = now or NOW
    out = {'rows': [], 'uwagi': [], 'wiersze': [], 'spojnosc': []}
    zle = out['spojnosc']
    if not (isinstance(np_, dict) and np_.get('v') == 1):
        return out
    # ---- ciss ----
    C = np_.get('ciss') if isinstance(np_.get('ciss'), dict) else None
    ar = C.get('a') if C and isinstance(C.get('a'), dict) else None
    if ar:
        brak = [a for a in NP_K_OBSZARY if a not in ar]
        if brak:
            zle.append('CISS: brak obszarów ' + ', '.join(brak))
        dni = []
        for a, o in ar.items():
            if a not in NP_K_OBSZARY or not isinstance(o, dict):
                zle.append(f'CISS {a}: nieznany obszar albo zły wiersz'); continue
            v, d1, p = _np_k_num(o.get('v')), _np_k_num(o.get('d1')), _np_k_num(o.get('p'))
            if v is None or not 0 <= v <= 1 or _np_k_dzien(o.get('date')) is None:
                zle.append(f'CISS {a}: zła liczba albo dzień'); continue
            if d1 is not None and abs(d1) > NP_K_SKOK_CISS:
                zle.append(f'CISS {a}: dzienna zmiana {d1} ponad progiem {NP_K_SKOK_CISS}')
            if o.get('p') is not None and (p is None or not 0 <= p <= 100):
                zle.append(f'CISS {a}: percentyl poza 0–100')
            if a in NP_K_GLOWNE:
                dni.append(o['date'])
                last = _np_k_hist(o.get('hist'), f'CISS {a}', (0.0, 1.0), NP_K_SKOK_CISS, zle, 200)
                if last is not None and (last[0] != o['date'] or abs(last[1] - v) > 1e-9):
                    zle.append(f'CISS {a}: ostatni punkt wykresu różni się od pól date/v')
        if len(dni) == len(NP_K_GLOWNE) and (max(map(_np_k_dzien, dni)) - min(map(_np_k_dzien, dni))).days > NP_K_ROZJAZD_D:
            zle.append(f'CISS: daty głównych obszarów rozjeżdżają się o więcej niż {NP_K_ROZJAZD_D} dni')
        u2 = ar.get('U2') if isinstance(ar.get('U2'), dict) else {}
        txt = u2.get('date')
        if txt is None:
            out['rows'].append((NP_K_ETYKIETA['ciss'], '?', None, None, 'brak strefy euro w pliku'))
        else:
            w = wiek_danych(txt, 'day', 'd', now)
            st = '?' if w is None else ('⚠\ufe0f' if w > NP_K_PROG['ciss'] else '✅')
            note = f'próg {fmt_wiek(NP_K_PROG["ciss"])} roboczych — źródło spóźnia się albo część przestała się odświeżać; najwyżej uwaga' if st == '⚠\ufe0f' else ''
            out['rows'].append((NP_K_ETYKIETA['ciss'], st, w, txt, note))
            if st == '⚠\ufe0f':
                out['uwagi'].append(f'{NP_K_ETYKIETA["ciss"]}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
    else:
        out['rows'].append((NP_K_ETYKIETA['ciss'], '?', None, None, 'brak części w pliku'))
    # ---- epu i gpr ----
    for k in ('epu', 'gpr'):
        P = np_.get(k) if isinstance(np_.get(k), dict) else None
        if not P:
            out['rows'].append((NP_K_ETYKIETA[k], '?', None, None, 'brak części w pliku')); continue
        v, m, d30, p = (_np_k_num(P.get(x)) for x in ('v', 'ma30', 'd30', 'p'))
        zk = NP_K_MA_ZAKRES[k]
        if v is None or not 0 < v <= NP_K_DZIEN_MAX or m is None or not zk[0] <= m <= zk[1] or _np_k_dzien(P.get('date')) is None:
            zle.append(f'{k.upper()}: wartość dnia albo średnia 30 dni poza zakresem')
        else:
            last = _np_k_hist(P.get('hist'), k.upper(), zk, NP_K_SKOK_MA[k], zle, 300)
            if last is not None and (last[0] != P['date'] or abs(last[1] - m) > 0.006):
                zle.append(f'{k.upper()}: ostatni punkt wykresu różni się od pól date/ma30')
        if P.get('p') is None or p is None or not 0 <= p <= 100:
            zle.append(f'{k.upper()}: brak percentyla albo poza 0–100')
        if d30 is not None and abs(d30) > NP_K_D30[k]:
            zle.append(f'{k.upper()}: zmiana 30 dni {d30} ponad progiem {NP_K_D30[k]} (większa niż w całej historii 1985–2026)')
        txt = P.get('date')
        w = wiek_danych(txt, 'day', 'd', now) if _np_k_dzien(txt) else None
        st = '?' if w is None else ('⚠\ufe0f' if w > NP_K_PROG[k] else '✅')
        note = f'próg {fmt_wiek(NP_K_PROG[k])} roboczych — źródło spóźnia się albo część przestała się odświeżać; najwyżej uwaga' if st == '⚠\ufe0f' else ('brak dnia danych w pliku' if st == '?' else '')
        out['rows'].append((NP_K_ETYKIETA[k], st, w, txt if _np_k_dzien(txt) else None, note))
        if st == '⚠\ufe0f':
            out['uwagi'].append(f'{NP_K_ETYKIETA[k]}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
    # ---- tylko informacja: CISS USA a indeks stresu USA ----
    try:
        us = ar.get('US') if ar else None
        fh = ((stres or {}).get('fsi') or {}).get('hist') if isinstance(stres, dict) else None
        if isinstance(us, dict) and isinstance(us.get('hist'), list) and isinstance(fh, list):
            a = {r[0]: r[1] for r in us['hist'] if isinstance(r, list) and len(r) >= 2 and _np_k_num(r[1]) is not None}
            b = {r[0]: r[1] for r in fh if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and _np_k_num(r[1]) is not None}
            wsp = sorted(set(a) & set(b))
            if len(wsp) >= 100:
                x, y = [float(a[d]) for d in wsp], [float(b[d]) for d in wsp]
                mx, my = sum(x) / len(x), sum(y) / len(y)
                sxx, syy = sum((i - mx) ** 2 for i in x), sum((i - my) ** 2 for i in y)
                if sxx > 0 and syy > 0:
                    r = sum((i - mx) * (j - my) for i, j in zip(x, y)) / (sxx * syy) ** 0.5
                    out['wiersze'].append((f'CISS USA a indeks stresu USA (plik stres): korelacja poziomów {r:.2f} na {len(wsp)} wspólnych dniach — tylko informacja', 'ℹ\ufe0f'))
    except Exception as e:  # noqa
        zle.append(f'porównanie CISS USA z indeksem stresu: {str(e)[:60]}')
    for z in zle[:4]:
        out['uwagi'].append(f'stres i niepewność (v368): {z}')
    if out['rows']:
        out['wiersze'].append(('spójność pliku (zakresy, skoki dzienne, wykresy, percentyle, komplet obszarów)', '⚠\ufe0f' if zle else '✅'))
    return out


# ---------------------------------------------------------------- v372 (F9Z1): kalendarz „Najbliższe 14 dni” (data/kalendarz.json) ----------------------------------------------------------------
# Plik: e (terminy każdej z pięciu części: fed, bea, census, eurostat, ecb; czas w UTC, kod, region, waga 1–3, g = z terminarza / z reguły), n (po części: [rozpoznanych w całej odpowiedzi,
# w oknie pliku]), ok / part_at / errs, od / do (okno pliku: wczoraj … +30 dni UTC), brak (obszary bez terminarza). Kontrola czyta plik ze strony (bez zapytań do sieci):
# (1) świeżość pobrania każdej części osobnym wierszem (odświeżanie co 6 h, część z błędem co godzinę): starsza niż KAL_K_PROG_MIN = ⚠ (najwyżej uwaga);
# (2) TERMINARZ PUSTY ALBO PRZETERMINOWANY (⚠ z opisem): brak jakiegokolwiek terminu w następnych 14 dniach, plik starszy niż KAL_K_PLIK_MIN, terminy kończą się wcześniej niż za 14 dni,
#     część, która w całej odpowiedzi rozpoznała mniej terminów niż próg (parser zgubił tabelę), część fed/bea/census/eurostat bez żadnego terminu w oknie pliku;
# (3) ❌ wyłącznie przy sprzeczności wewnątrz pliku: zły czas / kod / region / waga (waga i region muszą zgadzać się z tabelą kodów), dubel, terminy poza oknem pliku od–do, terminy w części
#     nie rosną, liczba w oknie w n ≠ liczbie terminów (część z ok True), wersja inna niż 1 pomijana (brak wierszy);
# (4) TYLKO UWAGA ⚠: data decyzji FOMC w terminarzu różni się od posiedzenia na rynku zakładów (plik fed: ks.meetings[].date) — obie daty w następnych 30 dniach muszą się pokrywać.
# Najwyżej ⚠ poza (3). Brak pliku zgłasza pętla PLIKI.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'kalendarz')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['kalendarz'] = 12 * 60   # plik zapisywany co ok. 6 h (część z błędem: co godzinę) — wiek pobrania każdej części ocenia osobny wiersz
AW_BEZ_BLEDU.update({'kalendarz_' + p_: 'kalendarz — część z błędem zostaje ze starymi terminami i datą (v372); wiek pobrania w wierszach świeżości' for p_ in ('bc_us', 'pkb_us', 'sprz_us', 'stat_eu', 'bc_eu')})
KAL_K_PROG_MIN = 24 * 60          # min — wiek pobrania części (odświeżanie co 6 h)
KAL_K_PLIK_MIN = 48 * 60          # min — plik starszy = terminarz przeterminowany
KAL_K_OKNO_DNI = 14               # okno strony
KAL_K_FOMC_DNI = 30               # dni — porównanie z rynkiem zakładów
KAL_K_PARTS = ('bc_us', 'pkb_us', 'sprz_us', 'stat_eu', 'bc_eu')
KAL_K_ROZP_MIN = {'bc_us': 10, 'pkb_us': 10, 'sprz_us': 8, 'stat_eu': 3, 'bc_eu': 3}   # progi parsera (jak bramki zbieracza)
KAL_K_BEZ_OKNA = ('bc_us', 'pkb_us', 'sprz_us', 'stat_eu')   # części, które muszą mieć termin w oknie pliku (ECB ma posiedzenia co ok. 6 tygodni)
KAL_K_NAZWA = {'bc_us': 'Fed', 'pkb_us': 'BEA', 'sprz_us': 'Census', 'stat_eu': 'Eurostat', 'bc_eu': 'EBC'}   # nazwy części w komunikatach kontroli (raport wewnętrzny, nie strona)
KAL_K_ETYKIETA = {'bc_us': 'Kalendarz: terminarz Rezerwy Federalnej (pobranie)', 'pkb_us': 'Kalendarz: terminarz PKB i inflacji PCE USA (pobranie)',
                  'sprz_us': 'Kalendarz: terminarz sprzedaży i budownictwa USA (pobranie)', 'stat_eu': 'Kalendarz: terminarz statystyk strefy euro (pobranie)',
                  'bc_eu': 'Kalendarz: terminarz posiedzeń EBC (pobranie)'}
KAL_K_KODY = {
    'fomc': ('us', 3), 'fomc_min': ('us', 2), 'beige': ('us', 1), 'g17': ('us', 1), 'h41': ('us', 1), 'z1': ('us', 1),
    'us_pkb': ('us', 3), 'us_pce': ('us', 3), 'us_handel': ('us', 1), 'us_bop': ('us', 1), 'us_iip': ('us', 1),
    'us_sprzedaz': ('us', 2), 'us_trwale': ('us', 1), 'us_budowy': ('us', 1),
    'eu_cpi_flash': ('eu', 3), 'eu_cpi': ('eu', 2), 'eu_pkb_flash': ('eu', 3), 'eu_pkb': ('eu', 2), 'eu_bezrob': ('eu', 2), 'eu_esi': ('eu', 1), 'eu_prod': ('eu', 1), 'eu_handel': ('eu', 1),
    'eu_stopy': ('eu', 3),
}


def _kal_k_czas(s):
    """„RRRR-MM-DDTGG:MMZ” → datetime w UTC albo None."""
    if not isinstance(s, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z', s):
        return None
    try:
        return dt.datetime.strptime(s, '%Y-%m-%dT%H:%MZ').replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def kalendarz_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w kalendarzu) → lista opisów."""
    zle = []
    e = j.get('e') if isinstance(j.get('e'), dict) else None
    if e is None:
        return ['brak pola e (terminów)']
    od, do = j.get('od'), j.get('do')
    for k, L in e.items():
        if k not in KAL_K_PARTS or not isinstance(L, list):
            zle.append(f'{k}: nieznana część albo zła lista'); continue
        prev, widziane = None, set()
        for x in L:
            u = _kal_k_czas(x.get('t')) if isinstance(x, dict) else None
            tab = KAL_K_KODY.get(x.get('k')) if isinstance(x, dict) else None
            if u is None or tab is None:
                zle.append(f'{k}: zły czas albo nieznany kod terminu ({str(x)[:60]})'); continue
            if (x.get('r'), x.get('w')) != tab:
                zle.append(f'{k} {x["k"]}: region/waga {x.get("r")}/{x.get("w")} ≠ tabela {tab[0]}/{tab[1]}')
            if x.get('g') not in ('z', 'r'):
                zle.append(f'{k} {x["k"]}: pole g ≠ z/r')
            if (x['t'], x['k']) in widziane:
                zle.append(f'{k}: dubel {x["t"]} {x["k"]}')
            widziane.add((x['t'], x['k']))
            if prev is not None and x['t'] < prev:
                zle.append(f'{k}: terminy nie rosną ({prev} przed {x["t"]})')
            prev = x['t']
            if isinstance(od, str) and isinstance(do, str) and not od <= x['t'][:10] <= do:
                zle.append(f'{k}: termin {x["t"]} poza oknem pliku {od} … {do}')
        n = (j.get('n') or {}).get(k) if isinstance(j.get('n'), dict) else None
        if (j.get('ok') or {}).get(k) is True and isinstance(n, list) and len(n) == 2 and n[1] != len(L):
            zle.append(f'{k}: n[1] = {n[1]} ≠ liczba terminów {len(L)}')
    return zle[:12]


def kalendarz_swiezosc(j, now=None):
    """Wiersze świeżości pobrania pięciu części (etykieta, status, wiek min, chwila pobrania, uwaga); brak pliku albo inna wersja = brak wierszy; część bez chwili — '?'. Najwyżej ⚠."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    rows = []
    for p in KAL_K_PARTS:
        txt = (j.get('part_at') or {}).get(p) if isinstance(j.get('part_at'), dict) else None
        if not txt:
            rows.append((KAL_K_ETYKIETA[p], '?', None, None, 'brak chwili pobrania tej części w pliku')); continue
        w = wiek_danych(str(txt), 'ts', 'k', now)
        ok = (j.get('ok') or {}).get(p) if isinstance(j.get('ok'), dict) else None
        st = '?' if w is None else ('⚠\ufe0f' if w > KAL_K_PROG_MIN else '✅')
        note = ''
        if st == '⚠\ufe0f':
            note = f'pobranie starsze niż {fmt_wiek(KAL_K_PROG_MIN)} (odświeżanie co 6 h) — terminy mogą być nieaktualne; najwyżej uwaga'
        elif ok is False:
            note = 'ostatnie pobranie nieudane — terminy z poprzedniego pobrania'
        rows.append((KAL_K_ETYKIETA[p], st, w, str(txt), note))
    return rows


def kalendarz_uwagi(j, fed=None, now=None):
    """Uwagi ⚠ (nigdy ❌): terminarz pusty albo przeterminowany, parser, FOMC a rynek zakładów. → {'wiersze': [(opis, znak)], 'uwagi': [...]}"""
    now = now or NOW
    out = {'wiersze': [], 'uwagi': []}
    e = j.get('e') if isinstance(j.get('e'), dict) else {}
    wszystkie = []   # (chwila, część, termin)
    for k, L in e.items():
        for x in L if isinstance(L, list) else []:
            u = _kal_k_czas(x.get('t')) if isinstance(x, dict) else None
            if u is not None:
                wszystkie.append((u, k, x))
    koniec = now + dt.timedelta(days=KAL_K_OKNO_DNI)
    w14 = [t for t in wszystkie if now <= t[0] < koniec]
    st = '✅' if w14 else '⚠\ufe0f'
    out['wiersze'].append((f'terminy w następnych {KAL_K_OKNO_DNI} dniach: {len(w14)}' + (f' (w tym wagi 3: {sum(1 for t in w14 if t[2].get("w") == 3)})' if w14 else ' — terminarz pusty'), st))
    if not w14:
        out['uwagi'].append(f'Kalendarz: terminarz pusty — żadnego terminu w następnych {KAL_K_OKNO_DNI} dniach (źródła nie zwróciły terminów albo plik przeterminowany)')
    at = j.get('at')
    w = wiek_danych(str(at), 'ts', 'k', now) if at else None
    if w is not None and w > KAL_K_PLIK_MIN:
        out['uwagi'].append(f'Kalendarz: terminarz przeterminowany — plik sprzed {fmt_wiek(w)} (próg {fmt_wiek(KAL_K_PLIK_MIN)})')
        out['wiersze'].append((f'wiek pliku {fmt_wiek(w)} — terminarz przeterminowany', '⚠\ufe0f'))
    if wszystkie:
        ost = max(t[0] for t in wszystkie)
        if ost < koniec:
            out['uwagi'].append(f'Kalendarz: terminy kończą się {ost.date().isoformat()} — wcześniej niż za {KAL_K_OKNO_DNI} dni (terminarz przeterminowany albo część źródeł bez terminów)')
            out['wiersze'].append((f'ostatni termin w pliku {ost.date().isoformat()} — za wcześnie', '⚠\ufe0f'))
    n = j.get('n') if isinstance(j.get('n'), dict) else {}
    for p in KAL_K_PARTS:
        nn = n.get(p)
        if isinstance(nn, list) and len(nn) == 2 and all(isinstance(v, int) for v in nn):
            if nn[0] < KAL_K_ROZP_MIN[p]:
                out['uwagi'].append(f'Kalendarz {KAL_K_NAZWA[p]}: rozpoznano tylko {nn[0]} terminów (próg {KAL_K_ROZP_MIN[p]}) — zmieniony układ źródła?')
            elif p in KAL_K_BEZ_OKNA and nn[1] < 1:
                out['uwagi'].append(f'Kalendarz {KAL_K_NAZWA[p]}: żadnego terminu w oknie pliku — zmieniony układ źródła albo pusty terminarz')
        elif (j.get('ok') or {}).get(p) is True:
            out['uwagi'].append(f'Kalendarz {KAL_K_NAZWA[p]}: brak liczników n w pliku')
    # ---- FOMC a rynek zakładów (tylko uwaga) ----
    try:
        ms = ((fed or {}).get('ks') or {}).get('meetings') if isinstance(fed, dict) else None
        daty_rynku = sorted({m['date'] for m in ms if isinstance(m, dict) and isinstance(m.get('date'), str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', m['date'])}) if isinstance(ms, list) else []
        gr = (now + dt.timedelta(days=KAL_K_FOMC_DNI)).date().isoformat()
        rynek = [d for d in daty_rynku if now.date().isoformat() <= d <= gr]
        nasze = sorted({t[0].date().isoformat() for t in wszystkie if t[1] == 'bc_us' and t[2].get('k') == 'fomc' and now.date().isoformat() <= t[0].date().isoformat() <= gr})
        if rynek and (j.get('ok') or {}).get('bc_us') is True:
            zg = rynek == nasze
            out['wiersze'].append((f'decyzja FOMC: terminarz {", ".join(nasze) or "—"} a rynek zakładów {", ".join(rynek)}', '✅' if zg else '⚠\ufe0f'))
            if not zg:
                out['uwagi'].append(f'Kalendarz: data decyzji FOMC w terminarzu ({", ".join(nasze) or "brak"}) ≠ posiedzenie na rynku zakładów ({", ".join(rynek)})')
    except Exception as ex:  # noqa
        out['uwagi'].append(f'Kalendarz: porównanie FOMC z rynkiem zakładów przerwane ({str(ex)[:60]})')
    return out


def kalendarz_kontrola(files, now=None):
    """Kontrola pliku kalendarz.json bez sieci → {'spojnosc': [...], 'wiersze': [(opis, znak)], 'uwagi': [...], 'czesci_bez_odpowiedzi': [...]}; brak pliku albo inna wersja = None (raport bez linii)."""
    j = files.get('kalendarz') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    U = kalendarz_uwagi(j, files.get('fed'), now)
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': kalendarz_spojnosc(j), 'wiersze': U['wiersze'], 'uwagi': U['uwagi'], 'czesci_bez_odpowiedzi': nie}


# ---------------------------------------------------------------- v375 (F9Z1, część 2): kalendarz 2 (data/kalendarz2.json) ----------------------------------------------------------------
# Plik: e (terminy czterech części: cpi_praca_us, dane_pl, bc_uk, bc_jp; czas w UTC, kod, region, waga 1–3, g = r), n (po części: [rozpoznanych w całej odpowiedzi, w oknie pliku]), ok / part_at / errs,
# od / do, brak (obszary bez terminarza). Kontrola czyta plik ze strony (bez zapytań do sieci): (1) świeżość pobrania każdej części osobnym wierszem (najwyżej ⚠); (2) parser: część, która w całej
# odpowiedzi rozpoznała mniej terminów niż próg, albo część cpi_praca_us / dane_pl bez terminu w oknie pliku (⚠); (3) ❌ wyłącznie przy sprzeczności wewnątrz pliku: zły czas / kod / region / waga
# (muszą zgadzać się z tabelą kodów), dubel, termin poza oknem od–do, terminy w części nie rosną, n[1] ≠ liczbie terminów. Brak pliku zgłasza pętla PLIKI.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'kalendarz2')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['kalendarz2'] = 12 * 60   # plik zapisywany co ok. 6 h (część z błędem: co godzinę) — wiek pobrania każdej części ocenia osobny wiersz
AW_BEZ_BLEDU.update({'kalendarz2_' + p_: 'kalendarz 2 — część z błędem zostaje ze starymi terminami i datą (v375); wiek pobrania w wierszach świeżości' for p_ in ('cpi_praca_us', 'dane_pl', 'bc_uk', 'bc_jp')})
KAL2_K_PARTS = ('cpi_praca_us', 'dane_pl', 'bc_uk', 'bc_jp')
KAL2_K_ROZP_MIN = {'cpi_praca_us': 6, 'dane_pl': 20, 'bc_uk': 6, 'bc_jp': 8}   # progi parsera (jak bramki zbieracza)
KAL2_K_BEZ_OKNA = ('cpi_praca_us', 'dane_pl')   # części, które muszą mieć termin w oknie pliku (decyzje banków są co kilka tygodni)
KAL2_K_NAZWA = {'cpi_praca_us': 'FRED', 'dane_pl': 'GUS', 'bc_uk': 'BoE', 'bc_jp': 'BoJ'}   # nazwy części w komunikatach kontroli (raport wewnętrzny, nie strona)
KAL2_K_ETYKIETA = {'cpi_praca_us': 'Kalendarz 2: terminy inflacji i zatrudnienia USA (pobranie)', 'dane_pl': 'Kalendarz 2: kalendarz danych Polski (pobranie)',
                   'bc_uk': 'Kalendarz 2: terminy decyzji banku Anglii (pobranie)', 'bc_jp': 'Kalendarz 2: terminy posiedzeń banku Japonii (pobranie)'}
KAL2_K_KODY = {'us_cpi': ('us', 3), 'us_praca': ('us', 3), 'pl_cpi': ('pl', 2), 'pl_pkb': ('pl', 2), 'pl_prod': ('pl', 1), 'pl_praca': ('pl', 1), 'uk_stopy': ('gb', 3), 'jp_stopy': ('jp', 3)}


def kalendarz2_spojnosc(j):
    """Sprzeczności wewnątrz pliku (jedyny powód ❌ w kalendarzu 2) → lista opisów."""
    zle = []
    e = j.get('e') if isinstance(j.get('e'), dict) else None
    if e is None:
        return ['brak pola e (terminów)']
    od, do = j.get('od'), j.get('do')
    for k, L in e.items():
        if k not in KAL2_K_PARTS or not isinstance(L, list):
            zle.append(f'{k}: nieznana część albo zła lista'); continue
        prev, widziane = None, set()
        for x in L:
            u = _kal_k_czas(x.get('t')) if isinstance(x, dict) else None
            tab = KAL2_K_KODY.get(x.get('k')) if isinstance(x, dict) else None
            if u is None or tab is None:
                zle.append(f'{k}: zły czas albo nieznany kod terminu ({str(x)[:60]})'); continue
            if (x.get('r'), x.get('w')) != tab:
                zle.append(f'{k} {x["k"]}: region/waga {x.get("r")}/{x.get("w")} ≠ tabela {tab[0]}/{tab[1]}')
            if x.get('g') not in ('z', 'r'):
                zle.append(f'{k} {x["k"]}: pole g ≠ z/r')
            if (x['t'], x['k']) in widziane:
                zle.append(f'{k}: dubel {x["t"]} {x["k"]}')
            widziane.add((x['t'], x['k']))
            if prev is not None and x['t'] < prev:
                zle.append(f'{k}: terminy nie rosną ({prev} przed {x["t"]})')
            prev = x['t']
            if isinstance(od, str) and isinstance(do, str) and not od <= x['t'][:10] <= do:
                zle.append(f'{k}: termin {x["t"]} poza oknem pliku {od} … {do}')
        n = (j.get('n') or {}).get(k) if isinstance(j.get('n'), dict) else None
        if (j.get('ok') or {}).get(k) is True and isinstance(n, list) and len(n) == 2 and n[1] != len(L):
            zle.append(f'{k}: n[1] = {n[1]} ≠ liczba terminów {len(L)}')
    return zle[:12]


def kalendarz2_swiezosc(j, now=None):
    """Wiersze świeżości pobrania czterech części (etykieta, status, wiek min, chwila pobrania, uwaga); brak pliku albo inna wersja = brak wierszy. Najwyżej ⚠ (próg jak w kalendarzu: KAL_K_PROG_MIN)."""
    now = now or NOW
    if not isinstance(j, dict) or j.get('v') != 1:
        return []
    rows = []
    for p in KAL2_K_PARTS:
        txt = (j.get('part_at') or {}).get(p) if isinstance(j.get('part_at'), dict) else None
        if not txt:
            rows.append((KAL2_K_ETYKIETA[p], '?', None, None, 'brak chwili pobrania tej części w pliku')); continue
        w = wiek_danych(str(txt), 'ts', 'k', now)
        ok = (j.get('ok') or {}).get(p) if isinstance(j.get('ok'), dict) else None
        st = '?' if w is None else ('⚠️' if w > KAL_K_PROG_MIN else '✅')
        note = ''
        if st == '⚠️':
            note = f'pobranie starsze niż {fmt_wiek(KAL_K_PROG_MIN)} (odświeżanie co 6 h) — terminy mogą być nieaktualne; najwyżej uwaga'
        elif ok is False:
            note = 'ostatnie pobranie nieudane — terminy z poprzedniego pobrania'
        rows.append((KAL2_K_ETYKIETA[p], st, w, str(txt), note))
    return rows


def kalendarz2_uwagi(j):
    """Uwagi ⚠ (nigdy ❌): parser zgubił tabelę albo część bez terminu w oknie → {'wiersze': [(opis, znak)], 'uwagi': [...]}"""
    out = {'wiersze': [], 'uwagi': []}
    n = j.get('n') if isinstance(j.get('n'), dict) else {}
    for p in KAL2_K_PARTS:
        nn = n.get(p)
        if isinstance(nn, list) and len(nn) == 2 and all(isinstance(v, int) for v in nn):
            if nn[0] < KAL2_K_ROZP_MIN[p]:
                out['uwagi'].append(f'Kalendarz 2 {KAL2_K_NAZWA[p]}: rozpoznano tylko {nn[0]} terminów (próg {KAL2_K_ROZP_MIN[p]}) — zmieniony układ źródła?')
            elif p in KAL2_K_BEZ_OKNA and nn[1] < 1:
                out['uwagi'].append(f'Kalendarz 2 {KAL2_K_NAZWA[p]}: żadnego terminu w oknie pliku — zmieniony układ źródła albo pusty terminarz')
        elif (j.get('ok') or {}).get(p) is True:
            out['uwagi'].append(f'Kalendarz 2 {KAL2_K_NAZWA[p]}: brak liczników n w pliku')
    out['wiersze'].append(('terminy: ' + ', '.join(f'{KAL2_K_NAZWA[p]} {len((j.get("e") or {}).get(p) or [])}' for p in KAL2_K_PARTS), '⚠️' if out['uwagi'] else '✅'))
    return out


def kalendarz2_kontrola(files):
    """Kontrola pliku kalendarz2.json bez sieci → {'spojnosc': [...], 'wiersze': [(opis, znak)], 'uwagi': [...], 'czesci_bez_odpowiedzi': [...]}; brak pliku albo inna wersja = None (raport bez linii)."""
    j = files.get('kalendarz2') if isinstance(files, dict) else None
    if not isinstance(j, dict) or j.get('v') != 1:
        return None
    U = kalendarz2_uwagi(j)
    nie = sorted(k for k, v in (j.get('ok') or {}).items() if v is False) if isinstance(j.get('ok'), dict) else []
    return {'spojnosc': kalendarz2_spojnosc(j), 'wiersze': U['wiersze'], 'uwagi': U['uwagi'], 'czesci_bez_odpowiedzi': nie}


def kontrola():
    R = {'at': NOW.isoformat(), 'strona': {}, 'meta': {}, 'pliki': {}, 'actions': {}, 'swiezosc': [], 'zgodnosc': {}, 'uwagi': [], 'bledy': []}
    _R_BIEZACY[0] = R; termin_start()   # v327 (KON-04): wspólny termin całej kontroli; R widoczny dla raportu częściowego
    files = {}
    # 1. strona główna
    try:
        st, body, ms = get_ponow(f'{SITE}/index.html?nc={int(time.time())}')   # v327 (KON-05): jedno ponowienie przy 5xx albo przekroczeniu czasu
        ok = st == 200 and len(body) > 1_000_000 and b'const EXTRA' in body
        R['strona'] = {'http': st, 'bajty': len(body), 'ms': ms, 'ok': ok}
        if not ok:
            R['bledy'].append(f'strona główna: HTTP {st}, {len(body)} B')
    except Exception as e:  # noqa
        R['strona'] = {'ok': False, 'blad': str(e)[:200]}
        R['bledy'].append(f'strona główna nie odpowiada: {str(e)[:120]}')
    # 1b. v141: lżejsza strona — pliki słowników języków wskazane przez index.html (HTTP 200, skrót = treść); pełna strona = uwaga; najwyżej ⚠️
    try:
        i18n_kontrola(body if (R.get('strona') or {}).get('ok') else None, R)
    except Exception as e:  # noqa
        R['uwagi'].append(f'pliki słowników języków: kontrola nie przeszła ({str(e)[:80]})')
    # 1c. v247: strona w przeglądarce bez okna (Chrome, ekran telefonu) — błędy JavaScriptu na prawdziwych danych; najwyżej ⚠️. Tylko gdy
    # KONTROLA_PRZEGLADARKA=1 (ustawia kontrola.yml): testy wołające kontrola() nie mogą uruchamiać przeglądarki — ona ma własną sieć
    if (R.get('strona') or {}).get('ok') and os.environ.get('KONTROLA_PRZEGLADARKA') == '1':
        try:
            R['przegladarka'] = strona_przegladarka(f'{SITE}/?nc={int(time.time())}' + PRZEGL_PELNA)   # v308: wszystko od razu, jak dawniej (pliki CRYPTO bez czekania na otwarcie zakładki)
        except Exception as e:  # noqa
            R['przegladarka'] = {'stan': 'blad', 'brak': f'błąd sprawdzania: {type(e).__name__}'}
        u = przegladarka_uwagi(R['przegladarka'], przegladarka_poprzedni(os.path.join(OUT_DIR, 'historia.json')))   # v248: drugi raz bez strony = uwaga
        if u and R['przegladarka'].get('stan') == 'zawieszona':
            R['przegladarka']['powtorka'] = True
        R['uwagi'] += u
        R['przegladarka_lekka'] = przegladarka_lekka(SITE, R['przegladarka'])   # v308: druga runda — strona jak u czytelnika (bez ?pelna=1)
        R['uwagi'] += przegladarka_uwagi_lekka(R['przegladarka_lekka'])
    # 2. plik stanu automatu
    try:
        st, body, ms = get_ponow(f'{SITE}/data/meta.json?nc={int(time.time())}')   # v327 (KON-05): jedno ponowienie przy 5xx albo przekroczeniu czasu
        m = json.loads(body); files['meta'] = m
        w = wiek_min(m.get('at'))
        nie = sorted(k for k, v in (m.get('ok') or {}).items() if v is False)
        R['meta'] = {'at': m.get('at'), 'wiek_min': w, 'zrodla': len(m.get('ok') or {}), 'bez_odpowiedzi': nie,
                     'errors': [str(x)[:160] for x in (m.get('errors') or [])], 'notes': [str(x)[:160] for x in (m.get('notes') or [])],
                     'czas': m.get('czas') if isinstance(m.get('czas'), dict) else None,   # v185: czas przebiegu automatu
                     'awarie_od': m.get('awarie_od') if isinstance(m.get('awarie_od'), str) else None}   # v211: początek pamięci awarii
        if w is None:
            R['bledy'].append('plik stanu bez czasu przebiegu')
        elif w > 180:
            R['bledy'].append(f'automat nie odświeżył danych od {w // 60} godz. (ostatni przebieg {czas_pl(m.get("at"))})')
        elif w > LIMIT_MIN['meta']:
            R['uwagi'].append(f'ostatni przebieg automatu sprzed {w} min (zwykle co 10 min)')
        if nie:
            R['uwagi'].append('źródła bez odpowiedzi w ostatnim przebiegu: ' + ', '.join(nie))
        for e in (m.get('errors') or []):   # v211: dopisek z pełnej treści (dotąd z obciętej do 160 znaków)
            R['uwagi'].append('błąd zbieracza: ' + str(e)[:160] + awaria_rodzaj(e))   # v207: dopisek — odrzucony klucz / limit planu
        aw = awarie_ocena(m)   # v207: pamięć awarii zbieracza — od kiedy część nie działa, co naprawiło się samo (None = zbieracz sprzed v207)
        if aw is not None:
            R['awarie'] = aw
            R['uwagi'] += aw['uwagi']; R['bledy'] += aw['bledy']
        zu = zuzycie_ocena(m)   # v222: licznik zużycia darmowych planów (None = zbieracz sprzed v222)
        if zu is not None:
            R['zuzycie'] = zu
            R['uwagi'] += zu['uwagi']; R['bledy'] += zu['bledy']
    except Exception as e:  # noqa
        R['meta'] = {'blad': str(e)[:200]}
        R['bledy'].append(f'plik stanu (meta.json) nie odpowiada: {str(e)[:120]}')
    # 3. wiek plików danych
    pominiete, pow_pom = [], None   # v327 (KON-04): strona wisi albo minął termin — reszta plików bez zapytań, jedna uwaga
    for n in PLIKI:
        if n == 'meta':
            continue
        pp = site_pomin()
        if pp:
            R['pliki'][n] = {'pominiete': True}; pominiete.append(n); pow_pom = pow_pom or pp
            continue
        try:
            st, body, ms = get(f'{SITE}/data/{n}.json?nc={int(time.time())}')
            j = json.loads(body); files[n] = j if isinstance(j, dict) else None
            w = wiek_min(j.get('at')) if isinstance(j, dict) else None
            okp = j.get('ok') if isinstance(j, dict) else None
            nie = sorted(k for k, v in okp.items() if v is False) if isinstance(okp, dict) else []
            R['pliki'][n] = {'http': st, 'bajty': len(body), 'wiek_min': w, 'czesci_bez_odpowiedzi': nie}
            if isinstance(j, dict) and j.get('off') is True:   # v176: plik części wyłączonej celowo (np. insiderzy bez SEC_CONTACT) — stan, nie usterka
                R['pliki'][n]['wylaczone'] = str(j.get('powod') or 'wyłączone')[:160]
            if w is not None and w > LIMIT_MIN.get(n, 24 * 60):
                R['uwagi'].append(f'{n}.json sprzed {w // 60} godz. {w % 60} min (limit {LIMIT_MIN.get(n, 1440) // 60} godz.)')
            if nie:
                R['uwagi'].append(f'{n}.json: części bez odpowiedzi: ' + ', '.join(nie))
        except urllib.error.HTTPError as e:
            R['pliki'][n] = {'http': e.code}
            wyl = wylaczone(files.get('meta')).get(n) if e.code == 404 else None
            if wyl:
                R['pliki'][n]['wylaczone'] = wyl                       # v171: część wyłączona celowo — opis, nie uwaga
            elif n in ('etf', 'trendy', 'oecd', 'rynki'):
                R['uwagi'].append(f'{n}.json: HTTP {e.code}')
            elif n != 'indeksy':
                R['uwagi'].append(f'{n}.json: HTTP {e.code} (brak pliku)')
        except Exception as e:  # noqa
            R['pliki'][n] = {'blad': str(e)[:160]}
            R['uwagi'].append(f'{n}.json: {str(e)[:100]}')
    # 3b. v111: pliki dla wyszukiwarek (robots.txt, sitemap.xml, plik weryfikacji Google) — tylko kod HTTP; v348: także skrypt licznika count.js (strona ładuje go z własnego adresu)
    for f in ('robots.txt', 'sitemap.xml', 'google433f7c24524100a9.html', 'count.js', 'sw.js'):
        pp = site_pomin()   # v327 (KON-04)
        if pp:
            R['pliki'][f] = {'pominiete': True}; pominiete.append(f); pow_pom = pow_pom or pp
            continue
        try:
            st, body, ms = get(f'{SITE}/{f}?nc={int(time.time())}')
            R['pliki'][f] = {'http': st, 'bajty': len(body)}
            if st != 200 or len(body) < 20:
                R['uwagi'].append(f'{f}: HTTP {st}, {len(body)} B')
        except urllib.error.HTTPError as e:   # v111.1: kod HTTP w wierszu plików, nie „HTTP ?”
            R['pliki'][f] = {'http': e.code}; R['uwagi'].append(f'{f}: HTTP {e.code}')
        except Exception as e:  # noqa
            R['pliki'][f] = {'blad': str(e)[:120]}; R['uwagi'].append(f'{f}: {str(e)[:80]}')
    if pominiete:   # v327 (KON-04): jedna uwaga zamiast uwagi przy każdym pliku
        R['uwagi'].append(f'pominięto plików strony: {len(pominiete)} ({pow_pom}) — ' + ', '.join(pominiete[:6]) + (' …' if len(pominiete) > 6 else ''))
    # 3c. v115: świeżość źródeł wg kategorii — żółte po progu, czerwone po 2×
    for label, st, w, txt, note in swiezosc(files):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '❌':
            R['bledy'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c'. v131: świeżość szans Fed (osobny wiersz tabeli — lista SWIEZOSC bez zmian) i uwagi o jakości cen (informacja)
    fr = fed_swiezosc(files.get('fed'))
    if fr:
        label, st, w, txt, note = fr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '❌':
            R['bledy'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    R['uwagi'].extend(fed_uwagi(files.get('fed')))
    # 3c''. v132: wycena BTC — świeżość części MVRV (dziennie) i SOPR (źródło opóźnia 7 dni; najwyżej ⚠️) jako osobne wiersze (lista SWIEZOSC
    # bez zmian) oraz MVRV z dwóch źródeł (drugie źródło tylko do tej kontroli) — najwyżej uwaga, nigdy błąd
    for label, st, w, txt, note in wycena_swiezosc(files.get('wycena')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '❌':
            R['bledy'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    if isinstance(files.get('wycena'), dict):
        R['zgodnosc']['wycena'] = wycena_mvrv(files.get('wycena'))
        R['uwagi'] += R['zgodnosc']['wycena']['uwagi']
    # 3c''. v136: świeżość kursów dolara Ameryki Łacińskiej — osobny wiersz tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    dr = dolar_swiezosc(files.get('dolar'))
    if dr:
        label, st, w, txt, note = dr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c'''. v134: świeżość funduszy USA (data/ici.json) — osobne wiersze tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    for label, st, w, txt, note in ici_swiezosc(files.get('ici')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-su. v295: surowce (data/surowce.json w wersji 2) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in surowce_swiezosc(files.get('surowce')) + surowce_swiezosc3(files.get('surowce')):   # v298: + etap 3
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-sz. v305: szlaki handlowe i łańcuchy dostaw (data/szlaki.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in szlaki_swiezosc(files.get('szlaki')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-lng. v340: gaz i LNG (data/lng.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in lng_swiezosc(files.get('lng')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-zm. v352: zmienność rynków (data/zmiennosc.json), put/call i indeks stresu (data/stres.json) — świeżość każdej części osobnym wierszem; najwyżej ⚠️
    for label, st, w, txt, note in zm_swiezosc(files.get('zmiennosc'), files.get('stres')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-ru. v353: Rosja (data/rosja.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in rosja_swiezosc(files.get('rosja')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-plr. v361 (F3Z2): Polska na rynku dziennie (data/polska-rynek.json) — świeżość każdej z trzech części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in polska_rynek_swiezosc(files.get('polska-rynek')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-pk. v365 (F3Z3): Polska — kapitał z zagranicy i wypłaty UE (data/polska-kapital.json) — świeżość każdej z dwóch części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in polska_kapital_swiezosc(files.get('polska-kapital')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-pd. v371 (F3Z1): Polska — kto trzyma dług skarbowy i sprzedaż obligacji detalicznych (data/polska-dlug.json) — świeżość każdej z dwóch części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in polska_dlug_swiezosc(files.get('polska-dlug')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-gx. v349 (F6Z1): giełdy scentralizowane i DEX (data/gieldy.json, data/dex.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in gx_swiezosc(files.get('gieldy'), files.get('dex')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-sr. v320: raporty miesięczne o surowcach (data/surowce-raporty.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in surowce_raporty_swiezosc(files.get('surowce-raporty')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-zd. v341 (F5Z3): zboża dziennie i koszt transportu (data/zboza-dzien.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in zboza_swiezosc(files.get('zboza-dzien')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-zs. v327 (KON-08): zastój źródeł Meksyku, SPW i Korei (zbieracz zgłasza go tylko w przebiegu budującym plik) — progi zbieracza, osobne
    # wiersze (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    for label, st, w, txt, note in zastoj_swiezosc(files):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-pip. v337 (F2Z4): MFW PIP (data/pip.json) — wiek półrocza (≤ PIP_OKRES_MIES mies. od końca) i suma posiadaczy ≈ wiersz świata; osobne
    # wiersze (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    P_pip = pip_kontrola(files.get('pip'))
    for label, st, w, txt, note in P_pip['rows']:
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
    R['uwagi'] += P_pip['uwagi']
    # 3c-dzw. v343 (F1Z3): dźwignia (data/dzwignia.json) — wiek krzywej terminowej Deribit i Coinbase USA (czas z odpowiedzi giełdy) oraz zgodność basis
    # Deribit vs OKX w tym samym terminie; osobne wiersze (lista SWIEZOSC bez zmian); najwyżej ostrzeżenie, nigdy błąd krytyczny ani BŁĄD
    P_dzw = dzw_kontrola(files.get('dzwignia'))
    for label, st, w, txt, note in P_dzw['rows']:
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
    R['uwagi'] += P_dzw['uwagi']
    # 3c-dzw9. v369 (F6Z2): dźwignia — pięć dalszych giełd (Bitget, Gate, KuCoin, MEXC, HTX): wiek odczytu, kompletność BTC/ETH i — tylko informacja — suma wobec poprzedniego
    # zestawu giełd; osobne wiersze (lista SWIEZOSC bez zmian); najwyżej ostrzeżenie, nigdy błąd krytyczny ani BŁĄD
    P_dzw9 = dzw9_kontrola(files.get('dzwignia'))
    for label, st, w, txt, note in P_dzw9['rows']:
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
    R['uwagi'] += P_dzw9['uwagi']
    # 3c-mt. v339 (F4Z1+F4Z2): metale przemysłowe (data/metale.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️
    for label, st, w, txt, note in metale_swiezosc(files.get('metale')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-fu. v342 (F1Z2): fundusze ETF w USA (data/fundusze.json) — fundusze z ostatnią sesją wydawcy (≥ 95%, bez danych 3 sesje) i NAV a zamknięcie
    # na giełdzie (data/ceny.json); osobne wiersze (lista SWIEZOSC bez zmian); najwyżej uwaga (⚠), nigdy ❌ ani BŁĄD
    F_fu = fundusze_kontrola(files.get('fundusze'), files.get('ceny'))
    for label, st, w, txt, note in F_fu['rows']:
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
    R['uwagi'] += F_fu['uwagi']
    # 3c-pl. v304: Polska (data/polska.json) — świeżość każdej części osobnym wierszem (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    for label, st, w, txt, note in polska_swiezosc(files.get('polska')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c''. v137: Japonia — kto handluje akcjami na giełdzie: świeżość wg kalendarza publikacji (4. dzień roboczy następnego tygodnia, święta
    # w Japonii) — osobny wiersz tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    jr = jpx_swiezosc(files.get('jpx'))
    if jr:
        label, st, w, txt, note = jr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    ju = jpx_swieta_uwaga()
    if ju:
        R['uwagi'].append(ju)
    # 3c''''. v162: dzienniki sygnałów TRENDÓW — ostatni dzień z wynikiem (treść pliku, nie jego wiek); osobne wiersze tabeli, najwyżej ⚠️
    for plik, _lab, _kat, _prog in DZ_SPEC:
        dz = dziennik_swiezosc(files.get(plik), plik)
        if dz:
            label, st, w, txt, note = dz
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
            if st == '⚠️':
                R['uwagi'].append(f'{label}: ostatni wynik z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
            elif st == '?':
                R['uwagi'].append(f'{label}: {note}')
    # 3c'''''. v303: dziennik reguł „w cieniu” SUROWCE — ostatni dzień z wynikiem (treść pliku, nie jego wiek); osobny wiersz tabeli, najwyżej ⚠️
    sz = su_dziennik_swiezosc(files.get('surowce-dziennik'))
    if sz:
        label, st, w, txt, note = sz
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: ostatni wynik z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-su309. v309: TRENDY surowce — dane funduszy surowcowych w pliku swiat-dzien (wejścia reguł „w cieniu”); osobne wiersze, najwyżej ⚠️
    for label, st, w, txt, note in su_fundusze_swiezosc(files.get('swiat-dzien')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-ng373. v373: nowe grupy w TRENDACH — dziennik reguł „w cieniu” (ostatni dzień z wynikiem) i ceny 14 funduszy wyników; osobne wiersze, najwyżej ⚠️
    ngz = ng_dziennik_swiezosc(files.get('ng-dziennik'))
    for label, st, w, txt, note in ([ngz] if ngz else []) + ng_ceny_swiezosc(files.get('ng-ceny')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: ostatni wynik z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c''. v133: tokenizowane aktywa RWA (data/rwa.json) — świeżość listy osobnym wierszem tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️,
    # nigdy ❌ ani BŁĄD
    rr = rwa_swiezosc(files.get('rwa'))
    if rr:
        label, st, w, txt, note = rr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c'''. v150: tokenizowane aktywa — odczyt własny z łańcucha (blok onchain w data/rwa.json) — osobny wiersz (lista SWIEZOSC bez zmian);
    # najwyżej ⚠️; brak bloku albo wyłącznik RWA_CHAIN_OFF = „—” bez uwagi
    rc = rwc_swiezosc(files.get('rwa'))
    if rc:
        label, st, w, txt, note = rc
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c''''. v169: tokenizowane aktywa — dane emitentów (blok issuer w data/rwa.json) — osobny wiersz (lista SWIEZOSC bez zmian); najwyżej ⚠️;
    # brak bloku albo wyłącznik RWA_EM_OFF = „—” bez uwagi
    re_ = rwe_swiezosc(files.get('rwa'))
    if re_:
        label, st, w, txt, note = re_
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c-v355. TARGET krajów strefy euro (data/target.json) i rejestry MiCA (data/mica.json): wiek danych i spójność z plików strony, bez zapytań; najwyżej ⚠️
    for nm_, fn_, args_ in (('target', target_kontrola, (files.get('target'), files.get('instytucje'))), ('mica', mica_kontrola, (files.get('mica'),))):
        try:
            T_ = fn_(*args_)
            for label, st, w, txt, note in T_['rows']:
                R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
            R['uwagi'] += T_['uwagi']
            R['zgodnosc'][nm_] = {'spojnosc': T_['spojnosc'], 'wiersze': T_['wiersze']} if (T_['rows'] or T_['wiersze']) else None
        except Exception as e:  # noqa
            R['zgodnosc'][nm_] = {'blad': str(e)[:120]}
            R['uwagi'].append(f'{nm_}: kontrola przerwana ({str(e)[:80]})')
    # 3c-v357. skład portfela Fed, pozycje bilansu Eurosystemu i fundusze hedgingowe (data/soma-sklad.json, eurosystem.json, hedge.json): wiek dnia danych, spójność i zgodność
    # z panelem „dane urzędowe” (instytucje.json) — z plików strony, bez zapytań; najwyżej ⚠️
    try:
        T_ = plynnosc_kontrola(files.get('soma-sklad'), files.get('eurosystem'), files.get('hedge'), files.get('instytucje'))
        for label, st, w, txt, note in T_['rows']:
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        R['uwagi'] += T_['uwagi']
        R['zgodnosc']['plynnosc'] = {'spojnosc': T_['spojnosc'], 'wiersze': T_['wiersze']} if (T_['rows'] or T_['wiersze']) else None
    except Exception as e:  # noqa
        R['zgodnosc']['plynnosc'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'płynność i fundusze (v357): kontrola przerwana ({str(e)[:80]})')
    # 3c-v363. emitenci stablecoinów (data/stable-emitenci.json): wiek raportów Tether i Circle, spójność w pliku, porównania z drugim źródłem — z plików strony, bez zapytań; TYLKO informacja, najwyżej ⚠️
    try:
        os.makedirs(OUT_DIR, exist_ok=True)
        ste_path, ste_dzis = os.path.join(OUT_DIR, 'stable-emitenci.csv'), NOW.date().isoformat()
        ste_rows = ste_k_csv(ste_path)
        T_ = ste_kontrola(files.get('stable-emitenci'), files.get('cmc'), ste_rows, ste_dzis)
        for label, st, w, txt, note in T_['rows']:
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        R['uwagi'] += T_['uwagi']
        R['zgodnosc']['stable-emitenci'] = {'spojnosc': T_['spojnosc'], 'wiersze': T_['wiersze']} if (T_['rows'] or T_['wiersze']) else None
        if ste_rows.get(ste_dzis):
            ste_k_zapisz(ste_path, ste_rows)
    except Exception as e:  # noqa
        R['zgodnosc']['stable-emitenci'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'emitenci stablecoinów (v363): kontrola przerwana ({str(e)[:80]})')
    # 3c-v362. krzywe rentowności (data/krzywe.json): wiek dnia danych każdej krzywej, spójność i zgodność 10L USA i Niemiec z rynki.json — z plików strony, bez zapytań; najwyżej ⚠
    try:
        T_ = krzywe_kontrola(files.get('krzywe'), files.get('rynki'))
        for label, st, w, txt, note in T_['rows']:
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        R['uwagi'] += T_['uwagi']
        R['zgodnosc']['krzywe'] = {'spojnosc': T_['spojnosc'], 'wiersze': T_['wiersze']} if (T_['rows'] or T_['wiersze']) else None
    except Exception as e:  # noqa
        R['zgodnosc']['krzywe'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'krzywe rentowności (v362): kontrola przerwana ({str(e)[:80]})')
    # 3c-v366. inflacja (BIS) i koniunktura (OECD): wiek najnowszego miesiąca, spójność plików, pokrycie stopy realnej, inflacja USA a CPI-U z usa-makro (tylko informacja) — z plików strony, bez zapytań; najwyżej ⚠
    try:
        T_ = stopy_realne_kontrola(files.get('inflacja'), files.get('koniunktura'), files.get('usa-makro'), files.get('stopy'))
        for label, st, w, txt, note in T_['rows']:
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        R['uwagi'] += T_['uwagi']
        R['zgodnosc']['stopy-realne'] = {'spojnosc': T_['spojnosc'], 'wiersze': T_['wiersze']} if (T_['rows'] or T_['wiersze']) else None
    except Exception as e:  # noqa
        R['zgodnosc']['stopy-realne'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'inflacja i koniunktura (v366): kontrola przerwana ({str(e)[:80]})')
    # 3c-v367. prąd i CO2 (data/prad.json): świeżość trzech części osobnymi wierszami (lista SWIEZOSC bez zmian), sprzeczności w pliku (❌) i progi/porównania (najwyżej ⚠️) — z plików strony, bez zapytań
    try:
        for label, st, w, txt, note in prad_swiezosc(files.get('prad')):
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
            if st == '⚠️':
                R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
            elif st == '?':
                R['uwagi'].append(f'{label}: {note}')
        T_ = prad_kontrola(files)
        if T_:
            for z_ in T_['spojnosc'][:5]:
                R['bledy'].append(f'prad.json: sprzeczność w pliku — {z_}')
            R['uwagi'] += T_['uwagi']
        R['zgodnosc']['prad'] = {k_: T_[k_] for k_ in ('spojnosc', 'wiersze', 'czesci_bez_odpowiedzi')} if T_ else None
    except Exception as e:  # noqa
        R['zgodnosc']['prad'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'prąd i CO2 (v367): kontrola przerwana ({str(e)[:80]})')
    # 3c-v368. stres i niepewność (data/niepewnosc.json): wiek dnia danych CISS, EPU i GPR osobnymi wierszami, spójność z progami z rozkładu historii, CISS USA a indeks stresu (tylko informacja) — z plików strony, bez zapytań; najwyżej ⚠
    try:
        T_ = niepewnosc_kontrola(files.get('niepewnosc'), files.get('stres'))
        for label, st, w, txt, note in T_['rows']:
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        R['uwagi'] += T_['uwagi']
        R['zgodnosc']['niepewnosc'] = {'spojnosc': T_['spojnosc'], 'wiersze': T_['wiersze']} if (T_['rows'] or T_['wiersze']) else None
    except Exception as e:  # noqa
        R['zgodnosc']['niepewnosc'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'stres i niepewność (v368): kontrola przerwana ({str(e)[:80]})')
    # 3c-v372. kalendarz (data/kalendarz.json): świeżość pobrania pięciu części osobnymi wierszami (lista SWIEZOSC bez zmian), terminarz pusty / przeterminowany / parser zgubił tabelę (najwyżej ⚠),
    # sprzeczności w pliku (❌) i data decyzji FOMC a rynek zakładów (⚠) — z plików strony, bez zapytań
    try:
        for label, st, w, txt, note in kalendarz_swiezosc(files.get('kalendarz')):
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
            if st == '⚠\ufe0f':
                R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
            elif st == '?':
                R['uwagi'].append(f'{label}: {note}')
        T_kal = kalendarz_kontrola(files)
        if T_kal:
            for z_ in T_kal['spojnosc'][:5]:
                R['bledy'].append(f'kalendarz.json: sprzeczność w pliku — {z_}')
            R['uwagi'] += T_kal['uwagi']
        R['zgodnosc']['kalendarz'] = {k_: T_kal[k_] for k_ in ('spojnosc', 'wiersze', 'czesci_bez_odpowiedzi')} if T_kal else None
    except Exception as e:  # noqa
        R['zgodnosc']['kalendarz'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'kalendarz (v372): kontrola przerwana ({str(e)[:80]})')
    # 3c-v375. kalendarz 2 (data/kalendarz2.json): świeżość pobrania czterech części osobnymi wierszami, parser (najwyżej ⚠) i sprzeczności w pliku (❌) — z plików strony, bez zapytań
    try:
        for label, st, w, txt, note in kalendarz2_swiezosc(files.get('kalendarz2')):
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
            if st == '⚠️':
                R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
            elif st == '?':
                R['uwagi'].append(f'{label}: {note}')
        T_kal2 = kalendarz2_kontrola(files)
        if T_kal2:
            for z_ in T_kal2['spojnosc'][:5]:
                R['bledy'].append(f'kalendarz2.json: sprzeczność w pliku — {z_}')
            R['uwagi'] += T_kal2['uwagi']
        R['zgodnosc']['kalendarz2'] = {k_: T_kal2[k_] for k_ in ('spojnosc', 'wiersze', 'czesci_bez_odpowiedzi')} if T_kal2 else None
    except Exception as e:  # noqa
        R['zgodnosc']['kalendarz2'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'kalendarz 2 (v375): kontrola przerwana ({str(e)[:80]})')
    # 3d. v115: zgodność liczb — kapitalizacja (mediana 30 dni), ceny BTC/ETH, TGA, wieloryby
    Z = R['zgodnosc']
    today = NOW.date().isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    zg_path = os.path.join(OUT_DIR, 'zgodnosc.csv')
    rows = zgodnosc_csv(zg_path)
    rows.setdefault(today, {})
    gap, d_cmc = None, None
    try:
        cg = get_json(CG_GLOBAL)['data']['total_market_cap']['usd']; cp = get_json(CP_GLOBAL)['market_cap_usd']
        gap = round((float(cp) - float(cg)) / float(cg) * 100.0, 3)
        rows[today]['cap'] = gap
        d_cmc = cmc_roznica(files.get('cmc') if isinstance(files.get('cmc'), dict) else {}, cg, NOW)   # v277: trzecie źródło (plik strony)
    except Exception as e:  # noqa
        Z['kapitalizacja_blad'] = str(e)[:120]; R['uwagi'].append(f'zgodność kapitalizacji: brak odczytu ({str(e)[:80]})')
    st, med, n, opis = kapitalizacja(rows, gap, today)
    if d_cmc is not None and st in ('✅', 'ℹ️'):   # v281 (przegląd v277): norma CMC tylko z dni bez rozbieżności głównej reguły — nie uczy się błędu CoinGecko
        rows[today]['cmc'] = d_cmc
    else:
        rows[today].pop('cmc', None)
    st, opis = kapitalizacja_trzecie(rows, st, opis, d_cmc, today)   # v277: odstaje źródło kontrolne, gdy oba źródła strony zgodne — ℹ️
    Z['kapitalizacja'] = {'status': st, 'dzis_pct': gap, 'mediana_pct': (round(med, 3) if med is not None else None), 'dni': n, 'opis': opis,
                          'cmc_pct': d_cmc}
    if st == '❌':
        R['bledy'].append(f'kapitalizacja krypto: różnica źródeł dziś {gap:.2f}% wobec normy {med:.2f}% — {opis}')
    elif st == '⚠️':
        R['uwagi'].append(f'kapitalizacja krypto: różnica źródeł dziś {gap:.2f}% wobec normy {med:.2f}% — {opis}')
    try:
        p1 = get_json(CG_PRICE); c = {}
        for cid, key in (('btc-bitcoin', 'bitcoin'), ('eth-ethereum', 'ethereum')):
            p2 = get_json(CP_TICKER.format(id=cid))['quotes']['USD']['price']
            r = procent(float(p1[key]['usd']), float(p2))
            c[key] = {'a': float(p1[key]['usd']), 'b': float(p2), 'roznica_pct': (round(r, 3) if r is not None else None)}
            if r is not None and r > CENA_PROG:
                R['uwagi'].append(f'cena {key}: dwa źródła różnią się o {r:.2f}% (próg {CENA_PROG:g}%)')
        Z['ceny'] = c
    except Exception as e:  # noqa
        Z['ceny_blad'] = str(e)[:120]; R['uwagi'].append(f'zgodność cen BTC/ETH: brak odczytu ({str(e)[:80]})')
    Z['tga'] = tga_ocena(rows, files.get('instytucje') or {}, files.get('fred') or {}, today)   # v293 (audyt G2): WDTGAL — próg stały, WTREGEN — mediana
    tz = Z['tga']
    if tz and tz['status'] == '⚠️':
        R['uwagi'].append(f"TGA {tz['data']}: Fiscal Data {_zuz_l(tz['fiscal_mln'])} vs FRED {_zuz_l(tz['fred_mln'])} mln USD — różnica {tz['roznica_pct']:.2f}%"
                          + (f" wobec normy {tz['mediana_pct']:.2f}%" if tz['mediana_pct'] is not None else '') + f" ({tz['opis']})")
    s = stab_porownanie(files.get('krypto'), files.get('cmc'))   # v209: podaż stablecoinów — dwa pliki strony, odchylenie od mediany (najwyżej ⚠️)
    if s:
        if s['roznica_pct'] is not None:
            rows[today]['stab'] = s['roznica_pct']
            st3, med3, n3, opis3 = mediana_ocena(rows, 'stab', s['roznica_pct'], today, STAB_ZOLTE, None)
            s.update(status=st3, mediana_pct=(round(med3, 3) if med3 is not None else None), dni=n3, opis=opis3)
            if st3 == '⚠️':
                R['uwagi'].append(f'podaż stablecoinów: różnica dwóch źródeł dziś {s["roznica_pct"]:+.2f}% wobec normy {med3:+.2f}% ({opis3}) — sprawdzić, czy któreś źródło nie pominęło sieci albo monety')
        Z['stablecoiny'] = s
    if isinstance(files.get('rynki'), dict) and isinstance(files['rynki'].get('ust'), list):   # v209/v211: rentowność 10L USA vs H.15 — wydawca, zapas FRED; brak = informacja
        u, bu = None, []
        for nazwa, url, czytaj in (('Fed', UST_FED, ust_fed_csv), ('FRED', UST_FRED.format(od=(NOW.date() - dt.timedelta(days=UST_OD_DNI)).isoformat()), ust_fred_csv)):
            try:
                st4, body4, _ = get(url, timeout=30)
                F = czytaj(body4.decode('utf-8', 'replace'))
                if not F:
                    raise ValueError('plik bez liczb')
                u = ust_porownanie(files['rynki'], F); u['zrodlo'] = nazwa
                break
            except Exception as e:  # noqa
                bu.append(f'{nazwa}: {str(e)[:80]}')
        if u is not None:
            Z['ust10'] = u
            if u['roznice']:
                R['uwagi'].append('rentowność 10L USA: plik strony vs H.15 różnią się ponad ' + f'{UST_PROG:g} pkt proc.: '
                                  + ', '.join(f'{d}: {a:g} vs {b:g}' for d, a, b, x in u['roznice'][:5]))
        else:
            Z['ust10'] = {'brak': '; '.join(bu)[:200]}
    if isinstance(files.get('stopy'), dict):   # v241–v246: stopy banków centralnych vs ich własne źródła (bez klucza); brak odczytu = informacja
        try:
            Z['stopy'], u = stopy_sprawdz(files['stopy'])
        except Exception as e:  # noqa — v248: błąd bloku stóp nie zabiera całego raportu
            Z['stopy'], u = {'wyniki': [], 'brak': f'błąd kontroli stóp: {type(e).__name__}: {str(e)[:80]}'}, []
        R['uwagi'] += u
    if isinstance(files.get('rynki'), dict) and isinstance(files['rynki'].get('fx'), dict):   # v225: kursy walut vs H.10 (Fed); brak = informacja
        try:
            st5, body5, _ = get(FX_H10, timeout=30)
            H = fx_h10_csv(body5.decode('utf-8', 'replace'))
            if not H:
                raise ValueError('plik bez liczb')
            f = fx_porownanie(files['rynki'], H)
            Z['fx'] = f if f is not None else {'brak': 'brak migawek kursów w pliku strony'}
            R['uwagi'] += fx_uwagi(f)   # v227: przecinki dziesiętne, opis bez „migawki z innego dnia”
        except Exception as e:  # noqa
            Z['fx'] = {'brak': f'H.10: {str(e)[:100]}', 'baza': fx_baza(files['rynki'])}   # v235: ostrzeżenie o walucie bazowej i bez H.10
            R['uwagi'] += fx_uwagi(Z['fx'])
    try:
        zgodnosc_zapisz(zg_path, rows)
    except Exception as e:  # noqa
        R['uwagi'].append(f'zgodnosc.csv: nie zapisano ({str(e)[:80]})')
    Z['indeksy'] = indeksy_ocena((files.get('indeksy') or {}).get('ix'))   # v254: świeżość każdej serii indeksów
    R['uwagi'] += indeksy_uwagi(Z['indeksy'])   # v258: zacięte, z przyszłości, dostawca stoi
    if isinstance((files.get('indeksy') or {}).get('ix'), dict):   # v257/v259: 4 indeksy vs ich wydawcy (serie wydawców z pliku); brak = informacja
        try:
            Z['ix_fred'] = ixf_sprawdz(files['indeksy']['ix'], files['indeksy'].get('wyd'))
        except Exception as e:  # noqa — błąd bloku nie zabiera całego raportu
            Z['ix_fred'] = {'brak': f'błąd porównania indeksów: {type(e).__name__}: {str(e)[:80]}'}
        R['uwagi'] += ixf_uwagi(Z['ix_fred'])
    e = etf_porownanie(files.get('ceny') or {}, files.get('indeksy') or {})
    if e:
        zle = [x for x in e if x[4] is not None and x[4] > ETF_PROG]
        Z['etf'] = {'porownane': len(e), 'roznice': [{'symbol': s, 'data': d, 'a': a, 'b': b, 'roznica_pct': round(r, 3)} for s, d, a, b, r in zle]}
        if zle:
            R['uwagi'].append('ETF (mapa): zamknięcia z dwóch źródeł różnią się > ' + f'{ETF_PROG:g}% dla ' + ', '.join(f'{s} ({d}: {a:g} vs {b:g})' for s, d, a, b, r in zle[:6]))
    else:
        Z['etf'] = None
    w = wieloryby_ocena(os.path.join(ARCH_DIR, 'wieloryby.csv'), zmiany=wh_zmiany(files.get('wieloryby')),
                        hist=(files.get('wieloryby') or {}).get('hist'))   # v249: salda z migawek o północy UTC   # v230: dzień zmiany listy; v174: na tle historii pary i tylko przy migawkach oddalonych o ok. dobę
    if w:
        zle = w['zle']
        Z['wieloryby'] = {'dzien': w['dzien'], 'poprzedni': w['poprzedni'], 'porownane': w['porownane'], 'odstep_h': w['odstep_h'], 'pomin': w['pomin'],
                          'bez_historii': w['bez_historii'], 'pominiete': w.get('pominiete', 0), 'lista': w.get('lista', []), 'polnoc': w.get('polnoc', 0), 'poprzedni_pokaz': w.get('poprzedni_pokaz'),
                          'rozbieznosci': [{'gielda': g, 'aktywo': a, 'zmiana_usd': round(x, 2), 'netto_usd': round(y, 2), 'roznica_usd': round(z, 2), 'mediana_usd': round(m, 2)}
                                           for g, a, x, y, z, m in zle]}
        if zle:
            R['uwagi'].append('wieloryby: zmiana salda ≠ przelewy netto — rozbieżność nietypowa (ponad ' + f'{WH_RAZY:g}× zwykłej dla pary) dla '
                              + ', '.join(f'{g} {a} ({z / 1e6:.0f} mln USD, zwykle {m / 1e6:.0f} mln)' for g, a, x, y, z, m in zle[:6])
                              + ' — sprawdzić skan przelewów tej giełdy')
    else:
        Z['wieloryby'] = None
    wl = wh_listy_ocena(files.get('wieloryby'))   # v218: wiek list portfeli giełd z raportów miesięcznych
    if wl is not None:
        Z['wh_listy'] = wl
        for g, d, n in wl['stare']:
            R['uwagi'].append(f'lista portfeli giełdy {g} z {d} ma {n} dni — portfele dodane przez giełdę od tego czasu nie są liczone; '
                              f'co zrobić: napisz do Claude „odśwież listę portfeli {g} z nowego raportu dowodu rezerw”')
        try:   # v237: nowe raporty dowodu rezerw — automat sam wie, kiedy listę można odświeżyć
            Z['wh_nowe'] = wh_nowe_raporty((files.get('wieloryby') or {}).get('gieldy'))
        except Exception as e:  # noqa
            Z['wh_nowe'] = {'_blad': type(e).__name__}   # v243: wiersz „nie wiadomo”, nie zniknięcie
        for g, o in Z['wh_nowe'].items():
            if isinstance(o, dict) and o.get('nowy') and o.get('lista'):
                R['uwagi'].append(f'nowa lista portfeli giełdy {g} z {o["nowy"]} (raport dowodu rezerw; obecna z {o["od"]}) — co zrobić: napisz do '
                                  f'Claude „odśwież listę portfeli {g} z nowego raportu dowodu rezerw”')
    # 3e. v130: ETF krypto u źródła — przepływy IBIT i ETHA na stronie vs wyliczenie z plików emitenta (2 zapytania, bez ponawiania; najwyżej ⚠️)
    try:
        Z['etf_emitent'] = etf_emitent(files, R)
    except Exception as e:  # noqa
        Z['etf_emitent'] = {'status': '?', 'blad': str(e)[:120], 'fundusze': {}}
        R['uwagi'].append(f'ETF u źródła (pliki emitenta): kontrola przerwana ({str(e)[:80]})')
    # 3e'. v355: druga, niezależna kontrola przepływów ETF bitcoina — plik emitenta ARKB (1 zapytanie, bez ponawiania; najwyżej ⚠️; bez nowej liczby na stronie)
    try:
        Z['arkb'] = arkb_kontrola(files, R)
    except Exception as e:  # noqa
        Z['arkb'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'ARKB (druga kontrola przepływów ETF bitcoina): kontrola przerwana ({str(e)[:80]})')
    # 3e. v128: zgodność premii krypto (bez sieci: plik premie i wczytany rynki) — tylko uwagi, nigdy błąd (dziwny rynek to nie awaria strony)
    Z['premie'] = premie_porownanie(files.get('premie'), files.get('rynki'))
    R['uwagi'] += Z['premie']['uwagi']
    # 3f. v136: Argentyna — dwa odczyty tych samych kursów (plik dolar.json) i kurs hurtowy vs bank centralny (1 zapytanie); najwyżej ⚠️ (nigdy ❌
    # ani BŁĄD): kurs z nieoficjalnego serwisu to nie awaria strony
    try:
        Z['dolar'] = dolar_kontrola(files.get('dolar'), R)
    except Exception as e:  # noqa
        Z['dolar'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'kursy dolara (Argentyna): kontrola przerwana ({str(e)[:80]})')
    # 3g. v134: fundusze USA — tożsamości sum ostatniego tygodnia w pliku strony (bez sieci) i informacja o poprawkach wydawcy; najwyżej ⚠️
    try:
        Z['ici'] = ici_kontrola(files.get('ici'), R)
    except Exception as e:  # noqa
        Z['ici'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'fundusze USA: kontrola sum przerwana ({str(e)[:80]})')
    # 3g. v137: Japonia — zagranica w akcjach: giełda (tylko handel na giełdzie) vs MOF (wszystkie akcje i fundusze) — kierunek i korelacja
    # z plików strony, bez zapytań; najwyżej ⚠️ (różne miary, nigdy ❌ ani BŁĄD)
    try:
        Z['jpx'] = jpx_kontrola(files, R)
    except Exception as e:  # noqa
        Z['jpx'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'Japonia — giełda vs MOF: kontrola przerwana ({str(e)[:80]})')
    # 3g. v295: surowce — sprzeczności w pliku (❌) i porównania z progami z testów wstecznych (najwyżej ⚠️), z pliku strony, bez zapytań
    try:
        Z['surowce'] = surowce_kontrola(files.get('surowce'), R)
    except Exception as e:  # noqa
        Z['surowce'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'surowce: kontrola przerwana ({str(e)[:80]})')
    # 3g. v305: szlaki handlowe — sprzeczności w pliku (❌) i progi z testów wstecznych (najwyżej ⚠️), z pliku strony, bez zapytań
    try:
        Z['szlaki'] = szlaki_kontrola(files.get('szlaki'), R)
    except Exception as e:  # noqa
        Z['szlaki'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'szlaki: kontrola przerwana ({str(e)[:80]})')
    # 3g. v339: metale przemysłowe — sprzeczności w pliku (❌) i porównania (raport tygodniowy o miedzi vs dane giełd, kwity, średnie miesięczne vs
    # Bank Światowy; najwyżej ⚠️), z plików strony, bez zapytań
    try:
        Z['metale'] = metale_kontrola(files, R)
    except Exception as e:  # noqa
        Z['metale'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'metale: kontrola przerwana ({str(e)[:80]})')
    # 3g. v340: gaz i LNG — sprzeczności w pliku (❌) i progi z testów wstecznych (najwyżej ⚠️), z pliku strony, bez zapytań
    try:
        Z['lng'] = lng_kontrola(files.get('lng'), R)
    except Exception as e:  # noqa
        Z['lng'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'gaz i LNG: kontrola przerwana ({str(e)[:80]})')
    # 3g. v353: Rosja — sprzeczności w pliku (❌), porównania handlu UE z danymi zgłoszonymi przez Rosję, cena uncji z rezerw i kopia złota (najwyżej ⚠️), z plików strony, bez zapytań
    try:
        Z['rosja'] = rosja_kontrola(files, R)
    except Exception as e:  # noqa
        Z['rosja'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'Rosja: kontrola przerwana ({str(e)[:80]})')
    # 3g. v361 (F3Z2): Polska na rynku dziennie — sprzeczności w pliku (❌), WIG20 z giełdy a z drugiego dostawcy, skoki indeksów i rentowności, różnica do Niemiec (najwyżej ⚠️), z plików strony, bez zapytań
    try:
        Z['polska-rynek'] = polska_rynek_kontrola(files, R)
    except Exception as e:  # noqa
        Z['polska-rynek'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'Polska na rynku: kontrola przerwana ({str(e)[:80]})')
    # 3g. v365 (F3Z3): Polska — kapitał z zagranicy i wypłaty UE — sprzeczności w pliku (❌), porównanie kwartalnego świata z plikiem miesięcznym (najwyżej ⚠️), z plików strony, bez zapytań
    try:
        Z['polska-kapital'] = polska_kapital_kontrola(files, R)
    except Exception as e:  # noqa
        Z['polska-kapital'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'Polska kapitał: kontrola przerwana ({str(e)[:80]})')
    # 3g. v371 (F3Z1): Polska — kto trzyma dług skarbowy i sprzedaż obligacji detalicznych — sprzeczności w pliku (❌), porównanie zagranicy z plikiem nierezydentów (najwyżej ⚠️), z plików strony, bez zapytań
    try:
        Z['polska-dlug'] = polska_dlug_kontrola(files, R)
    except Exception as e:  # noqa
        Z['polska-dlug'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'Polska dług: kontrola przerwana ({str(e)[:80]})')
    # 3g. v341 (F5Z3): zboża dziennie i koszt transportu — sprzeczności w pliku (❌), skoki, korelacje zmian miesięcznych z innymi danymi i tabela źródła (najwyżej ⚠️), z plików strony, bez zapytań
    try:
        Z['zboza-dzien'] = zboza_kontrola(files.get('zboza-dzien'), files, R)
    except Exception as e:  # noqa
        Z['zboza-dzien'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'zboża dziennie: kontrola przerwana ({str(e)[:80]})')
    # 3g. v349 (F6Z1): giełdy scentralizowane i DEX — sprzeczności w plikach (❌) i informacje (ℹ️; progi bez testu wstecznego), z plików strony, bez zapytań
    try:
        Z['gieldy-dex'] = gx_kontrola(files, R)
    except Exception as e:  # noqa
        Z['gieldy-dex'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'giełdy i DEX: kontrola przerwana ({str(e)[:80]})')
    # 3g. v320: raporty miesięczne o surowcach — sprzeczności w pliku (❌) i porównania (uran z funduszu vs średnia branżowa — ℹ️), z plików strony, bez zapytań
    try:
        Z['surowce-raporty'] = surowce_raporty_kontrola(files, R)
    except Exception as e:  # noqa
        Z['surowce-raporty'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'surowce (raporty): kontrola przerwana ({str(e)[:80]})')
    # 3g. v320: pozycje funduszy USA — plik tygodniowy (surowce.json) vs ten sam raport w drugim kanale urzędu (jedno zapytanie bez klucza); różnica = ⚠️
    try:
        Z['surowce-cftc'] = surowce_cftc_kontrola(files.get('surowce'), R)
    except Exception as e:  # noqa
        Z['surowce-cftc'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'surowce (pozycje, drugi kanał): kontrola przerwana ({str(e)[:80]})')
    # 3g. v304: Polska — sprzeczności w pliku (❌) i złoto w zł/g wobec ceny w USD × kurs USD/PLN (najwyżej ⚠️), z plików strony, bez zapytań
    try:
        Z['polska'] = polska_kontrola(files, R)
    except Exception as e:  # noqa
        Z['polska'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'Polska: kontrola przerwana ({str(e)[:80]})')
    # 3g. v295c: złoto i surowce a krypto — wiek stałej zasobów wydobytego złota (z pliku strony, bez zapytań; najwyżej ⚠️)
    try:
        Z['zloto-krypto'] = zk_kontrola(files.get('zloto-krypto'), R)
    except Exception as e:  # noqa
        Z['zloto-krypto'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'złoto i surowce a krypto: kontrola przerwana ({str(e)[:80]})')
    # 3g. v133: tokenizowane aktywa RWA — własna zmiana 7 dni vs zmiana podana przez źródło, produkty spoza głównej listy, skok sumy dzień do dnia
    # (z pliku strony, bez zapytań; najwyżej ⚠️ — do raportu bez nowej kolumny zgodnosc.csv)
    try:
        Z['rwa'] = rwa_kontrola(files, R)
    except Exception as e:  # noqa
        Z['rwa'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'tokenizowane aktywa: kontrola przerwana ({str(e)[:80]})')
    # 3h. v150: odczyt własny z łańcucha — podaż 24 h, wartość vs ostatnio znana, produkty bez pełnego odczytu (z pliku strony, bez zapytań; najwyżej ⚠️)
    try:
        Z['rwa-lancuch'] = rwc_kontrola(files, R)
    except Exception as e:  # noqa
        Z['rwa-lancuch'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'tokenizowane aktywa (odczyt własny): kontrola przerwana ({str(e)[:80]})')
    # 3i. v169: dane emitentów — produkty w sumach, braki, inny zakres, produkty, które wypadły (z pliku strony, bez zapytań; najwyżej ⚠️)
    try:
        Z['rwa-emitenci'] = rwe_kontrola(files, R)
    except Exception as e:  # noqa
        Z['rwa-emitenci'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'tokenizowane aktywa (dane emitentów): kontrola przerwana ({str(e)[:80]})')
    # 4. przebiegi Actions z ostatnich 24 h (API publiczne; token tylko podnosi limit zapytań)
    try:
        hdr = {'Accept': 'application/vnd.github+json'}
        if TOKEN:
            hdr['Authorization'] = 'Bearer ' + TOKEN
        runs, ids, druga = [], set(), None
        for strona in (1, 2):   # v177: lista samego zadania „Strona i dane” (inne zadania — zegar, kontrola — wypychały je z listy 100 po ok. 8–10 h);
            try:
                st, body, ms = get(f'https://api.github.com/repos/{REPO}/actions/workflows/strona.yml/runs?per_page=100&page={strona}', headers=hdr)
                Rr = json.loads(body).get('workflow_runs', []) or []
            except Exception as e:  # noqa — v181: nieczytelna DRUGA strona nie kasuje pierwszej (liczba z pierwszej, dopisek w raporcie)
                if strona == 1:
                    raise
                druga = str(e)[:80] or type(e).__name__; break
            runs += [r for r in Rr if not (isinstance(r, dict) and r.get('id') in ids)]   # druga strona tylko, gdy 100 przebiegów nie pokrywa doby;
            ids.update(r.get('id') for r in Rr if isinstance(r, dict))                  # v181: bez podwójnych (nowy przebieg między stronami przesuwa listę)
            w = wiek_min(Rr[-1].get('run_started_at') or Rr[-1].get('created_at')) if Rr else None
            if len(Rr) < 100 or w is None or w > 24 * 60:
                break
        # v124.1: nazwa nieudanego kroku dla najwyżej 5 porażek z 24 h (1 zapytanie na porażkę; błąd odczytu = sama godzina)
        kroki = {}
        for r in [r for r in runs if str(r.get('name', '')).startswith('Strona') and r.get('conclusion') == 'failure'
                  and wiek_min(r.get('run_started_at')) is not None and wiek_min(r.get('run_started_at')) <= 24 * 60][:5]:
            try:
                _, b2, _ = get(f'https://api.github.com/repos/{REPO}/actions/runs/{r["id"]}/jobs', headers=hdr)
                for j in json.loads(b2).get('jobs', []):
                    if j.get('conclusion') == 'failure':
                        kroki[r['id']] = opis_kroku(j.get('name'), next((s.get('name') for s in j.get('steps') or [] if s.get('conclusion') == 'failure'), None))
                        break
            except Exception:  # noqa
                pass
        pend = {}   # v235: oczekujące wdrożenia przebiegów „waiting” (najwyżej 3 zapytania; błąd odczytu = jak dotąd, bez rozróżnienia)
        for r in [r for r in runs if isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and r.get('status') == 'waiting'][:3]:
            try:
                _, b4, _ = get(f'https://api.github.com/repos/{REPO}/actions/runs/{r["id"]}/pending_deployments', headers=hdr)
                pend[r['id']] = json.loads(b4)
            except Exception:  # noqa
                pass
        R['actions'], b, u = przebiegi_ocena(runs, NOW, kroki, pend)
        # v194 (przegląd v190–v192): czas samego zadania budowy (limit 25 min) w 3 najdłuższych udanych przebiegach — całość przebiegu zawiera
        # czekanie na maszyny (w awarii GitHuba fałszywe „blisko limitu”); 3 dodatkowe zapytania, błąd odczytu = bez tej liczby
        bud, t_b = [], time.monotonic()
        dl_b = {r.get('id'): przebieg_min(r) for r in runs if isinstance(r, dict)}
        for rid in budowa_kandydaci(runs, NOW):   # v199: także każdy udany > 20 min; v205: koniec, gdy dłuższej budowy już nie będzie, albo po 90 s
            if bud and (dl_b.get(rid) or 0) <= max(bud):
                break                                    # budowa ≤ cały przebieg, kandydaci malejąco — kolejne nie dadzą dłuższej budowy
            if time.monotonic() - t_b > BUDOWA_BUDZET_S:
                R['actions']['budowa_niepelna'] = True; break
            try:
                _, b3, _ = get(f'https://api.github.com/repos/{REPO}/actions/runs/{rid}/jobs', headers=hdr)
                m3 = zadanie_min(json.loads(b3).get('jobs', []), 'zbuduj')
                if m3 is not None:
                    bud.append(m3)
            except Exception:  # noqa
                pass
        if bud:
            R['actions']['budowa_max_min'] = round(max(bud), 1)
        if druga:
            R['actions']['lista_niepelna'] = druga
        R['bledy'] += b
        R['uwagi'] += u
    except Exception as e:  # noqa
        R['actions'] = {'blad': str(e)[:160]}
        R['uwagi'].append('nie udało się odczytać listy przebiegów Actions: ' + str(e)[:100])
    # 4b. v291: ostrzeżenia GitHuba o przestarzałych akcjach i systemie w ostatnim zakończonym przebiegu każdego przepływu (07.10 „Node.js 20
    # is deprecated…” znalezione przypadkiem w adnotacji sondy); tylko uwaga, błąd odczytu = „?” bez uwagi
    try:
        hdr = {'Accept': 'application/vnd.github+json'}
        if TOKEN:
            hdr['Authorization'] = 'Bearer ' + TOKEN
        R['github_ostrz'] = github_ostrz_odczyt(hdr)   # v292: każdy przepływ osobno (błąd jednego nie przerywa pozostałych)
        zn = R['github_ostrz']['znalezione']
        if zn:
            R['uwagi'].append('GitHub ostrzega o przestarzałych akcjach albo systemie (' + '; '.join(f'{w}: {m[:90]}' for w, m in zn[:3])
                              + ') — napisz do Claude: „zaktualizuj akcje GitHuba”')
    except Exception as e:  # noqa
        R['github_ostrz'] = {'blad': str(e)[:120]}
    # 4c. v354: strażnik harmonogramów — przepływy z harmonogramem czynne (GitHub wyłącza je po 60 dniach bez aktywności), ostatni przebieg strażnika (raz w tygodniu),
    # wiek ostatniego commitu; tylko uwaga, nigdy BŁĄD; błąd odczytu = „?” bez uwagi
    try:
        hdr = {'Accept': 'application/vnd.github+json'}
        if TOKEN:
            hdr['Authorization'] = 'Bearer ' + TOKEN
        R['straznik'] = straznik_odczyt(hdr, NOW)
        R['uwagi'] += ['strażnik harmonogramów: ' + x for x in R['straznik']['uwagi']]
    except Exception as e:  # noqa
        R['straznik'] = {'blad': str(e)[:120] or type(e).__name__}
    # 5. v115: historia — błędy zbieracza w 3 kolejnych przebiegach kontroli = czerwone
    if _TERMIN['przekroczony']:   # v327 (KON-04): po terminie całej kontroli część zapytań nie wyszła — raport częściowy
        R['bledy'].append(kontrola_przerwana_opis(KoniecCzasu()))
    n_err = len(R['meta'].get('errors') or []) if isinstance(R['meta'], dict) else 0
    hist = historia(os.path.join(OUT_DIR, 'historia.json'), {'at': R['at'], 'bledy_zbieracza': n_err, 'uwagi': len(R['uwagi']), 'bledy': len(R['bledy']),
                                                           'przegl': (R.get('przegladarka') or {}).get('stan')})   # v248: stan przeglądarki
    if czerwone_z_historii(hist):
        R['bledy'].append(f'zbieracz zgłasza błędy w {HIST_CZERWONE} kolejnych dniach kontroli (' + '; '.join((R['meta'].get('errors') or ['?'])[:2]) + ')')
    R['historia_n'] = len(hist)
    R['wynik'] = 'BŁĄD' if R['bledy'] else ('UWAGA' if R['uwagi'] else 'OK')
    return R


def raport_md(R):
    m = R.get('meta') or {}
    werdykt = ('✅ Wszystko w normie.' if R['wynik'] == 'OK' else
               f'⚠️ Uwag: {len(R["uwagi"])} — nic nie wymaga natychmiastowej reakcji.' if R['wynik'] == 'UWAGA' else
               f'❌ Błędów: {len(R["bledy"])} — wymagają uwagi (szczegóły niżej).')
    L = [f'# Kontrola strony — {czas_pl(R["at"])} (czas polski)', '',
         f'**Wynik: {R["wynik"]}**', '', werdykt, '',
         f'- Strona główna: {"działa" if (R.get("strona") or {}).get("ok") else "PROBLEM"} (HTTP {(R.get("strona") or {}).get("http", "—")}, {(R.get("strona") or {}).get("ms", "—")} ms).',
         f'- Ostatni przebieg automatu: {czas_pl(m.get("at"))} — {("sprzed " + str(m.get("wiek_min")) + " min") if m.get("wiek_min") is not None else "brak"}; '
         f'źródeł: {m.get("zrodla", "—")}, bez odpowiedzi: {", ".join(m.get("bez_odpowiedzi") or []) or "żadne"}; błędów zbieracza: {len(m.get("errors") or [])}.']
    if R['wynik'] == 'BŁĄD' and R.get('bledy'):   # v212: zaraz pod werdyktem — co zrobić przy każdym rodzaju błędu (nagłówek i „Wynik:” bez zmian)
        L[6:6] = ['**Co zrobić:**'] + ['- ' + h for h in co_zrobic(R['bledy'])] + ['']
    cz = m.get('czas') if isinstance(m.get('czas'), dict) else None   # v185: czas tego przebiegu i najdłuższe części
    if cz and isinstance(cz.get('s'), (int, float)):
        top = [x for x in (cz.get('top') or []) if isinstance(x, list) and len(x) == 2][:3]
        L.append(f'- Czas tego przebiegu automatu: {int(cz["s"]) // 60} min {int(cz["s"]) % 60} s'
                 + ('; najdłużej: ' + ', '.join(f'{n} {s} s' for n, s in top) if top else '') + '.')
    s18 = (R.get('strona') or {}).get('i18n')   # v141: lżejsza strona — pliki słowników języków
    if s18:
        L.append('- Słowniki języków de–ja (osobne pliki strony): ' + s18.get('opis', '—') + '.')
    pg = R.get('przegladarka')   # v247: strona w przeglądarce bez okna
    if isinstance(pg, dict):
        L.append(przegladarka_wiersz(pg))
    pl = R.get('przegladarka_lekka')   # v308: runda bez ?pelna=1 (jak u czytelnika)
    if isinstance(pl, dict):
        L.append(przegladarka_wiersz_lekka(pl))
    a = R.get('actions') or {}
    if 'przebiegi_24h' in a:
        L.append(f'- Przebiegi Actions w 24 h: {a["przebiegi_24h"]} ({", ".join(f"{k}: {v}" for k, v in a["wg_wyniku"].items()) or "—"}).'
                 + (' Uwaga: lista niepełna — druga strona listy nieczytelna, liczba z pierwszych 100.' if a.get('lista_niepelna') else ''))
        if isinstance(a.get('najdluzszy_min'), (int, float)):   # v190: zapas do limitu zadania budowy (25 min)
            nd, bm = a['najdluzszy_min'], a.get('budowa_max_min')
            if isinstance(bm, (int, float)) and not isinstance(bm, bool):   # v194: ostrzeżenie z czasu samego zadania budowy (bez czekania na maszyny)
                L.append(f'- Najdłuższy udany przebieg w 24 h: {nd:.1f} min'.replace('.', ',') + ' (od startu do końca, z czekaniem na maszyny); samo zadanie budowy najdłużej '
                         + f'{bm:.1f} min'.replace('.', ',') + ' z limitu 25 min' + (' ⚠️ blisko limitu.' if bm > 20 else '.'))
            else:
                L.append(f'- Najdłuższy udany przebieg w 24 h: {nd:.1f} min'.replace('.', ',') + ' (od startu do końca, z czekaniem na maszyny; limit zadania budowy 25 min)'
                         + (' ⚠️ blisko limitu.' if nd > 20 else '.'))
        if a.get('porazki'):   # v124.1: każda porażka z godziną i krokiem; czy automat już działa
            L.append('- Nieudane przebiegi (24 h): ' + '; '.join(czas_pl(p['at']) + (f' — {p["krok"]}' if p.get('krok') else '') for p in a['porazki'])
                     + (f'. Od ostatniej porażki {pl_udane(a["udane_po_porazce"])} z rzędu.' if a.get('udane_po_porazce') else '. Ostatni zakończony przebieg nieudany.'))
    sz = R.get('straznik') if isinstance(R.get('straznik'), dict) else None   # v354: strażnik harmonogramów
    if sz is not None:
        L.append(straznik_wiersz(sz))
    go = R.get('github_ostrz') if isinstance(R.get('github_ostrz'), dict) else None   # v291: ostrzeżenia GitHuba o przestarzałych akcjach
    if go is not None:
        if go.get('blad'):
            L.append(f'- Ostrzeżenia GitHuba o przestarzałych akcjach: ? (odczyt przerwany: {go["blad"][:60]}).')
        elif go.get('znalezione'):
            L.append('- Ostrzeżenia GitHuba o przestarzałych akcjach: ' + '; '.join(f'{w}: {m[:90]}' for w, m in go['znalezione'][:3])
                     + ' ⚠️ — napisz do Claude: „zaktualizuj akcje GitHuba”.')
        else:
            L.append(f'- Ostrzeżenia GitHuba o przestarzałych akcjach (ostatni przebieg każdego z {go.get("sprawdzone", 0)} przepływów): brak ✅'
                     + (f'; nie odczytano: {", ".join(go["bledne"])[:120]}.' if go.get('bledne') else '.'))
    L.append('- Pliki danych (wiek): ' + ', '.join(f'{n} {("%dh%02d" % divmod(p["wiek_min"], 60)) if p.get("wiek_min") is not None and not p.get("wylaczone") else ("wyłączone" if p.get("wylaczone") else "pominięty" if p.get("pominiete") else "HTTP " + str(p.get("http", "?")))}'
                                             for n, p in (R.get('pliki') or {}).items()) + '.')
    aw = R.get('awarie') if isinstance(R.get('awarie'), dict) else None   # v207: pamięć awarii części automatu
    if aw is not None:
        if not aw.get('trwa') and not aw.get('naprawione') and not aw.get('zniknely'):
            ao, ra = _aw_t(m.get('awarie_od')), _aw_t(R.get('at'))   # v211: „brak” tylko za ostatnią dobę; pamięć młodsza niż doba — od kiedy
            L.append('- Awarie części automatu (24 h): brak' + (f' (pamięć od {czas_pl(m["awarie_od"])})' if ao and ra and (ra - ao).total_seconds() < AW_INFO_H * 3600 else '') + '.')
        if aw.get('trwa'):
            L.append('- Awarie części automatu — trwają: ' + '; '.join(
                f'{x["czesc"]} od {czas_pl(x["od"])} ({_aw_h(x["h"])}, nieudanych przebiegów: {x["n"]}) '
                + ('ℹ️ (' + AW_BEZ_BLEDU.get(x['czesc'], '') + ')' if x.get('bez') else '❌' if x['h'] >= AW_BLAD_H else '⚠️' if x['h'] >= AW_UWAGA_H else 'ℹ️')
                for x in aw['trwa']) + '.')
        if aw.get('naprawione'):
            L.append('- Naprawiły się same (24 h): ' + '; '.join(
                f'{x["czesc"]} {czas_pl(x["od"])} – {czas_pl(x["do"])} ({_aw_h(x["h"])}, nieudanych przebiegów: {x["n"]}) ℹ️' for x in aw['naprawione']) + '.')
        if aw.get('zniknely'):   # v211: seria zamknięta, bo część nie pojawia się w przebiegach (wyłączona albo zmieniona) — nie awaria, nie naprawa
            L.append('- Zniknęły z przebiegów (24 h; część wyłączona albo zmieniona — nie awaria): ' + '; '.join(
                f'{x["czesc"]} — ostatnia nieudana próba {czas_pl(x["ost"])} (nieudanych przebiegów: {x["n"]}) ℹ️' for x in aw['zniknely']) + '.')
    zu = R.get('zuzycie') if isinstance(R.get('zuzycie'), dict) else None   # v222: zużycie darmowych planów z limitem
    if zu and zu.get('plany'):
        L.append('- Zużycie darmowych planów (licznik automatu — dolna granica): ' + '; '.join(f'{p["tekst"]} {p["znak"]}' for p in zu['plany']) + '.')
    if m.get('notes'):
        L.append('- Notatki automatu: ' + ' · '.join(m['notes']) + '.')
    if R.get('swiezosc'):
        L += ['', '## Świeżość źródeł', '', '| Źródło | Status | Wiek danych | Data danych | Uwaga |', '|---|---|---|---|---|']
        for s in R['swiezosc']:
            L.append(f'| {s["zrodlo"]} | {s["status"]} | {fmt_wiek(s["wiek_min"])} | {s["data"] or "—"} | {s["uwaga"] or "—"} |')
    Z = R.get('zgodnosc') or {}
    if Z:
        L += ['', '## Zgodność liczb (porównania krzyżowe)', '']
        k = Z.get('kapitalizacja') or {}
        if k:
            dz = f'{k["dzis_pct"]:.2f}%' if k.get('dzis_pct') is not None else '—'
            L.append(f'- Kapitalizacja krypto, dwa źródła: różnica dziś {dz}{_norma(k.get("mediana_pct"), k.get("dni", 0))} — {k.get("status", "?")} {k.get("opis", "")}.')
        c = Z.get('ceny') or {}
        for key, nm in (('bitcoin', 'BTC'), ('ethereum', 'ETH')):
            if key in c:
                r = c[key].get('roznica_pct')
                L.append(f'- Cena {nm}: {_zuz_l(c[key]["a"])} vs {_zuz_l(c[key]["b"])} USD — różnica {r:.2f}% {"⚠️" if r > CENA_PROG else "✅"}.' if r is not None else f'- Cena {nm}: brak porównania.')
        t = Z.get('tga')
        if t:
            r = t.get('roznica_pct')
            L.append(f'- TGA {t["data"]}: Fiscal Data {_zuz_l(t["fiscal_mln"])} vs FRED {_zuz_l(t["fred_mln"])} mln USD — różnica {r:.2f}%{_norma(t.get("mediana_pct"), t.get("dni", 0))} — {t.get("status", "?")} {t.get("opis", "")}.'
                     if r is not None else f'- TGA {t["data"]}: brak porównania.')
        else:
            L.append('- TGA: brak wspólnej daty Fiscal Data i FRED.')
        s = Z.get('stablecoiny')   # v209
        if s:
            if s.get('roznica_pct') is None:
                L.append(f'- Podaż stablecoinów, dwa źródła: pliki pobrane w odstępie {s["odstep_h"]} h — bez porównania ℹ️.' if s.get('odstep_h') is not None
                         else '- Podaż stablecoinów, dwa źródła: brak czasu pobrania jednego z plików — bez porównania ℹ️.')   # v327 (KON-06): bez „None h”
            else:
                L.append(f'- Podaż stablecoinów, dwa źródła: {s["a"] / 1e9:.1f} vs {s["b"] / 1e9:.1f} mld USD — różnica dziś {s["roznica_pct"]:+.2f}%'
                         f'{_norma(s.get("mediana_pct"), s.get("dni", 0), "{:+.2f}%")} — {s.get("status", "?")} {s.get("opis", "")}.')
        u = Z.get('ust10')   # v209
        if u:
            if u.get('brak'):
                L.append(f'- Rentowność 10L USA (Skarb USA vs H.15): brak odczytu H.15 ({u["brak"]}) ℹ️.')
            elif not u.get('porownane'):
                L.append('- Rentowność 10L USA (Skarb USA vs H.15): brak wspólnych dat ℹ️.')
            else:
                L.append(f'- Rentowność 10L USA (Skarb USA vs H.15{" — " + u["zrodlo"] if u.get("zrodlo") else ""}, te same dni): porównane {u["porownane"]} dat (do {u["do"]}), różnice > {UST_PROG:g} pkt proc.: '
                         f'{len(u["roznice"])} ' + ('⚠️ — ' + ', '.join(f'{d}: {a:g} vs {b:g}' for d, a, b, x in u['roznice'][:5]) + '.' if u['roznice'] else '✅.'))
        sp = Z.get('stopy')   # v241
        if sp:
            try:
                L.append(stopy_wiersz(sp))
            except Exception as e:  # noqa — v248
                L.append(f'- Stopy banków centralnych: błąd wiersza raportu ({type(e).__name__}) ℹ️.')
        f = Z.get('fx')   # v225: kursy walut vs H.10
        if f:
            if f.get('brak'):
                L.append(f'- Kursy walut (plik strony vs H.10 Fed): brak porównania ({f["brak"]}) ℹ️'
                         + ('; migawki z walutą bazową inną niż USD: ' + ', '.join(f'{k} ({b})' for k, b in f['baza']) + ' ⚠️.' if f.get('baza') else '.'))   # v235
            elif not f.get('daty') and f.get('baza'):   # v233: same migawki z inną bazą — ⚠️ z powodem (dotąd „brak wspólnych dat”)
                L.append('- Kursy walut (plik strony vs H.10 Fed): migawki z walutą bazową inną niż USD ('
                         + ', '.join(f'{k} ({b})' for k, b in f['baza']) + ') — bez porównania ⚠️.')
            elif not f.get('daty'):
                L.append('- Kursy walut (plik strony vs H.10 Fed): brak wspólnych dat (H.10 wychodzi raz w tygodniu) ℹ️.')
            else:
                L.append('- Kursy walut (strona: kurs EBC; H.10: Fed, Nowy Jork; te same dni): ' + '; '.join(
                    f'{d} — {n} walut, mediana różnicy {m:.2f}%, najwięcej {c} {x:+.2f}%'.replace('.', ',') for d, n, m, c, x in f['daty'])
                    + ('; migawki z inną walutą bazową: ' + ', '.join(f'{k} ({b})' for k, b in f['baza']) if f.get('baza') else '')   # v233
                    + (' ⚠️.' if f['zle'] or f['med_zle'] or f.get('baza') else ' ✅.'))
        L.append(indeksy_wiersz(Z.get('indeksy')))   # v254
        w = ixf_wiersz(Z.get('ix_fred'))   # v257
        if w:
            L.append(w)
        e = Z.get('etf')
        if e:
            L.append(f'- ETF mapy (dwa źródła, ta sama data): porównane {e["porownane"]} symboli, różnice > {ETF_PROG:g}%: {len(e["roznice"])} {"⚠️" if e["roznice"] else "✅"}' + (' — ' + ', '.join(x["symbol"] for x in e["roznice"][:6]) if e["roznice"] else '') + '.')
        else:
            L.append('- ETF mapy: brak wspólnej daty zamknięć w dwóch źródłach.')
        w = Z.get('wieloryby')
        if w and w.get('pomin'):   # v174: migawki nie o dobę — bez porównania (informacja)
            L.append(f'- Wieloryby {w["dzien"]} vs {w.get("poprzedni_pokaz") or w["poprzedni"]}: {w["pomin"]} ℹ️.')
        elif w:
            L.append(f'- Wieloryby {w["dzien"]} vs {w.get("poprzedni_pokaz") or w["poprzedni"]}: {w["porownane"]} par giełda/aktywo'   # v250
                     + (f' (salda z migawek o północy UTC: {w["polnoc"]})' if w.get('polnoc') else '')   # v249
                     + f', rozbieżności nietypowe (> 5% i > {WH_RAZY:g}× zwykłej): '
                     f'{len(w["rozbieznosci"])} {"⚠️" if w["rozbieznosci"] else "✅"}'
                     + (' — ' + ', '.join(f'{x["gielda"]} {x["aktywo"]}' for x in w["rozbieznosci"][:6]) if w['rozbieznosci'] else '')
                     + (f' (bez historii: {w["bez_historii"]})' if w.get('bez_historii') else '')
                     + (f' (pominięte pary z innym odstępem migawek: {w["pominiete"]})' if w.get('pominiete') else '')
                     + (f' (nowa lista portfeli — bez porównania: {", ".join(w["lista"])})' if w.get('lista') else '') + '.')
        else:
            L.append('- Wieloryby: archiwum ma mniej niż dwa dni — porównanie od jutra.')
        wl = Z.get('wh_listy')   # v218: wiek list portfeli giełd z raportów miesięcznych
        if wl and wl.get('wszystkie'):
            L.append('- Listy portfeli giełd z raportów miesięcznych (wiek): ' + ', '.join(f'{g} {n} dni' + (' ⚠️' if n > WH_LISTY_DNI else '') for g, d, n in wl['wszystkie'])
                     + (' ✅.' if not wl['stare'] else '.'))
        if Z.get('wh_nowe'):   # v237
            L.append(wh_nowe_wiersz(Z['wh_nowe']))
        wy = Z.get('wycena')   # v132: MVRV BTC z dwóch źródeł — tylko różnice procentowe i daty; brak = „—”
        if wy:
            dz = f'{wy["roznica_pct"]:+.2f}% ({wy["dzien"]})' if wy.get('roznica_pct') is not None else '—'
            L.append(f'- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia {dz}{_norma(wy.get("mediana_pct"), wy.get("n", 0), "{:+.2f}%")} — {wy.get("status", "?")} {wy.get("opis", "")}.')
        pz = Z.get('premie')
        if pz:
            L.append(f'- Premie krypto: {pz.get("opis") or "—"} ' + ('⚠️' if pz.get('uwagi') else '✅') + '.')
        em = Z.get('etf_emitent') or {}   # v130: ETF krypto u źródła — tylko różnice i daty (+ koniec pliku emitenta i jego zaległość); brak = „—”
        cz = [emitent_linia(t, F) for t, F in (em.get('fundusze') or {}).items()]
        L.append(f'- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; '
                 f'próg max {EM_TOL_MLN:g} mln USD / {EM_TOL_PCT:g}%): ' + (' · '.join(cz) if cz else (f'? kontrola przerwana ({em["blad"]})' if em.get('blad') else '—')) + '.')
        ak = Z.get('arkb')   # v355: druga kontrola przepływów ETF bitcoina (ARKB) — tylko różnice i daty; brak = bez linii
        if ak:
            L.append(f'- ETF bitcoina — druga, niezależna kontrola przepływu ARKB (zmiana liczby BTC w pliku emitenta × cena z pliku vs przepływ na stronie; '
                     f'próg max {ARK_TOL_MLN:g} mln USD / {ARK_TOL_PCT:g}%): ' + arkb_linia(ak) + '.')
        dz = Z.get('dolar')   # v136: Argentyna — tylko różnice w % i daty (bez kursów); brak pliku = bez linii
        if dz:
            L.append('- Argentyna — dwa odczyty tych samych kursów: ' + (dz.get('opis') or (f'? kontrola przerwana ({dz["blad"]})' if dz.get('blad') else '—')) + '.')
        fz = Z.get('ici')   # v134: fundusze USA — tożsamości sum ostatniego tygodnia i poprawki wydawcy (informacja, bez koloru); brak pliku = bez linii
        if fz:
            cz = [f'{ICI_KROTKO.get(k, k)} {s["tydzien"] or "—"}: {s["status"]} {s["opis"]}' for k, s in (fz.get('sumy') or {}).items()]
            L.append('- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): '
                     + (' · '.join(cz) if cz else (f'? kontrola przerwana ({fz["blad"]})' if fz.get('blad') else '—')) + '.'
                     + (' Poprawki wydawcy (informacja): ' + '; '.join(fz['rev']) + '.' if fz.get('rev') else ''))
        jz = Z.get('jpx')   # v137: Japonia — giełda vs MOF (kierunek i korelacja netto zagranicy); brak pliku = bez linii
        if jz:
            L.append('- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: '
                     + (jz.get('opis') or (f'? kontrola przerwana ({jz["blad"]})' if jz.get('blad') else '—')) + '.'
                     + (f' Korekty źródła z 7 dni: {len(jz["korekty"])} (sprawdzić ręcznie).' if jz.get('korekty') else ''))
        sz = Z.get('surowce')   # v295: surowce — sprzeczności w pliku i porównania (bez liczb cen, tylko różnice i znaki); brak pliku v2 = bez linii
        if sz:
            L.append('- Surowce (porównania z pliku strony): ' + (f'? kontrola przerwana ({sz["blad"]})' if sz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(sz['spojnosc'][:3]) + ' ❌ · ' if sz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in sz.get('wiersze') or []) or '—') + '.')
        szl = Z.get('szlaki')   # v305: szlaki handlowe — sprzeczności w pliku i progi (sumy statków, zakresy, skoki); brak pliku = bez linii
        if szl:
            L.append('- Szlaki handlowe i łańcuchy dostaw (z pliku strony): ' + (f'? kontrola przerwana ({szl["blad"]})' if szl.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(szl['spojnosc'][:3]) + ' ❌ · ' if szl.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in szl.get('wiersze') or []) or '—') + '.')
        mtz = Z.get('metale')   # v339: metale przemysłowe — sprzeczności w pliku i porównania; brak pliku = bez linii
        if mtz:
            L.append('- Metale przemysłowe (z plików strony): ' + (f'? kontrola przerwana ({mtz["blad"]})' if mtz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(mtz['spojnosc'][:3]) + ' ❌ · ' if mtz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in mtz.get('wiersze') or []) or '—') + '.')
        lgz = Z.get('lng')   # v340: gaz i LNG — sprzeczności w pliku i progi (zakres i skoki sumy UE, suma dób miesiąca wobec importu); brak pliku = bez linii
        if lgz:
            L.append('- Gaz i LNG (z pliku strony): ' + (f'? kontrola przerwana ({lgz["blad"]})' if lgz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(lgz['spojnosc'][:3]) + ' ❌ · ' if lgz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in lgz.get('wiersze') or []) or '—') + '.')
        rsz = Z.get('rosja')   # v353: Rosja — sprzeczności w pliku i porównania (iloraz handlu UE do danych zgłoszonych przez Rosję, cena uncji z rezerw, kopia złota); brak pliku = bez linii
        if rsz:
            L.append('- Rosja (z pliku strony): ' + (f'? kontrola przerwana ({rsz["blad"]})' if rsz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(rsz['spojnosc'][:3]) + ' ❌ · ' if rsz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in rsz.get('wiersze') or []) or '—') + '.')
        rpz = Z.get('polska-rynek')   # v361: Polska na rynku dziennie — sprzeczności w pliku i porównania (WIG20 z drugim dostawcą, skoki, różnica do Niemiec); brak pliku = bez linii
        if rpz:
            L.append('- Polska na rynku: giełda, obligacje, fundusze (z pliku strony): ' + (f'? kontrola przerwana ({rpz["blad"]})' if rpz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(rpz['spojnosc'][:3]) + ' ❌ · ' if rpz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in rpz.get('wiersze') or []) or '—') + '.')
        rpk = Z.get('polska-kapital')   # v365: Polska — kapitał z zagranicy i wypłaty UE — sprzeczności w pliku i porównanie z plikiem miesięcznym; brak pliku = bez linii
        if rpk:
            L.append('- Polska: kapitał z zagranicy i wypłaty UE (z pliku strony): ' + (f'? kontrola przerwana ({rpk["blad"]})' if rpk.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(rpk['spojnosc'][:3]) + ' ❌ · ' if rpk.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in rpk.get('wiersze') or []) or '—') + '.')
        rpd = Z.get('polska-dlug')   # v371: Polska — kto trzyma dług skarbowy i sprzedaż obligacji detalicznych — sprzeczności w pliku i porównanie zagranicy z plikiem nierezydentów; brak pliku = bez linii
        if rpd:
            L.append('- Polska: dług skarbowy i obligacje detaliczne (z pliku strony): ' + (f'? kontrola przerwana ({rpd["blad"]})' if rpd.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(rpd['spojnosc'][:3]) + ' ❌ · ' if rpd.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in rpd.get('wiersze') or []) or '—') + '.')
        gdz = Z.get('gieldy-dex')   # v349: giełdy scentralizowane i DEX — sprzeczności w plikach i informacje (flagi skoku listy portfeli, znak przepływu, stosunek DEX do giełd); brak plików = bez linii
        if gdz:
            L.append('- Giełdy scentralizowane, DEX i kontrakty na łańcuchu (z plików strony): ' + (f'? kontrola przerwana ({gdz["blad"]})' if gdz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(gdz['spojnosc'][:3]) + ' ❌ · ' if gdz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in gdz.get('wiersze') or []) or '—') + '.')
        for nm_, tyt_ in (('target', '- Salda TARGET krajów strefy euro (z pliku strony; porównanie z panelem „dane urzędowe”): '), ('mica', '- Rejestry MiCA (z pliku strony): ')):
            tz_ = Z.get(nm_)   # v355: brak pliku = bez linii
            if tz_:
                L.append(tyt_ + (f'? kontrola przerwana ({tz_["blad"]})' if tz_.get('blad') else
                         ('niespójności w pliku: ' + '; '.join(tz_['spojnosc'][:3]) + ' ⚠️ · ' if tz_.get('spojnosc') else '')
                         + ' · '.join(f'{o} {zn}' for o, zn in tz_.get('wiersze') or []) or '—') + '.')
        sez_ = Z.get('stable-emitenci')   # v363: emitenci stablecoinów — brak pliku = bez linii
        if sez_:
            L.append('- Emitenci stablecoinów (z pliku strony; porównania z drugim źródłem tylko informacyjnie): ' + (f'? kontrola przerwana ({sez_["blad"]})' if sez_.get('blad') else
                     ('niespójności w pliku: ' + '; '.join(sez_['spojnosc'][:3]) + ' ⚠️ · ' if sez_.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in sez_.get('wiersze') or []) or '—') + '.')
        pz_ = Z.get('plynnosc')   # v357: skład portfela Fed, bilans Eurosystemu, fundusze hedgingowe — brak plików = bez linii
        if pz_:
            L.append('- Płynność dolara i euro oraz fundusze hedgingowe (z plików strony; porównanie z panelem „dane urzędowe”): ' + (f'? kontrola przerwana ({pz_["blad"]})' if pz_.get('blad') else
                     ('niespójności w pliku: ' + '; '.join(pz_['spojnosc'][:3]) + ' ⚠️ · ' if pz_.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in pz_.get('wiersze') or []) or '—') + '.')
        kz_ = Z.get('krzywe')   # v362: krzywe rentowności — sprzeczności w pliku i zgodność 10L USA i Niemiec z rynki.json; brak pliku = bez linii
        if kz_:
            L.append('- Krzywe rentowności (z plików strony; porównanie 10L USA i Niemiec z rynki.json): ' + (f'? kontrola przerwana ({kz_["blad"]})' if kz_.get('blad') else
                     ('niespójności w pliku: ' + '; '.join(kz_['spojnosc'][:3]) + ' \u26a0\ufe0f · ' if kz_.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in kz_.get('wiersze') or []) or '—') + '.')
        sr_ = Z.get('stopy-realne')   # v366: inflacja (BIS), koniunktura (OECD), pokrycie stopy realnej i inflacja USA a CPI-U — sprzeczności w plikach; brak plików = bez linii
        if sr_:
            L.append('- Inflacja, koniunktura i stopy realne (z plików strony; inflacja USA a CPI-U z pliku usa-makro tylko informacyjnie): ' + (f'? kontrola przerwana ({sr_["blad"]})' if sr_.get('blad') else
                     ('niespójności w plikach: ' + '; '.join(sr_['spojnosc'][:3]) + ' ⚠\ufe0f · ' if sr_.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in sr_.get('wiersze') or []) or '—') + '.')
        prz = Z.get('prad')   # v367: prąd i CO2 — sprzeczności w pliku i porównania (RCE ze strefą Polska i indeksem giełdowym, ceny ujemne tylko informacją); brak pliku = bez linii
        if prz:
            L.append('- Prąd i CO2 (z pliku strony): ' + (f'? kontrola przerwana ({prz["blad"]})' if prz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(prz['spojnosc'][:3]) + ' ❌ · ' if prz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in prz.get('wiersze') or []) or '—') + '.')
        np_ = Z.get('niepewnosc')   # v368: stres i niepewność (CISS, EPU, GPR) — sprzeczności w pliku i CISS USA a indeks stresu (tylko informacja); brak pliku = bez linii
        if np_:
            L.append('- Stres i niepewność (CISS, EPU, GPR; z pliku strony; CISS USA a indeks stresu USA tylko informacyjnie): ' + (f'? kontrola przerwana ({np_["blad"]})' if np_.get('blad') else
                     ('niespójności w pliku: ' + '; '.join(np_['spojnosc'][:3]) + ' ⚠\ufe0f · ' if np_.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in np_.get('wiersze') or []) or '—') + '.')
        krz = Z.get('kalendarz')   # v372: kalendarz — sprzeczności w pliku, terminarz pusty / przeterminowany i FOMC a rynek zakładów; brak pliku = bez linii
        if krz:
            L.append('- Kalendarz (z pliku strony): ' + (f'? kontrola przerwana ({krz["blad"]})' if krz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(krz['spojnosc'][:3]) + ' ❌ · ' if krz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in krz.get('wiersze') or []) or '—') + '.')
        krz2 = Z.get('kalendarz2')   # v375: kalendarz 2 — sprzeczności w pliku i parser; brak pliku = bez linii
        if krz2:
            L.append('- Kalendarz 2 (z pliku strony): ' + (f'? kontrola przerwana ({krz2["blad"]})' if krz2.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(krz2['spojnosc'][:3]) + ' ❌ · ' if krz2.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in krz2.get('wiersze') or []) or '—') + '.')
        srz = Z.get('surowce-raporty')   # v320: raporty miesięczne o surowcach — sprzeczności w pliku i porównania; brak pliku = bez linii
        if srz:
            L.append('- Surowce — raporty miesięczne (podaż ropy, zboża, uran; z plików strony): ' + (f'? kontrola przerwana ({srz["blad"]})' if srz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(srz['spojnosc'][:3]) + ' ❌ · ' if srz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in srz.get('wiersze') or []) or '—') + '.')
        zdz = Z.get('zboza-dzien')   # v341: zboża dziennie i koszt transportu — sprzeczności w pliku i porównania; brak pliku = bez linii
        if zdz:
            L.append('- Zboża dziennie i koszt transportu (z plików strony): ' + (f'? kontrola przerwana ({zdz["blad"]})' if zdz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(zdz['spojnosc'][:3]) + ' ❌ · ' if zdz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in zdz.get('wiersze') or []) or '—') + '.')
        scz = Z.get('surowce-cftc')   # v320: pozycje funduszy USA — plik tygodniowy vs drugi kanał urzędu; brak pozycji w pliku = bez linii
        if scz:
            L.append('- Surowce — pozycje funduszy USA, plik tygodniowy vs drugi kanał urzędu (ten sam raport): ' + (f'? kontrola przerwana ({scz["blad"]})' if scz.get('blad') else
                     ' · '.join(f'{o} {zn}' for o, zn in scz.get('wiersze') or []) or '—') + '.')
        pz = Z.get('polska')   # v304: Polska — sprzeczności w pliku i porównanie złota (różnica w %, bez cen); brak pliku = bez linii
        if pz:
            L.append('- Polska (porównanie z plików strony): ' + (f'? kontrola przerwana ({pz["blad"]})' if pz.get('blad') else
                     ('sprzeczności w pliku: ' + '; '.join(pz['spojnosc'][:3]) + ' ❌ · ' if pz.get('spojnosc') else '')
                     + ' · '.join(f'{o} {zn}' for o, zn in pz.get('wiersze') or []) or '—') + '.')
        rz = Z.get('rwa')   # v133: tokenizowane aktywa — zmiana 7 dni (własna vs źródło), produkty spoza listy, skoki sumy; brak pliku = bez linii
        if rz:
            L.append('- Tokenizowane aktywa (RWA): ' + (rz.get('opis') or (f'? kontrola przerwana ({rz["blad"]})' if rz.get('blad') else '—')) + '.')
        oz = Z.get('rwa-lancuch')   # v150: odczyt własny z łańcucha — podaż 24 h, wartość vs ostatnio znana, braki; brak bloku = bez linii
        if oz:
            L.append('- Tokenizowane aktywa — odczyt własny z łańcucha: ' + (oz.get('opis') or (f'? kontrola przerwana ({oz["blad"]})' if oz.get('blad') else '—')) + '.')
        ez = Z.get('rwa-emitenci')   # v169: dane emitentów — produkty w sumach, braki, inny zakres; brak bloku = bez linii
        if ez:
            L.append('- Tokenizowane aktywa — dane emitentów: ' + (ez.get('opis') or (f'? kontrola przerwana ({ez["blad"]})' if ez.get('blad') else '—')) + '.')
    if R['bledy']:
        L += ['', '## Błędy (wymagają uwagi)'] + [f'- {x}' for x in R['bledy']]
    if R['uwagi']:
        L += ['', '## Uwagi'] + [f'- {x}' for x in R['uwagi']]
    if not R['bledy'] and not R['uwagi']:
        L += ['', 'Wszystko w normie.']
    L += ['', 'Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.']
    return '\n'.join(L) + '\n'


def kontrola_przerwana_opis(e):
    """v327 (KON-04): treść BŁĘDU przerwanej kontroli (początek „kontrola przerwana” — podpowiedź „co zrobić”)."""
    if isinstance(e, KoniecCzasu):
        return (f'kontrola przerwana: limit czasu całej kontroli ({_TERMIN["s"] or TERMIN_S:g} s) — część sprawdzeń pominięta, raport częściowy '
                '(strona albo źródła odpowiadały bardzo wolno)')
    return f'kontrola przerwana: {type(e).__name__}: {str(e)[:120]} — raport częściowy'


def kontrola_przerwana(e):
    """v327 (KON-04): wynik przerwanej kontroli — to, co kontrola() zdążyła zebrać (_R_BIEZACY), z BŁĘDEM „kontrola przerwana”; wpis
    w historii, jeśli kontrola() go nie zrobiła."""
    R = _R_BIEZACY[0] if isinstance(_R_BIEZACY[0], dict) else {}
    for kk, v in (('at', NOW.isoformat()), ('strona', {}), ('meta', {}), ('pliki', {}), ('actions', {}), ('swiezosc', []), ('zgodnosc', {}),
                  ('uwagi', []), ('bledy', [])):
        if not isinstance(R.get(kk), type(v)):
            R[kk] = v
    if not any(str(b).startswith('kontrola przerwana') for b in R['bledy']):
        R['bledy'].append(kontrola_przerwana_opis(e))
    R['przerwana'] = True
    if 'historia_n' not in R:
        try:
            m = R['meta'] if isinstance(R['meta'], dict) else {}
            os.makedirs(OUT_DIR, exist_ok=True)
            R['historia_n'] = len(historia(os.path.join(OUT_DIR, 'historia.json'), {'at': R['at'], 'bledy_zbieracza': len(m.get('errors') or []),
                                                                                    'uwagi': len(R['uwagi']), 'bledy': len(R['bledy']), 'przerwana': True}))
        except Exception:  # noqa
            pass
    R['wynik'] = 'BŁĄD'
    return R


def raport_bezpieczny(R):
    """v327 (KON-04): raport_md, a gdy raport częściowy go nie przejdzie — nagłówek, „Wynik:” i listy błędów i uwag (format bez zmian)."""
    try:
        return raport_md(R)
    except Exception:  # noqa
        L = [f'# Kontrola strony — {czas_pl(R.get("at"))} (czas polski)', '', f'**Wynik: {R.get("wynik", "BŁĄD")}**', '',
             f'❌ Błędów: {len(R.get("bledy") or [])} — wymagają uwagi (szczegóły niżej).', '']
        L += ['## Błędy (wymagają uwagi)'] + [f'- {x}' for x in R.get('bledy') or []]
        if R.get('uwagi'):
            L += ['', '## Uwagi'] + [f'- {x}' for x in R['uwagi']]
        return '\n'.join(L) + '\n'


def _alarm(signum, frame):
    raise KoniecCzasu('przerwanie awaryjne kontroli')


def main():
    stary = None
    if hasattr(signal, 'SIGALRM'):   # v327 (KON-04): przerwanie awaryjne po terminie + TERMIN_TWARDY_S (wiszące zapytanie albo przeglądarka)
        stary = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(int((TERMIN_PUSH_S if os.environ.get('GITHUB_EVENT_NAME') == 'push' else TERMIN_S) + TERMIN_TWARDY_S))
    R = None
    try:
        R = kontrola()
    except BaseException as e:  # noqa — v327: także przerwanie awaryjne i anulowanie zadania; raport częściowy zamiast żadnego
        R = kontrola_przerwana(e)
    finally:
        if stary is not None:
            signal.alarm(0); signal.signal(signal.SIGALRM, stary)
        if R is None:
            R = kontrola_przerwana(KoniecCzasu())
        md = raport_bezpieczny(R)
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(os.path.join(OUT_DIR, 'ostatnia.md'), 'w', encoding='utf-8') as f:
            f.write(md)
        with open(os.path.join(OUT_DIR, 'ostatnia.json'), 'w', encoding='utf-8') as f:
            json.dump(R, f, ensure_ascii=False, indent=1, default=str)
    print(md)
    summ = os.environ.get('GITHUB_STEP_SUMMARY')
    if summ:
        with open(summ, 'a', encoding='utf-8') as f:
            f.write(md)
    print('::notice title=kontrola::' + (R['wynik'] + ' — ' + '; '.join(R['bledy'] + R['uwagi'])[:900]).replace('%', '%25').replace('\n', '%0A'))
    sys.exit(1 if R['bledy'] else 0)


# --- v352: zmienność rynków (data/zmiennosc.json) oraz put/call i indeks stresu (data/stres.json) — świeżość w dniach roboczych (kontrola dzienna) ---
# Seria dzienna z zamknięcia sesji w USA jest publikowana z ok. 1 dniem opóźnienia; dzień danych liczony do końca doby, wiek w godzinach roboczych (bez sobót
# i niedziel). Próg 4 doby robocze (96 h) mieści opóźnienie publikacji i jedno święto giełdowe w USA; indeks stresu ma opóźnienie 2 dni robocze — próg 5 dób.
# Najwyżej ⚠️ (nigdy ❌). Plik stres jest już w PLIKI (limit 24 h) — dochodzą tylko wiersze dat put/call i indeksu stresu. Czerwień z serii awarii ('stres', 'zmiennosc')
# zostaje taka jak dla innych części z cached (wzór v211: trwała awaria > 48 h = błąd) — np. trwała blokada sieci giełdy opcji nie jest chowana.
PLIKI.insert(PLIKI.index('krypto-dzien'), 'zmiennosc')   # przed plikami krypto dziennie (test: PLIKI[-2:] bez zmian)
LIMIT_MIN['zmiennosc'] = 26 * 60
ZM_K_ETYKIETA = {'vix': 'zmienność: VIX (S&P 500, 30 dni; dni robocze USA)', 'vix3m': 'zmienność: VIX 3M (S&P 500, 3 miesiące; dni robocze USA)',
                 'vxn': 'zmienność: Nasdaq 100 (dni robocze USA)', 'vxeem': 'zmienność: rynki wschodzące (dni robocze USA)',
                 'ovx': 'zmienność: ropa (dni robocze USA)', 'gvz': 'zmienność: złoto (dni robocze USA)'}
ZM_K_PROG = 96 * 60
ST_K_ETYKIETA = {'pc': 'put/call: wskaźniki dzienne giełdy opcji USA (sesje USA)', 'fsi': 'indeks stresu finansowego USA (dni robocze, opóźnienie 2 dni)'}
ST_K_PROG = {'pc': 96 * 60, 'fsi': 120 * 60}


def zm_swiezosc(j, st=None, now=None):
    """Wiersze świeżości w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). zmiennosc.json — 6 serii; stres.json — put/call
    (tylko gdy część jest w pliku) i indeks stresu. Najwyżej ⚠️, nigdy ❌; brak pliku albo innej wersji zmiennosc = brak wierszy; seria bez daty — '?'."""
    now = now or NOW
    rows = []

    def wiersz(label, txt, prog):
        if not isinstance(txt, str) or not re.match(r'^\d{4}-\d{2}-\d{2}', txt):
            rows.append((label, '?', None, None, 'brak danych tej części w pliku')); return
        w = wiek_danych(txt, 'day', 'd', now)
        s_ = '?' if w is None else ('⚠️' if w > prog else '✅')
        rows.append((label, s_, w, txt[:10], f'próg {fmt_wiek(prog)} roboczych — najwyżej uwaga' if s_ == '⚠️' else ''))
    if isinstance(j, dict) and j.get('v') == 1:
        S_ = j.get('s') if isinstance(j.get('s'), dict) else {}
        for k, label in ZM_K_ETYKIETA.items():
            e = S_.get(k)
            wiersz(label, e.get('date') if isinstance(e, dict) else None, ZM_K_PROG)
    if isinstance(st, dict):
        for k, label in ST_K_ETYKIETA.items():
            e = st.get(k)
            if isinstance(e, dict) and not (k == 'pc' and st.get('pc_off') is True):
                wiersz(label, e.get('date'), ST_K_PROG[k])
    return rows


if __name__ == '__main__':
    main()
