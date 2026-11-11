import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';
const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');
const runtime = require('react/jsx-runtime');
const { renderToStaticMarkup } = require('react-dom/server');
function load(file, stubs) {
  const code = ts.transpileModule(readFileSync(new URL('../src/' + file, import.meta.url), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', code)(name => name in stubs ? stubs[name] : require(name), mod, mod.exports);
  return mod.exports;
}
const success = { ok: true, personas: 1, rostro_anonimizado: true, reba_final: null, reba_nivel: 'sin_dato', grupo_a: null, grupo_b: null, tabla_c: null, assessment_status: 'incomplete', risk_ready: false, missing_evidence: ['actividad'], tiempo_ms: 12,
  advertencia: 'Faltan datos operativos confirmados.', angulos: [{ segmento: 'tronco', grados: 22.5, puntaje_reba: null, estado: 'ok', confianza: 0.9 }, { segmento: 'cuello', grados: null, puntaje_reba: null, estado: 'sin_dato', confianza: 0 }], imagen_anotada_b64: 'data:image/jpeg;base64,AA==' };
function render(result) {
  let slot = 0;
  const { CapturaCamaraModal } = load('components/CapturaCamaraModal.tsx', {
    react: { useEffect: () => {}, useRef: () => ({ current: null }), useState: initial => [slot++ === 7 ? result : initial, () => {}] },
    '../api': { api: {} }, '../lib/niveles': { NIVEL_REBA: { medio: { color: 'amarillo' } }, COLOR_SEMAFORO: { amarillo: '#E0B000' }, ETIQUETA_TAREA: {} },
    'react/jsx-runtime': runtime,
  });
  return renderToStaticMarkup(runtime.jsx(CapturaCamaraModal, { alCerrar: () => {} }));
}
test('camera shows measured angles but no final risk when operational evidence is missing', () => {
  const html = render(success);
  for (const value of ['22.5', 'tronco', 'cuello', 'sin_dato', 'data:image/jpeg;base64,AA==', '—', 'pendiente de revisión']) assert.ok(html.includes(value), value);
  assert.doesNotMatch(html, />4</);
  assert.doesNotMatch(html, /Dictamen REBA/);
  assert.match(html, /Análisis de postura/);
});
test('no-person response shows warning and retry, not a diagnosis or broken image', () => {
  const html = render({ ...success, ok: false, personas: 0, reba_final: null, reba_nivel: 'sin_dato', angulos: [], imagen_anotada_b64: null, advertencia: 'No se detectó a ninguna persona.' });
  assert.match(html, /No se detectó a ninguna persona/);
  assert.match(html, /Tomar otra fotografía/);
  assert.doesNotMatch(html, /Dictamen REBA|<img/);
});
function client(mock) {
  return load('api.ts', { './lib/config': { API_URL: '/api', USE_MOCK: mock }, './lib/sesion': { actorActual: () => ({ usuario: 'test', rol: 'ergonomia' }) }, './mocks/data': { casosMock: [], alertasMock: [] } }).api;
}
test('mock uses the same public response fields; multipart quick-analysis and case upload stay intact', async () => {
  const response = await client(true).analizarRapido();
  for (const key of Object.keys(success)) assert.ok(key in response, key);
  assert.ok(Array.isArray(response.angulos));
  const original = globalThis.fetch, calls = [];
  globalThis.fetch = async (url, init) => { calls.push([url, init]); return { ok: true, json: async () => success }; };
  try {
    const api = client(false), photo = new Blob(['fixture'], { type: 'image/jpeg' });
    assert.deepEqual(await api.analizarRapido(photo), success);
    await api.crearCaso({ estacion: 'test' }, { lateral: photo });
    assert.deepEqual(calls.map(c => c[0]), ['/api/vision/analizar-rapido', '/api/casos']);
    assert.deepEqual([...calls[0][1].body.keys()], ['foto']);
    assert.deepEqual([...calls[1][1].body.keys()], ['datos', 'lateral']);
    for (const [, init] of calls) { assert.equal(init.method, 'POST'); assert.equal(init.headers, undefined); }
  } finally { globalThis.fetch = original; }
});
