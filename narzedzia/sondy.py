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
  * Every request has a timeout <= 20 s; a global deadline keeps the whole run < 5 min (v294p: 240 s, earlier 105 s).
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
import urllib.parse
import urllib.request
import zipfile

T0 = time.monotonic()
DEADLINE = T0 + 240.0          # hard stop for starting/reading requests (seconds); v294p: 240 s (sonda surowców — paczki Twelve Data co 61 s; było 105 s)
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
    "banxico":      ["BANXICO_TOKEN"],          # v126 (27.09): Banco de México SIE, nagłówek Bmx-Token
    "evds":         ["EVDS_KEY"],               # v126 (27.09): TCMB EVDS3, nagłówek key
    "twelvedata":   ["TWELVEDATA_KEY"],         # v294p: sekrety pod tymi samymi nazwami co w strona.yml
    "eia":          ["EIA_KEY"],
    "coingecko":    ["COINGECKO_KEY"],          # plan Demo: nagłówek x-cg-demo-api-key
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
    for label, sym in (("eod_FTSEMIB.INDX", "FTSEMIB.INDX"),):   # FTSE.INDX i UKX.INDX: HTTP 200, pusta lista (26.09, sonda) — indeksy LSE poza planem
        probe("eodhd", label, f"https://eodhd.com/api/eod/{sym}?fmt=json&from={frm}&api_token={key}", env_name=name)
        time.sleep(0.5)


def g_fmp():
    name, key = find_key("fmp")
    if not key:
        skipped("fmp", "stable quote/eod/etf")
        return
    b = "https://financialmodelingprep.com/stable"
    # 26.09.2026: FTSE 100 i FTSE MIB poza planem EODHD — czy FMP (plan bezpłatny) daje ich dzienne zamknięcia? Tylko HTTP i liczba elementów.
    for label, path in (
        ("stable_eod_light_^FTSE", "/historical-price-eod/light?symbol=%5EFTSE"),
        ("stable_eod_light_FTSEMIB.MI", "/historical-price-eod/light?symbol=FTSEMIB.MI"),
        ("stable_eod_light_^GDAXI", "/historical-price-eod/light?symbol=%5EGDAXI"),
        ("stable_quote_^FTSE", "/quote?symbol=%5EFTSE"),
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


# =========================================================================== v126: trzy nowe sekrety właściciela (27.09.2026)

# --------------------------------------------------------------------------- coinalyze (v126k)
# Coinalyze API v1 (https://api.coinalyze.net/v1/doc/): key in header `api_key`; 40 API calls per minute per key and
# every symbol in a request counts as one call (a request with 5 symbols = 5 calls). This group uses 17 API calls in total.
# Prints only: HTTP status, sizes, key names, counts, dates, exchange codes, market-symbol codes (public metadata) and
# derived unitless ratios — never key values, URLs, headers or raw bodies.
# Secret COINALYZE (without _KEY) is deliberately NOT a candidate (owner: ignore it).
KEY_CANDIDATES["coinalyze"] = ["COINALYZE_KEY", "COINALYZE_API_KEY"]

CZ_BASE = "https://api.coinalyze.net/v1/"
CZ_COINS = ("BTC", "ETH", "XRP", "BNB", "SOL", "DOGE", "ADA", "TRX", "LINK", "AVAX")
CZ_QUOTES = ("USD", "USDT", "USDC")
_CZ = {"ex": set(), "btc": {}}   # public market metadata remembered between probes of this group


def _cz_json(raw):
    return json.loads(raw)


def _cz_ex(raw):
    L = _cz_json(raw)
    if not isinstance(L, list):
        return "not-a-list " + shape(raw)
    codes = sorted(str(e.get("code")) for e in L if isinstance(e, dict) and e.get("code") is not None)
    _CZ["ex"] = set(codes)
    return f"list n={len(L)} codes={''.join(codes)}"


def _cz_fm(raw):
    L = _cz_json(raw)
    if not isinstance(L, list):
        return "not-a-list " + shape(raw)
    per, lsn, exn, den, unk = {}, {}, {}, {}, 0
    for m in L:
        if not isinstance(m, dict):
            continue
        e = str(m.get("exchange"))
        if _CZ["ex"] and e not in _CZ["ex"]:
            unk += 1
        b, q = m.get("base_asset"), m.get("quote_asset")
        if b not in CZ_COINS or q not in CZ_QUOTES or m.get("is_perpetual") is not True:
            continue
        per[b] = per.get(b, 0) + 1
        exn[e] = exn.get(e, 0) + 1
        d = str(m.get("oi_lq_vol_denominated_in") or "-")[:1]
        den[d] = den.get(d, 0) + 1
        if m.get("has_long_short_ratio_data") is True:
            lsn[b] = lsn.get(b, 0) + 1
        if b == "BTC" and isinstance(m.get("symbol"), str):
            _CZ["btc"].setdefault((e, q), m["symbol"])
    s = lambda e, q: _CZ["btc"].get((e, q), "-")
    return (f"list n={len(L)} perps10={sum(per.values())} "
            + " ".join(f"{c}={per.get(c, 0)}/ls{lsn.get(c, 0)}" for c in CZ_COINS)
            + " ex=" + ",".join(f"{k}:{v}" for k, v in sorted(exn.items()))
            + " den=" + ",".join(f"{k}:{v}" for k, v in sorted(den.items()))
            + f" unknown_ex={unk} sym_A={s('A', 'USDT')} sym_6={s('6', 'USDT')} sym_3={s('3', 'USDT')} sym_H={s('H', 'USD')}")


def _cz_cur(raw):
    L = _cz_json(raw)
    if not isinstance(L, list):
        return "not-a-list " + shape(raw)
    now = time.time() * 1000
    ages = [int((now - x["update"]) / 1000) for x in L if isinstance(x, dict) and isinstance(x.get("update"), (int, float))]
    pos = all(isinstance(x.get("value"), (int, float)) and not isinstance(x.get("value"), bool) and x["value"] > 0 for x in L if isinstance(x, dict))
    keys = sorted(L[0].keys()) if L and isinstance(L[0], dict) else []
    return f"list n={len(L)} keys={','.join(keys)} values_pos={pos} max_age_s={max(ages) if ages else '-'}"


def _cz_hist(raw):
    """Per symbol: rows, first date, last timestamp, keys of a row, ascending order, alignment to hour/day."""
    L = _cz_json(raw)
    if not isinstance(L, list):
        return "not-a-list " + shape(raw)
    out = []
    for it in L:
        h = it.get("history") if isinstance(it, dict) else None
        sym = str(it.get("symbol")) if isinstance(it, dict) else "?"
        if not isinstance(h, list):
            out.append(f"{sym}:no-history")
            continue
        ts = [r["t"] for r in h if isinstance(r, dict) and isinstance(r.get("t"), (int, float))]
        if not ts:
            out.append(f"{sym}:rows=0")
            continue
        f = dt.datetime.fromtimestamp(min(ts), dt.timezone.utc).date().isoformat()
        la = dt.datetime.fromtimestamp(max(ts), dt.timezone.utc).isoformat(timespec="minutes")
        zero = sum(1 for r in h if isinstance(r, dict) and "c" not in r and "r" not in r and r.get("l") == 0 and r.get("s") == 0)   # liquidation rows only
        out.append(f"{sym}:rows={len(ts)} first={f} last={la} keys={','.join(sorted(h[-1].keys()))} asc={ts == sorted(ts)}"
                   f" h_aligned={all(t % 3600 == 0 for t in ts)} d_aligned={all(t % 86400 == 0 for t in ts)} zero_ls_rows={zero}")
    return f"list n={len(L)} " + " ; ".join(out)


def _hl_btc_funding():
    """Hyperliquid (public): current hourly funding of BTC, as a fraction — for the unit cross-check only."""
    st, raw, _, _ = http("https://api.hyperliquid.xyz/info", "POST", {"type": "metaAndAssetCtxs"})
    try:
        meta, ctx = json.loads(raw)
        for u, c in zip(meta["universe"], ctx):
            if u.get("name") == "BTC":
                return float(c["funding"])
    except Exception:
        return None
    return None


def _cz_fr_ratio(hl_f):
    def fn(raw):
        L = _cz_json(raw)
        base = _cz_cur(raw)
        v = L[0].get("value") if isinstance(L, list) and L and isinstance(L[0], dict) else None
        if not isinstance(v, (int, float)) or not hl_f:
            return base + " hl_ratio=-"
        r = (v / 100.0) / hl_f
        verdict = "8h-normalised" if 6 <= r <= 10 else "native-1h" if 0.75 <= r <= 1.33 else "unclear"
        return base + f" hl_ratio={r:.2f} ({verdict})"
    return fn


def g_coinalyze():
    # keyless: documented error shape (seen 27.09.2026 from PL: HTTP 401 {"message":"Invalid/Missing API key"})
    probe("coinalyze", "keyless_exchanges_expect401", CZ_BASE + "exchanges")
    name, key = find_key("coinalyze")
    if not key:
        skipped("coinalyze", "exchanges/markets/oi/fr/lq/ls")
        return
    H = {"api_key": key}   # urllib sends it as "Api_key" (header names are case-insensitive) — this probe proves it works
    P = lambda label, path, fn=None: (probe("coinalyze", label, CZ_BASE + path, env_name=name, headers=H, extra_fn=fn), time.sleep(0.3))[0]
    now = int(time.time())
    P("exchanges", "exchanges", _cz_ex)                                     # 1 call
    P("future-markets", "future-markets", _cz_fm)                           # 1 call
    a = _CZ["btc"].get(("A", "USDT"), "BTCUSDT_PERP.A")
    b = _CZ["btc"].get(("6", "USDT"))
    h = _CZ["btc"].get(("H", "USD"))
    cur = ",".join(x for x in (a, b, h) if x)
    P("open-interest_usd_A6H", f"open-interest?symbols={cur}&convert_to_usd=true", _cz_cur)            # 3 calls
    if h:
        hl_f = _hl_btc_funding()
        P("funding-rate_H_vs_direct", f"funding-rate?symbols={h}", _cz_fr_ratio(hl_f))                 # 1 call
        P("predicted-fr_H_vs_direct", f"predicted-funding-rate?symbols={h}", _cz_fr_ratio(hl_f))       # 1 call
    P("funding-rate_A", f"funding-rate?symbols={a}", _cz_cur)                                           # 1 call
    lq = ",".join(x for x in (a, b, h) if x)
    P("liq-hist_1h_24h_A6H_usd", f"liquidation-history?symbols={lq}&interval=1hour&from={now - 86400}&to={now}&convert_to_usd=true", _cz_hist)   # 3 calls
    P("ls-hist_daily_since2019_A", f"long-short-ratio-history?symbols={a}&interval=daily&from=1546300800&to={now}", _cz_hist)                      # 1 call
    P("oi-hist_daily_since2019_A_usd", f"open-interest-history?symbols={a}&interval=daily&from=1546300800&to={now}&convert_to_usd=true", _cz_hist)  # 1 call
    P("oi-hist_1h_120d_A_usd", f"open-interest-history?symbols={a}&interval=1hour&from={now - 120 * 86400}&to={now}&convert_to_usd=true", _cz_hist)  # 1 call
    P("fr-hist_daily_400d_A", f"funding-rate-history?symbols={a}&interval=daily&from={now - 400 * 86400}&to={now}", _cz_hist)                     # 1 call
    P("unknown_symbol_mix", f"open-interest?symbols={a},ZZZUSDT_PERP.A", _cz_cur)                                                               # 2 calls
    # total: 1+1+3+1+1+1+3+1+1+1+1+2 = 17 API calls (< 40/min)


# --- paste into narzedzia/sondy.py (v126k, label "banxico") ---------------------------------------------
# 1) KEY_CANDIDATES: add   "banxico": ["BANXICO_TOKEN"],
# 2) GROUPS: append g_banxico
# 3) .github/workflows/sondy.yml: env  BANXICO_TOKEN: ${{ secrets.BANXICO_TOKEN }}  and add 'banxico' to the
#    first provider tuple of the annotation filter (so both the keyless control line and the keyed lines reach the notice).
# Prints only: HTTP status, byte length, series ids, counts, last data DATE per series (public calendar dates),
# comma/N-E flags, a boolean sum check and unit names of odd series. Never the token, URLs, headers or values.

BMX_BASE = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/"
BMX_IDS = "SF65218,SF65219,SF65137,SF65046,SF65107,SP68257"            # exactly what build_meksyk uses today
BMX_EXTRA = "SF108390,SF341599,SF347164,SF355431,SF65077"              # optional: Udibonos in MXN, Bondes F, Bondes G, Bonos MS, Bondes D
BMX_PARTS = ("SF65137", "SF65046", "SF108390", "SF341599", "SF347164", "SF355431", "SF65077")   # sum == SF65218 (checked on 178 days of 2026, max diff 0.03)


def _bmx_series(raw):
    obj = json.loads(raw)
    return ((obj or {}).get("bmx") or {}).get("series") or []


def _bmx_num(s):
    s = str(s).strip()
    if s in ("", "N/E"):
        return None
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _bmx_data_shape(raw):
    ser = _bmx_series(raw)
    parts, comma, ne, cols = [], 0, 0, {}
    for s in ser:
        dat = s.get("datos") if isinstance(s.get("datos"), list) else []
        num = [(str(o.get("fecha", "")), _bmx_num(o.get("dato"))) for o in dat if isinstance(o, dict)]
        num = [(f, v) for f, v in num if v is not None]
        comma += sum("," in str(o.get("dato", "")) for o in dat if isinstance(o, dict))
        ne += sum(str(o.get("dato", "")).strip() == "N/E" for o in dat if isinstance(o, dict))
        cols[s.get("idSerie")] = dict(num)
        parts.append(f"{s.get('idSerie')}:{len(num)}/{len(dat)}@{num[-1][0] if num else '-'}" + ("" if "datos" in s else "(no datos)"))
    out = f"series={len(ser)} commas={comma} NE={ne} " + " ".join(parts)
    tot = cols.get("SF65218") or {}
    days = [d for d in tot if all(d in (cols.get(p) or {}) for p in BMX_PARTS if p in cols)]
    if days and all(p in cols for p in BMX_PARTS):
        d = max(days, key=lambda x: x[6:] + x[3:5] + x[:2])        # dd/mm/yyyy -> latest
        diff = abs(sum(cols[p][d] for p in BMX_PARTS) - tot[d])
        out += f" sum_ok={diff < 0.1} on {d}"
    return out


def _bmx_meta_shape(raw):
    ser = _bmx_series(raw)
    odd = [f"{s.get('idSerie')}={s.get('unidad')}" for s in ser
           if s.get("unidad") not in ("Millones de Pesos", "Millones de Unidades de Inversión", "Unidades de Inversión")]
    per = sorted({str(s.get("periodicidad")) for s in ser})
    return f"series={len(ser)} periodicidad={per} odd_units=[{', '.join(odd)}]"


def _bmx_err(raw):
    """v126: publiczny komunikat błędu SIE ({"error":{"mensaje","detalle"}}) — bez tokenu (scrub w report), najwyżej 110 znaków."""
    try:
        e = (json.loads(raw) or {}).get("error") or {}
        return f"mensaje={str(e.get('mensaje'))[:110]!r} detalle={str(e.get('detalle'))[:110]!r}"
    except Exception as x:
        return "not-json " + type(x).__name__


def _bmx_diag(name, key):
    """v126 (27.09): token odrzucany (HTTP 400). Tylko wartości logiczne o FORMACIE tokenu (nie długość, nie znaki) i treść błędu banku."""
    import re
    fmt = bool(re.fullmatch(r"[0-9a-f]{64}", key))
    fmt_ci = bool(re.fullmatch(r"[0-9a-fA-F]{64}", key))
    odd = any(c in key for c in " \t\r\n\"'<>:=")
    st, raw, ms, err = http(BMX_BASE + "SF65218/datos/oportuno")
    report("banxico", None, "diag_keyless_error", st, raw, ms, err, _bmx_err(raw) if raw else None)
    time.sleep(0.5)
    st, raw, ms, err = http(BMX_BASE + "SF65218/datos/oportuno", headers={"Bmx-Token": key, "Accept": "application/json"})
    report("banxico", name, "diag_keyed_error", st, raw, ms, err,
           (_bmx_err(raw) if st != 200 and raw else "ok") + f" token_hex64={fmt} hex64_any_case={fmt_ci} odd_chars={odd}")


def g_banxico():
    # keyless control: proves the US runner reaches the API host (expected HTTP 400, keys=[error], "Token inválido")
    probe("banxico", "keyless_oportuno_SF65218", BMX_BASE + "SF65218/datos/oportuno")
    name, key = find_key("banxico")
    if not key:
        skipped("banxico", "SIE API (metadatos/oportuno/rango)")
        return
    _bmx_diag(name, key)
    hdr = {"Bmx-Token": key, "Accept": "application/json"}             # header only; never the ?token= parameter
    time.sleep(0.5)
    probe("banxico", "metadatos_11", BMX_BASE + BMX_IDS + "," + BMX_EXTRA, env_name=name, headers=hdr, extra_fn=_bmx_meta_shape)
    time.sleep(0.5)
    probe("banxico", "oportuno_6", BMX_BASE + BMX_IDS + "/datos/oportuno", env_name=name, headers=hdr, extra_fn=_bmx_data_shape)
    time.sleep(0.5)
    end = _utc_today()
    start = end - dt.timedelta(days=30)
    probe("banxico", "rango_11_30d", f"{BMX_BASE}{BMX_IDS},{BMX_EXTRA}/datos/{start.isoformat()}/{end.isoformat()}",
          env_name=name, headers=hdr, extra_fn=_bmx_data_shape)


# Snippet for narzedzia/sondy.py (v126k, label "evds"). Paste the three parts where marked; nothing else in sondy.py changes
# except (4) the optional rate-limit header whitelist. Also add EVDS_KEY to .github/workflows/sondy.yml and 'evds' to the
# annotation filter there (see PLAN.md section 6). Prints only: status, ms, bytes, counts, first/last DATE, format flags —
# never the key, the URL, response headers (except the three whitelisted integers) or any data value.

# (1) KEY_CANDIDATES — add one entry:
#     "evds":         ["EVDS_KEY"],

# (2) the group (after g_alphavantage), and add g_evds to GROUPS:
EVDS_B = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
EVDS_CODES = ("TP.MKNETHAR.M20", "TP.MKNETHAR.M7", "TP.MKNETHAR.M8", "TP.MKNETHAR.M12", "TP.MKNETHAR.M22", "TP.MKNETHAR.M23")


def _evds_tr_today():
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).date()     # Türkiye UTC+3


def _evds_shape(raw):
    """items / totalCount / first and last date / all Fridays / which of the 6 codes are present / all-null rows / Tarih format.
    Dates are public calendar dates of the weekly release (no values are printed)."""
    import re
    obj = json.loads(raw)
    if not isinstance(obj, dict) or not isinstance(obj.get("items"), list):
        return shape(raw)
    it = [x for x in obj["items"] if isinstance(x, dict)]
    fm = {"dd-mm-yyyy": 0, "other": 0, "missing": 0}
    ds = []
    for x in it:
        t = str(x.get("Tarih") or "")
        m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", t)
        fm["dd-mm-yyyy" if m else ("missing" if not t else "other")] += 1
        if m and not all(x.get(c.replace(".", "_")) in (None, "") for c in EVDS_CODES):   # first/last = weeks WITH data
            ds.append(dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
    codes = sum(1 for c in EVDS_CODES if any(c.replace(".", "_") in x for x in it))
    nulls = sum(1 for x in it if all(x.get(c.replace(".", "_")) in (None, "") for c in EVDS_CODES))
    ux = sum(1 for x in it if isinstance(x.get("UNIXTIME"), dict))
    vtype = sorted({type(x.get("TP_MKNETHAR_M20")).__name__ for x in it})
    return (f"items={len(it)} total={obj.get('totalCount')} first={min(ds).isoformat() if ds else '-'} last={max(ds).isoformat() if ds else '-'} "
            f"fri={all(d.weekday() == 4 for d in ds)} codes={codes}/6 nullrows={nulls} tarih={'/'.join(f'{k}:{v}' for k, v in fm.items())} "
            f"unixtime={ux} vtype={','.join(vtype)} "
            f"keys=[{','.join(sorted(obj.keys()))[:60]}]")


def _evds_list(raw):
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    m20 = next((x for x in obj if isinstance(x, dict) and str(x.get("SERIE_CODE") or x.get("Serie_Code")) == "TP.MKNETHAR.M20"), {})
    return (f"list n={len(obj)} m20_fields=[{','.join(sorted(m20.keys()))[:120]}] "
            f"m20_start={m20.get('START_DATE') or m20.get('Start_Date')} m20_end={m20.get('END_DATE') or m20.get('End_Date')}")


def g_evds():
    end = _evds_tr_today()
    q = lambda a, b: (f"{EVDS_B}series={'-'.join(EVDS_CODES)}&startDate={a.strftime('%d-%m-%Y')}"
                      f"&endDate={b.strftime('%d-%m-%Y')}&type=json")
    # keyless: reachability of the API host from the US runner + the no-key error shape (expect HTTP 403 keys=[status,message])
    probe("evds", "nokey_series_403", q(end - dt.timedelta(days=56), end))
    name, key = find_key("evds")
    if not key:
        skipped("evds", "series/serieList (EVDS_KEY)")
        return
    hdr = {"key": key, "Accept": "application/json"}
    # A: what the collector asks on every refresh (last ~8 weeks): expect 200, items 8-9, codes=6/6, fri=True, last = latest Friday
    probe("evds", "series6_8w", q(end - dt.timedelta(days=56), end), env_name=name, headers=hdr, extra_fn=_evds_shape)
    time.sleep(1.0)
    # B: the whole history in ONE request (315+ Fridays x 6 series = 1890 values > WS_MAX_OBSERVATION 1000):
    #    items ~315 & first=2020-09-11 -> cap counts dates;  items ~166 & first later -> cap counts values (chunking needed; plan chunks anyway)
    probe("evds", "series6_full_cap_test", q(dt.date(2020, 9, 11), end), env_name=name, headers=hdr, extra_fn=_evds_shape)
    time.sleep(1.0)
    # C: documented metadata service: series list of the data group, with START/END dates of TP.MKNETHAR.M20
    probe("evds", "serieList_bie_mknethar", f"{EVDS_B}serieList/type=json&code=bie_mknethar", env_name=name, headers=hdr, extra_fn=_evds_list)
    # never probe evds2.tcmb.gov.tr with the key: every evds2 URL answers 302 -> https://evds3.tcmb.gov.tr/ (HTML) and urllib
    # forwards custom headers to the redirect target.


# (3) GROUPS = [..., g_fmp, g_alphavantage, g_evds]


# v136 (etykieta „dolar”): sondy bez klucza dla data/dolar.json — serwis kursów Argentyny, Wenezueli i Boliwii (przed nim Cloudflare), jego kopia
# plików na GitHubie (zapas), serwis historii Argentyny (jednorazowe uzupełnienie) i API banku centralnego Argentyny (tylko kontrola dzienna).
# Wypisuje tylko: kod HTTP, ms, bajty, liczniki, identyfikatory casa/fuente, nazwy pól, znaczniki aktualizacji i daty oraz wartości logiczne —
# nigdy kursu, adresu, nagłówka ani treści. Oczekiwane z serwera w USA (27.09.2026): wszędzie HTTP 200 poza „ar_dolares_pythonUA_exp403” = 403
# (Cloudflare „error code: 1010” odrzuca domyślny identyfikator Python-urllib; zbieracz wysyła własny) — dlatego podsumowanie „dolarapi” pokazuje
# „likely geo/CDN block on 1”: to ta zamierzona sonda. Opcjonalna sonda biuletynu B3 z planu pominięta (osobne, przyszłe wydanie).
DOLAR_UA = {"User-Agent": "CapitalFlowAI-collector/1.0"}      # dokładnie to, co wysyłają zbieraj_dane.get() / get_json()
DOLAR_AR_CASAS = ("oficial", "blue", "bolsa", "contadoconliqui", "mayorista", "cripto", "tarjeta")


def _dl_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0


def _dl_ar(raw):
    """Kursy Argentyny (odczyt główny albo drugi): obecne casy, ile ma dodatnią sprzedaż, czy każdy stosunek do kursu hurtowego jest rozsądny
    (0,5..4,0; bez „tarjeta” — to wyliczenie z podatkami), pierwszy/ostatni znacznik aktualizacji, nazwy pól."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    it = [x for x in obj if isinstance(x, dict)]
    casas = {str(x.get("casa")) for x in it}
    ok = sum(1 for x in it if _dl_num(x.get("venta")))
    ts = sorted(str(x.get("fechaActualizacion"))[:16] for x in it if x.get("fechaActualizacion"))
    base = next((x.get("venta") for x in it if x.get("casa") == "mayorista"), None)
    sane = _dl_num(base) and all(0.5 <= x["venta"] / base <= 4.0 for x in it if _dl_num(x.get("venta")) and x.get("casa") != "tarjeta")
    cmp_ok = all(not _dl_num(x.get("compra")) or x["compra"] <= x["venta"] * 1.02 for x in it if _dl_num(x.get("venta")))
    keys = sorted({str(k) for x in it for k in x})
    return (f"list n={len(it)} venta_ok={ok} missing={sorted(set(DOLAR_AR_CASAS) - casas) or '-'} "
            f"new={sorted(casas - set(DOLAR_AR_CASAS)) or '-'} ratio_sane={bool(sane)} compra_le_venta={cmp_ok} "
            f"t_min={ts[0] if ts else '-'} t_max={ts[-1] if ts else '-'} keys=[{','.join(keys)[:90]}]")


def _dl_ve(raw):
    """Wenezuela: obecne źródła (fuente), dodatnia średnia, rozsądny stosunek równoległy/oficjalny (0,5..5,0), oba znaczniki aktualizacji."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    it = {str(x.get("fuente")): x for x in obj if isinstance(x, dict)}
    of, pa = it.get("oficial") or {}, it.get("paralelo") or {}
    sane = _dl_num(of.get("promedio")) and _dl_num(pa.get("promedio")) and 0.5 <= pa["promedio"] / of["promedio"] <= 5.0
    return (f"list n={len(obj)} fuentes={sorted(it)} promedio_ok={sum(1 for x in it.values() if _dl_num(x.get('promedio')))} "
            f"ratio_sane={bool(sane)} t_oficial={str(of.get('fechaActualizacion'))[:25]} t_paralelo={str(pa.get('fechaActualizacion'))[:16]}")


def _dl_bo(raw):
    """Boliwia: obecne casy, dodatnia sprzedaż, rozsądny stosunek P2P/oficjalny (0,5..5,0), oba znaczniki aktualizacji."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    it = {str(x.get("casa")): x for x in obj if isinstance(x, dict)}
    of, bn = it.get("oficial") or {}, it.get("binance") or {}
    sane = _dl_num(of.get("venta")) and _dl_num(bn.get("venta")) and 0.5 <= bn["venta"] / of["venta"] <= 5.0
    return (f"list n={len(obj)} casas={sorted(it)} venta_ok={sum(1 for x in it.values() if _dl_num(x.get('venta')))} "
            f"ratio_sane={bool(sane)} t_oficial={str(of.get('fechaActualizacion'))[:16]} t_p2p={str(bn.get('fechaActualizacion'))[:16]}")


def _dl_hist(raw):
    """Lista historii (Wenezuela, Argentyna): wiersze z dodatnią liczbą, pierwsza/ostatnia data, wiersze z datą po dzisiejszej (UTC), powtórzone daty."""
    obj = json.loads(raw)
    if not isinstance(obj, list):
        return shape(raw)
    ds = sorted(str(x.get("fecha")) for x in obj if isinstance(x, dict) and (_dl_num(x.get("promedio")) or _dl_num(x.get("venta"))))
    today = _utc_today().isoformat()
    return (f"list n={len(obj)} num={len(ds)} first={ds[0] if ds else '-'} last={ds[-1] if ds else '-'} "
            f"future_dated={sum(1 for d in ds if d > today)} dup={len(ds) - len(set(ds))}")


def _dl_bcra(raw):
    """API kursów banku centralnego Argentyny (Cotizaciones/USD): dni z dodatnim kursem, ostatnia data, status."""
    obj = json.loads(raw)
    r = obj.get("results") if isinstance(obj, dict) else None
    if not isinstance(r, list):
        return shape(raw)
    ds = sorted(str(x.get("fecha")) for x in r if isinstance(x, dict)
                and any(isinstance(y, dict) and _dl_num(y.get("tipoCotizacion")) for y in (x.get("detalle") or [])))
    return f"results={len(r)} num={len(ds)} last={ds[-1] if ds else '-'} status={obj.get('status')}"


def g_dolar():
    ar = "https://dolarapi.com/v1/dolares"
    # A: to, o co zbieracz pyta przy każdej budowie (jego identyfikator), potem to samo z identyfikatorem sond i z domyślnym Pythona (oczekiwane 403)
    probe("dolarapi", "ar_dolares_collectorUA", ar, headers=DOLAR_UA, extra_fn=_dl_ar)
    time.sleep(0.3)
    probe("dolarapi", "ar_dolares_sondyUA", ar, extra_fn=_dl_ar)
    time.sleep(0.3)
    probe("dolarapi", "ar_dolares_pythonUA_exp403", ar, headers={"User-Agent": "Python-urllib/3.12"})
    time.sleep(0.3)
    # B: drugi odczyt tych samych kursów Argentyny — tylko dla kontroli dziennej
    probe("dolarapi", "ar_ambito_collectorUA", "https://dolarapi.com/v1/ambito/dolares", headers=DOLAR_UA, extra_fn=_dl_ar)
    time.sleep(0.3)
    probe("dolarapi", "ve_dolares", "https://ve.dolarapi.com/v1/dolares", headers=DOLAR_UA, extra_fn=_dl_ve)
    time.sleep(0.3)
    probe("dolarapi", "bo_dolares", "https://bo.dolarapi.com/v1/dolares", headers=DOLAR_UA, extra_fn=_dl_bo)
    for f in ("oficial", "paralelo"):
        time.sleep(0.3)
        probe("dolarapi", f"ve_hist_{f}", f"https://ve.dolarapi.com/v1/historicos/dolares/{f}", headers=DOLAR_UA, extra_fn=_dl_hist)
    # C: zapas — ten sam plik w publicznym repozytorium projektu (27.09 bajt w bajt jak w API)
    probe("dolarapi-gh", "raw_ar_dolares", "https://raw.githubusercontent.com/enzonotario/dolarapi.com/main/datos/v1/dolares/index.json",
          headers=DOLAR_UA, extra_fn=_dl_ar)
    # D: historia Argentyny (jedna pełna seria ok. 0,54 MB; zbieracz potrzebuje sześciu serii tylko raz) i jeden wiersz jednego dnia
    probe("argdatos", "hist_contadoconliqui", "https://api.argentinadatos.com/v1/cotizaciones/dolares/contadoconliqui",
          headers=DOLAR_UA, extra_fn=_dl_hist)
    d = _utc_today() - dt.timedelta(days=2)
    probe("argdatos", "day_blue_D-2", f"https://api.argentinadatos.com/v1/cotizaciones/dolares/blue/{d:%Y/%m/%d}", headers=DOLAR_UA)
    # E: oficjalny kurs hurtowy (API banku centralnego Argentyny, bez klucza) — tylko porównanie w kontroli dziennej
    a, b = _utc_today() - dt.timedelta(days=10), _utc_today()
    probe("bcra", "cotizaciones_USD_10d",
          f"https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD?fechadesde={a.isoformat()}&fechahasta={b.isoformat()}",
          headers=DOLAR_UA, extra_fn=_dl_bcra)


def g_nasdaq():
    """v127, krok 0 wydania: Nasdaq quote API bez klucza — DOKŁADNIE ta prośba, którą wyśle zbieracz (sam nagłówek User-Agent zbieracza, bez
    Accept); wypisuje tylko kod HTTP, liczbę wierszy i najnowszą datę (bez adresu i treści). Wiersz „summary nasdaq-rows” trafia do adnotacji."""
    d = _utc_today()
    url = (f"https://api.nasdaq.com/api/quote/SPY/historical?assetclass=etf&fromdate={(d - dt.timedelta(days=10)).isoformat()}"
           f"&limit=5&todate={d.isoformat()}")
    req = urllib.request.Request(url, headers={"User-Agent": "CapitalFlowAI-collector/1.0"})
    t = time.monotonic(); status = raw = err = None
    try:
        with urllib.request.urlopen(req, timeout=min(REQ_TIMEOUT, max(1.0, _remaining())), context=SSL_CTX) as r:
            status = r.status; raw = _read_capped(r, t + REQ_TIMEOUT)
    except urllib.error.HTTPError as e:
        status = e.code
    except Exception as e:  # noqa
        err = type(e).__name__
    rows = newest = None
    if status == 200 and raw:
        try:
            rr = ((json.loads(raw).get("data") or {}).get("tradesTable") or {}).get("rows") or []
            rows = len(rr); newest = max((dt.datetime.strptime(x["date"], "%m/%d/%Y").date() for x in rr), default=None)
        except Exception as e:  # noqa
            err = type(e).__name__
    report("nasdaq", None, "SPY_historical_5 (collector UA)", status, raw, int((time.monotonic() - t) * 1000), err,
           f"rows={rows} newest={newest}" if rows is not None else None)
    with _print_lock:
        print(f"summary nasdaq-rows {rows} newest {newest}", flush=True)


GROUPS = [g_deribit, g_binance_fapi, g_binance_mirrors, g_bybit, g_okx, g_hyperliquid,
          g_alternatives, g_onchain_public, g_etherscan, g_cryptopanic, g_tiingo,
          g_massive, g_eodhd, g_fmp, g_alphavantage, g_coinalyze, g_banxico, g_evds, g_dolar, g_nasdaq]


# v134 (etykieta „ici”): sondy bez klucza dla data/ici.json — pliki .xls wydawcy statystyk funduszy w USA: napływy do funduszy
# długoterminowych (środy) i aktywa funduszy rynku pieniężnego (czwartki). Dokładnie te nagłówki, które wysyła zbieracz (ICI_HDR: identyfikator
# automatu + Accept / Accept-Language / Accept-Encoding: identity — bez nich CDN odpowiada 403); 4 zapytania z przerwą 2 s. Wypisuje tylko: kod
# HTTP, ms, bajty, czy jest sygnatura OLE2 (.xls), liczbę dat w pliku, pierwszą/ostatnią datę i liczbę śród — nigdy adresu, nagłówka ani treści.
# Oczekiwane z serwera w USA (sonda 27.09.2026): lt_recipe 200, mm_recipe 200, mm_if_modified_since_now 304, lt_prev_year_alias 200
# (stara nazwa roku = kopia bieżącego pliku). Przeglądarkowego zestawu nagłówków nie sprawdzamy — zbieracz go nie używa.
import re as _ici_re

ICI_B = "https://www.ici.org/"
ICI_OK_HDR = {"User-Agent": "CapitalFlowAI-collector/1.0", "Accept": "application/vnd.ms-excel, */*", "Accept-Language": "en-US,en;q=0.9",
              "Accept-Encoding": "identity"}
_ICI_DATE = _ici_re.compile(rb"(?<![0-9/])(\d{1,2})/(\d{1,2})/(20\d\d)(?![0-9/])")


def _ici_shape(raw):
    """Sygnatura OLE2 i daty „MM/DD/RRRR” zapisane w pliku (tylko liczba dat, pierwsza/ostatnia i liczba śród — bez wartości)."""
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
    probe("ici", "lt_recipe", lt, headers=ICI_OK_HDR, extra_fn=_ici_shape)                      # napływy: zapytanie zbieracza → 200
    time.sleep(2.0)
    probe("ici", "mm_recipe", mm, headers=ICI_OK_HDR, extra_fn=_ici_shape)                      # rynek pieniężny → 200
    time.sleep(2.0)
    import email.utils as _eu
    probe("ici", "mm_if_modified_since_now", mm, headers={**ICI_OK_HDR, "If-Modified-Since": _eu.formatdate(time.time(), usegmt=True)})   # → 304
    time.sleep(2.0)
    probe("ici", "lt_prev_year_alias", f"{ICI_B}combined_flows_data_{y - 1}.xls", headers=ICI_OK_HDR, extra_fn=_ici_shape)            # → 200


GROUPS.insert(GROUPS.index(g_nasdaq), g_ici)   # v134: przed g_nasdaq (test v127: g_nasdaq zostaje ostatnia)


# v137 (etykieta „jpx”): sondy bez klucza dla data/jpx.json — tygodniowe zestawienie giełdy w Tokio (kto kupuje i sprzedaje akcje). Cztery
# zapytania z przerwą 1,5 s i identyfikatorem zbieracza: lista (strona angielska), ta sama lista z If-Modified-Since „teraz” (oczekiwane 304),
# najnowszy plik .xlsx z listy, strona archiwum bieżącego roku. Wypisuje tylko: kod HTTP, ms, bajty, liczby linków, daty tygodni z nazw plików,
# sygnaturę pliku (zip / OLE2), liczbę kart i rząd wielkości największej liczby (13 = jeny, 10 = tys. jenów) — nigdy adresu, strony, pliku ani
# wartości. Wiersz „summary jpx-files …” trafia do adnotacji (filtr adnotacji w sondy.yml przepuszcza wiersze summary — workflow bez zmian).
JPX_SB = "https://www.jpx.co.jp"
JPX_SEN = JPX_SB + "/english/markets/statistics-equities/investor-type/"
JPX_S_HDR = {"User-Agent": "CapitalFlowAI-collector/1.0"}
_JPX_S = {"new": [], "arch": None}


def _jpx_s_links(raw):
    """Lista albo archiwum: liczba plików obu formatów, najnowszy tydzień z nazwy pliku, lata archiwów (bez treści strony)."""
    import re as _re
    s = raw.decode("utf-8", "replace")
    pre = r'href="(?:https?://www\.jpx\.co\.jp)?'
    new = sorted(set(_re.findall(pre + r'(/[^"]*/stock_1_w_(\d{8})_(\d{8})\.xlsx)"', s)), key=lambda x: x[2])
    old = set(_re.findall(pre + r'/[^"]*/stock_val_1_(\d{6})\.xls"', s))
    arch = dict((y, n) for n, y in _re.findall(r'<option[^>]*value="[^"]*00-00-archives-(\d{2})\.html"[^>]*>\s*(\d{4})', s))
    if new and not _JPX_S["new"]:
        _JPX_S["new"] = new
    if arch and _JPX_S["arch"] is None:
        _JPX_S["arch"] = arch
    return (f"new_xlsx={len(new)}({new[-1][1] + '-' + new[-1][2] if new else '-'}) old_xls={len(old)} "
            f"arch_years={len(arch)}({min(arch) if arch else '-'}..{max(arch) if arch else '-'})")


def _jpx_s_file(raw):
    """Plik danych: sygnatura, liczba kart, „Tokyo & Nagoya” w napisach, rząd wielkości największej liczby (bez wartości)."""
    import io as _io
    import re as _re
    import zipfile as _zf
    if raw[:4] != b"PK\x03\x04":
        return f"zip=False ole2={raw[:8] == bytes.fromhex('d0cf11e0a1b11ae1')} html={raw[:200].lstrip().lower().startswith(b'<')}"
    z = _zf.ZipFile(_io.BytesIO(raw))
    names = z.namelist()
    wb = z.read("xl/workbook.xml").decode("utf-8", "replace") if "xl/workbook.xml" in names else ""
    ss = z.read("xl/sharedStrings.xml").decode("utf-8", "replace") if "xl/sharedStrings.xml" in names else ""
    mx = 0.0
    for n in names:
        if n.startswith("xl/worksheets/sheet"):
            for attrs, v in _re.findall(r"<c ([^>]*)>\s*<v>([^<]*)</v>", z.read(n).decode("utf-8", "replace")):
                if not _re.search(r'\bt="(s|str|b|e|inlineStr)"', attrs):
                    try:
                        mx = max(mx, abs(float(v)))
                    except ValueError:
                        pass
    e = len(str(int(mx))) - 1 if mx >= 1 else -1
    _JPX_S["unit"] = "JPY" if e >= 12 else ("kJPY" if e >= 0 else "-")
    return f"zip=True sheets={wb.count('<sheet ')} tokyo_nagoya={'Tokyo &amp; Nagoya' in ss} maxexp={e if e >= 0 else '-'}"


def g_jpx():
    import email.utils as _eu
    probe("jpx", "listing_en", JPX_SEN + "index.html", headers=JPX_S_HDR, extra_fn=_jpx_s_links)                     # → 200
    time.sleep(1.5)
    probe("jpx", "listing_if_modified_since_now", JPX_SEN + "index.html",
          headers={**JPX_S_HDR, "If-Modified-Since": _eu.formatdate(time.time(), usegmt=True)})                     # → 304
    time.sleep(1.5)
    new = _JPX_S["new"]
    if new:
        probe("jpx", "newest_xlsx", JPX_SB + new[-1][0], headers=JPX_S_HDR, extra_fn=_jpx_s_file)                    # → 200, zip
    else:
        skipped("jpx", "newest_xlsx", "no .xlsx link on the listing")
    time.sleep(1.5)
    arch = _JPX_S["arch"] or {}
    if arch:
        probe("jpx", "archive_current_year", JPX_SEN + f"00-00-archives-{arch[max(arch)]}.html", headers=JPX_S_HDR, extra_fn=_jpx_s_links)   # → 200
    else:
        skipped("jpx", "archive_current_year", "no archive map on the listing")
    with _print_lock:
        print(f"summary jpx-files new_xlsx={len(new)} newest={new[-1][1] + '-' + new[-1][2] if new else '-'} unit={_JPX_S.get('unit', '-')} "
              f"arch_years={len(arch)}", flush=True)


GROUPS.insert(GROUPS.index(g_nasdaq), g_jpx)   # v137: przed g_nasdaq (test v127: g_nasdaq zostaje ostatnia)


# v133 (etykieta „rwa”): sondy bez klucza dla data/rwa.json — oficjalne darmowe API wartości protokołów (tokenizowane aktywa ze świata realnego).
# Sześć zapytań z przerwą 0,5 s i nagłówkami zbieracza (identyfikator + Accept-Encoding: gzip): lista wszystkich protokołów (2,35 MB gzip — sondy
# czytają najwyżej 6 MB, a bez gzip lista ma 9 MB), bieżąca wartość trzech produktów ukrytych na liście (oczekiwane: liczba > 0) i jednego bez
# wartości (oczekiwane: pusty tekst), /rwa/current (tylko plan płatny — oczekiwane 404 na darmowym adresie). Wypisuje tylko: kod HTTP, ms, bajty,
# bajty po rozpakowaniu, liczby pozycji, wartości logiczne i datę najnowszego wpisu — nigdy kwoty, adresu, nagłówka ani treści. Wiersz
# „summary rwa-list …” trafia do adnotacji (filtr adnotacji w sondy.yml przepuszcza wiersze summary — workflow bez zmian).
RWA_SB = "https://api.llama.fi"
RWA_S_HDR = {"User-Agent": "CapitalFlowAI-collector/1.0", "Accept-Encoding": "gzip"}
RWA_S_HID = ("blackrock-buidl", "circle-usyc", "tether-gold", "fidelity-digital-interest-token")
_RWA_S = {"list": None, "num": 0}


def _rwa_s_body(raw):
    """gzip (bajty 1f8b) → bajty; inne bez zmian."""
    import gzip as _gz
    return _gz.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw


def _rwa_s_list(raw):
    """Lista protokołów: pozycje, kategoria RWA, z wartością > 0, ukryte (tvl null), martwe, pole zmiany 30 dni, najnowszy wpis (data) — bez kwot."""
    body = _rwa_s_body(raw)
    L = json.loads(body)
    if not isinstance(L, list):
        return "not-a-list " + shape(body)
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    R = [p for p in L if isinstance(p, dict) and p.get("category") == "RWA"]
    pos = sum(1 for p in R if num(p.get("tvl")) and p["tvl"] > 0)
    nul = sum(1 for p in R if p.get("tvl") is None)
    dead = sum(1 for p in R if p.get("deadFrom"))
    by = {p.get("slug"): p for p in R}
    hid = all(s in by and by[s].get("tvl") is None for s in RWA_S_HID[:3])
    c30 = any(k in p for p in R for k in ("change_1m", "change_30d"))
    la = [p["listedAt"] for p in R if num(p.get("listedAt"))]
    newest = dt.datetime.fromtimestamp(max(la), dt.timezone.utc).date().isoformat() if la else "-"
    _RWA_S["list"] = (len(L), len(R), pos, nul, hid)
    return (f"raw={len(body)}B list n={len(L)} rwa={len(R)} tvl>0={pos} tvl_null={nul} dead={dead} flagship_hidden={hid} "
            f"has_30d_field={c30} newest_listed={newest}")


def _rwa_s_tvl(raw):
    """/tvl/{produkt}: pusty tekst / liczba > 0 / inna treść — nigdy sama liczba."""
    body = _rwa_s_body(raw).strip()
    if not body:
        return "empty-body (no value)"
    try:
        v = float(body)
    except ValueError:
        return "not-a-number " + shape(body)
    if v > 0:
        _RWA_S["num"] += 1
    return f"number>0={v > 0} len={len(body)}"


def g_rwa():
    probe("rwa", "protocols_gzip_collectorUA", RWA_SB + "/protocols", headers=RWA_S_HDR, extra_fn=_rwa_s_list)          # → 200, ok. 2,35 MB
    for s in RWA_S_HID:
        time.sleep(0.5)
        probe("rwa", f"tvl_{s[:26]}", f"{RWA_SB}/tvl/{s}", headers=RWA_S_HDR, extra_fn=_rwa_s_tvl)                       # → 200 (3 liczby, 1 pusty)
    time.sleep(0.5)
    probe("rwa", "rwa_current_free_expect404", RWA_SB + "/rwa/current", headers=RWA_S_HDR)                                # → 404 (plan płatny)
    li = _RWA_S["list"]
    with _print_lock:
        print(f"summary rwa-list n={li[0] if li else '-'} rwa={li[1] if li else '-'} tvl>0={li[2] if li else '-'} tvl_null={li[3] if li else '-'} "
              f"flagship_hidden={li[4] if li else '-'} tvl_numbers={_RWA_S['num']}/3", flush=True)


GROUPS.insert(GROUPS.index(g_nasdaq), g_rwa)   # v133: przed g_nasdaq (test v127: g_nasdaq zostaje ostatnia)


# v150 (etykieta „rwa-chain”): sondy bez klucza dla odczytu własnego z łańcucha (blok onchain w data/rwa.json) — po jednym żądaniu na sieć do tych
# samych węzłów co zbieracz (przerwa 0,3 s): EVM — paczka eth_blockNumber + totalSupply() jednego tokenu (na Ethereum także latestRoundData() obu
# wyroczni i owner() kontraktów BUIDL; na BNB i Tempo owner() BUIDL); Solana — getMultipleAccounts trzech kont emisji (jedno zwykłe żądanie);
# Aptos — /view 0x1::fungible_asset::supply. Wypisuje tylko: kod HTTP, ms, bajty, liczbę wyników, czy wyniki są liczbami, wiek cen w godzinach
# i zgodność właściciela trzech kontraktów BUIDL bez strony emitenta (tak / nie) — nigdy kwot, cen ani adresów. Wiersz „summary rwa-chain …”
# trafia do adnotacji (filtr adnotacji w sondy.yml przepuszcza wiersze summary — workflow bez zmian).
RWC_S_SUP, RWC_S_RND, RWC_S_OWN = "0x18160ddd", "0xfeaf968c", "0x8da5cb5b"
RWC_S_BUIDL = "0x7712c34205737192402172409a8f7ccef8aa2aec"   # kontrakt wzorcowy (komunikat emitenta) — owner() porównujemy z trzema poniżej
RWC_S = [   # (sieć, węzeł, rodzaj, token do totalSupply(), dodatkowe wywołania eth_call [(adres, selektor, znaczenie)])
    ("eth", "https://ethereum-rpc.publicnode.com", "evm", RWC_S_BUIDL,
     [("0x214ed9da11d2fbe465a6fc601a91e62ebec1a0d6", RWC_S_RND, "px"), ("0x74f2199aeb743f68f05943e5715a33eaf2b61f53", RWC_S_RND, "px"),
      (RWC_S_BUIDL, RWC_S_OWN, "ref"), ("0x6a9da2d710bb9b700acde7cb81f10f1ff8c89041", RWC_S_OWN, "own")]),
    ("arb", "https://arbitrum-one-rpc.publicnode.com", "evm", "0xa6525ae43edcd03dc08e775774dcabd3bb925872", []),
    ("op", "https://optimism-rpc.publicnode.com", "evm", "0xa1cdab15bba75a80df4089cafba013e376957cf5", []),
    ("pol", "https://polygon-bor-rpc.publicnode.com", "evm", "0x2893ef551b6dd69f661ac00f11d93e5dc5dc0e99", []),
    ("avax", "https://avalanche-c-chain-rpc.publicnode.com", "evm", "0x53fc82f14f009009b440a706e31c9021e1196a2f", []),
    ("bsc", "https://bsc-rpc.publicnode.com", "evm", "0x8d0fa28f221eb5735bc71d3a0da67ee5bc821311",
     [("0x2d5bdc96d9c8aabbdb38c9a27398513e7e5ef84f", RWC_S_OWN, "own")]),
    ("tempo", "https://rpc.tempo.xyz", "evm", "0xb5ff12bd8010baef823d1bfa2ce6bdc0109cbb24", [("0xb5ff12bd8010baef823d1bfa2ce6bdc0109cbb24", RWC_S_OWN, "own")]),
    ("arc", "https://rpc.mainnet.arc.io", "evm", "0x8a5d989bbb96929f689b0200f435f53da42bf490", []),
    ("sol", "https://api.mainnet-beta.solana.com", "sol", ["GyWgeqpy5GueU2YbkE8xqUeVEokCMMCEeUrfbtMw6phr", "5GgRAEmv8ZxF2PR5hY72Qs5x1bnQ6UK2RbTPoqJ3wSwW",
                                                         "7LWanZteUKtvFjv4MHYgKXXdAuCQYFPJysL9pxxdRQGn"], []),
    ("apt", "https://api.mainnet.aptoslabs.com/v1/view", "apt", "0x50038be55be5b964cfa32cf128b5cf05f123959f286b4cc02b86cafd48945f89", []),
]
_RWC_S = {"ok": 0, "own": [], "ref": None}


def _rwc_s_word(r):
    return isinstance(r, str) and r.startswith("0x") and len(r) >= 66 and all(c in "0123456789abcdefABCDEF" for c in r[2:])


def _rwc_s_evm(extra):
    def fn(raw):
        r = json.loads(raw)
        if not isinstance(r, list):
            return "not-a-batch " + shape(raw)
        by = {x.get("id"): x.get("result") for x in r if isinstance(x, dict)}
        num = sum(1 for k in range(2) if isinstance(by.get(k), str) and by[k].startswith("0x"))
        ages, own = [], []
        for k, (_a, _sel, kind) in enumerate(extra, start=2):
            v = by.get(k)
            if kind == "px" and _rwc_s_word(v) and len(v) == 2 + 5 * 64:
                ages.append(round((time.time() - int(v[2 + 3 * 64:2 + 4 * 64], 16)) / 3600, 1))
            elif kind in ("ref", "own") and _rwc_s_word(v):
                o = v[-40:].lower()
                if kind == "ref":
                    _RWC_S["ref"] = o
                else:
                    own.append(o)
        _RWC_S["own"] += own
        ok = num == 2 and all(by.get(k) is not None for k in range(2, 2 + len(extra)))
        _RWC_S["ok"] += ok
        return f"results={len(r)} supply_and_block_hex={num == 2}" + (f" price_age_h={ages}" if ages else "") + (f" owner_reads={len(own)}" if own else "")
    return fn


def _rwc_s_sol(raw):
    r = json.loads(raw)
    V = ((r.get("result") or {}).get("value") if isinstance(r, dict) else None) or []
    n = sum(1 for v in V if isinstance(v, dict) and str((((v.get("data") or {}).get("parsed") or {}).get("info") or {}).get("supply", "")).isdigit())
    _RWC_S["ok"] += n == 3
    return f"mint_accounts={len(V)} supply_numbers={n}/3"


def _rwc_s_apt(raw):
    r = json.loads(raw)
    ok = isinstance(r, list) and len(r) == 1 and isinstance(r[0], dict) and str((r[0].get("vec") or [""])[0]).isdigit()
    _RWC_S["ok"] += ok
    return f"view_supply_number={ok}"


def g_rwa_lancuch():
    for sid, url, kind, tok, extra in RWC_S:
        if kind == "sol":
            probe("rwa-chain", "sol_getMultipleAccounts_3mints", url, method="POST", extra_fn=_rwc_s_sol,
                  body={"jsonrpc": "2.0", "id": 0, "method": "getMultipleAccounts", "params": [tok, {"encoding": "jsonParsed"}]})
        elif kind == "apt":
            probe("rwa-chain", "apt_view_fa_supply", url, method="POST", extra_fn=_rwc_s_apt,
                  body={"function": "0x1::fungible_asset::supply", "type_arguments": ["0x1::fungible_asset::Metadata"], "arguments": [tok]})
        else:
            body = [{"jsonrpc": "2.0", "id": 0, "method": "eth_blockNumber", "params": []},
                    {"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": tok, "data": RWC_S_SUP}, "latest"]}]
            body += [{"jsonrpc": "2.0", "id": k, "method": "eth_call", "params": [{"to": a, "data": sel}, "latest"]} for k, (a, sel, _x) in enumerate(extra, start=2)]
            probe("rwa-chain", f"{sid}_batch_{len(body)}calls", url, method="POST", extra_fn=_rwc_s_evm(extra), body=body)
        time.sleep(0.3)
    ref = _RWC_S["ref"]
    with _print_lock:
        print(f"summary rwa-chain chains_ok={_RWC_S['ok']}/{len(RWC_S)} owner_match={sum(1 for o in _RWC_S['own'] if ref and o == ref)}/3", flush=True)


GROUPS.insert(GROUPS.index(g_nasdaq), g_rwa_lancuch)   # v150: przed g_nasdaq (test v127: g_nasdaq zostaje ostatnia)


# ===================== v169: tokenizowane aktywa — dane emitentów (BADANIE_RWA2.md, 05.10.2026) i JSE Top 40 =====================
# Czy publiczne adresy emitentów odpowiadają z serwera GitHub (USA) i czy kształt odpowiedzi jest taki jak z Polski. Tylko kod HTTP, rozmiar,
# czas i wyliczone liczby (mln USD / liczba pozycji / data) — nigdy treść. Wiersze „summary rwa-em …” i „summary jse …” trafiają do adnotacji.
RWAE_SEC = ("BCAP", "MI4", "ACRED", "VBILL", "STAC", "HLSCOPE", "BUIDL")
RWAE_CFG_Q = "{ tokens(limit: 500) { items { symbol decimals totalIssuance tokenPrice } } }"
RWAE_BACKED_Q = ("query R($page:Int!,$pageSize:Int!,$where:TokensWhereInput){ tokens(page:$page,pageSize:$pageSize,where:$where){ nodes{ symbol "
                 "proofOfReserves{ at sharesHeld{ quantity } } } page{ totalPages totalNodes } } }")
_RWAE = {}


def _rwae_f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _rwae_put(k, v):
    with _print_lock:
        _RWAE[k] = v
    return v


def _rwae_m(v):
    return "-" if v is None else f"{v / 1e6:.1f}"


def _rwae_spiko_cls(raw):
    j = json.loads(raw)
    return f"classes={_rwae_put('spiko_cls', len(j) if isinstance(j, list) else -1)}"


def _rwae_spiko_tot(raw):
    j = json.loads(raw)
    a = (j.get("totalAssets") or {}) if isinstance(j, dict) else {}
    nav = (((j.get("netAssetValue") or {}).get("day") or "") if isinstance(j, dict) else "")[:10]
    _rwae_put("spiko", (_rwae_m(_rwae_f(a.get("value"))), a.get("currency"), nav))
    return f"M={_RWAE['spiko'][0]} {a.get('currency')} nav={nav}"


def _rwae_sec(sym):
    def f(raw):
        j = json.loads(raw)
        rows = j.get("data") if isinstance(j, dict) else None
        if not isinstance(rows, list):
            return _rwae_put("sec_" + sym, "bad")
        s = sum(_rwae_f(r.get("aum")) or 0 for r in rows if isinstance(r, dict))
        ds = [int(r["date"]) for r in rows if isinstance(r, dict) and str(r.get("date", "")).isdigit()]
        d = dt.datetime.fromtimestamp(max(ds) / 1e9, dt.timezone.utc).strftime("%m-%dT%H:%M") if ds else "-"
        return _rwae_put("sec_" + sym, f"{_rwae_m(s)}M/{len(rows)}ch@{d}")
    return f


def _rwae_hastra(raw):
    j = json.loads(raw)
    v = sum(_rwae_f((j.get(k) or {}).get("vaulted_wylds")) or 0 for k in ("prime_card", "auto_card", "smb_card")) if isinstance(j, dict) else None
    return _rwae_put("hastra", f"{_rwae_m(v)}M@{str((j or {}).get('timestamp', '-'))[5:16]}")


def _rwae_oe(raw):
    j = json.loads(raw)
    v = _rwae_f(j.get("tvl")) if isinstance(j, dict) else None
    at = (((j.get("liveVault") or {}).get("updatedAt")) or "-") if isinstance(j, dict) else "-"
    return _rwae_put("openeden", f"{_rwae_m(v)}M@{str(at)[5:16]}")


def _rwae_md(raw):
    j = json.loads(raw)
    d = j.get("data") if isinstance(j, dict) else None
    v = _rwae_f((d or {}).get("token_total_supply")) if isinstance(d, dict) else None
    return _rwae_put("xaum", f"{v:.0f}oz" if v else "-")


def _rwae_cfg(raw):
    j = json.loads(raw)
    it = (((j.get("data") or {}).get("tokens") or {}).get("items")) if isinstance(j, dict) else None
    if not isinstance(it, list):
        return _rwae_put("cfg", "bad")
    v = 0.0
    for t in it:
        try:
            if not str(t.get("symbol", "")).startswith("de"):
                v += int(t["totalIssuance"]) / 10 ** int(t["decimals"]) * int(t["tokenPrice"]) / 1e18
        except (KeyError, TypeError, ValueError):
            pass
    return _rwae_put("cfg", f"{_rwae_m(v)}M/{len(it)}t")


def _rwae_ondo(raw):
    s = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    return _rwae_put("ondo", f"assetsData={'assetsData' in s} gmTvl={'gmTvl' in s} kB={len(raw) // 1024}")


def _rwae_backed(raw):
    j = json.loads(raw)
    t = ((j.get("data") or {}).get("tokens")) if isinstance(j, dict) else None
    n = len((t or {}).get("nodes") or []) if isinstance(t, dict) else -1
    pg = ((t or {}).get("page") or {}) if isinstance(t, dict) else {}
    return _rwae_put("backed", f"nodes={n} pages={pg.get('totalPages', '-')}")


def _rwae_jse(lab):
    def f(raw):
        j = json.loads(raw)
        n = len(j) if isinstance(j, list) else len((j or {}).get("historical") or []) if isinstance(j, dict) else -1
        return _rwae_put("jse_" + lab, f"rows={n}")
    return f


def g_rwa_emitenci():
    probe("rwa-em", "spiko_share-classes", "https://public-api.spiko.io/share-classes", extra_fn=_rwae_spiko_cls)
    time.sleep(0.3)
    probe("rwa-em", "spiko_EUTBL_totals", "https://public-api.spiko.io/share-classes/EUTBL/totals", extra_fn=_rwae_spiko_tot)
    for sym in RWAE_SEC:
        time.sleep(0.3)
        probe("rwa-em", f"sec_{sym}", f"https://public-feed.securitize.io/asset-stats?symbol={sym}", extra_fn=_rwae_sec(sym))
    probe("rwa-em", "hastra_por", "https://hastra.io/hastra-pulse/public/api/v1/por", extra_fn=_rwae_hastra)
    probe("rwa-em", "openeden_aggregates", "https://prod-gw.openeden.com/v3/vault/aggregates", extra_fn=_rwae_oe)
    probe("rwa-em", "matrixdock_xaum", "https://www.matrixdock.com/rwa/anon/website/api/v1/stats/total?symbol=XAUM", extra_fn=_rwae_md)
    probe("rwa-em", "centrifuge_graphql", "https://api.centrifuge.io", method="POST", body={"query": RWAE_CFG_Q}, extra_fn=_rwae_cfg)
    probe("rwa-em", "ondo_homepage", "https://ondo.finance/", extra_fn=_rwae_ondo)
    probe("rwa-em", "backed_graphql", "https://api.backed.fi/graphql", method="POST", extra_fn=_rwae_backed,
          body={"query": RWAE_BACKED_Q, "variables": {"page": 1, "pageSize": 200, "where": {"businessLine": {"equals": "xStocks"}}}})
    with _print_lock:
        R = _RWAE
        sec = " ".join(f"{s}={R.get('sec_' + s, '-')}" for s in RWAE_SEC)
        print(f"summary rwa-em spiko={R.get('spiko_cls', '-')}cl EUTBL={'/'.join(map(str, R.get('spiko', ('-',))))} hastra={R.get('hastra', '-')} "
              f"oe={R.get('openeden', '-')} xaum={R.get('xaum', '-')} cfg={R.get('cfg', '-')}", flush=True)
        print(f"summary rwa-em2 {sec}", flush=True)
        print(f"summary rwa-em3 ondo[{R.get('ondo', '-')}] backed[{R.get('backed', '-')}]", flush=True)


def g_jse():
    frm = (_utc_today() - dt.timedelta(days=10)).isoformat()
    name, key = find_key("eodhd")
    if key:   # 1 zapytanie: limit planu 20 na dobę liczy też zbieracz
        probe("jse", "eodhd_J200.INDX", f"https://eodhd.com/api/eod/J200.INDX?fmt=json&from={frm}&api_token={key}", env_name=name, extra_fn=_rwae_jse("eod_J200"))
    else:
        skipped("jse", "eodhd")
    name, key = find_key("fmp")
    if key:
        for lab, sym in (("fmp_J200.JO", "%5EJ200.JO"), ("fmp_JTOPI.JO", "JTOPI.JO")):
            time.sleep(0.4)
            probe("jse", lab, f"https://financialmodelingprep.com/stable/historical-price-eod/light?symbol={sym}&apikey={key}", env_name=name, extra_fn=_rwae_jse(lab))
    else:
        skipped("jse", "fmp")
    with _print_lock:
        print("summary jse " + " ".join(f"{k[4:]}={v}" for k, v in sorted(_RWAE.items()) if k.startswith("jse_")), flush=True)


GROUPS.insert(GROUPS.index(g_nasdaq), g_rwa_emitenci)   # v169: przed g_nasdaq (test v127: g_nasdaq zostaje ostatnia)
GROUPS.insert(GROUPS.index(g_nasdaq), g_jse)


# v272p (07.10.2026): pokrycie indeksów w planach z kluczem, które właściciel już ma (FMP, Massive). Plan bezpłatny EODHD (20 zapytań na dobę)
# nie wystarcza na 22 indeksy strony: co dzień 2–3 indeksy (06.10 m.in. WIG20 i trzy indeksy USA) dostają sesję dopiero po północy UTC.
# Czy FMP albo Massive dają dzienne zamknięcia tych indeksów? Wynik: HTTP, liczba wierszy, najnowsza data i różnica zamknięcia względem pliku
# strony (indeksy.json, te same dni; ostatni wspólny dzień i największa różnica) — nigdy wartości, adresy ani klucze. FMP: lista indeksów
# + 1 zapytanie na kod (plan 250 na dobę); Massive: 3 zapytania z przerwą 13 s (plan 5 na minutę). Bez zapytań z dobowego limitu EODHD.
IXK_FMP = (("GSPC", "%5EGSPC"), ("IXIC", "%5EIXIC"), ("DJI", "%5EDJI"), ("N225", "%5EN225"), ("GSPTSE", "%5EGSPTSE"), ("BVSP", "%5EBVSP"),
           ("MXX", "%5EMXX"), ("GDAXI", "%5EGDAXI"), ("FCHI", "%5EFCHI"), ("IBEX", "%5EIBEX"), ("AEX", "%5EAEX"), ("SSMI", "%5ESSMI"),
           ("OMXS30", "%5EOMX"), ("WIG20", "WIG20.WA"), ("WIG20", "%5EWIG20"), ("TA125", "%5ETA125.TA"), ("XU100", "XU100.IS"), ("HSI", "%5EHSI"),
           ("SSEC", "000001.SS"), ("BSESN", "%5EBSESN"), ("AXJO", "%5EAXJO"), ("JKSE", "%5EJKSE"), ("KS11", "%5EKS11"))
IXK_MASSIVE = (("GSPC", "I:SPX"), ("IXIC", "I:COMP"), ("DJI", "I:DJI"))
IXK_SITE = "https://capitalflowai-app.github.io/data/indeksy.json"


def _ixk_site():
    """Serie indeksów z pliku strony (publiczny, bez klucza) → {kod: {dzień: zamknięcie}}; błąd = {} (porównanie „nocommon”)."""
    st, raw, _, _ = http(IXK_SITE)
    try:
        ix = (json.loads(raw).get("ix") or {}) if st == 200 and raw else {}
        return {k: {r[0]: r[1] for r in (v.get("d") or []) if isinstance(r, list) and len(r) == 2} for k, v in ix.items() if isinstance(v, dict)}
    except Exception:
        return {}


def _ixk_rows(raw, kind):
    """Odpowiedź → [(dzień, zamknięcie)] rosnąco: FMP — lista {date, price|close}; Massive — {results: [{t (ms), c}]}."""
    j = json.loads(raw)
    if kind == "fmp":
        rows = [(str(r.get("date"))[:10], r.get("price", r.get("close"))) for r in j if isinstance(r, dict)] if isinstance(j, list) else []
    else:
        res = j.get("results") if isinstance(j, dict) else None
        rows = [(dt.datetime.fromtimestamp(r["t"] / 1000, dt.timezone.utc).date().isoformat(), r.get("c"))
                for r in (res if isinstance(res, list) else []) if isinstance(r, dict) and isinstance(r.get("t"), (int, float))]
    return sorted((d, float(v)) for d, v in rows if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0)


def _ixk_res(st, raw, ref, kind):
    """Wynik jednego kodu: 'HTTP/r<wiersze>/<najnowszy MM-DD>/d<różnica % ostatniego wspólnego dnia>@<dzień>/m<największa |różnica| %>'."""
    if st != 200 or not raw:
        return str(st if st is not None else "ERR")
    try:
        rows = _ixk_rows(raw, kind)
    except Exception as e:  # noqa
        return f"200/{type(e).__name__}"
    if not rows:
        return "200/r0"
    s = f"200/r{len(rows)}/{rows[-1][0][5:]}"
    com = [(d, v, ref[d]) for d, v in rows if isinstance(ref, dict) and isinstance(ref.get(d), (int, float)) and ref[d] > 0]
    if not com:
        return s + "/nocommon"
    dd = [(v / r - 1) * 100 for _, v, r in com]
    return s + f"/d{dd[-1]:+.2f}@{com[-1][0][5:]}/m{max(abs(x) for x in dd):.2f}"


def g_ix_fmp():
    name, key = find_key("fmp")
    if not key:
        skipped("fmp", "index coverage")
        return
    ref = _ixk_site()
    b = "https://financialmodelingprep.com/stable"
    frm = (_utc_today() - dt.timedelta(days=12)).isoformat()
    st, raw = probe("fmp", "index_list", f"{b}/index-list?apikey={key}", env_name=name)
    lst = "-"
    if st == 200 and raw:
        try:
            have = {str(r.get("symbol")) for r in json.loads(raw) if isinstance(r, dict)}
            lst = f"n={len(have)} has=" + ",".join(c for c, s in IXK_FMP if urllib.parse.unquote(s) in have)
        except Exception as e:  # noqa
            lst = type(e).__name__
    out = []
    for code, sym in IXK_FMP:
        time.sleep(0.3)
        lab = urllib.parse.unquote(sym)
        st, raw = probe("fmp", f"ix_{code}_{lab}", f"{b}/historical-price-eod/light?symbol={sym}&from={frm}&apikey={key}", env_name=name)
        out.append(f"{code}:{lab}=" + _ixk_res(st, raw, ref.get(code), "fmp"))
    with _print_lock:
        print(f"summary ix-fmp-list {lst} site_codes={len(ref)}", flush=True)
        print("summary ix-fmp " + " ".join(out), flush=True)


def g_ix_massive():
    name, key = find_key("massive")
    if not key:
        skipped("massive", "index aggregates")
        return
    ref = _ixk_site()
    hdr = {"Authorization": "Bearer " + key}
    frm, to = (_utc_today() - dt.timedelta(days=12)).isoformat(), _utc_today().isoformat()
    out = []
    for i, (code, sym) in enumerate(IXK_MASSIVE):
        if i:
            time.sleep(13)   # plan bezpłatny: 5 zapytań na minutę (zbieracz pyta Massive 4 razy na dobę)
        st, raw = probe("massive", f"ix_{code}_{sym}", f"https://api.massive.com/v2/aggs/ticker/{sym}/range/1/day/{frm}/{to}?adjusted=true&sort=asc&limit=50",
                        env_name=name, headers=hdr)
        out.append(f"{code}:{sym}=" + _ixk_res(st, raw, ref.get(code), "massive"))
    with _print_lock:
        print("summary ix-massive " + " ".join(out), flush=True)


GROUPS.insert(GROUPS.index(g_nasdaq), g_ix_fmp)
GROUPS.insert(GROUPS.index(g_nasdaq), g_ix_massive)


# v288p (07.10.2026): JSE Top 40 (RPA) — jedyny indeks strony bez notowań (EODHD: pusta odpowiedź od 03.10; w GLOBAL „—” przy RPA). Czy FMP
# (klucz właściciela, 250 zapytań na dobę) ma indeks RPA? Lista indeksów FMP: kody i nazwy z RPA (bez wartości), potem do 4 kodów — HTTP,
# liczba wierszy z 12 dni i najnowsza data (nigdy wartości). Bez zapytań z dobowego limitu EODHD.
JSE_FMP_DOM = ("%5EJ200.JO", "%5EJ203.JO", "%5EJTOPI.JO", "%5EJALSH.JO")
JSE_RE = r"JSE|South Africa|Johannesburg|Top 40|All Share"


def _jse_res(st, raw):
    """HTTP i dla 200: liczba wierszy i najnowsza data (MM-DD) — bez wartości."""
    if st != 200 or not raw:
        return str(st)
    try:
        j = json.loads(raw)
        rows = j if isinstance(j, list) else (j or {}).get("historical") or [] if isinstance(j, dict) else []
        ds = sorted(str(r.get("date"))[:10] for r in rows if isinstance(r, dict) and r.get("date"))
        return f"200/r{len(rows)}" + (f"/{ds[-1][5:]}" if ds else "")
    except Exception as e:  # noqa
        return f"200/{type(e).__name__}"


def g_jse2():
    import re
    name, key = find_key("fmp")
    if not key:
        skipped("fmp", "jse")
        return
    b = "https://financialmodelingprep.com/stable"
    frm = (_utc_today() - dt.timedelta(days=12)).isoformat()
    st, raw = probe("fmp", "index_list_jse", f"{b}/index-list?apikey={key}", env_name=name)
    zn, lst = [], str(st)
    if st == 200 and raw:
        try:
            L = [r for r in json.loads(raw) if isinstance(r, dict)]
            for r in L:
                s, n, c = str(r.get("symbol") or ""), str(r.get("name") or ""), str(r.get("currency") or "")
                if s.upper().endswith(".JO") or c.upper() == "ZAR" or re.search(JSE_RE, n, re.I):
                    zn.append(f"{s[:16]}|{n[:36]}|{str(r.get('exchange') or '')[:8]}|{c[:4]}")
            lst = f"n={len(L)} rpa={len(zn)}"
        except Exception as e:  # noqa
            lst = type(e).__name__
    kody = [urllib.parse.quote(x.split("|")[0]) for x in zn[:4]]
    for s in JSE_FMP_DOM:
        if s not in kody and len(kody) < 4:
            kody.append(s)
    out = []
    for sym in kody[:4]:
        time.sleep(0.3)
        lab = urllib.parse.unquote(sym)
        st, raw = probe("fmp", f"jse_{lab}", f"{b}/historical-price-eod/light?symbol={sym}&from={frm}&apikey={key}", env_name=name)
        out.append(f"{lab}=" + _jse_res(st, raw))
    with _print_lock:
        print(f"summary jse2-list {lst} " + "; ".join(zn[:12]), flush=True)
        print("summary jse2 " + " ".join(out), flush=True)


GROUPS.insert(GROUPS.index(g_nasdaq), g_jse2)


# ===================== v294p: SUROWCE — etap 0: sonda źródeł z serwerów GitHub (USA) =====================
# Dział SUROWCE (projekt: surowce/wyniki_badania.json, 07.10.2026). Czy źródła cen, zapasów i pozycji surowców odpowiadają z serwera GitHub
# (USA) i co dają plany z kluczem właściciela: Twelve Data Basic (czy towary są w planie — badacze się różnią), FMP darmowy, EIA, Tiingo,
# CoinGecko Demo. Wynik: kod HTTP, rozmiar, czas, najnowsza data, liczba wierszy i kształt; błąd jako klasa (plan / limit / key / nf) — nigdy
# klucze, adresy, treść ani ceny. Wyjątek bez poziomu ceny: zmiana % dnia przy dwóch podejrzanych punktach (WTI 25.09, Brent 02.10) w Twelve
# Data, FMP i EIA — weryfikacja drugim źródłem (projekt, sonda 12). Limity tego przebiegu: Twelve Data 16 kredytów (paczki ≤ 7 co 61 s — limit
# planu 8 na minutę dzieli zbieracz; paczka odrzucona limitem minutowym: jedna powtórka), FMP 19 zapytań (z 250 na dobę), EIA 6, Tiingo 8,
# CoinGecko 1. Duże pliki (JODI 5,5 MB, Weekly Oil Bulletin 4,5 MB): tylko 64 KB / 4 KB (nagłówek Range), rozmiar z nagłówków. Ochrona przed
# botami (403, captcha, Cloudflare): notatka „blocked:…”, bez obchodzenia. Chainlink: ten sam węzeł co XAU/USD w RWA (bez nowego węzła).
# Każda sonda: wiersz „summary su-<grupa> <sonda> <HTTP> <rozmiar> <czas> <wynik>” — sondy.yml dzieli wiersze summary na kilka adnotacji.
import csv as _su_csv
import email.utils as _su_eu
import re as _su_re

SU_HDR = {"User-Agent": "CapitalFlowAI-collector/1.0"}   # identyfikator zbieracza — ta sama prośba, którą wyśle później zbieracz
SU_W_OD = "2026-09-20"     # początek okna historii w zapytaniach z kluczem: weryfikacja WTI 25.09 i Brent 02.10
SU_TD = "https://api.twelvedata.com"
SU_TD_SYMS = ("XAU/USD", "XAG/USD", "XPT/USD", "XPD/USD", "HG1", "WTI/USD", "XBR/USD")
SU_TD_W = (("WTI/USD", "2026-09-25"), ("XBR/USD", "2026-10-02"))
SU_TD_PACZKA = 7           # kredyty w jednej minucie (plan Basic: 8 na minutę; 1 zostaje) — 1 symbol = 1 kredyt
SU_FMP = "https://financialmodelingprep.com/stable"
SU_FMP_SYMS = ("BZUSD", "SIUSD", "CLUSD", "NGUSD", "GCUSD", "HGUSD", "ALIUSD", "PLUSD", "PAUSD")
SU_FMP_W = (("CLUSD", "2026-09-25"), ("BZUSD", "2026-10-02"))
SU_FMP_EXTRA = r"TTF|Dutch|Coal|Uranium|Iron|Lithium|Cobalt|Gasoil|Heating"
SU_EIA = "https://api.eia.gov/v2/"
SU_EIA_W = (("RWTC", "2026-09-25"), ("RBRTE", "2026-10-02"))
SU_STEO = ("COPR_OPEC", "COPR_OPECPLUS", "COPC_OPEC", "PAPR_WORLD", "BREPUUS")
SU_WSTK = ("WCESTUS1", "WCSSTUS1", "WGTSTUS1", "WDISTUS1", "WKJSTUS1", "W_EPC0_SAX_YCUOK_MBBL")
SU_SNDW = ("WCRFPUS2", "WPULEUS3", "WCREXUS2", "WRPUPUS2")
SU_TIINGO = ("WEAT", "CORN", "SOYB", "DBA", "DBC", "GSG", "USO", "CPER")
SU_JODI = "https://www.jodidata.org/_resources/files/downloads/oil-data/annual-csv/primary/primaryyear2026.csv"
SU_WOB = ("https://energy.ec.europa.eu/document/download/906e60ca-8b6a-44e7-8589-652854d2fd3f_en"
          "?filename=Weekly_Oil_Bulletin_Prices_History_maticni_4web.xlsx")
SU_IMF30 = ("https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.RES/PCPS/+/"
            "G001.PGOLD+PSILVER+PPLAT+PPALLA+PCOPP+PALUM+PNICK+PZINC+PIORECR+PURAN.USD.M?lastNObservations=3")
SU_IMF21 = ("https://api.imf.org/external/sdmx/2.1/data/IMF.RES,PCPS/"
            "G001.POILBRE+POILDUB+POILWTI+PNGASEU+PNGASUS+PNGASJP+PCOALAU+PURAN.USD.M?startPeriod=2026-01")
SU_WB_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
SU_CL = (("xag", "0x379589227b15F1a12195D3f2d90bBc9F31f95235"), ("paxg", "0x9944D86CEB9160aF5C5feB251FD671923323f8C3"))
SU_SOC_CODES = ("023651", "111659", "022651", "06765T")
SU_MON = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def _su_sz(n):
    n = n or 0
    return f"{n / 1e6:.1f}MB" if n >= 1_000_000 else f"{n / 1e3:.1f}KB"


def _su_out(line):
    with _print_lock:
        print(_scrub(line), flush=True)


def _su_num(v):
    if isinstance(v, bool):
        return False
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return f == f and 0 < f < float("inf")


def _su_errcls(raw):
    """Treść odpowiedzi z błędem → klasa: html (strona błędu) / limit / plan / key / nf / '-'. Sam komunikat nigdy nie jest wypisywany
    (może zawierać adres)."""
    b = raw if isinstance(raw, (bytes, bytearray)) else str(raw or "").encode()
    s = bytes(b[:4000]).decode("utf-8", "replace").lower()
    if s.lstrip().startswith("<") or "<html" in s[:1000]:
        return "html"
    for cls, words in (("limit", ("credits", "limit reach", "rate limit", "too many", "limit exceeded", "exceeded")),
                       ("plan", ("premium", "plan", "upgrade", "subscription", "exclusive", "restricted")),
                       ("key", ("api key", "apikey", "api_key", "token", "unauthorized", "not authorized", "invalid key")),
                       ("nf", ("not found", "invalid symbol", "no data", "symbol"))):
        if any(w in s for w in words):
            return cls
    return "-"


def _su_blocked(raw):
    """Ochrona przed botami albo odmowa → 'cloudflare' / 'captcha' / 'denied' / None (tylko notatka, bez obchodzenia)."""
    b = bytes((raw or b"")[:60000]).lower()
    if b"just a moment" in b or b"cf-chl" in b or b"challenge-platform" in b or b"attention required" in b:
        return "cloudflare"
    if b"captcha" in b:
        return "captcha"
    if b"access denied" in b or b"request rejected" in b:
        return "denied"
    return None


def _su_info(st, raw, err, fn):
    """Opis wyniku: dla 2xx — fn(raw) (daty, wiersze, kształt); pusty opis albo wyjątek przy ochronie przed botami → 'blocked:…';
    inne kody — 'blocked:…' albo klasa błędu. Nigdy treść ani adres."""
    if err:
        return err
    if st in (200, 206) and raw is not None:
        try:
            info = fn(raw) if fn else shape(raw)
        except Exception as e:  # noqa
            info = "parse:" + type(e).__name__
        k = _su_blocked(raw) if (not info or info.startswith("parse:")) else None
        return "blocked:" + k if k else (info or "-")
    k = _su_blocked(raw)
    return "blocked:" + k if k else _su_errcls(raw)


def _su(grp, label, url, fn=None, headers=None, env_name=None, method="GET", body=None, line=True):
    """Jedno zapytanie: wiersz sondy (report) i — gdy line — wiersz „summary su-<grp> <label> <HTTP> <rozmiar> <ms>ms <wynik>”."""
    st, raw, ms, err = http(url, method, body, SU_HDR if headers is None else headers)
    info = _su_info(st, raw, err, fn)
    report("su-" + grp, env_name, label, st, raw, ms, None, info)
    if line:
        _su_out(f"summary su-{grp} {label} {st if st is not None else 'ERR'} {_su_sz(len(raw) if raw else 0)} {ms}ms {info}")
    return st, raw, info


def _su_part(url, n=65536, tail=False, headers=None):
    """Tylko część dużego pliku: nagłówek Range (pierwsze albo ostatnie n bajtów); serwer bez Range — i tak najwyżej n bajtów.
    → (status, rozmiar pliku z Content-Range / Content-Length albo None, Last-Modified 'RRRR-MM-DD' albo None, bajty, ms, błąd)."""
    left = _remaining()
    if left < 2.0:
        return None, None, None, None, 0, "SkippedDeadline"
    h = {"User-Agent": SU_HDR["User-Agent"], "Accept": "*/*", "Range": f"bytes=-{n}" if tail else f"bytes=0-{n - 1}"}
    h.update(headers or {})
    t = time.monotonic()
    st = tot = lm = raw = err = hd = None
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=min(REQ_TIMEOUT, left), context=SSL_CTX) as r:
            st, hd = r.status, r.headers
            raw = r.read(n)
    except urllib.error.HTTPError as e:
        st, hd = e.code, e.headers
    except Exception as e:  # noqa
        reason = getattr(e, "reason", None)
        err = type(e).__name__ + ("/" + type(reason).__name__ if reason is not None and not isinstance(reason, str) else "")
    if hd is not None:
        m = _su_re.search(r"/(\d+)\s*$", str(hd.get("Content-Range") or ""))
        cl = str(hd.get("Content-Length") or "")
        tot = int(m.group(1)) if m else (int(cl) if st == 200 and cl.isdigit() else None)
        try:
            lm = _su_eu.parsedate_to_datetime(hd.get("Last-Modified")).date().isoformat() if hd.get("Last-Modified") else None
        except Exception:  # noqa
            lm = None
    return st, tot, lm, raw, int((time.monotonic() - t) * 1000), err


def _su_big(grp, label, url, n, tail, fn):
    st, tot, lm, raw, ms, err = _su_part(url, n, tail)
    rng = "range" if st == 206 else ("norange" if st == 200 else "-")
    info = f"total={_su_sz(tot) if tot else '-'} lm={lm or '-'} {rng} " + _su_info(st, raw, err, fn)
    report("su-" + grp, None, label, st, raw, ms, None, info)
    _su_out(f"summary su-{grp} {label} {st if st is not None else 'ERR'} {_su_sz(len(raw) if raw else 0)} {ms}ms {info}")


# --------------------------------------------------------------------------- daty i proste kształty (bez wartości)

def _su_date(s):
    """Tekst daty (RRRR-MM-DD, RRRR/MM/DD, RRRR-Mon-DD, MM/DD/RRRR, M/D/RR, DD-Mon-RRRR, DD Mon RRRR, Mon DD, RRRR) → dt.date albo None."""
    s = str(s or "").strip()
    try:
        m = _su_re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
        if m:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        m = _su_re.match(r"^(\d{4})-([A-Za-z]{3})-(\d{1,2})", s)
        if m and m.group(2).lower() in SU_MON:
            return dt.date(int(m.group(1)), SU_MON[m.group(2).lower()], int(m.group(3)))
        m = _su_re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?!\d)", s)
        if m:
            y = int(m.group(3))
            return dt.date(y + 2000 if y < 100 else y, int(m.group(1)), int(m.group(2)))
        m = _su_re.match(r"^(\d{1,2})[- ]([A-Za-z]{3})[a-z]*[- ,]+(\d{4})", s)
        if m and m.group(2).lower() in SU_MON:
            return dt.date(int(m.group(3)), SU_MON[m.group(2).lower()], int(m.group(1)))
        m = _su_re.match(r"^([A-Za-z]{3})[a-z]*\.? (\d{1,2}),? (\d{4})", s)
        if m and m.group(1).lower() in SU_MON:
            return dt.date(int(m.group(3)), SU_MON[m.group(1).lower()], int(m.group(2)))
    except ValueError:
        return None
    return None


def _su_max(ds):
    """Najnowsza data nie później niż jutro (dt.date albo tekst) → 'RRRR-MM-DD' albo '-'."""
    lim = _utc_today() + dt.timedelta(days=1)
    xs = [d if isinstance(d, dt.date) else _su_date(d) for d in ds]
    xs = [d for d in xs if d and d <= lim]
    return max(xs).isoformat() if xs else "-"


def _su_iso(text):
    return _su_re.findall(r"(?<!\d)(20\d\d-\d\d-\d\d)(?!\d)", text)


def _su_txt(raw):
    """HTML → tekst bez znaczników, skryptów i stylów (jedna spacja między słowami)."""
    s = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    s = _su_re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", s)
    s = _su_re.sub(r"<[^>]+>", " ", s).replace("&nbsp;", " ").replace("&#160;", " ")
    return " ".join(s.split())


def _su_walk(o, out, keys=("date", "period"), depth=0):
    """Daty RRRR-MM-DD spod kluczy `keys` w dowolnym zagnieżdżeniu JSON (do 8 poziomów, najwyżej 50 000 dat)."""
    if depth > 8 or len(out) > 50000:
        return
    if isinstance(o, dict):
        for k, v in o.items():
            if k in keys and isinstance(v, str) and _su_re.match(r"\d{4}-\d{2}-\d{2}", v):
                out.append(v[:10])
            elif isinstance(v, (dict, list)):
                _su_walk(v, out, keys, depth + 1)
    elif isinstance(o, list):
        for v in o:
            if isinstance(v, (dict, list)):
                _su_walk(v, out, keys, depth + 1)


def _su_pct(rows, day):
    """[(dzień, liczba)] → zmiana % dnia `day` wobec poprzedniego dnia w danych, np. '+18.0%/10-01' (sama zmiana — bez poziomu ceny);
    brak dnia → 'brak'."""
    r = sorted((str(d)[:10], float(v)) for d, v in rows if _su_num(v))
    for i, (d, v) in enumerate(r):
        if d == day:
            return f"{(v / r[i - 1][1] - 1) * 100:+.1f}%/{r[i - 1][0][5:]}" if i else "pierwszy"
    return "brak"


# --------------------------------------------------------------------------- (a) z kluczem: Twelve Data

def _su_td_list(raw):
    j = json.loads(raw)
    L = [x for x in ((j.get("data") if isinstance(j, dict) else j) or []) if isinstance(x, dict)]
    have = {str(x.get("symbol")) for x in L}
    miss = [s for s in SU_TD_SYMS if s not in have]
    return f"n={len(L)} has={len(SU_TD_SYMS) - len(miss)}/{len(SU_TD_SYMS)} miss={','.join(miss) or '-'}"


def _su_td_obj(j, syms):
    """Odpowiedź Twelve Data → {symbol: obiekt}; jeden symbol — obiekt na górze; błąd całego zapytania — ten sam dla wszystkich."""
    if not isinstance(j, dict):
        return {s: None for s in syms}
    if any(s in j for s in syms):
        return {s: j.get(s) for s in syms}
    return {s: j for s in syms}


def _su_td_err(o):
    """Błąd w treści (status 'error' / code + message) → kod i klasa komunikatu, np. '403plan'; poprawny obiekt → None."""
    if not isinstance(o, dict):
        return "shape"
    if o.get("status") == "error" or ("code" in o and "message" in o):
        return f"{o.get('code', '')}{_su_errcls(str(o.get('message', '')))}"
    return None


def _su_td_ts(o):
    """time_series jednego symbolu → ('ok/r<wiersze>/<najnowszy MM-DD>' albo kod i klasa błędu, [(dzień, zamknięcie)])."""
    e = _su_td_err(o)
    if e:
        return e, []
    rows = [(str(x.get("datetime"))[:10], x.get("close")) for x in (o.get("values") or []) if isinstance(x, dict)]
    ds = sorted(d for d, _ in rows)
    return f"ok/r{len(rows)}" + (f"/{ds[-1][5:]}" if ds else ""), rows


def _su_td_q(o, now):
    """quote jednego symbolu → 'ok/<dzień świecy MM-DD>/c<początek świecy HH:MM UTC>/lag<min od ostatniego notowania>m/o<rynek otwarty>'."""
    e = _su_td_err(o)
    if e:
        return e
    ts, lq = o.get("timestamp"), o.get("last_quote_at")
    lq = lq if isinstance(lq, (int, float)) and not isinstance(lq, bool) else ts
    c = dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%H:%M") if isinstance(ts, (int, float)) and not isinstance(ts, bool) else "-"
    lag = f"lag{int((now - lq) / 60)}m" if isinstance(lq, (int, float)) and not isinstance(lq, bool) else "lag-"
    return f"ok/{str(o.get('datetime') or '-')[5:10]}/c{c}/{lag}/o{int(bool(o.get('is_market_open')))}"


def _su_td_url(job, key):
    s = ",".join(SU_TD_SYMS)
    if job == "ts":
        return f"{SU_TD}/time_series?symbol={s}&interval=1day&start_date={SU_W_OD}&apikey={key}"
    if job == "q":
        return f"{SU_TD}/quote?symbol={s}&apikey={key}"
    if job == "hist":
        return f"{SU_TD}/time_series?symbol=XAU/USD&interval=1day&outputsize=5000&apikey={key}"
    return f"{SU_TD}/api_usage?apikey={key}"


def _su_td_job(job, key, name, W):
    """Jedno zapytanie Twelve Data; → True, gdy całą paczkę odrzucił limit minutowy (bez zużycia kredytów — do powtórki)."""
    st, raw, ms, err = http(_su_td_url(job, key), "GET", None, SU_HDR)
    try:
        j = json.loads(raw) if raw else None
    except Exception:  # noqa
        j = None
    lim = st == 429 or (isinstance(j, dict) and not any(s in j for s in SU_TD_SYMS)
                        and (j.get("code") == 429 or "credits" in str(j.get("message", "")).lower()))
    if err:
        info = err
    elif lim:
        info = "429limit"
    elif not isinstance(j, dict):
        info = _su_errcls(raw) if st != 200 else "non-json"
    elif job in ("ts", "q"):
        objs, parts = _su_td_obj(j, SU_TD_SYMS), []
        for s in SU_TD_SYMS:
            if job == "ts":
                r, rows = _su_td_ts(objs.get(s))
                if rows:
                    W[s] = rows
            else:
                r = _su_td_q(objs.get(s), time.time())
            parts.append(f"{s}={r}")
        info = " ".join(parts)
    elif job == "hist":
        r, rows = _su_td_ts(_su_td_obj(j, ("XAU/USD",)).get("XAU/USD"))
        ds = sorted(d for d, _ in rows)
        info = f"XAU/USD={r}" + (f"/od={ds[0]}" if ds else "")
    else:
        info = _su_td_err(j) if ("code" in j and "message" in j) else (
            f"plan={str(j.get('plan_category', '-'))[:16]} min={j.get('current_usage', '-')}/{j.get('plan_limit', '-')} "
            f"day={j.get('daily_usage', '-')}/{j.get('plan_daily_limit', '-')}")
    report("su-td", name, job, st, raw, ms, None, info)
    _su_out(f"summary su-td {job} {st if st is not None else 'ERR'} {_su_sz(len(raw) if raw else 0)} {ms}ms {info}")
    return lim


def g_su_td():
    """Twelve Data (plan Basic): czy towary są w planie (time_series i quote 7 symboli), opóźnienie notowań, początek świecy dziennej,
    od kiedy jest historia złota (outputsize 5000), zużycie planu (api_usage). Paczki ≤ 7 kredytów co 61 s; 16 kredytów w sumie."""
    _su("td", "commodities_list_nokey", SU_TD + "/commodities", fn=_su_td_list)   # lista bez klucza — bez kredytów
    name, key = find_key("twelvedata")
    if not key:
        skipped("su-td", "time_series/quote/api_usage")
        return
    jobs = [("ts", len(SU_TD_SYMS)), ("q", len(SU_TD_SYMS)), ("hist", 1), ("usage", 1)]
    W, again, sent, first = {}, set(), 0, True
    while jobs:
        if not first:
            time.sleep(61)   # nowa minuta limitu planu (8 kredytów na minutę, część dla zbieracza)
        first = False
        if _remaining() < 15:
            for j, _ in jobs:
                skipped("su-td", j, "global deadline")
            break
        cap, now_jobs = SU_TD_PACZKA, []
        while jobs and (jobs[0][1] <= cap or not now_jobs):
            cap -= jobs[0][1]
            now_jobs.append(jobs.pop(0))
        for job, cost in now_jobs:
            if _su_td_job(job, key, name, W):
                if job not in again:
                    again.add(job)
                    jobs.append((job, cost))
            else:
                sent += cost
    _su_out("summary su-td-w " + " ".join(f"{s}@{d[5:]}=" + (_su_pct(W[s], d) if W.get(s) else "brak") for s, d in SU_TD_W))
    _su_out(f"summary su-td-credits sent={sent} retries={len(again)}")


# --------------------------------------------------------------------------- (a) z kluczem: FMP

def _su_fmp_list(raw):
    j = json.loads(raw)
    if not isinstance(j, list):
        return "err-" + _su_errcls(raw)
    L = [r for r in j if isinstance(r, dict)]
    have = {str(r.get("symbol")) for r in L}
    ex = [str(r.get("symbol"))[:10] for r in L if _su_re.search(SU_FMP_EXTRA, str(r.get("name") or ""), _su_re.I)]
    miss = [s for s in SU_FMP_SYMS if s not in have]
    return (f"n={len(L)} has={len(SU_FMP_SYMS) - len(miss)}/{len(SU_FMP_SYMS)} miss={','.join(miss) or '-'} "
            f"extra={','.join(ex[:8]) or '-'}")


def _su_fmp_q(raw):
    j = json.loads(raw)
    if not isinstance(j, list):
        return "err-" + _su_errcls(raw)
    r = next((x for x in j if isinstance(x, dict)), None)
    if r is None:
        return "r0"
    t = r.get("timestamp")
    return f"lag{int((time.time() - t) / 60)}m" if isinstance(t, (int, float)) and not isinstance(t, bool) else "lag-"


def _su_fmp_eod(raw):
    j = json.loads(raw)
    if not isinstance(j, list):
        return "err-" + _su_errcls(raw)
    ds = sorted(str(r.get("date"))[:10] for r in j if isinstance(r, dict) and r.get("date"))
    return f"r{len(ds)}" + (f"/{ds[-1][5:]}" if ds else "")


def g_su_fmp():
    """FMP (plan darmowy, 250 zapytań na dobę dzielone ze zbieraczem): lista towarów, quote i dzienne zamknięcia 9 symboli — 19 zapytań."""
    name, key = find_key("fmp")
    if not key:
        skipped("su-fmp", "commodities-list/quote/eod")
        return
    _su("fmp", "commodities_list", f"{SU_FMP}/commodities-list?apikey={key}", fn=_su_fmp_list, env_name=name)
    q, e, W = [], [], {}
    for s in SU_FMP_SYMS:
        time.sleep(0.3)
        st, raw, info = _su("fmp", f"quote_{s}", f"{SU_FMP}/quote?symbol={s}&apikey={key}", fn=_su_fmp_q, env_name=name, line=False)
        q.append(f"{s}={st if st is not None else 'ERR'}/{info}")
        time.sleep(0.3)
        st, raw, info = _su("fmp", f"eod_{s}", f"{SU_FMP}/historical-price-eod/light?symbol={s}&from={SU_W_OD}&apikey={key}",
                            fn=_su_fmp_eod, env_name=name, line=False)
        e.append(f"{s}={st if st is not None else 'ERR'}/{info}")
        if st == 200 and raw:
            try:
                W[s] = [(str(r.get("date"))[:10], r.get("price", r.get("close"))) for r in json.loads(raw) if isinstance(r, dict)]
            except Exception:  # noqa
                pass
    _su_out("summary su-fmp-q " + " ".join(q))
    _su_out("summary su-fmp-eod " + " ".join(e))
    _su_out("summary su-fmp-w " + " ".join(f"{s}@{d[5:]}=" + (_su_pct(W[s], d) if W.get(s) else "brak") for s, d in SU_FMP_W))


# --------------------------------------------------------------------------- (a) z kluczem: EIA API v2

def _su_eia_url(route, key, params):
    return SU_EIA + route + "/data/?" + urllib.parse.urlencode([("api_key", key)] + list(params))


def _su_eia_info(field, expect=()):
    def f(raw):
        j = json.loads(raw)
        if not isinstance(j, dict) or j.get("error"):
            return "err-" + _su_errcls(json.dumps(j.get("error") if isinstance(j, dict) else ""))
        r = j.get("response") or {}
        rows = [x for x in (r.get("data") or []) if isinstance(x, dict)]
        ser = {str(x.get(field)) for x in rows}
        ps = sorted(str(x.get("period")) for x in rows if x.get("period"))
        s = f"total={str(r.get('total', '-'))[:10]} r={len(rows)} ser={len(ser)}"
        if expect:   # ser=<znalezione z oczekiwanych>/<oczekiwane>
            miss = [x for x in expect if x not in ser]
            s = s.rsplit(" ser=", 1)[0] + f" ser={len(expect) - len(miss)}/{len(expect)}" + (f" miss={','.join(miss)}" if miss else "")
        if j.get("warning") or r.get("warnings"):
            s += " warn"
        return s + (f" {ps[0]}..{ps[-1]}" if ps else "")
    return f


def g_su_eia():
    """EIA API v2: ceny spot jednym zapytaniem (bez filtra serii, 5000 wierszy — czas i rozmiar), STEO (OPEC, OPEC+, moce, świat, Brent),
    zapasy tygodniowe, bilans tygodniowy, gaz w magazynach, Henry Hub — 6 zapytań."""
    name, key = find_key("eia")
    if not key:
        skipped("su-eia", "pri/spt, steo, wstk, sndw, stor/wkly, pri/fut")
        return
    desc = [("sort[0][column]", "period"), ("sort[0][direction]", "desc"), ("offset", "0")]
    st, raw, _ = _su("eia", "pri_spt_all_5000", _su_eia_url("petroleum/pri/spt", key, [("frequency", "daily"), ("data[0]", "value")] + desc
                                                             + [("length", "5000")]), fn=_su_eia_info("series"), env_name=name)
    W = {}
    if st == 200 and raw:
        try:
            for x in (json.loads(raw).get("response") or {}).get("data") or []:
                if isinstance(x, dict) and x.get("series") in dict(SU_EIA_W):
                    W.setdefault(x["series"], []).append((str(x.get("period"))[:10], x.get("value")))
        except Exception:  # noqa
            pass
    od = (_utc_today() - dt.timedelta(days=120)).strftime("%Y-%m")
    wk = [("frequency", "weekly"), ("data[0]", "value")]
    calls = (("steo_5", "steo", [("frequency", "monthly"), ("data[0]", "value")] + [("facets[seriesId][]", s) for s in SU_STEO]
              + [("start", od)] + desc + [("length", "500")], "seriesId", SU_STEO),
             ("stoc_wstk_6", "petroleum/stoc/wstk", wk + [("facets[series][]", s) for s in SU_WSTK] + desc + [("length", "60")], "series", SU_WSTK),
             ("sum_sndw_4", "petroleum/sum/sndw", wk + [("facets[series][]", s) for s in SU_SNDW] + desc + [("length", "40")], "series", SU_SNDW),
             ("ng_stor_wkly", "natural-gas/stor/wkly", wk + [("facets[series][]", "NW2_EPG0_SWO_R48_BCF")] + desc + [("length", "10")], "series",
              ("NW2_EPG0_SWO_R48_BCF",)),
             ("ng_pri_fut_hh", "natural-gas/pri/fut", [("frequency", "daily"), ("data[0]", "value"), ("facets[series][]", "RNGWHHD")] + desc
              + [("length", "10")], "series", ("RNGWHHD",)))
    for lab, route, params, field, exp in calls:
        time.sleep(0.3)
        _su("eia", lab, _su_eia_url(route, key, params), fn=_su_eia_info(field, exp), env_name=name)
    _su_out("summary su-eia-w " + " ".join(f"{s}@{d[5:]}=" + (_su_pct(W[s], d) if W.get(s) else "brak") for s, d in SU_EIA_W))


# --------------------------------------------------------------------------- (a) z kluczem: Tiingo, CoinGecko

def _su_tiingo_eod(raw):
    j = json.loads(raw)
    if not isinstance(j, list):
        return "err-" + _su_errcls(json.dumps(j))
    ds = sorted(str(r.get("date"))[:10] for r in j if isinstance(r, dict) and r.get("date"))
    return f"r{len(ds)}" + (f"/{ds[-1][5:]}" if ds else "")


def g_su_tiingo():
    """Tiingo (plan darmowy): dzienne zamknięcia 8 funduszy surowcowych z 10 dni — 8 zapytań (klucz tylko w nagłówku)."""
    name, key = find_key("tiingo")
    if not key:
        skipped("su-tiingo", "daily prices of 8 commodity funds")
        return
    hdr = {**SU_HDR, "Authorization": "Token " + key, "Content-Type": "application/json"}
    start = (_utc_today() - dt.timedelta(days=10)).isoformat()
    out = []
    for i, tk in enumerate(SU_TIINGO):
        if i:
            time.sleep(0.3)
        st, raw, info = _su("tiingo", f"eod_{tk}", f"https://api.tiingo.com/tiingo/daily/{tk}/prices?startDate={start}", fn=_su_tiingo_eod,
                            headers=hdr, env_name=name, line=False)
        out.append(f"{tk}={st if st is not None else 'ERR'}/{info}")
    _su_out("summary su-tiingo " + " ".join(out))


def _su_cg(raw):
    j = json.loads(raw)
    if not isinstance(j, dict):
        return "shape"
    out = []
    for cid in ("pax-gold", "tether-gold"):
        o = j.get(cid)
        if not isinstance(o, dict):
            out.append(f"{cid}=brak")
            continue
        t = o.get("last_updated_at")
        lag = f"lag{int((time.time() - t) / 60)}m" if isinstance(t, (int, float)) and not isinstance(t, bool) else "lag-"
        out.append(f"{cid}=ok/{lag}/mcap={'usd_market_cap' in o}")
    return " ".join(out)


def g_su_cg():
    """CoinGecko simple/price dla PAXG i XAUT — 1 zapytanie (klucz Demo w nagłówku, gdy jest; bez klucza — plan publiczny)."""
    name, key = find_key("coingecko")
    hdr = {**SU_HDR, "x-cg-demo-api-key": key} if key else None
    _su("cg", "simple_price_paxg_xaut" + ("" if key else "_nokey"),
        "https://api.coingecko.com/api/v3/simple/price?ids=pax-gold,tether-gold&vs_currencies=usd&include_market_cap=true&include_last_updated_at=true",
        fn=_su_cg, headers=hdr, env_name=name)


# --------------------------------------------------------------------------- (b) bez klucza: energia

def _su_table1(raw):
    t = raw.decode("utf-8-sig", "replace")
    L = [x for x in t.splitlines() if x.strip()]
    h = next(_su_csv.reader([L[0]])) if L else []
    ds = [d for d in (_su_date(c) for c in h) if d]
    return f"week={ds[0].isoformat() if ds else '-'} rows={max(0, len(L) - 1)}"


def _su_psw(raw):
    j = json.loads(raw)
    md = (j.get("metadata") or {}) if isinstance(j, dict) else {}
    ds = []
    _su_walk(j.get("data") if isinstance(j, dict) else j, ds)
    return f"rel={str(md.get('release_date') or '-')[:10]} newest={_su_max(ds)} n={len(ds)}"


def _su_wngsr(raw):
    j = json.loads(raw)
    ds = []
    _su_walk(j, ds, ("current_week", "report_date", "week_ending", "date", "period"))
    g = j if isinstance(j, dict) else {}
    return f"week={str(g.get('current_week') or '-')[:10]} rel={_su_date(g.get('release_date')) or '-'} newest={_su_max(ds)}"


def _su_prices(raw):
    s = _su_txt(raw)
    m = _su_re.findall(r"(\d{1,2}/\d{1,2}/\d{2,4})\s+Close", s)
    return f"close={_su_max(m)} tables={raw.count(b'summary=')}"


def _su_dnav(raw):
    """Strona historii EIA (wiersz = tydzień, 5 dni roboczych): najnowszy dzień z liczbą i liczba tygodni — bez wartości."""
    s = raw.decode("utf-8", "replace")
    rows = _su_re.findall(r"(\d{4})\s+([A-Z][a-z]{2})-\s*(\d{1,2})\s+to\s+[A-Z][a-z]{2}-\s*\d{1,2}\s*</td>(.*?)</tr>", s, _su_re.S)
    if not rows:
        return "weeks=0"
    y, mon, d, cells = rows[-1]
    vals = _su_re.findall(r"<td[^>]*>(.*?)</td>", cells, _su_re.S)
    idx = [i for i, c in enumerate(vals) if _su_re.search(r"\d", _su_re.sub(r"<[^>]+>|&nbsp;", "", c))]
    newest = (dt.date(int(y), SU_MON[mon.lower()], int(d)) + dt.timedelta(days=idx[-1])).isoformat() if idx and mon.lower() in SU_MON else "-"
    return f"weeks={len(rows)} newest={newest}"


def _su_acer(raw):
    t = raw.decode("latin-1")
    R = [r for r in _su_csv.reader(t.splitlines()) if r]
    if not R:
        return "rows=0"
    h = [c.strip().upper() for c in R[0]]
    bi = next((i for i, c in enumerate(h) if "BENCHMARK" in c), None)
    data = [r for r in R[1:] if _su_date(r[0])]
    if not data:
        return f"rows=0 cols={len(h)}"
    nw = max(data, key=lambda r: _su_date(r[0]))
    bm = "-" if bi is None else ("empty" if bi >= len(nw) or not nw[bi].strip() else "ok")
    return f"rows={len(data)} newest={_su_date(nw[0]).isoformat()} bm_newest={bm} cols={len(h)}"


def _su_jodi(raw):
    t = raw.decode("utf-8", "replace")
    ps = _su_re.findall(r",((?:19|20)\d\d-\d\d),", t)
    return f"lines={t.count(chr(10))} newest={max(ps) if ps else '-'}"


def _su_zipsig(raw):
    return f"zip={raw[:4] == b'PK' + bytes([3, 4])}"


def g_su_energia():
    """Energia bez klucza: pliki raportów tygodniowych EIA (przekierowania 302), strona cen dziennych, strony historii WTI i Brent,
    ACER TERMINAL (LNG), JODI (ostatnie 64 KB), Weekly Oil Bulletin KE (pierwsze 4 KB)."""
    E = "https://ir.eia.gov/"
    for i, (lab, url, fn) in enumerate((("wpsr_table1_csv", E + "wpsr/table1.csv", _su_table1),
                                        ("wpsr_psw00_json", E + "wpsr/psw00.json", _su_psw),
                                        ("ngs_wngsr_json", E + "ngs/wngsr.json", _su_wngsr),
                                        ("todayinenergy_prices", "https://www.eia.gov/todayinenergy/prices.php", _su_prices),
                                        ("dnav_hist_RWTCD", "https://www.eia.gov/dnav/pet/hist/RWTCD.htm", _su_dnav),
                                        ("dnav_hist_RBRTED", "https://www.eia.gov/dnav/pet/hist/RBRTED.htm", _su_dnav),
                                        ("acer_terminal_csv", "https://aegis.acer.europa.eu/terminal/price_assessments/historical_data", _su_acer))):
        if i:
            time.sleep(0.3)
        _su("en", lab, url, fn=fn)
    time.sleep(0.3)
    _su_big("en", "jodi_primary2026_tail64k", SU_JODI, 65536, True, _su_jodi)
    time.sleep(0.3)
    _su_big("en", "eu_oil_bulletin_head4k", SU_WOB, 4096, False, _su_zipsig)


# --------------------------------------------------------------------------- (c) bez klucza: metale i fundusze

def _su_xlsx(raw):
    """Plik .xlsx: arkusze, wiersze największego arkusza (pierwszy bywa zastrzeżeniem — SPDR: „Disclaimer”) i najnowsza data w kolumnie A
    (tekst albo liczba seryjna Excela) — bez wartości."""
    if raw[:4] != b"PK" + bytes([3, 4]):
        return f"zip=False html={raw[:300].lstrip().lower().startswith(b'<')}"
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()
    wb = z.read("xl/workbook.xml").decode("utf-8", "replace") if "xl/workbook.xml" in names else ""
    ss = []
    if "xl/sharedStrings.xml" in names:
        x = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        ss = [_su_re.sub(r"<[^>]+>", "", si) for si in _su_re.findall(r"<si>(.*?)</si>", x, _su_re.S)]
    sh = [n for n in names if _su_re.match(r"xl/worksheets/sheet\d+\.xml$", n)]
    s1 = z.read(max(sh, key=lambda n: z.getinfo(n).file_size)).decode("utf-8", "replace") if sh else ""
    ds = []
    for attrs, inner in _su_re.findall(r'<c ([^>]*?\br="A\d+"[^>]*?)(?:/>|>(.*?)</c>)', s1, _su_re.S):
        v = _su_re.search(r"<v>([^<]*)</v>", inner or "")
        tt = _su_re.search(r'\bt="(\w+)"', attrs)
        if tt and tt.group(1) == "s" and v and v.group(1).isdigit():
            k = int(v.group(1))
            ds.append(_su_date(ss[k]) if k < len(ss) else None)
        elif tt and tt.group(1) in ("inlineStr", "str"):
            ds.append(_su_date(_su_re.sub(r"<[^>]+>", "", inner or "")))
        elif v:
            try:
                f = float(v.group(1))
            except ValueError:
                f = 0.0
            if 36526 <= f <= 60000:
                ds.append(dt.date(1899, 12, 30) + dt.timedelta(days=int(f)))
    ds = [d for d in ds if d]
    return (f"xlsx sheets={wb.count('<sheet ')} rows={len(_su_re.findall(r'<row[ >]', s1))} dates={len(ds)} "
            f"newest={_su_max(ds)}")


def _su_sprott(raw):
    """Lista trustów bez symboli: liczba pozycji, podpis kolejności (rząd wielkości wartość/ilość, „+” = drugi metal), najnowsza data."""
    j = json.loads(raw)
    L = j if isinstance(j, list) else (j.get("data") if isinstance(j, dict) else None)
    if not isinstance(L, list):
        return "shape"
    sig, ds = [], []
    for x in L[:6]:
        if not isinstance(x, dict):
            sig.append("?")
            continue
        ds.append(str(x.get("dateTimeStamp") or "")[:10])
        try:
            r = float(x.get("totalMarketValue")) / float(x.get("totalOunces1"))
            e = f"e{len(str(int(r))) - 1}" if r >= 1 else "e-"
        except (TypeError, ValueError, ZeroDivisionError):
            e = "e?"
        sig.append(e + ("+" if _su_num(x.get("totalOunces2")) else ""))
    k0 = ",".join(str(k)[:16] for k in list(L[0].keys())[:7]) if L and isinstance(L[0], dict) else "-"
    return f"n={len(L)} sig={'/'.join(sig)} newest={_su_max(ds)} keys0={k0}"


def _su_cameco(raw):
    ds = {f"{a}-{b}-{c}" for a, b, c in _su_re.findall(r"(20\d\d)/(\d\d)/(\d\d)", raw.decode("utf-8", "replace"))}
    return f"dates={len(ds)} newest={_su_max(ds)}"


def _su_nbp(raw):
    j = json.loads(raw)
    ds = [str(x.get("data")) for x in j if isinstance(x, dict)] if isinstance(j, list) else []
    return f"r={len(ds)} newest={_su_max(ds)}"


def _su_sdmx(raw):
    """SDMX-JSON (MFW 2.1 i 3.0): liczba serii, liczba okresów z obserwacją i najnowszy okres — bez wartości."""
    j = json.loads(raw)
    d = j.get("data", j) if isinstance(j, dict) else {}
    ds = (d.get("dataSets") or [{}])[0] or {}
    st = d.get("structures") or d.get("structure") or {}
    st = (st[0] if st else {}) if isinstance(st, list) else st
    od = ((st.get("dimensions") or {}).get("observation") or [{}]) if isinstance(st, dict) else [{}]
    per = [v.get("value") or v.get("id") for v in ((od[0] or {}).get("values") or []) if isinstance(v, dict)]
    ser = ds.get("series") or {}
    idx = set()
    for s in ser.values():
        idx.update(int(k) for k in ((s or {}).get("observations") or {}) if str(k).isdigit())
    ps = sorted(str(per[i]) for i in idx if i < len(per))
    return f"ser={len(ser)} periods={len(ps)} newest={ps[-1] if ps else '-'}"


def _su_wb_link(raw):
    s = raw.decode("utf-8", "replace")
    m = _su_re.search(r'href="([^"]*CMO-Historical-Data-Monthly\.xlsx)"', s) or _su_re.search(r"""(https?://[^\s"'<>]*CMO-Historical-Data-Monthly\.xlsx)""", s)
    return urllib.parse.urljoin(SU_WB_PAGE, m.group(1)) if m else None


def _su_wb_xlsx(raw):
    """Arkusz Banku Światowego: arkusze, czy jest 'Monthly Prices', najnowszy miesiąc 'RRRRMmm' i data aktualizacji — bez wartości."""
    if raw[:4] != b"PK" + bytes([3, 4]):
        return f"zip=False html={raw[:300].lstrip().lower().startswith(b'<')}"
    z = zipfile.ZipFile(io.BytesIO(raw))
    names = z.namelist()
    wb = z.read("xl/workbook.xml").decode("utf-8", "replace") if "xl/workbook.xml" in names else ""
    txt = z.read("xl/sharedStrings.xml").decode("utf-8", "replace") if "xl/sharedStrings.xml" in names else ""
    mre = r"(?<![\dA-Za-z])((?:19|20)\d\dM(?:0[1-9]|1[0-2]))(?!\d)"
    ms = set(_su_re.findall(mre, txt))
    if not ms:
        for n in names:
            if n.startswith("xl/worksheets/sheet"):
                ms |= set(_su_re.findall(mre, z.read(n).decode("utf-8", "replace")))
    up = _su_re.search(r"Updated on ([A-Z][a-z]+ \d{1,2},? \d{4})", txt)
    ms = sorted(ms)
    return (f"sheets={wb.count('<sheet ')} monthly_prices={'Monthly Prices' in wb} months={len(ms)} newest={ms[-1] if ms else '-'} "
            f"upd={_su_date(up.group(1)) if up else '-'}")


def _su_kraken(raw):
    j = json.loads(raw)
    if not isinstance(j, dict):
        return "shape"
    if j.get("error"):
        return "err=" + str(j["error"][0] if isinstance(j["error"], list) else j["error"])[:40].replace(" ", "_")
    L = next((v for v in (j.get("result") or {}).values() if isinstance(v, list)), [])
    ts = [x[0] for x in L if isinstance(x, list) and x and isinstance(x[0], (int, float))]
    return f"r={len(L)} newest={dt.datetime.fromtimestamp(max(ts), dt.timezone.utc).date().isoformat() if ts else '-'}"


def g_su_metale():
    """Metale i fundusze bez klucza: archiwa SPDR (GLD, GLDM), trusty Sprott, uran (Cameco), złoto NBP, MFW PCPS (SDMX 3.0 metale,
    2.1 energia), świece dzienne PAXG i XAUT (Kraken), Bank Światowy (strona → adres pliku → xlsx)."""
    J = {"Accept": "application/json"}
    for i, (lab, url, fn, hdr) in enumerate((
            ("spdr_gld_archive_xlsx", "https://api.spdrgoldshares.com/api/v1/historical-archive?product=gld&exchange=NYSE&lang=en", _su_xlsx, None),
            ("spdr_gldm_archive_xlsx", "https://api.spdrgoldshares.com/api/v1/historical-archive?product=gldm&exchange=NYSE&lang=en", _su_xlsx, None),
            ("sprott_bullion_calc", "https://sprott.com/api/FinancialData/v1/BullionCalculatorData", _su_sprott, None),
            ("cameco_uranium_price", "https://www.cameco.com/invest/markets/uranium-price", _su_cameco, None),
            ("nbp_cenyzlota_last5", "https://api.nbp.pl/api/cenyzlota/last/5?format=json", _su_nbp, None),
            ("imf_pcps_sdmx30_metals", SU_IMF30, _su_sdmx, J),
            ("imf_pcps_sdmx21_energy", SU_IMF21, _su_sdmx, J),
            ("kraken_ohlc_PAXGUSD", "https://api.kraken.com/0/public/OHLC?pair=PAXGUSD&interval=1440", _su_kraken, None),
            ("kraken_ohlc_XAUTUSD", "https://api.kraken.com/0/public/OHLC?pair=XAUTUSD&interval=1440", _su_kraken, None))):
        if i:
            time.sleep(0.3)
        _su("met", lab, url, fn=fn, headers=None if hdr is None else {**SU_HDR, **hdr})
    time.sleep(0.3)
    st, raw, _ = _su("met", "worldbank_page", SU_WB_PAGE, fn=lambda r: f"xlsx_link={'yes' if _su_wb_link(r) else 'no'}")
    link = _su_wb_link(raw) if st == 200 and raw else None
    if link:
        time.sleep(0.3)
        _su("met", "worldbank_cmo_monthly_xlsx", link, fn=_su_wb_xlsx)
    else:
        skipped("su-met", "worldbank_cmo_monthly_xlsx", "no link on page")
        _su_out("summary su-met worldbank_cmo_monthly_xlsx SKIP no-link-on-page")


def _su_cl(raw):
    j = json.loads(raw)
    h = str(j.get("result") or "") if isinstance(j, dict) else ""
    if not h.startswith("0x") or len(h) < 2 + 64 * 5:
        return "err-" + ("rpc" if isinstance(j, dict) and j.get("error") else "shape")
    w = [int(h[2 + 64 * i:2 + 64 * (i + 1)], 16) for i in range(5)]
    return f"answer>0={0 < w[1] < 2 ** 255} age={(time.time() - w[3]) / 3600:.1f}h"


def g_su_chainlink():
    """Wyrocznie XAG/USD i PAXG/USD (latestRoundData) przez ten sam publiczny węzeł Ethereum, którego zbieracz używa dla XAU/USD w RWA —
    bez nowego węzła. Tylko: czy odpowiedź jest dodatnia i wiek ostatniej aktualizacji (bez kursu)."""
    for i, (lab, adr) in enumerate(SU_CL):
        if i:
            time.sleep(0.3)
        _su("cl", f"latestRoundData_{lab}", "https://ethereum-rpc.publicnode.com", fn=_su_cl, method="POST",
            body={"jsonrpc": "2.0", "id": 1, "method": "eth_call", "params": [{"to": adr, "data": "0xfeaf968c"}, "latest"]})


# --------------------------------------------------------------------------- (d) bez klucza: pozycje i rolne

def _su_cot(raw):
    t = raw.decode("utf-8-sig", "replace")
    return f"rows={sum(1 for x in t.splitlines() if x.strip())} newest={_su_max(_su_iso(t))}"


def _su_soc_cftc(raw):
    j = json.loads(raw)
    if not isinstance(j, list):
        return "err-" + _su_errcls(raw)
    R = [r for r in j if isinstance(r, dict)]
    cs = {str(r.get("cftc_contract_market_code")) for r in R}
    return (f"r={len(R)} newest={_su_max([str(r.get('report_date_as_yyyy_mm_dd') or '')[:10] for r in R])} "
            f"codes={len(cs & set(SU_SOC_CODES))}/{len(SU_SOC_CODES)}")


def _su_soc_date(raw):
    j = json.loads(raw)
    if not isinstance(j, list):
        return "err-" + _su_errcls(raw)
    return f"r={len(j)} newest={_su_max([str(r.get('date') or '')[:10] for r in j if isinstance(r, dict)])}"


def _su_ice(raw):
    t = raw.decode("utf-8-sig", "replace")
    R = [r for r in _su_csv.reader(t.splitlines()) if r]
    h = R[0] if R else []
    di = next((i for i, c in enumerate(h) if c.strip().startswith("As_of_Date_Form")), None)
    ds = [_su_date(r[di]) for r in R[1:] if di is not None and di < len(r)]
    if di is None:
        ds = [_su_date(f"{a}/{b}/{c}") for a, b, c in _su_re.findall(r"(?<!\d)(\d{2})/(\d{2})/(20\d\d)(?!\d)", t)]
    return f"rows={max(0, len(R) - 1)} newest={_su_max([d for d in ds if d])} mkts={len({r[0] for r in R[1:]})} cols={len(h)}"


def _su_fao(raw):
    ms = _su_re.findall(r"(?m)^\"?((?:19|20)\d\d-\d\d)", raw.decode("utf-8-sig", "replace"))
    return f"rows={len(ms)} newest={max(ms) if ms else '-'}"


def _su_valet(raw):
    j = json.loads(raw)
    g = j if isinstance(j, dict) else {}
    obs = [o for o in (g.get("observations") or []) if isinstance(o, dict)]
    return f"obs={len(obs)} newest={_su_max([o.get('d') for o in obs])} ser={len(g.get('seriesDetail') or {})}"


def _su_gscpi(raw):
    R = [r for r in _su_csv.reader(raw.decode("utf-8-sig", "replace").splitlines()) if r]
    if not R:
        return "rows=0"
    h = R[0]
    li = max((i for i, c in enumerate(h) if c.strip()), default=0)
    last = [r for r in R[1:] if li < len(r) and r[li].strip()]
    return f"vintage={h[li].strip()[:12]} rows={len(R) - 1} last={last[-1][0].strip()[:12] if last else '-'}"


def _su_arcgis(raw):
    j = json.loads(raw)
    if not isinstance(j, dict):
        return "shape"
    if j.get("error"):
        return "err-" + str((j.get("error") or {}).get("code", ""))[:6]
    F = [f.get("attributes") or {} for f in (j.get("features") or []) if isinstance(f, dict)]
    ds = []
    for a in F:
        v = a.get("date")
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            ds.append(dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc).date())
        elif v:
            ds.append(str(v)[:10])
    return f"n={len(F)} newest={_su_max(ds)} ports={len({a.get('portname') for a in F})}"


def _su_lmr_list(raw):
    j = json.loads(raw)
    L = j if isinstance(j, list) else ((j.get("results") or j.get("reports") or []) if isinstance(j, dict) else [])
    return f"reports={len(L)}"


def _su_lmr(raw):
    j = json.loads(raw)
    R = (j.get("results") or []) if isinstance(j, dict) else (j if isinstance(j, list) else [])
    ds = [str(r.get("report_date") or "") for r in R if isinstance(r, dict)]
    return f"res={len(R)} newest={_su_max(ds)}"


def g_su_rolne():
    """Pozycje i rolne bez klucza: CFTC (indeksowi, Socrata z filtrem), ICE COT, FAO, WASDE (bieżący albo poprzedni miesiąc), Bank Kanady
    (BCPI), NY Fed (GSCPI), PortWatch (cieśniny), agtransport (inspekcje zboża), USDA LMR (lista raportów i wycena wołowiny)."""
    q = urllib.parse.quote
    soc = "https://publicreporting.cftc.gov/resource/72hh-3qpy.json?" + urllib.parse.urlencode(
        {"$where": "cftc_contract_market_code in(" + ",".join(f"'{c}'" for c in SU_SOC_CODES) + ")",
         "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "8"}, quote_via=q)
    agt = "https://agtransport.usda.gov/resource/sruw-w49i.json?" + urllib.parse.urlencode({"$order": "date DESC", "$limit": "5"}, quote_via=q)
    pw = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query?"
          "where=1%3D1&outFields=date,portname,n_total&orderByFields=date%20DESC&resultRecordCount=30&f=json")
    lmr = "https://mpr.datamart.ams.usda.gov/services/v1.1/reports"
    for i, (lab, url, fn) in enumerate((
            ("cftc_deacit_txt", "https://www.cftc.gov/dea/newcot/deacit.txt", _su_cot),
            ("cftc_socrata_72hh_filter", soc, _su_soc_cftc),
            ("ice_cothist2026_csv", "https://www.ice.com/publicdocs/futures/COTHist2026.csv", _su_ice),
            ("fao_food_price_indices_csv", "https://www.fao.org/media/docs/worldfoodsituationlibraries/wfs-library/food_price_indices_data.csv",
             _su_fao),
            ("boc_valet_bcpi_weekly", "https://www.bankofcanada.ca/valet/observations/group/BCPI_WEEKLY/json?recent=5", _su_valet),
            ("nyfed_gscpi_csv", "https://www.newyorkfed.org/medialibrary/research/interactives/data/gscpi/gscpi_interactive_data.csv", _su_gscpi),
            ("imf_portwatch_chokepoints", pw, _su_arcgis),
            ("agtransport_sruw_inspections", agt, _su_soc_date),
            ("usda_lmr_reports_list", lmr, _su_lmr_list),
            ("usda_lmr_2453_cutout", f"{lmr}/2453/Current%20Cutout%20Values?q=report_date={_last_weekday(1):%m/%d/%Y}", _su_lmr))):
        if i:
            time.sleep(0.3)
        _su("rol", lab, url, fn=fn)
    t = _utc_today()
    for y, m in ((t.year, t.month), (t.year - 1, 12) if t.month == 1 else (t.year, t.month - 1)):
        time.sleep(0.3)
        st, _, _ = _su("rol", f"wasde_csv_{y}-{m:02d}", f"https://www.usda.gov/sites/default/files/documents/oce-wasde-report-data-{y}-{m:02d}.csv",
                       fn=_su_cot)
        if st == 200:
            break


# --------------------------------------------------------------------------- (e) bez klucza: źródła kruche (tylko dostęp)

def _su_shfe(raw):
    j = json.loads(raw)
    g = j if isinstance(j, dict) else {}
    return f"inst={len(g.get('o_curinstrument') or [])} idx={len(g.get('o_curmetalindex') or [])} keys={len(g)}"


def _su_sge(raw):
    j = json.loads(raw)
    g = j if isinstance(j, dict) else {}
    out = []
    for k in ("zp", "wp"):
        L = [x for x in (g.get(k) or []) if isinstance(x, list) and x and isinstance(x[0], (int, float))]
        nw = (dt.datetime.fromtimestamp(max(x[0] for x in L) / 1000, dt.timezone.utc) + dt.timedelta(hours=8)).date().isoformat() if L else "-"   # północ w Pekinie
        out.append(f"{k}={len(L)}/{nw}")
    return " ".join(out)


def _su_gme(raw):
    m = _su_re.search(r"OQD Marker Price\s+([A-Z][a-z]+ \d{1,2},? \d{4})", _su_txt(raw))
    return f"marker_date={_su_date(m.group(1)) if m else '-'}"


def _su_orlen(raw):
    j = json.loads(raw)
    L = [x for x in j if isinstance(x, dict)] if isinstance(j, list) else []
    return f"n={len(L)} newest={_su_max([str(x.get('effectiveDate') or '')[:10] for x in L])}"


def _su_tge(raw):
    m = _su_re.search(r"w dniu\s+(\d{2})-(\d{2})-(\d{4})", _su_txt(raw))
    return f"delivery_day={m.group(3)}-{m.group(2)}-{m.group(1)}" if m else ""


def _su_igc(word):
    def f(raw):
        s = _su_txt(raw)
        m = _su_re.search(r"\b(\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))\b", s)
        return f"table={word in s} date={m.group(1).replace(' ', '_') if m else '-'}" if word in s else ""
    return f


def g_su_kruche():
    """Źródła kruche (tylko dostęp z USA): SHFE (plik dnia sprzed świąt w Chinach i ostatni dzień roboczy), SGE, GME (OQD Marker), Orlen,
    TGE (gaz RDN), IGC (indeks zbóż i frachtów). Przy 403 / captcha / Cloudflare — notatka, bez obchodzenia."""
    sh = "https://www.shfe.com.cn/data/tradedata/future/dailydata/kx{}.dat"
    d2 = _last_weekday(1).strftime("%Y%m%d")
    items = [("shfe_kx_20260930", sh.format("20260930"), _su_shfe)]
    if d2 != "20260930":
        items.append(("shfe_kx_last_weekday", sh.format(d2), _su_shfe))
    items += [("sge_gold_benchmark", "https://en.sge.com.cn/graph/DayilyJzj", _su_sge),
              ("gme_homepage", "https://www.gulfmerc.com/", _su_gme),
              ("orlen_wholesalefuelprices", "https://tool.orlen.pl/api/wholesalefuelprices", _su_orlen),
              ("tge_gaz_rdn", "https://tge.pl/gaz-rdn", _su_tge),
              ("igc_goi", "https://igc.int/en/public-site/markets/marketinfo-goi.aspx", _su_igc("Grains and Oilseeds Index")),
              ("igc_freight", "https://igc.int/en/public-site/markets/marketinfo-freight.aspx", _su_igc("Freight Index"))]
    for i, (lab, url, fn) in enumerate(items):
        if i:
            time.sleep(0.3)
        _su("kru", lab, url, fn=fn)


GROUPS.insert(GROUPS.index(g_nasdaq), g_su_td)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_fmp)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_eia)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_tiingo)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_cg)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_energia)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_metale)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_chainlink)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_rolne)
GROUPS.insert(GROUPS.index(g_nasdaq), g_su_kruche)
TYLKO = ("g_su_td", "g_su_fmp", "g_su_eia", "g_su_tiingo", "g_su_cg", "g_su_energia", "g_su_metale", "g_su_chainlink", "g_su_rolne",
         "g_su_kruche")   # v294p: ten przebieg — tylko sonda surowców (v288p: g_jse2; v272p: g_ix_fmp, g_ix_massive; pusta krotka = wszystkie)


# --------------------------------------------------------------------------- main

def main():
    print(f"sondy.py start {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')} "
          f"python {sys.version.split()[0]} (no URLs, headers, bodies or key values are printed)", flush=True)
    print(f"{'provider':<15}| {'env var found':<30}| {'probe':<34}| status    | elapsed   | bytes       | shape", flush=True)
    grupy = [g for g in GROUPS if not TYLKO or g.__name__ in TYLKO]   # v272p: przebieg tylko wybranych grup (bez zbędnych zapytań z limitów planów)
    ex = cf.ThreadPoolExecutor(max_workers=max(1, len(grupy)))
    futs = {ex.submit(g): g.__name__ for g in grupy}
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
