"""Simulation engine.

# Weighted-factor model (no ML): every intermediate value is returned in
# `RegionResult.factors` so the UI and the Urban Copilot can explain the result.
"""

from __future__ import annotations

import uuid
from typing import Literal

from app.schemas import (
    CityModel,
    ComparisonDelta,
    Intervention,
    InterventionType,
    Region,
    RegionResult,
    RiskLevel,
    ScenarioParams,
    ScenarioType,
    SimulationComparison,
    SimulationResult,
    SimulationTotals,
)

# Lower bound of the susceptibility index, so a place is never perfectly safe.
SUSCEPTIBILITY_FLOOR = 0.45

# How each intervention type reshapes the risk factors of the region it lands in.
# Keys must match the factor names produced by the per-scenario factor builders.
INTERVENTION_PROFILE: dict[InterventionType, dict[str, float]] = {
    InterventionType.GREEN_AREA: {
        "impermeability": 0.22,
        "vegetation_index": 0.18,
        "infiltration_boost": 0.15,
    },
    InterventionType.RESERVOIR: {
        "impermeability": 0.12,
        "storage_capacity": 0.30,
        "peak_reduction": 0.24,
    },
    InterventionType.SHELTER: {
        "shelter_capacity": 1.0,
        "population_relief": 0.10,
    },
    InterventionType.ALTERNATE_ROUTE: {
        "road_resilience": 0.26,
        "access_reduction": 0.18,
    },
    InterventionType.CARE_POST: {
        "service_pressure_relief": 0.28,
        "critical_exposure": 0.14,
    },
}

INTERVENTION_LABELS: dict[InterventionType, str] = {
    InterventionType.GREEN_AREA: "Área verde",
    InterventionType.RESERVOIR: "Reservatório",
    InterventionType.SHELTER: "Abrigo",
    InterventionType.ALTERNATE_ROUTE: "Rota alternativa",
    InterventionType.CARE_POST: "Ponto de atendimento",
}

# Portuguese names for the keys in RegionResult.factors. Defined beside the
# builders that emit them so a new factor cannot be published unnamed.
FACTOR_LABELS: dict[str, str] = {
    "hazard": "intensidade e duração do evento",
    "drainage_deficit": "déficit de drenagem pela impermeabilidade do solo",
    "storage_capacity": "capacidade de armazenamento de água",
    "terrain_susceptibility": "susceptibilidade do terreno a alagamentos",
    "social_vulnerability": "vulnerabilidade social da população",
    "susceptibility": "susceptibilidade combinada",
    "runoff": "escoamento superficial",
    "shade_deficit": "déficit de sombra e cobertura vegetal",
    "thermal_mass": "capacidade de retenção de calor do solo",
    "heat_exposure": "exposição térmica da região",
    "heat_load": "carga térmica do cenário",
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _round(value: float, digits: int = 3) -> float:
    return round(value, digits)


def risk_level_of(risk: float) -> RiskLevel:
    if risk >= 0.62:
        return RiskLevel.HIGH
    if risk >= 0.34:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


def _hazard_multiplier(scenario: ScenarioParams) -> float:
    severity = _clamp(scenario.intensity) ** 0.85
    exposure_time = 0.55 + 0.45 * _clamp(scenario.duration)
    return _round(severity * exposure_time)


def _bounds(region: Region) -> tuple[float, float, float, float]:
    xs = [p.x for p in region.polygon]
    ys = [p.y for p in region.polygon]
    return min(xs), min(ys), max(xs), max(ys)


# How much of an intervention's effect reaches each neighbouring region.
# Hydrological works (reservoir, green area) drain across boundaries; a shelter
# or a care post only serves the population inside its own region.
SPILLOVER: dict[InterventionType, float] = {
    InterventionType.RESERVOIR: 0.35,
    InterventionType.GREEN_AREA: 0.30,
    InterventionType.ALTERNATE_ROUTE: 0.20,
    InterventionType.SHELTER: 0.0,
    InterventionType.CARE_POST: 0.0,
}

ADJACENCY_TOLERANCE = 1.0


def _adjacency(city: CityModel) -> dict[str, list[str]]:
    neighbours: dict[str, list[str]] = {region.id: [] for region in city.regions}
    boxes = {region.id: _bounds(region) for region in city.regions}
    for a in city.regions:
        ax0, ay0, ax1, ay1 = boxes[a.id]
        for b in city.regions:
            if a.id == b.id:
                continue
            bx0, by0, bx1, by1 = boxes[b.id]
            touches_x = ax0 - ADJACENCY_TOLERANCE <= bx1 and bx0 - ADJACENCY_TOLERANCE <= ax1
            touches_y = ay0 - ADJACENCY_TOLERANCE <= by1 and by0 - ADJACENCY_TOLERANCE <= ay1
            if touches_x and touches_y:
                neighbours[a.id].append(b.id)
    return neighbours


def _distribute(
    city: CityModel, interventions: list[Intervention]
) -> dict[str, list[Intervention]]:
    """Spread each intervention to neighbouring regions with a decayed strength."""
    by_region: dict[str, list[Intervention]] = {}
    for intervention in interventions:
        by_region.setdefault(intervention.region_id, []).append(intervention)

    # Adjacency is an O(regions^2) scan, so it is only worth building when some
    # works actually spill. A baseline run has nothing to spread.
    spilling = [i for i in interventions if SPILLOVER[i.type] > 0]
    if not spilling:
        return by_region

    neighbours = _adjacency(city)
    for intervention in spilling:
        decay = SPILLOVER[intervention.type]
        for neighbour_id in neighbours.get(intervention.region_id, []):
            by_region.setdefault(neighbour_id, []).append(
                intervention.model_copy(
                    update={
                        "id": f"{intervention.id}~{neighbour_id}",
                        "region_id": neighbour_id,
                        "impact_factor": round(intervention.impact_factor * decay, 4),
                        "location": intervention.location,
                    }
                )
            )
    return by_region


def _effective_metrics(
    region: Region, interventions: list[Intervention]
) -> tuple[dict[str, float], list[str]]:
    m = region.metrics
    values = {
        "impermeability": m.impermeability,
        "vegetation_index": m.vegetation_index,
        "infiltration_boost": 0.0,
        "storage_capacity": 0.0,
        "peak_reduction": 0.0,
        "shelter_capacity": 0.0,
        "population_relief": 0.0,
        "road_resilience": 0.0,
        "access_reduction": 0.0,
        "service_pressure_relief": 0.0,
        "critical_exposure": 0.0,
    }
    applied: list[str] = []
    for intervention in interventions:
        profile = INTERVENTION_PROFILE[intervention.type]
        strength = intervention.impact_factor
        for key, coefficient in profile.items():
            if key in {"impermeability"}:
                values[key] -= coefficient * strength
            elif key == "vegetation_index":
                values[key] += coefficient * strength
            else:
                values[key] += coefficient * strength
        label = INTERVENTION_LABELS[intervention.type]
        if "~" in intervention.id:
            applied.append(f"{label} (efeito indireto, fator {strength:.2f})")
        else:
            applied.append(f"{label} (fator {strength:.2f})")
    values["impermeability"] = _clamp(values["impermeability"], 0.05, 0.99)
    values["vegetation_index"] = _clamp(values["vegetation_index"], 0.0, 0.95)
    return values, applied


def _susceptibility(*parts: tuple[float, float]) -> float:
    """Weighted susceptibility lifted onto a floor of SUSCEPTIBILITY_FLOOR.

    Multiplying the raw factors collapses the scale: with Franca's real values
    an impermeable block scores about 0.4, so a product of four sub-unit
    factors never clears 0.62 and no region is ever classified as high risk.
    A weighted mean, then lifted so it spans floor..1, keeps the factors
    readable while letting hazard actually reach the top of the scale.
    """
    total_weight = sum(weight for _, weight in parts)
    if total_weight <= 0:
        return SUSCEPTIBILITY_FLOOR
    weighted = sum(value * weight for value, weight in parts) / total_weight
    return _clamp(SUSCEPTIBILITY_FLOOR + (1.0 - SUSCEPTIBILITY_FLOOR) * weighted)


def _rain_factors(region: Region, effective: dict[str, float], hazard: float) -> dict[str, float]:
    drainage_deficit = _clamp(
        effective["impermeability"] * (1 - 0.6 * effective["vegetation_index"])
    )
    storage = _clamp(effective["storage_capacity"] * 0.6 + effective["infiltration_boost"] * 0.4)
    terrain = _clamp(region.metrics.flood_risk)
    social = _clamp(0.55 + 0.45 * region.metrics.vulnerability)
    susceptibility = _susceptibility(
        (drainage_deficit, 0.40),
        (terrain, 0.35),
        (social, 0.25),
    )
    runoff = _clamp(
        hazard * susceptibility * (1 - 0.45 * storage) * (1 - effective["peak_reduction"])
    )
    return {
        "hazard": hazard,
        "drainage_deficit": _round(drainage_deficit),
        "storage_capacity": _round(storage),
        "terrain_susceptibility": _round(terrain),
        "social_vulnerability": _round(social),
        "susceptibility": _round(susceptibility),
        "runoff": _round(runoff),
        "risk": _round(runoff),
    }


def _heat_factors(region: Region, effective: dict[str, float], hazard: float) -> dict[str, float]:
    shade_deficit = _clamp(1 - effective["vegetation_index"] * 0.9)
    thermal_mass = _clamp(
        0.35 + 0.5 * effective["impermeability"] - 0.2 * effective["storage_capacity"]
    )
    exposure = _clamp(region.metrics.heat_exposure)
    social = _clamp(0.5 + 0.5 * region.metrics.vulnerability)
    susceptibility = _susceptibility(
        (shade_deficit, 0.40),
        (exposure, 0.35),
        (social, 0.25),
    )
    heat_load = _clamp(hazard * susceptibility * (1 - 0.25 * (thermal_mass - 0.5)))
    return {
        "hazard": hazard,
        "shade_deficit": _round(shade_deficit),
        "thermal_mass": _round(thermal_mass),
        "heat_exposure": _round(exposure),
        "social_vulnerability": _round(social),
        "susceptibility": _round(susceptibility),
        "heat_load": _round(heat_load),
        "risk": _round(heat_load),
    }


def _region_result(
    region: Region,
    scenario: ScenarioParams,
    interventions: list[Intervention],
    hazard: float,
) -> RegionResult:
    """Build one region result. ``baseline_risk`` is filled in by the caller.

    A region that receives no work, direct or spilled, has the same risk with
    and without mitigation, so the caller reuses this run's own risk instead of
    paying for a second identical factor computation.
    """
    effective, applied = _effective_metrics(region, interventions)
    if scenario.type is ScenarioType.EXTREME_RAIN:
        factors = _rain_factors(region, effective, hazard)
        impact_multiplier = 1.0
    else:
        factors = _heat_factors(region, effective, hazard)
        impact_multiplier = 1.12

    risk = factors["risk"]
    relief = _clamp(effective["population_relief"])
    affected = int(
        round(region.metrics.population * risk * 0.86 * impact_multiplier * (1 - relief))
    )

    road_resilience = _clamp(effective["road_resilience"])
    access_reduction = _clamp(effective["access_reduction"])
    road_exposure = _clamp(risk * (1 - 0.35 * access_reduction))
    compromised = int(round(region.road_count * road_exposure * (1 - 0.6 * road_resilience)))

    critical_exposure = _clamp(risk * (1 - 0.5 * effective["critical_exposure"]))
    critical_total = sum(1 for f in region.facilities if f.critical)
    critical_affected = int(round(critical_total * critical_exposure))
    if critical_affected == 0 and risk >= 0.62 and critical_total > 0:
        critical_affected = 1

    return RegionResult(
        region_id=region.id,
        risk=_round(risk),
        risk_level=risk_level_of(risk),
        baseline_risk=_round(risk),
        affected_population=affected,
        compromised_roads=compromised,
        critical_facilities_affected=critical_affected,
        factors=factors,
        mitigations_applied=applied,
    )


def run_simulation(
    city: CityModel,
    scenario: ScenarioParams,
    interventions: list[Intervention] | None = None,
    label: Literal["baseline", "mitigated"] = "baseline",
) -> SimulationResult:
    interventions = interventions or []
    hazard = _hazard_multiplier(scenario)
    by_region = _distribute(city, interventions)

    results: list[RegionResult] = []
    for region in city.regions:
        applied = by_region.get(region.id, [])
        result = _region_result(region, scenario, applied, hazard)
        if applied:
            result.baseline_risk = _round(_baseline_risk(city, scenario, region.id, hazard))
        results.append(result)

    totals = SimulationTotals(
        affected_population=sum(r.affected_population for r in results),
        compromised_roads=sum(r.compromised_roads for r in results),
        critical_facilities_affected=sum(r.critical_facilities_affected for r in results),
        high_risk_regions=sum(1 for r in results if r.risk_level is RiskLevel.HIGH),
        population_exposure_index=_round(
            min(
                1.0,
                sum(r.affected_population for r in results)
                / max(1, sum(reg.metrics.population for reg in city.regions)),
            )
        ),
        service_pressure_index=_round(
            min(
                1.0,
                sum(r.critical_facilities_affected for r in results)
                / max(1, sum(len(reg.facilities) for reg in city.regions)),
            )
        ),
    )

    return SimulationResult(
        id=f"sim-{uuid.uuid4().hex[:10]}",
        scenario=scenario,
        interventions=interventions,
        label=label,
        totals=totals,
        regions=results,
    )


def _baseline_risk(
    city: CityModel, scenario: ScenarioParams, region_id: str, hazard: float
) -> float:
    region = next((r for r in city.regions if r.id == region_id), None)
    if region is None:
        return 0.0
    empty, _ = _effective_metrics(region, [])
    factors = (
        _rain_factors(region, empty, hazard)
        if scenario.type is ScenarioType.EXTREME_RAIN
        else _heat_factors(region, empty, hazard)
    )
    return factors["risk"]


def _pct(before: float, after: float) -> float:
    if before <= 0:
        return 0.0
    return _round((after - before) / before * 100.0, 1)


def compare(
    city: CityModel,
    scenario: ScenarioParams,
    interventions: list[Intervention],
    baseline: SimulationResult | None = None,
) -> SimulationComparison:
    """Baseline against mitigated.

    ``baseline`` may be passed when the caller already has it. The baseline is
    independent of the interventions, so recomputing it just burns CPU and risks
    a different result appearing on either side of the comparison.
    """
    if baseline is None:
        baseline = run_simulation(city, scenario, [], "baseline")
    mitigated = run_simulation(city, scenario, interventions, "mitigated")

    base_by_region = {r.region_id: r for r in baseline.regions}
    per_region: list[dict[str, float | int | str]] = []
    for result in mitigated.regions:
        name = next(reg.name for reg in city.regions if reg.id == result.region_id)
        per_region.append(
            {
                "region_id": result.region_id,
                "region_name": name,
                "risk_before": result.baseline_risk,
                "risk_after": result.risk,
                "affected_before": base_by_region[result.region_id].affected_population,
                "affected_after": result.affected_population,
                "delta_pct": _pct(
                    base_by_region[result.region_id].affected_population, result.affected_population
                ),
            }
        )

    return SimulationComparison(
        scenario=scenario,
        baseline=baseline.totals,
        mitigated=mitigated.totals,
        delta=ComparisonDelta(
            affected_population=mitigated.totals.affected_population
            - baseline.totals.affected_population,
            affected_population_pct=_pct(
                baseline.totals.affected_population, mitigated.totals.affected_population
            ),
            compromised_roads=mitigated.totals.compromised_roads
            - baseline.totals.compromised_roads,
            compromised_roads_pct=_pct(
                baseline.totals.compromised_roads, mitigated.totals.compromised_roads
            ),
            critical_facilities_affected=(
                mitigated.totals.critical_facilities_affected
                - baseline.totals.critical_facilities_affected
            ),
            critical_facilities_affected_pct=_pct(
                baseline.totals.critical_facilities_affected,
                mitigated.totals.critical_facilities_affected,
            ),
            service_pressure_index=_round(
                mitigated.totals.service_pressure_index - baseline.totals.service_pressure_index
            ),
        ),
        per_region=per_region,
    )
