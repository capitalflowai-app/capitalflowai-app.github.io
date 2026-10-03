#!/usr/bin/env python3
"""Codzienna kontrola strony — uruchamiana w GitHub Actions (ma dostęp do sieci), nie w chmurze Claude (tam brak dostępu do strony).
Sprawdza: stronę główną, plik stanu automatu (meta.json: wiek, błędy, źródła bez odpowiedzi), wiek plików danych, pliki dla wyszukiwarek,
przebiegi Actions z 24 h; v115 (część C zadania z 26.09.2026): świeżość źródeł wg kategorii (godzinowe / dzienne w dni robocze / tygodniowe
/ miesięczne; żółte po przekroczeniu progu, czerwone po 2×), błędy zbieracza w 3 kolejnych uruchomieniach = czerwone (kontrola/historia.json),
zgodność liczb (kapitalizacja krypto CoinGecko vs CoinPaprika — różnica dnia wobec mediany 30 dni w kontrola/zgodnosc.csv; ceny BTC/ETH;
TGA Fiscal Data vs FRED; wieloryby: zmiana salda vs przelewy z archiwum).
Zapisuje `kontrola/ostatnia.md` (po polsku: nagłówek i linia „Wynik:” w stałym formacie — czyta je zadanie w chmurze; potem werdykt
✅/⚠️/❌ i tabela źródło → status → wiek danych → uwaga), `kontrola/ostatnia.json`, `kontrola/zgodnosc.csv`, `kontrola/historia.json`.
Kod wyjścia 1 = BŁĄD (GitHub wysyła właścicielowi e-mail o nieudanym przebiegu). Bez kluczy, tylko odczyt. Python 3.12, sama biblioteka standardowa.
Uwaga: komunikat commita bota zawiera „[skip ci]” — GitHub pomija wtedy przebiegi wyzwalane pushem (dlatego commit dodający ten plik
nie może mieć tego napisu w treści — pierwszy przebieg nie ruszył właśnie z tego powodu).
v136: kursy dolara Ameryki Łacińskiej (data/dolar.json) — świeżość osobnym wierszem (najwyżej ⚠️), dwa odczyty kursów Argentyny z pliku i kurs hurtowy vs API banku centralnego Argentyny (1 zapytanie); tylko uwagi, nigdy BŁĄD.
v130: ETF krypto u źródła — przepływy IBIT i ETHA na stronie vs wyliczenie z plików emitenta (liczba jednostek × NAV); zapis sesji ze strony w `kontrola/etf-emitent.csv`."""
import csv
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

SITE = os.environ.get('SITE_URL', 'https://capitalflowai-app.github.io').rstrip('/')
REPO = os.environ.get('GITHUB_REPOSITORY', 'capitalflowai-app/capitalflowai-app.github.io')
TOKEN = os.environ.get('GITHUB_TOKEN', '')          # tylko do odczytu listy przebiegów (API publiczne działa też bez niego)
OUT_DIR = os.environ.get('KONTROLA_DIR', 'kontrola')
ARCH_DIR = os.environ.get('KONTROLA_ARCH', 'archiwum')   # archiwum własne z tego samego checkoutu (v113)
NOW = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
PLIKI = ['meta', 'etf', 'trendy', 'oecd', 'rynki', 'dzwignia', 'wieloryby', 'energia', 'usa-makro', 'bilans-usa', 'krypto', 'krypto-top10', 'instytucje', 'tic', 'cm', 'fred', 'cftc', 'ceny', 'indeksy', 'ceny-krypto', 'snb', 'fed', 'lancuch', 'wycena', 'insider', 'nastroj', 'stres', 'aukcje', 'swiat-dzien', 'swiat-dziennik', 'premie', 'dolar', 'krypto-dzien', 'krypto-dziennik']
LIMIT_MIN = {'meta': 90, 'etf': 180, 'trendy': 180, 'oecd': 24 * 60, 'rynki': 180, 'dzwignia': 180, 'wieloryby': 90, 'energia': 24 * 60,
             'usa-makro': 24 * 60, 'bilans-usa': 48 * 60, 'krypto': 180, 'krypto-top10': 180, 'instytucje': 180, 'tic': 48 * 60, 'cm': 180, 'fred': 180, 'cftc': 24 * 60, 'ceny': 180, 'indeksy': 24 * 60, 'ceny-krypto': 180, 'snb': 24 * 60, 'fed': 90, 'lancuch': 90, 'wycena': 8 * 60, 'insider': 48 * 60, 'nastroj': 12 * 60, 'stres': 24 * 60, 'aukcje': 24 * 60, 'swiat-dzien': 180, 'swiat-dziennik': 180, 'premie': 90, 'dolar': 180, 'krypto-dzien': 180, 'krypto-dziennik': 180}
# v115: świeżość ŹRÓDEŁ (data danych, nie czas pliku). (etykieta, plik, kategoria, próg w minutach). Kategorie: 'h' = godzinowe (czas części
# pliku), 'd' = dzienne w dni robocze (koniec dnia danych, liczone godzinami roboczymi bez sobót i niedziel), 'w' = tygodniowe (koniec dnia danych),
# 'm' = miesięczne (koniec miesiąca danych). Progi z zadania: 3 h / 36 h / 9 dni / 45 dni; CFTC +3 dni (raport wtorkowy publikowany w piątek),
# TIC +40 dni (Skarb USA publikuje dane miesiąca 46–51 dni po jego końcu; tuż przed publikacją wiek = 30 + 51 = 81 dni) — inaczej żółte świeciłoby co miesiąc bez powodu.
# EIA: ceny dzienne ropy są publikowane raz w tygodniu (środa, za poprzedni tydzień) — próg tygodniowy 9 dni, nie 36 h (26.09: dane z wtorku w sobotę = 3 dni).
SWIEZOSC = [
    ('rynki (kursy EBC, rentowności)', 'rynki', 'h', 180), ('wieloryby (salda portfeli giełd)', 'wieloryby', 'h', 180), ('dźwignia (giełdy pochodnych)', 'dzwignia', 'h', 180),
    ('premie krypto (minuty giełd)', 'premie', 'h', 180),
    ('TGA (Fiscal Data, dziennie)', 'instytucje', 'd', 36 * 60), ('ETF krypto (SoSoValue, dziennie)', 'etf', 'd', 36 * 60),
    ('FRED dzienne (RRPONTSYD)', 'fred', 'd', 36 * 60), ('EIA ceny dzienne (publikowane co tydzień)', 'energia', 'w', 9 * 24 * 60),
    ('CFTC (raport tygodniowy)', 'cftc', 'w', (9 + 3) * 24 * 60), ('FRED tygodniowe (WALCL)', 'fred', 'w', 9 * 24 * 60),
    ('TIC (miesięcznie)', 'tic', 'm', (45 + 40) * 24 * 60), ('OECD (miesięcznie)', 'oecd', 'm', 45 * 24 * 60), ('BLS (miesięcznie)', 'usa-makro', 'm', 45 * 24 * 60),
]
CG_GLOBAL = 'https://api.coingecko.com/api/v3/global'
CP_GLOBAL = 'https://api.coinpaprika.com/v1/global'
CG_PRICE = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd'
CP_TICKER = 'https://api.coinpaprika.com/v1/tickers/{id}?quotes=USD'
ZG_DNI = 30          # mediana z ostatnich 30 dni różnicy kapitalizacji
ZG_MIN = 7           # do zebrania tylu dni historii — tylko informacja, bez koloru
ZG_ZOLTE, ZG_CZERWONE = 2.0, 5.0   # pkt proc. odchylenia od mediany
CENA_PROG = 1.0      # % różnicy cen BTC/ETH między źródłami
ETF_PROG = 1.0       # % różnicy zamknięcia ETF tej samej daty: Twelve Data (ceny.json, mapa) vs Massive/Tiingo (indeksy.json → etf) — v117.1
TGA_PROG = 1.0       # pkt proc. — odchylenie dzisiejszej różnicy TGA (Fiscal Data vs FRED WTREGEN, ta sama data) od mediany 30 dni; różnica sama w sobie
                     # jest stała (~3%: H.4.1 liczy zobowiązanie Fed na środę, DTS — gotówkę operacyjną Skarbu), więc próg 1% na poziomach świeciłby codziennie
WH_PROG = 5.0        # % — |zmiana salda − przelewy netto| wobec większej z tych liczb
WH_MIN_USD = 1e6     # poniżej miliona USD rozbieżność nie jest uwagą (przelewy < 1 mln nie są skanowane)
HIST_N = 30          # przechowywane przebiegi w historia.json
HIST_CZERWONE = 3    # tyle kolejnych przebiegów z błędami zbieracza = czerwone
# v130: ETF krypto u źródła (bez klucza). Pliki funduszy emitenta IBIT i ETHA (Excel 2003 XML, arkusz „Historical”: As Of, NAV per Share,
# Shares Outstanding) → przepływ dnia D = (jednostki z wiersza D+1 − jednostki z wiersza D) × NAV z dnia D: wiersz „As Of” D+1 zawiera
# jednostki utworzone w sesji D (sprawdzone 27.09 na 7 sesjach IBIT i 2 ETHA). Strona pokazuje przepływ funduszu tylko dla ostatniej sesji
# (data/etf.json → assets[btc|eth].funds[].d1 dla `asof`), więc każdy przebieg zapisuje go w kontrola/etf-emitent.csv, a porównanie dnia D
# rusza, gdy plik emitenta ma już wiersz następnej sesji (przy kontroli o 06:20 UTC zwykle dzień po zapisie). Wynik najwyżej ⚠️ (nigdy ❌
# ani BŁĄD); do raportu idą tylko różnice i daty. Zestawienie niezależnego serwisu z planu v128 odrzucone: sonda z serwera GitHub w USA
# (27.09) dostała 403 (wyzwanie Cloudflare) dla każdego identyfikatora — z Actions nie da się go odczytać, a zabezpieczeń nie obchodzimy.
EM_DOC = ('https://www.blackrock.com/varnish-api/blk-one01-product-data/product-data/api/v1/get-fund-document?appType=PRODUCT_PAGE'
          '&appSubType=ISHARES&targetSite=us-ishares&locale=en_US&portfolioId={pid}&component=fundDownload&userType=individual')
EM_FUNDS = (('IBIT', 'btc', '333011'), ('ETHA', 'eth', '337614'))   # symbol, aktywo w etf.json, numer pliku funduszu (jak w zbieraczu, v90)
EM_CSV = 'etf-emitent.csv'
EM_KOL = ['date', 'ticker', 'site_flow_musd', 'read_at']   # tylko liczby ze strony (pusta komórka = brak, nigdy 0) i czas ich odczytu
EM_DNI = 60            # tyle ostatnich dat trzyma zapis
EM_SESJE = 5           # okno porównania: ostatnie zapisane sesje, które plik emitenta już rozlicza (różnica w oknie = ⚠️ przez ok. tydzień)
EM_TOL_MLN, EM_TOL_PCT = 0.5, 2.0    # zgodne, gdy |strona − emitent| ≤ max(0,5 mln USD; 2% |emitent|)
EM_NAV_SKOK = 30.0     # % — większy skok NAV między sąsiednimi wierszami = podział jednostek albo błąd pliku: dzień pominięty
EM_PRZERWA = 5         # dni — następny wiersz pliku dalej niż to = dzień pominięty (brak wierszy w pliku)
EM_ZALEGLOSC = 2       # sesje — strona ma więcej sesji nowszych niż ostatni wiersz pliku emitenta = plik nieaktualny (zwykle 0; 1 = wiersz jeszcze
                       # nieopublikowany): status „?” i uwaga, bo porównanie obejmuje wtedy tylko stare sesje, a nowsze czekają bez sprawdzenia
EM_TIMEOUT = 45        # s na plik (ok. 250 KB; z USA ok. 0,6 s)
EM_PAUZA = 1.0         # s przerwy między dwoma zapytaniami do tego samego serwera


def get(url, timeout=25, headers=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalFlowAI-kontrola/1.0', **(headers or {})})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        return r.status, body, int((time.monotonic() - t0) * 1000)


def get_json(url, timeout=25):
    return json.loads(get(url, timeout)[1])


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


def fmt_wiek(m):
    """Minuty → „0 h 34 min” / „2 d 3 h” / „—”."""
    if m is None:
        return '—'
    if m < 60 * 48:
        return f'{m // 60} h {m % 60:02d} min'
    return f'{m // 1440} d {(m % 1440) // 60} h'


# ---------------------------------------------------------------- v115: świeżość źródeł ----------------------------------------------------------------
def godziny_robocze(od, do):
    """Godziny między od i do (UTC) bez sobót i niedziel — dane dzienne nie starzeją się przez weekend."""
    if do <= od:
        return 0.0
    h, t = 0.0, od
    while t < do:
        nxt = min(do, (t + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0))
        if t.weekday() < 5:
            h += (nxt - t).total_seconds() / 3600
        t = nxt
    return h


def data_danych(name, j):
    """Data/czas danych z pliku wg jego kształtu → (tekst daty, rodzaj: 'ts' | 'day' | 'month') albo None."""
    try:
        if name in ('rynki', 'dzwignia'):
            pa = j.get('part_at') or {}
            if name == 'dzwignia':   # v126: część `cz` (źródło zbiorcze, dobierana co przebieg) nie świadczy o świeżości odczytów bezpośrednich
                pa = {k: x for k, x in pa.items() if k != 'cz'}
            v = max((x for x in pa.values() if isinstance(x, str)), default=None)
            return (v, 'ts') if v else None
        if name == 'premie':   # v128: najnowsza minuta odczytu na żywo (koniec okna) spośród bloków now.*
            N = j.get('now') or {}
            v = max((B['win'][1] for B in N.values() if isinstance(B, dict) and isinstance(B.get('win'), list) and len(B['win']) == 2
                     and isinstance(B['win'][1], str)), default=None)
            return (v, 'ts') if v else None
        if name == 'wieloryby':
            v = (j.get('part_at') or {}).get('salda') or j.get('at')
            return (v, 'ts') if isinstance(v, str) else None
        if name == 'instytucje':
            return (j['tga']['asof'], 'day')
        if name == 'etf':
            return (j['asof'], 'day')
        if name == 'energia':
            d = j['s']['wti']['d']; return (d[-1][0], 'day')
        if name == 'cftc':
            return (j['asof'], 'day')
        if name == 'tic':
            return (j['asof'], 'month')
        if name == 'oecd':
            last = None
            for part in ('cli', 'irlt', 'share'):
                for rows in (j.get(part) or {}).values():
                    if rows and isinstance(rows[-1], list):
                        last = max(last or '', str(rows[-1][0]))
            return (last, 'month') if last else None
        if name == 'usa-makro':
            d = j['s']['cpi']['d']; return (d[-1][0], 'month')
    except Exception:
        return None
    return None


def wiek_danych(txt, kind, kat, now=None):
    """Wiek danych w minutach dla kategorii progu: 'ts' → od znacznika czasu; 'day' → od końca dnia danych; 'month' → od końca
    miesiąca danych; kategoria 'd' liczy godziny robocze (bez sobót i niedziel). None = nie da się policzyć."""
    now = now or NOW
    try:
        if kind == 'ts':
            t = dt.datetime.fromisoformat(str(txt).replace('Z', '+00:00'))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
            return max(0, int((now - t).total_seconds() // 60))
        if kind == 'day':
            d = dt.datetime.fromisoformat(str(txt)[:10]).replace(tzinfo=dt.timezone.utc) + dt.timedelta(days=1)
        else:   # month 'YYYY-MM' → pierwszy dzień następnego miesiąca
            y, m = int(str(txt)[:4]), int(str(txt)[5:7])
            d = dt.datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=dt.timezone.utc)
        if kat == 'd':
            return int(godziny_robocze(d, now) * 60)
        return max(0, int((now - d).total_seconds() // 60))
    except Exception:
        return None


def ocena(wiek, prog):
    if wiek is None:
        return '?'
    return '❌' if wiek > 2 * prog else ('⚠️' if wiek > prog else '✅')


def swiezosc(files, now=None):
    """files: nazwa → wczytany JSON (albo None). Zwraca listę wierszy tabeli: (etykieta, status, wiek min, data danych, uwaga)."""
    rows = []
    for label, name, kat, prog in SWIEZOSC:
        j = files.get(name)
        if not isinstance(j, dict):
            rows.append((label, '?', None, None, 'plik nie wczytany')); continue
        if name == 'fred':
            sid = 'RRPONTSYD' if kat == 'd' else 'WALCL'
            try:
                txt, kind = j['series'][sid]['asof'], 'day'
            except Exception:
                rows.append((label, '?', None, None, f'brak serii {sid}')); continue
        else:
            dd = data_danych(name, j)
            if not dd:
                rows.append((label, '?', None, None, 'brak daty danych w pliku')); continue
            txt, kind = dd
        w = wiek_danych(txt, kind, kat, now)
        st = ocena(w, prog)
        note = '' if st == '✅' else (f'próg {fmt_wiek(prog)}' + (' (godziny robocze)' if kat == 'd' else '') + (', ponad 2× progu' if st == '❌' else ''))
        rows.append((label, st, w, txt, note))
    return rows


# ---------------------------------------------------------------- v131: szanse decyzji Fed (rynek zakładów) ----------------------------------------------------------------
FED_ETYKIETA = 'szanse decyzji Fed (rynek zakładów)'
FED_PROG = 90              # min — wiek cen (part_at.ks; automat co 20 min): żółte po progu, czerwone po 2× — osobny wiersz, lista SWIEZOSC bez zmian
FED_SUMA = (0.90, 1.10)    # suma surowych cen wyników posiedzenia poza tym pasmem = uwaga (informacja o jakości cen, bez koloru)


def fed_swiezosc(j, now=None):
    """Wiersz świeżości szans Fed (data/fed.json → part_at.ks) w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data, uwaga);
    brak pliku = None (wiersz pominięty; brak pliku zgłasza pętla wieku plików); wyłącznik KALSHI_OFF = status „—” z opisem (bez uwagi)."""
    if not isinstance(j, dict):
        return None
    if (j.get('ok') or {}).get('ks') == 'off':
        return (FED_ETYKIETA, '—', None, None, 'wyłączone (KALSHI_OFF)')
    v = (j.get('part_at') or {}).get('ks')
    if not isinstance(v, str):
        return (FED_ETYKIETA, '?', None, None, 'brak czasu cen w pliku')
    w = wiek_danych(v, 'ts', 'h', now)
    st = ocena(w, FED_PROG)
    note = '' if st == '✅' else (f'próg {fmt_wiek(FED_PROG)}' + (', ponad 2× progu' if st == '❌' else ''))
    return (FED_ETYKIETA, st, w, v, note)


def fed_uwagi(j):
    """Uwagi o jakości cen Fed (informacja): nieznane wyniki, brak ceny któregoś wyniku albo suma surowych cen posiedzenia poza FED_SUMA."""
    K = j.get('ks') if isinstance(j, dict) and isinstance(j.get('ks'), dict) else {}
    out = []
    for m in K.get('meetings') or []:
        if not isinstance(m, dict):
            continue
        d, s = str(m.get('date') or '?'), m.get('sum_raw')
        if m.get('unknown'):
            out.append(f'Fed {d}: nieznane wyniki ({len(m["unknown"])}) — szanse bez przeliczenia do 100%')
        if s is None:
            out.append(f'Fed {d}: nie każdy wynik ma cenę — surowe ceny bez przeliczenia do 100%')
        elif isinstance(s, (int, float)) and not FED_SUMA[0] <= s <= FED_SUMA[1]:
            out.append(f'Fed {d}: suma surowych cen {s:.3f} poza pasmem {FED_SUMA[0]:.2f}–{FED_SUMA[1]:.2f}')
    return out


# ---------------------------------------------------------------- v132: wycena BTC z łańcucha bloków (MVRV, SOPR) ----------------------------------------------------------------
# Dwa osobne wiersze świeżości (lista SWIEZOSC bez zmian): część cm (MVRV, średnia cena zakupu — dzień danych z wczoraj; dzień D pełny u źródła
# w D+1 ok. 03 UTC) i część bg (SOPR — źródło opóźnia darmowy plan o 7 dni, więc wiek ~6–7 dni jest normą; ten wiersz najwyżej ⚠️, nigdy ❌:
# to dodatek z darmowego planu, jego brak nie jest awarią strony). MVRV z dwóch źródeł (drugie źródło pobierane tylko do tej kontroli): różnica
# r = (drugie / główne − 1) × 100 dla wspólnych dni; norma = mediana r z okna (pomiar 27.09.2026 z 90 dni: mediana +0,84%, zakres +0,60…+1,63%,
# zmiana dzień do dnia p95 0,24 pkt proc.). ✅ gdy |r najnowszego dnia − mediana| ≤ WY_ZG_PP i |mediana| ≤ WY_ZG_MED; inaczej ⚠️ (nigdy błąd).
# Dodatkowe ⚠️, gdy po przesunięciu dat o ±1 dzień mediana |r| spada poniżej WY_ZG_SHIFT × mediany |r| bez przesunięcia — tak wyglądała historia
# drugiego źródła 2023-10…2025-08 (dzień d = dzień d+1 głównego); na historii od 2025-10 reguła nie zgłasza nic (sprawdzone na 341 oknach).
WY_ETYKIETA_CM = 'wycena BTC — MVRV, średnia cena zakupu (dziennie)'
WY_ETYKIETA_BG = 'SOPR BTC (źródło opóźnia 7 dni)'
WY_PROG_CM = 36 * 60          # min od końca dnia danych (kontrola o 06:20 UTC widzi zwykle wczoraj: ~6 h); ❌ po 2× progu
WY_PROG_BG = 9 * 24 * 60      # min od końca dnia danych SOPR (norma ~6 d 6 h); tylko ⚠️
WY_ZG_MIN = 20                # wspólnych dni MVRV — mniej = tylko informacja, bez koloru
WY_ZG_PP = 1.5                # pkt proc.
WY_ZG_MED = 3.0               # %
WY_ZG_SHIFT = 0.67            # przesunięcie dat: mediana |r| po przesunięciu < 0,67 × bez przesunięcia
WY_OPOZN = 7                  # dni opóźnienia darmowego planu drugiego źródła (pomiar 27.09.2026)


def wycena_swiezosc(j, now=None):
    """Wiersze świeżości wyceny BTC w kształcie wierszy swiezosc(): (etykieta, status, wiek min, data danych, uwaga). Brak pliku = [] (brak
    pliku zgłasza pętla wieku plików); SOPR wyłączony (WYCENA_BG_OFF) = status „—” z opisem (bez uwagi); SOPR nigdy ❌ (najwyżej ⚠️)."""
    if not isinstance(j, dict):
        return []
    rows = []
    C = j.get('cm') if isinstance(j.get('cm'), dict) else {}
    a = C.get('asof')
    if not isinstance(a, str) or len(a) != 10:
        rows.append((WY_ETYKIETA_CM, '?', None, None, 'brak dnia danych w pliku'))
    else:
        w = wiek_danych(a, 'day', 'c', now)      # 'c' = dni kalendarzowe (krypto bez przerwy na weekend)
        st = ocena(w, WY_PROG_CM)
        rows.append((WY_ETYKIETA_CM, st, w, a, '' if st == '✅' else f'próg {fmt_wiek(WY_PROG_CM)}' + (', ponad 2× progu' if st == '❌' else '')))
    B = j.get('bg') if isinstance(j.get('bg'), dict) else {}
    if B.get('off') or (j.get('ok') or {}).get('bg') == 'off':
        rows.append((WY_ETYKIETA_BG, '—', None, None, 'wyłączone (WYCENA_BG_OFF)'))
        return rows
    s = (B.get('sopr') or {}).get('asof') if isinstance(B.get('sopr'), dict) else None
    if not isinstance(s, str) or len(s) != 10:
        rows.append((WY_ETYKIETA_BG, '?', None, None, 'brak dnia danych SOPR w pliku'))
    else:
        w = wiek_danych(s, 'day', 'c', now)
        st = ocena(w, WY_PROG_BG)
        st = '⚠️' if st == '❌' else st
        rows.append((WY_ETYKIETA_BG, st, w, s, '' if st == '✅' else f'próg {fmt_wiek(WY_PROG_BG)} (dodatek z darmowego planu — najwyżej uwaga)'))
    return rows


def wycena_mvrv(j):
    """MVRV z dwóch źródeł (data/wycena.json: cm.d i bg.mvrv.d) → {'status', 'n', 'mediana_pct', 'dzien', 'roznica_pct', 'przesuniecie',
    'opoznienie_d', 'opis', 'uwagi'}. Tylko różnice procentowe i daty (bez liczb drugiego źródła); uwagi najwyżej ⚠️ — nigdy błąd."""
    out = {'status': '?', 'n': 0, 'mediana_pct': None, 'dzien': None, 'roznica_pct': None, 'przesuniecie': False, 'opoznienie_d': None,
           'opis': 'plik nie wczytany', 'uwagi': []}
    if not isinstance(j, dict):
        return out
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') and v > 0   # noqa: E731
    C = j.get('cm') if isinstance(j.get('cm'), dict) else {}
    B = j.get('bg') if isinstance(j.get('bg'), dict) else {}
    if B.get('off'):
        out.update(status='—', opis='drugie źródło wyłączone (WYCENA_BG_OFF)')
        return out
    a = {r[0]: float(r[1]) for r in (C.get('d') or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and num(r[1])}
    M = B.get('mvrv') if isinstance(B.get('mvrv'), dict) else {}
    b = {r[0]: float(r[1]) for r in (M.get('d') or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and num(r[1])}
    dl = B.get('delay_d')
    if isinstance(dl, int) and not isinstance(dl, bool):
        out['opoznienie_d'] = dl
        if dl != WY_OPOZN:
            out['uwagi'].append(f'SOPR BTC: źródło zmieniło opóźnienie planu darmowego: {dl} dni (było {WY_OPOZN})')
    wsp = sorted(set(a) & set(b))
    out['n'] = len(wsp)
    if len(wsp) < WY_ZG_MIN:
        out.update(status='ℹ️', opis=f'wspólnych dni {len(wsp)} z {WY_ZG_MIN} — bez oceny')
        return out
    r = [(b[d] / a[d] - 1) * 100 for d in wsp]
    med, last = statistics.median(r), r[-1]
    out.update(mediana_pct=round(med, 3), dzien=wsp[-1], roznica_pct=round(last, 3))

    def mabs(k):
        v = [abs(b[d] / a[x] - 1) * 100 for d in wsp for x in [(dt.date.fromisoformat(d) + dt.timedelta(days=k)).isoformat()] if x in a]
        return statistics.median(v) if v else None
    m0, mk = mabs(0), [m for m in (mabs(-1), mabs(1)) if m is not None]
    out['przesuniecie'] = bool(mk) and m0 is not None and min(mk) < WY_ZG_SHIFT * m0
    ok = abs(last - med) <= WY_ZG_PP and abs(med) <= WY_ZG_MED
    out['status'] = '✅' if ok and not out['przesuniecie'] else '⚠️'
    out['opis'] = f'odchylenie najnowszego dnia od normy {abs(last - med):.2f} pkt proc. (próg {WY_ZG_PP:g}), norma {med:+.2f}% (próg ±{WY_ZG_MED:g}%)'
    if not ok:
        out['uwagi'].append(f'MVRV: dwa źródła różnią się o {last:+.2f}% ({wsp[-1]}) wobec normy {med:+.2f}% (mediana {len(wsp)} dni)')
    if out['przesuniecie']:
        out['uwagi'].append('MVRV: możliwe przesunięcie dat o 1 dzień u jednego ze źródeł (po przesunięciu różnice wyraźnie mniejsze)')
    return out


# ---------------------------------------------------------------- v115: zgodność liczb ----------------------------------------------------------------
ZG_KOL = ['date', 'cap_gap_pct', 'tga_gap_pct']   # kontrola/zgodnosc.csv: tylko różnice procentowe (bez wartości źródeł); puste pole = brak odczytu


def zgodnosc_csv(path):
    """{dzień: {'cap': %, 'tga': %}} — pusta komórka = brak (klucz pominięty)."""
    rows = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8', newline='') as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) >= 2 and row[0] != 'date':
                    rec = {}
                    for i, kk in ((1, 'cap'), (2, 'tga')):
                        try:
                            rec[kk] = float(row[i])
                        except (ValueError, IndexError):
                            pass
                    rows[row[0]] = rec
    return rows


def zgodnosc_zapisz(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        wtr = csv.writer(f, lineterminator='\n'); wtr.writerow(ZG_KOL)
        for d in sorted(rows):
            wtr.writerow([d] + [('%.3f' % rows[d][kk]) if isinstance(rows[d].get(kk), (int, float)) else '' for kk in ('cap', 'tga')])


def mediana_ocena(rows, kk, gap, today, zolte, czerwone):
    """rows: dzień → {kk: różnica %} z poprzednich dni; gap: dzisiejsza różnica. Zwraca (status, mediana, n, opis) — żółte/czerwone,
    gdy dzisiejsza różnica odbiega od mediany ostatnich ZG_DNI dni o więcej niż progi (pkt proc.); < ZG_MIN dni historii = tylko informacja."""
    hist = [v[kk] for d, v in sorted(rows.items()) if d < today and isinstance(v.get(kk), (int, float))][-ZG_DNI:]
    if gap is None:
        return '?', None, len(hist), 'brak odczytu'
    if len(hist) < ZG_MIN:
        return 'ℹ️', (statistics.median(hist) if hist else None), len(hist), f'historia {len(hist)} z {ZG_MIN} dni — bez oceny'
    med = statistics.median(hist)
    d = abs(gap - med)
    st = '❌' if (czerwone is not None and d > czerwone) else ('⚠️' if d > zolte else '✅')
    return st, med, len(hist), f'odchylenie od mediany {d:.2f} pkt proc. (progi {zolte:g}' + (f' / {czerwone:g}' if czerwone is not None else '') + ')'


def kapitalizacja(rows, gap, today):
    return mediana_ocena(rows, 'cap', gap, today, ZG_ZOLTE, ZG_CZERWONE)


def procent(a, b):
    try:
        return abs(a - b) / abs(b) * 100.0 if b else None
    except Exception:
        return None


def tga_porownanie(inst, fred):
    """Ostatnia wspólna data Fiscal Data (instytucje.tga.d) i FRED WTREGEN (obie w mln USD) → (data, fiscal, fred, różnica %)."""
    try:
        a = {str(r[0]): float(r[1]) for r in inst['tga']['d'] if isinstance(r, list) and len(r) >= 2 and r[1] is not None}
        b = {str(r[0]): float(r[1]) for r in fred['series']['WTREGEN']['d'] if isinstance(r, list) and len(r) >= 2 and r[1] is not None}
    except Exception:
        return None
    wspolne = sorted(set(a) & set(b))
    if not wspolne:
        return None
    d = wspolne[-1]
    return d, a[d], b[d], procent(a[d], b[d])


def etf_porownanie(ceny, ix):
    """14 symboli ETF mapy: ostatnia wspólna data zamknięcia w ceny.json (Twelve Data, `q[SYM].d = [[data, close, wolumen]]`) i w indeksy.json
    (`etf.q[SYM] = [[data, close]]`, Massive/Tiingo) → lista (symbol, data, a, b, różnica %); symbol bez wspólnej daty = pominięty. None = brak plików."""
    try:
        q1, q2 = ceny['q'], ix['etf']['q']
    except Exception:
        return None
    out = []
    for sym, rec in q1.items():
        d1 = {str(r[0]): float(r[1]) for r in ((rec.get('d') if isinstance(rec, dict) else None) or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[1], (int, float))}
        d2 = {str(r[0]): float(r[1]) for r in (q2.get(sym) or []) if isinstance(r, list) and len(r) >= 2 and isinstance(r[1], (int, float))}
        wsp = sorted(set(d1) & set(d2))
        if wsp:
            d = wsp[-1]; out.append((sym, d, d1[d], d2[d], procent(d1[d], d2[d])))
    return out


def wieloryby_porownanie(path):
    """archiwum/wieloryby.csv: dla ostatniego dnia z poprzednim dniem — |zmiana salda − przelewy netto| na giełdę i aktywo; zmiana salda liczona
    w jednostkach aktywa po dzisiejszym kursie (saldo w USD zmienia się też przez kurs ETH, a to nie przelew). Pusta komórka przepływów (brak sum
    dobowych) = para pominięta. Zwraca (dzień, poprzedni, lista (giełda, aktywo, zmiana, netto, rozbieżność) ponad progiem, liczba porównanych) albo None."""
    if not os.path.exists(path):
        return None
    by = {}
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f); head = next(r, None)
        if not head or head[:5] != ['date', 'exchange', 'asset', 'balance', 'balance_usd']:
            return None
        for row in r:
            if len(row) >= 8:
                by.setdefault(row[0], {})[(row[1], row[2])] = row
    days = sorted(by)
    if len(days) < 2:
        return None
    d, p = days[-1], days[-2]
    zle, n = [], 0
    for k, row in by[d].items():
        prev = by[p].get(k)
        if not prev:
            continue
        try:
            u, u0, usd, net = float(row[3]), float(prev[3]), float(row[4]), float(row[7])
        except ValueError:
            continue
        if not u:
            continue
        n += 1
        delta = (u - u0) * (usd / u)   # zmiana w jednostkach × dzisiejszy kurs — ruch kursu ETH nie jest przelewem (v117)
        roz = abs(delta - net)
        if roz > WH_MIN_USD and roz > WH_PROG / 100 * max(abs(delta), abs(net), WH_MIN_USD):
            zle.append((k[0], k[1], delta, net, roz))
    return d, p, zle, n


PR_USDC_PP = 0.10    # v128: pkt proc. — premia USA przez USDT (poprawiona) vs przez parę z USDC; większa różnica = uwaga (kurs USDT albo USDC odbiega od dolara?)
PR_CB_MAX = 2.0      # % — |premia USA| ponad to = możliwy zły odczyt (uwaga)
PR_STARE_H = 3       # h — ostatnia minuta odczytu starsza, choć plik młody = giełdy nie odpowiadają (uwaga)
PR_KR_MAX, PR_USDT_MAX = 10.0, 5.0   # v129: % — |premia Korei BTC/ETH| i |USDT w Korei| ponad to = możliwy zły odczyt (uwaga)
PR_FX_PCT = 0.01     # v129: % — kurs KRW/USD wprost vs ten sam kurs w pliku rynki (ta sama data); większa różnica = uwaga


def premie_porownanie(prem, rynki=None, now=None):
    """v128: zgodność premii krypto bez sieci (plik premie.json; v129 także rynki.json) → {'opis', 'uwagi', 'cb_usdc_pp'}.
    Tylko uwagi (⚠️), nigdy błąd: dziwny rynek to nie awaria strony."""
    now = now or NOW
    out = {'opis': '', 'uwagi': [], 'cb_usdc_pp': None}
    if not isinstance(prem, dict):
        out['opis'] = 'plik nie wczytany'
        return out
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731
    N = prem.get('now') if isinstance(prem.get('now'), dict) else {}
    cb = N.get('cb') if isinstance(N.get('cb'), dict) else {}
    txt = []
    b = cb.get('btc') if isinstance(cb.get('btc'), dict) else {}
    p, u = b.get('p'), b.get('usdc')
    if num(p) and num(u):
        g = round(abs(p - u), 3); out['cb_usdc_pp'] = g
        txt.append(f'USA BTC {p:+.2f}% (przez USDC {u:+.2f}%, różnica {g:.2f} pkt proc.)')
        if g > PR_USDC_PP:
            out['uwagi'].append(f'premia USA: przeliczenie przez USDT i przez USDC różni się o {g:.2f} pkt proc. (próg {PR_USDC_PP:g}) — kurs USDT albo USDC odbiega od dolara?')
    for c in ('btc', 'eth'):
        x = (cb.get(c) or {}).get('p') if isinstance(cb.get(c), dict) else None
        if num(x) and abs(x) > PR_CB_MAX:
            out['uwagi'].append(f'premia USA {c.upper()} {x:+.2f}% (ponad ±{PR_CB_MAX:g}%) — możliwy zły odczyt')
    last = max((B['win'][1] for B in N.values() if isinstance(B, dict) and isinstance(B.get('win'), list) and len(B['win']) == 2
                and isinstance(B['win'][1], str)), default=None)
    wp = wiek_danych(prem.get('at'), 'ts', 'h', now) if isinstance(prem.get('at'), str) else None
    wm = wiek_danych(last, 'ts', 'h', now) if last else None
    if wp is not None and wp <= LIMIT_MIN['premie'] and (wm is None or wm > PR_STARE_H * 60):
        out['uwagi'].append('premie krypto: giełdy nie odpowiadają — ' + (f'ostatnia minuta odczytu {last} UTC ({fmt_wiek(wm)} temu)' if last else 'brak odczytu') + ', choć plik jest świeży')
    # v129: Korea — (c) |premia BTC/ETH| > PR_KR_MAX %, |USDT| > PR_USDT_MAX % = możliwy zły odczyt; (b) kurs EBC wprost vs ten sam kurs
    # w pliku rynki (ta sama data): różnica > PR_FX_PCT % = uwaga (plik rynki zmienił metodę kursu?)
    kr = N.get('kr') if isinstance(N.get('kr'), dict) else {}
    for c, lim in (('btc', PR_KR_MAX), ('eth', PR_KR_MAX), ('usdt', PR_USDT_MAX)):
        x = (kr.get(c) or {}).get('p') if isinstance(kr.get(c), dict) else None
        if num(x):
            if c == 'btc':
                txt.append(f'Korea BTC {x:+.2f}% (kurs z {kr.get("fx_d") or "—"})')
            if abs(x) > lim:
                out['uwagi'].append(f'premia Korei {c.upper()} {x:+.2f}% (ponad ±{lim:g}%) — możliwy zły odczyt')
    fx = prem.get('fx') if isinstance(prem.get('fx'), dict) else {}
    fr = ((rynki.get('fx') or {}).get('now') or {}) if isinstance(rynki, dict) and isinstance(rynki.get('fx'), dict) else {}
    a, b2 = fx.get('v'), (fr.get('rates') or {}).get('KRW') if isinstance(fr.get('rates'), dict) else None
    out['fx_gap_pct'] = None
    if fx.get('src') == 'ecb' and num(a) and num(b2) and b2 > 0 and fx.get('d') == fr.get('date'):
        g = abs(a / b2 - 1) * 100; out['fx_gap_pct'] = round(g, 4)
        txt.append(f'kurs KRW/USD {fx["d"]}: wprost {a:.3f}, w pliku rynki {b2:.3f} (różnica {g:.3f}%)')
        if g > PR_FX_PCT:
            out['uwagi'].append(f'kurs KRW/USD {fx["d"]}: kurs wprost {a:.3f} i kurs z pliku rynki {b2:.3f} różnią się o {g:.3f}% (próg {PR_FX_PCT:g}%) — plik rynki zmienił metodę kursu?')
    out['opis'] = '; '.join(txt) or 'brak odczytu'
    return out


def czerwone_z_historii(hist, n=None):
    """Błędy zbieracza w n kolejnych kontrolach z RÓŻNYCH dni UTC (kontrola rusza też po pushu — kilka przebiegów jednego dnia to nie „3 dni z rzędu”)."""
    n = HIST_CZERWONE if n is None else n
    ost = {}
    for h in hist:
        if isinstance(h, dict) and isinstance(h.get('at'), str):
            ost[h['at'][:10]] = h   # ostatni przebieg dnia
    dni = sorted(ost)[-n:]
    return len(dni) >= n and all((ost[d].get('bledy_zbieracza') or 0) > 0 for d in dni)


def historia(path, wpis):
    """Dopisuje wpis do kontrola/historia.json (ostatnie HIST_N) i zwraca całą listę (najnowszy na końcu)."""
    hist = []
    try:
        with open(path, encoding='utf-8') as f:
            hist = json.load(f)
        if not isinstance(hist, list):
            hist = []
    except Exception:
        hist = []
    hist = [h for h in hist if isinstance(h, dict) and h.get('at') != wpis.get('at')] + [wpis]
    hist = hist[-HIST_N:]
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=0)
    return hist


def pl_przebiegi(n):
    """Liczebnik: 1 nieudany przebieg / 2–4 nieudane przebiegi / 5+ (i 12–14) nieudanych przebiegów."""
    if n == 1:
        return '1 nieudany przebieg'
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f'{n} nieudane przebiegi'
    return f'{n} nieudanych przebiegów'


def pl_udane(n):
    """Liczebnik: 1 udany przebieg / 2–4 udane przebiegi / 0, 5+ (i 12–14) udanych przebiegów."""
    if n == 1:
        return '1 udany przebieg'
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f'{n} udane przebiegi'
    return f'{n} udanych przebiegów'


def opis_kroku(zadanie, krok):
    """Nazwa nieudanego kroku po ludzku: publikacja GitHub Pages to zwykle chwilowa awaria po stronie GitHuba; długie nazwy kroków
    z workflow skrócone do części przed nawiasem / myślnikiem."""
    if not krok:
        return zadanie or None
    if 'deploy-pages' in krok:
        return 'publikacja na GitHub Pages (zwykle chwilowa awaria po stronie GitHuba)'
    k = krok.split(' (')[0].split(' — ')[0].strip()
    return f'{zadanie} / {k}' if zadanie else k


def przebiegi_ocena(runs, now, kroki=None):
    """v124.1: przebiegi automatu („Strona i dane”) z ostatnich 24 h → (actions, bledy, uwagi).
    BŁĄD tylko, gdy automat NADAL nie działa: dwa ostatnie zakończone przebiegi nieudane albo ≥ 3 porażki w 24 h i ostatni zakończony
    też nieudany. Jedna świeża porażka = uwaga („kolejny przebieg za ok. 20 min”). Porażki już naprawione (po ostatniej same udane) =
    uwaga z godzinami, krokiem i liczbą udanych przebiegów od ostatniej porażki. Przebiegi w toku i anulowane nie liczą się do serii.
    kroki: {id przebiegu: opis kroku} dla porażek (z API zadań; może brakować — wtedy sama godzina)."""
    kroki = kroki or {}
    od = now - dt.timedelta(hours=24)

    def czas(r):
        try:
            t = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
            return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        except Exception:
            return None
    ost = [r for r in runs if isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and czas(r) is not None and czas(r) >= od]
    ost.sort(key=czas, reverse=True)
    z = {}
    for r in ost:
        w = r.get('conclusion') or r.get('status')
        z[w] = z.get(w, 0) + 1
    zak = [r for r in ost if r.get('status') == 'completed' and r.get('conclusion') in ('success', 'failure')]
    por = [r for r in ost if r.get('conclusion') == 'failure']
    z_rzedu = next((i for i, r in enumerate(zak) if r.get('conclusion') != 'failure'), len(zak))
    udane_po = next((i for i, r in enumerate(zak) if r.get('conclusion') == 'failure'), len(zak)) if por else None
    A = {'przebiegi_24h': len(ost), 'wg_wyniku': z, 'ostatni': ost[0].get('run_started_at') if ost else None,
         'ostatnia_porazka': por[0].get('run_started_at') if por else None, 'porazki_z_rzedu': z_rzedu, 'udane_po_porazce': udane_po,
         'porazki': [{'at': r.get('run_started_at'), 'krok': kroki.get(r.get('id'))} for r in por[:10]]}
    bledy, uwagi = [], []
    if por:
        c = [czas_pl(p['at']) for p in A['porazki'][:5]]
        lista = ', '.join((x[:5] + ' ' + x[-5:] if x != '—' else x) + (f' ({p["krok"]})' if p.get('krok') else '') for x, p in zip(c, A['porazki']))
        lista += f' i {len(por) - 5} wcześniejsze' if len(por) > 5 else ''
        if z_rzedu >= 2 or (len(por) >= 3 and z_rzedu >= 1):
            bledy.append(f'automat nie działa: {pl_przebiegi(len(por))} w 24 h, ostatnie {z_rzedu} z rzędu — strona nie odświeża danych ({lista})')
        elif z_rzedu == 1:
            uwagi.append(f'ostatni przebieg automatu nieudany ({lista}) — kolejny za ok. 20 min; dwa nieudane z rzędu = błąd')
        else:
            uwagi.append(f'{pl_przebiegi(len(por))} automatu w 24 h — już naprawione: od ostatniej porażki {pl_udane(udane_po)} z rzędu ({lista})')
    if len(ost) < 20:
        uwagi.append(f'tylko {len(ost)} przebiegów w 24 h (harmonogram co 20 min ≈ 72; GitHub bywa opóźniony)')
    return A, bledy, uwagi


# ---------------------------------------------------------------- v130: ETF krypto u źródła (pliki emitenta) ----------------------------------------------------------------
def _em_liczba(s):
    """'1,234.56' → 1234.56; '--', '', 'N/A', zero, ujemne, nieskończone → None (brak, nie zero)."""
    try:
        v = float(str(s).replace(',', '').strip())
    except ValueError:
        return None
    return v if 0 < v < float('inf') else None


def _em_skonczona(v):
    """Liczba skończona (bez bool, NaN, ∞) albo None."""
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float('inf') else None


def emitent_historia(raw):
    """Plik funduszu emitenta (Excel 2003 XML, bajty) → {data ISO: (NAV, liczba jednostek)} z arkusza „Historical”. Wiersze z „--”, pustą
    komórką albo złą datą pominięte; komórki z ss:Index (przerwa w wierszu) na właściwym miejscu. Wyjątek, gdy brak arkusza albo nagłówka."""
    ns = '{urn:schemas-microsoft-com:office:spreadsheet}'
    txt = raw.decode('utf-8-sig', 'replace') if isinstance(raw, bytes) else str(raw)
    txt = re.sub(r'&(?!(amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)', '&amp;', txt)   # gołe „&” w nazwach spółek (jak w zbieraczu)
    ws = next((w for w in ET.fromstring(txt).iter(ns + 'Worksheet') if w.get(ns + 'Name') == 'Historical'), None)
    if ws is None:
        raise ValueError('brak arkusza Historical')
    head, out = None, {}
    for row in ws.iter(ns + 'Row'):
        c = []
        for x in row.iter(ns + 'Cell'):
            ix = x.get(ns + 'Index')
            if ix and ix.isdigit():
                c += [''] * max(0, int(ix) - 1 - len(c))
            d = x.find(ns + 'Data')
            c.append(((d.text if d is not None else '') or '').strip())
        if head is None:
            if 'As Of' in c and 'NAV per Share' in c and 'Shares Outstanding' in c:
                head = (c.index('As Of'), c.index('NAV per Share'), c.index('Shares Outstanding'))
            continue
        try:
            d = dt.datetime.strptime(c[head[0]], '%b %d, %Y').date().isoformat()
        except (ValueError, IndexError):
            continue
        nav = _em_liczba(c[head[1]]) if len(c) > head[1] else None
        sh = _em_liczba(c[head[2]]) if len(c) > head[2] else None
        if nav and sh:
            out[d] = (nav, sh)
    if head is None:
        raise ValueError('arkusz Historical bez nagłówka As Of / NAV per Share / Shares Outstanding')
    return out


def emitent_sesje(etf, a):
    """Daty sesji z data/etf.json (assets[a].day = [[znacznik północy UTC, mln]]) — kalendarz do wykrycia braku wiersza w pliku emitenta."""
    out = set()
    A = ((etf.get('assets') if isinstance(etf, dict) else None) or {})
    A = A.get(a) if isinstance(A, dict) else None
    for r in ((A.get('day') if isinstance(A, dict) else None) or []):
        try:
            out.add(dt.datetime.fromtimestamp(r[0], dt.timezone.utc).date().isoformat())
        except (TypeError, ValueError, OverflowError, OSError, IndexError, KeyError):
            pass
    return out


def emitent_przeplywy(hist, sesje=()):
    """{data: (NAV, jednostki)} → ({dzień D: przepływ w mln USD}, {dzień D: powód pominięcia}); D = (S[D+1] − S[D]) × NAV[D] / 1e6, gdzie D+1
    to następny wiersz pliku. Wiersz identyczny z poprzednim (dzień wolny w USA) usunięty; ostatni wiersz bez przepływu (jeszcze go nie ma).
    Pominięty dzień, gdy następny wiersz jest dalej niż EM_PRZERWA dni albo między nimi jest sesja z `sesje` (brak wiersza w pliku), albo gdy
    NAV skacze o więcej niż EM_NAV_SKOK % (podział jednostek?)."""
    rows = sorted(hist.items())
    rows = rows[:1] + [b for a, b in zip(rows, rows[1:]) if b[1] != a[1]]
    ss = sorted(sesje)
    out, pom = {}, {}
    for (d, (nav, sh)), (n, (nav2, sh2)) in zip(rows, rows[1:]):
        if (dt.date.fromisoformat(n) - dt.date.fromisoformat(d)).days > EM_PRZERWA or any(d < s < n for s in ss):
            pom[d] = f'w pliku emitenta brak sesji po {d}'
        elif abs(nav2 / nav - 1) * 100 > EM_NAV_SKOK:
            pom[d] = 'skok NAV (podział jednostek?)'
        else:
            out[d] = (sh2 - sh) * nav / 1e6
    return out, pom


def emitent_zapis(path):
    """kontrola/etf-emitent.csv → {(data, symbol): [liczba ze strony | None, czas odczytu | None]}; pusta komórka = brak (nie zero).
    Inny nagłówek = zapis od nowa (bez mieszania kolumn)."""
    rows = {}
    if not os.path.exists(path):
        return rows
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        if next(r, None) != EM_KOL:
            return rows
        for row in r:
            if len(row) < 4 or not row[1]:
                continue
            try:
                d = dt.date.fromisoformat(row[0]).isoformat()
                v = _em_skonczona(float(row[2])) if row[2] != '' else None
            except ValueError:
                continue
            rows[(d, row[1])] = [v, row[3] or None]
    return rows


def emitent_zapis_zapisz(path, rows):
    """Zapis ostatnich EM_DNI dat, rosnąco po dacie i symbolu; brak = pusta komórka."""
    daty = set(sorted({d for d, _ in rows})[-EM_DNI:])
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n'); w.writerow(EM_KOL)
        for d, t in sorted(k for k in rows if k[0] in daty):
            v, at = rows[(d, t)]
            w.writerow([d, t, (('%.6f' % (round(v, 6) + 0.0)).rstrip('0').rstrip('.') if v is not None else ''), at or ''])


def emitent_odczyt(rows, etf):
    """Dopisuje do zapisu przepływy funduszy EM_FUNDS pokazane na stronie (etf.json, `asof` aktywa). Ta sama data i symbol = nadpisanie
    (wygrywa najpóźniejszy odczyt), ale brak (None) nie kasuje liczby zapisanej wcześniej. Zwraca symbole, których nie ma na liście funduszy strony."""
    brak = []
    if not isinstance(etf, dict):
        return brak
    at = etf.get('at') if isinstance(etf.get('at'), str) else None
    assets = etf.get('assets') if isinstance(etf.get('assets'), dict) else {}
    for t, a, _ in EM_FUNDS:
        A = assets.get(a)
        if not isinstance(A, dict) or not isinstance(A.get('asof'), str):
            continue
        try:
            d = dt.date.fromisoformat(A['asof'][:10]).isoformat()
        except ValueError:
            continue
        funds = [f for f in (A.get('funds') if isinstance(A.get('funds'), list) else []) if isinstance(f, dict)]
        f = next((f for f in funds if f.get('t') == t), None)
        if f is None and funds:
            brak.append(t)
        v = _em_skonczona(f.get('d1')) if f else None
        old = rows.get((d, t))
        if v is not None or old is None or old[0] is None:
            rows[(d, t)] = [v, at]
    return brak


def emitent_porownanie(zap, przep, pom, plik_do, sesje=()):
    """zap: {data: [liczba ze strony | None, czas odczytu]} jednego funduszu; przep, pom: z emitent_przeplywy; plik_do: ostatni dzień pliku;
    sesje: kalendarz sesji strony (emitent_sesje). Okno = ostatnie EM_SESJE zapisanych dat sprzed plik_do (późniejsze czekają na następny wiersz
    pliku). Brak liczby na stronie albo dzień bez wyliczenia = pominięty z powodem (nigdy 0). Zaległość = sesje strony (kalendarz i zapis) nowsze
    niż plik_do; ponad EM_ZALEGLOSC = plik nieaktualny (np. stara kopia pliku z kodem 200) — wtedy okno to tylko stare sesje, a nowsze czekają.
    Status: ✅ zgodne; ⚠️ różnica ponad próg w oknie; ℹ️ jeszcze nic do porównania; ? są daty w oknie, ale żadnej nie da się porównać, albo plik
    nieaktualny (różnica ⚠️ ma pierwszeństwo). Tylko różnice i daty (bez liczb emitenta)."""
    okno = sorted(d for d in zap if d < plik_do)[-EM_SESJE:]
    daty, pomin, roz, maxr = [], [], [], None
    for d in okno:
        a = zap[d][0]
        if a is None:
            pomin.append({'data': d, 'powod': 'brak liczby na stronie'}); continue
        if d not in przep:
            pomin.append({'data': d, 'powod': pom.get(d, 'brak tej sesji w pliku emitenta')}); continue
        b = przep[d]; r = a - b
        daty.append(d); maxr = abs(r) if maxr is None else max(maxr, abs(r))
        if abs(r) > max(EM_TOL_MLN, EM_TOL_PCT / 100 * abs(b)):
            roz.append({'data': d, 'roznica_mln': round(r, 1) + 0.0, 'roznica_pct': (round(r / abs(b) * 100, 1) + 0.0) if b else None,
                        'strona_zero': a == 0})
    po = sorted({d for d in zap if d > plik_do} | {s for s in sesje if s > plik_do})   # sesje strony, których plik emitenta jeszcze nie ma
    stary = len(po) > EM_ZALEGLOSC
    st = ('⚠️' if roz else '✅') if daty else ('?' if pomin else 'ℹ️')
    if stary and st != '⚠️':
        st = '?'
    return {'status': st, 'porownane': len(daty), 'od': daty[0] if daty else None, 'do': daty[-1] if daty else None,
            'max_roznica_mln': (round(maxr, 2) + 0.0) if maxr is not None else None, 'roznice': roz, 'pominiete': pomin,
            'czeka': sorted(d for d in zap if d >= plik_do), 'plik_do': plik_do, 'zaleglosc': len(po), 'strona_do': po[-1] if po else None,
            'nieaktualny': stary}


def _em_roznica(x):
    return (f'{x["data"]}: {x["roznica_mln"]:+.1f} mln USD' + (f' ({x["roznica_pct"]:+.1f}%)' if x.get('roznica_pct') is not None else '')
            + (' — strona pokazywała 0.0 (możliwe opóźnienie publikacji funduszu)' if x.get('strona_zero') else ''))


def emitent_linia(t, F):
    """Fragment linii raportu dla jednego funduszu: status, porównane sesje, różnice i pominięte daty, a zawsze też ostatni dzień pliku emitenta,
    liczba nowszych sesji strony (zaległość pliku) i zapisane sesje czekające na porównanie. Brak = „—”; bez liczb emitenta."""
    if F.get('blad'):
        return f'{t} ? brak odczytu pliku ({F["blad"]})'
    st, pom, cz = F.get('status') or '?', F.get('pominiete') or [], F.get('czeka') or []
    if F.get('porownane'):
        mx = f'{F["max_roznica_mln"]:.1f} mln USD' if F.get('max_roznica_mln') is not None else '—'
        okr = F['od'] if F.get('od') == F.get('do') else f'{F["od"]} – {F["do"]}'
        s = (f'{t} {st} porównane sesje: {F["porownane"]} ({okr}), różnic ponad próg: {len(F["roznice"])}, największa różnica {mx}'
             + (' — ' + '; '.join(_em_roznica(x) for x in F['roznice'][-EM_SESJE:]) if F['roznice'] else ''))
        if pom:
            s += '; pominięte: ' + ', '.join(f'{x["data"]} ({x["powod"]})' for x in pom[-3:])
    elif pom:
        s = f'{t} {st} zapisane sesje bez porównania: ' + ', '.join(f'{x["data"]} ({x["powod"]})' for x in pom[-3:])
    else:
        s = f'{t} {st} jeszcze bez porównania'
    s += f'; plik emitenta do {F.get("plik_do") or "—"}, nowszych sesji na stronie: ' + (str(F['zaleglosc']) if F.get('zaleglosc') is not None else '—')
    if F.get('nieaktualny'):
        s += f' — plik nieaktualny (próg {EM_ZALEGLOSC}), te sesje bez porównania'
    return s + f'; czeka na porównanie: {len(cz)}' + (' (' + ('…, ' if len(cz) > 3 else '') + ', '.join(cz[-3:]) + ')' if cz else '')


def etf_emitent(files, R):
    """Krok 3e kontroli: zapis przepływów IBIT i ETHA ze strony, 2 zapytania o pliki emitenta (bez ponawiania), porównanie → słownik do
    R['zgodnosc']['etf_emitent']; uwagi dopisane do R['uwagi'] (nigdy do listy błędów)."""
    path = os.path.join(OUT_DIR, EM_CSV)
    zap = emitent_zapis(path)
    for t in emitent_odczyt(zap, files.get('etf')):
        R['uwagi'].append(f'ETF {t}: funduszu nie ma na liście funduszy strony (etf.json) — lista ucięta albo zmiana symbolu')
    try:
        emitent_zapis_zapisz(path, zap)
    except Exception as e:  # noqa
        R['uwagi'].append(f'{EM_CSV}: nie zapisano ({str(e)[:80]})')
    E = {'fundusze': {}, 'zapis_dni': len({d for d, _ in zap})}
    for i, (t, a, pid) in enumerate(EM_FUNDS):
        if i:
            time.sleep(EM_PAUZA)
        try:
            st, body, ms = get(EM_DOC.format(pid=pid), timeout=EM_TIMEOUT)
            hist = emitent_historia(body)
            if not hist:
                raise ValueError('arkusz Historical bez wierszy z liczbami')
        except urllib.error.HTTPError as e:
            F = {'status': '?', 'blad': f'HTTP {e.code}'}
        except Exception as e:  # noqa
            F = {'status': '?', 'blad': (str(e) or type(e).__name__)[:120]}
        else:
            ses = emitent_sesje(files.get('etf'), a)
            przep, pom = emitent_przeplywy(hist, ses)
            F = emitent_porownanie({d: v for (d, tt), v in zap.items() if tt == t}, przep, pom, max(hist), ses)
            F['ms'] = ms
        E['fundusze'][t] = F
        if F.get('blad'):
            R['uwagi'].append(f'ETF {t}: plik emitenta — brak odczytu ({F["blad"]}); porównanie przepływów pominięte')
            continue
        if F['status'] == '⚠️':
            R['uwagi'].append(f'ETF {t}: przepływ na stronie ≠ wyliczenie z pliku emitenta (próg max {EM_TOL_MLN:g} mln USD / {EM_TOL_PCT:g}%) — '
                              + '; '.join(_em_roznica(x) for x in F['roznice'][-3:]))
        elif F['pominiete'] and not F['porownane']:
            R['uwagi'].append(f'ETF {t}: zapisanych sesji nie da się porównać z plikiem emitenta — '
                              + ', '.join(f'{x["data"]} ({x["powod"]})' for x in F['pominiete'][-3:]))
        if F['nieaktualny']:   # stara kopia pliku (kod 200) nie może dawać wiecznego ✅ na starych sesjach
            R['uwagi'].append(f'ETF {t}: plik emitenta kończy się na {F["plik_do"]}, a strona ma już {F["zaleglosc"]} nowszych sesji (do {F["strona_do"]}) — '
                              f'plik nieaktualny (próg {EM_ZALEGLOSC}), te sesje bez porównania')
    sts = [F['status'] for F in E['fundusze'].values()]
    E['status'] = next((s for s in ('⚠️', '?', '✅') if s in sts), 'ℹ️')
    return E


# ---------------------------------------------------------------- v136: kursy dolara Ameryki Łacińskiej (data/dolar.json) ----------------------------------------------------------------
DL_ETYKIETA = 'kursy dolara Ameryki Łacińskiej (co godzinę)'
DL_PROG = 180              # min — wiek najnowszej części pliku (part_at.ar/ve/bo; automat co 55 min): po progu ⚠️, nigdy ❌ — osobny wiersz, lista SWIEZOSC bez zmian
DL_PARY = (('blue', 'blue', 0.5), ('mayorista', 'hurtowy', 0.5), ('oficial', 'oficjalny w banku', 0.5), ('bolsa', 'MEP', 2.0), ('contadoconliqui', 'CCL', 2.0))
DL_DUZA = {0.5: 1.5, 2.0: 4.0}   # % — ponad to różnica dwóch odczytów jest „duża” (dopisek przy ⚠️; nigdy ❌ ani BŁĄD)
DL_DNI = 3                 # dni — znaczniki dwóch odczytów dalej od siebie = „?” (bez oceny: porównanie różnych sesji)
DL_BCRA = 'https://api.bcra.gob.ar/estadisticascambiarias/v1.0/Cotizaciones/USD?fechadesde={a}&fechahasta={b}'   # bez klucza, dni robocze
DL_BCRA_PROG = 0.3         # % — kurs hurtowy z pliku vs kurs banku centralnego Argentyny z tego samego dnia (27.09: 1525,5 = 1525,5)
DL_LUKA_MAX = {'ar': 60.0, 've': 300.0}   # % — większa luka = możliwy błąd skali, który przeszedł przez zakres stosunku kursów (uwaga)
DL_LUKA_DNI = 4            # dni — najstarszy kurs głównej luki (AR: CCL i hurtowy, VE: równoległy i data kursu banku, BO: USDT i oficjalny) starszy = ⚠️
DL_KRAJE = (('ar', 'Argentyna'), ('ve', 'Wenezuela'), ('bo', 'Boliwia'))
DL_TZ_K = {'ar': -3, 've': -4, 'bo': -4}   # jak w zbieraczu: kurs „sama data” (północ UTC) liczony od końca tego dnia w kraju


def _dl_kurs(q):
    """Kurs z pliku: [kupno | None, sprzedaż > 0, znacznik, …]."""
    return isinstance(q, list) and len(q) >= 3 and isinstance(q[1], (int, float)) and not isinstance(q[1], bool) and q[1] > 0


def _dl_czas(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return t if t.tzinfo else None
    except (TypeError, ValueError):
        return None


def _dl_od(stamp, cc):
    """Chwila, od której liczymy wiek kursu (jak dl_qtime w zbieraczu): znacznik; „sama data” (północ UTC albo RRRR-MM-DD) — koniec tego dnia w kraju."""
    s = str(stamp or '')
    if len(s) == 10:
        s += 'T00:00:00Z'
    t = _dl_czas(s)
    if t is not None and t.utcoffset() == dt.timedelta(0) and (t.hour, t.minute, t.second, t.microsecond) == (0, 0, 0, 0):
        return t + dt.timedelta(days=1) - dt.timedelta(hours=DL_TZ_K[cc])
    return t


def dolar_luki(dl, now=None):
    """v136, przegląd: główne luki strony (AR: CCL wobec hurtowego, VE, BO) — ⚠️, gdy luki brak (strona pokazuje „—”) albo gdy najstarszy z jej
    kursów jest starszy niż DL_LUKA_DNI dni W CHWILI KONTROLI (wiek z dat samych kursów, nie z part_at — kraj z błędem ma stary part_at, ale też
    kraj bez błędu może mieć zatrzymane kursy). Tylko uwagi, nigdy ❌. → ({kraj: {'status', 'wiek_dni', 'uwaga'}}, [uwagi])"""
    now = now or NOW
    out, uw = {}, []
    for cc, nm in DL_KRAJE:
        P = dl.get(cc) if isinstance(dl, dict) and isinstance(dl.get(cc), dict) else {}
        q = P.get('q') if isinstance(P.get('q'), dict) else {}
        if cc == 'ar':
            g = (P.get('gap') or {}).get('contadoconliqui') if isinstance(P.get('gap'), dict) else None
            st = [x[2] for x in (q.get('contadoconliqui'), q.get('mayorista')) if _dl_kurs(x)]
            need = 2
        elif cc == 've':
            g = P.get('gap'); b = P.get('base') if isinstance(P.get('base'), list) and len(P.get('base')) >= 4 else None
            st = ([q['paralelo'][2]] if _dl_kurs(q.get('paralelo')) else []) + ([b[3]] if b and b[3] else [])
            need = 2
        else:
            g = P.get('gap')
            st = [x[2] for x in (q.get('usdt'), q.get('oficial')) if _dl_kurs(x)]
            need = 2
        ts = [_dl_od(x, cc) for x in st]
        dni = (now - min(ts)).total_seconds() / 86400 if ts and None not in ts else None
        wiek = round(dni, 1) if dni is not None else None
        num = isinstance(g, (int, float)) and not isinstance(g, bool)
        if not num:
            K = {'status': '⚠️', 'wiek_dni': wiek, 'uwaga': 'główna luka bez wartości (na stronie „—”)'}
        elif len(ts) < need or None in ts:
            K = {'status': '⚠️', 'wiek_dni': wiek, 'uwaga': 'brak daty któregoś kursu głównej luki'}
        elif dni > DL_LUKA_DNI:
            K = {'status': '⚠️', 'wiek_dni': wiek, 'uwaga': f'najstarszy kurs głównej luki sprzed {wiek:.1f} dni (próg {DL_LUKA_DNI})'}
        else:
            K = {'status': '✅', 'wiek_dni': wiek}
        out[cc] = K
        if K['status'] == '⚠️':
            uw.append(f'kursy dolara — {nm}: {K["uwaga"]}')
    return out, uw


def _dl_bcra_kurs(j, d):
    """Odpowiedź API banku centralnego Argentyny (Cotizaciones/USD) → kurs dnia d (RRRR-MM-DD) albo None."""
    for x in ((j.get('results') if isinstance(j, dict) else None) or []):
        if isinstance(x, dict) and x.get('fecha') == d:
            for y in x.get('detalle') or []:
                v = y.get('tipoCotizacion') if isinstance(y, dict) else None
                if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 and (y.get('codigoMoneda') or 'USD') == 'USD':
                    return float(v)
    return None


def dolar_swiezosc(j, now=None):
    """Wiersz świeżości kursów dolara (data/dolar.json → najnowsza z part_at.ar/ve/bo) w kształcie wierszy swiezosc(): (etykieta, status, wiek min,
    data, uwaga); brak pliku = None (brak pliku zgłasza pętla wieku plików). Najwyżej ⚠️ — nieoficjalny serwis kursów to nie awaria strony."""
    if not isinstance(j, dict):
        return None
    pa = j.get('part_at') if isinstance(j.get('part_at'), dict) else {}
    v = max((pa[k] for k in ('ar', 've', 'bo') if isinstance(pa.get(k), str)), default=None)
    if not v:
        return (DL_ETYKIETA, '?', None, None, 'brak czasu części w pliku')
    w = wiek_danych(v, 'ts', 'h', now)
    if w is None:
        return (DL_ETYKIETA, '?', None, v, 'zły zapis czasu części')
    st = '✅' if w <= DL_PROG else '⚠️'
    note = '' if st == '✅' else f'próg {fmt_wiek(DL_PROG)}' + (', ponad 2× progu — tylko uwaga' if w > 2 * DL_PROG else '')
    return (DL_ETYKIETA, st, w, v, note)


def dolar_porownanie(dl, bcra=None, now=None):
    """v136: Argentyna — dwa odczyty tych samych kursów z pliku dolar.json (ar.q vs ar.amb, sprzedaż) i kurs hurtowy vs kurs banku centralnego
    z tego samego dnia w Argentynie (UTC−3; bcra = odpowiedź API banku albo None) → {'status', 'pary', 'bcra', 'uwagi', 'opis'}. Para: ✅ w progu,
    ⚠️ ponad próg (nigdy ❌), „?” = brak któregoś odczytu albo znaczniki dalej niż DL_DNI dni. Do raportu tylko różnice w % i daty (bez kursów)."""
    out = {'status': '?', 'pary': [], 'bcra': None, 'uwagi': [], 'opis': ''}
    A = dl.get('ar') if isinstance(dl, dict) and isinstance(dl.get('ar'), dict) else {}
    q = A.get('q') if isinstance(A.get('q'), dict) else {}
    amb = A.get('amb') if isinstance(A.get('amb'), dict) else {}
    txt = []
    for k, nm, prog in DL_PARY:
        a, b = q.get(k), amb.get(k)
        P = {'kurs': nm, 'status': '?', 'roznica_pct': None, 'prog': prog}
        ta, tb = (_dl_czas(a[2]) if _dl_kurs(a) else None), (_dl_czas(b[2]) if _dl_kurs(b) else None)
        if ta is None or tb is None:
            P['uwaga'] = 'brak odczytu'
        elif abs(ta - tb) > dt.timedelta(days=DL_DNI):
            P['uwaga'] = f'odczyty dalej niż {DL_DNI} dni od siebie'
        else:
            r = abs(a[1] - b[1]) / b[1] * 100
            P['roznica_pct'] = round(r, 2) + 0.0
            P['status'] = '✅' if r <= prog else '⚠️'
            if r > prog:
                out['uwagi'].append(f'Argentyna, kurs {nm}: dwa odczyty różnią się o {r:.2f}% (próg {prog:g}%'
                                    + (f'; ponad {DL_DUZA[prog]:g}% — duża różnica' if r > DL_DUZA[prog] else '') + ')')
        out['pary'].append(P)
        txt.append(f'{nm} {P["status"]} ' + (f'{P["roznica_pct"]:.2f}%' if P['roznica_pct'] is not None else f'({P["uwaga"]})'))
    m = q.get('mayorista')
    B = {'status': '?', 'data': None, 'roznica_pct': None}
    t = _dl_czas(m[2]) if _dl_kurs(m) else None
    if t is None:
        B['uwaga'] = 'brak kursu hurtowego w pliku'
    else:
        B['data'] = (t - dt.timedelta(hours=3)).date().isoformat()
        v = _dl_bcra_kurs(bcra, B['data'])
        if v is None:
            B['uwaga'] = 'brak tego dnia w odpowiedzi banku' if isinstance(bcra, dict) else 'brak odczytu banku'
        else:
            r = abs(m[1] - v) / v * 100
            B['roznica_pct'] = round(r, 2) + 0.0; B['status'] = '✅' if r <= DL_BCRA_PROG else '⚠️'
            if r > DL_BCRA_PROG:
                out['uwagi'].append(f'Argentyna {B["data"]}: kurs hurtowy w pliku ≠ kurs banku centralnego o {r:.2f}% (próg {DL_BCRA_PROG:g}%)')
    out['bcra'] = B
    txt_b = f'hurtowy vs bank centralny ({B["data"] or "—"}) {B["status"]} ' + (f'{B["roznica_pct"]:.2f}%' if B['roznica_pct'] is not None else f'({B["uwaga"]})')
    gaps = {('ar', k): v for k, v in (A.get('gap') or {}).items()} if isinstance(A.get('gap'), dict) else {}
    V = dl.get('ve') if isinstance(dl, dict) and isinstance(dl.get('ve'), dict) else {}
    gaps[('ve', 'paralelo')] = V.get('gap')
    for (cc, k), g in gaps.items():
        if isinstance(g, (int, float)) and not isinstance(g, bool) and g > DL_LUKA_MAX[cc]:
            out['uwagi'].append(f'kursy dolara: luka {cc.upper()} {k} {g:+.1f}% ponad {DL_LUKA_MAX[cc]:g}% — możliwy błąd skali kursu')
    if isinstance(dl, dict):   # główne luki strony: brak albo stare kursy (wiek z dat kursów) = ⚠️
        out['luki'], uw = dolar_luki(dl, now)
        out['uwagi'] += uw
        txt_b += '; główne luki: ' + ', '.join(f'{cc.upper()} {K["status"]}' + (f' ({K["uwaga"]})' if K.get('uwaga') else '') for cc, K in out['luki'].items())
    sts = [P['status'] for P in out['pary']] + [B['status']]
    out['status'] = '⚠️' if '⚠️' in sts or out['uwagi'] else ('✅' if '✅' in sts else '?')
    out['opis'] = ', '.join(txt) + '; ' + txt_b
    return out


def dolar_kontrola(dl, R):
    """Krok 3f kontroli: 1 zapytanie do API banku centralnego Argentyny (10 dni do dnia kursu hurtowego; tylko gdy plik ma ten kurs z datą)
    i porównanie dolar_porownanie; uwagi dopisane do R['uwagi'] (nigdy do listy błędów). Brak pliku = None."""
    if not isinstance(dl, dict):
        return None
    A = dl.get('ar') if isinstance(dl.get('ar'), dict) else {}
    m = (A.get('q') or {}).get('mayorista') if isinstance(A.get('q'), dict) else None
    t = _dl_czas(m[2]) if _dl_kurs(m) else None
    bcra = None
    if t is not None:
        d = (t - dt.timedelta(hours=3)).date()
        try:
            bcra = get_json(DL_BCRA.format(a=(d - dt.timedelta(days=10)).isoformat(), b=d.isoformat()))
        except Exception as e:  # noqa
            R['uwagi'].append(f'kurs hurtowy Argentyny vs bank centralny: brak odczytu ({str(e)[:80]})')
    Z = dolar_porownanie(dl, bcra)
    R['uwagi'].extend(Z['uwagi'])
    return Z


# ---------------------------------------------------------------- kontrola ----------------------------------------------------------------
def kontrola():
    R = {'at': NOW.isoformat(), 'strona': {}, 'meta': {}, 'pliki': {}, 'actions': {}, 'swiezosc': [], 'zgodnosc': {}, 'uwagi': [], 'bledy': []}
    files = {}
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
        m = json.loads(body); files['meta'] = m
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
            j = json.loads(body); files[n] = j if isinstance(j, dict) else None
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
    # 3b. v111: pliki dla wyszukiwarek (robots.txt, sitemap.xml, plik weryfikacji Google) — tylko kod HTTP
    for f in ('robots.txt', 'sitemap.xml', 'google433f7c24524100a9.html'):
        try:
            st, body, ms = get(f'{SITE}/{f}?nc={int(time.time())}')
            R['pliki'][f] = {'http': st, 'bajty': len(body)}
            if st != 200 or len(body) < 20:
                R['uwagi'].append(f'{f}: HTTP {st}, {len(body)} B')
        except urllib.error.HTTPError as e:   # v111.1: kod HTTP w wierszu plików, nie „HTTP ?”
            R['pliki'][f] = {'http': e.code}; R['uwagi'].append(f'{f}: HTTP {e.code}')
        except Exception as e:  # noqa
            R['pliki'][f] = {'blad': str(e)[:120]}; R['uwagi'].append(f'{f}: {str(e)[:80]}')
    # 3c. v115: świeżość źródeł wg kategorii — żółte po progu, czerwone po 2×
    for label, st, w, txt, note in swiezosc(files):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '❌':
            R['bledy'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c'. v131: świeżość szans Fed (osobny wiersz tabeli — lista SWIEZOSC bez zmian) i uwagi o jakości cen (informacja)
    fr = fed_swiezosc(files.get('fed'))
    if fr:
        label, st, w, txt, note = fr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '❌':
            R['bledy'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    R['uwagi'].extend(fed_uwagi(files.get('fed')))
    # 3c''. v132: wycena BTC — świeżość części MVRV (dziennie) i SOPR (źródło opóźnia 7 dni; najwyżej ⚠️) jako osobne wiersze (lista SWIEZOSC
    # bez zmian) oraz MVRV z dwóch źródeł (drugie źródło tylko do tej kontroli) — najwyżej uwaga, nigdy błąd
    for label, st, w, txt, note in wycena_swiezosc(files.get('wycena')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '❌':
            R['bledy'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    if isinstance(files.get('wycena'), dict):
        R['zgodnosc']['wycena'] = wycena_mvrv(files.get('wycena'))
        R['uwagi'] += R['zgodnosc']['wycena']['uwagi']
    # 3c''. v136: świeżość kursów dolara Ameryki Łacińskiej — osobny wiersz tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    dr = dolar_swiezosc(files.get('dolar'))
    if dr:
        label, st, w, txt, note = dr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3d. v115: zgodność liczb — kapitalizacja (mediana 30 dni), ceny BTC/ETH, TGA, wieloryby
    Z = R['zgodnosc']
    today = NOW.date().isoformat()
    os.makedirs(OUT_DIR, exist_ok=True)
    zg_path = os.path.join(OUT_DIR, 'zgodnosc.csv')
    rows = zgodnosc_csv(zg_path)
    rows.setdefault(today, {})
    gap = None
    try:
        cg = get_json(CG_GLOBAL)['data']['total_market_cap']['usd']; cp = get_json(CP_GLOBAL)['market_cap_usd']
        gap = round((float(cp) - float(cg)) / float(cg) * 100.0, 3)
        rows[today]['cap'] = gap
    except Exception as e:  # noqa
        Z['kapitalizacja_blad'] = str(e)[:120]; R['uwagi'].append(f'zgodność kapitalizacji: brak odczytu ({str(e)[:80]})')
    st, med, n, opis = kapitalizacja(rows, gap, today)
    Z['kapitalizacja'] = {'status': st, 'dzis_pct': gap, 'mediana_pct': (round(med, 3) if med is not None else None), 'dni': n, 'opis': opis}
    if st == '❌':
        R['bledy'].append(f'kapitalizacja krypto: różnica źródeł dziś {gap:.2f}% wobec normy {med:.2f}% — {opis}')
    elif st == '⚠️':
        R['uwagi'].append(f'kapitalizacja krypto: różnica źródeł dziś {gap:.2f}% wobec normy {med:.2f}% — {opis}')
    try:
        p1 = get_json(CG_PRICE); c = {}
        for cid, key in (('btc-bitcoin', 'bitcoin'), ('eth-ethereum', 'ethereum')):
            p2 = get_json(CP_TICKER.format(id=cid))['quotes']['USD']['price']
            r = procent(float(p1[key]['usd']), float(p2))
            c[key] = {'a': float(p1[key]['usd']), 'b': float(p2), 'roznica_pct': (round(r, 3) if r is not None else None)}
            if r is not None and r > CENA_PROG:
                R['uwagi'].append(f'cena {key}: dwa źródła różnią się o {r:.2f}% (próg {CENA_PROG:g}%)')
        Z['ceny'] = c
    except Exception as e:  # noqa
        Z['ceny_blad'] = str(e)[:120]; R['uwagi'].append(f'zgodność cen BTC/ETH: brak odczytu ({str(e)[:80]})')
    t = tga_porownanie(files.get('instytucje') or {}, files.get('fred') or {})
    if t:
        d, a, b, r = t
        if r is not None:
            rows[today]['tga'] = round(r, 3)
        st2, med2, n2, opis2 = mediana_ocena(rows, 'tga', r, today, TGA_PROG, None)
        Z['tga'] = {'data': d, 'fiscal_mln': a, 'fred_mln': b, 'roznica_pct': (round(r, 3) if r is not None else None), 'status': st2,
                    'mediana_pct': (round(med2, 3) if med2 is not None else None), 'dni': n2, 'opis': opis2}
        if st2 == '⚠️':
            R['uwagi'].append(f'TGA {d}: Fiscal Data {a:,.0f} vs FRED {b:,.0f} mln USD — różnica {r:.2f}% wobec normy {med2:.2f}% ({opis2})')
    else:
        Z['tga'] = None
    try:
        zgodnosc_zapisz(zg_path, rows)
    except Exception as e:  # noqa
        R['uwagi'].append(f'zgodnosc.csv: nie zapisano ({str(e)[:80]})')
    e = etf_porownanie(files.get('ceny') or {}, files.get('indeksy') or {})
    if e:
        zle = [x for x in e if x[4] is not None and x[4] > ETF_PROG]
        Z['etf'] = {'porownane': len(e), 'roznice': [{'symbol': s, 'data': d, 'a': a, 'b': b, 'roznica_pct': round(r, 3)} for s, d, a, b, r in zle]}
        if zle:
            R['uwagi'].append('ETF (mapa): zamknięcia z dwóch źródeł różnią się > ' + f'{ETF_PROG:g}% dla ' + ', '.join(f'{s} ({d}: {a:g} vs {b:g})' for s, d, a, b, r in zle[:6]))
    else:
        Z['etf'] = None
    w = wieloryby_porownanie(os.path.join(ARCH_DIR, 'wieloryby.csv'))
    if w:
        d, p, zle, n = w
        Z['wieloryby'] = {'dzien': d, 'poprzedni': p, 'porownane': n, 'rozbieznosci': [{'gielda': g, 'aktywo': a, 'zmiana_usd': round(x, 2), 'netto_usd': round(y, 2), 'roznica_usd': round(z, 2)} for g, a, x, y, z in zle]}
        if zle:
            R['uwagi'].append('wieloryby: zmiana salda ≠ przelewy netto (> 5%) dla ' + ', '.join(f'{g} {a}' for g, a, *_ in zle[:6])
                              + ' — możliwe przelewy spoza zakresu skanu (< 1 mln USD, ETH przez kontrakty)')
    else:
        Z['wieloryby'] = None
    # 3e. v130: ETF krypto u źródła — przepływy IBIT i ETHA na stronie vs wyliczenie z plików emitenta (2 zapytania, bez ponawiania; najwyżej ⚠️)
    try:
        Z['etf_emitent'] = etf_emitent(files, R)
    except Exception as e:  # noqa
        Z['etf_emitent'] = {'status': '?', 'blad': str(e)[:120], 'fundusze': {}}
        R['uwagi'].append(f'ETF u źródła (pliki emitenta): kontrola przerwana ({str(e)[:80]})')
    # 3e. v128: zgodność premii krypto (bez sieci: plik premie i wczytany rynki) — tylko uwagi, nigdy błąd (dziwny rynek to nie awaria strony)
    Z['premie'] = premie_porownanie(files.get('premie'), files.get('rynki'))
    R['uwagi'] += Z['premie']['uwagi']
    # 3f. v136: Argentyna — dwa odczyty tych samych kursów (plik dolar.json) i kurs hurtowy vs bank centralny (1 zapytanie); najwyżej ⚠️ (nigdy ❌
    # ani BŁĄD): kurs z nieoficjalnego serwisu to nie awaria strony
    try:
        Z['dolar'] = dolar_kontrola(files.get('dolar'), R)
    except Exception as e:  # noqa
        Z['dolar'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'kursy dolara (Argentyna): kontrola przerwana ({str(e)[:80]})')
    # 4. przebiegi Actions z ostatnich 24 h (API publiczne; token tylko podnosi limit zapytań)
    try:
        hdr = {'Accept': 'application/vnd.github+json'}
        if TOKEN:
            hdr['Authorization'] = 'Bearer ' + TOKEN
        st, body, ms = get(f'https://api.github.com/repos/{REPO}/actions/runs?per_page=100', headers=hdr)
        runs = json.loads(body).get('workflow_runs', [])
        # v124.1: nazwa nieudanego kroku dla najwyżej 5 porażek z 24 h (1 zapytanie na porażkę; błąd odczytu = sama godzina)
        kroki = {}
        for r in [r for r in runs if str(r.get('name', '')).startswith('Strona') and r.get('conclusion') == 'failure'
                  and wiek_min(r.get('run_started_at')) is not None and wiek_min(r.get('run_started_at')) <= 24 * 60][:5]:
            try:
                _, b2, _ = get(f'https://api.github.com/repos/{REPO}/actions/runs/{r["id"]}/jobs', headers=hdr)
                for j in json.loads(b2).get('jobs', []):
                    if j.get('conclusion') == 'failure':
                        kroki[r['id']] = opis_kroku(j.get('name'), next((s.get('name') for s in j.get('steps') or [] if s.get('conclusion') == 'failure'), None))
                        break
            except Exception:  # noqa
                pass
        R['actions'], b, u = przebiegi_ocena(runs, NOW, kroki)
        R['bledy'] += b
        R['uwagi'] += u
    except Exception as e:  # noqa
        R['actions'] = {'blad': str(e)[:160]}
        R['uwagi'].append('nie udało się odczytać listy przebiegów Actions: ' + str(e)[:100])
    # 5. v115: historia — błędy zbieracza w 3 kolejnych przebiegach kontroli = czerwone
    n_err = len(R['meta'].get('errors') or []) if isinstance(R['meta'], dict) else 0
    hist = historia(os.path.join(OUT_DIR, 'historia.json'), {'at': R['at'], 'bledy_zbieracza': n_err, 'uwagi': len(R['uwagi']), 'bledy': len(R['bledy'])})
    if czerwone_z_historii(hist):
        R['bledy'].append(f'zbieracz zgłasza błędy w {HIST_CZERWONE} kolejnych dniach kontroli (' + '; '.join((R['meta'].get('errors') or ['?'])[:2]) + ')')
    R['historia_n'] = len(hist)
    R['wynik'] = 'BŁĄD' if R['bledy'] else ('UWAGA' if R['uwagi'] else 'OK')
    return R


def raport_md(R):
    m = R.get('meta') or {}
    werdykt = ('✅ Wszystko w normie.' if R['wynik'] == 'OK' else
               f'⚠️ Uwag: {len(R["uwagi"])} — nic nie wymaga natychmiastowej reakcji.' if R['wynik'] == 'UWAGA' else
               f'❌ Błędów: {len(R["bledy"])} — wymagają uwagi (szczegóły niżej).')
    L = [f'# Kontrola strony — {czas_pl(R["at"])} (czas polski)', '',
         f'**Wynik: {R["wynik"]}**', '', werdykt, '',
         f'- Strona główna: {"działa" if (R.get("strona") or {}).get("ok") else "PROBLEM"} (HTTP {(R.get("strona") or {}).get("http", "—")}, {(R.get("strona") or {}).get("ms", "—")} ms).',
         f'- Ostatni przebieg automatu: {czas_pl(m.get("at"))} — {("sprzed " + str(m.get("wiek_min")) + " min") if m.get("wiek_min") is not None else "brak"}; '
         f'źródeł: {m.get("zrodla", "—")}, bez odpowiedzi: {", ".join(m.get("bez_odpowiedzi") or []) or "żadne"}; błędów zbieracza: {len(m.get("errors") or [])}.']
    a = R.get('actions') or {}
    if 'przebiegi_24h' in a:
        L.append(f'- Przebiegi Actions w 24 h: {a["przebiegi_24h"]} ({", ".join(f"{k}: {v}" for k, v in a["wg_wyniku"].items()) or "—"}).')
        if a.get('porazki'):   # v124.1: każda porażka z godziną i krokiem; czy automat już działa
            L.append('- Nieudane przebiegi (24 h): ' + '; '.join(czas_pl(p['at']) + (f' — {p["krok"]}' if p.get('krok') else '') for p in a['porazki'])
                     + (f'. Od ostatniej porażki {pl_udane(a["udane_po_porazce"])} z rzędu.' if a.get('udane_po_porazce') else '. Ostatni zakończony przebieg nieudany.'))
    L.append('- Pliki danych (wiek): ' + ', '.join(f'{n} {("%dh%02d" % divmod(p["wiek_min"], 60)) if p.get("wiek_min") is not None else ("HTTP " + str(p.get("http", "?")))}'
                                             for n, p in (R.get('pliki') or {}).items()) + '.')
    if m.get('notes'):
        L.append('- Notatki automatu: ' + ' · '.join(m['notes']) + '.')
    if R.get('swiezosc'):
        L += ['', '## Świeżość źródeł', '', '| Źródło | Status | Wiek danych | Data danych | Uwaga |', '|---|---|---|---|---|']
        for s in R['swiezosc']:
            L.append(f'| {s["zrodlo"]} | {s["status"]} | {fmt_wiek(s["wiek_min"])} | {s["data"] or "—"} | {s["uwaga"] or "—"} |')
    Z = R.get('zgodnosc') or {}
    if Z:
        L += ['', '## Zgodność liczb (porównania krzyżowe)', '']
        k = Z.get('kapitalizacja') or {}
        if k:
            dz = f'{k["dzis_pct"]:.2f}%' if k.get('dzis_pct') is not None else '—'
            md = f'{k["mediana_pct"]:.2f}%' if k.get('mediana_pct') is not None else '—'
            L.append(f'- Kapitalizacja krypto, dwa źródła: różnica dziś {dz}, norma (mediana {k.get("dni", 0)} dni) {md} — {k.get("status", "?")} {k.get("opis", "")}.')
        c = Z.get('ceny') or {}
        for key, nm in (('bitcoin', 'BTC'), ('ethereum', 'ETH')):
            if key in c:
                r = c[key].get('roznica_pct')
                L.append(f'- Cena {nm}: {c[key]["a"]:,.0f} vs {c[key]["b"]:,.0f} USD — różnica {r:.2f}% {"⚠️" if r > CENA_PROG else "✅"}.' if r is not None else f'- Cena {nm}: brak porównania.')
        t = Z.get('tga')
        if t:
            r = t.get('roznica_pct'); md2 = f'{t["mediana_pct"]:.2f}%' if t.get('mediana_pct') is not None else '—'
            L.append(f'- TGA {t["data"]}: Fiscal Data {t["fiscal_mln"]:,.0f} vs FRED {t["fred_mln"]:,.0f} mln USD — różnica {r:.2f}%, norma (mediana {t.get("dni", 0)} dni) {md2} — {t.get("status", "?")} {t.get("opis", "")}.'
                     if r is not None else f'- TGA {t["data"]}: brak porównania.')
        else:
            L.append('- TGA: brak wspólnej daty Fiscal Data i FRED.')
        e = Z.get('etf')
        if e:
            L.append(f'- ETF mapy (dwa źródła, ta sama data): porównane {e["porownane"]} symboli, różnice > {ETF_PROG:g}%: {len(e["roznice"])} {"⚠️" if e["roznice"] else "✅"}' + (' — ' + ', '.join(x["symbol"] for x in e["roznice"][:6]) if e["roznice"] else '') + '.')
        else:
            L.append('- ETF mapy: brak wspólnej daty zamknięć w dwóch źródłach.')
        w = Z.get('wieloryby')
        if w:
            L.append(f'- Wieloryby {w["dzien"]} vs {w["poprzedni"]}: {w["porownane"]} par giełda/aktywo, rozbieżności > 5%: {len(w["rozbieznosci"])} {"⚠️" if w["rozbieznosci"] else "✅"}.')
        else:
            L.append('- Wieloryby: archiwum ma mniej niż dwa dni — porównanie od jutra.')
        wy = Z.get('wycena')   # v132: MVRV BTC z dwóch źródeł — tylko różnice procentowe i daty; brak = „—”
        if wy:
            dz = f'{wy["roznica_pct"]:+.2f}% ({wy["dzien"]})' if wy.get('roznica_pct') is not None else '—'
            md3 = f'{wy["mediana_pct"]:+.2f}%' if wy.get('mediana_pct') is not None else '—'
            L.append(f'- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia {dz}, norma (mediana {wy.get("n", 0)} dni) {md3} — {wy.get("status", "?")} {wy.get("opis", "")}.')
        pz = Z.get('premie')
        if pz:
            L.append(f'- Premie krypto: {pz.get("opis") or "—"} ' + ('⚠️' if pz.get('uwagi') else '✅') + '.')
        em = Z.get('etf_emitent') or {}   # v130: ETF krypto u źródła — tylko różnice i daty (+ koniec pliku emitenta i jego zaległość); brak = „—”
        cz = [emitent_linia(t, F) for t, F in (em.get('fundusze') or {}).items()]
        L.append(f'- ETF krypto u źródła — przepływy funduszy na stronie vs wyliczenie z plików emitenta (dzień D = zmiana liczby jednostek D → D+1 × NAV z D; '
                 f'próg max {EM_TOL_MLN:g} mln USD / {EM_TOL_PCT:g}%): ' + (' · '.join(cz) if cz else (f'? kontrola przerwana ({em["blad"]})' if em.get('blad') else '—')) + '.')
        dz = Z.get('dolar')   # v136: Argentyna — tylko różnice w % i daty (bez kursów); brak pliku = bez linii
        if dz:
            L.append('- Argentyna — dwa odczyty tych samych kursów: ' + (dz.get('opis') or (f'? kontrola przerwana ({dz["blad"]})' if dz.get('blad') else '—')) + '.')
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
