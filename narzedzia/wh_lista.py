#!/usr/bin/env python3
"""Automatyczne odświeżanie listy portfeli OKX (v477, 19.10.2026) — tylko biblioteka standardowa, bez kluczy i tokenów.

Giełda OKX publikuje co miesiąc publiczny plik dowodu rezerw (static.okx.com/cdn/okx/por/chain/por_csv_RRRRMMDD00_V1.zip, ok. 83 MB, jeden
strumień deflate, w środku CSV: najpierw krótkie zestawienie „coin,amount”, potem tabela adresów z kolumnami coin, Type, Network, address,
amount, …). Z tabeli wybieramy 10 największych portfeli USDC w sieci Ethereum (to ok. 98 % USDC giełdy w tej sieci) — bez węzła RPC.

Przepływ (.github/workflows/wh_listy.yml, raz dziennie): szuka nowszego pliku (krótkie zapytania z Range), czyta go STRUMIENIOWO (nie zapisuje
na dysk), a listę przyjmuje do konfig/wh_listy.json TYLKO po kontrolach: (1) test odtworzenia — z pliku wzorcowego 20260908 musi wyjść dokładnie
obecnych 10 adresów; (2) sygnatura PK i suma CRC32 pliku; (3) nagłówek z kolumnami coin, Type, Network, address, amount; (4) adresy 0x + 40 znaków
szesnastkowych (zapis małymi literami); (5) 10 największych daje co najmniej 90 % USDC w sieci Ethereum. Zbieracz (zbieraj_dane.py) czyta
ten plik z wartownikiem: plik brakujący albo niepoprawny = lista wbudowana. Stan przebiegu: konfig/wh_listy_stan.json (czyta go kontrola dzienna).
Kody wyjścia: 0 — przebieg zakończony (także „brak nowszego” i błędy sieci: zapisane w stanie), 2 — zły argument. Nic nie jest wysyłane nigdzie."""
import csv
import datetime as dt
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request
import zlib

UA = 'CapitalFlowAI-collector/1.0 (public data, non-profit project)'
OKX_URL = 'https://static.okx.com/cdn/okx/por/chain/por_csv_{r}{mm}{dd}00_V1.zip'
OKX_NAZWA = 'por_csv_{r}{mm}{dd}00_V1'
NAGLOWEK_KOLUMNY = ('coin', 'Type', 'Network', 'address', 'amount')
SIEC = ('ethereum', 'eth')          # wartości kolumny Network (małe litery) oznaczające sieć Ethereum
TOP_N = 10
MIN_UDZIAL = 0.90                   # 10 największych portfeli ≥ 90 % USDC z sieci Ethereum
MIN_ADRESOW = 1000                  # w pliku jest ok. 24 000 adresów USDC na Ethereum; mniej = plik nie ten
MAX_ZLYCH = 0.001                   # najwyżej tyle wierszy USDC/Ethereum z błędną kwotą albo adresem (ułamek)
BLOK = 1 << 18                      # 256 KB odczytu
MAX_WYJSCIE = 1 << 22               # rozpakowanie porcjami do 4 MB (ochrona przed „bombą”)
MAX_SKOMPR = 400 * 1024 * 1024      # plik ok. 83 MB; więcej niż 400 MB = to nie ten plik
MAX_ROZPAK = 6 * 1024 * 1024 * 1024
LIMIT_CZASU_S = 900                 # na cały odczyt jednego pliku
OKNO_OD_DNI = 20                    # raport miesięczny: nowszego szukamy od tylu dni po dacie obecnej listy
OKNO_MAX = 45                       # najwyżej tyle dat na przebieg, od najnowszej
PAUZA_S = 0.3
PONOWNIE_PO_DNIACH = 7              # plik odrzucony przy kontroli: kolejna próba najwcześniej po tylu dniach
WZORZEC = {'plik': 'por_csv_2026090800_V1', 'since': '2026-09-08',
           'adresy': ['0xa073345811e360e9b66f24bc11f3a4bfa924f236', '0x08f619716db7c6245401b543e59acac1d25cb483',
                      '0x6709383e211ab08a6e3270532e756220400424a6', '0xa09fe38187abecc2768b98b80ea30afbc2fbd774',
                      '0x445f16314284b43dfa1fd3cd77b9dea4a1bebd97', '0x87d0d6c8cdd71a658ecf1566f13e4cbc562beaf9',
                      '0x1dfc6bec8499fcb5e3151c7c6d27feb9d7eae1d4', '0xebf6c883a1d60ab38c8ed4780aadbfe4c805ed4f',
                      '0x3425519651e4c42833633fe5c0e24ed89c1023a3', '0x7fea5b4568751533039179116e372e26b6b41b13']}
ADRES = re.compile(r'^0x[0-9a-f]{40}$')
ADRES_PLIK = re.compile(r'^0x[0-9a-fA-F]{40}$')
DATA = re.compile(r'^\d{4}-\d{2}-\d{2}$')
PLIK = re.compile(r'^por_csv_(\d{4})(\d{2})(\d{2})00_V1$')
KORZEN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LISTA_PLIK = os.path.join(KORZEN, 'konfig', 'wh_listy.json')
STAN_PLIK = os.path.join(KORZEN, 'konfig', 'wh_listy_stan.json')


class BladPliku(Exception):
    """Zawartość pliku jest niepoprawna (sygnatura, CRC, nagłówek, adresy, udział) — plik NIE jest przyjmowany."""


class BladSieci(Exception):
    """Brak odpowiedzi, przerwane łączenie, plik ucięty, limit czasu — nic nie wiadomo o pliku; próba ponowiona następnego dnia."""


# ---------- odczyt archiwum ZIP strumieniowo ----------
def _dokladnie(odczyt, n):
    b = b''
    while len(b) < n:
        k = odczyt(n - len(b))
        if not k:
            break
        b += k
    return b


def strumien_zip(odczyt, blok=BLOK, max_skompr=MAX_SKOMPR, max_rozpak=MAX_ROZPAK, zegar=time.monotonic, limit_s=LIMIT_CZASU_S):
    """Generator kawałków pierwszego pliku archiwum ZIP (deflate, także z deskryptorem danych po strumieniu). Po ostatnim kawałku sprawdza
    sumę CRC32 i rozmiar; niezgodność = BladPliku. Plik ucięty albo przerwane łączenie = BladSieci. Kto przerwał pętlę przed końcem, nie ma wyniku."""
    t0 = zegar()
    h = _dokladnie(odczyt, 30)
    if h[:4] != b'PK\x03\x04' and len(h) >= 4:
        raise BladPliku('brak sygnatury pliku ZIP (PK)')
    if len(h) < 30:
        raise BladSieci('plik ucięty w nagłówku' if h[:4] == b'PK\x03\x04' else 'pusta odpowiedź')
    flaga, met = struct.unpack('<HH', h[6:10])
    crc_h, _, rozm_h = struct.unpack('<III', h[14:26])
    nl, el = struct.unpack('<HH', h[26:30])
    if met != 8 or flaga & 1:
        raise BladPliku('inna metoda kompresji albo plik zaszyfrowany')
    if len(_dokladnie(odczyt, nl + el)) < nl + el:
        raise BladSieci('plik ucięty w nagłówku')
    d = zlib.decompressobj(-15)
    crc = rozm = 0
    wczytano = 30 + nl + el
    while not d.eof:
        if zegar() - t0 > limit_s:
            raise BladSieci('limit czasu odczytu pliku')
        k = odczyt(blok)
        if not k:
            raise BladSieci('plik ucięty (strumień bez końca)')
        wczytano += len(k)
        if wczytano > max_skompr:
            raise BladPliku('plik większy niż dopuszczalny')
        dane = k
        while dane and not d.eof:
            try:
                wyj = d.decompress(dane, MAX_WYJSCIE)
            except zlib.error:
                raise BladPliku('uszkodzony strumień kompresji') from None
            if len(dane) == len(d.unconsumed_tail) and not wyj:
                raise BladPliku('strumień kompresji nie postępuje')
            dane = d.unconsumed_tail
            if wyj:
                crc = zlib.crc32(wyj, crc)
                rozm += len(wyj)
                if rozm > max_rozpak:
                    raise BladPliku('rozpakowana zawartość większa niż dopuszczalna')
                yield wyj
    ogon = d.unused_data
    if flaga & 8:   # deskryptor danych: [PK\x07\x08] CRC, rozmiar skompresowany, rozmiar rozpakowany (32 albo 64 bity)
        while len(ogon) < 24:
            k = odczyt(64)
            if not k:
                break
            ogon += k
        o = ogon[4:] if ogon[:4] == b'PK\x07\x08' else ogon
        if len(o) < 12:
            raise BladSieci('plik ucięty po strumieniu (brak sumy kontrolnej)')
        crc_z = struct.unpack('<I', o[:4])[0]
        rozm_ok = struct.unpack('<I', o[8:12])[0] == rozm & 0xFFFFFFFF or (len(o) >= 20 and struct.unpack('<Q', o[12:20])[0] == rozm)
    else:
        crc_z, rozm_ok = crc_h, rozm_h == rozm & 0xFFFFFFFF
    if crc_z != crc & 0xFFFFFFFF:
        raise BladPliku(f'suma CRC32 niezgodna (plik {crc_z:08x}, odczyt {crc & 0xFFFFFFFF:08x})')
    if not rozm_ok:
        raise BladPliku('rozmiar rozpakowany niezgodny z archiwum')
    strumien_zip.ostatnie_crc = crc & 0xFFFFFFFF


strumien_zip.ostatnie_crc = None


# ---------- wybór portfeli z CSV ----------
def wybierz_usdc_eth(kawalki, min_adresow=MIN_ADRESOW, top_n=TOP_N, min_udzial=MIN_UDZIAL):
    """Kawałki bajtów CSV → {'addr': [top_n adresów małymi literami, od największego], 'kwoty': […], 'udzial': ułamek, 'adresy': liczba adresów USDC w
    sieci Ethereum, 'wierszy': liczba wierszy}. Zestawienie „coin,amount” przed tabelą adresów jest pomijane; nagłówek tabeli MUSI mieć kolumny
    coin, Type, Network, address, amount. Wiersze tego samego adresu sumowane. Błąd zawartości = BladPliku."""
    buf, idx, S, wierszy, zle = b'', None, {}, 0, 0

    def linia(l):
        nonlocal idx, wierszy, zle
        if l.endswith(b'\r'):
            l = l[:-1]
        if idx is None:
            if l.startswith(b'coin,') and b'address' in l:
                kol = [c.strip() for c in next(csv.reader([l.decode('utf-8', 'replace')]))]
                brak = [c for c in NAGLOWEK_KOLUMNY if c not in kol]
                if brak:
                    raise BladPliku('nagłówek bez kolumn: ' + ', '.join(brak))
                idx = {c: kol.index(c) for c in NAGLOWEK_KOLUMNY}
            return
        if b'USDC' not in l:
            return
        w = next(csv.reader([l.decode('utf-8', 'replace')]))
        if len(w) <= max(idx.values()) or w[idx['coin']] != 'USDC' or w[idx['Network']].strip().lower() not in SIEC:
            return
        wierszy += 1
        a = w[idx['address']].strip()
        try:
            x = float(w[idx['amount']])
        except ValueError:
            zle += 1
            return
        if not ADRES_PLIK.match(a) or not x >= 0 or x == float('inf'):
            zle += 1
            return
        a = a.lower()
        S[a] = S.get(a, 0.0) + x

    for k in kawalki:
        buf += k
        czesci = buf.split(b'\n')
        buf = czesci.pop()
        for l in czesci:
            linia(l)
    if buf:
        linia(buf)
    if idx is None:
        raise BladPliku('brak nagłówka tabeli adresów (coin, Type, Network, address, amount)')
    if zle > max(3, MAX_ZLYCH * wierszy):
        raise BladPliku(f'zbyt wiele błędnych wierszy USDC/Ethereum ({zle} z {wierszy})')
    if len(S) < max(min_adresow, top_n):
        raise BladPliku(f'za mało adresów USDC w sieci Ethereum ({len(S)})')
    razem = sum(S.values())
    if razem <= 0:
        raise BladPliku('suma USDC w sieci Ethereum nie jest dodatnia')
    top = sorted(S.items(), key=lambda p: (-p[1], p[0]))[:top_n]
    udzial = sum(x for _, x in top) / razem
    if udzial < min_udzial:
        raise BladPliku(f'10 największych portfeli daje tylko {udzial * 100:.1f} % USDC (wymagane ≥ {min_udzial * 100:.0f} %)')
    if not all(ADRES.match(a) for a, _ in top):
        raise BladPliku('adres poza formatem 0x + 40 znaków szesnastkowych małymi literami')
    return {'addr': [a for a, _ in top], 'kwoty': [x for _, x in top], 'udzial': udzial, 'adresy': len(S), 'wierszy': wierszy}


def czytaj_plik(odczyt, **kw):
    """Cały odczyt jednego pliku: ZIP strumieniowo → wybór portfeli. Zwraca wynik wybierz_usdc_eth + 'crc'. Wynik tylko po pełnym, poprawnym odczycie."""
    w = wybierz_usdc_eth(strumien_zip(odczyt), **kw)
    w['crc'] = f'{strumien_zip.ostatnie_crc:08x}'
    return w


# ---------- sieć ----------
def _otworz(url, bajty=None, timeout=60):
    h = {'User-Agent': UA}
    if bajty:
        h['Range'] = f'bytes=0-{bajty - 1}'
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)


def adres_pliku(d):
    return OKX_URL.format(r=d.year, mm=f'{d.month:02d}', dd=f'{d.day:02d}')


def nazwa_pliku(d):
    return OKX_NAZWA.format(r=d.year, mm=f'{d.month:02d}', dd=f'{d.day:02d}')


def sonda(url, otworz=_otworz):
    """True — plik jest (200/206 z sygnaturą PK); False — „nie ma pliku” (404); None — nie wiadomo (blokada, limit, sieć, strona HTML z kodem 200)."""
    try:
        r = otworz(url, 1024, 15)
        try:
            st, b = getattr(r, 'status', 200), r.read(1024)
        finally:
            getattr(r, 'close', lambda: None)()
    except urllib.error.HTTPError as e:
        return False if e.code == 404 else None
    except Exception:  # noqa — sieć, limit czasu
        return None
    return True if st in (200, 206) and b[:4] == b'PK\x03\x04' else None


def znajdz_nowy(od, dzis, otworz=_otworz, spij=time.sleep):
    """Najnowszy plik z dat od+OKNO_OD_DNI … dzis (od najnowszej, najwyżej OKNO_MAX dat) → (data albo None, 'brak' | 'nie wiadomo' | 'jest' | 'za wcześnie').
    „brak” tylko gdy każda odpowiedź brzmiała „nie ma pliku” (404); jakakolwiek inna = „nie wiadomo”."""
    dni = [od + dt.timedelta(days=i) for i in range(OKNO_OD_DNI, (dzis - od).days + 1)][::-1][:OKNO_MAX]
    if not dni:
        return None, 'za wcześnie'
    niewiadomo = False
    for d in dni:
        spij(PAUZA_S)
        s = sonda(adres_pliku(d), otworz)
        if s is True:
            return d, 'jest'
        if s is None:
            niewiadomo = True
    return None, 'nie wiadomo' if niewiadomo else 'brak'


def czytaj_z_sieci(d, otworz=_otworz, **kw):
    try:
        r = otworz(adres_pliku(d), None, 60)
    except urllib.error.HTTPError as e:
        raise BladSieci(f'HTTP {e.code}') from None
    except Exception as e:  # noqa
        raise BladSieci(type(e).__name__) from None
    try:
        def odczyt(n):
            try:
                return r.read(n)
            except Exception as e:  # noqa — przerwane łączenie, limit czasu gniazda
                raise BladSieci(type(e).__name__) from None
        return czytaj_plik(odczyt, **kw)
    finally:
        getattr(r, 'close', lambda: None)()


def odtworzenie(otworz=_otworz, **kw):
    """Test odtworzenia: z pliku wzorcowego (8.09.2026) musi wyjść dokładnie WZORZEC['adresy'] (jako zbiór). → 'ok'; BladPliku — inny wynik
    (parser nie odtwarza znanej listy); 'brak' — plik wzorcowy usunięty przez giełdę (404; reszta kontroli obowiązuje); BladSieci — nie wiadomo."""
    m = PLIK.match(WZORZEC['plik'])
    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    try:
        w = czytaj_z_sieci(d, otworz, **kw)
    except BladSieci as e:
        if str(e) == 'HTTP 404':
            return 'brak'
        raise
    if sorted(w['addr']) != sorted(WZORZEC['adresy']):
        raise BladPliku('test odtworzenia: z pliku wzorcowego wyszła inna lista niż znana (parser albo format pliku się zmienił)')
    return 'ok'


# ---------- lista i stan ----------
def poprawna_lista(j, dzis=None):
    """Plik konfig/wh_listy.json → rekord OKX albo None (każdy błąd = None). Te same zasady co wartownik w zbieraj_dane.py."""
    try:
        if not isinstance(j, dict) or j.get('v') != 1 or not isinstance(j.get('OKX'), dict):
            return None
        o = j['OKX']
        m = PLIK.match(o.get('plik') if isinstance(o.get('plik'), str) else '')
        s = o.get('since')
        if not m or not isinstance(s, str) or not DATA.match(s) or s != f'{m.group(1)}-{m.group(2)}-{m.group(3)}':
            return None
        d = dt.date.fromisoformat(s)
        if dzis is not None and d > dzis + dt.timedelta(days=1):
            return None
        a = o.get('addr')
        if not isinstance(a, list) or len(a) != TOP_N or len(set(a)) != TOP_N or not all(isinstance(x, str) and ADRES.match(x) for x in a):
            return None
        u = o.get('udzial')
        if isinstance(u, bool) or not isinstance(u, (int, float)) or not MIN_UDZIAL <= u <= 1:
            return None
        return o
    except (ValueError, TypeError, AttributeError):
        return None


def _wczytaj(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _zapisz(p, j):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    t = p + '.tmp'
    with open(t, 'w', encoding='utf-8') as f:
        json.dump(j, f, ensure_ascii=False, indent=1, sort_keys=False)
        f.write('\n')
    os.replace(t, p)


def uruchom(lista_p=LISTA_PLIK, stan_p=STAN_PLIK, dzis=None, otworz=_otworz, spij=time.sleep, **kw):
    """Jeden przebieg: szukaj → (odtworzenie → odczyt → kontrole) → zapis listy; stan zawsze. Zwraca krótki opis do dziennika. Nie rzuca wyjątków sieci."""
    dzis = dzis or dt.datetime.now(dt.timezone.utc).date()
    iso = dzis.isoformat()
    stan = _wczytaj(stan_p)
    stan = stan if isinstance(stan, dict) else {}
    ob = poprawna_lista(_wczytaj(lista_p), dzis)
    since = ob['since'] if ob else WZORZEC['since']
    od = dt.date.fromisoformat(since)
    S = {'v': 1, 'sprawdzono': iso, 'ostatnie_ok': stan.get('ostatnie_ok'), 'blad': None, 'blad_od': None, 'lista_od': since,
         'nowy': None, 'odrzucony': stan.get('odrzucony') if isinstance(stan.get('odrzucony'), dict) else None, 'odtworzenie': stan.get('odtworzenie')}
    wynik = 'brak nowszego pliku'
    try:
        d, st = znajdz_nowy(od, dzis, otworz, spij)
        if st == 'nie wiadomo':
            raise BladSieci('serwer nie odpowiada plikiem (blokada, limit albo błąd sieci)')
        if d is None:
            S['ostatnie_ok'] = iso
            wynik = 'brak nowszego pliku' if st == 'brak' else 'za wcześnie na nowy plik'
        else:
            S['nowy'] = d.isoformat()
            plik = nazwa_pliku(d)
            odr = S['odrzucony']
            if odr and odr.get('plik') == plik and DATA.match(str(odr.get('dnia'))) \
                    and (dzis - dt.date.fromisoformat(odr['dnia'])).days < PONOWNIE_PO_DNIACH:
                raise BladPliku(f'plik {plik} odrzucony wcześniej ({odr.get("dnia")}): ' + str(odr.get('powod')))
            try:
                S['odtworzenie'] = odtworzenie(otworz, **kw)
                w = czytaj_z_sieci(d, otworz, **kw)
            except BladPliku as e:
                S['odrzucony'] = {'plik': plik, 'dnia': iso, 'powod': str(e)[:160]}
                raise
            _zapisz(lista_p, {'v': 1, 'OKX': {'since': d.isoformat(), 'plik': plik, 'n': len(w['addr']), 'udzial': round(w['udzial'], 4),
                                              'adresy_w_pliku': w['adresy'], 'crc': w['crc'], 'zapisano': iso, 'addr': w['addr']}})
            S.update({'ostatnie_ok': iso, 'lista_od': d.isoformat(), 'nowy': None, 'odrzucony': None})
            wynik = f'lista OKX odświeżona: plik {plik}, udział 10 portfeli {w["udzial"] * 100:.1f} %, test odtworzenia: {S["odtworzenie"]}'
    except (BladPliku, BladSieci) as e:
        S['blad'] = str(e)[:160]
        S['blad_od'] = stan.get('blad_od') if DATA.match(str(stan.get('blad_od'))) else iso   # trwa od pierwszego dnia z rzędu
        wynik = ('plik odrzucony przy kontroli: ' if isinstance(e, BladPliku) else 'brak odpowiedzi: ') + S['blad']
    except Exception as e:  # noqa — nic nie może zatrzymać przepływu; ślad w stanie
        S['blad'] = type(e).__name__
        S['blad_od'] = stan.get('blad_od') if DATA.match(str(stan.get('blad_od'))) else iso
        wynik = 'nieoczekiwany błąd: ' + type(e).__name__
    _zapisz(stan_p, S)
    return wynik


def main(argv):
    if len(argv) != 1:
        print('użycie: wh_lista.py (bez argumentów)')
        return 2
    print('Listy portfeli giełd (OKX):', uruchom())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))   # v477b: main() oczekuje pełnego argv (nazwa skryptu); wcześniej sys.argv[1:] dawało puste argv → kod 2 przy każdym uruchomieniu
