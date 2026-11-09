// Por defecto se usa ruta relativa (resuelta por el proxy de Vite en desarrollo o Nginx en Docker)
// o VITE_API_URL si se define explícitamente; el modo simulado se activa con VITE_USE_MOCK=true.
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === "true";
export const API_URL: string = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");
