import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const backendPort = env.VITE_BACKEND_PORT || env.BACKEND_PORT || "8000";
  const defaultProxyTarget = `http://localhost:${backendPort}`;
  const proxyTarget = env.VITE_BACKEND_PROXY_TARGET || defaultProxyTarget;
  const rutasProxy = ["/casos", "/alertas", "/bitacora", "/rag", "/media", "/vision", "/catalogo", "/salud", "/metricas"];

  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_PORT || 5173),
      host: env.VITE_HOST || env.HOST || undefined,
      proxy: Object.fromEntries(
        rutasProxy.map(ruta => [
          ruta,
          {
            target: proxyTarget,
            changeOrigin: true,
            // /casos/C-001 es a la vez página de la app y ruta de la API: si el navegador pide la página
            // (F5 o enlace directo), se sirve la app; solo las llamadas de datos van al backend.
            bypass: (req: { headers: Record<string, string | string[] | undefined> }) => {
              const accept = String(req.headers.accept ?? "");
              return accept.includes("text/html") ? "/index.html" : undefined;
            },
          },
        ]),
      ),
    },
  };
});
