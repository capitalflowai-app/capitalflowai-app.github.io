#!/usr/bin/env python3
"""v354 (13.10.2026): STRAŻNIK harmonogramów — raz w tygodniu pilnuje, żeby automat w GitHub nigdy nie stanął sam.
GitHub wyłącza zaplanowane przepływy w publicznym repozytorium po 60 dniach bez aktywności (commitu) — wtedy strona przestaje się odświeżać
bez niczyjej wiedzy. Strażnik (workflow `straznik.yml`, poniedziałek ok. 04:41 UTC) robi dwie rzeczy:
  1. `sprawdz` — pyta API GitHuba o przepływy; każdy z ZAPLANOWANE w stanie `disabled_inactivity` włącza z powrotem (PUT .../enable).
     Przepływ wyłączony RĘCZNIE (`disabled_manually`) jest świadomą decyzją właściciela — tylko zgłaszany w logu; włączany dopiero, gdy zmienna
     repozytorium STRAZNIK_RECZNIE=1. Sprawdza też wiek ostatniego commitu na głównej gałęzi: starszy niż PROG_COMMIT_DNI (30) = potrzebny
     commit aktywności (wynik `aktywnosc=tak` dla drugiego zadania przepływu).
  2. `zapisz` — (drugie zadanie, osobne uprawnienie contents: write) zapisuje malutki plik kontrola/straznik.json; commit z [skip ci].
Token: GH_TOKEN = token przebiegu (GITHUB_TOKEN; zadanie 1: actions: write + contents: read, zadanie 2: contents: write), tylko w nagłówku, nigdy w logu.
Bez sekretów właściciela. Wyłącznik: zmienna repozytorium STRAZNIK_OFF=1. Kod wyjścia 1 = coś nie dało się naprawić (GitHub wyśle e-mail
o nieudanym przebiegu); 2 = zły tryb. Python 3.12, sama biblioteka standardowa."""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

REPO = os.environ.get('GITHUB_REPOSITORY', 'capitalflowai-app/capitalflowai-app.github.io')
API = 'https://api.github.com'
# przepływy z harmonogramem (cron), które muszą działać same; sondy (jednorazowe, tylko ręcznie) nie wchodzą — test pilnuje zgodności z plikami
ZAPLANOWANE = ('strona.yml', 'zegar.yml', 'kontrola.yml', 'archiwum.yml', 'straznik.yml', 'raport-ai.yml')   # v482: raport tygodniowy AI
PROG_COMMIT_DNI = 30                       # commit aktywności, gdy ostatni commit jest starszy (limit GitHuba: 60 dni)
WLACZ_ZAWSZE = ('disabled_inactivity',)    # GitHub wyłączył z powodu braku aktywności
WLACZ_RECZNIE = ('disabled_manually',)     # wyłączony ręcznie — tylko przy STRAZNIK_RECZNIE=1
PLIK_AKTYWNOSCI = os.path.join('kontrola', 'straznik.json')


def czas(s):
    """'2026-10-13T06:51:12Z' → datetime UTC; inne → None."""
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _api(metoda, sciezka, token, dane=None):
    """Zapytanie do API GitHuba; PUT bez treści wysyła pustą treść (Content-Length: 0). Zwraca (kod, JSON albo None)."""
    cialo = None if dane is None else (dane if isinstance(dane, bytes) else json.dumps(dane).encode())
    req = urllib.request.Request(API + sciezka, data=cialo, method=metoda,
                                 headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                                          'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'CapitalFlowAI-straznik/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
        return r.status, (json.loads(body) if body else None)


def nazwa_pliku(w):
    return os.path.basename(str((w or {}).get('path') or '')) if isinstance(w, dict) else ''


def do_wlaczenia(lista, recznie=False):
    """Lista przepływów z API → [(id, plik, stan)] do włączenia: tylko z ZAPLANOWANE, stan disabled_inactivity (zawsze) albo disabled_manually (recznie)."""
    out = []
    for w in lista if isinstance(lista, list) else []:
        if not isinstance(w, dict):
            continue
        nazwa, stan, i = nazwa_pliku(w), w.get('state'), w.get('id')
        if nazwa in ZAPLANOWANE and isinstance(i, int) and not isinstance(i, bool) \
                and (stan in WLACZ_ZAWSZE or (recznie and stan in WLACZ_RECZNIE)):
            out.append((i, nazwa, stan))
    return out


def wylaczone_recznie(lista, recznie=False):
    """Pliki z ZAPLANOWANE wyłączone ręcznie i NIE włączane (do zgłoszenia w logu)."""
    if recznie:
        return []
    return [nazwa_pliku(w) for w in lista if isinstance(w, dict) and nazwa_pliku(w) in ZAPLANOWANE and w.get('state') in WLACZ_RECZNIE]


def dni_bez_commita(iso, now):
    """Pełne dni od commitu (iso) do chwili `now`; nieczytelna data → None."""
    t = czas(iso)
    return None if t is None else max(0, (now - t).days)


def potrzebny_commit(dni):
    """True, gdy ostatni commit jest starszy niż PROG_COMMIT_DNI dni."""
    return dni is not None and dni > PROG_COMMIT_DNI


def sprawdz(token, now, recznie=False, api=_api):
    """Włącza wyłączone przepływy i ocenia wiek ostatniego commitu. Każda część osobno — błąd jednej nie blokuje drugiej.
    Zwraca {'wlaczone': [pliki], 'reczne': [pliki], 'bledy': [opisy], 'dni': int|None, 'aktywnosc': bool}. W opisach błędów tylko rodzaj (bez treści wyjątku)."""
    w = {'wlaczone': [], 'reczne': [], 'bledy': [], 'dni': None, 'aktywnosc': False}

    def rodzaj(e):
        return f'HTTP {e.code}' if isinstance(e, urllib.error.HTTPError) else type(e).__name__
    try:
        _, j = api('GET', f'/repos/{REPO}/actions/workflows?per_page=100', token)
        lista = (j.get('workflows') or []) if isinstance(j, dict) else []
        w['reczne'] = wylaczone_recznie(lista, recznie)
        for i, nazwa, stan in do_wlaczenia(lista, recznie):
            try:
                st, _ = api('PUT', f'/repos/{REPO}/actions/workflows/{i}/enable', token, b'')
                if st in (200, 204):
                    w['wlaczone'].append(nazwa)
                else:
                    w['bledy'].append(f'{nazwa}: włączenie — HTTP {st}')
            except Exception as e:  # noqa — bez treści wyjątku (mogłaby zawierać nagłówki)
                w['bledy'].append(f'{nazwa}: włączenie nieudane ({rodzaj(e)})')
    except Exception as e:  # noqa
        w['bledy'].append(f'lista przepływów nieczytelna ({rodzaj(e)})')
    try:
        _, j = api('GET', f'/repos/{REPO}/commits?per_page=1', token)
        c = (j[0].get('commit') or {}) if isinstance(j, list) and j and isinstance(j[0], dict) else {}
        iso = (c.get('committer') or {}).get('date') or (c.get('author') or {}).get('date')
        w['dni'] = dni_bez_commita(iso, now)
        if w['dni'] is None:
            w['bledy'].append('ostatni commit — brak daty')
        w['aktywnosc'] = potrzebny_commit(w['dni'])
    except Exception as e:  # noqa
        w['bledy'].append(f'ostatni commit nieczytelny ({rodzaj(e)})')
    return w


def zapisz_plik(sciezka, now, dni=None):
    """Malutki plik aktywności (zawsze inna treść = prawdziwy commit)."""
    os.makedirs(os.path.dirname(sciezka) or '.', exist_ok=True)
    tresc = {'at': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
             'powod': f'ostatni commit w repozytorium starszy niż {PROG_COMMIT_DNI} dni — commit aktywności strażnika (GitHub wyłącza harmonogramy po 60 dniach bez aktywności)'}
    if dni is not None:
        tresc['dni_bez_commita'] = dni
    with open(sciezka, 'w', encoding='utf-8') as f:
        json.dump(tresc, f, ensure_ascii=False, indent=1)
        f.write('\n')


def _wyjscie(env, **kv):
    """Dopisuje wyniki do pliku GITHUB_OUTPUT (gdy jest)."""
    p = env.get('GITHUB_OUTPUT')
    if p:
        with open(p, 'a', encoding='utf-8') as f:
            for k, v in kv.items():
                f.write(f'{k}={v}\n')


def main(argv, now_fn=lambda: dt.datetime.now(dt.timezone.utc), env=None, api=_api):
    env = os.environ if env is None else env
    tryb = argv[1] if len(argv) > 1 else ''
    if tryb not in ('sprawdz', 'zapisz'):
        print('użycie: straznik.py sprawdz|zapisz'); return 2
    if env.get('STRAZNIK_OFF', '').strip() == '1':
        print('strażnik: wyłączony (STRAZNIK_OFF=1)'); _wyjscie(env, aktywnosc='nie', dni=''); return 0
    now = now_fn()
    if tryb == 'zapisz':
        d = env.get('STRAZNIK_DNI', '').strip()
        zapisz_plik(PLIK_AKTYWNOSCI, now, int(d) if d.isdigit() else None)
        print(f'strażnik: zapisano {PLIK_AKTYWNOSCI}'); return 0
    token = env.get('GH_TOKEN', '').strip()
    if not token:
        print('strażnik: brak GH_TOKEN — nic nie zrobiłem'); _wyjscie(env, aktywnosc='nie', dni=''); return 1
    w = sprawdz(token, now, env.get('STRAZNIK_RECZNIE', '').strip() == '1', api)
    print('strażnik: włączone ponownie: ' + (', '.join(w['wlaczone']) or 'żaden (wszystkie czynne)'))
    if w['reczne']:
        print('strażnik: wyłączone RĘCZNIE (zostawione): ' + ', '.join(w['reczne']) + ' — włącz w zakładce Actions albo ustaw zmienną STRAZNIK_RECZNIE=1')
    print('strażnik: dni od ostatniego commitu: ' + ('—' if w['dni'] is None else str(w['dni']))
          + (f' — próg {PROG_COMMIT_DNI}, robię commit aktywności' if w['aktywnosc'] else f' (próg {PROG_COMMIT_DNI})'))
    for b in w['bledy']:
        print('strażnik: BŁĄD: ' + b)
    _wyjscie(env, aktywnosc='tak' if w['aktywnosc'] else 'nie', dni='' if w['dni'] is None else w['dni'])
    return 1 if w['bledy'] else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
