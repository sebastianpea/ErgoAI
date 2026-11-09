// Sesión del prototipo (sin login): el rol activo se elige en la barra y se recuerda en este navegador.
import { useSyncExternalStore } from "react";
import type { Actor, Rol } from "../types/caso";

export const PERFILES: Record<Rol, { usuario: string; etiqueta: string; descripcion: string }> = {
  ergonomia: {
    usuario: import.meta.env.VITE_USER_ERGONOMIA ?? "Ing. Ergonomía",
    etiqueta: "Ergonomía",
    descripcion: "Revisa el análisis y aprueba, edita o rechaza recomendaciones",
  },
  ingenieria: {
    usuario: import.meta.env.VITE_USER_INGENIERIA ?? "Ing. Procesos (IE)",
    etiqueta: "Ingeniería (IE/Facilities)",
    descripcion: "Autoriza o deniega los cambios en planta",
  },
};

const CLAVE = "ergoai.rol";
const oyentes = new Set<() => void>();

function leer(): Rol {
  try {
    const v = localStorage.getItem(CLAVE);
    return v === "ingenieria" ? "ingenieria" : "ergonomia";
  } catch {
    return "ergonomia";
  }
}

let rolActual: Rol = leer();

export function cambiarRol(rol: Rol) {
  rolActual = rol;
  try {
    localStorage.setItem(CLAVE, rol);
  } catch {
    // almacenamiento bloqueado: el rol solo dura esta pestaña
  }
  oyentes.forEach(f => f());
}

export function actorActual(): Actor {
  return { rol: rolActual, usuario: PERFILES[rolActual].usuario };
}

export function useSesion(): Actor & { esErgonomia: boolean; esIngenieria: boolean } {
  const rol = useSyncExternalStore(
    f => { oyentes.add(f); return () => oyentes.delete(f); },
    () => rolActual,
  );
  return { rol, usuario: PERFILES[rol].usuario, esErgonomia: rol === "ergonomia", esIngenieria: rol === "ingenieria" };
}
