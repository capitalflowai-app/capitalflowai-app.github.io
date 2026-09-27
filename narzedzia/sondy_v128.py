#!/usr/bin/env python3
"""sondy_v128.py — sondy 8 nowych źródeł bez klucza z listy właściciela (27.09.2026), uruchamiane z serwera GitHub (USA).
Fragmenty działają w przestrzeni nazw narzedzia/sondy.py (te same pomocniki probe/http/report/shape — wypisują TYLKO status, czas,
rozmiar, kształt, liczniki i daty; nigdy treści odpowiedzi, adresów z kluczem ani nagłówków). Osobny plik, żeby nie ruszać sondy.py
(zmienia go równolegle wydanie v127). Kod wyjścia zawsze 0."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sondy as S   # noqa: E402
import gzip, io, re, zipfile, zoneinfo   # noqa: E401,E402 — moduły, których fragmenty używają bez własnego importu
for _m in (gzip, io, re, zipfile, zoneinfo):
    S.__dict__.setdefault(_m.__name__, _m)

S.DEADLINE = time.monotonic() + 300.0   # 8 grup po kolei — dłuższy termin niż w sondy.py (105 s)

GRUPY = []

# ==================================================================================================== premie
KOD_PREMIE = r'''# =========================================================================== v128 (premie): premia koreańska i premia Coinbase — bez kluczy
# Paste into narzedzia/sondy.py after the g_evds group (before GROUPS) and append g_premie to GROUPS.
# Uses only the helpers of sondy.py: http, probe, report, shape, skipped, _print_lock, dt, json, time.
# Prints only: HTTP status, elapsed ms, byte length, counts, key names, minute stamps (UTC), ages in seconds and DERIVED unitless
# premiums in % with 2 decimals (like the Coinalyze group's derived ratios). Never response bodies, raw prices, headers or URLs.
# 19 keyless requests, sequential in one thread (about 10-25 s): ECB 1, Frankfurter 1, Upbit 5, Coinbase Exchange 6, Binance data-api 4,
# fallbacks Bithumb 1 and Kraken 1 (only to know whether they could replace Upbit / Coinbase if one of them is blocked from US runners).
import zoneinfo as _pr_zi   # stdlib; ubuntu-latest has the system tz database (Europe/Berlin for the ECB 14:10 fixing)

PR_UP = "https://api.upbit.com/v1/"
PR_CB = "https://api.exchange.coinbase.com/products/"
PR_BN = "https://data-api.binance.vision/api/v3/"
PR_FX = "https://api.frankfurter.dev/v1/latest?from=USD&to=KRW"
PR_ECB = "https://data-api.ecb.europa.eu/service/data/EXR/D.KRW+USD.EUR.SP00.A?lastNObservations=3&format=csvdata"
_PR = {}   # leg -> {"YYYY-MM-DDTHH:MM": close}; filled by the shape functions below, never printed raw


def _pr_iso_min(sec):
    return dt.datetime.fromtimestamp(sec, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M")


def _pr_info(label, text):
    with _print_lock:
        print(f"{'premie':<15}| env={'-':<26}| {label:<34}| INFO      |        |           | {text}", flush=True)


def _pr_span(m):
    ks = sorted(m)
    return f"minutes={len(ks)} first={ks[0] if ks else '-'} last={ks[-1] if ks else '-'}"


def _pr_up_ticker(raw):
    L = json.loads(raw)
    if not isinstance(L, list):
        return "not-a-list " + shape(raw)
    now = time.time() * 1000
    ages = {str(x.get("market")): int((now - x["trade_timestamp"]) / 1000) for x in L
            if isinstance(x, dict) and isinstance(x.get("trade_timestamp"), (int, float))}
    pos = all(isinstance(x.get("trade_price"), (int, float)) and x["trade_price"] > 0 for x in L if isinstance(x, dict))
    return f"list n={len(L)} price_pos={pos} trade_age_s=" + ",".join(f"{k}:{v}" for k, v in sorted(ages.items()))


def _pr_up_candles(leg):
    def fn(raw):
        L = json.loads(raw)
        if not isinstance(L, list):
            return "not-a-list " + shape(raw)
        m = {}
        for x in L:
            if isinstance(x, dict) and isinstance(x.get("candle_date_time_utc"), str) and isinstance(x.get("trade_price"), (int, float)) and x["trade_price"] > 0:
                m[x["candle_date_time_utc"][:16]] = float(x["trade_price"])
        _PR[leg] = m
        stamps = [x.get("candle_date_time_utc") for x in L if isinstance(x, dict)]
        keys = ",".join(sorted(L[0].keys())) if L and isinstance(L[0], dict) else "-"
        return f"list n={len(L)} {_pr_span(m)} desc={stamps == sorted(stamps, reverse=True)} keys={keys}"
    return fn


def _pr_cb_ticker(raw):
    o = json.loads(raw)
    if not isinstance(o, dict):
        return shape(raw)
    try:
        t = dt.datetime.fromisoformat(str(o.get("time"))[:26].rstrip("Z") + "+00:00")
        age = int(time.time() - t.timestamp())
    except Exception:
        age = "-"
    return f"keys=[{','.join(sorted(o.keys()))}] trade_age_s={age}"


def _pr_cb_candles(leg):
    def fn(raw):
        L = json.loads(raw)
        if not isinstance(L, list):
            return "not-a-list " + shape(raw)
        m = {}
        for r in L:
            if isinstance(r, list) and len(r) >= 6 and isinstance(r[0], (int, float)) and isinstance(r[4], (int, float)) and r[4] > 0:
                m[_pr_iso_min(r[0])] = float(r[4])     # [time, low, high, open, close, volume]
        _PR[leg] = m
        ts = [r[0] for r in L if isinstance(r, list) and r]
        return f"list n={len(L)} {_pr_span(m)} desc={ts == sorted(ts, reverse=True)} row_len={len(L[0]) if L and isinstance(L[0], list) else '-'}"
    return fn


def _pr_bn_klines(leg):
    def fn(raw):
        L = json.loads(raw)
        if not isinstance(L, list):
            return "not-a-list " + shape(raw)
        m = {}
        for r in L:
            try:
                c = float(r[4])                      # [openTime ms, open, high, low, close (string), volume, closeTime, ...]
            except Exception:
                continue
            if c > 0:
                m[_pr_iso_min(r[0] / 1000)] = c
        _PR[leg] = m
        return f"list n={len(L)} {_pr_span(m)} row_len={len(L[0]) if L and isinstance(L[0], list) else '-'}"
    return fn


def _pr_kr_ohlc(leg):
    def fn(raw):
        o = json.loads(raw)
        if not isinstance(o, dict) or o.get("error"):
            return "kraken-error " + shape(raw)
        res = o.get("result") or {}
        rows = next((v for k, v in res.items() if k != "last" and isinstance(v, list)), [])
        m = {}
        for r in rows:
            try:
                c = float(r[4])                      # [time, open, high, low, close (string), vwap, volume, count]
            except Exception:
                continue
            if c > 0:
                m[_pr_iso_min(r[0])] = c
        _PR[leg] = m
        return f"rows={len(rows)} {_pr_span(m)} row_len={len(rows[0]) if rows and isinstance(rows[0], list) else '-'}"
    return fn


def _pr_fx(raw):
    o = json.loads(raw)
    r = (o.get("rates") or {}).get("KRW") if isinstance(o, dict) else None
    _PR["fx"] = (str(o.get("date")), float(r)) if isinstance(r, (int, float)) and r > 0 else None
    return f"keys=[{','.join(sorted(o.keys()))}] date={o.get('date')} krw_pos={bool(_PR['fx'])}"


def _pr_ecb(raw):
    import csv as _csv, io as _io
    rows = list(_csv.DictReader(_io.StringIO(raw.decode("utf-8", "replace"))))
    d = {}
    for r in rows:
        try:
            d.setdefault(r["CURRENCY"], {})[r["TIME_PERIOD"]] = float(r["OBS_VALUE"])
        except Exception:
            pass
    common = sorted(set(d.get("KRW", {})) & set(d.get("USD", {})))
    if common:
        last = common[-1]
        _PR["ecb"] = (last, d["KRW"][last] / d["USD"][last])
    return f"csv rows={len(rows)} dates={','.join(common)}"


def _pr_prem(a, b, fx=None, adj=None, last_n=5, before=None):
    """Median premium in % over the last `last_n` minutes present in every leg (a vs b, b converted by fx or adj per minute)."""
    legs = [a, b] + ([adj] if isinstance(adj, dict) else [])
    common = sorted(set.intersection(*[set(x) for x in legs])) if all(legs) else []
    if before:
        common = [k for k in common if k < before]
    use = common[-last_n:]
    vals = []
    for k in use:
        ref = b[k] * (fx if fx else 1.0) * (adj[k] if isinstance(adj, dict) else 1.0)
        vals.append((a[k] / ref - 1.0) * 100.0)
    if not vals:
        return "common=0 p=-"
    vals.sort()
    med = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
    return f"common={len(common)} used={use[0]}..{use[-1]} p_med={med:+.2f}% spread={vals[-1] - vals[0]:.2f}pp"


def _pr_fixing_utc(day_iso):
    """ECB concertation 'around 14:10 CET' read as 14:10 Frankfurt local time -> the UTC minute of that day."""
    d = dt.date.fromisoformat(day_iso)
    loc = dt.datetime(d.year, d.month, d.day, 14, 10, tzinfo=_pr_zi.ZoneInfo("Europe/Berlin"))
    return loc.astimezone(dt.timezone.utc)


def g_premie():
    now = int(time.time())
    closed = _pr_iso_min((now // 60) * 60)            # minutes strictly before this one are closed
    # 1) FX first (Frankfurter = ECB reference rates; the collector's rynki.json uses the same host) + ECB itself as a cross-check
    probe("ecb-fx", "frankfurter_latest_USD_KRW", PR_FX, extra_fn=_pr_fx)
    probe("ecb-fx", "ecb_EXR_D_KRW_USD_last3", PR_ECB, extra_fn=_pr_ecb)
    # 2) Upbit (KRW): ticker snapshot + 1-minute candles of the last ~10 minutes (newest first; `to` omitted = up to now)
    probe("upbit", "ticker_KRW-BTC,ETH,USDT", PR_UP + "ticker?markets=KRW-BTC,KRW-ETH,KRW-USDT", extra_fn=_pr_up_ticker)
    for mk, leg in (("KRW-BTC", "up_btc"), ("KRW-ETH", "up_eth"), ("KRW-USDT", "up_usdt")):
        time.sleep(0.15)                               # quotation group: 10 requests per second per IP
        probe("upbit", f"candles_1m_{mk}_x10", PR_UP + f"candles/minutes/1?market={mk}&count=10", extra_fn=_pr_up_candles(leg))
    # 3) Coinbase Exchange (USD): ticker + 1-minute candles for the same window; USDT-USD for the stablecoin correction
    probe("coinbase-ex", "ticker_BTC-USD", PR_CB + "BTC-USD/ticker", extra_fn=_pr_cb_ticker)
    for pid, leg in (("BTC-USD", "cb_btc"), ("ETH-USD", "cb_eth"), ("USDT-USD", "cb_usdt")):
        time.sleep(0.15)
        probe("coinbase-ex", f"candles_60_{pid}_10min", PR_CB + f"{pid}/candles?granularity=60&start={now - 660}&end={now}",
              extra_fn=_pr_cb_candles(leg))
    time.sleep(0.15)
    probe("coinbase-ex", "candles_3600_BTC-USD_300h", PR_CB + f"BTC-USD/candles?granularity=3600&start={now - 299 * 3600}&end={now}",
          extra_fn=_pr_cb_candles("cb_btc_h"))                  # history in chunks: at most 300 buckets per explicit range (else HTTP 400)
    # 4) Binance global through the public market-data mirror (api.binance.com answers 451 from US runners)
    probe("bn-data-api", "ticker_price_BTCUSDT", PR_BN + "ticker/price?symbol=BTCUSDT")
    for sym, leg in (("BTCUSDT", "bn_btc"), ("ETHUSDT", "bn_eth"), ("BTCUSDC", "bn_btcusdc")):
        time.sleep(0.1)
        probe("bn-data-api", f"klines_1m_{sym}_x11", PR_BN + f"klines?symbol={sym}&interval=1m&startTime={(now - 660) * 1000}&limit=11",
              extra_fn=_pr_bn_klines(leg))
    # 5) derived premiums on CLOSED minutes present in every leg (median of the last 5 common minutes)
    fx = (_PR.get("ecb") or _PR.get("fx") or (None, None))[1]     # plan: ECB itself first, Frankfurter (v1 = ECB rates) as fallback
    _pr_info("fx_ecb_vs_frankfurter", f"frankfurter={(_PR.get('fx') or ('-',))[0]} ecb={(_PR.get('ecb') or ('-',))[0]} "
             + (f"cross_diff={abs(_PR['fx'][1] / _PR['ecb'][1] - 1) * 100:.3f}%" if _PR.get("fx") and _PR.get("ecb") else "cross_diff=-"))
    if fx:
        _pr_info("kr_btc_vs_coinbase_x_ecb", _pr_prem(_PR.get("up_btc"), _PR.get("cb_btc"), fx=fx, before=closed))
        _pr_info("kr_eth_vs_coinbase_x_ecb", _pr_prem(_PR.get("up_eth"), _PR.get("cb_eth"), fx=fx, before=closed))
        _pr_info("kr_usdt_vs_ecb", _pr_prem(_PR.get("up_usdt"), {k: 1.0 for k in (_PR.get("up_usdt") or {})}, fx=fx, before=closed))
    else:
        _pr_info("kr_premia", "no ECB USD/KRW rate -> skipped")
    _pr_info("cb_btc_vs_binance_raw", _pr_prem(_PR.get("cb_btc"), _PR.get("bn_btc"), before=closed))
    _pr_info("cb_btc_vs_binance_usdt_adj", _pr_prem(_PR.get("cb_btc"), _PR.get("bn_btc"), adj=_PR.get("cb_usdt"), before=closed))
    _pr_info("cb_eth_vs_binance_usdt_adj", _pr_prem(_PR.get("cb_eth"), _PR.get("bn_eth"), adj=_PR.get("cb_usdt"), before=closed))
    _pr_info("cb_btc_vs_binance_usdc", _pr_prem(_PR.get("cb_btc"), _PR.get("bn_btcusdc"), before=closed))
    # 6) history at the ECB fixing minute of the latest ECB day: 5 minutes ending at the fixing (both venues keep 1m history for years)
    day = (_PR.get("ecb") or _PR.get("fx") or (None,))[0]
    if day and fx:
        fix = _pr_fixing_utc(day)
        s = int(fix.timestamp())
        time.sleep(0.15)
        probe("upbit", "candles_1m_KRW-BTC_at_ecb_fixing", PR_UP + f"candles/minutes/1?market=KRW-BTC&count=5&to={fix.strftime('%Y-%m-%dT%H:%M:%SZ')}",
              extra_fn=_pr_up_candles("up_fix"))
        time.sleep(0.15)
        probe("coinbase-ex", "candles_60_BTC-USD_at_ecb_fixing", PR_CB + f"BTC-USD/candles?granularity=60&start={s - 300}&end={s}",
              extra_fn=_pr_cb_candles("cb_fix"))
        _pr_info("kr_btc_at_ecb_fixing", f"day={day} fixing_utc={fix.strftime('%H:%M')} "
                 + _pr_prem(_PR.get("up_fix"), _PR.get("cb_fix"), fx=fx, before=_pr_iso_min(s)))

    # 7) fallbacks, only to learn whether they answer from a US runner (not used unless Upbit or Coinbase is blocked there)
    time.sleep(0.15)
    probe("bithumb", "candles_1m_KRW-BTC_x10", "https://api.bithumb.com/v1/candles/minutes/1?market=KRW-BTC&count=10",
          extra_fn=_pr_up_candles("bt_btc"))                    # same response shape as Upbit (ticker trade_timestamp is shifted +9 h: do not use it)
    probe("kraken", "OHLC_1m_XBTUSD_since10min", f"https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=1&since={now - 660}",
          extra_fn=_pr_kr_ohlc("kr_btc"))
    if fx:
        _pr_info("fallback_kr_bithumb_vs_cb", _pr_prem(_PR.get("bt_btc"), _PR.get("cb_btc"), fx=fx, before=closed))
    _pr_info("fallback_kraken_vs_binance_adj", _pr_prem(_PR.get("kr_btc"), _PR.get("bn_btc"), adj=_PR.get("cb_usdt"), before=closed))
'''
exec(compile(KOD_PREMIE, "sondy_v128/premie", "exec"), S.__dict__)
GRUPY.append(("premie", S.__dict__["g_premie"]))

# ==================================================================================================== farside
KOD_FARSIDE = r'''# ---------------------------------------------------------------- v128 (27.09): Farside (TYLKO HTTPS), CoinShares, BlackRock IBIT/ETHA
# Wklejenie do narzedzia/sondy.py: (1) `import re` i `import xml.etree.ElementTree as ET` do importów na górze;
# (2) ten blok przed GROUPS; (3) g_farside na końcu listy GROUPS; (4) w sondy.yml dopisać 'farside','coinshares','blackrock'
# do filtra B (linia z 'coinalyze','banxico','evds'), żeby wiersze trafiły do adnotacji.
# Celowo BEZ wariantu http:// (port 80) dla Farside: tam wyzwanie Cloudflare nie działa, a korzystanie z tego byłoby obchodzeniem
# zabezpieczenia przed automatami. Wypisuje tylko: status, bajty, rodzaj strony, liczby wierszy i daty — nigdy wartości ani treści.
FS_BASE = 'https://farside.co.uk/'
FS_UA = {'User-Agent': 'CapitalFlowAI-collector/1.0'}
FS_HTML = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'Accept-Language': 'en-GB,en;q=0.9'}
CS_SITEMAP = 'https://coinshares.com/sitemap/sitemap-articles__main.xml'
BR_DOC = ('https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appType=PRODUCT_PAGE'
          '&appSubType=ISHARES&targetSite=us-ishares&locale=en_US&portfolioId={pid}&component=fundDownload&userType=individual')
BR_PID = (('ibit', '333011'), ('etha', '337614'))
_FS_DATE = re.compile(rb'<td[^>]*>\s*<span[^>]*>\s*(\d{2} [A-Z][a-z]{2} \d{4})\s*<')
_CS_FF = re.compile(rb'<loc>(https://coinshares\.com/insights/research-data/fund-flows-(\d{1,2})-(\d{1,2})-(\d{2,4})/?)</loc>')


def _page_kind(raw):
    """Rodzaj odpowiedzi bez treści: cf-challenge / rss / html / xml / other / empty."""
    if not raw:
        return 'empty'
    h = raw[:30000]
    if b'challenge-platform' in h or b'cf_chl_opt' in h or b'<title>Just a moment' in h:
        return 'cf-challenge'
    top = h[:3000].lower()
    if b'<rss' in top:
        return 'rss'
    if b'<html' in top or b'<!doctype html' in top:
        return 'html'
    return 'xml' if top.lstrip().startswith(b'<?xml') else 'other'


def _span(ds):
    return f'{min(ds)}..{max(ds)}' if ds else '-'


def _fs_shape(raw):
    """Farside: tabela class="etf" — liczba wierszy, wierszy z datą, zakres dat, liczba kolumn nagłówka funduszy."""
    k = _page_kind(raw)
    if k != 'html':
        return k
    m = re.search(rb'<table class="etf">(.*?)</table>', raw, re.S)
    if not m:
        return 'html no-table.etf'
    ds = []
    for x in _FS_DATE.findall(m.group(1)):
        try:
            ds.append(dt.datetime.strptime(x.decode(), '%d %b %Y').date())
        except ValueError:
            pass
    return f'table.etf tr={m.group(1).count(b"<tr")} dated={len(ds)} {_span(ds)}'


def _rss_shape(raw):
    k = _page_kind(raw)
    if k != 'rss':
        return k
    m = re.search(rb'<lastBuildDate>([^<]+)</lastBuildDate>', raw)
    d = '-'
    if m:
        try:
            d = dt.datetime.strptime(m.group(1).decode().strip(), '%a, %d %b %Y %H:%M:%S %z').date().isoformat()
        except ValueError:
            pass
    return f'rss items={raw.count(b"<item>")} lastBuild={d}'


def _cs_dates(raw):
    out = []
    for url, d, mo, y in _CS_FF.findall(raw or b''):
        y = int(y) + (2000 if int(y) < 100 else 0)
        try:
            out.append((dt.date(y, int(mo), int(d)), url.decode()))
        except ValueError:
            pass
    return sorted(out)


def _cs_shape(raw):
    ds = _cs_dates(raw)
    return f'{_page_kind(raw)} fund-flows urls={len(ds)} latest={ds[-1][0] if ds else "-"}'


def _cs_article_shape(raw):
    low = raw.lower()
    return (f'{_page_kind(raw)} tables={low.count(b"<table")} png={low.count(b".png")} csv={low.count(b".csv")} '
            f'xlsx={low.count(b".xlsx")} json-ld={low.count(b"application/ld+json")}')


def _br_shape(raw):
    """BlackRock iShares, plik funduszu (Excel 2003 XML), arkusz Historical: liczba wierszy i zakres dat „As Of”."""
    ns = '{urn:schemas-microsoft-com:office:spreadsheet}'
    txt = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', raw.decode('utf-8-sig', 'replace'))
    ws = next((w for w in ET.fromstring(txt).iter(ns + 'Worksheet') if w.get(ns + 'Name') == 'Historical'), None)
    if ws is None:
        return 'no Historical sheet'
    head, ds = None, []
    for row in ws.iter(ns + 'Row'):
        c = [(x.find(ns + 'Data').text if x.find(ns + 'Data') is not None else '') or '' for x in row.iter(ns + 'Cell')]
        if head is None:
            if 'As Of' in c and 'NAV per Share' in c and 'Shares Outstanding' in c:
                head = {n: i for i, n in enumerate(c)}
            continue
        try:
            ds.append(dt.datetime.strptime(c[head['As Of']].strip(), '%b %d, %Y').date())
        except (ValueError, IndexError):
            pass
    return 'Historical: no As Of/NAV/Shares header' if head is None else f'Historical rows={len(ds)} {_span(ds)}'


def _probe_any(provider, label, url, headers, fn):
    """Jak probe(), ale kształt liczony także dla odpowiedzi ≠ 200 (403 z wyzwaniem Cloudflare) — tylko rodzaj i liczby."""
    status, raw, ms, err = http(url, headers=headers)
    extra = None
    if raw:
        try:
            extra = fn(raw)
        except Exception as e:
            extra = type(e).__name__
    report(provider, None, label, status, raw, ms, err, extra)
    return status, raw


def g_farside():
    for label, path, hdr in (('https_btc_genericUA_ctrl', 'btc/', {'User-Agent': 'Python-urllib/3.12'}),   # kontrola: lokalnie 403 cf-challenge
                             ('https_btc_sondyUA', 'btc/', None), ('https_btc_collectorUA', 'btc/', FS_UA),
                             ('https_btc_collectorUA_html', 'btc/', dict(FS_UA, **FS_HTML)), ('https_eth_collectorUA', 'eth/', FS_UA),
                             ('https_btc_alldata_collectorUA', 'bitcoin-etf-flow-all-data/', dict(FS_UA, **FS_HTML))):
        _probe_any('farside', label, FS_BASE + path, hdr, _fs_shape)
        time.sleep(0.5)
    _probe_any('farside', 'https_feed_control', FS_BASE + 'feed/', FS_UA, _rss_shape)
    st, raw = _probe_any('coinshares', 'sitemap_articles_main', CS_SITEMAP, FS_UA, _cs_shape)
    ds = _cs_dates(raw) if st == 200 else []
    if ds:
        _probe_any('coinshares', 'latest_fund_flows_article', ds[-1][1], FS_UA, _cs_article_shape)
    else:
        skipped('coinshares', 'latest_fund_flows_article', 'no fund-flows url in sitemap')
    for t, pid in BR_PID:
        time.sleep(0.5)
        _probe_any('blackrock', f'historical_{t}', BR_DOC.format(pid=pid), FS_UA, _br_shape)
'''
exec(compile(KOD_FARSIDE, "sondy_v128/farside", "exec"), S.__dict__)
GRUPY.append(("farside", S.__dict__["g_farside"]))

# ==================================================================================================== kalshi
KOD_KALSHI = r'''# --------------------------------------------------------------------------- kalshi (v128)
# --- paste into narzedzia/sondy.py after the last group (before "GROUPS = [") and append g_kalshi to GROUPS;
#     in .github/workflows/sondy.yml add 'kalshi' to the provider tuple of the annotation filter (no secret, keyless). ---
# Kalshi public market data (docs.kalshi.com, "Quick Start: Market Data": no authentication for these endpoints).
# 7 GET requests, keyless, read-only, ~0.3 s apart. Prints only: HTTP status, size, key names, counts, public calendar
# dates/tickers of Fed meetings, ages in minutes/hours and derived unitless checks (sum of outcome midpoints, max spread)
# — never response bodies, prices per outcome, headers or URLs.
KS_B = "https://external-api.kalshi.com/trade-api/v2"
KS_B2 = "https://api.elections.kalshi.com/trade-api/v2"
KS_UA = {"User-Agent": "CapitalFlowAI-collector/1.0"}      # the collector's own User-Agent (sondy default UA is tested too)
_KS = {"next": [], "tickers": []}


def _ks_f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _ks_age_min(iso):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return int((dt.datetime.now(dt.timezone.utc) - t).total_seconds() // 60)
    except Exception:
        return None


def _ks_events(raw):
    j = json.loads(raw)
    E = j.get("events") if isinstance(j, dict) else None
    if not isinstance(E, list):
        return "no-events " + shape(raw)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = []
    for e in E:
        M = [m for m in (e.get("markets") or []) if isinstance(m, dict)]
        closes = sorted(str(m.get("close_time") or "") for m in M)
        if not M or not closes or closes[0] <= now:
            continue
        rows.append((str(e.get("strike_date") or ""), str(e.get("event_ticker") or ""), M))
    rows.sort()
    _KS["next"] = [r[1] for r in rows[:2]]
    _KS["tickers"] = [str(m.get("ticker") or "") for r in rows[:2] for m in r[2]]
    parts = [f"events={len(E)} open_future={len(rows)} per_event={sorted({len(r[2]) for r in rows})}"]
    for sd, et, M in rows[:2]:
        mids, spreads, cs_ok, fields_ok = [], [], 0, 0
        for m in M:
            b, a = _ks_f(m.get("yes_bid_dollars")), _ks_f(m.get("yes_ask_dollars"))
            if a is not None and b is not None and a > 0:
                mids.append((a + b) / 2); spreads.append(a - b)
            cs = m.get("custom_strike")
            cs_ok += isinstance(cs, dict) and len(cs) == 1 and next(iter(cs)) in ("Hike", "Cut")
            fields_ok += all(k in m for k in ("last_price_dollars", "volume_fp", "volume_24h_fp", "open_interest_fp", "previous_yes_bid_dollars"))
        parts.append(f"{et}@{sd[:16]} n={len(M)} strike_ok={cs_ok} fields_ok={fields_ok} "
                     f"sum_mid={sum(mids):.3f} max_spread={max(spreads) if spreads else -1:.2f} "
                     f"status={','.join(sorted({str(m.get('status')) for m in M}))}")
    return " | ".join(parts)


def _ks_trade(raw):
    j = json.loads(raw)
    T = j.get("trades") if isinstance(j, dict) else None
    if not isinstance(T, list):
        return "no-trades " + shape(raw)
    return f"trades={len(T)} last_trade_age_min={_ks_age_min(T[0].get('created_time')) if T else '-'} keys={','.join(sorted(T[0])[:10]) if T else '-'}"


def _ks_candles(raw):
    j = json.loads(raw)
    M = j.get("markets") if isinstance(j, dict) else None
    if not isinstance(M, list):
        return "no-markets " + shape(raw)
    n = [len(m.get("candlesticks") or []) for m in M]
    ends = sorted(c.get("end_period_ts") for m in M for c in (m.get("candlesticks") or []) if isinstance(c.get("end_period_ts"), int))
    no_px = sum(1 for m in M for c in (m.get("candlesticks") or []) if not (c.get("price") or {}).get("close_dollars"))
    no_ba = sum(1 for m in M for c in (m.get("candlesticks") or []) if not (c.get("yes_bid") or {}).get("close_dollars") or not (c.get("yes_ask") or {}).get("close_dollars"))
    hrs = sorted({dt.datetime.fromtimestamp(e, dt.timezone.utc).hour for e in ends})
    first = dt.datetime.fromtimestamp(ends[0], dt.timezone.utc).date() if ends else "-"
    last = dt.datetime.fromtimestamp(ends[-1], dt.timezone.utc).isoformat()[:16] if ends else "-"
    return f"markets={len(M)} candles={sum(n)} per_market={min(n) if n else 0}..{max(n) if n else 0} first_end={first} last_end={last} end_hours_utc={hrs} no_trade_days={no_px} no_bidask={no_ba}"


def _ks_settled(raw):
    j = json.loads(raw)
    M = j.get("markets") if isinstance(j, dict) else None
    if not isinstance(M, list):
        return "no-markets " + shape(raw)
    ev = sorted({str(m.get("event_ticker")) for m in M})
    yes = sum(1 for m in M if m.get("result") == "yes")
    return f"markets={len(M)} events={','.join(e.split('-')[-1] for e in ev)} result_yes={yes} statuses={','.join(sorted({str(m.get('status')) for m in M}))}"


def g_kalshi():
    base = f"{KS_B}/events?series_ticker=KXFEDDECISION&status=open&with_nested_markets=true&limit=200"
    st, _ = probe("kalshi", "events_open_nested_collectorUA", base, headers=KS_UA, extra_fn=_ks_events)
    time.sleep(0.3)
    probe("kalshi", "series_sondyUA", f"{KS_B}/series/KXFEDDECISION")            # default sondy UA (browser-like)
    time.sleep(0.3)
    if _KS["tickers"]:
        probe("kalshi", "trades_limit1_next_mtg", f"{KS_B}/markets/trades?ticker={_KS['tickers'][0]}&limit=1", headers=KS_UA, extra_fn=_ks_trade)
        time.sleep(0.3)
        now = int(time.time())
        ts = ",".join(_KS["tickers"][:10])
        probe("kalshi", "candles_1d_122d_batch10", f"{KS_B}/markets/candlesticks?market_tickers={ts}&start_ts={now - 122 * 86400}&end_ts={now}&period_interval=1440",
              headers=KS_UA, extra_fn=_ks_candles)
        time.sleep(0.3)
    else:
        skipped("kalshi", "trades/candles", "no open meeting parsed")
    probe("kalshi", "settled_75d", f"{KS_B}/markets?series_ticker=KXFEDDECISION&status=settled&min_settled_ts={int(time.time()) - 75 * 86400}&limit=100",
          headers=KS_UA, extra_fn=_ks_settled)
    time.sleep(0.3)
    probe("kalshi", "fallback_host_series", f"{KS_B2}/series/KXFEDDECISION", headers=KS_UA)
    time.sleep(0.3)
    probe("kalshi", "bad_event_expect404", f"{KS_B}/events/KXFEDDECISION-00XXX", headers=KS_UA)
'''
exec(compile(KOD_KALSHI, "sondy_v128/kalshi", "exec"), S.__dict__)
GRUPY.append(("kalshi", S.__dict__["g_kalshi"]))

# ==================================================================================================== bgeometrics
KOD_BGEOMETRICS = r'''# --- v128 (27.09): BGeometrics / bitcoin-data.com — wskaźniki on-chain BTC, BEZ klucza --------------------------------------------
# Do wklejenia do narzedzia/sondy.py przed listą GROUPS, a g_bgeometrics dopisać na końcu GROUPS.
# Limit planu darmowego bez klucza: 10 zapytań/h i 15/dobę NA ADRES IP, liczone od pierwszego zapytania (okno 1 h i 24 h), liczy KAŻDE
# zapytanie do hosta API (także 404 i /v3/api-docs) — dlatego tylko 3 zapytania. Drukujemy wyłącznie status, rozmiar, liczbę wierszy,
# daty pierwszego/ostatniego dnia, opóźnienie w dniach, nazwy pól i flagę delayed — nigdy wartości wskaźników ani treści.
BG_API = "https://api.bitcoin-data.com/v1/"
BG_UA = "CapitalFlowAI-collector/1.0"      # ten sam User-Agent co zbieraj_dane.py (sondy mają własny UA w http())


def _bg_rows(raw, field):
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    ds = sorted(r["d"] for r in obj if isinstance(r, dict) and isinstance(r.get("d"), str) and len(r["d"]) == 10)
    num = sum(1 for r in obj if isinstance(r, dict) and isinstance(r.get(field), (int, float)) and not isinstance(r.get(field), bool))
    fields = sorted({str(k)[:16] for r in obj[:3] if isinstance(r, dict) for k in r})
    lag = (_utc_today() - dt.date.fromisoformat(ds[-1])).days if ds else None
    return (f"list n={len(obj)} num_{field}={num} first={ds[0] if ds else '-'} last={ds[-1] if ds else '-'} "
            f"lag_d={lag} fields=[{','.join(fields)}]")


def _bg_last(field):
    def f(raw):
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            return shape(raw)
        d = obj.get("d")
        lag = (_utc_today() - dt.date.fromisoformat(d)).days if isinstance(d, str) and len(d) == 10 else None
        v = obj.get(field)
        return (f"keys=[{','.join(sorted(str(k)[:16] for k in obj))}] d={d if lag is not None else '-'} lag_d={lag} "
                f"num={isinstance(v, (int, float)) and not isinstance(v, bool)} delayed={obj.get('delayed')}")
    return f


def g_bgeometrics():
    start = (_utc_today() - dt.timedelta(days=400)).isoformat()
    # 1) lista z zakresem (UA zbieracza): SOPR — oczekiwane lag_d=7 (plan darmowy przycina ostatnie 7 dni), n ≈ 394
    probe("bgeometrics", "sopr_list_400d_collectorUA", f"{BG_API}sopr?startday={start}",
          headers={"User-Agent": BG_UA}, extra_fn=lambda raw: _bg_rows(raw, "sopr"))
    time.sleep(1.0)
    # 2) ostatnia wartość (UA sond): MVRV — oczekiwane delayed=True, lag_d=7
    probe("bgeometrics", "mvrv_last_probeUA", f"{BG_API}mvrv/last", extra_fn=_bg_last("mvrv"))
    time.sleep(1.0)
    # 3) punkt końcowy bez kłódki (realized cap) — czy świeży (lag_d 1–2) z serwera w USA
    probe("bgeometrics", "realized_cap_last", f"{BG_API}realized-cap/last",
          headers={"User-Agent": BG_UA}, extra_fn=_bg_last("realizedCap"))
    # HTTP 429 = limit IP wyczerpany (wspólne adresy runnerów GitHub) — to też wynik sondy, nie błąd kodu
'''
exec(compile(KOD_BGEOMETRICS, "sondy_v128/bgeometrics", "exec"), S.__dict__)
GRUPY.append(("bgeometrics", S.__dict__["g_bgeometrics"]))

# ==================================================================================================== rwa
KOD_RWA = r'''# --- paste into narzedzia/sondy.py (v128, label "rwa") ---------------------------------------------------------------
# Keyless. 12 requests to api.llama.fi (free, official public API). Prints only: HTTP status, ms, bytes (compressed and
# decompressed), counts, booleans, dates (listedAt / history dates) and public slugs of the probe itself — never a value in USD,
# a response body, a URL or a header. Needs `import gzip` at the top of sondy.py (stdlib).
# Also: add g_defillama_rwa to GROUPS and 'defillama-rwa' to the provider tuple of the annotation filter in
# .github/workflows/sondy.yml (so the lines reach the ::notice).
import gzip   # (top of sondy.py)

LL_API = "https://api.llama.fi"
LL_HIDDEN = ("blackrock-buidl", "circle-usyc", "ondo-yield-assets", "tether-gold", "spiko", "fidelity-digital-interest-token")
LL_UA_COLLECTOR = {"User-Agent": "CapitalFlowAI-collector/1.0", "Accept-Encoding": "gzip"}


def _ll_body(raw):
    """gzip (magic 1f8b) -> bytes; anything else unchanged."""
    return gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def _ll_protocols(raw):
    """/protocols: total rows, RWA rows, RWA with number TVL > 0, with TVL null, dead, tags seen, change_7d present,
    newest listedAt (date), whether the flagship hidden products are really null, decompressed size, parse ok."""
    body = _ll_body(raw)
    L = json.loads(body)
    if not isinstance(L, list):
        return "not-a-list " + shape(body)
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    R = [p for p in L if isinstance(p, dict) and p.get("category") == "RWA"]
    pos = [p for p in R if num(p.get("tvl")) and p["tvl"] > 0]
    nul = [p for p in R if p.get("tvl") is None]
    dead = sum(1 for p in R if p.get("deadFrom"))
    tags = sorted({t for p in R for t in (p.get("tags") or []) if isinstance(t, str)})
    c7 = sum(1 for p in pos if num(p.get("change_7d")))
    la = [p["listedAt"] for p in R if num(p.get("listedAt"))]
    newest = dt.datetime.fromtimestamp(max(la), dt.timezone.utc).date().isoformat() if la else "-"
    by = {p.get("slug"): p for p in R}
    hid = all(by.get(s, {}).get("tvl", 0) is None for s in LL_HIDDEN[:5])
    keys = sorted(set().union(*(p.keys() for p in R))) if R else []
    has_c30 = any(k in keys for k in ("change_1m", "change_30d"))
    return (f"raw={len(body)}B list n={len(L)} rwa={len(R)} tvl>0={len(pos)} tvl_null={len(nul)} dead={dead} c7_present={c7}/{len(pos)} "
            f"has_30d_field={has_c30} tags={len(tags)} newest_listed={newest} flagship_hidden={hid} "
            f"rwaAssetIds={sum(1 for p in R if p.get('rwaAssetIds'))}")


def _ll_tvl(raw):
    """/tvl/{slug}: plain number (text). Only: empty / number>0 / other — never the number."""
    body = _ll_body(raw).strip()
    if not body:
        return "empty-body (no value)"
    try:
        v = float(body)
    except ValueError:
        return "not-a-number " + shape(body)
    return f"number>0={v > 0} len={len(body)}"


def _ll_hist(raw):
    """/protocol/{slug}: number of TVL history points, first/last date, last point age (h), daily spacing."""
    body = _ll_body(raw)
    d = json.loads(body)
    if not isinstance(d, dict):
        return shape(body)
    tv = [x for x in (d.get("tvl") or []) if isinstance(x, dict) and isinstance(x.get("date"), (int, float))]
    if not tv:
        return f"raw={len(body)}B tvl_points=0 currentChainTvls={len(d.get('currentChainTvls') or {})}"
    ts = [int(x["date"]) for x in tv]
    f = dt.datetime.fromtimestamp(min(ts), dt.timezone.utc).date().isoformat()
    la = dt.datetime.fromtimestamp(max(ts), dt.timezone.utc)
    age_h = int((dt.datetime.now(dt.timezone.utc) - la).total_seconds() // 3600)
    return f"raw={len(body)}B tvl_points={len(ts)} first={f} last={la.isoformat(timespec='minutes')} last_age_h={age_h} asc={ts == sorted(ts)}"


def g_defillama_rwa():
    # 1) the one big list, exactly as the collector will ask (its User-Agent, gzip): expect 200, ~2.3 MB gz, ~9 MB json
    probe("defillama-rwa", "protocols_gzip_collectorUA", LL_API + "/protocols", headers=LL_UA_COLLECTOR, extra_fn=_ll_protocols)
    time.sleep(0.5)
    # 2) the same list with the default probe UA and gzip (UA-based blocking check; sizes must match)
    probe("defillama-rwa", "protocols_gzip_plainUA", LL_API + "/protocols", headers={"Accept-Encoding": "gzip"},
          extra_fn=lambda raw: f"raw={len(_ll_body(raw))}B")
    # 3) current value of products hidden from /protocols (tvl null there): expect 5x number>0 and 1x empty body
    for s in LL_HIDDEN:
        time.sleep(0.3)
        probe("defillama-rwa", f"tvl_{s[:26]}", f"{LL_API}/tvl/{s}", headers=LL_UA_COLLECTOR, extra_fn=_ll_tvl)
    # 4) history: a listed product (expect ~860 daily points up to today) vs a hidden one (expect 0 points)
    for s in ("invesco-ustb", "blackrock-buidl"):
        time.sleep(0.3)
        probe("defillama-rwa", f"protocol_hist_{s}", f"{LL_API}/protocol/{s}", headers=LL_UA_COLLECTOR, extra_fn=_ll_hist)
    # 5) the dedicated RWA endpoints are Pro-only (x-api-plan-only): expect 404 on the free host; /rwa/stats = legacy small map
    time.sleep(0.3)
    probe("defillama-rwa", "rwa_current_free_expect404", LL_API + "/rwa/current", headers=LL_UA_COLLECTOR)
    time.sleep(0.3)
    probe("defillama-rwa", "rwa_stats_free_legacy", LL_API + "/rwa/stats", headers=LL_UA_COLLECTOR,
          extra_fn=lambda raw: (lambda o: f"dict n={len(o)}" if isinstance(o, dict) else shape(_ll_body(raw)))(json.loads(_ll_body(raw))))
    # total: 2 + 6 + 2 + 2 = 12 requests (~5 MB compressed, most of it the two /protocols lists)

# GROUPS = [..., g_evds, g_defillama_rwa]
'''
exec(compile(KOD_RWA, "sondy_v128/rwa", "exec"), S.__dict__)
GRUPY.append(("rwa", S.__dict__["g_defillama_rwa"]))

# ==================================================================================================== ici
KOD_ICI = r'''# ---- v128 ICI: snippet for narzedzia/sondy.py (paste after g_evds, add g_ici to GROUPS) ----------------------------------------
# Keyless. Prints only: HTTP status, ms, bytes, OLE2 magic yes/no, count of US dates found in the file bytes, first/last date,
# Wednesdays among them, and the year alias result. Never a URL, header value or body.
import re as _ici_re

ICI_B = "https://www.ici.org/"
ICI_UA = "CapitalFlowAI-collector/1.0"      # a "Mozilla/..." UA WITHOUT sec-ch-ua/Sec-Fetch headers is refused by the CDN (tested 27.09)
ICI_OK_HDR = {"User-Agent": ICI_UA, "Accept": "application/vnd.ms-excel, */*", "Accept-Language": "en-US,en;q=0.9",
              "Accept-Encoding": "identity"}
_ICI_DATE = _ici_re.compile(rb"(?<![0-9/])(\d{1,2})/(\d{1,2})/(20\d\d)(?![0-9/])")


def _ici_shape(raw):
    """OLE2 magic + the US dates stored as 8-bit strings in the shared-string table (the files keep dates as text)."""
    ole = raw[:8] == bytes.fromhex("d0cf11e0a1b11ae1")
    ds = set()
    for m, d, y in _ICI_DATE.findall(raw):
        try:
            ds.add(dt.date(int(y), int(m), int(d)))
        except ValueError:
            pass
    wed = sorted(x for x in ds if x.weekday() == 2)
    return (f"ole2={ole} dates={len(ds)} first={min(ds).isoformat() if ds else '-'} last={max(ds).isoformat() if ds else '-'} "
            f"wed={len(wed)} last_wed={wed[-1].isoformat() if wed else '-'}")


def g_ici():
    y = _utc_today().year
    lt, mm = f"{ICI_B}combined_flows_data_{y}.xls", f"{ICI_B}mm_summary_data_{y}.xls"
    # A: control - sondy's default headers (Mozilla-style UA, Accept json) - expect 403 "Access Denied" from the CDN, as locally
    probe("ici", "lt_default_hdr_403?", lt)
    time.sleep(0.5)
    # B: the planned request (expect 200, ole2=True, weekly Wednesdays: last_wed = Wednesday 7 days before the latest Wednesday release)
    probe("ici", "lt_recipe", lt, headers=ICI_OK_HDR, extra_fn=_ici_shape)
    time.sleep(0.5)
    # C: money market file (expect 200, ole2=True, 20 Wednesdays + 1 release date, last_wed = latest Wednesday after Thursday release)
    probe("ici", "mm_recipe", mm, headers=ICI_OK_HDR, extra_fn=_ici_shape)
    time.sleep(0.5)
    # D: conditional GET the collector will use between releases (expect 304, 0 B)
    import email.utils as _eu
    probe("ici", "mm_if_modified_since_now_304?", mm, headers={**ICI_OK_HDR, "If-Modified-Since": _eu.formatdate(time.time(), usegmt=True)})
    time.sleep(0.5)
    # E: previous-year name (fallback in January) - locally 27.09 it served the same current file (expect 200 + same last_wed as B)
    probe("ici", "lt_prev_year_alias", f"{ICI_B}combined_flows_data_{y - 1}.xls", headers=ICI_OK_HDR, extra_fn=_ici_shape)
    time.sleep(0.5)
    # F: browser-like variant (only matters if B is refused from the runner): Chrome UA + client hints + Sec-Fetch (expect 200 locally)
    ch = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
    probe("ici", "lt_browserlike", lt, headers={"User-Agent": ch, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
          "Accept-Language": "en-US,en;q=0.9", "sec-ch-ua": '"Chromium";v="129", "Not=A?Brand";v="8"', "sec-ch-ua-mobile": "?0",
          "sec-ch-ua-platform": '"Linux"', "Sec-Fetch-Dest": "document", "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Site": "none",
          "Sec-Fetch-User": "?1", "Upgrade-Insecure-Requests": "1"}, extra_fn=_ici_shape)

# GROUPS = [..., g_banxico, g_evds, g_ici]
'''
exec(compile(KOD_ICI, "sondy_v128/ici", "exec"), S.__dict__)
GRUPY.append(("ici", S.__dict__["g_ici"]))

# ==================================================================================================== jpx
KOD_JPX = r'''# --- paste into narzedzia/sondy.py (v128, label "jpx") before GROUPS; then append g_jpx to GROUPS -------------------------
# and add 'jpx' to the provider tuple of the annotation one-liner in .github/workflows/sondy.yml
# (…l.split('|')[0].strip() in ('coinalyze','banxico','evds','jpx')…). No key, no secret, read-only GETs (8 requests, ~0.6 MB).
# JPX "Trading by Type of Investors" (equities, weekly; www.jpx.co.jp = Amazon CloudFront + S3). Prints only: HTTP status, ms,
# bytes, counts, file-name patterns, public week DATES, magic bytes, booleans and ONE order of magnitude (maxexp: decides yen vs
# thousand yen in the new xlsx) — never a page, a file or a trading value.
JPX_B = 'https://www.jpx.co.jp'
JPX_EN = JPX_B + '/english/markets/statistics-equities/investor-type/'
JPX_JA = JPX_B + '/markets/statistics-equities/investor-type/'
JPX_SAMPLE = JPX_JA + 'tvdivq00000014fy-att/stock_1_w_YYYYMMDD_YYYYMMDD.xlsx'     # format sample published 28.07.2026 (JP page only)
_JPX = {'new': [], 'old': [], 'arch': {}}


def _jpx_links(raw):
    """Listing / archive page -> counts of data files by format, newest week by file name, archive years (no page text printed)."""
    import re
    s = raw.decode('utf-8', 'replace')
    old = sorted(set(re.findall(r'href="(/[^"]*/stock_val_1_(\d{6})\.xls)"', s)), key=lambda x: x[1])
    vol = len(set(re.findall(r'href="/[^"]*/stock_vol_1_\d{6}\.xls"', s)))
    new = sorted(set(re.findall(r'href="(/[^"]*/stock_1_w_(\d{8})_(\d{8})\.xlsx)"', s)), key=lambda x: x[2])
    arch = dict((y, u) for u, y in re.findall(r'<option[^>]*value="([^"]*00-00-archives-\d{2}\.html)"[^>]*>\s*(\d{4})\s*<', s))
    _JPX['new'] = _JPX['new'] or new; _JPX['old'] = _JPX['old'] or old; _JPX['arch'] = _JPX['arch'] or arch
    upd = re.search(r'Update\s*:\s*([A-Z][a-z]{2}\.?\s*\d{1,2},\s*\d{4})', s)
    return (f"old_xls={len(old)}({old[0][1] if old else '-'}..{old[-1][1] if old else '-'}) vol_xls={vol} "
            f"new_xlsx={len(new)}({new[-1][1] + '-' + new[-1][2] if new else '-'}) arch_years={len(arch)}"
            f"({min(arch) if arch else '-'}..{max(arch) if arch else '-'}) update={upd.group(1) if upd else '-'} "
            f"notice={'stock_1_w_YYYYMMDD_YYYYMMDD' in s}")


def _jpx_file(raw):
    """Data file: magic + minimal structure. xlsx: sheets, markers, numeric cell count, order of magnitude of the largest number."""
    import io
    import re
    if raw[:8] == b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1':
        return (f"ole2 tokyo_nagoya={'Tokyo & Nagoya'.encode('utf-16-le') in raw or b'Tokyo & Nagoya' in raw} "
                f"foreigners={'Foreigners'.encode('utf-16-le') in raw or b'Foreigners' in raw}")
    if raw[:4] != b'PK\x03\x04':
        return f"unknown_magic html={raw[:200].lstrip().lower().startswith(b'<')}"
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()
    wb = z.read('xl/workbook.xml').decode('utf-8', 'replace') if 'xl/workbook.xml' in names else ''
    ss = z.read('xl/sharedStrings.xml').decode('utf-8', 'replace') if 'xl/sharedStrings.xml' in names else ''
    sh = [n for n in names if n.startswith('xl/worksheets/sheet')]
    nums = []
    for n in sh:
        for attrs, v in re.findall(r'<c ([^>]*)>\s*<v>([^<]*)</v>', z.read(n).decode('utf-8', 'replace')):
            if not re.search(r'\bt="(s|str|b|e|inlineStr)"', attrs):
                try:
                    nums.append(abs(float(v)))
                except ValueError:
                    pass
    mx = max(nums) if nums else 0
    return (f"zip parts={len(names)} sheets={wb.count('<sheet ')} tokyo_nagoya={'Tokyo &amp; Nagoya' in ss} "
            f"foreigners={'Foreigners' in ss} value_row={'Value' in ss} numeric_cells={len(nums)} "
            f"maxexp={len(str(int(mx))) - 1 if mx >= 1 else '-'} unzipped={sum(i.file_size for i in z.infolist())}")


def g_jpx():
    import email.utils
    # 1-2: listings (English = primary, Japanese = fallback + format notice); same files, same bytes on both (md5 checked 27.09)
    probe('jpx', 'listing_en', JPX_EN + 'index.html', extra_fn=_jpx_links)
    time.sleep(1.0)
    probe('jpx', 'listing_ja', JPX_JA + 'index.html', extra_fn=_jpx_links)
    time.sleep(1.0)
    # 3: conditional GET (collector polls with If-Modified-Since = stored Last-Modified): expect HTTP 304 with 0 bytes
    st, raw, ms, err = http(JPX_EN + 'index.html', headers={'If-Modified-Since': email.utils.formatdate(usegmt=True)})
    report('jpx', None, 'listing_en_if_modified_since_now', st, raw, ms, err, 'expect 304')
    time.sleep(1.0)
    # 4: newest data file — new format when present (from the 29.09.2026 06:30 UTC release), else the newest old .xls
    new, old = _JPX['new'], _JPX['old']
    if new:
        probe('jpx', f'newest_xlsx_{new[-1][1]}_{new[-1][2]}', JPX_B + new[-1][0], extra_fn=_jpx_file)
    elif old:
        probe('jpx', f'newest_xls_{old[-1][1]}', JPX_B + old[-1][0], extra_fn=_jpx_file)
    else:
        skipped('jpx', 'newest data file', 'no data link found on listing')
    time.sleep(1.0)
    # 5-6: archives — current year (00) and the oldest listed year (history depth); the year->page map is read from <option>
    arch = _JPX['arch']
    for y in sorted(arch)[-1:] + sorted(arch)[:1]:
        u = arch[y] if arch[y].startswith('http') else JPX_B + arch[y]
        probe('jpx', f'archive_{y}', u, extra_fn=_jpx_links)
        time.sleep(1.0)
    if not arch:
        skipped('jpx', 'archives', 'no <option> archive list')
    # 7: format sample (fixed URL; proves xlsx fetch + zip from the runner even before the first real new file exists)
    probe('jpx', 'format_sample_xlsx', JPX_SAMPLE, extra_fn=_jpx_file)
    time.sleep(1.0)
    # 8: revision log (checked once a day by the collector via If-Modified-Since)
    probe('jpx', 'revision_information_e', JPX_EN + 'tvdivq00000014fy-att/revision_information_e.xls', extra_fn=_jpx_file)


# GROUPS = [..., g_banxico, g_evds, g_jpx]
'''
exec(compile(KOD_JPX, "sondy_v128/jpx", "exec"), S.__dict__)
GRUPY.append(("jpx", S.__dict__["g_jpx"]))

# ==================================================================================================== dolar
KOD_DOLAR = r'''# Snippet for narzedzia/sondy.py (v128, label "dolar"). Keyless: DolarApi (Argentina, Venezuela, Bolivia), its GitHub data mirror,
# ArgentinaDatos (history), BCRA (official wholesale rate, cross-check only) and, optionally, the B3 daily bulletin (BDI).
# Paste (1) after g_evds, add g_dolar to GROUPS (2) and the provider names to the annotation filter in .github/workflows/sondy.yml (3).
# Prints only: HTTP status, ms, bytes, item counts, which fixed ids/field names are present, ISO dates of updates (public calendar
# dates / update stamps) and booleans of sanity checks. Never a rate value, a URL, a response header or a body.
# Expected from a US runner (local check 27.09.2026, Germany): every probe HTTP 200 except "ar_dolares_pythonUA_exp403" = 403
# (Cloudflare "error code: 1010" bans the default Python-urllib user agent; the collector sends its own UA and passes).

# (1) the group
DOLAR_UA = {"User-Agent": "CapitalFlowAI-collector/1.0"}      # exactly what zbieraj_dane.get()/get_json() send
DOLAR_AR_CASAS = ("oficial", "blue", "bolsa", "contadoconliqui", "mayorista", "cripto", "tarjeta")


def _dl_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def _dl_ar(raw):
    """Argentina /v1/dolares or /v1/ambito/dolares: casas present, how many have a positive 'venta', whether every ratio to the
    wholesale rate is sane (0.5..4.0; tarjeta excluded: a tax construct), first/last update stamp, field names."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    it = [x for x in obj if isinstance(x, dict)]
    casas = {str(x.get("casa")) for x in it}
    ok = sum(1 for x in it if _dl_num(x.get("venta")))
    ts = sorted(str(x.get("fechaActualizacion"))[:16] for x in it if x.get("fechaActualizacion"))
    base = next((x.get("venta") for x in it if x.get("casa") == "mayorista"), None)
    sane = _dl_num(base) and all(0.5 <= x["venta"] / base <= 4.0 for x in it
                                 if _dl_num(x.get("venta")) and x.get("casa") != "tarjeta")
    cmp_ok = all(not _dl_num(x.get("compra")) or x["compra"] <= x["venta"] * 1.02 for x in it if _dl_num(x.get("venta")))
    keys = sorted({str(k) for x in it for k in x})
    return (f"list n={len(it)} venta_ok={ok} missing={sorted(set(DOLAR_AR_CASAS) - casas) or '-'} "
            f"new={sorted(casas - set(DOLAR_AR_CASAS)) or '-'} ratio_sane={bool(sane)} compra_le_venta={cmp_ok} "
            f"t_min={ts[0] if ts else '-'} t_max={ts[-1] if ts else '-'} keys=[{','.join(keys)[:90]}]")


def _dl_ve(raw):
    """Venezuela /v1/dolares: fuentes present, 'promedio' positive, paralelo/oficial ratio sane (0.5..5.0), both update stamps."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    it = {str(x.get("fuente")): x for x in obj if isinstance(x, dict)}
    of, pa = it.get("oficial") or {}, it.get("paralelo") or {}
    sane = _dl_num(of.get("promedio")) and _dl_num(pa.get("promedio")) and 0.5 <= pa["promedio"] / of["promedio"] <= 5.0
    return (f"list n={len(obj)} fuentes={sorted(it)} promedio_ok={sum(1 for x in it.values() if _dl_num(x.get('promedio')))} "
            f"ratio_sane={bool(sane)} t_oficial={str(of.get('fechaActualizacion'))[:25]} t_paralelo={str(pa.get('fechaActualizacion'))[:16]}")


def _dl_bo(raw):
    """Bolivia /v1/dolares: casas present, 'venta' positive, binance/oficial ratio sane (0.5..5.0), both update stamps."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    it = {str(x.get("casa")): x for x in obj if isinstance(x, dict)}
    of, bn = it.get("oficial") or {}, it.get("binance") or {}
    sane = _dl_num(of.get("venta")) and _dl_num(bn.get("venta")) and 0.5 <= bn["venta"] / of["venta"] <= 5.0
    return (f"list n={len(obj)} casas={sorted(it)} venta_ok={sum(1 for x in it.values() if _dl_num(x.get('venta')))} "
            f"ratio_sane={bool(sane)} t_oficial={str(of.get('fechaActualizacion'))[:16]} t_binance={str(bn.get('fechaActualizacion'))[:16]}")


def _dl_hist(raw):
    """History list (DolarApi Venezuela, ArgentinaDatos): rows with a positive number, first/last date, rows dated after today (UTC),
    duplicate dates."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    ds = sorted(str(x.get("fecha")) for x in obj if isinstance(x, dict) and (_dl_num(x.get("promedio")) or _dl_num(x.get("venta"))))
    today = _utc_today().isoformat()
    return (f"list n={len(obj)} num={len(ds)} first={ds[0] if ds else '-'} last={ds[-1] if ds else '-'} "
            f"future_dated={sum(1 for d in ds if d > today)} dup={len(ds) - len(set(ds))}")


def _dl_bcra(raw):
    """BCRA Estadísticas Cambiarias v1.0 /Cotizaciones/USD: result days with a positive rate, last date, status."""
    obj = json.loads(raw)
    r = obj.get("results") if isinstance(obj, dict) else None
    if not isinstance(r, list):
        return shape(raw)
    ds = sorted(str(x.get("fecha")) for x in r if isinstance(x, dict)
                and any(isinstance(y, dict) and _dl_num(y.get("tipoCotizacion")) for y in (x.get("detalle") or [])))
    return f"results={len(r)} num={len(ds)} last={ds[-1] if ds else '-'} status={obj.get('status')}"


def _dl_b3(raw):
    """B3 BDI table SharesInvesVolum (month-to-date buys/sells by investor type): rows, column names, whether the foreign-investor row
    exists with numbers, the 'data through' date from the table text, status, last update date."""
    import re
    j = json.loads(raw)
    t = (j or {}).get("table") or {}
    v = t.get("values") if isinstance(t.get("values"), list) else []
    cols = [str(c.get("name")) for c in (t.get("columns") or []) if isinstance(c, dict)]
    fx = [r for r in v if isinstance(r, list) and r and r[0] == "Investidor Estrangeiro"]
    txt = " ".join(str(x.get("textPt") or "") for x in (t.get("texts") or []) if isinstance(x, dict))
    m = re.search(r"até o dia (\d{2})/(\d{2})/(\d{4})", txt)
    num = bool(fx) and len(fx[0]) > 3 and all(isinstance(fx[0][i], (int, float)) for i in (1, 3))
    return (f"rows={len(v)} cols=[{','.join(cols)}] foreign_row={bool(fx)} foreign_numeric={num} "
            f"data_through={m.group(3) + '-' + m.group(2) + '-' + m.group(1) if m else '-'} status={j.get('status')} "
            f"upd={str(j.get('lastUpdateDate'))[:10]}")


def g_dolar():
    ar = "https://dolarapi.com/v1/dolares"
    # A: what the collector will ask every hour (its own UA), then the same with sondy's UA and with the default Python UA
    probe("dolarapi", "ar_dolares_collectorUA", ar, headers=DOLAR_UA, extra_fn=_dl_ar)
    time.sleep(0.3)
    probe("dolarapi", "ar_dolares_sondyUA", ar, extra_fn=_dl_ar)
    time.sleep(0.3)
    probe("dolarapi", "ar_dolares_pythonUA_exp403", ar, headers={"User-Agent": "Python-urllib/3.12"})
    time.sleep(0.3)
    # B: second reading of the same Argentine rates (Ámbito via DolarApi) — used only by the daily check (kontrola)
    probe("dolarapi", "ar_ambito_collectorUA", "https://dolarapi.com/v1/ambito/dolares", headers=DOLAR_UA, extra_fn=_dl_ar)
    time.sleep(0.3)
    probe("dolarapi", "ve_dolares", "https://ve.dolarapi.com/v1/dolares", headers=DOLAR_UA, extra_fn=_dl_ve)
    time.sleep(0.3)
    probe("dolarapi", "bo_dolares", "https://bo.dolarapi.com/v1/dolares", headers=DOLAR_UA, extra_fn=_dl_bo)
    for f in ("oficial", "paralelo"):
        time.sleep(0.3)
        probe("dolarapi", f"ve_hist_{f}", f"https://ve.dolarapi.com/v1/historicos/dolares/{f}", headers=DOLAR_UA, extra_fn=_dl_hist)
    # C: fallback — the same files in the project's public GitHub repository (MIT), byte-identical to the API on 27.09
    probe("dolarapi-gh", "raw_ar_dolares", "https://raw.githubusercontent.com/enzonotario/dolarapi.com/main/datos/v1/dolares/index.json",
          headers=DOLAR_UA, extra_fn=_dl_ar)
    # D: history for Argentina (one full series ~0.54 MB; the collector needs it only on the first run) and one single-day row
    probe("argdatos", "hist_contadoconliqui", "https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui",
          headers=DOLAR_UA, extra_fn=_dl_hist)
    d = _utc_today() - dt.timedelta(days=2)
    probe("argdatos", "day_blue_D-2", f"https://api.argentinadatos.com/v1/cotizaciones/dolares/blue/{d:%Y/%m/%d}", headers=DOLAR_UA)
    # E: official wholesale rate (BCRA API, keyless) — cross-check only
    a, b = _utc_today() - dt.timedelta(days=10), _utc_today()
    probe("bcra", "cotizaciones_USD_10d",
          f"https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD?fechadesde={a.isoformat()}&fechahasta={b.isoformat()}",
          headers=DOLAR_UA, extra_fn=_dl_bcra)
    # F (optional, not for publication without B3's written permission): B3 daily bulletin, investor participation (POST with {})
    wd = _last_weekday(1).isoformat()
    probe("b3-bdi", "SharesInvesVolum_last_wd", f"https://arquivos.b3.com.br/bdi/table/SharesInvesVolum/{wd}/{wd}/1/100",
          method="POST", body={}, headers=DOLAR_UA, extra_fn=_dl_b3)
    # dadosdemercado.com.br is NOT probed: its FAQ asks not to scrape the site; locally 27.09 it answered 403 (CloudFront) to any
    # non-browser UA and its API needs a paid token (401 "Missing token").


# (2) GROUPS = [..., g_banxico, g_evds, g_dolar]
# (3) .github/workflows/sondy.yml, annotation filter tuple: add 'dolarapi','dolarapi-gh','argdatos','bcra','b3-bdi'
#     (13 lines of ~190 B = ~2.5 KB; the annotation is capped at 3900 characters — if other v128 groups are added in the same run,
#     keep only the summary lines of the others or split the filter per label).
'''
exec(compile(KOD_DOLAR, "sondy_v128/dolar", "exec"), S.__dict__)
GRUPY.append(("dolar", S.__dict__["g_dolar"]))


def main():
    for k, g in GRUPY:
        try:
            g()
        except Exception as e:  # noqa
            print(f"{k:<15}| grupa przerwana: {type(e).__name__}", flush=True)
    stat = {}
    for prov, st, _ in S._results:
        a = stat.setdefault(prov, [0, 0]); a[1] += 1; a[0] += int(st == 200)
    for prov in sorted(stat):
        print(f"summary {prov:<15} http200 {stat[prov][0]}/{stat[prov][1]}", flush=True)


if __name__ == "__main__":
    main()
