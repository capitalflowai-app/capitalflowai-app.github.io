// Test bramki strony dla plików widoków silnika (data/widoki/*.json), bez przeglądarki.
// Wycina z index.html czystą funkcję engCheck i sprawdza, kiedy strona pokaże liczby, a kiedy nie.
// Uruchomienie: node --test test_widoki.cjs   (w GitHub Actions krok przed publikacją; awaria blokuje publikację)
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const start = html.indexOf('function engCheck(rec,view,nowMs){');
assert.ok(start > 0, 'index.html musi zawierać engCheck');
const end = html.indexOf('\nfunction engLoad(', start);
assert.ok(end > start, 'engCheck musi kończyć się przed engLoad');
const engCheck = new Function(html.slice(start, end) + '\nreturn engCheck;')();

const NOW = Date.parse('2026-09-24T12:00:00Z');
const bound = (over = {}) => Object.assign({
  schema: 'capitalflowai.public-view.v1', view: 'cftc-euro-fx', state: 'BOUND', trial: false,
  public_display: { admitted: true }, valid_until: '2026-09-28T14:00:00.000000+00:00',
  captured_at: '2026-09-20T14:00:00.000000+00:00', values: [], engine_panel: { data: {} },
}, over);

test('brak pliku to „brak pliku”, nie zero', () => {
  assert.deepEqual(engCheck(null, 'cftc-euro-fx', NOW), { ok: false, code: 'SITE_FILE_MISSING' });
  assert.deepEqual(engCheck(undefined, 'cftc-euro-fx', NOW), { ok: false, code: 'SITE_FILE_MISSING' });
});

test('poprawny plik BOUND z dopuszczeniem i terminem w przyszłości pokazuje liczby', () => {
  assert.deepEqual(engCheck(bound(), 'cftc-euro-fx', NOW), { ok: true, state: 'BOUND' });
});

test('plik WITHHELD jest pokazywany jako karta bez liczb', () => {
  assert.deepEqual(engCheck({ schema: 'capitalflowai.public-view.v1', view: 'tic-flows', state: 'WITHHELD' }, 'tic-flows', NOW),
    { ok: true, state: 'WITHHELD' });
});

test('zły schemat, inny widok albo nieznany stan są odrzucane', () => {
  assert.equal(engCheck(bound({ schema: 'x' }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
  assert.equal(engCheck(bound(), 'cftc-crypto', NOW).code, 'SITE_FILE_INVALID');
  assert.equal(engCheck(bound({ state: 'READY' }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
  assert.equal(engCheck('tekst', 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
});

test('BOUND bez dopuszczenia publicznego nigdy nie pokazuje liczb', () => {
  assert.equal(engCheck(bound({ public_display: { admitted: false } }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
  assert.equal(engCheck(bound({ public_display: null }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
  assert.equal(engCheck(bound({ public_display: { admitted: 'true' } }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
});

test('plik po terminie ważności albo bez terminu nie pokazuje liczb', () => {
  assert.equal(engCheck(bound({ valid_until: '2026-09-24T12:00:00.000000+00:00' }), 'cftc-euro-fx', NOW).code, 'FILE_EXPIRED');
  assert.equal(engCheck(bound({ valid_until: '2026-01-01T00:00:00Z' }), 'cftc-euro-fx', NOW).code, 'FILE_EXPIRED');
  assert.equal(engCheck(bound({ valid_until: null }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
  assert.equal(engCheck(bound({ valid_until: 'wczoraj' }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
  // JS obcina mikrosekundy: termin 1 µs po „teraz” liczy się jako miniony (ostrożnie); sekundę później plik jest ważny
  assert.equal(engCheck(bound({ valid_until: '2026-09-24T12:00:00.000001+00:00' }), 'cftc-euro-fx', NOW).code, 'FILE_EXPIRED');
  assert.deepEqual(engCheck(bound({ valid_until: '2026-09-24T12:00:01+00:00' }), 'cftc-euro-fx', NOW), { ok: true, state: 'BOUND' });
});

test('plik z przebiegu próbnego nigdy nie trafia na stronę', () => {
  assert.equal(engCheck(bound({ trial: true }), 'cftc-euro-fx', NOW).code, 'SITE_TRIAL_FILE');
});

test('BOUND bez czasu pobrania albo bez danych jest niepoprawny', () => {
  assert.equal(engCheck(bound({ captured_at: null }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
  assert.equal(engCheck(bound({ values: null, engine_panel: null }), 'cftc-euro-fx', NOW).code, 'SITE_FILE_INVALID');
});

test('każdy z ośmiu widoków ma w stronie własną sekcję', () => {
  for (const view of ['tic-flows', 'tic-countries', 'wdi-destinations', 'imf-portfolio-pairs', 'cftc-euro-fx',
    'coinmetrics-exchange-flows', 'defillama-stablecoins', 'cftc-crypto']) {
    assert.ok(html.includes(`id="eng-${view}" hidden`), view);
  }
});

// v36: dokładny tekst w mln USD (Bank Światowy) — te same reguły co na lokalnej stronie silnika (destinations_page.py)
const m0 = html.indexOf('function engInc(');
assert.ok(m0 > 0, 'index.html musi zawierać engInc/engMln (v36)');
const m1 = html.indexOf('const engK=(label,value,wrap)=>', m0);
assert.ok(m1 > m0, 'engMln musi kończyć się przed engK');
const mlnFor = (lang) => new Function('LANG', html.slice(m0, m1) + '\nreturn engMln;')(lang);
const mln = mlnFor('pl');

test('mln USD: zaokrąglenie do parzystej z dokładnego tekstu, bez zmiennoprzecinkowych błędów', () => {
  assert.equal(mln('382049649287.081'), '+382 049,6');
  assert.equal(mln('-19616207108.3879'), '−19 616,2');
  assert.equal(mln('1250000'), '+1,2');      // remis: cyfra parzysta zostaje
  assert.equal(mln('1350000'), '+1,4');      // remis: cyfra nieparzysta idzie w górę
  assert.equal(mln('1250000.001'), '+1,3');  // powyżej remisu
  assert.equal(mln('999950000'), '+1 000,0'); // przeniesienie przez tysiące
});

test('mln USD: kwota poniżej 0,1 mln nie jest zerem, zero bez znaku, −0 ze znakiem tylko gdy zgłoszone', () => {
  assert.equal(mln('49999'), '+<0,1');
  assert.equal(mln('-40000'), '−<0,1');
  assert.equal(mln('0'), '0,0');
  assert.equal(mln('-0'), '0,0');
  assert.equal(mln('-0', true), '−0,0');
  assert.equal(mln('1e5'), null);
  assert.equal(mln(5), null);
  assert.equal(mlnFor('en')('-1'), '−<0.1');
  assert.equal(mlnFor('en')('382049649287.081'), '+382 049.6');
});

test('sekcja Banku Światowego ma etykiety v36 w obu językach', () => {
  for (const key of ['eng.c.economy', 'eng.d.in', 'eng.d.out', 'eng.k.cov', 'eng.prev.gap', 'eng.prev.zero']) {
    assert.ok(html.includes(`"${key}":`), key);
  }
});

// v37: licencje — strona publiczna bez danych z planów „tylko do użytku osobistego”; atrybucje; migawka z SoSoValue
test('migawka ETF pochodzi z SoSoValue, a CoinMarketCap zostaje tylko w zdaniu o usunięciu', () => {
  assert.ok(html.includes("const ETF_SNAP={asof:'2026-09-23',fetched:'2026-09-24 13:48 UTC',src:'SoSoValue',"));
  assert.ok(!html.includes('CoinMarketCap ETF Tracker'), 'migawka ETF nie pochodzi już ze strony CMC');
  const sn0 = html.indexOf('const ETF_SNAP='), snap = html.slice(sn0, html.indexOf(';\n', sn0));
  assert.ok(sn0 > 0 && !snap.includes("src:'CoinMarketCap'"), 'migawka: src SoSoValue (v66: CoinMarketCap wolno w kafelku kapitalizacji)');
});

test('atrybucje wymagane przez dostawców są na stronie', () => {
  // v96: „Data by CoinGecko” przeniesione z panelu ETF do jednej stopki strony (sprawdza ją obszar „źródła”); w panelu ETF już go nie ma
  const re0 = html.indexOf('function renderEtf(){'), re1 = html.indexOf('\nconst CGST=', re0);
  assert.ok(re0 > 0 && re1 > re0 && !html.slice(re0, re1).includes('Data by CoinGecko') && !html.slice(re0, re1).includes('sosovalue.com'), 'v96: bez atrybucji w panelu ETF');
  // v103: lista linków Atrybucji (ATTR_LINKS) usunięta razem z dawną stroną Źródła — zostają tylko podpisy wymagane licencją (testy v103-zrodla)
});

test('notowania ETF-ów: plik z serwera (klucz właściciela) najpierw, potem własny klucz; CoinMarketCap z serwera', () => {
  assert.ok(html.includes("srvJSON('ceny')"), 'ceny.json z serwera (klucz właściciela) czytany najpierw — decyzja właściciela 24.09');
  assert.ok(html.includes("const KEYS={soso:'cfai.key.soso',finnhub:'cfai.key.finnhub',cg:'cfai.key.cg',td:'cfai.key.td'};"));
  assert.ok(html.includes('<section class="panel pcard" id="cmc" hidden></section>'), 'sekcja CoinMarketCap');
  assert.ok(html.includes("srvJSON('cmc')") && html.includes('X-CMC') === false, 'cmc.json z serwera; klucz nigdy w stronie');
  assert.ok(html.includes("TD_B1=['SPY','VGK','EWJ','MCHI','INDA','EWY','EWC'],TD_B2=['ILF','KSA','TUR','EIS','EZA','ASEA','EWA']"));
  assert.ok(html.includes('TD_GAP=61000'), 'druga paczka po 61 s (limit 8 kredytów/min)');
  assert.ok(html.includes('TD_TTL=60*60*1000'), 'pamięć podręczna 60 min');
});

// v38: nazwy i daty z zewnątrz (CoinPaprika, SoSoValue, pliki serwera) są escapowane przed wstawieniem do HTML (audyt B5/B6)
test('nazwy monet i funduszy oraz daty z plików są escapowane', () => {
  assert.ok(html.includes('<span class="nm">${escH(r.name)}</span>'));
  assert.ok(html.includes('<b>${escH(f.t)}</b>'));
  assert.ok(html.includes('<small class="mtxt">${escH(f.n)}</small>'));
  assert.ok(html.includes("t('etf.src.snap',{d:escH(D.asof),f:escH(ETF_SNAP.fetched)})"));
  assert.ok(!html.includes('${r.name}') && !html.includes('${f.n}') && !html.includes('${f.t}'));
  assert.ok(html.includes('/^(https:\\/\\/|data:image\\/(webp|png);base64,)/.test(String(lg))'), 'v96: logo z https albo wbudowany obraz (nie dowolny adres)');
  const e0 = html.indexOf('function escH('); const e1 = html.indexOf('\n', e0);
  const escH = new Function(html.slice(e0, e1) + '\nreturn escH;')();
  assert.equal(escH('<img src=x onerror=alert(1)>'), '&lt;img src=x onerror=alert(1)&gt;');
  assert.equal(escH('A&B "c" \'d\''), 'A&amp;B &quot;c&quot; &#39;d&#39;');
});

// v38: widok MFW (pary gospodarek) — mld USD z dziesiątych części miliarda, te same reguły co w silniku (holdings_page.py)
test('mld USD z dziesiątych: znak minus typograficzny, plus tylko przy zmianie, zero bez znaku', () => {
  const b0 = html.indexOf('function engBld('); const b1 = html.indexOf('function engHalf(', b0);
  assert.ok(b0 > 0 && b1 > b0, 'engBld musi istnieć przed engHalf');
  const mk = (lang) => new Function('LANG', 'engNum', html.slice(b0, b1) + '\nreturn engBld;')(lang, v => v.toLocaleString(lang === 'pl' ? 'pl-PL' : 'en-GB'));
  const pl = mk('pl');
  assert.equal(pl(45133), '4 513,3');
  assert.equal(pl(36, true), '+3,6');
  assert.equal(pl(-36, true), '−3,6');
  assert.equal(pl(0, true), '0,0');
  assert.equal(pl(7), '0,7');
  assert.equal(pl(1.5), null);
  assert.equal(mk('en')(45133), '4,513.3');
  assert.ok(html.includes("if(Array.isArray(d.pairs))return engPairs(rec);"));
  for (const key of ['eng.c.pair', 'eng.d.pairs', 'eng.k.top', 'eng.h.of.2']) assert.ok(html.includes(`"${key}":`), key);
});

// v39: dane urzędowe (TGA, RRP, SOMA, TARGET, MOF) — sekcja z pliku instytucje.json, liczby z datą i wiekiem
test('sekcja danych urzędowych: mln → mld z jednym miejscem, grupowanie jak w silniku, nota NY Fed i licencja MOF', () => {
  assert.ok(html.includes('<section class="panel pcard" id="inst" hidden></section>'));
  assert.ok(html.includes("srvJSON('instytucje')"));
  const m0 = html.indexOf('function instMld('); const m1 = html.indexOf('const instSign=', m0);
  assert.ok(m0 > 0 && m1 > m0);
  const mk = (lang) => new Function('LANG', html.slice(m0, m1) + '\nreturn instMld;')(lang);
  const pl = mk('pl');
  assert.equal(pl(957409), '957,4');
  assert.equal(pl(6364278), '6 364,3');
  assert.equal(pl(1037116.1), '1 037,1');
  assert.equal(pl(-331168.67), '−331,2');
  assert.equal(pl(999950), '1 000,0');
  assert.equal(pl(461), '0,5');
  assert.equal(pl('x'), null);
  assert.equal(mk('en')(6364278), '6,364.3');
  assert.ok(html.includes('subject to the Terms of Use posted at newyorkfed.org'), 'nota wymagana przez NY Fed');
  assert.ok(html.includes('Public Data License (PDL) v1.0'), 'licencja MOF');
  for (const key of ['inst.tga', 'inst.rrp', 'inst.soma', 'inst.tgb.t', 'inst.mof.t', 'inst.not1', 'g.hs.tga', 'g.hs.mof']) assert.ok(html.includes(`"${key}":`), key);
});

// v41: oficjalne widgety TradingView — tylko po kliknięciu (zgoda cfai.tv.ok), atrybucja zachowana, motyw i język ze strony
const tv0 = html.indexOf('/* v41: TradingView — początek');
const tv1 = html.indexOf('/* v41: TradingView — koniec */', tv0);
assert.ok(tv0 > 0 && tv1 > tv0, 'blok TradingView istnieje');
const tvBlock = html.slice(tv0, tv1);
const tvFor = (lang, theme) => new Function('LANG', 't', 'document', 'localStorage', '$', 'escH',
  tvBlock + '\nreturn {TV, TV_LOCALE, TV_W, tvLocale, tvTheme, tvMarkup, tvOk};')(
  lang, (k, v) => v ? k + ':' + JSON.stringify(v) : k, { documentElement: { dataset: { theme } } },
  { getItem() { throw new Error('bez pamięci'); }, setItem() { throw new Error('bez pamięci'); } }, () => null, s => String(s));

test('TradingView: bez kliknięcia w kodzie strony nie ma żadnego elementu ładowanego z domen TradingView', () => {
  assert.doesNotMatch(html, /<script[^>]*src=["'][^"']*tradingview/i, 'skrypt TradingView w HTML');
  assert.doesNotMatch(html, /<iframe[^>]*tradingview/i, 'iframe TradingView w HTML');
  assert.doesNotMatch(html, /<(link|img|source|embed|object)[^>]*tradingview/i, 'inny element z adresem TradingView');
  assert.doesNotMatch(html, /tradingview-widget\.com\/w\//, 'komponent web TradingView (język zaszyty w adresie) nie jest używany');
  // jedyne miejsce włączające widget sprawdza zgodę; adres skryptu jest budowany tylko w tvMount
  assert.equal((tvBlock.match(/TV\.loaded\[k\]=true/g) || []).length, 1);
  assert.ok(tvBlock.includes("function tvOn(k){if(!tvOk())return;TV.loaded[k]=true;"), 'włączenie tylko za zgodą');
  assert.equal((html.match(/https:\/\/s3\.tradingview\.com\/external-embedding\//g) || []).length, 1, 'adres loadera tylko w stałej TV.HOST (nazwa domeny w tekście „Źródła i prawa” i host w polityce CSP to nie adresy loadera)');
  assert.ok(html.includes("KEY:'cfai.tv.ok'"), 'klucz zgody w localStorage');
});

test('TradingView: cztery sekcje w istniejących klasach, pod mapą GLOBAL i CRYPTO, ukryte bez JS', () => {
  const gd = html.indexOf('id="g-detail"'), ge = html.indexOf('id="g-etf"'), cd = html.indexOf('id="detail"'), cm = html.indexOf('id="eng-coinmetrics-exchange-flows"');
  for (const id of ['tv-markets', 'tv-calendar']) { const i = html.indexOf(`<section class="panel pcard" id="${id}" hidden></section>`); assert.ok(i > gd && i < ge, id); }
  for (const id of ['tv-heatmap', 'tv-chart']) { const i = html.indexOf(`<section class="panel pcard" id="${id}" hidden></section>`); assert.ok(i > cd && i < cm, id); }
});

test('TradingView: bez pamięci przeglądarki zgoda = brak; język i motyw strony trafiają do konfiguracji', () => {
  const de = tvFor('de', 'light');
  assert.equal(de.tvOk(), false);
  assert.equal(de.tvLocale(), 'de_DE');
  assert.deepEqual(Object.keys(de.TV_LOCALE).sort(), ['de', 'en', 'es', 'fr', 'it', 'ja', 'pl', 'pt', 'ru', 'zh']);
  assert.equal(de.TV_LOCALE.pt, 'br'); assert.equal(de.TV_LOCALE.zh, 'zh_CN');
  const m = de.TV_W.markets.cfg(), c = de.TV_W.calendar.cfg(), h = de.TV_W.heatmap.cfg(), a = de.TV_W.chart.cfg();
  assert.equal(m.colorTheme, 'light'); assert.equal(m.locale, 'de_DE'); assert.equal(m.width, '100%'); assert.equal(m.isTransparent, false, 'v41.1: z true widget rysuje się na biało w ciemnym motywie');
  assert.equal(m.tabs.length, 4); assert.equal(m.tabs[0].title, 'tv.tab.idx'); assert.equal(m.tabs[0].originalTitle, 'Indices');
  assert.equal(c.colorTheme, 'light'); assert.equal(c.locale, 'de_DE'); assert.equal(c.importanceFilter, '1'); assert.equal(c.countryFilter, 'us,eu,gb,jp,cn,de'); assert.equal(c.isTransparent, false);
  assert.equal(h.dataSource, 'Crypto'); assert.equal(h.blockSize, 'market_cap_calc'); assert.equal(h.blockColor, '24h_close_change|5'); assert.equal(h.colorTheme, 'light'); assert.equal(h.locale, 'de_DE');
  assert.equal(a.theme, 'light'); assert.equal(a.locale, 'de_DE'); assert.ok(!('backgroundColor' in a) && !('gridColor' in a), 'jasny motyw: kolory domyślne TradingView'); assert.equal(a.symbol, 'BITSTAMP:BTCUSD'); assert.equal(a.allow_symbol_change, true); assert.equal(a.hide_top_toolbar, false); assert.equal(a.autosize, true);
  const ja = tvFor('ja', 'dark');
  assert.equal(ja.TV_W.chart.cfg().theme, 'dark'); assert.equal(ja.TV_W.chart.cfg().backgroundColor, '#0F0F0F'); assert.equal(ja.tvLocale(), 'ja');
  ja.TV.sym = 'BITSTAMP:ETHUSD';
  assert.equal(ja.TV_W.chart.cfg().symbol, 'BITSTAMP:ETHUSD');
  assert.ok(ja.tvMarkup('chart').includes('https://www.tradingview.com/symbols/ETHUSD/?exchange=BITSTAMP'));
  assert.equal(tvFor('xx', 'dark').tvLocale(), 'en', 'nieznany język → en');
});

test('TradingView: stopka z linkiem TradingView zostaje w każdym widgecie; skryptu nie ma w znacznikach', () => {
  const x = tvFor('pl', 'dark');
  for (const k of ['markets', 'calendar', 'heatmap', 'chart']) {
    const mk = x.tvMarkup(k);
    assert.ok(mk.includes('<div class="tradingview-widget-copyright"><a href="https://www.tradingview.com/'), k);
    assert.ok(mk.includes('class="blue-text"') && mk.includes('rel="noopener nofollow" target="_blank"'), k);
    assert.ok(mk.includes('tradingview-widget-container__widget'), k);
    assert.ok(!mk.includes('<script'), k + ': skrypt tylko po zgodzie (tvMount)');
  }
  assert.ok(x.tvMarkup('calendar').includes('<span class="blue-text">Economic Calendar</span></a><span class="trademark"> by TradingView</span>'));
  assert.ok(x.tvMarkup('heatmap').includes('<span class="blue-text">Crypto Heatmap</span></a><span class="trademark"> by TradingView</span>'));
  assert.ok(x.tvMarkup('markets').includes('<span class="blue-text">Track all markets on TradingView</span>'));
});

test('TradingView: wiersz na stronie Źródła, atrybucja, wpis w „Źródła i prawa”, teksty w dziesięciu językach', () => {
  const d0 = html.indexOf('const EXTRA30='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA30='.length, d1));
  assert.deepEqual(Object.keys(dict).sort(), ['de', 'en', 'es', 'fr', 'it', 'ja', 'pl', 'pt', 'ru', 'zh']);
  for (const l of Object.keys(dict)) for (const k of ['tv.ph', 'tv.load', 'tv.off', 'tv.foot', 'tv.st.on', 'tv.st.off', 'tv.t.markets', 'tv.t.chart', 'tv.tab.idx', 'tv.tab.cmd']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['tv.ph'].includes('kliknij, aby załadować (treść z serwerów TradingView, mogą ustawić ciasteczka)'));
  assert.ok(dict.pl['g.hs.tv'] && dict.en['g.hs.tv'], 'opis wiersza Źródła');
});

// v42: serie Fed przez FRED (klucz właściciela) — tylko serie Fed, podpis z FRED, brak nie jest zerem
const fp0 = html.indexOf('function fredPct(series,back){');
const fp1 = html.indexOf('\nconst FRED={data:null};', fp0);
const fredFns = new Function('instSign', 'nfmt', html.slice(fp0, fp1) + '\nreturn {fredPct, fredSignPct};')(
  v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d));

test('FRED: zmiana procentowa indeksu dolara liczona tylko z liczb; za krótka seria to brak, nie zero', () => {
  const s = [['2026-09-10', 120], ['2026-09-11', 121.2], ['2026-09-12', 119.5133]];
  assert.equal(fredFns.fredPct(s, 2).toFixed(4), '-0.4056');
  assert.equal(fredFns.fredPct(s, 3), null, 'brak obserwacji wstecz → null');
  assert.equal(fredFns.fredPct([['2026-09-12', 'x'], ['2026-09-13', 1]], 1), null);
  assert.equal(fredFns.fredSignPct(-0.4056), '−0.41%'); assert.equal(fredFns.fredSignPct(1.5), '+1.50%'); assert.equal(fredFns.fredSignPct(0), '0.00%');
});

test('FRED: strona czyta fred.json z serwera, pokazuje cztery serie Fed z podpisem FRED i notą API', () => {
  assert.ok(html.includes("srvJSON('fred')"), 'plik automatu');
  for (const k of ['WALCL', 'RRPONTSYD', 'DTWEXBGS', 'WTREGEN']) assert.ok(html.includes(`sr('${k}')`), k);
  assert.ok(!/sr\('(SP500|VIXCLS|BAMLH0A0HYM2)'\)/.test(html), 'tylko serie Fed');
  const d0 = html.indexOf('const EXTRA31='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA31='.length, d1));
  for (const l of ['pl', 'en']) {
    assert.ok(dict[l]['inst.fred.src'].includes('Board of Governors of the Federal Reserve System (US), via FRED'), l);
    assert.equal(dict[l]['inst.fred.api'], 'This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.');
  }
  assert.ok(html.includes("if(!INST.data&&!FRED.data&&!REZ.data&&!xtra.length){el.hidden=true;el.innerHTML='';return;}"), 'sekcja także z samym FRED (v50: i z samymi rezerwami MFW)');
});

// v43: Eurosystem (EBC) w sekcji danych urzędowych; „dane z dzisiaj” zamiast „sprzed 0 dni”
const ga0 = html.indexOf('function gAgeNote(fresh){');
const ga1 = html.indexOf('\nfunction gRenderKpi(){', ga0);
const ageFor = new Function('t', html.slice(ga0, ga1) + '\nreturn gAgeNote;')(k => k);
const dayIso = (back) => new Date(Date.now() - back * 86400000).toISOString().slice(0, 10);

test('wiek danych: dziś → „dane z dzisiaj”, 1 dzień → g.age1, więcej → g.age; brak daty → nic', () => {
  assert.equal(ageFor(dayIso(0)), ' · g.age0');
  assert.equal(ageFor(dayIso(1)), ' · g.age1');
  assert.equal(ageFor(dayIso(5)), ' · g.age');
  assert.equal(ageFor(''), ''); assert.equal(ageFor('x'), '');
  const d0 = html.indexOf('const EXTRA32='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA32='.length, d1));
  for (const l of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) assert.ok(dict[l]['g.age0'], l);
});

test('Eurosystem: sekcja czyta ilm i m3 z pliku urzędowego, podpis EBC, wiersz Źródła i wpis w prawach', () => {
  assert.ok(html.includes("['tga','rrp','soma','tgb','ilm','m3','bop','mof'].some("), 'klucze pliku (v46 dodało bop)');
  assert.ok(html.includes("const ilm=D.ilm,m3=D.m3,"), 'blok');
  const d0 = html.indexOf('const EXTRA32='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA32='.length, d1));
  for (const l of ['pl', 'en']) assert.ok(dict[l]['inst.ecb.src'].includes('Reproduction is permitted provided the source is acknowledged'), l);
});

// v44: rynek krypto z pliku automatu (open interest, DeFi, Fear & Greed) — brak = brak, wskaźnik podpisany jako model
const kr0 = html.indexOf('function krClass(c){');
const kr1 = html.indexOf('\nfunction renderKr(){', kr0);
const krFns = new Function('t', 'escH', html.slice(kr0, kr1) + '\nreturn {krClass, krFngAt};')(k => k, s => String(s));

test('Fear & Greed: klasy tłumaczone przez klucze, nieznana klasa escapowana; wartość sprzed N dni albo brak', () => {
  assert.equal(krFns.krClass('Extreme Greed'), 'kr.c.xg'); assert.equal(krFns.krClass('Neutral'), 'kr.c.n'); assert.equal(krFns.krClass('Weird'), 'Weird');
  const rows = [['2026-09-22', 78, 'Extreme Greed'], ['2026-09-23', 71, 'Greed'], ['2026-09-24', 71, 'Greed']];
  assert.equal(krFns.krFngAt(rows, 0), 71); assert.equal(krFns.krFngAt(rows, 2), 78); assert.equal(krFns.krFngAt(rows, 7), null);
});

test('rynek krypto: sekcja w CRYPTO po CoinMarketCap, plik krypto.json, atrybucje i wiersze Źródła', () => {
  const c = html.indexOf('<section class="panel pcard" id="cmc" hidden></section>'), k = html.indexOf('<section class="panel pcard" id="krypto" hidden></section>');
  assert.ok(c > 0 && k > c, 'sekcja po #cmc');
  assert.ok(html.includes("srvJSON('krypto')"), 'plik automatu');
  const d0 = html.indexOf('const EXTRA33='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA33='.length, d1));
  for (const l of ['pl', 'en']) { assert.equal(dict[l]['kr.src.cg'], 'Data by CoinGecko'); assert.ok(dict[l]['kr.ind'], l); }
});

// v45: polityka bezpieczeństwa treści — każdy adres, z którym łączy się strona, jest na liście; obce adresy nie
test('CSP: meta obecna, connect-src obejmuje wszystkie hosty pobierane przez stronę, skrypty tylko własne i loader TradingView', () => {
  const m = html.match(/<meta http-equiv="Content-Security-Policy" content="([^"]+)">/);
  assert.ok(m, 'meta CSP');
  const csp = m[1];
  const dir = (name) => (csp.split(';').map(x => x.trim()).find(x => x.startsWith(name + ' ')) || '').slice(name.length + 1).split(/\s+/);
  const connect = dir('connect-src');
  assert.ok(connect.includes("'self'"), 'własne pliki');
  for (const h of ['https://api.coingecko.com', 'https://api.coinpaprika.com', 'https://sdmx.oecd.org', 'https://stablecoins.llama.fi', 'https://api.llama.fi',
    'https://home.treasury.gov', 'https://stats.bis.org', 'https://openapi.sosovalue.com', 'https://api.twelvedata.com', 'https://api.statistiken.bundesbank.de',
    'https://api.frankfurter.dev', 'https://finnhub.io']) assert.ok(connect.includes(h), h);
  // każdy host pobierany fetch-em w kodzie strony (poza tekstami i linkami) musi być dozwolony
  const script = html.slice(html.indexOf('<script>'), html.lastIndexOf('</script>'));
  const fetched = new Set([...script.matchAll(/(?:fetch|gJSON|gText)\((?:[^)]*?)(https:\/\/[a-z0-9.-]+)/g)].map(x => x[1]));
  for (const h of fetched) assert.ok(connect.includes(h), 'fetch bez zezwolenia: ' + h);
  assert.deepEqual(dir('script-src'), ["'self'", "'unsafe-inline'", 'https://s3.tradingview.com']);
  assert.deepEqual(dir('frame-src'), ['https://www.tradingview-widget.com', 'https://www.tradingview.com']);
  assert.deepEqual(dir('object-src'), ["'none'"]); assert.deepEqual(dir('base-uri'), ["'self'"]);
  assert.ok(html.includes('<meta name="referrer" content="no-referrer">'), 'referrer');
});

// v46: bilans płatniczy strefy euro (EBC) — suma 12 mies. tylko z kompletu, znak objaśniony, wiersz Źródła, prawa
const bs0 = html.indexOf('function bopSum(rows,n){');
const bs1 = html.indexOf('\nfunction instRow(', bs0);
const bopFns = new Function('instSign', 'instMld', html.slice(bs0, bs1) + '\nreturn {bopSum, bopMld};')(
  v => v > 0 ? '+' : (v < 0 ? '−' : ''), mln => (Math.round(mln / 100) / 10).toFixed(1));

test('bilans płatniczy: suma 12 miesięcy tylko z kompletu liczb, brak → null; znak przy mld', () => {
  const rows = Array.from({ length: 13 }, (_, i) => ['2025-' + String(i + 1).padStart(2, '0'), 1000]);
  assert.equal(bopFns.bopSum(rows, 12), 12000); assert.equal(bopFns.bopSum(rows, 13), 13000); assert.equal(bopFns.bopSum(rows, 14), null);
  rows[5][1] = null; assert.equal(bopFns.bopSum(rows, 12), null, 'brak w środku → brak sumy');
  assert.equal(bopFns.bopMld(36516), '+36.5'); assert.equal(bopFns.bopMld(-21794), '−21.8'); assert.equal(bopFns.bopMld(0), '0.0'); assert.equal(bopFns.bopMld(null), '—');
});

test('bilans płatniczy: klucz bop w pliku urzędowym, blok, wiersz Źródła, wpis w prawach, znak objaśniony w obu językach', () => {
  assert.ok(html.includes("['tga','rrp','soma','tgb','ilm','m3','bop','mof'].some("), 'klucze');
  assert.ok(html.includes("const bop=D.bop,BS="), 'blok');
  const d0 = html.indexOf('const EXTRA34='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA34='.length, d1));
  assert.ok(dict.pl['inst.bop.sub'].includes('plus = kapitał netto wypływa')); assert.ok(dict.en['inst.bop.sub'].includes('positive = capital flows out'));
  assert.ok(dict.pl['src.l.2m'] && dict.en['src.l.2m']);
});

// v47: TIC — przepływy netto USA ↔ regiony; netto = do − z tylko z kompletu; regiony z niepełnym składem oznaczone
const tc0 = html.indexOf('const ticLast=rows=>');
const tc1 = html.indexOf('\nfunction renderTic(){', tc0);
const ticFns = new Function('bopSum', 't', html.slice(tc0, tc1) + '\nreturn {ticLast, ticVal, ticNet, ticPartial};')(
  (rows, n) => { if (!Array.isArray(rows) || rows.length < n) return null; let s = 0; for (let i = rows.length - n; i < rows.length; i++) { if (typeof rows[i][1] !== 'number') return null; s += rows[i][1]; } return s; },
  (k, v) => k + (v ? ':' + JSON.stringify(v) : ''));

test('TIC: netto do USA = do − z, brak po którejkolwiek stronie → brak; suma 12 mies. z kompletu', () => {
  const mk = (n, v) => Array.from({ length: n }, (_, i) => ['2025-' + String(i + 1).padStart(2, '0'), v, 1]);
  const reg = { n: 1, in: mk(12, 100), out: mk(12, 30) };
  assert.equal(ticFns.ticNet(reg, 0), 70); assert.equal(ticFns.ticNet(reg, 12), 840); assert.equal(ticFns.ticNet(reg, 13), null);
  assert.equal(ticFns.ticNet({ n: 1, in: mk(12, 100), out: null }, 0), null);
  assert.equal(ticFns.ticNet({ n: 1, in: mk(12, 100), out: [['2025-12', null, 0]] }, 0), null);
  assert.equal(ticFns.ticPartial({ n: 5 }, [['2026-07', 10, 3]]), ' <small class="mtxt">(tic.partial:{"k":3,"n":5})</small>');
  assert.equal(ticFns.ticPartial({ n: 5 }, [['2026-07', 10, 5]]), '');
});

test('TIC: sekcja #tic w GLOBAL przed widokami silnika, plik tic.json, karty WITHHELD widoków TIC ukryte, wiersz Źródła, prawa', () => {
  const a = html.indexOf('<section class="panel pcard" id="tic" hidden></section>'), b = html.indexOf('<section class="panel pcard" id="eng-tic-flows" hidden></section>');
  assert.ok(a > 0 && b > a, 'sekcja');
  assert.ok(html.includes("srvJSON('tic')"), 'plik');
  assert.ok(html.includes("if(v.startsWith('tic-')&&!(chk.ok&&chk.state==='BOUND')){el.hidden=true;el.innerHTML='';return;}"), 'karty TIC silnika ukryte, gdy nie BOUND');
  const d0 = html.indexOf('const EXTRA35='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA35='.length, d1));
  for (const l of ['pl', 'en']) for (const k of ['tic.t', 'tic.in', 'tic.out', 'tic.net', 'tic.not2', 'tic.src', 'g.hs.tic']) assert.ok(dict[l][k], l + ' ' + k);
});

// v48: uczciwość — zmiana wyceny to „zmiana wartości”; brak wymyślonych ocen, linii i liczb przykładowych na stronie publicznej
test('v48: słownik nadpisań ma wszystkie 10 języków i nie mówi o „napływie” tam, gdzie liczymy zmianę ceny', () => {
  const d0 = html.indexOf('const EXTRA36='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA36='.length, d1));
  assert.deepEqual(Object.keys(dict).sort(), ['de', 'en', 'es', 'fr', 'it', 'ja', 'pl', 'pt', 'ru', 'zh']);
  for (const l of Object.keys(dict)) for (const k of ['plain.in', 'plain.out', 'g.leg.in', 'g.leg.out', 'q.src.v', 'rail.rel', 'src.f.h', 'src.l.w']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(!/napłynęło|odpłynęło/.test(dict.pl['plain.in'] + dict.pl['plain.out']));
  assert.ok(dict.pl['plain.in'].includes('nie zmierzony napływ'));
  assert.ok(html.indexOf('for(const l in EXTRA36)') > html.indexOf('for(const l in EXTRA_F1415)'), 'nadpisania stosowane na końcu');
});

test('v48: panel jakości CRYPTO liczy fakty (bez gwiazdek i stałych ocen), miernik = pokrycie koszyków', () => {
  const w0 = html.indexOf('function renderWhy(){'), w1 = html.indexOf('\nfunction renderList(', w0);
  const why = html.slice(w0, w1);
  assert.ok(!why.includes('★'), 'bez gwiazdek'); assert.ok(why.includes("t('q.src.v',{k:okN,n:srcs.length})"));
  const g0 = html.indexOf('function renderGauge(){'), g1 = html.indexOf('\n}', g0);
  const gauge = html.slice(g0, g1);
  assert.ok(!gauge.includes('score=42') && !gauge.includes('55+25*'), 'bez wymyślonego wyniku');
  assert.ok(gauge.includes('Math.round(LIVE.cover*100)'));
});

test('v48: scena CRYPTO — bez wymyślonych połączeń i bez linii przykładowych na żywo; stablecoiny z podaży', () => {
  const b0 = html.indexOf('function buildEdges(F){'), b1 = html.indexOf('\nfunction applyLive(', b0);
  assert.ok(!html.slice(b0, b1).includes('ref*.06'), 'bez wymyślonych kwot');
  const a0 = html.indexOf('function applyLive(){'), a1 = html.indexOf('\n}\n', a0);
  assert.ok(!html.slice(a0, a1).includes('EDGES_SAMPLE'), 'applyLive bez próbki');
  assert.ok(html.includes("LIVE.stabD={'24H':dlt('circulatingPrevDay'),'7D':dlt('circulatingPrevWeek'),'30D':dlt('circulatingPrevMonth')};"));
  assert.ok(html.includes(" {id:'btc',p:[9.2,0,0],ev:'proxy',src:'src.asset'},"), 'BTC z ceny = proxy, nie „bezpośredni flow”');
});

test('v48: GLOBAL na stronie publicznej bez OECD pokazuje brak danych, nie liczby przykładowe', () => {
  assert.ok(html.includes("if(location.protocol!=='file:'){F[r.id]=[0,0,false];return;}"));
  assert.ok(html.includes("s2.hidden=live||location.protocol!=='file:';"));
});

test('v48: gfmt i etfM — poniżej 1 mln i poniżej 0,1 mln to nie zero; 999,7 mld to już bilion', () => {
  const f0 = html.indexOf('const gfmt=v=>{'), f1 = html.indexOf('\nconst gpct=', f0);
  const gfmt = new Function('LOCALE', 'LANG', 't', html.slice(f0, f1) + '\nreturn gfmt;')({ pl: 'pl-PL' }, 'pl', k => k);
  assert.ok(gfmt(999.7).endsWith('u.t'), gfmt(999.7)); assert.equal(gfmt(0.0001), '<1 u.m'); assert.equal(gfmt(-0.0001), '−<1 u.m');
  const e0 = html.indexOf('const etfM=v=>{'), e1 = html.indexOf('\nconst etfA=', e0);
  const etfM = new Function('LOCALE', 'LANG', 't', html.slice(e0, e1) + '\nreturn etfM;')({ pl: 'pl-PL' }, 'pl', k => k);
  assert.equal(etfM(0), '0 u.m'); assert.equal(etfM(0.03), '+<0,1 u.m'); assert.equal(etfM(-0.03), '−<0,1 u.m');
});

test('v48: TIC — netto z krajów obecnych w obu tabelach, znacznik niepełnego składu w każdej kolumnie, Tajwan osobno', () => {
  assert.ok(html.includes('function ticNet(reg,back){if(Array.isArray(reg.net))'));
  assert.ok(html.includes("${ticPartial(reg,reg.out)}") && html.includes("${ticPartial(reg,reg.net)}"));
  assert.ok(html.includes("${D.twn?row(I('f','tw')+t('tic.twn'),D.twn):''}"), 'v96: Tajwan osobno, z flagą');
  assert.ok(!html.includes('<b>W przygotowaniu:</b>'), 'Źródła bez nieaktualnego bloku');
});

// v49: prawdziwe 30D/1R, okresy bez danych wyłączone, podaż stablecoinów z serwera, lżejsze odświeżanie, limity czasu
test('v49: 0 z CoinPaprika dla 30D/1R to brak; uzupełnienie z CoinGecko; brak okresu wyłącza przycisk zamiast pokazywać zera', () => {
  assert.ok(html.includes("'30D':nz(q.percent_change_30d),'1R':nz(q.percent_change_1y)"));
  const k0 = html.indexOf('function krMerge(){'), k1 = html.indexOf('\nfunction krLoad(', k0);
  const LIVE = { C: { BTC: { pct: { '24H': -0.2, '7D': 10, '30D': null, '1R': null } }, USDT: { pct: { '30D': 1.5, '1R': null } } } };
  const KR = { data: { mk: { rows: [['BTC', 1, 2, 3, 6.5954, -25.7682], ['USDT', 1, 0, 0, 0.01, 0.02]] }, stabh: { cur: 3e11, d: { '1': 1e8, '7': 7e8, '30': 3e9, '365': 4e10 }, pct: { '1': 0.03, '7': 0.2, '30': 1, '365': 15 } } } };
  new Function('LIVE', 'KR', html.slice(k0 - html.slice(0, k0).lastIndexOf('function krData'), k1).replace(/^[^]*?function krData/, 'function krData') + '\nkrMerge();')(LIVE, KR);
  assert.equal(LIVE.C.BTC.pct['30D'], 6.5954); assert.equal(LIVE.C.BTC.pct['1R'], -25.7682);
  assert.equal(LIVE.C.USDT.pct['30D'], 1.5, 'wartość CoinPaprika (≠0) zostaje'); assert.equal(LIVE.C.USDT.pct['1R'], 0.02);
  assert.equal(LIVE.stabD['1R'].d, 4e10 / 1e6); assert.equal(LIVE.stabD['1R'].pct, 15);
  assert.ok(html.includes("for(const per in PCTF)D[per]=buildPeriod(per);"));
  assert.ok(html.includes("b.disabled=!ok;b.title=ok?'':t('eng.gap');"));
});

test('v49: GLOBAL nie pobiera co minutę 1,3 MB historii stablecoinów, gdy serwer ją ma; zapytania mają limit czasu', () => {
  const a0 = html.indexOf('function gAuto(on){'), a1 = html.indexOf('\n/* BIS:', a0);
  const auto = html.slice(a0, a1);
  assert.ok(auto.includes('(!krStabh()&&due(15))?gJSON(GSRC.stab)'), 'stablecoiny tylko bez pliku serwera i rzadko');
  assert.ok(auto.includes("due(15)?srvJSON('rynki')") && auto.includes("return gJSON(GSRC.fx('latest'))"), 'kursy EBC raz na 15 min (v101: najpierw plik serwera, zapas — prosto)');
  assert.ok(html.includes("function gJSON(u){return fetch(u,{cache:'no-store',signal:fetchTO(30000)})"));
  assert.ok(html.includes("const keepSrc={};['cmc','kr','fng']"), 'pełne odświeżenie nie kasuje cmc/kr/fng');
  assert.ok(html.includes('loadAll(afterLive,true);},5*60*1000)'), 'CRYPTO odświeża się samo');
});

// v50 BIS LBS: zmierzone kwartalne przepływy bankowe między regionami mapy (plik automatu bis.json, miara F)
test('v50 BIS: panel z bis.json — korytarze wg wartości bezwzględnej, brak to „—”, nie zero; tekst z pliku escapowany', () => {
  const b0 = html.indexOf('const BI={data:null};'), b1 = html.indexOf('/* v50 BIS: koniec */', b0);
  assert.ok(b0 > 0 && b1 > b0, 'blok BIS');
  const m0 = html.indexOf('function instMld(mln,dec){'), m1 = html.indexOf('\nfunction instDelta(', m0);
  const s0 = html.indexOf('function bopSum(rows,n){'), s1 = html.indexOf('\nfunction instFoot(', s0);
  const e0 = html.indexOf('function escH(s){'), e1 = html.indexOf('\n', e0);
  assert.ok(m0 > 0 && m1 > m0 && s0 > 0 && s1 > s0 && e0 > 0, 'funkcje pomocnicze');
  const el = { hidden: true, innerHTML: '' }, oks = [];
  const GB_ = Object.fromEntries(['usa', 'can', 'lat', 'eur', 'rus', 'mea', 'afr', 'ind', 'chn', 'jpn', 'asean', 'oce'].map(k => [k, {}]));
  const B = new Function('$', 't', 'GB_', 'gOk', 'engNum', 'engDate', 'LANG',
    html.slice(e0, e1) + '\n' + html.slice(m0, m1) + '\n' + html.slice(s0, s1) + '\nfunction instFoot(d){return escH(d);}\n' + html.slice(b0, b1) +
    '\nreturn {biApply, biTop, biBig, BI};')(
    s => (s === '#bis' ? el : null), (k, v) => k + (v ? ':' + JSON.stringify(v) : ''), GB_, k => oks.push(k), v => String(v), s => 'D(' + s + ')', 'pl');
  const q = ['2025-Q2', '2025-Q3', '2025-Q4', '2026-Q1'];
  const rows = (vals, n) => q.map((qq, i) => [qq, vals[i], vals[i] == null ? 0 : n]);
  const D = { at: '2026-09-24T21:00:00+00:00', asof: '2026-Q1', quarters: q, no_reporter: ['rus', 'x<y'],
    flows: { 'eur>usa': rows([1000, 2000, -13875.2, 302398.2], 8), 'usa>eur': [['2025-Q2', 1, 8], ['2025-Q3', 2, 8], ['2025-Q4', 3, 7], ['2026-Q1', 67331.6, 8]], 'jpn>usa': rows([null, 5, 6, 111551.3], 2),
      'chn>usa': rows([1, 1, 1, -18637.6], 1), 'eur>rus': rows([1, 1, 1, 500], 3), 'zzz>usa': rows([1, 1, 1, 9e9], 1), 'usa>usa': rows([1, 1, 1, 8e9], 1),
      'can>usa': rows([1, 1, 1, null], 1) },
    regions: {
      eur: { rep: ['GB', '<img src=x>'], cp: ['GB', 'DE'], out: rows([1, 1, 1, 537011.8], 217), in: rows([1, 1, 1, 133006.3], 88), net: rows([98620.6, 68661.2, -50462.1, 311770.6], 83), net4: 428590.3, rep_q: [['GB', 194782.4, 1], ['<b>', 1, 1]] },
      usa: { rep: ['US'], cp: ['US'], out: rows([1, 1, 1, 71473.6], 36), in: rows([1, 1, 1, 395125.1], 18), net: rows([1, 1, 1, -342007.6], 18), net4: -897369.9, rep_q: [] },
      rus: { rep: [], cp: ['RU'], out: rows([null, null, null, null], 0), in: rows([1, 1, 1, -1278.3], 14), net: rows([null, null, null, null], 0), net4: null, rep_q: [] } } };
  const top = B.biTop(D, 10, id => !!GB_[id]);
  assert.deepEqual(top.map(c => c.a + '>' + c.b), ['eur>usa', 'jpn>usa', 'usa>eur', 'chn>usa', 'eur>rus'], 'nieznany region, ten sam region i brak liczby pominięte');
  assert.deepEqual(B.biBig(D, 4, id => !!GB_[id]), ['usa', 'eur'], 'region bez salda nie jest „największy”');
  B.biApply(D);
  assert.equal(el.hidden, false); assert.deepEqual(oks, ['bis2']);
  const h = el.innerHTML;
  assert.ok(h.includes('bis2.t') && h.includes('bis2.sign') && h.includes('bis2.netplain'));
  assert.ok(h.includes('<span class="cell mono">+302,4</span>') && h.includes('<span class="cell mono">−18,6</span>'), 'mld USD ze znakiem');
  assert.ok(h.includes('bis2.s4:{"v":"+428,6 inst.mld.usd"}') && h.includes('bis2.pairs:{"n":83}'), 'suma 4 kwartałów i liczba par w kafelku');
  const r0 = h.indexOf('<span class="cell">g.n.rus<small'), rus = h.slice(r0, h.indexOf('</tr>', r0));
  assert.ok(r0 > 0, 'wiersz Rosji w tabeli sald');
  assert.ok(rus.includes('bis2.norep') && rus.includes('>—<') && !/>[+−]?0(,0)?</.test(rus), 'Rosja: brak = „—”, nie zero');
  const jpn = h.slice(h.indexOf('g.n.jpn → g.n.usa'), h.indexOf('</tr>', h.indexOf('g.n.jpn → g.n.usa')));
  assert.equal((jpn.match(/>—</g) || []).length, 1, 'suma 4 kwartałów bez kompletu = „—”');
  const er = h.slice(h.indexOf('g.n.eur → g.n.rus'), h.indexOf('</tr>', h.indexOf('g.n.eur → g.n.rus')));
  assert.ok(er.includes('bis2.oneway'), 'drugi kierunek bez raportu oznaczony');
  assert.ok(er.includes('>+&lt;0,1<') && !er.includes('+0,0'), '1 mln USD to „<0,1 mld”, nie zero');
  const ue = h.slice(h.indexOf('g.n.usa → g.n.eur'), h.indexOf('</tr>', h.indexOf('g.n.usa → g.n.eur')));
  assert.ok(ue.includes('bis2.pairs:{"n":7}') && ue.includes('bis2.pairsr:{"a":7,"b":8}'), '_fix: zmienny skład par oznaczony przy poprzednim kwartale i sumie');
  const eu = h.slice(h.indexOf('g.n.eur → g.n.usa'), h.indexOf('</tr>', h.indexOf('g.n.eur → g.n.usa')));
  assert.ok(!eu.includes('bis2.pairsr') && !eu.includes('bis2.pairs:'), '_fix: stały skład bez oznaczeń');
  const kp = h.slice(h.indexOf('<div class="etfkpis">'), h.indexOf('</div><p class="pnote">bis2.netplain'));
  assert.ok(kp.includes('bis2.rep:{"c":"US"}') && kp.includes('bis2.rep:{"c":"GB, &lt;img src=x&gt;"}'), '_fix: kafelki z listą krajów raportujących (escapowaną)');
  assert.ok(!h.includes('<img src=x>') && h.includes('&lt;img src=x&gt;') && h.includes('&lt;b&gt;') && !h.includes('x<y'), 'escapowanie');
  assert.ok(h.includes('bis2.not3b:{"r":"g.n.rus"}'), 'regiony bez raportujących z pliku');
  assert.ok(!h.includes('zzz') && !h.includes('9e9') && !h.includes('9 000'), 'nieznany region pominięty');
  B.biApply({ at: 'x' }); assert.equal(el.hidden, true); assert.equal(el.innerHTML, '');
  B.biApply(null); assert.equal(el.hidden, true); assert.deepEqual(oks, ['bis2']);
});

test('v50 BIS: sekcja #bis po #tic, plik bis.json w GLOBAL, język, wiersz Źródła, atrybucja BIS, prawa, słownik PL/EN', () => {
  const a = html.indexOf('<section class="panel pcard" id="tic" hidden></section>'), b = html.indexOf('<section class="panel pcard" id="bis" hidden></section>');
  assert.ok(a > 0 && b > a, 'sekcja po TIC');
  assert.ok(html.includes("srvJSON('bis').then(j=>{biApply(j);}).catch(()=>{biApply(null);}),"), 'plik');
  assert.ok(html.indexOf("srvJSON('bis')") > html.indexOf('function gLoad(cb){'), 'w gLoad');
  assert.ok(html.includes("if(typeof renderBis==='function')renderBis();"), 'zmiana języka');
  const d0 = html.indexOf('const EXTRA39='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA39='.length, d1));
  const b0 = html.indexOf('const BI={data:null};'), b1 = html.indexOf('/* v50 BIS: koniec */', b0);
  const used = [...new Set([...html.slice(b0, b1).matchAll(/t\('(bis2\.[a-z0-9.]+)'/g)].map(x => x[1]))];
  assert.ok(used.length > 20, 'klucze panelu');
  for (const l of ['pl', 'en']) for (const k of used.concat(['g.hs.bis2'])) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['bis2.src'].includes('nieoficjalne tłumaczenie') && dict.pl['bis2.src'].includes('nie popiera'), 'atrybucja zgodna z warunkami BIS');
  assert.ok(dict.en['bis2.src'].includes('unofficial translations'));
  assert.ok(html.indexOf('for(const l in EXTRA39)') > html.indexOf('for(const l in EXTRA38)'), 'słownik po EXTRA38');
});

// v50 CFTC: panele EURO FX i krypto z data/cftc.json (rejestr ENG_OVR); brak pliku/rynku → widok silnika; brak liczby = „—”
const cf0 = html.indexOf('/* v50: CFTC — Traders in Financial Futures wprost z cftc.gov');
const cf1 = html.indexOf('/* v50: CFTC — koniec bloku */', cf0);
const cfEsc = new Function(html.slice(html.indexOf('function escH(s){'), html.indexOf('\n', html.indexOf('function escH(s){'))) + '\nreturn escH;')();
const cfEnv = () => {
  const env = { ENG_OVR: {}, oks: [], renders: 0 };
  const deps = {
    ENG_OVR: env.ENG_OVR, t: (k, v) => k + (v ? ':' + JSON.stringify(v) : ''), nfmt: v => String(v),
    instSign: v => v > 0 ? '+' : (v < 0 ? '−' : ''), escH: cfEsc, gAgeNote: d => ' · age(' + d + ')',
    instRow: (l, v, e, n) => `<div class="etfk"><span>${l}</span><b>${v}</b><small class="mtxt">${n}</small></div>`,
    instFoot: d => cfEsc(d) + ' · age', engK: (l, v) => `<div class="etfk wrap"><span>${l}</span><b>${v}</b></div>`,
    engDate: s => 'D(' + s + ')', engPeriod: p => 'P(' + p.value + ')', gOk: k => env.oks.push(k),
    srvJSON: () => Promise.resolve(null), renderEng: () => { env.renders++; }, document: { hidden: false },
    setInterval: () => 7, clearInterval: () => {},
  };
  const names = Object.keys(deps);
  Object.assign(env, new Function(...names, html.slice(cf0, cf1) + '\nreturn {CFTC, cftcApply, cftcMkt, cftcS, cftcN};')(...names.map(n => deps[n])));
  return env;
};
const cfMkt = (over = {}) => Object.assign({
  code: '099741', name: 'EURO FX - CHICAGO MERCANTILE EXCHANGE', units: '(CONTRACTS OF EUR 125,000)', asof: '2026-09-15', in_week_file: true, oi: 920035, oi_chg: -22429,
  groups: { dealer: { long: 41113, short: 299193, spread: 5144, net: -258080, chg_net: 3374 }, asset_mgr: { long: 486435, short: 234737, spread: 43899, net: 251698, chg_net: 1020 },
    lev_funds: { long: 103260, short: 131416, spread: 23388, net: -28156, chg_net: 5129 }, other_rept: { long: 24818, short: 17063, spread: 0, net: 7755, chg_net: null },
    nonrept: { long: 188399, short: 161616, spread: null, net: 26783, chg_net: -9103 } },
  hist: { dates: ['2026-09-08', '2026-09-15'], oi: [942464, 920035], dealer: [-261454, -258080], asset_mgr: [250678, 251698], lev_funds: [-33285, -28156], other_rept: [8175, null], nonrept: [35886, 26783] },
}, over);

test('v50 CFTC: bez pliku albo bez rynku panele oddają miejsce widokowi silnika; zły plik nie kasuje wczytanego', () => {
  const E = cfEnv(), el = { hidden: true, innerHTML: 'silnik' };
  assert.equal(E.ENG_OVR['cftc-euro-fx'](el), false); assert.equal(E.ENG_OVR['cftc-crypto'](el), false); assert.equal(el.innerHTML, 'silnik');
  E.cftcApply(null); assert.equal(E.oks.length, 0); assert.equal(E.renders, 1);
  E.cftcApply({ at: '2026-09-24T20:00:00+00:00', markets: { eur: null, btc: { asof: '2026-13-45', groups: {} }, eth: { asof: '2026-09-15' } } });
  assert.equal(E.oks.length, 0, 'plik bez poprawnego rynku to nie „źródło działa”');
  assert.equal(E.ENG_OVR['cftc-euro-fx'](el), false); assert.equal(E.ENG_OVR['cftc-crypto'](el), false);
  E.cftcApply({ at: '2026-09-24T20:00:00+00:00', markets: { eur: cfMkt() } }); assert.deepEqual(E.oks, ['cftc']);
  E.cftcApply(null); assert.ok(E.cftcMkt('eur'), 'chwilowy błąd sieci nie kasuje danych'); assert.equal(E.oks.length, 1);
});

test('v50 CFTC: panel EURO FX — netto ze znakiem, brak to „—” (nie 0), prawdziwe 0 zostaje, historia od najnowszego, tekst z pliku escapowany', () => {
  const E = cfEnv(), el = { hidden: true, innerHTML: '' };
  E.cftcApply({ at: '2026-09-24T20:00:00+00:00', markets: { eur: cfMkt({ units: '<img src=x onerror=alert(1)>' }) } });
  assert.equal(E.ENG_OVR['cftc-euro-fx'](el), true); assert.equal(el.hidden, false);
  const h = el.innerHTML;
  assert.ok(h.includes('<h2>eng.t.cftc-euro-fx</h2>') && h.includes('cftc.state:'), 'tytuł silnika i stan');
  assert.ok(h.includes('<div class="etfk wrap"><span>cftc.rep</span><b>P(2026-09-15)</b>') && h.includes('cftc.pub:{"d":"P(2026-09-18)"}'), 'data raportu (wtorek) i publikacji (piątek)');
  assert.ok(h.includes('<span class="cell mono">−258080</span>') && h.includes('<span class="cell mono">+3374</span>'), 'netto i zmiana dealerów ze znakiem');
  assert.ok(h.includes('<b>+251698</b>') && h.includes('<b>−28156</b>') && h.includes('<b>920035</b>'), 'KPI: netto zarządzających i funduszy, otwarte kontrakty');
  assert.ok(h.includes('<td><span class="cell mono">0</span></td>'), 'spreading 0 z raportu zostaje zerem');
  const nonrept = h.slice(h.indexOf('cftc.g.nonrept'), h.indexOf('</tr>', h.indexOf('cftc.g.nonrept')));
  assert.ok(nonrept.includes('>—<') && !nonrept.includes('>0<'), 'brak spreadingu małych graczy to „—”');
  assert.ok(h.includes('cftc.chg:{"v":"+1020"}') && h.includes('cftc.chg:{"v":"−22429"}'), 'zmiana tygodniowa ze znakiem');
  const other = h.slice(h.indexOf('cftc.g.other_rept'), h.indexOf('</tr>', h.indexOf('cftc.g.other_rept')));
  assert.ok(other.endsWith('<span class="cell mono">—</span></td>'), 'brak zmiany netto to „—”, nie 0');
  assert.ok(h.includes('&lt;img src=x onerror=alert(1)&gt;') && !h.includes('<img'), 'jednostka z pliku przez escH');
  assert.ok(h.indexOf('P(2026-09-15)</span></td>') < h.indexOf('P(2026-09-08)</span></td>'), 'najnowszy raport u góry');
  assert.ok(h.includes('cftc.hist:{"n":2}') && h.includes('eng.notsays') && h.includes('cftc.disc'));
  assert.ok(!h.includes('cftc.src') && !h.includes('eng.k.src') && !h.includes('href="https://www.cftc.gov'), 'v96: źródło i link tylko na stronie Źródła');
  assert.equal(E.cftcS(0), '0'); assert.equal(E.cftcS(null), '—'); assert.equal(E.cftcS(NaN), '—'); assert.equal(E.cftcN(undefined), '—');
});

test('v50 CFTC: stan z poniedziałku (tydzień ze świętem) — publikacja to najbliższy piątek, nie czwartek', () => {
  const E = cfEnv(), el = { hidden: true, innerHTML: '' };
  E.cftcApply({ at: '2025-11-20T20:00:00+00:00', markets: { eur: cfMkt({ asof: '2025-11-10', hist: { dates: ['2025-11-10'], oi: [1], dealer: [1], asset_mgr: [1], lev_funds: [1], other_rept: [1], nonrept: [1] } }) } });
  assert.equal(E.ENG_OVR['cftc-euro-fx'](el), true);
  assert.ok(el.innerHTML.includes('cftc.pub:{"d":"P(2025-11-14)"}'), 'poniedziałek 10.11 → piątek 14.11');
  E.cftcApply({ at: '2026-09-24T20:00:00+00:00', markets: { eur: cfMkt() } });
  assert.equal(E.ENG_OVR['cftc-euro-fx'](el), true);
  assert.ok(el.innerHTML.includes('cftc.pub:{"d":"P(2026-09-18)"}'), 'wtorek 15.09 → piątek 18.09');
});

test('v50 CFTC: panel krypto — jeden rynek wystarczy, brak drugiego opisany (nie zera); poprzedni stan oznaczony', () => {
  const E = cfEnv(), el = { hidden: true, innerHTML: '' };
  const btc = cfMkt({ code: '133741', units: '(5 Bitcoins)', oi: 20773, kept: true, asof: '2026-09-08' });
  E.cftcApply({ at: '2026-09-24T20:00:00+00:00', markets: { eur: null, btc, eth: null } });
  assert.equal(E.ENG_OVR['cftc-euro-fx'](el), false);
  assert.equal(E.ENG_OVR['cftc-crypto'](el), true);
  const h = el.innerHTML;
  assert.ok(h.includes('<b>cftc.mkt.btc</b>') && h.includes('<b>cftc.mkt.eth</b>'));
  assert.ok(h.includes('eng.r.MARKET_MISSING'), 'brak ETH opisany');
  assert.ok(h.includes('cftc.kept'), 'stan z poprzedniego pobrania oznaczony');
  assert.ok(h.includes('cftc.u.btc:{"u":"(5 Bitcoins)"}'));
});

test('v50 CFTC: plik w gLoad po TIC, zegar, wiersze Źródła (GLOBAL i CRYPTO), prawa, słownik PL/EN', () => {
  const tic = html.indexOf("srvJSON('tic').then(j=>{ticApply(j);})"), cf = html.indexOf("srvJSON('cftc').then(j=>{cftcApply(j);})");
  const gl0 = html.indexOf('function gLoad(cb){'), gl1 = html.indexOf('Promise.all(P).then(', gl0);
  assert.ok(gl0 < tic && tic < cf && cf < gl1, 'plik cftc.json wczytywany w gLoad po TIC');
  assert.ok(cf0 > html.indexOf('const ENG_OVR={};') && cf1 > cf0, 'rejestracja po ENG_OVR, przed renderEng');
  const d0 = html.indexOf('const EXTRA40='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA40='.length, d1));
  assert.deepEqual(Object.keys(dict.pl).sort(), Object.keys(dict.en).sort());
  for (const l of ['pl', 'en']) for (const k of ['cftc.how', 'cftc.u.eth', 'cftc.not1', 'cftc.src', 'g.hs.cftc', 'cftc.g.nonrept']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(/50 eth/.test(dict.en['cftc.u.eth']) && /50 etherów/.test(dict.pl['cftc.u.eth']) && /gotówkowo/.test(dict.pl['cftc.u.eth']));
});

// v50 cm: Coin Metrics — wpłaty i wypłaty BTC/ETH na giełdy z pliku cm.json; karta widoku przejęta przez ENG_OVR
const cmSrc0 = html.indexOf('/* v50: Coin Metrics Community (plik automatu cm.json)');
const cmSrc1 = html.indexOf('/* v50 cm: koniec */', cmSrc0);
const cmEsc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const cmMake = () => {
  const ENG_OVR = {}, oks = [], calls = { render: 0 };
  const api = new Function('ENG_OVR', 't', 'instSign', 'nfmt', 'gfmt', 'gpct', 'instRow', 'instFoot', 'escH', 'engDate', 'engNum', 'gOk', 'srvJSON', 'renderEng',
    html.slice(cmSrc0, cmSrc1) + '\nreturn {CM, cmOk, cmApply, cmPanel, cmCoin, cmUsd, cmSign, cmTable, cmBack};')(
    ENG_OVR, (k, v) => k + (v ? ':' + JSON.stringify(v) : ''), v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), v => v.toFixed(1) + ' u.b',
    v => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(2) + '%', (l, v, e, n) => `[${l}|${v}|${e}|${n}]`, d => cmEsc(d), cmEsc, iso => 'F(' + iso + ')', v => String(v),
    k => oks.push(k), () => Promise.resolve(null), () => { calls.render++; });
  return { api, ENG_OVR, oks, calls };
};
const cmSample = () => ({ at: '2026-09-24T20:40:00+00:00', cols: ['date', 'in', 'out', 'net', 'in_usd', 'out_usd', 'net_usd', 'sply', 'sply_usd'],
  assets: { btc: { sym: 'BTC', asof: '2026-09-23', status: 'flash', pending: '2026-09-24', missing: 0,
    last: { in: 22387.65, out: 32444.54, net: -10056.9, in_usd: 1890285677, out_usd: 2739432938, net_usd: -849147261, sply: 2695208.79, sply_usd: 227568118688 },
    sum7: { net: -34394.79, net_usd: -2925524045 }, sum30: { net: null, net_usd: null },
    sply_ch7: { ntv: -20434.46, pct: -0.75 }, sply_ch30: { ntv: null, pct: null },
    d: [['2026-09-22', 1, 2, 3.5, 10, 20, 7000000, 5, 50], ['2026-09-23', 22387.65, 32444.54, -10056.9, 1890285677, 2739432938, -849147261, 2695208.79, 227568118688]] },
    eth: null } });

test('v50 cm: brak pliku zostawia kartę silnika; plik z danymi rysuje panel, gOk(cm) i renderEng', () => {
  const m = cmMake();
  const el = { hidden: true, innerHTML: 'silnik' };
  assert.equal(m.ENG_OVR['coinmetrics-exchange-flows'](el), false); assert.equal(el.innerHTML, 'silnik');
  assert.equal(m.api.cmOk(null), false); assert.equal(m.api.cmOk({ at: 'x', assets: { btc: null, eth: null } }), false);
  assert.equal(m.api.cmOk({ assets: { btc: { asof: '2026-09-23' } } }), false, 'bez pola at');
  assert.equal(m.api.cmOk({ at: 'x', assets: { btc: { asof: '<b>' } } }), false, 'zła data');
  m.api.cmApply(cmSample());
  assert.deepEqual(m.oks, ['cm']); assert.equal(m.calls.render, 1);
  assert.equal(m.ENG_OVR['coinmetrics-exchange-flows'](el), true); assert.equal(el.hidden, false);
  assert.ok(el.innerHTML.includes('<h2>cm.t</h2>'));
  m.api.cmApply(null); assert.equal(m.api.CM.data, null); assert.equal(m.ENG_OVR['coinmetrics-exchange-flows'](el), false);
});

test('v50 cm: netto z pola net (nie z zaokrąglonych wpłat i wypłat), podpis ze znaku, brak = „—” i „brak danych”, nigdy 0', () => {
  const m = cmMake(), h = m.api.cmPanel(cmSample());
  assert.ok(h.includes('[cm.in|22388 BTC|inst.exact:{"v":"22387.65 BTC"}|cm.usd:{"v":"1.9 u.b"}]'), 'wpłynęło');
  assert.ok(h.includes('[cm.net|−10057 BTC|inst.exact:{"v":"−10056.90 BTC"}|cm.s.out · cm.usd:{"v":"−0.8 u.b"}]'), 'netto dnia z pola net');
  assert.ok(!h.includes('10056.89'), 'nie liczymy netto z zaokrąglonych');
  assert.ok(h.includes('[cm.net7|−34395 BTC|inst.exact:{"v":"−34394.79 BTC"}|cm.s.out · cm.win:{"n":7,"d":"2026-09-23"} · cm.usd:{"v":"−2.9 u.b"}]'));
  assert.ok(h.includes('[cm.net30|—||eng.gap]'), 'brak sumy 30 dni to brak, nie zero');
  assert.ok(h.includes('[cm.ch7|−20434 BTC (−0.75%)|inst.exact:{"v":"−20434.46 BTC"}|cm.z.down:{"n":7,"d":"2026-09-16"}]'));
  assert.ok(h.includes('[cm.ch30|—||eng.gap]'));
  assert.ok(h.includes('<h3 class="mtxt"><b>cm.btc</b> · cm.day 2026-09-23 · cm.flash</h3>'), 'dzień danych + wiek + wstępne');
  assert.ok(h.includes('cm.pending:{"d":"2026-09-24"}'));
  assert.ok(h.includes('<h3 class="mtxt"><b>cm.eth</b></h3>') && h.includes('[cm.net|—||eng.gap]'), 'ETH bez danych');
  assert.equal(m.api.cmCoin(null, 'BTC', true), null); assert.equal(m.api.cmUsd(undefined, true), null);
  assert.equal(m.api.cmSign(3), 'cm.s.in'); assert.equal(m.api.cmSign(-3), 'cm.s.out'); assert.equal(m.api.cmSign(0), 'cm.s.eq'); assert.equal(m.api.cmSign(null), '');
  assert.equal(m.api.cmCoin(12.5, 'ETH', true), '+12.50 ETH'); assert.equal(m.api.cmBack('2026-09-23', 30), '2026-08-24');
});

test('v50 cm: tabela 14 dni w <details>, czego nie mówi, atrybucja z licencją, tekst z pliku przez escH', () => {
  const m = cmMake(), D = cmSample();
  D.assets.btc.pending = '<img src=x>';
  D.assets.btc.d = Array.from({ length: 20 }, (_, i) => ['2026-09-' + String(i + 4).padStart(2, '0'), 1, 1, i % 2 ? null : -i, 1, 1, null, 1, 1]);
  const h = m.api.cmPanel(D);
  assert.ok(!h.includes('<img') && h.includes('&lt;img src=x&gt;'), 'pending przez escH');
  const tab = m.api.cmTable(D);
  assert.ok(tab.startsWith('<details class="etfd"><summary>cm.tab</summary><div class="list-wrap"><table class="etft">'));
  assert.equal((tab.match(/<tr>/g) || []).length, 15, 'nagłówek + 14 dni');
  assert.ok(tab.includes('2026-09-23') && !tab.includes('2026-09-09'), 'najnowsze 14 dni');
  assert.ok(tab.includes('<td><span class="cell mono">—</span></td>'), 'brak = —');
  assert.ok(!tab.includes('>0 BTC<') && tab.includes('−18.00 BTC'), 'bez wymyślonych zer');
  const ns = h.indexOf('<details class="etfd"><summary>eng.notsays</summary>');
  assert.ok(ns > 0); for (const k of ['cm.not1', 'cm.not2', 'cm.not3', 'cm.not4', 'cm.not5']) assert.ok(h.indexOf(k, ns) > ns, k);
  // v96: podpis Coin Metrics i licencja CC BY-NC — w menu „Źródła” i w stopce strony, nie w panelu; w panelu zostaje sposób liczenia
  assert.ok(!h.includes('coinmetrics.io') && !h.includes('creativecommons.org') && h.includes('<p class="pnote">cm.src</p>'));
  assert.ok(h.includes('<p class="pfoot">inst.file:{"t":"F(2026-09-24T20:40:00+00:00)"} · cm.disc</p>'));
});

test('v50 cm: plik cm.json w gLoad i osobny zegar, wiersz Źródła CRYPTO, atrybucja, prawa, słownik EXTRA41 (PL, EN)', () => {
  assert.ok(html.includes("srvJSON('cm').then(j=>{cmApply(j);}).catch(()=>{cmApply(null);}),"), 'gLoad');
  assert.ok(html.includes('krLoad();krAuto();tvInit();\n') && html.includes('\ncmLoad();cmAuto();   /* v50: Coin Metrics'), 'start i zegar');
  assert.ok(html.includes('},30*60*1000);}   /* dane dzienne: co 30 min wystarczy */'), 'co 30 min');
  assert.ok(!html.includes('Coin Metrics (wpłaty BTC i ETH na giełdy — licencja niekomercyjna) i DefiLlama'), 'zdanie „nie pokazujemy” zaktualizowane');
  assert.ok(!html.includes('; Coin Metrics, DefiLlama (sieci) · <i>nie pokazujemy</i>'));
  assert.ok(html.includes('<section class="panel pcard" id="eng-coinmetrics-exchange-flows" hidden></section>'), 'sekcja bez zmian');
  const d0 = html.indexOf('const EXTRA41='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA41='.length, d1));
  for (const l of ['pl', 'en']) for (const k of ['cm.t', 'cm.sub', 'cm.in', 'cm.out', 'cm.net', 'cm.s.in', 'cm.s.out', 'cm.tab', 'cm.not1', 'cm.not2', 'cm.not3', 'cm.src', 'cm.disc', 'g.hs.cm']) assert.ok(dict[l][k], l + ' ' + k);
  assert.equal(Object.keys(dict.pl).sort().join(), Object.keys(dict.en).sort().join(), 'te same klucze PL i EN');
  assert.ok(html.indexOf('const EXTRA41=') > html.indexOf('for(const l in EXTRA38)'), 'po EXTRA38');
});

// v50 (fedimf): Fed H.4.1 — papiery w depozycie Fed dla zagranicznych instytucji oficjalnych; rezerwy walutowe MFW
const fm0 = html.indexOf('/* v50 (fedimf) początek: Fed H.4.1');
const fm1 = html.indexOf('/* v50 koniec (fedimf) */', fm0);
const fmT = (k, v) => k + (v ? JSON.stringify(v) : '');
const fmEsc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmCalls = { ok: [], render: 0 };
const fm = new Function('t', 'escH', 'engDate', 'engNum', 'nfmt', 'instRow', 'instFoot', 'instMld', 'instSign', 'gOk', 'renderInst', 'LANG',
  html.slice(fm0, fm1) + '\nreturn {fredWk, fredCust, fredCustRows, fredCustKpis, fredCustTable, REZ, rezRows, rezApply, rezHtml, rezD, rezBn};')(
  fmT, fmEsc, x => 'D(' + x + ')', v => String(v), (v, d) => Number(v).toFixed(d || 0),
  (l, v, e, n) => `<div class="etfk"><span>${l}</span><b>${v}</b>${n ? `<small class="mtxt">${n}</small>` : ''}</div>`,
  d => fmEsc(d), mln => (Math.round(mln / 100) / 10).toFixed(1), v => v > 0 ? '+' : (v < 0 ? '−' : ''),
  k => fmCalls.ok.push(k), () => { fmCalls.render++; }, 'pl');
const fmS = (d) => ({ d });
const fmSeries = {   // prawdziwe stany środowe H.4.1 (mln USD); 2026-08-26 celowo brak w WSEFINTL1
  WSEFINTL1: fmS([['2026-08-19', 2864974], ['2026-09-02', 2877129], ['2026-09-09', 2865365], ['2026-09-16', 2884717]]),
  WMTSECL1: fmS([['2026-09-09', 2590095], ['2026-09-16', 2608821]]),
  WFASECL1: fmS([['2026-09-16', 202071]]),
  WSEFINOL: fmS([['2026-09-16', 73825]]),
};

test('v50: depozyt Fed — zmiana tylko od środy dokładnie 7 dni wcześniej, brak części = brak, nie zero', () => {
  assert.equal(fm.fredWk('2026-09-16'), '2026-09-09'); assert.equal(fm.fredWk('x'), '');
  const R = fm.fredCustRows(fmSeries, 8);
  assert.deepEqual(R[0], ['2026-09-16', 2884717, 2608821, 202071, 73825, 19352]);
  assert.deepEqual(R[1], ['2026-09-09', 2865365, 2590095, null, null, -11764]);
  assert.deepEqual(R[2], ['2026-09-02', 2877129, null, null, null, null], 'poprzednia środa 2026-08-26 nie istnieje → brak, nie zmiana od 08-19');
  assert.equal(R.length, 4); assert.deepEqual(fm.fredCustRows({}, 8), []); assert.deepEqual(fm.fredCustRows(null, 8), []);
  assert.equal(fm.fredCust({ custody: { total: 'x', asof: '2026-09-16' } }), null); assert.equal(fm.fredCust(null), null);
});

test('v50: depozyt Fed — kafelki z liczbami H.4.1, udział Skarbu USA, brak pliku = brak danych; tabela i „czego nie mówi”', () => {
  const C = { asof: '2026-09-16', total: 2884717, ust: 2608821, d1w: 19352, d4w: 19743, d52w: -234533, ust_d1w: 18726, ust_d52w: -183831,
    ust_share_pct: 90.4, parts_ok: true, lo52: ['2026-08-19', 2864974], hi52: ['2025-09-17', 3119250] };
  const k = fm.fredCustKpis({ custody: C, series: fmSeries });
  assert.ok(k.includes('<span>inst.fred.cust</span><b>2884.7 inst.mld.usd</b>'), k);
  assert.ok(k.includes('inst.fred.cust.ch{"w":"+19.4","m":"+19.7","y":"−234.5"}'), 'zmiana stanu na środę');
  assert.ok(k.includes('inst.fred.cust.share{"p":"90.4"}') && k.includes('<b>2608.8 inst.mld.usd</b>'), 'Skarb USA');
  assert.equal(k.split('inst.fred.wed 2026-09-16').length - 1, 2, 'data stanu przy obu kafelkach (razem i Skarb USA)');
  const k0 = fm.fredCustKpis({ series: {} });
  assert.ok(k0.includes('<b>—</b>') && k0.includes('eng.gap') && !/\d/.test(k0.replace(/inst\.fred\.cust/g, '')), 'bez pliku: brak, nie zero');
  const tb = fm.fredCustTable({ custody: C, series: fmSeries });
  assert.ok(tb.includes('inst.fred.cust.plain') && tb.includes('inst.fred.cust.not1') && tb.includes('<details class="etfd">'));
  assert.ok(tb.includes('<td><span class="cell mono">+19352</span></td>') && tb.includes('inst.fred.cust.range'));
  assert.ok(!tb.includes('inst.fred.cust.parts'), 'części sumują się');
  assert.ok(fm.fredCustTable({ custody: Object.assign({}, C, { parts_ok: false }), series: fmSeries }).includes('inst.fred.cust.parts'));
  assert.ok(!/NaN|undefined/.test(k + tb));
});

test('v50: rezerwy MFW — kraje bez sumy pominięte, znak przy zmianach, brak = „—”, nazwy i kody escapowane', () => {
  const R = { at: '2026-09-24T21:00:00+00:00', order: ['CHN', 'JPN', 'X<b>'], missing: ['TWN'], countries: {
    CHN: { pl: 'Chiny', en: 'China', asof: '2026-06', total: 3786.1, fx: 3416.3, gold: 303.7, d1m: -64.1, d12m: 158.5, p12m: 4.4 },
    JPN: { pl: 'Japonia', en: 'Japan', asof: '2026-08', total: 1207.5, fx: 1010.8, gold: null, d1m: -79.6, d12m: null, p12m: null },
    'X<b>': { pl: '<i>zły</i>', total: null } } };
  assert.deepEqual(fm.rezRows(R).map(x => x[0]), ['CHN', 'JPN']);
  assert.equal(fm.rezD(-64.1), '−64.1'); assert.equal(fm.rezD(0), '0.0'); assert.equal(fm.rezD(null), '—'); assert.equal(fm.rezBn(undefined), '—');
  const h = fm.rezHtml(R);
  assert.ok(h.includes('<span class="cell">Chiny <span class="cell mono">CHN</span></span>'));
  assert.ok(h.includes('<span class="cell mono">3786.1</span>') && h.includes('<span class="cell mono">−64.1</span>') && h.includes('+158.5 <small class="mtxt">(+4.4%)</small>'));
  assert.ok(h.includes('<td><span class="cell mono">—</span></td>'), 'Japonia bez złota → —');
  assert.ok(h.includes('<span class="cell mono">2026-06</span>') && h.includes('<span class="cell mono">2026-08</span>'), 'miesiąc per kraj');
  assert.ok(h.includes('rez.note') && h.includes('rez.missing{"c":"TWN"}') && h.includes('inst.file'));
  assert.ok(!h.includes('rez.src') && !h.includes('data.imf.org'), 'v96: źródło i link tylko na stronie Źródła');
  assert.ok(!h.includes('<i>zły</i>') && !/NaN|undefined/.test(h));
  assert.equal(fm.rezHtml(null), ''); assert.equal(fm.rezHtml({ order: ['CHN'], countries: { CHN: { total: 'x' } } }), '');
  fm.rezApply({ at: 'x', order: ['CHN'], countries: { CHN: { total: 1 } } }); assert.deepEqual(fmCalls.ok, ['imf']); assert.ok(fm.REZ.data);
  fm.rezApply({ order: ['CHN'], countries: { CHN: { total: 1 } } }); assert.equal(fm.REZ.data, null, 'bez „at” plik odrzucony'); assert.equal(fmCalls.render, 2);
});

test('v50: rezerwy i depozyt Fed wpięte w sekcję danych urzędowych, plik rezerwy.json, wiersz Źródła, atrybucja MFW, słownik pl/en', () => {
  const r0 = html.indexOf('function renderInst(){'), r1 = html.indexOf('\n/* v37: Twelve Data TYLKO', r0), ri = html.slice(r0, r1);
  assert.ok(ri.includes("if(!INST.data&&!FRED.data&&!REZ.data&&!xtra.length){el.hidden=true;el.innerHTML='';return;}"), 'sekcja także z samymi rezerwami');
  const b3 = ri.indexOf('/* B3. bilans płatniczy strefy euro'), b4 = ri.indexOf('html+=rezHtml(REZ.data);'), c = ri.indexOf('/* C. Japonia');
  assert.ok(b3 > 0 && b4 > b3 && c > b4, 'rezerwy po bilansie płatniczym, przed Japonią');
  const f0 = ri.indexOf("const walcl=sr('WALCL')"), fk = ri.indexOf('html+=fredCustKpis(F);'), ft = ri.indexOf('html+=fredCustTable(F);'), fs = ri.indexOf("${t('inst.file',{t:engDate(F.at)})}", ft);
  assert.ok(f0 > 0 && fk > f0 && ft > fk && fs > ft, 'depozyt w bloku FRED');
  assert.ok(!ri.includes("t('inst.fred.src')") && !ri.includes("t('inst.fred.api')") && !ri.includes("t('inst.nyfed')"), 'v96: zdania o źródłach tylko na stronie Źródła');
  const tl = html.indexOf("srvJSON('tic').then(j=>{ticApply(j);})"), rl = html.indexOf("srvJSON('rezerwy').then(j=>{rezApply(j);}).catch(()=>{rezApply(null);}),");
  assert.ok(tl > 0 && rl > tl, 'plik rezerwy.json w gLoad');
  const d0 = html.indexOf('const EXTRA42='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA42='.length, d1));
  const keys = Object.keys(dict.pl);
  assert.deepEqual(Object.keys(dict.en), keys, 'te same klucze pl/en');
  for (const l of ['pl', 'en']) {
    for (const k of keys) assert.ok(typeof dict[l][k] === 'string' && dict[l][k].length > 1, l + ' ' + k);
    for (const sid of ['WSEFINTL1', 'WMTSECL1', 'WFASECL1', 'WSEFINOL']) assert.ok(dict[l]['inst.fred.src'].includes(sid) && dict[l]['g.hs.fred'].includes(sid), l + ' ' + sid);
    assert.ok(dict[l]['inst.fred.src'].includes('Board of Governors of the Federal Reserve System (US), via FRED'));
    assert.ok(dict[l]['rez.src'].includes('International Monetary Fund, International Liquidity (IL)'));
  }
  assert.ok(dict.pl['inst.fred.cust'] === 'Papiery w depozycie Fed dla zagranicznych instytucji oficjalnych (H.4.1)');
  assert.ok(dict.pl['inst.fred.sub'].startsWith('Osiem serii') && dict.en['inst.fred.sub'].startsWith('Eight'));
  assert.ok(dict.pl['inst.fred.cust.plain'].includes('To nie wszystkie obligacje USA za granicą') && dict.pl['inst.fred.cust.plain'].includes('minus = papierów ubyło (sprzedaż, wykup w terminie'));
  assert.ok(dict.pl['rez.note'].includes('to nie to samo co interwencje') && dict.en['rez.note'].includes('not the same as intervention'));
  assert.ok(dict.pl['rez.c.d12'].includes('w nawiasie %') && dict.en['rez.c.d12'].includes('% in brackets'), 'kolumna 12 mies.: mld USD, % w nawiasie');
  const ex = html.indexOf('for(const l in EXTRA38)'), e42 = html.indexOf('for(const l in EXTRA42)if(I18N[l])Object.assign(I18N[l],EXTRA42[l]);');
  assert.ok(ex > 0 && e42 > ex, 'EXTRA42 nakładany po EXTRA38');
});

// v51: stan źródeł z meta.json, czas pliku zamiast chwili pobrania, wiek dla zakresu miesięcy
test('v51: instFoot bierze koniec zakresu dat; strona Źródła pokazuje czas pliku serwera i błąd ostatniego przebiegu', () => {
  const f0 = html.indexOf('function instFoot(d){'), f1 = html.indexOf('\n', f0);
  const instFoot = new Function('escH', 'gAgeNote', html.slice(f0, f1) + '\nreturn instFoot;')(s => String(s), s => '|' + s);
  assert.equal(instFoot('2026-06 – 2026-07'), '2026-06 – 2026-07|2026-07'); assert.equal(instFoot('2026-09-16'), '2026-09-16|2026-09-16');
  const m0 = html.indexOf('function metaErr(k){'), m1 = html.indexOf('\n}', html.indexOf('return e||t(', m0)) ;
  const GLIVE = { meta: { ok: { fred: false, tic: 'cached', krypto: true }, errors: ['FRED WALCL: HTTP 500', 'TIC: x'] } };
  const metaErr = new Function('GLIVE', 't', html.slice(m0, html.indexOf('return e||t(', m0)) + "return e||t('src.m.err');}\nreturn metaErr;")(GLIVE, k => k);
  assert.equal(metaErr('fred'), 'FRED WALCL: HTTP 500'); assert.equal(metaErr('tic'), null, 'z pamięci to nie błąd'); assert.equal(metaErr('kr'), null);
  assert.ok(html.includes('metaLoad();setInterval('), 'meta.json wczytywany i odświeżany');
});

// v52: stopy banków centralnych — tabela w sekcji banków centralnych, wiersz w szczegółach regionu, brak = „—”
test('v52: stopy banków centralnych: formatowanie, różnica wobec Fed, wiersz regionu i Źródła', () => {
  assert.ok(html.includes("srvJSON('stopy')") && html.includes('html+=spBlock();') && html.includes('${spRegion(s.id)}'));
  const p0 = html.indexOf('const spPct='), p1 = html.indexOf('\nfunction spRegion(', p0);
  const f = new Function('nfmt', 'instSign', html.slice(p0, p1) + '\nreturn {spPct, spPP};')((v, d) => v.toFixed(d), v => v > 0 ? '+' : (v < 0 ? '−' : ''));
  assert.equal(f.spPct(3.875), '3.875'); assert.equal(f.spPct(2.5), '2.50'); assert.equal(f.spPct(1), '1.00'); assert.equal(f.spPct(null), '—');
  assert.equal(f.spPP(-1.375), '−1.375'); assert.equal(f.spPP(0), '0'); assert.equal(f.spPP(0.25), '+0.25'); assert.equal(f.spPP(undefined), '—');
  const d0 = html.indexOf('const EXTRA44='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA44='.length, d1));
  for (const l of ['pl', 'en']) for (const k of ['sp.t', 'sp.sub', 'sp.src', 'sp.cc.XM', 'sp.cc.US', 'g.hs.sp']) assert.ok(dict[l][k], l + ' ' + k);
});

// v53: jedno okno czasu na liczbę mapy (średnie EBC tych samych miesięcy co OECD), baza, BIS w korytarzach, BOP w podpowiedzi
test('v53: kurs ze średnich miesięcznych EBC z tych samych miesięcy co indeks OECD; bez pliku = kurs dzienny, oznaczony', () => {
  const a0 = html.indexOf('const KM={data:null};'), a1 = html.indexOf('function gIdxRatio(r,n){', a0);
  const oks = [];
  const f = new Function('GLIVE', 'gOk', html.slice(a0, a1) + '\nreturn {KM, kmApply, kmUsd, gWin, gFxRatioM, gNoFx, gFrozen, gFrozenN};')(
    {oecd: {JPN: [['2026-05', 100], ['2026-06', 101], ['2026-07', 102], ['2026-08', 103]], KOR: [['2026-07', 50], ['2026-08', 51]],
            RUS: [['2026-04', 190.936], ['2026-05', 190.936], ['2026-06', 190.936], ['2026-07', 190.936], ['2026-08', 190.936]]}}, k => oks.push(k));
  const jpn = {iso: ['JPN', 'KOR'], w: [7611, 2757], fx: [['JPY', 7611], ['KRW', 2757]]};
  assert.equal(f.gFxRatioM(jpn, 1), null, 'bez pliku kursy.json = null (strona użyje kursu dziennego)');
  f.kmApply({at: '2026-09-25T00:00:00+00:00', m: {USD: [['2026-07', 1.15], ['2026-08', 1.16]], JPY: [['2026-07', 172.5], ['2026-08', 185.6]]}});
  assert.deepEqual(oks, ['kursy']);
  assert.deepEqual(f.gWin(jpn, 1), ['2026-08', '2026-07'], 'miesiące z kraju o największej wadze');
  assert.ok(Math.abs(f.kmUsd('JPY', '2026-08') - 160) < 1e-9 && Math.abs(f.kmUsd('EUR', '2026-07') - 1 / 1.15) < 1e-12 && f.kmUsd('USD', 'x') === 1);
  const r = f.gFxRatioM(jpn, 1);   // KRW brak w pliku → pominięty jak w gFxRatio; JPY: 150 (07) → 160 (08) = słabszy jen
  assert.equal(r.a, '2026-08'); assert.equal(r.b, '2026-07'); assert.ok(Math.abs(r.v - 150 / 160) < 1e-12);
  assert.equal(f.gFxRatioM({iso: ['USA'], w: [1], fx: [['USD', 1]]}, 1), null, 'region w dolarach: nic do przeliczenia');
  assert.equal(f.gFxRatioM(jpn, 3), null, 'KOR ma za krótką serię, JPN ma — ale brak kursów z maja = null');
  f.kmApply({at: 'x', m: {JPY: []}}); assert.equal(f.KM.data, null, 'plik bez USD odrzucony');
  assert.equal(f.gFrozenN([['a', 1], ['b', 2], ['c', 2]]), 2); assert.equal(f.gFrozen([['a', 1], ['b', 2], ['c', 2]]), false);
  assert.equal(f.gWin({iso: ['RUS'], w: [1], fx: []}, 1), null, 'zamrożony indeks (Rosja) nie daje okna — brak, nie 0 %');
  assert.ok(html.includes('function gCtyIdx(S,w){if(!Array.isArray(S)||!S.length||gFrozen(S))return null;'), 'v62: indeks kraju pomija zamrożony');
  assert.ok(html.includes('const R=gRegRatio(r,n,per),wn=gWin(r,n);') && html.includes("k:R?R.k:null,out:R?R.out:[]"));
  assert.ok(html.includes("(F.fxm?'OECD · EBC':'OECD')") && html.includes("srvJSON('kursy')"));
  assert.ok(html.includes('stopy:()=>SP.data&&SP.data.at,kursy:()=>KM.data&&KM.data.at') && html.includes("stopy:'BIS stopy',kursy:'EBC kursy'"), 'Źródła: czas pliku i błąd serwera dla stóp i kursów');
});

test('v53: szczegóły — okno czasu, źródło bazy, zmierzone BIS w korytarzu; BOP z dokładną wartością w podpowiedzi', () => {
  const d0 = html.indexOf('/* v53: okno czasu i źródło bazy'), d1 = html.indexOf('function gProbBox(id){', d0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const BI = {data: {asof: '2026-Q1', no_reporter: ['rus'], flows: {'usa>eur': [['2025-Q2', -42215.3, 8], ['2025-Q3', 128750.6, 8], ['2025-Q4', -23252.5, 8], ['2026-Q1', 67331.6, 8]]}}};
  const GDATA = {'1Q': {fxw: {jpn: {a: '2026-08', b: '2026-05', k: 'm'}}}};
  const gFrozenN = s => { let k = 1; for (let i = s.length - 1; i > 0 && s[i][1] === s[i - 1][1]; i--) k++; return k; }, gFrozen = s => gFrozenN(s) >= 4;
  const GLIVE = {oecd: {JPN: [['2026-08', 1]], KOR: [['2026-08', 2]], RUS: [1, 2, 3, 4, 5].map(i => ['m' + i, 190.936]), USA: [['2026-08', 3]]}};
  const GB_ = {usa: {iso: ['USA']}, eur: {iso: ['DEU']}, rus: {iso: ['RUS']}, jpn: {iso: ['JPN', 'KOR']}, mea: {iso: ['SAU', 'USA']}};
  GDATA['1Q'].fxw.usa = {a: '2026-08', b: '2026-05', k: 'u'};
  const f = new Function('t', 'escH', 'GDATA', 'gst', 'BI', 'GB_', 'GLIVE', 'gFrozen', 'gFrozenN', 'instSign', 'instMld', 'bopMld', 'biRow', 'biV', 'bopSum', 'instFoot', html.slice(d0, d1) + '\nreturn {gWinRow, gBaseRow, biEdgeRow};')(
    T, s => String(s), GDATA, {period: '1Q'}, BI, GB_, GLIVE, gFrozen, gFrozenN, v => v > 0 ? '+' : (v < 0 ? '−' : ''), v => (v / 1000).toFixed(1), v => (v / 1000).toFixed(1),
    (rows, back) => rows[rows.length - 1 - back], r => r ? r[1] : null, (rows, n) => rows.slice(-n).reduce((a, r) => a + r[1], 0), s => s);
  assert.ok(f.gWinRow('jpn').includes('g.win.m{"a":"2026-08","b":"2026-05"}') && !f.gWinRow('jpn').includes('g.win.out'));
  assert.ok(f.gWinRow('usa').includes('g.win.u'), 'region w dolarach: okno bez przeliczenia');
  const ru = f.gWinRow('rus'); assert.ok(!ru.includes('<dt>g.win</dt>') && ru.includes('<dt>g.win.out</dt>') && ru.includes('g.win.fz{"c":"RUS","n":5}'), 'Rosja: zamrożony indeks opisany, bez okna');
  assert.ok(f.gWinRow('mea').includes('g.win.miss{"c":"SAU"}'), 'kraj bez indeksu OECD opisany');
  GDATA['1Q'].fxw = undefined; assert.equal(f.gWinRow('rus'), '', 'okres z ETF-ów (bez OECD): bez wierszy o OECD');
  assert.ok(f.gBaseRow('eur').includes('FR 2018, GB 2022, IT 2014, NL 2017, SE 2003') && f.gBaseRow('mea').includes('"c":"IL"') && f.gBaseRow('usa').includes('g.d.basey.v'));
  const e = f.biEdgeRow('usa', 'eur');
  assert.ok(e.includes('bi.e.v') && e.includes('"q":"2026-Q1"') && e.includes('"v":"67.3 inst.mld.usd"') && e.includes('"s":"130.6 inst.mld.usd"'), e);
  assert.ok(e.includes('bi.e.none'), 'brak kierunku eur>usa = brak danych, nie zero');
  assert.ok(f.biEdgeRow('rus', 'usa').includes('bi.e.norep'), 'region bez raportujących banków');
  assert.equal(f.biEdgeRow('usa', 'xx'), '');
  assert.ok(html.includes('${gWinRow(s.id)}') && html.includes('${gBaseRow(s.id)}') && html.includes('${biEdgeRow(e.f,e.t)}'));
  assert.ok(html.includes("${v[2]?t(v[0]>0?'g.plain.in':v[0]<0?'g.plain.out':'gmap.plain.zero'") && html.includes(":t('g.plain.none',{n:t('g.n.'+s.id)"), 'brak danych nie jest opisany jako wzrost o 0 (v96: dokładne zero — „nie zmieniła się”)');
  assert.ok(html.includes('<td><span class="cell mono"${atT(k,p)}>${at(k,p)}</span></td>'), 'BOP: dokładna wartość w podpowiedzi');
  const x0 = html.indexOf('const EXTRA45='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA45='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['g.win', 'g.win.m', 'g.win.u', 'g.win.d', 'g.win.out', 'g.win.fz', 'g.win.miss', 'g.plain.none', 'g.src.regm', 'g.d.basey.v', 'bi.e.v', 'bi.e.none', 'bi.e.norep', 'g.hs.km']) assert.ok(dict[l][k], l + ' ' + k);
});

// v54: zmierzone dzienne przepływy inwestorów zagranicznych (Indie, Tajwan) — sumy tylko z pełnego okna, brak = „—”
test('v54: inwestorzy zagraniczni: wczytanie, sumy okien, blok, wiersz regionu Indii, Źródła', () => {
  const a0 = html.indexOf('const ZAG={data:null};'), a1 = html.indexOf('function renderInst(){', a0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'instRow', 'instFoot', 'engNum', 'engDate', 'escH', html.slice(a0, a1) + '\nreturn {ZAG, zagApply, zagSum, zagM, zagB, zagBlock, zagRegion};')(
    T, k => oks.push(k), () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), (a, b, c, d) => `[${a}|${b}|${c}|${d}]`, s => s, v => String(v), s => s, s => String(s));
  assert.equal(f.zagSum([['a', 1], ['b', 2]], 1, 3), null, 'za krótka historia = brak sumy');
  assert.equal(f.zagSum([['a', 1], ['b', null], ['c', 2]], 1, 2), null, 'dziura w oknie = brak sumy, nie zero');
  assert.equal(f.zagSum([['a', 1], ['b', 2], ['c', 3]], 1, 2), 5);
  assert.equal(f.zagM(-270.67), '−271'); assert.equal(f.zagM(5.17), '+5.2'); assert.equal(f.zagM(null), '—'); assert.equal(f.zagB(-32964.6), '−33.0');
  f.zagApply({at: 'x', in: {d: []}}); assert.equal(f.ZAG.data, null, 'plik bez dni odrzucony');
  f.zagApply({at: '2026-09-25T00:00:00+00:00', in: {d: [['2026-09-23', -270.67, -24.91, null, -290.42, 95.8], ['2026-09-24', 754.19, 46.98, -0.19, 806.15, 95.7]]},
             tw: {d: [['2026-09-24', -32964.6, -12823.3, 1338.4, -44449.4, -1036, '2026-09-18']]}});
  assert.deepEqual(oks, ['obce_in', 'obce_tw']);
  const b = f.zagBlock();
  assert.ok(b.includes('[ob.in.k|+806 inst.mln.usd|') && b.includes('"e":"+754","d":"+47"') && b.includes('ob.sn{"n":2,"v":"+516"}'), 'Indie: kafelek, podział, suma z dostępnych dni (2) z ich liczbą');
  assert.ok(b.includes('[ob.tw.k|−33.0 ob.mld.twd|') && b.includes('ob.tw.usd{"v":"−1036","d":"2026-09-18"}'));
  assert.ok(b.includes('<td><span class="cell mono">2026-09-23</span></td>') && (b.match(/<tr>/g) || []).length >= 3, 'tabela: dzień bez sesji na Tajwanie = —');
  assert.ok(f.zagRegion('ind').includes('ob.reg.v') && f.zagRegion('chn') === '', 'wiersz tylko dla Indii');
  f.zagApply({at: 'x', tw: {d: [['2026-09-24', 1, 1, 1, 1, null, null]]}});
  assert.ok(f.zagBlock().includes('[ob.in.k|—||eng.gap]') && !f.zagBlock().includes('ob.tw.usd'), 'brak części Indii = brak, bez przeliczenia bez kursu');
  assert.ok(html.includes('html+=zagBlock();') && html.includes("srvJSON('obce')") && html.includes('${zagRegion(s.id)}'));
  assert.ok(html.includes("obce_in:'NSDL',obce_tw:'TWSE'") && html.includes('obce_in:()=>ZAG.data&&ZAG.data.in&&ZAG.data.in.at'));
  const x0 = html.indexOf('const EXTRA46='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA46='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ob.t', 'ob.sub', 'ob.in.k', 'ob.tw.k', 'ob.not', 'ob.src', 'ob.reg.v', 'g.hs.nsdl', 'g.hs.twse']) assert.ok(dict[l][k], l + ' ' + k);
});

// v56: kursy efektywne BIS obok stóp — kolumna w tabeli stóp, wiersz w szczegółach regionu; brak = „—”
test('v56: kursy efektywne BIS: format, komórka tabeli stóp, wiersz regionu, Źródła', () => {
  const a0 = html.indexOf('const EER={data:null};'), a1 = html.indexOf('function spRegion(id){', a0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'instFoot', 'escH', html.slice(a0, a1) + '\nreturn {EER, eerApply, eerPct, eerCell, eerRegion};')(
    T, k => oks.push(k), () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), s => s, s => String(s));
  assert.equal(f.eerCell('JP'), '—', 'bez pliku = brak'); assert.equal(f.eerRegion('jpn'), '');
  f.eerApply({at: '2026-09-25T00:00:00+00:00', rows: {JP: {v: 69.16, d: '2026-09-22', c30: 1.62, m: '2026-08', c12: -2.5}, KR: {v: 92, d: '2026-09-22', c30: null, c12: 0}}});
  assert.deepEqual(oks, ['eer']);
  assert.equal(f.eerPct(1.62), '+1.6%'); assert.equal(f.eerPct(0), '0%'); assert.equal(f.eerPct(null), '—');
  assert.equal(f.eerCell('JP'), '+1.6% · −2.5%'); assert.equal(f.eerCell('KR'), '— · 0%'); assert.equal(f.eerCell('US'), '—');
  const r = f.eerRegion('jpn');
  assert.ok(r.includes('eer.reg.v{"c":"JPY","a":"+1.6%","b":"−2.5%","m":"2026-08"} · 2026-09-22') && r.includes('"c":"KRW","a":"—","b":"0%"'), r);
  assert.equal(f.eerRegion('usa'), '', 'region bez danych w pliku = bez wiersza');
  assert.ok(html.includes('<td><span class="cell mono"><span>${eerCell(a)}</span></span></td></tr>') && html.includes("<th>${t('sp.c.fx')}</th></tr></thead>"));
  assert.ok(html.includes('${eerRegion(s.id)}') && html.includes("srvJSON('eer')"));
  assert.ok(html.includes("eer:'BIS kursy efektywne'") && html.includes('eer:()=>EER.data&&EER.data.at'));
  const x0 = html.indexOf('const EXTRA47='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA47='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['sp.c.fx', 'eer.not', 'eer.src', 'eer.reg', 'eer.reg.v', 'g.hs.eer']) assert.ok(dict[l][k], l + ' ' + k);
});

// v57: bilans przepływu w krypto — cztery rodzaje miar osobno (bez sumowania), brak = „—”, ukryty bez danych
test('v57: bilans krypto: linie z rodzajem, datą; brak = —; bez danych ukryty; tytuł sekcji instytucji', () => {
  const a0 = html.indexOf('function cBal(){'), a1 = html.indexOf('function renderEtf(){', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const el = {hidden: true, innerHTML: ''};
  const run = (ETF, H, CMd, M) => new Function('$', 't', 'ETF', 'etfTotals', 'etfM', 'etfCls', 'krStabh', 'gfmt', 'CM', 'cmA', 'cmIs', 'cmUsd', 'cftcMkt', 'cftcS', 'instFoot',
    html.slice(a0, a1) + '\ncBal();')(() => el, T, ETF, D => ({m: D.m}), v => v == null ? '—' : String(v), v => v > 0 ? 'pos' : (v < 0 ? 'neg' : ''), () => H, v => v.toFixed(2) + ' mld',
    {data: CMd}, (D, a) => D.assets[a] || null, v => typeof v === 'number' && isFinite(v), (v, s) => (v > 0 ? '+' : '−') + (Math.abs(v) / 1e9).toFixed(1) + ' mld',
    k => M[k] || null, v => v == null ? '—' : String(v), d => d);
  run({data: null}, null, null, {});
  assert.equal(el.hidden, true, 'bez żadnych danych — panel ukryty'); assert.equal(el.innerHTML, '');
  run({data: {assets: {}, m: 5100, asof: '2026-09-23'}}, {asof: '2026-09-24', d: {'30': 2458885594}}, {assets: {btc: {asof: '2026-09-23', sum30: {net_usd: -2e9}}, eth: {asof: '2026-09-23', sum30: {net_usd: null}}}},
      {btc: {asof: '2026-09-15', groups: {asset_mgr: {net: 1234}}}});
  const h = el.innerHTML;
  assert.equal(el.hidden, false);
  assert.ok(h.includes('cb.etf: <b class="pos">5100</b>') && h.includes('cb.k.meas · 2026-09-23'), 'ETF: pomiar przepływu z datą');
  assert.ok(h.includes('cb.stab: <b class="pos">+2.46 mld</b>') && h.includes('cb.k.sply · 2026-09-24'));
  assert.ok(h.includes('cb.ex: <b class="">—</b>') && h.includes('cb.k.chain · cb.ex.n · 2026-09-23'), 'brak ETH = brak sumy giełd, nie połowa');
  assert.ok(h.includes('cb.cme.v{"b":"<span class=\\"pos\\">1234</span>","e":"—"}') && h.includes('cb.k.pos · 2026-09-15'), 'CME: pozycje, nie przepływ; v98.2: długie netto zielone, brak bez koloru');
  assert.ok(html.includes('<section class="panel etf-rail" id="c-bal" hidden></section>') && html.includes("function renderKr(){if(typeof cBal==='function')cBal();"));
  const x0 = html.indexOf('const EXTRA48='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA48='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['cb.t', 'cb.sub', 'cb.etf', 'cb.stab', 'cb.ex', 'cb.cme', 'cb.k.pos', 'inst.t', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['inst.sub'].includes('BIS') && dict.pl['inst.sub'].includes('Tajwan'));
});

// v58: stablecoiny per sieć zamiast wstrzymanej karty; panele silnika w języku widza (słownik wg widoku, nazwy krajów z ISO)
test('v58: stablecoiny per sieć — panel z pliku, brak = —; karta silnika tylko bez danych', () => {
  const a0 = html.indexOf('function stcPanel(S,H){'), a1 = html.indexOf("ENG_OVR['coinmetrics-exchange-flows']=el=>", a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const ENG_OVR = {}, KR = {data: null};
  let H = null;
  const f = new Function('t', 'gfmt', 'engDate', 'instRow', 'instFoot', 'engNum', 'escH', 'KR', 'krData', 'krStabh', 'ENG_OVR', html.slice(a0, a1) + '\nreturn {stcPanel};')(
    T, v => v.toFixed(2) + ' mld', s => String(s), (a, b, c, d) => `[${a}|${b}|${d}]`, s => s, v => String(v), s => String(s), KR, () => KR.data, () => H, ENG_OVR);
  const el = {hidden: true, innerHTML: ''};
  assert.equal(ENG_OVR['defillama-stablecoins'](el), true); assert.equal(el.hidden, true, 'v63: bez pliku panel ukryty (bez karty „bez zgody”)');
  KR.data = {at: 'x', stabc: {asof: '2026-09-25', n: 180, total: [313e9, 1e8, 2e9, 3.6e9], rows: [['Ethereum', 147.6e9, 0, -0.19e9, -0.19e9], ['Solana', 17.6e9, 0, 1.88e9, null]]}};
  H = {asof: '2026-09-24', cur: 311e9, d: {'7': 1.47e9, '30': 2.46e9}};
  assert.equal(ENG_OVR['defillama-stablecoins'](el), true); assert.equal(el.hidden, false);
  const h = el.innerHTML;
  assert.ok(h.includes('[stc.k.tot|311.00 mld|stc.day{"d":"2026-09-24"}]') && h.includes('[stc.k.d30|+2.46 mld|]'), 'sumy z tej samej serii co reszta strony');
  assert.ok(h.includes('stc.tab{"n":2,"t":"180"}') && h.includes('<span class="cell mono neg">−0.19 mld</span>') && h.includes('<span class="cell mono ">—</span>'), 'brak = —');
  assert.ok(html.includes('if(typeof renderEng===\'function\')renderEng();   /* v58'));
});

test('v58: panele silnika po angielsku — teksty wg widoku, wiek z liczbą miesięcy, nazwy krajów z ISO, bez „Texts … in Polish”', () => {
  const a0 = html.indexOf('const ISO32='), a1 = html.indexOf('function engKpis(rec){', a0);
  const x0 = html.indexOf('const EXTRA49='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA49='.length, x1));
  let LANG = 'en';
  const t = (k, o) => { let s = dict[LANG] && dict[LANG][k] !== undefined ? dict[LANG][k] : (dict.en[k] !== undefined ? dict.en[k] : k); if (o) for (const v in o) s = s.split('{' + v + '}').join(o[v]); return s; };
  const mk = () => new Function('LANG', 'LOCALE', 't', html.slice(a0, a1) + '\nreturn {engCty, engTx, engAge, engAttr, engRights, engLim, ISO32};');
  const rec = {view: 'wdi-destinations', kind_pl: 'Przepływ', says_pl: 'PL', data_age: {phrase_pl: 'Dane roczne …; w chwili pobrania miały 20 mies.'}, attribution: 'Źródło: …', rights: {sentence_pl: 'Licencja …'}, limitations_pl: ['a', 'b']};
  const en = mk()('en', {en: 'en-GB'}, t);
  assert.equal(en.engTx(rec, 'kind'), 'Flow'); assert.ok(en.engTx(rec, 'says').startsWith('Annual net inflow'));
  assert.equal(en.engAge(rec), 'Annual data, published with a lag; at capture they were 20 months old.');
  assert.ok(en.engAttr(rec).startsWith('Source: World Bank') && en.engRights(rec).startsWith('CC BY 4.0') && en.engLim(rec).length === 9);
  assert.equal(en.engTx({view: 'nowy-widok', says_pl: 'tylko PL'}, 'says'), 'tylko PL', 'brak słownika dla widoku — tekst źródłowy, nie pusto');
  assert.equal(en.engAge({view: 'wdi-destinations', data_age: {phrase_pl: 'bez liczby'}}), 'bez liczby', 'bez liczby miesięcy — tekst źródłowy');
  assert.equal(en.ISO32.CYM, 'KY'); assert.equal(en.ISO32.TWN, 'TW'); assert.equal(en.ISO32.CHI, undefined, 'kod spoza ISO pominięty');
  const n = en.engCty('ZZZ', 'Nieznany', 'Unknown'); assert.equal(n, 'Unknown', 'brak kodu ISO — nazwa angielska u źródła');
  const pl = mk()('pl', {pl: 'pl-PL'}, t);
  assert.equal(pl.engTx(rec, 'kind'), 'Przepływ'); assert.equal(pl.engCty('IRL', 'Irlandia', 'Ireland'), 'Irlandia'); assert.deepEqual(pl.engLim(rec), ['a', 'b']);
  assert.ok(!dict.en['eng.disclaimer'].includes('Polish'));
  assert.ok(html.includes("escH(engCty(r.code,r.name_pl,r.name))") && html.includes("escH(C(engTx(rec,'kind')))") && html.includes('engLim(rec).map('), 'v96: tekst z pliku przez engTx, gtEngClean (C) i escH');
  for (const k of ['stc.t', 'stc.sub', 'stc.not', 'stc.src']) assert.ok(dict.pl[k] && dict.en[k], k);
});

// v59: MFW COFER — udziały walut w rezerwach świata; brak = „—”
test('v59: COFER: tabela udziałów, zmiany, „inne waluty”, stopka z udziałem przypisanych, Źródła', () => {
  const a0 = html.indexOf('const COF={data:null};'), a1 = html.indexOf('function renderInst(){', a0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'escH', 'engDate', 'instFoot', html.slice(a0, a1) + '\nreturn {COF, cofApply, cofHtml};')(
    T, k => oks.push(k), () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), s => String(s), s => String(s), s => String(s));
  assert.equal(f.cofHtml(null), '');
  f.cofApply({at: 'x', asof: '2025-Q2', alloc: 12400, total: 13000, alloc_pct: 95.4, imp_pct: 10.65, order: ['USD', 'EUR', 'OTHC'],
              rows: {USD: {sh: 56.32, d1: -1.48, d4: -1.88, v: 7000, dv4: 100}, EUR: {sh: 20.1, d1: null, d4: null, v: null, dv4: null}, OTHC: {sh: 5.5, d1: 0, d4: 0.3, v: 700, dv4: -2}}});
  assert.deepEqual(oks, ['cofer']);
  const h = f.cofHtml(f.COF.data);
  assert.ok(h.includes('<td><span class="cell mono">56.32</span></td><td><span class="cell mono">−1.48</span></td><td><span class="cell mono">−1.88</span></td><td><span class="cell mono">7000 <small class="mtxt">(+100)</small></span></td>'), h);
  assert.ok(h.includes('<td><span class="cell">EUR</span></td><td><span class="cell mono">20.10</span></td><td><span class="cell mono">—</span></td>'), 'brak zmiany = —');
  assert.ok(h.includes('<span class="cell">cof.oth</span>') && h.includes('cof.foot{"q":"2025-Q2","a":"12400","i":"10.7"}'));
  f.cofApply({at: 'x', asof: 'q', rows: {}, order: []}); assert.equal(f.COF.data, null, 'plik bez walut odrzucony');
  assert.ok(html.includes('html+=cofHtml(COF.data);') && html.includes("srvJSON('cofer')") && html.includes("cofer:'MFW COFER'"));
  const x0 = html.indexOf('const EXTRA50='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA50='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['cof.t', 'cof.sub', 'cof.foot', 'cof.foot0', 'cof.not', 'cof.src', 'g.hs.cofer']) assert.ok(dict[l][k], l + ' ' + k);
});

// v60: strona Źródła zgodna z decyzją właściciela (bez obietnic zgody/wyłączenia) i ze stanem strony (nowe źródła, silnik = 2 panele)
test('v60: tekst Źródeł: bez „wystąpimy o zgodę / wyłączymy”, wpisy nowych źródeł, prawdziwy opis paneli silnika', () => {
  // v103: długi opis źródeł (TXT_ZRODLA_PL) usunięty ze strony Źródła — została karta stanu „na żywo” (testy v103-zrodla na końcu pliku)
  assert.ok(!html.includes('const TXT_ZRODLA_PL=') && !html.includes('function txtZrodla('), 'v103: bez dawnego opisu źródeł');
});

// v62: mapa — średnia ważona ZMIAN krajów (nie poziomów), każdy kraj z własną walutą i tymi samymi miesiącami
test('v62: region = średnia ważona zmian; kraj bez miesiąca / bez kursu poza średnią; kurs dzienny oznaczony; Indie z bazą 2024', () => {
  const a0 = html.indexOf('const KM={data:null};'), a1 = html.indexOf('function gFxRatio(r,per){', a0);
  const GLIVE = {oecd: {
    TUR: [['2026-05', 1700], ['2026-06', 1720], ['2026-07', 1740], ['2026-08', 1753]],
    ISR: [['2026-05', 300], ['2026-06', 295], ['2026-07', 292], ['2026-08', 290]],
    COL: [['2026-04', 100], ['2026-05', 101], ['2026-06', 102], ['2026-07', 103]],
    USA: [['2026-05', 100], ['2026-06', 101], ['2026-07', 102], ['2026-08', 110]]}, fx: null};
  const f = new Function('GLIVE', 'gOk', html.slice(a0, a1) + '\nreturn {KM, kmApply, gRegRatio, gIdxRatio, gWin, GCUR};')(GLIVE, () => {});
  const mea = {iso: ['SAU', 'TUR', 'ISR'], w: [2359, 404, 331]};
  // bez kursów EBC i dziennych: TUR/ISR poza średnią (brak kursu), SAU bez indeksu → brak liczby
  assert.equal(f.gRegRatio(mea, 3, '1Q'), null);
  f.kmApply({at: 'x', m: {USD: [['2026-05', 1], ['2026-08', 1]], TRY: [['2026-05', 40], ['2026-08', 44]], ILS: [['2026-05', 4], ['2026-08', 4]]}});
  const R = f.gRegRatio(mea, 3, '1Q');
  const tur = (1753 / 1700) * (40 / 44), isr = (290 / 300) * 1, want = (404 * tur + 331 * isr) / (404 + 331);
  assert.ok(Math.abs(R.v - want) < 1e-12, 'średnia ważona zmian (nie poziomów)'); assert.equal(R.k, 'm'); assert.deepEqual([R.a, R.b], ['2026-08', '2026-05']);
  const old = ((404 * 1753 + 331 * 290) / (404 * 1700 + 331 * 300));   // dawna średnia poziomów — inna liczba
  assert.ok(Math.abs(f.gIdxRatio(mea, 3) - (404 * 1753 / 1700 + 331 * 290 / 300) / 735) < 1e-12 && Math.abs(f.gIdxRatio(mea, 3) - old) > 1e-4);
  const lat = {iso: ['USA', 'COL'], w: [10, 5]};
  const L = f.gRegRatio(lat, 3, '1Q');
  assert.deepEqual(L.out, [['COL', 'nomonth']], 'Kolumbia bez sierpnia — poza średnią, nie jako sierpień');
  assert.equal(L.k, 'u'); assert.ok(Math.abs(L.v - 1.1) < 1e-12);
  f.kmApply({at: 'x', m: {USD: [['2026-05', 1], ['2026-08', 1]]}});
  GLIVE.fx = {now: {rates: {TRY: 44}}, '1Q': {rates: {TRY: 40}}};
  const D = f.gRegRatio(mea, 3, '1Q');
  assert.equal(D.k, 'd', 'kurs dzienny — oznaczony'); assert.deepEqual(D.out, [['ISR', 'nofx', 'ILS']]);
  assert.equal(f.GCUR.SAU, 'USD'); assert.equal(f.GCUR.CHL, 'CLP');
  assert.ok(html.includes(" {id:'ind', lat:22,  lon:79,   mcap:5131, iso:['IND'], w:[1],") && html.includes('fix:{ind:1}'));
  // v96: wiersza „Źródło” w szczegółach regionu już nie ma (źródła tylko na stronie Źródła); klucze g.src.* zostają w słownikach
  assert.ok(!html.includes("'g.src.regm'") && !html.includes("'Finnhub · '+t('g.src.reg1d')"), 'bez wiersza źródła w szczegółach regionu');
  const x0 = html.indexOf('const EXTRA51='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA51='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['g.win.nomonth', 'g.win.nofx', 'g.src.regu', 'g.d.basey.fix']) assert.ok(dict[l][k], l + ' ' + k);
});

// v63: poprawki po niezależnym przeglądzie
test('v63: „bez zmian” tylko z historią, dokładność różnicy wobec Fed, wiek przy liczbach, angielski zapas, legenda i teksty', () => {
  const a0 = html.indexOf('const spPct='), a1 = html.indexOf('\nfunction spRegion(', a0);
  const f = new Function('nfmt', 'instSign', html.slice(a0, a1) + '\nreturn {spPct, spPP};')((v, d) => v.toFixed(d), v => v > 0 ? '+' : (v < 0 ? '−' : ''));
  assert.equal(f.spPP(-0.125), '−0.125'); assert.equal(f.spPP(0.475), '+0.475'); assert.equal(f.spPP(-1), '−1.00');
  assert.ok(html.includes("(typeof r.m_n==='number'?(r.m_n>=13?t('sp.none.n',{n:r.m_n}):'—'):t('sp.none'))"));
  assert.ok(html.includes("t('cof.foot',{q:instFoot(C.asof),") && html.includes("q:r?instFoot(r[0]):'—'") && html.includes("ob.reg.v',{d:instFoot(l[0]),"), 'wiek przy liczbach');
  const g0 = html.indexOf('const engGen='), g1 = html.indexOf('function engKpis(rec){', g0);
  const x0 = html.indexOf('const EXTRA52='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA52='.length, x1));
  const t = (k, o) => { let s = dict.en[k] !== undefined ? dict.en[k] : k; if (o) for (const v in o) s = s.split('{' + v + '}').join(o[v]); return s; };
  const e = new Function('LANG', 't', html.slice(g0, g1) + '\nreturn {engTx, engAttr, engRights, engLim, engAge};')('en', t);
  const rec = {view: 'cftc-euro-fx', kind_pl: 'Pozycje', says_pl: 'Jak grupy…', not_says_pl: 'To pozycje…', rights: {sentence_pl: 'Dane rządu USA…'}, limitations_pl: ['PL'], data_age: {phrase_pl: 'Stan z wtorku'}, attribution: 'Źródło: CFTC', source_home: 'https://www.cftc.gov'};
  assert.equal(e.engTx(rec, 'kind'), ''); assert.equal(e.engTx(rec, 'says'), '');
  assert.ok(e.engTx(rec, 'not_says').startsWith('See the Sources page') && e.engRights(rec).startsWith('Terms and attribution') && e.engLim(rec)[0].startsWith('See the Sources'));
  assert.equal(e.engAttr(rec), 'Source: https://www.cftc.gov'); assert.ok(!/[ąćęłńóśźż]/i.test(e.engAge(rec)), 'bez polskiego');
  assert.ok(!html.includes('przygotowujemy do zasilania strony danymi CFTC'));
  assert.ok(!html.includes("'Twelve Data (klucz własny) · ETF'") && html.includes("t('g.src.tdown')+' · ETF'"));
  for (const l of ['pl', 'en']) for (const k of ['sp.none.n', 'g.hs.sp', 'eer.reg.v', 'bi.e.norep', 'stc.t0', 'g.src.tdown']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(!dict.pl['bi.e.norep'].includes('nie raportują'));
});

// v64: kwartał i rok z cen ETF-ów, gdy plik ma dość historii (≥ 80% symboli); inaczej OECD
test('v64: gCenyDeep — 1KW/1R z cen ETF tylko przy pełnej historii; zmiana 63/252 sesji', () => {
  const a0 = html.indexOf('const GCENY_N='), a1 = html.indexOf('function gCenyReg(r,per){', a0);
  const GPROXY = {usa: [['SPY', 1]], mea: [['KSA', .76], ['TUR', .13], ['EIS', .11]], jpn: [['EWJ', .76], ['EWY', .24]]};
  const GLIVE = {ceny: null};
  const f = new Function('GLIVE', 'GPROXY', 'gOk', 'gPeriodButtons', html.slice(a0, a1) + '\nreturn {GCENY_N, gCenyDeep, gCenyDp};')(GLIVE, GPROXY, () => {}, () => {});
  const series = n => Array.from({length: n}, (_, i) => ['d' + String(260 - n + i).padStart(3, '0'), 100 + 260 - n + i]);   // v69: krótsza historia = najnowsze sesje, wspólny kalendarz
  GLIVE.ceny = {q: {SPY: {d: series(260)}, KSA: {d: series(260)}, TUR: {d: series(260)}, EIS: {d: series(260)}, EWJ: {d: series(45)}, EWY: {d: series(260)}}};
  assert.equal(f.gCenyDeep('1Q'), true, '5 z 6 symboli (83%) ma ≥ 64 sesje');
  GLIVE.ceny.q.EWY.d = series(45);
  assert.equal(f.gCenyDeep('1Q'), false, '4 z 6 (67%) — kwartał z OECD');
  assert.equal(f.gCenyDeep('1M'), true);
  assert.ok(Math.abs(f.gCenyDp('SPY', '1R') - ((359 / 107) - 1) * 100) < 1e-9, '252 sesje wstecz');
  assert.equal(f.gCenyDp('EWJ', '1Q'), null, 'za krótka historia symbolu — brak, nie zero');
  assert.ok(html.includes("((per==='1Q'||per==='1R')&&gCenyDeep(per))") && html.includes("['1T','1M','1Q','1R'].filter(p=>p==='1T'||p==='1M'||gCenyDeep(p))"));
});

// v65: zmierzone przepływy urzędowe przy regionach (TIC, EBC, MOF); brak = bez wiersza
test('v65: msRegion — USA z TIC, Europa z bilansu płatniczego, Japonia z MOF; miesiące tylko zgodne', () => {
  const a0 = html.indexOf('function msRegion(id){'), a1 = html.indexOf('function gProbBox(id){', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const mk = (TIC, INST) => new Function('t', 'TIC', 'INST', 'instSign', 'instMld', 'instFoot', 'escH', html.slice(a0, a1) + '\nreturn msRegion;')(
    T, TIC, INST, v => v > 0 ? '+' : (v < 0 ? '−' : ''), v => (v / 1000).toFixed(1), s => s, s => String(s));
  const f = mk({data: {world: {in: [['2026-06', 1, 1], ['2026-07', 40616, 1]], in_tr: [['2026-07', -3560, 1]], in_eq: [['2026-06', 3705, 1]], out: [['2026-06', 5, 1], ['2026-07', 68522, 1]]}}},
               {data: {bop: {s: {fa: [['2026-06', 1000], ['2026-07', -20000]], pi: [['2026-07', 5000]]}}, mof: {d: [{from: '2026-09-06', to: '2026-09-12', assets: {total_net: -3458}, liabilities: {equity_net: -25110, ltdebt_net: 5118}}]}}});
  const u = f('usa');
  assert.ok(u.includes('ms.usa{"m":"2026-07","in":"+40.6","tr":"−3.6","eq":"—","out":"+68.5"}'), 'akcje z innego miesiąca = „—”, nie mieszamy miesięcy: ' + u);
  assert.ok(f('eur').includes('ms.eur{"m":"2026-07","fa":"−20.0","pi":"+5.0"}'));
  assert.ok(f('jpn').includes('ms.jpn{"w":"2026-09-06 – 2026-09-12","e":"−2511.0","b":"+511.8","a":"−345.8"}'), '100 mln JPY → mld JPY');
  assert.equal(f('chn'), ''); assert.equal(mk({data: null}, {data: null})('usa'), '');
  assert.ok(html.includes('${msRegion(s.id)}'));
  const x0 = html.indexOf('const EXTRA54='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA54='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ms.t', 'ms.usa', 'ms.eur', 'ms.jpn', 'ms.note']) assert.ok(dict[l][k], l + ' ' + k);
});

// v66: jedna kapitalizacja krypto z jednego źródła; nazwy źródeł po angielsku poza polskim
test('v66: kafelek kapitalizacji krypto z CoinMarketCap (jak panel CRYPTO), CoinGecko jako zapas; nazwy Źródeł po angielsku', () => {
  const k0 = html.indexOf("((M=>(M&&typeof M.total_mcap==='number'"), k1 = html.indexOf("(typeof CMC!=='undefined'?CMC.data:null))", k0) + "(typeof CMC!=='undefined'?CMC.data:null))".length;
  const expr = html.slice(k0, k1);
  const run = (CMC, cy) => new Function('CMC', 'cy', 'return ' + expr + ';')(CMC, cy);
  const a = run({data: {total_mcap: 2887476408334.7, mcap_chg24_pct: 0.83135, asof: '2026-09-25T00:10:59.999Z'}}, {total_market_cap: {usd: 2.9e12}, market_cap_change_percentage_24h_usd: -2.02, updated_at: 1790295334});
  assert.equal(a.src, 'CoinMarketCap'); assert.ok(Math.abs(a.v - 2887.4764) < 1e-3); assert.equal(a.d, 0.83135); assert.equal(a.fresh, '2026-09-25');
  const b = run({data: null}, {total_market_cap: {usd: 2.9e12}, market_cap_change_percentage_24h_usd: -2.02, updated_at: 1790295334});
  assert.equal(b.src, 'CoinGecko', 'bez pliku CMC — zapas CoinGecko'); assert.equal(b.d, -2.02);
  const c = run({data: {total_mcap: 1, mcap_chg24_pct: 'x', asof: ''}}, null); assert.equal(c.d, null, 'zła zmiana = brak, nie 0');
});

// v67: HKEX Stock Connect (southbound) — trzeci kafelek, kolumna w tabeli, wiersz regionu Chiny, Źródła
test('v67: Stock Connect — kafelek, kolumna, wiersz regionu Chiny; brak części HK = bez kolumny', () => {
  const a0 = html.indexOf('const ZAG={data:null};'), a1 = html.indexOf('function renderInst(){', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'instRow', 'instFoot', 'engNum', 'engDate', 'escH', html.slice(a0, a1) + '\nreturn {ZAG, zagApply, zagBlock, zagRegion};')(
    T, () => {}, () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), (a, b, c, d) => `[${a}|${b}|${c}|${d}]`, s => s, v => String(v), s => s, s => String(s));
  f.zagApply({at: 'x', in: {d: [['2026-09-24', 754.19, 46.98, -0.19, 806.15, 95.7]]}});
  let b = f.zagBlock(); assert.ok(!b.includes('ob.c.hk') && !b.includes('ob.hk.k'), 'bez części HK — bez kafelka i kolumny');
  f.zagApply({at: 'x', hk: {d: [['2026-09-23', 1000, 1, 1, 2, 127.5, '2026-09-18'], ['2026-09-24', 2899.77, 32950.11, 30050.34, 2, 369.6, '2026-09-18']]}});
  b = f.zagBlock();
  assert.ok(b.includes('[ob.hk.k|+2.9 ob.mld.hkd|') && b.includes('ob.hk.usd{"v":"+370","d":"2026-09-18"}') && b.includes('ob.snh{"n":2,"w":"sessions","v":"+3.9"}'), b.slice(0, 600));
  assert.ok(b.includes('<th>ob.c.hk</th>') && b.includes('ob.not.hk') && b.includes('[ob.in.k|—||eng.gap]'));
  const r = f.zagRegion('chn'); assert.ok(r.includes('ob.reg.hk.v') && r.includes('"v":"+2.9"') && r.includes('≈ +370 inst.mln.usd'), r);
  assert.equal(f.zagRegion('jpn'), '');
  assert.ok(html.includes("obce_hk:'HKEX'"));
  const x0 = html.indexOf('const EXTRA55='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA55='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ob.t', 'ob.hk.k', 'ob.not.hk', 'ob.reg.hk.v', 'g.hs.hkex']) assert.ok(dict[l][k], l + ' ' + k);
});

// v68: CFTC — dodatkowe rynki (waluty, indeks dolara, 10-latki, S&P 500, MSCI EM); brak rynku = bez wiersza
test('v68: cftcOthers — wiersze tylko dla obecnych rynków, zmiana 13 tyg. z historii funduszy lewarowanych', () => {
  const a0 = html.indexOf('const CFTC_X='), a1 = html.indexOf('function cftcTail(){', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const M = {jpy: {asof: '2026-09-15', groups: {asset_mgr: {net: 1000}, lev_funds: {net: -5000, chg_net: 300}}, hist: {dates: ['2026-06-23', '2026-09-15'], lev_funds: [-2000, -5000]}},
             ust10: {asof: '2026-09-15', kept: true, groups: {asset_mgr: {net: 7}, lev_funds: {net: null}}, hist: null}};
  const f = new Function('t', 'cftcMkt', 'cftcS', 'cftcIsN', 'instFoot', 'escH', html.slice(a0, a1) + '\nreturn cftcOthers;')(
    T, k => M[k] || null, v => v == null ? '—' : String(v), v => typeof v === 'number' && isFinite(v), s => s, s => String(s));
  const h = f();
  assert.ok(h.includes('cftc.m.jpy') && h.includes('cftc.m.ust10') && !h.includes('cftc.m.gbp'), 'tylko obecne rynki');
  assert.ok(h.includes('<span class="cell mono">-3000</span>') && h.includes('cftc.x.c.lf13{"d":"2026-06-23"}'), 'zmiana 13 tyg. = ostatni − pierwszy');
  assert.ok(h.includes('<span class="cell mono">—</span>') && h.includes('cftc.kept'), 'brak = —, stan zachowany oznaczony');
  assert.ok(html.includes('cftcHist(m)+cftcOthers()+cftcTail()'));
  const x0 = html.indexOf('const EXTRA56='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA56='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['cftc.x.t', 'cftc.x.sub', 'cftc.m.jpy', 'cftc.m.msciem']) assert.ok(dict[l][k], l + ' ' + k);
});

// v69: wspólny kalendarz sesji ETF-ów, nagłówek CRYPTO z CoinMarketCap, teksty regionu dla okresów z ETF-ów
test('v69: fałszywa sesja nie przesuwa okna; ETF bez daty końca = brak; daty okna przy zmianach ETF', () => {
  const a0 = html.indexOf('const GCENY_N='), a1 = html.indexOf('function gCenyReg(r,per){', a0);
  const GPROXY = {usa: [['SPY', 1]], oce: [['EWA', 1]]}, GLIVE = {ceny: null};
  const f = new Function('GLIVE', 'GPROXY', 'gOk', 'gPeriodButtons', html.slice(a0, a1) + '\nreturn {gCenyWin, gCenyDp, gCenyDeep};')(GLIVE, GPROXY, () => {}, () => {});
  const days = Array.from({length: 70}, (_, i) => 'd' + String(i).padStart(3, '0'));
  GLIVE.ceny = {q: {SPY: {d: days.map((d, i) => [d, 100 + i])}, EWA: {d: [...days.slice(0, 10).map((d, i) => [d, 50 + i]), ['d009x', 59], ...days.slice(10).map((d, i) => [d, 60 + i])]}}};
  assert.deepEqual(f.gCenyWin('1Q'), ['d006', 'd069']);
  assert.ok(Math.abs(f.gCenyDp('EWA', '1Q') - ((119 / 56) - 1) * 100) < 1e-9, 'wiersz spoza kalendarza nie przesuwa okna');
  GLIVE.ceny.q.EWA.d.pop(); assert.equal(f.gCenyDp('EWA', '1Q'), null, 'ETF bez ostatniej sesji — brak, nie inne okno');
  assert.ok(html.includes("(w=>w?' · '+escH(w[0])+' → '+escH(w[1]):'')(gCenyWin(p))"));
  assert.ok(html.includes("jpn:[['EWJ',7611],['EWY',2757]]"), 'wagi Japonii i Korei z bazy');
  const rk0 = html.indexOf('function renderKPI(){'), rk1 = html.indexOf('\nfunction kpiIco(', rk0);   // v96: kafelki bez nazw dostawców (pole src zostaje w danych)
  assert.ok(html.includes('function kpiCmc(M,out,live)') && rk0 > 0 && rk1 > rk0 && !html.slice(rk0, rk1).includes('KSRC') && !/[^k]src/.test(html.slice(rk0, rk1)));   // v73: kafelki CMC w kpiCmc
  assert.ok(html.includes("t(GLIVE.cenySrv?'g.m.regtds':'g.m.regtd',{n:GCENY_N[gst.period]})") && html.includes("'gmap.l.regtd':'gmap.l.reg'"));   // v96: te same ograniczenia, opis bez nazw instytucji
  const z0 = html.indexOf('const zagSes='), z1 = html.indexOf('\n', z0), zs = new Function('LANG', html.slice(z0, z1) + '\nreturn zagSes;')('pl');
  assert.deepEqual([1, 2, 4, 5, 12, 20, 22].map(zs), ['sesja', 'sesje', 'sesje', 'sesji', 'sesji', 'sesji', 'sesje']);
  const x0 = html.indexOf('const EXTRA57='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA57='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['g.m.regtds', 'g.src.regtds', 'g.l.regtd', 'g.pf.mom3', 'ob.src', 'ob.reg.hk.v']) assert.ok(dict[l][k], l + ' ' + k);
  assert.equal(dict.pl['g.per.1R'], 'rok (12 miesięcy)');
});

// v70: MFW bilans płatniczy — zmierzony napływ kapitału; ranking z 4 kwartałów; brak = „—”; wiersz regionu
test('v70: bilans płatniczy: sumy tylko z kompletu, ranking, starszy kwartał w rozwinięciu, wiersz regionu, podpięcie źródła', () => {
  const a0 = html.indexOf('const BIL={data:null};'), a1 = html.indexOf('function renderInst(){', a0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'escH', 'engDate', 'instFoot', 'etfCls', 'bopMld', 'LANG', html.slice(a0, a1) + '\nreturn {BIL, bilApply, bilHtml, bilRegion, bilSum, bilQadd};')(
    T, k => oks.push(k), () => {}, s => String(s), s => String(s), s => 'F' + s, v => v > 0 ? 'pos' : (v < 0 ? 'neg' : ''), v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—', 'pl');
  assert.equal(f.bilHtml(null), '');
  assert.equal(f.bilQadd('2026-Q1', -1), '2025-Q4'); assert.equal(f.bilQadd('2026-Q2', -4), '2025-Q2');
  const S = (q0, vals) => vals.map((v, i) => [f.bilQadd(q0, i - vals.length + 1), v]);
  f.bilApply({at: 'x', asof_max: '2026-Q2', order: ['USA', 'KOR', 'IRL', 'HKG'], rows: {
    USA: {q: '2026-Q1', s: {in_d: S('2026-Q1', [1, 1, 1, 1]), in_p: S('2026-Q1', [400000, 400000, 400000, 334100]), in_o: S('2026-Q1', [0, 0, 0, 0])}},
    KOR: {q: '2026-Q2', s: {in_d: S('2026-Q2', [1000, 1000, 1000, 5000]), in_p: S('2026-Q2', [16300, 16300, -41300, -47463.3]), in_pe: S('2026-Q2', [-63905.4]), in_o: S('2026-Q2', [0, 0, 0, 17981.4]),
                             out_d: S('2026-Q2', [1, 1, 1, 18807.5]), out_p: S('2026-Q2', [1, 1, 1, 18019]), out_o: S('2026-Q2', [1, 1, 1, 37327])}},
    IRL: {q: '2025-Q4', s: {in_d: S('2025-Q4', [1, 1, 1, 1]), in_p: S('2025-Q4', [100900, 100900, 100900, 100900]), in_o: S('2025-Q4', [0, 0, 0, 0])}},
    HKG: {q: '2026-Q2', s: {in_p: S('2026-Q2', [8100])}}}});
  assert.deepEqual(oks, ['bilans']);
  const h = f.bilHtml(f.BIL.data), main = h.split('<details')[0], more = h.split('bil.more')[1] || '';
  assert.ok(main.indexOf('<span class="cell">USA</span>') < main.indexOf('<span class="cell">KOR</span>'), 'ranking wg 4 kwartałów');
  assert.ok(main.includes('<span class="cell mono pos">+1534.1</span>') && main.includes('<span class="cell mono pos">+334.1</span>'), 'USA: kwartał 334,1; 4 kw. 1534,1 mld ' + main.slice(0, 900));
  assert.ok(main.includes('<span class="cell mono neg">-24.5</span>') && main.includes('<span class="cell mono neg">-30.2</span>'), 'KOR: kwartał 5 − 47,5 + 18,0 = −24,5; 4 kw. −30,2');
  assert.ok(main.includes('<span class="cell">HKG</span>') && main.includes('<span class="cell mono">—</span>'), 'HKG bez bezpośrednich = —, nie zero');
  assert.ok(!main.includes('IRL') && more.includes('IRL') && h.includes('bil.more{"n":1}'), 'starszy kwartał tylko w rozwinięciu');
  const r = f.bilRegion('jpn');
  assert.ok(r.includes('<dt>bil.reg</dt>') && r.includes('"c":"KOR","q":"F2026-Q2"') && r.includes('"pe":"-63.9"') && r.includes('"pd":"—"') && r.includes('"out":"+74.2"'), r);
  assert.equal(f.bilRegion('rus'), '', 'brak kraju w pliku = bez wiersza');
  f.bilApply({at: 'x', rows: {}, order: []}); assert.equal(f.BIL.data, null, 'plik bez krajów odrzucony');
  assert.ok(html.includes("html+=(typeof bilHtml==='function'&&typeof BIL!=='undefined')?bilHtml(BIL.data):'';") && html.includes("srvJSON('bilans')") && html.includes("bilans:'MFW bilans płatniczy'"));
  assert.ok(html.includes("${typeof bilRegion==='function'?bilRegion(s.id):''}") && html.includes('bilans:()=>BIL.data&&BIL.data.at') && html.includes("bilans:'bilans',"));
  const x0 = html.indexOf('const EXTRA58='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA58='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['bil.t', 'bil.sub', 'bil.c.t4', 'bil.more', 'bil.foot', 'bil.not', 'bil.src', 'bil.reg', 'bil.reg.v', 'g.hs.bilans']) assert.ok(dict[l][k], l + ' ' + k);
});

// v71: Brazylia — dolary przez rynek walutowy (BCB); brak = „—”; wiersz regionu Ameryka Łacińska; podpięcie źródła
test('v71: blok BCB: kapitał, handel, razem, sumy tylko z kompletu, wiersz regionu, podpięcie', () => {
  const a0 = html.indexOf('function brBlock(){'), a1 = html.indexOf('/* v59: MFW COFER', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const ZAG = {data: null};
  const zagNum = v => (typeof v === 'number' && isFinite(v)) ? v : null;
  const zagSum = (d, i, n) => { if (d.length < n) return null; let s = 0; for (const r of d.slice(-n)) { const v = zagNum(r[i]); if (v == null) return null; s += v; } return s; };
  const zagPart = k => { const p = ZAG.data && ZAG.data[k]; return (p && Array.isArray(p.d) && p.d.length) ? p : null; };
  const f = new Function('t', 'ZAG', 'zagPart', 'zagNum', 'zagSum', 'zagM', 'zagSes', 'instRow', 'instFoot', 'engDate', 'nfmt', html.slice(a0, a1) + '\nreturn {brBlock, brRegion};')(
    T, ZAG, zagPart, zagNum, zagSum, v => v == null ? '—' : String(Math.round(v * 100) / 100), n => n === 1 ? 'session' : 'sessions',
    (l, v, x, n) => `[${l}|${v}|${n}]`, s => s, s => s, (v, d) => v.toFixed(d));
  assert.equal(f.brBlock(), ''); assert.equal(f.brRegion('lat'), '');
  const days = Array.from({length: 22}, (_, i) => ['2026-08-' + String(10 + i).padStart(2, '0'), 10, 20, 10, 1, 11]);
  days[21] = ['2026-09-18', -330.4, 2955.74, 3286.14, null, -392.5];
  ZAG.data = {at: 'x', br: {at: 'y', d: days}};
  const h = f.brBlock();
  assert.ok(h.includes('[br.fin|-330.4 inst.mln.usd|br.fin.bs{"b":"2956","s":"3286"} · ob.day 2026-09-18 · br.s5{"v":"-290.4"} · br.sn{"n":20,"w":"sessions","v":"-140.4"}]'), h);
  assert.ok(h.includes('[br.com|— inst.mln.usd|ob.day 2026-09-18 · br.s5{"v":"—"}'), 'brak handlu w oknie = brak sumy, nie zero');
  assert.ok(h.includes('<p class="pnote">inst.file{"t":"y"}</p>') && !h.includes('br.src'), 'v96: źródło tylko na stronie Źródła');
  const r = f.brRegion('lat');
  assert.ok(r.includes('<dt>br.reg</dt>') && r.includes('"f":"-330.4","c":"—"') && r.includes('"f20":"-140.4","t20":"-183.5"'), r);
  assert.equal(f.brRegion('usa'), '');
  assert.ok(html.includes("html+=typeof brBlock==='function'?brBlock():'';") && html.includes("${typeof brRegion==='function'?brRegion(s.id):''}"));
  assert.ok(html.includes("if(okD(j.br))gOk('obce_br');") && html.includes("obce_br:'BCB'") && html.includes('obce_br:()=>ZAG.data&&ZAG.data.br&&ZAG.data.br.at'));
  const x0 = html.indexOf('const EXTRA59='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA59='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['br.t', 'br.sub', 'br.fin', 'br.com', 'br.tot', 'br.not', 'br.src', 'br.reg', 'br.reg.v', 'g.hs.bcb']) assert.ok(dict[l][k], l + ' ' + k);
});

// v72: SAFE (Chiny) — kupno i sprzedaż walut przez banki; 12 miesięcy tylko z kolejnych miesięcy; brak = „—”
test('v72: SAFE: kapitał, handel, razem, suma 12 kolejnych miesięcy, wiersz regionu Chiny, podpięcie', () => {
  const a0 = html.indexOf('const SAFE={data:null};'), a1 = html.indexOf('function renderInst(){', a0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instRow', 'instFoot', 'instSign', 'nfmt', 'engDate', html.slice(a0, a1) + '\nreturn {SAFE, safeApply, safeHtml, safeRegion, safeSum, safeMadd};')(
    T, k => oks.push(k), () => {}, (l, v, x, n) => `[${l}|${v}|${n}]`, s => 'F' + s, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), s => s);
  assert.equal(f.safeHtml(null), ''); assert.equal(f.safeRegion('chn'), '');
  assert.equal(f.safeMadd('2026-01', -1), '2025-12'); assert.equal(f.safeMadd('2026-08', -11), '2025-09');
  const M = Array.from({length: 13}, (_, i) => [f.safeMadd('2026-08', i - 12), 10, 12, -2, -0.5, -1, 40, 42]);
  M[12] = ['2026-08', 51.92, 61.56, -9.63, -1.17, null, 36.24, 45.87];
  f.safeApply({at: 'x', m: M}); assert.deepEqual(oks, ['safe']);
  const h = f.safeHtml(f.SAFE.data);
  assert.ok(h.includes('[sf.cfa|−9.6 inst.mld.usd|sf.m{"m":"F2026-08"} · sf.split{"p":"—","d":"−1.2"} · sf.12{"v":"−31.6"}]'), h);
  assert.ok(h.includes('[sf.cust|+51.9 inst.mld.usd|sf.m{"m":"F2026-08"} · sf.12{"v":"+161.9"}]'), 'razem: 11×10 + 51,92');
  const r = f.safeRegion('chn');
  assert.ok(r.includes('<dt>sf.reg</dt>') && r.includes('"c":"−9.6","p":"—","d":"−1.2","a":"+61.6","c12":"−31.6"'), r);
  assert.equal(f.safeRegion('ind'), '');
  const G = M.filter((_, i) => i !== 5); f.safeApply({at: 'x', m: G});
  assert.ok(f.safeHtml(f.SAFE.data).includes('sf.12{"v":"—"}'), 'brak miesiąca w oknie = brak sumy 12 miesięcy');
  f.safeApply({at: 'x', m: []}); assert.equal(f.SAFE.data, null);
  assert.ok(html.includes("html+=(typeof safeHtml==='function'&&typeof SAFE!=='undefined')?safeHtml(SAFE.data):'';") && html.includes("${typeof safeRegion==='function'?safeRegion(s.id):''}"));
  assert.ok(html.includes("srvJSON('safe')") && html.includes("safe:'SAFE'") && html.includes('safe:()=>SAFE.data&&SAFE.data.at') && html.includes("safe:'safe',"));
  const x0 = html.indexOf('const EXTRA60='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA60='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['sf.t', 'sf.sub', 'sf.cfa', 'sf.ca', 'sf.cust', 'sf.not', 'sf.src', 'sf.reg', 'sf.reg.v', 'g.hs.safe']) assert.ok(dict[l][k], l + ' ' + k);
});

// v73: poprawki po trzecim przeglądzie
test('v73: kafelki CoinMarketCap z własnym czasem, także bez CoinPaprika; bez „−0,0”; CFTC data przy wierszu; teksty panelu', () => {
  const a0 = html.indexOf('function kpiCmc(M,out,live){'), a1 = html.indexOf('function renderKPI(){', a0);
  const f = new Function('big', html.slice(a0, a1) + '\nreturn kpiCmc;')(v => [v / 1e12, 'u.T', 2]);
  assert.equal(f(null, {}, false), null, 'bez pliku i bez CoinPaprika — brak');
  const o = {vol: 1}; assert.equal(f(null, o, true), o, 'bez pliku — to, co z CoinPaprika');
  const r = f({total_mcap: 2.88e12, mcap_chg24_pct: 0.004, btc_dom: 58.9, asof: '2026-09-25T01:47:59.999Z', at: 'x'}, {}, false);
  assert.deepEqual(r.mcap, {val: 2.88, unit: 'u.T', dec: 2, d: 0, src: 'CoinMarketCap', at: '2026-09-25T01:47:59.999Z'});
  assert.equal(r.dom.at, '2026-09-25T01:47:59.999Z'); assert.equal(r.dom.d, null);
  assert.ok(html.includes("const ks=own?engDate(own)+gAgeNote(own):gap?'':!lv?t('live.off'):liveWhen()+gAgeNote(LIVE.at||'');") && html.includes('else if(lv||L){gap=true;d=null;}'));   // v96: data i wiek bez dostawcy
  const b0 = html.indexOf('const bopMld='), b1 = html.indexOf('\n', b0);
  const bop = new Function('instSign', 'instMld', html.slice(b0, b1) + '\nreturn bopMld;')(v => v > 0 ? '+' : (v < 0 ? '−' : ''), m => (m / 1000).toFixed(1));
  assert.equal(bop(-29.7), '−&lt;0.1'); assert.equal(bop(0), '0.0'); assert.equal(bop(-1234), '−1.2'); assert.equal(bop(null), '—');
  assert.ok(html.includes("t('cftc.x.from',{d:escH(c[1])})") && html.includes('cnt[b]-cnt[a]'));
  assert.ok(!html.includes("${K?' · HKEX (Stock Connect)':''}"), 'HKEX nie dwa razy w linii źródeł');
  assert.ok(html.includes('<td><span class="cell mono">${instFoot(r.q)}</span></td>'), 'kwartał z wiekiem danych');
  assert.ok(html.includes('Zmierzone przepływy kapitału między krajami — transakcje, a nie zmiany cen'));
  for (const k of ['bilans płatniczy 37 gospodarek', 'kupno i sprzedaż walut przez banki w Chinach', 'dolary przez rynek walutowy Brazylii', 'pozycje dużych graczy w kontraktach']) assert.ok(html.includes('<span class="cell">' + k + '</span>'), k);
  const x0 = html.indexOf('const EXTRA61='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA61='.length, x1));
  for (const l of ['pl', 'en']) {
    for (const k of ['br.sub', 'br.fin', 'br.fin.bs', 'br.reg.v', 'src.l.bop', 'src.l.bcb', 'bil.c.o', 'bil.foot', 'bil.not', 'bil.reg.v', 'cftc.x.from', 'cftc.x.sub', 'inst.t', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
    assert.ok(!/Sześć|Six sets/.test(dict[l]['inst.sub']));
  }
  assert.ok(dict.pl['br.sub'].includes('bez rynku międzybankowego') && dict.pl['bil.not'].includes('Wielka Brytania') && dict.pl['bil.foot'].includes('12 gospodarek'));
});

// v74: Turcja — tygodniowe transakcje nierezydentów (CBRT); sumy tylko z kolejnych tygodni; wiersz regionu Bliski Wschód
test('v74: blok CBRT: razem, akcje, obligacje; 4 i 13 tygodni tylko z kolejnych tygodni; wiersz regionu; podpięcie', () => {
  const a0 = html.indexOf('const trDadd='), a1 = html.indexOf('/* v59: MFW COFER', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : ''), ZAG = {data: null};
  const zagNum = v => (typeof v === 'number' && isFinite(v)) ? v : null;
  const zagPart = k => { const p = ZAG.data && ZAG.data[k]; return (p && Array.isArray(p.d) && p.d.length) ? p : null; };
  const f = new Function('t', 'ZAG', 'zagPart', 'zagNum', 'zagM', 'instRow', 'instFoot', 'engDate', html.slice(a0, a1) + '\nreturn {trBlock, trRegion, trSum, trDadd};')(
    T, ZAG, zagPart, zagNum, v => v == null ? '—' : String(Math.round(v * 100) / 100), (l, v, x, n) => `[${l}|${v}|${n}]`, s => s, s => s);
  assert.equal(f.trBlock(), ''); assert.equal(f.trRegion('mea'), '');
  assert.equal(f.trDadd('2026-09-18', -7), '2026-09-11'); assert.equal(f.trDadd('2026-01-02', -7), '2025-12-26');
  const W = Array.from({length: 5}, (_, i) => [f.trDadd('2026-09-18', -7 * (4 - i)), 10, 5, 2, 1, 2, 1]);
  W[4] = ['2026-09-18', -316.01, -109.83, -116.9, -331.69, 242.41, -168.69];
  ZAG.data = {at: 'x', tr: {at: 'y', d: W}};
  const h = f.trBlock();
  assert.ok(h.includes('[tr.tot|-316.01 inst.mln.usd|tr.wk{"d":"2026-09-18"} · tr.s4{"v":"-286.01"} · tr.split{"c":"-331.69","x":"242.41"}]'), h);
  assert.ok(!h.includes('tr.s13'), '13 tygodni pokazujemy dopiero z pełną historią');
  const G = W.filter((_, i) => i !== 2); ZAG.data = {at: 'x', tr: {at: 'y', d: G}};
  assert.ok(f.trBlock().includes('tr.s4{"v":"—"}'), 'luka w tygodniach = brak sumy, nie zero');
  ZAG.data = {at: 'x', tr: {at: 'y', d: W}};
  const r = f.trRegion('mea');
  assert.ok(r.includes('<dt>tr.reg</dt>') && r.includes('"t":"-316.01","e":"-109.83","g":"-116.9","t4":"-286.01"'), r);
  assert.equal(f.trRegion('eur'), '');
  assert.ok(html.includes("html+=typeof trBlock==='function'?trBlock():'';") && html.includes("${typeof trRegion==='function'?trRegion(s.id):''}"));
  assert.ok(html.includes("if(okD(j.tr))gOk('obce_tr');") && html.includes("obce_tr:'CBRT'") && html.includes('obce_tr:()=>ZAG.data&&ZAG.data.tr&&ZAG.data.tr.at'));
  assert.ok(html.includes('<span class="cell">nierezydenci w tureckich akcjach i obligacjach</span>'));
  const x0 = html.indexOf('const EXTRA62='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA62='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['tr.t', 'tr.sub', 'tr.tot', 'tr.eq', 'tr.gd', 'tr.not', 'tr.src', 'tr.reg', 'tr.reg.v', 'g.hs.tcmb', 'src.l.tcmb', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
});

// v75: przegląd zmierzonych przepływów — jeden wiersz na źródło; znak EBC odwrócony; jednostki; brak = „—”
test('v75: przegląd: USA, strefa euro (znak odwrócony), Japonia (100 mln JPY), Chiny (mld → mln), sesje, Turcja; brak = —', () => {
  const a0 = html.indexOf('function flowRows(){'), a1 = html.indexOf('function renderInst(){', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const parts = {
    hk: {d: Array.from({length: 3}, (_, i) => ['2026-09-2' + (2 + i), 1, 1, 1, 2, 100 + i, 'x'])},
    tw: {d: [['2026-09-23', 1, 0, 0, 0, null, ''], ['2026-09-24', 1, 0, 0, 0, 50, '']]},
    tr: {d: [['2026-09-18', -316.01]]}};
  const zagPart = k => parts[k] || null;
  const zagSum = (d, i, n) => { let s = 0; for (const r of d.slice(-n)) { if (typeof r[i] !== 'number') return null; s += r[i]; } return s; };
  const env = {TIC: {data: {world: {in: [['2026-06', 1], ['2026-07', 75450]]}}},
    INST: {data: {bop: {s: {pi: [['2026-07', -21794]]}}, mof: {d: [{from: '2026-09-06', to: '2026-09-12', liabilities: {total_net: -4995}}]}}},
    SAFE: {data: {m: [['2026-08', 51.92, 61.56, -9.63]]}}};
  const f = new Function('t', 'TIC', 'INST', 'SAFE', 'zagPart', 'zagSum', 'zagSes', 'trSum', 'bilCty', 'bopMld', 'etfCls', 'escH', 'gAgeNote', html.slice(a0, a1) + '\nreturn {flowRows, flowOverview};')(
    T, env.TIC, env.INST, env.SAFE, zagPart, zagSum, n => n === 1 ? 'session' : 'sessions', (d, i, n) => -359.51, c => c, v => (v > 0 ? '+' : '') + (v / 1000).toFixed(1), v => v > 0 ? 'pos' : (v < 0 ? 'neg' : ''), s => String(s), d => ' · A' + d);
  const R = f.flowRows(), by = Object.fromEntries(R.map(r => [r.c, r]));
  assert.deepEqual(R.map(r => r.c), ['USA', 'EA', 'JPN', 'CHN', 'HKG', 'TWN', 'TUR'], 'kolejność; bez źródła — bez wiersza');
  assert.equal(by.USA.v, 75450); assert.equal(by.EA.v, 21794, 'EBC: aktywa − pasywa → znak odwrócony');
  assert.equal(by.JPN.v, -499500, '100 mln JPY → mln JPY'); assert.ok(Math.abs(by.CHN.v + 9630) < 1e-9, 'mld → mln USD');
  assert.equal(by.HKG.v, 303); assert.equal(by.TWN.v, null, 'brak przeliczenia jednego dnia = brak sumy'); assert.equal(by.TUR.v, -359.51);
  assert.equal(by.HKG.p, 'fo.s{"n":3,"x":"sessions","d":"2026-09-24"}');
  const h = f.flowOverview();
  assert.ok(h.includes('<span class="cell mono pos">+21.8 fo.u.eur</span>') && h.includes('<span class="cell mono neg">-499.5 fo.u.jpy</span>'), h);
  assert.ok(h.includes('<span class="cell mono ">—</span>'), 'brak = —, bez jednostki');
  assert.ok(h.includes('<span class="cell mono pos">≈ +0.3 fo.u.usd</span>'), 'przeliczenie: „≈” przed liczbą');
  assert.ok(h.includes('fo.w{"w":"2026-09-06 – 2026-09-12"} · A2026-09-12'), 'okres z wiekiem danych');
  assert.ok(html.includes("html+=typeof flowOverview==='function'?flowOverview():'';"));
  const x0 = html.indexOf('const EXTRA63='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA63='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['fo.t', 'fo.sub', 'fo.eur', 'fo.usa', 'fo.jpn', 'fo.chn', 'fo.hkg', 'fo.ind', 'fo.twn', 'fo.bra', 'fo.tur', 'fo.foot', 'fo.u.usdx']) assert.ok(dict[l][k], l + ' ' + k);
});

// v76: Eurostat — kraje UE; ranking z 12 miesięcy; Polska zawsze w głównej tabeli; wiersz Polski w przeglądzie
test('v76: UE: sumy tylko z kompletu 12 miesięcy, Polska zawsze widoczna, starszy miesiąc w rozwinięciu, podpięcie', () => {
  const a0 = html.indexOf('const UE={data:null};'), a1 = html.indexOf('function flowRows(){', a0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'escH', 'engDate', 'instFoot', 'etfCls', 'bopMld', 'LANG', 'LOCALE', 'ENG_DN', html.slice(a0, a1) + '\nreturn {UE, ueApply, ueHtml, ueSum, ueMadd};')(
    T, k => oks.push(k), () => {}, s => String(s), s => String(s), s => 'F' + s, v => v > 0 ? 'pos' : (v < 0 ? 'neg' : ''), v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—', 'xx', {}, {en: {of: x => x}});
  assert.equal(f.ueHtml(null), ''); assert.equal(f.ueMadd('2026-01', -1), '2025-12');
  const S = (m0, vals) => vals.map((v, i) => [f.ueMadd(m0, i - vals.length + 1), v]);
  const full = v => ({in_d: S('2026-07', Array(12).fill(0)), in_p: S('2026-07', Array(12).fill(v)), in_o: S('2026-07', Array(12).fill(0))});
  const rows = {};
  ['DE', 'FR', 'IT', 'ES', 'SE', 'AT', 'BE', 'DK', 'FI', 'PT', 'GR2', 'CZ'].forEach((g, i) => { rows[g] = {m: '2026-07', s: full(10000 - i * 500)}; });
  rows.PL = {m: '2026-07', s: full(100)}; rows.LU = {m: '2026-03', s: {in_p: S('2026-03', [5000])}};
  f.ueApply({at: 'x', order: [...Object.keys(rows)], rows}); assert.deepEqual(oks, ['ue']);
  const h = f.ueHtml(f.UE.data), main = h.split('<details')[0], more = h.split('ue.more')[1] || '';
  assert.ok(main.includes('<span class="cell">PL</span>'), 'Polska zawsze w głównej tabeli'); assert.ok(!main.includes('<span class="cell">CZ</span>') && more.includes('CZ'), 'poza 10 — w rozwinięciu');
  assert.ok(!main.includes('>LU<') && more.includes('LU'), 'starszy miesiąc — w rozwinięciu');
  assert.ok(main.includes('<span class="cell mono pos">+120.0</span>'), 'DE 12 miesięcy = 12 × 10 000 mln');
  assert.ok(more.includes('F2026-03') && more.includes('<span class="cell mono ">—</span>'), 'LU bez kompletu — „—”');
  assert.ok(html.includes("html+=(typeof ueHtml==='function'&&typeof UE!=='undefined')?ueHtml(UE.data):'';") && html.includes("srvJSON('ue')") && html.includes("ue:'Eurostat'"));
  assert.ok(html.includes("add('POL',t('fo.pol')"));
  const x0 = html.indexOf('const EXTRA64='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA64='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ue.t', 'ue.sub', 'ue.c.t12', 'ue.foot', 'ue.not', 'ue.src', 'g.hs.ue', 'fo.pol', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['inst.sub'].includes('kraje UE'));
});

// v77: poprawki po czwartym przeglądzie — uczciwe opisy „plus” i SAFE, przybliżenie kursu, wiersz USA po przyjściu TIC
test('v77: przegląd i SAFE opisane zgodnie z danymi; TIC przerysowuje panel; opóźnienie MFW spójne', () => {
  const x0 = html.indexOf('const EXTRA65='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA65='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['fo.sub', 'fo.foot', 'fo.ind', 'fo.jpn', 'fo.chn', 'sf.t', 'sf.sub', 'sf.not', 'tr.gd']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['fo.sub'].includes('transakcje mieszkańców') && !dict.pl['fo.sub'].includes('zagranica kupuje tam więcej'));
  assert.ok(dict.pl['sf.sub'].includes('nie to samo co pieniądze przychodzące z zagranicy') && !dict.pl['sf.sub'].includes('napłynęło więcej walut'));
  assert.ok(dict.pl['fo.foot'].includes('najbliższego wcześniejszego dnia'));
  assert.ok(html.includes("renderTic();if(typeof renderInst==='function')renderInst();}"));
  assert.ok(!html.includes('kraje publikują z opóźnieniem od jednego do dwóch kwartałów'));
});

// v78: Kanada — Statistics Canada; 12 miesięcy tylko z kolejnych miesięcy; wiersz regionu; wiersz w przeglądzie
test('v78: blok Kanady: razem, obligacje, akcje; suma 12 kolejnych miesięcy; wiersz regionu; podpięcie', () => {
  const a0 = html.indexOf('const KAN={data:null};'), a1 = html.indexOf('function flowRows(){', a0);
  const s0 = html.indexOf('const safeV='), s1 = html.indexOf('function safeHtml(', s0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instRow', 'instFoot', 'instSign', 'nfmt', 'engDate', 'bopMld', html.slice(s0, s1) + html.slice(a0, a1) + '\nreturn {KAN, kanApply, kanHtml, kanRegion, safeMadd};')(
    T, k => oks.push(k), () => {}, (l, v, x, n) => `[${l}|${v}|${n}]`, s => 'F' + s, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), s => s,
    v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—');
  assert.equal(f.kanHtml(null), ''); assert.equal(f.kanRegion('can'), '');
  const M = Array.from({length: 13}, (_, i) => [f.safeMadd('2026-07', i - 12), 1000, 500, 600, -100, 500]);
  M[12] = ['2026-07', 20653, 13453, 25321, -11869, 7200];
  f.kanApply({at: 'x', m: M}); assert.deepEqual(oks, ['kanada']);
  const h = f.kanHtml(f.KAN.data);
  assert.ok(h.includes('[kan.tot|+20.7 kan.u|sf.m{"m":"F2026-07"} · kan.split{"b":"+25.3","m":"-11.9","e":"+7.2"} · sf.12{"v":"+31.7"}]'), h);
  const r = f.kanRegion('can');
  assert.ok(r.includes('<dt>kan.reg</dt>') && r.includes('"t":"+20.7","b":"+25.3","e":"+7.2","t12":"+31.7"'), r);
  assert.equal(f.kanRegion('usa'), '');
  assert.ok(html.includes("html+=(typeof kanHtml==='function'&&typeof KAN!=='undefined')?kanHtml(KAN.data):'';") && html.includes("${typeof kanRegion==='function'?kanRegion(s.id):''}"));
  assert.ok(html.includes("add('CAN',t('fo.can')") && html.includes("srvJSON('kanada')") && html.includes("kanada:'Statistics Canada'"));
  const x0 = html.indexOf('const EXTRA66='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA66='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['kan.t', 'kan.sub', 'kan.tot', 'kan.not', 'kan.src', 'kan.reg.v', 'g.hs.kanada', 'fo.can', 'fo.u.cad', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['kan.src'].includes('with the permission of Statistics Canada') && dict.pl['inst.sub'].includes('Kanada'));
});

// v79: Brazylia — miesięczny bilans płatniczy w bloku, w regionie i w przeglądzie; suma tylko z kompletu
test('v79: BCB bilans płatniczy: razem z trzech składników, 12 kolejnych miesięcy, brak = —', () => {
  const s0 = html.indexOf('const safeV='), s1 = html.indexOf('function safeHtml(', s0);
  const a0 = html.indexOf('function brBopT('), a1 = html.indexOf('function brBlock(){', a0);
  const f = new Function('instSign', 'nfmt', html.slice(s0, s1) + html.slice(a0, a1) + '\nreturn {brBopRow, safeMadd};')(v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d));
  assert.equal(f.brBopRow(null), null); assert.equal(f.brBopRow({m: []}), null);
  const M = Array.from({length: 13}, (_, i) => [f.safeMadd('2026-07', i - 12), 1000, 500, 300, 100, 100, 200, 0, 0, 0]);
  M[12] = ['2026-07', 7460.5, 2158.3, 1688.5, 167.9, 301.9, 3740.6, 11.7, 0, 0];
  const R = f.brBopRow({m: M});   // v81: pozostałe bez banku centralnego (3740,6 − 11,7)
  assert.ok(Math.abs(R.t - 13347.7) < 1e-6 && Math.abs(R.t12 - (11 * 1700 + 13347.7)) < 1e-6 && R.m === '2026-07' && Math.abs(R.o - 3728.9) < 1e-6, JSON.stringify(R));
  M[5][6] = null; const R2 = f.brBopRow({m: M}); assert.equal(R2.t12, null, 'brak składnika w oknie = brak sumy');
  assert.ok(html.includes("t('br.bop.split',{d:bopMld(R.d),p:bopMld(R.p),o:bopMld(R.o)})") && html.includes("add('BRA',t('fo.bram')"));
  assert.ok(html.includes("t('br.reg.m',{m:instFoot(R.m)"));
  const x0 = html.indexOf('const EXTRA67='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA67='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['br.bop', 'br.bop.split', 'br.bop.note', 'br.reg.m', 'fo.bram']) assert.ok(dict[l][k], l + ' ' + k);
});

// v80: poprawki po piątym przeglądzie — pozostałe bez banku centralnego, statusy Eurostatu, licencja Statistics Canada z datą
test('v80: UE: kolumna pozostałych bez banku centralnego, status przy miesiącu; Kanada: formuła „Adapted from” z datą', () => {
  const a0 = html.indexOf('const UE={data:null};'), a1 = html.indexOf('/* v78: Kanada', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'escH', 'engDate', 'instFoot', 'etfCls', 'bopMld', 'LANG', 'LOCALE', 'ENG_DN', html.slice(a0, a1) + '\nreturn {UE, ueApply, ueHtml, ueMadd};')(
    T, () => {}, () => {}, s => String(s), s => String(s), s => 'F' + s, () => '', v => typeof v === 'number' ? String(v) : '—', 'xx', {}, {en: {of: x => x}});
  const S = (vals) => vals.map((v, i) => [f.ueMadd('2026-07', i - vals.length + 1), v]);
  f.ueApply({at: 'x', order: ['PL'], rows: {PL: {m: '2026-07', f: {'2026-07': 'e'}, s: {in_p: S([1]), in_d: S([1]), in_o: S([1])}}}});
  const h = f.ueHtml(f.UE.data);
  assert.ok(h.includes('<th>ue.c.o</th>') && h.includes('F2026-07 · ue.f.e'), h.slice(0, 900));
  const k0 = html.indexOf('function kanHtml(K){'), k1 = html.indexOf('\nfunction kanRegion(', k0);
  assert.ok(k0 > 0 && k1 > k0 && !html.slice(k0, k1).includes("t('kan.src'"), 'v96: formuła licencji na stronie Źródła, nie przy liczbach');
  const x0 = html.indexOf('const EXTRA68='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA68='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ue.sub', 'ue.c.o', 'ue.foot', 'ue.not', 'ue.f.e', 'ue.f.p', 'fo.pol', 'kan.src', 'bil.not']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['kan.src'].includes('Adapted from Statistics Canada') && dict.pl['kan.src'].includes('{d}') && dict.pl['ue.foot'].includes('poufne'));
  assert.ok(dict.pl['fo.pol'].includes('bez banku centralnego') && dict.pl['bil.not'].includes('TARGET2'));
});

// v81: Brazylia — pozostałe bez banku centralnego; ostatni miesiąc z kompletem; opisy po szóstym przeglądzie
test('v81: BCB: ostatni kompletny miesiąc zamiast niepełnego; brak pozycji banku centralnego = brak sumy', () => {
  const s0 = html.indexOf('const safeV='), s1 = html.indexOf('function safeHtml(', s0);
  const a0 = html.indexOf('function brBopT('), a1 = html.indexOf('function brBlock(){', a0);
  const f = new Function('instSign', 'nfmt', html.slice(s0, s1) + html.slice(a0, a1) + '\nreturn {brBopRow, safeMadd};')(v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d));
  const M = [['2026-06', 9074.8, -1055.3, 0, 0, 0, 6570.0, -1291.6, 0, 0], ['2026-07', 7460.5, 2158.3, 0, 0, 0, 3740.6, null, 0, 0]];
  const R = f.brBopRow({m: M});
  assert.equal(R.m, '2026-06', 'lipiec bez pozycji banku centralnego — czerwiec z kompletem');
  assert.ok(Math.abs(R.t - (9074.8 - 1055.3 + 6570.0 + 1291.6)) < 1e-6 && Math.abs(R.o - 7861.6) < 1e-6, JSON.stringify(R));
  const x0 = html.indexOf('const EXTRA69='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA69='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['br.sub', 'br.bop.note', 'br.bop.split', 'br.reg.m', 'br.src', 'g.hs.bcb', 'fo.bra', 'fo.bram', 'fo.sub', 'ue.foot', 'ue.not', 'kan.src', 'bil.not']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['br.src'].includes('22986') && dict.pl['ue.foot'].includes('Austrii i Luksemburga') && dict.pl['ue.not'].includes('kredyty dla rządu'));
  assert.ok(html.includes('22971 minus 22986, 23001, 23042'));
});

// v82: Korea — FSS; akcje i obligacje; ≈ USD kursem Fed; 12 miesięcy tylko z kolejnych miesięcy; wiersz regionu i przeglądu
test('v82: blok Korei: bln KRW i ≈ mld USD, suma 12 kolejnych miesięcy, wiersz regionu Japonia i Korea, podpięcie', () => {
  const s0 = html.indexOf('const safeV='), s1 = html.indexOf('function safeHtml(', s0);
  const k0 = html.indexOf('function kanLast('), k1 = html.indexOf('function kanHtml(', k0);
  const a0 = html.indexOf('const KOR={data:null};'), a1 = html.indexOf('function flowRows(){', a0);
  const oks = [], T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instRow', 'instFoot', 'instSign', 'nfmt', 'engDate', 'bopMld', html.slice(s0, s1) + html.slice(k0, k1) + html.slice(a0, a1) + '\nreturn {KOR, korApply, korHtml, korRegion, safeMadd};')(
    T, k => oks.push(k), () => {}, (l, v, x, n) => `[${l}|${v}|${n}]`, s => 'F' + s, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), s => s,
    v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—');
  assert.equal(f.korHtml(null), ''); assert.equal(f.korRegion('jpn'), '');
  const M = Array.from({length: 13}, (_, i) => [f.safeMadd('2026-08', i - 12), -1000, 500, -700, 350, 1400]);
  M[12] = ['2026-08', 344.0, -4736.0, 249.3, -3431.9, 1380.0];
  f.korApply({at: 'x', m: M}); assert.deepEqual(oks, ['korea']);
  const h = f.korHtml(f.KOR.data);
  assert.ok(h.includes('[kor.eq|+0.3 kor.u|sf.m{"m":"F2026-08"} · kor.usd{"v":"+0.2","r":"1380.0"} · kor.12{"v":"-10.7"}]'), h);
  assert.ok(h.includes('[kor.bd|-4.7 kor.u|sf.m{"m":"F2026-08"} · kor.usd{"v":"-3.4","r":"1380.0"} · kor.12{"v":"+0.8"}]'), h);
  const r = f.korRegion('jpn'); assert.ok(r.includes('<dt>kor.reg</dt>') && r.includes('"e":"+0.3","b":"-4.7","e12":"-10.7","b12":"+0.8"'), r);
  assert.equal(f.korRegion('chn'), '');
  assert.ok(html.includes("html+=(typeof korHtml==='function'&&typeof KOR!=='undefined')?korHtml(KOR.data):'';") && html.includes("${typeof korRegion==='function'?korRegion(s.id):''}"));
  assert.ok(html.includes("add('KOR',t('fo.kor')") && html.includes("srvJSON('korea')") && html.includes("korea:'FSS'"));
  const x0 = html.indexOf('const EXTRA70='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA70='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['kor.t', 'kor.sub', 'kor.eq', 'kor.bd', 'kor.u', 'kor.usd', 'kor.12', 'kor.not', 'kor.src', 'kor.reg.v', 'g.hs.fss', 'fo.kor', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['inst.sub'].includes('Korea'));
});

// v83: Korea — opisy zgodne z FSS (obligacje netto po wykupach, akcje KOSPI/KOSDAQ przy rozliczeniu), opóźnienie 9–31 dni, kurs miesięczny w przypisie
test('v83: Korea: opisy i opóźnienie zgodne ze źródłem', () => {
  const x0 = html.indexOf('const EXTRA71='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA71='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['kor.sub', 'kor.eq', 'kor.bd', 'kor.not', 'g.hs.fss', 'fo.kor', 'src.l.fss', 'fo.foot']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['kor.sub'].includes('wykupione przy zapadalności') && dict.pl['kor.sub'].includes('KOSPI i KOSDAQ') && dict.pl['kor.not'].includes('kraj rejestracji'));
  assert.ok(dict.pl['fo.foot'].includes('Korea: średnim kursem miesiąca'));
  assert.ok(!html.includes(".replace(/^([+−])/,'$1')"));
  assert.ok(html.includes('zwykle 2–4 tygodnie po końcu miesiąca (w ostatnim roku 9–31 dni)'));
});

// v84: przegląd całościowy tekstów — Korea na własnych kluczach (panel krypto odzyskał teksty), nieaktualne i przesadzone opisy poprawione
test('v84: klucze Korei nie kolidują z panelem krypto; słownik v84 nakładany jako ostatni; poprawione opisy', () => {
  const dictOf = n => { const a = 'const EXTRA' + n + '=', x0 = html.indexOf(a), x1 = html.indexOf(';\n', x0); return JSON.parse(html.slice(x0 + a.length, x1)); };
  const k70 = dictOf(70), k71 = dictOf(71);
  for (const l of ['pl', 'en']) {
    assert.ok(k70[l]['kor.t'] && k70[l]['kor.reg.v'] && k71[l]['kor.sub'], l);
    for (const k of ['kr.t', 'kr.sub', 'kr.not']) assert.ok(!(k in k70[l]) && !(k in k71[l]), l + ' ' + k);
  }
  for (const m of html.matchAll(/const EXTRA(\d+)=\{"/g)) {   // żaden słownik po v44 nie nadpisuje tytułu, podtytułu ani opisu panelu krypto
    const n = +m[1]; if (n <= 36) continue;
    const d = dictOf(n); for (const l in d) for (const k of ['kr.t', 'kr.sub', 'kr.not']) assert.ok(!(k in d[l]), 'EXTRA' + n + ' ' + l + ' ' + k);
  }
  const kh = html.slice(html.indexOf('function korHtml('), html.indexOf('function flowRows('));
  assert.ok(kh.includes("t('kor.t')") && kh.includes("t('kor.reg')") && !kh.includes("t('kr."));
  assert.ok(html.includes("<h2>${t('kr.t')}</h2><p class=\"pnote\">${t('kr.sub2')}</p>"), 'panel krypto czyta swoje klucze (v96: podtytuł bez nazwy dostawcy)');
  const d = dictOf(72), a39 = html.indexOf('Object.assign(I18N[l],EXTRA39[l]);'), a84 = html.indexOf('Object.assign(I18N[l],EXTRA72[l]);');
  assert.ok(a39 > 0 && a84 > a39, 'v84 nakładany po EXTRA39 (ostatni)');
  assert.ok(d.pl['cftc.not4'].includes('ICE Futures U.S.') && d.pl['g.hs.cftc'].includes('11 innych rynkach') && d.pl['g.hs.fx'].includes('Frankfurter'));
  assert.ok(d.pl['g.plain.cf'].startsWith('Waluty regionu „{r}”') && d.pl['g.plain.crypto'].includes('przybliżenie') && d.pl['g.stabflow'].includes('przybliżenie'));
  assert.ok(d.pl['pg.nosrc.d'].includes('1KW, 1R') && d.pl['g.q.srcv'].includes('Twelve Data') && d.pl['rail.in.g'] && d.pl['src.l.7w'] && d.pl['src.l.bis']);
  for (const l of ['de', 'fr', 'zh', 'ja']) assert.ok(d[l]['top.t'] && d[l]['g.q.limd'] && d[l]['pg.nosrc.d'] && d[l]['g.help.limd'], l);
  const E0 = {"pl": "w panelach pod mapą (TIC, bilans płatniczy, MOF Japonii)", "en": "in the panels below the map (TIC, balance of payments, Japan MOF)", "de": "in den Panels unter der Karte (TIC, Zahlungsbilanz, MOF Japan)", "es": "en los paneles bajo el mapa (TIC, balanza de pagos, MOF de Japón)", "fr": "dans les panneaux sous la carte (TIC, balance des paiements, MOF du Japon)", "it": "nei pannelli sotto la mappa (TIC, bilancia dei pagamenti, MOF del Giappone)", "pt": "nos painéis abaixo do mapa (TIC, balanço de pagamentos, MOF do Japão)", "ru": "в панелях под картой (TIC, платёжный баланс, МФ Японии)", "zh": "见地图下方面板（TIC、国际收支、日本财务省）", "ja": "地図の下のパネル（TIC、国際収支、日本の財務省）"};
  for (const l of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) assert.ok(/BIS|BIZ|BRI|BPI/.test(d[l]['g.help.2']) && d[l]['g.help.2'].includes('TIC') && !d[l]['g.help.2'].includes(E0[l]), l);
  assert.ok(d.pl['g.help.3'].includes('To model, nie pomiar') && d.en['g.help.3'].includes('not a measurement'));
  for (const l of ['pl', 'en']) for (const k of ['ue.not', 'bil.not']) assert.ok(!d[l][k].includes('TARGET2'), l + ' ' + k);
  assert.ok(html.includes("t('rail.in.g')") && html.includes('data-i18n="g.help.regtds"'));   // v96: Finnhub i Twelve Data opisane na stronie Źródła (okno pomocy ma tylko link)
  assert.ok(!html.includes("['Finnhub','g.hs.fh'],['Twelve Data','g.hs.td']") && html.includes('<p class="mtxt" id="gh-src"></p>'), 'v96: okno pomocy GLOBAL bez listy źródeł');
  assert.ok(!html.includes('tych danych nie ma') && !html.includes('(okresy 1T i 1M)') && !html.includes('Plik z serwera starszy niż trzy godziny') && !html.includes('tylko giełda CME.'));
  for (const s of ['Obok pokazujemy miary pokrewne', 'dopisek „pokazany poprzedni plik”', 'wpłaty i wypłaty BTC i ETH na giełdy</span>'])   // v96: tabela częstotliwości bez kolumny „Źródło” (źródła tylko na stronie Źródła)
    assert.ok(html.includes(s), s);
});

// v85: tryb CRYPTO — boczny panel to szacunek modelu, strona Przepływy i legenda to zmiana wartości
test('v85: teksty trybu CRYPTO nie nazywają zmian wyceny ani podziału modelu przepływem', () => {
  const a = 'const EXTRA73=', x0 = html.indexOf(a), d = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  for (const l of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) for (const k of ['rail.in', 'rail.out', 'leg.areaB', 'label.pct', 'pg.sectors.dc']) assert.ok(d[l][k], l + ' ' + k);
  assert.ok(d.pl['rail.in'].includes('szacunek') && d.pl['leg.areaB'].includes('zmianie wartości') && d.pl['pg.sectors.dc'].includes('zmiany wartości'));
  assert.ok(html.indexOf('Object.assign(I18N[l],EXTRA73[l]);') > html.indexOf('Object.assign(I18N[l],EXTRA72[l]);'));
  assert.ok(html.includes('<h2 class="pos">▲ ${t(\'rail.in.g\')}</h2>') && html.includes('<h2 class="neg">▼ ${t(\'rail.out.g\')}</h2>') && html.includes('<span data-i18n="rail.in"></span>'));   // v96: nagłówki zielony/czerwony
});

// v86 / v86.1: Tajlandia — ThaiBMA: blok (20 sesji jak w przeglądzie, małe kwoty „<0,1”), linia regionu Azja Płd.-Wsch., wiersz przeglądu
test('v86: Tajlandia (ThaiBMA): blok, sumy, stan, linia regionu, przegląd, podpięcie', () => {
  const z0 = html.indexOf('const zagNum='), z1 = html.indexOf('function zagBlock(', z0);
  const a0 = html.indexOf('/* v86: Tajlandia — nierezydenci w tajskich obligacjach (ThaiBMA; obce.json'), a1 = html.indexOf('/* v59: MFW COFER', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'instRow', 'instFoot', 'instSign', 'nfmt', 'engNum', 'escH', 'engDate', 'bopMld', 'instMld', 'LANG',
    'const ZAG={data:null};' + html.slice(z0, z1) + html.slice(a0, a1) + '\nreturn {ZAG, thBlock, thRegion, zagSum};')(
    T, (l, v, x, n) => `[${l}|${v}|${n}]`, s => 'F' + s, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), v => String(v), s => s, s => s,
    v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—', v => (v / 1000).toFixed(1), 'pl');
  assert.equal(f.thBlock(), ''); assert.equal(f.thRegion('asean'), '');
  const day = i => '2026-08-' + String(i + 1).padStart(2, '0');
  const d = Array.from({length: 23}, (_, i) => [day(i), 1000, 1000, 600, 400, 0, 900000 + 100 * i, 30.8, 32.5, '2026-08-01']);
  d[22] = ['2026-09-24', 3216, 3216, 1695, 1521, 0, 920455.75, 98.9, 32.5, '2026-09-18'];
  f.ZAG.data = {at: 'x', th: {at: 'x', d}};
  const h = f.thBlock();
  assert.ok(h.includes('[th.nf|+3.2 th.mld|ob.day F2026-09-24 · th.usd{"v":"+99","d":"2026-09-18"} · th.split{"s":"+1.7","l":"+1.5","x":"0"}]'), h);
  assert.ok(h.includes('[th.sum{"n":20,"w":"sesji"}|+22.2 th.mld|th.s5{"v":"+7.2"}]'), h);
  assert.ok(h.includes('[th.hold|920.5 th.mld|inst.asof F2026-09-24 · th.hold.usd{"v":"28.3"} · th.hold.ch{"d":"2026-08-03","v":"+20.3"}]'), h);
  d[22][5] = 3; assert.ok(f.thBlock().includes('"x":"&lt;0.1"'), 'wykup 3 mln THB — „<0,1”, nie „0,0”'); d[22][5] = 0;
  d[20][1] = null; assert.ok(f.thBlock().includes('th.s5{"v":"—"}'), 'brak dnia w oknie = brak sumy, nie zero');
  const r = f.thRegion('asean'); assert.ok(r.includes('<dt>th.reg</dt>') && r.includes('"v":"+3.2"') && r.includes('"n":20') && r.includes('"h":"920.5"'), r);
  assert.equal(f.thRegion('chn'), '');
  assert.ok(html.includes("html+=typeof thBlock==='function'?thBlock():'';") && html.includes("${typeof thRegion==='function'?thRegion(s.id):''}"));
  assert.ok(html.includes("ses('th',7,'THA','fo.tha','fo.u.usdx');") && html.includes("if(okD(j.th))gOk('obce_th');") && html.includes("obce_th:'ThaiBMA'"));
  assert.ok(html.includes('<span class="cell">nierezydenci w tajskich obligacjach</span>'));
  const dictOf = n => { const a = 'const EXTRA' + n + '=', x0 = html.indexOf(a); return JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0))); };
  const dict = dictOf(74), fix = dictOf(75);
  for (const l of ['pl', 'en']) for (const k of ['th.t', 'th.sub', 'th.nf', 'th.split', 'th.hold', 'th.hold.ch', 'th.not', 'th.src', 'th.reg.v', 'fo.tha', 'g.hs.thbma', 'src.l.th', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
  for (const l of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) assert.ok(dict[l]['g.q.limd'] && dict[l]['g.help.limd'], l);
  assert.ok(dict.pl['g.q.limd'].includes('Hongkong, Tajlandia;') && dict.pl['inst.sub'].includes('Hongkong, Tajlandia i dolary'));
  assert.ok(fix.pl['th.split'].includes('z wykupem w ciągu roku') && fix.en['th.split'].includes('maturing within 1 year') && fix.pl['th.not'].includes('od 16:00 poprzedniego dnia roboczego'));
});

// v87: Polska — MF: zmiana stanu SPW u nierezydentów (tylko między istniejącymi miesiącami), tabele typów, regionów i krajów, linia regionu, przegląd
test('v87: Polska (MF): blok, zmiany, tabele, kraje, linia regionu Europa, przegląd, podpięcie', () => {
  const a0 = html.indexOf('/* v87: Polska — Ministerstwo Finansów: nierezydenci w krajowych SPW (plik serwera'), a1 = html.indexOf('const KOR={data:null};', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instRow', 'instFoot', 'nfmt', 'escH', 'engDate', 'bopMld', 'LANG', 'instMld', html.slice(a0, a1) + '\nreturn {SPW, spwApply, spwHtml, spwRegion, spwLast, spwMadd};')(
    T, () => {}, () => {}, (l, v, x, n) => `[${l}|${v}|${n}]`, s => 'F' + s, (v, d) => v.toFixed(d), s => s, s => s,
    v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—', 'pl', v => (v / 1000).toFixed(1));
  assert.equal(f.spwMadd('2026-01', -1), '2025-12'); assert.equal(f.spwMadd('2026-07', -12), '2025-07'); assert.equal(f.spwMadd('2025-12', 1), '2026-01');
  assert.equal(f.spwHtml(null), ''); assert.equal(f.spwRegion('eur'), '');
  const M = [['2025-07', 180000, 179900, 100], ['2026-05', 206240, 205596, 644], ['2026-06', 198955.2, 198832, 123], ['2026-07', 204131.8, 204009, 123]];
  const S = {at: 'x', m: M, t: {omni: [['2026-06', 95249.8], ['2026-07', 97615.9]], cb: [['2026-07', 14485.9]]}, r: {asia: [['2025-07', 30000], ['2026-07', 31590.6]]},
    kr: [{m: '2026-07', c: [['Japonia', 'Japan', 18031.64, 19.59], ['Holandia', 'Netherlands (the)', 7678.98, 8.34]]}, {m: '2026-06', c: [['Japonia', 'Japan', 17382.46, 19.71]]}]};
  f.spwApply(S);
  const L = f.spwLast(S); assert.equal(L.m, '2026-07'); assert.ok(Math.abs(L.d1 - 5176.6) < 0.01); assert.ok(Math.abs(L.d12 - 24131.8) < 0.01);
  const h = f.spwHtml(S);
  assert.ok(h.includes('[spw.d1|+5.2 spw.u|spw.d1.n{"m":"F2026-07","s":"204.1","y":"+24.1"} · spw.omni{"p":"48"}]'), h);
  S.kr[0].c.push(['Pozostałe kraje', 'Others', 7043.42, 7.65]); S.kr[1].c.push(['Pozostałe kraje', 'Others', 6000.0, 6.9]);
  const hk = f.spwHtml(S); S.kr[0].c.pop(); S.kr[1].c.pop();
  assert.ok(hk.includes('<td><span class="cell">Pozostałe kraje</span></td><td><span class="cell mono">7.0</span></td><td><span class="cell mono">7.7%</span></td><td><span class="cell mono">—</span></td>'), 'v87.1: „Pozostałe kraje” bez zmiany');
  assert.ok(hk.includes('spw.tab.k{"m":"2026-07","x":"32.8","p":"16"}'), 'v87.1: suma listy krajów i jej udział w stanie');
  assert.ok(h.includes('spw.ty.omni</span></td><td><span class="cell mono">97.6</span></td><td><span class="cell mono">+2.4</span></td><td><span class="cell mono">—</span></td>'), 'brak miesiąca = „—”, nie zero');
  assert.ok(h.indexOf('spw.ty.omni') < h.indexOf('spw.ty.cb'), 'od największego');
  assert.ok(h.includes('spw.rg.asia</span></td><td><span class="cell mono">31.6</span></td><td><span class="cell mono">—</span></td><td><span class="cell mono">+1.6</span></td>'));
  assert.ok(h.includes('spw.tab.k{"m":"2026-07","x":"25.7","p":"13"}') && h.includes('<td><span class="cell">Japonia</span></td><td><span class="cell mono">18.0</span></td><td><span class="cell mono">19.6%</span></td><td><span class="cell mono">+0.6</span></td>'));
  assert.ok(h.includes('<td><span class="cell">Holandia</span></td><td><span class="cell mono">7.7</span></td><td><span class="cell mono">8.3%</span></td><td><span class="cell mono">—</span></td>'), 'kraj bez poprzedniego miesiąca — bez zmiany');
  S.r.afr = [['2026-07', 26.4]]; assert.ok(f.spwHtml(S).includes('spw.rg.afr</span></td><td><span class="cell mono">&lt;0.1</span>'), 'mały stan — „<0,1”'); delete S.r.afr;
  const r = f.spwRegion('eur'); assert.ok(r.includes('<dt>spw.reg</dt>') && r.includes('"d":"+5.2","s":"204.1"'), r); assert.equal(f.spwRegion('usa'), '');
  S.m = [['2026-05', 206240], ['2026-07', 204131.8]]; assert.equal(f.spwLast(S).d1, null, 'bez czerwca — zmiana lipca to brak, nie różnica z majem');
  assert.ok(html.includes("srvJSON('spw').then(j=>{spwApply(j);})") && html.includes("html+=(typeof spwHtml==='function'&&typeof SPW!=='undefined')?spwHtml(SPW.data):'';"));
  assert.ok(html.includes("${typeof spwRegion==='function'?spwRegion(s.id):''}") && html.includes("add('POL',t('fo.polspw'),t('fo.m',{m:L.m}),L.d1,'fo.u.pln',L.m);"));
  assert.ok(html.includes("spw:()=>SPW.data&&SPW.data.at") && html.includes("spw:'MF SPW'"));
  assert.ok(html.includes('<span class="cell">nierezydenci w krajowych papierach skarbowych (zmiana stanu)</span>'));
  const a = 'const EXTRA76=', x0 = html.indexOf(a), dict = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  for (const l of ['pl', 'en']) for (const k of ['spw.t', 'spw.sub', 'spw.d1', 'spw.d1.n', 'spw.omni', 'spw.not', 'spw.src', 'spw.reg.v', 'spw.ty.omni', 'spw.rg.asia', 'fo.polspw', 'fo.u.pln', 'g.hs.spw', 'src.l.spw', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
});

// v87.1: Polska (MF) po przeglądzie — zmiana stanu (nie transakcje), udział w liście, rachunki zbiorcze, wiersz przeglądu opisany
test('v87.1: Polska (MF): opisy po przeglądzie, zasada 2 i przegląd', () => {
  const a = 'const EXTRA77=', x0 = html.indexOf(a), d = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(d.pl['fo.sub'].includes('Wyjątek: wiersz Polski z Ministerstwa Finansów to zmiana stanu') && d.en['fo.sub'].includes('Exception: the Poland row'));
  assert.ok(d.pl['spw.d1'].includes('Zmiana stanu') && !d.pl['spw.sub'].includes('zakupy netto minus wykupy') && d.pl['spw.not'].includes('z założenia'));
  assert.ok(d.pl['spw.c.sh'] === 'Udział w liście' && d.pl['spw.tab.k'].includes('{x}') && d.pl['spw.tab.k'].includes('{p}') && d.pl['fo.polspw'].includes('wycinek kapitału z wiersza wyżej'));
  assert.ok(d.pl['spw.src'].includes('Dane przetworzone') && d.en['spw.src'].includes('Processed data'));
  assert.ok(html.includes('oraz zmianę stanu papierów skarbowych u nierezydentów w wartości nominalnej: polskich (Ministerstwo Finansów)'));   // v88: rozszerzone o Meksyk
  assert.ok(!html.includes('polskie papiery skarbowe u nierezydentów (Ministerstwo Finansów) oraz kwartalne'), 'nie na liście transakcji');
  assert.ok(html.includes("replace(/\\s*\\(the\\)/g,'')"), 'angielskie nazwy krajów bez „(the)”');
});

// v88: Meksyk — Banxico: zmiana stanu (20 sesji, dzień, 5 sesji, od końca roku), stan i udział w obiegu, ≈ USD, linia regionu, przegląd
test('v88: Meksyk (Banxico): blok, zmiany, stan, linia regionu Ameryka Łacińska, przegląd, podpięcie', () => {
  const a0 = html.indexOf('/* v88: Meksyk — Banco de México (plik serwera'), a1 = html.indexOf('const KOR={data:null};', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instRow', 'instFoot', 'nfmt', 'escH', 'engDate', 'bopMld', 'zagSes', html.slice(a0, a1) + '\nreturn {MX, mxApply, mxHtml, mxRegion, mxLast};')(
    T, () => {}, () => {}, (l, v, x, n) => `[${l}|${v}|${n}]`, s => 'F' + s, (v, d) => v.toFixed(d), s => s, s => s,
    v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—', n => n === 1 ? 'sesja' : 'sesji');
  assert.equal(f.mxHtml(null), ''); assert.equal(f.mxRegion('lat'), '');
  const day = i => { const x = new Date(Date.UTC(2026, 7, 1) + i * 864e5); return x.toISOString().slice(0, 10); };
  const d = [['2025-12-30', 1740000, 15200000], ['2025-12-31', 1739824.42, 15210747.57]].concat(Array.from({length: 25}, (_, i) => [day(i), 1800000 + 100 * i, 16000000]));
  d.push(['2026-09-14', 1788646.44, 16097115.95]);
  const M = {at: 'x', d, fx: [18.25, '2026-09-18']};
  f.mxApply(M); const L = f.mxLast(M);
  assert.equal(L.n, 20); assert.equal(L.y, '2025'); assert.ok(Math.abs(L.dy - (1788646.44 - 1739824.42)) < 1e-6, 'od końca roku — z 31.12');
  assert.ok(Math.abs(L.d1 - (1788646.44 - 1802400)) < 1e-6);
  const h = f.mxHtml(M);
  assert.ok(h.includes('[mx.d{"n":20,"w":"sesji"}|−'.replace('−', '')) || h.includes('[mx.d{"n":20,"w":"sesji"}|'), h);
  assert.ok(h.includes('"y":"2025","vy":"+48.8","u":"mx.usd{\\"v\\":\\"-0.6\\",\\"r\\":\\"2026-09-18\\"}"'), h);
  assert.ok(h.includes('[mx.lv|1788.6 mx.u|mx.lv.n{"d":"F2026-09-14","u":"mx.lv.usd{\\"v\\":\\"98.0\\"}","p":"11.1","t":"16097.1"}]'), h);
  const r = f.mxRegion('lat'); assert.ok(r.includes('<dt>mx.reg</dt>') && r.includes('"s":"1788.6"') && r.includes('"n":20'), r); assert.equal(f.mxRegion('eur'), '');
  const M2 = {at: 'x', d: [['2026-09-14', 1788646.44, null]]}; const h2 = f.mxHtml(M2);
  assert.ok(h2.includes('"p":"—"') && !h2.includes('mx.usd{'), 'bez całości i kursu — „—”, nie zero');
  assert.ok(html.includes("srvJSON('meksyk').then(j=>{mxApply(j);})") && html.includes("html+=(typeof mxHtml==='function'&&typeof MX!=='undefined')?mxHtml(MX.data):'';"));
  assert.ok(html.includes("${typeof mxRegion==='function'?mxRegion(s.id):''}") && html.includes("add('MEX',t('fo.mex'),t('fo.s',{n:L.n,x:zagSes(L.n),d:L.d}),L.rt&&L.dn!=null?L.dn/L.rt:null,'fo.u.usdx',L.d);"));
  assert.ok(html.includes("meksyk:()=>MX.data&&MX.data.at") && html.includes("meksyk:'Banxico'"));
  assert.ok(html.includes('<span class="cell">nierezydenci w meksykańskich papierach rządowych (zmiana stanu)</span>'));
  assert.ok(html.includes('polskich (Ministerstwo Finansów) i meksykańskich (Banco de México).'));
  const a = 'const EXTRA78=', x0 = html.indexOf(a), dict = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  for (const l of ['pl', 'en']) for (const k of ['mx.t', 'mx.sub', 'mx.d', 'mx.d.n', 'mx.lv', 'mx.lv.n', 'mx.not', 'mx.src', 'mx.reg.v', 'fo.mex', 'g.hs.bmx', 'src.l.bmx', 'fo.sub']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['fo.sub'].includes('Wyjątki: wiersz Polski z Ministerstwa Finansów i wiersz Meksyku'));
});

// v88.1: Meksyk — podział na rodzaje papierów (Bonos M, Cetes, Udibonos, reszta), liczba USD przy zmianie 20 sesji, opisy po przeglądzie
test('v88.1: Meksyk (Banxico): rodzaje papierów, reszta do całości, brak = „—”, opisy', () => {
  const a0 = html.indexOf('/* v88: Meksyk — Banco de México (plik serwera'), a1 = html.indexOf('const KOR={data:null};', a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('t', 'gOk', 'renderInst', 'instRow', 'instFoot', 'nfmt', 'escH', 'engDate', 'bopMld', 'zagSes', html.slice(a0, a1) + '\nreturn {mxHtml, mxLast, mxI};')(
    T, () => {}, () => {}, (l, v, x, n) => `[${l}|${v}|${n}]`, s => 'F' + s, (v, d) => v.toFixed(d), s => s, s => s,
    v => typeof v === 'number' ? (v > 0 ? '+' : '') + (v / 1000).toFixed(1) : '—', n => n === 1 ? 'sesja' : 'sesji');
  const day = i => { const x = new Date(Date.UTC(2026, 7, 1) + i * 864e5); return x.toISOString().slice(0, 10); };
  const d = [['2025-12-31', 1739824.42, 15210747.57, 1400000, 250000, 60000]].concat(Array.from({length: 21}, (_, i) => [day(i), 1800000, 16000000, 1500000, 210000, 50000]));
  d.push(['2026-09-14', 1788646.44, 16097115.95, 1512900, 202500, 46000]);
  const M = {at: 'x', d, fx: [17.11, '2026-09-11']}, h = f.mxHtml(M);
  assert.ok(h.includes('<tr><td><span class="cell">mx.i.bon</span></td><td><span class="cell mono">1512.9</span></td><td><span class="cell mono">84.6%</span></td><td><span class="cell mono">+12.9</span></td><td><span class="cell mono">+112.9</span></td></tr>'), h);
  assert.ok(h.includes('<tr><td><span class="cell">mx.i.oth</span></td><td><span class="cell mono">27.2</span></td>'), 'reszta = całość − trzy rodzaje');
  assert.ok(h.includes('mx.c.dn{"n":20,"w":"sesji"}') && h.includes('mx.c.dy{"y":"2025"}'));
  d[d.length - 1][4] = null; const h2 = f.mxHtml(M);
  assert.ok(h2.includes('<tr><td><span class="cell">mx.i.oth</span></td><td><span class="cell mono">—</span></td>'), 'brak Cetes — reszta to brak, nie zero');
  assert.equal(f.mxHtml({at: 'x', d: [['2026-09-14', 1788646.44, 16097115.95]]}).includes('mx.tab'), false, 'stary plik bez rodzajów — bez tabeli');
  const a = 'const EXTRA79=', x0 = html.indexOf(a), dict = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(dict.pl['mx.d.n'].startsWith('do {d}{u} ·') && dict.en['mx.d.n'].startsWith('to {d}{u} ·'), 'USD przy zmianie 20 sesji, nie przy „od końca roku”');
  assert.ok(dict.pl['mx.not'].includes('repo') && dict.pl['mx.not'].includes('instytucji przechowującej') && dict.pl['mx.not'].includes('IPAB'));
  assert.ok(dict.pl['inst.sub'].includes('meksykańskich papierów rządowych') && dict.pl['fo.sub'].includes('skarbowych (rządowych)'));
});

test('v89: TRENDY — trzecia zakładka, sekcja po GLOBAL, tryb w setMode/applyVis, klawiatura po indeksie, menu jak GLOBAL', () => {
  assert.ok(html.includes('<button role="tab" id="tab-trendy" aria-selected="false" aria-controls="trendy" data-i18n="tab.trendy"></button>'));
  assert.ok(html.indexOf('id="tab-trendy"') > html.indexOf('id="tab-crypto"'), 'TRENDY po CRYPTO');
  const s = '<section class="global" id="trendy" role="tabpanel" aria-labelledby="tab-trendy" hidden></section>';
  assert.ok(html.includes(s) && html.indexOf(s) > html.indexOf('<section class="panel pcard" id="inst" hidden></section>'), 'sekcja po GLOBAL (pierwsza .head-row .badge nadal z CRYPTO)');
  assert.ok(html.includes("$('#trendy').hidden=!(ov&&st.mode==='trendy');"));
  assert.ok(html.includes("['global','crypto','trendy'].forEach(k=>$('#tab-'+k).setAttribute('aria-selected',m===k));"));
  assert.ok(html.includes("if(m==='trendy')renderTrendy();"));
  assert.ok(html.includes("$('#tab-trendy').addEventListener('click',()=>setMode('trendy'));"));
  assert.ok(!html.includes("b.id==='tab-crypto'?$('#tab-global'):$('#tab-crypto')"), 'strzałki: po indeksie, nie para GLOBAL/CRYPTO');
  assert.ok(html.includes("function gActive(){return st.mode!=='crypto';}"), 'strony z menu w TRENDACH pokazują dane GLOBAL');
  assert.ok(html.includes("if(document.hidden||!gActive())return;"), '… i dane GLOBAL odświeżają się także w TRENDACH');
  assert.ok(html.includes("if(sc)sc.hidden=st.mode!=='crypto';"), 'ustawienia sceny 3D tylko w CRYPTO');
  assert.ok(html.includes("if(st.mode==='trendy'){if(page!=='overview')setPage('overview');const d=$('#trd-method');"), 'znak zapytania w TRENDACH otwiera „Jak liczymy” (także z innej strony menu)');
  assert.ok(html.includes('trdLoad();trdAuto();'), 'plik trendów wczytywany na starcie i co 20 min');
  assert.ok(html.includes("if(typeof renderTrendy==='function'&&st.mode==='trendy')renderTrendy();"), 'zmiana języka odświeża TRENDY');
  assert.ok(html.includes('.tabs button{padding:9px 16px}') && html.includes('@media (max-width:400px){.tabs button{padding:9px 10px;letter-spacing:.01em}}'), 'trzy zakładki mieszczą się na telefonie');
});

test('v89: EXTRA80 — nazwa zakładki w 10 językach, pl i en z tymi samymi kluczami, stany bez słów o przyszłości i bez „kupuj/sprzedaj”', () => {
  const a = 'const EXTRA80=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(x0 > html.indexOf('for(const l in EXTRA79)'), 'po EXTRA79');
  assert.ok(html.includes('for(const l in EXTRA80)if(I18N[l])Object.assign(I18N[l],EXTRA80[l]);'));
  for (const l of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) assert.ok(D[l] && D[l]['tab.trendy'], 'tab.trendy ' + l);
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort());
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  const lit = [...blk.matchAll(/t\('(trd\.[A-Za-z0-9_.]+)'/g)].map(m => m[1]).filter(k => !/[._]$/.test(k));   /* v93: też przedrostki kluczy („trd.s.fe_”) */
  const ALL = {pl: {}, en: {}};   /* v93: klucze z EXTRA80 i późniejszych słowników TRENDÓW */
  for (const m of html.matchAll(/const (EXTRA(?:8\d|9\d))=/g)) { const x = html.indexOf(m[0]), d = JSON.parse(html.slice(x + m[0].length, html.indexOf(';\n', x))); Object.assign(ALL.pl, d.pl || {}); Object.assign(ALL.en, d.en || {}); }
  for (const k of lit) assert.ok(ALL.pl[k] && ALL.en[k], 'brak klucza ' + k);
  const ST = ['in_up', 'in_flat', 'in_down', 'in_rev', 'in_new', 'in_dir', 'out_up', 'out_flat', 'out_down', 'out_rev', 'out_new', 'out_dir'];
  for (const s of ST.concat(['mixed', 'none', 'short', 'gap', 'stale'])) assert.ok(D.pl['trd.sn.' + s] && D.en['trd.sn.' + s], 'trd.sn.' + s);
  for (const m of ['stock', 'exch', 'supply', 'pos']) for (const s of ST.concat(['none'])) assert.ok(D.pl[`trd.sn.${m}.${s}`] && D.en[`trd.sn.${m}.${s}`], `trd.sn.${m}.${s}`);
  for (const s of ['up_cont', 'up_new', 'dn_fade', 'up_fade', 'dn_new', 'dn_cont', 'flat']) assert.ok(D.pl['trd.ps.' + s] && D.en['trd.ps.' + s]);
  for (const id of ['in_eq', 'in_bd', 'tw', 'hk', 'th', 'br', 'tr_eq', 'tr_bd', 'jp_eq', 'jp_bd', 'mx', 'etf_btc', 'etf_eth', 'etf_sol', 'etf_xrp', 'stab', 'cm_btc', 'cm_eth',
                    'cf_usd', 'cf_eur', 'cf_jpy', 'cf_spx', 'cf_msciem', 'cf_btc', 'cf_eth']) {
    assert.ok(D.pl['trd.s.' + id] && D.en['trd.s.' + id], 'trd.s.' + id);
    assert.ok(D.pl['trd.src.' + id.split('_')[0]], 'trd.src.' + id.split('_')[0]);
  }
  for (const s of ['SPY', 'EWC', 'ILF', 'VGK', 'KSA', 'TUR', 'EIS', 'EZA', 'INDA', 'MCHI', 'EWJ', 'EWY', 'ASEA', 'EWA']) assert.ok(D.pl['trd.px.' + s] && D.en['trd.px.' + s]);
  const bad = /kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|warto kupi|okazj|sygna[łl] (kupna|sprzeda)|prognozuj|rekomend|\btrwa(?![a-ząćęłńóśźż])|odbic|odbij|cofa si|zaczyna|\bbuy\b|\bsell\b|worth buying|opportunit|recommend|forecast|rebound|continues|pulling back|\bstarts\b/i;
  for (const l of ['pl', 'en']) for (const k in D[l]) {
    if (!/^trd\.(sn|ps|sum|k|s|px|x|f|c|p|h1|sub|n)\b/.test(k)) continue;   /* ostrzeżenia (disc, m.*, b.concl*) cytują te słowa w zaprzeczeniu */
    assert.doesNotMatch(D[l][k], bad, `${l} ${k}: ${D[l][k]}`);
  }
  for (const k of ['trd.sn.pos.in_up', 'trd.sn.pos.out_up']) assert.ok(D.pl[k].includes('pozycja netto') && D.en[k].includes('net position'), 'CFTC: zmiana pozycji netto, nie „nowe zakłady”');
  assert.ok(D.pl['trd.disc'].includes('ani rekomendacja') && D.en['trd.disc'].includes('not a recommendation'), 'ostrzeżenie zawsze na górze');
  assert.ok(!D.pl['trd.disc'].includes('nie wynika') && !D.pl['trd.m.5'].includes('warto kupić'), 'ostrzeżenie nie zależy od statystyki');
});

test('v89: TRENDY — karty, kolejność stanów, brak = „—”, bez oceny przy braku danych, kafle z pełną historią, wniosek z liczb', () => {
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */');
  const a = 'const EXTRA80=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const el = {innerHTML: '', q: [], querySelectorAll() { return this.q; }, querySelector() { return null; }}, st = {mode: 'trendy'};
  const nf = (v, d = 0) => v.toFixed(d), sg = v => v > 0 ? '+' : v < 0 ? '−' : '';
  const f = new Function('$', 't', 'st', 'srvJSON', 'escH', 'etfCls', 'gAgeNote', 'fInt', 'sg', 'nfmt', 'fPct', 'zagSes', 'engDate', 'LANG', 'LOCALE', 'I18N',
    html.slice(b0, b1) + '\nreturn {TRD, trdApply, trdAmt, renderTrendy, trdVerdict};')(
    () => el, T, st, () => Promise.resolve(null), s => String(s).replace(/</g, '&lt;'), v => v > 0 ? 'pos' : v < 0 ? 'neg' : '', d => ' ·age(' + d + ')',
    v => sg(v) + Math.abs(v), sg, nf, (v, d) => sg(v) + nf(Math.abs(v), d) + '%', n => 'ses', s => 'DT(' + s + ')', 'pl', {pl: 'pl-PL'}, {pl: {}, en: D.en});
  assert.equal(f.trdAmt(null, 'USD'), '—'); assert.equal(f.trdAmt(0.01, 'USD'), '+&lt;0.1 trd.u.m USD', 'mała kwota nie jest zerem');
  assert.equal(f.trdAmt(-41054.2, 'BTC'), '−41054 BTC'); assert.equal(f.trdAmt(0.2, 'BTC'), '+&lt;1 BTC', 'ułamek monety nie jest „0 BTC”');
  assert.equal(f.trdAmt(1538, 'CT'), '+1538 trd.u.ct'); assert.equal(f.trdAmt(-1522.8, 'JPY'), '−1522.8 trd.u.b JPY', 'JPY: plik w mld → mln × 1000');
  f.renderTrendy();
  assert.ok(el.innerHTML.includes('trd.nodata') && el.innerHTML.includes('trd.disc') && el.innerHTML.includes('live off') && el.innerHTML.includes('id="trd-method"'),
            'bez pliku — komunikat, ostrzeżenie i opis metody, nie zera');
  f.trdApply({at: 'x'}); assert.equal(f.TRD.data, null, 'plik bez list f/p — odrzucony');
  const row = (o) => Object.assign({g: 'eq', m: 'flow', sz: 5, cur: 'USD', date: '2026-09-24', age: 1, n: 8, lc: false, s: 1, sg: 1, x: false}, o);
  const data = {at: '2026-09-25T10:00:00Z', f: [
    row({id: 'tw', st: 'out_dir', w: -500, d: -1.5, cur: 'TWD', wu: -15, du: -90, lc: true, n: 4}),
    row({id: 'hk', st: 'in_dir', w: 24306.46, wu: 3098.1, d: 1.73, base: 10106.06, du: 1810, cur: 'HKD', s: 14, lc: true, n: 4}),
    row({id: 'th', g: 'bd', st: 'in_new', w: 5497, wu: 164.7, d: 1.12, base: -2944.3, du: 252.9, cur: 'THB', ph: 0.6}),
    row({id: 'jp_bd', g: 'bd', st: 'in_new', sz: 1, w: 2236.2, wu: 14081.6, d: 2.68, base: 34.9, du: 13861.8, cur: 'JPY', fxm: '2026-08'}),
    row({id: 'jp_eq', st: 'out_new', sz: 1, w: -1522.8, wu: -9589.2, d: -2.78, base: 146.1, du: -10509.4, cur: 'JPY'}),
    row({id: 'in_eq', st: 'short', w: 543.78, n: 2}),
    row({id: 'tr_bd', g: 'bd', st: 'stale', sz: 1, w: -116.9, x: true, dz: 5, n: 8}),
    row({id: 'mx', g: 'bd', m: 'stock', st: 'out_new', w: -13103.56, wu: -765.8, d: -1.24, du: -810.7, cur: 'MXN'}),
    row({id: 'cm_btc', g: 'cr', m: 'exch', sz: 7, st: 'out_dir', w: -41054.24, wu: -3495.5, d: -2.98, cur: 'BTC', lc: true, n: 4}),
    row({id: 'cf_spx', g: 'pos', m: 'pos', sz: 1, st: 'in_rev', w: 47961, d: 1.92, cur: 'CT', roll: true}),
    row({id: 'bad', st: 'weird'}), row({id: 'x<y', st: 'in_up'}), row({id: 'hk', st: 'in_up', cur: '<b>'})],
    p: [{id: 'SPY', g: 'eq', date: '2026-09-24', w: 0.6, pr: -0.84, typ: 1.9, st: 'flat'}, {id: 'EWJ', g: 'eq', date: '2026-09-24', w: -2.14, pr: 3.3, typ: 2.6, st: 'up_fade'},
        {id: 'EZA', g: 'eq', date: '2026-09-24', w: -4.06, pr: -2.28, typ: 4.3, st: 'dn_new'}, {id: 'KSA', g: 'eq', date: '2026-09-24', w: -1.52, pr: -1.73, typ: 2.1, st: 'dn_new'},
        {id: 'BTC', g: 'cr', date: '2026-09-25', w: 8.58, pr: -1.49, st: 'up_new'}],
    b: [{id: 'th', k: 14, n: 28, weeks: 28, from: '2025-09-15', to: '2026-08-17', ci: [32.6, 67.4]}, {id: 'px', k: 143, n: 294, weeks: 32, from: '2026-02-02', to: '2026-09-14', ci: [32.4, 65.1]}]};
  f.trdApply(data); const h = el.innerHTML;
  assert.ok(h.includes('live wait') || h.includes('live on'));
  assert.ok(!h.includes('x<y') && !h.includes('<b>USD') && !h.includes('trd.s.bad'), 'nieznany stan, dziwne id i waluta z pliku — pominięte');
  const pf = h.slice(h.indexOf('trd.f.t'));
  const at = id => pf.indexOf('<span>trd.s.' + id + '</span>');
  assert.ok(at('jp_bd') < at('th') && at('th') < at('hk') && at('hk') < at('jp_eq') && at('jp_eq') < at('mx') && at('mx') < at('tw'), 'kolejność stanów, potem siła (|d|)');
  assert.ok(h.includes('<b class="pos">+24.3 trd.u.b HKD<small>trd.sn.in_dir</small></b>'), 'Hongkong: 4 tygodnie historii — sam kierunek');
  assert.ok(h.includes('≈ +3.10 trd.u.b USD') && h.includes('trd.n.sp{"n":14,"x":"ses"}') && h.includes('trd.n.ph.hold{"p":"+0.60%"}'));
  assert.ok(h.includes('≈ +14.1 trd.u.b USD (trd.n.fxm{"m":"08.2026"})'), 'kurs EBC z miesiącem MM.RRRR');
  assert.ok(h.includes('trd.sn.stock.out_new') && h.includes('trd.sn.pos.in_rev') && h.includes('trd.n.roll'));
  assert.ok(!h.includes('trd.sn.exch.out_dir') && !h.includes('trd.s.cm_btc'), 'v96: giełdy krypto — w widoku „Trendy krypto”, nie w global');
  assert.ok(h.includes('trd.rest{"n":2}') && h.includes('trd.sn.short{"n":2}') && h.includes('trd.sn.stale'), 'za krótka historia i brak nowych danych — w rozwijanym bloku');
  const stale = h.slice(h.indexOf('<span>trd.s.tr_bd</span>'), h.indexOf('</div>', h.indexOf('<span>trd.s.tr_bd</span>')));
  assert.ok(!stale.includes('trd.n.x') && !stale.includes('trd.n.day'), 'brak nowych danych — bez „wyjątkowo” i bez oceny dnia');
  assert.ok(h.includes('<b>trd.sum.t</b> <b>trd.s.jp_bd</b>: trd.sn.in_new · <b>trd.s.th</b>: trd.sn.in_new'), 'podsumowanie: nazwy i stany, bez sumowania źródeł');
  assert.ok(h.includes('trd.k.in</span></div><div class="k-val pos">≈ +14.1 trd.u.b USD</div>'), 'kafel napływu: największe odchylenie w USD, tylko pełna historia (Japonia, nie Hongkong); v96: zielony');
  assert.ok(h.includes('trd.k.out</span></div><div class="k-val neg">≈ −9.59 trd.u.b USD</div>'), 'kafel odpływu: Japonia (Meksyk — zmiana stanu, nie w kaflach); v96: czerwony');
  assert.ok(h.includes('trd.k.fade</span></div><div class="k-val na">—</div>'), 'brak słabnących — „—”, nie zero; v96: szary');
  assert.ok(h.includes('trd.n.base{"v":"+34.9 trd.u.b JPY"}'), 'kafel: obok kwoty zwykły poziom');
  assert.ok(h.includes('trd.k.pdn</span></div><div class="k-val neg">−4.06%</div>') && h.includes('trd.k.pup</span></div><div class="k-val neu">+0.60%</div>') && h.includes('<span class="dlt chg">•</span><span class="ksrc" title="trd.ps.flat">'), 'v98.2: kolor kwoty według stanu, jak na karcie — +0,60% „bez wyraźnego ruchu” żółte, nie zielone');
  assert.ok(h.indexOf('<span>trd.px.EZA</span>') < h.indexOf('<span>trd.px.KSA</span>'), 'spadki: najmocniejszy pierwszy');
  assert.ok(h.includes('trd.k.coin{"k":143,"n":294}') && h.includes('<b>trd.b.concl</b>') && h.includes('trd.b.wk{"w":32}') && h.includes('trd.b.per{"a":"DT'.slice(0, 11)));
  assert.ok(h.includes('trd.ps.up_fade') && h.includes('trd.n.typ{"v":"2.6"}') && !h.includes('trd.n.pr23'), 'v96: ceny krypto — w widoku krypto');
  assert.ok(h.includes('id="trd-method"') && h.includes('trd.m.6') && h.includes('eng.disclaimer'));
  assert.equal(f.trdVerdict({ci: [52, 60]}), 'more'); assert.equal(f.trdVerdict({ci: [30, 45]}), 'less'); assert.equal(f.trdVerdict({}), 'coin');
  const html2 = el.innerHTML; f.trdApply(Object.assign({}, data)); assert.equal(el.innerHTML, html2, 'ten sam plik (at) — bez przebudowy');
  f.trdApply(null); assert.ok(f.TRD.data && el.innerHTML === html2, 'chwilowy błąd pobrania nie kasuje danych na ekranie');
  f.trdApply(Object.assign({}, data, {at: '2026-09-25T10:20:00Z', b: [{id: 'th', k: 5, n: 28, ci: [8, 35], from: '2025-09-15', to: '2026-08-17'}]}));
  assert.ok(el.innerHTML.includes('<b>trd.b.concl2</b>'), 'gdy kierunek częściej się odwracał — inny wniosek, nie wpisany na stałe');
  st.trdv = 'crypto'; f.renderTrendy(); const hc = el.innerHTML;   /* v96: widok „Trendy krypto” */
  assert.ok(hc.includes('trd.sn.exch.out_dir') && hc.includes('trd.n.pr23{"v":"−1.49%"}') && hc.includes('<span>trd.s.cm_btc</span>'), 'giełdy i ceny krypto w widoku krypto');
  assert.ok(!hc.includes('trd.s.jp_bd') && !hc.includes('trd.b.concl') && hc.includes('trd.b.nocr') && hc.includes('id="trd-method"'), 'bez krajów i bez wyników świata; opis metody w obu widokach');
});

test('v90: TRENDY — panel funduszy ETF w USA, stany „prawie nic”, wiersz na stronie Źródła', () => {
  const a = 'const EXTRA81=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(x0 > html.indexOf('for(const l in EXTRA80)') && html.includes('for(const l in EXTRA81)if(I18N[l])Object.assign(I18N[l],EXTRA81[l]);'));
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort());
  for (const m of ['', 'stock.', 'exch.', 'supply.', 'pos.']) for (const s of ['in_stop', 'out_stop']) assert.ok(D.pl[`trd.sn.${m}${s}`] && D.en[`trd.sn.${m}${s}`], `trd.sn.${m}${s}`);
  for (const g of ['us', 'tech', 'fin', 'energy', 'health', 'indu', 'cdisc', 'cstap', 'util', 'dev', 'eur', 'jpn', 'em', 'chn', 'india', 'bra', 'kor', 'twn',
                   'ustl', 'ustm', 'usts', 'agg', 'ig', 'hy', 'emb', 'gold', 'silver']) assert.ok(D.pl['trd.s.fe_' + g] && D.en['trd.s.fe_' + g], 'trd.s.fe_' + g);
  for (const k of ['trd.e.t', 'trd.e.sub', 'trd.src.fe', 'trd.b.fe', 'g.hs.fe']) assert.ok(D.pl[k] && D.en[k], k);
  assert.ok(D.pl['trd.m.6'].includes('fundusze rynków wschodzących tworzą jednostki rzadko'), 'dni z zerem w funduszach EM opisane jako pomiar');
  assert.ok(html.includes("trdPanel('e',F.filter(r=>r.g==='fe'))+") && html.indexOf("trdPanel('e'") < html.indexOf("trdPanel('f'"), 'panel funduszy przed krajami');
  assert.ok(html.includes("'in_down','in_stop','out_up'") && html.includes("['in_down','in_stop','out_down','out_stop'].includes(r.st)"));
  assert.ok(html.includes("fe:'fundusze ETF'") && html.includes("fe:()=>typeof TRD!=='undefined'&&TRD.data&&TRD.data.at"));
  const bad = /kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|warto kupi|okazj|prognozuj|rekomend|\btrwa(?![a-ząćęłńóśźż])|odbic|\bbuy\b|\bsell\b|forecast|recommend/i;
  for (const l of ['pl', 'en']) for (const k in D[l]) if (/^trd\.(sn|s|e)\b/.test(k)) assert.doesNotMatch(D[l][k], bad, `${l} ${k}`);
});

test('v91: GLOBAL — linie funduszy ETF w opisie regionu z pliku TRENDÓW; brak pliku = brak linii', () => {
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */');
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const f = new Function('$', 't', 'st', 'srvJSON', 'escH', 'etfCls', 'gAgeNote', 'fInt', 'sg', 'nfmt', 'fPct', 'zagSes', 'engDate', 'LANG', 'LOCALE', 'I18N',
    html.slice(b0, b1) + '\nreturn {TRD, feRegion};')(() => ({}), T, {mode: 'global'}, () => Promise.resolve(null), s => String(s), v => v > 0 ? 'pos' : v < 0 ? 'neg' : '',
    d => ' ·age', v => String(v), v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d = 0) => v.toFixed(d), (v, d) => v.toFixed(d) + '%', n => 'ses', s => s, 'pl', {pl: 'pl-PL'}, {pl: {}, en: {}});
  assert.equal(f.feRegion('usa'), '', 'bez pliku TRENDÓW — bez linii');
  f.TRD.data = {at: 'x', f: [{id: 'fe_jpn', g: 'fe', m: 'flow', sz: 5, cur: 'USD', date: '2026-09-24', st: 'mixed', w: -58.39}, {id: 'fe_kor', g: 'fe', m: 'flow', sz: 5, cur: 'USD', date: '2026-09-24', st: 'weird', w: 1}], p: []};
  const h = f.feRegion('jpn');
  assert.ok(h.startsWith('<div class="wide"><dt>fe.reg</dt>') && h.includes('trd.s.fe_jpn: <b class="neu">−58 trd.u.m USD</b>') && !h.includes('fe_kor'), h);
  assert.equal(f.feRegion('mea'), '', 'region bez funduszy — bez linii');
  assert.ok(html.includes("${typeof feRegion==='function'?feRegion(s.id):''}"));
  const a = 'const EXTRA82=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(D.pl['fe.reg'] && D.en['fe.reg']);
});

test('v92: surowce z CFTC w TRENDACH — nazwy, źródło, wiersz na stronie Źródła', () => {
  const a = 'const EXTRA83=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  for (const k of ['gold', 'silver', 'copper', 'wti']) assert.ok(D.pl['trd.s.cs_' + k] && D.en['trd.s.cs_' + k]);
  assert.ok(D.pl['trd.src.cs'] && D.pl['trd.p.sub'].includes('fundusze zarządzające') && D.en['g.hs.cs'].includes('open interest'));
  assert.ok(html.includes("cs:'surowce'") && html.includes("cs:'CFTC surowce'"));
});

test('v93: TRENDY — ceny jednostek funduszy (obligacje, metale, sektory) w panelu cen', () => {
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */');
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const el = {innerHTML: '', querySelectorAll() { return []; }, querySelector() { return null; }};
  const f = new Function('$', 't', 'st', 'srvJSON', 'escH', 'etfCls', 'gAgeNote', 'fInt', 'sg', 'nfmt', 'fPct', 'zagSes', 'engDate', 'LANG', 'LOCALE', 'I18N',
    html.slice(b0, b1) + '\nreturn {trdApply};')(() => el, T, {mode: 'trendy'}, () => Promise.resolve(null), s => String(s).replace(/</g, '&lt;'), v => v > 0 ? 'pos' : v < 0 ? 'neg' : '',
    d => '', v => String(v), v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d = 0) => v.toFixed(d), (v, d) => v.toFixed(d) + '%', n => 'ses', s => s, 'pl', {pl: 'pl-PL'}, {pl: {}, en: {}});
  f.trdApply({at: '2026-09-25T10:00:00Z', f: [], b: [], p: [{id: 'fp_gold', g: 'fp', sym: 'GLD', date: '2026-09-24', w: -1.2, pr: 4.1, typ: 1.8, st: 'up_fade'},
    {id: 'fp_bad', g: 'fp', sym: '<x>', date: '2026-09-24', w: 1, pr: 1, typ: 1, st: 'flat'}]});
  const h = el.innerHTML;
  assert.ok(h.includes('<h3 class="mtxt"><b>trd.x.fp</b></h3>') && h.includes('<span>trd.s.fe_gold</span>') && h.includes('trd.n.nav0{"s":"GLD"}') && h.includes('trd.n.typ{"v":"1.8"}'));
  assert.ok(!h.includes('fp_bad') && !h.includes('<x>'), 'dziwny symbol z pliku — pominięty');
  const a = 'const EXTRA84=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(D.pl['trd.x.fp'] && D.en['trd.n.nav'] && D.pl['trd.x.sub'].includes('State Street'));
});

test('v94: TRENDY po drugim przeglądzie — wynik funduszy ETF widoczny, źródło grupy, kafel „osłabł”, opis w katalogu źródeł', () => {
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */');
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const el = {innerHTML: '', querySelectorAll() { return []; }, querySelector() { return null; }};
  const f = new Function('$', 't', 'st', 'srvJSON', 'escH', 'etfCls', 'gAgeNote', 'fInt', 'sg', 'nfmt', 'fPct', 'zagSes', 'engDate', 'LANG', 'LOCALE', 'I18N',
    html.slice(b0, b1) + '\nreturn {trdApply};')(() => el, T, {mode: 'trendy'}, () => Promise.resolve(null), s => String(s), v => v > 0 ? 'pos' : v < 0 ? 'neg' : '',
    d => '', v => String(v), v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d = 0) => v.toFixed(d), (v, d) => v.toFixed(d) + '%', n => 'ses', s => s, 'pl', {pl: 'pl-PL'}, {pl: {}, en: {}});
  const row = o => Object.assign({g: 'fe', m: 'flow', sz: 5, cur: 'USD', date: '2026-09-24', age: 1, n: 8, lc: false, s: 1, sg: 1, x: false}, o);
  f.trdApply({at: '2026-09-25T10:00:00Z', p: [{id: 'fp_gold', g: 'fp', sym: 'GLD', date: '2026-09-24', w: -2, pr: 1, typ: 4, st: 'dn_new'}],
    f: [row({id: 'fe_tech', st: 'in_rev', w: 552.6, base: -173, d: 1.7, du: 725.7, iss: 'ssga'}), row({id: 'fe_gold', st: 'in_stop', w: -229.5, base: 1423, d: -1.5, du: -1652.8, iss: 'both'})],
    b: [{id: 'fe', k: 307, n: 536, weeks: 57, from: '2025-08-11', to: '2026-09-14', ci: [44.4, 69.3]}]});
  const h = el.innerHTML;
  assert.ok(h.includes('<span>trd.b.fe</span>') && h.includes('trd.b.wk{"w":57}'), 'wynik funduszy ETF pokazany, z liczbą tygodni');
  assert.ok(!h.includes('trd.src.') && !h.includes('trd.foot'), 'v96: bez linii źródła na kartach i bez stopki ze źródłami (wydawcy funduszy — znaczki, test v96-trendy)');
  assert.ok(h.includes('trd.k.fade</span></div><div class="k-val neu">−230 trd.u.m USD</div>') && h.includes('<span class="dlt chg">•</span><span class="ksrc" title="trd.sn.in_stop">'), 'kafel „osłabł” przy *_stop — v96: żółty (zmiana bez wyraźnego kierunku)');
  assert.ok(h.includes('trd.n.nav0{"s":"GLD"}'), 'złoto: bez wzmianki o dywidendzie');
  const a = 'const EXTRA85=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(D.pl['trd.x.sub'].includes('Obligacji tu nie ma') && D.pl['g.hs.fe'].includes('niekomercyjnym') && D.pl['trd.s.fe_util'].includes('USA'));
});

test('v95: TRENDY — „czy tydzień zapowiadał następny” dla dziennych przepływów krajów; opisy źródeł: co godzinę, historia wstecz', () => {
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */');
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const el = {innerHTML: '', querySelectorAll() { return []; }, querySelector() { return null; }};
  const f = new Function('$', 't', 'st', 'srvJSON', 'escH', 'etfCls', 'gAgeNote', 'fInt', 'sg', 'nfmt', 'fPct', 'zagSes', 'engDate', 'LANG', 'LOCALE', 'I18N',
    html.slice(b0, b1) + '\nreturn {trdApply};')(() => el, T, {mode: 'trendy'}, () => Promise.resolve(null), s => String(s), v => v > 0 ? 'pos' : v < 0 ? 'neg' : '',
    d => '', v => String(v), v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d = 0) => v.toFixed(d), (v, d) => v.toFixed(d) + '%', n => 'ses', s => s, 'pl', {pl: 'pl-PL'}, {pl: {}, en: {}});
  f.trdApply({at: '2026-09-25T10:00:00Z', f: [], p: [], b: [{id: 'ob', k: 40, n: 75, weeks: 26, from: '2026-03-30', to: '2026-09-14', ci: [41.2, 64.9]},
    {id: 'zz', k: 1, n: 2, weeks: 1, ci: [1, 99]}]});
  const h = el.innerHTML;
  assert.ok(h.includes('<span>trd.b.ob</span>') && h.includes('trd.b.wk{"w":26}') && h.includes('trd.b.pxnote') && h.includes('trd.b.v.coin'), h);
  assert.ok(!h.includes('trd.b.zz'), 'nieznany wynik z pliku — pominięty');
  const a = 'const EXTRA86=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(x0 > html.indexOf('for(const l in EXTRA85)') && html.includes('for(const l in EXTRA86)if(I18N[l])Object.assign(I18N[l],EXTRA86[l]);'));
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort());
  assert.ok(D.pl['trd.b.ob'].includes('Brazylia') && D.en['trd.b.ob'].includes('Brazil'));
  for (const k of ['g.hs.nsdl', 'g.hs.twse', 'g.hs.hkex']) assert.ok(D.pl[k].includes('co godzinę') && D.en[k].includes('every hour') && !D.pl[k].includes('co 3 h'), k);
  assert.ok(D.pl['g.hs.nsdl'].includes('suma dni zgadza się z sumą miesiąca'));
  assert.ok(D.pl['trd.b.concl3'].includes('Przepływy to nie ceny') && D.en['trd.b.concl3'].includes('Flows are not prices') && D.pl['trd.b.concl3'].includes('nie piszemy „kupuj”'));
  assert.ok(!('trd.b.concl2' in D.pl) && !D.pl['g.hs.hkex'].includes('trzyma'), 'v95.2: zwykły wniosek bez zmian; opis HKEX bez nieścisłości');
  f.trdApply({at: '2026-09-25T11:00:00Z', f: [], p: [], b: [{id: 'ob', k: 73, n: 112, weeks: 51, from: '2025-09-22', to: '2026-09-14', ci: [51.5, 76.8]}]});
  assert.ok(el.innerHTML.includes('trd.b.v.more') && el.innerHTML.includes('<b>trd.b.concl3</b>'), 'wynik przepływów ponad 50% — opis „częściej trwał” i zdanie „przepływy to nie ceny”');
  f.trdApply({at: '2026-09-25T12:00:00Z', f: [], p: [], b: [{id: 'px', k: 180, n: 290, weeks: 31, from: '2026-02-09', to: '2026-09-14', ci: [55.2, 67.4]}, {id: 'ob', k: 1, n: 2, weeks: 2, ci: [9.5, 90.5]}]});
  assert.ok(el.innerHTML.includes('<b>trd.b.concl2</b>') && !el.innerHTML.includes('trd.b.concl3'), 'wynik tylko dla cen — bez zdania o przepływach');
  f.trdApply({at: '2026-09-25T13:00:00Z', f: [], p: [], b: [{id: 'ob', k: 30, n: 112, weeks: 51, from: '2025-09-22', to: '2026-09-14', ci: [19.4, 35.6]}]});
  assert.ok(el.innerHTML.includes('trd.b.v.less') && el.innerHTML.includes('<b>trd.b.concl2</b>'), 'przepływy częściej się odwracały — zwykły wniosek');
});

test('v96: fundament — flagi, loga, waluty, znaczki wydawców (jedna funkcja na rodzaj ikony, zawsze jakaś ikona)', () => {
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('\nfunction fundIco(', h0);
  assert.ok(h0 > 0 && h1 > h0);
  const body = html.slice(h0, html.indexOf('\n', h1 + 1));
  const escH = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const F = new Function('escH', 'ISO32', 'COIN_LOGO', body + '\nreturn {flagCode,flagImg,flagsHtml,regFlags,ccyMark,coinImg,netImg,exchImg,issuerOf,issBadge,fundIco,FLAGS_OK};')(
    escH, {GRC: 'GR', DEU: 'DE', EMU: ''}, {PEPE: 'data:image/webp;base64,AAAA', BAD: 'https://zly.example/x.png'});
  assert.equal(F.flagCode('XM'), 'eu'); assert.equal(F.flagCode('EA'), 'eu'); assert.equal(F.flagCode('EL'), 'gr'); assert.equal(F.flagCode('GRC'), 'gr');
  assert.equal(F.flagCode('DEU'), 'de'); assert.equal(F.flagCode('PL'), 'pl'); assert.equal(F.flagCode('zz'), ''); assert.equal(F.flagCode('"><x'), '');
  assert.ok(F.flagImg('pl').includes('src="img/flagi/pl.svg"') && F.flagImg('zz') === '');
  const two = F.flagsHtml(['jp', 'kr']);
  assert.equal((two.match(/<img /g) || []).length, 2, 'dwa kraje = dwie flagi');
  assert.ok(F.flagsHtml(['id', 'sg', 'th', 'my', 'ph']).includes('<i class="more">+2</i>'), 'więcej niż 3 — „+N”');
  assert.ok(F.flagsHtml([]).includes('img/glify/globe.svg'), 'bez flagi — glob, nigdy pusto');
  assert.ok(F.regFlags('eur').includes('flagi/eu.svg') && F.regFlags('eur').includes('flagi/gb.svg') && F.regFlags('eur').includes('flagi/ch.svg'));
  assert.ok(F.ccyMark('EUR').includes('flagi/eu.svg') && F.ccyMark('EUR').includes('<i>€</i>') && F.ccyMark('USD').includes('flagi/us.svg'));
  assert.ok(F.ccyMark('XYZ').includes('glify/coin.svg'), 'nieznana waluta — glif monety');
  assert.ok(F.coinImg('BTC').includes('img/krypto/btc.svg') && F.coinImg('pepe').includes('data:image/webp;base64,AAAA'));
  assert.ok(F.coinImg('BAD').includes('class="iss') && !F.coinImg('BAD').includes('zly.example'), 'obcy adres obrazka nie przechodzi — znaczek z literami');
  assert.ok(F.coinImg('<b>').includes('&lt;B') && !F.coinImg('<b>').includes('<b>'), 'litery ze znaczka są escapowane');
  assert.ok(F.netImg('Hyperliquid L1').includes('sieci/hyper-evm.svg') && F.netImg('BSC').includes('binance-smart-chain') && F.netImg('Nowa Sieć').includes('class="iss'));
  assert.ok(F.exchImg('Binance (Futures)').includes('gieldy/binance.svg') && F.exchImg('Hyperliquid').includes('sieci/hyper-evm.svg') && F.exchImg('MEXC').includes('class="iss'));
  assert.equal(F.issuerOf('BTC', 'Grayscale Bitcoin Mini Trust'), 'grayscale', 'ticker BTC funduszu — wydawca z nazwy, nie logo monety');
  assert.equal(F.issuerOf('ARKB', 'ARK 21Shares Bitcoin ETF'), 'ark'); assert.equal(F.issuerOf('TETH', '21Shares Core Ethereum ETF'), 's21');
  assert.equal(F.issuerOf('IBIT', ''), 'ishares'); assert.equal(F.issuerOf('XLK', ''), 'ssga'); assert.equal(F.issuerOf('VGK', ''), 'vanguard');
  assert.ok(F.fundIco('IBIT', 'iShares Bitcoin Trust', 'BTC').includes('>iS</span>') && F.fundIco('IBIT', 'iShares Bitcoin Trust', 'BTC').includes('krypto/btc.svg'));
  assert.ok(F.fundIco('ZZZZ', '').includes('glify/etf.svg'), 'nieznany wydawca — glif ETF');
});

test('v96: Ustawienia bez pola kluczy, logo prowadzi do GLOBAL, ruchome tło w lewym pasku, kolory Apple', () => {
  assert.ok(!html.includes('id="set-data"') && !html.includes('id="soso-key"') && !html.includes('function etfInitSettings('), 'pole „Dane” z kluczami usunięte');
  assert.ok(html.includes("function keyGet(k){return '';}") && html.includes("Object.values(KEYS).concat(['cfai.td.cache']).forEach(k=>localStorage.removeItem(k))"), 'dawne klucze usuwane z przeglądarki');
  assert.ok(html.includes('etfLoad();etfAuto();engLoad();') && !html.includes('cgPing();engLoad'));
  assert.ok(html.includes('<a class="logo" id="logo-home" href="./" data-i18n-aria="nav.home">'));
  assert.ok(html.includes("$('#logo-home').addEventListener('click',e=>{if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey||e.button)return;e.preventDefault();page='overview';setMode('global');"));
  assert.ok(html.includes('.side{grid-row:1/3;grid-column:1;background:transparent;') && html.includes('.nav::before{content:"";position:absolute;z-index:-1;'), 'tło pod „Metodologia” widoczne');
  assert.ok(html.includes('  .nav::before{display:none}'), 'na telefonie pasek jest poziomy — panel jak dotąd');
  assert.ok(html.includes('--yl:#FFD60A;') && html.includes('--yl:#FFCC00;') && html.includes('--gr-tx:#248A3D; --rd-tx:#D70015;'), 'żółty Apple i czytelne odcienie w jasnym motywie');
  assert.ok(html.includes('.neu{--c:var(--yl);color:var(--yl-tx)}') && html.includes(".live.off{color:var(--yl-tx);"));
  const a = 'const EXTRA87=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort());
  assert.ok(D.pl['nav.home'] && !D.pl['etf.src.snap'].includes('Ustawienia') && !D.pl['pg.nosrc.d'].includes('Ustawieniach') && !D.pl['g.hs.fh'].includes('własnego klucza'));
});

// ===== v96 — obszar global_map: mapa GLOBAL, kafelki, szczegóły regionu, „Gdzie warunki sprzyjają”, karty jakości =====
const gm96 = (() => {
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('\nfunction fundIco(', h0);
  const body = html.slice(h0, html.indexOf('\n', h1 + 1));
  const escH = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  const ISO32 = {USA: 'US', DEU: 'DE', FRA: 'FR', GBR: 'GB', SAU: 'SA', TUR: 'TR', ISR: 'IL', JPN: 'JP', KOR: 'KR', RUS: 'RU'};
  const H = new Function('escH', 'ISO32', 'COIN_LOGO', body + '\nreturn {flagCode,flagImg,flagsHtml,regFlags,ccyMark,coinImg,fundIco,glyphImg,icoWrap,REGF};')(escH, ISO32, {});
  const x0 = html.indexOf('const EXTRA88='), D = JSON.parse(html.slice(x0 + 'const EXTRA88='.length, html.indexOf(';\n', x0)));
  return {H, escH, D};
})();
const GM_PROV = /OECD|\bBIS\b|\bEBC\b|\bECB\b|Bank Światowy|World Bank|Finnhub|Twelve Data|CoinGecko|CoinPaprika|CoinMarketCap|DefiLlama|\bTIC\b|\bMOF\b|Skarb USA|US Treasury|Bundesbank|Frankfurter/;

test('v98: mapa świata bez zmian (decyzja właściciela 25.09) — flagi i loga tylko w opisach, kafelkach i tabelach', () => {
  assert.ok(html.includes('const GFLAG={') && html.includes('function gFlagOn(c,id,x,y,r){') && html.includes('const GSIL={') && html.includes('function gSil(c,x,y,rad,id){'), 'dawne flagi i sylwetki na mapie');
  assert.ok(html.includes('if(!gFlagOn(g2,r.id,n.x,n.y,rr*.93)){') && html.includes('tint=v[2]?(up?PAL.gr:PAL.rd):PAL.bl'), 'węzły mapy rysowane jak wcześniej');
  assert.ok(!html.includes('function gFlagsOn(') && !html.includes('function gFlagBmp('), 'bez nowego rysowania flag na mapie');
  assert.ok(html.includes("vl=gst.label==='name'?'':(v[2]?gpct(v[1]):t('g.nodata'))"), 'podpisy na mapie jak wcześniej');
});

test('v96-global_map: kafelki GLOBAL — ikona na każdym kafelku, bez nazw dostawców, zmiana: wzrost/spadek/zero', () => {
  const a0 = html.indexOf('\nfunction gRenderKpi(){'), a1 = html.indexOf('\nfunction gNameL(', a0);
  const H = gm96.H, el = {innerHTML: ''};
  const run = (GKPI, h) => { new Function('$', 'GKPI', 't', 'gfmt', 'LOCALE', 'LANG', 'gst', 'gAgeNote', 'escH', 'flagImg', 'glyphImg', 'coinImg', 'icoWrap', html.slice(a0, a1) + '\nreturn gRenderKpi;')(
    () => el, GKPI, (k, o) => k + (o ? JSON.stringify(o) : ''), v => 'F' + v, {pl: 'pl-PL'}, 'pl', {period: '1M'}, d => ' · age(' + d + ')', gm96.escH,
    h ? H.flagImg : undefined, h ? H.glyphImg : undefined, h ? H.coinImg : undefined, h ? H.icoWrap : undefined)(); return el.innerHTML; };
  const K = [
    {k: 'g.k.eq', v: 1000, u: 'u.b', d: 1.25, cov: [11, 12], src: 'Finnhub · ETF', fresh: '2026-09-24'},
    {k: 'g.k.dxy', v: 98.5, u: '', dec: 2, d: -0.4, src: 'ECB', fresh: '2026-09-24'},
    {k: 'g.k.us10', v: 4.1, u: 'u.pp0', dec: 2, d: 0, dpp: 1, src: 'US Treasury', fresh: '2026-09-24'},
    {k: 'g.k.de10', v: 2.6, u: 'u.pp0', dec: 2, d: 0.003, dpp: 1, src: 'Bundesbank', fresh: '2026-09-23'},
    {k: 'g.k.cry', v: 2887, u: 'u.b', d: null, d24: 1, src: 'CoinMarketCap', fresh: '2026-09-25'},
    {k: 'g.k.stab', v: null, u: 'u.b', d: null, src: 'DefiLlama', fresh: ''}];
  const h = run(K, true);
  assert.ok(!GM_PROV.test(h), 'pod kafelkami nie ma nazw dostawców: ' + (h.match(GM_PROV) || [])[0]);
  const tiles = h.split('<div class="panel kpi">').slice(1);
  assert.equal(tiles.length, 6);
  tiles.forEach((x, i) => assert.ok(/<div class="k-head"><span class="icos">.+?<\/span><span>g\.k\./.test(x), 'kafelek ' + i + ' ma ikonę przed nazwą'));
  assert.ok(tiles[0].includes('img/glify/globe.svg') && tiles[1].includes('flagi/us.svg') && !tiles[1].includes('ksym'));   // v98.2: DXY — sama flaga USA (podpis w jednej linii)
  assert.ok(tiles[2].includes('flagi/us.svg') && tiles[3].includes('flagi/de.svg'));
  assert.ok(tiles[4].includes('krypto/btc.svg') && tiles[4].includes('krypto/eth.svg') && tiles[5].includes('krypto/usdt.svg') && tiles[5].includes('krypto/usdc.svg'));
  assert.ok(tiles[0].includes('class="dlt up">▲ +') && tiles[1].includes('class="dlt dn">▼ −'), 'wzrost zielony, spadek czerwony');
  assert.ok(tiles[2].includes('class="dlt zero">• ') && !/dlt (up|dn)/.test(tiles[2]) && tiles[3].includes('class="dlt zero">'), 'zero (i poniżej 0,005) — neutralnie, nie „brak porównania”');
  assert.ok(tiles[4].includes('class="dlt na">kpi.nodelta') && tiles[5].includes('<div class="k-val">—</div>'), 'brak to brak, nie zero');
  assert.ok(tiles[0].includes('<span class="ksrc">g.cov.of{"n":11,"m":12} · 2026-09-24 · age(2026-09-24)</span>'), 'zostają pokrycie, data i wiek');
  assert.ok(tiles[5].includes('<span class="ksrc"></span>'));
  assert.ok(!run(K, false).includes('class="icos"'), 'bez pomocników ikon — sam tekst, bez błędu');
});

test('v96-global_map: szczegóły regionu — flagi krajów i regionów, waluty ze znakiem, bez wierszy „Źródło”', () => {
  const d0 = html.indexOf('/* v53: okno czasu i źródło bazy'), d1 = html.indexOf('function gRenderQ(){', d0);
  const H = gm96.H, T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const BI = {data: {asof: '2026-Q1', no_reporter: [], flows: {'usa>eur': [['2026-Q1', 67331.6, 8]]}}};
  const GDATA = {'1Q': {cry: 1, fxw: {mea: {a: '2026-08', b: '2026-05', k: 'm', out: [['ISR', 'nofx', 'ILS']]}}}};
  const GLIVE = {oecd: {TUR: [['2026-08', 1]], ISR: [['2026-08', 2]]}, fiat: {cur: {usa: {USD: 1}, eur: {EUR: 1, GBP: 1, '<b>': 1}}, byCur: {USD: 5, EUR: 3, GBP: 1}}};
  const GB_ = {usa: {iso: ['USA']}, eur: {iso: ['DEU']}, mea: {iso: ['SAU', 'TUR', 'ISR']}};
  const f = new Function('t', 'escH', 'GDATA', 'gst', 'BI', 'GB_', 'GLIVE', 'gFrozen', 'gFrozenN', 'instSign', 'instMld', 'bopMld', 'biRow', 'biV', 'bopSum', 'instFoot', 'TIC', 'INST',
    'flagImg', 'regFlags', 'ccyMark', 'coinImg', 'icoWrap', 'fundIco', 'bilCty', 'gfmt', 'GCEDGE', 'LOCALE', 'LANG', 'I18N', 'GPROB',
    html.slice(d0, d1) + '\nreturn {gWinRow, gBaseRow, biEdgeRow, msRegion, gFiatBox, gProbBox, gmCty, gmTone, gmAmt, gmFund, gmCodes};')(
    T, gm96.escH, GDATA, {period: '1Q'}, BI, GB_, GLIVE, () => false, () => 1, v => v > 0 ? '+' : (v < 0 ? '−' : ''), v => (v / 1000).toFixed(1), v => (v / 1000).toFixed(1),
    (rows, back) => rows[rows.length - 1 - back], r => r ? r[1] : null, (rows, n) => rows.slice(-n).reduce((a, r) => a + r[1], 0), s => s,
    {data: {world: {in: [['2026-07', 40616, 1]], out: [['2026-07', 68522, 1]]}}}, {data: null},
    H.flagImg, H.regFlags, H.ccyMark, H.coinImg, H.icoWrap, H.fundIco, c => ({DEU: 'Niemcy', SAU: 'Arabia Saudyjska'})[c] || c, v => 'F' + v,
    [{f: 'usa', sh: .6, a: 12}, {f: 'eur', sh: .4, a: 0}], {pl: 'pl-PL'}, 'pl', {en: {'gmap.pf.cli.lvl': 'x'}},
    [{id: 'usa', score: 0, parts: [['cli.lvl', 0, '0'], ['fx', -2, '−2']]}]);
  const w = f.gWinRow('mea');
  assert.ok(w.includes('g.win.miss{"c":"<img class=\\"ico sm gf\\" src=\\"img/flagi/sa.svg\\"'), 'kraj bez indeksu — z flagą: ' + w);
  assert.ok(w.includes('flagi/il.svg') && w.includes('flagi/il.svg\\" alt=\\"\\" title=\\"IL\\"') && w.includes('<span class=\\"ccy\\">'), 'waluta z flagą i znakiem');
  const b = f.gBaseRow('eur');
  assert.ok(['fr', 'gb', 'it', 'nl', 'se'].every(c => b.includes('flagi/' + c + '.svg')) && b.includes('FR 2018') && b.includes('SE 2003'), 'rok bazy przy każdym kraju z flagą');
  assert.ok(f.gBaseRow('asean').includes('flagi/vn.svg') && f.gBaseRow('mea').includes('flagi/ae.svg') && f.gBaseRow('mea').includes('flagi/il.svg'));
  const e = f.biEdgeRow('usa', 'eur');
  assert.ok(e.includes('flagi/us.svg') && e.includes('flagi/eu.svg') && e.includes('flagi/gb.svg'), 'korytarz BIS — flagi obu regionów');
  const m = f.msRegion('usa');
  assert.ok(m.includes('<dd><img class="ico sm gf" src="img/flagi/us.svg"') && m.includes('ms.usa{'), 'zmierzone przepływy USA z flagą');
  assert.equal(f.msRegion('chn'), '');
  const cty = f.gmCty('DEU');
  assert.ok(cty.includes('flagi/de.svg') && cty.includes('>Niemcy</span>') && cty.includes('title="DEU"'), 'kraj: flaga i nazwa');
  assert.ok(f.gmCty('XXX').includes('>XXX</span>') && !f.gmCty('XXX').includes('<img'), 'nieznany kod — sam kod, bez obcego obrazka');
  assert.deepEqual([f.gmTone(2), f.gmTone(-1), f.gmTone(0), f.gmTone(null)], ['pos', 'neg', '', '']);
  assert.equal(f.gmAmt(0), '<span>F0</span>', 'zero — bez znaku i koloru');
  assert.equal(f.gmAmt(-5), '<span class="neg">−F5</span>');
  assert.ok(f.gmFund('EWJ').includes('>iS</span>') && f.gmFund('<x>').includes('&lt;x&gt;'), 'fundusz: znaczek wydawcy, ticker escapowany');
  const fb = f.gFiatBox();
  assert.ok(fb.includes('class="pbox gfiat"') && fb.includes('flagi/us.svg') && fb.includes('<i>€</i>') && fb.includes('<i>£</i>'), 'waluty z flagą i znakiem');
  assert.ok(fb.includes('&lt;B&gt;') && !fb.includes('<b>'), 'kody walut z danych są escapowane');
  assert.ok(fb.includes('<span class="cell mono pos">+F12</span>') && fb.includes('<span class="cell mono">F0</span>'), 'napływ zielony, zero neutralne');
  const pb = f.gProbBox('usa');
  assert.ok(pb.includes('<h4>g.pr.t · 0</h4>') && pb.includes('<li><span>gmap.pf.cli.lvl</span><b class="">0</b></li>') && pb.includes('<b class="neg">−2</b>'));
  // gRenderDetail: flagi w nagłówkach, bez wierszy „Źródło”
  const r0 = html.indexOf('function gRenderDetail(){'), r1 = html.indexOf('/* v53: okno czasu', r0), R = html.slice(r0, r1);
  assert.ok(R.includes('<h3>${gmRf(s.id,\'\')}${gNameL(s.id)}</h3>') && R.includes('r.iso.map(gmCty)'), 'region: flagi przed nazwą, kraje z flagami');
  assert.ok(R.includes('<h3>${gmRf(e.f,\'\')}${t(\'g.n.\'+e.f)} → ${gmRf(e.t,\'\')}${t(\'g.n.\'+e.t)}</h3>'), 'korytarz: flagi po obu stronach');
  assert.ok(R.includes("t('gmap.cf.edge',{r:gmRf(e.f,'')+t('g.n.'+e.f),c:CRY()})") && R.includes("gmCoins(['BTC','ETH'])"), 'krypto: loga monet');
  assert.ok(!R.includes("t('d.source')") && !GM_PROV.test(R.replace(/\/\*[\s\S]*?\*\//g, '')), 'bez wierszy „Źródło” i nazw dostawców');
  assert.ok(R.includes('<b class="${gmTone(dy.dp)}">') && R.includes('${gmRf(s.id)}${(Array.isArray(dy.syms)?dy.syms:[]).map(gmFund)'), 'dzisiejsza sesja: kolor wg znaku, flagi regionu (v98.2), fundusze ze znaczkiem');
});

test('v96-global_map: „Gdzie warunki sprzyjają” z flagami; karty jakości bez karty „Źródła”; słownik bez nazw dostawców', () => {
  const d0 = html.indexOf('/* v53: okno czasu i źródło bazy'), d1 = html.indexOf('function gRenderRefresh(){', d0);
  const els = {}, $ = s => els[s] || (els[s] = {innerHTML: ''});
  const PL = Object.assign({}, gm96.D.pl), T = (k, o) => { let s = PL[k] !== undefined ? PL[k] : k; if (o) for (const v in o) s = s.split('{' + v + '}').join(o[v]); return s; };
  const GREG = [{id: 'usa'}, {id: 'jpn'}, {id: 'eur'}];
  const f = new Function('t', 'escH', '$', '$$', 'GDATA', 'gst', 'GLIVE', 'GREG', 'GLINK', 'GPROB', 'I18N', 'gAgeNote', 'flagImg', 'regFlags', 'st', 'gRenderDetail', 'gDirty',
    html.slice(d0, d1) + '\nreturn {gRenderProb, gRenderQ};')(
    T, gm96.escH, $, () => [], {'1M': {usa: [1, 1, 1], jpn: [0, 0, 0], eur: [-1, -1, 1]}}, {period: '1M'}, {asof: '2026-08', src: {}}, GREG, true,
    [{id: 'usa', score: 40, parts: [['cli.lvl', 0, '0'], ['fx', 2, '+2']]}, {id: 'jpn', score: -12, parts: [['mom1', -3, '−3']]}], {en: gm96.D.en}, d => ' · age(' + d + ')',
    gm96.H.flagImg, gm96.H.regFlags, {anim: false}, () => {}, () => {});
  f.gRenderProb();
  const p = els['#g-prob'].innerHTML;
  assert.ok(/<span class="pname"><span class="icos"><img class="ico sm" src="img\/flagi\/us\.svg"[^>]*><\/span><span>g\.n\.usa<\/span><\/span>/.test(p), 'flaga przed nazwą regionu');
  assert.ok(p.includes('flagi/jp.svg') && p.includes('flagi/kr.svg'), 'Japonia i Korea — dwie flagi');
  assert.ok(p.includes('<button class="prow pos" data-r="usa">') && p.includes('<button class="prow neg" data-r="jpn">'));
  assert.ok(p.includes('class="pchip z"') && p.includes('class="pchip p"') && p.includes('class="pchip n"'), 'składnik równy zero — neutralnie');
  assert.ok(p.includes('title="' + gm96.D.pl['gmap.pf.cli.lvl'] + '"') && !GM_PROV.test(p), 'podpowiedzi bez nazw instytucji');
  f.gRenderQ();
  const q = els['#g-q'].innerHTML;
  assert.equal((q.match(/<div class="panel q">/g) || []).length, 5, 'pięć kart: świeżość, pokrycie, metoda, korytarze, ograniczenia');
  assert.ok(!q.includes('g.q.src') && !GM_PROV.test(q), 'bez karty „Źródła” i bez nazw dostawców');
  assert.ok(q.includes('2026-08 · age(2026-08)') && q.includes('2 / 3') && q.includes(gm96.D.pl['gmap.q.corrv1']));
  // słownik EXTRA88: pełny angielski, bez nazw dostawców w tekstach dla czytelnika
  assert.deepEqual(Object.keys(gm96.D.pl).sort(), Object.keys(gm96.D.en).sort());
  for (const l of Object.keys(gm96.D)) for (const [k, v] of Object.entries(gm96.D[l])) {
    assert.ok(!GM_PROV.test(v) && !/\b(IWF|BIZ|FMI|BRI|BPI|МВФ|IMF)\b/.test(v), l + ' ' + k + ': ' + v);
    assert.ok(gm96.D.en[k] !== undefined, l + ' ' + k + ': klucz także po angielsku');
  }
  // po przeglądzie: klucze, które wcześniej miały tłumaczenia (korytarz, ograniczenia), mają je nadal — bez nazw instytucji
  for (const l of ['de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) for (const k of ['gmap.plain.edge', 'gmap.plain.edge0', 'gmap.q.limd']) {
    assert.ok(gm96.D[l] && gm96.D[l][k] && gm96.D[l][k] !== gm96.D.en[k], l + ' ' + k);
    for (const ph of ['{p}', '{a}', '{b}', '{v}']) if (gm96.D.en[k].includes(ph)) assert.ok(gm96.D[l][k].includes(ph), l + ' ' + k + ' ' + ph);
  }
  // kafelki: w danych zostaje src (testy v63/v66), ale nie jest pokazywane
  const k0 = html.indexOf('\nfunction gRenderKpi(){'), k1 = html.indexOf('\nfunction gNameL(', k0);
  assert.ok(!html.slice(k0, k1).includes('k.src'), 'nazwa dostawcy nie trafia pod kafelek');
});

test('v96-global_map: gRenderDetail uruchomiony — węzeł krypto, regiony, krawędź krypto i korytarz: flagi, loga, zero bez „+”, odpływ nazwany odpływem, bez „Źródło”', () => {
  const r0 = html.indexOf('\nfunction gNameL('), r1 = html.indexOf('function gRenderQ(){', r0);
  const n0 = html.indexOf('const gfmt=v=>{'), n1 = html.indexOf('\n', html.indexOf('\nconst gpct=', n0) + 1);
  const g0 = html.indexOf('const GREG=['), g1 = html.indexOf('\n];', g0) + 3;
  assert.ok(r0 > 0 && r1 > r0 && n0 > 0 && n1 > n0 && g0 > 0 && g1 > g0);
  const PL = gm96.D.pl, T = (k, o) => { if (PL[k] === undefined) return k + (o ? JSON.stringify(o) : ''); let s = PL[k]; if (o) for (const v in o) s = s.split('{' + v + '}').join(o[v]); return s; };
  const NF = new Function('t', 'LOCALE', 'LANG', html.slice(n0, n1) + '\nreturn {gfmt, gpct};')(T, {pl: 'pl-PL'}, 'pl');
  const GREG = new Function(html.slice(g0, g1) + '\nreturn GREG;')(), GB_ = Object.fromEntries(GREG.map(r => [r.id, r]));
  const H = gm96.H, els = {}, $ = q => els[q] || (els[q] = {innerHTML: '', hidden: false, addEventListener() {}});
  const GDATA = {'1M': {cry: 1, crypto: [-3.2, -1, 1], usa: [0, 0, 1], jpn: [-5, -1.234, 1], eur: [12, 0.8, 1], can: [0, 0, 0], lat: [4, 1, 1]}};
  const GLIVE = {day: {usa: {dp: 0, syms: ['SPY']}, jpn: {dp: -0.5, syms: ['EWJ', '<x>']}}, dayAt: '<b>x</b>', fiat: {cur: {usa: {USD: 1}, eur: {EUR: 1, GBP: 1}}, byCur: {USD: 5, EUR: 2, GBP: 1}}};
  const GCEDGE = [{id: 'usa>crypto', f: 'usa', sh: .6, a: 2.5}, {id: 'eur>crypto', f: 'eur', sh: .3, a: -2}, {id: 'jpn>crypto', f: 'jpn', sh: .1, a: 0}];
  const GPROB = [{id: 'jpn', score: -12, parts: [['mom1', -3, NF.gpct(-3)], ['fx', 0, NF.gpct(0)]]}];
  const names = ['t', 'I18N', 'LANG', 'LOCALE', '$', 'gst', 'GDATA', 'GB_', 'GLIVE', 'gStabDelta', 'ETF', 'etfTotals', 'etfCls', 'etfM', 'etfA', 'gCenyRow', 'spRegion', 'eerRegion', 'zagRegion',
    'GCENY_N', 'GLINK', 'GCEDGE', 'GEDGE', 'GPROB', 'gDirty', 'gfmt', 'gpct', 'escH', 'flagImg', 'regFlags', 'ccyMark', 'coinImg', 'icoWrap', 'fundIco', 'bilCty',
    'gFrozen', 'gFrozenN', 'BI', 'TIC', 'INST', 'instSign', 'instMld', 'instFoot', 'bopMld', 'biRow', 'biV', 'bopSum'];
  const gst = {period: '1M', sel: null};
  const mk = link => new Function(...names, html.slice(r0, r1) + '\nreturn {gRenderDetail, gmPct, gmSh};')(
    T, {en: gm96.D.en, pl: PL}, 'pl', {pl: 'pl-PL'}, $, gst, GDATA, GB_, GLIVE, () => null, {data: {}}, () => ({m: 1.5, d1: 0, aum: 100}), v => v > 0 ? 'pos' : v < 0 ? 'neg' : '', String, String,
    () => '', () => '', () => '', () => '', {'1M': 12}, link, GCEDGE, [{id: 'can>lat', f: 'can', t: 'lat', a: 4}], GPROB, () => {}, NF.gfmt, NF.gpct, gm96.escH,
    H.flagImg, H.regFlags, H.ccyMark, H.coinImg, H.icoWrap, H.fundIco, c => ({USA: 'Stany Zjednoczone', JPN: 'Japonia', KOR: 'Korea Południowa'})[c] || c,
    () => false, () => 1, {data: {no_reporter: [], flows: {}}}, {data: null}, {data: null}, v => v > 0 ? '+' : v < 0 ? '−' : '', v => String(v), s => s, v => String(v), () => null, () => null, () => null);
  const f = mk(false), fL = mk(true);
  const Z = NF.gpct(0), Z0 = Z.replace(/^[+−]/, '');   // „+0,00%” → „0,00%”
  const run = (sel, g) => { gst.sel = sel; (g || f).gRenderDetail(); return els['#g-detail'].innerHTML; };
  const clean = (h, id) => { assert.ok(!GM_PROV.test(h) && !h.includes('d.source') && !h.includes('g.src.') && !h.includes('Źródło'), id + ': bez źródeł: ' + (h.match(GM_PROV) || [])[0]); };
  // węzeł krypto
  const c = run({type: 'node', id: 'crypto'}); clean(c, 'crypto');
  assert.ok(/<h3><span class="icos"><img[^>]*krypto\/btc\.svg[^>]*><img[^>]*krypto\/eth\.svg[^>]*><\/span>g\.n\.crypto<\/h3>/.test(c), 'krypto: loga BTC i ETH przed nazwą');
  assert.ok(c.includes('<div class="d-val"><span class="neg">−') && c.includes('krypto/usdt.svg') && c.includes('krypto/usdc.svg'), 'spadek podaży czerwony; stablecoiny z logami');
  assert.ok(c.includes('<b class="pos">1.5</b>') && c.includes('<b class="">0</b>') && c.includes('class="pbox gfiat"') && c.includes('flagi/us.svg') && c.includes('<i>€</i>'));
  // region: dokładne zero — „nie zmieniła się”, bez „+0,00%”, bez koloru
  const u = run({type: 'node', id: 'usa'}); clean(u, 'usa');
  assert.ok(u.includes('<h3><span class="icos"><img class="ico" src="img/flagi/us.svg"') && u.includes('>Stany Zjednoczone</span>'), 'USA: flaga w nagłówku i przy kraju');
  assert.ok(u.includes('<div class="d-val"><span>' + NF.gfmt(0) + '</span>'), 'zero: bez znaku i koloru');
  assert.ok(u.includes(T('gmap.plain.zero', {n: 'g.n.usa', p: 'g.per.1M'})) && !u.includes('g.plain.in'), 'zero nie jest opisane jako wzrost');
  assert.ok(!u.includes(Z) && u.includes('<span class="">' + Z0 + '</span>') && u.includes('<b class="">' + Z0 + '</b>'), 'zmiana w % i dzisiejsza sesja: zero bez „+”');
  assert.ok(u.includes('>SP</span>') && u.includes('SPY'), 'fundusz sesji ze znaczkiem wydawcy');
  // region: spadek; Japonia i Korea — dwie flagi; dane escapowane
  const j = run({type: 'node', id: 'jpn'}); clean(j, 'jpn');
  assert.ok(j.includes('flagi/jp.svg') && j.includes('flagi/kr.svg') && j.includes('>Korea Południowa</span>'));
  assert.ok(j.includes('<div class="d-val"><span class="neg">−') && j.includes('g.plain.out{') && j.includes('<span class="neg">' + NF.gpct(-1.234) + '</span>') && j.includes('<b class="neg">' + NF.gpct(-0.5) + '</b>'));
  assert.ok(j.includes('&lt;x&gt;') && j.includes('&lt;b&gt;x&lt;/b&gt;') && !j.includes('<x>') && !j.includes('<b>x</b>'), 'ticker i data z danych escapowane');
  assert.ok(j.includes('<b class="">' + Z0 + '</b>') && j.includes('<b class="neg">' + NF.gpct(-3) + '</b>'), 'składnik rankingu równy zero — bez „+”');
  // region bez danych — brak, nie zero
  const n = run({type: 'node', id: 'can'});
  assert.ok(n.includes('<div class="d-val">—<small>') && n.includes('g.plain.none{') && n.includes('<dd>—</dd>') && n.includes('flagi/ca.svg'));
  // Europa: trzy flagi w nagłówku, lista krajów szeroka
  const e = run({type: 'node', id: 'eur'}); clean(e, 'eur');
  assert.ok(['eu', 'gb', 'ch'].every(x => e.includes('flagi/' + x + '.svg')) && e.includes('<div class="wide"><dt>g.d.cty</dt><dd class="gctys">') && (e.match(/class="gcty"/g) || []).length === 9);
  // krawędź krypto: napływ / odpływ / zero
  const cu = run({type: 'edge', id: 'usa>crypto'}); clean(cu, 'usa>crypto');
  assert.ok(/<h3><span class="icos"><img[^>]*flagi\/us\.svg[^>]*><\/span>g\.n\.usa → <span class="icos"><img[^>]*btc\.svg/.test(cu), 'region → krypto: flaga i loga');
  assert.ok(cu.includes('<span class="pos">+') && cu.includes('g.cf.edged{') && cu.includes('g.plain.cf{'));
  const ce = run({type: 'edge', id: 'eur>crypto'}); clean(ce, 'eur>crypto');
  assert.ok(ce.includes('<span class="neg">−') && ce.includes(T('gmap.cf.edged.out', {s: '30%'})) && ce.includes(PL['gmap.plain.cf.out'].split('{')[0]) && !ce.includes('g.cf.edged{') && !ce.includes('g.plain.cf{'), 'ujemna kwota opisana jako odpływ: ' + ce.slice(0, 600));
  const cz = run({type: 'edge', id: 'jpn>crypto'});
  assert.ok(cz.includes('<div class="d-val"><span>' + NF.gfmt(0) + '</span>') && cz.includes(T('gmap.cf.edged.0', {s: '10%'})));
  // korytarz: flagi po obu stronach; opis zależny od powiązań bankowych
  const k = run({type: 'edge', id: 'can>lat'}); clean(k, 'can>lat');
  assert.ok(/<h3><span class="icos"><img[^>]*flagi\/ca\.svg[^>]*><\/span>g\.n\.can → <span class="icos">(<img[^>]*>){3}<i class="more">\+1<\/i><\/span>g\.n\.lat<\/h3>/.test(k), 'korytarz: flagi po obu stronach: ' + k.slice(0, 400));
  assert.ok(k.includes(PL['gmap.plain.edge0'].split('{')[0]) && k.includes('<dd>g.m.corr</dd>') && k.includes('banki z regionu <span class="icos">'), 'bez powiązań: podział proporcjonalny');
  const kl = run({type: 'edge', id: 'can>lat'}, fL);
  assert.ok(kl.includes(T('gmap.m.corrbis')) && kl.includes(T('gmap.plain.edge', {a: 'g.n.can', b: 'g.n.lat', v: NF.gfmt(4), p: 'g.per.1M'})));
  // nieznany wybór — panel się chowa, bez błędu
  gst.sel = {type: 'edge', id: 'xx>crypto'}; f.gRenderDetail(); assert.equal(els['#g-why'].hidden, true);
  // pomocniki: procent i składnik rankingu
  assert.deepEqual([f.gmPct(0), f.gmPct(-0), f.gmPct(1.5), f.gmPct(-2)], [Z0, Z0, NF.gpct(1.5), NF.gpct(-2)]);
  assert.deepEqual([f.gmSh('+0,00 pp', 0), f.gmSh('+2', 2), f.gmSh('−1', -1)], ['0,00 pp', '+2', '−1']);
  // kafelki: brak części pomocników ikon (np. tylko flagImg i icoWrap) — bez błędu, bez ikon
  const a0 = html.indexOf('\nfunction gRenderKpi(){'), a1 = html.indexOf('\nfunction gNameL(', a0), el = {innerHTML: ''};
  new Function('$', 'GKPI', 't', 'gfmt', 'LOCALE', 'LANG', 'gst', 'gAgeNote', 'escH', 'flagImg', 'icoWrap', html.slice(a0, a1) + '\nreturn gRenderKpi;')(
    () => el, [{k: 'g.k.cry', v: 1, u: 'u.b', d: 1}, {k: 'g.k.eq', v: 1, u: 'u.b', d: -1}], T, NF.gfmt, {pl: 'pl-PL'}, 'pl', {period: '1M'}, () => '', gm96.escH, H.flagImg, H.icoWrap)();
  assert.ok(el.innerHTML.includes('<div class="k-head"><span>g.k.cry</span>') && !el.innerHTML.includes('class="icos"'));
});

// v96-global_tables: flagi, waluty i kolory w tabelach GLOBAL; źródła tylko na stronie Źródła
const gtEsc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const gtT = (k, v) => k + (v ? JSON.stringify(v) : '');
const gtEnv = (() => {
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('\nfunction fundIco(', h0);
  const g0 = html.indexOf('/* v96-gt: ikony w tabelach GLOBAL — początek'), g1 = html.indexOf('/* v96-gt: ikony w tabelach GLOBAL — koniec */', g0);
  const i0 = html.indexOf('const ISO32='), i1 = html.indexOf('\n', i0);
  assert.ok(h0 > 0 && h1 > h0 && g0 > 0 && g1 > g0 && i0 > 0, 'bloki ikon');
  return new Function('escH', 'COIN_LOGO', html.slice(i0, i1) + '\n' + html.slice(h0, html.indexOf('\n', h1 + 1)) + '\n' + html.slice(g0, g1) + '\nreturn {gtI, gtNm, gtTone, gtZero, gtEngClean};')(gtEsc, {});
})();
const gtFlag = c => `src="img/flagi/${c}.svg"`;

test('v96-global_tables: gtI — flagi (ISO2, ISO3, strefa euro), regiony, nazwy krajów, waluty, rynki; zawsze jakaś ikona', () => {
  const I = gtEnv.gtI;
  assert.ok(I('f', 'CHN').includes(gtFlag('cn')) && I('f', 'US').includes(gtFlag('us')) && I('f', 'EA').includes(gtFlag('eu')) && I('f', 'XM').includes(gtFlag('eu')));
  assert.ok(I('f', 'ZZZ').includes('img/glify/globe.svg'), 'nieznany kod — glob, nigdy pusto');
  const jk = I('r', 'jpn'); assert.ok(jk.includes(gtFlag('jp')) && jk.includes(gtFlag('kr')), 'Japonia i Korea — dwie flagi');
  assert.ok(I('f', ['ky', 'bs', 'bm']).includes(gtFlag('bm')), 'Karaiby — trzy flagi');
  // nazwy z pliku TIC (tabela 5) i MF (kraje) — prawdziwe wiersze z 25.09.2026
  const names = { 'Japan': 'jp', 'United Kingdom': 'gb', 'China, Mainland': 'cn', 'Belgium': 'be', 'Cayman Islands': 'ky', 'Luxembourg': 'lu', 'Canada': 'ca', 'Ireland': 'ie',
    'France': 'fr', 'Taiwan': 'tw', 'Switzerland': 'ch', 'Singapore': 'sg', 'Hong Kong': 'hk', 'Norway': 'no', 'India': 'in', 'Korea, South': 'kr', 'Saudi Arabia': 'sa',
    'United Arab Emirates': 'ae', 'Turkey': 'tr', 'Memo: European Union': 'eu', 'Netherlands (the)': 'nl', 'United States (the)': 'us', 'United Kingdom (the)': 'gb',
    'Korea (the Republic of)': 'kr', 'Włochy': 'it', 'Korea Południowa': 'kr', 'Stany Zjednoczone': 'us', 'Holandia': 'nl', 'Niemcy': 'de' };
  for (const [n, c] of Object.entries(names)) assert.deepEqual(gtEnv.gtNm(n), [c], n);
  for (const n of ['Grand Total', 'All Other', 'Total Latin America', 'Pozostałe kraje', 'Others']) assert.ok(I('n', n).includes('img/glify/globe.svg'), n + ' — glob');
  assert.ok(I('c', 'JPY').includes(gtFlag('jp')) && I('c', 'JPY').includes('<i>¥</i>') && I('c', 'JPY').includes('JPY'), 'waluta: flaga, kod, symbol');
  assert.ok(I('m', 'eur').includes(gtFlag('eu')) && I('m', 'ust10').includes(gtFlag('us')) && I('m', 'spx').includes(gtFlag('us')) && I('m', 'msciem').includes('glify/globe.svg'));
  assert.ok(I('m', 'btc').includes('img/krypto/btc.svg') && I('k', ['BTC', 'ETH']).includes('img/krypto/eth.svg'));
  assert.ok(I('e', 'ILF').includes(gtFlag('br')) && I('e', 'VGK').includes(gtFlag('ch')) && I('e', 'ASEA').includes('<i class="more">+2</i>'), 'ETF zastępczy regionu — flagi krajów');
  assert.equal(I('cs', 'jpy'), '<small class="mtxt">JPY · ¥</small>'); assert.equal(I('cs', 'ust10'), ''); assert.equal(I('cs', 'zzz'), '');
  assert.ok(I('iss', 'SPY').includes('>SP</span>') && I('iss', 'VGK').includes('Vanguard') && I('iss', 'ZZZZ') === '', 'wydawca ETF zastępczego — własny znaczek');
  assert.ok(!/https?:/.test(I('f', 'PL') + I('c', 'EUR') + I('m', 'btc')), 'bez obcych adresów obrazków');
  // kolory: plus zielony, minus czerwony, zero i brak bez koloru; inv — kolumna, w której plus = odpływ
  assert.equal(I('t', 5), ' pos'); assert.equal(I('t', -5), ' neg'); assert.equal(I('t', 0), ''); assert.equal(I('t', null), ''); assert.equal(I('t', NaN), '');
  assert.equal(I('t', 5, 1), ' neg'); assert.equal(I('t', -5, 1), ' pos'); assert.equal(I('t', 0, 1), '');
  assert.equal(I('w', -1.5, '−1,5'), '<span class="neg">−1,5</span>'); assert.equal(I('w', 0, '0'), '0'); assert.equal(I('w', 2, '+2', 1), '<span class="neg">+2</span>');
});

test('v96-global_tables: rezerwy, stopy, COFER, bilans płatniczy i przegląd — flaga przy każdym kraju, znak waluty, kolory, zero bez koloru', () => {
  const I = gtEnv.gtI;
  const fm0 = html.indexOf('/* v50 (fedimf) początek: Fed H.4.1'), fm1 = html.indexOf('/* v50 koniec (fedimf) */', fm0);
  const F = new Function('t', 'escH', 'engDate', 'engNum', 'nfmt', 'instRow', 'instFoot', 'instMld', 'instSign', 'gOk', 'renderInst', 'LANG', 'gtI',
    html.slice(fm0, fm1) + '\nreturn {rezHtml};')(gtT, gtEsc, x => 'D(' + x + ')', v => String(v), (v, d) => Number(v).toFixed(d || 0),
    (l, v, e, n) => `[${l}|${v}|${n}]`, d => gtEsc(d), m => (m / 1000).toFixed(1), v => v > 0 ? '+' : (v < 0 ? '−' : ''), () => {}, () => {}, 'pl', I);
  const R = { at: 'x', order: ['CHN', 'JPN'], missing: ['TWN'], countries: { CHN: { pl: 'Chiny', total: 3786.1, fx: 3416.3, gold: 303.7, d1m: -64.1, d12m: 158.5, p12m: 4.4, asof: '2026-06' },
    JPN: { pl: 'Japonia', total: 1207.5, fx: 1010.8, gold: null, d1m: 0, d12m: null, p12m: null, asof: '2026-08' } } };
  const h = F.rezHtml(R);
  assert.ok(h.includes('<span class="cell"><span class="icos"><img class="ico" src="img/flagi/cn.svg"') && h.includes(gtFlag('jp')), 'flaga przy kraju (kod ISO3)');
  assert.ok(h.includes('<span class="cell mono neg">−64.1</span>') && h.includes('<span class="cell mono pos">+158.5'), 'spadek czerwony, wzrost zielony');
  assert.ok(h.includes('<span class="cell mono">0.0</span>'), 'zero bez koloru');
  assert.ok(h.includes('<td><span class="cell mono">—</span></td>') && !h.includes('mono neg">—') && !h.includes('mono pos">—'), 'brak = szare „—”');
  assert.ok(h.includes('flagi/tw.svg') && !h.includes('rez.src') && !h.includes('data.imf.org'), 'brakujący kraj z flagą; bez źródła');
  // stopy i kursy efektywne
  const e0 = html.indexOf('const SP={data:null};'), e1 = html.indexOf('/* v54: ZMIERZONE dzienne', e0);
  const SP = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'instFoot', 'escH', 'engDate', 'gtI', html.slice(e0, e1) + '\nreturn {spApply, EER, eerApply, eerCell, eerRegion, spBlock, spRegion};')(
    gtT, () => {}, () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), s => s, gtEsc, s => s, I);
  SP.spApply({ at: 'x', order: ['XM', 'US'], rows: { XM: { rate: 2, date: '2026-09-20', d12: -0.5, vs_us: -2.25, last: ['2025-06', -0.25] }, US: { rate: 4.25, date: '2026-09-20', d12: 0, vs_us: 0 } } });
  SP.eerApply({ at: 'x', rows: { XM: { c30: 1.2, c12: -0.4, m: '2026-08', d: '2026-09-22' }, US: { c30: 0, c12: 2 } } });
  const sb = SP.spBlock();
  assert.ok(sb.includes(gtFlag('eu')) && sb.includes(gtFlag('us')), 'strefa euro (XM) i USA z flagami');
  assert.ok(sb.includes('<span class="cell mono neg">−0.50</span>') && sb.includes('<span class="cell mono">0</span>'), 'zmiana stopy: spadek czerwony, zero bez koloru');
  assert.ok(SP.eerCell('XM') === '<span class="pos">+1.2%</span> · <span class="neg">−0.4%</span>' && SP.eerCell('US') === '0% · <span class="pos">+2.0%</span>', 'siła waluty w kolorze, 0 bez koloru');
  const er = SP.eerRegion('eur'); assert.ok(er.includes('"c":"<span class=\\"ccy\\">') && er.includes('EUR<i>€</i>'), 'waluta: flaga, kod i symbol');
  assert.ok(SP.spRegion('usa').startsWith('<div class="wide"><dt>sp.region</dt><dd><span class="icos">'), 'linia regionu: flaga banku centralnego');
  assert.ok(!sb.includes('sp.src') && !sb.includes('eer.src'), 'bez zdań o źródłach');
  // COFER, bilans płatniczy (wypływ mieszkańców odwrotnie), przegląd
  const c0 = html.indexOf('const COF={data:null};'), c1 = html.indexOf('function renderInst(){', c0);
  const X = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'escH', 'engDate', 'instFoot', 'etfCls', 'bopMld', 'LANG', 'gtI', html.slice(c0, c1) + '\nreturn {COF, cofApply, cofHtml, BIL, bilApply, bilHtml};')(
    gtT, () => {}, () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => Number(v).toFixed(d), gtEsc, s => s, s => s, v => v > 0 ? 'pos' : (v < 0 ? 'neg' : ''), v => v == null ? '—' : String(v), 'pl', I);
  X.cofApply({ at: 'x', asof: '2026-Q2', order: ['USD', 'OTHC'], rows: { USD: { sh: 56.3, d1: -0.4, d4: 0, v: 7000, dv4: 12 }, OTHC: { sh: 3, d1: 0.1, d4: 0.2, v: 1, dv4: 0 } } });
  const cf = X.cofHtml(X.COF.data);
  assert.ok(cf.includes('<span class="ccy">') && cf.includes(gtFlag('us')) && cf.includes('<i>$</i>') && cf.includes('img/glify/coin.svg'), 'waluty ze znakiem; „inne” z glifem');
  assert.ok(cf.includes('<span class="cell mono neg">−0.40</span>') && cf.includes('<span class="cell mono">0</span>') && !cf.includes('cof.src'));
  const S4 = (v) => ['2025-Q3', '2025-Q4', '2026-Q1', '2026-Q2'].map(q => [q, v]);
  X.bilApply({ at: 'x', order: ['DEU'], rows: { DEU: { q: '2026-Q2', s: { in_d: S4(1), in_p: S4(-2), in_o: S4(0), out_d: S4(3), out_p: S4(0), out_o: S4(0) } } } });
  const bl = X.bilHtml(X.BIL.data);
  assert.ok(bl.includes(gtFlag('de')), 'flaga kraju');
  assert.ok(bl.includes('<span class="cell mono neg">-2</span>') && bl.includes('<span class="cell mono">0</span>'), 'składnik napływu: minus czerwony, zero bez koloru');
  assert.ok(bl.includes('<span class="cell mono neg">12</span></td></tr>'), 'wypływ mieszkańców (plus = odpływ) na czerwono');
  assert.ok(!bl.includes('bil.src'));
});

test('v96-global_tables: CFTC — znak euro, flagi i glob przy rynkach, loga BTC/ETH, netto w kolorze, bez kafelka „Źródło” i linku', () => {
  const env = { ENG_OVR: {} };
  const deps = { ENG_OVR: env.ENG_OVR, t: (k, v) => k + (v ? ':' + JSON.stringify(v) : ''), nfmt: v => String(v), instSign: v => v > 0 ? '+' : (v < 0 ? '−' : ''), escH: gtEsc, gAgeNote: () => '',
    instRow: (l, v, e, n) => `<div class="etfk"><span>${l}</span><b>${v}</b><small class="mtxt">${n}</small></div>`, instFoot: d => gtEsc(d), engK: (l, v) => `<div class="etfk wrap"><span>${l}</span><b>${v}</b></div>`,
    engDate: s => s, engPeriod: p => p.value, gOk: () => {}, srvJSON: () => Promise.resolve(null), renderEng: () => {}, document: { hidden: false }, setInterval: () => 1, clearInterval: () => {}, gtI: gtEnv.gtI };
  const names = Object.keys(deps);
  Object.assign(env, new Function(...names, html.slice(cf0, cf1) + '\nreturn {cftcApply};')(...names.map(n => deps[n])));
  const g = { dealer: { long: 1, short: 3, spread: 0, net: -2, chg_net: 0 }, asset_mgr: { long: 5, short: 1, spread: 0, net: 4, chg_net: 1 }, lev_funds: { long: 1, short: 2, spread: 0, net: -1, chg_net: -3 }, other_rept: { net: 0 }, nonrept: { net: 1 } };
  const mk = asof => ({ asof, oi: 10, oi_chg: 1, units: 'u', groups: g, hist: { dates: ['2026-06-16', asof], lev_funds: [5, -1], asset_mgr: [1, 4], dealer: [0, -2], other_rept: [0, 0], nonrept: [1, 1], oi: [9, 10] } });
  env.cftcApply({ at: 'x', markets: { eur: mk('2026-09-15'), jpy: mk('2026-09-15'), ust10: mk('2026-09-15'), msciem: mk('2026-09-15'), btc: mk('2026-09-15'), eth: mk('2026-09-15') } });
  const el = { hidden: true, innerHTML: '' };
  assert.equal(env.ENG_OVR['cftc-euro-fx'](el), true);
  const h = el.innerHTML;
  assert.ok(/<h2><span class="icos"><img class="ico" src="img\/flagi\/eu\.svg"/.test(h), 'tytuł ze znakiem euro');
  assert.ok(h.includes('<span class="cell mono neg">−2</span>') && h.includes('<span class="cell mono pos">+4</span>') && h.includes('<span class="cell mono">0</span>'), 'netto: plus zielony, minus czerwony, zero bez koloru');
  assert.ok(h.includes('<b><span class="pos">+4</span></b>') && h.includes('cftc.chg:{"v":"<span class=\\"neg\\">−3</span>"}'), 'kafelki netto i zmiany w kolorze');
  for (const c of ['jp', 'us']) assert.ok(h.includes(gtFlag(c)), 'rynek ' + c);
  assert.ok(h.includes('<span class="cell"><span class="icos"><img class="ico" src="img/glify/globe.svg"') && h.includes('cftc.m.msciem'), 'MSCI EM — glob');
  assert.ok(!h.includes('eng.k.src') && !h.includes('cftc.src') && !h.includes('cftc.gov'), 'bez źródła przy liczbach');
  assert.equal(env.ENG_OVR['cftc-crypto'](el), true);
  assert.ok(el.innerHTML.includes('img/krypto/btc.svg') && el.innerHTML.includes('img/krypto/eth.svg') && !el.innerHTML.includes('eng.k.src'), 'loga BTC i ETH, bez kafelka „Źródło”');
});

test('v96-global_tables: widoki silnika — flagi krajów z ISO3; kolor według znaku z pliku (odpływ netto ujemny = czerwony, także kafelek i nagłówek); bez źródła, praw i odcisku pliku', () => {
  const a0 = html.indexOf('function engPairs(rec){'), a1 = html.indexOf('\n/* v58: panele silnika w języku widza', a0), k0 = html.indexOf('function engKpis(rec){'), k1 = html.indexOf('\nfunction engWithheld(', k0);
  assert.ok(a0 > 0 && a1 > a0 && html.slice(a0, a1).includes('function engDest(rec){'), 'wycinek z engDest');
  const E = new Function('t', 'escH', 'engCty', 'engHalf', 'engBld', 'engMln', 'engNum', 'engK', 'LANG', 'engDate', 'engPeriod', 'engTx', 'engAge', 'engAttr', 'engRights', 'engLim', 'engTable', 'engSafeUrl', 'gtI',
    html.slice(a0, a1) + '\n' + html.slice(k0, k1) + '\nreturn {engPairs, engDestRows, engDest, engKpis, engBound};')(
    gtT, gtEsc, (c, pl) => pl || c, x => String(x), v => String(v), v => (Number(v) > 0 ? '+' : '') + v, v => String(v), (l, v, w) => `<div class="etfk${w ? ' wrap' : ''}"><span>${l}</span><b>${v}</b></div>`, 'pl',
    s => s, () => 'P', () => 'tx', () => 'age', () => 'ATTR', () => 'RIGHTS', () => ['lim'], () => '', u => u, gtEnv.gtI);
  // prawdziwe wiersze WDI z 24.09.2026: odpływy netto są w pliku UJEMNE („Wartość ujemna to odpływ netto”)
  const out = E.engDestRows([{ code: 'NLD', name_pl: 'Holandia', value: '-19616207108.3879', previous: '-20877434452.6139' }, { code: 'BRA', name_pl: 'Brazylia', value: '-17512844211.93', previous: '834210216.59' }, { code: 'XKX', name_pl: 'Kosowo', value: '0', previous: null }], '2024', '2023');
  const inn = E.engDestRows([{ code: 'IRL', name_pl: 'Irlandia', value: '382049649287.081', previous: '165860971208.244' }, { code: 'FRA', name_pl: 'Francja', value: '28417546614.5479', previous: '-12285177530.1403' }], '2024', '2023');
  assert.ok(out.includes(gtFlag('nl')) && out.includes(gtFlag('br')) && out.includes(gtFlag('xk')) && inn.includes(gtFlag('ie')), 'flaga z kodu ISO3');
  assert.ok(out.includes('<span class="cell mono neg" title="eng.exact{&quot;v&quot;:&quot;-19616207108.3879&quot;}"'), 'odpływ netto (liczba ujemna) — czerwony');
  assert.ok(out.includes('<span class="cell mono neg" title="eng.exact{&quot;v&quot;:&quot;-20877434452.6139&quot;}"'), 'rok wcześniej też odpływ — czerwony');
  assert.ok(out.includes('<span class="cell mono pos" title="eng.exact{&quot;v&quot;:&quot;834210216.59&quot;}"'), 'rok wcześniej napływ — zielony');
  assert.ok(!out.includes('class="cell mono pos" title="eng.exact{&quot;v&quot;:&quot;-'), 'żadna ujemna liczba nie jest zielona');
  assert.ok(out.includes('<span class="cell mono" title="eng.exact{&quot;v&quot;:&quot;0&quot;}"'), 'zero bez koloru');
  assert.ok(inn.includes('<span class="cell mono pos" title="eng.exact{&quot;v&quot;:&quot;382049649287.081&quot;}"') && inn.includes('<span class="cell mono neg" title="eng.exact{&quot;v&quot;:&quot;-12285177530.1403&quot;}"'), 'napływ zielony; ujemny rok wcześniej czerwony');
  const d = E.engDest({ engine_panel: { data: { year: 2024, previous_year: 2023, counts: { inflows: 68, outflows: 51 }, inflows: [{ code: 'IRL', value: '1' }], outflows: [{ code: 'NLD', value: '-1' }] } } });
  assert.ok(d.includes('<summary><b class="pos">eng.d.in{') && d.includes('<summary><b class="neg">eng.d.out{'), 'nagłówki: największe napływy zielone, odpływy czerwone');
  const k = E.engKpis({ engine_panel: { data: { year: 2024, inflows: [{ code: 'IRL', name_pl: 'Irlandia', value: '382049649287.081' }], outflows: [{ code: 'NLD', name_pl: 'Holandia', value: '-19616207108.3879' }], counts: {} } } });
  assert.ok(k.includes('<div class="etfk wrap"><span>eng.k.in{"y":"2024"}</span><b><span class="pos"><span class="icos"><img class="ico sm" src="img/flagi/ie.svg"'), 'największy napływ zielony, z flagą, kafelek z zawijaniem');
  assert.ok(k.includes('<div class="etfk wrap"><span>eng.k.out{"y":"2024"}</span><b><span class="neg"><span class="icos"><img class="ico sm" src="img/flagi/nl.svg"'), 'największy odpływ czerwony, z flagą, kafelek z zawijaniem (telefon)');
  const pr = E.engPairs({ engine_panel: { data: { latest_period: 'H1', previous_period: 'H0', counts: {}, pairs: [{ investor: 'JPN', issuer: 'USA', position_tenths: 10, change_tenths: -5 }] } } });
  assert.ok(pr.includes(gtFlag('jp')) && pr.includes(gtFlag('us')) && pr.includes('<span class="cell mono neg">'), 'para krajów: dwie flagi; spadek czerwony');
  const b = E.engBound({ view: 'wdi-destinations', values: [{ label_pl: 'x', value: 1, unit_label_pl: 'u' }], source_url: 'https://example.org', attribution: 'ATTR', rights: { sentence_pl: 'RIGHTS' }, source_sha256: 'abcdef1234567890', generated_at: 'G', valid_until: 'V', data_age: {}, period: {} });
  assert.ok(!b.includes('eng.k.src') && !b.includes('ATTR') && !b.includes('RIGHTS') && !b.includes('example.org') && !b.includes('abcdef'), 'bez źródła, praw, linku i odcisku pliku');
  assert.ok(b.includes('gt.eng.foot{"g":"G","v":"V"}') && b.includes('eng.k.age') && b.includes('<h2><span class="icos"><img class="ico" src="img/glify/globe.svg"'), 'data pliku i wiek zostają; glob przy tytule');
  const w0 = html.indexOf('function engWithheld('), w1 = html.indexOf('\n}', w0);
  assert.ok(!html.slice(w0, w1).includes("t('eng.k.src')") && !html.slice(w0, w1).includes("t('eng.k.rights')"), 'karta wstrzymana: bez źródła i praw');
});

test('v96-global_tables: bloki krajów — flagi w nagłówkach i liniach regionu, kolory liczb; żadnych zdań o źródłach w tabelach GLOBAL', () => {
  const I = gtEnv.gtI;
  const a0 = html.indexOf('const ZAG={data:null};'), a1 = html.indexOf('function renderInst(){', a0);
  const f = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'instRow', 'instFoot', 'engNum', 'engDate', 'escH', 'etfCls', 'bopMld', 'instMld', 'LANG', 'LOCALE', 'ENG_DN', 'gAgeNote', 'TIC', 'INST', 'gtI',
    html.slice(a0, a1) + '\nreturn {ZAG, zagApply, zagBlock, zagRegion, brRegion, trBlock, thRegion, safeApply, safeHtml, kanApply, kanHtml, korApply, korRegion, spwApply, spwHtml, mxApply, mxRegion, flowOverview};')(
    gtT, () => {}, () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => Number(v).toFixed(d), (l, v, e, n) => `[${l}|${v}|${n}]`, s => s, v => String(v), s => s, gtEsc,
    v => v > 0 ? 'pos' : (v < 0 ? 'neg' : ''), v => v == null ? '—' : (v > 0 ? '+' : '') + v, v => String(v), 'pl', { pl: 'pl-PL' }, {}, () => '', null, null, I);
  f.zagApply({ at: 'x', in: { d: [['2026-09-24', 5, -2, 0, 3]] }, tw: { d: [['2026-09-24', -1000, 0, 0, 0, -30, '2026-09-18']] }, hk: { d: [['2026-09-24', 2000, 0, 0, 0, 60, '2026-09-18']] },
    tr: { d: [['2026-09-19', -10, 4, 0, 0, 0, 0]] }, th: { d: [['2026-09-24', 0, 0, 0, 0, 0, 1000, 0, 32, '2026-09-18']] } });
  const z = f.zagBlock();
  assert.ok(/<h3 class="mtxt"><span class="icos">.*flagi\/in\.svg.*flagi\/tw\.svg.*flagi\/hk\.svg/.test(z.slice(0, z.indexOf('</h3>'))), 'nagłówek: Indie, Tajwan, Hongkong');
  assert.ok(z.includes('[<span class="icos"><img class="ico sm" src="img/flagi/in.svg"') && z.includes('|<span class="pos">+3.0 inst.mln.usd</span>|'), 'kafelek Indii: flaga, napływ zielony');
  assert.ok(z.includes('<span class="neg">−1.0 ob.mld.twd</span>') && z.includes('<td><span class="cell mono neg">−2.0</span></td>'), 'odpływ czerwony (kafelek i tabela)');
  assert.ok(!z.includes('ob.src'), 'bez źródeł');
  assert.ok(f.zagRegion('ind').startsWith('<div class="wide"><dt><span class="icos"><img class="ico sm" src="img/flagi/in.svg"') && f.zagRegion('chn').includes(gtFlag('hk')), 'linie regionu z flagami');
  assert.ok(f.trBlock().includes(gtFlag('tr')) && f.trBlock().includes('<span class="neg">−10 inst.mln.usd</span>') && !f.trBlock().includes('tr.src'));
  assert.ok(f.thRegion('asean').includes(gtFlag('th')) && f.thRegion('asean').includes('"v":"0"'), 'Tajlandia: zero bez koloru');
  f.safeApply({ at: 'x', m: [['2026-08', 1, -2, 3, 1, 2, 0, 0]] });
  const sf = f.safeHtml({ at: 'x', m: [['2026-08', 1, -2, 3, 1, 2, 0, 0]] });
  assert.ok(sf.includes(gtFlag('cn')) && sf.includes('<span class="neg">−2.0 inst.mld.usd</span>') && !sf.includes('sf.src'));
  const kh = f.kanHtml({ at: 'x', m: [['2026-07', 1000, 0, 500, 0, -200]] });
  assert.ok(kh.includes(gtFlag('ca')) && kh.includes('<span class="neg">-200 kan.u</span>') && !kh.includes('kan.src'), 'Kanada: flaga, kolor, bez formuły źródła');
  f.korApply({ at: 'x', m: [['2026-08', 1, -1, 1, -1, 1400]] });
  assert.ok(f.korRegion('jpn').includes(gtFlag('kr')), 'Korea w regionie Japonia i Korea z flagą');
  const spw = { at: 'x', m: [['2026-06', 100000], ['2026-07', 99000]], r: { ea: [['2026-07', 5000]], nam: [['2026-07', 3000]], asia: [['2026-07', 1000]] },
    kr: [{ m: '2026-07', c: [['Japonia', 'Japan', 20000, 20], ['Holandia', 'Netherlands (the)', 8000, 8], ['Pozostałe kraje', 'Others', 1, 1]] }] };
  f.spwApply(spw); const sw = f.spwHtml(spw);
  assert.ok(sw.includes(gtFlag('pl')) && sw.includes(gtFlag('jp')) && sw.includes(gtFlag('nl')) && sw.includes(gtFlag('eu')) && sw.includes(gtFlag('ca')) && sw.includes('glify/globe.svg'), 'Polska, kraje posiadaczy (nazwy), regiony (UE, Ameryka Płn., glob)');
  assert.ok(sw.includes('<span class="neg">-1000 spw.u</span>') && !sw.includes('spw.src'));
  const fo = f.flowOverview();
  assert.ok(fo.includes(gtFlag('in')) && fo.includes(gtFlag('tw')) && fo.includes(gtFlag('hk')), 'przegląd: flaga przy każdym kraju');
  // żaden blok tabel GLOBAL nie rysuje zdań o źródłach ani linków do dostawców
  const body = html.slice(html.indexOf('function renderBis(){'), html.indexOf('/* v50 BIS: koniec */')) + html.slice(html.indexOf('function renderTic(){'), html.indexOf('/* v50 (fedimf) początek')) +
    html.slice(html.indexOf('function rezHtml(R){'), html.indexOf('/* v50 koniec (fedimf) */')) + html.slice(html.indexOf('const EER={data:null};'), html.indexOf('/* v37: Twelve Data TYLKO'));
  const used = [...new Set([...body.matchAll(/t\('([a-z0-9]+\.(?:[a-z0-9]+\.)*(?:src|api|nyfed))'/g)].map(x => x[1]))];
  assert.deepEqual(used, [], 'klucze źródeł rysowane w tabelach GLOBAL: ' + used.join(', '));
  assert.ok(!/href="https:\/\/(data\.imf\.org|www\.cftc\.gov|fred\.stlouisfed\.org)/.test(body), 'bez linków do dostawców');
});

test('v96-global_tables: tytuły i opisy bez nazw dostawców (pl, en); TradingView — bez stopki ze źródłem, link widgetu i zgoda zostają', () => {
  const a = 'const EXTRA89=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort(), 'te same klucze pl/en');
  // rez.sub zostaje poza listą: „pozycja w MFW” to składnik rezerw (rodzaj aktywa), nie nazwa dostawcy
  const prov = /\b(BIS|MFW|IMF|FRED|EBC|ECB|Eurostat|NSDL|TWSE|HKEX|ThaiBMA|SAFE|FSS|KRX|Banxico|CBRT|Statistics Canada|MOF|TIC|CFTC|TradingView|Twelve Data|INDEVAL|H\.4\.1|Ministerstwo Finansów|Ministry of Finance)\b/;
  const titles = ['bis2.t', 'bis2.sub', 'tic.t', 'tic.hold.t', 'tic.members', 'rez.t', 'sp.t', 'sp.c.fx', 'eer.reg', 'ob.sub', 'ob.reg', 'ob.reg.hk', 'br.t', 'br.reg', 'tr.t', 'tr.reg', 'th.t', 'th.reg', 'th.sub',
    'cof.t', 'bil.t', 'bil.reg', 'sf.t', 'sf.reg', 'sf.sub', 'ue.t', 'ue.sub', 'kan.t', 'kan.reg', 'kor.t', 'kor.reg', 'kor.sub', 'mx.t', 'mx.reg', 'mx.sub', 'spw.t', 'spw.reg', 'spw.sub', 'fo.t', 'fo.sub',
    'fo.usa', 'fo.can', 'fo.eur', 'fo.jpn', 'fo.pol', 'fo.polspw', 'fo.kor', 'fo.chn', 'fo.ind', 'fo.twn', 'fo.tha', 'fo.mex', 'fo.tur', 'fo.bra', 'fo.bram', 'inst.t', 'inst.sub', 'inst.fred.t', 'inst.fred.sub',
    'inst.fred.walcl', 'inst.fred.tga', 'inst.ecb.t', 'inst.ecb.sub', 'inst.tgb.t', 'inst.bop.t', 'inst.bop.sub', 'inst.mof.t', 'cftc.x.t', 'cftc.rep', 'eng.t.cftc-euro-fx', 'tv.t.markets', 'tv.t.calendar',
    'tv.t.heatmap', 'tv.t.chart', 'tv.sub.markets', 'tv.sub.heatmap', 'g.d.td', 'g.d.tdnote', 'g.d.tdnote.srv'];
  for (const l of ['pl', 'en']) for (const k of titles) { assert.ok(D[l][k], l + ' ' + k); assert.ok(!prov.test(D[l][k]), l + ' ' + k + ': ' + D[l][k]); }
  for (const k of ['ob.tw.usd', 'ob.hk.usd', 'th.usd', 'mx.usd', 'kor.usd']) assert.ok(!/Fed/.test(D.pl[k] + D.en[k]), k + ': kurs bez nazwy dostawcy');
  for (const l of ['de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) for (const k of ['tv.t.markets', 'tv.t.calendar', 'tv.t.heatmap', 'tv.t.chart']) assert.ok(D[l][k] && !D[l][k].includes('TradingView'), l + ' ' + k);
  const X = tvFor('pl', 'dark'), r0 = html.indexOf('function tvRender(k){'), r1 = html.indexOf('\nfunction tvRenderAll(', r0), p0 = html.indexOf('function tvPlaceholder(k){');
  assert.ok(!html.slice(r0, r1).includes("t('tv.foot')") && !html.slice(r0, r1).includes('>tradingview.com</a>'), 'bez dodatkowej stopki ze źródłem');
  assert.ok(html.slice(r0, r1).includes('data-tv-off="1"'), 'wycofanie zgody zostaje');
  assert.ok(html.slice(p0, r0).includes("t('tv.ph',{w:t('tv.n.'+k)})") && html.slice(p0, r0).includes('>TradingView</a>'), 'tekst zgody z nazwą zostaje (prywatność)');
  assert.ok(X.tvMarkup('markets').includes('tradingview-widget-copyright'), 'własny link widgetu zostaje');
});

test('v96-global_tables: widoki silnika — teksty z plików (pl) i tłumaczenia (en) bez nazw dostawców: podtytuł, wiek danych, „Czego nie mówią”, karta wstrzymana', () => {
  // prawdziwe teksty z plików data/widoki/*.json z 24.09.2026 (pola opisowe)
  const R = {"wdi-destinations":{"view":"wdi-destinations","title_pl":"Dokąd płynie kapitał portfelowy","kind_pl":"Przepływ","says_pl":"Roczny napływ netto inwestycji w akcje do gospodarek świata, według Banku Światowego.","not_says_pl":"Nie mówi, skąd ten kapitał przyszedł.","attribution":"Źródło: World Bank, World Development Indicators, wskaźnik BX.PEF.TOTL.CD.WD (licencja CC BY 4.0). The World Bank: World Development Indicators: Balance of Payments database, International Monetary Fund (IMF); International Debt Statistics, World Bank (WB). Bank Światowy nie jest autorem tej strony i jej nie popiera.","data_age":{"basis":"CAPTURED_AT","phrase_pl":"Dane roczne, publikowane z opóźnieniem; w chwili pobrania miały 20 mies."},"limitations_pl":["To napływ netto kapitału portfelowego w akcje do gospodarki. Nie mówi, skąd kapitał przyszedł.","Wartość ujemna to odpływ netto: więcej kapitału wycofano, niż napłynęło.","Centra finansowe, np. Irlandia czy Luksemburg, często pokazują przepływy do zarejestrowanych tam funduszy — to miejsce rejestracji, niekoniecznie ostateczny cel kapitału.","Gospodarki według Banku Światowego (kraje i terytoria); regiony i grupy dochodowe są wykluczone.","Nazwy po polsku z przejrzanej tabeli; nazwa u źródła zostaje w podpowiedzi.","Dane roczne, publikowane z opóźnieniem. Świeżość nie została oceniona.","Brak danych nie oznacza zera. Netto zero nie oznacza braku transakcji.","Pokazujemy 20 największych napływów i 20 największych odpływów; pozostałe są policzone.","Z atrybucją źródła (licencja CC BY 4.0)."],"rights":{"code":"CC_BY_4_0_ATTRIBUTED","sentence_pl":"Licencja CC BY 4.0: wolno używać z pełnym podaniem źródła (Bank Światowy; wskaźnik z bazy MFW), także komercyjnie; Bank Światowy nie jest autorem tej strony i jej nie popiera."},"reason_texts_pl":["Właściciel dopuścił ten widok do publicznego pokazywania osobną, ważną decyzją.","Decyzja o użyciu źródła jest ważna, a kopia danych mieści się w swoim czasie życia."],"reason_codes":["PUBLIC_DISPLAY_ADMITTED","DECLARATIONS_MATCHED"],"generated_at":"2026-09-24T14:58:12.654311+00:00","valid_until":"2026-10-24T14:50:35.000000+00:00","period":{"kind":"YEAR","source_field":"data.year","value":"2024"},"captured_at":"2026-09-24T15:01:16.227692+00:00"},"imf-portfolio-pairs":{"view":"imf-portfolio-pairs","title_pl":"Kto trzyma czyje papiery","kind_pl":"Stan","says_pl":"Pary gospodarek: ile papierów emitentów z jednej trzymali inwestorzy z drugiej, według MFW, co pół roku.","not_says_pl":"To stan, nie przepływ: zmiana stanu obejmuje też zmiany cen i kursów walut.","attribution":"Źródło: International Monetary Fund, Portfolio Investment Positions by Counterpart Economy (PIP, dawniej CPIS), https://data.imf.org/en/datasets/IMF.STA:PIP. Dane MFW: z podaniem źródła; wybór i zaokrąglenie nasze. Na użycie zarobkowe potrzebna zgoda MFW.","data_age":{"basis":"CAPTURED_AT","phrase_pl":"Koniec półrocza, MFW publikuje z opóźnieniem; w chwili pobrania dane miały 14 mies."},"limitations_pl":["To stan na koniec półrocza, nie przepływ: ile papierów portfelowych (akcje, udziały w funduszach i papiery dłużne) inwestorzy z jednej gospodarki trzymali w papierach emitentów z drugiej.","Zmiana stanu obejmuje zakupy i sprzedaże razem ze zmianami cen i kursów walut — nie jest przepływem.","Kraj inwestora i kraj emitenta to miejsca rezydencji, nie ostateczny właściciel ani ostateczne ryzyko. Centra finansowe (np. Kajmany, Luksemburg, Irlandia) pośredniczą między nimi.","Jako inwestorzy występują tylko gospodarki, które zgłosiły dane za to półrocze; brak zgłoszenia to brak danych, nie zero. Gospodarki, które zgłosiły tylko wcześniejsze półrocza, są policzone.","Agregaty (świat, regiony), organizacje międzynarodowe oraz pozycje nieokreślone lub poufne są pominięte w parach i policzone.","Pokazujemy 20 największych par; wartości w miliardach USD zaokrąglone do jednego miejsca po przecinku. To nasz wybór i zaokrąglenie danych MFW.","Z podaniem źródła (MFW). Świeżość nie została oceniona."],"rights":{"code":"ATTRIBUTED_NON_COMMERCIAL","sentence_pl":"Dane MFW: wolno używać i rozpowszechniać z podaniem źródła i bez zniekształcania; wybór 20 par i zaokrąglenie nasze; na użycie zarobkowe potrzebna zgoda MFW."},"reason_texts_pl":["Właściciel dopuścił ten widok do publicznego pokazywania osobną, ważną decyzją.","Decyzja o użyciu źródła jest ważna, a kopia danych mieści się w swoim czasie życia."],"reason_codes":["PUBLIC_DISPLAY_ADMITTED","DECLARATIONS_MATCHED"],"generated_at":"2026-09-24T14:58:12.654311+00:00","valid_until":"2026-10-24T14:58:11.000000+00:00","period":{"kind":"HALF","source_field":"data.latest_period","value":"2025-S1"},"captured_at":"2026-09-24T15:01:24.564310+00:00"},"tic-flows":{"view":"tic-flows","title_pl":"Przepływy: zagranica ↔ USA","kind_pl":"Przepływ","says_pl":"Czy zagranica netto kupuje, czy sprzedaje długoterminowe obligacje skarbowe i akcje spółek USA, miesiąc po miesiącu.","not_says_pl":"Nie mówi, kto konkretnie kupuje ani dlaczego. Nie obejmuje obligacji agencyjnych i korporacyjnych, więc jego liczby są mniejsze niż w widoku „Skąd płynie kapitał do papierów USA”, który liczy wszystkie klasy razem.","attribution":"Źródło: U.S. Department of the Treasury, TIC, raport SLT Table 1, Grand Total. Departament Skarbu USA nie jest autorem tej strony i jej nie popiera.","data_age":null,"limitations_pl":["Dane rządu USA; CapitalFlowAI przyjął własną zasadę: przetwarzanie przejściowe, bez redystrybucji. To nie jest zakaz Skarbu USA.","Nie mówi, kto konkretnie kupuje ani dlaczego. Nie obejmuje obligacji agencyjnych i korporacyjnych, więc jego liczby są mniejsze niż w widoku „Skąd płynie kapitał do papierów USA”, który liczy wszystkie klasy razem."],"rights":{"code":"PROJECT_RULE_NO_REDISTRIBUTION","sentence_pl":"Dane rządu USA; CapitalFlowAI przyjął własną zasadę: przetwarzanie przejściowe, bez redystrybucji. To nie jest zakaz Skarbu USA."},"reason_texts_pl":["Wstrzymane z naszej własnej zasady: danych TIC nie rozpowszechniamy, dopóki nie potwierdzimy praw do tego pliku. To nie jest zakaz Skarbu USA.","Nie zainstalowano decyzji o użyciu tego źródła. Nie pokazujemy wartości."],"reason_codes":["PROJECT_RULE_NO_REDISTRIBUTION","NO_REVIEW"],"generated_at":"2026-09-24T14:58:12.654311+00:00","valid_until":null,"period":null,"captured_at":null}};
  const dicts = {};   // słowniki EXTRA w kolejności, jak na stronie (późniejszy wygrywa)
  for (const m of html.matchAll(/const EXTRA(\d+)=/g)) { const x0 = m.index + m[0].length, D = new Function('return ' + html.slice(x0, html.indexOf(';\n', x0)))(); for (const l in D) Object.assign(dicts[l] = dicts[l] || {}, D[l]); }   // EXTRA2 to obiekt JS, nie JSON
  const g0 = html.indexOf('const engGen='), g1 = html.indexOf('function engKpis(rec){', g0), b0 = html.indexOf('function engBound(rec){'), b1 = html.indexOf('\n/* v50: CFTC', b0);
  assert.ok(g0 > 0 && g1 > g0 && b0 > 0 && b1 > b0, 'wycinki');
  const prov = /\b(MFW|IMF|International Monetary Fund|World Bank|Bank(u|iem)? Światow|Banku Światowego|CFTC|Treasury|Skarbu USA|data\.imf\.org|worldbank|CC BY)\b/;
  for (const LANG of ['pl', 'en']) {
    const t = (k, o) => { let s = dicts[LANG][k] !== undefined ? dicts[LANG][k] : (dicts.en[k] !== undefined ? dicts.en[k] : k); if (o) for (const v in o) s = s.split('{' + v + '}').join(o[v]); return s; };
    const E = new Function('LANG', 't', 'escH', 'engPeriod', 'engDate', 'engKpis', 'engK', 'engTable', 'engNum', 'gtI', 'gtEngClean', html.slice(g0, g1) + '\n' + html.slice(b0, b1) + '\nreturn {engBound, engWithheld};')(
      LANG, t, gtEsc, () => 'P', s => s, () => '', (l, v) => `[${l}|${v}]`, () => '', v => String(v), gtEnv.gtI, gtEnv.gtEngClean);
    for (const v of ['wdi-destinations', 'imf-portfolio-pairs']) {
      const h = E.engBound(R[v]), txt = h.replace(/<[^>]+>/g, ' ');
      assert.ok(!prov.test(txt), LANG + ' ' + v + ': ' + (txt.match(prov) || [''])[0] + ' w: ' + txt.slice(Math.max(0, txt.search(prov) - 80), txt.search(prov) + 40));
      assert.ok(txt.includes(LANG === 'pl' ? 'Świeżość nie została oceniona' : 'Freshness has not been assessed'), LANG + ' ' + v + ': reszta ograniczeń zostaje');
    }
    const w = E.engBound(R['wdi-destinations']);
    assert.ok(w.includes(LANG === 'pl' ? 'Wartość ujemna to odpływ netto' : 'A negative value is a net outflow') && w.includes(LANG === 'pl' ? 'Gospodarki (kraje i terytoria)' : 'Economies (countries and territories)'), LANG + ': zdania o znaczeniu liczb zostają');
    assert.ok(w.includes(LANG === 'pl' ? 'Roczny napływ netto inwestycji w akcje do gospodarek świata.' : 'Annual net inflow of equity portfolio investment into the world’s economies.'), LANG + ': podtytuł bez „według …”');
    const i = E.engBound(R['imf-portfolio-pairs']);
    assert.ok(i.includes(LANG === 'pl' ? 'publikacja z opóźnieniem; w chwili pobrania dane miały 14 mies.' : 'published with a lag; at capture the data were 14 months old'), LANG + ': wiek danych bez nazwy dostawcy');
    const x = E.engWithheld('tic-flows', R['tic-flows'], { ok: true, state: 'WITHHELD' }).replace(/<[^>]+>/g, ' ');
    assert.ok(!prov.test(x), LANG + ' karta wstrzymana: ' + (x.match(prov) || [''])[0]);
  }
  // słownik (en): tłumaczenia tych pól bez nazw dostawców
  for (const k of ['eng.x.imf-portfolio-pairs.says', 'eng.x.imf-portfolio-pairs.age', 'eng.x.imf-portfolio-pairs.lim', 'eng.x.wdi-destinations.says', 'eng.x.wdi-destinations.lim']) assert.ok(dicts.en[k] && !prov.test(dicts.en[k]), 'en ' + k);
  const C = gtEnv.gtEngClean;
  assert.equal(C('Z atrybucją źródła (licencja CC BY 4.0).'), '', 'zdanie tylko o podaniu źródła znika, także z „4.0”');
  assert.equal(C('Centra (np. Kajmany, Irlandia) pośredniczą. Z podaniem źródła (MFW). Świeżość nie została oceniona.'), 'Centra (np. Kajmany, Irlandia) pośredniczą. Świeżość nie została oceniona.', 'skróty „np.” nie psują tekstu');
  assert.equal(C('Bez nazw.'), 'Bez nazw.'); assert.equal(C(''), ''); assert.equal(C(null), null);
});

test('v96-global_tables: zero po zaokrągleniu bez koloru („−0,0%” nie jest czerwone); liczba „<0,1” ma kolor', () => {
  const I = gtEnv.gtI, Z = gtEnv.gtZero;
  assert.equal(I('w', -0.03, '−0,0%'), '−0,0%'); assert.equal(I('w', 0.04, '+0,0 mld USD'), '+0,0 mld USD'); assert.equal(I('w', -0.03, '−&lt;0,1'), '<span class="neg">−&lt;0,1</span>');
  assert.equal(I('t', -0.03, 0, '−0,0'), ''); assert.equal(I('t', -0.03, 0, '−0,03'), ' neg'); assert.equal(I('t', -0.03), ' neg'); assert.equal(I('t', 0.2, 1, '+0,2'), ' neg');
  assert.ok(Z('−0,0%') && Z('<b>+0.0</b>') && !Z('—') && !Z('+<0,1') && !Z('Holandia: −19 616,2'), 'gtZero');
  const e0 = html.indexOf('const eerPct='), e1 = html.indexOf('\nfunction eerRegion(', e0);
  const f = new Function('instSign', 'nfmt', 'EER', 'gtI', html.slice(e0, e1) + '\nreturn {eerCell};')(v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => Number(v).toFixed(d), { data: { rows: { XM: { c30: -0.03, c12: 2.4 } } } }, I);
  assert.equal(f.eerCell('XM'), '0.0% · <span class="pos">+2.4%</span>', 'kurs efektywny: zero po zaokrągleniu bez koloru i bez „−” (v98.2), wzrost zielony');
  for (const s of ["I('t',x.d1m,0,rezD(x.d1m))", "I('t',r[2],0,sg(r[2]))", "I('t',n(r.d1),0,pp(r.d1))", "G('t',x,0,v)", "I('t',nv(r.value),0,v)"]) assert.ok(html.includes(s), 'tekst komórki trafia do koloru: ' + s);
  assert.equal(html.split("c=(v,x)=>`<td><span class=\"cell mono${I('t',x,0,v)}\">${v}</span></td>`").length, 3, 'SPW: obie tabele');
});

test('v96-global_tables: flagi po przeglądzie — puste kafelki i nagłówki tabeli Indie/Tajwan/Hongkong, nagłówki „JP → …”, nazwa polska jako zapas, legenda kolorów BIS', () => {
  const I = gtEnv.gtI;
  const a0 = html.indexOf('const ZAG={data:null};'), a1 = html.indexOf('function renderInst(){', a0);
  const f = new Function('t', 'gOk', 'renderInst', 'instSign', 'nfmt', 'instRow', 'instFoot', 'engNum', 'engDate', 'escH', 'etfCls', 'bopMld', 'instMld', 'LANG', 'LOCALE', 'ENG_DN', 'gAgeNote', 'TIC', 'INST', 'gtI',
    html.slice(a0, a1) + '\nreturn {ZAG, zagApply, zagBlock};')(
    gtT, () => {}, () => {}, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => Number(v).toFixed(d), (l, v, e, n) => `[${l}|${v}|${n}]`, s => s, v => String(v), s => s, gtEsc,
    v => v > 0 ? 'pos' : (v < 0 ? 'neg' : ''), v => String(v), v => String(v), 'pl', { pl: 'pl-PL' }, {}, () => '', null, null, I);
  f.zagApply({ at: 'x', tw: { d: [['2026-09-24', 0.04, 0, 0, 0, -30, '2026-09-18']] }, hk: { d: [] }, br: { d: [['2026-09-24', 1, 1, 0, 0, 1]] } });
  const z = f.zagBlock();
  assert.ok(z.includes('[<span class="icos"><img class="ico sm" src="img/flagi/in.svg"') && z.includes('ob.in.k|—|eng.gap]'), 'pusty kafelek Indii z flagą');
  assert.ok(z.includes('<th><span class="icos"><img class="ico sm" src="img/flagi/in.svg"') && z.includes('ob.c.ineq</th>') && z.includes('<th><span class="icos"><img class="ico sm" src="img/flagi/tw.svg"') && z.includes('ob.c.twusd</th>'), 'nagłówki tabeli z flagami');
  assert.ok(z.includes('<td><span class="cell mono">+0.0</span></td>'), 'tabela: „+0,0” po zaokrągleniu bez koloru');
  const m0 = html.indexOf('/* C. Japonia: tygodniowe transakcje w papierach (MOF) */'), m = html.slice(m0, html.indexOf('\n  }', m0));
  for (const k of ['inst.mof.a.eq.s', 'inst.mof.a.lt.s', 'inst.mof.l.eq.s', 'inst.mof.l.lt.s']) assert.ok(m.includes("<th>${I('f','jp','sm')}${t('" + k + "')}</th>"), 'MOF: flaga przy ' + k);
  assert.ok(I('n', ['Nowa nazwa (the)', 'Japonia']).includes(gtFlag('jp')) && I('n', ['Japan', 'Japonia']).includes(gtFlag('jp')) && I('n', ['Others', 'Pozostałe kraje']).includes('glify/globe.svg'), 'kilka nazw: pierwsza rozpoznana, inaczej glob');
  assert.ok(html.includes("I('n',[r[1],r[0]])") && !html.includes("I('n',r[1]||r[0])"), 'SPW: nazwa polska, gdy angielska nieznana');
  const a = 'const EXTRA89=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  const r0 = html.indexOf('function renderBis(){'), r1 = html.indexOf('/* v50 BIS: koniec */', r0);
  assert.ok(html.slice(r0, r1).includes("<p class=\"pnote\">${t('gt.bis.col')}</p>"), 'BIS: linia o kolorach pod „jak czytać znak”');
  for (const l of ['pl', 'en']) assert.ok(/zielon|green/.test(D[l]['gt.bis.col']) && /czerwon|red/.test(D[l]['gt.bis.col']) && /a → b/.test(D[l]['gt.bis.col']), l + ' gt.bis.col');
  assert.ok(!/Rad[ay] Gubernatorów|Federal Reserve Board|FRED/.test(D.pl['inst.fred.sub'] + D.en['inst.fred.sub']), 'inst.fred.sub bez autora danych');
});

test('v96-global_tables: noty wymagane przez dostawców zostają w słownikach (do strony Źródła), ale nie w tabelach GLOBAL', () => {
  const vals = k => [...html.matchAll(new RegExp('"' + k.replace(/\./g, '\\.') + '":"((?:[^"\\\\]|\\\\.)*)"', 'g'))].map(m => JSON.parse('"' + m[1] + '"'));
  const kan = vals('kan.src'), ny = vals('inst.nyfed'), api = vals('inst.fred.api');
  assert.ok(kan.some(s => s.includes('This does not constitute an endorsement by Statistics Canada of this product.') && s.includes('{d}')), 'Statistics Canada: formuła „Adapted from … {d}” i brak poparcia — nadal w słowniku');
  assert.ok(ny.some(s => s.includes('The New York Fed is not responsible for publication of the data by CapitalFlowAI')), 'nota NY Fed w słowniku');
  assert.ok(api.some(s => s.includes('This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.')), 'nota FRED® API w słowniku');
  const i0 = html.indexOf('function renderInst(){'), i1 = html.indexOf('\nfunction ', i0 + 10), k0 = html.indexOf('function kanHtml(K){'), k1 = html.indexOf('\nfunction kanRegion(', k0);
  assert.ok(!html.slice(i0, i1).includes("t('inst.nyfed')") && !html.slice(i0, i1).includes("t('inst.fred.api')") && !html.slice(k0, k1).includes("t('kan.src'"), 'na stronie danych — tylko na stronie Źródła');
});

test('v96-global_tables: bilans płatniczy strefy euro — kolor w samej liczbie (komórka jak w v53); rachunek finansowy: plus = odpływ (czerwony)', () => {
  const b0 = html.indexOf("const inv=k=>k!=='ca';"), b1 = html.indexOf('/* B4. v50: rezerwy walutowe', b0);
  assert.ok(b0 > 0 && b1 > b0, 'blok BOP');
  const B = html.slice(b0, b1);
  assert.ok(B.includes("const at=(k,p)=>{const r=Array.isArray(BS[k])?BS[k].find(x=>x[0]===p):null;return r?chg(r[1],bopMld(r[1]),inv(k)):'—';};"), 'liczba w kolorze przez chg (gtI w)');
  assert.ok(B.includes('<td><span class="cell mono"${atT(k,p)}>${at(k,p)}</span></td>'), 'znacznik komórki bez zmian');
  const I = gtEnv.gtI, inv = k => k !== 'ca';
  assert.equal(I('w', 12.3, '+12,3', inv('fa')), '<span class="neg">+12,3</span>', 'rachunek finansowy: plus = kapitał wypłynął — czerwony');
  assert.equal(I('w', 12.3, '+12,3', inv('ca')), '<span class="pos">+12,3</span>', 'rachunek bieżący: nadwyżka — zielony');
});

// v96 etap 2 — obszar „crypto”: logo przy każdym aktywie krypto, funduszu, sieci i giełdzie; kolory wzrost/spadek/zero; bez nazw dostawców
const v96cEsc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const v96cT = (k, o) => k + (o ? JSON.stringify(o) : '');
const v96cHelpers = () => {   // prawdziwe pomocniki v96 (flagi, monety, sieci, giełdy, wydawcy) + pomocniki obszaru krypto
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('/* ---------- klocek: neonowa bryła', h0);
  assert.ok(h0 > 0 && h1 > h0, 'blok v96');
  const V = new Function('escH', 'ISO32', 'COIN_LOGO', html.slice(h0, h1) + '\nreturn {flagImg,glyphImg,icoWrap,coinImg,netImg,exchImg,issuerOf,fundIco,ccyIco};')(
    v96cEsc, { USA: 'US' }, { SOL: 'data:image/webp;base64,AAAA' });
  const c0 = html.indexOf('/* ===================== v96 (krypto): logo i kolor'), c1 = html.indexOf('const liveWhen=', c0);
  assert.ok(c0 > 0 && c1 > c0, 'pomocniki krypto');
  const C = new Function('coinImg', 'icoWrap', 'iconURL', 'escH', 'nName', html.slice(c0, c1) + '\nreturn {cCoins,cGrp,cGrpW};')(
    V.coinImg, V.icoWrap, id => 'data:image/png;base64,' + id, v96cEsc, id => 'n.' + id);
  return Object.assign({}, V, C);
};

test('v96-crypto: fundusze ETF — znaczek wydawcy wg NAZWY (BTC = Grayscale Mini, nie logo bitcoina), logo monet, słupki zero szare, stopka bez dostawców', () => {
  const H = v96cHelpers();
  const a0 = html.indexOf('function etfBars(day){'), a1 = html.indexOf('\nconst CGST=', a0);
  assert.ok(a0 > 0 && a1 > a0);
  const el = { '#g-etf': { innerHTML: '', hidden: true }, '#c-etf': { innerHTML: '' }, '#c-bal': { innerHTML: '', hidden: true } };
  const D = { asof: '2026-09-24', assets: {
    btc: { sym: 'BTC', d1: 100, w: 0, m: -5, cum: 1000, aum: 5000, share: 6.1, day: [['a', 10], ['b', 0], ['c', -4], ['d', null]], funds: [
      { t: 'BTC', n: 'Grayscale Bitcoin Mini Trust ETF', aum: 100, d1: 0, cum: 5, fee: 0.15, cty: 'us' },
      { t: 'IBIT', n: 'iShares Bitcoin Trust', aum: 500, d1: 3, cum: 9, fee: 0.25, cty: 'us' },
      { t: '<X>', n: '<img src=x>', aum: 1, d1: null, cum: null, fee: null, cty: 'hk' }] },
    eth: { sym: 'ETH', d1: -1, w: -1, m: 2, cum: 3, aum: 4, share: 2.2, day: [], funds: [{ t: 'ETH', n: 'Grayscale Ethereum Mini Trust ETF', aum: 1, d1: 1, cum: 1, fee: 0.15, cty: 'us' }] },
    xrp: { sym: 'XRP', d1: 1, w: 1, m: 1, cum: 1, aum: 1, share: 1, day: [], funds: [{ t: 'XRP', n: 'Bitwise XRP ETF', aum: 1, d1: 1, cum: 1, fee: 0.3, cty: 'us' }] } } };
  const ETF = { data: D, live: true, st: 'srv', stale: false, at: '10:00', meta: { at: '2026-09-24T10:00:00Z', ok: { sosovalue: true, finnhub: false }, errors: ['Finnhub: HTTP 500'] } };
  const f = new Function('ETF', 'ETF_SYMS', 'ETF_SNAP', '$', 't', 'escH', 'etfM', 'etfA', 'etfP', 'etfCls', 'etfKey', 'gAgeNote', 'LOCALE', 'LANG', 'krStabh', 'gfmt',
    'CM', 'cmA', 'cmIs', 'cmUsd', 'cftcMkt', 'cftcS', 'instFoot', 'cCoins', 'fundIco', 'flagImg', 'glyphImg', 'icoWrap', 'coinImg',
    html.slice(a0, a1) + '\nreturn {renderEtf, etfBars, etfMetaLine};')(
    ETF, ['btc', 'eth', 'sol', 'xrp'], { asof: '2026-09-23', fetched: 'x' }, s => el[s] || null, v96cT, v96cEsc, v => v == null ? '—' : String(v), v => v == null ? '—' : String(v),
    (v, d) => v == null ? '—' : v.toFixed(d == null ? 1 : d) + '%', v => v > 0 ? 'pos' : v < 0 ? 'neg' : '', () => '', () => '', { pl: 'pl-PL' }, 'pl', () => null, v => String(v),
    { data: null }, () => null, v => typeof v === 'number', v => String(v), () => null, v => String(v), d => d, H.cCoins, H.fundIco, H.flagImg, H.glyphImg, H.icoWrap, H.coinImg);
  f.renderEtf();
  const g = el['#g-etf'].innerHTML, c = el['#c-etf'].innerHTML;
  const cellBefore = marker => { const i = g.indexOf(marker); assert.ok(i > 0, marker); return g.slice(g.lastIndexOf('<span class="cell">', i), i); };
  for (const [tk, nm] of [['BTC', 'Grayscale Bitcoin Mini Trust ETF'], ['ETH', 'Grayscale Ethereum Mini Trust ETF']]) {
    const seg = cellBefore(`<b>${tk}</b><small class="mtxt">${nm}`);
    assert.ok(seg.startsWith('<span class="cell"><span class="icos"><span class="iss"') && seg.includes('title="Grayscale"'), tk + ': najpierw znaczek wydawcy z nazwy funduszu');
    assert.ok(!seg.includes(`<img class="ico" src="img/krypto/${tk.toLowerCase()}.svg"`), tk + ': duże logo monety nie udaje wydawcy');
    assert.ok(seg.includes(`<img class="ico sm" src="img/krypto/${tk.toLowerCase()}.svg"`), tk + ': małe logo monety obok');
  }
  assert.ok(cellBefore('<b>XRP</b><small class="mtxt">Bitwise XRP ETF').includes('title="Bitwise"'), 'XRP = fundusz Bitwise');
  assert.ok(cellBefore('<b>IBIT</b>').includes('>iS</span>'), 'IBIT = iShares');
  assert.ok(g.includes('&lt;X&gt;') && g.includes('&lt;img src=x&gt;') && !g.includes('<img src=x>'), 'dane z pliku escapowane');
  assert.ok(g.includes('<span class="pchip"><img class="ico sm" src="img/flagi/hk.svg"'), 'fundusz z Hongkongu z flagą');
  assert.ok(g.includes('<span class="cell"><span class="icos"><img class="ico" src="img/krypto/btc.svg"') && g.includes('<b>BTC</b><small class="mtxt">etf.n.btc</small>'), 'wiersz aktywa z logo');
  assert.ok(g.includes('<summary><span class="icos"><img class="ico" src="img/krypto/btc.svg"') && g.includes('<b>BTC</b> · etf.funds{"n":3}</summary>'), 'podsumowanie z logo');
  assert.ok(g.includes('<span class="nw"><span class="icos"><img class="ico sm" src="img/krypto/btc.svg"') && g.includes('krypto/btc.svg" alt="" title="BTC" loading="lazy" decoding="async"></span>BTC 6.10%</span>') && g.includes(' · <span class="nw"><span class="icos"><img class="ico sm" src="img/krypto/eth.svg"'), 'udział BTC i ETH z logo (logo i liczba razem)');
  const foot = g.slice(g.indexOf('<p class="pfoot">'));
  for (const w of ['SoSoValue', 'CoinGecko', 'Finnhub', 'sosovalue.com', 'coingecko.com', '<a ']) assert.ok(!foot.includes(w), 'stopka ETF bez: ' + w);
  assert.ok(foot.includes('etf.src.live') && foot.includes('etf.meta2') && foot.includes('etf.meta.okv') && foot.includes('etf.meta.errs2'), 'stopka: odświeżanie, stan automatu, odesłanie do Źródeł');
  assert.ok(g.includes('etf.b.live{"d":"2026-09-24","t":"10:00"}'), 'plakietka: data i godzina');
  const bars = f.etfBars(D.assets.btc.day);
  assert.equal((bars.match(/<rect /g) || []).length, 3, 'dzień bez danych = brak słupka, nie zero');
  assert.ok(bars.includes('fill="var(--gr)"') && bars.includes('fill="var(--rd)"') && bars.includes('fill="var(--dim)"'), 'zero szare, nie zielone');
  assert.ok(c.includes('<div class="etfr"><span><span class="icos"><img class="ico sm" src="img/krypto/btc.svg"') && c.includes('<b>XRP</b></span>'), 'szyna CRYPTO: logo przy BTC, ETH, SOL, XRP');
  const tiles = g.slice(g.indexOf('<div class="etfkpis">'), g.indexOf('<div class="list-wrap">')).split(/<div class="etfk(?: wrap)?">/).slice(1);
  assert.equal(tiles.length, 6, 'sześć kafelków (bez porównania ze stablecoinami, gdy brak danych)');
  for (const k of ['etf.k.day', 'etf.k.w', 'etf.k.m', 'etf.k.cum', 'etf.k.aum']) {
    const tl = tiles.find(x => x.includes(k + '</span>')); assert.ok(tl, k);
    assert.ok(tl.startsWith('<span><span class="icos"><img class="ico" src="img/flagi/us.svg"') && tl.includes('src="img/glify/etf.svg"'), k + ': flaga USA i znak ETF');
  }
  assert.ok(tiles.find(x => x.includes('etf.k.share</span>')).startsWith('<span><span class="icos"><img class="ico" src="img/glify/etf.svg"'), 'udział: znak ETF');
  assert.ok(g.includes('etf.k.day</span><b class="pos">100</b>') && g.includes('etf.k.w</span><b class="">0</b>') && g.includes('etf.k.m</span><b class="neg">-2</b>'), 'kafelki: wzrost zielony, spadek czerwony, zero bez koloru');
});

test('v96-crypto: stablecoiny per sieć — logo sieci w każdym wierszu, suma z USDT i USDC, zmiany zielone/czerwone, zero i brak bez koloru', () => {
  const H = v96cHelpers();
  const a0 = html.indexOf('function stcPanel(S,H){'), a1 = html.indexOf("ENG_OVR['defillama-stablecoins']=el=>", a0);
  assert.ok(a0 > 0 && a1 > a0);
  const f = new Function('t', 'gfmt', 'engDate', 'instRow', 'instFoot', 'engNum', 'escH', 'KR', 'icoWrap', 'netImg', 'coinImg', html.slice(a0, a1) + '\nreturn stcPanel;')(
    v96cT, v => v.toFixed(2) + ' mld', s => String(s), (l, v, e, n) => `<div class="etfk"><span>${l}</span><b>${v}</b>${n ? '<small>' + n + '</small>' : ''}</div>`, s => s, v => String(v), v96cEsc,
    { data: { at: 'x' } }, H.icoWrap, H.netImg, H.coinImg);
  const h = f({ asof: '2026-09-25', n: 180, total: [313e9, 0, 0, 0], rows: [['Ethereum', 147e9, 0, -0.19e9, 0], ['Hyperliquid L1', 5e9, 0, 1e9, null], ['Nowa <Sieć>', 1e9, 0, null, null]] },
    { asof: '2026-09-24', cur: 311e9, d: { '7': 1.47e9, '30': 0 } });
  assert.ok(h.includes('<span class="cell"><span class="icos"><img class="ico" src="img/sieci/ethereum.svg"') && h.includes('title="Ethereum" loading="lazy" decoding="async"></span>Ethereum</span>'), 'Ethereum z logo sieci');
  assert.ok(h.includes('img/sieci/hyper-evm.svg') && h.includes('<span class="iss" style="--ic:') && h.includes('Nowa &lt;Sieć&gt;</span>') && !h.includes('Nowa <Sieć>'), 'nieznana sieć — znaczek z literami, nazwa escapowana');
  assert.ok(h.includes('krypto/usdt.svg') && h.includes('krypto/usdc.svg') && h.includes('stc.k.tot</span><b>311.00 mld</b>'), 'suma z logo USDT i USDC');
  assert.ok(h.includes('stc.k.d7</span><b class="pos">+1.47 mld</b>') && h.includes('stc.k.d30</span><b>0</b>'), 'wzrost zielony, zero bez koloru');
  assert.ok(h.includes('<span class="cell mono neg">−0.19 mld</span>') && h.includes('<span class="cell mono ">0</span>') && h.includes('<span class="cell mono ">—</span>'), 'spadek czerwony, zero i brak bez koloru');
  assert.ok(h.includes('<p class="pfoot">stc.src eng.disclaimer</p>'), 'zdanie o sposobie liczenia (bez dostawcy — słownik)');
});

test('v96-crypto: Coin Metrics — logo BTC i ETH w nagłówkach i w tabeli, wpłynęło zielone, wypłynęło czerwone, bez linków dostawcy', () => {
  const H = v96cHelpers();
  const s0 = html.indexOf('/* v50: Coin Metrics Community (plik automatu cm.json)'), s1 = html.indexOf('/* v50 cm: koniec */', s0);
  assert.ok(s0 > 0 && s1 > s0);
  const api = new Function('ENG_OVR', 't', 'instSign', 'nfmt', 'gfmt', 'gpct', 'instRow', 'instFoot', 'escH', 'engDate', 'engNum', 'gOk', 'srvJSON', 'renderEng', 'coinImg', 'icoWrap',
    html.slice(s0, s1) + '\nreturn {cmPanel, cmTable};')(
    {}, v96cT, v => v > 0 ? '+' : (v < 0 ? '−' : ''), (v, d) => v.toFixed(d), v => v.toFixed(1) + ' u.b', v => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(2) + '%',
    (l, v, e, n) => `<div class="etfk"><span>${l}</span><b${e ? ' title="' + e + '"' : ''}>${v}</b></div>`, d => v96cEsc(d), v96cEsc, iso => 'F(' + iso + ')', v => String(v), () => {}, () => Promise.resolve(null), () => {},
    H.coinImg, H.icoWrap);
  const D = { at: '2026-09-24T20:40:00+00:00', cols: ['date', 'in', 'out', 'net', 'in_usd', 'out_usd', 'net_usd'],
    assets: { btc: { sym: 'BTC', asof: '2026-09-23', status: 'reviewed', last: { in: 10, out: 20, net: -10, in_usd: 1e9, out_usd: 2e9, net_usd: -1e9 }, sum7: { net: 0, net_usd: 0 }, sum30: { net: 5, net_usd: 5e8 },
      sply_ch7: { ntv: 3, pct: 0.1 }, sply_ch30: { ntv: 0, pct: 0 }, d: [['2026-09-22', 1, 1, 0, 1, 1, 0], ['2026-09-23', 10, 20, -10, 1e9, 2e9, -1e9]] }, eth: null } };
  const h = api.cmPanel(D);
  assert.ok(h.includes('<h3 class="mtxt"><span class="icos"><img class="ico" src="img/krypto/btc.svg"') && h.includes('<h3 class="mtxt"><span class="icos"><img class="ico" src="img/krypto/eth.svg"'), 'logo przy nagłówkach BTC i ETH (także bez danych)');
  assert.ok(h.includes('cm.in</span><b class="pos" title=') && h.includes('cm.out</span><b class="neg" title=') && h.includes('cm.net</span><b class="neg" title='), 'wpłynęło zielone, wypłynęło czerwone, netto wg znaku');
  assert.ok(h.includes('cm.net7</span><b title=') && h.includes('cm.net30</span><b class="pos" title=') && h.includes('cm.ch7</span><b class="pos" title='), 'zero bez koloru; wzrost zapasu zielony');
  assert.ok(h.includes('<th><span class="icos"><img class="ico sm" src="img/krypto/btc.svg"') && h.includes('img/krypto/eth.svg" alt="" title="ETH" loading="lazy" decoding="async"></span>ETH cm.c.net</th>'), 'logo w nagłówkach tabeli');
  assert.ok(h.includes('<span class="cell mono neg">−10.00 BTC</span>') && h.includes('<span class="cell mono">0.00 BTC</span>'), 'tabela: spadek czerwony, zero bez koloru');
  assert.ok(!h.includes('coinmetrics.io') && !h.includes('creativecommons') && !h.includes('Coin Metrics'), 'bez podpisu dostawcy w panelu');
  assert.ok(h.includes('cm.ch30</span><b title=') && h.includes('0.00 BTC (0.00%)') && !h.includes('+0.00%'), 'zmiana zapasu 0 — bez koloru i bez „+”');
});

test('v96-crypto: kafelki CRYPTO — logo przy każdym, zmiana 0 to „•” bez koloru (nie zielone ▲), bez nazw dostawców', () => {
  const H = v96cHelpers();
  const k0 = html.indexOf('const KDEF=['), k1 = html.indexOf('/* zapasowe wartości', k0);
  const KDEF = new Function(html.slice(k0, k1) + '\nreturn KDEF;')();
  const r0 = html.indexOf('function renderKPI(){'), r1 = html.indexOf('/* ===================== PALETA SCENY', r0);
  assert.ok(r0 > 0 && r1 > r0);
  const el = { innerHTML: '' };
  const vals = { mcap: { val: 2.5, unit: 'u.t', dec: 2, d: 0, src: 'CoinMarketCap', at: '2026-09-25T01:00:00Z' }, dom: { val: 58.9, unit: '%', dec: 1, d: 0.4, src: 'CoinPaprika' },
    stab: { val: 300, unit: 'u.b', dec: 1, d: -0.2, src: 'DefiLlama' }, vol: { val: 90, unit: 'u.b', dec: 1, d: null, src: 'CoinPaprika' }, tvl: { val: 88, unit: 'u.b', dec: 1, d: null, src: 'DefiLlama' } };
  new Function('$', 'kpiVals', 'isLive', 'KDEF', 'KV_SAMPLE', 't', 'sg', 'nfmt', 'engDate', 'gAgeNote', 'liveWhen', 'LIVE', 'coinImg', 'icoWrap', 'cGrp',
    html.slice(r0, r1) + '\nrenderKPI();')(() => el, () => vals, () => true, KDEF, {}, k => k, v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d) => v.toFixed(d), iso => 'D(' + iso + ')', () => '', () => 'W', { at: 'x' },
    H.coinImg, H.icoWrap, H.cGrp);
  const tiles = el.innerHTML.split('<div class="panel kpi">').slice(1);
  assert.equal(tiles.length, 6);
  const [mcap, dom, stab, vol, tvl, alt] = tiles;
  assert.ok(mcap.includes('<span class="dlt eq">• 0.00%') && !mcap.includes('▲'), 'zero — neutralne „•”');
  assert.ok(dom.includes('<span class="dlt up">▲ +0.40 u.pp') && stab.includes('<span class="dlt dn">▼ −0.20%'), 'wzrost ▲, spadek ▼');
  assert.ok(alt.includes('eng.gap') && alt.includes('<span class="ksrc"></span>'), 'brak danych — „brak”, bez liczby i bez dostawcy');
  for (const w of ['CoinMarketCap', 'CoinPaprika', 'DefiLlama', 'CoinGecko']) assert.ok(!el.innerHTML.includes(w), 'bez: ' + w);
  assert.ok(mcap.includes('<span class="ksrc">D(2026-09-25T01:00:00Z)</span>') && dom.includes('<span class="ksrc">W</span>'), 'data i czas danych zostają');
  assert.ok(mcap.includes('krypto/btc.svg') && mcap.includes('krypto/eth.svg') && dom.includes('krypto/btc.svg') && stab.includes('krypto/usdt.svg') && stab.includes('krypto/usdc.svg'));
  assert.ok(vol.includes('data-id="exch"') && tvl.includes('data-id="defi"') && alt.includes('krypto/xrp.svg') && alt.includes('krypto/bnb.svg'), 'wolumen — giełdy, TVL — DeFi, poza BTC i ETH — inne monety');
  assert.ok(!el.innerHTML.includes('<svg'), 'logo zamiast symbolu konturowego');
});

test('v96-crypto: chipy, lista i Top 10 — zero bez koloru i bez strzałki; Top 10 bez nazwy dostawcy', () => {
  const NODES = [{ id: 'btc' }, { id: 'eth' }, { id: 'rwa' }], DATA = { '24H': { btc: [5, 1.2], eth: [-3, -0.5], rwa: [0, 0] } }, st = { period: '24H', view: 'list', sel: null };
  const ch = { innerHTML: '' }, wrap = { innerHTML: '' };
  const c0 = html.indexOf('function renderChips(){'), c1 = html.indexOf('\nfunction renderLegend(', c0);
  new Function('$', '$$', 'DATA', 'st', 'NODES', 'isSel', 'iconURL', 'nName', 'fPct', 't', 'select', html.slice(c0, c1) + '\nrenderChips();')(
    () => ch, () => [], DATA, st, NODES, () => false, id => 'data:image/png;base64,' + id, id => 'n.' + id, v => String(v), k => k, () => {});
  assert.ok(ch.innerHTML.includes('<button class="chip-n eq" data-n="rwa"') && ch.innerHTML.includes('n.rwa<span class="p">• 0</span>'), 'zero: „•”, bez koloru');
  assert.ok(ch.innerHTML.includes('<button class="chip-n in" data-n="btc"') && ch.innerHTML.includes('<button class="chip-n out" data-n="eth"'));
  const l0 = html.indexOf('function renderList(){'), l1 = html.indexOf('\n/* ---------- sterowanie', l0);
  new Function('$', '$$', 'DATA', 'st', 'NODES', 'isSel', 'iconURL', 'nName', 'fInt', 'fPct', 't', 'select', html.slice(l0, l1) + '\nrenderList();')(
    () => wrap, () => [], DATA, st, NODES, () => false, id => 'data:image/png;base64,' + id, id => 'n.' + id, v => String(v), v => String(v), k => k, () => {});
  const row = wrap.innerHTML.slice(wrap.innerHTML.indexOf('data-n="rwa"'));
  assert.ok(row.includes('<span class="sz eq"') && row.includes('<span class="cell "><b>• 0</b>') && row.includes('<span class="cell">d.eq</span>'), 'lista: zero neutralne');
  assert.ok(wrap.innerHTML.includes('<span class="cell pos"><b>▲ 5</b>') && wrap.innerHTML.includes('<span class="cell neg"><b>▼ -3</b>'));
  const t0 = html.indexOf('function renderTop10(id){'), t1 = html.indexOf('/* ===================== v96 (krypto)', t0);
  const top = new Function('BASKET', 'LIVE', 'st', 't', 'flowOf', 'COIN_LOGO', 'escH', 'nfmt', 'fPct', 'coinImg', 'liveWhen', 'sg', html.slice(t0, t1) + '\nreturn renderTop10;')(
    { rwa: ['ONDO', 'OM'] }, { st: 'ok', C: { ONDO: { name: 'Ondo', mcap: 1e9, pct: { '24H': 0 } }, OM: { name: 'Mantra', mcap: 1e9, pct: { '24H': 2 } } } }, st, v96cT,
    (m, p) => m * p / 100, {}, v96cEsc, (v, d) => v.toFixed(d), v => String(v), s => '<i class="cic">' + s + '</i>', () => 'T', v => v > 0 ? '+' : v < 0 ? '−' : '');
  const h = top('rwa');
  assert.ok(h.includes('<span class="fl ">0.0</span>') && h.includes('<span class="bar "><i style="width:0.0%">') && h.includes('<span class="fl pos">+20</span>'), 'Top 10: zero bez koloru, bez „+” i bez paska');
  assert.ok(html.includes('.t10 .bar:not(.pos):not(.neg) i{background:var(--dim)}'), 'Top 10: pasek bez kierunku szary, nie turkusowy');
  assert.ok(h.includes('top.live{"t":"T"}'));
  const LIVEe = { st: 'err', err: 'HTTP 500', C: {} };
  const topE = new Function('BASKET', 'LIVE', 'st', 't', 'escH', html.slice(t0, t1) + '\nreturn renderTop10;')({ rwa: ['ONDO'] }, LIVEe, st, v96cT, v96cEsc);
  assert.ok(topE('rwa').includes('<small>HTTP 500</small>') && !topE('rwa').includes('CoinPaprika'), 'błąd bez nazwy dostawcy');
});

test('v96-crypto: panele krypto bez nazw dostawców i linków; logo giełdy, DeFi i nastrojów; dowody bez czerwieni i zieleni', () => {
  const body = (a, b) => { const i = html.indexOf(a), j = html.indexOf(b, i + a.length); assert.ok(i > 0 && j > i, a); return html.slice(i, j); };
  const kr = body('function renderKr(){', '\nfunction renderCmc(');
  assert.ok(!kr.includes('coingecko.com') && !kr.includes('alternative.me') && !kr.includes("t('kr.src.cg')") && !kr.includes("t('kr.sub')") && !kr.includes("t('kr.not')"), 'renderKr bez linków i zdań z dostawcą');
  assert.ok(kr.includes("exchImg(String(top[0]),'sm')") && kr.includes("glyphImg('gauge'") && kr.includes("cGrp(id)") && kr.includes("gi('defi')"), 'renderKr: logo giełdy, DeFi, glif nastrojów');
  const cmc = body('function renderCmc(){', '\n/* v39:');
  assert.ok(!cmc.includes('coinmarketcap.com') && !cmc.includes("t('cmc.src')") && cmc.includes("cc('BTC')+t('cmc.btc')") && cmc.includes("cc('ETH')+t('cmc.eth')") && cmc.includes("cc('USDT','USDC')") && cmc.includes("cc('BTC','ETH')+t('cmc.chg')"), 'CMC: logo przy każdym kafelku, także przy zmianie 24h');
  const why = body('function renderWhy(){', '\nfunction renderList(');
  for (const w of ['CoinPaprika', 'DefiLlama', 'CoinMarketCap', 'CoinGecko', 'SoSoValue', '--rd-rgb', '--gr-rgb']) assert.ok(!why.includes(w), 'renderWhy bez: ' + w);
  assert.ok(html.includes('.ev-direct-c{color:var(--bl);') && html.includes('.ev-unc-c{color:var(--mut);') && html.includes('.ev-proxy-c{color:var(--yl-tx);'), 'niepewne — szare, bezpośrednie — niebieskie');
  const det = body('function renderDetails(){', '\nfunction renderChips(');
  assert.ok(det.includes("t('d.meth')") && !det.includes("t('d.source')") && det.includes('cGrpW(e.f)') && det.includes("cGrpW(s.id,'lg')"), 'szczegóły: „jak liczymy” zamiast „źródło”, logo');
  const rail = body('function renderRail(){', '\nconst SEC_IDS=');
  assert.ok(rail.includes('<span class="ep">${cGrpW(e.f,\'sm\')}${nName(e.f)}</span> → <span class="ep">${cGrpW(e.t,\'sm\')}${nName(e.t)}</span>'), 'szyna: logo obu końców przepływu, logo i nazwa razem');
  const sec = body('function renderSectors(){', '\nfunction renderGauge(');
  assert.ok(!sec.includes('hsl(') && sec.includes("cGrpW(id,'sm')"), 'sektory: logo, poziom aktywności bez czerwieni');
  const bal = body('function cBal(){', '\nfunction renderEtf(');
  assert.ok(bal.includes("flagImg('us','sm')+glyphImg('etf','sm')") && bal.includes("ic('USDT','USDC')") && !bal.includes('s30>=0'), 'bilans: logo przy liniach, zero bez koloru');
  const top = body('function renderTop10(id){', '\nconst liveWhen=');
  assert.ok(!top.includes('CoinPaprika:') && !top.includes('r.fl>=0'));
});

test('v96-crypto: słownik EXTRA90 — PL i EN te same klucze, bez nazw dostawców, bez „kupuj/sprzedawaj”, inne języki tylko nadpisują istniejące', () => {
  const a = 'const EXTRA90=', x0 = html.indexOf(a);
  assert.ok(x0 > 0, 'EXTRA90 w stronie');
  const D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort());
  const prov = /CoinPaprika|CoinGecko|DefiLlama|SoSoValue|Coin Metrics|CoinMarketCap|Alternative\.me|Finnhub/;
  for (const l of Object.keys(D)) for (const k of Object.keys(D[l])) {
    assert.ok(!prov.test(D[l][k]), l + ' ' + k + ': nazwa dostawcy');
    assert.ok(!/kupuj|sprzedawaj/i.test(D[l][k]), l + ' ' + k);
    if (l !== 'pl' && l !== 'en') assert.ok(k in D.en, l + ' ' + k + ' — tylko klucze z EN');
  }
  for (const k of ['etf.b.live', 'etf.b.snap', 'etf.b.load', 'etf.src.live', 'etf.src.snap', 'top.live', 'q.fresh.d']) for (const l of ['de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) assert.ok(D[l][k], l + ' ' + k + ' — stara wersja z dostawcą nadpisana');
  assert.ok(D.pl['etf.b.live'].includes('{d}') && D.pl['top.live'].includes('{t}'), 'data i czas zostają');
  for (const k of ['kr.t', 'kr.sub', 'kr.not']) assert.ok(!(k in D.pl), 'v84: tytuł, podtytuł i opis panelu krypto nie są nadpisywane — nowe klucze kr.sub2, kr.not2');
  assert.ok(html.indexOf('for(const l in EXTRA90)') > html.indexOf('for(const l in EXTRA87)'), 'po EXTRA87');
});

test('v96-crypto: wszystkie 10 języków — teksty, które pokazują panele krypto, bez nazw dostawców (działający słownik po wszystkich EXTRA)', () => {
  const i0 = html.indexOf('const I18N={'), an = 'for(const l in EXTRA87)if(I18N[l])Object.assign(I18N[l],EXTRA87[l]);\n';
  let i1 = html.indexOf(an) + an.length;
  assert.ok(i0 > 0 && i1 > i0 + an.length);
  while (html.startsWith('const EXTRA', i1) || html.startsWith('for(const l in EXTRA', i1)) i1 = html.indexOf('\n', i1) + 1;   // także słowniki innych obszarów (późniejszy wygrywa)
  const I = new Function(html.slice(i0, i1) + '\nreturn I18N;')();
  const tx = (l, k) => (I[l] && I[l][k]) ?? I.en[k];   // jak t(): brak w języku → angielski
  const parts = [['function kpiCmc(', '\n/* ===================== PALETA SCENY'], ['function renderKr(){', '\n/* v39:'],
    ['/* v50: Coin Metrics Community (plik automatu cm.json)', '/* v50 cm: koniec */'], ['function etfBars(day){', '\nconst CGST='], ['function renderTop10(id){', '\n/* ---------- sterowanie']];
  const keys = new Set();
  for (const [a, b] of parts) {
    const x = html.indexOf(a), y = html.indexOf(b, x + a.length); assert.ok(x > 0 && y > x, a);
    for (const m of html.slice(x, y).matchAll(/'([a-z0-9]+(?:\.[A-Za-z0-9_]+)+)'/g)) if (m[1] in I.en) keys.add(m[1]);
  }
  for (const k of ['kpi.mcap', 'kpi.dom', 'kpi.stab', 'kpi.vol', 'kpi.tvl', 'kpi.alt', 'etf.n.btc', 'etf.n.eth']) if (k in I.en) keys.add(k);   // klucze składane w kodzie
  assert.ok(keys.size > 150 && keys.has('etf.src.snap') && keys.has('cm.src') && keys.has('stc.src') && keys.has('top.live'), 'zebrane klucze: ' + keys.size);
  const prov = /CoinPaprika|CoinGecko|DefiLlama|SoSoValue|Coin ?Metrics|CoinMarketCap|Alternative\.me|Finnhub/i;
  const bad = [];
  for (const l of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) for (const k of keys) { const v = tx(l, k); if (typeof v === 'string' && prov.test(v)) bad.push(l + ' ' + k); }
  assert.deepEqual(bad, [], 'nazwy dostawców w tekstach paneli krypto');
  for (const l of ['de', 'fr', 'ja']) assert.ok(!/SoSoValue/.test(tx(l, 'etf.src.snap')) && tx(l, 'etf.src.snap').includes('{d}') && tx(l, 'etf.src.snap').includes('{f}'), l + ': migawka ETF — data i czas pobrania zostają, bez dostawcy');
});

test('v96-crypto: wykres TradingView (CRYPTO) — przyciski BTC/USD i ETH/USD z logo monety i znakiem dolara; bez pomocników sam tekst', () => {
  const H = v96cHelpers(), el = { innerHTML: '', hidden: true };
  const mk = (...h) => new Function('LANG', 't', 'document', 'localStorage', '$', 'escH', 'icoWrap', 'coinImg', 'ccyIco', tvBlock + '\nreturn {TV, tvRender};')(
    'pl', k => k, { documentElement: { dataset: { theme: 'dark' } } }, { getItem() { return null; }, setItem() {} }, s => s === '#tv-chart' ? el : null, v96cEsc, ...h);
  mk(H.icoWrap, H.coinImg, H.ccyIco).tvRender('chart');
  assert.ok(el.innerHTML.includes('data-tv-sym="BITSTAMP:BTCUSD" aria-pressed="true"><span class="icos"><img class="ico sm" src="img/krypto/btc.svg"'), 'BTC/USD: logo bitcoina');
  assert.ok(el.innerHTML.includes('data-tv-sym="BITSTAMP:ETHUSD" aria-pressed="false"><span class="icos"><img class="ico sm" src="img/krypto/eth.svg"'), 'ETH/USD: logo etheru');
  assert.ok(el.innerHTML.includes('src="img/flagi/us.svg"') && el.innerHTML.includes('</span>BTC/USD</button>') && el.innerHTML.includes('</span>ETH/USD</button>'), 'znak dolara i nazwa pary');
  mk(undefined, undefined, undefined).tvRender('chart');
  assert.ok(el.innerHTML.includes('aria-pressed="true">BTC/USD</button>'), 'bez pomocników — tekst jak dawniej');
});

// v96-pages: strony z menu (Przepływy, Sektory, Aktywa) z flagami i logami, trzy kolory, aktualność bez nazw dostawców; flagi języków
const pgEnv = (over = {}) => {
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('\nfunction fundIco(', h0);
  const p0 = html.indexOf('function gActive(){'), p1 = html.indexOf('\n/* v35: widoki silnika z plików', p0);
  assert.ok(h0 > 0 && h1 > h0 && p0 > 0 && p1 > p0, 'bloki pomocników v96 i stron z menu');
  const src = html.slice(h0, html.indexOf('\n', h1 + 1)) + '\n' + html.slice(p0, p1) +
    '\nreturn {pgEdges, pgNodes, pgIco, pgCtyRow, pgAsIco, renderFlows, renderAssets, renderSectorsPage, flagCode};';
  const el = {innerHTML: ''};
  const E = Object.assign({
    escH: s => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'),
    ISO32: {DEU: 'DE', FRA: 'FR', GBR: 'GB', JPN: 'JP', KOR: 'KR', USA: 'US'}, COIN_LOGO: {},
    $: () => el, t: (k, o) => k + (o ? JSON.stringify(o) : ''), st: {mode: 'global', period: '24H'}, gst: {period: '1M'},
    GREG: [{id: 'eur', mcap: 100, iso: ['DEU', 'FRA', 'GBR']}, {id: 'jpn', mcap: 50, iso: ['JPN', 'KOR']}, {id: 'usa', mcap: 200, iso: ['USA']}, {id: 'rus', mcap: 9, iso: ['RUS']}],
    GDATA: {'1M': {eur: [-5, -1, true], jpn: [3, 2, true], usa: [0, 0, true], rus: [0, 0, false], crypto: [1, .5, true]}},
    GEDGE: [{f: 'eur', t: 'jpn', a: 3, ev: 'proxy'}], GCEDGE: [{f: 'usa', t: 'crypto', a: .5, ev: 'proxy'}],
    ETF: {data: {assets: {btc: {m: 1200, sym: 'BTC'}}}}, ETF_SYMS: ['btc', 'eth'],
    EDGES: [{f: 'btc', t: 'exch', a: 415, k: 'out', ev: 'direct'}, {f: 'stab', t: 'defi', a: 512, k: 'in', ev: 'onchain'}],
    NODES: [{id: 'btc', ev: 'proxy'}, {id: 'exch', ev: 'unc'}, {id: 'stab', ev: 'onchain'}, {id: 'defi', ev: 'proxy'}],
    DATA: {'24H': {btc: [1840, 8.4], exch: [-520, -2.1], stab: [0, 0], defi: [240, 1.8]}},
    eAmt: e => e.a, nName: id => 'N:' + id, chip: k => '[' + k + ']', gfmt: v => v.toFixed(1) + ' B', nfmt: (v, d = 0) => Number(v).toFixed(d), CMC: undefined, fInt: v => (v > 0 ? '+' : '') + v,
    iconURL: id => 'data:image/png;base64,' + id, LOCALE: {pl: 'pl-PL'}, LANG: 'pl',
    GLIVE: {}, GKPI: null, gDxy: () => null, gDaily: () => null, gStabDelta: () => null, gAgeNote: d => d ? ' ·age(' + d + ')' : '',
    KDEF: [{id: 'mcap'}, {id: 'dom'}, {id: 'stab'}, {id: 'vol'}, {id: 'tvl'}, {id: 'alt'}],
    KV_SAMPLE: {mcap: [2.43, 'u.t', 2.31, 1], dom: [54.2, '%', .38, 1], stab: [162.7, 'u.b', 1.24, 1], vol: [98.4, 'u.b', 6.2, 1], tvl: [88.4, 'u.b', 1.85, 1], alt: [1.11, 'u.t', 3.4, 2]},
    kpiVals: () => null, isLive: () => false, liveWhen: () => 'WHEN', engDate: s => 'D(' + s + ')',
  }, over);
  const names = Object.keys(E);
  const f = new Function(...names, src)(...names.map(k => E[k]));
  return {f, el, E};
};

test('v96-pages: Przepływy — flagi obu końców (GLOBAL), loga grup (CRYPTO), nagłówki i kwoty w kolorze kierunku', () => {
  const g = pgEnv();
  g.f.renderFlows();
  const h = g.el.innerHTML;
  assert.ok(h.includes('<h2 class="pos">▲ rail.in.g</h2>') && h.includes('<h2 class="neg">▼ rail.out.g</h2>'), 'nagłówki zielony / czerwony');
  const rows = h.split('<tr>').slice(2);
  const eur = rows.find(r => r.includes('g.n.eur'));
  assert.ok(eur && eur.includes('flagi/eu.svg') && eur.includes('flagi/gb.svg') && eur.includes('flagi/jp.svg') && eur.includes('flagi/kr.svg'), 'flagi obu końców: Europa → Japonia i Korea');
  assert.ok(eur.includes('<span class="cell pos"><b>+3.0 B</b>'), 'napływ zielony z „+”');
  const etf = rows.find(r => r.includes('ETF BTC'));
  assert.ok(etf && etf.includes('glify/etf.svg') && (etf.match(/krypto\/btc\.svg/g) || []).length === 2, 'ETF BTC: glif ETF + logo BTC; „Krypto” — logo BTC');
  const us = rows.find(r => r.includes('g.n.usa'));
  assert.ok(us && us.includes('flagi/us.svg'), 'USA → Krypto z flagą');
  assert.ok(h.includes('class="amt in pos">+') && h.includes('class="amt out neg">−5.0 B'), 'listy: napływy zielone z „+”, odpływy czerwone z „−”');
  assert.ok(!h.includes('g.n.rus'), 'region bez danych i region z zerem nie trafiają do list największych');
  for (const r of rows) assert.ok(/<img |<span class="iss/.test(r.split('<td>')[1] || '') , 'każdy wiersz ma ikonę przy „Z”');
  // CRYPTO: loga grup, odpływ do giełd czerwony z „−”, bez podwójnego znaku
  const c = pgEnv({st: {mode: 'crypto', period: '24H'}});
  c.f.renderFlows();
  const k = c.el.innerHTML;
  assert.ok(k.includes('data-id="btc"') && k.includes('data-id="exch"') && k.includes('data-id="stab"') && k.includes('data-id="defi"'), 'loga grup krypto');
  assert.ok(k.includes('<span class="cell neg"><b>−415 u.m</b>') && k.includes('<span class="cell pos"><b>+512 u.m</b>'), 'kwota idzie za kierunkiem');
  assert.ok(!/\+\+|−\+|\+−/.test(k), 'bez „++1 840” ani „−+520”');
  assert.ok(k.includes('class="amt in pos">+1840 u.m') && k.includes('class="amt out neg">−520 u.m'));
});

test('v96-pages: Sektory — flagi regionu przed nazwą, kraje jako flagi (dwa kraje = dwie flagi), trzy kolory, loga grup krypto', () => {
  const g = pgEnv();
  g.f.renderSectorsPage();
  const h = g.el.innerHTML, rows = h.split('<div class="secrow">').slice(1);
  const row = id => rows.find(r => r.includes('g.n.' + id + '<'));
  const eur = row('eur'), jpn = row('jpn'), usa = row('usa'), rus = row('rus'), cr = row('crypto');
  const nameOf = r => r.slice(r.indexOf('<span class="sname">'), r.indexOf('<span class="sbar'));
  const subOf = r => r.slice(r.indexOf('<span class="ssub">'));
  assert.ok(nameOf(eur).includes('flagi/de.svg') && nameOf(eur).includes('flagi/fr.svg') && nameOf(eur).includes('flagi/gb.svg') && !nameOf(eur).includes('flagi/eu.svg'), 'flagi regionu przed nazwą — te same kraje co w wierszu');
  assert.equal((subOf(eur).match(/class="scty"/g) || []).length, 3, 'jedna flaga na kraj');
  assert.ok(subOf(eur).includes('flagi/de.svg') && subOf(eur).includes('flagi/fr.svg') && subOf(eur).includes('flagi/gb.svg') && !h.includes('DEU, FRA'));
  assert.equal((subOf(jpn).match(/<img /g) || []).length, 2, 'Japonia i Korea — dwie flagi');
  assert.ok(/title="[^"]+"/.test(subOf(jpn)), 'nazwa kraju w podpowiedzi');
  assert.ok(eur.includes('<span class="sval neg">−5.0 B</span>') && jpn.includes('<span class="sval pos">+3.0 B</span>'));
  assert.ok(usa.includes('<span class="sval ">0.0 B</span>') && usa.includes('width:0%'), 'dokładne zero — bez koloru i bez paska');
  assert.ok(rus.includes('<span class="sval na">—</span>') && rus.includes('class="sna">g.nodata<'), 'brak danych to szary „—” (v98.2), nie zero');
  assert.ok(nameOf(cr).includes('krypto/btc.svg') && subOf(cr).includes('pg.sub.crypto') && subOf(cr).includes('krypto/usdt.svg') && subOf(cr).includes('krypto/usdc.svg'));
  const p0 = html.indexOf('function pgNodes(){'), p1 = html.indexOf('\nconst pgFmt=', p0);
  assert.ok(p1 > p0 && !html.slice(p0, p1).includes("'BTC · ETH · stablecoiny'") && html.slice(p0, p1).includes("t('pg.sub.crypto')"), 'podpis krypto tłumaczony');
  const c = pgEnv({st: {mode: 'crypto', period: '24H'}});
  c.f.renderSectorsPage();
  const k = c.el.innerHTML;
  assert.ok(k.includes('data-id="btc"') && k.includes('data-id="exch"') && k.includes('<span class="sval pos">+1840 u.m</span>') && k.includes('<span class="sval neg">−520 u.m</span>'));
  assert.ok(!/\+\+|−\+/.test(k) && k.includes('<span class="sval ">0 u.m</span>'), 'CRYPTO: bez „++”, zero bez koloru');
});

test('v96-pages: Aktywa — kolumna „Aktualność” (częstotliwość i dzień, bez nazw dostawców), flagi i loga, trzy kolory', () => {
  const PROV = ['Twelve Data', 'Finnhub', 'OECD', 'EBC', 'ECB', 'US Treasury', 'Bundesbank', 'CoinGecko', 'DefiLlama', 'CoinPaprika', 'CoinMarketCap'];
  const g = pgEnv({
    GLIVE: {fx: {now: {date: '2026-09-24'}}, irlt: {USA: [['2026-08', 4.1]], DEU: [['2026-08', 2.6]], JPN: [['2026-08', 1.6]]}, stab: [{date: 1790000000}]},
    GKPI: [{k: 'g.k.cry', v: 3900, d: 0, fresh: '2026-09-25'}],
    gDxy: () => [98.1, -0.4], gDaily: (s, p) => s === 'UST' ? {v: 4.12, d: .01, date: '2026-09-24'} : null, gStabDelta: () => [1.2, 0.8, 300],
  });
  g.E.GLIVE.ust = 'UST';
  g.f.renderAssets();
  const h = g.el.innerHTML;
  assert.ok(h.includes('<th>pg.fresh</th>') && !h.includes('d.source') && h.includes('pg.assets.dv'), 'kolumna „Aktualność”, nowy opis strony');
  for (const p of PROV) assert.ok(!h.includes(p), 'bez nazwy dostawcy: ' + p);
  const a0 = html.indexOf('function renderAssets(){'), a1 = html.indexOf('\nfunction renderSectorsPage(', a0), body = html.slice(a0, a1);
  for (const p of PROV) assert.ok(!body.includes("'" + p), 'kod strony Aktywa nie wpisuje dostawcy: ' + p);
  const row = k => h.split('<tr>').find(r => r.includes('<b>' + k + '</b>')) || '';
  assert.ok(row('as.us10').includes('flagi/us.svg') && row('as.us10').includes('pg.daily · 2026-09-24 ·age(2026-09-24)'), 'USA: flaga, dziennie, dzień i wiek');
  assert.ok(row('as.de10').includes('flagi/de.svg') && row('as.de10').includes('pg.monthly · 2026-08'), 'Niemcy: miesięcznie z okresem');
  assert.ok(row('as.jp10').includes('flagi/jp.svg') && row('as.eq').includes('glify/globe.svg'));
  assert.ok(row('as.fx').includes('flagi/us.svg') && row('as.fx').includes('USD<i>$</i>') && row('as.fx').includes('<span class="cell neg">▼ −0.40%</span>'), 'dolar: flaga i znak $, spadek czerwony');
  assert.ok(row('as.cry').includes('krypto/btc.svg') && row('as.cry').includes('krypto/eth.svg') && row('as.cry').includes('3900.0 B') && row('as.cry').includes('<span class="cell ">0.00%</span>'), 'krypto: loga BTC+ETH, liczba jak na kafelku, zero bez koloru');
  assert.ok(row('as.stab').includes('krypto/usdt.svg') && row('as.stab').includes('krypto/usdc.svg') && row('as.stab').includes('<span class="cell pos">▲ +0.80%</span>'));
  // CRYPTO: plik rynku krypto bez CoinPaprika — brakujące kafelki to „—”, nie liczby przykładowe
  const c = pgEnv({st: {mode: 'crypto', period: '24H'}, kpiVals: () => ({mcap: {val: 2.4, unit: 'u.t', dec: 1, d: -1.5, at: '2026-09-25T10:00:00Z'}, dom: {val: 57.1, unit: '%', dec: 1, d: .2}})});
  c.f.renderAssets();
  const k = c.el.innerHTML, rk = id => k.split('<tr>').find(r => r.includes('<b>kpi.' + id + '</b>')) || '';
  assert.ok(rk('mcap').includes('D(2026-09-25T10:00:00Z)') && rk('mcap').includes('krypto/btc.svg') && rk('mcap').includes('<span class="cell neg">▼ −1.50%</span>'));
  assert.ok(rk('dom').includes('▲ +0.20 u.pp') && rk('dom').includes('krypto/btc.svg'), 'dominacja w punktach procentowych');
  assert.ok(rk('tvl').includes('— · eng.gap') && rk('tvl').includes('data-id="defi"') && !k.includes('88.4'), 'brak ≠ liczba przykładowa');
  assert.ok(rk('stab').includes('krypto/usdt.svg') && rk('alt').includes('krypto/sol.svg') && rk('vol').includes('data-id="exch"'));
  for (const p of PROV) assert.ok(!k.includes(p), 'CRYPTO bez nazwy dostawcy: ' + p);
  const s = pgEnv({st: {mode: 'crypto', period: '24H'}});
  s.f.renderAssets();
  assert.ok(s.el.innerHTML.includes('badge') && s.el.innerHTML.includes('<span class="cell pos">▲ +2.31%</span>'), 'bez danych — makieta z oznaczeniem');
  const a = 'const EXTRA91=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.equal(D.pl['pg.fresh'], 'Aktualność');
  assert.ok(D.en['pg.fresh'] && !D.pl['pg.assets.dv'].includes('skąd pochodzi') && D.en['pg.assets.dv'] && D.pl['pg.sub.crypto'] && D.en['pg.sub.crypto'].includes('stablecoins'));
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort());
});

test('v96-pages: Ustawienia → Język — flaga przy każdym języku i na przycisku', () => {
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('\nfunction fundIco(', h0);
  const l0 = html.indexOf('const LANG_NAMES='), l1 = html.indexOf("\ndropdown($('#dd-lang')", l0);
  assert.ok(l0 > 0 && l1 > l0);
  const F = new Function('escH', 'ISO32', 'COIN_LOGO', html.slice(h0, html.indexOf('\n', h1 + 1)) + '\n' + html.slice(l0, l1) + '\nreturn {LANG_NAMES, LANG_FLAG, langIcon, FLAGS_OK};')(s => String(s), {}, {});
  const want = {pl: 'pl', en: 'gb', de: 'de', es: 'es', fr: 'fr', it: 'it', pt: 'pt', ru: 'ru', zh: 'cn', ja: 'jp'};
  for (const l of Object.keys(F.LANG_NAMES)) {
    assert.equal(F.langIcon(l), 'img/flagi/' + want[l] + '.svg', l);
    assert.ok(F.FLAGS_OK.has(want[l]), 'plik flagi ' + want[l]);
  }
  assert.ok(html.includes("items:Object.keys(LANG_NAMES).map(v=>({v,raw:LANG_NAMES[v],icon:()=>langIcon(v)}))"), 'lista języków z ikoną');
  assert.ok(html.includes("(cur&&cur.icon?`<img src=\"${cur.icon()}\" alt=\"\">`:'')"), 'przycisk pokazuje flagę wybranego języka');
  assert.ok(html.includes('#dd-lang img{border-radius:50%;') && html.includes('#page-sectors .icos .logo-img{width:18px;height:18px}'), 'okrągłe flagi; loga w tabelach 18 px');
  assert.ok(html.includes('#dd-lang .dd-btn{justify-content:flex-start}') && html.includes('#dd-lang .dd-btn .car{margin-left:auto}'), 'flaga i nazwa języka razem przy lewej krawędzi przycisku');
  assert.ok(!/(^|[\s,}])\.page td \.cell>\.icos|(^|[\s,}])\.page \.icos \.logo-img/.test(html), 'reguły ikon tylko dla trzech stron z menu (nie Źródła/Metodologia)');
});

test('v96-pages: po przeglądzie — dni z serwerów zewnętrznych zabezpieczone (escH), akcje z dniem, plik krypto „co 20 min”, liczby po polsku', () => {
  const X = '<img src=x onerror=alert(1)>';
  const g = pgEnv({
    GLIVE: {fx: {now: {date: X}}, irlt: {USA: [['<b>2026-08</b>', 4.1]], DEU: [['2026-08', 2.6]], JPN: [['2026-08', 1.6]]}, stab: [{date: 1790000000}], buba: 'BUBA'},
    GKPI: [{k: 'g.k.cry', v: 3900, d: 1.234, fresh: '<i>c</i>'}, {k: 'g.k.eq', v: 1, fresh: '2026-09-24'}],
    gDxy: () => [98.1, -0.4], gDaily: (s) => s === 'BUBA' ? {v: 2.61, d: 0, date: '"><svg onload=alert(2)>'} : null, gStabDelta: () => null,
    gAgeNote: d => /^\d{4}-\d{2}/.test(d || '') ? ' ·wiek' : '',   // prawdziwy gAgeNote nie powtarza wejścia
    nfmt: (v, d = 0) => Number(v).toFixed(d).replace('.', ','),
    CMC: {data: {total_mcap: 3.9e12}},
  });
  g.f.renderAssets();
  const h = g.el.innerHTML, row = k => h.split('<tr>').find(r => r.includes('<b>' + k + '</b>')) || '';
  for (const bad of ['<img src=x', '<b>2026-08', '<svg', '<i>c</i>']) assert.ok(!h.includes(bad), 'surowy znacznik z danych: ' + bad);
  assert.ok(row('as.fx').includes('pg.daily · &lt;img src=x onerror=alert(1)&gt;'), 'dzień kursu dolara zabezpieczony');
  assert.ok(row('as.us10').includes('&lt;b&gt;2026-08&lt;/b&gt;') && row('as.de10').includes('&quot;&gt;&lt;svg'), 'okres OECD i dzień z Niemiec zabezpieczone');
  assert.ok(row('as.cry').includes('pg.20m · &lt;i&gt;c&lt;/i&gt;') && !row('as.cry').includes('pg.live'), 'plik rynku krypto: „co 20 min”, nie „na bieżąco”');
  assert.ok(row('as.eq').includes('pg.monthly · 2026-09-24 ·wiek · g.q.cov 3/4'), 'akcje: częstotliwość, dzień i wiek jak na kafelku');
  assert.ok(row('as.fx').includes('<span class="cell">98,10</span>') && row('as.fx').includes('▼ −0,40%') && row('as.de10').includes('2,61%') && row('as.cry').includes('▲ +1,23%'), 'przecinek dziesiętny po polsku');
  const lv = pgEnv({GKPI: [{k: 'g.k.cry', v: 3900, d: 0, fresh: '2026-09-25'}]});
  lv.f.renderAssets();
  assert.ok(lv.el.innerHTML.includes('pg.live · 2026-09-25'), 'bez pliku — kurs na żywo „na bieżąco”');
  const c = pgEnv({st: {mode: 'crypto', period: '24H'}, isLive: () => true, liveWhen: () => '<b>w</b>', gAgeNote: () => '',
    kpiVals: () => ({mcap: {val: 2.4, unit: 'u.t', dec: 1, d: -1.5, at: '<script>'}, vol: {val: 98, unit: 'u.b', dec: 0, d: 2}})});
  c.f.renderAssets();
  const k = c.el.innerHTML;
  assert.ok(!k.includes('<script>') && !k.includes('<b>w</b>') && k.includes('pg.20m · D(&lt;script&gt;)') && k.includes('pg.live · &lt;b&gt;w&lt;/b&gt;'), 'CRYPTO: czas z pliku i czas na żywo zabezpieczone');
  const a0 = html.indexOf('function renderAssets(){'), a1 = html.indexOf('\nfunction renderSectorsPage(', a0), body = html.slice(a0, a1);
  assert.ok(body.includes("const when=(fr,day)=>fr+(day?' · '+escH(day)+gAgeNote(day):'');") && !/toFixed\(/.test(body), 'kod: dzień przez escH, liczby przez nfmt');
  const a = 'const EXTRA91=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.equal(D.pl['pg.20m'], 'co 20 min'); assert.equal(D.en['pg.20m'], 'every 20 min');
});

test('v96-pages: po przeglądzie — Sektory: flagi przy nazwie = kraje z wiersza (Chiny bez Hongkongu, Azja Płd.-Wsch. = Indonezja); „0 mln” bez zieleni', () => {
  const g = pgEnv({
    ISO32: {DEU: 'DE', FRA: 'FR', GBR: 'GB', ITA: 'IT', ESP: 'ES', JPN: 'JP', KOR: 'KR', CHN: 'CN', IDN: 'ID', USA: 'US'},
    GREG: [{id: 'eur', mcap: 100, iso: ['DEU', 'FRA', 'GBR', 'ITA', 'ESP']}, {id: 'chn', mcap: 80, iso: ['CHN']}, {id: 'asean', mcap: 20, iso: ['IDN']}, {id: 'jpn', mcap: 50, iso: ['JPN', 'KOR']}],
    GDATA: {'1M': {eur: [-5, -1, true], chn: [2, 1, true], asean: [1, 1, true], jpn: [3, 2, true], crypto: [1, .5, true]}},
  });
  g.f.renderSectorsPage();
  const rows = g.el.innerHTML.split('<div class="secrow">').slice(1);
  const flags = s => (s.match(/flagi\/([a-z]{2})\.svg/g) || []).map(x => x.slice(6, 8));
  for (const id of ['eur', 'chn', 'asean', 'jpn']) {
    const r = rows.find(x => x.includes('g.n.' + id + '<'));
    const nm = flags(r.slice(r.indexOf('<span class="sname">'), r.indexOf('<span class="sbar'))), sub = flags(r.slice(r.indexOf('<span class="ssub">')));
    assert.ok(nm.length && nm.every(f => sub.includes(f)), id + ': każda flaga przy nazwie jest też w wierszu krajów');
    assert.deepEqual(nm, sub.slice(0, 3), id + ': te same pierwsze kraje');
  }
  const chn = rows.find(x => x.includes('g.n.chn<')), as = rows.find(x => x.includes('g.n.asean<')), eur = rows.find(x => x.includes('g.n.eur<'));
  assert.ok(!chn.includes('flagi/hk.svg') && !as.includes('flagi/sg.svg') && !as.includes('flagi/th.svg'), 'bez flag krajów spoza wiersza');
  assert.ok(eur.includes('<i class="more">+2</i>'), 'Europa: trzy flagi i „+2”, pełna lista w wierszu');
  // CRYPTO: |v| < 0,5 mln pokazuje „0 mln” — bez zieleni/czerwieni, bez paska i poza listami największych
  const E = {st: {mode: 'crypto', period: '24H'}, DATA: {'24H': {btc: [1840, 8.4], exch: [-0.4, -2.1], stab: [0.3, 0], defi: [240, 1.8]}},
    EDGES: [{f: 'btc', t: 'exch', a: 0.2, k: 'out', ev: 'direct'}, {f: 'stab', t: 'defi', a: 512, k: 'in', ev: 'onchain'}]};
  const c = pgEnv(E);
  c.f.renderSectorsPage();
  const k = c.el.innerHTML, rk = id => k.split('<div class="secrow">').find(x => x.includes('data-id="' + id + '"')) || '';
  assert.ok(rk('stab').includes('<span class="sval ">0 u.m</span>') && rk('stab').includes('width:0%'), '+0,3 mln → „0 mln” bez koloru');
  assert.ok(rk('exch').includes('<span class="sval ">0 u.m</span>') && !k.includes('−0 u.m') && !k.includes('+0 u.m'), '−0,4 mln → „0 mln” bez koloru i znaku');
  const f = pgEnv(E);
  f.f.renderFlows();
  const fl = f.el.innerHTML, tr = fl.split('<tr>').slice(2);
  assert.ok(tr.find(r => r.includes('N:exch')).includes('<span class="cell "><b>0 u.m</b>'), 'korytarz 0,2 mln — bez koloru i znaku');
  const lists = fl.slice(0, fl.indexOf('<table>'));
  assert.ok(!lists.includes('data-id="stab"') && !lists.includes('data-id="exch"') && lists.includes('data-id="btc"'), 'zaokrąglone zero nie trafia do list największych');
});

/* ---------- v96-trendy: dwa widoki, ikony, kolory według stanu, bez nazw dostawców ---------- */
const trdV96 = (() => {
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */');
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const escH = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  /* prawdziwe funkcje ikon z bloku v96 */
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('\nfunction fundIco(', h0);
  const ICO = new Function('escH', 'ISO32', 'COIN_LOGO', html.slice(h0, html.indexOf('\n', h1 + 1)) + '\nreturn {flagImg,glyphImg,coinImg,issBadge,issuerOf,icoWrap};')(escH, {}, {});
  const make = (st, ico, tt, el0) => {
    const el = el0 || {innerHTML: '', querySelectorAll() { return []; }, querySelector() { return null; }};
    const names = ['$', 't', 'st', 'srvJSON', 'escH', 'etfCls', 'gAgeNote', 'fInt', 'sg', 'nfmt', 'fPct', 'zagSes', 'engDate', 'LANG', 'LOCALE', 'I18N'];
    const vals = [() => el, tt || T, st, () => Promise.resolve(null), escH, v => v > 0 ? 'pos' : v < 0 ? 'neg' : '', d => '', v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v),
      v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d = 0) => v.toFixed(d), (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%', n => 'ses', s => s, 'pl', {pl: 'pl-PL'}, {pl: {}, en: {}}];
    if (ico) { names.push('flagImg', 'glyphImg', 'coinImg', 'issBadge', 'issuerOf', 'icoWrap'); vals.push(ICO.flagImg, ICO.glyphImg, ICO.coinImg, ICO.issBadge, ICO.issuerOf, ICO.icoWrap); }
    const f = new Function(...names, html.slice(b0, b1) + '\nreturn {TRD, trdApply, renderTrendy, trdTone, trdSt, trdCard, trdPx, feRegion};')(...vals);
    f.el = el; return f;
  };
  const row = o => Object.assign({g: 'eq', m: 'flow', sz: 5, cur: 'USD', date: '2026-09-24', age: 1, n: 8, lc: false, s: 1, sg: 1, x: false}, o);
  const data = {at: '2026-09-25T10:00:00Z', f: [
    row({id: 'fe_us', g: 'fe', st: 'in_rev', w: 65115.8, base: -19469.4, d: 2, du: 84585.2, iss: 'both'}),
    row({id: 'fe_tech', g: 'fe', st: 'in_new', w: 552.6, base: -173, d: 1.7, du: 725.7, iss: 'ssga'}),
    row({id: 'fe_gold', g: 'fe', st: 'in_stop', w: -229.5, base: 1423, d: -1.5, du: -1652.8, iss: 'both'}),
    row({id: 'fe_jpn', g: 'fe', st: 'mixed', w: -58.4, base: 69.5, d: -0.4, du: -127.9, iss: 'ishares'}),
    row({id: 'fe_em', g: 'fe', st: 'none', w: 0, base: 343, d: 0, du: -343, iss: 'both'}),
    row({id: 'hk', st: 'in_dir', w: 24306.46, wu: 3098.1, d: 1.73, base: 10106.06, du: 1810, cur: 'HKD', lc: true, n: 4}),
    row({id: 'jp_eq', st: 'out_new', sz: 1, w: -1522.8, wu: -9589.2, d: -2.78, base: 146.1, du: -10509.4, cur: 'JPY'}),
    row({id: 'in_eq', st: 'short', w: 402.3, n: 2}),
    row({id: 'tr_bd', g: 'bd', st: 'stale', sz: 1, w: -116.9, n: 8}),
    row({id: 'th', g: 'bd', st: 'gap', w: 495, cur: 'THB', wu: 14.8}),
    row({id: 'mx', g: 'bd', m: 'stock', st: 'out_down', w: -13103.56, wu: -765.8, d: -1.24, du: -810.7, cur: 'MXN'}),
    row({id: 'etf_btc', g: 'cr', st: 'short', w: 2684.35, n: 3}), row({id: 'etf_eth', g: 'cr', st: 'short', w: -746.7, n: 3}),
    row({id: 'etf_sol', g: 'cr', st: 'stale', w: -9999, n: 3}), row({id: 'etf_xrp', g: 'cr', st: 'in_up', w: 100, base: 10, d: 3, du: 999999}),
    row({id: 'cm_btc', g: 'cr', m: 'exch', sz: 7, st: 'out_dir', w: -41054.24, wu: -3495.5, d: -2.98, cur: 'BTC', lc: true, n: 4}),
    row({id: 'stab', g: 'cr', m: 'supply', sz: 7, st: 'in_flat', w: 1457.27, base: 641.07, d: 1, du: 816.2}),
    row({id: 'cf_usd', g: 'pos', m: 'pos', sz: 1, st: 'out_new', w: -11095, cur: 'CT', base: 103.5}),
    row({id: 'cf_eur', g: 'pos', m: 'pos', sz: 1, st: 'out_stop', w: 5129, cur: 'CT', base: 6828.75}),
    row({id: 'cf_spx', g: 'pos', m: 'pos', sz: 1, st: 'in_rev', w: 47961, cur: 'CT'}),
    row({id: 'cf_btc', g: 'pos', m: 'pos', sz: 1, st: 'in_new', w: 1538, cur: 'CT', base: -210}),
    row({id: 'cf_eth', g: 'pos', m: 'pos', sz: 1, st: 'none', w: -436, cur: 'CT', base: -822}),
    row({id: 'cs_gold', g: 'pos', m: 'pos', sz: 1, st: 'none', w: -1856, cur: 'CT'}),
    row({id: 'cs_wti', g: 'pos', m: 'pos', sz: 1, st: 'out_rev', w: -5452, cur: 'CT'})],
    p: [{id: 'SPY', g: 'eq', date: '2026-09-24', w: 0.6, pr: -0.84, typ: 1.9, st: 'flat'}, {id: 'VGK', g: 'eq', date: '2026-09-24', w: -1.45, pr: -3.1, typ: 2.2, st: 'dn_cont'},
        {id: 'ILF', g: 'eq', date: '2026-09-24', w: 1.2, pr: -5, typ: 3.2, st: 'dn_fade'}, {id: 'EWJ', g: 'eq', date: '2026-09-24', w: -2.14, pr: 3.3, typ: 2.6, st: 'up_fade'},
        {id: 'fp_gold', g: 'fp', sym: 'IAU', date: '2026-09-24', w: -2.34, pr: -2.11, typ: 3.67, st: 'dn_new'}, {id: 'fp_tech', g: 'fp', sym: 'XLK', date: '2026-09-24', w: 3.56, pr: 2.44, typ: 3.97, st: 'up_new'},
        {id: 'BTC', g: 'cr', date: '2026-09-25', w: 4.89, pr: 2.01, st: 'up_new'}, {id: 'TRX', g: 'cr', date: '2026-09-25', w: -0.67, pr: 1.16, st: 'flat'}],
    b: [{id: 'ob', k: 1, n: 2, weeks: 2, from: '2026-08-24', to: '2026-09-07', ci: [9.5, 90.5]}, {id: 'fe', k: 470, n: 805, weeks: 56, from: '2025-08-18', to: '2026-09-14', ci: [45.3, 70.3]},
        {id: 'px', k: 138, n: 288, weeks: 31, from: '2026-02-09', to: '2026-09-14', ci: [31.6, 64.7]}]};
  const card = (h, lab) => { const i = h.indexOf('<span>' + lab + '</span>'); if (i < 0) return ''; const a = h.lastIndexOf('<div class="etfk', i); return h.slice(a, h.indexOf('</div>', i) + 6); };
  return {make, data, card, ICO};
})();

test('v96-trendy: przełącznik „Trendy global / Trendy krypto” — .seg w nagłówku, zapamiętany wybór, każdy widok tylko ze swoimi seriami', () => {
  const {make, data} = trdV96;
  assert.ok(html.includes("const st={mode:'crypto',trdv:'global',"), 'domyślnie global');
  assert.ok(html.includes("$('#tab-trendy').addEventListener('click',()=>setMode('trendy'));\ntry{const v=localStorage.getItem('cfai.trd.view');if(v==='crypto'||v==='global')st.trdv=v;}catch(e){}$('#trendy').addEventListener('click',e=>{const b=e.target.closest('#trd-view button[data-v]');"), 'jeden słuchacz przy zakładkach; wybór z przeglądarki wczytany poza blokiem (test bez localStorage)');
  assert.ok(html.includes("try{localStorage.setItem('cfai.trd.view',v);}catch(_){}renderTrendy();"));
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  assert.ok(!blk.includes('class="tabs') && !blk.includes('localStorage'), 'nie druga grupa .tabs (strzałki zakładek); blok bez localStorage');
  const st = {mode: 'trendy'}, f = make(st);
  f.renderTrendy();
  assert.ok(f.el.innerHTML.includes('<div class="seg trd-seg" id="trd-view" role="group" aria-label="trd.v.aria"><button type="button" data-v="global" aria-pressed="true">trd.v.global</button><button type="button" data-v="crypto" aria-pressed="false">trd.v.crypto</button></div>') && f.el.innerHTML.includes('trd.nodata'), 'przełącznik także bez pliku');
  f.trdApply(data); const g = f.el.innerHTML;
  for (const id of ['fe_us', 'fe_tech', 'hk', 'jp_eq', 'cf_usd', 'cf_spx', 'cs_gold']) assert.ok(g.includes('<span>trd.s.' + id + '</span>'), 'global: ' + id);
  for (const id of ['etf_btc', 'cm_btc', 'stab', 'cf_btc', 'cf_eth']) assert.ok(!g.includes('trd.s.' + id), 'global bez krypto: ' + id);
  assert.ok(g.includes('<span>trd.px.SPY</span>') && g.includes('<span>trd.s.fe_gold</span>') && !g.includes('<span>BTC</span>') && !g.includes('trd.x.cr') && !g.includes('trd.kc.'), 'global: ceny akcji i funduszy, bez cen krypto i kafli krypto');
  assert.ok(g.includes('trd.v.gi') && g.includes('<h1>trd.h1</h1>') && g.includes('<span>trd.b.fe</span>') && g.includes('trd.k.in</span>'));
  const kin = g.slice(g.indexOf('trd.k.in</span>'), g.indexOf('trd.k.out</span>'));
  assert.ok(kin.includes('trd.s.fe_us') && !kin.includes('etf_xrp'), 'kafle świata bez funduszy krypto, nawet przy pełnej historii');
  st.trdv = 'crypto'; f.renderTrendy(); const c = f.el.innerHTML;
  assert.ok(c.includes('data-v="global" aria-pressed="false"') && c.includes('data-v="crypto" aria-pressed="true"') && c.includes('<h1>trd.h1c</h1>') && c.includes('trd.v.ci'));
  for (const id of ['etf_btc', 'etf_eth', 'cm_btc', 'stab', 'cf_btc', 'cf_eth']) assert.ok(c.includes('<span>trd.s.' + id + '</span>'), 'krypto: ' + id);
  for (const id of ['fe_us', 'hk', 'jp_eq', 'cf_usd', 'cf_spx', 'cs_gold']) assert.ok(!c.includes('trd.s.' + id), 'krypto bez świata: ' + id);
  assert.ok(c.includes('<span>BTC</span>') && !c.includes('trd.px.SPY') && !c.includes('trd.b.fe') && c.includes('trd.b.nocr') && c.includes('id="trd-method"') && c.includes('id="trd-rest-c"') && !c.includes('trd-rest-p"'), 'ceny krypto, brak wyników świata, własny blok „pozostałe”');
  assert.ok(c.indexOf('<span>trd.s.etf_btc</span>') < c.indexOf('id="trd-rest-c"'), 'fundusze ETF krypto z krótką historią na wierzchu, nie w zwiniętym bloku');
  assert.ok(c.includes('trd.kc.in</span></div><div class="k-val pos">+2.68 trd.u.b USD</div>') && c.includes('trd.kc.out</span></div><div class="k-val neg">−747 trd.u.m USD</div>'), 'kafle krypto: największy napływ i odpływ ETF (bez „brak nowych danych”)');
  assert.ok(c.includes('title="trd.sn.short{&quot;n&quot;:3}"') && !c.includes('trd.k.in<') && !c.includes('trd.k.out<'), 'krótka historia — stan widać, tytuł nie mówi o „zwykłym poziomie”');
  assert.ok(c.includes('trd.kc.pup</span></div><div class="k-val pos">+4.89%</div>') && c.includes('trd.kc.pdn</span></div><div class="k-val neu">−0.67%</div>') && c.includes('<b class="neu">−0.67%') && c.includes('trd.kc.exch</span></div><div class="k-val neg">−41054 BTC</div>'));
  st.trdv = 'zzz'; f.renderTrendy(); assert.ok(f.el.innerHTML.includes('<h1>trd.h1</h1>'), 'nieznana wartość = global');
});

test('v96-trendy: ikony na każdej karcie, cenie, kaflu i wyniku — flagi, loga monet, glify surowców, znaczki wydawców; tylko obrazki strony', () => {
  const {make, data, card} = trdV96;
  const st = {mode: 'trendy'}, f = make(st, true);
  f.trdApply(data); const g = f.el.innerHTML;
  const hk = card(g, 'trd.s.hk');
  assert.ok(hk.startsWith('<div class="etfk trk"><span class="icos">') && hk.includes('flagi/hk.svg') && hk.includes('flagi/cn.svg') && hk.includes('</span><span>trd.s.hk</span>'), 'Hongkong (inwestorzy z Chin) — dwie flagi przed nazwą: ' + hk.slice(0, 300));
  const tech = card(g, 'trd.s.fe_tech');
  assert.ok(tech.includes('flagi/us.svg') && tech.includes('>SP</span>') && !tech.includes('>iS</span>') && !tech.includes('trd.src'), 'sektor USA — flaga + znaczek SPDR zamiast linii źródła');
  const gold = card(g, 'trd.s.fe_gold');
  assert.ok(gold.includes('glify/gold.svg') && gold.includes('>SP</span>') && gold.includes('>iS</span>'), 'złoto — glif + dwaj wydawcy');
  assert.ok(card(g, 'trd.s.cf_usd').includes('flagi/us.svg') && card(g, 'trd.s.cf_eur').includes('flagi/eu.svg'), 'waluty — flagi');
  assert.ok(card(g, 'trd.s.cs_gold').includes('glify/gold.svg') && card(g, 'trd.s.cs_wti').includes('glify/oil.svg'), 'surowce — glify');
  const vgk = card(g, 'trd.px.VGK');
  assert.ok(vgk.includes('flagi/eu.svg') && vgk.includes('flagi/gb.svg') && vgk.includes('flagi/ch.svg') && vgk.includes('title="Vanguard"'), 'Europa (VGK) — UE, Wielka Brytania, Szwajcaria + Vanguard');
  assert.ok(card(g, 'trd.px.ILF').includes('<i class="more">+1</i>'), 'więcej krajów niż 3 — „+N”');
  const fpg = g.slice(g.indexOf('trd.x.fp')), fpc = card(fpg, 'trd.s.fe_gold');
  assert.ok(fpc.includes('glify/gold.svg') && fpc.includes('>iS</span>') && !fpc.includes('>SP</span>'), 'cena funduszu złota — wydawca z symbolu w pliku (IAU = iShares)');
  const ob = card(g, 'trd.b.ob');
  assert.ok(['in', 'tw', 'hk', 'br'].every(c => ob.includes('flagi/' + c + '.svg')) && !ob.includes('class="more"'), 'wynik dla krajów — cztery flagi');
  assert.ok(card(g, 'trd.b.px').includes('glify/globe.svg') && card(g, 'trd.b.fe').includes('glify/etf.svg'));
  const tiles = g.slice(g.indexOf('<section class="kpis gkpis">'), g.indexOf('</section>', g.indexOf('<section class="kpis gkpis">')));
  assert.equal((tiles.match(/<div class="k-head"><span class="icos">/g) || []).length, 6, 'każdy kafel z ikoną');
  assert.ok(g.includes('<button type="button" data-v="crypto" aria-pressed="false"><span class="icos"><img class="ico sm" src="img/krypto/btc.svg"'));
  st.trdv = 'crypto'; f.renderTrendy(); const c = f.el.innerHTML;
  const eb = card(c, 'trd.s.etf_btc');
  assert.ok(eb.includes('krypto/btc.svg') && eb.includes('flagi/us.svg'), 'ETF bitcoina — logo monety + flaga USA');
  assert.ok(card(c, 'trd.s.cm_btc').includes('krypto/btc.svg') && card(c, 'trd.s.stab').includes('krypto/usdt.svg') && card(c, 'trd.s.stab').includes('krypto/usdc.svg') && card(c, 'trd.s.cf_eth').includes('krypto/eth.svg'));
  assert.ok(card(c, 'BTC').includes('krypto/btc.svg') && card(c, 'TRX').includes('krypto/trx.svg'), 'ceny krypto — loga monet');
  const ct = c.slice(c.indexOf('<section class="kpis gkpis">'), c.indexOf('</section>', c.indexOf('<section class="kpis gkpis">')));
  assert.equal((ct.match(/<div class="k-head"><span class="icos">/g) || []).length, 6, 'kafle krypto — każdy z ikoną');
  for (const x of [g, c]) {
    const src = [...x.matchAll(/src="([^"]*)"/g)].map(m => m[1]);
    assert.ok(src.length > 20 && src.every(s => /^img\/(flagi|krypto|glify)\/[a-z0-9-]+\.svg$/.test(s)), 'tylko obrazki z folderu img/ strony: ' + src.filter(s => !/^img\//.test(s)).join(' '));
  }
  f.TRD.data = {at: 'x', p: [], f: [row2()]};
  function row2() { return {id: 'fe_jpn', g: 'fe', m: 'flow', sz: 5, cur: 'USD', date: '2026-09-24', st: 'out_up', w: -58.39, iss: 'ishares'}; }
  const reg = f.feRegion('jpn');
  assert.ok(reg.includes('flagi/jp.svg') && reg.includes('>iS</span>') && reg.includes('<b class="neg">'), 'opis regionu GLOBAL — flaga i znaczek wydawcy');
});

test('v96-trendy: kolory według stanu — napływ zielony, odpływ czerwony, osłabienie i brak kierunku żółte, bez oceny szare, zero bez koloru', () => {
  const {make, data, card} = trdV96;
  const st = {mode: 'trendy'}, f = make(st);
  const tone = (st0, w) => f.trdTone({st: st0, w: w === undefined ? 5 : w});
  for (const s of ['in_up', 'in_flat', 'in_rev', 'in_new', 'in_dir', 'up_cont', 'up_new', 'dn_fade']) assert.equal(tone(s), 'pos', s);
  for (const s of ['out_up', 'out_flat', 'out_rev', 'out_new', 'out_dir', 'up_fade', 'dn_new', 'dn_cont']) assert.equal(tone(s, -5), 'neg', s);
  for (const s of ['in_down', 'out_down', 'in_stop', 'out_stop', 'mixed', 'none', 'flat']) assert.equal(tone(s), 'neu', s);
  for (const s of ['gap', 'stale']) assert.equal(tone(s), '', s);
  assert.equal(tone('short', 5), ''); assert.equal(tone('short', -5), '', 'za mało historii — bez oceny, bez koloru (jak luka i brak nowych danych)');
  assert.equal(tone('in_up', 0), '', 'zero — bez zieleni i czerwieni'); assert.equal(f.trdTone({st: 'in_up', w: null}), '', 'brak — szary „—”');
  assert.equal(f.trdSt('△ napływ słabszy niż zwykle', 'neu'), '<i class="tg neu">△</i> napływ słabszy niż zwykle', 'znaczek stanu w kolorze stanu');
  assert.equal(f.trdSt('za mało <historii>', ''), 'za mało &lt;historii&gt;');
  f.trdApply(trdV96.data); const g = f.el.innerHTML;
  assert.ok(card(g, 'trd.s.fe_gold').includes('<b class="neu">−230 trd.u.m USD'), 'zwykle napływ, teraz bez kierunku — żółty');
  assert.ok(card(g, 'trd.s.fe_jpn').includes('<b class="neu">') && card(g, 'trd.s.mx').includes('<b class="neu">'), 'tydzień niejednolity i „słabiej niż zwykle” — żółte');
  assert.ok(card(g, 'trd.s.fe_em').includes('<b class="">0 trd.u.m USD') || card(g, 'trd.s.fe_em').includes('<b class="">'), 'zero — bez koloru');
  assert.ok(card(g, 'trd.s.tr_bd').includes('<b class="">') && card(g, 'trd.s.th').includes('<b class="">'), 'brak nowych danych / luka — szare');
  assert.ok(card(g, 'trd.s.in_eq').includes('<b class="">+402 trd.u.m USD') && card(g, 'trd.s.jp_eq').includes('<b class="neg">') && card(g, 'trd.s.cf_eur').includes('<b class="neu">'));
  assert.ok(card(g, 'trd.px.SPY').includes('<b class="neu">+0.60%') && card(g, 'trd.px.ILF').includes('<b class="pos">') && card(g, 'trd.px.EWJ').includes('<b class="neg">'), 'ceny: bez wyraźnego ruchu żółte');
  assert.ok(g.includes('trd.k.in</span></div><div class="k-val pos">') && g.includes('trd.k.out</span></div><div class="k-val neg">') && g.includes('trd.k.fade</span></div><div class="k-val neu">'), 'kafle: największy napływ zielony, odpływ czerwony, osłabienie żółte');
  assert.ok(g.includes('<span class="dlt chg">•</span><span class="ksrc" title="trd.sn.in_stop">'));
  assert.ok(g.includes('<i class="tdot pos"></i>trd.lg.pos') && g.includes('<i class="tdot neu"></i>trd.lg.neu') && g.includes('<i class="tdot"></i>trd.lg.na'), 'legenda kolorów');
  /* ze słownikiem: znaczek ▲ / △ w kolorze stanu, opis szary */
  const DP = {};   /* teksty pl ze wszystkich słowników TRENDÓW (EXTRA80…) */
  for (const m of html.matchAll(/const (EXTRA(?:8\d|9\d))=/g)) { const x = html.indexOf(m[0]); Object.assign(DP, JSON.parse(html.slice(x + m[0].length, html.indexOf(';\n', x))).pl || {}); }
  const f2 = make({mode: 'trendy'}, false, (k, o) => (DP[k] || k).replace(/\{(\w+)\}/g, (_, n) => o && o[n] !== undefined ? o[n] : ''));
  f2.trdApply(trdV96.data); const g2 = f2.el.innerHTML;
  assert.ok(g2.includes('<b class="neu">−230 mln USD<small><i class="tg neu">△</i> zwykle napływ'), 'złoto: żółty trójkąt');
  assert.ok(g2.includes('<small><i class="tg pos">▲</i> napływ po tygodniach odpływu</small>') && g2.includes('<i class="tg neg">▼</i>'));
  const css = html.slice(html.indexOf('/* v96 etap 2 — EXTRA92 */'));
  assert.ok(css.includes('.etfk.trk>.icos{display:flex;margin:0 0 5px;height:18px}') && !css.includes('.etfk.trk>.icos{float:left;') && css.includes('#trendy .etfkpis>.etfk.trk{display:grid;grid-template-columns:minmax(0,1fr);grid-row:span 4;grid-template-rows:subgrid;') && css.includes('.tdot{') && css.includes('#trendy .icos>*+.iss,.trd-fr .icos>*+.iss{margin-left:2px}') && css.includes('#trendy .etfk.trk b.na,#trendy .k-val.na{color:var(--dim)}'));
  assert.ok(html.includes('.neu{--c:var(--yl);color:var(--yl-tx)}') && html.includes('.dlt.chg{color:var(--yl-tx)}'), 'żółty Apple przez tokeny (czytelny w jasnym motywie)');
});

test('v96-trendy: bez nazw dostawców danych na stronie TRENDY (tylko strona Źródła); stare klucze zostają w słownikach', () => {
  const {make, data} = trdV96;
  const st = {mode: 'trendy'}, f = make(st);
  f.trdApply(data); const g = f.el.innerHTML; st.trdv = 'crypto'; f.renderTrendy(); const c = f.el.innerHTML;
  for (const h of [g, c]) assert.ok(!h.includes('trd.src.') && !h.includes('trd.foot') && h.includes('<p class="pfoot">inst.file{"t":"2026-09-25T10:00:00Z"} · eng.disclaimer</p>'), 'bez linii źródła i bez stopki ze źródłami — zostaje czas pliku i ostrzeżenie');
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  assert.ok(!blk.includes("t('trd.foot')") && !blk.includes("'trd.src.'"));
  const a = 'const EXTRA92=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.ok(x0 > html.indexOf('for(const l in EXTRA87)') && html.includes('for(const l in EXTRA92)if(I18N[l])Object.assign(I18N[l],EXTRA92[l]);'), 'po EXTRA87 — nadpisuje starsze teksty');
  assert.deepEqual(Object.keys(D.pl).sort(), Object.keys(D.en).sort());
  const prov = /Twelve Data|State Street|iShares|BlackRock|CoinGecko|CFTC|Coin ?Metrics|DefiLlama|SoSoValue|NSDL|TWSE|HKEX|ThaiBMA|Banxico|\bEBC\b|\bECB\b|FRED|\bTFF\b|disaggregated/;
  for (const l of ['pl', 'en']) for (const k in D[l]) assert.doesNotMatch(D[l][k], prov, `${l} ${k}`);
  for (const k of ['trd.x.sub', 'trd.p.t', 'trd.p.sub', 'trd.m.1', 'trd.m.3', 'trd.m.6', 'trd.n.fxm']) assert.ok(D.pl[k] && D.en[k], 'nadpisane bez nazw dostawców: ' + k);
  assert.ok(D.pl['trd.x.sub'].includes('Obligacji tu nie ma') && D.pl['trd.p.sub'].includes('fundusze zarządzające') && D.pl['trd.m.6'].includes('tworzą jednostki rzadko'), 'treść bez zmian poza nazwami');
  const a0 = 'const EXTRA80=', y0 = html.indexOf(a0), D80 = JSON.parse(html.slice(y0 + a0.length, html.indexOf(';\n', y0)));
  assert.ok(D80.pl['trd.src.etf'] && D80.pl['trd.src.cm'], 'stare klucze źródeł zostają (strona Źródła)');
  const bad = /kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|warto kupi|okazj|prognozuj|rekomend|\btrwa(?![a-ząćęłńóśźż])|odbic|odbij|cofa si|zaczyna|\bbuy\b|\bsell\b|worth buying|opportunit|recommend|forecast|rebound|continues|pulling back|\bstarts\b/i;
  for (const l of ['pl', 'en']) for (const k in D[l]) if (!/^trd\.m\./.test(k) && k !== 'trd.discc') assert.doesNotMatch(D[l][k], bad, `${l} ${k}: ${D[l][k]}`);
  assert.ok(D.pl['trd.discc'].includes('ani rekomendacja') && D.pl['trd.discc'].includes('ani prognoza') && D.en['trd.discc'].includes('not a recommendation') && !/panel niżej|panel below/.test(D.pl['trd.discc'] + D.en['trd.discc']), 'ostrzeżenie krypto: to samo „nie rekomendacja”, bez odsyłacza do panelu, którego w krypto nie ma');
  assert.doesNotMatch(D.pl['trd.discc'].replace('ani rekomendacja', ''), bad); assert.doesNotMatch(D.en['trd.discc'].replace('not a recommendation to buy or sell', '').replace('not a forecast', ''), bad, 'poza samym zaprzeczeniem — bez słów o kupnie, sprzedaży i prognozie');
  for (const k of ['trd.v.global', 'trd.v.crypto', 'trd.h1c', 'trd.kc.in', 'trd.kc.out', 'trd.kc.noout', 'trd.pc.t', 'trd.pc.sub', 'trd.xc.t', 'trd.xc.sub', 'trd.b.nocr', 'trd.lg.neu']) assert.ok(D.pl[k] && D.en[k], k);
  assert.ok(!/ponad zwykły|above the usual/.test(D.pl['trd.kc.in'] + D.pl['trd.kc.out'] + D.en['trd.kc.in'] + D.en['trd.kc.out']), 'kafle krypto nie mówią o „zwykłym poziomie”');
});

test('v96-trendy: przełącznik naprawdę działa — kliknięcie zmienia widok i zapisuje wybór, zablokowana pamięć przeglądarki nie psuje strony; otwarte bloki pamiętane osobno dla każdego widoku', () => {
  const i0 = html.indexOf("try{const v=localStorage.getItem('cfai.trd.view')"), line = html.slice(i0, html.indexOf('\n', i0));
  assert.ok(i0 > 0 && html.slice(i0 - 80, i0).includes("setMode('trendy'));\n"), 'linia słuchacza tuż po zakładce TRENDY');
  const run = (store, throws) => {
    const calls = {render: 0, focus: 0, set: []}, st = {mode: 'trendy', trdv: 'global'};
    let handler = null;
    const btn = {focus() { calls.focus++; }};
    const $ = sel => sel === '#trendy' ? {addEventListener(ev, fn) { assert.equal(ev, 'click'); handler = fn; }} : sel === '#trd-view button[aria-pressed="true"]' ? btn : null;
    const ls = {getItem(k) { if (throws) throw new Error('blocked'); return k in store ? store[k] : null; }, setItem(k, v) { if (throws) throw new Error('blocked'); calls.set.push([k, v]); store[k] = v; }};
    new Function('$', 'st', 'localStorage', 'renderTrendy', line)($, st, ls, () => { calls.render++; });
    const click = v => handler({target: {closest(sel) { assert.equal(sel, '#trd-view button[data-v]'); return v === null ? null : {dataset: {v}}; }}});
    return {st, calls, click};
  };
  let r = run({});
  assert.equal(r.st.trdv, 'global', 'bez zapisu — global');
  r.click(null); assert.equal(r.calls.render, 0, 'kliknięcie poza przełącznikiem — nic');
  r.click('global'); assert.equal(r.calls.render, 0, 'ten sam widok — bez przebudowy');
  r.click('crypto'); assert.equal(r.st.trdv, 'crypto'); assert.equal(r.calls.render, 1); assert.deepEqual(r.calls.set, [['cfai.trd.view', 'crypto']]);
  assert.equal(r.calls.focus, 1, 'fokus wraca na wciśnięty przycisk (klawiatura)');
  r.click('zzz'); assert.equal(r.st.trdv, 'global', 'nieznana wartość przycisku = global'); assert.deepEqual(r.calls.set[1], ['cfai.trd.view', 'global']);
  assert.equal(run({'cfai.trd.view': 'crypto'}).st.trdv, 'crypto', 'zapamiętany wybór wczytany przy starcie');
  assert.equal(run({'cfai.trd.view': '<x>'}).st.trdv, 'global', 'dziwna wartość w pamięci — pominięta');
  r = run({}, true); assert.equal(r.st.trdv, 'global');
  r.click('crypto'); assert.equal(r.st.trdv, 'crypto', 'pamięć przeglądarki zablokowana — przełącznik i tak działa'); assert.equal(r.calls.render, 1);
  /* otwarte bloki: osobno dla „global” i „krypto” */
  const {make, data} = trdV96, opened = [];
  const el = {innerHTML: '', q: [], querySelectorAll(sel) { assert.equal(sel, 'details[open]'); return this.q; },
    querySelector(sel) { const d = {id: sel.slice(1)}; Object.defineProperty(d, 'open', {set(v) { if (v) opened.push(d.id); }}); return this.innerHTML.includes('id="' + d.id + '"') ? d : null; }};
  const st = {mode: 'trendy'}, f = make(st, false, undefined, el);
  f.trdApply(data); assert.deepEqual(opened, []);
  assert.ok(el.innerHTML.includes('id="trd-rest-f"') && el.innerHTML.includes('<b>trd.disc</b>') && !el.innerHTML.includes('trd.discc'), 'global: zwykłe ostrzeżenie');
  el.q = [{id: 'trd-rest-f'}, {id: 'trd-method'}, {}];
  f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-rest-f', 'trd-method'], 'odświeżenie — otwarte zostają otwarte');
  st.trdv = 'crypto'; f.renderTrendy(); assert.deepEqual(opened.splice(0), [], 'krypto — własne bloki, zamknięte');
  assert.ok(el.innerHTML.includes('<b>trd.discc</b>') && !el.innerHTML.includes('<b>trd.disc</b>'), 'krypto: ostrzeżenie bez odsyłacza do panelu wyników');
  el.q = [{id: 'trd-rest-c'}]; st.trdv = 'global'; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-rest-f', 'trd-method'], 'powrót do global — bloki znowu otwarte');
  el.q = [{id: 'trd-rest-f'}, {id: 'trd-method'}]; st.trdv = 'crypto'; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-rest-c'], 'powrót do krypto — jego blok też');
  const f0 = make({mode: 'trendy', trdv: 'crypto'}); f0.renderTrendy(); assert.ok(f0.el.innerHTML.includes('<b>trd.discc</b>') && f0.el.innerHTML.includes('trd.nodata'), 'bez pliku, widok krypto');
});

test('v96-trendy: puste kafle krypto (brak danych ≠ brak napływu), szary „—” przy braku wartości, flagi i loga także w zdaniu „Najważniejsze” i w opisie regionu', () => {
  const {make, data, card} = trdV96;
  const R = o => Object.assign({g: 'cr', m: 'flow', sz: 5, cur: 'USD', date: '2026-09-24', n: 3, s: 1, sg: 1}, o);
  const tiles = h => { const a = h.indexOf('<section class="kpis gkpis">'); return h.slice(a, h.indexOf('</section>', a)); };
  const st = {mode: 'trendy', trdv: 'crypto'}, f = make(st);
  f.trdApply({at: 'a1', f: [], p: []}); let k = tiles(f.el.innerHTML);
  assert.equal((k.match(/<div class="k-val na">—<\/div><small class="mtxt">trd\.kc\.none<\/small>/g) || []).length, 6, 'brak danych — sześć szarych „—” z „brak danych”: ' + k.slice(0, 400));
  f.trdApply({at: 'a2', f: [R({id: 'etf_btc', st: 'short', w: 100}), R({id: 'etf_eth', st: 'short', w: 50})], p: [{id: 'BTC', g: 'cr', date: '2026-09-25', w: 1.2, pr: 0, st: 'up_new'}]}); k = tiles(f.el.innerHTML);
  assert.ok(k.includes('trd.kc.in</span></div><div class="k-val pos">+100 trd.u.m USD</div>'), 'największy napływ — zielony także przy krótkiej historii');
  assert.ok(k.includes('trd.kc.out</span></div><div class="k-val na">—</div><small class="mtxt">trd.kc.noout</small>'), 'same napływy — „żadna grupa nie miała odpływu”');
  assert.ok(k.includes('trd.kc.pdn</span></div><div class="k-val na">—</div><small class="mtxt">trd.kc.nopdn</small>') && k.includes('trd.kc.stab</span></div><div class="k-val na">—</div><small class="mtxt">trd.kc.none</small>'));
  assert.ok(k.includes('<span class="dlt na">•</span><span class="ksrc" title="trd.sn.short{&quot;n&quot;:3}">'), 'krótka historia — znaczek stanu szary');
  f.trdApply({at: 'a3', f: [R({id: 'etf_btc', st: 'short', w: -100})], p: []}); k = tiles(f.el.innerHTML);
  assert.ok(k.includes('trd.kc.in</span></div><div class="k-val na">—</div><small class="mtxt">trd.kc.noin</small>') && k.includes('trd.kc.out</span></div><div class="k-val neg">−100 trd.u.m USD</div>'));
  f.trdApply({at: 'a4', f: [R({id: 'etf_btc', st: 'stale', w: 100})], p: []}); k = tiles(f.el.innerHTML);
  assert.ok(k.includes('trd.kc.in</span></div><div class="k-val na">—</div><small class="mtxt">trd.kc.none</small>'), 'stare dane to nie „brak napływu”');
  st.trdv = 'global';
  f.trdApply({at: 'a5', f: [R({id: 'tw', g: 'eq', st: 'gap', w: null})], p: [{id: 'SPY', g: 'eq', date: '2026-09-24', w: null, pr: null, st: 'flat'}]});
  const g = f.el.innerHTML;
  assert.ok(card(g, 'trd.s.tw').includes('<b class="na">—<small>') && card(g, 'trd.px.SPY').includes('<b class="na">—<small>'), 'brak wartości — szary „—”, nie zero');
  assert.ok(g.includes('trd.k.in</span></div><div class="k-val na">—</div>') && g.includes('trd.k.pup</span></div><div class="k-val na">—</div>'));
  /* zdanie „Najważniejsze” — przed każdą nazwą flaga, glif albo logo (małe) */
  const f2 = make({mode: 'trendy'}, true); f2.trdApply(data); const h = f2.el.innerHTML;
  const sums = [...h.matchAll(/<b>trd\.sum\.t<\/b>(.*?)<\/p>/g)].map(m => m[1]);
  assert.ok(sums.length >= 2, 'zdania w panelach');
  for (const s of sums) for (const part of s.split(' · ')) assert.match(part, /^\s*<span class="trd-nw"><span class="icos"><img class="ico sm" src="img\/(flagi|glify|krypto)\//, 'każda nazwa w zdaniu z ikoną (v98.2: razem z nazwą, bez łamania linii): ' + part.slice(0, 200));
  assert.ok(sums[0].includes('flagi/us.svg') && sums[0].includes('>SP</span>') && sums[0].includes('<b>trd.s.fe_us</b>') && sums.some(s => s.includes('flagi/jp.svg')), sums.join('\n'));
  const g1 = make({mode: 'trendy'}); g1.trdApply(data); assert.ok(g1.el.innerHTML.includes('<b>trd.sum.t</b> <b>trd.s.fe_us</b>'), 'bez funkcji ikon (test) — zdanie bez zmian');
  /* opis regionu GLOBAL: własna klasa, żeby znaczki SP i iS się nie zasłaniały (reguła poza #trendy) */
  const reg = f2.feRegion('usa');
  assert.ok(reg.startsWith('<div class="wide"><dt>fe.reg</dt><dd class="trd-fr"><span class="icos">') && reg.includes('flagi/us.svg') && reg.includes('>SP</span>') && reg.includes('>iS</span>'), reg);
});

// v96 (obszar „sources”): źródła tylko na stronie Źródła; jedna stopka z linkiem i wymaganym podpisem CoinGecko
const v96src = (() => {
  const escH = new Function(html.slice(html.indexOf('function escH(s){'), html.indexOf('\n', html.indexOf('function escH(s){'))) + '\nreturn escH;')();
  const h0 = html.indexOf('/* ===================== v96: FLAGI, LOGA, WALUTY, ZNACZKI WYDAWCÓW'), h1 = html.indexOf('\nfunction fundIco(', h0);
  const H = new Function('escH', 'ISO32', 'COIN_LOGO', html.slice(h0, html.indexOf('\n', h1 + 1)) + '\nreturn {icoWrap,glyphImg,flagImg,issBadge,coinImg,netImg,exchImg};')(escH, {}, {});
  const d0 = html.indexOf('const LOCALE='), mm = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)], m = mm[mm.length - 1];   // v98: do ostatniego słownika
  const I18N = new Function(html.slice(d0, m.index + m[0].length) + '\nreturn I18N;')();
  const tFor = L => (k, vars) => { let s = (I18N[L] && I18N[L][k]) ?? I18N.en[k] ?? k; if (vars) for (const v in vars) s = s.split('{' + v + '}').join(vars[v]); return s; };
  const s0 = html.indexOf('const TXT_JAK_PL=`'), s1 = html.indexOf('\nfunction renderMethod(', s0);   // v103: dawny opis źródeł usunięty — od Metodologii
  const render = (L, crypto, KAN, noIco) => {
    const w = {innerHTML: ''};
    const f = new Function('$', 'gActive', 'GLIVE', 'tvState', 'LIVE', 'isLive', 'krStabh', 'srvAt', 'metaErr', 'LOCALE', 'escH', 't', 'LANG', 'KAN', 'kanLast', 'icoWrap', 'glyphImg', 'flagImg', 'issBadge', 'coinImg', 'netImg', 'exchImg', 'engDate', 'gAgeNote',
      html.slice(s0, s1) + '\nrenderSources();\nreturn {JAK_ICO, txtJakCzytac, zrCount};');
    const I = noIco ? {} : H;
    const r = f(q => q === '#page-sources' ? w : null, () => !crypto, {src: {}, srcAt: {}}, () => '—', {mkN: 0, tvl: 0, stab: null}, () => false, () => null, () => null, () => null,
      {pl: 'pl-PL', en: 'en-US'}, escH, tFor(L), L, KAN, K => K.m[K.m.length - 1], I.icoWrap, I.glyphImg, I.flagImg, I.issBadge, I.coinImg, I.netImg, I.exchImg, s => s, () => '');
    r.out = w.innerHTML; return r;
  };
  return {escH, H, I18N, tFor, render};
})();

test('v96-sources: jedna stopka pod stronami z danymi — link „Źródła i licencje” i podpis „Data by CoinGecko”, nic więcej', () => {
  const f0 = html.indexOf('<footer class="srcfoot" id="srcfoot">'), f1 = html.indexOf('</footer>', f0), foot = html.slice(f0, f1);
  assert.ok(f0 > 0 && f1 > f0 && html.indexOf('<footer') === f0 && html.indexOf('<footer', f0 + 5) < 0, 'dokładnie jedna stopka');
  assert.ok(foot.includes('<button type="button" class="srcfoot-a" data-go="sources">') && foot.includes('<span data-i18n="foot.src"></span>'));
  assert.ok(foot.includes('<a class="srcfoot-cg" href="https://www.coingecko.com" target="_blank" rel="noopener">Data by CoinGecko</a>'));
  for (const w of ['SoSoValue', 'DefiLlama', 'CoinMarketCap', 'CoinPaprika', 'Coin Metrics', 'OECD', 'BIS', 'Finnhub', 'Twelve Data', 'TradingView']) assert.ok(!foot.includes(w), 'stopka bez: ' + w);
  // stopka jest ostatnim dzieckiem .app, po przeglądzie (GLOBAL, CRYPTO, TRENDY), po stronach i ustawieniach — CSS ukrywa ją na Ustawieniach, na stronie Źródła i w Metodologii
  for (const id of ['id="crypto"', 'id="rail"', 'id="settings"', 'id="page-sources"', 'id="page-method"', 'id="global"', 'id="trendy"']) assert.ok(html.indexOf(id) > 0 && html.indexOf(id) < f0, id);
  assert.ok(html.slice(f1, f1 + 80).startsWith('</footer>\n</div>\n\n<div class="modal" id="g-help-modal"'), 'koniec .app zaraz po stopce');
  assert.ok(html.includes('#settings:not([hidden])~.srcfoot,#page-sources:not([hidden])~.srcfoot,#page-method:not([hidden])~.srcfoot{display:none}'), 'bez stopki na Ustawieniach, Źródłach i Metodologii');
  assert.ok(html.includes('.srcfoot-a,.srcfoot a{display:inline-flex;align-items:center;min-height:44px;padding:0}'), 'telefon: pole dotyku 44 px');
  assert.ok(html.includes('.srcfoot{grid-column:2/-1;grid-row:5;') && html.includes('@media (max-width:900px){.srcfoot{grid-column:1;') && html.includes('@media (min-width:901px){.side{grid-row:1/6}}'), 'siatka: pod treścią, telefon jedna kolumna');
  const D = v96src.I18N;
  assert.equal(D.pl['foot.src'], 'Źródła'); assert.equal(D.en['foot.src'], 'Sources');   // v103: przycisk stopki = nazwa zakładki
  const a = 'const EXTRA93=', x0 = html.indexOf(a), E = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.deepEqual(Object.keys(E.pl).sort(), Object.keys(E.en).sort());
});

test('v96-sources: kliknięcie „Źródła i licencje” (stopka, okno pomocy, Metodologia) otwiera stronę Źródła', () => {
  const l0 = html.indexOf("$('#logo-home').addEventListener('click'"), l1 = html.indexOf('\n', l0), l2 = html.indexOf('\n', l1 + 1), line = html.slice(l1 + 1, l2);
  assert.ok(line.startsWith("document.addEventListener('click',e=>{const a=e.target&&e.target.closest?e.target.closest('[data-go=\"sources\"]'):null;") && line.includes("setPage('sources');"), 'linia zaraz po logo');
  let h = null; const calls = []; const focus = [];
  const doc = {addEventListener: (ev, fn) => { if (ev === 'click') h = fn; }};
  const head = {focus: o => focus.push(o)};
  const run = (modalOpen) => new Function('document', '$', 'gModal', 'hModal', 'closeHelp', 'setPage', line)(doc, q => q === '#page-sources h1' ? head : null, {hidden: !modalOpen}, {hidden: true}, () => calls.push('close'), p => calls.push('page:' + p));
  run(false);
  let prevented = 0; const ev = hit => ({target: {closest: s => (s === '[data-go="sources"]' && hit) ? {} : null}, preventDefault: () => { prevented++; }});
  h(ev(false)); assert.deepEqual(calls, [], 'klik obok — nic');
  h(ev(true)); assert.deepEqual(calls, ['page:sources']); assert.equal(prevented, 1); assert.equal(head.tabIndex, -1); assert.equal(focus.length, 1, 'fokus na nagłówku strony Źródła');
  calls.length = 0; run(true); h(ev(true)); assert.deepEqual(calls, ['close', 'page:sources'], 'z okna pomocy: najpierw zamknij okno');
});

// v103: testy dawnej strony Źródła (tabela źródeł, Atrybucje, opis praw do danych) usunięte — strona jest teraz kartą stanu „na żywo”; testy v103-zrodla na końcu pliku

test('v96-sources: Metodologia i okno pomocy — pod kafelkami data i wiek, źródła tylko na stronie Źródła', () => {
  const j0 = html.indexOf('const TXT_JAK_PL=`'), j = html.slice(j0, html.indexOf('`;', j0));
  assert.ok(j.includes('<b>3. Każda liczba ma datę i wiek, a jej źródło jest opisane na stronie „Źródła”.</b> Pod kafelkami: „data · dane sprzed N dni”.'));
  for (const w of ['Pod kafelkami: „źródło', 'źródło · 2026-08', 'Na żywo · SoSoValue', 'Migawka z 2026-09-23 · SoSoValue', '· SoSoValue: … · Finnhub: …', '<th>Źródło</th>']) assert.ok(!j.includes(w), w);
  const f0 = j.indexOf('<h3>Jak często zmieniają się dane</h3>'), ft = j.slice(f0, j.indexOf('</tbody></table></div>', f0));
  const trs = ft.split('<tr>').slice(2);
  assert.ok(trs.length >= 30 && trs.every(r => (r.match(/<td>/g) || []).length === 3), 'tabela częstotliwości bez kolumny „Źródło”');
  assert.ok(j.includes('<button type="button" class="lnk" data-go="sources">stronę Źródła</button>'));
  assert.ok(html.includes('every number carries its date and age while its source is named on the <button type="button" class="lnk" data-go="sources">Sources page</button>'));
  // okno pomocy GLOBAL: zamiast listy źródeł jedno zdanie z linkiem
  assert.ok(html.includes('<h3 data-i18n="g.help.src"></h3>\n      <p class="mtxt" id="gh-src"></p>') && !html.includes('<div class="q-grid" id="gh-src">'));
  const g0 = html.indexOf('function gHelpSrc(){'), g1 = html.indexOf('\n}', g0) + 2;
  const w = {innerHTML: ''}; new Function('$', 't', html.slice(g0, g1) + '\ngHelpSrc();')(q => q === '#gh-src' ? w : null, v96src.tFor('pl'));
  assert.equal(w.innerHTML, 'Dane pochodzą z legalnych, publicznych źródeł i są pobierane automatycznie; stan odświeżania: <button type="button" class="lnk" data-go="sources">Źródła</button>');   // v103
  assert.ok(html.includes('.lnk{background:none;border:0;padding:0;font:inherit;color:var(--bl);'));
});

test('v96-sources: Metodologia — flaga albo logo przy każdym wierszu tabeli „Jak często zmieniają się dane”', () => {
  const R = v96src.render('pl', false, null), J = R.txtJakCzytac();
  const f0 = J.indexOf('<h3>Jak często zmieniają się dane</h3>'), ft = J.slice(f0, J.indexOf('</tbody></table></div>', f0));
  const trs = ft.split('<tr>').slice(2);
  assert.ok(trs.length >= 31, 'wszystkie wiersze: ' + trs.length);
  for (const r of trs) assert.ok(r.startsWith('<td><span class="cell"><span class="icos"><') && /<img class="ico sm" src="img\/(flagi|glify|krypto)\//.test(r.slice(0, 200)) && r.includes('</span><span>'), 'ikona: ' + r.slice(0, 120));
  assert.equal(Object.keys(R.JAK_ICO).length, trs.length, 'każdy klucz trafia w wiersz (tekst wiersza = klucz)');
  const row = n => trs.find(r => r.includes('<span>' + n + '</span>')) || '';
  const need = {'zakupy i sprzedaże inwestorów zagranicznych: Indie, Tajwan, Hongkong': ['flagi/in.svg', 'flagi/tw.svg', 'flagi/hk.svg'], 'nierezydenci w meksykańskich papierach rządowych (zmiana stanu)': ['flagi/mx.svg'],
    'nierezydenci w tureckich akcjach i obligacjach': ['flagi/tr.svg'], 'nierezydenci w tajskich obligacjach': ['flagi/th.svg'], 'dolary przez rynek walutowy Brazylii': ['flagi/br.svg'],
    'transakcje w papierach Japonii': ['flagi/jp.svg'], 'papiery USA ↔ zagranica (TIC)': ['flagi/us.svg', 'glify/globe.svg'], 'bilans płatniczy strefy euro': ['flagi/eu.svg'],
    'nierezydenci w krajowych papierach skarbowych (zmiana stanu)': ['flagi/pl.svg'], 'inwestorzy zagraniczni w Korei: akcje i obligacje': ['flagi/kr.svg'], 'nierezydenci w kanadyjskich papierach': ['flagi/ca.svg'],
    'bilans płatniczy krajów UE (w tym Polski)': ['flagi/eu.svg', 'flagi/pl.svg'], 'kupno i sprzedaż walut przez banki w Chinach': ['flagi/cn.svg'], 'rentowność 10 lat USA i Niemiec': ['flagi/us.svg', 'flagi/de.svg'],
    'wpłaty i wypłaty BTC i ETH na giełdy': ['krypto/btc.svg', 'krypto/eth.svg'], 'napływy do ETF na krypto': ['glify/etf.svg', 'krypto/btc.svg', 'krypto/eth.svg'], 'bilans płatniczy 37 gospodarek': ['glify/globe.svg']};
  for (const n in need) for (const x of need[n]) assert.ok(row(n).includes(x), n + ' → ' + x);
  // druga tabela (napisy przy liczbach) bez zmian; tekst tabeli w kodzie bez zmian
  assert.ok(J.includes('<tr><td><span class="cell">2026-08 · dane sprzed 24 dni</span></td>'));
  assert.ok(html.includes('<tr><td><span class="cell">nierezydenci w tajskich obligacjach</span></td>'), 'tekst w kodzie bez zmian — ikony dokłada txtJakCzytac');
  assert.ok(html.includes('#page-method td .cell>.icos{margin-right:0}'));
  // po angielsku — krótki tekst bez tabeli
  assert.ok(!v96src.render('en', false, null).txtJakCzytac().includes('class="icos"'));
});

test('v96-sources: bez pomocników ikon strona Źródła i Metodologia nie wywracają się (same opisy)', () => {
  const R = v96src.render('pl', false, null, true), out = R.out;
  assert.ok(out.includes('class="panel pgc zr-attr2"') && out.includes('country-flag-icons') && out.includes('This product uses the FRED® API') && !out.includes('class="icos"'));   // v103: karta stanu + wymagane podpisy
  const J = R.txtJakCzytac();
  assert.ok(J.includes('<tr><td><span class="cell"><span>zakupy i sprzedaże inwestorów zagranicznych: Indie, Tajwan, Hongkong</span></span></td>') && !J.includes('class="icos"'));
  assert.ok(v96src.render('pl', true, null, true).out.includes('zr-attr2'), 'CRYPTO bez ikon też działa');
});

test('v98-usa: panel USA — energia, gospodarka i przepływ kapitału; ikony, kolory, brak = „—”, bez nazw dostawców', () => {
  const b0 = html.indexOf('/* ===================== v98: USA — energia'), b1 = html.indexOf('function usaAuto(){', b0);
  assert.ok(b0 > 0 && b1 > b0, 'blok USA w stronie');
  const blk = html.slice(b0, html.indexOf('\n', b1));
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const el = {innerHTML: '', hidden: true, querySelectorAll() { return []; }, querySelector() { return null; }};
  const escH = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const mk = extra => new Function('$', 't', 'escH', 'nfmt', 'fPct', 'sg', 'gAgeNote', 'LOCALE', 'LANG', 'srvJSON', 'engDate', ...Object.keys(extra),
    blk + '\nreturn {USA, renderUsa, usaApply};')(() => el, T, escH, (v, d = 0) => v.toFixed(d), (v, d = 1) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%',
    v => v > 0 ? '+' : v < 0 ? '−' : '', d => ' ·wiek', {pl: 'pl-PL'}, 'pl', () => Promise.resolve(null), s => 'D:' + s, ...Object.values(extra));
  const f = mk({});
  f.usaApply('e', {at: '2026-09-25T18:42:19+00:00', s: {
    wti: {d: [['2026-09-15', 100], ['2026-09-16', 99], ['2026-09-17', 98], ['2026-09-18', 97], ['2026-09-21', 96.97], ['2026-09-22', 96.41]]},
    crude: {d: [['2026-09-11', 423429], ['2026-09-18', 426398]]}, gas: {d: [['2026-09-22', null]]}}});
  let h = el.innerHTML;
  assert.ok(!el.hidden && h.includes('<h2>') && h.includes('usa.t'), 'sekcja widoczna z tytułem');
  assert.ok(h.includes('<span>usa.wti</span>') || h.includes('usa.wti</span>'), h.slice(0, 400));
  assert.ok(h.includes('96.41') && h.includes('class="neg">▼ −3.6% usa.wk'), 'WTI: −3,6% wobec notowania sprzed 5 sesji, na czerwono');
  assert.ok(h.includes('426.4') && h.includes('class="pos">▲ +3.0 usa.wk1'), 'zapasy: +3,0 mln bbl tydzień do tygodnia, na zielono');
  assert.ok(!h.includes('usa.gas'), 'gaz bez wartości — bez kafla, nie zero');
  assert.ok(!/EIA|BLS|BEA|Energy Information|Labor Statistics|Economic Analysis/.test(h), 'bez nazw dostawców na stronie głównej');
  f.usaApply('m', {at: '2026-09-25T18:42:19+00:00', s: {cpi: {d: [], yoy: [['2026-07', 3.4], ['2026-08', 3.4]]}, unemp: {d: [['2026-07', 4.2], ['2026-08', 4.1]]},
    nfp: {d: [], chg: [['2026-08', 162]]}, core: {d: [], yoy: [['2026-08', 2.4]]}}});
  f.usaApply('b', {at: '2026-09-25T18:42:19+00:00', ita: {FinLiabsExclFinDeriv: [['2026-Q2', 978860]], FinAssetsExclFinDeriv: [['2026-Q2', 663301]], BalCurrAcct: [['2026-Q2', -246023]]},
    gdp: [['2026-Q2', 1.5]], areas: {FinLiabsExclFinDeriv: {Europe: [['2026-Q2', 300000]], China: [['2026-Q2', -1234]]}, FinAssetsExclFinDeriv: {Europe: [['2026-Q2', 100000]]}}, names: {}});
  h = el.innerHTML;
  assert.ok(h.includes('usa.cpi') && h.includes('3.4%') && h.includes('<small class="">• 0.0 usa.pp') && !h.includes('class="neu">• 0.0'), 'inflacja bez zmiany — v98.2: zero bez koloru (szary „•”)');
  assert.ok(h.includes('usa.unemp') && h.includes('4.1%') && h.includes('class="neg">▼ −0.1 usa.pp'), 'bezrobocie spadło o 0,1 pkt — czerwona strzałka w dół');
  assert.ok(h.includes('<b class="pos">+162 <small class="mtxt">usa.u.k</small></b>'), 'nowe etaty na zielono');
  assert.ok(h.includes('usa.gdp') && h.includes('<b class="pos">+1.5%</b>') && h.includes('usa.q{"q":"2","r":"II","y":"2026"}'), 'PKB na zielono, kwartał po rzymsku');
  assert.ok(h.includes('<b class="pos">+978.9 <small class="mtxt">usa.u.bn</small></b>') && h.includes('<b class="neg">−663.3'), 'do USA zielono, z USA czerwono');
  assert.ok(h.includes('<b class="pos">+315.6'), 'netto = do USA − z USA');
  assert.ok(h.includes('<td><span class="cell">Europe</span></td>'), 'bez tłumaczenia — nazwa obszaru z pliku (w stronie: „Europa”)');
  assert.ok(h.includes('<td><span class="cell mono pos">+300.0</span></td><td><span class="cell mono neg">−100.0</span></td><td><span class="cell mono pos">+200.0</span></td>'), 'tabela: kolory jak w innych tabelach strony');
  assert.ok(h.includes('China</span></td><td><span class="cell mono neg">−1.2</span></td><td><span class="cell mono na">—</span></td><td><span class="cell mono na">—</span></td>'), 'brak = „—”, nie zero');
  const g = mk({flagImg: (c, cls) => `<img class="ico" src="img/flagi/${c}.svg">`, glyphImg: n => `<img class="ico" src="img/glify/${n}.svg">`,
    flagsHtml: (l, m, cls) => `<span class="icos">${l.map(c => `<img src="img/flagi/${c}.svg">`).join('')}</span>`});
  g.usaApply('e', {at: 'x', s: {wti: {d: [['2026-09-22', 96.41]]}}});
  g.usaApply('b', {at: 'x', ita: {FinLiabsExclFinDeriv: [['2026-Q2', 1]], FinAssetsExclFinDeriv: [['2026-Q2', 1]]}, areas: {FinLiabsExclFinDeriv: {Europe: [['2026-Q2', 1]]}, FinAssetsExclFinDeriv: {}}});
  h = el.innerHTML;
  assert.ok(h.includes('img/glify/oil.svg') && h.includes('img/flagi/us.svg') && h.includes('img/flagi/eu.svg') && h.includes('img/flagi/gb.svg'), 'ikony: ropa, flaga USA, flagi Europy');
  const e2 = mk({}); e2.usaApply('e', null);
  assert.ok(html.includes('<section class="panel pcard" id="g-usa" hidden></section>') && html.includes('usaLoad();usaAuto();'));
});
test('v98.1-usa: panel USA — kolory widoczne (styl kafelków nie gasi zmian), ikony w linii z nazwą', () => {
  assert.ok(html.includes('#g-usa .etfk b small.pos{color:var(--gr-tx)}') && html.includes('#g-usa .etfk b small.neg{color:var(--rd-tx)}') && html.includes('#g-usa .etfk b small.neu{color:var(--yl-tx)}'));
  assert.ok(html.includes('#g-usa .etfk span.icos{display:inline-flex'));
});
test('v98.2: okno pomocy GLOBAL bez nazw instytucji, w 10 językach; Metodologia zostaje przy dawnych tekstach', () => {
  const m0 = html.indexOf('<div class="modal" id="g-help-modal"'), m1 = html.indexOf('<div class="modal" id="help-modal"', m0), M = html.slice(m0, m1);
  for (const k of ['2', 'readd', 'corr', 'probd', 'limd']) assert.ok(M.includes(`data-i18n="g.hm.${k}"`) && !M.includes(`data-i18n="g.help.${k}"`), 'okno pomocy: ' + k);
  const PROV = /\b(BIS|BIZ|BRI|BPI|OECD|OCDE|TIC|MOF|EBC|ECB|EZB|BCE|Eurostat|MFW|IMF|IWF|FMI|CFTC)\b|МВФ|ЕЦБ|Евростат|欧洲央行|欧盟统计局|ユーロスタット/;
  const en = v96src.tFor('en');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    for (const k of ['g.hm.2', 'g.hm.readd', 'g.hm.corr', 'g.hm.probd', 'g.hm.limd']) { const v = t(k); assert.ok(v && v !== k && !PROV.test(v), L + ' ' + k + ': ' + v); }
    if (L !== 'en') for (const k of ['g.hm.corr', 'g.hm.probd']) assert.notEqual(t(k), en(k), 'przetłumaczone (wcześniej po angielsku): ' + L + ' ' + k);
  }
  assert.ok(v96src.tFor('pl')('g.hm.limd').includes('kwartalne (bilanse płatnicze i międzynarodowe statystyki bankowe)'));
  assert.ok(v96src.tFor('pl')('g.hm.probd').includes('nie jest to porada inwestycyjna'), 'zastrzeżenie zostaje');
  assert.ok(html.includes("<p class=\"mtxt\">${t('g.help.corr')}</p>") && html.includes("${t('g.help.limd')}"), 'Metodologia: dawne teksty bez zmian');
});
test('v98.2: jednostka kontraktu i podpis wykresu bez nazw dostawców; flagi przy gospodarkach w opisie kalendarza', () => {
  const c0 = html.indexOf('function cftcUnit('), c1 = html.indexOf('\n', html.indexOf("return v?`<p class=\"pnote\">", c0));
  const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const clean = s => s.replace(/Opis jednostki w raporcie CFTC: \([^)]*\)\.\s*/, '');
  const mk = L => new Function('t', 'LANG', 'escH', 'gtEngClean', html.slice(c0, c1 + 1) + '\nreturn cftcUnit;')(v96src.tFor(L), L, esc, clean);
  const btc = 'Opis jednostki w raporcie CFTC: (5 Bitcoins). Po polsku: 1 kontrakt to 5 bitcoinów.', eth = 'Opis jednostki w raporcie CFTC: (50 Index Points). Po polsku: 1 kontrakt to 50 punktów indeksu, rozliczany gotówkowo (bez dostawy etheru).';
  assert.equal(mk('pl')(btc), '<p class="pnote">1 kontrakt to 5 bitcoinów.</p>');
  assert.equal(mk('de')(eth), '<p class="pnote">1 Kontrakt = 50 Indexpunkte, bar abgerechnet.</p>');
  assert.equal(mk('en')(btc), '<p class="pnote">1 contract = 5 bitcoins.</p>');
  assert.equal(mk('pl')('Opis jednostki w raporcie CFTC: (1 Ounce). Po polsku: 1 kontrakt to 1 uncja.'), '<p class="pnote">1 kontrakt to 1 uncja.</p>', 'nieznana jednostka po polsku — oczyszczona');
  assert.equal(mk('ja')('Opis jednostki w raporcie CFTC: (1 Ounce). Po polsku: 1 kontrakt to 1 uncja.'), '', 'nieznana jednostka w innym języku — bez polskiego zdania');
  assert.equal(mk('pl')(''), ''); assert.equal(mk('pl')(null), '');
  assert.ok(!html.includes('escH(m.unit_note)') && html.includes('${cftcUnit(m.unit_note)}'));
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    assert.ok(!t('tv.sub.chart').includes('Bitstamp') && t('tv.sub.chart').includes('BTC/USD'), 'wykres bez nazwy giełdy: ' + L);
    for (const k of ['cftc.u.btc', 'cftc.u.idx', 'live.nosrc']) assert.ok(t(k) !== k && !/CFTC|Bitstamp/.test(t(k)), L + ' ' + k);
  }
  const k0 = html.indexOf('function tvCalSub('), k1 = html.indexOf('\nfunction tvRender(', k0);
  const cal = (L, tt) => new Function('t', 'flagImg', html.slice(k0, k1) + '\nreturn tvCalSub();')(tt || v96src.tFor(L), c => `[${c}]`);
  assert.equal(cal('pl'), 'Wydarzenia o wysokiej wadze: <span class="tvc">[us]USA</span>, <span class="tvc">[eu]strefa euro</span>, <span class="tvc">[gb]Wielka Brytania</span>, <span class="tvc">[jp]Japonia</span>, <span class="tvc">[cn]Chiny</span>, <span class="tvc">[de]Niemcy</span>.');
  assert.ok(cal('zh').includes('<span class="tvc">[cn]中国</span>、<span class="tvc">[de]德国</span>。'), cal('zh'));
  for (const L of ['en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'ja']) assert.equal((cal(L).match(/class="tvc"/g) || []).length, 6, 'sześć flag: ' + L + ' ' + cal(L));
  assert.equal(cal('pl', () => 'Tekst bez listy'), 'Tekst bez listy', 'inny kształt tekstu — sam tekst, bez błędu');
  assert.ok(html.includes("<p class=\"pnote\">${k==='calendar'?tvCalSub():t('tv.sub.'+k)}</p>") && html.includes("<h2>${hIc}${t('tv.t.'+k)}</h2>") && html.includes("({chart:()=>icoWrap(coinImg('BTC','sm')+coinImg('ETH','sm')),"));
});
test('v98.2: zero po zaokrągleniu bez koloru i bez minusa (panel USA, kurs efektywny); kolor i strzałka z pokazanej liczby', () => {
  const u0 = html.indexOf('function usaTone('), u1 = html.indexOf('\nfunction usaMon(', u0);
  const U = new Function('usaNum', 'sg', 'nfmt', html.slice(u0, u1) + '\nreturn {usaTone, usaChg};')(v => typeof v === 'number' && isFinite(v), v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d) => Number(v).toFixed(d));
  assert.equal(U.usaTone(0), ''); assert.equal(U.usaTone(0.04, 1), ''); assert.equal(U.usaTone(0.06, 1), 'pos'); assert.equal(U.usaTone(-0.06, 1), 'neg'); assert.equal(U.usaTone(null), ''); assert.equal(U.usaTone(-2), 'neg');
  assert.equal(U.usaChg(0.04, 1, '', 'usa.pp'), '• 0.0 usa.pp'); assert.equal(U.usaChg(-0.26, 1, '%', 'usa.wk'), '▼ −0.3% usa.wk'); assert.equal(U.usaChg(-0.04, 1, '%', 'usa.wk'), '• 0.0% usa.wk');
  assert.ok(!html.includes(":v<0?'neg':'neu';}"), 'zero nie jest żółte');
  const e0 = html.indexOf('const eerPct='), e1 = html.indexOf('\n', e0);
  const eer = new Function('instSign', 'nfmt', html.slice(e0, e1) + '\nreturn eerPct;')(v => v > 0 ? '+' : v < 0 ? '−' : '', (v, d) => Number(v).toFixed(d));
  assert.equal(eer(-0.04), '0.0%'); assert.equal(eer(0.04), '0.0%'); assert.equal(eer(0), '0%'); assert.equal(eer(-0.06), '−0.1%'); assert.equal(eer(null), '—');
});
test('v98.2: kolory tam, gdzie ich brakowało; brak danych szary; plakietka CRYPTO w nowym języku', () => {
  assert.ok(html.includes("L.push(ln('cb.cme',t('cb.cme.v',{b:cbTone(g(mb)),e:cbTone(g(me))}),"), 'CME w bilansie krypto: kolor pozycji');
  assert.ok(html.includes('<div class="d-val sora${dTone?\' \'+dTone:\'\'}">') && html.includes("dTone=Math.round(v)>0?'pos':Math.round(v)<0?'neg':'';"), 'CRYPTO: kwota w nagłówku szczegółów w kolorze, zero bez');
  assert.ok(html.includes("out:mld(L('out')&&L('out')[0]===i[0]?L('out')[1]:null,1)") && html.includes('fa:mld(f[1],1),pi:p?mld(p[1],1)') && html.includes('a:j(A.total_net,1)'), 'zmierzone przepływy regionu: plus = odpływ — odwrócony kolor');
  const r0 = html.indexOf('function msRegion('), r1 = html.indexOf('\nfunction gProbBox(', r0);
  const gtI = (k, v, txt, inv) => { const x = inv ? -v : v; return x > 0 ? `<span class="pos">${txt}</span>` : x < 0 ? `<span class="neg">${txt}</span>` : txt; };
  const ms = new Function('t', 'TIC', 'INST', 'instSign', 'instMld', 'instFoot', 'gtI', 'gmFl', html.slice(r0, r1) + '\nreturn msRegion;')((k, o) => k + (o ? JSON.stringify(o) : ''),
    {data: {world: {in: [['2026-07', 40600]], in_tr: [['2026-07', -3600]], in_eq: [['2026-07', 3700]], out: [['2026-07', 68500]]}}}, undefined,
    v => v > 0 ? '+' : v < 0 ? '−' : '', v => (v / 1000).toFixed(1), d => d, gtI, c => '');
  const us = ms('usa');
  assert.ok(us.includes('"in":"<span class=\\"pos\\">+40.6</span>"') && us.includes('"tr":"<span class=\\"neg\\">−3.6</span>"') && us.includes('"out":"<span class=\\"neg\\">+68.5</span>"'), 'USA: napływ zielony, zakupy Amerykanów za granicą (odpływ) czerwone: ' + us);
  assert.ok(html.includes("const chg=(k,d)=>{if(d==null||!isFinite(d))return `<span class=\"cell na\">—</span>`;") && html.includes("<span class=\"sval ${na?'na':c}\">") && html.includes("gAgeNote(GLIVE.asof):'<span class=\"na\">—</span>'],"));
  assert.ok(html.includes('#page-assets .cell.na,#page-sectors .sval.na,#g-q .na{color:var(--dim)}'));
  const a0 = html.indexOf('function applyLang(){'), a1 = html.indexOf('\nfunction applyTheme(', a0);
  assert.ok(html.slice(a0, a1).includes("if(typeof renderStatus==='function')renderStatus();"), 'applyLang odświeża plakietkę');
  assert.ok(html.includes("el.title=s==='err'?(/brak źródła/.test(String(LIVE.err))?t('live.nosrc'):String(LIVE.err)):'';"), 'podpowiedź bez polskiego komunikatu błędu');
});
test('v98.2: TRENDY — kafle bez ucinania opisu, kolor ceny według stanu, ikony nad nazwą; brakujące flagi i loga', () => {
  const d0 = html.indexOf('const TRD_DLT='), d1 = html.indexOf('\n', d0), f0 = html.indexOf('function trdTile('), f1 = html.indexOf('\nfunction trdPick(', f0);
  const T = new Function('escH', html.slice(d0, d1) + '\n' + html.slice(f0, f1) + '\nreturn trdTile;')(s => String(s));
  const empty = T('trd.kc.out', '—', '', 'trd.kc.noout', '', '');
  assert.ok(!empty.includes('k-foot') && !empty.includes('>•<'), 'pusty opis — bez samotnego „•”: ' + empty);
  assert.ok(T('x', '+1%', 'neu', '', '• trd.ps.flat', '').includes('<div class="k-foot"><span class="dlt chg">•</span><span class="ksrc" title="trd.ps.flat">trd.ps.flat</span></div>'));
  assert.ok(html.includes('#trendy .k-foot{justify-content:flex-start;') && html.includes('#trendy .ksrc{white-space:normal;overflow:visible;text-overflow:clip}'), 'opis od lewej, w całości');
  assert.ok(html.includes("const pt=(title,r)=>r?trdTile(title,fPct(r.w,2),trdTone(r),") && html.includes("const pt=(title,r,tone,key)=>r?trdTile(title,fPct(r.w,2),trdTone(r),"), 'kafel ceny: kolor jak na karcie');
  assert.ok(html.includes("iss=fe&&TRD_ISS[fe.iss]||trdIssOf(r.sym)"), 'karta cen grupy funduszy: znaczki wszystkich wydawców');
  assert.ok(html.includes("grid('trd.x.eq',EQ,'@globe')+grid('trd.x.fp',FP,'@gold @silver us')"));
  assert.ok(html.includes('.trd-nw{white-space:nowrap}'), 'ikona i nazwa w zdaniu „Najważniejsze” nie rozdzielają się');
  assert.ok(html.includes("kpi(I('f','us','sm')+t('tic.in'),W.in)+kpi(I('f','us','sm')+t('tic.out'),W.out,'',1)") && html.includes("instRow(I('f','us','sm')+t('tic.net'),") && html.includes("instRow(I('f','us','sm')+t('tic.hold.out'),"), 'TIC: flaga USA w kaflach „Świat razem”');
  assert.ok(html.includes("${usaG('oil','sm')}${usaF('us','sm')}</span><b>${t('usa.h.e')}</b>") && html.includes("<b>${t('usa.h.m')}</b>") && html.includes("icoWrap(coinImg('BTC','sm')+coinImg('ETH','sm')+flagImg('us','sm')):''}${t('etf.t')}</h2>"), 'nagłówki USA i ETF z ikonami');
  assert.ok(html.includes("?icoWrap(coinImg('BTC','sm')+coinImg('ETH','sm')):''}${t('cm.t')}</h2>"), 'nagłówek przepływów na giełdy z logo BTC i ETH');
  assert.ok(html.includes("${gmRf(s.id)}${(Array.isArray(dy.syms)?dy.syms:[]).map(gmFund)"), 'dzisiejsza sesja: flagi regionu');
});
test('v98.2: czytelność — żółty w jasnym motywie, chipy CRYPTO, znaczki wydawców, tabela USA na telefonie, liczby bez ucinania', () => {
  assert.ok(html.includes('--gr-tx:#248A3D; --rd-tx:#D70015; --yl-tx:#8F6A00;'), 'jasny motyw: ciemnozłoty zamiast pomarańczowo-brązowego');
  assert.ok(html.includes('.chip-n.in .p{color:var(--gr-tx)}.chip-n.out .p{color:var(--rd-tx)}'));
  assert.ok(!html.includes('.stars{'), 'bez martwej reguły .stars (jedyny pomarańczowy)');
  assert.ok(html.includes("ishares:['iShares (BlackRock)','iS','#5A5A5E']") && !html.includes("'#141414'"), 'znaczek iShares widoczny na ciemnym tle');
  assert.ok(html.includes('#usa-areas .etft{min-width:0}') && html.includes('#usa-areas td .cell>.icos{min-width:50px}'), 'tabela USA mieści się na telefonie, nazwy w jednej linii');
  assert.ok(html.includes('#eng-coinmetrics-exchange-flows .etfk b,#eng-defillama-stablecoins .etfk b{white-space:normal;'), 'liczby w kafelkach giełd i stablecoinów nie są ucinane');
  assert.ok(html.includes('#page-sectors .ssub .icos>*+.ico{margin-left:2px}'), 'Sektory: loga krypto nie zakrywają się');
  assert.ok(html.includes("'g.k.dxy':()=>flagImg('us','sm'),"));
  assert.ok(html.includes('@supports (grid-template-rows:subgrid){.gkpis>.kpi{display:grid;grid-template-columns:minmax(0,1fr);grid-row:span 4;grid-template-rows:subgrid;align-content:start}'), 'kafle: kwoty w rzędzie na jednej wysokości');
});
test('v99: OECD najpierw z pliku serwera (co 6 h), prosto z OECD tylko brakująca część; plik starszy niż 7 dni pominięty', () => {
  const o0 = html.indexOf('function oecdSrv('), o1 = html.indexOf('\n  return out;}', o0) + '\n  return out;}'.length;
  const f = new Function(html.slice(o0, o1) + '\nreturn oecdSrv;')();
  const now = new Date().toISOString(), old = new Date(Date.now() - 8 * 864e5).toISOString();
  const S = {USA: [['2026-07', 224.2], ['2026-08', 230.7]], JPN: [['2026-08', null], 'x']};
  const r = f({at: now, share: S, irlt: {USA: [['2026-08', 4.68]]}, cli: {USA: [['2026-08', 100.9]]}, part_at: {share: now, irlt: now, cli: old}});
  assert.deepEqual(r.share, {USA: [['2026-07', 224.2], ['2026-08', 230.7]]}, 'wiersze bez liczby odrzucone (brak ≠ zero)');
  assert.deepEqual(r.irlt, {USA: [['2026-08', 4.68]]});
  assert.ok(!('cli' in r), 'część starsza niż 7 dni — pominięta (strona zapyta OECD sama)');
  assert.deepEqual(f({at: old, share: S}), {}, 'cały plik starszy niż 7 dni — pominięty');
  assert.deepEqual(f(null), {}); assert.deepEqual(f({at: 'x', share: S}), {}); assert.deepEqual(f({at: now, share: []}), {});
  const g0 = html.indexOf('function gLoad(cb){'), g1 = html.indexOf('\n  Promise.all(P).then(', g0), G = html.slice(g0, g1);
  assert.ok(G.includes("srvJSON('oecd').then(j=>{const S=oecdSrv(j),pa=") && G.includes("S[k]?Promise.resolve().then(()=>{set(S[k]);gOk(src);GLIVE.oecdAt[src]=pa[k]||j.at;}):gJSON(GSRC[g](gISO.join('+')))"), 'najpierw plik, potem zapas');
  assert.ok(G.includes("one('share','oecd','oecd',v=>{GLIVE.oecd=v;},1)") && G.includes("one('cli','cli','cli',v=>{GLIVE.cli=v;})") && !G.includes("gJSON(GSRC.oecd(gISO.join('+'))).then"), 'bez bezpośrednich zapytań przy dobrym pliku');
  assert.ok(html.includes('oecd:()=>GLIVE.oecdAt&&GLIVE.oecdAt.oecd,irlt:') && html.includes("oecd:'oecd',irlt:'oecd',cli:'oecd',") && html.includes("oecd:'OECD',irlt:'OECD',cli:'OECD',"), 'Źródła: czas pliku serwera i błąd z meta przy wierszach OECD');
});
test('v100: nowe widgety TradingView po kliknięciu — wiadomości (GLOBAL, CRYPTO), zmienność opcji BTC/ETH (DVOL); zgoda wspólna', () => {
  const w0 = html.indexOf('const TV_W={'), w1 = html.indexOf('\n};', w0), W = html.slice(w0, w1);
  for (const k of ['markets', 'calendar', 'heatmap', 'chart', 'news', 'newsc', 'dvol']) assert.ok(W.includes('\n  ' + k + ":{id:'tv-" + k + "'"), 'widget ' + k);
  assert.ok(W.includes("js:'embed-widget-timeline.js'") && W.includes("feedMode:'all_symbols'") && W.includes("feedMode:'market',market:'crypto'"), 'wiadomości: świat i krypto');
  assert.ok(W.includes('symbol:TV.dvol') && html.includes("dvol:'DERIBIT:DVOL'") && html.includes("[['DERIBIT:DVOL','BTC'],['DERIBIT:ETHDVOL','ETH']]"), 'DVOL: BTC i ETH');
  for (const id of ['tv-news', 'tv-newsc', 'tv-dvol']) assert.equal(html.split('<section class="panel pcard" id="' + id + '" hidden></section>').length, 2, 'jedno miejsce: ' + id);
  const c0 = html.indexOf('<section class="panel pcard" id="tv-chart" hidden></section>'), g0 = html.indexOf('<section class="panel pcard" id="tv-calendar" hidden></section>');
  assert.ok(html.indexOf('id="tv-dvol"') > c0 && html.indexOf('id="tv-dvol"') < c0 + 200 && html.indexOf('id="tv-news"') > g0 && html.indexOf('id="tv-news"') < g0 + 200, 'CRYPTO: po wykresie; GLOBAL: po kalendarzu');
  assert.ok(html.includes("closest('[data-tv-load],[data-tv-sym],[data-tv-dvol],[data-tv-off]')") && html.includes("if(b.dataset.tvDvol){TV.dvol=b.dataset.tvDvol;tvRender('dvol');if(!TV.loaded.dvol&&tvOk())tvOn('dvol');return;}"), 'przełącznik BTC/ETH ładuje tylko za zgodą');
  assert.ok(html.includes('function tvOn(k){if(!tvOk())return;TV.loaded[k]=true;tvRender(k);}'), 'bez kliknięcia — zero połączeń z TradingView');
  const PROV = /Deribit|CoinDesk|Reuters|Bloomberg/;
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    for (const k of ['tv.t.news', 'tv.sub.news', 'tv.n.news', 'tv.t.newsc', 'tv.sub.newsc', 'tv.n.newsc', 'tv.t.dvol', 'tv.sub.dvol', 'tv.n.dvol']) assert.ok(t(k) !== k && !PROV.test(t(k)), L + ' ' + k);
    assert.ok(!/cztery|four|vier|cuatro|quatre|quattro|quatro|четыр|四|4 つ/.test(t('tv.ph.note')), 'zgoda bez liczby widgetów: ' + L);
  }
  assert.ok(v96src.tFor('pl')('tv.sub.dvol').includes('nie prognoza kierunku') && v96src.tFor('pl')('tv.sub.news').includes('nie jest nasza ocena'), 'oczekiwanie rynku, nie prognoza; nagłówki, nie nasza ocena');
  assert.ok(v96src.tFor('pl')('g.hs.tv').includes('wiadomości krypto') && v96src.tFor('en')('g.hs.tv').includes('DVOL'), 'strona Źródła wymienia nowe widgety');
});
test('v101: kursy EBC i rentowności 10L najpierw z pliku serwera; prosto ze źródła tylko brakująca albo za stara część', () => {
  const r0 = html.indexOf('function rynkiSrv('), r1 = html.indexOf('\n  return out;}', r0) + '\n  return out;}'.length;
  const f = new Function(html.slice(r0, r1) + '\nreturn rynkiSrv;')();
  const now = new Date().toISOString(), old = new Date(Date.now() - 40 * 3600e3).toISOString(), vold = new Date(Date.now() - 5 * 864e5).toISOString();
  const R = {amount: 1, base: 'USD', date: '2026-09-25', rates: {EUR: 0.877}}, FX = {now: R, '1M': R, '1Q': R, '1R': R, '1D': R, '1T': R};
  const ok = f({at: now, fx: FX, ust: [['2026-09-25', 5.17], ['x', null]], buba: [['2026-09-25', 3.6]], part_at: {fx: now, ust: now, buba: now}});
  assert.ok(ok.fx === FX && ok.ust.length === 1 && ok.buba.length === 1, 'wiersze bez liczby odrzucone (brak ≠ zero)');
  const miss = Object.assign({}, FX); delete miss['1T'];
  assert.ok(!('fx' in f({at: now, fx: miss})), 'kursy bez jednej daty — nie z pliku');
  assert.ok(!('fx' in f({at: now, fx: FX, part_at: {fx: old}})), 'kursy starsze niż 36 h — nie z pliku');
  assert.ok('ust' in f({at: now, ust: [['2026-09-25', 5.17]], part_at: {ust: old}}) && !('ust' in f({at: now, ust: [['2026-09-25', 5.17]], part_at: {ust: vold}})), 'rentowności: do 4 dni');
  assert.deepEqual(f(null), {}); assert.deepEqual(f({at: 'x', fx: FX}), {});
  const g0 = html.indexOf('function gLoad(cb){'), g1 = html.indexOf('\n  Promise.all(P).then(', g0), G = html.slice(g0, g1);
  assert.ok(G.includes("srvJSON('rynki').then(j=>{const S=rynkiSrv(j),") && G.includes("S.ust?Promise.resolve().then(()=>use('ust',v=>{GLIVE.ust=v;})):gUstLoad()"), 'najpierw plik, zapas — dawny kod');
  assert.ok(!G.includes('gText(GSRC.ust(yr))') && html.includes('function gUstLoad(){'), 'pliki XML Skarbu USA tylko jako zapas');
  assert.ok(html.includes("due(15)?srvJSON('rynki').then(j=>{const S=rynkiSrv(j);if(S.fx&&GLIVE.fx){GLIVE.fx=S.fx;"), 'odświeżanie kursów co 15 min — też z pliku');
  assert.ok(html.includes("const MK={fx:'rynki_fx',ust:'rynki_ust',buba:'rynki_buba',") && html.includes("const PX={fx:'Frankfurter',ust:'Skarb USA 10L',buba:'Bundesbank 10L',"), 'Źródła: czas pliku i błąd z meta');
});
test('v102: tło — dwie warstwy ciągów, wolniejsze tempo, najwyżej jeden złoty ciąg naraz z przerwą; kolor złota z motywu', () => {
  const h0 = html.indexOf('/* ---------- tło: znaki szesnastkowe ---------- */'), h1 = html.indexOf('/* ---------- zegar ---------- */', h0), B = html.slice(h0, h1);
  assert.ok(B.includes('drops=Array.from({length:cols*2},(_,i)=>hNew(i<cols));'), 'dwa ciągi na kolumnę');
  assert.ok(B.includes('v:.10+Math.random()*.26') && !B.includes('.25+Math.random()*.55'), 'wolniej niż dotąd');
  assert.ok(B.includes('function hGoldPick(d,tm){if(!hGold&&d.on&&tm>=hGoldNext){d.gold=true;hGold=true;}}') && B.includes('if(d.gold){d.gold=false;hGold=false;hGoldNext=tm+8000+Math.random()*15000;}'), 'jeden złoty naraz, potem przerwa 8–23 s');
  assert.ok(B.includes('const tail=d.gold?PAL.hexGoldTail:PAL.hexTail,head=d.gold?PAL.hexGold:PAL.hexHead;') && B.includes("x=(i%cols)*CS"), 'złoty kolor głowy i ogona; kolumna z indeksu');
  assert.ok(html.includes('--hex-gold:255,214,10; --hex-gold-tail:214,178,48;') && html.includes('--hex-gold:176,124,0; --hex-gold-tail:168,136,40;') && html.includes("hexGold:g('--hex-gold')||'255,214,10'"), 'złoto w obu motywach');
  assert.ok(B.includes('const gi=Math.floor(cols*.37);') && B.includes('col=i===gi?PAL.hexGoldTail:PAL.hexTail'), 'obraz bez animacji też ma złoty ciąg');
});

// v103 (obszar „zrodla”): strona Źródła = karta stanu „na żywo” — zegar, czas ostatniego przebiegu z meta.json, liczba źródeł,
// zdanie o legalnych publicznych źródłach i tylko podpisy wymagane przez licencje (spis źródeł usunięty — decyzja właściciela 26.09)
const v103zr = (() => {
  const s0 = html.indexOf('/* ===================== v103: zrodla'), s1 = html.indexOf('\nfunction renderMethod(', s0);
  assert.ok(s0 > 0 && s1 > s0, 'blok v103 zrodla tuż przed renderMethod');
  const src = html.slice(s0, s1);
  const FRESH = new Date(Date.now() - 10 * 60000).toISOString();
  const k0 = html.indexOf('function kanLast(K){'), kanLast = new Function(html.slice(k0, html.indexOf('\n', k0)) + '\nreturn kanLast;')();   // prawdziwy kanLast strony (sprawdza kształt YYYY-MM)
  const render = (L, meta, noIco, KAN) => {
    const w = {innerHTML: ''}, I = noIco ? {} : v96src.H;
    const f = new Function('$', 't', 'GLIVE', 'engDate', 'gAgeNote', 'LOCALE', 'LANG', 'escH', 'icoWrap', 'glyphImg', 'flagImg', 'coinImg', 'KAN', 'kanLast', src + '\nrenderSources();\nreturn {zrCount, zrNow, zrCredits};');
    const r = f(q => q === '#page-sources' ? w : null, v96src.tFor(L), {meta}, iso => 'ED[' + iso + ']', d => ' · AGE[' + d + ']', {pl: 'pl-PL', en: 'en-US'}, L, v96src.escH, I.icoWrap, I.glyphImg, I.flagImg, I.coinImg, KAN, kanLast);
    r.out = w.innerHTML; return r;
  };
  const a = 'const EXTRA97=', x0 = html.indexOf(a); assert.ok(x0 > 0, 'słownik EXTRA97');
  const dict = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  return {src, render, dict, FRESH, L10: ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']};
})();

test('v103-zrodla: karta stanu — plakietka NA ŻYWO, zegar, czas odświeżenia z meta.json z wiekiem, „2 z 3” źródeł, zdanie właściciela', () => {
  const R = v103zr.render('pl', {at: v103zr.FRESH, ok: {a: true, b: 'cached', c: false}}), out = R.out;
  assert.ok(out.startsWith('<h1>Źródła</h1>'), 'nagłówek strony bez zmian');
  assert.ok(out.includes('<section class="panel zr-live">') && out.includes('<span class="live on"><i></i>NA ŻYWO</span>'), 'plakietka');
  const ck = out.match(/<b id="zr-clock" class="zr-clock">([^<]*)<\/b>/); assert.ok(ck && /\d/.test(ck[1]) && ck[1].includes(', '), 'zegar wypełniony od razu: ' + (ck && ck[1]));
  assert.ok(out.includes('Dane na serwerze odświeżone: <b>ED[' + v103zr.FRESH + ']</b> · AGE[' + v103zr.FRESH.slice(0, 10) + '] (co 20 minut, automatycznie)'), 'czas pliku meta + wiek danych: ' + out.slice(out.indexOf('Dane na serwerze'), out.indexOf('Dane na serwerze') + 160));
  assert.ok(out.includes('<p class="zr-count">W ostatnim przebiegu odpowiedziało 2 z 3 źródeł danych</p>'), 'true i cached = odpowiedź, false = brak');
  assert.deepEqual(R.zrCount({ok: {a: true, b: 'cached', c: false}}), {n: 2, m: 3});
  assert.ok(out.includes(v103zr.dict.pl['zr2.legal']) && out.includes('legalnych, publicznie dostępnych źródeł danych') && out.includes('publicznych sieci blockchain'), 'zdanie właściciela');
  assert.ok(out.includes('brak danych jest pokazywany jako „—”, nigdy jako zero'), 'nota o brakach');
  assert.ok(!out.includes('class="neu"') && !out.includes('Ostatni przebieg automatu') && !out.includes(v103zr.dict.pl['zr2.nometa']) && !out.includes(v103zr.dict.pl['zr2.noat']), 'świeży plik — bez ostrzeżeń');
  assert.ok(out.includes('img/glify/gauge.svg') && out.includes('img/glify/globe.svg') && out.includes('img/glify/coin.svg'), 'glify przy liniach karty');
  assert.ok(!out.includes('<table') && !out.includes('id="zr-attr"') && !out.includes('id="zr-icons"') && !out.includes('Czego celowo tu nie ma') && !out.includes('class="pgsub"'), 'bez tabeli źródeł, dawnych Atrybucji, „Czego nie ma” i podtytułu');
  assert.ok(/\d/.test(R.zrNow()) && R.zrNow().includes(', '));
});

test('v103-zrodla: bez pliku meta „—” z powodem i bez linii liczby źródeł; plik bez poprawnego czasu = inny powód; pusty ok = bez linii; stary plik = ostrzeżenie', () => {
  const NOMETA = v103zr.dict.pl['zr2.nometa'], NOAT = v103zr.dict.pl['zr2.noat'];
  assert.ok(NOMETA && NOAT && NOMETA !== NOAT && NOAT.includes('nie ma poprawnego czasu przebiegu'), 'dwa różne powody');
  // po przeglądzie: plik jeszcze nie pobrany (null/undefined) → „nie został jeszcze wczytany”; plik jest, ale bez użytecznego czasu → „nie ma poprawnego czasu”, bez obietnicy, że się pojawi
  const CASES = [[null, NOMETA], [undefined, NOMETA], [{}, NOAT], [{ok: null}, NOAT], [{ok: {a: true}}, NOAT], [{at: 'garbage', ok: {a: true}}, NOAT], [{at: '', ok: {a: true}}, NOAT],
    [{at: 1758834179000, ok: {a: true}}, NOAT], [{at: '2026-09-25', ok: {a: true}}, NOAT], [{at: null, ok: {a: true}}, NOAT]];
  for (const [meta, why] of CASES) {
    const out = v103zr.render('pl', meta).out, other = why === NOMETA ? NOAT : NOMETA;
    assert.ok(out.includes('Dane na serwerze odświeżone: <b class="na">—</b> (co 20 minut, automatycznie)'), 'bez czasu: ' + JSON.stringify(meta));
    assert.ok(out.includes('<p class="zr-count">' + why + '</p>') && !out.includes(other) && !out.includes('ED[') && !out.includes('AGE['), 'właściwy powód zamiast zmyślonego czasu: ' + JSON.stringify(meta) + ' → ' + out.slice(out.indexOf('<p class="zr-count">'), out.indexOf('<p class="zr-count">') + 90));
    assert.ok(!out.includes('W ostatnim przebiegu'), 'liczba źródeł tylko z datowanego pliku: ' + JSON.stringify(meta));
    assert.ok(out.includes('NA ŻYWO') && out.includes('id="zr-clock"') && out.includes(v103zr.dict.pl['zr2.legal']) && out.includes('Data by CoinGecko'), 'reszta karty zostaje');
  }
  const noOk = v103zr.render('pl', {at: v103zr.FRESH}).out;   // plik z czasem, ale bez ok: czas jest, liczba źródeł pominięta bez ostrzeżenia
  assert.ok(noOk.includes('<b>ED[' + v103zr.FRESH + ']</b>') && !noOk.includes('W ostatnim przebiegu') && !noOk.includes(NOMETA) && !noOk.includes(NOAT), 'czas bez ok');
  assert.ok(!v103zr.render('pl', {at: v103zr.FRESH, ok: {}}).out.includes('W ostatnim przebiegu'), 'pusty ok — bez „0 z 0”');
  const old = new Date(Date.now() - 30 * 3600e3).toISOString(), so = v103zr.render('pl', {at: old, ok: {a: true}}).out;
  assert.ok(so.includes('<b class="neu">ED[' + old + ']</b> · AGE[' + old.slice(0, 10) + ']') && so.includes('<p class="zr-count neu">Ostatni przebieg automatu jest starszy niż 3 godz.'), 'stary plik: czas na bursztynowo i ostrzeżenie');
  assert.ok(so.includes('W ostatnim przebiegu odpowiedziało 1 z 1 źródeł danych') && !so.includes(NOMETA) && !so.includes(NOAT));
  const R = v103zr.render('pl', null);
  assert.equal(R.zrCount(null), null); assert.equal(R.zrCount({}), null); assert.equal(R.zrCount({ok: {}}), null); assert.equal(R.zrCount({ok: 'x'}), null); assert.equal(R.zrCount({ok: []}), null);
  assert.deepEqual(R.zrCount({ok: {a: false}}), {n: 0, m: 1}, 'zero odpowiedzi to prawdziwa liczba, nie brak');
  assert.deepEqual(R.zrCount({ok: {a: true, b: 'cached', c: false, d: null}}), {n: 3, m: 4}, 'tylko false znaczy „bez odpowiedzi”');
  // brak elementu strony — bez błędu
  new Function('$', 't', 'GLIVE', v103zr.src + '\nrenderSources();')(() => null, k => k, {});
});

test('v103-zrodla: wszystkie klucze zr2 w 10 językach, foot.src = „Źródła” jak nav.sources, zdanie o źródłach w każdym języku, bez surowych kluczy', () => {
  const a0 = html.indexOf('function gAgeNote(fresh){'), a1 = html.indexOf('\n}', a0) + 2;
  const AGE = (L, days) => new Function('t', html.slice(a0, a1) + '\nreturn gAgeNote;')(v96src.tFor(L))(new Date(Date.now() - days * 86400000).toISOString().slice(0, 10));
  const d = v103zr.dict, KEYS = ['zr2.live', 'zr2.refresh', 'zr2.count', 'zr2.legal', 'zr2.note', 'zr2.attr', 'zr2.tv', 'zr2.icons', 'zr2.help', 'zr2.stale', 'zr2.nometa', 'zr2.noat', 'foot.src', 'pg.sources', 'g.age1', 'g.age'];
  assert.deepEqual(Object.keys(d).sort(), [...v103zr.L10].sort());
  for (const l of v103zr.L10) {
    assert.deepEqual(Object.keys(d[l]).sort(), [...KEYS].sort(), l + ': ten sam zestaw kluczy');
    for (const k of KEYS) assert.ok(typeof d[l][k] === 'string' && d[l][k].trim(), l + ' ' + k);
    assert.ok(d[l]['zr2.refresh'].includes('{t}') && d[l]['zr2.refresh'].includes('{age}') && d[l]['zr2.count'].includes('{n}') && d[l]['zr2.count'].includes('{m}') && d[l]['zr2.stale'].includes('{h}'), l + ': pola');
    assert.equal(d[l]['foot.src'], v96src.I18N[l]['nav.sources'], l + ': przycisk stopki = nazwa zakładki');
    assert.equal(d[l]['pg.sources'], v96src.I18N[l]['nav.sources'], l + ': nagłówek strony = nazwa zakładki (dawniej angielski „Sources” poza pl/en)');
    assert.ok(/country-flag-icons \(MIT\)/.test(d[l]['zr2.icons']) && /web3icons \(MIT\)/.test(d[l]['zr2.icons']) && /cryptocurrency-icons \(CC0\)/.test(d[l]['zr2.icons']), l + ': licencje ikon');
    assert.ok(d[l]['zr2.tv'].includes('TradingView'), l + ': TradingView');
    const out = v103zr.render(l, {at: v103zr.FRESH, ok: {a: true, b: false}}).out;
    assert.ok(out.startsWith('<h1>' + d[l]['pg.sources'] + '</h1>'), l + ': nagłówek w tym języku');
    assert.ok(out.includes(d[l]['zr2.legal']) && out.includes(d[l]['zr2.live']) && out.includes('<h2>' + d[l]['zr2.attr'] + '</h2>') && out.includes(d[l]['zr2.note']), l + ': strona w tym języku');
    assert.ok(!/zr2\./.test(out) && !out.includes('{n}') && !out.includes('{m}') && !out.includes('{t}') && !out.includes('{age}'), l + ': bez surowych kluczy i pól');
    assert.ok(out.includes(d[l]['zr2.count'].replace('{n}', '1').replace('{m}', '2')), l + ': 1 z 2');
    assert.ok(v103zr.render(l, {ok: {a: true}}).out.includes(d[l]['zr2.noat']) && !d[l]['zr2.noat'].includes('{'), l + ': plik bez czasu — powód w tym języku');
    // po przeglądzie: wiek danych („dane sprzed 1 dnia” / „{n} dni”) był tylko po polsku i angielsku — teraz w 10 językach, przez prawdziwe gAgeNote
    assert.ok(d[l]['g.age'].includes('{n}') && !d[l]['g.age1'].includes('{'), l + ': g.age z {n}, g.age1 bez pola');
    assert.equal(v96src.I18N[l]['g.age'], d[l]['g.age'], l + ': słownik strony ma wiek danych');
    assert.equal(AGE(l, 1), ' · ' + d[l]['g.age1'], l + ': 1 dzień'); assert.equal(AGE(l, 7), ' · ' + d[l]['g.age'].replace('{n}', '7'), l + ': 7 dni'); assert.equal(AGE(l, 0), ' · ' + v96src.I18N[l]['g.age0'], l + ': dziś');
    assert.ok(!/g\.age/.test(AGE(l, 1) + AGE(l, 7)), l + ': bez surowego klucza');
  }
  assert.equal(AGE('de', 1), ' · Daten von gestern'); assert.equal(AGE('ja', 3), ' · 3日前のデータ'); assert.equal(AGE('pl', 5), ' · dane sprzed 5 dni'); assert.equal(AGE('en', 1), ' · data 1 day old');
  assert.equal(d.pl['zr2.legal'], 'Wszystkie informacje na tej stronie pochodzą z legalnych, publicznie dostępnych źródeł danych — urzędów statystycznych, banków centralnych, ministerstw finansów, giełd i publicznych sieci blockchain — i są pobierane automatycznie, bez ręcznej obróbki.');
  assert.equal(d.pl['zr2.live'], 'NA ŻYWO'); assert.equal(d.en['zr2.live'], 'LIVE'); assert.equal(d.pl['foot.src'], 'Źródła');
  assert.ok(html.includes('for(const l in EXTRA97)if(I18N[l])Object.assign(I18N[l],EXTRA97[l]);\n'), 'słownik nałożony po EXTRA96');
  assert.ok(html.indexOf('Object.assign(I18N[l],EXTRA96[l]);') < html.indexOf('const EXTRA97='), 'EXTRA97 po EXTRA96');
  assert.equal(v96src.I18N.de['foot.src'], 'Quellen', 'przycisk stopki po niemiecku (dawniej angielski zapas)'); assert.equal(v96src.I18N.de['pg.sources'], 'Quellen'); assert.equal(v96src.I18N.pl['pg.sources'], 'Źródła');
  assert.equal(v96src.I18N.pl['zr2.help'], d.pl['zr2.help']);
});

test('v103-zrodla: bez nazw dostawców poza akapitem wymaganych podpisów; podpisy dosłownie; dawny kod strony Źródła usunięty, Metodologia nietknięta', () => {
  const out = v103zr.render('pl', {at: v103zr.FRESH, ok: {fred: true, sosovalue: 'cached'}}).out;
  const cutAt = out.indexOf('<section class="panel pgc zr-attr2">'); assert.ok(cutAt > 0, 'sekcja podpisów');
  const card = out.slice(0, cutAt), attr = out.slice(cutAt);
  const PROV = /Etherscan|EODHD|Tiingo|SoSoValue|Twelve Data|Finnhub|OECD|Bundesbank|CoinMarketCap|DefiLlama|CoinPaprika|Coin ?Metrics|FRED|Massive|Alpha Vantage|FMP|CryptoPanic|PublicNode|Frankfurter|Eurostat|\bBIS\b|\bMFW\b|\bIMF\b/;
  assert.ok(!PROV.test(card), 'karta stanu bez nazw dostawców: ' + (card.match(PROV) || [''])[0]);
  assert.ok(!/Etherscan|EODHD|Tiingo|SoSoValue|Twelve Data|Finnhub|CoinMarketCap|DefiLlama/.test(attr), 'podpisy tylko wymagane (bez dostawców, których warunki podpisu nie wymagają)');
  // po przeglądzie: noty, których wymagają warunki instytucji (były w dawnych Atrybucjach v96), wróciły jako druga linia tego samego akapitu — dosłownie, z linkami do licencji CC
  const CRED = ['Source: International Monetary Fund — International Liquidity (IL), COFER, Balance of Payments (BOP), Portfolio Investment Positions (PIP)',
    'Source: European Central Bank, Eurostat, Deutsche Bundesbank and Bank for International Settlements — reproduction is permitted provided the source is acknowledged',
    'Source: OECD (share price indices, 10-year yields, CLI) and World Bank (World Development Indicators) — <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener">CC BY 4.0</a>',
    'Source: Ministry of Finance, Japan — International Transactions in Securities, Public Data License (PDL) v1.0',
    'Adapted from Statistics Canada, Table 36-10-0028-01 International transactions in securities, portfolio transactions in Canadian and foreign securities, by type of instrument and issuer, monthly. This does not constitute an endorsement by Statistics Canada of this product.',
    'The reverse repo and SOMA data are subject to the Terms of Use posted at newyorkfed.org. The New York Fed is not responsible for publication of the data by CapitalFlowAI, does not sanction or endorse any particular republication, and has no liability for your use.',
    'Crypto Fear &amp; Greed Index: <a href="https://alternative.me/crypto/fear-and-greed-index/" target="_blank" rel="noopener">Alternative.me</a>',
    'Coin prices and market caps: <a href="https://coinpaprika.com" target="_blank" rel="noopener">CoinPaprika</a>'];
  for (const s of ['<h2>Wymagane podpisy</h2>', '<a href="https://www.coingecko.com" target="_blank" rel="noopener">Data by CoinGecko</a>',
    'This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis.',
    'Source: Coin Metrics Community Network Data (<a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" rel="noopener">CC BY-NC 4.0</a>)',
    'Widgety TradingView niosą własne oznaczenie w każdym widgecie.', 'Flagi: country-flag-icons (MIT) · loga kryptowalut i sieci: web3icons (MIT) · pozostałe loga monet: cryptocurrency-icons (CC0)', ...CRED]) {
    assert.ok(attr.includes(s), 'podpis: ' + s);
    assert.ok(!card.includes(s.replace(/<[^>]+>/g, '')), 'karta stanu bez podpisu: ' + s.slice(0, 40));
  }
  assert.equal((attr.match(/<p class="mtxt">/g) || []).length, 1, 'jeden akapit drobnym drukiem');
  assert.equal((attr.match(/<br>/g) || []).length, 1, 'noty instytucji w drugiej linii tego samego akapitu');
  assert.ok(attr.indexOf('cryptocurrency-icons (CC0)') < attr.indexOf('<br>') && attr.indexOf('<br>') < attr.indexOf(CRED[0]), 'kolejność: serwisy, ikony, potem instytucje');
  assert.equal((attr.match(/creativecommons\.org\/licenses\/by-nc\/4\.0\//g) || []).length, 1); assert.equal((attr.match(/creativecommons\.org\/licenses\/by\/4\.0\//g) || []).length, 1);
  assert.equal((html.match(/creativecommons\.org\/licenses\/by-nc\/4\.0\//g) || []).length, 1, 'link do licencji Coin Metrics wrócił (dawne ATTR_LINKS/ATTR_META usunięte)');
  assert.ok((attr.match(/<a href="https:\/\/[^"]+" target="_blank" rel="noopener">/g) || []).length >= 5, 'każdy link w nowej karcie, bez śledzenia');
  assert.ok(!attr.includes('undefined') && !attr.includes('null') && !attr.includes('{d}'), 'bez śmieci w podpisach');
  // Statistics Canada: licencja wymaga daty odniesienia — ostatni miesiąc z danych, gdy są; bez danych — bez daty (nigdy zmyślonej)
  const kanOut = v103zr.render('pl', {at: v103zr.FRESH, ok: {kanada: true}}, false, {data: {m: [['2026-06', 1], ['2026-07', 2]]}}).out;
  assert.ok(kanOut.includes('by type of instrument and issuer, monthly, 2026-07. This does not constitute an endorsement by Statistics Canada of this product.'), 'data odniesienia z danych: ' + kanOut.slice(kanOut.indexOf('monthly'), kanOut.indexOf('monthly') + 40));
  assert.ok(!v103zr.render('pl', {at: v103zr.FRESH, ok: {kanada: true}}, false, {data: {m: []}}).out.includes('monthly,'), 'puste dane — bez daty');
  assert.ok(!v103zr.render('pl', {at: v103zr.FRESH, ok: {kanada: true}}, false, {data: {m: 'x'}}).out.includes('monthly,'), 'zepsute dane — bez daty, bez błędu');
  const R0 = v103zr.render('pl', null); assert.ok(R0.zrCredits().startsWith('Source: International Monetary Fund') && R0.zrCredits().split(' · ').length === CRED.length, 'osiem not');
  assert.ok(!out.includes('sosovalue') && !out.includes('>fred'), 'klucze meta.ok (nazwy plików zbieracza) nie są wypisywane');
  const ni = v103zr.render('pl', {at: v103zr.FRESH, ok: {a: true}}, true).out;
  assert.ok(!ni.includes('class="icos"') && ni.includes('NA ŻYWO') && ni.includes('1 z 1') && ni.includes('Data by CoinGecko'), 'bez pomocników ikon — te same teksty');
  for (const s of ['const TXT_ZRODLA_PL=', 'const TXT_ZRODLA_EN=', 'function txtZrodla(', 'function attrHtml(', 'function iconsHtml(', 'const ATTR_LINKS=', 'const ATTR_META=', 'const SRC_EN=', 'const SRC_ICO=', 'function srcIco(', "t('zr.sub')", "t('pg.nosrc')", "t('pg.attr')", "t('zr.help')"])
    assert.ok(!html.includes(s), 'usunięte: ' + s);
  for (const s of ['const TXT_JAK_PL=`', 'const TXT_JAK_EN=`', 'const JAK_ICO=', 'function jakIco(', 'function txtJakCzytac(){', 'function renderMethod(){', '<section class="page" id="page-sources" hidden></section>', "else if(page==='sources')renderSources();", 'function metaErr(k){', 'metaLoad();setInterval('])
    assert.ok(html.includes(s), 'zostaje: ' + s);
  assert.equal((html.match(/function renderSources\(\)\{/g) || []).length, 1);
  assert.ok(v96src.render('pl', false, null).txtJakCzytac().includes('<h3>Jak często zmieniają się dane</h3>'), 'Metodologia renderuje się po zmianie');
});

test('v103-zrodla: tickClock dopisuje datę i godzinę do #zr-clock (i nie wywraca się bez niego); okno pomocy — nowe zdanie i przycisk „Źródła”; CSS strony', () => {
  const c0 = html.indexOf('function tickClock(){'), c1 = html.indexOf('\n}', c0) + 2, tc = html.slice(c0, c1);
  assert.ok(tc.includes("  el.innerHTML=dt+'<b>'+tm+'</b>';\n  const z=$('#zr-clock');if(z)z.textContent=dt+', '+tm;"), 'linia zegara strony Źródła zaraz po zegarze paska');
  const el = {innerHTML: ''}, z = {textContent: ''};
  const run = hasZ => new Function('$', 'LOCALE', 'LANG', tc + '\ntickClock();')(q => q === '#clock' ? el : (q === '#zr-clock' && hasZ ? z : null), {pl: 'pl-PL'}, 'pl');
  run(true);
  assert.ok(/\d/.test(z.textContent) && z.textContent === el.innerHTML.replace('<b>', ', ').replace('</b>', ''), 'ta sama data i godzina co w pasku: ' + z.textContent + ' | ' + el.innerHTML);
  z.textContent = 'x'; run(false); assert.equal(z.textContent, 'x', 'bez elementu — nic');
  const g0 = html.indexOf('function gHelpSrc(){'), g1 = html.indexOf('\n}', g0) + 2;
  const w = {innerHTML: ''}; new Function('$', 't', html.slice(g0, g1) + '\ngHelpSrc();')(q => q === '#gh-src' ? w : null, v96src.tFor('pl'));
  assert.equal(w.innerHTML, 'Dane pochodzą z legalnych, publicznych źródeł i są pobierane automatycznie; stan odświeżania: <button type="button" class="lnk" data-go="sources">Źródła</button>');
  const wd = {innerHTML: ''}; new Function('$', 't', html.slice(g0, g1) + '\ngHelpSrc();')(q => q === '#gh-src' ? wd : null, v96src.tFor('de'));
  assert.ok(wd.innerHTML.startsWith('Die Daten stammen aus legalen') && wd.innerHTML.endsWith('<button type="button" class="lnk" data-go="sources">Quellen</button>') && !wd.innerHTML.includes('zr2.'), 'po niemiecku: ' + wd.innerHTML);
  for (const s of ['/* v103 zrodla */', '#page-sources .zr-live{display:flex;flex-direction:column;', '#page-sources .zr-clock{display:block;', 'font-variant-numeric:tabular-nums', 'overflow-wrap:anywhere}', '@media (max-width:620px){#page-sources .zr-live{', '#page-sources .zr-refresh b.na{'])
    assert.ok(html.includes(s), 'CSS: ' + s);
  assert.ok(html.indexOf('/* v103 zrodla */') < html.indexOf('</style>') && html.indexOf('/* v103 zrodla */') > html.indexOf('<style>'), 'CSS w arkuszu strony');
  assert.ok(html.includes('<span data-i18n="foot.src"></span>'), 'przycisk stopki nadal ze słownika');
});
