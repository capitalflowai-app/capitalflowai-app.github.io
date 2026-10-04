#!/usr/bin/env python3
"""Lżejsza strona (v141): przy publikacji słowniki 8 języków (de, es, fr, it, pt, ru, zh, ja) idą z index.html do osobnych plików.

Strona źródłowa (index.html w repozytorium) zostaje bez zmian i ma wszystkie 10 języków; ten skrypt buduje jej lżejszą kopię w katalogu
publikacji (_site). Każdy słownik w postaci czystego JSON-a (`const EXTRAnn={"pl":{…},"en":{…},"de":{…},…};` z linią
`for(const l in EXTRAnn)…Object.assign(I18N[l],EXTRAnn[l]);`) traci w kopii 8 języków — pl i en zostają w stronie (pl to język domyślny,
en to zapas t()). Wkład tych 8 języków ze wszystkich słowników, scalony w kolejności nakładania, trafia do _site/i18n/<język>.<skrót8>.js
(window.CF_I18N_X={"lang":…,"h":…,"d":{…}}). Słowniki, które nie są JSON-em (I18N, EXTRA, EXTRA2), zostają nietknięte — muszą stać w pliku
i być nakładane PRZED każdym słownikiem JSON (inaczej odmowa), bo tylko wtedy scalony wkład nałożony po ostatnim słowniku daje dokładnie
ten sam stan końcowy co pełna strona.

W kopii: w <head> mała ładowarka (ten sam wybór języka co strona — linia przepisana dosłownie ze strony) zaczyna w tle pobieranie
i18n/xx.<skrót>.js (link rel=preload — rysowanie strony nie czeka) tylko dla języka spoza pl/en; tuż przed skryptem strony drugi mały
skrypt dopisuje przez document.write blokujący <script src> tego samego pliku (już pobranego); skrypt strony nakłada plik zaraz po
`const I18N={…};` (wczesne t()) i ponownie zaraz po ostatniej linii `for(const l in EXTRA…)` (stan końcowy); zaczep cfLangReady(l,go)
(w stronie źródłowej zawsze true) w kopii doczytuje plik innego języka przy zmianie w Ustawieniach i dopiero wtedy przełącza (go()).
Skrót w nazwie pliku = sha256 treści, więc dana index.html zawsze wskazuje dokładnie swój plik.
Brak pliku (404, blokada, brak sieci): klucze, które plik by nadpisał, są usuwane z I18N[język] (lista CF_I18N_S w kopii) — strona pokazuje
wtedy czysty angielski zapas, nigdy starszego tłumaczenia ze słowników nie-JSON (np. dawnej „oceny jakości źródeł”); przy zmianie języka
w Ustawieniach nieudane wczytanie = jedno przeładowanie z ?lang= (strażnik w sessionStorage, najpierw HEAD strony — bez sieci zostaje angielski).

Przed zapisem kopia jest sprawdzana w silniku JS (node; lokalnie także jsc z macOS): dla każdego z 10 języków końcowy I18N[język] kopii
(z plikiem tego języka) = końcowy I18N[język] pełnej strony; ładowarka wybiera właściwy plik (?lang=, pamięć przeglądarki, pl/en bez pliku);
bez pliku każdy tekst = pełna strona albo angielski; zaczep doczytuje, przełącza i raz przeładowuje. Coś nie tak = odmowa (kod 1) i nic nie
jest zapisane — w strona.yml krok „Złóż stronę” publikuje wtedy pełną stronę (bez przerwy w działaniu) z ostrzeżeniem.

Użycie:
  python3 narzedzia/odchudz_strone.py <index.html> <katalog _site> [--bez-sprawdzenia]
  python3 narzedzia/odchudz_strone.py --poprzednie <adres strony> <katalog _site>
     (najlepsza próba, zawsze kod 0, najwyżej ok. 30 s: pliki słowników wersji, która jest teraz na żywo — stara index.html z pamięci
      przeglądarki lub serwera pośredniczącego, do 10 min po publikacji, dalej znajdzie swój plik zamiast 404)
Silnik JS: zmienna CF_JS (ścieżki rozdzielone przecinkiem) albo node z PATH / node aplikacji ChatGPT / jsc z macOS (każdy znaleziony).
Kody wyjścia: 0 = zapisano; 1 = odmowa — nic nie zapisano; 2 = złe argumenty. Python 3.12, tylko biblioteka standardowa."""
# ================================ ZASADY DLA AUTORÓW ŁATEK (słowniki w index.html) ================================
# Odmowa tego narzędzia = czerwone testy (test_zbieraj_dane.LzejszaStronaV141) = brak publikacji, więc przed łatką sprawdź:
#  1. Nowy słownik = czysty JSON: const EXTRAnn={"pl":{"klucz":"tekst",…},"en":{…},"de":{…},…}; — klucze i napisy w cudzysłowach "…",
#     bez komentarzy, wyrażeń, zmiennych i szablonów `…`; wartość każdego języka to obiekt; bez klucza "__proto__".
#  2. Zaraz po nim dokładnie jedna linia: for(const l in EXTRAnn)if(I18N[l])Object.assign(I18N[l],EXTRAnn[l]);
#     Nowy słownik i jego linię dopisuje się PO ostatniej takiej linii (kolejność linii = kolejność nakładania = pierwszeństwo).
#  3. Nazwa EXTRAnn jest unikalna i występuje tylko w swojej definicji, w swojej linii for(…) i ewentualnie w komentarzu /* … */ —
#     nigdy w kodzie (np. EXTRAnn.de['x'] albo Object.keys(EXTRAnn) — po podziale części słownika nie ma w stronie).
#  4. Słowniki, które nie są JSON-em (I18N, EXTRA, EXTRA2), zostają tam, gdzie są: przed wszystkimi słownikami JSON. Nowych nie-JSON nie dodawać.
#  5. Bez zmian zostają: znacznik ładowarki w <head> (komentarz v141), linia wyboru języka (try{const q=…LANG=…}catch(e){}),
#     function cfLangReady(l,go){return true;} zaraz po t(), SEO_LANGS z 10 językami; każda zmiana języka przez cfLangReady(l,go).
#  6. Kod strony nie wylicza kluczy I18N[…] (Object.keys, for…in) — kolejność kluczy w lżejszej kopii jest inna.
# ==================================================================================================================
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zlib

JEZYKI = ('pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja')
DZIELONE = ('de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja')       # pl (domyślny) i en (zapas t()) zostają w stronie
ZNACZNIK = ('<!-- v141: miejsce ładowarki słownika języka — przy publikacji narzedzia/odchudz_strone.py wstawia tu skrypt, który przed '
            'skryptem strony wczytuje i18n/<język>.<skrót>.js (języki spoza pl i en) -->')
ZACZEP = 'function cfLangReady(l,go){return true;}'
LINIA_JEZYKA = ("try{const q=new URLSearchParams(location.search).get('lang'),m=localStorage.getItem('cfai.lang');"
                "LANG=SEO_LANGS.includes(q)?q:(SEO_LANGS.includes(m)?m:'pl');}catch(e){}")
POCZATEK = "<script>\n(function(){\n'use strict';\n"
RX_BLOK = re.compile(r'^const (I18N|EXTRA\w*)=\{', re.M)
RX_FOR = re.compile(r'^for\(const l in (EXTRA\w*)\)(?:if\(I18N\[l\]\))?Object\.assign\(I18N\[l\],\1\[l\]\);?$', re.M)
RX_SEO = re.compile(r"\bSEO_LANGS=\[([^\]]*)\]")
NODE_CHATGPT = '/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node'
JSC_MACOS = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc'
MAX_PLIK = 6 * 1024 * 1024        # dolny limit pobrania (pliki poprzedniej wersji); rzeczywisty = max(6 MB, 2 × bieżąca index.html)
BUDZET_S, OPERACJA_S = 30.0, 10.0  # cały dokładany zestaw najwyżej ok. 30 s; pojedyncza operacja sieci najwyżej 10 s

# zasady w komunikatach odmowy (krótko, dla autora następnej łatki — pełna lista w komentarzu na górze pliku)
Z_JSON = ('Zasada: nowy słownik musi być czystym JSON-em — const EXTRAnn={"pl":{"klucz":"tekst"},"en":{…},…}; (klucze i napisy w "…", '
          'bez komentarzy, wyrażeń i szablonów; wartość języka = obiekt).')
Z_FOR = ('Zasada: zaraz po słowniku dokładnie jedna linia for(const l in EXTRAnn)if(I18N[l])Object.assign(I18N[l],EXTRAnn[l]); — '
         'nowy słownik z linią dopisuje się PO ostatniej takiej linii.')
Z_NAZWA = ('Zasada: nazwa EXTRAnn jest unikalna i występuje tylko w swojej definicji, w swojej linii for(…) i w komentarzu /* … */ — '
           'nie w kodzie (np. EXTRAnn.de[…]).')
Z_KOLEJ = 'Zasada: słowniki nie-JSON (I18N, EXTRA, EXTRA2) stoją i są nakładane przed wszystkimi słownikami JSON; nowe słowniki tylko jako JSON na końcu.'
Z_ZACZ = ('Zasada: w index.html zostają bez zmian znacznik ładowarki v141 w <head>, linia wyboru języka (try{const q=…LANG=…}catch(e){}), '
          'function cfLangReady(l,go){return true;} po t() i SEO_LANGS z 10 językami.')


class Odmowa(Exception):
    """Strona nie pasuje do założeń podziału — nic nie zapisujemy (publikacja pełnej strony)."""


# ---------------------------------------------------------------- odczyt słowników
RX_KOD = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|/\*.*?\*/|//[^\n]*|[{}`"\']', re.S)
RX_SZABLON = re.compile(r'\\.|`|\$\{', re.S)
RX_PUSTE = re.compile(r'(?:\s|/\*.*?\*/|//[^\n]*)*', re.S)
RX_NAPIS = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')
RX_NAZWA = re.compile(r'[A-Za-z_$][\w$]*')


def koniec_obiektu(s, i):
    """Indeks klamry zamykającej literał obiektu JS od s[i] == '{' (napisy '…' "…", szablony `…${…}…`, komentarze)."""
    if s[i] != '{':
        raise Odmowa(f'oczekiwana klamra na pozycji {i}')
    stos, j = ['{'], i + 1
    while True:
        if stos[-1] == '`':
            m = RX_SZABLON.search(s, j)
            if not m:
                raise Odmowa('szablon bez końca w słowniku. ' + Z_JSON)
            if m.group(0) == '`':
                stos.pop()
            elif m.group(0) == '${':
                stos.append('${')
            j = m.end()
            continue
        m = RX_KOD.search(s, j)
        if not m:
            raise Odmowa('słownik bez klamry zamykającej. ' + Z_JSON)
        t, j = m.group(0), m.end()
        if t in ('"', "'"):
            raise Odmowa(f'napis bez końca w słowniku (pozycja {m.start()}). ' + Z_JSON)
        if t in ('`', '{'):
            stos.append(t)
        elif t == '}':
            stos.pop()
            if not stos:
                return m.start()


def _pary(pary):
    """object_pairs_hook: klucz __proto__ w literale JS ustawia prototyp zamiast wpisu — takiego słownika nie dzielimy."""
    for k, _ in pary:
        if k == '__proto__':
            raise Odmowa('klucz __proto__ w słowniku JSON. ' + Z_JSON)
    return dict(pary)


DEK = json.JSONDecoder(object_pairs_hook=_pary)


def czlony(s, a, b):
    """Człony najwyższego poziomu obiektu JSON s[a]=='{' … s[b]=='}': [(klucz, początek, koniec)] (tekst członu = s[początek:koniec])."""
    def pomin(j):
        while s[j] in ' \t\r\n':
            j += 1
        return j
    out, j = [], pomin(a + 1)
    if j == b:
        return out
    while True:
        k0 = j
        klucz, j = DEK.raw_decode(s, j)
        if not isinstance(klucz, str):
            raise Odmowa('klucz słownika nie jest napisem. ' + Z_JSON)
        j = pomin(j)
        if s[j] != ':':
            raise Odmowa('słownik JSON: brak dwukropka. ' + Z_JSON)
        _, j = DEK.raw_decode(s, pomin(j + 1))
        out.append((klucz, k0, j))
        j = pomin(j)
        if s[j] == ',':
            j = pomin(j + 1)
        elif s[j] == '}' and j == b:
            return out
        else:
            raise Odmowa('słownik JSON: nieoczekiwany znak po wartości. ' + Z_JSON)


def _klucz_js(s, j):
    """Klucz literału obiektu JS od pozycji j: nazwa albo napis '…' / "…" (ucieczki jak w JSON). Zwraca (klucz, koniec)."""
    m = RX_NAPIS.match(s, j)
    if m:
        q = m.group(0)
        try:
            return (json.loads(q) if q[0] == '"' else json.loads('"' + q[1:-1].replace("\\'", "'").replace('"', '\\"') + '"')), m.end()
        except ValueError:
            raise Odmowa(f'słownik nie-JSON: nieczytelny klucz {q[:40]!r}. ' + Z_KOLEJ)
    m = RX_NAZWA.match(s, j)
    if m:
        return m.group(0), m.end()
    raise Odmowa(f'słownik nie-JSON: klucz w nieznanej postaci (pozycja {j}: {s[j:j + 30]!r}). ' + Z_KOLEJ)


def _koniec_wartosci(s, j):
    """Pozycja przecinka albo klamry zamykającej, które kończą wartość od j (głębokość nawiasów 0; napisy pomijane)."""
    d = 0
    while True:
        j = RX_PUSTE.match(s, j).end()
        c = s[j]
        if c in '"\'':
            m = RX_NAPIS.match(s, j)
            if not m:
                raise Odmowa(f'słownik nie-JSON: napis bez końca (pozycja {j}). ' + Z_KOLEJ)
            j = m.end()
            continue
        if c == '`':
            raise Odmowa(f'słownik nie-JSON: szablon `…` jako wartość (pozycja {j}). ' + Z_KOLEJ)
        if c in '{[(':
            d += 1
        elif c in '}])':
            if d == 0:
                return j
            d -= 1
        elif c == ',' and d == 0:
            return j
        j += 1


def klucze_nie_json(s, a, b):
    """Klucze języków w słowniku nie-JSON s[a]=='{' … s[b]=='}' (postać {pl:{'k':'…',…},…}): {język: zbiór kluczy}."""
    out, j = {}, a + 1
    while True:
        j = RX_PUSTE.match(s, j).end()
        if j >= b:
            return out
        lang, j = _klucz_js(s, j)
        j = RX_PUSTE.match(s, j).end()
        if s[j] != ':':
            raise Odmowa(f'słownik nie-JSON: brak dwukropka po {lang!r}. ' + Z_KOLEJ)
        j = RX_PUSTE.match(s, j + 1).end()
        if s[j] != '{':
            raise Odmowa(f'słownik nie-JSON: wartość języka {lang!r} nie jest obiektem. ' + Z_KOLEJ)
        e = koniec_obiektu(s, j)
        ks, k = out.setdefault(lang, set()), j + 1
        while True:
            k = RX_PUSTE.match(s, k).end()
            if k >= e:
                break
            kl, k = _klucz_js(s, k)
            k = RX_PUSTE.match(s, k).end()
            if s[k] != ':':
                raise Odmowa(f'słownik nie-JSON: brak dwukropka po {kl!r}. ' + Z_KOLEJ)
            ks.add(kl)
            k = _koniec_wartosci(s, k + 1)
            if s[k] == ',':
                k += 1
        j = RX_PUSTE.match(s, e + 1).end()
        if j < b and s[j] == ',':
            j += 1


def bloki(s, a0, a1):
    """Słowniki w skrypcie strony s[a0:a1]: [{nazwa, start, lb, rb, obj (None = nie JSON)}] w kolejności w pliku."""
    out, nazwy = [], set()
    for m in RX_BLOK.finditer(s, a0, a1):
        lb = m.end() - 1
        rb = koniec_obiektu(s, lb)
        if s[rb + 1:rb + 2] != ';':
            raise Odmowa(f'{m.group(1)}: po słowniku brak średnika. ' + Z_JSON)
        try:
            obj, kon = DEK.raw_decode(s, lb)
            if kon != rb + 1:
                raise Odmowa(f'{m.group(1)}: JSON kończy się w innym miejscu niż literał. ' + Z_JSON)
        except ValueError:
            obj = None
        if obj is not None and not isinstance(obj, dict):
            obj = None
        if m.group(1) in nazwy:
            raise Odmowa(f'{m.group(1)}: dwa słowniki o tej samej nazwie. ' + Z_NAZWA)
        nazwy.add(m.group(1))
        out.append({'nazwa': m.group(1), 'start': m.start(), 'lb': lb, 'rb': rb, 'obj': obj})
    return out


def w_komentarzu(s, i):
    """Czy pozycja i leży w komentarzu /* … */ (ostatnie „/*” przed nią bliżej niż ostatnie „*/”)."""
    a = s.rfind('/*', max(0, i - 4000), i)
    return a >= 0 and s.rfind('*/', a, i) < 0


# ---------------------------------------------------------------- podział
def skrot(jezyk, d_json):
    """Skrót w nazwie pliku: sha256(język + '\\n' + JSON słownika z pliku)[:8] (ten sam wzór sprawdza narzedzia/kontrola.py)."""
    return hashlib.sha256((jezyk + '\n' + d_json).encode('utf-8')).hexdigest()[:8]


def js_json(o):
    """JSON jako literał JS: bez ucieczek ASCII (mniejszy plik), U+2028/U+2029 zawsze jako \\u (starsze silniki), „</” jako „<\\/”
    (plik da się bezpiecznie wkleić także w <script> strony)."""
    return (json.dumps(o, ensure_ascii=False, separators=(',', ':'))
            .replace('\u2028', '\\u2028').replace('\u2029', '\\u2029').replace('</', '<\\/'))


def podziel(src):
    """Zwraca (lżejsza strona, {język: (nazwa pliku, treść)}, opis). Odmowa, gdy strona nie pasuje do założeń."""
    def raz(tekst, co):
        n = src.count(tekst)
        if n != 1:
            raise Odmowa(f'{co}: wystąpień {n} (wymagane dokładnie 1). ' + Z_ZACZ)
        return src.index(tekst)
    p_zn = raz(ZNACZNIK, 'znacznik ładowarki w <head>')
    p_sk = raz(POCZATEK, 'początek skryptu strony')
    if not (src.find('<head>') < p_zn < src.find('</head>') < p_sk):
        raise Odmowa('znacznik ładowarki nie w <head> albo skrypt strony przed </head>. ' + Z_ZACZ)
    k_sk = src.find('\n})();\n</script>', p_sk)
    if k_sk < 0:
        raise Odmowa('skrypt strony: brak zakończenia „})();</script>”. ' + Z_ZACZ)
    p_zc = raz(ZACZEP, 'zaczep cfLangReady')
    p_lj = raz(LINIA_JEZYKA, 'linia wyboru języka')
    if not p_sk < p_lj < p_zc < k_sk:
        raise Odmowa('linia wyboru języka albo zaczep poza skryptem strony. ' + Z_ZACZ)
    m = RX_SEO.search(src, p_sk, k_sk)
    if not m or [x.strip().strip("'\"") for x in m.group(1).split(',')] != list(JEZYKI):
        raise Odmowa('SEO_LANGS inne niż 10 języków strony. ' + Z_ZACZ)
    if 'CF_I18N' in src or 'cfI18nX' in src:
        raise Odmowa('strona źródłowa już zawiera nazwy z podziału (CF_I18N / cfI18nX). Zasada: na wejściu index.html z repozytorium, '
                     'nigdy kopia z _site; nazwy CF_I18N i cfI18nX są zarezerwowane dla narzędzia.')
    B = bloki(src, p_sk, k_sk)
    if not B or B[0]['nazwa'] != 'I18N' or B[0]['obj'] is not None:
        raise Odmowa('pierwszym słownikiem musi być literał const I18N={…}. ' + Z_KOLEJ)
    fory = {}
    for f in RX_FOR.finditer(src, p_sk, k_sk):
        fory.setdefault(f.group(1), []).append(f)
    nazwy = {b['nazwa'] for b in B}
    obce = sorted(set(fory) - nazwy)
    if obce:
        raise Odmowa('linie for(const l in …) bez słownika: ' + ', '.join(obce) + '. ' + Z_FOR)
    jsonowe = [b for b in B if b['obj'] is not None]
    nie_json = [b for b in B if b['obj'] is None]
    if not jsonowe:
        raise Odmowa('brak słowników JSON do podziału. ' + Z_JSON)
    for b in B:
        f = fory.get(b['nazwa'], [])
        if b['obj'] is not None and len(f) != 1:
            raise Odmowa(f"{b['nazwa']}: linii nakładania jest {len(f)} (wymagana dokładnie 1). " + Z_FOR)
        if len(f) > 1:
            raise Odmowa(f"{b['nazwa']}: więcej niż jedna linia nakładania. " + Z_FOR)
        if f and f[0].start() < b['rb']:
            raise Odmowa(f"{b['nazwa']}: linia nakładania przed słownikiem. " + Z_FOR)
        b['for'] = f[0] if f else None
    # kolejność: wszystkie słowniki nie-JSON (i ich nakładanie) przed każdym słownikiem JSON — wtedy stan końcowy = pliki nałożone na końcu
    if max(b['start'] for b in nie_json) > min(b['start'] for b in jsonowe):
        zle = [b['nazwa'] for b in nie_json if b['start'] > min(x['start'] for x in jsonowe)]
        raise Odmowa('słownik, który nie jest JSON-em, stoi po słownikach JSON: ' + ', '.join(zle) + '. ' + Z_KOLEJ + ' ' + Z_JSON)
    f_nj = [b['for'].start() for b in nie_json if b['for']]
    if f_nj and max(f_nj) > min(b['for'].start() for b in jsonowe):
        raise Odmowa('słownik nie-JSON nakładany po słownikach JSON. ' + Z_KOLEJ)
    # nazwy słowników JSON poza definicją i linią nakładania (np. EXTRA5.de w kodzie) — po podziale byłyby puste; w komentarzach wolno
    jn = {b['nazwa']: b for b in jsonowe}
    for mm in re.finditer(r'(?<![\w$.])EXTRA\w*(?![\w$])', src):
        b, i = jn.get(mm.group(0)), mm.start()
        if b is None or b['start'] <= i <= b['rb'] or b['for'].start() <= i < b['for'].end() or w_komentarzu(src, i):
            continue
        raise Odmowa(f"{b['nazwa']}: nazwa użyta w kodzie poza słownikiem i jego linią nakładania (pozycja {i}). " + Z_NAZWA)
    # wkład 8 języków w kolejności NAKŁADANIA (linie for), wycięcie ich z tekstu słownika (pl, en i inne klucze zostają bez zmian)
    D = {j: {} for j in DZIELONE}
    for b in sorted(jsonowe, key=lambda x: x['for'].start()):
        for j in DZIELONE:
            if j in b['obj']:
                if not isinstance(b['obj'][j], dict):
                    raise Odmowa(f"{b['nazwa']}.{j}: wartość języka nie jest obiektem. " + Z_JSON)
                D[j].update(b['obj'][j])
    zamiany = []
    for b in jsonowe:
        cz = czlony(src, b['lb'], b['rb'])
        nowy = '{' + ','.join(src[a:z] for k, a, z in cz if k not in DZIELONE) + '}'
        if DEK.decode(nowy) != {k: v for k, v in b['obj'].items() if k not in DZIELONE}:
            raise Odmowa(f"{b['nazwa']}: wycięcie języków zmieniło pl/en (błąd narzędzia — zgłoś). " + Z_JSON)
        zamiany.append((b['lb'], b['rb'] + 1, nowy))
    # klucze, które plik języka nadpisuje, a które strona ma też w słownikach nie-JSON (starsze teksty): bez pliku są usuwane (angielski zapas)
    w_stronie = {}
    for b in nie_json:
        for j, ks in klucze_nie_json(src, b['lb'], b['rb']).items():
            w_stronie.setdefault(j, set()).update(ks)
    stare = {j: sorted(set(D[j]) & w_stronie.get(j, set())) for j in DZIELONE}
    pliki, H = {}, {}
    for j in DZIELONE:
        dj = js_json(D[j])
        h = skrot(j, dj)
        H[j] = h
        pliki[j] = (f'{j}.{h}.js', f'window.CF_I18N_X={{"lang":"{j}","h":"{h}","d":{dj}}};\n')
    mapa = js_json(H)
    # wstawki w lżejszej stronie
    i18n = B[0]
    if src[i18n['rb'] + 2:i18n['rb'] + 3] != '\n':
        raise Odmowa('po const I18N={…}; brak nowej linii. ' + Z_KOLEJ)
    zamiany.append((i18n['rb'] + 3, i18n['rb'] + 3, scal1(mapa, js_json(stare))))
    ost = max((b['for'] for b in B if b['for']), key=lambda f: f.start())
    if src[ost.end():ost.end() + 1] != '\n':
        raise Odmowa('ostatnia linia nakładania nie kończy się nową linią. ' + Z_FOR)
    zamiany.append((ost.end() + 1, ost.end() + 1, SCAL2))
    zamiany.append((p_zc, p_zc + len(ZACZEP), ZACZEP_KOPII))
    m_seo = '[' + ','.join("'" + j + "'" for j in JEZYKI) + ']'
    zamiany.append((p_zn, p_zn + len(ZNACZNIK), LADOWARKA.replace('__SEO__', m_seo).replace('__H__', mapa).replace('__LINIA__', LINIA_JEZYKA)))
    zamiany.append((p_sk, p_sk, PISARZ))
    zamiany.sort(key=lambda z: z[0])
    for (a1, z1, _), (a2, _, _) in zip(zamiany, zamiany[1:]):
        if z1 > a2:
            raise Odmowa('nakładające się wstawki (błąd narzędzia — zgłoś)')
    out, p = [], 0
    for a, z, t in zamiany:
        out.append(src[p:a]); out.append(t); p = z
    out.append(src[p:])
    lekka = ''.join(out)
    opis = {'bloki': len(B), 'json': len(jsonowe), 'nie_json': [b['nazwa'] for b in nie_json], 'klucze': {j: len(D[j]) for j in DZIELONE}, 'skroty': H,
            'ostatni': ost.group(1), 'stare': {j: len(v) for j, v in stare.items()}}
    return lekka, pliki, opis


def scal1(mapa, stare):
    return ('/* v141 (wstawione przy publikacji przez narzedzia/odchudz_strone.py): języki spoza pl i en z pliku i18n/<język>.<skrót>.js wczytanego '
            'przed tym skryptem — nakładane tu (wczesne t()) i ponownie po ostatnim słowniku (stan końcowy jak w pełnej stronie); CF_I18N_S = klucze, '
            'które plik nadpisuje, a słowniki nie-JSON mają w starszej wersji — bez pliku usuwane (czysty angielski zapas zamiast starego tekstu) */\n'
            'const CF_I18N_H=' + mapa + ',CF_I18N_S=' + stare + ';function cfI18nX(){const x=typeof window===\'object\'&&window?window.CF_I18N_X:null;'
            'if(x&&typeof x.lang===\'string\'&&Object.prototype.hasOwnProperty.call(CF_I18N_H,x.lang)&&x.h===CF_I18N_H[x.lang]&&x.d&&'
            'typeof x.d===\'object\'&&I18N[x.lang]){Object.assign(I18N[x.lang],x.d);cfI18nX.ok[x.lang]=1;}}cfI18nX.ok={};cfI18nX();\n')


SCAL2 = ("cfI18nX();for(const l in CF_I18N_S)if(!cfI18nX.ok[l]&&I18N[l])for(const k of CF_I18N_S[l])delete I18N[l][k];"
         "if(Object.prototype.hasOwnProperty.call(CF_I18N_H,LANG)&&!cfI18nX.ok[LANG])cfLangReady(LANG,()=>{try{applyLang();}catch(e){}},1);"
         "   /* v141: plik języka nałożony ponownie po ostatnim słowniku; języki bez pliku bez starszych tekstów (angielski zapas); gdy pliku "
         "strony brak (blokada document.write, błąd sieci) — jedna próba doczytania, bez przeładowania */\n")
# zaczep w kopii: język spoza pl/en bez pliku — doczytanie i go() po wczytaniu; przy zmianie w Ustawieniach (nie przy starcie) nieudane
# wczytanie = jedno przeładowanie z ?lang= (świeża index.html może wskazywać istniejący plik), tylko gdy strona odpowiada na HEAD i nie było
# już próby dla tego pliku w tej karcie (sessionStorage); inaczej go() — czysty angielski zapas (także bez sieci)
ZACZEP_KOPII = ("function cfLangReady(l,go,start){if(!Object.prototype.hasOwnProperty.call(CF_I18N_H,l)||cfI18nX.ok[l]){cfLangReady.w=null;return true;}"
                "cfLangReady.w=l;const v=l+'.'+CF_I18N_H[l],K='cfai.i18n.ponow',s=document.createElement('script'),"
                "dalej=()=>{if(cfLangReady.w===l){cfLangReady.w=null;go();}},"
                "fin=()=>{cfI18nX();if(cfLangReady.w!==l)return;if(cfI18nX.ok[l]||start)return dalej();let juz=true;"
                "try{juz=sessionStorage.getItem(K)===v;}catch(e){}"
                "if(juz||(typeof navigator==='object'&&navigator&&navigator.onLine===false)||typeof fetch!=='function')return dalej();"
                "fetch(location.pathname,{method:'HEAD',cache:'no-store'}).then(r=>{if(cfLangReady.w!==l)return;if(!(r&&r.ok))return dalej();"
                "try{sessionStorage.setItem(K,v);localStorage.setItem('cfai.lang',l);}catch(e){return dalej();}cfLangReady.w=null;"
                "location.replace(location.pathname+'?lang='+l+(location.hash||''));},dalej);};"
                "s.onload=fin;s.onerror=fin;s.src='i18n/'+l+'.'+CF_I18N_H[l]+'.js';document.head.appendChild(s);return false;}")
# Ładowarka i pisarz. Kompromis (przegląd v141): blokujący <script src> (document.write) tuż przed skryptem strony daje jeden render od razu
# w języku widza, bez mrugnięcia angielskiego; koszt — gdy plik języka utknie na serwerze, strona w tym języku czeka (pomiar 03.10: zatrzymanie
# pliku de na 15 s = pierwszy tekst po ok. 15 s; pl/en nie czekają). Plik leży na tym samym serwerze co index.html i jest pobierany w tle od
# <head>, więc zatrzymanie pliku oznacza w praktyce zatrzymanie całej strony — ten sam serwer zatrzymałby i ją.
LADOWARKA = ("<script>/* v141: słownik języka spoza pl i en — plik i18n/<język>.<skrót>.js tego samego serwera pobierany w tle od razu (preload, bez "
             "blokowania rysowania); wybór języka przepisany ze strony */\n(function(){const SEO_LANGS=__SEO__,H=__H__;let LANG='pl';\n__LINIA__\n"
             "if(Object.prototype.hasOwnProperty.call(H,LANG)){const s='i18n/'+LANG+'.'+H[LANG]+'.js';window.CF_I18N_SRC=s;"
             "try{const k=document.createElement('link');k.rel='preload';k.as='script';k.href=s;document.head.appendChild(k);}catch(e){}}})();</script>")
PISARZ = ("<script>/* v141: ten sam plik (już pobrany w tle) jako blokujący skrypt tuż przed skryptem strony — jeden render w języku widza; "
          "utknięcie pliku zatrzymuje stronę w tym języku (ten sam serwer co index.html) */\n"
          "if(window.CF_I18N_SRC)try{document.write('<script src=\"'+window.CF_I18N_SRC+'\"><\\/script>');}catch(e){}</script>\n")


# ---------------------------------------------------------------- sprawdzenie w silniku JS
SPRAWDZ_JS = r"""'use strict';
/* v141: porównanie pełnej i lżejszej strony w silniku JS (node albo jsc). Argumenty: pełna.html lżejsza.html katalog_z_i18n. Wypisuje raport JSON. */
const ARGS = (typeof process !== 'undefined' && process.argv) ? process.argv.slice(2) : (typeof arguments !== 'undefined' ? Array.prototype.slice.call(arguments) : []);
const RD = typeof readFile === 'function' ? (p => readFile(p)) : (p => require('fs').readFileSync(p, 'utf8'));
const ISF = p => { try { RD(p); return true; } catch (e) { return false; } };
const OUT = (typeof process === 'undefined' && typeof print === 'function') ? print : (s => console.log(s));
const LANGS = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'], SPLIT = LANGS.slice(2);
const POCZ = "<script>\n(function(){\n'use strict';\n", RX_FOR = /^for\(const l in (EXTRA\w*)\)(?:if\(I18N\[l\]\))?Object\.assign\(I18N\[l\],\1\[l\]\);?$/gm;
const R = {engine: (typeof process !== 'undefined' && process.versions && process.versions.node) ? 'node ' + process.versions.node : 'jsc', langs: {}, loader: [], missing: {}, stale: {}, hook: {}, reload: {}, early: {}, guard: {}, errors: []};
const canon = v => (v && typeof v === 'object') ? (Array.isArray(v) ? '[' + v.map(canon).join(',') + ']' : '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + canon(v[k])).join(',') + '}') : JSON.stringify(v);
const diff = (a, b) => { const o = []; for (const k of new Set([...Object.keys(a || {}), ...Object.keys(b || {})])) if (canon((a || {})[k]) !== canon((b || {})[k])) { o.push(k); if (o.length >= 5) break; } return o; };
class USP { constructor(q) { this.m = {}; String(q || '').replace(/^\?/, '').split('&').filter(Boolean).forEach(p => { const i = p.indexOf('='), k = decodeURIComponent(i < 0 ? p : p.slice(0, i)); if (!(k in this.m)) this.m[k] = decodeURIComponent(i < 0 ? '' : p.slice(i + 1)); }); } get(k) { return k in this.m ? this.m[k] : null; } }
const mkLS = (o, rzuca) => ({getItem: k => { if (rzuca) throw new Error('SecurityError'); return Object.prototype.hasOwnProperty.call(o, k) ? o[k] : null; }, setItem: (k, v) => { if (rzuca) throw new Error('SecurityError'); o[k] = String(v); }, _o: o});
const mkDoc = () => { const d = {writes: [], added: []}; d.write = s => d.writes.push(String(s)); d.createElement = t => ({tagName: String(t).toUpperCase(), src: '', href: '', rel: '', as: '', onload: null, onerror: null}); d.head = {appendChild: e => { d.added.push(e); return e; }}; return d; };
const skr = d => d.added.filter(e => e.tagName === 'SCRIPT'), pre = d => d.added.filter(e => e.tagName === 'LINK' && e.rel === 'preload');
/* otoczenie przeglądarki dla zaczepu: sessionStorage, navigator, fetch (HEAD strony; odpowiedź od razu — bez kolejki zadań) */
const mkEnv = (o) => { o = o || {}; const E = {fetches: [], ss: mkLS(o.ss || {}, !!o.ssRzuca), nav: {onLine: o.offline ? false : true}};
  E.fetch = (u, opt) => { E.fetches.push([u, opt && opt.method]); return {then: (ok, no) => { if (o.fetchRzuca) no(new Error('sieć')); else ok({ok: o.fetchOk !== false}); }}; }; return E; };
/* początek skryptu strony do końca ostatniej linii nakładania słownika (w lżejszej: z linią zaraz po niej, jeśli to drugie nałożenie) */
function prefiks(html, czy_lekka) {
  const i = html.indexOf(POCZ); if (i < 0 || html.indexOf(POCZ, i + 1) >= 0) throw new Error('skrypt strony: początek');
  const cialo = html.slice(i + POCZ.length - "'use strict';\n".length);
  let m, ost = null; RX_FOR.lastIndex = 0; while ((m = RX_FOR.exec(cialo))) ost = m;
  if (!ost) throw new Error('brak linii for(const l in …)');
  let k = ost.index + ost[0].length + 1;
  if (czy_lekka) { const k2 = cialo.indexOf('\n', k) + 1; if (/cfI18nX|CF_I18N/.test(cialo.slice(k, k2))) k = k2; }   /* linia zaraz po ostatnim nakładaniu (drugie nałożenie), jeśli jest */
  return cialo.slice(0, k);
}
const SRC = RD(ARGS[0]), LEK = RD(ARGS[1]), DIR = ARGS[2];
const PAR = ['window', 'document', 'location', 'localStorage', 'URLSearchParams', 'sessionStorage', 'navigator', 'fetch'];
const STUB = '\nfunction applyLang(){window.__applied=(window.__applied||0)+1;if(window.__rzuc)throw new Error("applyLang");}\n;return {I18N:I18N,LANG:LANG,t:t,cfLangReady:cfLangReady};';
const fSrc = new Function(...PAR, prefiks(SRC, false) + STUB);
const fLek = new Function(...PAR, prefiks(LEK, true) + STUB);
/* ładowarka w <head> (wybór języka + pobieranie w tle) i pisarz tuż przed skryptem strony (blokujący <script src>) */
const l0 = LEK.indexOf('<script>/* v141:'), l1 = LEK.indexOf('</script>', l0), pS = LEK.indexOf(POCZ), w0 = LEK.lastIndexOf('<script>/* v141:', pS), w1 = LEK.indexOf('</script>', w0);
if (l0 < 0 || l1 < 0 || l0 > LEK.indexOf('</head>')) throw new Error('lżejsza strona: brak ładowarki w <head>');
if (w0 <= l0 || w1 + '</script>\n'.length !== pS) throw new Error('lżejsza strona: pisarz nie stoi tuż przed skryptem strony');
const LADOW = new Function('window', 'document', 'location', 'localStorage', 'URLSearchParams', LEK.slice(LEK.indexOf('\n', l0) + 1, l1));
const PISZ = new Function('window', 'document', LEK.slice(LEK.indexOf('\n', w0) + 1, w1));
const loc = q => { const L = {search: q, hash: '', pathname: '/', href: 'https://example.test/' + q, replaced: []}; L.replace = u => L.replaced.push(u); return L; };
const hashPliku = src => (/"h":"([0-9a-f]{8})"/.exec(RD(DIR + '/' + src)) || [])[1];
function wczytaj(win, src) { const p = DIR + '/' + src; if (!ISF(p)) return false; new Function('window', RD(p))(win); return true; }
/* przebieg jak w przeglądarce: ładowarka w <head> (preload) → pisarz (document.write) → plik języka (gdy dopisany i jest) → skrypt strony */
function lekka(q, ls, rzuca, bezPliku, env) {
  const win = {}, doc = mkDoc(), L = mkLS(Object.assign({}, ls), rzuca), E = env || mkEnv(), lc = loc(q);
  LADOW(win, doc, lc, L, USP);
  const pl0 = pre(doc).map(e => e.as + ':' + e.href);
  PISZ(win, doc);
  const src = doc.writes.map(w => (/^<script src="([^"]+)"><\/script>$/.exec(w) || [])[1]);
  let plik = null;
  if (doc.writes.length === 1 && src[0] && !bezPliku) plik = wczytaj(win, src[0]) ? src[0] : 'BRAK:' + src[0];
  const r = fLek(win, doc, lc, L, USP, E.ss, E.nav, E.fetch);
  r.win = win; r.doc = doc; r.writes = doc.writes; r.src = src; r.plik = plik; r.preload = pl0; r.loc = lc; r.ls = L; r.env = E; return r;
}
function pelna(q, ls, rzuca) { const win = {}, doc = mkDoc(), E = mkEnv(); const r = fSrc(win, doc, loc(q), mkLS(Object.assign({}, ls), rzuca), USP, E.ss, E.nav, E.fetch); r.win = win; r.doc = doc; return r; }
const sekcja = (n, f) => { try { f(); } catch (e) { R.errors.push(n + ': ' + String(e && e.stack || e).slice(0, 400)); } };
const MAPA = (() => { const i = LEK.indexOf('const CF_I18N_H='); return i < 0 ? {} : JSON.parse(LEK.slice(i + 16, LEK.indexOf(',CF_I18N_S=', i))); })();
const STARE = (() => { const i = LEK.indexOf(',CF_I18N_S='); return i < 0 ? {} : JSON.parse(LEK.slice(i + 11, LEK.indexOf(';function cfI18nX', i))); })();
const LJ = SPLIT.find(l => (STARE[l] || []).length) || 'ja';   /* język z listą starszych tekstów (do próby przeładowania) */
const S = pelna('', {}, false);
sekcja('zaczep pełnej strony', () => { for (const l of LANGS) if (S.cfLangReady(l, () => {}) !== true) R.errors.push('pełna strona: zaczep nie zwraca true dla ' + l); });
/* 1. równoważność: 10 języków, każdy z własnym plikiem (pl, en bez pliku) — końcowy I18N[język] (i pl, en) jak w pełnej stronie; bez dociągania */
for (const l of LANGS) sekcja('język ' + l, () => {
  const K = lekka('?lang=' + l, {}, false, false);
  const d = diff(K.I18N[l], S.I18N[l]), dpl = diff(K.I18N.pl, S.I18N.pl), den = diff(K.I18N.en, S.I18N.en);
  const ok = K.LANG === l && d.length === 0 && dpl.length === 0 && den.length === 0 && skr(K.doc).length === 0 && K.env.fetches.length === 0 &&
    (SPLIT.includes(l) ? (K.writes.length === 1 && !!K.plik && !String(K.plik).startsWith('BRAK') && K.preload.join() === 'script:' + K.src[0]) : (K.writes.length === 0 && K.preload.length === 0));
  R.langs[l] = {ok, keys: Object.keys(S.I18N[l]).length, plik: K.plik, diff: d.concat(dpl.map(k => 'pl:' + k), den.map(k => 'en:' + k)), writes: K.writes.length, LANG: K.LANG};
});
/* 2. ładowarka = ten sam wybór języka co strona (?lang=, pamięć przeglądarki, pl/en bez pliku); plik istnieje i jest tego języka */
sekcja('ładowarka', () => {
  const CASES = [['?lang=de', {}, false], ['', {'cfai.lang': 'ja'}, false], ['?lang=pl', {'cfai.lang': 'de'}, false], ['?lang=en', {}, false], ['', {}, false],
    ['?lang=xx', {'cfai.lang': 'fr'}, false], ['?lang=de', {}, true], ['?lang=ru&utm=1', {'cfai.lang': 'pl'}, false], ['?lang=zh', {'cfai.lang': 'zz'}, false], ['', {'cfai.lang': 'en'}, false]];
  for (const [q, ls, rz] of CASES) {
    const K = lekka(q, ls, rz, false), Sx = pelna(q, ls, rz), split = SPLIT.includes(Sx.LANG);
    const ok = K.LANG === Sx.LANG && (split ? (K.writes.length === 1 && K.plik === K.src[0] && K.src[0] === 'i18n/' + Sx.LANG + '.' + hashPliku(K.src[0]) + '.js' && !!K.win.CF_I18N_X && K.win.CF_I18N_X.lang === Sx.LANG && K.preload.join() === 'script:' + K.src[0]) : (K.writes.length === 0 && K.preload.length === 0));
    R.loader.push({q, ls: JSON.stringify(ls), lsThrows: rz, LANG: Sx.LANG, src: K.src[0] || null, ok});
  }
});
/* 3. brak pliku przy starcie (404, blokada document.write): bez awarii; jedna próba doczytania, bez przeładowania; błąd = zapas; wczytanie = stan końcowy;
   wyjątek z applyLang w doczytaniu nie wychodzi poza zaczep */
sekcja('brak pliku', () => {
  const K = lekka('?lang=de', {}, false, true);
  const lack = Object.keys(S.I18N.de).filter(k => !(k in K.I18N.de));
  const fb = lack.filter(k => K.t(k) !== (S.I18N.en[k] ?? S.I18N.pl[k] ?? k));   // v153: t() — zapas polski po angielskim
  const a = skr(K.doc);
  const okA = a.length === 1 && a[0].src === 'i18n/de.' + hashPliku(K.src[0]) + '.js';
  if (a[0] && a[0].onerror) a[0].onerror();
  const okErr = K.win.__applied === 1 && lack.every(k => !(k in K.I18N.de)) && K.env.fetches.length === 0 && K.loc.replaced.length === 0;
  const K2 = lekka('?lang=de', {}, false, true), a2 = skr(K2.doc)[0];
  let okLoad = false;
  if (a2) { wczytaj(K2.win, a2.src); a2.onload(); okLoad = K2.win.__applied === 1 && diff(K2.I18N.de, S.I18N.de).length === 0; }
  const K3 = lekka('?lang=ja', {}, false, true), a3 = skr(K3.doc)[0];
  let okRzuc = false;
  if (a3) { K3.win.__rzuc = 1; wczytaj(K3.win, a3.src); try { a3.onload(); okRzuc = K3.win.__applied === 1; } catch (e) { okRzuc = false; } }
  R.missing = {ok: lack.length > 0 && fb.length === 0 && okA && okErr && okLoad && okRzuc, braki: lack.length, zly_zapas: fb.slice(0, 5), proba: okA, blad: okErr, wczytanie: okLoad, wyjatek: okRzuc};
});
/* 4. bez pliku (każdy z 8 języków): każdy tekst = pełna strona w tym języku albo angielski ze strony — nigdy starszy tekst ze słowników nie-JSON */
sekcja('bez pliku: bez starych tekstów', () => {
  const out = {};
  for (const l of SPLIT) {
    const K = lekka('?lang=' + l, {}, false, true), ks = new Set([...Object.keys(S.I18N[l]), ...Object.keys(S.I18N.en)]);
    let pelny = 0, ang = 0; const zle = [];
    for (const k of ks) { const v = K.t(k); if (v === (S.I18N[l][k] ?? S.I18N.en[k] ?? S.I18N.pl[k] ?? k)) pelny++; else if (v === (K.I18N.en[k] ?? K.I18N.pl[k] ?? k)) ang++; else if (zle.length < 5) zle.push(k + '=' + String(v).slice(0, 40)); }
    out[l] = {ok: zle.length === 0 && pelny > 0, klucze: ks.size, pelny, ang, zle};
  }
  R.stale = Object.assign({ok: SPLIT.every(l => out[l].ok)}, out);
});
/* 5. zaczep w lżejszej stronie: pl/en/wczytany = od razu; inny język = doczytanie i przełączenie po wczytaniu; ostatni wybór wygrywa; podwójne kliknięcie = jedno go() */
sekcja('zaczep', () => {
  const K = lekka('?lang=de', {}, false, false), H = K.cfLangReady, g = {};
  const go = n => () => { g[n] = (g[n] || 0) + 1; };
  const now = H('pl', go('pl')) === true && H('en', go('en')) === true && H('de', go('de')) === true && skr(K.doc).length === 0;
  const pend = H('ja', go('ja')) === false && skr(K.doc).length === 1 && !g.ja;
  const s = skr(K.doc)[0]; wczytaj(K.win, s.src); s.onload();
  const ja = g.ja === 1 && diff(K.I18N.ja, S.I18N.ja).length === 0 && H('ja', go('ja2')) === true;
  H('es', go('es')); H('fr', go('fr')); const es = skr(K.doc)[1], fr = skr(K.doc)[2];
  wczytaj(K.win, es.src); es.onload(); wczytaj(K.win, fr.src); fr.onload();
  const race = !g.es && g.fr === 1 && diff(K.I18N.fr, S.I18N.fr).length === 0;
  H('it', go('it')); if (H('pl', go('pl2'))) go('pl2')(); const it = skr(K.doc)[3]; it.onerror();
  const cancel = !g.it && g.pl2 === 1 && K.env.fetches.length === 0;
  H('pt', go('pt1')); H('pt', go('pt2')); const [p1, p2] = skr(K.doc).slice(4); wczytaj(K.win, p1.src); p1.onload(); p2.onload();
  const podwojne = (g.pt1 || 0) + (g.pt2 || 0) === 1;
  R.hook = {ok: now && pend && ja && race && cancel && podwojne, now, pend, ja, race, cancel, podwojne};
});
/* 6. nieudane wczytanie przy zmianie w Ustawieniach: jedno przeładowanie z ?lang= (gdy strona odpowiada na HEAD i nie było próby dla tego pliku);
   druga porażka, brak sieci, HEAD ≠ 200, błąd sieci, zablokowana pamięć karty = czysty angielski (go()) bez przeładowania */
sekcja('przeładowanie', () => {
  const pr = (env) => { const K = lekka('?lang=pl', {}, false, false, env), g = {n: 0}; const r = K.cfLangReady(LJ, () => { g.n++; }); const s = skr(K.doc)[0]; s.onerror(); return {K, g, r}; };
  const E1 = mkEnv(), a = pr(E1);
  const raz = a.r === false && a.g.n === 0 && E1.fetches.length === 1 && E1.fetches[0][0] === '/' && E1.fetches[0][1] === 'HEAD' && a.K.loc.replaced.length === 1 &&
    a.K.loc.replaced[0] === '/?lang=' + LJ && E1.ss._o['cfai.i18n.ponow'] === LJ + '.' + MAPA[LJ] && a.K.ls._o['cfai.lang'] === LJ;
  const b = pr(E1), drugi = b.g.n === 1 && E1.fetches.length === 1 && b.K.loc.replaced.length === 0;
  const czysty = (STARE[LJ] || []).every(k => !(k in b.K.I18N[LJ]));   /* po porażce: klucze starszych tekstów usunięte — t() da angielski */
  const E3 = mkEnv({offline: true}), c = pr(E3), offline = c.g.n === 1 && E3.fetches.length === 0 && c.K.loc.replaced.length === 0;
  const E4 = mkEnv({fetchOk: false}), d = pr(E4), head = d.g.n === 1 && E4.fetches.length === 1 && d.K.loc.replaced.length === 0;
  const E5 = mkEnv({fetchRzuca: true}), e = pr(E5), siec = e.g.n === 1 && e.K.loc.replaced.length === 0;
  const E6 = mkEnv({ssRzuca: true}), f = pr(E6), pamiec = f.g.n === 1 && E6.fetches.length === 0 && f.K.loc.replaced.length === 0;
  R.reload = {ok: raz && drugi && czysty && offline && head && siec && pamiec, raz, drugi, czysty, offline, head, siec, pamiec};
});
/* 7. wczesne t(): zaraz po const I18N={…}; (pierwsze nałożenie) słownik języka ma już cały plik */
sekcja('wczesne t()', () => {
  const b = LEK.indexOf(POCZ), z = LEK.indexOf('\n', LEK.indexOf('function cfLangReady(', b)) + 1;
  const f = new Function(...PAR, LEK.slice(b + POCZ.length - "'use strict';\n".length, z) + '\n;return {I18N:I18N,t:t};');
  const out = {};
  for (const l of SPLIT) {
    const win = {}; wczytaj(win, 'i18n/' + l + '.' + MAPA[l] + '.js');
    const E = mkEnv(), K = f(win, mkDoc(), loc('?lang=' + l), mkLS({}, false), USP, E.ss, E.nav, E.fetch), d = win.CF_I18N_X.d, ks = Object.keys(d);
    out[l] = ks.every(k => K.I18N[l][k] === d[k] && K.t(k) === d[k]); out.n = (out.n || 0) + ks.length;
  }
  R.early = Object.assign({ok: SPLIT.every(l => out[l]) && out.n > 0}, out);
});
/* 8. zły plik nie jest nakładany: skrót inny niż w mapie, język spoza mapy (pl; „constructor” — nie z prototypu), treść nie-obiekt */
sekcja('zły plik', () => {
  const run = X => { const E = mkEnv(); return fLek({CF_I18N_X: X}, mkDoc(), loc('?lang=' + (LANGS.includes(X.lang) ? X.lang : 'pl')), mkLS({}, false), USP, E.ss, E.nav, E.fetch); };
  const w = {}; wczytaj(w, 'i18n/de.' + MAPA.de + '.js'); const d = w.CF_I18N_X.d;
  const a = run({lang: 'de', h: '00000000', d: d}), zlySkrot = Object.keys(d).some(k => a.I18N.de[k] !== S.I18N.de[k]);
  const b = run({lang: 'pl', h: MAPA.de, d: {'nav.method': 'ZLY'}}), pl = b.I18N.pl['nav.method'] === S.I18N.pl['nav.method'];
  const c = run({lang: 'de', h: MAPA.de, d: 'abc'}), napis = !('0' in c.I18N.de);
  let proto = false; try { run({lang: 'constructor', h: Object, d: {zly141: 1}}); proto = !Object.prototype.hasOwnProperty.call(Object, 'zly141'); } finally { try { delete Object.zly141; } catch (e) { /* */ } }
  R.guard = {ok: zlySkrot && pl && napis && proto, zlySkrot, pl, napis, proto};
});
R.ok = R.errors.length === 0 && LANGS.every(l => R.langs[l] && R.langs[l].ok) && R.loader.length === 10 && R.loader.every(c => c.ok) && !!R.missing.ok && !!R.stale.ok &&
  !!R.hook.ok && !!R.reload.ok && !!R.early.ok && !!R.guard.ok;
OUT(JSON.stringify(R));
"""


def silniki():
    env = os.environ.get('CF_JS')
    if env:
        return [p for p in env.split(',') if p.strip()]
    out = []
    n = shutil.which('node') or (NODE_CHATGPT if os.path.isfile(NODE_CHATGPT) else None)
    if n:
        out.append(n)
    if os.path.isfile(JSC_MACOS):
        out.append(JSC_MACOS)
    return out


def sprawdz(src_p, lek_p, katalog, silnik_lista=None):
    """Raporty z silników JS ([dict]); Odmowa, gdy brak silnika albo którykolwiek raport nie jest „ok”."""
    lista = silniki() if silnik_lista is None else silnik_lista
    if not lista:
        raise Odmowa('brak silnika JS do sprawdzenia (node albo jsc) — bez sprawdzenia nie dzielimy')
    with tempfile.TemporaryDirectory() as td:
        h = os.path.join(td, 'sprawdz_v141.cjs')
        with open(h, 'w', encoding='utf-8') as f:
            f.write(SPRAWDZ_JS)
        raporty = []
        for exe in lista:
            cmd = [exe, h, '--', src_p, lek_p, katalog] if os.path.basename(exe).startswith('jsc') else [exe, h, src_p, lek_p, katalog]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise Odmowa(f'silnik {exe}: {e}')
            linie = [x for x in r.stdout.splitlines() if x.startswith('{')]
            if r.returncode != 0 or not linie:
                raise Odmowa(f'silnik {exe}: kod {r.returncode}; {(r.stderr or r.stdout)[-400:]}')
            rap = json.loads(linie[-1])
            raporty.append(rap)
            if not rap.get('ok'):
                zle = {k: v for k, v in rap.get('langs', {}).items() if not v.get('ok')}
                raise Odmowa(f"sprawdzenie w {rap.get('engine')}: lżejsza strona NIE jest równoważna pełnej — błędy {rap.get('errors')}; języki {zle}; "
                             f"ładowarka {[c for c in rap.get('loader', []) if not c.get('ok')]}; brak pliku {rap.get('missing')}; "
                             f"stare teksty {rap.get('stale', {}).get('ok')}; zaczep {rap.get('hook')}; wczesne {rap.get('early', {}).get('ok')}; "
                             f"osłona {rap.get('guard')}")
        return raporty


# ---------------------------------------------------------------- zapis
def gz(b):
    return len(gzip.compress(b, 9, mtime=0))


def zbuduj(src_path, site, sprawdzac=True, silnik_lista=None):
    """Buduje i (domyślnie) sprawdza lżejszą stronę; zapisuje dopiero po sprawdzeniu. Zwraca opis (dict) albo podnosi Odmowa."""
    with open(src_path, encoding='utf-8') as f:
        src = f.read()
    lekka, pliki, opis = podziel(src)
    raporty = []
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, 'i18n'))
        for j, (nazwa, tresc) in pliki.items():
            with open(os.path.join(td, 'i18n', nazwa), 'w', encoding='utf-8', newline='') as f:
                f.write(tresc)
        sp, lp = os.path.join(td, 'pelna.html'), os.path.join(td, 'index.html')
        with open(sp, 'w', encoding='utf-8', newline='') as f:
            f.write(src)
        with open(lp, 'w', encoding='utf-8', newline='') as f:
            f.write(lekka)
        if sprawdzac:
            raporty = sprawdz(sp, lp, td, silnik_lista)
    os.makedirs(os.path.join(site, 'i18n'), exist_ok=True)
    for j, (nazwa, tresc) in pliki.items():
        p = os.path.join(site, 'i18n', nazwa)
        with open(p + '.tmp', 'w', encoding='utf-8', newline='') as f:
            f.write(tresc)
        os.replace(p + '.tmp', p)
    p = os.path.join(site, 'index.html')
    with open(p + '.tmp', 'w', encoding='utf-8', newline='') as f:
        f.write(lekka)
    os.replace(p + '.tmp', p)                                   # index.html na końcu: wskazuje pliki, które już są
    sb, lb = src.encode('utf-8'), lekka.encode('utf-8')
    opis.update({'przed': (len(sb), gz(sb)), 'po': (len(lb), gz(lb)),
                 'pliki': {j: (n, len(t.encode('utf-8')), gz(t.encode('utf-8'))) for j, (n, t) in pliki.items()},
                 'sprawdzenie': [r.get('engine') for r in raporty], 'raporty': raporty})
    return opis


# ---------------------------------------------------------------- pliki poprzedniej wersji (najlepsza próba)
def limit_pobrania(site):
    """Największy przyjmowany plik: max(6 MB, 2 × bieżąca _site/index.html) — z zapasem na wzrost strony (pełna strona rośnie ok. 10%/dobę)."""
    try:
        return max(MAX_PLIK, 2 * os.path.getsize(os.path.join(site, 'index.html')))
    except OSError:
        return MAX_PLIK


def _pobierz(url, timeout=OPERACJA_S, limit=MAX_PLIK, do=None):
    """GET: limit czasu każdej operacji sieci (timeout), czas końcowy całego pobierania (do = time.monotonic()), limit rozmiaru przed
    i po rozpakowaniu gzip (bez „bomby” — dekompresja z limitem). Zwraca tekst UTF-8 albo podnosi wyjątek."""
    rq = urllib.request.Request(url, headers={'Accept-Encoding': 'gzip', 'User-Agent': 'capitalflowai-odchudz/141'})
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        czesci, n = [], 0
        while True:
            if do is not None and time.monotonic() > do:
                raise TimeoutError('budżet czasu pobierania wyczerpany')
            c = r.read1(65536)
            if not c:
                break
            n += len(c)
            if n > limit:
                raise ValueError('za duży plik')
            czesci.append(c)
        b = b''.join(czesci)
        if r.headers.get('Content-Encoding', '').lower() == 'gzip':
            z = zlib.decompressobj(16 + zlib.MAX_WBITS)
            b = z.decompress(b, limit + 1)
            if len(b) > limit or z.unconsumed_tail:
                raise ValueError('za duży plik po rozpakowaniu')
    return b.decode('utf-8')


def poprzednie(url, site, pobierz=None, budzet=BUDZET_S, timeout=OPERACJA_S, limit=None):
    """Najlepsza próba (nigdy wyjątek): dokłada do site/i18n pliki słowników wskazane przez index.html, która jest teraz na żywo.
    Całość najwyżej `budzet` sekund (+ jedna operacja), każda operacja sieci najwyżej `timeout` s, plik najwyżej `limit` bajtów.
    Zwraca (liczba dołożonych, uwagi)."""
    pobierz = pobierz or _pobierz
    limit = limit or limit_pobrania(site)
    koniec = time.monotonic() + budzet
    baza = url if url.endswith('/') else url + '/'

    def pob(u):
        zostalo = koniec - time.monotonic()
        if zostalo <= 0:
            raise TimeoutError('budżet czasu całego dokładania wyczerpany')
        return pobierz(u, timeout=min(timeout, zostalo), limit=limit, do=koniec)
    uwagi, n = [], 0
    try:
        html = pob(baza)
    except Exception as e:                                       # brak sieci / 404 / zły plik — publikacja i tak idzie
        return 0, [f'żywa strona niedostępna: {type(e).__name__}']
    m = re.search(r'const CF_I18N_H=(\{[^{}]*\})[;,]', html or '')
    if not m:
        return 0, ['żywa strona bez mapy plików słowników (pełna strona albo starsza wersja)']
    try:
        mapa = json.loads(m.group(1))
    except ValueError:
        return 0, ['mapa plików słowników nieczytelna']
    os.makedirs(os.path.join(site, 'i18n'), exist_ok=True)
    for j, h in sorted(mapa.items()):
        if j not in DZIELONE or not isinstance(h, str) or not re.fullmatch(r'[0-9a-f]{8}', h):
            uwagi.append(f'pominięty wpis {j!r}'); continue
        cel = os.path.join(site, 'i18n', f'{j}.{h}.js')
        if os.path.exists(cel):
            continue
        try:
            t = pob(f'{baza}i18n/{j}.{h}.js')
            pre = f'window.CF_I18N_X={{"lang":"{j}","h":"{h}","d":'
            if not (t.startswith(pre) and t.endswith('};\n')):
                raise ValueError('nieoczekiwana treść (początek albo koniec pliku)')
            dj = t[len(pre):-3]
            if not isinstance(json.loads(dj), dict) or skrot(j, dj) != h:
                raise ValueError('skrót nie zgadza się z treścią')
        except Exception as e:
            uwagi.append(f'{j}.{h}.js: {type(e).__name__}: {e}'[:160]); continue
        with open(cel + '.tmp', 'w', encoding='utf-8', newline='') as f:
            f.write(t)
        os.replace(cel + '.tmp', cel)
        n += 1
    return n, uwagi


def _kb(n):
    return f'{n / 1024:,.0f} KB'.replace(',', ' ')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ['--poprzednie']:
        if len(argv) != 3 or not argv[1].startswith(('https://', 'http://')) or not os.path.isdir(argv[2]):
            print('użycie: odchudz_strone.py --poprzednie <adres strony> <katalog _site>', file=sys.stderr); return 2
        t0 = time.monotonic()
        n, uwagi = poprzednie(argv[1], argv[2])
        print(f'v141: pliki słowników poprzedniej wersji z żywej strony: dołożone {n} w {time.monotonic() - t0:.1f} s'
              + (f' ({"; ".join(uwagi)})' if uwagi else ''))
        return 0
    sprawdzac = '--bez-sprawdzenia' not in argv
    args = [a for a in argv if a != '--bez-sprawdzenia']
    if len(args) != 2 or any(a.startswith('-') for a in args) or not os.path.isfile(args[0]) or not os.path.isdir(args[1]):
        print('użycie: odchudz_strone.py <index.html> <katalog _site> [--bez-sprawdzenia] | --poprzednie <adres strony> <katalog _site>', file=sys.stderr)
        return 2
    try:
        o = zbuduj(args[0], args[1], sprawdzac)
    except Odmowa as e:
        print(f'v141 ODMOWA — nic nie zapisano (publikować pełną stronę): {e}', file=sys.stderr); return 1
    (a, ag), (b, bg) = o['przed'], o['po']
    print(f"v141: index.html {_kb(a)} → {_kb(b)} (gzip {_kb(ag)} → {_kb(bg)}); słowników {o['bloki']} (JSON {o['json']}, "
          f"bez zmian: {', '.join(o['nie_json'])}); ostatni nakładany {o['ostatni']}; starszych tekstów usuwanych bez pliku: {max(o['stare'].values())}")
    print('v141: pliki i18n/: ' + ', '.join(f'{n} {_kb(r)} (gzip {_kb(g)})' for n, r, g in o['pliki'].values()))
    print('v141: sprawdzenie w silniku JS: ' + (', '.join(o['sprawdzenie']) + ' — 10 języków równe pełnej stronie, ładowarka, brak pliku bez starych '
                                                 'tekstów, zaczep' if o['sprawdzenie'] else 'POMINIĘTE (--bez-sprawdzenia)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
