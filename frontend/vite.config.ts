import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const backendPort = env.VITE_BACKEND_PORT || env.BACKEND_PORT || "8000";
  const defaultProxyTarget = `http://localhost:${backendPort}`;
  const proxyTarget = env.VITE_BACKEND_PROXY_TARGET || defaultProxyTarget;
  const rutasProxy = ["/casos", "/alertas", "/bitacora", "/rag", "/media", "/vision", "/catalogo", "/salud"];

  return {
    plugins: [react()],
    server: {
      port: Number(env.VITE_PORT || 5173),
      host: env.VITE_HOST || env.HOST || undefined,
      proxy: Object.fromEntries(
        rutasProxy.map(ruta => [
          ruta,
          { target: proxyTarget, changeOrigin: true },
        ]),
      ),
    },
  };
});
