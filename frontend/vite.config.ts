import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const backendPort = process.env.VITE_BACKEND_PORT || process.env.BACKEND_PORT || env.VITE_BACKEND_PORT || env.BACKEND_PORT || "8080";
  const defaultProxyTarget = `http://localhost:${backendPort}`;
  const proxyTarget = process.env.VITE_BACKEND_PROXY_TARGET || env.VITE_BACKEND_PROXY_TARGET || defaultProxyTarget;
  const rutasHibridas = ["/casos", "/alertas", "/bitacora"];
  const rutasApiPuras = ["/rag", "/media", "/vision", "/catalogo", "/salud", "/metricas"];

  return {
    plugins: [react()],
    server: {
      port: Number(process.env.VITE_PORT || process.env.FRONTEND_PORT || env.VITE_PORT || env.FRONTEND_PORT || 5180),
      host: process.env.VITE_HOST || process.env.HOST || env.VITE_HOST || env.HOST || undefined,
      proxy: {
        ...Object.fromEntries(
          rutasHibridas.map(ruta => [
            ruta,
            {
              target: proxyTarget,
              changeOrigin: true,
              bypass: req => (req.headers.accept?.includes("text/html") ? "/index.html" : undefined),
            },
          ]),
        ),
        ...Object.fromEntries(
          rutasApiPuras.map(ruta => [
            ruta,
            { target: proxyTarget, changeOrigin: true },
          ]),
        ),
      },
    },
  };
});
