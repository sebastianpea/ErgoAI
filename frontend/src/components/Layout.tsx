import { useEffect, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { USE_MOCK } from "../lib/config";
import { PERFILES, cambiarRol, useSesion } from "../lib/sesion";
import type { Rol } from "../types/caso";
import logoJabil from "../assets/jabil-logo.svg";

/** Sin login en el prototipo: el rol activo define qué acciones se muestran y queda en la bitácora. */
function SelectorRol() {
  const { rol, usuario } = useSesion();
  return (
    <label className="selector-rol" title={PERFILES[rol].descripcion}>
      <span className="selector-rol-usuario">{usuario}</span>
      <select value={rol} onChange={e => cambiarRol(e.target.value as Rol)} aria-label="Rol activo">
        {(Object.keys(PERFILES) as Rol[]).map(r => <option key={r} value={r}>{PERFILES[r].etiqueta}</option>)}
      </select>
    </label>
  );
}

export function Layout() {
  const { data: alertas } = useQuery({ queryKey: ["alertas"], queryFn: api.listarAlertas });
  const nuevas = alertas?.filter(a => a.estado === "nueva").length ?? 0;
  const [compacta, setCompacta] = useState(false);
  const [menuAbierto, setMenuAbierto] = useState(false);
  const { pathname } = useLocation();

  useEffect(() => {
    const alDesplazar = () => setCompacta(window.scrollY > 8);
    alDesplazar();
    window.addEventListener("scroll", alDesplazar, { passive: true });
    return () => window.removeEventListener("scroll", alDesplazar);
  }, []);

  useEffect(() => setMenuAbierto(false), [pathname]);

  useEffect(() => {
    if (!menuAbierto) return;
    const alTeclear = (e: KeyboardEvent) => e.key === "Escape" && setMenuAbierto(false);
    window.addEventListener("keydown", alTeclear);
    return () => window.removeEventListener("keydown", alTeclear);
  }, [menuAbierto]);

  const enlaces = (
    <>
      <NavLink to="/" end>Dashboard</NavLink>
      <NavLink to="/casos">Casos</NavLink>
      <NavLink to="/alertas">
        Alertas{nuevas > 0 && <span className="globo" aria-label={`${nuevas} nuevas`}>{nuevas}</span>}
      </NavLink>
      <NavLink to="/bitacora">Bitácora</NavLink>
    </>
  );

  return (
    <div className="app">
      <a className="saltar" href="#contenido">Saltar al contenido</a>
      <header className={`barra${compacta ? " compacta" : ""}`}>
        <div className="barra-interior">
          <NavLink to="/" className="marca" aria-label="ErgoAI, inicio">
            <img src={logoJabil} alt="Jabil" className="logo-jabil" />
            <span className="separador" aria-hidden />
            <span className="producto">Ergo<b>AI</b></span>
          </NavLink>
          <nav className="nav-principal" aria-label="Principal">{enlaces}</nav>
          <span className="usuario">
            {USE_MOCK && <span className="mock">Datos simulados</span>}
            <SelectorRol />
          </span>
          <button
            className="hamburguesa" aria-label="Abrir menú" aria-expanded={menuAbierto}
            aria-controls="menu-movil" onClick={() => setMenuAbierto(true)}
          >
            <span /><span /><span />
          </button>
        </div>
      </header>

      <div id="menu-movil" className={`menu-movil${menuAbierto ? " abierto" : ""}`} hidden={!menuAbierto}>
        <button className="cerrar" aria-label="Cerrar menú" onClick={() => setMenuAbierto(false)}>×</button>
        <nav aria-label="Principal (móvil)">{enlaces}</nav>
        <div className="rol-movil"><SelectorRol /></div>
        <p className="tagline"><span>MADE</span> POSSIBLE. <span>MADE</span> BETTER.</p>
      </div>

      <main id="contenido">
        <Outlet />
      </main>

      <footer className="pie">
        <div className="pie-interior">
          <div>
            <p className="pie-producto">Ergo<b>AI</b></p>
            <p className="pie-texto">Copiloto de auditoría ergonómica · REBA · NOM-036-1-STPS-2018 · 16-PE30-6500-00023</p>
          </div>
          <p className="tagline"><span>MADE</span> POSSIBLE. <span>MADE</span> BETTER.</p>
        </div>
        <p className="pie-nota">
          Uso exclusivo de ergonomía, IE y EHS. Las decisiones las toma el especialista; nada se notifica al operador.
        </p>
      </footer>
    </div>
  );
}
