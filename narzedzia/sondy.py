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
    "banxico":      ["BANXICO_TOKEN"],          # v126 (27.09): Banco de México SIE, nagłówek Bmx-Token
    "evds":         ["EVDS_KEY"],               # v126 (27.09): TCMB EVDS3, nagłówek key
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
