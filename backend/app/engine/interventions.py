"""Intervention catalogue exposed to the UI (impact factors, suggested defaults)."""

from __future__ import annotations

from app.engine.simulation import INTERVENTION_LABELS, INTERVENTION_PROFILE
from app.schemas import Intervention, InterventionType, Point

DEFAULTS: dict[InterventionType, float] = {
    InterventionType.GREEN_AREA: 0.60,
    InterventionType.RESERVOIR: 0.75,
    InterventionType.SHELTER: 0.80,
    InterventionType.ALTERNATE_ROUTE: 0.70,
    InterventionType.CARE_POST: 0.70,
}

DESCRIPTIONS: dict[InterventionType, str] = {
    InterventionType.GREEN_AREA: "Aumenta a cobertura vegetal e a permeabilidade do solo.",
    InterventionType.RESERVOIR: "Acumula o excedente de escoamento e reduz o pico de vazão.",
    InterventionType.SHELTER: "Estrutura de acolhimento que reduz a população diretamente exposta.",
    InterventionType.ALTERNATE_ROUTE: "Desvia o tráfego de vias expostas durante o evento.",
    InterventionType.CARE_POST: "Distribui a demanda sobre os equipamentos de saúde da região.",
}


def catalogue() -> list[dict[str, object]]:
    return [
        {
            "type": kind.value,
            "label": INTERVENTION_LABELS[kind],
            "description": DESCRIPTIONS[kind],
            "default_impact_factor": DEFAULTS[kind],
            "effects": INTERVENTION_PROFILE[kind],
        }
        for kind in InterventionType
    ]


def normalize(intervention: Intervention) -> Intervention:
    if intervention.type is InterventionType.RESERVOIR and intervention.impact_factor == 0:
        intervention.impact_factor = DEFAULTS[InterventionType.RESERVOIR]
    return intervention


def place(
    intervention_type: InterventionType,
    region_id: str,
    location: Point,
    impact_factor: float,
    index: int,
) -> Intervention:
    return normalize(
        Intervention(
            id=f"int-{intervention_type.value}-{index}",
            type=intervention_type,
            region_id=region_id,
            location=location,
            impact_factor=impact_factor,
        )
    )
