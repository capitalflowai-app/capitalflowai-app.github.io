#!/usr/bin/env python3
"""CapitalFlowAI — zbieranie danych wymagających klucza API (uruchamiane przez GitHub Actions).

Wynik: data/etf.json (napływy ETF, SoSoValue + kapitalizacje CoinGecko),
       data/dzis.json (notowania ETF-ów krajowych USA, Finnhub — okres DZIŚ),
       data/ceny.json (dzienne notowania 14 ETF-ów zastępczych, Twelve Data — okresy 1T i 1M),
       data/cmc.json (CoinMarketCap: kapitalizacja rynku, dominacja BTC/ETH, stablecoiny, DeFi),
       data/instytucje.json (bez klucza: Skarb USA — saldo TGA; NY Fed — reverse repo i portfel SOMA; EBC — salda
       TARGET; MOF Japonia — tygodniowe transakcje w papierach wartościowych),
       data/meta.json (kiedy, co się udało, błędy).
Klucze wyłącznie ze zmiennych środowiskowych: SOSOVALUE_KEY, COINGECKO_KEY, FINNHUB_KEY, TWELVEDATA_KEY, COINMARKETCAP_KEY.
Decyzja właściciela 24.09.2026 (wieczór): dane z jego kluczy Finnhub, Twelve Data i CoinMarketCap są publikowane na stronie
mimo planów „do użytku osobistego" — właściciel przyjął ryzyko i zapowiedział plany płatne (checkpoints/DECYZJA_...).
SITE_URL (opcjonalnie): adres opublikowanej strony — gdy źródło zawiedzie, zachowujemy poprzedni plik
zamiast pustki (data w polu "at" pokazuje wtedy prawdziwy wiek danych).
Tylko biblioteka standardowa — zero zależności.
"""
import csv, io, json, os, re, sys, time, datetime, urllib.request, urllib.error

SOSO = 'https://openapi.sosovalue.com/openapi/v1'
ETF_SYMS = ['btc', 'eth', 'sol', 'xrp']
CG_IDS = {'btc': 'bitcoin', 'eth': 'ethereum', 'sol': 'solana', 'xrp': 'ripple'}
SOSO_SLEEP = 4.0   # limit 20 zapytań/min — 15/min zostawia zapas
# te same ETF-y zastępcze co w index.html (GPROXY)
DAY_SYMS = ['SPY', 'EWC', 'ILF', 'VGK', 'KSA', 'TUR', 'EIS', 'EZA', 'INDA', 'MCHI', 'EWJ', 'EWY', 'ASEA', 'EWA']
TD = 'https://api.twelvedata.com'
TD_BATCH = 7        # limit 8 kredytów/min (1 symbol = 1 kredyt): dwie paczki po 7 z minutą przerwy
TD_SLEEP = 61
TD_OUTPUT = 45      # ≈ 2 miesiące sesji; 1M = 21 sesji + zapas
TD_MIN_SYMBOLS = 10
TD_MIN_CANDLES = 22
CMC = 'https://pro-api.coinmarketcap.com'
# FRED (Federal Reserve Bank of St. Louis) — tylko serie Rady Gubernatorów Fed: domena publiczna, „citation requested”.
# Serie firm trzecich na FRED (SP500, VIXCLS, BAMLH0A0HYM2 …) wymagają zgody właściciela — nie pobieramy.
FRED = 'https://api.stlouisfed.org/fred/series/observations'
FRED_SERIES = {
    'WALCL': {'unit': 'mln USD', 'freq': 'W', 'name': 'Fed: aktywa razem (H.4.1), środa'},
    'RRPONTSYD': {'unit': 'mld USD', 'freq': 'D', 'name': 'Reverse repo overnight, wolumen dnia'},
    'DTWEXBGS': {'unit': 'indeks (styczeń 2006 = 100)', 'freq': 'D', 'name': 'Szeroki nominalny indeks dolara'},
    'WTREGEN': {'unit': 'mln USD', 'freq': 'W', 'name': 'Konto rządu USA w Fed (TGA) wg H.4.1, środa'},
}
FRED_LIMIT = 60      # ostatnie 60 obserwacji: ~1 rok tygodniowych, ~3 miesiące dziennych
FRED_SLEEP = 0.6     # limit FRED: 120 zapytań/min — 4 zapytania na przebieg z odstępem
FRED_CITE = 'Board of Governors of the Federal Reserve System (US), via FRED, Federal Reserve Bank of St. Louis'
FRED_API_NOTE = 'This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.'
OUT = 'data'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
META = {'at': NOW, 'ok': {}, 'errors': []}
SECRETS = []      # wartości kluczy — maskowane w każdym komunikacie błędu
TICKER = re.compile(r'^[A-Z0-9.]{1,10}$')


def mask(text):
    """Komunikat błędu nigdy nie zawiera klucza (nawet gdy dostawca odbije adres z parametrem)."""
    text = str(text)
    for k in SECRETS:
        if k:
            text = text.replace(k, '***')
    return text


def get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalFlowAI-collector/1.0', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'replace')


def get_json(url, headers=None):
    st, body = get(url, headers)
    return json.loads(body)


def get_bytes(url, headers=None, timeout=60):
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalFlowAI-collector/1.0', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def soso(path, key, _retry=True):
    time.sleep(SOSO_SLEEP)
    try:
        j = get_json(SOSO + path, {'x-soso-api-key': key})
    except urllib.error.HTTPError as e:
        if e.code == 429 and _retry:          # limit minutowy — odczekaj pełną minutę i spróbuj raz jeszcze
            print('SoSoValue 429 — czekam 65 s')
            time.sleep(65)
            return soso(path, key, _retry=False)
        raise
    if isinstance(j, dict) and j.get('code') not in (None, 0):
        raise RuntimeError(f'SoSoValue {path}: {j.get("message")}')
    return j['data'] if isinstance(j, dict) and 'data' in j else j


def previous(name):
    """Poprzedni plik z opublikowanej strony (żeby awaria API nie wymazała danych)."""
    site = os.environ.get('SITE_URL', '').rstrip('/')
    if not site:
        return None
    try:
        return get_json(f'{site}/data/{name}.json?t={int(time.time())}')
    except Exception as e:  # noqa
        META['errors'].append(mask(f'poprzedni {name}.json: {e}'))
        return None


def fresh(prev, minutes):
    """Czy poprzedni plik (z opublikowanej strony) jest młodszy niż `minutes` minut."""
    try:
        at = datetime.datetime.fromisoformat(prev['at'])
        return (datetime.datetime.now(datetime.timezone.utc) - at).total_seconds() < minutes * 60
    except Exception:
        return False


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{name}.json', 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    print(f'zapisano {OUT}/{name}.json ({os.path.getsize(f"{OUT}/{name}.json")} B)')


def ts(date_str):
    return int(datetime.datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp())


# --- źródła urzędowe bez klucza (licencje: strona/LICENCJE-zrodel.md i checkpoints/PUBLIC_RIGHTS_*_PL.md) ---
TGA_URL = ('https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/dts/operating_cash_balance'
           '?filter=account_type:eq:Treasury%20General%20Account%20(TGA)%20Closing%20Balance'
           '&sort=-record_date&page[size]=70&fields=record_date,account_type,open_today_bal')
RRP_URL = 'https://markets.newyorkfed.org/api/rp/reverserepo/all/results/last/30.json'
SOMA_URL = 'https://markets.newyorkfed.org/api/soma/summary.json'
TGB_COUNTRIES = ['DE', 'IT', 'ES', 'NL', 'FR', 'IE', 'PT', 'GR', 'LU']
TGB_URL = ('https://data-api.ecb.europa.eu/service/data/TGB/M.' + '+'.join(TGB_COUNTRIES)
           + '.N.A094T.U2.EUR.E?format=jsondata&lastNObservations=13')
MOF_URL = 'https://www.mof.go.jp/policy/international_policy/reference/itn_transactions_in_securities/week.csv'
MOF_WEEKS = 26
_FULLWIDTH = str.maketrans({'．': '.', '～': '~', '　': ' '})


def _num(token):
    """Liczba z tekstu dostawcy ('1,689 ', '-15,228', '957409'); brak/nie-liczba → None (nigdy 0)."""
    t = str(token).replace(',', '').strip()
    if t in ('', '-', '－', 'null', 'None'):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_tga(j):
    """FiscalData DTS: saldo zamknięcia konta TGA (mln USD) rosnąco po dacie."""
    rows = []
    for r in j.get('data', []):
        if 'Closing Balance' not in str(r.get('account_type', '')):
            continue
        v = _num(r.get('open_today_bal'))
        d = str(r.get('record_date', ''))[:10]
        if v is None or not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
            continue
        rows.append([d, int(round(v))])
    rows.sort(key=lambda x: x[0])
    if not rows:
        raise RuntimeError('FiscalData: brak wierszy TGA')
    return {'src': 'U.S. Treasury, Fiscal Data — Daily Treasury Statement', 'unit': 'mln USD', 'asof': rows[-1][0],
            'url': 'https://fiscaldata.treasury.gov/datasets/daily-treasury-statement/', 'd': rows}


def parse_rrp(j):
    """NY Fed: przyjęte kwoty w operacjach reverse repo (mln USD) rosnąco po dacie."""
    rows = []
    for o in (j.get('repo') or {}).get('operations') or []:
        if o.get('operationType') != 'Reverse Repo':
            continue
        v = _num(o.get('totalAmtAccepted'))
        d = str(o.get('operationDate', ''))[:10]
        if v is None or not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
            continue
        rows.append([d, int(round(v / 1e6))])
    rows.sort(key=lambda x: x[0])
    if not rows:
        raise RuntimeError('NY Fed: brak operacji reverse repo')
    return {'src': 'Federal Reserve Bank of New York — reverse repo operations', 'unit': 'mln USD', 'asof': rows[-1][0],
            'url': 'https://www.newyorkfed.org/markets/desk-operations/reverse-repo', 'd': rows}


def parse_soma(j):
    """NY Fed: łączny portfel SOMA (mln USD), ostatnie 12 tygodni, rosnąco."""
    rows = []
    for r in (j.get('soma') or {}).get('summary') or []:
        v = _num(r.get('total'))
        d = str(r.get('asOfDate', ''))[:10]
        if v is None or not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
            continue
        rows.append([d, int(round(v / 1e6))])
    rows.sort(key=lambda x: x[0])
    rows = rows[-12:]
    if not rows:
        raise RuntimeError('NY Fed: brak wierszy SOMA')
    return {'src': 'Federal Reserve Bank of New York — SOMA holdings', 'unit': 'mln USD', 'asof': rows[-1][0],
            'url': 'https://www.newyorkfed.org/markets/soma-holdings', 'd': rows}


def parse_tgb(j):
    """EBC Data Portal (SDMX-JSON): salda TARGET krajów (mln EUR), miesięcznie, rosnąco."""
    dims = j['structure']['dimensions']
    series_dims = dims['series']
    area_i = next(i for i, d in enumerate(series_dims) if d['id'] == 'REF_AREA')
    areas = [v['id'] for v in series_dims[area_i]['values']]
    periods = [v['id'] for v in dims['observation'][0]['values']]
    q = {}
    for key, ser in j['dataSets'][0]['series'].items():
        area = areas[int(key.split(':')[area_i])]
        rows = []
        for oi, o in ser['observations'].items():
            v = _num(o[0] if o else None)
            if v is None:
                continue
            rows.append([periods[int(oi)], round(v, 2)])
        rows.sort(key=lambda x: x[0])
        if rows:
            q[area] = rows
    if not q:
        raise RuntimeError('EBC: brak serii TGB')
    asof = sorted({rows[-1][0] for rows in q.values()})
    return {'src': 'European Central Bank — TARGET balances (TGB)', 'unit': 'mln EUR',
            'asof': asof[0] if len(asof) == 1 else f'{asof[0]} – {asof[-1]}',
            'url': 'https://data.ecb.europa.eu/data/datasets/TGB', 'q': q}


def _mof_period(text):
    """'2026．9．6～9．12' → ('2026-09-06', '2026-09-12'); koniec bez roku bierze rok początku (przełom roku: +1)."""
    t = text.translate(_FULLWIDTH).replace(' ', '')
    m = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})~(?:(\d{4})\.)?(\d{1,2})\.(\d{1,2})$', t)
    if not m:
        return None
    y1, m1, d1, y2, m2, d2 = m.groups()
    y1, m1, d1, m2, d2 = int(y1), int(m1), int(d1), int(m2), int(d2)
    y2 = int(y2) if y2 else (y1 + 1 if m2 < m1 else y1)
    try:
        a = datetime.date(y1, m1, d1); b = datetime.date(y2, m2, d2)
    except ValueError:
        return None
    return a.isoformat(), b.isoformat()


def parse_mof(raw):
    """MOF Japonia, week.csv (cp932): tygodniowe transakcje w papierach (100 mln JPY); ostatnie MOF_WEEKS tygodni."""
    txt = raw.decode('cp932') if isinstance(raw, bytes) else raw
    out = []
    for row in csv.reader(io.StringIO(txt)):
        if not row or not row[0].strip() or not row[0].strip()[0].isdigit():
            continue
        per = _mof_period(row[0])
        if not per or len(row) < 23:
            continue
        col = lambda i: _num(row[i])
        out.append({'from': per[0], 'to': per[1],
                    'assets': {'equity_net': col(3), 'ltdebt_net': col(6), 'stdebt_net': col(10), 'total_net': col(11)},
                    'liabilities': {'equity_net': col(14), 'ltdebt_net': col(17), 'stdebt_net': col(21), 'total_net': col(22)}})
    out.sort(key=lambda r: r['from'])
    out = out[-MOF_WEEKS:]
    if not out:
        raise RuntimeError('MOF: brak tygodni')
    return {'src': 'Ministry of Finance, Japan — International Transactions in Securities (weekly)', 'unit': '100 mln JPY',
            'asof': f"{out[-1]['from']} – {out[-1]['to']}",
            'url': 'https://www.mof.go.jp/english/policy/international_policy/reference/itn_transactions_in_securities/index.htm',
            'd': out}


def build_instytucje():
    """data/instytucje.json — każde źródło osobno: awaria jednego nie kasuje pozostałych (brak nie jest zerem)."""
    out = {'at': NOW, 'src': 'instytucje'}
    jobs = [('tga', lambda: parse_tga(get_json(TGA_URL))), ('rrp', lambda: parse_rrp(get_json(RRP_URL))),
            ('soma', lambda: parse_soma(get_json(SOMA_URL))), ('tgb', lambda: parse_tgb(get_json(TGB_URL))),
            ('mof', lambda: parse_mof(get_bytes(MOF_URL)))]
    for name, job in jobs:
        try:
            out[name] = job(); META['ok'][name] = True
            print(f"{name}: stan {out[name]['asof']}")
        except Exception as e:
            META['errors'].append(mask(f'{name}: {e}')); META['ok'][name] = False
    if not any(k in out for k, _ in jobs):
        raise RuntimeError('żadne źródło urzędowe nie odpowiedziało')
    return out


def parse_td(j, syms):
    """Odpowiedź Twelve Data (zbiorcza: klucze = symbole; pojedyncza: obiekt z 'values') → (notowania, błędy).

    Notowanie symbolu: {'asof': ostatnia świeca, 'ex': kod giełdy, 'd': [[data, close, volume|None], …] rosnąco}.
    Świeca bez poprawnego close jest pomijana (brak nie jest zerem); symbol z status != ok trafia do błędów, nie do q.
    """
    if not isinstance(j, dict):
        raise RuntimeError('Twelve Data: odpowiedź nie jest obiektem JSON')
    if j.get('status') == 'error' and 'values' not in j and not any(s in j for s in syms):
        raise RuntimeError(f'Twelve Data: {j.get("code")} {j.get("message")}')
    if 'values' in j and len(syms) == 1:
        j = {syms[0]: j}
    q, errors = {}, []
    for sym in syms:
        o = j.get(sym)
        if not isinstance(o, dict):
            errors.append(f'Twelve Data {sym}: brak w odpowiedzi')
            continue
        if o.get('status') != 'ok' or not isinstance(o.get('values'), list):
            errors.append(f'Twelve Data {sym}: {o.get("message") or o.get("status") or "błąd"}')
            continue
        rows = []
        for v in o['values']:
            try:
                date = str(v['datetime'])[:10]
                datetime.datetime.strptime(date, '%Y-%m-%d')
                close = round(float(v['close']), 4)
            except (KeyError, TypeError, ValueError):
                continue
            if not close > 0:
                continue
            try:
                volume = int(float(v['volume'])) if v.get('volume') not in (None, '') else None
            except (TypeError, ValueError):
                volume = None
            rows.append([date, close, volume])
        if not rows:
            errors.append(f'Twelve Data {sym}: brak poprawnych świec')
            continue
        rows.sort(key=lambda r: r[0])
        meta = o.get('meta') or {}
        q[sym] = {'asof': rows[-1][0], 'ex': meta.get('mic_code') or meta.get('exchange') or '', 'd': rows}
    return q, errors


def td_batch(syms, key, _retry=True):
    url = f'{TD}/time_series?symbol={",".join(syms)}&interval=1day&outputsize={TD_OUTPUT}&apikey={key}'
    try:
        st, body = get(url)
    except urllib.error.HTTPError as e:
        # treść błędu bez adresu (adres zawiera klucz); 401 = zły klucz
        raise RuntimeError(f'HTTP {e.code}') from None
    j = json.loads(body)
    q, errors = parse_td(j, syms)
    if _retry and any(': 429' in e or 'credits' in e.lower() or 'limit' in e.lower() for e in errors) and not q:
        print('Twelve Data 429 — czekam 61 s')
        time.sleep(TD_SLEEP)
        return td_batch(syms, key, _retry=False)
    return q, errors


def build_prices(key):
    """data/ceny.json: dzienne zamknięcia 14 ETF-ów zastępczych (te same co DZIŚ), rosnąco po dacie."""
    q, errors = {}, []
    batches = [DAY_SYMS[i:i + TD_BATCH] for i in range(0, len(DAY_SYMS), TD_BATCH)]
    for n, syms in enumerate(batches):
        if n:
            time.sleep(TD_SLEEP)
        bq, be = td_batch(syms, key)
        q.update(bq)
        errors.extend(be)
    META['errors'].extend(errors)
    good = [s for s, v in q.items() if len(v['d']) >= TD_MIN_CANDLES]
    if len(good) < TD_MIN_SYMBOLS:
        raise RuntimeError(f'tylko {len(good)} symboli z {len(DAY_SYMS)} ma ≥ {TD_MIN_CANDLES} świec')
    dates = sorted({v['asof'] for v in q.values()})
    asof = dates[0] if len(dates) == 1 else f'{dates[0]} – {dates[-1]}'
    for s, v in q.items():
        print(f'{s}: {len(v["d"])} świec, ostatnia {v["asof"]} close {v["d"][-1][1]}')
    return {'at': NOW, 'src': 'Twelve Data', 'plan': 'basic', 'asof': asof, 'q': q}


def build_day(key):
    q = {}
    for sym in DAY_SYMS:
        st, body = get(f'https://finnhub.io/api/v1/quote?symbol={sym}&token={key}')
        j = json.loads(body)
        if j.get('c') and j.get('pc'):
            q[sym] = {'c': j['c'], 'pc': j['pc'], 'dp': j['dp'] if j.get('dp') is not None else (j['c'] / j['pc'] - 1) * 100,
                      't': j.get('t')}
        time.sleep(0.2)
    if len(q) < 10:
        raise RuntimeError(f'Finnhub: tylko {len(q)} notowań z {len(DAY_SYMS)}')
    return {'at': NOW, 'src': 'Finnhub', 'q': q}


def build_cmc(key):
    """data/cmc.json — CoinMarketCap global metrics (klucz w nagłówku). Pola nieobecne → None, nigdy 0."""
    j = get_json(f'{CMC}/v1/global-metrics/quotes/latest', {'X-CMC_PRO_API_KEY': key, 'Accept': 'application/json'})
    st = j.get('status') or {}
    if st.get('error_code') not in (None, 0):
        raise RuntimeError(f'CoinMarketCap: {st.get("error_code")} {st.get("error_message")}')
    d = j.get('data') or {}
    usd = (d.get('quote') or {}).get('USD') or {}
    num = lambda v: (float(v) if isinstance(v, (int, float)) else None)
    out = {'at': NOW, 'src': 'CoinMarketCap', 'asof': str(d.get('last_updated') or usd.get('last_updated') or ''),
           'total_mcap': num(usd.get('total_market_cap')), 'total_vol24': num(usd.get('total_volume_24h')),
           'mcap_chg24_pct': num(usd.get('total_market_cap_yesterday_percentage_change')),
           'btc_dom': num(d.get('btc_dominance')), 'eth_dom': num(d.get('eth_dominance')),
           'stable_mcap': num(usd.get('stablecoin_market_cap') if 'stablecoin_market_cap' in usd else d.get('stablecoin_market_cap')),
           'defi_mcap': num(usd.get('defi_market_cap') if 'defi_market_cap' in usd else d.get('defi_market_cap')),
           'altcoin_mcap': num(usd.get('altcoin_market_cap')), 'active': d.get('active_cryptocurrencies')}
    if out['total_mcap'] is None:
        raise RuntimeError('CoinMarketCap: brak total_market_cap')
    return out


def parse_fred(j, sid):
    """FRED observations → [[data, wartość]] rosnąco; '.' albo pusta wartość = brak (pomijamy, nigdy 0)."""
    if not isinstance(j, dict) or 'observations' not in j:
        raise RuntimeError(f'{sid}: odpowiedź bez observations' + (f" ({j.get('error_message')})" if isinstance(j, dict) and j.get('error_message') else ''))
    rows = []
    for o in j.get('observations', []):
        d = str(o.get('date', ''))[:10]
        v = _num(o.get('value')) if str(o.get('value', '')).strip() != '.' else None
        if v is None or not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
            continue
        rows.append([d, v])
    rows.sort(key=lambda x: x[0])
    if not rows:
        raise RuntimeError(f'{sid}: brak obserwacji z wartością')
    meta = FRED_SERIES[sid]
    return {'unit': meta['unit'], 'freq': meta['freq'], 'name': meta['name'], 'asof': rows[-1][0], 'd': rows}


def build_fred(key):
    """data/fred.json — serie Rady Gubernatorów Fed przez FRED API (klucz tylko w adresie zapytania, nigdy w komunikatach).
    Każda seria osobno: awaria jednej nie kasuje pozostałych (brak nie jest zerem)."""
    out = {'at': NOW, 'src': FRED_CITE, 'api_note': FRED_API_NOTE, 'url': 'https://fred.stlouisfed.org/', 'series': {}}
    for sid in FRED_SERIES:
        time.sleep(FRED_SLEEP)
        try:
            j = get_json(f'{FRED}?series_id={sid}&api_key={key}&file_type=json&sort_order=desc&limit={FRED_LIMIT}')
            out['series'][sid] = parse_fred(j, sid)
            print(f"FRED {sid}: stan {out['series'][sid]['asof']}")
        except Exception as e:
            META['errors'].append(mask(f'FRED {sid}: {e}'))
    if not out['series']:
        raise RuntimeError('żadna seria FRED nie odpowiedziała')
    return out


def build_etf(key, cg_key):
    out = {'at': NOW, 'asof': '', 'src': 'SoSoValue', 'live': True, 'mcap': {}, 'assets': {}}
    # kapitalizacje (CoinGecko) — do udziału ETF w rynku
    try:
        u = ('https://api.coingecko.com/api/v3/simple/price?ids=' + ','.join(CG_IDS.values())
             + '&vs_currencies=usd&include_market_cap=true')
        j = get_json(u, {'x-cg-demo-api-key': cg_key} if cg_key else None)   # klucz w nagłówku, nie w adresie
        out['mcap'] = {s: j[CG_IDS[s]]['usd_market_cap'] for s in ETF_SYMS}
        META['ok']['coingecko'] = True
    except Exception as e:
        META['errors'].append(mask(f'CoinGecko: {e}'))
        META['ok']['coingecko'] = False
    for s in ETF_SYMS:
        rows = soso(f'/etfs/summary-history?symbol={s.upper()}&country_code=US&limit=60', key)
        rows = [r for r in rows if r.get('date') and r.get('total_net_inflow') is not None]
        rows.sort(key=lambda r: r['date'])
        if not rows:
            raise RuntimeError(f'SoSoValue: brak danych dla {s}')
        day = [[ts(r['date']), r['total_net_inflow'] / 1e6] for r in rows]
        last = rows[-1]
        out['asof'] = max(out['asof'], last['date'])
        aum = last['total_net_assets'] / 1e6 if last.get('total_net_assets') else None
        mc = out['mcap'].get(s)
        a = {'sym': s.upper(), 'asof': last['date'], 'day': day, 'd1': day[-1][1],
             'w': sum(v for _, v in day[-5:]), 'm': sum(v for _, v in day[-min(len(day), 22):]),
             'cum': last['cum_net_inflow'] / 1e6, 'aum': aum,
             'share': (aum * 1e6 / mc * 100) if (aum and mc) else None, 'funds': []}
        lst = soso(f'/etfs?symbol={s.upper()}&country_code=US', key)
        for it in (lst or [])[:12]:
            if not TICKER.match(str(it.get('ticker', ''))):
                # ticker spoza wzorca nie trafia na stronę — i nie znika po cichu
                META['errors'].append(f'SoSoValue {s.upper()}: odrzucony ticker {str(it.get("ticker"))[:20]!r}')
                continue
            try:
                d = soso(f'/etfs/{it["ticker"]}/market-snapshot', key)
                a['funds'].append({'t': it['ticker'], 'n': it.get('name'), 'cty': 'us',
                                   'aum': d['net_assets'] / 1e6 if d.get('net_assets') is not None else None,
                                   'cum': d['cum_inflow'] / 1e6 if d.get('cum_inflow') is not None else None,
                                   'd1': d['net_inflow'] / 1e6 if d.get('net_inflow') is not None else None,
                                   'fee': d['sponsor_fee'] * 100 if d.get('sponsor_fee') is not None else None,
                                   'prem': d.get('prem_dsc')})
            except Exception as e:
                META['errors'].append(mask(f'SoSoValue {it.get("ticker")}: {e}'))
        a['funds'].sort(key=lambda f: -(f['aum'] or 0))
        if not a['aum'] and a['funds']:
            # suma aktywów tylko wtedy, gdy KAŻDY fundusz ma aktywa — brak nie jest zerem
            a['aum'] = (sum(f['aum'] for f in a['funds']) or None) if all(f['aum'] is not None for f in a['funds']) else None
            if a['aum'] and mc:
                a['share'] = a['aum'] * 1e6 / mc * 100
        out['assets'][s] = a
        print(f'{s.upper()}: dzień {last["date"]} {a["d1"]:+.1f} mln, AUM {a["aum"]}, funduszy {len(a["funds"])}')
    # fundusze publikują dane w różnych godzinach — jeśli daty różnią się między monetami, pokazujemy zakres, nie najnowszą
    dates = sorted({a['asof'] for a in out['assets'].values()})
    out['asof'] = dates[0] if len(dates) == 1 else f'{dates[0]} – {dates[-1]}'
    return out


def main():
    soso_key = os.environ.get('SOSOVALUE_KEY', '').strip()
    cg_key = os.environ.get('COINGECKO_KEY', '').strip()
    fh_key = os.environ.get('FINNHUB_KEY', '').strip()
    td_key = os.environ.get('TWELVEDATA_KEY', '').strip()
    cmc_key = os.environ.get('COINMARKETCAP_KEY', '').strip()
    fred_key = os.environ.get('FRED_KEY', '').strip()
    SECRETS[:] = [k for k in (soso_key, cg_key, fh_key, td_key, cmc_key, fred_key) if k]
    # ETF — dane dzienne: SoSoValue pytamy najwyżej raz na godzinę (oszczędza limit 100 000/mies.),
    # między odświeżeniami zachowujemy plik z opublikowanej strony (pole "at" mówi, kiedy pobrano)
    prev_etf = previous('etf') if soso_key else None
    if soso_key and prev_etf and fresh(prev_etf, 55):
        save('etf', prev_etf); META['ok']['sosovalue'] = 'cached'; print('ETF: dane z', prev_etf.get('at'), '— młodsze niż 55 min, bez zapytań do SoSoValue')
    elif soso_key:
        try:
            save('etf', build_etf(soso_key, cg_key)); META['ok']['sosovalue'] = True
        except Exception as e:
            META['errors'].append(mask(f'SoSoValue: {e}')); META['ok']['sosovalue'] = False
            if prev_etf: save('etf', prev_etf); print('SoSoValue zawiódł — zachowano poprzedni etf.json z', prev_etf.get('at'))
    else:
        META['errors'].append('brak SOSOVALUE_KEY'); META['ok']['sosovalue'] = False
    # DZIŚ (Finnhub, klucz właściciela) — decyzja właściciela 24.09 wieczór
    if fh_key:
        try:
            save('dzis', build_day(fh_key)); META['ok']['finnhub'] = True
        except Exception as e:
            META['errors'].append(mask(f'Finnhub: {e}')); META['ok']['finnhub'] = False
            prev = previous('dzis')
            if prev: save('dzis', prev); print('Finnhub zawiódł — zachowano poprzedni dzis.json z', prev.get('at'))
    else:
        META['errors'].append('brak FINNHUB_KEY'); META['ok']['finnhub'] = False
    # CENY (okresy 1T i 1M, Twelve Data, klucz właściciela): najwyżej raz na godzinę — 24 × 14 kredytów = 336 z 800 dziennie
    prev_ceny = previous('ceny') if td_key else None
    if td_key and prev_ceny and fresh(prev_ceny, 55):
        save('ceny', prev_ceny); META['ok']['twelvedata'] = 'cached'; print('CENY: dane z', prev_ceny.get('at'), '— młodsze niż 55 min, bez zapytań do Twelve Data')
    elif td_key:
        try:
            save('ceny', build_prices(td_key)); META['ok']['twelvedata'] = True
        except Exception as e:
            META['errors'].append(mask(f'Twelve Data: {e}')); META['ok']['twelvedata'] = False
            if prev_ceny: save('ceny', prev_ceny); print('Twelve Data zawiódł — zachowano poprzedni ceny.json z', prev_ceny.get('at'))
    else:
        META['errors'].append('brak TWELVEDATA_KEY'); META['ok']['twelvedata'] = False
    # CMC (CoinMarketCap, klucz właściciela): global metrics co przebieg (limit planu Basic: 10 000 kredytów/mies.; 72/dzień)
    if cmc_key:
        try:
            save('cmc', build_cmc(cmc_key)); META['ok']['coinmarketcap'] = True
        except Exception as e:
            META['errors'].append(mask(f'CoinMarketCap: {e}')); META['ok']['coinmarketcap'] = False
            prev = previous('cmc')
            if prev: save('cmc', prev)
    else:
        META['errors'].append('brak COINMARKETCAP_KEY'); META['ok']['coinmarketcap'] = False
    # FRED (klucz właściciela): cztery serie Fed, najwyżej raz na 55 min; przy awarii zachowaj poprzedni plik
    prev_fred = previous('fred') if fred_key else None
    if fred_key and prev_fred and fresh(prev_fred, 55):
        save('fred', prev_fred); META['ok']['fred'] = 'cached'; print('FRED: dane z', prev_fred.get('at'), '— młodsze niż 55 min, bez zapytań do FRED')
    elif fred_key:
        try:
            save('fred', build_fred(fred_key)); META['ok']['fred'] = True
        except Exception as e:
            META['errors'].append(mask(f'FRED: {e}')); META['ok']['fred'] = False
            if prev_fred: save('fred', prev_fred); print('FRED zawiódł — zachowano poprzedni fred.json z', prev_fred.get('at'))
    else:
        META['errors'].append('brak FRED_KEY'); META['ok']['fred'] = False
    # INSTYTUCJE (bez klucza): najwyżej raz na 55 min; przy awarii zachowaj poprzedni plik (pole "at" mówi, jak stary)
    prev_inst = previous('instytucje')
    if prev_inst and fresh(prev_inst, 55):
        save('instytucje', prev_inst); META['ok']['instytucje'] = 'cached'; print('INSTYTUCJE: dane z', prev_inst.get('at'), '— młodsze niż 55 min')
    else:
        try:
            save('instytucje', build_instytucje()); META['ok']['instytucje'] = True
        except Exception as e:
            META['errors'].append(mask(f'instytucje: {e}')); META['ok']['instytucje'] = False
            if prev_inst: save('instytucje', prev_inst); print('źródła urzędowe zawiodły — zachowano poprzedni instytucje.json z', prev_inst.get('at'))
    save('meta', META)
    print('błędy:', META['errors'] or 'brak')
    return 0


if __name__ == '__main__':
    sys.exit(main())
