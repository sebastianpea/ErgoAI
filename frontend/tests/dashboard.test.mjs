import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');
const runtime = require('react/jsx-runtime');
const { renderToStaticMarkup } = require('react-dom/server');
const root = fileURLToPath(new URL('../src/', import.meta.url));

// Compile installed TypeScript in memory; no generated files, browser or network.
function load(file, stubs = {}, cache = new Map()) {
  const path = resolve(root, file);
  if (cache.has(path)) return cache.get(path).exports;
  const mod = { exports: {} };
  cache.set(path, mod);
  const code = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  new Function('require', 'module', 'exports', code)(name => {
    if (name in stubs) return stubs[name];
    if (name === 'react/jsx-runtime') return runtime;
    if (name.endsWith('.webp')) return 'logo.webp';
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
const nodes = (tree, type) => {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(child => nodes(child, type));
  return [...(tree.type === type ? [tree] : []), ...nodes(tree.props?.children, type)];
};
const text = tree => {
  if (tree == null || typeof tree === 'boolean') return '';
  if (typeof tree !== 'object') return String(tree);
  return Array.isArray(tree) ? tree.map(text).join('') : text(tree.props?.children);
};
const Link = ({ to, children, ...props }) => runtime.jsx('a', { ...props, href: to, children });
const metrics = { total_casos: 27, niveles: { sin_evaluar: 2, inapreciable: 1, bajo: 3, medio: 6, alto: 8, muy_alto: 7 }, tipos_tarea: { postura: 20, transporte: 7 }, decisiones_pendientes: 41, por_autorizar: 9 };

function page(file, initialData, initialSearch = '') {
  let queryData = initialData, search = new URLSearchParams(initialSearch), calls = [], effects = [], refetches = 0;
  const stubs = {
    react: { ...require('react'), useEffect: fn => effects.push(fn) },
    'react-router-dom': { Link, useSearchParams: () => [search, value => { search = new URLSearchParams(value); }] },
    '@tanstack/react-query': { useQuery: options => {
      calls.push(options);
      return { ...queryData, refetch: () => { refetches++; } };
    } },
    '../api': { api: { listarCasosPaginados: (...args) => args, metricasDashboard: () => metrics } },
  };
  const Component = Object.values(load(file, stubs))[0];
  const result = { render(data = queryData) {
    queryData = data; calls = []; effects = [];
    result.tree = Component();
    effects.forEach(fn => fn());
    return result.tree;
  }, get calls() { return calls; }, get search() { return search; }, get refetches() { return refetches; } };
  result.render();
  return result;
}

test('default route is dashboard; case list and all previous case workflows remain reachable', () => {
  const Route = () => null;
  const stubs = { 'react-router-dom': { Route, Routes: () => null }, './components/Layout': { Layout: () => null } };
  for (const name of ['Dashboard', 'Bandeja', 'Analisis', 'Plan', 'Informe', 'Alertas', 'Bitacora', 'NuevoCaso']) {
    stubs[`./pages/${name}`] = { [name]: Object.assign(() => null, { page: name }) };
  }
  const tree = load('App.tsx', stubs).default();
  const routes = nodes(tree, Route);
  assert.equal(routes.find(r => r.props.index).props.element.type.page, 'Dashboard');
  for (const [path, name] of Object.entries({ casos: 'Bandeja', 'casos/nuevo': 'NuevoCaso', 'casos/:id': 'Analisis', 'casos/:id/plan': 'Plan', 'casos/:id/informe': 'Informe', alertas: 'Alertas', bitacora: 'Bitacora' })) {
    assert.equal(routes.find(r => r.props.path === path)?.props.element.type.page, name);
  }
});

test('navigation keeps desktop/mobile cases, alert badges and role controls alongside dashboard', () => {
  const changed = [];
  const NavLink = ({ end, ...props }) => Link(props);
  const { Layout } = load('components/Layout.tsx', {
    react: { useState: initial => [initial, () => {}], useEffect: () => {} },
    'react-router-dom': { NavLink, Outlet: () => null, useLocation: () => ({ pathname: '/' }) },
    '@tanstack/react-query': { useQuery: () => ({ data: [{ estado: 'nueva' }] }) },
    '../api': { api: {} }, '../lib/config': { USE_MOCK: true },
    '../lib/sesion': {
      useSesion: () => ({ rol: 'ergonomia', usuario: 'Especialista' }),
      cambiarRol: role => changed.push(role),
      PERFILES: { ergonomia: { etiqueta: 'Ergonomía' }, ingenieria: { etiqueta: 'Ingeniería' } },
    },
  });
  const tree = Layout();
  const html = renderToStaticMarkup(tree);
  assert.equal(nodes(tree, NavLink).filter(n => n.props.to === '/casos').length, 2);
  for (const value of ['Dashboard', 'Casos', 'Alertas', 'Bitácora', 'Rol activo', 'Ingeniería', '1 nuevas']) assert.ok(html.includes(value), value);
  assert.match(html, /href="\/casos"/);
  const selector = nodes(tree, 'label').length;
  assert.equal(selector, 0, 'selectors remain separate components');
  // Exercise the existing role control via the actual nested component.
  const roleComponent = nodes(tree, 'span').find(n => n.props.className === 'usuario').props.children[1];
  const select = nodes(roleComponent.type(), 'select')[0];
  select.props.onChange({ target: { value: 'ingenieria' } });
  assert.deepEqual(changed, ['ingenieria']);
});

test('existing broad invalidations reach page and aggregate query keys', async () => {
  const { QueryClient } = require('@tanstack/react-query');
  const qc = new QueryClient({ defaultOptions: { queries: { gcTime: Infinity } } });
  const dashboard = page('pages/Dashboard.tsx', { data: metrics }).calls[0].queryKey;
  const cases = page('pages/Bandeja.tsx', { data: { items: [], total: 0, total_pages: 0 } }).calls[0].queryKey;
  for (const key of [dashboard, cases, ['alertas']]) qc.setQueryData(key, {});
  await qc.invalidateQueries({ queryKey: ['casos'], refetchType: 'none' });
  assert.equal(qc.getQueryState(dashboard).isInvalidated, true);
  assert.equal(qc.getQueryState(cases).isInvalidated, true);
  assert.equal(qc.getQueryState(['alertas']).isInvalidated, false);
  qc.clear();
});

test('dashboard uses global aggregates only and renders accessible charts with exact labels and counts', async () => {
  const p = page('pages/Dashboard.tsx', { data: metrics });
  assert.deepEqual(p.calls.map(c => c.queryKey), [['casos', 'dashboard']]);
  assert.deepEqual(await p.calls[0].queryFn(), metrics);
  const html = renderToStaticMarkup(p.tree);
  for (const value of ['27', '41', '9', 'Sin evaluar', 'Muy alto', 'Postura (ensamble)', 'Transporte sin auxiliar (acarreo)', '20', '7']) assert.ok(html.includes(value), value);
  assert.match(html, /href="\/casos"/);
  for (const [label, count] of [['Sin evaluar', 2], ['Inapreciable', 1], ['Bajo', 3], ['Medio', 6], ['Alto', 8], ['Muy alto', 7], ['Postura (ensamble)', 20], ['Transporte sin auxiliar (acarreo)', 7]]) {
    assert.ok(html.includes(`${label}</span><strong>${count}</strong>`), `${label}: ${count}`);
  }
  const figures = html.match(/<figure/g) ?? [];
  assert.equal(figures.length, 2);
  assert.match(html, /<figcaption/);
  assert.match(html, /<ul/);
  const chart = load('components/GraficaDashboard.tsx').GraficaDashboard;
  const zero = renderToStaticMarkup(runtime.jsx(chart, { titulo: 'Vacío', datos: [{ etiqueta: 'Cero', valor: 0 }] }));
  assert.match(zero, /Cero/); assert.match(zero, />0</); assert.ok(!zero.includes('NaN'));
  const unknown = page('pages/Dashboard.tsx', { data: { ...metrics, niveles: { ...metrics.niveles, futuro: 4 }, tipos_tarea: { tarea_nueva: 3 } } });
  assert.match(renderToStaticMarkup(unknown.tree), /tarea_nueva/);
});

// Persistent hook slots exercise the real chart handlers without a browser.
function chartProbe(datos) {
  const slots = []; let cursor = 0;
  const { GraficaDashboard } = load('components/GraficaDashboard.tsx', {
    react: { useState: initial => {
      const slot = cursor++;
      if (!(slot in slots)) slots[slot] = initial;
      return [slots[slot], value => { slots[slot] = typeof value === 'function' ? value(slots[slot]) : value; }];
    } },
  });
  return { render(next = datos) { cursor = 0; return GraficaDashboard({ titulo: 'Distribución', datos: next }); } };
}
const segments = tree => nodes(tree, 'circle').filter(n => n.props.pathLength === 100);
const detail = tree => nodes(tree, 'div').find(n => n.props.className === 'grafica-centro');

test('donut geometry reflects displayed counts and percentages without changing visible semantic data', () => {
  const data = [{ etiqueta: 'Uno', valor: 3 }, { etiqueta: 'Dos', valor: 1 }, { etiqueta: 'Cero', valor: 0 }];
  const tree = chartProbe(data).render();
  assert.equal(nodes(tree, 'svg').length, 1);
  assert.deepEqual(segments(tree).map(n => n.props.strokeDasharray), ['75 25', '25 75']);
  assert.deepEqual(segments(tree).map(n => n.props.strokeDashoffset), [0, -75]);
  assert.match(text(detail(tree)), /Total.*4/);
  assert.equal(nodes(tree, 'li').length, 3);
  for (const [i, expected] of ['75%', '25%', '0%'].entries()) {
    assert.match(text(nodes(tree, 'li')[i]), new RegExp(expected));
    assert.equal(text(nodes(nodes(tree, 'li')[i], 'strong')[0]), String(data[i].valor));
    assert.ok(text(nodes(tree, 'li')[i]).includes(data[i].etiqueta));
  }
});

test('native legend buttons select details, toggle off and reset without hiding other values', () => {
  const probe = chartProbe([{ etiqueta: 'Uno', valor: 3 }, { etiqueta: 'Dos', valor: 1 }]);
  let tree = probe.render();
  const category = (t, label) => nodes(t, 'button').find(n => text(n).includes(label));
  for (const label of ['Uno', 'Dos']) {
    const button = category(tree, label);
    assert.equal(button.props.type, 'button');
    assert.equal(button.props['aria-pressed'], false);
    assert.equal(button.props.tabIndex, undefined, 'native keyboard activation, no custom key trapping');
  }
  category(tree, 'Dos').props.onClick(); tree = probe.render();
  assert.equal(category(tree, 'Dos').props['aria-pressed'], true);
  assert.match(text(detail(tree)), /Dos.*1.*25%/);
  assert.equal(segments(tree)[1].props.className, 'grafica-segmento seleccionado');
  assert.match(text(tree), /Uno3.*75%/);
  category(tree, 'Dos').props.onClick(); tree = probe.render();
  assert.match(text(detail(tree)), /Total.*4/);
  category(tree, 'Uno').props.onClick(); tree = probe.render();
  category(tree, 'Ver total').props.onClick(); tree = probe.render();
  assert.match(text(detail(tree)), /Total.*4/);
  category(tree, 'Uno').props.onClick();
  tree = probe.render([{ etiqueta: 'Otra', valor: 2 }]);
  assert.match(text(detail(tree)), /Total.*2/, 'removed selection cannot show stale detail');
});

test('empty, zero, single and malformed inputs never invent slices or percentages', () => {
  const empty = chartProbe([]).render();
  assert.match(text(empty), /Sin datos para esta distribución/);
  assert.equal(segments(empty).length, 0);
  const zero = chartProbe([{ etiqueta: 'Cero', valor: 0 }]).render();
  assert.equal(segments(zero).length, 0);
  assert.match(text(zero), /Sin casos en esta distribución/);
  assert.match(text(nodes(zero, 'li')[0]), /Cero0.*0%/);
  const single = chartProbe([{ etiqueta: 'Única', valor: 9 }]).render();
  assert.equal(segments(single).length, 1);
  assert.equal(segments(single)[0].props.strokeDasharray, '100 0');
  assert.match(text(single), /100%/);
  for (const value of [NaN, Infinity, -1, Number.MAX_VALUE]) {
    const tree = chartProbe([{ etiqueta: 'Inválida', valor: value }, { etiqueta: 'Otra', valor: Number.MAX_VALUE }]).render();
    assert.equal(segments(tree).length, 0);
    assert.match(text(tree), /No se puede representar esta distribución/);
    assert.ok(!/NaN|Infinity/.test(renderToStaticMarkup(tree)));
    assert.ok(!text(tree).includes('%'), 'unavailable distribution must not fabricate percentages');
  }
});

test('risk and task calls retain the shared chart contract and exact supplied risk colors', () => {
  const p = page('pages/Dashboard.tsx', { data: metrics });
  const charts = nodes(p.tree, 'div').find(n => n.props.className === 'dashboard-graficas').props.children;
  assert.equal(charts.length, 2);
  assert.equal(charts[0].type, charts[1].type);
  assert.deepEqual(charts[0].props.datos.map(d => [d.etiqueta, d.valor, d.color]), [
    ['Sin evaluar', 2, '#8A9EB4'], ['Inapreciable', 1, '#8A9EB4'], ['Bajo', 3, '#2E9E5B'],
    ['Medio', 6, '#E0B000'], ['Alto', 8, '#E8790C'], ['Muy alto', 7, '#D93A3A'],
  ]);
  const risk = chartProbe(charts[0].props.datos).render();
  assert.deepEqual(segments(risk).map(n => n.props.stroke), charts[0].props.datos.map(d => d.color));
  const tasks = chartProbe(charts[1].props.datos).render();
  assert.equal(new Set(segments(tasks).map(n => n.props.stroke)).size, 2);
  assert.deepEqual(segments(tasks).map(n => n.props.stroke), ['var(--jabil-navy)', 'var(--jabil-cyan)']);
});

test('pagination requests its own page, preserves stable backend order, and exposes bounded callbacks', async () => {
  const items = [{ id_caso: 'C001', estacion: 'A', tipo_tarea: 'postura', fecha: '2025-01-01', nivel: 'bajo', reba_final: 2, decisiones_pendientes: 0 }, { id_caso: 'C002', estacion: 'B', tipo_tarea: 'postura', fecha: '2025-01-01', nivel: 'alto', reba_final: 8, decisiones_pendientes: 1 }];
  const p = page('pages/Bandeja.tsx', { data: { items, total: 27, page: 1, page_size: 10, total_pages: 3 } });
  assert.deepEqual(p.calls.map(c => c.queryKey), [['casos', 'pagina', 1, 10]]);
  assert.deepEqual(await p.calls[0].queryFn(), [1, 10]);
  assert.deepEqual(nodes(p.tree, Link).filter(n => /^\/casos\/C/.test(n.props.to)).map(n => n.props.to), ['/casos/C001', '/casos/C002']);
  const button = label => nodes(p.tree, 'button').find(n => text(n).includes(label));
  assert.equal(button('Anterior').props.disabled, true);
  button('Siguiente').props.onClick(); p.render();
  assert.deepEqual(p.calls[0].queryKey, ['casos', 'pagina', 2, 10]);
  button('Anterior').props.onClick(); p.render();
  nodes(p.tree, 'select')[0].props.onChange({ target: { value: '25' } }); p.render();
  assert.deepEqual(p.calls[0].queryKey, ['casos', 'pagina', 1, 25]);
  assert.equal(nodes(p.tree, 'select')[0].props['aria-label'], 'Casos por página');
  const last = page('pages/Bandeja.tsx', { data: { items: [], total: 27, total_pages: 3 } }, 'page=3&page_size=10');
  assert.equal(nodes(last.tree, 'button').find(n => text(n).includes('Siguiente')).props.disabled, true);
  last.render({ data: { items: [], total: 2, total_pages: 1 } }); last.render();
  assert.deepEqual(last.calls[0].queryKey, ['casos', 'pagina', 1, 10]);
  last.render(); assert.equal(last.search.get('page'), '1', 'shrink converges without a loop');
  const invalid = page('pages/Bandeja.tsx', { data: { items: [], total: 0, total_pages: 0 } }, 'page=-2&page_size=1000');
  assert.deepEqual(invalid.calls[0].queryKey, ['casos', 'pagina', 1, 10]);
});

test('dashboard and cases distinguish loading, retryable error and empty states', () => {
  for (const file of ['pages/Dashboard.tsx', 'pages/Bandeja.tsx']) {
    const p = page(file, { isLoading: true });
    assert.match(text(p.tree), /Cargando/);
    p.render({ error: new Error('Fallo de prueba') });
    assert.match(text(p.tree), /Fallo de prueba/);
    nodes(p.tree, 'button').find(n => text(n).includes('Reintentar')).props.onClick();
    assert.equal(p.refetches, 1);
    p.render({ data: file.includes('Dashboard') ? { ...metrics, total_casos: 0, niveles: {}, tipos_tarea: {} } : { items: [], total: 0, total_pages: 0 } });
    assert.match(text(p.tree), /No hay casos/);
  }
});

function client(mock, fixtures) {
  return load('api.ts', {
    './lib/config': { API_URL: '/api', USE_MOCK: mock },
    './lib/sesion': { actorActual: () => ({ usuario: 'Especialista', rol: 'ergonomia' }) },
    ...(fixtures ? { './mocks/data': { casosMock: fixtures, alertasMock: [] } } : {}),
  });
}

test('real client uses additive URLs and envelopes and preserves legacy list, detail, media and errors', async () => {
  const { api, urlImagen } = client(false);
  const requests = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    requests.push([url, init]);
    const body = url.endsWith('/metricas/dashboard') ? metrics
      : url.endsWith('/casos') ? [] : { items: [], total: 0, page: 2, page_size: 25, total_pages: 0 };
    return { ok: true, json: async () => body };
  };
  try {
    assert.deepEqual(await api.listarCasosPaginados(2, 25), { items: [], total: 0, page: 2, page_size: 25, total_pages: 0 });
    assert.deepEqual(await api.metricasDashboard(), metrics);
    assert.deepEqual(await api.listarCasos(), []);
    await api.obtenerCaso('A/B');
    assert.deepEqual(requests.map(r => r[0]), ['/api/casos/pagina?page=2&page_size=25', '/api/metricas/dashboard', '/api/casos', '/api/casos/A%2FB']);
    assert.equal(urlImagen('/media/a.jpg'), '/api/media/a.jpg');
    assert.equal(urlImagen('https://example.test/a.jpg'), 'https://example.test/a.jpg');
    globalThis.fetch = async () => ({ ok: false, status: 422, text: async () => JSON.stringify({ detail: 'Página inválida' }) });
    await assert.rejects(api.listarCasosPaginados(0, 10), /Página inválida/);
  } finally { globalThis.fetch = original; }
});

test('mock computes honest global aggregates and ordered pages, validates boundaries without changing cases or audit', async () => {
  const fixture = (id, nivel, tipo_tarea, recomendaciones = []) => ({ id_caso: id, estacion: id, tipo_tarea, fecha: '2025-01-01', reba: nivel ? { final: 8, nivel } : null, recomendaciones });
  const { api } = client(true, [fixture('C003', null, 'postura'), fixture('C001', 'alto', 'transporte', [{ estado: 'propuesta', implementacion: null }]), fixture('C002', 'bajo', 'postura', [{ estado: 'aprobada', implementacion: 'pendiente_autorizacion' }])]);
  const all = await api.listarCasos(); const audit = await api.bitacora();
  assert.deepEqual(await api.listarCasosPaginados(1, 2), { items: [all[1], all[2]], total: 3, page: 1, page_size: 2, total_pages: 2 });
  assert.deepEqual((await api.listarCasosPaginados(2, 2)).items, [all[0]]);
  assert.deepEqual((await api.listarCasosPaginados(3, 2)).items, []);
  assert.equal((await api.listarCasosPaginados(1, 100)).items.length, 3);
  assert.equal((await api.listarCasosPaginados(1, 1)).items.length, 1);
  const expected = { total_casos: 3, niveles: { sin_evaluar: 1, inapreciable: 0, bajo: 1, medio: 0, alto: 1, muy_alto: 0 }, tipos_tarea: { transporte: 1, postura: 2 }, decisiones_pendientes: 1, por_autorizar: 1 };
  assert.deepEqual(await api.metricasDashboard(), expected);
  for (const [page, size] of [[0, 10], [-1, 10], [1.5, 10], [1, 0], [1, 101], [1, 1.5], [NaN, 10], [1, Infinity]]) await assert.rejects(api.listarCasosPaginados(page, size));
  assert.deepEqual(await api.listarCasos(), all);
  assert.deepEqual(await api.bitacora(), audit);
  assert.deepEqual(await api.metricasDashboard(), expected);
  const empty = client(true, []).api;
  assert.deepEqual(await empty.listarCasosPaginados(1, 10), { items: [], total: 0, page: 1, page_size: 10, total_pages: 0 });
  assert.equal((await empty.metricasDashboard()).total_casos, 0);
});
