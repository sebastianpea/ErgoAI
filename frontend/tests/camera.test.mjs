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
const success = { ok: true, personas: 1, rostro_anonimizado: true, reba_final: 4, reba_nivel: 'medio', grupo_a: 3, grupo_b: 2, tabla_c: 4, tiempo_ms: 12,
  angulos: [{ segmento: 'tronco', grados: 22.5, puntaje_reba: 2, estado: 'ok', confianza: 0.9 }, { segmento: 'cuello', grados: null, puntaje_reba: 1, estado: 'sin_dato', confianza: 0 }], imagen_anotada_b64: 'data:image/jpeg;base64,AA==' };
function render(result) {
  let slot = 0;
  const { CapturaCamaraModal } = load('components/CapturaCamaraModal.tsx', {
    react: { useEffect: () => {}, useRef: () => ({ current: null }), useState: initial => [slot++ === 9 ? result : initial, () => {}] },
    '../api': { api: {} }, '../lib/niveles': { NIVEL_REBA: { medio: { color: 'amarillo' } }, COLOR_SEMAFORO: { amarillo: '#E0B000' }, ETIQUETA_TAREA: {} },
    'react/jsx-runtime': runtime,
  });
  return renderToStaticMarkup(runtime.jsx(CapturaCamaraModal, { alCerrar: () => {} }));
}
test('camera renders the public list/REBA response and missing angles without legacy fields', () => {
  const html = render(success);
  for (const value of ['22.5', 'tronco', 'cuello', 'medio', 'data:image/jpeg;base64,AA==', '—']) assert.ok(html.includes(value), value);
  assert.match(html, />4</);
});
test('no-person response shows warning and retry, not a diagnosis or broken image', () => {
  const html = render({ ...success, ok: false, personas: 0, reba_final: 0, reba_nivel: 'sin_dato', angulos: [], imagen_anotada_b64: null, advertencia: 'No se detectó a ninguna persona.' });
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
    assert.deepEqual(await api.analizarRapido(photo, 'postura', 8), success);
    await api.crearCaso({ estacion: 'test' }, { lateral: photo });
    assert.deepEqual(calls.map(c => c[0]), ['/api/vision/analizar-rapido', '/api/casos']);
    assert.deepEqual([...calls[0][1].body.keys()], ['foto', 'tipo_tarea', 'carga_kg']);
    assert.equal(calls[0][1].body.get('carga_kg'), '8');
    assert.equal(calls[0][1].body.get('tipo_tarea'), 'postura');
    assert.deepEqual([...calls[1][1].body.keys()], ['datos', 'lateral']);
    for (const [, init] of calls) { assert.equal(init.method, 'POST'); assert.equal(init.headers, undefined); }
  } finally { globalThis.fetch = original; }
});
