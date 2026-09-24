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


class MainFlow(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear()
        zd.META['ok'].clear()
        self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj))
        self.p_save.start()

    def tearDown(self):
        self.p_save.stop()

    def test_young_previous_file_is_reused_without_asking_sosovalue(self):
        prev = {'at': _iso(10), 'assets': {'btc': {'day': [[1, 1.0]]}}}
        env = {'SOSOVALUE_KEY': 'k', 'FINNHUB_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'etf' else None), \
             mock.patch.object(zd, 'build_etf', side_effect=AssertionError('nie wolno pytać SoSoValue')):
            zd.main()
        self.assertIs(self.saved['etf'], prev)
        self.assertEqual(zd.META['ok']['sosovalue'], 'cached')

    def test_source_failure_keeps_previous_file_and_reports_error(self):
        prev = {'at': _iso(180), 'assets': {'btc': {'day': [[1, 1.0]]}}}
        env = {'SOSOVALUE_KEY': 'k', 'FINNHUB_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'etf' else None), \
             mock.patch.object(zd, 'build_etf', side_effect=RuntimeError('SoSoValue: 429')):
            zd.main()
        self.assertIs(self.saved['etf'], prev)                     # stary plik z prawdziwym „at”, nie pustka
        self.assertIs(zd.META['ok']['sosovalue'], False)
        self.assertTrue(any('SoSoValue' in e for e in zd.META['errors']))
        self.assertIn('finnhub', zd.META['ok'])
        self.assertIs(zd.META['ok']['finnhub'], False)              # brak klucza = jawny błąd, nie cisza

    def test_meta_is_always_written(self):
        env = {'SOSOVALUE_KEY': '', 'FINNHUB_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False):
            zd.main()
        self.assertIn('meta', self.saved)
        self.assertEqual(self.saved['meta']['errors'], ['brak SOSOVALUE_KEY', 'brak FINNHUB_KEY', 'brak TWELVEDATA_KEY'])
        self.assertNotIn('ceny', self.saved)                    # bez klucza pliku nie tworzymy


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

    def tearDown(self):
        self.p_save.stop()

    def test_young_previous_file_is_reused_without_asking_twelve_data(self):
        prev = {'at': _iso(10), 'q': {'SPY': {'d': [['2026-09-23', 1.0, 1]]}}}
        env = {'SOSOVALUE_KEY': '', 'FINNHUB_KEY': '', 'COINGECKO_KEY': '', 'TWELVEDATA_KEY': 'k'}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'ceny' else None), \
             mock.patch.object(zd, 'build_prices', side_effect=AssertionError('nie wolno pytać Twelve Data')):
            zd.main()
        self.assertIs(self.saved['ceny'], prev)
        self.assertEqual(zd.META['ok']['twelvedata'], 'cached')

    def test_source_failure_keeps_previous_file_and_reports_error(self):
        prev = {'at': _iso(180), 'q': {'SPY': {'d': [['2026-09-23', 1.0, 1]]}}}
        env = {'SOSOVALUE_KEY': '', 'FINNHUB_KEY': '', 'COINGECKO_KEY': '', 'TWELVEDATA_KEY': 'k'}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', lambda name: prev if name == 'ceny' else None), \
             mock.patch.object(zd, 'build_prices', side_effect=RuntimeError('HTTP 429')):
            zd.main()
        self.assertIs(self.saved['ceny'], prev)
        self.assertIs(zd.META['ok']['twelvedata'], False)
        self.assertIn('Twelve Data: HTTP 429', zd.META['errors'])

    def test_missing_key_is_reported_and_no_file_is_written(self):
        env = {'SOSOVALUE_KEY': '', 'FINNHUB_KEY': '', 'COINGECKO_KEY': '', 'TWELVEDATA_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), \
             mock.patch.object(zd, 'previous', side_effect=AssertionError('bez klucza nie pytamy o poprzedni plik')):
            zd.main()
        self.assertNotIn('ceny', self.saved)
        self.assertIn('brak TWELVEDATA_KEY', zd.META['errors'])
        self.assertIs(zd.META['ok']['twelvedata'], False)


if __name__ == '__main__':
    unittest.main()
