"""Modelos tipados para los datos de entrada de una estación de trabajo y especificaciones Jabil."""

from enum import Enum
try:
    from enum import StrEnum
except ImportError:
    class StrEnum(str, Enum):
        pass
from typing import Optional
from pydantic import BaseModel, Field


class WorkstationType(StrEnum):
    """Tipo de estación o área funcional."""
    BE = "BE"
    SMT = "SMT"
    TEST = "pruebas"
    MRB = "MRB"
    WAREHOUSE = "almacen"
    PACKAGING = "empaque"
    OTHER_PRODUCTIVE = "productiva_otra"
    NON_PRODUCTIVE = "no_productiva"


class RuleStatus(StrEnum):
    """Estados posibles para la evaluación de una regla ergonómica o de layout."""
    CONFORME = "CONFORME"
    ADVERTENCIA = "ADVERTENCIA"
    NO_CONFORME = "NO CONFORME"
    CRITICO = "CRITICO"
    REVISION_HUMANA = "REVISION HUMANA"
    NO_APLICA = "NO APLICA"
    DATO_FALTANTE = "DATO FALTANTE"


class RuleOrigin(StrEnum):
    """Origen y respaldo normativo de la regla."""
    DOC = "DOC"          # Directamente estipulada en la instrucción de trabajo oficial
    SUPUESTO = "SUPUESTO"  # Criterio propuesto para completar lagunas normativas, sujeto a validación EHS


class ChairLawAnswers(BaseModel):
    """Respuestas a las 7 preguntas normativas de la Ley Silla (bipedestación prolongada)."""
    p1_standing_time: int = Field(..., ge=1, le=3, description="Tiempo de pie diario continuo: <=30m=1, 30-60m=2, >60m=3")
    p2_posture_change: int = Field(..., ge=1, le=3, description="Posibilidad de cambiar de postura: Si=1, Algunas=2, No=3")
    p3_surface_type: int = Field(..., ge=1, le=3, description="Superficie: Blando/antifatiga=1, Firme=2, Duro=3")
    p4_footwear: int = Field(..., ge=1, le=3, description="Calzado: Ergonómico=1, Aceptable=2, Inadecuado=3")
    p5_space: int = Field(..., ge=1, le=3, description="Espacio: Amplio=1, Limitado=2, Muy reducido=3")
    p6_discomfort: int = Field(..., ge=1, le=3, description="Malestares: Ninguno=1, Fatiga eventual=2, Dolor lumbar/hinchazón=3")
    p7_breaks: int = Field(..., ge=1, le=3, description="Pausas: Planeadas=1, Informales=2, Sin pausas=3")

    @property
    def total_score(self) -> int:
        """Suma de puntos de las 7 preguntas (7 a 21)."""
        return (
            self.p1_standing_time
            + self.p2_posture_change
            + self.p3_surface_type
            + self.p4_footwear
            + self.p5_space
            + self.p6_discomfort
            + self.p7_breaks
        )


class WorkstationDimensions(BaseModel):
    """Dimensiones físicas y holguras antropométricas de la estación."""
    surface_height_cm: Optional[float] = Field(default=None, description="Altura de la superficie de trabajo (CUU: 95-125 cm)")
    table_thickness_cm: Optional[float] = Field(default=None, description="Espesor de la mesa (máx. 10 cm)")
    leg_room_depth_cm: Optional[float] = Field(default=None, description="Profundidad libre para piernas en sedestación (mín. 55 cm)")
    leg_room_width_cm: Optional[float] = Field(default=None, description="Ancho libre para piernas en sedestación (mín. 60 cm)")
    footrest_height_cm: Optional[float] = Field(default=None, description="Altura de reposapiés (21-37 cm)")
    footrest_recess_cm: Optional[float] = Field(default=None, description="Retroceso del reposapiés desde el borde de mesa (15 cm)")
    standing_foot_depth_cm: Optional[float] = Field(default=None, description="Espacio libre de pies para estación de pie (mín. 15 cm)")
    operator_distance_cm: Optional[float] = Field(default=None, description="Distancia entre operadores punto medio a punto medio (mín. 80 cm)")


class WorkstationLiftingData(BaseModel):
    """Parámetros de manejo manual de cargas."""
    weight_kg: Optional[float] = Field(default=None, description="Peso de la carga manipulada en kg")
    num_people: int = Field(default=1, ge=1, description="Número de personas levantando simultáneamente")
    has_mechanical_assist: bool = Field(default=False, description="True si cuenta con grúa, lifter o asistencia mecánica")
    is_containment: bool = Field(default=False, description="True si el levantamiento múltiple es una medida temporal de contención")
    medical_clearance: Optional[bool] = Field(default=None, description="True si cuenta con visto bueno del departamento médico")
    has_moc: Optional[bool] = Field(default=None, description="True si cuenta con trámite MOC aprobado")
    has_form_00014: Optional[bool] = Field(default=None, description="True si cuenta con formato de ergonomía 16-PE80-6500-00014")
    pickup_height_m: Optional[float] = Field(default=None, description="Altura física de toma en metros")
    pickup_origin: Optional[str] = Field(default=None, description="Origen de carga: piso, rack_estatico, tarima, carro, sobre_cabeza, mesa")
    free_space_around_cm: Optional[float] = Field(default=None, description="Espacio libre alrededor del operario (mín. 60 cm)")
    is_new_business: bool = Field(default=False, description="True si es proyecto o negocio nuevo")
    has_form_00091: Optional[bool] = Field(default=None, description="True si cuenta con formato de evaluación de cargas 16-PE80-6500-00091")


class WorkstationChairData(BaseModel):
    """Condiciones de sillas y requerimientos de descanso."""
    chair_has_5_legs: Optional[bool] = None
    chair_has_footrest: Optional[bool] = None
    chair_height_adjustable: Optional[bool] = None
    chair_non_rigid_backrest: Optional[bool] = None
    chair_polyurethane: Optional[bool] = None
    is_esd_chair: Optional[bool] = None
    marked_on_floor: Optional[bool] = None
    documented_in_layout: Optional[bool] = None
    visual_factory_signage: Optional[bool] = None
    secured_with_ehs_permission: Optional[bool] = None
    chair_strategy: Optional[str] = None  # "silla_descanso", "rotacion", "ninguna"
    has_chair_schedule: Optional[bool] = None
    rotation_approved_by_supervisor: Optional[bool] = None


class WorkstationConveyorData(BaseModel):
    """Condiciones de transportadores/conveyors en la estación."""
    has_conveyor: bool = False
    conveyor_type: Optional[str] = None  # "electrico", "gravedad"
    height_m: Optional[float] = None     # 0.5 a 1.4 m
    length_m: Optional[float] = None     # gravedad máx. 3 m
    moving_parts_guards: Optional[bool] = None  # guardas en engranes/motores/poleas
    work_area_access_cm: Optional[float] = None # mín. 80 cm
    has_ergonomic_analysis: Optional[bool] = None
    used_as_worktable: bool = False
    allows_chair_stations: Optional[bool] = None
    pallet_separation_cm: Optional[float] = None  # mín. 30 cm


class WorkstationAislesData(BaseModel):
    """Pasillos, flujo logístico, áreas AMR y MRB."""
    aisle_type: Optional[str] = None  # "peatonal_bajo_flujo", "peatonal_carros", "peatonal_tarimas", "be_material"
    aisle_width_m: Optional[float] = None
    has_amr: bool = False
    amr_is_bidirectional: bool = False
    amr_width_m: Optional[float] = None
    amr_load_width_m: Optional[float] = None
    electrical_panel_clearance_cm: Optional[float] = None  # mín. 90 cm
    emergency_exits_unblocked: Optional[bool] = None
    is_mrb_area: bool = False
    mrb_cage_height_m: Optional[float] = None  # mín. 1.60 m
    mrb_has_lock: Optional[bool] = None
    mrb_has_esd_magnifier: Optional[bool] = None


class WorkstationInputData(BaseModel):
    """Entrada completa para la auditoría de una estación de trabajo."""
    id_estacion: str = Field(..., description="Identificador único de la estación")
    area: str = Field(default="Producción", description="Área o edificio de la planta")
    tipo: WorkstationType = Field(default=WorkstationType.BE, description="Tipo de estación")
    is_epa_area: bool = Field(default=True, description="True si es área protegida contra descargas electrostáticas (EPA)")
    posture_proposed: str = Field(default="de_pie", description="'sentado' o 'de_pie'")
    standing_continuous_time_min: float = Field(default=0.0, description="Minutos continuos de bipedestación sin pausa sentado")
    seated_pause_min: float = Field(default=0.0, description="Minutos de descanso sentado otorgados")
    has_fine_assembly: bool = Field(default=False, description="True si realiza ensamble fino")
    requires_pedals: bool = Field(default=False, description="True si requiere accionar pedales")
    frequent_travel_required: bool = Field(default=False, description="True si requiere traslados frecuentes entre puntos distantes")
    last_ergonomic_evaluation_fiscal_year: Optional[int] = Field(default=None, description="Año fiscal de última evaluación (formato 00014)")
    current_fiscal_year: int = Field(default=2026, description="Año fiscal en curso")

    dimensions: WorkstationDimensions = Field(default_factory=WorkstationDimensions)
    lifting: WorkstationLiftingData = Field(default_factory=WorkstationLiftingData)
    chair_law: Optional[ChairLawAnswers] = None
    chair_spec: WorkstationChairData = Field(default_factory=WorkstationChairData)
    conveyor: WorkstationConveyorData = Field(default_factory=WorkstationConveyorData)
    aisles: WorkstationAislesData = Field(default_factory=WorkstationAislesData)

