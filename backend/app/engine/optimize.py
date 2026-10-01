"""Budget-constrained intervention selection.

The objective is *not* an abstract score: every candidate is priced by
:mod:`app.engine.costs` and measured by actually re-running the simulation
engine. A candidate is worth what the engine says it is worth in people spared,
for the scenario the user is looking at.

Greedy marginal-gain knapsack, in three phases:

1. Score every candidate on its own, running the engine once per candidate.
   Candidates that spare nobody are dropped: spending real money for no
   measurable effect is not a proposal.
2. Walk down the gain-per-real ranking, re-measuring the marginal gain of the
   leading candidates against the portfolio built so far. Re-measuring matters
   because hydrological works spill into neighbouring sub-basins, so a second
   intervention next to the first buys less than the standalone estimate.
3. Run the engine once more with the whole portfolio. Every total reported to
   the client comes from that run, never from summing phase-1 estimates, which
   would double count the spillover.

One work per region per type. A greedy ratio ranking would otherwise pile every
reservoir into the two most exposed basins, which both overstates the effect
(the spillover overlap is already priced in by the marginal re-measurement) and
concentrates a city's resilience on a single watercourse.
"""

from __future__ import annotations

from typing import Literal

from app.engine.costs import cost_for
from app.engine.interventions import DEFAULTS
from app.engine.simulation import FACTOR_LABELS, INTERVENTION_LABELS, run_simulation
from app.schemas import (
    CityModel,
    Intervention,
    InterventionType,
    OptimizeRequest,
    OptimizeResponse,
    Point,
    ProposedIntervention,
    Region,
    RegionResult,
    ScenarioParams,
    SimulationTotals,
)

# How many regions are worth proposing works for at all. Below this the model
# starts funding places where the exposure is negligible; above it the greedy
# loop gets slower without changing which few interventions win.
CANDIDATE_REGIONS = 12

# How many top-ranked candidates get their marginal gain re-measured each step.
REFINED_PER_STEP = 8

# How many unaffordable proposals to report back, so the user can see what the
# budget is actually excluding.
REJECTED_LIMIT = 6

UNIT_LABELS: dict[InterventionType, str] = {
    InterventionType.GREEN_AREA: "m2",
    InterventionType.RESERVOIR: "m3",
    InterventionType.SHELTER: "camas",
    InterventionType.ALTERNATE_ROUTE: "km",
    InterventionType.CARE_POST: "posto",
}


def _brl(value: float) -> str:
    """pt-BR thousands separator, for the rationale text."""
    return f"{value:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _pt(value: float) -> str:
    return f"{value:,.0f}".replace(",", ".")


def _priority(region: Region, result: RegionResult) -> float:
    """Rank regions for candidacy: exposure, weighted by vulnerability."""
    metrics = region.metrics
    exposure = result.affected_population / max(1, metrics.population)
    return (
        result.risk * 0.40
        + exposure * 0.30
        + metrics.vulnerability * 0.15
        + min(0.15, result.critical_facilities_affected * 0.05)
    )


def _shortlist(city: CityModel, baseline: list[RegionResult]) -> list[Region]:
    regions = {region.id: region for region in city.regions}
    ranked = sorted(baseline, key=lambda result: -_priority(regions[result.region_id], result))
    return [regions[result.region_id] for result in ranked[:CANDIDATE_REGIONS]]


def _proposal(
    kind: InterventionType,
    region: Region,
    index: int,
    affected_population: int,
    intensity: float,
) -> tuple[Intervention, float]:
    """Build one proposal and price it against this region's exposure."""
    impact_factor = DEFAULTS[kind]
    cost, quantity = cost_for(kind, region, intensity, affected_population, impact_factor)
    intervention = Intervention(
        id=f"opt-{kind.value}-{index}",
        type=kind,
        region_id=region.id,
        location=Point(x=region.centroid.x, y=region.centroid.y),
        impact_factor=impact_factor,
        cost_brl=cost,
        label=INTERVENTION_LABELS[kind],
    )
    return intervention, quantity


def _population_saved(
    city: CityModel,
    scenario: ScenarioParams,
    portfolio: list[Intervention],
    baseline_population: int,
) -> int:
    mitigated = run_simulation(city, scenario, portfolio, "mitigated")
    return max(0, baseline_population - mitigated.totals.affected_population)


def _rationale(
    region: Region,
    kind: InterventionType,
    result: RegionResult,
    saved: int,
    quantity: float,
    cost_brl: float,
) -> str:
    drivers = ", ".join(
        FACTOR_LABELS.get(label, label)
        for label, _ in sorted(result.factors.items(), key=lambda item: -item[1])[:2]
    )
    return (
        f"{region.name} tem {_pt(result.affected_population)} pessoas potencialmente "
        f"afetadas e risco {result.risk:.2f} ({result.risk_level.value}). "
        f"Os fatores dominantes são {drivers}. "
        f"Esta intervenção evita {_pt(saved)} pessoas expostas, é dimensionada em "
        f"{_pt(quantity)} {UNIT_LABELS[kind]} e custa {_brl(cost_brl)}."
    )


def _risk_reduction_pct(baseline: SimulationTotals, mitigated: SimulationTotals) -> float:
    if baseline.high_risk_regions <= 0:
        return 0.0
    return round(
        max(
            0.0,
            (baseline.high_risk_regions - mitigated.high_risk_regions)
            / baseline.high_risk_regions
            * 100.0,
        ),
        1,
    )


def optimize(city: CityModel, request: OptimizeRequest) -> OptimizeResponse:
    scenario = request.scenario
    allowed = request.allowed_types or list(InterventionType)
    intensity = scenario.intensity

    baseline = run_simulation(city, scenario, [], "baseline")
    baseline_population = baseline.totals.affected_population
    exposed = {result.region_id: result.affected_population for result in baseline.regions}
    results = {result.region_id: result for result in baseline.regions}

    # Phase 1: standalone value of each candidate.
    scored: list[tuple[float, Intervention, Region, float, int]] = []
    index = 0
    for region in _shortlist(city, baseline.regions):
        for kind in allowed:
            intervention, quantity = _proposal(kind, region, index, exposed[region.id], intensity)
            index += 1
            saved = _population_saved(city, scenario, [intervention], baseline_population)
            if saved <= 0:
                continue
            ratio = saved / max(1.0, intervention.cost_brl)
            scored.append((ratio, intervention, region, quantity, saved))

    if not scored:
        return OptimizeResponse(
            scenario=scenario,
            budget_brl=request.budget_brl,
            spent_brl=0.0,
            remaining_brl=request.budget_brl,
            baseline_totals=baseline.totals,
            projected_totals=baseline.totals,
            affected_population_avoided=0,
            risk_reduction_pct=0.0,
            selected=[],
            rejected_budget=[],
        )

    scored.sort(key=lambda item: -item[0])

    # Phase 2: greedy, re-measuring the marginal gain of the leaders each step.
    portfolio: list[Intervention] = []
    chosen: list[ProposedIntervention] = []
    spent = 0.0
    taken: set[str] = set()
    taken_sites: set[tuple[InterventionType, str]] = set()

    while len(portfolio) < request.max_interventions:
        affordable = [
            item
            for item in scored
            if item[1].id not in taken
            and (item[1].type, item[1].region_id) not in taken_sites
            and spent + item[1].cost_brl <= request.budget_brl
        ]
        if not affordable:
            break

        current = _population_saved(city, scenario, portfolio, baseline_population)
        best: tuple[float, Intervention, Region, float, int] | None = None
        for _, intervention, region, quantity, _ in affordable[:REFINED_PER_STEP]:
            with_candidate = _population_saved(
                city, scenario, [*portfolio, intervention], baseline_population
            )
            marginal = with_candidate - current
            if marginal <= 0:
                continue
            ratio = marginal / max(1.0, intervention.cost_brl)
            if best is None or ratio > best[0]:
                best = (ratio, intervention, region, quantity, marginal)
        if best is None:
            break

        _, intervention, region, quantity, marginal = best
        portfolio.append(intervention)
        taken.add(intervention.id)
        taken_sites.add((intervention.type, intervention.region_id))
        spent = round(spent + intervention.cost_brl, 2)
        result = results[region.id]
        chosen.append(
            ProposedIntervention(
                type=intervention.type,
                region_id=region.id,
                region_name=region.name,
                label=INTERVENTION_LABELS[intervention.type],
                location=intervention.location,
                cost_brl=intervention.cost_brl,
                impact_factor=intervention.impact_factor,
                expected_affected_population_avoided=marginal,
                expected_risk_reduction=0.0,
                rationale=_rationale(
                    region,
                    intervention.type,
                    result,
                    marginal,
                    quantity,
                    intervention.cost_brl,
                ),
            )
        )

    # Phase 3: one real run of the whole portfolio drives every reported total.
    mitigated = run_simulation(city, scenario, portfolio, "mitigated")
    avoided = max(0, baseline.totals.affected_population - mitigated.totals.affected_population)

    risk_before = {result.region_id: result.risk for result in baseline.regions}
    for proposal in chosen:
        after = next(
            (r.risk for r in mitigated.regions if r.region_id == proposal.region_id),
            risk_before[proposal.region_id],
        )
        proposal.expected_risk_reduction = round(
            max(0.0, risk_before[proposal.region_id] - after), 3
        )

    rejected = [
        ProposedIntervention(
            type=intervention.type,
            region_id=region.id,
            region_name=region.name,
            label=INTERVENTION_LABELS[intervention.type],
            location=intervention.location,
            cost_brl=intervention.cost_brl,
            impact_factor=intervention.impact_factor,
            expected_affected_population_avoided=saved,
            expected_risk_reduction=0.0,
            rationale="Não coube no orçamento restante.",
        )
        for _, intervention, region, _, saved in scored
        if intervention.id not in taken
    ][:REJECTED_LIMIT]

    return OptimizeResponse(
        scenario=scenario,
        budget_brl=request.budget_brl,
        spent_brl=spent,
        remaining_brl=round(request.budget_brl - spent, 2),
        binding_constraint=_binding_constraint(
            len(portfolio), request.max_interventions, spent, request.budget_brl
        ),
        baseline_totals=baseline.totals,
        projected_totals=mitigated.totals,
        affected_population_avoided=avoided,
        risk_reduction_pct=_risk_reduction_pct(baseline.totals, mitigated.totals),
        selected=chosen,
        rejected_budget=rejected,
    )


def _binding_constraint(
    selected_count: int, max_interventions: int, spent: float, budget: float
) -> Literal["budget", "max_interventions"]:
    """Report which limit stopped the search, so a leftover balance reads true.

    A portfolio that stops at the intervention cap leaves money unspent for a
    reason the user can act on, and silently reporting that as "money left over"
    would send them to the wrong place.
    """
    if selected_count >= max_interventions and spent < budget:
        return "max_interventions"
    return "budget"
