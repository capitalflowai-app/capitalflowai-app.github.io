#!/usr/bin/env python3
"""CapitalFlowAI — zbieranie danych wymagających klucza API (uruchamiane przez GitHub Actions).

Wynik: data/etf.json (napływy ETF, SoSoValue + kapitalizacje CoinGecko),
       data/dzis.json (notowania ETF-ów krajowych USA, Finnhub — okres DZIŚ),
       data/meta.json (kiedy, co się udało, błędy).
Klucze wyłącznie ze zmiennych środowiskowych: SOSOVALUE_KEY, FINNHUB_KEY, COINGECKO_KEY.
SITE_URL (opcjonalnie): adres opublikowanej strony — gdy źródło zawiedzie, zachowujemy poprzedni plik
zamiast pustki (data w polu "at" pokazuje wtedy prawdziwy wiek danych).
Tylko biblioteka standardowa — zero zależności.
"""
import json, os, sys, time, datetime, urllib.request, urllib.error

SOSO = 'https://openapi.sosovalue.com/openapi/v1'
ETF_SYMS = ['btc', 'eth', 'sol', 'xrp']
CG_IDS = {'btc': 'bitcoin', 'eth': 'ethereum', 'sol': 'solana', 'xrp': 'ripple'}
# te same ETF-y zastępcze co w index.html (GPROXY)
DAY_SYMS = ['SPY', 'EWC', 'ILF', 'VGK', 'KSA', 'TUR', 'EIS', 'EZA', 'INDA', 'MCHI', 'EWJ', 'EWY', 'ASEA', 'EWA']
SOSO_SLEEP = 3.2   # limit 20 zapytań/min
OUT = 'data'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
META = {'at': NOW, 'ok': {}, 'errors': []}


def get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalFlowAI-collector/1.0', **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode('utf-8', 'replace')


def get_json(url, headers=None):
    st, body = get(url, headers)
    return json.loads(body)


def soso(path, key):
    time.sleep(SOSO_SLEEP)
    j = get_json(SOSO + path, {'x-soso-api-key': key})
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
        META['errors'].append(f'poprzedni {name}.json: {e}')
        return None


def save(name, obj):
    os.makedirs(OUT, exist_ok=True)
    with open(f'{OUT}/{name}.json', 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, separators=(',', ':'))
    print(f'zapisano {OUT}/{name}.json ({os.path.getsize(f"{OUT}/{name}.json")} B)')


def ts(date_str):
    return int(datetime.datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc).timestamp())


def build_etf(key, cg_key):
    out = {'at': NOW, 'asof': '', 'src': 'SoSoValue', 'live': True, 'mcap': {}, 'assets': {}}
    # kapitalizacje (CoinGecko) — do udziału ETF w rynku
    try:
        u = ('https://api.coingecko.com/api/v3/simple/price?ids=' + ','.join(CG_IDS.values())
             + '&vs_currencies=usd&include_market_cap=true' + (f'&x_cg_demo_api_key={cg_key}' if cg_key else ''))
        j = get_json(u)
        out['mcap'] = {s: j[CG_IDS[s]]['usd_market_cap'] for s in ETF_SYMS}
        META['ok']['coingecko'] = True
    except Exception as e:
        META['errors'].append(f'CoinGecko: {e}')
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
        a = {'sym': s.upper(), 'day': day, 'd1': day[-1][1],
             'w': sum(v for _, v in day[-5:]), 'm': sum(v for _, v in day[-min(len(day), 22):]),
             'cum': last['cum_net_inflow'] / 1e6, 'aum': aum,
             'share': (aum * 1e6 / mc * 100) if (aum and mc) else None, 'funds': []}
        lst = soso(f'/etfs?symbol={s.upper()}&country_code=US', key)
        for it in (lst or [])[:12]:
            try:
                d = soso(f'/etfs/{it["ticker"]}/market-snapshot', key)
                a['funds'].append({'t': it['ticker'], 'n': it.get('name'), 'cty': 'us',
                                   'aum': d['net_assets'] / 1e6 if d.get('net_assets') is not None else None,
                                   'cum': d['cum_inflow'] / 1e6 if d.get('cum_inflow') is not None else None,
                                   'd1': d['net_inflow'] / 1e6 if d.get('net_inflow') is not None else None,
                                   'fee': d['sponsor_fee'] * 100 if d.get('sponsor_fee') is not None else None,
                                   'prem': d.get('prem_dsc')})
            except Exception as e:
                META['errors'].append(f'SoSoValue {it.get("ticker")}: {e}')
        a['funds'].sort(key=lambda f: -(f['aum'] or 0))
        if not a['aum'] and a['funds']:
            a['aum'] = sum(f['aum'] or 0 for f in a['funds']) or None
            if a['aum'] and mc:
                a['share'] = a['aum'] * 1e6 / mc * 100
        out['assets'][s] = a
        print(f'{s.upper()}: dzień {a["d1"]:+.1f} mln, AUM {a["aum"]}, funduszy {len(a["funds"])}')
    return out


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


def main():
    soso_key = os.environ.get('SOSOVALUE_KEY', '').strip()
    fh_key = os.environ.get('FINNHUB_KEY', '').strip()
    cg_key = os.environ.get('COINGECKO_KEY', '').strip()
    # ETF
    if soso_key:
        try:
            save('etf', build_etf(soso_key, cg_key)); META['ok']['sosovalue'] = True
        except Exception as e:
            META['errors'].append(f'SoSoValue: {e}'); META['ok']['sosovalue'] = False
            prev = previous('etf')
            if prev: save('etf', prev); print('SoSoValue zawiódł — zachowano poprzedni etf.json z', prev.get('at'))
    else:
        META['errors'].append('brak SOSOVALUE_KEY'); META['ok']['sosovalue'] = False
    # DZIŚ
    if fh_key:
        try:
            save('dzis', build_day(fh_key)); META['ok']['finnhub'] = True
        except Exception as e:
            META['errors'].append(f'Finnhub: {e}'); META['ok']['finnhub'] = False
            prev = previous('dzis')
            if prev: save('dzis', prev); print('Finnhub zawiódł — zachowano poprzedni dzis.json z', prev.get('at'))
    else:
        META['errors'].append('brak FINNHUB_KEY'); META['ok']['finnhub'] = False
    save('meta', META)
    print('błędy:', META['errors'] or 'brak')
    return 0


if __name__ == '__main__':
    sys.exit(main())
