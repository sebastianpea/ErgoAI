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
test('person selector exposes all/one and an accessible visibility switch', () => {
  const { PersonaSelector } = load('components/PersonaSelector.tsx', { 'react/jsx-runtime': runtime });
  let selected = 'unset', visible = false;
  const tree = PersonaSelector({ imagen: { personas: [{ id: 'persona-1' }, { id: 'persona-2' }], persona_seleccionada: null },
    mostrar: false, onMostrar: value => visible = value, onSeleccionar: value => selected = value });
  function nodes(node, type) {
    if (!node || typeof node !== 'object') return [];
    if (Array.isArray(node)) return node.flatMap(n => nodes(n, type));
    return [...(node.type === type ? [node] : []), ...nodes(node.props?.children, type)];
  }
  const toggle = nodes(tree, 'input')[0];
  assert.equal(toggle.props.role, 'switch');
  assert.equal(toggle.props.checked, false);
  toggle.props.onChange({ target: { checked: true } });
  assert.equal(visible, true);
  const select = nodes(tree, 'select')[0];
  assert.equal(select.props.value, '');
  assert.equal(nodes(tree, 'option').length, 3);
  select.props.onChange({ target: { value: 'persona-2' } });
  assert.equal(selected, 'persona-2');
  select.props.onChange({ target: { value: '' } });
  assert.equal(selected, null);
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

test('person selection and corrections carry explicit per-image identity', async () => {
  const original = globalThis.fetch, calls = [];
  globalThis.fetch = async (url, init) => { calls.push([url, JSON.parse(init.body)]); return { ok: true, json: async () => ({}) }; };
  try {
    const api = client(false);
    await api.seleccionarPersona('C-1', 'frontal', 'persona-2');
    await api.corregirPuntos('C-1', 'frontal', [], 'persona-2');
    await api.seleccionarPersona('C-1', 'frontal', null);
    assert.deepEqual(calls.map(c => c[0]), ['/api/casos/C-1/persona/frontal', '/api/casos/C-1/puntos/frontal', '/api/casos/C-1/persona/frontal']);
    assert.deepEqual(calls.map(c => c[1].persona_id), ['persona-2', 'persona-2', null]);
  } finally { globalThis.fetch = original; }
});
