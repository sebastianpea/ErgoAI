"""Casos de prueba oficiales del Track 4 (Jabil / X-RAIC 2026).

Define los 6 casos de evaluación requeridos por la rúbrica oficial:
  - Levantamiento (Casos 1 y 2)
  - Transporte con auxiliar (Casos 3 y 4)
  - Transporte sin auxiliar (Casos 5 y 6)
conforme a los Criterios 1, 2, 3 y Entregable 2.
"""

from __future__ import annotations

from typing import Any, Dict, List
from pathlib import Path
from pydantic import BaseModel, Field

from ergoai.config import SETTINGS


class JabilBenchmarkCase(BaseModel):
    """Especificación completa de un caso de evaluación ergonómica oficial de Jabil."""
    case_id: str
    case_number: int
    task_type: str = Field(..., description="Levantamiento, Transporte con auxiliar, o Transporte sin auxiliar")
    title: str
    description: str
    lateral_file: str
    frontal_file: str
    aerea_file: str
    recommended_load_kg: float
    coupling_score: int = 0
    is_static: bool = False
    is_repetitive: bool = False
    is_shock_load: bool = False
    reach_frequency: float = 1.0
    reference_reba_range: tuple[int, int] = (1, 15)
    reference_risk_level: str = "MEDIUM"
    key_biomechanical_issues: List[str] = Field(default_factory=list)
    nom036_focus: str = "Manejo manual de cargas"


def get_official_jabil_cases(include_compliant: bool = False) -> List[JabilBenchmarkCase]:
    """Retorna los 6 casos de prueba del benchmark de Jabil descubiertos dinámicamente (y opcional caso conforme)."""
    ds = SETTINGS.dataset_dir

    cases = [
        # =========================================================================
        # BLOQUE A: LEVANTAMIENTO (Casos 1 y 2)
        # =========================================================================
        JabilBenchmarkCase(
            case_id="caso_1_levantamiento_caja_pesada",
            case_number=1,
            task_type="Levantamiento",
            title="Caso 1: Levantamiento Manual de Caja Pesada con Oclusión de Muñecas",
            description="Levantamiento de contenedor al pecho con oclusión frontal de muñecas y flexión lumbar forzada. "
                        "Evalúa precisión anatómica bajo oclusión, superación del límite normativo B1 (16.5 kg > 14 kg) "
                        "y prioridad de asistencia mecánica (lifter) según NOM-036-1 Numeral 7.1.",
            lateral_file=str(ds / "02_oclusion_levantamiento" / "lev_03_caja_lateral_perfil_C.jpg"),
            frontal_file=str(ds / "02_oclusion_levantamiento" / "lev_01_caja_pecho_munecas_A.jpg"),
            aerea_file=str(ds / "04_perspectiva_cenital" / "cen_02_vista_cenital_oblicua_25deg.jpg"),
            recommended_load_kg=16.5,
            coupling_score=1,
            is_static=False,
            is_repetitive=False,
            is_shock_load=False,
            reference_reba_range=(8, 11),
            reference_risk_level="HIGH",
            key_biomechanical_issues=[
                "Carga manual de 16.5 kg que excede el límite seguro Jabil B1 (14.0 kg)",
                "Flexión de tronco > 20° al iniciar el levantamiento",
                "Oclusión de muñecas resuelta por RTMPose WholeBody-133",
            ],
            nom036_focus="Numeral 7.1: Manejo manual de cargas > 14 kg requiere asistencia mecánica obligatoria",
        ),
        JabilBenchmarkCase(
            case_id="caso_2_levantamiento_estacion_cenital",
            case_number=2,
            task_type="Levantamiento",
            title="Caso 2: Levantamiento en Estación de Ensamble y Alcance Cenital Crítico",
            description="Operación repetitiva de pick-and-place desde estante superior hacia estación. "
                        "Evalúa alcance en Zona 4/5 (> 500 mm), flexión cervical por altura inadecuada "
                        "y propuesta de reubicación a Zonas 1 y 2 según estándar Jabil 7.2.2.2.",
            lateral_file=str(ds / "02_oclusion_levantamiento" / "lev_02_caja_pecho_munecas_B.jpg"),
            frontal_file=str(ds / "01_sin_rostro" / "sr_03_recorte_hombros_operarioC.jpg"),
            aerea_file=str(ds / "04_perspectiva_cenital" / "cen_01_vista_picado_frontal.jpg"),
            recommended_load_kg=12.0,
            coupling_score=0,
            is_static=False,
            is_repetitive=True,
            is_shock_load=False,
            reference_reba_range=(6, 8),
            reference_risk_level="MEDIUM",
            key_biomechanical_issues=[
                "Alcance manual en Zona 4 (> 500 mm) que provoca torsión axial",
                "Ciclo repetitivo (> 4 veces/min) que eleva puntuación de actividad REBA (+1)",
                "Flexión de hombro > 45° al tomar pieza en rack alto",
            ],
            nom036_focus="Numeral 7.2.2: Reubicación de materiales a Zonas 1 y 2 para eliminar abducción",
        ),

        # =========================================================================
        # BLOQUE B: TRANSPORTE CON AUXILIAR (Casos 3 y 4)
        # =========================================================================
        JabilBenchmarkCase(
            case_id="caso_3_transporte_auxiliar_carrito",
            case_number=3,
            task_type="Transporte con auxiliar",
            title="Caso 3: Transporte con Auxiliar — Carrito de Charolas con Oclusión Inferior",
            description="Empuje de carrito de transporte de charolas SMT con oclusión severa de rodillas y pies. "
                        "Evalúa reconstrucción biomecánica de miembros inferiores según proporción antropométrica "
                        "y validación de altura de agarre en carro auxiliar (Jabil B4).",
            lateral_file=str(ds / "03_oclusion_auxiliar" / "aux_01_carrito_tapa_rodillas_A.jpg"),
            frontal_file=str(ds / "03_oclusion_auxiliar" / "aux_02_carrito_tapa_rodillas_B.jpg"),
            aerea_file=str(ds / "04_perspectiva_cenital" / "cen_03_vista_cenital_rotada_neg30deg.jpg"),
            recommended_load_kg=8.0,
            coupling_score=0,
            is_static=True,
            is_repetitive=False,
            is_shock_load=False,
            reference_reba_range=(4, 6),
            reference_risk_level="MEDIUM",
            key_biomechanical_issues=[
                "Oclusión completa de rodillas y pies por panel frontal del carro",
                "Ángulo de flexión de antebrazo fuera del rango óptimo (60°-100°)",
                "Postura estática sostenida durante el posicionamiento",
            ],
            nom036_focus="Numeral 7.2: Altura de agarre del carro auxiliar ajustada entre 0.9 y 1.1 m",
        ),
        JabilBenchmarkCase(
            case_id="caso_4_transporte_auxiliar_mesa_cadera",
            case_number=4,
            task_type="Transporte con auxiliar",
            title="Caso 4: Transporte con Auxiliar — Mesa Rodante con Tracción a Nivel de Cadera",
            description="Tracción de mesa móvil a baja altura provocando inclinación lateral de tronco "
                        "y postura asimétrica de hombros. Evalúa abducción coronal y propuesta de rediseño "
                        "de maneral a altura estándar (Jabil F1 / NOM-036).",
            lateral_file=str(ds / "03_oclusion_auxiliar" / "aux_03_mesa_transporte_cadera_C.jpg"),
            frontal_file=str(ds / "03_oclusion_auxiliar" / "aux_02_carrito_tapa_rodillas_B.jpg"),
            aerea_file=str(ds / "04_perspectiva_cenital" / "cen_02_vista_cenital_oblicua_25deg.jpg"),
            recommended_load_kg=10.5,
            coupling_score=1,
            is_static=False,
            is_repetitive=False,
            is_shock_load=False,
            reference_reba_range=(5, 7),
            reference_risk_level="MEDIUM",
            key_biomechanical_issues=[
                "Tracción baja que induce flexión de tronco lateral y torsión",
                "Punto de empuje inferior a 95 cm que obliga a flexión forzada",
            ],
            nom036_focus="Numeral 7.3: Rediseño de manerales de transporte a cota ergonómica de 95 a 110 cm",
        ),

        # =========================================================================
        # BLOQUE C: TRANSPORTE SIN AUXILIAR (Casos 5 y 6)
        # =========================================================================
        JabilBenchmarkCase(
            case_id="caso_5_transporte_sin_auxiliar_acarreo",
            case_number=5,
            task_type="Transporte sin auxiliar",
            title="Caso 5: Transporte sin Auxiliar — Acarreo Manual Individual Forzado",
            description="Transporte manual prolongado sin equipo auxiliar con carga de 15 kg superando el umbral "
                        "unipersonal. Demuestra la necesidad de dotar carrito auxiliar o lifter (NOM-036 / Jabil B1) "
                        "y alternancia postural entre sentado y de pie.",
            lateral_file=str(ds / "02_oclusion_levantamiento" / "lev_03_caja_lateral_perfil_C.jpg"),
            frontal_file=str(ds / "01_sin_rostro" / "sr_02_recuadro_negro_operarioB.jpg"),
            aerea_file=str(ds / "04_perspectiva_cenital" / "cen_01_vista_picado_frontal.jpg"),
            recommended_load_kg=15.0,
            coupling_score=1,
            is_static=False,
            is_repetitive=False,
            is_shock_load=False,
            reference_reba_range=(7, 9),
            reference_risk_level="HIGH",
            key_biomechanical_issues=[
                "Acarreo manual > 14 kg sin carro auxiliar, no conforme con Jabil B1",
                "Esfuerzo muscular continuo de antebrazos y bíceps",
                "Falta de soporte lumbar en marcha con carga",
            ],
            nom036_focus="Numeral 7.1 y 7.2: Transición obligatoria a transporte con auxiliar mecánico",
        ),
        JabilBenchmarkCase(
            case_id="caso_6_celda_multipersona_sin_rostro",
            case_number=6,
            task_type="Transporte sin auxiliar",
            title="Caso 6: Celda Multi-Persona sin Rostro — Análisis de Separación y Distancia F2",
            description="Estación con 2 operarios concurrentes con rostro cubierto por recuadro negro. "
                        "Evalúa tolerancia sin rostro (privacidad NOM-036), seguimiento individual ByteTrack "
                        "y verificación de la Regla F2 de distancia inter-operador (>= 80 cm).",
            lateral_file=str(ds / "01_sin_rostro" / "sr_01_recuadro_negro_operarioA.jpg"),
            frontal_file=str(ds / "01_sin_rostro" / "sr_01_recuadro_negro_operarioA.jpg"),
            aerea_file=str(ds / "04_perspectiva_cenital" / "cen_01_vista_picado_frontal.jpg"),
            recommended_load_kg=6.0,
            coupling_score=0,
            is_static=True,
            is_repetitive=False,
            is_shock_load=False,
            reference_reba_range=(4, 6),
            reference_risk_level="LOW",
            key_biomechanical_issues=[
                "2 operarios en estación adyacente: medición euclidiana métrica de separación F2",
                "Tolerancia total ante rostros cubiertos con recuadros negros (sin pérdida de tracking)",
                "Validación de postura estática y ángulo de visión de ensamble",
            ],
            nom036_focus="Jabil F2: Separación inter-operador >= 80 cm para evitar colisiones e interferencia",
        ),
    ]

    if include_compliant:
        cases.append(get_compliant_posture_case())

    return cases


def get_compliant_posture_case() -> JabilBenchmarkCase:
    """Retorna un caso de referencia de postura ergonómicamente correcta y conforme a NOM-036."""
    ds = SETTINGS.dataset_dir
    return JabilBenchmarkCase(
        case_id="caso_postura_correcta_conforme",
        case_number=7,
        task_type="Postura Ergonómica Correcta",
        title="Caso de Referencia: Postura Ergonómica Correcta y Conforme (NOM-036)",
        description="Operario en celda de ensamble en postura ergonómicamente óptima y conforme a la NOM-036-1-STPS-2018. "
                    "Columna vertebral en ángulo neutro (< 20°), cuello relajado, brazos en zona de confort (< 20°), "
                    "antebrazos en rango óptimo (60°-100°) y muñecas sin desviación. Demuestra la capacidad del sistema "
                    "para reconocer y certificar condiciones de bajo riesgo ergonómico.",
        lateral_file=str(ds / "01_sin_rostro" / "sr_03_recorte_hombros_operarioC.jpg"),
        frontal_file=str(ds / "01_sin_rostro" / "sr_03_recorte_hombros_operarioC.jpg"),
        aerea_file=str(ds / "04_perspectiva_cenital" / "cen_01_vista_picado_frontal.jpg"),
        recommended_load_kg=1.5,
        coupling_score=0,
        is_static=False,
        is_repetitive=False,
        is_shock_load=False,
        reference_reba_range=(1, 3),
        reference_risk_level="NEGLIGIBLE",
        key_biomechanical_issues=[
            "Postura Óptima y Conforme con la NOM-036-1-STPS-2018",
            "Columna y cuello en rango neutro (< 20°)",
            "Brazos relajados junto al cuerpo en plano de confort",
        ],
        nom036_focus="Conformidad ergonómica: Postura óptima sin requerimiento de intervención",
    )

