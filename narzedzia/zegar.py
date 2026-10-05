#!/usr/bin/env python3
"""v145: zapasowy zegar automatu strony. 03.10.2026 harmonogram GitHub (cron) workflow „Strona i dane” przestał uruchamiać przebiegi
po 11:05 UTC (GitHub: „All Systems Operational”, harmonogramy dzienne działały) — dane odświeżały się tylko przy publikacjach.
v145.2 (04.10.2026): zegar jako CZUWANIE po każdym przebiegu. 02:16 UTC harmonogram uruchomił jeden przebieg, zegar uznał „harmonogram działa”
i nie czuwał, a harmonogram znów stanął — od 02:16 do 03:50 bez przebiegu. Teraz każdy przebieg strony na końcu budzi zegar (zawsze), a zegar
czeka do PROGU od startu ostatniego przebiegu i uruchamia następny, gdy w tym czasie nic nie ruszyło:
  próg ODSTEP_MIN (20 min), gdy harmonogram stoi (ostatni przebieg z harmonogramu starszy niż STOI_MIN),
  próg LUZ_MIN (30 min), gdy harmonogram niedawno działał — harmonogram ma 10 min zapasu na swoje opóźnienie, zegar nie dubluje przebiegów.
v171 (05.10.2026): harmonogram co 10 min (v168), ale GitHub uruchamia tylko część terminów — 05.10 05:46–07:59 UTC 6 z ok. 13 (odstępy 16–27 min),
a zegar wkraczał dopiero po 30 min ciszy. Progi przestawione na rytm 10 min: LUZ_MIN 15 (5 min zapasu na opóźnienie harmonogramu), ODSTEP_MIN 10,
STOI_MIN 25, czekanie najwyżej 16 min.
v159 (04.10.2026): harmonogram GitHub nie uruchomił też kontroli dziennej (27.09–03.10 ruszała 06:37–06:49 UTC; 04.10 wcale), a archiwum
ruszyło o 04:01 zamiast 01:20. Na początku każdego czuwania krótki tryb `dzienne` uruchamia zadanie dzienne, gdy minął jego termin + zapas,
a dziś nie powstał żaden jego przebieg (DZIENNE; wyłącznik ZEGAR_DZIENNE_OFF=1). Oba zadania są idempotentne (ten sam dzień nadpisywany).
Tryby:
  python3 narzedzia/zegar.py zbudz    — (koniec przebiegu „Strona i dane”) uruchom workflow „Zegar zapasowy” (zegar.yml); poprzednie czuwanie
                                        anuluje GitHub (concurrency zegar, cancel-in-progress)
  python3 narzedzia/zegar.py dzienne  — (v159, workflow „Zegar zapasowy”, przed prowadz) kontrola i archiwum dzienne, gdy ich harmonogram nie ruszył
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
STOI_MIN = 25       # v171: brak przebiegu z harmonogramu dłużej = harmonogram stoi (co 10 min, opóźnienia GitHub do ~15 min); było 45
ODSTEP_MIN = 10     # v171: próg czuwania, gdy harmonogram stoi (jak odstęp w harmonogramie); było 20
LUZ_MIN = 15        # v145.2 / v171: próg czuwania, gdy harmonogram niedawno działał (5 min zapasu na jego opóźnienie — bez dublowania); było 30
MAX_CZEKAJ = 16 * 60   # s — pełny LUZ_MIN + zapas (v145.1: ucięte czekanie zrywało łańcuch); zadanie zegara ma limit 40 min; było 31 min
DOCZEKAJ_S = 120       # v145.1: po czekaniu brakuje najwyżej tylu sekund (różnice zegarów GitHub i maszyny) → doczekaj raz, nie zrywaj łańcucha
AKTYWNE = ('queued', 'in_progress', 'waiting', 'pending', 'requested')
# v159: zadania dzienne pilnowane przez zegar — (plik workflow, nazwa w logu, godzina UTC, minuta, zapas w min) zgodne z ich cron (test pilnuje).
# Zapas = typowe spóźnienie harmonogramu GitHub + margines: kontrola 06:20 → 07:30 UTC, archiwum 01:20 → 03:00 UTC.
DZIENNE = (('kontrola.yml', 'kontrola dzienna', 6, 20, 70), ('archiwum.yml', 'archiwum dzienne', 1, 20, 100))
DZIENNE_OD_MIN = 20   # przebieg „z dziś” = utworzony najwcześniej tyle minut przed terminem (wcześniejszy push to nie dzisiejsze zadanie)


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


def dzienne_decyzja(runs, now, godz, minuta, zapas):
    """v159: przebiegi zadania dziennego (API, najnowsze) i chwila → ('nic', powód) | ('uruchom', powód). Uruchom, gdy minął dzisiejszy termin
    + zapas, żaden przebieg nie czeka ani nie trwa, a od DZIENNE_OD_MIN min przed terminem nie powstał żaden przebieg (z harmonogramu, ręczny,
    z zegara, push). Tylko bieżąca doba UTC — wczorajszego zadania po północy nie nadrabia (dzisiejsze i tak przyjdzie)."""
    termin = now.replace(hour=godz, minute=minuta, second=0, microsecond=0)
    gr = termin + dt.timedelta(minutes=zapas)
    if now < gr:
        return ('nic', 'przed terminem z zapasem')
    R = [r for r in runs if isinstance(r, dict)]
    if any(r.get('status') in AKTYWNE for r in R):
        return ('nic', 'przebieg czeka albo trwa')
    od = termin - dt.timedelta(minutes=DZIENNE_OD_MIN)
    if any(t is not None and t >= od for t in (czas(r.get('created_at')) for r in R)):
        return ('nic', 'dziś już był')
    return ('uruchom', f'harmonogram nie uruchomił go do {gr:%H:%M} UTC')


def przebiegi_wf(wf, token, n=10):
    """v159: ostatnie przebiegi dowolnego workflow (najwyżej n)."""
    _, j = _api(f'/repos/{REPO}/actions/workflows/{wf}/runs?per_page={n}', token)
    return (j.get('workflow_runs') or []) if isinstance(j, dict) else []


def _dzienne(token, now):
    """v159: każde zadanie osobno — błąd jednego (sieć, API) nie blokuje drugiego; w logu tylko rodzaj błędu."""
    for wf, nazwa, godz, minuta, zapas in DZIENNE:
        try:
            d = dzienne_decyzja(przebiegi_wf(wf, token), now, godz, minuta, zapas)
            if d[0] == 'uruchom':
                st = uruchom(wf, token)
                print(f'zegar: {nazwa}: {d[1]} — uruchamiam (HTTP {st})')
            else:
                print(f'zegar: {nazwa}: nic ({d[1]})')
        except Exception as e:  # noqa — bez treści wyjątku (mogłaby zawierać nagłówki), tylko rodzaj
            print(f'zegar: {nazwa}: błąd {type(e).__name__} — następna próba przy kolejnym czuwaniu')
    return 0


def main(argv, now_fn=lambda: dt.datetime.now(dt.timezone.utc), sleep=time.sleep):
    """Kod 2 tylko przy złym trybie; każdy inny wynik (także błąd sieci/API) = 0 — zegar nigdy nie psuje przebiegu strony."""
    try:
        return _main(argv, now_fn, sleep)
    except Exception as e:  # noqa — bez treści wyjątku (mógłby zawierać nagłówki), tylko rodzaj
        print(f'zegar: błąd {type(e).__name__} — bez wpływu na stronę; następna próba przy kolejnym przebiegu')
        return 0


def _main(argv, now_fn, sleep):
    tryb = argv[1] if len(argv) > 1 else ''
    if tryb not in ('zbudz', 'prowadz', 'dzienne'):
        print('użycie: zegar.py zbudz|prowadz|dzienne'); return 2
    if os.environ.get('ZEGAR_OFF', '').strip() == '1':
        print('zegar: wyłączony (ZEGAR_OFF=1)'); return 0
    if tryb == 'dzienne' and os.environ.get('ZEGAR_DZIENNE_OFF', '').strip() == '1':
        print('zegar: zadania dzienne wyłączone (ZEGAR_DZIENNE_OFF=1)'); return 0
    token = os.environ.get('GH_TOKEN', '').strip()
    if not token:
        print('zegar: brak GH_TOKEN — nic nie robię'); return 0
    if tryb == 'dzienne':   # v159: krótko, bez czekania — przed czuwaniem „Strona i dane”
        return _dzienne(token, now_fn())
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
