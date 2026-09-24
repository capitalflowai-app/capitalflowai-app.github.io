#!/usr/bin/env python3
"""Testy zbieracza (tylko biblioteka standardowa, bez sieci).

Sprawdzają zasady projektu: brak nie jest zerem, żadnego cichego zastępowania danych,
zakres dat gdy monety publikują w różnych dniach, pamięć podręczna tylko dla młodych plików.
Uruchomienie: python3 -m unittest -v test_zbieraj_dane.py
"""
import datetime
import json
import os
import unittest
from unittest import mock

import zbieraj_dane as zd


def _iso(minutes_ago):
    t = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutes_ago)
    return t.replace(microsecond=0).isoformat()


class Fresh(unittest.TestCase):
    def test_young_file_is_fresh(self):
        self.assertTrue(zd.fresh({'at': _iso(10)}, 55))

    def test_old_file_is_not_fresh(self):
        self.assertFalse(zd.fresh({'at': _iso(120)}, 55))

    def test_broken_or_missing_at_is_not_fresh(self):
        self.assertFalse(zd.fresh({}, 55))
        self.assertFalse(zd.fresh({'at': 'wczoraj'}, 55))
        self.assertFalse(zd.fresh(None, 55))


def _soso_factory(history, funds, snapshots):
    """Udaje SoSoValue: history[sym] = wiersze summary-history, funds[sym] = lista funduszy,
    snapshots[ticker] = market-snapshot."""
    def soso(path, key, _retry=True):
        if path.startswith('/etfs/summary-history'):
            sym = path.split('symbol=')[1].split('&')[0].lower()
            return history.get(sym, [])
        if path.startswith('/etfs?'):
            sym = path.split('symbol=')[1].split('&')[0].lower()
            return funds.get(sym, [])
        if path.startswith('/etfs/') and path.endswith('/market-snapshot'):
            ticker = path.split('/')[2]
            return snapshots[ticker]
        raise AssertionError('nieznana ścieżka ' + path)
    return soso


def _rows(dates, inflow=100.0, assets=None):
    return [{'date': d, 'total_net_inflow': inflow * 1e6, 'cum_net_inflow': 5e9,
             'total_net_assets': assets} for d in dates]


class BuildEtf(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear()
        zd.META['ok'].clear()
        self.no_cg = mock.patch.object(zd, 'get_json', side_effect=RuntimeError('brak sieci'))
        self.no_cg.start()

    def tearDown(self):
        self.no_cg.stop()

    def test_missing_fund_assets_make_total_unknown_not_zero(self):
        history = {s: _rows(['2026-09-22', '2026-09-23'], assets=None) for s in zd.ETF_SYMS}
        funds = {s: [{'ticker': s.upper() + 'A', 'name': 'A'}, {'ticker': s.upper() + 'B', 'name': 'B'}] for s in zd.ETF_SYMS}
        snapshots = {}
        for s in zd.ETF_SYMS:
            snapshots[s.upper() + 'A'] = {'net_assets': 1.5e9, 'cum_inflow': 1e9, 'net_inflow': 1e6, 'sponsor_fee': 0.0025}
            snapshots[s.upper() + 'B'] = {'net_assets': None, 'cum_inflow': None, 'net_inflow': None, 'sponsor_fee': None}
        with mock.patch.object(zd, 'soso', _soso_factory(history, funds, snapshots)):
            out = zd.build_etf('klucz', '')
        for s in zd.ETF_SYMS:
            self.assertIsNone(out['assets'][s]['aum'], s)      # brak aktywów jednego funduszu = suma nieznana
            self.assertIsNone(out['assets'][s]['share'], s)

    def test_complete_fund_assets_are_summed(self):
        history = {s: _rows(['2026-09-23'], assets=None) for s in zd.ETF_SYMS}
        funds = {s: [{'ticker': s.upper() + 'A', 'name': 'A'}, {'ticker': s.upper() + 'B', 'name': 'B'}] for s in zd.ETF_SYMS}
        snapshots = {}
        for s in zd.ETF_SYMS:
            snapshots[s.upper() + 'A'] = {'net_assets': 1.5e9}
            snapshots[s.upper() + 'B'] = {'net_assets': 0.5e9}
        with mock.patch.object(zd, 'soso', _soso_factory(history, funds, snapshots)):
            out = zd.build_etf('klucz', '')
        self.assertAlmostEqual(out['assets']['btc']['aum'], 2000.0)   # mln USD

    def test_asof_is_a_range_when_coins_differ(self):
        history = {'btc': _rows(['2026-09-22', '2026-09-23']), 'eth': _rows(['2026-09-23']),
                   'sol': _rows(['2026-09-22']), 'xrp': _rows(['2026-09-22'])}
        with mock.patch.object(zd, 'soso', _soso_factory(history, {}, {})):
            out = zd.build_etf('klucz', '')
        self.assertEqual(out['asof'], '2026-09-22 – 2026-09-23')
        self.assertEqual(out['assets']['sol']['asof'], '2026-09-22')

    def test_asof_is_single_date_when_coins_agree(self):
        history = {s: _rows(['2026-09-23']) for s in zd.ETF_SYMS}
        with mock.patch.object(zd, 'soso', _soso_factory(history, {}, {})):
            out = zd.build_etf('klucz', '')
        self.assertEqual(out['asof'], '2026-09-23')

    def test_no_rows_for_a_coin_is_an_error_not_a_zero(self):
        history = {'btc': _rows(['2026-09-23']), 'eth': [], 'sol': _rows(['2026-09-23']), 'xrp': _rows(['2026-09-23'])}
        with mock.patch.object(zd, 'soso', _soso_factory(history, {}, {})):
            with self.assertRaises(RuntimeError):
                zd.build_etf('klucz', '')

    def test_rows_without_inflow_are_dropped_not_zeroed(self):
        rows = _rows(['2026-09-22', '2026-09-23'])
        rows[1]['total_net_inflow'] = None
        history = {s: list(rows) for s in zd.ETF_SYMS}
        with mock.patch.object(zd, 'soso', _soso_factory(history, {}, {})):
            out = zd.build_etf('klucz', '')
        self.assertEqual(len(out['assets']['btc']['day']), 1)
        self.assertEqual(out['asof'], '2026-09-22')

    def test_coingecko_failure_is_recorded_not_hidden(self):
        history = {s: _rows(['2026-09-23']) for s in zd.ETF_SYMS}
        with mock.patch.object(zd, 'soso', _soso_factory(history, {}, {})):
            out = zd.build_etf('klucz', 'klucz-cg')
        self.assertEqual(out['mcap'], {})
        self.assertIs(zd.META['ok']['coingecko'], False)
        self.assertTrue(any(e.startswith('CoinGecko') for e in zd.META['errors']))


class MainFlow(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear()
        zd.META['ok'].clear()
        self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj))
        self.p_save.start()
        # testy bez sieci: źródła urzędowe udają awarię (ich własne testy są w klasie Instytucje)
        self.p_inst = mock.patch.object(zd, 'build_instytucje', side_effect=RuntimeError('offline'))
        self.p_inst.start()

    def tearDown(self):
        self.p_save.stop()
        self.p_inst.stop()

    def test_young_previous_file_is_reused_without_asking_sosovalue(self):
        prev = {'at': _iso(10), 'assets': {'btc': {'day': [[1, 1.0]]}}}
        env = {'SOSOVALUE_KEY': 'k', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'etf' else None), \
             mock.patch.object(zd, 'build_etf', side_effect=AssertionError('nie wolno pytać SoSoValue')):
            zd.main()
        self.assertIs(self.saved['etf'], prev)
        self.assertEqual(zd.META['ok']['sosovalue'], 'cached')

    def test_source_failure_keeps_previous_file_and_reports_error(self):
        prev = {'at': _iso(180), 'assets': {'btc': {'day': [[1, 1.0]]}}}
        env = {'SOSOVALUE_KEY': 'k', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'etf' else None), \
             mock.patch.object(zd, 'build_etf', side_effect=RuntimeError('SoSoValue: 429')):
            zd.main()
        self.assertIs(self.saved['etf'], prev)                     # stary plik z prawdziwym „at”, nie pustka
        self.assertIs(zd.META['ok']['sosovalue'], False)
        self.assertTrue(any('SoSoValue' in e for e in zd.META['errors']))
        self.assertIs(zd.META['ok']['finnhub'], False)              # brak klucza = jawny błąd, nie cisza

    def test_meta_is_always_written(self):
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False):
            zd.main()
        self.assertIn('meta', self.saved)
        self.assertEqual([e for e in self.saved['meta']['errors'] if not e.startswith('instytucje') and not e.startswith('poprzedni')],
                         ['brak SOSOVALUE_KEY', 'brak FINNHUB_KEY', 'brak TWELVEDATA_KEY', 'brak COINMARKETCAP_KEY', 'brak FRED_KEY'])


class BuildDay(unittest.TestCase):
    def _quotes(self, n, dp=True):
        def get(url, headers=None, timeout=30):
            sym = url.split('symbol=')[1].split('&')[0]
            if zd.DAY_SYMS.index(sym) >= n:
                return 200, json.dumps({'c': 0, 'pc': 0})
            q = {'c': 101.0, 'pc': 100.0, 't': 1790193600}
            if dp:
                q['dp'] = 1.0
            return 200, json.dumps(q)
        return get

    def test_too_few_quotes_is_an_error(self):
        with mock.patch.object(zd, 'get', self._quotes(9)), mock.patch.object(zd.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                zd.build_day('klucz')

    def test_enough_quotes_and_missing_dp_is_computed(self):
        with mock.patch.object(zd, 'get', self._quotes(14, dp=False)), mock.patch.object(zd.time, 'sleep'):
            out = zd.build_day('klucz')
        self.assertEqual(len(out['q']), 14)
        self.assertAlmostEqual(out['q']['SPY']['dp'], 1.0)
        self.assertEqual(out['src'], 'Finnhub')

# --- Twelve Data (data/ceny.json): okresy 1T i 1M ---
def _td_symbol(dates, close0=100.0, exchange='ARCX'):
    """Odpowiedź w formacie Twelve Data: values od najnowszej do najstarszej, liczby jako teksty."""
    values = [{'datetime': d, 'open': str(close0 + i), 'high': str(close0 + i + 1), 'low': str(close0 + i - 1),
               'close': f'{close0 + i:.5f}', 'volume': str(1000 + i)} for i, d in enumerate(dates)]
    values.reverse()
    return {'meta': {'symbol': 'X', 'interval': '1day', 'currency': 'USD', 'exchange': 'NYSE', 'mic_code': exchange,
                     'type': 'ETF'}, 'values': values, 'status': 'ok'}


def _dates(n, start=datetime.date(2026, 7, 20)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def _raise():
    raise AssertionError('bez klucza nie pytamy o poprzedni ceny.json')


class ParseTwelveData(unittest.TestCase):
    def test_batch_response_gives_ascending_rows_with_float_close_and_int_volume(self):
        dates = _dates(45)
        j = {'SPY': _td_symbol(dates), 'EWC': _td_symbol(dates, 50.0, 'XNMS')}
        q, errors = zd.parse_td(j, ['SPY', 'EWC'])
        self.assertEqual(errors, [])
        self.assertEqual(sorted(q), ['EWC', 'SPY'])
        d = q['SPY']['d']
        self.assertEqual(len(d), 45)
        self.assertEqual([r[0] for r in d], dates)                       # rosnąco po dacie
        self.assertIsInstance(d[0][1], float)
        self.assertEqual(d[0][1], 100.0)
        self.assertEqual(d[-1][1], 144.0)
        self.assertEqual(d[0][2], 1000)
        self.assertEqual(q['SPY']['asof'], dates[-1])
        self.assertEqual(q['EWC']['ex'], 'XNMS')

    def test_single_symbol_response_without_outer_key_is_accepted(self):
        q, errors = zd.parse_td(_td_symbol(_dates(30)), ['SPY'])
        self.assertEqual(errors, [])
        self.assertEqual(len(q['SPY']['d']), 30)

    def test_error_symbol_goes_to_errors_not_to_quotes(self):
        j = {'SPY': _td_symbol(_dates(30)), 'TUR': {'code': 400, 'message': 'symbol not found', 'status': 'error'}}
        q, errors = zd.parse_td(j, ['SPY', 'TUR'])
        self.assertEqual(list(q), ['SPY'])
        self.assertEqual(errors, ['Twelve Data TUR: symbol not found'])

    def test_bad_key_is_a_whole_response_error(self):
        with self.assertRaises(RuntimeError):
            zd.parse_td({'code': 401, 'message': 'invalid api key', 'status': 'error'}, ['SPY', 'EWC'])

    def test_rows_without_valid_close_are_dropped_not_zeroed(self):
        o = _td_symbol(_dates(3))
        o['values'][0]['close'] = 'null'
        o['values'][1]['close'] = '0'
        q, errors = zd.parse_td({'SPY': o}, ['SPY'])
        self.assertEqual(len(q['SPY']['d']), 1)
        o['values'][2]['close'] = 'x'
        q, errors = zd.parse_td({'SPY': o}, ['SPY'])
        self.assertEqual(q, {})
        self.assertEqual(errors, ['Twelve Data SPY: brak poprawnych świec'])


class BuildPrices(unittest.TestCase):
    def _get(self, n_ok, n_candles=45, asof_shift=None):
        def get(url, headers=None, timeout=30):
            self.assertNotIn('apikey=', url.split('?')[0])
            syms = url.split('symbol=')[1].split('&')[0].split(',')
            self.assertLessEqual(len(syms), zd.TD_BATCH)
            out = {}
            for s in syms:
                if zd.DAY_SYMS.index(s) < n_ok:
                    dates = _dates(n_candles)
                    if asof_shift and s == 'EWA':
                        dates = dates[:-1]
                    out[s] = _td_symbol(dates)
                else:
                    out[s] = {'code': 404, 'message': 'no data', 'status': 'error'}
            return 200, json.dumps(out)
        return get

    def setUp(self):
        zd.META['errors'].clear()

    def test_two_batches_with_a_minute_between_them(self):
        sleeps = []
        with mock.patch.object(zd, 'get', self._get(14)), mock.patch.object(zd.time, 'sleep', sleeps.append):
            out = zd.build_prices('klucz')
        self.assertEqual(len(out['q']), 14)
        self.assertEqual(sleeps, [zd.TD_SLEEP])                            # jedna przerwa między dwiema paczkami
        self.assertEqual(out['src'], 'Twelve Data')
        self.assertEqual(out['plan'], 'basic')
        self.assertEqual(out['asof'], _dates(45)[-1])
        self.assertEqual(zd.META['errors'], [])

    def test_too_few_symbols_is_an_error(self):
        with mock.patch.object(zd, 'get', self._get(9)), mock.patch.object(zd.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                zd.build_prices('klucz')
        self.assertEqual(len([e for e in zd.META['errors'] if e.startswith('Twelve Data')]), 5)

    def test_too_few_candles_do_not_count(self):
        with mock.patch.object(zd, 'get', self._get(14, n_candles=21)), mock.patch.object(zd.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                zd.build_prices('klucz')

    def test_asof_is_a_range_when_symbols_differ(self):
        with mock.patch.object(zd, 'get', self._get(14, asof_shift=True)), mock.patch.object(zd.time, 'sleep'):
            out = zd.build_prices('klucz')
        d = _dates(45)
        self.assertEqual(out['asof'], f'{d[-2]} – {d[-1]}')

    def test_http_error_does_not_leak_the_key(self):
        import urllib.error
        def get(url, headers=None, timeout=30):
            raise urllib.error.HTTPError(url, 401, 'Unauthorized', {}, None)
        with mock.patch.object(zd, 'get', get), mock.patch.object(zd.time, 'sleep'):
            with self.assertRaises(RuntimeError) as cm:
                zd.build_prices('tajny-klucz')
        self.assertNotIn('tajny-klucz', str(cm.exception))


class MainFlowPrices(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear()
        zd.META['ok'].clear()
        self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj))
        self.p_save.start()
        self.p_inst = mock.patch.object(zd, 'build_instytucje', side_effect=RuntimeError('offline'))
        self.p_inst.start()

    def tearDown(self):
        self.p_save.stop()
        self.p_inst.stop()

    def test_young_previous_file_is_reused_without_asking_twelve_data(self):
        prev = {'at': _iso(10), 'q': {'SPY': {'d': [['2026-09-23', 1.0, 1]]}}}
        env = {'SOSOVALUE_KEY': '', 'FINNHUB_KEY': '', 'COINGECKO_KEY': '', 'TWELVEDATA_KEY': 'k', 'COINMARKETCAP_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'ceny' else None), \
             mock.patch.object(zd, 'build_prices', side_effect=AssertionError('nie wolno pytać Twelve Data')):
            zd.main()
        self.assertIs(self.saved['ceny'], prev)
        self.assertEqual(zd.META['ok']['twelvedata'], 'cached')

    def test_source_failure_keeps_previous_file_and_reports_error(self):
        prev = {'at': _iso(180), 'q': {'SPY': {'d': [['2026-09-23', 1.0, 1]]}}}
        env = {'SOSOVALUE_KEY': '', 'FINNHUB_KEY': '', 'COINGECKO_KEY': '', 'TWELVEDATA_KEY': 'k', 'COINMARKETCAP_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'ceny' else None), \
             mock.patch.object(zd, 'build_prices', side_effect=RuntimeError('HTTP 429')):
            zd.main()
        self.assertIs(self.saved['ceny'], prev)
        self.assertIs(zd.META['ok']['twelvedata'], False)
        self.assertIn('Twelve Data: HTTP 429', zd.META['errors'])

    def test_missing_key_is_reported_and_no_file_is_written(self):
        env = {'SOSOVALUE_KEY': '', 'FINNHUB_KEY': '', 'COINGECKO_KEY': '', 'TWELVEDATA_KEY': '', 'COINMARKETCAP_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: (_raise() if name == 'ceny' else None)):
            zd.main()
        self.assertNotIn('ceny', self.saved)
        self.assertIn('brak TWELVEDATA_KEY', zd.META['errors'])
        self.assertIs(zd.META['ok']['twelvedata'], False)

class BuildCmc(unittest.TestCase):
    """CoinMarketCap global metrics: klucz w nagłówku, brakujące pola = None (nie 0), błąd statusu = wyjątek."""

    def test_metrics_parsed_from_documented_shape(self):
        seen = {}
        def get_json(url, headers=None):
            seen['url'], seen['headers'] = url, headers
            return {'status': {'error_code': 0}, 'data': {'active_cryptocurrencies': 9000, 'btc_dominance': 56.3, 'eth_dominance': 12.1,
                    'last_updated': '2026-09-24T15:00:00.000Z', 'quote': {'USD': {'total_market_cap': 2.84e12, 'total_volume_24h': 1.7e11,
                    'total_market_cap_yesterday_percentage_change': -4.9, 'stablecoin_market_cap': 3.1e11, 'defi_market_cap': 9.4e10}}}}
        with mock.patch.object(zd, 'get_json', get_json):
            out = zd.build_cmc('TAJNY-CMC')
        self.assertNotIn('TAJNY-CMC', seen['url']); self.assertEqual(seen['headers']['X-CMC_PRO_API_KEY'], 'TAJNY-CMC')
        self.assertEqual(out['total_mcap'], 2.84e12); self.assertEqual(out['btc_dom'], 56.3); self.assertEqual(out['stable_mcap'], 3.1e11)
        self.assertIsNone(out['altcoin_mcap'])                       # pola nieobecnego nie zgadujemy
        self.assertEqual(out['asof'], '2026-09-24T15:00:00.000Z')

    def test_error_status_is_an_exception_without_the_key(self):
        with mock.patch.object(zd, 'get_json', lambda url, headers=None: {'status': {'error_code': 1002, 'error_message': 'API key missing.'}}):
            with self.assertRaises(RuntimeError) as cm:
                zd.build_cmc('TAJNY-CMC')
        self.assertNotIn('TAJNY-CMC', str(cm.exception))


class Hardening(unittest.TestCase):
    """Audyt 24.09 (B6, B8, B9): klucz nigdy w meta.json, klucz CoinGecko w nagłówku, ticker sprawdzany wzorcem."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.SECRETS[:] = ['TAJNY-SOSO', 'TAJNY-CG']

    def tearDown(self):
        zd.SECRETS[:] = []

    def test_error_messages_never_contain_a_key(self):
        self.assertEqual(zd.mask('boom https://x?key=TAJNY-CG'), 'boom https://x?key=***')
        self.assertEqual(zd.mask(RuntimeError('SoSoValue TAJNY-SOSO')), 'SoSoValue ***')

    def test_coingecko_key_travels_in_a_header_not_in_the_url(self):
        seen = {}
        def get_json(url, headers=None):
            seen['url'], seen['headers'] = url, headers
            raise RuntimeError('stop')
        with mock.patch.object(zd, 'get_json', get_json), mock.patch.object(zd, 'soso', side_effect=RuntimeError('stop')):
            with self.assertRaises(RuntimeError):
                zd.build_etf('TAJNY-SOSO', 'TAJNY-CG')
        self.assertNotIn('TAJNY-CG', seen['url'])
        self.assertEqual(seen['headers'], {'x-cg-demo-api-key': 'TAJNY-CG'})
        self.assertTrue(all('TAJNY' not in e for e in zd.META['errors']))

    def test_ticker_outside_the_pattern_is_rejected_and_reported(self):
        funds = {'btc': [{'ticker': 'IBIT', 'name': 'ok'}, {'ticker': '<img src=x>', 'name': 'zły'}]}
        snapshots = {'IBIT': {'net_assets': 1e9, 'cum_inflow': 1e9, 'net_inflow': 1e6, 'sponsor_fee': 0.0025}}
        with mock.patch.object(zd, 'soso', _soso_factory({'btc': _rows(['2026-09-22', '2026-09-23'])}, funds, snapshots)), \
             mock.patch.object(zd, 'get_json', lambda url, headers=None: {'bitcoin': {'usd_market_cap': 1e12}, 'ethereum': {'usd_market_cap': 1},
                                                                          'solana': {'usd_market_cap': 1}, 'ripple': {'usd_market_cap': 1}}), \
             mock.patch.object(zd, 'ETF_SYMS', ['btc']):
            out = zd.build_etf('k', 'c')
        self.assertEqual([f['t'] for f in out['assets']['btc']['funds']], ['IBIT'])
        self.assertTrue(any('odrzucony ticker' in e for e in zd.META['errors']))


class Instytucje(unittest.TestCase):
    """Źródła urzędowe bez klucza: parsery na kształtach odpowiedzi sprawdzonych 24.09.2026; brak nie jest zerem."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()
        self.p_sleep = mock.patch.object(zd.time, 'sleep', lambda s: None); self.p_sleep.start()   # odstępy EBC bez czekania

    def tearDown(self):
        self.p_sleep.stop()

    def test_tga_closing_balance_ascending_and_null_skipped(self):
        j = {'data': [
            {'record_date': '2026-09-22', 'account_type': 'Treasury General Account (TGA) Closing Balance', 'open_today_bal': '957409'},
            {'record_date': '2026-09-21', 'account_type': 'Treasury General Account (TGA) Closing Balance', 'open_today_bal': 'null'},
            {'record_date': '2026-09-18', 'account_type': 'Treasury General Account (TGA) Closing Balance', 'open_today_bal': '1004391'},
            {'record_date': '2026-09-18', 'account_type': 'Total TGA Deposits (Table II)', 'open_today_bal': '5'}]}
        t = zd.parse_tga(j)
        self.assertEqual(t['d'], [['2026-09-18', 1004391], ['2026-09-22', 957409]])
        self.assertEqual(t['asof'], '2026-09-22'); self.assertEqual(t['unit'], 'mln USD')
        with self.assertRaises(RuntimeError):
            zd.parse_tga({'data': []})

    def test_rrp_accepted_in_millions_only_reverse_repo(self):
        j = {'repo': {'operations': [
            {'operationDate': '2026-09-23', 'operationType': 'Reverse Repo', 'totalAmtAccepted': 461000000},
            {'operationDate': '2026-09-22', 'operationType': 'Reverse Repo', 'totalAmtAccepted': 453000000},
            {'operationDate': '2026-09-24', 'operationType': 'Repo', 'totalAmtAccepted': 1000000}]}}
        r = zd.parse_rrp(j)
        self.assertEqual(r['d'], [['2026-09-22', 453], ['2026-09-23', 461]])
        self.assertEqual(r['asof'], '2026-09-23')

    def test_soma_total_last_twelve_weeks(self):
        rows = [{'asOfDate': f'2026-0{1 + i // 4}-{1 + 7 * (i % 4):02d}', 'total': str((6000000 + i) * 1e6)} for i in range(16)]
        s = zd.parse_soma({'soma': {'summary': rows}})
        self.assertEqual(len(s['d']), 12)
        self.assertEqual(s['d'][-1][1], 6000015)

    def test_tgb_series_mapped_by_country(self):
        j = {'structure': {'dimensions': {'series': [{'id': 'FREQ', 'values': [{'id': 'M'}]}, {'id': 'REF_AREA', 'values': [{'id': 'DE'}, {'id': 'IT'}]}],
                                          'observation': [{'id': 'TIME_PERIOD', 'values': [{'id': '2026-06'}, {'id': '2026-07'}]}]}},
             'dataSets': [{'series': {'0:0': {'observations': {'0': [1043208.02], '1': [1037116.1]}},
                                      '0:1': {'observations': {'0': [None], '1': [-331168.67]}}}}]}
        g = zd.parse_tgb(j)
        self.assertEqual(g['q']['DE'], [['2026-06', 1043208.02], ['2026-07', 1037116.1]])
        self.assertEqual(g['q']['IT'], [['2026-07', -331168.67]])       # brak obserwacji pominięty, nie zero
        self.assertEqual(g['asof'], '2026-07')

    def test_mof_period_and_columns(self):
        self.assertEqual(zd._mof_period('2026．9．6～9．12'), ('2026-09-06', '2026-09-12'))
        self.assertEqual(zd._mof_period('2025．12．28～2026．1．3'), ('2025-12-28', '2026-01-03'))
        self.assertEqual(zd._mof_period('2025．12．28～1．3'), ('2025-12-28', '2026-01-03'))
        self.assertIsNone(zd._mof_period('razem'))
        head = 'tytul,,,,,,,,,,,,,,,,,,,,,,\n"期間\nPeriod",a,b,c,d,e,f,g,h,i,j,k,l,m,n,o,p,q,r,s,t,u,v\n'
        row = '2026．9．6～9．12,"30,037 ","28,345 ","1,692 ","117,497 ","106,668 ","10,829 ","12,521 ","18,524 ","17,015 ","1,508 ","14,029 ","381,075 ","396,303 ","-15,228 ","75,958 ","53,597 ","22,362 ","7,133 ","32,871 ","45,000 ","-12,128 ","-4,995 "\n'
        m = zd.parse_mof((head + row + '(Note 1),uwaga\n').encode('cp932'))
        self.assertEqual(len(m['d']), 1)
        w = m['d'][0]
        self.assertEqual((w['from'], w['to']), ('2026-09-06', '2026-09-12'))
        self.assertEqual(w['assets']['equity_net'], 1692.0); self.assertEqual(w['assets']['total_net'], 14029.0)
        self.assertEqual(w['liabilities']['equity_net'], -15228.0); self.assertEqual(w['liabilities']['total_net'], -4995.0)
        self.assertEqual(m['unit'], '100 mln JPY')

    def test_one_failing_source_does_not_erase_the_others(self):
        def get_json(url, headers=None):
            if 'fiscaldata' in url: raise RuntimeError('timeout')
            if 'reverserepo' in url: return {'repo': {'operations': [{'operationDate': '2026-09-23', 'operationType': 'Reverse Repo', 'totalAmtAccepted': 1e6}]}}
            if 'soma' in url: return {'soma': {'summary': [{'asOfDate': '2026-09-16', 'total': '6.364e12'}]}}
            if 'ecb' in url: raise RuntimeError('503')
            raise AssertionError(url)
        with mock.patch.object(zd, 'get_json', get_json), mock.patch.object(zd, 'get_bytes', side_effect=RuntimeError('cp932')):
            out = zd.build_instytucje()
        self.assertEqual(sorted(k for k in out if k not in ('at', 'src')), ['rrp', 'soma'])
        self.assertEqual(zd.META['ok'], {'tga': False, 'rrp': True, 'soma': True, 'tgb': False, 'ilm': False, 'm3': False, 'mof': False})
        self.assertEqual(len(zd.META['errors']), 5)

    def test_all_sources_failing_is_an_error(self):
        with mock.patch.object(zd, 'get_json', side_effect=RuntimeError('down')), mock.patch.object(zd, 'get_bytes', side_effect=RuntimeError('down')):
            with self.assertRaises(RuntimeError):
                zd.build_instytucje()


class MainFlowInstytucje(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj)); self.p_save.start()

    def tearDown(self):
        self.p_save.stop()

    def test_young_previous_file_is_reused(self):
        prev = {'at': _iso(10), 'tga': {'d': [['2026-09-22', 1]]}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'instytucje' else None), \
             mock.patch.object(zd, 'build_instytucje', side_effect=AssertionError('bez zapytań')):
            zd.main()
        self.assertIs(self.saved['instytucje'], prev); self.assertEqual(zd.META['ok']['instytucje'], 'cached')

    def test_failure_keeps_previous_and_reports(self):
        prev = {'at': _iso(180), 'tga': {'d': [['2026-09-22', 1]]}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'instytucje' else None), \
             mock.patch.object(zd, 'build_instytucje', side_effect=RuntimeError('nic nie odpowiedziało')):
            zd.main()
        self.assertIs(self.saved['instytucje'], prev); self.assertIs(zd.META['ok']['instytucje'], False)
        self.assertIn('instytucje: nic nie odpowiedziało', zd.META['errors'])


class ParseFred(unittest.TestCase):
    """B.2 zadania „więcej danych”: FRED API, '.' = brak (nigdy zero), rosnąco po dacie, tylko serie Fed."""

    def test_dot_and_empty_values_are_skipped_and_rows_ascend(self):
        j = {'observations': [{'date': '2026-09-23', 'value': '0.461'}, {'date': '2026-09-22', 'value': '.'},
                              {'date': '2026-09-21', 'value': ''}, {'date': '2026-09-19', 'value': '2.155'}]}
        out = zd.parse_fred(j, 'RRPONTSYD')
        self.assertEqual(out['d'], [['2026-09-19', 2.155], ['2026-09-23', 0.461]])
        self.assertEqual(out['asof'], '2026-09-23'); self.assertEqual(out['unit'], 'mld USD'); self.assertEqual(out['freq'], 'D')

    def test_weekly_series_in_millions_keeps_documented_value(self):
        j = {'observations': [{'date': '2026-09-16', 'value': '6746548.0'}, {'date': '2026-09-09', 'value': '6750000.0'}]}
        out = zd.parse_fred(j, 'WALCL')
        self.assertEqual(out['d'][-1], ['2026-09-16', 6746548.0]); self.assertEqual(out['unit'], 'mln USD')

    def test_no_observations_or_error_body_is_an_error_not_a_zero(self):
        with self.assertRaises(RuntimeError):
            zd.parse_fred({'observations': [{'date': '2026-09-16', 'value': '.'}]}, 'WALCL')
        with self.assertRaises(RuntimeError) as cm:
            zd.parse_fred({'error_code': 400, 'error_message': 'Bad Request. Variable api_key is not set.'}, 'WALCL')
        self.assertIn('api_key is not set', str(cm.exception))

    def test_only_fed_series_are_configured(self):
        self.assertEqual(sorted(zd.FRED_SERIES), ['DTWEXBGS', 'RRPONTSYD', 'WALCL', 'WTREGEN'])
        for third_party in ('SP500', 'VIXCLS', 'BAMLH0A0HYM2'):
            self.assertNotIn(third_party, zd.FRED_SERIES)
        self.assertIn('Board of Governors of the Federal Reserve System', zd.FRED_CITE)
        self.assertIn('not endorsed or certified by the Federal Reserve Bank of St. Louis', zd.FRED_API_NOTE)


class BuildFred(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.SECRETS[:] = ['TAJNY-FRED']
        self.p_sleep = mock.patch.object(zd.time, 'sleep', lambda s: None); self.p_sleep.start()

    def tearDown(self):
        self.p_sleep.stop(); zd.SECRETS[:] = []

    def test_one_failing_series_does_not_erase_the_others_and_key_never_leaks(self):
        def get_json(url, headers=None):
            self.assertIn('api_key=TAJNY-FRED', url); self.assertIn('file_type=json', url)
            if 'series_id=DTWEXBGS' in url:
                raise RuntimeError('HTTP 500 for ' + url)
            return {'observations': [{'date': '2026-09-16', 'value': '5'}]}
        with mock.patch.object(zd, 'get_json', get_json):
            out = zd.build_fred('TAJNY-FRED')
        self.assertEqual(sorted(out['series']), ['RRPONTSYD', 'WALCL', 'WTREGEN'])
        self.assertEqual(out['src'], zd.FRED_CITE); self.assertEqual(out['api_note'], zd.FRED_API_NOTE)
        self.assertTrue(any(e.startswith('FRED DTWEXBGS:') for e in zd.META['errors']))
        self.assertTrue(all('TAJNY' not in e for e in zd.META['errors']), zd.META['errors'])

    def test_all_series_failing_is_an_error(self):
        with mock.patch.object(zd, 'get_json', side_effect=RuntimeError('down')):
            with self.assertRaises(RuntimeError):
                zd.build_fred('TAJNY-FRED')


class MainFlowFred(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj)); self.p_save.start()
        self.p_inst = mock.patch.object(zd, 'build_instytucje', side_effect=RuntimeError('offline')); self.p_inst.start()

    def tearDown(self):
        self.p_save.stop(); self.p_inst.stop()

    def test_young_previous_file_is_reused_without_asking_fred(self):
        prev = {'at': _iso(10), 'series': {'WALCL': {'d': [['2026-09-16', 1.0]]}}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': '', 'FRED_KEY': 'TAJNY-FRED'}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'fred' else None), \
             mock.patch.object(zd, 'build_fred', side_effect=AssertionError('bez zapytań')):
            zd.main()
        self.assertIs(self.saved['fred'], prev); self.assertEqual(zd.META['ok']['fred'], 'cached')

    def test_failure_keeps_previous_and_reports(self):
        prev = {'at': _iso(180), 'series': {'WALCL': {'d': [['2026-09-16', 1.0]]}}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': '', 'FRED_KEY': 'TAJNY-FRED'}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'fred' else None), \
             mock.patch.object(zd, 'build_fred', side_effect=RuntimeError('żadna seria FRED nie odpowiedziała')):
            zd.main()
        self.assertIs(self.saved['fred'], prev); self.assertIs(zd.META['ok']['fred'], False)
        self.assertIn('FRED: żadna seria FRED nie odpowiedziała', zd.META['errors'])

    def test_missing_key_is_reported_and_no_file_is_written(self):
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': '', 'FRED_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: None), \
             mock.patch.object(zd, 'build_fred', side_effect=AssertionError('bez zapytań')):
            zd.main()
        self.assertNotIn('fred', self.saved); self.assertIs(zd.META['ok']['fred'], False); self.assertIn('brak FRED_KEY', zd.META['errors'])


class Eurosystem(unittest.TestCase):
    """B.3 zadania „więcej danych”: bilans Eurosystemu (ILM, tygodniowo) i M3 (BSI, miesięcznie) z ECB Data Portal."""

    @staticmethod
    def _sdmx(periods, values, n_series=1):
        series = {}
        for i in range(n_series):
            series[':'.join(['0'] * 6) if n_series == 1 else f'{i}:0:0:0:0:0'] = {'observations': {str(k): [v] for k, v in enumerate(values)}}
        return {'structure': {'dimensions': {'series': [{'id': 'FREQ', 'values': [{'id': 'W'}]}],
                                             'observation': [{'id': 'TIME_PERIOD', 'values': [{'id': p} for p in periods]}]}},
                'dataSets': [{'series': series}]}

    def test_ilm_weeks_map_to_friday_and_missing_is_skipped(self):
        j = self._sdmx(['2026-W36', '2026-W37', '2026-W38'], [5901000.4, None, 5898477])
        out = zd.parse_ilm(j)
        self.assertEqual(out['d'], [['2026-09-04', 5901000, '2026-W36'], ['2026-09-18', 5898477, '2026-W38']])
        self.assertEqual(out['asof'], '2026-09-18'); self.assertEqual(out['period'], '2026-W38'); self.assertEqual(out['unit'], 'mln EUR')

    def test_m3_monthly_keeps_period_and_documented_value(self):
        j = self._sdmx(['2026-05', '2026-06', '2026-07'], [17500000, 17550000, 17613983])
        out = zd.parse_m3(j)
        self.assertEqual(out['d'][-1], ['2026-07', 17613983]); self.assertEqual(out['asof'], '2026-07')

    def test_two_series_or_no_values_is_an_error_not_a_zero(self):
        with self.assertRaises(RuntimeError):
            zd.parse_ilm(self._sdmx(['2026-W38'], [1], n_series=2))
        with self.assertRaises(RuntimeError):
            zd.parse_m3(self._sdmx(['2026-07'], [None]))

    def test_iso_week_end(self):
        self.assertEqual(zd._iso_week_end('2026-W38'), '2026-09-18')
        self.assertEqual(zd._iso_week_end('2026-01'), None)

    def test_ecb_calls_are_spaced(self):
        calls = []
        with mock.patch.object(zd, 'get_json', lambda url, headers=None: {'u': url}), \
             mock.patch.object(zd.time, 'sleep', lambda s: calls.append(round(s, 1))), \
             mock.patch.object(zd.time, 'monotonic', lambda: 100.0):
            zd._ECB_LAST = -1e9
            zd._ecb_json('https://data-api.ecb.europa.eu/a'); zd._ecb_json('https://data-api.ecb.europa.eu/b')
        self.assertEqual(calls, [zd.ECB_SLEEP])         # pierwsze bez czekania, drugie po odstępie
        self.assertGreaterEqual(zd.ECB_SLEEP, 1.0)


if __name__ == '__main__':
    unittest.main()
