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
PLIKI = ['meta', 'etf', 'trendy', 'oecd', 'rynki', 'dzwignia', 'wieloryby', 'energia', 'usa-makro', 'bilans-usa', 'krypto', 'krypto-top10', 'cmc', 'instytucje', 'tic', 'cm', 'fred', 'cftc', 'ceny', 'indeksy', 'ceny-krypto', 'snb', 'ici', 'fed', 'lancuch', 'wycena', 'insider', 'nastroj', 'stres', 'aukcje', 'swiat-dzien', 'swiat-dziennik', 'premie', 'dolar', 'jpx', 'rwa', 'krypto-dzien', 'krypto-dziennik']
LIMIT_MIN = {'meta': 90, 'etf': 180, 'trendy': 180, 'oecd': 24 * 60, 'rynki': 180, 'dzwignia': 180, 'wieloryby': 90, 'energia': 24 * 60,
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
AW_BEZ_BLEDU = {   # v211: części, w których „brak” znaczy też „czeka na publikację” albo dodatek bez czerwieni — seria tylko informacją (wiek danych ocenia wiersz świeżości)
    'ici': 'fundusze USA — spóźniona publikacja to nie awaria (v134)', 'jpx': 'Japonia — tydzień czeka na publikację giełdy',
    'snb': 'Szwajcaria — tydzień czeka na publikację banku', 'wycena_bg': 'dodatek SOPR — limit planu źródła (v132)'}


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


def wieloryby_ocena(path):
    """v174: zgodność sald i przepływów wielorybów na tle historii. Przepływy to tylko przelewy ≥ 1 mln USD w oknie 24 h, a migawki sald dzieli
    tyle, ile minęło między zapisami archiwum (05.10: od 7,7 do 28 h) — rozbieżność jest normalna. Uwaga tylko, gdy migawki pary dzieli ok. doba
    (WH_DOBA_BLOKI) i jej rozbieżność przekracza zwykły próg (WH_PROG %, WH_MIN_USD) ORAZ WH_RAZY × medianę jej rozbieżności z co najmniej
    WH_HIST_MIN wcześniejszych porównywalnych dni. v175: odstęp liczony dla KAŻDEJ pary z jej własnych bloków — para z innym odstępem pominięta
    (pole pominiete), reszta porównana; żadnej pary o dobę = bez porównania (powód w 'pomin'). Mniej niż dwa dni archiwum = None.
    → {'dzien', 'poprzedni', 'porownane', 'pominiete', 'odstep_h' (mediana par), 'pomin', 'zle': [(giełda, aktywo, zmiana, netto, rozb., mediana)],
    'bez_historii'}."""
    by = _wh_csv(path)
    if not by:
        return None
    days = sorted(by)
    if len(days) < 2:
        return None
    d, p = days[-1], days[-2]
    doba = lambda sp: sp is not None and WH_DOBA_BLOKI[0] <= sp <= WH_DOBA_BLOKI[1]  # noqa: E731
    dzis = _wh_rozb(by[p], by[d])
    S = sorted(x[3] for x in dzis.values() if x[3] is not None)
    out = {'dzien': d, 'poprzedni': p, 'porownane': sum(1 for x in dzis.values() if doba(x[3])),
           'pominiete': sum(1 for x in dzis.values() if not doba(x[3])),
           'odstep_h': round(S[len(S) // 2] * 12 / 3600, 1) if S else None, 'pomin': None, 'zle': [], 'bez_historii': 0}
    if not out['porownane']:
        out['pomin'] = (f"odstęp migawek {out['odstep_h']:.1f} h — porównanie z przepływami 24 h tylko przy ok. dobie" if out['odstep_h'] is not None
                        else 'brak numeru bloku migawki — bez porównania')
        return out
    hist = {}
    for a, b in zip(days[:-2], days[1:-1]):
        for k, (_dl, _n, r, sp) in _wh_rozb(by[a], by[b]).items():
            if doba(sp):
                hist.setdefault(k, []).append(r)
    for k, (delta, net, roz, sp) in sorted(dzis.items()):
        if not doba(sp) or not (roz > WH_MIN_USD and roz > WH_PROG / 100 * max(abs(delta), abs(net), WH_MIN_USD)):
            continue
        h = sorted(hist.get(k, []))
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
            bledy.append(f'automat nie działa: {pl_przebiegi(len(por))} w 24 h, ostatnie {z_rzedu} z rzędu — strona nie odświeża danych ({lista})')
        elif z_rzedu == 1:
            uwagi.append(f'ostatni przebieg automatu nieudany ({lista}) — kolejny za ok. 10 min; dwa nieudane z rzędu = błąd')
        else:
            uwagi.append(f'{pl_przebiegi(len(por))} automatu w 24 h — już naprawione: od ostatniej porażki {pl_udane(udane_po)} z rzędu ({lista})')
    if len(ost) < 20:
        uwagi.append(f'tylko {len(ost)} przebiegów w 24 h (harmonogram co 10 min ≈ 144; GitHub bywa opóźniony)')
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
            R['uwagi'].append(f'TGA {d}: Fiscal Data {a:,.0f} vs FRED {b:,.0f} mln USD — różnica {r:.2f}% wobec normy {med2:.2f}% ({opis2})')
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
    w = wieloryby_ocena(os.path.join(ARCH_DIR, 'wieloryby.csv'))   # v174: na tle historii pary i tylko przy migawkach oddalonych o ok. dobę
    if w:
        zle = w['zle']
        Z['wieloryby'] = {'dzien': w['dzien'], 'poprzedni': w['poprzedni'], 'porownane': w['porownane'], 'odstep_h': w['odstep_h'], 'pomin': w['pomin'],
                          'bez_historii': w['bez_historii'], 'pominiete': w.get('pominiete', 0),
                          'rozbieznosci': [{'gielda': g, 'aktywo': a, 'zmiana_usd': round(x, 2), 'netto_usd': round(y, 2), 'roznica_usd': round(z, 2), 'mediana_usd': round(m, 2)}
                                           for g, a, x, y, z, m in zle]}
        if zle:
            R['uwagi'].append('wieloryby: zmiana salda ≠ przelewy netto — rozbieżność nietypowa (ponad ' + f'{WH_RAZY:g}× zwykłej dla pary) dla '
                              + ', '.join(f'{g} {a} ({z / 1e6:.0f} mln USD, zwykle {m / 1e6:.0f} mln)' for g, a, x, y, z, m in zle[:6])
                              + ' — sprawdzić skan przelewów tej giełdy')
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
        R['actions'], b, u = przebiegi_ocena(runs, NOW, kroki)
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
    cz = m.get('czas') if isinstance(m.get('czas'), dict) else None   # v185: czas tego przebiegu i najdłuższe części
    if cz and isinstance(cz.get('s'), (int, float)):
        top = [x for x in (cz.get('top') or []) if isinstance(x, list) and len(x) == 2][:3]
        L.append(f'- Czas tego przebiegu automatu: {int(cz["s"]) // 60} min {int(cz["s"]) % 60} s'
                 + ('; najdłużej: ' + ', '.join(f'{n} {s} s' for n, s in top) if top else '') + '.')
    s18 = (R.get('strona') or {}).get('i18n')   # v141: lżejsza strona — pliki słowników języków
    if s18:
        L.append('- Słowniki języków de–ja (osobne pliki strony): ' + s18.get('opis', '—') + '.')
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
        s = Z.get('stablecoiny')   # v209
        if s:
            if s.get('roznica_pct') is None:
                L.append(f'- Podaż stablecoinów, dwa źródła: pliki pobrane w odstępie {s.get("odstep_h", "—")} h — bez porównania ℹ️.')
            else:
                md3 = f'{s["mediana_pct"]:+.2f}%' if s.get('mediana_pct') is not None else '—'
                L.append(f'- Podaż stablecoinów, dwa źródła: {s["a"] / 1e9:.1f} vs {s["b"] / 1e9:.1f} mld USD — różnica dziś {s["roznica_pct"]:+.2f}%, '
                         f'norma (mediana {s.get("dni", 0)} dni) {md3} — {s.get("status", "?")} {s.get("opis", "")}.')
        u = Z.get('ust10')   # v209
        if u:
            if u.get('brak'):
                L.append(f'- Rentowność 10L USA (Skarb USA vs H.15): brak odczytu H.15 ({u["brak"]}) ℹ️.')
            elif not u.get('porownane'):
                L.append('- Rentowność 10L USA (Skarb USA vs H.15): brak wspólnych dat ℹ️.')
            else:
                L.append(f'- Rentowność 10L USA (Skarb USA vs H.15{" — " + u["zrodlo"] if u.get("zrodlo") else ""}, te same dni): porównane {u["porownane"]} dat (do {u["do"]}), różnice > {UST_PROG:g} pkt proc.: '
                         f'{len(u["roznice"])} ' + ('⚠️ — ' + ', '.join(f'{d}: {a:g} vs {b:g}' for d, a, b, x in u['roznice'][:5]) + '.' if u['roznice'] else '✅.'))
        e = Z.get('etf')
        if e:
            L.append(f'- ETF mapy (dwa źródła, ta sama data): porównane {e["porownane"]} symboli, różnice > {ETF_PROG:g}%: {len(e["roznice"])} {"⚠️" if e["roznice"] else "✅"}' + (' — ' + ', '.join(x["symbol"] for x in e["roznice"][:6]) if e["roznice"] else '') + '.')
        else:
            L.append('- ETF mapy: brak wspólnej daty zamknięć w dwóch źródłach.')
        w = Z.get('wieloryby')
        if w and w.get('pomin'):   # v174: migawki nie o dobę — bez porównania (informacja)
            L.append(f'- Wieloryby {w["dzien"]} vs {w["poprzedni"]}: {w["pomin"]} ℹ️.')
        elif w:
            L.append(f'- Wieloryby {w["dzien"]} vs {w["poprzedni"]}: {w["porownane"]} par giełda/aktywo, rozbieżności nietypowe (> 5% i > {WH_RAZY:g}× zwykłej): '
                     f'{len(w["rozbieznosci"])} {"⚠️" if w["rozbieznosci"] else "✅"}'
                     + (' — ' + ', '.join(f'{x["gielda"]} {x["aktywo"]}' for x in w["rozbieznosci"][:6]) if w['rozbieznosci'] else '')
                     + (f' (bez historii: {w["bez_historii"]})' if w.get('bez_historii') else '')
                     + (f' (pominięte pary z innym odstępem migawek: {w["pominiete"]})' if w.get('pominiete') else '') + '.')
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
