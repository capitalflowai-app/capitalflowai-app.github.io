#!/usr/bin/env python3
"""CapitalFlowAI — zbieranie danych wymagających klucza API (uruchamiane przez GitHub Actions).

Wynik: data/etf.json (napływy ETF, SoSoValue + kapitalizacje CoinGecko),
       data/dzis.json (notowania ETF-ów krajowych USA, Finnhub — okres DZIŚ),
       data/ceny.json (dzienne notowania 14 ETF-ów zastępczych, Twelve Data — okresy 1T i 1M),
       data/cmc.json (CoinMarketCap: kapitalizacja rynku, dominacja BTC/ETH, stablecoiny, DeFi),
       data/instytucje.json (bez klucza: Skarb USA — saldo TGA; NY Fed — reverse repo i portfel SOMA; EBC — salda
       TARGET; MOF Japonia — tygodniowe transakcje w papierach wartościowych),
       data/cm.json (bez klucza: Coin Metrics Community — wpłaty i wypłaty BTC/ETH na giełdy, zapas monet na giełdach),
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
_DEADLINE = [None]   # v49: po tym czasie (monotonic) SoSoValue nie czeka na 429 i pomija listy funduszy
SOSO_BUDGET = 8 * 60
SOSO_SLEEP = 4.0   # limit 20 zapytań/min — 15/min zostawia zapas
# te same ETF-y zastępcze co w index.html (GPROXY)
DAY_SYMS = ['SPY', 'EWC', 'ILF', 'VGK', 'KSA', 'TUR', 'EIS', 'EZA', 'INDA', 'MCHI', 'EWJ', 'EWY', 'ASEA', 'EWA']
TD = 'https://api.twelvedata.com'
TD_BATCH = 7        # limit 8 kredytów/min (1 symbol = 1 kredyt): dwie paczki po 7 z minutą przerwy
TD_SLEEP = 61
TD_OUTPUT = 260     # v64: ponad rok sesji (1R = 252) — koszt zapytania ten sam (1 kredyt na symbol niezależnie od liczby świec)
TD_MIN_SYMBOLS = 10
TD_MIN_CANDLES = 22
CMC = 'https://pro-api.coinmarketcap.com'
# TIC (Skarb USA, dane rządowe): pliki SLT tabulatorowe; pobierane najwyżej raz na dobę (publikacja ok. 15–18 dnia miesiąca)
TIC_BASE = 'https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/'
TIC_MONTHS = 13
TIC_REGIONS = {   # region strony → wiersze TIC (kraje i sumy urzędowe); 'usa' nie ma sensu (TIC = zagranica vs USA)
    'can': ['Canada'],
    'lat': ['Total Latin America'],                         # bez Karaibów (centra finansowe — osobno jako 'carib')
    'eur': ['Memo: European Union', 'United Kingdom', 'Switzerland', 'Norway'],
    'rus': ['Russia'],
    'mea': ['Saudi Arabia', 'United Arab Emirates', 'Kuwait', 'Israel', 'Turkey'],   # tabela 2 nie ma Arabii Saudyjskiej
    'afr': ['Total Africa'],
    'ind': ['India'],
    'chn': ['China, Mainland', 'Hong Kong'],
    'jpn': ['Japan', 'Korea, South'],                  # Tajwan osobno (nie ma go na mapie strony)
    'asean': ['Singapore', 'Malaysia', 'Thailand', 'Indonesia', 'Philippines'],
    'oce': ['Australia', 'New Zealand'],
}
CG = 'https://api.coingecko.com/api/v3'      # plan Demo: klucz w nagłówku, atrybucja „Data by CoinGecko” wymagana
FNG_URL = 'https://api.alternative.me/fng/?limit=31'   # 31 dni: dziś + wartość sprzed 30 dni   # wskaźnik nastroju (model), podać źródło z linkiem
# FRED (Federal Reserve Bank of St. Louis) — tylko serie Rady Gubernatorów Fed: domena publiczna, „citation requested”.
# Serie firm trzecich na FRED (SP500, VIXCLS, BAMLH0A0HYM2 …) wymagają zgody właściciela — nie pobieramy.
FRED = 'https://api.stlouisfed.org/fred/series/observations'
FRED_SERIES = {
    'WALCL': {'unit': 'mln USD', 'freq': 'W', 'name': 'Fed: aktywa razem (H.4.1), środa'},
    'RRPONTSYD': {'unit': 'mld USD', 'freq': 'D', 'name': 'Reverse repo overnight, wolumen dnia'},
    'DTWEXBGS': {'unit': 'indeks (styczeń 2006 = 100)', 'freq': 'D', 'name': 'Szeroki nominalny indeks dolara'},
    'WTREGEN': {'unit': 'mln USD', 'freq': 'W', 'name': 'Konto rządu USA w Fed (TGA) wg H.4.1, środa'},
    # v50: H.4.1 Table 1A (Memorandum items, Wednesday level) — papiery w depozycie Fed dla zagranicznych instytucji oficjalnych
    'WSEFINTL1': {'unit': 'mln USD', 'freq': 'W', 'name': 'Fed: papiery w depozycie dla zagranicznych instytucji oficjalnych i międzynarodowych (H.4.1), środa'},
    'WMTSECL1': {'unit': 'mln USD', 'freq': 'W', 'name': '… w tym rynkowe papiery Skarbu USA (H.4.1), środa'},
    'WFASECL1': {'unit': 'mln USD', 'freq': 'W', 'name': '… w tym dług agencji federalnych i MBS (H.4.1), środa'},
    'WSEFINOL': {'unit': 'mln USD', 'freq': 'W', 'name': '… w tym pozostałe papiery (H.4.1), środa'},
}
FRED_LIMIT = 60      # ostatnie 60 obserwacji: ~1 rok tygodniowych, ~3 miesiące dziennych
FRED_SLEEP = 0.6     # limit FRED: 120 zapytań/min — 8 zapytań na przebieg z odstępem (v50: + 4 serie depozytu H.4.1)
FRED_CITE = 'Board of Governors of the Federal Reserve System (US), via FRED, Federal Reserve Bank of St. Louis'
FRED_API_NOTE = 'This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.'
OUT = 'data'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
META = {'at': NOW, 'ok': {}, 'errors': [], 'notes': []}   # notes: informacje (np. brak poprzedniego pliku), nie błędy
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
        if e.code == 429 and _retry and (_DEADLINE[0] is None or time.monotonic() < _DEADLINE[0]):          # limit minutowy — odczekaj pełną minutę i spróbuj raz jeszcze
            print('SoSoValue 429 — czekam 65 s')
            time.sleep(65)
            return soso(path, key, _retry=False)
        raise
    if isinstance(j, dict) and j.get('code') not in (None, 0):
        raise RuntimeError(f'SoSoValue {path}: {j.get("message")}')
    return j['data'] if isinstance(j, dict) and 'data' in j else j


def _prev_site(name):
    site = os.environ.get('SITE_URL', '').rstrip('/')
    if not site:
        return None
    try:
        return get_json(f'{site}/data/{name}.json?t={int(time.time())}')
    except urllib.error.HTTPError as e:
        if e.code == 404:   # pliku jeszcze nie ma (pierwszy przebieg) — informacja, nie błąd
            META['notes'].append(f'poprzedni {name}.json: brak na stronie (404)'); return None
        META['errors'].append(mask(f'poprzedni {name}.json: {e}')); return None
    except Exception as e:  # noqa
        META['errors'].append(mask(f'poprzedni {name}.json: {e}'))
        return None


def _prev_cache(name):
    """v51: plik z pamięci GitHub Actions (CACHE_DIR) — przeżywa awarię publikacji strony."""
    d = os.environ.get('CACHE_DIR', '').strip()
    if not d:
        return None
    p = os.path.join(d, name + '.json')
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:  # noqa
        META['errors'].append(mask(f'pamięć {name}.json: {e}'))
        return None


def previous(name):
    """Poprzedni plik: nowszy (wg pola at) z pamięci Actions i z opublikowanej strony — awaria API nie wymaże danych,
    a awaria publikacji nie zwielokrotni zapytań (v51)."""
    cands = [c for c in (_prev_cache(name), _prev_site(name)) if isinstance(c, dict)]
    if not cands:
        return None
    return max(cands, key=lambda c: str(c.get('at') or ''))


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
ILM_URL = 'https://data-api.ecb.europa.eu/service/data/ILM/W.U2.C.T000000.Z5.Z01?lastNObservations=13&format=jsondata'
M3_URL = 'https://data-api.ecb.europa.eu/service/data/BSI/M.U2.Y.V.M30.X.1.U2.2300.Z01.E?lastNObservations=14&format=jsondata'
BOP_CA_URL = ('https://data-api.ecb.europa.eu/service/data/BPS/M.N.U2.W1.S1.S1.T.B.CA._Z._Z._Z.EUR._T._X.N.ALL'
              '?lastNObservations=13&format=jsondata')
BOP_FA_URL = ('https://data-api.ecb.europa.eu/service/data/BPS/M.N.U2.W1.S1.S1.T.N.FA........'   # jedno zapytanie: wszystkie serie FA netto
              '?lastNObservations=13&format=jsondata')
BOP_FA_KEYS = {   # klucze sprawdzone 24.09.2026 (U2 = strefa euro w zmiennym składzie; serie I9 skończyły się na 2025-12)
    'M.N.U2.W1.S1.S1.T.N.FA._T.F._Z.EUR._T._X.N.ALL': 'fa',       # rachunek finansowy netto, razem
    'M.N.U2.W1.S1.S1.T.N.FA.D.F._Z.EUR._T._X.N.ALL': 'di',        # inwestycje bezpośrednie netto
    'M.N.U2.W1.S1.S1.T.N.FA.P.F._Z.EUR._T.M.N.ALL': 'pi',         # inwestycje portfelowe netto, razem
    'M.N.U2.W1.S1.S1.T.N.FA.P.F5._Z.EUR._T.M.N.ALL': 'pi_eq',     # … akcje i fundusze
    'M.N.U2.W1.S1.S1.T.N.FA.P.F3.T.EUR._T.M.N.ALL': 'pi_debt',    # … papiery dłużne
    'M.N.U2.W1.S1.S1.T.N.FA.O.F._Z.EUR._T._X.N.ALL': 'oi',        # pozostałe inwestycje netto
}
ECB_SLEEP = 1.2      # EBC blokuje serie szybkich zapytań („access blocked”): odstęp między zapytaniami do EBC
_ECB_LAST = -1e9
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


def _ecb_json(url):
    """EBC blokuje serie szybkich zapytań: odstęp ECB_SLEEP od poprzedniego zapytania do EBC (User-Agent ustawia get)."""
    global _ECB_LAST
    wait = ECB_SLEEP - (time.monotonic() - _ECB_LAST)
    if wait > 0:
        time.sleep(wait)
    try:
        return get_json(url)
    finally:
        _ECB_LAST = time.monotonic()


def _ecb_try(url, label):
    """v49: zapytanie do EBC, które przy błędzie zwraca None i zapisuje błąd (druga seria nadal może się udać)."""
    try:
        return _ecb_json(url)
    except Exception as e:
        META['errors'].append(mask(f'{label}: {e}'))
        return None


def _iso_week_end(period):
    """'2026-W38' → piątek tego tygodnia ISO (dzień, na który EBC sporządza tygodniowe sprawozdanie); inne → None."""
    m = re.match(r'^(\d{4})-W(\d{2})$', str(period))
    if not m:
        return None
    return datetime.date.fromisocalendar(int(m.group(1)), int(m.group(2)), 5).isoformat()


def parse_ecb_single(j, label):
    """EBC Data Portal (SDMX-JSON), dokładnie jedna seria: [[okres, wartość]] rosnąco; brak obserwacji pominięty (nigdy 0)."""
    dims = j['structure']['dimensions']
    periods = [v['id'] for v in dims['observation'][0]['values']]
    series = j['dataSets'][0]['series']
    if len(series) != 1:
        raise RuntimeError(f'{label}: oczekiwano jednej serii, jest {len(series)}')
    ser = next(iter(series.values()))
    rows = []
    for oi, o in ser['observations'].items():
        v = _num(o[0] if o else None)
        if v is None:
            continue
        rows.append([periods[int(oi)], v])
    rows.sort(key=lambda x: x[0])
    if not rows:
        raise RuntimeError(f'{label}: brak obserwacji')
    return rows


def parse_ilm(j):
    """Eurosystem, aktywa razem z tygodniowego sprawozdania (mln EUR): [[piątek tygodnia, wartość, tydzień ISO]]."""
    d = [[_iso_week_end(p) or p, int(round(v)), p] for p, v in parse_ecb_single(j, 'ILM')]
    return {'src': 'European Central Bank — Eurosystem weekly financial statement (ILM)', 'unit': 'mln EUR',
            'asof': d[-1][0], 'period': d[-1][2], 'url': 'https://data.ecb.europa.eu/data/datasets/ILM', 'd': d}


def parse_m3(j):
    """Agregat M3 strefy euro (mln EUR, wyrównany sezonowo), miesięcznie: [[YYYY-MM, wartość]]."""
    d = [[p, int(round(v))] for p, v in parse_ecb_single(j, 'BSI M3')]
    return {'src': 'European Central Bank — monetary aggregate M3 (BSI), seasonally adjusted', 'unit': 'mln EUR',
            'asof': d[-1][0], 'url': 'https://data.ecb.europa.eu/data/datasets/BSI', 'd': d}


def parse_ecb_multi(j):
    """EBC Data Portal (SDMX-JSON) z wieloma seriami → {pełny klucz serii: [[okres, wartość]] rosnąco}; brak pominięty."""
    dims = j['structure']['dimensions']
    sdims = dims['series']
    periods = [v['id'] for v in dims['observation'][0]['values']]
    out = {}
    for key, ser in j['dataSets'][0]['series'].items():
        full = '.'.join(sdims[i]['values'][int(p)]['id'] for i, p in enumerate(key.split(':')))
        rows = []
        for oi, o in ser['observations'].items():
            v = _num(o[0] if o else None)
            if v is not None:
                rows.append([periods[int(oi)], v])
        rows.sort(key=lambda x: x[0])
        if rows:
            out[full] = rows
    return out


def parse_bop(j_ca, j_fa):
    """Bilans płatniczy strefy euro (mln EUR, miesięcznie, nieskorygowany sezonowo): saldo rachunku bieżącego oraz rachunek
    finansowy netto (aktywa − pasywa) z podziałem; plus = kapitał netto wypływa ze strefy euro. Brak serii = None (nie zero)."""
    s = {}
    try:
        s['ca'] = [[p, int(round(v))] for p, v in parse_ecb_single(j_ca, 'BPS CA')] if j_ca is not None else None
    except Exception as e:
        META['errors'].append(mask(f'bop ca: {e}')); s['ca'] = None
    multi = parse_ecb_multi(j_fa) if j_fa is not None else {}
    for key, name in BOP_FA_KEYS.items():
        rows = multi.get(key)
        s[name] = [[p, int(round(v))] for p, v in rows] if rows else None
    if not any(s.get(n) for n in s):
        raise RuntimeError('BPS: żadna seria bilansu płatniczego nie odpowiedziała')
    asof = max(r[-1][0] for r in s.values() if r)
    return {'src': 'European Central Bank — euro area balance of payments (BPS), monthly, not seasonally adjusted', 'unit': 'mln EUR',
            'asof': asof, 'url': 'https://data.ecb.europa.eu/data/datasets/BPS',
            'sign': 'net = assets minus liabilities; positive = net outflow from the euro area', 's': s}


def build_instytucje():
    """data/instytucje.json — każde źródło osobno: awaria jednego nie kasuje pozostałych (brak nie jest zerem)."""
    out = {'at': NOW, 'src': 'instytucje'}
    jobs = [('tga', lambda: parse_tga(get_json(TGA_URL))), ('rrp', lambda: parse_rrp(get_json(RRP_URL))),
            ('soma', lambda: parse_soma(get_json(SOMA_URL))), ('tgb', lambda: parse_tgb(_ecb_json(TGB_URL))),
            ('ilm', lambda: parse_ilm(_ecb_json(ILM_URL))), ('m3', lambda: parse_m3(_ecb_json(M3_URL))),
            ('bop', lambda: parse_bop(_ecb_try(BOP_CA_URL, 'bop ca'), _ecb_try(BOP_FA_URL, 'bop fa'))),
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


def _ny_now():
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.now(ZoneInfo('America/New_York'))
    except Exception:   # brak bazy stref — przyjmij czas letni (UTC−4)
        return datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=4)


def _drop_open_session(q, now_ny=None):
    """v51: świeca z dzisiejszą datą przed 16:15 czasu Nowego Jorku to trwająca sesja, nie zamknięcie — pomijamy ją,
    żeby wszystkie regiony liczyły zmianę do tego samego rodzaju ceny (ostatnie zamknięcie)."""
    now_ny = now_ny or _ny_now()
    today = now_ny.date().isoformat()
    if (now_ny.hour, now_ny.minute) >= (16, 15):
        return 0
    n = 0
    for s, v in q.items():
        d = v.get('d') or []
        if d and str(d[-1][0])[:10] == today:
            v['d'] = d[:-1]; n += 1
            if v['d']:
                v['asof'] = str(v['d'][-1][0])[:10]
    if n:
        META['notes'].append(f'Twelve Data: pominięto {n} świec trwającej sesji ({today})')
    return n


def _align_calendar(q):
    """v69: wszystkie ETF-y na wspólnym kalendarzu sesji (daty SPY; bez SPY — daty obecne w co najmniej połowie symboli).
    Świeca spoza kalendarza (np. 25.12 przy święcie w USA) jest usuwana — każdy region liczy zmianę z tych samych sesji."""
    if not q:
        return 0
    spy = q.get('SPY') if isinstance(q.get('SPY'), dict) else None
    lens = sorted(len(v.get('d') or []) for v in q.values())
    if spy and spy.get('d') and len(spy['d']) >= lens[len(lens) // 2] - 5:   # v73: SPY tylko z pełną historią
        cal = {str(r[0])[:10] for r in spy['d']}
    else:
        cnt = {}
        for v in q.values():
            for r in (v.get('d') or []):
                cnt[str(r[0])[:10]] = cnt.get(str(r[0])[:10], 0) + 1
        cal = {d for d, c in cnt.items() if c * 2 >= len(q)}
    n, gone = 0, []
    for sym, v in list(q.items()):
        d = v.get('d') or []
        keep = [r for r in d if str(r[0])[:10] in cal]
        if not keep:
            gone.append(sym); del q[sym]; continue   # v73: bez żadnej świecy w kalendarzu — poza plikiem (build_prices nie padnie)
        if len(keep) != len(d):
            n += len(d) - len(keep); v['d'] = keep
            v['asof'] = str(keep[-1][0])[:10]
    if gone:
        META['notes'].append('Twelve Data: bez świec we wspólnym kalendarzu: ' + ', '.join(sorted(gone)))
    if n:
        META['notes'].append(f'Twelve Data: świece spoza wspólnego kalendarza sesji pominięte: {n}')
    return n


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
    _drop_open_session(q)
    _align_calendar(q)   # v69: jeden kalendarz sesji dla wszystkich ETF-ów
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
        try:
            st, body = get(f'https://finnhub.io/api/v1/quote?symbol={sym}&token={key}')
            j = json.loads(body)
        except Exception as e:   # v49: jeden symbol z błędem nie przerywa pozostałych (próg ≥10 z 14 zostaje)
            META['errors'].append(mask(f'Finnhub {sym}: {e}')); time.sleep(0.2); continue
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
    try:   # v50: podsumowanie depozytu H.4.1 — jego błąd nie może zatrzymać zapisu pozostałych serii FRED
        out['custody'] = custody_summary(out['series'])
    except Exception as e:
        out['custody'] = None; META['errors'].append(mask(f'FRED custody: {e}'))
    return out


def parse_deriv(j):
    """CoinGecko /derivatives/exchanges: otwarte pozycje w BTC per giełda; giełda bez liczby pominięta (nie zero)."""
    if not isinstance(j, list):
        raise RuntimeError('derivatives: odpowiedź nie jest listą')
    rows = []
    for x in j:
        oi = x.get('open_interest_btc') if isinstance(x, dict) else None
        if isinstance(oi, bool) or not isinstance(oi, (int, float)) or oi < 0:
            continue
        rows.append([str(x.get('name', ''))[:60], round(float(oi), 2)])
    if not rows:
        raise RuntimeError('derivatives: żadna giełda bez liczby otwartych pozycji')
    rows.sort(key=lambda r: -r[1])
    return {'src': 'CoinGecko — derivatives exchanges', 'unit': 'BTC', 'n': len(rows), 'total_oi_btc': round(sum(r[1] for r in rows), 2), 'top': rows[:5]}


def parse_defi(j):
    """CoinGecko /global/decentralized_finance_defi: liczby jako teksty → float; brak → None (nigdy 0)."""
    d = j.get('data') if isinstance(j, dict) else None
    if not isinstance(d, dict):
        raise RuntimeError('defi: brak pola data')
    out = {'src': 'CoinGecko — global DeFi'}
    for k in ('defi_market_cap', 'eth_market_cap', 'defi_to_eth_ratio', 'trading_volume_24h', 'defi_dominance'):
        out[k] = _num(d.get(k))
    if out['defi_market_cap'] is None:
        raise RuntimeError('defi: brak defi_market_cap')
    return out


def parse_fng(j):
    """Alternative.me Fear & Greed: [[data UTC, wartość 0–100, klasa]] rosnąco (wskaźnik nastroju — model, nie pomiar)."""
    data = j.get('data') if isinstance(j, dict) else None
    if not isinstance(data, list):
        raise RuntimeError('fng: brak pola data')
    rows = []
    for x in data:
        v = _num(x.get('value')); t = _num(x.get('timestamp'))
        if v is None or t is None or not 0 <= v <= 100:
            continue
        day = datetime.datetime.fromtimestamp(int(t), datetime.timezone.utc).date().isoformat()
        rows.append([day, int(round(v)), str(x.get('value_classification', ''))[:20]])
    rows.sort(key=lambda r: r[0])
    if not rows:
        raise RuntimeError('fng: brak wartości')
    return {'src': 'Alternative.me — Crypto Fear & Greed Index', 'url': 'https://alternative.me/crypto/fear-and-greed-index/',
            'kind': 'indicator', 'asof': rows[-1][0], 'd': rows}


def parse_tic_table(raw):
    """TIC SLT (tekst rozdzielany tabulatorami, nagłówek techniczny w wierszu zaczynającym się od 'country\t'):
    {kraj: {YYYY-MM: {kolumna: liczba}}}; puste pola = brak (None), wiersze stopki (bez daty YYYY-MM) pominięte."""
    text = raw.decode('utf-8', errors='replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
    lines = text.splitlines()
    cols = None
    out = {}
    for line in lines:
        parts = line.split('\t')
        if cols is None:
            if parts and parts[0].strip() == 'country':
                cols = [p.strip() for p in parts]
            continue
        if len(parts) < 4 or not re.match(r'^\d{4}-\d{2}$', parts[2].strip()):
            continue
        name = parts[0].strip(); month = parts[2].strip()
        rec = {}
        for i, c in enumerate(cols[3:], start=3):
            rec[c] = _num(parts[i]) if i < len(parts) else None
        out.setdefault(name, {})[month] = rec
    if cols is None or not out:
        raise RuntimeError('TIC: brak nagłówka technicznego albo wierszy z datą')
    return out


def parse_tic_holders(raw):
    """TIC Table 5 (Major Foreign Holders of Treasury Securities, mld USD): {'months': [...], 'rows': [[kraj, [wartości]]]}."""
    text = raw.decode('utf-8', errors='replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
    months = None; rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split('\t')]
        if months is None:
            if parts and parts[0] == 'Country' and len(parts) > 1 and re.match(r'^\d{4}-\d{2}$', parts[1]):
                months = parts[1:]
            continue
        if not parts or not parts[0] or parts[0].startswith('Of Which') or parts[0] in ('All Other', 'Grand Total'):
            if parts and parts[0] == 'Grand Total':
                rows.append(['Grand Total', [_num(v) for v in parts[1:len(months) + 1]]])
            continue
        vals = [_num(v) for v in parts[1:len(months) + 1]]
        if any(v is not None for v in vals):
            rows.append([parts[0], vals])
    if not months or not rows:
        raise RuntimeError('TIC tabela 5: brak nagłówka z miesiącami albo wierszy')
    return {'months': months, 'rows': rows}


def _tic_sum(table, members, months, col):
    """Suma kolumny po członkach regionu w każdym miesiącu: [[miesiąc, suma, liczba obecnych członków]]; brak = None, nie 0."""
    rows = []
    for m in months:
        vals = [table.get(name, {}).get(m, {}).get(col) for name in members]
        present = [v for v in vals if v is not None]
        rows.append([m, int(round(sum(present))) if present else None, len(present)])
    return rows


def _tic_net(t1, t2, members, months):
    """Netto do USA = zakupy zagranicy (tabela 1) − zakupy USA (tabela 2) tylko dla krajów obecnych w OBU tabelach w danym
    miesiącu: [[miesiąc, suma, liczba krajów]]; brak = None (np. tabela 2 nie ma Arabii Saudyjskiej)."""
    rows = []
    for m in months:
        vals = []
        for name in members:
            a = t1.get(name, {}).get(m, {}).get('for_lt_total_net')
            b = t2.get(name, {}).get(m, {}).get('us_lt_total_net')
            if a is not None and b is not None:
                vals.append(a - b)
        rows.append([m, int(round(sum(vals))) if vals else None, len(vals)])
    return rows


def build_tic():
    """data/tic.json — przepływy papierów wartościowych USA ↔ regiony strony (mln USD, miesięcznie, TIC SLT).
    in = netto zakupy amerykańskich papierów przez zagranicę (plus = kapitał do USA); out = netto zakupy zagranicznych
    papierów przez USA (plus = kapitał z USA). Tabela 2 i 5 osobno: ich awaria nie kasuje tabeli 1."""
    t1 = parse_tic_table(get_bytes(TIC_BASE + 'slt_table1.txt', timeout=120))
    months = sorted({m for c in t1.values() for m in c})[-TIC_MONTHS:]
    if not months:
        raise RuntimeError('TIC: brak miesięcy')
    try:
        t2 = parse_tic_table(get_bytes(TIC_BASE + 'slt_table2.txt', timeout=120))
    except Exception as e:
        META['errors'].append(mask(f'TIC tabela 2: {e}')); t2 = None
    try:
        holders = parse_tic_holders(get_bytes(TIC_BASE + 'slt_table5.txt'))
    except Exception as e:
        META['errors'].append(mask(f'TIC tabela 5: {e}')); holders = None
    last = months[-1]

    def region(members):
        r = {'members': members, 'n': len(members),
             'in': _tic_sum(t1, members, months, 'for_lt_total_net'), 'in_tr': _tic_sum(t1, members, months, 'for_lt_treas_net'),
             'in_eq': _tic_sum(t1, members, months, 'for_lt_eqty_net'), 'hold_in': _tic_sum(t1, members, [last], 'for_lt_total_pos')[0]}
        if t2 is not None:
            r['out'] = _tic_sum(t2, members, months, 'us_lt_total_net'); r['out_eq'] = _tic_sum(t2, members, months, 'us_lt_eqty_net')
            r['out_gov'] = _tic_sum(t2, members, months, 'us_lt_govt_bond_net'); r['hold_out'] = _tic_sum(t2, members, [last], 'us_lt_total_pos')[0]
            r['net'] = _tic_net(t1, t2, members, months)
        else:
            r['out'] = None; r['out_eq'] = None; r['out_gov'] = None; r['hold_out'] = None; r['net'] = None
        return r

    out = {'at': NOW, 'src': 'U.S. Department of the Treasury — Treasury International Capital (TIC), SLT tables 1, 2, 5',
           'url': 'https://home.treasury.gov/data/treasury-international-capital-tic-system', 'unit': 'mln USD', 'asof': last, 'months': months,
           'sign': 'in: net foreign purchases of U.S. long-term securities (positive = capital into the USA); out: net U.S. purchases of foreign long-term securities (positive = capital out of the USA)',
           'regions': {rid: region(members) for rid, members in TIC_REGIONS.items()},
           'world': region(['Grand Total']), 'carib': region(['Total Caribbean']), 'twn': region(['Taiwan']), 'holders': None}
    if holders:
        hm = holders['months']
        top = []
        for name, vals in holders['rows']:
            if name == 'Grand Total' or vals[0] is None:
                continue
            d1 = (vals[0] - vals[1]) if len(vals) > 1 and vals[1] is not None else None
            d12 = (vals[0] - vals[12]) if len(vals) > 12 and vals[12] is not None else None
            top.append([name, vals[0], None if d1 is None else round(d1, 1), None if d12 is None else round(d12, 1)])
        total = next((vals for name, vals in holders['rows'] if name == 'Grand Total'), None)
        out['holders'] = {'asof': hm[0], 'unit': 'mld USD', 'top': top[:15], 'total': total[0] if total else None,
                          'total_d12': (round(total[0] - total[12], 1) if total and len(total) > 12 and total[12] is not None and total[0] is not None else None)}
    return out


def parse_mk(pages):
    """CoinGecko /coins/markets (strony po 250): [[SYMBOL, kapitalizacja, zm.24h, 7d, 30d, 1y]] — pierwszy (większy) symbol
    wygrywa; brak liczby = None (nigdy 0)."""
    rows, seen, last = [], set(), ''
    for page in pages:
        if not isinstance(page, list):
            raise RuntimeError('markets: odpowiedź nie jest listą')
        for c in page:
            if not isinstance(c, dict):
                continue
            sy = str(c.get('symbol') or '').upper()
            if not sy or sy in seen or not re.match(r'^[A-Z0-9.$-]{1,15}$', sy):
                continue
            seen.add(sy)
            num = lambda k: c.get(k) if isinstance(c.get(k), (int, float)) and not isinstance(c.get(k), bool) else None
            rows.append([sy, num('market_cap'), num('price_change_percentage_24h_in_currency'), num('price_change_percentage_7d_in_currency'),
                         num('price_change_percentage_30d_in_currency'), num('price_change_percentage_1y_in_currency')])
            last = max(last, str(c.get('last_updated') or ''))
    if not rows:
        raise RuntimeError('markets: brak monet')
    return {'src': 'CoinGecko — coins/markets', 'asof': last[:19], 'cols': ['sym', 'mcap', 'p24h', 'p7d', 'p30d', 'p1y'], 'rows': rows}


def parse_stabc(j, top=14):
    """v58: DefiLlama /stablecoins → podaż stablecoinów dolarowych per sieć: teraz, zmiana 1, 7 i 30 dni (USD).
    Zmiana liczona tylko z aktywów, które mają obie wartości (brak poprzedniej = poza oknem, nie zero)."""
    A = j.get('peggedAssets') if isinstance(j, dict) else None
    if not isinstance(A, list) or not A:
        raise RuntimeError('stablecoins: brak peggedAssets')
    num = lambda o: (o.get('peggedUSD') if isinstance(o, dict) and isinstance(o.get('peggedUSD'), (int, float)) and not isinstance(o.get('peggedUSD'), bool) else None)
    ch = {}
    for a in A:
        if not isinstance(a, dict) or a.get('pegType') != 'peggedUSD' or not isinstance(a.get('chainCirculating'), dict):
            continue
        for name, v in a['chainCirculating'].items():
            if not isinstance(v, dict):
                continue
            cur = num(v.get('current'))
            if cur is None or cur < 0:
                continue
            c = ch.setdefault(str(name)[:40], {'cur': 0.0, 'd1': [0.0, 0.0], 'd7': [0.0, 0.0], 'd30': [0.0, 0.0]})
            c['cur'] += cur
            for k, f in (('d1', 'circulatingPrevDay'), ('d7', 'circulatingPrevWeek'), ('d30', 'circulatingPrevMonth')):
                p = num(v.get(f))
                if p is not None and p >= 0:
                    c[k][0] += cur; c[k][1] += p
    if not ch:
        raise RuntimeError('stablecoins: żadna sieć')
    rows = [[n, round(c['cur']), round(c['d1'][0] - c['d1'][1]), round(c['d7'][0] - c['d7'][1]), round(c['d30'][0] - c['d30'][1])]
            for n, c in sorted(ch.items(), key=lambda x: -x[1]['cur'])]
    tot = lambda i: sum(r[i] for r in rows)
    return {'src': 'DefiLlama — stablecoins (chainCirculating, peggedUSD)', 'unit': 'USD', 'asof': NOW[:10],
            'cols': ['sieć', 'podaż', 'zmiana 1 dzień', 'zmiana 7 dni', 'zmiana 30 dni'], 'n': len(rows),
            'total': [round(tot(1)), round(tot(2)), round(tot(3)), round(tot(4))], 'rows': rows[:top]}


def parse_stabh(j):
    """DefiLlama stablecoincharts/all → podaż stablecoinów w USD (totalCirculatingUSD.peggedUSD) teraz i zmiany za 1, 7, 30, 91, 365 dni
    (wartość z ostatniego dnia nie później niż N dni wstecz). To zmiana podaży = emisja − umorzenia, nie zmiana ceny."""
    if not isinstance(j, list) or len(j) < 40:
        raise RuntimeError('stablecoincharts: za krótka seria')
    pts = []
    for o in j:
        t = _num(o.get('date')) if isinstance(o, dict) else None
        tc = (o.get('totalCirculatingUSD') or o.get('totalCirculating') or {}) if isinstance(o, dict) else {}
        v = tc.get('peggedUSD') if isinstance(tc, dict) else None
        if t is None or not isinstance(v, (int, float)) or v <= 0:
            continue
        pts.append((int(t), float(v)))
    pts.sort()
    if len(pts) < 40:
        raise RuntimeError('stablecoincharts: za mało punktów')
    t_last, cur = pts[-1]
    out = {'src': 'DefiLlama — stablecoincharts/all (peggedUSD)', 'unit': 'USD',
           'asof': datetime.datetime.fromtimestamp(t_last, datetime.timezone.utc).date().isoformat(), 'cur': round(cur), 'd': {}, 'pct': {}}
    for n in (1, 7, 30, 91, 365):
        target = t_last - n * 86400
        prev = [v for t, v in pts if t <= target]
        if prev:
            out['d'][str(n)] = round(cur - prev[-1]); out['pct'][str(n)] = round((cur / prev[-1] - 1) * 100, 4)
    return out


# BIS LBS (v50): kwartalne przepływy bankowe między regionami strony — statystyki lokalizacyjne, miara F (zmiana należności
# skorygowana o kursy i przerwy w seriach), bez klucza. Warunki data.bis.org/help/legal: BIS jako źródło, tłumaczenie
# oznaczone jako nieoficjalne, bez sugerowania poparcia BIS. Wynik: data/bis.json (mln USD), pobierany najwyżej raz na dobę.
BIS_ORDER = ['usa', 'can', 'lat', 'eur', 'rus', 'mea', 'afr', 'ind', 'chn', 'jpn', 'asean', 'oce']   # kolejność GREG
BIS_REP = {   # region strony → kraje raportujące (jak GBISREP w index.html); TR, IN, SG, MY publikują tylko sumy (5J)
    'usa': ['US'], 'can': ['CA'], 'lat': ['BR', 'MX', 'CL'], 'eur': ['GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'CH', 'SE'],
    'mea': ['TR'], 'afr': ['ZA'], 'ind': ['IN'], 'chn': ['HK'], 'jpn': ['JP', 'KR'], 'asean': ['SG', 'MY', 'PH'], 'oce': ['AU']}
BIS_CP = {    # region strony → kraje kontrahentów (jak GBISCP w index.html); te same kody mapują też raportujących
    'usa': ['US'], 'can': ['CA'], 'lat': ['BR', 'MX', 'CL', 'CO', 'AR'], 'eur': ['GB', 'DE', 'FR', 'IT', 'ES', 'NL', 'CH', 'SE'],
    'rus': ['RU'], 'mea': ['TR', 'SA', 'AE', 'IL'], 'afr': ['ZA', 'NG', 'EG'], 'ind': ['IN'], 'chn': ['CN', 'HK', 'TW'],
    'jpn': ['JP', 'KR'], 'asean': ['SG', 'ID', 'TH', 'MY', 'VN', 'PH'], 'oce': ['AU', 'NZ']}
BIS_Q = 4             # okno: 4 kolejne kwartały kończące się na ostatnim pełnym
BIS_LASTN = 5         # o jeden więcej niż BIS_Q: serie spóźnione o kwartał nadal pokrywają okno
BIS_URL = ('https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0/Q.F.C.A.TO1.A.5J.A.'
           + '+'.join(c for r in BIS_ORDER for c in BIS_REP.get(r, [])) + '.A.'
           + '+'.join(dict.fromkeys(c for r in BIS_ORDER for c in BIS_CP[r]))
           + f'.N?lastNObservations={BIS_LASTN}&format=csv')
# wymiary klucza, których się spodziewamy — wiersz z innym kluczem nie trafia do sum (ochrona przed zmianą API)
BIS_KEY = {'FREQ': 'Q', 'L_MEASURE': 'F', 'L_POSITION': 'C', 'L_INSTR': 'A', 'L_DENOM': 'TO1', 'L_CURR_TYPE': 'A',
           'L_PARENT_CTY': '5J', 'L_REP_BANK_TYPE': 'A', 'L_CP_SECTOR': 'A', 'L_POS_TYPE': 'N'}
BIS_MISSING = ('H', 'K', 'L', 'M', 'Q')   # OBS_STATUS: braki (Q = „suppressed”, poufne; K = ujęte w innej kategorii) — nigdy 0
_BIS_PERIOD = re.compile(r'^\d{4}-Q[1-4]$')
BIS_SIGN = ('flows["a>b"]: quarterly FX- and break-adjusted change in cross-border claims (all instruments, all sectors) '
            'of banks located in region a on residents of region b; positive = banks in a lent/placed more in b '
            '(bank capital a -> b), negative = they cut exposure (b -> a). pairs["a|b"]: a>b plus b>a. '
            'regions[r].out = sum of r>x; regions[r].in = sum of x>r; regions[r].net = sum over matched country '
            'pairs (both countries report in that quarter) of [claims of r on x] - [claims of x on r]; positive = r is '
            'a net supplier of bank credit to the other regions (net outflow), negative = net recipient (net inflow). '
            'Sum of net over all regions = 0. Residence principle: London branches of US banks count as "eur". '
            'regions[r].rep_q = contribution of each reporting country of r to r.out in the latest quarter.')


def _bis_num(row):
    """OBS_VALUE → mln USD; 'NaN', pusty, status braku → None (nigdy 0). Inna waluta miary = błąd całej odpowiedzi."""
    if row.get('OBS_STATUS') in BIS_MISSING:
        return None
    t = str(row.get('OBS_VALUE', '')).replace(',', '').strip()
    try:
        v = float(t)
    except ValueError:
        return None
    if not (-1e15 < v < 1e15):   # NaN i ±inf nie spełniają nierówności
        return None
    if row.get('UNIT_MEASURE') != 'USD':
        raise RuntimeError(f'nieoczekiwana jednostka {row.get("UNIT_MEASURE")!r} (oczekiwano USD)')
    try:
        mult = int(row.get('UNIT_MULT'))
    except (TypeError, ValueError):
        raise RuntimeError(f'nieczytelny mnożnik jednostki {row.get("UNIT_MULT")!r}')
    return v * 10 ** (mult - 6)          # UNIT_MULT 6 = miliony → bez zmian


def _bis_rows(d, quarters):
    """{kwartał: [suma, n]} → [[kwartał, suma|None, n]] (brak = None i n = 0, nie 0)."""
    return [[q, round(d[q][0], 1) + 0.0, d[q][1]] if q in d and d[q][1] else [q, None, 0] for q in quarters]   # + 0.0: bez „-0.0”


def _bis_total(rows):
    """Suma z pełnego okna; gdy którykolwiek kwartał nie ma danych → None."""
    if len(rows) != BIS_Q or any(r[1] is None for r in rows):
        return None
    return round(sum(r[1] for r in rows), 1) + 0.0


def _bis_qshift(q, k):
    """'2026-Q1' cofnięty o k kwartałów (k=1 → '2025-Q4')."""
    i = int(q[:4]) * 4 + int(q[-1]) - 1 - k
    return f'{i // 4}-Q{i % 4 + 1}'


def parse_bis_flows(raw, at=None):
    """CSV z BIS (miara F) → struktura data/bis.json. Jednostka: mln USD. Brak ≠ 0 na każdym poziomie.
    Okno = BIS_Q kolejnych kwartałów kończących się na ostatnim „pełnym” (co najmniej połowa najliczniejszego);
    kwartał w oknie bez danych zostaje jako brak (None), sumy 4 kwartałów liczone tylko z kompletu."""
    text = raw.decode('utf-8-sig', 'replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
    rd = csv.DictReader(io.StringIO(text))
    need = {'L_REP_CTY', 'L_CP_COUNTRY', 'TIME_PERIOD', 'OBS_VALUE', 'UNIT_MEASURE', 'UNIT_MULT', *BIS_KEY}
    if not rd.fieldnames or not need <= set(rd.fieldnames):
        raise RuntimeError('odpowiedź bez kolumn ' + ', '.join(sorted(need - set(rd.fieldnames or []))))
    c2r = {c: rid for rid, cs in BIS_CP.items() for c in cs}
    obs, count = {}, {}                   # (kraj raportujący, kraj kontrahenta) → {kwartał: mln USD}
    for row in rd:
        if any(row.get(k) != v for k, v in BIS_KEY.items()):
            continue
        rep, cp, q = row['L_REP_CTY'], row['L_CP_COUNTRY'], row['TIME_PERIOD']
        if rep == cp or rep not in c2r or cp not in c2r or not _BIS_PERIOD.match(q or ''):
            continue
        v = _bis_num(row)
        if v is None:
            continue
        obs.setdefault((rep, cp), {})[q] = v
        count[q] = count.get(q, 0) + 1
    if not count:
        raise RuntimeError('brak liczb w odpowiedzi LBS')
    top = max(count.values())
    # ostatni kwartał „pełny” (co najmniej połowa najliczniejszego): stare końcówki zamkniętych serii i świeże
    # szczątkowe publikacje nie wyznaczają okna
    last = max(q for q, c in count.items() if 2 * c >= top)
    quarters = [_bis_qshift(last, k) for k in range(BIS_Q - 1, -1, -1)]
    acc = {}                              # (region a, region b) → {kwartał: [suma, liczba par krajów]}
    for (rep, cp), ser in obs.items():
        a, b = c2r[rep], c2r[cp]
        if a == b:
            continue
        for q in quarters:
            if q in ser:
                s = acc.setdefault((a, b), {}).setdefault(q, [0.0, 0])
                s[0] += ser[q]; s[1] += 1
    if len(acc) < 6:
        raise RuntimeError(f'za mało par regionów w LBS ({len(acc)})')
    pos = {r: i for i, r in enumerate(BIS_ORDER)}
    flows = {f'{a}>{b}': _bis_rows(d, quarters) for (a, b), d in sorted(acc.items(), key=lambda kv: (pos[kv[0][0]], pos[kv[0][1]]))}
    pairs, oneway = {}, []
    for i, a in enumerate(BIS_ORDER):
        for b in BIS_ORDER[i + 1:]:
            d1, d2 = acc.get((a, b), {}), acc.get((b, a), {})
            if not d1 and not d2:
                continue
            m = {}
            for d in (d1, d2):
                for q, (v, n) in d.items():
                    s = m.setdefault(q, [0.0, 0]); s[0] += v; s[1] += n
            key = '|'.join(sorted((a, b)))    # jak klucze GLINK w index.html (a<b alfabetycznie)
            pairs[key] = _bis_rows(m, quarters)
            if not d1 or not d2:
                oneway.append(key)            # tylko jeden kierunek: druga strona nie ma banków raportujących
    net = {r: {} for r in BIS_ORDER}      # saldo na parach krajów, gdzie oba kraje raportują w danym kwartale
    for (rep, cp), ser in obs.items():
        a, b = c2r[rep], c2r[cp]
        back = obs.get((cp, rep))
        if a == b or rep > cp or not back:
            continue
        for q in quarters:
            if q in ser and q in back:
                d = ser[q] - back[q]
                s = net[a].setdefault(q, [0.0, 0]); s[0] += d; s[1] += 1
                s = net[b].setdefault(q, [0.0, 0]); s[0] -= d; s[1] += 1
    seen = {rep for (rep, _), ser in obs.items() if any(q in ser for q in quarters)}
    rep_q = {}                            # wkład kraju raportującego w wypływ regionu w ostatnim kwartale
    for (rep, cp), ser in obs.items():
        if c2r[rep] != c2r[cp] and last in ser:
            s = rep_q.setdefault(rep, [0.0, 0]); s[0] += ser[last]; s[1] += 1
    regions = {}
    for r in BIS_ORDER:
        out_d, in_d = {}, {}
        for (a, b), d in acc.items():
            tgt = out_d if a == r else in_d if b == r else None
            if tgt is None:
                continue
            for q, (v, n) in d.items():
                s = tgt.setdefault(q, [0.0, 0]); s[0] += v; s[1] += n
        reg = {'rep': [c for c in BIS_REP.get(r, []) if c in seen], 'cp': list(BIS_CP[r]),
               'out': _bis_rows(out_d, quarters), 'in': _bis_rows(in_d, quarters), 'net': _bis_rows(net[r], quarters),
               'rep_q': sorted(([c, round(rep_q[c][0], 1) + 0.0, rep_q[c][1]] for c in BIS_REP.get(r, []) if c in rep_q),
                               key=lambda x: -abs(x[1]))}
        for k in ('out', 'in', 'net'):
            reg[k + '4'] = _bis_total(reg[k])
        regions[r] = reg
    return {'at': at, 'src': 'BIS Locational Banking Statistics (WS_LBS_D_PUB), measure F: FX and break adjusted change',
            'url': 'https://data.bis.org/topics/LBS', 'api': BIS_URL, 'unit': 'mln USD', 'asof': last,
            'quarters': quarters, 'sign': BIS_SIGN,
            'no_reporter': [r for r in BIS_ORDER if not regions[r]['rep']],
            'regions': regions, 'flows': flows, 'pairs': pairs, 'oneway': oneway}


def build_bis():
    """data/bis.json — kwartalne przepływy bankowe BIS LBS między regionami strony (mln USD); jedno zapytanie bez klucza."""
    return parse_bis_flows(get_bytes(BIS_URL, timeout=90), NOW)


# --- v50: CFTC Commitments of Traders — Traders in Financial Futures (TFF), tylko futures; dane rządu USA (domena publiczna) ---
# Plik tygodniowy FinFutWk.txt nie ma nagłówka: kolejność 87 kolumn z dokumentacji CFTC (cotvariablestfm.html), sprawdzona
# 24.09.2026 z nagłówkiem pliku rocznego (identyczna). Stan na wtorek, publikacja zwykle w piątek ok. 19:30 UTC.
import zipfile   # v50 CFTC: plik roczny to archiwum zip (biblioteka standardowa)

CFTC_WEEK_URL = 'https://www.cftc.gov/dea/newcot/FinFutWk.txt'
CFTC_YEAR_URL = 'https://www.cftc.gov/files/dea/history/fut_fin_txt_{}.zip'
CFTC_HOME = 'https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm'
CFTC_MARKETS = {'eur': '099741', 'btc': '133741', 'eth': '146021'}   # EURO FX, BITCOIN, ETHER CASH SETTLED — wszystkie CME
CFTC_EXTRA = {'usd': '098662', 'jpy': '097741', 'gbp': '096742', 'chf': '092741', 'cad': '090741', 'aud': '232741', 'mxn': '095741',
              'brl': '102741', 'ust10': '043602', 'spx': '13874A', 'msciem': '244042'}   # v68: dodatkowe rynki z tych samych plików; brak = notatka
CFTC_WEEKS = 13
CFTC_SPAN_DAYS = CFTC_WEEKS * 7 - 1    # historia = raporty z 90 dni przed najnowszym (bez dziur na przełomie roku)
CFTC_KEEP_DAYS = 35                    # rynek nieobecny w obu plikach: poprzedni stan najwyżej 5 tygodni (jego data mówi, jak stary)
CFTC_GROUPS = (('dealer', 'Dealer_Positions', 'Dealer'), ('asset_mgr', 'Asset_Mgr_Positions', 'Asset_Mgr'),
               ('lev_funds', 'Lev_Money_Positions', 'Lev_Money'), ('other_rept', 'Other_Rept_Positions', 'Other_Rept'),
               ('nonrept', 'NonRept_Positions', 'NonRept'))
CFTC_COLS = tuple((
    'Market_and_Exchange_Names As_of_Date_In_Form_YYMMDD Report_Date_as_YYYY-MM-DD CFTC_Contract_Market_Code '
    'CFTC_Market_Code CFTC_Region_Code CFTC_Commodity_Code Open_Interest_All Dealer_Positions_Long_All Dealer_Positions_Short_All '
    'Dealer_Positions_Spread_All Asset_Mgr_Positions_Long_All Asset_Mgr_Positions_Short_All Asset_Mgr_Positions_Spread_All '
    'Lev_Money_Positions_Long_All Lev_Money_Positions_Short_All Lev_Money_Positions_Spread_All Other_Rept_Positions_Long_All '
    'Other_Rept_Positions_Short_All Other_Rept_Positions_Spread_All Tot_Rept_Positions_Long_All Tot_Rept_Positions_Short_All '
    'NonRept_Positions_Long_All NonRept_Positions_Short_All Change_in_Open_Interest_All Change_in_Dealer_Long_All '
    'Change_in_Dealer_Short_All Change_in_Dealer_Spread_All Change_in_Asset_Mgr_Long_All Change_in_Asset_Mgr_Short_All '
    'Change_in_Asset_Mgr_Spread_All Change_in_Lev_Money_Long_All Change_in_Lev_Money_Short_All Change_in_Lev_Money_Spread_All '
    'Change_in_Other_Rept_Long_All Change_in_Other_Rept_Short_All Change_in_Other_Rept_Spread_All Change_in_Tot_Rept_Long_All '
    'Change_in_Tot_Rept_Short_All Change_in_NonRept_Long_All Change_in_NonRept_Short_All Pct_of_Open_Interest_All '
    'Pct_of_OI_Dealer_Long_All Pct_of_OI_Dealer_Short_All Pct_of_OI_Dealer_Spread_All Pct_of_OI_Asset_Mgr_Long_All '
    'Pct_of_OI_Asset_Mgr_Short_All Pct_of_OI_Asset_Mgr_Spread_All Pct_of_OI_Lev_Money_Long_All Pct_of_OI_Lev_Money_Short_All '
    'Pct_of_OI_Lev_Money_Spread_All Pct_of_OI_Other_Rept_Long_All Pct_of_OI_Other_Rept_Short_All Pct_of_OI_Other_Rept_Spread_All '
    'Pct_of_OI_Tot_Rept_Long_All Pct_of_OI_Tot_Rept_Short_All Pct_of_OI_NonRept_Long_All Pct_of_OI_NonRept_Short_All '
    'Traders_Tot_All Traders_Dealer_Long_All Traders_Dealer_Short_All Traders_Dealer_Spread_All Traders_Asset_Mgr_Long_All '
    'Traders_Asset_Mgr_Short_All Traders_Asset_Mgr_Spread_All Traders_Lev_Money_Long_All Traders_Lev_Money_Short_All '
    'Traders_Lev_Money_Spread_All Traders_Other_Rept_Long_All Traders_Other_Rept_Short_All Traders_Other_Rept_Spread_All '
    'Traders_Tot_Rept_Long_All Traders_Tot_Rept_Short_All Conc_Gross_LE_4_TDR_Long_All Conc_Gross_LE_4_TDR_Short_All '
    'Conc_Gross_LE_8_TDR_Long_All Conc_Gross_LE_8_TDR_Short_All Conc_Net_LE_4_TDR_Long_All Conc_Net_LE_4_TDR_Short_All '
    'Conc_Net_LE_8_TDR_Long_All Conc_Net_LE_8_TDR_Short_All Contract_Units CFTC_Contract_Market_Code_Quotes CFTC_Market_Code_Quotes '
    'CFTC_Commodity_Code_Quotes CFTC_SubGroup_Code FutOnly_or_Combined').split())
_CFTC_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _cftc_int(token):
    """Liczba kontraktów: '  41113' → 41113; '.', '', 'nan', 'inf' i nie-liczba → None (nigdy 0)."""
    v = _num(token)
    try:
        return None if v is None else int(round(v))
    except (ValueError, OverflowError):
        return None


def _cftc_iso(day):
    """'RRRR-MM-DD' → datetime.date; zły format albo nieistniejąca data (np. 2026-13-45) → None."""
    if not isinstance(day, str) or not _CFTC_DATE.match(day):
        return None
    try:
        return datetime.date.fromisoformat(day)
    except ValueError:
        return None


def parse_cftc_csv(text, header=None, codes=None):
    """CSV CFTC TFF → {kod rynku: {data raportu: wiersz jako dict nazwa→tekst}}.
    header=None: pierwszy wiersz to nagłówek (plik roczny FinFutYY.txt); plik tygodniowy nie ma nagłówka — podaj CFTC_COLS.
    Wiersz z inną liczbą pól niż nagłówek jest pomijany (zmiana układu pliku ⇒ brak rynku i błąd, nigdy przesunięte liczby)."""
    codes = set(codes or list(CFTC_MARKETS.values()) + list(CFTC_EXTRA.values()))   # v68
    reader = csv.reader(io.StringIO(text))
    cols = [c.strip() for c in (header or next(reader, []))]
    need = {'Report_Date_as_YYYY-MM-DD', 'CFTC_Contract_Market_Code', 'Open_Interest_All'}
    need |= {f'{pos}_{side}_All' for _, pos, _ in CFTC_GROUPS for side in ('Long', 'Short')}
    missing = need - set(cols)
    if missing:
        raise RuntimeError('brak kolumn ' + ', '.join(sorted(missing))[:200])
    out = {}
    for parts in reader:
        if len(parts) != len(cols):
            continue
        r = {c: p.strip() for c, p in zip(cols, parts)}
        code, day = r['CFTC_Contract_Market_Code'], r['Report_Date_as_YYYY-MM-DD']
        if code not in codes or r.get('FutOnly_or_Combined', 'FutOnly') != 'FutOnly' or _cftc_iso(day) is None:
            continue
        out.setdefault(code, {})[day] = r
    return out


def cftc_record(r):
    """Jeden wiersz → liczby dla strony. net = long − short (spreading liczy się po obu stronach, więc się znosi);
    chg_net = zmiana long − zmiana short z kolumn CFTC „Change_in_…” (względem poprzedniego raportu). Brak = None."""
    g = {}
    for key, pos, chg in CFTC_GROUPS:
        lo, sh = _cftc_int(r.get(f'{pos}_Long_All')), _cftc_int(r.get(f'{pos}_Short_All'))
        clo, csh = _cftc_int(r.get(f'Change_in_{chg}_Long_All')), _cftc_int(r.get(f'Change_in_{chg}_Short_All'))
        g[key] = {'long': lo, 'short': sh,
                  'spread': None if key == 'nonrept' else _cftc_int(r.get(f'{pos}_Spread_All')),   # małe pozycje: CFTC nie dzieli
                  'net': lo - sh if lo is not None and sh is not None else None,
                  'chg_net': clo - csh if clo is not None and csh is not None else None}
    return {'date': r.get('Report_Date_as_YYYY-MM-DD'), 'name': r.get('Market_and_Exchange_Names', ''),
            'units': r.get('Contract_Units', ''), 'oi': _cftc_int(r.get('Open_Interest_All')),
            'oi_chg': _cftc_int(r.get('Change_in_Open_Interest_All')), 'g': g}


def cftc_consistent(rec):
    """Strażnik przesunięcia kolumn: suma long (i osobno short) wszystkich grup + spreading = open interest.
    W danych CFTC 2025–2026 różnica wynosi najwyżej 0,0014% (dla EUR/BTC/ETH zawsze 0); tolerancja 0,5%."""
    oi = rec['oi']
    if oi is None or oi <= 0:
        return False
    for side in ('long', 'short'):
        vals = [x[side] for x in rec['g'].values()] + [x['spread'] for k, x in rec['g'].items() if k != 'nonrept']
        if any(v is None for v in vals) or abs(sum(vals) - oi) > max(5, oi * 0.005):
            return False
    return True


def _cftc_hv(seq, i):
    """Wartość z poprzedniej historii: tylko liczba całkowita; inaczej brak (None), nigdy 0."""
    v = seq[i] if isinstance(seq, list) and i < len(seq) else None
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def build_cftc(fetch=None, today=None, prev=None):
    """data/cftc.json — pozycje grup uczestników (TFF, futures-only) dla EUR, BTC, ETH na CME: stan z ostatniego raportu
    (plik tygodniowy) + netto z raportów z ostatnich 90 dni (plik roczny; w styczniu dociągany też rok poprzedni).
    Każda część osobno: awaria pliku rocznego nie kasuje bieżącego tygodnia i odwrotnie. prev = poprzedni cftc.json ze strony:
    gdy rynku brak w obu plikach — zostaje poprzedni stan (kept=True, najwyżej 35 dni; jego asof mówi, jak stary); gdy historia
    jest krótsza niż 13 raportów — brakujące starsze tygodnie z okna 90 dni uzupełnia poprzednia historia. Gdy żaden rynek
    nie ma danych z tego pobrania — wyjątek (main zachowuje wtedy poprzedni plik z jego prawdziwym „at”)."""
    fetch = fetch or (lambda u: get_bytes(u, timeout=120))
    today = today or datetime.datetime.now(datetime.timezone.utc).date()
    errors = []
    week = {}
    try:
        week = parse_cftc_csv(fetch(CFTC_WEEK_URL).decode('utf-8', 'replace'), header=CFTC_COLS)
    except Exception as e:
        errors.append(f'CFTC tydzień: {e}')
    hist = {}

    def load_year(y):
        try:
            with zipfile.ZipFile(io.BytesIO(fetch(CFTC_YEAR_URL.format(y)))) as z:
                names = [n for n in z.namelist() if n.lower().endswith('.txt')]
                if not names:
                    raise RuntimeError('brak pliku .txt w archiwum')
                text = z.read(names[0]).decode('utf-8', 'replace')
            for code, rows in parse_cftc_csv(text).items():
                for day, r in rows.items():
                    hist.setdefault(code, {}).setdefault(day, r)
        except urllib.error.HTTPError as e:
            errors.append(f'CFTC rok {y}: HTTP {e.code}' + (' (w pierwszych dniach stycznia to normalne)' if e.code == 404 else ''))
        except Exception as e:
            errors.append(f'CFTC rok {y}: {e}')

    load_year(today.year)
    if any(len(set(hist.get(c, {})) | set(week.get(c, {}))) < CFTC_WEEKS + 1 for c in CFTC_MARKETS.values()):
        load_year(today.year - 1)
    fields = ['oi'] + [gk for gk, _, _ in CFTC_GROUPS]
    markets = {}
    notes = []   # v68: problemy dodatkowych rynków to notatki, nie błędy
    for key, code in list(CFTC_MARKETS.items()) + list(CFTC_EXTRA.items()):
        rows = dict(hist.get(code, {}))
        rows.update(week.get(code, {}))           # ten sam tydzień: wygrywa plik tygodniowy (liczby są identyczne)
        recs = []
        for day in sorted(rows):
            rec = cftc_record(rows[day])
            if cftc_consistent(rec):
                recs.append(rec)
            else:
                (errors if key in CFTC_MARKETS else notes).append(f'CFTC {key} {day}: suma pozycji ≠ open interest — wiersz pominięty')
        if recs:                                  # rok poprzedni (lub stara historia) nie może wejść do „13 tygodni” z dziurą
            last_d = _cftc_iso(recs[-1]['date'])
            recs = [x for x in recs if (last_d - _cftc_iso(x['date'])).days <= CFTC_SPAN_DAYS]
        prev_m = ((prev.get('markets') or {}).get(key) if isinstance(prev.get('markets'), dict) else None) if isinstance(prev, dict) else None
        prev_m = prev_m if isinstance(prev_m, dict) else None
        if not recs:
            (errors if key in CFTC_MARKETS else notes).append(f'CFTC {key}: brak rynku {code} w raporcie')
            pd = _cftc_iso(prev_m.get('asof')) if prev_m else None
            kept_m = dict(prev_m, kept=True) if pd and 0 <= (today - pd).days <= CFTC_KEEP_DAYS else None
            if kept_m is not None or key in CFTC_MARKETS:   # v68: brakujący dodatkowy rynek w ogóle nie trafia do pliku
                markets[key] = kept_m
            continue
        last = recs[-1]
        last_d = _cftc_iso(last['date'])
        before = recs[-2] if len(recs) > 1 and (last_d - _cftc_iso(recs[-2]['date'])).days <= 10 else None
        for gk, x in last['g'].items():           # zapas: gdy CFTC nie podał zmiany, różnica do poprzedniego raportu
            if x['chg_net'] is None and before and x['net'] is not None and before['g'][gk]['net'] is not None:
                x['chg_net'] = x['net'] - before['g'][gk]['net']
        if last['oi_chg'] is None and before and before['oi'] is not None:
            last['oi_chg'] = last['oi'] - before['oi']
        byday = {}
        ph = prev_m.get('hist') if prev_m and len(recs) < CFTC_WEEKS else None
        if isinstance(ph, dict) and isinstance(ph.get('dates'), list):
            for i, day in enumerate(ph['dates']):
                d = _cftc_iso(day)
                if d and day < recs[0]['date'] and (last_d - d).days <= CFTC_SPAN_DAYS:   # starsze niż pobrane, w oknie 90 dni
                    byday[day] = {f: _cftc_hv(ph.get(f), i) for f in fields}
        for r in recs:
            byday[r['date']] = dict({'oi': r['oi']}, **{gk: r['g'][gk]['net'] for gk, _, _ in CFTC_GROUPS})
        days = sorted(byday)[-CFTC_WEEKS:]
        h = {'dates': days}
        for f in fields:
            h[f] = [byday[d][f] for d in days]
        markets[key] = {'code': code, 'name': last['name'], 'units': last['units'], 'asof': last['date'],
                        'in_week_file': last['date'] in week.get(code, {}), 'oi': last['oi'], 'oi_chg': last['oi_chg'],
                        'groups': {gk: {k: v for k, v in x.items() if k in ('long', 'short', 'spread', 'net', 'chg_net')}
                                   for gk, x in last['g'].items()},
                        'hist': h}
    for e in errors:
        META['errors'].append(mask(e))
    for n in notes:
        META['notes'].append(mask(n))
    live = [m for m in markets.values() if m]
    if not any(not m.get('kept') for m in live):
        raise RuntimeError('żaden rynek nie ma danych z tego pobrania (szczegóły w osobnych błędach CFTC)')
    return {'at': NOW, 'src': 'CFTC — Commitments of Traders: Traders in Financial Futures (futures only)',
            'url': CFTC_HOME, 'data_url': CFTC_WEEK_URL, 'unit': 'kontrakty', 'asof': max(m['asof'] for m in live),
            'net': 'long − short; spreading is counted on both sides and cancels out',
            'order': [gk for gk, _, _ in CFTC_GROUPS], 'markets': markets}


# --- Coin Metrics Community (bez klucza): przepływy BTC i ETH na giełdy i z giełd, zapas na giełdach -------------------
# Licencja danych: CC BY-NC 4.0 (docs.coinmetrics.io/api/v4 → „Available to the community under the Creative Commons
# license” z linkiem do by-nc/4.0; github.com/coinmetrics/data/LICENSE). Limit Community: 10 zapytań / 6 s na IP.
# Jedno zapytanie na przebieg: 2 aktywa × 6 metryk × 36 dni (limit_per_asset + paging_from=end → rosnąco po dacie).
# 36, nie 35: limit liczy też najnowszy dzień, który Coin Metrics jeszcze publikuje (ok. 02–03 UTC). Gdy parser cofa się
# wtedy do ostatniego pełnego dnia, okno 35 dni nadal jest pełne — inaczej najstarszy dzień okna byłby fałszywą „luką”.
CM_ASSETS = ('btc', 'eth')
CM_DAYS = 35
CM_METRICS = (('in', 'FlowInExNtv'), ('out', 'FlowOutExNtv'), ('in_usd', 'FlowInExUSD'),
              ('out_usd', 'FlowOutExUSD'), ('sply', 'SplyExNtv'), ('sply_usd', 'SplyExUSD'))
CM_URL = ('https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=' + ','.join(CM_ASSETS)
          + '&metrics=' + ','.join(m for _, m in CM_METRICS)
          + f'&frequency=1d&limit_per_asset={CM_DAYS + 1}&paging_from=end&page_size=1000'
          # metryka przeniesiona do planu płatnego nie zwraca wtedy 400 dla CAŁEGO zapytania (sprawdzone 24.09.2026)
          + '&ignore_unsupported_errors=true')
CM_LICENSE_URL = 'https://creativecommons.org/licenses/by-nc/4.0/'
CM_ATTR = ('Source: Coin Metrics Community Network Data (https://coinmetrics.io), licensed under CC BY-NC 4.0 '
           '(https://creativecommons.org/licenses/by-nc/4.0/). Net flows and 7/30-day sums computed by CapitalFlowAI. '
           'Coin Metrics does not endorse this site.')
CM_COLS = ['date', 'in', 'out', 'net', 'in_usd', 'out_usd', 'net_usd', 'sply', 'sply_usd']


def _cm_val(v):
    """Liczba z tekstu Coin Metrics ('28280.09508818'); brak, nie-liczba, nan/inf albo wartość ujemna → None (nigdy 0).
    Przepływy i zapas na giełdach nie mogą być ujemne — ujemna liczba to błąd dostawcy, nie pomiar."""
    if v is None or isinstance(v, bool):
        return None
    x = _num(v)
    if x is None or x != x or x in (float('inf'), float('-inf')) or x < 0:
        return None
    return x


def _cm_round(key, v):
    if v is None:
        return None
    return int(round(v)) if key.endswith('_usd') else round(v, 2)


def _cm_sum(by_day, last, days, key):
    """Suma `key` z `days` kolejnych dni kalendarzowych kończących się na `last`; brak choćby jednego dnia → None."""
    d0 = datetime.date.fromisoformat(last)
    total = 0.0
    for i in range(days):
        v = by_day.get((d0 - datetime.timedelta(days=i)).isoformat(), {}).get(key)
        if v is None:
            return None
        total += v
    return total


def _cm_net(rec, a, b):
    return rec[a] - rec[b] if rec.get(a) is not None and rec.get(b) is not None else None


def parse_cm_asset(rows, asset):
    """Wiersze jednego aktywa → {'sym','asof','status','pending','d','missing','last','sum7','sum30','sply_ch7','sply_ch30'};
    None gdy brak dni. d: CM_DAYS dni kalendarzowych rosnąco kończących się na ostatnim dniu z danymi; dzień bez wiersza = same None.
    Netto liczone z liczb niezaokrąglonych (dopiero wynik jest zaokrąglany)."""
    by_day, status = {}, {}
    for r in rows:
        if not isinstance(r, dict) or r.get('asset') != asset:
            continue
        day = str(r.get('time', ''))[:10]
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', day):
            continue
        try:
            datetime.date.fromisoformat(day)      # np. '2026-02-30' przechodzi przez wzorzec, ale nie jest datą
        except ValueError:
            continue
        rec = {k: _cm_val(r.get(m)) for k, m in CM_METRICS}
        if all(v is None for v in rec.values()):
            continue
        rec['net'] = _cm_net(rec, 'in', 'out')
        rec['net_usd'] = _cm_net(rec, 'in_usd', 'out_usd')
        by_day[day] = rec
        status[day] = {str(r.get(m + '-status')) for _, m in CM_METRICS if r.get(m) is not None and r.get(m + '-status')}
    if not by_day:
        return None
    last = max(by_day)
    # Metryki nowego dnia pojawiają się po kolei (natywne od ok. 01:10 UTC, USD do ~70 min później). Gdy najnowszy dzień
    # jest jeszcze niepełny, a dzień wcześniej jest pełny — pokazujemy ten pełny (inaczej USD i sumy 7/30 dni = null
    # przez ~1 h dziennie, a BTC i ETH mogą mieć różne daty). Starsza luka niż 1 dzień = zmiana u dostawcy → bez cofania.
    full = [day for day, rec in by_day.items() if all(rec[k] is not None for k, _ in CM_METRICS)]
    pending = None
    if full and last not in full and (datetime.date.fromisoformat(last) - datetime.date.fromisoformat(max(full))).days == 1:
        pending, last = last, max(full)
    d0 = datetime.date.fromisoformat(last)
    cal = [(d0 - datetime.timedelta(days=i)).isoformat() for i in range(CM_DAYS - 1, -1, -1)]
    d = [[day] + [_cm_round(k, by_day.get(day, {}).get(k)) for k in CM_COLS[1:]] for day in cal]
    st = status.get(last, set())
    out = {'sym': asset.upper(), 'asof': last,
           # 'flash' = wstępne (Coin Metrics może je poprawić), 'reviewed' = po przeglądzie; mieszane → 'flash'
           'status': 'flash' if 'flash' in st else ('reviewed' if st == {'reviewed'} else None),
           'pending': pending,   # najnowszy dzień, który Coin Metrics jeszcze publikuje (pominięty), albo null
           'd': d, 'missing': sum(1 for day in cal if day not in by_day),
           'last': {k: _cm_round(k, by_day[last].get(k)) for k in CM_COLS[1:]}}
    flow_keys = ('in', 'out', 'net', 'in_usd', 'out_usd', 'net_usd')
    for n in (7, 30):
        out[f'sum{n}'] = {k: _cm_round(k, _cm_sum(by_day, last, n, k)) for k in flow_keys}
        now_s = by_day[last].get('sply')
        then_s = by_day.get((d0 - datetime.timedelta(days=n)).isoformat(), {}).get('sply')
        ch = (now_s - then_s) if now_s is not None and then_s is not None else None
        out[f'sply_ch{n}'] = {'ntv': _cm_round('sply', ch),
                              'pct': round(ch / then_s * 100, 2) if ch is not None and then_s else None}
    return out


def parse_cm(j):
    """Coin Metrics /timeseries/asset-metrics → data/cm.json. Każde aktywo osobno: brak jednego nie kasuje drugiego."""
    if isinstance(j, dict) and isinstance(j.get('error'), dict):
        raise RuntimeError('Coin Metrics: ' + str(j['error'].get('message', j['error']))[:200])
    rows = j.get('data') if isinstance(j, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError('Coin Metrics: brak pola data')
    if j.get('next_page_token'):
        META['errors'].append('Coin Metrics: odpowiedź podzielona na strony — użyto tylko pierwszej')
    seen = {m for r in rows if isinstance(r, dict) for _, m in CM_METRICS if r.get(m) is not None}
    for _, m in CM_METRICS:
        if m not in seen:
            META['errors'].append(f'Coin Metrics: brak metryki {m} w odpowiedzi')
    out = {'at': NOW, 'src': 'Coin Metrics Community Network Data — API v4 asset-metrics (exchange flows)',
           'url': 'https://docs.coinmetrics.io/api/v4/', 'home': 'https://coinmetrics.io',
           'license': 'CC BY-NC 4.0', 'license_url': CM_LICENSE_URL, 'attribution': CM_ATTR,
           'unit': {'ntv': 'native units (BTC, ETH)', 'usd': 'USD'},
           'sign': 'net = in - out; positive = more coins sent to exchanges than withdrawn (excl. exchange-to-exchange)',
           'cols': CM_COLS, 'asof': None, 'assets': {}}
    for a in CM_ASSETS:
        out['assets'][a] = parse_cm_asset(rows, a)
        if out['assets'][a] is None:
            META['errors'].append(f'Coin Metrics: brak dni dla {a}')
    dates = sorted({v['asof'] for v in out['assets'].values() if v})
    if not dates:
        raise RuntimeError('Coin Metrics: żadne aktywo nie ma danych')
    out['asof'] = dates[0] if len(dates) == 1 else f'{dates[0]} – {dates[-1]}'
    return out


def build_cm():
    """data/cm.json — jedno zapytanie bez klucza do Coin Metrics Community (limit 10 zapytań / 6 s na IP)."""
    return parse_cm(get_json(CM_URL))


# --- v50: Fed H.4.1 — papiery w depozycie Fed dla zagranicznych instytucji oficjalnych i międzynarodowych (serie w FRED_SERIES) ---
FRED_CUSTODY = ('WSEFINTL1', 'WMTSECL1', 'WFASECL1', 'WSEFINOL')   # razem; w tym Skarb USA; agencje i MBS; pozostałe
CUSTODY_TOL = 5     # mln USD: części H.4.1 są zaokrąglane („Components may not sum to totals because of rounding”)


def _fed_day_back(date_str, days):
    return (datetime.date.fromisoformat(date_str) - datetime.timedelta(days=days)).isoformat()


def custody_summary(series):
    """Z out['series'] build_fred: stan środowy (H.4.1, Table 1A, Wednesday level) papierów w depozycie Fed dla zagranicznych
    instytucji oficjalnych. Zmiany tylko względem DOKŁADNIE tej samej środy 1/4/52 tygodnie wcześniej (brak takiej środy = None,
    nigdy 0 i nigdy starszy tydzień); części (Skarb USA, agencje/MBS, pozostałe) tylko z tej samej daty co suma."""
    fin = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf')) else None
    tot = (series or {}).get('WSEFINTL1') or {}
    rows = sorted([[d, v] for d, v in (tot.get('d') or []) if fin(v) is not None], key=lambda r: r[0])
    if not rows:
        return None
    idx = {sid: {d: fin(v) for d, v in (((series or {}).get(sid) or {}).get('d') or [])} for sid in FRED_CUSTODY}
    asof, total = rows[-1]
    at = lambda sid, day: idx[sid].get(day)
    out = {'asof': asof, 'unit': 'mln USD', 'total': total, 'ust': at('WMTSECL1', asof),
           'agency': at('WFASECL1', asof), 'other': at('WSEFINOL', asof)}
    for key, days in (('d1w', 7), ('d4w', 28), ('d52w', 364)):
        day = _fed_day_back(asof, days)
        p = at('WSEFINTL1', day)
        out[key] = None if p is None else round(total - p, 1)
        u0, u1 = at('WMTSECL1', day), out['ust']
        out['ust_' + key] = None if u0 is None or u1 is None else round(u1 - u0, 1)
    out['ust_share_pct'] = round(100.0 * out['ust'] / total, 1) if out['ust'] is not None and total else None
    parts = [out['ust'], out['agency'], out['other']]
    out['parts_ok'] = None if any(p is None for p in parts) else abs(sum(parts) - total) <= CUSTODY_TOL
    year = [r for r in rows if r[0] >= _fed_day_back(asof, 364)]
    lo = min(year, key=lambda r: r[1]); hi = max(year, key=lambda r: r[1])
    out['lo52'] = [lo[0], lo[1]]; out['hi52'] = [hi[0], hi[1]]; out['n52'] = len(year)
    return out


# --- v50: rezerwy walutowe dużych posiadaczy — MFW (IMF), International Liquidity (IL), API SDMX 3.0 bez klucza ---
# Warunki MFW („The Use of IMF Data”): wolno pobierać i publikować z atrybucją „Source: International Monetary Fund, <baza>”;
# przekształcenie trzeba oznaczyć (strona: mld USD, złoto jako różnica, zmiany liczone przez stronę).
RES_COUNTRIES = ['CHN', 'JPN', 'CHE', 'IND', 'TWN', 'SAU', 'KOR', 'BRA']
RES_NAMES = {'CHN': ('Chiny', 'China'), 'JPN': ('Japonia', 'Japan'), 'CHE': ('Szwajcaria', 'Switzerland'),
             'IND': ('Indie', 'India'), 'TWN': ('Tajwan', 'Taiwan'), 'SAU': ('Arabia Saudyjska', 'Saudi Arabia'),
             'KOR': ('Korea Płd.', 'Korea'), 'BRA': ('Brazylia', 'Brazil')}
RES_IND = {'TRGMV_REVS': 'total', 'RXF11_REVS': 'ex_gold', 'RXF11FX_REVS': 'fx'}   # razem ze złotem rynkowo; bez złota; waluty obce
IMF_IL_URL = ('https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IL/+/'
              + '+'.join(RES_COUNTRIES) + '.' + '+'.join(RES_IND) + '.USD.M?lastNObservations=13')
IMF_IL_PAGE = 'https://data.imf.org/en/datasets/IMF.STA:IL'
IMF_IL_SRC = 'International Monetary Fund, International Liquidity (IL)'
_IMF_PERIOD = re.compile(r'^(\d{4})-M?(\d{2})$')


def _imf_month(p):
    """'2026-M06' albo '2026-06' → '2026-06'; inny zapis → None."""
    m = _IMF_PERIOD.match(str(p or '').strip())
    return f'{m.group(1)}-{m.group(2)}' if m and 1 <= int(m.group(2)) <= 12 else None


def _imf_month_add(ym, k):
    t = int(ym[:4]) * 12 + int(ym[5:7]) - 1 + k
    return f'{t // 12:04d}-{t % 12 + 1:02d}'


def parse_imf_sdmx(j, norm=None):
    """SDMX-JSON 2.0 z API MFW 3.0: {(kod wymiaru 1, 2, …): [[YYYY-MM, liczba]]} rosnąco. Klucz serii '0:2:0:0' = indeksy
    wartości wymiarów wg keyPosition; obserwacja [OBS_VALUE, atrybuty…]; wartość pusta / nie-liczba / NaN pominięta (nigdy 0).
    Brak jakiejkolwiek serii = błąd (API odpowiada 200 bez 'series')."""
    try:
        st = j['data']['structures'][0]; ds = j['data']['dataSets'][0]
        sdims = sorted(st['dimensions']['series'], key=lambda d: d.get('keyPosition', 0))
        periods = [v.get('value') or v.get('id') for v in st['dimensions']['observation'][0]['values']]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f'nieznany kształt odpowiedzi ({e})')
    out = {}
    for key, s in (ds.get('series') or {}).items():
        try:
            lab = tuple(sdims[i]['values'][int(n)]['id'] for i, n in enumerate(key.split(':')))
        except (IndexError, ValueError, KeyError):
            continue
        rows = []
        for oi, ov in ((s or {}).get('observations') or {}).items():
            try:
                per = (norm or _imf_month)(periods[int(oi)])   # v59: norm — np. kwartały COFER
            except (IndexError, ValueError):
                continue
            v = _num(ov[0]) if isinstance(ov, list) and ov and ov[0] is not None else None
            if v is not None and (v != v or v in (float('inf'), float('-inf'))):
                v = None      # 'NaN' / 'inf' = brak — nigdy NaN w JSON (JSON.parse na stronie by padł)
            if per is not None and v is not None:
                rows.append([per, v])
        if rows:
            out[lab] = sorted(rows)
    if not out:
        raise RuntimeError('brak serii z wartościami')
    return out


def parse_rezerwy(j):
    """IL → rezerwy 8 gospodarek w mld USD. total = rezerwy razem ze złotem po cenie rynkowej (TRGMV), ex_gold = bez złota
    (RXF11), fx = waluty obce (RXF11FX), gold = total − ex_gold (wyliczenie strony). Każdy kraj ma własny miesiąc 'asof'
    (MFW publikuje z różnym opóźnieniem); części i porównania tylko z dokładnie tego miesiąca (i 1/12 mies. wcześniej).
    Kraj bez sumy → 'missing' (nie zero)."""
    ser = parse_imf_sdmx(j)
    r1 = lambda v: None if v is None else round(v / 1e9, 1)
    countries, missing = {}, []
    for c in RES_COUNTRIES:
        by = {k: dict(ser.get((c, code, 'USD', 'M')) or []) for code, k in RES_IND.items()}
        if not by['total']:
            missing.append(c); continue
        tot_rows = sorted(by['total'].items())
        asof, total = tot_rows[-1]
        ex_gold, fx = by['ex_gold'].get(asof), by['fx'].get(asof)
        p1, p12 = by['total'].get(_imf_month_add(asof, -1)), by['total'].get(_imf_month_add(asof, -12))
        countries[c] = {'pl': RES_NAMES[c][0], 'en': RES_NAMES[c][1], 'asof': asof, 'total': r1(total), 'ex_gold': r1(ex_gold),
                        'fx': r1(fx), 'gold': None if ex_gold is None else r1(total - ex_gold),
                        'd1m': None if p1 is None else r1(total - p1), 'd12m': None if p12 is None else r1(total - p12),
                        'p12m': None if not p12 else round(100.0 * (total - p12) / p12, 1),
                        'd': [[m, r1(v)] for m, v in tot_rows]}
    if not countries:
        raise RuntimeError('żaden kraj bez sumy rezerw')
    tots = sorted(v['total'] for v in countries.values())
    if tots[len(tots) // 2] < 1:      # mediana < 1 mld USD: wartości nie są w dolarach (zmiana SCALE?) — nie pokazujemy źle
        raise RuntimeError('wartości wyglądają na przeskalowane (atrybut SCALE) — sprawdź jednostkę')
    order = sorted(countries, key=lambda c: -countries[c]['total'])
    months = [countries[c]['asof'] for c in countries]
    return {'src': IMF_IL_SRC, 'url': IMF_IL_PAGE, 'unit': 'mld USD', 'asof_min': min(months), 'asof_max': max(months),
            'order': order, 'countries': countries, 'missing': missing,
            'note': 'gold = total − ex_gold (wyliczenie strony z danych MFW); zmiana zawiera wycenę walut i złota'}


def build_rezerwy():
    """data/rezerwy.json — jedno zapytanie do API MFW (bez klucza); dane miesięczne, w main() najwyżej raz na dobę."""
    out = parse_rezerwy(get_json(IMF_IL_URL, {'Accept': 'application/json'}))
    out['at'] = NOW
    return out


# BIS — stopy procentowe banków centralnych (WS_CBPOL), bez klucza; dzienne (stan) + miesięczne (historia zmian)
CBPOL_AREAS = ['US', 'XM', 'GB', 'CH', 'SE', 'NO', 'PL', 'JP', 'KR', 'CN', 'IN', 'ID', 'AU', 'CA', 'BR', 'MX', 'ZA', 'TR', 'SA', 'RU']
CBPOL_BASE = 'https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/'


def parse_cbpol_csv(raw):
    """CSV BIS (pola w cudzysłowach, długie opisy) → {kraj: [[okres, stopa %], ...]} rosnąco; NaN / status braku = pominięte."""
    text = raw.decode('utf-8', errors='replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        area = (r.get('REF_AREA') or '').strip(); per = (r.get('TIME_PERIOD') or '').strip()
        if not area or not re.match(r'^\d{4}-\d{2}(-\d{2})?$', per):
            continue
        if (r.get('OBS_STATUS') or '').strip() in ('H', 'K', 'L', 'M', 'Q'):
            continue
        v = _num(r.get('OBS_VALUE'))
        if v is None or v != v or v in (float('inf'), float('-inf')):
            continue
        out.setdefault(area, []).append([per, v])
    for a in out:
        out[a].sort(key=lambda x: x[0])
    if not out:
        raise RuntimeError('brak obserwacji w odpowiedzi')
    return out


def cbpol_summary(daily, monthly):
    """Stan (ostatnia wartość dzienna), zmiana od 12 miesięcy, ostatnia zmiana (miesiąc, o ile pkt proc.), różnica wobec Fed."""
    rows = {}
    for a in CBPOL_AREAS:
        d = daily.get(a) or []; m = monthly.get(a) or []
        if not d and not m:
            continue
        rate, date = (d[-1][1], d[-1][0]) if d else (m[-1][1], m[-1][0])
        cur_m = date[:7]
        y, mo = int(cur_m[:4]), int(cur_m[5:7])
        ago = f'{y - 1:04d}-{mo:02d}'
        base = [v for p, v in m if p <= ago]
        d12 = round(rate - base[-1], 4) if base else None
        last = None   # (miesiąc, zmiana) — przeszukanie od najnowszego: wartość dzienna vs ostatni miesiąc, potem miesiąc do miesiąca
        seq = [v for p, v in m if p < cur_m] + [rate]
        per = [p for p, v in m if p < cur_m] + [cur_m]
        for i in range(len(seq) - 1, 0, -1):
            if abs(seq[i] - seq[i - 1]) > 1e-9:
                last = [per[i], round(seq[i] - seq[i - 1], 4)]; break
        rows[a] = {'rate': rate, 'date': date, 'd12': d12, 'last': last, 'm_n': len(m)}   # v63: ile miesięcy historii (bez historii nie ma „bez zmian”)
    us = rows.get('US', {}).get('rate')
    for a, r in rows.items():
        r['vs_us'] = round(r['rate'] - us, 4) if us is not None else None
    return rows


def build_stopy():
    """data/stopy.json — stopy banków centralnych (BIS WS_CBPOL): dzienne 15 obserwacji (ostatnia ważna), miesięczne 25."""
    keys = '+'.join(CBPOL_AREAS)
    daily = parse_cbpol_csv(get_bytes(CBPOL_BASE + f'D.{keys}?lastNObservations=15&format=csv', timeout=90))
    try:
        monthly = parse_cbpol_csv(get_bytes(CBPOL_BASE + f'M.{keys}?lastNObservations=25&format=csv', timeout=90))
    except Exception as e:
        META['errors'].append(mask(f'BIS stopy (miesięczne): {e}')); monthly = {}
    rows = cbpol_summary(daily, monthly)
    if not rows:
        raise RuntimeError('BIS stopy: żadna gospodarka')
    return {'at': NOW, 'src': 'BIS — Central bank policy rates (WS_CBPOL)', 'url': 'https://data.bis.org/topics/CBPOL', 'unit': '% rocznie',
            'asof': max(r['date'] for r in rows.values()), 'order': [a for a in CBPOL_AREAS if a in rows], 'rows': rows}


# EBC — średnie miesięczne kursy referencyjne (EXR), bez klucza: kurs z tych samych miesięcy co średni indeks OECD na mapie
EXR_CUR = ['USD', 'CAD', 'BRL', 'MXN', 'GBP', 'CHF', 'SEK', 'PLN', 'TRY', 'ILS', 'ZAR', 'INR', 'CNY', 'HKD', 'JPY', 'KRW',
           'IDR', 'SGD', 'THB', 'MYR', 'PHP', 'AUD', 'NZD']
EXR_URL = ('https://data-api.ecb.europa.eu/service/data/EXR/M.' + '+'.join(EXR_CUR)
           + '.EUR.SP00.A?lastNObservations=15&format=csvdata')


def parse_exr_csv(raw):
    """CSV EBC (EXR, miesięczne średnie) → {waluta: [[RRRR-MM, jednostek waluty za 1 EUR], ...]} rosnąco; brak/0 = pominięte."""
    text = raw.decode('utf-8', errors='replace') if isinstance(raw, (bytes, bytearray)) else str(raw)
    out = {}
    for r in csv.DictReader(io.StringIO(text)):
        cur = (r.get('CURRENCY') or '').strip(); per = (r.get('TIME_PERIOD') or '').strip()
        if not cur or not re.match(r'^\d{4}-\d{2}$', per):
            continue
        v = _num(r.get('OBS_VALUE'))
        if v is None or v != v or v <= 0 or v == float('inf'):
            continue
        out.setdefault(cur, []).append([per, round(v, 6)])
    for c in out:
        out[c].sort(key=lambda x: x[0])
    if not out.get('USD'):
        raise RuntimeError('brak kursu USD w odpowiedzi')
    return out


def build_kursy():
    """data/kursy.json — średnie miesięczne kursów EBC (15 miesięcy) dla walut regionów mapy."""
    m = parse_exr_csv(get_bytes(EXR_URL, timeout=90))
    return {'at': NOW, 'src': 'ECB — euro foreign exchange reference rates, monthly averages (EXR)',
            'url': 'https://data.ecb.europa.eu/data/datasets/EXR', 'unit': 'jednostek waluty za 1 EUR, średnia miesiąca',
            'asof': m['USD'][-1][0], 'm': m}


# v54: ZMIERZONE dzienne przepływy inwestorów zagranicznych — Indie (NSDL, FPI) i Tajwan (TWSE), bez klucza
import html as _html   # biblioteka standardowa: encje w tabeli HTML NSDL
NSDL_URL = 'https://www.fpi.nsdl.co.in/web/Reports/Monthly.aspx'
TWSE_URL = 'https://www.twse.com.tw/rwd/en/fund/BFI82U?type=day&dayDate={d}&response=json'
TWSE_SLEEP = 2.0          # TWSE blokuje szybkie serie zapytań (ok. 3 na 5 s)
TWSE_MAX = 30             # najwyżej tyle dni na jeden przebieg (pierwszy przebieg: ok. 25 dni sesyjnych)
OBCE_KEEP = 100           # tyle ostatnich dni trzyma plik (historia narasta z przebiegu na przebieg)
NSDL_CATS = {'equity': 'eq', 'debt-general limit': 'debt', 'debt-vrr': 'debt', 'debt-far': 'debt', 'hybrid': 'hyb',
             'mutual funds': 'mf', 'aifs': 'aif'}


def _nsdl_num(tok):
    """'1,705.34' → 1705.34; '(126.43)' → -126.43 (nawias = minus); brak → None."""
    t = str(tok).replace(',', '').strip()
    neg = t.startswith('(') and t.endswith(')')
    try:
        v = float(t.strip('()').strip())
    except ValueError:
        return None
    return -v if neg else v


def parse_nsdl_html(text):
    """Tabela NSDL „Daily Trends in FPI Investments” → [[data, akcje, dług, hybrydy, razem, INR za USD], ...] w mln USD.
    Dług = Debt-General Limit + Debt-VRR + Debt-FAR; tabela instrumentów pochodnych (dalej na stronie) pominięta."""
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', text, flags=re.S | re.I)
    days, date, cat = {}, None, None
    for r in re.findall(r'<tr[^>]*>(.*?)</tr>', t, flags=re.S | re.I):
        cells = [re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', '', c))).strip()
                 for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', r, flags=re.S | re.I)]
        if not any(cells):
            continue
        if any('derivative' in c.lower() for c in cells):
            break
        if re.match(r'^\d{2}-[A-Za-z]{3}-\d{4}$', cells[0]):
            date = datetime.datetime.strptime(cells[0], '%d-%b-%Y').date().isoformat(); cells = cells[1:]; cat = None
            d = days.setdefault(date, {})
            if cells and cells[-1].lower().startswith('rs'):
                m = re.search(r'(\d+(?:\.\d+)?)', cells[-1])
                if m:
                    d['inr'] = float(m.group(1))
                cells = cells[:-1]
        if date is None or not cells:
            continue
        d = days[date]
        if cells[0].lower() == 'total' and len(cells) >= 5:
            d['tot'] = _nsdl_num(cells[4]); continue
        if cells[0].lower() in NSDL_CATS:
            cat = NSDL_CATS[cells[0].lower()]; cells = cells[1:]
        if cells and cells[0].lower() == 'sub-total' and cat and len(cells) >= 5:
            v = _nsdl_num(cells[4])
            if v is not None:
                d[cat] = round(d.get(cat, 0.0) + v, 2)
    out = [[k, days[k].get('eq'), days[k].get('debt'), days[k].get('hyb'), days[k].get('tot'), days[k].get('inr')]
           for k in sorted(days) if days[k].get('eq') is not None and days[k].get('tot') is not None]
    if not out:
        raise RuntimeError('brak dni w tabeli')
    return out


def parse_twse(j):
    """TWSE BFI82U (jeden dzień) → [data, zagraniczni, fundusze krajowe (SITC), dealerzy, razem] w mln TWD; brak sesji → None."""
    if not isinstance(j, dict) or j.get('stat') != 'OK' or not isinstance(j.get('data'), list):
        return None
    ds = str(j.get('date') or '')
    if not re.match(r'^\d{8}$', ds):
        return None
    fx = it = dl = tot = None
    for row in j['data']:
        if not isinstance(row, list) or len(row) < 4:
            continue
        name, v = str(row[0]).strip().lower(), _num(row[3])
        if v is None:
            continue
        if name.startswith('foreign'):
            fx = (fx or 0.0) + v          # inwestorzy zagraniczni (z Chin kontynentalnych) + zagraniczni dealerzy
        elif name.startswith('securities investment trust'):
            it = v
        elif name.startswith('dealers'):
            dl = (dl or 0.0) + v
        elif name.startswith('total'):
            tot = v
    if fx is None:
        return None
    m = lambda v: None if v is None else round(v / 1e6, 1)
    return [f'{ds[:4]}-{ds[4:6]}-{ds[6:]}', m(fx), m(it), m(dl), m(tot)]


def tw_dates(have, empty, now_tpe, first):
    """Dni robocze do pobrania z TWSE: brakujące w pliku, bez znanych dni bez sesji; dziś dopiero po 16:00 czasu Tajpej."""
    today = now_tpe.date(); out = []
    for i in range(35 if first else 10, -1, -1):
        d = today - datetime.timedelta(days=i)
        iso = d.isoformat()
        if d.weekday() >= 5 or iso in have or iso in empty or (d == today and now_tpe.hour < 16):
            continue
        out.append(iso)
    return out


def twd_rates(key):
    """FRED DEXTAUS (TWD za 1 USD, Fed H.10) → {data: kurs}; '.' = brak."""
    j = get_json(f'{FRED}?series_id=DEXTAUS&api_key={key}&file_type=json&sort_order=desc&limit=60')
    out = {}
    for o in j.get('observations', []) if isinstance(j, dict) else []:
        v = _num(o.get('value'))
        if v and v > 0 and re.match(r'^\d{4}-\d{2}-\d{2}$', str(o.get('date', ''))):
            out[o['date']] = v
    return out


def _now_utc():
    return datetime.datetime.now(datetime.timezone.utc)   # osobno, żeby testy mogły ustawić czas


def _rate_for(rates, day):
    ks = [k for k in rates if k <= day] or []
    return (max(ks), rates[max(ks)]) if ks else (None, None)


def _rows(prev_part):
    return {r[0]: r for r in (prev_part or {}).get('d', []) if isinstance(r, list) and r and isinstance(r[0], str)}


def nsdl_part(prev_in):
    rows = parse_nsdl_html(get_bytes(NSDL_URL, timeout=60).decode('utf-8', 'replace'))
    m = _rows(prev_in); m.update({r[0]: r for r in rows})
    d = [m[k] for k in sorted(m)][-OBCE_KEEP:]
    return {'at': NOW, 'src': 'NSDL — Daily Trends in FPI Investments', 'url': NSDL_URL, 'unit': 'mln USD (przeliczenie NSDL)',
            'cols': ['data raportu', 'akcje', 'dług', 'hybrydy', 'razem', 'INR za USD'], 'asof': d[-1][0], 'd': d}


def twse_part(prev_tw, key):
    prev_tw = prev_tw if isinstance(prev_tw, dict) else {}
    have = {k: list(v) for k, v in _rows(prev_tw).items()}   # kopie — poprzedni plik nie jest zmieniany w miejscu
    now_tpe = _now_utc() + datetime.timedelta(hours=8)
    lim = (now_tpe.date() - datetime.timedelta(days=40)).isoformat()
    empty = {x for x in prev_tw.get('empty', []) if isinstance(x, str) and x >= lim}
    fails = []
    for iso in tw_dates(set(have), empty, now_tpe, first=not have)[-TWSE_MAX:]:
        time.sleep(TWSE_SLEEP)
        try:
            r = parse_twse(get_json(TWSE_URL.format(d=iso.replace('-', ''))))
        except Exception as e:
            fails.append(f'{iso}: {e}'); continue
        if r is None:
            if iso < now_tpe.date().isoformat():
                empty.add(iso)      # dzień bez sesji (święto) — nie pytamy ponownie
            continue
        have[r[0]] = r[:5]
    if not have:
        raise RuntimeError('brak dni' + (f' ({fails[0]})' if fails else ''))
    if fails:
        META['errors'].append(mask(f'TWSE: {len(fails)} dni bez odpowiedzi, np. {fails[0]}'))
    d = [have[k] for k in sorted(have)][-OBCE_KEEP:]
    rates = {}
    if key:
        try:
            rates = twd_rates(key)
        except Exception as e:
            META['errors'].append(mask(f'TWSE kurs FRED DEXTAUS: {e}'))
    old = _rows(prev_tw)
    for r in d:
        rd, rt = _rate_for(rates, r[0])
        if rt and r[1] is not None:
            r[5:] = [round(r[1] / rt, 1), rd]
        elif r[0] in old and len(old[r[0]]) >= 7:
            r[5:] = old[r[0]][5:7]          # bez nowego kursu zostaje poprzednie przeliczenie
        else:
            r[5:] = [None, None]
    return {'at': NOW, 'src': 'TWSE — Trading Value of Foreign & Other Investors (BFI82U)',
            'url': 'https://www.twse.com.tw/en/trading/foreign/bfi82u.html', 'unit': 'mln TWD; ≈ mln USD kursem Fed H.10 (FRED DEXTAUS)',
            'cols': ['data', 'zagraniczni', 'fundusze krajowe', 'dealerzy', 'razem', '≈ mln USD (zagraniczni)', 'data kursu'],
            'asof': d[-1][0], 'empty': sorted(empty), 'd': d}


# v67: HKEX Stock Connect — dzienne kupno i sprzedaż akcji w Hongkongu przez inwestorów z Chin kontynentalnych (southbound)
HKEX_URL = 'https://www.hkex.com.hk/eng/csm/DailyStat/data_tab_daily_{d}e.js'
HKEX_SLEEP = 1.0


def parse_hkex(text):
    """Plik dzienny HKEX (JS `tabData = [...]`) → [data, netto, kupno, sprzedaż, liczba rynków] w mln HKD (Szanghaj + Shenzhen
    → Hongkong); dzień bez sesji albo bez kupna/sprzedaży → None. Northbound od 2024 bez podziału na kupno i sprzedaż — pomijamy."""
    t = str(text)
    try:
        j = json.loads(t[t.index('['):t.rindex(']') + 1])
    except (ValueError, json.JSONDecodeError):
        return None
    date, buy, sell, n, sb, bad = None, 0.0, 0.0, 0, 0, 0
    for m in j if isinstance(j, list) else []:
        if not isinstance(m, dict) or 'southbound' not in str(m.get('market', '')).lower():
            continue
        sb += 1
        if not m.get('tradingDay'):
            continue
        try:
            tb = m['content'][0]['table']; d = dict(zip(tb['schema'][0], [x['td'][0][0] for x in tb['tr']]))
        except (KeyError, IndexError, TypeError):
            bad += 1; continue
        b, s = _num(d.get('Buy Turnover')), _num(d.get('Sell Turnover'))
        if b is None or s is None or not re.match(r'^\d{4}-\d{2}-\d{2}$', str(m.get('date', ''))):
            bad += 1; continue
        if b == 0 and s == 0:
            continue      # v73: rynek bez handlu (święto w Chinach kontynentalnych przy otwartym Hongkongu: tradingDay 1, obrót 0,00)
        date = m['date']; buy += b; sell += s; n += 1
    if bad:
        return None       # v73: nieczytelna tabela rynku w dniu sesji = nieczytelny plik (ponowimy), nie dzień z częścią rynków
    if not n:
        return False if sb else None   # v69: False = dzień bez sesji (plik z tradingDay 0), None = nieczytelny plik
    return [date, round(buy - sell, 2), round(buy, 2), round(sell, 2), n]


def fred_rates(key, sid, limit=60):
    """FRED — kurs (dzienny albo średnia miesięczna, zależnie od serii; jednostek waluty za 1 USD, Fed H.10) → {data: kurs}; '.' = brak."""
    j = get_json(f'{FRED}?series_id={sid}&api_key={key}&file_type=json&sort_order=desc&limit={limit}')
    out = {}
    for o in j.get('observations', []) if isinstance(j, dict) else []:
        v = _num(o.get('value'))
        if v and v > 0 and re.match(r'^\d{4}-\d{2}-\d{2}$', str(o.get('date', ''))):
            out[o['date']] = v
    return out


def hkex_part(prev_hk, key):
    prev_hk = prev_hk if isinstance(prev_hk, dict) else {}
    have = {k: list(v) for k, v in _rows(prev_hk).items()}
    now_hk = _now_utc() + datetime.timedelta(hours=8)
    lim = (now_hk.date() - datetime.timedelta(days=40)).isoformat()
    empty = {x for x in prev_hk.get('empty', []) if isinstance(x, str) and x >= lim}
    fails = []
    for k in [k for k, r in have.items() if len(r) > 3 and r[2] == 0 and r[3] == 0]:
        del have[k]; empty.add(k)   # v73: dawny zapis „sesja z zerem” w dniu bez handlu → dzień bez sesji
    for iso in tw_dates(set(have), empty, now_hk, first=not have)[-TWSE_MAX:]:   # te same zasady dni co dla Tajwanu (UTC+8)
        time.sleep(HKEX_SLEEP)
        try:
            r = parse_hkex(get_bytes(HKEX_URL.format(d=iso.replace('-', '')), timeout=30).decode('utf-8', 'replace'))
        except urllib.error.HTTPError as e:
            if e.code != 404 or iso < now_hk.date().isoformat():
                fails.append(f'{iso}: HTTP {e.code}')   # v69: 404 za dzień roboczy z przeszłości = brak pliku (święta mają plik) — ponowimy
            continue
        except Exception as e:
            fails.append(f'{iso}: {e}'); continue
        if r is False:
            empty.add(iso); continue      # v69: święto w Hongkongu — plik z tradingDay 0
        if r is None:
            fails.append(f'{iso}: nieczytelny plik'); continue
        have[r[0]] = r[:5]
    if not have:
        raise RuntimeError('brak dni' + (f' ({fails[0]})' if fails else ''))
    if fails:
        META['errors'].append(mask(f'HKEX: {len(fails)} dni bez odpowiedzi, np. {fails[0]}'))
    d = [have[k] for k in sorted(have)][-OBCE_KEEP:]
    rates = {}
    if key:
        try:
            rates = fred_rates(key, 'DEXHKUS')
        except Exception as e:
            META['errors'].append(mask(f'HKEX kurs FRED DEXHKUS: {e}'))
    old = _rows(prev_hk)
    for r in d:
        rd, rt = _rate_for(rates, r[0])
        if rt and r[1] is not None:
            r[5:] = [round(r[1] / rt, 1), rd]
        elif r[0] in old and len(old[r[0]]) >= 7:
            r[5:] = old[r[0]][5:7]
        else:
            r[5:] = [None, None]
    return {'at': NOW, 'src': 'HKEX — Stock Connect daily statistics (Southbound: Shanghai + Shenzhen → Hong Kong)',
            'url': 'https://www.hkex.com.hk/Mutual-Market/Stock-Connect/Statistics/Historical-Daily',
            'unit': 'mln HKD; ≈ mln USD kursem Fed H.10 (FRED DEXHKUS)',
            'cols': ['data', 'netto', 'kupno', 'sprzedaż', 'rynki', '≈ mln USD (netto)', 'data kursu'],
            'asof': d[-1][0], 'empty': sorted(empty), 'd': d}


# v71: Banco Central do Brasil (SGS, bez klucza) — „câmbio contratado”: dzienne przepływy dolarów przez rynek walutowy Brazylii
BCB_URL = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{id}/dados?formato=json&dataInicial={a}&dataFinal={b}'   # „ultimos/N” ma limit 20
BCB_SERIES = (('fin', 13970), ('fin_buy', 13968), ('fin_sell', 13969), ('com', 13967), ('tot', 13961))
BCB_DAYS = 60     # dni kalendarzowe wstecz (ok. 40 dni roboczych)


def _bcb_date(s):
    m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', str(s or '').strip())
    return f'{m.group(3)}-{m.group(2)}-{m.group(1)}' if m else None


# v79: Brazylia — miesięczny bilans płatniczy (bank centralny, SGS): kapitał zagraniczny napływający do Brazylii (pasywa), mln USD
BCB_BOP = (('fdi', 22885), ('pi', 22924), ('pi_eq', 22927), ('pi_fund', 22936), ('pi_debt', 22939), ('oi', 22971),
           ('cb_dep', 22986), ('cb_loan', 23001), ('sdr', 23042))   # v81: pozycje banku centralnego i SDR — strona odejmuje je od pozostałych


def bcb_bop(prev_m):
    """SGS (miesięcznie) → [[YYYY-MM, bezpośrednie, portfelowe, akcje, fundusze, obligacje, pozostałe]] w mln USD, 25 miesięcy.
    Seria bez odpowiedzi zostawia stare wartości swojej kolumny (nowe miesiące: None, nigdy 0); bez żadnego miesiąca = błąd."""
    now_br = _now_utc() - datetime.timedelta(hours=3)
    a, b = f'01/{now_br.month:02d}/{now_br.year - 2}', now_br.strftime('%d/%m/%Y')
    got, fails = {}, []
    for name, sid in BCB_BOP:
        try:
            j = get_json(BCB_URL.format(id=sid, a=a, b=b))
            if not isinstance(j, list):
                raise RuntimeError('nieznany kształt odpowiedzi')
            for r in j:
                d = _bcb_date(r.get('data')) if isinstance(r, dict) else None
                v = _num(r.get('valor')) if d else None
                if d and v is not None and v == v and abs(v) != float('inf'):
                    got.setdefault(d[:7], {})[name] = round(v, 1)
        except Exception as e:
            fails.append(f'{sid}: {e}')
    if not got:
        raise RuntimeError('brak miesięcy' + (f' ({fails[0]})' if fails else ''))
    have = {r[0]: list(r) for r in (prev_m or []) if isinstance(r, list) and r and isinstance(r[0], str)}
    cols = [n for n, _ in BCB_BOP]
    for m, vals in got.items():
        old = have.get(m) or []
        have[m] = [m] + [vals[c] if c in vals else (old[i + 1] if len(old) > i + 1 else None) for i, c in enumerate(cols)]
    if fails:
        META['errors'].append(mask(f'BCB bilans płatniczy: {len(fails)} serie bez odpowiedzi, np. {fails[0]}'))
    rows = [have[k] for k in sorted(have)][-25:]
    bad = [r[0] for r in rows if None not in r[2:6] and abs(r[2] - r[3] - r[4] - r[5]) > 1]
    if bad:
        META['notes'].append('BCB: portfelowe ≠ akcje + fundusze + obligacje w miesiącach: ' + ', '.join(bad))
    return rows


def bcb_part(prev_br):
    """BCB SGS → [data, finansowy saldo, kupno, sprzedaż, handlowy saldo, razem] w mln USD. Każda seria osobno: seria bez odpowiedzi
    zostawia stare wartości swojej kolumny, a nowe dni mają tam None (nigdy 0). Bez żadnego nowego dnia = błąd (zostaje poprzednia część)."""
    have = {k: list(v) for k, v in _rows(prev_br).items()}
    got, fails = {}, []
    now_br = _now_utc() - datetime.timedelta(hours=3)
    a, b = (now_br - datetime.timedelta(days=BCB_DAYS)).strftime('%d/%m/%Y'), now_br.strftime('%d/%m/%Y')
    for name, sid in BCB_SERIES:
        try:
            j = get_json(BCB_URL.format(id=sid, a=a, b=b))
            if not isinstance(j, list):
                raise RuntimeError('nieznany kształt odpowiedzi')
            for r in j:
                d = _bcb_date(r.get('data')) if isinstance(r, dict) else None
                v = _num(r.get('valor')) if d else None
                if d and v is not None and v == v and abs(v) != float('inf'):
                    got.setdefault(d, {})[name] = round(v, 2)
        except Exception as e:
            fails.append(f'{sid}: {e}')
    if not got:
        raise RuntimeError('brak dni' + (f' ({fails[0]})' if fails else ''))
    cols = [n for n, _ in BCB_SERIES]
    for d, vals in got.items():
        old = have.get(d) or []
        have[d] = [d] + [vals[c] if c in vals else (old[i + 1] if len(old) > i + 1 else None) for i, c in enumerate(cols)]
    if fails:
        META['errors'].append(mask(f'BCB: {len(fails)} serie bez odpowiedzi, np. {fails[0]}'))
    d = [have[k] for k in sorted(have)][-OBCE_KEEP:]
    try:   # v79: miesięczny bilans płatniczy — jego awaria nie zatrzymuje części dziennej
        mrows = bcb_bop((prev_br or {}).get('m'))
    except Exception as e:
        mrows = (prev_br or {}).get('m'); META['errors'].append(mask(f'BCB bilans płatniczy: {e}'))
    extra = {'m': mrows, 'm_cols': ['miesiąc', 'bezpośrednie', 'portfelowe', 'akcje', 'fundusze', 'obligacje', 'pozostałe',
                                    'bank centralny: waluty i depozyty', 'bank centralny: kredyty', 'SDR'],
             'm_src': 'Banco Central do Brasil — SGS, balanço de pagamentos (22885, 22924, 22927, 22936, 22939, 22971, 22986, 23001, 23042)'} if mrows else {}
    return {**extra, 'at': NOW, 'src': 'Banco Central do Brasil — SGS, câmbio contratado (13961, 13967–13970)',
            'url': 'https://www.bcb.gov.br/estatisticas/tabelaespecial', 'unit': 'mln USD',
            'cols': ['data', 'finansowy saldo', 'finansowy kupno', 'finansowy sprzedaż', 'handlowy saldo', 'razem saldo'],
            'asof': d[-1][0], 'd': d}


# v74: Turcja — bank centralny (CBRT), tygodniowe transakcje netto nierezydentów w papierach (oczyszczone z cen i kursów), bez klucza
TCMB_PAGE = 'https://www.tcmb.gov.tr/wps/wcm/connect/EN/TCMB+EN/Main+Menu/Statistics/Monetary+and+Financial+Statistics/Securities+Statistics/'
TCMB_KEYS = (('tot', 'net transactions total'), ('eq', 'equity'), ('gdds', 'gdds (outright purchase)'),
             ('corp', 'debt securities issued by other than general'), ('intl', 'b.2. international market total'),
             ('eurob', 'general government issuances'))


def _tcmb_day(v):
    s = str(v or '').strip()
    m = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', s)
    if m:
        return f'{m.group(3)}-{m.group(2)}-{m.group(1)}'
    x = _num(s)
    if x is not None and 20000 < x < 80000:
        return (datetime.date(1899, 12, 30) + datetime.timedelta(days=int(x))).isoformat()
    return None


def parse_tcmb(rows):
    """Arkusz T1_En → [[tydzień do (piątek), razem, akcje, obligacje skarbowe (zakup bezwarunkowy), obligacje firm i banków,
    rynek zagraniczny razem, euroobligacje rządu]] w mln USD — tylko część „B. NET TRANSACTIONS”, wiersze po nazwie."""
    head, got = None, {}
    for _, r in sorted(rows.items()):
        lab = re.sub(r'\s+', ' ', r.get(2, '')).strip().lower()
        if lab.startswith('b. net transactions'):
            head = {c: _tcmb_day(v) for c, v in r.items() if c > 2}
            head = {c: d for c, d in head.items() if d}
            continue
        if head is None:
            continue
        if not lab or lab.startswith('('):
            break          # koniec części B (przypisy)
        for key, pre in TCMB_KEYS:
            if key not in got and lab.startswith(pre):
                got[key] = {head[c]: _num(v) for c, v in r.items() if c in head and _num(v) is not None and _num(v) == _num(v)}
                break
    if not head or 'tot' not in got:
        raise RuntimeError('brak części „B. NET TRANSACTIONS”')
    days = sorted({d for x in got.values() for d in x})
    return [[d] + [(got.get(k) or {}).get(d) for k, _ in TCMB_KEYS] for d in days]


def tcmb_part(prev_tr):
    import html as _h
    import zipfile
    page = get_bytes(TCMB_PAGE, timeout=60).decode('utf-8', 'replace')
    m = re.search(r'href="([^"]*Securities\+Statistics\.zip[^"]*)"', page)
    if not m:
        raise RuntimeError('brak odnośnika do pliku')
    href = _h.unescape(m.group(1))
    z = zipfile.ZipFile(io.BytesIO(get_bytes(href if href.startswith('http') else 'https://www.tcmb.gov.tr' + href, timeout=90)))
    name = next((n for n in z.namelist() if n.lower().endswith('.xlsx')), None)
    if not name:
        raise RuntimeError('brak pliku .xlsx w archiwum')
    new = parse_tcmb(_xlsx_rows(z.read(name), 'T1_En'))
    big = [r[0] for r in new if any(v is not None and abs(v) > 1e5 for v in r[1:])]   # v77: tydzień > 100 mld USD = zła skala
    if big:
        raise RuntimeError(f'skala niezgodna ({big[-1]})')
    gap = [r[0] for r in new if None not in r[1:6] and abs(r[1] - r[2] - r[3] - r[4] - r[5]) > 1]
    if gap:
        META['notes'].append('CBRT: razem ≠ suma składników w tygodniach: ' + ', '.join(gap))
    have = {k: list(v) for k, v in _rows(prev_tr).items()}
    have.update({r[0]: r for r in new})      # nowszy plik poprawia poprzedni tydzień (dane wstępne)
    d = [have[k] for k in sorted(have)][-OBCE_KEEP:]
    return {'at': NOW, 'src': 'Central Bank of the Republic of Türkiye (CBRT) — Securities Statistics, Table 1, B. Net Transactions',
            'url': TCMB_PAGE, 'unit': 'mln USD; transakcje netto nierezydentów oczyszczone ze zmian cen i kursów; bez repo, zabezpieczeń i pożyczek papierów',
            'cols': ['tydzień do', 'razem', 'akcje', 'obligacje skarbowe (zakup bezwarunkowy)', 'obligacje firm i banków', 'rynek zagraniczny razem', 'euroobligacje rządu'],
            'asof': d[-1][0], 'd': d}


# v86: Tajlandia — ThaiBMA „Non-resident Flows”: dzienne transakcje nierezydentów w tajskich obligacjach (mln THB), bez klucza;
# ≈ USD kursem Fed H.10 (FRED DEXTHUS). Źródło oddaje całą historię (od 2016) w jednym pliku JSON.
THBMA_URL = 'https://www.thaibma.or.th/nrdaily/GetNR/'
THBMA_PAGE = 'https://www.thaibma.or.th/EN/Market/NR/NRDaily.aspx'
TH_KEEP = 270      # ok. 13 miesięcy sesji — wystarcza na sumę 12 miesięcy (250 sesji)
TH_COLS = ('NetFlow', 'TotalNetTrade', 'ShortTermTrade', 'LongTermTrade', 'ExpireToday', 'NetHolding')
TH_STALE = 8       # dni kalendarzowych bez nowego pełnego dnia = błąd (najdłuższa przerwa w 10 latach: 6 dni — Songkran, Nowy Rok)


def parse_thbma(j):
    """ThaiBMA /nrdaily/GetNR/ → [[data, przepływ netto (transakcje netto − wykupy), transakcje netto, z wykupem w ciągu roku, później,
    wykupy, stan posiadania (wartość nominalna)]] mln THB, rosnąco. Dzień w toku (najnowsza data bez części popołudniowej P3 — ThaiBMA
    publikuje ją o 16:30 w Bangkoku) pominięty; zakończony dzień bez P3 albo bez sum — wiersz z brakami (None), żeby sumy okien pokazały
    „—”, a nie sięgnęły dzień dalej; powtórzona data — pierwszy wiersz (różne wiersze = uwaga)."""
    if not isinstance(j, list):
        raise RuntimeError('odpowiedź nie jest listą')
    rows = [r for r in j if isinstance(r, dict) and re.match(r'^\d{4}-\d{2}-\d{2}$', str(r.get('Asof') or '')[:10])]
    if not rows:
        raise RuntimeError('brak dni')
    newest = max(str(r['Asof'])[:10] for r in rows)
    out, seen, dup, hole = {}, {}, [], []
    for r in rows:
        day = str(r['Asof'])[:10]
        v = [_num(r.get(k)) for k in TH_COLS]
        if day in seen:
            if seen[day] != v:
                dup.append(day)
            continue
        seen[day] = v
        if r.get('P3Net') is None and day == newest:
            continue                      # dzień w toku
        if r.get('P3Net') is None or v[0] is None or v[1] is None:
            v = [None] * len(TH_COLS); hole.append(day)
        out[day] = [day] + v
    if not out:
        raise RuntimeError('brak pełnych dni')
    keep = set(sorted(out)[-TH_KEEP:])
    if [x for x in dup if x in keep]:
        META['notes'].append('ThaiBMA: różne wiersze dla tej samej daty (wzięty pierwszy): ' + ', '.join(sorted(x for x in dup if x in keep)))
    if [x for x in hole if x in keep]:
        META['notes'].append('ThaiBMA: zakończony dzień bez części popołudniowej albo bez sum (pokazany jako brak): ' + ', '.join(sorted(x for x in hole if x in keep)))
    return [out[k] for k in sorted(out)]


def _th_scale_ok(r):
    return r[1] is None or (abs(r[1]) <= 2e5 and (r[6] is None or 1e5 < r[6] < 1e7))   # dzień ≤ 200 mld THB; stan 0,1–10 bln THB


def thbma_part(prev_th, key):
    prev_th = prev_th if isinstance(prev_th, dict) else {}
    try:
        j = json.loads(get_bytes(THBMA_URL, timeout=120).decode('utf-8-sig', 'replace'))
    except ValueError:
        raise RuntimeError('odpowiedź nie jest JSON (np. przerwa techniczna)')
    d = [list(r) for r in parse_thbma(j)[-TH_KEEP:]]      # źródło oddaje całą historię — wiersze tylko ze źródła (bez starych dni z pliku)
    if len(d) < 30:
        raise RuntimeError(f'za mało dni ({len(d)})')
    if not _th_scale_ok(d[-1]):
        raise RuntimeError(f'skala niezgodna ({d[-1][0]})')    # najnowszy dzień — zostaje poprzednia część
    bad = [r[0] for r in d if not _th_scale_ok(r)]
    for r in d:
        if r[0] in bad:
            r[1:7] = [None] * 6                                # pojedynczy zły dzień = brak, nie blokada całej części
    if bad:
        META['errors'].append('ThaiBMA: wartości poza skalą (pokazane jako brak) w dniach: ' + ', '.join(bad[-5:]))
    gap = [r[0] for r in d[-30:] if None not in r[1:6] and (abs(r[2] - r[3] - r[4]) > 1 or abs(r[2] - r[5] - r[1]) > 1)]
    if gap:
        META['notes'].append('ThaiBMA: sumy niezgodne w dniach: ' + ', '.join(gap))
    rates = {}
    if key:
        try:
            rates = fred_rates(key, 'DEXTHUS', limit=400)
        except Exception as e:
            META['errors'].append(mask(f'ThaiBMA kurs FRED DEXTHUS: {e}'))
    old = _rows(prev_th)
    for r in d:
        rd, rt = _rate_for(rates, r[0])
        if rt and r[1] is not None:
            r[7:] = [round(r[1] / rt, 1), rt, rd]
        elif r[1] is not None and r[0] in old and len(old[r[0]]) >= 10 and old[r[0]][1] == r[1]:
            r[7:] = old[r[0]][7:10]
        else:
            r[7:] = [None, None, None]
    last = d[-1][0]
    if ((_now_utc() + datetime.timedelta(hours=7)).date() - datetime.date.fromisoformat(last)).days > TH_STALE:
        META['errors'].append(f'ThaiBMA: brak nowego pełnego dnia po {last}')
    return {'at': NOW, 'src': 'The Thai Bond Market Association (ThaiBMA) — Non-resident Flows (daily)', 'url': THBMA_PAGE,
            'unit': 'mln THB; ≈ mln USD kursem Fed H.10 (FRED DEXTHUS); stan posiadania w wartości nominalnej',
            'cols': ['data', 'przepływ netto', 'transakcje netto', 'z wykupem w ciągu roku', 'z wykupem później', 'wykupy', 'stan posiadania',
                     '≈ mln USD', 'kurs THB/USD', 'dzień kursu'],
            'asof': last, 'd': d}

def build_obce(key, prev=None):
    """data/obce.json — każda część osobno: awaria jednej zostawia jej poprzednią wersję (brak nie jest zerem)."""
    prev = prev if isinstance(prev, dict) else {}
    out = {'at': NOW, 'ok': {}, 'errs': {}}   # v77: stan i błędy części — widoczne także przy przebiegach z pamięci
    for part, fn in (('in', lambda: nsdl_part(prev.get('in'))), ('tw', lambda: twse_part(prev.get('tw'), key)),
                     ('hk', lambda: hkex_part(prev.get('hk'), key)),   # v67: Stock Connect southbound
                     ('br', lambda: bcb_part(prev.get('br'))),   # v71: Brazylia — rynek walutowy (BCB)
                     ('tr', lambda: tcmb_part(prev.get('tr'))),   # v74: Turcja — nierezydenci w papierach (CBRT)
                     ('th', lambda: thbma_part(prev.get('th'), key))):   # v86: Tajlandia — nierezydenci w obligacjach (ThaiBMA)
        n0 = len(META['errors'])
        try:
            out[part] = fn(); META['ok']['obce_' + part] = True
        except Exception as e:
            META['errors'].append(mask(f"{ {'in': 'NSDL', 'tw': 'TWSE', 'hk': 'HKEX', 'br': 'BCB', 'tr': 'CBRT', 'th': 'ThaiBMA'}[part] }: {e}")); META['ok']['obce_' + part] = False
            if isinstance(prev.get(part), dict):
                out[part] = prev[part]
        out['ok'][part] = META['ok']['obce_' + part]
        if META['errors'][n0:]:
            out['errs'][part] = META['errors'][n0:]
    if not any(p in out for p in ('in', 'tw', 'hk', 'br', 'tr', 'th')):
        raise RuntimeError('żadna część nie odpowiedziała')
    return out


# v56: BIS — nominalne efektywne kursy walut (WS_EER, szeroki koszyk 64 gospodarek), bez klucza
EER_AREAS = ['US', 'XM', 'GB', 'CH', 'SE', 'NO', 'PL', 'JP', 'KR', 'CN', 'HK', 'IN', 'ID', 'SG', 'TH', 'MY', 'PH', 'AU', 'NZ',
             'CA', 'BR', 'MX', 'TR', 'IL', 'ZA', 'SA', 'RU']
EER_BASE = 'https://stats.bis.org/api/v2/data/dataflow/BIS/WS_EER/1.0/'


def eer_summary(daily, monthly):
    """Poziom (ostatni dzienny), zmiana 30 dni (dzienne) i 12 miesięcy (średnie miesięczne, ten sam miesiąc rok wcześniej), w %."""
    rows = {}
    for a in EER_AREAS:
        d = daily.get(a) or []; m = monthly.get(a) or []
        if not d and not m:
            continue
        r = {'v': None, 'd': None, 'c30': None, 'm': None, 'c12': None}
        if d:
            p, v = d[-1]
            lim = (datetime.date.fromisoformat(p) - datetime.timedelta(days=30)).isoformat()
            base = [x for q, x in d if q <= lim]
            r.update({'v': v, 'd': p, 'c30': round((v / base[-1] - 1) * 100, 2) if base and base[-1] else None})
        if m:
            p, v = m[-1]
            ago = f'{int(p[:4]) - 1:04d}-{p[5:7]}'
            prev = [x for q, x in m if q == ago]
            r.update({'m': p, 'c12': round((v / prev[0] - 1) * 100, 2) if prev and prev[0] else None})
        rows[a] = r
    return rows


def build_eer():
    """data/eer.json — kursy efektywne BIS: dzienne 45 obserwacji (do zmiany 30 dni), miesięczne 14 (do zmiany 12 mies.)."""
    keys = '+'.join(EER_AREAS)
    daily = parse_cbpol_csv(get_bytes(EER_BASE + f'D.N.B.{keys}?lastNObservations=45&format=csv&detail=dataonly', timeout=90))
    try:
        monthly = parse_cbpol_csv(get_bytes(EER_BASE + f'M.N.B.{keys}?lastNObservations=14&format=csv&detail=dataonly', timeout=90))
    except Exception as e:
        META['errors'].append(mask(f'BIS kursy efektywne (miesięczne): {e}')); monthly = {}
    rows = eer_summary(daily, monthly)
    if not rows:
        raise RuntimeError('żadna waluta')
    return {'at': NOW, 'src': 'BIS — Effective exchange rates (WS_EER), nominal, broad basket', 'url': 'https://data.bis.org/topics/EER',
            'unit': 'indeks 2020=100; zmiany w %', 'asof': max((r['d'] or '') for r in rows.values()), 'rows': rows}


# v59: MFW COFER — skład walutowy światowych rezerw walutowych (kwartalnie), bez klucza
COFER_CUR = ['CI_USD', 'CI_EUR', 'CI_JPY', 'CI_GBP', 'CI_CNY', 'CI_CAD', 'CI_AUD', 'CI_CHF', 'CI_OTHC']
COFER_URL = ('https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/COFER/+/G001.AFXRA+TFXRA+TFXRA_IMP.'
             + '+'.join(COFER_CUR + ['CI_T']) + '.SHRO_PT+NV_USD.Q?lastNObservations=9')


def _imf_quarter(p):
    s = str(p or '').strip()
    return s if re.match(r'^\d{4}-Q[1-4]$', s) else None


def _q_add(q, n):
    i = int(q[:4]) * 4 + int(q[-1]) - 1 + n
    return f'{i // 4:04d}-Q{i % 4 + 1}'


def parse_cofer(j):
    """COFER → udział walut w rezerwach przypisanych do walut (%), zmiana 1 kw. i 1 roku (pkt proc.), wartość (mld USD).
    Brak wartości = brak (nie zero); zmiana tylko z dokładnie tego kwartału rok / kwartał wcześniej."""
    ser = parse_imf_sdmx(j, _imf_quarter)
    alloc = dict(ser.get(('G001', 'AFXRA', 'CI_T', 'NV_USD', 'Q')) or [])
    total = dict(ser.get(('G001', 'TFXRA', 'CI_T', 'NV_USD', 'Q')) or [])
    if not alloc:
        raise RuntimeError('COFER: brak sumy rezerw przypisanych do walut')
    q = max(alloc)
    bn = lambda v: None if v is None else round(v / 1e9, 1)
    dif = lambda a, b: None if a is None or b is None else round(a - b, 2)
    rows = {}
    for c in COFER_CUR:
        sh = dict(ser.get(('G001', 'AFXRA', c, 'SHRO_PT', 'Q')) or []); v = dict(ser.get(('G001', 'AFXRA', c, 'NV_USD', 'Q')) or [])
        if sh.get(q) is None and v.get(q) is None:
            continue
        s0, v0, v4 = sh.get(q), v.get(q), v.get(_q_add(q, -4))
        rows[c[3:]] = {'sh': None if s0 is None else round(s0, 2), 'd1': dif(s0, sh.get(_q_add(q, -1))), 'd4': dif(s0, sh.get(_q_add(q, -4))),
                       'v': bn(v0), 'dv4': bn(None if v0 is None or v4 is None else v0 - v4)}
    if not rows:
        raise RuntimeError('COFER: żadna waluta')
    tq = total.get(q)
    imp = dict(ser.get(('G001', 'TFXRA_IMP', 'CI_T', 'SHRO_PT', 'Q')) or []).get(q)   # od 2026: część składu szacuje MFW
    return {'src': 'International Monetary Fund, Currency Composition of Official Foreign Exchange Reserves (COFER)',
            'url': 'https://data.imf.org/en/datasets/IMF.STA:COFER', 'unit': '% rezerw przypisanych do walut; mld USD',
            'asof': q, 'alloc': bn(alloc[q]), 'total': bn(tq), 'alloc_pct': round(alloc[q] / tq * 100, 1) if tq else None,
            'imp_pct': None if imp is None else round(imp, 2),
            'order': [c[3:] for c in COFER_CUR if c[3:] in rows], 'rows': rows}


def build_cofer():
    out = parse_cofer(get_json(COFER_URL, {'Accept': 'application/json'}))
    out['at'] = NOW
    return out


# v70: MFW — bilans płatniczy (BOP, BPM6), kwartalnie, bez klucza: ZMIERZONE przepływy kapitału 37 gospodarek.
# L_NIL_T = kapitał zagraniczny napływający do kraju; A_NFA_T = kapitał mieszkańców wysyłany za granicę; NETCD_T CAB = rachunek bieżący.
BIL_CTY = ['USA', 'CAN', 'BRA', 'MEX', 'CHL', 'COL', 'ARG', 'DEU', 'FRA', 'GBR', 'ITA', 'ESP', 'NLD', 'CHE', 'SWE', 'POL', 'IRL',
           'RUS', 'SAU', 'TUR', 'ISR', 'ZAF', 'EGY', 'NGA', 'IND', 'CHN', 'HKG', 'JPN', 'KOR', 'IDN', 'SGP', 'THA', 'MYS', 'PHL',
           'VNM', 'AUS', 'NZL']
BIL_KEYS = {('L_NIL_T', 'D_F'): 'in_d', ('L_NIL_T', 'P_F'): 'in_p', ('L_NIL_T', 'P_F5'): 'in_pe', ('L_NIL_T', 'P_F3'): 'in_pd',
            ('L_NIL_T', 'O_F'): 'in_o', ('A_NFA_T', 'D_F'): 'out_d', ('A_NFA_T', 'P_F'): 'out_p', ('A_NFA_T', 'O_F'): 'out_o',
            ('NETCD_T', 'CAB'): 'ca'}
BIL_URL = ('https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/BOP/+/' + '+'.join(BIL_CTY)
           + '.L_NIL_T+A_NFA_T+NETCD_T.D_F+P_F+P_F5+P_F3+O_F+CAB.USD.Q?lastNObservations=8&dimensionAtObservation=TIME_PERIOD')


def parse_bilans(j):
    """BOP MFW → {kraj: {'q': ostatni kwartał z napływem, 's': {klucz: [[kwartał, mln USD]] rosnąco, najwyżej 8}}}.
    Wartość pusta / NaN = brak (nigdy 0). Straż skali: napływ portfelowy USA musi mieć rząd mld–bln USD na kwartał."""
    ser = parse_imf_sdmx(j, _imf_quarter)
    rows = {}
    for lab, d in ser.items():
        if len(lab) != 5:
            continue
        c, e, i, u, f = lab
        k = BIL_KEYS.get((e, i))
        if not k or u != 'USD' or f != 'Q' or c not in BIL_CTY:
            continue
        rows.setdefault(c, {})[k] = [[q, round(v / 1e6, 1)] for q, v in d][-8:]
    usa = (rows.get('USA') or {}).get('in_p')
    if usa and not 1e3 <= abs(usa[-1][1]) <= 1e7:
        raise RuntimeError(f'skala niezgodna (USA napływ portfelowy {usa[-1][1]} mln USD)')
    out = {}
    for c in BIL_CTY:
        s = rows.get(c)
        qs = [x[-1][0] for k, x in (s or {}).items() if k in ('in_d', 'in_p', 'in_o') and x]
        if qs:
            q = max(qs); lo = _q_add(q, -4)
            out[c] = {'q': q, 's': {k: x for k, x in s.items() if x and x[-1][0] >= lo}}   # v73: seria urwana dawno (np. Wietnam 2014) — poza plikiem
    if not out:
        raise RuntimeError('żaden kraj z napływem kapitału')
    return {'src': 'International Monetary Fund, Balance of Payments (BOP)', 'url': 'https://data.imf.org/en/datasets/IMF.STA:BOP',
            'unit': 'mln USD, transakcje w kwartale; in_* = kapitał zagraniczny napływający do kraju (net incurrence of liabilities), '
                    'out_* = kapitał mieszkańców wysyłany za granicę (net acquisition of financial assets); d bezpośrednie, '
                    'p portfelowe (pe akcje, pd obligacje), o pozostałe (kredyty, depozyty); ca = saldo rachunku bieżącego',
            'asof_max': max(r['q'] for r in out.values()), 'order': [c for c in BIL_CTY if c in out], 'rows': out}


def build_bilans():
    out = parse_bilans(get_json(BIL_URL, {'Accept': 'application/json'}))
    out['at'] = NOW
    return out


# v72: SAFE (Chiny) — kupno i sprzedaż walut przez banki w imieniu klientów, miesięcznie, w USD; bez klucza
SAFE_PAGE = 'https://www.safe.gov.cn/en/2023/0215/2048.html'
SAFE_LINK = 'Time-series Data of Foreign Exchange Settlement and Sales by Banks'
SAFE_SHEET = 'in USD (Monthly)'
SAFE_KEEP = 25     # miesięcy (12-miesięczna suma i porównanie rok do roku)


def _xlsx_rows(data, sheet):
    """Czytnik .xlsx na bibliotece standardowej (zip + ElementTree): {nr wiersza: {nr kolumny: tekst}} arkusza o podanej nazwie.
    v77: puste komórki i wiersze pomijane bez przesuwania sąsiednich; tekst sformatowany (kilka <r><t>) sklejany; komórka bez
    adresu = następna kolumna; system dat 1904 = jawny błąd (daty byłyby przesunięte o 4 lata)."""
    import html as _h
    import zipfile
    import xml.etree.ElementTree as ET
    z = zipfile.ZipFile(io.BytesIO(data))
    names = set(z.namelist())
    loc = lambda tag: str(tag).rsplit('}', 1)[-1]
    def text(el):   # v80: tekst elementu bez podpowiedzi fonetycznych (<rPh>)
        if loc(el.tag) == 'rPh':
            return ''
        own = (el.text or '') if loc(el.tag) == 't' else ''
        return own + ''.join(text(c) for c in el)
    strs = []
    if 'xl/sharedStrings.xml' in names:
        strs = [text(si) for si in ET.fromstring(z.read('xl/sharedStrings.xml')) if loc(si.tag) == 'si']
    wb = z.read('xl/workbook.xml').decode('utf-8')
    if re.search(r'date1904="(1|true)"', wb):
        raise RuntimeError('system dat 1904 — nieobsługiwany')
    attr = lambda tag, a: (re.search(r'\b' + a + r'="([^"]*)"', tag) or [None, None])[1]
    rid = None
    for tag in re.findall(r'<sheet\b[^>]*>', wb):
        if _h.unescape(attr(tag, 'name') or '') == sheet:
            rid = attr(tag, 'r:id')
    if not rid:
        raise RuntimeError(f'brak arkusza „{sheet}”')
    target = None
    for tag in re.findall(r'<Relationship\b[^>]*>', z.read('xl/_rels/workbook.xml.rels').decode('utf-8')):
        if attr(tag, 'Id') == rid:
            target = attr(tag, 'Target')
    path = 'xl/' + target.lstrip('/').replace('xl/', '', 1) if target else None
    if path not in names:
        raise RuntimeError('brak pliku arkusza')
    col = lambda c: sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(c)))
    rows, rn = {}, 0
    for row in ET.fromstring(z.read(path)).iter():
        if loc(row.tag) != 'row':
            continue
        r = row.get('r')
        rn = int(r) if r and r.isdigit() else rn + 1
        cn = 0
        for c in row:
            if loc(c.tag) != 'c':
                continue
            m = re.match(r'^([A-Z]+)\d*$', c.get('r') or '')
            cn = col(m.group(1)) if m else cn + 1
            t = c.get('t')
            if t == 'inlineStr':
                v = text(c)
            else:
                ve = next((x for x in c if loc(x.tag) == 'v'), None)
                if ve is None or ve.text is None:
                    continue          # pusta komórka — bez wartości, sąsiedzi na swoich miejscach
                v = ve.text
                if t == 's':
                    i = int(v); v = strs[i] if 0 <= i < len(strs) else ''
            rows.setdefault(rn, {})[cn] = v.strip()
    return rows


def _xlsx_month(v):
    """Nagłówek miesiąca: liczba seryjna Excela (46235 = 2026-08-01) albo tekst '2026-08' / '2026.08' → 'YYYY-MM'."""
    s = str(v or '').strip()
    m = re.match(r'^(\d{4})[.\-/](\d{1,2})$', s)
    if m and 1 <= int(m.group(2)) <= 12:
        return f'{m.group(1)}-{int(m.group(2)):02d}'
    x = _num(s)
    if x is not None and 20000 < x < 80000:
        d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(x))
        return f'{d.year:04d}-{d.month:02d}'
    return None


def parse_safe(rows):
    """Arkusz „in USD (Monthly)” → [[YYYY-MM, klienci saldo, bieżący saldo, kapitałowy saldo, bezpośrednie saldo, portfelowe saldo,
    kapitałowy rozliczenie, kapitałowy sprzedaż]] w mld USD (plik: 100 mln USD). Wiersze po nazwie w sekcjach I/II/III, nie po numerze."""
    head = next((r for _, r in sorted(rows.items()) if r.get(1, '').strip().lower() == 'item'), None)
    if not head:
        raise RuntimeError('brak wiersza nagłówka')
    months = {c: _xlsx_month(v) for c, v in head.items() if c > 1}
    months = {c: m for c, m in months.items() if m}
    if not months:
        raise RuntimeError('brak miesięcy w nagłówku')
    sec, cust, got = None, False, {}
    for _, r in sorted(rows.items()):
        lab = re.sub(r'\s+', ' ', r.get(1, '')).strip()
        m = re.match(r'^(I|II|III|IV|V|VI|VII|VIII)\.\s', lab)
        if m:
            sec, cust = m.group(1), False
            continue
        if sec not in ('I', 'II', 'III'):
            continue
        low = lab.lower()
        if low.startswith('(ii) by banks for customers'):
            cust = True; key = 'cust'
        elif low.startswith('(i) by banks for themselves'):
            cust = False; continue
        elif cust and low.startswith('1. current account'):
            key = 'ca'
        elif cust and low.startswith('2. capital and financial account'):
            key = 'cfa'
        elif cust and 'direct investment' in low:
            key = 'fdi'
        elif cust and low.startswith('portfolio investment'):
            key = 'port'
        else:
            continue
        got[(sec, key)] = {months[c]: _num(v) for c, v in r.items() if c in months and _num(v) is not None and _num(v) == _num(v)}
    need = [('III', 'cust'), ('III', 'ca'), ('III', 'cfa')]
    if any(k not in got for k in need):
        raise RuntimeError('brak wierszy salda (klienci / bieżący / kapitałowy)')
    keys = [('III', 'cust'), ('III', 'ca'), ('III', 'cfa'), ('III', 'fdi'), ('III', 'port'), ('I', 'cfa'), ('II', 'cfa')]
    allm = sorted({mm for k in keys for mm in (got.get(k) or {})})
    bn = lambda v: None if v is None else round(v / 10, 2)
    out = [[mm] + [bn((got.get(k) or {}).get(mm)) for k in keys] for mm in allm]
    out = [r for r in out if any(x is not None for x in r[1:])][-SAFE_KEEP:]
    g = out[-1][6]   # straż skali: rozliczenia kapitałowe klientów w miesiącu to dziesiątki mld USD
    if g is not None and not 5 <= g <= 1000:
        raise RuntimeError(f'skala niezgodna (rozliczenia kapitałowe {g} mld USD)')
    return out


def build_safe():
    page = get_bytes(SAFE_PAGE, timeout=60).decode('utf-8', 'replace')
    href = next((h for h, t in re.findall(r'<a[^>]+href="([^"]+\.xlsx)"[^>]*>(.*?)</a>', page, re.S)
                 if SAFE_LINK.lower() in re.sub(r'<[^>]+>', '', t).lower()), None)
    if not href:
        raise RuntimeError('brak odnośnika do pliku')
    url = href if href.startswith('http') else 'https://www.safe.gov.cn' + href
    m = parse_safe(_xlsx_rows(get_bytes(url, timeout=90), SAFE_SHEET))
    ids = [r for r in m if None not in r[1:4] and abs(r[1] - r[2] - r[3]) > 0.2]
    if ids:
        META['notes'].append(f'SAFE: saldo klientów ≠ bieżący + kapitałowy w {len(ids)} mies. (np. {ids[-1][0]})')
    return {'at': NOW, 'src': 'State Administration of Foreign Exchange (SAFE), Data on Foreign Exchange Settlement and Sales by Banks',
            'url': SAFE_PAGE, 'file': url, 'unit': 'mld USD; saldo = rozliczenie (klienci sprzedają waluty bankom) minus sprzedaż (kupują od banków)',
            'cols': ['miesiąc', 'klienci saldo', 'rachunek bieżący saldo', 'kapitałowy i finansowy saldo', 'w tym bezpośrednie saldo',
                     'w tym portfelowe saldo', 'kapitałowy rozliczenie', 'kapitałowy sprzedaż'],
            'asof': m[-1][0], 'm': m}


# v76: Eurostat — miesięczny bilans płatniczy krajów UE (bop_c6_m), bez klucza
UE_GEO = ['AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES', 'FI', 'FR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
          'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK']
UE_KEYS = {('FA__P__F', 'LIAB'): 'in_p', ('FA__D__F', 'LIAB'): 'in_d', ('FA__O__F', 'LIAB'): 'in_o',
           ('FA__P__F', 'ASS'): 'out_p', ('FA__D__F', 'ASS'): 'out_d', ('FA__O__F', 'ASS'): 'out_o'}
UE_URL = ('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/bop_c6_m?format=JSON&lang=EN&currency=MIO_EUR'
          '&partner=WRL_REST&sector10=S1&sector10=S121&sectpart=S1&lastTimePeriod=24&' + '&'.join('geo=' + g for g in UE_GEO)
          + '&bop_item=FA__P__F&bop_item=FA__D__F&bop_item=FA__O__F&stk_flow=LIAB&stk_flow=ASS')


def parse_jsonstat(j):
    """JSON-stat 2.0 (Eurostat) → ({(kod wymiaru 1, 2, …): wartość}, id wymiarów, {(…): litery statusu}); indeks płaski = wiersz po
    wymiarach w kolejności 'id'; indeks kategorii jako obiekt albo lista (v80); status np. 'e' szacunek, 'p' wstępne (poufne bez wartości)."""
    try:
        ids, size = j['id'], j['size']
        keys = []
        for d in ids:
            idx = j['dimension'][d]['category']['index']
            if isinstance(idx, list):
                idx = {k: i for i, k in enumerate(idx)}
            keys.append([k for k, _ in sorted(idx.items(), key=lambda kv: kv[1])])
        vals = j.get('value') or {}
        stat = j.get('status') or {}
    except (KeyError, TypeError, AttributeError) as e:
        raise RuntimeError(f'nieznany kształt odpowiedzi ({e})')
    if isinstance(vals, list):
        vals = {str(i): v for i, v in enumerate(vals) if v is not None}
    if isinstance(stat, list):
        stat = {str(i): v for i, v in enumerate(stat) if v}

    def lab(flat):
        i, out = int(flat), []
        for s, ks in zip(reversed(size), reversed(keys)):
            out.append(ks[i % s]); i //= s
        return tuple(reversed(out))
    out, flags = {}, {}
    for flat, v in vals.items():
        try:
            k = lab(flat)
        except (ValueError, IndexError):
            continue
        x = _num(v)
        if x is not None and x == x:
            out[k] = x
            f = ''.join(ch for ch in str(stat.get(flat, '')).split('|')[0] if ch in 'ep')
            if f:
                flags[k] = f
    if not out:
        raise RuntimeError('brak wartości')
    return out, ids, flags


def parse_ue(j):
    """bop_c6_m → {kraj: {'m': ostatni miesiąc z kompletem składników, 's': {klucz: [[YYYY-MM, mln EUR]]}, 'f': {YYYY-MM: 'e'|'p'}}}.
    v80: „pozostałe” bez banku centralnego (S1 minus S121, tylko gdy są obie wartości; bez S121 = brak, nigdy suma z TARGET2)."""
    vals, ids, flags = parse_jsonstat(j)
    pos = {d: i for i, d in enumerate(ids)}
    rows, cb, fl = {}, {}, {}
    for lab, v in vals.items():
        item, flow, g, m = lab[pos['bop_item']], lab[pos['stk_flow']], lab[pos['geo']], lab[pos['time']]
        sec = lab[pos['sector10']] if 'sector10' in pos else 'S1'
        if g not in UE_GEO or not re.match(r'^\d{4}-\d{2}$', m):
            continue
        k = UE_KEYS.get((item, flow))
        if not k:
            continue
        if sec == 'S121':
            if item == 'FA__O__F':
                cb.setdefault(g, {}).setdefault(k, {})[m] = v
            continue
        if sec != 'S1':
            continue
        rows.setdefault(g, {}).setdefault(k, {})[m] = v
        if lab in flags and k.startswith('in_'):
            fl.setdefault(g, {})[m] = ''.join(sorted(set(fl.get(g, {}).get(m, '') + flags[lab])))
    out = {}
    for g in UE_GEO:
        s0 = rows.get(g) or {}
        s = {}
        for k, series in s0.items():
            if k.endswith('_o'):   # pozostałe bez banku centralnego
                c = (cb.get(g) or {}).get(k) or {}
                series = {m: v - c[m] for m, v in series.items() if m in c}
            if series:
                s[k] = [[m, round(v, 1)] for m, v in sorted(series.items())]
        have = lambda k: {m for m, _ in s.get(k, [])}
        full = have('in_p') & have('in_d') & have('in_o')
        anym = have('in_p') | have('in_d') | have('in_o')
        if anym:
            out[g] = {'m': max(full) if full else max(anym), 's': s}
            if fl.get(g):
                out[g]['f'] = fl[g]
    if not out:
        raise RuntimeError('żaden kraj z napływem kapitału')
    de = [abs(v) for _, v in ((out.get('DE') or {}).get('s', {}).get('in_p') or [])]
    if de and not 100 <= max(de) <= 1e6:
        raise RuntimeError(f'skala niezgodna (Niemcy, napływ portfelowy do {max(de)} mln EUR)')
    return {'src': 'Eurostat, Balance of payments by country — monthly data (BPM6), bop_c6_m', 'url': 'https://ec.europa.eu/eurostat/databrowser/view/bop_c6_m/default/table',
            'unit': 'mln EUR, transakcje w miesiącu; in_* = napływ kapitału z zagranicy (pasywa), out_* = kapitał mieszkańców za granicę (aktywa); '
                    'p portfelowe, d bezpośrednie, o pozostałe bez banku centralnego (S1 − S121); f = status Eurostatu (e szacunek, p wstępne)',
            'asof_max': max(r['m'] for r in out.values()), 'order': [g for g in UE_GEO if g in out], 'rows': out}


def build_ue():
    out = parse_ue(get_json(UE_URL))
    out['at'] = NOW
    return out


# v78: Kanada — Statistics Canada, tabela 36-10-0028-01 (International transactions in securities), miesięcznie, bez klucza
KAN_VEC = (('tot', 61915649), ('debt', 61915652), ('bond', 61915682), ('mm', 61915655), ('eq', 61915712))   # stałe numery wektorów „Net flows”
KAN_URL = 'https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorByReferencePeriodRange?vectorIds={v}&startRefPeriod={a}&endReferencePeriod={b}'


def parse_kanada(j):
    """WDS → [[YYYY-MM, razem, dłużne, obligacje, rynek pieniężny, akcje]] w mln CAD; brak = None (nigdy 0); skala ≠ miliony = błąd."""
    names = {vid: k for k, vid in KAN_VEC}
    got = {}
    for x in j if isinstance(j, list) else []:
        o = (x or {}).get('object') or {}
        name = names.get(o.get('vectorId'))
        if not name:
            continue
        for p in o.get('vectorDataPoint') or []:
            m = re.match(r'^(\d{4}-\d{2})-01$', str(p.get('refPer', '')))
            v = p.get('value')
            if not m or not isinstance(v, (int, float)) or v != v:
                continue
            if p.get('scalarFactorCode') != 6:
                raise RuntimeError(f'skala niezgodna (scalarFactorCode {p.get("scalarFactorCode")})')
            got.setdefault(name, {})[m.group(1)] = round(float(v), 1)
    if 'tot' not in got:
        raise RuntimeError('brak serii „razem”')
    months = sorted({mm for d in got.values() for mm in d})[-25:]
    rows = [[mm] + [got.get(k, {}).get(mm) for k, _ in KAN_VEC] for mm in months]
    bad = [r[0] for r in rows if None not in (r[1], r[2], r[5]) and abs(r[1] - r[2] - r[5]) > 2]
    if bad:
        META['notes'].append('Statistics Canada: razem ≠ dłużne + akcje w miesiącach: ' + ', '.join(bad))
    return rows


def build_kanada():
    now = _now_utc().date()
    v = ','.join(f'%22{vid}%22' for _, vid in KAN_VEC)
    m = parse_kanada(get_json(KAN_URL.format(v=v, a=f'{now.year - 2}-{now.month:02d}-01', b=now.isoformat())))
    return {'at': NOW, 'src': 'Statistics Canada, Table 36-10-0028-01 International transactions in securities, portfolio transactions in Canadian and foreign securities, monthly',
            'url': 'https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610002801',
            'unit': 'mln CAD; transakcje nierezydentów w kanadyjskich papierach, netto (plus = zagranica kupiła netto)',
            'cols': ['miesiąc', 'razem', 'dłużne', 'obligacje', 'rynek pieniężny', 'akcje i jednostki funduszy'], 'asof': m[-1][0], 'm': m}


# v87: Polska — Ministerstwo Finansów: nierezydenci w krajowych skarbowych papierach wartościowych (SPW), miesięcznie, bez klucza.
# Odnośniki do plików zmieniają się co miesiąc — szukamy ich po stałych tytułach na stronie „Struktura inwestorów”.
SPW_PAGE = 'https://www.gov.pl/web/finanse/struktura-inwestorow'
SPW_BASE = 'https://www.gov.pl'
SPW_FILES = {'st': 'Struktura podmiotowa zadłużenia wobec nierezydentów w krajowych SPW',
             'kr': 'Zadłużenie wobec nierezydentów w krajowych SPW po krajach'}
SPW_A = re.compile(r'<a\b[^>]*href="(/attachment/[0-9a-f-]{36})"[^>]*>((?:(?!</a>).)*?)</a>', re.S)
SPW_KEEP = 25      # miesięcy (zmiana 12 miesięcy i rok wcześniej)
SPW_GRP = 13       # miesięcy dla typów i regionów (zmiana 12 miesięcy)
SPW_STALE = 70     # dni po końcu najnowszego miesiąca bez nowego pliku = błąd (zwykle ok. miesiąca)
SPW_TYPES = (('bank', 'banki'), ('cb', 'banki centralne'), ('pub', 'instytucje publiczne'), ('ins', 'zakłady ubezpieczeniowe'),
             ('pen', 'fundusze emerytalne'), ('inv', 'fundusze inwestycyjne'), ('hf', 'fundusze hedgingowe'), ('hh', 'gospodarstwa domowe'),
             ('corp', 'przedsiębiorstwa niefinansowe'), ('oth', 'inne podmioty'), ('omni', 'rachunki zbiorcze'), ('tot', 'razem'))
SPW_REGS = (('ea', 'europa - kraje strefy euro'), ('eun', 'europa - kraje ue spoza strefy euro'), ('eur', 'europa - kraje spoza ue'),
            ('afr', 'afryka'), ('sam', 'ameryka południowa'), ('nam', 'ameryka północna'), ('oce', 'australia i oceania'),
            ('asia', 'azja'), ('me', 'bliski wschód'), ('omni', 'rachunki zbiorcze'), ('tot', 'razem'))


def _spw_month(v):
    x = _num(v)
    if x is None or not 30000 < x < 80000:
        return None
    d = datetime.date(1899, 12, 30) + datetime.timedelta(days=int(x))
    return f'{d.year:04d}-{d.month:02d}'


def spw_sheet(rows, keys):
    """Arkusz MF → {miesiąc: {klucz: mln zł}}; kolumny po nazwach z wiersza nagłówka „Data” (najpierw nazwa dokładna, potem początek:
    „Banki” ≠ „Banki centralne”); brak kolumny „Razem” = błąd; pusta komórka = brak, nie zero."""
    col, out = None, {}
    for _, r in sorted(rows.items()):
        lab = re.sub(r'\s+', ' ', str(r.get(1, ''))).strip().lower()
        if col is None:
            if lab == 'data':
                heads = {c: re.sub(r'\s+', ' ', str(v)).strip().lower() for c, v in r.items() if c > 1}
                col = {}
                for k, pre in keys:
                    hit = [c for c, h in heads.items() if h == pre] or [c for c, h in heads.items() if h.startswith((pre + ' ', pre + '('))]
                    if len(hit) == 1:
                        col[k] = hit[0]
                if 'tot' not in col:
                    raise RuntimeError('brak kolumny „Razem”')
            continue
        m = _spw_month(r.get(1))
        if m:
            out[m] = {k: _num(r.get(c)) for k, c in col.items()}
    if not out:
        raise RuntimeError('brak miesięcy')
    return out


def spw_links(page):
    out = {}
    for href, txt in SPW_A.findall(page):
        t = re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', ' ', txt))).strip()
        for k, name in SPW_FILES.items():
            if t == name or t.startswith(name + ' '):     # „…w krajowych SPW” ≠ „…w krajowych SPW po krajach”
                out.setdefault(k, SPW_BASE + href)
    return out


def spw_countries(data):
    """Plik „po krajach” → [{'m': YYYY-MM, 'c': [[kraj PL, kraj EN, mln zł, udział %]]}] dla dwóch najnowszych arkuszy (pierwsze w pliku);
    bez wierszy sum, rachunków zbiorczych i banków centralnych (tak jak w źródle)."""
    import zipfile
    names = [_html.unescape(n) for n in re.findall(r'<sheet\b[^>]*\bname="([^"]+)"', zipfile.ZipFile(io.BytesIO(data)).read('xl/workbook.xml').decode('utf-8', 'replace'))]
    out = []
    for nm in names[:2]:
        mm = re.search(r'\(\s*([A-Za-z]+)\s*(\d{4})\s*\)', nm)
        mo = MONTHS_EN.get(mm.group(1).capitalize()) if mm else None
        if not mo:
            raise RuntimeError(f'nieznany arkusz „{nm}”')
        cs = []
        for _, r in sorted(_xlsx_rows(data, nm).items()):
            lab = re.sub(r'\s+', ' ', str(r.get(1, ''))).strip()
            v, sh = _num(r.get(2)), _num(r.get(3))
            if '/' not in lab or v is None or lab.lower().startswith(('suma', 'rachunki zbiorcze', 'banki centralne', 'razem', 'kraje')):
                continue
            pl, en = [x.strip() for x in lab.split('/', 1)]
            cs.append([pl, en, v, None if sh is None else round(sh * 100, 2)])
        if not cs:
            raise RuntimeError(f'brak krajów w arkuszu „{nm}”')
        out.append({'m': f'{mm.group(2)}-{mo:02d}', 'c': cs})
    return out


def build_spw():
    """data/spw.json — m: [[miesiąc, razem, obligacje, bony]] mln zł (wartość nominalna, koniec miesiąca), 25 miesięcy;
    t / r: {typ|region: [[miesiąc, mln zł]]} 13 miesięcy; kr: kraje (2 najnowsze miesiące, opcjonalnie)."""
    L = spw_links(get_bytes(SPW_PAGE, timeout=60).decode('utf-8', 'replace'))
    if 'st' not in L:
        raise RuntimeError('brak odnośnika do pliku struktury nierezydentów')
    data = get_bytes(L['st'], timeout=90)
    T = spw_sheet(_xlsx_rows(data, 'Razem_podmiot'), SPW_TYPES)
    R = spw_sheet(_xlsx_rows(data, 'Razem_region'), SPW_REGS)
    B = spw_sheet(_xlsx_rows(data, 'Obligacje skarbowe_podmiot'), (('tot', 'razem'),))
    S = spw_sheet(_xlsx_rows(data, 'Bony skarbowe_podmiot'), (('tot', 'razem'),))
    ms = sorted(m for m in T if T[m].get('tot') is not None)[-SPW_KEEP:]
    bad = [m for m in ms if not 1e4 < T[m]['tot'] < 1e7]     # razem poza 10 mld – 10 bln zł = zła skala
    if bad:
        raise RuntimeError(f'skala niezgodna ({bad[-1]})')
    gap = [m for m in ms[-SPW_GRP:] if any(abs(sum(v for k, v in G.get(m, {}).items() if k != 'tot' and v is not None) - T[m]['tot']) > 1 for G in (T, R))
           or abs(((B.get(m) or {}).get('tot') or 0) + ((S.get(m) or {}).get('tot') or 0) - T[m]['tot']) > 1]
    if gap:
        META['notes'].append('MF SPW: sumy niezgodne w miesiącach: ' + ', '.join(gap))
    grp = ms[-SPW_GRP:]
    out = {'at': NOW, 'src': 'Ministerstwo Finansów — Struktura podmiotowa zadłużenia wobec nierezydentów w krajowych SPW (miesięcznie)',
           'url': SPW_PAGE, 'unit': 'mln zł, wartość nominalna, stan na koniec miesiąca', 'asof': ms[-1],
           'cols': ['miesiąc', 'razem', 'obligacje skarbowe', 'bony skarbowe'],
           'm': [[m, T[m]['tot'], (B.get(m) or {}).get('tot'), (S.get(m) or {}).get('tot')] for m in ms],
           't': {k: [[m, (T.get(m) or {}).get(k)] for m in grp] for k, _ in SPW_TYPES if k != 'tot'},
           'r': {k: [[m, (R.get(m) or {}).get(k)] for m in grp] for k, _ in SPW_REGS if k != 'tot'}}
    try:
        if 'kr' not in L:
            raise RuntimeError('brak odnośnika do pliku „po krajach”')
        out['kr'] = spw_countries(get_bytes(L['kr'], timeout=90))
    except Exception as e:
        META['errors'].append(mask(f'MF SPW kraje: {e}'))
    y, mo = int(ms[-1][:4]), int(ms[-1][5:7])
    end = datetime.date(y + (mo == 12), mo % 12 + 1, 1) - datetime.timedelta(days=1)
    if (_now_utc().date() - end).days > SPW_STALE:
        META['errors'].append(f'MF SPW: brak nowego miesiąca po {ms[-1]}')
    return out


# v82: Korea Płd. — FSS, miesięczny komunikat „Foreign Investors' Stock and Bond Investment” (po angielsku), bez klucza
FSS_LIST = 'https://www.fss.or.kr/eng/bbs/B0000211/list.do?menuNo=400010&pageIndex={p}'
FSS_BASE = 'https://www.fss.or.kr'
FSS_PAGES = 12
FSS_TITLE = re.compile(r'<a href="(/eng/bbs/B0000211/view\.do\?[^"]+)"[^>]*>\s*Foreign Investors(?:&#39;|\'|’) Stock and Bond Investment, ([A-Z][a-z]+) (\d{4})\s*</a>')
FSS_SENT = re.compile(r'Foreign investors (bought|sold) a net KRW\s?([\d.,]+) (billion|trillion) of listed stocks? and (?:(bought|sold) )?a net KRW\s?([\d.,]+) '
                      r'(billion|trillion) of listed bonds in ([A-Z][a-z]+) (\d{4})')
MONTHS_EN = {m: i for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
                                         'November', 'December'], 1)}


def parse_fss(text):
    """Komunikat FSS → [YYYY-MM, akcje, obligacje] w mld KRW (plus = zakupy netto zagranicy); inne zdanie = None (nigdy zgadywanie)."""
    t = re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', ' ', str(text))))
    m = FSS_SENT.search(t)
    mo = MONTHS_EN.get(m.group(7)) if m else None
    if not mo:
        return None

    def val(side, num, unit):
        v = _num(num)
        if v is None:
            return None
        v *= 1000 if unit == 'trillion' else 1
        return round(v if side == 'bought' else -v, 1)
    return [f'{m.group(8)}-{mo:02d}', val(m.group(1), m.group(2), m.group(3)), val(m.group(4) or m.group(1), m.group(5), m.group(6))]   # bez drugiego czasownika = ten sam kierunek


def fss_months(a, b):
    """Lista miesięcy 'YYYY-MM' od a do b włącznie."""
    out, (y, m) = [], (int(a[:4]), int(a[5:7]))
    while f'{y:04d}-{m:02d}' <= b:
        out.append(f'{y:04d}-{m:02d}'); m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def build_korea(key, prev=None):
    """data/korea.json — [[YYYY-MM, akcje mld KRW, obligacje mld KRW, akcje ≈ mln USD, obligacje ≈ mln USD, kurs]]; 25 miesięcy.
    v83: komunikaty ze strony 1 czytane zawsze (poprawki); brakujące miesiące szukane na kolejnych stronach i zgłaszane przy
    każdym przebiegu; brak nowego komunikatu zbyt długo = błąd; wartość ponad 100 bln KRW = nieczytelna."""
    have = {r[0]: list(r) for r in ((prev or {}).get('m') or []) if isinstance(r, list) and r and isinstance(r[0], str)}
    had, newest, fails, missing = bool(have), None, [], []
    for p in range(1, FSS_PAGES + 1):
        page = get_bytes(FSS_LIST.format(p=p), timeout=60).decode('utf-8', 'replace')
        for href, mon, yr in FSS_TITLE.findall(page):
            mo = MONTHS_EN.get(mon)
            if not mo:
                continue
            ym = f'{yr}-{mo:02d}'
            newest = max(newest or ym, ym)
            if p > 1 and ym in have and have[ym][1] is not None and have[ym][2] is not None:
                continue
            try:
                r = parse_fss(get_bytes(FSS_BASE + _html.unescape(href), timeout=60).decode('utf-8', 'replace'))
                if not r or r[0] != ym or r[1] is None or r[2] is None or max(abs(r[1]), abs(r[2])) > 1e5:
                    raise RuntimeError('nieznany układ komunikatu')
                old = have.get(ym) or []
                have[ym] = r + (old[3:6] if len(old) >= 6 and old[1:3] == r[1:3] else [None, None, None])
            except Exception as e:
                fails.append(f'{ym}: {e}')
        if newest:
            lo = max(min(have) if had and have else _q_ym_add(newest, -12), _q_ym_add(newest, -24))
            missing = [m for m in fss_months(lo, newest) if m not in have]
            if not missing:
                break
    if not have:
        raise RuntimeError('brak komunikatów' + (f' ({fails[0]})' if fails else ''))
    if fails:
        META['errors'].append(mask(f'FSS: {len(fails)} komunikaty nieczytelne, np. {fails[0]}'))
    if missing:
        META['errors'].append(f'FSS: brak komunikatów za miesiące: {", ".join(missing)}')
    last = max(have)
    due = datetime.date(int(_q_ym_add(last, 2)[:4]), int(_q_ym_add(last, 2)[5:7]), 1) + datetime.timedelta(days=34)
    if _now_utc().date() > due:
        META['errors'].append(f'FSS: brak nowego komunikatu po {last} (ostatni termin {due.isoformat()})')
    rates = {}
    if key:
        try:
            rates = fred_rates(key, 'EXKOUS')   # Fed H.10, średnia miesięczna KRW za 1 USD
        except Exception as e:
            META['errors'].append(mask(f'FSS kurs FRED EXKOUS: {e}'))
    rows = [have[k] for k in sorted(have)][-25:]
    for r in rows:
        rt = rates.get(r[0] + '-01')
        if rt:
            r[3:6] = [round(r[1] * 1000 / rt, 1) if r[1] is not None else None, round(r[2] * 1000 / rt, 1) if r[2] is not None else None, rt]
        elif len(r) < 6 or r[5] is None:
            r[3:6] = [None, None, None]
    return {'at': NOW, 'src': 'Financial Supervisory Service (Korea) — monthly press release „Foreign Investors’ Stock and Bond Investment”',
            'url': FSS_LIST.format(p=1),
            'unit': 'mld KRW; akcje = zakupy netto (KOSPI, KOSDAQ, rozliczenie), obligacje = inwestycje netto (zakupy netto minus wykupy); '
                    '≈ mln USD po średnim kursie miesiąca (Fed H.10, FRED EXKOUS)',
            'cols': ['miesiąc', 'akcje mld KRW', 'obligacje mld KRW', 'akcje ≈ mln USD', 'obligacje ≈ mln USD', 'KRW za 1 USD'], 'asof': rows[-1][0], 'm': rows}


def _q_ym_add(ym, k):
    t = int(ym[:4]) * 12 + int(ym[5:7]) - 1 + k
    return f'{t // 12:04d}-{t % 12 + 1:02d}'


def build_krypto(cg_key):
    """data/krypto.json — każda część osobno (awaria jednej nie kasuje pozostałych); CoinGecko z kluczem w nagłówku."""
    out = {'at': NOW, 'src': 'krypto', 'attribution': 'Data by CoinGecko'}
    hdr = {'x-cg-demo-api-key': cg_key} if cg_key else None
    jobs = [('deriv', lambda: parse_deriv(get_json(CG + '/derivatives/exchanges?per_page=20', hdr))),
            ('defi', lambda: parse_defi(get_json(CG + '/global/decentralized_finance_defi', hdr))),
            ('fng', lambda: parse_fng(get_json(FNG_URL))),
            ('mk', lambda: parse_mk([get_json(CG + f'/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page={p}'
                                             '&price_change_percentage=24h,7d,30d,1y', hdr) for p in (1, 2)])),
            ('stabh', lambda: parse_stabh(get_json('https://stablecoins.llama.fi/stablecoincharts/all'))),
            ('stabc', lambda: parse_stabc(get_json('https://stablecoins.llama.fi/stablecoins?includePrices=true')))]   # v58: per sieć
    for name, job in jobs:
        try:
            out[name] = job(); META['ok']['krypto.' + name] = True
        except Exception as e:
            META['errors'].append(mask(f'krypto {name}: {e}')); META['ok']['krypto.' + name] = False
    if not any(k in out for k, _ in jobs):
        raise RuntimeError('żadne źródło rynku krypto nie odpowiedziało')
    return out


ETF_KEEP_DAYS = 60   # v55: tyle dni trzyma etf.json (SoSoValue oddaje tylko ok. 21 ostatnich — reszta z poprzedniego pliku)


def etf_merge_days(prev_day, new_day):
    """v55: [[ts, mln USD], ...] — nowe okno SoSoValue + starsze dni z poprzedniego pliku, TYLKO gdy okna się nakładają
    (bez cichej luki w sumie 22 sesji); dla tego samego dnia wygrywa nowa wartość; ostatnie ETF_KEEP_DAYS dni."""
    new = [r for r in (new_day or []) if isinstance(r, list) and len(r) == 2 and isinstance(r[0], int)]
    old = [r for r in (prev_day or []) if isinstance(r, list) and len(r) == 2 and isinstance(r[0], int) and not isinstance(r[0], bool)
           and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)]
    if not new or not old or max(r[0] for r in old) < min(r[0] for r in new):
        return new
    m = {r[0]: r[1] for r in old}; m.update({r[0]: r[1] for r in new})
    return [[k, m[k]] for k in sorted(m)][-ETF_KEEP_DAYS:]


def build_etf(key, cg_key, prev=None):
    out = {'at': NOW, 'asof': '', 'src': 'SoSoValue', 'live': True, 'mcap': {}, 'assets': {}}
    prev_assets = prev.get('assets') if isinstance(prev, dict) and isinstance(prev.get('assets'), dict) else {}
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
        try:
            pa = prev_assets.get(s) if isinstance(prev_assets.get(s), dict) else {}
            _etf_coin(out, s, key, pa.get('day'))
        except Exception as e:   # v49: brak jednej monety nie kasuje pozostałych
            META['errors'].append(mask(f'SoSoValue {s.upper()}: {e}'))
    if not out['assets']:
        raise RuntimeError('SoSoValue: brak danych dla wszystkich monet')
    _etf_hk(out, key, prev.get('hk') if isinstance(prev, dict) else None)   # v61: Hongkong (próba, nie psuje części USA)
    # fundusze publikują dane w różnych godzinach — jeśli daty różnią się między monetami, pokazujemy zakres, nie najnowszą
    dates = sorted({a['asof'] for a in out['assets'].values()})
    out['asof'] = dates[0] if len(dates) == 1 else f'{dates[0]} – {dates[-1]}'
    return out


def _etf_hk(out, key, prev_assets_hk):
    """v61: ETF-y spot w Hongkongu (SoSoValue country_code=HK), BTC i ETH — dane dzienne jak dla USA (bez listy funduszy).
    Brak/awaria = notatka w meta (nie błąd strony); pole 'fields' mówi, co zwraca API (nazwy pól, bez wartości)."""
    hk = {}
    for s in ('btc', 'eth'):
        if _DEADLINE[0] is not None and time.monotonic() > _DEADLINE[0]:
            META['notes'].append('SoSoValue HK: pominięte — limit czasu przebiegu'); break
        try:
            rows = soso(f'/etfs/summary-history?symbol={s.upper()}&country_code=HK&limit=60', key)
            rows = sorted([r for r in (rows or []) if isinstance(r, dict) and r.get('date') and r.get('total_net_inflow') is not None],
                          key=lambda r: r['date'])
            if not rows:
                META['notes'].append(f'SoSoValue HK {s.upper()}: brak danych'); continue
            last = rows[-1]
            pd = (prev_assets_hk or {}).get(s) if isinstance(prev_assets_hk, dict) else None
            day = etf_merge_days(pd.get('day') if isinstance(pd, dict) else None, [[ts(r['date']), r['total_net_inflow'] / 1e6] for r in rows])
            num = lambda k: last[k] / 1e6 if isinstance(last.get(k), (int, float)) and not isinstance(last.get(k), bool) else None
            hk[s] = {'sym': s.upper(), 'asof': last['date'], 'day': day, 'd1': day[-1][1],
                     'w': sum(v for _, v in day[-5:]) if len(day) >= 5 else None,
                     'm': sum(v for _, v in day[-22:]) if len(day) >= 22 else None, 'm_n': min(len(day), 22),
                     'cum': num('cum_net_inflow'), 'aum': num('total_net_assets'), 'fields': sorted(str(k) for k in last)[:20]}
            META['notes'].append(f'SoSoValue HK {s.upper()}: {len(rows)} dni do {last["date"]}; pola: {", ".join(hk[s]["fields"])}')
        except Exception as e:
            META['notes'].append(mask(f'SoSoValue HK {s.upper()}: {e}'))
    if hk:
        out['hk'] = hk


def _etf_coin(out, s, key, prev_day=None):
        """v49: dane jednej monety (wydzielone z build_etf, żeby błąd jednej nie kasował pozostałych)."""
        rows = soso(f'/etfs/summary-history?symbol={s.upper()}&country_code=US&limit=60', key)
        rows = [r for r in rows if r.get('date') and r.get('total_net_inflow') is not None]
        rows.sort(key=lambda r: r['date'])
        if not rows:
            raise RuntimeError(f'SoSoValue: brak danych dla {s}')
        day = etf_merge_days(prev_day, [[ts(r['date']), r['total_net_inflow'] / 1e6] for r in rows])   # v55: historia dłuższa niż okno API
        last = rows[-1]
        out['asof'] = max(out['asof'], last['date'])
        aum = last['total_net_assets'] / 1e6 if last.get('total_net_assets') else None
        mc = out['mcap'].get(s)
        a = {'sym': s.upper(), 'asof': last['date'], 'day': day, 'd1': day[-1][1],
             'w': sum(v for _, v in day[-5:]), 'm': sum(v for _, v in day[-22:]) if len(day) >= 22 else None, 'm_n': min(len(day), 22),   # v51: 22 sesje albo brak (nie cicha niepełna suma)
            
             'cum': last['cum_net_inflow'] / 1e6, 'aum': aum,
             'share': (aum * 1e6 / mc * 100) if (aum and mc) else None, 'funds': []}
        lst = soso(f'/etfs?symbol={s.upper()}&country_code=US', key)
        for it in (lst or [])[:12]:
            if _DEADLINE[0] is not None and time.monotonic() > _DEADLINE[0]:   # v49: limit czasu przebiegu
                META['errors'].append(f'SoSoValue {s.upper()}: lista funduszy pominięta — limit czasu przebiegu'); break
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


def main():
    _DEADLINE[0] = time.monotonic() + SOSO_BUDGET
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
            save('etf', build_etf(soso_key, cg_key, prev_etf)); META['ok']['sosovalue'] = True
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
    # FRED (klucz właściciela): osiem serii Fed (v50: + depozyt H.4.1), najwyżej raz na 55 min; przy awarii zachowaj poprzedni plik
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
    # TIC (Skarb USA, bez klucza, ~1,6 MB): najwyżej raz na dobę; przy awarii zachowaj poprzedni plik
    prev_tic = previous('tic')
    if prev_tic and fresh(prev_tic, 24 * 60) and 'twn' in prev_tic:   # v50: plik sprzed v48 (bez netto ze wspólnych krajów) pobieramy od nowa
        save('tic', prev_tic); META['ok']['tic'] = 'cached'; print('TIC: dane z', prev_tic.get('at'), '— młodsze niż doba')
    else:
        try:
            save('tic', build_tic()); META['ok']['tic'] = True
        except Exception as e:
            META['errors'].append(mask(f'TIC: {e}')); META['ok']['tic'] = False
            if prev_tic: save('tic', prev_tic); print('TIC zawiódł — zachowano poprzedni tic.json z', prev_tic.get('at'))
    # BIS LBS (bez klucza, ~220 KB, dane kwartalne): najwyżej raz na dobę; przy awarii zachowaj poprzedni plik
    prev_bis = previous('bis')
    if prev_bis and fresh(prev_bis, 24 * 60):
        save('bis', prev_bis); META['ok']['bis'] = 'cached'; print('BIS: dane z', prev_bis.get('at'), '— młodsze niż doba')
    else:
        try:
            save('bis', build_bis()); META['ok']['bis'] = True
        except Exception as e:
            META['errors'].append(mask(f'BIS: {e}')); META['ok']['bis'] = False
            if prev_bis: save('bis', prev_bis); print('BIS zawiódł — zachowano poprzedni bis.json z', prev_bis.get('at'))
    # CFTC TFF (v50, bez klucza): raport w piątki ok. 19:30 UTC (stan na wtorek) — pytamy najwyżej raz na 6 h; przy awarii poprzedni plik
    prev_cftc = previous('cftc')
    if prev_cftc and fresh(prev_cftc, 360):
        save('cftc', prev_cftc); META['ok']['cftc'] = 'cached'; print('CFTC: dane z', prev_cftc.get('at'), '— młodsze niż 6 h')
    else:
        try:
            save('cftc', build_cftc(prev=prev_cftc)); META['ok']['cftc'] = True
        except Exception as e:
            META['errors'].append(mask(f'CFTC: {e}')); META['ok']['cftc'] = False
            if prev_cftc: save('cftc', prev_cftc); print('CFTC zawiódł — zachowano poprzedni cftc.json z', prev_cftc.get('at'))
    # COIN METRICS (Community, bez klucza): dane dzienne (nowy dzień ok. 02–03 UTC) — plik młodszy niż 60 min bez zapytań;
    # przy awarii zachowaj poprzedni plik (pole "at" mówi, jak stary)
    prev_cm = previous('cm')
    if prev_cm and fresh(prev_cm, 60):
        save('cm', prev_cm); META['ok']['cm'] = 'cached'; print('Coin Metrics: dane z', prev_cm.get('at'), '— młodsze niż 60 min')
    else:
        try:
            save('cm', build_cm()); META['ok']['cm'] = True
        except Exception as e:
            msg = str(e)
            META['errors'].append(mask(msg if msg.startswith('Coin Metrics') else f'Coin Metrics: {msg}')); META['ok']['cm'] = False
            if prev_cm: save('cm', prev_cm); print('Coin Metrics zawiódł — zachowano poprzedni cm.json z', prev_cm.get('at'))
    # MFW — rezerwy walutowe (International Liquidity, bez klucza): dane miesięczne, najwyżej raz na dobę; przy awarii poprzedni plik
    prev_res = previous('rezerwy')
    if prev_res and fresh(prev_res, 24 * 60):
        save('rezerwy', prev_res); META['ok']['imf'] = 'cached'; print('MFW: dane z', prev_res.get('at'), '— młodsze niż doba')
    else:
        try:
            save('rezerwy', build_rezerwy()); META['ok']['imf'] = True
        except Exception as e:
            META['errors'].append(mask(f'MFW rezerwy: {e}')); META['ok']['imf'] = False
            if prev_res: save('rezerwy', prev_res); print('MFW zawiódł — zachowano poprzedni rezerwy.json z', prev_res.get('at'))
    # STOPY banków centralnych (BIS, bez klucza): najwyżej co 6 h; przy awarii poprzedni plik
    prev_st = previous('stopy')
    if prev_st and fresh(prev_st, 360):
        save('stopy', prev_st); META['ok']['stopy'] = 'cached'
    else:
        try:
            save('stopy', build_stopy()); META['ok']['stopy'] = True
        except Exception as e:
            META['errors'].append(mask(f'BIS stopy: {e}')); META['ok']['stopy'] = False
            if prev_st: save('stopy', prev_st)
    # KURSY — średnie miesięczne EBC (bez klucza): najwyżej co 12 h (miesiąc publikowany raz, na początku następnego)
    prev_k = previous('kursy')
    if prev_k and fresh(prev_k, 720):
        save('kursy', prev_k); META['ok']['kursy'] = 'cached'
    else:
        try:
            save('kursy', build_kursy()); META['ok']['kursy'] = True
        except Exception as e:
            META['errors'].append(mask(f'EBC kursy: {e}')); META['ok']['kursy'] = False
            if prev_k: save('kursy', prev_k)
    # OBCE — zmierzone dzienne przepływy inwestorów zagranicznych (NSDL Indie, TWSE Tajwan): najwyżej co 3 h
    prev_o = previous('obce')
    pok = (prev_o or {}).get('ok') or {}   # v80: brak oczekiwanej części = pobierz od nowa; część z błędem — ponów po 60 min
    miss = [p for p in ('in', 'tw', 'hk', 'br', 'tr', 'th') if prev_o and p not in prev_o and pok.get(p) is not False]
    retry = [p for p, st in pok.items() if st is False]
    if prev_o and isinstance(prev_o.get('br'), dict) and any(isinstance(r, list) and len(r) < 10 for r in (prev_o['br'].get('m') or [])):
        miss.append('br')   # v81: wiersze miesięczne Brazylii bez kolumn banku centralnego — pobierz od razu
    if prev_o and fresh(prev_o, 180) and not miss and not (retry and not fresh(prev_o, 60)):
        save('obce', prev_o); META['ok']['obce'] = 'cached'
        for p, st in (prev_o.get('ok') or {}).items():   # v77: stan części z ostatniego pełnego pobrania (błąd zostaje widoczny)
            META['ok']['obce_' + p] = 'cached' if st is True else st
        META['errors'].extend(e for es in (prev_o.get('errs') or {}).values() for e in (es if isinstance(es, list) else []))
    else:
        try:
            save('obce', build_obce(fred_key, prev_o)); META['ok']['obce'] = True
        except Exception as e:
            META['errors'].append(mask(f'obce: {e}')); META['ok']['obce'] = False
            if prev_o: save('obce', prev_o)
    # EER — kursy efektywne BIS (bez klucza): najwyżej co 6 h
    prev_e = previous('eer')
    if prev_e and fresh(prev_e, 360):
        save('eer', prev_e); META['ok']['eer'] = 'cached'
    else:
        try:
            save('eer', build_eer()); META['ok']['eer'] = True
        except Exception as e:
            META['errors'].append(mask(f'BIS kursy efektywne: {e}')); META['ok']['eer'] = False
            if prev_e: save('eer', prev_e)
    # COFER — skład walutowy rezerw świata (MFW, kwartalnie): najwyżej raz na dobę
    prev_c = previous('cofer')
    if prev_c and fresh(prev_c, 1440):
        save('cofer', prev_c); META['ok']['cofer'] = 'cached'
    else:
        try:
            save('cofer', build_cofer()); META['ok']['cofer'] = True
        except Exception as e:
            META['errors'].append(mask(f'MFW COFER: {e}')); META['ok']['cofer'] = False
            if prev_c: save('cofer', prev_c)
    # v70: MFW — bilans płatniczy 37 gospodarek (kwartalnie): najwyżej raz na dobę; awaria = poprzedni plik i błąd
    prev_bl = previous('bilans')
    if prev_bl and fresh(prev_bl, 1440):
        save('bilans', prev_bl); META['ok']['bilans'] = 'cached'
    else:
        try:
            save('bilans', build_bilans()); META['ok']['bilans'] = True
        except Exception as e:
            META['errors'].append(mask(f'MFW bilans płatniczy: {e}')); META['ok']['bilans'] = False
            if prev_bl: save('bilans', prev_bl)
    # v72: SAFE — kupno i sprzedaż walut przez banki w Chinach (miesięcznie): najwyżej raz na dobę; awaria = poprzedni plik i błąd
    prev_sf = previous('safe')
    if prev_sf and fresh(prev_sf, 1440):
        save('safe', prev_sf); META['ok']['safe'] = 'cached'
    else:
        try:
            save('safe', build_safe()); META['ok']['safe'] = True
        except Exception as e:
            META['errors'].append(mask(f'SAFE: {e}')); META['ok']['safe'] = False
            if prev_sf: save('safe', prev_sf)
    # v76: Eurostat — bilans płatniczy krajów UE (miesięcznie): najwyżej raz na dobę; awaria = poprzedni plik i błąd
    prev_ue = previous('ue')
    if prev_ue and fresh(prev_ue, 1440) and 'S121' in str(prev_ue.get('unit', '')):   # v80: plik sprzed v80 (pozostałe z bankiem centralnym) — przebuduj
        save('ue', prev_ue); META['ok']['ue'] = 'cached'
    else:
        try:
            save('ue', build_ue()); META['ok']['ue'] = True
        except Exception as e:
            META['errors'].append(mask(f'Eurostat: {e}')); META['ok']['ue'] = False
            if prev_ue and 'S121' in str(prev_ue.get('unit', '')): save('ue', prev_ue)   # v81: pliku w starym formacie nie publikujemy ponownie
    # v78: Kanada — Statistics Canada (miesięcznie): najwyżej raz na dobę; awaria = poprzedni plik i błąd
    prev_ka = previous('kanada')
    if prev_ka and fresh(prev_ka, 1440):
        save('kanada', prev_ka); META['ok']['kanada'] = 'cached'
    else:
        try:
            save('kanada', build_kanada()); META['ok']['kanada'] = True
        except Exception as e:
            META['errors'].append(mask(f'Statistics Canada: {e}')); META['ok']['kanada'] = False
            if prev_ka: save('kanada', prev_ka)
    # v82: Korea — FSS (miesięcznie): najwyżej raz na dobę; awaria = poprzedni plik i błąd
    prev_kr = previous('korea')
    if prev_kr and fresh(prev_kr, 1440):
        save('korea', prev_kr); META['ok']['korea'] = 'cached'
    else:
        try:
            save('korea', build_korea(fred_key, prev_kr)); META['ok']['korea'] = True
        except Exception as e:
            META['errors'].append(mask(f'FSS: {e}')); META['ok']['korea'] = False
            if prev_kr: save('korea', prev_kr)
    # v87: Polska — MF, nierezydenci w krajowych SPW (miesięcznie): najwyżej raz na dobę; awaria = poprzedni plik i błąd
    prev_sp = previous('spw')
    if prev_sp and fresh(prev_sp, 1440):
        save('spw', prev_sp); META['ok']['spw'] = 'cached'
    else:
        try:
            save('spw', build_spw()); META['ok']['spw'] = True
        except Exception as e:
            META['errors'].append(mask(f'MF SPW: {e}')); META['ok']['spw'] = False
            if prev_sp: save('spw', prev_sp)
    # KRYPTO (CoinGecko z kluczem właściciela w nagłówku + Alternative.me): najwyżej raz na 55 min (limit Demo 10 000/mies.)
    prev_kr = previous('krypto')
    if prev_kr and fresh(prev_kr, 55):
        save('krypto', prev_kr); META['ok']['krypto'] = 'cached'; print('KRYPTO: dane z', prev_kr.get('at'), '— młodsze niż 55 min')
    else:
        try:
            save('krypto', build_krypto(cg_key)); META['ok']['krypto'] = True
        except Exception as e:
            META['errors'].append(mask(f'krypto: {e}')); META['ok']['krypto'] = False
            if prev_kr: save('krypto', prev_kr); print('rynek krypto zawiódł — zachowano poprzedni krypto.json z', prev_kr.get('at'))
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
