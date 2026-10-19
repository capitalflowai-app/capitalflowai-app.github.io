#!/usr/bin/env python3
"""v478 (19.10.2026): samodzielne odświeżanie list portfeli giełd z miesięcznych raportów dowodu rezerw (Bybit, KuCoin).

Dotąd nowa lista wymagała człowieka z Claude (kontrola pisała „napisz do Claude”). Ten skrypt robi to sam, ostrożnie:
  * Bybit: szuka nowszego pliku Bybit_PoR_Audit_RRRR_Mmm_DD.pdf (jak kontrola: Range 1 KB, podpis %PDF; 403 inne niż AmazonS3 = „nie wiadomo”,
    blokady nie obchodzi, lista zostaje); KuCoin: link do PDF tylko z pola auditReportUrl publicznego API (puste = raport jeszcze niedostępny).
  * PDF czyta pypdf (przypięta wersja instalowana TYLKO w przepływie wh_listy_pdf.yml; zbieracz zostaje na bibliotece standardowej): tekst, ligatury
    ﬀ/ﬁ/ﬂ/ﬃ/ﬄ zamienione przed wyszukaniem adresów 0x[0-9a-f]{40}, adresy małymi literami.
  * Test odtworzenia: ten sam parser musi z PDF-a OBECNEJ listy dać identyczny zbiór adresów — inaczej nowa lista nie jest przyjęta.
  * Nowa lista przyjęta tylko gdy: data nowsza od obecnej, liczba w przedziale (Bybit 100–400, KuCoin 20–100), bez duplikatów i adresów zepsutych,
    co najmniej 90% starych adresów zostaje (06.10: 108 ze 108).
  * Wynik trafia do osobnego pliku konfig/wh_listy_pdf.json ({"v": 1, "Bybit": {since, url, addr, n, zapisano}, "KuCoin": {…}}; zbieracz nakłada go na listy
    wbudowane — wh_konfig_nalozone w zbieraj_dane.py; osobny plik = niezależny od przepływu listy OKX); stan przebiegu (status i powód każdej giełdy) w
    konfig/wh_listy_pdf_stan.json — przy porażce lista zostaje, a powód pokazuje kontrola. Cudzych kluczy pliku skrypt nie rusza.
Użycie: python3 narzedzia/wh_listy_auto.py [--sucho]   (z katalogu głównego repozytorium; --sucho = bez zapisu pliku)
Kod wyjścia: 0 (także gdy źródło milczy); 1 tylko przy awarii samego skryptu."""
import datetime as dt
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

KONFIG = os.environ.get('WH_PDF_PLIK') or 'konfig/wh_listy_pdf.json'
STAN = os.environ.get('WH_STAN_PDF_PLIK') or 'konfig/wh_listy_pdf_stan.json'
PRZEDZIALY = {'Bybit': (100, 400), 'KuCoin': (20, 100)}   # liczba portfeli w sieci Ethereum (obecnie 122 i 33)
PROG_STARE = 0.90          # tyle starych adresów musi zostać na nowej liście
MAX_PDF = 15_000_000       # bajtów
MAX_STRON = 400
UA = 'CapitalFlowAI-collector/1.0'
KU_API = 'https://www.kucoin.com/_api/asset-front/proof-of-reserves/asset-reserve'
BYBIT_URL = 'https://www.bybit.com/common-static/cht-static/por/Bybit_PoR_Audit_{r}_{mies}_{dd}.pdf'
MIES_EN = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
OD_DNI = 20                # nowszego raportu Bybit szukamy od tylu dni po dacie obecnej listy (raporty miesięczne)
MAX_DAT = 30               # najwyżej tyle dat, od najnowszej
PAUZA_S = 0.3
TOLERANCJA_DNI = 7         # data w stopce PDF a data z nazwy pliku (Bybit) albo z API (KuCoin)
LIGATURY = {'ﬀ': 'ff', 'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬃ': 'ffi', 'ﬄ': 'ffl'}
PROFILE = ('wiersze', 'wszystkie')   # „wiersze”: tabela „Network Address”, tylko wiersze sieci Ethereum; „wszystkie”: każdy adres 0x… w dokumencie
RE_ADRES = re.compile(r'(?<![0-9A-Za-z])0x[0-9a-fA-F]{40}(?![0-9A-Za-z])')
RE_WIERSZ = re.compile(r'(?<![0-9A-Za-z])(?:Ethereum|ETH|ERC-?20)\s+(0x[0-9A-Za-z]*)')
RE_ADRES_PELNY = re.compile(r'0x[0-9a-fA-F]{40}')
RE_STOPKA = re.compile(r'Proof\s+of\s+Reserves\s+(\d{4})/(\d{2})/(\d{2})')


# ---------------------------------------------------------------------------------------------------------------- sieć
def http(url, timeout=30, headers=None, limit=None):
    """GET z identyfikatorem zbieracza → (status, treść, adres końcowy, nagłówki); limit = najwyżej tyle bajtów."""
    req = urllib.request.Request(url, headers={'User-Agent': UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, (r.read() if limit is None else r.read(limit)), r.geturl(), r.headers


class Siec:
    """Wszystko, co dotyka sieci i biblioteki PDF — w testach zastępowane zaślepką o tych samych metodach."""

    def plik_jest(self, url):
        """True — plik PDF odpowiada (200/206 z podpisem %PDF); False — „nie ma pliku” (404 albo 403 ze stroną brakującego pliku, Server: AmazonS3);
        None — nie wiadomo (blokada, limit, sieć, strona HTML z kodem 200). Blokady nie obchodzimy."""
        try:
            st, body, _, _ = http(url, 10, {'Range': 'bytes=0-1023'}, 1024)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return False
            if e.code == 403:
                srv = (e.headers.get('Server') if e.headers is not None and hasattr(e.headers, 'get') else None) or ''
                return False if 'AmazonS3' in str(srv) else None
            return None
        except Exception:  # noqa — sieć, limit czasu
            return None
        return True if st in (200, 206) and bytes(body[:4]) == b'%PDF' else None

    def pdf(self, url):
        if not isinstance(url, str) or not url.startswith('https://'):
            raise ValueError('adres raportu nie jest https')
        st, body, koniec, _ = http(url, 90, None, MAX_PDF + 1)
        if not str(koniec).startswith('https://'):
            raise ValueError('przekierowanie poza https')
        if st != 200 or len(body) > MAX_PDF or bytes(body[:4]) != b'%PDF':
            raise ValueError(f'to nie jest PDF do {MAX_PDF // 1_000_000} MB (kod {st}, {len(body)} B)')
        return bytes(body)

    def tekst(self, dane):
        """Tekst PDF-a (pypdf — instalowany tylko w przepływie wh_listy_pdf.yml)."""
        try:
            import pypdf
            r = pypdf.PdfReader(io.BytesIO(dane))
            if len(r.pages) > MAX_STRON:
                raise ValueError(f'za dużo stron ({len(r.pages)})')
            return '\n'.join((p.extract_text() or '') for p in r.pages)
        except ValueError:
            raise
        except Exception as e:  # noqa
            raise ValueError(f'PDF nieczytelny ({type(e).__name__})') from None

    def ku_api(self):
        st, body, _, _ = http(KU_API, 20)
        j = json.loads(body)
        d = j.get('data') if isinstance(j, dict) else None
        if st != 200 or not isinstance(d, dict):
            raise ValueError('odpowiedź API bez pola data')
        return d


# ------------------------------------------------------------------------------------------------------------- parser
def wyciagnij(tekst, profil):
    """Tekst PDF → (adresy małymi literami w kolejności, liczba duplikatów, liczba adresów zepsutych, adresy odczytane dopiero po zamianie ligatur).
    Ligatury zamieniane PRZED wyszukaniem (w PDF-ach giełd „ﬀ” siedzi w środku adresu: 0xaa…34ﬀ1b…). Zepsuty = wiersz sieci Ethereum z adresem
    krótszym/dłuższym niż 40 znaków."""
    t0 = str(tekst or '')
    t = t0
    for a, b in LIGATURY.items():
        t = t.replace(a, b)
    zle = 0
    if profil == 'wiersze':
        kand = []
        for m in RE_WIERSZ.finditer(t):
            if RE_ADRES_PELNY.fullmatch(m.group(1)):
                kand.append(m.group(1))
            else:
                zle += 1
    elif profil == 'wszystkie':
        kand = RE_ADRES.findall(t)
    else:
        raise ValueError('nieznany profil ' + str(profil))
    bez_lig = set(a.lower() for a in (RE_ADRES.findall(t0) if profil == 'wszystkie' else
                                      [m.group(1) for m in RE_WIERSZ.finditer(t0) if RE_ADRES_PELNY.fullmatch(m.group(1))]))
    wyn, widziane, dup = [], set(), 0
    for a in kand:
        a = a.lower()
        if a in widziane:
            dup += 1
        else:
            widziane.add(a)
            wyn.append(a)
    return wyn, dup, zle, [a for a in wyn if a not in bez_lig]


def dobierz_profil(tekst_obecny, addr_obecne):
    """Test odtworzenia: który profil parsera daje z PDF-a obecnej listy dokładnie ten sam zbiór adresów? → (profil albo None, opis liczb).
    Jedyny dopuszczony wyjątek: parser znajduje DODATKOWE adresy, które w tekście PDF mają ligaturę (KuCoin 31.08.2026: lista z v108 pominęła 5 takich
    adresów, bo wtedy ligatur nie zamieniano; Bybit od v230 jest kompletny) — wtedy wszystkie obecne adresy muszą być znalezione."""
    cel, opis = set(a.lower() for a in addr_obecne), []
    for p in PROFILE:
        a, dup, zle, lig = wyciagnij(tekst_obecny, p)
        if zle == 0 and dup == 0 and set(a) == cel and len(a) == len(addr_obecne):
            return p, None
        if zle == 0 and dup == 0 and cel < set(a) and set(a) - cel <= set(lig):
            return p, None
        opis.append(f'{p}: {len(a)} adresów, wspólnych {len(set(a) & cel)} z {len(cel)}' + (f', duplikatów {dup}' if dup else '') + (f', zepsutych {zle}' if zle else ''))
    return None, '; '.join(opis)


def waliduj(g, stare, nowe, dup, zle, nowa_data, stara_data):
    """Warunki przyjęcia nowej listy → None (przyjęta) albo powód odrzucenia (po polsku, krótko)."""
    try:
        if not dt.date.fromisoformat(nowa_data) > dt.date.fromisoformat(stara_data):
            return f'data raportu {nowa_data} nie jest nowsza od obecnej {stara_data}'
    except (TypeError, ValueError):
        return f'nieczytelna data raportu ({nowa_data!r} albo {stara_data!r})'
    lo, hi = PRZEDZIALY[g]
    if zle:
        return f'{zle} adresów o złej długości w tabeli'
    if dup:
        return f'duplikaty adresów w tabeli ({dup})'
    if not all(RE_ADRES_PELNY.fullmatch(a) and a == a.lower() for a in nowe):
        return 'adres w złym formacie'
    if len(nowe) != len(set(nowe)):
        return 'duplikaty adresów'
    if not lo <= len(nowe) <= hi:
        return f'liczba portfeli {len(nowe)} poza przedziałem {lo}–{hi}'
    st = set(stare)
    zostaje = len(st & set(nowe))
    if st and zostaje < PROG_STARE * len(st):
        return f'z {len(st)} dotychczasowych adresów zostaje tylko {zostaje} (próg {int(PROG_STARE * 100)}%)'
    return None


def data_stopki(tekst):
    """Data stanu z stopki raportu („… Proof of Reserves 2026/08/31”) → ISO albo None."""
    m = RE_STOPKA.search(re.sub(r'\s+', ' ', str(tekst or '')))
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
    except ValueError:
        return None


# -------------------------------------------------------------------------------------------------- szukanie raportów
def adresy_bybit(d):
    dd = [f'{d.day:02d}'] + ([str(d.day)] if d.day < 10 else [])
    return [BYBIT_URL.format(r=d.year, mies=MIES_EN[d.month - 1], dd=x) for x in dd]


def szukaj_bybit(cur, dzis, io_, spij=time.sleep):
    """→ ('znaleziono', data ISO, adres) albo (status, powód)."""
    od = dt.date.fromisoformat(cur['since'])
    ku = cur['url'] if isinstance(cur.get('url'), str) and cur['url'].startswith('https://') else adresy_bybit(od)[0]
    dni = [od + dt.timedelta(days=i) for i in range(OD_DNI, (dzis - od).days + 1)][::-1][:MAX_DAT]
    if not dni:
        return 'brak', f'raport miesięczny — sprawdzanie od {(od + dt.timedelta(days=OD_DNI)).isoformat()}'
    if io_.plik_jest(ku) is not True:
        return 'nie_wiadomo', 'plik obecnej listy nie odpowiada plikiem (możliwa blokada serwera) — nic nie zmieniono'
    niejasne = 0
    for d in dni:
        spij(PAUZA_S)
        wyn = []
        for u in adresy_bybit(d):
            wyn.append(io_.plik_jest(u))
            if wyn[-1] is True:
                return 'znaleziono', d.isoformat(), u
        if None in wyn:
            niejasne += 1
    if niejasne:
        return 'nie_wiadomo', f'brak nowszego raportu w dniach z jasną odpowiedzią; dni bez jasnej odpowiedzi: {niejasne}'
    return 'brak', f'brak nowszego niż {cur["since"]}'


def szukaj_kucoin(cur, io_):
    od = dt.date.fromisoformat(cur['since'])
    try:
        d = io_.ku_api()
        ms = d.get('latestAuditDate')
        if not isinstance(ms, (int, float)) or isinstance(ms, bool):
            raise ValueError('brak daty audytu')
        a = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()
    except Exception as e:  # noqa
        return 'nie_wiadomo', f'API giełdy nie odpowiada jasno ({type(e).__name__})'
    if a <= od:
        return 'brak', f'brak nowszego audytu niż {cur["since"]}'
    u = d.get('auditReportUrl')
    if not isinstance(u, str) or not u.strip():
        return 'czeka', f'audyt z {a.isoformat()} jest, link do raportu jeszcze niepodany'
    if u == cur.get('url'):
        return 'czeka', f'audyt z {a.isoformat()}, ale link do raportu bez zmiany'
    return 'znaleziono', a.isoformat(), u.strip()


# --------------------------------------------------------------------------------------------------------- jedna giełda
def odswiez_gielde(g, cur, dzis, io_, spij=time.sleep):
    """→ {'status', 'powod', 'wpis'}; status: ok (nowa lista przyjęta, wpis = {since, url, addr}), brak, czeka, nie_wiadomo, odrzucona, blad."""
    try:
        r = szukaj_bybit(cur, dzis, io_, spij) if g == 'Bybit' else szukaj_kucoin(cur, io_)
        if r[0] != 'znaleziono':
            return {'status': r[0], 'powod': r[1], 'wpis': None}
        data_audytu, url = r[1], r[2]
        stare = [a.lower() for a in cur['addr']]
        try:
            t_nowy = io_.tekst(io_.pdf(url))
            t_obecny = io_.tekst(io_.pdf(cur['url']))
        except Exception as e:  # noqa — brak pobrania albo odczytu: nic nie zmieniamy, ale to nie „błąd skryptu”
            return {'status': 'nie_wiadomo', 'powod': f'nie udało się pobrać albo odczytać PDF ({str(e)[:90]})', 'wpis': None}
        profil, opis = dobierz_profil(t_obecny, stare)
        if profil is None:
            return {'status': 'odrzucona', 'powod': f'parser nie odtwarza obecnej listy z jej PDF ({opis})', 'wpis': None}
        data = data_audytu
        ds = data_stopki(t_nowy)   # data stanu ze stopki raportu: musi zgadzać się z datą z nazwy pliku (Bybit) albo z API (KuCoin)
        if ds:
            if abs((dt.date.fromisoformat(ds) - dt.date.fromisoformat(data_audytu)).days) > TOLERANCJA_DNI:
                return {'status': 'odrzucona', 'powod': f'data w PDF {ds} rozjeżdża się z datą raportu {data_audytu}', 'wpis': None}
            data = ds
        nowe, dup, zle, _ = wyciagnij(t_nowy, profil)
        powod = waliduj(g, stare, nowe, dup, zle, data, cur['since'])
        if powod:
            return {'status': 'odrzucona', 'powod': powod + f' (raport z {data})', 'wpis': None}
        return {'status': 'ok', 'powod': f'nowa lista z {data}: {len(nowe)} portfeli (było {len(stare)})', 'wpis': {'since': data, 'url': url, 'addr': sorted(nowe)}}
    except Exception as e:  # noqa
        return {'status': 'blad', 'powod': f'wyjątek {type(e).__name__}: {str(e)[:90]}', 'wpis': None}


# ------------------------------------------------------------------------------------------------------------- plik
def wczytaj(sciezka):
    try:
        with open(sciezka, encoding='utf-8') as f:
            j = json.load(f)
        if isinstance(j, dict):
            return j
    except (OSError, ValueError):
        pass
    return {}


def zapisz(sciezka, cfg):
    """Zapis atomowy; zwraca True, gdy treść pliku się zmieniła (plik zmienia się najwyżej raz na dobę — w wyniku jest tylko dzień)."""
    tekst = json.dumps(cfg, ensure_ascii=False, indent=1, sort_keys=True) + '\n'
    try:
        with open(sciezka, encoding='utf-8') as f:
            if f.read() == tekst:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(os.path.abspath(sciezka)), exist_ok=True)
    tmp = sciezka + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(tekst)
    os.replace(tmp, sciezka)
    return True


def uruchom(biezace, dzis, io_=None, sciezka=KONFIG, spij=time.sleep, zapis=True, stan_sciezka=STAN):
    """biezace = {giełda: {'since', 'url', 'addr'}} (obecne listy, już z nałożonym plikiem) → {giełda: wynik}. Plik list zmienia się tylko po przyjęciu nowej listy
    (cudzych kluczy nie rusza); stan przebiegu (dzień, status, powód każdej giełdy) zapisywany zawsze."""
    io_ = io_ or Siec()
    cfg, stan = wczytaj(sciezka), wczytaj(stan_sciezka)
    wyniki, zmiana = {}, False
    stan['v'] = 1
    for g in PRZEDZIALY:
        cur = biezace.get(g)
        if not isinstance(cur, dict):
            wyniki[g] = {'status': 'blad', 'powod': 'brak obecnej listy', 'wpis': None}
        else:
            wyniki[g] = odswiez_gielde(g, cur, dzis, io_, spij)
        w = wyniki[g]
        if w['status'] == 'ok':
            cfg[g] = {**w['wpis'], 'n': len(w['wpis']['addr']), 'zapisano': dzis.isoformat()}
            zmiana = True
        stan[g] = {'dzien': dzis.isoformat(), 'status': w['status'], 'powod': w['powod'][:300]}
    if zapis:
        if zmiana:
            cfg['v'] = 1
            zapisz(sciezka, cfg)
        zapisz(stan_sciezka, stan)
    return wyniki


def main(argv):
    sys.path.insert(0, os.getcwd())
    import zbieraj_dane as zd   # obecne listy = wbudowane z nałożonym plikiem konfig/wh_listy_pdf.json
    dzis = dt.datetime.now(dt.timezone.utc).date()
    wyniki = uruchom({g: zd.WH_GIELDY.get(g) for g in PRZEDZIALY}, dzis, zapis='--sucho' not in argv)
    for g, w in wyniki.items():
        print(f'{g}: {w["status"]} — {w["powod"]}')
        if w['status'] in ('odrzucona', 'blad'):
            print(f'::warning title=lista portfeli {g}::{w["status"]} — {w["powod"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
