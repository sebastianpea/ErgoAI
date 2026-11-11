import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');
const runtime = require('react/jsx-runtime');
const root = new URL('../src/', import.meta.url).pathname;
export const nodes = (tree, type) => {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => nodes(child, type));
  return [...(tree.type === type ? [tree] : []), ...nodes(tree.props?.children, type)];
};
export const text = tree => tree == null || typeof tree === 'boolean' ? '' : typeof tree !== 'object' ? String(tree) : Array.isArray(tree) ? tree.map(text).join('') : text(tree.props?.children);
export function probe(file, name, props, stubs = {}) {
  const slots = []; let cursor = 0;
  const hooks = { useMemo: fn => fn(), useState: initial => {
    const i = cursor++;
    if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
    return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }];
  } };
  const cache = new Map();
  function load(path) {
    if (cache.has(path)) return cache.get(path).exports;
    const mod = { exports: {} }; cache.set(path, mod);
    const code = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
    new Function('require', 'module', 'exports', code)(id => {
      if (id === 'react') return hooks;
      if (id === 'react/jsx-runtime') return runtime;
      if (id in stubs) return stubs[id];
      if (id.endsWith('/api')) return { api: {} };
      if (id.startsWith('.')) {
        const base = resolve(dirname(path), id);
        for (const ext of ['.ts', '.tsx']) {
          try { return load(base + ext); } catch (e) { if (e.code !== 'ENOENT') throw e; }
        }
      }
      return require(id);
    }, mod, mod.exports);
    return mod.exports;
  }
  const Component = load(resolve(root, file))[name];
  // Expand stateless child controls so tests activate their real native buttons.
  const expand = tree => {
    if (!tree || typeof tree !== 'object') return tree;
    if (Array.isArray(tree)) return tree.map(expand);
    if (typeof tree.type === 'function') return expand(tree.type(tree.props));
    return { ...tree, props: { ...tree.props, children: expand(tree.props?.children) } };
  };
  const p = { props, render() { cursor = 0; p.tree = expand(Component(props)); return p.tree; }, click(label) {
    const button = nodes(p.tree, 'button').find(n => text(n) === label);
    assert.ok(button, label); assert.ok(!button.props.disabled, `${label} enabled`);
    button.props.onClick(); p.render();
  } };
  p.render(); return p;
}
export const visible = (tree, type) => nodes(tree, type).filter(n => !n.props.className?.includes('pagination-oculto'));

const findings = Array.from({ length: 12 }, (_, i) => ({ id: `H${i}`, origen: 'reba', mensaje: `Hallazgo ${i}`, severidad: 'alta' }));
// Alert tests reuse this in-memory probe without registering this file's cases twice.
if (process.argv[1] === fileURLToPath(import.meta.url)) {
test('findings paginate with accessible boundaries and retain review draft and actions', () => {
  const calls = []; const original = structuredClone(findings);
  const p = probe('components/ListaHallazgos.tsx', 'ListaHallazgos', { hallazgos: findings, editable: true, ocupado: false, onRevisar: (...args) => calls.push(args) });
  assert.equal(visible(p.tree, 'li').length, 5);
  assert.equal(nodes(p.tree, 'nav')[0].props['aria-label'], 'Paginación de hallazgos');
  assert.equal(nodes(p.tree, 'button').find(n => text(n) === 'Anterior').props.disabled, true);
  nodes(visible(p.tree, 'li')[0], 'button')[0].props.onClick(); p.render();
  nodes(p.tree, 'input')[0].props.onChange({ target: { value: 'Observado en piso' } }); p.render();
  p.click('Siguiente'); assert.equal(visible(p.tree, 'li')[0].props.children[1].props.children, 'Hallazgo 5');
  p.click('Anterior'); assert.equal(nodes(p.tree, 'input')[0].props.value, 'Observado en piso');
  nodes(p.tree, 'form')[0].props.onSubmit({ preventDefault() {} }); p.render();
  assert.deepEqual(calls, [['H0', 'descartar', 'Observado en piso']]);
  p.click('Siguiente'); p.click('Siguiente');
  assert.equal(visible(p.tree, 'li').length, 2);
  assert.equal(nodes(p.tree, 'button').find(n => text(n) === 'Siguiente').props.disabled, true);
  p.props.hallazgos = findings.slice(0, 1); p.render();
  assert.equal(visible(p.tree, 'li').length, 1);
  assert.deepEqual(findings, original);
});

test('angle pages retain confirmation and view filtering resets the page', () => {
  const calls = [];
  const angulos = Array.from({ length: 12 }, (_, i) => ({ vista: i < 6 ? 'frontal' : 'lateral', segmento: 'cuello', lado: String(i), angulo_grados: i, puntaje_reba: 1, modificadores: [], estado: 'revisar' }));
  const p = probe('components/TablaAngulos.tsx', 'TablaAngulos', { angulos, editable: true, onConfirmar: (...args) => calls.push(args) });
  assert.equal(visible(p.tree, 'tr').length, 6);
  p.click('Siguiente');
  nodes(visible(p.tree, 'tr')[1], 'button')[0].props.onClick();
  assert.deepEqual(calls, [['frontal', 'cuello']]);
  p.click('lateral'); assert.match(text(nodes(p.tree, 'span').find(n => n.props.role === 'status')), /Página 1 de 2/);
  assert.equal(visible(p.tree, 'tr').length, 6);
  p.click('Siguiente'); assert.equal(visible(p.tree, 'tr').length, 2);
});

test('REBA, NOM breakdown and residual paginate presentation while retaining global totals and scale', () => {
  const reba = { grupo_a: 3, grupo_b: 4, tabla_c: 5, carga: 1, agarre: 2, actividad: 1, final: 9, nivel: 'alto' };
  const r = probe('components/DesgloseReba.tsx', 'DesgloseReba', { reba });
  assert.equal(visible(r.tree, 'dt').length, 6); // dt belongs to paginated wrapper; inspect wrappers below.
  assert.equal(nodes(r.tree, 'div').filter(n => n.props.className === 'pagination-oculto').length, 1);
  r.click('Siguiente'); assert.match(text(r.tree), /Puntaje final REBA.*9/);
  const factores = Array.from({ length: 11 }, (_, i) => ({ codigo: `F${i}`, etiqueta: `Factor ${i}`, valor: i, color: 'verde' }));
  const n = probe('components/DesgloseReba.tsx', 'DesgloseNom036', { nom: { metodo: 'levantamiento', factores, total: 55, nivel: 'rojo' } });
  assert.equal(visible(n.tree, 'tr').length, 6); n.click('Siguiente'); assert.match(text(n.tree), /Total NOM-036.*55/);
  const residual = { segmentos: Array.from({ length: 6 }, (_, i) => ({ segmento: `s${i}`, antes: i + 1, despues: i })), antes_nivel: 'alto', despues_nivel: 'medio', antes_final: 10, despues_final: 5, recomendaciones_aplicadas: [] };
  const g = probe('components/GraficaResidual.tsx', 'GraficaResidual', { residual });
  const widths = nodes(g.tree, 'div').filter(n => n.props.className === 'barra-valor').map(n => n.props.style.width);
  g.click('Siguiente'); assert.match(text(g.tree), /Reducción de 50%/);
  assert.deepEqual(nodes(g.tree, 'div').filter(n => n.props.className === 'barra-valor').map(n => n.props.style.width), widths);
});

test('all report and print rows remain available without a page change', () => {
  const p = probe('components/ListaHallazgos.tsx', 'ListaHallazgos', { hallazgos: findings, editable: false });
  assert.equal(nodes(p.tree, 'li').length, 12);
  const css = text(nodes(p.tree, 'style')[0]);
  assert.match(css, /@media print/);
  assert.match(css, /\.informe \.pagination-oculto/);
  assert.match(css, /display: revert/);
  assert.match(css, /\.barra-fila\.pagination-oculto \{ display: grid/);
});

test('empty and short lists retain previous behavior without redundant controls', () => {
  const p = probe('components/ListaHallazgos.tsx', 'ListaHallazgos', { hallazgos: [], editable: false });
  assert.equal(text(p.tree), 'Sin hallazgos.');
  p.props.hallazgos = findings.slice(0, 5); p.render();
  assert.equal(visible(p.tree, 'li').length, 5);
  assert.equal(nodes(p.tree, 'nav').length, 0);
  assert.equal(nodes(p.tree, 'button').length, 0);
});
}
