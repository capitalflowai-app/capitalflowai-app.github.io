/* CF-SW v351 (F4Z4) — własny Service Worker strony CapitalFlowAI.
   CEL: szybsze powroty (czcionki, obrazki, skrypt licznika z pamięci przeglądarki) BEZ pogorszenia świeżości danych.

   ZASADY
   1) Strona (HTML) i pliki data/*.json: ZAWSZE najpierw z sieci. Żądanie przechodzi bez zmian (nagłówki, tryb pamięci, adres z ?t=…),
      więc świeżość jest taka sama jak bez Service Workera. Kopia z pamięci tylko wtedy, gdy sieć w ogóle nie odpowiada (błąd połączenia);
      wtedy strona pokazuje pasek „zapisana kopia z <data>” (wiek danych jest podany uczciwie). Odpowiedź serwera z błędem HTTP
      (404, 5xx) NIE jest zastępowana kopią. Do pamięci trafiają tylko odpowiedzi 200 o właściwym typie (HTML / JSON).
   2) fonts/, img/ i count.js: z pamięci od razu; w tle odświeżane, gdy kopia jest starsza niż godzina (stale-while-revalidate).
   3) Obce domeny (źródła danych, licznik odwiedzin) i wszystko spoza listy powyżej (np. archiwum/, kontrola/, robots.txt, ten plik):
      NIE przechwytywane — przeglądarka robi z nimi to, co zrobiłaby bez Service Workera. Service Worker sam nie pyta obcych domen.
   4) Wersja wydania: publikacja (strona.yml) podstawia pod znacznik wydania skrót zawartości złożonej strony. Pamięć nazywa się
      „cf-<skrót>”: nowe wydanie = nowy Service Worker = nowa pamięć; stare pamięci „cf-*” są kasowane przy aktywacji
      (cudzych pamięci nie ruszamy). Bez podstawienia (kopia robocza) pamięć nazywa się „cf-dev”.

   WYŁĄCZNIKI AWARYJNE
   a) U jednego widza: otwórz stronę z dopiskiem ?sw=off (np. https://…/?sw=off). Strona wyrejestruje Service Workera, skasuje jego pamięć
      i zapamięta wybór w przeglądarce (klucz cf-sw-off) — odtąd nie rejestruje go więcej. Powrót: ?sw=on.
   b) Dla wszystkich: zmień poniżej WYLACZONY na true i opublikuj. Przeglądarki sprawdzają ten plik przy każdym wejściu na stronę
      (rejestracja z updateViaCache:'none'); wyłączony Service Worker nie przechwytuje niczego, kasuje wszystkie pamięci „cf-*”
      i sam się wyrejestrowuje. */
'use strict';
const WYDANIE = '__WYDANIE__';
const WYLACZONY = false;
const PREFIKS = 'cf-';
const NAZWA = PREFIKS + (/^[0-9a-f]{8,64}$/.test(WYDANIE) ? WYDANIE : 'dev');
const ODSWIEZ_STATYKI_MS = 60 * 60 * 1000;
const ZAKRES = new URL(self.registration.scope);
const KORZEN = ZAKRES.pathname;
const KLUCZ_STRONY = ZAKRES.origin + KORZEN + 'index.html';
const KLUCZ_STAN = ZAKRES.origin + KORZEN + '__stan';

/* Rodzaj żądania: ['strona'|'dane'|'statyk', klucz w pamięci] albo null (nie przechwytujemy). Klucz bez ?zapytania (?t=… zmienia się co minutę). */
function rodzaj(url) {
  if (url.origin !== ZAKRES.origin || url.pathname.indexOf(KORZEN) !== 0) return null;
  const w = url.pathname.slice(KORZEN.length);
  if (w === '' || w === 'index.html') return ['strona', KLUCZ_STRONY];
  if (/^data\/(?:[A-Za-z0-9_-]+\/)?[A-Za-z0-9_.-]+\.json$/.test(w)) return ['dane', url.origin + url.pathname];
  if (/^(?:fonts|img)\/[A-Za-z0-9_.\/-]+$/.test(w) || w === 'count.js') return ['statyk', url.origin + url.pathname];
  return null;
}

/* Czy odpowiedź nadaje się do zapisu: 200 bez przekierowania, właściwy typ (strona poczekalni z hotelu zwraca 200 i HTML zamiast JSON). */
function nadaje(res, rod) {
  if (!res || res.status !== 200 || res.redirected || res.type === 'opaque') return false;
  const ct = String(res.headers.get('content-type') || '').toLowerCase();
  if (rod === 'strona') return ct.indexOf('text/html') >= 0;
  if (rod === 'dane') return ct.indexOf('json') >= 0;
  return ct.indexOf('text/html') < 0;
}

/* Zapis kopii z godziną zapisu (nagłówek x-cf-zapisano). Nagłówków kodowania i długości nie przenosimy: treść jest już rozpakowana. */
async function zapisz(klucz, res) {
  try {
    const h = new Headers(res.headers);
    h.delete('content-encoding'); h.delete('content-length');
    h.set('x-cf-zapisano', new Date().toISOString());
    const kopia = new Response(await res.blob(), { status: res.status, statusText: res.statusText, headers: h });
    const c = await caches.open(NAZWA);
    await c.put(klucz, kopia);
  } catch (_) { /* brak miejsca albo przerwane pobieranie — bez zapisu, strona działa jak dotąd */ }
}

async function czytajStan(c) {
  try { const r = await c.match(KLUCZ_STAN); return r ? await r.json() : null; } catch (_) { return null; }
}
async function wyczyscStan() {
  try { const c = await caches.open(NAZWA); await c.delete(KLUCZ_STAN); } catch (_) { /* nic */ }
}
/* Zapamiętuje, że strona dostała kopię z pamięci (najstarszą datę z sesji) i powiadamia otwarte karty. */
async function zanotuj(z) {
  try {
    const c = await caches.open(NAZWA);
    let data = z.headers.get('x-cf-zapisano') || '';
    const stary = await czytajStan(c);
    if (stary && stary.data && (!data || Date.parse(stary.data) < Date.parse(data))) data = stary.data;
    await c.put(KLUCZ_STAN, new Response(JSON.stringify({ data }), { headers: { 'content-type': 'application/json' } }));
    const karty = await self.clients.matchAll({ includeUncontrolled: true });
    for (const k of karty) k.postMessage({ typ: 'z-pamieci', data });
  } catch (_) { /* nic */ }
}

async function siecNajpierw(e, req, rod, klucz) {
  let res;
  try { res = await fetch(req); }
  catch (blad) {
    if (blad && blad.name === 'AbortError') throw blad;   // przerwane przez stronę (limit czasu) — to nie brak sieci
    const c = await caches.open(NAZWA);
    const z = await c.match(klucz);
    if (!z) throw blad;                                   // brak kopii: błąd sieci jak bez Service Workera (strona pokaże „—”)
    e.waitUntil(zanotuj(z));
    return z;
  }
  if (nadaje(res, rod)) e.waitUntil(zapisz(klucz, res.clone()).then(() => (rod === 'strona' ? wyczyscStan() : null)));
  return res;
}

async function statyk(e, req, klucz) {
  const c = await caches.open(NAZWA);
  const z = await c.match(klucz);
  const pobierz = async () => {
    const res = await fetch(req);
    if (nadaje(res, 'statyk')) e.waitUntil(zapisz(klucz, res.clone()));
    return res;
  };
  if (z) {
    const t0 = Date.parse(z.headers.get('x-cf-zapisano') || '');
    if (!(Date.now() - t0 < ODSWIEZ_STATYKI_MS)) e.waitUntil(pobierz().catch(() => {}));
    return z;
  }
  return pobierz();
}

self.addEventListener('install', (e) => {
  self.skipWaiting();
  if (WYLACZONY) return;
  e.waitUntil((async () => {
    try {   // kopia strony od razu, by pierwsze wejście bez sieci też zadziałało; adres „/” — ten sam, który przeglądarka już pobrała
      const res = await fetch(ZAKRES.href);
      if (nadaje(res, 'strona')) await zapisz(KLUCZ_STRONY, res.clone());
    } catch (_) { /* bez kopii na start — zapisze się przy następnym wejściu */ }
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    const nazwy = await caches.keys();
    await Promise.all(nazwy.filter((n) => n.indexOf(PREFIKS) === 0 && (WYLACZONY || n !== NAZWA)).map((n) => caches.delete(n)));
    if (WYLACZONY) { await self.registration.unregister(); return; }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  if (WYLACZONY) return;
  const req = e.request;
  if (req.method !== 'GET' || req.headers.has('range')) return;
  if (req.cache === 'only-if-cached' && req.mode !== 'same-origin') return;
  let url;
  try { url = new URL(req.url); } catch (_) { return; }
  const r = rodzaj(url);
  if (!r) return;
  e.respondWith(r[0] === 'statyk' ? statyk(e, req, r[1]) : siecNajpierw(e, req, r[0], r[1]));
});

self.addEventListener('message', (e) => {
  if (WYLACZONY) return;
  const d = e.data || {};
  if (d.typ === 'stan') {
    e.waitUntil((async () => {
      const st = await czytajStan(await caches.open(NAZWA));
      if (st && e.source && e.source.postMessage) e.source.postMessage({ typ: 'z-pamieci', data: st.data });
    })());
  } else if (d.typ === 'wyczysc') e.waitUntil(wyczyscStan());
});
