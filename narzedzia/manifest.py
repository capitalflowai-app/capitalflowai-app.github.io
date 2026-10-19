#!/usr/bin/env python3
"""Spis plików danych wydania (v459, F11Z41, szybkość etap 7): `data/manifest.json` = {"v":1,"at":"<UTC>","f":{"<nazwa>":["<skrót 12 znaków>",<bajty>]}}.
Nazwa = ścieżka względem data/ bez „.json” (tak samo jak nazwa w srvJSON na stronie: „cmc”, „widoki/xyz”). Skrót = pierwsze 12 znaków SHA-256 treści pliku.
Strona odpytuje ten mały plik co minutę (tylko gdy karta widoczna) i pobiera ponownie wyłącznie pliki, których skrót się zmienił.

Użycie: manifest.py zapisz <katalog_data>   — buduje spis z plików *.json katalogu (i widoki/*.json); zapis atomowy (plik tymczasowy → zamiana);
        manifest.py sprawdz <katalog_data>  — porównuje spis z plikami; kod 0 = zgodny, 1 = niezgodny albo brak/uszkodzony.
Spis jest dodatkiem: bez niego (albo przy błędzie) strona działa dokładnie jak dotąd, na własnych zegarach modułów. Python 3.12, biblioteka standardowa."""
import datetime
import hashlib
import json
import os
import re
import sys

NAZWA_PLIKU = 'manifest.json'
PODKATALOGI = ('widoki',)                    # pliki widoków silnika (data/widoki/*.json) — nazwa „widoki/<plik>”
_NAZWA = re.compile(r'^[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?$')   # zgodna z wzorcem po stronie strony (manApply) i Service Workera
SKROT = 12


def _skrot(sciezka):
    h = hashlib.sha256()
    n = 0
    with open(sciezka, 'rb') as f:
        for blok in iter(lambda: f.read(1 << 20), b''):
            h.update(blok); n += len(blok)
    return h.hexdigest()[:SKROT], n


def pliki(katalog):
    """{nazwa: ścieżka} plików *.json katalogu danych (bez samego spisu); nazwy spoza wzorca pomijane."""
    out = {}
    miejsca = [('', katalog)] + [(p + '/', os.path.join(katalog, p)) for p in PODKATALOGI]
    for pref, kat in miejsca:
        if not os.path.isdir(kat):
            continue
        for fn in sorted(os.listdir(kat)):
            if not fn.endswith('.json') or (not pref and fn == NAZWA_PLIKU):
                continue
            nazwa = pref + fn[:-5]
            s = os.path.join(kat, fn)
            if _NAZWA.match(nazwa) and os.path.isfile(s) and not os.path.islink(s):
                out[nazwa] = s
    return out


def zbuduj(katalog, teraz=None):
    teraz = teraz or datetime.datetime.now(datetime.timezone.utc)
    f = {}
    for nazwa, s in pliki(katalog).items():
        sk, n = _skrot(s)
        f[nazwa] = [sk, n]
    return {'v': 1, 'at': teraz.strftime('%Y-%m-%dT%H:%M:%SZ'), 'f': f}


def zapisz(katalog, teraz=None):
    m = zbuduj(katalog, teraz)
    if not m['f']:
        raise RuntimeError('brak plików danych — spis nie powstał')
    cel = os.path.join(katalog, NAZWA_PLIKU)
    tmp = cel + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(m, f, separators=(',', ':'), sort_keys=True)
    os.replace(tmp, cel)                     # atomowo: nigdy pół pliku
    return m


def sprawdz(katalog):
    """Lista różnic (pusta = zgodny)."""
    cel = os.path.join(katalog, NAZWA_PLIKU)
    try:
        with open(cel, encoding='utf-8') as f:
            m = json.load(f)
    except Exception as e:  # noqa
        return ['brak albo uszkodzony spis: ' + str(e)[:80]]
    if not isinstance(m, dict) or m.get('v') != 1 or not isinstance(m.get('f'), dict) or not m['f']:
        return ['zły format spisu']
    ro = []
    teraz = zbuduj(katalog)['f']
    for k in sorted(set(m['f']) | set(teraz)):
        if m['f'].get(k) != teraz.get(k):
            ro.append(k)
    return ro


def main(argv):
    if len(argv) != 3 or argv[1] not in ('zapisz', 'sprawdz') or not os.path.isdir(argv[2]):
        print('użycie: manifest.py zapisz|sprawdz <katalog_data>'); return 2
    if argv[1] == 'zapisz':
        m = zapisz(argv[2])
        print('spis plików: %d plików, %d B' % (len(m['f']), os.path.getsize(os.path.join(argv[2], NAZWA_PLIKU))))
        return 0
    ro = sprawdz(argv[2])
    if ro:
        print('spis niezgodny z plikami: ' + ', '.join(ro[:10])); return 1
    print('spis zgodny z plikami wydania')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
