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
  assert.ok(!html.includes("src:'CoinMarketCap'"), 'migawka: src SoSoValue');
});

test('atrybucje wymagane przez dostawców są na stronie', () => {
  assert.ok(html.includes('>Data by CoinGecko</a>'));
  assert.ok(html.includes("['Napływy ETF: SoSoValue','https://sosovalue.com']"));
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
