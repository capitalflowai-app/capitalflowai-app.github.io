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
v133: tokenizowane aktywa RWA (data/rwa.json): świeżość listy osobnym wierszem (próg 12 h; najwyżej ⚠️) i porównania z pliku strony bez zapytań — własna zmiana 7 dni vs podana przez źródło, produkty spoza głównej listy, skok sumy dzień do dnia (najwyżej ⚠️).
v137: Japonia — kto handluje akcjami na giełdzie (data/jpx.json): świeżość wg kalendarza publikacji źródła (4. dzień roboczy następnego tygodnia, święta w Japonii; najwyżej ⚠️) i zgodność kierunku zagranicy z danymi tygodniowymi MOF (z plików strony, bez zapytań; najwyżej ⚠️).
v136: kursy dolara Ameryki Łacińskiej (data/dolar.json) — świeżość osobnym wierszem (najwyżej ⚠️), dwa odczyty kursów Argentyny z pliku i kurs hurtowy vs API banku centralnego Argentyny (1 zapytanie); tylko uwagi, nigdy BŁĄD.
v130: ETF krypto u źródła — przepływy IBIT i ETHA na stronie vs wyliczenie z plików emitenta (liczba jednostek × NAV); zapis sesji ze strony w `kontrola/etf-emitent.csv`.
v134: fundusze USA (data/ici.json) — świeżość części osobnymi wierszami (najwyżej ⚠️; lista SWIEZOSC bez zmian), tożsamości sum ostatniego
tygodnia w pliku strony i poprawki wydawcy (informacja); bez sieci, nigdy BŁĄD.
v135: fundusze rynku pieniężnego (ta sama data/ici.json, część mm) — osobny wiersz świeżości (próg 10 dni, najwyżej ⚠️) i sumy ostatniego tygodnia.
v150: tokenizowane aktywa — odczyt własny z łańcucha (blok onchain w data/rwa.json): wiersz świeżości (próg 12 h, najwyżej ⚠️; wyłącznik
RWA_CHAIN_OFF = „—”) i porównania bez sieci — podaż produktu dzień do dnia (> 50% = ⚠️), wartość z łańcucha vs ostatnio znana wartość
źródła v133 (poza 1/3–3× = ⚠️), produkty bez pełnego odczytu, odczyt niepełny; skok sumy RWA w dniu zmiany zbioru produktów z odczytu
własnego liczony bez nich (zmiana zakresu, nie rynku)."""
import csv
import datetime as dt
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
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
PLIKI = ['meta', 'etf', 'trendy', 'oecd', 'rynki', 'dzwignia', 'wieloryby', 'energia', 'usa-makro', 'bilans-usa', 'krypto', 'krypto-top10', 'cmc', 'instytucje', 'tic', 'cm', 'fred', 'cftc', 'ceny', 'indeksy', 'ceny-krypto', 'snb', 'ici', 'fed', 'lancuch', 'wycena', 'insider', 'nastroj', 'stres', 'aukcje', 'swiat-dzien', 'swiat-dziennik', 'premie', 'dolar', 'stopy', 'jpx', 'rwa', 'krypto-dzien', 'krypto-dziennik']
LIMIT_MIN = {'stopy': 24 * 60, 'meta': 90, 'etf': 180, 'trendy': 180, 'oecd': 24 * 60, 'rynki': 180, 'dzwignia': 180, 'wieloryby': 90, 'energia': 24 * 60,
             'usa-makro': 24 * 60, 'bilans-usa': 48 * 60, 'krypto': 180, 'krypto-top10': 180, 'cmc': 90, 'instytucje': 180, 'tic': 48 * 60, 'cm': 180, 'fred': 180, 'cftc': 24 * 60, 'ceny': 180, 'indeksy': 24 * 60, 'ceny-krypto': 180, 'snb': 24 * 60, 'ici': 24 * 60, 'fed': 90, 'lancuch': 90, 'wycena': 8 * 60, 'insider': 48 * 60, 'nastroj': 12 * 60, 'stres': 24 * 60, 'aukcje': 24 * 60, 'swiat-dzien': 180, 'swiat-dziennik': 180, 'premie': 90, 'dolar': 180, 'jpx': 26 * 60, 'rwa': 12 * 60, 'krypto-dzien': 180, 'krypto-dziennik': 180}
# v171: części zbieracza wyłączone celowo (notatka w meta.json) — brak pliku to wtedy stan, nie usterka: w raporcie „wyłączone”, bez uwagi
WYLACZONE = {'insider': ('brak SEC_CONTACT', 'SEC_CONTACT to nie adres e-mail')}


def wylaczone(meta):
    """v171: {plik: notatka zbieracza} dla części wyłączonych celowo (np. brak sekretu SEC_CONTACT — urząd wymaga adresu w zapytaniu);
    brak pliku stanu albo notatki = {}."""
    N = [x for x in (meta.get('notes') or []) if isinstance(x, str)] if isinstance(meta, dict) else []
    out = {}
    for n, F in WYLACZONE.items():
        for x in N:
            if any(f in x for f in F):
                out[n] = x[:160]
                break
    return out


# v115: świeżość ŹRÓDEŁ (data danych, nie czas pliku). (etykieta, plik, kategoria, próg w minutach). Kategorie: 'h' = godzinowe (czas części
# pliku), 'd' = dzienne w dni robocze (koniec dnia danych, liczone godzinami roboczymi bez sobót i niedziel), 'w' = tygodniowe (koniec dnia danych),
# 'm' = miesięczne (koniec miesiąca danych). Progi z zadania: 3 h / 36 h / 9 dni / 45 dni; CFTC +3 dni (raport wtorkowy publikowany w piątek),
# TIC +40 dni (Skarb USA publikuje dane miesiąca 46–51 dni po jego końcu; tuż przed publikacją wiek = 30 + 51 = 81 dni) — inaczej żółte świeciłoby co miesiąc bez powodu.
# EIA: ceny dzienne ropy są publikowane raz w tygodniu (środa, za poprzedni tydzień) — próg tygodniowy 9 dni, nie 36 h (26.09: dane z wtorku w sobotę = 3 dni).
# v182: TGA — zestawienie Skarbu USA za dzień D ukazuje się o 16:00 czasu nowojorskiego NASTĘPNEGO dnia roboczego (20:00 UTC latem, 21:00 zimą), więc
# przed publikacją najnowsze jest D−2 dni robocze: normalny wiek do ok. 45 h roboczych (+ do 1 h na odświeżenie pliku). Próg 36 h dawał ⚠️ w każdy
# dzień roboczy od 12:00 do ok. 21:00 UTC (05.10, 12:03 UTC: „36 h 03 min”) — teraz 48 h; święto federalne USA = ⚠️ (informacja, nigdy BŁĄD).
SWIEZOSC = [
    ('rynki (kursy EBC, rentowności)', 'rynki', 'h', 180), ('wieloryby (salda portfeli giełd)', 'wieloryby', 'h', 180), ('dźwignia (giełdy pochodnych)', 'dzwignia', 'h', 180),
    ('premie krypto (minuty giełd)', 'premie', 'h', 180),
    ('TGA (Fiscal Data, dziennie)', 'instytucje', 'd', 48 * 60), ('ETF krypto (SoSoValue, dziennie)', 'etf', 'd', 36 * 60),
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

# v209: podaż stablecoinów — dwa pliki strony (bez zapytań); rentowność 10L USA — plik strony vs H.15 (FRED, bez klucza)
STAB_ZOLTE = 2.0     # pkt proc. — odchylenie dzisiejszej różnicy (DefiLlama vs CoinMarketCap) od mediany ZG_DNI dni = ⚠️ (nigdy ❌)
STAB_MAX_H = 6.0     # h — pliki krypto.json i cmc.json pobrane dalej od siebie = bez porównania (informacja)
UST_FRED = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10&cosd={od}'   # H.15: Rada Gubernatorów Fed — domena publiczna, bez klucza
UST_FED = ('https://www.federalreserve.gov/datadownload/Output.aspx?rel=H15&series=bf17364827e38702b42a58cf8eaa3f78&lastobs=15&from=&to='
           '&filetype=csv&label=include&layout=seriescolumn&type=package')   # v211: H.15 u wydawcy (stałe zapadalności, dni robocze) — najpierw to, FRED zapasem
UST_FED_KOL = 'RIFLGFCY10_N.B'   # v211: kolumna 10 lat w pliku H.15 (06.10: 24.09 5,18 = DGS10 5,18 = plik strony)
UST_PROG = 0.02      # pkt proc. — ta sama data: plik strony (Skarb USA) vs H.15; większa różnica = ⚠️
UST_DNI = 10         # tyle ostatnich dat z pliku strony porównujemy (H.15 wychodzi z ok. 1-dniowym opóźnieniem)
UST_OD_DNI = 21      # FRED: plik od tylu dni wstecz (mały — ok. 200 B)
# v241: stopy Fed i EBC — plik strony (stopy.json) vs FRED (bez klucza), ten sam dzień; zmiana stopy, której strona jeszcze nie ma
STOPY_FRED = {'US': (('DFEDTARL', 'DFEDTARU'), 'Fed'), 'XM': (('ECBDFR',), 'EBC')}   # zapas (FRED): Fed — środek przedziału celu; EBC — stopa depozytowa
# v242: najpierw źródło banku, bez klucza (FRED z serwerów GitHub nie odpowiedział w 30 s): Fed — przedział celu z danych EFFR nowojorskiego Fed,
# EBC — stopa depozytowa z portalu danych EBC; kolejność wariantów = pierwszeństwo
STOPY_SERIE = {'US': ((('NYFED_LO', 'NYFED_HI'), 'Fed', 'NY Fed'), (('DFEDTARL', 'DFEDTARU'), 'Fed', 'FRED')),
               'XM': ((('ECB_DFR',), 'EBC', 'EBC'), (('ECBDFR',), 'EBC', 'FRED')),
               # v244: sześć kolejnych banków u źródła, bez klucza (06.10.2026 wszystkie zgodne ze stroną); bez zapasu FRED (brak serii dziennych)
               'GB': ((('BOE_BR',), 'Bank Anglii', 'BoE'),), 'CH': ((('SNB_LZ',), 'Bank Szwajcarii', 'SNB'),),
               'SE': ((('RB_POL',), 'Bank Szwecji', 'Riksbank'),), 'NO': ((('NB_KPRA',), 'Bank Norwegii', 'Norges Bank'),),
               'PL': ((('NBP_REF',), 'NBP', 'NBP'),), 'CA': ((('BOC_V39079',), 'Bank Kanady', 'BoC'),),
               'BR': ((('BCB_SELIC',), 'Bank Brazylii', 'BCB'),)}   # v245: Selic — cel stopy (SGS 432)
STOPY_NYFED = 'https://markets.newyorkfed.org/api/rates/unsecured/effr/last/100.json'
STOPY_ECB = 'https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.DFR.LEV?lastNObservations=150&format=csvdata'
# v244: adresy kolejnych banków ({od} = dzień początkowy, {do} = dziś; Bank Anglii — data „08/Jun/2026”). Bank Australii odrzuca automaty
# (403 — zabezpieczenie) — pominięty.
STOPY_BOE = ('https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom={od}&Dateto=now'
             '&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N')
STOPY_SNB = 'https://data.snb.ch/api/cube/snbgwdzid/data/csv/en?dimSel=D0(LZ)&fromDate={od}'
STOPY_RIKS = 'https://api.riksbank.se/swea/v1/Observations/SECBREPOEFF/{od}/{do}'
STOPY_NORGES = 'https://data.norges-bank.no/api/data/IR/B.KPRA.SD.R?format=csv&startPeriod={od}&locale=en'
STOPY_NBP = 'https://static.nbp.pl/dane/stopy/stopy_procentowe.xml'   # tylko stopa obowiązująca i dzień, od którego obowiązuje (archiwum do 2015)
STOPY_BOC = 'https://www.bankofcanada.ca/valet/observations/V39079/json?start_date={od}'
STOPY_BCB = 'https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json&dataInicial={od}&dataFinal={do}'   # v245: daty dd/mm/rrrr
STOPY_MIES_EN = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
STOPY_BUDZET_S = 90    # v245: cały blok stóp (źródła banków, ponowienia, zapas FRED) — zapytanie tylko, gdy zmieści się w budżecie (krok kontroli
#                        ok. 90 s; zadanie ma 12 min, w tym do 5 min czekania na publikację)
STOPY_PAUZA_S = 3      # v245: przerwa przed jedną ponowną próbą po błędzie serwera (5xx) albo przekroczeniu czasu
STOPY_ZAPAS_S = 5      # v248: twardy limit jednego zapytania = jego limit + tyle (urllib liczy limit na operację gniazda; DNS bez limitu)
STOPY_FRED_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}&cosd={od}'
STOPY_OD_DNI = 120    # FRED: plik od tylu dni wstecz (data stopy na stronie bywa sprzed kilku tygodni — np. RBI)
STOPY_PROG = 0.01     # pkt proc. — większa różnica w tym samym dniu = ⚠️
STOPY_ZWLOKA_DNI = 10  # zmiana stopy starsza niż tyle dni, a strona jej nie ma = ⚠️ (v243: źródło stóp strony spóźnia się 7–8 dni; przy 3 każda
#                        decyzja Fed/EBC dawałaby kilka dni UWAGI)


def _stopa_fred(S, d):
    """Stopa z serii FRED (lista {dzień: %}) w dniu d = średnia ostatnich obserwacji ≤ d każdej serii; brak którejś = None."""
    v = []
    for s in S:
        dn = [k for k in s if k <= d]
        if not dn:
            return None
        v.append(s[max(dn)])
    return sum(v) / len(v)


def stopy_nyfed(body):
    """v242: JSON EFFR nowojorskiego Fed → {'NYFED_LO': {dzień: dolna granica celu}, 'NYFED_HI': {dzień: górna}}; pusto = wyjątek."""
    j = json.loads(body)
    lo, hi = {}, {}
    for r in (j.get('refRates') or []) if isinstance(j, dict) else []:
        d, a, b = (r.get('effectiveDate'), r.get('targetRateFrom'), r.get('targetRateTo')) if isinstance(r, dict) else (None, None, None)
        if isinstance(d, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', d) and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x == x and abs(x) < 1e6 for x in (a, b)):
            lo[d], hi[d] = float(a), float(b)
    if not lo:
        raise ValueError('brak przedziału celu')
    return {'NYFED_LO': lo, 'NYFED_HI': hi}


def stopy_ecb_csv(body, sep=','):
    """v242: CSV portalu danych EBC (kolumny TIME_PERIOD, OBS_VALUE) → {dzień: stopa}; puste wartości pominięte; pusto = wyjątek.
    v244: sep=';' — ten sam układ SDMX u Norges Bank; znacznik BOM pominięty."""
    L = (body.decode('utf-8-sig', 'replace') if isinstance(body, (bytes, bytearray)) else str(body)).splitlines()
    h = L[0].split(sep) if L else []
    if 'TIME_PERIOD' not in h or 'OBS_VALUE' not in h:
        raise ValueError('nieznany nagłówek')
    i, j, out = h.index('TIME_PERIOD'), h.index('OBS_VALUE'), {}
    for line in L[1:]:
        p = line.split(sep)
        if len(p) > max(i, j) and re.match(r'^\d{4}-\d{2}-\d{2}$', p[i]):
            try:
                v = float(p[j])
            except ValueError:
                continue
            if v == v and abs(v) < 1e6:   # v243: NaN i nieskończoność odrzucone
                out[p[i]] = v
    if not out:
        raise ValueError('plik bez liczb')
    return out


def _stopy_tekst(body):
    """v244: treść odpowiedzi jako tekst, bez znacznika BOM."""
    return body.decode('utf-8-sig', 'replace') if isinstance(body, (bytes, bytearray)) else str(body).lstrip('\ufeff')


def _stopy_liczba(x):
    """v244: stopa z liczby albo tekstu („3,75” i „3.75”); NaN, nieskończoność, wartości absurdalne i typ bool = None."""
    if isinstance(x, bool):
        return None
    if isinstance(x, str):
        try:
            x = float(x.strip().replace(',', '.'))
        except ValueError:
            return None
    return float(x) if isinstance(x, (int, float)) and x == x and abs(x) < 1e6 else None


def stopy_boe(body):
    """v244: CSV bazy danych Banku Anglii (DATE,IUDBEDR; wiersze „05 Oct 2026,3.75”) → {'BOE_BR': {dzień: stopa}}; inny nagłówek (np. strona
    błędu z kodem 200) = wyjątek; skróty miesięcy po angielsku bez ustawień regionalnych."""
    L = _stopy_tekst(body).splitlines()
    if not L or L[0].replace(' ', '') != 'DATE,IUDBEDR':
        raise ValueError('nieznany nagłówek')
    out = {}
    for line in L[1:]:
        p = line.split(',')
        m = re.match(r'^(\d{1,2}) ([A-Z][a-z]{2}) (\d{4})$', p[0].strip()) if len(p) == 2 else None
        v = _stopy_liczba(p[1]) if m and m.group(2) in STOPY_MIES_EN else None
        if v is not None:
            out[f'{m.group(3)}-{STOPY_MIES_EN.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}'] = v
    if not out:
        raise ValueError('plik bez liczb')
    return {'BOE_BR': out}


def stopy_snb(body):
    """v244: CSV portalu danych SNB (średniki, cudzysłowy: „"2026-10-02";"LZ";"0"”) → {'SNB_LZ': {dzień: stopa}} — tylko wymiar LZ (stopa SNB)."""
    out = {}
    for line in _stopy_tekst(body).splitlines():
        p = [x.strip().strip('"') for x in line.split(';')]
        if len(p) == 3 and p[1] == 'LZ' and re.match(r'^\d{4}-\d{2}-\d{2}$', p[0]):
            v = _stopy_liczba(p[2])
            if v is not None:
                out[p[0]] = v
    if not out:
        raise ValueError('plik bez liczb')
    return {'SNB_LZ': out}


def stopy_riksbank(body):
    """v244: JSON Riksbanku (lista {date, value}) → {'RB_POL': {dzień: stopa}}."""
    j = json.loads(body)
    out = {}
    for r in j if isinstance(j, list) else []:
        d, v = (r.get('date'), _stopy_liczba(r.get('value'))) if isinstance(r, dict) else (None, None)
        if isinstance(d, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', d) and v is not None:
            out[d] = v
    if not out:
        raise ValueError('brak stóp')
    return {'RB_POL': out}


def stopy_norges(body):
    """v244: CSV Norges Bank (SDMX, średniki; kolumny TIME_PERIOD, OBS_VALUE) → {'NB_KPRA': {dzień: stopa}}."""
    return {'NB_KPRA': stopy_ecb_csv(body, sep=';')}


def stopy_nbp(body):
    """v244: XML stóp NBP — tylko stopa obowiązująca (pozycja id="ref", „3,75”) i dzień, od którego obowiązuje → {'NBP_REF': {dzień: stopa}}:
    seria schodkowa z jednym punktem (ta stopa na każdy dzień od tej daty; dzień strony sprzed niej — bez porównania, ale ze zmianą)."""
    for m in re.finditer(r'<pozycja\b([^>]*)>', _stopy_tekst(body)):
        a = dict(re.findall(r'(\w+)\s*=\s*"([^"]*)"', m.group(1)))
        if a.get('id') == 'ref':
            d, v = a.get('obowiazuje_od', ''), _stopy_liczba(a.get('oprocentowanie', ''))
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', d) or v is None:
                raise ValueError('zła stopa referencyjna')
            return {'NBP_REF': {d: v}}
    raise ValueError('brak stopy referencyjnej')


def stopy_boc(body):
    """v244: JSON Banku Kanady (Valet: observations [{d, V39079: {v: "2.25"}}]) → {'BOC_V39079': {dzień: stopa}}."""
    j = json.loads(body)
    out = {}
    for r in (j.get('observations') or []) if isinstance(j, dict) else []:
        o = r.get('V39079') if isinstance(r, dict) else None
        d, v = (r.get('d'), _stopy_liczba(o.get('v'))) if isinstance(o, dict) else (None, None)
        if isinstance(d, str) and re.match(r'^\d{4}-\d{2}-\d{2}$', d) and v is not None:
            out[d] = v
    if not out:
        raise ValueError('brak stóp')
    return {'BOC_V39079': out}


def stopy_bcb(body):
    """v245: JSON Banku Brazylii (SGS 432 — cel stopy Selic, dziennie; [{"data": "29/09/2026", "valor": "13.75"}]) → {'BCB_SELIC': {dzień:
    stopa}}; obiekt z błędem (np. okno ponad 10 lat) = wyjątek."""
    j = json.loads(body)
    out = {}
    for r in j if isinstance(j, list) else []:
        m = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', r.get('data', '')) if isinstance(r, dict) and isinstance(r.get('data'), str) else None
        v = _stopy_liczba(r.get('valor')) if m else None
        if v is not None:
            out[f'{m.group(3)}-{m.group(2)}-{m.group(1)}'] = v
    if not out:
        raise ValueError('brak stóp' if isinstance(j, list) else f'odpowiedź bez listy ({str(j)[:40]})')
    return {'BCB_SELIC': out}


def stopy_adresy(now=None):
    """v244: (nazwa źródła, adres, parser, serie) kolejnych banków — od STOPY_OD_DNI dni wstecz do dziś (v246: serie — do powodu banku przy
    błędzie odczytu)."""
    now = now or NOW
    d0, d1 = now.date() - dt.timedelta(days=STOPY_OD_DNI), now.date()
    od = d0.isoformat()
    return (('BoE', STOPY_BOE.format(od=f'{d0.day:02d}/{STOPY_MIES_EN[d0.month - 1]}/{d0.year}'), stopy_boe, ('BOE_BR',)),
            ('SNB', STOPY_SNB.format(od=od), stopy_snb, ('SNB_LZ',)),
            ('Riksbank', STOPY_RIKS.format(od=od, do=d1.isoformat()), stopy_riksbank, ('RB_POL',)),
            ('Norges Bank', STOPY_NORGES.format(od=od), stopy_norges, ('NB_KPRA',)),
            ('NBP', STOPY_NBP, stopy_nbp, ('NBP_REF',)),
            ('BoC', STOPY_BOC.format(od=od), stopy_boc, ('BOC_V39079',)),
            ('BCB', STOPY_BCB.format(od=d0.strftime('%d/%m/%Y'), do=d1.strftime('%d/%m/%Y')), stopy_bcb, ('BCB_SELIC',)))


def stopy_ponowic(e):
    """v245: błąd chwilowy, który warto raz ponowić — kod 5xx serwera albo przekroczenie czasu (także owinięte w URLError)."""
    if isinstance(e, urllib.error.HTTPError):
        return e.code >= 500
    if isinstance(e, urllib.error.URLError):
        return isinstance(e.reason, TimeoutError)
    return isinstance(e, TimeoutError)


def _stopy_raz(url, timeout, headers=None, pobierz=None, zapas=None):
    """v248: jedno zapytanie z twardym limitem łącznego czasu (timeout + STOPY_ZAPAS_S) — urllib liczy limit na operację gniazda, nie na całość
    (wolno sączący serwer, DNS); wątek w tle po przekroczeniu jest porzucany (kończy się sam albo z procesem)."""
    pobierz = pobierz or get
    zapas = STOPY_ZAPAS_S if zapas is None else zapas
    wyn = {}

    def run():
        try:
            wyn['b'] = pobierz(url, timeout=timeout, headers=headers)[1]
        except Exception as e:  # noqa
            wyn['e'] = e
    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(timeout + zapas)
    if t.is_alive():
        raise TimeoutError(f'brak całej odpowiedzi w {timeout + zapas:g} s')
    if 'e' in wyn:
        raise wyn['e']
    return wyn['b']


def _dzien(s):
    """v248: 'RRRR-MM-DD' tylko prawdziwego dnia kalendarza (np. 31.09 = None) — daty źródeł trafiają później do date.fromisoformat."""
    if not isinstance(s, str) or not re.match(r'^\d{4}-\d{2}-\d{2}$', s):
        return None
    try:
        dt.date.fromisoformat(s)
    except ValueError:
        return None
    return s


def stopy_porownanie(stopy, fred, now=None, bledy=None):
    """v241/v243: stopy.json (rows[kraj] = {rate, date}) i serie ({id: {dzień: %}}) → jedna pozycja na bank: porównanie {'bank', 'zrodlo',
    'data', 'strona', 'fred', 'zgodne', 'zmiana': [dzień, nowa stopa] albo None} albo {'bank', 'brak': powód, 'powod'} — bank bez porównania
    nie znika z wiersza raportu (v243). Wariant serii: pierwszy, który obejmuje dzień strony (źródło banku, potem FRED). Brak pliku strony = [].
    v246: bledy = {id serii: 'źródło: błąd'} — bank bez żadnej serii: powód z błędów odczytu ('powod': 'odczyt', 'bledy'); „brak serii
    obejmującej dzień strony” tylko, gdy seria jest, ale zaczyna się po dniu strony ('powod': 'seria') — wtedy pierwsza inna stopa w całej
    serii ('zmiana'); inna już na początku danych = 'od_poczatku' (dzień zmiany nieznany; NBP — jedyny dzień to dzień, od którego obowiązuje)."""
    now = now or NOW
    if not isinstance(stopy, dict):
        return []
    rows = stopy.get('rows') if isinstance(stopy.get('rows'), dict) else {}
    F = {i: {d: v for d, v in s.items() if _dzien(d)} for i, s in fred.items() if isinstance(s, dict)} if isinstance(fred, dict) else {}   # v248: tylko prawdziwe dni
    B = bledy if isinstance(bledy, dict) else {}
    out = []
    for a, warianty in STOPY_SERIE.items():
        nazwa = warianty[0][1]
        r = rows.get(a)
        rate = r.get('rate') if isinstance(r, dict) else None
        if not isinstance(rate, (int, float)) or isinstance(rate, bool) or rate != rate or abs(rate) > 1e6:
            out.append({'bank': nazwa, 'brak': 'brak stopy w pliku strony', 'powod': 'strona'})
            continue
        if not _dzien(r.get('date')):   # v248: także 30.02 to nie dzień
            out.append({'bank': nazwa, 'brak': f'data w pliku strony „{str(r.get("date"))[:10]}” to nie dzień', 'powod': 'strona'})
            continue
        jest = [(ids, zr) for ids, _, zr in warianty if all(isinstance(F.get(i), dict) and F.get(i) for i in ids)]
        wyb = None
        for ids, zr in jest:
            S = [F[i] for i in ids]
            f = _stopa_fred(S, r['date'])
            if f is not None:
                wyb = (S, zr, f)
                break
        if not jest:   # v246: żadne źródło nie dało serii — powód z błędów odczytu (było „brak serii obejmującej dzień strony”)
            bl = list(dict.fromkeys(B[i] for ids, _, _ in warianty for i in ids if i in B))
            out.append({'bank': nazwa, 'brak': ('nie odczytano źródła — ' + '; '.join(bl)) if bl else 'brak danych ze źródła', 'powod': 'odczyt',
                        'bledy': bl})
            continue
        if wyb is None:   # seria jest, ale zaczyna się po dniu strony (NBP podaje tylko stopę obowiązującą; okno pobierania ok. 4 mies.)
            ids, zr = jest[0]
            S = [F[i] for i in ids]
            d0 = max(min(s) for s in S)
            o = {'bank': nazwa, 'brak': f'brak serii obejmującej dzień strony ({r["date"]})', 'powod': 'seria'}
            for d in sorted({k for s in S for k in s if k >= d0}):   # v246: pierwsza inna stopa w całej serii (było: tylko pierwszy dzień)
                v = _stopa_fred(S, d)
                if v is not None and abs(v - rate) >= STOPY_PROG:
                    o.update(zrodlo=zr, data=r['date'], strona=float(rate), zmiana=[d, round(v, 4)],
                             od_poczatku=d == d0 and any(len(s) > 1 for s in S))
                    break
            out.append(o)
            continue
        S, zr, f = wyb
        o = {'bank': nazwa, 'zrodlo': zr, 'data': r['date'], 'strona': float(rate), 'fred': round(f, 4), 'zgodne': abs(rate - f) < STOPY_PROG, 'zmiana': None}
        dni = sorted({k for s in S for k in s if k > r['date']})
        for d in dni:
            v = _stopa_fred(S, d)
            if v is not None and abs(v - f) >= STOPY_PROG:
                o['zmiana'] = [d, round(v, 4)]
                break
        out.append(o)
    return out


def stopy_sprawdz(stopy, now=None, zegar=time.monotonic, spij=time.sleep):
    """v246: blok stóp kontroli (wyjęty z kontrola(), żeby testy szły przez prawdziwy przebieg): źródła banków w budżecie STOPY_BUDZET_S,
    zapas FRED dla banków bez porównania, błąd odczytu każdej serii → powód „brak porównania” banku. v248: faza 1 — każde źródło raz;
    faza 2 — jedno ponowienie źródeł z błędem chwilowym (5xx, przekroczenie czasu) w tym, co zostało z budżetu (ponowienia pierwszych źródeł
    nie zabierają czasu pozostałym); każde zapytanie z twardym limitem łącznego czasu (_stopy_raz).
    → ({'wyniki': [...], 'brak': błędy odczytu nieujęte w powodach banków albo None}, uwagi)."""
    now = now or NOW
    Fs, bs, Bl = {}, [], {}
    t0 = zegar()

    def blad(nm, ids, e):
        t = f'{nm}: {str(e)[:60]}'
        bs.append(t)
        Bl.update({i: t for i in ids})
    zr = [('NY Fed', STOPY_NYFED, stopy_nyfed, ('NYFED_LO', 'NYFED_HI'), 20, None),   # v242: źródło banku najpierw, bez klucza
          ('EBC', STOPY_ECB, lambda b: {'ECB_DFR': stopy_ecb_csv(b)}, ('ECB_DFR',), 20, {'Accept': 'text/csv'})]
    zr += [(nm, url, fn, ids, 15, None) for nm, url, fn, ids in stopy_adresy(now)]   # v244: kolejne banki u źródła
    ponow = []
    for z in zr:   # faza 1: każde źródło raz
        nm, url, fn, ids, tm, hd = z
        if zegar() - t0 + tm > STOPY_BUDZET_S:
            blad(nm, ids, 'pominięte — limit czasu kontroli stóp')
            continue
        try:
            Fs.update(fn(_stopy_raz(url, tm, hd)))
        except Exception as e:  # noqa
            if stopy_ponowic(e):
                ponow.append((z, e))
            else:
                blad(nm, ids, e)
    if ponow:   # faza 2 (v245/v248): jedno ponowienie błędów chwilowych, w tym, co zostało z budżetu
        spij(STOPY_PAUZA_S)
    for (nm, url, fn, ids, tm, hd), e0 in ponow:
        if zegar() - t0 + tm > STOPY_BUDZET_S:
            blad(nm, ids, e0)   # brak czasu na ponowienie — pierwotny błąd
            continue
        try:
            Fs.update(fn(_stopy_raz(url, tm, hd)))
        except Exception as e:  # noqa
            blad(nm, ids, e)
    Ps = stopy_porownanie(stopy, Fs, now, bledy=Bl)
    bez = {o['bank'] for o in Ps if o.get('powod') in ('odczyt', 'seria')}   # v243/v246: seria nie sięga dnia strony albo źródło nieodczytane
    od_s = (now.date() - dt.timedelta(days=STOPY_OD_DNI)).isoformat()
    ids_f = sorted({i for a, (ids, nm) in STOPY_FRED.items() if nm in bez for i in ids if i not in Fs})
    for sid in ids_f:   # zapas FRED tylko dla banków bez porównania (v245: w budżecie, bez ponowienia — z serwerów GitHub zwykle nie odpowiada)
        try:
            if zegar() - t0 + 30 > STOPY_BUDZET_S:
                raise TimeoutError('pominięte — limit czasu kontroli stóp')
            x = ust_fred_csv(_stopy_raz(STOPY_FRED_URL.format(id=sid, od=od_s), 30).decode('utf-8', 'replace'))
            if not x:   # v246: strona HTML z kodem 200 — błąd, nie cisza
                raise ValueError('plik bez liczb')
            Fs[sid] = x
        except Exception as e:  # noqa
            blad(sid, (sid,), e)
    if ids_f:
        Ps = stopy_porownanie(stopy, Fs, now, bledy=Bl)
    uz = {e for o in Ps for e in o.get('bledy') or []}   # v246: błędy ujęte w powodach banków nie powtarzają się na końcu wiersza; bez ucinania
    reszta = [e for e in dict.fromkeys(bs) if e not in uz]
    return {'wyniki': Ps, 'brak': '; '.join(reszta) if reszta else None}, stopy_uwagi(Ps, now)


def stopy_wiersz(sp, now=None):
    """v241: wiersz raportu z Z['stopy'] — porównanie albo brak odczytu (informacja, nigdy „zgodne”); zmiana stopy, której strona jeszcze nie
    ma: ℹ️ do STOPY_ZWLOKA_DNI dni, potem ⚠️ (jak uwaga). v243: bank bez porównania widoczny, z powodem. v244: zmiana także przy braku
    porównania (seria banku zaczyna się po dniu strony — NBP podaje tylko stopę obowiązującą)."""
    now = now or NOW
    n = lambda x: format(x, 'g').replace('.', ',')  # noqa: E731
    W = sp.get('wyniki') or []
    if not W:
        return f'- Stopy banków centralnych (strona vs źródło banku): brak odczytu ({sp.get("brak") or "brak wspólnych danych"}) ℹ️.'

    def stara(o):
        z = o.get('zmiana')
        return bool(z) and (now.date() - dt.date.fromisoformat(z[0])).days > STOPY_ZWLOKA_DNI

    def poz(o):
        z = o.get('zmiana')
        if z and o.get('od_poczatku'):   # v246: inna stopa już na początku danych źródła — dzień zmiany nieznany
            zm = f' (już {n(z[1])}% na początku danych źródła ({z[0]}) — strona jeszcze bez tej stopy)'
        else:
            zm = f' (zmiana {z[0]} na {n(z[1])}% — strona jeszcze bez niej)' if z else ''
        if o.get('brak'):
            return f'{o["bank"]}: brak porównania ({o["brak"]}) ' + ('⚠️' if stara(o) else 'ℹ️') + zm
        znak = '⚠️' if not o['zgodne'] or stara(o) else ('ℹ️' if z else '✅')
        return (f'{o["bank"]} {n(o["strona"])}% ' + ('= ' if o['zgodne'] else '≠ ') + f'{n(o["fred"])}% ({o.get("zrodlo") or "FRED"}) '
                + znak + zm)
    bez = [o for o in W if o.get('brak')]
    return ('- Stopy banków centralnych (strona vs źródło banku, ten sam dzień): '
            + '; '.join(poz(o) for o in [o for o in W if not o.get('brak')] + bez)
            + (f'; błędy odczytu: {sp["brak"]}' if bez and sp.get('brak') else '') + '.')


def stopy_uwagi(P, now=None):
    """v241: uwagi z wyniku stopy_porownanie — różnica w tym samym dniu; zmiana stopy starsza niż STOPY_ZWLOKA_DNI, której strona nie ma
    (v244: także przy braku porównania — seria banku zaczyna się po dniu strony). Bank bez porównania i bez zmiany — tylko informacja (v243)."""
    now = now or NOW
    n = lambda x: format(x, 'g').replace('.', ',')  # noqa: E731
    out = []
    for o in P or []:
        if not o.get('brak') and not o.get('zgodne'):
            out.append(f'stopy banków centralnych: {o["bank"]} na stronie {n(o["strona"])}% vs {o.get("zrodlo") or "FRED"} {n(o["fred"])}% ({o["data"]}) — sprawdzić plik stóp strony')
        z = o.get('zmiana')
        if z and o.get('od_poczatku'):   # v246: dzień zmiany nieznany — plik strony nie ma stopy tego banku od miesięcy (uwaga od razu)
            out.append(f'stopy banków centralnych: {o["bank"]} — źródło podaje {n(z[1])}% już na początku swoich danych ({z[0]}), strona pokazuje '
                       f'stopę z {o["data"]} ({n(o["strona"])}%); plik stóp strony nie aktualizuje tego banku od miesięcy — sprawdzić')
        elif z and (now.date() - dt.date.fromisoformat(z[0])).days > STOPY_ZWLOKA_DNI:
            out.append(f'stopy banków centralnych: {o["bank"]} zmienił stopę {z[0]} na {n(z[1])}% — strona pokazuje stopę z {o["data"]} '
                       f'({n(o["strona"])}%); źródło strony spóźnia się — zwykle samo się wyrówna')
    return out


# v225: kursy walut — migawki pliku strony (rynki.json fx: now/1D/1T/1M/1Q/1R, waluta za 1 USD; kurs EBC przez serwis pośredni) vs H.10 Fed
# (kursy w południe w Nowym Jorku, wydawane raz w tygodniu; bez klucza) — te same dni. Inna godzina ustalenia kursu (EBC 14:15 we Frankfurcie),
# więc małe różnice są normalne (06.10.2026: 3 daty × 20 walut, mediana 0,09%, najwięcej 0,79% — peso meksykańskie). v227: progi z 5 lat
# poprawnych danych (1 234 wspólne daty 10.2021–10.2026): największa różnica waluty 3,65% (jen 21.10.2022 — interwencja), najwyższa mediana dnia
# 1,85% (10.11.2022 — dane o inflacji w USA między ustaleniami kursów); progi 1,5% / 0,4% z v225 dawały ⚠️ w ok. 10% dni.
FX_H10 = ('https://www.federalreserve.gov/datadownload/Output.aspx?rel=H10&series=60f32914ab61dfab590e0e470153e3ae&lastobs=300&from=&to='
          '&filetype=csv&label=include&layout=seriescolumn&type=package')   # v227: 300 obserwacji (ok. 14 mies., ok. 57 KB) — też migawki 1Q i 1R
FX_PROG = 5.0      # % — waluta ponad tyle od H.10 tego samego dnia = ⚠️ (grube błędy: odwrócony kurs, zła jednostka; nigdy ❌)
FX_MED = 2.5       # % — mediana różnic jednej daty ponad tyle = ⚠️ (np. waluta bazowa źle podpisana); migawka sprzed tygodnia/miesiąca
#                    prawie nigdy nie przekracza progów (sprawdzone v231) — to kontrola grubych błędów, nie dat
FX_MIN_N = 5       # najmniej wspólnych walut, żeby oceniać medianę dnia
FX_MIGAWKI = ('now', '1D', '1T', '1M', '1Q', '1R')
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


def get(url, timeout=25, headers=None, limit=None):
    req = urllib.request.Request(url, headers={'User-Agent': 'CapitalFlowAI-kontrola/1.0', **(headers or {})})
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read() if limit is None else r.read(limit)   # v237: limit — najwyżej tyle bajtów (sprawdzanie, czy plik jest)
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


def _pl_przesuniecie_h(u):
    """v202: przesunięcie czasu polskiego bez bazy stref (reguła UE): czas letni od ostatniej niedzieli marca do ostatniej niedzieli października,
    zmiana o 01:00 UTC → 2, inaczej 1. `u` — chwila ze strefą."""
    u = u.astimezone(dt.timezone.utc)

    def last_sun(y, m):
        d = dt.date(y, m, 31)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)
    a = dt.datetime.combine(last_sun(u.year, 3), dt.time(1), dt.timezone.utc)
    b = dt.datetime.combine(last_sun(u.year, 10), dt.time(1), dt.timezone.utc)
    return 2 if a <= u < b else 1


def czas_pl(iso):
    """Czas polski (v202: Europe/Warsaw — latem UTC+2, zimą UTC+1; dotąd stałe UTC+2); zapis bez strefy = UTC; zły zapis = „—”."""
    try:
        t = dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            t = t.astimezone(ZoneInfo('Europe/Warsaw'))
        except Exception:   # brak bazy stref — reguła UE
            t = t.astimezone(dt.timezone(dt.timedelta(hours=_pl_przesuniecie_h(t))))
        return t.strftime('%d.%m.%Y, %H:%M')
    except Exception:
        return '—'


AW_UWAGA_H = 3        # v207: część automatu nie działa co najmniej tyle godzin (seria trwa) = ⚠️ z datą początku
AW_BLAD_H = 48        # v207: … co najmniej tyle godzin = BŁĄD (e-mail do właściciela): automat nie naprawił tego sam
AW_INFO_H = 24        # v207: awarie naprawione w ostatnich tylu godzinach — informacja ℹ️ (samonaprawa widoczna w raporcie)
AW_KLUCZ = re.compile(r'klucz\w*(?:\s+\S+)?\s+odrzuc|zły klucz|unauthori[sz]ed|HTTP\D{0,7}401\b|(?:invalid|incorrect) api ?key', re.I)
AW_LIMIT = re.compile(r'HTTP\D{0,7}(?:429|402)\b|too many requests|rate limit|credits|limit zapytań(?! w przebiegu)|dobowy limit|limit planu', re.I)   # v211: bez własnego limitu zbieracza
AW_BEZ_BLEDU = {   # v211/v215: części bez czerwieni z serii awarii — seria tylko informacją (wiek danych ocenia wiersz świeżości); v215: snb usunięte (False = błąd pobrania)
    'ici': 'fundusze USA — z założenia bez czerwieni (v134); wiek danych w wierszu świeżości', 'jpx': 'Japonia — tydzień czeka na publikację giełdy',
    'wycena_bg': 'dodatek SOPR — limit planu źródła (v132)'}


def _aw_t(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (TypeError, ValueError):
        return None
    return t.astimezone(dt.timezone.utc) if t.tzinfo else None


def _aw_h(h):
    """Godziny → „5 godz.” albo „3 dni 2 godz.” (pełne godziny w dół)."""
    h = int(h)
    return f'{h // 24} {"dzień" if h // 24 == 1 else "dni"} {h % 24} godz.' if h >= 24 else f'{h} godz.'


def awaria_rodzaj(e):
    """v207: błąd zbieracza → dopisek dla właściciela: odrzucony klucz (automat sam tego nie naprawi), limit planu (zwykle mija sam) albo ''."""
    e = str(e)
    if AW_KLUCZ.search(e):
        return ' — wygląda na odrzucony klucz: automat sam tego nie naprawi (co zrobić: napisz do Claude „sprawdź klucz z tego błędu”)'
    if AW_LIMIT.search(e):
        return ' — limit darmowego planu: zwykle mija sam (automat ponawia); jeśli trwa ponad 2 dni — napisz do Claude'
    return ''


def awarie_ocena(meta, now=None):
    """v207/v211: pole 'awarie' z meta.json (pamięć zbieracza między przebiegami) → {'trwa', 'naprawione', 'zniknely', 'uwagi', 'bledy'};
    element: {'czesc', 'od', 'ost', 'n', 'do', 'h'[, 'bez']} (h — godziny serii: do ostatniego przebiegu automatu (meta.at; nie dalej niż
    teraz) albo do końca serii). Seria trwa ≥ AW_BLAD_H h = błąd (automat nie naprawił tego sam), ≥ AW_UWAGA_H h = uwaga, krótsza —
    informacja; części z AW_BEZ_BLEDU — zawsze informacja ('bez'); zamknięte w ostatnich AW_INFO_H h — „naprawione” albo „zniknęły” (zn);
    poprzednia zamknięta seria (prev) — także w „naprawionych”. Brak pola (zbieracz sprzed v207) albo zły typ = None; złe wpisy pomijane."""
    now = now or NOW
    aw = meta.get('awarie') if isinstance(meta, dict) else None
    if not isinstance(aw, dict):
        return None
    ma = _aw_t(meta.get('at'))
    kon = min(now, ma) if ma else now
    Z = {'trwa': [], 'naprawione': [], 'zniknely': [], 'uwagi': [], 'bledy': []}
    for k, w in sorted(aw.items()):
        if not isinstance(w, dict):
            continue
        od, ost, n = _aw_t(w.get('od')), _aw_t(w.get('ost')), w.get('n')
        do = _aw_t(w.get('do')) if w.get('do') is not None else None
        if od is None or ost is None or not isinstance(n, int) or isinstance(n, bool) or n < 1 or (w.get('do') is not None and do is None):
            continue
        h = max(0.0, ((do or kon) - od).total_seconds() / 3600)
        x = {'czesc': str(k)[:40], 'od': w['od'], 'ost': w['ost'], 'n': n, 'do': w.get('do'), 'h': round(h, 1)}
        if do is None:
            x['bez'] = k in AW_BEZ_BLEDU
            Z['trwa'].append(x)
            opis = f'część automatu „{x["czesc"]}” nie działa od {czas_pl(w["od"])} ({_aw_h(h)}, nieudanych przebiegów z rzędu: {n})'
            if x['bez']:
                pass
            elif h >= AW_BLAD_H:
                Z['bledy'].append(opis + ' — automat nie naprawił tego sam; co zrobić: napisz do Claude „napraw część ' + x['czesc'] + '”')
            elif h >= AW_UWAGA_H:
                Z['uwagi'].append(opis + ' — automat ponawia sam; dane tej części mają swój wiek na stronie')
        elif (now - do).total_seconds() <= AW_INFO_H * 3600:
            Z['zniknely' if w.get('zn') is True else 'naprawione'].append(x)
        p = w.get('prev')
        if isinstance(p, list) and len(p) == 3:
            po, pd_, pn = _aw_t(p[0]), _aw_t(p[1]), p[2]
            if (po and pd_ and pd_ >= po and isinstance(pn, int) and not isinstance(pn, bool) and pn >= 1
                    and (now - pd_).total_seconds() <= AW_INFO_H * 3600):
                Z['naprawione'].append({'czesc': str(k)[:40], 'od': p[0], 'ost': p[1], 'n': pn, 'do': p[1], 'h': round((pd_ - po).total_seconds() / 3600, 1)})
    Z['naprawione'].sort(key=lambda x: (x['czesc'], x['od']))
    return Z


# v212: rodzaj BŁĘDU (początek treści) → co zrobić — prostymi słowami dla właściciela; kolejność = pierwszeństwo dopasowania
CO_ZROBIC = (   # v215: dopasowania po przeglądzie — „HTTP 200” i „bez czasu” osobno, publikacja Pages osobno, świeżość bez „to normalne”
    (re.compile(r'^strona główna: HTTP 200'),
     'Strona odpowiada, ale jej treść jest niepełna (nieudana publikacja) — napisz do Claude: „strona ma złą treść — sprawdź kontrolę”.'),
    (re.compile(r'^(strona główna|plik stanu \(meta\.json\) nie odpowiada)'),
     'Strona albo jej plik stanu nie odpowiada. Zwykle to chwilowa awaria serwera GitHub — sprawdź stronę za godzinę (stan serwera: githubstatus.com). '
     'Jeśli trwa ponad 3 godziny, napisz do Claude: „strona nie działa — sprawdź kontrolę”.'),
    (re.compile(r'^plik stanu bez czasu'),
     'Plik stanu automatu jest uszkodzony (bez czasu przebiegu) — to błąd w kodzie, sam się nie naprawi. Napisz do Claude: „plik stanu bez czasu”.'),
    (re.compile(r'^automat nie odświeżył danych'),
     'Automat nie odświeża danych od ponad 3 godzin — zegar zapasowy też nie pomógł. Najczęściej to przerwa po stronie GitHub (stan: githubstatus.com); '
     'jeśli trwa ponad 6 godzin, napisz do Claude: „automat stoi”.'),
    (re.compile(r'^publikacja zawieszona'),   # v232: przebieg czeka na środowisko, choć nikt nie musi zatwierdzać
     'Przebieg publikacji czeka na „zatwierdzenie”, którego nikt nie wymaga (usterka po stronie GitHub), a zegar zapasowy go nie anulował — '
     'dopóki czeka, strona nie dostaje nowych danych. Otwórz na GitHub zakładkę Actions, przebieg „Strona i dane” ze stanem „Waiting” '
     '→ „Cancel workflow”; następny przebieg ruszy sam w ciągu 10–20 min. Jeśli to wraca, napisz do Claude: „publikacja zawieszona”.'),
    (re.compile(r'^automat nie działa \(publikacja GitHub Pages\)'),   # v219: tylko seria samych porażek publikacji (przebiegi_ocena)
     'Ostatnie przebiegi padły na publikacji strony — to zwykle chwilowa awaria po stronie GitHub. Sprawdź za 1–2 godziny; jeśli trwa dłużej, '
     'napisz do Claude: „publikacja strony nie działa”.'),
    (re.compile(r'^automat nie działa'),
     'Ostatnie przebiegi automatu kończą się błędem. Napisz do Claude: „przebiegi automatu kończą się błędem”.'),
    (re.compile(r'^część automatu „'),
     'Część automatu nie działa od ponad 2 dni (szczegóły niżej) — napisz do Claude tak, jak podpowiada wiersz błędu.'),
    (re.compile(r'^zbieracz zgłasza błędy'),
     'Zbieracz od kilku dni zgłasza błędy — napisz do Claude: „napraw błędy zbieracza z kontroli”.'),
    (re.compile(r'^kapitalizacja krypto'),
     'Dwa źródła tej samej liczby bardzo się różnią — jedno może podawać złe dane. Napisz do Claude: „sprawdź różnicę źródeł z kontroli”.'),
    (re.compile(r': dane z .* temu \('),
     'Dane źródła są dużo starsze niż zwykle (ponad dwa razy dłużej niż norma; weekendy już odliczone) — źródło przestało publikować '
     '(np. przerwa w pracy urzędu) albo automat nie może ich pobrać. Napisz do Claude: „sprawdź źródło z kontroli”.'),
    (re.compile(r'^limit planu '),   # v222: licznik zużycia darmowych planów
     'Darmowy plan jednego źródła danych jest (prawie) wyczerpany — część liczb może chwilowo zniknąć, aż limit się odnowi (o północy UTC '
     'albo z nowym miesiącem); nic nie psuje się na stałe. Napisz do Claude: „zmniejsz liczbę zapytań — limit planu z kontroli”.'),
)
CO_ZROBIC_INNE = 'Napisz do Claude: „sprawdź błąd z kontroli” — w raporcie niżej jest jego treść.'
WAIT_UWAGA_MIN, WAIT_BLAD_MIN = 30, 120   # v232: przebieg „Strona i dane” w stanie waiting tak długo — uwaga / błąd (zegar anuluje po 15 min)


def co_zrobic(bledy):
    """v212: treści BŁĘDÓW → lista podpowiedzi „co zrobić” (każda raz, w kolejności pierwszego błędu danego rodzaju; nieznany — ogólna)."""
    out = []
    for b in bledy or []:
        h = next((x for r, x in CO_ZROBIC if r.search(str(b))), CO_ZROBIC_INNE)
        if h not in out:
            out.append(h)
    return out


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
FED_PROG = 90              # min — wiek cen (part_at.ks; automat co 10 min): żółte po progu, czerwone po 2× — osobny wiersz, lista SWIEZOSC bez zmian
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
ZG_KOL = ['date', 'cap_gap_pct', 'tga_gap_pct', 'stab_gap_pct']   # kontrola/zgodnosc.csv: tylko różnice procentowe (bez wartości źródeł); puste pole = brak odczytu (v209: + stablecoiny)


def zgodnosc_csv(path):
    """{dzień: {'cap': %, 'tga': %, 'stab': %}} — pusta komórka albo brak kolumny (plik sprzed v209) = brak (klucz pominięty)."""
    rows = {}
    if os.path.exists(path):
        with open(path, encoding='utf-8', newline='') as f:
            r = csv.reader(f); next(r, None)
            for row in r:
                if len(row) >= 2 and row[0] != 'date':
                    rec = {}
                    for i, kk in ((1, 'cap'), (2, 'tga'), (3, 'stab')):
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
            wtr.writerow([d] + [('%.3f' % rows[d][kk]) if isinstance(rows[d].get(kk), (int, float)) else '' for kk in ('cap', 'tga', 'stab')])


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


def stab_porownanie(krypto, cmc):
    """v209: podaż stablecoinów z dwóch plików strony → {'a': DefiLlama (krypto.json stabh.cur, USD), 'b': CoinMarketCap (cmc.json stable_mcap),
    'roznica_pct': (a − b) / b × 100, 'odstep_h': odstęp pobrań plików, 'data': stabh.asof} albo None (brak liczby). Odstęp > STAB_MAX_H —
    'roznica_pct' None (bez porównania; liczby różnych chwil)."""
    st = krypto.get('stabh') if isinstance(krypto, dict) and isinstance(krypto.get('stabh'), dict) else {}
    a, b = st.get('cur'), (cmc.get('stable_mcap') if isinstance(cmc, dict) else None)
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0  # noqa: E731
    if not (num(a) and num(b)):
        return None
    try:
        t1 = dt.datetime.fromisoformat(str(krypto.get('at')).replace('Z', '+00:00')); t2 = dt.datetime.fromisoformat(str(cmc.get('at')).replace('Z', '+00:00'))
        h = abs((t1 - t2).total_seconds()) / 3600 if t1.tzinfo and t2.tzinfo else None
    except (TypeError, ValueError):
        h = None
    r = round((a - b) / b * 100.0, 3) if h is not None and h <= STAB_MAX_H else None
    return {'a': float(a), 'b': float(b), 'roznica_pct': r, 'odstep_h': (round(h, 1) if h is not None else None), 'data': st.get('asof')}


def ust_fred_csv(txt):
    """v209: CSV z FRED (observation_date,DGS10) → {dzień: rentowność}; '.' albo puste (święto) i złe wiersze pominięte."""
    out = {}
    for line in str(txt or '').splitlines()[1:]:
        p = line.strip().split(',')
        if len(p) == 2 and re.match(r'^\d{4}-\d{2}-\d{2}$', p[0]):
            try:
                out[p[0]] = float(p[1])
            except ValueError:
                pass
    return out


def ust_fed_csv(txt):
    """v211: CSV H.15 z serwisu danych Rady Gubernatorów Fed (wiersze opisu, potem „Time Period” z kodami serii, potem dni) → {dzień: rentowność
    10L}; 'ND' (brak notowania) i złe wiersze pominięte; brak kolumny 10L albo nagłówka = {}."""
    out, col = {}, None
    for r in csv.reader(str(txt or '').splitlines()):
        if not r:
            continue
        if r[0].strip() == 'Time Period':
            col = r.index(UST_FED_KOL) if UST_FED_KOL in r else None
            continue
        if col is not None and len(r) > col and re.match(r'^\d{4}-\d{2}-\d{2}$', r[0]):
            try:
                out[r[0]] = float(r[col])
            except ValueError:
                pass
    return out


def fx_h10_csv(txt):
    """v225: CSV H.10 z serwisu danych Rady Gubernatorów Fed (wiersze opisu — „Currency:” z kodami walut, „Unique Identifier:” z kodami serii:
    RXI$US = USD za jednostkę waluty, RXI = waluta za 1 USD; potem dni) → {dzień: {waluta: ile waluty za 1 USD}}; 'ND' (brak notowania), zera,
    kody spoza trzech liter i złe wiersze pominięte; bez wierszy walut = {}."""
    cur, inv, out = None, None, {}
    for r in csv.reader(str(txt or '').splitlines()):
        if not r:
            continue
        k = r[0].strip()
        if k == 'Currency:':
            cur = [c.strip() for c in r[1:]]
            continue
        if k.startswith('Unique Identifier'):
            inv = ['$US' in c for c in r[1:]]
            continue
        if cur and inv and len(inv) == len(cur) and re.match(r'^\d{4}-\d{2}-\d{2}$', k):
            d = {}
            for c, i, v in zip(cur, inv, r[1:]):
                try:
                    x = float(v)
                except ValueError:
                    continue
                if x > 0 and re.match(r'^[A-Z]{3}$', c):
                    d[c] = 1 / x if i else x
            if d:
                out[k] = d
    return out


def fx_uwagi(f):
    """v227: uwagi kontroli z wyniku fx_porownanie — liczby z przecinkiem dziesiętnym (nazwa „H.10” bez zmian)."""
    n = lambda x, fmt: format(x, fmt).replace('.', ',')  # noqa: E731
    out = []
    if isinstance(f, dict) and f.get('zle'):
        out.append(f'kursy walut: plik strony vs H.10 (Fed) różnią się ponad {n(FX_PROG, "g")}%: '
                   + ', '.join(f'{c} {d}: {n(v, "g")} vs {n(h, "g")} ({n(r, "+.2f")}%)' for d, c, v, h, r in f['zle'][:6]))
    if isinstance(f, dict) and f.get('baza'):   # v231
        out.append('kursy walut: migawki z walutą bazową inną niż USD: ' + ', '.join(f'{k} ({b})' for k, b in f['baza'])
                   + ' — strona przyjmuje tylko USD (te kursy pominie); sprawdzić serwis pośredni kursów')
    if isinstance(f, dict) and f.get('med_zle'):
        out.append(f'kursy walut: mediana różnic z H.10 (Fed) ponad {n(FX_MED, "g")}% dla ' + ', '.join(f'{d} ({n(m, ".2f")}%)' for d, m in f['med_zle'])
                   + ' — sprawdzić walutę bazową i datę migawki')
    return out


def fx_baza(rynki):
    """v235: migawki kursów pliku strony z polem base innym niż USD → [[migawka, waluta albo „brak”], …] — niezależnie od H.10 (gdy H.10 nie
    odpowiada, ostrzeżenie zostaje; strona takie migawki odrzuca). Bez pola base (stary format) — bez uwagi."""
    fx = rynki.get('fx') if isinstance(rynki, dict) else None
    if not isinstance(fx, dict):
        return []
    return [[k, fx[k]['base'][:8] if isinstance(fx[k].get('base'), str) and fx[k]['base'] else 'brak'] for k in FX_MIGAWKI
            if isinstance(fx.get(k), dict) and 'base' in fx[k] and fx[k].get('base') != 'USD']


def fx_porownanie(rynki, h10):
    """v225: migawki kursów pliku strony (rynki.json → fx[now|1D|1T|1M|1Q|1R] = {date, base: USD, rates: {waluta: ile za 1 USD}}) vs H.10 z tych
    samych dni → {'daty': [[dzień, n walut, mediana |%|, waluta z największą różnicą, jej %], …], 'zle': [[dzień, waluta, strona, H.10, %], …]
    (ponad FX_PROG), 'med_zle': [[dzień, mediana %], …] (ponad FX_MED przy co najmniej FX_MIN_N walutach)}; brak migawek albo H.10 = None.
    Ta sama data w kilku migawkach — porównana raz (pierwsza w kolejności FX_MIGAWKI)."""
    fx = rynki.get('fx') if isinstance(rynki, dict) else None
    baza = fx_baza(rynki)   # v231/v233/v235: migawka z inną walutą bazową (także pusta) — ⚠️, także bez H.10
    if not isinstance(fx, dict) or not isinstance(h10, dict) or not h10:
        return {'daty': [], 'zle': [], 'med_zle': [], 'baza': baza} if baza else None
    by = {}
    for k in FX_MIGAWKI:
        s = fx.get(k)
        if isinstance(s, dict) and s.get('base') == 'USD' and isinstance(s.get('date'), str) and isinstance(s.get('rates'), dict):
            by.setdefault(s['date'], s['rates'])
    if not by and not baza:
        return None
    out = {'daty': [], 'zle': [], 'med_zle': [], 'baza': baza}
    for d in sorted(by):
        H = h10.get(d)
        if not isinstance(H, dict):
            continue
        rs = [(c, float(v), H[c], (float(v) / H[c] - 1) * 100) for c, v in by[d].items()
              if c in H and isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0]
        if not rs:
            continue
        med = statistics.median(abs(x[3]) for x in rs)
        mx = max(rs, key=lambda x: abs(x[3]))
        out['daty'].append([d, len(rs), round(med, 3), mx[0], round(mx[3], 3)])
        out['zle'] += [[d, c, v, round(h, 6), round(r, 3)] for c, v, h, r in rs if abs(r) > FX_PROG]
        if len(rs) >= FX_MIN_N and med > FX_MED:
            out['med_zle'].append([d, round(med, 3)])
    return out


def ust_porownanie(rynki, fred):
    """v209: rentowność 10L USA — plik strony (rynki.json ust: [[dzień, %], …]) vs H.15 (DGS10, {dzień: %}) z tych samych dni, ostatnie UST_DNI dat
    pliku strony → {'porownane': n, 'do': ostatnia wspólna data, 'roznice': [[dzień, a, b, |a − b|], …] ponad UST_PROG} albo None (brak serii)."""
    s = rynki.get('ust') if isinstance(rynki, dict) else None
    if not isinstance(s, list) or not isinstance(fred, dict):
        return None
    ost = [r for r in s if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str) and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)][-UST_DNI:]
    wsp = [(d, float(v), fred[d]) for d, v in ost if d in fred]
    return {'porownane': len(wsp), 'do': (wsp[-1][0] if wsp else None),
            'roznice': [[d, a, b, round(abs(a - b), 3)] for d, a, b in wsp if abs(a - b) > UST_PROG + 1e-9]}


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


WH_DOBA_BLOKI = (6900, 7500)   # v174: migawki oddalone o ok. dobę (12 s na blok Ethereum: 23–25 h) — inny odstęp: sald nie porównujemy z przepływami 24 h
WH_RAZY = 3.0                  # v174: rozbieżność pary ponad tyle × jej mediana z wcześniejszych porównywalnych dni = uwaga (zwykła rozbieżność to norma)
WH_HIST_MIN = 3                # v174: mniej wcześniejszych porównywalnych dni pary = bez oceny (informacja)


def _wh_csv(path):
    """v174/v175: archiwum/wieloryby.csv → {dzień: {(giełda, aktywo): wiersz}}; zły nagłówek albo brak pliku = None."""
    if not os.path.exists(path):
        return None
    by = {}
    with open(path, encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        head = next(r, None)
        if not head or head[:5] != ['date', 'exchange', 'asset', 'balance', 'balance_usd']:
            return None
        for row in r:
            if len(row) >= 9:
                by.setdefault(row[0], {})[(row[1], row[2])] = row
    return by


def _wh_rozb(a, b):
    """v174/v175: rozbieżności par dnia `b` wobec dnia `a` → {(giełda, aktywo): (zmiana, netto, |zmiana − netto|, odstęp w blokach albo None)};
    odstęp z bloków WŁASNYCH migawek pary (giełda bez nowego odczytu ma w archiwum blok poprzedniego)."""
    out = {}
    for k, row in b.items():
        prev = a.get(k)
        if not prev:
            continue
        try:
            u, u0, usd, net = float(row[3]), float(prev[3]), float(row[4]), float(row[7])
        except ValueError:
            continue
        if not u:
            continue
        delta = (u - u0) * (usd / u)
        sp = int(row[8]) - int(prev[8]) if row[8].isdigit() and prev[8].isdigit() else None
        out[k] = (delta, net, abs(delta - net), sp)
    return out


ZUZ_PLANY = (('cg', 'CoinGecko (Demo)', 'mies', 10000, 'zapytań'),        # v222: limity darmowych planów (stan 06.10.2026; inny plan = zmiana tutaj)
             ('cmc', 'CoinMarketCap (Basic)', 'mies', 15000, 'zapytań'),       # v226: 15 000 według dostawcy (06.10.2026)
             ('td', 'Twelve Data (Basic)', 'doba', 800, 'kredytów'))
ZUZ_UWAGA = 0.8       # v222: prognoza miesiąca albo wczorajsza doba ≥ 80% limitu = ⚠️
ZUZ_BLAD = 0.95       # v222: zużyte w miesiącu ≥ 95% limitu albo wczoraj ≥ 100% limitu doby = ❌
ZUZ_PROG_H = 24       # v222: prognoza miesiąca dopiero po dobie liczenia
ZUZ_MP_DNI = 7       # v226: w pierwszych tylu dniach miesiąca oceniany też koniec poprzedniego (przekroczenie po ostatniej kontroli)


def _zuz_l(n):
    return f'{n:,.0f}'.replace(',', ' ')


def _norma(med, dni, fmt='{:.2f}%'):
    """v245: „, norma (mediana N dni) X%” do wierszy porównań — bez mediany (za krótka historia) pusto (było „norma (mediana 0 dni) — —”)."""
    return f', norma (mediana {dni} dni) {fmt.format(med)}' if med is not None else ''


def _zuz_ok(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def zuzycie_ocena(meta):
    """v222: licznik zużycia darmowych planów (meta.json → zuzycie) → {'plany': [{'k', 'tekst', 'znak'}], 'uwagi', 'bledy'}; plik bez pola
    (zbieracz sprzed v222) albo bez czasu = None. Liczby automatu to dolna granica (przebieg bez zapisu stanu nie dolicza się); CoinMarketCap
    także według samego dostawcy (raport co 6 h). Miesiąc i doba — kalendarz UTC."""
    z = meta.get('zuzycie') if isinstance(meta, dict) else None
    at = _aw_t(meta.get('at')) if isinstance(meta, dict) else None
    if not isinstance(z, dict) or at is None:
        return None
    out = {'plany': [], 'uwagi': [], 'bledy': []}
    for k, nazwa, okres, lim, jedn in ZUZ_PLANY:
        q = z.get(k) if isinstance(z.get(k), dict) else None
        od = _aw_t(q.get('od')) if q else None
        if od is None:
            continue
        krotko, znak = nazwa.split(' (')[0], '✅'
        ds0 = q.get('dost') if isinstance(q.get('dost'), dict) else {}
        ml = ds0.get('mies') if isinstance(ds0.get('mies'), list) and len(ds0['mies']) == 3 else [None] * 3
        if okres == 'mies' and _zuz_ok(ml[2]) and ml[2] > 0:
            lim = ml[2]   # v223: limit miesiąca według samego dostawcy (CoinMarketCap 06.10: 15 000, nie 10 000)
        rada = f'co zrobić: napisz do Claude „zmniejsz liczbę zapytań do {krotko}”'
        if okres == 'mies':
            ms = at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if q.get('m') != at.strftime('%Y-%m') or not _zuz_ok(q.get('nm')):
                out['plany'].append({'k': k, 'tekst': f'{nazwa} — brak licznika w tym miesiącu', 'znak': 'ℹ️'})
                continue
            nm, start = q['nm'], max(ms, od)
            t = f'{nazwa} — {jedn} w tym miesiącu' + (f' (od {czas_pl(od.isoformat())})' if od > ms else '') + f': {_zuz_l(nm)}'
            h = (at - start).total_seconds() / 3600
            if h >= ZUZ_PROG_H:
                dni = ((ms + dt.timedelta(days=32)).replace(day=1) - ms).days
                prog = nm / h * dni * 24
                t += f', prognoza na miesiąc ok. {_zuz_l(prog)} z limitu {_zuz_l(lim)} ({prog / lim * 100:.0f}%)'
                if prog >= ZUZ_UWAGA * lim:
                    znak = '⚠️'
                    out['uwagi'].append(f'{nazwa}: prognoza zużycia planu w miesiącu ok. {_zuz_l(prog)} z {_zuz_l(lim)} {jedn} — '
                                        + ('ponad limit' if prog >= lim else 'zapas maleje') + f'; {rada}')
            else:
                t += ' (prognoza po pierwszej dobie liczenia)'
            if nm >= ZUZ_BLAD * lim:
                znak = '❌'
                out['bledy'].append(f'limit planu {nazwa} prawie wyczerpany: {_zuz_l(nm)} z {_zuz_l(lim)} {jedn} w tym miesiącu (licznik automatu)')
            mp, pm_ = q.get('mp'), (ms - dt.timedelta(days=1)).strftime('%Y-%m')
            if at.day <= ZUZ_MP_DNI and isinstance(mp, list) and len(mp) == 2 and mp[0] == pm_ and _zuz_ok(mp[1]) and mp[1] >= ZUZ_BLAD * lim:
                znak = '❌' if znak == '❌' else '⚠️'   # v226: koniec poprzedniego miesiąca (przekroczenie mogło przyjść po ostatniej kontroli)
                out['uwagi'].append(f'{nazwa}: w poprzednim miesiącu ({mp[0]}) automat zużył {_zuz_l(mp[1])} z {_zuz_l(lim)} {jedn} — limit był prawie '
                                    f'wyczerpany, część liczb mogła zniknąć pod koniec miesiąca; {rada}')
        else:
            dp, wcz = q.get('dp'), (at - dt.timedelta(days=1)).strftime('%Y-%m-%d')
            if isinstance(dp, list) and len(dp) == 2 and dp[0] == wcz and _zuz_ok(dp[1]) and dp[0] > od.strftime('%Y-%m-%d'):
                t = f'{nazwa} — {jedn} wczoraj (doba UTC): {_zuz_l(dp[1])} z limitu {_zuz_l(lim)} ({dp[1] / lim * 100:.0f}%)'
                if dp[1] >= lim:
                    znak = '❌'
                    out['bledy'].append(f'limit planu {nazwa} wyczerpany wczoraj: {_zuz_l(dp[1])} z {_zuz_l(lim)} {jedn} (licznik automatu) — '
                                        'część notowań mogła nie przyjść')
                elif dp[1] >= ZUZ_UWAGA * lim:
                    znak = '⚠️'
                    out['uwagi'].append(f'{nazwa}: wczoraj {_zuz_l(dp[1])} z {_zuz_l(lim)} {jedn} limitu doby — zapas maleje; {rada}')
            else:
                t = f'{nazwa} — {jedn} wczoraj: brak pełnej doby licznika'
            if q.get('d') == at.strftime('%Y-%m-%d') and _zuz_ok(q.get('n')):
                t += f'; w bieżącej dobie (od północy UTC): {_zuz_l(q["n"])}'
        ds = q.get('dost') if isinstance(q.get('dost'), dict) else None
        if ds and ds.get('blad'):
            t += f'; raport dostawcy niedostępny ({str(ds["blad"])[:80]})'
        elif ds:
            def trzy(x):
                return (list(x) + [None] * 3)[:3] if isinstance(x, list) else [None] * 3
            u, left, lm = trzy(ds.get('mies'))
            lm = lm if _zuz_ok(lm) and lm > 0 else (u + left if _zuz_ok(u) and _zuz_ok(left) and u + left > 0 else None)
            if _zuz_ok(u) and lm:
                t += f'; według dostawcy w miesiącu: {_zuz_l(u)} z {_zuz_l(lm)} ({u / lm * 100:.0f}%, stan {czas_pl(ds.get("at"))})'
                if u >= ZUZ_BLAD * lm:
                    znak = '❌'
                    out['bledy'].append(f'limit planu {nazwa} prawie wyczerpany według dostawcy: {_zuz_l(u)} z {_zuz_l(lm)} w tym miesiącu')
                elif u >= ZUZ_UWAGA * lm:
                    znak = '❌' if znak == '❌' else '⚠️'
                    out['uwagi'].append(f'{nazwa}: według dostawcy zużyto {_zuz_l(u)} z {_zuz_l(lm)} w tym miesiącu — zapas maleje; {rada}')
            du, dleft, dlm = trzy(ds.get('dz'))
            if _zuz_ok(du) and _zuz_ok(dlm) and dlm > 0 and du >= dlm:
                znak = '❌' if znak == '❌' else '⚠️'
                out['uwagi'].append(f'{nazwa}: według dostawcy dzienny limit wyczerpany ({_zuz_l(du)} z {_zuz_l(dlm)}, stan {czas_pl(ds.get("at"))}) — '
                                    f'część liczb może poczekać do północy UTC; {rada}')
        out['plany'].append({'k': k, 'tekst': t, 'znak': znak})
    return out


WH_LISTY_MIES = ('OKX', 'Bybit', 'KuCoin')   # v218: giełdy z comiesięcznym raportem dowodu rezerw (wieloryby.json → gieldy[*].since) — listy do odświeżania
WH_LISTY_DNI = 45                             # v218: lista starsza = uwaga (portfele dodane przez giełdę od tego czasu nie są liczone)


def wh_listy_ocena(j, now=None):
    """v218: wiek list portfeli giełd z miesięcznym raportem dowodu rezerw → {'wszystkie': [(giełda, data, dni)], 'stare': [… > WH_LISTY_DNI]};
    brak pliku albo pola gieldy = None; giełda bez poprawnej daty RRRR-MM-DD pominięta."""
    now = now or NOW
    G = j.get('gieldy') if isinstance(j, dict) and isinstance(j.get('gieldy'), dict) else None
    if G is None:
        return None
    A = []
    for g in WH_LISTY_MIES:
        s = G[g].get('since') if isinstance(G.get(g), dict) else None
        try:
            A.append((g, s, (now.date() - dt.date.fromisoformat(s)).days))
        except (TypeError, ValueError):
            continue
    return {'wszystkie': A, 'stare': [x for x in A if x[2] > WH_LISTY_DNI]}


# v237/v242: nowe raporty dowodu rezerw giełd (listy portfeli wielorybów) — sprawdzanie codzienne, bez pobierania całych plików
WH_NOWE_OD_DNI = 20        # nowszego raportu szukamy od tylu dni po dacie obecnej listy (raporty miesięczne)
WH_NOWE_MAX = 30           # najwyżej tyle dat na giełdę, od najnowszej
WH_NOWE_BUDZET_S = 60      # nowe zapytanie tylko, gdy od początku minęło mniej niż tyle sekund minus jego limit (całość ok. 60–70 s)
WH_NOWE_ADRESY = {'OKX': 'https://static.okx.com/cdn/okx/por/chain/por_csv_{r}{mm}{dd}00_V1.zip',
                  'Bybit': 'https://www.bybit.com/common-static/cht-static/por/Bybit_PoR_Audit_{r}_{mies}_{dd}.pdf'}
WH_NOWE_SYGN = {'OKX': b'PK\x03\x04', 'Bybit': b'%PDF'}   # v242: trafienie tylko z podpisem pliku (strona HTML z kodem 200 to nie plik)
WH_NOWE_BRAK = {'OKX': (404,), 'Bybit': (403, 404)}       # v242: „nie ma pliku” wg giełdy (OKX: 404 XML; Bybit: 403 ze stroną WWW); inne = nie wiadomo
WH_NOWE_PAUZA_S = 0.3      # v242: przerwa między zapytaniami do tej samej giełdy
WH_NOWE_KUCOIN = 'https://www.kucoin.com/_api/asset-front/proof-of-reserves/asset-reserve'
MIES_EN = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')


def wh_plik_jest(url, g=None):
    """v237/v242: czy plik istnieje — tylko pierwsze 1 024 bajty (Range): 200/206 z podpisem pliku giełdy = jest; kod „nie ma pliku” tej giełdy
    (WH_NOWE_BRAK) = nie ma; wszystko inne (blokada, limit, sieć, strona HTML z kodem 200) = None (nie wiadomo)."""
    try:
        st, body, _ = get(url, timeout=10, headers={'Range': 'bytes=0-1023'}, limit=1024)
    except urllib.error.HTTPError as e:
        if e.code not in WH_NOWE_BRAK.get(g, (404,)):
            return None
        if g == 'Bybit' and e.code == 403:   # v243: 403 = „nie ma pliku” tylko ze stroną brakującego pliku (Server: AmazonS3); blokada wygląda inaczej
            srv = (e.headers.get('Server') if e.headers is not None and hasattr(e.headers, 'get') else None) or ''
            return False if 'AmazonS3' in str(srv) else None
        return False
    except Exception:  # noqa — sieć, limit czasu, zaślepka testu bez parametru limit
        return None
    if st not in (200, 206):
        return None
    sg = WH_NOWE_SYGN.get(g)
    return True if sg is None or (isinstance(body, (bytes, bytearray)) and bytes(body[:len(sg)]) == sg) else None


def wh_nowe_adresy(g, d):
    """v237: adresy pliku giełdy g z dnia d (Bybit: dzień jednocyfrowy w dwóch zapisach — „05” i „5”)."""
    w = WH_NOWE_ADRESY[g]
    dd = [f'{d.day:02d}'] + ([str(d.day)] if g == 'Bybit' and d.day < 10 else [])
    return [w.format(r=d.year, mm=f'{d.month:02d}', dd=x, mies=MIES_EN[d.month - 1]) for x in dd]


def wh_nowe_raporty(gieldy, now=None, budzet_s=WH_NOWE_BUDZET_S, zegar=time.monotonic, spij=time.sleep):
    """v237/v242: listy portfeli giełd z raportów miesięcznych (wieloryby.json → gieldy[g].since, .url) → {giełda: {'od', 'nowy' (data nowszego
    raportu albo None), 'lista' (True — plik z adresami jest; False — audyt bez raportu z listą), 'prob' (dat sprawdzonych), 'zakres' ([od, do]
    sprawdzonych dni), 'kontrola' (plik obecnej listy: True — odpowiedział plikiem, 'brak' — nie, None — nie sprawdzany), 'nie_wiadomo', 'przerwane'}}. OKX i Bybit: najpierw
    plik obecnej listy — gdy nie odpowiada plikiem (blokada serwera, limit), „nie wiadomo”, nigdy „brak nowszego”."""
    now = now or NOW
    G = gieldy if isinstance(gieldy, dict) else {}
    t0, out = zegar(), {}
    czas_ok = lambda lim: zegar() - t0 + lim <= budzet_s  # noqa: E731
    for g in WH_LISTY_MIES:
        c = G.get(g) if isinstance(G.get(g), dict) else {}
        try:
            od = dt.date.fromisoformat(c.get('since'))
        except (TypeError, ValueError):
            continue
        o = {'od': c['since'], 'nowy': None, 'lista': None, 'prob': 0, 'zakres': None, 'kontrola': None, 'nie_wiadomo': 0, 'przerwane': False}
        out[g] = o
        if g == 'KuCoin':
            if not czas_ok(15):
                o['przerwane'] = True
                continue
            try:
                j = json.loads(get(WH_NOWE_KUCOIN, timeout=15)[1])
                d = j.get('data') if isinstance(j, dict) and isinstance(j.get('data'), dict) else {}
                ms = d.get('latestAuditDate')
                if not isinstance(ms, (int, float)) or isinstance(ms, bool):
                    raise ValueError('brak daty audytu')
                o['prob'] = 1
                a = dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date()
                if a > od:
                    u = d.get('auditReportUrl')
                    o['nowy'], o['lista'] = a.isoformat(), bool(u) and u != c.get('url')   # v242: ten sam link co obecna lista — nic nowego
            except Exception:  # noqa
                o['nie_wiadomo'] += 1
            continue
        if g not in WH_NOWE_ADRESY:
            continue
        dni = [od + dt.timedelta(days=i) for i in range(WH_NOWE_OD_DNI, (now.date() - od).days + 1)][::-1][:WH_NOWE_MAX]
        if not dni:
            continue
        ku = c.get('url') if g == 'Bybit' and isinstance(c.get('url'), str) and c['url'].startswith('https://') else wh_nowe_adresy(g, od)[0]
        if not czas_ok(10):
            o['przerwane'] = True
            continue
        o['kontrola'] = True if wh_plik_jest(ku, g) is True else 'brak'   # v242: próba kontrolna — plik obecnej listy musi odpowiedzieć plikiem
        if o['kontrola'] != True:  # noqa: E712
            o['nie_wiadomo'] += 1
            continue
        ciagly = True   # v246: zakres tylko z ciągłych dni od najnowszego — dzień bez odpowiedzi go zamyka
        for d in dni:
            if not czas_ok(20):
                o['przerwane'] = True
                break
            spij(WH_NOWE_PAUZA_S)
            o['prob'] += 1
            wyn = []
            for u in wh_nowe_adresy(g, d):
                wyn.append(wh_plik_jest(u, g))
                if wyn[-1] is True:
                    break
            if True in wyn:
                o['nowy'], o['lista'] = d.isoformat(), True
                break
            if None in wyn:
                o['nie_wiadomo'] += 1
                ciagly = False
            elif ciagly:   # v243: zakres „brak nowszego” tylko z dni, na które każda odpowiedź brzmiała „nie ma pliku” (v246: ciągłych)
                o['zakres'] = [d.isoformat(), o['zakres'][1] if o['zakres'] else d.isoformat()]
        if o['prob'] and not o['nowy'] and czas_ok(10) and wh_plik_jest(ku, g) is not True:   # v243: druga próba kontrolna — blokada w trakcie
            o['kontrola'] = 'brak'
            o['nie_wiadomo'] += 1
    return out


def wh_nowe_wiersz(W):
    """v237/v242: wiersz raportu „Nowe raporty dowodu rezerw giełd” — zakres naprawdę sprawdzonych dni; „nie wiadomo” i „przerwane” osobno."""
    if W.get('_blad'):   # v243: błąd całego sprawdzania — wiersz zostaje, „nie wiadomo”
        return f'- Nowe raporty dowodu rezerw giełd (listy portfeli): nie wiadomo (błąd sprawdzania: {str(W["_blad"])[:80]}) ℹ️.'
    cz = []
    for g, o in W.items():
        if o.get('nowy') and o.get('lista'):
            cz.append(f'{g} — nowy raport z listą portfeli z {o["nowy"]} (obecna z {o["od"]}) ⚠️')
        elif o.get('nowy'):
            cz.append(f'{g} — audyt z {o["nowy"]}, raport z listą portfeli jeszcze niedostępny ℹ️')
        elif o.get('kontrola') == 'brak':
            cz.append(f'{g} — nie wiadomo (plik obecnej listy nie odpowiada plikiem — możliwa blokada serwera) ℹ️')
        elif o.get('przerwane'):
            cz.append(f'{g} — sprawdzanie przerwane (limit czasu)' + (f'; brak nowszego w dniach {o["zakres"][0]}–{o["zakres"][1]}' if o.get('zakres') else '')
                      + (f'; dni bez odpowiedzi: {o["nie_wiadomo"]}' if o.get('nie_wiadomo') else '') + ' ℹ️')
        elif o.get('nie_wiadomo'):
            cz.append(f'{g} — nie wiadomo (źródło nie odpowiedziało albo odpowiedź niejasna) ℹ️')
        elif not o.get('prob'):
            cz.append(f'{g} — sprawdzanie od {(dt.date.fromisoformat(o["od"]) + dt.timedelta(days=WH_NOWE_OD_DNI)).isoformat()} (raport miesięczny)')
        elif o.get('zakres'):
            cz.append(f'{g} — brak nowszego w dniach {o["zakres"][0]}–{o["zakres"][1]} ✅')
        else:
            cz.append(f'{g} — brak nowszego niż {o["od"]} ✅')
    return '- Nowe raporty dowodu rezerw giełd (listy portfeli; sprawdzone dziś): ' + '; '.join(cz) + '.'


def wh_zmiany(j):
    """v230: wieloryby.json → {giełda: dzień zmiany listy portfeli (gieldy[g].zmiana)}; brak = {}."""
    G = j.get('gieldy') if isinstance(j, dict) and isinstance(j.get('gieldy'), dict) else {}
    return {g: v['zmiana'] for g, v in G.items() if isinstance(v, dict) and isinstance(v.get('zmiana'), str) and re.match(r'^\d{4}-\d{2}-\d{2}$', v['zmiana'])}


WH_POLNOC_H = 2       # v249: migawka „pierwsza z doby” z pliku wielorybów (hist) — tylko wykonana do tylu godzin po północy UTC
WH_POLNOC_SP = 7200   # v249: para z migawek o północy = pełna doba (24 h w blokach po 12 s) — spełnia WH_DOBA_BLOKI


def _wh_polnoc(hist):
    """v249: data/wieloryby.json → hist ({giełda: [[dzień, czas bloku, eth, usdt, usdc, wersja listy], …]}) → {dzień: {(giełda, aktywo): (jednostki,
    czas, wersja listy)}}; tylko migawki z tego samego dnia, wykonane do WH_POLNOC_H h po północy UTC (zbieracz zapisuje pierwszą z doby —
    po awarii mogła być później)."""
    out = {}
    for g, rows in (hist.items() if isinstance(hist, dict) else ()):
        for r in rows if isinstance(rows, list) else ():
            if not (isinstance(r, list) and len(r) >= 5 and _dzien(r[0]) and isinstance(r[1], str) and r[1][:10] == r[0]):
                continue
            try:
                if int(r[1][11:13]) >= WH_POLNOC_H:
                    continue
            except ValueError:
                continue
            for a, i in (('ETH', 2), ('USDT', 3), ('USDC', 4)):
                if isinstance(r[i], (int, float)) and not isinstance(r[i], bool) and r[i] == r[i]:
                    out.setdefault(r[0], {})[(g, a)] = (float(r[i]), r[1], r[5] if len(r) > 5 else None)
    return out


def _wh_rozb_polnoc(H, d, row_d):
    """v249: pary dnia archiwum `d` z migawek o północy: zmiana salda między migawkami z d − 1 i d (cała doba d − 1; ta sama wersja listy portfeli)
    vs przelewy netto z wiersza archiwum d (suma pełnej doby d − 1) → {(giełda, aktywo): (zmiana, netto, |zmiana − netto|, WH_POLNOC_SP)};
    zmiana w jednostkach po kursie z wiersza archiwum (saldo USD / jednostki) — ruch kursu ETH nie jest przelewem."""
    if not _dzien(d):
        return {}
    A = H.get((dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat()) or {}
    B = H.get(d) or {}
    out = {}
    for k, row in row_d.items():
        if k not in A or k not in B or A[k][2] != B[k][2]:
            continue
        try:
            u, usd, net = float(row[3]), float(row[4]), float(row[7])
        except ValueError:
            continue
        if not u:
            continue
        delta = (B[k][0] - A[k][0]) * (usd / u)
        out[k] = (delta, net, abs(delta - net), WH_POLNOC_SP)
    return out


IXF_SERIE = (('GSPC', 'SP500', 'S&P 500'), ('IXIC', 'NASDAQCOM', 'Nasdaq Composite'), ('DJI', 'DJIA', 'Dow Jones'),
             ('N225', 'NIKKEI225', 'Nikkei 225'))   # v257: indeksy strony, które FRED podaje od ich wydawców (bez klucza)
IXF_DNI = 45       # v257: okno porównania — dni kalendarzowe wstecz od dziś
IXF_TOL = 0.02     # v257: % — różnica do tylu = zgodne (zaokrąglenia: dostawca strony podaje zamknięcia do 4 miejsc)
IXF_ZLE = 0.1      # v257: % — starsza sesja różna o więcej = ⚠️ (kolejne pobranie z zakładką 10 dni powinno ją już poprawić)


def ixf_porownanie(rows, F, od):
    """v257: seria strony [[dzień, zamknięcie], …] vs {dzień: zamknięcie} wydawcy od dnia `od` → {'n', 'zgodne', 'ost', 'ost_roz',
    'roznice': [(dzień, strona, wydawca, %)], 'bez_sesji': [dni strony, których wydawca nie ma, choć ma późniejsze], 'luki': [dni wydawcy
    bez wiersza strony, do ostatniego dnia strony]} albo None. Ostatni dzień strony osobno (ost_roz) — może być zamknięciem wstępnym."""
    S = {r[0]: r[1] for r in (rows or []) if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str) and r[0] >= od
         and isinstance(r[1], (int, float)) and not isinstance(r[1], bool) and 0 < r[1] < float('inf')}
    F = {d: v for d, v in (F or {}).items() if d >= od and isinstance(v, (int, float)) and 0 < v < float('inf')}
    if not S or not F:
        return None
    ost, fmax = max(S), max(F)
    out = {'n': 0, 'zgodne': 0, 'ost': ost, 'ost_roz': None, 'roznice': [], 'bez_sesji': [], 'luki': []}
    for d in sorted(S):
        if d in F:
            out['n'] += 1
            p = round((S[d] / F[d] - 1) * 100, 3)
            if abs(p) <= IXF_TOL:
                out['zgodne'] += 1
            elif d == ost:
                out['ost_roz'] = (d, S[d], F[d], p)
            else:
                out['roznice'].append((d, S[d], F[d], p))
        elif d < fmax:
            out['bez_sesji'].append(d)
    out['luki'] = [d for d in sorted(F) if d <= ost and d not in S]
    return out


def ixf_sprawdz(ix, wyd=None, now=None):
    """v257/v259: 4 indeksy strony vs wydawcy → {'od', 'wyniki': [{'s', 'nazwa', 'at', 'wyd_at', … ixf_porownanie albo 'brak'}]}. v259: serie
    wydawców z pliku indeksów (część 'wyd' — zbieracz pobiera je z FRED z kluczem co 3 h); v257 pytała FRED bez klucza, ale z maszyn GitHub
    FRED nie odpowiadał w 30 s (06.10 18:09 UTC — wszystkie 4 „brak porównania”). Ten blok kontroli działa bez sieci."""
    now = now or NOW
    od = (now.date() - dt.timedelta(days=IXF_DNI)).isoformat()
    W = wyd.get('d') if isinstance(wyd, dict) and isinstance(wyd.get('d'), dict) else {}
    WA = wyd.get('at_s') if isinstance(wyd, dict) and isinstance(wyd.get('at_s'), dict) else {}
    wyn = []
    for s, fid, nazwa in IXF_SERIE:
        rec = ix.get(s) if isinstance(ix, dict) and isinstance(ix.get(s), dict) else {}
        w = {'s': s, 'nazwa': nazwa, 'at': rec.get('at') if isinstance(rec.get('at'), str) else None,
             'wyd_at': WA.get(s) if isinstance(WA.get(s), str) else None}
        F = {r[0]: r[1] for r in (W.get(s) if isinstance(W.get(s), list) else []) if isinstance(r, list) and len(r) == 2 and isinstance(r[0], str)
             and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)}
        if not F:
            w['brak'] = f'zbieracz nie podał serii wydawcy {fid}'
        else:
            c = ixf_porownanie(rec.get('d') if isinstance(rec.get('d'), list) else [], F, od)
            if c is None:
                w['brak'] = 'seria strony albo wydawcy bez sesji w oknie porównania'
            else:
                w.update(c)
        wyn.append(w)
    return {'od': od, 'wyniki': wyn}

def _ixf_n(x):
    return f'{x:,.2f}'.replace(',', ' ').replace('.', ',')


def _ixf_p(p):
    return f'{p:+.2f}%'.replace('.', ',')


def ixf_uwagi(o):
    """v257: uwaga tylko dla starszej sesji różnej o więcej niż IXF_ZLE (ponowne pobranie jej nie poprawiło); reszta — informacja w wierszu."""
    u = []
    for w in (o or {}).get('wyniki') or []:
        zle = [r for r in w.get('roznice') or [] if abs(r[3]) > IXF_ZLE]
        if zle:
            u.append(f"indeks {w['nazwa']}: zamknięcie na stronie różni się od wydawcy ponad {IXF_ZLE:g}% także po ponownym pobraniu: ".replace('.', ',')
                     + ', '.join(f'{d}: {_ixf_n(a)} vs {_ixf_n(b)} ({_ixf_p(p)})' for d, a, b, p in zle[:3])
                     + ' — sprawdzić dane dostawcy indeksów')
    return u


def ixf_wiersz(o):
    """v257: wiersz raportu „Indeksy vs wydawcy”: zgodne sesje, różne (⚠️ ponad IXF_ZLE, inaczej ℹ️), ostatnia sesja różna (ℹ️, z godziną
    pobrania), sesje bez odpowiednika (ℹ️); brak porównania — ℹ️. Brak wyniku — None (wiersza nie ma)."""
    if not isinstance(o, dict):
        return None
    if o.get('brak'):
        return f'- Indeksy vs wydawcy (FRED): brak porównania ({o["brak"]}) ℹ️.'
    cz, zle = [], False
    for w in o.get('wyniki') or []:
        if w.get('brak'):
            cz.append(f"{w['nazwa']} — brak porównania ({w['brak']}) ℹ️")
            continue
        x = []
        if w.get('roznice'):
            z = any(abs(r[3]) > IXF_ZLE for r in w['roznice'])
            zle = zle or z
            x.append('różne: ' + ', '.join(f'{d} {_ixf_p(p)}' for d, a, b, p in w['roznice'][:5]) + (' ⚠️' if z else ' ℹ️'))
        if w.get('ost_roz'):
            d, a, b, p = w['ost_roz']
            kiedy = str(w.get('at') or '')[:16].replace('T', ' ')
            x.append(f'ostatnia sesja {d}: {_ixf_n(a)} vs {_ixf_n(b)} ({_ixf_p(p)})' + (f' — pobrana {kiedy} UTC' if kiedy else '')
                     + ', możliwe zamknięcie wstępne; następne pobranie ją nadpisze ℹ️')
        if w.get('bez_sesji'):
            x.append('sesje, których wydawca nie ma: ' + ', '.join(w['bez_sesji'][:5]) + ' ℹ️')
        if w.get('luki'):
            x.append('sesje wydawcy bez wiersza na stronie: ' + ', '.join(w['luki'][:5]) + ' ℹ️')
        cz.append(f"{w['nazwa']} — zgodne {w['zgodne']} z {w['n']} sesji" + ('; ' + '; '.join(x) if x else ' ✅'))
    return f'- Indeksy vs wydawcy (FRED, {IXF_DNI} dni): ' + ' · '.join(cz) + '.'


IX_OPOZ_DNI = 1      # v254/v258: seria indeksu starsza od dnia odniesienia o więcej DNI ROBOCZYCH (pn–pt) = „opóźniona” (informacja: rotacja, święto)
IX_STARE_DNI = 9     # v258: … o więcej niż tyle dni roboczych = ⚠️ (seria się zacięła). Przegląd v254: 10 dni kalendarzowych to mniej niż prawdziwe
                     # przerwy giełd — Szanghaj, Święto Wiosny 2026: bez sesji 13.02–24.02 (7 dni roboczych); Indonezja 2025: 8; z jednym nieudanym
                     # pobraniem w dniu otwarcia — 9
IX_WSZYSTKIE_DNI = 3   # v258: najnowsza sesja wszystkich serii starsza od dziś o więcej dni roboczych = ⚠️ (dostawca stoi, choć plik jest świeży)


def _dni_rob(a, b):
    """v258: dni robocze (pn–pt) po dniu a do dnia b włącznie (daty); b ≤ a → 0."""
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        n += d.weekday() < 5
    return n


def indeksy_ocena(ix, now=None):
    """v254/v258: świeżość każdej serii indeksów (indeksy.json → ix: {symbol: {'d': [[dzień, zamknięcie], …], 'bad_at'?}}) → {'n', 'swieze',
    'najnowsza', 'opoznione': [(symbol, dzień, dni robocze)], 'stare': [...], 'puste': [(symbol, od)], 'przyszle': [(symbol, dzień)],
    'wszystkie': dni robocze od najnowszej sesji do dziś} albo None. v258 (przegląd): dzień odniesienia = najnowsza sesja wszystkich serii, ale
    nie później niż dziś (UTC) — sesja z przyszłości (błąd dostawcy) osobno i pominięta w ocenie; odstępy w dniach roboczych (pn–pt)."""
    if not isinstance(ix, dict) or not ix:
        return None
    dzis = (now or NOW).date()
    ost, puste, przyszle = {}, [], []
    for s, v in sorted(ix.items()):
        d = v.get('d') if isinstance(v, dict) else None
        dd = [r[0] for r in d if isinstance(r, list) and len(r) >= 2 and _dzien(r[0]) and isinstance(r[1], (int, float)) and not isinstance(r[1], bool)
              and r[1] == r[1]] if isinstance(d, list) else []
        fut = [x for x in dd if dt.date.fromisoformat(x) > dzis]
        if fut:
            przyszle.append((s, max(fut)))
            dd = [x for x in dd if x not in fut]
        if dd:
            ost[s] = max(dd)
        elif not fut:
            puste.append((s, str(v.get('bad_at') or '')[:10] if isinstance(v, dict) else ''))
    out = {'n': len(ix), 'swieze': 0, 'najnowsza': None, 'opoznione': [], 'stare': [], 'puste': puste, 'przyszle': przyszle, 'wszystkie': None}
    if not ost:
        return out
    najn = max(ost.values())
    out['najnowsza'] = najn
    out['wszystkie'] = _dni_rob(dt.date.fromisoformat(najn), dzis)
    for s, x in sorted(ost.items()):
        n = _dni_rob(dt.date.fromisoformat(x), dt.date.fromisoformat(najn))
        if n > IX_STARE_DNI:
            out['stare'].append((s, x, n))
        elif n > IX_OPOZ_DNI:
            out['opoznione'].append((s, x, n))
        else:
            out['swieze'] += 1
    return out


def indeksy_uwagi(o):
    """v254/v258: uwagi — seria zacięta, sesja z przyszłości, dostawca stoi (wszystkie serie bez nowych sesji)."""
    o = o or {}
    u = [f'indeksy giełdowe: {s} bez nowych sesji od {x} ({n} dni roboczych wobec najnowszej sesji innych indeksów) — sprawdzić pobieranie tego indeksu'
         for s, x, n in o.get('stare') or []]
    u += [f'indeksy giełdowe: {s} ma sesję z datą z przyszłości ({x}) — błąd danych dostawcy (strona może pokazywać ją jako ostatnią); w ocenie świeżości pominięta'
          for s, x in o.get('przyszle') or []]
    if (o.get('wszystkie') or 0) > IX_WSZYSTKIE_DNI:
        u.append(f'indeksy giełdowe: najnowsza sesja wszystkich serii to {o["najnowsza"]} — {o["wszystkie"]} dni roboczych bez nowych sesji; '
                 'dostawca oddaje stare dane albo pobieranie stoi')
    return u


def indeksy_wiersz(o):
    """v254/v258: wiersz raportu „Indeksy giełdowe” — świeże, opóźnione (ℹ️), zacięte (⚠️), z przyszłości (⚠️), wszystkie stare (⚠️), bez danych (ℹ️)."""
    if not isinstance(o, dict):
        return '- Indeksy giełdowe: plik bez serii indeksów ℹ️.'
    cz = [f'świeże {o["swieze"]} z {o["n"]}' + (f' (do {o["najnowsza"]})' if o.get('najnowsza') else '')]
    zle = (o.get('wszystkie') or 0) > IX_WSZYSTKIE_DNI
    if zle:
        cz.append(f'najnowsza sesja {o["wszystkie"]} dni roboczych temu ⚠️')
    if o.get('przyszle'):
        cz.append('sesja z datą z przyszłości: ' + ', '.join(f'{s} ({x})' for s, x in o['przyszle']) + ' ⚠️')
    if o.get('stare'):
        cz.append('bez nowych sesji ponad ' + f'{IX_STARE_DNI} dni roboczych: ' + ', '.join(f'{s} (od {x})' for s, x, n in o['stare']) + ' ⚠️')
    if o.get('opoznione'):
        cz.append('opóźnione: ' + ', '.join(f'{s} ({x})' for s, x, n in o['opoznione']) + ' ℹ️')
    if o.get('puste'):
        cz.append('bez danych (dostawca nie podaje): ' + ', '.join(s for s, od in o['puste']) + ' ℹ️')
    return '- Indeksy giełdowe: ' + '; '.join(cz) + ('.' if (zle or o.get('przyszle') or o.get('stare') or o.get('opoznione') or o.get('puste')) else ' ✅.')


def wieloryby_ocena(path, zmiany=None, hist=None):
    """v174: zgodność sald i przepływów wielorybów na tle historii. Przepływy to tylko przelewy ≥ 1 mln USD w oknie 24 h, a migawki sald dzieli
    tyle, ile minęło między zapisami archiwum (05.10: od 7,7 do 28 h) — rozbieżność jest normalna. Uwaga tylko, gdy migawki pary dzieli ok. doba
    (WH_DOBA_BLOKI) i jej rozbieżność przekracza zwykły próg (WH_PROG %, WH_MIN_USD) ORAZ WH_RAZY × medianę jej rozbieżności z co najmniej
    WH_HIST_MIN wcześniejszych porównywalnych dni. v175: odstęp liczony dla KAŻDEJ pary z jej własnych bloków — para z innym odstępem pominięta
    (pole pominiete), reszta porównana; żadnej pary o dobę = bez porównania (powód w 'pomin'). Mniej niż dwa dni archiwum = None.
    → {'dzien', 'poprzedni', 'poprzedni_pokaz', 'porownane', 'pominiete', 'odstep_h' (mediana par), 'pomin', 'zle': [(giełda, aktywo, zmiana,
    netto, rozb., mediana)], 'bez_historii', 'lista', 'polnoc'}. v230: zmiany = {giełda: dzień zmiany listy portfeli} — pary tej giełdy
    obejmujące ten dzień (także jako dzień poprzedni: migawka archiwum mogła być przed zmianą) pominięte — nowe portfele to skok salda bez
    przelewów. v249: hist = pole hist pliku wielorybów — para z migawek o północy UTC (zgrana z dobą przelewów) zastępuje dziś parę z migawek
    archiwum ('polnoc' — ile dziś takich par). v250: historia (norma pary) liczona osobno dla par z północy i z archiwum — para dnia oceniana
    normą swojego rodzaju (rozbieżności par z archiwum są zwykle większe); 'poprzedni_pokaz' — przy samych parach z północy dzień d − 1."""
    by = _wh_csv(path)
    if not by:
        return None
    days = sorted(by)
    if len(days) < 2:
        return None
    d, p = days[-1], days[-2]
    doba = lambda sp: sp is not None and WH_DOBA_BLOKI[0] <= sp <= WH_DOBA_BLOKI[1]  # noqa: E731
    Hn = _wh_polnoc(hist) if hist else {}

    def obie(a, b):   # v250: pary z archiwum ('a') i z migawek o północy ('p') osobno
        return ({k: v + ('a',) for k, v in _wh_rozb(by[a], by[b]).items()},
                {k: v + ('p',) for k, v in _wh_rozb_polnoc(Hn, b, by[b]).items()})
    A, Pn = obie(p, d)
    dzis = dict(A)
    dzis.update(Pn)   # v249: para z migawek o północy zastępuje dziś parę z migawek archiwum (te robione są o różnych porach)
    zm = lambda g, a, b: isinstance(zmiany, dict) and isinstance(zmiany.get(g), str) and a <= zmiany[g] <= b  # noqa: E731 — v230
    lista = sorted({k[0] for k in dzis if zm(k[0], p, d)})
    dzis = {k: v for k, v in dzis.items() if not zm(k[0], p, d)}
    S = sorted(x[3] for x in dzis.values() if x[3] is not None)
    dm1 = (dt.date.fromisoformat(d) - dt.timedelta(days=1)).isoformat() if _dzien(d) else p
    out = {'dzien': d, 'poprzedni': p, 'porownane': sum(1 for x in dzis.values() if doba(x[3])),
           'pominiete': sum(1 for x in dzis.values() if not doba(x[3])),
           'odstep_h': round(S[len(S) // 2] * 12 / 3600, 1) if S else None, 'pomin': None, 'zle': [], 'bez_historii': 0, 'lista': lista,
           'polnoc': sum(1 for x in dzis.values() if x[4] == 'p')}
    out['poprzedni_pokaz'] = dm1 if out['polnoc'] and out['polnoc'] == out['porownane'] else p   # v250: podpis zgodny z porównanymi migawkami
    if not out['porownane']:   # v253: powód z faktycznych danych (nie zgadywany)
        pw = []
        if lista:   # v258 (przegląd): pary giełd z nową listą portfeli odpadły — powód zawsze wymieniony (wpadało w „brak numeru bloku”)
            pw.append('nowa lista portfeli — bez porównania: ' + ', '.join(lista))
        reszta = [r for k, r in by[d].items() if k[0] not in lista]   # v258: giełdy bez nowej listy
        if reszta and all(len(r) > 7 and not str(r[7]).strip() for r in reszta):
            pw.append('archiwum bez sum przelewów doby (doba niepełna albo sum brak)')
        elif out['odstep_h'] is not None:
            pw.append(f"odstęp migawek {out['odstep_h']:.1f} h — porównanie z przepływami 24 h tylko przy ok. dobie")
        elif dzis:   # v258: pary są, ale żadna nie ma numerów bloków obu migawek
            pw.append('brak numeru bloku migawki — bez porównania')
        elif reszta:   # v258: żadnej pary giełda/aktywo z liczbami w obu dniach
            pw.append(f'brak wspólnych par giełda/aktywo z liczbami w dniach {p} i {d}')
        if hist and not out['polnoc']:   # v250/v253: migawki o północy — dzień i giełdy, których migawki brak albo jest późna; inna wersja listy
            A, B = Hn.get(dm1) or {}, Hn.get(d) or {}
            ga = sorted({k[0] for k in by[d] if k not in A})
            gb = sorted({k[0] for k in by[d] if k not in B})
            gw = sorted({k[0] for k in by[d] if k in A and k in B and A[k][2] != B[k][2]})
            cz = [f'{x} — {", ".join(g)}' for x, g in ((dm1, ga), (d, gb)) if g]
            if cz:
                pw.append(f'migawki o północy brak albo później niż {WH_POLNOC_H} h po północy UTC: ' + '; '.join(cz))
            if gw:
                pw.append('inna wersja listy portfeli w migawkach o północy: ' + ', '.join(gw))
        out['pomin'] = '; '.join(pw)
        return out
    norma = {}
    for a, b in zip(days[:-2], days[1:-1]):
        for X in obie(a, b):
            for k, (_dl, _n, r, sp, rd) in X.items():
                if doba(sp) and not zm(k[0], a, b):
                    norma.setdefault((k, rd), []).append(r)
    for k, (delta, net, roz, sp, rd) in sorted(dzis.items()):
        if not doba(sp) or not (roz > WH_MIN_USD and roz > WH_PROG / 100 * max(abs(delta), abs(net), WH_MIN_USD)):
            continue
        h = sorted(norma.get((k, rd), []))   # v250: norma z par tego samego rodzaju
        if len(h) < WH_HIST_MIN:
            out['bez_historii'] += 1
            continue
        med = h[len(h) // 2] if len(h) % 2 else (h[len(h) // 2 - 1] + h[len(h) // 2]) / 2
        if roz > WH_RAZY * med:
            out['zle'].append((k[0], k[1], delta, net, roz, med))
    return out


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


def najdluzsze_udane(runs, now, n=3):
    """v194: identyfikatory n najdłuższych udanych przebiegów „Strona i dane” z ostatnich 24 h (od startu do ostatniej zmiany), malejąco."""
    od, out = now - dt.timedelta(hours=24), []
    for r in runs if isinstance(runs, list) else []:
        if not (isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and r.get('status') == 'completed' and r.get('conclusion') == 'success'):
            continue
        try:
            a = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
            b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
        except Exception:
            continue
        a, b = (x if x.tzinfo else x.replace(tzinfo=dt.timezone.utc) for x in (a, b))
        if a >= od and b >= a:
            out.append(((b - a).total_seconds(), r.get('id')))
    return [i for _, i in sorted(out, key=lambda x: -x[0])[:n]]


BUDOWA_BUDZET_S = 90   # v205: s — odczyt czasów zadania budowy (API zadań) najwyżej tyle; limit całego zadania kontroli 12 min


def przebieg_min(r):
    """v205: minuty od startu do ostatniej zmiany przebiegu; zły zapis = None."""
    try:
        a = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
        b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
        return (b - a).total_seconds() / 60
    except Exception:
        return None


def budowa_kandydaci(runs, now, n=3, prog_min=20, cap=40):   # v203: cap 40 (było 10) — każdy udany > 20 min
    """v199: przebiegi do odczytu czasu zadania budowy: n najdłuższych udanych z 24 h i każdy udany dłuższy niż prog_min min (razem najwyżej cap)
    — przy czekaniu w kolejce najdłuższa budowa nie musi być wśród 3 najdłuższych przebiegów (przegląd 06.10)."""
    ids = najdluzsze_udane(runs, now, len(runs) if isinstance(runs, list) else 0)
    dl = {}
    for r in runs if isinstance(runs, list) else []:
        try:
            a = dt.datetime.fromisoformat(str(r.get('run_started_at')).replace('Z', '+00:00'))
            b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
            dl[r.get('id')] = (b - a).total_seconds() / 60
        except Exception:
            continue
    return [i for k, i in enumerate(ids) if k < n or dl.get(i, 0) > prog_min][:cap]


def zadanie_min(jobs, nazwa):
    """v194: minuty zadania o tej nazwie (od startu zadania do końca, bez czekania w kolejce); brak albo zły czas = None."""
    for j in jobs if isinstance(jobs, list) else []:
        if isinstance(j, dict) and j.get('name') == nazwa:
            try:
                a = dt.datetime.fromisoformat(str(j.get('started_at')).replace('Z', '+00:00'))
                b = dt.datetime.fromisoformat(str(j.get('completed_at')).replace('Z', '+00:00'))
                m = (b - a).total_seconds() / 60
            except Exception:
                return None
            return m if m >= 0 else None
    return None


def przebiegi_ocena(runs, now, kroki=None, pend=None):
    """v124.1: przebiegi automatu („Strona i dane”) z ostatnich 24 h → (actions, bledy, uwagi).
    BŁĄD tylko, gdy automat NADAL nie działa: dwa ostatnie zakończone przebiegi nieudane albo ≥ 3 porażki w 24 h i ostatni zakończony
    też nieudany. Jedna świeża porażka = uwaga („kolejny przebieg za ok. 20 min”). Porażki już naprawione (po ostatniej same udane) =
    uwaga z godzinami, krokiem i liczbą udanych przebiegów od ostatniej porażki. Przebiegi w toku i anulowane nie liczą się do serii.
    kroki: {id przebiegu: opis kroku} dla porażek (z API zadań; może brakować — wtedy sama godzina).
    v235: pend — {id przebiegu: oczekujące wdrożenia} dla przebiegów „waiting”: czeka na osobę (recenzent) = uwaga „zatwierdź”, nie błąd."""
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
    def trwanie(r):   # v190: minuty od startu do końca przebiegu (z czekaniem na maszyny); zły czas = None
        try:
            b = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
            b = b if b.tzinfo else b.replace(tzinfo=dt.timezone.utc)
            return (b - czas(r)).total_seconds() / 60
        except Exception:
            return None
    trw = [x for x in (trwanie(r) for r in ost if r.get('status') == 'completed' and r.get('conclusion') == 'success') if x is not None and x >= 0]
    A = {'przebiegi_24h': len(ost), 'wg_wyniku': z, 'ostatni': ost[0].get('run_started_at') if ost else None,
         'najdluzszy_min': round(max(trw), 1) if trw else None,   # v190: najdłuższy udany przebieg w 24 h
         'ostatnia_porazka': por[0].get('run_started_at') if por else None, 'porazki_z_rzedu': z_rzedu, 'udane_po_porazce': udane_po,
         'porazki': [{'at': r.get('run_started_at'), 'krok': kroki.get(r.get('id'))} for r in por[:10]]}
    bledy, uwagi = [], []
    if por:
        c = [czas_pl(p['at']) for p in A['porazki'][:5]]
        lista = ', '.join((x[:5] + ' ' + x[-5:] if x != '—' else x) + (f' ({p["krok"]})' if p.get('krok') else '') for x, p in zip(c, A['porazki']))
        lista += f' i {len(por) - 5} wcześniejsze' if len(por) > 5 else ''
        if z_rzedu >= 2 or (len(por) >= 3 and z_rzedu >= 1):
            pages = all('GitHub Pages' in str(kroki.get(r.get('id')) or '') for r in zak[:min(z_rzedu, 5)])   # v219/v221: 5 najnowszych porażek serii (tylko one mają opis kroku)
            bledy.append(f'automat nie działa{" (publikacja GitHub Pages)" if pages else ""}: {pl_przebiegi(len(por))} w 24 h, ostatnie {z_rzedu} z rzędu — strona nie odświeża danych ({lista})')
        elif z_rzedu == 1:
            uwagi.append(f'ostatni przebieg automatu nieudany ({lista}) — kolejny za ok. 10 min; dwa nieudane z rzędu = błąd')
        else:
            uwagi.append(f'{pl_przebiegi(len(por))} automatu w 24 h — już naprawione: od ostatniej porażki {pl_udane(udane_po)} z rzędu ({lista})')
    if len(ost) < 20:
        uwagi.append(f'tylko {len(ost)} przebiegów w 24 h (harmonogram co 10 min ≈ 144; GitHub bywa opóźniony)')
    # v232: przebieg w stanie waiting (zadanie „opublikuj” czeka na środowisko) trzyma grupę „pages” — żadna publikacja nie przejdzie;
    # wszystkie przebiegi z listy (także starsze niż doba), czas czekania od updated_at; zła data = bez zgadywania
    def czeka_min(r):
        try:
            t = dt.datetime.fromisoformat(str(r.get('updated_at')).replace('Z', '+00:00'))
            t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        except Exception:
            return None
        return int((now - t).total_seconds() // 60)
    cz = [(czeka_min(r), r) for r in runs if isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and r.get('status') == 'waiting']
    cz = sorted(((m, r) for m, r in cz if m is not None and m >= WAIT_UWAGA_MIN), key=lambda x: -x[0])
    if cz:
        m, r = cz[0]
        kiedy = czas_pl(r.get('run_started_at'))
        pd_ = (pend or {}).get(r.get('id'))
        if isinstance(pd_, list) and any(isinstance(p, dict) and p.get('reviewers') for p in pd_):   # v235: wymóg zatwierdzenia przez osobę
            uwagi.append(f'publikacja czeka od {m} min na zatwierdzenie przez osobę (przebieg z {kiedy}; wymóg w ustawieniach środowiska '
                         'github-pages) — zatwierdź w Actions („Review deployments”) albo usuń ten wymóg; zegar zapasowy takiego przebiegu nie anuluje')
        elif m >= WAIT_BLAD_MIN:
            bledy.append(f'publikacja zawieszona: przebieg z {kiedy} czeka od {m // 60} godz. {m % 60} min na wdrożenie strony (stan „waiting”), '
                         'a zegar zapasowy go nie anulował — strona bez nowych danych')
        else:
            uwagi.append(f'publikacja czeka od {m} min (przebieg z {kiedy}, stan „waiting”) — zegar zapasowy anuluje taki przebieg sam '
                         f'(po 15 min, przy najbliższym czuwaniu), jeśli środowisko publikacji nie wymaga zatwierdzenia; od {WAIT_BLAD_MIN // 60} godz. to błąd')
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


# ---------------------------------------------------------------- v162: dzienniki sygnałów TRENDÓW — ostatni dzień z wynikiem ----------------------------------------------------------------
# Plik dziennika jest przepisywany w każdym przebiegu (wiek pliku zawsze mały), więc pętla wieku plików nie widzi, że wyniki przestały dochodzić.
# Tu: najnowszy dzień (sesja) z liczbą w polu wyniku (wiersz [dzień, symbol, N, stan, głosy, czas, y]). Krypto: wynik doby D dochodzi ok. D+3
# 00:30 UTC (pliki dzienne archiwum cen; wynik potrzebuje otwarcia 06:00 doby D+2) — norma 2–3 dni od końca doby, próg 4 dni kalendarzowe.
# Świat: wynik sesji dochodzi tego samego wieczoru — próg 48 h roboczych (święto w USA się mieści). Najwyżej ⚠️, nigdy ❌ ani BŁĄD; przed
# startem dziennika (since) albo w pierwszych dniach bez wyniku — „—”; brak pliku albo plik bez wierszy — None (brak pliku zgłasza pętla wieku plików).
DZ_SPEC = (('krypto-dziennik', 'TRENDY krypto — ostatni dzień z wynikiem sygnałów', 'w', 4 * 24 * 60),
           ('swiat-dziennik', 'TRENDY świat — ostatnia sesja z wynikiem sygnałów', 'd', 48 * 60))
_DZ_DZIEN = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def dziennik_swiezosc(j, plik, now=None):
    """v162: wiersz świeżości dziennika sygnałów (data/<plik>.json) w kształcie wierszy swiezosc(): (etykieta, status, wiek min, dzień, uwaga)
    albo None (inny plik, brak pliku, plik bez listy wierszy). Wynik = liczba skończona w polu y (bool, None, NaN — nie)."""
    spec = next((x for x in DZ_SPEC if x[0] == plik), None)
    if spec is None or not isinstance(j, dict) or not isinstance(j.get('rows'), list):
        return None
    _p, lab, kat, prog = spec
    now = now or NOW
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and v not in (float('inf'), float('-inf'))  # noqa: E731
    dni = [r[0] for r in j['rows'] if isinstance(r, list) and len(r) == 7 and isinstance(r[0], str) and _DZ_DZIEN.match(r[0]) and num(r[6])]
    since = j.get('since') if isinstance(j.get('since'), str) and _DZ_DZIEN.match(j['since']) else None
    if not dni:
        if since and now.date().isoformat() <= since:
            return (lab, '—', None, None, f'dziennik rusza {since} — pierwsze wyniki po pierwszym sprawdzeniu')
        w0 = wiek_danych(since, 'day', kat, now) if since else None
        if w0 is not None and w0 <= prog:
            return (lab, '—', None, None, f'dziennik od {since} — czekamy na pierwsze wyniki')
        return (lab, '⚠️', w0, None, 'brak dnia z wynikiem w dzienniku' + (f' (od {since})' if since else '') + ' (tylko uwaga)')
    d = max(dni)
    w = wiek_danych(d, 'day', kat, now)
    if w is None:
        return (lab, '?', None, d, 'zły zapis dnia')
    if w <= prog:
        return (lab, '✅', w, d, '')
    return (lab, '⚠️', w, d, f'próg {fmt_wiek(prog)} — wyniki sygnałów przestały dochodzić (tylko uwaga)')


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


# ---------------------------------------------------------------- v134: fundusze USA (data/ici.json) ----------------------------------------------------------------
# Świeżość każdej części osobnym wierszem tabeli (lista SWIEZOSC bez zmian — test liczy jej wiersze) i tożsamości sum ostatniego tygodnia
# w opublikowanym pliku. Wszystko najwyżej ⚠️ (uwaga), nigdy ❌ ani BŁĄD: tygodniowe dane wydawcy spóźniają się przez święta w USA, a zbieracz
# i tak odrzuca pliki z niezgodnymi sumami — niezgodność w pliku strony to sygnał do sprawdzenia, nie awaria strony.
ICI_ETYKIETA = {'lt': 'Fundusze USA: napływy (tydzień do środy, publ. w środę)'}
ICI_KROTKO = {'lt': 'napływy'}
# progi wieku danych (od końca dnia tygodnia danych): napływy w dniu publikacji mają już 7 dni, tuż przed następną 14 dni + ok. 14 h;
# 16 dni = 1,5 doby zapasu na przesunięcie publikacji (święto w USA) i godzinne okno zbieracza
ICI_PROG = {'lt': 16 * 24 * 60}
ICI_TOL = (3, 5)     # mln USD: tolerancja zaokrągleń (składniki grupy, suma grup) — jak w zbieraczu
ICI_SUMY = {'lt': (('eq', ('dom', 'wld'), 0), ('bd', ('tax', 'muni'), 0), ('total', ('eq', 'hyb', 'bd', 'com'), 1))}
ICI_OPIS = {'lt': 'akcje = USA + spoza USA, obligacje = zwykłe + municypalne, razem = suma grup'}
# v135: rynek pieniężny (część „mm” pliku ici.json; publikacja w czwartek za tydzień do środy): w dniu publikacji dane mają 1 dzień, tuż przed
# następną — 7 dni i ok. 20 h; próg 10 dni = ok. 2 doby zapasu na przesunięcie publikacji (czwartki świąteczne w USA: Święto Dziękczynienia,
# Wigilia, Sylwester) i godzinne okno zbieracza. Najwyżej ⚠️, nigdy ❌ — jak napływy.
ICI_ETYKIETA['mm'] = 'Fundusze USA: rynek pieniężny (tydzień do środy, publ. w czwartek)'
ICI_KROTKO['mm'] = 'rynek pieniężny'
ICI_PROG['mm'] = 10 * 24 * 60
ICI_SUMY['mm'] = (('tot', ('gov', 'prime', 'te'), 0), ('tot', ('inst', 'ret'), 0), ('inst', ('gov_i', 'prime_i', 'te_i'), 0), ('ret', ('gov_r', 'prime_r', 'te_r'), 0))
ICI_OPIS['mm'] = 'razem = rządowe + prime + zwolnione z podatku = instytucjonalne + detaliczne (także w każdej grupie)'


def ici_swiezosc(j, now=None):
    """Wiersze świeżości części pliku ici.json w kształcie wierszy swiezosc(): (etykieta, status, wiek min, tydzień, uwaga). Najwyżej ⚠️
    (próg ICI_PROG), nigdy ❌; brak pliku = brak wierszy (brak pliku zgłasza pętla wieku plików); brak tygodnia części = „?”."""
    if not isinstance(j, dict):
        return []
    rows = []
    for k, label in ICI_ETYKIETA.items():
        P = j.get(k) if isinstance(j.get(k), dict) else {}
        w = P.get('week')
        if not (isinstance(w, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', w)):
            rows.append((label, '?', None, None, 'brak tygodnia w pliku')); continue
        wiek, prog = wiek_danych(w, 'day', 'w', now), ICI_PROG[k]
        st = '?' if wiek is None else ('⚠️' if wiek > prog else '✅')
        note = '' if st == '✅' else (f'próg {fmt_wiek(prog)} (tydzień danych + publikacja + święta w USA) — najwyżej uwaga' if st == '⚠️' else 'zła data tygodnia')
        rows.append((label, st, wiek, w, note))
    return rows


def ici_sumy(j):
    """Tożsamości sum w ostatnim tygodniu każdej części (ten sam wzór co zbieracz) i zgodność sumy 4 tygodni z wierszami pliku.
    → {część: {'tydzien', 'status' ✅/⚠️/?, 'opis'}}; brak liczby nie jest niezgodnością (sprawdzamy tylko pary z liczbami)."""
    out = {}
    for k, reguly in ICI_SUMY.items():
        P = j.get(k) if isinstance(j, dict) and isinstance(j.get(k), dict) else None
        cols, w = (P or {}).get('cols'), (P or {}).get('w')
        if not (isinstance(cols, list) and isinstance(w, list) and w and isinstance(w[-1], list) and len(w[-1]) == len(cols) + 1):
            out[k] = {'tydzien': None, 'status': '?', 'opis': 'brak wierszy w pliku'}; continue
        r = dict(zip(cols, w[-1][1:]))
        num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)   # noqa: E731
        zle = []
        for cel, czesci, t in reguly:
            if num(r.get(cel)) and all(num(r.get(c)) for c in czesci) and abs(r[cel] - sum(r[c] for c in czesci)) > ICI_TOL[t]:
                zle.append(f'{cel} {r[cel]:,.0f} ≠ {" + ".join(czesci)} {sum(r[c] for c in czesci):,.0f}'.replace(',', ' '))
        s4 = P.get('sum4')
        if isinstance(s4, dict) and isinstance(s4.get('v'), list) and len(w) >= 4 and s4.get('to') == w[-1][0]:
            for i, c in enumerate(cols):
                vals = [x[i + 1] if isinstance(x, list) and len(x) > i + 1 else None for x in w[-4:]]
                if i < len(s4['v']) and num(s4['v'][i]) and all(num(v) for v in vals) and abs(s4['v'][i] - sum(vals)) > 0.5:
                    zle.append(f'suma 4 tyg. {c}'); break
        out[k] = {'tydzien': w[-1][0], 'status': '⚠️' if zle else '✅', 'opis': '; '.join(zle) if zle else ICI_OPIS.get(k, 'sumy grup')}
    return out


def ici_kontrola(j, R):
    """Kontrola pliku ici.json bez sieci: tożsamości sum (⚠️ = uwaga) i informacja o dużej poprawce danych przez wydawcę (rev — bez koloru,
    tylko w raporcie). Brak pliku = None (raport bez linii)."""
    if not isinstance(j, dict):
        return None
    S = ici_sumy(j)
    for k, s in S.items():
        if s['status'] == '⚠️':
            R['uwagi'].append(f'{ICI_ETYKIETA.get(k, k)}: sumy w pliku strony niezgodne w tygodniu {s["tydzien"]} ({s["opis"]})')
    rev = []
    for k in ICI_ETYKIETA:
        r = (j.get(k) or {}).get('rev') if isinstance(j.get(k), dict) else None
        if isinstance(r, dict) and all(isinstance(r.get(x), (int, float)) for x in ('old', 'new')):
            rev.append(f'{ICI_KROTKO.get(k, k)}: wydawca poprawił tydzień {r.get("week")}: {r["old"]:,.0f} → {r["new"]:,.0f} mln USD'.replace(',', ' '))
    return {'sumy': S, 'rev': rev}


# ---------------------------------------------------------------- v137: Japonia — kto handluje akcjami na giełdzie (data/jpx.json) ----------------------------------------------------------------
JPX_ETYKIETA = 'Japonia: kto handluje akcjami na giełdzie (tydzień)'
JPX_ZWLOKA_H = 26          # h po spodziewanej publikacji następnego tygodnia (06:30 UTC) bez nowego tygodnia w pliku = ⚠️ (nigdy ❌ ani BŁĄD)
JPX_PARY = 26              # tyle ostatnich par tygodni porównujemy z danymi tygodniowymi MOF (plik instytucje trzyma 26 tygodni)
JPX_MIN_N = 8              # mniej par = „?” (za mało do oceny)
JPX_R_MIN = 0.6            # korelacja netto zagranicy (giełda vs MOF) poniżej progu = ⚠️; stan 27.09.2026: 0,909 z 26 par, kierunek 34 z 36 tygodni 2026
JPX_DUZE = 300.0           # mld JPY — w ostatnich 4 parach oba |netto| ≥ próg i przeciwne znaki = ⚠️
JPX_ZNAK = 50.0            # mld JPY — zgodność znaków liczona dla par, w których oba |netto| ≥ próg
JPX_KOREKTA_DNI = 7        # informacja o korekcie danych źródła z pliku jpx.json — uwaga w raporcie przez 7 dni
# dni bez sesji w Tokio poza weekendem — ta sama tabela co JPX_SWIETA w zbieraj_dane.py (test pilnuje zgodności); 31.12 i 1–3.01 — reguła.
# Po JPX_SWIETA_DO święta nie są znane: spodziewana publikacja wychodzi za wcześnie i świeżość może pokazać fałszywe ⚠️ (Złoty Tydzień: ok. 4 dni)
# — dlatego od 1 grudnia ostatniego roku tabeli raport ma uwagę „dopisać święta”.
JPX_SWIETA = frozenset((
    '2026-01-12', '2026-02-11', '2026-02-23', '2026-03-20', '2026-04-29', '2026-05-04', '2026-05-05', '2026-05-06', '2026-07-20',
    '2026-08-11', '2026-09-21', '2026-09-22', '2026-09-23', '2026-10-12', '2026-11-03', '2026-11-23',
    '2027-01-11', '2027-02-11', '2027-02-23', '2027-03-22', '2027-04-29', '2027-05-03', '2027-05-04', '2027-05-05', '2027-07-19',
    '2027-08-11', '2027-09-20', '2027-09-23', '2027-10-11', '2027-11-03', '2027-11-23',
    '2028-01-10', '2028-02-11', '2028-02-23', '2028-03-20', '2028-05-03', '2028-05-04', '2028-05-05', '2028-07-17', '2028-08-11',
    '2028-09-18', '2028-09-22', '2028-10-09', '2028-11-03', '2028-11-23',
    '2029-01-08', '2029-02-12', '2029-02-23', '2029-03-20', '2029-04-30', '2029-05-03', '2029-05-04', '2029-07-16', '2029-09-17',
    '2029-09-24', '2029-10-08', '2029-11-23',
    '2030-01-14', '2030-02-11', '2030-03-20', '2030-04-29', '2030-05-03', '2030-05-06', '2030-07-15', '2030-08-12', '2030-09-16',
    '2030-09-23', '2030-10-14', '2030-11-04'))
JPX_SWIETA_DO = 2030       # ostatni rok tabeli świąt


def jpx_swieta_uwaga(now=None):
    """Uwaga od 1 grudnia ostatniego roku tabeli świąt (i później): bez nowego roku kalendarz publikacji liczy święta jak dni sesji."""
    now = now or NOW
    if now.date() >= dt.date(JPX_SWIETA_DO, 12, 1):
        return (f'Japonia — tabela świąt giełdy w Tokio (JPX_SWIETA w zbieraj_dane.py i narzedzia/kontrola.py) kończy się na {JPX_SWIETA_DO} r. — '
                'dopisać kolejny rok, inaczej kalendarz publikacji liczy święta jak dni sesji (fałszywe ⚠️ świeżości)')
    return None


def jpx_bday(d):
    return d.weekday() < 5 and d.isoformat() not in JPX_SWIETA and not ((d.month == 12 and d.day == 31) or (d.month == 1 and d.day <= 3))


def jpx_release(day):
    """Publikacja danych tygodnia zawierającego `day`: 4. dzień roboczy od poniedziałku następnego tygodnia (jak w zbieraczu)."""
    d, n = day - dt.timedelta(days=day.weekday()) + dt.timedelta(days=7), 0
    for _ in range(40):
        if jpx_bday(d):
            n += 1
            if n == 4:
                return d
        d += dt.timedelta(days=1)
    return d


def jpx_next_release(asof):
    """Spodziewana publikacja następnego tygodnia z sesjami po tygodniu kończącym się `asof`."""
    m = asof - dt.timedelta(days=asof.weekday()) + dt.timedelta(days=7)
    for k in range(6):
        w0 = m + dt.timedelta(days=7 * k)
        if any(jpx_bday(w0 + dt.timedelta(days=i)) for i in range(5)):
            return jpx_release(w0)
    return jpx_release(m)


def jpx_swiezosc(j, now=None):
    """Wiersz świeżości (etykieta, status, wiek min, data, uwaga) wg kalendarza publikacji: ⚠️ dopiero JPX_ZWLOKA_H h po spodziewanej publikacji
    następnego tygodnia (4. dzień roboczy, ok. 06:30 UTC; święta w Japonii przesuwają termin); nigdy ❌. Brak pliku = ⚠️ „brak danych”
    (zbieracz bez poprzedniego pliku i bez danych nie zapisuje pliku — notatka w META, nie błąd)."""
    if not isinstance(j, dict):
        return (JPX_ETYKIETA, '⚠️', None, None, 'brak pliku data/jpx.json — brak danych, blok na stronie ukryty (tylko uwaga)')
    a = str(j.get('asof') or '')
    try:
        d = dt.date.fromisoformat(a[:10])
    except ValueError:
        return (JPX_ETYKIETA, '?', None, None, 'brak daty danych w pliku')
    now = now or NOW
    w = wiek_danych(a, 'day', 'w', now)
    nx = jpx_next_release(d)
    pub = dt.datetime(nx.year, nx.month, nx.day, 6, 30, tzinfo=dt.timezone.utc)
    if now <= pub + dt.timedelta(hours=JPX_ZWLOKA_H):
        return (JPX_ETYKIETA, '✅', w, a, '')
    late = int((now - pub).total_seconds() // 60)
    return (JPX_ETYKIETA, '⚠️', w, a, f'następny tydzień spodziewany {nx.isoformat()} ok. 06:30 UTC, brak od {fmt_wiek(late)} (kalendarz świąt w Japonii) — tylko uwaga')


def jpx_mof_porownanie(inst, jx):
    """Zagranica w japońskich akcjach: giełda (data/jpx.json, tylko handel na giełdzie, pon–pt) vs MOF (instytucje.json → mof, wszystkie akcje
    i fundusze, także poza giełdą, nd–sob). Para tygodni: sobota MOF = koniec tygodnia giełdy + (5 − dzień tygodnia). Netto w mld JPY: giełda
    (for_b − for_s) / 1000, MOF liabilities.equity_net / 10. Ostatnie ≤ JPX_PARY par: korelacja Pearsona, zgodność znaków (oba |netto| ≥ JPX_ZNAK),
    ostatnia para. ✅: n ≥ JPX_MIN_N, r ≥ JPX_R_MIN i w ostatnich 4 parach żadnej dużej (oba ≥ JPX_DUZE) z przeciwnym znakiem; „?”: n < JPX_MIN_N;
    inaczej ⚠️. Nigdy ❌ — to różne miary, a różnica to nie awaria strony."""
    Z = {'status': '?', 'n': 0, 'r': None, 'znak': None, 'ostatnia': None, 'opis': '', 'uwagi': []}
    if not isinstance(jx, dict):
        return None
    cols = jx.get('cols') if isinstance(jx.get('cols'), list) else []
    if not all(c in cols for c in ('to', 'for_s', 'for_b')):
        Z['opis'] = '? plik giełdy bez kolumn'; return Z
    i_t, i_s, i_b = cols.index('to'), cols.index('for_s'), cols.index('for_b')
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and v == v   # noqa: E731
    G = {}
    for r in jx.get('d') or []:
        try:
            t = dt.date.fromisoformat(str(r[i_t])[:10])
        except (TypeError, ValueError, IndexError):
            continue
        if num(r[i_s]) and num(r[i_b]):
            G[(t + dt.timedelta(days=5 - t.weekday())).isoformat()] = (str(r[i_t]), (r[i_b] - r[i_s]) / 1000)
    M = {}
    mof = ((inst or {}).get('mof') or {}).get('d') if isinstance(inst, dict) else None
    for w in mof or []:
        v = ((w or {}).get('liabilities') or {}).get('equity_net') if isinstance(w, dict) else None
        if isinstance(w, dict) and num(v) and isinstance(w.get('to'), str):
            M[w['to'][:10]] = v / 10
    pary = [(G[k][0], G[k][1], M[k]) for k in sorted(set(G) & set(M))][-JPX_PARY:]
    Z['n'] = n = len(pary)
    if pary:
        Z['ostatnia'] = {'tydzien': pary[-1][0], 'gielda_mld': round(pary[-1][1], 1), 'mof_mld': round(pary[-1][2], 1)}
    if n < JPX_MIN_N:
        Z['opis'] = f'? za mało wspólnych tygodni ({n}, potrzeba {JPX_MIN_N})'; return Z
    a, b = [p[1] for p in pary], [p[2] for p in pary]
    try:
        Z['r'] = round(statistics.correlation(a, b), 3)
    except (statistics.StatisticsError, ValueError, ZeroDivisionError):
        Z['r'] = None
    big = [(x, y) for _, x, y in pary if abs(x) >= JPX_ZNAK and abs(y) >= JPX_ZNAK]
    Z['znak'] = [sum(1 for x, y in big if x * y > 0), len(big)]
    zle = [p for p in pary[-4:] if abs(p[1]) >= JPX_DUZE and abs(p[2]) >= JPX_DUZE and p[1] * p[2] < 0]
    Z['status'] = '✅' if Z['r'] is not None and Z['r'] >= JPX_R_MIN and not zle else '⚠️'
    o = Z['ostatnia']
    Z['opis'] = (f'{Z["status"]} r = {Z["r"] if Z["r"] is not None else "—"} z {n} tygodni, ten sam kierunek w {Z["znak"][0]} z {Z["znak"][1]} '
                 f'(oba ≥ {JPX_ZNAK:g} mld JPY); ostatni tydzień {o["tydzien"]}: giełda {o["gielda_mld"]:+.1f} vs MOF {o["mof_mld"]:+.1f} mld JPY')
    if Z['status'] == '⚠️':
        Z['uwagi'].append('Japonia — zagranica w akcjach, giełda vs MOF: ' + Z['opis'][3:]
                          + ('; przeciwny kierunek w dużym tygodniu ' + ', '.join(p[0] for p in zle) if zle else '') + ' — różne miary, tylko uwaga')
    return Z


def jpx_korekty(jx, now=None):
    """Informacje o korekcie danych źródła zapisane przez zbieracz (jpx.json → korekty: [czas, tekst]) z ostatnich JPX_KOREKTA_DNI dni → uwagi.
    Zbieracz nie poprawia jeszcze zapisanych tygodni na ich podstawie (następna wersja) — uwaga mówi, że trzeba sprawdzić ręcznie."""
    now = now or NOW
    out = []
    for k in (jx.get('korekty') or []) if isinstance(jx, dict) and isinstance(jx.get('korekty'), list) else []:
        if not (isinstance(k, list) and len(k) == 2 and isinstance(k[1], str)):
            continue
        try:
            t = dt.datetime.fromisoformat(str(k[0]))
        except ValueError:
            continue
        t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        if now - t < dt.timedelta(days=JPX_KOREKTA_DNI):
            out.append(f'Japonia — giełda ({czas_pl(k[0])}): {k[1][:200]}')
    return out


def jpx_kontrola(files, R):
    """Krok kontroli v137 (bez sieci): porównanie giełda vs MOF i informacje o korektach źródła; uwagi do R['uwagi'] (nigdy do błędów).
    Brak pliku jpx = None."""
    Z = jpx_mof_porownanie(files.get('instytucje'), files.get('jpx'))
    if Z:
        R['uwagi'].extend(Z['uwagi'])
        Z['korekty'] = jpx_korekty(files.get('jpx'))
        R['uwagi'].extend(Z['korekty'])
    return Z


# ---------------------------------------------------------------- v247: strona w przeglądarce bez okna (Chrome, ekran telefonu) -----------
# Kontrola otwiera stronę jak telefon, czeka na dane i wykresy (czas wirtualny strony), zapisuje stronę i komunikaty konsoli. Nieobsłużony błąd
# JavaScriptu = ⚠️ (testy strony liczą na danych zastępczych — tu prawdziwe). 06.10.2026 lokalnie: zrzut po 10 s, 170 grafik, konsola pusta.
PRZEGL_PROGRAMY = ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser',
                   '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
PRZEGL_CZAS_S = 90          # najdłużej tyle czekamy na zrzut strony — potem przeglądarka jest zamykana („nie sprawdzono”)
PRZEGL_BUDZET_MS = 20000    # czas wirtualny strony przed zrzutem (dane, wykresy, liczniki odświeżania)
PRZEGL_OKNO = '390,844'     # ekran telefonu
PRZEGL_KONSOLA = re.compile(r':CONSOLE(?::\d+\]|\(\d+\)\]) "(.*)", source: (\S*) \((\d+)\)\s*$', re.S)   # v248: też CONSOLE(N); wiele linii
PRZEGL_REKORD = re.compile(r'\n(?=\[\d+:\d+:\d{4}/)')   # v248: nowy wpis logu zaczyna się od „[proces:wątek:MMDD/” — komunikat bywa wielowierszowy
PRZEGL_ZNACZNIK = 'const EXTRA'   # v248: zrzut to nasza strona (ten sam znacznik co pobranie index.html), nie np. strona 404
PRZEGL_BLAD = re.compile(r'^(Uncaught (\(in promise\) )?)?(\[object \w*(Error|Exception)\]|\w*(Error|Exception)\b)')   # v250/v252: nazwa błędu JS (też DOMException, „[object DOMException]”)
PRZEGL_KONSOLA_LUZ = re.compile(r':CONSOLE(?::\d+\]|\(\d+\)\]) "(.*?)", source: (\S*) \((\d+)\)', re.S)   # v252: wpis z doklejoną obcą linią
PRZEGL_POPRZ_H = 30   # v250: „drugi raz z rzędu” — poprzednia kontrola z przeglądarką nie starsza niż tyle godzin
PRZEGL_MIN_WYKRESY = 10   # v248: wykresów liniowych poza tekstem skryptów — 06.10: 20 z danymi, 0 bez danych (strona z pliku, dane niedostępne)
PRZEGL_ARTEFAKTY = re.compile(r'\bNaN\b|\bundefined\b|\[object Object\]|\bInfinity\b|\bnull\b|∞|Invalid Date')   # v252: „∞” — Intl dla Infinity
#   # v250: napisy-błędy (06.10: 0 na całej stronie)


def przegladarka_artefakty(tresc):
    """v250: napisy-błędy w tekście narysowanej strony (bez skryptów — już usunięte —, stylów, znaczników i atrybutów): „NaN”, „undefined”,
    „[object Object]”, „Infinity”, „null” — objaw błędu na prawdziwych danych → fragmenty tekstu z otoczeniem (gdzie)."""
    t = re.sub(r'<style\b[^>]*>.*?</style>', ' ', str(tresc or ''), flags=re.S | re.I)
    t = ' '.join(re.sub(r'<[^>]+>', ' ', t).split())
    return [t[max(0, m.start() - 40):m.end() + 20] for m in PRZEGL_ARTEFAKTY.finditer(t)]


def przegladarka_program(kandydaci=PRZEGL_PROGRAMY, szukaj=None):
    """v247: ścieżka przeglądarki — zmienna KONTROLA_CHROME albo pierwszy znaleziony program; brak = None."""
    szukaj = szukaj or shutil.which
    env = os.environ.get('KONTROLA_CHROME')
    for k in ((env,) if env else ()) + tuple(kandydaci):
        p = (k if os.path.exists(k) else None) if os.path.isabs(k) else szukaj(k)
        if p:
            return p
    return None


def przegladarka_konsola(log):
    """v247: komunikaty konsoli z logu przeglądarki → {'bledy': nieobsłużone wyjątki („Uncaught …”, także odrzucone obietnice),
    'zasoby': nieudane wczytania i zapytania zablokowane (adres; 06.10 lokalnie: źródło cen krypto po kilku próbach — strona ma zapas),
    'inne': pozostałe komunikaty (console.error/warn/log), 'nieczytelne': liczba wpisów konsoli, których nie udało się odczytać}.
    v248: log dzielony na wpisy tylko przed nowym wpisem — komunikat z nową linią (np. błąd JSON.parse z treścią strony błędu) nie ginie."""
    out = {'bledy': [], 'zasoby': [], 'inne': [], 'nieczytelne': 0}
    for rek in PRZEGL_REKORD.split(str(log or '')):
        if ':CONSOLE' not in rek[:120]:
            continue
        m = PRZEGL_KONSOLA.search(rek) or PRZEGL_KONSOLA_LUZ.search(rek)   # v252: obca linia doklejona do wpisu — wpis nadal odczytany
        if not m:
            if re.search(r':CONSOLE[^\]]*\] "Uncaught', rek):   # v250: obca linia doklejona do wpisu z błędem — nadal błąd
                out['bledy'].append('nieczytelny wpis z „Uncaught” (zob. log przeglądarki)')
            else:
                out['nieczytelne'] += 1
            continue
        msg, src, nr = ' '.join(m.group(1).split()), m.group(2), m.group(3)   # wiele linii → jedna
        if msg.startswith('Uncaught') or PRZEGL_BLAD.match(msg):   # v250: też błąd złapany przez stronę i wypisany przez console.error
            out['bledy'].append(f'{msg[:160]} ({src.split("?")[0].rsplit("/", 1)[-1][:40] or "strona"}:{nr})')
        elif msg.startswith('Failed to load resource'):
            out['zasoby'].append(src[:160])
        elif msg.startswith("Access to fetch at '"):   # zapytanie zablokowane przez przeglądarkę (CORS — zwykle limit źródła: odpowiedź bez nagłówka)
            out['zasoby'].append(msg[len("Access to fetch at '"):].split("'", 1)[0][:160])
        else:
            out['inne'].append(msg[:160])
    return out


def strona_przegladarka(url, czas_s=PRZEGL_CZAS_S, program=None, zegar=time.monotonic, spij=time.sleep):
    """v247: strona w przeglądarce bez okna. v248 → {'stan': 'ok', 'ok': True, 'czas_s', 'bajty', 'svg', 'wykresy' (bez tekstu skryptów),
    'bledy', 'zasoby', 'inne', 'nieczytelne'} albo {'stan': 'brak_programu' | 'zakonczona' (awaria: kod i ostatni wpis błędu) | 'zawieszona'
    (przeglądarka działa, strony brak — zawieszona strona albo źródło, które nie odpowiada) | 'inna_strona' (brak znacznika), 'brak': opis, …}.
    Osobny profil tymczasowy; po zrzucie albo czas_s — zamknięcie całej grupy procesów."""
    program = program or przegladarka_program()
    if not program:
        return {'stan': 'brak_programu', 'brak': 'brak przeglądarki na maszynie kontroli'}
    with tempfile.TemporaryDirectory(prefix='kontrola-przegl-') as tmp:
        args = [program, '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check', '--disable-extensions',
                '--disable-dev-shm-usage', f'--user-data-dir={os.path.join(tmp, "profil")}', '--enable-logging=stderr', '--v=1',
                f'--virtual-time-budget={PRZEGL_BUDZET_MS}', f'--window-size={PRZEGL_OKNO}', '--dump-dom', url]
        if sys.platform.startswith('linux'):
            args.insert(1, '--no-sandbox')   # maszyny GitHub (ubuntu) nie dają piaskownicy jądra; otwieramy tylko własną stronę
        po, pe = os.path.join(tmp, 'strona.html'), os.path.join(tmp, 'konsola.log')
        t0, rc = zegar(), None
        with open(po, 'wb') as fo, open(pe, 'wb') as fe:
            p = subprocess.Popen(args, stdout=fo, stderr=fe, stdin=subprocess.DEVNULL, start_new_session=True)
            try:
                while zegar() - t0 < czas_s and p.poll() is None:
                    try:
                        with open(po, 'rb') as f:
                            f.seek(max(0, os.path.getsize(po) - 64))
                            if b'</html>' in f.read():
                                break
                    except OSError:
                        pass
                    spij(1)
            finally:
                rc = p.poll()   # v248: zakończona sama (awaria) czy nadal działa
                try:
                    os.killpg(p.pid, signal.SIGKILL)   # przeglądarka nie zamyka się sama (liczniki strony) — cała grupa procesów
                except OSError:
                    pass
                try:
                    p.wait(timeout=10)
                except Exception:  # noqa
                    pass
        czas = round(zegar() - t0, 1)
        with open(po, 'rb') as f:
            dom = f.read().decode('utf-8', 'replace')
        with open(pe, 'rb') as f:
            log = f.read().decode('utf-8', 'replace')
    K = przegladarka_konsola(log)
    if '</html>' not in dom[-64:]:
        if rc is not None:   # v248: przeglądarka zakończyła się sama bez strony — awaria (kod i ostatni wpis błędu)
            L = [x.strip() for x in log.splitlines() if x.strip()]
            ost = next((x for x in reversed(L) if ':ERROR:' in x or ':FATAL:' in x), L[-1] if L else '')
            return {'stan': 'zakonczona', 'brak': f'przeglądarka zakończyła się po {czas:g} s bez strony, kod {rc}'.replace('.', ',')
                    + (f': {ost[-100:]}' if ost else ''), 'czas_s': czas, **K}
        return {'stan': 'zawieszona', 'brak': f'strona nie oddała się w {czas_s} s — zawieszona strona albo źródło, które nie odpowiada',
                'czas_s': czas, **K}
    if PRZEGL_ZNACZNIK not in dom:
        return {'stan': 'inna_strona', 'brak': 'przeglądarka dostała inną stronę (bez znacznika strony)', 'czas_s': czas, **K}
    tresc = re.sub(r'<script\b[^>]*>.*?</script>', '', dom, flags=re.S | re.I)   # v248: tylko narysowana strona, nie tekst skryptów
    A = przegladarka_artefakty(tresc)   # v250: napisy-błędy w tekście strony
    return {'stan': 'ok', 'ok': True, 'czas_s': czas, 'bajty': len(dom), 'svg': tresc.count('<svg'), 'wykresy': tresc.count('class="arc-gr"'),
            'artefakty': A[:5], 'artefakty_n': len(A), **K}


def przegladarka_poprzedni(path, now=None):
    """v248: stan przeglądarki z ostatniej kontroli, która ją uruchamiała (kontrola/historia.json, pole 'przegl') albo None. v250: tylko
    z kontroli z ostatnich PRZEGL_POPRZ_H h (dwie szybkie publikacje mogą nadpisać wpis historii — stary stan nie liczy się „z rzędu”)."""
    now = now or NOW
    try:
        with open(path, encoding='utf-8') as f:
            H = json.load(f)
    except Exception:  # noqa
        return None
    for h in reversed(H) if isinstance(H, list) else ():
        if isinstance(h, dict) and h.get('przegl'):
            try:
                if (now - dt.datetime.fromisoformat(str(h.get('at')))).total_seconds() > PRZEGL_POPRZ_H * 3600:
                    return None
            except (TypeError, ValueError):
                pass
            return h['przegl']
    return None


def przegladarka_uwagi(P, poprzedni=None):
    """v247/v248: uwagi tylko z pełnego zrzutu: nieobsłużone błędy JavaScriptu, za mało wykresów liniowych (PRZEGL_MIN_WYKRESY). Strona,
    która się nie oddała (zawieszona albo wiszące źródło) — uwaga dopiero, gdy poprzednia kontrola z przeglądarką skończyła się tak samo."""
    if not isinstance(P, dict):
        return []
    out = []
    if P.get('ok'):
        if P.get('bledy'):
            out.append(f'strona w przeglądarce: błędów JavaScriptu {len(P["bledy"])} — pierwszy: {P["bledy"][0]}')
        if P.get('artefakty_n'):   # v250
            out.append(f'strona w przeglądarce: napisy-błędy w tekście strony (NaN, undefined…): {P["artefakty_n"]} — pierwszy: „{(P.get("artefakty") or ["—"])[0]}”')
        if isinstance(P.get('wykresy'), int) and P['wykresy'] < PRZEGL_MIN_WYKRESY:
            out.append(f'strona w przeglądarce: narysowanych wykresów liniowych tylko {P["wykresy"]} (zwykle ok. 20) — dane mogły się nie wczytać')
    elif P.get('stan') == 'zawieszona' and poprzedni == 'zawieszona':
        out.append(f'strona w przeglądarce: drugi raz z rzędu nie oddała się w {PRZEGL_CZAS_S} s — możliwa zawieszona strona (pętla w skrypcie) '
                   'albo źródło, które nie odpowiada')
    return out


def przegladarka_wiersz(P):
    """v247/v248: wiersz raportu „Strona w przeglądarce” — błędy JS i za mało wykresów ⚠️; nieudane wczytania, inne i nieczytelne komunikaty
    konsoli ℹ️; bez pełnego zrzutu „nie sprawdzono” ℹ️ (drugi raz z rzędu bez strony — ⚠️), z błędami z logu do przerwania jako informacją."""
    if not P.get('ok'):
        b = P.get('bledy') or []
        return (f'- Strona w przeglądarce (bez okna, ekran telefonu): nie sprawdzono ({P.get("brak") or "—"})'
                + (f'; w logu do przerwania błędów JavaScriptu: {len(b)}' if b else '') + (' ⚠️.' if P.get('powtorka') else ' ℹ️.'))
    b, z, i, nc = P.get('bledy') or [], P.get('zasoby') or [], P.get('inne') or [], P.get('nieczytelne') or 0
    malo = isinstance(P.get('wykresy'), int) and P['wykresy'] < PRZEGL_MIN_WYKRESY
    hosty = sorted({u.split('/')[2] if '://' in u else u for u in z})
    return (f'- Strona w przeglądarce (bez okna, ekran telefonu 390 px): zrzut po {str(P.get("czas_s", "—")).replace(".", ",")} s — grafik '
            f'{P.get("svg", 0)}, wykresów liniowych {P.get("wykresy", 0)}' + (' ⚠️ (zwykle ok. 20)' if malo else '')
            + f'; błędów JavaScriptu: {len(b)} ' + ('⚠️' if b else ('ℹ️' if nc else '✅'))
            + (f' (wpisów konsoli nieczytelnych: {nc})' if nc else '')
            + (f'; napisy-błędy w tekście (NaN, undefined…): {P["artefakty_n"]} ⚠️' if P.get('artefakty_n') else '')   # v250
            + (f'; nieudane wczytania: {len(z)} ({", ".join(hosty[:4])}) ℹ️' if z else '')
            + (f'; inne komunikaty konsoli: {len(i)} (pierwszy: {i[0][:80]}) ℹ️' if i else '') + '.')

# ---------------------------------------------------------------- v141: lżejsza strona — pliki słowników języków (i18n/<język>.<skrót>.js) ----------------------------------------------------------------
I18N_MAPA = re.compile(r'const CF_I18N_H=(\{[^{}]*\})[;,]')
I18N_JEZYKI = ('de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja')


def i18n_skrot(jezyk, d_json):
    """Ten sam wzór co narzedzia/odchudz_strone.py (skrot): sha256(język + '\\n' + JSON słownika z pliku)[:8]."""
    import hashlib
    return hashlib.sha256((jezyk + '\n' + d_json).encode('utf-8')).hexdigest()[:8]


def i18n_kontrola(body, R, pobierz=None):
    """v141: index.html na żywo. Mapa plików słowników (CF_I18N_H) — każdy plik HTTP 200, treść window.CF_I18N_X tego języka i skrótu,
    skrót w nazwie = treść. Brak mapy = na żywo PEŁNA strona (przekształcenie przy publikacji odmówiło — publikacja dalej działa, ale strona
    jest cięższa; szczegóły w ostrzeżeniu „lżejsza strona” przebiegu „Strona i dane”). Tylko uwagi (najwyżej ⚠️, nigdy błąd).
    Wynik w R['strona']['i18n'] (linia raportu pod „Strona główna”)."""
    if body is None:
        return None
    pobierz = pobierz or get
    txt = body.decode('utf-8', 'replace') if isinstance(body, bytes) else str(body)
    m = I18N_MAPA.search(txt)
    if not m:
        R['strona']['i18n'] = {'pelna': True, 'opis': 'pełna strona (bez osobnych plików słowników)'}
        R['uwagi'].append('strona główna to PEŁNA wersja (bez osobnych plików słowników v141) — przekształcenie przy publikacji odmówiło; '
                          'zobacz ostrzeżenie „lżejsza strona” w przebiegu „Strona i dane”')
        return R['strona']['i18n']
    try:
        mapa = json.loads(m.group(1))
    except ValueError:
        mapa = {}
    zle, ok = [], 0
    for j in I18N_JEZYKI:
        h = mapa.get(j)
        if not (isinstance(h, str) and re.fullmatch(r'[0-9a-f]{8}', h)):
            zle.append(f'{j}: brak w mapie'); continue
        try:
            st, b, ms = pobierz(f'{SITE}/i18n/{j}.{h}.js')
        except urllib.error.HTTPError as e:
            zle.append(f'{j}.{h}.js: HTTP {e.code}'); continue
        except Exception as e:  # noqa
            zle.append(f'{j}.{h}.js: {str(e)[:60]}'); continue
        t = b.decode('utf-8', 'replace') if isinstance(b, bytes) else str(b)
        pre = f'window.CF_I18N_X={{"lang":"{j}","h":"{h}","d":'
        if st != 200:
            zle.append(f'{j}.{h}.js: HTTP {st}')
        elif not (t.startswith(pre) and t.endswith('};\n')) or i18n_skrot(j, t[len(pre):-3]) != h:
            zle.append(f'{j}.{h}.js: treść nie zgadza się ze skrótem w nazwie')
        else:
            ok += 1
    R['strona']['i18n'] = {'pelna': False, 'plikow': len(I18N_JEZYKI), 'ok': ok, 'zle': zle,
                           'opis': f'{ok} z {len(I18N_JEZYKI)} plików odpowiada, skróty zgodne' if not zle else f'{ok} z {len(I18N_JEZYKI)} w porządku'}
    if zle:
        R['uwagi'].append('pliki słowników języków (lżejsza strona): ' + '; '.join(zle) + ' — widz w tym języku dostanie angielski zapas')
    return R['strona']['i18n']


# ---------------------------------------------------------------- v133: tokenizowane aktywa RWA (data/rwa.json) ----------------------------------------------------------------
RWA_ETYKIETA = 'tokenizowane aktywa RWA (co 3 h)'   # v172: było co 6 h
RWA_SWIEZ_MIN = 12 * 60    # min — lista starsza (plik co 3 h od v172, część z błędem ponawiana po godzinie) = ⚠️; nigdy ❌ ani BŁĄD
RWA_PP = 1.0               # pkt proc. — |własna zmiana 7 dni − zmiana 7 dni podana przez źródło| (produkty z listy) większa = ⚠️
RWA_HIST_MIN = 8           # dni własnych zapisów sum potrzebnych do porównania zmian 7 dni (wcześniej tylko informacja)
RWA_SKOK = 25.0            # % — zmiana sumy między dwoma kolejnymi dniami zapisów większa = ⚠️ (dni z ostatniego tygodnia)
RWA_HID_MIN = 20           # mniej produktów spoza głównej listy z jakąkolwiek wartością w ostatnim pobraniu = ⚠️ (27.09: 33 z 47) — źródło
                           # przestało podawać ich wartości (pusty tekst, „0”, 400, 404); plan v128 §4.4
RWA_FZ_PROG = 50.0         # % — udział wartości bez bieżącej wyceny w (bieżące + bez wyceny) większy = ⚠️ (właściciel widzi to w raporcie; tylko uwaga)
RWA_HID_DNI = 3            # v196: dni od najmłodszego „brak od” produktów spoza listy — potem stan trwały (źródło zmieniło zakres danych)
RWA_HID_FZ = 5.0           # v196: % „bez bieżącej wyceny”, do którego trwały brak wartości spoza listy jest tylko informacją ℹ️ (06.10: 1,6%)


def rwa_swiezosc(j, now=None):
    """Wiersz świeżości (etykieta, status, wiek min, data, uwaga): czas listy (part_at.list, inaczej at); starszy niż RWA_SWIEZ_MIN = ⚠️, nigdy ❌.
    Brak pliku = ⚠️ „brak danych” (zbieracz bez poprzedniego pliku i bez danych nie zapisuje pliku — notatka w META, nie błąd)."""
    if not isinstance(j, dict):
        return (RWA_ETYKIETA, '⚠️', None, None, 'brak pliku data/rwa.json — panel na stronie ukryty (tylko uwaga)')
    pa = j.get('part_at') if isinstance(j.get('part_at'), dict) else {}
    ts = pa.get('list') if isinstance(pa.get('list'), str) else j.get('at')
    w = wiek_danych(ts, 'ts', 'h', now or NOW) if isinstance(ts, str) else None
    if w is None:
        return (RWA_ETYKIETA, '?', None, None, 'brak czasu danych w pliku')
    if w <= RWA_SWIEZ_MIN:
        return (RWA_ETYKIETA, '✅', w, ts, '')
    return (RWA_ETYKIETA, '⚠️', w, ts, f'lista starsza niż {RWA_SWIEZ_MIN // 60} h (plik co 3 h) — tylko uwaga')


def _rwa_hist(j):
    """Wiersze historii sum [dzień, suma, …] z prawdziwą datą i liczbą sumy (mln USD), rosnąco, bez powtórzeń."""
    out = {}
    for r in j.get('hist') or []:
        if isinstance(r, list) and len(r) >= 2 and isinstance(r[0], str) and isinstance(r[1], (int, float)) and not isinstance(r[1], bool) and r[1] > 0:
            try:
                dt.date.fromisoformat(r[0])
            except ValueError:
                continue
            out[r[0]] = float(r[1])
    return sorted(out.items())


def rwa_brak_od(j):
    """v196: najmłodszy dzień „brak od” w zapisach produktów spoza listy (hv: [wartość, dzień tej samej wartości, zmiana, odczyty, brak od]);
    brak zapisów albo dat = None."""
    hv = j.get('hv') if isinstance(j, dict) and isinstance(j.get('hv'), dict) else {}
    d = [r[4] for r in hv.values() if isinstance(r, list) and len(r) > 4 and isinstance(r[4], str) and re.match(r'^\d{4}-\d{2}-\d{2}$', r[4])]
    return max(d) if d else None


def rwa_porownanie(j, now=None):
    """Kontrola pliku RWA bez sieci (najwyżej ⚠️): (1) po ≥ RWA_HIST_MIN dniach zapisów — własna zmiana 7 dni produktów z listy vs zmiana 7 dni
    podana przez źródło (ważona wartością); źródło porównuje punkt godzinowy sprzed 168 h, my dzienne zapisy z chwil naszych pobrań, więc
    drobna różnica jest normalna; (2) produkty spoza głównej listy: ostatnie pobranie przerwane = ⚠️; ile ma bieżącą wartość, a ile wartość
    niezmienioną od dnia X (poza sumami zbieracza — źródło przestało je odświeżać; stan od 27.09.2026); udział wartości bez bieżącej wyceny
    w (bieżące + bez wyceny) ponad RWA_FZ_PROG % = ⚠️, inaczej informacja ℹ️;
    (3) skok sumy > RWA_SKOK % między dwoma kolejnymi dniami zapisów z ostatniego tygodnia. → {'status', 'opis', 'uwagi', …}."""
    now = now or NOW
    Z = {'status': '✅', 'opis': '', 'uwagi': []}
    if not isinstance(j, dict):
        return None
    H = _rwa_hist(j)
    chk = j.get('chk') if isinstance(j.get('chk'), dict) else {}
    n = j.get('n') if isinstance(j.get('n'), dict) else {}
    ok = j.get('ok') if isinstance(j.get('ok'), dict) else {}
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    cz = []
    span = (dt.date.fromisoformat(H[-1][0]) - dt.date.fromisoformat(H[0][0])).days + 1 if H else 0
    a, b = chk.get('c7_api_listed'), chk.get('c7_own_listed')
    Z['c7_api'], Z['c7_own'] = (a if num(a) else None), (b if num(b) else None)
    if span < RWA_HIST_MIN:
        cz.append(f'ℹ️ zapisów sum {len(H)} (od {H[0][0] if H else "—"}) — porównanie zmiany 7 dni od {RWA_HIST_MIN}. dnia')
    elif not (num(a) and num(b)):
        cz.append('ℹ️ zmiana 7 dni: brak jednej z liczb (własnej albo źródła) — bez oceny')
    else:
        d = abs(b - a)
        Z['c7_roznica_pp'] = round(d, 3)
        if d > RWA_PP:
            Z['status'] = '⚠️'
            Z['uwagi'].append(f'tokenizowane aktywa: zmiana 7 dni produktów z listy — własna {b:+.2f}% vs źródło {a:+.2f}% (różnica {d:.2f} pkt proc., próg {RWA_PP:g}); '
                              'źródło liczy od punktu godzinowego sprzed 168 h, my od dziennego zapisu z chwili pobrania — sprawdzić, czy różnica się utrzymuje')
        cz.append(f'zmiana 7 dni produktów z listy: własna {b:+.2f}% vs źródło {a:+.2f}% (różnica {d:.2f} pkt proc.) {"⚠️" if d > RWA_PP else "✅"}')
    hv, kept = n.get('hidden_valued'), n.get('kept')
    if ok.get('hidden') is False:
        Z['status'] = '⚠️'
        Z['uwagi'].append(f'tokenizowane aktywa: ostatnie pobranie wartości produktów spoza głównej listy przerwane — z poprzedniego dnia: {kept if num(kept) else "—"} '
                          '(ponowienie po 1 h, 2 h, potem co 3 h; tylko uwaga)')
        cz.append(f'produkty spoza listy: pobranie przerwane, z poprzedniego dnia {kept if num(kept) else "—"} ⚠️')
    if num(hv) and hv < RWA_HID_MIN:
        # v196: stan trwały (≥ RWA_HID_DNI dni od najmłodszego „brak od”) przy małym udziale „bez bieżącej wyceny” — tylko informacja, nie codzienna uwaga
        bo = rwa_brak_od(j)
        s0 = j.get('stale') if isinstance(j.get('stale'), dict) else {}
        sv0 = s0.get('v') if num(s0.get('v')) and s0.get('v') > 0 else 0.0
        cv0 = ((j.get('seg') or {}).get('all') or {}).get('v') if isinstance((j.get('seg') or {}).get('all'), dict) else None
        cv0 = cv0 if num(cv0) and cv0 > 0 else 0.0
        p0 = sv0 / (cv0 + sv0) * 100 if cv0 + sv0 > 0 else 0.0
        dni = (now.date() - dt.date.fromisoformat(bo)).days if bo else None
        if dni is not None and dni >= RWA_HID_DNI and p0 <= RWA_HID_FZ:
            cz.append(f'ℹ️ produkty spoza listy z wartością {hv} (próg {RWA_HID_MIN}) — źródło nie podaje ich wartości od {bo} ({dni} dni, stan trwały); '
                      + f'bez bieżącej wyceny {p0:.1f}% sumy'.replace('.', ',') + ' — bez uwagi')
        else:
            Z['status'] = '⚠️'
            Z['uwagi'].append(f'tokenizowane aktywa: produkty spoza głównej listy z jakąkolwiek wartością — tylko {hv} (próg {RWA_HID_MIN}) — źródło przestało '
                              'podawać ich wartości; ostatnio znane są w grupie „bez bieżącej wyceny”, sumy spadną (tylko uwaga)')
            cz.append(f'produkty spoza listy z wartością {hv} (próg {RWA_HID_MIN}) ⚠️')
    st = j.get('stale') if isinstance(j.get('stale'), dict) else {}
    sv = st.get('v') if num(st.get('v')) and st.get('v') > 0 else 0.0
    seg = j.get('seg') if isinstance(j.get('seg'), dict) else {}
    cv = (seg.get('all') or {}).get('v') if isinstance(seg.get('all'), dict) else None
    cv = cv if num(cv) and cv > 0 else 0.0
    if sv > 0:
        p = sv / (cv + sv) * 100
        Z['fz_pct'] = round(p, 1)
        ng = st.get('ng') if num(st.get('ng')) else 0
        kom = (f'bez bieżącej wyceny {p:.0f}% wartości ({sv / 1e9:.1f} mld USD, liczba produktów {st.get("n") if num(st.get("n")) else "—"}: '
               + (f'niezmienione co najmniej od {st.get("last") or "—"}' + (' — źródło stoi' if st.get('src') is True else '') if st.get('nf') or not ng else '')
               + (f'{", " if st.get("nf") else ""}{ng} bez wartości od {st.get("gone") or "—"}' if ng else '')
               + f'), z bieżącą wyceną {cv / 1e9:.1f} mld USD')
        if p > RWA_FZ_PROG:
            Z['status'] = '⚠️'
            Z['uwagi'].append(f'tokenizowane aktywa: {kom} — sumy na stronie obejmują tylko wartości bieżące (próg {RWA_FZ_PROG:g}%; tylko uwaga)')
        cz.append(kom + (' ⚠️' if p > RWA_FZ_PROG else ' ℹ️'))
    elif num(hv):
        cz.append(f'produkty spoza listy: z bieżącą wartością {hv}, bez bieżącej wyceny 0 ✅')
    lo = (now.date() - dt.timedelta(days=7)).isoformat()
    skoki = []
    hd = rwc_hd(j)   # v150: dzień zmiany zbioru produktów z odczytu własnego — skok liczony bez nich (zmiana zakresu danych, nie rynku)
    for d, x in rwe_hd(j).items():   # v169: dane emitentów tak samo (produkty z przedrostkiem e:, żeby zbiory się nie myliły)
        a = hd.get(d, (0.0, frozenset()))
        hd[d] = (a[0] + x[0], a[1] | frozenset('e:' + s for s in x[1]))
    for (d0, v0), (d1, v1) in zip(H, H[1:]):
        if d1 >= lo and (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days == 1:
            a0, a1 = hd.get(d0, (0.0, frozenset())), hd.get(d1, (0.0, frozenset()))
            if a0[1] != a1[1] and v0 - a0[0] > 0:
                p = ((v1 - a1[0]) / (v0 - a0[0]) - 1) * 100
                cz.append(f'ℹ️ {d1}: zmiana zbioru produktów z odczytu własnego albo danych emitentów ({a0[0] / 1e3:.1f} → {a1[0] / 1e3:.1f} mld USD) — skok sumy liczony bez nich')
            else:
                p = (v1 / v0 - 1) * 100
            if abs(p) > RWA_SKOK:
                skoki.append(f'{d0} → {d1}: {p:+.1f}%')
    Z['skoki'] = skoki
    if skoki:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa: skok sumy dzień do dnia ponad ' + f'{RWA_SKOK:g}%: ' + '; '.join(skoki[:3]) + ' — sprawdzić, czy to nie zmiana zakresu danych')
        cz.append('skok sumy: ' + '; '.join(skoki[:3]) + ' ⚠️')
    elif len(H) >= 2:
        cz.append(f'skoków sumy ponad {RWA_SKOK:g}% w tygodniu: brak ✅')
    Z['opis'] = '; '.join(cz)
    return Z


def rwa_kontrola(files, R):
    """Wynik porównań RWA do raportu (zgodność) i uwag; brak pliku = None (wiersz świeżości i tak mówi „brak pliku”)."""
    Z = rwa_porownanie(files.get('rwa'))
    if Z:
        R['uwagi'].extend(Z['uwagi'])
    return Z


# ---------------------------------------------------------------- v150: tokenizowane aktywa — odczyt własny z łańcucha (blok onchain w data/rwa.json) ----------------------------------------------------------------
RWC_ETYKIETA = 'tokenizowane aktywa — odczyt własny z łańcucha (co 3 h)'
RWC_SWIEZ_MIN = 12 * 60    # min — odczyt starszy (plik co 3 h od v172) = ⚠️; nigdy ❌ ani BŁĄD (zbieracz i tak nie liczy odczytów starszych niż 12 h)
RWC_SKOK_POD = 50.0        # % — zmiana podaży produktu między dwoma kolejnymi dniami zapisów (24 h) większa = ⚠️ (zły kontrakt albo zmiana emisji)
RWC_RAZY = 3.0             # wartość z łańcucha vs ostatnio znana wartość źródła v133 tego produktu: więcej niż 3× albo mniej niż 1/3 = ⚠️


def rwc_swiezosc(j, now=None):
    """Wiersz świeżości odczytu własnego (etykieta, status, wiek min, data, uwaga) — czas bloku onchain (at). Brak pliku = None (wiersz RWA mówi
    „brak pliku”); plik bez bloku (przed pierwszym odczytem po wdrożeniu v150) albo wyłącznik RWA_CHAIN_OFF = status „—” z opisem, bez uwagi;
    starszy niż RWC_SWIEZ_MIN = ⚠️, nigdy ❌."""
    if not isinstance(j, dict):
        return None
    oc = j.get('onchain')
    if not isinstance(oc, dict):
        return (RWC_ETYKIETA, '—', None, None, 'brak odczytu własnego w pliku (przed pierwszym odczytem po wdrożeniu v150)')
    if oc.get('off'):
        return (RWC_ETYKIETA, '—', None, None, 'wyłączone (RWA_CHAIN_OFF)')
    ts = oc.get('at')
    w = wiek_danych(ts, 'ts', 'h', now or NOW) if isinstance(ts, str) else None
    if w is None:
        return (RWC_ETYKIETA, '?', None, None, 'brak czasu odczytu w pliku')
    if w <= RWC_SWIEZ_MIN:
        return (RWC_ETYKIETA, '✅', w, ts, '')
    return (RWC_ETYKIETA, '⚠️', w, ts, f'odczyt starszy niż {RWC_SWIEZ_MIN // 60} h (plik co 3 h) — produkty z odczytu własnego wracają do „bez bieżącej wyceny”')


def rwc_hd(j):
    """Dzienny zapis odczytu własnego z pliku: {dzień: (mln USD w sumach, zbiór produktów)} — tylko poprawne wiersze."""
    oc = j.get('onchain') if isinstance(j, dict) else None
    hd = oc.get('hd') if isinstance(oc, dict) and isinstance(oc.get('hd'), dict) else {}
    out = {}
    for d, x in hd.items():
        if (isinstance(d, str) and isinstance(x, list) and len(x) == 2 and isinstance(x[0], (int, float)) and not isinstance(x[0], bool)
                and x[0] >= 0 and isinstance(x[1], list)):
            out[d] = (float(x[0]), frozenset(s for s in x[1] if isinstance(s, str)))
    return out


def rwc_porownanie(j, now=None):
    """Kontrola odczytu własnego bez sieci (najwyżej ⚠️): (1) podaż produktu — zmiana między dwoma kolejnymi dniami zapisów (24 h) ponad
    RWC_SKOK_POD % = ⚠️; (2) wartość z łańcucha vs ostatnio znana wartość źródła v133 (zapis hv) — poza [1/RWC_RAZY, RWC_RAZY] = ⚠️ (zły
    adres, zła reguła ceny albo miejsca dziesiętne); (3) produkty z listy bez pełnego odczytu (sieci bez liczby albo cena nieświeża) — ⚠️ gdy
    wypadły z sum, ℹ️ gdy to stały brak sieci, której nie czytamy; (4) sieci bez odpowiedzi w ostatnim odczycie (ok False) = ⚠️.
    Brak pliku albo bloku = None; wyłącznik = opis „wyłączone”. → {'status', 'opis', 'uwagi', …}."""
    if not isinstance(j, dict) or not isinstance(j.get('onchain'), dict):
        return None
    oc = j['onchain']
    Z = {'status': '✅', 'opis': '', 'uwagi': []}
    if oc.get('off'):
        Z['opis'] = 'wyłączone (RWA_CHAIN_OFF) — sumy bez odczytu własnego'
        return Z
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    P = oc.get('p') if isinstance(oc.get('p'), dict) else {}
    used = oc.get('used') if isinstance(oc.get('used'), dict) else {}
    hv = j.get('hv') if isinstance(j.get('hv'), dict) else {}
    cz, skoki, razy, braki = [], [], [], []
    for s, p in sorted(P.items()):
        if not isinstance(p, dict):
            continue
        nm = p.get('name') if isinstance(p.get('name'), str) else s
        H = sorted((x for x in ((oc.get('hs') or {}).get(s) or []) if isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and num(x[1])),
                   key=lambda x: x[0])
        if len(H) >= 2:
            (d0, a), (d1, b) = H[-2], H[-1]
            try:
                kol = (dt.date.fromisoformat(d1) - dt.date.fromisoformat(d0)).days == 1
            except ValueError:
                kol = False
            if kol and a > 0 and abs(b / a - 1) * 100 > RWC_SKOK_POD:
                skoki.append(f'{nm} {d0} → {d1}: {(b / a - 1) * 100:+.0f}%')
        v = p.get('v') if num(p.get('v')) else None
        r = hv.get(s)
        if v and isinstance(r, list) and r and num(r[0]) and r[0] > 0 and not (1 / RWC_RAZY <= v / r[0] <= RWC_RAZY):
            razy.append(f'{nm}: z łańcucha {v / 1e9:.2f} mld USD vs ostatnio znana {r[0] / 1e9:.2f} mld USD ({v / r[0]:.1f}×)')
        if s not in used:
            n, nr = p.get('n'), p.get('nr')
            if num(n) and num(nr) and nr < n:
                braki.append(f'{nm}: {nr} z {n} kontraktów' + (f' (bez liczby: {", ".join(p.get("un") or [])})' if p.get('un') else ''))
            elif p.get('px_ok') is False:
                braki.append(f'{nm}: cena nieświeża ({p.get("px_at") or "—"})')
            elif 'rez' in p and not (isinstance(p.get('rez'), dict) and p['rez'].get('ok') is True):
                braki.append(f'{nm}: brak bieżących danych emitenta o rezerwie (wybite, niewydane)')   # v160: Tether Gold
    if skoki:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): podaż zmieniła się w ciągu doby o ponad ' + f'{RWC_SKOK_POD:g}%: ' + '; '.join(skoki[:3])
                          + ' — sprawdzić kontrakt i emisję')
        cz.append('podaż 24 h: ' + '; '.join(skoki[:3]) + ' ⚠️')
    else:
        cz.append(f'podaż 24 h: zmian ponad {RWC_SKOK_POD:g}% brak ✅')
    if razy:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): wartość z łańcucha daleko od ostatnio znanej: ' + '; '.join(razy[:3]) + ' — sprawdzić adresy i regułę ceny')
        cz.append('wartość vs ostatnio znana: ' + '; '.join(razy[:3]) + ' ⚠️')
    elif P:
        cz.append(f'wartość vs ostatnio znana: w paśmie 1/{RWC_RAZY:g}–{RWC_RAZY:g}× ✅')
    tot = sum(x for x in used.values() if num(x))
    cz.append(f'w sumach z odczytu własnego: {len(used)} z {len(P)} produktów, {tot / 1e9:.1f} mld USD')
    if braki:
        cz.append('bez pełnego odczytu (poza sumami): ' + '; '.join(braki[:4]) + ' ℹ️')
    hd = rwc_hd(j)
    dzis = (oc.get('at') or '')[:10]
    wcz = [d for d in sorted(hd) if d < dzis]
    wyp = sorted(s for s in (hd[wcz[-1]][1] if wcz else ()) if s not in used)
    if wyp:
        Z['status'] = '⚠️'
        nm = lambda s: (P.get(s) or {}).get('name') if isinstance(P.get(s), dict) and isinstance((P.get(s) or {}).get('name'), str) else s  # noqa: E731
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): po ' + wcz[-1] + ' już nie liczone z łańcucha: ' + ', '.join(nm(s) for s in wyp)
                          + ' — odczyt niepełny, cena nieświeża albo źródło v133 znów podaje bieżącą wartość (tylko uwaga)')
        cz.append('już nie z łańcucha: ' + ', '.join(nm(s) for s in wyp) + ' ⚠️')
    if oc.get('ok') is False:
        Z['status'] = '⚠️'
        nt = [x for x in (oc.get('notes') or []) if isinstance(x, str)]
        Z['uwagi'].append('tokenizowane aktywa (odczyt własny): ostatni odczyt niepełny — ' + ('; '.join(nt[:2]) if nt else 'brak szczegółów')
                          + ' (wartości z poprzedniego odczytu najwyżej 12 h; tylko uwaga)')
        cz.append('ostatni odczyt niepełny ⚠️')
    Z['skoki_podazy'], Z['razy'], Z['braki'], Z['wypadly'] = skoki, razy, braki, wyp
    Z['opis'] = '; '.join(cz)
    return Z


def rwc_kontrola(files, R):
    """Wynik porównań odczytu własnego do raportu (zgodność) i uwag; brak pliku albo bloku = None."""
    Z = rwc_porownanie(files.get('rwa'))
    if Z:
        R['uwagi'].extend(Z['uwagi'])
    return Z


# ---------------------------------------------------------------- v169: tokenizowane aktywa — dane emitentów (blok issuer w data/rwa.json) ----------------------------------------------------------------
RWE_ETYKIETA = 'tokenizowane aktywa — dane emitentów (co 3 h)'
RWE_SWIEZ_MIN = 12 * 60    # min — odczyt starszy (plik co 3 h od v172) = ⚠️; nigdy ❌ ani BŁĄD
RWE_ZAKRES = (0.8, 1.25)   # wartość wg emitenta vs ostatnio znana źródła v133 poza tym pasmem = informacja ℹ️ (inny zakres liczenia albo prawdziwa zmiana)


def rwe_swiezosc(j, now=None):
    """Wiersz świeżości danych emitentów (etykieta, status, wiek min, data, uwaga) — czas bloku issuer (at). Brak pliku = None (wiersz RWA mówi
    „brak pliku”); plik bez bloku (przed pierwszym odczytem po wdrożeniu v169) albo wyłącznik RWA_EM_OFF = status „—” z opisem, bez uwagi;
    starszy niż RWE_SWIEZ_MIN = ⚠️, nigdy ❌."""
    if not isinstance(j, dict):
        return None
    em = j.get('issuer')
    if not isinstance(em, dict):
        return (RWE_ETYKIETA, '—', None, None, 'brak danych emitentów w pliku (przed pierwszym odczytem po wdrożeniu v169)')
    if em.get('off'):
        return (RWE_ETYKIETA, '—', None, None, 'wyłączone (RWA_EM_OFF)')
    ts = em.get('at')
    w = wiek_danych(ts, 'ts', 'h', now or NOW) if isinstance(ts, str) else None
    if w is None:
        return (RWE_ETYKIETA, '?', None, None, 'brak czasu odczytu w pliku')
    if w <= RWE_SWIEZ_MIN:
        return (RWE_ETYKIETA, '✅', w, ts, '')
    return (RWE_ETYKIETA, '⚠️', w, ts, f'odczyt starszy niż {RWE_SWIEZ_MIN // 60} h (plik co 3 h) — produkty wg emitentów wracają do „bez bieżącej wyceny”')


def rwe_hd(j):
    """Dzienny zapis danych emitentów z pliku: {dzień: (mln USD w sumach, zbiór produktów)} — tylko poprawne wiersze."""
    em = j.get('issuer') if isinstance(j, dict) else None
    hd = em.get('hd') if isinstance(em, dict) and isinstance(em.get('hd'), dict) else {}
    out = {}
    for d, x in hd.items():
        if (isinstance(d, str) and isinstance(x, list) and len(x) == 2 and isinstance(x[0], (int, float)) and not isinstance(x[0], bool)
                and x[0] >= 0 and isinstance(x[1], list)):
            out[d] = (float(x[0]), frozenset(s for s in x[1] if isinstance(s, str)))
    return out


def rwe_porownanie(j, now=None):
    """Kontrola danych emitentów bez sieci (najwyżej ⚠️): (1) w sumach wg emitentów — ile produktów i ile mld USD; (2) produkty bez bieżących danych
    emitenta (poza sumami) z powodem — ℹ️; (3) wartość wg emitenta vs ostatnio znana źródła v133 poza pasmem RWE_ZAKRES — ℹ️ (różnica zakresu,
    np. STAC z klasą na Solanie, Centrifuge bez tokenów-opakowań — opisane na stronie); (4) produkty liczone poprzedniego dnia wg emitenta, a teraz
    już nie (zapis hd) — ⚠️; (5) ostatni odczyt niepełny (ok False) — ⚠️. Brak pliku albo bloku = None; wyłącznik = opis „wyłączone”.
    → {'status', 'opis', 'uwagi', 'braki', 'zakres', 'wypadly'}."""
    if not isinstance(j, dict) or not isinstance(j.get('issuer'), dict):
        return None
    em = j['issuer']
    Z = {'status': '✅', 'opis': '', 'uwagi': []}
    if em.get('off'):
        Z['opis'] = 'wyłączone (RWA_EM_OFF) — sumy bez danych emitentów'
        return Z
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)  # noqa: E731
    P = em.get('p') if isinstance(em.get('p'), dict) else {}
    used = em.get('used') if isinstance(em.get('used'), dict) else {}
    nm = lambda s: P[s]['name'] if isinstance(P.get(s), dict) and isinstance(P[s].get('name'), str) else s  # noqa: E731
    cz, braki, zakres = [], [], []
    tot = sum(x for x in used.values() if num(x))
    cz.append(f'w sumach wg emitentów: {len(used)} z {len(P)} produktów, {tot / 1e9:.1f} mld USD')
    for s, p in sorted(P.items()):
        if not isinstance(p, dict):
            continue
        st = p.get('stan')   # v175: stan produktu w sumach (pliki od v175); starsze — wg pełnego odczytu
        if st == 'brak':
            braki.append(f'{nm(s)}: nie ma go na liście źródła v133 — nie liczony')
        elif (st == 'poza' if isinstance(st, str) else p.get('full') is not True):
            why = p.get('err') if isinstance(p.get('err'), str) else ('stan emitenta za stary albo brak ceny' if num(p.get('v')) else 'brak wartości')
            braki.append(f'{nm(s)}: {why[:120]}')
        v, r = used.get(s), p.get('ref')
        if num(v) and num(r) and r > 0 and not RWE_ZAKRES[0] <= v / r <= RWE_ZAKRES[1]:
            zakres.append(f'{nm(s)} {v / 1e6:.0f} mln USD vs ostatnio znana {r / 1e6:.0f} mln ({v / r:.2f}×)')
    if zakres:
        cz.append('inny zakres niż ostatnio znana (opisane na stronie): ' + '; '.join(zakres[:4]) + ' ℹ️')
    if braki:
        cz.append('bez bieżących danych emitenta (poza sumami): ' + '; '.join(braki[:4]) + ' ℹ️')
    hd = rwe_hd(j)
    dzis = (em.get('at') or '')[:10]
    wcz = [d for d in sorted(hd) if d < dzis]
    wyp = sorted(s for s in (hd[wcz[-1]][1] if wcz else ()) if s not in used)
    inne = [s for s in wyp if isinstance(P.get(s), dict) and P[s].get('stan') in ('l', 'o')]   # v175: liczony innym źródłem — informacja, nie uwaga
    if inne:
        cz.append('liczone teraz innym źródłem (bieżąca wartość źródła v133 albo odczyt z łańcucha): ' + ', '.join(nm(s) for s in inne) + ' ℹ️')
    wyp = [s for s in wyp if s not in inne]
    if wyp:
        Z['status'] = '⚠️'
        Z['uwagi'].append('tokenizowane aktywa (dane emitentów): po ' + wcz[-1] + ' już nie liczone wg emitenta: ' + ', '.join(nm(s) for s in wyp)
                          + ' — odczyt nieudany, stan za stary albo źródło v133 znów podaje bieżącą wartość (tylko uwaga)')
        cz.append('już nie wg emitenta: ' + ', '.join(nm(s) for s in wyp) + ' ⚠️')
    if em.get('ok') is False:
        Z['status'] = '⚠️'
        nt = [x for x in (em.get('notes') or []) if isinstance(x, str)]
        Z['uwagi'].append('tokenizowane aktywa (dane emitentów): ostatni odczyt niepełny — ' + ('; '.join(x[:160] for x in nt[:2]) if nt else 'brak szczegółów')
                          + ' (poprzednie odczyty z ich stanem; tylko uwaga)')
        cz.append('ostatni odczyt niepełny ⚠️')
    Z['braki'], Z['zakres'], Z['wypadly'] = braki, zakres, wyp
    Z['opis'] = '; '.join(cz)
    return Z


def rwe_kontrola(files, R):
    """Wynik kontroli danych emitentów do raportu i uwag; brak pliku albo bloku = None."""
    Z = rwe_porownanie(files.get('rwa'))
    if Z:
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
    # 1b. v141: lżejsza strona — pliki słowników języków wskazane przez index.html (HTTP 200, skrót = treść); pełna strona = uwaga; najwyżej ⚠️
    try:
        i18n_kontrola(body if (R.get('strona') or {}).get('ok') else None, R)
    except Exception as e:  # noqa
        R['uwagi'].append(f'pliki słowników języków: kontrola nie przeszła ({str(e)[:80]})')
    # 1c. v247: strona w przeglądarce bez okna (Chrome, ekran telefonu) — błędy JavaScriptu na prawdziwych danych; najwyżej ⚠️. Tylko gdy
    # KONTROLA_PRZEGLADARKA=1 (ustawia kontrola.yml): testy wołające kontrola() nie mogą uruchamiać przeglądarki — ona ma własną sieć
    if (R.get('strona') or {}).get('ok') and os.environ.get('KONTROLA_PRZEGLADARKA') == '1':
        try:
            R['przegladarka'] = strona_przegladarka(f'{SITE}/?nc={int(time.time())}')
        except Exception as e:  # noqa
            R['przegladarka'] = {'stan': 'blad', 'brak': f'błąd sprawdzania: {type(e).__name__}'}
        u = przegladarka_uwagi(R['przegladarka'], przegladarka_poprzedni(os.path.join(OUT_DIR, 'historia.json')))   # v248: drugi raz bez strony = uwaga
        if u and R['przegladarka'].get('stan') == 'zawieszona':
            R['przegladarka']['powtorka'] = True
        R['uwagi'] += u
    # 2. plik stanu automatu
    try:
        st, body, ms = get(f'{SITE}/data/meta.json?nc={int(time.time())}')
        m = json.loads(body); files['meta'] = m
        w = wiek_min(m.get('at'))
        nie = sorted(k for k, v in (m.get('ok') or {}).items() if v is False)
        R['meta'] = {'at': m.get('at'), 'wiek_min': w, 'zrodla': len(m.get('ok') or {}), 'bez_odpowiedzi': nie,
                     'errors': [str(x)[:160] for x in (m.get('errors') or [])], 'notes': [str(x)[:160] for x in (m.get('notes') or [])],
                     'czas': m.get('czas') if isinstance(m.get('czas'), dict) else None,   # v185: czas przebiegu automatu
                     'awarie_od': m.get('awarie_od') if isinstance(m.get('awarie_od'), str) else None}   # v211: początek pamięci awarii
        if w is None:
            R['bledy'].append('plik stanu bez czasu przebiegu')
        elif w > 180:
            R['bledy'].append(f'automat nie odświeżył danych od {w // 60} godz. (ostatni przebieg {czas_pl(m.get("at"))})')
        elif w > LIMIT_MIN['meta']:
            R['uwagi'].append(f'ostatni przebieg automatu sprzed {w} min (zwykle co 10 min)')
        if nie:
            R['uwagi'].append('źródła bez odpowiedzi w ostatnim przebiegu: ' + ', '.join(nie))
        for e in (m.get('errors') or []):   # v211: dopisek z pełnej treści (dotąd z obciętej do 160 znaków)
            R['uwagi'].append('błąd zbieracza: ' + str(e)[:160] + awaria_rodzaj(e))   # v207: dopisek — odrzucony klucz / limit planu
        aw = awarie_ocena(m)   # v207: pamięć awarii zbieracza — od kiedy część nie działa, co naprawiło się samo (None = zbieracz sprzed v207)
        if aw is not None:
            R['awarie'] = aw
            R['uwagi'] += aw['uwagi']; R['bledy'] += aw['bledy']
        zu = zuzycie_ocena(m)   # v222: licznik zużycia darmowych planów (None = zbieracz sprzed v222)
        if zu is not None:
            R['zuzycie'] = zu
            R['uwagi'] += zu['uwagi']; R['bledy'] += zu['bledy']
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
            if isinstance(j, dict) and j.get('off') is True:   # v176: plik części wyłączonej celowo (np. insiderzy bez SEC_CONTACT) — stan, nie usterka
                R['pliki'][n]['wylaczone'] = str(j.get('powod') or 'wyłączone')[:160]
            if w is not None and w > LIMIT_MIN.get(n, 24 * 60):
                R['uwagi'].append(f'{n}.json sprzed {w // 60} godz. {w % 60} min (limit {LIMIT_MIN.get(n, 1440) // 60} godz.)')
            if nie:
                R['uwagi'].append(f'{n}.json: części bez odpowiedzi: ' + ', '.join(nie))
        except urllib.error.HTTPError as e:
            R['pliki'][n] = {'http': e.code}
            wyl = wylaczone(files.get('meta')).get(n) if e.code == 404 else None
            if wyl:
                R['pliki'][n]['wylaczone'] = wyl                       # v171: część wyłączona celowo — opis, nie uwaga
            elif n in ('etf', 'trendy', 'oecd', 'rynki'):
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
    # 3c'''. v134: świeżość funduszy USA (data/ici.json) — osobne wiersze tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    for label, st, w, txt, note in ici_swiezosc(files.get('ici')):
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c''. v137: Japonia — kto handluje akcjami na giełdzie: świeżość wg kalendarza publikacji (4. dzień roboczy następnego tygodnia, święta
    # w Japonii) — osobny wiersz tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️, nigdy ❌ ani BŁĄD
    jr = jpx_swiezosc(files.get('jpx'))
    if jr:
        label, st, w, txt, note = jr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    ju = jpx_swieta_uwaga()
    if ju:
        R['uwagi'].append(ju)
    # 3c''''. v162: dzienniki sygnałów TRENDÓW — ostatni dzień z wynikiem (treść pliku, nie jego wiek); osobne wiersze tabeli, najwyżej ⚠️
    for plik, _lab, _kat, _prog in DZ_SPEC:
        dz = dziennik_swiezosc(files.get(plik), plik)
        if dz:
            label, st, w, txt, note = dz
            R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
            if st == '⚠️':
                R['uwagi'].append(f'{label}: ostatni wynik z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
            elif st == '?':
                R['uwagi'].append(f'{label}: {note}')
    # 3c''. v133: tokenizowane aktywa RWA (data/rwa.json) — świeżość listy osobnym wierszem tabeli (lista SWIEZOSC bez zmian); najwyżej ⚠️,
    # nigdy ❌ ani BŁĄD
    rr = rwa_swiezosc(files.get('rwa'))
    if rr:
        label, st, w, txt, note = rr
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c'''. v150: tokenizowane aktywa — odczyt własny z łańcucha (blok onchain w data/rwa.json) — osobny wiersz (lista SWIEZOSC bez zmian);
    # najwyżej ⚠️; brak bloku albo wyłącznik RWA_CHAIN_OFF = „—” bez uwagi
    rc = rwc_swiezosc(files.get('rwa'))
    if rc:
        label, st, w, txt, note = rc
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
        elif st == '?':
            R['uwagi'].append(f'{label}: {note}')
    # 3c''''. v169: tokenizowane aktywa — dane emitentów (blok issuer w data/rwa.json) — osobny wiersz (lista SWIEZOSC bez zmian); najwyżej ⚠️;
    # brak bloku albo wyłącznik RWA_EM_OFF = „—” bez uwagi
    re_ = rwe_swiezosc(files.get('rwa'))
    if re_:
        label, st, w, txt, note = re_
        R['swiezosc'].append({'zrodlo': label, 'status': st, 'wiek_min': w, 'data': txt, 'uwaga': note})
        if st == '⚠️':
            R['uwagi'].append(f'{label}: dane z {txt} — {fmt_wiek(w)} temu ({note})' if txt else f'{label}: {note}')
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
            R['uwagi'].append(f'TGA {d}: Fiscal Data {_zuz_l(a)} vs FRED {_zuz_l(b)} mln USD — różnica {r:.2f}% wobec normy {med2:.2f}% ({opis2})')
    else:
        Z['tga'] = None
    s = stab_porownanie(files.get('krypto'), files.get('cmc'))   # v209: podaż stablecoinów — dwa pliki strony, odchylenie od mediany (najwyżej ⚠️)
    if s:
        if s['roznica_pct'] is not None:
            rows[today]['stab'] = s['roznica_pct']
            st3, med3, n3, opis3 = mediana_ocena(rows, 'stab', s['roznica_pct'], today, STAB_ZOLTE, None)
            s.update(status=st3, mediana_pct=(round(med3, 3) if med3 is not None else None), dni=n3, opis=opis3)
            if st3 == '⚠️':
                R['uwagi'].append(f'podaż stablecoinów: różnica dwóch źródeł dziś {s["roznica_pct"]:+.2f}% wobec normy {med3:+.2f}% ({opis3}) — sprawdzić, czy któreś źródło nie pominęło sieci albo monety')
        Z['stablecoiny'] = s
    if isinstance(files.get('rynki'), dict) and isinstance(files['rynki'].get('ust'), list):   # v209/v211: rentowność 10L USA vs H.15 — wydawca, zapas FRED; brak = informacja
        u, bu = None, []
        for nazwa, url, czytaj in (('Fed', UST_FED, ust_fed_csv), ('FRED', UST_FRED.format(od=(NOW.date() - dt.timedelta(days=UST_OD_DNI)).isoformat()), ust_fred_csv)):
            try:
                st4, body4, _ = get(url, timeout=30)
                F = czytaj(body4.decode('utf-8', 'replace'))
                if not F:
                    raise ValueError('plik bez liczb')
                u = ust_porownanie(files['rynki'], F); u['zrodlo'] = nazwa
                break
            except Exception as e:  # noqa
                bu.append(f'{nazwa}: {str(e)[:80]}')
        if u is not None:
            Z['ust10'] = u
            if u['roznice']:
                R['uwagi'].append('rentowność 10L USA: plik strony vs H.15 różnią się ponad ' + f'{UST_PROG:g} pkt proc.: '
                                  + ', '.join(f'{d}: {a:g} vs {b:g}' for d, a, b, x in u['roznice'][:5]))
        else:
            Z['ust10'] = {'brak': '; '.join(bu)[:200]}
    if isinstance(files.get('stopy'), dict):   # v241–v246: stopy banków centralnych vs ich własne źródła (bez klucza); brak odczytu = informacja
        try:
            Z['stopy'], u = stopy_sprawdz(files['stopy'])
        except Exception as e:  # noqa — v248: błąd bloku stóp nie zabiera całego raportu
            Z['stopy'], u = {'wyniki': [], 'brak': f'błąd kontroli stóp: {type(e).__name__}: {str(e)[:80]}'}, []
        R['uwagi'] += u
    if isinstance(files.get('rynki'), dict) and isinstance(files['rynki'].get('fx'), dict):   # v225: kursy walut vs H.10 (Fed); brak = informacja
        try:
            st5, body5, _ = get(FX_H10, timeout=30)
            H = fx_h10_csv(body5.decode('utf-8', 'replace'))
            if not H:
                raise ValueError('plik bez liczb')
            f = fx_porownanie(files['rynki'], H)
            Z['fx'] = f if f is not None else {'brak': 'brak migawek kursów w pliku strony'}
            R['uwagi'] += fx_uwagi(f)   # v227: przecinki dziesiętne, opis bez „migawki z innego dnia”
        except Exception as e:  # noqa
            Z['fx'] = {'brak': f'H.10: {str(e)[:100]}', 'baza': fx_baza(files['rynki'])}   # v235: ostrzeżenie o walucie bazowej i bez H.10
            R['uwagi'] += fx_uwagi(Z['fx'])
    try:
        zgodnosc_zapisz(zg_path, rows)
    except Exception as e:  # noqa
        R['uwagi'].append(f'zgodnosc.csv: nie zapisano ({str(e)[:80]})')
    Z['indeksy'] = indeksy_ocena((files.get('indeksy') or {}).get('ix'))   # v254: świeżość każdej serii indeksów
    R['uwagi'] += indeksy_uwagi(Z['indeksy'])   # v258: zacięte, z przyszłości, dostawca stoi
    if isinstance((files.get('indeksy') or {}).get('ix'), dict):   # v257/v259: 4 indeksy vs ich wydawcy (serie wydawców z pliku); brak = informacja
        try:
            Z['ix_fred'] = ixf_sprawdz(files['indeksy']['ix'], files['indeksy'].get('wyd'))
        except Exception as e:  # noqa — błąd bloku nie zabiera całego raportu
            Z['ix_fred'] = {'brak': f'błąd porównania indeksów: {type(e).__name__}: {str(e)[:80]}'}
        R['uwagi'] += ixf_uwagi(Z['ix_fred'])
    e = etf_porownanie(files.get('ceny') or {}, files.get('indeksy') or {})
    if e:
        zle = [x for x in e if x[4] is not None and x[4] > ETF_PROG]
        Z['etf'] = {'porownane': len(e), 'roznice': [{'symbol': s, 'data': d, 'a': a, 'b': b, 'roznica_pct': round(r, 3)} for s, d, a, b, r in zle]}
        if zle:
            R['uwagi'].append('ETF (mapa): zamknięcia z dwóch źródeł różnią się > ' + f'{ETF_PROG:g}% dla ' + ', '.join(f'{s} ({d}: {a:g} vs {b:g})' for s, d, a, b, r in zle[:6]))
    else:
        Z['etf'] = None
    w = wieloryby_ocena(os.path.join(ARCH_DIR, 'wieloryby.csv'), zmiany=wh_zmiany(files.get('wieloryby')),
                        hist=(files.get('wieloryby') or {}).get('hist'))   # v249: salda z migawek o północy UTC   # v230: dzień zmiany listy; v174: na tle historii pary i tylko przy migawkach oddalonych o ok. dobę
    if w:
        zle = w['zle']
        Z['wieloryby'] = {'dzien': w['dzien'], 'poprzedni': w['poprzedni'], 'porownane': w['porownane'], 'odstep_h': w['odstep_h'], 'pomin': w['pomin'],
                          'bez_historii': w['bez_historii'], 'pominiete': w.get('pominiete', 0), 'lista': w.get('lista', []), 'polnoc': w.get('polnoc', 0), 'poprzedni_pokaz': w.get('poprzedni_pokaz'),
                          'rozbieznosci': [{'gielda': g, 'aktywo': a, 'zmiana_usd': round(x, 2), 'netto_usd': round(y, 2), 'roznica_usd': round(z, 2), 'mediana_usd': round(m, 2)}
                                           for g, a, x, y, z, m in zle]}
        if zle:
            R['uwagi'].append('wieloryby: zmiana salda ≠ przelewy netto — rozbieżność nietypowa (ponad ' + f'{WH_RAZY:g}× zwykłej dla pary) dla '
                              + ', '.join(f'{g} {a} ({z / 1e6:.0f} mln USD, zwykle {m / 1e6:.0f} mln)' for g, a, x, y, z, m in zle[:6])
                              + ' — sprawdzić skan przelewów tej giełdy')
    else:
        Z['wieloryby'] = None
    wl = wh_listy_ocena(files.get('wieloryby'))   # v218: wiek list portfeli giełd z raportów miesięcznych
    if wl is not None:
        Z['wh_listy'] = wl
        for g, d, n in wl['stare']:
            R['uwagi'].append(f'lista portfeli giełdy {g} z {d} ma {n} dni — portfele dodane przez giełdę od tego czasu nie są liczone; '
                              f'co zrobić: napisz do Claude „odśwież listę portfeli {g} z nowego raportu dowodu rezerw”')
        try:   # v237: nowe raporty dowodu rezerw — automat sam wie, kiedy listę można odświeżyć
            Z['wh_nowe'] = wh_nowe_raporty((files.get('wieloryby') or {}).get('gieldy'))
        except Exception as e:  # noqa
            Z['wh_nowe'] = {'_blad': type(e).__name__}   # v243: wiersz „nie wiadomo”, nie zniknięcie
        for g, o in Z['wh_nowe'].items():
            if isinstance(o, dict) and o.get('nowy') and o.get('lista'):
                R['uwagi'].append(f'nowa lista portfeli giełdy {g} z {o["nowy"]} (raport dowodu rezerw; obecna z {o["od"]}) — co zrobić: napisz do '
                                  f'Claude „odśwież listę portfeli {g} z nowego raportu dowodu rezerw”')
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
    # 3g. v134: fundusze USA — tożsamości sum ostatniego tygodnia w pliku strony (bez sieci) i informacja o poprawkach wydawcy; najwyżej ⚠️
    try:
        Z['ici'] = ici_kontrola(files.get('ici'), R)
    except Exception as e:  # noqa
        Z['ici'] = {'blad': str(e)[:120]}
        R['uwagi'].append(f'fundusze USA: kontrola sum przerwana ({str(e)[:80]})')
    # 3g. v137: Japonia — zagranica w akcjach: giełda (tylko handel na giełdzie) vs MOF (wszystkie akcje i fundusze) — kierunek i korelacja
    # z plików strony, bez zapytań; najwyżej ⚠️ (różne miary, nigdy ❌ ani BŁĄD)
    try:
        Z['jpx'] = jpx_kontrola(files, R)
    except Exception as e:  # noqa
        Z['jpx'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'Japonia — giełda vs MOF: kontrola przerwana ({str(e)[:80]})')
    # 3g. v133: tokenizowane aktywa RWA — własna zmiana 7 dni vs zmiana podana przez źródło, produkty spoza głównej listy, skok sumy dzień do dnia
    # (z pliku strony, bez zapytań; najwyżej ⚠️ — do raportu bez nowej kolumny zgodnosc.csv)
    try:
        Z['rwa'] = rwa_kontrola(files, R)
    except Exception as e:  # noqa
        Z['rwa'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'tokenizowane aktywa: kontrola przerwana ({str(e)[:80]})')
    # 3h. v150: odczyt własny z łańcucha — podaż 24 h, wartość vs ostatnio znana, produkty bez pełnego odczytu (z pliku strony, bez zapytań; najwyżej ⚠️)
    try:
        Z['rwa-lancuch'] = rwc_kontrola(files, R)
    except Exception as e:  # noqa
        Z['rwa-lancuch'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'tokenizowane aktywa (odczyt własny): kontrola przerwana ({str(e)[:80]})')
    # 3i. v169: dane emitentów — produkty w sumach, braki, inny zakres, produkty, które wypadły (z pliku strony, bez zapytań; najwyżej ⚠️)
    try:
        Z['rwa-emitenci'] = rwe_kontrola(files, R)
    except Exception as e:  # noqa
        Z['rwa-emitenci'] = {'status': '?', 'blad': str(e)[:120]}
        R['uwagi'].append(f'tokenizowane aktywa (dane emitentów): kontrola przerwana ({str(e)[:80]})')
    # 4. przebiegi Actions z ostatnich 24 h (API publiczne; token tylko podnosi limit zapytań)
    try:
        hdr = {'Accept': 'application/vnd.github+json'}
        if TOKEN:
            hdr['Authorization'] = 'Bearer ' + TOKEN
        runs, ids, druga = [], set(), None
        for strona in (1, 2):   # v177: lista samego zadania „Strona i dane” (inne zadania — zegar, kontrola — wypychały je z listy 100 po ok. 8–10 h);
            try:
                st, body, ms = get(f'https://api.github.com/repos/{REPO}/actions/workflows/strona.yml/runs?per_page=100&page={strona}', headers=hdr)
                Rr = json.loads(body).get('workflow_runs', []) or []
            except Exception as e:  # noqa — v181: nieczytelna DRUGA strona nie kasuje pierwszej (liczba z pierwszej, dopisek w raporcie)
                if strona == 1:
                    raise
                druga = str(e)[:80] or type(e).__name__; break
            runs += [r for r in Rr if not (isinstance(r, dict) and r.get('id') in ids)]   # druga strona tylko, gdy 100 przebiegów nie pokrywa doby;
            ids.update(r.get('id') for r in Rr if isinstance(r, dict))                  # v181: bez podwójnych (nowy przebieg między stronami przesuwa listę)
            w = wiek_min(Rr[-1].get('run_started_at') or Rr[-1].get('created_at')) if Rr else None
            if len(Rr) < 100 or w is None or w > 24 * 60:
                break
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
        pend = {}   # v235: oczekujące wdrożenia przebiegów „waiting” (najwyżej 3 zapytania; błąd odczytu = jak dotąd, bez rozróżnienia)
        for r in [r for r in runs if isinstance(r, dict) and str(r.get('name', '')).startswith('Strona') and r.get('status') == 'waiting'][:3]:
            try:
                _, b4, _ = get(f'https://api.github.com/repos/{REPO}/actions/runs/{r["id"]}/pending_deployments', headers=hdr)
                pend[r['id']] = json.loads(b4)
            except Exception:  # noqa
                pass
        R['actions'], b, u = przebiegi_ocena(runs, NOW, kroki, pend)
        # v194 (przegląd v190–v192): czas samego zadania budowy (limit 25 min) w 3 najdłuższych udanych przebiegach — całość przebiegu zawiera
        # czekanie na maszyny (w awarii GitHuba fałszywe „blisko limitu”); 3 dodatkowe zapytania, błąd odczytu = bez tej liczby
        bud, t_b = [], time.monotonic()
        dl_b = {r.get('id'): przebieg_min(r) for r in runs if isinstance(r, dict)}
        for rid in budowa_kandydaci(runs, NOW):   # v199: także każdy udany > 20 min; v205: koniec, gdy dłuższej budowy już nie będzie, albo po 90 s
            if bud and (dl_b.get(rid) or 0) <= max(bud):
                break                                    # budowa ≤ cały przebieg, kandydaci malejąco — kolejne nie dadzą dłuższej budowy
            if time.monotonic() - t_b > BUDOWA_BUDZET_S:
                R['actions']['budowa_niepelna'] = True; break
            try:
                _, b3, _ = get(f'https://api.github.com/repos/{REPO}/actions/runs/{rid}/jobs', headers=hdr)
                m3 = zadanie_min(json.loads(b3).get('jobs', []), 'zbuduj')
                if m3 is not None:
                    bud.append(m3)
            except Exception:  # noqa
                pass
        if bud:
            R['actions']['budowa_max_min'] = round(max(bud), 1)
        if druga:
            R['actions']['lista_niepelna'] = druga
        R['bledy'] += b
        R['uwagi'] += u
    except Exception as e:  # noqa
        R['actions'] = {'blad': str(e)[:160]}
        R['uwagi'].append('nie udało się odczytać listy przebiegów Actions: ' + str(e)[:100])
    # 5. v115: historia — błędy zbieracza w 3 kolejnych przebiegach kontroli = czerwone
    n_err = len(R['meta'].get('errors') or []) if isinstance(R['meta'], dict) else 0
    hist = historia(os.path.join(OUT_DIR, 'historia.json'), {'at': R['at'], 'bledy_zbieracza': n_err, 'uwagi': len(R['uwagi']), 'bledy': len(R['bledy']),
                                                           'przegl': (R.get('przegladarka') or {}).get('stan')})   # v248: stan przeglądarki
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
    if R['wynik'] == 'BŁĄD' and R.get('bledy'):   # v212: zaraz pod werdyktem — co zrobić przy każdym rodzaju błędu (nagłówek i „Wynik:” bez zmian)
        L[6:6] = ['**Co zrobić:**'] + ['- ' + h for h in co_zrobic(R['bledy'])] + ['']
    cz = m.get('czas') if isinstance(m.get('czas'), dict) else None   # v185: czas tego przebiegu i najdłuższe części
    if cz and isinstance(cz.get('s'), (int, float)):
        top = [x for x in (cz.get('top') or []) if isinstance(x, list) and len(x) == 2][:3]
        L.append(f'- Czas tego przebiegu automatu: {int(cz["s"]) // 60} min {int(cz["s"]) % 60} s'
                 + ('; najdłużej: ' + ', '.join(f'{n} {s} s' for n, s in top) if top else '') + '.')
    s18 = (R.get('strona') or {}).get('i18n')   # v141: lżejsza strona — pliki słowników języków
    if s18:
        L.append('- Słowniki języków de–ja (osobne pliki strony): ' + s18.get('opis', '—') + '.')
    pg = R.get('przegladarka')   # v247: strona w przeglądarce bez okna
    if isinstance(pg, dict):
        L.append(przegladarka_wiersz(pg))
    a = R.get('actions') or {}
    if 'przebiegi_24h' in a:
        L.append(f'- Przebiegi Actions w 24 h: {a["przebiegi_24h"]} ({", ".join(f"{k}: {v}" for k, v in a["wg_wyniku"].items()) or "—"}).'
                 + (' Uwaga: lista niepełna — druga strona listy nieczytelna, liczba z pierwszych 100.' if a.get('lista_niepelna') else ''))
        if isinstance(a.get('najdluzszy_min'), (int, float)):   # v190: zapas do limitu zadania budowy (25 min)
            nd, bm = a['najdluzszy_min'], a.get('budowa_max_min')
            if isinstance(bm, (int, float)) and not isinstance(bm, bool):   # v194: ostrzeżenie z czasu samego zadania budowy (bez czekania na maszyny)
                L.append(f'- Najdłuższy udany przebieg w 24 h: {nd:.1f} min'.replace('.', ',') + ' (od startu do końca, z czekaniem na maszyny); samo zadanie budowy najdłużej '
                         + f'{bm:.1f} min'.replace('.', ',') + ' z limitu 25 min' + (' ⚠️ blisko limitu.' if bm > 20 else '.'))
            else:
                L.append(f'- Najdłuższy udany przebieg w 24 h: {nd:.1f} min'.replace('.', ',') + ' (od startu do końca, z czekaniem na maszyny; limit zadania budowy 25 min)'
                         + (' ⚠️ blisko limitu.' if nd > 20 else '.'))
        if a.get('porazki'):   # v124.1: każda porażka z godziną i krokiem; czy automat już działa
            L.append('- Nieudane przebiegi (24 h): ' + '; '.join(czas_pl(p['at']) + (f' — {p["krok"]}' if p.get('krok') else '') for p in a['porazki'])
                     + (f'. Od ostatniej porażki {pl_udane(a["udane_po_porazce"])} z rzędu.' if a.get('udane_po_porazce') else '. Ostatni zakończony przebieg nieudany.'))
    L.append('- Pliki danych (wiek): ' + ', '.join(f'{n} {("%dh%02d" % divmod(p["wiek_min"], 60)) if p.get("wiek_min") is not None and not p.get("wylaczone") else ("wyłączone" if p.get("wylaczone") else "HTTP " + str(p.get("http", "?")))}'
                                             for n, p in (R.get('pliki') or {}).items()) + '.')
    aw = R.get('awarie') if isinstance(R.get('awarie'), dict) else None   # v207: pamięć awarii części automatu
    if aw is not None:
        if not aw.get('trwa') and not aw.get('naprawione') and not aw.get('zniknely'):
            ao, ra = _aw_t(m.get('awarie_od')), _aw_t(R.get('at'))   # v211: „brak” tylko za ostatnią dobę; pamięć młodsza niż doba — od kiedy
            L.append('- Awarie części automatu (24 h): brak' + (f' (pamięć od {czas_pl(m["awarie_od"])})' if ao and ra and (ra - ao).total_seconds() < AW_INFO_H * 3600 else '') + '.')
        if aw.get('trwa'):
            L.append('- Awarie części automatu — trwają: ' + '; '.join(
                f'{x["czesc"]} od {czas_pl(x["od"])} ({_aw_h(x["h"])}, nieudanych przebiegów: {x["n"]}) '
                + ('ℹ️ (' + AW_BEZ_BLEDU.get(x['czesc'], '') + ')' if x.get('bez') else '❌' if x['h'] >= AW_BLAD_H else '⚠️' if x['h'] >= AW_UWAGA_H else 'ℹ️')
                for x in aw['trwa']) + '.')
        if aw.get('naprawione'):
            L.append('- Naprawiły się same (24 h): ' + '; '.join(
                f'{x["czesc"]} {czas_pl(x["od"])} – {czas_pl(x["do"])} ({_aw_h(x["h"])}, nieudanych przebiegów: {x["n"]}) ℹ️' for x in aw['naprawione']) + '.')
        if aw.get('zniknely'):   # v211: seria zamknięta, bo część nie pojawia się w przebiegach (wyłączona albo zmieniona) — nie awaria, nie naprawa
            L.append('- Zniknęły z przebiegów (24 h; część wyłączona albo zmieniona — nie awaria): ' + '; '.join(
                f'{x["czesc"]} — ostatnia nieudana próba {czas_pl(x["ost"])} (nieudanych przebiegów: {x["n"]}) ℹ️' for x in aw['zniknely']) + '.')
    zu = R.get('zuzycie') if isinstance(R.get('zuzycie'), dict) else None   # v222: zużycie darmowych planów z limitem
    if zu and zu.get('plany'):
        L.append('- Zużycie darmowych planów (licznik automatu — dolna granica): ' + '; '.join(f'{p["tekst"]} {p["znak"]}' for p in zu['plany']) + '.')
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
            L.append(f'- Kapitalizacja krypto, dwa źródła: różnica dziś {dz}{_norma(k.get("mediana_pct"), k.get("dni", 0))} — {k.get("status", "?")} {k.get("opis", "")}.')
        c = Z.get('ceny') or {}
        for key, nm in (('bitcoin', 'BTC'), ('ethereum', 'ETH')):
            if key in c:
                r = c[key].get('roznica_pct')
                L.append(f'- Cena {nm}: {_zuz_l(c[key]["a"])} vs {_zuz_l(c[key]["b"])} USD — różnica {r:.2f}% {"⚠️" if r > CENA_PROG else "✅"}.' if r is not None else f'- Cena {nm}: brak porównania.')
        t = Z.get('tga')
        if t:
            r = t.get('roznica_pct')
            L.append(f'- TGA {t["data"]}: Fiscal Data {_zuz_l(t["fiscal_mln"])} vs FRED {_zuz_l(t["fred_mln"])} mln USD — różnica {r:.2f}%{_norma(t.get("mediana_pct"), t.get("dni", 0))} — {t.get("status", "?")} {t.get("opis", "")}.'
                     if r is not None else f'- TGA {t["data"]}: brak porównania.')
        else:
            L.append('- TGA: brak wspólnej daty Fiscal Data i FRED.')
        s = Z.get('stablecoiny')   # v209
        if s:
            if s.get('roznica_pct') is None:
                L.append(f'- Podaż stablecoinów, dwa źródła: pliki pobrane w odstępie {s.get("odstep_h", "—")} h — bez porównania ℹ️.')
            else:
                L.append(f'- Podaż stablecoinów, dwa źródła: {s["a"] / 1e9:.1f} vs {s["b"] / 1e9:.1f} mld USD — różnica dziś {s["roznica_pct"]:+.2f}%'
                         f'{_norma(s.get("mediana_pct"), s.get("dni", 0), "{:+.2f}%")} — {s.get("status", "?")} {s.get("opis", "")}.')
        u = Z.get('ust10')   # v209
        if u:
            if u.get('brak'):
                L.append(f'- Rentowność 10L USA (Skarb USA vs H.15): brak odczytu H.15 ({u["brak"]}) ℹ️.')
            elif not u.get('porownane'):
                L.append('- Rentowność 10L USA (Skarb USA vs H.15): brak wspólnych dat ℹ️.')
            else:
                L.append(f'- Rentowność 10L USA (Skarb USA vs H.15{" — " + u["zrodlo"] if u.get("zrodlo") else ""}, te same dni): porównane {u["porownane"]} dat (do {u["do"]}), różnice > {UST_PROG:g} pkt proc.: '
                         f'{len(u["roznice"])} ' + ('⚠️ — ' + ', '.join(f'{d}: {a:g} vs {b:g}' for d, a, b, x in u['roznice'][:5]) + '.' if u['roznice'] else '✅.'))
        sp = Z.get('stopy')   # v241
        if sp:
            try:
                L.append(stopy_wiersz(sp))
            except Exception as e:  # noqa — v248
                L.append(f'- Stopy banków centralnych: błąd wiersza raportu ({type(e).__name__}) ℹ️.')
        f = Z.get('fx')   # v225: kursy walut vs H.10
        if f:
            if f.get('brak'):
                L.append(f'- Kursy walut (plik strony vs H.10 Fed): brak porównania ({f["brak"]}) ℹ️'
                         + ('; migawki z walutą bazową inną niż USD: ' + ', '.join(f'{k} ({b})' for k, b in f['baza']) + ' ⚠️.' if f.get('baza') else '.'))   # v235
            elif not f.get('daty') and f.get('baza'):   # v233: same migawki z inną bazą — ⚠️ z powodem (dotąd „brak wspólnych dat”)
                L.append('- Kursy walut (plik strony vs H.10 Fed): migawki z walutą bazową inną niż USD ('
                         + ', '.join(f'{k} ({b})' for k, b in f['baza']) + ') — bez porównania ⚠️.')
            elif not f.get('daty'):
                L.append('- Kursy walut (plik strony vs H.10 Fed): brak wspólnych dat (H.10 wychodzi raz w tygodniu) ℹ️.')
            else:
                L.append('- Kursy walut (strona: kurs EBC; H.10: Fed, Nowy Jork; te same dni): ' + '; '.join(
                    f'{d} — {n} walut, mediana różnicy {m:.2f}%, najwięcej {c} {x:+.2f}%'.replace('.', ',') for d, n, m, c, x in f['daty'])
                    + ('; migawki z inną walutą bazową: ' + ', '.join(f'{k} ({b})' for k, b in f['baza']) if f.get('baza') else '')   # v233
                    + (' ⚠️.' if f['zle'] or f['med_zle'] or f.get('baza') else ' ✅.'))
        L.append(indeksy_wiersz(Z.get('indeksy')))   # v254
        w = ixf_wiersz(Z.get('ix_fred'))   # v257
        if w:
            L.append(w)
        e = Z.get('etf')
        if e:
            L.append(f'- ETF mapy (dwa źródła, ta sama data): porównane {e["porownane"]} symboli, różnice > {ETF_PROG:g}%: {len(e["roznice"])} {"⚠️" if e["roznice"] else "✅"}' + (' — ' + ', '.join(x["symbol"] for x in e["roznice"][:6]) if e["roznice"] else '') + '.')
        else:
            L.append('- ETF mapy: brak wspólnej daty zamknięć w dwóch źródłach.')
        w = Z.get('wieloryby')
        if w and w.get('pomin'):   # v174: migawki nie o dobę — bez porównania (informacja)
            L.append(f'- Wieloryby {w["dzien"]} vs {w.get("poprzedni_pokaz") or w["poprzedni"]}: {w["pomin"]} ℹ️.')
        elif w:
            L.append(f'- Wieloryby {w["dzien"]} vs {w.get("poprzedni_pokaz") or w["poprzedni"]}: {w["porownane"]} par giełda/aktywo'   # v250
                     + (f' (salda z migawek o północy UTC: {w["polnoc"]})' if w.get('polnoc') else '')   # v249
                     + f', rozbieżności nietypowe (> 5% i > {WH_RAZY:g}× zwykłej): '
                     f'{len(w["rozbieznosci"])} {"⚠️" if w["rozbieznosci"] else "✅"}'
                     + (' — ' + ', '.join(f'{x["gielda"]} {x["aktywo"]}' for x in w["rozbieznosci"][:6]) if w['rozbieznosci'] else '')
                     + (f' (bez historii: {w["bez_historii"]})' if w.get('bez_historii') else '')
                     + (f' (pominięte pary z innym odstępem migawek: {w["pominiete"]})' if w.get('pominiete') else '')
                     + (f' (nowa lista portfeli — bez porównania: {", ".join(w["lista"])})' if w.get('lista') else '') + '.')
        else:
            L.append('- Wieloryby: archiwum ma mniej niż dwa dni — porównanie od jutra.')
        wl = Z.get('wh_listy')   # v218: wiek list portfeli giełd z raportów miesięcznych
        if wl and wl.get('wszystkie'):
            L.append('- Listy portfeli giełd z raportów miesięcznych (wiek): ' + ', '.join(f'{g} {n} dni' + (' ⚠️' if n > WH_LISTY_DNI else '') for g, d, n in wl['wszystkie'])
                     + (' ✅.' if not wl['stare'] else '.'))
        if Z.get('wh_nowe'):   # v237
            L.append(wh_nowe_wiersz(Z['wh_nowe']))
        wy = Z.get('wycena')   # v132: MVRV BTC z dwóch źródeł — tylko różnice procentowe i daty; brak = „—”
        if wy:
            dz = f'{wy["roznica_pct"]:+.2f}% ({wy["dzien"]})' if wy.get('roznica_pct') is not None else '—'
            L.append(f'- MVRV BTC, dwa źródła: różnica najnowszego wspólnego dnia {dz}{_norma(wy.get("mediana_pct"), wy.get("n", 0), "{:+.2f}%")} — {wy.get("status", "?")} {wy.get("opis", "")}.')
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
        fz = Z.get('ici')   # v134: fundusze USA — tożsamości sum ostatniego tygodnia i poprawki wydawcy (informacja, bez koloru); brak pliku = bez linii
        if fz:
            cz = [f'{ICI_KROTKO.get(k, k)} {s["tydzien"] or "—"}: {s["status"]} {s["opis"]}' for k, s in (fz.get('sumy') or {}).items()]
            L.append('- Fundusze USA — sumy ostatniego tygodnia w pliku strony (tolerancja 3/5 mln USD): '
                     + (' · '.join(cz) if cz else (f'? kontrola przerwana ({fz["blad"]})' if fz.get('blad') else '—')) + '.'
                     + (' Poprawki wydawcy (informacja): ' + '; '.join(fz['rev']) + '.' if fz.get('rev') else ''))
        jz = Z.get('jpx')   # v137: Japonia — giełda vs MOF (kierunek i korelacja netto zagranicy); brak pliku = bez linii
        if jz:
            L.append('- Japonia: giełda (tylko handel akcjami na giełdzie) vs MOF (wszystkie akcje i fundusze, także poza giełdą), zagranica netto: '
                     + (jz.get('opis') or (f'? kontrola przerwana ({jz["blad"]})' if jz.get('blad') else '—')) + '.'
                     + (f' Korekty źródła z 7 dni: {len(jz["korekty"])} (sprawdzić ręcznie).' if jz.get('korekty') else ''))
        rz = Z.get('rwa')   # v133: tokenizowane aktywa — zmiana 7 dni (własna vs źródło), produkty spoza listy, skoki sumy; brak pliku = bez linii
        if rz:
            L.append('- Tokenizowane aktywa (RWA): ' + (rz.get('opis') or (f'? kontrola przerwana ({rz["blad"]})' if rz.get('blad') else '—')) + '.')
        oz = Z.get('rwa-lancuch')   # v150: odczyt własny z łańcucha — podaż 24 h, wartość vs ostatnio znana, braki; brak bloku = bez linii
        if oz:
            L.append('- Tokenizowane aktywa — odczyt własny z łańcucha: ' + (oz.get('opis') or (f'? kontrola przerwana ({oz["blad"]})' if oz.get('blad') else '—')) + '.')
        ez = Z.get('rwa-emitenci')   # v169: dane emitentów — produkty w sumach, braki, inny zakres; brak bloku = bez linii
        if ez:
            L.append('- Tokenizowane aktywa — dane emitentów: ' + (ez.get('opis') or (f'? kontrola przerwana ({ez["blad"]})' if ez.get('blad') else '—')) + '.')
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
