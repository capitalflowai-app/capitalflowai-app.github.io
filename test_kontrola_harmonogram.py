"""Kontrole cztery razy dziennie i niezależny zegar zapasowy; bez sieci i czekania."""
import contextlib
import datetime as dt
import importlib.util
import io
from pathlib import Path
import re
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('kontrola_harmonogram_zegar', ROOT / 'narzedzia' / 'zegar.py')
ZEGAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ZEGAR)


class KontrolaHarmonogram(unittest.TestCase):
    @staticmethod
    def now(value):
        return dt.datetime.fromisoformat(value).replace(tzinfo=dt.timezone.utc)

    @staticmethod
    def run_at(value, status='completed'):
        return {'created_at': value + 'Z', 'status': status, 'event': 'schedule'}

    def run_clock(self, now, runs=(), archive_done=True):
        posts, reads = [], []

        def fetch(wf, token):
            reads.append(wf)
            if wf == 'kontrola.yml':
                return list(runs)
            return [self.run_at(now.date().isoformat() + 'T01:30:00')] if archive_done else []

        def dispatch(wf, token):
            posts.append(wf)
            return 204

        with mock.patch.object(ZEGAR, 'przebiegi_wf', fetch), mock.patch.object(ZEGAR, 'uruchom', dispatch), contextlib.redirect_stdout(io.StringIO()):
            rc = ZEGAR._dzienne('test-token', now)
        self.assertEqual(rc, 0)
        self.assertEqual(reads, ['kontrola.yml', 'archiwum.yml'], 'jeden odczyt na workflow, bez czterech równoległych dispatches')
        return posts

    def test_cron_and_clock_cover_the_same_four_slots(self):
        workflow = (ROOT / '.github' / 'workflows' / 'kontrola.yml').read_text()
        slots = re.findall(r"cron: '(\d+) (\d+) \* \* \*'", workflow)
        self.assertEqual([(int(h), int(m)) for m, h in slots], [(6, 20), (11, 20), (16, 20), (21, 20)])
        self.assertEqual(ZEGAR.KONTROLA_GODZINY, (6, 11, 16, 21))
        self.assertIn('python3 -m unittest -v test_kontrola_harmonogram.py', workflow)

    def test_each_missing_slot_runs_after_its_grace_period(self):
        for hour in ZEGAR.KONTROLA_GODZINY:
            with self.subTest(hour=hour):
                now = self.now(f'2026-11-03T{hour + 1:02d}:30:00')
                prior = [self.run_at(f'2026-11-03T{h:02d}:25:00') for h in ZEGAR.KONTROLA_GODZINY if h < hour]
                self.assertEqual(self.run_clock(now, prior), ['kontrola.yml'])

    def test_previous_check_does_not_replace_later_checks(self):
        morning = [self.run_at('2026-11-03T06:25:00')]
        self.assertEqual(self.run_clock(self.now('2026-11-03T12:30:00'), morning), ['kontrola.yml'])
        self.assertEqual(self.run_clock(self.now('2026-11-03T17:30:00'), morning), ['kontrola.yml'])
        self.assertEqual(self.run_clock(self.now('2026-11-03T22:30:00'), morning), ['kontrola.yml'])

    def test_grace_period_does_not_create_an_early_duplicate(self):
        for hour in (11, 16, 21):
            with self.subTest(hour=hour):
                earlier = [self.run_at(f'2026-11-03T{hour - 5:02d}:25:00')]
                self.assertEqual(self.run_clock(self.now(f'2026-11-03T{hour + 1:02d}:29:59'), earlier), [])

    def test_existing_scheduled_or_fallback_run_prevents_a_duplicate(self):
        now = self.now('2026-11-03T17:40:00')
        for at, status in (('2026-11-03T16:25:00', 'completed'), ('2026-11-03T17:31:00', 'completed'),
                           ('2026-11-03T17:31:00', 'queued'), ('2026-11-03T16:25:00', 'in_progress')):
            with self.subTest(at=at, status=status):
                self.assertEqual(self.run_clock(now, [self.run_at(at, status)]), [])

    def test_long_outage_creates_one_current_report(self):
        self.assertEqual(self.run_clock(self.now('2026-11-03T23:59:00')), ['kontrola.yml'])

    def test_new_day_does_not_replay_yesterdays_four_reports(self):
        self.assertEqual(self.run_clock(self.now('2026-11-04T00:10:00')), [])
        yesterday = [self.run_at('2026-11-03T21:25:00')]
        self.assertEqual(self.run_clock(self.now('2026-11-04T07:30:00'), yesterday), ['kontrola.yml'])

    def test_archive_keeps_its_own_daily_schedule(self):
        self.assertEqual(self.run_clock(self.now('2026-11-03T02:59:59'), archive_done=False), [])
        self.assertEqual(self.run_clock(self.now('2026-11-03T03:00:00'), archive_done=False), ['archiwum.yml'])
        self.assertEqual(self.run_clock(self.now('2026-11-03T23:59:00'), archive_done=False), ['kontrola.yml', 'archiwum.yml'])


if __name__ == '__main__':
    unittest.main()
