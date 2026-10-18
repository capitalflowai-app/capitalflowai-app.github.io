#!/usr/bin/env python3
"""Lżejsza strona, etap 2 (v412, F11Z21): komentarze programisty usuwane TYLKO z opublikowanej kopii index.html (źródło w repozytorium bez zmian).

Komentarze w skrypcie strony (JavaScript) i w jej arkuszu stylów (CSS) to ok. 12% bajtów opublikowanej strony; czytelnik ich nie widzi,
a przeglądarka musi je pobrać i przeczytać. Narzędzie wycina je w kopii składanej przez strona.yml (krok „Złóż stronę”, zaraz po v141),
przed policzeniem skrótu wydania Service Workera.

CO WYCINA
  * w największym skrypcie strony (ten, który ma `'use strict'` na początku): komentarze blokowe i liniowe — każdy znaleziony tokenizatorem
    JavaScriptu, który rozumie łańcuchy '…' i "…", szablony `…${…}…`, wyrażenia regularne /…/flagi (także z `/` w klasie znaków [...]) oraz
    nawiasy; komentarz wewnątrz łańcucha, szablonu albo wyrażenia regularnego NIE jest komentarzem;
  * w pierwszym arkuszu <style>: komentarze /* … */ (łańcuchy i url(…) są pomijane).
  Cała linia z samym komentarzem znika razem z końcem linii; komentarz za kodem traci też białe znaki przed sobą; komentarz w środku linii
  zamienia się w spację (tokeny się nie sklejają); komentarz blokowy z końcem linii w środku linii kodu zamienia się w koniec linii
  (wstawianie średnika i `return` + nowa linia działają tak samo jak przed wycięciem).
  Zostają: wszystkie inne skrypty (licznik, Service Worker), komentarze HTML (<!-- … -->) i cały tekst poza <script>/<style>.

JAK SIĘ UPEWNIAMY (każda odmowa = kod wyjścia 1, nic nie zapisano, strona.yml publikuje kopię z komentarzami z ostrzeżeniem)
  1. tokenizator kończy w stanie czystym (żaden łańcuch, szablon, wyrażenie regularne ani komentarz nie jest otwarty, nawiasy w parach);
  2. po wycięciu ta sama funkcja daje IDENTYCZNY ciąg tokenów (skrót SHA-256 ciągu rodzaj+tekst) i ZERO komentarzy;
  3. skrypt po wycięciu ma poprawną składnię w silniku JS (node i jsc, jeśli są; `new Function`);
  4. skrypt po wycięciu jest krótszy, a CSS po wycięciu równy CSS-owi z komentarzami usuniętymi niezależnym sposobem (maska łańcuchów + wyrażenie regularne)
     z dokładnością do białych znaków.

Opcjonalny znacznik wydania: `--wydanie <skrót>` dopisuje w <head> kopii `<meta name="cf-wydanie" content="<skrót>">` — komentarze z numerami wersji
(v412 itd.) znikają z opublikowanej strony, a po znaczniku wciąż widać, który commit jest na żywo (GITHUB_SHA; bez wartości znacznika nie ma).

Użycie:  python3 narzedzia/bez_komentarzy.py <index.html w katalogu _site> [--wydanie <skrót>] [--bez-sprawdzenia]
Kody wyjścia: 0 = zapisano; 1 = odmowa (nic nie zapisano); 2 = złe argumenty. Python 3.12+, tylko biblioteka standardowa."""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile

NODE_CHATGPT = '/Applications/ChatGPT.app/Contents/Resources/cua_node/bin/node'
JSC_MACOS = '/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc'
POCZATEK_SKRYPTU = "<script>\n(function(){\n'use strict';\n"
ZNAK_KOM = '\x00'          # w tekście roboczym: komentarz bez końca linii w środku
ZNAK_KOM_NL = '\x01'       # w tekście roboczym: komentarz z końcem linii w środku


class Odmowa(Exception):
    pass


# ---------------------------------------------------------------- tokenizator JavaScriptu
RX_BIALE = re.compile(r'[ \t\r\n\f\v\u00a0\ufeff\u2028\u2029]+')
RX_NAPIS_D = re.compile(r'"(?:[^"\\\n]|\\.)*"', re.S)
RX_NAPIS_P = re.compile(r"'(?:[^'\\\n]|\\.)*'", re.S)
RX_SZABLON = re.compile(r'\\.|`|\$\{', re.S)
RX_IDENT = re.compile(r'[A-Za-z0-9_$\u0080-\u009f\u00a1-\u2027\u202a-\ufefe\uff00-\uffff]+')
RX_LICZBA = re.compile(r'0[xXbBoO][0-9a-fA-F_]+n?|(?:\d[\d_]*\.?[\d_]*|\.\d[\d_]*)(?:[eE][+-]?\d[\d_]*)?n?')
RX_FLAGI = re.compile(r'[A-Za-z]*')
# po tych słowach kluczowych może zaczynać się wyrażenie regularne (po pozostałych identyfikatorach `/` to dzielenie)
PO_SLOWIE = frozenset('return typeof instanceof in of new delete void throw case do else yield await extends'.split())
STEROWANIE = frozenset(('if', 'for', 'while', 'with'))


def tokeny_js(s):
    """Generator (rodzaj, początek, koniec): rodzaje: 'k' komentarz, 'n' napis, 's' szablon (część), 'r' wyrażenie regularne, 'i' identyfikator,
    'l' liczba, 'p' znak/operator. Spacje i końce linii nie są tokenami. Odmowa przy każdym niedomkniętym elemencie albo niesparowanych nawiasach."""
    n = len(s)
    i = 0
    stos = []          # elementy: '(' , '(c' (po if/for/while/with), '[', '{b' (blok), '{o' (obiekt), '{t' (wyrażenie w szablonie)
    prev = ('p', '')   # (rodzaj, tekst) ostatniego znaczącego tokenu; rodzaj 'o' = operand (po nim `/` to dzielenie)
    pp = ('p', '')     # token przed prev (do rozróżnienia `.słowo`)
    W = RX_BIALE.match
    szablon = False    # True: czytamy część szablonu (po ` albo po } kończącym ${…})
    while i < n:
        if szablon:
            a = i
            while True:
                m = RX_SZABLON.search(s, i)
                if not m:
                    raise Odmowa('niedomknięty szablon `…`')
                t = m.group(0)
                if t[0] == '\\':
                    i = m.end()
                    continue
                if t == '`':
                    yield ('s', a, m.end())
                    i = m.end()
                    szablon = False
                    prev, pp = ('o', '`'), prev
                    break
                yield ('s', a, m.end())          # `${`
                i = m.end()
                szablon = False
                stos.append('{t')
                prev, pp = ('p', '${'), prev
                break
            continue
        m = W(s, i)
        if m:
            i = m.end()
            continue
        c = s[i]
        d = s[i + 1] if i + 1 < n else ''
        if c == '/' and d == '/':
            j = s.find('\n', i)
            j = n if j < 0 else j
            yield ('k', i, j)
            i = j
            continue
        if c == '/' and d == '*':
            j = s.find('*/', i + 2)
            if j < 0:
                raise Odmowa('niedomknięty komentarz /* … */')
            yield ('k', i, j + 2)
            i = j + 2
            continue
        if c == '"' or c == "'":
            m = (RX_NAPIS_D if c == '"' else RX_NAPIS_P).match(s, i)
            if not m:
                raise Odmowa(f'niedomknięty łańcuch w pobliżu: {s[i:i + 40]!r}')
            yield ('n', i, m.end())
            i = m.end()
            prev, pp = ('o', 'napis'), prev
            continue
        if c == '`':
            szablon = True
            i += 1
            continue
        if c == '/':
            if prev[0] == 'o':                      # dzielenie albo /=
                yield ('p', i, i + 1)
                i += 1
                prev, pp = ('p', '/'), prev
                continue
            j = i + 1
            klasa = False
            while True:
                if j >= n or s[j] == '\n':
                    raise Odmowa(f'niedomknięte wyrażenie regularne w pobliżu: {s[i:i + 50]!r}')
                ch = s[j]
                if ch == '\\':
                    j += 2
                    continue
                if ch == '[':
                    klasa = True
                elif ch == ']':
                    klasa = False
                elif ch == '/' and not klasa:
                    break
                j += 1
            j = RX_FLAGI.match(s, j + 1).end()
            yield ('r', i, j)
            i = j
            prev, pp = ('o', '/re/'), prev
            continue
        if c.isdigit() or (c == '.' and d.isdigit() and prev[0] != 'o'):
            m = RX_LICZBA.match(s, i)
            yield ('l', i, m.end())
            i = m.end()
            prev, pp = ('o', 'liczba'), prev
            continue
        if RX_IDENT.match(c):
            m = RX_IDENT.match(s, i)
            w = m.group(0)
            yield ('i', i, m.end())
            i = m.end()
            if prev[1] == '.' and pp[1] != '.':     # właściwość: `x.return` — zwykły operand
                prev, pp = ('o', w), prev
            elif w in PO_SLOWIE:
                prev, pp = ('p', w), prev
            else:
                prev, pp = ('o', w), prev
            continue
        # znak interpunkcyjny
        yield ('p', i, i + 1)
        i += 1
        if c == '(':
            ster = prev[1] in STEROWANIE and prev[0] == 'o' and pp[1] != '.'
            stos.append('(c' if ster else '(')
            prev, pp = ('p', '('), prev
        elif c == '[':
            stos.append('[')
            prev, pp = ('p', '['), prev
        elif c == '{':
            blok = prev[1] in ('', ')', ';', '{', '}', '=>', 'else', 'do', 'try', 'finally') or (prev[0] == 'o' and prev[1] not in ('liczba', 'napis', '/re/', '`'))
            stos.append('{b' if blok else '{o')
            prev, pp = ('p', '{'), prev
        elif c in ')]}':
            if not stos:
                raise Odmowa(f'nadmiarowy nawias {c!r}')
            t = stos.pop()
            if (c == ')' and t[0] != '(') or (c == ']' and t != '[') or (c == '}' and t[0] != '{'):
                raise Odmowa(f'niesparowany nawias {c!r} (otwarty {t!r})')
            if c == '}' and t == '{t':
                szablon = True
                prev, pp = ('p', '}'), prev
            elif c == ')':
                prev, pp = (('p', ')') if t == '(c' else ('o', ')')), prev
            elif c == ']':
                prev, pp = ('o', ']'), prev
            else:
                prev, pp = (('p', '}') if t == '{b' else ('o', '}')), prev
        elif (c == '+' or c == '-') and d == c:     # ++ / -- : stan operandu bez zmian
            yield ('p', i, i + 1)
            i += 1
        elif c == '=' and d == '>':
            yield ('p', i, i + 1)
            i += 1
            prev, pp = ('p', '=>'), prev
        else:
            prev, pp = ('p', c), prev
    if szablon:
        raise Odmowa('niedomknięty szablon `…`')
    if stos:
        raise Odmowa(f'niedomknięte nawiasy: {stos[-3:]}')


def skrot_tokenow(s):
    """(skrót SHA-256 ciągu tokenów bez komentarzy, liczba tokenów, lista przedziałów komentarzy)."""
    h = hashlib.sha256()
    kom = []
    nt = 0
    for r, a, b in tokeny_js(s):
        if r == 'k':
            kom.append((a, b))
            continue
        h.update(r.encode())
        h.update(s[a:b].encode('utf-8', 'surrogatepass'))
        h.update(b'\n')
        nt += 1
    return h.hexdigest(), nt, kom


def _srodek(m):
    """Komentarz w środku linii kodu: z końcem linii w środku → koniec linii; na początku linii (po wcięciu) → samo wcięcie; przed ; , ) ] } → nic; inaczej jedna spacja."""
    if ZNAK_KOM_NL in m.group(2):
        return '\n'
    if m.start() == 0:
        return m.group(1)
    return '' if m.string[m.end():m.end() + 1] in (';', ',', ')', ']', '}') else ' '


def usun_komentarze_js(s):
    """Zwraca (nowy tekst, liczba usuniętych komentarzy, liczba usuniętych bajtów). Odmowa, gdy tekst zawiera znaki robocze."""
    if ZNAK_KOM in s or ZNAK_KOM_NL in s:
        raise Odmowa('skrypt zawiera znaki robocze \\x00/\\x01')
    kom = [(a, b) for r, a, b in tokeny_js(s) if r == 'k']
    if not kom:
        return s, 0, 0
    cz = []
    p = 0
    for a, b in kom:
        cz.append(s[p:a])
        cz.append(ZNAK_KOM_NL if '\n' in s[a:b] else ZNAK_KOM)
        p = b
    cz.append(s[p:])
    t = ''.join(cz)
    linie = t.split('\n')
    wyj = []
    for l in linie:
        if ZNAK_KOM in l or ZNAK_KOM_NL in l:
            gol = l.replace(ZNAK_KOM, '').replace(ZNAK_KOM_NL, '')
            if gol.strip(' \t\r') == '':
                continue                                   # cała linia to sam komentarz (lub same komentarze)
            l = re.sub(r'[ \t]*[\x00\x01]+[ \t\x00\x01]*$', '', l)    # komentarz(e) na końcu linii: razem z odstępem przed nimi
            if ZNAK_KOM in l or ZNAK_KOM_NL in l:         # w środku linii kodu: jedna spacja (albo koniec linii) zamiast komentarza i odstępów wokół
                l = re.sub(r'([ \t]*)([\x00\x01][ \t\x00\x01]*)([ \t]*)', _srodek, l)
        wyj.append(l)
    nowy = '\n'.join(wyj)
    return nowy, len(kom), len(s) - len(nowy)


# ---------------------------------------------------------------- CSS
def komentarze_css(s):
    """Przedziały komentarzy /* … */ w CSS (pomija "…", '…' i url(…) bez cudzysłowu). Odmowa przy niedomkniętych elementach."""
    kom = []
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '/' and s.startswith('/*', i):
            j = s.find('*/', i + 2)
            if j < 0:
                raise Odmowa('niedomknięty komentarz w CSS')
            kom.append((i, j + 2))
            i = j + 2
        elif c == '"' or c == "'":
            m = (RX_NAPIS_D if c == '"' else RX_NAPIS_P).match(s, i)
            if not m:
                raise Odmowa('niedomknięty łańcuch w CSS')
            i = m.end()
        elif c == '(' and s[max(0, i - 3):i].lower() == 'url' and not re.match(r'\s*["\']', s[i + 1:i + 40]):
            j = s.find(')', i)
            if j < 0:
                raise Odmowa('niedomknięte url( w CSS')
            i = j + 1
        else:
            i += 1
    return kom


def usun_komentarze_css(s):
    kom = komentarze_css(s)
    if not kom:
        return s, 0, 0
    cz, p = [], 0
    for a, b in kom:
        cz.append(s[p:a])
        cz.append(ZNAK_KOM)
        p = b
    cz.append(s[p:])
    t = ''.join(cz)
    wyj = []
    for l in t.split('\n'):
        if ZNAK_KOM in l:
            if l.replace(ZNAK_KOM, '').strip(' \t\r') == '':
                continue
            l = re.sub(r'[ \t]*\x00+[ \t\x00]*$', '', l)
            l = re.sub(r'\x00+', ' ', l)
        wyj.append(l)
    nowy = '\n'.join(wyj)
    return nowy, len(kom), len(s) - len(nowy)


def css_niezaleznie(s):
    """Drugi, niezależny sposób: maska łańcuchów i url(…), potem wyrażenie regularne; zwraca tekst bez białych znaków (do porównania)."""
    sl = []

    def maska(m):
        sl.append(m.group(0))
        return f'\x02{len(sl) - 1}\x03'
    t = re.sub(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|url\((?!\s*["\'])[^)]*\)', maska, s, flags=re.S)
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    t = re.sub(r'\x02(\d+)\x03', lambda m: sl[int(m.group(1))], t)
    return re.sub(r'\s+', '', t)


# ---------------------------------------------------------------- silniki JS (sprawdzenie składni)
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


SKLADNIA_JS = ("'use strict';\nconst rd=(p)=>(typeof readFile==='function'?readFile(p):(typeof read==='function'?read(p):require('node:fs').readFileSync(p,'utf8')));\n"
               "const a=(typeof process!=='undefined'?process.argv.slice(2):(typeof arguments!=='undefined'?arguments:[]));\n"
               "let r='ok';try{new Function(rd(a[0]));}catch(e){r='BLAD '+e.message;}\n"
               "const o=typeof print==='function'?print:console.log;o('SKLADNIA '+r);\n")


def sprawdz_skladnie(kod, silnik_lista=None):
    lista = silniki() if silnik_lista is None else silnik_lista
    if not lista:
        raise Odmowa('brak silnika JS do sprawdzenia składni (node albo jsc)')
    with tempfile.TemporaryDirectory() as td:
        kp, hp = os.path.join(td, 'kod.js'), os.path.join(td, 'sprawdz.cjs')
        with open(kp, 'w', encoding='utf-8', newline='') as f:
            f.write(kod)
        with open(hp, 'w', encoding='utf-8') as f:
            f.write(SKLADNIA_JS)
        for exe in lista:
            cmd = [exe, hp, '--', kp] if os.path.basename(exe).startswith('jsc') else [exe, hp, kp]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise Odmowa(f'silnik {exe}: {e}')
            if r.returncode != 0 or 'SKLADNIA ok' not in r.stdout:
                raise Odmowa(f'składnia po wycięciu komentarzy ({os.path.basename(exe)}): {(r.stdout + r.stderr)[-300:]}')
    return [os.path.basename(e) for e in lista]


# ---------------------------------------------------------------- strona
def znajdz_skrypt(html):
    """(początek treści, koniec treści) największego skryptu strony: ten, który zaczyna się od POCZATEK_SKRYPTU ('use strict' na początku)."""
    a = html.find(POCZATEK_SKRYPTU)
    if a < 0 or html.count(POCZATEK_SKRYPTU) != 1:
        raise Odmowa('nie znaleziono jednego skryptu strony (początek „(function(){ \'use strict\';”)')
    a += len('<script>')
    b = html.find('</script>', a)
    if b < 0:
        raise Odmowa('skrypt strony bez </script>')
    return a, b


def znajdz_style(html):
    a = html.find('<style>')
    if a < 0 or html.count('<style>') != 1:
        raise Odmowa('nie znaleziono jednego arkusza <style>')
    a += len('<style>')
    b = html.find('</style>', a)
    if b < 0:
        raise Odmowa('arkusz <style> bez </style>')
    return a, b


def odchudz(html, wydanie='', sprawdzac=True, silnik_lista=None):
    """Zwraca (nowa strona, opis) albo podnosi Odmowa."""
    ja, jb = znajdz_skrypt(html)
    js = html[ja:jb]
    nowy_js, nk, nb = usun_komentarze_js(js)
    if sprawdzac:
        h0, t0, _ = skrot_tokenow(js)
        h1, t1, k1 = skrot_tokenow(nowy_js)
        if k1:
            raise Odmowa(f'po wycięciu zostało {len(k1)} komentarzy')
        if h0 != h1 or t0 != t1:
            raise Odmowa(f'ciąg tokenów po wycięciu komentarzy różni się od pierwotnego ({t0} → {t1} tokenów)')
        if nowy_js != js and not len(nowy_js) < len(js):
            raise Odmowa('skrypt po wycięciu nie jest krótszy')
    sa, sb = znajdz_style(html)
    css = html[sa:sb]
    nowy_css, nkc, nbc = usun_komentarze_css(css)
    if sprawdzac:
        if komentarze_css(nowy_css):
            raise Odmowa('w arkuszu stylów zostały komentarze')
        if css_niezaleznie(css) != re.sub(r'\s+', '', nowy_css):
            raise Odmowa('arkusz stylów po wycięciu komentarzy różni się od pierwotnego (kontrola niezależna)')
    # składanie od końca, żeby przesunięcia się nie psuły (skrypt jest po arkuszu)
    if not (sb <= ja):
        raise Odmowa('nieoczekiwana kolejność: arkusz <style> musi stać przed skryptem strony')
    wynik = html[:sa] + nowy_css + html[sb:ja] + nowy_js + html[jb:]
    silniki_ok = []
    if sprawdzac:
        silniki_ok = sprawdz_skladnie(nowy_js, silnik_lista)
    if wydanie:
        if not re.fullmatch(r'[0-9a-f]{7,64}', wydanie):
            raise Odmowa('znacznik wydania musi być skrótem szesnastkowym (7–64 znaków)')
        kotwica = '<meta name="referrer" content="no-referrer">\n'
        if wynik.count(kotwica) != 1:
            raise Odmowa('brak jednej kotwicy dla znacznika wydania w <head>')
        wynik = wynik.replace(kotwica, kotwica + f'<meta name="cf-wydanie" content="{wydanie}">\n', 1)
    opis = {'js_komentarzy': nk, 'js_bajtow': nb, 'css_komentarzy': nkc, 'css_bajtow': nbc, 'silniki': silniki_ok,
            'przed': len(html.encode('utf-8')), 'po': len(wynik.encode('utf-8'))}
    return wynik, opis


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    sprawdzac = '--bez-sprawdzenia' not in argv
    argv = [a for a in argv if a != '--bez-sprawdzenia']
    wyd = ''
    if '--wydanie' in argv:
        k = argv.index('--wydanie')
        if k + 1 >= len(argv):
            print('użycie: bez_komentarzy.py <index.html> [--wydanie <skrót>] [--bez-sprawdzenia]', file=sys.stderr); return 2
        wyd = argv[k + 1]
        del argv[k:k + 2]
    if len(argv) != 1 or argv[0].startswith('-') or not os.path.isfile(argv[0]):
        print('użycie: bez_komentarzy.py <index.html> [--wydanie <skrót>] [--bez-sprawdzenia]', file=sys.stderr); return 2
    with open(argv[0], encoding='utf-8', newline='') as f:
        html = f.read()
    try:
        nowa, o = odchudz(html, wyd[:12] if re.fullmatch(r'[0-9a-f]{7,64}', wyd or '') else '', sprawdzac)
        if wyd and not re.fullmatch(r'[0-9a-f]{7,64}', wyd):
            print('v412: pusty albo nieszesnastkowy znacznik wydania — bez znacznika', file=sys.stderr)
    except Odmowa as e:
        print(f'v412 ODMOWA — nic nie zapisano (publikowana kopia z komentarzami): {e}', file=sys.stderr)
        return 1
    tmp = argv[0] + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        f.write(nowa)
    os.replace(tmp, argv[0])
    print(f"v412: komentarze wycięte: skrypt {o['js_komentarzy']} ({o['js_bajtow'] / 1024:,.0f} KB), arkusz {o['css_komentarzy']} ({o['css_bajtow'] / 1024:,.0f} KB); "
          f"index.html {o['przed'] / 1024:,.0f} KB → {o['po'] / 1024:,.0f} KB; składnia: {', '.join(o['silniki']) or 'POMINIĘTA'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
