import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { probe as pageProbe, visible } from './pagination.test.mjs';

const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');
const runtime = require('react/jsx-runtime');
const { renderToStaticMarkup } = require('react-dom/server');
const router = require('react-router-dom');
const { StaticRouter } = require('react-router-dom/server');
const root = fileURLToPath(new URL('../src/', import.meta.url));
function load(file, stubs, cache = new Map()) {
  const path = resolve(root, file);
  if (cache.has(path)) return cache.get(path).exports;
  const mod = { exports: {} };
  cache.set(path, mod);
  const code = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  new Function('require', 'module', 'exports', code)(name => {
    if (name in stubs) return stubs[name];
    if (name.startsWith('.')) {
      const base = resolve(dirname(path), name);
      for (const ext of ['.ts', '.tsx']) {
        try { return load(base + ext, stubs, cache); }
        catch (error) { if (error.code !== 'ENOENT') throw error; }
      }
    }
    return require(name);
  }, mod, mod.exports);
  return mod.exports;
}
function nodes(tree, type) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => nodes(child, type));
  return [...(tree.type === type ? [tree] : []), ...nodes(tree.props?.children, type)];
}
const text = tree => tree == null || typeof tree === 'boolean' ? '' : typeof tree !== 'object'
  ? String(tree) : Array.isArray(tree) ? tree.map(text).join('') : text(tree.props?.children);
const detail = 'EVIDENCIA DISTINTIVA: el tronco permanece flexionado durante la secuencia completa de ensamble; revisar la mesa, el agarre y todas las mediciones antes de decidir. Fin del informe íntegro.';
const alert = (extra = {}) => ({ id_alerta: 'A/1', id_caso: 'C/uno #', id_operario: null,
  estacion: 'Mesa norte', tipo_evento: 'ANGULO_POR_REVISAR', nivel_urgencia: 'ALTO',
  detalles: detail, timestamp: '2025-01-01T12:00:00Z', estado: 'nueva', ...extra });
const caseData = { id_caso: 'C/uno #', estacion: 'Mesa norte', tipo_tarea: 'postura', imagenes: [],
  angulos: [], hallazgos: [], contexto: {}, evaluacion_previa: {}, reba: { final: 8 }, nom036: null,
  validacion: { pendientes: 1, por_autorizar: 0 } };
function probe(alertState = { data: [alert()] }, caseState = { data: caseData }, role = 'ergonomia') {
  const queries = [], mutations = [], invalidations = [], attended = [];
  const api = { listarAlertas: () => { throw new Error('No extra alert download'); },
    obtenerCaso: id => id, atenderAlerta: id => attended.push(id) };
  const stubs = {
    '../api': { api },
    '../lib/sesion': { useSesion: () => ({ rol: role, esErgonomia: role === 'ergonomia' }) },
    '@tanstack/react-query': {
      useQuery: options => { queries.push(options); return options.queryKey[0] === 'caso' ? caseState : alertState; },
      useQueryClient: () => ({ invalidateQueries: args => invalidations.push(args.queryKey) }),
      useMutation: options => { mutations.push(options); return { isPending: false, mutate: id => {
        options.mutationFn(id); options.onSuccess?.();
      } }; },
    },
  };
  // Keep the complete Analisis page, replacing only unrelated forms/geometry with public markers.
  for (const name of ['FormNom036', 'FormReferencia', 'SkeletonEditor', 'TablaAngulos', 'FormContexto', 'ListaHallazgos']) {
    stubs[`../components/${name}`] = { [name]: () => runtime.jsx('span', { children: name }) };
  }
  stubs['../components/DesgloseReba'] = { DesgloseReba: () => 'REBA vigente', DesgloseNom036: () => null };
  const Alertas = load('pages/Alertas.tsx', stubs).Alertas;
  const Analisis = load('pages/Analisis.tsx', stubs).Analisis;
  const cards = () => {
    let tree;
    function Capture() { tree = Alertas(); return null; }
    renderToStaticMarkup(runtime.jsx(Capture, {}));
    return tree;
  };
  const renderCards = tree => renderToStaticMarkup(runtime.jsx(StaticRouter, { location: '/alertas', children: tree }));
  const renderCase = (entry = '/casos/C%2Funo%20%23') => renderToStaticMarkup(runtime.jsx(StaticRouter, {
    location: entry, children: runtime.jsx(router.Routes, { children:
      runtime.jsx(router.Route, { path: '/casos/:id', element: runtime.jsx(Analisis, {}) }) }),
  }));
  return { cards, renderCards, renderCase, queries, mutations, invalidations, attended };
}

test('cards contain a brief understandable description, never full narrative or hidden copies', () => {
  const p = probe();
  const html = p.renderCards(p.cards());
  assert.ok(!html.includes(detail), 'full distinctive narrative must not be in rendered card HTML');
  assert.ok(!html.includes('EVIDENCIA DISTINTIVA'));
  assert.match(html, /Ángulo por revisar/);
  const paragraphs = [...html.matchAll(/<p>(.*?)<\/p>/g)].map(m => m[1]);
  assert.equal(paragraphs.length, 1);
  assert.ok(paragraphs[0].length < 140 && /ángulo|medición|postura/i.test(paragraphs[0]));
  for (const label of ['ALTO', 'Mesa norte', 'nueva', 'Ver caso', 'Marcar atendida']) assert.ok(html.includes(label));
});

test('actual Ver caso Link destination and route props expose exact complete linked detail without attending', () => {
  const p = probe();
  const tree = p.cards();
  const link = nodes(tree, router.Link).find(n => text(n).startsWith('Ver caso'));
  assert.ok(link);
  assert.ok(p.renderCase().includes(detail), 'valid case route must expose complete literal alert detail');
  p.queries.length = 1; // retain the card observer before following the Link's actual destination
  const html = p.renderCase(link.props.to);
  assert.ok(html.includes(detail), 'case reached from Link must show the complete literal alert detail');
  assert.equal(link.props.to, '/casos/C%2Funo%20%23');
  for (const label of ['Detalle de alertas del caso', 'Ángulo por revisar', 'ALTO', 'Mesa norte', 'nueva',
    'Hallazgos', 'Ángulos por segmento', 'Datos de la tarea', 'REBA vigente']) assert.ok(html.includes(label), label);
  const observers = p.queries.filter(q => q.queryKey[0] === 'alertas');
  assert.equal(observers.length, 2);
  assert.equal(observers[1].enabled, false, 'case observes Layout cache, never starts another fetch-all');
  assert.deepEqual(p.attended, []);
  assert.deepEqual(p.invalidations, []);
});

test('legacy sorting, exact count, simulation badge and attendance mutation remain unchanged for both roles', () => {
  for (const role of ['ergonomia', 'ingenieria']) {
    const data = [alert({ id_alerta: 'done', estado: 'atendida', nivel_urgencia: 'CRITICO' }),
      alert({ id_alerta: 'low', nivel_urgencia: 'BAJO' }),
      alert({ id_alerta: 'sim', tipo_evento: 'EMERGENCIA_CAIDA', nivel_urgencia: 'CRITICO', id_caso: null }), alert()];
    const before = structuredClone(data);
    const p = probe({ data }, undefined, role);
    const tree = p.cards();
    const cards = nodes(tree, 'article');
    assert.equal(cards.length, 4);
    assert.deepEqual(cards.map(c => c.key), ['sim', 'A/1', 'low', 'done']);
    assert.match(p.renderCards(tree), /Fase 2 · simulación/);
    assert.equal(nodes(cards[0], router.Link).length, 0, 'null-case simulation has no broken navigation');
    assert.equal(nodes(cards[3], 'button').length, 0);
    nodes(cards[1], 'button')[0].props.onClick();
    assert.deepEqual(p.attended, ['A/1']);
    assert.deepEqual(p.invalidations, [['alertas'], ['bitacora']]);
    assert.deepEqual(data, before, 'rendering never rewrites stored details');
  }
});

test('all event descriptions are brief while original titles and counts remain', () => {
  const types = ['RIESGO_ALTO_PENDIENTE', 'DISCREPANCIA_EVALUACION', 'ANGULO_POR_REVISAR',
    'OBJETO_DESCONOCIDO', 'AUTORIZACION_PENDIENTE', 'EMERGENCIA_CAIDA'];
  const p = probe({ data: types.map((tipo_evento, i) => alert({ tipo_evento, id_alerta: String(i) })) });
  const tree = p.cards();
  assert.equal(nodes(tree, 'article').length, 6);
  for (const card of nodes(tree, 'article')) {
    const summary = nodes(card, 'p')[0];
    assert.ok(text(summary).length > 20 && text(summary).length < 140);
    assert.ok(!p.renderCards(card).includes(detail));
  }
});

test('direct case navigation filters unrelated/null cases and preserves loading, errors and underlying evidence', () => {
  const data = [alert({ id_caso: 'other', detalles: 'UNRELATED SECRET' }), alert({ id_caso: null, detalles: 'NULL SECRET' })];
  const before = structuredClone(data);
  for (const state of [{ data }, { data: [] }, { isPending: true }, { error: new Error('Alertas no disponibles') }]) {
    const p = probe(state);
    const html = p.renderCase();
    assert.ok(!html.includes('UNRELATED SECRET') && !html.includes('NULL SECRET'));
    assert.match(html, /Hallazgos/);
    assert.match(html, /REBA vigente/);
    if (state.isPending) assert.match(html, /Cargando alertas del caso/);
    if (state.error) assert.match(html, /Alertas no disponibles/);
    assert.deepEqual(p.queries.map(q => q.queryKey[0]), ['caso', 'alertas']);
    assert.deepEqual(p.attended, []); assert.deepEqual(p.invalidations, []);
  }
  assert.deepEqual(data, before);
  const mismatch = probe({ data: [alert()] }, { data: { ...caseData, id_caso: 'other' } });
  assert.ok(!mismatch.renderCase().includes(detail));
  assert.deepEqual(mismatch.attended, []); assert.deepEqual(mismatch.invalidations, []);
  for (const state of [{ isLoading: true }, { error: new Error('Caso inaccesible') }, {}]) {
    const p = probe({ data: [alert()] }, state);
    const html = p.renderCase();
    assert.match(html, /Cargando caso|Caso inaccesible|Caso no encontrado/);
    assert.ok(!html.includes(detail));
    assert.deepEqual(p.attended, []); assert.deepEqual(p.invalidations, []);
  }
});

test('alert list retains loading, error and empty states', () => {
  for (const [state, expected] of [[{ isLoading: true }, 'Cargando alertas'],
    [{ error: new Error('Fallo de alertas') }, 'Fallo de alertas'], [{ data: [] }, 'Sin alertas.']]) {
    const p = probe(state);
    assert.ok(p.renderCards(p.cards()).includes(expected));
    assert.deepEqual(p.attended, []); assert.deepEqual(p.invalidations, []);
  }
});

test('alerts sort globally before paging, preserve attend action, case link and invalidations', () => {
  const invalidated = [], attended = [];
  const data = Array.from({ length: 12 }, (_, i) => ({ id_alerta: `A${i}`, id_caso: `C/${i}`, estado: i === 0 ? 'atendida' : 'nueva', nivel_urgencia: i === 11 ? 'CRITICO' : 'BAJO', tipo_evento: 'ANGULO_POR_REVISAR', estacion: `Estación ${i}`, timestamp: '2025-01-01' }));
  const before = structuredClone(data);
  const p = pageProbe('pages/Alertas.tsx', 'Alertas', {}, {
    'react-router-dom': { Link: ({ to, children, ...rest }) => ({ type: 'a', props: { ...rest, href: to, children } }) },
    '@tanstack/react-query': {
      useQuery: () => ({ data }),
      useQueryClient: () => ({ invalidateQueries: value => invalidated.push(value.queryKey) }),
      useMutation: options => ({ mutate: id => { attended.push(id); options.onSuccess(); } }),
    },
  });
  assert.equal(visible(p.tree, 'article').length, 5);
  assert.match(text(visible(p.tree, 'article')[0]), /Estación 11/);
  assert.equal(nodes(visible(p.tree, 'article')[0], 'a')[0].props.href, '/casos/C%2F11');
  assert.match(text(p.tree), /11 alertas pendientes en total/);
  p.click('Siguiente');
  const article = visible(p.tree, 'article')[0];
  nodes(article, 'button')[0].props.onClick();
  assert.equal(attended[0], 'A5');
  assert.deepEqual(invalidated, [['alertas'], ['bitacora']]);
  p.click('Anterior'); assert.match(text(visible(p.tree, 'article')[0]), /Estación 11/);
  assert.deepEqual(data, before);
});
