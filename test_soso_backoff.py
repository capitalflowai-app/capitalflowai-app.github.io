"""Celowane testy trwałej przerwy SoSoValue po 429; bez sieci i rzeczywistego czekania."""
import contextlib
import copy
import datetime
import email.utils
import io
import os
import unittest
from unittest import mock

import zbieraj_dane as zd
import test_zbieraj_dane as fixtures


UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 11, 5, 12, 0, tzinfo=UTC)


def error(code=429, retry=None):
    headers = {} if retry is None else {'Retry-After': retry}
    return zd.urllib.error.HTTPError(zd.SOSO, code, 'Too Many Requests' if code == 429 else 'Forbidden', headers, None)


def previous_etf():
    return {'at': (NOW - datetime.timedelta(hours=3)).isoformat(),
            'mcap': {s: 1e11 for s in zd.ETF_SYMS}, 'mcap_at': NOW.isoformat(),
            'assets': {s: {'sym': s.upper(), 'asof': '2026-11-04', 'day': [[zd.ts('2026-11-04'), 1.0]],
                           'd1': 1.0, 'funds': []} for s in zd.ETF_SYMS}}


class SosoBackoff(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.object(zd, 'META', {'at': NOW.isoformat(), 'ok': {}, 'errors': [], 'notes': []}))
        self.enterContext(mock.patch.object(zd, 'NOW', NOW.isoformat()))
        self.enterContext(mock.patch.object(zd, '_now_utc', return_value=NOW))
        self.sleep = self.enterContext(mock.patch.object(zd.time, 'sleep'))
        self.enterContext(mock.patch.object(zd.urllib.request, 'urlopen', side_effect=AssertionError('sieć wyłączona')))
        self.enterContext(contextlib.redirect_stdout(io.StringIO()))

    def test_retry_after_seconds_or_http_date_without_retry_or_long_sleep(self):
        date = email.utils.format_datetime(NOW + datetime.timedelta(hours=2), usegmt=True)
        for retry in ('7200', date):
            with self.subTest(retry=retry):
                zd.META.pop('soso_blok429', None)
                self.sleep.reset_mock()
                with mock.patch.object(zd, 'get_json', side_effect=error(retry=retry)) as get:
                    with self.assertRaises(zd.urllib.error.HTTPError):
                        zd.soso('/etfs/summary-history?symbol=BTC', 'test-key')
                    with self.assertRaisesRegex(RuntimeError, '429'):
                        zd.soso('/etfs/summary-history?symbol=ETH', 'test-key')
                get.assert_called_once()
                self.sleep.assert_called_once_with(zd.SOSO_SLEEP)
                self.assertEqual(datetime.datetime.fromisoformat(zd.META['soso_blok429']['do']), NOW + datetime.timedelta(hours=2))

    def test_missing_invalid_short_or_past_retry_uses_minimum_cooldown(self):
        past = email.utils.format_datetime(NOW - datetime.timedelta(hours=1), usegmt=True)
        for retry in (None, '', 'n/a', '-1', 'nan', '30.5', '0', '65', past):
            with self.subTest(retry=retry):
                zd.META.pop('soso_blok429', None)
                with mock.patch.object(zd, 'get_json', side_effect=error(retry=retry)):
                    with self.assertRaises(zd.urllib.error.HTTPError):
                        zd.soso('/etfs', 'test-key', _retry=False)
                self.assertEqual(datetime.datetime.fromisoformat(zd.META['soso_blok429']['do']), NOW + datetime.timedelta(minutes=55))

    def test_http_date_never_shortened_by_fractional_clock(self):
        start = NOW.replace(microsecond=900000)
        until = NOW + datetime.timedelta(hours=2)
        with mock.patch.object(zd, '_now_utc', return_value=start), mock.patch.object(zd, 'get_json', side_effect=error(retry=email.utils.format_datetime(until, usegmt=True))):
            with self.assertRaises(zd.urllib.error.HTTPError):
                zd.soso('/etfs', 'test-key')
        self.assertGreaterEqual(datetime.datetime.fromisoformat(zd.META['soso_blok429']['do']), until)

    def test_cooldown_boundaries_and_malformed_state(self):
        good = {'soso_blok429': {'od': NOW.isoformat(), 'do': (NOW + datetime.timedelta(hours=2)).isoformat()}}
        self.assertTrue(zd.soso_blok429_swieza(good, NOW))
        self.assertFalse(zd.soso_blok429_swieza(good, NOW - datetime.timedelta(seconds=1)))
        self.assertFalse(zd.soso_blok429_swieza(good, NOW + datetime.timedelta(hours=2)))
        for bad in (None, [], {}, {'soso_blok429': 3}, {'soso_blok429': {'od': 'bad', 'do': 'bad'}},
                    {'soso_blok429': {'od': NOW.isoformat(), 'do': NOW.isoformat()}}):
            self.assertFalse(zd.soso_blok429_swieza(bad, NOW))

    def test_403_and_response_validation_remain_unchanged(self):
        with mock.patch.object(zd, 'get_json', side_effect=error(403)) as get:
            with self.assertRaises(zd.urllib.error.HTTPError) as raised:
                zd.soso('/etfs', 'test-key')
        self.assertEqual(raised.exception.code, 403)
        get.assert_called_once()
        self.assertNotIn('soso_blok429', zd.META)
        with mock.patch.object(zd, 'get_json', return_value={'code': 7, 'message': 'bad reply'}):
            with self.assertRaisesRegex(RuntimeError, 'bad reply'):
                zd.soso('/etfs', 'test-key')
        with mock.patch.object(zd, 'get_json', return_value={'code': 0, 'data': [1, 2]}):
            self.assertEqual(zd.soso('/etfs', 'test-key'), [1, 2])

    def test_first_429_stops_all_other_coins_including_fast_mode(self):
        for only in (None, {'eth'}):
            with self.subTest(only=only):
                zd.META.pop('soso_blok429', None)
                prev = previous_etf()
                before = copy.deepcopy(prev)
                with mock.patch.object(zd, 'get_json', side_effect=error()) as get:
                    with self.assertRaises(RuntimeError):
                        zd.build_etf('test-key', '', prev, tylko=only)
                get.assert_called_once()
                self.assertEqual(prev, before)


class SosoBackoffMain(unittest.TestCase):
    def setUp(self):
        SosoBackoff.setUp(self)
        fixtures.MainFlow.setUp(self)
        self.addCleanup(fixtures.MainFlow.tearDown, self)
        env = {k: '' for k in os.environ if k.endswith('_KEY')}
        env.update(SOSOVALUE_KEY='test-soso-secret', SITE_URL='', CACHE_DIR='')
        self.enterContext(mock.patch.dict(os.environ, env))

    def test_429_persists_then_skips_next_run_without_forging_etf(self):
        for prev in (None, previous_etf()):
            with self.subTest(has_previous=bool(prev)):
                self.saved.clear()
                zd.META.pop('soso_blok429', None)
                calls = []
                def get(url, headers=None, timeout=30):
                    if url.startswith(zd.SOSO):
                        calls.append(url)
                        raise error(retry='7200')
                    raise RuntimeError('offline')
                with mock.patch.object(zd, 'previous', side_effect=lambda n: prev if n == 'etf' else None), mock.patch.object(zd, 'get_json', side_effect=get):
                    zd.main()
                self.assertEqual(len(calls), 1)
                meta = copy.deepcopy(self.saved['meta'])
                self.assertIn('soso_blok429', meta)
                self.assertIs(meta['ok']['sosovalue'], False)
                self.assertEqual('etf' in self.saved, prev is not None)
                if prev:
                    self.assertEqual(self.saved['etf'], prev)
                self.saved.clear()
                later = NOW + datetime.timedelta(minutes=10)
                with mock.patch.object(zd, '_now_utc', return_value=later), mock.patch.object(zd, 'NOW', later.isoformat()), \
                     mock.patch.object(zd, 'previous', side_effect=lambda n: meta if n == 'meta' else prev if n == 'etf' else None) as previous, \
                     mock.patch.object(zd, 'build_etf', side_effect=AssertionError('przerwa 429')) as build:
                    zd.main()
                build.assert_not_called()
                self.assertEqual([c for c in previous.call_args_list if c.args == ('meta',)], [mock.call('meta')])
                self.assertEqual(self.saved['meta']['soso_blok429'], meta['soso_blok429'], 'kolejny przebieg nie przesuwa końca przerwy')
                self.assertIs(self.saved['meta']['ok']['sosovalue'], False)
                self.assertTrue(any('429' in e for e in self.saved['meta']['errors']))
                self.assertEqual('etf' in self.saved, prev is not None)

    def test_expired_cooldown_allows_success_and_clears_marker(self):
        meta = {'soso_blok429': {'od': (NOW - datetime.timedelta(hours=3)).isoformat(), 'do': NOW.isoformat()}}
        new = {'at': NOW.isoformat(), 'assets': {}}
        with mock.patch.object(zd, 'previous', side_effect=lambda n: meta if n == 'meta' else None), mock.patch.object(zd, 'build_etf', return_value=new) as build:
            zd.main()
        build.assert_called_once()
        self.assertIs(self.saved['etf'], new)
        self.assertIs(zd.META['ok']['sosovalue'], True)
        self.assertNotIn('soso_blok429', self.saved['meta'])

    def test_partial_success_keeps_valid_data_and_reports_rate_limit(self):
        prev = previous_etf()
        def coin(out, sym, key, *args, **kwargs):
            if sym == 'btc':
                out['assets']['btc'] = copy.deepcopy(prev['assets']['btc'])
                return
            zd.soso('/etfs/summary-history?symbol=' + sym.upper(), key)
        with mock.patch.object(zd, 'previous', side_effect=lambda n: prev if n == 'etf' else None), \
             mock.patch.object(zd, 'get_json', side_effect=error()), mock.patch.object(zd, '_etf_coin', side_effect=coin) as build_coin:
            zd.main()
        self.assertEqual(build_coin.call_count, 2, 'BTC sukces, ETH 429, SOL/XRP bez prób')
        self.assertEqual(set(self.saved['etf']['assets']), set(zd.ETF_SYMS))
        self.assertIs(zd.META['ok']['sosovalue'], False)
        self.assertIn('soso_blok429', self.saved['meta'])


if __name__ == '__main__':
    unittest.main()
