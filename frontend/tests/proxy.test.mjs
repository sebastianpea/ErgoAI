import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { createServer as createHttpServer } from 'node:http';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { pathToFileURL } from 'node:url';

const require = createRequire(new URL('../package.json', import.meta.url));
const ts = require('typescript');
const { createServer } = await import(new URL('./dist/node/index.js', pathToFileURL(require.resolve('vite/package.json'))).href);
const prefixes = ['casos', 'alertas', 'bitacora', 'rag', 'media', 'vision', 'catalogo', 'salud', 'metricas'];
const html = '<!doctype html><html><body>Proxy test SPA</body></html>';

// Execute the real config without reading local .env files or loading application data.
// Only environment/plugin loading is isolated; Vite handles HTTP and proxying itself.
function config(target) {
  const source = readFileSync(new URL('../vite.config.ts', import.meta.url), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  const mod = { exports: {} };
  new Function('require', 'module', 'exports', code)(name => {
    if (name === 'vite') return { defineConfig: value => value, loadEnv: () => ({ VITE_BACKEND_PROXY_TARGET: target }) };
    if (name === '@vitejs/plugin-react') return { default: () => [] };
    throw new Error(`Unexpected config import: ${name}`);
  }, mod, mod.exports);
  return mod.exports.default({ mode: 'test' });
}

async function snapshot(origin, path, accept = '*/*') {
  const response = await fetch(origin + path, { headers: { accept }, signal: AbortSignal.timeout(5000) });
  return { status: response.status, type: response.headers.get('content-type'), body: await response.text() };
}

function expected(path) {
  return { status: 200, type: 'application/json', body: JSON.stringify({ path, fixture: 'proxy-only' }) };
}

async function withProxy(run) {
  const root = await mkdtemp(join(tmpdir(), 'ergoai-proxy-'));
  const backend = createHttpServer((request, response) => {
    response.writeHead(200, { 'Content-Type': 'application/json' });
    response.end(expected(request.url).body);
  });
  let vite;
  try {
    await writeFile(join(root, 'index.html'), html);
    await new Promise((resolve, reject) => {
      backend.once('error', reject);
      backend.listen(0, '127.0.0.1', resolve);
    });
    const options = config(`http://127.0.0.1:${backend.address().port}`);
    vite = await createServer({
      ...options, root, configFile: false, envFile: false, cacheDir: join(root, 'cache'),
      optimizeDeps: { noDiscovery: true, include: [] },
      server: { ...options.server, host: '127.0.0.1', port: 0, open: false, watch: null },
    });
    await vite.listen();
    await run(`http://127.0.0.1:${vite.httpServer.address().port}`);
  } finally {
    try { await vite?.close(); }
    finally {
      backend.closeAllConnections();
      await new Promise(resolve => backend.close(resolve));
      await rm(root, { recursive: true, force: true });
    }
  }
}

test('actual Vite proxy returns metrics JSON, never the successful HTML SPA fallback', async () => {
  await withProxy(async origin => {
    for (const path of ['/metricas/dashboard', '/metricas/impacto']) {
      assert.deepEqual(await snapshot(origin, path), expected(path), path);
    }
  });
});

test('existing namespaces preserve path/query and document requests; real frontend routes retain SPA fallback', async () => {
  await withProxy(async origin => {
    for (const prefix of prefixes.filter(value => value !== 'metricas')) {
      const path = `/${prefix}/proxy-fixture?pagina=2`;
      assert.deepEqual(await snapshot(origin, path), expected(path), path);
    }
    // /casos has always been proxied, including browser navigations: do not change that contract here.
    for (const path of ['/casos', '/casos/PROXY-FIXTURE/plan', '/casos/PROXY-FIXTURE/informe']) {
      assert.deepEqual(await snapshot(origin, path, 'text/html'), expected(path), path);
    }
    for (const path of ['/', '/frontend-proxy-fixture']) {
      const response = await snapshot(origin, path, 'text/html');
      assert.equal(response.status, 200);
      assert.equal(response.type, 'text/html');
      assert.match(response.body, /<body>Proxy test SPA<\/body>/);
    }
  });
});

test('Nginx matches the API namespaces without rewriting proxy paths and retains SPA fallback', () => {
  const source = readFileSync(new URL('../nginx.conf', import.meta.url), 'utf8');
  const location = source.match(/location\s+~\s+(\S+)\s*\{([^}]+)\}/);
  assert.ok(location, 'bounded regex proxy location');
  const pattern = new RegExp(location[1]);
  for (const prefix of prefixes) {
    for (const path of [`/${prefix}`, `/${prefix}/proxy-fixture`]) assert.ok(pattern.test(path), path);
    assert.equal(pattern.test(`/${prefix}-frontend`), false);
  }
  for (const path of ['/metricas/dashboard', '/metricas/impacto', '/casos/PROXY-FIXTURE/plan']) assert.ok(pattern.test(path), path);
  for (const path of ['/', '/frontend-proxy-fixture']) assert.equal(pattern.test(path), false);
  assert.match(location[2], /proxy_pass\s+http:\/\/backend:8000\s*;/);
  assert.doesNotMatch(location[2], /\brewrite\b/);
  assert.match(location[2], /proxy_http_version\s+1\.1\s*;/);
  assert.match(location[2], /proxy_set_header Host \$host;/);
  assert.match(source, /location\s+\/\s*\{\s*try_files \$uri \$uri\/ \/index\.html;/);
});
