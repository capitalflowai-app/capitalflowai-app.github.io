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
  assert.ok(html.includes('>Data by CoinGecko</a>'));
  assert.ok(html.includes("['SoSoValue','https://sosovalue.com']"), 'v66: podpis neutralny językowo');
  for (const host of ['home.treasury.gov', 'www.bundesbank.de', 'www.ecb.europa.eu', 'www.oecd.org', 'www.bis.org', 'www.worldbank.org']) {
    assert.ok(html.includes(`'https://${host}'`), host);
  }
});

test('notowania ETF-ów: plik z serwera (klucz właściciela) najpierw, potem własny klucz; CoinMarketCap z serwera', () => {
  assert.ok(html.includes("srvJSON('ceny')"), 'ceny.json z serwera (klucz właściciela) czytany najpierw — decyzja właściciela 24.09');
  assert.ok(html.includes("const KEYS={soso:'cfai.key.soso',finnhub:'cfai.key.finnhub',cg:'cfai.key.cg',td:'cfai.key.td'};"));
  assert.ok(html.includes('zbiera nasz automat na serwerze z kluczy właściciela'));
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
  assert.ok(html.includes('/^https:\\/\\//.test(String(lg))'), 'logo tylko z https');
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
  assert.ok(html.includes("['TradingView','https://www.tradingview.com']"), 'atrybucja');
  assert.equal((html.match(/'www\.tradingview\.com','src\.f\.l','src\.l\.0',tvState\(\),'g\.hs\.tv'\]/g) || []).length, 2, 'wiersze GLOBAL i CRYPTO');
  assert.ok(html.includes('<summary><b>TradingView</b> · widgety'), 'Źródła i prawa');
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
  assert.ok(html.includes("'api.stlouisfed.org','src.f.h','src.l.w',GLIVE.src.fred,'g.hs.fred','fred']"), 'wiersz Źródła');
  assert.ok(html.includes("['Board of Governors of the Federal Reserve System (US), via FRED','https://fred.stlouisfed.org']"), 'atrybucja');
  assert.ok(html.includes('<summary><b>Federal Reserve przez FRED</b>'), 'Źródła i prawa');
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
  assert.ok(html.includes("'data-api.ecb.europa.eu','src.f.w','src.l.w',(GLIVE.src['inst.ilm']||GLIVE.src['inst.m3']),'g.hs.ecb2','inst.ilm']"), 'wiersz Źródła');
  assert.ok(html.includes('<summary><b>EBC — bilans Eurosystemu i M3</b>'), 'Źródła i prawa');
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
  assert.ok(html.includes("['Alternative.me — Crypto Fear & Greed Index','https://alternative.me/crypto/fear-and-greed-index/']"), 'atrybucja');
  assert.ok(html.includes("'api.coingecko.com','src.f.h','src.l.90m',GLIVE.src.kr,'g.hs.kr','kr']") && html.includes("'api.alternative.me','src.f.d','src.l.90m',GLIVE.src.fng,'g.hs.fng','fng']"), 'wiersze Źródła');
  assert.ok(html.includes('<summary><b>Alternative.me</b>') && html.includes('<summary><b>CoinGecko przez automat strony</b>'), 'Źródła i prawa');
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
  assert.ok(html.includes("'data-api.ecb.europa.eu','src.f.m','src.l.7w',GLIVE.src['inst.bop'],'g.hs.bop','inst.bop']"), 'wiersz Źródła');
  assert.ok(html.includes('<summary><b>EBC — bilans płatniczy strefy euro</b>'), 'prawa');
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
  assert.ok(html.includes("'ticdata.treasury.gov','src.f.m','src.l.7w',GLIVE.src.tic,'g.hs.tic','tic']"), 'wiersz Źródła');
  assert.ok(html.includes('<summary><b>Skarb USA — TIC</b>'), 'prawa');
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
  assert.ok(html.includes("${D.twn?row(t('tic.twn'),D.twn):''}"));
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
  assert.ok(auto.includes('due(15)?gJSON(GSRC.fx'), 'kursy EBC raz na 15 min');
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
  assert.ok(html.includes("['BIS — przepływy bankowe między regionami (LBS, miara F: zmiana skorygowana o kursy)','stats.bis.org','src.f.q','src.l.bis',GLIVE.src.bis2,'g.hs.bis2','bis2'],"), 'wiersz Źródła');
  assert.ok(html.includes("['BIS Locational Banking Statistics (own calculations; unofficial translation)','https://data.bis.org/topics/LBS']"), 'atrybucja');
  assert.ok(html.includes('<summary><b>BIS — przepływy bankowe między regionami</b>') && html.includes('oznaczenia tłumaczenia jako nieoficjalnego'), 'prawa');
  assert.ok(html.includes('w produkcie płatnym — że dane BIS nie podnoszą ceny'), '_fix: warunek BIS dla produktu płatnego');
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
  assert.ok(h.includes('cftc.hist:{"n":2}') && h.includes('eng.notsays') && h.includes('cftc.src') && h.includes('cftc.disc'));
  assert.ok(h.includes('href="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"'));
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
  const s0 = html.indexOf('const S=gActive()?['), s1 = html.indexOf('\n  ]:[', s0), s2 = html.indexOf('\n  ];', s1);
  const rg = html.indexOf("['CFTC — pozycje w kontraktach na 14 rynkach (euro i inne waluty, indeks dolara, obligacje USA, S&P 500, MSCI EM, bitcoin, ether), wprost z cftc.gov','www.cftc.gov','src.f.w','src.l.w',GLIVE.src.cftc,'g.hs.cftc','cftc']");
  const rc = html.indexOf("['CFTC — pozycje w kontraktach na bitcoin i ether (CME), wprost z cftc.gov','www.cftc.gov','src.f.w','src.l.w',GLIVE.src.cftc,'g.hs.cftc','cftc']");
  assert.ok(html.indexOf("GLIVE.src['inst.bop'],'g.hs.bop','inst.bop']", s0) < rg && rg < s1, 'wiersz GLOBAL po BPS');
  assert.ok(html.indexOf("GLIVE.src.fng,'g.hs.fng','fng']", s1) < rc && rc < s2, 'wiersz CRYPTO po Fear & Greed');
  assert.ok(html.includes('<summary><b>CFTC — wprost z cftc.gov</b>'), 'prawa');
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
  assert.ok(h.includes('<a href="https://coinmetrics.io" target="_blank" rel="noopener">Source: Coin Metrics Community Network Data</a>'));
  assert.ok(h.includes('<a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" rel="noopener">CC BY-NC 4.0</a>'));
  assert.ok(h.includes('<p class="pfoot">inst.file:{"t":"F(2026-09-24T20:40:00+00:00)"} · cm.disc</p>'));
});

test('v50 cm: plik cm.json w gLoad i osobny zegar, wiersz Źródła CRYPTO, atrybucja, prawa, słownik EXTRA41 (PL, EN)', () => {
  assert.ok(html.includes("srvJSON('cm').then(j=>{cmApply(j);}).catch(()=>{cmApply(null);}),"), 'gLoad');
  assert.ok(html.includes('krLoad();krAuto();tvInit();\n') && html.includes('\ncmLoad();cmAuto();   /* v50: Coin Metrics'), 'start i zegar');
  assert.ok(html.includes('},30*60*1000);}   /* dane dzienne: co 30 min wystarczy */'), 'co 30 min');
  assert.ok(html.includes("'community-api.coinmetrics.io','src.f.d','src.l.1d',GLIVE.src.cm,'g.hs.cm','cm']"), 'wiersz Źródła');
  const rf = html.indexOf("GLIVE.src.fng,'g.hs.fng','fng'],"), rc = html.indexOf("['Coin Metrics — wpłaty BTC/ETH na giełdy i wypłaty z giełd"), rt = html.indexOf("['TradingView — widgety: mapa cieplna krypto");
  assert.ok(rf > 0 && rc > rf && rt > rc, 'lista CRYPTO: po Alternative.me, przed TradingView');
  assert.ok(html.includes("['Source: Coin Metrics Community Network Data','https://coinmetrics.io']"), 'atrybucja');
  const a = html.indexOf('<summary><b>Alternative.me</b>'), c = html.indexOf('<summary><b>Coin Metrics</b>');
  assert.ok(a > 0 && c > a, 'wpis praw po Alternative.me');
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
  assert.ok(h.includes('rez.note') && h.includes('rez.missing{"c":"TWN"}') && h.includes('rez.src') && h.includes('https://data.imf.org/en/datasets/IMF.STA:IL'));
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
  const f0 = ri.indexOf("const walcl=sr('WALCL')"), fk = ri.indexOf('html+=fredCustKpis(F);'), ft = ri.indexOf('html+=fredCustTable(F);'), fs = ri.indexOf("${t('inst.fred.src')}");
  assert.ok(f0 > 0 && fk > f0 && ft > fk && fs > ft, 'depozyt w bloku FRED');
  const tl = html.indexOf("srvJSON('tic').then(j=>{ticApply(j);})"), rl = html.indexOf("srvJSON('rezerwy').then(j=>{rezApply(j);}).catch(()=>{rezApply(null);}),");
  assert.ok(tl > 0 && rl > tl, 'plik rezerwy.json w gLoad');
  const sf = html.indexOf("'api.stlouisfed.org','src.f.h','src.l.w',GLIVE.src.fred,'g.hs.fred','fred'],");
  const sm = html.indexOf("    ['MFW — rezerwy walutowe (International Liquidity)','api.imf.org','src.f.m','src.l.2m',GLIVE.src.imf,'g.hs.imf','imf'],\n");
  assert.ok(sf > 0 && sm > sf && sm < html.indexOf("'www.mof.go.jp','src.f.w'", sf), 'wiersz Źródła po FRED, w tabeli GLOBAL');
  assert.ok(html.includes("['International Monetary Fund, International Liquidity (IL)','https://data.imf.org/en/datasets/IMF.STA:IL']"), 'atrybucja');
  assert.ok(html.includes('<summary><b>MFW — rezerwy walutowe (International Liquidity)</b>') && html.includes('osiem serii Rady Gubernatorów Fed:'), 'Źródła i prawa');
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
  assert.ok(html.includes("const ms=k==='etf'?(typeof ETF!=='undefined'&&ETF.atMs):(fa||(k&&GLIVE.srcAt&&GLIVE.srcAt[k]));"));
  assert.ok(html.includes('metaLoad();setInterval('), 'meta.json wczytywany i odświeżany');
});

// v52: stopy banków centralnych — tabela w sekcji banków centralnych, wiersz w szczegółach regionu, brak = „—”
test('v52: stopy banków centralnych: formatowanie, różnica wobec Fed, wiersz regionu i Źródła', () => {
  assert.ok(html.includes("srvJSON('stopy')") && html.includes('html+=spBlock();') && html.includes('${spRegion(s.id)}'));
  const p0 = html.indexOf('const spPct='), p1 = html.indexOf('\nfunction spRegion(', p0);
  const f = new Function('nfmt', 'instSign', html.slice(p0, p1) + '\nreturn {spPct, spPP};')((v, d) => v.toFixed(d), v => v > 0 ? '+' : (v < 0 ? '−' : ''));
  assert.equal(f.spPct(3.875), '3.875'); assert.equal(f.spPct(2.5), '2.50'); assert.equal(f.spPct(1), '1.00'); assert.equal(f.spPct(null), '—');
  assert.equal(f.spPP(-1.375), '−1.375'); assert.equal(f.spPP(0), '0'); assert.equal(f.spPP(0.25), '+0.25'); assert.equal(f.spPP(undefined), '—');
  assert.ok(html.includes("'stats.bis.org','src.f.d','src.l.1d',GLIVE.src.stopy,'g.hs.sp','stopy']"));
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
  assert.ok(html.includes("'data-api.ecb.europa.eu','src.f.m','src.l.w',GLIVE.src.kursy,'g.hs.km','kursy']"));
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
  assert.ok(html.includes("${v[2]?t(v[0]>=0?'g.plain.in':'g.plain.out'") && html.includes(":t('g.plain.none',{n:t('g.n.'+s.id)"), 'brak danych nie jest opisany jako wzrost o 0');
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
  assert.ok(html.includes("'www.fpi.nsdl.co.in','src.f.d','src.l.1d',GLIVE.src.obce_in,'g.hs.nsdl','obce_in']") && html.includes("'www.twse.com.tw','src.f.d','src.l.0',GLIVE.src.obce_tw,'g.hs.twse','obce_tw']"));
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
  assert.ok(html.includes('<td><span class="cell mono">${eerCell(a)}</span></td></tr>') && html.includes("<th>${t('sp.c.fx')}</th></tr></thead>"));
  assert.ok(html.includes('${eerRegion(s.id)}') && html.includes("srvJSON('eer')"));
  assert.ok(html.includes("'stats.bis.org','src.f.d','src.l.1d',GLIVE.src.eer,'g.hs.eer','eer']") && html.includes("eer:'BIS kursy efektywne'") && html.includes('eer:()=>EER.data&&EER.data.at'));
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
  assert.ok(h.includes('cb.cme.v{"b":"1234","e":"—"}') && h.includes('cb.k.pos · 2026-09-15'), 'CME: pozycje, nie przepływ');
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
  assert.ok(html.includes("escH(engCty(r.code,r.name_pl,r.name))") && html.includes("escH(engTx(rec,'kind'))") && html.includes('engLim(rec).map('));
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
  assert.ok(html.includes("'api.imf.org','src.f.q','src.l.q',GLIVE.src.cofer,'g.hs.cofer','cofer']"));
  const x0 = html.indexOf('const EXTRA50='), x1 = html.indexOf(';\n', x0);
  const dict = JSON.parse(html.slice(x0 + 'const EXTRA50='.length, x1));
  for (const l of ['pl', 'en']) for (const k of ['cof.t', 'cof.sub', 'cof.foot', 'cof.foot0', 'cof.not', 'cof.src', 'g.hs.cofer']) assert.ok(dict[l][k], l + ' ' + k);
});

// v60: strona Źródła zgodna z decyzją właściciela (bez obietnic zgody/wyłączenia) i ze stanem strony (nowe źródła, silnik = 2 panele)
test('v60: tekst Źródeł: bez „wystąpimy o zgodę / wyłączymy”, wpisy nowych źródeł, prawdziwy opis paneli silnika', () => {
  const a0 = html.indexOf('const TXT_ZRODLA_PL=`'), a1 = html.indexOf('`;', a0), z = html.slice(a0, a1);
  for (const w of ['wystąpić', 'wyłączymy', 'prosząc o potwierdzenie', 'zamierzamy']) assert.ok(!z.includes(w), w);
  for (const w of ['BIS — stopy procentowe banków centralnych', 'BIS — efektywne kursy walut', 'EBC — średnie miesięczne kursów', 'NSDL (Indie)', 'Giełda w Tajpej (TWSE)', 'MFW — COFER'])
    assert.ok(z.includes('<summary><b>' + w + '</b>'), w);
  assert.ok(z.includes('<b>Widoki silnika projektu:</b> MFW, Bank Światowy · <i>pokazujemy</i></summary>') && !z.includes('DefiLlama (sieci) · <i>nie pokazujemy</i>'));
  assert.ok(z.includes('Stan opisu: 25 września 2026.'));
  assert.equal((z.match(/<details class="etfd"/g) || []).length, (z.match(/<\/details>/g) || []).length, 'zbalansowane bloki');
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
  assert.ok(html.includes("return t(w&&w.k==='m'?'g.src.regm':(w&&w.k==='u'?'g.src.regu':'g.src.reg'));"), 'źródło w szczegółach wg regionu, nie wg okresu');
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
  const z0 = html.indexOf('const TXT_ZRODLA_PL=`'), z = html.slice(z0, html.indexOf('`;', z0));
  assert.ok(!z.includes('w przygotowaniu') && z.includes('<b>pokazujemy z klucza właściciela</b> —') && z.includes('<b>zapas</b> —') && z.includes('Od drugiej połowy 2025'));
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
  const s0 = html.indexOf('const SRC_EN='), s1 = html.indexOf(';\n', s0), M = JSON.parse(html.slice(s0 + 'const SRC_EN='.length, s1));
  const rows = [...html.matchAll(/\[\s*'([^']+)','[^']*','src\.f/g)].map(m => m[1]);
  assert.ok(rows.length >= 40); for (const n of rows) assert.ok(M[n], 'brak nazwy EN dla: ' + n);
  for (const v of Object.values(M)) assert.ok(!/[ąćęłńóśźż]/i.test(v), 'polski znak w nazwie EN: ' + v);
  assert.ok(html.includes("<b>${LANG==='pl'?n:(SRC_EN[n]||n)}</b>"));
  const a0 = html.indexOf('const ATTR_LINKS='), a1 = html.indexOf(';\n', a0);
  assert.ok(!/[ąćęłńóśźż]/i.test(html.slice(a0, a1)), 'podpisy źródeł bez polskich słów');
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
  assert.ok(html.includes("'www.hkex.com.hk','src.f.d','src.l.0',GLIVE.src.obce_hk,'g.hs.hkex','obce_hk']") && html.includes("obce_hk:'HKEX'"));
  assert.ok(html.includes('<summary><b>HKEX — Stock Connect</b>'));
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
  assert.ok(html.includes('function kpiCmc(M,out,live)') && html.includes('if(L[k.id].src)src=L[k.id].src;'));   // v73: kafelki CMC w kpiCmc
  assert.ok(html.includes("t(GLIVE.cenySrv?'g.m.regtds':'g.m.regtd',{n:GCENY_N[gst.period]})") && html.includes("'g.l.regtd':'g.l.reg'"));
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
  assert.ok(html.includes("'api.imf.org','src.f.q','src.l.bop',GLIVE.src.bilans,'g.hs.bilans','bilans']") && html.includes('"MFW — bilans płatniczy (BOP)":"IMF — balance of payments (BOP)"'));
  assert.ok(html.includes('<summary><b>MFW — bilans płatniczy (BOP)</b>'));
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
  assert.ok(h.includes('br.src · inst.file{"t":"y"}'));
  const r = f.brRegion('lat');
  assert.ok(r.includes('<dt>br.reg</dt>') && r.includes('"f":"-330.4","c":"—"') && r.includes('"f20":"-140.4","t20":"-183.5"'), r);
  assert.equal(f.brRegion('usa'), '');
  assert.ok(html.includes("html+=typeof brBlock==='function'?brBlock():'';") && html.includes("${typeof brRegion==='function'?brRegion(s.id):''}"));
  assert.ok(html.includes("if(okD(j.br))gOk('obce_br');") && html.includes("obce_br:'BCB'") && html.includes('obce_br:()=>ZAG.data&&ZAG.data.br&&ZAG.data.br.at'));
  assert.ok(html.includes("'api.bcb.gov.br','src.f.d','src.l.bcb',GLIVE.src.obce_br,'g.hs.bcb','obce_br']") && html.includes("['Banco Central do Brasil','https://www.bcb.gov.br']"));
  assert.ok(html.includes('<summary><b>Banco Central do Brasil — câmbio contratado</b>'));
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
  assert.ok(html.includes("'www.safe.gov.cn','src.f.m','src.l.3w',GLIVE.src.safe,'g.hs.safe','safe']") && html.includes("['SAFE','https://www.safe.gov.cn']"));
  assert.ok(html.includes('<summary><b>SAFE (Chiny) — kupno i sprzedaż walut przez banki</b>'));
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
  assert.ok(html.includes("const ks=own?src+' · '+engDate(own)+gAgeNote(own):gap?src:!lv?t('live.off'):src+' · '+liveWhen()+gAgeNote(LIVE.at||'');") && html.includes('else if(lv||L){gap=true;d=null;}'));
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
  assert.ok(html.includes("'www.tcmb.gov.tr','src.f.w','src.l.tcmb',GLIVE.src.obce_tr,'g.hs.tcmb','obce_tr']") && html.includes("['Central Bank of the Republic of Türkiye','https://www.tcmb.gov.tr']"));
  assert.ok(html.includes('<summary><b>Bank centralny Turcji (CBRT) — nierezydenci w akcjach i obligacjach</b>') && html.includes('<span class="cell">nierezydenci w tureckich akcjach i obligacjach</span>'));
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
  assert.ok(html.includes("add('POL',t('fo.pol')") && html.includes("'ec.europa.eu/eurostat','src.f.m','src.l.2m',GLIVE.src.ue,'g.hs.ue','ue']"));
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
  assert.ok(!html.includes('kraje publikują z opóźnieniem od jednego do dwóch kwartałów') && html.includes('kraje publikują od około 3 do 9 miesięcy po końcu kwartału'));
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
  assert.ok(html.includes("add('CAN',t('fo.can')") && html.includes("srvJSON('kanada')") && html.includes("kanada:'Statistics Canada'") && html.includes("['Statistics Canada','https://www.statcan.gc.ca']"));
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
  assert.ok(html.includes("${t('kan.src',{d:l[0]})}"));
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
  assert.ok(html.includes("add('KOR',t('fo.kor')") && html.includes("srvJSON('korea')") && html.includes("korea:'FSS'") && html.includes("['Financial Supervisory Service (Korea)','https://www.fss.or.kr']"));
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
  assert.ok(html.includes("'www.fss.or.kr','src.f.m','src.l.fss',GLIVE.src.korea") && !html.includes(".replace(/^([+−])/,'$1')"));
  assert.ok(html.includes('obligacje: inwestycje netto zagranicy po wykupach') && html.includes('zwykle 2–4 tygodnie po końcu miesiąca (w ostatnim roku 9–31 dni)'));
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
  assert.ok(html.includes("<h2>${t('kr.t')}</h2><p class=\"pnote\">${t('kr.sub')}</p>"), 'panel krypto czyta swoje klucze');
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
  assert.ok(html.includes("t('rail.in.g')") && html.includes("['Finnhub','g.hs.fh'],['Twelve Data','g.hs.td']") && html.includes('data-i18n="g.help.regtds"'));
  assert.ok(html.includes("'ticdata.treasury.gov','src.f.m','src.l.7w'") && html.includes("'stats.bis.org','src.f.q','src.l.bis',GLIVE.src.bis2"));
  assert.ok(!html.includes('tych danych nie ma') && !html.includes('(okresy 1T i 1M)') && !html.includes('Plik z serwera starszy niż trzy godziny') && !html.includes('tylko giełda CME.'));
  for (const s of ['<b>Skarb USA — Fiscal Data</b>', '<b>NY Fed</b>', '<b>EBC — salda TARGET</b>', '<b>Ministerstwo Finansów Japonii (MOF)</b>', 'Obok pokazujemy miary pokrewne', 'dopisek „pokazany poprzedni plik”', 'Coin Metrics</span>'])
    assert.ok(html.includes(s), s);
});

// v85: tryb CRYPTO — boczny panel to szacunek modelu, strona Przepływy i legenda to zmiana wartości
test('v85: teksty trybu CRYPTO nie nazywają zmian wyceny ani podziału modelu przepływem', () => {
  const a = 'const EXTRA73=', x0 = html.indexOf(a), d = JSON.parse(html.slice(x0 + a.length, html.indexOf(';\n', x0)));
  for (const l of ['pl', 'en', 'de', 'es', 'fr', 'it', 'pt', 'ru', 'zh', 'ja']) for (const k of ['rail.in', 'rail.out', 'leg.areaB', 'label.pct', 'pg.sectors.dc']) assert.ok(d[l][k], l + ' ' + k);
  assert.ok(d.pl['rail.in'].includes('szacunek') && d.pl['leg.areaB'].includes('zmianie wartości') && d.pl['pg.sectors.dc'].includes('zmiany wartości'));
  assert.ok(html.indexOf('Object.assign(I18N[l],EXTRA73[l]);') > html.indexOf('Object.assign(I18N[l],EXTRA72[l]);'));
  assert.ok(html.includes("<h2>▲ ${t('rail.in.g')}</h2>") && html.includes("<h2>▼ ${t('rail.out.g')}</h2>") && html.includes('<span data-i18n="rail.in"></span>'));
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
  assert.ok(html.includes("'www.thaibma.or.th','src.f.d','src.l.th',GLIVE.src.obce_th,'g.hs.thbma','obce_th']") && html.includes("['The Thai Bond Market Association (ThaiBMA)','https://www.thaibma.or.th']"));
  assert.ok(html.includes('<b>ThaiBMA (Tajlandia) — nierezydenci w obligacjach</b>') && html.includes('<span class="cell">nierezydenci w tajskich obligacjach</span>'));
  assert.ok(html.includes('regulamin ThaiBMA (pkt 2.2) przewiduje użytek osobisty') && html.includes('papiery z wykupem w ciągu roku i później'));
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
  assert.ok(html.includes("spw:()=>SPW.data&&SPW.data.at") && html.includes("spw:'MF SPW'") && html.includes("'www.gov.pl','src.f.m','src.l.spw',GLIVE.src.spw,'g.hs.spw','spw']"));
  assert.ok(html.includes('<b>Ministerstwo Finansów (Polska) — nierezydenci w krajowych papierach skarbowych</b>') && html.includes('<span class="cell">nierezydenci w krajowych papierach skarbowych (zmiana stanu)</span>'));
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
  assert.ok(html.includes('w ostatni dzień roboczy następnego miesiąca (dane za lipiec 2026 — 31.08.2026)') && html.includes('dane przetworzone'));
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
  assert.ok(html.includes("meksyk:()=>MX.data&&MX.data.at") && html.includes("meksyk:'Banxico'") && html.includes("'www.banxico.org.mx','src.f.d','src.l.bmx',GLIVE.src.meksyk,'g.hs.bmx','meksyk']"));
  assert.ok(html.includes('<b>Banco de México — nierezydenci w papierach rządowych</b>') && html.includes('<span class="cell">nierezydenci w meksykańskich papierach rządowych (zmiana stanu)</span>'));
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
  assert.ok(html.includes('banki centralne Brazylii, Meksyku i Turcji') && html.includes('kursem Fed z dnia danych (H.10, przez FRED)'));
});
