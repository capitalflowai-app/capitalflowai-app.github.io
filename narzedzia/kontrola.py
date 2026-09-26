#!/usr/bin/env python3
"""Codzienna kontrola strony — uruchamiana w GitHub Actions (ma dostęp do sieci), nie w chmurze Claude (tam brak dostępu do strony).
Sprawdza: stronę główną, plik stanu automatu (meta.json: wiek, błędy, źródła bez odpowiedzi), wiek plików danych, przebiegi Actions z 24 h.
Zapisuje `kontrola/ostatnia.md` (po polsku, krótko) i `kontrola/ostatnia.json`; wynik trafia też do podsumowania przebiegu.
Kod wyjścia 1 = BŁĄD (GitHub wysyła właścicielowi e-mail o nieudanym przebiegu). Bez kluczy, tylko odczyt. Python 3.12, sama biblioteka standardowa."""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

SITE = os.environ.get('SITE_URL', 'https://capitalflowai-app.github.io').rstrip('/')
REPO = os.environ.get('GITHUB_REPOSITORY', 'capitalflowai-app/capitalflowai-app.github.io')
TOKEN = os.environ.get('GITHUB_TOKEN', '')          # tylko do odczytu listy przebiegów (API publiczne działa też bez niego)
OUT_DIR = os.environ.get('KONTROLA_DIR', 'kontrola')
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
PLIKI = ['meta', 'etf', 'trendy', 'oecd', 'rynki', 'dzwignia', 'wieloryby', 'energia', 'usa-makro', 'bilans-usa', 'krypto', 'instytucje', 'tic', 'cm']
LIMIT_MIN = {'meta': 90, 'etf': 180, 'trendy': 180, 'oecd': 24 * 60, 'rynki': 180, 'dzwignia': 180, 'wieloryby': 90, 'energia': 24 * 60,
             'usa-makro': 24 * 60, 'bilans-usa': 48 * 60, 'krypto': 180, 'instytucje': 180, 'tic': 48 * 60, 'cm': 180}


def get(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalFlowAI-kontrola/1.0', **(headers or {})})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        return r.status, body, int((time.monotonic() - t0) * 1000)


def wiek_min(iso):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return max(0, int((NOW - t).total_seconds() // 60))
    except Exception:
        return None


def czas_pl(iso):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00')).astimezone(dt.timezone(dt.timedelta(hours=2)))   # czas polski (letni)
        return t.strftime('%d.%m.%Y, %H:%M')
    except Exception:
        return '—'


def kontrola():
    R = {'at': NOW.isoformat(), 'strona': {}, 'meta': {}, 'pliki': {}, 'actions': {}, 'uwagi': [], 'bledy': []}
    # 1. strona główna
    try:
        st, body, ms = get(f'{SITE}/index.html?nc={int(time.time())}')
        ok = st == 200 and len(body) > 1_000_000 and b'const EXTRA' in body
        R['strona'] = {'http': st, 'bajty': len(body), 'ms': ms, 'ok': ok}
        if not ok:
            R['bledy'].append(f'strona główna: HTTP {st}, {len(body)} B')
    except Exception as e:  # noqa
        R['strona'] = {'ok': False, 'blad': str(e)[:200]}
        R['bledy'].append(f'strona główna nie odpowiada: {str(e)[:120]}')
    # 2. plik stanu automatu
    try:
        st, body, ms = get(f'{SITE}/data/meta.json?nc={int(time.time())}')
        m = json.loads(body)
        w = wiek_min(m.get('at'))
        nie = sorted(k for k, v in (m.get('ok') or {}).items() if v is False)
        R['meta'] = {'at': m.get('at'), 'wiek_min': w, 'zrodla': len(m.get('ok') or {}), 'bez_odpowiedzi': nie,
                     'errors': [str(x)[:160] for x in (m.get('errors') or [])], 'notes': [str(x)[:160] for x in (m.get('notes') or [])]}
        if w is None:
            R['bledy'].append('plik stanu bez czasu przebiegu')
        elif w > 180:
            R['bledy'].append(f'automat nie odświeżył danych od {w // 60} godz. (ostatni przebieg {czas_pl(m.get("at"))})')
        elif w > LIMIT_MIN['meta']:
            R['uwagi'].append(f'ostatni przebieg automatu sprzed {w} min (zwykle co 20 min)')
        if nie:
            R['uwagi'].append('źródła bez odpowiedzi w ostatnim przebiegu: ' + ', '.join(nie))
        for e in R['meta']['errors']:
            R['uwagi'].append('błąd zbieracza: ' + e)
    except Exception as e:  # noqa
        R['meta'] = {'blad': str(e)[:200]}
        R['bledy'].append(f'plik stanu (meta.json) nie odpowiada: {str(e)[:120]}')
    # 3. wiek plików danych
    for n in PLIKI:
        if n == 'meta':
            continue
        try:
            st, body, ms = get(f'{SITE}/data/{n}.json?nc={int(time.time())}')
            j = json.loads(body)
            w = wiek_min(j.get('at')) if isinstance(j, dict) else None
            okp = j.get('ok') if isinstance(j, dict) else None
            nie = sorted(k for k, v in okp.items() if v is False) if isinstance(okp, dict) else []
            R['pliki'][n] = {'http': st, 'bajty': len(body), 'wiek_min': w, 'czesci_bez_odpowiedzi': nie}
            if w is not None and w > LIMIT_MIN.get(n, 24 * 60):
                R['uwagi'].append(f'{n}.json sprzed {w // 60} godz. {w % 60} min (limit {LIMIT_MIN.get(n, 1440) // 60} godz.)')
            if nie:
                R['uwagi'].append(f'{n}.json: części bez odpowiedzi: ' + ', '.join(nie))
        except urllib.error.HTTPError as e:
            R['pliki'][n] = {'http': e.code}
            if n in ('etf', 'trendy', 'oecd', 'rynki'):
                R['uwagi'].append(f'{n}.json: HTTP {e.code}')
            elif n != 'indeksy':
                R['uwagi'].append(f'{n}.json: HTTP {e.code} (brak pliku)')
        except Exception as e:  # noqa
            R['pliki'][n] = {'blad': str(e)[:160]}
            R['uwagi'].append(f'{n}.json: {str(e)[:100]}')
    # 4. przebiegi Actions z ostatnich 24 h (API publiczne; token tylko podnosi limit zapytań)
    try:
        hdr = {'Accept': 'application/vnd.github+json'}
        if TOKEN:
            hdr['Authorization'] = 'Bearer ' + TOKEN
        st, body, ms = get(f'https://api.github.com/repos/{REPO}/actions/runs?per_page=100', headers=hdr)
        runs = json.loads(body).get('workflow_runs', [])
        od = NOW - dt.timedelta(hours=24)
        ost = [r for r in runs if r.get('name', '').startswith('Strona') and wiek_min(r.get('run_started_at')) is not None
               and dt.datetime.fromisoformat(r['run_started_at'].replace('Z', '+00:00')) >= od]
        z = {}
        for r in ost:
            z[r.get('conclusion') or r.get('status')] = z.get(r.get('conclusion') or r.get('status'), 0) + 1
        R['actions'] = {'przebiegi_24h': len(ost), 'wg_wyniku': z,
                        'ostatni': (ost[0]['run_started_at'] if ost else None), 'ostatnia_porazka': next((r['run_started_at'] for r in ost if r.get('conclusion') == 'failure'), None)}
        if z.get('failure', 0) >= 3:
            R['bledy'].append(f'{z["failure"]} nieudanych przebiegów automatu w 24 h')
        elif z.get('failure', 0):
            R['uwagi'].append(f'{z["failure"]} nieudany przebieg automatu w 24 h (ostatni: {czas_pl(R["actions"]["ostatnia_porazka"])})')
        if len(ost) < 20:
            R['uwagi'].append(f'tylko {len(ost)} przebiegów w 24 h (harmonogram co 20 min ≈ 72; GitHub bywa opóźniony)')
    except Exception as e:  # noqa
        R['actions'] = {'blad': str(e)[:160]}
        R['uwagi'].append('nie udało się odczytać listy przebiegów Actions: ' + str(e)[:100])
    R['wynik'] = 'BŁĄD' if R['bledy'] else ('UWAGA' if R['uwagi'] else 'OK')
    return R


def raport_md(R):
    m = R.get('meta') or {}
    L = [f'# Kontrola strony — {czas_pl(R["at"])} (czas polski)', '',
         f'**Wynik: {R["wynik"]}**', '',
         f'- Strona główna: {"działa" if (R.get("strona") or {}).get("ok") else "PROBLEM"} (HTTP {(R.get("strona") or {}).get("http", "—")}, {(R.get("strona") or {}).get("ms", "—")} ms).',
         f'- Ostatni przebieg automatu: {czas_pl(m.get("at"))} — {("sprzed " + str(m.get("wiek_min")) + " min") if m.get("wiek_min") is not None else "brak"}; '
         f'źródeł: {m.get("zrodla", "—")}, bez odpowiedzi: {", ".join(m.get("bez_odpowiedzi") or []) or "żadne"}; błędów zbieracza: {len(m.get("errors") or [])}.']
    a = R.get('actions') or {}
    if 'przebiegi_24h' in a:
        L.append(f'- Przebiegi Actions w 24 h: {a["przebiegi_24h"]} ({", ".join(f"{k}: {v}" for k, v in a["wg_wyniku"].items()) or "—"}).')
    L.append('- Pliki danych (wiek): ' + ', '.join(f'{n} {("%dh%02d" % divmod(p["wiek_min"], 60)) if p.get("wiek_min") is not None else ("HTTP " + str(p.get("http", "?")))}'
                                             for n, p in (R.get('pliki') or {}).items()) + '.')
    if m.get('notes'):
        L.append('- Notatki automatu: ' + ' · '.join(m['notes']) + '.')
    if R['bledy']:
        L += ['', '## Błędy (wymagają uwagi)'] + [f'- {x}' for x in R['bledy']]
    if R['uwagi']:
        L += ['', '## Uwagi'] + [f'- {x}' for x in R['uwagi']]
    if not R['bledy'] and not R['uwagi']:
        L += ['', 'Wszystko w normie.']
    L += ['', 'Kontrola wykonana przez GitHub Actions (plik `narzedzia/kontrola.py`), bez kluczy, tylko odczyt.']
    return '\n'.join(L) + '\n'


def main():
    R = kontrola()
    md = raport_md(R)
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, 'ostatnia.md'), 'w', encoding='utf-8') as f:
        f.write(md)
    with open(os.path.join(OUT_DIR, 'ostatnia.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    print(md)
    summ = os.environ.get('GITHUB_STEP_SUMMARY')
    if summ:
        with open(summ, 'a', encoding='utf-8') as f:
            f.write(md)
    print('::notice title=kontrola::' + (R['wynik'] + ' — ' + '; '.join(R['bledy'] + R['uwagi'])[:900]).replace('%', '%25').replace('\n', '%0A'))
    sys.exit(1 if R['bledy'] else 0)


if __name__ == '__main__':
    main()
