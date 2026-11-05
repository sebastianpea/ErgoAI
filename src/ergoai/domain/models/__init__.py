"""Exportación centralizada de modelos del Dominio ErgoAI."""

from ergoai.domain.models.keypoints import (
    WholeBodyKeypointIndex,
    CameraView,
    Keypoint,
    BoundingBox,
    Pose2D,
    MultiViewPose,
    FrameDetections,
    MultiPersonScene,
)
# Alias para compatibilidad hacia atrás
COCOKeypointIndex = WholeBodyKeypointIndex

from ergoai.domain.models.angles import (
    ActiveSide,
    BiomechanicalAngles,
    AngularDiscrepancy,
)
from ergoai.domain.models.reach_zones import (
    ZoneClassification,
    ReachPointEvaluation,
)
from ergoai.domain.models.reba import (
    REBARiskLevel,
    REBAGroupAScore,
    REBAGroupBScore,
    REBAActivityScore,
    REBAAssessment,
)
from ergoai.domain.models.workstation import (
    WorkstationType,
    RuleStatus,
    RuleOrigin,
    ChairLawAnswers,
    WorkstationDimensions,
    WorkstationLiftingData,
    WorkstationChairData,
    WorkstationConveyorData,
    WorkstationAislesData,
    WorkstationInputData,
)
from ergoai.domain.models.audit import (
    RuleEvaluationResult,
    GlobalStationResult,
    AuditLogEntry,
)
from ergoai.domain.models.simulation import (
    EngineeringControlID,
    EngineeringControlProposal,
    ResidualRiskComparison,
)

__all__ = [
    "WholeBodyKeypointIndex",
    "COCOKeypointIndex",
    "CameraView",
    "Keypoint",
    "BoundingBox",
    "Pose2D",
    "MultiViewPose",
    "FrameDetections",
    "MultiPersonScene",
    "ActiveSide",
    "BiomechanicalAngles",
    "AngularDiscrepancy",
    "ZoneClassification",
    "ReachPointEvaluation",
    "REBARiskLevel",
    "REBAGroupAScore",
    "REBAGroupBScore",
    "REBAActivityScore",
    "REBAAssessment",
    "WorkstationType",
    "RuleStatus",
    "RuleOrigin",
    "ChairLawAnswers",
    "WorkstationDimensions",
    "WorkstationLiftingData",
    "WorkstationChairData",
    "WorkstationConveyorData",
    "WorkstationAislesData",
    "WorkstationInputData",
    "RuleEvaluationResult",
    "GlobalStationResult",
    "AuditLogEntry",
    "EngineeringControlID",
    "EngineeringControlProposal",
    "ResidualRiskComparison",
]
