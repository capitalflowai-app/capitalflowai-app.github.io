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
  for (const key of ['inst.tga', 'inst.rrp', 'inst.soma', 'inst.tgb.t', 'inst.mof.t', 'inst.not1']) assert.ok(html.includes(`"${key}":`), key);
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
  for (const l of ['pl', 'en']) for (const k of ['tic.t', 'tic.in', 'tic.out', 'tic.net', 'tic.not2', 'tic.src']) assert.ok(dict[l][k], l + ' ' + k);
});

// v48: uczciwość — zmiana wyceny to „zmiana wartości”; brak wymyślonych ocen, linii i liczb przykładowych na stronie publicznej
test('v48: słownik nadpisań ma wszystkie 10 języków i nie mówi o „napływie” tam, gdzie liczymy zmianę ceny', () => {
  const d0 = html.indexOf('const EXTRA36='), d1 = html.indexOf(';\n', d0);
  const dict = JSON.parse(html.slice(d0 + 'const EXTRA36='.length, d1));
  assert.deepEqual(Object.keys(dict).sort(), ['de', 'en', 'es', 'fr', 'it', 'ja', 'pl', 'pt', 'ru', 'zh']);
  for (const l of Object.keys(dict)) for (const k of ['plain.in', 'plain.out', 'g.leg.in', 'g.leg.out', 'q.src.v', 'rail.rel']) assert.ok(dict[l][k], l + ' ' + k);
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
  for (const l of ['pl', 'en']) for (const k of used) assert.ok(dict[l][k], l + ' ' + k);
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
  for (const l of ['pl', 'en']) for (const k of ['cftc.how', 'cftc.u.eth', 'cftc.not1', 'cftc.src', 'cftc.g.nonrept']) assert.ok(dict[l][k], l + ' ' + k);
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
  for (const l of ['pl', 'en']) for (const k of ['cm.t', 'cm.sub', 'cm.in', 'cm.out', 'cm.net', 'cm.s.in', 'cm.s.out', 'cm.tab', 'cm.not1', 'cm.not2', 'cm.not3', 'cm.src', 'cm.disc']) assert.ok(dict[l][k], l + ' ' + k);
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
    for (const sid of ['WSEFINTL1', 'WMTSECL1', 'WFASECL1', 'WSEFINOL']) assert.ok(dict[l]['inst.fred.src'].includes(sid), l + ' ' + sid);
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
  // v107: metaErr (błąd ostatniego przebiegu w wierszu dawnej tabeli źródeł) usunięta razem z tabelą — sprawdzenie metaErr wypadło
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
  for (const l of ['pl', 'en']) for (const k of ['sp.t', 'sp.sub', 'sp.src', 'sp.cc.XM', 'sp.cc.US']) assert.ok(dict[l][k], l + ' ' + k);
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
  // v107: mapy srvAt/metaErr (czas pliku i błąd w wierszu dawnej tabeli źródeł) usunięte razem z tabelą
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
  for (const l of ['pl', 'en']) for (const k of ['g.win', 'g.win.m', 'g.win.u', 'g.win.d', 'g.win.out', 'g.win.fz', 'g.win.miss', 'g.plain.none', 'g.src.regm', 'g.d.basey.v', 'bi.e.v', 'bi.e.none', 'bi.e.norep']) assert.ok(dict[l][k], l + ' ' + k);
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
  // v107: bez map srvAt/metaErr
  const x0 = html.indexOf('const EXTRA46='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA46='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ob.t', 'ob.sub', 'ob.in.k', 'ob.tw.k', 'ob.not', 'ob.src', 'ob.reg.v']) assert.ok(dict[l][k], l + ' ' + k);
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
  // v107: bez map srvAt/metaErr
  const x0 = html.indexOf('const EXTRA47='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA47='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['sp.c.fx', 'eer.not', 'eer.src', 'eer.reg', 'eer.reg.v']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes('html+=cofHtml(COF.data);') && html.includes("srvJSON('cofer')"));
  const x0 = html.indexOf('const EXTRA50='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA50='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['cof.t', 'cof.sub', 'cof.foot', 'cof.foot0', 'cof.not', 'cof.src']) assert.ok(dict[l][k], l + ' ' + k);
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
  for (const l of ['pl', 'en']) for (const k of ['sp.none.n', 'eer.reg.v', 'bi.e.norep', 'stc.t0', 'g.src.tdown']) assert.ok(dict[l][k], l + ' ' + k);
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
  // v107: bez map srvAt/metaErr
  const x0 = html.indexOf('const EXTRA55='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA55='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ob.t', 'ob.hk.k', 'ob.not.hk', 'ob.reg.hk.v']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes("html+=(typeof bilHtml==='function'&&typeof BIL!=='undefined')?bilHtml(BIL.data):'';") && html.includes("srvJSON('bilans')"));
  assert.ok(html.includes("${typeof bilRegion==='function'?bilRegion(s.id):''}"));
  const x0 = html.indexOf('const EXTRA58='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA58='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['bil.t', 'bil.sub', 'bil.c.t4', 'bil.more', 'bil.foot', 'bil.not', 'bil.src', 'bil.reg', 'bil.reg.v']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes("if(okD(j.br))gOk('obce_br');"));
  const x0 = html.indexOf('const EXTRA59='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA59='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['br.t', 'br.sub', 'br.fin', 'br.com', 'br.tot', 'br.not', 'br.src', 'br.reg', 'br.reg.v']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes("srvJSON('safe')"));
  const x0 = html.indexOf('const EXTRA60='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA60='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['sf.t', 'sf.sub', 'sf.cfa', 'sf.ca', 'sf.cust', 'sf.not', 'sf.src', 'sf.reg', 'sf.reg.v']) assert.ok(dict[l][k], l + ' ' + k);
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
    for (const k of ['br.sub', 'br.fin', 'br.fin.bs', 'br.reg.v', 'bil.c.o', 'bil.foot', 'bil.not', 'bil.reg.v', 'cftc.x.from', 'cftc.x.sub', 'inst.t', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes("if(okD(j.tr))gOk('obce_tr');"));
  assert.ok(html.includes('<span class="cell">nierezydenci w tureckich akcjach i obligacjach</span>'));
  const x0 = html.indexOf('const EXTRA62='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA62='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['tr.t', 'tr.sub', 'tr.tot', 'tr.eq', 'tr.gd', 'tr.not', 'tr.src', 'tr.reg', 'tr.reg.v', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes("html+=(typeof ueHtml==='function'&&typeof UE!=='undefined')?ueHtml(UE.data):'';") && html.includes("srvJSON('ue')"));
  assert.ok(html.includes("add('POL',t('fo.pol')"));
  const x0 = html.indexOf('const EXTRA64='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA64='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['ue.t', 'ue.sub', 'ue.c.t12', 'ue.foot', 'ue.not', 'ue.src', 'fo.pol', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes("add('CAN',t('fo.can')") && html.includes("srvJSON('kanada')"));
  const x0 = html.indexOf('const EXTRA66='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA66='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['kan.t', 'kan.sub', 'kan.tot', 'kan.not', 'kan.src', 'kan.reg.v', 'fo.can', 'fo.u.cad', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
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
  for (const l of ['pl', 'en']) for (const k of ['br.sub', 'br.bop.note', 'br.bop.split', 'br.reg.m', 'br.src', 'fo.bra', 'fo.bram', 'fo.sub', 'ue.foot', 'ue.not', 'kan.src', 'bil.not']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(html.includes("add('KOR',t('fo.kor')") && html.includes("srvJSON('korea')"));
  const x0 = html.indexOf('const EXTRA70='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA70='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['kor.t', 'kor.sub', 'kor.eq', 'kor.bd', 'kor.u', 'kor.usd', 'kor.12', 'kor.not', 'kor.src', 'kor.reg.v', 'fo.kor', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
  assert.ok(dict.pl['inst.sub'].includes('Korea'));
});

// v83: Korea — opisy zgodne z FSS (obligacje netto po wykupach, akcje KOSPI/KOSDAQ przy rozliczeniu), opóźnienie 9–31 dni, kurs miesięczny w przypisie
test('v83: Korea: opisy i opóźnienie zgodne ze źródłem', () => {
  const x0 = html.indexOf('const EXTRA71='), x1 = html.indexOf(';\n', x0), dict = JSON.parse(html.slice(x0 + 'const EXTRA71='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['kor.sub', 'kor.eq', 'kor.bd', 'kor.not', 'fo.kor', 'fo.foot']) assert.ok(dict[l][k], l + ' ' + k);
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
  assert.ok(d.pl['cftc.not4'].includes('ICE Futures U.S.'));
  assert.ok(d.pl['g.plain.cf'].startsWith('Waluty regionu „{r}”') && d.pl['g.plain.crypto'].includes('przybliżenie') && d.pl['g.stabflow'].includes('przybliżenie'));
  assert.ok(d.pl['g.q.srcv'].includes('Twelve Data') && d.pl['rail.in.g']);
  for (const l of ['de', 'fr', 'zh', 'ja']) assert.ok(d[l]['top.t'] && d[l]['g.q.limd'] && d[l]['g.help.limd'], l);
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
  assert.ok(html.includes("ses('th',7,'THA','fo.tha','fo.u.usdx');") && html.includes("if(okD(j.th))gOk('obce_th');"));
  assert.ok(html.includes('<span class="cell">nierezydenci w tajskich obligacjach</span>'));
  const dictOf = n => { const a = 'const EXTRA' + n + '=', x0 = html.indexOf(a); return JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0))); };
  const dict = dictOf(74), fix = dictOf(75);
  for (const l of ['pl', 'en']) for (const k of ['th.t', 'th.sub', 'th.nf', 'th.split', 'th.hold', 'th.hold.ch', 'th.not', 'th.src', 'th.reg.v', 'fo.tha', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
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
  // v107: bez map srvAt/metaErr
  assert.ok(html.includes('<span class="cell">nierezydenci w krajowych papierach skarbowych (zmiana stanu)</span>'));
  const a = 'const EXTRA76=', x0 = html.indexOf(a), dict = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  for (const l of ['pl', 'en']) for (const k of ['spw.t', 'spw.sub', 'spw.d1', 'spw.d1.n', 'spw.omni', 'spw.not', 'spw.src', 'spw.reg.v', 'spw.ty.omni', 'spw.rg.asia', 'fo.polspw', 'fo.u.pln', 'inst.sub']) assert.ok(dict[l][k], l + ' ' + k);
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
  // v107: bez map srvAt/metaErr
  assert.ok(html.includes('<span class="cell">nierezydenci w meksykańskich papierach rządowych (zmiana stanu)</span>'));
  assert.ok(html.includes('polskich (Ministerstwo Finansów) i meksykańskich (Banco de México).'));
  const a = 'const EXTRA78=', x0 = html.indexOf(a), dict = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  for (const l of ['pl', 'en']) for (const k of ['mx.t', 'mx.sub', 'mx.d', 'mx.d.n', 'mx.lv', 'mx.lv.n', 'mx.not', 'mx.src', 'mx.reg.v', 'fo.mex', 'fo.sub']) assert.ok(dict[l][k], l + ' ' + k);
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
  for (const m of html.matchAll(/const (EXTRA(?:8\d|9\d|1\d\d))=/g)) { const x = html.indexOf(m[0]), d = JSON.parse(html.slice(x + m[0].length, html.indexOf(';\n', x))); Object.assign(ALL.pl, d.pl || {}); Object.assign(ALL.en, d.en || {}); }
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
  for (const k of ['trd.e.t', 'trd.e.sub', 'trd.src.fe', 'trd.b.fe']) assert.ok(D.pl[k] && D.en[k], k);
  assert.ok(D.pl['trd.m.6'].includes('fundusze rynków wschodzących tworzą jednostki rzadko'), 'dni z zerem w funduszach EM opisane jako pomiar');
  assert.ok(html.includes("trdPanel('e',F.filter(r=>r.g==='fe'))+") && html.indexOf("trdPanel('e'") < html.indexOf("trdPanel('f'"), 'panel funduszy przed krajami');
  assert.ok(html.includes("'in_down','in_stop','out_up'") && html.includes("['in_down','in_stop','out_down','out_stop'].includes(r.st)"));
  // v107: bez map srvAt/metaErr
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
  assert.ok(D.pl['trd.src.cs'] && D.pl['trd.p.sub'].includes('fundusze zarządzające'));
  // v107: bez map srvAt/metaErr
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
  assert.ok(D.pl['trd.x.sub'].includes('Obligacji tu nie ma') && D.pl['trd.s.fe_util'].includes('USA'));
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
  assert.ok(D.pl['trd.b.concl3'].includes('Przepływy to nie ceny') && D.en['trd.b.concl3'].includes('Flows are not prices') && D.pl['trd.b.concl3'].includes('nie piszemy „kupuj”'));
  assert.ok(!('trd.b.concl2' in D.pl), 'v95.2: zwykły wniosek bez zmian');
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
  assert.ok(D.pl['nav.home'] && !D.pl['etf.src.snap'].includes('Ustawienia'));
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
  for (const m of html.matchAll(/const (EXTRA(?:8\d|9\d|1\d\d))=/g)) { const x = html.indexOf(m[0]); Object.assign(DP, JSON.parse(html.slice(x + m[0].length, html.indexOf(';\n', x))).pl || {}); }
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
  // v107: mapy srvAt/metaErr usunięte razem z dawną tabelą źródeł
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
  // v107: mapy srvAt/metaErr usunięte razem z dawną tabelą źródeł
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
  for (const s of ['const TXT_JAK_PL=`', 'const TXT_JAK_EN=`', 'const JAK_ICO=', 'function jakIco(', 'function txtJakCzytac(){', 'function renderMethod(){', '<section class="page" id="page-sources" hidden></section>', "else if(page==='sources')renderSources();", 'metaLoad();setInterval('])
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

// ===== v104 — obszar dzwignia: panel „Dźwignia i pozycje w krypto” (plik data/dzwignia.json) =====
const lev104 = (() => {
  const b0 = html.indexOf('/* ===================== v104: dźwignia i pozycje w krypto'), b1 = html.indexOf('function levAuto(){', b0);
  const blk = b0 > 0 && b1 > b0 ? html.slice(b0, html.indexOf('\n', b1)) : '';
  const T = (k, o) => k + (o ? '{' + Object.keys(o).map(a => a + '=' + o[a]).join(',') + '}' : '');   // bez cudzysłowów — podpisy kafelków przechodzą przez escH
  const escH = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const mk = (extra, tt) => {
    const el = {innerHTML: '', hidden: true, querySelectorAll() { return []; }, querySelector() { return null; }};
    const f = new Function('$', 't', 'escH', 'nfmt', 'fPct', 'sg', 'gAgeNote', 'LOCALE', 'LANG', 'srvJSON', 'engDate', ...Object.keys(extra),
      blk + '\nreturn {LEV, renderLev, levApply, levHist, levPart};')(() => el, tt || T, escH, (v, d = 0) => v.toFixed(d), (v, d = 1) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%',
      v => v > 0 ? '+' : v < 0 ? '−' : '', d => ' ·wiek(' + d + ')', {pl: 'pl-PL'}, 'pl', () => Promise.resolve(null), s => 'D:' + s, ...Object.values(extra));
    f.el = el; return f;
  };
  const now = new Date().toISOString(), today = now.slice(0, 10), yest = new Date(Date.now() - 864e5).toISOString().slice(0, 10), d2 = new Date(Date.now() - 2 * 864e5).toISOString().slice(0, 10);
  const fix = () => ({at: now, ok: {hl: true, bn: true, dr: true, okx: true}, part_at: {hl: now, bn: now, dr: now, okx: now},
    hl: {n: 234, top: ['BTC', 'ETH', 'HYPE', 'SOL', 'XRP'], f7_y: {BTC: 8.2, ETH: null}, rows: {
      BTC: {f_h: 0.0000125, f_y: 10.95, oi: 37688.3, oi_usd: 3162290812, px: 83895, d1: -0.337, vol_usd: 2577312373},
      ETH: {f_h: -0.00001, f_y: -8.76, oi: 1104443.3, oi_usd: 2968019557, px: 2687.37, d1: 0.312, vol_usd: 839906068},
      HYPE: {f_h: 0.0000125, f_y: 10.95, oi: 1, oi_usd: 1877000000, px: 40, d1: 0, vol_usd: null},
      SOL: {f_h: null, f_y: null, oi: 5683459.5, oi_usd: 684000000, px: 120.39, d1: 3.39, vol_usd: 598530337},
      XRP: {f_h: 0.0000125, f_y: 10.95, oi: 197101732, oi_usd: 305882000, px: 1.5519, d1: 1.33, vol_usd: 225105356}}},
    bn: {day: d2, BTC: {t: d2 + ' 21:10:00', n: 254, last: {oi: 95949.275, oi_usd: 8088522776.3, ls: 1.2262, top_ls: 1.3198, top_pos: 1.9252, taker: 1.0832},
      mean: {oi: 97000, oi_usd: 8200000000, ls: 1.19, top_ls: 1.31, top_pos: 1.91, taker: 1.3}},
      ETH: {t: d2 + ' 23:15:00', n: 288, last: {oi: 2272548.5, oi_usd: 6104472058.4, ls: 0.7, top_ls: 1.5279, top_pos: 1.5613, taker: null}, mean: {oi: null, oi_usd: null, ls: 2.72, top_ls: null, top_pos: null, taker: null}}},
    dr: {BTC: {dvol: {v: 34.67, v24: 35.2, d1: -1.506, t: now}, opt: {oi: 351282.7, oi_p: 120393.5, oi_c: 230889.2, pc: 0.5214, n: 998, px: 83914, exp: [[ '2026-12-25', 118793.6], ['2026-10-30', 117025.8], ['2027-03-26', 34480.3], ['2026-10-02', 25707.7]], t: now}},
      ETH: {dvol: {v: 48.21, v24: 48.0, d1: 0.437, t: now}, opt: {oi: 1232994, oi_p: 700000, oi_c: 532994, pc: 1.3134, n: 856, px: 2687, exp: [['2026-12-25', 528141]], t: now}}},
    okx: {BTC: {t: now, f: 0.0000210707, f_hours: 8, f_y: 2.307, oi_usd: 2395706135.5, oi: 28559.68, ls: 1.36, ls_t: yest + 'T16:00:00+00:00'}, ETH: {t: now, f: -0.0000041437, f_hours: 8, f_y: -0.454, oi_usd: 1601902860.3, oi: 596334.24, ls: 1.0, ls_t: yest + 'T16:00:00+00:00'}},
    hist: [{d: d2, hl_btc: 3000000000, hl_eth: 3100000000, dvol_btc: 36, dvol_eth: 50, bn_btc: 8088522776.3, bn_eth: 6104472058.4},
           {d: today, hl_btc: 3162290812, hl_eth: 2968019557, f_btc: 10.95, f_eth: -8.76, dvol_btc: 34.67, dvol_eth: 48.21}]});
  return {blk, mk, fix, now, today, yest, d2, T};
})();

test('v104-dzwignia: panel — kafelki z kolorami wg kierunku, brak = „—” (nie zero), nazwy giełd dozwolone, bez nazw dostawców', () => {
  assert.ok(lev104.blk.length > 1000, 'blok v104 w stronie');
  const f = lev104.mk({});
  f.levApply(null);
  assert.ok(f.el.hidden && f.el.innerHTML === '', 'bez pliku — sekcja ukryta');
  f.levApply(lev104.fix());
  const h = f.el.innerHTML;
  assert.ok(!f.el.hidden && h.includes('<h2>lev.t</h2>') && h.includes('lev.sub') && h.includes('inst.file{t=D:' + lev104.now + '}'), 'tytuł, podtytuł, czas pliku');
  assert.ok(h.includes('lev.k.fund{c=BTC}</span><b class="pos">+10.9% <small class="pos">lev.f7{v=+8.2%}</small></b>'), 'finansowanie BTC dodatnie — zielone, ze średnią 7 dni: ' + h.slice(h.indexOf('lev.k.fund'), h.indexOf('lev.k.fund') + 200));
  assert.ok(h.includes('lev.k.fund{c=ETH}</span><b class="neg">−8.8% <small>lev.f.h{v=−0.0010%}</small></b>'), 'finansowanie ETH ujemne — czerwone, bez średniej 7 dni → stawka godzinowa');
  assert.ok(h.includes('lev.k.oi{c=BTC}</span><b>3.16 <small class="mtxt">lev.u.mld</small> <small><span class="pos">lev.dn{n=2,v=+5.4%}</span></small></b>'), 'otwarte pozycje BTC ze zmianą wobec wpisu sprzed 2 dni (prawdziwy odstęp): ' + h.slice(h.indexOf('lev.k.oi{c=BTC}'), h.indexOf('lev.k.oi{c=BTC}') + 220));
  assert.ok(h.includes('lev.k.oi{c=ETH}</span><b>2.97 <small class="mtxt">lev.u.mld</small> <small><span class="neg">lev.dn{n=2,v=−4.3%}</span></small></b>'), 'otwarte pozycje ETH — spadek na czerwono');
  assert.ok(h.includes('<b class="pos">1.23 <small class="pos">lev.more.long · lev.mean{v=1.19} · lev.topacc{v=1.32} · lev.top{v=1.93}</small></b><small class="mtxt">lev.bnday{d='), 'Binance BTC: więcej długich, średnia dnia, najwięksi gracze, dzień pliku');
  assert.ok(h.includes('<b class="neg">0.70 <small class="neg">lev.more.short · lev.mean{v=2.72} · lev.topacc{v=1.53} · lev.top{v=1.56}</small></b>'), 'Binance ETH: więcej krótkich — czerwono');
  assert.ok(h.includes('lev.k.taker{c=BTC}</span><b class="pos">1.30 <small class="pos">lev.more.buy · lev.last5{v=1.08}</small></b>'), 'kupno/sprzedaż BTC: nagłówek, kolor i słowa ze średniej dnia (1,30), ostatnie 5 min (1,08) tylko w dopisku: ' + h.slice(h.indexOf('lev.k.taker{c=BTC}'), h.indexOf('lev.k.taker{c=BTC}') + 160));
  assert.ok(h.includes('lev.k.taker{c=ETH}</span><b class="na">— <small>eng.gap</small></b>'), 'brak stosunku kupno/sprzedaż ETH — „—” z powodem, nie zero');
  const asof = 'lev.asof{t=D:' + lev104.now + ' ·wiek(' + lev104.today + ')}';
  assert.ok(h.includes('lev.tab.sub{n=234} · ' + asof + '</p>'), 'tabela kontraktów ma własną datę części (stan na): ' + h.slice(h.indexOf('lev.tab.sub'), h.indexOf('lev.tab.sub') + 120));
  assert.ok(h.includes('lev.k.oib{c=ETH}</span><b>6.10 <small class="mtxt">lev.u.mld</small></b>') && !h.includes('lev.mean{v=0.00'), 'otwarte pozycje ETH koniec dnia bez średniej (brak, nie zero)');
  assert.ok(h.includes('lev.k.dvol{c=BTC}</span><b>34.7 <small class="neg">lev.dn{n=1,v=−1.5%}</small></b>'), 'DVOL BTC: spadek o 1,5 % — czerwono');
  assert.ok(h.includes('lev.k.dvol{c=ETH}</span><b>48.2 <small class="neu">lev.dn{n=1,v=+0.4%}</small></b>'), 'DVOL ETH: zmiana w granicach ±1 % — żółto');
  assert.ok(h.includes('lev.k.pc{c=BTC}</span><b class="pos">0.52 <small class="pos">lev.more.call</small></b>') && h.includes('lev.k.pc{c=ETH}</span><b class="neg">1.31 <small class="neg">lev.more.put</small></b>'), 'put/call: poniżej 1 zielono (więcej calli), powyżej 1 czerwono (więcej putów)');
  assert.ok(h.includes('<td><span class="cell">OKX</span></td><td><span class="cell">ETH</span></td><td><span class="cell mono neg">−0.5%</span></td><td><span class="cell mono">1.60</span></td><td><span class="cell mono">1.00<small>'), 'tabela giełd: OKX ETH — finansowanie ujemne czerwono, stosunek 1,00 bez koloru');
  assert.ok(h.includes('<td><span class="cell">Binance</span></td><td><span class="cell">BTC</span></td><td><span class="cell mono na" title="lev.np">—</span></td><td><span class="cell mono">8.09</span></td><td><span class="cell mono pos">1.23</span></td>'), 'tabela giełd: Binance nie publikuje finansowania — „—” z podpowiedzią');
  assert.ok(h.includes('<td><span class="cell">Hyperliquid</span></td><td><span class="cell">BTC</span></td><td><span class="cell mono pos">+10.9%</span></td><td><span class="cell mono">3.16</span></td><td><span class="cell mono na" title="lev.np">—</span></td>'), 'tabela giełd: Hyperliquid bez stosunku kont');
  const tab = h.slice(h.indexOf('lev.h.tab'), h.indexOf('lev-opt'));
  assert.ok(tab.indexOf('>BTC<') < tab.indexOf('>ETH<') && tab.indexOf('>ETH<') < tab.indexOf('>HYPE<') && tab.indexOf('>HYPE<') < tab.indexOf('>SOL<'), 'tabela Hyperliquid w kolejności otwartych pozycji');
  assert.ok(tab.includes('<td><span class="cell mono na">—</span></td>') && tab.includes('<span class="cell mono">0.0%</span>') && !tab.includes('cell mono pos">0.0%') && tab.includes('lev.tab.sub{n=234}'), 'SOL bez finansowania — „—”; zmiana 0,0 % bez koloru');
  assert.ok(h.includes('lev.opt.tot{v=351283,c=BTC,u=29.48,pc=0.52} · ' + asof + '</p>') && h.includes('<span class="cell mono">33.8%</span>'), 'opcje wg terminu: razem, ≈ USD, put/call, data części, udział terminu');
  assert.ok(!h.includes('·wiek(2026-12-25)') && !h.includes('·wiek(2026-10-30)'), 'termin wygaśnięcia nie dostaje „wieku danych”');
  assert.ok(h.includes('<summary>eng.notsays</summary><p class="pnote">lev.not1</p>') && h.includes('lev.not6</p></details><p class="pfoot">inst.file{t=D:' + lev104.now + '} · eng.disclaimer</p>'), '„Czego te dane nie mówią” i stopka');
  assert.ok(!/CoinGlass|Coinglass|Coin Metrics|Etherscan|EODHD|Tiingo|CryptoPanic|Alpha Vantage|Massive/.test(h), 'bez nazw dostawców');
  assert.ok((h.match(/class="etfk"/g) || []).length === 18, '18 kafelków: 4 razem (v109), 4 Hyperliquid, 6 Binance, 4 Deribit; jest ' + (h.match(/class="etfk"/g) || []).length);
});

test('v104-dzwignia: część nieaktualna albo brakująca = brak (nie stare liczby bez daty); zmiana z historii; chwilowy błąd nie kasuje danych', () => {
  const f = lev104.mk({});
  const j = lev104.fix();
  j.part_at.bn = new Date(Date.now() - 5 * 864e5).toISOString();   // część Binance starsza niż 4 dni
  delete j.okx;
  f.levApply(j);
  let h = f.el.innerHTML;
  assert.ok(!h.includes('lev.h.bn') && !h.includes('lev.k.ls') && !h.includes('>Binance<'), 'stara część Binance pominięta w kafelkach i w tabeli giełd');
  assert.ok(!h.includes('>OKX<') && h.includes('>Hyperliquid<'), 'bez części OKX zostają pozostałe giełdy');
  assert.equal(f.levHist('hl_btc', 1).n, 2); assert.equal(f.levHist('hl_btc', 7), null, 'brak wpisu sprzed 7 dni — brak zmiany, nie zero');
  assert.equal(f.levHist('dvol_eth', 1).pct.toFixed(2), '-3.58');
  f.levApply({at: 'x'});
  assert.ok(!f.el.hidden && f.el.innerHTML === h, 'zły plik po dobrym — poprzednie dane zostają');
  const g = lev104.mk({});
  const k = lev104.fix(); k.hist = [{d: lev104.today, hl_btc: 1}];
  g.levApply(k);
  assert.ok(g.el.innerHTML.includes('<b>3.16 <small class="mtxt">lev.u.mld</small> <small>lev.nohist</small></b>'), 'pierwszy dzień historii — bez porównania, z powodem');
  const e = lev104.mk({}); e.levApply({at: lev104.now, ok: {}, part_at: {}});
  assert.ok(e.el.hidden, 'plik bez części — sekcja ukryta');
  // kupno/sprzedaż: średnia dnia poniżej 1 przy ostatnim oknie powyżej 1 — nagłówek, kolor i słowa ze średniej; bez średniej — „—”, ostatnie okno nie zastępuje nagłówka
  const tk = lev104.mk({}); const jt = lev104.fix(); jt.bn.ETH.mean.taker = 0.66; jt.bn.ETH.last.taker = 1.2; jt.bn.BTC.mean.taker = null;
  tk.levApply(jt); const ht = tk.el.innerHTML;
  assert.ok(ht.includes('lev.k.taker{c=ETH}</span><b class="neg">0.66 <small class="neg">lev.more.sell · lev.last5{v=1.20}</small></b>'), 'średnia dnia 0,66 → „więcej sprzedaży” na czerwono, ostatnie 5 min 1,20 w dopisku: ' + ht.slice(ht.indexOf('lev.k.taker{c=ETH}'), ht.indexOf('lev.k.taker{c=ETH}') + 160));
  assert.ok(ht.includes('lev.k.taker{c=BTC}</span><b class="na">— <small>eng.gap</small></b>') && !ht.includes('lev.last5{v=1.08}'), 'bez średniej dnia — „—”, nie ostatnie okno');
  // część Deribit zachowana z wcześniejszego przebiegu: opcje pokazują własny czas części, nie czas pliku
  const od = lev104.mk({}); const jd = lev104.fix(); const older = new Date(Date.now() - 864e5).toISOString(); jd.part_at.dr = older; jd.dr.BTC.opt.t = older; jd.dr.ETH.opt.t = older;
  od.levApply(jd);
  assert.ok(od.el.innerHTML.includes('lev.opt.tot{v=351283,c=BTC,u=29.48,pc=0.52} · lev.asof{t=D:' + older + ' ·wiek(' + lev104.yest + ')}'), 'opcje z zachowanej części — data tej części z wiekiem');
});

test('v104-dzwignia: ikony (loga monet i giełd, Hyperliquid = logo sieci, Deribit = znaczek), sekcja w CRYPTO, ładowanie i odświeżanie, CSS', () => {
  const I = v96src.H;
  const f = lev104.mk({coinImg: I.coinImg, exchImg: I.exchImg, glyphImg: I.glyphImg});
  f.levApply(lev104.fix());
  const h = f.el.innerHTML;
  assert.ok(h.includes('<h2><span class="icos"><img class="ico" src="img/krypto/btc.svg" alt="" title="BTC" loading="lazy" decoding="async"><img class="ico" src="img/krypto/eth.svg"'), 'loga BTC i ETH w tytule');
  assert.ok(h.includes('img/sieci/hyper-evm.svg') && h.includes('img/gieldy/binance.svg') && h.includes('img/gieldy/okx.svg') && /class="iss sm"[^>]*title="Deribit"/.test(h), 'Hyperliquid — logo sieci, Binance i OKX — loga, Deribit — znaczek z literami');
  const tiles = h.split('<div class="etfk">').slice(1);
  tiles.forEach((x, i) => assert.ok(/^<span><span class="icos">.+?<\/span>lev\./.test(x), 'kafelek ' + i + ' ma ikonę przed podpisem'));
  assert.ok(h.includes('<span class="icos"><img class="ico sm" src="img/krypto/btc.svg"') && /title="HYPE"/.test(h), 'w tabeli logo BTC i znaczek dla HYPE');
  assert.ok(html.includes('    <section class="panel pcard" id="eng-cftc-crypto" hidden></section>\n    <section class="panel pcard" id="c-dzwignia" hidden></section>'), 'sekcja tuż po panelu CFTC krypto (zakładka CRYPTO)');
  assert.ok(html.includes("function levLoad(){srvJSON('dzwignia')") && html.includes('levLoad();levAuto();try{new MutationObserver(()=>renderLev())') && html.includes('LEV.timer=setInterval(()=>{if(!document.hidden)levLoad();},30*60*1000);'), 'plik automatu, odświeżanie co 30 min, zmiana języka');
  assert.ok(html.includes('/* v104 dzwignia') && html.includes('#c-dzwignia .etfk span.icos{display:inline-flex') && html.includes('#c-dzwignia .etfk b small.neu{color:var(--yl-tx)}') && html.includes('#c-dzwignia .etfk b span{display:inline'), 'CSS tylko dla #c-dzwignia');
});

test('v104-dzwignia: 10 języków z tymi samymi kluczami lev.*, po niemiecku bez surowych kluczy, teksty nie nazywają pozycji przepływem', () => {
  const a = 'const EXTRA98=', x0 = html.indexOf(a);
  assert.ok(x0 > 0 && html.includes('for(const l in EXTRA98)if(I18N[l])Object.assign(I18N[l],EXTRA98[l]);'), 'słownik EXTRA98 podpięty');
  const D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.deepEqual(Object.keys(D).sort(), ['de', 'en', 'es', 'fr', 'it', 'ja', 'pl', 'pt', 'ru', 'zh']);
  const keys = Object.keys(D.pl).sort();
  assert.ok(keys.length >= 50 && keys.every(k => k.startsWith('lev.')));
  for (const L of Object.keys(D)) {
    assert.deepEqual(Object.keys(D[L]).sort(), keys, L);
    for (const k of keys) { const ph = (D.pl[k].match(/\{[a-z]+\}/g) || []).sort(); assert.deepEqual((D[L][k].match(/\{[a-z]+\}/g) || []).sort(), ph, L + ' ' + k); }
  }
  assert.ok(D.pl['lev.t'] === 'Dźwignia i pozycje w krypto' && D.en['lev.t'] === 'Leverage and positioning in crypto');
  assert.ok(!/napływ|odpływ/i.test(Object.values(D.pl).join(' ')), 'pozycje to stan, nie przepływ — bez słów „napływ”/„odpływ”');
  for (const L of ['de', 'ja']) {
    const f = lev104.mk({}, v96src.tFor(L));
    f.levApply(lev104.fix());
    assert.ok(!/lev\.[a-z]/.test(f.el.innerHTML.replace(/id="lev-[a-z]+"/g, '').replace(/lev-opt/g, '')), L + ': bez surowych kluczy: ' + (f.el.innerHTML.match(/lev\.[a-z.]+/) || [])[0]);
  }
  const de = lev104.mk({}, v96src.tFor('de')); de.levApply(lev104.fix());
  assert.ok(de.el.innerHTML.includes('Hebel und Positionierung in Krypto') && de.el.innerHTML.includes('mehr Longs'));
  const ja = lev104.mk({}, v96src.tFor('ja')); ja.levApply(lev104.fix());
  assert.ok(ja.el.innerHTML.includes('3.16 <small class="mtxt">十億ドル</small>') && !/10 億ドル|100 万ドル/.test(ja.el.innerHTML) && D.ja['lev.c.vol'].includes('百万ドル'), 'jednostki po japońsku jak w słowniku bazowym (十億ドル, 百万ドル)');
  assert.ok(!/publikuje|publish|veröffentlicht|publica|publie|pubblica|публикует|公布|公表/.test(Object.values(D).map(x => x['lev.np']).join(' ')) && D.pl['lev.np'].includes('źródle'), '„—” w tabeli giełd: brak w naszym źródle, nie „giełda nie publikuje”');
  assert.ok(D.pl['lev.k.taker'].includes('średnia dnia') && D.pl['lev.last5'].startsWith('ostatnie 5 min') && D.pl['lev.asof'] === 'stan na {t}', 'nowe podpisy: średnia dnia, ostatnie 5 min, stan na');
});
test('v105: wieloryby — pomocnicze: kształt pliku, kwoty, zmiana wobec zrzutu, skrót transakcji, zero bez koloru', () => {
  const w0 = html.indexOf('/* ===================== v105: wieloryby'), w1 = html.indexOf('\nfunction whTile(', w0);
  assert.ok(w0 > 0 && w1 > w0, 'blok v105 w stronie');
  const T = (k, v) => k + (v ? JSON.stringify(v) : '');
  const W = new Function('t', 'nfmt', html.slice(w0, w1) + '\nreturn {whOk, whAmt, whChg, whDay, whShort, whDelta};')(T, (v, d) => Number(v).toFixed(d));
  const now = new Date().toISOString();
  assert.ok(W.whOk({at: now, salda: {Binance: {eth: 1}}}) && W.whOk({at: now, transfery: [], okno: 10}), 'plik z saldami albo z oknem transferów');
  assert.ok(!W.whOk(null) && !W.whOk({at: 'x', salda: {Binance: {}}}) && !W.whOk({at: now, salda: {}}) && !W.whOk({at: now, transfery: []}) && !W.whOk('tekst'), 'bez czasu, bez sald, bez okna — nie');
  assert.equal(W.whAmt(2345678901, 'USDT'), '2.35 wh.u.mld USDT'); assert.equal(W.whAmt(1500000), '1.5 wh.u.mln'); assert.equal(W.whAmt(462013.4, 'ETH'), '462013 ETH'); assert.equal(W.whAmt(-999600000), '−1.00 wh.u.mld');
  assert.equal(W.whAmt(null), '—'); assert.equal(W.whAmt('1'), '—'); assert.equal(W.whAmt(NaN), '—');
  assert.equal(W.whDay('2026-09-26', -1), '2026-09-25'); assert.equal(W.whDay('2026-03-01T10:00:00+00:00', -7), '2026-02-22'); assert.equal(W.whDay('x', -1), '');
  const H = [['2026-09-19', '2026-09-19T00:05:00+00:00', 10, 100, 1000], ['2026-09-25', '2026-09-25T00:07:00+00:00', 12, 130, 900], ['2026-09-26', '2026-09-26T00:03:00+00:00', 13, 131, null]];
  assert.deepEqual(W.whChg(H, '2026-09-26', 1, 3, 150), {d: 20, t: '2026-09-25T00:07:00+00:00'}, 'zmiana wobec zrzutu z poprzedniej doby');
  assert.deepEqual(W.whChg(H, '2026-09-26', 7, 4, 900), {d: -100, t: '2026-09-19T00:05:00+00:00'}, 'zmiana wobec zrzutu sprzed 7 dni');
  assert.equal(W.whChg(H, '2026-09-27', 1, 4, 900), null, 'zrzut bez liczby (null) — brak, nie zero');
  assert.equal(W.whChg(H, '2026-09-28', 1, 3, 150), null, 'brak zrzutu z poprzedniej doby — brak');
  assert.deepEqual(W.whChg(H, '2026-09-26', 1, 4, 900), {d: 0, t: '2026-09-25T00:07:00+00:00'}, 'równe salda: zmiana 0 (prawdziwe zero, bez koloru w whDelta)');
  assert.equal(W.whChg(H, '2026-09-26', 1, 3, null), null); assert.equal(W.whChg(null, '2026-09-26', 1, 3, 1), null);
  assert.equal(W.whShort('0x' + 'ab'.repeat(32)), '0xabab…abab'); assert.equal(W.whShort('0x12'), ''); assert.equal(W.whShort(null), '');
  assert.deepEqual(W.whDelta(2500000), {txt: '▲ +2.5 wh.u.mln', cls: 'pos'}); assert.deepEqual(W.whDelta(-3), {txt: '▼ −3', cls: 'neg'});
  assert.deepEqual(W.whDelta(0.4), {txt: '• 0', cls: ''}, 'zero po zaokrągleniu — bez strzałki i koloru'); assert.deepEqual(W.whDelta(-0.3), {txt: '• 0', cls: ''});
});
test('v105: wieloryby — panel z pliku: kafle z datą i wiekiem, tabela z linkiem, stan pusty, bez pliku ukryty, brak nie jest zerem', () => {
  const w0 = html.indexOf('/* ===================== v105: wieloryby'), w1 = html.indexOf('\nfunction whApply(', w0);
  const T = (k, v) => (k.startsWith('wh.n.') ? 'nota:' + k : k) + (v ? JSON.stringify(v) : '');   // nota giełdy tylko, gdy klucz istnieje
  const run = D => {
    const el = {innerHTML: '', hidden: true, querySelectorAll: () => [], querySelector: () => null};
    new Function('$', 't', 'nfmt', 'escH', 'engDate', 'gAgeNote', 'icoWrap', 'coinImg', 'exchImg', 'netImg', 'D', html.slice(w0, w1) + '\nWH.data=D;renderWh();')(
      q => q === '#c-wieloryby' ? el : null, T, (v, d) => Number(v).toFixed(d), v96src.escH, s => '[' + String(s) + ']', d => ' · age(' + String(d).slice(0, 10) + ')',
      x => `<span class="icos">${x}</span>`, (s, c) => `<i class="ico ${c}">${s}</i>`, (s, c) => `<i class="ico ${c}">${s}</i>`, (s, c) => `<i class="ico ${c}">${s}</i>`, D);
    return el;
  };
  const now = new Date().toISOString(), tx = '0x' + '1a'.repeat(32);
  const D = {at: now, eth_usd: 2688.87, eth_usd_at: now, okno: 4800, okno_od: 100, okno_od_t: '2026-09-25T16:00:00+00:00', ostatni_blok: 4899, ostatni_t: '2026-09-26T08:00:00+00:00',
    gieldy: {Binance: {n: 9, since: '2022-11', tokeny: ['USDT', 'USDC', 'ETH']}, OKX: {n: 10, since: '2026-09-08', tokeny: ['USDC']}},
    salda: {Binance: {eth: 462013.4, usdt: 2345678901, usdc: 1500000, usd: 3.6e9, blk: 4899, t: '2026-09-26T08:00:00+00:00', n: 9},
      OKX: {eth: 12.5, usdt: 0, usdc: 1580000000, usd: null, blk: 4899, t: '2026-09-26T08:00:00+00:00', n: 10}},
    hist: {Binance: [['2026-09-25', '2026-09-25T00:07:00+00:00', 462000, 2300000000, 1500000], ['2026-09-26', '2026-09-26T00:03:00+00:00', 462013.4, 2345678901, 1500000]]},
    transfery: [{t: '2026-09-26T07:12:00+00:00', token: 'USDT', amt: 2000000, dir: 'in', exch: 'Binance', tx, blk: 4890},
      {t: '2026-09-26T05:00:00+00:00', token: 'USDC', amt: 12500000.5, dir: 'out', exch: 'OKX', tx: 'zły-hash', blk: 4700}, {t: 'x', token: 'USDT', amt: 5e6, dir: 'in', exch: 'Binance', tx, blk: 1},
      {t: '2026-09-26T06:00:00+00:00', token: 'USDC', amt: 3000000, dir: 'out', exch: 'OKX', tx, blk: 4850, wew: true}]};
  const el = run(D), out = el.innerHTML;
  assert.ok(!el.hidden && out.includes('wh.t') && out.includes('wh.sub') && out.includes('inst.file{"t":"[' + now + ']"}'), 'nagłówek i czas pliku');
  assert.ok(out.includes('Binance · USDT') && out.includes('2.35 wh.u.mld USDT') && out.includes('462013 ETH') && out.includes('Binance · wh.k.usd') && out.includes('3.60 wh.u.mld USD'), 'kafle Binance: ' + out.slice(0, 300));
  assert.ok(out.includes('<small class="pos">▲ +45.7 wh.u.mln · wh.vs{"t":"[2026-09-25T00:07:00+00:00]"}</small>'), 'zmiana USDT od zrzutu z poprzedniej doby, zielona');
  assert.ok(out.includes('<small class="na">wh.d7: — · wh.short</small>'), '7 dni bez zrzutu — brak z powodem');
  assert.ok(out.includes('OKX · USDC') && !out.includes('OKX · ETH') && !out.includes('OKX · USDT') && !out.includes('OKX · wh.k.usd'), 'OKX: tylko USDC (lista tokenów z pliku)');
  assert.ok(out.includes('<small class="na">— · wh.nochg</small>'), 'OKX bez historii — brak wcześniejszego zrzutu, nie zero');
  assert.ok(out.includes('wh.blk{"t":"[2026-09-26T08:00:00+00:00]","n":"4899"} · age(2026-09-26)'), 'data i wiek salda');
  assert.ok(out.includes('wh.wal{"n":"9","d":"2022-11"}') && out.includes('<span class="whn">nota:wh.n.OKX</span>') && out.includes('nota:wh.n.Binance'), 'liczba portfeli, data listy, nota giełdy: ' + out.slice(out.indexOf('wh.wal'), out.indexOf('wh.wal') + 120));
  assert.ok(out.includes('wh.tr.sub{"a":"[2026-09-25T16:00:00+00:00]","b":"[2026-09-26T08:00:00+00:00]","n":"4800"}'), 'okno transferów z czasami bloków');
  const rows = out.split('<tr><td>').length - 1;
  assert.equal(rows, 3, 'wiersz bez czasu odrzucony');
  assert.ok(out.indexOf('12.5 wh.u.mln USDC') < out.indexOf('3.0 wh.u.mln USDC') && out.indexOf('3.0 wh.u.mln USDC') < out.indexOf('2.0 wh.u.mln USDT'), 'malejąco wg kwoty');
  assert.ok(out.includes('<span class="cell neu wew">▼ wh.out · <span class="icos"><i class="ico sm">OKX</i></span>OKX<small class="whx">wh.wew</small></span>'), 'para „ta sama kwota w obie strony”: bursztyn (kierunek niejasny) i dopisek, wiersz zostaje');
  assert.equal((out.match(/class="cell neu wew"/g) || []).length, 1, 'oznaczenie tylko przy wierszu z wew');
  assert.ok(out.includes(`<a href="https://etherscan.io/tx/${tx}" target="_blank" rel="noopener" title="wh.tx.open">0x1a1a…1a1a</a>`), 'link do transakcji z krótkim hashem');
  assert.ok(out.includes('<span class="cell pos">▲ wh.in · <span class="icos"><i class="ico sm">Binance</i></span>Binance</span>') && out.includes('<span class="cell neg">▼ wh.out · <span class="icos"><i class="ico sm">OKX</i></span>OKX</span>'), 'kierunek: strzałka, słowa, kolor, logo i nazwa giełdy');
  assert.equal((out.match(/<th>/g) || []).length, 4, 'cztery kolumny');
  assert.ok(out.includes('class="cell mono">—</span>'), 'zły hash — bez linku, kreska');
  assert.ok(!/Etherscan|Chainlink|CoinGecko|PublicNode|publicnode/.test(out.replace(/href="[^"]*"/g, '')), 'bez nazw dostawców w tekście panelu (tylko w adresie linku)');
  assert.ok(out.includes('wh.px{"p":"2689","t":"[' + now + ']"}') && out.includes('wh.not1') && out.includes('wh.not4') && out.includes('wh.foot') && out.includes('eng.disclaimer'), 'kurs, „czego nie mówią”, stopka');
  const E = run(Object.assign({}, D, {transfery: [], eth_usd: null, salda: Object.assign({}, D.salda, {Binance: Object.assign({}, D.salda.Binance, {usd: null})})}));
  assert.ok(E.innerHTML.includes('wh.tr.none{"a":') && E.innerHTML.includes('wh.px.na') && !E.innerHTML.includes('wh.px{') && !E.innerHTML.includes('<table'), 'pusty stan: brak dużych transferów w oknie, brak kursu i suma „—” = nota o braku kursu');
  const E2 = run(Object.assign({}, D, {eth_usd: null}));
  assert.ok(!E2.innerHTML.includes('wh.px.na') && !E2.innerHTML.includes('wh.px{') && E2.innerHTML.includes('3.60 wh.u.mld USD'), 'brak kursu w pliku, ale sumy w USD pokazane (poprzednie salda) — bez sprzecznej noty „brak kursu”');
  const E3 = run(Object.assign({}, D, {eth_usd: null, salda: {OKX: D.salda.OKX}}));
  assert.ok(!E3.innerHTML.includes('wh.px.na') && !E3.innerHTML.includes('wh.px{'), 'giełda bez kafla „razem w USD” (sama USDC) nie wywołuje noty o braku kursu');
  const N = run(Object.assign({}, D, {salda: {Binance: {eth: null, usdt: 2e9, usdc: 1e6, usd: null, blk: 4899, t: '2026-09-26T08:00:00+00:00', n: 9}}, hist: {}}));
  assert.ok(N.innerHTML.includes('Binance · ETH</span><b>—') && N.innerHTML.includes('— <small class="na">wh.usd.na</small>'), 'saldo bez liczby = „—”, suma bez kursu = „—” z powodem');
  const Z = run(null);
  assert.ok(Z.hidden && Z.innerHTML === '', 'bez pliku sekcja ukryta');
  assert.equal(html.split('<section class="panel pcard" id="c-wieloryby" hidden></section>').length, 2, 'jedna sekcja');
  const c0 = html.indexOf('<section class="panel pcard" id="eng-coinmetrics-exchange-flows" hidden></section>');
  assert.ok(html.indexOf('id="c-wieloryby"') > c0 && html.indexOf('id="c-wieloryby"') < c0 + 200, 'CRYPTO: zaraz po przepływach na giełdy');
  assert.ok(html.includes("srvJSON('wieloryby').then(whApply)") && html.includes('20*60*1000') && html.includes("attributeFilter:['lang']});}catch(e){}   /* v105"), 'plik serwera, odświeżanie co 20 min, zmiana języka');
});
test('v105: wieloryby — dziesięć języków ma wszystkie klucze wh.*, bez nazw dostawców, z zastrzeżeniem „pomiar, nie kupno”', () => {
  const keys = Object.keys(v96src.I18N.pl).filter(k => k.startsWith('wh.'));
  assert.ok(keys.length >= 30 && keys.includes('wh.t') && keys.includes('wh.tr.none') && keys.includes('wh.n.OKX'), 'klucze: ' + keys.length);
  const PROV = /Etherscan|Chainlink|CoinGecko|PublicNode|Allnodes|Coin Metrics/i;
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    for (const k of keys) { assert.ok(v96src.I18N[L][k] && t(k) !== k, L + ' ' + k); assert.ok(!PROV.test(t(k)), 'dostawca: ' + L + ' ' + k); }
    for (const [k, ph] of [['wh.wal', ['{n}', '{d}']], ['wh.vs', ['{t}']], ['wh.blk', ['{t}', '{n}']], ['wh.tr.sub', ['{a}', '{b}', '{n}']], ['wh.tr.none', ['{n}', '{a}', '{b}']], ['wh.px', ['{p}', '{t}']]])
      for (const p of ph) assert.ok(v96src.I18N[L][k].includes(p), 'symbol ' + p + ' w ' + L + ' ' + k);
  }
  assert.ok(v96src.tFor('pl')('wh.sub').includes('nie kupna ani sprzedaży') && v96src.tFor('en')('wh.sub').includes('not buying or selling'), 'pomiar sald, nie kupno');
  assert.ok(v96src.tFor('pl')('wh.tr.none').includes('nie jest zero') && v96src.tFor('en')('wh.tr.none').includes('not zero'), 'pusty stan nie jest zerem');
  assert.ok(keys.includes('wh.wew') && !v96src.tFor('pl')('wh.px.na').includes('aktualne') && !v96src.tFor('en')('wh.px.na').includes('current'), 'nota o braku kursu nie twierdzi, że salda są aktualne (mają własną datę)');
  assert.ok(v96src.tFor('pl')('wh.not2').includes('nieogłoszony portfel') && v96src.tFor('en')('wh.not2').includes('unpublished exchange wallet'), '„czego nie mówią”: para z nieogłoszonego portfela');
});
test('v106: indeksy świata — zmiany z sesji indeksu (1 D, 1 T, 1 M, od początku roku), luki i święta, brak ≠ zero, kolejność, ukryte bez danych', () => {
  const i0 = html.indexOf('/* ===================== v106: INDEKSY GIEŁDOWE ŚWIATA'), i1 = html.indexOf('\nfunction ixLoad(', i0);
  assert.ok(i0 > 0 && i1 > i0, 'blok v106 na stronie');
  const mk = ($) => new Function('$', 't', 'nfmt', 'fPct', 'sg', 'escH', 'gAgeNote', 'engDate', 'LOCALE', 'LANG', html.slice(i0, i1) +
    '\nreturn {IX, IX_META, ixRows, ixDerive, ixTone, ixPct, ixItems, ixSort, ixBody, ixCty, renderIx, ixApply, ixEtfClose, ixEtfSeries};')(
    $ || (() => null), (k, o) => k + (o ? JSON.stringify(o) : ''), (v, d) => Number(v).toFixed(d), (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%',
    v => v > 0 ? '+' : v < 0 ? '−' : '', s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])), d => ' · age(' + d + ')', iso => 'D(' + iso + ')', {pl: 'pl-PL', en: 'en-US'}, 'en');
  const X = mk();
  // 30 sesji: 8.12.2025 – 20.01.2026 bez weekendów, bez 25.12 i 1.01 (święta); zamknięcia 100, 101, 102, …
  const days = []; for (let d = new Date(Date.UTC(2025, 11, 8)); days.length < 30; d.setUTCDate(d.getUTCDate() + 1)) { const iso = d.toISOString().slice(0, 10); if (d.getUTCDay() % 6 && iso !== '2025-12-25' && iso !== '2026-01-01') days.push(iso); }
  const rows = days.map((d, i) => [d, 100 + i]);
  assert.equal(days[16], '2025-12-31'); assert.equal(days[29], '2026-01-20');
  const v = X.ixDerive(rows), near = (a, b, m) => assert.ok(Math.abs(a - b) < 1e-9, m + ': ' + a + ' vs ' + b);
  assert.equal(v.date, '2026-01-20'); assert.equal(v.close, 129); assert.equal(v.n, 30);
  near(v.d1, (129 / 128 - 1) * 100, '1 D = poprzednia sesja'); near(v.w1, (129 / 124 - 1) * 100, '1 T = 5 sesji'); near(v.m1, (129 / 108 - 1) * 100, '1 M = 21 sesji');
  near(v.ytd, (129 / 116 - 1) * 100, 'od początku roku = ostatnie zamknięcie 2025 (31.12), nie 1.01');
  const junk = rows.slice().reverse().concat([['2026-01-21', null], ['2026-01-22', 0], ['2026-01-23', -1], ['bad', 5], 'x', ['2026-01-26']]);
  assert.deepEqual(X.ixDerive(junk), v, 'kolejność dowolna, wiersze bez liczby (null, 0, ujemne, zła data) odrzucone — nigdy zero');
  const s = X.ixDerive(rows.slice(-10));
  assert.ok(s.d1 !== null && s.w1 !== null && s.m1 === null && s.ytd === null, 'za krótka seria: 1 M i od początku roku = brak, nie 0');
  assert.equal(X.ixDerive([]), null); assert.equal(X.ixDerive(null), null); assert.equal(X.ixDerive([['2026-01-20', 5]]).d1, null);
  assert.equal(X.ixTone(0.04, 1), ''); assert.equal(X.ixTone(0.06, 1), 'pos'); assert.equal(X.ixTone(-0.06, 1), 'neg'); assert.equal(X.ixTone(null, 1), '');
  assert.equal(X.ixPct(0.04), '<span class="cell mono">0.0%</span>', 'zero po zaokrągleniu — bez koloru i bez znaku');
  assert.equal(X.ixPct(-0.06), '<span class="cell mono neg">−0.1%</span>'); assert.equal(X.ixPct(2.345), '<span class="cell mono pos">+2.3%</span>');
  assert.equal(X.ixPct(null), '<span class="cell mono na">—</span>'); assert.equal(X.ixPct(NaN), '<span class="cell mono na">—</span>');
  const it = X.ixItems({ix: {GSPC: {d: rows}, ZZZ: {d: rows}, DJI: {d: []}, FCHI: 'x', GDAXI: {d: rows.slice(-3)}, N225: {bad_at: '2026-01-15T10:00:00+00:00', bad_n: 1, bad: 403}}});
  assert.equal(it.length, 24, 'część ix istnieje — wiersz dla każdego indeksu z listy (nieznany ZZZ pominięty); v119: 23 EODHD + FTSE z FMP');
  assert.deepEqual(it.filter(x => x.close !== null).map(x => x.sym), ['GSPC', 'GDAXI'], 'seria tylko dla znanych kodów z danymi');
  const by = Object.fromEntries(it.map(x => [x.sym, x]));
  assert.ok(by.DJI.close === null && by.DJI.m1 === null && by.DJI.why === 'none' && by.FCHI.why === 'none' && by.KS11.why === 'none', 'bez serii: brak (null) z powodem, nie zero');
  assert.ok(by.N225.why === 'bad' && by.N225.bad_at === '2026-01-15T10:00:00+00:00' && by.N225.close === null, 'kod odrzucony — powód „bad” z datą');
  assert.ok(!('ZZZ' in by));
  assert.deepEqual(X.ixSort(it, 'm1').map(x => x.sym).slice(0, 2), ['GSPC', 'GDAXI'], 'z wartością najpierw, potem z zamknięciem bez 1 M, bez danych na końcu');
  assert.ok(X.ixSort(it, 'm1').slice(2).every(x => x.close === null));
  assert.equal(X.ixItems({ix: {}}).length, 0, 'część ix pusta — bez wierszy'); assert.equal(X.ixItems({}).length, 0);
  const it2 = [{name: 'B', m1: 1}, {name: 'A', m1: null}, {name: 'C', m1: 5}, {name: 'Z', m1: NaN}];
  assert.deepEqual(X.ixSort(it2, 'm1').map(x => x.name), ['C', 'B', 'A', 'Z']);
  const D = {at: '2026-01-21T06:00:00+00:00', ix: {GSPC: {d: rows}, GDAXI: {d: rows.map((r, i) => [r[0], 300 - i])}}};
  const body = X.ixBody(D);
  assert.ok(body.includes('<table class="etft">') && (body.match(/<tr><td>/g) || []).length === 2 && (body.match(/<tr class="ix-na"><td>/g) || []).length === 22 && !/undefined|NaN|\[object/.test(body), body.slice(0, 300));
  assert.equal((body.match(/ix\.nodata/g) || []).length, 22, 'każdy indeks bez serii: wiersz „—” z powodem „jeszcze nie pobrano”');
  assert.equal((body.match(/<span class="cell mono na">—<\/span>/g) || []).length, 22 * 5, 'zamknięcie i cztery zmiany = „—”, nie zero');
  assert.ok(body.indexOf('S&amp;P 500') < body.indexOf('DAX') && body.indexOf('DAX') < body.indexOf('ix.nodata'), 'kolejność wg 1 M: rosnący, spadający, potem bez danych');
  assert.ok(body.includes('ix.k.upv{"n":"1","m":"2"}') && body.includes('ix.k.upn{"d":') && body.includes('age(2026-01-20)'), 'kafle: licznik, najnowsza sesja z wiekiem');
  assert.ok(body.includes('<td><span class="cell mono">129.00</span></td>') && body.includes('class="cell mono pos">+19.4%') && body.includes('class="cell mono neg">'), 'zamknięcie z 2 miejscami, zmiany w kolorze');
  assert.ok(body.includes('ix.k.best') && body.includes('ix.k.worst') && body.includes('ix.k.ybest') && body.includes('ix.k.yworst') && body.includes('ix.note'));
  assert.ok(!body.includes('ix.c.date'), 'data i wiek w wierszu pod nazwą, nie w osobnej kolumnie');
  const one = X.ixBody({at: 'x', ix: {GSPC: {d: rows}, N225: {bad_at: '2026-01-15T10:00:00+00:00', bad_n: 2, bad: 403}}});
  assert.ok(one.includes('ix.k.best') && one.includes('ix.k.ybest') && !one.includes('ix.k.worst') && !one.includes('ix.k.yworst'), 'jeden indeks z wartością: bez kafli „najsłabszy” (nie ten sam indeks dwa razy)');
  assert.ok(one.includes('ix.k.upv{"n":"1","m":"1"}') && one.includes('ix.bad{"d":"') && one.includes('2026') && (one.match(/ix\.nodata/g) || []).length === 22, 'kod odrzucony: powód z datą; reszta „jeszcze nie pobrano”');
  assert.equal(X.ixBody({at: 'x', ix: {}}), ''); assert.equal(X.ixBody(null), '');
  assert.equal(X.ixBody({at: 'x', ix: {GSPC: {bad_at: 'x', bad_n: 1, bad: 403}, IXIC: {d: []}}}), '', 'same znaczniki przerw, żadnej serii — panel ukryty');
  const el = {hidden: false, innerHTML: 'x'}, Y = mk(q => q === '#g-indeksy' ? el : null);
  Y.renderIx(); assert.ok(el.hidden === true && el.innerHTML === '', 'bez danych — sekcja ukryta, bez pustego panelu');
  Y.ixApply({at: new Date().toISOString(), etf: {q: {SPY: [['2026-01-20', 1]]}}}); assert.equal(el.hidden, true, 'plik bez części ix (klucz jeszcze nie dodany) — ukryta');
  Y.ixApply({at: new Date().toISOString(), ix: {GSPC: {bad_at: '2026-01-15T10:00:00+00:00', bad_n: 1, bad: 403}}}); assert.equal(el.hidden, true, 'plik z samymi znacznikami (klucz odrzucony) — ukryta');
  const now = new Date().toISOString();
  Y.ixApply({at: now, ix: D.ix, etf: {q: {SPY: [['2026-09-24', 690.12], ['2026-09-23', 688], ['2026-09-25', null]]}}});
  assert.ok(el.hidden === false && el.innerHTML.includes('ix.t') && el.innerHTML.includes('inst.file{"t":"D(' + now + ')"}') && el.innerHTML.includes('eng.notsays') && el.innerHTML.includes('ix.not') && el.innerHTML.includes('eng.disclaimer'));
  assert.deepEqual(Y.ixEtfClose('spy'), {date: '2026-09-24', close: 690.12}, 'zapas cen ETF: ostatnie zamknięcie z datą'); assert.equal(Y.ixEtfClose('QQQ'), null);
  assert.deepEqual(Y.ixEtfSeries('SPY'), [['2026-09-23', 688], ['2026-09-24', 690.12]]);
  Y.ixApply(null); assert.equal(el.hidden, false, 'chwilowy błąd pobrania nie zasłania danych');
  const Z = mk(q => q === '#g-indeksy' ? el : null);
  Z.ixApply({at: now, part_at: {ix: new Date(Date.now() - 40 * 864e5).toISOString()}, ix: D.ix}); assert.equal(el.hidden, true, 'część ix starsza niż 30 dni — ukryta');
  Z.ixApply({at: new Date(Date.now() - 40 * 864e5).toISOString(), ix: D.ix}); assert.equal(el.hidden, true);
  assert.equal(Object.keys(X.IX_META).length, 24);
  for (const k in X.IX_META) assert.ok(/^[a-z]{2}$/.test(X.IX_META[k][0]) && X.IX_META[k][1], k);
});
test('v106: indeksy — słownik w 10 językach bez nazw dostawców; sekcja, styl i plik na miejscu', () => {
  const KEYS = ['ix.t', 'ix.sub', 'ix.c.idx', 'ix.c.close', 'ix.c.1d', 'ix.c.1w', 'ix.c.1m', 'ix.c.ytd', 'ix.k.up', 'ix.k.upv', 'ix.k.upn', 'ix.k.best', 'ix.k.worst', 'ix.k.ybest', 'ix.k.yworst', 'ix.note', 'ix.not', 'ix.nodata', 'ix.bad', 'inst.file'];
  const PROV = /EODHD|Massive|Polygon|Tiingo|Twelve|Finnhub|Alpha Vantage|FMP|Yahoo|Stooq/i;
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const tt = v96src.tFor(L);
    assert.ok(v96src.I18N[L] && KEYS.every(k => typeof v96src.I18N[L][k] === 'string' && v96src.I18N[L][k].trim()), 'wszystkie klucze: ' + L);
    for (const k of KEYS) assert.ok(!PROV.test(tt(k)) && !tt(k).includes('{v}'), L + ' ' + k);
    const u = tt('ix.k.upv', {n: '7', m: '25'});
    assert.ok(u.includes('7') && u.includes('25') && !u.includes('{'), L + ' ' + u);
    assert.ok(tt('ix.k.upn', {d: 'XYZ'}).includes('XYZ') && !tt('ix.k.upn', {d: 'XYZ'}).includes('{'), L + ' upn');
    assert.ok(tt('ix.bad', {d: 'XYZ'}).includes('XYZ') && !tt('ix.bad', {d: 'XYZ'}).includes('{'), L + ' bad');
    assert.ok(v96src.I18N[L]['inst.file'].includes('{t}') && tt('inst.file', {t: 'QQ'}).includes('QQ'), L + ' inst.file w języku strony (nie po angielsku)');
  }
  assert.equal(v96src.I18N.pl['inst.file'], 'Plik z {t}'); assert.equal(v96src.I18N.en['inst.file'], 'File from {t}');
  assert.ok(v96src.I18N.de['inst.file'] !== v96src.I18N.en['inst.file'] && v96src.I18N.ja['inst.file'] !== v96src.I18N.en['inst.file'], 'luka słownika „Plik z …” zamknięta');
  assert.ok(v96src.tFor('pl')('ix.sub').includes('nie zmierzony przepływ') && v96src.tFor('en')('ix.sub').includes('not a measured flow'), 'zmiana indeksu ≠ przepływ');
  assert.equal(html.split('<section class="panel pcard" id="g-indeksy" hidden></section>').length, 2, 'jedno miejsce sekcji');
  const u = html.indexOf('<section class="panel pcard" id="g-usa" hidden></section>'), x = html.indexOf('<section class="panel pcard" id="g-indeksy" hidden></section>');
  assert.ok(x > u && x < u + 300, 'zaraz po panelu USA (zakładka GLOBAL)');
  assert.ok(html.includes("srvJSON('indeksy')") && html.includes('/* v106 indeksy */') && html.includes('#g-indeksy .etft{min-width:0;width:100%}'), 'plik, styl');
  assert.ok(html.includes('const EXTRA100=') && html.includes('for(const l in EXTRA100)if(I18N[l])Object.assign(I18N[l],EXTRA100[l]);'), 'słownik EXTRA100 dołączony');
  assert.ok(html.includes("if(!ok&&IX.data)return;") && html.includes("60*60*1000") && html.includes("attributeFilter:['lang']})") , 'odświeżanie co 60 min, zmiana języka');
  assert.equal(html.split('/* ===================== v106: INDEKSY GIEŁDOWE ŚWIATA').length, 2);
});
test('v106.1: wspólne napisy paneli przetłumaczone w 10 językach (dotąd angielski zapas w 8)', () => {
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L), en = v96src.tFor('en');
    for (const k of ['eng.notsays', 'eng.disclaimer', 'eng.gap', 'inst.exact', 'inst.asof']) {
      assert.ok(t(k) !== k, L + ' ' + k);
      if (!['pl', 'en'].includes(L)) assert.notEqual(t(k), en(k), 'przetłumaczone: ' + L + ' ' + k);
    }
    assert.ok(t('inst.exact').includes('{v}'), 'symbol {v} zachowany: ' + L);
  }
  assert.ok(html.includes('for(const l in EXTRA101)if(I18N[l])Object.assign(I18N[l],EXTRA101[l]);'));
});

// ===== v109 — obszar dzwignia2: więcej giełd (Kraken Futures, Coinbase International, dYdX) i rząd „wszystkie giełdy razem” =====
const lev109 = (() => {
  const now = lev104.now, old7 = new Date(Date.now() - 7 * 3600e3).toISOString();
  const row = (f_y, oi, px, vol_usd, t) => ({f_h: f_y / (24 * 365 * 100), f_y, f_hours: 1, oi, oi_usd: oi === null ? null : Math.round(oi * px), px, vol: null, vol_usd, t});
  const fix = () => {   // plik v104 + trzy nowe części (liczby z nagrań 26.09) + wpis historii sprzed 2 dni z sumą tego samego zestawu giełd (BTC) i innego (ETH)
    const j = lev104.fix();
    Object.assign(j.ok, {kr: true, cb: true, dy: true}); Object.assign(j.part_at, {kr: now, cb: now, dy: now});
    j.kr = {t: now, f_hours: 1, BTC: Object.assign(row(-2.637, 2175.3188, 84005.9, 321113985, now), {sym: 'PF_XBTUSD'}), ETH: Object.assign(row(2.85, 26150.793, 2690.16, 91647374, now), {sym: 'PF_ETHUSD'})};
    j.cb = {t: now, f_hours: 1, BTC: row(7.008, 1075.7102, 84012.9, 3692548262, now), ETH: row(5.256, 17069.0224, 2690, 2555737254, now)};
    j.dy = {t: now, f_hours: 1, BTC: row(-0.691, 190.2829, 83979.1, 2793172, now), ETH: row(-43.943, 6080.201, 2688.87, 38816887, now)};
    j.hist[0].all_btc = 5.5e9; j.hist[0].all_btc_v = 'cb,dy,hl,kr,okx'; j.hist[0].all_eth = 4.5e9; j.hist[0].all_eth_v = 'cb,dy,hl,okx';
    return j;
  };
  const fp = v => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(1) + '%';
  return {fix, old7, fp, VEN: 'Hyperliquid, OKX, Kraken, Coinbase, dYdX'};
})();

test('v109-dzwignia2: „wszystkie giełdy razem” — suma z giełd z bieżącym stanem, Binance poza sumą, średnia ważona pozycjami, zmiana dzienna tylko przy tym samym zestawie giełd', () => {
  const f = lev104.mk({}); const j = lev109.fix(); f.levApply(j); const h = f.el.innerHTML;
  const S = j.hl.rows.BTC.oi_usd + j.okx.BTC.oi_usd + j.kr.BTC.oi_usd + j.cb.BTC.oi_usd + j.dy.BTC.oi_usd, pct = (S / j.hist[0].all_btc - 1) * 100;
  const i0 = h.indexOf('lev.h.all'); assert.ok(i0 > 0 && i0 < h.indexOf('lev.h.hl') && h.includes('lev.all.sub'), 'rząd „razem” przed Hyperliquid, z podtytułem');
  const want = 'lev.k.oiall{c=BTC}</span><b>' + (S / 1e9).toFixed(2) + ' <small class="mtxt">lev.u.mld</small> <small>lev.sumof{n=5,v=' + lev109.VEN + '} · <span class="pos">lev.dn{n=2,v=' + lev109.fp(pct) + '}</span> · lev.bnout{v=8.09 lev.u.mld,d=';
  assert.ok(h.includes(want), 'suma BTC z 5 giełd, zmiana wobec wpisu sprzed 2 dni, Binance poza sumą: ' + h.slice(h.indexOf('lev.k.oiall{c=BTC}'), h.indexOf('lev.k.oiall{c=BTC}') + 320));
  assert.ok(h.includes('lev.k.oiall{c=ETH}</span><b>') && h.includes('lev.sumof{n=5,v=' + lev109.VEN + '} · lev.diffn · lev.bnout{v=6.10 lev.u.mld,d='), 'ETH: dzień wcześniej inny zestaw giełd — bez zmiany, z powodem');
  const L = [[10.95, j.hl.rows.BTC.oi_usd], [2.307, j.okx.BTC.oi_usd], [j.kr.BTC.f_y, j.kr.BTC.oi_usd], [j.cb.BTC.f_y, j.cb.BTC.oi_usd], [j.dy.BTC.f_y, j.dy.BTC.oi_usd]];
  const w = L.reduce((a, r) => a + r[1], 0), avg = L.reduce((a, r) => a + r[0] * r[1], 0) / w;
  assert.ok(avg > 5 && avg < 10, 'średnia ważona między OKX a Hyperliquid: ' + avg);
  assert.ok(h.includes('lev.k.fall{c=BTC}</span><b class="pos">' + lev109.fp(avg) + ' <small>lev.wof{n=5,v=' + lev109.VEN + '}</small></b><small class="mtxt">D:' + lev104.now + ' ·wiek(' + lev104.today + ')</small>'), 'średnia ważona, dodatnia — zielono, data najstarszego zdjęcia stanu: ' + h.slice(h.indexOf('lev.k.fall{c=BTC}'), h.indexOf('lev.k.fall{c=BTC}') + 300));
  assert.ok(/lev\.k\.fall\{c=ETH\}<\/span><b class="neg">−/.test(h), 'ETH: średnia ujemna — czerwono');
  assert.ok((h.match(/class="etfk"/g) || []).length === 18, '18 kafelków');
  const k = lev104.mk({}); const jj = lev104.fix(); k.levApply(jj); const hh = k.el.innerHTML;   // plik sprzed v109: suma z dwóch giełd, historia bez sum → „historia dopiero się buduje”
  assert.ok(hh.includes('lev.sumof{n=2,v=Hyperliquid, OKX} · lev.nohist · lev.bnout{v=8.09 lev.u.mld,d='), 'bez nowych części: suma z Hyperliquid i OKX, brak historii sum: ' + hh.slice(hh.indexOf('lev.k.oiall{c=BTC}'), hh.indexOf('lev.k.oiall{c=BTC}') + 260));
});

test('v109-dzwignia2: giełda bez bieżącego stanu (> 6 h) albo bez pozycji — poza sumą i średnią, liczba giełd to odzwierciedla; własny czas wiersza ważniejszy niż czas części; wszystkie stare → „—” z powodem', () => {
  const f = lev104.mk({}); const j = lev109.fix();
  j.part_at.kr = lev109.old7; j.kr.t = lev109.old7; j.kr.BTC.t = lev109.old7; j.kr.ETH.t = lev109.old7;   // Kraken sprzed 7 h — w tabeli (< 4 dni), poza sumą
  j.cb.BTC.oi_usd = null; j.cb.BTC.oi = null;   // Coinbase BTC bez pozycji — stawka jest, ale bez wagi: poza sumą i poza średnią
  j.part_at.dy = lev109.old7;   // część stara, ale wiersze mają własny świeży czas → wchodzą
  f.levApply(j); const h = f.el.innerHTML;
  assert.ok(h.includes('lev.sumof{n=3,v=Hyperliquid, OKX, dYdX}') && h.includes('lev.wof{n=3,v=Hyperliquid, OKX, dYdX}'), 'BTC: 3 giełdy w sumie i w średniej: ' + (h.match(/lev\.(sumof|wof)\{[^}]*\}/g) || []).join(' | '));
  assert.ok(h.includes('lev.sumof{n=4,v=Hyperliquid, OKX, Coinbase, dYdX}') && h.includes('lev.wof{n=4,v=Hyperliquid, OKX, Coinbase, dYdX}'), 'ETH: Coinbase wciąż w sumie (ma pozycje)');
  assert.ok(h.includes('<td><span class="cell">Kraken</span></td><td><span class="cell">BTC</span></td><td><span class="cell mono neg">−2.6%</span></td><td><span class="cell mono">0.18</span></td>'), 'Kraken nadal w tabeli giełd (własna data i wiek)');
  assert.ok(h.includes('lev.sumof{n=3,v=Hyperliquid, OKX, dYdX} · lev.diffn'), 'zestaw inny niż w historii → brak zmiany, z powodem');
  const g = lev104.mk({}); const k = lev109.fix(); for (const p of ['hl', 'okx', 'kr', 'cb', 'dy']) k.part_at[p] = lev109.old7; for (const p of ['okx', 'kr', 'cb', 'dy']) for (const c of ['BTC', 'ETH']) k[p][c].t = lev109.old7;
  g.levApply(k); const hh = g.el.innerHTML;
  assert.ok(hh.includes('lev.k.oiall{c=BTC}</span><b class="na">— <small>lev.nosum</small></b><small class="mtxt">D:' + lev104.now) && hh.includes('lev.k.fall{c=ETH}</span><b class="na">— <small>lev.nosum</small></b>'), 'żadna giełda z ostatnich 6 h — „—” z powodem i czasem pliku: ' + hh.slice(hh.indexOf('lev.k.oiall{c=BTC}'), hh.indexOf('lev.k.oiall{c=BTC}') + 200));
  assert.ok(hh.includes('>Kraken<') && hh.includes('lev.h.hl') && !hh.includes('lev.bnout'), 'stare (< 4 dni) części nadal pokazane z własnymi datami; bez sumy nie ma dopisku o Binance');
  const e = lev104.mk({}); const m = lev109.fix(); delete m.hl; delete m.okx; delete m.kr; delete m.cb; delete m.dy; e.levApply(m);
  assert.ok(!e.el.innerHTML.includes('lev.h.all') && e.el.innerHTML.includes('lev.h.bn'), 'bez żadnej giełdy z bieżącym stanem — rząd „razem” pominięty (zostają Binance i Deribit)');
});

test('v109-dzwignia2: tabela giełd z Kraken, Coinbase i dYdX (loga, znaczek dYdX), kolumna obrotu, notka o okresach finansowania; dopisek „najwięksi gracze (konta)”; dwa nowe punkty „czego nie mówią”; bez nazw dostawców', () => {
  const I = v96src.H; const f = lev104.mk({coinImg: I.coinImg, exchImg: I.exchImg, glyphImg: I.glyphImg}); const j = lev109.fix(); f.levApply(j); const h = f.el.innerHTML;
  const tab = h.slice(h.indexOf('lev.h.ven'), h.indexOf('lev.h.tab'));
  assert.ok(tab.includes('<th>lev.c.ls</th><th>lev.c.vol</th><th>lev.c.when</th>'), 'kolumna obrotu przed „stan na”');
  assert.ok(tab.includes('img/gieldy/kraken.svg') && tab.includes('img/gieldy/coinbase.svg') && tab.includes('img/gieldy/dydx.svg'), 'loga Kraken, Coinbase i dYdX (v109.2: logo z paczki ikon zamiast znaczka)');
  const kr = tab.slice(tab.indexOf('title="Kraken"'), tab.indexOf('title="Kraken"') + 800);
  assert.ok(kr.includes('<td><span class="cell mono neg">−2.6%</span></td><td><span class="cell mono">0.18</span></td><td><span class="cell mono na" title="lev.np">—</span></td><td><span class="cell mono">321</span></td><td><span class="cell mono">D:' + lev104.now), 'Kraken BTC: finansowanie ujemne czerwono, 0,18 mld, bez stosunku kont, obrót 321 mln, własny czas: ' + kr.slice(0, 500));
  assert.ok(tab.includes('<td><span class="cell mono pos">+7.0%</span></td><td><span class="cell mono">0.09</span></td>'), 'Coinbase BTC: +7,0 %, 0,09 mld');
  assert.ok(tab.includes('<td><span class="cell mono neg">−0.7%</span></td><td><span class="cell mono">0.02</span></td><td><span class="cell mono na" title="lev.np">—</span></td><td><span class="cell mono">3</span></td>'), 'dYdX BTC: −0,7 %, 0,02 mld, obrót 3 mln');
  const okx = tab.slice(tab.indexOf('title="OKX"'), tab.indexOf('title="OKX"') + 700);
  assert.ok(okx.includes('</span></td><td><span class="cell mono na" title="lev.np">—</span></td><td><span class="cell mono">D:'), 'OKX bez obrotu w naszym źródle — „—” z podpowiedzią');
  const hl = tab.slice(tab.indexOf('title="Hyperliquid"'), tab.indexOf('title="Hyperliquid"') + 700);
  assert.ok(hl.includes('<td><span class="cell mono">2577</span></td>'), 'Hyperliquid BTC: obrót 2577 mln');
  assert.ok(tab.includes('</table></div><p class="pnote">lev.ven.note</p>'), 'notka o okresach finansowania pod tabelą');
  const order = ['>Hyperliquid<', '>OKX<', '>Binance<', '>Kraken<', '>Coinbase<', '>dYdX<'].map(s => tab.indexOf(s)); assert.ok(order.every((v, i) => v > 0 && (i === 0 || v > order[i - 1])), 'kolejność giełd: ' + order.join(','));
  assert.ok((tab.match(/<tr>/g) || []).length === 13, '12 wierszy (6 giełd × 2 monety) + nagłówek; jest ' + (tab.match(/<tr>/g) || []).length);
  assert.ok(h.includes('lev.more.long · lev.mean{v=1.19} · lev.topacc{v=1.32} · lev.top{v=1.93}</small>'), 'stosunek kont najwięksi gracze w dopisku (top_ls), przed stosunkiem pozycji');
  assert.ok(h.includes('<p class="pnote">lev.not4</p><p class="pnote">lev.not5</p><p class="pnote">lev.not6</p></details>'), 'dwa nowe punkty na końcu');
  assert.ok(h.includes('<h3 class="mtxt"><span class="icos"><img class="ico sm" src="img/glify/globe.svg"') && h.includes('lev.k.oiall{c=BTC}'), 'glif świata w nagłówku i kafelkach rzędu „razem”');
  const tiles = h.split('<div class="etfk">').slice(1);
  tiles.forEach((x, i) => assert.ok(/^<span><span class="icos">.+?<\/span>lev\./.test(x), 'kafelek ' + i + ' ma ikonę przed podpisem'));
  assert.ok(!/CoinGlass|Coinglass|Coin Metrics|Etherscan|EODHD|Tiingo|CryptoPanic|Alpha Vantage|Massive/.test(h), 'bez nazw dostawców');
});

test('v109-dzwignia2: EXTRA102 — 10 języków, te same klucze lev.* i miejsca na liczby, bez powtórzeń z EXTRA98, po niemiecku i japońsku bez surowych kluczy', () => {
  const a = 'const EXTRA102=', x0 = html.indexOf(a);
  assert.ok(x0 > 0 && html.includes('for(const l in EXTRA102)if(I18N[l])Object.assign(I18N[l],EXTRA102[l]);'), 'słownik EXTRA102 podpięty');
  assert.ok(html.indexOf('for(const l in EXTRA101)if(I18N[l])') < x0 && html.indexOf('for(const l in EXTRA98)if(I18N[l])') > 0, 'po EXTRA101 (kotwica), EXTRA98 obecny');
  const D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.deepEqual(Object.keys(D).sort(), ['de', 'en', 'es', 'fr', 'it', 'ja', 'pl', 'pt', 'ru', 'zh']);
  const keys = Object.keys(D.pl).sort();
  assert.ok(keys.length === 13 && keys.every(k => k.startsWith('lev.')), keys.join(','));
  const b = 'const EXTRA98=', b0 = html.indexOf(b), OLD = JSON.parse(html.slice(b0 + b.length, html.indexOf(';\n', b0)));
  assert.ok(keys.every(k => !(k in OLD.pl)), 'żaden klucz nie powtarza EXTRA98');
  for (const L of Object.keys(D)) {
    assert.deepEqual(Object.keys(D[L]).sort(), keys, L);
    for (const k of keys) { const ph = (D.pl[k].match(/\{[a-z]+\}/g) || []).sort(); assert.deepEqual((D[L][k].match(/\{[a-z]+\}/g) || []).sort(), ph, L + ' ' + k); }
  }
  assert.ok(D.pl['lev.h.all'] === 'Wszystkie giełdy razem' && D.en['lev.h.all'] === 'All exchanges together');
  assert.ok(!/napływ|odpływ/i.test(Object.values(D.pl).join(' ')), 'pozycje to stan, nie przepływ');
  assert.ok(/6 godzin/.test(D.pl['lev.all.sub']) && /Bybit/.test(D.pl['lev.not6']) && /8 godzin/.test(D.pl['lev.ven.note']) && /przybliżon/.test(D.pl['lev.not5']), 'treść: 6 h, Bybit, okres 8 godzin, suma przybliżona');
  for (const L of ['de', 'ja']) {
    const f = lev104.mk({}, v96src.tFor(L)); f.levApply(lev109.fix());
    assert.ok(!/lev\.[a-z]/.test(f.el.innerHTML.replace(/id="lev-[a-z]+"/g, '').replace(/lev-opt/g, '')), L + ': bez surowych kluczy: ' + (f.el.innerHTML.match(/lev\.[a-z.]+/) || [])[0]);
  }
  const de = lev104.mk({}, v96src.tFor('de')); de.levApply(lev109.fix());
  assert.ok(de.el.innerHTML.includes('Alle Börsen zusammen') && de.el.innerHTML.includes('Börsen in der Summe (5): Hyperliquid, OKX, Kraken, Coinbase, dYdX') && de.el.innerHTML.includes('größte Händler (Konten): 1.32'), 'niemiecki: nagłówek, lista giełd, konta najwięksi gracze');
  const ja = lev104.mk({}, v96src.tFor('ja')); ja.levApply(lev109.fix());
  assert.ok(ja.el.innerHTML.includes('全取引所の合計') && ja.el.innerHTML.includes('十億ドル'), 'japoński: nagłówek i jednostka jak w słowniku bazowym');
});

test('v108: wieloryby — nowe giełdy (Bybit, KuCoin, Bitfinex): kafle, noty z listą i datą, brak wcześniejszego zrzutu, przelew między giełdami, dziesięć języków', () => {
  const w0 = html.indexOf('/* ===================== v105: wieloryby'), w1 = html.indexOf('\nfunction whApply(', w0);
  assert.ok(w0 > 0 && w1 > w0, 'blok v105 w stronie');
  const T = (k, v) => (k.startsWith('wh.n.') ? 'nota:' + k : k) + (v ? JSON.stringify(v) : '');
  const run = D => {
    const el = {innerHTML: '', hidden: true, querySelectorAll: () => [], querySelector: () => null};
    new Function('$', 't', 'nfmt', 'escH', 'engDate', 'gAgeNote', 'icoWrap', 'coinImg', 'exchImg', 'netImg', 'D', html.slice(w0, w1) + '\nWH.data=D;renderWh();')(
      q => q === '#c-wieloryby' ? el : null, T, (v, d) => Number(v).toFixed(d), v96src.escH, s => '[' + String(s) + ']', d => ' · age(' + String(d).slice(0, 10) + ')',
      x => `<span class="icos">${x}</span>`, (s, c) => `<i class="ico ${c}">${s}</i>`, (s, c) => `<i class="ico ${c}">${s}</i>`, (s, c) => `<i class="ico ${c}">${s}</i>`, D);
    return el;
  };
  const now = new Date().toISOString(), t0 = '2026-09-26T08:00:00+00:00', tx = '0x' + '2b'.repeat(32), S = {blk: 4899, t: t0};
  const D = {at: now, eth_usd: 2690.54, eth_usd_at: now, okno: 4800, okno_od: 100, okno_od_t: '2026-09-25T16:00:00+00:00', ostatni_blok: 4899, ostatni_t: t0,
    gieldy: {Binance: {n: 9, since: '2022-11', tokeny: ['USDT', 'USDC', 'ETH']}, OKX: {n: 10, since: '2026-09-08', tokeny: ['USDC']},
      Bybit: {n: 108, since: '2026-08-26', tokeny: ['USDT', 'USDC', 'ETH']}, KuCoin: {n: 33, since: '2026-08-31', tokeny: ['USDT', 'USDC', 'ETH']}, Bitfinex: {n: 4, since: '2022-11', tokeny: ['USDT', 'USDC', 'ETH']}},
    salda: {Binance: Object.assign({eth: 2702952.36, usdt: 20743650467.52, usdc: 57096.09, usd: 28004143062.82, n: 9}, S), OKX: Object.assign({eth: 0.6, usdt: 29.81, usdc: 1359427317.99, usd: 1359428969.12, n: 10}, S),
      Bybit: Object.assign({eth: 305310.2, usdt: 1217100000, usdc: 301600000, usd: 2340000000, n: 108}, S), KuCoin: Object.assign({eth: 67834, usdt: 510000000, usdc: 46600000, usd: 739000000, n: 33}, S),
      Bitfinex: Object.assign({eth: 272369, usdt: 2000000, usdc: 22200000, usd: null, n: 4}, S)},
    hist: {Bybit: [['2026-09-25', '2026-09-25T00:03:00+00:00', 305000, 1217000000, 301600000]]},
    transfery: [{t: '2026-09-26T07:12:00+00:00', token: 'USDT', amt: 3000000, dir: 'out', exch: 'Bybit', tx, blk: 4890}, {t: '2026-09-26T07:12:00+00:00', token: 'USDT', amt: 3000000, dir: 'in', exch: 'KuCoin', tx, blk: 4890},
      {t: '2026-09-26T06:00:00+00:00', token: 'USDC', amt: 4000000, dir: 'out', exch: 'Bybit', tx: '0x' + '3c'.repeat(32), blk: 4850, wew: true}, {t: '2026-09-26T06:01:00+00:00', token: 'USDC', amt: 4000000, dir: 'in', exch: 'Bybit', tx: '0x' + '4d'.repeat(32), blk: 4855, wew: true}]};
  const el = run(D), out = el.innerHTML;
  assert.ok(!el.hidden, 'sekcja widoczna');
  const order = ['Binance', 'OKX', 'Bybit', 'KuCoin', 'Bitfinex'].map(g => out.indexOf(`<b>${g}</b>`));
  assert.ok(order.every((p, i) => p > 0 && (i === 0 || p > order[i - 1])), 'giełdy w kolejności pliku: ' + order.join(','));
  assert.ok(out.includes('wh.wal{"n":"108","d":"2026-08-26"}') && out.includes('<span class="whn">nota:wh.n.Bybit</span>'), 'Bybit: 108 portfeli, data listy, nota');
  assert.ok(out.includes('wh.wal{"n":"33","d":"2026-08-31"}') && out.includes('nota:wh.n.KuCoin') && out.includes('wh.wal{"n":"4","d":"2022-11"}') && out.includes('nota:wh.n.Bitfinex'), 'KuCoin i Bitfinex: liczba portfeli, data listy, nota');
  for (const g of ['Bybit', 'KuCoin', 'Bitfinex']) for (const k of ['USDT', 'USDC', 'ETH', 'wh.k.usd']) assert.ok(out.includes(`${g} · ${k}`), 'kafel ' + g + ' ' + k);
  assert.ok(out.includes('Bybit · USDT</span><b>1.22 wh.u.mld USDT') && out.includes('Bybit · ETH</span><b>305310 ETH') && out.includes('Bybit · wh.k.usd</span><b>2.34 wh.u.mld USD'), 'kwoty Bybit: ' + out.slice(out.indexOf('Bybit · USDT'), out.indexOf('Bybit · USDT') + 120));
  assert.ok(out.includes('KuCoin · USDT</span><b>510.0 wh.u.mln USDT') && out.includes('Bitfinex · ETH</span><b>272369 ETH'), 'kwoty KuCoin i Bitfinex');
  assert.ok(out.includes('Bitfinex · wh.k.usd</span><b>— <small class="na">wh.usd.na</small>'), 'suma Bitfinex bez liczby = „—” z powodem, nie zero');
  const seg = g => out.slice(out.indexOf(`<b>${g}</b>`), out.indexOf('<h3', out.indexOf(`<b>${g}</b>`) + 1) > 0 ? out.indexOf('<h3', out.indexOf(`<b>${g}</b>`) + 1) : out.length);
  assert.equal((seg('KuCoin').match(/— · wh\.nochg/g) || []).length, 3, 'KuCoin bez historii: trzy kafle z „brak wcześniejszego zrzutu”, nie zero');
  assert.equal((seg('Bitfinex').match(/— · wh\.nochg/g) || []).length, 3, 'Bitfinex bez historii: trzy kafle z „brak wcześniejszego zrzutu”');
  assert.ok(seg('Bybit').includes('<small class="pos">▲ +100000 · wh.vs{"t":"[2026-09-25T00:03:00+00:00]"}</small>'), 'Bybit USDT: zmiana wobec wczorajszego zrzutu, zielona');
  assert.ok(seg('Bybit').includes('<small class="">• 0 · wh.vs{"t":"[2026-09-25T00:03:00+00:00]"}</small>'), 'Bybit USDC: równe salda = zero bez koloru i strzałki');
  assert.equal((seg('Bybit').match(/wh\.d7: — · wh\.short/g) || []).length, 3, 'Bybit: 7 dni bez zrzutu = „za krótka historia” przy trzech kaflach'); assert.ok(!seg('Bybit').includes('wh.nochg'), 'Bybit ma wczorajszy zrzut');
  assert.ok(out.includes(`wh.blk{"t":"[${t0}]","n":"4899"} · age(2026-09-26)`), 'data i wiek salda przy kaflach');
  assert.ok((out.match(/<i class="ico sm">Bybit<\/i>/g) || []).length >= 5 && (out.match(/<i class="ico sm">Bitfinex<\/i>/g) || []).length >= 5, 'logo (albo monogram) giełdy przy nagłówku, kaflach i w tabeli');
  const rows = out.split('<tr><td>').length - 1;
  assert.equal(rows, 4, 'przelew Bybit → KuCoin = dwa wiersze (z giełdy / na giełdę), para wew = dwa wiersze');
  assert.ok(out.includes('▼ wh.out · <span class="icos"><i class="ico sm">Bybit</i></span>Bybit</span>') && out.includes('▲ wh.in · <span class="icos"><i class="ico sm">KuCoin</i></span>KuCoin</span>'), 'kierunki z logo i nazwą nowej giełdy');
  assert.equal((out.match(/class="cell neu wew"/g) || []).length, 2, 'para na Bybit: obie strony bursztynowe z dopiskiem');
  assert.ok(!/Hacken|Etherscan|Chainlink|CoinGecko|PublicNode|publicnode|GitHub/.test(out.replace(/href="[^"]*"/g, '')), 'bez nazw dostawców ani audytora w tekście panelu');
  // słownik: nowe klucze wh.n.* w dziesięciu językach, z datą listy, bez nazw dostawców i audytora; stare klucze bez zmian
  const keys = ['wh.n.Bybit', 'wh.n.KuCoin', 'wh.n.Bitfinex'], PROV = /Etherscan|Chainlink|CoinGecko|PublicNode|Allnodes|Coin Metrics|Hacken|GitHub/i;
  assert.ok(html.includes('const EXTRA103=') && html.includes('for(const l in EXTRA103)if(I18N[l])Object.assign(I18N[l],EXTRA103[l]);'), 'słownik EXTRA103 podpięty');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    for (const k of keys) { assert.ok(v96src.I18N[L][k] && t(k) !== k && t(k).length > 40, L + ' ' + k); assert.ok(!PROV.test(t(k)), 'dostawca: ' + L + ' ' + k); }
    assert.ok(/2026/.test(t('wh.n.Bybit')) && /2026/.test(t('wh.n.KuCoin')) && /2022/.test(t('wh.n.Bitfinex')), 'data listy w nocie: ' + L);
    if (!['pl', 'en'].includes(L)) for (const k of keys) assert.notEqual(t(k), v96src.tFor('en')(k), 'przetłumaczone: ' + L + ' ' + k);
  }
  assert.ok(v96src.tFor('pl')('wh.n.Bybit').includes('108') === false && v96src.tFor('pl')('wh.n.Bybit').includes('Portfele giełdy w sieci Ethereum wymienione'), 'nota Bybit: portfele z raportu (liczba i data listy są w wh.wal z pliku)');
  assert.ok(v96src.tFor('en')('wh.n.Bitfinex').includes('not all of them') && v96src.tFor('pl')('wh.n.Bitfinex').includes('nie całość'), 'nota Bitfinex: część majątku, nie całość');
  assert.equal(v96src.tFor('pl')('wh.n.Binance'), 'Portfele gorące i zimne z wpisu giełdy o przejrzystości (listopad 2022) — część majątku giełdy, nie całość.', 'stara nota bez zmian');
});

// v110 (obszar „krypto3d”): BLOCKCHAIN 3D domyślnie, KULE 3D w tej samej scenie 3D, zdjęcia węzłów z img/wezly/, płaski widok bąbelków usunięty
test('v110: domyślny widok zakładki CRYPTO to BLOCKCHAIN 3D (blocks); lista widoków bez zmian', () => {
  assert.ok(html.includes("const st={mode:'crypto',trdv:'global',period:'24H',view:'blocks',"), 'view:blocks');
  assert.ok(html.includes("items:[{v:'blocks',l:'view.blocks'},{v:'bubbles',l:'view.bubbles'},{v:'list',l:'view.list'}]"), 'trzy widoki w menu');
  assert.ok(!html.includes("view:'bubbles',label:'pct'"), 'stary domyślny widok');
});
test('v110: zdjęcia węzłów gaming / giełdy / memecoiny z img/wezly/, stary base64 memecoinów usunięty', () => {
  const a = html.indexOf('const LOGO_URLS={'), b = html.indexOf('\nconst logoSrc=', a);
  assert.ok(a > 0 && b > a);
  const U = new Function(html.slice(a, b) + '\nreturn {LOGO_URLS,LOGO_URLS_LIGHT};')();
  assert.equal(U.LOGO_URLS.gaming, 'img/wezly/gaming.jpg'); assert.equal(U.LOGO_URLS.exch, 'img/wezly/gieldy.jpg'); assert.equal(U.LOGO_URLS.meme, 'img/wezly/memecoiny.jpg');
  for (const id of ['btc', 'eth', 'stab', 'defi', 'depin']) assert.ok(/^data:image\//.test(U.LOGO_URLS[id]), 'pozostałe loga bez zmian: ' + id);
  assert.ok(!U.LOGO_URLS_LIGHT.gaming && !U.LOGO_URLS_LIGHT.exch && !U.LOGO_URLS_LIGHT.meme, 'zdjęcia wspólne dla obu motywów');
  assert.equal((html.match(/meme:'data:image/g) || []).length, 0);
  assert.ok(html.includes("const LOGO_PHOTO=new Set(['exch','gaming','meme']);") && html.includes('if(LOGO_PHOTO.has(id)){c.lineWidth=Math.max(1,s*.09);'), 'obwódka zdjęć w drawIconOn');
  assert.ok(/img-src 'self' data:/.test(html), 'CSP pozwala na obrazki z własnego folderu');
  // pliki w repo (pod node; pod jsc fs.existsSync nie istnieje — sprawdza to test zbieracza)
  if (typeof fs.existsSync === 'function' && __dirname) for (const f of ['gaming', 'gieldy', 'memecoiny']) assert.ok(fs.existsSync(path.join(__dirname, 'img', 'wezly', f + '.jpg')), 'brak pliku ' + f);
});
test('v110: render() rysuje oba widoki w scenie 3D — płaski renderer bąbelków (szary szkielet) usunięty', () => {
  const r0 = html.indexOf('function render(time){'), r1 = html.indexOf('\n}', r0), R = html.slice(r0, r1);
  assert.ok(!R.includes('drawBub') && R.includes('setCam();drawFloor();NODES.forEach(drawGroundGlow);') && R.includes('if(C[1]>FY+.3)drawScene(true,time);') && R.includes('drawScene(false,time);drawLabels();'), R);
  for (const s of ['drawBub', 'pickBub', 'layoutBub', 'ensureBub', 'bubArc', 'bubBall', 'bubPt', 'drawSpace', 'FLATV', 'HINTK', 'OBkey', 'const flat=', 'flat.k', 'labelLead(', 'OB.SK', 'OB.HEX',
    '.stage3d.orb', '.stage3d.flat', "classList.toggle('flat'", "classList.toggle('orb'"]) assert.equal(html.split(s).length, 1, 'martwy symbol: ' + s);
  assert.equal((html.match(/\blabelSpot\(/g) || []).length, 0, 'labelSpot usunięty (labelSpotG mapy GLOBAL zostaje)');
  assert.ok(html.includes('function labelSpotG(') && html.includes('function heart(time){') && html.includes('const hb=heart(time);') && html.includes('const qpt=('), 'heart, qpt i labelSpotG zostają dla mapy GLOBAL');
  assert.ok(html.includes("if(!n._hull.length)return Math.hypot(x-n._c[0],y-n._c[1])<=n._c[2]+4;"), 'pick 3D trafia w kule po n._c');
  assert.ok(html.includes("if(!mirror){n._c=[cp[0],cp[1],Rp];n._hull=[];"), 'kula zapisuje trafienie');
  assert.ok(html.includes('const BUB_R=.72;') && html.includes("r=s*(style==='bubble'?BUB_R:.62)") && html.includes("st.view==='bubbles'?cur[n.id]*BUB_R:cur[n.id]*.58"), 'promień kul większy niż .62, linie zaczynają się na powierzchni kuli');
  assert.ok(html.includes("drawSphere(n,mirror,ga,n.shape==='sphere'?'globe':'bubble')"), 'gałąź kul w drawScene');
  assert.ok(html.includes("if(st.view!=='bubbles')LAT.forEach(([a,b])=>{") && (html.match(/LAT\.forEach\(/g) || []).length === 1, 'siatka LAT (szare linie między sąsiadami) tylko w widoku BLOCKCHAIN 3D — KULE 3D bez szarych linii');
  assert.ok(html.includes("$('#z-reset').addEventListener('click',()=>{camTo(HOME(),800);});") && html.includes("cam.dist*=Math.exp(e.deltaY*.0011);clampCam();camTw=null;dirty=true;},{passive:false});"), 'zoom i reset zawsze kamerą 3D');
  assert.ok(html.includes('.stage3d{position:relative;height:clamp(440px,54vw,680px);') && html.includes('.stage3d{height:clamp(380px,100vw,520px)}'), 'jedna wysokość sceny dla obu widoków');
});
test('v110: nazwy widoków i opisy w 10 językach — BLOCKCHAIN 3D / KULE 3D, bez „klocka” i „bąbelka”', () => {
  const NAMES = {pl: 'KULE 3D', en: '3D SPHERES', de: '3D-KUGELN', es: 'ESFERAS 3D', fr: 'SPHÈRES 3D', it: 'SFERE 3D', pt: 'ESFERAS 3D', ru: '3D-СФЕРЫ', zh: '3D 球体', ja: '3D 球体'};
  const BAD = {pl: /klock|klocek|bąbel/i, en: /bubble/i, de: /blase/i, es: /burbuja/i, fr: /bulle/i, it: /boll[ae]/i, pt: /bolha/i, ru: /пузыр/i, zh: /气泡/, ja: /バブル/};
  const KEYS = ['view.blocks', 'view.bubbles', 'leg.areaB', 'howto.1b', 'scene.aria', 'why.empty'];
  for (const L of Object.keys(NAMES)) {
    const tt = v96src.tFor(L), d = v96src.I18N[L];
    assert.equal(tt('view.blocks'), 'BLOCKCHAIN 3D', L); assert.equal(tt('view.bubbles'), NAMES[L], L); assert.equal(tt('view.list'), v96src.I18N[L]['view.list'], L);
    for (const k of KEYS) assert.ok(typeof d[k] === 'string' && d[k].trim() && !BAD[L].test(d[k]), L + ' ' + k + ': ' + d[k]);
    assert.ok(d['leg.areaB'].includes('{v}') && tt('leg.areaB', {v: 'QQ'}).includes('QQ'), L + ' {v}');
    assert.ok(/blockchain|блокчейн|区块链|ブロックチェーン/i.test(d['howto.1b']) && /blockchain|блокчейн|区块链|ブロックチェーン/i.test(d['scene.aria']), L + ' opis mówi o blokach blockchain');
  }
  assert.ok(html.includes('const EXTRA104=') && html.includes('for(const l in EXTRA104)if(I18N[l])Object.assign(I18N[l],EXTRA104[l]);'), 'słownik EXTRA104 dołączony');
  // EXTRA104 nadpisuje tylko klucze, które strona czyta: hint3 (dawne HINTK) i leg.area (legenda używa leg.areaB) zostają bez martwych nadpisań
  const e0 = html.indexOf('const EXTRA104='), e1 = html.indexOf(';\nfor(const l in EXTRA104)', e0);
  const E = JSON.parse(html.slice(e0 + 'const EXTRA104='.length, e1));
  for (const L of Object.keys(NAMES)) assert.equal(Object.keys(E[L]).sort().join('|'), KEYS.slice().sort().join('|'), L + ': klucze EXTRA104');
  assert.ok(!html.includes("t('hint3')") && !html.includes("t('leg.area'") && html.includes("t('leg.areaB'") && !html.includes('HINTK'), 'hint3 i leg.area nie są czytane przez stronę');
  assert.ok(html.includes('<div class="hint" id="hint" data-i18n="hint"></div>'), 'podpowiedź pod sceną z klucza hint');
});

// v107 (sprzątanie): martwy kod po dawnej stronie Źródła usunięty — funkcje bez wywołań, CSS bez klas, 160 kluczy bez użycia;
// strażnik „bez wiszących kluczy”: każdy literał t('…') / t("…") i każdy atrybut data-i18n* w stronie ma wpis w pl i en
test('v107: srvAt/metaErr/tvState, CSS dawnej strony Źródła i klucze zr./g.hs./src./pg.attr… nie istnieją; klucze v103 zostają', () => {
  for (const s of ['function srvAt(', 'function metaErr(', 'function tvState(', '.zr-attr{', '.zr-g{', '.zr-ico small{', '#zr-icons', '.cell.zr-n{', "t('src.m.err')", "'tv.src.on'",
    'const EXTRA16=', 'const EXTRA37=', 'const EXTRA_YLD=', 'Object.assign(I18N.pl,{"g.hs.tga":'])
    assert.ok(!html.includes(s), 'usunięte: ' + s);
  const D = v96src.I18N;
  const gone = ['zr.sub', 'zr.help', 'zr.lic', 'zr.ico', 'zr.ico.flags', 'zr.g.i', 'zr.a.oecd', 'zr.a.tv', 'g.hs.tv', 'g.hs.oecd', 'g.hs.tga', 'g.hs.mof', 'g.hs.fh', 'g.hs.irlt', 'g.hs.ust', 'g.hs.mk',
    'src.f.d', 'src.f.w', 'src.l.1d', 'src.l.7w', 'src.d.cp', 'src.d.wbfix', 'src.m.file', 'src.m.err', 'pg.attr', 'pg.attr.d', 'pg.nosrc', 'pg.nosrc.d', 'pg.source', 'pg.host', 'pg.freq', 'pg.lag', 'pg.state', 'pg.sources.d', 'tv.src.on', 'tv.src.off'];
  for (const k of gone) for (const L in D) assert.ok(!(k in D[L]), 'martwy klucz usunięty: ' + L + ' ' + k);
  for (const L in D) for (const k in D[L]) assert.ok(!/^(zr\.(a|g|ico)\.|g\.hs\.|src\.(f|l|d|m)\.|pg\.(attr|nosrc)|tv\.src\.)/.test(k) && k !== 'zr.sub' && k !== 'zr.help' && k !== 'zr.lic' && k !== 'zr.ico', 'rodzina usunięta w całości: ' + L + ' ' + k);
  for (const k of ['zr2.live', 'zr2.refresh', 'zr2.count', 'zr2.legal', 'zr2.attr', 'zr2.help', 'foot.src', 'pg.sources', 'pg.fixed', 'pg.ok', 'pg.no', 'g.age', 'g.age1', 'g.age0', 'inst.file', 'eng.notsays', 'eng.disclaimer'])
    assert.ok(D.pl[k] && D.en[k], 'zostaje: ' + k);
  assert.ok(html.includes('function metaLoad(){') && html.includes('function tvAnyLoaded(){') && html.includes('GLIVE.srcAt'), 'metaLoad, tvAnyLoaded i GLIVE.srcAt zostają');
  // strona Źródła v103 renderuje się po sprzątaniu tak samo (karta stanu, podpisy), bez surowych kluczy
  for (const L of ['pl', 'de', 'ja']) {
    const out = v96src.render(L, false, null).out;
    assert.ok(out.includes('id="zr-clock"') && out.includes('zr-attr2') && out.includes('Data by CoinGecko') && !/zr2?\.[a-z]/.test(out.replace(/zr-attr2/g, '')), L + ': karta stanu bez surowych kluczy');
  }
});

test('v107: strażnik — każdy literał t(\'klucz\') i data-i18n w stronie ma wpis w słowniku pl i en', () => {
  const D = v96src.I18N;
  const s0 = html.indexOf('<script>'), s1 = html.lastIndexOf('</script>'), js = html.slice(s0, s1);
  const d0 = js.indexOf('const I18N={'), d1 = js.indexOf('/* ===================== STAN I DANE');
  assert.ok(d0 > 0 && d1 > d0);
  const code = js.slice(0, d0) + js.slice(d1);   // kod strony bez samego bloku słowników
  // klucze składane dynamicznie ('g.n.'+id, 'trd.'+key+'.t' …) nie są literałami, więc strażnik ich nie widzi; tu wpisać literał, który celowo nie ma wpisu
  const EXCLUDE = [];
  const keys = new Set();
  for (const m of code.matchAll(/(?<![A-Za-z0-9_$.])t\(\s*(['"])([^'"\\]+)\1\s*[,)]/g)) keys.add(m[2]);
  for (const m of html.matchAll(/data-i18n(?:-[a-z]+)?="([^"]+)"/g)) keys.add(m[1]);
  assert.ok(keys.size > 900, 'literały znalezione: ' + keys.size);
  const missing = [...keys].filter(k => !EXCLUDE.includes(k) && !(k in D.pl && k in D.en));
  assert.deepEqual(missing, [], 'literały bez wpisu w pl/en');
  for (const k of ['pg.sources', 'zr2.live', 'inst.file', 'eng.notsays', 'lev.t', 'wh.t', 'ix.t']) assert.ok(keys.has(k), 'literał widziany przez strażnika: ' + k);
});

test('v108.1: noty Bybit/KuCoin nie mówią „wszystkie portfele” (raport obejmuje portfele w jego zakresie)', () => {
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    for (const k of ['wh.n.Bybit', 'wh.n.KuCoin']) assert.ok(!/^(Wszystkie|All of|Alle |Todas|Tous|Tutti|Все)/.test(t(k)) && !t(k).includes('全部钱包') && !t(k).includes('全ウォレット'), L + ' ' + k + ': ' + t(k).slice(0, 60));
  }
  assert.ok(v96src.tFor('pl')('wh.n.Bybit').startsWith('Portfele giełdy w sieci Ethereum wymienione w jej'));
});
test('v109.2: logo dYdX z tej samej paczki ikon (wpis EXCH_SVG; plik img/gieldy/dydx.svg kopiowany z obszarem)', () => {
  assert.ok(html.includes("EXCH_SVG={dydx:'dydx',binance:'binance',"));
  assert.ok(html.includes("if(k==='hyperliquid')") && html.includes("icoImg('img/gieldy/'+f+'.svg'"), 'exchImg mapuje nazwę giełdy na plik z img/gieldy');
});

test('v111: wyszukiwarki — weryfikacja Google w <head>, opis, canonical, hreflang ×11, Open Graph, tytuł; ?lang= i pamięć języka; teksty w 10 językach', () => {
  const head = html.slice(0, html.indexOf('</head>'));
  assert.ok(head.includes('<meta name="google-site-verification" content="ZdWOjrS6sSu-8eNCUvoFlkLmzqCpRlTcOmZpoomXvAQ" />'), 'tag weryfikacji Google — nigdy nie usuwać');
  assert.ok(head.includes('<meta name="description" content="Mapa przepływu kapitału na żywo') && head.includes('<link rel="canonical" href="https://capitalflowai-app.github.io/">'));
  assert.equal((head.match(/<link rel="alternate" hreflang="/g) || []).length, 11, '10 języków + x-default');
  assert.ok(head.includes('hreflang="x-default" href="https://capitalflowai-app.github.io/"') && head.includes('hreflang="ja" href="https://capitalflowai-app.github.io/?lang=ja"'));
  for (const p of ['og:type', 'og:site_name', 'og:url', 'og:title', 'og:description', 'og:image', 'og:image:width', 'og:image:height', 'og:locale']) assert.ok(head.includes('<meta property="' + p + '"'), p);
  assert.ok(head.includes('content="https://capitalflowai-app.github.io/img/og.png"') && head.includes('<meta name="twitter:card" content="summary_large_image">'));
  assert.ok(head.includes('<title>CapitalFlowAI — Gdzie płynie kapitał?</title>') && !head.includes('CRYPTO 3D v3'));
  assert.ok(html.includes("new URLSearchParams(location.search).get('lang')") && html.includes("localStorage.getItem('cfai.lang')") && html.includes("localStorage.setItem('cfai.lang',LANG)"), 'język z adresu, potem zapamiętany');
  assert.ok(html.includes('function applyLang(){\n  document.documentElement.lang=LANG;\n  seoApply();'), 'applyLang odświeża tytuł/opis/canonical/og');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    assert.ok(t('seo.title').startsWith('CapitalFlowAI — ') && t('seo.desc').length <= 155 && t('seo.desc').length > 30, L + ': ' + t('seo.desc').length);   // zh/ja: znaki CJK — krótsze napisy
  }
});

test('v112: transfery ETH natywne w tabeli wielorybów — słownik EXTRA106 (10 języków), sortowanie wg USD, nota o rotacji / braku odczytu, kwota ETH z ≈ USD', () => {
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)];
  const order = apl.map(m => m[1]);
  assert.ok(order.indexOf('EXTRA106') > order.indexOf('EXTRA99') && order.indexOf('EXTRA106') > order.indexOf('EXTRA103'), 'EXTRA106 nałożony po EXTRA99/EXTRA103 (starszy słownik nie może nadpisać nagłówka)');
  assert.ok(v96src.tFor('pl')('wh.n.Bybit').includes('w jej miesięcznym raporcie dowodu rezerw') && v96src.tFor('ru')('wh.n.Bybit').includes('в её ежемесячном аудиторском отчёте'), 'noty v108.1 poprawione gramatycznie');
  assert.ok(html.includes("function whUsd(r){return whNum(r.usd)?r.usd:r.amt;}") && html.includes(".sort((a,b)=>whUsd(b)-whUsd(a));}"), 'tabela malejąco wg USD');
  assert.ok(html.includes("t(E||ethNa?'wh.h.tr':'wh.h.tr2')") && html.includes("t('wh.eth.na')") && html.includes("t('wh.eth.note',{n:") && html.includes("coinImg('ETH','sm'):''}${coinImg('USDT','sm')}"));
  assert.ok(html.includes("whNum(r.usd)?`<small class=\"whx\"> ≈ ${whAmt(r.usd,'USD')}</small>`:''"), 'kwota ETH z przybliżeniem w USD');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    assert.ok(t('wh.h.tr').includes('ETH') && t('wh.h.tr').includes('USDT') && t('wh.h.tr').includes('USDC'), L + ' nagłówek');
    assert.ok(t('wh.h.tr2').includes('USDT') && !t('wh.h.tr2').includes('ETH'), L + ' dawny nagłówek bez ETH');
    assert.ok(t('wh.eth.note').includes('{n}') && t('wh.eth.note').includes('{m}') && t('wh.eth.note').includes('{l}') && t('wh.eth.note').length > 80, L + ' nota');
    assert.ok(t('wh.eth.na').length > 30 && t('wh.eth.na').includes('USDT'), L + ' brak odczytu');
  }
});

test('v114: archiwum własne na stronie — słownik EXTRA107 (10 języków), sekcje GLOBAL/CRYPTO, wczytanie archiwum/seria.json, okno 30/90/365 zapamiętane, wykres bez zera za brak', () => {
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)];
  const ordr = apl.map(m => m[1]); assert.ok(ordr.indexOf('EXTRA107') > ordr.indexOf('EXTRA106') && ordr.indexOf('EXTRA107') > ordr.indexOf('EXTRA99'), 'EXTRA107 po EXTRA106');
  assert.ok(html.includes('<section class="panel pcard" id="g-archiwum" hidden></section>') && html.includes('<section class="panel pcard" id="c-archiwum" hidden></section>'));
  assert.ok(html.includes("fetch('archiwum/seria.json?t='") && html.includes("localStorage.setItem('cfai.arc.per',String(p))") && html.includes("const ARC={data:null,timer:null,per:90,ok:[30,90,365]};"));
  assert.ok(html.includes("if(freq==='M')return d.slice(-12);") && html.includes('if(gaps[i-1]>7*med)out.push([]);'), 'dane miesięczne = 12 punktów; luka > 7 odstępów przerywa linię');
  assert.ok(html.includes('arcLoad();arcAuto();') && html.includes('if [ -d archiwum ]') === false, 'start wczytywania na stronie');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    for (const k of ['arc.t', 'arc.t.c', 'arc.sub', 'arc.credit', 'arc.foot', 'arc.k.liq', 'arc.k.yld', 'arc.k.tic', 'arc.k.stab', 'arc.k.wh', 'arc.src.fred', 'arc.u.ct']) assert.ok(t(k) !== k && t(k).length > 0, L + ' ' + k);   // ja: „枚” — jeden znak
    assert.ok(t('arc.per').includes('{n}') && t('arc.since').includes('{d}') && t('arc.since').includes('{n}') && t('arc.k.cftc').includes('{c}') && t('arc.src').includes('{s}'), L + ' zmienne');
    assert.ok(t('arc.credit').includes('CapitalFlowAI'), L + ' podpis archiwum');
  }
  // funkcje czyste: okno, luki, format
  const src = html.slice(html.indexOf('function arcMs(d)'), html.indexOf('function arcBlock('));
  const env = new Function('t', 'nfmt', 'escH', src + '\nreturn {arcMs, arcWin, arcSegs, arcVal, arcChart};')(k => ({'u.t': 'bln USD', 'u.b': 'mld USD', 'u.m': 'mln USD', 'u.pp': 'pp', 'arc.u.ct': 'kontraktów', 'arc.empty': 'brak'}[k] || k), (v, d) => v.toFixed(d || 0), s => String(s));
  const d = [['2026-09-01', 1], ['2026-09-02', 2], ['2026-09-03', 3], ['2026-09-20', 4], ['2026-09-21', 5]];
  assert.deepEqual(env.arcWin(d, 30, 'D'), d); assert.deepEqual(env.arcWin(d, 2, 'D'), [['2026-09-20', 4], ['2026-09-21', 5]], 'okno od ostatniego punktu, nie od dziś');
  assert.equal(env.arcWin(Array.from({length: 20}, (_, i) => ['2025-' + String(i + 1).padStart(2, '0'), i]), 30, 'M').length, 12, 'miesięczne: 12 punktów');
  assert.deepEqual(env.arcSegs(d).map(s => s.length), [3, 2], 'przerwa 17 dni przy typowym odstępie 1 dnia = luka');
  assert.equal(env.arcVal(6590000, 'mln USD'), '6.59 bln USD'); assert.equal(env.arcVal(-120500, 'mln USD'), '−120.5 mld USD'); assert.equal(env.arcVal(88304342264.55, 'tok'), '88.30 mld');
  assert.equal(env.arcVal(5.17, '%'), '5.17 %'); assert.equal(env.arcVal(-7953, 'kontrakty'), '−7953 kontraktów'); assert.equal(env.arcVal(null, '%'), '—');
  const svg = env.arcChart([{d, cls: 'l1'}], '%', false);
  assert.ok(svg.includes('<polyline class="arc-l l1"') && (svg.match(/<polyline/g) || []).length === 2 && svg.includes('2026-09-01') && svg.includes('2026-09-21'), 'dwa odcinki (luka), daty skrajne');
  assert.ok(env.arcChart([{d: [], cls: 'l1'}], '%', false).includes('arc-empty') && env.arcChart([{d: [['2026-09-26', 1]], cls: 'l1'}], '%', true).includes('<circle'), 'pusto = napis; jeden punkt = kropka');
});

test('v116: małe ikony — piktogramy własne dla zdjęć węzłów przy ≤ 24 px (pasek, chipy), scena 3D bez zmian, Bitfinex „BFX”', () => {
  assert.ok(html.includes("const EXCH_MONO={bitfinex:'BFX'};") && html.includes("monoBadge(EXCH_MONO[k]||k.slice(0,2).toUpperCase()||'?'"), 'BFX zamiast BI');
  assert.ok(html.includes('const SMALL_PX=24;') && html.includes('const SMALL_PICTO={') && /gaming\(c,px,col\)\{/.test(html) && /meme\(c,px,col\)\{/.test(html) && /exch\(c,px\)\{/.test(html), 'trzy piktogramy: pad, buźka, strzałki');
  assert.ok(html.includes("const src=logoSrc(id);if(src&&!(px<=SMALL_PX&&SMALL_PICTO[id]))return src;") && html.includes('if(src)smallPicto(c,id,px);else drawIconOn('), 'zdjęcie tylko powyżej 24 px');
  assert.ok(html.includes("src=\"${iconURL(id,20)}\" alt=\"\" width=\"20\"") && html.includes("src=\"${iconURL(n.id,18)}\" alt=\"\" width=\"18\"") && html.includes("src=\"${iconURL(n.id,26)}\" alt=\"\" width=\"26\"") && html.includes('data-px="18" src="${escH(iconURL(id,18))}"'), 'rozmiar przekazany do iconURL');
  assert.ok(html.includes("im.src=iconURL(im.dataset.id,+im.getAttribute('width')||+im.dataset.px||56)"), 'zmiana motywu zachowuje rozmiar');
  assert.ok(html.includes("const px=cls==='sm'?14:cls==='lg'?24:18;") && html.includes('u=iconURL(id,px);') && html.includes('data-px="${px}" src="${escH(u)}"'), 'chipy .ico wg klasy: 14 / 18 / 24 px');
  const scene = html.slice(html.indexOf('function drawIconOn('), html.indexOf('const drawIcon=('));
  assert.ok(scene.includes('const im=logoImg(id);') && !scene.includes('SMALL_PICTO') && scene.includes('LOGO_PHOTO.has(id)'), 'scena 3D rysuje zdjęcia jak dotąd');
  assert.ok(!/emoji|😀|🎮/.test(html.slice(html.indexOf('const SMALL_PICTO='), html.indexOf('function iconURL('))), 'własne kształty, nie emoji');
});

test('v117: poprawki po przeglądzie — nota o starych wierszach ETH (EXTRA108), roundRect z zapasem dla starszych przeglądarek', () => {
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)];
  const ordr8 = apl.map(m => m[1]); assert.ok(ordr8.indexOf('EXTRA108') > ordr8.indexOf('EXTRA107'), 'EXTRA108 po EXTRA107');
  assert.ok(html.includes("ethOld=ethNa&&R.some(r=>r.token==='ETH')") && html.includes("ethOld?`<p class=\"pnote neu\">${t('wh.eth.old',{t:engDate(D.part_at&&D.part_at.eth)})}</p>`:ethNa?"), 'stare wiersze ETH ≠ „tylko USDT i USDC”');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) assert.ok(v96src.tFor(L)('wh.eth.old').includes('{t}') && v96src.tFor(L)('wh.eth.old').includes('ETH'), L);
  assert.ok(html.includes('if(c.roundRect)c.roundRect(-w/2,-hh/2,w,hh,hh*.5);else c.rect(-w/2,-hh/2,w,hh);'), 'roundRect tylko gdy istnieje');
});

test('v118: sumy dobowe dużych przelewów w panelu wielorybów — blok whDob z D.dobowe, podpisy doby (w toku / liczone od / pełna), EXTRA109 ×10', () => {
  assert.ok(html.includes("const body=whExch(D)+whDob(D)+whTable(D);") && html.includes("function whDob(D){const B=D&&D.dobowe&&typeof D.dobowe==='object'?D.dobowe:null;if(!B)return '';"));
  assert.ok(html.includes(".sort().reverse().slice(0,3)") && html.includes("const from=!!(od&&od.slice(0,10)>=d),p=[];if(from)p.push(t('wh.dob.from',{t:engDate(od)}));"), '3 ostatnie doby; doba z początkiem liczenia = „liczone od”');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    for (const k of ['wh.h.dob', 'wh.dob.sub', 'wh.dob.part', 'wh.dob.full', 'wh.c.day', 'wh.c.n', 'wh.c.net']) assert.ok(t(k) !== k && t(k).length > 0, L + ' ' + k);   // ja: „日”
    assert.ok(t('wh.dob.from').includes('{t}') && /60/.test(t('wh.dob.sub')), L + ' sub mówi o 60 z tabeli');
  }
  // czysta funkcja: sumy per giełda i doba, sortowanie wg obrotu, brak bloku bez danych
  const src = html.slice(html.indexOf('function whDob(D){'), html.indexOf('function whTable(D){'));
  const env = new Function('t', 'engDate', 'escH', 'whNum', 'whAmt', 'nfmt', src + '\nreturn {whDob};')(
    (k, v) => k + (v ? JSON.stringify(v) : ''), s => 'D(' + s + ')', s => String(s), v => typeof v === 'number' && isFinite(v), (v, u) => v.toFixed(0) + ' ' + u, v => String(v));
  const today = new Date().toISOString().slice(0, 10);
  const D = {dobowe: {'2026-09-25': {Binance: {USDT: {in: 5e6, out: 2e6, n: 2}, ETH: {in: 0, out: 1e6, n: 1}}, OKX: {USDC: {in: 1e6, out: 0, n: 1}}}, [today]: {Bybit: {ETH: {in: 3e6, out: 0, n: 1}}}, 'x': 1}, dobowe_od: '2026-09-25T13:00:00+00:00'};
  const out = env.whDob(D);
  assert.ok(out.includes('wh.h.dob') && out.includes('Binance') && out.includes('▲ 5000000 USD') && out.includes('▼ 3000000 USD') && out.includes('+2000000 USD'), 'Binance: in 5, out 3 (USDT 2 + ETH 1), netto +2');
  assert.ok(out.indexOf('Binance') < out.indexOf('OKX'), 'większy obrót pierwszy'); assert.ok(out.includes('wh.dob.part') && out.includes('wh.dob.from{"t":"D(2026-09-25T13:00:00+00:00)"}'), 'dziś = w toku; 25.09 = liczone od');
  const out2 = env.whDob({dobowe: {[today]: {Bybit: {ETH: {in: 3e6, out: 0, n: 1}}}}, dobowe_od: today + 'T15:00:00+00:00'});
  assert.ok(out2.includes('wh.dob.from') && out2.includes('wh.dob.part') && !out2.includes('wh.dob.full'), 'pierwszy dzień liczenia = „liczone od” i „w toku” razem (v118.1)');
  assert.equal(env.whDob({dobowe: {}}), ''); assert.equal(env.whDob({}), '');
});

/* v120: TRENDY — sygnały dzienne (blok nad kaflami tygodnia; dane z klucza `d` i linie zbiorcze `bd` w data/trendy.json) */
const trdV120 = (() => {
  const row = o => Object.assign({fam: 'eq', grp: null, iss: null, pub: 0, sym: null, date: '2026-09-25', nx: '2026-09-28', live: true, age: 1, f: null, cur: null, fu: null, zf: null, r: null, zp: null,
    rule: 'none', dir: 0, side: 'none', str: 0, st: 'quiet', vd: null, ik: null, in: null}, o);
  const line = o => Object.assign({k: 0, n: 0, days: 0, from: null, to: null, p: null, ci: [null, null], h1: null, h2: null, lk: 0, ln: 0, ldays: 0, m: 0, need: 100, vd: 'short'}, o);
  const d = [
    row({id: 'IVV', grp: 'fe_us', iss: 'ishares', sym: 'IVV', f: 412.3, cur: 'USD', fu: 412.3, zf: 0.4, r: 0.84, zp: 1.3, rule: 'p', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none', ik: 18, in: 34}),
    row({id: 'EWZ', grp: 'fe_bra', iss: 'ishares', sym: 'EWZ', f: 95.2, cur: 'USD', fu: 95.2, zf: 2.3, r: 1.9, zp: 0.6, rule: 'f', dir: 1, side: 'buy', str: 2, st: 'buy', vd: 'edge', ik: 9, in: 15}),
    row({id: 'SLV', fam: 'pm', grp: 'fe_silver', iss: 'ishares', sym: 'SLV', f: -30.1, cur: 'USD', fu: -30.1, zf: -0.2, r: -2.4, zp: -1.6, rule: 'p', dir: -1, side: 'sell', str: 1, st: 'obs', vd: 'anti', ik: 40, in: 77}),
    row({id: 'tw', sym: 'EWT', date: '2026-09-24', nx: '2026-09-25', live: false, age: 2, f: -32964.6, cur: 'TWD', fu: -1013.2, zf: -2.3, r: -0.4, zp: -0.5, rule: 'f', dir: -1, side: 'none', str: 2, st: 'stale', vd: 'none', ik: 9, in: 20}),
    row({id: 'EWC', sym: 'EWC', r: 0.21, zp: 0.3, st: 'quiet'}),
    row({id: 'XLK', grp: 'fe_tech', iss: 'ssga', sym: 'XLK', f: 300.5, cur: 'USD', fu: 300.5, zf: 1.5, r: -1.2, zp: -1.4, rule: 'x', dir: 0, side: 'none', str: 0, st: 'x', vd: null}),
    row({id: 'KSA', sym: 'KSA', r: 0.5, zp: null, st: 'short'})];
  const bd = [
    line({fam: 'eq', rule: 'f', k: 402, n: 774, days: 245, from: '2025-10-13', to: '2026-09-25', p: 51.9, ci: [52, 58.1], h1: 53, h2: 51, m: 26, need: 0, vd: 'edge'}),
    line({fam: 'eq', rule: 'p', k: 1155, n: 2306, days: 253, from: '2025-10-01', to: '2026-09-25', ci: [44, 56.2], h1: 50.5, h2: 49.7, need: 0, vd: 'none'}),
    line({fam: 'eq', rule: 'fp', k: 101, n: 196, days: 124, from: '2025-10-20', to: '2026-09-25', ci: [42.8, 60.1], h1: 52, h2: 51, need: 0, vd: 'none'}),
    line({fam: 'bd', rule: 'f', k: 198, n: 398, days: 200, from: '2025-10-13', to: '2026-09-25', ci: [42.9, 56.6], h1: 49, h2: 50.3, need: 0, vd: 'none'}),
    line({fam: 'pm', rule: 'f', k: 76, n: 133, days: 94, from: '2025-11-03', to: '2026-09-25', ci: [48, 66], h1: 58, h2: 56, need: 6, vd: 'short'}),
    line({fam: 'pm', rule: 'p', k: 100, n: 227, days: 103, from: '2025-10-27', to: '2026-09-25', ci: [34.9, 49.7], h1: 45, h2: 43, need: 0, vd: 'anti'}),
    line({fam: 'pm', rule: 'fp', k: 24, n: 48, days: 37, from: '2026-01-12', to: '2026-09-25', ci: [35, 65], h1: 50, h2: 50, need: 63, vd: 'short'})];
  const data = extra => Object.assign({}, trdV96.data, {dv: 1, dsince: '2026-09-28', d, bd}, extra || {});
  const card = (h, sym) => { const key = sym.length > 4 || /^[a-z]/.test(sym) ? '<span>trd.s.' + sym + '</span>' : (/^(EWC|KSA|ILF|VGK|TUR|EIS|EZA|ASEA|EWA|SPY|INDA|MCHI|EWJ|EWY)$/.test(sym) ? '<span>trd.px.' + sym + '</span>' : '<small>' + sym + '</small></span>');
    const i = h.indexOf(key); if (i < 0) return ''; const a = h.lastIndexOf('<div class="etfk trk">', i); return h.slice(a, h.indexOf('</div>', i) + 6); };
  return {row, line, d, bd, data, card};
})();

test('v120: EXTRA110 — 10 języków (pl pierwszy, en drugi), te same klucze i pola w każdym języku, tylko klucze trd.d.*, literały bloku v89 w słowniku, bez „kupuj/sprzedawaj” i bez nazw dostawców', () => {
  const a = 'const EXTRA110=', x0 = html.indexOf(a); assert.ok(x0 > html.indexOf('for(const l in EXTRA109)'), 'po EXTRA109');
  assert.ok(html.includes('for(const l in EXTRA110)if(I18N[l])Object.assign(I18N[l],EXTRA110[l]);'));
  const D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0))), L10 = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'];
  assert.deepEqual(Object.keys(D), L10, 'kolejność języków');
  const K = Object.keys(D.pl).sort(); assert.ok(K.length >= 85, 'liczba kluczy ' + K.length);
  const ph = s => (s.match(/\{\w+\}/g) || []).sort().join(',');
  for (const l of L10) { assert.deepEqual(Object.keys(D[l]).sort(), K, 'klucze ' + l); for (const k of K) { assert.ok(k.startsWith('trd.d.') && typeof D[l][k] === 'string' && D[l][k].trim().length > 0, l + ' ' + k); assert.equal(ph(D[l][k]), ph(D.pl[k]), 'pola ' + l + ' ' + k); } }
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  const lit = [...blk.matchAll(/t\('(trd\.d\.[A-Za-z0-9_.]+)'/g)].map(m => m[1]).filter(k => !/[._]$/.test(k));
  assert.ok(lit.length > 25, 'literały w bloku: ' + lit.length); for (const k of lit) assert.ok(D.pl[k] && D.en[k], 'brak klucza ' + k);
  for (const s of ['buy', 'sell', 'obs.up', 'obs.dn', 'x', 'quiet', 'stale', 'short', 'nodata']) assert.ok(D.pl['trd.d.st.' + s] && D.en['trd.d.st.' + s], 'trd.d.st.' + s);
  for (const s of ['x', 'quiet', 'stale', 'short', 'nodata']) assert.ok(D.pl['trd.d.why.' + s] && D.en['trd.d.why.' + s], 'trd.d.why.' + s);
  for (const s of ['edge', 'anti', 'none', 'short']) assert.ok(D.pl['trd.d.v.' + s] && D.en['trd.d.v.' + s], 'trd.d.v.' + s);
  for (const s of ['f', 'p', 'fp', 'x']) assert.ok(D.pl['trd.d.r.' + s] && D.en['trd.d.r.' + s]); for (const s of ['eq', 'bd', 'pm']) assert.ok(D.pl['trd.d.fam.' + s] && D.en['trd.d.fam.' + s]);
  for (const i of ['1', '2', '3', '4', '5', '6', '7']) assert.ok(D.pl['trd.d.m.' + i] && D.en['trd.d.m.' + i], 'trd.d.m.' + i);
  for (const k of ['trd.d.buy.t', 'trd.d.sell.t', 'trd.d.buy.sub', 'trd.d.sell.sub', 'trd.d.k.of', 'trd.d.k.oos', 'trd.d.k.oos0', 'trd.d.b.short', 'trd.d.ev', 'trd.d.own', 'trd.d.own0']) assert.ok(D.pl[k] && D.en[k], k);
  const bad = /kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|warto kupi|okazj|prognoz|gwarant|na pewno|pewny zysk|wzrośnie|spadnie|buy now|must buy|sure profit|will rise|will fall|guarantee|forecast/i;
  for (const l of ['pl', 'en']) for (const k of K) { if (k === 'trd.d.disc' || k.startsWith('trd.d.m.') || k === 'trd.d.b.sub' || k === 'trd.d.b.note') continue; assert.doesNotMatch(D[l][k], bad, `${l} ${k}: ${D[l][k]}`); }
  assert.ok(D.pl['trd.d.disc'].includes('nie jest rekomendacj') && D.en['trd.d.disc'].includes('not a recommendation'), 'ostrzeżenie');
  assert.ok(D.pl['trd.d.v.anti'].includes('nie odwracamy') && D.pl['trd.d.m.5'].includes('strony nie odwracamy'), '„anti” nie odwraca strony');
  const prov = /ishares|state street|ssga|blackrock|twelve|coingecko/i; for (const l of L10) for (const k of K) assert.doesNotMatch(D[l][k], prov, `${l} ${k}`);
  assert.ok(D.pl['trd.d.k.of'] === '{e} z 7' && D.en['trd.d.k.of'] === '{e} of 7', '„0 z 7” to wartość');
  for (const l of L10) { assert.ok(D[l]['trd.d.nocr'].includes('{v}') && !/Trend[a-zy]* global|global trends|全球趋势|グローバルトレンド/i.test(D[l]['trd.d.nocr']), 'nota krypto: nazwa widoku z przycisku, ' + l);
    assert.ok(D[l]['trd.d.empty.st'].includes('{s}') && D[l]['trd.d.empty.st'].includes('{n}'), 'pusta strona z nieaktualnymi: ' + l); }
  assert.ok(D.pl['trd.d.lg'].includes('żółty') && D.en['trd.d.lg'].includes('yellow'), 'legenda tłumaczy żółty napis „odwrotnie”');
  assert.ok(/brak porównania z historią/.test(D.pl['trd.d.r.f.nz']) && D.pl['trd.d.r.f.nz'].includes('{v}') && D.pl['trd.d.r.p.nz'].includes('{p}'), 'liczba bez porównania ≠ brak danych');
});

test('v120: bez klucza `d` w pliku — TRENDY jak dotąd (bez bloku dziennego, bez nagłówka „Tło”), hak w renderTrendy, CSS bloku', () => {
  assert.ok(html.includes("const dly=trdDaily(D,cr);w.innerHTML=head+dly+(dly?`<h2 class=\"trd-wk mtxt\">${t('trd.d.wk')}</h2>`:'')+disc+(!cr?"), 'hak (v120.1): blok dzienny na górze, potem „Tło” i tygodniowe ostrzeżenie');
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  for (const f of ['trdDaily', 'trdDRow', 'trdDWhy', 'trdDCard', 'trdDPool', 'trdDKpis']) assert.ok(blk.includes('function ' + f + '(') && blk.indexOf('function ' + f + '(') < blk.indexOf('function renderTrendy(){'), f + ' przed renderTrendy');
  assert.ok(blk.includes("if(!D||!Array.isArray(D.d))return '';"), 'bez `d` → pusty napis');
  assert.ok(blk.includes("const TRD_DST=['buy','sell','obs','x','quiet','stale','short','nodata'];"), '8 stanów');
  const {make, data} = trdV96, st = {mode: 'trendy'}, f = make(st); f.trdApply(data); const g = f.el.innerHTML;
  assert.ok(!g.includes('trd.d.') && !g.includes('trd-wk') && !g.includes('trd-daily') && g.includes('trd.k.in') && g.includes('id="trd-method"'), 'wynik bez `d` nie zawiera nic z bloku dziennego');
  st.trdv = 'crypto'; f.renderTrendy(); const c = f.el.innerHTML; assert.ok(!c.includes('trd.d.') && !c.includes('trd-wk'), 'krypto też');
  const css = html.slice(html.indexOf('/* v120 sygnały dzienne'), html.indexOf('/* v105 wieloryby */'));
  assert.ok(css.includes('#trendy .trd-d h3{margin:14px 0 6px}') && css.includes('#trendy .trd-d .etfk.trk b{white-space:nowrap}') && css.includes('.trd-wk{margin:') && css.includes('#trendy .trd-d .gkpis{grid-template-columns:repeat(4,minmax(0,1fr))}') && css.includes('@media (max-width:1240px){#trendy .trd-d .gkpis{grid-template-columns:repeat(2,minmax(0,1fr))}}'), 'CSS: 4 kafle, 2 na węższych ekranach, wartości w jednej linii');
});

test('v120: blok dzienny — listy stron, kolory tylko przy przewadze, „anti” = odznaka po stronie kierunku, „Bez sygnału” w kolejności x/quiet/stale/short, kafle 2 / 1 / 4 / „1 z 7”, sortowanie wg przewagi i siły', () => {
  const {make} = trdV96, {data, card} = trdV120, st = {mode: 'trendy'}, f = make(st); f.trdApply(data()); const g = f.el.innerHTML;
  const i0 = g.indexOf('id="trd-daily"'), iw = g.indexOf('<h2 class="trd-wk mtxt">trd.d.wk</h2>'), ik = g.indexOf('trd.k.in');
  assert.ok(i0 > 0 && i0 < g.indexOf('<b>trd.disc</b>') && iw > i0 && g.indexOf('<b>trd.disc</b>') > iw && ik > iw, 'v120.1: blok dzienny pierwszy, potem „Tło”, tygodniowe ostrzeżenie i kafle tygodnia');
  const iB = g.indexOf('trd.d.buy.t'), iS = g.indexOf('trd.d.sell.t'), iR = g.indexOf('id="trd-drest"'), iP = g.indexOf('id="trd-dbd"'), iM = g.indexOf('id="trd-dmethod"');
  assert.ok(i0 < iB && iB < iS && iS < iR && iR < iP && iP < iM && iM < iw, 'kolejność: kupno, sprzedaż, bez sygnału, skuteczność, metoda');
  assert.ok(g.includes('<h2>trd.d.t{"d":"') && g.includes('<p class="pnote">trd.d.sub</p><p class="pnote"><b>trd.d.disc</b></p><p class="pnote trd-dlg"><i class="tdot pos"></i><i class="tdot neg"></i><i class="tdot neu"></i><i class="tdot"></i> trd.d.lg</p>'), 'nagłówek z datą, podtytuł, ostrzeżenie, legenda (z żółtą kropką dla „odwrotnie”)');
  assert.ok(g.includes('<h3 class="mtxt"><i class="tg pos">▲</i><b>trd.d.buy.t</b></h3><p class="pnote">trd.d.buy.sub</p><div class="etfkpis">') && g.includes('<h3 class="mtxt"><i class="tg neg">▼</i><b>trd.d.sell.t</b></h3><p class="pnote">trd.d.sell.sub</p><div class="etfkpis">'));
  const buy = g.slice(iB, iS), sell = g.slice(iS, iR), rest = g.slice(iR, iP);
  const ewz = card(buy, 'EWZ'), ivv = card(buy, 'IVV'), slv = card(sell, 'SLV');
  assert.ok(ewz.includes('<b class="pos">▲ ●●○<i class="sr">trd.d.s{&quot;s&quot;:2}</i><small>trd.d.st.buy</small></b>') && ewz.includes('trd.d.v.edge') && ewz.includes('<i class="tg pos">trd.d.v.edge</i>'), 'EWZ: zielony, 2 kropki, odznaka „częściej w tę stronę”: ' + ewz);
  assert.ok(ewz.includes('trd.d.r.f.in{"w":"trd.d.w2","v":"+95 trd.u.m USD"}') && ewz.includes('trd.d.r.p.q (+1.90%)') && !ewz.includes('trd.d.r.p.up') && ewz.includes('trd.d.nx{"d":"') && ewz.includes('trd.d.ev{"rule":"trd.d.r.f","fam":"trd.d.fam.eq","p":"51.9","k":402,"n":774,"days":245,"lo":"52.0","hi":"58.1"}') && ewz.includes('trd.d.own{"k":9,"n":15}'), 'EWZ: powody, skuteczność linii, własne k/n: ' + ewz);
  assert.ok(ivv.includes('<b class="na">▲ ●○○<i class="sr">trd.d.s{&quot;s&quot;:1}</i><small>trd.d.st.obs.up</small></b>') && ivv.includes('<i class="tg">trd.d.v.none</i>') && ivv.includes('trd.d.r.f.q (+412 trd.u.m USD)') && ivv.includes('trd.d.r.p.up{"w":"trd.d.pw1","p":"+0.84%"}'), 'IVV: szara obserwacja po stronie kupna z odznaką „brak przewagi”: ' + ivv);
  assert.ok(buy.indexOf('<small>EWZ</small>') < buy.indexOf('<small>IVV</small>'), 'przewaga przed obserwacją');
  assert.ok(slv && slv.includes('<b class="na">▼ ●○○<i class="sr">trd.d.s{&quot;s&quot;:1}</i><small>trd.d.st.obs.dn</small></b>') && slv.includes('<i class="tg neu">trd.d.v.anti</i>') && !buy.includes('<small>SLV</small>'), 'SLV: „anti” = szara obserwacja po stronie sprzedaży, odznaka, strona nie odwrócona: ' + slv);
  assert.ok(g.includes('<span>trd.s.fe_bra <small>EWZ</small></span>') && g.includes('<span>trd.s.tw</span>') && g.includes('<span>trd.px.EWC</span>'), 'nazwy: grupa + ticker, kraj, rynek z listy cen');
  assert.ok(rest.includes('<summary>trd.d.none.t{"n":4}</summary>'), 'Bez sygnału dziś (4)');
  const pos = ['XLK', 'EWC', 'tw', 'KSA'].map(s => rest.indexOf(card(rest, s))); assert.ok(pos.every(p => p >= 0) && pos[0] < pos[1] && pos[1] < pos[2] && pos[2] < pos[3], 'kolejność x, quiet, stale, short: ' + pos);
  for (const s of ['XLK', 'EWC', 'tw', 'KSA']) assert.ok(!buy.includes(card(rest, s)) && !sell.includes(card(rest, s)), s + ' tylko w „Bez sygnału”');
  assert.ok(card(rest, 'XLK').includes('<b class="na">•<small>trd.d.st.x</small></b>') && card(rest, 'XLK').includes('<br>trd.d.why.x'), 'XLK: sprzeczne');
  assert.ok(card(rest, 'EWC').includes('<small>trd.d.st.quiet</small>') && card(rest, 'EWC').includes('trd.d.r.p.q (+0.21%)') && !card(rest, 'EWC').includes('trd.d.r.f.na') && card(rest, 'EWC').includes('<br>trd.d.why.quiet'), 'EWC: rynek tylko z ceną — bez zdania o braku przepływu');
  const tw = card(rest, 'tw'); assert.ok(tw.includes('<small>trd.d.st.stale</small>') && tw.includes('trd.d.r.ob.out{"w":"trd.d.sw2","v":"−33.0 trd.u.b TWD · trd.d.usd{\\"v\\":\\"−1.01 trd.u.b USD\\"}"}') && tw.includes('trd.d.why.stale{"d":"'), 'Tajwan: sprzedaż zagranicy, kwota w TWD i USD, nieaktualne: ' + tw);
  assert.ok(card(rest, 'KSA').includes('<small>trd.d.st.short</small>') && card(rest, 'KSA').includes('trd.d.r.p.nz{"p":"+0.50%"}') && !card(rest, 'KSA').includes('trd.d.r.p.na') && card(rest, 'KSA').includes('<br>trd.d.why.short'), 'KSA: za mało historii — liczba dnia jest (+0,50%), tylko bez porównania z historią (nie „brak danych”)');
  assert.ok(g.includes('trd.d.k.buy</span></div><div class="k-val pos">2</div><small class="mtxt">trd.s.fe_bra (EWZ) · trd.s.fe_us (IVV)</small><div class="k-foot"><span class="dlt up">▲</span><span class="ksrc" title="trd.d.k.edge{&quot;e&quot;:1}">'), 'kafel kupna: 2, zielony (1 z przewagą), nazwy od najsilniejszej');
  assert.ok(g.includes('trd.d.k.sell</span></div><div class="k-val">1</div><small class="mtxt">trd.s.fe_silver (SLV)</small><div class="k-foot"><span class="dlt na">•</span><span class="ksrc" title="trd.d.k.noedge">'), 'kafel sprzedaży: 1, bez koloru (obserwacja)');
  assert.ok(g.includes('trd.d.k.none</span></div><div class="k-val">4</div><small class="mtxt">trd.d.k.nline{"q":1,"x":1,"s":1,"o":1}</small></div>'), 'kafel „bez sygnału”: 4');
  assert.ok(g.includes('trd.d.k.rules</span></div><div class="k-val">trd.d.k.of{"e":1}</div><small class="mtxt">trd.d.k.oos0{"d":"') && g.includes('title="trd.d.k.hist"'), 'kafel reguł: „1 z 7”, licznik od wdrożenia bez par');
  assert.ok(!g.includes('trd.d.none.all'), 'jest linia z przewagą — bez zdania „żadna z 7 reguł”');
  const pool = g.slice(iP, iM); assert.equal((pool.match(/<div class="etfk trk">/g) || []).length, 7, '7 linii zbiorczych');
  assert.ok(pool.includes('<span>trd.d.b.name{&quot;fam&quot;:&quot;trd.d.fam.eq&quot;,&quot;rule&quot;:&quot;trd.d.r.f&quot;}</span><b>51.9%</b>') && pool.includes('trd.b.kn{"k":402,"n":774} · trd.d.b.days{"d":245} · trd.d.b.per{"a":"') && pool.includes('trd.b.ci{"lo":"52.0","hi":"58.1"}<br>trd.d.b.halves{"a":"53.0","b":"51.0"} · trd.d.b.oos{"k":0,"n":0}<br><i class="tg pos">trd.d.v.edge</i>'), 'linia eq·f: procent, k/n, dni, okres, zakres, połowy, od wdrożenia, odznaka');
  assert.ok(pool.includes('<span>trd.d.b.name{&quot;fam&quot;:&quot;trd.d.fam.pm&quot;,&quot;rule&quot;:&quot;trd.d.r.f&quot;}</span><b class="na">—</b>') && pool.includes('<i class="tg">trd.d.b.short{"d":94,"need":6}</i>') && pool.includes('<i class="tg neu">trd.d.v.anti</i>'), 'krótka linia: „—” zamiast procentu; anti żółte');
  assert.ok(pool.indexOf('&quot;rule&quot;:&quot;trd.d.r.f&quot;}</span>') < pool.indexOf('&quot;fam&quot;:&quot;trd.d.fam.eq&quot;,&quot;rule&quot;:&quot;trd.d.r.p&quot;') && pool.indexOf('trd.d.fam.bd') < pool.indexOf('trd.d.fam.pm'), 'kolejność 7 linii jak w regułach');
  assert.ok(pool.includes('<p class="pnote">trd.d.b.sub</p>') && pool.includes('<p class="pnote">trd.d.b.note</p>'), 'opis i nota o przypadkowej przewadze');
  assert.ok(g.includes('<summary>trd.d.m.t{"v":1}</summary><p class="pnote">trd.d.m.1</p>') && g.includes('<p class="pnote">trd.d.m.7</p></details></section>'), 'metoda z wersją reguły, 7 akapitów');
  /* sortowanie: w warstwie „przewaga” siła dnia, nie wielkość odchylenia */
  const {row} = trdV120, f2 = make({mode: 'trendy'});
  f2.trdApply(data({at: '2026-09-25T11:00:00Z', d: [row({id: 'XLF', grp: 'fe_fin', iss: 'ssga', sym: 'XLF', f: 900, cur: 'USD', fu: 900, zf: 9.5, rule: 'f', dir: 1, side: 'buy', str: 2, st: 'buy', vd: 'edge'}),
    row({id: 'EWZ', grp: 'fe_bra', iss: 'ishares', sym: 'EWZ', f: 12, cur: 'USD', fu: 12, zf: 1.1, r: 1.9, zp: 2.4, rule: 'fp', dir: 1, side: 'buy', str: 3, st: 'buy', vd: 'edge'}),
    row({id: 'XLE', grp: 'fe_energy', iss: 'ssga', sym: 'XLE', f: 40, cur: 'USD', fu: 40, zf: 1.2, rule: 'f', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none'})]}));
  const h2 = f2.el.innerHTML, o = ['EWZ', 'XLF', 'XLE'].map(s => h2.indexOf('<small>' + s + '</small></span>'));
  assert.ok(o[0] > 0 && o[0] < o[1] && o[1] < o[2], 'EWZ (siła 3) przed XLF (siła 2, choć odchylenie 9,5), obserwacja na końcu: ' + o);
  const e3 = trdV120.card(h2, 'EWZ'); assert.ok(e3.includes('<b class="pos">▲ ●●●<i class="sr">trd.d.s{&quot;s&quot;:3}</i>') && e3.includes('trd.d.r.f.in{"w":"trd.d.w1"') && e3.includes('trd.d.r.p.up{"w":"trd.d.pw2"'), 'EWZ fp: 3 kropki; przepływ „wyraźnie” (1,1), cena „mocno” (2,4): ' + e3);
  assert.ok(trdV120.card(h2, 'XLF').includes('trd.d.r.f.in{"w":"trd.d.w2"'), 'XLF: 9,5 rozrzutu i siła 2 → „dużo”');
  assert.ok(h2.includes('<div class="k-val pos">3</div><small class="mtxt">trd.s.fe_bra (EWZ) · trd.s.fe_fin (XLF) · trd.s.fe_energy (XLE)</small>'), 'kafel: 3 nazwy w tej kolejności');
});

test('v120: wszystkie linie bez przewagi → zdanie „żadna z 7 reguł” i kafel „0 z 7” (nie „—”); ze słownikiem pl: „1 z 7” i „0 z 7”, „Bez sygnału dziś (4)”', () => {
  const {make} = trdV96, {data, bd, row} = trdV120;
  const none = bd.map(b => Object.assign({}, b, {vd: b.vd === 'short' ? 'short' : 'none', ci: [45, 55]}));
  const f = make({mode: 'trendy'}); f.trdApply(data({bd: none, d: [row({id: 'IVV', grp: 'fe_us', iss: 'ishares', sym: 'IVV', f: 412.3, cur: 'USD', fu: 412.3, zf: 1.4, rule: 'f', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none', ik: 18, in: 34})]}));
  const g = f.el.innerHTML;
  assert.ok(g.includes('<p class="pnote">trd.d.none.all</p><h3 class="mtxt"><i class="tg pos">▲</i><b>trd.d.buy.t</b>'), 'zdanie o braku przewagi przed listami');
  assert.ok(g.includes('<div class="k-val">trd.d.k.of{"e":0}</div>') && !g.includes('<div class="k-val na">'), '„0 z 7” to wartość, nie „—”');
  assert.ok(g.includes('<div class="k-val">1</div>') && g.includes('<b class="na">▲ ●○○') && g.includes('<p class="pnote">trd.d.empty</p>'), 'obserwacja po stronie kupna; strona sprzedaży pusta = zdanie');
  assert.ok(!g.includes('id="trd-drest"'), 'bez kart „Bez sygnału” — bez zwijanego bloku');
  const DP = {}; for (const m of html.matchAll(/const (EXTRA(?:8\d|9\d|1\d\d))=/g)) { const x = html.indexOf(m[0]); Object.assign(DP, JSON.parse(html.slice(x + m[0].length, html.indexOf(';\n', x))).pl || {}); }
  const tp = (k, o) => (DP[k] || k).replace(/\{(\w+)\}/g, (_, n) => o && o[n] !== undefined ? o[n] : '');
  const f2 = make({mode: 'trendy'}, false, tp); f2.trdApply(data()); const g2 = f2.el.innerHTML;
  assert.ok(g2.includes('<div class="k-val">1 z 7</div>') && g2.includes('<summary>Bez sygnału dziś (4)</summary>') && g2.includes('<span>Akcje Brazylii <small>EWZ</small></span>') && g2.includes('<span>Tajwan · akcje</span>') && g2.includes('<h2>Następna sesja: co mówią dane z ') && g2.includes('<h2 class="trd-wk mtxt">Tło: ostatni tydzień danych</h2>'), 'teksty pl: ' + g2.slice(g2.indexOf('id="trd-daily"'), g2.indexOf('id="trd-daily"') + 400));
  /* liczby w teście formatuje zastępcze nfmt z kropką (na stronie: Intl wg języka — „1,90%”) */
  assert.ok(g2.includes('pieniądze: napływ dużo większy niż zwykle (+95 mln USD)') && g2.includes('cena w zwykłym zakresie (+1.90%)') && g2.includes('cena: dzień wyraźnie w górę (+0.84%)') && g2.includes('cena +0.50% — brak porównania z historią') && g2.includes('inwestorzy zagraniczni: sprzedawali dużo więcej niż zwykle (−33.0 mld TWD · ≈ −1.01 mld USD)'), 'zdania z powodami po polsku: ' + g2.slice(g2.indexOf('inwestorzy zagraniczni'), g2.indexOf('inwestorzy zagraniczni') + 120));
  assert.ok(g2.includes('▲ ●●○<i class="sr">siła 2 z 3 — opisuje dzień, nie skuteczność</i><small>strona kupna</small>') && g2.includes('<small>strona sprzedaży (obserwacja)</small>') && g2.includes('w historii częściej odwrotnie — strony nie odwracamy'), 'stan pod znaczkiem bez powtórzonego znaczka; anti słowami');
  const dn = trdV120.d.map(r => r.vd === 'edge' ? Object.assign({}, r, {st: 'obs', vd: 'none'}) : r);   /* wiersze zgodne z liniami: żaden nie ma przewagi */
  const f3 = make({mode: 'trendy'}, false, tp); f3.trdApply(data({bd: none, d: dn})); assert.ok(f3.el.innerHTML.includes('<div class="k-val">0 z 7</div>') && f3.el.innerHTML.includes('Dziś żadna z 7 reguł'), '„0 z 7” po polsku');
});

test('v120: złe wiersze pominięte (stan, siła, kierunek, id, niezgodna strona), nieznana linia zbiorcza pominięta, brak `bd` → kafel „—” a karty zostają; brak liczb = „—”, nigdy 0', () => {
  const {make} = trdV96, {data, row, bd, card} = trdV120, f = make({mode: 'trendy'});
  const badRows = [row({id: 'IVV', st: 'weird'}), row({id: 'EWC', str: 4}), row({id: 'EWC', dir: 2}), row({id: 'a b', st: 'quiet'}), row({id: 'XLK', grp: 'fe_tech', rule: 'f', dir: 1, side: 'sell', str: 1, st: 'buy', vd: 'edge'}),
    row({id: 'SLV', fam: 'pm', rule: 'p', dir: -1, side: 'buy', str: 1, st: 'obs', vd: 'none'}), row({id: 'KSA', date: '25.09.2026', st: 'quiet'}), row({id: 'EWC', vd: 'maybe'}), null, 'x'];
  f.trdApply(data({d: badRows.concat([row({id: 'EWA', sym: 'EWA', r: null, zp: null, st: 'nodata'})]), bd: bd.concat([{fam: 'cr', rule: 'f', k: 10, n: 10, vd: 'edge'}, {fam: 'eq', rule: 'f', k: 5, n: 5, vd: 'edge'}, {fam: 'eq', rule: 'p', k: 1, n: 2, vd: 'perhaps'}])}));
  const g = f.el.innerHTML;
  assert.ok(g.includes('id="trd-daily"') && !g.includes('<small>IVV</small>') && !g.includes('trd.px.EWC') && !g.includes('<small>XLK</small>') && !g.includes('<small>SLV</small>') && !g.includes('trd.px.KSA'), 'złe wiersze nie dają kart');
  assert.ok(g.includes('<div class="k-val">1</div><small class="mtxt">trd.d.k.nline{"q":0,"x":0,"s":0,"o":1}</small>') && g.includes('<summary>trd.d.none.t{"n":1}</summary>'), 'został jeden wiersz „brak danych dnia”');
  const ewa = card(g, 'EWA'); assert.ok(ewa.includes('<b class="na">•<small>trd.d.st.nodata</small></b>') && ewa.includes('trd.d.r.p.na') && ewa.includes('<br>trd.d.why.nodata') && !ewa.includes('0%') && !ewa.includes('trd.d.r.f.na'), 'brak liczb = „—” i słowa, nigdy 0: ' + ewa);
  assert.equal((g.slice(g.indexOf('id="trd-dbd"'), g.indexOf('id="trd-dmethod"')).match(/<div class="etfk trk">/g) || []).length, 7, 'nieznana rodzina, duplikat i zły werdykt pominięte — nadal 7 linii');
  assert.ok(g.includes('<div class="k-val">trd.d.k.of{"e":1}</div>'), 'duplikat eq·f (5 z 5) nie liczy się drugi raz');
  const f2 = make({mode: 'trendy'}); f2.trdApply(data({at: '2026-09-25T12:00:00Z', bd: undefined})); const g2 = f2.el.innerHTML;
  assert.ok(g2.includes('trd.d.k.rules</span></div><div class="k-val na">—</div>') && g2.includes('<small>EWZ</small>') && !g2.includes('id="trd-dbd"') && !g2.includes('trd.d.none.all'), 'bez `bd`: kafel „—”, karty są, bez bloku linii i bez zdania „żadna z 7 reguł” (nie wiemy)');
  const ewz = card(g2, 'EWZ'); assert.ok(ewz.includes('<b class="pos">▲ ●●○') && !ewz.includes('trd.d.ev{') && ewz.includes('<i class="tg pos">trd.d.v.edge</i> · trd.d.own{"k":9,"n":15}'), 'karta bez linii zbiorczej: bez zdania o skuteczności, odznaka z wiersza zostaje');
  const f3 = make({mode: 'trendy'}); f3.trdApply(data({at: '2026-09-25T13:00:00Z', d: []})); const g3 = f3.el.innerHTML;
  assert.ok(g3.includes('id="trd-daily"') && g3.includes('<div class="k-val">0</div>') && g3.includes('trd.d.k.empty') && g3.includes('<p class="pnote">trd.d.empty</p>') && g3.includes('<h2>trd.d.t{"d":"—"}</h2>'), 'pusta lista `d`: blok z zerami i „dziś nikt”, data „—”');
});

test('v120: widok krypto — tylko nota i ostrzeżenie (bez kafli i list), widok global nie chowa paneli tygodnia; otwarte bloki dzienne zostają otwarte po odświeżeniu', () => {
  const {make} = trdV96, {data} = trdV120, opened = [];
  const el = {innerHTML: '', q: [], querySelectorAll(sel) { assert.equal(sel, 'details[open]'); return this.q; },
    querySelector(sel) { const d = {id: sel.slice(1)}; Object.defineProperty(d, 'open', {set(v) { if (v) opened.push(d.id); }}); return this.innerHTML.includes('id="' + d.id + '"') ? d : null; }};
  const st = {mode: 'trendy'}, f = make(st, false, undefined, el); f.trdApply(data()); const g = el.innerHTML;
  assert.ok(g.includes('id="trd-daily"') && g.includes('trd.k.in') && g.includes('trd.e.t') && g.includes('trd.b.t') && g.includes('id="trd-method"') && g.includes('<p class="pfoot">inst.file{"t":"2026-09-25T10:00:00Z"} · eng.disclaimer</p>'), 'global: blok dzienny + wszystkie panele tygodnia');
  el.q = [{id: 'trd-drest'}, {id: 'trd-dmethod'}, {id: 'trd-method'}]; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drest', 'trd-dmethod', 'trd-method'], 'odświeżenie — otwarte bloki dzienne zostają otwarte');
  st.trdv = 'crypto'; f.renderTrendy(); const c = el.innerHTML; assert.deepEqual(opened.splice(0), [], 'krypto — własne bloki');
  assert.ok(c.includes('<section class="panel pcard trd-d"><h2>trd.d.t{"d":"') && c.includes('<p class="pnote">trd.d.nocr{"v":"trd.v.global"}</p><p class="pnote"><b>trd.d.disc</b></p></section><h2 class="trd-wk mtxt">trd.d.wk</h2>'), 'krypto: nota + ostrzeżenie + nagłówek „Tło”');
  assert.ok(!c.includes('id="trd-daily"') && !c.includes('trd.d.buy.t') && !c.includes('trd.d.k.buy') && !c.includes('id="trd-dbd"') && c.includes('trd.kc.in') && c.includes('trd.b.nocr'), 'krypto: bez kafli i list dziennych, kafle krypto zostają');
  el.q = []; st.trdv = 'global'; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drest', 'trd-dmethod', 'trd-method'], 'powrót do global — bloki znowu otwarte');
});

test('v120 (poprawki po przeglądzie): liczba bez z ≠ brak danych; „strzeliło” i „dużo” z reguły i siły, nie z zaokrąglonego z; pusta strona z nieaktualnymi; „żadna z 7” tylko gdy znamy 7 linii; nota krypto z nazwą przycisku', () => {
  const {make} = trdV96, {data, row, bd, card} = trdV120;
  const R = (d, extra) => { const f = make({mode: 'trendy'}); f.trdApply(data(Object.assign({at: '2026-09-25T14:' + String(R.n = (R.n || 0) + 1).padStart(2, '0') + ':00Z', d}, extra || {}))); return f.el.innerHTML; };
  /* 1) liczba dnia jest, z nie ma (mniej niż 40 porównywalnych dni albo same zera w tle — serwer daje wtedy z = null) */
  const g1 = R([row({id: 'SPEM', grp: 'fe_em', iss: 'ssga', sym: 'SPEM', f: 25, cur: 'USD', fu: 25, zf: null, r: 0.3, zp: 0.36, st: 'quiet'}),
    row({id: 'EEM', grp: 'fe_em', iss: 'ishares', sym: 'EEM', f: null, cur: 'USD', zf: null, r: null, zp: null, st: 'nodata'}),
    row({id: 'hk', sym: 'FXI', f: 1200, cur: 'HKD', fu: 154, zf: null, r: -0.4, zp: null, st: 'short'}),
    row({id: 'TLT', fam: 'bd', grp: 'fe_ustl', iss: 'ishares', sym: 'TLT', f: -52, cur: 'USD', fu: -52, zf: -0.3, r: -0.2, zp: null, st: 'quiet'})]);
  const spem = card(g1, 'SPEM'); assert.ok(spem.includes('trd.d.r.f.nz{"v":"+25') && !spem.includes('trd.d.r.f.na') && spem.includes('trd.d.r.p.q (+0.30%)'), 'SPEM: przepływ +25 mln USD pokazany, bez porównania — nie „brak danych”: ' + spem);
  assert.ok(card(g1, 'EEM').includes('trd.d.r.f.na') && card(g1, 'EEM').includes('trd.d.r.p.na') && !card(g1, 'EEM').includes('.nz{'), 'EEM: naprawdę brak liczb → „brak danych”');
  const hk = card(g1, 'hk'); assert.ok(hk.includes('trd.d.r.f.nz{"v":"+1.20 trd.u.b HKD · trd.d.usd') && hk.includes('trd.d.r.p.nz{"p":"−0.40%"}'), 'Hongkong: kwota w HKD i USD, cena — obie bez porównania: ' + hk);
  assert.ok(card(g1, 'TLT').includes('trd.d.r.p.nz{"p":"−0.20%"} trd.d.r.p.bd'), 'obligacje: cena bez porównania + zdanie, że cena nie wchodzi do reguły');
  /* 2) serwer decyduje z odchyleń przed zaokrągleniem: 0,996 → reguła „none”, a do pliku idzie 1.0; 1,996 → siła bez punktu za ≥ 2, w pliku 2.0 */
  const g2 = R([row({id: 'IVV', grp: 'fe_us', iss: 'ishares', sym: 'IVV', f: 9.8, cur: 'USD', fu: 9.8, zf: 1.0, r: 0.1, zp: 0.2, rule: 'none', st: 'quiet'}),
    row({id: 'EFA', grp: 'fe_dev', iss: 'ishares', sym: 'EFA', f: 40, cur: 'USD', fu: 40, zf: 1.0, r: 1.1, zp: 1.2, rule: 'p', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none'}),
    row({id: 'XLK', grp: 'fe_tech', iss: 'ssga', sym: 'XLK', f: 300, cur: 'USD', fu: 300, zf: 2.0, r: 0.1, zp: 0.2, rule: 'f', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none'}),
    row({id: 'XLE', grp: 'fe_energy', iss: 'ssga', sym: 'XLE', f: -80, cur: 'USD', fu: -80, zf: -0.5, r: -2.1, zp: -2.0, rule: 'p', dir: -1, side: 'sell', str: 1, st: 'obs', vd: 'none'}),
    row({id: 'XLF', grp: 'fe_fin', iss: 'ssga', sym: 'XLF', f: 500, cur: 'USD', fu: 500, zf: 2.0, r: 0.2, zp: 0.3, rule: 'f', dir: 1, side: 'buy', str: 2, st: 'obs', vd: 'none'}),
    row({id: 'AGG', fam: 'bd', grp: 'fe_agg', iss: 'ishares', sym: 'AGG', f: -300, cur: 'USD', fu: -300, zf: -1.5, r: -0.3, zp: -1.1, rule: 'f', dir: -1, side: 'sell', str: 1, st: 'obs', vd: 'none'})]);
  const ivv = card(g2, 'IVV'); assert.ok(ivv.includes('trd.d.r.f.q (+9.8 trd.u.m USD)') && !ivv.includes('trd.d.r.f.in') && ivv.includes('<br>trd.d.why.quiet'), 'IVV: reguła „none” → przepływ w zwykłym zakresie, choć z w pliku = 1.0: ' + ivv);
  const efa = card(g2, 'EFA'); assert.ok(efa.includes('trd.d.r.f.q (+40') && efa.includes('trd.d.r.p.up{"w":"trd.d.pw1"'), 'EFA: reguła p → strzeliła tylko cena: ' + efa);
  assert.ok(card(g2, 'XLK').includes('trd.d.r.f.in{"w":"trd.d.w1"'), 'XLK: siła 1 (bez punktu za ≥ 2) → „wyraźnie”, choć z w pliku = 2.0');
  assert.ok(card(g2, 'XLE').includes('trd.d.r.p.dn{"w":"trd.d.pw1"') && card(g2, 'XLE').includes('trd.d.r.f.q ('), 'XLE: cena „wyraźnie” (siła 1), przepływ spokojny');
  assert.ok(card(g2, 'XLF').includes('trd.d.r.f.in{"w":"trd.d.w2"'), 'XLF: siła 2 → „dużo”');
  assert.ok(card(g2, 'AGG').includes('trd.d.r.f.out{"w":"trd.d.w1"') && card(g2, 'AGG').includes('trd.d.r.p.dn{"w":"trd.d.pw1","p":"−0.30%"} trd.d.r.p.bd'), 'obligacje: cena tylko opisowo (poza regułą)');
  /* 3) pusta strona, ale nieaktualne karty wskazywały w jej kierunku */
  const g3 = R([row({id: 'tw', sym: 'EWT', date: '2026-09-24', nx: '2026-09-25', live: false, age: 2, f: -32964.6, cur: 'TWD', fu: -1013.2, zf: -2.3, r: -0.4, zp: -0.5, rule: 'f', dir: -1, side: 'none', str: 2, st: 'stale', vd: 'none'}),
    row({id: 'XLU', grp: 'fe_util', iss: 'ssga', sym: 'XLU', date: '2026-09-24', nx: '2026-09-25', live: false, age: 2, f: 3, cur: 'USD', fu: 3, zf: 0.2, r: -1.4, zp: -1.3, rule: 'p', dir: -1, side: 'none', str: 1, st: 'stale', vd: 'none'}),
    row({id: 'EWC', sym: 'EWC', r: 0.21, zp: 0.3, st: 'quiet'})]);
  const b3 = g3.slice(g3.indexOf('trd.d.buy.t</b>'), g3.indexOf('trd.d.sell.t</b>')), s3 = g3.slice(g3.indexOf('trd.d.sell.t</b>'), g3.indexOf('id="trd-drest"'));
  assert.ok(b3.includes('<p class="pnote">trd.d.empty</p>') && s3.includes('<p class="pnote">trd.d.empty.st{"n":2,"s":"trd.d.k.none"}</p>') && !s3.includes('trd.d.empty</p>'), 'kupno: nic; sprzedaż: 2 nieaktualne w tym kierunku — w „Bez sygnału dziś”');
  assert.ok(g3.includes('trd.d.k.buy</span></div><div class="k-val">0</div><small class="mtxt">trd.d.k.empty</small>') && g3.includes('trd.d.k.sell</span></div><div class="k-val">0</div><small class="mtxt">trd.d.k.emptyst{"n":2}</small>'), 'kafle: „dziś nikt” / „dziś nikt aktualny · nieaktualnych: 2”');
  /* 4) „żadna z 7 reguł” tylko przy komplecie 7 linii bez przewagi i bez wiersza z przewagą */
  const none = bd.map(b => Object.assign({}, b, {vd: b.vd === 'short' ? 'short' : 'none'})), ivvO = row({id: 'IVV', grp: 'fe_us', iss: 'ishares', sym: 'IVV', f: 412.3, cur: 'USD', fu: 412.3, zf: 1.4, rule: 'f', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none'});
  const g4 = R([ivvO], {bd: none.slice(0, 6)}); assert.ok(!g4.includes('trd.d.none.all') && g4.includes('trd.d.k.rules</span></div><div class="k-val na">—</div>'), '6 z 7 linii bez przewagi: nie wiemy o siódmej — bez zdania, kafel „—”');
  const g5 = R([ivvO], {bd: none}); assert.ok(g5.includes('trd.d.none.all') && g5.includes('<div class="k-val">trd.d.k.of{"e":0}</div>'), 'komplet 7 linii bez przewagi: zdanie i „0 z 7”');
  const g6 = R([Object.assign({}, ivvO, {st: 'buy', vd: 'edge'})], {bd: none}); assert.ok(!g6.includes('trd.d.none.all'), 'wiersz z przewagą przy liniach bez przewagi (niespójny plik) — bez sprzecznego zdania');
  /* 5) nota krypto nazywa widok tak, jak podpisany jest przycisk — w każdym języku (de: przycisk ma tekst z en) */
  const dict = l => { const o = {}; for (const m of html.matchAll(/const (EXTRA(?:8\d|9\d|1\d\d))=/g)) { const x = html.indexOf(m[0]); Object.assign(o, JSON.parse(html.slice(x + m[0].length, html.indexOf(';\n', x)))[l] || {}); } return o; };
  const DE = dict('de'), EN = dict('en'), tde = (k, o) => String(DE[k] ?? EN[k] ?? k).replace(/\{(\w+)\}/g, (_, n) => o && o[n] !== undefined ? o[n] : '');
  const st = {mode: 'trendy', trdv: 'crypto'}, fc = make(st, false, tde); fc.trdApply(data()); const c = fc.el.innerHTML;
  assert.ok(c.includes('in der Ansicht „' + tde('trd.v.global') + '“') && c.includes('>' + tde('trd.v.global') + '</button>'), 'de: nota i przycisk tą samą nazwą: ' + tde('trd.v.global'));
  /* 6) „anti” zostaje żółtą odznaką na szarej karcie po stronie kierunku — legenda to tłumaczy */
  const g7 = R(trdV120.d); assert.ok(card(g7, 'SLV').includes('<b class="na">▼') && card(g7, 'SLV').includes('<i class="tg neu">trd.d.v.anti</i>') && g7.includes('<i class="tdot neu"></i>'), 'SLV: szara karta, żółta odznaka „odwrotnie”, żółta kropka w legendzie');
});

test('v120.1: TRENDY — sekcja dzienna przed tygodniowym wprowadzeniem; tytuł i podtytuł global o następnej sesji (EXTRA115 ×10)', () => {
  assert.ok(html.includes("w.innerHTML=head+dly+(dly?`<h2 class=\"trd-wk mtxt\">${t('trd.d.wk')}</h2>`:'')+disc+(!cr?"), 'dzienna sekcja pierwsza, potem „Tło” i tygodniowe wprowadzenie');
  assert.ok(html.includes("<span class=\"gsub\">${t(cr?'trd.subc':'trd.subd')}</span>"), 'v123.1: widok krypto ma własny podtytuł o następnej dobie');
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA115') > apl.indexOf('EXTRA80') && apl.indexOf('EXTRA80') >= 0, 'EXTRA115 nałożony po EXTRA80 — nadpisuje trd.h1 (kolejne słowniki nie mają trd.h1)');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    assert.ok(t('trd.subd') !== 'trd.subd' && t('trd.h1').length > 10, L);
    assert.ok(!/kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|buy now|guarantee|forecast/i.test(t('trd.h1') + t('trd.subd')), L + ' bez trybu rozkazującego i obietnic');
  }
  assert.equal(v96src.tFor('pl')('trd.h1'), 'Dokąd płynie kapitał: następna sesja i ostatni tydzień');
});

test('v121: ceny krypto — pomocnicze: wiersze po dacie, zmiana wobec dokładnie k dni wcześniej (luka = brak, nie zero), wyprowadzenie, format ceny i obrotu', () => {
  const k0 = html.indexOf('/* ===================== v121: CENY KRYPTO'), k1 = html.indexOf('\nfunction kcItems(', k0);
  assert.ok(k0 > 0 && k1 > k0, 'blok v121 w stronie');
  const T = (k, v) => k + (v ? JSON.stringify(v) : '');
  const K = new Function('t', 'nfmt', 'fPct', 'escH', 'LOCALE', 'LANG', html.slice(k0, k1) + '\nreturn {KC, kcRows, kcDay, kcChg, kcDerive, kcSeries, kcTone, kcPct, kcPx, kcVol};')(
    T, (v, d) => Number(v).toFixed(d), (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%', v96src.escH, {pl: 'pl-PL'}, 'pl');
  const day = i => new Date(Date.UTC(2026, 8, 25) - i * 864e5).toISOString().slice(0, 10);   // 2026-09-25 minus i dni
  const rows = [];
  for (let i = 40; i >= 0; i--) if (i !== 7) rows.push([day(i), 100 + (40 - i)]);   // luka dokładnie 7 dni przed ostatnim
  rows.push(['zła data', 5], ['2026-09-10', 0], ['2026-09-11', 'x'], 'tekst');
  const r = K.kcRows(rows);
  assert.equal(r.length, 40, 'złe wiersze odrzucone (data, zero, tekst)'); assert.equal(r[0][0], day(40)); assert.equal(r[r.length - 1][0], '2026-09-25');
  assert.equal(K.kcDay('2026-09-25', -7), '2026-09-18'); assert.equal(K.kcDay('2026-03-01', -1), '2026-02-28'); assert.equal(K.kcDay('x', -1), '');
  const c1 = K.kcChg(rows, 1); assert.ok(c1 && c1.t === '2026-09-24' && Math.abs(c1.p - (140 / 139 - 1) * 100) < 1e-9, '1 D wobec 24.09');
  assert.equal(K.kcChg(rows, 7), null, 'luka 7 dni wcześniej = brak, nie zero');
  const c30 = K.kcChg(rows, 30); assert.ok(c30 && c30.t === '2026-08-26' && Math.abs(c30.p - (140 / 110 - 1) * 100) < 1e-9, '30 D wobec 26.08');
  assert.equal(K.kcChg([], 1), null); assert.equal(K.kcChg([['2026-09-25', 5]], 1), null, 'jeden wiersz — brak porównania');
  const v = K.kcDerive({d: rows, vol: [['2026-09-25', 1520256979], ['2026-09-24', 5]]});
  assert.equal(v.date, '2026-09-25'); assert.equal(v.close, 140); assert.equal(v.vol, 1520256979); assert.equal(v.d7, null); assert.equal(v.n, 40); assert.equal(v.from, day(40));
  assert.equal(K.kcDerive({d: rows}).vol, null, 'bez obrotu = null'); assert.equal(K.kcDerive(null), null); assert.equal(K.kcDerive({d: []}), null); assert.equal(K.kcDerive('x'), null);
  K.KC.data = {q: {BTC: {d: rows}}}; assert.equal(K.kcSeries('btc').length, 40, 'zaczep dla TRENDÓW: seria pary'); assert.equal(K.kcSeries('ETH').length, 0); K.KC.data = null; assert.equal(K.kcSeries('BTC').length, 0);
  assert.equal(K.kcTone(0.04), ''); assert.equal(K.kcTone(0.05), 'pos'); assert.equal(K.kcTone(-0.3), 'neg'); assert.equal(K.kcTone(null), '');
  assert.equal(K.kcPct(null), '<span class="cell mono na" title="kc.na">—</span>', 'brak z powodem');
  assert.ok(K.kcPct({p: 2.34, t: '2026-09-24'}).startsWith('<span class="cell mono pos" title="kc.vs{') && K.kcPct({p: 2.34, t: '2026-09-24'}).endsWith('">+2.3%</span>'), 'zmiana z datą porównania w podpowiedzi');
  assert.ok(K.kcPct({p: -0.04, t: '2026-09-24'}).includes('class="cell mono" title=') && K.kcPct({p: -0.04, t: '2026-09-24'}).endsWith('>0.0%</span>'), 'zero po zaokrągleniu — bez koloru');
  assert.equal(K.kcPx(84099.99), '84100'); assert.equal(K.kcPx(4034.5), '4035'); assert.equal(K.kcPx(403.456), '403.46'); assert.equal(K.kcPx(0.2468), '0.2468'); assert.equal(K.kcPx(null), '—'); assert.equal(K.kcPx(0), '—');
  assert.equal(K.kcVol(1520256979), '1.52 wh.u.mld USDT'); assert.equal(K.kcVol(49214794), '49.2 wh.u.mln USDT'); assert.equal(K.kcVol(250e6), '250 wh.u.mln USDT'); assert.equal(K.kcVol(null), '');
});
test('v121: ceny krypto — panel z pliku: 10 wierszy z logo monety, datą i wiekiem, brak = „—” z powodem, para z błędem = dopisek, plik za stary albo bez pliku = ukryty', () => {
  const k0 = html.indexOf('/* ===================== v121: CENY KRYPTO'), k1 = html.indexOf('\nfunction kcApply(', k0);
  assert.ok(k0 > 0 && k1 > k0);
  const T = (k, v) => k + (v ? JSON.stringify(v) : '');
  const run = (D, apply) => {
    const el = {innerHTML: '', hidden: true, querySelectorAll: () => [], querySelector: () => null};
    const r = new Function('$', 't', 'nfmt', 'fPct', 'escH', 'LOCALE', 'LANG', 'engDate', 'gAgeNote', 'icoWrap', 'coinImg', 'D',
      html.slice(k0, k1) + (apply ? '\nreturn kcOk(D);' : '\nKC.data=D;renderKc();return null;'))(
      q => q === '#c-ceny-krypto' ? el : null, T, (v, d) => Number(v).toFixed(d), (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%', v96src.escH, {pl: 'pl-PL'}, 'pl',
      s => '[' + String(s) + ']', d => ' · age(' + String(d).slice(0, 10) + ')', x => `<span class="icos">${x}</span>`, (s, c) => `<i class="ico ${c}">${s}</i>`, D);
    return apply ? r : el;
  };
  const now = new Date().toISOString(), y = new Date(Date.now() - 864e5).toISOString().slice(0, 10), y2 = new Date(Date.now() - 2 * 864e5).toISOString().slice(0, 10);
  const mk = (c0, c1) => ({d: [[y2, c0], [y, c1]], vol: [[y, 1520256979]]});
  const D = {at: now, keep: 420, ok: {BTC: true, ETH: false}, bledy: {ETH: 'ETH: HTTP Error 500'}, q: {BTC: mk(80000, 84099.99), ETH: mk(4000, 3900), DOGE: {d: [[y, 0.2468]]}}};
  const el = run(D), out = el.innerHTML;
  assert.ok(!el.hidden && out.includes('kc.t') && out.includes('kc.sub') && out.includes('inst.file{"t":"[' + now + ']"}') && out.includes('class="live on"'), 'nagłówek, czas pliku, plik młody');
  assert.equal((out.match(/<\/tr>/g) || []).length, 11, 'nagłówek + każda z 10 monet ma wiersz'); assert.equal((out.match(/<th>/g) || []).length, 4, 'cztery kolumny zawsze widoczne'); assert.equal((out.match(/<th class="kc-w">/g) || []).length, 2, 'dwie kolumny ukrywane na telefonie');
  assert.ok(out.includes('<i class="ico sm">BTC</i>') && out.includes('<b>BTC</b>') && out.includes('<span class="cell mono">84100</span>') && out.includes('>+5.1%</span>'), 'BTC: logo, zamknięcie bez groszy, 1 D +5,1 %: ' + out.slice(out.indexOf('<b>BTC'), out.indexOf('<b>BTC') + 400));
  assert.ok(out.includes('<span class="cell mono">1.52 wh.u.mld USDT</span>'), 'obrót doby w USDT (waluta kwotowana pary)');
  assert.ok(out.includes(' · age(' + y + ')'), 'data i wiek zamknięcia');
  assert.ok(out.includes('>−2.5%</span>') && out.includes(' · kc.stale</small>'), 'ETH: spadek i dopisek o nieudanym pobraniu (liczby z poprzedniego pliku)');
  assert.ok(out.includes('<span class="cell mono">0.2468</span>'), 'DOGE z czterema miejscami');
  assert.equal((out.match(/title="kc\.na"/g) || []).length, 2 + 2 + 3 + 7 * 3, 'BTC/ETH bez 7 D i 30 D, DOGE bez żadnej zmiany, 7 monet bez serii — brak z powodem, nigdy zero');
  assert.equal((out.match(/class="kc-na"/g) || []).length, 7, 'siedem monet bez serii'); assert.ok(out.includes('<small>kc.nodata</small>') && out.includes('<span class="cell mono na">—</span>'));
  assert.ok(out.includes('kc.note{"d":') && out.includes('"n":"420"}') && out.includes('kc.not1') && out.includes('kc.not3') && out.includes('eng.notsays') && out.includes('kc.foot') && out.includes('eng.disclaimer'), 'nota, „czego nie mówią”, stopka');
  assert.ok(!/Binance|Coinbase|Kraken|Bybit|OKX/i.test(out), 'bez nazw giełd i dostawców w panelu');
  const old = run(Object.assign({}, D, {at: new Date(Date.now() - 4 * 3600e3).toISOString()}));
  assert.ok(old.innerHTML.includes('class="live off"'), 'plik starszy niż 3 h = wskaźnik wyłączony');
  assert.ok(run(D, true) === true && run(null, true) === false && run({at: now, q: {}}, true) === false && run({at: 'x', q: D.q}, true) === false, 'plik ok: czas, q, świeże zamknięcie');
  const stale = new Date(Date.now() - 20 * 864e5).toISOString().slice(0, 10);
  assert.equal(run({at: now, q: {BTC: {d: [[stale, 5]]}}}, true), false, 'najnowsze zamknięcie sprzed 20 dni = plik odrzucony');
  const Z = run(null); assert.ok(Z.hidden && Z.innerHTML === '', 'bez pliku sekcja ukryta');
  const E = run({at: now, q: {BTC: {d: []}}}); assert.ok(E.hidden && E.innerHTML === '', 'plik bez żadnej serii = ukryty');
});
test('v121: ceny krypto — słownik EXTRA111 w 10 językach (te same klucze, miejsca na daty i liczby), bez nazw dostawców; sekcja po archiwum, styl, plik, odświeżanie co 60 min', () => {
  const KEYS = ['kc.t', 'kc.sub', 'kc.c.coin', 'kc.c.close', 'kc.c.1d', 'kc.c.7d', 'kc.c.30d', 'kc.c.vol', 'kc.vs', 'kc.na', 'kc.nodata', 'kc.stale', 'kc.note', 'kc.foot', 'kc.not1', 'kc.not2', 'kc.not3'];
  const e0 = html.indexOf('const EXTRA111='), e1 = html.indexOf(';\nfor(const l in EXTRA111)', e0);
  assert.ok(e0 > 0 && e1 > e0 && html.includes('for(const l in EXTRA111)if(I18N[l])Object.assign(I18N[l],EXTRA111[l]);\n'), 'słownik EXTRA111 podpięty');
  const E = JSON.parse(html.slice(e0 + 'const EXTRA111='.length, e1));
  const PROV = /Binance|Coinbase|Kraken|Bybit|OKX|CoinGecko|CoinPaprika|CoinMarketCap|Kaiko|Yahoo|Stooq/i;
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    assert.equal(Object.keys(E[L]).sort().join('|'), KEYS.slice().sort().join('|'), L + ': klucze EXTRA111');
    const t = v96src.tFor(L);
    for (const k of KEYS) { assert.ok(v96src.I18N[L][k] && t(k) !== k && t(k).trim(), L + ' ' + k); assert.ok(!PROV.test(t(k)), 'dostawca: ' + L + ' ' + k); }
    assert.ok(E[L]['kc.vs'].includes('{t}') && E[L]['kc.note'].includes('{d}') && E[L]['kc.note'].includes('{n}'), L + ': miejsca na datę i liczbę');
    assert.ok(!t('kc.note', {d: 'QQ', n: '420'}).includes('{') && t('kc.note', {d: 'QQ', n: '420'}).includes('420'), L + ' note');
    assert.ok(/USDT/.test(E[L]['kc.c.close']) && /UTC/.test(E[L]['kc.not3']), L + ': waluta kwotowana i doba UTC nazwane');
    assert.ok(/USDT/.test(E[L]['kc.foot']) && !/\bUSD\b|美元|米ドル/.test(E[L]['kc.foot']), L + ': obrót doby w USDT, nie w USD');
  }
  assert.ok(v96src.tFor('pl')('kc.sub').includes('nie zmierzony przepływ') && v96src.tFor('en')('kc.sub').includes('not a measured capital flow'), 'notowanie ≠ przepływ');
  assert.ok(v96src.tFor('pl')('kc.sub').includes('nigdy zero') && v96src.tFor('en')('kc.sub').includes('never zero'), 'brak nie jest zerem');
  for (const k of ['wh.u.mld', 'wh.u.mln', 'inst.file', 'eng.notsays', 'eng.disclaimer']) assert.ok(v96src.I18N.pl[k] && v96src.I18N.en[k], 'wspólny klucz używany przez panel: ' + k);
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA111') > apl.indexOf('EXTRA109') && apl.indexOf('EXTRA109') >= 0, 'EXTRA111 po EXTRA109');
  assert.equal(html.split('<section class="panel pcard" id="c-ceny-krypto" hidden></section>').length, 2, 'jedna sekcja');
  const a = html.indexOf('<section class="panel pcard" id="c-archiwum" hidden></section>'), x = html.indexOf('<section class="panel pcard" id="c-ceny-krypto" hidden></section>');
  assert.ok(a > 0 && x > a && x < a + 500, 'CRYPTO: po archiwum własnym');
  assert.ok(html.includes("function kcLoad(){srvJSON('ceny-krypto').then(kcApply);}") && html.includes('KC.timer=setInterval(()=>{if(!document.hidden)kcLoad();},60*60*1000);')
    && html.includes("kcLoad();kcAuto();try{new MutationObserver(()=>renderKc()).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});}catch(e){}"), 'plik serwera, odświeżanie co 60 min, zmiana języka');
  assert.ok(html.includes('/* v121 ceny krypto */') && html.includes('#c-ceny-krypto .etft{min-width:0;width:100%}') && html.indexOf('/* v121 ceny krypto */') < html.indexOf('/* v105 wieloryby */'), 'styl przed stylem wielorybów');
  assert.equal(html.split('/* ===================== v121: CENY KRYPTO').length, 2, 'jeden blok JS');
  assert.ok(html.indexOf('/* ===================== v121: CENY KRYPTO') < html.indexOf('/* ===================== v98: USA'), 'blok przed blokiem USA');
});
test('v121: ceny krypto — podpis licencji danych (CC BY-NC-SA 4.0, „Binance Vision”) w akapicie wymaganych podpisów strony Źródła; nigdzie indziej', () => {
  const CREDIT = 'Crypto spot candles (daily and hourly, USDT pairs) and futures long/short metrics: <a href="https://data.binance.vision/" target="_blank" rel="noopener">Binance Vision</a>, <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener">CC BY-NC-SA 4.0</a> — values derived from them on this site are shared under the same licence, for non-commercial use';
  const out = v103zr.render('pl', {at: v103zr.FRESH, ok: {'ceny-krypto': true}}).out;
  const cut = out.indexOf('<section class="panel pgc zr-attr2">'); assert.ok(cut > 0);
  const card = out.slice(0, cut), attr = out.slice(cut);
  assert.ok(attr.includes(CREDIT), 'podpis w akapicie wymaganych podpisów');
  assert.ok(attr.indexOf('CC BY-NC 4.0</a>) · ' + CREDIT + ' · ') > 0 && attr.indexOf(CREDIT) < attr.indexOf('<br>'), 'po podpisie Coin Metrics, w linii serwisów');
  assert.ok(!/Binance/.test(card), 'karta stanu bez nazwy dostawcy');
  assert.equal(html.split('by-nc-sa/4.0/').length, 2, 'jeden link do licencji CC BY-NC-SA 4.0 w całej stronie');
  const k0 = html.indexOf('/* ===================== v121: CENY KRYPTO'), k1 = html.indexOf('/* ===================== v98: USA', k0);
  assert.ok(!/Binance/i.test(html.slice(k0, k1)), 'blok panelu bez nazwy dostawcy');
});

test('v121: insiderzy — blok strony: kafelki (zakupy, sprzedaż, stosunek, zgłoszenia), największe spółki, lista 30 dni ze słupkami, dzień w toku, brak ≠ zero, ukryte bez danych, wczytanie pliku', () => {
  const i0 = html.indexOf('/* ===================== v121: INSIDERZY SPÓŁEK USA'), i1 = html.indexOf('\nfunction insLoad(', i0);
  assert.ok(i0 > 0 && i1 > i0, 'blok v121 na stronie');
  const mk = ($) => new Function('$', 't', 'nfmt', 'escH', 'gAgeNote', 'engDate', 'LOCALE', 'LANG', html.slice(i0, i1) +
    '\nreturn {INS, INS_DAYS, INS_MAX_AGE, insRows, insUsd, insRatio, insExact, insTop, insList, insTops, insBody, renderIns, insApply};')(
    $ || (() => null), (k, o) => k + (o ? JSON.stringify(o) : ''), (v, d) => Number(v).toFixed(d),
    s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])), d => ' · age(' + d + ')', iso => 'D(' + iso + ')', {pl: 'pl-PL', en: 'en-US'}, 'en');
  const X = mk();
  assert.equal(X.insUsd(1.5e6), '1.5 ins.mln'); assert.equal(X.insUsd(2.25e9), '2.25 ins.mld'); assert.equal(X.insUsd(37047.9), '37.0 ins.tys'); assert.equal(X.insUsd(500), '500 USD'); assert.equal(X.insUsd(null), '—'); assert.equal(X.insUsd(-1), '—'); assert.equal(X.insUsd(0), '0 USD', 'prawdziwe zero dnia bez transakcji zostaje zerem');
  assert.equal(X.insRatio(35), '35.0'); assert.equal(X.insRatio(0.42), '0.42'); assert.equal(X.insRatio(0.001), '0.001'); assert.equal(X.insRatio(0.0004), '<0.001'); assert.equal(X.insRatio(0), '0.000'); assert.equal(X.insRatio(null), '—');
  assert.equal(X.insExact(1234.6), '1235 USD'); assert.equal(X.insExact(null), '');
  assert.deepEqual(X.insRows([['2026-09-25', 1, 2, 1, 1], ['2026-09-24', null, null, null, null], ['zła', 1, 2], ['2026-09-23', -1, 2], 'x', ['2026-09-22', 5, 'a']]), [['2026-09-24', null, null, null, null], ['2026-09-25', 1, 2, 1, 1]], 'wiersze bez liczby (null) zostają jako brak, ujemne i śmieci odpadają, kolejność rosnąca');
  const today = new Date().toISOString().slice(0, 10);
  const days = []; for (let i = 34; i >= 0; i--) { const d = new Date(Date.now() - i * 864e5); days.push(d.toISOString().slice(0, 10)); }
  const hist = days.map((d, i) => i === 10 ? [d, null, null, null, null] : [d, (i + 1) * 1e6, i === 30 ? 0 : (35 - i) * 1e6, i, 35 - i]);
  const D = {at: '2026-09-26T04:20:00+00:00', day: today, done: true, n_filings: 812, n_queued: 700, n_parsed: 700, n_fail: 2, buys_usd: 35e6, sells_usd: 1e6, n_buy: 34, n_sell: 1, ratio: 35, share: 97.2,
    top_buys: [['Acme & Sons', 'ACME', 20e6], ['Beta <Corp>', null, 15e6], ['zero', 'Z', 0]], top_sells: [['Gamma', 'GAM', 1e6]], hist};
  const body = X.insBody(D);
  assert.ok(body.includes('ins.k.buy') && body.includes('35.0 ins.mln') && body.includes('ins.k.rep{"n":"34"}') && body.includes('title="35000000 USD"'), 'kafelek zakupów z liczbą zgłoszeń i dokładną kwotą');
  assert.ok(body.includes('ins.k.sell') && body.includes('1.0 ins.mln') && body.includes('ins.k.rep{"n":"1"}'), 'kafelek sprzedaży');
  assert.ok(body.includes('ins.k.ratio') && body.includes('>35.0<small>ins.k.share{"p":"97.2"}') , 'stosunek z udziałem');
  assert.ok(body.includes('ins.k.nv{"n":"700","m":"700"}') && body.includes('ins.cap{"n":"812","m":"700"}') && !body.includes('ins.full'), 'dzień z limitem 700 opisany');
  assert.ok(body.includes('age(' + today + ')'), 'wiek dnia danych przy kafelkach');
  assert.ok(body.includes('Acme &amp; Sons') && body.includes('<small>ACME</small>') && body.includes('Beta &lt;Corp&gt;') && !body.includes('>zero<'), 'największe spółki: nazwy uciekane, ticker w small, zero pominięte');
  assert.ok(body.includes('ins.h.topb{"d":') && body.includes('ins.h.tops{"d":'), 'nagłówki list z dniem');
  const tb = body.slice(body.indexOf('<tbody>'), body.indexOf('</tbody>'));
  assert.equal((tb.match(/<tr/g) || []).length, X.INS_DAYS, 'lista ma 30 wierszy'); assert.ok(body.includes('ins.h.hist{"n":"30"}'));
  const first = tb.slice(0, tb.indexOf('</tr>'));
  assert.ok(first.includes('width:100%') && first.includes('ins-bar s') && first.includes('35.0 ins.mln') && first.includes('mono pos">+34.0 ins.mln') && first.includes('34 / 1'), 'najnowszy dzień pierwszy: pełny słupek zakupów, netto dodatnie, zgłoszenia');
  const rows = tb.split('</tr>');
  const nullRow = rows.find(r => r.includes('cell mono na">—'));
  assert.ok(nullRow && !nullRow.includes('ins-bar') && nullRow.includes('mono na">—'), 'dzień bez liczby: „—” bez słupka, nie zero');
  const zeroSell = rows[4];
  assert.ok(zeroSell.includes('0 USD') && zeroSell.includes('width:1%'), 'zero sprzedaży = zero (najwęższy słupek), nie brak');
  assert.ok(!body.includes('ins.part'), 'pełny dzień bez „w toku”');
  const P = X.insBody(Object.assign({}, D, {done: false, n_parsed: 120, n_queued: 700, n_filings: 700}));
  assert.ok(P.includes('ins.part') && P.includes('ins.k.nv{"n":"120","m":"700"}') && P.includes('class="ins-part"') && P.includes('ins.part.s') && !P.includes('ins.cap'), 'dzień w toku oznaczony w kafelku i w wierszu');
  const N = X.insBody(Object.assign({}, D, {ratio: null, share: null, buys_usd: null, n_buy: null, hist: [[today, null, null, null, null]], top_buys: [], top_sells: []}));
  assert.ok(N.includes('ins.k.noshare') && N.includes('class="na"') && !N.includes('ins-top') && N.includes('ins.h.hist{"n":"1"}'), 'brak stosunku i brak kwot = „—”, bez list spółek');
  const Q = X.insBody(Object.assign({}, D, {done: false, n_parsed: 0, buys_usd: null, sells_usd: null, n_buy: 0, n_sell: 0, ratio: null, share: null}));
  assert.ok(!Q.includes('ins.k.rep{"n":"0"}') && Q.includes('ins.k.nv{"n":"0","m":"700"}') && Q.includes('class="na"'), 'nic nie odczytane: „—” bez „0 zgłoszeń” pod spodem (brak ≠ zero)');
  assert.equal(X.insBody(null), ''); assert.equal(X.insBody({day: 'x'}), ''); assert.equal(X.insBody({day: today, hist: []}), '');
  assert.equal(X.insTops({top_buys: 'x', top_sells: null}), '');
  const el = {hidden: false, innerHTML: 'x'}, Y = mk(q => q === '#g-insider' ? el : null);
  Y.renderIns(); assert.ok(el.hidden === true && el.innerHTML === '', 'bez danych — sekcja ukryta');
  Y.insApply(D); assert.ok(el.hidden === false && el.innerHTML.includes('ins.t') && el.innerHTML.includes('ins.sub') && el.innerHTML.includes('inst.file{"t":"D(2026-09-26T04:20:00+00:00)"}') && el.innerHTML.includes('ins.not') && el.innerHTML.includes('ins.delay') && el.innerHTML.includes('eng.disclaimer'), 'panel z nagłówkiem, czasem pliku, notą o opóźnieniu i „czego nie mówią”');
  Y.insApply(null); assert.ok(el.hidden === false && Y.INS.data === D, 'chwilowy błąd pobrania nie zasłania danych');
  const Z = mk(q => q === '#g-insider' ? el : null);
  Z.insApply({at: 'x', day: '2020-01-01', hist: [['2020-01-01', 1, 1, 1, 1]]}); assert.ok(Z.INS.data === null && el.hidden === true, 'dzień starszy niż INS_MAX_AGE — ukryte');
  Z.insApply({day: today}); assert.ok(Z.INS.data === null, 'bez pola at — odrzucone');
  Z.insApply('śmieć'); assert.ok(Z.INS.data === null);
});

test('v121: insiderzy — słownik EXTRA112 w 10 językach (te same klucze, miejsca na liczby, bez nazwy urzędu w panelu); sekcja po archiwum GLOBAL, styl, plik, odświeżanie', () => {
  const KEYS = ['ins.t', 'ins.sub', 'ins.k.buy', 'ins.k.sell', 'ins.k.rep', 'ins.k.ratio', 'ins.k.share', 'ins.k.noshare', 'ins.k.n', 'ins.k.nv', 'ins.part', 'ins.part.s', 'ins.cap', 'ins.full',
    'ins.h.hist', 'ins.c.day', 'ins.c.buy', 'ins.c.sell', 'ins.c.net', 'ins.c.n', 'ins.h.topb', 'ins.h.tops', 'ins.none', 'ins.mln', 'ins.mld', 'ins.tys', 'ins.delay', 'ins.not'];
  const m = html.match(/const EXTRA112=(\{.*?\});\n/s); assert.ok(m, 'słownik EXTRA112 na stronie');
  const X = JSON.parse(m[1]);
  assert.deepEqual(Object.keys(X).sort(), ['de', 'en', 'es', 'fr', 'it', 'ja', 'pl', 'pt', 'ru', 'zh']);
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    assert.deepEqual(Object.keys(X[L]).sort(), KEYS.slice().sort(), 'te same klucze: ' + L);
    const tt = v96src.tFor(L);
    assert.ok(KEYS.every(k => typeof v96src.I18N[L][k] === 'string' && v96src.I18N[L][k].trim()), 'słownik wczytany: ' + L);
    for (const k of KEYS) assert.ok(!/\bSEC\b|EDGAR/.test(tt(k)), L + ' ' + k + ': bez nazwy urzędu w panelu');
    assert.ok(tt('ins.k.rep', {n: '7'}).includes('7') && !tt('ins.k.rep', {n: '7'}).includes('{'), L + ' rep');
    const nv = tt('ins.k.nv', {n: '7', m: '25'}); assert.ok(nv.includes('7') && nv.includes('25') && !nv.includes('{'), L + ' nv');
    const cap = tt('ins.cap', {n: '812', m: '700'}); assert.ok(cap.includes('812') && cap.includes('700') && !cap.includes('{'), L + ' cap');
    assert.ok(tt('ins.k.share', {p: '97,2'}).includes('97,2') && tt('ins.h.hist', {n: '30'}).includes('30') && tt('ins.h.topb', {d: 'XYZ'}).includes('XYZ') && tt('ins.h.tops', {d: 'XYZ'}).includes('XYZ'), L + ' miejsca na liczby');
    assert.ok(/2/.test(tt('ins.delay')), L + ': nota o 2 dniach roboczych');
  }
  assert.ok(v96src.tFor('pl')('ins.t').includes('Insiderzy') && v96src.tFor('en')('ins.t').includes('insiders'), 'tytuł');
  assert.ok(v96src.tFor('pl')('ins.not').includes('nie zero') && v96src.tFor('en')('ins.not').includes('not zero'), 'brak ≠ zero w nocie');
  assert.equal(html.split('<section class="panel pcard" id="g-insider" hidden></section>').length, 2, 'jedno miejsce sekcji');
  const u = html.indexOf('<section class="panel pcard" id="g-archiwum" hidden></section>'), x = html.indexOf('<section class="panel pcard" id="g-insider" hidden></section>');
  assert.ok(x > u && x < u + 400, 'po panelu archiwum (zakładka GLOBAL)');
  assert.ok(html.includes("srvJSON('insider')") && html.includes('/* v121 insiderzy */') && html.includes('#g-insider .etft{min-width:0;width:100%}') && html.includes('#g-insider .ins-bar{'), 'plik, styl');
  assert.ok(html.includes('for(const l in EXTRA112)if(I18N[l])Object.assign(I18N[l],EXTRA112[l]);'), 'słownik dołączony');
  assert.ok(html.includes('if(!ok&&INS.data)return;') && html.includes('INS.timer=setInterval(()=>{if(!document.hidden)insLoad();},60*60*1000)'), 'odświeżanie co 60 min, błąd nie zasłania danych');
  assert.equal(html.split('/* ===================== v121: INSIDERZY SPÓŁEK USA').length, 2);
  const s0 = html.indexOf('<script>'), s1 = html.lastIndexOf('</script>'); new Function(html.slice(s0 + 8, s1));
});

// ===== v121 — obszar stres-opcje: indeks stresu finansowego USA i wskaźniki put/call (plik data/stres.json, słownik EXTRA113) =====
const str121 = (() => {
  const i0 = html.indexOf('/* ===================== v121: STRES FINANSOWY USA'), i1 = html.indexOf('\nfunction strLoad(', i0);
  const mk = ($) => new Function('$', 't', 'nfmt', 'escH', 'gAgeNote', 'engDate', 'LOCALE', 'LANG', html.slice(i0, i1) +
    '\nreturn {STR, STR_COLS, strRows, strMinMax, strDelta, strVal, strFsi, strPc, strPcOn, strBody, renderStr, strApply};')(
    $ || (() => null), (k, o) => k + (o ? JSON.stringify(o) : ''), (v, d) => Number(v).toFixed(d), v96src.escH, d => ' · age(' + d + ')', iso => 'D(' + iso + ')', {pl: 'pl-PL', en: 'en-US'}, 'en');
  return {i0, i1, mk};
})();

test('v121: stres i opcje — pomocnicze: wiersze rosnąco, najniżej/najwyżej z 60 sesji tylko z liczb, zmiana bez zera w kolorze, wzrost stresu na czerwono, brak ≠ zero', () => {
  assert.ok(str121.i0 > 0 && str121.i1 > str121.i0, 'blok v121 na stronie'); const X = str121.mk();
  assert.deepEqual(X.strRows([['2026-09-23', -2.663], ['2026-09-21', -2.727], ['zła', 1], 'x', ['2026-09-22', null], ['2026-09-24', '1']]), [['2026-09-21', -2.727], ['2026-09-22', null], ['2026-09-23', -2.663], ['2026-09-24', null]]);
  const H = []; for (let i = 0; i < 80; i++) { const d = new Date(Date.UTC(2026, 5, 1 + i)); H.push([d.toISOString().slice(0, 10), i === 70 ? null : (i % 7 === 0 ? -3 - i / 100 : -2 + i / 100)]); }
  const mm = X.strMinMax(H, 1, 60);   // ostatnie 60 wierszy (i = 20…79), bez i = 70 (brak) → 59 liczb; najniżej i = 77, najwyżej i = 79
  assert.deepEqual(mm, {n: 59, min: H[77][1], dmin: H[77][0], max: H[79][1], dmax: H[79][0]});
  assert.equal(X.strMinMax([['2026-09-23', 1]], 1, 60), null, 'jedna liczba to nie zakres'); assert.equal(X.strMinMax(null, 1, 60), null); assert.equal(X.strMinMax([['2026-09-23', null], ['2026-09-24', null]], 1, 60), null);
  assert.deepEqual(X.strMinMax([['2026-09-23', 1, 5], ['2026-09-24', 2, 4], ['2026-09-25', 3, null]], 2, 60), {n: 2, min: 4, dmin: '2026-09-24', max: 5, dmax: '2026-09-23'}, 'inna kolumna');
  assert.deepEqual(X.strDelta(0.004, 2, '1 D', 'inv'), {txt: '• 0.00 1 D', cls: ''}, 'zero po zaokrągleniu — bez strzałki i koloru');
  assert.deepEqual(X.strDelta(0.11, 2, '1 D', 'inv'), {txt: '▲ +0.11 1 D', cls: 'neg'}, 'wzrost stresu = czerwony'); assert.deepEqual(X.strDelta(-0.163, 2, '5 S', 'inv'), {txt: '▼ −0.16 5 S', cls: 'pos'});
  assert.deepEqual(X.strDelta(0.05, 2, '1 D', 'none'), {txt: '▲ +0.05 1 D', cls: ''}, 'put/call: bez koloru'); assert.deepEqual(X.strDelta(0.05, 2, '1 D'), {txt: '▲ +0.05 1 D', cls: 'pos'});
  assert.deepEqual(X.strDelta(null, 2, '1 D', 'inv'), {txt: '— 1 D', cls: 'na'}); assert.deepEqual(X.strDelta(NaN, 2, '1 D'), {txt: '— 1 D', cls: 'na'}); assert.deepEqual(X.strDelta(0.01, 2, '', 'inv'), {txt: '▲ +0.01', cls: 'neg'});
  assert.equal(X.strVal(-2.663, 2), '−2.66'); assert.equal(X.strVal(0.75, 2), '0.75'); assert.equal(X.strVal(null, 2), '—'); assert.equal(X.strVal('1', 2), '—'); assert.equal(X.strVal(Infinity, 2), '—');
});

test('v121: stres i opcje — panel z pliku: kafle z datą i wiekiem, składowe w tabeli, put/call wyłączone = wersja samego indeksu (bez noty o wyłączeniu), część bez danych = nota, bez pliku ukryty; EXTRA113 ×10 bez nazw dostawców; sekcja, styl, plik', () => {
  const X = str121.mk();
  const hist = []; for (let i = 0; i < 70; i++) { const d = new Date(Date.UTC(2026, 6, 1 + i)); hist.push([d.toISOString().slice(0, 10), -2 - i / 100]); }
  const fsi = {date: '2026-09-23', value: -2.663, d1: 0.11, d5: -0.163, hist, cols: {credit: {v: null, d1: null}, equity: {v: -0.567, d1: 0.01}, vol: {v: -0.488, d1: 0.118}, zzz: {v: 1, d1: 1}, us: 'x'}};
  const D = {at: '2026-09-26T14:00:00+00:00', ok: {fsi: true}, part_at: {fsi: '2026-09-26T14:00:00+00:00'}, pc_off: true, fsi};
  const b = X.strBody(D);
  assert.ok(b.startsWith('<div class="etfkpis"><div class="etfk"><span>st.k.fsi</span><b>−2.66<small class="neg">▲ +0.11 st.k.d1</small><small class="pos">▼ −0.16 st.k.d5</small></b><small class="mtxt">'), b.slice(0, 300));
  assert.ok(b.includes('2026 · age(2026-09-23)</small></div></div>'), 'data i wiek danych pod kaflem');
  assert.ok(b.includes('st.mm.fsi{"n":"60","min":"−2.69","dmin":"') && b.includes('","max":"−2.10","dmax":"'), 'najniżej/najwyżej z ostatnich 60 wierszy historii');
  assert.equal((b.match(/<tr><td>/g) || []).length, 3, 'tylko znane składowe obecne w pliku (credit, equity, vol); nieznane klucze i śmieci pominięte');
  assert.ok(b.indexOf('st.p.credit') < b.indexOf('st.p.equity') && b.indexOf('st.p.equity') < b.indexOf('st.p.vol'), 'kolejność z listy');
  assert.ok(b.includes('<td><span class="cell mono na">—</span></td><td><span class="cell mono na">—</span></td>'), 'składowa bez liczby: „—” dwa razy, nie zero');
  assert.ok(b.includes('<span class="cell mono">−0.57</span></td><td><span class="cell mono neg">▲ +0.01</span>') && b.includes('<span class="cell mono neg">▲ +0.12</span>'), 'wzrost składowej na czerwono');
  assert.ok(b.includes('st.h.parts') && b.includes('st.c.part') && b.endsWith('<p class="pnote">st.note.fsi</p>') && !b.includes('st.pc.') && !b.includes('st.k.pc') && !b.includes('st.fsi.na') && !b.includes('pnote neu'), 'bez zgody: nota samego indeksu, żadnych kafli put/call ani noty o wyłączeniu');
  assert.equal(X.strPcOn(D), false); assert.equal(X.strPcOn({pc_off: false}), true); assert.equal(X.strPcOn({}), true, 'plik bez pc_off (sprzed wyłączenia) = pełny panel');
  assert.ok(!/undefined|NaN|\[object/.test(b));
  const pc = {date: '2026-09-25', total: 0.75, equity: 0.52, index: null, hist: [['2026-09-24', 0.8, 0.55, 0.87], ['2026-09-25', 0.75, 0.52, null], ['2026-09-23', 0.9, 0.6, 1.0], ['x', 1, 1, 1]]};
  const b2 = X.strBody(Object.assign({}, D, {pc_off: false, pc}));
  assert.ok(b2.includes('<span>st.k.pc</span><b>0.75<small class="">▼ −0.05 st.k.d1</small></b><small class="mtxt">') && b2.includes('age(2026-09-25)'), 'put/call razem ze zmianą wobec poprzedniej sesji z historii, bez koloru');
  assert.ok(b2.includes('<span>st.k.pce</span><b>0.52<small class="">▼ −0.03 st.k.d1</small></b>') && b2.includes('<span>st.k.pci</span><b>—<small class="na">— st.k.d1</small></b>'), 'indeksy bez liczby = „—”, nie zero');
  assert.ok(b2.includes('st.mm.pc{"n":"3","min":"0.75","dmin":"') && b2.includes('","max":"0.90","dmax":"') && !b2.includes('st.pc.na') && b2.endsWith('<p class="pnote">st.note</p>'), 'ze zgodą: pełna nota');
  assert.equal(X.strBody(Object.assign({}, D, {pc})), b, 'bez zgody dane put/call z pliku pomijane');
  assert.ok((b2.match(/<div class="etfk">/g) || []).length === 4 && b2.indexOf('st.k.fsi') < b2.indexOf('st.k.pc'), 'cztery kafle: indeks, potem trzy put/call');
  const b3 = X.strBody({at: 'x', pc_off: false, fsi});
  assert.ok(b3.includes('<p class="pnote neu">st.pc.na</p>') && b3.endsWith('<p class="pnote">st.note</p>'), 'zgoda jest, danych nie ma = nota o braku danych');
  const b4 = X.strBody({at: 'x', pc_off: false, pc});
  assert.ok(b4.includes('<p class="pnote neu">st.fsi.na</p>') && b4.includes('st.k.pc') && !b4.includes('st.h.parts'), 'sam put/call: nota o indeksie, bez tabeli składowych');
  assert.equal(X.strBody({at: 'x', pc_off: true, fsi: {date: '2026-09-23', value: null}}), '', 'indeks bez liczby i put/call wyłączone = nic (sekcja ukryta)'); assert.equal(X.strBody(null), ''); assert.equal(X.strBody({}), '');
  const el = {hidden: false, innerHTML: 'x'}, Y = str121.mk(q => q === '#g-stres' ? el : null);
  Y.renderStr(); assert.ok(el.hidden === true && el.innerHTML === '', 'bez danych — sekcja ukryta');
  Y.strApply({at: 'zły'}); assert.equal(el.hidden, true); Y.strApply({at: '2026-09-26T14:00:00+00:00'}); assert.equal(el.hidden, true, 'plik bez obu części — ukryta');
  Y.strApply(D);
  assert.ok(el.hidden === false && el.innerHTML.includes('<h2>st.t.fsi</h2><p class="pnote">st.sub.fsi</p>') && el.innerHTML.includes('inst.file{"t":"D(2026-09-26T14:00:00+00:00)"}') && el.innerHTML.includes('eng.notsays') && el.innerHTML.includes('eng.disclaimer'), 'bez zgody: tytuł i opis samego indeksu');
  assert.ok(el.innerHTML.includes('<p class="pnote">st.not1</p>') && !el.innerHTML.includes('st.not2') && !el.innerHTML.includes('st.not3') && !el.innerHTML.includes('>st.t<') && !el.innerHTML.includes('>st.sub<'), 'bez zgody: „czego nie mówi” tylko o indeksie');
  Y.strApply(Object.assign({}, D, {pc_off: false, pc}));
  assert.ok(el.innerHTML.includes('<h2>st.t</h2><p class="pnote">st.sub</p>') && el.innerHTML.includes('<p class="pnote">st.not2</p>') && el.innerHTML.includes('<p class="pnote">st.not3</p>') && el.innerHTML.includes('st.k.pc'), 'ze zgodą: pełny tytuł, opis i noty');
  Y.strApply(null); assert.equal(el.hidden, false, 'chwilowy błąd pobrania nie zasłania wczytanych danych');
  // słownik EXTRA113: 10 języków, te same klucze, miejsca na liczby, bez nazw dostawców, przetłumaczone
  const e0 = html.indexOf('const EXTRA113='), e1 = html.indexOf(';\n', e0); assert.ok(e0 > 0 && e1 > e0, 'słownik EXTRA113');
  const E = JSON.parse(html.slice(e0 + 'const EXTRA113='.length, e1)), LANGS = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'];
  const KEYS = ['st.t', 'st.t.fsi', 'st.sub', 'st.sub.fsi', 'st.k.fsi', 'st.k.d1', 'st.k.d5', 'st.k.pc', 'st.k.pce', 'st.k.pci', 'st.h.parts', 'st.c.part', 'st.c.val', 'st.c.d1', 'st.p.credit', 'st.p.equity', 'st.p.safe', 'st.p.funding', 'st.p.vol', 'st.p.us', 'st.p.ae', 'st.p.em',
    'st.mm.fsi', 'st.mm.pc', 'st.pc.na', 'st.fsi.na', 'st.note', 'st.note.fsi', 'st.not1', 'st.not2', 'st.not3'];
  const PUTCALL = /put\/call|пут\/колл|看跌|プット/i;   // „put” samo trafia w „computed”
  const PROV = /OFR|Cboe|CBOE|Office of Financial Research|financialresearch|Chicago Board/i;
  assert.deepEqual(Object.keys(E), LANGS, 'polski pierwszy, dziesięć języków');
  for (const L of LANGS) {
    assert.deepEqual(Object.keys(E[L]).sort(), KEYS.slice().sort(), 'te same klucze: ' + L);
    for (const k of KEYS) { const s = v96src.I18N[L][k]; assert.ok(typeof s === 'string' && s.trim() && s === E[L][k], L + ' ' + k + ' dołączony do I18N'); assert.ok(!PROV.test(s), 'bez nazw dostawców: ' + L + ' ' + k); }
    for (const k of ['st.mm.fsi', 'st.mm.pc']) for (const v of ['{n}', '{min}', '{dmin}', '{max}', '{dmax}']) assert.ok(E[L][k].includes(v), L + ' ' + k + ' ' + v);
    const u = v96src.tFor(L)('st.mm.fsi', {n: '60', min: 'A', dmin: 'B', max: 'C', dmax: 'Q'}); assert.ok(u.includes('60') && u.includes('A') && u.includes('Q') && !u.includes('{'), L + ' ' + u);
    if (!['pl', 'en'].includes(L)) for (const k of ['st.t', 'st.t.fsi', 'st.sub', 'st.sub.fsi', 'st.note.fsi', 'st.not2', 'st.not3']) assert.notEqual(E[L][k], E.en[k], 'przetłumaczone: ' + L + ' ' + k);
    for (const k of ['st.t.fsi', 'st.sub.fsi', 'st.note.fsi', 'st.not1', 'st.k.d5', 'st.mm.fsi']) assert.ok(!PUTCALL.test(E[L][k]), L + ' ' + k + ': wersja samego indeksu bez put/call');
    for (const k of ['st.t', 'st.sub', 'st.note', 'st.not2', 'st.not3']) assert.ok(PUTCALL.test(E[L][k]) || /opcj|opci|option|opzion|opç|опцион|期权|オプション/i.test(E[L][k]), L + ' ' + k + ': pełna wersja mówi o put/call');
    for (const k of ['st.note', 'st.note.fsi']) assert.ok(!/1\s*[–\-〜~]\s*2/.test(E[L][k]) && /2/.test(E[L][k]), L + ' ' + k + ': opóźnienie 2 dni robocze, nie „1–2”');
    assert.ok(/0/.test(E[L]['st.sub.fsi']) && E[L]['st.sub'].startsWith(E[L]['st.sub.fsi'].split(/[.。]/)[0].slice(0, 20)), L + ': opis samego indeksu = początek pełnego');
    assert.ok(/1/.test(E[L]['st.sub']) && /0/.test(E[L]['st.sub']), L + ': opis mówi o progu 0 (stres) i 1 (put/call)');
  }
  assert.ok(E.pl['st.sub'].includes('nie zmierzony przepływ') && E.en['st.sub'].includes('not a measured capital flow') && E.pl['st.sub.fsi'].includes('nie zmierzony przepływ') && E.en['st.sub.fsi'].includes('not a measured capital flow'), 'pomiar warunków ≠ przepływ');
  assert.ok(E.en['st.sub'].includes('from a US options exchange') && E.pl['st.sub'].includes('z jednej z giełd opcji w USA'), 'jedna giełda opcji, nie „cały rynek opcji USA”');
  assert.ok(E.en['st.k.d5'] === '5 business days' && E.pl['st.k.d5'] === '5 dni roboczych' && E.en['st.mm.fsi'].includes('business days') && E.en['st.mm.pc'].includes('sessions') && E.pl['st.mm.pc'].includes('sesjach'), 'indeks: dni robocze (także święta giełdowe); put/call: sesje');
  assert.ok(E.pl['st.note'].includes('opóźnieniem 2 dni roboczych') && E.en['st.note'].includes('lag of 2 business days') && E.pl['st.not3'].startsWith('Put/call:') && E.en['st.not3'].startsWith('Put/call:'), 'opóźnienie 2 dni robocze; „bez sesji” tylko o put/call');
  assert.ok(E.pl['st.not2'].includes('nie jest sygnałem kupna') && E.en['st.not2'].includes('buy or sell signal'), 'bez „kupuj/sprzedawaj”');
  // sekcja, styl, plik, kolejność słownika, odświeżanie
  assert.equal(html.split('<section class="panel pcard" id="g-stres" hidden></section>').length, 2, 'jedno miejsce sekcji');
  const g = html.indexOf('<section class="panel pcard" id="g-archiwum" hidden></section>'), s = html.indexOf('<section class="panel pcard" id="g-stres" hidden></section>'), n = html.indexOf('<section class="panel pcard" id="inst" hidden></section>');
  assert.ok(g > 0 && s > g && n > s, 'w zakładce GLOBAL: po archiwum, przed danymi urzędowymi');
  assert.ok(html.includes("srvJSON('stres')") && html.includes('/* v121 stres */') && html.includes('#g-stres .etfk b small.neg{color:var(--rd-tx)}') && html.includes('#g-stres .etft{min-width:0;width:100%}'), 'plik, styl');
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA113') > apl.indexOf('EXTRA109') && apl.indexOf('EXTRA109') >= 0, 'EXTRA113 dołączony po EXTRA109');
  assert.ok(html.includes("if(!ok&&STR.data)return;") && html.includes("strLoad();strAuto();try{new MutationObserver(()=>renderStr()).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});}catch(e){}"), 'chwilowy błąd nie zasłania danych; zmiana języka');
  assert.ok(html.includes("STR.timer=setInterval(()=>{if(!document.hidden)strLoad();},60*60*1000);"), 'odświeżanie co godzinę (plik zmienia się co 6 h)');
  assert.equal(html.split('/* ===================== v121: STRES FINANSOWY USA').length, 2);
  assert.ok(html.indexOf('/* ===================== v121: STRES FINANSOWY USA') < html.indexOf('/* ===================== v98: USA'), 'blok przed blokiem USA (v98)');
  const blok = html.slice(str121.i0, html.indexOf('\n', html.indexOf('strLoad();strAuto();')));
  assert.ok(!PROV.test(blok), 'kod strony bez nazw dostawców');
});

test('v121: aukcje Skarbu USA — wiersze od najnowszej, strzałki wobec mediany 12 mies., termin i rodzaj papieru, brak ≠ zero, 12 z 40 wierszy, ukryte bez danych', () => {
  const a0 = html.indexOf('/* ===================== v121: AUKCJE PAPIERÓW SKARBOWYCH USA'), a1 = html.indexOf('\nfunction aukLoad(', a0);
  assert.ok(a0 > 0 && a1 > a0, 'blok v121 na stronie');
  const mk = ($) => new Function('$', 't', 'nfmt', 'escH', 'gAgeNote', 'engDate', 'LOCALE', 'LANG', html.slice(a0, a1) +
    '\nreturn {AUK, AUK_ROWS, aukRows, aukKey, aukMed, aukCmp, aukArrow, aukVal, aukPct, aukTerm, aukType, aukYield, aukBody, renderAuk, aukApply};')(
    $ || (() => null), (k, o) => k + (o ? JSON.stringify(o) : ''), (v, d) => Number(v).toFixed(d),
    s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])), d => ' · age(' + d + ')', iso => 'D(' + iso + ')', {pl: 'pl-PL', en: 'en-US'}, 'en');
  const X = mk();
  const row = (date, type, term, btc, ind, extra) => Object.assign({date, type, term, k: type + ' ' + term, reopen: false, btc, indirect_pct: ind, direct_pct: 20.5, dealer_pct: ind == null ? null : 100 - ind - 20.5, yield: 4.5, ykind: 'yld', accepted_bln: 44.0, cusip: 'X'}, extra || {});
  const last = [row('2026-09-24', 'Note', '7-Year', 2.42, 57.2), row('2026-09-24', 'Bill', '8-Week', 2.76, 58.8, {ykind: 'inv', yield: 4.071, accepted_bln: 92.026}),
    row('2026-09-23', 'FRN', '2-Year', 2.63, 59.1, {ykind: 'dm', yield: 0.04}), row('2026-09-17', 'TIPS', '10-Year', 2.24, 59.1, {ykind: 'real', yield: 2.653}),
    row('2026-09-09', 'Note', '10-Year', 2.71, null, {yield: null, accepted_bln: null, reopen: true}), row('2026-09-02', 'Note', '2-Year', 2.60, 50.0)];
  for (let i = 0; i < 8; i++) last.push(row('2026-08-' + (20 - i), 'Bill', '4-Week', 2.9 + i / 100, 60 + i));
  /* plik: śmieci, potem starsze bony od najstarszego, na końcu sześć nowszych aukcji w kolejności pliku (ten sam dzień 24.09: 7-latka przed bonem) */
  const D = {at: new Date().toISOString(), last: [{date: 'bad', type: 'Note', term: '2-Year'}, {date: '2026-19-24', type: 'Note', term: '2-Year', btc: 2.5}, 'x', null, {date: '2026-01-01'}].concat(last.slice(6).reverse(), last.slice(0, 6)),
    med12m: {'Note 7-Year': {btc: 2.40, indirect_pct: 60.0, n: 13}, 'Bill 8-Week': {btc: 2.76, indirect_pct: 55.0, n: 50}, 'Bill 4-Week': {btc: 2.95, indirect_pct: 61.0, n: 50}, 'Note 10-Year': {btc: 2.5, indirect_pct: 60, n: 12}}};
  const R = X.aukRows(D);
  assert.equal(R.length, 14, 'śmieci i data niemożliwa (miesiąc 19) odrzucone'); assert.equal(R[0].k, 'Note 7-Year'); assert.equal(R[1].k, 'Bill 8-Week', 'ten sam dzień — kolejność pliku'); assert.equal(R[13].date, '2026-08-13');
  assert.equal(X.aukCmp(2.42, 2.40, 2), 1); assert.equal(X.aukCmp(2.404, 2.40, 2), 0, 'równe po zaokrągleniu'); assert.equal(X.aukCmp(2.3, 2.5, 2), -1); assert.equal(X.aukCmp(null, 2, 2), null); assert.equal(X.aukCmp(2, undefined, 1), null);
  assert.equal(X.aukVal(null, 2, 2), '<span class="cell mono na">—</span>', 'brak = kreska, nie 0');
  const up = X.aukVal(2.42, 2.40, 2); assert.ok(up.startsWith('<span class="cell mono pos">') && up.includes('2.42') && up.includes('auk-ar pos">▲') && up.includes('auk.med{"v":"2.40"}'), up);
  const dn = X.aukVal(57.2, 60.0, 1, '%'); assert.ok(dn.includes('cell mono neg') && dn.includes('57.2%') && dn.includes('▼') && dn.includes('auk.med{"v":"60.0%"}'), dn);
  const eq = X.aukVal(2.76, 2.76, 2); assert.ok(eq.startsWith('<span class="cell mono">') && eq.includes('auk-ar na">=') , 'tyle samo — bez koloru');
  const nm = X.aukVal(2.6, null, 2); assert.ok(!nm.includes('auk-ar') && nm.includes('auk.nomed'), 'bez mediany — bez strzałki, z notą');
  assert.equal(X.aukTerm('7-Year'), 'auk.y{"n":"7"}'); assert.equal(X.aukTerm('2-Year'), 'auk.y2{"n":"2"}'); assert.equal(X.aukTerm('3-Year'), 'auk.y2{"n":"3"}'); assert.equal(X.aukTerm('10-Year'), 'auk.y{"n":"10"}');
  assert.equal(X.aukTerm('4-Week'), 'auk.w{"n":"4"}'); assert.equal(X.aukTerm('27-Day'), '27-Day', 'nieznany zapis dosłownie'); assert.equal(X.aukTerm(''), ''); assert.equal(X.aukTerm('<b>'), '&lt;b&gt;');
  assert.equal(X.aukType({type: 'Note'}), 'Note', 'zaślepka t zwraca klucz — rodzaj dosłownie'); assert.equal(X.aukType({type: '<x>'}), '&lt;x&gt;');
  assert.equal(X.aukYield({yield: null}), '<span class="cell mono na">—</span>'); assert.ok(X.aukYield({yield: 4.071, ykind: 'inv'}).includes('4.071%') && X.aukYield({yield: 4.071, ykind: 'inv'}).includes('auk.yk.inv'));
  assert.ok(!X.aukYield({yield: 5.085, ykind: 'yld'}).includes('auk.yk'), 'zwykła rentowność bez podpisu');
  const body = X.aukBody(D);
  assert.equal((body.match(/<tr><td>/g) || []).length, 12, '12 z 14 wierszy'); assert.ok(!/undefined|NaN|\[object/.test(body), body.slice(0, 200));
  assert.ok(body.indexOf('auk.y{"n":"7"} · Note') < body.indexOf('auk.w{"n":"8"} · Bill') && body.indexOf('auk.w{"n":"8"} · Bill') < body.indexOf('auk.y2{"n":"2"} · FRN'), 'od najnowszej');
  assert.ok(body.includes('<small class="auk-re">auk.reopen</small>') && (body.match(/auk\.reopen/g) || []).length === 1, 'dodatkowa transza oznaczona raz');
  assert.ok(body.includes('age(2026-09-24)') && body.includes('age(2026-09-09)'), 'każda aukcja z wiekiem');
  const r10 = body.slice(body.indexOf('auk.y{"n":"10"} · Note'), body.indexOf('auk.y2{"n":"2"} · Note'));
  assert.equal((r10.match(/<span class="cell mono na">—<\/span>/g) || []).length, 4, '10-latka bez udziałów, rentowności i kwoty: cztery kreski, żadnego zera');
  assert.ok(r10.includes('2.71') && r10.includes('▲'), 'stosunek ofert 2,71 wobec mediany 2,5 = wyżej');
  assert.ok(body.includes('auk.k.last') && body.includes('auk.k.btc') && body.includes('auk.k.ind') && body.includes('auk.k.above'), 'cztery kafle');
  assert.ok(body.includes('<b class="pos">2.42 <span class="auk-ar pos">▲</span></b>') && body.includes('<b class="neg">57.2% <span class="auk-ar neg">▼</span></b>'), 'ostatnia aukcja: stosunek wyżej, udział niżej');
  /* stosunek ofert: 7-latka ▲, 8-tyg. =, 10-latka ▲, sześć 4-tyg. 2.90–2.95 wobec 2.95 (=, reszta ▼); bez mediany (FRN, TIPS, 2-latka) nie liczą się → 2 z 9.
     udział pośrednich: 7-latka ▼, 8-tyg. ▲, 10-latka bez liczby, 4-tyg. 60–65 wobec 61 (62–65 ▲) → 5 z 8 */
  assert.ok(body.includes('auk.k.abovev{"n":"2","m":"9"}') && body.includes('auk.k.aboven{"k":"5","m":"8"}'), 'kafel „powyżej mediany” liczy tylko aukcje z liczbą i medianą: ' + body.slice(body.indexOf('auk.k.above'), body.indexOf('auk.k.above') + 160));
  assert.ok(body.includes('auk.n{"n":"12"}') && body.includes('auk.leg') && body.includes('auk.note') && body.includes('auk.c.auc') && body.includes('class="auk-w"'), 'noty i nagłówki');
  assert.equal(X.aukBody({at: 'x', last: []}), ''); assert.equal(X.aukBody(null), ''); assert.equal(X.aukBody({at: 'x', last: [{date: 'bad'}]}), '');
  const nomed = X.aukBody({at: 'x', last: [row('2026-09-24', 'Bond', '30-Year', 2.39, 60)]});
  assert.ok(nomed.includes('auk.nomed') && !nomed.includes('auk-ar') && !nomed.includes('auk.k.above'), 'bez median: noty, bez strzałek, bez kafla „powyżej mediany”');
  const el = {hidden: false, innerHTML: 'x'}, Y = mk(q => q === '#g-aukcje' ? el : null);
  Y.renderAuk(); assert.ok(el.hidden === true && el.innerHTML === '', 'bez danych — sekcja ukryta');
  Y.aukApply({at: new Date().toISOString(), last: []}); assert.equal(el.hidden, true, 'plik bez aukcji — ukryta');
  Y.aukApply(D);
  assert.ok(el.hidden === false && el.innerHTML.includes('auk.t') && el.innerHTML.includes('auk.sub') && el.innerHTML.includes('inst.file{"t":"D(' + D.at + ')"}') && el.innerHTML.includes('eng.notsays') && el.innerHTML.includes('auk.not') && el.innerHTML.includes('eng.disclaimer'));
  Y.aukApply(null); assert.equal(el.hidden, false, 'chwilowy błąd pobrania nie zasłania danych');
  const Z = mk(q => q === '#g-aukcje' ? el : null);
  Z.aukApply(Object.assign({}, D, {at: new Date(Date.now() - 50 * 864e5).toISOString()})); assert.equal(el.hidden, true, 'plik starszy niż 45 dni — ukryta');
  Z.aukApply(Object.assign({}, D, {at: 'kiedyś'})); assert.equal(el.hidden, true, 'plik bez daty — ukryta');
  assert.equal(X.AUK_ROWS, 12);
});
test('v121: aukcje — słownik w 10 językach bez nazw dostawców, sekcja po archiwum (GLOBAL), styl, plik co 60 min, wiersz Metodologii z flagą', () => {
  const KEYS = ["auk.t", "auk.sub", "auk.c.auc", "auk.c.btc", "auk.c.ind", "auk.c.dir", "auk.c.dlr", "auk.c.yld", "auk.c.amt", "auk.k.last", "auk.k.btc", "auk.k.ind", "auk.k.above", "auk.k.abovev", "auk.k.aboven", "auk.med", "auk.nomed", "auk.reopen", "auk.tp.Bill", "auk.tp.Note", "auk.tp.Bond", "auk.tp.TIPS", "auk.tp.FRN", "auk.y", "auk.y2", "auk.w", "auk.yk.inv", "auk.yk.dm", "auk.yk.real", "auk.n", "auk.leg", "auk.note", "auk.not"];
  const PROV = /TreasuryDirect|Treasury Direct|Fiscal ?Data|fiscaldata|Bloomberg|Reuters|EODHD|FMP/i;
  const FOREIGN = {pl: /zagranicz/i, en: /foreign/i, de: /ausländ/i, es: /extranjer/i, fr: /étranger/i, it: /ester/i, pt: /estrangeir/i, ru: /иностран/i, zh: /海外|外国/, ja: /海外|外国/};
  const INDIRECT = {pl: /pośredni/i, en: /indirect/i, de: /indirekt/i, es: /indirect/i, fr: /indirect/i, it: /indirett/i, pt: /indiret/i, ru: /непрям/i, zh: /间接/, ja: /間接/};
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const tt = v96src.tFor(L);
    assert.ok(v96src.I18N[L] && KEYS.every(k => typeof v96src.I18N[L][k] === 'string' && v96src.I18N[L][k].trim()), 'wszystkie klucze: ' + L);
    for (const k of KEYS) assert.ok(!PROV.test(v96src.I18N[L][k]), 'dostawca: ' + L + ' ' + k);
    for (const [k, ph] of [['auk.k.abovev', ['{n}', '{m}']], ['auk.k.aboven', ['{k}', '{m}']], ['auk.med', ['{v}']], ['auk.y', ['{n}']], ['auk.y2', ['{n}']], ['auk.w', ['{n}']], ['auk.n', ['{n}']]])
      for (const p of ph) assert.ok(v96src.I18N[L][k].includes(p), 'symbol ' + p + ' w ' + L + ' ' + k);
    const u = tt('auk.k.abovev', {n: '7', m: '12'}); assert.ok(u.includes('7') && u.includes('12') && !u.includes('{'), L + ' ' + u);
    assert.ok(tt('auk.leg').includes('▲') && tt('auk.leg').includes('▼'), L + ' legenda');
    assert.ok(!FOREIGN[L].test(tt('auk.t')) && INDIRECT[L].test(tt('auk.t')), L + ': tytuł nazywa kupujących pośrednich, nie „zagranicznych” (tego aukcja nie mierzy): ' + tt('auk.t'));
    assert.ok(Object.keys(v96src.I18N[L]).filter(k => k.startsWith('auk.')).length === KEYS.length, L + ': te same klucze auk.* co pl');
  }
  assert.ok(v96src.tFor('pl')('auk.sub').includes('nie przepływ kapitału') && v96src.tFor('en')('auk.sub').includes('not a capital flow'), 'wynik aukcji ≠ przepływ');
  assert.ok(v96src.tFor('pl')('auk.note').includes('brak nie jest zerem') && v96src.tFor('en')('auk.note').includes('a gap is not a zero'));
  assert.ok(v96src.tFor('pl')('auk.not').includes('nie podaje krajów') && v96src.tFor('en')('auk.not').includes('does not publish countries'), '„czego nie mówią”: kupujący pośredni ≠ zagranica');
  assert.equal(v96src.tFor('pl')('auk.y2', {n: '2'}), '2 lata'); assert.equal(v96src.tFor('pl')('auk.y', {n: '7'}), '7 lat'); assert.equal(v96src.tFor('ru')('auk.y2', {n: '3'}), '3 года');
  assert.equal(html.split('<section class="panel pcard" id="g-aukcje" hidden></section>').length, 2, 'jedno miejsce sekcji');
  const u = html.indexOf('<section class="panel pcard" id="g-archiwum" hidden></section>'), x = html.indexOf('<section class="panel pcard" id="g-aukcje" hidden></section>');
  assert.ok(x > u && x < u + 600, 'zaraz po archiwum własnym (zakładka GLOBAL)');
  assert.ok(html.includes("srvJSON('aukcje')") && html.includes('/* v121 aukcje */') && html.includes('#g-aukcje .etft{min-width:0;width:100%}'), 'plik, styl');
  assert.ok(html.includes('const EXTRA114=') && html.includes('for(const l in EXTRA114)if(I18N[l])Object.assign(I18N[l],EXTRA114[l]);'), 'słownik EXTRA114 dołączony');
  assert.ok(html.includes('if(!ok&&AUK.data)return;') && html.includes("/* v121: aukcje Skarbu USA; zmiana języka = nowe etykiety */"), 'odświeżanie, zmiana języka');
  assert.equal(html.split('/* ===================== v121: AUKCJE PAPIERÓW SKARBOWYCH USA').length, 2);
  const R = v96src.render('pl', false, null), J = R.txtJakCzytac();
  assert.ok(J.includes('<span>aukcje papierów skarbowych USA (popyt)</span>') && R.JAK_ICO['aukcje papierów skarbowych USA (popyt)'] === 'us', 'Metodologia: wiersz z flagą USA');
});

/* v123: TRENDY — sygnały dzienne krypto (wiersze `d` z fam „cr”, linia `cr·p` w `bd`): widok krypto tej samej sekcji dziennej */
const trdV123 = (() => {
  const {row, line} = trdV120;
  const cr = o => row(Object.assign({fam: 'cr', sym: o.id, nx: '2026-09-26'}, o));
  const rows = [
    cr({id: 'BTC', r: 2.1, zp: 1.3, rule: 'p', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none', ik: 51, in: 105}),
    cr({id: 'ETH', r: 0.13, zp: 0.04, st: 'quiet', ik: 44, in: 90}),
    cr({id: 'SOL', date: '2026-09-24', nx: '2026-09-25', live: false, age: 2, r: 4.4, zp: 1.5, rule: 'p', dir: 1, side: 'none', str: 1, st: 'stale', vd: 'none', ik: 50, in: 104}),
    cr({id: 'DOGE', r: 3.3, zp: null, st: 'short'})];
  const ln = line({fam: 'cr', rule: 'p', k: 440, n: 912, days: 252, from: '2025-09-12', to: '2026-09-24', p: 48.2, ci: [42.1, 54.4], h1: 48.5, h2: 48, m: 10, need: 0, vd: 'none', v: 1, since: '2026-09-29'});
  const both = extra => trdV120.data(Object.assign({d: trdV120.d.concat(rows), bd: trdV120.bd.concat([ln])}, extra || {}));
  const sec = h => { const i = h.indexOf('<section class="panel pcard trd-d" id="trd-dailyc">'); return i < 0 ? '' : h.slice(i, h.indexOf('</details></section>', i) + 20); };
  const card = (h, sym) => { const i = h.indexOf('<span>' + sym + '</span>'); if (i < 0) return ''; const a = h.lastIndexOf('<div class="etfk trk">', i); return h.slice(a, h.indexOf('</div>', i) + 6); };
  const dict = l => { const o = {}; for (const m of html.matchAll(/const (EXTRA(?:8\d|9\d|1\d\d))=/g)) { const x = html.indexOf(m[0]); Object.assign(o, JSON.parse(html.slice(x + m[0].length, html.indexOf(';\n', x)))[l] || {}); } return o; };
  return {cr, rows, ln, both, sec, card, dict};
})();

test('v123: EXTRA116 — 10 języków (pl pierwszy, en drugi), te same klucze i pola, tylko trd.dc.* + trd.d.fam.cr + trd.d.m.6, nałożony po EXTRA110 i EXTRA114, literały trd.dc.* w bloku v89, bez „kupuj/sprzedawaj” i bez nazw dostawców; trd.d.m.6 bez „brak krypto”', () => {
  const a = 'const EXTRA116=', x0 = html.indexOf(a), fl = 'for(const l in EXTRA116)if(I18N[l])Object.assign(I18N[l],EXTRA116[l]);\n';
  assert.ok(x0 > html.indexOf('for(const l in EXTRA114)') && html.indexOf('for(const l in EXTRA114)') > 0 && html.indexOf(fl) > x0, 'słownik po poprzednim ostatnim (EXTRA114), linia nakładania po nim');
  assert.equal(html.split('const EXTRA116=').length, 2, 'jeden słownik EXTRA116'); assert.equal(html.split(fl).length, 2, 'jedna linia nakładania');
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA110') >= 0 && apl.indexOf('EXTRA116') > apl.indexOf('EXTRA110') && apl.indexOf('EXTRA116') > apl.indexOf('EXTRA114'), 'nałożony po EXTRA110 (nadpisuje trd.d.m.6) i po EXTRA114');
  const D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0))), L10 = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'];
  assert.deepEqual(Object.keys(D), L10, 'kolejność języków');
  const K = Object.keys(D.pl).sort(); assert.equal(K.length, 21, 'liczba kluczy');
  assert.ok(K.every(k => k.startsWith('trd.dc.') || k === 'trd.d.fam.cr' || k === 'trd.d.m.6'), 'tylko trd.dc.*, trd.d.fam.cr, trd.d.m.6: ' + K);
  const ph = s => (s.match(/\{\w+\}/g) || []).sort().join(',');
  for (const l of L10) { assert.deepEqual(Object.keys(D[l]).sort(), K, 'klucze ' + l); for (const k of K) { assert.ok(typeof D[l][k] === 'string' && D[l][k].trim().length > 0, l + ' ' + k); assert.equal(ph(D[l][k]), ph(D.pl[k]), 'pola ' + l + ' ' + k); } }
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  const lit = [...new Set([...blk.matchAll(/'(trd\.dc\.[A-Za-z0-9_.]+)'/g)].map(m => m[1]).filter(k => !/[._]$/.test(k)))];
  assert.ok(lit.length >= 15, 'literały trd.dc.* w bloku: ' + lit.length); for (const k of lit) assert.ok(D.pl[k] && D.en[k], 'brak klucza ' + k);
  for (const k of ['trd.dc.buy.sub', 'trd.dc.sell.sub', 'trd.d.fam.cr']) assert.ok(D.pl[k] && D.en[k], k + ' (klucz składany w kodzie)');
  for (const i of ['1', '2', '3', '4', '5', '6']) assert.ok(D.pl['trd.dc.m.' + i] && D.en['trd.dc.m.' + i], 'trd.dc.m.' + i);
  const bad = /kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|warto kupi|okazj|prognoz|gwarant|na pewno|pewny zysk|wzrośnie|spadnie|buy now|must buy|sure profit|will rise|will fall|guarantee|forecast/i;
  for (const l of ['pl', 'en']) for (const k of K) { if (!k.startsWith('trd.dc.') || k.startsWith('trd.dc.m.') || k === 'trd.dc.b.sub' || k === 'trd.dc.b.note') continue; assert.doesNotMatch(D[l][k], bad, `${l} ${k}: ${D[l][k]}`); }
  const prov = /binance|coinbase|coin ?metrics|defillama|sosovalue|coingecko|ishares|ssga/i; for (const l of L10) for (const k of K) assert.doesNotMatch(D[l][k], prov, `${l} ${k}`);
  assert.ok(D.pl['trd.dc.k.of'] === '{e} z {n}' && D.en['trd.dc.k.of'] === '{e} of {n}' && D.pl['trd.d.fam.cr'] === 'krypto', '„0 z 1” to wartość; rodzina „krypto”');
  assert.ok(/UTC/.test(D.pl['trd.dc.t']) && /UTC/.test(D.pl['trd.dc.nx']) && /UTC/.test(D.pl['trd.dc.why.stale']), 'doba UTC w tytule, dacie i „nieaktualne”');
  assert.ok(D.pl['trd.dc.m.3'].includes('7 dni w tygodniu') && D.pl['trd.dc.m.1'].includes('nigdy zero') && D.pl['trd.dc.m.5'].includes('Stablecoinów'), 'metoda: 7 dni, brak ≠ zero, stablecoiny bez kart');
  /* scalony słownik (wszystkie słowniki w kolejności nakładania): trd.d.m.6 ze słownika v123 — bez „brak krypto”, z odesłaniem do widoku krypto */
  for (const l of L10) assert.equal(v96src.I18N[l]['trd.d.m.6'], D[l]['trd.d.m.6'], 'scalone trd.d.m.6 = EXTRA116 (' + l + ')');
  assert.ok(!v96src.I18N.pl['trd.d.m.6'].includes('brak krypto') && v96src.I18N.pl['trd.d.m.6'].includes('Krypto ma osobną regułę w widoku krypto') && !/no crypto/i.test(v96src.I18N.en['trd.d.m.6']), 'trd.d.m.6: krypto ma osobną regułę');
  assert.ok(v96src.I18N.pl['trd.d.m.6'].includes('brak indeksów oraz rynków z opóźnioną publikacją (Brazylia, Meksyk, Tajlandia, dług Indii)'), 'reszta zdania bez zmian');
  for (const l of L10) { const tt = v96src.tFor(l); assert.ok(tt('trd.dc.t', {d: 'X'}).includes('X') && tt('trd.dc.k.of', {e: 0, n: 1}).includes('0') && tt('trd.dc.k.of', {e: 0, n: 1}).includes('1'), l); }
});

test('v123: widok global — bajt w bajt ten sam HTML z wierszami i linią krypto w pliku i bez nich (także z ikonami i słownikiem pl); linia świata z fam „cr” nie dociera do świata', () => {
  const {make} = trdV96, {data, line} = trdV120, {rows, ln, both} = trdV123;
  const DP = trdV123.dict('pl'), tp = (k, o) => (DP[k] || k).replace(/\{(\w+)\}/g, (_, n) => o && o[n] !== undefined ? o[n] : '');
  for (const [ico, tt] of [[false, undefined], [true, undefined], [false, tp]]) {
    const a = make({mode: 'trendy'}, ico, tt), b = make({mode: 'trendy'}, ico, tt); a.trdApply(data()); b.trdApply(both());
    assert.ok(a.el.innerHTML.includes('id="trd-daily"') && !b.el.innerHTML.includes('trd-dailyc') && !b.el.innerHTML.includes('trd.dc.'), 'global: bez sekcji i tekstów krypto');
    assert.equal(b.el.innerHTML, a.el.innerHTML, 'global bez zmian (ikony: ' + ico + ', słownik: ' + !!tt + ')');
  }
  /* wiersze krypto przed wierszami świata, linie cr·f / cr·fp / cr·p z przewagą między liniami świata — świat nadal bez zmian */
  const extra = [line({fam: 'cr', rule: 'f', k: 90, n: 100, days: 150, vd: 'edge'}), line({fam: 'cr', rule: 'fp', k: 90, n: 100, days: 150, vd: 'edge'}), Object.assign({}, ln, {vd: 'edge', k: 700})];
  const a = make({mode: 'trendy'}), b = make({mode: 'trendy'}); a.trdApply(data());
  b.trdApply(data({d: rows.concat(trdV120.d), bd: extra.slice(0, 2).concat(trdV120.bd.slice(0, 3), extra.slice(2), trdV120.bd.slice(3))}));
  assert.equal(b.el.innerHTML, a.el.innerHTML, 'kolejność i linie krypto bez wpływu na świat');
  assert.equal((a.el.innerHTML.slice(a.el.innerHTML.indexOf('id="trd-dbd"'), a.el.innerHTML.indexOf('id="trd-dmethod"')).match(/<div class="etfk trk">/g) || []).length, 7, '7 linii świata');
});

test('v123: widok krypto — sekcja dzienna krypto nad „Tło”: kafle 1 / 0 / 3 / „0 z 1”, licznik od wdrożenia z linii krypto, BTC szara obserwacja ▲ z logo, SOL nieaktualna (doba UTC), 1 linia, metoda krypto; tygodniowe kafle krypto zostają', () => {
  const {make} = trdV96, {both, sec, card} = trdV123, st = {mode: 'trendy', trdv: 'crypto'}, f = make(st, true); f.trdApply(both()); const g = f.el.innerHTML, c = sec(g);
  const i0 = g.indexOf('id="trd-dailyc"'), iw = g.indexOf('<h2 class="trd-wk mtxt">trd.d.wk</h2>'), ik = g.indexOf('trd.kc.in'), inc = g.indexOf('trd.b.nocr');
  assert.ok(c && i0 > 0 && iw > i0 && ik > iw && inc > ik, 'sekcja krypto, potem „Tło”, kafle tygodnia krypto i nota tygodniowa: ' + [i0, iw, ik, inc]);
  assert.ok(!g.includes('id="trd-daily"') && !g.includes('trd.d.nocr') && !g.includes('trd.d.t{'), 'bez sekcji świata i bez dawnej noty');
  assert.ok(c.includes('<h2>trd.dc.t{"d":"') && c.includes('<p class="pnote">trd.dc.sub</p><p class="pnote"><b>trd.d.disc</b></p><p class="pnote trd-dlg"><i class="tdot pos"></i><i class="tdot neg"></i><i class="tdot neu"></i><i class="tdot"></i> trd.d.lg</p>'), 'tytuł z datą, podtytuł, ostrzeżenie, legenda');
  assert.ok(/<h2>trd\.dc\.t\{"d":"[^"]*25[^"]*"\}<\/h2>/.test(c), 'data tytułu = najnowsza aktualna doba krypto (25.09)');
  assert.ok(!c.includes('trd.px.') && !c.includes('trd.s.fe_') && !c.includes('<small>IVV</small>') && !c.includes('<small>EWZ</small>'), 'bez rynków świata w sekcji krypto');
  const iB = c.indexOf('trd.d.buy.t'), iS = c.indexOf('trd.d.sell.t'), iR = c.indexOf('id="trd-drestc"'), iP = c.indexOf('id="trd-dbdc"'), iM = c.indexOf('id="trd-dmethodc"');
  assert.ok(iB > 0 && iB < iS && iS < iR && iR < iP && iP < iM, 'kolejność: kupno, sprzedaż, bez sygnału, skuteczność, metoda: ' + [iB, iS, iR, iP, iM]);
  assert.ok(c.includes('<h3 class="mtxt"><i class="tg pos">▲</i><b>trd.d.buy.t</b></h3><p class="pnote">trd.dc.buy.sub</p><div class="etfkpis">') && c.includes('<h3 class="mtxt"><i class="tg neg">▼</i><b>trd.d.sell.t</b></h3><p class="pnote">trd.dc.sell.sub</p><p class="pnote">trd.d.empty</p>'), 'listy: podtytuły krypto, pusta strona sprzedaży = zdanie');
  /* kafle — tylko wiersze krypto */
  assert.ok(c.includes('trd.d.k.buy</span></div><div class="k-val">1</div><small class="mtxt">BTC</small>') && c.includes('trd.d.k.sell</span></div><div class="k-val">0</div><small class="mtxt">trd.d.k.empty</small>'), 'kafle stron: 1 (BTC, szary) / 0');
  assert.ok(c.includes('trd.d.k.none</span></div><div class="k-val">3</div><small class="mtxt">trd.d.k.nline{"q":1,"x":0,"s":1,"o":1}</small>'), 'bez sygnału: 3 (spokojny, nieaktualny, za mało historii)');
  assert.ok(c.includes('trd.d.k.rules</span></div><div class="k-val">trd.dc.k.of{"e":0,"n":1}</div>'), 'kafel reguł: „0 z 1”');
  const oos = /trd\.d\.k\.oos0\{"d":"([^"]*)"\}/.exec(c); assert.ok(oos && /29/.test(oos[1]) && !/28/.test(oos[1]), 'od wdrożenia — data z linii krypto (29.09), nie dsince świata (28.09): ' + (oos && oos[1]));
  assert.ok(c.includes('<p class="pnote">trd.dc.none.all</p><h3 class="mtxt"><i class="tg pos">▲</i>'), 'zdanie „reguła krypto bez przewagi” przed listami');
  /* karty */
  const buy = c.slice(iB, iS), rest = c.slice(iR, iP), btc = card(buy, 'BTC');
  assert.ok(btc.includes('<b class="na">▲ ●○○<i class="sr">trd.d.s{&quot;s&quot;:1}</i><small>trd.d.st.obs.up</small></b>') && btc.includes('img/krypto/btc.svg'), 'BTC: szara obserwacja ▲, 1 kropka, logo monety: ' + btc);
  assert.ok(btc.includes('trd.d.r.p.up{"w":"trd.d.pw1","p":"+2.10%"}') && !btc.includes('trd.d.r.f.') && btc.includes('trd.dc.nx{"d":"') && !btc.includes('trd.d.nx{'), 'BTC: ruch ceny, bez zdania o przepływie, data doby UTC: ' + btc);
  assert.ok(btc.includes('trd.d.ev{"rule":"trd.d.r.p","fam":"trd.d.fam.cr","p":"48.2","k":440,"n":912,"days":252,"lo":"42.1","hi":"54.4"}') && btc.includes('<i class="tg">trd.d.v.none</i>') && btc.includes('trd.d.own{"k":51,"n":105}'), 'BTC: skuteczność linii cr·p, odznaka „brak przewagi”, własne k/n: ' + btc);
  assert.ok(rest.includes('<summary>trd.d.none.t{"n":3}</summary>'), 'Bez sygnału dziś (3)');
  const pos = ['ETH', 'SOL', 'DOGE'].map(s => rest.indexOf(card(rest, s))); assert.ok(pos.every(p => p >= 0) && pos[0] < pos[1] && pos[1] < pos[2], 'kolejność quiet, stale, short: ' + pos);
  const sol = card(rest, 'SOL'); assert.ok(sol.includes('<b class="na">•<small>trd.d.st.stale</small></b>') && sol.includes('<br>trd.dc.why.stale{"d":"') && !sol.includes('trd.d.why.stale') && !buy.includes('<span>SOL</span>'), 'SOL: nieaktualna (minęła doba UTC), tylko w „Bez sygnału”: ' + sol);
  assert.ok(card(rest, 'ETH').includes('trd.d.r.p.q (+0.13%)') && card(rest, 'ETH').includes('<br>trd.d.why.quiet'), 'ETH: spokojny');
  assert.ok(card(rest, 'DOGE').includes('trd.d.r.p.nz{"p":"+3.30%"}') && card(rest, 'DOGE').includes('<br>trd.d.why.short'), 'DOGE: liczba jest, porównania brak — nie „brak danych”');
  /* linia i metoda */
  const pool = c.slice(iP, iM); assert.equal((pool.match(/<div class="etfk trk">/g) || []).length, 1, 'jedna linia krypto');
  assert.ok(pool.includes('<summary>trd.dc.b.t</summary><p class="pnote">trd.dc.b.sub</p>') && pool.includes('<p class="pnote">trd.dc.b.note</p>') && pool.includes('<span>trd.d.b.name{&quot;fam&quot;:&quot;trd.d.fam.cr&quot;,&quot;rule&quot;:&quot;trd.d.r.p&quot;}</span><b>48.2%</b>'), 'linia cr·p z tekstami krypto');
  assert.ok(pool.includes('trd.b.kn{"k":440,"n":912} · trd.d.b.days{"d":252}') && pool.includes('trd.b.ci{"lo":"42.1","hi":"54.4"}<br>trd.d.b.halves{"a":"48.5","b":"48.0"} · trd.d.b.oos{"k":0,"n":0}<br><i class="tg">trd.d.v.none</i>'), 'liczby linii: 440 z 912, 252 dni, zakres, połowy, od wdrożenia, brak przewagi');
  const meth = c.slice(iM); assert.ok(meth.includes('<summary>trd.dc.m.t{"v":1}</summary>'), 'wersja reguły krypto z linii (v)');
  const P = [...meth.matchAll(/<p class="pnote">(trd\.[a-z.0-9]+)<\/p>/g)].map(m => m[1]);
  assert.deepEqual(P, ['trd.dc.m.1', 'trd.dc.m.2', 'trd.dc.m.3', 'trd.dc.m.4', 'trd.d.m.5', 'trd.dc.m.5', 'trd.dc.m.6', 'trd.d.m.7'], 'metoda: trd.dc.m.1–6 + trd.d.m.5 + trd.d.m.7');
  /* ze słownikiem pl */
  const DP = trdV123.dict('pl'), tp = (k, o) => (DP[k] || k).replace(/\{(\w+)\}/g, (_, n) => o && o[n] !== undefined ? o[n] : '');
  const f2 = make({mode: 'trendy', trdv: 'crypto'}, false, tp); f2.trdApply(both()); const p = sec(f2.el.innerHTML);
  assert.ok(p.includes('<h2>Następna doba (UTC): co mówią ceny krypto z ') && p.includes('<div class="k-val">0 z 1</div>') && p.includes('<span>krypto: ruch ceny dnia</span>') && p.includes('Jak liczymy sygnały dzienne krypto (wersja reguły 1)') && p.includes('zamknięcie ') && p.includes('(UTC) → następna doba ') && p.includes('Bez sygnału dziś (3)'), 'teksty pl: ' + p.slice(0, 300));
  assert.ok(p.includes('po takich dniach (ruch ceny dnia, krypto): 48.2% w tę stronę (440 z 912, 252 dni)'), 'skuteczność linii po polsku');
});

test('v123: widok krypto bez wierszy krypto (stary plik, brak cen krypto, same złe wiersze) — dawna nota bez zmian; `d` z samymi wierszami krypto — świat bez bloku dziennego i bez „Tło”', () => {
  const {make} = trdV96, {data} = trdV120, {rows, ln, cr, sec} = trdV123;
  const note = (c) => c.includes('<section class="panel pcard trd-d"><h2>trd.d.t{"d":"') && c.includes('<p class="pnote">trd.d.nocr{"v":"trd.v.global"}</p><p class="pnote"><b>trd.d.disc</b></p></section><h2 class="trd-wk mtxt">trd.d.wk</h2>');
  const f = make({mode: 'trendy', trdv: 'crypto'}); f.trdApply(data()); assert.ok(note(f.el.innerHTML) && !f.el.innerHTML.includes('trd-dailyc'), 'stary plik: nota jak dotąd');
  const f1 = make({mode: 'trendy', trdv: 'crypto'}); f1.trdApply(data({bd: trdV120.bd.concat([ln])})); assert.ok(note(f1.el.innerHTML) && !f1.el.innerHTML.includes('trd-dailyc'), 'linia krypto bez wierszy: nota');
  const f2 = make({mode: 'trendy', trdv: 'crypto'}); f2.trdApply(data({d: trdV120.d.concat([cr({id: 'BTC', st: 'weird'}), cr({id: 'ETH', str: 7}), cr({id: 'b c'})])})); assert.ok(note(f2.el.innerHTML), 'same złe wiersze krypto: nota');
  /* tylko wiersze krypto (świat niepoliczony) */
  const f3 = make({mode: 'trendy'}); f3.trdApply(data({d: rows, bd: [ln]})); const g3 = f3.el.innerHTML;
  assert.ok(!g3.includes('trd-daily') && !g3.includes('trd-wk') && !g3.includes('trd.d.') && g3.includes('trd.k.in') && g3.includes('id="trd-method"'), 'global: bez bloku dziennego i bez nagłówka „Tło” (jak bez `d`)');
  const f4 = make({mode: 'trendy', trdv: 'crypto'}); f4.trdApply(data({d: rows, bd: [ln]})); const g4 = f4.el.innerHTML;
  assert.ok(sec(g4) && g4.includes('<h2 class="trd-wk mtxt">trd.d.wk</h2>') && g4.includes('trd.d.k.rules</span></div><div class="k-val">trd.dc.k.of{"e":0,"n":1}</div>'), 'krypto: sekcja krypto działa bez świata');
  /* `d: []` — jak dotąd */
  const f5 = make({mode: 'trendy'}); f5.trdApply(data({d: []})); const g5 = f5.el.innerHTML;
  assert.ok(g5.includes('id="trd-daily"') && g5.includes('<h2>trd.d.t{"d":"—"}</h2>') && g5.includes('trd.d.k.empty'), 'pusta lista `d`: blok świata z zerami, jak dotąd');
  const f6 = make({mode: 'trendy', trdv: 'crypto'}); f6.trdApply(data({d: []})); assert.ok(note(f6.el.innerHTML), 'pusta lista `d`, widok krypto: nota');
  /* bez linii krypto: karty są, kafel reguł „—”, bez zdania o braku przewagi i bez bloku linii; wersja i data „—” */
  const f7 = make({mode: 'trendy', trdv: 'crypto'}); f7.trdApply(data({d: rows})); const c7 = sec(f7.el.innerHTML);
  assert.ok(c7.includes('<span>BTC</span>') && c7.includes('trd.d.k.rules</span></div><div class="k-val na">—</div>') && c7.includes('trd.d.k.oos0{"d":"—"}') && !c7.includes('trd.dc.none.all') && !c7.includes('id="trd-dbdc"') && c7.includes('<summary>trd.dc.m.t{"v":"—"}</summary>'), 'bez linii krypto: „—”, nie zero: ' + c7.slice(0, 200));
  const b7 = trdV123.card(c7, 'BTC'); assert.ok(!b7.includes('trd.d.ev{') && b7.includes('<i class="tg">trd.d.v.none</i> · trd.d.own{"k":51,"n":105}'), 'karta bez linii: bez zdania o skuteczności, odznaka z wiersza: ' + b7);
});

test('v123: linie krypto — tylko cr·p (cr·f, cr·fp, zły werdykt i duplikat pominięte, pierwszy wygrywa); wiersze krypto z regułą f/fp/x przyjmowane (faza 2); przewaga linii → kolor i „1 z 1”', () => {
  const {make} = trdV96, {data, line} = trdV120, {rows, ln, cr, sec, card} = trdV123;
  const L = [line({fam: 'cr', rule: 'f', k: 90, n: 100, days: 150, vd: 'edge'}), line({fam: 'cr', rule: 'fp', k: 90, n: 100, days: 150, vd: 'edge'}), Object.assign({}, ln, {vd: 'maybe'}), ln, Object.assign({}, ln, {k: 700, vd: 'edge'})];
  const f = make({mode: 'trendy', trdv: 'crypto'}); f.trdApply(data({d: rows.concat([cr({id: 'XRP', f: 12, cur: 'USD', fu: 12, zf: 1.4, r: -1.8, zp: -1.2, rule: 'x', st: 'x'})]), bd: trdV120.bd.concat(L)})); const c = sec(f.el.innerHTML);
  const pool = c.slice(c.indexOf('id="trd-dbdc"'), c.indexOf('id="trd-dmethodc"'));
  assert.equal((pool.match(/<div class="etfk trk">/g) || []).length, 1, 'jedna linia'); assert.ok(pool.includes('<b>48.2%</b>') && !pool.includes('trd.d.r.f&quot;') && !pool.includes('trd.d.v.edge'), 'pierwsza poprawna cr·p');
  assert.ok(c.includes('<div class="k-val">trd.dc.k.of{"e":0,"n":1}</div>') && c.includes('trd.dc.none.all'), '„0 z 1”, zdanie o braku przewagi');
  assert.ok(card(c, 'XRP').includes('<small>trd.d.st.x</small>') && card(c, 'XRP').includes('<br>trd.d.why.x') && c.includes('trd.d.k.nline{"q":1,"x":1,"s":1,"o":1}'), 'XRP (reguła x, faza 2): przyjęty, w „Bez sygnału”');
  /* linia z przewagą i wiersz „buy” — zielony kolor tylko wtedy */
  const e = Object.assign({}, ln, {k: 560, n: 912, ci: [58, 64.3], h1: 60, h2: 62, vd: 'edge'});
  const f2 = make({mode: 'trendy', trdv: 'crypto'}); f2.trdApply(data({d: [Object.assign({}, rows[0], {st: 'buy', vd: 'edge'})].concat(rows.slice(1)), bd: [e]})); const c2 = sec(f2.el.innerHTML);
  assert.ok(card(c2, 'BTC').includes('<b class="pos">▲ ●○○') && card(c2, 'BTC').includes('<i class="tg pos">trd.d.v.edge</i>') && c2.includes('<div class="k-val">trd.dc.k.of{"e":1,"n":1}</div>') && c2.includes('<div class="k-val pos">1</div>') && !c2.includes('trd.dc.none.all'), 'przewaga: zielona karta, „1 z 1”, bez zdania o braku przewagi');
});

test('v123: otwarte bloki — widok krypto zapamiętuje trd-drestc / trd-dbdc / trd-dmethodc, świat swoje; przełączanie widoków przywraca każdy zestaw', () => {
  const {make} = trdV96, {both} = trdV123, opened = [];
  const el = {innerHTML: '', q: [], querySelectorAll(sel) { assert.equal(sel, 'details[open]'); return this.q; },
    querySelector(sel) { const d = {id: sel.slice(1)}; Object.defineProperty(d, 'open', {set(v) { if (v) opened.push(d.id); }}); return this.innerHTML.includes('id="' + d.id + '"') ? d : null; }};
  const st = {mode: 'trendy'}, f = make(st, false, undefined, el); f.trdApply(both());
  const W = [{id: 'trd-drest'}, {id: 'trd-dmethod'}], C = [{id: 'trd-drestc'}, {id: 'trd-dbdc'}, {id: 'trd-dmethodc'}];
  el.q = W; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drest', 'trd-dmethod'], 'global: odświeżenie zachowuje otwarte');
  st.trdv = 'crypto'; f.renderTrendy(); assert.deepEqual(opened.splice(0), [], 'krypto: własne bloki (na start zamknięte)');
  assert.ok(el.innerHTML.includes('id="trd-drestc"') && el.innerHTML.includes('id="trd-dbdc"') && el.innerHTML.includes('id="trd-dmethodc"') && !el.innerHTML.includes('id="trd-drest"') && !el.innerHTML.includes('id="trd-dmethod"'), 'krypto: własne id bloków');
  el.q = C; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drestc', 'trd-dbdc', 'trd-dmethodc'], 'krypto: odświeżenie zachowuje otwarte');
  st.trdv = 'global'; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drest', 'trd-dmethod'], 'powrót do global — bloki świata otwarte');
  el.q = W; st.trdv = 'crypto'; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drestc', 'trd-dbdc', 'trd-dmethodc'], 'powrót do krypto — bloki krypto otwarte');
});

test('v123: kod strony — TRD_DRULESC = [cr·p], trdDRow przyjmuje fam „cr”, trdDailyC przed trdDaily i renderTrendy, hak renderTrendy bez zmian, świat odfiltrowuje wiersze krypto', () => {
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  assert.ok(blk.includes("const TRD_DRULESC=[['cr','p']];") && blk.indexOf("const TRD_DRULESC=") < blk.indexOf("const TRD_DFAM=['eq','bd','pm'],"), 'stała linii krypto');
  assert.ok(blk.includes("if(!(TRD_DFAM.includes(r.fam)||r.fam==='cr')||!TRD_DRL.includes(r.rule)"), 'trdDRow: rodzina krypto');
  const iC = blk.indexOf('function trdDailyC(D){'), iD = blk.indexOf('function trdDaily(D,cr){'), iR = blk.indexOf('function renderTrendy(){');
  assert.ok(iC > 0 && iC < iD && iD < iR, 'trdDailyC przed trdDaily i renderTrendy');
  assert.ok(blk.includes("if(!cr&&D.d.length&&D.d.every(r=>r&&r.fam==='cr'))return '';") && blk.includes("const R=D.d.map(trdDRow).filter(r=>r&&r.fam!=='cr');") && blk.includes('if(cr)return trdDailyC(D)||`<section class="panel pcard trd-d"><h2>'), 'trdDaily: świat bez krypto, krypto — sekcja albo nota');
  assert.ok(html.includes("const dly=trdDaily(D,cr);w.innerHTML=head+dly+(dly?`<h2 class=\"trd-wk mtxt\">${t('trd.d.wk')}</h2>`:'')+disc+(!cr?"), 'hak renderTrendy bez zmian');
  assert.equal(blk.split('function trdDailyC(').length, 2, 'jedna funkcja trdDailyC');
});

test('v123.1: TRENDY krypto — tytuł i podtytuł o następnej dobie w 10 językach (EXTRA117)', () => {
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA117') > apl.indexOf('EXTRA80') && apl.indexOf('EXTRA80') >= 0, 'EXTRA117 po EXTRA80');
  const en = v96src.tFor('en')('trd.h1c');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const t = v96src.tFor(L);
    assert.ok(t('trd.subc') !== 'trd.subc' && t('trd.subc').includes('10') && t('trd.h1c').length > 4, L);
    if (L !== 'en') assert.notEqual(t('trd.h1c'), en, L + ' ma własny tytuł (nie angielski zapas)');
    assert.ok(!/kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|buy now|guarantee|forecast/i.test(t('trd.h1c') + t('trd.subc')), L);
  }
  assert.equal(v96src.tFor('pl')('trd.h1c'), 'Krypto: następna doba i ostatni tydzień');
});

// v124: historia krypto — cm.json trzyma do 400 dni, krypto.stabh.dd do 400 punktów; strona pokazuje dokładnie to samo co wcześniej
test('v124: cm.json z 400 dniami historii — panel i tabela identyczne jak przy 35 dniach (tabela = 14 najnowszych dni, nie 400)', () => {
  const m = cmMake();
  const day = i => new Date(Date.parse('2026-09-23T00:00:00Z') - i * 864e5).toISOString().slice(0, 10);
  const row = i => [day(i), 10 + i, 12, -2 - i, 1000 + i, 1200, -200 - i, 900 + i, 90000 + i];
  const D35 = cmSample(), D400 = cmSample();
  D35.assets.btc.d = Array.from({ length: 35 }, (_, k) => row(34 - k));
  D400.assets.btc.d = Array.from({ length: 400 }, (_, k) => row(399 - k));
  Object.assign(D400, { keep: 400, fetch: 'backfill', bf: '2026-09-24T20:40:00+00:00' });
  D400.assets.btc.h = { from: day(399), to: day(0), len: 400, n: 400, new: 400 };
  assert.equal(m.api.cmPanel(D400), m.api.cmPanel(D35), 'dłuższa historia i nowe pola nie zmieniają panelu');
  const tab = m.api.cmTable(D400);
  assert.equal((tab.match(/<tr>/g) || []).length, 15, 'nagłówek + 14 dni');
  assert.ok(tab.includes(day(0)) && tab.includes(day(13)) && !tab.includes(day(14)) && !tab.includes(day(399)), '14 najnowszych dni');
  D400.assets.btc.missing = 1;   // zbieracz liczy missing z ostatnich 35 dni — strona pisze „w ostatnich 35 dniach”
  assert.ok(m.api.cmPanel(D400).includes('cm.missing:{"n":"1"}'));
});

test('v124: krypto.stabh.dd do 400 punktów — strona nie czyta dd (panel stablecoinów bez zmian)', () => {
  const a0 = html.indexOf('function stcPanel(S,H){'), a1 = html.indexOf("ENG_OVR['coinmetrics-exchange-flows']=el=>", a0);
  assert.ok(a0 > 0 && a1 > a0);
  const T = (k, o) => k + (o ? JSON.stringify(o) : '');
  const KR = { data: { at: '2026-09-26T10:00:00+00:00' } };
  const f = new Function('t', 'gfmt', 'engDate', 'instRow', 'instFoot', 'engNum', 'escH', 'KR', 'krData', 'krStabh', 'ENG_OVR', html.slice(a0, a1) + '\nreturn {stcPanel};')(
    T, v => v.toFixed(2) + ' mld', s => String(s), (a, b, c, d) => `[${a}|${b}|${d}]`, s => s, v => String(v), s => String(s), KR, () => KR.data, () => null, {});
  const H = { asof: '2026-09-26', cur: 311e9, d: { '7': 1.47e9, '30': 2.46e9 }, pct: { '7': 0.5, '30': 0.8 } };
  const dd = n => Array.from({ length: n }, (_, i) => [new Date(Date.parse('2026-09-26T00:00:00Z') - (n - 1 - i) * 864e5).toISOString().slice(0, 10), 3e11 + i]);
  const S = { asof: '2026-09-26', n: 2, total: [313e9, 1e8, 2e9, 3.6e9], rows: [['Ethereum', 147.6e9, 0, -0.19e9, -0.19e9]] };
  assert.equal(f.stcPanel(S, Object.assign({ dd: dd(400) }, H)), f.stcPanel(S, Object.assign({ dd: dd(71) }, H)));
  const s0 = html.indexOf('<script>'), s1 = html.lastIndexOf('</script>'), js = html.slice(s0, s1);
  assert.ok(!/[\w$\])]\.dd\b(?![-\w])/.test(js) && !/\[['"]dd['"]\]/.test(js), 'skrypt strony nie czyta pola dd');
});

test('v124: trd.dc.m.6 — „za krótka historia” już tylko dla funduszy ETF; przepływy na giełdy i podaż stablecoinów mają historię do 400 dni (10 języków)', () => {
  const a = 'const EXTRA116=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  const L10 = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'];
  const old = /nierosn|non-growing|nicht wachsend|que no crece|ne s’allonge pas|che non cresce|que não cresce|не растущ|不会增长|伸びていきません/;
  for (const l of L10) {
    const s = D[l]['trd.dc.m.6'];
    assert.ok(typeof s === 'string' && s.includes('ETF') && s.includes('400') && !/\{\w+\}/.test(s), l + ': ETF, 400 dni, bez pól');
    assert.doesNotMatch(s, old, l + ': bez „nierosnącej historii”');
  }
  const pl = D.pl['trd.dc.m.6'], en = D.en['trd.dc.m.6'];
  assert.ok(pl.includes('Przepływy do funduszy ETF na krypto mają w plikach strony za krótką historię dzienną.'), 'pl: krótka historia tylko ETF');
  assert.ok(pl.includes('Przepływy na giełdy i zmiana podaży stablecoinów mają już długą historię dzienną (do 400 dni)') && pl.includes('z własnym licznikiem „od wdrożenia”'), 'pl: giełdy i stablecoiny — długa historia, nowa wersja reguły');
  assert.ok(en.includes('Flows into crypto ETFs have too short a daily history') && en.includes('now have a long daily history (up to 400 days)') && en.includes('its own “since going live” counter'), 'en');
  for (const l of L10) assert.equal(v96src.I18N[l]['trd.dc.m.6'], D[l]['trd.dc.m.6'], 'scalony słownik = EXTRA116 (' + l + ')');
});

test('v124: widok „Trendy krypto” nie mówi już, że historia przepływów na giełdy i podaży stablecoinów jest krótka — trd.b.nocr i trd.discc (EXTRA92: pl, en; 8 języków bierze en)', () => {
  const a = 'const EXTRA92=', x0 = html.indexOf(a), D = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  assert.deepEqual(Object.keys(D), ['pl', 'en'], 'słownik jak przed v124: tylko pl i en');
  const L10 = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'];
  const oldClaim = /nie mamy jeszcze dość długiej historii|Historia danych krypto jest jeszcze krótka|do not yet have a long enough data history|crypto data history is still short/;
  for (const l of L10) for (const k in v96src.I18N[l]) assert.doesNotMatch(String(v96src.I18N[l][k]), oldClaim, l + ' ' + k + ': bez dawnego „historia krypto za krótka”');
  for (const l of L10) {
    const tt = v96src.tFor(l);
    for (const k of ['trd.b.nocr', 'trd.discc', 'trd.dc.m.6']) {
      const s = tt(k);
      assert.ok(s !== k && s.includes('400') && s.includes('ETF') && !/\{\w+\}/.test(s), l + ' ' + k + ': 400 dni, ETF, bez pól {…}');
    }
    if (l !== 'pl' && l !== 'en') for (const k of ['trd.b.nocr', 'trd.discc']) assert.equal(tt(k), D.en[k], l + ' ' + k + ': tekst en, jak przed v124');
  }
  const nb = D.pl['trd.b.nocr'], ne = D.en['trd.b.nocr'], cp = D.pl['trd.discc'], ce = D.en['trd.discc'];
  assert.ok(nb.includes('Przepływy na giełdy i podaż stablecoinów mają już historię dzienną do 400 dni') && nb.includes('dla krypto jeszcze nie dodaliśmy')
    && nb.includes('przepływy do funduszy ETF na krypto mają za krótką historię') && nb.endsWith('Wyniki dla świata są w widoku „Trendy global”.'), 'pl trd.b.nocr: ' + nb);
  assert.ok(ne.includes('Flows to exchanges and stablecoin supply now have up to 400 days of daily history') && ne.includes('we have not yet added the check')
    && ne.includes('flows into crypto ETFs still have too short a history') && ne.endsWith('Results for the world are in the “Global trends” view.'), 'en trd.b.nocr: ' + ne);
  assert.ok(cp.startsWith('Tu widać, co już się stało:') && cp.includes('ani rekomendacja kupna lub sprzedaży, ani porada inwestycyjna, ani prognoza.')
    && cp.includes('mają już historię dzienną do 400 dni, ale tego sprawdzenia dla krypto jeszcze nie dodaliśmy') && cp.includes('funduszy ETF na krypto mają za krótką historię'), 'pl trd.discc: ' + cp);
  assert.ok(ce.startsWith('This shows what has already happened:') && ce.includes('It is not a recommendation to buy or sell, not investment advice and not a forecast.')
    && ce.includes('we have not yet added that check for crypto') && ce.includes('crypto ETFs still have too short a history'), 'en trd.discc: ' + ce);
});

test('v124: sieć Bitcoin — pomocnicze: historia po datach, średnia 7 dób bez dziur, zmiana 30 dni, średnia krocząca, liczby, wiek części', () => {
  const k0 = html.indexOf('/* ===================== v124: SIEĆ BITCOIN'), k1 = html.indexOf('\nfunction lnTile(', k0);
  assert.ok(k0 > 0 && k1 > k0, 'blok v124 w stronie');
  const T = (k, v) => k + (v ? JSON.stringify(v) : '');
  const K = new Function('t', 'nfmt', 'fPct', 'escH', 'LOCALE', 'LANG', 'engDate', 'gAgeNote', html.slice(k0, k1) + '\nreturn {LN, lnPart, lnAgo, lnWhen, lnDay, lnDayLag, lnHist, lnAvg, lnMa7, lnChg30, lnFee, lnEh, lnPct};')(
    T, (v, d) => Number(v).toFixed(d), (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%', v96src.escH, {pl: 'pl-PL'}, 'pl', s => '[' + s + ']', d => ' · age(' + String(d).slice(0, 10) + ')');
  const day = i => new Date(Date.UTC(2026, 8, 25) - i * 864e5).toISOString().slice(0, 10);   // 2026-09-25 minus i dób
  const full = []; for (let i = 44; i >= 0; i--) full.push([day(i), 100 + (44 - i)]);
  const gap = full.filter(r => r[0] !== day(33));   // brak doby 33 dni przed ostatnią
  const r = K.lnHist(gap.concat([['zła', 5], [day(50), 0], [day(51), -3], [day(52), 'x'], 'tekst']));
  assert.equal(r.length, 44, 'złe wiersze odrzucone'); assert.equal(r[0][0], day(44)); assert.equal(r[r.length - 1][0], '2026-09-25');
  assert.equal(K.lnHist([[day(1), 5], [day(0), 7], [day(1), 6]]).map(x => x.join(':')).join(','), day(1) + ':6,' + day(0) + ':7', 'powtórzona doba — ostatnia wartość, rosnąco');
  assert.equal(K.lnDay('2026-03-01', -1), '2026-02-28'); assert.equal(K.lnDay('x', -1), '');
  const today = new Date().toISOString().slice(0, 10);
  assert.equal(K.lnDayLag(today), 0); assert.equal(K.lnDayLag(K.lnDay(today, -2)), 2, 'doba 2 dni przed dziś (UTC)'); assert.equal(K.lnDayLag(K.lnDay(today, 1)), -1);
  assert.equal(K.lnDayLag('x'), null); assert.equal(K.lnDayLag(null), null); assert.equal(K.lnDayLag(undefined), null); assert.equal(K.lnDayLag(today + 'T10:00'), null, 'tylko sama doba RRRR-MM-DD');
  assert.equal(K.lnDayLag('2026-09-24', '2026-09-25T17:02:00+00:00'), 1, 'od doby UTC chwili pobrania, nie od dziś'); assert.equal(K.lnDayLag('2026-09-24', '2026-09-27T00:30:00Z'), 3);
  assert.equal(K.lnDayLag('2026-09-24', '2026-09-25T23:30:00-02:00'), 2, 'doba UTC chwili (strefa w czasie przeliczona)');
  assert.equal(K.lnDayLag('2026-09-24', 'x'), null); assert.equal(K.lnDayLag('2026-09-24', null), null, 'zły czas odniesienia = brak'); assert.equal(K.lnDayLag('x', '2026-09-25T17:02:00Z'), null);
  assert.equal(K.lnAvg(full, '2026-09-25', 7), 141, 'średnia 7 dób: 144…138'); assert.equal(K.lnAvg(gap, day(30), 7), null, 'dziura w oknie = brak, nie średnia z dziurą');
  const c = K.lnChg30(full); assert.ok(c && Math.abs(c.p - (141 / 111 - 1) * 100) < 1e-9 && c.b0 === day(30), '30 dni: średnia 7 dób wobec 7 dób sprzed 30 dni');
  assert.equal(K.lnChg30(gap), null, 'brak doby w oknie porównania = „—”'); assert.equal(K.lnChg30([]), null); assert.equal(K.lnChg30(null), null);
  assert.equal(K.lnMa7(full).length, 39, 'średnia krocząca tylko dla dób z kompletem 7'); assert.equal(K.lnMa7(gap).length, 32, 'luka wyłącza 7 średnich');
  assert.equal(K.lnMa7(full)[0][0], day(38)); assert.equal(K.lnMa7(full)[0][1], (106 + 105 + 104 + 103 + 102 + 101 + 100) / 7);
  assert.equal(K.lnFee(1.641), '1.64'); assert.equal(K.lnFee(0.2), '0.20'); assert.equal(K.lnFee(12.34), '12.3'); assert.equal(K.lnFee(150), '150'); assert.equal(K.lnFee(2, false), '2', 'opłaty zaokrąglone przez źródło — bez miejsc');
  assert.equal(K.lnFee(null), '—'); assert.equal(K.lnFee(0), '—', 'zero opłaty = brak, nie „0”');
  assert.equal(K.lnEh(939.2), '939'); assert.equal(K.lnEh(88.24), '88.2'); assert.equal(K.lnEh(0), '—'); assert.equal(K.lnPct(-2.4163, 1), '−2.4%'); assert.equal(K.lnPct(null, 1), '—');
  const ago = m => new Date(Date.now() - m * 60e3).toISOString();
  assert.equal(K.lnAgo(ago(5)), ' · ln.ago.m{"n":5}'); assert.equal(K.lnAgo(ago(185)), ' · ln.ago.h{"n":3}'); assert.equal(K.lnAgo(ago(3 * 1440 + 5)), ' · ln.ago.d{"n":3}');
  assert.equal(K.lnAgo(ago(-10)), ' · ln.ago.now', 'czas bloku z przyszłości (zegar górnika) = „przed chwilą”'); assert.equal(K.lnAgo('x'), ''); assert.equal(K.lnWhen(''), '');
  assert.ok(K.lnWhen(ago(5)).startsWith('[') && K.lnWhen(ago(5)).endsWith(' · ln.ago.m{"n":5}'), 'czas i wiek');
  const D = {fees: {fast: 1, at: ago(10)}, mempool: {count: 1, at: ago(49 * 60)}, tip: 'x', check: {height: 1}};
  assert.ok(K.lnPart(D, 'fees') === D.fees && K.lnPart(D, 'mempool') === null && K.lnPart(D, 'tip') === null && K.lnPart(D, 'check') === null && K.lnPart(null, 'fees') === null,
    'część starsza niż 48 h, bez czasu albo nie obiekt = brak');
});
test('v124: sieć Bitcoin — panel z pliku: 7 kafli z czasem i wiekiem, dopisek przy nieudanym pobraniu, brak = „—” z powodem, porównanie eksploratorów, wykres doby i średniej 7 dób, bez nazw dostawców', () => {
  const k0 = html.indexOf('/* ===================== v124: SIEĆ BITCOIN'), k1 = html.indexOf('\nfunction lnApply(', k0);
  assert.ok(k0 > 0 && k1 > k0);
  const T = (k, v) => k + (v ? JSON.stringify(v) : '');
  const run = (D, ok) => {
    const el = {innerHTML: '', hidden: true, querySelectorAll: () => [], querySelector: () => null};
    const r = new Function('$', 't', 'nfmt', 'fPct', 'escH', 'LOCALE', 'LANG', 'engDate', 'gAgeNote', 'icoWrap', 'coinImg', 'glyphImg', 'D',
      html.slice(k0, k1) + (ok ? '\nreturn lnOk(D);' : '\nLN.data=D;renderLn();return null;'))(
      q => q === '#c-lancuch' ? el : null, T, (v, d) => Number(v).toFixed(d), (v, d) => (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v).toFixed(d) + '%', v96src.escH, {pl: 'pl-PL'}, 'pl',
      s => '[' + String(s) + ']', d => ' · age(' + String(d).slice(0, 10) + ')', x => `<span class="icos">${x}</span>`, (s, c) => `<i class="ico ${c}">${s}</i>`, (n, c) => `<i class="gl ${c}">${n}</i>`, D);
    return ok ? r : el;
  };
  const now = Date.now(), iso = m => new Date(now - m * 60e3).toISOString(), dd = i => new Date(now - i * 864e5).toISOString().slice(0, 10);
  const hist = []; for (let i = 60; i >= 1; i--) hist.push([dd(i), 900 + (i % 5)]);
  const base = () => ({at: iso(5), ok: {fees: true, mempool: true, difficulty: true, tip: true, hashrate: true, hist: true, check: true},
    fees: {fast: 1.641, half_hour: 1.006, hour: 0.532, economy: 0.2, minimum: 0.1, prec: true, at: iso(5)},
    mempool: {count: 72910, vsize: 40383203, total_fee: 6343662, at: iso(5)},
    difficulty: {progress: 52.38, change_est: -2.42, remaining_blocks: 960, eta: '2026-10-03T15:47:50+00:00', prev_change: 4.16, next_height: 969696, block_min: 10.26, at: iso(5)},
    tip: {height: 968736, time: iso(9), tx_count: 6514, at: iso(5)},
    hashrate: {current: 939.2, avg_3d: 883.3, day: dd(1), hist, hist_at: iso(300), at: iso(5)},
    check: {height: 968736, count: 67394, vsize: 39204062, at: iso(4)}});
  const el = run(base()), out = el.innerHTML;
  assert.ok(!el.hidden && out.includes('ln.t') && out.includes('ln.sub') && out.includes('class="live on"') && out.includes('<i class="ico sm">BTC</i>'), 'nagłówek, logo monety, plik młody');
  assert.equal((out.match(/<div class="etfk">/g) || []).length, 7, 'siedem kafli');
  assert.ok(out.includes('1.64 sat/vB') && out.includes('ln.k.fee.tx{"s":"231","n":141}'), 'opłata na następny blok i ≈ sat za typowy przelew');
  assert.ok(out.includes('0.20 sat/vB') && out.includes('ln.k.eco.l{"a":"1.01","b":"0.53","c":"0.10"}'), 'opłata oszczędna z drabinką');
  assert.ok(out.includes('>72910<small>') && out.includes('ln.k.mp.vb{"v":"40.4","n":"41"}') && out.includes('ln.k.mp.fee{"v":"0.063"}'), 'kolejka: liczba, rozmiar ≈ bloki, opłaty w BTC');
  assert.ok(out.includes('>968736<small>') && out.includes('ln.k.tip.tx{"n":"6514"}') && out.includes('ln.k.tip.at{"t":"[') && out.includes('ln.ago.m{\\"n\\":9}'), 'ostatni blok z czasem bloku i wiekiem');
  assert.ok(out.includes('939 EH/s') && out.includes('ln.k.hr30{"p":"') && !out.includes('ln.k.hr30.na') && out.includes('ln.k.hr3{"v":"883"}'), 'moc: bieżąca, 30 dni, 3 doby');
  assert.ok(out.includes('>−2.4%<small>') && out.includes('ln.k.diff.left{"n":"960","d":"') && out.includes('ln.k.diff.prog{"p":"52"}') && out.includes('ln.k.diff.prev{"p":"+4.2%"}') && out.includes('ln.k.diff.bt{"m":"10.3"}'), 'trudność');
  assert.ok(out.includes('>ln.k.chk.same<small>') && out.includes('ln.k.chk.h{"h":"968736"}') && out.includes('ln.k.chk.mp{"n":"67394"} (ln.k.chk.mpd{"p":"−7.6%"})'), 'drugi eksplorator: ten sam blok, kolejka i różnica');
  assert.equal((out.match(/<small class="mtxt">\[/g) || []).length, 6, 'sześć kafli z czasem pobrania części'); assert.ok(!out.includes('ln.stale') && !out.includes('ln.na'));
  assert.ok(out.includes('<svg class="arc-svg"') && (out.match(/<polyline class="arc-l l1"/g) || []).length === 1 && (out.match(/<polyline class="arc-l l2"/g) || []).length === 1, 'wykres: doba i średnia 7 dób');
  assert.ok(out.includes('ln.h.hist') && out.includes('ln.leg.day') && out.includes('ln.leg.ma') && out.includes('ln.hist.note{"d":') && out.includes(' · age(' + dd(1) + ')'), 'wykres z legendą, datą i wiekiem ostatniej doby');
  assert.ok(out.includes('ln.note') && out.includes('ln.not1') && out.includes('ln.not3') && out.includes('eng.notsays') && out.includes('ln.foot') && out.includes('eng.disclaimer'), 'nota, „czego nie mówi”, stopka');
  assert.ok(!/mempool\.space|blockstream|esplora|blockchain\.com|blockchair/i.test(out), 'bez nazw dostawców w panelu'); assert.ok(!/NaN|undefined|Infinity/.test(out), 'bez NaN');
  const st = base(); st.ok.fees = false; const o2 = run(st).innerHTML;
  assert.equal((o2.match(/<small class="ln-st">ln\.stale<\/small>/g) || []).length, 2, 'nieudane pobranie opłat — dopisek w obu kaflach opłat');
  const old = base(); old.fees.at = iso(49 * 60); old.check = null; const o3 = run(old).innerHTML;
  assert.equal((o3.match(/<b class="na">—<\/b><small class="mtxt">ln\.na<\/small>/g) || []).length, 3, 'opłaty starsze niż 48 h i brak drugiego eksploratora = „—” z powodem');
  const ah = base(); ah.check.height = 968737; assert.ok(run(ah).innerHTML.includes('ln.k.chk.dh{"n":"+1"}'), 'różnica wysokości');
  const far = base(); far.check.at = iso(125); const o4 = run(far).innerHTML;
  assert.ok(o4.includes('>968736<small>ln.k.chk.mp{"n":"67394"}</small>') && !o4.includes('ln.k.chk.h{'), 'pobrania z różnych przebiegów — bez porównania, sama wysokość');
  const rnd = base(); rnd.fees = {fast: 2, half_hour: 1, hour: 1, economy: 1, minimum: 1, prec: false, at: iso(5)}; const o5 = run(rnd).innerHTML;
  assert.ok(o5.includes('2 sat/vB') && o5.includes('ln.prec') && o5.includes('ln.k.eco.l{"a":"1","b":"1","c":"1"}'), 'opłaty zaokrąglone przez źródło — oznaczone');
  const nh = base(); nh.hashrate.hist = hist.slice(-20); const o6 = run(nh).innerHTML; assert.ok(o6.includes('ln.k.hr30.na'), 'za krótka historia — 30 dni „—”');
  const sh = base(); sh.hashrate.hist = hist.slice(0, 30); assert.ok(!run(sh).innerHTML.includes('<svg'), 'historia zatrzymana ponad 14 dni temu — bez wykresu');
  // przegląd v124 (1): liczby dobowe (30 dni, 3 doby) z datą ostatniej doby; doba starsza niż 2 dni przed dobą pobrania części = „—” z powodem,
  // moc bieżąca zostaje (doby liczone od doby UTC czasu części — bez zależności od godziny przebiegu testu)
  const sh1 = (d, k) => new Date(Date.parse(d + 'T00:00:00Z') + k * 864e5).toISOString().slice(0, 10), upTo = (h, d) => h.filter(x => x[0] <= d);
  const aD = iso(5).slice(0, 10);   // doba UTC pobrania części w base()
  assert.ok(out.includes('ln.k.hr3{"v":"883"}</small><small>ln.k.hr.d{"d":"'), 'liczby dobowe z datą swojej ostatniej doby');
  const sd = base(); sd.hashrate.day = sh1(aD, -3); sd.hashrate.hist = upTo(hist, sd.hashrate.day); const o7 = run(sd).innerHTML;
  assert.ok(o7.includes('939 EH/s<small>ln.k.hr.old{"d":"') && !o7.includes('ln.k.hr30{') && !o7.includes('ln.k.hr3{') && !o7.includes('ln.k.hr.d{'), 'historia stoi 3 dni — 30 dni i 3 doby „—” z powodem i datą doby');
  assert.ok(!o7.includes('ln.na') && o7.includes('<svg class="arc-svg"'), 'kafel i wykres (z datą i wiekiem ostatniej doby) zostają');
  const sd2 = base(); sd2.hashrate.day = sh1(aD, -2); sd2.hashrate.hist = upTo(hist, sd2.hashrate.day); const o8 = run(sd2).innerHTML;
  assert.ok(o8.includes('ln.k.hr30{"p":"') && o8.includes('ln.k.hr3{"v":"883"}') && !o8.includes('ln.k.hr.old'), 'doba 2 dni przed pobraniem = jeszcze świeża (tuż po północy)');
  const nd = base(); delete nd.hashrate.day; nd.hashrate.hist = upTo(hist, sh1(aD, -3)); assert.ok(run(nd).innerHTML.includes('ln.k.hr.old'), 'bez pola doby — ostatnia doba historii');
  // przegląd v124 (runda 2): opóźnienie doby od doby pobrania części, nie od dziś — automat stoi ok. 40 h, źródło działało (doba = „wczoraj”
  // wobec pobrania): liczby dobowe zostają z datą swojej doby, wiek pobrania pod kaflem, bez obwiniania źródła; tak samo, gdy nie wyszło pobranie mocy
  const md = Date.parse(new Date(now).toISOString().slice(0, 10) + 'T00:00:00Z') - 864e5;   // północ UTC wczoraj
  const X = new Date(Math.floor((now - 48 * 3600e3 + md) / 2)).toISOString(), xD = X.slice(0, 10);   // środek [teraz − 48 h, północ wczoraj): pobranie przedwczoraj
  const stop = back => {
    const s = base(); s.at = X; for (const k of ['fees', 'mempool', 'difficulty', 'tip', 'hashrate', 'check']) s[k].at = X;
    s.tip.time = new Date(Date.parse(X) - 4 * 60e3).toISOString(); s.hashrate.hist_at = X; s.hashrate.hist = [];
    for (let i = 61; i >= back; i--) s.hashrate.hist.push([sh1(xD, -i), 900 + (i % 5)]);
    s.hashrate.day = sh1(xD, -back); return s;
  };
  const s1 = stop(1), lagNow = Math.round((Date.parse(new Date(now).toISOString().slice(0, 10) + 'T00:00:00Z') - Date.parse(s1.hashrate.day + 'T00:00:00Z')) / 864e5);
  assert.equal(lagNow, 3, 'scenariusz przeglądu: doba 3 dni przed dziś, 1 dzień przed pobraniem'); assert.ok(now - Date.parse(X) >= 36 * 3600e3 && now - Date.parse(X) < 48 * 3600e3, 'pobranie 36–48 h temu');
  const o13 = run(s1).innerHTML;
  assert.ok(o13.includes('939 EH/s<small>ln.k.hr30{"p":"') && o13.includes('ln.k.hr3{"v":"883"}') && o13.includes('ln.k.hr.d{"d":"') && !o13.includes('ln.k.hr.old'),
    'automat stoi — liczby dobowe z datą doby, bez „źródło nie dopisuje dób”');
  assert.ok(o13.includes('class="live off"') && !o13.includes('ln.na') && !o13.includes('ln.stale') && /<small class="mtxt">\[[^\]]+\] · ln\.ago\.h\{"n":(3[6-9]|4[0-7])\}<\/small>/.test(o13), 'wiek pobrania (36–47 h) pod kaflami, plik oznaczony jako nieodświeżany');
  const s2 = stop(1); s2.ok.hashrate = false; const o14 = run(s2).innerHTML;
  assert.ok(o14.includes('ln.k.hr.d{"d":"') && o14.includes('<small class="ln-st">ln.stale</small>') && !o14.includes('ln.k.hr.old'), 'pobieranie mocy nie wychodzi — dopisek o nieudanym pobraniu, bez obwiniania źródła');
  const o15 = run(stop(3)).innerHTML;
  assert.ok(o15.includes('939 EH/s<small>ln.k.hr.old{"d":"') && !o15.includes('ln.k.hr.d{'), 'doba 3 dni przed samym pobraniem — źródło nie dopisywało wtedy dób (powód uzasadniony danymi)');
  // przegląd v124 (2): moc bieżąca 0 u źródła — „—” z własnym powodem, liczby dobowe zostają; poprzednia liczba z własnym czasem i wiekiem
  const cm = base(); cm.hashrate.current = null; cm.hashrate.cur_at = null; const o9 = run(cm).innerHTML;
  assert.equal((o9.match(/<div class="etfk">/g) || []).length, 7, 'kafel mocy zostaje');
  assert.ok(o9.includes('<b><span class="na">—</span><small>ln.k.hr.nocur</small><small>ln.k.hr30{"p":"') && o9.includes('ln.k.hr3{"v":"883"}') && o9.includes('ln.k.hr.d{'),
    'brak mocy bieżącej: „—” z powodem, 30 dni i 3 doby zostają');
  assert.ok(!o9.includes('ln.na') && !o9.includes('939 EH/s') && !/NaN|undefined/.test(o9), 'bez fałszywego powodu „brak świeżych danych” i bez zera');
  const cc = base(); cc.hashrate.cur_at = iso(180); const o10 = run(cc).innerHTML;
  assert.ok(o10.includes('939 EH/s<small>ln.k.hr.cold{"t":"[') && o10.includes('ln.ago.h{\\"n\\":3}') && o10.includes('ln.k.hr30{"p":"'), 'moc bieżąca z wcześniejszego pobrania — z własnym czasem i wiekiem');
  const cc2 = base(); cc2.hashrate.cur_at = iso(49 * 60); const o11 = run(cc2).innerHTML;
  assert.ok(o11.includes('<span class="na">—</span><small>ln.k.hr.nocur</small>') && !o11.includes('939 EH/s'), 'poprzednia moc bieżąca starsza niż 48 h = „—”');
  const cn = base(); cn.hashrate.current = null; cn.hashrate.avg_3d = null; cn.hashrate.hist = []; const o12 = run(cn).innerHTML;
  assert.equal((o12.match(/<b class="na">—<\/b><small class="mtxt">ln\.na<\/small>/g) || []).length, 1, 'ani mocy bieżącej, ani liczb dobowych = „—” z powodem ogólnym');
  const offl = base(); offl.at = iso(90); assert.ok(run(offl).innerHTML.includes('class="live off"'), 'plik starszy niż godzina = wskaźnik wyłączony');
  const Z = run(null); assert.ok(Z.hidden && Z.innerHTML === '', 'bez pliku sekcja ukryta');
  const allOld = base(); for (const k of ['fees', 'mempool', 'difficulty', 'tip', 'hashrate', 'check']) allOld[k].at = iso(3 * 1440); allOld.hashrate.hist = [];
  const E = run(allOld); assert.ok(E.hidden && E.innerHTML === '', 'wszystkie części starsze niż 48 h i bez historii = ukryta');
  assert.ok(run(base(), true) === true && run(null, true) === false && run({at: 'x', fees: {}}, true) === false && run({at: iso(1)}, true) === false && run({at: iso(1), fees: []}, true) === false, 'plik ok: czas i choć jedna część');
});
test('v124: sieć Bitcoin — słownik EXTRA119 w 10 językach (te same klucze i miejsca na wartości), bez nazw dostawców; sekcja po cenach krypto, styl, blok JS, plik, odświeżanie co 10 min', () => {
  const e0 = html.indexOf('const EXTRA119='), e1 = html.indexOf(';\nfor(const l in EXTRA119)', e0);
  assert.ok(e0 > 0 && e1 > e0 && html.includes('for(const l in EXTRA119)if(I18N[l])Object.assign(I18N[l],EXTRA119[l]);\n'), 'słownik EXTRA119 podpięty');
  const E = JSON.parse(html.slice(e0 + 'const EXTRA119='.length, e1)), KEYS = Object.keys(E.pl).sort(), PH = s => (s.match(/\{[a-z]+\}/g) || []).sort().join(',');
  assert.ok(KEYS.length >= 40 && KEYS.every(k => k.startsWith('ln.')), 'klucze ln.*');
  assert.ok(['ln.k.hr.d', 'ln.k.hr.old', 'ln.k.hr.nocur', 'ln.k.hr.cold'].every(k => KEYS.includes(k)), 'teksty przeglądu: data doby, historia stoi, brak mocy bieżącej, moc z wcześniejszego pobrania');
  assert.ok(E.pl['ln.k.hr.nocur'].includes('nie zero') && E.en['ln.k.hr.nocur'].includes('not zero'), 'brak mocy bieżącej ≠ zero');
  assert.ok(E.pl['ln.k.hr.old'].includes('przed ostatnim udanym pobraniem') && E.en['ln.k.hr.old'].includes('before the last successful fetch') && !/nie dopisuje|is not adding/.test(E.pl['ln.k.hr.old'] + E.en['ln.k.hr.old']),
    'stojące źródło — opisane w chwili ostatniego udanego pobrania, nie „teraz”');
  const PROV = /mempool\.space|blockstream|esplora|blockchain\.com|blockchair|coinmetrics|binance/i;
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    assert.equal(Object.keys(E[L]).sort().join('|'), KEYS.join('|'), L + ': klucze EXTRA119');
    const t = v96src.tFor(L);
    for (const k of KEYS) {
      assert.ok(v96src.I18N[L][k] && t(k) !== k && t(k).trim(), L + ' ' + k); assert.ok(!PROV.test(t(k)), 'dostawca: ' + L + ' ' + k);
      assert.equal(PH(E[L][k]), PH(E.pl[k]), L + ' ' + k + ': miejsca na wartości');
    }
    assert.ok(E[L]['ln.note'].includes('sat/vB') && E[L]['ln.note'].includes('EH/s') && E[L]['ln.h.hist'].includes('EH/s'), L + ': jednostki nazwane');
    assert.ok(!t('ln.k.fee.tx', {s: '231', n: 141}).includes('{'), L + ': wartości podstawione');
  }
  assert.ok(v96src.tFor('pl')('ln.sub').includes('nigdy zero') && v96src.tFor('pl')('ln.sub').includes('nie przepływ kapitału'), 'pl: brak ≠ zero, stan ≠ przepływ');
  assert.ok(v96src.tFor('en')('ln.sub').includes('never zero') && v96src.tFor('en')('ln.sub').includes('not a capital flow'), 'en: brak ≠ zero, stan ≠ przepływ');
  for (const k of ['inst.file', 'eng.notsays', 'eng.disclaimer']) assert.ok(v96src.I18N.pl[k] && v96src.I18N.en[k], 'wspólny klucz używany przez panel: ' + k);
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA119') > apl.indexOf('EXTRA117') && apl.indexOf('EXTRA117') >= 0, 'EXTRA119 po EXTRA117');
  const S = '<section class="panel pcard" id="c-lancuch" hidden></section>';
  assert.equal(html.split(S).length, 2, 'jedna sekcja');
  const a = html.indexOf('<section class="panel pcard" id="c-ceny-krypto" hidden></section>'), x = html.indexOf(S), cr = html.indexOf('id="crypto"');
  assert.ok(a > 0 && x > a && x < a + 1500 && cr > 0 && cr < x, 'CRYPTO: po cenach krypto');
  assert.ok(html.includes("function lnLoad(){srvJSON('lancuch').then(lnApply);}") && html.includes('LN.timer=setInterval(()=>{if(!document.hidden)lnLoad();},10*60*1000);')
    && html.includes("lnLoad();lnAuto();try{new MutationObserver(()=>renderLn()).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});}catch(e){}"), 'plik serwera, odświeżanie co 10 min, zmiana języka');
  assert.ok(html.includes('/* v124 sieć Bitcoin */') && html.includes('#c-lancuch .etfk b small.ln-st{color:var(--yl-tx)}') && html.includes('#c-lancuch .etfk b.na{color:var(--dim)}') && html.includes('#c-lancuch .etfk b>span.na{display:inline;font-size:inherit;line-height:inherit;font-weight:inherit;color:var(--dim)}') &&html.indexOf('/* v124 sieć Bitcoin */') < html.indexOf('/* v105 wieloryby */'), 'styl przed stylem wielorybów');
  const j0 = html.indexOf('/* ===================== v124: SIEĆ BITCOIN'), j1 = html.indexOf('\n/* ===================== v98: USA');
  assert.equal(html.split('/* ===================== v124: SIEĆ BITCOIN').length, 2, 'jeden blok JS'); assert.ok(j0 > 0 && j1 > j0, 'blok przed blokiem USA');
  const blk = html.slice(j0, html.indexOf('/* v124: sieć Bitcoin; zmiana języka', j0));
  assert.ok(!/mempool\.space|blockstream|esplora|blockchain\.com/i.test(blk), 'blok panelu bez nazw dostawców');
});

/* ===================== v124: SZWAJCARIA — depozyty banków w banku centralnym (data/snb.json), słownik EXTRA121, podpis na stronie Źródła ===================== */
const snb124 = (() => {
  const a0 = html.indexOf('/* ===================== v124: SZWAJCARIA'), a1 = html.indexOf('\nfunction snbLoad(', a0);
  assert.ok(a0 > 0 && a1 > a0, 'blok v124 na stronie');
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const mk = (o) => { o = o || {};
    return new Function('$', 't', 'nfmt', 'escH', 'gAgeNote', 'engDate', 'LOCALE', 'LANG', 'flagImg', 'glyphImg', 'icoWrap', 'renderSources', html.slice(a0, a1) +
      '\nreturn {SNB, SNB_ROWS, SNB_OKNO, SNB_MAX_AGE, snbRows, snbDiv, snbAmt, snbDelta, snbWk, snbMinMax, snbBody, renderSnb, snbApply, snbCredit, SNB_CREDIT, renderSources};')(
      o.$ || (() => null), o.t || ((k, v) => k + (v ? JSON.stringify(v) : '')), o.nfmt || ((v, d) => Number(v).toFixed(d)), esc, d => ' · age(' + d + ')', iso => 'D(' + iso + ')',
      {pl: 'pl-PL', en: 'en-US', zh: 'zh-CN'}, o.L || 'en', o.flagImg, o.glyphImg, o.icoWrap, o.renderSources); };
  /* 10 tygodni (piątki) z luką 21.08 i brakiem krajowych 4.09; rezerwy z lipca */
  const W = ['2026-07-17', '2026-07-24', '2026-07-31', '2026-08-07', '2026-08-14', '2026-08-28', '2026-09-04', '2026-09-11', '2026-09-18'];
  const hist = W.map((d, i) => [d, d === '2026-09-04' ? null : 440000 - i * 1000, 470000 - i * 1000]);
  const D = {at: new Date().toISOString(), ok: {gw: true, fx: true}, part_at: {}, week: '2026-09-18', domestic: 432000, total: 462000, other: 30000,
    d1w: 790, d4w: -9077, d1w_total: 2391, d4w_total: null, hist: [['bad', 1, 2], 'x', null, ['2026-02-30', 1, 1]].concat(hist.slice().reverse()),
    fx_res: {month: '2026-07', value: 802477.5, d1m: 16413.6, d12m: null, hist: [['2026-07', 802477.5]]}};
  return {a0, a1, mk, D, W};
})();

test('v124: Szwajcaria — pomocnicze: historia po dacie, kwota w mld (zh/ja w 億), zmiana ze strzałką bez koloru, luka = brak zmiany, najniżej/najwyżej tylko z liczb', () => {
  const X = snb124.mk(), R = X.snbRows(snb124.D);
  assert.equal(R.length, 9, 'śmieci i data niemożliwa odrzucone'); assert.equal(R[0][0], '2026-07-17'); assert.equal(R[8][0], '2026-09-18');
  assert.deepEqual(R.find(r => r[0] === '2026-09-04'), ['2026-09-04', null, 464000], 'brak krajowych = null, nie 0');
  assert.equal(X.snbDiv(), 1000, 'bez słownika — mld'); assert.equal(X.snbAmt(null), '—'); assert.equal(X.snbAmt(428033), 'snb.bn{"v":"428.0"}');
  assert.deepEqual(X.snbDelta(null, 'L'), {txt: '— L', cls: 'na'});
  assert.deepEqual(X.snbDelta(790, 'L'), {txt: '▲ +snb.bn{"v":"0.8"} L', cls: ''}, 'wzrost bez koloru');
  assert.deepEqual(X.snbDelta(-9077, ''), {txt: '▼ −snb.bn{"v":"9.1"}', cls: ''});
  assert.deepEqual(X.snbDelta(20, ''), {txt: '• snb.bn{"v":"0.0"}', cls: ''}, 'zero po zaokrągleniu — kropka, bez strzałki');
  const i11 = R.findIndex(r => r[0] === '2026-09-11'), i28 = R.findIndex(r => r[0] === '2026-08-28'), i04 = R.findIndex(r => r[0] === '2026-09-04');
  assert.equal(X.snbWk(R, i11, 2), R[i11][2] - R[i04][2], 'razem: wobec tygodnia dokładnie 7 dni wcześniej');
  assert.equal(X.snbWk(R, i11, 1), null, 'krajowe 4.09 brak — brak zmiany'); assert.equal(X.snbWk(R, i28, 1), null, 'luka 21.08 — brak zmiany, nie wobec 14.08');
  assert.equal(X.snbWk(R, i04, 1), null, 'brak liczby w tym tygodniu');
  const mm = X.snbMinMax(R, 1, 52); assert.deepEqual([mm.n, mm.min, mm.dmin, mm.max, mm.dmax], [8, 432000, '2026-09-18', 440000, '2026-07-17']);
  assert.equal(X.snbMinMax([['2026-09-18', 1, 2]], 1, 52), null, 'jedna liczba — bez zakresu');
  const Z = snb124.mk({t: (k, v) => k === 'snb.div' ? '100' : k + (v ? JSON.stringify(v) : '')});
  assert.equal(Z.snbDiv(), 100); assert.equal(Z.snbAmt(428033), 'snb.bn{"v":"4280"}', 'zh/ja: w 億 (100 mln), bez miejsc po przecinku');
  assert.deepEqual(Z.snbDelta(790, ''), {txt: '▲ +snb.bn{"v":"8"}', cls: ''});
  assert.equal(X.SNB_ROWS, 8); assert.equal(X.SNB_OKNO, 52); assert.equal(X.SNB_MAX_AGE, 45);
});

test('v124: Szwajcaria — panel z pliku: 3 kafle z datą i wiekiem, ▲/▼ wobec tygodnia i 4 tygodni, tabela 8 tygodni od najnowszego, brak = „—”, część z błędem = nota, bez danych ukryty', () => {
  const X = snb124.mk(), D = snb124.D, body = X.snbBody(D);
  assert.ok(!/undefined|NaN|\[object|null/.test(body), body.slice(0, 300));
  assert.equal((body.match(/<div class="etfk">/g) || []).length, 3, 'trzy kafle');
  assert.ok(body.includes('snb.k.dom') && body.includes('snb.k.tot') && body.includes('snb.k.fx'));
  assert.ok(body.includes('<small class="">▲ +snb.bn{"v":"0.8"} snb.k.d1w</small>') && body.includes('<small class="">▼ −snb.bn{"v":"9.1"} snb.k.d4w</small>'), 'krajowe: tydzień i 4 tygodnie');
  assert.ok(body.includes('<small class="na">— snb.k.d4w</small>'), 'razem bez zmiany 4-tygodniowej — kreska, nie zero');
  assert.ok(body.includes('snb.wk{"d":') && body.includes('age(2026-09-18)') && body.includes('snb.fxm{"m":') && body.includes('age(2026-07)'), 'data i wiek przy kaflach');
  assert.ok(body.includes('snb.bn{"v":"802.5"}') && body.includes('▲ +snb.bn{"v":"16.4"} snb.k.d1m') && body.includes('— snb.k.d12m'), 'rezerwy: zmiana miesięczna, brak rocznej');
  const trs = body.split('<tr><td>').slice(1); assert.equal(trs.length, 8, '8 tygodni z 9');
  assert.ok(trs[0].includes('snb.bn{"v":"432.0"}') && trs[1].includes('snb.bn{"v":"433.0"}') && trs[3].includes('snb.bn{"v":"435.0"}') && trs[7].includes('snb.bn{"v":"439.0"}'), 'od najnowszego (18.09, 11.09, 4.09, 28.08 … 24.07)');
  assert.ok(!trs.some(r => r.includes('snb.bn{"v":"440.0"}')), 'najstarszy tydzień (17.07) poza tabelą');
  assert.ok(trs[0].includes('▲ +snb.bn{"v":"0.8"}') === false && trs[0].includes('▲ +snb.bn{"v":"1.0"}') === false && trs[0].includes('▼ −snb.bn{"v":"1.0"}'), 'zmiana w tabeli z historii: 432 wobec 433 tydzień wcześniej');
  const r0904 = trs[2];
  assert.equal((r0904.match(/<span class="cell mono na">—<\/span>/g) || []).length, 2, 'tydzień bez krajowych: kwota i zmiana — kreski');
  assert.ok(body.includes('snb.mm{"n":"8","min":"snb.bn{\\"v\\":\\"432.0\\"}"'), 'najniżej / najwyżej z 8 liczb');
  assert.ok(body.includes('snb.leg') && body.includes('snb.note') && body.includes('snb.h.wk') && body.includes('class="snb-w"'), 'noty i nagłówki');
  assert.ok(!body.includes('pos') && !body.includes('neg'), 'bez kolorów kierunku');
  assert.ok(!body.includes('snb.prev') && !body.includes('snb.gw.na') && !body.includes('snb.fx.na'));
  // część z błędem z poprzednią wersją — nota z czasem części; brak części — nota
  const P = Object.assign({}, D, {ok: {gw: true, fx: false}, part_at: {fx: '2026-09-20T10:00:00+00:00'}});
  assert.ok(X.snbBody(P).includes('<p class="pnote neu">snb.prev{"t":"D(2026-09-20T10:00:00+00:00)"}</p>'));
  const noFx = X.snbBody(Object.assign({}, D, {fx_res: null}));
  assert.ok(noFx.includes('snb.fx.na') && (noFx.match(/<div class="etfk">/g) || []).length === 2);
  const noGw = X.snbBody({at: D.at, fx_res: D.fx_res, hist: []});
  assert.ok(noGw.includes('snb.gw.na') && (noGw.match(/<div class="etfk">/g) || []).length === 1 && !noGw.includes('<table'), 'same rezerwy');
  assert.equal(X.snbBody({at: D.at, week: '2026-09-18', domestic: null, total: null, fx_res: {month: 'x', value: 1}}), '', 'bez liczb — pusto');
  assert.equal(X.snbBody(null), ''); assert.equal(X.snbBody({week: 'bad', domestic: 1}), '');
  // rysowanie i wczytanie
  const el = {hidden: false, innerHTML: 'x'}, Y = snb124.mk({$: q => q === '#g-snb' ? el : null});
  Y.renderSnb(); assert.ok(el.hidden === true && el.innerHTML === '', 'bez danych — sekcja ukryta');
  Y.snbApply({at: new Date().toISOString(), hist: []}); assert.equal(el.hidden, true, 'plik bez liczb — ukryta');
  Y.snbApply(D);
  assert.ok(el.hidden === false && el.innerHTML.includes('snb.t') && el.innerHTML.includes('snb.sub') && el.innerHTML.includes('inst.file{"t":"D(' + D.at + ')"}') && el.innerHTML.includes('eng.notsays') && el.innerHTML.includes('snb.not') && el.innerHTML.includes('eng.disclaimer'));
  Y.snbApply(null); assert.equal(el.hidden, false, 'chwilowy błąd pobrania nie zasłania danych');
  const Z = snb124.mk({$: q => q === '#g-snb' ? el : null});
  Z.snbApply(Object.assign({}, D, {at: new Date(Date.now() - 50 * 864e5).toISOString()})); assert.equal(el.hidden, true, 'plik starszy niż 45 dni — ukryta');
  Z.snbApply(Object.assign({}, D, {at: 'kiedyś'})); assert.equal(el.hidden, true, 'plik bez daty — ukryta');
});

test('v124: Szwajcaria — prawdziwy słownik: pl w mld CHF, zh w 億; teksty bez surowych kluczy i bez nazwy banku; podpis źródła tylko na stronie Źródła', () => {
  const PROV = /\bSNB\b|Swiss National Bank|Nationalbank|Banque nationale|Banca nazionale|Banco Nacional|Национальный банк|国家银行|国立銀行|data\.snb/i;
  for (const L of ['pl', 'zh', 'ja', 'de']) {
    const tt = v96src.tFor(L), el = {hidden: true, innerHTML: ''};
    const X = snb124.mk({t: tt, L, $: q => q === '#g-snb' ? el : null, ...v96src.H});
    X.snbApply(snb124.D);
    const out = el.innerHTML;
    assert.ok(el.hidden === false && !/snb\.[a-z]/.test(out.replace(/snb-(w|not)/g, '')) && !out.includes('{') && !out.includes('undefined'), L + ': bez surowych kluczy: ' + (out.match(/snb\.[a-z.]+/) || [''])[0]);
    assert.ok(!PROV.test(out.replace(/snb-(w|not)/g, '')), L + ': panel bez nazwy banku / portalu');
    assert.ok(out.includes('img/flagi/ch.svg'), L + ': flaga Szwajcarii');
    if (L === 'pl') assert.ok(out.includes('432.0 mld CHF') && out.includes('▲ +0.8 mld CHF wobec poprzedniego tygodnia') && out.includes('Szwajcaria: depozyty banków w banku centralnym (tygodniowo)'), 'pl: ' + out.slice(0, 200));
    if (L === 'zh') assert.ok(out.includes('4320亿瑞郎') && out.includes('▲ +8亿瑞郎 较前一周'), 'zh: 億 jednostki');
    if (L === 'ja') assert.ok(out.includes('8025億スイスフラン'), 'ja: rezerwy w 億');
  }
  // podpis źródła: dopisany do akapitu wymaganych podpisów po narysowaniu strony Źródła — raz, bez błędu bez strony
  const calls = [], p = {innerHTML: 'A'}, page = {querySelector: s => s === '.zr-attr2 p.mtxt' ? p : null};
  const X = snb124.mk({$: q => q === '#page-sources' ? page : null, renderSources: function () { calls.push('rs'); return 7; }});
  assert.equal(X.renderSources(), 7, 'opakowanie zwraca wynik oryginału'); assert.deepEqual(calls, ['rs']);
  assert.equal(p.innerHTML, 'A · ' + X.SNB_CREDIT); X.renderSources(); assert.equal(p.innerHTML, 'A · ' + X.SNB_CREDIT, 'bez powtórzenia');
  assert.ok(X.SNB_CREDIT.startsWith('<span class="zr-snb">Source: Swiss National Bank (SNB), <a href="https://data.snb.ch/en" target="_blank" rel="noopener">data.snb.ch</a>') && X.SNB_CREDIT.endsWith('</span>'));
  X.snbCredit(null); X.snbCredit({}); X.snbCredit({querySelector: () => null});
  const Y = snb124.mk({$: () => null, renderSources: () => 1}); assert.equal(Y.renderSources(), 1, 'bez strony — bez błędu');
  assert.equal(snb124.mk().renderSources, undefined, 'bez funkcji strony Źródła — nic nie opakowujemy');
  assert.equal((html.match(/Swiss National Bank/g) || []).length, 1, 'nazwa banku w stronie tylko w podpisie źródła');
  const blok = html.slice(snb124.a0, html.indexOf('\n', html.indexOf('snbLoad();snbAuto();'))).split('\n').filter(l => !l.startsWith('const SNB_CREDIT=')).join('\n');
  assert.ok(!/Swiss National Bank|Nationalbank|data\.snb\.ch/.test(blok), 'kod panelu bez nazwy banku (poza podpisem)');
});

test('v124: Szwajcaria — słownik EXTRA121 w 10 językach (te same klucze, pola {d} {m} {v} {n}…), sekcja po aukcjach (GLOBAL), styl, plik co 60 min, blok przed USA (v98)', () => {
  const a = 'const EXTRA121=', x0 = html.indexOf(a); assert.ok(x0 > 0, 'słownik EXTRA121');
  const E = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  const L10 = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'];
  assert.deepEqual(Object.keys(E), L10, '10 języków, pl pierwszy');
  const KEYS = Object.keys(E.pl).sort();
  assert.ok(KEYS.length === 25 && KEYS.every(k => k.startsWith('snb.')), 'tylko klucze snb.*: ' + KEYS.length);
  const PH = {'snb.wk': ['{d}'], 'snb.fxm': ['{m}'], 'snb.bn': ['{v}'], 'snb.mm': ['{n}', '{min}', '{dmin}', '{max}', '{dmax}'], 'snb.prev': ['{t}']};
  const PROV = /\bSNB\b|Swiss National Bank|Nationalbank|Banque nationale|Banca nazionale|Banco Nacional|Национальный банк|国家银行|国立銀行|data\.snb/i;
  for (const L of L10) {
    assert.deepEqual(Object.keys(E[L]).sort(), KEYS, L + ': te same klucze');
    for (const k of KEYS) { assert.ok(typeof E[L][k] === 'string' && E[L][k].trim(), L + ' ' + k); assert.ok(!PROV.test(E[L][k]), 'nazwa banku: ' + L + ' ' + k); }
    for (const k in PH) for (const p of PH[k]) assert.ok(E[L][k].includes(p), L + ' ' + k + ' ' + p);
    for (const k of KEYS) if (!PH[k]) assert.ok(!/\{[a-z]+\}/.test(E[L][k]), L + ' ' + k + ': bez pól');
    assert.ok(['1000', '100'].includes(E[L]['snb.div']), L + ': dzielnik');
    assert.ok(E[L]['snb.leg'].includes('▲') && E[L]['snb.leg'].includes('▼') && E[L]['snb.sub'].includes('▲/▼'), L + ': legenda i ▲/▼ w opisie');
    assert.equal(v96src.I18N[L]['snb.t'], E[L]['snb.t'], L + ': nałożony na słownik strony');
  }
  assert.equal(E.zh['snb.div'], '100'); assert.equal(E.ja['snb.div'], '100'); assert.equal(E.pl['snb.div'], '1000');
  assert.equal(E.pl['snb.t'], 'Szwajcaria: depozyty banków w banku centralnym (tygodniowo)');
  assert.ok(E.pl['snb.note'].includes('brak nie jest zerem') && E.en['snb.note'].includes('a gap is not a zero') && E.pl['snb.note'].includes('nie jest przepływem'), 'brak ≠ zero, stan ≠ przepływ');
  assert.ok(E.pl['snb.sub'].includes('interwencji') && E.pl['snb.sub'].includes('bezpiecznej przystani') && E.pl['snb.sub'].includes('4 tygodni'), 'dlaczego to ważne');
  assert.ok(E.pl['snb.not'].includes('raz na kwartał'), '„czego nie mówi”');
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA121') > apl.indexOf('EXTRA117') && apl.indexOf('EXTRA117') >= 0, 'EXTRA121 dołączony po EXTRA117');
  assert.ok(html.indexOf('const EXTRA121=') < html.indexOf('/* ===================== STAN I DANE'), 'w bloku słowników');
  assert.equal(html.split('<section class="panel pcard" id="g-snb" hidden></section>').length, 2, 'jedno miejsce sekcji');
  const u = html.indexOf('<section class="panel pcard" id="g-aukcje" hidden></section>'), x = html.indexOf('<section class="panel pcard" id="g-snb" hidden></section>'), n = html.indexOf('<section class="panel pcard" id="inst" hidden></section>');
  assert.ok(u > 0 && x > u && n > x, 'zakładka GLOBAL: po aukcjach, przed danymi urzędowymi');
  assert.ok(html.includes("srvJSON('snb')") && html.includes('/* v124 szwajcaria: depozyty w banku centralnym */') && html.includes('#g-snb .etfkpis{grid-template-columns:repeat(3,minmax(0,1fr))}'), 'plik, styl');
  assert.ok(html.indexOf('/* v124 szwajcaria') < html.indexOf('/* v105 wieloryby */'), 'styl przed wielorybami');
  assert.ok(html.includes("SNB.timer=setInterval(()=>{if(!document.hidden)snbLoad();},60*60*1000);") && html.includes('if(!ok&&SNB.data)return;'), 'odświeżanie co godzinę; chwilowy błąd nie zasłania danych');
  assert.ok(html.includes("snbLoad();snbAuto();try{new MutationObserver(()=>renderSnb()).observe(document.documentElement,{attributes:true,attributeFilter:['lang']});}catch(e){}"), 'zmiana języka');
  assert.equal(html.split('/* ===================== v124: SZWAJCARIA').length, 2);
  assert.ok(html.indexOf('/* ===================== v124: SZWAJCARIA') < html.indexOf('/* ===================== v98: USA'), 'blok przed blokiem USA (v98)');
  assert.ok(html.indexOf('/* ===================== v124: SZWAJCARIA') > html.indexOf('function renderSources(){'), 'opakowanie po definicji strony Źródła');
});

/* v125: TRENDY krypto — sygnały dzienne w wersji reguły 2 (pięć powodów p/t/e/s/h, linie n2 i all, okno 06:00 → 06:00 UTC): wiersze `d` z fam „cr”
   i polem rs (trdDRow2), linie `bd` z fam „cr” i v === 2 (trdDailyC → trdDailyC2). Dane: prawdziwa część krypto pliku trendy.json z 27.09.2026
   (10 wierszy + 7 linii v2 — v125/judge2/out/trendy_cr_v125_example.json) i linia v1 cr·p (v: 1) z tego samego pliku; świat — dane testowe v120.
   Prawdziwe słowniki strony (wszystkie EXTRA po kolei) i prawdziwe nfmt/fInt/fPct; wiek danych (gAgeNote) atrapą — testy bez zegara.
   Wiersze v2 z regułą c / cx / c0 (dopisek do SPEC §5.1 — SPEC-v125-ADDENDUM: kody nieznane stronie sprzed v125); przed nimi 10 kart v1
   (V1R) z pliku, który w tym samym przebiegu zapisuje zbieracz produkcji — zbieracz v125 zostawia je w pliku (dopisek A1). Blok TRENDY
   produkcji 44e0565 (karta przeglądarki otwarta przed wdrożeniem wykonuje zamrożony kod produkcji) osadzony dosłownie przy budowie łatki
   z judge2/prod/index.html, z sumą FNV-1a — test nie zależy od tego, co następne wydania zmienią w bloku TRENDY strony. */
const trdV125 = (() => {
  const CR = {rows: [
    {"id":"BTC","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"BTC","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":0.4,"zp":0.17,"rule":"c0","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null,"ici":null,"rs":[["p",0.4,0.17,0],["t",48.4,-0.58,0],["e",-5945,-0.82,0],["s",158,0.38,0],["h",-0.0419,-0.61,0]],"N":0,"ek":[],"lt":[]},
    {"id":"ETH","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"ETH","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":0.18,"zp":0.05,"rule":"c","dir":-1,"side":"sell","str":2,"st":"obs","vd":"none","ik":338,"in":643,"ici":[48.7,56.4],"rs":[["p",0.18,0.05,0],["t",45.7,-1.23,-1],["e",47592,1.43,-1],["s",158,0.38,0],["h",-0.0063,0.48,0]],"N":-2,"ek":[],"lt":[]},
    {"id":"XRP","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"XRP","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-2.62,"zp":-0.62,"rule":"c","dir":-1,"side":"sell","str":1,"st":"obs","vd":"none","ik":322,"in":628,"ici":[47.4,55.2],"rs":[["p",-2.62,-0.62,0],["t",44.3,-1.38,-1],["s",158,0.38,0],["h",-0.0003,0.44,0]],"N":-1,"ek":[],"lt":[]},
    {"id":"BNB","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"BNB","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-0.46,"zp":-0.22,"rule":"c","dir":1,"side":"buy","str":1,"st":"obs","vd":"none","ik":304,"in":615,"ici":[45.5,53.4],"rs":[["p",-0.46,-0.22,0],["t",53.7,1.41,1],["s",158,0.38,0],["h",-0.004,0.08,0]],"N":1,"ek":[],"lt":[]},
    {"id":"SOL","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"SOL","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-0.61,"zp":-0.18,"rule":"c0","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null,"ici":null,"rs":[["p",-0.61,-0.18,0],["t",52.8,0.99,0],["s",158,0.38,0],["h",-0.0164,0.2,0]],"N":0,"ek":[],"lt":[]},
    {"id":"DOGE","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"DOGE","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-2.26,"zp":-0.58,"rule":"cx","dir":0,"side":"none","str":0,"st":"x","vd":null,"ik":null,"in":null,"ici":null,"rs":[["p",-2.26,-0.58,0],["t",52.6,1.37,1],["s",158,0.38,0],["h",0.0526,1.59,-1]],"N":0,"ek":[],"lt":[]},
    {"id":"ADA","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"ADA","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-1.85,"zp":-0.43,"rule":"c","dir":-1,"side":"sell","str":1,"st":"obs","vd":"none","ik":299,"in":629,"ici":[43.7,51.4],"rs":[["p",-1.85,-0.43,0],["t",49.7,0.13,0],["s",158,0.38,0],["h",0.0204,1.52,-1]],"N":-1,"ek":[],"lt":[]},
    {"id":"TRX","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"TRX","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-1.15,"zp":-1.35,"rule":"c","dir":-1,"side":"sell","str":2,"st":"obs","vd":"none","ik":298,"in":611,"ici":[44.8,52.7],"rs":[["p",-1.15,-1.35,-1],["t",39.9,-1.87,-1],["s",158,0.38,0],["h",-0.0705,-0.74,0]],"N":-2,"ek":[],"lt":[]},
    {"id":"LINK","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"LINK","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":1.55,"zp":0.4,"rule":"c0","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null,"ici":null,"rs":[["p",1.55,0.4,0],["t",49.9,0.08,0],["s",158,0.38,0],["h",0.0216,0.67,0]],"N":0,"ek":[],"lt":[]},
    {"id":"AVAX","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"AVAX","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":1.78,"zp":0.39,"rule":"cx","dir":0,"side":"none","str":0,"st":"x","vd":null,"ik":null,"in":null,"ici":null,"rs":[["p",1.78,0.39,0],["t",55.5,1.46,1],["s",158,0.38,0],["h",0.0229,1.3,-1]],"N":0,"ek":[],"lt":[]}],
  lines: [
    {"fam":"cr","rule":"p","k":1271,"n":2652,"days":751,"from":"2023-11-03","to":"2026-09-24","p":47.9,"ci":[44.4,51.5],"ca":[43.1,52.8],"cl":99.3,"M":7,"b0":50.1,"thr":55.0,"mde":56.5,"h1":49.7,"h2":46.2,"sb":{"k":698,"n":1425,"days":484,"p":49.0,"b0":50.3,"ci":[44.6,53.4]},"ss":{"k":573,"n":1227,"days":333,"p":46.7,"b0":49.8,"ci":[41.4,52.1]},"y1":{"k":403,"n":875,"days":240,"p":46.1,"ci":[39.9,52.4],"from":"2025-09-28","to":"2026-09-24"},"lk":0,"ln":0,"ldays":0,"lvd":"wait","lc":null,"lnx":100,"cll":99.8,"m":10,"need":0,"vd":"none","v":2,"since":"2026-09-28","wh":6,"cut":330},
    {"fam":"cr","rule":"t","k":1661,"n":3320,"days":1015,"from":"2023-11-02","to":"2026-09-24","p":50.0,"ci":[47.0,53.1],"ca":[45.8,54.2],"cl":99.3,"M":7,"b0":50.0,"thr":54.2,"mde":55.5,"h1":49.4,"h2":50.7,"sb":{"k":832,"n":1678,"days":730,"p":49.6,"b0":50.4,"ci":[46.0,53.2]},"ss":{"k":829,"n":1642,"days":710,"p":50.5,"b0":49.6,"ci":[46.8,54.2]},"y1":{"k":546,"n":1097,"days":349,"p":49.8,"ci":[44.6,55.0],"from":"2025-09-27","to":"2026-09-24"},"lk":0,"ln":0,"ldays":0,"lvd":"wait","lc":null,"lnx":100,"cll":99.8,"m":10,"need":0,"vd":"none","v":2,"since":"2026-09-28","wh":6,"cut":330},
    {"fam":"cr","rule":"e","k":100,"n":175,"days":167,"from":"2023-11-07","to":"2026-09-24","p":57.1,"ci":[49.6,64.4],"ca":[46.8,66.9],"cl":99.3,"M":7,"b0":50.2,"thr":60.6,"mde":63.8,"h1":61.4,"h2":53.3,"sb":{"k":63,"n":99,"days":96,"p":63.6,"b0":51.3,"ci":[53.7,72.6]},"ss":{"k":37,"n":76,"days":76,"p":48.7,"b0":48.7,"ci":[37.8,59.7]},"y1":{"k":23,"n":52,"days":44,"p":44.2,"ci":[30.6,58.8],"from":"2026-05-27","to":"2026-09-24"},"lk":0,"ln":0,"ldays":0,"lvd":"wait","lc":null,"lnx":100,"cll":99.8,"m":2,"need":0,"vd":"none","v":2,"since":"2026-09-28","wh":6,"cut":330},
    {"fam":"cr","rule":"s","k":847,"n":1755,"days":176,"from":"2023-11-02","to":"2026-09-24","p":48.3,"ci":[41.0,55.6],"ca":[38.4,58.3],"cl":99.3,"M":7,"b0":50.1,"thr":60.2,"mde":63.4,"h1":51.4,"h2":45.2,"sb":{"k":568,"n":1118,"days":112,"p":50.8,"b0":50.3,"ci":[41.7,59.9]},"ss":{"k":279,"n":637,"days":64,"p":43.8,"b0":49.6,"ci":[32.3,56.0]},"y1":{"k":222,"n":488,"days":49,"p":45.5,"ci":[32.4,59.3],"from":"2025-10-02","to":"2026-09-24"},"lk":0,"ln":0,"ldays":0,"lvd":"wait","lc":null,"lnx":100,"cll":99.8,"m":10,"need":0,"vd":"none","v":2,"since":"2026-09-28","wh":6,"cut":330},
    {"fam":"cr","rule":"h","k":2021,"n":3929,"days":983,"from":"2023-11-02","to":"2026-09-23","p":51.4,"ci":[48.3,54.6],"ca":[47.2,55.7],"cl":99.3,"M":7,"b0":50.0,"thr":54.3,"mde":55.6,"h1":52.3,"h2":50.3,"sb":{"k":991,"n":1883,"days":620,"p":52.6,"b0":50.3,"ci":[48.7,56.5]},"ss":{"k":1030,"n":2046,"days":578,"p":50.3,"b0":49.7,"ci":[46.3,54.4]},"y1":{"k":520,"n":1052,"days":333,"p":49.4,"ci":[44.1,54.8],"from":"2025-09-27","to":"2026-09-23"},"lk":0,"ln":0,"ldays":0,"lvd":"wait","lc":null,"lnx":100,"cll":99.8,"m":10,"need":0,"vd":"none","v":2,"since":"2026-09-28","wh":6,"cut":330},
    {"fam":"cr","rule":"n2","k":780,"n":1600,"days":654,"from":"2023-11-02","to":"2026-09-24","p":48.8,"ci":[44.9,52.6],"ca":[43.5,54.0],"cl":99.3,"M":7,"b0":50.0,"thr":55.3,"mde":56.9,"h1":52.0,"h2":45.4,"sb":{"k":443,"n":883,"days":383,"p":50.2,"b0":50.3,"ci":[45.2,55.2]},"ss":{"k":337,"n":717,"days":300,"p":47.0,"b0":49.6,"ci":[41.4,52.7]},"y1":{"k":207,"n":468,"days":204,"p":44.2,"ci":[37.6,51.1],"from":"2025-09-28","to":"2026-09-24"},"lk":0,"ln":0,"ldays":0,"lvd":"wait","lc":null,"lnx":100,"cll":99.8,"m":10,"need":0,"vd":"none","v":2,"since":"2026-09-28","wh":6,"cut":330},
    {"fam":"cr","rule":"all","k":3187,"n":6336,"days":1056,"from":"2023-11-02","to":"2026-09-24","p":50.3,"ci":[47.3,53.3],"ca":[46.2,54.4],"cl":99.3,"M":7,"b0":50.0,"thr":54.2,"mde":55.5,"h1":51.9,"h2":48.6,"sb":{"k":1734,"n":3367,"days":842,"p":51.5,"b0":50.4,"ci":[48.1,54.9]},"ss":{"k":1453,"n":2969,"days":791,"p":48.9,"b0":49.7,"ci":[45.5,52.4]},"y1":{"k":982,"n":2026,"days":361,"p":48.5,"ci":[43.4,53.6],"from":"2025-09-27","to":"2026-09-24"},"lk":0,"ln":0,"ldays":0,"lvd":"wait","lc":null,"lnx":100,"cll":99.8,"m":10,"need":0,"vd":"none","v":2,"since":"2026-09-28","wh":6,"cut":330}]};
  const V1L = {"fam":"cr","rule":"p","k":438,"n":909,"days":252,"from":"2025-09-13","to":"2026-09-25","p":48.2,"ci":[42.1,54.3],"h1":48.4,"h2":48.0,"lk":0,"ln":0,"ldays":0,"m":10,"need":0,"vd":"none","v":1,"since":"2026-09-28"};
  const V1R = [
    {"id":"BTC","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"BTC","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":0.4,"zp":0.17,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"ETH","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"ETH","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":0.18,"zp":0.05,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"XRP","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"XRP","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-2.62,"zp":-0.62,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"BNB","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"BNB","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-0.46,"zp":-0.22,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"SOL","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"SOL","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-0.61,"zp":-0.18,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"DOGE","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"DOGE","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-2.26,"zp":-0.58,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"ADA","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"ADA","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-1.85,"zp":-0.43,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"TRX","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"TRX","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":-1.15,"zp":-1.35,"rule":"p","dir":-1,"side":"sell","str":1,"st":"obs","vd":"none","ik":39,"in":82},
    {"id":"LINK","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"LINK","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":1.55,"zp":0.4,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null},
    {"id":"AVAX","fam":"cr","grp":null,"iss":null,"pub":0,"sym":"AVAX","date":"2026-09-26","nx":"2026-09-27","live":true,"age":1,"f":null,"cur":null,"fu":null,"zf":null,"r":1.78,"zp":0.39,"rule":"none","dir":0,"side":"none","str":0,"st":"quiet","vd":null,"ik":null,"in":null}];
  const b0 = html.indexOf('/* v89: TRENDY — początek'), b1 = html.indexOf('/* v89: TRENDY — koniec */'), blk = html.slice(b0, b1);
  const l0 = html.indexOf('const LOCALE='), LOC = new Function(html.slice(l0, html.indexOf('\n', l0)) + '\nreturn LOCALE;')();
  const f0 = html.indexOf('const NF={};'), f1 = html.indexOf('\n', html.indexOf('const fPct=', f0)), I = trdV96.ICO;
  const fnv = s => { let h = 0x811c9dc5; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 0x01000193) >>> 0; } return h.toString(16); };
  /* blok TRENDY produkcji 44e0565 — stara karta przeglądarki: kod, który wykonuje karta otwarta przed wdrożeniem (osadzony przy budowie łatki;
     przy budowie sprawdzone też, że cofnięcie podmian łatki na tej stronie daje dokładnie ten blok) */
  const PROD_BLK = "/* v89: TRENDY — początek (plik serwera data/trendy.json: tydzień na tle 4 poprzednich, każde źródło osobno; opis tego, co się stało — nie prognoza) */\nconst TRD={data:null,timer:null,open:{},shown:''};   /* v96: open — otwarte bloki osobno dla każdego widoku; shown — widok na ekranie */\nconst TRD_ORD=['in_up','in_rev','in_new','in_dir','in_flat','in_down','in_stop','out_up','out_rev','out_new','out_dir','out_flat','out_down','out_stop','mixed','none','short','gap','stale'];\nconst TRD_PORD=['up_cont','up_new','dn_fade','up_fade','dn_new','dn_cont','flat'];\nconst TRD_M=['flow','stock','exch','supply','pos'];\nfunction trdApply(j){\n  const ok=!!(j&&typeof j==='object'&&typeof j.at==='string'&&Array.isArray(j.f)&&Array.isArray(j.p));\n  if(!ok){if(TRD.data)return;TRD.data=null;}          /* chwilowy błąd pobrania nie zasłania wcześniej wczytanych danych */\n  else if(TRD.data&&TRD.data.at===j.at)return;         /* ten sam plik — bez przebudowy (otwarte bloki zostają) */\n  else TRD.data=j;\n  if(st.mode==='trendy')renderTrendy();\n  else if(st.mode==='global'&&typeof gst!=='undefined'&&gst.sel&&typeof gRenderDetail==='function')gRenderDetail();   /* v91: linie funduszy w opisie regionu */\n}\nfunction trdLoad(){srvJSON('trendy').then(trdApply);}\nfunction trdAuto(){if(TRD.timer)clearInterval(TRD.timer);TRD.timer=setInterval(()=>{if(!document.hidden)trdLoad();},20*60*1000);}\nconst trdNum=v=>typeof v==='number'&&isFinite(v);\nconst trdLt=()=>'&lt;'+nfmt(.1,1)+' ';\n/* kwota w jednostce źródła: mln waluty; BTC/ETH — monety; CT — kontrakty; JPY — mld JPY. Brak → „—”, mała kwota → „<0,1 mln”, nigdy 0 */\nfunction trdAmt(v,cur){\n  if(!trdNum(v))return '—';\n  const c=escH(cur);\n  if(cur==='BTC'||cur==='ETH'){const a=Math.abs(v);return a>0&&a<.5?sg(v)+'&lt;1 '+c:fInt(Math.round(v))+' '+c;}\n  if(cur==='CT')return fInt(Math.round(v))+' '+t('trd.u.ct');\n  const m=cur==='JPY'?v*1000:v,a=Math.abs(m);   /* własne jednostki: u.m / u.b strony zawierają już „USD” */\n  if(a>0&&a<.05)return sg(m)+trdLt()+t('trd.u.m')+' '+c;\n  if(a>=1000)return sg(m)+nfmt(a/1000,a>=10000?1:2)+' '+t('trd.u.b')+' '+c;\n  return sg(m)+nfmt(a,a<10?1:0)+' '+t('trd.u.m')+' '+c;\n}\nconst trdDay=iso=>{const ms=Date.parse(String(iso||'').slice(0,10)+'T00:00:00Z');return isFinite(ms)?new Date(ms).toLocaleDateString(LOCALE[LANG],{timeZone:'UTC',day:'2-digit',month:'2-digit',year:'numeric'}):'—';};\nfunction trdUnit(r,n){return r.sz===1?t('trd.u.wk'):r.sz===7?t('trd.u.days'):zagSes(n);}\nfunction trdWin(r){return r.sz===1?t('trd.n.wk',{d:trdDay(r.date)}):t('fo.s',{n:r.sz,x:trdUnit(r,r.sz),d:trdDay(r.date)});}\nfunction trdSn(r){const k='trd.sn.'+r.m+'.'+r.st,o=r.st==='short'?{n:trdNum(r.n)?r.n:'—'}:undefined;return ((I18N[LANG]&&I18N[LANG][k])||I18N.en[k])?t(k,o):t('trd.sn.'+r.st,o);}\nfunction trdUsd(r){return r.cur==='USD'?r.w:(trdNum(r.wu)?r.wu:null);}\nconst trdEv=r=>!['short','gap','stale'].includes(r.st);\n/* v96: dwa widoki — „Trendy global” i „Trendy krypto”; krypto = grupa cr + pozycje na kontraktach na bitcoina i ether */\nconst trdCry=r=>r.g==='cr'||r.id==='cf_btc'||r.id==='cf_eth';\nconst trdIsC=()=>!!(st&&st.trdv==='crypto');\n/* v96: kolor według stanu (nie według znaku w tekście): napływ i wzrost — zielony, odpływ i spadek — czerwony,\n   słabiej niż zwykle albo bez wyraźnego kierunku — żółty; brak nowych danych albo części tygodnia — szary; zero — bez koloru */\nconst TRD_TONE={in_up:'pos',in_flat:'pos',in_rev:'pos',in_new:'pos',in_dir:'pos',out_up:'neg',out_flat:'neg',out_rev:'neg',out_new:'neg',out_dir:'neg',\n  in_down:'neu',out_down:'neu',in_stop:'neu',out_stop:'neu',mixed:'neu',none:'neu',short:'',gap:'',stale:'',\n  up_cont:'pos',up_new:'pos',dn_fade:'pos',up_fade:'neg',dn_new:'neg',dn_cont:'neg',flat:'neu'};\n/* „za mało historii”, luka i brak nowych danych — bez oceny, więc bez koloru (szary znaczek); największy napływ / odpływ w kaflach krypto ma kolor z kafla */\nfunction trdTone(r){if(!r||!trdNum(r.w)||r.w===0)return '';return TRD_TONE[r.st]||'';}\nconst trdVc=r=>trdNum(r.w)?trdTone(r):'na';   /* brak wartości — szary „—” (brak to nie zero) */\nconst TRD_DLT={pos:'up',neg:'dn',neu:'chg'};\n/* znaczek stanu (▲ ▼ △ ▽ •) w kolorze stanu, opis zostaje szary */\nfunction trdSt(s,tone){const x=String(s),m=/^([▲▼△▽•])\\s+/.exec(x);return m?`<i class=\"tg${tone?' '+tone:''}\">${m[1]}</i> ${escH(x.slice(m[0].length))}`:escH(x);}\n/* v96: ikony — kraj = flaga (dwa kraje = dwie flagi), moneta = logo, surowiec = glif, fundusz = znaczek wydawcy.\n   Funkcje z bloku v96 (flagImg, glyphImg, coinImg, issBadge, issuerOf); bez nich (np. w teście) — bez ikon, reszta karty bez zmian. */\nconst TRD_ICO={fe_us:'us',fe_tech:'us',fe_fin:'us',fe_energy:'us',fe_health:'us',fe_indu:'us',fe_cdisc:'us',fe_cstap:'us',fe_util:'us',\n  fe_dev:'@globe',fe_eur:'eu',fe_jpn:'jp',fe_chn:'cn',fe_india:'in',fe_bra:'br',fe_kor:'kr',fe_twn:'tw',fe_em:'@globe',fe_emb:'@globe',\n  fe_ustl:'us',fe_ustm:'us',fe_usts:'us',fe_agg:'us',fe_ig:'us',fe_hy:'us',fe_gold:'@gold',fe_silver:'@silver',\n  in_eq:'in',in_bd:'in',tw:'tw',hk:'hk cn',th:'th',br:'br',tr_eq:'tr',tr_bd:'tr',jp_eq:'jp',jp_bd:'jp',mx:'mx',\n  etf_btc:'$BTC us',etf_eth:'$ETH us',etf_sol:'$SOL us',etf_xrp:'$XRP us',cm_btc:'$BTC',cm_eth:'$ETH',stab:'$USDT $USDC',cf_btc:'$BTC',cf_eth:'$ETH',\n  cf_usd:'us',cf_eur:'eu',cf_jpy:'jp',cf_spx:'us',cf_msciem:'@globe',cs_gold:'@gold',cs_silver:'@silver',cs_copper:'@copper',cs_wti:'@oil',\n  SPY:'us',EWC:'ca',ILF:'br mx cl co',VGK:'eu gb ch',KSA:'sa',TUR:'tr',EIS:'il',EZA:'za',INDA:'in',MCHI:'cn',EWJ:'jp',EWY:'kr',ASEA:'id sg th my ph',EWA:'au',\n  b_th:'th',b_mx:'mx',b_ob:'in tw hk br',b_fe:'us @etf',b_px:'@globe'};\nconst TRD_ISS={ssga:['ssga'],ishares:['ishares'],both:['ssga','ishares']};\nfunction trdIco(spec,iss,max,cls){\n  const m=max||3;let h='',nf=0,more=0;\n  for(const p of String(spec||'').split(' ').filter(Boolean)){\n    if(p[0]==='@')h+=typeof glyphImg==='function'?glyphImg(p.slice(1),cls):'';\n    else if(p[0]==='$')h+=typeof coinImg==='function'?coinImg(p.slice(1),cls):'';\n    else if(nf<m){h+=typeof flagImg==='function'?flagImg(p,cls):'';nf++;}\n    else more++;\n  }\n  if(h&&more)h+=`<i class=\"more\">+${more}</i>`;\n  for(const k of iss||[])h+=typeof issBadge==='function'?issBadge(k,cls):'';\n  return h?`<span class=\"icos\">${h}</span>`:'';\n}\nfunction trdIcoF(r,cls){const fe=r.id.slice(0,3)==='fe_',iss=fe?TRD_ISS[r.iss]||[]:[];return trdIco((TRD_ICO[r.id]||'@globe')+(fe&&!iss.length?' @etf':''),iss,0,cls);}\nfunction trdIssOf(sym){const k=typeof issuerOf==='function'?issuerOf(sym,''):'';return k?[k]:[];}\nfunction trdIcoP(r,cls){\n  if(r.g==='cr')return trdIco('$'+r.id,[],0,cls);\n  if(r.g==='fp'){const fe=TRD.data&&Array.isArray(TRD.data.flows)?TRD.data.flows.find(x=>x&&x.id==='fe_'+r.id.slice(3)):null,iss=fe&&TRD_ISS[fe.iss]||trdIssOf(r.sym);return trdIco(TRD_ICO['fe_'+r.id.slice(3)]||'@etf',iss,0,cls);}   /* v98.2: grupa funduszy (np. GLD, IAU, GLDM) — znaczki wszystkich wydawców, jak na karcie przepływów */   /* fundusz wybrany w pliku (np. GLD albo IAU) — wydawca z symbolu */\n  return trdIco(TRD_ICO[r.id]||'@globe',trdIssOf(r.id),0,cls);\n}\nfunction trdCard(r){\n  const tone=trdTone(r),ev=trdEv(r);\n  const l1=[];\n  if(r.cur!=='USD'&&trdNum(r.wu))l1.push('≈ '+trdAmt(r.wu,'USD')+(typeof r.fxm==='string'&&/^\\d{4}-\\d{2}$/.test(r.fxm)?' ('+t('trd.n.fxm',{m:r.fxm.slice(5)+'.'+r.fxm.slice(0,4)})+')':''));\n  l1.push(trdWin(r)+gAgeNote(r.date));\n  const l2=[];\n  if(trdNum(r.base))l2.push(t('trd.n.base',{v:trdAmt(r.base,r.cur)}));\n  if(ev&&r.x)l2.push(t('trd.n.x'));\n  if(ev&&r.roll)l2.push(t('trd.n.roll'));\n  if(trdNum(r.s)&&r.s>=(r.sz===1?3:5))l2.push(t(r.sg>0?'trd.n.sp':'trd.n.sm',{n:r.s,x:trdUnit(r,r.s)}));\n  if(ev&&trdNum(r.dz)&&Math.abs(r.dz)>=3)l2.push(t('trd.n.day',{v:trdAmt(r.last,r.cur)}));\n  if(trdNum(r.ph))l2.push(t('trd.n.ph.'+(r.id.slice(0,3)==='etf'||r.id.slice(0,3)==='fe_'?'etf':r.id.slice(0,2)==='cm'?'cm':'hold'),{p:sg(r.ph)+nfmt(Math.abs(r.ph),2)+'%'}));\n  /* v96: nazwy dostawców danych tylko na stronie Źródła; wydawcy funduszy — znaczki przy nazwie */\n  return `<div class=\"etfk trk\">${trdIcoF(r)}<span>${escH(t('trd.s.'+r.id))}</span><b class=\"${trdVc(r)}\">${trdAmt(r.w,r.cur)}<small>${trdSt(trdSn(r),tone)}</small></b><small class=\"mtxt\">${l1.join(' · ')}${l2.length?'<br>'+l2.join(' · '):''}</small></div>`;\n}\nfunction trdSort(A){return A.slice().sort((a,b)=>(TRD_ORD.indexOf(a.st)-TRD_ORD.indexOf(b.st))||((trdNum(b.d)?Math.abs(b.d):-1)-(trdNum(a.d)?Math.abs(a.d):-1)));}\n/* jedno zdanie na górze sekcji: źródła, które w ostatnim tygodniu wyraźnie odbiegały od zwykłego poziomu (źródeł nie sumujemy) */\nconst TRD_KEY=['in_up','in_rev','in_new','in_down','in_stop','out_up','out_rev','out_new','out_down','out_stop'];\nfunction trdSum(A){\n  const ev=A.filter(trdEv);\n  if(!ev.length)return `<p class=\"pnote\">${t('trd.sum.noeval')}</p>`;\n  const K=trdSort(ev.filter(r=>TRD_KEY.includes(r.st))).slice(0,6);\n  if(!K.length)return `<p class=\"pnote\">${t('trd.sum.none')}</p>`;\n  return `<p class=\"pnote\"><b>${t('trd.sum.t')}</b> ${K.map(r=>{const ic=trdIcoF(r,'sm'),nm=`<b>${escH(t('trd.s.'+r.id))}</b>`;return `${ic?`<span class=\"trd-nw\">${ic}${nm}</span>`:nm}: ${trdSt(trdSn(r),trdTone(r))}`;}).join(' · ')}</p>`;   /* v96: flaga / logo także w zdaniu */\n}\nfunction trdPanel(key,A,keep){\n  if(!A.length)return '';\n  const top=r=>trdEv(r)||(keep||[]).includes(r.st),main=trdSort(A.filter(top)),rest=trdSort(A.filter(r=>!top(r)));\n  return `<section class=\"panel pcard\"><h2>${t('trd.'+key+'.t')}</h2><p class=\"pnote\">${t('trd.'+key+'.sub')}</p>${trdSum(A)}`+\n    (main.length?`<div class=\"etfkpis\">${main.map(trdCard).join('')}</div>`:'')+\n    (rest.length?`<details class=\"etfd\" id=\"trd-rest-${key}\"><summary>${t('trd.rest',{n:rest.length})}</summary><div class=\"etfkpis\">${rest.map(trdCard).join('')}</div></details>`:'')+`</section>`;\n}\nfunction trdPx(r){\n  const eq=r.g==='eq'||r.g==='fp',name=r.g==='fp'?t('trd.s.fe_'+r.id.slice(3)):eq?t('trd.px.'+r.id):r.id;   /* v93: fp — cena jednostki funduszu */\n  const l=[t(eq?'trd.n.pw':'trd.n.pw7',{d:trdDay(r.date)})+gAgeNote(r.date),t(eq?'trd.n.pr':'trd.n.pr23',{v:trdNum(r.pr)?fPct(r.pr,2):'—'})];\n  if(eq&&trdNum(r.typ))l.push(t('trd.n.typ',{v:nfmt(r.typ,1)}));\n  if(r.g==='fp')l.push(t(r.id==='fp_gold'||r.id==='fp_silver'?'trd.n.nav0':'trd.n.nav',{s:escH(r.sym)}));   /* v94: trusty złota i srebra nie płacą dywidend */\n  const tone=trdTone(r);\n  return `<div class=\"etfk trk\">${trdIcoP(r)}<span>${escH(name)}</span><b class=\"${trdVc(r)}\">${trdNum(r.w)?fPct(r.w,2):'—'}<small>${trdSt(t('trd.ps.'+r.st),tone)}</small></b><small class=\"mtxt\">${l.join(' · ')}</small></div>`;\n}\nfunction trdPxSort(A){return A.slice().sort((a,b)=>(TRD_PORD.indexOf(a.st)-TRD_PORD.indexOf(b.st))||(Math.abs(b.w||0)-Math.abs(a.w||0)));}\nfunction trdVerdict(b){const ci=Array.isArray(b.ci)?b.ci:[];return trdNum(ci[0])&&ci[0]>50?'more':trdNum(ci[1])&&ci[1]<50?'less':'coin';}\n/* v96: kafel — ikona przed tytułem, kwota w kolorze (największy napływ zielony, odpływ czerwony, osłabienie żółte), znaczek stanu w kolorze stanu */\nfunction trdTile(title,val,tone,line,foot,ico,ftone){\n  const f=String(foot),m=/^([▲▼△▽•])\\s+/.exec(f),ft=ftone===undefined?tone:ftone,g=m?m[1]:ft==='pos'?'▲':ft==='neg'?'▼':'•',x=m?f.slice(m[0].length):f,vt=val==='—'?'na':tone;   /* brak — szary „—” */\n  return `<div class=\"panel kpi\"><div class=\"k-head\">${ico||''}<span>${title}</span></div><div class=\"k-val${vt?' '+vt:''}\">${val}</div>`+\n    (line?`<small class=\"mtxt\">${line}</small>`:'')+\n    (x.trim()?`<div class=\"k-foot\"><span class=\"dlt ${TRD_DLT[ft]||'na'}\">${g}</span><span class=\"ksrc\" title=\"${escH(x)}\">${escH(x)}</span></div>`:'')+`</div>`;   /* v98.2: pusty opis — bez samotnego „•” */\n}\nfunction trdPick(A,f,k){return A.filter(f).sort((a,b)=>k(b)-k(a))[0]||null;}\n/* kafle: źródła z pełną historią (8 tygodni), wybór według odchylenia od zwykłego poziomu w mln USD (du); Meksyk (zmiana stanu), giełdy krypto i CFTC — bez kafli; v96: tylko świat (krypto ma własne kafle) */\nfunction trdKpis(F,P,B){\n  const money=F.filter(r=>r.m==='flow'&&!r.lc&&trdNum(r.du)&&!trdCry(r));\n  const pick=trdPick;\n  const inU=pick(money,r=>['in_up','in_rev','in_new'].includes(r.st),r=>r.du),outU=pick(money,r=>['out_up','out_rev','out_new'].includes(r.st),r=>-r.du),\n        fade=pick(money,r=>['in_down','in_stop','out_down','out_stop'].includes(r.st),r=>Math.abs(r.du));\n  const EQ=P.filter(r=>r.g==='eq'&&trdNum(r.w)),pU=pick(EQ,r=>r.w>0,r=>r.w),pD=pick(EQ,r=>r.w<0,r=>-r.w);\n  const b=B.find(x=>x.id==='px')||null;\n  const ft=(title,r,tone)=>{if(!r)return trdTile(title,'—','','',t('trd.k.none'),trdIco('@globe',[],2,'sm'));const u=trdUsd(r);\n    return trdTile(title,trdNum(u)?(r.cur==='USD'?'':'≈ ')+trdAmt(u,'USD'):trdAmt(r.w,r.cur),tone,\n      `${escH(t('trd.s.'+r.id))} · ${trdWin(r)}${gAgeNote(r.date)} · ${t('trd.n.base',{v:trdAmt(r.base,r.cur)})}`,trdSn(r),trdIcoF(r,'sm'),trdTone(r));};\n  const pt=(title,r)=>r?trdTile(title,fPct(r.w,2),trdTone(r),`${escH(t('trd.px.'+r.id))} · ${t('trd.n.pw',{d:trdDay(r.date)})}${gAgeNote(r.date)}`,t('trd.ps.'+r.st),trdIcoP(r,'sm'),trdTone(r)):trdTile(title,'—','','',t('trd.k.none'),trdIco('@globe',[],2,'sm'));\n  const bt=b?trdTile(t('trd.k.next'),nfmt(100*b.k/b.n,0)+'%','',t('trd.b.per',{a:trdDay(b.from),b:trdDay(b.to)}),t('trd.k.'+trdVerdict(b),{k:b.k,n:b.n}),trdIco(TRD_ICO.b_px,[],2,'sm')):trdTile(t('trd.k.next'),'—','','',t('trd.k.none'),trdIco(TRD_ICO.b_px,[],2,'sm'));\n  return `<section class=\"kpis gkpis\">${ft(t('trd.k.in'),inU,'pos')}${ft(t('trd.k.out'),outU,'neg')}${ft(t('trd.k.fade'),fade,'neu')}${pt(t('trd.k.pup'),pU)}${pt(t('trd.k.pdn'),pD)}${bt}</section>`;\n}\n/* v96: kafle krypto — fundusze ETF mają jeszcze krótką historię, więc tytuły mówią o tygodniu, nie o „zwykłym poziomie”; stan widać pod kwotą */\nfunction trdKpisC(F,P){\n  const E=F.filter(r=>r.id.slice(0,4)==='etf_'&&r.m==='flow'&&trdNum(r.w)&&!['gap','stale'].includes(r.st));\n  const eIn=trdPick(E,r=>r.w>0,r=>r.w),eOut=trdPick(E,r=>r.w<0,r=>-r.w);\n  const one=id=>F.find(r=>r.id===id&&trdNum(r.w))||null,stab=one('stab'),cmb=one('cm_btc');\n  const CR=P.filter(r=>r.g==='cr'&&trdNum(r.w)),pU=trdPick(CR,r=>r.w>0,r=>r.w),pD=trdPick(CR,r=>r.w<0,r=>-r.w);\n  const none=(title,key,ic)=>trdTile(title,'—','',t(key),'',trdIco(ic,[],2,'sm'));\n  const line=r=>[escH(t('trd.s.'+r.id)),(r.cur!=='USD'&&trdNum(r.wu)?'≈ '+trdAmt(r.wu,'USD'):''),trdWin(r)+gAgeNote(r.date),(trdNum(r.base)?t('trd.n.base',{v:trdAmt(r.base,r.cur)}):'')].filter(Boolean).join(' · ');\n  const ft=(title,r,tone,key,ic)=>r?trdTile(title,trdAmt(r.w,r.cur),tone,line(r),trdSn(r),trdIcoF(r,'sm'),trdTone(r)):none(title,key,ic);\n  const pt=(title,r,tone,key)=>r?trdTile(title,fPct(r.w,2),trdTone(r),`${escH(r.id)} · ${t('trd.n.pw7',{d:trdDay(r.date)})}${gAgeNote(r.date)}`,t('trd.ps.'+r.st),trdIcoP(r,'sm'),trdTone(r)):none(title,CR.length?key:'trd.kc.none','@coin');\n  const ek=k=>E.length?k:'trd.kc.none';   /* brak danych ≠ „nikt nie wpłacił” */\n  return `<section class=\"kpis gkpis\">${ft(t('trd.kc.in'),eIn,'pos',ek('trd.kc.noin'),'@etf')}${ft(t('trd.kc.out'),eOut,'neg',ek('trd.kc.noout'),'@etf')}`+\n    `${ft(t('trd.kc.stab'),stab,stab?trdTone(stab):'','trd.kc.none','$USDT $USDC')}${ft(t('trd.kc.exch'),cmb,cmb?trdTone(cmb):'','trd.kc.none','$BTC')}`+\n    `${pt(t('trd.kc.pup'),pU,'pos','trd.kc.nopup')}${pt(t('trd.kc.pdn'),pD,'neg','trd.kc.nopdn')}</section>`;\n}\nfunction trdBase(B){\n  if(!B.length)return '';\n  const card=b=>{const ci=Array.isArray(b.ci)?b.ci:[];\n    return `<div class=\"etfk trk\">${trdIco(TRD_ICO['b_'+b.id]||'@globe',[],4)}<span>${escH(t('trd.b.'+b.id))}</span><b>${nfmt(100*b.k/b.n,0)}%</b><small class=\"mtxt\">${t('trd.b.kn',{k:b.k,n:b.n})}`+\n      (['px','fe','ob'].includes(b.id)&&trdNum(b.weeks)?' · '+t('trd.b.wk',{w:b.weeks}):'')+` · ${t('trd.b.per',{a:trdDay(b.from),b:trdDay(b.to)})}<br>`+\n      `${t('trd.b.ci',{lo:trdNum(ci[0])?nfmt(ci[0],0):'—',hi:trdNum(ci[1])?nfmt(ci[1],0):'—'})}<br>${t('trd.b.v.'+trdVerdict(b))}${['px','fe','ob'].includes(b.id)?' '+t('trd.b.pxnote'):''}</small></div>`;};\n  const any=B.some(b=>trdVerdict(b)!=='coin'),   /* wniosek zależy od liczb (w obie strony), nie jest wpisany na stałe */\n        flow=B.some(b=>b.id!=='px'&&trdVerdict(b)==='more');   /* v95.2: zdanie „przepływy to nie ceny” tylko, gdy przepływy częściej trwały dalej */\n  return `<section class=\"panel pcard\"><h2>${t('trd.b.t')}</h2><p class=\"pnote\">${t('trd.b.sub')}</p><div class=\"etfkpis\">${B.map(card).join('')}</div><p class=\"pnote\"><b>${t(flow?'trd.b.concl3':any?'trd.b.concl2':'trd.b.concl')}</b></p></section>`;\n}\nfunction trdMethod(){return `<details class=\"etfd\" id=\"trd-method\"><summary>${t('trd.m.t')}</summary>`+['1','2','3','4','5','6'].map(i=>`<p class=\"pnote\">${t('trd.m.'+i)}</p>`).join('')+`</details>`;}\n/* v120: sygnały dzienne — co mówią dane z ostatniego dnia o następnej sesji (klucze d, bd, dv, dsince w data/trendy.json).\n   Bez klucza `d` blok się nie pojawia i strona wygląda jak dotąd. Kolor tylko przy potwierdzonej przewadze w historii;\n   „anti” (historia częściej odwrotnie) to tylko odznaka — nigdy nie odwraca strony. Brak liczby = null = „—”, nigdy 0. */\nconst TRD_DST=['buy','sell','obs','x','quiet','stale','short','nodata'];            /* stany karty; od „x” — kolejność w „Bez sygnału dziś” */\nconst TRD_DRULES=[['eq','f'],['eq','p'],['eq','fp'],['bd','f'],['pm','f'],['pm','p'],['pm','fp']];   /* 7 linii zbiorczych — zawsze wszystkie */\nconst TRD_DRULESC=[['cr','p']];   /* v123: linie krypto (faza 1: sam ruch ceny); faza 2 dopisze cr·f / cr·fp */\nconst TRD_DFAM=['eq','bd','pm'],TRD_DRL=['f','p','fp','x','none'],TRD_DVD=['edge','anti','none','short'],TRD_DOB={in_eq:1,tw:1,hk:1};\nconst trdIso=s=>typeof s==='string'&&/^\\d{4}-\\d{2}-\\d{2}$/.test(s);\nconst trdDn=v=>trdNum(v)?v:null;                                                    /* liczba albo null — brak nie jest zerem */\n/* jeden wiersz `d`: sprawdzenie pól (zły wiersz = pominięty, nie „0”), brakujące liczby → null; strona musi zgadzać się ze stanem i kierunkiem */\nfunction trdDRow(r){\n  if(!r||typeof r!=='object'||typeof r.id!=='string'||!/^[A-Za-z_]{1,20}$/.test(r.id))return null;\n  if(!(TRD_DFAM.includes(r.fam)||r.fam==='cr')||!TRD_DRL.includes(r.rule)||!TRD_DST.includes(r.st)||!trdIso(r.date))return null;\n  if(!['buy','sell','none'].includes(r.side)||![-1,0,1].includes(r.dir)||!Number.isInteger(r.str)||r.str<0||r.str>3)return null;\n  if(!(r.vd==null||TRD_DVD.includes(r.vd)))return null;\n  if(r.st==='buy'&&(r.side!=='buy'||r.dir!==1))return null;\n  if(r.st==='sell'&&(r.side!=='sell'||r.dir!==-1))return null;\n  if(r.st==='obs'&&r.side!==(r.dir>0?'buy':r.dir<0?'sell':''))return null;\n  if(!['buy','sell','obs'].includes(r.st)&&r.side!=='none')return null;\n  return {id:r.id,fam:r.fam,grp:typeof r.grp==='string'&&/^fe_[a-z]{2,10}$/.test(r.grp)?r.grp:null,iss:typeof r.iss==='string'&&TRD_ISS[r.iss]?r.iss:null,\n    sym:typeof r.sym==='string'&&/^[A-Z]{2,5}$/.test(r.sym)?r.sym:null,date:r.date,nx:trdIso(r.nx)?r.nx:null,live:r.live===true,\n    f:trdDn(r.f),cur:typeof r.cur==='string'&&/^[A-Z]{2,4}$/.test(r.cur)?r.cur:null,fu:trdDn(r.fu),zf:trdDn(r.zf),r:trdDn(r.r),zp:trdDn(r.zp),\n    rule:r.rule,dir:r.dir,side:r.side,str:r.str,st:r.st,vd:r.vd==null?null:r.vd,ik:trdDn(r.ik),in:trdDn(r.in)};\n}\n/* nazwa i ikona rynku: kraj z listy przepływów (flaga), grupa funduszy (nazwa grupy bez nawiasu + ticker, flaga/glif + znaczek wydawcy),\n   albo rynek z listy cen (flaga). s = nazwa do sortowania i do kafli; h = HTML do karty. */\nfunction trdDName(r,cls){\n  if(r.fam==='cr')return {s:r.id,h:escH(r.id),ic:trdIcoP({g:'cr',id:r.id},cls)};   /* v123: symbol i logo monety, jak w tygodniu */\n  if(TRD_DOB[r.id]){const n=String(t('trd.s.'+r.id));return {s:n,h:escH(n),ic:trdIcoF({id:r.id},cls)};}\n  if(r.grp){const n=String(t('trd.s.'+r.grp)).replace(/\\s*\\([A-Z0-9, ]+\\)\\s*$/,'');\n    return {s:n+(r.sym?' ('+r.sym+')':''),h:escH(n)+(r.sym?` <small>${escH(r.sym)}</small>`:''),ic:trdIco(TRD_ICO[r.grp]||'@etf',TRD_ISS[r.iss]||[],0,cls)};}\n  const n=String(t('trd.px.'+r.id));return {s:n,h:escH(n),ic:trdIcoP({g:'eq',id:r.id},cls)};\n}\n/* pierwsza linia karty — powody słowami: przepływ dnia, ruch ceny dnia, data danych → następna sesja (+ wiek danych).\n   Czy wejście „strzeliło” (≥ 1 rozrzut), bierzemy z reguły dnia `rule`, a nie z liczby zf/zp: serwer liczy regułę z odchyleń\n   przed zaokrągleniem i dopiero potem zaokrągla je do 2 miejsc — 0,996 przychodzi jako 1.0, choć reguła mówi „spokojnie”.\n   Tak samo „dużo/mocno” (≥ 2): tylko gdy siła dnia ma punkt za ≥ 2 (reguła f/p: siła 2, reguła fp: siła 3); przy sprzecznych (x,\n   siła 0) — z samej liczby. Obligacje: cena nie wchodzi do reguły, więc zdanie o cenie jest tylko opisem liczby zp.\n   Brak z przy obecnej liczbie (mniej niż 40 porównywalnych dni albo same zera w tle) → „{liczba} — brak porównania z historią”;\n   „brak danych z tego dnia” tylko wtedy, gdy nie ma samej liczby. */\nfunction trdDWhy(r){\n  const L=[],ob=!!TRD_DOB[r.id],fund=ob||!!r.grp,R=r.rule,bdF=r.fam==='bd';\n  const two=R==='fp'?r.str>=3:(R==='f'||R==='p')?r.str>=2:true;                    /* czy siła dnia zawiera punkt „największe |z| ≥ 2” */\n  const big=z=>two&&Math.abs(z)>=2;\n  const v=trdNum(r.f)?trdAmt(r.f,r.cur||'USD')+(r.cur&&r.cur!=='USD'&&trdNum(r.fu)?' · '+t('trd.d.usd',{v:trdAmt(r.fu,'USD')}):''):'—';\n  const fF=['f','fp','x'].includes(R)&&trdNum(r.zf);                                 /* przepływ strzelił wg reguły dnia */\n  if(fF){const up=r.zf>0,w=big(r.zf);\n    L.push(t(ob?(up?'trd.d.r.ob.in':'trd.d.r.ob.out'):(up?'trd.d.r.f.in':'trd.d.r.f.out'),{w:t(ob?(w?'trd.d.sw2':'trd.d.sw1'):(w?'trd.d.w2':'trd.d.w1')),v}));}\n  else if(trdNum(r.zf))L.push(t('trd.d.r.f.q')+(trdNum(r.f)?' ('+v+')':''));\n  else if(fund)L.push(trdNum(r.f)?t('trd.d.r.f.nz',{v}):t('trd.d.r.f.na'));         /* rynki tylko z ceną nie mają przepływu — bez zdania o braku */\n  const bd=bdF?' '+t('trd.d.r.p.bd'):'',p=trdNum(r.r)?fPct(r.r,2):'—';\n  const pF=trdNum(r.zp)&&(bdF?Math.abs(r.zp)>=1:['p','fp','x'].includes(R));        /* cena strzeliła wg reguły (obligacje: tylko opis liczby) */\n  if(pF)L.push(t(r.zp>0?'trd.d.r.p.up':'trd.d.r.p.dn',{w:t((bdF?Math.abs(r.zp)>=2:big(r.zp))?'trd.d.pw2':'trd.d.pw1'),p})+bd);\n  else if(trdNum(r.zp))L.push(t('trd.d.r.p.q')+(trdNum(r.r)?' ('+p+')':'')+bd);\n  else L.push(trdNum(r.r)?t('trd.d.r.p.nz',{p})+bd:t('trd.d.r.p.na'));\n  L.push((r.fam==='cr'?t('trd.dc.nx',{d:trdDay(r.date),nx:r.nx?trdDay(r.nx):'—'}):t('trd.d.nx',{d:trdDay(r.date),nx:r.nx?trdDay(r.nx):'—'}))+gAgeNote(r.date));   /* v123: krypto — doba UTC zamiast sesji */\n  return L.join(' · ');\n}\nconst trdDBadge=(vd,tone,days)=>`<i class=\"tg${tone?' '+tone:''}\">${vd==='short'?t('trd.d.v.short',{days:trdNum(days)?days:'—'}):t('trd.d.v.'+vd)}</i>`;\nconst trdDN1=v=>trdNum(v)?nfmt(v,1):'—';\n/* druga linia karty po stronie kupna/sprzedaży: skuteczność linii (rodzina, reguła) w historii + odznaka + własne k/n rynku (bez oceny) */\nfunction trdDEv(r,BD){\n  const b=BD.find(x=>x.fam===r.fam&&x.rule===r.rule)||null,P=[],vd=r.vd||(b?b.vd:'none');\n  if(b&&b.n>0){const ci=Array.isArray(b.ci)?b.ci:[];\n    P.push(t('trd.d.ev',{rule:t('trd.d.r.'+r.rule),fam:t('trd.d.fam.'+r.fam),p:nfmt(100*b.k/b.n,1),k:b.k,n:b.n,days:trdNum(b.days)?b.days:'—',lo:trdDN1(ci[0]),hi:trdDN1(ci[1])}));}\n  P.push(trdDBadge(vd,vd==='edge'?(r.side==='sell'?'neg':'pos'):vd==='anti'?'neu':'',b?b.days:null));\n  P.push(trdNum(r.in)&&r.in>0?t('trd.d.own',{k:trdNum(r.ik)?r.ik:'—',n:r.in}):t('trd.d.own0'));\n  return P.join(' · ');\n}\n/* karta rynku (4 dzieci jak karty tygodnia: ikona · nazwa · znaczek+kropki+stan · opis): kolor tylko buy/sell (potwierdzona przewaga), reszta szara */\nfunction trdDCard(r,BD){\n  const nm=trdDName(r),S=r.st,ev=['buy','sell','obs'].includes(S);\n  const glyph=r.side==='buy'?'▲':r.side==='sell'?'▼':'•',cls=S==='buy'?'pos':S==='sell'?'neg':'na';\n  const dots=ev?' '+'●'.repeat(r.str)+'○'.repeat(3-r.str):'';\n  const stTxt=String(t(S==='obs'?(r.side==='buy'?'trd.d.st.obs.up':'trd.d.st.obs.dn'):'trd.d.st.'+S)).replace(/^[▲▼•]\\s*/,'');   /* znaczek już stoi wyżej */\n  const l2=ev?trdDEv(r,BD):r.fam==='cr'&&S==='stale'?t('trd.dc.why.stale',{d:trdDay(r.date),nx:r.nx?trdDay(r.nx):'—'}):t('trd.d.why.'+S,{d:trdDay(r.date),nx:r.nx?trdDay(r.nx):'—'});   /* v123: krypto — minęła doba UTC */\n  return `<div class=\"etfk trk\">${nm.ic}<span>${nm.h}</span><b class=\"${cls}\">${glyph}${dots}${ev?`<i class=\"sr\">${escH(t('trd.d.s',{s:r.str}))}</i>`:''}<small>${escH(stTxt)}</small></b>`+\n    `<small class=\"mtxt\">${trdDWhy(r)}<br>${l2}</small></div>`;\n}\n/* kolejność na listach: najpierw potwierdzona przewaga, potem siła dnia, potem nazwa — nigdy według wielkości odchylenia */\nconst trdDSort=A=>A.slice().sort((a,b)=>((b.vd==='edge')-(a.vd==='edge'))||(b.str-a.str)||a.nm.localeCompare(b.nm));\n/* nieaktualne karty (stan „stale”) z kierunkiem dir — trafiają do „Bez sygnału dziś”, ale pusta strona musi o nich wspomnieć */\nconst trdDStale=(R,dir)=>R.filter(r=>r.st==='stale'&&r.dir===dir).length;\n/* 7 linii zbiorczych (rodzina × reguła) — zawsze wszystkie, także złe; „—” zamiast procentu, gdy za mało historii albo bez par */\nfunction trdDPool(BD,V){   /* v123: V = {since} w widoku krypto (linie TRD_DRULESC, teksty trd.dc.*, id …c); bez V — świat jak dotąd */\n  if(!BD.length)return '';\n  const card=b=>{const ci=Array.isArray(b.ci)?b.ci:[],sh=b.vd==='short'||!(b.n>0);\n    return `<div class=\"etfk trk\">${trdIco('@globe',[],4)}<span>${escH(t('trd.d.b.name',{fam:t('trd.d.fam.'+b.fam),rule:t('trd.d.r.'+b.rule)}))}</span>`+\n      `<b${sh?' class=\"na\"':''}>${sh?'—':nfmt(100*b.k/b.n,1)+'%'}</b><small class=\"mtxt\">${t('trd.b.kn',{k:b.k,n:b.n})} · ${t('trd.d.b.days',{d:trdNum(b.days)?b.days:'—'})}`+\n      ` · ${t('trd.d.b.per',{a:trdIso(b.from)?trdDay(b.from):'—',b:trdIso(b.to)?trdDay(b.to):'—'})}<br>${t('trd.b.ci',{lo:trdDN1(ci[0]),hi:trdDN1(ci[1])})}<br>`+\n      `${t('trd.d.b.halves',{a:trdDN1(b.h1),b:trdDN1(b.h2)})} · ${t('trd.d.b.oos',{k:trdNum(b.lk)?b.lk:'—',n:trdNum(b.ln)?b.ln:'—'})}<br>`+\n      (b.vd==='short'?`<i class=\"tg\">${t(V?'trd.dc.b.short':'trd.d.b.short',{d:trdNum(b.days)?b.days:'—',need:trdNum(b.need)?b.need:'—'})}</i>`:trdDBadge(b.vd,b.vd==='edge'?'pos':b.vd==='anti'?'neu':'',b.days))+`</small></div>`;};\n  const S=(V?TRD_DRULESC:TRD_DRULES).map(p=>BD.find(b=>b.fam===p[0]&&b.rule===p[1])).filter(Boolean);\n  return `<details class=\"etfd\" id=\"trd-dbd${V?'c':''}\"><summary>${t(V?'trd.dc.b.t':'trd.d.b.t')}</summary><p class=\"pnote\">${t(V?'trd.dc.b.sub':'trd.d.b.sub')}</p><div class=\"etfkpis\">${S.map(card).join('')}</div><p class=\"pnote\">${t(V?'trd.dc.b.note':'trd.d.b.note')}</p></details>`;\n}\n/* 4 kafle: strona kupna · strona sprzedaży · bez sygnału · reguły z przewagą („0 z 7” to wynik, nie brak; „—” gdy nie znamy wszystkich\n   7 linii, a żadna ze znanych nie ma przewagi). Pusta strona: „dziś nikt aktualny · nieaktualnych: n”, jeśli nieaktualne karty wskazywały w tę stronę. */\nfunction trdDKpis(R,BD,D,V){   /* v123: V = {since} w widoku krypto — data „od wdrożenia” z linii krypto i „{e} z {n}” linii krypto */\n  const buy=trdDSort(R.filter(r=>r.side==='buy')),sell=trdDSort(R.filter(r=>r.side==='sell'));\n  const eB=buy.filter(r=>r.vd==='edge').length,eS=sell.filter(r=>r.vd==='edge').length;\n  const cnt=k=>R.filter(r=>r.st===k).length,q=cnt('quiet'),x=cnt('x'),s=cnt('stale'),o=cnt('short')+cnt('nodata');\n  const names=(A,ns)=>A.length?A.slice(0,3).map(r=>escH(r.nm)).join(' · '):ns?t('trd.d.k.emptyst',{n:ns}):t('trd.d.k.empty');\n  const side=(title,A,e,tone)=>trdTile(title,String(A.length),e>0?tone:'',names(A,trdDStale(R,tone==='pos'?1:-1)),e>0?t('trd.d.k.edge',{e}):t('trd.d.k.noedge'),A.length?trdDName(A[0],'sm').ic:trdIco('@globe',[],2,'sm'),e>0?tone:'');\n  const e=BD.filter(b=>b.vd==='edge').length,lk=BD.reduce((a,b)=>a+(trdNum(b.lk)?b.lk:0),0),ln=BD.reduce((a,b)=>a+(trdNum(b.ln)?b.ln:0),0),ds=V?(trdIso(V.since)?trdDay(V.since):'—'):trdIso(D.dsince)?trdDay(D.dsince):'—';\n  return `<section class=\"kpis gkpis\">${side(t('trd.d.k.buy'),buy,eB,'pos')}${side(t('trd.d.k.sell'),sell,eS,'neg')}`+\n    trdTile(t('trd.d.k.none'),String(q+x+s+o),'',t('trd.d.k.nline',{q,x,s,o}),'',trdIco('@globe',[],2,'sm'))+\n    trdTile(t('trd.d.k.rules'),BD.length===(V?TRD_DRULESC:TRD_DRULES).length||e>0?(V?t('trd.dc.k.of',{e,n:TRD_DRULESC.length}):t('trd.d.k.of',{e})):'—','',ln>0?t('trd.d.k.oos',{d:ds,k:lk,n:ln}):t('trd.d.k.oos0',{d:ds}),t('trd.d.k.hist'),trdIco(TRD_ICO.b_px,[],2,'sm'),'')+`</section>`;\n}\n/* v123: widok krypto — ta sama sekcja dzienna dla 10 kryptowalut: wiersze `d` z fam „cr” i linie `bd` tylko z TRD_DRULESC.\n   '' bez wierszy krypto (stary plik albo brak cen krypto) — wtedy trdDaily pokazuje dotychczasową notę. Kafle, listy i „Bez sygnału dziś”\n   liczą tylko wiersze krypto; wersja reguły (v) i data wdrożenia (since) pochodzą z linii krypto, niezależnie od dv/dsince świata.\n   Kolor nadal tylko przy potwierdzonej przewadze; brak liczby = „—”, nigdy 0. */\nfunction trdDailyC(D){\n  const R=D.d.filter(r=>r&&r.fam==='cr').map(trdDRow).filter(Boolean);\n  if(!R.length)return '';\n  R.forEach(r=>{r.nm=trdDName(r).s;});\n  const seen={},BD=(Array.isArray(D.bd)?D.bd:[]).filter(b=>{if(!(b&&typeof b==='object'&&TRD_DRULESC.some(p=>p[0]===b.fam&&p[1]===b.rule)&&trdNum(b.k)&&trdNum(b.n)&&b.k>=0&&b.n>=b.k&&TRD_DVD.includes(b.vd)))return false;\n    const k=b.fam+'.'+b.rule;if(seen[k])return false;seen[k]=1;return true;});   /* ta sama kontrola co w świecie, tylko linie krypto; duplikat — pierwszy wygrywa */\n  const L=BD[0]||{},V={since:trdIso(L.since)?L.since:null};\n  const live=R.filter(r=>r.live),dd=(live.length?live:R).map(r=>r.date).sort().pop()||null,dTxt=dd?trdDay(dd):'—';\n  /* „reguła krypto nie ma przewagi” tylko, gdy znamy linię krypto i ani linia, ani wiersz nie mówi „edge” */\n  const noEdge=BD.length===TRD_DRULESC.length&&!BD.some(b=>b.vd==='edge')&&!R.some(r=>r.vd==='edge');\n  const buy=trdDSort(R.filter(r=>r.side==='buy')),sell=trdDSort(R.filter(r=>r.side==='sell'));\n  const rest=TRD_DST.slice(3).flatMap(k=>R.filter(r=>r.st===k).sort((a,b)=>a.nm.localeCompare(b.nm)));\n  const ns=k=>trdDStale(R,k==='buy'?1:-1);\n  const lst=(k,A,tone,g)=>`<h3 class=\"mtxt\"><i class=\"tg ${tone}\">${g}</i><b>${t('trd.d.'+k+'.t')}</b></h3><p class=\"pnote\">${t('trd.dc.'+k+'.sub')}</p>`+\n    (A.length?`<div class=\"etfkpis\">${A.map(r=>trdDCard(r,BD)).join('')}</div>`:`<p class=\"pnote\">${ns(k)?t('trd.d.empty.st',{n:ns(k),s:t('trd.d.k.none')}):t('trd.d.empty')}</p>`);\n  const lg=`<p class=\"pnote trd-dlg\"><i class=\"tdot pos\"></i><i class=\"tdot neg\"></i><i class=\"tdot neu\"></i><i class=\"tdot\"></i> ${t('trd.d.lg')}</p>`;\n  return `<section class=\"panel pcard trd-d\" id=\"trd-dailyc\"><h2>${t('trd.dc.t',{d:dTxt})}</h2><p class=\"pnote\">${t('trd.dc.sub')}</p><p class=\"pnote\"><b>${t('trd.d.disc')}</b></p>${lg}`+\n    trdDKpis(R,BD,D,V)+(noEdge?`<p class=\"pnote\">${t('trd.dc.none.all')}</p>`:'')+lst('buy',buy,'pos','▲')+lst('sell',sell,'neg','▼')+\n    (rest.length?`<details class=\"etfd\" id=\"trd-drestc\"><summary>${t('trd.d.none.t',{n:rest.length})}</summary><div class=\"etfkpis\">${rest.map(r=>trdDCard(r,BD)).join('')}</div></details>`:'')+\n    trdDPool(BD,V)+\n    `<details class=\"etfd\" id=\"trd-dmethodc\"><summary>${t('trd.dc.m.t',{v:Number.isInteger(L.v)?L.v:'—'})}</summary>${['trd.dc.m.1','trd.dc.m.2','trd.dc.m.3','trd.dc.m.4','trd.d.m.5','trd.dc.m.5','trd.dc.m.6','trd.d.m.7'].map(k=>`<p class=\"pnote\">${t(k)}</p>`).join('')}</details></section>`;\n}\n/* cały blok dzienny; '' bez klucza `d` (strona bez zmian); w widoku krypto — sekcja krypto (trdDailyC), a bez wierszy krypto tylko nota i ostrzeżenie */\nfunction trdDaily(D,cr){\n  if(!D||!Array.isArray(D.d))return '';\n  if(!cr&&D.d.length&&D.d.every(r=>r&&r.fam==='cr'))return '';   /* v123: same wiersze krypto = świat niepoliczony (jak null) */\n  const R=D.d.map(trdDRow).filter(r=>r&&r.fam!=='cr');R.forEach(r=>{r.nm=trdDName(r).s;});\n  const seen={},BD=(Array.isArray(D.bd)?D.bd:[]).filter(b=>{if(!(b&&typeof b==='object'&&TRD_DRULES.some(p=>p[0]===b.fam&&p[1]===b.rule)&&trdNum(b.k)&&trdNum(b.n)&&b.k>=0&&b.n>=b.k&&TRD_DVD.includes(b.vd)))return false;\n    const k=b.fam+'.'+b.rule;if(seen[k])return false;seen[k]=1;return true;});\n  const live=R.filter(r=>r.live),dd=(live.length?live:R).map(r=>r.date).sort().pop()||null,dTxt=dd?trdDay(dd):'—';\n  const disc=`<p class=\"pnote\"><b>${t('trd.d.disc')}</b></p>`;\n  if(cr)return trdDailyC(D)||`<section class=\"panel pcard trd-d\"><h2>${t('trd.d.t',{d:dTxt})}</h2><p class=\"pnote\">${t('trd.d.nocr',{v:t('trd.v.global')})}</p>${disc}</section>`;\n  const buy=trdDSort(R.filter(r=>r.side==='buy')),sell=trdDSort(R.filter(r=>r.side==='sell'));\n  /* „żadna z 7 reguł nie ma przewagi” tylko, gdy znamy wszystkie 7 linii i ani linia, ani wiersz nie mówi „edge” (bez `bd` nie wiemy nic) */\n  const noEdge=BD.length===TRD_DRULES.length&&!BD.some(b=>b.vd==='edge')&&!R.some(r=>r.vd==='edge');\n  const rest=TRD_DST.slice(3).flatMap(k=>R.filter(r=>r.st===k).sort((a,b)=>a.nm.localeCompare(b.nm)));\n  const ns=k=>trdDStale(R,k==='buy'?1:-1);                                         /* nieaktualne karty w kierunku tej strony */\n  const lst=(k,A,tone,g)=>`<h3 class=\"mtxt\"><i class=\"tg ${tone}\">${g}</i><b>${t('trd.d.'+k+'.t')}</b></h3><p class=\"pnote\">${t('trd.d.'+k+'.sub')}</p>`+\n    (A.length?`<div class=\"etfkpis\">${A.map(r=>trdDCard(r,BD)).join('')}</div>`:`<p class=\"pnote\">${ns(k)?t('trd.d.empty.st',{n:ns(k),s:t('trd.d.k.none')}):t('trd.d.empty')}</p>`);\n  const lg=`<p class=\"pnote trd-dlg\"><i class=\"tdot pos\"></i><i class=\"tdot neg\"></i><i class=\"tdot neu\"></i><i class=\"tdot\"></i> ${t('trd.d.lg')}</p>`;   /* kropki w kolejności zdania: zielony, czerwony, żółty („odwrotnie”), szary */\n  return `<section class=\"panel pcard trd-d\" id=\"trd-daily\"><h2>${t('trd.d.t',{d:dTxt})}</h2><p class=\"pnote\">${t('trd.d.sub')}</p>${disc}${lg}`+\n    trdDKpis(R,BD,D)+(noEdge?`<p class=\"pnote\">${t('trd.d.none.all')}</p>`:'')+lst('buy',buy,'pos','▲')+lst('sell',sell,'neg','▼')+\n    (rest.length?`<details class=\"etfd\" id=\"trd-drest\"><summary>${t('trd.d.none.t',{n:rest.length})}</summary><div class=\"etfkpis\">${rest.map(r=>trdDCard(r,BD)).join('')}</div></details>`:'')+\n    trdDPool(BD)+\n    `<details class=\"etfd\" id=\"trd-dmethod\"><summary>${t('trd.d.m.t',{v:Number.isInteger(D.dv)?D.dv:'—'})}</summary>${['1','2','3','4','5','6','7'].map(i=>`<p class=\"pnote\">${t('trd.d.m.'+i)}</p>`).join('')}</details></section>`;\n}\nfunction renderTrendy(){\n  const w=$('#trendy');if(!w)return;\n  const D=TRD.data,old=D&&Date.now()-Date.parse(D.at)>2*3600*1000,cr=trdIsC(),v=cr?'crypto':'global';\n  /* otwarte bloki zostają otwarte po odświeżeniu i po powrocie do widoku (v96: zapamiętane osobno dla „global” i „krypto”) */\n  if(TRD.shown)TRD.open[TRD.shown]=[...w.querySelectorAll('details[open]')].map(d=>d.id).filter(Boolean);\n  /* v96: przełącznik widoków (.seg, nie druga grupa .tabs — strzałki zakładek zostają dla zakładek); obsługa kliknięcia — jeden słuchacz przy zakładkach */\n  const seg=`<div class=\"seg trd-seg\" id=\"trd-view\" role=\"group\" aria-label=\"${escH(t('trd.v.aria'))}\">`+\n    `<button type=\"button\" data-v=\"global\" aria-pressed=\"${cr?'false':'true'}\">${trdIco('@globe',[],1,'sm')}${t('trd.v.global')}</button>`+\n    `<button type=\"button\" data-v=\"crypto\" aria-pressed=\"${cr?'true':'false'}\">${trdIco('$BTC',[],1,'sm')}${t('trd.v.crypto')}</button></div>`;\n  const head=`<div class=\"head-row\"><div><h1>${t(cr?'trd.h1c':'trd.h1')}</h1><div class=\"sub\"><span class=\"live ${!D?'off':old?'wait':'on'}\" id=\"trd-live\"><i></i>${!D?t('trd.wait'):old?t('trd.old',{t:engDate(D.at)}):t('inst.file',{t:engDate(D.at)})}</span><span class=\"gsub\">${t(cr?'trd.subc':'trd.subd')}</span></div></div>${seg}</div>`;   /* v120.1: global = sygnały dnia */\n  const lg=`<p class=\"pnote trd-lg\"><span><i class=\"tdot pos\"></i>${t('trd.lg.pos')}</span><span><i class=\"tdot neg\"></i>${t('trd.lg.neg')}</span><span><i class=\"tdot neu\"></i>${t('trd.lg.neu')}</span><span><i class=\"tdot\"></i>${t('trd.lg.na')}</span></p>`;\n  const disc=`<section class=\"panel pcard\"><p class=\"pnote trd-lead\">${t(cr?'trd.v.ci':'trd.v.gi')}</p><p class=\"pnote\"><b>${t(cr?'trd.discc':'trd.disc')}</b></p>${lg}</section>`;\n  if(!D){w.innerHTML=head+`<section class=\"panel pcard\"><p class=\"pnote\">${t('trd.nodata')}</p><p class=\"pnote\"><b>${t(cr?'trd.discc':'trd.disc')}</b></p>${trdMethod()}</section>`;}\n  else{\n    const F=D.f.filter(r=>r&&typeof r.id==='string'&&/^[a-z_]{1,20}$/.test(r.id)&&TRD_ORD.includes(r.st)&&TRD_M.includes(r.m)&&typeof r.cur==='string'&&/^[A-Z]{2,4}$/.test(r.cur)&&trdNum(r.sz)),\n          P=D.p.filter(r=>r&&typeof r.id==='string'&&(/^[A-Z]{2,5}$/.test(r.id)||/^fp_[a-z]{2,8}$/.test(r.id)&&typeof r.sym==='string'&&/^[A-Z]{2,5}$/.test(r.sym))&&TRD_PORD.includes(r.st)),\n          B=(Array.isArray(D.b)?D.b:[]).filter(b=>b&&['th','mx','ob','fe','px'].includes(b.id)&&trdNum(b.k)&&trdNum(b.n)&&b.n>0);\n    const EQ=trdPxSort(P.filter(r=>r.g==='eq')),CR=trdPxSort(P.filter(r=>r.g==='cr')),FP=trdPxSort(P.filter(r=>r.g==='fp'));\n    const grid=(k,A,ic)=>A.length?`<h3 class=\"mtxt\">${ic?trdIco(ic,[],2,'sm'):''}<b>${t(k)}</b></h3><div class=\"etfkpis\">${A.map(trdPx).join('')}</div>`:'';\n    /* v96: stopka bez listy dostawców (są na stronie Źródła) — zostaje czas pliku i ostrzeżenie */\n    const foot=`<section class=\"panel pcard\">${trdMethod()}<p class=\"pfoot\">${t('inst.file',{t:engDate(D.at)})} · ${t('eng.disclaimer')}</p></section>`;\n    const dly=trdDaily(D,cr);w.innerHTML=head+dly+(dly?`<h2 class=\"trd-wk mtxt\">${t('trd.d.wk')}</h2>`:'')+disc+(!cr?\n      trdKpis(F,P,B)+\n      trdPanel('e',F.filter(r=>r.g==='fe'))+   /* v90: fundusze ETF w USA — najszerszy obraz: akcje, sektory, kraje, obligacje, złoto */\n      trdPanel('f',F.filter(r=>['eq','bd','fx'].includes(r.g)))+\n      trdPanel('p',F.filter(r=>r.g==='pos'&&!trdCry(r)))+\n      (EQ.length||FP.length?`<section class=\"panel pcard\"><h2>${t('trd.x.t')}</h2><p class=\"pnote\">${t('trd.x.sub')}</p>`+grid('trd.x.eq',EQ,'@globe')+grid('trd.x.fp',FP,'@gold @silver us')+`</section>`:'')+\n      trdBase(B)\n    :\n      trdKpisC(F,P)+\n      trdPanel('c',F.filter(r=>r.g==='cr'),['short'])+\n      trdPanel('pc',F.filter(r=>r.g==='pos'&&trdCry(r)))+   /* własny klucz: otwarty blok „pozostałe” nie przechodzi między widokami */\n      (CR.length?`<section class=\"panel pcard\"><h2>${t('trd.xc.t')}</h2><p class=\"pnote\">${t('trd.xc.sub')}</p>`+grid('trd.x.cr',CR)+`</section>`:'')+\n      `<section class=\"panel pcard\"><h2>${t('trd.b.t')}</h2><p class=\"pnote\">${t('trd.b.nocr')}</p></section>`)+\n      foot;\n  }\n  TRD.shown=v;\n  (TRD.open[v]||[]).forEach(id=>{const d=w.querySelector('#'+id);if(d)d.open=true;});\n}\n/* v91: fundusze ETF w USA na region mapy GLOBAL — z pliku TRENDÓW (tydzień na tle 4 poprzednich); brak = brak linii, nie zero */\nconst FE_REG={usa:['fe_us'],eur:['fe_eur'],jpn:['fe_jpn','fe_kor'],chn:['fe_chn'],ind:['fe_india'],lat:['fe_bra']};\nfunction feRegion(id){const ids=FE_REG[id];if(!ids||typeof TRD==='undefined'||!TRD.data||!Array.isArray(TRD.data.f))return '';\n  const R=ids.map(k=>TRD.data.f.find(r=>r&&r.id===k&&r.m==='flow'&&trdNum(r.w)&&trdNum(r.sz)&&typeof r.cur==='string'&&/^[A-Z]{2,4}$/.test(r.cur)&&TRD_ORD.includes(r.st))).filter(Boolean);if(!R.length)return '';\n  return `<div class=\"wide\"><dt>${t('fe.reg')}</dt><dd class=\"trd-fr\">${R.map(r=>`${trdIcoF(r)}${escH(t('trd.s.'+r.id))}: <b class=\"${trdTone(r)}\">${trdAmt(r.w,'USD')}</b> · ${trdWin(r)}${gAgeNote(r.date)} · ${trdSt(trdSn(r),trdTone(r))}`).join('<br>')}</dd></div>`;}\n", PROD_FNV = '59fc37c2';
  const oldBlk = () => { assert.equal(fnv(PROD_BLK), PROD_FNV, 'osadzony blok TRENDY produkcji — suma FNV-1a'); return PROD_BLK; };
  /* blok TRENDY z prawdziwym słownikiem języka L (albo tt — np. klucze z polami, jak w testach v96/v120); src — inny blok (stara strona) */
  const make = (L, st, el0, tt, src) => {
    const el = el0 || {innerHTML: '', querySelectorAll() { return []; }, querySelector() { return null; }};
    const F = new Function('LANG', 'LOCALE', html.slice(f0, f1) + '\nreturn {nfmt, sg, fInt, fPct};')(L, LOC);
    const names = ['$', 't', 'st', 'srvJSON', 'escH', 'etfCls', 'gAgeNote', 'fInt', 'sg', 'nfmt', 'fPct', 'zagSes', 'engDate', 'LANG', 'LOCALE', 'I18N',
      'flagImg', 'glyphImg', 'coinImg', 'issBadge', 'issuerOf', 'icoWrap'];
    const vals = [() => el, tt || v96src.tFor(L), st || {mode: 'trendy', trdv: 'crypto'}, () => Promise.resolve(null), v96src.escH, v => v > 0 ? 'pos' : v < 0 ? 'neg' : '', () => '',
      F.fInt, F.sg, F.nfmt, F.fPct, () => 'ses', s => s, L, LOC, v96src.I18N, I.flagImg, I.glyphImg, I.coinImg, I.issBadge, I.issuerOf, I.icoWrap];
    const ret = src ? '\nreturn {TRD, trdApply, renderTrendy, trdDRow, trdDWhy, trdDCard, TRD_DST, TRD_DRL, TRD_DRULESC};'
      : '\nreturn {TRD, trdApply, renderTrendy, trdDRow, TRD_DCAL, TRD_CRL, TRD_CRK, TRD_DRULESC2, TRD_DRULESC, TRD_DST};';
    const f = new Function(...names, (src || blk) + ret)(...vals);
    f.el = el; return f;
  };
  const clone = o => JSON.parse(JSON.stringify(o));
  const rows = f => { const R = clone(CR.rows); if (f) f(R); return R; }, lines = f => { const B = clone(CR.lines); if (f) f(B); return B; };
  const by = (A, k) => A.find(x => x.id === k || (x.fam === 'cr' && x.rule === k && !x.id));
  const world = () => trdV120.data();                                          /* świat bez krypto: 7 wierszy `d`, 7 linii `bd` */
  /* plik v125: świat + 10 kart v1 (V1R) + 10 wierszy v2; `bd` = 7 linii świata, linia v1 (v: 1), 7 linii v2 — jak zapisuje zbieracz (dopisek A1);
     prodFile — plik zbieracza produkcji z tego samego przebiegu: świat + karty v1, `bd` = 7 linii świata + linia v1 */
  const file = (R, B, extra) => { const w = world(); return Object.assign(w, {d: w.d.concat(clone(V1R), R || rows()), bd: w.bd.concat([clone(V1L)], B || lines())}, extra || {}); };
  const prodFile = () => { const w = world(); return Object.assign(w, {d: w.d.concat(clone(V1R)), bd: w.bd.concat([clone(V1L)])}); };
  const sec = trdV123.sec, card = trdV123.card;
  const txt = h => h.replace(/<br>/g, ' ').replace(/<[^>]+>/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&')
    .replace(/[\u00a0\u202f]/g, ' ').replace(/\s+/g, ' ');
  const view = (L, data, st) => { const f = make(L, st); f.trdApply(data); return f.el.innerHTML; };
  const raw = s => /undefined|NaN|\[object/.test(s) || /\btrd\.[a-z0-9_]+\.[a-z0-9_.]+/.test(s);   /* „undefined”, NaN albo surowy klucz słownika */
  return {CR, V1L, V1R, make, clone, rows, lines, by, world, file, prodFile, sec, card, txt, view, raw, blk, fnv, oldBlk, PROD_FNV};
})();

test('v125: EXTRA118 — 10 języków w kolejności, te same 83 klucze trd.dc2.* i te same pola w każdym języku, zaraz po EXTRA117 z linią nakładania; pl i en = tekst specyfikacji (Aneks A z dopiskiem: 5 kluczy „po czasie”); EXTRA120 zaraz po nim; literały i klucze składane bloku v89 w pl i en; bez „kupuj/sprzedawaj” i bez nazw dostawców; żaden klucz dwa razy', () => {
  const a = 'const EXTRA118=', x0 = html.indexOf(a), fl = 'for(const l in EXTRA118)if(I18N[l])Object.assign(I18N[l],EXTRA118[l]);\n';
  const f117 = 'for(const l in EXTRA117)if(I18N[l])Object.assign(I18N[l],EXTRA117[l]);\n', i117 = html.indexOf(f117), x1 = html.indexOf(';\n', x0);
  assert.equal(html.split(a).length, 2, 'jeden słownik EXTRA118'); assert.equal(html.split(fl).length, 2, 'jedna linia nakładania');
  const gap = html.slice(i117 + f117.length, x0); assert.ok(i117 > 0 && gap.startsWith('/* v125:') && gap.split('\n').length === 2, 'zaraz po EXTRA117: jeden wiersz komentarza i słownik');
  assert.equal(html.slice(x1 + 2, x1 + 2 + fl.length), fl, 'linia nakładania zaraz po słowniku');
  const apl = [...html.matchAll(/for\(const l in (EXTRA\d+)\)if\(I18N\[l\]\)Object\.assign\(I18N\[l\],\1\[l\]\);\n/g)].map(m => m[1]);
  assert.ok(apl.indexOf('EXTRA118') === apl.indexOf('EXTRA117') + 1 && apl.indexOf('EXTRA120') === apl.indexOf('EXTRA118') + 1 && apl.indexOf('EXTRA119') === apl.indexOf('EXTRA120') + 1,
    'EXTRA118 po EXTRA117, zaraz po nim EXTRA120 (przegląd 27.09), potem EXTRA119');
  const src = html.slice(x0 + a.length, x1), D = JSON.parse(src), L10 = ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja'];
  assert.deepEqual(Object.keys(D), L10, 'kolejność języków');
  const K = Object.keys(D.pl); assert.equal(K.length, 83, 'liczba kluczy'); assert.ok(K.every(k => k.startsWith('trd.dc2.')), 'tylko trd.dc2.*');
  const ph = s => (s.match(/\{\w+\}/g) || []).sort().join(',');
  for (const l of L10) {
    assert.deepEqual(Object.keys(D[l]), K, 'te same klucze w tej samej kolejności: ' + l);
    for (const k of K) { assert.ok(typeof D[l][k] === 'string' && D[l][k].trim().length > 0, l + ' ' + k); assert.equal(ph(D[l][k]), ph(D.pl[k]), 'pola ' + l + ' ' + k); }
  }
  for (const k of K) assert.equal(src.split('"' + k + '":').length - 1, 10, 'klucz raz w każdym języku: ' + k);
  /* EXTRA120 (przegląd 27.09): zaraz po linii nakładania EXTRA118 — komentarz, słownik, linia nakładania; 6 nowych kluczy trd.dc2.* w 10 językach
     (sprawdzamy tylko własną nazwę i miejsce — nazw innych wydań nie; EXTRA122 bierze v126) */
  const ap = 'const EXTRA120=', p0 = html.indexOf(ap), p1 = html.indexOf(';\n', p0), flp = 'for(const l in EXTRA120)if(I18N[l])Object.assign(I18N[l],EXTRA120[l]);\n';
  const gp = html.slice(x1 + 2 + fl.length, p0);
  assert.ok(html.split(ap).length === 2 && html.split(flp).length === 2 && gp.startsWith('/* v125 po przeglądzie 27.09:') && gp.split('\n').length === 2, 'EXTRA120 zaraz po EXTRA118');
  assert.equal(html.slice(p1 + 2, p1 + 2 + flp.length), flp, 'linia nakładania EXTRA120');
  const srcP = html.slice(p0 + ap.length, p1), DP = JSON.parse(srcP), KP = Object.keys(DP.pl);
  assert.deepEqual(Object.keys(DP), L10, 'EXTRA120: kolejność języków');
  assert.deepEqual(KP, ['trd.dc2.ans.grey', 'trd.dc2.ans.qlate', 'trd.dc2.v.edge', 'trd.dc2.v.veto', 'trd.dc2.lc.no', 'trd.dc2.lc.yes'], 'EXTRA120: klucze');
  for (const l of L10) {
    assert.deepEqual(Object.keys(DP[l]), KP, 'EXTRA120: te same klucze: ' + l);
    for (const k of KP) { assert.ok(typeof DP[l][k] === 'string' && DP[l][k].trim().length > 0 && !(k in D[l]), l + ' ' + k); assert.equal(ph(DP[l][k]), ph(DP.pl[k]), 'pola ' + l + ' ' + k);
      assert.equal(v96src.I18N[l][k], DP[l][k], 'scalony słownik strony: ' + l + ' ' + k); }
  }
  for (const k of KP) assert.equal(srcP.split('"' + k + '":').length - 1, 10, 'klucz raz w każdym języku: ' + k);
  assert.equal(html.split('"trd.dc2.').length - 1, 830 + 60, 'klucze trd.dc2.* tylko w EXTRA118 i EXTRA120 — żaden wcześniejszy klucz nie jest nadpisany');
  /* pl i en jak w specyfikacji (v125/judge2/extra118_pl_en.json = Aneks A, suma FNV-1a 'fc214b73:332954a9'), poza 5 kluczami „po czasie”
     z dopisku SPEC-v125-ADDENDUM: suma tekstu JSON bez tych 5 kluczy = suma Aneksu A bez nich; te 5 (i ans.qlate w EXTRA120) — tekst wprost */
  const {fnv} = trdV125, LATE = ['trd.dc2.why.late', 'trd.dc2.lt', 'trd.dc2.ans.late', 'trd.dc2.mkt.late', 'trd.dc2.m.4'];
  const noLate = o => Object.fromEntries(Object.entries(o).filter(([k]) => !LATE.includes(k)));
  assert.equal(fnv(JSON.stringify(noLate(D.pl))) + ':' + fnv(JSON.stringify(noLate(D.en))), 'd09e53bd:e00574a', 'pl i en = Aneks A (poza 5 kluczami dopisku)');
  assert.equal(D.pl['trd.dc2.why.late'], 'ceny i obroty potrzebne tej karcie (z {d} albo z dni, z którymi ją porównujemy — do 61 dni wstecz) trafiły na stronę albo zostały poprawione dopiero po {u} UTC, tuż przed albo już po starcie mierzonego okna — karta jest tylko opisem, bez strony');
  assert.equal(D.en['trd.dc2.why.late'], 'the prices and turnover this card needs (from {d} or from the days it is compared with — up to 61 days back) reached the site or were corrected only after {u} UTC, just before or after the measured window started — this card is only a description, without a side');
  assert.equal(D.pl['trd.dc2.lt'], 'po {u} UTC, bez głosu: {l} (liczba z tej doby albo dni, z którymi ją porównujemy)');
  assert.equal(D.en['trd.dc2.lt'], 'after {u} UTC, no vote: {l} (the day’s figure or the days it is compared with)');
  assert.equal(D.pl['trd.dc2.ans.late'], 'Po {u} UTC dotarły: {l} (liczba z tej doby albo dni, z którymi ją porównujemy) — na kartach z {d} są bez głosu, bo mierzone okno zaczyna się o {h} UTC.');
  assert.equal(D.en['trd.dc2.mkt.late'], 'stablecoin supply (USDT and USDC) changed by {v}, but this number or the days it is compared with arrived after {u} UTC — no vote');
  assert.ok(D.pl['trd.dc2.m.4'].includes('przepływy na giełdy i stablecoiny tracą głos także wtedy, gdy po {u} UTC dotarły dni, z którymi je porównujemy (do 60 dni wstecz). Gdy po {u} UTC dotrą albo zostaną poprawione ceny i obroty potrzebne karcie — z tej doby albo z dni, z którymi ją porównujemy (do 61 dni wstecz) — karta jest tylko opisem.')
    && !D.pl['trd.dc2.m.4'].includes('gdy spóźnią się same ceny doby'), 'm.4: tło porównania, bez „same ceny doby”');
  assert.equal(DP.pl['trd.dc2.ans.qlate'], 'Ceny i obroty potrzebne kartom z {d} (z tej doby albo z dni, z którymi je porównujemy) dotarły na stronę albo zostały poprawione dopiero po {u} UTC (kart: {n}) — te karty są tylko opisem, bez strony; liczymy je razem z nieaktualnymi.');
  assert.equal(DP.en['trd.dc2.ans.qlate'], 'The prices and turnover needed for the cards from {d} (from that day or from the days they are compared with) reached the site or were corrected only after {u} UTC (cards: {n}) — these cards are only a description, without a side; we count them together with outdated ones.');
  /* „po czasie” we wszystkich 10 językach mówi o dniach porównania (61 / 60 dni wstecz), nie tylko o samej dobie */
  for (const l of L10) { for (const k of ['trd.dc2.why.late', 'trd.dc2.m.4']) assert.ok(D[l][k].includes('61'), l + ' ' + k + ': 61 dni'); assert.ok(D[l]['trd.dc2.m.4'].includes('60'), l + ' m.4: 60 dni'); }
  const L6 = Object.fromEntries(L10.map(l => [l, LATE.concat(['trd.dc2.ans.qlate']).map(k => D[l][k] || DP[l][k])]));
  assert.equal(fnv(JSON.stringify(L6)), 'ae3b07e0', 'teksty „po czasie” (5 kluczy EXTRA118 + ans.qlate) w 10 językach = dopisek SPEC-v125-ADDENDUM (suma FNV-1a)');
  assert.equal(D.pl['trd.dc2.ev1'], '{name} {p}% ({k} z {n})'); assert.equal(D.en['trd.dc2.y1'], '{p}% ({k} of {n})'); assert.equal(D.pl['trd.dc2.n.t.s'], 'agresywna sprzedaż');
  assert.equal(D.pl['trd.dc2.b.lvd.wait'], 'ocena „od wdrożenia” tylko po 100, 200 i 400 dniach z sygnałem (zakres {cll}%) — teraz {d} z {c}');
  /* literały i klucze składane w kodzie — w pl i en */
  const lit = [...new Set([...trdV125.blk.matchAll(/'(trd\.dc2\.[A-Za-z0-9_.]+)'/g)].map(m => m[1]).filter(k => !/[._]$/.test(k)))];
  assert.ok(lit.length >= 40, 'literały trd.dc2.* w bloku: ' + lit.length); for (const k of lit) assert.ok((D.pl[k] || DP.pl[k]) && (D.en[k] || DP.en[k]), 'brak klucza ' + k);
  for (const k of KP) assert.ok(lit.includes(k), 'klucz EXTRA120 używany w kodzie: ' + k);
  const comp = ['n.t.s', 'why.x', 'why.quiet', 'why.stale', 'why.late', 'y1', 'y1.0', 'buy.sub', 'sell.sub', 'st.late', 'w1', 'w2']
    .concat(['p', 't', 'e', 's', 'h', 'n2', 'all'].flatMap(k => ['n.' + k, 'd.' + k]), ['t.buy', 't.sell', 'e.hi', 'e.lo', 's.up', 's.dn', 'h.hi', 'h.lo'].map(k => 'r.' + k));
  for (const k of comp) assert.ok(D.pl['trd.dc2.' + k] && D.en['trd.dc2.' + k], 'klucz składany: trd.dc2.' + k);
  for (const i of [1, 2, 3, 4, 5, 6, 7, 8]) assert.ok(D.pl['trd.dc2.m.' + i] && D.en['trd.dc2.m.' + i], 'metoda ' + i);
  const bad = /kupuj(?![a-ząćęłńóśźż])|sprzedawaj(?![a-ząćęłńóśźż])|warto kupi|okazj|prognoz|gwarant|na pewno|pewny zysk|wzrośnie|spadnie|buy now|must buy|sure profit|will rise|will fall|guarantee|forecast/i;
  for (const l of ['pl', 'en']) for (const k of K) { if (k.startsWith('trd.dc2.m.') || k === 'trd.dc2.b.sub' || k === 'trd.dc2.b.note') continue; assert.doesNotMatch(D[l][k], bad, `${l} ${k}: ${D[l][k]}`); }
  for (const l of ['pl', 'en']) for (const k of KP) assert.doesNotMatch(DP[l][k], bad, `${l} ${k}: ${DP[l][k]}`);
  const prov = /binance|coinbase|coin ?metrics|defillama|hyperliquid|sosovalue|coingecko|ishares|ssga/i;
  for (const l of L10) for (const k of K) assert.doesNotMatch(D[l][k], prov, `dostawca: ${l} ${k}`);
  for (const l of L10) for (const k of KP) assert.doesNotMatch(DP[l][k], prov, `dostawca: ${l} ${k}`);
  /* przepływ netto może być ujemny — nazwa powodu bez „napływu” (de/ru/zh/ja); włoski zwraca się do czytelnika na „ty” jak reszta strony */
  for (const [l, re] of [['de', /Zufluss/], ['ru', /приток/], ['zh', /流入/], ['ja', /への流入(?!出)/]])
    for (const k of ['trd.dc2.n.e', 'trd.dc2.d.e', 'trd.dc2.r.e.hi', 'trd.dc2.r.e.lo', 'trd.dc2.sub', 'trd.dc2.m.2', 'trd.dc2.m.4', 'trd.dc2.m.7']) assert.doesNotMatch(D[l][k], re, l + ' ' + k);
  assert.ok(D.it['trd.dc2.win'].includes('nella tua ora') && !/\bSua\b/.test(JSON.stringify(D.it) + JSON.stringify(DP.it)), 'it: „tua”');
  for (const l of L10) {
    for (const k of K) assert.equal(v96src.I18N[l][k], D[l][k], 'scalony słownik strony: ' + l + ' ' + k);
    const tt = v96src.tFor(l), y = tt('trd.dc2.y1', {p: '44,2', k: 23, n: 52});
    assert.ok(y.includes('44,2') && y.includes('23') && y.includes('52') && !y.includes('{'), l + ': ' + y);
    assert.ok(D[l]['trd.dc2.st.late'].startsWith('• '), l + ': znaczek stanu (usuwany w karcie)');
    if (l !== 'pl' && l !== 'en') assert.notEqual(tt('trd.dc2.ans.none', {n: 5}), v96src.tFor('en')('trd.dc2.ans.none', {n: 5}), l + ' ma własny tekst (nie angielski zapas)');
  }
});

test('v125: widok global — bajt w bajt ten sam HTML z częścią krypto v125 (10 kart v1, 10 wierszy v2, linia v1, 7 linii v2) i bez krypto (pl, en, klucze; także w innej kolejności); wiersz świata ze stanem „late” odrzucony', () => {
  const {make, file, world, clone, CR, V1L} = trdV125;
  for (const L of ['pl', 'en']) {
    const a = make(L, {mode: 'trendy'}), b = make(L, {mode: 'trendy'}), c = make(L, {mode: 'trendy'}); a.trdApply(world()); b.trdApply(file());
    assert.ok(a.el.innerHTML.includes('id="trd-daily"') && !b.el.innerHTML.includes('trd-dailyc') && !b.el.innerHTML.includes(v96src.tFor(L)('trd.dc2.ans.t')), L + ': global bez sekcji i tekstów krypto');
    assert.equal(b.el.innerHTML, a.el.innerHTML, L + ': global bez zmian');
    const w = world(), L2 = clone(CR.lines);
    c.trdApply(Object.assign(w, {d: clone(CR.rows).concat(w.d), bd: L2.slice(0, 3).concat(w.bd.slice(0, 4), [clone(V1L)], L2.slice(3), w.bd.slice(4))}));
    assert.equal(c.el.innerHTML, a.el.innerHTML, L + ': wiersze krypto przed światem, linie przemieszane — świat bez zmian');
  }
  const k0 = trdV96.make({mode: 'trendy'}), k1 = trdV96.make({mode: 'trendy'}); k0.trdApply(world()); k1.trdApply(file());
  assert.ok(k1.el.innerHTML === k0.el.innerHTML && !k1.el.innerHTML.includes('trd.dc2.'), 'klucze (harness v96): bez zmian');
  const f = make('pl'), wr = world().d[0];
  assert.ok(f.trdDRow(wr) && !('rs' in f.trdDRow(wr)), 'wiersz świata jak dotąd');
  assert.equal(f.trdDRow(Object.assign({}, wr, {st: 'late'})), null, 'świat: stan „late” odrzucony');
  assert.equal(f.trdDRow(Object.assign({}, wr, {st: 'late', side: 'none', rs: []})), null, 'świat z polem rs: kontrola v1 (bez „late”)');
});

test('v125: widok krypto (pl) — sekcja v2 z prawdziwych danych 27.09: kolejność bloków, „Odpowiedź na dziś” (ans.none + ans.best z ostatnim rokiem, progiem i mde + ans.need), kafle 1 / 4 / 5 / „0 z 7”, pasek rynku, karta ETH z opisem strony sprzedaży, DOGE i AVAX sprzeczne, 7 kart linii, metoda', () => {
  const {make, file, sec, card, txt, raw} = trdV125, tp = v96src.tFor('pl'), f = make('pl'); f.trdApply(file());
  const g = f.el.innerHTML, c = sec(g), T = txt(c);
  assert.ok(c && !g.includes('id="trd-daily"') && !raw(T), 'sekcja krypto v2 bez undefined/NaN/surowych kluczy');
  assert.ok(g.indexOf('id="trd-dailyc"') < g.indexOf('<h2 class="trd-wk mtxt">'), 'nad „Tło”');
  const at = s => c.indexOf(s), P = ['<h2>Następna doba (UTC): co mówią dane krypto z 26.09.2026</h2>', '<p class="pnote">' + tp('trd.dc2.sub', {h: '06:00'}) + '</p>',
    '<p class="pnote"><b>' + tp('trd.d.disc') + '</b></p>', '<h3 class="mtxt"><b>Odpowiedź na dziś</b></h3>', 'class="pnote trd-dlg"', '<section class="kpis gkpis">',
    '<p class="pnote">Cały rynek krypto, doba 26.09.2026 (UTC)', '<b>' + tp('trd.d.buy.t') + '</b>', '<b>' + tp('trd.d.sell.t') + '</b>', 'id="trd-drestc"', 'id="trd-dbdc"', 'id="trd-dmethodc"'].map(at);
  assert.ok(P.every((x, i) => x > 0 && (i === 0 || x > P[i - 1])), 'kolejność bloków: ' + P);
  assert.ok(!c.includes(tp('trd.dc.b.t')) && !c.includes(tp('trd.dc.none.all')) && !c.includes('trd-daily"'), 'bez tekstów sekcji v1');
  /* odpowiedź na dziś */
  assert.ok(c.includes('<p class="pnote">' + tp('trd.dc2.ans.none', {n: 5}) + '</p>'), 'ans.none (5 powodów)');
  assert.ok(T.includes('Najwyżej wypada: przepływ na giełdy — 57,1% w 167 dniach (obie strony razem; w ostatnim roku: 44,2% (23 z 52)). Zakres 99,3%: 46,8–66,9%. Żeby przy tej liczbie dni uznać przewagę, wynik musiałby przekroczyć ok. 60,6%, a nawet prawdziwą przewagę mniejszą niż ok. 63,8% łatwo tu przeoczyć — ten wynik wciąż może być przypadkiem. Przy 7 liniach najwyższy wynik zwykle wypada powyżej 50% także wtedy, gdy przewagi nie ma.'), 'ans.best');
  assert.ok(c.includes('<p class="pnote">' + tp('trd.dc2.ans.need', {cl: '99,3'}) + '</p>') && !T.includes('nie są jeszcze kompletne') && !T.includes('dotarły:'), 'ans.need; bez ans.wait i ans.late');
  /* kafle */
  assert.ok(c.includes(tp('trd.d.k.buy') + '</span></div><div class="k-val">1</div><small class="mtxt">BNB</small>'), 'kupno: 1 (BNB, szara)');
  assert.ok(c.includes(tp('trd.d.k.sell') + '</span></div><div class="k-val">4</div><small class="mtxt">ETH · TRX · ADA</small>'), 'sprzedaż: 4');
  assert.ok(c.includes('<div class="k-val">5</div><small class="mtxt">3 spokojnych · 2 sprzecznych · 0 nieaktualnych · 0 bez danych lub historii</small>'), 'bez sygnału: 5');
  assert.ok(c.includes('<div class="k-val">0 z 7</div>') && T.includes('od wdrożenia reguły (28.09.2026): jeszcze bez par'), '„0 z 7”, od wdrożenia z linii v2');
  assert.ok(T.includes('Cały rynek krypto, doba 26.09.2026 (UTC): podaż stablecoinów (USDT i USDC) zmieniła się o +158 mln USD — w zwykłym zakresie.'), 'pasek rynku');
  /* listy */
  const iB = at('<b>' + tp('trd.d.buy.t') + '</b>'), iS = at('<b>' + tp('trd.d.sell.t') + '</b>'), iR = at('id="trd-drestc"'), iP = at('id="trd-dbdc"'), iM = at('id="trd-dmethodc"');
  const buy = c.slice(iB, iS), sell = c.slice(iS, iR), rest = c.slice(iR, iP), pool = c.slice(iP, iM), meth = c.slice(iM);
  assert.ok(buy.includes('<p class="pnote">' + tp('trd.dc2.buy.sub', {h: '06:00'}) + '</p>') && sell.includes('<p class="pnote">' + tp('trd.dc2.sell.sub', {h: '06:00'}) + '</p>'), 'podtytuły list');
  assert.deepEqual([...buy.matchAll(/<span>([A-Z]+)<\/span>/g)].map(m => m[1]), ['BNB'], 'strona kupna');
  assert.deepEqual([...sell.matchAll(/<span>([A-Z]+)<\/span>/g)].map(m => m[1]), ['ETH', 'TRX', 'ADA', 'XRP'], 'strona sprzedaży: siła, potem nazwa');
  const eth = card(sell, 'ETH'), E = txt(eth);
  assert.ok(eth.includes('<b class="na">▼ ●●○') && eth.includes('<small>strona sprzedaży (obserwacja)</small>') && eth.includes('img/krypto/eth.svg'), 'ETH: szara obserwacja ▼, 2 kropki, logo: ' + eth);
  assert.ok(E.includes('agresywna sprzedaż wyraźnie większa niż zwykle (kupno 45,7% obrotu) · przepływ netto na giełdy wyraźnie wyższy niż zwykle (+47 592 ETH) · w zwykłym zakresie: ruch ceny, stablecoiny, premia na kontraktach'), 'ETH: powody słowami: ' + E);
  assert.match(E, /okno: 27\.09,? 06:00 → 28\.09,? 06:00 \(UTC\) · u Ciebie od \d\d:\d\d/, 'ETH: okno w UTC i czas czytelnika');
  assert.ok(E.includes('w historii, gdy powód wskazywał tę stronę (sam opis): agresywna sprzedaż 50,5% (829 z 1642) · przepływ na giełdy 48,7% (37 z 76) · co najmniej 2 powody zgodnie 47,0% (337 z 717) (zwykła doba 49,6%)'), 'ETH: strona sprzedaży (ss), linia n2: ' + E);
  assert.ok(E.includes('ocena (obie strony razem): ' + tp('trd.d.v.none')) && eth.includes('<i class="tg">' + tp('trd.d.v.none') + '</i>'), 'ETH: ocena obu stron, szara odznaka');
  assert.ok(E.includes('ta moneta, wszystkie jej karty: 338 z 643 (zakres 95%: 48,7–56,4%; sam opis, bez oceny — jedna z 10 monet)'), 'ETH: własne karty z zakresem 95%');
  assert.ok(txt(card(buy, 'BNB')).includes('agresywne kupno 49,6% (832 z 1678) · każda karta 51,5% (1734 z 3367) (zwykła doba 50,4%)'), 'BNB: strona kupna (sb), linia all');
  assert.ok(txt(card(sell, 'TRX')).includes('ruch ceny 46,7% (573 z 1227) · agresywna sprzedaż 50,5% (829 z 1642) · co najmniej 2 powody zgodnie 47,0% (337 z 717)'), 'TRX');
  assert.ok(txt(card(sell, 'ADA')).includes('premia na kontraktach wieczystych wyraźnie wyższa niż zwykle (+0,020%)') && txt(card(sell, 'ADA')).includes('premia na kontraktach 50,3% (1030 z 2046) · każda karta 48,9% (1453 z 2969) (zwykła doba 49,7%)'), 'ADA');
  /* bez sygnału: sprzeczne, potem spokojne, alfabetycznie */
  assert.ok(rest.includes('<summary>Bez sygnału dziś (5)</summary>'), 'Bez sygnału dziś (5)');
  assert.deepEqual([...rest.matchAll(/<span>([A-Z]+)<\/span>/g)].map(m => m[1]), ['AVAX', 'DOGE', 'BTC', 'LINK', 'SOL'], 'kolejność: x, quiet');
  for (const s of ['DOGE', 'AVAX']) { const k = card(rest, s); assert.ok(k.includes('<b class="na">•<small>' + tp('trd.d.st.x').replace(/^•\s*/, '') + '</small></b>') && k.includes('<br>' + tp('trd.dc2.why.x') + '</small>'), s + ': sprzeczne'); }
  assert.ok(txt(card(rest, 'DOGE')).includes('agresywne kupno wyraźnie większe niż zwykle (52,6% obrotu) · premia na kontraktach wieczystych wyraźnie wyższa niż zwykle (+0,053%) · w zwykłym zakresie: ruch ceny, stablecoiny'), 'DOGE: oba powody słowami');
  assert.ok(card(rest, 'BTC').includes('<br>' + tp('trd.dc2.why.quiet') + '</small>') && txt(card(rest, 'BTC')).includes('w zwykłym zakresie: ruch ceny, agresywne kupno, przepływ na giełdy, stablecoiny, premia na kontraktach'), 'BTC: spokojny, 5 powodów');
  /* 7 kart linii */
  const cards = pool.split('<div class="etfk trk">').slice(1);
  assert.equal(cards.length, 7, '7 kart linii');
  const names = cards.map(x => /<span>([^<]*)<\/span>/.exec(x)[1]);
  assert.deepEqual(names, ['p', 't', 'e', 's', 'h', 'n2', 'all'].map(k => v96src.escH(tp('trd.dc2.b.name', {n: tp('trd.dc2.n.' + k), d: tp('trd.dc2.d.' + k)}))), 'kolejność i nazwy linii');
  for (const x of cards) {
    const X = txt(x);
    assert.ok(X.includes('zakres 99,3% (7 linii naraz): ') && X.includes('zwykła doba: ') && X.includes('po stronie kupna: ') && X.includes('— sam opis, bez oceny') && X.includes('ostatni rok (pary od '), 'linia: zakres oceny, zwykła doba, strony, ostatni rok: ' + X);
    assert.ok(X.includes('od wdrożenia: 0 z 0 · ocena „od wdrożenia” tylko po 100, 200 i 400 dniach z sygnałem (zakres 99,8%) — teraz 0 z 100') && X.includes('próg przy tej liczbie dni: wynik powyżej ok. '), 'linia: licznik od wdrożenia bez oceny, próg i mde: ' + X);
  }
  const Ec = txt(cards[2]);
  assert.ok(cards[2].includes('<b>57,1%</b>') && Ec.includes('100 z 175 przypadków · 167 dni · dni 07.11.2023 – 24.09.2026') && Ec.includes('zakres 99,3% (7 linii naraz): 46,8–66,9%') && Ec.includes('pierwsza połowa historii: 61,4% · druga: 53,3%'), 'linia e: liczby');
  assert.ok(Ec.includes('po stronie kupna: 63 z 99 (63,6%, zwykła doba 51,3%) · po stronie sprzedaży: 37 z 76 (48,7%, zwykła doba 48,7%) — sam opis, bez oceny') && Ec.includes('ostatni rok (pary od 27.05.2026): 23 z 52 (44,2%) w 44 dniach — sam opis'), 'linia e: strony i ostatni rok');
  assert.ok(Ec.includes('próg przy tej liczbie dni: wynik powyżej ok. 60,6%; prawdziwą przewagę mniejszą niż ok. 63,8% łatwo przeoczyć'), 'linia e: próg i mde');
  const be = tp('trd.dc2.b.e', {u: '05:30'}); assert.ok(pool.split(be).length === 2 && cards[2].includes(be), 'uwaga o pierwszej publikacji tylko na karcie e');
  assert.ok(pool.includes('<p class="pnote">' + tp('trd.dc2.b.sub', {h: '06:00', m: 7, cl: '99,3'}) + '</p>') && pool.includes('<p class="pnote">' + tp('trd.dc2.b.note', {x1: 1, x2: 7, x3: 4, x4: 2, m: 7, h: '06:00', cll: '99,8'}) + '</p>'), 'opis i kalibracja (1 / 7 / 4 / 2 na 100)');
  /* metoda */
  assert.ok(meth.includes('<summary>Jak liczymy sygnały dzienne krypto (wersja reguły 2)</summary>'), 'wersja reguły z linii');
  const MV = {h: '06:00', u: '05:30', m: 7, cl: '99,3', s: '28.09.2026'};
  assert.deepEqual([...meth.matchAll(/<p class="pnote">([^<]*)<\/p>/g)].map(m => m[1]), ['1', '2', '3', '4', '5', '6', '7', '8'].map(i => tp('trd.dc2.m.' + i, MV)).concat([tp('trd.d.m.7')]), 'metoda: m.1–m.8 + trd.d.m.7');
  /* ten sam układ w kluczach (harness v96: t = klucz + pola) */
  const k = trdV96.make({mode: 'trendy', trdv: 'crypto'}); k.trdApply(file()); const kc = sec(k.el.innerHTML);
  assert.deepEqual([...kc.slice(kc.indexOf('id="trd-dmethodc"')).matchAll(/<p class="pnote">(trd\.[a-z0-9.]+)[{<]/g)].map(m => m[1]), ['1', '2', '3', '4', '5', '6', '7', '8'].map(i => 'trd.dc2.m.' + i).concat(['trd.d.m.7']), 'kolejność kluczy metody');
});

test('v125: widok krypto (en) i wszystkie 10 języków — ans.best, karta ETH po angielsku; w każdym języku tytuł, odpowiedź, 7 linii, 9 akapitów metody, bez undefined/NaN/surowych kluczy', () => {
  const {file, view, sec, card, txt, raw} = trdV125, c = sec(view('en', file())), T = txt(c);
  assert.ok(c && !raw(T), 'en: bez undefined/NaN/surowych kluczy');
  assert.ok(T.includes('Highest: flow to exchanges — 57.1% over 167 days (both sides together; in the last year: 44.2% (23 of 52)). 99.3% range: 46.8–66.9%. To count as an edge with this many days, the result would have to exceed about 60.6%, and even a real edge smaller than about 63.8% is easy to miss here'), 'en: ans.best');
  const E = txt(card(c, 'ETH'));
  assert.ok(E.includes('(+47,592 ETH)') && E.includes('aggressive selling 50.5% (829 of 1642) · flow to exchanges 48.7% (37 of 76) · at least 2 reasons agreeing 47.0% (337 of 717) (ordinary day 49.6%)') && E.includes('verdict (both sides together):') && E.includes('this coin, all its cards: 338 of 643 (95% range: 48.7–56.4%'), 'en: ETH: ' + E);
  assert.ok(c.includes('<div class="k-val">0 of 7</div>'), 'en: „0 of 7”');
  for (const L of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) {
    const tt = v96src.tFor(L), s = sec(view(L, file())), S = txt(s);
    assert.ok(s && !raw(S), L + ': bez undefined/NaN/surowych kluczy');
    assert.ok(s.includes('<h2>' + tt('trd.dc2.t').split('{d}')[0]) && S.includes(txt(tt('trd.dc2.ans.best').split('{name}')[0])) && s.includes('<b>' + tt('trd.dc2.ans.t') + '</b>'), L + ': tytuł, odpowiedź');
    const pool = s.slice(s.indexOf('id="trd-dbdc"'), s.indexOf('id="trd-dmethodc"')), meth = s.slice(s.indexOf('id="trd-dmethodc"'));
    assert.equal(pool.split('<div class="etfk trk">').length - 1, 7, L + ': 7 linii'); assert.equal(meth.split('<p class="pnote">').length - 1, 9, L + ': 9 akapitów metody');
    assert.ok(S.includes(txt(tt('trd.dc2.why.x'))) && S.includes(txt(tt('trd.dc2.why.quiet'))), L + ': karty bez sygnału');
  }
});

test('v125: przewaga — linia t „edge” i BNB „buy” z ek [t] → zielona karta, „Odpowiedź na dziś” wymienia BNB, „kolor, bo…”, „1 z 7”; przewaga przeciw karcie → karta szara, bez zdania „na żadnej karcie”; linia z przewagą, której powód dziś nigdzie nie głosuje → ans.idle', () => {
  const {make, file, rows, lines, by, sec, card, txt, raw} = trdV125, tp = v96src.tFor('pl');
  const Lt = () => lines(B => { by(B, 't').vd = 'edge'; });
  const f1 = make('pl'); f1.trdApply(file(rows(R => Object.assign(by(R, 'BNB'), {st: 'buy', vd: 'edge', ek: ['t']})), Lt()));
  const c1 = sec(f1.el.innerHTML), T1 = txt(c1), bnb = card(c1, 'BNB');
  assert.ok(!raw(T1) && bnb.includes('<b class="pos">▲ ●○○') && bnb.includes('<i class="tg pos">' + tp('trd.dc2.v.edge') + '</i>'), 'BNB zielona z odznaką przewagi (obie strony razem): ' + bnb);
  assert.ok(txt(bnb).includes('kolor, bo w historii potwierdzone: agresywne kupno'), '„kolor, bo…”');
  assert.ok(T1.includes('Z potwierdzoną przewagą w historii: strona kupna — BNB; strona sprzedaży — ' + tp('trd.d.k.empty') + '.'), 'ans.edge');
  assert.ok(!T1.includes('Najwyżej wypada') && !T1.includes(tp('trd.dc2.ans.need', {cl: '99,3'})) && !T1.includes('W historii potwierdzoną przewagę ma'), 'przy kolorze: bez „najwyżej”, bez warunku koloru');
  assert.ok(c1.includes('<div class="k-val">1 z 7</div>') && c1.includes('<div class="k-val pos">1</div>'), '„1 z 7”, kafel kupna zielony');
  const pool = c1.slice(c1.indexOf('id="trd-dbdc"')), tl = pool.split('<div class="etfk trk">')[2];
  assert.ok(tl.includes('<i class="tg pos">' + tp('trd.d.v.edge') + '</i>') && !tl.includes('próg przy tej liczbie dni'), 'linia t: odznaka przewagi, bez progu');
  /* przewaga przeciw karcie: ADA (sprzedaż) z agresywnym kupnem, linia t „edge” → zbieracz daje „obs”; strona pokazuje szarą kartę i „przeciw: …” */
  const f2 = make('pl'); f2.trdApply(file(rows(R => { const a = by(R, 'ADA'); a.rs = a.rs.map(x => x[0] === 't' ? ['t', 55.2, 1.4, 1] : x[0] === 'p' ? ['p', -1.9, -1.6, -1] : x); a.N = -1; }), Lt()));
  const c2 = sec(f2.el.innerHTML), T2 = txt(c2), ada = card(c2, 'ADA');
  assert.ok(ada.includes('<b class="na">▼') && txt(ada).includes('przeciw: agresywne kupno wyraźnie większe niż zwykle (55,2% obrotu)'), 'ADA szara, powód przeciw: ' + txt(ada));
  assert.ok(!T2.includes('ale dziś ten powód na żadnej karcie nie wskazuje kierunku') && T2.includes(tp('trd.dc2.ans.grey', {l: 'agresywne kupno'})) && T2.includes(tp('trd.dc2.ans.need', {cl: '99,3'})) && !T2.includes(tp('trd.dc2.ans.none', {n: 5})),
    'powód z przewagą dziś głosuje tylko na szarych kartach → ans.grey (nie ans.idle, nie ans.none); warunek koloru zostaje');
  assert.ok(txt(ada).includes('ocena (obie strony razem): ' + tp('trd.d.v.none')), 'ADA: po jej stronie żadna linia bez przewagi — ocena linii łączonej');
  assert.ok(c2.includes('<div class="k-val">1 z 7</div>'), '„1 z 7” także bez koloru');
  /* linia s „edge”: stablecoiny dziś na żadnej karcie nie głosują → ans.idle */
  const f3 = make('pl'); f3.trdApply(file(undefined, lines(B => { by(B, 's').vd = 'edge'; })));
  const T3 = txt(sec(f3.el.innerHTML));
  assert.ok(T3.includes('W historii potwierdzoną przewagę ma: stablecoiny — ale dziś ten powód na żadnej karcie nie wskazuje kierunku, więc kart w kolorze nie ma.') && !T3.includes('Najwyżej wypada'), 'ans.idle');
  /* linia all „edge” przy kartach z N ≠ 0 bez koloru → bez ans.idle; linia anti → żółta odznaka na linii */
  const f4 = make('pl'); f4.trdApply(file(undefined, lines(B => { by(B, 'all').vd = 'edge'; by(B, 'p').vd = 'anti'; })));
  const c4 = sec(f4.el.innerHTML), T4 = txt(c4), p4 = c4.slice(c4.indexOf('id="trd-dbdc"')).split('<div class="etfk trk">')[1];
  assert.ok(!T4.includes('ale dziś ten powód na żadnej karcie nie wskazuje kierunku') && T4.includes(tp('trd.dc2.ans.grey', {l: 'każda karta'})) && p4.includes('<i class="tg neu">' + tp('trd.d.v.anti') + '</i>'), 'all: ans.grey, bez ans.idle; p: odznaka „odwrotnie”');
});

test('v125: dane po czasie — SOL „late” w „Bez sygnału dziś” (dane po czasie + wyjaśnienie: ceny tej doby albo dni porównania), ETH z lt [e] → „po 05:30 UTC, bez głosu: przepływ na giełdy (liczba z tej doby albo dni…)” + ans.late; brak liczby → ans.wait, „brak danych z tej doby”, pasek rynku bez liczby; stablecoiny po czasie i bez porównania', () => {
  const {make, file, rows, by, sec, card, txt, raw} = trdV125, tp = v96src.tFor('pl');
  const R = rows(R => {
    Object.assign(by(R, 'SOL'), {st: 'late'});
    const e = by(R, 'ETH'); e.lt = ['e']; e.rs = e.rs.map(x => x[0] === 'e' ? [x[0], x[1], x[2], 0] : x); e.N = -1; e.str = 1;
  });
  const f = make('pl'); f.trdApply(file(R)); const c = sec(f.el.innerHTML), T = txt(c);
  assert.ok(!raw(T), 'bez undefined/NaN');
  const rest = c.slice(c.indexOf('id="trd-drestc"'), c.indexOf('id="trd-dbdc"')), sol = card(rest, 'SOL');
  assert.deepEqual([...rest.matchAll(/<span>([A-Z]+)<\/span>/g)].map(m => m[1]), ['AVAX', 'DOGE', 'BTC', 'LINK', 'SOL'], '„late” po spokojnych');
  assert.ok(sol.includes('<b class="na">•<small>dane po czasie</small></b>') && txt(sol).includes('ceny i obroty potrzebne tej karcie (z 26.09.2026 albo z dni, z którymi ją porównujemy — do 61 dni wstecz) trafiły na stronę albo zostały poprawione dopiero po 05:30 UTC, tuż przed albo już po starcie mierzonego okna — karta jest tylko opisem, bez strony'), 'SOL: ' + txt(sol));
  assert.ok(!txt(c).includes('dane z 26.09.2026 trafiły na stronę dopiero po'), 'bez dawnego zdania o samej dobie');
  const eth = txt(card(c, 'ETH'));
  assert.ok(eth.includes('po 05:30 UTC, bez głosu: przepływ na giełdy (liczba z tej doby albo dni, z którymi ją porównujemy)') && eth.includes('agresywna sprzedaż 50,5% (829 z 1642) · każda karta 48,9% (1453 z 2969) (zwykła doba 49,7%)') && !eth.includes('przepływ na giełdy 48,7%'), 'ETH: przepływ bez głosu, linia all: ' + eth);
  assert.ok(T.includes('Po 05:30 UTC dotarły: przepływ na giełdy (liczba z tej doby albo dni, z którymi ją porównujemy) — na kartach z 26.09.2026 są bez głosu, bo mierzone okno zaczyna się o 06:00 UTC.'), 'ans.late');
  assert.ok(c.includes('<div class="k-val">5</div><small class="mtxt">2 spokojnych · 2 sprzecznych · 1 nieaktualnych · 0 bez danych lub historii</small>'), '„late” liczone jako nieaktualne');
  /* brak liczby stablecoinów u BTC (pierwsza karta z wpisem s) */
  const f2 = make('pl'); f2.trdApply(file(rows(R => { const b = by(R, 'BTC'); b.rs = b.rs.map(x => x[0] === 's' ? ['s', null, null, 0] : x); })));
  const c2 = sec(f2.el.innerHTML), T2 = txt(c2);
  assert.ok(T2.includes('Dane z 26.09.2026 nie są jeszcze kompletne — brakuje: stablecoiny. Zwykle wszystko jest do ok. 04:30 UTC.') && txt(card(c2, 'BTC')).includes('brak danych z tej doby: stablecoiny'), 'ans.wait i „brak danych”');
  assert.ok(T2.includes('Cały rynek krypto, doba 26.09.2026 (UTC): ' + tp('trd.dc2.mkt.na') + '.') && !T2.includes('zmieniła się o 0') && !T2.includes('+0 mln'), 'pasek rynku: brak liczby, nigdy 0');
  const f3 = make('pl'); f3.trdApply(file(rows(R => { const b = by(R, 'BTC'); b.lt = ['s']; })));
  assert.ok(txt(sec(f3.el.innerHTML)).includes('podaż stablecoinów (USDT i USDC) zmieniła się o +158 mln USD, ale ta liczba albo dni, z którymi ją porównujemy, dotarły po 05:30 UTC — bez głosu'), 'pasek rynku: po czasie');
  /* en: te same zdania po angielsku (karta, powód, odpowiedź) */
  const fe = make('en'); fe.trdApply(file(R)); const ce = sec(fe.el.innerHTML), TE = txt(ce);
  assert.ok(txt(card(ce, 'SOL')).includes('the prices and turnover this card needs (from 09/26/2026 or from the days it is compared with — up to 61 days back) reached the site or were corrected only after 05:30 UTC')
    && txt(card(ce, 'ETH')).includes('after 05:30 UTC, no vote: flow to exchanges (the day’s figure or the days it is compared with)')
    && TE.includes('Arrived after 05:30 UTC: flow to exchanges (the day’s figure or the days it is compared with) — on the cards from 09/26/2026 they have no vote'), 'en: ' + TE.slice(0, 300));
  const f4 = make('pl'); f4.trdApply(file(rows(R => { const b = by(R, 'BTC'); b.rs = b.rs.map(x => x[0] === 's' ? ['s', 158, null, 0] : x); })));
  const T4 = txt(sec(f4.el.innerHTML));
  assert.ok(T4.includes('zmieniła się o +158 mln USD — bez porównania z historią') && txt(card(sec(f4.el.innerHTML), 'BTC')).includes('bez porównania z historią: stablecoiny'), 'bez z: bez porównania');
});

test('v125 (przegląd 27.09): karta w kolorze — „potwierdzona przewaga” i nazwa powodu jak na karcie (agresywna sprzedaż); weto — nazwane linie z przewagą, karta szara; przewaga głosująca tylko na szarych kartach → ans.grey; same ceny po czasie → ans.qlate i kafle zgodne z listami; punkt kontrolny dziennika → zastrzeżenie / potwierdzenie', () => {
  const {make, file, rows, lines, by, sec, card, txt, raw} = trdV125, tp = v96src.tFor('pl');
  /* XRP (sprzedaż, agresywna sprzedaż) w kolorze przez linię t; ETH: t po jej stronie z przewagą, ale premia przeciw też z przewagą → weto */
  const Lth = () => lines(B => { by(B, 't').vd = 'edge'; by(B, 'h').vd = 'edge'; });
  const R1 = rows(R => {
    Object.assign(by(R, 'XRP'), {st: 'sell', vd: 'edge', ek: ['t']});
    const e = by(R, 'ETH'); e.rs = e.rs.map(x => x[0] === 'h' ? ['h', 0.02, 1.5, 1] : x); e.N = -1; e.str = 2;
  });
  const f1 = make('pl'); f1.trdApply(file(R1, Lth())); const c1 = sec(f1.el.innerHTML), T1 = txt(c1), xrp = card(c1, 'XRP'), eth = card(c1, 'ETH');
  assert.ok(!raw(T1), 'bez undefined/NaN/surowych kluczy');
  assert.ok(xrp.includes('<b class="neg">▼') && xrp.includes('<i class="tg neg">' + tp('trd.dc2.v.edge') + '</i>') && !xrp.includes(tp('trd.d.v.edge')), 'XRP: czerwona, „potwierdzona przewaga” (obie strony razem), bez „częściej w tę stronę”: ' + xrp);
  assert.ok(txt(xrp).includes('agresywna sprzedaż 50,5% (829 z 1642)') && txt(xrp).includes('kolor, bo w historii potwierdzone: agresywna sprzedaż') && !txt(xrp).includes('potwierdzone: agresywne kupno'), 'XRP: nazwa powodu jak na karcie: ' + txt(xrp));
  assert.ok(T1.includes('Z potwierdzoną przewagą w historii: strona kupna — ' + tp('trd.d.k.empty') + '; strona sprzedaży — XRP.'), 'ans.edge');
  assert.ok(eth.includes('<b class="na">▼') && eth.includes('<i class="tg">' + tp('trd.dc2.v.veto', {l: 'agresywna sprzedaż'}) + '</i>') && txt(eth).includes('przeciw: premia na kontraktach wieczystych'), 'ETH: weto nazwane: ' + txt(eth));
  assert.ok(!eth.includes(tp('trd.d.v.none')) && !eth.includes(tp('trd.dc2.col', {l: 'agresywna sprzedaż'})), 'ETH: bez „brak przewagi” i bez „kolor, bo…”');
  /* TRX: t po jej stronie z przewagą, ale ani powodu z przewagą przeciw, ani linii łączonej „odwrotnie” (wiersz niezgodny z liniami) — bez zdania o wecie */
  assert.ok(!card(c1, 'TRX').includes('karta zostaje szara') && card(c1, 'TRX').includes('<i class="tg">' + tp('trd.d.v.none') + '</i>'), 'TRX: weto tylko z powodem w pliku');
  /* weto przez linię łączoną „odwrotnie” (n2 anti przy |N| = 2): TRX z ruchem ceny i agresywną sprzedażą, linia p z przewagą */
  const f1b = make('pl'); f1b.trdApply(file(undefined, lines(B => { by(B, 'p').vd = 'edge'; by(B, 'n2').vd = 'anti'; })));
  const trx = card(sec(f1b.el.innerHTML), 'TRX');
  assert.ok(trx.includes('<i class="tg">' + tp('trd.dc2.v.veto', {l: 'ruch ceny'}) + '</i>'), 'TRX: weto przez n2 „odwrotnie”: ' + txt(trx));
  /* linia t z przewagą, ale wszystkie karty z głosem t są po czasie albo sprzeczne → ans.grey; same ceny po czasie → ans.qlate; kafle = listy */
  const R2 = rows(R => { for (const k of ['ETH', 'TRX', 'XRP', 'BNB']) Object.assign(by(R, k), {st: 'late', side: 'none', vd: by(R, k).vd}); });
  const f2 = make('pl'); f2.trdApply(file(R2, lines(B => { by(B, 't').vd = 'edge'; }))); const c2 = sec(f2.el.innerHTML), T2 = txt(c2);
  assert.ok(!raw(T2) && T2.includes(tp('trd.dc2.ans.grey', {l: 'agresywne kupno'})) && !T2.includes('ale dziś ten powód na żadnej karcie nie wskazuje kierunku'), 'ans.grey: ' + T2.slice(0, 600));
  assert.ok(T2.includes('Ceny i obroty potrzebne kartom z 26.09.2026 (z tej doby albo z dni, z którymi je porównujemy) dotarły na stronę albo zostały poprawione dopiero po 05:30 UTC (kart: 4) — te karty są tylko opisem, bez strony; liczymy je razem z nieaktualnymi.'), 'ans.qlate');
  assert.ok(c2.includes(tp('trd.d.k.buy') + '</span></div><div class="k-val">0</div><small class="mtxt">' + tp('trd.d.k.emptyst', {n: 1}) + '</small>'), 'kafel kupna: nikt aktualny, 1 nieaktualna (jak lista)');
  const iB = c2.indexOf('<b>' + tp('trd.d.buy.t') + '</b>'), iS = c2.indexOf('<b>' + tp('trd.d.sell.t') + '</b>');
  assert.ok(c2.slice(iB, iS).includes(tp('trd.d.empty.st', {n: 1, s: tp('trd.d.k.none')})), 'lista kupna: ta sama liczba');
  assert.ok(c2.includes('<div class="k-val">9</div><small class="mtxt">3 spokojnych · 2 sprzecznych · 4 nieaktualnych · 0 bez danych lub historii</small>'), '„Bez sygnału”: late jak nieaktualne');
  /* punkt kontrolny dziennika: t (przewaga w próbie) — licznik jej nie potwierdził; all — potwierdził */
  const lc = (vd, c) => ({c, k: 60, n: 100, p: 60, b0: 50, ca: [44, 75], vd, to: '2027-01-05'});
  const L3 = lines(B => { by(B, 't').vd = 'edge'; Object.assign(by(B, 't'), {lc: lc('none', 100), lvd: 'none', lnx: 200}); Object.assign(by(B, 'all'), {lc: lc('edge', 200), lvd: 'edge', lnx: 400}); });
  const f3 = make('pl'); f3.trdApply(file(rows(R => Object.assign(by(R, 'XRP'), {st: 'sell', vd: 'edge', ek: ['t']})), L3)); const c3 = sec(f3.el.innerHTML), T3 = txt(c3);
  assert.ok(T3.includes('Uwaga: licznik „od wdrożenia” w swoim punkcie kontrolnym nie potwierdził przewagi: agresywne kupno.'), 'ans: zastrzeżenie punktu kontrolnego');
  assert.ok(T3.includes('Licznik „od wdrożenia” w swoim punkcie kontrolnym potwierdził przewagę: każda karta — to ocena kart zapisanych przed oknem pomiaru, a nie historii.'), 'ans: potwierdzenie punktu kontrolnego');
  assert.ok(txt(card(c3, 'XRP')).includes('kolor, bo w historii potwierdzone: agresywna sprzedaż · Uwaga: licznik „od wdrożenia” w swoim punkcie kontrolnym nie potwierdził przewagi: agresywna sprzedaż.'), 'karta: zastrzeżenie');
  const f4 = make('pl'); f4.trdApply(file(undefined, lines(B => { by(B, 't').vd = 'edge'; Object.assign(by(B, 't'), {lc: lc('edge', 100), lvd: 'edge'}); }))); const T4 = txt(sec(f4.el.innerHTML));
  assert.ok(!T4.includes('Uwaga: licznik') && T4.includes('potwierdził przewagę: agresywne kupno'), 'punkt kontrolny zgodny — bez zastrzeżenia');
  const f5 = make('pl'); f5.trdApply(file()); const T5 = txt(sec(f5.el.innerHTML));
  assert.ok(!T5.includes('„od wdrożenia” w swoim punkcie kontrolnym') && !T5.includes('dotarły na stronę dopiero') && !T5.includes(tp('trd.dc2.v.edge')), 'dziś (bez punktów kontrolnych i spóźnień): bez nowych zdań');
  for (const L of ['en', 'de', 'ja']) { const s = sec(trdV125.view(L, file(R1, Lth()))); assert.ok(s && !raw(txt(s)), L + ': bez surowych kluczy'); }
});

test('v125 (przegląd 27.09): okno karty — początek u czytelnika z dniem i miesiącem, gdy u niego to inny dzień kalendarzowy niż w UTC (na zachód od UTC−6); inaczej sama godzina', () => {
  const {make, file, sec, card, txt} = trdV125;
  const f0 = make('pl'); f0.trdApply(file()); const E0 = txt(card(sec(f0.el.innerHTML), 'ETH'));
  assert.match(E0, /okno: 27\.09,? 06:00 → 28\.09,? 06:00 \(UTC\) · u Ciebie od \d\d:\d\d/, 'ten sam dzień: sama godzina');
  const P = Date.prototype, g0 = P.getDate;
  P.getDate = function () { return this.getUTCDate() === 1 ? 2 : this.getUTCDate() - 1; };   /* czytelnik, u którego to jeszcze poprzedni dzień */
  try {
    const f1 = make('pl'); f1.trdApply(file()); const E1 = txt(card(sec(f1.el.innerHTML), 'ETH'));
    assert.match(E1, /okno: 27\.09,? 06:00 → 28\.09,? 06:00 \(UTC\) · u Ciebie od \d\d\.\d\d,? \d\d:\d\d/, 'inny dzień: z dniem i miesiącem: ' + E1);
  } finally { P.getDate = g0; }
});

test('v125: licznik „od wdrożenia” — punkt kontrolny linii all (100 dni: 260 z 520, 50,0%, zwykła doba 50,1%, brak przewagi) + następna ocena po 200 dniach (teraz 130); kafel liczy tylko linię all; dziennik nieznany → „—”', () => {
  const {make, file, lines, by, sec, txt} = trdV125, tp = v96src.tFor('pl');
  const B = lines(B => {
    for (const b of B) Object.assign(b, {lk: 5, ln: 10, ldays: 9});
    Object.assign(by(B, 'all'), {lc: {c: 100, k: 260, n: 520, p: 50, b0: 50.1, ca: [43.1, 56.9], vd: 'none', to: '2027-01-05'}, lnx: 200, ldays: 130, lk: 330, ln: 660, lvd: 'none'});
  });
  const f = make('pl'); f.trdApply(file(undefined, B)); const c = sec(f.el.innerHTML), cards = c.slice(c.indexOf('id="trd-dbdc"')).split('<div class="etfk trk">').slice(1);
  assert.ok(txt(cards[6]).includes('od wdrożenia: 330 z 660 · ocena „od wdrożenia” po 100 dniach z sygnałem: 260 z 520 (50,0%, zwykła doba 50,1%) — ' + tp('trd.d.v.none') + ' · następna ocena po 200 dniach (teraz 130)'), 'punkt kontrolny: ' + txt(cards[6]));
  assert.ok(txt(cards[0]).includes('od wdrożenia: 5 z 10 · ocena „od wdrożenia” tylko po 100, 200 i 400 dniach z sygnałem (zakres 99,8%) — teraz 9 z 100'), 'przed punktem: bez oceny');
  assert.ok(txt(c).includes('od wdrożenia reguły (28.09.2026): 330 z 660 trafień'), 'kafel: tylko linia all (linie się pokrywają)');
  /* dziennik nieznany w tym przebiegu: lk/ln/ldays null → „—”, nigdy 0 */
  const f2 = make('pl'); f2.trdApply(file(undefined, lines(B => { for (const b of B) Object.assign(b, {lk: null, ln: null, ldays: null}); })));
  const c2 = sec(f2.el.innerHTML), X = txt(c2.slice(c2.indexOf('id="trd-dbdc"')).split('<div class="etfk trk">')[1]);
  assert.ok(X.includes('od wdrożenia: — z — · ocena „od wdrożenia” tylko po 100, 200 i 400 dniach z sygnałem (zakres 99,8%) — teraz — z 100') && txt(c2).includes('od wdrożenia reguły (28.09.2026): — z — trafień')
    && !txt(c2).includes('jeszcze bez par'), 'dziennik nieznany: „— z —”, nigdy „jeszcze bez par”: ' + X);
  /* nieznany tylko licznik linii all (ta liczy się do kafla) — też „—”; linia all bez liczby, inne z liczbą — kafel nie sumuje innych */
  const f2b = make('pl'); f2b.trdApply(file(undefined, lines(B => { for (const b of B) Object.assign(b, {lk: 7, ln: 12, ldays: 9}); Object.assign(by(B, 'all'), {lk: null, ln: null}); })));
  assert.ok(txt(sec(f2b.el.innerHTML)).includes('od wdrożenia reguły (28.09.2026): — z — trafień'), 'linia all nieznana: „—”');
  const f2c = make('pl'); f2c.trdApply(file(undefined, lines(B => { for (const b of B) Object.assign(b, {lk: 0, ln: 0, ldays: 0}); })));
  assert.ok(txt(sec(f2c.el.innerHTML)).includes('od wdrożenia reguły (28.09.2026): jeszcze bez par'), 'licznik znany, 0 par: „jeszcze bez par”');
  /* po 400 dniach: bez następnej oceny */
  const f3 = make('pl'); f3.trdApply(file(undefined, lines(B => Object.assign(by(B, 'e'), {lc: {c: 400, k: 230, n: 410, p: 56.1, b0: 50, ca: [48, 64], vd: 'none', to: '2030-01-01'}, lnx: null, lvd: 'none', ldays: 420}))));
  const Y = txt(sec(f3.el.innerHTML).split('<div class="etfk trk">').filter(x => x.includes(tp('trd.dc2.b.e', {u: '05:30'})))[0]);
  assert.ok(Y.includes('ocena „od wdrożenia” po 400 dniach z sygnałem: 230 z 410 (56,1%, zwykła doba 50,0%)') && !Y.includes('następna ocena'), 'po 400 dniach: ' + Y);
});

test('v125: trdDRow2 odrzuca zły wiersz v2 (nigdy „0”): znak N ≠ dir, powtórzony klucz rs, reguła p, kody v1 x/none (dopisek do §5.1: tylko c/cx/c0), reguła niezgodna z głosami, N ≠ suma głosów, nieznany klucz, reguła c przy N = 0, głos bez z, rs dłuższe niż 5, głos spoza −1/0/1, N niecałkowite, „late” ze stroną; ici bez dwóch liczb → null (wiersz zostaje); ek/lt tylko znane klucze', () => {
  const {make, file, rows, CR, clone, sec} = trdV125, D = make('pl').trdDRow, ok = clone(CR.rows.find(r => r.id === 'ETH'));
  const r0 = D(ok);
  assert.ok(r0 && r0.rule === 'c' && r0.st === 'obs' && r0.N === -2 && r0.rs.length === 5 && r0.rs[1].k === 't' && r0.rs[1].v === 45.7 && r0.rs[1].g === -1 && r0.ici[0] === 48.7, 'dobry wiersz');
  const q = clone(CR.rows.find(r => r.id === 'BTC')), x = clone(CR.rows.find(r => r.id === 'DOGE'));
  assert.ok(q.rule === 'c0' && x.rule === 'cx' && D(q).rule === 'c0' && D(x).rule === 'cx' && D(q).st === 'quiet' && D(x).st === 'x', 'spokojna c0 i sprzeczna cx przyjęte (kody z pliku)');
  const bad = {'znak N ≠ dir': [ok, {N: 1}], 'powtórzony klucz rs': [ok, {rs: [['p', 1, 1, 0], ['p', 1, 1, 0]]}], 'reguła p w wierszu v2': [ok, {rule: 'p'}],
    'nieznany klucz rs': [ok, {rs: [['q', 1, 1, 0]]}], 'reguła c przy N = 0': [q, {rule: 'c'}], 'reguła cx przy N ≠ 0': [ok, {rule: 'cx'}], 'reguła c0 przy N ≠ 0': [ok, {rule: 'c0'}],
    'kod v1 x (sprzeczna)': [x, {rule: 'x'}], 'kod v1 none (spokojna)': [q, {rule: 'none'}], 'kod v1 x przy N ≠ 0': [ok, {rule: 'x'}],
    'cx bez żadnego głosu': [q, {rule: 'cx', st: 'x'}], 'c0 z głosami': [x, {rule: 'c0', st: 'quiet'}], 'N ≠ suma głosów': [ok, {N: -1}], 'N = 0 przy głosach jednej strony': [x, {rs: x.rs.map(y => y[0] === 'h' ? [y[0], y[1], y[2], 0] : y)}],
    'głos bez z': [ok, {rs: [['t', 45, null, -1]]}],
    'rs dłuższe niż 5': [ok, {rs: ['p', 't', 'e', 's', 'h', 'p'].map(k => [k, 1, 0.1, 0])}], 'głos spoza −1/0/1': [ok, {rs: [['t', 45, -1.2, -2]]}], 'wpis rs nie czwórką': [ok, {rs: [['t', 45, -1.2]]}],
    'rs nie tablicą': [ok, {rs: {p: 1}}], 'N niecałkowite': [ok, {N: -1.5}], 'N brak': [ok, {N: null}], '„late” ze stroną': [ok, {st: 'late'}], 'stan spoza listy': [ok, {st: 'weird'}]};
  for (const m in bad) assert.equal(D(Object.assign({}, bad[m][0], bad[m][1])), null, m);
  for (const ici of [[48.7], [48.7, '56.4'], null, 'x', [NaN, 1], [1, 2, 3]]) { const r = D(Object.assign({}, ok, {ici})); assert.ok(r && r.ici === null, 'ici ' + JSON.stringify(ici)); }
  const r2 = D(Object.assign({}, ok, {ek: ['t', 'zz', 'all', 7], lt: ['e', 'n2', 'x']})); assert.deepEqual([r2.ek, r2.lt], [['t', 'all'], ['e']], 'ek ⊂ linie, lt ⊂ powody');
  const r3 = D(Object.assign({}, ok, {rs: [['p', null, null, 0], ['t', 'x', 1.2, -1]], N: -1}));   /* N = suma głosów */
  assert.ok(r3.rs[0].v === null && r3.rs[0].z === null && r3.rs[1].v === null && r3.rs[1].z === 1.2, 'brak liczby = null');
  assert.ok(D(Object.assign({}, q, {st: 'late'})) && D(Object.assign({}, q, {st: 'late'})).st === 'late', '„late” bez strony przyjęty');
  /* zły wiersz v2 wypada, pozostałe karty zostają */
  const f = make('pl'); f.trdApply(file(rows(R => { R.find(r => r.id === 'ETH').N = 1; }))); const c = sec(f.el.innerHTML);
  assert.ok(c && !c.includes('<span>ETH</span>') && c.includes('<span>TRX</span>') && c.includes('<div class="k-val">3</div><small class="mtxt">TRX · ADA · XRP</small>'), 'bez ETH, reszta bez zmian');
});

test('v125: zapasy — plik v1 bez zmian (sekcja v123, bez tekstów v2); wiersze v2 bez poprawnej linii v2 → bez sekcji (dawna nota); karty v1 obok kart v2 (dopisek A1) → sekcja v2 tylko z kart v2, bajt w bajt jak bez nich; wszystkie wiersze v2 odrzucone → sekcja v1 z kart v1 (jak plik produkcji); linia v2 cr·p przed linią v1 w pliku v1 → sekcja v1 bierze linię v1 (48,2%, nie 47,9%); kolejność d i bd jak u zbieracza', () => {
  const {make, file, prodFile, world, rows, lines, clone, CR, V1L, V1R, sec, txt, raw} = trdV125, tp = v96src.tFor('pl');
  /* plik v1 (v123): sekcja v1 bez tekstów v2 */
  const k = trdV96.make({mode: 'trendy', trdv: 'crypto'}); k.trdApply(trdV123.both()); const kc = sec(k.el.innerHTML);
  assert.ok(kc && kc.includes('<summary>trd.dc.b.t</summary>') && !kc.includes('trd.dc2.'), 'plik v1: sekcja v123');
  const v1R = [{id: 'BTC', fam: 'cr', grp: null, iss: null, pub: 0, sym: 'BTC', date: '2026-09-26', nx: '2026-09-27', live: true, age: 1, f: null, cur: null, fu: null, zf: null, r: 1.2, zp: 1.1,
    rule: 'p', dir: 1, side: 'buy', str: 1, st: 'obs', vd: 'none', ik: 60, in: 120}];
  const v1file = bd => { const w = world(); return Object.assign(w, {d: w.d.concat(clone(v1R)), bd: w.bd.concat(bd)}); };
  const f1 = make('pl'); f1.trdApply(v1file([clone(V1L)])); const c1 = sec(f1.el.innerHTML);
  assert.ok(c1.includes('<h2>Następna doba (UTC): co mówią ceny krypto z 26.09.2026</h2>') && c1.includes('<b>48,2%</b>') && !c1.includes(tp('trd.dc2.ans.t')) && !raw(txt(c1)), 'plik v1 (prawdziwa linia v1): 48,2%');
  /* linia v2 cr·p przed linią v1: sekcja v1 bierze linię v1 */
  const v2p = clone(CR.lines[0]); assert.equal(v2p.rule + v2p.v, 'p2');
  const f2 = make('pl'); f2.trdApply(v1file([v2p, clone(V1L)])); const c2 = sec(f2.el.innerHTML);
  assert.ok(c2.includes('<b>48,2%</b>') && !c2.includes('47,9%') && !c2.includes(tp('trd.dc2.ans.t')) && c2.includes('<div class="k-val">0 z 1</div>'), 'v1: linia v1, nigdy v2');
  /* wiersze v2 bez poprawnej linii v2 → bez sekcji, dawna nota */
  const note = h => !h.includes('id="trd-dailyc"') && h.includes('<p class="pnote">' + tp('trd.d.nocr', {v: tp('trd.v.global')}) + '</p>');
  const cases = {'zły werdykt': lines(B => B.forEach(b => { b.vd = 'bogus'; })), 'bez v': lines(B => B.forEach(b => { delete b.v; })), 'v: 1': lines(B => B.forEach(b => { b.v = 1; })),
    'k > n': lines(B => B.forEach(b => { b.k = b.n + 1; })), 'nieznana reguła': lines(B => B.forEach(b => { b.rule = b.rule + 'x'; })), 'brak linii v2': []};
  for (const m in cases) { const f = make('pl'); f.trdApply(file(undefined, cases[m])); assert.ok(note(f.el.innerHTML), 'bez sekcji: ' + m); }
  /* dopisek A1: zbieracz zostawia karty v1 przed kartami v2 (dla kart przeglądarki sprzed v125) — sekcja v2 bierze tylko karty v2: ten sam HTML
     co plik bez kart v1, także z kartą v1 wstawioną między karty v2; karty v1 z liniami v2 bez poprawnej linii — nadal bez sekcji (wyżej) */
  for (const L of ['pl', 'en']) {
    const a = make(L), b = make(L), c = make(L); a.trdApply(file()); b.trdApply(Object.assign(file(), {d: world().d.concat(rows())}));
    c.trdApply(file(rows(R => R.splice(3, 0, clone(V1R[7])))));
    assert.ok(sec(a.el.innerHTML).includes(v96src.tFor(L)('trd.dc2.ans.t')) && a.el.innerHTML === b.el.innerHTML && c.el.innerHTML === a.el.innerHTML,
      L + ': karty v1 obok kart v2 — sekcja v2 bez nich, bajt w bajt');
  }
  /* wszystkie wiersze v2 odrzucone (tu: dawne kody x w wierszach v2) → zostają karty v1: sekcja v1 z linią v1, bajt w bajt jak plik produkcji */
  const g1 = make('pl'), g0 = make('pl'); g1.trdApply(file(rows(R => R.forEach(r => { r.rule = 'x'; })))); g0.trdApply(prodFile()); const cg = sec(g0.el.innerHTML);
  assert.ok(g1.el.innerHTML === g0.el.innerHTML && cg.includes('<b>48,2%</b>') && cg.includes('<summary>' + tp('trd.dc.b.t') + '</summary>') && !g0.el.innerHTML.includes(tp('trd.dc2.ans.t')),
    'wiersze v2 odrzucone: sekcja v1 z kart v1 i linii v1');
  /* część linii v2 poprawna: sekcja z tymi liniami (kafel „—”, bez ans.none); duplikat — pierwszy wygrywa; kolejność linii zawsze p, t, e, s, h, n2, all */
  const f4 = make('pl'); f4.trdApply(file(undefined, lines(B => { B.reverse(); B[0].vd = 'bogus'; B.push(Object.assign(clone(B[1]), {k: 1})); })));
  const c4 = sec(f4.el.innerHTML), n4 = c4.slice(c4.indexOf('id="trd-dbdc"')).split('<div class="etfk trk">').slice(1).map(x => /<span>([^<]*) \(/.exec(x)[1]);
  assert.deepEqual(n4, ['p', 't', 'e', 's', 'h', 'n2'].map(k => tp('trd.dc2.n.' + k)), 'linie po kolei, bez złej, duplikat pominięty');
  assert.ok(c4.includes('<div class="k-val na">—</div>') && !txt(c4).includes(tp('trd.dc2.ans.none', {n: 5})) && txt(c4).includes('Najwyżej wypada: przepływ na giełdy — 57,1%'), '6 z 7 linii: „—”, bez ans.none');
  /* plik testowy = zapis zbieracza: d — świat, 10 kart v1, 10 kart v2; bd — świat, linia v1, 7 linii v2 */
  const bd = file().bd; assert.deepEqual(bd.map(b => b.fam === 'cr' ? b.rule + ':' + b.v : 'w'), ['w', 'w', 'w', 'w', 'w', 'w', 'w', 'p:1', 'p:2', 't:2', 'e:2', 's:2', 'h:2', 'n2:2', 'all:2']);
  assert.deepEqual(file().d.map(r => r.fam !== 'cr' ? 'w' : 'rs' in r ? 2 : 1).join(''), 'w'.repeat(7) + '1'.repeat(10) + '2'.repeat(10), 'd: świat, karty v1, karty v2');
  assert.deepEqual(V1R.map(r => r.id), CR.rows.map(r => r.id), 'karty v1 tych samych 10 monet');
});

test('v125 (dopisek do SPEC §5.1, A1): stara karta przeglądarki — osadzony blok TRENDY produkcji 44e0565 (suma FNV-1a) z plikiem v125: każdy wiersz v2 (c / cx / c0) odrzucony w każdym stanie; widok krypto = jej widok pliku zbieracza produkcji z tego samego przebiegu (karty v1, linia v1 48,2%, 438 z 909, „0 z 1”) bajt w bajt, bez liczby ani zdania z części v2; świat bez zmian; plik v1 jak na stronie v125; bez NaN/undefined', () => {
  const {make, oldBlk, file, prodFile, world, rows, lines, clone, CR, V1L, V1R, sec, card, txt, raw} = trdV125, tp = v96src.tFor('pl');
  const OLD = oldBlk();
  assert.ok(!OLD.includes('trdDRow2') && !OLD.includes('trd.dc2.') && !OLD.includes('r.v!==2') && OLD.includes('function trdDailyC(D){'), 'bez kodu v125');
  const mk = (L, st) => make(L, st || {mode: 'trendy', trdv: 'crypto'}, undefined, undefined, OLD), o = mk('pl');
  /* 1. każdy wiersz v2 — z każdą regułą v2, w każdym stanie, z każdą stroną — odrzucony przez trdDRow produkcji (c / cx / c0 spoza TRD_DRL);
        karty v1 z pliku — przyjęte */
  assert.deepEqual(o.TRD_DRL, ['f', 'p', 'fp', 'x', 'none'], 'TRD_DRL produkcji');
  assert.deepEqual(CR.rows.map(r => r.rule), ['c0', 'c', 'c', 'c', 'c0', 'cx', 'c', 'c', 'c0', 'cx'], 'plik v125: tylko kody v2');
  let n = 0;
  for (const r of CR.rows) for (const rule of ['c', 'cx', 'c0']) for (const st of o.TRD_DST.concat(['late'])) for (const side of ['buy', 'sell', 'none']) {
    assert.equal(o.trdDRow(Object.assign(clone(r), {rule, st, side})), null, r.id + ' ' + rule + ' ' + st + ' ' + side); n++; }
  assert.equal(n, 10 * 3 * 9 * 3);
  assert.ok(V1R.every(r => o.trdDRow(clone(r))), 'karty v1 przyjęte przez stronę produkcji');
  /* 2. kontrola (stan sprzed dopisku, ws5/fix): plik bez kart v1, wiersze v2 z kodami x / none — stara strona przyjmowała 5 kart v2 i opisywała je
        zdaniami v1 — DOGE: „cena: dzień wyraźnie w dół (−2,26%)” i „przepływ i cena wskazują w przeciwne strony”, choć zp = −0,58, a spierają się
        agresywne kupno i premia */
  const v1codes = rows(R => R.forEach(r => { if (r.rule === 'cx') r.rule = 'x'; if (r.rule === 'c0') r.rule = 'none'; }));
  const pre = R => { const w = world(); return Object.assign(w, {d: w.d.concat(R), bd: w.bd.concat([clone(V1L)], lines())}); };
  const acc = v1codes.map(r => o.trdDRow(clone(r))).filter(Boolean);
  assert.deepEqual(acc.map(r => r.id), ['BTC', 'SOL', 'DOGE', 'LINK', 'AVAX'], 'kody v1: 5 wierszy v2 przyjętych (błąd sprzed dopisku)');
  const why = acc.map(r => o.trdDWhy(r)), g0 = mk('pl'); g0.trdApply(pre(v1codes)); const c0 = sec(g0.el.innerHTML), doge = card(c0, 'DOGE');
  assert.ok(txt(why[2]).includes('cena: dzień wyraźnie w dół (−2,26%)') && txt(doge).includes(tp('trd.d.why.x')), 'kontrola — fałszywy opis DOGE: ' + txt(doge));
  assert.ok(why.every(w => c0.includes(w)), 'kontrola: stara strona z kodami v1 pokazywała zdania v1 o kartach v2');
  /* 2b. kontrola (stan fix3: kody v2, bez kart v1 w pliku): stara strona odrzucała wszystko i pokazywała tylko notę trd.d.nocr („w przygotowaniu”)
        — bez linii v1 */
  const g2 = mk('pl'); g2.trdApply(pre(rows())); assert.ok(!g2.el.innerHTML.includes('id="trd-dailyc"') && g2.el.innerHTML.includes(tp('trd.d.nocr', {v: tp('trd.v.global')})), 'kontrola fix3: sama nota');
  /* 3. plik v125 (karty v1 + wiersze v2): widok krypto starej strony = jej widok pliku zbieracza produkcji z tego samego przebiegu, bajt w bajt —
        sekcja v1 z kart v1 i linii v1; żadna liczba linii v2 ani tekst v2; bez noty „w przygotowaniu” */
  const kn2 = L => CR.lines.map(b => v96src.tFor(L)('trd.b.kn', {k: b.k, n: b.n}));
  for (const L of ['pl', 'en']) {
    const t = v96src.tFor(L), f = mk(L), f0 = mk(L); f.trdApply(file()); f0.trdApply(prodFile()); const g = f.el.innerHTML, c = sec(g), T = txt(c);
    assert.equal(g, f0.el.innerHTML, L + ': plik v125 = plik zbieracza produkcji z tego samego przebiegu (bajt w bajt)');
    assert.ok(c && c.includes('<b>' + (L === 'pl' ? '48,2' : '48.2') + '%</b>') && T.includes(t('trd.b.kn', {k: 438, n: 909})) && c.includes('<div class="k-val">' + t('trd.dc.k.of', {e: 0, n: 1}) + '</div>'),
      L + ': sekcja v1 z linią v1 (48,2%, 438 z 909, „0 z 1”)');
    assert.ok(V1R.every(r => card(c, r.id)) && !g.includes(t('trd.d.nocr', {v: t('trd.v.global')})), L + ': karty v1 wszystkich 10 monet, bez noty');
    assert.ok(kn2(L).every(k => !T.includes(k)) && !g.includes(t('trd.dc2.ans.t')) && !g.includes('trd.dc2.'), L + ': bez liczb linii v2 i tekstów v2');
    assert.ok(!raw(T), L + ': bez undefined/NaN/surowych kluczy');
  }
  /* 4. świat (widok global) starej strony: plik v125 = plik bez krypto, bajt w bajt */
  for (const L of ['pl', 'en']) { const a = mk(L, {mode: 'trendy'}), b = mk(L, {mode: 'trendy'}); a.trdApply(world()); b.trdApply(file());
    assert.ok(a.el.innerHTML.includes('id="trd-daily"') && b.el.innerHTML === a.el.innerHTML, L + ': świat starej strony bez zmian'); }
  /* 5. linia v1 cr·p: w pliku v125 tuż po liniach świata, bajt w bajt; plik v1 (zbieracz przed ready albo po awarii v2) — stara strona i strona
        v125 pokazują go tak samo (bajt w bajt) */
  const bd = file().bd; assert.equal(JSON.stringify(bd[7]), JSON.stringify(V1L), 'linia v1 w pliku v125: tuż po świecie, bez zmian');
  for (const L of ['pl', 'en']) { const a = mk(L), b = make(L); a.trdApply(prodFile()); b.trdApply(prodFile());
    assert.ok(sec(a.el.innerHTML).includes('<b>' + (L === 'pl' ? '48,2' : '48.2') + '%</b>') && b.el.innerHTML === a.el.innerHTML, L + ': plik v1 — stara strona i strona v125 bajt w bajt'); }
});

test('v125: otwarte bloki — widok krypto v2 zapamiętuje trd-drestc / trd-dbdc / trd-dmethodc (te same id co v1); świat swoje', () => {
  const {make, file} = trdV125, opened = [];
  const el = {innerHTML: '', q: [], querySelectorAll(sel) { assert.equal(sel, 'details[open]'); return this.q; },
    querySelector(sel) { const d = {id: sel.slice(1)}; Object.defineProperty(d, 'open', {set(v) { if (v) opened.push(d.id); }}); return this.innerHTML.includes('id="' + d.id + '"') ? d : null; }};
  const st = {mode: 'trendy', trdv: 'crypto'}, f = make('pl', st, el); f.trdApply(file());
  const C = [{id: 'trd-drestc'}, {id: 'trd-dbdc'}, {id: 'trd-dmethodc'}], W = [{id: 'trd-drest'}, {id: 'trd-dmethod'}];
  assert.ok(C.every(d => el.innerHTML.includes('id="' + d.id + '"')) && !el.innerHTML.includes('id="trd-drest"'), 'te same id bloków co v1');
  el.q = C; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drestc', 'trd-dbdc', 'trd-dmethodc'], 'krypto v2: odświeżenie zachowuje otwarte');
  st.trdv = 'global'; f.renderTrendy(); assert.deepEqual(opened.splice(0), [], 'global: własne bloki (na start zamknięte)');
  el.q = W; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drest', 'trd-dmethod'], 'global: odświeżenie zachowuje swoje');
  st.trdv = 'crypto'; f.renderTrendy(); assert.deepEqual(opened.splice(0), ['trd-drestc', 'trd-dbdc', 'trd-dmethodc'], 'powrót do krypto v2 — bloki otwarte');
});

test('v125: kod strony — P1 pierwsza linia trdDRow (linia v1 dosłownie bez zmian), TRD_DST i TRD_DRULESC bez zmian, P2 kafle, P3 kod v125 tuż przed trdDailyC i przekierowanie po 4 liniach jej początku, P3b filtr linii v1, TRD_DCAL = [1, 7, 4, 2], bez nowego stylu', () => {
  const {make, file, blk, sec} = trdV125;
  assert.ok(blk.includes("function trdDRow(r){\n  if(r&&typeof r==='object'&&r.fam==='cr'&&Array.isArray(r.rs))return trdDRow2(r);   /* v125: wiersz krypto wersji 2 */\n  if(!r||typeof r!=='object'||typeof r.id!=='string'"), 'P1');
  assert.ok(blk.includes("if(!(TRD_DFAM.includes(r.fam)||r.fam==='cr')||!TRD_DRL.includes(r.rule)||!TRD_DST.includes(r.st)||!trdIso(r.date))return null;"), 'linia v1 trdDRow bez zmian');
  assert.ok(blk.includes("const TRD_DST=['buy','sell','obs','x','quiet','stale','short','nodata'];") && blk.includes("const TRD_DRULESC=[['cr','p']];"), 'TRD_DST, TRD_DRULESC bez zmian');
  assert.ok(blk.includes("s=cnt('stale')+cnt('late'),o=cnt('short')+cnt('nodata');") && blk.includes("BO=V&&V.n?BD.filter(b=>b.rule==='all'):BD,lk=BO.reduce(") && blk.includes("BD.length===(V?(V.n||TRD_DRULESC.length):TRD_DRULES.length)||e>0?(V?t('trd.dc.k.of',{e,n:V.n||TRD_DRULESC.length})"), 'P2');
  assert.ok(!blk.includes("s=cnt('stale'),o=") && !blk.includes('lk=BD.reduce(') && !blk.includes("n:TRD_DRULESC.length})"), 'P2: stare wersje usunięte');
  assert.ok(blk.includes("lu=!!(V&&V.n)&&!(BO.length&&BO.every(b=>trdNum(b.lk)&&trdNum(b.ln))),") && blk.includes("!lu&&ln>0?t('trd.d.k.oos',{d:ds,k:lk,n:ln}):t(lu?'trd.d.k.oos':'trd.d.k.oos0',lu?{d:ds,k:'—',n:'—'}:{d:ds})")
    && !blk.includes("ln>0?t('trd.d.k.oos',{d:ds,k:lk,n:ln}):t('trd.d.k.oos0',{d:ds})"), 'P2: licznik linii all nieznany → „—”');
  assert.ok(blk.includes("const trdDStale=(R,dir)=>R.filter(r=>(r.st==='stale'||r.st==='late')&&r.dir===dir).length;") && !blk.includes("r.st==='stale'&&r.dir===dir"), 'P2b: trdDStale liczy „late”');
  const iC = blk.indexOf('function trdDailyC(D){\n'), i2 = blk.indexOf('/* v125: TRENDY krypto — sygnały dzienne'), code = blk.slice(i2, iC);
  assert.ok(i2 > 0 && i2 < iC && code.endsWith('</details></section>`;\n}\n') && code.includes('function trdDailyC2(D,R,BD){'), 'P3: kod v125 tuż przed trdDailyC');
  assert.ok(blk.includes("  R.forEach(r=>{r.nm=trdDName(r).s;});\n  const s2={},B2=(Array.isArray(D.bd)?D.bd:[]).filter(b=>{if(!(b&&typeof b==='object'&&b.fam==='cr'&&b.v===2&&TRD_CRL.includes(b.rule)") &&
    blk.includes("\n  const R2=R.filter(r=>Array.isArray(r.rs));   /* v125: karty v2;") &&
    blk.includes("\n  if(B2.length&&R2.length)return trdDailyC2(D,R2,TRD_CRL.map(k=>B2.find(b=>b.rule===k)).filter(Boolean));\n  if(R2.length)return '';"), 'P3: przekierowanie (sekcja v2 tylko z kart v2)');
  assert.ok(blk.includes("TRD_DRULESC.some(p=>p[0]===b.fam&&p[1]===b.rule)&&b.v!==2&&trdNum(b.k)") && !blk.includes("TRD_DRULESC.some(p=>p[0]===b.fam&&p[1]===b.rule)&&trdNum(b.k)")
    && blk.includes("TRD_DRULES.some(p=>p[0]===b.fam&&p[1]===b.rule)&&trdNum(b.k)"), 'P3b: filtr linii v1 krypto bez v2; filtr świata bez zmian');
  for (const n of ['trdDRs', 'trdDRow2', 'trdDRsTxt', 'trdDWhy2', 'trdDWin', 'trdDEv2', 'trdDCard2', 'trdDAns', 'trdDMkt', 'trdDPool2', 'trdDailyC2']) assert.equal(blk.split('function ' + n + '(').length, 2, 'jedna funkcja ' + n);
  const f = make('pl');
  assert.deepEqual([f.TRD_DCAL, f.TRD_CRL, f.TRD_CRK, f.TRD_DRULESC2.map(p => p.join('.'))], [[1, 7, 4, 2], ['p', 't', 'e', 's', 'h', 'n2', 'all'], ['p', 't', 'e', 's', 'h'], ['cr.p', 'cr.t', 'cr.e', 'cr.s', 'cr.h', 'cr.n2', 'cr.all']]);
  assert.ok(!/style=|<style|localStorage|Date\.now|fetch\(/.test(code), 'kod v125 bez stylu, pamięci przeglądarki, zegara i sieci');
  /* klasy sekcji v2 ⊂ klasy sekcji v1 i świata (bez nowego CSS) */
  const cls = h => new Set([...h.matchAll(/class="([^"]*)"/g)].flatMap(m => m[1].split(' ')).filter(Boolean));
  const v2 = cls(sec(trdV125.view('pl', file()))), k1 = trdV96.make({mode: 'trendy', trdv: 'crypto'}, true); k1.trdApply(trdV123.both());
  const k2 = trdV96.make({mode: 'trendy'}, true); k2.trdApply(trdV120.data()); const known = new Set([...cls(k1.el.innerHTML), ...cls(k2.el.innerHTML)]);
  assert.deepEqual([...v2].filter(x => !known.has(x)), [], 'bez nowych klas');
});

test('v125: podpis licencji danych krypto — świece dzienne i godzinowe (P5), stary opis usunięty', () => {
  assert.ok(html.includes('Crypto spot candles (daily and hourly, USDT pairs) and futures long/short metrics: <a href="https://data.binance.vision/" target="_blank" rel="noopener">Binance Vision</a>'), 'nowy podpis');
  assert.ok(!html.includes('Crypto daily closes (spot, USDT pairs)'), 'stary podpis usunięty');
  assert.equal(html.split('Crypto spot candles (daily and hourly, USDT pairs)').length, 2, 'jeden podpis');
});
