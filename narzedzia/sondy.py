#!/usr/bin/env python3
"""sondy.py - reachability probes for candidate data sources (stdlib only, Python 3.12).

Intended to run once inside GitHub Actions (ubuntu-latest, US/Azure egress) to check
which endpoints answer from a US runner IP, before any of them is added to
zbieraj_dane.py.

SAFETY RULES (enforced by the code below):
  * Keys are read ONLY from environment variables (several candidate names per provider).
  * For every probe the script prints ONLY: provider, the NAME of the env var that was
    found (or "-"), HTTP status, elapsed ms, byte length, and the top-level JSON keys or
    an item count. It never prints key values, URLs (keyed or not), response headers or
    response bodies. Exception messages are reduced to the exception class name.
  * Every request has a timeout <= 20 s; a global deadline keeps the whole run < 2 min.
  * The process always exits with code 0.
  * SONDY_NO_KEYS=1 disables all keyed probes (public probes only).

Usage:  python3 sondy.py
"""
import concurrent.futures as cf
import datetime as dt
import io
import json
import os
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile

T0 = time.monotonic()
DEADLINE = T0 + 105.0          # hard stop for starting/reading requests (seconds)
REQ_TIMEOUT = 20.0             # per-request timeout cap (seconds)
MAX_BYTES = 6_000_000          # never read more than this per response
UA = "Mozilla/5.0 (compatible; CapitalFlowAI-sondy/1.0; +https://github.com)"

_print_lock = threading.Lock()
_results = []                  # (provider, status) for the summary
_secret_values = []            # key values, used only to scrub text before printing

# --------------------------------------------------------------------------- keys

KEY_CANDIDATES = {
    "etherscan":    ["ETHERSCAN_KEY", "ETHERSCAN_API_KEY", "ETHERSCAN_TOKEN"],
    "cryptopanic":  ["CRYPTOPANIC_KEY", "CRYPTOPANIC_TOKEN", "CRYPTOPANIC_API_KEY", "CRYPTOPANIC_AUTH_TOKEN"],
    "tiingo":       ["TIINGO_KEY", "TIINGO_API_KEY", "TIINGO_TOKEN"],
    "massive":      ["POLYGON_KEY", "MASSIVE_KEY", "POLYGON_API_KEY", "MASSIVE_API_KEY"],
    "eodhd":        ["EODHD_KEY", "EODHD_API_KEY", "EOD_KEY", "EODHD_TOKEN"],
    "fmp":          ["FMP_KEY", "FMP_API_KEY", "FINANCIALMODELINGPREP_KEY", "FINANCIALMODELINGPREP_API_KEY"],
    "alphavantage": ["ALPHAVANTAGE_KEY", "ALPHA_VANTAGE_KEY", "ALPHAVANTAGE_API_KEY", "ALPHA_VANTAGE_API_KEY"],
}


def find_key(provider):
    """Return (env_var_name, value) or (None, None). The value is never printed."""
    if os.environ.get("SONDY_NO_KEYS", "").strip() == "1":
        return None, None
    for name in KEY_CANDIDATES.get(provider, []):
        val = os.environ.get(name, "").strip()
        if val:
            if val not in _secret_values:
                _secret_values.append(val)
            return name, val
    return None, None


# --------------------------------------------------------------------------- http

def _ssl_context():
    ctx = ssl.create_default_context()
    # Some local Python builds (e.g. python.org on macOS) ship without a CA store.
    # On ubuntu-latest the default store is used; this fallback only matters locally.
    paths = ssl.get_default_verify_paths()
    if not os.environ.get("SSL_CERT_FILE") and not (paths.cafile and os.path.exists(paths.cafile)):
        for cand in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
            if os.path.exists(cand):
                try:
                    ctx.load_verify_locations(cafile=cand)
                except Exception:
                    pass
                break
    return ctx


SSL_CTX = _ssl_context()


def _remaining():
    return DEADLINE - time.monotonic()


def http(url, method="GET", body=None, headers=None):
    """Return (status or None, bytes or None, elapsed_ms, error_class_name or None)."""
    left = _remaining()
    if left < 2.0:
        return None, None, 0, "SkippedDeadline"
    timeout = min(REQ_TIMEOUT, left)
    h = {"User-Agent": UA, "Accept": "application/json, */*"}
    if headers:
        h.update(headers)
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    t = time.monotonic()
    status, raw, err = None, None, None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            status = r.status
            raw = _read_capped(r, t + timeout)
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            raw = _read_capped(e, t + timeout)
        except Exception:
            raw = b""
    except Exception as e:  # URLError, timeout, SSL, DNS ...
        reason = getattr(e, "reason", None)
        err = type(e).__name__ + ("/" + type(reason).__name__ if reason is not None and not isinstance(reason, str) else "")
    return status, raw, int((time.monotonic() - t) * 1000), err


def _read_capped(resp, until):
    buf = bytearray()
    while len(buf) < MAX_BYTES:
        if time.monotonic() > until or _remaining() < 0.5:
            break
        chunk = resp.read(65536)
        if not chunk:
            break
        buf.extend(chunk)
    return bytes(buf)


# --------------------------------------------------------------------------- output

LIST_FIELDS = ("result", "data", "results", "list", "items", "markets", "ticker")


def shape(raw):
    """Top-level JSON keys (max 12) and an item count; never the values themselves."""
    if raw is None:
        return "-"
    try:
        obj = json.loads(raw)
    except Exception:
        return "non-json"
    if isinstance(obj, list):
        return f"list n={len(obj)}"
    if isinstance(obj, dict):
        keys = list(obj.keys())
        out = "keys=[" + ",".join(str(k)[:24] for k in keys[:12]) + (",..." if len(keys) > 12 else "") + "]"
        n = _count(obj)
        return out + (f" n={n}" if n is not None else "")
    return type(obj).__name__


def _count(obj, depth=0):
    for f in LIST_FIELDS:
        v = obj.get(f)
        if isinstance(v, list):
            return len(v)
        if isinstance(v, dict) and depth == 0:
            n = _count(v, 1)
            if n is not None:
                return n
    return None


def _scrub(text):
    for s in _secret_values:
        if s:
            text = text.replace(s, "***")
    return text


def report(provider, env_name, label, status, raw, ms, err, extra=None):
    blen = len(raw) if raw is not None else 0
    st = str(status) if status is not None else "ERR"
    info = extra if extra is not None else (shape(raw) if raw is not None else "-")
    if err:
        info = f"{err} {info}".strip()
    line = f"{provider:<15}| env={env_name or '-':<26}| {label:<34}| HTTP {st:<4}| {ms:>6} ms | {blen:>9} B | {info}"
    with _print_lock:
        print(_scrub(line), flush=True)
        _results.append((provider, status, env_name is not None))


def probe(provider, label, url, env_name=None, method="GET", body=None, headers=None, extra_fn=None):
    status, raw, ms, err = http(url, method, body, headers)
    extra = None
    if extra_fn is not None and raw is not None and status == 200:
        try:
            extra = extra_fn(raw)
        except Exception as e:
            extra = type(e).__name__
    report(provider, env_name, label, status, raw, ms, err, extra)
    return status, raw


def skipped(provider, label, why="no key in env"):
    with _print_lock:
        print(f"{provider:<15}| env={'-':<26}| {label:<34}| SKIP      |        |           | {why}", flush=True)


# --------------------------------------------------------------------------- dates

def _utc_today():
    return dt.datetime.now(dt.timezone.utc).date()


def _last_weekday(offset_days=1):
    d = _utc_today() - dt.timedelta(days=offset_days)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


def _ms(d):
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)


# --------------------------------------------------------------------------- public groups

def g_deribit():
    base = "https://www.deribit.com/api/v2/public/"
    end = int(time.time() * 1000)
    start = end - 4 * 86400 * 1000
    for cur in ("BTC", "ETH"):
        probe("deribit", f"dvol_{cur.lower()}_1d", f"{base}get_volatility_index_data?currency={cur}&start_timestamp={start}&end_timestamp={end}&resolution=1D")
        time.sleep(0.2)
    for cur in ("BTC", "ETH"):
        probe("deribit", f"book_summary_option_{cur.lower()}", f"{base}get_book_summary_by_currency?currency={cur}&kind=option")
        time.sleep(0.2)
    probe("deribit", "funding_rate_value_btc_perp", f"{base}get_funding_rate_value?instrument_name=BTC-PERPETUAL&start_timestamp={end - 86400000}&end_timestamp={end}")


def g_binance_fapi():
    b = "https://fapi.binance.com"
    probe("binance-fapi", "premiumIndex_BTCUSDT", f"{b}/fapi/v1/premiumIndex?symbol=BTCUSDT")
    probe("binance-fapi", "openInterest_BTCUSDT", f"{b}/fapi/v1/openInterest?symbol=BTCUSDT")
    probe("binance-fapi", "globalLongShortAccountRatio_1d", f"{b}/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1d&limit=2")
    probe("binance-fapi", "openInterestHist_ETHUSDT_1d", f"{b}/futures/data/openInterestHist?symbol=ETHUSDT&period=1d&limit=2")


def _zip_rows(raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()
    rows = sum(max(0, len(z.read(n).splitlines()) - 1) for n in names)
    return f"zip files={len(names)} csv_rows={rows}"


def g_binance_mirrors():
    probe("binance-vision", "data-api_spot_ticker24h_BTCUSDT", "https://data-api.binance.vision/api/v3/ticker/24hr?symbol=BTCUSDT")
    # Daily bulk file with OI + long/short ratios (5-min rows). Published the next day.
    for back in (1, 2):
        d = (_utc_today() - dt.timedelta(days=back)).isoformat()
        url = f"https://data.binance.vision/data/futures/um/daily/metrics/BTCUSDT/BTCUSDT-metrics-{d}.zip"
        st, _ = probe("binance-vision", f"bulk_metrics_BTCUSDT_D-{back}", url, extra_fn=_zip_rows)
        if st == 200:
            break


def g_bybit():
    for host in ("api.bybit.com", "api.bytick.com"):
        probe("bybit", f"{host.split('.')[1]}_tickers_linear_BTC", f"https://{host}/v5/market/tickers?category=linear&symbol=BTCUSDT")
        time.sleep(0.2)
    probe("bybit", "account-ratio_BTC_1d", "https://api.bybit.com/v5/market/account-ratio?category=linear&symbol=BTCUSDT&period=1d&limit=2")
    probe("bybit", "open-interest_BTC_1d", "https://api.bybit.com/v5/market/open-interest?category=linear&symbol=BTCUSDT&intervalTime=1d&limit=2")


def g_okx():
    for host in ("www.okx.com", "openapi.okx.com", "us.okx.com"):
        probe("okx", f"{host.split('.')[0]}_funding-rate_BTC-SWAP", f"https://{host}/api/v5/public/funding-rate?instId=BTC-USDT-SWAP")
        time.sleep(0.3)
    probe("okx", "open-interest_BTC-SWAP", "https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP")
    time.sleep(0.3)
    probe("okx", "rubik_long-short-account-ratio", "https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1D")
    time.sleep(0.5)
    probe("okx", "rubik_option_oi-volume-ratio", "https://www.okx.com/api/v5/rubik/stat/option/open-interest-volume-ratio?ccy=BTC&period=1D")
    time.sleep(0.3)
    probe("okx", "opt-summary_BTC-USD", "https://www.okx.com/api/v5/public/opt-summary?instFamily=BTC-USD")


def g_hyperliquid():
    def _hl(raw):
        obj = json.loads(raw)
        if isinstance(obj, list) and len(obj) == 2 and isinstance(obj[0], dict):
            return f"list n=2 universe={len(obj[0].get('universe', []))} assetCtxs={len(obj[1])}"
        return shape(raw)
    probe("hyperliquid", "info_metaAndAssetCtxs", "https://api.hyperliquid.xyz/info", method="POST",
          body={"type": "metaAndAssetCtxs"}, extra_fn=_hl)


def g_alternatives():
    probe("coinbase-intx", "BTC-PERP_quote", "https://api.international.coinbase.com/api/v1/instruments/BTC-PERP/quote")
    probe("kraken-fut", "tickers_PF_XBTUSD", "https://futures.kraken.com/derivatives/api/v3/tickers/PF_XBTUSD")
    probe("dydx-indexer", "perpetualMarkets_BTC-USD", "https://indexer.dydx.trade/v4/perpetualMarkets?ticker=BTC-USD")


def g_onchain_public():
    usdt = "0xdac17f958d2ee523a2206206994597c13d831ec7"
    probe("blockscout", "eth_tokentx_USDT_compat", f"https://eth.blockscout.com/api?module=account&action=tokentx&contractaddress={usdt}&page=1&offset=5&sort=desc")
    st, raw = probe("publicnode", "eth_blockNumber", "https://ethereum-rpc.publicnode.com", method="POST",
                    body={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []})
    # v99: odczyt, jakiego potrzebują „wieloryby” — logi Transfer USDT do portfela giełdy (adres opublikowany przez Binance, 11.2022) z ok. 900 bloków
    try:
        head = int(json.loads(raw)["result"], 16) if st == 200 and raw else None
    except Exception:
        head = None
    if head:
        hot = "0x28c6c06298d514db089934071355e5743bf21d60"
        topic = "0x" + "0" * 24 + hot[2:]
        for host, lab in (("https://ethereum-rpc.publicnode.com", "publicnode"), ("https://eth.llamarpc.com", "llamarpc")):
            probe(lab, "eth_getLogs_USDT_to_exchange_900", host, method="POST",
                  body={"jsonrpc": "2.0", "id": 2, "method": "eth_getLogs", "params": [{"address": usdt, "fromBlock": hex(head - 900), "toBlock": hex(head),
                        "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef", None, topic]}]})
            probe(lab, "eth_getBalance_exchange", host, method="POST",
                  body={"jsonrpc": "2.0", "id": 3, "method": "eth_getBalance", "params": [hot, "latest"]})


# --------------------------------------------------------------------------- keyed groups

def g_etherscan():
    name, key = find_key("etherscan")
    if not key:
        skipped("etherscan", "tokentx/txlist/tokenbalance")
        return
    b = "https://api.etherscan.io/v2/api?chainid=1"
    usdt = "0xdac17f958d2ee523a2206206994597c13d831ec7"
    hot = "0x28c6c06298d514db089934071355e5743bf21d60"  # widely published Binance hot wallet ("Binance 14")
    calls = [
        ("tokentx_by_contract_USDT_desc", f"{b}&module=account&action=tokentx&contractaddress={usdt}&page=1&offset=100&sort=desc"),
        ("txlist_exchange_wallet_desc", f"{b}&module=account&action=txlist&address={hot}&page=1&offset=100&sort=desc"),
        ("tokentx_exchange_wallet_USDT", f"{b}&module=account&action=tokentx&contractaddress={usdt}&address={hot}&page=1&offset=100&sort=desc"),
        ("tokenbalance_USDT_exchange", f"{b}&module=account&action=tokenbalance&contractaddress={usdt}&address={hot}&tag=latest"),
    ]
    for label, url in calls:
        probe("etherscan", label, url + "&apikey=" + key, env_name=name)
        time.sleep(0.45)   # free tier: 3 calls/s


def g_cryptopanic():
    name, key = find_key("cryptopanic")
    if not key:
        skipped("cryptopanic", "posts v2")
        return
    for plan in ("developer", "growth"):
        probe("cryptopanic", f"{plan}_v2_posts_public", f"https://cryptopanic.com/api/{plan}/v2/posts/?auth_token={key}&public=true&currencies=BTC,ETH&kind=news", env_name=name)
        time.sleep(1.0)


def g_tiingo():
    name, key = find_key("tiingo")
    if not key:
        skipped("tiingo", "daily/iex")
        return
    hdr = {"Authorization": "Token " + key, "Content-Type": "application/json"}
    start = (_utc_today() - dt.timedelta(days=10)).isoformat()
    probe("tiingo", "daily_SPY_prices_10d", f"https://api.tiingo.com/tiingo/daily/SPY/prices?startDate={start}", env_name=name, headers=hdr)
    probe("tiingo", "daily_SPY_meta", "https://api.tiingo.com/tiingo/daily/SPY", env_name=name, headers=hdr)
    probe("tiingo", "iex_SPY", "https://api.tiingo.com/iex/?tickers=spy", env_name=name, headers=hdr)


def g_massive():
    name, key = find_key("massive")
    if not key:
        skipped("massive", "grouped daily / prev")
        return
    hdr = {"Authorization": "Bearer " + key}
    d = _last_weekday(1).isoformat()
    probe("massive", "grouped_daily_us_stocks", f"https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{d}?adjusted=true", env_name=name, headers=hdr)
    time.sleep(13)   # free plan: 5 calls/min
    probe("massive", "ticker_SPY_prev", "https://api.massive.com/v2/aggs/ticker/SPY/prev?adjusted=true", env_name=name, headers=hdr)


def g_eodhd():
    name, key = find_key("eodhd")
    if not key:
        skipped("eodhd", "eod ETF + INDX")
        return
    frm = (_utc_today() - dt.timedelta(days=10)).isoformat()
    # 26.09.2026: rotacja indeksów zgłosiła FTSE „pusta odpowiedź” i FTMIB HTTP 404 — sprawdzamy kody kandydatów (limit planu: 20 zapytań na dobę,
    # dlatego tylko trzy; SPY/GSPC/GDAXI już potwierdzone). Wynik: HTTP + liczba elementów listy, nigdy treść.
    for label, sym in (("eod_FTSE.INDX", "FTSE.INDX"), ("eod_UKX.INDX", "UKX.INDX"), ("eod_FTSEMIB.INDX", "FTSEMIB.INDX")):
        probe("eodhd", label, f"https://eodhd.com/api/eod/{sym}?fmt=json&from={frm}&api_token={key}", env_name=name)
        time.sleep(0.5)


def g_fmp():
    name, key = find_key("fmp")
    if not key:
        skipped("fmp", "stable quote/eod/etf")
        return
    b = "https://financialmodelingprep.com/stable"
    for label, path in (
        ("stable_quote_SPY", "/quote?symbol=SPY"),
        ("stable_eod_light_SPY", "/historical-price-eod/light?symbol=SPY"),
        ("stable_quote_^GDAXI", "/quote?symbol=%5EGDAXI"),
        ("stable_etf_sector-weightings_SPY", "/etf/sector-weightings?symbol=SPY"),
        ("stable_etf_holdings_SPY", "/etf/holdings?symbol=SPY"),
    ):
        probe("fmp", label, f"{b}{path}&apikey={key}", env_name=name)
        time.sleep(0.4)


def g_alphavantage():
    name, key = find_key("alphavantage")
    if not key:
        skipped("alphavantage", "daily/global quote")
        return
    b = "https://www.alphavantage.co/query?"
    probe("alphavantage", "TIME_SERIES_DAILY_SPY", f"{b}function=TIME_SERIES_DAILY&symbol=SPY&outputsize=compact&apikey={key}", env_name=name)
    time.sleep(2.0)
    probe("alphavantage", "GLOBAL_QUOTE_SPY", f"{b}function=GLOBAL_QUOTE&symbol=SPY&apikey={key}", env_name=name)


GROUPS = [g_deribit, g_binance_fapi, g_binance_mirrors, g_bybit, g_okx, g_hyperliquid,
          g_alternatives, g_onchain_public, g_etherscan, g_cryptopanic, g_tiingo,
          g_massive, g_eodhd, g_fmp, g_alphavantage]


# --------------------------------------------------------------------------- main

def main():
    print(f"sondy.py start {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} "
          f"python {sys.version.split()[0]} (no URLs, headers, bodies or key values are printed)", flush=True)
    print(f"{'provider':<15}| {'env var found':<30}| {'probe':<34}| status    | elapsed   | bytes       | shape", flush=True)
    ex = cf.ThreadPoolExecutor(max_workers=len(GROUPS))
    futs = {ex.submit(g): g.__name__ for g in GROUPS}
    try:
        for f in cf.as_completed(futs, timeout=max(1.0, DEADLINE + 8 - time.monotonic())):
            try:
                f.result()
            except Exception as e:
                with _print_lock:
                    print(f"{futs[f]:<15}| group error {type(e).__name__}", flush=True)
    except cf.TimeoutError:
        with _print_lock:
            print("global deadline reached; unfinished probes abandoned", flush=True)
    # summary: per provider, count of HTTP 200 vs total; flags 403/451 (typical geo/CDN blocks)
    with _print_lock:
        per = {}
        for prov, st, keyed in _results:
            ok, tot, geo = per.get(prov, (0, 0, 0))
            # 451 is always a legal/geo block; 403 counts as a likely geo/CDN block only on
            # keyless probes (with a key, 403 usually means a bad key or a plan limit).
            blocked = st == 451 or (st == 403 and not keyed)
            per[prov] = (ok + (st == 200), tot + 1, geo + blocked)
        print("-" * 100)
        print("note: etherscan and alphavantage report errors with HTTP 200; success shows n=<items>"
              " (etherscan) or a 'Time Series'/'Global Quote' key (alphavantage)")
        for prov in sorted(per):
            ok, tot, geo = per[prov]
            print(f"summary {prov:<15} http200 {ok}/{tot}" + (f"  (likely geo/CDN block on {geo})" if geo else ""))
        print(f"elapsed total {int((time.monotonic() - T0) * 1000)} ms", flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:  # never fail the workflow
        try:
            print(f"fatal {type(e).__name__} (ignored)", flush=True)
        except Exception:
            pass
    finally:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        os._exit(0)
