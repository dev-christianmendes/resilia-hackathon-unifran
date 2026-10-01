from app.data import get_city
from app.engine.interventions import DEFAULTS
from app.schemas import (
    Intervention,
    InterventionType,
    Point,
    ScenarioParams,
    ScenarioType,
)


def scenario_rain(intensity: float = 0.8, duration: float = 0.6) -> ScenarioParams:
    return ScenarioParams(type=ScenarioType.EXTREME_RAIN, intensity=intensity, duration=duration)


def scenario_heat(intensity: float = 0.8, duration: float = 0.6) -> ScenarioParams:
    return ScenarioParams(type=ScenarioType.HEAT_WAVE, intensity=intensity, duration=duration)


def intervention(
    kind: InterventionType, region_id: str, factor: float | None = None
) -> Intervention:
    city = get_city()
    region = next(r for r in city.regions if r.id == region_id)
    return Intervention(
        id=f"test-{kind.value}",
        type=kind,
        region_id=region_id,
        location=Point(x=region.centroid.x, y=region.centroid.y),
        impact_factor=DEFAULTS[kind] if factor is None else factor,
    )
