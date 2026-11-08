"""
Servicio de casos: orquesta visión (keypoints → ángulos), motores deterministas (REBA, NOM-036,
riesgo residual), reglas Jabil, validación Human-in-the-Loop, bitácora y alertas.
Toda la persistencia es en archivos JSON del workspace (sin base de datos).

Flujo de una recomendación:
    propuesta ──(ergonomía aprueba/edita)──► aprobada
        ├─ postura / administrativo ─────────────────────────► por_implementar ──► implementada
        └─ cambio en planta ─► pendiente_autorizacion ─(ingeniería autoriza)─► por_implementar ──► implementada
                                                     └─(ingeniería deniega)──► denegada
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.api.schemas import (
    Actor, Alerta, Angulo, Autorizacion, CasoAlmacenado, CasoDetalle, CasoImpacto, CasoResumen, CorreccionContexto,
    CorreccionNom036, CorreccionReferencia, Decision, Impacto, Nom036Captura,
    Descarte, Hallazgo, Imagen, Implementacion, NuevaRecomendacion, NuevoCaso, Punto, Recomendacion, RecomendacionAlmacenada,
    Residual, ResultadoIntegridad, ResultadoNom036, ResultadoReba, RevisionHallazgo, SegmentoResidual, Validacion,
    Vista,
)
from backend.app.core_ergonomics.angle_geometry import extraer_angulos_laterales, medir_vista_frontal
from backend.app.core_ergonomics.cambios import (
    PARAMETROS, describir_contexto, dict_a_efecto, efecto_a_cambios, efecto_a_dict,
)
from backend.app.core_ergonomics.modelos import SEGMENTOS, AnguloMedido, Efecto, Segmento
from backend.app.core_ergonomics.nom036_calculator import color_total, total_factores, validar_captura
from backend.app.core_ergonomics.reba_calculator import RebaCalculator, ResultadoRebaCalculado
from backend.app.core_ergonomics.residual_simulator import simular
from backend.app.session_store import (
    AuditActionEnum, AuditFileManager, BitacoraLedger, ControlHierarchyEnum, EntradaBitacora, NormativeConfigLoader,
    RecommendationSnapshot, SessionStatusEnum,
)
from backend.app.core_ergonomics.generador_recomendaciones import generar
from backend.app.settings import (
    CONFIANZA_MINIMA, FUENTE_EVALUACION_MANUAL, MAX_FOTO_MB, MINUTOS_EVALUACION_MANUAL, TOLERANCIA_UMBRAL_GRADOS,
)
from backend.app.vision.estimador import VisionNoDisponible, estimador

log = logging.getLogger("ergoai.casos")

USUARIO_SISTEMA = "sistema"
ETIQUETA_SEGMENTO: Dict[Segmento, str] = {
    "tronco": "Tronco", "cuello": "Cuello", "piernas": "Piernas",
    "brazo": "Brazo", "antebrazo": "Antebrazo", "muneca": "Muñeca",
}
ETIQUETA_NIVEL = {
    "inapreciable": "inapreciable", "bajo": "bajo", "medio": "medio", "alto": "alto", "muy_alto": "muy alto",
}
ACCION_AUDITORIA = {
    "aprobar": AuditActionEnum.APPROVED, "editar": AuditActionEnum.EDITED, "rechazar": AuditActionEnum.REJECTED,
}
JERARQUIA = {"ingenieria": ControlHierarchyEnum.INGENIERIA, "administrativo": ControlHierarchyEnum.ADMINISTRATIVO}
TAREAS_CON_LEVANTAMIENTO = ("levantamiento", "transporte")
ETIQUETA_ROL = {"ergonomia": "Ergonomía", "ingenieria": "Ingeniería (IE/Facilities)"}


class NoEncontrado(Exception):
    pass


class Conflicto(Exception):
    pass


class DatosInvalidos(Exception):
    pass


class Prohibido(Exception):
    """La acción no corresponde al rol que la solicita."""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _efecto_vacio(e: Efecto) -> bool:
    return e == Efecto()


def _exigir_rol(actor: Actor, rol: str, accion: str) -> None:
    if actor.rol != rol:
        raise Prohibido(f"Solo {ETIQUETA_ROL[rol]} puede {accion}")


def _valor_legible(clave: str, v: object) -> str:
    if isinstance(v, bool):
        return "sí" if v else "no"
    unidad = PARAMETROS[clave].unidad
    return f"{v:g}{'°' if unidad == '°' else f' {unidad}' if unidad else ''}" if isinstance(v, (int, float)) else str(v)


def _describir_efecto(e: Efecto) -> str:
    d = efecto_a_dict(e)
    return "; ".join(f"{PARAMETROS[k].etiqueta}: {_valor_legible(k, v)}" for k, v in d.items()) or "sin cambios modelados"


class ServicioCasos:
    ARCHIVO_CASO = "caso.json"
    ARCHIVO_ALERTAS = "alertas.json"

    def __init__(self, mgr: AuditFileManager, config: NormativeConfigLoader):
        self.mgr = mgr
        self.ledger = BitacoraLedger(mgr)
        self.config = config
        self.reba = RebaCalculator(config.get_reba_tables())
        self._lock = threading.RLock()

    # ================= Persistencia =================

    def _ruta_caso(self, id_caso: str) -> Path:
        try:
            return self.mgr.get_case_dir(id_caso) / self.ARCHIVO_CASO
        except ValueError as e:
            raise NoEncontrado(f"Caso {id_caso} no encontrado") from e

    def _cargar(self, id_caso: str) -> CasoAlmacenado:
        ruta = self._ruta_caso(id_caso)
        if not ruta.exists():
            raise NoEncontrado(f"Caso {id_caso} no encontrado")
        with open(ruta, "r", encoding="utf-8") as f:
            return CasoAlmacenado.model_validate(json.load(f))

    def _guardar(self, caso: CasoAlmacenado) -> None:
        self.mgr.write_json_atomic(self._ruta_caso(caso.id_caso), caso.model_dump(mode="json"))

    def _ids(self) -> List[str]:
        return [i for i in self.mgr.list_cases() if self._ruta_caso(i).exists()]

    @property
    def _ruta_alertas(self) -> Path:
        return self.mgr.workspace_root / self.ARCHIVO_ALERTAS

    def _cargar_alertas(self) -> List[Alerta]:
        if not self._ruta_alertas.exists():
            return []
        with open(self._ruta_alertas, "r", encoding="utf-8") as f:
            return [Alerta.model_validate(a) for a in json.load(f)]

    def _guardar_alertas(self, alertas: List[Alerta]) -> None:
        self.mgr.write_json_atomic(self._ruta_alertas, [a.model_dump(mode="json") for a in alertas])

    @staticmethod
    def _buscar_rec(caso: CasoAlmacenado, id_rec: str) -> RecomendacionAlmacenada:
        rec = next((r for r in caso.recomendaciones if r.id == id_rec), None)
        if rec is None:
            raise NoEncontrado(f"Recomendación {id_rec} no encontrada en {caso.id_caso}")
        return rec

    def _verificar_cadenas(self, id_caso: str) -> None:
        """Verificar ambas cadenas antes de mutar para no dejar estados a medias."""
        self.mgr.load_audit_trail(id_caso, verify=True)
        verif = self.ledger.verificar()
        if not verif.ok:
            raise Conflicto(f"Bitácora comprometida: {verif.detalle}")

    # ================= Semilla =================

    def sembrar_si_vacio(self, ruta_semilla: Path) -> int:
        """Crea los casos de demostración si el workspace no tiene ninguno. Devuelve cuántos creó."""
        with self._lock:
            if self._ids():
                return 0
            with open(ruta_semilla, "r", encoding="utf-8") as f:
                semilla = json.load(f)
            imagen_origen = ruta_semilla.parent / semilla["imagen_placeholder"]

            if not self._ruta_alertas.exists():
                self._guardar_alertas([Alerta.model_validate(a) for a in semilla.get("alertas", [])])

            for datos in semilla["casos"]:
                id_caso = datos["id_caso"]
                imagenes = []
                for vista in ("lateral", "frontal", "cenital"):
                    esq = semilla["esqueletos"][vista]
                    imagenes.append({
                        "vista": vista, "url": imagen_origen.name, "ancho": esq["ancho"], "alto": esq["alto"],
                        "puntos": [{"id": i, "x": x, "y": y, "confianza": c, "corregido": False}
                                   for i, x, y, c in esq["puntos"]],
                    })
                recs = [{**r, "texto_ia": r["texto"]} for r in datos.get("recomendaciones", [])]
                caso = CasoAlmacenado.model_validate({**datos, "imagenes": imagenes, "recomendaciones": recs})

                case_dir = self.mgr.init_case_workspace(id_caso)
                shutil.copyfile(imagen_origen, case_dir / "inputs" / imagen_origen.name)
                self._guardar(caso)
                detalle = self._evaluar(caso)
                self.ledger.registrar(USUARIO_SISTEMA, "caso_creado", id_caso, id_caso)
                self.ledger.registrar(
                    USUARIO_SISTEMA, "analisis_ejecutado", id_caso, id_caso,
                    despues=f"REBA {detalle.reba.final if detalle.reba else '—'}",
                )
                self._sincronizar(caso, detalle)
                log.info("Caso semilla creado: %s", id_caso)
            return len(semilla["casos"])

    # ================= Evaluación =================

    def _medir(self, caso: CasoAlmacenado) -> Optional[Dict[Segmento, AnguloMedido]]:
        lateral = next((i for i in caso.imagenes if i.vista == "lateral"), None)
        return extraer_angulos_laterales(lateral.puntos) if lateral else None

    def _calcular_reba(self, caso: CasoAlmacenado) -> Optional[tuple[Dict[Segmento, AnguloMedido], ResultadoRebaCalculado]]:
        medidos = self._medir(caso)
        if medidos is None:
            return None
        return medidos, self.reba.calcular({s: m.grados for s, m in medidos.items()}, caso.contexto)

    def _estado_angulo(self, grados: Optional[float], confianza: float, umbrales: List[float]) -> str:
        if grados is None:
            return "sin_dato"
        if confianza < CONFIANZA_MINIMA or any(abs(grados - u) < TOLERANCIA_UMBRAL_GRADOS for u in umbrales):
            return "revisar"
        return "ok"

    @staticmethod
    def _aplicable(r: RecomendacionAlmacenada) -> bool:
        """Cuenta para el riesgo residual proyectado."""
        return r.estado != "rechazada" and r.implementacion != "denegada" and not _efecto_vacio(r.efecto)

    def _evaluar(self, caso: CasoAlmacenado) -> CasoDetalle:
        ctx = caso.contexto
        jabil = self.config.get_jabil_standards()
        angulos: List[Angulo] = []
        reba: Optional[ResultadoReba] = None
        residual: Optional[Residual] = None
        hallazgos: List[Hallazgo] = list(caso.hallazgos_vision)
        grados: Dict[Segmento, Optional[float]] = {}

        calculo = self._calcular_reba(caso)
        if calculo:
            medidos, res = calculo
            grados = {s: m.grados for s, m in medidos.items()}
            for seg in SEGMENTOS:
                m, ps = medidos[seg], res.segmentos[seg]
                g, confianza = m.grados, m.confianza
                if seg == "muneca" and g is None and ctx.muneca_grados is not None:
                    g, confianza = ctx.muneca_grados, 1.0  # medición manual del especialista
                angulos.append(Angulo(
                    segmento=seg, lado=m.lado, vista="lateral", angulo_grados=g,
                    puntaje_reba=ps.puntaje, modificadores=ps.modificadores,
                    estado=self._estado_angulo(g, confianza, ps.umbrales),
                    puntaje_previo=caso.evaluacion_previa.segmentos.get(seg),
                ))
            reba = ResultadoReba(
                grupo_a=res.grupo_a, grupo_b=res.grupo_b, tabla_c=res.tabla_c, carga=res.carga,
                agarre=res.agarre, actividad=res.actividad, final=res.final, nivel=res.nivel,
            )

            # Auditoría contra la evaluación capturada en piso
            for a in angulos:
                if a.puntaje_previo is not None and a.puntaje_previo != a.puntaje_reba:
                    hallazgos.append(Hallazgo(
                        id=f"AUD-{a.segmento}", origen="auditoria", severidad="advertencia",
                        mensaje=(f"{ETIQUETA_SEGMENTO[a.segmento]}: puntaje capturado en piso {a.puntaje_previo}; "
                                 f"la foto indica {a.puntaje_reba}"),
                    ))
            previo = caso.evaluacion_previa.reba_final
            if previo is not None and previo != res.final:
                cambia_nivel = self.reba.nivel(previo) != res.nivel
                hallazgos.append(Hallazgo(
                    id="AUD-final", origen="auditoria", severidad="critico" if cambia_nivel else "advertencia",
                    mensaje=(f"REBA capturado en piso {previo} ({ETIQUETA_NIVEL[self.reba.nivel(previo)]}); "
                             f"recalculado {res.final} ({ETIQUETA_NIVEL[res.nivel]})"),
                ))

            aplicables = [r for r in caso.recomendaciones if self._aplicable(r)]
            res2 = simular(self.reba, grados, ctx, [r.efecto for r in aplicables])
            residual = Residual(
                antes_final=res.final, antes_nivel=res.nivel, despues_final=res2.final, despues_nivel=res2.nivel,
                segmentos=[SegmentoResidual(segmento=s, antes=res.segmentos[s].puntaje, despues=res2.segmentos[s].puntaje)
                           for s in SEGMENTOS],
                recomendaciones_aplicadas=[r.id for r in aplicables],
            )

        # Reglas corporativas Jabil (prevalece el límite más estricto)
        limite = jabil["load_limits"]["max_single_person_lift_kg"]
        if caso.tipo_tarea in TAREAS_CON_LEVANTAMIENTO and ctx.carga_kg > limite:
            hallazgos.append(Hallazgo(
                id="JABIL-carga", origen="reglas_jabil", severidad="critico",
                mensaje=f"Carga de {ctx.carga_kg:g} kg supera el límite de {limite:g} kg por persona",
                referencia=jabil["references"]["load_limit"],
            ))
        if ctx.altura_trabajo_cm is not None:
            lo, hi = jabil["workstation_geometry"]["recommended_work_height_range_cm"]
            if not lo <= ctx.altura_trabajo_cm <= hi:
                hallazgos.append(Hallazgo(
                    id="JABIL-altura", origen="reglas_jabil", severidad="advertencia",
                    mensaje=f"Altura de trabajo de {ctx.altura_trabajo_cm:g} cm fuera del rango {lo:g}–{hi:g} cm",
                    referencia=jabil["references"]["work_height"],
                ))

        for h in hallazgos:
            h.descartado = caso.hallazgos_descartados.get(h.id)

        nom036 = None
        if caso.nom036:
            total = total_factores(f.valor for f in caso.nom036.factores)
            nom036 = ResultadoNom036(
                metodo=caso.nom036.metodo, total=total, factores=caso.nom036.factores,
                nivel=color_total(total, self.config.get_nom036_tables()),
            )

        recomendaciones = []
        for r in caso.recomendaciones:
            proyectado = None
            if calculo and not _efecto_vacio(r.efecto):
                proyectado = simular(self.reba, grados, ctx, [r.efecto]).final
            base = r.model_dump(exclude={"texto_ia", "efecto", "efecto_ia"})
            recomendaciones.append(Recomendacion(
                **base, cambios=efecto_a_cambios(r.efecto, grados, ctx), reba_proyectado=proyectado,
                requiere_autorizacion=r.tipo_cambio == "planta",
            ))

        return CasoDetalle(
            id_caso=caso.id_caso, estacion=caso.estacion, tipo_tarea=caso.tipo_tarea, fecha=caso.fecha,
            imagenes=[Imagen(**{**i.model_dump(), "url": f"/media/{caso.id_caso}/{i.url}"}) for i in caso.imagenes],
            contexto=ctx, evaluacion_previa=caso.evaluacion_previa, angulos=angulos, reba=reba, nom036=nom036,
            hallazgos=hallazgos, recomendaciones=recomendaciones, residual=residual,
            validacion=self._validacion(caso, reba), metricas=caso.metricas,
        )

    @staticmethod
    def _validacion(caso: CasoAlmacenado, reba: Optional[ResultadoReba]) -> Validacion:
        recs = caso.recomendaciones
        pendientes = sum(r.estado == "propuesta" for r in recs)
        riesgo_alto = reba is not None and reba.nivel in ("alto", "muy_alto")
        ing_aprobada = any(
            r.nivel_control == "ingenieria" and r.estado in ("aprobada", "editada_aprobada")
            and r.implementacion != "denegada"
            for r in recs)
        falta = riesgo_alto and not ing_aprobada
        return Validacion(
            pendientes=pendientes, falta_ingenieria=falta, completa=pendientes == 0 and not falta,
            por_autorizar=sum(r.implementacion == "pendiente_autorizacion" for r in recs),
            por_implementar=sum(r.implementacion == "por_implementar" for r in recs),
            implementadas=sum(r.implementacion == "implementada" for r in recs),
        )

    # ================= Estado de sesión y alertas =================

    def _sincronizar(self, caso: CasoAlmacenado, detalle: CasoDetalle, especialista: Optional[str] = None) -> None:
        self._registrar_hitos(caso, detalle)
        self._sincronizar_estado(caso, detalle, especialista)
        self._sincronizar_alertas(caso, detalle)

    def _registrar_hitos(self, caso: CasoAlmacenado, d: CasoDetalle) -> None:
        """Primera decisión y validación completa: base de la medición de tiempos de respuesta."""
        m, cambio = caso.metricas, False
        if m.primera_decision_en is None and any(r.estado != "propuesta" for r in caso.recomendaciones):
            m.primera_decision_en, cambio = _ahora(), True
        if m.validado_en is None and d.validacion.completa:
            m.validado_en, cambio = _ahora(), True
        if cambio:
            self._guardar(caso)
            d.metricas = m

    def _sincronizar_estado(self, caso: CasoAlmacenado, d: CasoDetalle, especialista: Optional[str]) -> None:
        estado = self.mgr.load_session_state(caso.id_caso)
        if d.reba is None:
            estado.status = SessionStatusEnum.PENDING_ANALYSIS
        elif d.validacion.completa:
            estado.status = SessionStatusEnum.VALIDATED
        else:
            estado.status = SessionStatusEnum.IN_REVIEW
        estado.measured_angles = {a.segmento: a.angulo_grados for a in d.angulos if a.angulo_grados is not None}
        if d.reba:
            banda = next(b for b in self.config.get_reba_tables()["risk_levels"].values()
                         if b["score_range"][0] <= d.reba.final <= b["score_range"][1])
            estado.reba_initial_score = d.reba.final
            estado.reba_initial_risk_level = banda["risk"]
            estado.reba_initial_action_level = f"{banda['action_level']}: {banda['action_description']}"
        estado.nom036_alerts = [h.mensaje for h in d.hallazgos if h.origen == "reglas_jabil" and not h.descartado]
        estado.recommendations = [r.model_dump(mode="json") for r in caso.recomendaciones]
        estado.residual_risk_score = d.residual.despues_final if d.residual else None
        if especialista:
            estado.specialist_id = especialista
        estado.is_validated_by_human = d.validacion.completa
        estado.updated_at_utc = _ahora()
        self.mgr.save_session_state(caso.id_caso, estado)

    def _condiciones_alerta(self, d: CasoDetalle) -> Dict[str, Optional[tuple[str, str]]]:
        """tipo_evento → (urgencia, detalles) si la condición está activa, o None."""
        vigentes = [h for h in d.hallazgos if not h.descartado]
        cond: Dict[str, Optional[tuple[str, str]]] = {}
        alto = d.reba is not None and d.reba.nivel in ("alto", "muy_alto") and not d.validacion.completa
        cond["RIESGO_ALTO_PENDIENTE"] = (
            ("CRITICO" if d.reba.nivel == "muy_alto" else "ALTO",
             f"REBA {d.reba.final} ({ETIQUETA_NIVEL[d.reba.nivel]}) sin validación completa del especialista")
            if alto and d.reba else None)
        aud = [h.mensaje for h in vigentes if h.origen == "auditoria"]
        cond["DISCREPANCIA_EVALUACION"] = ("ALTO", "; ".join(aud)) if aud else None
        rev = [ETIQUETA_SEGMENTO[a.segmento] for a in d.angulos if a.estado == "revisar"]
        cond["ANGULO_POR_REVISAR"] = (
            ("MEDIO", f"Cerca de un umbral REBA o baja confianza: {', '.join(rev)}") if rev else None)
        obj = [h.mensaje for h in vigentes if h.origen == "vision" and h.caja]
        cond["OBJETO_DESCONOCIDO"] = ("MEDIO", "; ".join(obj)) if obj else None
        por_aut = [r.titulo for r in d.recomendaciones if r.implementacion == "pendiente_autorizacion"]
        cond["AUTORIZACION_PENDIENTE"] = (
            ("MEDIO", f"Cambios en planta esperando autorización de ingeniería: {'; '.join(por_aut)}")
            if por_aut else None)
        return cond

    def _sincronizar_alertas(self, caso: CasoAlmacenado, d: CasoDetalle) -> None:
        alertas = self._cargar_alertas()
        por_id = {a.id_alerta: a for a in alertas}
        for tipo, activa in self._condiciones_alerta(d).items():
            id_alerta = f"{caso.id_caso}-{tipo}"
            existente = por_id.get(id_alerta)
            if activa:
                urgencia, detalles = activa
                if existente is None:
                    nueva = Alerta(id_alerta=id_alerta, estacion=caso.estacion, tipo_evento=tipo,
                                   nivel_urgencia=urgencia, detalles=detalles, timestamp=_ahora(),
                                   id_caso=caso.id_caso)
                    alertas.append(nueva)
                    por_id[id_alerta] = nueva
                elif existente.estado != "atendida":
                    existente.nivel_urgencia, existente.detalles = urgencia, detalles
                elif tipo == "AUTORIZACION_PENDIENTE" and existente.detalles != detalles:
                    # Un nuevo cambio en planta espera autorización: se reabre.
                    existente.estado, existente.detalles, existente.timestamp = "nueva", detalles, _ahora()
            elif existente is not None and existente.estado != "atendida":
                existente.estado = "atendida"
                self.ledger.registrar(USUARIO_SISTEMA, "alerta_cerrada", id_alerta, caso.id_caso,
                                      motivo="La condición que la originó ya no se cumple")
        self._guardar_alertas(alertas)

    # ================= Auditoría por caso =================

    def _registrar_auditoria(self, caso: CasoAlmacenado, rec: RecomendacionAlmacenada, accion: AuditActionEnum,
                             usuario: str, motivo: Optional[str], reba_antes: Optional[int],
                             residual_despues: Optional[int], efecto_original: Optional[Efecto] = None) -> None:
        """Evento en audit_trail.json del caso (AuditEvent con cadena SHA-256)."""
        if reba_antes is None or residual_despues is None:
            return  # sin análisis REBA no hay puntajes que auditar
        medidos = self._medir(caso)
        grados = {s: m.grados for s, m in medidos.items()} if medidos else {}

        def proyectado(e: Efecto) -> Optional[int]:
            return simular(self.reba, grados, caso.contexto, [e]).final if medidos and not _efecto_vacio(e) else None

        original_efecto = efecto_original or rec.efecto_ia or rec.efecto
        original = RecommendationSnapshot(
            recommendation_id=rec.id, hierarchy=JERARQUIA[rec.nivel_control],
            description=f"{rec.texto_ia} [{_describir_efecto(original_efecto)}]",
            projected_reba=proyectado(original_efecto),
        )
        humana = RecommendationSnapshot(
            recommendation_id=rec.id, hierarchy=JERARQUIA[rec.nivel_control],
            description=f"{rec.texto} [{_describir_efecto(rec.efecto)}]",
            projected_reba=proyectado(rec.efecto), justification=motivo,
        )
        trail = self.mgr.load_audit_trail(caso.id_caso, verify=True)
        self.mgr.append_audit_event(
            case_id=caso.id_caso, event_id=f"EVT-{len(trail.events) + 1:04d}", specialist_id=usuario,
            action=accion, target_recommendation_id=rec.id,
            original_ai_recommendation=original, human_edited_recommendation=humana,
            initial_risk_score=reba_antes, residual_risk_score=residual_despues,
        )

    def _cerrar_mutacion(self, caso: CasoAlmacenado) -> CasoDetalle:
        """Persiste el caso y devuelve la evaluación recalculada."""
        self._guardar(caso)
        return self._evaluar(caso)

    # ================= Casos de uso públicos =================

    def listar(self) -> List[CasoResumen]:
        with self._lock:
            res = []
            for id_caso in self._ids():
                d = self._evaluar(self._cargar(id_caso))
                res.append(CasoResumen(
                    id_caso=d.id_caso, estacion=d.estacion, tipo_tarea=d.tipo_tarea, fecha=d.fecha,
                    reba_final=d.reba.final if d.reba else None, nivel=d.reba.nivel if d.reba else None,
                    decisiones_pendientes=d.validacion.pendientes, por_autorizar=d.validacion.por_autorizar,
                ))
            return res

    def obtener(self, id_caso: str) -> CasoDetalle:
        with self._lock:
            return self._evaluar(self._cargar(id_caso))

    def corregir_puntos(self, id_caso: str, vista: Vista, puntos: List[Punto], actor: Actor) -> CasoDetalle:
        _exigir_rol(actor, "ergonomia", "corregir el esqueleto")
        with self._lock:
            caso = self._cargar(id_caso)
            img = next((i for i in caso.imagenes if i.vista == vista), None)
            if img is None:
                raise NoEncontrado(f"El caso {id_caso} no tiene imagen {vista}")
            nuevos = {p.id: p for p in puntos}
            if len(nuevos) != len(puntos) or set(nuevos) != {p.id for p in img.puntos}:
                raise DatosInvalidos("Los puntos deben ser exactamente los del esqueleto, sin repetir")
            for p in puntos:
                if not (0 <= p.x <= img.ancho and 0 <= p.y <= img.alto):
                    raise DatosInvalidos(f"Punto {p.id} fuera de la imagen ({img.ancho}×{img.alto})")

            antes = self._evaluar(caso)
            movidos = 0
            for p in img.puntos:
                n = nuevos[p.id]
                if (n.x, n.y) != (p.x, p.y):
                    p.x, p.y, p.corregido = n.x, n.y, True  # la confianza del detector se conserva
                    movidos += 1
            if movidos == 0:
                return antes

            despues = self._cerrar_mutacion(caso)
            cambio = f"; REBA {antes.reba.final} → {despues.reba.final}" if antes.reba and despues.reba else ""
            self.ledger.registrar(actor.usuario, "puntos_corregidos", f"{id_caso} / {vista}", id_caso,
                                  despues=f"{movidos} punto(s) movido(s){cambio}")
            self._sincronizar(caso, despues, actor.usuario)
            log.info("Puntos corregidos caso=%s vista=%s movidos=%d", id_caso, vista, movidos)
            return despues

    def corregir_contexto(self, id_caso: str, c: CorreccionContexto) -> CasoDetalle:
        """El especialista corrige los datos de la tarea (carga, agarre, modificadores…)."""
        _exigir_rol(c, "ergonomia", "corregir los datos de la tarea")
        with self._lock:
            caso = self._cargar(id_caso)
            antes_txt, despues_txt = describir_contexto(caso.contexto), describir_contexto(c.contexto)
            cambios = [k for k in antes_txt if antes_txt[k] != despues_txt[k]]
            if not cambios:
                return self._evaluar(caso)
            antes = self._evaluar(caso)
            caso.contexto = c.contexto
            despues = self._cerrar_mutacion(caso)
            reba = f" (REBA {antes.reba.final} → {despues.reba.final})" if antes.reba and despues.reba else ""
            self.ledger.registrar(
                c.usuario, "contexto_corregido", f"{id_caso} / datos de la tarea", id_caso,
                antes="; ".join(f"{k}: {antes_txt[k]}" for k in cambios),
                despues="; ".join(f"{k}: {despues_txt[k]}" for k in cambios) + reba,
                motivo=c.motivo.strip(),
            )
            self._sincronizar(caso, despues, c.usuario)
            return despues

    def revisar_hallazgo(self, id_caso: str, id_hallazgo: str, r: RevisionHallazgo) -> CasoDetalle:
        _exigir_rol(r, "ergonomia", "descartar o restaurar hallazgos")
        with self._lock:
            caso = self._cargar(id_caso)
            actual = self._evaluar(caso)
            hallazgo = next((h for h in actual.hallazgos if h.id == id_hallazgo), None)
            if hallazgo is None:
                raise NoEncontrado(f"Hallazgo {id_hallazgo} no encontrado en {id_caso}")
            if r.accion == "descartar":
                if hallazgo.descartado:
                    raise Conflicto("El hallazgo ya está descartado")
                caso.hallazgos_descartados[id_hallazgo] = Descarte(
                    motivo=r.motivo.strip(), usuario=r.usuario, timestamp=_ahora())
            else:
                if not hallazgo.descartado:
                    raise Conflicto("El hallazgo no está descartado")
                del caso.hallazgos_descartados[id_hallazgo]
            despues = self._cerrar_mutacion(caso)
            self.ledger.registrar(r.usuario, f"hallazgo_{'descartado' if r.accion == 'descartar' else 'restaurado'}",
                                  f"{id_caso} / {id_hallazgo}", id_caso, antes=hallazgo.mensaje, motivo=r.motivo.strip())
            self._sincronizar(caso, despues, r.usuario)
            return despues

    def decidir(self, id_caso: str, id_recomendacion: str, d: Decision) -> None:
        if d.id_caso != id_caso or d.id_recomendacion != id_recomendacion:
            raise DatosInvalidos("El cuerpo de la decisión no coincide con la ruta")
        _exigir_rol(d, "ergonomia", "aprobar, editar o rechazar recomendaciones")
        with self._lock:
            caso = self._cargar(id_caso)
            rec = self._buscar_rec(caso, id_recomendacion)
            if rec.estado != "propuesta":
                raise Conflicto(f"La recomendación {rec.id} ya fue decidida ({rec.estado})")
            self._verificar_cadenas(id_caso)

            antes = self._evaluar(caso)
            texto_antes, efecto_antes = rec.texto, rec.efecto
            if d.accion == "editar" and d.cambios:
                actuales = efecto_a_dict(rec.efecto)
                desconocidos = set(d.cambios) - set(actuales)
                if desconocidos:
                    raise DatosInvalidos(f"La recomendación no propone esos parámetros: {', '.join(sorted(desconocidos))}")
                try:
                    rec.efecto = dict_a_efecto({**actuales, **d.cambios})
                except ValueError as e:
                    raise DatosInvalidos(str(e)) from e
                rec.efecto_ia = rec.efecto_ia or efecto_antes

            if d.accion == "rechazar":
                rec.estado, rec.implementacion = "rechazada", None
            else:
                if d.accion == "editar" and d.texto_editado is not None:
                    rec.texto = d.texto_editado.strip()
                rec.estado = "editada_aprobada" if d.accion == "editar" else "aprobada"
                rec.implementacion = "pendiente_autorizacion" if rec.tipo_cambio == "planta" else "por_implementar"
                rec.aprobado_por = d.usuario
                rec.responsable = (d.responsable or "").strip() or None
                rec.fecha_compromiso = d.fecha_compromiso
            motivo = (d.motivo or "").strip() or None

            despues = self._cerrar_mutacion(caso)
            self._registrar_auditoria(
                caso, rec, ACCION_AUDITORIA[d.accion], d.usuario, motivo,
                antes.reba.final if antes.reba else None,
                despues.residual.despues_final if despues.residual else None, efecto_original=efecto_antes)
            cambio_valores = ""
            if rec.efecto != efecto_antes:
                cambio_valores = f" | valores: {_describir_efecto(efecto_antes)} → {_describir_efecto(rec.efecto)}"
            self.ledger.registrar(
                d.usuario, f"recomendacion_{d.accion}", f"{id_caso} / {rec.id}", id_caso,
                antes=f"propuesta: {texto_antes}",
                despues=f"{rec.estado}: {rec.texto}{cambio_valores}", motivo=motivo,
            )
            self._sincronizar(caso, despues, d.usuario)
            log.info("Decisión caso=%s rec=%s accion=%s usuario=%s", id_caso, rec.id, d.accion, d.usuario)

    def autorizar(self, id_caso: str, id_recomendacion: str, a: Autorizacion) -> None:
        """Ingeniería autoriza o deniega un cambio en planta ya aprobado por ergonomía."""
        _exigir_rol(a, "ingenieria", "autorizar cambios en planta")
        with self._lock:
            caso = self._cargar(id_caso)
            rec = self._buscar_rec(caso, id_recomendacion)
            if rec.implementacion != "pendiente_autorizacion":
                raise Conflicto(f"La recomendación {rec.id} no está esperando autorización de ingeniería")
            if rec.aprobado_por and rec.aprobado_por.strip().lower() == a.usuario.strip().lower():
                raise Conflicto("Quien aprobó la recomendación no puede autorizarla (segregación de funciones)")
            self._verificar_cadenas(id_caso)

            antes = self._evaluar(caso)
            motivo = (a.motivo or "").strip() or None
            if a.accion == "autorizar":
                rec.implementacion, accion = "por_implementar", AuditActionEnum.AUTHORIZED
            else:
                rec.implementacion, accion = "denegada", AuditActionEnum.DENIED
            rec.autorizado_por, rec.nota_autorizacion = a.usuario, motivo

            despues = self._cerrar_mutacion(caso)
            self._registrar_auditoria(caso, rec, accion, a.usuario, motivo,
                                      antes.reba.final if antes.reba else None,
                                      despues.residual.despues_final if despues.residual else None)
            self.ledger.registrar(
                a.usuario, f"cambio_planta_{'autorizado' if a.accion == 'autorizar' else 'denegado'}",
                f"{id_caso} / {rec.id}", id_caso, antes="pendiente de autorización",
                despues=f"{rec.implementacion}: {rec.titulo}", motivo=motivo,
            )
            self._sincronizar(caso, despues)

    def implementar(self, id_caso: str, id_recomendacion: str, i: Implementacion) -> None:
        _exigir_rol(i, "ergonomia", "confirmar la implementación")
        with self._lock:
            caso = self._cargar(id_caso)
            rec = self._buscar_rec(caso, id_recomendacion)
            if rec.implementacion != "por_implementar":
                detalle = ("requiere autorización de ingeniería" if rec.implementacion == "pendiente_autorizacion"
                           else f"estado actual: {rec.implementacion or rec.estado}")
                raise Conflicto(f"La recomendación {rec.id} no se puede marcar como implementada ({detalle})")
            self._verificar_cadenas(id_caso)
            antes = self._evaluar(caso)
            nota = (i.nota or "").strip() or None
            rec.implementacion, rec.implementado_por, rec.nota_implementacion = "implementada", i.usuario, nota
            despues = self._cerrar_mutacion(caso)
            self._registrar_auditoria(caso, rec, AuditActionEnum.IMPLEMENTED, i.usuario, nota,
                                      antes.reba.final if antes.reba else None,
                                      despues.residual.despues_final if despues.residual else None)
            self.ledger.registrar(i.usuario, "recomendacion_implementada", f"{id_caso} / {rec.id}", id_caso,
                                  despues=f"implementada: {rec.titulo}", motivo=nota)
            self._sincronizar(caso, despues, i.usuario)

    def crear_recomendacion(self, id_caso: str, n: NuevaRecomendacion) -> str:
        """Recomendación redactada por el especialista; queda aprobada por él mismo."""
        _exigir_rol(n, "ergonomia", "crear recomendaciones")
        with self._lock:
            caso = self._cargar(id_caso)
            try:
                efecto = dict_a_efecto(n.cambios)
            except ValueError as e:
                raise DatosInvalidos(str(e)) from e
            usados = {r.id for r in caso.recomendaciones}
            num = 1
            while f"E{num}" in usados:
                num += 1
            self._verificar_cadenas(id_caso)
            antes = self._evaluar(caso)
            rec = RecomendacionAlmacenada(
                id=f"E{num}", nivel_control=n.nivel_control, tipo_cambio=n.tipo_cambio, titulo=n.titulo.strip(),
                texto=n.texto.strip(), texto_ia=n.texto.strip(), referencia=n.referencia.strip(), origen="especialista",
                estado="aprobada", aprobado_por=n.usuario,
                implementacion="pendiente_autorizacion" if n.tipo_cambio == "planta" else "por_implementar",
                responsable=(n.responsable or "").strip() or None, fecha_compromiso=n.fecha_compromiso, efecto=efecto,
            )
            caso.recomendaciones.append(rec)
            despues = self._cerrar_mutacion(caso)
            self._registrar_auditoria(caso, rec, AuditActionEnum.CREATED, n.usuario, n.motivo.strip(),
                                      antes.reba.final if antes.reba else None,
                                      despues.residual.despues_final if despues.residual else None)
            self.ledger.registrar(n.usuario, "recomendacion_creada", f"{id_caso} / {rec.id}", id_caso,
                                  despues=f"{rec.titulo}: {rec.texto} [{_describir_efecto(efecto)}]",
                                  motivo=n.motivo.strip())
            self._sincronizar(caso, despues, n.usuario)
            return rec.id

    def crear_caso(self, datos: NuevoCaso, fotos: Dict[str, bytes]) -> str:
        """
        Crea un caso a partir de fotos reales: visión (YOLOX + RTMPose) → puntos → REBA → hallazgos →
        recomendaciones propuestas. Las fotos se guardan con el rostro difuminado.
        """
        _exigir_rol(datos, "ergonomia", "crear casos")
        if "lateral" not in fotos:
            raise DatosInvalidos("La foto lateral es obligatoria: de ella se miden los ángulos REBA")
        desconocidas = set(fotos) - {"lateral", "frontal", "cenital"}
        if desconocidas:
            raise DatosInvalidos(f"Vistas no válidas: {', '.join(sorted(desconocidas))}")
        ok, detalle_vision = estimador.estado()
        if not ok:
            raise VisionNoDisponible(detalle_vision)

        import cv2  # dependencia opcional: solo se necesita con visión instalada
        import numpy as np

        t0 = time.perf_counter()

        # La inferencia (lenta) va fuera del candado del servicio.
        resultados = {}
        for vista, contenido in fotos.items():
            if len(contenido) > MAX_FOTO_MB * 1_000_000:
                raise DatosInvalidos(f"La foto {vista} supera {MAX_FOTO_MB:g} MB")
            img = cv2.imdecode(np.frombuffer(contenido, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise DatosInvalidos(f"La foto {vista} no es una imagen JPG o PNG válida")
            resultados[vista] = estimador.analizar(img)
        if resultados["lateral"].personas == 0:
            raise DatosInvalidos("No se detectó a ninguna persona en la foto lateral. Usa una toma donde el "
                                 "operador se vea de cuerpo completo y de costado.")

        with self._lock:
            usados = set(self._ids())
            num = 1
            while f"C-{num:03d}" in usados:
                num += 1
            id_caso = f"C-{num:03d}"
            case_dir = self.mgr.init_case_workspace(id_caso)

            imagenes, hallazgos = [], []
            for vista in ("lateral", "frontal", "cenital"):
                r = resultados.get(vista)
                if r is None:
                    continue
                archivo = f"{vista}.jpg"
                # Se re-codifica: elimina metadatos EXIF y conserva solo la versión anonimizada.
                if not cv2.imwrite(str(case_dir / "inputs" / archivo), r.imagen_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90]):
                    raise RuntimeError(f"No se pudo guardar la foto {vista}")
                h, w = r.imagen_bgr.shape[:2]
                imagenes.append(Imagen(vista=vista, url=archivo, ancho=w, alto=h, puntos=[
                    Punto(id=p.id, x=round(p.x, 1), y=round(p.y, 1), confianza=p.confianza) for p in r.puntos]))
                if r.personas > 1:
                    hallazgos.append(Hallazgo(
                        id=f"V-personas-{vista}", origen="vision", severidad="info", vista=vista,
                        mensaje=(f"Se detectaron {r.personas} personas en la vista {vista}; se evalúa la de mayor "
                                 f"tamaño. Si no es el operador auditado, corrige los puntos."),
                        caja=r.caja))
                if r.por_respaldo:
                    hallazgos.append(Hallazgo(
                        id=f"V-oclusion-{vista}", origen="vision", severidad="advertencia", vista=vista,
                        mensaje=(f"El operador está parcialmente oculto en la vista {vista}; los puntos se estimaron "
                                 f"sobre la imagen completa. Verifícalos antes de validar.")))
                if r.personas == 0:
                    hallazgos.append(Hallazgo(
                        id=f"V-sin-persona-{vista}", origen="vision", severidad="info", vista=vista,
                        mensaje=f"No se detectó a ninguna persona en la vista {vista}."))

            caso = CasoAlmacenado(
                id_caso=id_caso, estacion=datos.estacion.strip(), tipo_tarea=datos.tipo_tarea,
                fecha=datetime.now().astimezone().isoformat(timespec="seconds"), imagenes=imagenes,
                contexto=datos.contexto, evaluacion_previa=datos.evaluacion_previa, hallazgos_vision=hallazgos,
            )
            medidos = self._medir(caso)
            self._aplicar_vista_frontal(caso, medidos["brazo"].lado or "izq")
            medidos, res = self._calcular_reba(caso)  # type: ignore[misc]  (hay foto lateral)
            propuestas = generar(
                {s: m.grados for s, m in medidos.items()}, caso.contexto, caso.tipo_tarea, res.final,
                self.config.get_reba_tables(), self.config.get_jabil_standards())
            caso.recomendaciones = [RecomendacionAlmacenada.model_validate({**r, "texto_ia": r["texto"]})
                                    for r in propuestas]
            caso.metricas.creado_en = _ahora()
            caso.metricas.analisis_ms = round((time.perf_counter() - t0) * 1000, 1)

            self._guardar(caso)
            detalle = self._evaluar(caso)
            self.ledger.registrar(datos.usuario, "caso_creado", id_caso, id_caso,
                                  despues=f"{caso.estacion} · {len(fotos)} foto(s)")
            self.ledger.registrar(
                USUARIO_SISTEMA, "analisis_ejecutado", id_caso, id_caso,
                despues=f"REBA {res.final} · {len(propuestas)} recomendación(es) · {detalle_vision}")
            self._sincronizar(caso, detalle, datos.usuario)
            log.info("Caso creado desde fotos: %s REBA=%s", id_caso, res.final)
            return id_caso

    def _aplicar_vista_frontal(self, caso: CasoAlmacenado, lado: str) -> None:
        """Marca los modificadores que se ven en la foto frontal; el especialista puede desmarcarlos."""
        frontal = next((i for i in caso.imagenes if i.vista == "frontal" and i.puntos), None)
        if frontal is None:
            return
        umbrales = self.config.get_reba_tables()["frontal_view_thresholds_deg"]
        m = medir_vista_frontal(frontal.puntos, lado, CONFIANZA_MINIMA)
        mods = caso.contexto.modificadores
        if m["inclinacion_tronco"] is not None and m["inclinacion_tronco"] > umbrales["trunk_side_bending"]:
            mods.tronco_torsion_o_inclinacion = True
            caso.hallazgos_vision.append(Hallazgo(
                id="V-frontal-tronco", origen="vision", severidad="info", vista="frontal",
                mensaje=(f"Vista frontal: inclinación lateral de tronco de {m['inclinacion_tronco']:g}° "
                         f"(> {umbrales['trunk_side_bending']:g}°); se marcó el modificador REBA de tronco.")))
        if m["abduccion_brazo"] is not None and m["abduccion_brazo"] > umbrales["upper_arm_abduction"]:
            mods.brazo_abducido_o_rotado = True
            caso.hallazgos_vision.append(Hallazgo(
                id="V-frontal-brazo", origen="vision", severidad="info", vista="frontal",
                mensaje=(f"Vista frontal: abducción del brazo de {m['abduccion_brazo']:g}° "
                         f"(> {umbrales['upper_arm_abduction']:g}°); se marcó el modificador REBA de brazo.")))

    def corregir_referencia(self, id_caso: str, c: CorreccionReferencia) -> CasoDetalle:
        """Carga o corrige el estudio de referencia de Jabil contra el que se audita el análisis."""
        _exigir_rol(c, "ergonomia", "capturar la evaluación de referencia")
        with self._lock:
            caso = self._cargar(id_caso)
            if caso.evaluacion_previa == c.evaluacion_previa:
                return self._evaluar(caso)

            def txt(e) -> str:
                partes = [f"{s}: {v}" for s, v in e.segmentos.items()]
                return "; ".join(partes + [f"REBA {e.reba_final}"] if e.reba_final else partes) or "sin captura"

            antes = txt(caso.evaluacion_previa)
            caso.evaluacion_previa = c.evaluacion_previa
            despues = self._cerrar_mutacion(caso)
            self.ledger.registrar(c.usuario, "referencia_corregida", f"{id_caso} / evaluación de referencia", id_caso,
                                  antes=antes, despues=txt(c.evaluacion_previa), motivo=c.motivo.strip())
            self._sincronizar(caso, despues, c.usuario)
            return despues

    def corregir_nom036(self, id_caso: str, c: CorreccionNom036) -> CasoDetalle:
        """Captura o corrige la evaluación NOM-036 (factores de la hoja 16-PE80-6500-00014-H)."""
        _exigir_rol(c, "ergonomia", "capturar la evaluación NOM-036")
        tablas = self.config.get_nom036_tables()
        if c.nom036 is not None:
            try:
                validar_captura(c.nom036.metodo, c.nom036.factores, tablas)
            except ValueError as e:
                raise DatosInvalidos(str(e)) from e
        with self._lock:
            caso = self._cargar(id_caso)
            if caso.nom036 == c.nom036:
                return self._evaluar(caso)

            def txt(n: Optional[Nom036Captura]) -> str:
                if n is None:
                    return "sin evaluación"
                total = total_factores(f.valor for f in n.factores)
                return f"{n.metodo}: total {total} ({color_total(total, tablas)})"

            antes = txt(caso.nom036)
            caso.nom036 = c.nom036
            despues = self._cerrar_mutacion(caso)
            self.ledger.registrar(c.usuario, "nom036_capturada", f"{id_caso} / NOM-036", id_caso,
                                  antes=antes, despues=txt(c.nom036), motivo=c.motivo.strip())
            self._sincronizar(caso, despues, c.usuario)
            return despues

    def impacto(self) -> Impacto:
        """Tiempos medidos en los casos analizados desde fotos frente a la evaluación manual."""
        with self._lock:
            casos = []
            for id_caso in self._ids():
                c = self._cargar(id_caso)
                m = c.metricas
                if m.analisis_ms is None:
                    continue  # casos de ejemplo: no tienen tiempo real medido
                validacion = None
                if m.creado_en and m.validado_en:
                    validacion = round((datetime.fromisoformat(m.validado_en)
                                        - datetime.fromisoformat(m.creado_en)).total_seconds() / 60, 1)
                casos.append(CasoImpacto(id_caso=id_caso, estacion=c.estacion,
                                         analisis_s=round(m.analisis_ms / 1000, 1), validacion_min=validacion))
            analisis = [c.analisis_s for c in casos if c.analisis_s is not None]
            validados = [c.validacion_min for c in casos if c.validacion_min is not None]
            prom_val = round(sum(validados) / len(validados), 1) if validados else None
            ahorro = round(MINUTOS_EVALUACION_MANUAL - prom_val, 1) if prom_val is not None else None
            return Impacto(
                minutos_evaluacion_manual=MINUTOS_EVALUACION_MANUAL, fuente_referencia_manual=FUENTE_EVALUACION_MANUAL,
                casos=casos, analisis_promedio_s=round(sum(analisis) / len(analisis), 1) if analisis else None,
                validacion_promedio_min=prom_val, ahorro_promedio_min=ahorro,
                ahorro_porcentaje=round(ahorro / MINUTOS_EVALUACION_MANUAL * 100, 1) if ahorro is not None else None,
            )

    def listar_alertas(self) -> List[Alerta]:
        with self._lock:
            return self._cargar_alertas()

    def atender_alerta(self, id_alerta: str, usuario: str) -> None:
        with self._lock:
            alertas = self._cargar_alertas()
            alerta = next((a for a in alertas if a.id_alerta == id_alerta), None)
            if alerta is None:
                raise NoEncontrado(f"Alerta {id_alerta} no encontrada")
            if alerta.estado == "atendida":
                return
            alerta.estado = "atendida"
            self._guardar_alertas(alertas)
            self.ledger.registrar(usuario, "alerta_atendida", id_alerta, alerta.id_caso)

    def bitacora(self, id_caso: Optional[str] = None) -> List[EntradaBitacora]:
        with self._lock:
            return self.ledger.listar(id_caso)

    def verificar_integridad(self) -> ResultadoIntegridad:
        with self._lock:
            v = self.ledger.verificar()
            if not v.ok:
                return ResultadoIntegridad(ok=False, total=v.total, primera_falla=v.primera_falla, detalle=v.detalle)
            for id_caso in self._ids():
                ok, err = self.mgr.verify_case_audit_integrity(id_caso)
                if not ok:
                    return ResultadoIntegridad(ok=False, total=v.total, primera_falla=None,
                                               detalle=f"audit_trail de {id_caso}: {err}")
            return ResultadoIntegridad(ok=True, total=v.total, primera_falla=None)

    def ruta_media(self, id_caso: str, archivo: str) -> Path:
        try:
            base = (self.mgr.get_case_dir(id_caso) / "inputs").resolve()
        except ValueError as e:
            raise NoEncontrado("Imagen no encontrada") from e
        ruta = (base / archivo).resolve()
        if ruta.parent != base or not ruta.is_file():
            raise NoEncontrado("Imagen no encontrada")
        return ruta
