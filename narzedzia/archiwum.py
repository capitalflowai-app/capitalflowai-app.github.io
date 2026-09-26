#!/usr/bin/env python3
"""Własne archiwum danych CapitalFlowAI (v113, część B zadania z 26.09.2026) — raz dziennie ok. 00:20 UTC z GitHub Actions.

Repozytorium jest publiczne, więc w archiwum są tylko (1) nasze własne wyliczenia z danych publicznych i (2) dane z domeny publicznej
albo otwartych licencji: łańcuch Ethereum (odczyt własny), FRED (serie Rady Gubernatorów Fed), U.S. Treasury (TIC, rentowności),
CFTC, Deutsche Bundesbank. Żadnych danych z API osobistych ani od dostawców z własnymi warunkami (CoinGecko, SoSoValue, CoinPaprika,
Coin Metrics, Finnhub, Twelve Data, CoinMarketCap, giełdy, Tiingo, Massive, EODHD, FMP, Alpha Vantage, Etherscan, CryptoPanic).

Pliki CSV (UTF-8, przecinek, kropka dziesiętna, nagłówek po angielsku bez polskich znaków) w katalogu `archiwum/`:
  wieloryby.csv        dzień × giełda × aktywo — salda ogłoszonych portfeli giełd (z data/wieloryby.json, wyliczenie własne v105–v112)
  stablecoiny-eth.csv  dzień × token — własny odczyt totalSupply() USDT i USDC w sieci Ethereum (tylko ta sieć)
  plynnosc.csv         dzień — FRED WALCL, WTREGEN (TGA), RRPONTSYD; net = WALCL − TGA − RRP; serie tygodniowe przenoszone do przodu (kolumna method)
  tic.csv              miesiąc × kraj — TIC SLT tabela 1 (zagranica kupuje papiery USA) i tabela 2 (USA kupują papiery zagraniczne), od 2020-01
  cftc-krypto.csv      tydzień × kontrakt × grupa — CFTC COT (TFF, futures-only) BTC i ETH na CME, 2 lata
  rentownosci.csv      dzień — rentowność 10-letnia USA (Skarb USA) i Niemiec (Bundesbank) oraz różnica, 2 lata
Zasady: operacja idempotentna (jeden wiersz na klucz; ponowne uruchomienie tego samego dnia nadpisuje ten sam dzień); brak danych
danego dnia = brak wiersza, nigdy zero; rewizje (np. FRED) nadpisywane najnowszą wartością i zliczane w `archiwum/indeks.json`.
Każde źródło osobno: awaria jednego nie blokuje pozostałych; kod wyjścia 1 gdy którekolwiek zawiodło (e-mail z GitHuba).
Python 3.12, biblioteka standardowa; parsery wspólne ze zbieraczem (import zbieraj_dane)."""
import csv
import datetime
import io
import json
import os
import sys
import time
import urllib.error
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import zbieraj_dane as zd  # noqa: E402 — parsery, adresy źródeł, maskowanie kluczy

ARCH = os.environ.get('ARCHIWUM_DIR', os.path.join(ROOT, 'archiwum'))
SITE = os.environ.get('SITE_URL', 'https://capitalflowai-app.github.io').rstrip('/')
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
TODAY = NOW.date()
CREDIT = 'Archiwum własne CapitalFlowAI'

# nazwa → plik, kolumny, kolumny klucza (jeden wiersz na klucz), lata wstecz przy pierwszym zasileniu (None = od dziś), źródło bazowe
FILES = {
    'wieloryby': {'file': 'wieloryby.csv', 'cols': ['date', 'exchange', 'asset', 'balance', 'balance_usd', 'inflow_24h', 'outflow_24h', 'net_24h', 'block'],
                  'key': ['date', 'exchange', 'asset'], 'back': None,
                  'src': 'Obliczenia własne z publicznego łańcucha Ethereum (salda ogłoszonych portfeli giełd; przepływy = suma przelewów ≥ 1 mln USD z pełnej doby UTC poprzedzającej datę wiersza)'},
    'stablecoiny-eth': {'file': 'stablecoiny-eth.csv', 'cols': ['date', 'token', 'total_supply'], 'key': ['date', 'token'], 'back': None,
                        'src': 'Odczyt własny totalSupply() USDT i USDC przez publiczny węzeł JSON-RPC — tylko sieć Ethereum'},
    'plynnosc': {'file': 'plynnosc.csv', 'cols': ['date', 'walcl_musd', 'tga_musd', 'rrp_musd', 'net_liquidity_musd', 'method'], 'key': ['date'], 'back': 3,
                 'src': 'Source: Federal Reserve, via FRED (WALCL, WTREGEN, RRPONTSYD); net = WALCL − TGA − RRP, obliczenie własne'},
    'tic': {'file': 'tic.csv', 'cols': ['month', 'country', 'net_flow_musd', 'table'], 'key': ['month', 'country', 'table'], 'back': None,
            'src': 'U.S. Department of the Treasury — Treasury International Capital (TIC), SLT tabele 1 i 2 (domena publiczna)'},
    'cftc-krypto': {'file': 'cftc-krypto.csv', 'cols': ['date', 'contract', 'group', 'long', 'short', 'net'], 'key': ['date', 'contract', 'group'], 'back': 2,
                    'src': 'CFTC — Commitments of Traders, Traders in Financial Futures (futures-only), BTC i ETH na CME (domena publiczna)'},
    'rentownosci': {'file': 'rentownosci.csv', 'cols': ['date', 'ust10y', 'bund10y', 'spread'], 'key': ['date'], 'back': 2,
                    'src': 'U.S. Department of the Treasury (krzywa rentowności, 10 lat) i Deutsche Bundesbank (rentowność 10-letnia, BBSIS)'},
}
TIC_OD = '2020-01'
STABLE = {'USDT': zd.WH_USDT, 'USDC': zd.WH_USDC}   # oba po 6 miejsc
FRED_OBS = 'https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={key}&file_type=json&observation_start={od}&sort_order=asc'


def lata_wstecz(d, n):
    """Ten sam dzień n lat wcześniej (29 lutego → 28 lutego)."""
    try:
        return d.replace(year=d.year - n)
    except ValueError:
        return d.replace(year=d.year - n, day=28)


def fmt(v):
    """Wartość do CSV: brak → puste pole (nigdy 0); liczby z kropką, bez zbędnych zer; teksty bez zmian."""
    if v is None:
        return ''
    if isinstance(v, bool):
        return str(v).lower()
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v != v or v in (float('inf'), float('-inf')):
            return ''
        s = repr(v)   # najkrótszy zapis, który wraca do tej samej liczby (88304342264.55, nie 88304342264.550003)
        if 'e' in s or 'E' in s:
            s = ('%.6f' % v).rstrip('0').rstrip('.')
        elif s.endswith('.0'):
            s = s[:-2]
        return s if s not in ('', '-0') else '0'
    return str(v)


def read_csv(path, cols):
    """Istniejący plik → {klucz: wiersz (lista tekstów)}; brak pliku albo inny nagłówek = pusto (nagłówek jest częścią umowy)."""
    if not os.path.exists(path):
        return {}, None
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        head = next(r, None)
        if head != cols:
            return {}, f'nagłówek {head} ≠ {cols} — plik zapisany od nowa'
        return {tuple(row): row for row in r if len(row) == len(cols)}, None


def merge(old, new_rows, cols, key):
    """Stare i nowe wiersze → (wiersze wg klucza, dodane, zrewidowane). Nowy wiersz z tym samym kluczem nadpisuje stary (rewizja
    liczona, gdy zmieniła się choć jedna wartość). Wiersze spoza tego przebiegu zostają (archiwum rośnie, nigdy nie kurczy)."""
    ki = [cols.index(k) for k in key]
    out = {tuple(row[i] for i in ki): row for row in old.values()}
    added = revised = 0
    for row in new_rows:
        row = [fmt(v) for v in row]
        if len(row) != len(cols):
            raise ValueError(f'wiersz ma {len(row)} pól, kolumn jest {len(cols)}')
        k = tuple(row[i] for i in ki)
        if k in out:
            if out[k] != row:
                revised += 1; out[k] = row
        else:
            added += 1; out[k] = row
    return out, added, revised


def write_csv(path, cols, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(cols)
        for k in sorted(rows):
            w.writerow(rows[k])


# ------------------------------------------------------------------ źródła: każde zwraca listę wierszy (listy wartości) ------------
def src_wieloryby(today=None):
    """data/wieloryby.json ze strony (obliczenie własne z łańcucha): saldo każdej giełdy w ETH/USDT/USDC z ostatniego bloku,
    saldo w USD po kursie z pliku, przepływy = sumy dobowe zbieracza (`dobowe`, pełna lista przelewów ≥ 1 mln USD, nie obcięta tabela)
    za pełną dobę UTC poprzedzającą datę wiersza (zapis o 00:20). Dzień bez sum albo część bez odpowiedzi (ok=False) = pole puste,
    nie zero; giełda bez tokena na liście = bez wiersza."""
    today = today or TODAY
    d = zd.get_json(f'{SITE}/data/wieloryby.json?t={int(time.time())}', timeout=60)
    salda, gieldy, ok = d.get('salda') or {}, d.get('gieldy') or {}, d.get('ok') or {}
    if not isinstance(salda, dict) or not salda:
        raise RuntimeError('plik wielorybów bez sald')
    px = d.get('eth_usd') if isinstance(d.get('eth_usd'), (int, float)) and d.get('eth_usd') > 0 else None
    wczoraj = (today - datetime.timedelta(days=1)).isoformat()
    dob = (d.get('dobowe') or {}).get(wczoraj) if isinstance(d.get('dobowe'), dict) else None
    od = str(d.get('dobowe_od') or '')[:10]
    if not isinstance(dob, dict):
        dob = None; NOTES.append(f'brak sum dobowych za {wczoraj} — przepływy puste')
    elif not od or od >= wczoraj:   # zbieranie sum zaczęło się w tej dobie (albo później) — doba niepełna, nie udajemy pełnej
        dob = None; NOTES.append(f'sumy dobowe zbierane od {od or "?"} — doba {wczoraj} niepełna, przepływy puste')
    # v118.1: doba jest pełna tylko, gdy skan przekroczył północ UTC: stablecoiny — ostatni zeskanowany blok (ostatni_t) już dziś i bez luki;
    # ETH — najstarszy odczyt portfela (czas głowicy − lag_min) też już dziś (portfele w rotacji ~80 min). Inaczej pola puste, z uwagą.
    polnoc = datetime.datetime(today.year, today.month, today.day, tzinfo=datetime.timezone.utc)
    try:
        ost = datetime.datetime.fromisoformat(str(d.get('ostatni_t')))
        cov_stab = ost >= polnoc and not d.get('luka')
    except Exception:
        cov_stab = False
    try:
        e = d.get('eth') or {}
        cov_eth = datetime.datetime.fromisoformat(str(d.get('blk_t'))) - datetime.timedelta(minutes=float(e.get('lag_min'))) >= polnoc
    except Exception:
        cov_eth = False
    if dob is not None and not cov_stab:
        NOTES.append(f'doba {wczoraj}: skan USDT/USDC nie sięga północy (ostatni blok {str(d.get("ostatni_t"))[:16]}) — przepływy USDT/USDC puste')
    if dob is not None and not cov_eth:
        NOTES.append(f'doba {wczoraj}: rotacja portfeli ETH nie objęła całej doby — przepływy ETH puste')
    flows_ok = {'USDT': ok.get('transfery') is True and cov_stab, 'USDC': ok.get('transfery') is True and cov_stab, 'ETH': ok.get('eth') is True and cov_eth}
    rows = []
    for g, s in salda.items():
        if not isinstance(s, dict):
            continue
        toks = (gieldy.get(g) or {}).get('tokeny') or ['USDT', 'USDC', 'ETH']
        for asset, fld in (('ETH', 'eth'), ('USDT', 'usdt'), ('USDC', 'usdc')):
            if asset not in toks or not isinstance(s.get(fld), (int, float)):
                continue
            bal = float(s[fld])
            usd = (None if px is None else round(bal * px, 2)) if asset == 'ETH' else round(bal, 2)   # ETH bez kursu = brak, nie zero
            ds = (dob.get(g) or {}).get(asset) if dob else None   # sumy dobowe tej giełdy i aktywa (nie nadpisywać `s` = salda giełdy)
            if flows_ok[asset] and dob is not None:   # doba obserwowana: giełda/aktywo bez wpisu = 0 dużych przelewów (zmierzone), nie brak
                inn = round(float(ds['in']), 2) if isinstance(ds, dict) else 0.0
                out = round(float(ds['out']), 2) if isinstance(ds, dict) else 0.0
                net = round(inn - out, 2)
            else:
                inn = out = net = None
            rows.append([today.isoformat(), g, asset, round(bal, 6), usd, inn, out, net, s.get('blk') if isinstance(s.get('blk'), int) else None])
    if not rows:
        raise RuntimeError('żadna giełda bez salda w pliku')
    return rows


def src_stable(today=None):
    """totalSupply() USDT i USDC z publicznego węzła (jedno żądanie zbiorcze); wynik bez liczby = brak wiersza tokena."""
    today = today or TODAY
    calls = [('eth_call', [{'to': a, 'data': '0x18160ddd'}, 'latest']) for a in STABLE.values()]
    res = zd.wh_rpc(calls, termin=time.monotonic() + 40)
    rows = []
    for (tok, _), r in zip(STABLE.items(), res):
        v = zd.wh_hex(r)
        if v is None or v <= 0:
            continue
        rows.append([today.isoformat(), tok, round(v / 1e6, 2)])
    if len(rows) < len(STABLE):
        raise RuntimeError('brak podaży dla: ' + ', '.join(t for t in STABLE if t not in {r[1] for r in rows}))
    return rows


def fred_obs(sid, key, od):
    j = zd.get_json(FRED_OBS.format(sid=sid, key=key, od=od.isoformat()), timeout=60)
    if not isinstance(j, dict) or 'observations' not in j:
        raise RuntimeError(f'{sid}: odpowiedź bez observations' + (f" ({j.get('error_message')})" if isinstance(j, dict) and j.get('error_message') else ''))
    out = {}
    for o in j['observations']:
        d = str(o.get('date', ''))[:10]
        v = zd._num(o.get('value')) if str(o.get('value', '')).strip() != '.' else None
        if v is not None and len(d) == 10:
            out[d] = v
    if not out:
        raise RuntimeError(f'{sid}: brak obserwacji z wartością')
    return out


def plynnosc_rows(walcl, tga, rrp, od):
    """Dzienne wiersze płynności: kalendarz z serii dziennej RRPONTSYD (mld USD → mln), WALCL i TGA (mln USD, środy) przeniesione
    do przodu do następnej publikacji; dzień bez którejkolwiek wartości = brak wiersza. method = daty przeniesionych obserwacji."""
    dw, dt = sorted(walcl), sorted(tga)
    rows = []
    for d in sorted(rrp):
        if d < od:
            continue
        w = max((x for x in dw if x <= d), default=None); t = max((x for x in dt if x <= d), default=None)
        if w is None or t is None:
            continue
        r = round(rrp[d] * 1000.0, 3)
        rows.append([d, walcl[w], tga[t], r, round(walcl[w] - tga[t] - r, 3), f'walcl@{w},tga@{t}'])
    return rows


def src_plynnosc(key, today=None):
    today = today or TODAY
    if not key:
        raise RuntimeError('brak FRED_KEY')
    od = lata_wstecz(today, FILES['plynnosc']['back'])
    marg = od - datetime.timedelta(days=45)   # zapas na przeniesienie serii tygodniowych do przodu na początku okresu
    walcl = fred_obs('WALCL', key, marg); time.sleep(zd.FRED_SLEEP)
    tga = fred_obs('WTREGEN', key, marg); time.sleep(zd.FRED_SLEEP)
    rrp = fred_obs('RRPONTSYD', key, marg)
    rows = plynnosc_rows(walcl, tga, rrp, od.isoformat())
    if not rows:
        raise RuntimeError('brak dni z kompletem serii')
    return rows


def tic_rows(t1, t2, od=TIC_OD):
    rows = []
    for tab, col, tag in ((t1, 'for_lt_total_net', 'slt1_for_lt_total_net'), (t2, 'us_lt_total_net', 'slt2_us_lt_total_net')):
        if not isinstance(tab, dict):
            continue
        for country, months in tab.items():
            for m, rec in months.items():
                v = rec.get(col) if isinstance(rec, dict) else None
                if m >= od and v is not None:
                    rows.append([m, country, int(round(v)), tag])
    return rows


def src_tic():
    t1 = zd.parse_tic_table(zd.get_bytes(zd.TIC_BASE + 'slt_table1.txt', timeout=120))
    try:
        t2 = zd.parse_tic_table(zd.get_bytes(zd.TIC_BASE + 'slt_table2.txt', timeout=120))
    except Exception as e:  # noqa — tabela 2 osobno: jej awaria nie kasuje tabeli 1 (wiersze tabeli 2 z poprzednich przebiegów zostają)
        t2 = None; NOTES.append(f'TIC tabela 2: {e}')
    rows = tic_rows(t1, t2)
    if not rows:
        raise RuntimeError('TIC: brak wierszy od ' + TIC_OD)
    return rows


def cftc_rows(tables, od):
    """{kod: {data: wiersz}} → wiersze (data, kontrakt, grupa, long, short, net) od dnia od; grupa bez obu liczb = brak wiersza."""
    names = {v: k.upper() for k, v in zd.CFTC_MARKETS.items() if k in ('btc', 'eth')}
    rows = []
    for code, days in tables.items():
        if code not in names:
            continue
        for day, r in days.items():
            if day < od:
                continue
            for key, pos, _ in zd.CFTC_GROUPS:
                lo, sh = zd._cftc_int(r.get(f'{pos}_Long_All')), zd._cftc_int(r.get(f'{pos}_Short_All'))
                if lo is None or sh is None:
                    continue
                rows.append([day, names[code], key, lo, sh, lo - sh])
    return rows


def src_cftc(today=None, fetch=None):
    today = today or TODAY
    fetch = fetch or (lambda u: zd.get_bytes(u, timeout=120))
    od = lata_wstecz(today, FILES['cftc-krypto']['back'])
    codes = [zd.CFTC_MARKETS['btc'], zd.CFTC_MARKETS['eth']]
    tables = {}
    for y in range(od.year, today.year + 1):
        try:
            with zipfile.ZipFile(io.BytesIO(fetch(zd.CFTC_YEAR_URL.format(y)))) as z:
                names = [n for n in z.namelist() if n.lower().endswith('.txt')]
                if not names:
                    raise RuntimeError('brak pliku .txt w archiwum')
                text = z.read(names[0]).decode('utf-8', 'replace')
            for code, days in zd.parse_cftc_csv(text, codes=codes).items():
                tables.setdefault(code, {}).update(days)
        except Exception as e:  # noqa — rok osobno
            NOTES.append(f'CFTC rok {y}: {e}')
    try:
        for code, days in zd.parse_cftc_csv(fetch(zd.CFTC_WEEK_URL).decode('utf-8', 'replace'), header=zd.CFTC_COLS, codes=codes).items():
            tables.setdefault(code, {}).update(days)
    except Exception as e:  # noqa
        NOTES.append(f'CFTC tydzień: {e}')
    rows = cftc_rows(tables, od.isoformat())
    if not rows:
        raise RuntimeError('CFTC: brak wierszy BTC/ETH' + ('; ' + '; '.join(NOTES[-3:]) if NOTES else ''))
    return rows


def rent_rows(ust, buba, od):
    """[[dzień, %]] × 2 → (dzień, ust10y, bund10y, spread) dla dni ≥ od z choć jedną wartością; spread tylko, gdy są obie."""
    u = {d: v for d, v in ust if d >= od}; b = {d: v for d, v in buba if d >= od}
    rows = []
    for d in sorted(set(u) | set(b)):
        x, y = u.get(d), b.get(d)
        rows.append([d, x, y, round(x - y, 4) if x is not None and y is not None else None])
    return rows


def src_rentownosci(today=None):
    today = today or TODAY
    od = lata_wstecz(today, FILES['rentownosci']['back'])
    ust = []
    for y in range(od.year, today.year + 1):
        try:
            ust += zd.ust_parse(zd.get(zd.UST_URL.format(y=y), timeout=90)[1])
        except Exception as e:  # noqa
            NOTES.append(f'Skarb USA {y}: {e}')
    try:
        buba = zd.buba_parse(zd.get_json(zd.BUBA_URL.format(f=od.isoformat()), timeout=90))
    except Exception as e:  # noqa
        buba = []; NOTES.append(f'Bundesbank: {e}')
    if not ust and not buba:
        raise RuntimeError('rentowności: żadne źródło nie odpowiedziało' + ('; ' + '; '.join(NOTES[-2:]) if NOTES else ''))
    return rent_rows(ust, buba, od.isoformat())


NOTES = []   # informacje z przebiegu (część źródła bez odpowiedzi itp.) — do indeks.json, nie do kodu wyjścia

SERIA_N = 400   # najwyżej tyle ostatnich punktów jednej serii w seria.json (365 dni + zapas); pełna historia zostaje w CSV


def _f(s):
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def seria(arch):
    """archiwum/seria.json — widok archiwum dla strony (wykresy 30/90/365 dni): kilkanaście szeregów [[dzień, wartość]] z plików CSV
    na dysku (także tych sprzed tego przebiegu). Pusta komórka = brak punktu (nigdy zero). Pełna historia i wszystkie kolumny są w CSV."""
    out = {}

    def add(sid, unit, freq, src_name, file):
        out[sid] = {'d': [], 'unit': unit, 'freq': freq, 'src': src_name, 'file': file}

    def put(sid, day, v):
        if v is not None:
            out[sid]['d'].append([day, v])

    rows, _ = read_csv(os.path.join(arch, 'plynnosc.csv'), FILES['plynnosc']['cols'])
    for sid, col in (('plyn.net', 4), ('plyn.walcl', 1), ('plyn.tga', 2), ('plyn.rrp', 3)):
        add(sid, 'mln USD', 'D', 'fred', 'plynnosc.csv')
    for r in rows.values():
        for sid, col in (('plyn.net', 4), ('plyn.walcl', 1), ('plyn.tga', 2), ('plyn.rrp', 3)):
            put(sid, r[0], _f(r[col]))
    rows, _ = read_csv(os.path.join(arch, 'rentownosci.csv'), FILES['rentownosci']['cols'])
    add('rent.ust', '%', 'D', 'rent', 'rentownosci.csv'); add('rent.bund', '%', 'D', 'rent', 'rentownosci.csv'); add('rent.spread', 'pp', 'D', 'rent', 'rentownosci.csv')
    for r in rows.values():
        put('rent.ust', r[0], _f(r[1])); put('rent.bund', r[0], _f(r[2])); put('rent.spread', r[0], _f(r[3]))
    rows, _ = read_csv(os.path.join(arch, 'tic.csv'), FILES['tic']['cols'])
    add('tic.in', 'mln USD', 'M', 'tic', 'tic.csv'); add('tic.out', 'mln USD', 'M', 'tic', 'tic.csv')
    for r in rows.values():
        if r[1] == 'All Countries':
            put('tic.in' if r[3].startswith('slt1') else 'tic.out', r[0], _f(r[2]))
    rows, _ = read_csv(os.path.join(arch, 'cftc-krypto.csv'), FILES['cftc-krypto']['cols'])
    grp = {'lev_funds': 'lev', 'asset_mgr': 'am', 'dealer': 'dealer'}
    for c in ('btc', 'eth'):
        for g in grp.values():
            add(f'cftc.{c}.{g}', 'kontrakty', 'W', 'cftc', 'cftc-krypto.csv')
    for r in rows.values():
        if r[2] in grp and r[1].lower() in ('btc', 'eth'):
            put(f'cftc.{r[1].lower()}.{grp[r[2]]}', r[0], _f(r[5]))
    rows, _ = read_csv(os.path.join(arch, 'stablecoiny-eth.csv'), FILES['stablecoiny-eth']['cols'])
    add('stab.usdt', 'USDT', 'D', 'stab', 'stablecoiny-eth.csv'); add('stab.usdc', 'USDC', 'D', 'stab', 'stablecoiny-eth.csv')
    for r in rows.values():
        if r[1] in ('USDT', 'USDC'):
            put('stab.' + r[1].lower(), r[0], _f(r[2]))
    rows, _ = read_csv(os.path.join(arch, 'wieloryby.csv'), FILES['wieloryby']['cols'])
    wh = {}
    for r in rows.values():   # suma USD giełdy w dniu; aktywo bez wartości w USD (np. ETH bez kursu) = giełda bez sumy tego dnia (suma częściowa byłaby fałszem)
        k, v = (r[1], r[0]), _f(r[4])
        if k in wh and wh[k] is None:
            continue
        wh[k] = None if v is None else wh.get(k, 0.0) + v
    for (g, day) in sorted(wh):
        sid = 'wh.' + g
        if sid not in out:
            add(sid, 'USD', 'D', 'wh', 'wieloryby.csv')
        put(sid, day, None if wh[(g, day)] is None else round(wh[(g, day)], 2))
    for sid, s in out.items():
        s['d'] = sorted(s['d'])[-SERIA_N:]
        s['n'] = len(s['d']); s['first'] = s['d'][0][0] if s['d'] else None; s['last'] = s['d'][-1][0] if s['d'] else None
    return {'at': NOW.isoformat(), 'credit': CREDIT, 'series': out}



def run(sources, arch=None, prev_index=None):
    """sources: nazwa → funkcja zwracająca wiersze. Zapisuje CSV i indeks.json; zwraca indeks (z listą błędów)."""
    arch = arch or ARCH
    prev = prev_index if isinstance(prev_index, dict) else {}
    pf = prev.get('files') if isinstance(prev.get('files'), dict) else {}
    idx = {'at': NOW.isoformat(), 'credit': CREDIT, 'files': {}, 'errors': [], 'notes': []}
    for name, fn in sources.items():
        spec = FILES[name]
        path = os.path.join(arch, spec['file'])
        old, note = read_csv(path, spec['cols'])
        if note:
            idx['notes'].append(f'{name}: {note}')
        rec = dict(pf.get(name) or {})
        rec.update({'file': spec['file'], 'src': spec['src'], 'cols': spec['cols'], 'key': spec['key']})
        try:
            NOTES.clear()
            rows = fn()
            merged, added, revised = merge(old, rows, spec['cols'], spec['key'])
            write_csv(path, spec['cols'], merged)
            keys = sorted(merged)
            rec.update({'ok': True, 'at': NOW.isoformat(), 'rows': len(merged), 'first': keys[0][0] if keys else None, 'last': keys[-1][0] if keys else None,
                        'added': added, 'revised': revised, 'revisions_total': int(rec.get('revisions_total') or 0) + revised, 'fetched': len(rows)})
            if NOTES:
                idx['notes'].append(f'{name}: ' + '; '.join(zd.mask(x) for x in NOTES)[:300])
            print(f'{name}: {len(rows)} wierszy pobranych, {added} nowych, {revised} zrewidowanych, razem {len(merged)}')
        except Exception as e:  # noqa — źródło osobno; poprzedni plik zostaje nietknięty
            msg = zd.mask(f'{name}: {e}')[:300]
            rec.update({'ok': False, 'error_at': NOW.isoformat(), 'error': msg, 'rows': len(old)})
            idx['errors'].append(msg); print('BŁĄD', msg)
        idx['files'][name] = rec
    os.makedirs(arch, exist_ok=True)
    try:   # widok dla strony z plików na dysku — także gdy część źródeł zawiodła (stare wiersze zostają)
        sj = seria(arch)
        with open(os.path.join(arch, 'seria.json'), 'w', encoding='utf-8') as f:
            json.dump(sj, f, ensure_ascii=False, separators=(',', ':'))
        idx['seria'] = {k: v['n'] for k, v in sj['series'].items()}
    except Exception as e:  # noqa
        idx['errors'].append(zd.mask(f'seria.json: {e}')[:300])
    with open(os.path.join(arch, 'indeks.json'), 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    return idx


def main():
    key = os.environ.get('FRED_KEY', '').strip()
    if key:
        zd.SECRETS.append(key)
    prev = None
    try:
        with open(os.path.join(ARCH, 'indeks.json'), encoding='utf-8') as f:
            prev = json.load(f)
    except Exception:
        prev = None
    idx = run({'wieloryby': src_wieloryby, 'stablecoiny-eth': src_stable, 'plynnosc': lambda: src_plynnosc(key), 'tic': src_tic,
               'cftc-krypto': src_cftc, 'rentownosci': src_rentownosci}, prev_index=prev)
    summ = os.environ.get('GITHUB_STEP_SUMMARY')
    lines = [f'## Archiwum własne — {NOW.isoformat()}', '', '| plik | wiersze | od | do | nowe | rewizje | stan |', '|---|---|---|---|---|---|---|']
    for n, r in idx['files'].items():
        lines.append(f"| {r['file']} | {r.get('rows', '—')} | {r.get('first') or '—'} | {r.get('last') or '—'} | {r.get('added', '—')} | {r.get('revised', '—')} | {'OK' if r.get('ok') else 'BŁĄD: ' + str(r.get('error'))} |")
    if idx['notes']:
        lines += ['', 'Uwagi: ' + ' · '.join(idx['notes'])]
    if summ:
        with open(summ, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    sys.exit(1 if idx['errors'] else 0)


if __name__ == '__main__':
    main()
