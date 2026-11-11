import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');
const runtime = require('react/jsx-runtime');
const compiled = ts.transpileModule(readFileSync(new URL('../src/components/FormNom036.tsx', import.meta.url), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const catalogo = {
  levantamiento: { hoja: 'L', factores: [
    { codigo: 'A', etiqueta: 'Carga', opciones: { verde: 0, rojo: 6 } },
    { codigo: 'B', etiqueta: 'Agarre', opciones: { verde: 0, amarillo: 1 } },
  ] },
  transporte: { hoja: 'T', factores: [{ codigo: 'A', etiqueta: 'Distancia', opciones: { verde: 0, rojo: 6 } }] },
  empuje_con_auxiliar: { hoja: 'E', captura_libre: true, factores: [{ codigo: 'A', etiqueta: 'Fuerza' }] },
};
function nodes(tree, type) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => nodes(child, type));
  return [...(tree.type === type ? [tree] : []), ...nodes(tree.props?.children, type)];
}
function form(actual = null) {
  const slots = [], saves = [];
  let index = 0, tree;
  const hooks = {
    useState(initial) {
      const i = index++;
      if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
      return [slots[i], value => { slots[i] = typeof value === 'function' ? value(slots[i]) : value; }];
    },
    useMemo: fn => fn(),
  };
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(name => {
    if (name === 'react') return hooks;
    if (name === 'react/jsx-runtime') return runtime;
    if (name === '@tanstack/react-query') return { useQuery: () => ({ data: catalogo }) };
    if (name === '../api') return { api: {} };
    if (name === '../lib/niveles') return { ETIQUETA_COLOR_NOM: {}, ETIQUETA_TAREA: {} };
    throw new Error(`Unexpected import: ${name}`);
  }, mod, mod.exports);
  const props = { tipoTarea: 'levantamiento', actual, editable: true, ocupado: false, onGuardar: (...args) => saves.push(args) };
  const render = () => { index = 0; tree = mod.exports.FormNom036(props); };
  const change = (node, value) => { node.props.onChange({ target: { value } }); render(); };
  render();
  tree.props.onClick(); render();
  const api = {
    saves, props, render,
    get tree() { return tree; },
    color: (label, value) => change(nodes(tree, 'select').find(n => n.props['aria-label'] === `Color: ${label}`), value),
    number: value => change(nodes(tree, 'input').find(n => n.props.type === 'number'), value),
    method: value => change(nodes(tree, 'select')[0], value),
    reason: value => change(nodes(tree, 'input').find(n => n.props.placeholder), value),
    submit: () => tree.props.onSubmit({ preventDefault() {} }),
    get disabled() { return nodes(tree, 'button').find(n => n.props.type === 'submit').props.disabled; },
    get total() { return nodes(tree, 'input').find(n => n.props.readOnly).props.value; },
  };
  return api;
}

test('untouched tabular factors stay unknown; only explicit green/zero permits saving', () => {
  const f = form();
  f.reason('Confirmado en piso');
  assert.equal(nodes(f.tree, 'select')[1].props.value, '');
  assert.notEqual(f.total, '0');
  assert.equal(f.disabled, true);
  f.submit(); assert.deepEqual(f.saves, []);
  f.color('Carga', 'verde');
  f.submit(); assert.deepEqual(f.saves, []);
  f.color('Agarre', 'verde');
  assert.equal(f.total, '0');
  assert.equal(f.disabled, false);
  f.submit();
  assert.deepEqual(f.saves, [[{ metodo: 'levantamiento', factores: [
    { codigo: 'A', etiqueta: 'Carga', color: 'verde', valor: 0 },
    { codigo: 'B', etiqueta: 'Agarre', color: 'verde', valor: 0 },
  ] }, 'Confirmado en piso']]);
  f.color('Carga', '');
  assert.equal(f.disabled, true);
  f.submit(); assert.equal(f.saves.length, 1);
});

test('changing sheets never carries shared factor codes; returning preserves explicit edits', () => {
  const f = form({ metodo: 'levantamiento', factores: [
    { codigo: 'A', color: 'rojo', valor: 6 }, { codigo: 'B', color: 'verde', valor: 0 },
  ] });
  f.reason('Revisado');
  f.color('Agarre', 'amarillo');
  f.method('transporte');
  assert.equal(nodes(f.tree, 'select')[1].props.value, '');
  assert.equal(f.disabled, true);
  f.submit(); assert.deepEqual(f.saves, []);
  f.color('Distancia', 'verde');
  f.submit();
  assert.equal(f.saves[0][0].factores[0].valor, 0);
  f.method('levantamiento');
  assert.equal(f.total, '7');
  f.submit();
  assert.deepEqual(f.saves[1][0].factores, [
    { codigo: 'A', etiqueta: 'Carga', color: 'rojo', valor: 6 },
    { codigo: 'B', etiqueta: 'Agarre', color: 'amarillo', valor: 1 },
  ]);
});

test('free capture requires separate color and number confirmation and clearing restores unknown', () => {
  for (const numberFirst of [false, true]) {
    const f = form(); f.method('empuje_con_auxiliar'); f.reason('Medido');
    assert.equal(nodes(f.tree, 'input').find(n => n.props.type === 'number').props.value, '');
    if (numberFirst) f.number('0'); else f.color('Fuerza', 'verde');
    assert.equal(f.disabled, true); f.submit(); assert.deepEqual(f.saves, []);
    if (numberFirst) f.color('Fuerza', 'verde'); else f.number('0');
    assert.equal(f.disabled, false); assert.equal(f.total, '0'); f.submit();
    assert.deepEqual(f.saves[0][0].factores, [{ codigo: 'A', etiqueta: 'Fuerza', color: 'verde', valor: 0 }]);
    f.number(''); assert.equal(f.disabled, true); f.submit(); assert.equal(f.saves.length, 1);
  }
});

test('existing free values, numeric edits, justification, busy guard and removal remain supported', () => {
  const f = form({ metodo: 'empuje_con_auxiliar', factores: [{ codigo: 'A', color: 'rojo', valor: 9 }] });
  assert.equal(f.total, '9'); assert.equal(f.disabled, true);
  f.reason('  Medido  '); f.number('2.6');
  assert.equal(f.total, '3'); f.submit();
  assert.deepEqual(f.saves, [[{ metodo: 'empuje_con_auxiliar', factores: [{ codigo: 'A', etiqueta: 'Fuerza', color: 'rojo', valor: 3 }] }, 'Medido']]);
  f.props.ocupado = true; f.render(); assert.equal(f.disabled, true);
  f.submit(); assert.equal(f.saves.length, 1);
  f.props.ocupado = false; f.render();
  nodes(f.tree, 'button').find(n => n.props.children === 'Quitar evaluación').props.onClick();
  assert.deepEqual(f.saves.at(-1), [null, 'Medido']);
});
