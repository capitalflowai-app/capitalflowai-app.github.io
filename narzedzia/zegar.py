#!/usr/bin/env python3
"""v145: zapasowy zegar automatu strony. 03.10.2026 harmonogram GitHub (cron) workflow „Strona i dane” przestał uruchamiać przebiegi
po 11:05 UTC (GitHub: „All Systems Operational”, harmonogramy dzienne działały) — dane odświeżały się tylko przy publikacjach.
v145.2 (04.10.2026): zegar jako CZUWANIE po każdym przebiegu. 02:16 UTC harmonogram uruchomił jeden przebieg, zegar uznał „harmonogram działa”
i nie czuwał, a harmonogram znów stanął — od 02:16 do 03:50 bez przebiegu. Teraz każdy przebieg strony na końcu budzi zegar (zawsze), a zegar
czeka do PROGU od startu ostatniego przebiegu i uruchamia następny, gdy w tym czasie nic nie ruszyło:
  próg ODSTEP_MIN (20 min), gdy harmonogram stoi (ostatni przebieg z harmonogramu starszy niż STOI_MIN),
  próg LUZ_MIN (30 min), gdy harmonogram niedawno działał — harmonogram ma 10 min zapasu na swoje opóźnienie, zegar nie dubluje przebiegów.
Tryby:
  python3 narzedzia/zegar.py zbudz    — (koniec przebiegu „Strona i dane”) uruchom workflow „Zegar zapasowy” (zegar.yml); poprzednie czuwanie
                                        anuluje GitHub (concurrency zegar, cancel-in-progress)
  python3 narzedzia/zegar.py prowadz  — (workflow „Zegar zapasowy”) czeka do progu od startu ostatniego przebiegu (najwyżej MAX_CZEKAJ s),
                                        sprawdza ponownie i uruchamia „Strona i dane”, chyba że w międzyczasie ruszył inny przebieg albo czeka/trwa
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
ODSTEP_MIN = 20     # próg czuwania, gdy harmonogram stoi (jak odstęp w harmonogramie)
LUZ_MIN = 30        # v145.2: próg czuwania, gdy harmonogram niedawno działał (10 min zapasu na jego opóźnienie — bez dublowania przebiegów)
MAX_CZEKAJ = 31 * 60   # s — pełny LUZ_MIN + zapas (v145.1: ucięte czekanie zrywało łańcuch); zadanie zegara ma limit 40 min
DOCZEKAJ_S = 120       # v145.1: po czekaniu brakuje najwyżej tylu sekund (różnice zegarów GitHub i maszyny) → doczekaj raz, nie zrywaj łańcucha
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


def prog_min(runs, now):
    """v145.2: próg czuwania w minutach — ODSTEP_MIN, gdy harmonogram stoi, LUZ_MIN, gdy niedawno działał."""
    return ODSTEP_MIN if harmonogram_stoi(runs, now) else LUZ_MIN


def decyzja(runs, now):
    """Przebiegi „Strona i dane” (API, najnowsze) i chwila → ('nic', powód) | ('czekaj', sekundy) | ('uruchom', powód)."""
    R = [r for r in runs if isinstance(r, dict)]
    if any(r.get('status') in AKTYWNE for r in R):
        return ('nic', 'inny przebieg czeka albo trwa')
    s = start_ostatni(R)
    if s is None:
        return ('uruchom', 'brak przebiegów')
    p, od = prog_min(R, now), now - s
    if od >= dt.timedelta(minutes=p):
        return ('uruchom', f'ostatni przebieg {int(od.total_seconds() // 60)} min temu, '
                           + ('harmonogram stoi' if p == ODSTEP_MIN else f'harmonogram nie zdążył w {LUZ_MIN} min'))
    return ('czekaj', int((dt.timedelta(minutes=p) - od).total_seconds()) + 5)


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
    if tryb == 'zbudz':   # v145.2: zawsze — czuwanie po każdym przebiegu (próg zależy od stanu harmonogramu, liczony w trybie prowadz)
        st = uruchom(WF_ZEGAR, token)
        print(f'zegar: czuwanie po przebiegu — uruchomiony zegar zapasowy (HTTP {st})'); return 0
    runs = przebiegi(token)
    now = now_fn()
    s, p = start_ostatni(runs), prog_min(runs, now)
    if s is not None:
        czekaj = int(min(MAX_CZEKAJ, max(0, (s + dt.timedelta(minutes=p) - now).total_seconds() + 5)))
        if czekaj:
            print(f'zegar: czekam {czekaj} s (do {p} min od startu ostatniego przebiegu)'); sleep(czekaj)
    runs = przebiegi(token)
    d = decyzja(runs, now_fn())
    if d[0] == 'czekaj' and d[1] <= DOCZEKAJ_S:   # v145.1: kilka sekund za wcześnie — doczekaj raz i sprawdź ponownie
        print(f'zegar: doczekuję {d[1]} s'); sleep(d[1])
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
