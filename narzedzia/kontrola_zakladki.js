/* v440 (18.10.2026): stała kontrola zakładek GLOBAL, CRYPTO i TRENDY — skrypt sprawdzający, wstrzykiwany przez narzedzia/kontrola_zakladki.py
   do KOPII strony serwowanej lokalnie (strona na żywo i jej kod bez zmian). Działa w przeglądarce bez okna (ekran telefonu 390 px, czas wirtualny):
   przełącza zakładki, przełączniki i zakresy (aria-pressed), rozwijane bloki (aria-expanded, details), liczy wykresy i napisy-błędy,
   zbiera błędy JavaScriptu i wysyła wynik do lokalnego serwera kontroli (/__kz/…). Niczego nie zmienia na stronie poza stanem widoku
   (każdy przełącznik wraca do stanu wyjściowego), niczego nie wysyła poza ten lokalny serwer. Konfiguracja: window.__KZ_CFG = {tryb:'pelny'|'dane', maks:N}. */
(function () {
  'use strict';
  if (window.__KZ) return;
  var CFG = window.__KZ_CFG || {};
  var KZ = window.__KZ = { v: 1, tryb: CFG.tryb || 'pelny', err: [], kons: [], ele: [], tab: {}, uwagi: [] };
  var ART = /\bNaN\b|\bundefined\b|\[object Object\]|(?<!PancakeSwap\s)\bInfinity\b|\bnull\b|∞|Invalid Date/g;
  var KSZ = 'path,polyline,polygon,rect,circle,ellipse,line';
  var ZAKL = [['global', 'GLOBAL'], ['crypto', 'CRYPTO'], ['trendy', 'TRENDY']];
  var MAKS = CFG.maks || 500;
  var kroki = 0;

  function skr(s, n) { s = String(s == null ? '' : s); return s.length > n ? s.slice(0, n - 1) + '…' : s; }
  window.addEventListener('error', function (e) {
    KZ.err.push(skr((e.message || 'błąd') + ' (' + String(e.filename || 'strona').split('?')[0].split('/').pop() + ':' + (e.lineno || 0) + ')', 160));
  });
  window.addEventListener('unhandledrejection', function (e) {
    var r = e.reason; KZ.err.push(skr('odrzucona obietnica: ' + (r && r.message ? r.message : r), 160));
  });
  var ce = console.error;
  console.error = function () {
    try { KZ.kons.push(skr(Array.prototype.map.call(arguments, function (a) { return a && a.message ? a.message : String(a); }).join(' '), 160)); } catch (_) { /* nic */ }
    return ce.apply(console, arguments);
  };
  function sig(n, q) { try { fetch('/__kz/' + n + (q ? '?' + q : ''), { cache: 'no-store', keepalive: true }); } catch (_) { /* nic */ } }
  function czekaj(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function vis(e) { return !!(e && (e.offsetWidth || e.offsetHeight || e.getClientRects().length)); }
  function tekst(e, n) { return skr(((e && (e.innerText || e.textContent)) || '').replace(/\s+/g, ' ').trim(), n || 40); }
  function tytul(p) {
    if (!p) return '?';
    var h = p.querySelector('h1,h2,h3,h4,.zw-t,summary');
    var t = tekst(h || p, 46);
    return t || p.id || '?';
  }
  function panelDla(e) { return e.closest('.panel,.pcard,details,section,.page') || e.parentElement; }

  function plotno(c) {
    try {
      var x = c.getContext('2d'); if (!x) return true;
      var d = x.getImageData(0, 0, c.width, c.height).data;
      for (var i = 3; i < d.length; i += 4 * 211) if (d[i]) return true;
      return false;
    } catch (_) { return true; }
  }
  function wykresy(root) {   /* liczba narysowanych wykresów w widocznej części: svg z ≥ 3 kształtami (poza ikonami przycisków) i niepuste canvas */
    var n = 0;
    root.querySelectorAll('svg').forEach(function (s) {
      if (!vis(s) || s.closest('button,summary,.icon-btn,nav,.tabs')) return;
      var b = s.getBoundingClientRect();
      if (b.width < 20 || b.height < 10) return;
      if (s.querySelectorAll(KSZ).length >= 3) n++;
    });
    root.querySelectorAll('canvas').forEach(function (c) { if (vis(c) && c.width > 50 && c.height > 30 && plotno(c)) n++; });
    return n;
  }
  function panele(root) {   /* widoczne panele z treścią */
    var n = 0;
    root.querySelectorAll('.panel').forEach(function (p) { if (vis(p) && (p.innerText || '').trim().length > 20) n++; });
    return n;
  }
  function artefakty(root) {   /* napisy-błędy w widocznym tekście: gdzie (panel) i otoczenie */
    var out = [], seen = {};
    var ps = root.matches && root.matches('.panel,.kpis,.map-panel') ? [root] : root.querySelectorAll('.panel,.kpis,.map-panel');
    ps.forEach(function (p) {
      if (!vis(p)) return;
      var t = (p.innerText || ''), m;
      ART.lastIndex = 0;
      while ((m = ART.exec(t))) {
        var k = tytul(p) + '|' + m[0];
        if (seen[k]) continue;
        seen[k] = 1;
        out.push(skr(tytul(p), 30) + ': „' + t.slice(Math.max(0, m.index - 24), m.index + m[0].length + 12).replace(/\s+/g, ' ') + '”');
        if (out.length >= 6) return;
      }
    });
    return out;
  }
  function zakres(id) {   /* elementy zakładki: jej sekcja i lewy pasek */
    return [document.getElementById(id), document.getElementById('side-fg')].filter(Boolean);
  }
  function wTab(id, sel) {
    var out = [];
    zakres(id).forEach(function (r) { r.querySelectorAll(sel).forEach(function (e) { if (out.indexOf(e) < 0) out.push(e); }); });
    return out;
  }
  async function krok(zak, typ, nazwa, fn) {
    if (kroki++ >= MAKS) return;
    var e0 = KZ.err.length, w = { z: zak, t: typ, n: skr(nazwa, 90), s: 'ok', u: [] };
    try { await fn(w); } catch (x) { w.s = 'blad'; w.u.push('wyjątek: ' + skr(x && x.message ? x.message : x, 100)); }
    if (KZ.err.length > e0) { w.s = 'blad'; w.u.push('błąd JavaScriptu: ' + skr(KZ.err.slice(e0).join(' | '), 200)); }
    if (CFG.diag) { var sk = document.querySelector('section[id=global],section[id=crypto],section[id=trendy]'); w.k = [wykresy(document.getElementById('global')), wykresy(document.getElementById('crypto')), wykresy(document.getElementById('trendy'))]; }
    KZ.ele.push(w);
  }
  function ostrz(w, t) { if (w.s === 'ok') w.s = 'ostrz'; w.u.push(t); }
  function blad(w, t) { w.s = 'blad'; w.u.push(t); }

  var WIDOK0 = { global: -1 };
  (function wypatrz() {   /* pierwszy widok GLOBAL — od startu skryptu, co 100 ms (czas wirtualny stoi, gdy sieć pracuje): chwila trafia do lokalnego serwera kontroli */
    var t0 = performance.now(), iv = setInterval(function () {
      var sek = document.getElementById('global');
      if (sek && vis(sek) && panele(sek) >= 2 && wykresy(sek) >= 1) { WIDOK0.global = Math.round(performance.now() - t0); sig('widok_global'); clearInterval(iv); }
      else if (performance.now() - t0 > 60000) clearInterval(iv);
    }, 100);
  })();
  async function pierwszyWidok(id, maksMs) {   /* czeka na pierwszy widok zakładki: ≥ 2 panele z treścią i ≥ 1 wykres; zwraca czas wirtualny */
    var sek = document.getElementById(id), t0 = performance.now();
    while (performance.now() - t0 < maksMs) {
      if (vis(sek) && panele(sek) >= 2 && wykresy(sek) >= 1) return Math.round(performance.now() - t0);
      await czekaj(100);
    }
    return -1;
  }
  async function osiadz(id) {   /* po wejściu w zakładkę: czekamy aż liczba wykresów przestanie rosnąć */
    var sek = document.getElementById(id), ost = -1, st = 0;
    for (var i = 0; i < 40 && st < 6; i++) {
      var n = wykresy(sek) * 1000 + panele(sek);
      st = n === ost ? st + 1 : 0; ost = n;
      await czekaj(250);
    }
  }

  async function przelacz(id, nazwa) {
    var b = document.getElementById('tab-' + id), sek = document.getElementById(id);
    var o = { ok: true, u: [] };
    if (!b || !sek) { o.ok = false; o.u.push('brak zakładki albo sekcji'); return o; }
    sig('klik_' + id);
    b.click();
    var v = await pierwszyWidok(id, 25000);
    if (v >= 0) sig('widok_' + id);
    o.widok_v = v;
    await osiadz(id);
    if (b.getAttribute('aria-selected') !== 'true') { o.ok = false; o.u.push('zakładka nie jest zaznaczona'); }
    if (!vis(sek)) { o.ok = false; o.u.push('sekcja zakładki niewidoczna'); }
    ZAKL.forEach(function (z) {
      if (z[0] !== id && vis(document.getElementById(z[0]))) { o.ok = false; o.u.push('widoczna też sekcja ' + z[1]); }
    });
    if (v < 0) o.widok_brak = true;   /* brak paneli z treścią albo wykresu w 25 s — przy pustym pliku danych to oczekiwane, ocenia Python */
    return o;
  }

  function poza(id) {   /* wykresy widoczne poza zwijanymi blokami i szczegółami (mapa, wskaźniki) */
    var sek = document.getElementById(id), n = 0;
    sek.querySelectorAll('svg,canvas').forEach(function (x) {
      if (x.closest('.zw-on') || x.closest('details')) return;
      var ob = { querySelectorAll: function (q) { var t = x.tagName.toLowerCase(); return q === t ? [x] : []; } };
      if (wykresy(ob) > 0) n++;
    });
    return n;
  }
  function opisTab(id) {
    var sek = document.getElementById(id);
    return { wykresy: wykresy(sek), panele: panele(sek), artefakty: artefakty(sek), tekst: (sek.innerText || '').length };
  }

  /* Elementy odnajdywane PO KLIKNIĘCIU po tożsamości (strona potrafi przerysować panel i wymienić przycisk): panel (id) + selektor + numer. */
  function panelId(e) { var p = e.closest('.panel[id],.pcard[id],section[id],details[id],.page[id]'); return p ? p.id : ''; }
  function zasieg(pid, id) { return pid ? document.getElementById(pid) : document.getElementById(id); }
  function atrybuty(e) {   /* selektor z atrybutów data-* (bez tłumaczeń) — tożsamość przycisku odporna na zmianę kolejności */
    var q = '';
    Array.prototype.forEach.call(e.attributes, function (a) {
      if (/^data-/.test(a.name) && !/^data-i18n/.test(a.name) && a.value.length < 40 && !/["\\]/.test(a.value)) q += '[' + a.name + '="' + a.value + '"]';
    });
    return q;
  }
  function kandydaci(t, id) {
    var r = zasieg(t.pid, id); if (!r) return [];
    return Array.prototype.filter.call(r.querySelectorAll(t.sel), function (x) { return !t.txt || tekst(x.tagName === 'DETAILS' ? x.querySelector('summary') : x, 30) === t.txt; });
  }
  function odnajdz(t, id) {
    if (t.domId) return document.getElementById(t.domId);
    return kandydaci(t, id)[t.idx] || null;
  }
  function tozsamosc(e, sel, id) {
    var t = { domId: e.id || '', pid: panelId(e), sel: sel + (e.tagName === 'BUTTON' ? atrybuty(e) : ''), txt: tekst(e.tagName === 'DETAILS' ? e.querySelector('summary') : e, 30) };
    t.idx = Math.max(0, kandydaci(t, id).indexOf(e));
    return t;
  }

  var NAZWY_GRUP = { 'g-period': 'Okres (GLOBAL)', 'seg-period': 'Okres (CRYPTO)', 'trd-view': 'Trendy: Global / Krypto', 'chips': 'Sektory krypto (chipy)',
    'zoom': 'Scena krypto (TOP 10, pełny ekran)', 'wk-seg': 'Widok: Karty / Wykresy', 'wk-sel': 'Widok: Karty / Wykresy' };
  function nazwaGrupy(g) {   /* czytelna nazwa grupy przełączników: znane identyfikatory, potem etykieta aria, potem tytuł panelu */
    var k = g.id || (g.className || '').split(/\s+/)[0];
    if (NAZWY_GRUP[k]) return NAZWY_GRUP[k];
    var et = g.getAttribute('aria-label'), pan = tytul(panelDla(g));
    return skr(et && pan.indexOf(et) < 0 ? pan + ' (' + et + ')' : pan, 38);
  }
  function etykieta(b, k) {   /* etykieta przycisku bez zmiennych liczb (strzałki i zmiany procentowe sektorów) */
    return tekst(b, 26).replace(/\s*[▲▼△▽].*$/, '').trim() || b.getAttribute('aria-label') || b.id || ('#' + (k + 1));
  }
  async function przelaczniki(id, nazwaZ) {
    /* przełączniki = widoczne przyciski aria-pressed, pogrupowane po rodzicu; grupa ≥ 2 przyciski */
    var grupy = [], mapa = [];
    wTab(id, 'button[aria-pressed]').forEach(function (b) {
      if (!vis(b) || b.disabled || b.hidden) return;
      var g = b.parentElement, i = mapa.indexOf(g);
      if (i < 0) { mapa.push(g); grupy.push({ el: g, b: [] }); i = mapa.length - 1; }
      grupy[i].b.push(b);
    });
    grupy = grupy.filter(function (g) { return g.b.length >= 2; }).map(function (g) {
      var wc = g.b.map(function (b) { return b.getAttribute('aria-pressed') === 'true'; });
      var typowa = g.el.getAttribute('role') === 'group' || /\b(seg|segs|wk-seg|trd-seg|arc-seg)\b/.test(g.el.className);
      return { nazwa: nazwaGrupy(g.el), typowa: typowa, wyl: typowa && wc.filter(Boolean).length === 1, el: g.b.map(function (b, k) {
        return { t: tozsamosc(b, 'button[aria-pressed]', id), et: etykieta(b, k), pocz: wc[k], wk: b.getAttribute('data-wk-v') === 'wykresy' };
      }) };
    });
    for (var gi = 0; gi < grupy.length; gi++) {
      var G = grupy[gi];
      for (var k = 0; k < G.el.length; k++) {
        var E = G.el[k];
        if (E.pocz && G.wyl) continue;   /* aktywny przycisk grupy wyłącznej — sprawdzamy pozostałe, na końcu wracamy do niego */
        await krok(nazwaZ, 'przełącznik', G.nazwa + ' › ' + E.et, async function (w) {
          var b = odnajdz(E.t, id);
          if (!b || !vis(b)) { ostrz(w, 'przycisk zniknął przed kliknięciem (zmiana układu)'); return; }
          var pan = panelDla(b), przed = wykresy(pan);
          b.click();
          await czekaj(600);
          var by = odnajdz(E.t, id);
          if (!by) { ostrz(w, 'po kliknięciu przycisk zniknął (zmiana układu)'); return; }
          var st = by.getAttribute('aria-pressed') === 'true';
          if (G.wyl) {
            var rodzic = by.parentElement, zazn = rodzic ? Array.prototype.filter.call(rodzic.querySelectorAll('button[aria-pressed]'), function (x) { return x.getAttribute('aria-pressed') === 'true'; }).length : 1;
            if (!st) ostrz(w, 'przycisk nie został zaznaczony');
            else if (zazn !== 1) ostrz(w, 'zaznaczone ' + zazn + ' przyciski zamiast jednego');
          } else if (st === E.pocz) ostrz(w, 'stan przycisku się nie zmienił');
          var pan2 = panelDla(by), po = wykresy(pan2 && pan2.isConnected ? pan2 : document.getElementById(id));
          if (G.typowa && przed > 0 && po === 0 && !E.wk) blad(w, 'wykresy zniknęły (było ' + przed + ', jest 0)');
          if (E.wk) { var wg = document.getElementById('wk-' + id) || document.getElementById(id); if (!vis(wg) || wykresy(wg) === 0) blad(w, 'widok „Wykresy” bez ani jednego wykresu'); }
          var a = artefakty(panelDla(by).isConnected ? panelDla(by) : document.getElementById(id)); if (a.length) blad(w, 'napis-błąd w tekście: ' + a[0]);
        });
      }
      /* powrót do stanu wyjściowego grupy */
      for (var p = 0; p < 3; p++) {
        var zmiana = false;
        for (var q = 0; q < G.el.length; q++) {
          var bq = odnajdz(G.el[q].t, id);
          if (bq && (bq.getAttribute('aria-pressed') === 'true') !== G.el[q].pocz && (!G.wyl || G.el[q].pocz)) { bq.click(); await czekaj(500); zmiana = true; break; }
        }
        if (!zmiana) break;
      }
    }
  }

  async function rozwijane(id, nazwaZ) {
    /* bloki z aria-expanded (przycisk panelu, „Widok”) i szczegóły <details>; po kliknięciu stan sprawdzany na elemencie odnalezionym od nowa */
    var SEL_E = '[aria-expanded]:not([aria-pressed])';
    var ex = wTab(id, SEL_E).filter(vis).map(function (e) {
      var fb = /\bzw-fb\b/.test(e.className);
      return { t: tozsamosc(e, SEL_E, id), nazwa: tytul(panelDla(e)) + (fb ? ' (przycisk „Widok”)' : ' (blok)'), fb: fb };
    });
    ex.sort(function (a, b) { return (a.fb ? 1 : 0) - (b.fb ? 1 : 0); });
    for (var i = 0; i < ex.length; i++) {
      var X = ex[i];
      await krok(nazwaZ, 'rozwijanie', X.nazwa, async function (w) {
        var e = odnajdz(X.t, id); if (!e) { ostrz(w, 'przycisk zniknął przed kliknięciem'); return; }
        var a0 = e.getAttribute('aria-expanded'), wk0 = wykresy(panelDla(e));
        e.click(); await czekaj(350);
        var e1 = odnajdz(X.t, id); if (!e1) { ostrz(w, 'po kliknięciu przycisk zniknął'); return; }
        if (e1.getAttribute('aria-expanded') === a0) ostrz(w, 'stan bloku się nie zmienił po kliknięciu');
        var rozw = e1.getAttribute('aria-expanded') === 'true';
        w.wk = rozw ? wykresy(panelDla(e1)) : wk0;   /* wykresy bloku w stanie rozwiniętym */
        var a = artefakty(panelDla(e1)); if (a.length) blad(w, 'napis-błąd w tekście: ' + a[0]);
        e1.click(); await czekaj(300);
        var e2 = odnajdz(X.t, id);
        if (!e2 || e2.getAttribute('aria-expanded') !== a0) ostrz(w, 'blok nie wrócił do stanu wyjściowego');
      });
    }
    var dt = wTab(id, 'details>summary').filter(vis).map(function (sm) {
      var d = sm.parentElement; return { t: tozsamosc(d, 'details', id), nazwa: tekst(sm, 70).replace(/\s*·.*$/, '').replace(/\s*\(\d+\)/g, '').trim() + ' (szczegóły)' };
    });
    for (var j = 0; j < dt.length; j++) {
      var D = dt[j];
      await krok(nazwaZ, 'rozwijanie', D.nazwa, async function (w) {
        var d = odnajdz(D.t, id); if (!d) { ostrz(w, 'szczegóły zniknęły przed kliknięciem'); return; }
        var o0 = d.open, sm = d.querySelector(':scope>summary');
        if (!sm) { ostrz(w, 'brak nagłówka szczegółów'); return; }
        sm.click(); await czekaj(220);
        var d1 = odnajdz(D.t, id); if (!d1) { ostrz(w, 'szczegóły zniknęły po kliknięciu'); return; }
        if (d1.open === o0) ostrz(w, 'szczegóły nie zmieniły stanu po kliknięciu');
        w.wk = d1.open ? wykresy(d1) : 0;
        var s1 = d1.querySelector(':scope>summary'); if (s1) { s1.click(); await czekaj(150); }
        var d2 = odnajdz(D.t, id); if (!d2 || d2.open !== o0) ostrz(w, 'szczegóły nie wróciły do stanu wyjściowego');
      });
    }
  }

  async function zakladka(id, nazwa, glowna) {
    var sw = await przelacz(id, nazwa);
    var op = opisTab(id);
    KZ.tab[id] = { nazwa: nazwa, przelaczenie: sw.ok, uwagi: sw.u, widok_v: sw.widok_v, widok_brak: !!sw.widok_brak, wykresy: op.wykresy, panele: op.panele, artefakty: op.artefakty, tekst: op.tekst, poza: poza(id) };
    var e0 = KZ.ele.length;
    if (KZ.tryb === 'pelny' || KZ.tryb === 'dane') {
      var fb = wTab(id, '.zw-fb[aria-expanded="false"]').filter(vis);   /* przycisk „Widok” odsłania przełącznik Karty/Wykresy */
      for (var f = 0; f < fb.length; f++) { fb[f].click(); await czekaj(300); }
      await przelaczniki(id, nazwa);
      for (var f2 = 0; f2 < fb.length; f2++) { var fx = document.getElementById(fb[f2].id); if (fx && fx.getAttribute('aria-expanded') === 'true') { fx.click(); await czekaj(300); } }
      await rozwijane(id, nazwa);
      var op2 = opisTab(id), sw2 = 0, bl = 0;
      KZ.ele.slice(e0).forEach(function (x) { if (typeof x.wk === 'number') { sw2 += x.wk; if (x.wk > 0) bl++; } });
      /* wykresy zakładki = widoczne poza zwijanymi blokami + wykresy każdego bloku w stanie rozwiniętym */
      KZ.tab[id].wykresy_po = KZ.tab[id].poza + sw2; KZ.tab[id].bloki_z_wykresem = bl; KZ.tab[id].panele_po = op2.panele; KZ.tab[id].artefakty_po = op2.artefakty;
    }
  }

  async function glowne() {
    try {
      sig('start');
      /* pierwszy widok GLOBAL (zakładka domyślna) */
      var v = await pierwszyWidok('global', 30000);
      KZ.tab.global0 = { widok_v: v };
      await osiadz('global');
      for (var i = 0; i < ZAKL.length; i++) await zakladka(ZAKL[i][0], ZAKL[i][1]);
      /* powrót do GLOBAL: zakładka wraca i wykresy nie znikają */
      var g1 = KZ.tab.global ? KZ.tab.global.wykresy : 0;
      var bk = await przelacz('global', 'GLOBAL'), op = opisTab('global');
      KZ.powrot = { ok: bk.ok, u: bk.u, wykresy: op.wykresy, wykresy_wczesniej: g1, panele: op.panele };
      /* wersja strony i stan końcowy */
      KZ.zegar = { stale: (function () { var e = document.getElementById('srv-stale'); return e && !e.hidden ? tekst(e, 120) : ''; })() };
    } catch (x) {
      KZ.uwagi.push('skrypt kontroli przerwany: ' + skr(x && x.message ? x.message : x, 120));
    }
    KZ.koniec = true;
    try {
      await fetch('/__kz/wynik', { method: 'POST', body: JSON.stringify(KZ), headers: { 'Content-Type': 'application/json' }, keepalive: true });
    } catch (_) { /* nic */ }
  }

  function start() { setTimeout(glowne, 1500); }
  if (document.readyState === 'complete') start(); else window.addEventListener('load', start);
})();
