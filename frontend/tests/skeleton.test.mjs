import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import test from 'node:test';

const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');
const runtime = require('react/jsx-runtime');
const source = readFileSync(new URL('../src/components/SkeletonEditor.tsx', import.meta.url), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
} }).outputText;

// Exercise the component's actual JSX and handlers without a DOM or user media.
function editor(props) {
  const slots = [];
  let index = 0, dirty = false, tree;
  const hooks = {
    useState(initial) {
      const i = index++;
      if (!(i in slots)) slots[i] = typeof initial === 'function' ? initial() : initial;
      return [slots[i], value => {
        slots[i] = typeof value === 'function' ? value(slots[i]) : value;
        dirty = true;
      }];
    },
    useRef(initial) {
      const i = index++;
      return slots[i] ??= { current: initial };
    },
    useMemo(fn) { return fn(); },
  };
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', compiled)(name => {
    if (name === 'react') return hooks;
    if (name === 'react/jsx-runtime') return runtime;
    if (name === '../api') return { urlImagen: path => `/media/${path}` };
    throw new Error(`Unexpected import: ${name}`);
  }, mod, mod.exports);
  function render(next = props) {
    props = next;
    let attempts = 0;
    do {
      assert.ok(++attempts < 10, 'render must settle');
      dirty = false;
      index = 0;
      tree = mod.exports.SkeletonEditor(props);
    } while (dirty);
    return tree;
  }
  render();
  return { render, get tree() { return tree; } };
}
function nodes(tree, type) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => nodes(child, type));
  return [...(tree.type === type ? [tree] : []), ...nodes(tree.props?.children, type)];
}
const point = (id, x, y, confianza = 0.9, corregido = false) => ({ id, x, y, confianza, corregido });
const image = (puntos, extra = {}) => ({ vista: 'lateral', url: 'fixture.jpg', ancho: 480, alto: 640, puntos, ...extra });
const circle = (e, id) => nodes(e.tree, 'circle').find(n => n.key === String(id));

function drag(e, id, x, y, inverse = { scale: 1, tx: 0, ty: 0 }) {
  let captured;
  e.tree.ref.current = { getScreenCTM: () => ({ inverse: () => inverse }) };
  circle(e, id).props.onPointerDown({ pointerId: 7, target: { setPointerCapture: id => captured = id } });
  e.render();
  const original = globalThis.DOMPoint;
  globalThis.DOMPoint = class {
    constructor(x, y) { this.x = x; this.y = y; }
    matrixTransform(m) { return { x: (this.x - m.tx) / m.scale, y: (this.y - m.ty) / m.scale }; }
  };
  try { e.tree.props.onPointerMove({ clientX: x, clientY: y }); }
  finally { globalThis.DOMPoint = original; }
  e.render();
  return captured;
}

test('unreliable, missing and out-of-frame endpoints never draw connections', () => {
  for (const invalid of [point(6, 200, 20, 0.39), point(6, 481, 20), point(6, 20, -1), point(6, NaN, 20), point(6, 20, 20, NaN), point(6, 20, 20, 1.1), point(6, 481, 20, 0.1, true), null]) {
    const e = editor({ imagen: image([point(5, 10, 20), ...(invalid ? [invalid] : [])]) });
    assert.equal(nodes(e.tree, 'line').length, 0, JSON.stringify(invalid));
  }
  const e = editor({ imagen: image([point(5, 0, 0, 0.4), point(6, 480, 640, 0.4)]) });
  assert.equal(nodes(e.tree, 'line').length, 1, 'inclusive threshold and image boundaries');
  assert.equal(nodes(e.tree, 'line')[0].props.x2, 480);
  assert.equal(e.tree.props.viewBox, '0 0 480 640');
  assert.equal(nodes(e.tree, 'image')[0].props.width, 480);
  assert.equal(nodes(e.tree, 'image')[0].props.height, 640);
});

test('parent point refresh replaces stale geometry; equivalent props preserve unsaved edits', () => {
  const imagen = image([point(5, 10, 20), point(6, 200, 20)]);
  const e = editor({ imagen });
  drag(e, 5, 60, 80);
  e.render({ imagen: structuredClone(imagen) });
  assert.equal(circle(e, 5).props.cx, 60, 'incidental parent rerender must not discard edits');
  const updated = image([point(5, 100, 120), point(6, 210, 30)]);
  e.render({ imagen: updated });
  assert.equal(circle(e, 5).props.cx, 100);
  assert.equal(nodes(e.tree, 'line')[0].props.x1, 100);
  e.render({ imagen: image([point(5, 1, 2)], { url: 'new.jpg', ancho: 100, alto: 200 }) });
  assert.equal(circle(e, 5).props.cx, 1);
  assert.equal(e.tree.props.viewBox, '0 0 100 200');
  assert.equal(nodes(e.tree, 'image')[0].props.href, '/media/new.jpg');
});

test('scaled drag commits corrected coordinates, identity and original confidence; clamps at image bounds', () => {
  const commits = [];
  const e = editor({ imagen: image([point(5, 10, 20, 0.1), point(6, 200, 20)]), onCommit: p => commits.push(p) });
  assert.equal(drag(e, 5, 130, 180, { scale: 2, tx: 10, ty: 20 }), 7);
  assert.equal(circle(e, 5).props.cx, 60);
  assert.equal(circle(e, 5).props.cy, 80);
  assert.equal(nodes(e.tree, 'line').length, 1, 'manual correction reconnects a low-confidence point');
  e.tree.props.onPointerUp();
  e.render();
  assert.deepEqual(commits, [[point(5, 60, 80, 0.1, true), point(6, 200, 20)]]);
  drag(e, 5, -20, 900);
  e.tree.props.onPointerCancel();
  e.render();
  assert.deepEqual(commits[1][0], point(5, 0, 640, 0.1, true));
  e.tree.props.onPointerUp();
  assert.equal(commits.length, 2, 'no duplicate idle commit');
});

test('keyboard corrections remain accessible and commit without changing confidence', () => {
  const commits = [];
  const e = editor({ imagen: image([point(5, 10, 20, 0.1)]), onCommit: p => commits.push(p) });
  assert.equal(circle(e, 5).props.tabIndex, 0);
  assert.match(circle(e, 5).props['aria-label'], /Punto 5/);
  let prevented = false;
  circle(e, 5).props.onKeyDown({ key: 'ArrowRight', shiftKey: true, preventDefault() { prevented = true; } });
  e.render();
  assert.equal(prevented, true);
  assert.deepEqual(commits, [[point(5, 20, 20, 0.1, true)]]);
  for (const key of ['ArrowLeft', 'ArrowUp', 'ArrowDown']) {
    circle(e, 5).props.onKeyDown({ key, preventDefault() {} });
    e.render();
  }
  assert.deepEqual(commits.at(-1), [point(5, 19, 20, 0.1, true)]);
  circle(e, 5).props.onKeyDown({ key: 'Tab', preventDefault() { assert.fail('Tab must work normally'); } });
  assert.equal(commits.length, 4);
});

test('read-only report retains reliable geometry but cannot edit or commit', () => {
  const commits = [];
  const e = editor({ imagen: image([point(5, 10, 20), point(6, 200, 20)]), editable: false, onCommit: p => commits.push(p) });
  assert.equal(nodes(e.tree, 'line').length, 1);
  circle(e, 5).props.onPointerDown({});
  e.render();
  e.tree.props.onPointerMove({ clientX: 99, clientY: 99 });
  e.tree.props.onPointerUp();
  assert.equal(circle(e, 5).props.cx, 10);
  assert.equal(commits.length, 0);
  assert.equal(circle(e, 5).props.tabIndex, undefined);
  circle(e, 5).props.onKeyDown({ key: 'ArrowRight' });
  assert.equal(commits.length, 0);
});

test('authoritative image metadata refresh cancels an active gesture even with identical points', () => {
  const commits = [];
  const imagen = image([point(5, 10, 20)]);
  const props = { imagen, onCommit: p => commits.push(p) };
  const e = editor(props);
  drag(e, 5, 60, 80);
  e.render({ ...props, imagen: { ...imagen, url: 'replacement.jpg', ancho: 960 } });
  assert.equal(circle(e, 5).props.cx, 10);
  e.tree.props.onPointerUp();
  assert.equal(commits.length, 0, 'old gesture must not overwrite the new image');
});

test('confidence threshold affects connections, not the ability to correct uncertain points', () => {
  const e = editor({ imagen: image([point(5, 10, 20, 0.6), point(6, 30, 40, 0.1, true)]), confianzaMinima: 0.7 });
  assert.equal(nodes(e.tree, 'line').length, 0);
  assert.equal(nodes(e.tree, 'circle').length, 2);
  assert.equal(circle(e, 5).props.fill, 'white');
  drag(e, 5, 20, 30);
  assert.equal(nodes(e.tree, 'line').length, 1);
  assert.equal(circle(e, 5).props.fill, 'var(--jabil-navy)');
});

test('absent screen transform leaves local geometry untouched', () => {
  const e = editor({ imagen: image([point(5, 10, 20)]) });
  circle(e, 5).props.onPointerDown({ pointerId: 1, target: { setPointerCapture() {} } });
  e.render();
  e.tree.props.onPointerMove({ clientX: 100, clientY: 200 });
  e.render();
  assert.equal(circle(e, 5).props.cx, 10);
  assert.equal(circle(e, 5).props.cy, 20);
});
