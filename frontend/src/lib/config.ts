// Por defecto se usa el backend real; el modo simulado se activa explícitamente (npm run dev:mock).
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
export const API_URL: string = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/+$/, "");
