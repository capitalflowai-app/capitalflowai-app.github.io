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
  python3 narzedzia/zegar.py odblokuj — (v232, workflow „Zegar zapasowy”, przed prowadz) anuluje przebieg „Strona i dane” zawieszony w stanie
                                        waiting (zadanie „opublikuj” czeka na środowisko, choć nic nie wymaga zatwierdzenia — 06.10.2026 od 08:47
                                        UTC trzymało grupę „pages” i blokowało każdą publikację); zatwierdzenia przez osobę nie rusza nigdy
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
import urllib.error
import urllib.parse
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
# v232 (06.10.2026): zadanie „opublikuj” stało ponad godzinę w stanie waiting (środowisko github-pages bez wymogu zatwierdzenia) i trzymało
# grupę „pages” — każdy następny przebieg czekał. Tryb `odblokuj` anuluje taki przebieg; zatwierdzenia przez osobę nie rusza nigdy.
ZAWIESZONY_MIN = 15         # v232: waiting tak długo (od updated_at), a nic nie czeka na osobę ani na licznik czasu = zawieszony (zwykle przejście trwa sekundy)
ZAWIESZONY_PUSTY_MIN = 60   # v232: waiting bez żadnego oczekującego wdrożenia (pusta lista) — dłuższa cierpliwość
ODBLOKUJ_MAX = 5            # v232: najwyżej tyle przebiegów sprawdzanych w jednym czuwaniu
SRODOWISKO_REGULY_OK = ('branch_policy', 'wait_timer')   # v235: tylko takie reguły środowiska — recenzent, reguła aplikacji, nieznana = nie anulować
ODBLOKUJ_CZEKAJ_S, ODBLOKUJ_KROK_S = 60, 5   # v235: po anulowaniu czekaj, aż GitHub zamknie przebieg (najwyżej tyle sekund, co tyle)


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


def zawieszony(run, pend, now):
    """v232: przebieg (API) i jego oczekujące wdrożenia (lista z /pending_deployments) → powód anulowania albo None (nie ruszać).
    Zawieszony = status 'waiting' od ≥ ZAWIESZONY_MIN min (updated_at), a żadne wdrożenie nie czeka na osobę (reviewers) ani na licznik czasu
    środowiska, który jeszcze biegnie (wait_timer); pusta lista — dopiero po ZAWIESZONY_PUSTY_MIN min. Zła data albo nieznany kształt = None."""
    if not isinstance(run, dict) or run.get('status') != 'waiting' or not isinstance(pend, list):
        return None
    t = czas(run.get('updated_at'))
    if t is None:
        return None
    od = (now - t).total_seconds() / 60
    if not pend:
        return f'czeka {int(od)} min bez oczekującego wdrożenia' if od >= ZAWIESZONY_PUSTY_MIN else None
    if od < ZAWIESZONY_MIN:
        return None
    for p in pend:
        if not isinstance(p, dict) or p.get('reviewers'):
            return None                                   # ktoś ma zatwierdzić — to nie usterka
        w = p.get('wait_timer') or 0
        if not isinstance(w, (int, float)) or isinstance(w, bool) or w < 0:
            return None
        if w:
            s = czas(p.get('wait_timer_started_at'))
            if s is None or now < s + dt.timedelta(minutes=w):
                return None                               # licznik czasu środowiska jeszcze biegnie
    return f'czeka {int(od)} min na wdrożenie, którego nikt nie musi zatwierdzać'


def srodowisko_ok(env, wlasne):
    """v235: środowisko (GET /environments/{nazwa}) i jego reguły aplikacji (GET …/deployment_protection_rules) → True, gdy wolno anulować:
    same reguły z SRODOWISKO_REGULY_OK i żadnej reguły aplikacji (ich zatwierdzeń nie widać w reviewers ani wait_timer); nieznany kształt = False."""
    if not isinstance(env, dict) or not isinstance(env.get('protection_rules'), list) or not isinstance(wlasne, dict):
        return False
    if any(not isinstance(r, dict) or r.get('type') not in SRODOWISKO_REGULY_OK for r in env['protection_rules']):
        return False
    n = wlasne.get('total_count')
    return isinstance(n, int) and not isinstance(n, bool) and n == 0


def czekaj_koniec(rid, token, sleep):
    """v235: po anulowaniu czekaj (najwyżej ODBLOKUJ_CZEKAJ_S), aż GitHub zamknie przebieg — inaczej czuwanie chwilę później widzi go jako
    aktywny („nic”), a po force-cancel zadanie zegara tego przebiegu się nie wykona (łańcuch czuwania mógłby stanąć). True = zamknięty."""
    for _ in range(ODBLOKUJ_CZEKAJ_S // ODBLOKUJ_KROK_S):
        _, j = _api(f'/repos/{REPO}/actions/runs/{rid}', token)
        if isinstance(j, dict) and j.get('status') == 'completed':
            return True
        sleep(ODBLOKUJ_KROK_S)
    return False


def anuluj(rid, token):
    """v232: anuluj przebieg; GitHub odmawia (409) — force-cancel. Zwraca kod HTTP."""
    try:
        st, _ = _api(f'/repos/{REPO}/actions/runs/{rid}/cancel', token, {})
        return st
    except urllib.error.HTTPError as e:
        if e.code != 409:
            raise
    st, _ = _api(f'/repos/{REPO}/actions/runs/{rid}/force-cancel', token, {})
    return st


def _odblokuj(token, now, sleep=time.sleep):
    """v232: zawieszone przebiegi „Strona i dane” → anuluj; każdy osobno (błąd jednego nie blokuje drugiego); w logu tylko rodzaj błędu."""
    _, j = _api(f'/repos/{REPO}/actions/workflows/{WF_STRONA}/runs?status=waiting&per_page=10', token)
    runs = [r for r in ((j.get('workflow_runs') or []) if isinstance(j, dict) else []) if isinstance(r, dict) and r.get('status') == 'waiting']
    if not runs:
        print('zegar: odblokuj: żaden przebieg nie czeka'); return 0
    for r in runs[:ODBLOKUJ_MAX]:
        rid = r.get('id')
        if not isinstance(rid, int) or isinstance(rid, bool):
            continue
        try:
            _, pend = _api(f'/repos/{REPO}/actions/runs/{rid}/pending_deployments', token)
            powod = zawieszony(r, pend, now)
            if powod is None:
                print(f'zegar: odblokuj: przebieg {rid} czeka — jeszcze nie zawieszony albo czeka na zatwierdzenie'); continue
            nazwy = sorted({p['environment']['name'] for p in pend if isinstance(p, dict) and isinstance(p.get('environment'), dict)
                            and isinstance(p['environment'].get('name'), str) and p['environment']['name']}) or ['github-pages']   # v239: każde
            zle = any(not (isinstance(p, dict) and isinstance(p.get('environment'), dict) and isinstance(p['environment'].get('name'), str)
                           and p['environment']['name']) for p in pend)   # v242: wdrożenie bez nazwy środowiska — nieznany kształt, nie anulować
            for nazwa in nazwy:
                q = urllib.parse.quote(nazwa, safe='')
                _, env = _api(f'/repos/{REPO}/environments/{q}', token)
                _, wl = _api(f'/repos/{REPO}/environments/{q}/deployment_protection_rules', token)
                zle = zle or not srodowisko_ok(env, wl)   # v235: recenzent, reguła aplikacji albo nieznana reguła — zatwierdzenie należy do właściciela
            if zle:
                print(f'zegar: odblokuj: przebieg {rid} {powod}, ale środowisko ma regułę inną niż gałąź i licznik czasu — nie anuluję'); continue
            st = anuluj(rid, token)
            print(f'zegar: odblokuj: przebieg {rid} {powod} — anulowany (HTTP {st}); następny przebieg ruszy sam')   # v239: zaraz po anulowaniu
            try:
                zam = czekaj_koniec(rid, token, sleep)   # v235
            except Exception as e2:  # noqa — tylko rodzaj błędu
                print(f'zegar: odblokuj: przebieg {rid}: stanu po anulowaniu nie odczytano ({type(e2).__name__})'); continue
            print(f'zegar: odblokuj: przebieg {rid} — ' + ('GitHub go zamknął' if zam else 'GitHub jeszcze go zamyka'))
        except Exception as e:  # noqa — bez treści wyjątku (mogłaby zawierać nagłówki), tylko rodzaj
            print(f'zegar: odblokuj: przebieg {rid}: błąd {type(e).__name__} — następna próba przy kolejnym czuwaniu')
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
    if tryb not in ('zbudz', 'prowadz', 'dzienne', 'odblokuj'):
        print('użycie: zegar.py zbudz|prowadz|dzienne|odblokuj'); return 2
    if os.environ.get('ZEGAR_OFF', '').strip() == '1':
        print('zegar: wyłączony (ZEGAR_OFF=1)'); return 0
    if tryb == 'dzienne' and os.environ.get('ZEGAR_DZIENNE_OFF', '').strip() == '1':
        print('zegar: zadania dzienne wyłączone (ZEGAR_DZIENNE_OFF=1)'); return 0
    token = os.environ.get('GH_TOKEN', '').strip()
    if not token:
        print('zegar: brak GH_TOKEN — nic nie robię'); return 0
    if tryb == 'dzienne':   # v159: krótko, bez czekania — przed czuwaniem „Strona i dane”
        return _dzienne(token, now_fn())
    if tryb == 'odblokuj':   # v232: krótko, bez czekania — przed czuwaniem (zawieszony przebieg trzyma grupę „pages”)
        return _odblokuj(token, now_fn(), sleep)
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
