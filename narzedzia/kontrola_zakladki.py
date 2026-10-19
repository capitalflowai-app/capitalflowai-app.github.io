#!/usr/bin/env python3
"""v440 (18.10.2026): stała, automatyczna kontrola zakładek GLOBAL, CRYPTO i TRENDY (punkt 10 poleceń właściciela z 18.10.2026).

Kontrola dzienna (narzedzia/kontrola.py, GitHub Actions) otwiera stronę w przeglądarce bez okna (Chrome, ekran telefonu 390 px) i sprawdza
po kolei: przełączanie zakładek, przełączniki i zakresy (1D/1T/1M…, Karty/Wykresy, okna czasu, sektory), rozwijanie bloków, rysowanie wykresów
(liczba narysowanych wykresów > 0), błędy JavaScriptu, napisy-błędy (NaN, undefined…) i czas pierwszego widoku każdej zakładki. Potem to samo
przy brakujących, pustych, starych i uciętych plikach danych — w KOPII strony, serwowanej lokalnie przez ten moduł (żywa strona, jej kod i dane
bez zmian: przeglądarka łączy się z lokalnym serwerem, który pobiera stronę i pliki z żywej strony i podmienia JEDEN plik na scenariusz).
Do kopii wstrzykiwany jest skrypt narzedzia/kontrola_zakladki.js (przełącza i liczy, każdy przełącznik wraca do stanu wyjściowego).
Wynik: sekcja w kontrola/ostatnia.md (✅/⚠️/❌ z nazwą elementu), najwyżej ⚠️ w uwagach kontroli — nigdy BŁĄD całej kontroli, bez zmian kodu strony
i danych. Czas pierwszego widoku mierzy zegar tego modułu (czas wirtualny przeglądarki nie liczy oczekiwania na sieć).
Tylko biblioteka standardowa. Python 3.12."""
import concurrent.futures
import copy
import datetime as dt
import gzip
import http.server
import json
import os
import re
import signal
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SKRYPT = os.path.join(HERE, 'kontrola_zakladki.js')
UA = 'CapitalFlowAI-kontrola/1.0'
PROGRAMY = ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser',
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
OKNO = '390,844'                  # ekran telefonu
BUDZET_MS = 900000                # czas wirtualny przeglądarki (skrypt kontroli czeka w czasie wirtualnym; sieć go wstrzymuje)
CZAS_PODSTAWOWY_S = 150           # najdłużej tyle czeka przebieg podstawowy (wszystkie przełączniki i bloki)
CZAS_SCENARIUSZ_S = 100           # i tyle przebieg z podmienionym plikiem (bez rozwijania bloków)
RWN = 2                           # tyle przebiegów z podmienionym plikiem naraz (maszyna GitHub: 2 rdzenie)
PROG_WIDOK_S = {'global': 40.0, 'crypto': 40.0, 'trendy': 40.0}   # s — pierwszy widok później niż tyle = ⚠️ (pierwsze wydanie: progi z zapasem, zob. KOMENTARZ_PROGOW)
KOMENTARZ_PROGOW = ('v440: czas pierwszego widoku liczony zegarem kontroli (od żądania strony do narysowania pierwszych paneli i wykresu); '
                    'pierwsze wydanie ostrzega dopiero po 40 s (strona czytelnika: kilka sekund), a każdy pomiar trafia do kontrola/historia.json '
                    '(pole zakl_czas) — próg do zaostrzenia po tygodniu pomiarów')
MIN_WYKRESY = {'global': 40, 'crypto': 8, 'trendy': 16}   # najmniej wykresów zakładki po rozwinięciu bloków (pomiar 18.10.2026 na żywej stronie: 119 / 21 / 48; próg ok. 1/3)
ZANIK_UDZIAL = 0.5                # przebieg z podmienionym plikiem: mniej niż tyle wykresów zakładki co w podstawowym = ⚠️ (chyba że plik jest rdzeniem zakładki)
MAKS_KROKOW_SCENARIUSZ = 250

# Scenariusze z podmienionym plikiem: (id, plik, zmiana, zakładki, opis). Plik = nazwa w data/ bez .json. „rdzen” — plik zasilający większość zakładki
# (utrata jej wykresów jest oczekiwana — liczą się wyłącznie błędy JavaScriptu i napisy-błędy).
ZMIANY = ('brak', 'pusty', 'stary', 'ucięty', 'puste_listy')
OPIS_ZMIAN = {'brak': 'plik nie istnieje (HTTP 404)', 'pusty': 'plik pusty ({})', 'stary': 'plik z datami sprzed 14 dni',
              'ucięty': 'plik niepełny (ucięty w połowie)', 'puste_listy': 'plik bez wierszy (wszystkie listy puste)'}
SCENARIUSZE = (   # pomiar 18.10.2026: pusty plik podmieniony kolejno dla wszystkich 99 plików danych strony (GLOBAL, CRYPTO, TRENDY) — 0 błędów JS; tu rdzenie zakładek i różne rodzaje uszkodzeń
    {'id': 's1', 'plik': 'krypto', 'zmiana': 'pusty', 'rdzen': True},          # rdzeń CRYPTO
    {'id': 's2', 'plik': 'rynki', 'zmiana': 'brak', 'rdzen': True},           # rdzeń GLOBAL (kafle, mapa)
    {'id': 's3', 'plik': 'trendy', 'zmiana': 'puste_listy', 'rdzen': True},   # rdzeń TRENDY
    {'id': 's4', 'plik': 'swiat-dziennik', 'zmiana': 'ucięty', 'rdzen': False},   # wyniki sygnałów TRENDY global
    {'id': 's5', 'plik': 'krypto-dziennik', 'zmiana': 'ucięty', 'rdzen': False},  # wyniki sygnałów TRENDY krypto
    {'id': 's6', 'plik': 'ceny', 'zmiana': 'puste_listy', 'rdzen': False},    # ceny GLOBAL bez wierszy
    {'id': 's7', 'plik': 'meta', 'zmiana': 'stary', 'rdzen': False},          # plik stanu sprzed 14 dni: pasek o nieaktualnych danych serwera
)

DATA_KLUCZE = {'at', 'ts', 'time', 't', 'updated', 'asof', 'as_of', 'date', 'd', 'ms'}
RE_DATA = re.compile(r'^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?)?$')


# ------------------------------------------------------------------ podmiana pliku (czyste funkcje) ------------------------------------------------------------------
def _przesun_str(s, dni):
    m = RE_DATA.match(s)
    if not m:
        return s
    try:
        d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) - dt.timedelta(days=dni)
    except ValueError:
        return s
    return f'{d.isoformat()}{s[10:]}'


def przesun_daty(obj, dni, klucz=None):
    """Wszystkie napisy-daty ISO (RRRR-MM-DD, także z godziną) cofnięte o `dni`; liczby (znacznik czasu) tylko pod kluczami czasu (at, ts, t, time…) —
    zwykłe liczby w danych (wolumeny, kapitalizacje) nietknięte."""
    if isinstance(obj, str):
        return _przesun_str(obj, dni)
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float)):
        if klucz in DATA_KLUCZE:
            if 1.4e9 < obj < 2.6e9:
                return obj - dni * 86400
            if 1.4e12 < obj < 2.6e12:
                return obj - dni * 86400 * 1000
        return obj
    if isinstance(obj, list):
        return [przesun_daty(x, dni) for x in obj]
    if isinstance(obj, dict):
        return {k: przesun_daty(v, dni, k) for k, v in obj.items()}
    return obj


def puste_listy(obj):
    """Struktura bez zmian, ale każda lista pusta (plik „niepełny”: są pola i daty, nie ma wierszy)."""
    if isinstance(obj, list):
        return []
    if isinstance(obj, dict):
        return {k: puste_listy(v) for k, v in obj.items()}
    return obj


def zmien_plik(zmiana, body):
    """→ (status HTTP, bajty odpowiedzi) dla pliku danych po podmianie."""
    if zmiana == 'brak':
        return 404, b'{"blad":"brak pliku (kontrola)"}'
    if zmiana == 'pusty':
        return 200, b'{}'
    if zmiana == 'ucięty':
        return 200, body[:max(2, len(body) // 2)]
    try:
        j = json.loads(body.decode('utf-8'))
    except Exception:  # noqa
        return 200, body   # nie JSON (nie powinno być) — bez zmiany
    if zmiana == 'stary':
        return 200, json.dumps(przesun_daty(j, 14), ensure_ascii=False).encode('utf-8')
    if zmiana == 'puste_listy':
        return 200, json.dumps(puste_listy(j), ensure_ascii=False).encode('utf-8')
    return 200, body


# ------------------------------------------------------------------ lokalny serwer kontroli ------------------------------------------------------------------
class Zrodlo:
    """Pobiera stronę i pliki z żywej strony (jedno pobranie na ścieżkę w całej kontroli — pamięć wspólna dla przebiegów)."""

    def __init__(self, site, pobierz=None):
        self.site, self.cache, self.zamek = site.rstrip('/'), {}, threading.Lock()
        self.pobierz = pobierz or self._http

    def _http(self, sciezka):
        req = urllib.request.Request(self.site + sciezka, headers={'User-Agent': UA, 'Accept-Encoding': 'gzip'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                b = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    b = gzip.decompress(b)
                return r.status, r.headers.get('Content-Type', 'application/octet-stream'), b
        except urllib.error.HTTPError as e:
            return e.code, 'text/plain', b''
        except Exception:  # noqa
            return 502, 'text/plain', b''

    def daj(self, sciezka):
        with self.zamek:
            if sciezka in self.cache:
                return self.cache[sciezka]
        w = self.pobierz(sciezka)
        with self.zamek:
            self.cache.setdefault(sciezka, w)
            return self.cache[sciezka]


class _Serwer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    request_queue_size = 128
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass   # przeglądarka zamykana sygnałem zrywa połączenia w trakcie odpowiedzi — to nie błąd kontroli (bez śladów w logu przebiegu)


def wstrzyknij(html, cfg, skrypt):
    """Skrypt kontroli zaraz po <head> (błędy łapane od początku); konfiguracja przed nim."""
    assert '</script' not in skrypt
    blok = '<script>window.__KZ_CFG=' + json.dumps(cfg) + ';\n' + skrypt + '\n</script>'
    return html.replace('<head>', '<head>' + blok, 1)


def nowy_stan():
    return {'zdarzenia': {}, 'wynik': None, 'gotowe': threading.Event(), 'zapytania': 0}


def obsluz(zrodlo, sc, cfg, skrypt, stan, metoda, adres, dane=b''):
    """Odpowiedź lokalnego serwera kontroli → (status, typ, bajty). Strona: żywy index.html ze wstrzykniętym skryptem; /data/<plik>.json scenariusza:
    plik podmieniony; reszta: bez zmian z żywej strony; /__kz/…: zdarzenia i wynik skryptu kontroli (nie wychodzą poza ten serwer)."""
    sciezka = adres.split('?', 1)[0]
    if sciezka.startswith('/__kz/'):
        nazwa = sciezka[len('/__kz/'):]
        if metoda == 'POST' and nazwa == 'wynik':
            try:
                stan['wynik'] = json.loads(dane.decode('utf-8'))
            except Exception:  # noqa
                stan['wynik'] = {'nieczytelny': True}
            stan['zdarzenia']['wynik'] = time.monotonic()
            stan['gotowe'].set()
        elif metoda == 'GET':
            stan['zdarzenia'].setdefault(nazwa, time.monotonic())
        return 204, 'text/plain', b''
    stan['zapytania'] += 1
    if sciezka in ('/', '/index.html'):
        kod, ct, body = zrodlo.daj('/index.html')
        stan['zdarzenia'].setdefault('strona', time.monotonic())
        if kod != 200:
            return kod, ct, body
        return 200, 'text/html; charset=utf-8', wstrzyknij(body.decode('utf-8', 'replace'), cfg, skrypt).encode('utf-8')
    kod, ct, body = zrodlo.daj(sciezka)
    if sc and sc.get('plik') and sciezka.startswith('/data/') and sciezka.endswith('.json') and sciezka[len('/data/'):-len('.json')] == sc['plik']:
        stan['zdarzenia'].setdefault('podmiana', time.monotonic())
        if kod != 200:
            return kod, ct, body
        k2, b2 = zmien_plik(sc['zmiana'], body)
        return k2, 'application/json', b2
    return kod, ct, body


def start_serwera(zrodlo, sc, cfg, skrypt, port=0):
    """→ (serwer, port, stan): stan = {'zdarzenia': {nazwa: czas}, 'wynik': dict|None, 'gotowe': Event, 'zapytania'}. Tylko 127.0.0.1."""
    stan = nowy_stan()

    class H(http.server.BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def log_message(self, *a):
            pass

        def _odp(self, metoda):
            n = int(self.headers.get('Content-Length') or 0)
            dane = self.rfile.read(n) if n else b''
            kod, ct, body = obsluz(zrodlo, sc, cfg, skrypt, stan, metoda, self.path, dane)
            self.send_response(kod)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._odp('GET')

        def do_POST(self):
            self._odp('POST')

    srv = _Serwer(('127.0.0.1', port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1], stan


# ------------------------------------------------------------------ przeglądarka ------------------------------------------------------------------
def program(kandydaci=PROGRAMY):
    import shutil
    env = os.environ.get('KONTROLA_CHROME')
    for k in ((env,) if env else ()) + tuple(kandydaci):
        p = (k if os.path.exists(k) else None) if os.path.isabs(k) else shutil.which(k)
        if p:
            return p
    return None


def czasy_widoku(z):
    """Czas pierwszego widoku w sekundach (zegar kontroli): GLOBAL — od żądania strony; CRYPTO i TRENDY — od kliknięcia zakładki."""
    o = {}
    s = z.get('strona')
    for t in ('global', 'crypto', 'trendy'):
        w = z.get('widok_' + t)
        p = s if t == 'global' else z.get('klik_' + t)
        o[t] = round(w - p, 1) if (w is not None and p is not None and w >= p) else None
    return o


def przebieg(zrodlo, sc, tryb, czas_s, port=0, prog=None, spij=time.sleep, zegar=time.monotonic):
    """Jeden przebieg przeglądarki: lokalny serwer + Chrome bez okna. → {'stan': 'ok'|'brak_programu'|'zawieszona'|'zakonczona'|'blad', 'czas_s',
    'wynik' (KZ ze skryptu), 'widok' (s), 'zapytania', 'brak'}."""
    prog = prog or program()
    if not prog:
        return {'stan': 'brak_programu', 'brak': 'brak przeglądarki na maszynie kontroli'}
    with open(SKRYPT, encoding='utf-8') as f:
        skrypt = f.read()
    cfg = {'tryb': tryb, 'maks': MAKS_KROKOW_SCENARIUSZ if tryb == 'dane' else 500}
    if os.environ.get('KONTROLA_ZAKL_DIAG'):
        cfg['diag'] = True
    srv, port, stan = start_serwera(zrodlo, sc, cfg, skrypt, port)
    t0, rc = zegar(), None
    try:
        with tempfile.TemporaryDirectory(prefix='kontrola-zakl-') as tmp:
            args = [prog, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
                    '--disable-dev-shm-usage', '--mute-audio', f'--user-data-dir={os.path.join(tmp, "profil")}', '--enable-logging=stderr', '--v=0',
                    f'--virtual-time-budget={BUDZET_MS}', f'--window-size={OKNO}', '--dump-dom',
                    f'http://127.0.0.1:{port}/?nc={int(time.time())}&sw=off']
            if sys.platform.startswith('linux'):
                args.insert(1, '--no-sandbox')   # maszyny GitHub (ubuntu) nie dają piaskownicy jądra; otwieramy tylko lokalną kopię własnej strony
            with open(os.path.join(tmp, 'o.html'), 'wb') as fo, open(os.path.join(tmp, 'e.log'), 'wb') as fe:
                try:
                    p = subprocess.Popen(args, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL, start_new_session=True)
                except OSError as e:
                    return {'stan': 'blad', 'brak': f'nie uruchomiono przeglądarki ({type(e).__name__})', 'czas_s': 0, 'zapytania': 0, 'widok': {}}
                try:
                    while zegar() - t0 < czas_s and p.poll() is None and not stan['gotowe'].is_set():
                        spij(0.5)
                finally:
                    rc = p.poll()
                    try:
                        os.killpg(p.pid, signal.SIGKILL)   # przeglądarka nie zamyka się sama — cała grupa procesów
                    except OSError:
                        pass
                    try:
                        p.wait(timeout=10)
                    except Exception:  # noqa
                        pass
    finally:
        srv.shutdown()
        srv.server_close()
    czas = round(zegar() - t0, 1)
    z = dict(stan['zdarzenia'])
    o = {'czas_s': czas, 'zapytania': stan['zapytania'], 'widok': czasy_widoku(z)}
    if stan['wynik'] and stan['wynik'].get('koniec'):
        o.update(stan='ok', wynik=stan['wynik'])
    elif stan['wynik']:
        o.update(stan='blad', brak='skrypt kontroli oddał niepełny wynik', wynik=stan['wynik'])
    elif rc is not None:
        o.update(stan='zakonczona', brak=f'przeglądarka zakończyła się po {czas:g} s bez wyniku, kod {rc}')
    else:
        o.update(stan='zawieszona', brak=f'bez wyniku w {czas_s:g} s — zawieszona strona albo źródło, które nie odpowiada')
    return o


# ------------------------------------------------------------------ ocena ------------------------------------------------------------------
IKONA = {'ok': '✅', 'ostrz': '⚠️', 'blad': '❌'}
ZAKL_NAZWY = (('global', 'GLOBAL'), ('crypto', 'CRYPTO'), ('trendy', 'TRENDY'))


def _ocena(z, p, n, t, u=''):
    return {'z': z, 'p': p, 'n': n, 't': t, 'u': u}


def oceny_podstawowe(w, widok):
    """Oceny z jednego przebiegu podstawowego (wynik skryptu `w`, czasy `widok`) → lista {'z','p','n','t','u'}; p = ✅ / ⚠️ / ❌ / ℹ️."""
    out = []
    err = w.get('err') or []
    for tid, tn in ZAKL_NAZWY:
        T = (w.get('tab') or {}).get(tid)
        if not T:
            out.append(_ocena(tn, '❌', 'zakładka', 'zakładka', 'skrypt nie doszedł do tej zakładki'))
            continue
        pr = T.get('przelaczenie')
        out.append(_ocena(tn, '✅' if pr else '❌', 'przełączenie zakładki', 'zakładka', '; '.join(T.get('uwagi') or []) if not pr else ''))
        nw, np_ = T.get('wykresy_po', T.get('wykresy')), T.get('panele')
        mn = MIN_WYKRESY.get(tid, 1)
        if isinstance(nw, int):
            out.append(_ocena(tn, '✅' if nw >= mn else '❌', f'rysowanie wykresów ({nw}, w {np_} panelach)', 'wykresy',
                              '' if nw >= mn else f'narysowanych wykresów {nw}, zwykle co najmniej {mn} — dane mogły się nie wczytać'))
        art = list(T.get('artefakty') or []) + [a for a in (T.get('artefakty_po') or []) if a not in (T.get('artefakty') or [])]
        out.append(_ocena(tn, '❌' if art else '✅', 'napisy-błędy (NaN, undefined…)', 'tekst', art[0] if art else ''))
        v = (widok or {}).get(tid)
        if T.get('widok_brak'):
            out.append(_ocena(tn, '❌', 'pierwszy widok zakładki', 'czas', 'brak paneli z treścią i wykresu w 25 s po otwarciu zakładki'))
        elif v is None:
            out.append(_ocena(tn, '⚠️', 'czas pierwszego widoku', 'czas', 'nie zmierzono (brak sygnału z przeglądarki)'))
        else:
            lim = PROG_WIDOK_S.get(tid, 40.0)
            out.append(_ocena(tn, '⚠️' if v > lim else '✅', f'czas pierwszego widoku ({str(v).replace(".", ",")} s)', 'czas',
                              f'dłużej niż {lim:g} s' if v > lim else ''))
    pw = w.get('powrot')
    if pw:
        ok = pw.get('ok') and (pw.get('wykresy', 0) >= max(1, int(0.7 * (pw.get('wykresy_wczesniej') or 0))))
        out.append(_ocena('GLOBAL', '✅' if ok else '❌', f'powrót do zakładki GLOBAL (wykresów {pw.get("wykresy")} z {pw.get("wykresy_wczesniej")})', 'zakładka',
                          '' if ok else '; '.join(pw.get('u') or []) or 'po powrocie wykresów wyraźnie mniej niż przed wyjściem'))
    for e in w.get('ele') or []:
        p = IKONA.get(e.get('s'), '⚠️')
        out.append(_ocena(e.get('z', '?'), p, e.get('n', '?'), e.get('t', 'element'), '; '.join(e.get('u') or [])))
    out.append(_ocena('wszystkie', '❌' if err else '✅', f'błędy JavaScriptu na stronie ({len(err)})', 'js', err[0] if err else ''))
    return out


def _klucz(x):
    """Klucz dopasowania elementu między przebiegami: nazwa bez cyfr, procentów i strzałek (etykiety bywają z liczbami z danych, np. „(25)”)."""
    n = re.sub(r'\([^)]*\d[^)]*\)', '', str(x.get('n', '')))
    n = re.sub(r'[−+-]?\d+[.,]\d+\s*%?|[−+-]?\d+\s*%|[▲▼△▽]', '', n)
    return (x.get('z'), ' '.join(n.split()))


def potwierdz(o1, o2):
    """Błąd potwierdzony tylko, gdy wystąpił w obu przebiegach podstawowych (jednorazowy — czas wirtualny, sieć — to ℹ️, nie ⚠️/❌).
    → lista ocen z o2 (stan z drugiego przebiegu), z ocenami niepotwierdzonymi zamienionymi na ℹ️."""
    k1 = {_klucz(x): x for x in o1}
    out = []
    for x in o2:
        y = dict(x)
        if x['p'] in ('⚠️', '❌'):
            a = k1.get(_klucz(x))
            if not a or a['p'] not in ('⚠️', '❌'):
                y['p'] = 'ℹ️'
                y['u'] = (x['u'] + ' ' if x['u'] else '') + '(tylko w drugim przebiegu — niepotwierdzone)'
        out.append(y)
    for x in o1:   # tylko w pierwszym przebiegu
        if x['p'] in ('⚠️', '❌') and not any(_klucz(y) == _klucz(x) and y['p'] in ('⚠️', '❌') for y in out):
            if not any(_klucz(y) == _klucz(x) for y in o2):
                continue
            for y in out:
                if _klucz(y) == _klucz(x):
                    y['p'] = 'ℹ️'
                    y['u'] = (x['u'] + ' ' if x['u'] else '') + '(tylko w pierwszym przebiegu — niepotwierdzone)'
    return out


def ocen_scenariusz(baza, w, sc, widok=None):
    """Przebieg z podmienionym plikiem wobec przebiegu podstawowego → lista ocen {'p','n','u'} dla scenariusza `sc`.
    Zasady: nowy błąd JavaScriptu, nowy napis-błąd, element z błędem, którego nie było w podstawowym, brak przełączenia zakładki = ❌;
    zanik ponad połowy wykresów zakładki (poza plikiem-rdzeniem) i brak paska o starych danych (plik meta „stary”) = ⚠️."""
    out = []
    err0, err = set(baza.get('err') or []), (w.get('err') or [])
    nowe = [e for e in err if e not in err0]
    out.append({'p': '❌' if nowe else '✅', 'n': f'błędy JavaScriptu ({len(nowe)})', 'u': nowe[0] if nowe else ''})
    art_nowe, zak_zle, zanik = [], [], []
    for tid, tn in ZAKL_NAZWY:
        T, B = (w.get('tab') or {}).get(tid) or {}, (baza.get('tab') or {}).get(tid) or {}
        if not T.get('przelaczenie'):
            zak_zle.append(f'{tn}: ' + ('; '.join(T.get('uwagi') or []) or 'zakładka się nie przełączyła'))
        a0 = set((B.get('artefakty') or []) + (B.get('artefakty_po') or []))
        for a in (T.get('artefakty') or []) + (T.get('artefakty_po') or []):
            if a not in a0:
                art_nowe.append(f'{tn}: {a}')
        nb, nw = B.get('wykresy_po', B.get('wykresy')), T.get('wykresy_po', T.get('wykresy'))
        if isinstance(nb, int) and isinstance(nw, int) and nb >= 6 and nw < nb * ZANIK_UDZIAL and not sc.get('rdzen'):
            zanik.append(f'{tn}: wykresów {nw} z {nb}')
    out.append({'p': '❌' if zak_zle else '✅', 'n': 'przełączanie zakładek', 'u': '; '.join(zak_zle)})
    out.append({'p': '❌' if art_nowe else '✅', 'n': 'napisy-błędy w tekście', 'u': '; '.join(art_nowe[:2])})
    el0 = {_klucz(e): e.get('s') for e in baza.get('ele') or []}
    zle = [e for e in w.get('ele') or [] if e.get('s') == 'blad' and el0.get(_klucz(e)) != 'blad']
    out.append({'p': '❌' if zle else '✅', 'n': f'przełączniki i zakresy ({len(w.get("ele") or [])} sprawdzonych)',
                'u': '; '.join(f'{e.get("z")} › {e.get("n")}: {"; ".join(e.get("u") or [])}' for e in zle[:2])})
    if sc.get('rdzen'):
        out.append({'p': 'ℹ️', 'n': 'wykresy zakładek', 'u': 'plik zasila większość strony — utrata wykresów jest oczekiwana, liczą się błędy powyżej'})
    else:
        out.append({'p': '⚠️' if zanik else '✅', 'n': 'wykresy zakładek', 'u': 'ponad połowa wykresów zniknęła przy jednym pliku: ' + '; '.join(zanik) if zanik else ''})
    if sc.get('plik') == 'meta' and sc.get('zmiana') == 'stary':
        st = (w.get('zegar') or {}).get('stale')
        out.append({'p': '✅' if st else '⚠️', 'n': 'pasek o nieaktualnych danych serwera', 'u': '' if st else 'plik stanu sprzed 14 dni, a strona nie pokazuje paska'})
    return out


# ------------------------------------------------------------------ całość ------------------------------------------------------------------
def _lim(termin_zostalo, maks, min_s):
    """Najdłuższy czas przebiegu przeglądarki tak, by przed terminem całej kontroli zostało 30 s zapasu; za mało czasu (< min_s) = None."""
    z = termin_zostalo() if termin_zostalo else None
    if z is None:
        return maks
    l = min(maks, z - 30)
    return l if l >= min_s else None


def kontrola_zakladek(site, termin_zostalo=None, pobierz=None, prog=None, scenariusze=None, port=0, przebieg_fn=None):
    """Pełna kontrola zakładek → słownik Z do raportu (zakladki_wiersze) i uwag (zakladki_uwagi); nigdy nie rzuca wyjątku i mieści się w terminie
    całej kontroli (`termin_zostalo` — funkcja zwracająca sekundy do terminu albo None; przebieg dostaje najwyżej tyle, ile zostało minus 30 s)."""
    t0 = time.monotonic()
    Z = {'at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'stan': 'ok', 'oceny': [], 'scenariusze': [], 'czas': {}}
    try:
        pr = przebieg_fn or przebieg
        l1 = _lim(termin_zostalo, CZAS_PODSTAWOWY_S, 60)
        if l1 is None:
            Z.update(stan='pominieta', brak='za mało czasu do końca kontroli')
            return Z
        zr = Zrodlo(site, pobierz)
        p1 = pr(zr, None, 'pelny', l1, port=port, prog=prog)
        Z['czas']['podstawowy_s'] = p1.get('czas_s')
        if p1.get('stan') != 'ok':
            Z.update(stan=p1.get('stan', 'blad'), brak=p1.get('brak', '—'))
            return Z
        o1 = oceny_podstawowe(p1['wynik'], p1.get('widok'))
        Z['wynik_podstawowy'] = {'wykresy': {k: v.get('wykresy_po', v.get('wykresy')) for k, v in (p1['wynik'].get('tab') or {}).items() if isinstance(v, dict) and k != 'global0'},
                                 'kroki': len(p1['wynik'].get('ele') or []), 'zapytania': p1.get('zapytania')}
        Z['widok'] = p1.get('widok')
        baza = p1['wynik']
        l2 = _lim(termin_zostalo, CZAS_PODSTAWOWY_S, 60)
        if any(x['p'] in ('⚠️', '❌') for x in o1) and l2 is not None:   # możliwy błąd → drugi przebieg potwierdza
            p2 = pr(zr, None, 'pelny', l2, port=port, prog=prog)
            Z['czas']['potwierdzenie_s'] = p2.get('czas_s')
            if p2.get('stan') == 'ok':
                Z['oceny'] = potwierdz(o1, oceny_podstawowe(p2['wynik'], p2.get('widok')))
                Z['potwierdzenie'] = True
                baza = p2['wynik']
            else:
                Z['oceny'] = [dict(x, p='ℹ️', u=((x['u'] + ' ') if x['u'] else '') + '(drugi przebieg nie doszedł do końca — niepotwierdzone)')
                              if x['p'] in ('⚠️', '❌') else x for x in o1]
        else:
            Z['oceny'] = o1
        lista = list(scenariusze if scenariusze is not None else SCENARIUSZE)

        def jeden(sc):
            l = _lim(termin_zostalo, CZAS_SCENARIUSZ_S, 45)
            if l is None:
                return sc, None
            return sc, pr(zr, sc, 'dane', l, port=0, prog=prog)
        pominiete = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=RWN) as ex:
            for sc, r in ex.map(jeden, lista):
                opis = f'plik „{sc["plik"]}”: {OPIS_ZMIAN.get(sc["zmiana"], sc["zmiana"])}'
                if r is None:
                    pominiete.append(sc['id'])
                elif r.get('stan') == 'ok':
                    Z['scenariusze'].append({'id': sc['id'], 'plik': sc['plik'], 'zmiana': sc['zmiana'], 'opis': opis, 'czas_s': r.get('czas_s'),
                                             'oceny': ocen_scenariusz(baza, r['wynik'], sc)})
                else:
                    Z['scenariusze'].append({'id': sc['id'], 'plik': sc['plik'], 'zmiana': sc['zmiana'], 'opis': opis, 'czas_s': r.get('czas_s'),
                                             'oceny': [{'p': 'ℹ️', 'n': 'przebieg', 'u': f'nie sprawdzono ({r.get("brak", "—")})'}]})
        if pominiete:
            Z['pominiete_scenariusze'] = pominiete
    except Exception as e:  # noqa
        Z.update(stan='blad', brak=f'błąd kontroli zakładek: {type(e).__name__}: {str(e)[:100]}')
    Z['czas']['razem_s'] = round(time.monotonic() - t0, 1)
    return Z


def zakladki_uwagi(Z):
    """Uwagi do R['uwagi'] (⚠️ całej kontroli, nigdy BŁĄD): potwierdzone ⚠️/❌ podstawowe i ❌/⚠️ scenariuszy."""
    if not isinstance(Z, dict) or Z.get('stan') != 'ok':
        return []
    out = []
    for x in Z.get('oceny') or []:
        if x['p'] in ('⚠️', '❌'):
            out.append(f'kontrola zakładek {x["z"]}: {x["n"]} — {x["u"] or "nie przeszło"}')
    for s in Z.get('scenariusze') or []:
        for x in s.get('oceny') or []:
            if x['p'] in ('⚠️', '❌'):
                out.append(f'kontrola zakładek, {s["opis"]}: {x["n"]} — {x["u"] or "nie przeszło"}')
    return out[:12]


def _grupuj(oceny, p):
    """Nazwy elementów z oceną `p` pogrupowane po panelu (nazwa „panel › etykieta”) → 'Panel: a, b · Panel2: c'."""
    g, kol = {}, []
    for x in oceny:
        if x['p'] != p or x['t'] not in ('przełącznik', 'rozwijanie'):
            continue
        pan, _, et = x['n'].partition(' › ')
        if not et:
            pan, et = '', x['n']
        if pan not in g:
            g[pan] = []
            kol.append(pan)
        g[pan].append(et)
    return ' · '.join((f'{k}: ' if k else '') + ', '.join(g[k]) for k in kol)


def zakladki_wiersze(Z):
    """Sekcja raportu (lista wierszy Markdown)."""
    L = ['', '## Kontrola zakładek GLOBAL, CRYPTO i TRENDY (przeglądarka bez okna, ekran telefonu 390 px)', '']
    if not isinstance(Z, dict):
        return L + ['- nie sprawdzono (brak wyniku) ℹ️.']
    if Z.get('stan') != 'ok':
        return L + [f'- Nie sprawdzono: {Z.get("brak") or Z.get("stan")} ℹ️.']
    c = Z.get('czas') or {}
    w = Z.get('wynik_podstawowy') or {}
    L.append(f'- Zakres: przełączanie zakładek, przełączniki i zakresy, rozwijanie bloków, wykresy, błędy JavaScriptu, napisy-błędy, czas pierwszego widoku; '
             f'potem to samo przy {len(Z.get("scenariusze") or [])} podmienionych plikach danych (kopia strony, żywa strona bez zmian). '
             f'Kroków: {w.get("kroki", "—")}; czas: {str(c.get("razem_s", "—")).replace(".", ",")} s'
             + ('; potwierdzone drugim przebiegiem' if Z.get('potwierdzenie') else '') + '.')
    for tn in [z[1] for z in ZAKL_NAZWY] + ['wszystkie']:
        ocz = [x for x in Z.get('oceny') or [] if x['z'] == tn]
        if not ocz:
            continue
        L.append('')
        L.append(f'### {tn}' if tn != 'wszystkie' else '### Cała strona')
        for x in ocz:
            if x['t'] in ('przełącznik', 'rozwijanie'):
                continue
            L.append(f'- {x["p"]} {x["n"]}' + (f' — {x["u"]}' if x['u'] else ''))
        bad = [x for x in ocz if x['t'] in ('przełącznik', 'rozwijanie') and x['p'] != '✅']
        n_ok = len([x for x in ocz if x['t'] in ('przełącznik', 'rozwijanie') and x['p'] == '✅'])
        for x in bad:
            L.append(f'- {x["p"]} {x["t"].capitalize()}: {x["n"]}' + (f' — {x["u"]}' if x['u'] else ''))
        if n_ok:
            pp = [x for x in ocz if x['t'] == 'przełącznik' and x['p'] == '✅']
            rr = [x for x in ocz if x['t'] == 'rozwijanie' and x['p'] == '✅']
            if pp:
                L.append(f'- ✅ Przełączniki i zakresy ({len(pp)}): ' + _grupuj(pp, '✅'))
            if rr:
                L.append(f'- ✅ Rozwijane bloki ({len(rr)}): ' + ', '.join(x['n'].replace(' (blok)', '').replace(' (szczegóły)', '') for x in rr))
    if Z.get('scenariusze'):
        L += ['', '### Brakujące, puste, stare i niepełne pliki danych (podmiana jednego pliku w kopii strony)']
        for s in Z['scenariusze']:
            zle = [x for x in s['oceny'] if x['p'] in ('⚠️', '❌')]
            ico = '❌' if any(x['p'] == '❌' for x in zle) else ('⚠️' if zle else ('ℹ️' if any(x['p'] == 'ℹ️' and x['n'] == 'przebieg' for x in s['oceny']) else '✅'))
            L.append(f'- {ico} {s["opis"]}: ' + ('; '.join(f'{x["p"]} {x["n"]}' + (f' — {x["u"]}' if x['u'] else '') for x in zle) if zle
                                                else 'bez nowych błędów JavaScriptu i napisów-błędów, zakładki się przełączają'
                                                + ''.join(f'; ℹ️ {x["u"]}' for x in s['oceny'] if x['p'] == 'ℹ️' and x['n'] != 'przebieg')
                                                + ''.join(f'; ✅ {x["n"]}' for x in s['oceny'] if x['p'] == '✅' and x['n'].startswith('pasek'))))
            for x in s['oceny']:
                if x['p'] == 'ℹ️' and x['n'] == 'przebieg':
                    L[-1] += f' ({x["u"]})'
    if Z.get('pominiete_scenariusze'):
        L += ['', f'- ℹ️ Podmiany plików pominięte z braku czasu do końca kontroli: {", ".join(Z["pominiete_scenariusze"])}.']
    return L
