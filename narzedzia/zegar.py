#!/usr/bin/env python3
"""v145: zapasowy zegar automatu strony. 03.10.2026 harmonogram GitHub (cron) workflow „Strona i dane” przestał uruchamiać przebiegi
po 11:05 UTC (GitHub: „All Systems Operational”, harmonogramy dzienne działały) — dane odświeżały się tylko przy publikacjach.
Zegar uruchamia „Strona i dane” zdarzeniem workflow_dispatch mniej więcej co ODSTEP_MIN minut, ale TYLKO gdy harmonogram stoi
(ostatni przebieg z harmonogramu starszy niż STOI_MIN); gdy harmonogram działa — nic nie robi. Tryby:
  python3 narzedzia/zegar.py zbudz    — (koniec przebiegu „Strona i dane”) harmonogram stoi → uruchom workflow „Zegar zapasowy” (zegar.yml)
  python3 narzedzia/zegar.py prowadz  — (workflow „Zegar zapasowy”) czeka do ODSTEP_MIN od startu ostatniego przebiegu (najwyżej MAX_CZEKAJ s),
                                        sprawdza ponownie i uruchamia „Strona i dane”, chyba że harmonogram ruszył albo inny przebieg czeka lub trwa
Token: GH_TOKEN — token przebiegu GitHub Actions (uprawnienie actions: write); tylko w nagłówku, nigdy w logu. Wyłącznik: ZEGAR_OFF=1.
Zdarzenia workflow_dispatch wywołane tokenem przebiegu tworzą nowe przebiegi (wyjątek od zasady „token przebiegu nie uruchamia workflow”).
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.request

REPO = os.environ.get('GITHUB_REPOSITORY', 'capitalflowai-app/capitalflowai-app.github.io')
API = 'https://api.github.com'
WF_STRONA, WF_ZEGAR = 'strona.yml', 'zegar.yml'
STOI_MIN = 45       # brak przebiegu z harmonogramu dłużej = harmonogram stoi (zwykle co 20 min, opóźnienia GitHub do ~15 min)
ODSTEP_MIN = 20     # docelowy odstęp między przebiegami (jak w harmonogramie)
MAX_CZEKAJ = 17 * 60   # s — zadanie zegara ma limit 20 min
AKTYWNE = ('queued', 'in_progress', 'waiting', 'pending', 'requested')


def czas(s):
    """'2026-10-03T11:05:11Z' → datetime UTC; inne → None."""
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def harmonogram_stoi(runs, now):
    """True, gdy ostatni przebieg „Strona i dane” z harmonogramu (event schedule) jest starszy niż STOI_MIN albo go nie ma."""
    t = [czas(r.get('created_at')) for r in runs if isinstance(r, dict) and r.get('event') == 'schedule']
    t = [x for x in t if x]
    return not t or now - max(t) >= dt.timedelta(minutes=STOI_MIN)


def start_ostatni(runs):
    """Najpóźniejszy start (run_started_at, inaczej created_at) przebiegu „Strona i dane”; brak → None."""
    t = [czas(r.get('run_started_at') or r.get('created_at')) for r in runs if isinstance(r, dict)]
    t = [x for x in t if x]
    return max(t) if t else None


def decyzja(runs, now):
    """Przebiegi „Strona i dane” (API, najnowsze) i chwila → ('nic', powód) | ('czekaj', sekundy) | ('uruchom', powód)."""
    R = [r for r in runs if isinstance(r, dict)]
    if not harmonogram_stoi(R, now):
        return ('nic', 'harmonogram działa')
    if any(r.get('status') in AKTYWNE for r in R):
        return ('nic', 'inny przebieg czeka albo trwa')
    s = start_ostatni(R)
    if s is None:
        return ('uruchom', 'brak przebiegów')
    od = now - s
    if od >= dt.timedelta(minutes=ODSTEP_MIN):
        return ('uruchom', f'ostatni przebieg {int(od.total_seconds() // 60)} min temu, harmonogram stoi')
    return ('czekaj', int((dt.timedelta(minutes=ODSTEP_MIN) - od).total_seconds()) + 5)


def _api(path, token, data=None):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                                          'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'CapitalFlowAI-zegar/1.0',
                                          **({'Content-Type': 'application/json'} if data is not None else {})},
                                 method='POST' if data is not None else 'GET')
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return r.status, (json.loads(body) if body else None)


def przebiegi(token):
    """Ostatnie przebiegi workflow „Strona i dane” (najwyżej 30)."""
    _, j = _api(f'/repos/{REPO}/actions/workflows/{WF_STRONA}/runs?per_page=30', token)
    return (j.get('workflow_runs') or []) if isinstance(j, dict) else []


def uruchom(wf, token):
    st, _ = _api(f'/repos/{REPO}/actions/workflows/{wf}/dispatches', token, {'ref': 'main'})
    return st


def main(argv, now_fn=lambda: dt.datetime.now(dt.timezone.utc), sleep=time.sleep):
    """Kod 2 tylko przy złym trybie; każdy inny wynik (także błąd sieci/API) = 0 — zegar nigdy nie psuje przebiegu strony."""
    try:
        return _main(argv, now_fn, sleep)
    except Exception as e:  # noqa — bez treści wyjątku (mógłby zawierać nagłówki), tylko rodzaj
        print(f'zegar: błąd {type(e).__name__} — bez wpływu na stronę; następna próba przy kolejnym przebiegu')
        return 0


def _main(argv, now_fn, sleep):
    tryb = argv[1] if len(argv) > 1 else ''
    if tryb not in ('zbudz', 'prowadz'):
        print('użycie: zegar.py zbudz|prowadz'); return 2
    if os.environ.get('ZEGAR_OFF', '').strip() == '1':
        print('zegar: wyłączony (ZEGAR_OFF=1)'); return 0
    token = os.environ.get('GH_TOKEN', '').strip()
    if not token:
        print('zegar: brak GH_TOKEN — nic nie robię'); return 0
    runs = przebiegi(token)
    now = now_fn()
    if not harmonogram_stoi(runs, now):
        print('zegar: harmonogram działa — nic nie robię'); return 0
    if tryb == 'zbudz':
        st = uruchom(WF_ZEGAR, token)
        print(f'zegar: harmonogram stoi — uruchomiony zegar zapasowy (HTTP {st})'); return 0
    s = start_ostatni(runs)
    if s is not None:
        czekaj = int(min(MAX_CZEKAJ, max(0, (s + dt.timedelta(minutes=ODSTEP_MIN) - now).total_seconds() + 5)))
        if czekaj:
            print(f'zegar: czekam {czekaj} s (do {ODSTEP_MIN} min od startu ostatniego przebiegu)'); sleep(czekaj)
    runs = przebiegi(token)
    d = decyzja(runs, now_fn())
    if d[0] == 'uruchom':
        st = uruchom(WF_STRONA, token)
        print(f'zegar: {d[1]} — uruchomiony „Strona i dane” (HTTP {st})')
    else:
        print(f'zegar: nic ({d[1]})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
