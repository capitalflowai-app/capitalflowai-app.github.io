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
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
        self.assertEqual([e for e in self.saved['meta']['errors'] if not e.startswith(('instytucje', 'poprzedni', 'krypto', 'TIC', 'BIS', 'CFTC', 'Coin Metrics', 'MFW', 'EBC kursy', 'obce', 'NSDL', 'TWSE', 'SAFE', 'Eurostat', 'Statistics Canada', 'FSS', 'MF SPW', 'Banxico', 'fundusze', 'BLS', 'OECD', 'Rynki'))],
                         ['brak SOSOVALUE_KEY', 'brak FINNHUB_KEY', 'brak TWELVEDATA_KEY', 'brak COINMARKETCAP_KEY', 'brak FRED_KEY', 'brak EIA_KEY', 'brak BEA_KEY'])


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
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
        self.p_v50 = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
                      for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
        self.ps += [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
        for fn in ('build_bis', 'build_cftc', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki'):   # pozostałe źródła v50 (mogą jeszcze nie istnieć); v95.3: bez pobierania funduszy i surowców w teście
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
        self.ps += [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in ('build_bis', 'build_cftc', 'build_cm', 'build_stopy', 'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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

        def gj(url, headers=None, timeout=30):
            if 'DEXTAUS' in url:
                return {'observations': [{'date': '2026-09-18', 'value': '31.82'}, {'date': '2026-09-17', 'value': '.'}]}
            day = url.split('dayDate=')[1][:8]
            iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'
            return self.tw(iso) if iso == '2026-09-24' else self.tw(iso, stat='x')

        with mock.patch.object(zd, 'get_bytes', lambda url, headers=None, timeout=60: self.NSDL.encode()), \
                mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd.time, 'sleep', lambda s: None), \
                mock.patch.object(zd, 'nsdl_http', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('bez sieci w teście'))), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.build_obce('KLUCZ', prev)
        self.assertEqual([r[0] for r in out['in']['d']], ['2026-09-22', '2026-09-23', '2026-09-24'], 'historia z poprzedniego pliku zostaje')
        tw = {r[0]: r for r in out['tw']['d']}
        self.assertEqual(tw['2026-09-24'][5:], [round(-32964.6 / 31.82, 1), '2026-09-18'])
        self.assertIn('2026-09-24', tw); self.assertIn('2026-09-23', tw)
        self.assertIn('2026-09-22', out['tw']['empty'], 'dzień bez sesji zapamiętany'); self.assertNotIn('2026-09-25', out['tw']['empty'], 'dzisiejszy brak nie jest świętem')
        self.assertEqual({k: v for k, v in zd.META['ok'].items() if k not in ('obce_hk', 'obce_br', 'obce_tr', 'obce_th')}, {'obce_in': True, 'obce_tw': True})
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
                          'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
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
            if sid > 20000:   # v79: miesięczny bilans płatniczy
                return [{'data': '01/07/2026', 'valor': {22924: '300', 22927: '100', 22936: '100', 22939: '100'}.get(sid, '50')}]
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
        self.assertTrue(any('bcdata.sgs.13961/dados?formato=json&dataInicial=21/08/2025&dataFinal=25/09/2026' in u for u in self.urls), self.urls)

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
        self.assertIn('geo=PL', zd.UE_URL); self.assertIn('lastTimePeriod=24', zd.UE_URL)


class ReviewV77(unittest.TestCase):
    """v77: czytnik .xlsx odporny na puste komórki i wiersze, tekst sformatowany, komórki bez adresu, system dat 1904;
    CBRT — straż skali; obce.json pamięta stan i błędy części, widoczne także przy przebiegu z pamięci."""
    NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def book(self, sheet, wbpr=''):
        import io, zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('xl/workbook.xml', f'<workbook {self.NS}>{wbpr}<sheets><sheet name="A &amp; B" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                                                      '<Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/sharedStrings.xml', f'<sst {self.NS}><si><t>Item</t></si><si/><si><r><t>Rich</t></r><r><t xml:space="preserve"> text</t></r></si></sst>')
            z.writestr('xl/worksheets/sheet1.xml', f'<worksheet {self.NS}><sheetData>{sheet}</sheetData></worksheet>')
        return buf.getvalue()

    def test_reader_empty_cells_rows_rich_text_and_1904(self):
        sheet = ('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" s="2"/><c r="C1"><v>46235</v></c></row><row r="2"/>'
                 '<row r="3"><c r="A3" t="s"><v>2</v></c><c r="B3" t="s"><v>1</v></c><c t="inlineStr"><is><t>x&amp;y</t></is></c></row>')
        rows = zd._xlsx_rows(self.book(sheet), 'A & B')
        self.assertEqual(rows, {1: {1: 'Item', 3: '46235'}, 3: {1: 'Rich text', 2: '', 3: 'x&y'}}, 'pusta komórka nie przesuwa lipca/sierpnia')
        with self.assertRaises(RuntimeError):
            zd._xlsx_rows(self.book(sheet, '<workbookPr date1904="1"/>'), 'A & B')

    def test_cbrt_scale_guard(self):
        rows = [r if r[1] != 'NET TRANSACTIONS TOTAL (**)' else [None, r[1], -316010000.0, 393.81] for r in TurcjaV74.ROWS]
        page = '<a href="/x/Securities+Statistics.zip?MOD=AJPERES">ZIP</a>'
        z = TurcjaV74.zipped(None, rows)
        with mock.patch.object(zd, 'get_bytes', lambda url, headers=None, timeout=60: page.encode() if url == zd.TCMB_PAGE else z):
            with self.assertRaises(RuntimeError):
                zd.tcmb_part(None)

    def test_obce_part_status_kept_and_shown_on_cached_runs(self):
        def boom(prev, key=''):
            raise RuntimeError('HTTP Error 503')

        def hk(prev, key):
            zd.META['errors'].append('HKEX: 1 dni bez odpowiedzi, np. 2026-09-23: HTTP 404'); return {'d': [['2026-09-24', 1.0]]}
        with mock.patch.object(zd, 'nsdl_part', lambda prev: {'d': [['2026-09-24', 1.0]]}), mock.patch.object(zd, 'twse_part', boom), \
                mock.patch.object(zd, 'hkex_part', hk), mock.patch.object(zd, 'bcb_part', lambda prev: {'d': [['2026-09-18', 1.0]]}), \
                mock.patch.object(zd, 'tcmb_part', lambda prev: {'d': [['2026-09-18', 1.0]]}), \
                mock.patch.object(zd, 'thbma_part', lambda prev, key: {'d': [['2026-09-24', 1.0]]}):
            out = zd.build_obce('', {})
        self.assertEqual(out['ok'], {'in': True, 'tw': False, 'hk': True, 'br': True, 'tr': True, 'th': True})
        self.assertEqual(out['errs']['tw'], ['TWSE: HTTP Error 503']); self.assertTrue(out['errs']['hk'][0].startswith('HKEX: 1 dni'))
        zd.META['errors'].clear(); zd.META['ok'].clear(); saved = {}
        prev = dict(out, at=_iso(30))   # v80: część z błędem ponawiana po 60 min
        offs = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True)
                for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy',
                          'build_kursy', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
        [p.start() for p in offs]
        try:
            with mock.patch.dict(os.environ, {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}, clear=False), \
                    mock.patch.object(zd, 'save', lambda name, obj: saved.__setitem__(name, obj)), \
                    mock.patch.object(zd, 'previous', lambda name: prev if name == 'obce' else None), \
                    mock.patch.object(zd, 'build_obce', side_effect=AssertionError('bez zapytań')):
                zd.main()
        finally:
            [p.stop() for p in offs]
        self.assertIs(saved['obce'], prev); self.assertEqual(zd.META['ok']['obce'], 'cached')
        self.assertIs(zd.META['ok']['obce_tw'], False); self.assertEqual(zd.META['ok']['obce_hk'], 'cached')
        self.assertIn('TWSE: HTTP Error 503', zd.META['errors']); self.assertTrue(any(e.startswith('HKEX: 1 dni') for e in zd.META['errors']))


class KanadaV78(unittest.TestCase):
    """v78: Statistics Canada — mln CAD, miesiąc z refPer, brak = None, skala ≠ miliony = błąd, notatka przy niezgodnej sumie."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    @staticmethod
    def vec(vid, pts, scale=6):
        return {'status': 'SUCCESS', 'object': {'vectorId': vid, 'vectorDataPoint': [
            {'refPer': d, 'value': v, 'scalarFactorCode': scale, 'statusCode': 0} for d, v in pts]}}

    def test_rows_units_identity_and_scale(self):
        j = [self.vec(61915649, [('2026-06-01', 41249.0), ('2026-07-01', 20653.0)]), self.vec(61915652, [('2026-07-01', 13453.0)]),
             self.vec(61915712, [('2026-07-01', 7200.0), ('2026-06-01', None)]), self.vec(61915682, [('2026-07-01', 25321.0)]),
             self.vec(61915655, [('2026-07-01', -11869.0), ('zły', 1)]), self.vec(999, [('2026-07-01', 5.0)])]
        m = zd.parse_kanada(j)
        self.assertEqual(m, [['2026-06', 41249.0, None, None, None, None], ['2026-07', 20653.0, 13453.0, 25321.0, -11869.0, 7200.0]], 'brak = None, nie zero')
        self.assertEqual(zd.META['notes'], [])
        j[1] = self.vec(61915652, [('2026-07-01', 1000.0)])
        zd.parse_kanada(j); self.assertTrue(any('razem ≠ dłużne + akcje' in n and '2026-07' in n for n in zd.META['notes']))
        with self.assertRaises(RuntimeError):
            zd.parse_kanada([self.vec(61915649, [('2026-07-01', 20.653)], scale=9)])
        with self.assertRaises(RuntimeError):
            zd.parse_kanada([])

    def test_build_url_one_get_with_five_vectors(self):
        seen = []
        with mock.patch.object(zd, 'get_json', lambda url, headers=None: seen.append(url) or [self.vec(61915649, [('2026-07-01', 1.0)])]), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.build_kanada()
        self.assertEqual(len(seen), 1); self.assertIn('vectorIds=%2261915649%22,%2261915652%22', seen[0])
        self.assertIn('startRefPeriod=2024-09-01&endReferencePeriod=2026-09-25', seen[0]); self.assertEqual(out['asof'], '2026-07')


class BrazyliaBopV79(unittest.TestCase):
    """v79: BCB miesięczny bilans płatniczy — mln USD, miesiąc z daty, seria bez odpowiedzi = stare wartości / None, awaria nie psuje dziennych."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_monthly_rows_identity_and_failure_isolated(self):
        vals = {22885: '7460.5', 22924: '2158.3', 22927: '1688.5', 22936: '167.9', 22939: '301.9', 22971: '3740.6', 22986: '11.7', 23001: '0', 23042: '0'}

        def gj(url, headers=None):
            sid = int(url.split('bcdata.sgs.')[1].split('/')[0])
            if sid == 22971:
                raise RuntimeError('HTTP Error 503')
            return [{'data': '01/06/2026', 'valor': '1'}, {'data': '01/07/2026', 'valor': vals[sid]}]
        with mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            rows = zd.bcb_bop([['2026-07', 1.0, 1.0, 1.0, 1.0, 1.0, 9.9]])
        self.assertEqual(rows[-1], ['2026-07', 7460.5, 2158.3, 1688.5, 167.9, 301.9, 9.9, 11.7, 0.0, 0.0], 'seria bez odpowiedzi: stara wartość zostaje')
        self.assertEqual(rows[0], ['2026-06', 1.0, 1.0, 1.0, 1.0, 1.0, None, 1.0, 1.0, 1.0], 'nowy miesiąc bez tej serii = None, nie 0')
        self.assertTrue(any(e.startswith('BCB bilans płatniczy: 1 serie') for e in zd.META['errors']))
        self.assertTrue(any('portfelowe ≠' in n and '2026-06' in n for n in zd.META['notes']), 'czerwiec 1 ≠ 1+1+1')

        def gj2(url, headers=None):
            sid = int(url.split('bcdata.sgs.')[1].split('/')[0])
            if sid > 20000:
                raise RuntimeError('HTTP Error 503')
            return [{'data': '18/09/2026', 'valor': '1'}]
        zd.META['errors'].clear()
        with mock.patch.object(zd, 'get_json', gj2), mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.bcb_part({'m': [['2026-06', 1.0, 2.0, 1.0, 0.5, 0.5, 3.0]]})
        self.assertEqual(out['d'][-1][0], '2026-09-18'); self.assertEqual(out['m'], [['2026-06', 1.0, 2.0, 1.0, 0.5, 0.5, 3.0]], 'awaria miesięcznych — poprzednie wiersze zostają')
        self.assertTrue(any(e.startswith('BCB bilans płatniczy:') for e in zd.META['errors']))


class ReviewV80(unittest.TestCase):
    """v80: Eurostat — pozostałe bez banku centralnego, miesiąc z kompletem, statusy, 24 miesiące; obce — brak części = pobierz;
    czytnik xlsx bez <rPh>; JSON-stat z indeksem jako lista."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    @staticmethod
    def js(values, status=None, geo=('DE', 'PL'), time=('2026-06', '2026-07'), as_list=False):
        dims = [('bop_item', ['FA__D__F', 'FA__O__F', 'FA__P__F']), ('sector10', ['S1', 'S121']), ('stk_flow', ['ASS', 'LIAB']), ('geo', list(geo)), ('time', list(time))]
        cat = lambda v: v if as_list else {k: i for i, k in enumerate(v)}
        return {'id': [d for d, _ in dims], 'size': [len(v) for _, v in dims], 'dimension': {d: {'category': {'index': cat(v)}} for d, v in dims},
                'value': values, 'status': status or {}}

    @staticmethod
    def ix(item, sec, flow, geo, time):
        return str((((item * 2 + sec) * 2 + flow) * 2 + geo) * 2 + time)

    def test_other_without_central_bank_full_month_and_flags(self):
        ix = self.ix
        v = {ix(2, 0, 1, 1, 1): 2422.2, ix(0, 0, 1, 1, 1): 509.5, ix(1, 0, 1, 1, 1): 7517.0, ix(1, 1, 1, 1, 1): 6834.0,   # PL 07: portfelowe, bezpośrednie, pozostałe S1 i S121
             ix(2, 0, 1, 1, 0): 100.0, ix(0, 0, 1, 1, 0): 50.0, ix(1, 0, 1, 1, 0): 999.0,                                   # PL 06: pozostałe bez S121
             ix(2, 0, 1, 0, 1): 42440.0, ix(2, 0, 1, 0, 0): 50.0}                                                          # DE: miesiąc bliski zera jest dozwolony
        out = zd.parse_ue(self.js(v, status={ix(2, 0, 1, 1, 1): 'e', ix(1, 1, 1, 1, 1): '|C'}))
        pl = out['rows']['PL']
        self.assertEqual(pl['s']['in_o'], [['2026-07', 683.0]], 'pozostałe bez banku centralnego; czerwiec bez S121 = brak, nie suma z TARGET2')
        self.assertEqual(pl['m'], '2026-07'); self.assertEqual(pl['f'], {'2026-07': 'e'})
        self.assertEqual(out['rows']['DE']['m'], '2026-07', 'bez kompletu — ostatni miesiąc z czymkolwiek')
        out2 = zd.parse_ue(self.js(v, as_list=True)); self.assertEqual(out2['rows']['PL']['s']['in_o'], [['2026-07', 683.0]], 'indeks kategorii jako lista')
        self.assertIn('sector10=S1&sector10=S121', zd.UE_URL); self.assertIn('lastTimePeriod=24', zd.UE_URL)
        with self.assertRaises(RuntimeError):
            zd.parse_ue(self.js({ix(2, 0, 1, 0, 1): 42.4, ix(2, 0, 1, 0, 0): 30.0}))   # skala: całe Niemcy poniżej 100 mln

    def test_latest_complete_month_wins(self):
        ix = self.ix
        v = {ix(2, 0, 1, 1, 0): 1.0, ix(0, 0, 1, 1, 0): 1.0, ix(1, 0, 1, 1, 0): 3.0, ix(1, 1, 1, 1, 0): 1.0, ix(2, 0, 1, 1, 1): 5.0,
             ix(2, 0, 1, 0, 1): 42440.0}
        self.assertEqual(zd.parse_ue(self.js(v))['rows']['PL']['m'], '2026-06', 'lipiec bez kompletu — czerwiec z kompletem')

    def test_obce_missing_part_forces_rebuild(self):
        prev = {'at': _iso(30), 'in': {'d': [['2026-09-24', 1.0]]}, 'tw': {'d': []}, 'hk': {'d': []}}
        new = {'at': zd.NOW, 'in': {}, 'tw': {}, 'hk': {}, 'br': {}, 'tr': {}}
        saved = {}
        offs = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True)
                for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy',
                          'build_kursy', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
        [p.start() for p in offs]
        try:
            with mock.patch.dict(os.environ, {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}, clear=False), \
                    mock.patch.object(zd, 'save', lambda name, obj: saved.__setitem__(name, obj)), \
                    mock.patch.object(zd, 'previous', lambda name: prev if name == 'obce' else None), \
                    mock.patch.object(zd, 'build_obce', return_value=new):
                zd.main()
        finally:
            [p.stop() for p in offs]
        self.assertIs(saved['obce'], new, 'brakuje części br i tr — pobieramy od nowa, choć plik jest świeży'); self.assertIs(zd.META['ok']['obce'], True)

    def test_xlsx_phonetic_runs_skipped(self):
        book = ReviewV77.book(ReviewV77(), '<row r="1"><c r="A1" t="s"><v>0</v></c></row>')
        import io, zipfile
        src = zipfile.ZipFile(io.BytesIO(book)); buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            for n in src.namelist():
                data = src.read(n)
                if n == 'xl/sharedStrings.xml':
                    data = data.replace(b'<si><t>Item</t></si>', b'<si><r><t>Kanji</t></r><rPh sb="0" eb="1"><t>kana</t></rPh></si>')
                z.writestr(n, data)
        self.assertEqual(zd._xlsx_rows(buf.getvalue(), 'A & B'), {1: {1: 'Kanji'}})


class UeFormatV80(unittest.TestCase):
    """v80: ue.json sprzed v80 (pozostałe z bankiem centralnym) jest przebudowywany mimo świeżości."""

    def test_old_format_rebuilt_new_format_cached(self):
        for unit, rebuilt in (('mln EUR, transakcje w miesiącu', True), ('… o pozostałe bez banku centralnego (S1 − S121)', False)):
            zd.META['errors'].clear(); zd.META['ok'].clear(); saved = {}
            prev = {'at': _iso(30), 'unit': unit, 'rows': {}, 'order': []}
            new = {'at': zd.NOW, 'unit': 'S121', 'rows': {}, 'order': []}
            offs = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True)
                    for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy',
                              'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
            [p.start() for p in offs]
            try:
                with mock.patch.dict(os.environ, {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}, clear=False), \
                        mock.patch.object(zd, 'save', lambda name, obj: saved.__setitem__(name, obj)), \
                        mock.patch.object(zd, 'previous', lambda name: prev if name == 'ue' else None), \
                        mock.patch.object(zd, 'build_ue', return_value=new):
                    zd.main()
            finally:
                [p.stop() for p in offs]
            self.assertIs(saved['ue'], new if rebuilt else prev, unit)


class KoreaV82(unittest.TestCase):
    """v82: FSS — tylko stałe zdanie komunikatu; bln/mld KRW; kupno +, sprzedaż −; historia z listy; kurs Fed; brak = None."""
    LIST = ('<a href="/eng/bbs/B0000211/view.do?nttId=229240&amp;menuNo=400010">Foreign Investors&#39; Stock and Bond Investment, August 2026</a>'
            '<a href="/eng/bbs/B0000211/view.do?nttId=1">Delinquency Rate on Domestic Banks</a>'
            '<a href="/eng/bbs/B0000211/view.do?nttId=223993&amp;menuNo=400010">Foreign Investors\' Stock and Bond Investment, July 2026</a>')
    AUG = '<div><p>Foreign investors bought a net KRW344.0 billion of listed stocks and sold a net KRW4.7360 trillion of listed bonds in August 2026. Foreign ...</p></div>'
    JUL = '<p>Foreign investors sold a net KRW31.6640 trillion of listed stocks and bought a net KRW2,388.0 billion of listed bonds in July 2026.</p>'

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_sentence_units_and_signs(self):
        self.assertEqual(zd.parse_fss(self.AUG), ['2026-08', 344.0, -4736.0])
        self.assertEqual(zd.parse_fss(self.JUL), ['2026-07', -31664.0, 2388.0])
        self.assertIsNone(zd.parse_fss('<p>Foreign investors were active in August 2026.</p>'), 'inne zdanie = brak, nie zgadywanie')
        self.assertEqual(zd.parse_fss('Foreign investors bought a net KRW1.5240 trillion of listed stocks and a net KRW7.8870 trillion of listed bonds in December 2025.'),
                         ['2025-12', 1524.0, 7887.0], 'bez drugiego czasownika — ten sam kierunek (komunikat z 12.2025)')
        self.assertEqual(zd.parse_fss('Foreign investors sold a net KRW13.3730 trillion of listed stock and bought a net KRW16.2540 trillion of listed bonds in November 2025.'),
                         ['2025-11', -13373.0, 16254.0], '„stock” w liczbie pojedynczej (komunikat z 11.2025)')

    def test_build_history_rate_and_unreadable_release(self):
        seen = []

        def gb(url, headers=None, timeout=60):
            seen.append(url)
            if 'list.do' in url:
                return self.LIST.encode() if url.endswith('pageIndex=1') else b'<html></html>'
            return (self.AUG if '229240' in url else '<p>Zmieniony układ</p>').encode()
        with mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd, 'fred_rates', lambda key, sid: {'2026-08-01': 1380.0}), \
                mock.patch.object(zd, '_now_utc', lambda: datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
            out = zd.build_korea('KLUCZ', {'m': [['2026-06', -49336.0, 4478.0, None, None, None]]})
        m = {r[0]: r for r in out['m']}
        self.assertEqual(m['2026-08'], ['2026-08', 344.0, -4736.0, round(344000 / 1380, 1), round(-4736000 / 1380, 1), 1380.0])
        self.assertEqual(m['2026-06'][:3], ['2026-06', -49336.0, 4478.0], 'historia z poprzedniego pliku zostaje')
        self.assertNotIn('2026-07', m, 'nieczytelny komunikat — bez miesiąca, nie zero')
        self.assertTrue(any(e.startswith('FSS: 1 komunikaty nieczytelne') for e in zd.META['errors']))
        self.assertIn('https://www.fss.or.kr/eng/bbs/B0000211/view.do?nttId=229240&menuNo=400010', seen)
        self.assertEqual(sum('list.do' in u for u in seen), zd.FSS_PAGES, 'v83: brakujący lipiec — szukamy na kolejnych stronach')
        self.assertIn('FSS: brak komunikatów za miesiące: 2026-07', zd.META['errors'], 'brak zgłaszany przy każdym przebiegu')
        self.assertFalse(any('KLUCZ' in e for e in zd.META['errors']))


class KoreaV83(unittest.TestCase):
    """v83: FSS — komplet miesięcy = jedna strona listy; strona 1 czytana zawsze (poprawki); brak nowego komunikatu = błąd; limit wartości."""

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def run_(self, pages, views, prev, now=datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
        seen = []

        def gb(url, headers=None, timeout=60):
            seen.append(url)
            if 'list.do' in url:
                return pages.get(int(url.rsplit('=', 1)[1]), '<html></html>').encode()
            return views[url.split('nttId=')[1].split('&')[0]].encode()
        with mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd, '_now_utc', lambda: now):
            return zd.build_korea('', prev), seen

    def test_complete_one_list_page_and_correction(self):
        page1 = KoreaV82.LIST
        views = {'229240': KoreaV82.AUG, '223993': KoreaV82.JUL.replace('KRW31.6640 trillion', 'KRW31.7000 trillion')}
        out, seen = self.run_({1: page1}, views, {'m': [['2026-07', -31664.0, 2388.0, None, None, None]]})
        self.assertEqual(sum('list.do' in u for u in seen), 1, 'komplet miesięcy — tylko strona 1')
        self.assertEqual({r[0]: r[1] for r in out['m']}['2026-07'], -31700.0, 'strona 1 czytana ponownie — poprawka wchodzi')
        self.assertEqual(zd.META['errors'], [])

    def test_stale_and_sanity(self):
        out, _ = self.run_({}, {}, {'m': [['2026-05', 1.0, 1.0, None, None, None]]})
        self.assertTrue(any(e.startswith('FSS: brak nowego komunikatu po 2026-05') for e in zd.META['errors']), zd.META['errors'])
        zd.META['errors'].clear()
        big = KoreaV82.AUG.replace('KRW344.0 billion', 'KRW4,7360 trillion')   # przecinek jako separator dziesiętny = 47 360 000 mld
        out, _ = self.run_({1: KoreaV82.LIST}, {'229240': big, '223993': KoreaV82.JUL}, {'m': [['2026-06', 1.0, 1.0, None, None, None]]})
        self.assertNotIn('2026-08', {r[0] for r in out['m']}, 'wartość ponad 100 bln KRW — nieczytelna, nie liczba')
        self.assertTrue(any(e.startswith('FSS: 1 komunikaty nieczytelne') for e in zd.META['errors']))


class ThailandV86(unittest.TestCase):
    """v86 / v86.1: ThaiBMA — dzień w toku pominięty, zakończony dzień bez części popołudniowej = brak; zły dzień = brak (nie blokada);
    ≈ USD kursem Fed; wiersze tylko ze źródła; BOM; kontrole skali, sum i świeżości."""

    @staticmethod
    def row(day, nf, tot=None, st=None, lt=None, ex=0.0, hold=900000.0, p3=1.0):
        tot = nf + ex if tot is None else tot
        st = tot if st is None else st
        lt = tot - st if lt is None else lt
        return {'Asof': day + 'T00:00:00', 'DisplayAsof': day + 'T00:00:00', 'P1Net': tot, 'P2Net': 0.0, 'P3Net': p3, 'ShortTermTrade': st,
                'LongTermTrade': lt, 'TotalNetTrade': tot, 'ExpireToday': ex, 'NetFlow': nf, 'NetHolding': hold}

    @classmethod
    def hist(cls, *extra):
        """35 wcześniejszych dni (sierpień i wrzesień do 15.09) + podane wiersze — źródło oddaje historię malejąco."""
        base = [(datetime.date(2026, 8, 1) + datetime.timedelta(days=i)).isoformat() for i in range(46)]
        rows = {d: cls.row(d, 100.0) for d in base}
        for r in extra:
            rows[r['Asof'][:10]] = r
        return [rows[k] for k in sorted(rows, reverse=True)]

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_parse_in_progress_gaps_and_duplicates(self):
        R = self.row
        src = [R('2026-09-25', -3648.0, p3=None), R('2026-09-24', 3216.0, st=1695.0), R('2026-09-24', 1.0),
               dict(R('2026-09-23', 1.0), NetFlow=None, TotalNetTrade=None), R('2026-09-22', -796.0, ex=3.0), R('2026-09-21', 5.0, p3=None)]
        out = zd.parse_thbma(src)
        self.assertEqual([r[0] for r in out], ['2026-09-21', '2026-09-22', '2026-09-23', '2026-09-24'], 'dzień w toku pominięty; rosnąco')
        self.assertEqual(out[0][1:], [None] * 6, 'zakończony dzień bez części popołudniowej = brak, nie pominięcie')
        self.assertEqual(out[2][1:], [None] * 6, 'dzień bez sum = brak')
        self.assertEqual(out[3][:4], ['2026-09-24', 3216.0, 3216.0, 1695.0], 'powtórzona data — pierwszy wiersz')
        self.assertTrue(any(n.startswith('ThaiBMA: różne wiersze dla tej samej daty (wzięty pierwszy): 2026-09-24') for n in zd.META['notes']))
        self.assertTrue(any('pokazany jako brak): 2026-09-21, 2026-09-23' in n for n in zd.META['notes']), zd.META['notes'])
        with self.assertRaises(RuntimeError):
            zd.parse_thbma([R('2026-09-25', 1.0, p3=None)])
        with self.assertRaises(RuntimeError):
            zd.parse_thbma({'error': 'x'})

    def run_(self, rows, key='KLUCZ', prev=None, now=datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc), raw=None):
        seen = []

        def gb(url, headers=None, timeout=60):
            seen.append(url); return raw if raw is not None else json.dumps(rows).encode()

        def gj(url, headers=None):
            seen.append(url)
            assert 'DEXTHUS' in url and 'limit=400' in url, url
            return {'observations': [{'date': '2026-09-18', 'value': '32.50'}, {'date': '2026-08-01', 'value': '.'}]}
        with mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd, '_now_utc', lambda: now):
            return zd.thbma_part(prev, key), seen

    def test_part_usd_rates_old_values_and_checks(self):
        R = self.row
        rows = self.hist(R('2026-09-24', 3216.0), R('2026-09-23', 4612.0, st=4000.0, lt=100.0), R('2026-09-17', 650.0))
        out, seen = self.run_(rows)
        d = {r[0]: r for r in out['d']}
        self.assertEqual(d['2026-09-24'][7:], [round(3216.0 / 32.5, 1), 32.5, '2026-09-18'], 'kurs z najbliższego wcześniejszego dnia')
        self.assertEqual(d['2026-09-17'][7:], [None, None, None], 'dzień przed pierwszym kursem — brak, nie zero')
        self.assertEqual(out['asof'], '2026-09-24'); self.assertEqual(out['url'], zd.THBMA_PAGE)
        self.assertTrue(any(n.startswith('ThaiBMA: sumy niezgodne w dniach: 2026-09-23') for n in zd.META['notes']), zd.META['notes'])
        self.assertEqual(zd.META['errors'], [])
        out2, seen2 = self.run_(rows, key='', prev=out)
        self.assertEqual({r[0]: r for r in out2['d']}['2026-09-24'][7:], [round(3216.0 / 32.5, 1), 32.5, '2026-09-18'], 'bez klucza — przeliczenie z poprzedniego pliku')
        self.assertFalse(any('DEXTHUS' in u for u in seen2))
        rows2 = self.hist(R('2026-09-24', 3300.0))
        out3, _ = self.run_(rows2, key='', prev=dict(out, d=out['d'] + [['2026-07-01', 1.0, 1.0, 1.0, 0.0, 0.0, 900000.0, None, None, None]]))
        self.assertEqual({r[0]: r for r in out3['d']}['2026-09-24'][7:], [None, None, None], 'poprawiona wartość — stare przeliczenie nie pasuje')
        self.assertNotIn('2026-07-01', {r[0] for r in out3['d']}, 'wiersze tylko ze źródła — bez starych dni z pliku')

    def test_scale_bom_json_and_stale(self):
        R = self.row
        with self.assertRaises(RuntimeError):
            self.run_(self.hist(R('2026-09-24', 3.2e6)))
        with self.assertRaises(RuntimeError):
            self.run_(self.hist(R('2026-09-24', 32.0, hold=920.0)))        # najnowszy stan 920 mln THB zamiast ok. 920 mld — zła skala
        zd.META['errors'].clear()
        out, _ = self.run_(self.hist(R('2026-09-24', 3216.0), R('2026-09-02', 2.5e5)))
        bad = {r[0]: r for r in out['d']}['2026-09-02']
        self.assertEqual(bad[1:], [None] * 9, 'stary zły dzień = brak, część działa dalej')
        self.assertTrue(any(e.startswith('ThaiBMA: wartości poza skalą (pokazane jako brak) w dniach: 2026-09-02') for e in zd.META['errors']))
        zd.META['errors'].clear()
        out, _ = self.run_(None, raw=b'\xef\xbb\xbf' + json.dumps(self.hist(R('2026-09-24', 3216.0))).encode())
        self.assertEqual(out['asof'], '2026-09-24', 'znak BOM na początku nie psuje odczytu')
        with self.assertRaisesRegex(RuntimeError, 'nie jest JSON'):
            self.run_(None, raw=b'<html>przerwa techniczna</html>')
        with self.assertRaisesRegex(RuntimeError, 'za mało dni'):
            self.run_([R('2026-09-24', 1.0)])
        self.run_(self.hist(R('2026-09-16', 1.0)), now=datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc))
        self.assertTrue(any(e.startswith('ThaiBMA: brak nowego pełnego dnia po 2026-09-16') for e in zd.META['errors']), zd.META['errors'])

class PolskaV87(unittest.TestCase):
    """v87 / v87.1: MF — nierezydenci w krajowych SPW: kolumny po nazwach, odnośniki po tytułach (zapas: nazwa pliku), kraje opcjonalnie
    (arkusze według miesiąca, udziały ok. 100%), brak kolumn i niezgodne sumy = błąd, kontrole skali i świeżości."""
    NS = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'

    @classmethod
    def book(cls, sheets):
        """{nazwa arkusza: [[komórki wiersza]]} → .xlsx (tekst inline, liczby jako liczby)."""
        import io, zipfile
        from xml.sax.saxutils import escape
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('xl/workbook.xml', f'<workbook {cls.NS}><sheets>' + ''.join(
                f'<sheet name="{escape(n)}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, n in enumerate(sheets)) + '</sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(
                f'<Relationship Id="rId{i + 1}" Type="x" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets))) + '</Relationships>')
            for i, rows in enumerate(sheets.values()):
                xml = ''
                for rn, row in enumerate(rows, 1):
                    cells = ''.join((f'<c r="{chr(65 + c)}{rn}"><v>{v}</v></c>' if isinstance(v, (int, float)) else
                                     f'<c r="{chr(65 + c)}{rn}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>') for c, v in enumerate(row) if v is not None)
                    xml += f'<row r="{rn}">{cells}</row>'
                z.writestr(f'xl/worksheets/sheet{i + 1}.xml', f'<worksheet {cls.NS}><sheetData>{xml}</sheetData></worksheet>')
        return buf.getvalue()

    TY = ['Data', 'Banki', 'Banki centralne', 'Instytucje publiczne', 'Zakłady ubezpieczeniowe', 'Fundusze emerytalne', 'Fundusze inwestycyjne',
          'Fundusze hedgingowe', 'Gospodarstwa domowe', 'Przedsiębiorstwa niefinansowe', 'Inne podmioty', 'Rachunki zbiorcze', 'Razem']
    RG = ['Data', 'Europa - kraje strefy euro', 'Europa - kraje UE spoza strefy euro', 'Europa - kraje spoza UE', 'Afryka',
          'Ameryka Południowa (w tym Karaiby)', 'Ameryka Północna', 'Australia i Oceania', 'Azja (bez Bliskiego Wschodu)', 'Bliski Wschód',
          'Rachunki zbiorcze', 'Razem']

    def st_book(self, tot_jul=204131.8, swap=False, drop=None):
        ser = {'2026-05-31': 46173, '2026-06-30': 46203, '2026-07-31': 46234}
        vals = {'2026-05-31': 206240.0, '2026-06-30': 198955.2, '2026-07-31': tot_jul}
        head = list(self.TY)
        rows_t = []
        for d, s in ser.items():
            v = vals[d]
            parts = [v * 0.1, v * 0.05, 0, 0, 0, v * 0.35, 0, 0, 0, 0, v * 0.5]
            rows_t.append([s] + parts + [sum(parts)])
        if swap:
            head = [head[0], head[2], head[1]] + head[3:]
            rows_t = [[r[0], r[2], r[1]] + r[3:] for r in rows_t]
        if drop:
            i = head.index(drop); head = head[:i] + head[i + 1:]; rows_t = [r[:i] + r[i + 1:] for r in rows_t]
        rows_t = [['Struktura podmiotowa nierezydentów w krajowych SPW (mln zł)'], [], head] + rows_t
        rows_r = [['Struktura geograficzna'], [], self.RG] + [[s] + [vals[d] * 0.3, 0, 0, 0, 0, vals[d] * 0.2, 0, 0, 0, vals[d] * 0.5, vals[d]] for d, s in ser.items()]
        rows_b = [['x'], [], ['Data', 'Banki', 'Razem']] + [[s, 0, vals[d] - 100] for d, s in ser.items()]
        rows_s = [['x'], [], ['Data', 'Banki', 'Razem']] + [[s, 0, 100] for d, s in ser.items()]
        return self.book({'Legenda': [['Tabele']], 'Razem_podmiot': rows_t, 'Razem_region': rows_r,
                          'Obligacje skarbowe_podmiot': rows_b, 'Bony skarbowe_podmiot': rows_s})

    def kr_book(self, order=('Lipiec2026(July2026)', 'Czerwiec2026(June2026)', 'Maj2026(May2026)'), others=0.2):
        def sheet(jp):
            return [['Kraje o udziale w zadłużeniu nierezydentów* w krajowych SPW większym niż 1% / Countries…'],
                    ['Kraje/Countries', 'Wartość nominalna', 'Udział'], [],
                    ['Japonia/Japan', jp, 0.5], ['Holandia/Netherlands (the)', 7678.98, 0.3], ['Pozostałe kraje/Others', 7043.42, others],
                    ['Suma/Total*', 92030.03, 1.0], ['Rachunki zbiorcze/Omnibus accounts', 97615.88, '-'], ['Banki centralne/Central banks', 14485.92, '-'],
                    ['Razem nierezydenci/Non-residents total', 204131.82, '-']]
        vals = {'Lipiec2026(July2026)': 18031.64, 'Czerwiec2026(June2026)': 17382.46, 'Maj2026(May2026)': 1.0}
        return self.book({n: sheet(vals[n]) for n in order})

    PAGE = ('<a class="file-download" href="/attachment/e73b4c6d-7ad4-4feb-81ce-dde6f293c39f" download>Struktura podmiotowa zadłużenia wobec nierezydentów '
            'w krajowych obligacjach rynkowych po seriach<br/><span>x.xls</span></a>'
            '<a class="file-download" href="/attachment/9ab3f0b9-1742-4b00-a6d9-a6a7753368ee" target="_blank" download\naria-label="Pobierz">\n'
            'Struktura podmiotowa zadłużenia wobec nierezydentów w krajowych SPW<br/>\n<span class="extension">Struktura&#8203;_nierezydentow07.xlsm</span></a>'
            '<a class="file-download" href="/attachment/fc49ffc2-3403-4ab7-977b-411ed9964215" download>Zadłużenie wobec nierezydentów w krajowych SPW po krajach'
            '<br/><span>Nierezydenci&#8203;_kraje07.xlsx</span></a>')

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def run_(self, st=None, kr=None, page=None, now=datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
        st, kr, page = st or self.st_book(), kr if kr is not None else self.kr_book(), page or self.PAGE

        def gb(url, headers=None, timeout=60):
            if url == zd.SPW_PAGE:
                return page.encode()
            if url.endswith('9ab3f0b9-1742-4b00-a6d9-a6a7753368ee'):
                return st
            if url.endswith('fc49ffc2-3403-4ab7-977b-411ed9964215'):
                if isinstance(kr, Exception):
                    raise kr
                return kr
            raise AssertionError(url)
        with mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd, '_now_utc', lambda: now):
            return zd.build_spw()

    def test_links_by_title_and_by_file_name(self):
        L = zd.spw_links(self.PAGE)
        self.assertEqual(L, {'st': 'https://www.gov.pl/attachment/9ab3f0b9-1742-4b00-a6d9-a6a7753368ee',
                             'kr': 'https://www.gov.pl/attachment/fc49ffc2-3403-4ab7-977b-411ed9964215'}, 'plik „po seriach” pominięty')
        renamed = self.PAGE.replace('Struktura podmiotowa zadłużenia wobec nierezydentów w krajowych SPW<br/>', 'Nierezydenci — struktura<br/>')
        self.assertEqual(zd.spw_links(renamed)['st'], 'https://www.gov.pl/attachment/9ab3f0b9-1742-4b00-a6d9-a6a7753368ee', 'zmieniony tytuł — plik po nazwie')

    def test_build_months_groups_countries(self):
        out = self.run_()
        self.assertEqual([r[0] for r in out['m']], ['2026-05', '2026-06', '2026-07'])
        self.assertEqual(out['m'][-1], ['2026-07', 204131.8, 204031.8, 100.0])
        self.assertAlmostEqual(dict(out['t']['cb'])['2026-07'], 204131.8 * 0.05)
        self.assertAlmostEqual(dict(out['t']['bank'])['2026-07'], 204131.8 * 0.1, msg='„Banki” to nie „Banki centralne”')
        self.assertAlmostEqual(dict(out['r']['omni'])['2026-07'], 204131.8 * 0.5)
        self.assertEqual([k['m'] for k in out['kr']], ['2026-07', '2026-06'], 'dwa najnowsze arkusze')
        self.assertEqual(out['kr'][0]['c'][0], ['Japonia', 'Japan', 18031.64, 50.0])
        self.assertEqual(out['kr'][0]['c'][1][1], 'Netherlands', 'bez „(the)”')
        self.assertEqual([c[0] for c in out['kr'][0]['c']], ['Japonia', 'Holandia', 'Pozostałe kraje'], 'bez sum, rachunków zbiorczych i banków centralnych')
        self.assertEqual(zd.META['errors'], []); self.assertEqual(zd.META['notes'], [])
        out2 = self.run_(st=self.st_book(swap=True), kr=self.kr_book(order=('Maj2026(May2026)', 'Lipiec2026(July2026)', 'Czerwiec2026(June2026)')))
        self.assertAlmostEqual(dict(out2['t']['cb'])['2026-07'], 204131.8 * 0.05, msg='kolumny po nazwach, nie po kolejności')
        self.assertEqual([k['m'] for k in out2['kr']], ['2026-07', '2026-06'], 'arkusze według miesiąca, nie kolejności w pliku')

    def test_countries_optional_columns_scale_and_stale(self):
        out = self.run_(kr=RuntimeError('HTTP Error 503'))
        self.assertNotIn('kr', out); self.assertTrue(any(e.startswith('MF SPW kraje: HTTP Error 503') for e in zd.META['errors']))
        zd.META['errors'].clear()
        out = self.run_(kr=self.kr_book(others=0.9))
        self.assertNotIn('kr', out); self.assertTrue(any('sumują się do 170.0%' in e for e in zd.META['errors']), zd.META['errors'])
        zd.META['errors'].clear()
        self.run_(st=self.st_book(drop='Fundusze hedgingowe'))
        self.assertIn('MF SPW: brak kolumn: hf', zd.META['errors'])
        zd.META['errors'].clear()
        with self.assertRaises(RuntimeError):
            self.run_(st=self.st_book(tot_jul=204.1))          # 204 mln zł zamiast 204 mld — zła skala
        zd.META['errors'].clear()
        self.run_(now=datetime.datetime(2026, 10, 20, 9, 0, tzinfo=datetime.timezone.utc))
        self.assertIn('MF SPW: brak nowego miesiąca po 2026-07', zd.META['errors'])
        with self.assertRaises(RuntimeError):
            self.run_(page='<a href="/attachment/x">inne</a>')

class MeksykV88(unittest.TestCase):
    """v88 / v88.1: Banxico — kolumny po kodach serii, „N/E” = brak, POST bez tokenu, rodzaje papierów (Udibonos × UDI),
    ≈ USD kursem Fed z dnia danych, kontrole skali i świeżości."""
    CSV = ('\r\n"Banco de México"\r\n\r\n"Valores en circulación"\r\n\r\n"Título","GUBERNAMENTAL, Total en Circulación (I + II)","GUBERNAMENTAL, Residentes en el Extranjero (II)"\r\n'
           '"Periodicidad","Diaria","Diaria"\r\n"Fecha","SF65219","SF65218"\r\n"11/09/2026","16096101.67","1789166.23"\r\n'
           '"14/09/2026","16097115.95","1788646.44"\r\n"10/09/2026","16090000.00","N/E"\r\n"12/09/2026","",""\r\n')
    CSV2 = ('"Fecha","SF65218","SF65219","SF65137","SF65046","SF65107","SP68257"\r\n'
            '"14/09/2026","1788646.44","16097115.95","1512900.00","202500.00","5200.00","8.84"\r\n'
            '"15/09/2026","N/E","N/E","N/E","N/E","N/E","8.845"\r\n')

    def setUp(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); zd.META['notes'].clear()

    def test_parse_by_codes_gaps_and_instruments(self):
        out = zd.parse_bmx(self.CSV)
        self.assertEqual(out, [['2026-09-11', 1789166.23, 16096101.67, None, None, None], ['2026-09-14', 1788646.44, 16097115.95, None, None, None]],
                         'po kodach, nie po kolejności; N/E i puste = brak dnia; bez serii rodzajów — brak, nie zero')
        out2 = zd.parse_bmx(self.CSV2)
        self.assertEqual(out2, [['2026-09-14', 1788646.44, 16097115.95, 1512900.0, 202500.0, round(5200.0 * 8.84, 2)]], 'Udibonos: mln UDI × wartość UDI; dzień z samą UDI pominięty')
        with self.assertRaises(RuntimeError):
            zd.parse_bmx('"Fecha","SF65219"\r\n"14/09/2026","1"\r\n')

    def run_(self, csv_text, key='KLUCZ', now=datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)):
        seen = []

        def pb(url, form, timeout=90):
            seen.append((url, form)); return csv_text.encode('latin-1')

        def gj(url, headers=None):
            assert 'DEXMXUS' in url, url
            return {'observations': [{'date': '2026-09-18', 'value': '18.25'}, {'date': '2026-09-11', 'value': '17.11'}, {'date': '2026-09-17', 'value': '.'}]}
        with mock.patch.object(zd, 'post_bytes', pb), mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd, '_now_utc', lambda: now):
            return zd.build_meksyk(key), seen

    def test_build_form_fx_scale_and_stale(self):
        out, seen = self.run_(self.CSV)
        url, form = seen[0]
        self.assertEqual(url, zd.BMX_URL); self.assertEqual(form['series'], ['SF65218', 'SF65219', 'SF65137', 'SF65046', 'SF65107', 'SP68257'])
        self.assertEqual(form['anoInicial'], '2024', 'dwa lata wstecz — w styczniu też jest koniec roku'); self.assertIn('formatoCSV.x', form)
        self.assertNotIn('token', json.dumps(form).lower())
        self.assertEqual(out['asof'], '2026-09-14'); self.assertEqual(out['fx'], [17.11, '2026-09-11'], 'kurs z dnia danych albo wcześniejszego, nie najnowszy')
        self.assertEqual(out['url'], zd.BMX_PAGE); self.assertEqual(zd.META['errors'], [])
        out2, _ = self.run_(self.CSV, key='')
        self.assertNotIn('fx', out2, 'bez klucza — bez przeliczenia, nie zero')
        with self.assertRaises(RuntimeError):
            self.run_(self.CSV.replace('1788646.44', '1788.64'))          # 1,8 mld MXN zamiast 1,8 bln — zła skala
        with self.assertRaises(RuntimeError):
            self.run_(self.CSV.replace('16097115.95', '1000000.00'))      # nierezydenci więcej niż całość
        zd.META['errors'].clear()
        self.run_(self.CSV, now=datetime.datetime(2026, 10, 20, 9, 0, tzinfo=datetime.timezone.utc))
        self.assertIn('Banxico: brak nowego dnia po 2026-09-14', zd.META['errors'])
        zd.META['notes'].clear()
        self.run_(self.CSV2.replace('"1512900.00"', '"1712900.00"'))
        self.assertTrue(any(n.startswith('Banxico: Bonos M + Cetes + Udibonos większe niż całość') for n in zd.META['notes']), zd.META['notes'])

class MeksykFormatV882(unittest.TestCase):
    """v88.2: meksyk.json bez kolumn rodzajów papierów jest pobierany od razu; plik w nowym formacie — z pamięci."""

    def test_old_format_rebuilt_new_format_cached(self):
        for row, rebuilt in ((['2026-09-14', 1788646.44, 16097115.95], True), (['2026-09-14', 1788646.44, 16097115.95, 1.0, 1.0, 1.0], False)):
            zd.META['errors'].clear(); zd.META['ok'].clear(); saved = {}
            prev = {'at': _iso(30), 'd': [row]}
            new = {'at': zd.NOW, 'd': [row + [None] * (6 - len(row))]}
            offs = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True)
                    for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy',
                              'build_kursy', 'build_obce', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
            [p.start() for p in offs]
            try:
                with mock.patch.dict(os.environ, {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}, clear=False), \
                        mock.patch.object(zd, 'save', lambda name, obj: saved.__setitem__(name, obj)), \
                        mock.patch.object(zd, 'previous', lambda name: prev if name == 'meksyk' else None), \
                        mock.patch.object(zd, 'build_meksyk', return_value=new):
                    zd.main()
            finally:
                [p.stop() for p in offs]
            self.assertIs(saved['meksyk'], new if rebuilt else prev, 'stary format — od razu nowy plik' if rebuilt else 'nowy format — z pamięci')


class TrendyV89(unittest.TestCase):
    """v89: TRENDY — tydzień porównany z 4 poprzednimi; brak w oknie = brak wyniku; stan „za stare” po zwykłym opóźnieniu źródła."""

    @staticmethod
    def blocks(*sums, size=5):
        """Sumy tygodni od najstarszego → wartości dzienne (każdy dzień = suma / size)."""
        return [s / size for s in sums for _ in range(size)]

    @staticmethod
    def weekdays(end, n):
        """n kolejnych dni roboczych kończących się na `end` (data ISO)."""
        d, out = datetime.date.fromisoformat(end), []
        while len(out) < n:
            if d.weekday() < 5:
                out.append(d.isoformat())
            d -= datetime.timedelta(days=1)
        return out[::-1]

    def test_state_rules(self):
        prev = [100, 100, 90, 110, 100, 80, 120, 100]            # od najstarszego; 4 ostatnie przed bieżącym: 100, 80, 120, 100
        t = zd.trend_state(self.blocks(*prev, 300), 5)
        self.assertEqual((t['st'], t['n'], t['lc']), ('in_up', 8, False))
        self.assertAlmostEqual(t['base'], 100); self.assertAlmostEqual(t['d'], 8.0, msg='rozrzut 11,95 < 1/4 typowego tygodnia (25) — próg 25')
        self.assertTrue(t['x'], '|d| ≥ 3 przy 8 tygodniach historii')
        self.assertEqual(zd.trend_state(self.blocks(*[200] * 8, 120), 5)['st'], 'in_down', 'napływ wyraźny, ale o 1,6 rozrzutu słabszy niż zwykle')
        self.assertEqual(zd.trend_state(self.blocks(*[200] * 8, 190), 5)['st'], 'in_flat')
        self.assertEqual(zd.trend_state(self.blocks(*[-100] * 8, -20), 5)['st'], 'out_stop', 'zwykle odpływ, w tym tygodniu prawie nic (v90)')
        self.assertEqual(zd.trend_state(self.blocks(*[-100] * 8, -300), 5)['st'], 'out_up')
        self.assertEqual(zd.trend_state(self.blocks(*[-100] * 8, 200), 5)['st'], 'in_rev', 'napływ po tygodniach odpływu — nie „większy niż zwykle”')
        self.assertEqual(zd.trend_state(self.blocks(*[10, -10] * 4, 200), 5)['st'], 'in_new', 'napływ po okresie bez wyraźnego kierunku')
        v = self.blocks(*[100] * 8) + [150, -20, -20, -20, -20]          # suma 70 (≥ 0,5 i < 1 typowego tygodnia), tylko 1 z 5 sesji na plus
        self.assertEqual(zd.trend_state(v, 5)['st'], 'mixed', 'duża suma z jednego dnia — tydzień niejednolity, nie „bez zmian”')
        v = self.blocks(*[100] * 8) + [200, -30, -30, -30, -10]          # suma 100 = typowy tydzień: kierunek wyraźny mimo dni
        self.assertEqual(zd.trend_state(v, 5)['st'], 'in_flat')
        t = zd.trend_state(self.blocks(100, 100, 100, 300), 5)
        self.assertEqual((t['st'], t['n']), ('short', 3), 'mniej niż 4 poprzednie tygodnie')
        self.assertEqual(zd.trend_state(self.blocks(*[100] * 8, 300)[:-1] + [None], 5)['st'], 'gap', 'brak dnia w bieżącym tygodniu — brak wyniku')
        t = zd.trend_state(self.blocks(*[100] * 5, 300), 5)
        self.assertEqual((t['st'], t['n'], t['lc'], t['x']), ('in_dir', 5, True, False), '5 tygodni: tylko kierunek, bez oceny siły i bez „wyjątkowo”')
        self.assertEqual(zd.trend_state([None] * 5 + self.blocks(*[100] * 4, 300), 5)['n'], 4)
        t = zd.trend_state([0.0] * 45, 5)
        self.assertEqual((t['st'], t.get('d')), ('none', None), 'same zera — bez dzielenia przez zero')
        self.assertEqual(zd.trend_state([10] * 8 + [50], 1)['st'], 'in_up', 'dane tygodniowe: bez warunku większości dni')
        self.assertEqual(zd.trend_state(self.blocks(*[70] * 8, 210, size=7), 7)['st'], 'in_up')
        self.assertEqual(zd.trend_state([float('nan')] + self.blocks(*[100] * 8, 300)[1:], 5)['n'], 7, 'NaN to brak, nie liczba')

    def test_calendar_gaps(self):
        ds = self.weekdays('2026-09-18', 45)
        v = self.blocks(*[100] * 8, 300)
        self.assertEqual(zd.trend_state(v, 5, ds, 11)['st'], 'in_up')
        ds2 = ds[:-5] + ['2026-09-21', '2026-09-22', '2026-09-23', '2026-09-24', '2026-10-05']   # ostatnie 5 wierszy na 15 dniach
        self.assertEqual(zd.trend_state(v, 5, ds2, 11)['st'], 'gap', 'brak wierszy z kilku dni w tygodniu — brak wyniku, nie ciche sklejenie')
        tw = {'d': [[d, 10.0, 0, 0, 0, 0.3, d] for d in ds], 'empty': []}
        del tw['d'][-3]                                                  # dzień roboczy bez wiersza (nieudane pobranie)
        now = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)
        with mock.patch.object(zd, '_now_utc', return_value=now):
            self.assertEqual({r['id']: r['st'] for r in zd.build_trendy({'obce': {'tw': tw}})['f']}['tw'], 'gap')
            tw['empty'] = [ds[-3]]                                       # ten sam dzień jako znany dzień bez sesji — nie jest brakiem
            r = {r['id']: r for r in zd.build_trendy({'obce': {'tw': tw}})['f']}['tw']
            self.assertEqual((r['st'], r['n'], r['date']), ('in_dir', 7, '2026-09-18'), '44 sesje = bieżący tydzień + 7 pełnych: tylko kierunek')

    def test_helpers(self):
        self.assertEqual(zd.trend_streak([1, -2, 3, 4, 5]), (3, 1))
        self.assertEqual(zd.trend_streak([1, None, -3, -4]), (2, -1))
        self.assertEqual(zd.trend_streak([2, 0]), (0, 0), 'zero przerywa serię')
        self.assertIsNone(zd.trend_day_z([1.0] * 30 + [5.0]), 'za mało sesji do porównania dnia')
        v = [(-1) ** i * 10.0 for i in range(60)] + [60.0]
        self.assertAlmostEqual(zd.trend_day_z(v), 60 / zd._sd(v[:-1]), places=6)
        self.assertEqual(zd.wilson(22, 53), (29.3, 54.9), '22 z 53 — policzone też ręcznie')
        self.assertEqual(str(zd.wilson(0, 10)[0]), '0.0', 'bez „-0.0”')
        self.assertEqual(zd.wilson(0, 0), (None, None))
        lo, hi = zd.wilson(195, 418, n_eff=50)
        self.assertTrue(lo < 40 and hi > 55, 'powiązane rynki: przedział liczony na tygodnie, szerszy')
        ds = self.weekdays('2026-09-11', 60)                            # 12 pełnych tygodni kalendarzowych
        v = [20.0 if (i // 5) % 2 == 0 else -20.0 for i in range(60)]  # tydzień na plus, tydzień na minus, …
        k, n, a, b = zd.trend_persist(ds, v, datetime.date(2026, 9, 25))
        self.assertEqual((k, n), (0, 7), 'kierunek zawsze się odwracał; pierwsze 4 tygodnie tylko do porównania')
        self.assertEqual((a, b), ('2026-07-20', '2026-09-07'))
        k2, n2, _, _ = zd.trend_persist(ds, v, datetime.date(2026, 9, 9))
        self.assertEqual(n2, 6, 'tydzień bieżący (niezakończony) nie jest liczony')
        ds, v = zd._tr_weeks(['2026-09-04', '2026-09-18'], [1, 3], n=3)
        self.assertEqual((ds, v), (['2026-09-04', '2026-09-11', '2026-09-18'], [1, None, 3]), 'brakujący tydzień = brak, nie sklejenie')
        ds, v = zd._tr_weeks(['2026-09-01', '2026-09-08', '2026-09-14'], [1, 2, 3], n=3)
        self.assertEqual((ds, v), (['2026-09-01', '2026-09-08', '2026-09-14'], [1, 2, 3]), 'raport w poniedziałek po święcie — ten sam tydzień')
        self.assertEqual(zd._bdays(datetime.date(2026, 9, 18), datetime.date(2026, 9, 21)), 1, 'piątek → poniedziałek = 1 dzień roboczy')
        self.assertEqual(zd._bdays(datetime.date(2026, 9, 18), datetime.date(2026, 9, 22), {'2026-09-21'}), 1, 'znany dzień bez sesji nie postarza danych')
        self.assertTrue(zd._cftc_roll('2026-09-15')); self.assertFalse(zd._cftc_roll('2026-10-13'))
        self.assertFalse(zd._isnum(float('nan'))); self.assertFalse(zd._isnum(float('inf'))); self.assertFalse(zd._isnum(True))

    def S(self):
        ses = self.weekdays('2026-09-18', 45)
        th = [[d, 10.0, 10.0, 0, 0, 0, 1000000.0, 0.3, 33.0, d] for d in ses[:-5]] + [[d, 100.0, 100.0, 0, 0, 0, 1000000.0, 3.0, 33.0, d] for d in ses[-5:]]
        tw = [[d, -50.0, 0, 0, 0, -1.6, d] for d in ses]
        tw[-3][1] = None
        mx = [[d, 1000.0 + i, 5000.0] for i, d in enumerate(ses)]
        return {'obce': {'th': {'d': th}, 'tw': {'d': tw}}, 'meksyk': {'d': mx, 'fx': [10.0, ses[-1]]}}

    def test_build_rows(self):
        now = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)     # poniedziałek po ostatniej sesji
        with mock.patch.object(zd, '_now_utc', return_value=now):
            out = zd.build_trendy(self.S())
            by = {r['id']: r for r in out['f']}
            th = by['th']
            self.assertEqual((th['st'], th['w'], th['base'], th['n'], th['cur'], th['wu'], th['du']), ('in_up', 500.0, 50.0, 8, 'THB', 15.0, 13.5))
            self.assertEqual((th['ph'], th['s'], th['sg'], th['date'], th['age'], th['x']), (0.05, 45, 1, '2026-09-18', 3, True))
            self.assertEqual(by['tw']['st'], 'gap', 'brak jednej sesji w tygodniu — bez stanu, nie zero')
            self.assertNotIn('w', by['tw']); self.assertFalse(by['tw']['x'])
            mx = by['mx']
            self.assertEqual((mx['m'], mx['cur'], mx['w'], mx['wu'], mx['st'], mx['n']), ('stock', 'MXN', 5.0, 0.5, 'in_dir', 7),
                             'Meksyk: zmiana stanu dzień do dnia (44 zmiany z 45 dni) — 7 tygodni historii, tylko kierunek')
            self.assertEqual([b['id'] for b in out['b']], ['th', 'mx', 'ob']); self.assertEqual(out['rules']['base_max'], 8)
            self.assertEqual(out['b'][0]['from'][:4], '2026')
        with mock.patch.object(zd, '_now_utc', return_value=now + datetime.timedelta(days=4)):   # piątek: 4 dni robocze po danych
            r = {r['id']: r for r in zd.build_trendy(self.S())['f']}['th']
            self.assertEqual((r['st'], r['x']), ('stale', False), 'za stare — bez oceny i bez „wyjątkowo”')
        self.assertEqual(zd.build_trendy({})['f'], [], 'bez plików — pusta lista, nie błąd')
        self.assertEqual(zd.build_trendy(None)['p'], [])
        zd.META['notes'].clear()
        with mock.patch.object(zd, '_now_utc', return_value=now):
            out = zd.build_trendy({'obce': {'th': 'zepsute', 'tw': self.S()['obce']['tw']}})
        self.assertEqual([r['id'] for r in out['f']], ['tw'], 'zepsuta część jednego źródła nie usuwa pozostałych')
        self.assertTrue(any(n.startswith('trendy th:') for n in zd.META['notes']), zd.META['notes'])

    def test_japan_weekly_usd(self):
        weeks = [(datetime.date(2026, 7, 18) + datetime.timedelta(days=7 * i)).isoformat() for i in range(9)]
        mof = [{'from': w, 'to': w, 'liabilities': {'equity_net': 1000.0, 'ltdebt_net': None if i == 3 else 500.0}} for i, w in enumerate(weeks)]
        S = {'instytucje': {'mof': {'d': mof}}, 'kursy': {'m': {'JPY': [['2026-07', 160.0], ['2026-08', 170.0]], 'USD': [['2026-07', 1.0], ['2026-08', 1.0]]}}}
        with mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 20, 10, 0, tzinfo=datetime.timezone.utc)):
            by = {r['id']: r for r in zd.build_trendy(S)['f']}
        eq = by['jp_eq']
        self.assertEqual((eq['w'], eq['cur'], eq['fxm'], eq['n'], eq['date'], eq['st']), (100.0, 'JPY', '2026-08', 8, '2026-09-12', 'in_flat'))
        self.assertEqual(eq['wu'], round(100.0 * 1000 / 170.0, 1), 'mld JPY → mln USD kursem sierpnia (ostatni znany ≤ wrzesień)')
        self.assertEqual(by['jp_bd']['n'], 4, 'brak tygodnia kończy porównanie: bieżący + 4 poprzednie (nie zero)')
        with mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 20, 10, 0, tzinfo=datetime.timezone.utc)):
            self.assertNotIn('wu', {r['id']: r for r in zd.build_trendy({'instytucje': S['instytucje']})['f']}['jp_eq'], 'bez kursów — bez ≈ USD, nie zero')

    def test_cftc_and_stablecoins(self):
        dates = [(datetime.date(2026, 6, 23) + datetime.timedelta(days=7 * i)).isoformat() for i in range(13)]
        dates[-1] = '2026-09-14'                                         # święto we wtorek — raport z poniedziałku
        cf = {'markets': {'usd': {'hist': {'dates': dates, 'lev_funds': [100 * i for i in range(12)] + [2000]}}}}
        now = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)
        dd = [[(datetime.date(2026, 7, 1) + datetime.timedelta(days=i)).isoformat(), 1e9 + 1e6 * i] for i in range(83)]   # do 2026-09-21 (dziś)
        dd[-1][1] = 5e9                                                  # dzisiejszy, niezamknięty punkt — pomijany
        with mock.patch.object(zd, '_now_utc', return_value=now):
            by = {r['id']: r for r in zd.build_trendy({'cftc': cf, 'krypto': {'stabh': {'dd': dd}}})['f']}
        u = by['cf_usd']
        self.assertEqual((u['date'], u['w'], u['n'], u['st'], u['roll'], u['x']), ('2026-09-14', 900, 8, 'in_up', True, False),
                         'poniedziałkowy raport w tym samym tygodniu; tydzień rolowania — bez „wyjątkowo”')
        s = by['stab']
        self.assertEqual((s['date'], s['w'], s['st'], s['sz']), ('2026-09-20', 7.0, 'in_flat', 7), 'stablecoiny: tylko zamknięte dni (bez dzisiejszego)')

    def test_prices_and_crypto(self):
        days = [d for d in (datetime.date(2025, 7, 1) + datetime.timedelta(days=i) for i in range(450)) if d.weekday() < 5 and d <= datetime.date(2026, 9, 18)]
        d = [[x.isoformat(), 100.0 + (8 if (i // 5) % 2 else 0) + i * 0.05] for i, x in enumerate(days)]
        mk = {'cols': ['sym', 'mcap', 'p24h', 'p7d', 'p30d', 'p1y'],
              'rows': [['btc', 2e12, 1, 8.0, 7.0, 50], ['eth', 5e11, 1, -6.0, 8.0, 20], ['sol', 9e10, 1, 1.0, 2.0, 3], ['btc', 1e6, 0, -50.0, -50.0, 0]]}
        with mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)):
            out = zd.build_trendy({'ceny': {'q': {'SPY': {'d': d}, 'EWC': {'d': d[:20]}}}, 'krypto': {'at': '2026-09-25T08:00:00+00:00', 'mk': mk}})
        by = {r['id']: r for r in out['p']}
        self.assertNotIn('EWC', by, 'za krótka historia cen — bez wiersza')
        self.assertIn(by['SPY']['st'], ('up_cont', 'dn_fade', 'up_new', 'flat', 'dn_cont', 'up_fade', 'dn_new'))
        self.assertEqual(by['BTC']['st'], 'up_new', 'BTC: +8% w tygodniu po −0,9% w 23 dniach; pierwszy wiersz BTC, nie podróbka')
        self.assertEqual(by['BTC']['pr'], -0.93)
        self.assertEqual(by['ETH']['st'], 'up_fade', 'ETH: −6% po +14,9% w 23 dniach — w dół po wcześniejszych wzrostach')
        self.assertEqual(by['SOL']['st'], 'flat', 'SOL: +1% < 4,5% — bez wyraźnego ruchu')
        b = out['b'][0]
        self.assertEqual((b['id'], b['kind'], b['n'] > 0, b['weeks'], b['n']), ('px', 'price', True, b['n'], b['n']), 'jeden rynek: tygodni tyle co par')
        self.assertTrue(b['to'] < '2026-09-21', 'bez tygodnia bieżącego')

    def test_main_writes_trendy_from_this_run(self):
        zd.META['errors'].clear(); zd.META['ok'].clear(); saved = {}
        offs = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True)
                for f in ('build_instytucje', 'build_krypto', 'build_tic', 'build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy',
                          'build_kursy', 'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk', 'build_fundusze', 'build_surowce', 'build_energia', 'build_usa_makro', 'build_bilans_usa', 'build_oecd', 'build_rynki')]
        [p.start() for p in offs]
        def fake_save(name, obj):
            saved[name] = obj; zd.SAVED[name] = obj
        try:
            with mock.patch.dict(os.environ, {'SOSOVALUE_KEY': '', 'COINGECKO_KEY': ''}, clear=False), \
                    mock.patch.object(zd, 'save', fake_save), mock.patch.object(zd, 'previous', lambda name: None), \
                    mock.patch.object(zd, 'build_obce', return_value=self.S()['obce']), \
                    mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)):
                zd.SAVED['meksyk'] = {'d': [['2026-01-01', 1.0]] * 3}     # pozostałość po innym przebiegu nie może trafić do TRENDÓW
                zd.main()
        finally:
            [p.stop() for p in offs]
        self.assertIs(zd.META['ok']['trendy'], True)
        ids = [r['id'] for r in saved['trendy']['f']]
        self.assertIn('th', ids); self.assertNotIn('mx', ids, 'SAVED czyszczony na początku przebiegu')
        self.assertLess(list(saved).index('trendy'), list(saved).index('meta'), 'TRENDY przed meta — błąd TRENDÓW widać w meta')

    def test_stabh_keeps_70_days(self):
        j = [{'date': str(1780000000 + i * 86400), 'totalCirculatingUSD': {'peggedUSD': 1e9 + i}} for i in range(100)]
        s = zd.parse_stabh(j)
        self.assertEqual(len(s['dd']), 71); self.assertEqual(s['dd'][-1][1], 1000000099)
        self.assertEqual(s['dd'][-1][0], datetime.datetime.fromtimestamp(1780000000 + 99 * 86400, datetime.timezone.utc).date().isoformat())


class FunduszeV90(unittest.TestCase):
    """v90: fundusze ETF w USA — przepływ = zmiana liczby jednostek × NAV z plików State Street i iShares (bez klucza)."""

    XML = ('<?xml version="1.0"?><ss:Workbook xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
           '<ss:Worksheet ss:Name="Holdings"><ss:Table><ss:Row><ss:Cell><ss:Data ss:Type="String">AT&T</ss:Data></ss:Cell></ss:Row></ss:Table></ss:Worksheet>'
           '<ss:Worksheet ss:Name="Historical"><ss:Table>'
           '<ss:Row><ss:Cell><ss:Data ss:Type="String">As Of</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">NAV per Share</ss:Data></ss:Cell>'
           '<ss:Cell><ss:Data ss:Type="String">Ex-Dividends</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="String">Shares Outstanding</ss:Data></ss:Cell></ss:Row>'
           '{rows}</ss:Table></ss:Worksheet></ss:Workbook>')

    @classmethod
    def xml(cls, rows):
        r = ''.join(f'<ss:Row><ss:Cell><ss:Data ss:Type="String">{d}</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="Number">{n}</ss:Data></ss:Cell>'
                    f'<ss:Cell><ss:Data ss:Type="String">--</ss:Data></ss:Cell><ss:Cell><ss:Data ss:Type="{"Number" if s != "--" else "String"}">{s}</ss:Data></ss:Cell></ss:Row>'
                    for d, n, s in rows)
        return cls.XML.format(rows=r).encode()

    @staticmethod
    def days(n, end='2026-09-24'):
        d, out = datetime.date.fromisoformat(end), []
        while len(out) < n:
            if d.weekday() < 5:
                out.append(d)
            d -= datetime.timedelta(days=1)
        return out[::-1]

    def test_parse_ishares_and_screener(self):
        ds = self.days(25)
        rows = [(d.strftime('%b %d, %Y'), 100.0 + i, 1000000 + 1000 * i) for i, d in enumerate(ds)][::-1] + [('Jan 03, 2000', 50.0, '--')]
        h = zd.parse_ishares_hist(self.xml(rows))
        self.assertEqual(len(h), 25, 'wiersz z „--” pominięty; gołe „&” w innym arkuszu nie psuje pliku')
        self.assertEqual(h[-1], ['2026-09-24', 124.0, 1024000]); self.assertEqual(h[0][0], ds[0].isoformat())
        with self.assertRaises(RuntimeError):
            zd.parse_ishares_hist(self.xml(rows[:5]))
        j = {'239726': {'localExchangeTicker': 'IVV', 'portfolioId': 239726, 'navAmount': {'r': 770.800542}, 'navAmountAsOf': {'r': 20260924},
                        'totalNetAssetsFund': {'r': 882219760864.18}, 'totalNetAssetsFundAsOf': {'r': 20260924}},
             '239623': {'localExchangeTicker': 'EFA', 'navAmount': {'r': 90.0}, 'navAmountAsOf': {'r': 20260924},
                        'totalNetAssetsFund': {'r': 9e9}, 'totalNetAssetsFundAsOf': {'r': 20260923}},
             '1': {'localExchangeTicker': 'XYZ', 'navAmount': {'r': 1.0}, 'navAmountAsOf': {'r': 20260924}, 'totalNetAssetsFund': {'r': 1.0}, 'totalNetAssetsFundAsOf': {'r': 20260924}}}
        s = zd.parse_ishares_screener(j)
        self.assertEqual(s, {'IVV': ('239726', '2026-09-24', 770.800542, 1144550000)}, 'różne daty NAV i aktywów — bez liczby; spoza listy — pominięty; v94: pełne tysiące')

    def test_parse_ssga(self):
        rows = {1: {1: 'Fund Name:', 2: 'SPDR® Gold Shares'}, 2: {1: 'Ticker Symbol:', 2: 'GLD®'}, 4: {1: 'Date', 2: 'NAV', 3: 'Shares Outstanding', 4: 'Total Net Assets'}}
        for i, d in enumerate(self.days(25)[::-1]):
            rows[5 + i] = {1: d.strftime('%d-%b-%Y'), 2: str(390.0 - i), 3: f'{3.697E8 - i * 1e5:E}', 4: '1'}
        rows[40] = {1: 'The whole or any part of this work may not be reproduced'}
        with mock.patch.object(zd, '_xlsx_rows', return_value=rows):
            h = zd.parse_ssga_navhist(b'x', 'GLD')
            self.assertEqual((len(h), h[-1]), (25, ['2026-09-24', 390.0, 369700000]))
            with self.assertRaises(RuntimeError):
                zd.parse_ssga_navhist(b'x', 'SPY')           # inny symbol w pliku — błąd, nie cudze liczby

    def test_flows_and_groups(self):
        h = [['2026-09-21', 100.0, 1000], ['2026-09-22', 101.0, 1100], ['2026-09-23', 50.0, 2200], ['2026-09-24', 50.0, 2150]]
        self.assertEqual(zd.fund_flows(h), {'2026-09-22': 100 * 101 / 1e6, '2026-09-23': 0.0, '2026-09-24': -50 * 50 / 1e6}, 'podział 2:1 — przepływ dnia liczony po podziale (v93)')
        self.assertEqual(zd.fund_flows([['2026-09-21', 100.0, 1000], ['2026-09-22', 50.0, 1000]]), {}, 'skok NAV bez podziału — dzień pominięty')
        fu = {'SPY': {'h': [['2026-09-22', 10.0, 100], ['2026-09-23', 10.0, 110], ['2026-09-24', 10.0, 130]]},
              'IVV': {'h': [['2026-09-22', 20.0, 50], ['2026-09-23', 20.0, 60]]}}
        ds, v, aum = zd.fund_group(fu, ('SPY', 'IVV'))
        self.assertEqual((ds, aum), (['2026-09-23'], (10.0 * 130 + 20.0 * 60) / 1e6), 'do ostatniego wspólnego dnia')
        self.assertAlmostEqual(v[0], 300 / 1e6)
        fu['IVV']['h'] = [['2026-09-21', 20.0, 40], ['2026-09-23', 20.0, 60]]
        ds, v, _ = zd.fund_group(fu, ('SPY', 'IVV'))
        self.assertEqual(ds, ['2026-09-23']); self.assertAlmostEqual(v[0], 100 / 1e6 + 400 / 1e6, msg='zmiana przez dwa dni przypisana do dnia publikacji')
        self.assertEqual(zd.fund_group(fu, ('SPY', 'EEM')), ([], [], None), 'brak funduszu w grupie — brak grupy, nie część')

    def test_build_fundusze(self):
        zd.META['errors'].clear(); zd.META['notes'].clear()
        ds = self.days(260)
        hist = self.xml([(d.strftime('%b %d, %Y'), 50.0, 1000000 + 100 * i) for i, d in enumerate(ds)][::-1])
        scr = {str(i): {'localExchangeTicker': t, 'portfolioId': str(i), 'navAmount': {'r': 50.0}, 'navAmountAsOf': {'r': 20260925},
                        'totalNetAssetsFund': {'r': 50.0 * 2000000}, 'totalNetAssetsFundAsOf': {'r': 20260925}} for i, t in enumerate(zd.FUND_ISH)}
        calls = []
        def fake(url, timeout=60, headers=None):
            calls.append(url)
            if 'ssga.com' in url:
                raise urllib.error.HTTPError(url, 403, 'Forbidden', None, None)
            if 'product-screener' in url:
                return json.dumps(scr).encode()
            return hist
        now = datetime.datetime(2026, 9, 25, 22, 0, tzinfo=datetime.timezone.utc)
        with mock.patch.object(zd, 'get_bytes', side_effect=fake), mock.patch.object(zd, '_now_utc', return_value=now), \
                mock.patch.object(zd, 'FUND_SLEEP', 0), mock.patch.object(zd.time, 'sleep'):
            out = zd.build_fundusze(None)
        self.assertEqual(sum('get-fund-document' in u for u in calls), 3, 'najwyżej 3 pełne historie na przebieg')
        full = [t for t, f in out['f'].items() if len(f.get('h') or []) > 1]
        self.assertEqual(len(full), 3); self.assertEqual(out['f'][full[0]]['h'][-1], ['2026-09-25', 50.0, 2000000], 'dzień z zestawienia dopisany')
        self.assertEqual(sum(1 for f in out['f'].values() if f.get('h')), 22, 'pozostałe fundusze iShares — jeden dzień z zestawienia (bez przepływu), do uzupełnienia w kolejnych przebiegach')
        self.assertTrue(any(e.startswith('fundusze ETF: 15 problemów') for e in zd.META['errors']), 'State Street niedostępny — błąd w meta')
        prev = out; prev['f']['SPY'] = {'iss': 'ssga', 'at': (now - datetime.timedelta(hours=1)).isoformat(), 'h': [['2026-09-24', 1.0, 1]]}
        calls.clear()
        with mock.patch.object(zd, 'get_bytes', side_effect=fake), mock.patch.object(zd, '_now_utc', return_value=now), \
                mock.patch.object(zd, 'FUND_SLEEP', 0), mock.patch.object(zd.time, 'sleep'):
            out2 = zd.build_fundusze(prev)
        self.assertFalse(any('spy.xlsx' in u for u in calls), 'plik State Street młodszy niż 6 h — bez pobierania')
        self.assertEqual(sum('get-fund-document' in u for u in calls), 3, 'kolejne 3 fundusze uzupełniane')
        with mock.patch.object(zd, 'get_bytes', side_effect=RuntimeError('offline')), mock.patch.object(zd, '_now_utc', return_value=now), \
                mock.patch.object(zd, 'FUND_SLEEP', 0), mock.patch.object(zd.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                zd.build_fundusze(None)

    def test_trendy_uses_funds(self):
        ds = self.days(60, '2026-09-18')
        fu = {t: {'h': [[d.isoformat(), 100.0, 1000000 + (5000 if i >= 55 else 1000) * i] for i, d in enumerate(ds)]} for t in ('SPY', 'IVV')}
        with mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)):
            out = zd.build_trendy({'fundusze': {'f': fu}})
        r = {x['id']: x for x in out['f']}['fe_us']
        self.assertEqual((r['g'], r['m'], r['cur'], r['n'], r['date']), ('fe', 'flow', 'USD', 8, '2026-09-18'))
        self.assertIn(r['st'], ('in_up', 'in_rev', 'in_new'), 'większy napływ w ostatnim tygodniu')
        self.assertTrue(r['ph'] > 0 and r['du'] > 0)
        self.assertEqual([b['id'] for b in out['b']], ['fe'])


class ObceV91(unittest.TestCase):
    """v91: Indie, Tajwan, Hongkong co godzinę; Brazylia, Turcja, ThaiBMA najwyżej co 3 h (bez zapytania, gdy część świeża i bez błędu)."""

    def test_slow_parts_reused(self):
        called = []
        mk = lambda name: (lambda *a, **k: called.append(name) or {'at': zd.NOW, 'd': [['2026-09-24', 1.0]]})
        prev = {'ok': {'in': True, 'tw': True, 'hk': True, 'br': True, 'tr': False, 'th': True},
                'br': {'at': _iso(30), 'd': [['2026-09-18', 2.0]]}, 'tr': {'at': _iso(30), 'd': []}, 'th': {'at': _iso(200), 'd': []}}
        with mock.patch.object(zd, 'nsdl_part', mk('in')), mock.patch.object(zd, 'twse_part', mk('tw')), mock.patch.object(zd, 'hkex_part', mk('hk')), \
                mock.patch.object(zd, 'bcb_part', mk('br')), mock.patch.object(zd, 'tcmb_part', mk('tr')), mock.patch.object(zd, 'thbma_part', mk('th')):
            out = zd.build_obce('', prev)
        self.assertEqual(called, ['in', 'tw', 'hk', 'tr', 'th'], 'Brazylia świeża (30 min) — z pamięci; Turcja z błędem i ThaiBMA sprzed 200 min — pobrane')
        self.assertIs(out['br'], prev['br']); self.assertIs(out['ok']['br'], True); self.assertEqual(zd.META['ok']['obce_br'], 'cached')


class SurowceV92(unittest.TestCase):
    """v92: CFTC disaggregated — złoto, srebro, miedź, ropa WTI; pozycje grup muszą sumować się do open interest."""

    @staticmethod
    def row(code, day, oi, mm=(100, 20, 10), bad=False):
        vals = {'Market_and_Exchange_Names': 'GOLD - COMMODITY EXCHANGE INC.', 'As_of_Date_In_Form_YYMMDD': day[2:].replace('-', ''),
                'Report_Date_as_YYYY-MM-DD': day, 'CFTC_Contract_Market_Code': code, 'CFTC_Market_Code': 'CMX', 'CFTC_Region_Code': '0',
                'CFTC_Commodity_Code': '88', 'Open_Interest_All': oi}
        L = {'Prod_Merc_Positions_Long_All': 50, 'Prod_Merc_Positions_Short_All': 150, 'Swap_Positions_Long_All': 30, 'Swap__Positions_Short_All': 20,
             'Swap__Positions_Spread_All': 5, 'M_Money_Positions_Long_All': mm[0], 'M_Money_Positions_Short_All': mm[1], 'M_Money_Positions_Spread_All': mm[2],
             'Other_Rept_Positions_Long_All': 10, 'Other_Rept_Positions_Short_All': 10, 'Other_Rept_Positions_Spread_All': 0,
             'NonRept_Positions_Long_All': 0, 'NonRept_Positions_Short_All': 0, 'Tot_Rept_Positions_Long_All': 0, 'Tot_Rept_Positions_Short_All': 0}
        vals.update(L)
        # NonRept dobrane tak, by obie strony (long + spread, short + spread) dały open interest; bad=True psuje sumę shortów
        vals['NonRept_Positions_Long_All'] = oi - (50 + 30 + 5 + mm[0] + mm[2] + 10)
        vals['NonRept_Positions_Short_All'] = oi - (150 + 20 + 5 + mm[1] + mm[2] + 10) + (7 if bad else 0)
        return [str(vals[c]) for c in zd.CFTCD_COLS] + ['x'] * 168

    def text(self, rows, header=True):
        import csv as _csv, io
        buf = io.StringIO(); w = _csv.writer(buf)
        if header:
            w.writerow(list(zd.CFTCD_COLS) + ['Extra'] * 168)
        for r in rows:
            w.writerow(r)
        return buf.getvalue()

    def test_parse_and_build(self):
        import io, zipfile
        days = [(datetime.date(2026, 6, 16) + datetime.timedelta(days=7 * i)).isoformat() for i in range(14)]
        year = [self.row('088691', d, 1000, mm=(100 + 10 * i, 20, 10)) for i, d in enumerate(days[:-1])] + [self.row('999999', days[0], 5)]
        year.append(self.row('088691', days[3], 1000, bad=True))            # zła suma — wiersz pominięty; poprawny wiersz z tego dnia zostaje
        week = [self.row('088691', days[-1], 1000, mm=(300, 20, 10))]
        p, bad = zd.parse_cftcd(self.text(year))
        self.assertEqual(sorted(p), ['088691'], 'tylko rynki z listy'); self.assertEqual(bad, ['088691 ' + days[3]])
        self.assertEqual(p['088691'][days[0]]['g']['mm'], {'long': 100, 'short': 20, 'spread': 10, 'net': 80})
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as z:
            z.writestr('f_year.txt', self.text(year))
        files = {zd.CFTCD_YEAR_URL.format(2026): buf.getvalue(), zd.CFTCD_WEEK_URL: self.text(week, header=False).encode()}
        zd.META['notes'].clear(); zd.META['errors'].clear()
        out = zd.build_surowce(fetch=lambda u: files[u] if u in files else (_ for _ in ()).throw(RuntimeError('404')), today=datetime.date(2026, 9, 25))
        g = out['markets']['gold']
        self.assertEqual((g['asof'], g['groups']['mm']['net'], len(g['hist']['dates']), g['hist']['mm'][-2:]), (days[-1], 280, 13, [200, 280]),
                         'tydzień z pliku tygodniowego; 13 raportów z okna 90 dni')
        self.assertTrue(any('pozycje ≠ open interest' in n for n in zd.META['notes']))
        self.assertTrue(any('brak rynku silver' in e for e in zd.META['errors']), 'brak rynku — błąd, nie zero')
        with mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 25, 12, 0, tzinfo=datetime.timezone.utc)):
            r = {x['id']: x for x in zd.build_trendy({'surowce': out})['f']}['cs_gold']
        self.assertEqual((r['g'], r['m'], r['cur'], r['w'], r['date']), ('pos', 'pos', 'CT', 80, days[-1]))


class CenyFunduszyV93(unittest.TestCase):
    """v93: TRENDY — tydzień ceny jednostki (NAV) największego funduszu w grupie: obligacje, metale, sektory, regiony spoza listy cen krajów."""

    def test_nav_rows(self):
        days = [d for d in (datetime.date(2025, 9, 1) + datetime.timedelta(days=i) for i in range(390)) if d.weekday() < 5][-280:]
        mk = lambda nav0, sh, step: [[d.isoformat(), nav0 + step * i, sh] for i, d in enumerate(days)]
        fu = {'GLD': {'h': mk(300.0, 400, 0.1)}, 'IAU': {'h': mk(60.0, 700, 0.02)}, 'GLDM': {'h': mk(70.0, 10, 0.02)},
              'TLT': {'h': mk(90.0, 500, -0.01)}, 'XLK': {'h': mk(200.0, 600, 0.01)}}
        fu['XLK']['h'][-3][1] = 100.0                                   # skok NAV o połowę — podział jednostek, bez wiersza
        with mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 25, 10, 0, tzinfo=datetime.timezone.utc)):
            zd.META['notes'].clear()
            out = zd.build_trendy({'fundusze': {'f': fu}})
        by = {r['id']: r for r in out['p']}
        self.assertEqual((by['fp_gold']['sym'], by['fp_gold']['g']), ('GLD', 'fp'), 'największy fundusz grupy (300 × 400 > 60 × 700)')
        self.assertNotIn('fp_ustl', by, 'v94: bez obligacji — wypłata odsetek obniża NAV'); self.assertNotIn('fp_tech', by); self.assertNotIn('fp_us', by, 'akcje USA są już na liście cen krajów (SPY)')
        self.assertTrue(any(n.startswith('trendy XLK: skok NAV bez podziału') for n in zd.META['notes']))
        fu2 = {'XLE': {'h': [[d.isoformat(), (90.0 if i < 200 else 45.0) + 0.01 * i, 300 if i < 200 else 600] for i, d in enumerate(days)]}}
        with mock.patch.object(zd, '_now_utc', return_value=datetime.datetime(2026, 9, 25, 10, 0, tzinfo=datetime.timezone.utc)):
            r = {x['id']: x for x in zd.build_trendy({'fundusze': {'f': fu2}})['p']}['fp_energy']
        self.assertTrue(abs(r['pr']) < 5 and abs(r['w']) < 5, 'podział 2:1 nie jest spadkiem ceny o połowę')
        self.assertEqual(zd.fund_split([0, 90.0, 300], [0, 45.0, 600]), 2); self.assertEqual(zd.fund_split([0, 45.0, 600], [0, 90.0, 300]), 0.5)
        self.assertEqual(by['fp_gold']['date'], days[-1].isoformat())
        self.assertEqual([b['id'] for b in out['b'] if b['id'] == 'px'], [], 'ceny funduszy nie wchodzą do „14 rynków akcji”')


class FunduszeV94(unittest.TestCase):
    """v94 (po drugim przeglądzie): zaokrąglenie liczby jednostek z zestawienia, luka w sesjach naprawiana pełnym plikiem, dni innego
    kalendarza w grupie, podziały 3:2, dni bez zmian w regule większości, krótka historia surowców, zły format daty CFTC."""

    def test_screener_rounding_and_rows(self):
        j = {'1': {'localExchangeTicker': 'EFA', 'portfolioId': '1', 'navAmount': {'r': 90.0}, 'navAmountAsOf': {'r': 20260924},
                   'totalNetAssetsFund': {'r': 90.0 * 739199996.8}, 'totalNetAssetsFundAsOf': {'r': 20260924}}}
        self.assertEqual(zd.parse_ishares_screener(j)['EFA'][3], 739200000, 'kilka jednostek różnicy z zaokrąglenia NAV — liczba z pełnymi tysiącami')
        h = [['2026-09-04', 10.0, 100], ['2026-09-07', 10.0, 100], ['2026-09-08', 11.0, 110]]
        self.assertEqual(zd._fund_rows(h), [h[0], h[2]], 'powtórzony wiersz (dzień wolny w USA w pliku złota) pominięty')

    def test_splits_and_clear(self):
        self.assertEqual(zd.fund_split([0, 30.0, 300], [0, 20.0, 450]), 1.5, 'podział 3:2')
        self.assertEqual(zd.fund_split([0, 20.0, 450], [0, 30.0, 300]), 1 / 1.5, 'scalenie 2:3')
        self.assertEqual(zd.fund_split([0, 30.0, 300], [0, 30.0, 3000]), 0, 'liczba ×10 przy tym samym NAV — błąd pliku, dzień pominięty')
        self.assertEqual(zd.fund_split([0, 30.0, 300], [0, 30.3, 360]), 1, 'duży, ale zwykły napływ (+20%)')
        self.assertTrue(zd._tr_clear(300, 400, [300, 0, 0, 0, 0]), 'jeden dzień tworzenia jednostek i dni bez zmian — wyraźny kierunek')
        self.assertFalse(zd._tr_clear(300, 400, [500, -50, -50, -50, -50]), 'dni ze zmianą w różne strony — bez wyraźnego kierunku')
        W = zd._iso_weeks(['2026-08-07', '2026-08-10', '2026-08-11', '2026-08-12', '2026-08-13', '2026-08-14'], [1, 1, 1, 1, 1, 1], datetime.date(2026, 9, 1))
        self.assertEqual([w[0].isoformat() for w in W], ['2026-08-10'], 'niepełny pierwszy tydzień historii (1 dzień) pominięty')

    def test_group_other_calendar(self):
        mk = lambda rows: {'h': rows}
        fu = {'GLD': mk([['2026-09-03', 10.0, 100], ['2026-09-04', 10.0, 110], ['2026-09-07', 10.1, 110], ['2026-09-08', 10.0, 130]]),
              'IAU': mk([['2026-09-03', 5.0, 100], ['2026-09-04', 5.0, 90], ['2026-09-08', 5.0, 120]])}
        ds, v, _ = zd.fund_group(fu, ('GLD', 'IAU'))
        self.assertEqual(ds, ['2026-09-04', '2026-09-08'], 'dzień tylko w jednym pliku nie robi luki w grupie')
        self.assertAlmostEqual(v[1], ((130 - 110) * 10.0 + (120 - 90) * 5.0) / 1e6, msg='suma przez dzień wolny — dokładna')

    def test_gap_repaired_by_backfill(self):
        now = datetime.datetime(2026, 9, 25, 12, 0, tzinfo=datetime.timezone.utc)
        spy = [[d, 700.0 + i, 1000000 + i] for i, d in enumerate(['2026-09-21', '2026-09-22', '2026-09-23', '2026-09-24'])]
        prev = {'scr_at': None, 'f': {t: {'iss': 'ssga', 'at': (now - datetime.timedelta(hours=1)).isoformat(), 'h': spy} for t in zd.FUND_SSGA}}
        hist = [['2026-09-%02d' % d, 50.0, 1000000] for d in (14, 15, 16, 17, 18, 21, 22)]
        prev['f']['EFA'] = {'iss': 'ishares', 'pid': '1', 'bf_done': True, 'h': hist}
        scr = {'1': {'localExchangeTicker': 'EFA', 'portfolioId': '1', 'navAmount': {'r': 50.0}, 'navAmountAsOf': {'r': 20260924},
                     'totalNetAssetsFund': {'r': 50.0 * 1200000}, 'totalNetAssetsFundAsOf': {'r': 20260924}}}
        doc = FunduszeV90.xml([(datetime.date(2026, 9, d).strftime('%b %d, %Y'), 50.0, 1000000 + 50000 * (d - 21)) for d in (24, 23, 22, 21, 18, 17, 16, 15, 14, 11, 10, 9, 8, 4, 3, 2, 1)
                               ] + [(datetime.date(2026, 8, d).strftime('%b %d, %Y'), 50.0, 1000000) for d in (31, 28, 27, 26, 25)])
        for fail in (False, True):
            calls = []
            def fake(url, timeout=60, headers=None):
                calls.append(url)
                if 'product-screener' in url:
                    return json.dumps(scr).encode()
                if fail:
                    raise RuntimeError('503')
                return doc
            zd.META['notes'].clear(); zd.META['errors'].clear()
            with mock.patch.object(zd, 'get_bytes', side_effect=fake), mock.patch.object(zd, '_now_utc', return_value=now), \
                    mock.patch.object(zd, 'FUND_SLEEP', 0), mock.patch.object(zd.time, 'sleep'):
                out = zd.build_fundusze(prev)
            e = out['f']['EFA']
            self.assertEqual(sum('get-fund-document' in u for u in calls), 1, 'luka 22.09 → 24.09 (brak 23.09) — pobranie pełnego pliku')
            if fail:
                self.assertEqual(e['h'][-1][0], '2026-09-22', 'bez pełnego pliku dzień z zestawienia nie jest dopisywany nad luką')
                self.assertTrue(e.get('bf_need') and e.get('bf_err_at'))
            else:
                self.assertEqual([r[0] for r in e['h'][-3:]], ['2026-09-22', '2026-09-23', '2026-09-24'])
                self.assertNotIn('bf_need', e)

    def test_surowce_short_history_and_bad_date(self):
        rows = SurowceV92.row('088691', '2026-09-15', 1000)
        rows[zd.CFTCD_COLS.index('Report_Date_as_YYYY-MM-DD')] = '09/15/2026'
        p, bad = zd.parse_cftcd(SurowceV92().text([rows]))
        self.assertEqual((p, bad), ({}, ['088691 09/15/2026 (data)']), 'nieznany format daty — wiersz pominięty, nie wyjątek')
        week = SurowceV92().text([SurowceV92.row('088691', '2026-09-15', 1000)], header=False).encode()
        prev = {'markets': {'gold': {'hist': {'dates': ['2026-06-%02d' % d for d in range(1, 14)]}}}}
        def fetch(u):
            if u == zd.CFTCD_WEEK_URL:
                return week
            raise RuntimeError('timeout')
        zd.META['errors'].clear()
        with self.assertRaises(RuntimeError):
            zd.build_surowce(fetch=fetch, today=datetime.date(2026, 9, 25), prev=prev)   # bez pliku rocznego: 1 raport zamiast 13 — zostaje poprzedni plik
        self.assertTrue(any('rok 2026' in e for e in zd.META['errors']))


def _wdays(a, b):
    d0, d1 = datetime.date.fromisoformat(a), datetime.date.fromisoformat(b)
    return [(d0 + datetime.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1) if (d0 + datetime.timedelta(days=i)).weekday() < 5]


class HistoriaV95(unittest.TestCase):
    """v95–v95.2: historia wstecz — Indie z archiwum NSDL (miesiąc przyjęty tylko, gdy suma dni = suma miesiąca; nieudany miesiąc nie blokuje
    starszych), Tajwan i Hongkong do 26 tygodni (twarde limity czasu, bez stałej granicy po jednym braku pliku, święto TWSE wstecz po dwóch
    odpowiedziach), Brazylia ponad rok; „czy tydzień zapowiadał następny” także dla dziennych przepływów krajów."""
    FORM = ('<form><input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="a&amp;b" />'
            '<input type="hidden" name="__VIEWSTATEGENERATOR" id="__VIEWSTATEGENERATOR" value="G" />'
            '<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="E" /></form>')
    T0 = datetime.datetime(2026, 9, 25, 9, 0, tzinfo=datetime.timezone.utc)

    @staticmethod
    def arch(days, month_total, month='August'):
        """Strona archiwum NSDL: dni (data, akcje, razem), potem bloki „Total for <miesiąc>” i „Total for 2026” (jak na prawdziwej stronie)."""
        h = '<html><body><table>'
        for d, eq, tot in days:
            h += (f'<tr><td rowspan="3">{d}</td><td>Equity</td><td>Stock Exchange</td><td>1</td><td>1</td><td>1</td><td>{eq}</td><td>Rs.95.5614</td></tr>'
                  f'<tr><td>Sub-total</td><td>1</td><td>1</td><td>1</td><td>{eq}</td></tr>'
                  f'<tr><td>Total</td><td>1</td><td>1</td><td>1</td><td>{tot}</td></tr>')
        return h + (f'<tr><td rowspan="3">Total for {month}</td><td>Equity</td><td>Stock Exchange</td><td>1</td><td>1</td><td>1</td><td>999.00</td><td>&nbsp;</td></tr>'
                    '<tr><td>Sub-total</td><td>1</td><td>1</td><td>1</td><td>999.00</td></tr>'
                    '<tr><td>Debt-General Limit</td><td>Stock Exchange</td><td>1</td><td>1</td><td>1</td><td>500.00</td></tr>'
                    '<tr><td>Sub-total</td><td>1</td><td>1</td><td>1</td><td>500.00</td></tr>'
                    f'<tr><td>Total</td><td>1</td><td>1</td><td>1</td><td>{month_total}</td></tr>'
                    '<tr><td>Total for 2026</td><td>Equity</td><td>Stock Exchange</td><td>1</td><td>1</td><td>1</td><td>5000.00</td></tr>'
                    '<tr><td>Total</td><td>1</td><td>1</td><td>1</td><td>7,777.00</td></tr>'
                    '<tr><td>Reporting Date</td><td>Derivative Products</td></tr></table></body></html>')

    def setUp(self):
        zd.META['errors'].clear(); zd.META['notes'].clear(); zd.META['ok'].clear(); zd._RUN_T0[0] = None; zd._BACK_LATE_NOTE[0] = False

    def at(self, now):
        """Wspólne atrapy czasu: data dnia stała (25.09, 17:00 w Tajpej), NOW przebiegu — podany."""
        return (mock.patch.object(zd.time, 'sleep', lambda s: None), mock.patch.object(zd, 'NOW', now),
                mock.patch.object(zd, '_now_utc', lambda: self.T0))

    def test_archive_month_and_year_totals_do_not_leak_into_last_day(self):
        tot = {}
        rows = zd.parse_nsdl_html(self.arch([('28-Aug-2026', '10.00', '12.00'), ('31-Aug-2026', '(134.81)', '(139.40)')], '(127.40)'), tot)
        self.assertEqual([r[0] for r in rows], ['2026-08-28', '2026-08-31'])
        self.assertEqual(rows[-1][1:5], [-134.81, None, None, -139.4], 'suma miesiąca nie jest dopisana do 31 sierpnia')
        self.assertEqual(tot, {'august': -127.4, '2026': 7777.0})

    def test_month_arithmetic(self):
        self.assertEqual((zd._ym_add('2026-01', -1), zd._ym_add('2026-09', -12), zd._ym_add('2025-12', 1)), ('2025-12', '2025-09', '2026-01'))

    def test_nsdl_http_sends_session_cookies_with_the_form(self):
        seen = []

        class R:
            def __init__(self, body, ck):
                self.body, self.headers = body, mock.Mock(get_all=lambda n: ck)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return self.body

        def uo(req, timeout=30):
            seen.append((req.get_method(), dict(req.header_items()), req.data, timeout))
            return R(b'formularz', ['ASP.NET_SessionId=abc; path=/; HttpOnly', 'NL01ba3203=xyz; Path=/']) if req.data is None else R(b'wynik', None)
        with mock.patch.object(zd.urllib.request, 'urlopen', uo):
            b1, ck = zd.nsdl_http(zd.NSDL_ARCH, timeout=15)
            b2, ck2 = zd.nsdl_http(zd.NSDL_ARCH, {'hdnDate': '31-Aug-2026', 'x': 'a b'}, ck, timeout=30)
        self.assertEqual((b1, ck, b2, ck2), (b'formularz', 'ASP.NET_SessionId=abc; NL01ba3203=xyz', b'wynik', 'ASP.NET_SessionId=abc; NL01ba3203=xyz'))
        m, h, data, to = seen[1]
        self.assertEqual((m, h.get('Cookie'), h.get('Content-type'), data, to),
                         ('POST', 'ASP.NET_SessionId=abc; NL01ba3203=xyz', 'application/x-www-form-urlencoded', b'hdnDate=31-Aug-2026&x=a+b', 30))
        self.assertEqual((seen[0][0], seen[0][3]), ('GET', 15))

    def test_nsdl_month_posts_last_day_and_checks_month_total(self):
        sent = []

        def http(url, form=None, cookie='', timeout=30):
            if form is None:
                return self.FORM.encode(), 'S=1'
            sent.append((dict(form), cookie, timeout))
            return self.arch([('03-Aug-2026', '1.00', '2.00'), ('31-Aug-2026', '3.00', '4.00'), ('01-Sep-2026', '5.00', '6.00')], '6.00').encode(), cookie
        with mock.patch.object(zd, 'nsdl_http', http):
            rows = zd.nsdl_month('2026-08')
            self.assertRaises(RuntimeError, zd.nsdl_month, '2025-12')      # w odpowiedzi nie ma dni grudnia
        self.assertEqual([r[0] for r in rows], ['2026-08-03', '2026-08-31'], 'tylko dni tego miesiąca')
        f, ck, to = sent[0]
        self.assertEqual((f['hdnDate'], f['__EVENTTARGET'], f['__VIEWSTATE'], f['__EVENTVALIDATION'], ck, to), ('31-Aug-2026', 'btnSubmit1', 'a&b', 'E', 'S=1', 30))
        self.assertEqual(sent[1][0]['hdnDate'], '31-Dec-2025')
        bad = lambda url, form=None, cookie='', timeout=30: (self.FORM.encode(), '') if form is None else (self.arch([('03-Aug-2026', '1.00', '2.00')], '9.00').encode(), '')
        with mock.patch.object(zd, 'nsdl_http', bad):
            with self.assertRaisesRegex(RuntimeError, 'suma dni'):
                zd.nsdl_month('2026-08')          # suma dni 2 ≠ suma miesiąca 9 — miesiąc odrzucony
        with mock.patch.object(zd, 'nsdl_http', lambda url, form=None, cookie='', timeout=30: (b'<html>nowy formularz</html>', '')):
            with self.assertRaisesRegex(RuntimeError, 'formularza'):
                zd.nsdl_month('2026-08')

    def test_nsdl_part_failed_month_does_not_block_older_ones(self):
        asked = []

        def month(ym):
            asked.append(ym)
            if ym == '2026-07':
                raise RuntimeError('suma dni ≠ suma miesiąca')
            return [[ym + '-15', 1.0, 2.0, 0.0, 3.0, 95.0]]
        prev = {'arch': ['2026-08', '1999-01'], 'd': [['2026-06-15', 9.0, 9.0, 9.0, 9.0, 90.0], ['2026-09-01', 1.0, 1.0, 1.0, 1.0, 95.0]]}
        page = mock.patch.object(zd, 'get_bytes', lambda url, headers=None, timeout=60: ObceV54.NSDL.encode())
        with page, mock.patch.object(zd, 'nsdl_month', month), mock.patch.object(zd, 'NOW', '2026-09-25T09:00:00+00:00'):
            out = zd.nsdl_part(prev)
            self.assertEqual(asked, ['2026-07', '2026-06', '2026-05'], 'nieudany miesiąc nie zatrzymuje starszych; najwyżej 3 próby')
            self.assertEqual(out['arch'], ['2026-05', '2026-06', '2026-08'], 'spoza 12 miesięcy — usunięty')
            self.assertEqual(out['afail'], {'2026-07': '2026-09-25T09:00:00+00:00'})
            m = {r[0]: r for r in out['d']}
            self.assertEqual(m['2026-06-15'][1], 1.0, 'archiwum zastępuje dzień zebrany wcześniej')
            self.assertTrue({'2026-09-01', '2026-09-23', '2026-09-24'} <= set(m))
            self.assertTrue(any(n.startswith('NSDL archiwum 2026-07') and 'jutro' in n for n in zd.META['notes']))
            self.assertFalse(zd.META['errors'], 'brak starszego miesiąca to notatka, nie błąd bieżących danych')
            asked.clear(); out2 = zd.nsdl_part(out)
            self.assertEqual(asked, ['2026-04', '2026-03', '2026-02'], 'miesiąc odrzucony dziś czeka do jutra')

            def down(ym):
                asked.append(ym); raise zd.urllib.error.URLError('timed out')
            asked.clear()
            with mock.patch.object(zd, 'nsdl_month', down):
                out3 = zd.nsdl_part(out2)
            self.assertEqual(asked, ['2026-01'], 'awaria sieci — przerwa do następnego przebiegu')
            self.assertNotIn('2026-01', out3.get('afail', {}))
        with page, mock.patch.object(zd, 'nsdl_month', month), mock.patch.object(zd, 'NOW', '2026-09-26T09:00:00+00:00'):
            asked.clear(); zd.nsdl_part(out)
        self.assertEqual(asked[0], '2026-07', 'następnego dnia — ponowna próba')

    def test_tw_back_newest_first_skips_known(self):
        now = datetime.datetime(2026, 9, 25, 17, 0)
        self.assertEqual(zd.tw_back({'2026-09-24'}, {'2026-09-23'}, now, skip={'2026-09-22', '2026-09-17'})[:4],
                         ['2026-09-21', '2026-09-18', '2026-09-16', '2026-09-15'])
        b = zd.tw_back(set(), set(), now)
        self.assertEqual(b, sorted(b, reverse=True)); self.assertEqual(b[-1], '2026-03-27', '182 dni wstecz')

    def test_twse_backfill_holiday_needs_two_answers_12h_apart(self):
        prev = {'d': [[d, 1.0, 0, 0, 0] for d in _wdays('2026-09-11', '2026-09-23')], 'empty': []}
        asked, tos = [], []

        def gj(url, headers=None, timeout=30):
            if 'DEXTAUS' in url:
                self.assertIn('limit=200', url)
                return {'observations': [{'date': '2026-07-01', 'value': '31.0'}]}
            day = url.split('dayDate=')[1][:8]; iso = f'{day[:4]}-{day[4:6]}-{day[6:]}'; asked.append(iso); tos.append(timeout)
            if iso == '2026-09-24':
                return {'stat': 'Busy'}                          # ostatni dzień: dziwna odpowiedź = błąd, nie święto
            if iso == '2026-09-10':
                return {'stat': 'OK', 'date': '20260910', 'data': []}   # starszy dzień bez danych — nie święto
            if iso == '2026-09-09':
                return {'stat': 'No Data!'}
            return ObceV54.tw(iso)
        a, b, c = self.at('2026-09-25T09:00:00+00:00')
        with a, b, c, mock.patch.object(zd, 'get_json', gj):
            out = zd.twse_part(prev, 'KLUCZ')
        self.assertEqual(len(asked), 2 + zd.TW_BACK_MAX); self.assertEqual(asked[:2], ['2026-09-24', '2026-09-25'], 'najpierw ostatnie dni')
        self.assertEqual((asked[2], asked[-1]), ('2026-09-10', '2026-08-26'), 'potem wstecz, od najnowszego, najwyżej 12 dni')
        self.assertEqual((tos[:2], set(tos[2:])), ([30, 30], {zd.TW_BACK_TIMEOUT}), 'zapytania wstecz z krótkim limitem czasu')
        days = {r[0] for r in out['d']}
        self.assertNotIn('2026-09-09', out['empty'], 'jedna odpowiedź „No Data!” za starszy dzień to jeszcze nie święto')
        self.assertEqual(out['pend'], {'2026-09-09': '2026-09-25T09:00:00+00:00'})
        self.assertTrue({'2026-08-26', '2026-09-08', '2026-09-25'} <= days); self.assertFalse({'2026-09-10', '2026-09-24', '2026-09-09'} & days)
        self.assertTrue(any(e.startswith('TWSE: 1 dni') and 'Busy' in e for e in zd.META['errors']))
        self.assertTrue(any(n.startswith('TWSE historia wstecz: 1 dni') for n in zd.META['notes']))
        self.assertEqual({r[0]: r[5] for r in out['d']}['2026-08-26'], round(-32964.6 / 31.0, 1), 'starszy dzień też przeliczony na USD')
        asked.clear()
        a, b, c = self.at('2026-09-25T10:00:00+00:00')
        with a, b, c, mock.patch.object(zd, 'get_json', gj):
            out2 = zd.twse_part(out, 'KLUCZ')
        self.assertNotIn('2026-09-09', asked, 'po godzinie — jeszcze nie pytamy ponownie')
        asked.clear()
        a, b, c = self.at('2026-09-25T22:00:00+00:00')
        with a, b, c, mock.patch.object(zd, 'get_json', lambda url, headers=None, timeout=30: {'stat': 'No Data!'} if '20260924' in url else gj(url, headers, timeout)):
            out3 = zd.twse_part(out2, 'KLUCZ')
        self.assertIn('2026-09-09', out3['empty'], 'druga odpowiedź „No Data!” po 13 h — święto')
        self.assertNotIn('pend', out3)
        self.assertIn('2026-09-24', out3['empty'], 'ostatni dzień: „No Data!” od razu = dzień bez sesji (jak dotąd)')

    def test_hkex_backfill_404_is_retried_later_and_three_in_a_row_stop(self):
        prev = {'d': [[d, 1.0, 2.0, 1.0, 2] for d in _wdays('2026-09-11', '2026-09-24')], 'empty': []}
        asked, gone = [], {'2026-09-08'}

        def gb(url, headers=None, timeout=60):
            d = url.split('daily_')[1][:8]; iso = f'{d[:4]}-{d[4:6]}-{d[6:]}'; asked.append(iso)
            if iso == '2026-09-25' or iso in gone or iso < '2026-09-01':
                raise zd.urllib.error.HTTPError(url, 404, 'Not Found', {}, None)
            return HkexV67.JS.replace('2026-09-24', iso).encode()

        def run(prev, now):
            a, b, c = self.at(now)
            with a, b, c, mock.patch.object(zd, 'get_bytes', gb), mock.patch.object(zd, 'get_json', lambda url, headers=None, timeout=30: {'observations': []}):
                return zd.hkex_part(prev, 'KLUCZ')
        out = run(prev, '2026-09-25T09:00:00+00:00')
        days = {r[0] for r in out['d']}
        self.assertTrue({'2026-09-07', '2026-09-01'} <= days, 'jeden brak pliku nie zatrzymuje starszych dni')
        self.assertEqual(set(out['nf']), {'2026-09-08', '2026-08-31', '2026-08-28', '2026-08-27'})
        self.assertNotIn('2026-08-26', asked, '3 braki pliku z rzędu — koniec na ten przebieg')
        self.assertFalse(zd.META['errors'], 'brak starszego pliku to nie błąd')
        self.assertTrue(any(n.startswith('HKEX historia wstecz: brak pliku za 4 dni') for n in zd.META['notes']))
        asked.clear(); out2 = run(out, '2026-09-26T09:00:00+00:00')
        self.assertEqual(asked, ['2026-09-25', '2026-08-26', '2026-08-25', '2026-08-24'], 'dni bez pliku odłożone na tydzień; dalej wstecz')
        gone.clear(); asked.clear(); out3 = run(out2, '2026-10-03T10:00:00+00:00')
        self.assertIn('2026-09-08', asked, 'po tygodniu — ponowna próba')
        self.assertIn('2026-09-08', {r[0] for r in out3['d']})

    def test_backfill_hard_time_budget_and_long_run(self):
        """v95.2–v95.4: budżet liczony razem z najdłuższym możliwym zapytaniem; przebieg dłuższy niż 9 min — bez historii wstecz (z notatką)."""
        prev = {'d': [[d, 1.0, 0, 0, 0] for d in _wdays('2026-09-11', '2026-09-23')], 'empty': []}
        asked = []

        def gj(url, headers=None, timeout=30):
            if 'DEXTAUS' in url:
                return {'observations': []}
            day = url.split('dayDate=')[1][:8]; asked.append(f'{day[:4]}-{day[4:6]}-{day[6:]}')
            return ObceV54.tw(asked[-1])
        clock = iter(range(0, 10000, 15))                  # każde sprawdzenie czasu = +15 s
        a, b, c = self.at('2026-09-25T09:00:00+00:00')
        with a, b, c, mock.patch.object(zd, 'get_json', gj), mock.patch.object(zd.time, 'monotonic', lambda: next(clock)):
            zd.twse_part(prev, '')
        self.assertEqual(asked, ['2026-09-24', '2026-09-25', '2026-09-10'], '15 s + 12 s ≤ 40 s — tak; 30 s + 12 s > 40 s — stop')
        asked.clear(); zd._RUN_T0[0] = zd.time.monotonic() - 700
        a, b, c = self.at('2026-09-25T09:00:00+00:00')
        with a, b, c, mock.patch.object(zd, 'get_json', gj):
            zd.twse_part(prev, '')
        self.assertEqual(asked, ['2026-09-24', '2026-09-25'], 'długi przebieg — tylko ostatnie dni')
        self.assertEqual(sum('historia wstecz pominięta' in n for n in zd.META['notes']), 1, 'jedna notatka z czasem przebiegu')
        zd._RUN_T0[0] = None; zd._BACK_LATE_NOTE[0] = False
        months = []

        def month(ym):
            months.append(ym); return [[ym + '-15', 1.0, 2.0, 0.0, 3.0, 95.0]]
        clock = iter([0, 0, 40, 80, 120])
        with mock.patch.object(zd, 'get_bytes', lambda url, headers=None, timeout=60: ObceV54.NSDL.encode()), mock.patch.object(zd, 'nsdl_month', month), \
                mock.patch.object(zd.time, 'monotonic', lambda: next(clock)):
            out = zd.nsdl_part({'d': []})
        self.assertEqual((months, out['arch']), (['2026-08'], ['2026-08']), 'drugi miesiąc: 40 s + 45 s > 60 s — w następnym przebiegu')

    def test_brazil_asks_for_more_than_a_year(self):
        self.assertGreaterEqual(zd.BCB_DAYS, 365)

    def test_base_rate_for_daily_country_flows(self):
        days = _wdays('2026-03-02', '2026-09-18')
        sign = lambda d: 1 if (datetime.date.fromisoformat(d).isocalendar()[1] // 3) % 2 else -1   # kierunek zmienia się co 3 tygodnie
        ob = {'in': {'d': [[d, 50.0 * sign(d), 10.0, 0, 60.0, 95.0] for d in days]},
              'br': {'d': [[d, -30.0 * sign(d), 0, 0, 0, 0] for d in days]},
              'tw': {'d': [[d, 900.0 * sign(d), 0, 0, 0] for d in days if d != '2026-06-10'], 'empty': []},
              'hk': {'d': [[d, 70.0 * sign(d), 0, 0, 2] for d in days if d != '2026-07-01'], 'empty': ['2026-07-01']}}
        with mock.patch.object(zd, '_now_utc', lambda: self.T0):
            out = zd.build_trendy({'obce': ob})
            today = datetime.date(2026, 9, 25)
            exp = [zd.trend_persist(*zd._tr_cols(ob['in'], 1), today), zd.trend_persist(*zd._tr_cols(ob['in'], 2), today),
                   zd.trend_persist(*zd._tr_sessions(ob['tw'], 1), today), zd.trend_persist(*zd._tr_sessions(ob['hk'], 1), today),
                   zd.trend_persist(*zd._tr_cols(ob['br'], 1), today)]
        b = {x['id']: x for x in out['b']}['ob']
        self.assertEqual((b['k'], b['n']), (sum(e[0] for e in exp), sum(e[1] for e in exp)))
        self.assertTrue(all(e[1] for e in exp), 'każda z 5 serii wnosi przypadki')
        self.assertGreater(b['n'], b['weeks'], 'kilka serii w tym samym tygodniu — niepewność liczona na tygodnie')
        self.assertEqual(b['ci'], list(zd.wilson(b['k'], b['n'], n_eff=b['weeks'])))
        self.assertLess(exp[2][1], exp[4][1], 'Tajwan: tydzień z brakującą sesją (10.06) nie jest liczony')
        self.assertEqual(exp[3][1], exp[4][1], 'Hongkong: znany dzień bez sesji (1.07) nie psuje tygodnia')
        self.assertNotIn('ob', {x['id'] for x in zd.build_trendy({'obce': {}})['b']})

import re as re   # v96: test ikon (moduł testów nie importował re)


class IkonyV96(unittest.TestCase):
    """v96: każda ikona, o którą prosi strona (flagi, krypto, sieci, giełdy, glify), istnieje w img/ i jest bezpiecznym SVG
    (bez skryptów, zdarzeń i odwołań na zewnątrz); publikacja kopiuje img/ i przerywa się bez ikon."""
    ROOT = os.path.dirname(os.path.abspath(__file__))

    def setUp(self):
        self.html = open(os.path.join(self.ROOT, 'index.html'), encoding='utf-8').read()

    def test_every_referenced_icon_file_exists(self):
        h = self.html
        flags = re.search(r"const FLAGS_OK=new Set\('([a-z ]+)'\.split", h).group(1).split()
        self.assertGreater(len(flags), 240)
        for c in flags + ['eu']:
            self.assertTrue(os.path.isfile(os.path.join(self.ROOT, 'img', 'flagi', c + '.svg')), c)
        for grp in re.findall(r"REGF=\{(.*?)\};", h)[:1]:
            for c in re.findall(r"'([a-z]{2})'", grp):
                self.assertIn(c, flags, 'flaga regionu ' + c)
        ccy = re.search(r"const CCY=\{(.*?)\};", h).group(1)
        for c in re.findall(r"\[\s*'([a-z]{2})'\s*,", ccy):
            self.assertIn(c, flags, 'flaga waluty ' + c)
        for c in re.search(r"const CRYPTO_SVG=new Set\('([a-z ]+)'\.split", h).group(1).split():
            self.assertTrue(os.path.isfile(os.path.join(self.ROOT, 'img', 'krypto', c + '.svg')), c)
        for c in set(re.findall(r":'([a-z0-9-]+)'", re.search(r"const NET_SVG=\{(.*?)\};", h).group(1))):
            self.assertTrue(os.path.isfile(os.path.join(self.ROOT, 'img', 'sieci', c + '.svg')), c)
        for c in set(re.findall(r":'([a-z0-9-]+)'", re.search(r"const EXCH_SVG=\{(.*?)\};", h).group(1))):
            self.assertTrue(os.path.isfile(os.path.join(self.ROOT, 'img', 'gieldy', c + '.svg')), c)
        self.assertTrue(os.path.isfile(os.path.join(self.ROOT, 'img', 'sieci', 'hyper-evm.svg')))
        for g in set(re.findall(r"glyphImg\('([a-z]+)'", h)):
            self.assertTrue(os.path.isfile(os.path.join(self.ROOT, 'img', 'glify', g + '.svg')), 'glif ' + g)
        self.assertTrue(os.path.isfile(os.path.join(self.ROOT, 'img', 'LICENCJE.txt')))

    def test_icon_files_are_safe_svg(self):
        bad = re.compile(r'<script|\bon[a-z]+\s*=|javascript:|<foreignObject|<image\b|<!ENTITY|@import|href\s*=\s*["\'](?!#)|url\((?!#)', re.I)
        n = 0
        for d in ('flagi', 'krypto', 'sieci', 'gieldy', 'glify'):
            for f in os.listdir(os.path.join(self.ROOT, 'img', d)):
                t = open(os.path.join(self.ROOT, 'img', d, f), encoding='utf-8').read()
                self.assertTrue(f.endswith('.svg') and t.lstrip().startswith('<svg'), f)
                self.assertIsNone(bad.search(t), d + '/' + f)
                n += 1
        self.assertGreater(n, 300)

    def test_publication_copies_icons(self):
        w = open(os.path.join(self.ROOT, '.github', 'workflows', 'strona.yml'), encoding='utf-8').read()
        self.assertIn('cp -r img _site/img', w)
        self.assertIn('test -f _site/img/flagi/pl.svg', w)


class UsaV97(unittest.TestCase):
    """v97: EIA (energia), BLS (makro USA), BEA (bilans płatniczy USA) — przykładowe odpowiedzi, bez sieci; brak nie jest zerem;
    klucze nigdy w plikach wynikowych ani w komunikatach."""
    KEY = 'SEKRET-KLUCZ-123'

    def setUp(self):
        zd.META['errors'].clear(); zd.META['notes'].clear(); zd.META['ok'].clear()
        self._sec = list(zd.SECRETS); zd.SECRETS[:] = [self.KEY]

    def tearDown(self):
        zd.SECRETS[:] = self._sec

    @staticmethod
    def eia(sid, rows):
        return {'response': {'total': '9983', 'frequency': 'daily', 'data': [
            {'period': d, 'series': sid, 'value': v, 'units': '$/BBL'} for d, v in rows]},
            'warnings': [{'warning': 'incomplete return', 'description': 'The API can only return 5000 rows'}]}

    def test_eia_series_url_parse_and_missing_values(self):
        seen = []

        def gj(url, headers=None, timeout=30):
            seen.append(url)
            return self.eia('RWTC', [('2026-09-22', '96.41'), ('2026-09-21', '96.97'), ('2026-09-19', None), ('2026-09-18', '-')])
        with mock.patch.object(zd, 'get_json', gj):
            d, unit = zd.eia_series(self.KEY, 'petroleum/pri/spt', 'daily', 'RWTC', 90)
        self.assertEqual(d, [['2026-09-21', 96.97], ['2026-09-22', 96.41]], 'rosnąco; brak i „-” pominięte, nie zero')
        self.assertEqual(unit, '$/BBL')
        self.assertIn('https://api.eia.gov/v2/petroleum/pri/spt/data/?api_key=SEKRET-KLUCZ-123&frequency=daily&data%5B0%5D=value&facets%5Bseries%5D%5B%5D=RWTC', seen[0])
        self.assertIn('sort%5B0%5D%5Bdirection%5D=desc', seen[0])
        with mock.patch.object(zd, 'get_json', lambda url, headers=None, timeout=30: {'error': {'code': 'API_KEY_INVALID'}}):
            self.assertRaises(RuntimeError, zd.eia_series, self.KEY, 'petroleum/pri/spt', 'daily', 'RWTC', 90)
        with mock.patch.object(zd, 'get_json', lambda url, headers=None, timeout=30: self.eia('RBRTE', [('2026-09-22', '114.89')])):
            self.assertRaises(RuntimeError, zd.eia_series, self.KEY, 'petroleum/pri/spt', 'daily', 'RWTC', 90)   # inna seria = brak

    def test_build_energia_keeps_old_series_and_masks_key(self):
        def gj(url, headers=None, timeout=30):
            if 'RBRTE' in url:
                raise RuntimeError(f'HTTP Error 503 dla {url}')
            sid = re.search(r'facets%5Bseries%5D%5B%5D=([A-Z0-9]+)', url).group(1)
            return self.eia(sid, [('2026-09-18', '100'), ('2026-09-22', '101.5')])
        prev = {'s': {'brent': {'id': 'RBRTE', 'freq': 'daily', 'unit': '$/BBL', 'd': [['2026-09-19', 110.0]]}}}
        with mock.patch.object(zd, 'get_json', gj):
            out = zd.build_energia(self.KEY, prev)
        self.assertEqual(set(out['s']), {'wti', 'brent', 'gas', 'crude', 'spr'})
        self.assertEqual(out['s']['brent']['d'], [['2026-09-19', 110.0]], 'seria bez odpowiedzi — poprzednie wartości z datą')
        self.assertEqual(out['s']['wti']['d'][-1], ['2026-09-22', 101.5])
        self.assertTrue(any(e.startswith('EIA: 1 serie') for e in zd.META['errors']))
        self.assertFalse(any(self.KEY in e for e in zd.META['errors']), 'klucz nigdy w komunikatach')
        self.assertNotIn(self.KEY, json.dumps(out))
        with mock.patch.object(zd, 'get_json', lambda url, headers=None, timeout=30: {'error': 'x'}):
            self.assertRaises(RuntimeError, zd.build_energia, self.KEY, None)

    def test_bls_payload_missing_month_yoy_and_payroll_change(self):
        sent = []

        def pj(url, obj, timeout=60):
            sent.append(obj)
            mk = lambda sid, vals: {'seriesID': sid, 'data': [{'year': y, 'period': p, 'value': v} for y, p, v in vals]}
            return {'status': 'REQUEST_SUCCEEDED', 'message': [], 'Results': {'series': [
                mk('CUUR0000SA0', [('2026', 'M08', '334.980'), ('2025', 'M08', '323.976'), ('2025', 'M10', '-'), ('2026', 'M10', '336'), ('2025', 'M13', '322')]),
                mk('LNS14000000', [('2026', 'M08', '4.4'), ('2026', 'M07', '4.3')]),
                mk('CES0000000001', [('2026', 'M06', '159500'), ('2026', 'M07', '159600'), ('2026', 'M08', '159650'), ('2026', 'M10', '159700')]),
                mk('CES0500000003', [('2026', 'M08', '37.10')])]}}
        with mock.patch.object(zd, 'post_json', pj):
            out = zd.build_usa_makro(self.KEY, None, today=datetime.date(2026, 9, 25))
        self.assertEqual(sent[0]['seriesid'][:2], ['CUUR0000SA0', 'CUUR0000SA0L1E'])
        self.assertEqual((sent[0]['startyear'], sent[0]['endyear'], sent[0]['registrationkey']), ('2024', '2026', self.KEY))
        cpi = out['s']['cpi']
        self.assertIn(['2025-10', None], cpi['d'], '„-” = brak, nie zero'); self.assertNotIn('2025-13', [d for d, _ in cpi['d']], 'M13 pominięte')
        self.assertEqual(cpi['yoy'], [['2026-08', round((334.98 / 323.976 - 1) * 100, 1)]], 'r/r tylko gdy są obie wartości (X 2026 bez X 2025)')
        self.assertEqual(out['s']['nfp']['chg'], [['2026-07', 100.0], ['2026-08', 50.0]], 'zmiana m/m tylko dla kolejnych miesięcy (IX brak)')
        self.assertNotIn('core', out['s']); self.assertTrue(any(e.startswith('BLS: brak serii CUUR0000SA0L1E') for e in zd.META['errors']))
        self.assertNotIn(self.KEY, json.dumps(out), 'klucz nie trafia do pliku')
        with mock.patch.object(zd, 'post_json', lambda url, obj, timeout=60: {'status': 'REQUEST_NOT_PROCESSED', 'message': ['daily threshold']}):
            self.assertRaisesRegex(RuntimeError, 'REQUEST_NOT_PROCESSED', zd.build_usa_makro, self.KEY, None)
        sent.clear()
        with mock.patch.object(zd, 'post_json', pj):
            zd.build_usa_makro('', None, today=datetime.date(2026, 9, 25))
        self.assertNotIn('registrationkey', sent[0], 'bez klucza — zapytanie publiczne (mniejszy limit)')

    def test_bea_units_errors_areas_and_gdp(self):
        def gj(url, headers=None, timeout=30):
            q = dict(zd.urllib.parse.parse_qsl(url.split('?', 1)[1]))
            self.assertEqual((q['UserID'], q['ResultFormat']), (self.KEY, 'JSON'))
            if q['method'] == 'GetParameterValues':
                vals = [{'Key': 'BalCurrAcct', 'Desc': 'Balance on current account'}, {'Key': 'FinAssetsExclFinDeriv', 'Desc': 'U.S. assets'},
                        {'Key': 'FinLiabsExclFinDeriv', 'Desc': 'U.S. liabilities'}] if q['ParameterName'] == 'Indicator' else \
                       [{'Key': 'AllCountries', 'Desc': 'All Countries Total'}, {'Key': 'China', 'Desc': 'China'}]
                return {'BEAAPI': {'Results': {'ParamValue': vals}}}
            if q.get('datasetname') == 'NIPA':
                self.assertEqual((q['TableName'], q['Frequency'], q['Year']), ('T10101', 'Q', '2023,2024,2025,2026'))
                return {'BEAAPI': {'Results': {'Data': [{'LineNumber': '1', 'TimePeriod': '2026Q2', 'DataValue': '3.8'},
                                                         {'LineNumber': '2', 'TimePeriod': '2026Q2', 'DataValue': '9.9'}]}}}
            if q['Indicator'] == 'NetLendBorrFinAcct':
                return {'BEAAPI': {'Results': {'Error': {'APIErrorCode': '1', 'APIErrorDescription': 'Invalid Indicator'}}}}
            if q['AreaOrCountry'] == 'All':
                self.assertEqual(q['Frequency'], 'QNSA')
                return {'BEAAPI': {'Results': {'Data': [{'AreaOrCountry': 'China', 'TimePeriod': '2026Q1', 'UNIT_MULT': '6', 'DataValue': '-1,234'},
                                                         {'AreaOrCountry': 'Europe', 'TimePeriod': '2026Q1', 'UNIT_MULT': '6', 'DataValue': '(D)'}]}}}
            return {'BEAAPI': {'Results': {'Data': [{'TimePeriod': '2026Q1', 'UNIT_MULT': '6', 'DataValue': '311,234'},
                                                     {'TimePeriod': '2026Q2', 'UNIT_MULT': '9', 'DataValue': '0.5'}]}}}
        with mock.patch.object(zd, 'get_json', gj):
            out = zd.build_bilans_usa(self.KEY, None, today=datetime.date(2026, 9, 25))
        self.assertEqual(out['ita']['BalCurrAcct'], [['2026-Q1', 311234.0], ['2026-Q2', 500.0]], 'mln USD: przecinki i UNIT_MULT')
        self.assertNotIn('NetLendBorrFinAcct', out['ita'])
        self.assertEqual(out['areas']['FinLiabsExclFinDeriv'], {'China': [['2026-Q1', -1234.0]]}, '„(D)” = brak, nie zero')
        self.assertEqual(out['gdp'], [['2026-Q2', 3.8]]); self.assertEqual(out['names']['China'], 'China')
        self.assertTrue(any(n.startswith('BEA: brak wskaźników NetLendBorrFinAcct') for n in zd.META['notes']))
        self.assertTrue(any(e.startswith('BEA: 1 zapytań bez danych') and 'Invalid Indicator' in e for e in zd.META['errors']))
        self.assertNotIn(self.KEY, json.dumps(out))
        bad = lambda url, headers=None, timeout=30: {'BEAAPI': {'Results': {'Error': {'APIErrorDescription': 'Invalid Request - Invalid API UserId.'}}}}
        with mock.patch.object(zd, 'get_json', bad):
            self.assertRaisesRegex(RuntimeError, 'Invalid API UserId', zd.build_bilans_usa, self.KEY, None)

    def test_main_block_cache_missing_key_and_failure_keeps_previous(self):
        saved = {}
        prev = {'energia': {'at': '2026-09-25T00:00:00+00:00', 's': {}}, 'bilans-usa': {'at': zd.NOW, 'ita': {}}}
        calls = []
        env = {'EIA_KEY': 'k1', 'BLS_KEY': '', 'BEA_KEY': ''}
        stubs = [mock.patch.object(zd, f, side_effect=RuntimeError('offline'), create=True) for f in
                 ('build_instytucje', 'build_krypto', 'build_tic', 'build_bis', 'build_cftc', 'build_cm', 'build_rezerwy', 'build_stopy', 'build_kursy', 'build_obce',
                  'build_eer', 'build_cofer', 'build_bilans', 'build_safe', 'build_ue', 'build_kanada', 'build_korea', 'build_spw', 'build_meksyk',
                  'build_fundusze', 'build_surowce', 'build_trendy', 'build_fred', 'build_etf', 'build_day', 'build_prices', 'build_cmc', 'build_oecd', 'build_rynki')]
        for s in stubs:
            s.start()
        try:
            with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(zd, 'save', lambda n, o: saved.__setitem__(n, o)), \
                    mock.patch.object(zd, 'previous', lambda n: prev.get(n)), \
                    mock.patch.object(zd, 'build_energia', lambda k, p: calls.append(('eia', k)) or (_ for _ in ()).throw(RuntimeError('HTTP 500'))), \
                    mock.patch.object(zd, 'build_usa_makro', lambda k, p: calls.append(('bls', k)) or {'at': 'x', 's': {}}), \
                    mock.patch.object(zd, 'build_bilans_usa', lambda k, p: calls.append(('bea', k)) or {}):
                zd.main()
        finally:
            for s in stubs:
                s.stop()
        self.assertEqual(calls, [('eia', 'k1'), ('bls', '')], 'BEA: plik młodszy niż doba — bez zapytań; BLS działa bez klucza')
        self.assertIs(saved['energia'], prev['energia'], 'awaria EIA — zostaje poprzedni plik')
        self.assertEqual((zd.META['ok']['eia'], zd.META['ok']['bls'], zd.META['ok']['bea']), (False, True, 'cached'))
        self.assertIn('EIA: HTTP 500', zd.META['errors'])


if __name__ == '__main__':
    unittest.main()


class OecdV99(unittest.TestCase):
    """v99: OECD na serwerze — kształt jak gOecd() na stronie, brak ≠ zero, część z błędem = poprzednia wersja z własnym czasem."""
    SD = {'data': {'structure': {'dimensions': {'observation': [
        {'id': 'REF_AREA', 'values': [{'id': 'USA'}, {'id': 'JPN'}]}, {'id': 'FREQ', 'values': [{'id': 'M'}]},
        {'id': 'TIME_PERIOD', 'values': [{'id': '2026-08'}, {'id': '2026-07'}]}]}},
        'dataSets': [{'observations': {'0:0:0': [230.7], '0:0:1': [224.2], '1:0:0': [None], '1:0:1': [True], }}]}}

    def test_start_like_page(self):
        self.assertEqual(zd.oecd_start(datetime.date(2026, 9, 25)), '2025-06')
        self.assertEqual(zd.oecd_start(datetime.date(2026, 1, 5)), '2024-10')
        self.assertEqual(zd.oecd_start(datetime.date(2026, 3, 31)), '2024-12')

    def test_parse_sorted_skip_missing(self):
        self.assertEqual(zd.oecd_parse(self.SD), {'USA': [['2026-07', 224.2], ['2026-08', 230.7]]})   # JPN: null i bool — brak, nie zero

    def test_iso_same_as_page(self):
        import re
        html = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'index.html'), encoding='utf-8').read()
        g = html[html.index('const GREG='):]
        g = g[:g.index('];')]
        iso = []
        for m in re.finditer(r"iso:\[([^\]]*)\]", g):
            for x in re.findall(r"'([A-Z]{3})'", m.group(1)):
                if x not in iso:
                    iso.append(x)
        self.assertEqual(zd.OECD_ISO, iso)
        self.assertIn("srvJSON('oecd')", html)

    def test_build_ok_and_partial_failure(self):
        zd.META['errors'].clear()
        with mock.patch.object(zd, 'oecd_get', return_value=self.SD), mock.patch.object(zd.time, 'sleep'):
            o = zd.build_oecd(None, today=datetime.date(2026, 9, 25))
        self.assertEqual(o['ok'], {'share': True, 'irlt': True, 'cli': True})
        self.assertEqual(o['start'], '2025-06'); self.assertEqual(o['part_at']['cli'], zd.NOW)
        self.assertEqual(zd.META['errors'], [])
        prev = {'at': '2026-09-24T00:00:00+00:00', 'cli': {'USA': [['2026-06', 100.5]]}, 'part_at': {'cli': '2026-09-20T00:00:00+00:00'}}

        def fake(path, start, _retry=True):
            if 'DF_CLI' in path:
                raise zd.urllib.error.HTTPError('u', 429, 'Too Many Requests', {}, None)
            return self.SD
        with mock.patch.object(zd, 'oecd_get', side_effect=fake), mock.patch.object(zd.time, 'sleep'):
            o = zd.build_oecd(prev, today=datetime.date(2026, 9, 25))
        self.assertEqual(o['ok']['cli'], False)
        self.assertEqual(o['cli'], prev['cli'], 'część z błędem — poprzednia wersja')
        self.assertEqual(o['part_at']['cli'], '2026-09-20T00:00:00+00:00', 'z własnym (starszym) czasem')
        self.assertTrue(any(e.startswith('OECD: cli:') for e in zd.META['errors']))
        zd.META['errors'].clear()
        with mock.patch.object(zd, 'oecd_get', side_effect=RuntimeError('offline')), mock.patch.object(zd.time, 'sleep'):
            with self.assertRaises(RuntimeError):
                zd.build_oecd(None, today=datetime.date(2026, 9, 25))   # bez indeksów giełdowych — nie zapisujemy pustego pliku
        zd.META['errors'].clear()

    def test_retry_once_on_429(self):
        calls = []

        def g(url, headers=None, timeout=30):
            calls.append(url)
            if len(calls) == 1:
                raise zd.urllib.error.HTTPError(url, 429, 'Too Many Requests', {}, None)
            return self.SD
        with mock.patch.object(zd, 'get_json', side_effect=g), mock.patch.object(zd.time, 'sleep'):
            self.assertEqual(zd.oecd_get(zd.OECD_Q['share'], '2025-06'), self.SD)
        self.assertEqual(len(calls), 2)
        self.assertIn('USA+CAN+BRA', calls[0]); self.assertIn('startPeriod=2025-06&format=jsondata', calls[0])

class RynkiV101(unittest.TestCase):
    """v101: kursy EBC i rentowności 10L na serwerze — kształt jak na stronie, brak ≠ zero, część z błędem = poprzednia wersja."""
    XML = ('<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom" '
           'xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata" xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">'
           '<entry><content type="application/xml"><m:properties><d:NEW_DATE m:type="Edm.DateTime">2026-09-25T00:00:00</d:NEW_DATE><d:BC_10YEAR m:type="Edm.Double">5.17</d:BC_10YEAR></m:properties></content></entry>'
           '<entry><content type="application/xml"><m:properties><d:NEW_DATE m:type="Edm.DateTime">2026-09-24T00:00:00</d:NEW_DATE><d:BC_10YEAR m:type="Edm.Double">5.12</d:BC_10YEAR></m:properties></content></entry>'
           '<entry><content type="application/xml"><m:properties><d:NEW_DATE m:type="Edm.DateTime">2026-09-23T00:00:00</d:NEW_DATE><d:BC_10YEAR m:null="true"/></m:properties></content></entry></feed>')
    BUBA = {'data': {'dataSets': [{'series': {'0:0': {'observations': {'0': ['3.55'], '1': ['3.60'], '2': [None]}}}}],
                     'structure': {'dimensions': {'observation': [{'values': [{'id': '2026-09-24'}, {'id': '2026-09-25'}, {'id': '2026-09-26'}]}]}}}}
    FX = {'amount': 1.0, 'base': 'USD', 'date': '2026-09-25', 'rates': {'EUR': 0.877}}

    def test_dates_like_page(self):
        self.assertEqual(zd.months_back(datetime.date(2026, 3, 31), 1), datetime.date(2026, 2, 28))
        self.assertEqual(zd.months_back(datetime.date(2026, 9, 25), 12), datetime.date(2025, 9, 25))
        self.assertEqual(zd.fx_dates(datetime.date(2026, 9, 25)), {'now': 'latest', '1M': '2026-08-25', '1Q': '2026-06-25', '1R': '2025-09-25', '1D': '2026-09-24', '1T': '2026-09-18'})

    def test_parsers(self):
        self.assertEqual(zd.ust_parse(self.XML), [['2026-09-24', 5.12], ['2026-09-25', 5.17]])   # brak wartości — brak wiersza, nie zero
        self.assertEqual(zd.buba_parse(self.BUBA), [['2026-09-24', 3.55], ['2026-09-25', 3.6]])

    def test_build_parts_and_fallback(self):
        zd.META['errors'].clear()
        calls = []

        def gj(url, headers=None, timeout=30):
            calls.append(url)
            return self.BUBA if 'bundesbank' in url else self.FX

        def gt(url, headers=None, timeout=30):
            calls.append(url)
            return 200, self.XML
        with mock.patch.object(zd, 'get_json', side_effect=gj), mock.patch.object(zd, 'get', side_effect=gt):
            o = zd.build_rynki(None, today=datetime.date(2026, 9, 26))
        self.assertEqual(o['ok'], {'fx': True, 'ust': True, 'buba': True})
        self.assertEqual(sorted(o['fx']), ['1D', '1M', '1Q', '1R', '1T', 'now'])
        self.assertEqual(sum('field_tdr_date_value=2025' in c for c in calls), 1, 'poprzedni rok pobrany, gdy go brak')
        self.assertIn('startPeriod=2025-08-26', [c for c in calls if 'bundesbank' in c][0])
        prev = {'at': '2026-09-25T00:00:00+00:00', 'fx': {'now': self.FX}, 'part_at': {'fx': '2026-09-25T10:00:00+00:00'},
                'ust': [['2025-%02d-%02d' % (1 + i // 28, 1 + i % 28), 4.0] for i in range(250)]}
        calls.clear()

        def gj2(url, headers=None, timeout=30):
            calls.append(url)
            if 'frankfurter' in url:
                raise zd.urllib.error.HTTPError(url, 503, 'Service Unavailable', {}, None)
            return self.BUBA
        with mock.patch.object(zd, 'get_json', side_effect=gj2), mock.patch.object(zd, 'get', side_effect=gt):
            o = zd.build_rynki(prev, today=datetime.date(2026, 9, 26))
        self.assertEqual(o['ok']['fx'], False)
        self.assertEqual(o['fx'], prev['fx']); self.assertEqual(o['part_at']['fx'], '2026-09-25T10:00:00+00:00', 'część z błędem — poprzednia, z własnym czasem')
        self.assertTrue(any(e.startswith('Frankfurter:') for e in zd.META['errors']))
        self.assertFalse(any('field_tdr_date_value=2025' in c for c in calls), 'poprzedni rok z pliku — bez pobierania')
        self.assertEqual(o['ust'][-1], ['2026-09-25', 5.17])
        zd.META['errors'].clear()
        with mock.patch.object(zd, 'get_json', side_effect=RuntimeError('offline')), mock.patch.object(zd, 'get', side_effect=RuntimeError('offline')):
            with self.assertRaises(RuntimeError):
                zd.build_rynki(None, today=datetime.date(2026, 9, 26))
        zd.META['errors'].clear()

