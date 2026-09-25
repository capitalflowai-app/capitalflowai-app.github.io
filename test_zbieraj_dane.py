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
        # v49: moneta bez danych jest pomijana (brak klucza, błąd zapisany), pozostałe zostają; wszystkie puste = błąd
        history = {'btc': _rows(['2026-09-23']), 'eth': [], 'sol': _rows(['2026-09-23']), 'xrp': _rows(['2026-09-23'])}
        with mock.patch.object(zd, 'soso', _soso_factory(history, {}, {})):
            out = zd.build_etf('klucz', '')
        self.assertNotIn('eth', out['assets']); self.assertEqual(sorted(out['assets']), ['btc', 'sol', 'xrp'])
        self.assertTrue(any(e.startswith('SoSoValue ETH') for e in zd.META['errors']))
        empty = {'btc': [], 'eth': [], 'sol': [], 'xrp': []}
        with mock.patch.object(zd, 'soso', _soso_factory(empty, {}, {})):
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
        self.p_kr = mock.patch.object(zd, 'build_krypto', side_effect=RuntimeError('offline')); self.p_kr.start()
        self.p_tic = mock.patch.object(zd, 'build_tic', side_effect=RuntimeError('offline')); self.p_tic.start()
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.p_v50]   # v50: nowe źródła w testach przepływu głównego bez sieci

    def tearDown(self):
        self.p_save.stop()
        self.p_inst.stop()
        self.p_kr.stop(); self.p_tic.stop()
        [p.stop() for p in self.p_v50]

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
        self.assertEqual([e for e in self.saved['meta']['errors'] if not e.startswith(('instytucje', 'poprzedni', 'krypto', 'TIC', 'BIS', 'CFTC', 'Coin Metrics', 'MFW', 'EBC kursy', 'obce', 'NSDL', 'TWSE', 'SAFE', 'Eurostat'))],
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
        self.p_kr = mock.patch.object(zd, 'build_krypto', side_effect=RuntimeError('offline')); self.p_kr.start()
        self.p_tic = mock.patch.object(zd, 'build_tic', side_effect=RuntimeError('offline')); self.p_tic.start()
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.p_v50]   # v50: nowe źródła w testach przepływu głównego bez sieci

    def tearDown(self):
        self.p_save.stop()
        self.p_inst.stop()
        self.p_kr.stop(); self.p_tic.stop()
        [p.stop() for p in self.p_v50]

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
        self.assertEqual(zd.META['ok'], {'tga': False, 'rrp': True, 'soma': True, 'tgb': False, 'ilm': False, 'm3': False, 'bop': False, 'mof': False})
        self.assertEqual(len(zd.META['errors']), 8)   # v49: bop ca + bop fa + bop razem

    def test_all_sources_failing_is_an_error(self):
        with mock.patch.object(zd, 'get_json', side_effect=RuntimeError('down')), mock.patch.object(zd, 'get_bytes', side_effect=RuntimeError('down')):
            with self.assertRaises(RuntimeError):
                zd.build_instytucje()


class MainFlowInstytucje(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj)); self.p_save.start()
        self.p_kr = mock.patch.object(zd, 'build_krypto', side_effect=RuntimeError('offline')); self.p_kr.start()
        self.p_tic = mock.patch.object(zd, 'build_tic', side_effect=RuntimeError('offline')); self.p_tic.start()
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.p_v50]   # v50: nowe źródła w testach przepływu głównego bez sieci

    def tearDown(self):
        self.p_save.stop(); self.p_kr.stop(); self.p_tic.stop()
        [p.stop() for p in self.p_v50]

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
        self.assertEqual(sorted(zd.FRED_SERIES), ['DTWEXBGS', 'RRPONTSYD', 'WALCL', 'WFASECL1', 'WMTSECL1', 'WSEFINOL', 'WSEFINTL1', 'WTREGEN'])   # v50: + depozyt H.4.1
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
        self.assertEqual(sorted(out['series']), ['RRPONTSYD', 'WALCL', 'WFASECL1', 'WMTSECL1', 'WSEFINOL', 'WSEFINTL1', 'WTREGEN'])   # v50: + depozyt H.4.1
        self.assertEqual(out['custody']['total'], 5.0); self.assertIsNone(out['custody']['d1w'])   # jedna środa: zmiany = brak, nie zero
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
        self.p_kr = mock.patch.object(zd, 'build_krypto', side_effect=RuntimeError('offline')); self.p_kr.start()
        self.p_tic = mock.patch.object(zd, 'build_tic', side_effect=RuntimeError('offline')); self.p_tic.start()
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.p_v50]   # v50: nowe źródła w testach przepływu głównego bez sieci

    def tearDown(self):
        self.p_save.stop(); self.p_inst.stop(); self.p_kr.stop(); self.p_tic.stop()
        [p.stop() for p in self.p_v50]

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


class Krypto(unittest.TestCase):
    """Sekcja C zadania „więcej danych” (część bez zgód): open interest i DeFi z CoinGecko, Fear & Greed z Alternative.me."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def test_deriv_sums_only_numeric_open_interest_and_keeps_top5(self):
        j = [{'name': 'Binance (Futures)', 'open_interest_btc': 410657.33}, {'name': 'X', 'open_interest_btc': None},
             {'name': 'Y', 'open_interest_btc': '12'}, {'name': 'Z', 'open_interest_btc': 100.004}]
        d = zd.parse_deriv(j)
        self.assertEqual(d['n'], 2); self.assertEqual(d['total_oi_btc'], 410757.33); self.assertEqual(d['top'][0], ['Binance (Futures)', 410657.33])
        with self.assertRaises(RuntimeError):
            zd.parse_deriv([{'name': 'X', 'open_interest_btc': None}])

    def test_defi_numbers_from_text_and_missing_is_none(self):
        d = zd.parse_defi({'data': {'defi_market_cap': '131076415637.0771', 'defi_to_eth_ratio': '39.9998', 'trading_volume_24h': None, 'defi_dominance': '4.4055'}})
        self.assertAlmostEqual(d['defi_market_cap'], 131076415637.0771); self.assertIsNone(d['trading_volume_24h']); self.assertIsNone(d['eth_market_cap'])
        with self.assertRaises(RuntimeError):
            zd.parse_defi({'data': {'defi_market_cap': None}})

    def test_fng_days_ascending_and_bad_values_skipped(self):
        j = {'data': [{'value': '71', 'value_classification': 'Greed', 'timestamp': '1790208000'},
                      {'value': '78', 'value_classification': 'Extreme Greed', 'timestamp': '1790035200'},
                      {'value': 'x', 'value_classification': '?', 'timestamp': '1790121600'}]}
        f = zd.parse_fng(j)
        self.assertEqual(f['d'], [['2026-09-22', 78, 'Extreme Greed'], ['2026-09-24', 71, 'Greed']])
        self.assertEqual(f['asof'], '2026-09-24'); self.assertEqual(f['kind'], 'indicator')

    def test_one_failing_part_does_not_erase_the_others_and_key_is_a_header(self):
        seen = {}
        def get_json(url, headers=None):
            seen[url] = headers
            if 'derivatives' in url: raise RuntimeError('429')
            if 'defi' in url: return {'data': {'defi_market_cap': '1'}}
            return {'data': [{'value': '50', 'value_classification': 'Neutral', 'timestamp': '1790208000'}]}
        with mock.patch.object(zd, 'get_json', get_json):
            out = zd.build_krypto('TAJNY-CG')
        self.assertEqual(sorted(k for k in out if k not in ('at', 'src', 'attribution')), ['defi', 'fng'])
        self.assertEqual(out['attribution'], 'Data by CoinGecko')
        self.assertEqual(zd.META['ok'], {'krypto.deriv': False, 'krypto.defi': True, 'krypto.fng': True, 'krypto.mk': False, 'krypto.stabh': False, 'krypto.stabc': False})
        self.assertTrue(all('TAJNY' not in u for u in seen), 'klucz nie w adresie')
        self.assertEqual(seen[zd.CG + '/global/decentralized_finance_defi'], {'x-cg-demo-api-key': 'TAJNY-CG'})
        self.assertIsNone(seen[zd.FNG_URL])

    def test_all_parts_failing_is_an_error(self):
        with mock.patch.object(zd, 'get_json', side_effect=RuntimeError('down')):
            with self.assertRaises(RuntimeError):
                zd.build_krypto('')


class MainFlowKrypto(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj)); self.p_save.start()
        self.p_inst = mock.patch.object(zd, 'build_instytucje', side_effect=RuntimeError('offline')); self.p_inst.start()
        self.p_kr = mock.patch.object(zd, 'build_krypto', side_effect=RuntimeError('offline')); self.p_kr.start()
        self.p_tic = mock.patch.object(zd, 'build_tic', side_effect=RuntimeError('offline')); self.p_tic.start()
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.p_v50]   # v50: nowe źródła w testach przepływu głównego bez sieci

    def tearDown(self):
        self.p_save.stop(); self.p_inst.stop(); self.p_kr.stop(); self.p_tic.stop()
        [p.stop() for p in self.p_v50]

    def test_young_previous_file_is_reused(self):
        prev = {'at': _iso(10), 'fng': {'d': [['2026-09-24', 71, 'Greed']]}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'krypto' else None), \
             mock.patch.object(zd, 'build_krypto', side_effect=AssertionError('bez zapytań')):
            zd.main()
        self.assertIs(self.saved['krypto'], prev); self.assertEqual(zd.META['ok']['krypto'], 'cached')

    def test_failure_keeps_previous_and_reports(self):
        prev = {'at': _iso(180), 'fng': {'d': [['2026-09-24', 71, 'Greed']]}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'krypto' else None), \
             mock.patch.object(zd, 'build_krypto', side_effect=RuntimeError('żadne źródło rynku krypto nie odpowiedziało')):
            zd.main()
        self.assertIs(self.saved['krypto'], prev); self.assertIs(zd.META['ok']['krypto'], False)
        self.assertIn('krypto: żadne źródło rynku krypto nie odpowiedziało', zd.META['errors'])


class BilansPlatniczy(unittest.TestCase):
    """B.4 zadania „więcej danych”: bilans płatniczy strefy euro z ECB Data Portal (BPS), miesięcznie."""

    @staticmethod
    def _multi(keys_rows, periods):
        # dwie serie zakodowane przez indeksy wymiarów: wymiar 0 = STO-like z wartościami po kolei
        vals = [{'id': k} for k in keys_rows]
        series = {f'{i}': {'observations': {str(j): [v] for j, v in enumerate(rows)}} for i, (k, rows) in enumerate(keys_rows.items())}
        return {'structure': {'dimensions': {'series': [{'id': 'KEY', 'values': vals}],
                                             'observation': [{'id': 'TIME_PERIOD', 'values': [{'id': p} for p in periods]}]}},
                'dataSets': [{'series': series}]}

    def test_multi_series_are_mapped_by_full_key_and_missing_is_skipped(self):
        j = self._multi({'A': [1.5, None, 3], 'B': [None, None, None]}, ['2026-05', '2026-06', '2026-07'])
        m = zd.parse_ecb_multi(j)
        self.assertEqual(m, {'A': [['2026-05', 1.5], ['2026-07', 3]]})

    def test_bop_keeps_components_and_missing_series_is_none_not_zero(self):
        periods = ['2026-06', '2026-07']
        fa = {'structure': {'dimensions': {'series': [{'id': 'K', 'values': [{'id': k} for k in zd.BOP_FA_KEYS]}],
                                           'observation': [{'id': 'TIME_PERIOD', 'values': [{'id': p} for p in periods]}]}},
              'dataSets': [{'series': {'0': {'observations': {'0': [10220.7459], '1': [11368.5966]}},        # fa
                                       '2': {'observations': {'0': [-204704.2331], '1': [-21793.6606]}}}}]}  # pi
        ca = {'structure': {'dimensions': {'series': [{'id': 'K', 'values': [{'id': 'CA'}]}],
                                           'observation': [{'id': 'TIME_PERIOD', 'values': [{'id': p} for p in periods]}]}},
              'dataSets': [{'series': {'0': {'observations': {'0': [30000.4], '1': [36516.5003]}}}}]}
        b = zd.parse_bop(ca, fa)
        self.assertEqual(b['s']['ca'], [['2026-06', 30000], ['2026-07', 36517]])
        self.assertEqual(b['s']['fa'], [['2026-06', 10221], ['2026-07', 11369]])
        self.assertEqual(b['s']['pi'], [['2026-06', -204704], ['2026-07', -21794]])
        for k in ('di', 'pi_eq', 'pi_debt', 'oi'):
            self.assertIsNone(b['s'][k], k)
        self.assertEqual(b['asof'], '2026-07'); self.assertEqual(b['unit'], 'mln EUR'); self.assertIn('positive = net outflow', b['sign'])

    def test_bop_without_any_series_is_an_error(self):
        empty = {'structure': {'dimensions': {'series': [{'id': 'K', 'values': []}], 'observation': [{'id': 'TIME_PERIOD', 'values': []}]}}, 'dataSets': [{'series': {}}]}
        with self.assertRaises(RuntimeError):
            zd.parse_bop(None, empty)
        self.assertEqual(sorted(zd.BOP_FA_KEYS.values()), ['di', 'fa', 'oi', 'pi', 'pi_debt', 'pi_eq'])


class Tic(unittest.TestCase):
    """Sekcja A zadania „więcej danych”: TIC SLT — tabulatory, nagłówek techniczny, brak = None, sumy po regionach z liczbą obecnych."""
    T1 = ("Table 1\nAll Countries\nnote\nMillions of dollars\nLink\n\n|||Total\nCountry\tCountry Code\tDate\tHoldings\tNet\tVal\n"
          "country\tcountry_code\tdate\tfor_lt_total_pos\tfor_lt_total_net\tfor_lt_total_valchg\tfor_lt_treas_pos\tfor_lt_treas_net\tfor_lt_treas_valchg\tfor_lt_agcy_pos\tfor_lt_agcy_net\tfor_lt_agcy_valchg\tfor_lt_corp_pos\tfor_lt_corp_net\tfor_lt_corp_valchg\tfor_lt_eqty_pos\tfor_lt_eqty_net\tfor_lt_eqty_valchg\n"
          "Japan\t42609\t2026-07\t2998094\t-6454\t-34194\t1023754\t-8846\t-12120\t269484\t-1096\t-5091\t312507\t1495\t-5349\t1392349\t1993\t-11634\n"
          "Japan\t42609\t2026-06\t3000000\t100\t0\t1000000\t50\t0\t1\t1\t1\t1\t1\t1\t1\t40\t1\n"
          "Korea, South\t42500\t2026-07\t100\t\t0\t1\t2\t3\t4\t5\t6\t7\t8\t9\t10\t11\t12\n"
          "Grand Total\t99996\t2026-07\t38820547\t40616\t-527089\t7783259\t-3560\t-101562\t1\t1\t1\t1\t1\t1\t24341164\t3705\t-304335\n"
          "Euro area:  As of January 2026, includes Austria\n"
          "for_lt_total_net: 3 + 7 - 2\n")

    def test_table_parsed_by_technical_header_blanks_are_none_footer_ignored(self):
        t = zd.parse_tic_table(self.T1.encode())
        self.assertEqual(t['Japan']['2026-07']['for_lt_total_net'], -6454.0); self.assertEqual(t['Japan']['2026-07']['for_lt_eqty_net'], 1993.0)
        self.assertIsNone(t['Korea, South']['2026-07']['for_lt_total_net'])       # puste pole = brak, nie zero
        self.assertNotIn('Euro area:  As of January 2026, includes Austria', t); self.assertNotIn('for_lt_total_net: 3 + 7 - 2', t)
        with self.assertRaises(RuntimeError):
            zd.parse_tic_table(b'no header\n')

    def test_region_sums_count_present_members_and_missing_is_none(self):
        t = zd.parse_tic_table(self.T1.encode())
        rows = zd._tic_sum(t, ['Japan', 'Korea, South', 'Taiwan'], ['2026-06', '2026-07'], 'for_lt_total_net')
        self.assertEqual(rows, [['2026-06', 100, 1], ['2026-07', -6454, 1]])     # Korea bez liczby, Tajwanu brak → tylko Japonia
        rows = zd._tic_sum(t, ['Taiwan'], ['2026-07'], 'for_lt_total_net')
        self.assertEqual(rows, [['2026-07', None, 0]])

    def test_holders_table_in_billions_with_grand_total(self):
        raw = ("Table 5\nHoldings\nBillions of dollars\nLink\n\nCountry\t2026-07\t2026-06\t2026-05\nJapan\t1103.9\t1116.7\t1143.1\n"
               "United Kingdom\t998.3\t939.9\t948.6\nAll Other\t1842.4\t1850.3\t1\nGrand Total\t9248.1\t9298.5\t9300.0\nOf Which: Foreign Official\t3773.1\t3778.1\t1\n")
        h = zd.parse_tic_holders(raw.encode())
        self.assertEqual(h['months'], ['2026-07', '2026-06', '2026-05'])
        self.assertEqual(h['rows'][0], ['Japan', [1103.9, 1116.7, 1143.1]]); self.assertEqual(h['rows'][-1], ['Grand Total', [9248.1, 9298.5, 9300.0]])
        self.assertFalse(any(r[0].startswith('Of Which') or r[0] == 'All Other' for r in h['rows']))

    def test_build_tic_regions_world_and_optional_tables(self):
        t2 = ("x\n" * 8 + "country\tcountry_code\tdate\tus_lt_total_pos\tus_lt_total_net\tus_lt_total_valchg\tus_lt_govt_bond_pos\tus_lt_govt_bond_net\tus_lt_govt_bond_valchg\tus_lt_corp_bond_pos\tus_lt_corp_bond_net\tus_lt_corp_bond_valchg\tus_lt_eqty_pos\tus_lt_eqty_net\tus_lt_eqty_valchg\n"
              "Japan\t42609\t2026-07\t1750866\t20746\t-525\t1\t2\t3\t4\t5\t6\t7\t8\t9\nGrand Total\t99996\t2026-07\t20356009\t68522\t-158325\t1\t2\t3\t4\t5\t6\t7\t8\t9\n")
        def get_bytes(url, headers=None, timeout=60):
            if 'table1' in url: return self.T1.encode()
            if 'table2' in url: return t2.encode()
            raise RuntimeError('503')
        with mock.patch.object(zd, 'get_bytes', get_bytes):
            out = zd.build_tic()
        self.assertEqual(out['asof'], '2026-07'); self.assertEqual(out['months'], ['2026-06', '2026-07']); self.assertEqual(out['unit'], 'mln USD')
        jp = out['regions']['jpn']
        self.assertEqual(jp['in'], [['2026-06', 100, 1], ['2026-07', -6454, 1]]); self.assertEqual(jp['out'], [['2026-06', None, 0], ['2026-07', 20746, 1]])
        self.assertEqual(jp['hold_in'], ['2026-07', 2998194, 2]); self.assertEqual(jp['hold_out'], ['2026-07', 1750866, 1]); self.assertEqual(jp['n'], 2)   # Japonia + Korea (Tajwan osobno)
        self.assertEqual(jp['net'], [['2026-06', None, 0], ['2026-07', -27200, 1]])   # netto tylko z krajów obecnych w obu tabelach
        self.assertIn('twn', out); self.assertEqual(out['twn']['members'], ['Taiwan'])
        self.assertEqual(out['world']['in'][-1], ['2026-07', 40616, 1]); self.assertEqual(out['world']['out'][-1], ['2026-07', 68522, 1])
        self.assertEqual(out['regions']['can']['in'][-1], ['2026-07', None, 0])           # brak Kanady w próbce → brak, nie zero
        self.assertIsNone(out['holders']); self.assertTrue(any(e.startswith('TIC tabela 5') for e in zd.META['errors']))
        self.assertIn('positive = capital into the USA', out['sign'])


class KryptoV49(unittest.TestCase):
    """v49: zmiany 30D/1R z CoinGecko (CoinPaprika free zwraca 0) i historia podaży stablecoinów na serwerze."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def test_markets_rows_dedupe_symbols_and_missing_is_none(self):
        p1 = [{'symbol': 'btc', 'market_cap': 1.69e12, 'price_change_percentage_24h_in_currency': -0.07, 'price_change_percentage_7d_in_currency': 10.2,
               'price_change_percentage_30d_in_currency': 6.5954, 'price_change_percentage_1y_in_currency': -25.7682, 'last_updated': '2026-09-24T20:35:20.000Z'},
              {'symbol': 'btc', 'market_cap': 1, 'price_change_percentage_30d_in_currency': 99},
              {'symbol': 'usdt', 'market_cap': 1.8e11, 'price_change_percentage_1y_in_currency': None}]
        m = zd.parse_mk([p1, []])
        self.assertEqual(m['rows'][0], ['BTC', 1.69e12, -0.07, 10.2, 6.5954, -25.7682])
        self.assertEqual(len(m['rows']), 2); self.assertIsNone(m['rows'][1][5]); self.assertEqual(m['asof'], '2026-09-24T20:35:20')
        with self.assertRaises(RuntimeError):
            zd.parse_mk([{'error': 'x'}])

    def test_stablecoin_history_changes_are_supply_not_price(self):
        day = 86400; t0 = 1790208000
        j = [{'date': str(t0 - k * day), 'totalCirculatingUSD': {'peggedUSD': 300e9 + (400 - k) * 1e8}} for k in range(400, -1, -1)]
        h = zd.parse_stabh(j)
        self.assertEqual(h['asof'], '2026-09-24'); self.assertEqual(h['cur'], round(300e9 + 400 * 1e8))
        self.assertEqual(h['d']['1'], round(1e8)); self.assertEqual(h['d']['30'], round(30e8)); self.assertEqual(h['d']['365'], round(365e8))
        self.assertAlmostEqual(h['pct']['7'], round((340e9 / (340e9 - 7e8) - 1) * 100, 4))
        with self.assertRaises(RuntimeError):
            zd.parse_stabh([{'date': '1', 'totalCirculatingUSD': {'peggedUSD': 1}}])


class RobustnessV49(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.SECRETS[:] = []   # inne testy uruchamiają main() z kluczami z otoczenia

    def test_one_finnhub_symbol_error_does_not_stop_the_rest(self):
        calls = []
        def get(url, headers=None, timeout=30):
            calls.append(url)
            if 'symbol=EWC' in url:
                raise RuntimeError('HTTP 429 for token=TAJNY')
            return 200, json.dumps({'c': 10.0, 'pc': 9.0, 'dp': 11.1, 't': 1})
        zd.SECRETS[:] = ['TAJNY']
        try:
            with mock.patch.object(zd, 'get', get), mock.patch.object(zd.time, 'sleep', lambda s: None):
                out = zd.build_day('TAJNY')
        finally:
            zd.SECRETS[:] = []
        self.assertEqual(len(calls), len(zd.DAY_SYMS)); self.assertNotIn('EWC', out['q']); self.assertEqual(len(out['q']), len(zd.DAY_SYMS) - 1)
        self.assertTrue(any(e.startswith('Finnhub EWC') and 'TAJNY' not in e for e in zd.META['errors']))

    def test_bop_current_account_failure_keeps_financial_account(self):
        fa = {'structure': {'dimensions': {'series': [{'id': 'K', 'values': [{'id': k} for k in zd.BOP_FA_KEYS]}],
                                           'observation': [{'id': 'TIME_PERIOD', 'values': [{'id': '2026-07'}]}]}},
              'dataSets': [{'series': {'0': {'observations': {'0': [11368.6]}}}}]}
        def ecb(url):
            if 'T.B.CA.' in url: raise RuntimeError('access blocked')
            return fa
        with mock.patch.object(zd, '_ecb_json', ecb):
            b = zd.parse_bop(zd._ecb_try(zd.BOP_CA_URL, 'bop ca'), zd._ecb_try(zd.BOP_FA_URL, 'bop fa'))
        self.assertIsNone(b['s']['ca']); self.assertEqual(b['s']['fa'], [['2026-07', 11369]])
        self.assertIn('bop ca: access blocked', zd.META['errors'])


class BisLbs(unittest.TestCase):
    """v50: BIS LBS miara F — prawdziwe wiersze z odpowiedzi BIS z 24.09.2026 (wycinek), brak = None, salda na parach krajów."""
    HEAD = ('FREQ,L_MEASURE,L_POSITION,L_INSTR,L_DENOM,L_CURR_TYPE,L_PARENT_CTY,L_REP_BANK_TYPE,L_REP_CTY,L_CP_SECTOR,'
            'L_CP_COUNTRY,L_POS_TYPE,DECIMALS,UNIT_MEASURE,UNIT_MULT,AVAILABILITY,TITLE_GRP,TIME_FORMAT,COLLECTION,'
            'ORG_VISIBILITY,TIME_PERIOD,OBS_VALUE,OBS_STATUS,OBS_CONF,OBS_PRE_BREAK')
    # raportujący,kontrahent,kwartał,wartość (mln USD),status — wycinek odpowiedzi BIS_URL z 24.09.2026
    REAL = """GB,US,2025-Q4,-3166.185,A
GB,US,2026-Q1,194782.426,A
US,GB,2025-Q4,-30041.572,A
US,GB,2026-Q1,83065.607,A
DE,US,2025-Q4,-2044.566,A
DE,US,2026-Q1,83688.666,A
US,DE,2025-Q4,12255.226,A
US,DE,2026-Q1,-4162.079,A
FR,US,2025-Q4,-22266.654,A
FR,US,2026-Q1,9684.247,A
US,FR,2025-Q4,10462.481,A
US,FR,2026-Q1,-28926.626,A
IT,US,2025-Q4,-1689.259,A
IT,US,2026-Q1,845.285,A
US,IT,2025-Q4,1444.204,A
US,IT,2026-Q1,-297.234,A
ES,US,2025-Q4,9287.087,A
ES,US,2026-Q1,6161.192,A
US,ES,2025-Q4,-573.321,A
US,ES,2026-Q1,2499.191,A
NL,US,2025-Q4,3992.794,A
NL,US,2026-Q1,3636.218,A
US,NL,2025-Q4,-1535.223,A
US,NL,2026-Q1,1082.293,A
CH,US,2025-Q4,9277.264,A
CH,US,2026-Q1,198.058,A
US,CH,2025-Q4,-2172.68,A
US,CH,2026-Q1,2632.248,A
SE,US,2025-Q4,-7265.643,A
SE,US,2026-Q1,3402.082,A
US,SE,2025-Q4,-13091.585,A
US,SE,2026-Q1,11438.216,A
JP,US,2025-Q4,69752.073,A
JP,US,2026-Q1,108345.812,A
KR,US,2025-Q4,3712.058,A
KR,US,2026-Q1,3205.537,A
HK,US,2025-Q4,30742.922,A
HK,US,2026-Q1,-18637.593,A
US,JP,2025-Q4,31172.02,A
US,JP,2026-Q1,-23517.386,A
US,KR,2025-Q4,-66.076,A
US,KR,2026-Q1,988.328,A
US,HK,2025-Q4,-6669.386,A
US,HK,2026-Q1,12479.868,A
ZA,GB,2025-Q4,1767.63,A
ZA,GB,2026-Q1,836.013,A
CA,RU,2025-Q4,-0.969,A
CA,RU,2026-Q1,0.132,A
AU,SG,2025-Q4,5986.833,A
AU,SG,2026-Q1,-483.505,A
AU,NZ,2025-Q4,389.123,A
AU,NZ,2026-Q1,1136.897,A
CA,MY,2025-Q4,NaN,Q
CA,MY,2026-Q1,NaN,Q
CA,MX,2025-Q4,NaN,Q
CL,EG,2022-Q2,-0.032,A
CL,IL,2022-Q2,-0.053,A"""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    @classmethod
    def row(cls, rep, cp, q, v, status='A', unit='USD', mult='6', measure='F'):
        return f'Q,{measure},C,A,TO1,A,5J,A,{rep},A,{cp},N,3,{unit},{mult},K,,,S,E,{q},{v},{status},F,'

    @classmethod
    def csv_of(cls, rows):
        return (cls.HEAD + '\n' + '\n'.join(rows) + '\n').encode()

    @classmethod
    def real(cls):
        return cls.csv_of([cls.row(*ln.split(',')) for ln in cls.REAL.splitlines()])

    # siedem par regionów (próg jakości to 6) w czterech kolejnych kwartałach
    Q4 = ['2025-Q2', '2025-Q3', '2025-Q4', '2026-Q1']

    def base4(self, skip=()):
        pairs = [('GB', 'US', 100), ('US', 'GB', 40), ('JP', 'US', 7), ('AU', 'SG', 2), ('ZA', 'GB', 3), ('CA', 'RU', 1), ('HK', 'IN', 5), ('BR', 'US', 4)]
        return [self.row(a, b, q, v) for a, b, v in pairs for q in self.Q4 if (a, b, q) not in skip]

    def test_real_rows_give_the_known_corridors(self):
        j = zd.parse_bis_flows(self.real(), at='2026-09-24T21:00:00+00:00')
        self.assertEqual(j['asof'], '2026-Q1'); self.assertEqual(j['unit'], 'mln USD')
        self.assertEqual(j['quarters'], ['2025-Q2', '2025-Q3', '2025-Q4', '2026-Q1'])   # okno 4 kolejnych kwartałów; stare 2022-Q2 nie liczą się
        f = j['flows']
        self.assertEqual(f['eur>usa'][-1], ['2026-Q1', 302398.2, 8])       # 8 krajów Europy → USA (tyle samo co w pełnej odpowiedzi)
        self.assertEqual(f['eur>usa'][-2], ['2025-Q4', -13875.2, 8])       # minus = banki ograniczyły należności
        self.assertEqual(f['usa>eur'][-1], ['2026-Q1', 67331.6, 8])
        self.assertEqual(f['jpn>usa'][-1], ['2026-Q1', 111551.3, 2])
        self.assertEqual(f['chn>usa'][-1], ['2026-Q1', -18637.6, 1])       # Chiny jako pożyczający = tylko Hongkong
        self.assertEqual(f['eur>usa'][0], ['2025-Q2', None, 0])            # kwartał w oknie bez danych = brak, nie zero
        self.assertIsNone(j['regions']['eur']['out4'])                     # suma 4 kwartałów tylko z kompletu
        self.assertEqual(f['can>rus'][-1], ['2026-Q1', 0.1, 1])            # 0,132 mln: mała liczba to liczba, nie brak
        self.assertNotIn('can>asean', f); self.assertNotIn('can>lat', f)   # Q (poufne) i NaN = brak, nie 0
        self.assertNotIn('oce>oce', f)                                     # AU→NZ: ten sam region
        self.assertIn('can|rus', j['oneway']); self.assertIn('eur|usa', j['pairs'])
        self.assertEqual(j['regions']['eur']['cp'], zd.BIS_CP['eur'])
        self.assertEqual(j['regions']['eur']['rep_q'][0], ['GB', 194782.4, 1])   # wkład Wielkiej Brytanii (Londyn) w wypływ Europy
        self.assertEqual(j['regions']['oce']['rep_q'], [['AU', -483.5, 1]])      # AU→NZ (ten sam region) nie jest wypływem regionu
        self.assertIn('rus', j['no_reporter']); self.assertIn('ind', j['no_reporter']); self.assertIn('mea', j['no_reporter'])
        self.assertTrue(all(x[1] is None and x[2] == 0 for x in j['regions']['rus']['out']))

    def test_net_uses_only_matched_country_pairs_and_sums_to_zero(self):
        j = zd.parse_bis_flows(self.real())
        v = {(a, b, q): float(x) for a, b, q, x, s in (ln.split(',') for ln in self.REAL.splitlines()) if s == 'A'}
        eur = sum(v[(c, 'US', '2026-Q1')] - v[('US', c, '2026-Q1')] for c in zd.BIS_CP['eur'])
        self.assertEqual(j['regions']['eur']['net'][-1], ['2026-Q1', round(eur, 1), 8])   # ZA→GB bez GB→ZA nie wchodzi do salda
        self.assertGreater(j['regions']['eur']['net'][-1][1], 0)                         # plus = Europa netto pożycza innym
        for i in range(4):
            s = sum(r['net'][i][1] for r in j['regions'].values() if r['net'][i][1] is not None)
            self.assertAlmostEqual(s, 0, delta=1.0)
        self.assertEqual(j['regions']['afr']['net'][-1], ['2026-Q1', None, 0])          # brak pary dwustronnej = brak, nie 0
        self.assertEqual(j['regions']['afr']['out'][-1], ['2026-Q1', 836.0, 1])

    def test_missing_statuses_nan_and_empty_are_missing_not_zero(self):
        rows = self.base4() + [self.row('DE', 'CN', '2026-Q1', 'NaN', 'Q'), self.row('DE', 'CN', '2025-Q4', '9', 'K'),
                               self.row('FR', 'CN', '2026-Q1', ''), self.row('IT', 'CN', '2026-Q1', '5', 'M')]
        j = zd.parse_bis_flows(self.csv_of(rows))
        self.assertNotIn('eur>chn', j['flows'])

    def test_totals_need_the_full_window(self):
        j = zd.parse_bis_flows(self.csv_of(self.base4()))
        self.assertEqual(j['regions']['eur']['out4'], 4 * 100 + 0.0)
        self.assertEqual(j['regions']['usa']['net4'], 4 * (40 - 100) + 0.0)
        j = zd.parse_bis_flows(self.csv_of(self.base4(skip={('GB', 'US', '2025-Q3')})))
        self.assertIsNone(j['regions']['eur']['out4']); self.assertEqual(j['flows']['eur>usa'][1], ['2025-Q3', None, 0])

    def test_latest_quarter_must_be_full(self):
        rows = self.base4() + [self.row('GB', 'US', '2026-Q2', '1')]      # szczątkowa świeża publikacja nie przesuwa okna
        j = zd.parse_bis_flows(self.csv_of(rows))
        self.assertEqual(j['asof'], '2026-Q1')

    def test_unit_multiplier_currency_measure_and_columns(self):
        j = zd.parse_bis_flows(self.csv_of(self.base4() + [self.row('DE', 'CN', '2026-Q1', '2', mult='9')]))
        self.assertEqual(j['flows']['eur>chn'][-1], ['2026-Q1', 2000.0, 1])   # 2 mld = 2000 mln
        with self.assertRaises(RuntimeError):
            zd.parse_bis_flows(self.csv_of(self.base4() + [self.row('DE', 'CN', '2026-Q1', '2', unit='EUR')]))
        j = zd.parse_bis_flows(self.csv_of(self.base4() + [self.row('DE', 'CN', '2026-Q1', '999999', measure='S')]))
        self.assertNotIn('eur>chn', j['flows'])                             # stan (S) zamiast zmiany (F) nie trafia do sum
        with self.assertRaises(RuntimeError):
            zd.parse_bis_flows(b'FREQ,TIME_PERIOD,OBS_VALUE\nQ,2026-Q1,1\n')
        with self.assertRaises(RuntimeError):
            zd.parse_bis_flows(self.csv_of([]))
        with self.assertRaises(RuntimeError):
            zd.parse_bis_flows(self.csv_of(self.base4()[:8]))               # za mało par regionów

    def test_url_is_measure_f_without_key_and_regions_are_consistent(self):
        self.assertIn('/Q.F.C.A.TO1.A.5J.A.', zd.BIS_URL); self.assertIn('lastNObservations=5', zd.BIS_URL)
        self.assertTrue(zd.BIS_URL.startswith('https://stats.bis.org/')); self.assertNotIn('key', zd.BIS_URL.lower())
        c2r = {c: r for r, cs in zd.BIS_CP.items() for c in cs}
        for r, cs in zd.BIS_REP.items():
            for c in cs:
                self.assertEqual(c2r[c], r)
        self.assertEqual(zd._bis_qshift('2026-Q1', 1), '2025-Q4'); self.assertEqual(zd._bis_qshift('2026-Q1', 4), '2025-Q1')

    def test_build_bis_single_request_with_file_time(self):
        calls = []
        def get_bytes(url, headers=None, timeout=60):
            calls.append((url, timeout)); return self.real()
        with mock.patch.object(zd, 'get_bytes', get_bytes):
            out = zd.build_bis()
        self.assertEqual(calls, [(zd.BIS_URL, 90)]); self.assertEqual(out['at'], zd.NOW)
        self.assertIn('positive = banks in a lent/placed more in b', out['sign'])
        self.assertLess(len(json.dumps(out)), 60000)


class MainFlowBis(unittest.TestCase):
    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.p_save = mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj)); self.p_save.start()
        self.p_off = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True)
                      for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.p_off]

    def tearDown(self):
        self.p_save.stop(); [p.stop() for p in self.p_off]

    def test_young_previous_file_is_reused(self):
        prev = {'at': _iso(60), 'asof': '2026-Q1', 'flows': {}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'bis' else None), \
             mock.patch.object(zd, 'build_bis', side_effect=AssertionError('bez zapytań')):
            zd.main()
        self.assertIs(self.saved['bis'], prev); self.assertEqual(zd.META['ok']['bis'], 'cached')

    def test_failure_keeps_previous_and_reports(self):
        prev = {'at': _iso(26 * 60), 'asof': '2026-Q1', 'flows': {}}
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'bis' else None), \
             mock.patch.object(zd, 'build_bis', side_effect=RuntimeError('HTTP Error 503')):
            zd.main()
        self.assertIs(self.saved['bis'], prev); self.assertIs(zd.META['ok']['bis'], False)
        self.assertIn('BIS: HTTP Error 503', zd.META['errors'])

    def test_fresh_build_is_saved(self):
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        new = {'at': zd.NOW, 'asof': '2026-Q1'}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: None), \
             mock.patch.object(zd, 'build_bis', return_value=new):
            zd.main()
        self.assertIs(self.saved['bis'], new); self.assertIs(zd.META['ok']['bis'], True)



# v50 CFTC: prawdziwe wiersze FinFutWk.txt (raport na 15.09.2026, pobrane 24.09.2026, końce linii CRLF jak w pliku CFTC);
# MICRO BITCOIN (133742) ma zostać pominięty. Historia w testach powstaje z tych wierszy (inna data, przesunięte pozycje).
_CFTC_WK = (
    '"EURO FX - CHICAGO MERCANTILE EXCHANGE",260915,2026-09-15,099741,CME ,00,099 ,  920035,   41113,  299193,    5144,  486435,  234737,   43899,  103260,  131416,   23388,   24818,   17063,    3579,  731636,  758419,  188399,  161616,  -22429,  -13244,  -16618,  -73160,    1992,     972,   -1665,    8452,    3323,  -37719,     231,     651,   -2934, -118047, -127150,   95618,  104721,  100.0,    4.5,   32.5,    0.6,   52.9,   25.5,    4.8,   11.2,   14.3,    2.5,    2.7,    1.9,    0.4,   79.5,   82.4,   20.5,   17.6,    318,     16,     13,      8,    116,     43,     49,     48,     48,     23,     21,     13,      6,    235,    169,    17.7,    30.6,    25.5,    45.6,    17.5,    30.6,    25.2,    44.5,"(CONTRACTS OF EUR 125,000)","099741","CME ","099 ","F10","FutOnly"\r\n'
    '"BITCOIN - CHICAGO MERCANTILE EXCHANGE",260915,2026-09-15,133741,CME ,00,133 ,   20773,    6587,    3168,     620,    4528,    1768,     486,    5545,   11899,    1841,     122,     136,      23,   19752,   19941,    1021,     832,    -310,    -212,    -688,      31,    -422,     561,     185,     399,   -1139,     585,    -647,      36,      23,     -58,    -406,    -252,      96,  100.0,   31.7,   15.3,    3.0,   21.8,    8.5,    2.3,   26.7,   57.3,    8.9,    0.6,    0.7,    0.1,   95.1,   96.0,    4.9,    4.0,    111,     12,      9,      4,      6,      7,      5,     26,     42,     16,      4,.,.,     63,     74,    61.0,    28.6,    71.7,    47.0,    59.6,    25.3,    68.2,    41.8,"(5 Bitcoins)","133741","CME ","133 ","F85","FutOnly"\r\n'
    '"MICRO BITCOIN - CHICAGO MERCANTILE EXCHANGE",260915,2026-09-15,133742,CME ,00,133 ,   37455,    3991,    6069,       0,    4700,     571,       0,   16881,   25363,     405,    6047,    2847,      87,   32111,   35342,    5344,    2113,    2276,    2804,    -116,       0,    3154,     532,     -10,   -2378,     698,     157,    -976,     766,      17,    2768,    2044,    -492,     232,  100.0,   10.7,   16.2,    0.0,   12.5,    1.5,    0.0,   45.1,   67.7,    1.1,   16.1,    7.6,    0.2,   85.7,   94.4,   14.3,    5.6,    198,      8,      4,      0,      8,.,      0,     51,     15,      6,     74,     36,.,    146,     61,    32.6,    76.1,    49.9,    82.4,    32.6,    75.7,    49.9,    81.9,"(Bitcoin X $0.10)","133742","CME ","133 ","F85","FutOnly"\r\n'
    '"ETHER CASH SETTLED - CHICAGO MERCANTILE EXCHANGE",260915,2026-09-15,146021,CME ,00,146 ,   28413,   19586,    9015,     980,    1419,    3339,     460,    3293,   11015,    1939,     159,    1282,       0,   27836,   28030,     577,     383,    1849,     -48,   -1216,     685,    -206,      61,     -39,     197,     633,    1581,       2,     180,       0,    2172,    1885,    -323,     -36,  100.0,   68.9,   31.7,    3.4,    5.0,   11.8,    1.6,   11.6,   38.8,    6.8,    0.6,    4.5,    0.0,   98.0,   98.7,    2.0,    1.3,    101,      5,     10,.,      5,      8,.,     29,     34,     14,      5,      4,      0,     55,     65,    81.5,    35.8,    86.8,    54.3,    75.2,    32.0,    78.5,    47.9,"(50 Index Points)","146021","CME ","146 ","F85","FutOnly"\r\n')
_CFTC_TODAY = datetime.date(2026, 9, 24)


def _cftc_row(line, day, delta=0, **cols):
    """Ten sam wiersz z innego tygodnia: data `day`; dealer long +delta, pozostali short +delta, open interest +delta
    (sumy dalej równe OI, więc strażnik go przepuszcza; netto dealerów +delta, pozostałych −delta); cols = nadpisane pola."""
    import csv, io
    p = next(csv.reader([line.strip()]))
    C = zd.CFTC_COLS
    p[C.index('Report_Date_as_YYYY-MM-DD')] = day
    p[C.index('As_of_Date_In_Form_YYMMDD')] = day[2:].replace('-', '')
    for c in ('Open_Interest_All', 'Dealer_Positions_Long_All', 'Other_Rept_Positions_Short_All'):
        p[C.index(c)] = str(int(p[C.index(c)]) + delta)
    for c, v in cols.items():
        p[C.index(c)] = v
    buf = io.StringIO(); csv.writer(buf, lineterminator='\n').writerow(p)
    return buf.getvalue()


def _cftc_weeks(last, n):
    d = datetime.date.fromisoformat(last)
    return [(d - datetime.timedelta(days=7 * k)).isoformat() for k in range(n - 1, -1, -1)]


def _cftc_year(days, skip=()):
    """Plik roczny (zip z FinFutYY.txt, z nagłówkiem): każdy tydzień z `days` dla każdego wiersza próbki; tydzień o k wcześniej
    niż ostatni ma delta = 100·k. skip = kody rynków pominiętych."""
    import io, zipfile
    lines = [l for l in _CFTC_WK.split('\r\n') if l and not any(f',{c},' in l for c in skip)]
    text = ','.join(zd.CFTC_COLS) + '\n' + ''.join(_cftc_row(l, d, 100 * (len(days) - 1 - i)) for i, d in enumerate(days) for l in lines)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('FinFutYY.txt', text)
    return buf.getvalue()


def _cftc_fetch(mapping):
    """Udaje sieć: URL → bajty albo wyjątek; nieznany URL → HTTP 404 (jak nieistniejący plik roczny CFTC)."""
    import urllib.error
    def fetch(url):
        v = mapping.get(url)
        if isinstance(v, Exception):
            raise v
        if v is None:
            raise urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
        return v
    return fetch


def _cftc_std(**over):
    m = {zd.CFTC_WEEK_URL: _CFTC_WK.encode(), zd.CFTC_YEAR_URL.format(2026): _cftc_year(_cftc_weeks('2026-09-15', 14))}
    m.update(over)
    return m


class Cftc(unittest.TestCase):
    """v50: CFTC Traders in Financial Futures wprost z cftc.gov — brak to None (nigdy 0), strażnik sum, historia z okna 90 dni."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.SECRETS[:] = []   # inne testy zostawiają klucze — mask() psułby komunikaty

    def test_weekly_file_without_header_real_numbers_only_our_markets(self):
        w = zd.parse_cftc_csv(_CFTC_WK, header=zd.CFTC_COLS)
        self.assertEqual(sorted(w), ['099741', '133741', '146021'])                 # MICRO BITCOIN 133742 pominięty
        self.assertEqual(len(zd.CFTC_COLS), 87)
        r = zd.cftc_record(w['099741']['2026-09-15'])
        d = r['g']['dealer']
        self.assertEqual((d['long'], d['short'], d['spread'], d['net'], d['chg_net']), (41113, 299193, 5144, -258080, 3374))
        self.assertEqual((r['g']['asset_mgr']['net'], r['g']['lev_funds']['net'], r['g']['other_rept']['net']), (251698, -28156, 7755))
        self.assertEqual(r['g']['lev_funds']['chg_net'], 5129)
        n = r['g']['nonrept']
        self.assertEqual((n['long'], n['short'], n['net'], n['chg_net']), (188399, 161616, 26783, -9103))
        self.assertIsNone(n['spread'])                                              # CFTC nie dzieli małych graczy — brak, nie 0
        self.assertEqual((r['oi'], r['oi_chg'], r['units']), (920035, -22429, '(CONTRACTS OF EUR 125,000)'))
        self.assertTrue(zd.cftc_consistent(r))
        eth = zd.cftc_record(w['146021']['2026-09-15'])
        self.assertEqual(eth['g']['other_rept']['spread'], 0)                       # prawdziwe zero z raportu zostaje zerem
        self.assertEqual(eth['units'], '(50 Index Points)')

    def test_missing_values_bad_dates_and_other_layouts_are_gaps_not_zeros(self):
        for tok in ('.', '', 'nan', 'inf', '-', 'x'):
            self.assertIsNone(zd._cftc_int(tok), tok)
        self.assertEqual(zd._cftc_int(' -22429'), -22429)
        line = _CFTC_WK.split('\r\n')[1]
        row = zd.parse_cftc_csv(_cftc_row(line, '2026-09-15', Change_in_Dealer_Long_All='.', Change_in_Open_Interest_All='nan'),
                                header=zd.CFTC_COLS)['133741']['2026-09-15']
        r = zd.cftc_record(row)
        self.assertIsNone(r['g']['dealer']['chg_net']); self.assertIsNone(r['oi_chg']); self.assertEqual(r['g']['dealer']['net'], 3419)
        self.assertEqual(zd.parse_cftc_csv(_cftc_row(line, '2026-13-45'), header=zd.CFTC_COLS), {})   # nieistniejąca data
        self.assertEqual(zd.parse_cftc_csv(line.rsplit(',', 1)[0] + '\n', header=zd.CFTC_COLS), {})  # 86 pól zamiast 87
        with self.assertRaises(RuntimeError):
            zd.parse_cftc_csv('a,b,c\n1,2,3\n')

    def test_guard_catches_shifted_columns(self):
        row = dict(zd.parse_cftc_csv(_CFTC_WK, header=zd.CFTC_COLS)['099741']['2026-09-15'])
        row['Dealer_Positions_Long_All'] = row['Dealer_Positions_Short_All']          # kolumna przesunięta o jedną w prawo
        self.assertFalse(zd.cftc_consistent(zd.cftc_record(row)))
        self.assertFalse(zd.cftc_consistent(zd.cftc_record(dict(row, Dealer_Positions_Long_All='.'))))

    def test_build_state_history_13_reports_and_order(self):
        out = zd.build_cftc(fetch=_cftc_fetch(_cftc_std()), today=_CFTC_TODAY)
        self.assertEqual(zd.META['errors'], [])
        self.assertEqual((out['asof'], out['unit'], out['url']), ('2026-09-15', 'kontrakty', zd.CFTC_HOME))
        self.assertEqual(out['order'], ['dealer', 'asset_mgr', 'lev_funds', 'other_rept', 'nonrept'])
        eur = out['markets']['eur']
        self.assertTrue(eur['in_week_file']); self.assertEqual((eur['oi'], eur['oi_chg']), (920035, -22429))
        self.assertEqual(eur['groups']['dealer'], {'long': 41113, 'short': 299193, 'spread': 5144, 'net': -258080, 'chg_net': 3374})
        self.assertEqual([out['markets']['btc']['groups']['lev_funds'][k] for k in ('long', 'short', 'spread')], [5545, 11899, 1841])
        self.assertEqual([out['markets']['eth']['groups']['dealer'][k] for k in ('long', 'short', 'spread')], [19586, 9015, 980])
        for key in ('eur', 'btc', 'eth'):
            h = out['markets'][key]['hist']
            self.assertEqual(h['dates'], _cftc_weeks('2026-09-15', 13))              # 23.06–15.09, rosnąco, 14. tydzień odcięty
            for g in out['order']:
                self.assertEqual(len(h[g]), 13); self.assertEqual(h[g][-1], out['markets'][key]['groups'][g]['net'])
        h = eur['hist']
        self.assertEqual(h['dealer'][0], -258080 + 1200); self.assertEqual(h['other_rept'][0], 7755 - 1200); self.assertEqual(h['oi'][0], 920035 + 1200)
        self.assertLess(len(json.dumps(out)), 8000)

    def test_week_file_down_uses_annual_file(self):
        import urllib.error
        out = zd.build_cftc(fetch=_cftc_fetch(_cftc_std(**{zd.CFTC_WEEK_URL: urllib.error.URLError('timeout')})), today=_CFTC_TODAY)
        eur = out['markets']['eur']
        self.assertEqual(eur['asof'], '2026-09-15'); self.assertFalse(eur['in_week_file'])
        self.assertEqual(eur['groups']['dealer']['chg_net'], 3374)
        self.assertTrue(any(e.startswith('CFTC tydzień') for e in zd.META['errors']))

    def test_missing_cftc_change_falls_back_to_previous_report_or_stays_gap(self):
        wk = ''.join(_cftc_row(l, '2026-09-15', Change_in_Dealer_Long_All='.', Change_in_Open_Interest_All='.') if ',099741,' in l else l + '\n'
                     for l in _CFTC_WK.split('\r\n') if l)
        out = zd.build_cftc(fetch=_cftc_fetch(_cftc_std(**{zd.CFTC_WEEK_URL: wk.encode()})), today=_CFTC_TODAY)
        self.assertEqual(out['markets']['eur']['groups']['dealer']['chg_net'], -100)   # −258080 − (−258080 + 100) z historii
        self.assertEqual(out['markets']['eur']['oi_chg'], -100)
        out = zd.build_cftc(fetch=_cftc_fetch(_cftc_std(**{zd.CFTC_WEEK_URL: wk.encode(), zd.CFTC_YEAR_URL.format(2026): RuntimeError('503')})),
                            today=_CFTC_TODAY)
        self.assertIsNone(out['markets']['eur']['groups']['dealer']['chg_net']); self.assertIsNone(out['markets']['eur']['oi_chg'])

    def test_annual_file_down_single_point_or_previous_history_in_window(self):
        full = zd.build_cftc(fetch=_cftc_fetch(_cftc_std()), today=_CFTC_TODAY)
        zd.META['errors'].clear()
        down = {zd.CFTC_YEAR_URL.format(2026): RuntimeError('HTTP 503'), zd.CFTC_YEAR_URL.format(2025): _cftc_year(_cftc_weeks('2025-12-30', 14))}
        out = zd.build_cftc(fetch=_cftc_fetch(_cftc_std(**down)), today=_CFTC_TODAY)
        for k in ('eur', 'btc', 'eth'):
            self.assertEqual(out['markets'][k]['hist']['dates'], ['2026-09-15'])  # nie 2025 + 15.09.2026 (dziura)
        self.assertEqual(out['markets']['eur']['groups']['lev_funds']['chg_net'], 5129)   # zmiana z kolumn CFTC, nie z historii
        self.assertTrue(any(e.startswith('CFTC rok 2026') for e in zd.META['errors']))
        prev = json.loads(json.dumps(full))
        for m in prev['markets'].values():                                           # poprzedni plik: historia do 08.09
            for f in list(m['hist']):
                m['hist'][f] = m['hist'][f][:-1]
        prev['markets']['btc']['hist']['dates'][0] = '2026-13-45'                   # zła data i nie-liczba w poprzednim pliku = pominięte
        prev['markets']['btc']['hist']['dealer'][1] = 'x'
        out = zd.build_cftc(fetch=_cftc_fetch(_cftc_std(**down)), today=_CFTC_TODAY, prev=prev)
        h = out['markets']['eur']['hist']
        self.assertEqual(h['dates'], _cftc_weeks('2026-09-15', 13)); self.assertEqual(h['dealer'], full['markets']['eur']['hist']['dealer'])
        b = out['markets']['btc']['hist']
        self.assertEqual(len(b['dates']), 12); self.assertIsNone(b['dealer'][0])
        old = json.loads(json.dumps(prev))
        for m in old['markets'].values():
            m['hist']['dates'] = [d.replace('2026-', '2025-') for d in m['hist']['dates']]
        out = zd.build_cftc(fetch=_cftc_fetch(_cftc_std(**down)), today=_CFTC_TODAY, prev=old)
        self.assertEqual(out['markets']['eth']['hist']['dates'], ['2026-09-15'])   # stara historia spoza 90 dni odrzucona

    def test_january_uses_previous_year_file(self):
        import urllib.error
        src = {zd.CFTC_WEEK_URL: urllib.error.URLError('down'), zd.CFTC_YEAR_URL.format(2025): _cftc_year(_cftc_weeks('2025-12-30', 15))}
        out = zd.build_cftc(fetch=_cftc_fetch(src), today=datetime.date(2026, 1, 2))
        h = out['markets']['btc']['hist']
        self.assertEqual(h['dates'], _cftc_weeks('2025-12-30', 13)); self.assertEqual(out['asof'], '2025-12-30')
        self.assertTrue(any('CFTC rok 2026: HTTP 404' in e for e in zd.META['errors']))

    def test_missing_market_is_none_or_previous_state_up_to_35_days(self):
        wk = '\r\n'.join(l for l in _CFTC_WK.split('\r\n') if ',133741,' not in l)
        src = _cftc_std(**{zd.CFTC_WEEK_URL: wk.encode(), zd.CFTC_YEAR_URL.format(2026): _cftc_year(_cftc_weeks('2026-09-15', 14), skip=('133741',))})
        out = zd.build_cftc(fetch=_cftc_fetch(src), today=_CFTC_TODAY)
        self.assertIsNone(out['markets']['btc']); self.assertIsNotNone(out['markets']['eur'])
        self.assertTrue(any('brak rynku 133741' in e for e in zd.META['errors']))
        prev = {'at': '2026-09-20T00:00:00+00:00', 'markets': {'btc': {'asof': '2026-09-08', 'oi': 21083}}}
        out = zd.build_cftc(fetch=_cftc_fetch(src), today=_CFTC_TODAY, prev=prev)
        self.assertEqual(out['markets']['btc'], {'asof': '2026-09-08', 'oi': 21083, 'kept': True})
        prev['markets']['btc']['asof'] = '2026-08-18'                                # 37 dni — za stare, brak zamiast starego stanu
        self.assertIsNone(zd.build_cftc(fetch=_cftc_fetch(src), today=_CFTC_TODAY, prev=prev)['markets']['btc'])
        prev['markets']['btc']['asof'] = '2026-13-01'
        self.assertIsNone(zd.build_cftc(fetch=_cftc_fetch(src), today=_CFTC_TODAY, prev=prev)['markets']['btc'])

    def test_nothing_fetched_raises_even_with_previous_file(self):
        import urllib.error
        down = {zd.CFTC_WEEK_URL: urllib.error.URLError('down'), zd.CFTC_YEAR_URL.format(2026): RuntimeError('503'),
                zd.CFTC_YEAR_URL.format(2025): RuntimeError('503')}
        with self.assertRaises(RuntimeError):
            zd.build_cftc(fetch=_cftc_fetch(down), today=_CFTC_TODAY)
        prev = {'at': '2026-09-19T00:00:00+00:00', 'markets': {k: {'asof': '2026-09-15', 'oi': 1} for k in ('eur', 'btc', 'eth')}}
        with self.assertRaises(RuntimeError):                                        # tylko stare stany ⇒ main zachowa stary plik i jego „at”
            zd.build_cftc(fetch=_cftc_fetch(down), today=_CFTC_TODAY, prev=prev)
        self.assertTrue(all(e.startswith('CFTC') for e in zd.META['errors']))


class MainFlowCftc(unittest.TestCase):
    """v50: młody poprzedni cftc.json (< 6 h) → bez zapytań; awaria → poprzedni plik zostaje, błąd „CFTC: …” w meta."""
    ENV = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': '', 'FINNHUB_KEY': '', 'TWELVEDATA_KEY': '', 'COINMARKETCAP_KEY': '', 'FRED_KEY': ''}

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.ps = [mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj))]
        self.ps += [mock.patch.object(zd, f, side_effect=RuntimeError('offline')) for f in ('build_instytucje', 'build_krypto', 'build_tic')]
        self.ps += [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.ps]

    def tearDown(self):
        [p.stop() for p in self.ps]

    def _main(self, prev, build):
        with mock.patch.dict(os.environ, self.ENV, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'cftc' else None), \
             mock.patch.object(zd, 'build_cftc', build) as b:
            zd.main()
        return b

    def test_young_previous_file_is_reused_without_requests(self):
        prev = {'at': _iso(5 * 60), 'asof': '2026-09-15', 'markets': {}}
        self._main(prev, mock.Mock(side_effect=AssertionError('bez zapytań')))
        self.assertIs(self.saved['cftc'], prev); self.assertEqual(zd.META['ok']['cftc'], 'cached')

    def test_older_file_is_rebuilt_with_previous_passed_in(self):
        prev = {'at': _iso(7 * 60), 'asof': '2026-09-08', 'markets': {}}
        new = {'at': _iso(0), 'asof': '2026-09-15', 'markets': {}}
        b = self._main(prev, mock.Mock(return_value=new))
        b.assert_called_once_with(prev=prev)
        self.assertIs(self.saved['cftc'], new); self.assertIs(zd.META['ok']['cftc'], True)

    def test_failure_keeps_previous_and_reports(self):
        prev = {'at': _iso(7 * 60), 'asof': '2026-09-08', 'markets': {}}
        self._main(prev, mock.Mock(side_effect=RuntimeError('żaden rynek nie ma danych')))
        self.assertIs(self.saved['cftc'], prev); self.assertIs(zd.META['ok']['cftc'], False)
        self.assertIn('CFTC: żaden rynek nie ma danych', zd.META['errors'])
        self.saved.clear(); zd.META['errors'].clear()
        self._main(None, mock.Mock(side_effect=RuntimeError('x')))                      # bez poprzedniego pliku: nic nie zapisujemy
        self.assertNotIn('cftc', self.saved); self.assertIn('CFTC: x', zd.META['errors'])


def _cm_row(asset, day, i, o, iu, ou, s, su, status='flash'):
    r = {'asset': asset, 'time': day + 'T00:00:00.000000000Z'}
    for m, v in (('FlowInExNtv', i), ('FlowOutExNtv', o), ('FlowInExUSD', iu), ('FlowOutExUSD', ou),
                 ('SplyExNtv', s), ('SplyExUSD', su)):
        if v is not None:
            r[m] = v; r[m + '-status'] = status; r[m + '-status-time'] = day + 'T02:00:00.000000000Z'
    return r


def _cm_series(asset, last='2026-09-23', n=35, skip=(), status='flash'):
    """n dni rosnąco: wpływ 10, wypływ 12 (netto −2 dziennie), zapas 1000 − 2·k, USD ×100 (teksty jak u dostawcy)."""
    d0 = datetime.date.fromisoformat(last)
    rows = []
    for k in range(n):
        day = (d0 - datetime.timedelta(days=n - 1 - k)).isoformat()
        if day in skip:
            continue
        rows.append(_cm_row(asset, day, '10.0', '12.0', '1000.5', '1200.5', str(1000 - 2 * k), str((1000 - 2 * k) * 100), status))
    return rows


# Prawdziwe odpowiedzi Coin Metrics Community z 24.09.2026 (8 ostatnich dni BTC i ETH, teksty bez zmian)
CM_REAL = {
    'btc': [
        ('2026-09-16', '23005.0435735', '25111.95609172', '1750278397.87302521799362345', '1910577310.373092978573929644', '2715643.25254517', '206612593715.522673197628736459'),
        ('2026-09-17', '21766.37576865', '22768.27672937', '1662666010.15348040373565032', '1739198120.534876233151184016', '2717241.34934502', '207561648340.492287723402723936'),
        ('2026-09-18', '26956.79244258', '28008.10103786', '2181994790.729968312846095348', '2267092076.812386564929669316', '2718781.15287739', '220069443549.326947134534782334'),
        ('2026-09-19', '13920.30109519', '15406.49176817', '1131196317.767704870377350018', '1251967657.789695729333835774', '2718047.40416887', '220874907380.868559276402635314'),
        ('2026-09-20', '12118.44914273', '12143.14716736', '983954376.302886483419629726', '985959726.091007174726671232', '2721135.94115925', '220941936239.83360304532696735'),
        ('2026-09-21', '39392.93389089', '43259.91376965', '3407697475.40797693418007915', '3742211721.20654441548406775', '2719494.22011218', '235250657235.4082620030970023'),
        ('2026-09-22', '26788.45880433', '43695.27229361', '2309306372.292639122668101195', '3766762824.384114662172450315', '2705076.07472788', '233191818257.78390678652978102'),
        ('2026-09-23', '22387.64642336', '32444.54357449', '1890285676.750714654929787264', '2739432937.603468979066092076', '2695208.79361638', '227568118688.422059403028163912'),
    ],
    'eth': [
        ('2026-09-16', '289382.073310989575481583', '212743.194353739073070714', '698485929.04586564440410663348219881565', '513501496.6758600223263853703466012027', '15388706.801086797410188754', '37143956582.3421258144738703656887627247'),
        ('2026-09-17', '267625.150138587144779647', '240294.989972524729939119', '654681864.07411971396984760189458268627', '587825067.56715277754633741250812832579', '15416030.460658763593125918', '37711685741.72171387332230353704504084038'),
        ('2026-09-18', '356672.792475764516139621', '212648.878259904896237837', '931833389.97422577397346811150449431467', '555560528.53851446633457874501080026499', '15560044.485571174299546947', '40651738251.45286313523098914606477319469'),
        ('2026-09-19', '110734.936450477785281349', '117829.794546268749835735', '291556129.28182150657257360720754134489', '310236316.67812432259804510538095462835', '15552943.686290538048104223', '40949642501.85785452245489574737288447003'),
        ('2026-09-20', '92560.011058430166140539', '126968.139877963660133432', '244515137.73109773031821180382826407923', '335410852.42657819793719839574007359224', '15518530.952890564413554298', '40995195332.62570146917542426933120645386'),
        ('2026-09-21', '369833.264598950719169977', '407638.521730416910587144', '1025844852.64772373878105520862139592522', '1130709212.19470504710965456670873458384', '15480710.367535076292751177', '42940450646.28609433714037931464559775722'),
        ('2026-09-22', '166693.231624719601151318', '230825.920339214647048367', '459231641.12677258814244778721651149796', '635914039.09320861072150661229549779274', '15416565.793280767156723457', '42471879276.57467950330200650882065335254'),
        ('2026-09-23', '167730.112637279856076631', '241843.073484394985997244', '450172921.29511826612335951381361423947', '649085612.43797930337580029021565884428', '15342440.16922408408424477', '41177764696.9759050596155967026849261849'),
    ],
}


class CoinMetrics(unittest.TestCase):
    """v50: Coin Metrics Community — wpłaty/wypłaty BTC i ETH na giełdy, zapas na giełdach; brak = None, nigdy 0."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def test_url_is_keyless_one_request_for_both_assets(self):
        self.assertTrue(zd.CM_URL.startswith('https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?'))
        for m in ('FlowInExNtv', 'FlowOutExNtv', 'FlowInExUSD', 'FlowOutExUSD', 'SplyExNtv', 'SplyExUSD', 'assets=btc,eth',
                  'frequency=1d', 'limit_per_asset=36', 'paging_from=end', 'ignore_unsupported_errors=true'):
            self.assertIn(m, zd.CM_URL)
        self.assertNotIn('api_key', zd.CM_URL)

    def test_sums_net_and_supply_change(self):
        out = zd.parse_cm({'data': _cm_series('btc') + _cm_series('eth')})
        b = out['assets']['btc']
        self.assertEqual(out['asof'], '2026-09-23'); self.assertEqual(b['asof'], '2026-09-23'); self.assertEqual(b['status'], 'flash')
        self.assertEqual(len(b['d']), 35); self.assertEqual(b['d'][0][0], '2026-08-20'); self.assertEqual(b['d'][-1][0], '2026-09-23')
        self.assertEqual(b['last'], {'in': 10.0, 'out': 12.0, 'net': -2.0, 'in_usd': 1000, 'out_usd': 1200, 'net_usd': -200,
                                     'sply': 932.0, 'sply_usd': 93200})
        self.assertEqual(b['sum7'], {'in': 70.0, 'out': 84.0, 'net': -14.0, 'in_usd': 7004, 'out_usd': 8404, 'net_usd': -1400})
        self.assertEqual(b['sum30']['net'], -60.0)
        self.assertEqual(b['sply_ch7'], {'ntv': -14.0, 'pct': round(-14 / 946 * 100, 2)})
        self.assertEqual(b['sply_ch30']['ntv'], -60.0)
        self.assertEqual(b['missing'], 0); self.assertIsNone(b['pending'])
        self.assertEqual(out['cols'], ['date', 'in', 'out', 'net', 'in_usd', 'out_usd', 'net_usd', 'sply', 'sply_usd'])
        self.assertEqual(out['license'], 'CC BY-NC 4.0')
        self.assertTrue(out['attribution'].startswith('Source: Coin Metrics Community Network Data'))
        self.assertIn('https://coinmetrics.io', out['attribution']); self.assertIn(zd.CM_LICENSE_URL, out['attribution'])

    def test_missing_day_is_none_never_zero_and_breaks_only_its_windows(self):
        out = zd.parse_cm({'data': _cm_series('btc', skip=('2026-09-20',)) + _cm_series('eth')})
        b = out['assets']['btc']
        gap = [r for r in b['d'] if r[0] == '2026-09-20'][0]
        self.assertEqual(gap[1:], [None] * 8)
        self.assertEqual(b['missing'], 1)
        self.assertIsNone(b['sum7']['in']); self.assertIsNone(b['sum30']['net'])
        self.assertEqual(b['sply_ch7']['ntv'], -14.0, 'zmiana zapasu liczy tylko dwa końce okna')
        self.assertEqual(out['assets']['eth']['sum7']['net'], -14.0, 'luka BTC nie psuje ETH')

    def test_one_side_missing_gives_none_net_but_keeps_other_values(self):
        rows = _cm_series('btc')
        del rows[-1]['FlowOutExUSD']
        rows[-1]['FlowOutExNtv'] = 'nan'
        rows[-2]['FlowInExNtv'] = '-5'
        b = zd.parse_cm({'data': rows})['assets']['btc']
        self.assertIsNone(b['last']['out']); self.assertIsNone(b['last']['net']); self.assertIsNone(b['last']['net_usd'])
        self.assertEqual(b['last']['in_usd'], 1000); self.assertEqual(b['last']['sply'], 932.0)
        self.assertIsNone(b['d'][-2][1], 'ujemny przepływ to błąd dostawcy → None')
        self.assertIsNone(b['sum7']['out']); self.assertIsNone(b['sum7']['in'])

    def test_one_asset_missing_keeps_the_other_and_reports(self):
        out = zd.parse_cm({'data': _cm_series('eth')})
        self.assertIsNone(out['assets']['btc']); self.assertEqual(out['assets']['eth']['asof'], '2026-09-23')
        self.assertIn('Coin Metrics: brak dni dla btc', zd.META['errors'])

    def test_different_last_days_give_a_range(self):
        out = zd.parse_cm({'data': _cm_series('btc', last='2026-09-22') + _cm_series('eth')})
        self.assertEqual(out['asof'], '2026-09-22 – 2026-09-23')

    def test_reviewed_status_and_mixed_status(self):
        self.assertEqual(zd.parse_cm({'data': _cm_series('btc', status='reviewed')})['assets']['btc']['status'], 'reviewed')
        rows = _cm_series('btc', status='reviewed'); rows[-1]['SplyExUSD-status'] = 'flash'
        self.assertEqual(zd.parse_cm({'data': rows})['assets']['btc']['status'], 'flash')

    def test_errors_and_empty_answers_raise(self):
        with self.assertRaises(RuntimeError):
            zd.parse_cm({'error': {'type': 'bad_parameter', 'message': "Bad parameter 'metrics'."}})
        with self.assertRaises(RuntimeError):
            zd.parse_cm({'data': []})
        with self.assertRaises(RuntimeError):
            zd.parse_cm([])
        with self.assertRaises(RuntimeError):
            zd.parse_cm({'data': [{'asset': 'btc', 'time': 'wczoraj', 'FlowInExNtv': '1'}]})

    def test_build_cm_uses_one_keyless_request(self):
        seen = []
        def get_json(url, headers=None):
            seen.append((url, headers)); return {'data': _cm_series('btc') + _cm_series('eth')}
        with mock.patch.object(zd, 'get_json', get_json):
            out = zd.build_cm()
        self.assertEqual(seen, [(zd.CM_URL, None)]); self.assertEqual(sorted(out['assets']), ['btc', 'eth'])

    def test_newest_day_still_publishing_falls_back_to_last_full_day(self):
        rows = _cm_series('btc') + _cm_series('eth')
        rows.append(_cm_row('btc', '2026-09-24', '11.0', '9.0', None, None, '930', None))   # natywne już są, USD jeszcze nie
        out = zd.parse_cm({'data': rows})
        b = out['assets']['btc']
        self.assertEqual(out['asof'], '2026-09-23'); self.assertEqual(b['asof'], '2026-09-23'); self.assertEqual(b['pending'], '2026-09-24')
        self.assertEqual(b['d'][-1][0], '2026-09-23'); self.assertEqual(len(b['d']), 35); self.assertEqual(b['missing'], 0)
        self.assertEqual(b['last']['net_usd'], -200); self.assertEqual(b['sum7']['in_usd'], 7004)
        self.assertIsNone(out['assets']['eth']['pending'])

    def test_api_window_has_no_false_gap_while_newest_day_is_publishing(self):
        """Coin Metrics zwraca limit_per_asset NAJNOWSZYCH wierszy, także niepełny dzień w publikacji (ok. 02–03 UTC).
        Po cofnięciu do ostatniego pełnego dnia okno 35 dni ma być pełne — brak dnia to tylko prawdziwa luka u dostawcy."""
        lim = int(zd.CM_URL.split('limit_per_asset=')[1].split('&')[0])
        rows = []
        for a in ('btc', 'eth'):
            r = _cm_series(a, last='2026-09-23', n=60) + [_cm_row(a, '2026-09-24', '11.0', '9.0', None, None, '930', None)]
            rows += r[-lim:]                                   # tyle wierszy odda API (paging_from=end)
        b = zd.parse_cm({'data': rows})['assets']['btc']
        self.assertEqual(b['pending'], '2026-09-24'); self.assertEqual(b['asof'], '2026-09-23')
        self.assertEqual(b['missing'], 0, 'najstarszy dzień okna nie może być fałszywą luką')
        self.assertEqual(b['d'][0][0], '2026-08-20'); self.assertIsNotNone(b['d'][0][1]); self.assertIsNotNone(b['sply_ch30']['ntv'])
        rows = [x for a in ('btc', 'eth') for x in _cm_series(a, n=60)[-lim:]]   # zwykła pora: wszystkie dni pełne
        b = zd.parse_cm({'data': rows})['assets']['btc']
        self.assertEqual(b['missing'], 0); self.assertEqual(len(b['d']), 35); self.assertIsNone(b['pending'])

    def test_partial_day_after_a_gap_is_not_hidden(self):
        rows = _cm_series('btc', last='2026-09-21')
        rows.append(_cm_row('btc', '2026-09-23', '11.0', '9.0', None, None, '930', None))
        b = zd.parse_cm({'data': rows})['assets']['btc']
        self.assertEqual(b['asof'], '2026-09-23'); self.assertIsNone(b['pending']); self.assertIsNone(b['last']['in_usd'])
        self.assertEqual(b['last']['net'], 2.0); self.assertIsNone(b['sum7']['in'], 'dzień 2026-09-22 brak → suma null, nie zero')

    def test_impossible_date_is_skipped_not_crash(self):
        rows = _cm_series('btc') + [_cm_row('btc', '2026-02-30', '1', '1', '1', '1', '1', '1')]
        self.assertEqual(zd.parse_cm({'data': rows})['assets']['btc']['asof'], '2026-09-23')

    def test_paged_answer_is_reported(self):
        zd.parse_cm({'data': _cm_series('btc') + _cm_series('eth'), 'next_page_token': 'abc'})
        self.assertTrue(any(e.startswith('Coin Metrics') and 'stron' in e for e in zd.META['errors']))

    def test_whole_metric_missing_is_reported_and_left_null(self):
        rows = _cm_series('btc') + _cm_series('eth')
        for r in rows:
            r.pop('SplyExUSD', None)
        out = zd.parse_cm({'data': rows})
        self.assertIn('Coin Metrics: brak metryki SplyExUSD w odpowiedzi', zd.META['errors'])
        b = out['assets']['btc']
        self.assertEqual(b['asof'], '2026-09-23'); self.assertIsNone(b['last']['sply_usd']); self.assertEqual(b['last']['sply'], 932.0)

    def test_real_answer_24_09_2026_net_from_unrounded_values(self):
        rows = [_cm_row(a, *r) for a in ('btc', 'eth') for r in CM_REAL[a]]
        out = zd.parse_cm({'data': rows})
        b, e = out['assets']['btc'], out['assets']['eth']
        self.assertEqual(out['asof'], '2026-09-23'); self.assertEqual(b['status'], 'flash'); self.assertIsNone(b['pending'])
        self.assertEqual(b['last']['in'], 22387.65); self.assertEqual(b['last']['out'], 32444.54)
        self.assertEqual(b['last']['net'], -10056.9, 'netto z liczb niezaokrąglonych (22387.65 − 32444.54 dałoby −10056.89)')
        self.assertEqual(b['last']['net_usd'], -849147261); self.assertEqual(b['last']['sply'], 2695208.79)
        self.assertEqual(b['sum7']['net'], -34394.79); self.assertEqual(b['sply_ch7'], {'ntv': -20434.46, 'pct': -0.75})
        self.assertIsNone(b['sum30']['net'], 'w próbce 8 dni — suma 30 dni to brak, nie zero')
        self.assertEqual(b['missing'], 27)
        self.assertEqual(e['last']['net'], -74112.96); self.assertEqual(e['sum7']['net'], -46199.82)
        self.assertEqual(e['sply_ch7'], {'ntv': -46266.63, 'pct': -0.3})


class MainFlowCm(unittest.TestCase):
    """v50: blok Coin Metrics w main() — pamięć 60 min, przy awarii poprzedni plik i META ok False, błąd z prefiksem."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.patches = [mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj))]
        for fn in ('build_instytucje', 'build_krypto', 'build_tic'):
            self.patches.append(mock.patch.object(zd, fn, side_effect=RuntimeError('offline')))
        for fn in ('build_bis', 'build_cftc', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue'):   # pozostałe źródła v50 (mogą jeszcze nie istnieć)
            self.patches.append(mock.patch.object(zd, fn, side_effect=RuntimeError('offline'), create=True))
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def _run(self, prev, build):
        env = {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'cm' else None), \
             mock.patch.object(zd, 'build_cm', build):
            zd.main()

    def test_young_previous_file_is_reused_without_request(self):
        prev = {'at': datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(), 'assets': {}}
        self._run(prev, mock.Mock(side_effect=AssertionError('bez zapytań')))
        self.assertIs(self.saved['cm'], prev); self.assertEqual(zd.META['ok']['cm'], 'cached')

    def test_failure_keeps_previous_and_reports(self):
        prev = {'at': '2026-09-24T10:00:00+00:00', 'assets': {}}
        self._run(prev, mock.Mock(side_effect=RuntimeError('HTTP Error 429')))
        self.assertIs(self.saved['cm'], prev); self.assertIs(zd.META['ok']['cm'], False)
        self.assertIn('Coin Metrics: HTTP Error 429', zd.META['errors'])

    def test_parser_error_is_not_prefixed_twice(self):
        self._run(None, lambda: zd.parse_cm({'data': []}))
        self.assertNotIn('cm', self.saved); self.assertIs(zd.META['ok']['cm'], False)
        self.assertIn('Coin Metrics: żadne aktywo nie ma danych', zd.META['errors'])
        self.assertFalse(any(e.startswith('Coin Metrics: Coin Metrics') for e in zd.META['errors']))

    def test_fresh_data_is_saved(self):
        self._run(None, lambda: zd.parse_cm({'data': _cm_series('btc') + _cm_series('eth')}))
        self.assertEqual(self.saved['cm']['asof'], '2026-09-23'); self.assertIs(zd.META['ok']['cm'], True)



class FedCustodyV50(unittest.TestCase):
    """v50: Fed H.4.1 — papiery w depozycie dla zagranicznych instytucji oficjalnych (FRED). Liczby = H.4.1 z 17.09.2026, mln USD."""
    ROWS = {   # data: (WSEFINTL1, WMTSECL1, WFASECL1, WSEFINOL) — prawdziwe stany środowe
        '2026-09-16': (2884717, 2608821, 202071, 73825),
        '2026-09-09': (2865365, 2590095, 201252, 74017),
        '2026-08-19': (2864974, 2586171, 204466, 74338),
        '2025-09-17': (3119250, 2792652, 247489, 79109),
        '2025-09-10': (3129862, 2802270, 248101, 79491),
    }
    IDS = ['WSEFINTL1', 'WMTSECL1', 'WFASECL1', 'WSEFINOL']

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def _json(self, sid, rows=None, drop=()):
        i = self.IDS.index(sid)
        return {'observations': [{'date': d, 'value': ('.' if (sid, d) in drop else str(v[i]) + '.0')}
                                 for d, v in sorted((rows or self.ROWS).items(), reverse=True)]}

    def _series(self, rows=None, drop=()):
        out = {}
        for sid in self.IDS:
            try:
                out[sid] = zd.parse_fred(self._json(sid, rows, drop), sid)
            except RuntimeError:
                pass
        return out

    def test_series_are_fed_board_h41_weekly_in_millions(self):
        self.assertEqual(sorted(zd.FRED_CUSTODY), sorted(self.IDS))
        for sid in self.IDS:
            self.assertEqual((zd.FRED_SERIES[sid]['unit'], zd.FRED_SERIES[sid]['freq']), ('mln USD', 'W'))
            self.assertIn('H.4.1', zd.FRED_SERIES[sid]['name'])

    def test_summary_matches_h41_release_of_2026_09_17(self):
        s = zd.custody_summary(self._series())
        self.assertEqual((s['asof'], s['total'], s['unit']), ('2026-09-16', 2884717.0, 'mln USD'))
        self.assertEqual((s['ust'], s['agency'], s['other']), (2608821.0, 202071.0, 73825.0))
        self.assertEqual((s['d1w'], s['d4w'], s['d52w']), (19352.0, 19743.0, -234533.0))   # zmiana STANU NA ŚRODĘ
        self.assertEqual((s['ust_d1w'], s['ust_d52w']), (18726.0, -183831.0))
        self.assertEqual(s['ust_share_pct'], 90.4); self.assertIs(s['parts_ok'], True)
        self.assertEqual(s['lo52'], ['2026-08-19', 2864974.0]); self.assertEqual(s['hi52'], ['2025-09-17', 3119250.0])

    def test_missing_week_is_none_not_an_older_week_and_not_zero(self):
        rows = {d: v for d, v in self.ROWS.items() if d != '2026-09-09'}
        s = zd.custody_summary(self._series(rows))
        self.assertIsNone(s['d1w']); self.assertIsNone(s['ust_d1w']); self.assertEqual(s['d4w'], 19743.0)

    def test_missing_part_is_none_and_parts_not_summing_are_flagged(self):
        s = zd.custody_summary(self._series(drop={('WFASECL1', '2026-09-16')}))
        self.assertIsNone(s['agency']); self.assertIsNone(s['parts_ok']); self.assertEqual(s['total'], 2884717.0)
        rows = dict(self.ROWS); rows['2026-09-16'] = (2884717, 2608821, 202071, 63825)
        self.assertIs(zd.custody_summary(self._series(rows))['parts_ok'], False)

    def test_no_total_series_gives_none_and_nan_is_ignored(self):
        self.assertIsNone(zd.custody_summary({})); self.assertIsNone(zd.custody_summary(None))
        self.assertIsNone(zd.custody_summary({'WMTSECL1': zd.parse_fred(self._json('WMTSECL1'), 'WMTSECL1')}))
        ser = self._series(); ser['WSEFINTL1']['d'].append(['2026-09-23', float('nan')])
        self.assertEqual(zd.custody_summary(ser)['asof'], '2026-09-16')

    def test_build_fred_adds_custody_and_a_summary_error_does_not_stop_fred(self):
        zd.SECRETS[:] = ['TAJNY-FRED']
        def get_json(url, headers=None):
            sid = url.split('series_id=')[1].split('&')[0]
            return self._json(sid) if sid in self.IDS else {'observations': [{'date': '2026-09-16', 'value': '5'}]}
        try:
            with mock.patch.object(zd, 'get_json', get_json), mock.patch.object(zd.time, 'sleep', lambda s: None):
                out = zd.build_fred('TAJNY-FRED')
                self.assertEqual(out['custody']['total'], 2884717.0); self.assertEqual(len(out['series']), 8)
                with mock.patch.object(zd, 'custody_summary', side_effect=ValueError('zły kształt TAJNY-FRED')):
                    out = zd.build_fred('TAJNY-FRED')
        finally:
            zd.SECRETS[:] = []
        self.assertIsNone(out['custody']); self.assertEqual(len(out['series']), 8)
        self.assertIn('FRED custody: zły kształt ***', zd.META['errors'])


def _imf_sdmx(series, periods, dims=None):
    """Minimalna odpowiedź SDMX-JSON 2.0 w kształcie API MFW 3.0 (IL, 24.09.2026)."""
    dims = dims or [('COUNTRY', ['BRA', 'CHN', 'TWN']), ('INDICATOR', ['RXF11FX_REVS', 'RXF11_REVS', 'TRGMV_REVS']),
                    ('UNIT', ['USD']), ('FREQUENCY', ['M'])]
    return {'meta': {}, 'data': {
        'dataSets': [{'structure': 0, 'action': 'Replace', 'series': {k: {'attributes': [0, None, 'true'], 'observations': {
            str(i): [v, None, 0, None] for i, v in obs.items()}} for k, obs in series.items()}}],
        'structures': [{'dimensions': {
            'series': [{'id': n, 'keyPosition': p, 'values': [{'id': x} for x in vals]} for p, (n, vals) in enumerate(dims)],
            'observation': [{'id': 'TIME_PERIOD', 'keyPosition': 4, 'values': [{'value': x} for x in periods]}]},
            'attributes': {'series': [{'id': 'SCALE', 'values': [{'id': '6'}]}]}}]}}


class ImfRezerwyV50(unittest.TestCase):
    """v50: rezerwy walutowe z MFW (International Liquidity) — mld USD, każdy kraj z własnym miesiącem, brak = brak."""
    PER = ['2026-M05', '2026-M06', '2025-M06', '2026-M08', '2026-M07', '2025-M08', '2026-M04', '2025-M04']   # celowo nie po kolei
    MINI = {   # prawdziwe wartości (USD) z odpowiedzi IL 24.09.2026
        '1:2:0:0': {1: '3786110832113.452', 0: '3850222574625.652', 2: '3627580370629.294'},   # CHN razem (złoto rynkowo)
        '1:1:0:0': {1: '3482385620113.452', 0: '3509458162625.652'},                          # CHN bez złota
        '1:0:0:0': {1: '3416262000000', 0: '3442238000000'},                                  # CHN waluty
        '0:2:0:0': {3: '373354596341.5881', 4: '369648992876.5459', 5: None},                 # BRA razem; 2025-08 = null
        '0:0:0:0': {3: '324148312609.55', 4: 'NaN'},                                          # BRA waluty; NaN = brak
        '2:0:0:0': {6: '602488000000'},                                                       # TWN tylko waluty, bez sumy
    }

    def test_url_is_keyless_and_asks_for_all_countries_and_indicators(self):
        u = zd.IMF_IL_URL
        self.assertTrue(u.startswith('https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IL/+/'))
        self.assertNotIn('key', u.lower().replace('lastnobservations', ''))
        for c in ('CHN', 'JPN', 'IND', 'SAU', 'KOR', 'CHE', 'BRA', 'TWN', 'TRGMV_REVS', 'RXF11_REVS', 'RXF11FX_REVS'):
            self.assertIn(c, u)
        self.assertTrue(u.endswith('.USD.M?lastNObservations=13'))

    def test_period_formats(self):
        self.assertEqual(zd._imf_month('2026-M06'), '2026-06'); self.assertEqual(zd._imf_month('2026-06'), '2026-06')
        self.assertIsNone(zd._imf_month('2026-Q2')); self.assertIsNone(zd._imf_month('2026-M13')); self.assertIsNone(zd._imf_month(None))
        self.assertEqual(zd._imf_month_add('2026-01', -1), '2025-12'); self.assertEqual(zd._imf_month_add('2026-06', -12), '2025-06')

    def test_parser_orders_periods_and_skips_null_and_nan(self):
        ser = zd.parse_imf_sdmx(_imf_sdmx(self.MINI, self.PER))
        self.assertEqual(ser[('CHN', 'TRGMV_REVS', 'USD', 'M')][0], ['2025-06', 3627580370629.294])
        self.assertEqual([r[0] for r in ser[('BRA', 'TRGMV_REVS', 'USD', 'M')]], ['2026-07', '2026-08'])
        self.assertEqual(ser[('BRA', 'RXF11FX_REVS', 'USD', 'M')], [['2026-08', 324148312609.55]])

    def test_reserves_in_billions_each_country_with_own_month(self):
        r = zd.parse_rezerwy(_imf_sdmx(self.MINI, self.PER))
        chn, bra = r['countries']['CHN'], r['countries']['BRA']
        self.assertEqual((chn['asof'], chn['total'], chn['fx'], chn['ex_gold'], chn['gold']), ('2026-06', 3786.1, 3416.3, 3482.4, 303.7))
        self.assertEqual((chn['d1m'], chn['d12m'], chn['p12m']), (-64.1, 158.5, 4.4))
        self.assertEqual((bra['asof'], bra['total'], bra['fx']), ('2026-08', 373.4, 324.1))
        self.assertIsNone(bra['ex_gold']); self.assertIsNone(bra['gold']); self.assertIsNone(bra['d12m'])   # brak = brak, nie zero
        self.assertEqual(r['order'], ['CHN', 'BRA']); self.assertEqual(r['unit'], 'mld USD')
        self.assertIn('TWN', r['missing']); self.assertIn('JPN', r['missing'])
        self.assertEqual((r['asof_min'], r['asof_max']), ('2026-06', '2026-08'))
        self.assertIn('International Monetary Fund', r['src']); self.assertTrue(r['url'].startswith('https://data.imf.org/'))
        json.dumps(r, allow_nan=False)   # żadnego NaN w pliku

    def test_empty_answer_or_scaled_values_are_errors_not_zeros(self):
        empty = _imf_sdmx({}, self.PER); del empty['data']['dataSets'][0]['series']
        for bad in (empty, {'errors': [{'code': 404}]}, _imf_sdmx({'1:2:0:0': {1: '3786110.83'}, '0:2:0:0': {3: '373354.6'}}, self.PER)):
            with self.assertRaises(RuntimeError):
                zd.parse_rezerwy(bad)

    def test_build_rezerwy_sends_json_accept_header_and_stamps_time(self):
        seen = {}
        def get_json(url, headers=None):
            seen['url'], seen['headers'] = url, headers
            return _imf_sdmx(self.MINI, self.PER)
        with mock.patch.object(zd, 'get_json', get_json):
            out = zd.build_rezerwy()
        self.assertEqual(seen['url'], zd.IMF_IL_URL); self.assertEqual(seen['headers'], {'Accept': 'application/json'})
        self.assertEqual(out['at'], zd.NOW); self.assertEqual(out['countries']['CHN']['total'], 3786.1)


class MainFlowRezerwyV50(unittest.TestCase):
    ENV = {k: '' for k in ('SOSOVALUE_KEY', 'COINGECKO_KEY', 'FINNHUB_KEY', 'TWELVEDATA_KEY', 'COINMARKETCAP_KEY', 'FRED_KEY')}

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); self.saved = {}
        self.ps = [mock.patch.object(zd, 'save', lambda name, obj: self.saved.__setitem__(name, obj))]
        self.ps += [mock.patch.object(zd, f, side_effect=RuntimeError('offline')) for f in ('build_instytucje', 'build_krypto', 'build_tic')]
        self.ps += [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue')]
        [p.start() for p in self.ps]

    def tearDown(self):
        [p.stop() for p in self.ps]

    def _main(self, prev, build):
        with mock.patch.dict(os.environ, self.ENV, clear=False), mock.patch.object(zd, 'previous', lambda name: prev if name == 'rezerwy' else None), \
             mock.patch.object(zd, 'build_rezerwy', build):
            zd.main()

    def test_young_previous_file_is_reused_without_asking_imf(self):
        prev = {'at': _iso(60), 'countries': {'CHN': {'total': 3786.1}}, 'order': ['CHN']}
        self._main(prev, mock.Mock(side_effect=AssertionError('bez zapytań do MFW')))
        self.assertIs(self.saved['rezerwy'], prev); self.assertEqual(zd.META['ok']['imf'], 'cached')

    def test_failure_keeps_previous_file_and_reports_with_mfw_prefix(self):
        prev = {'at': _iso(26 * 60), 'countries': {'CHN': {'total': 3786.1}}, 'order': ['CHN']}
        self._main(prev, mock.Mock(side_effect=RuntimeError('brak serii z wartościami')))
        self.assertIs(self.saved['rezerwy'], prev); self.assertIs(zd.META['ok']['imf'], False)
        self.assertIn('MFW rezerwy: brak serii z wartościami', zd.META['errors'])

    def test_fresh_build_is_saved(self):
        new = {'at': zd.NOW, 'countries': {}, 'order': []}
        self._main(None, mock.Mock(return_value=new))
        self.assertIs(self.saved['rezerwy'], new); self.assertIs(zd.META['ok']['imf'], True)


class StanV51(unittest.TestCase):
    """v51: poprzedni plik = nowszy z pamięci Actions i ze strony; 404 to informacja; bez świecy trwającej sesji."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear(); zd.SECRETS[:] = []

    def test_previous_takes_the_newer_of_cache_and_site(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'ceny.json'), 'w', encoding='utf-8') as f:
                json.dump({'at': '2026-09-25T08:00:00+00:00', 'src': 'pamięć'}, f)
            with mock.patch.dict(os.environ, {'CACHE_DIR': d, 'SITE_URL': 'https://x'}, clear=False), \
                 mock.patch.object(zd, 'get_json', lambda u, h=None: {'at': '2026-09-25T07:00:00+00:00', 'src': 'strona'}):
                self.assertEqual(zd.previous('ceny')['src'], 'pamięć')
            with mock.patch.dict(os.environ, {'CACHE_DIR': d, 'SITE_URL': 'https://x'}, clear=False), \
                 mock.patch.object(zd, 'get_json', lambda u, h=None: {'at': '2026-09-25T09:00:00+00:00', 'src': 'strona'}):
                self.assertEqual(zd.previous('ceny')['src'], 'strona')
            with mock.patch.dict(os.environ, {'CACHE_DIR': d, 'SITE_URL': ''}, clear=False):
                self.assertEqual(zd.previous('ceny')['src'], 'pamięć', 'awaria/brak strony — zostaje pamięć')

    def test_missing_previous_file_is_a_note_not_an_error(self):
        def nf(u, h=None):
            raise zd.urllib.error.HTTPError(u, 404, 'Not Found', None, None)
        with mock.patch.dict(os.environ, {'CACHE_DIR': '', 'SITE_URL': 'https://x'}, clear=False), mock.patch.object(zd, 'get_json', nf):
            self.assertIsNone(zd.previous('bis'))
        self.assertEqual(zd.META['errors'], []); self.assertTrue(any('bis.json' in n for n in zd.META['notes']))

    def test_running_session_candle_is_dropped_before_the_close(self):
        ny = datetime.datetime(2026, 9, 24, 15, 2)
        q = {'SPY': {'d': [['2026-09-23', 600.0, 54700000], ['2026-09-24', 601.0, 1100000]], 'asof': '2026-09-24'},
             'ASEA': {'d': [['2026-09-22', 10.0, 1], ['2026-09-23', 10.1, 1]], 'asof': '2026-09-23'}}
        self.assertEqual(zd._drop_open_session(q, ny), 1)
        self.assertEqual(q['SPY']['d'][-1][0], '2026-09-23'); self.assertEqual(q['SPY']['asof'], '2026-09-23'); self.assertEqual(q['ASEA']['asof'], '2026-09-23')
        q2 = {'SPY': {'d': [['2026-09-24', 601.0, 50000000]], 'asof': '2026-09-24'}}
        self.assertEqual(zd._drop_open_session(q2, datetime.datetime(2026, 9, 24, 16, 30)), 0, 'po zamknięciu świeca zostaje')


class StopyV52(unittest.TestCase):
    """v52: stopy banków centralnych (BIS WS_CBPOL): CSV z cudzysłowami, NaN/status M = brak, zmiany i różnica wobec Fed."""
    D = ('FREQ,REF_AREA,UNIT_MEASURE,TITLE,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n'
         'D,US,368,"Central bank policy rates - United States, daily",2026-09-19,3.625,A\n'
         'D,US,368,"Central bank policy rates - United States, daily",2026-09-22,3.875,A\n'
         'D,ID,368,"Indonesia, ""policy""",2026-09-19,5.75,A\n'
         'D,ID,368,"Indonesia",2026-09-20,NaN,M\n'
         'D,XM,368,"Euro area",2026-09-22,2.5,A\n')
    M = ('FREQ,REF_AREA,UNIT_MEASURE,TITLE,TIME_PERIOD,OBS_VALUE,OBS_STATUS\n'
         'M,US,368,"x",2025-09,4.125,A\nM,US,368,"x",2026-07,3.625,A\nM,US,368,"x",2026-08,3.625,A\n'
         'M,XM,368,"x",2025-09,2.0,A\nM,XM,368,"x",2026-06,2.25,A\nM,XM,368,"x",2026-07,2.25,A\nM,XM,368,"x",2026-08,2.25,A\n'
         'M,ID,368,"x",2026-08,5.75,A\n')

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def test_csv_with_quotes_and_missing_values(self):
        d = zd.parse_cbpol_csv(self.D.encode())
        self.assertEqual(d['US'], [['2026-09-19', 3.625], ['2026-09-22', 3.875]])
        self.assertEqual(d['ID'], [['2026-09-19', 5.75]], 'NaN ze statusem M pominięte, nie zero')
        with self.assertRaises(RuntimeError):
            zd.parse_cbpol_csv(b'FREQ,REF_AREA,TIME_PERIOD,OBS_VALUE\n')

    def test_summary_changes_and_spread_vs_fed(self):
        rows = zd.cbpol_summary(zd.parse_cbpol_csv(self.D.encode()), zd.parse_cbpol_csv(self.M.encode()))
        us, xm, idn = rows['US'], rows['XM'], rows['ID']
        self.assertEqual((us['rate'], us['date']), (3.875, '2026-09-22'))
        self.assertEqual(us['d12'], -0.25); self.assertEqual(us['last'], ['2026-09', 0.25]); self.assertEqual(us['vs_us'], 0)
        self.assertEqual(xm['last'], ['2026-09', 0.25]); self.assertEqual(xm['d12'], 0.5); self.assertEqual(xm['vs_us'], -1.375)
        self.assertEqual(idn['rate'], 5.75); self.assertIsNone(idn['d12'], 'brak historii 12 mies. = brak, nie zero')
        self.assertEqual((us['m_n'], idn['m_n']), (3, 1), 'v63: liczba miesięcy historii przy każdym kraju')

    def test_build_uses_daily_and_monthly_and_keeps_order(self):
        def gb(url, headers=None, timeout=60):
            return (self.D if '/D.' in url else self.M).encode()
        with mock.patch.object(zd, 'get_bytes', gb):
            out = zd.build_stopy()
        self.assertEqual(out['order'], ['US', 'XM', 'ID']); self.assertEqual(out['asof'], '2026-09-22'); self.assertEqual(out['unit'], '% rocznie')


class KursyV53(unittest.TestCase):
    """v53: średnie miesięczne kursów EBC (EXR) — do okien OECD na mapie; brak/0 = pominięte, bez USD = błąd."""
    CSV = ('KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE,OBS_STATUS,TITLE\n'
           'EXR.M.USD.EUR.SP00.A,M,USD,EUR,SP00,A,2026-07,1.1500,A,"US dollar/Euro, ""ECB"""\n'
           'EXR.M.USD.EUR.SP00.A,M,USD,EUR,SP00,A,2026-08,1.1593095238,A,"US dollar/Euro"\n'
           'EXR.M.JPY.EUR.SP00.A,M,JPY,EUR,SP00,A,2026-08,184.1019047619,A,"Japanese yen/Euro"\n'
           'EXR.M.JPY.EUR.SP00.A,M,JPY,EUR,SP00,A,2026-07,182.0,A,"Japanese yen/Euro"\n'
           'EXR.M.TRY.EUR.SP00.A,M,TRY,EUR,SP00,A,2026-08,NaN,M,"Turkish lira/Euro"\n'
           'EXR.M.KRW.EUR.SP00.A,M,KRW,EUR,SP00,A,2026-08,0,A,"x"\n')

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def test_parse_sorted_rounded_and_missing_skipped(self):
        m = zd.parse_exr_csv(self.CSV.encode())
        self.assertEqual(m['USD'], [['2026-07', 1.15], ['2026-08', 1.15931]])
        self.assertEqual(m['JPY'][0][0], '2026-07', 'rosnąco po miesiącu')
        self.assertNotIn('TRY', m, 'NaN = brak, nie zero'); self.assertNotIn('KRW', m, 'kurs 0 = brak')
        with self.assertRaises(RuntimeError):
            zd.parse_exr_csv(b'KEY,FREQ,CURRENCY,TIME_PERIOD,OBS_VALUE\nX,M,JPY,2026-08,184\n')

    def test_build_has_asof_from_usd_and_no_key_in_url(self):
        seen = []

        def gb(url, headers=None, timeout=60):
            seen.append(url); return self.CSV.encode()
        with mock.patch.object(zd, 'get_bytes', gb):
            out = zd.build_kursy()
        self.assertEqual(out['asof'], '2026-08'); self.assertIn('m', out); self.assertIn('EXR/M.USD+CAD', seen[0])
        self.assertIn('lastNObservations=15', seen[0]); self.assertNotIn('key', seen[0].lower())


class ObceV54(unittest.TestCase):
    """v54: zmierzone dzienne przepływy inwestorów zagranicznych — NSDL (Indie) i TWSE (Tajwan)."""
    NSDL = (
        '<html><body><table><tr><td colspan="8">Daily Trends in FPI Investments on 24-Sep-2026</td></tr>'
        '<tr><th>Reporting Date</th><th>Debt/Equity</th><th>Route</th><th>GP</th><th>GS</th><th>Net</th><th>Net US($) million</th><th>Conv</th></tr>'
        '<tr><td rowspan="3">23-Sep-2026</td><td rowspan="3">Equity</td><td>Stock Exchange</td><td>10.0</td><td>20.0</td><td>(10.00)</td><td>(270.67)</td><td>Rs.95.8179</td></tr>'
        '<tr><td>Primary market &amp; others</td><td>1</td><td>0</td><td>1</td><td>0.10</td></tr>'
        '<tr><td>Sub-total</td><td>11</td><td>20</td><td>(9)</td><td>(270.67)</td></tr>'
        '<tr><td>Debt-General Limit</td><td>Stock Exchange</td><td>1</td><td>1</td><td>0</td><td>(20.00)</td></tr>'
        '<tr><td>Sub-total</td><td>1</td><td>1</td><td>0</td><td>(20.00)</td></tr>'
        '<tr><td>Debt-VRR</td><td>Stock Exchange</td><td>1</td><td>1</td><td>0</td><td>(4.91)</td></tr>'
        '<tr><td>Sub-total</td><td>1</td><td>1</td><td>0</td><td>(4.91)</td></tr>'
        '<tr><td>Total</td><td>1</td><td>1</td><td>0</td><td>(290.42)</td></tr>'
        '<tr><td rowspan="2">24-Sep-2026</td><td>Equity</td><td>Stock Exchange</td><td>1</td><td>1</td><td>1</td><td>178.14</td><td>Rs.95.7310</td></tr>'
        '<tr><td>Sub-total</td><td>1</td><td>1</td><td>1</td><td>754.19</td></tr>'
        '<tr><td>Hybrid</td><td>Stock Exchange</td><td>1</td><td>1</td><td>1</td><td>(0.19)</td></tr>'
        '<tr><td>Sub-total</td><td>1</td><td>1</td><td>1</td><td>(0.19)</td></tr>'
        '<tr><td>Total</td><td>1</td><td>1</td><td>1</td><td>1,806.15</td></tr>'
        '<tr><td>Reporting Date</td><td>Derivative Products</td></tr>'
        '<tr><td>25-Sep-2026</td><td>Index Futures</td><td>1</td><td>2</td><td>3</td><td>4</td><td>5</td><td>6</td></tr>'
        '</table></body></html>')

    @staticmethod
    def tw(date, fx='-32,964,613,655', stat='OK'):
        if stat != 'OK':
            return {'stat': 'No Data!'}
        return {'stat': 'OK', 'date': date.replace('-', ''), 'data': [
            ['Dealers (Proprietary)', '1', '1', '4,235,536,088'], ['Dealers (Hedge)', '1', '1', '-2,897,105,667'],
            ['Securities Investment Trust Companies', '1', '1', '-12,823,263,300'],
            ['Foreign Investors include Mainland Area Investors(Foreign Dealers excluded)', '1', '1', fx],
            ['Foreign Dealers', '0', '0', '0'], ['Total', '1', '1', '-44,449,446,534']]}

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def test_nsdl_parse_parentheses_debt_sum_and_stop_at_derivatives(self):
        rows = zd.parse_nsdl_html(self.NSDL)
        self.assertEqual(rows[0], ['2026-09-23', -270.67, -24.91, None, -290.42, 95.8179])
        self.assertEqual(rows[1], ['2026-09-24', 754.19, None, -0.19, 1806.15, 95.731], 'brak długu = None, nie zero')
        self.assertEqual(len(rows), 2, 'tabela instrumentów pochodnych pominięta')
        with self.assertRaises(RuntimeError):
            zd.parse_nsdl_html('<table><tr><td>nic</td></tr></table>')

    def test_twse_parse_units_and_no_session(self):
        self.assertEqual(zd.parse_twse(self.tw('2026-09-24')), ['2026-09-24', -32964.6, -12823.3, 1338.4, -44449.4])
        self.assertIsNone(zd.parse_twse(self.tw('2026-09-20', stat='x')), 'weekend / święto = brak, nie zero')
        self.assertIsNone(zd.parse_twse({'stat': 'OK', 'date': '20260924', 'data': [['Total', '1', '1', '5']]}))

    def test_tw_dates_skip_weekend_known_and_today_before_close(self):
        now = datetime.datetime(2026, 9, 25, 10, 0)   # piątek 10:00 w Tajpej — dzisiejsza sesja jeszcze trwa
        d = zd.tw_dates({'2026-09-24'}, {'2026-09-22'}, now, first=False)
        self.assertNotIn('2026-09-25', d); self.assertNotIn('2026-09-24', d); self.assertNotIn('2026-09-22', d)
        self.assertNotIn('2026-09-20', d); self.assertIn('2026-09-23', d); self.assertEqual(d, sorted(d))
        self.assertIn('2026-09-25', zd.tw_dates(set(), set(), datetime.datetime(2026, 9, 25, 17, 0), first=False))

    def test_build_merges_history_converts_twd_and_keeps_failed_part(self):
        prev = {'in': {'d': [['2026-09-22', -67.67, -137.58, 2.82, -212.95, 95.8]]},
                'tw': {'d': [['2026-09-23', -1000.0, 0, 0, 0, -31.4, '2026-09-18']], 'empty': []}}

        def gj(url, headers=None):
            if 'DEXTAUS' in url:
                return {'observations': [{'date': '2026-09-18', 'value': '31.82'}, {'date': '2026-09-17', 'value': '.'}]}
            day = url.split('dayDate=')[1][:8]
            iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
            return self.tw(iso) if iso == '2026-09-24' else self.tw(iso, stat='x')

        with mock.patch.object(zd, 'get_bytes', lambda url, headers=None, timeout=60: self.NSDL.encode()), \
                mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd.time, 'sleep', lambda s: None), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.build_obce('KLUCZ', prev)
        self.assertEqual([r[0] for r in out['in']['d']], ['2026-09-22', '2026-09-23', '2026-09-24'], 'historia z poprzedniego pliku zostaje')
        tw = {r[0]: r for r in out['tw']['d']}
        self.assertEqual(tw['2026-09-24'][5:], [round(-32964.6 / 31.82, 1), '2026-09-18'])
        self.assertIn('2026-09-24', tw); self.assertIn('2026-09-23', tw)
        self.assertIn('2026-09-22', out['tw']['empty'], 'dzień bez sesji zapamiętany'); self.assertNotIn('2026-09-25', out['tw']['empty'], 'dzisiejszy brak nie jest świętem')
        self.assertEqual({k: v for k, v in zd.META['ok'].items() if k not in ('obce_hk', 'obce_br', 'obce_tr')}, {'obce_in': True, 'obce_tw': True})
        self.assertFalse(any('KLUCZ' in e for e in zd.META['errors']), 'klucz nigdy w komunikatach')

        def boom(url, headers=None, timeout=60):
            raise RuntimeError('HTTP Error 503')
        zd.META['ok'].clear()
        with mock.patch.object(zd, 'get_bytes', boom), mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd.time, 'sleep', lambda s: None), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out2 = zd.build_obce('', prev)
        self.assertIs(out2['in'], prev['in'], 'awaria NSDL: poprzednia część zostaje')
        self.assertFalse(zd.META['ok']['obce_in']); self.assertTrue(any(e.startswith('NSDL:') for e in zd.META['errors']))


class EtfHistoryV55(unittest.TestCase):
    """v55: SoSoValue oddaje ok. 21 dni — suma 22 sesji z historii poprzedniego pliku, tylko gdy okna się nakładają."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    @staticmethod
    def days(start, n, v=1.0):
        d0 = datetime.date.fromisoformat(start); out = []
        while len(out) < n:
            if d0.weekday() < 5:
                out.append(d0.isoformat())
            d0 += datetime.timedelta(days=1)
        return out

    def test_merge_overlap_extends_and_new_values_win(self):
        old = [[zd.ts(d), 1.0] for d in self.days('2026-08-24', 21)]
        new = [[zd.ts(d), 2.0] for d in self.days('2026-08-25', 21)]
        m = zd.etf_merge_days(old, new)
        self.assertEqual(len(m), 22); self.assertEqual(m[0], old[0]); self.assertEqual(m[-1][1], 2.0)
        self.assertEqual(sum(1 for r in m if r[1] == 2.0), 21, 'nakładające się dni: wartość z nowego okna')

    def test_merge_without_overlap_keeps_only_new(self):
        old = [[zd.ts(d), 1.0] for d in self.days('2026-06-01', 21)]
        new = [[zd.ts(d), 2.0] for d in self.days('2026-08-25', 21)]
        self.assertEqual(zd.etf_merge_days(old, new), new, 'luka między oknami — bez sklejania')
        self.assertEqual(zd.etf_merge_days(None, new), new)
        self.assertEqual(zd.etf_merge_days([['x', 1], [zd.ts('2026-08-25'), 'a']], new), new, 'śmieci z poprzedniego pliku pominięte')

    def test_build_uses_previous_history_for_22_sessions(self):
        new_dates = self.days('2026-08-25', 21)
        prev = {'assets': {s: {'day': [[zd.ts(d), 10.0] for d in self.days('2026-08-24', 21)]} for s in zd.ETF_SYMS}}
        history = {s: _rows(new_dates) for s in zd.ETF_SYMS}
        with mock.patch.object(zd, 'soso', _soso_factory(history, {s: [] for s in zd.ETF_SYMS}, {})), \
                mock.patch.object(zd, 'get_json', side_effect=RuntimeError('brak sieci')):
            out = zd.build_etf('klucz', '', prev)
            out0 = zd.build_etf('klucz', '')
        a = out['assets']['btc']
        self.assertEqual((len(a['day']), a['m_n']), (22, 22)); self.assertAlmostEqual(a['m'], 10.0 + 21 * 100.0)
        self.assertIsNone(out0['assets']['btc']['m'], 'bez poprzedniego pliku: 21 dni = brak sumy 22 sesji (bez zmian)')


class EerV56(unittest.TestCase):
    """v56: kursy efektywne BIS — zmiana 30 dni z danych dziennych, 12 mies. ze średnich miesięcznych; brak = None."""
    D = ('FREQ,EER_TYPE,EER_BASKET,REF_AREA,TIME_PERIOD,OBS_VALUE\n'
         'D,N,B,JP,2026-08-21,68.00\nD,N,B,JP,2026-08-24,68.06\nD,N,B,JP,2026-09-22,69.16\n'
         'D,N,B,US,2026-09-01,101.0\nD,N,B,US,2026-09-22,102.05\n'
         'D,N,B,SA,2026-09-22,NaN\n')
    M = ('FREQ,EER_TYPE,EER_BASKET,REF_AREA,TIME_PERIOD,OBS_VALUE\n'
         'M,N,B,JP,2025-08,70.0\nM,N,B,JP,2026-07,68.5\nM,N,B,JP,2026-08,68.25\nM,N,B,US,2026-08,101.5\n')

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear()

    def test_summary_30_days_and_12_months(self):
        rows = zd.eer_summary(zd.parse_cbpol_csv(self.D.encode()), zd.parse_cbpol_csv(self.M.encode()))
        jp, us = rows['JP'], rows['US']
        self.assertEqual((jp['v'], jp['d']), (69.16, '2026-09-22'))
        self.assertEqual(jp['c30'], round((69.16 / 68.00 - 1) * 100, 2), 'baza: ostatni dzień sprzed co najmniej 30 dni (21.08; 24.08 to tylko 29 dni)')
        self.assertEqual((jp['m'], jp['c12']), ('2026-08', round((68.25 / 70.0 - 1) * 100, 2)))
        self.assertIsNone(us['c30'], 'historia krótsza niż 30 dni = brak, nie zero'); self.assertIsNone(us['c12'], 'brak miesiąca rok wcześniej')
        self.assertNotIn('SA', rows, 'NaN pominięte')

    def test_build_urls_and_monthly_failure_is_soft(self):
        seen = []

        def gb(url, headers=None, timeout=60):
            seen.append(url)
            if '/M.N.B.' in url:
                raise RuntimeError('HTTP Error 500')
            return self.D.encode()
        with mock.patch.object(zd, 'get_bytes', gb):
            out = zd.build_eer()
        self.assertIn('D.N.B.US+XM', seen[0]); self.assertIn('detail=dataonly', seen[0])
        self.assertEqual(out['asof'], '2026-09-22'); self.assertIsNone(out['rows']['JP']['c12'])
        self.assertTrue(any(e.startswith('BIS kursy efektywne (miesięczne)') for e in zd.META['errors']))


class StablecoinChainsV58(unittest.TestCase):
    """v58: stablecoiny per sieć (DefiLlama /stablecoins) — tylko dolarowe; brak poprzedniej wartości = poza oknem, nie zero."""

    def test_sums_per_chain_and_missing_previous_is_left_out(self):
        j = {'peggedAssets': [
            {'pegType': 'peggedUSD', 'chainCirculating': {
                'Ethereum': {'current': {'peggedUSD': 100.0}, 'circulatingPrevDay': {'peggedUSD': 99.0}, 'circulatingPrevWeek': {'peggedUSD': 90.0}, 'circulatingPrevMonth': {'peggedUSD': 80.0}},
                'Solana': {'current': {'peggedUSD': 10.0}, 'circulatingPrevWeek': {'peggedUSD': 5.0}}}},
            {'pegType': 'peggedUSD', 'chainCirculating': {
                'Solana': {'current': {'peggedUSD': 30.0}, 'circulatingPrevDay': {'peggedUSD': 30.0}, 'circulatingPrevWeek': {'peggedUSD': 20.0}, 'circulatingPrevMonth': {'peggedUSD': 10.0}}}},
            {'pegType': 'peggedEUR', 'chainCirculating': {'Ethereum': {'current': {'peggedUSD': 999.0}}}}]}
        out = zd.parse_stabc(j)
        self.assertEqual(out['rows'][0], ['Ethereum', 100, 1, 10, 20], 'stablecoin euro pominięty')
        self.assertEqual(out['rows'][1], ['Solana', 40, 0, 15, 20], '30 dni: aktywo bez wartości sprzed miesiąca poza oknem (nie liczone jako 0)')
        self.assertEqual(out['total'], [140, 1, 25, 40]); self.assertEqual(out['n'], 2)
        with self.assertRaises(RuntimeError):
            zd.parse_stabc({'data': []})


class CoferV59(unittest.TestCase):
    """v59: MFW COFER — udziały walut w rezerwach świata (kwartalnie); zmiany tylko z dokładnego kwartału; brak = None."""
    DIMS = [('COUNTRY', ['G001']), ('INDICATOR', ['AFXRA', 'TFXRA', 'TFXRA_IMP']), ('FXR_CURRENCY', ['CI_EUR', 'CI_T', 'CI_USD']),
            ('TYPE_OF_TRANSFORMATION', ['NV_USD', 'SHRO_PT']), ('FREQUENCY', ['Q'])]
    PER = ['2025-Q2', '2024-Q2', '2025-Q1', 'zły']

    def test_quarters_shares_changes_and_missing(self):
        series = {'0:0:2:1:0': {0: '56.32', 1: '58.20', 2: '57.80'},        # USD udział
                  '0:0:2:0:0': {0: '7000000000000', 1: '6900000000000'},     # USD wartość
                  '0:0:0:1:0': {0: '20.10', 2: 'NaN'},                        # EUR udział; kwartał wcześniej NaN = brak
                  '0:0:1:0:0': {0: '12400000000000', 3: '1'},                 # suma przypisanych; okres „zły” pominięty
                  '0:1:1:0:0': {0: '13000000000000'},                          # suma wszystkich rezerw
                  '0:2:1:1:0': {0: '10.65'}}                                   # udział szacowany przez MFW
        out = zd.parse_cofer(_imf_sdmx(series, self.PER, self.DIMS))
        self.assertEqual(out['asof'], '2025-Q2'); self.assertEqual((out['alloc'], out['total'], out['alloc_pct'], out['imp_pct']), (12400.0, 13000.0, 95.4, 10.65))
        usd, eur = out['rows']['USD'], out['rows']['EUR']
        self.assertEqual((usd['sh'], usd['d1'], usd['d4'], usd['v'], usd['dv4']), (56.32, -1.48, -1.88, 7000.0, 100.0))
        self.assertEqual((eur['sh'], eur['d1'], eur['d4'], eur['v']), (20.1, None, None, None), 'brak = None, nie zero')
        self.assertEqual(out['order'], ['USD', 'EUR'])
        self.assertEqual(zd._q_add('2025-Q1', -1), '2024-Q4'); self.assertEqual(zd._q_add('2025-Q2', -4), '2024-Q2')
        with self.assertRaises(RuntimeError):
            zd.parse_cofer(_imf_sdmx({'0:0:2:1:0': {0: '56'}}, self.PER, self.DIMS))


class EtfHongKongV61(unittest.TestCase):
    """v61: ETF-y z Hongkongu — osobna część pliku; awaria = notatka, część USA bez zmian; historia jak w USA."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_hk_part_note_with_field_names_and_failure_is_only_a_note(self):
        dates = ['2026-09-22', '2026-09-23']
        seen = []

        def soso(path, key, _retry=True):
            seen.append(path)
            if 'country_code=HK' in path:
                if 'ETH' in path:
                    raise RuntimeError('HTTP Error 400')
                return [{'date': d, 'total_net_inflow': 5e6, 'cum_net_inflow': 3e8, 'total_net_assets': 4e8} for d in dates]
            if path.startswith('/etfs/summary-history'):
                return _rows(dates)
            return []
        with mock.patch.object(zd, 'soso', soso), mock.patch.object(zd, 'get_json', side_effect=RuntimeError('brak sieci')):
            out = zd.build_etf('klucz', '')
        self.assertEqual(sorted(out['hk']), ['btc'], 'ETH z błędem — pominięty, BTC jest')
        b = out['hk']['btc']
        self.assertEqual((b['d1'], b['w'], b['m'], b['cum'], b['aum']), (5.0, None, None, 300.0, 400.0), 'za krótko na 5 i 22 sesje = brak')
        self.assertEqual(sorted(out['assets']), sorted(zd.ETF_SYMS), 'część USA bez zmian')
        self.assertTrue(any(n.startswith('SoSoValue HK BTC: 2 dni do 2026-09-23; pola: cum_net_inflow, date,') for n in zd.META['notes']))
        self.assertTrue(any(n.startswith('SoSoValue HK ETH: HTTP Error 400') for n in zd.META['notes']))
        self.assertFalse(any('HK' in e for e in zd.META['errors']), 'Hongkong nigdy jako błąd strony')
        self.assertTrue(any('country_code=HK' in p for p in seen))


class TdHistoryV64(unittest.TestCase):
    """v64: plik cen ma ponad rok sesji (kwartał i rok na mapie z cen ETF-ów); koszt zapytania bez zmian."""

    def test_output_size_covers_a_year(self):
        self.assertGreaterEqual(zd.TD_OUTPUT, 253, '1R = 252 sesje + punkt odniesienia')
        seen = []

        def get(url, headers=None, timeout=30):
            seen.append(url); return 200, json.dumps({'SPY': {'status': 'error', 'code': 400, 'message': 'x'}})
        with mock.patch.object(zd, 'get', get):
            zd.td_batch(['SPY'], 'KLUCZ', _retry=False)
        self.assertIn('outputsize=260', seen[0])


class HkexV67(unittest.TestCase):
    """v67: HKEX Stock Connect southbound — kupno − sprzedaż (SSE + SZSE), mln HKD; 404 w przeszłości = dzień bez sesji."""
    JS = ('tabData = [{"id":0,"date":"2026-09-24","market":"SSE Northbound","tradingDay":1,"content":[{"table":{"schema":[["Total Turnover","DQB"]],"tr":[{"td":[["113,943.72"]]},{"td":[["999"]]}]}}]},'
          '{"id":1,"date":"2026-09-24","market":"SSE Southbound","tradingDay":1,"content":[{"table":{"schema":[["Total Turnover","Buy Turnover","Sell Turnover"]],"tr":[{"td":[["41,143.90"]]},{"td":[["22,121.38"]]},{"td":[["19,022.52"]]}]}}]},'
          '{"id":3,"date":"2026-09-24","market":"SZSE Southbound","tradingDay":1,"content":[{"table":{"schema":[["Total Turnover","Buy Turnover","Sell Turnover"]],"tr":[{"td":[["21,856.55"]]},{"td":[["10,828.73"]]},{"td":[["11,027.82"]]}]}}]}];')

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_parse_southbound_net_and_no_session(self):
        self.assertEqual(zd.parse_hkex(self.JS), ['2026-09-24', 2899.77, 32950.11, 30050.34, 2])
        self.assertIs(zd.parse_hkex(self.JS.replace('"tradingDay":1', '"tradingDay":0')), False, 'v69: dzień bez sesji (święto) = False, nie zero')
        self.assertIsNone(zd.parse_hkex('<html>404</html>'))

    def test_part_404_marks_holiday_and_converts_hkd(self):
        def gb(url, headers=None, timeout=60):
            d = url.split('daily_')[1][:8]
            if d == '20260924':
                return self.JS.encode()
            if d == '20260925':
                raise zd.urllib.error.HTTPError(url, 404, 'Not Found', {}, None)   # dzisiejszy plik jeszcze nie wyszedł
            return self.JS.replace('"tradingDay":1', '"tradingDay":0').replace('2026-09-24', d[:4] + '-' + d[4:6] + '-' + d[6:]).encode()   # v69: święto = plik z tradingDay 0

        def gj(url, headers=None):
            return {'observations': [{'date': '2026-09-18', 'value': '7.8456'}]}
        with mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd.time, 'sleep', lambda s: None), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.hkex_part(None, 'KLUCZ')
        self.assertEqual(out['d'][-1][:5], ['2026-09-24', 2899.77, 32950.11, 30050.34, 2])
        self.assertEqual(out['d'][-1][5:], [round(2899.77 / 7.8456, 1), '2026-09-18'])
        self.assertIn('2026-09-23', out['empty']); self.assertNotIn('2026-09-25', out['empty'], 'dzisiejszy brak nie jest świętem')
        self.assertFalse(zd.META['errors'])


class CftcExtraV68(unittest.TestCase):
    """v68: dodatkowe rynki CFTC (jen, funt, …) z tych samych plików; brak dodatkowego rynku = notatka, nie błąd."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['notes'].clear(); zd.META['ok'].clear()

    def test_extra_market_parsed_and_missing_extra_is_only_a_note(self):
        wk = _CFTC_WK.replace(',099741,', ',097741,').replace('EURO FX - CHICAGO', 'JAPANESE YEN - CHICAGO')
        std = _cftc_std(); std[zd.CFTC_WEEK_URL] = (_CFTC_WK.rstrip('\r\n') + '\r\n' + wk).encode()
        out = zd.build_cftc(fetch=_cftc_fetch(std), today=_CFTC_TODAY)
        self.assertEqual(zd.META['errors'], [], 'brak pozostałych dodatkowych rynków to nie błąd')
        jpy = out['markets']['jpy']
        self.assertEqual((jpy['code'], jpy['asof']), ('097741', '2026-09-15')); self.assertIn('JAPANESE YEN', jpy['name'])
        self.assertEqual(jpy['groups']['lev_funds']['net'], out['markets']['eur']['groups']['lev_funds']['net'])
        self.assertTrue(any(n.startswith('CFTC gbp: brak rynku 096742') for n in zd.META['notes']))
        self.assertNotIn('gbp', {k for k, v in out['markets'].items() if v})


class CalendarAndHkexV69(unittest.TestCase):
    """v69: jeden kalendarz sesji dla ETF-ów; 404 HKEX za dzień roboczy z przeszłości = błąd do ponowienia, nie święto."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['notes'].clear(); zd.META['ok'].clear()

    def test_fake_holiday_candle_removed(self):
        q = {'SPY': {'asof': '2025-12-26', 'd': [['2025-12-24', 1, 1], ['2025-12-26', 2, 1]]},
             'TUR': {'asof': '2025-12-26', 'd': [['2025-12-24', 1, 1], ['2025-12-25', 1, 1], ['2025-12-26', 2, 1]]}}
        self.assertEqual(zd._align_calendar(q), 1)
        self.assertEqual([r[0] for r in q['TUR']['d']], ['2025-12-24', '2025-12-26'])
        self.assertTrue(any('spoza wspólnego kalendarza' in n for n in zd.META['notes']))

    def test_hkex_past_404_is_a_failure_not_a_holiday(self):
        def gb(url, headers=None, timeout=60):
            d = url.split('daily_')[1][:8]
            if d == '20260924':
                return HkexV67.JS.encode()
            raise zd.urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
        with mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd.time, 'sleep', lambda s: None), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.hkex_part(None, '')
        self.assertNotIn('2026-09-23', out['empty'], 'brak pliku to nie święto')
        self.assertTrue(any(e.startswith('HKEX:') and 'HTTP 404' in e for e in zd.META['errors']))


class BilansV70(unittest.TestCase):
    """v70: MFW bilans płatniczy — mln USD, ostatni kwartał kraju, brak = brak (nie zero), straż skali, awaria = poprzedni plik."""
    DIMS = [('COUNTRY', ['KOR', 'USA', 'TWN']), ('BOP_ACCOUNTING_ENTRY', ['A_NFA_T', 'L_NIL_T', 'NETCD_T', 'CD_T']),
            ('INDICATOR', ['CAB', 'D_F', 'O_F', 'P_F', 'P_F5']), ('UNIT', ['USD']), ('FREQUENCY', ['Q'])]
    PER = ['2026-Q2', '2026-Q1', '2025-Q4', 'zły']

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_rows_units_quarters_and_missing(self):
        series = {'0:1:3:0:0': {0: '-47463300000', 1: '-41300000000', 3: '5'},   # KOR napływ portfelowy (okres „zły” pominięty)
                  '0:1:4:0:0': {0: '-63905400000'},                               # KOR akcje
                  '0:1:1:0:0': {1: '5961300000', 0: 'NaN'},                        # KOR bezpośrednie: 2026-Q2 NaN = brak
                  '0:0:3:0:0': {0: '18019000000'},                                # KOR mieszkańcy za granicę, portfel
                  '0:2:0:0:0': {0: '116630100000'},                               # KOR rachunek bieżący
                  '0:3:0:0:0': {0: '1'},                                           # CD_T nieużywany
                  '1:1:3:0:0': {1: '334100000000', 2: '423000000000'},             # USA napływ portfelowy
                  '2:1:3:0:0': {0: '1000000000'}}                                  # TWN spoza listy
        out = zd.parse_bilans(_imf_sdmx(series, self.PER, self.DIMS))
        kor, usa = out['rows']['KOR'], out['rows']['USA']
        self.assertEqual(kor['q'], '2026-Q2'); self.assertEqual(usa['q'], '2026-Q1')
        self.assertEqual(kor['s']['in_p'], [['2026-Q1', -41300.0], ['2026-Q2', -47463.3]])
        self.assertEqual(kor['s']['in_d'], [['2026-Q1', 5961.3]], 'NaN = brak, nie zero')
        self.assertEqual((kor['s']['in_pe'], kor['s']['out_p'], kor['s']['ca']), ([['2026-Q2', -63905.4]], [['2026-Q2', 18019.0]], [['2026-Q2', 116630.1]]))
        self.assertEqual(out['order'], ['USA', 'KOR']); self.assertEqual(out['asof_max'], '2026-Q2'); self.assertNotIn('TWN', out['rows'])
        with self.assertRaises(RuntimeError):
            zd.parse_bilans(_imf_sdmx({'1:1:3:0:0': {1: '334.1'}}, self.PER, self.DIMS))   # skala w mld zamiast USD
        with self.assertRaises(RuntimeError):
            zd.parse_bilans(_imf_sdmx({'0:2:0:0:0': {0: '1'}}, self.PER, self.DIMS))      # sam rachunek bieżący — bez napływu

    def test_build_url_and_main_flow_failure_keeps_previous(self):
        seen = []

        def gj(url, headers=None, timeout=60):
            seen.append(url); raise RuntimeError('HTTP Error 503')
        with mock.patch.object(zd, 'get_json', gj):
            with self.assertRaises(RuntimeError):
                zd.build_bilans()
        self.assertIn('IMF.STA/BOP/+/USA+CAN', seen[0]); self.assertIn('.L_NIL_T+A_NFA_T+NETCD_T.D_F+P_F+P_F5+P_F3+O_F+CAB.USD.Q?lastNObservations=8', seen[0])
        saved = {}
        prev = {'at': _iso(26 * 60), 'asof_max': '2026-Q1', 'rows': {}, 'order': []}
        offs = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True)
                for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy',
                          'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_safe', 'build_ue')]
        [p.start() for p in offs]
        try:
            with mock.patch.dict(os.environ, {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}, clear=False), \
                    mock.patch.object(zd, 'save', lambda name, obj: saved.__setitem__(name, obj)), \
                    mock.patch.object(zd, 'previous', lambda name: prev if name == 'bilans' else None), \
                    mock.patch.object(zd, 'build_bilans', side_effect=RuntimeError('HTTP Error 503')):
                zd.main()
        finally:
            [p.stop() for p in offs]
        self.assertIs(saved['bilans'], prev); self.assertIs(zd.META['ok']['bilans'], False)
        self.assertIn('MFW bilans płatniczy: HTTP Error 503', zd.META['errors'])


class BcbV71(unittest.TestCase):
    """v71: BCB — dzienne przepływy dolarów przez rynek walutowy Brazylii; seria bez odpowiedzi = stare wartości / None, nie 0."""
    DAYS = [('17/09/2026', {13970: '-1346.26818222', 13968: '2685.49075138', 13969: '4031.75893360', 13967: '-329.92553221', 13961: '-1676.19371443'}),
            ('18/09/2026', {13970: '-330.40093998', 13968: '2955.74363009', 13969: '3286.14457007', 13967: '-62.09649291', 13961: '-392.49743289'})]

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def gj(self, broken=()):
        self.urls = []

        def f(url, headers=None):
            self.urls.append(url)
            sid = int(url.split('bcdata.sgs.')[1].split('/')[0])
            if sid in broken:
                raise RuntimeError('HTTP Error 503')
            return [{'data': d, 'valor': v[sid]} for d, v in self.DAYS] + [{'data': 'zła', 'valor': '1'}, {'data': '19/09/2026', 'valor': 'NaN'}]
        return f

    def test_rows_identity_and_dates(self):
        with mock.patch.object(zd, 'get_json', self.gj()), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.bcb_part(None)
        self.assertEqual(out['d'], [['2026-09-17', -1346.27, 2685.49, 4031.76, -329.93, -1676.19], ['2026-09-18', -330.4, 2955.74, 3286.14, -62.1, -392.5]],
                         'zły zapis daty i NaN pominięte, nigdy 0')
        r = out['d'][-1]; self.assertAlmostEqual(r[1] + r[4], r[5], places=1)   # razem = finansowy + handlowy (tożsamość BCB)
        self.assertEqual(out['asof'], '2026-09-18'); self.assertEqual(zd.META['errors'], [])
        self.assertTrue(any('bcdata.sgs.13961/dados?formato=json&dataInicial=27/07/2026&dataFinal=25/09/2026' in u for u in self.urls), self.urls)

    def test_failed_series_keeps_old_column_and_reports(self):
        prev = {'d': [['2026-09-17', -1.0, 1.0, 2.0, 9.9, 8.9]]}
        with mock.patch.object(zd, 'get_json', self.gj(broken=(13967,))):
            out = zd.bcb_part(prev)
        rows = {r[0]: r for r in out['d']}
        self.assertEqual(rows['2026-09-17'][4], 9.9, 'seria bez odpowiedzi: stara wartość zostaje')
        self.assertIsNone(rows['2026-09-18'][4], 'nowy dzień bez tej serii = None, nie 0')
        self.assertEqual(rows['2026-09-18'][1], -330.4)
        self.assertTrue(any(e.startswith('BCB: 1 serie') for e in zd.META['errors']))
        with mock.patch.object(zd, 'get_json', self.gj(broken=(13970, 13968, 13969, 13967, 13961))):
            with self.assertRaises(RuntimeError):
                zd.bcb_part(prev)   # żadnego nowego dnia: build_obce zostawi poprzednią część


def _xlsx(sheets, shared=True):
    """Minimalny plik .xlsx do testów: {nazwa arkusza: [[komórki wiersza]]}; teksty jako wspólne napisy (t="s") albo inline."""
    import io, zipfile
    strs, buf = [], io.BytesIO()
    cref = lambda i: chr(65 + i)   # kolumny A–Z wystarczą w testach

    def cell(r, c, v):
        ref = f'{cref(c)}{r}'
        if isinstance(v, str):
            if shared:
                strs.append(v); return f'<c r="{ref}" t="s"><v>{len(strs) - 1}</v></c>'
            return f'<c r="{ref}" t="inlineStr"><is><t>{v}</t></is></c>'
        return f'<c r="{ref}"><v>{v}</v></c>'
    with zipfile.ZipFile(buf, 'w') as z:
        wb, rels = [], []
        for n, (name, rows) in enumerate(sheets.items(), 1):
            wb.append(f'<sheet name="{name}" sheetId="{n}" r:id="rId{n}"/>')
            rels.append(f'<Relationship Id="rId{n}" Type="x" Target="worksheets/sheet{n}.xml"/>')
            body = ''.join(f'<row r="{r}">' + ''.join(cell(r, c, v) for c, v in enumerate(row) if v is not None) + '</row>' for r, row in enumerate(rows, 1))
            z.writestr(f'xl/worksheets/sheet{n}.xml', f'<worksheet><sheetData>{body}</sheetData></worksheet>')
        z.writestr('xl/workbook.xml', '<workbook><sheets>' + ''.join(wb) + '</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships>' + ''.join(rels) + '</Relationships>')
        z.writestr('xl/sharedStrings.xml', '<sst>' + ''.join(f'<si><t>{s}</t></si>' for s in strs) + '</sst>')
    return buf.getvalue()


class SafeChinaVX(unittest.TestCase):
    """SAFE — kupno i sprzedaż walut przez banki w Chinach: wiersze po nazwie w sekcjach, mld USD, brak = None, straż skali."""
    HEAD = ['Item', 46204, 46235]   # 2026-07, 2026-08 (liczby seryjne Excela)
    ROWS = [['Monthly Data on Foreign Exchange Settlement and Sales by Banks (in USD)'], ['Unit: USD 100 million'], HEAD,
            ['I. Foreign exchange settlement', 2662.5672, 2518.2601], ['(I) by banks for themselves', 33.9, 35.8],
            ['(II) by banks for customers', 2628.6432, 2482.4808], ['1. Current Account', 2142.06, 2120.08],
            ['2. Capital and Financial Account', 486.5806, 362.3968], ['Including: Direct investment', 39.2, 33.2], ['       Portfolio investment', 434.0, 314.7],
            ['II. Foreign exchange sales', 2479.95, 2033.46], ['(I) by banks for themselves', 103.1, 70.2], ['(II) by banks for customers', 2376.8, 1963.2],
            ['1. Current Account', 1729.4, 1504.5], ['2. Capital and Financial Account', 647.3999, 458.7091], ['Including: Direct investment', 79.8, 44.8],
            ['       Portfolio investment', 520.6, 385.2],
            ['III. Balance', 182.6, 484.8], ['(I) by banks for themselves', -69.2, -34.4], ['(II) by banks for customers', 251.826, 519.2379],
            ['1. Current Account', 412.6453, 615.5502], ['   1.1 Trade in goods', 607.0, 746.1], ['2. Capital and Financial Account', -160.8193, -96.3123],
            ['Including: Direct investment', -40.5, -11.7], ['       Portfolio investment', -86.6, '-'],
            ['IV. Newly Signed Contract Amount of Forward Foreign Exchange Settlement and Sales', 420.4, 408.4], ['Balance', 1, 1]]

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_reader_parser_units_and_missing(self):
        for shared in (True, False):
            data = _xlsx({'in RMB (Monthly)': [['Item', 1]], 'in USD (Monthly)': self.ROWS}, shared=shared)
            m = zd.parse_safe(zd._xlsx_rows(data, 'in USD (Monthly)'))
            self.assertEqual(m, [['2026-07', 25.18, 41.26, -16.08, -4.05, -8.66, 48.66, 64.74],
                                 ['2026-08', 51.92, 61.56, -9.63, -1.17, None, 36.24, 45.87]], 'mld USD; „-” = brak, nie zero')
        self.assertEqual((zd._xlsx_month('2026.08'), zd._xlsx_month('46235'), zd._xlsx_month('Item')), ('2026-08', '2026-08', None))
        with self.assertRaises(RuntimeError):
            zd._xlsx_rows(_xlsx({'in RMB (Monthly)': [['Item', 1]]}), 'in USD (Monthly)')
        bad = [r if r[0] != '2. Capital and Financial Account' else [r[0], 4.866, 3.624] for r in self.ROWS]   # 100× za mało
        with self.assertRaises(RuntimeError):
            zd.parse_safe(zd._xlsx_rows(_xlsx({'in USD (Monthly)': bad}), 'in USD (Monthly)'))

    def test_build_finds_monthly_link_and_notes_identity(self):
        page = ('<a href="/en/file/file/20260915/aaa.xlsx">Data on Foreign Exchange Settlement and Sales by Banks in 2026 (by Region)</a>'
                '<a href="/en/file/file/20260915/bbb.xlsx"><span>Time-series Data of Foreign Exchange Settlement and Sales by Banks</span></a>')
        rows = [r if r[0] != '(II) by banks for customers' or r[1] != 251.826 else [r[0], 999.0, 519.2379] for r in self.ROWS]
        seen = []

        def gb(url, headers=None, timeout=60):
            seen.append(url)
            return page.encode() if url == zd.SAFE_PAGE else _xlsx({'in USD (Monthly)': rows})
        with mock.patch.object(zd, 'get_bytes', gb):
            out = zd.build_safe()
        self.assertEqual(seen[1], 'https://www.safe.gov.cn/en/file/file/20260915/bbb.xlsx', 'szereg czasowy, nie plik roczny')
        self.assertEqual((out['asof'], out['m'][-1][3]), ('2026-08', -9.63))
        self.assertTrue(any(n.startswith('SAFE: saldo klientów') and '2026-07' in n for n in zd.META['notes']), zd.META['notes'])
        with mock.patch.object(zd, 'get_bytes', lambda url, headers=None, timeout=60: b'<html>bez linku</html>'):
            with self.assertRaises(RuntimeError):
                zd.build_safe()


class ReviewV73(unittest.TestCase):
    """v73: święto w Chinach przy otwartym Hongkongu = brak sesji (nie zero); stare serie poza plikiem MFW; kalendarz ETF odporny."""

    @staticmethod
    def hk_file(day, buy='0.00', sell='0.00', trading=1, broken=False):
        mk = lambda name: {'id': 0, 'date': day, 'market': name, 'tradingDay': trading, 'content': [{'style': 1, 'table': {
            'schema': [['Total Turnover', 'Buy Turnover', 'Sell Turnover', 'Total Trade Count']],
            'tr': [] if broken else [{'td': [[str(float(buy) + float(sell))]]}, {'td': [[buy]]}, {'td': [[sell]]}, {'td': [['0']]}]}}]}
        north = {'id': 0, 'date': day, 'market': 'SSE Northbound', 'tradingDay': 0, 'content': []}
        return 'tabData = ' + json.dumps([north, mk('SSE Southbound'), mk('SZSE Southbound')]) + ';'

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_mainland_holiday_is_no_session_and_old_zero_rows_move_to_empty(self):
        self.assertIs(zd.parse_hkex(self.hk_file('2026-05-05')), False, 'tradingDay 1 z obrotem 0,00 = brak sesji, nie zero')
        self.assertEqual(zd.parse_hkex(self.hk_file('2026-09-24', '100.5', '50.25')), ['2026-09-24', 100.5, 201.0, 100.5, 2])
        self.assertIsNone(zd.parse_hkex(self.hk_file('2026-09-24', broken=True)), 'nieczytelna tabela w dniu sesji = nieczytelny plik')
        prev = {'d': [['2026-09-23', 3448.93, 42794.07, 39345.14, 2, 439.6, '2026-09-18'], ['2026-09-22', 0.0, 0.0, 0.0, 2, 0.0, '2026-09-18']], 'empty': []}

        def gb(url, headers=None, timeout=60):
            d = url.split('daily_')[1][:8]
            return self.hk_file(f'{d[:4]}-{d[4:6]}-{d[6:]}').encode()   # każdy dzień: Chiny zamknięte
        with mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd.time, 'sleep', lambda s: None), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.hkex_part(prev, '')
        self.assertEqual([r[0] for r in out['d']], ['2026-09-23'], 'dawny wiersz z zerem usunięty')
        self.assertIn('2026-09-22', out['empty']); self.assertIn('2026-09-24', out['empty'])

    def test_bilans_drops_series_that_ended_long_ago(self):
        dims = [('COUNTRY', ['VNM']), ('BOP_ACCOUNTING_ENTRY', ['L_NIL_T']), ('INDICATOR', ['D_F', 'P_F5']), ('UNIT', ['USD']), ('FREQUENCY', ['Q'])]
        out = zd.parse_bilans(_imf_sdmx({'0:0:0:0:0': {0: '5000000000'}, '0:0:1:0:0': {1: '100000000'}}, ['2026-Q1', '2014-Q4'], dims))
        self.assertEqual(out['rows']['VNM']['q'], '2026-Q1'); self.assertNotIn('in_pe', out['rows']['VNM']['s'], 'seria z 2014 poza plikiem')

    def test_calendar_uses_majority_when_spy_is_short_and_drops_empty_symbols(self):
        days = [f'2026-09-{d:02d}' for d in range(1, 21)]
        q = {'SPY': {'d': [[days[-1], 1, 1]]}, 'EWA': {'d': [[d, 1, 1] for d in days]}, 'EWJ': {'d': [[d, 1, 1] for d in days]},
             'TUR': {'d': [['2025-12-25', 1, 1]]}}
        zd._align_calendar(q)
        self.assertEqual(len(q['EWA']['d']), 20, 'krótka historia SPY nie obcina innych')
        self.assertNotIn('TUR', q); self.assertTrue(any('bez świec' in n and 'TUR' in n for n in zd.META['notes']))


class TurcjaV74(unittest.TestCase):
    """v74: CBRT — tygodniowe transakcje nierezydentów; tylko część B; nowszy plik poprawia tydzień; brak = None, nie 0."""
    ROWS = [[None, 'Table - 1. Shares and Debt Securities Held by Non-Residents (Million USD) (*)'],
            [None, 'A. STOCK (Market Value)', '18.09.2026', 46276], [None, 'STOCK TOTAL (**)', 148753.16, 153388.46], [None, 'Equity', 39355.01, 42410.94],
            [None, 'B. NET TRANSACTIONS (Adjusted for Market Prices and Exchange Rates)', '18.09.2026', 46276],
            [None, 'NET TRANSACTIONS TOTAL (**)', -316.01, 393.81], [None, 'B.1. Domestic Market Total (**)', -558.42, 423.06],
            [None, 'Equity', -109.83, 277.67], [None, 'GDDS (Outright Purchase)', -116.9, 151.15], [None, 'GDDS (Reverse Repo)', 0.61, 3.86],
            [None, 'Debt Securities Issued by Other Than General Government (***)', -331.69, '-'], [None, 'B.2. International Market Total', 242.41, -29.25],
            [None, 'General Government Issuances', -168.69, -52.28], [None, ''], [None, '(*) Data is disseminated provisionally']]

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def zipped(self, rows):
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('Securities Statistics.xlsx', _xlsx({'Contents': [['x']], 'T1_En': rows}))
        return buf.getvalue()

    def test_part_b_only_rows_by_label_and_revision(self):
        d = zd.parse_tcmb(zd._xlsx_rows(_xlsx({'T1_En': self.ROWS}), 'T1_En'))
        self.assertEqual(d, [['2026-09-11', 393.81, 277.67, 151.15, None, -29.25, -52.28],
                             ['2026-09-18', -316.01, -109.83, -116.9, -331.69, 242.41, -168.69]], 'akcje z części B, nie ze stanu; „-” = brak')
        r = d[-1]; self.assertAlmostEqual(r[2] + r[3] + r[4] + r[5], r[1], places=2)
        page = ('<a href="/wps/wcm/connect/dc9e/Securities+Statistics.zip?MOD=AJPERES&amp;CACHEID=ROOT-q3">ZIP</a>')
        seen = []

        def gb(url, headers=None, timeout=60):
            seen.append(url)
            return page.encode() if url == zd.TCMB_PAGE else self.zipped(self.ROWS)
        prev = {'d': [['2026-09-04', 1.0, 1.0, 1.0, 1.0, 1.0, 1.0], ['2026-09-11', 9.0, 9.0, 9.0, 9.0, 9.0, 9.0]]}
        with mock.patch.object(zd, 'get_bytes', gb):
            out = zd.tcmb_part(prev)
        self.assertEqual(seen[1], 'https://www.tcmb.gov.tr/wps/wcm/connect/dc9e/Securities+Statistics.zip?MOD=AJPERES&CACHEID=ROOT-q3')
        self.assertEqual([r[0] for r in out['d']], ['2026-09-04', '2026-09-11', '2026-09-18'], 'historia z poprzedniego pliku zostaje')
        self.assertEqual(out['d'][1][1], 393.81, 'nowszy plik poprawia tydzień'); self.assertEqual(out['asof'], '2026-09-18')
        with self.assertRaises(RuntimeError):
            zd.parse_tcmb(zd._xlsx_rows(_xlsx({'T1_En': self.ROWS[:4]}), 'T1_En'))


class EurostatUE(unittest.TestCase):
    """Eurostat bop_c6_m — JSON-stat → mln EUR, ostatni miesiąc kraju, brak = brak (nie zero), straż skali."""

    @staticmethod
    def js(values, geo=('DE', 'PL'), time=('2026-06', '2026-07')):
        dims = [('bop_item', ['FA__D__F', 'FA__P__F']), ('stk_flow', ['ASS', 'LIAB']), ('geo', list(geo)), ('time', list(time))]
        return {'id': [d for d, _ in dims], 'size': [len(v) for _, v in dims],
                'dimension': {d: {'category': {'index': {k: i for i, k in enumerate(v)}}} for d, v in dims}, 'value': values}

    def test_jsonstat_units_last_month_and_missing(self):
        # indeks = ((item*2 + flow)*2 + geo)*2 + time
        vals = {str(((1 * 2 + 1) * 2 + 0) * 2 + 1): 42440.0, str(((1 * 2 + 1) * 2 + 0) * 2 + 0): 27859.0,   # DE portfelowe napływ
                str(((1 * 2 + 1) * 2 + 1) * 2 + 1): 2422.2, str(((0 * 2 + 1) * 2 + 1) * 2 + 0): -935.4,      # PL portfelowe 07, bezpośrednie 06
                str(((1 * 2 + 0) * 2 + 1) * 2 + 1): 653.3}                                                    # PL portfelowe aktywa 07
        out = zd.parse_ue(self.js(vals))
        self.assertEqual(out['order'], ['DE', 'PL']); self.assertEqual(out['asof_max'], '2026-07')
        pl = out['rows']['PL']
        self.assertEqual(pl['m'], '2026-07'); self.assertEqual(pl['s']['in_p'], [['2026-07', 2422.2]]); self.assertEqual(pl['s']['in_d'], [['2026-06', -935.4]])
        self.assertEqual(pl['s']['out_p'], [['2026-07', 653.3]]); self.assertNotIn('in_o', pl['s'], 'brak = brak klucza, nie zero')
        self.assertEqual(out['rows']['DE']['s']['in_p'], [['2026-06', 27859.0], ['2026-07', 42440.0]])
        with self.assertRaises(RuntimeError):
            zd.parse_ue(self.js({str(((1 * 2 + 1) * 2 + 0) * 2 + 1): 42.44}))   # skala: mld zamiast mln
        with self.assertRaises(RuntimeError):
            zd.parse_ue(self.js({}))
        self.assertIn('bop_item=FA__P__F&bop_item=FA__D__F&bop_item=FA__O__F&stk_flow=LIAB&stk_flow=ASS', zd.UE_URL)
        self.assertIn('geo=PL', zd.UE_URL); self.assertIn('lastTimePeriod=13', zd.UE_URL)


if __name__ == '__main__':
    unittest.main()
