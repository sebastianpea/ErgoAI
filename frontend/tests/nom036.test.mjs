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
function form(actual = null, sheets = catalogo) {
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
    if (name === './PaginationControls') {
      const child = { exports: {} };
      const code = ts.transpileModule(readFileSync(new URL('../src/components/PaginationControls.tsx', import.meta.url), 'utf8'), {
        compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
      }).outputText;
      new Function('require', 'module', 'exports', code)(id => id === 'react' ? hooks : runtime, child, child.exports);
      return child.exports;
    }
    if (name === '@tanstack/react-query') return { useQuery: () => ({ data: sheets }) };
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
    page: label => {
      const control = nodes(tree, 'form')[0].props.children.find(n => typeof n?.type === 'function');
      assert.ok(control, 'pagination controls available');
      const button = nodes(control.type(control.props), 'button').find(n => n.props.children === label);
      assert.ok(!button.props.disabled); button.props.onClick(); render();
    },
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

test('team label never becomes a general task option in new cases or context corrections', () => {
  const load = (path, imports) => {
    const mod = { exports: {} };
    const code = ts.transpileModule(readFileSync(new URL(path, import.meta.url), 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
    }).outputText;
    new Function('require', 'module', 'exports', code)(name => {
      if (name === 'react') return { useState: initial => [typeof initial === 'function' ? initial() : initial, () => {}], useEffect: () => {} };
      if (name === 'react/jsx-runtime') return runtime;
      assert.ok(name in imports, `Unexpected import: ${name}`);
      return imports[name];
    }, mod, mod.exports);
    return mod.exports;
  };
  const levels = load('../src/lib/niveles.ts', {});
  assert.equal(levels.ETIQUETA_TAREA.equipo, 'Levantamiento/descenso en equipo');
  const context = load('../src/components/FormContexto.tsx', { '../lib/niveles': levels });
  const newCase = load('../src/pages/NuevoCaso.tsx', {
    'react-router-dom': { useNavigate: () => () => {} },
    '@tanstack/react-query': { useQuery: () => ({}), useQueryClient: () => ({}), useMutation: () => ({}) },
    '../api': { api: {} }, '../lib/niveles': levels,
    '../lib/sesion': { useSesion: () => ({ esErgonomia: true }) },
    '../components/FormReferencia': { CamposReferencia: () => null, REFERENCIA_VACIA: {} },
    '../components/Encabezado': { Encabezado: () => null },
    '../components/FormContexto': context,
    '../components/CapturaCamaraModal': { CapturaCamaraModal: () => null },
  });
  const expected = ['sin_clasificar', 'postura', 'levantamiento', 'transporte', 'empuje_con_auxiliar', 'empuje_sin_auxiliar'];
  for (const tree of [newCase.NuevoCaso(), context.FormContexto({ contexto: context.CONTEXTO_VACIO, tipoTarea: 'levantamiento', editable: true, ocupado: false, onGuardar: () => {} })]) {
    assert.deepEqual(nodes(nodes(tree, 'select')[0], 'option').map(n => n.props.value), expected);
  }
});

test('team sheet exposes all nine factors and refuses an unconfirmed factor across pages', () => {
  const sheets = JSON.parse(readFileSync(new URL('../../config_normativo/nom036_mac_rapp_tables.json', import.meta.url), 'utf8')).metodos;
  const f = form(null, sheets);
  const methods = nodes(f.tree, 'select')[0];
  assert.deepEqual(nodes(methods, 'option').map(n => n.props.value), [
    'levantamiento', 'transporte', 'equipo', 'empuje_con_auxiliar', 'empuje_sin_auxiliar',
  ]);
  assert.ok(nodes(methods, 'option').find(n => n.props.value === 'equipo').props.children.flat().join('').includes('Equipo (3)'));
  f.method('equipo'); f.reason('Hoja de equipo revisada en piso');
  const factors = sheets.equipo.factores;
  assert.equal(factors.length, 9);
  assert.equal(f.disabled, true); f.submit(); assert.deepEqual(f.saves, []);
  for (let i = 0; i < factors.length; i++) {
    if (i === 5) f.page('Siguiente');
    f.color(factors[i].etiqueta, 'verde');
    if (i === 8) continue;
    nodes(f.tree, 'input').find(n => n.props['aria-label'] === `Valor: ${factors[i].etiqueta}`).props.onChange({ target: { value: '0' } });
    f.render();
  }
  f.page('Anterior');
  assert.equal(f.disabled, true); f.submit(); assert.deepEqual(f.saves, []);
  f.page('Siguiente');
  nodes(f.tree, 'input').find(n => n.props['aria-label'] === `Valor: ${factors[8].etiqueta}`).props.onChange({ target: { value: '0' } });
  f.render(); f.submit();
  assert.deepEqual(f.saves, [[{ metodo: 'equipo', factores: factors.map(factor => ({ ...factor, color: 'verde', valor: 0 })) }, 'Hoja de equipo revisada en piso']]);
  f.method('levantamiento'); assert.equal(f.disabled, true);
  f.method('equipo'); assert.equal(f.total, '0');
});

test('paging preserves explicit factors and validates all pages before saving', () => {
  const factores = Array.from({ length: 12 }, (_, i) => ({ codigo: `F${i}`, etiqueta: `Factor ${i}`, opciones: { verde: 0, rojo: 6 } }));
  const f = form(null, { ...catalogo, levantamiento: { hoja: 'L', factores } });
  f.reason('Confirmado en piso');
  assert.equal(nodes(f.tree, 'tr').filter(n => n.props.className !== 'pagination-oculto').length, 6);
  for (let i = 0; i < 5; i++) f.color(`Factor ${i}`, 'verde');
  f.page('Siguiente'); f.color('Factor 5', 'rojo');
  f.page('Anterior');
  assert.equal(nodes(f.tree, 'select').find(n => n.props['aria-label'] === 'Color: Factor 0').props.value, 'verde');
  assert.equal(f.disabled, true); f.submit(); assert.deepEqual(f.saves, []);
  f.page('Siguiente');
  for (let i = 6; i < 10; i++) f.color(`Factor ${i}`, 'verde');
  f.page('Siguiente'); f.color('Factor 10', 'verde');
  assert.equal(f.disabled, true); f.submit(); assert.deepEqual(f.saves, []);
  f.color('Factor 11', 'verde'); assert.equal(f.total, '6');
  f.submit(); assert.equal(f.saves[0][0].factores.length, 12);
  assert.equal(f.saves[0][0].factores[5].valor, 6);
  f.page('Anterior'); f.color('Factor 5', '');
  assert.equal(f.disabled, true); f.submit(); assert.equal(f.saves.length, 1);
  f.method('transporte'); f.method('levantamiento');
  assert.equal(nodes(f.tree, 'select').find(n => n.props['aria-label'] === 'Color: Factor 0').props.value, 'verde');
  assert.equal(nodes(f.tree, 'tr').filter(n => n.props.className !== 'pagination-oculto').length, 6);
});

test('free-capture invalid and unknown values on another page still prevent saving', () => {
  const factores = Array.from({ length: 6 }, (_, i) => ({ codigo: `F${i}`, etiqueta: `Libre ${i}` }));
  const f = form({ metodo: 'empuje_con_auxiliar', factores: factores.map((factor, i) => ({ ...factor, color: 'verde', valor: i === 5 ? 51 : 0 })) },
    { ...catalogo, empuje_con_auxiliar: { hoja: 'E', captura_libre: true, factores } });
  f.reason('Medido en piso');
  assert.equal(f.disabled, true); f.submit(); assert.deepEqual(f.saves, []);
  f.page('Siguiente');
  const input = () => nodes(f.tree, 'input').find(n => n.props['aria-label'] === 'Valor: Libre 5');
  assert.equal(input().props.value, 51);
  input().props.onChange({ target: { value: '50' } }); f.render();
  f.page('Anterior'); assert.equal(f.total, '50'); f.submit();
  assert.equal(f.saves[0][0].factores.length, 6);
  f.page('Siguiente'); input().props.onChange({ target: { value: '' } }); f.render();
  f.page('Anterior'); assert.equal(f.disabled, true); f.submit(); assert.equal(f.saves.length, 1);
});

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
