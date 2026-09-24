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
        self.assertEqual(self.saved['meta']['errors'], ['brak SOSOVALUE_KEY', 'brak FINNHUB_KEY'])


if __name__ == '__main__':
    unittest.main()
