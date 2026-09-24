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
        self.assertNotIn('finnhub', zd.META['ok'])                # Finnhub nie jest już zbierany (licencja: użytek osobisty)

    def test_meta_is_always_written(self):
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False):
            zd.main()
        self.assertIn('meta', self.saved)
        self.assertEqual([e for e in self.saved['meta']['errors'] if not e.startswith('instytucje') and not e.startswith('poprzedni')], ['brak SOSOVALUE_KEY'])

    def test_no_quotes_are_collected_or_published(self):
        """Finnhub i Twelve Data: darmowe plany tylko do użytku osobistego — zbieracz ich nie dotyka (LICENCJE-zrodel.md)."""
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': '', 'FINNHUB_KEY': 'k', 'TWELVEDATA_KEY': 'k'}
        with mock.patch.dict(os.environ, env, clear=False):
            zd.main()
        self.assertEqual(sorted(k for k in zd.META['ok'] if k not in ('instytucje', 'tga', 'rrp', 'soma', 'tgb', 'mof')), ['sosovalue'])
        self.assertNotIn('dzis', self.saved)
        self.assertNotIn('ceny', self.saved)
        self.assertFalse(hasattr(zd, 'build_day'))
        self.assertFalse(hasattr(zd, 'build_prices'))
        src = open(zd.__file__, encoding='utf-8').read()
        self.assertNotIn('finnhub.io', src)
        self.assertNotIn('FINNHUB_KEY', src)
        self.assertNotIn('twelvedata.com', src)
        self.assertNotIn('TWELVEDATA_KEY', src)


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
        self.assertEqual(zd.META['ok'], {'tga': False, 'rrp': True, 'soma': True, 'tgb': False, 'mof': False})
        self.assertEqual(len(zd.META['errors']), 3)

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


if __name__ == '__main__':
    unittest.main()
