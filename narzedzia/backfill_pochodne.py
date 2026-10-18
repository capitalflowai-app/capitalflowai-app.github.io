#!/usr/bin/env python3
"""Historia pochodnych krypto do testów wstecznych TRENDÓW (v408, zadanie F11Z17) — DANE WEJŚCIOWE, bez żadnych sygnałów.

Trzy pliki CSV w archiwum/ (UTF-8, przecinek, kropka dziesiętna; brak wartości = puste pole, nigdy zero; jeden wiersz na dzień UTC):
  binance-metrics.csv  dzień × kontrakt (BTCUSDT od 2020-09-01, ETHUSDT od 2021-12-01) — z plików dziennych metryk kontraktów wieczystych
                       (wiersze co ok. 5 min → jeden wiersz doby: ostatni poprawny odczyt każdej wartości oraz średnia stosunku kupna do sprzedaży po rynku;
                       w części 2022 r. źródło ma puste stosunki największych graczy i kupna/sprzedaży — wtedy puste pola, a otwarte pozycje są)
                       date, sym, n (liczba odczytów doby), last_t (godzina UTC ostatniego odczytu), oi (otwarte pozycje, monety), oi_usd,
                       top_ls (stosunek kont największych graczy), top_pos (stosunek pozycji największych graczy), ls (stosunek kont
                       wszystkich), taker (kupno do sprzedaży po rynku, ostatni odczyt), taker_avg (średnia doby)
  binance-funding.csv  dzień × kontrakt (od 2020-01) — z plików miesięcznych stawek finansowania: date, sym, n (liczba rozliczeń doby),
                       sum_bp (suma stawek doby w punktach bazowych = stawka × 10 000), last_bp (ostatnie rozliczenie doby)
  deribit-dvol.csv     dzień × moneta (BTC, ETH; od 2021-03) — dzienne świece indeksu zmienności opcji (punkty indeksu):
                       date, cur, open, high, low, close; w pliku tylko pełne doby (świeca dnia bieżącego nie wchodzi)

DOSTĘPNOŚĆ (filtr przyczynowy dla testów wstecznych — patrz `dostepne_od`): plik dzienny metryk doby X pojawia się u źródła dopiero ok. 06:40–07:15 UTC
doby X+1 (więc po granicy 05:30 UTC reguł krypto); stawka finansowania i świeca indeksu doby X są znane od 00:00 UTC doby X+1. Plik miesięczny
finansowania pojawia się u źródła po końcu miesiąca — w archiwum finansowanie ma więc opóźnienie do kilku tygodni, ale wiersz doby X jest jawny
już o 00:00 UTC X+1 (tak go traktuje `dostepne_od`; archiwum przechowuje dane, nie moment zapisu).

Pobieranie: publiczne GET bez klucza, jedno zapytanie na plik (ok. 12 KB/doba), przerwa między zapytaniami. Brak pliku (404) dla doby z ostatnich dni =
plik jeszcze nie opublikowany (koniec przebiegu, ciąg dalszy następnym razem); brak pliku starszej doby = luka (dzień bez wiersza). Inny błąd
(403, 429, 5xx, uszkodzony plik) po pobranych już wierszach = zapis tego, co pobrano, i uwaga w indeksie; bez żadnego wiersza = błąd źródła.
Dane doby przychodzą ze źródła w pełnym zapisie 5-minutowym; w archiwum jest podsumowanie doby (rozmiar ok. 1 MB zamiast ok. 50 MB).

Licencja DANYCH metryk i finansowania: CC BY-NC-SA 4.0 — „Binance Vision Dataset Terms” v1.0 (tylko użycie niekomercyjne; wykorzystujemy je do własnych
testów statystycznych strony niezarobkowej; praca pochodna zostaje na tej samej licencji; decyzja D8: przegląd przed jakimikolwiek opłatami).
Indeks zmienności opcji: publiczne dane rynkowe giełdy opcji, bez klucza. Licencja MIT repozytorium dotyczy kodu, nie danych.

Użycie jednorazowe (pierwsze zasilenie, potem robi to codziennie narzedzia/archiwum.py):
  python3 narzedzia/backfill_pochodne.py [--arch katalog] [--maks N] [--pauza SEK] [--tylko metryki|finansowanie|dvol]
Biblioteka standardowa. Moduł nie wykonuje żadnych zapytań przy imporcie."""
import csv
import datetime
import io
import json
import math
import os
import sys
import time
import urllib.error
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BN_METRICS_URL = 'https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip'
BN_FUNDING_URL = 'https://data.binance.vision/data/futures/um/monthly/fundingRate/{s}/{s}-fundingRate-{m}.zip'
DR_DVOL_URL = ('https://www.deribit.com/api/v2/public/get_volatility_index_data?currency={c}&start_timestamp={a}&end_timestamp={b}&resolution=1D')

BN_START = {'BTCUSDT': '2020-09-01', 'ETHUSDT': '2021-12-01'}   # pierwszy dzień pliku metryk (wcześniej 404)
BN_FUND_START = '2020-01'                                       # pierwszy miesiąc pliku finansowania (BTC i ETH)
DVOL_START = '2021-03-24'                                       # pierwsza świeca indeksu zmienności
DVOL_CURS = ('BTC', 'ETH')
SYMS = tuple(BN_START)

COLS_METRICS = ['date', 'sym', 'n', 'last_t', 'oi', 'oi_usd', 'top_ls', 'top_pos', 'ls', 'taker', 'taker_avg']
COLS_FUNDING = ['date', 'sym', 'n', 'sum_bp', 'last_bp']
COLS_DVOL = ['date', 'cur', 'open', 'high', 'low', 'close']

MAKS_PRZEBIEG = 45     # zapytań o pliki na kontrakt w jednym przebiegu archiwum (po dłuższej przerwie ciąg dalszy następnego dnia)
PAUZA = 0.25           # s między zapytaniami do tego samego hosta
GRANICA_BRAKU_D = 2    # brak pliku dziennego doby nie starszej niż tyle dni przed dzisiejszą = jeszcze nie opublikowany
FUND_MAX = 0.05        # |stawka rozliczenia| ponad 5 % = pomyłka jednostki albo uszkodzony wiersz → pominięty
UA_PROG = 'CapitalFlowAI/1.0 badania-niekomercyjne (archiwum historii pochodnych)'

_BN_NEED = ('sum_open_interest', 'sum_open_interest_value', 'count_toptrader_long_short_ratio', 'sum_toptrader_long_short_ratio',
            'count_long_short_ratio', 'sum_taker_long_short_vol_ratio')


# ------------------------------------------------------------------ zapytania (jedyne miejsce z siecią; testy podstawiają własne) ----------
def _zd():
    sys.path.insert(0, ROOT)
    import zbieraj_dane as zd
    return zd


def pobierz_bajty(url):
    """Publiczne GET bez uwierzytelnienia; zbieracz liczy zapytania i maskuje klucze w komunikatach. 404 = urllib.error.HTTPError."""
    return _zd().get_bytes(url, {'User-Agent': UA_PROG}, timeout=30)


# ------------------------------------------------------------------ pomocnicze --------------------------------------------------------
def liczba(v, dodatnia=False):
    """Skończona liczba z tekstu albo liczby; bool, puste, NaN, nieskończoność → None (brak nigdy nie staje się zerem)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or math.isinf(x) or (dodatnia and x <= 0):
        return None
    return x


def _dzien(s):
    return datetime.date.fromisoformat(str(s)[:10])


def _csv_z_zip(dane):
    """ZIP z jednym plikiem CSV → tekst; uszkodzony plik albo brak CSV = wyjątek (nie „brak danych”)."""
    with zipfile.ZipFile(io.BytesIO(dane)) as z:
        nazwy = [n for n in z.namelist() if n.lower().endswith('.csv')]
        if not nazwy:
            raise ValueError('archiwum bez pliku CSV')
        return z.read(nazwy[0]).decode('utf-8', 'replace')


def dostepne_od(rodzaj, dzien):
    """Moment UTC, od którego wiersz doby `dzien` mógł być znany (filtr przyczynowy dla testów wstecznych):
    'metryki' — plik doby pojawia się ok. 06:40–07:15 UTC następnej doby (zapas do 07:30); 'finansowanie' i 'dvol' — od północy UTC następnej doby.
    Reguła/test, który liczy sygnał na moment T, może użyć tylko wierszy z dostepne_od(...) <= T."""
    d = _dzien(dzien) + datetime.timedelta(days=1)
    t = datetime.datetime(d.year, d.month, d.day, tzinfo=datetime.timezone.utc)
    if rodzaj == 'metryki':
        return t + datetime.timedelta(hours=7, minutes=30)
    if rodzaj in ('finansowanie', 'dvol'):
        return t
    raise ValueError(f'nieznany rodzaj: {rodzaj}')


def wiersze_do(rows, rodzaj, moment, kol_dzien=0):
    """Wiersze (listy, kolumna `kol_dzien` = dzień) znane najpóźniej w `moment` (UTC, z strefą) — nic z przyszłości."""
    return [r for r in rows if dostepne_od(rodzaj, r[kol_dzien]) <= moment]


# ------------------------------------------------------------------ metryki kontraktów (plik dzienny) -----------------------------------
def metryki_doby(sym, dzien, tekst):
    """Tekst CSV pliku dziennego → wiersz doby albo None (doba bez żadnego odczytu otwartych pozycji). Duplikaty czasu usuwane (starsze pliki mają
    każdy odczyt dwa razy), odczyty spoza doby pomijane. Odczyt liczy się (n), gdy ma dodatnie otwarte pozycje w monetach i w USD; każda z pozostałych
    wartości (stosunki kont i pozycji, kupno/sprzedaż po rynku) to jej ostatnia poprawna wartość doby, a brak (puste pole w pliku źródła, np. w całym
    2022 r., albo wartość ujemna) zostaje brakiem — puste pole, nigdy zero. last_t = godzina ostatniego odczytu otwartych pozycji."""
    r = csv.DictReader(io.StringIO(tekst))
    brak = [c for c in ('create_time',) + _BN_NEED if c not in (r.fieldnames or [])]
    if brak:
        raise ValueError('plik metryk bez kolumn: ' + ', '.join(brak))
    odczyty = {}
    for w in r:
        t = str(w.get('create_time') or '').strip()
        if t[:10] != dzien or len(t) < 16:
            continue
        v = {c: liczba(w.get(c)) for c in _BN_NEED}
        if not v['sum_open_interest'] or not v['sum_open_interest_value'] or v['sum_open_interest'] < 0 or v['sum_open_interest_value'] < 0:
            continue
        odczyty[t] = {c: (x if x is not None and x >= 0 else None) for c, x in v.items()}
    if not odczyty:
        return None
    ts = sorted(odczyty)

    def ostatnia(c):
        for t in reversed(ts):
            if odczyty[t][c] is not None:
                return round(odczyty[t][c], 6)
        return None
    tk = [odczyty[t]['sum_taker_long_short_vol_ratio'] for t in ts if odczyty[t]['sum_taker_long_short_vol_ratio'] is not None]
    return [dzien, sym, len(ts), ts[-1][11:16], ostatnia('sum_open_interest'), round(odczyty[ts[-1]]['sum_open_interest_value'], 2),
            ostatnia('count_toptrader_long_short_ratio'), ostatnia('sum_toptrader_long_short_ratio'), ostatnia('count_long_short_ratio'),
            ostatnia('sum_taker_long_short_vol_ratio'), round(sum(tk) / len(tk), 6) if tk else None]


def _ostatni_dzien(wiersze, sym, kol_sym=1):
    d = [w[0] for w in wiersze if w[kol_sym] == sym]
    return max(d) if d else None


def nowe_metryki(sym, istniejace, dzis, fetch=None, maks=MAKS_PRZEBIEG, pauza=PAUZA, uwagi=None, spij=time.sleep):
    """Wiersze metryk kontraktu `sym` dla dób po ostatnim zapisanym (albo od pierwszej doby pliku) do wczoraj UTC włącznie.
    istniejace: wiersze (listy tekstów) z pliku; dzis: data UTC (date). Najwyżej `maks` zapytań. Zwraca listę nowych wierszy.
    404 doby z ostatnich dni = plik jeszcze nie opublikowany (koniec); starsza doba bez pliku = luka. Błąd po pobranych wierszach = uwaga i zapis pobranych."""
    fetch = fetch or pobierz_bajty
    uwagi = uwagi if uwagi is not None else []
    ost = _ostatni_dzien(istniejace, sym)
    dzien = _dzien(ost) + datetime.timedelta(days=1) if ost else _dzien(BN_START[sym])
    out, zapytan, luki = [], 0, 0
    while dzien < dzis and zapytan < maks:
        d = dzien.isoformat()
        zapytan += 1
        try:
            tekst = _csv_z_zip(fetch(BN_METRICS_URL.format(s=sym, d=d)))
            w = metryki_doby(sym, d, tekst)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                if dzien >= dzis - datetime.timedelta(days=GRANICA_BRAKU_D):
                    break   # jeszcze nie opublikowany — ciąg dalszy następnym razem
                luki += 1; dzien += datetime.timedelta(days=1)
                if pauza:
                    spij(pauza)
                continue
            if out:
                uwagi.append(f'metryki {sym} {d}: HTTP {e.code}'); break
            raise
        except Exception as e:  # noqa — uszkodzony plik: bez pobranych wcześniej wierszy błąd źródła, z nimi zapis pobranych
            if out:
                uwagi.append(f'metryki {sym} {d}: {e}'); break
            raise
        if w is None:
            luki += 1
        else:
            out.append(w)
        dzien += datetime.timedelta(days=1)
        if pauza:
            spij(pauza)
    if luki:
        uwagi.append(f'metryki {sym}: {luki} dób bez pliku albo bez kompletnego odczytu (luki)')
    return out


# ------------------------------------------------------------------ finansowanie (plik miesięczny) ---------------------------------------
def finansowanie_miesiaca(sym, tekst):
    """Tekst CSV miesięcznego pliku stawek → wiersze dób [date, sym, n, sum_bp, last_bp]. Dzień = data UTC chwili rozliczenia; duplikaty chwili
    usuwane; stawka spoza ±FUND_MAX albo nieliczbowa pomijana (doba bez żadnej stawki = bez wiersza)."""
    r = csv.DictReader(io.StringIO(tekst))
    if 'calc_time' not in (r.fieldnames or []) or 'last_funding_rate' not in (r.fieldnames or []):
        raise ValueError('plik finansowania bez kolumn calc_time / last_funding_rate')
    po_dniach = {}
    for w in r:
        ms = liczba(w.get('calc_time'))
        f = liczba(w.get('last_funding_rate'))
        if ms is None or f is None or abs(f) > FUND_MAX or ms <= 0:
            continue
        d = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).date().isoformat()
        po_dniach.setdefault(d, {})[int(ms) // 1000] = f   # chwila z dokładnością do sekundy (rozliczenia mają znaczniki ±10 ms)
    out = []
    for d in sorted(po_dniach):
        stawki = [po_dniach[d][k] for k in sorted(po_dniach[d])]
        out.append([d, sym, len(stawki), round(sum(stawki) * 1e4, 6), round(stawki[-1] * 1e4, 6)])
    return out


def _miesiac(d):
    return d.year * 12 + d.month - 1


def _od_miesiaca(m):
    return datetime.date(m // 12, m % 12 + 1, 1)


def nowe_finansowanie(sym, istniejace, dzis, fetch=None, maks=MAKS_PRZEBIEG, pauza=PAUZA, uwagi=None, spij=time.sleep):
    """Wiersze finansowania dla miesięcy po ostatnim zapisanym (miesiąc bieżący nie ma jeszcze pliku). Miesiąc ostatniego wiersza jest pobierany
    ponownie tylko wtedy, gdy wiersz nie jest z ostatniego dnia miesiąca (plik mógł być wtedy niepełny). 404 miesiąca, który skończył się niedawno =
    plik jeszcze nie opublikowany (koniec); starszy = luka."""
    fetch = fetch or pobierz_bajty
    uwagi = uwagi if uwagi is not None else []
    ost = _ostatni_dzien(istniejace, sym)
    if ost:
        o = _dzien(ost)
        m = _miesiac(o) + (1 if (o + datetime.timedelta(days=1)).month != o.month else 0)
    else:
        m = _miesiac(_dzien(BN_FUND_START + '-01'))
    koniec = _miesiac(dzis)   # bieżącego miesiąca nie pobieramy
    out, zapytan, luki = [], 0, 0
    while m < koniec and zapytan < maks:
        nazwa = _od_miesiaca(m).isoformat()[:7]
        zapytan += 1
        try:
            w = finansowanie_miesiaca(sym, _csv_z_zip(fetch(BN_FUNDING_URL.format(s=sym, m=nazwa))))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                if m >= koniec - 1:
                    break   # poprzedni miesiąc może jeszcze nie mieć pliku
                luki += 1; m += 1
                if pauza:
                    spij(pauza)
                continue
            if out:
                uwagi.append(f'finansowanie {sym} {nazwa}: HTTP {e.code}'); break
            raise
        except Exception as e:  # noqa
            if out:
                uwagi.append(f'finansowanie {sym} {nazwa}: {e}'); break
            raise
        out += w
        m += 1
        if pauza:
            spij(pauza)
    if luki:
        uwagi.append(f'finansowanie {sym}: {luki} miesięcy bez pliku (luki)')
    return out


# ------------------------------------------------------------------ indeks zmienności opcji (dzienne świece) ----------------------------
def dvol_swiece(cur, dane, dzis):
    """Odpowiedź JSON (dict) → wiersze [date, cur, open, high, low, close] dla pełnych dób przed `dzis`. Świeca musi zaczynać się o północy UTC
    i mieć cztery dodatnie liczby z high ≥ low; inne pomijane. Zwraca (wiersze, kontynuacja albo None)."""
    res = dane.get('result') if isinstance(dane, dict) else None
    if not isinstance(res, dict) or not isinstance(res.get('data'), list):
        raise ValueError('odpowiedź indeksu zmienności bez pola result.data')
    out = {}
    for s in res['data']:
        if not isinstance(s, list) or len(s) < 5:
            continue
        ms = liczba(s[0]); v = [liczba(x, dodatnia=True) for x in s[1:5]]
        if ms is None or int(ms) % 86400000 != 0 or any(x is None for x in v) or v[1] < v[2]:
            continue
        d = datetime.datetime.fromtimestamp(ms / 1000, datetime.timezone.utc).date()
        if d >= dzis:
            continue
        out[d.isoformat()] = [d.isoformat(), cur] + [round(x, 4) for x in v]
    c = liczba(res.get('continuation'))
    return [out[k] for k in sorted(out)], (int(c) if c is not None else None)


def nowe_dvol(cur, istniejace, dzis, fetch=None, maks=8, pauza=PAUZA, uwagi=None, spij=time.sleep):
    """Dzienne świece indeksu zmienności monety po ostatnim zapisanym dniu (albo od DVOL_START) do wczoraj. Źródło oddaje najnowsze 1000 świec i
    znacznik kontynuacji (koniec następnej, starszej strony) — idziemy wstecz, aż pokryjemy początek zakresu. Najwyżej `maks` stron."""
    fetch = fetch or (lambda u: json.loads(pobierz_bajty(u).decode('utf-8', 'replace')))
    uwagi = uwagi if uwagi is not None else []
    ost = _ostatni_dzien(istniejace, cur)
    od = _dzien(ost) + datetime.timedelta(days=1) if ost else _dzien(DVOL_START)
    if od >= dzis:
        return []
    a = int(datetime.datetime(od.year, od.month, od.day, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    b = int(datetime.datetime(dzis.year, dzis.month, dzis.day, tzinfo=datetime.timezone.utc).timestamp() * 1000)
    out = {}
    for _ in range(maks):
        w, kont = dvol_swiece(cur, fetch(DR_DVOL_URL.format(c=cur, a=a, b=b)), dzis)
        for r in w:
            if r[0] >= od.isoformat():
                out[r[0]] = r
        if not w or kont is None or kont < a or kont >= b:
            break
        b = kont
        if pauza:
            spij(pauza)
    else:
        uwagi.append(f'indeks zmienności {cur}: pobrano {maks} stron — zakres może być niepełny, ciąg dalszy następnym razem')
    return [out[k] for k in sorted(out)]


# ------------------------------------------------------------------ jednorazowe zasilenie z wiersza poleceń ---------------------------------
def _archiwum():
    sys.path.insert(0, os.path.join(ROOT, 'narzedzia'))
    import archiwum
    return archiwum


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description='Jednorazowe zasilenie archiwum historii pochodnych (v408)')
    p.add_argument('--arch', default=None, help='katalog archiwum (domyślnie archiwum/ repozytorium)')
    p.add_argument('--maks', type=int, default=100000, help='najwyżej tyle zapytań o pliki na kontrakt')
    p.add_argument('--pauza', type=float, default=0.12)
    p.add_argument('--tylko', choices=('metryki', 'finansowanie', 'dvol'), default=None)
    a = p.parse_args(argv)
    A = _archiwum()
    arch = a.arch or A.ARCH
    prev = {}
    try:
        with open(os.path.join(arch, 'indeks.json'), encoding='utf-8') as f:
            prev = json.load(f)
    except Exception:  # noqa
        prev = {}
    zad = {'binance-metrics': (A.src_binance_metrics, 'metryki'), 'binance-funding': (A.src_binance_funding, 'finansowanie'),
           'deribit-dvol': (A.src_deribit_dvol, 'dvol')}
    A.BP_MAKS[0] = a.maks; A.BP_PAUZA[0] = a.pauza
    idx = dict(prev) if isinstance(prev, dict) else {}
    idx.setdefault('files', {})
    kod = 0
    for nazwa, (fn, tag) in zad.items():
        if a.tylko and a.tylko != tag:
            continue
        spec = A.FILES[nazwa]; path = os.path.join(arch, spec['file'])
        old, _ = A.read_csv(path, spec['cols'])
        A.NOTES.clear()
        try:
            rows = fn(arch=arch)
        except Exception as e:  # noqa
            print('BŁĄD', nazwa, e); kod = 1; continue
        merged, added, revised = A.merge(old, rows, spec['cols'], spec['key'])
        A.write_csv(path, spec['cols'], merged)
        keys = sorted(merged)
        rec = dict(idx['files'].get(nazwa) or {})
        rec.update({'file': spec['file'], 'src': spec['src'], 'cols': spec['cols'], 'key': spec['key'], 'ok': True, 'at': A.NOW.isoformat(),
                    'rows': len(merged), 'first': keys[0][0] if keys else None, 'last': keys[-1][0] if keys else None, 'added': added,
                    'revised': revised, 'revisions_total': int(rec.get('revisions_total') or 0) + revised, 'fetched': len(rows)})
        idx['files'][nazwa] = rec
        print(f'{nazwa}: {len(rows)} pobranych, {added} nowych, {revised} zrewidowanych, razem {len(merged)}; uwagi: {"; ".join(A.NOTES) or "—"}')
    with open(os.path.join(arch, 'indeks.json'), 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=1)
    return kod


if __name__ == '__main__':
    sys.exit(main())
