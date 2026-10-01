"""The budget-constrained optimiser.

These tests care about the promises the response makes, not about which
intervention happens to win: the budget is respected, the reported totals come
from a real engine run, and the cost assumptions are visible to the caller.
"""

from app.data import get_city
from app.data.geo import polygon_area
from app.engine.costs import (
    ASSUMPTION_NOTICE,
    COSTS,
    cost_for,
    quantity_for,
    region_area_m2,
)
from app.engine.optimize import optimize
from app.engine.simulation import run_simulation
from app.schemas import (
    Intervention,
    InterventionType,
    OptimizeRequest,
    ScenarioParams,
)
from tests.conftest import scenario_heat, scenario_rain

BUDGET = 50_000_000.0


def request_for(
    scenario: ScenarioParams, budget: float = BUDGET, max_n: int = 6
) -> OptimizeRequest:
    return OptimizeRequest(scenario=scenario, budget_brl=budget, max_interventions=max_n)


def test_area_helper_matches_the_published_polygon():
    """The inline shoelace must agree with the shared geometry helper."""
    city = get_city()
    for region in city.regions[:5]:
        expected = polygon_area([(p.x, p.y) for p in region.polygon])
        assert abs(region_area_m2(region) - expected) < 1e-6


def test_every_cost_is_bounded_by_its_own_floor_and_cap():
    city = get_city()
    for kind, model in COSTS.items():
        for region in city.regions:
            cost, _ = cost_for(kind, region, 0.8, 40_000, 0.75)
            assert model.minimum_brl <= cost <= model.maximum_brl
            assert cost > 0


def test_cost_grows_with_exposed_population_where_it_should():
    """People-serving work must be priced against the people it serves."""
    city = get_city()
    region = next(r for r in city.regions if r.road_count > 0)
    few, _ = cost_for(InterventionType.SHELTER, region, 0.8, 100, 0.8)
    many, _ = cost_for(InterventionType.SHELTER, region, 0.8, 40_000, 0.8)
    assert many > few


def test_reservoir_scales_with_sealed_area():
    """Runoff comes from the impermeable fraction, so two regions differ."""
    city = get_city()
    ranked = sorted(city.regions, key=lambda r: region_area_m2(r) * r.metrics.impermeability)
    low, high = ranked[0], ranked[-1]
    low_cost, _ = cost_for(InterventionType.RESERVOIR, low, 0.8, 0, 0.8)
    high_cost, _ = cost_for(InterventionType.RESERVOIR, high, 0.8, 0, 0.8)
    assert high_cost > low_cost


def test_quantity_never_exceeds_the_published_cap():
    city = get_city()
    region = max(city.regions, key=region_area_m2)
    for kind, model in COSTS.items():
        quantity = quantity_for(kind, region, 1.0, 1_000_000)
        # The cap is expressed in money; convert back through the unit price.
        assert quantity * model.unit_cost_brl <= model.maximum_brl * 1.01


def test_optimize_never_exceeds_the_budget():
    city = get_city()
    result = optimize(city, request_for(scenario_rain(), budget=5_000_000))
    assert result.spent_brl <= 5_000_000
    assert result.remaining_brl == round(5_000_000 - result.spent_brl, 2)
    assert result.spent_brl == round(sum(p.cost_brl for p in result.selected), 2)


def test_optimize_reports_a_real_engine_run():
    """Projected totals must equal a fresh run, not a sum of estimates."""
    city = get_city()
    scenario = scenario_rain()
    result = optimize(city, request_for(scenario))

    replay = run_simulation(
        city,
        scenario,
        [
            Intervention(
                id=f"replay-{index}",
                type=proposal.type,
                region_id=proposal.region_id,
                location=proposal.location,
                impact_factor=proposal.impact_factor,
                cost_brl=proposal.cost_brl,
            )
            for index, proposal in enumerate(result.selected)
        ],
        "mitigated",
    )
    assert replay.totals.affected_population == result.projected_totals.affected_population
    assert result.affected_population_avoided == (
        result.baseline_totals.affected_population - replay.totals.affected_population
    )


def test_optimize_actually_reduces_exposure():
    city = get_city()
    for scenario in (scenario_rain(), scenario_heat()):
        result = optimize(city, request_for(scenario))
        assert result.selected, f"nothing selected for {scenario.type}"
        assert result.affected_population_avoided > 0
        assert (
            result.projected_totals.affected_population < result.baseline_totals.affected_population
        )


def test_one_work_per_region_and_type():
    city = get_city()
    result = optimize(city, request_for(scenario_rain(), max_n=12))
    sites = [(p.type, p.region_id) for p in result.selected]
    assert len(sites) == len(set(sites))


def test_selection_spreads_across_regions():
    """A portfolio stacked on two basins would not be a city plan."""
    city = get_city()
    result = optimize(city, request_for(scenario_rain(), max_n=12))
    assert len({p.region_id for p in result.selected}) >= 8


def test_binding_constraint_is_reported_honestly():
    city = get_city()
    scenario = scenario_rain()

    capped = optimize(city, request_for(scenario, budget=BUDGET, max_n=3))
    assert capped.binding_constraint == "max_interventions"
    assert capped.spent_brl < BUDGET

    starved = optimize(city, request_for(scenario, budget=3_000_000, max_n=12))
    assert starved.binding_constraint == "budget"


def test_allowed_types_are_respected():
    city = get_city()
    result = optimize(
        city,
        OptimizeRequest(
            scenario=scenario_rain(),
            budget_brl=BUDGET,
            max_interventions=6,
            allowed_types=[InterventionType.CARE_POST, InterventionType.ALTERNATE_ROUTE],
        ),
    )
    assert {p.type for p in result.selected} <= {
        InterventionType.CARE_POST,
        InterventionType.ALTERNATE_ROUTE,
    }


def test_tiny_budget_selects_nothing_and_stays_consistent():
    city = get_city()
    result = optimize(city, request_for(scenario_rain(), budget=1.0))
    assert result.selected == []
    assert result.spent_brl == 0.0
    assert result.remaining_brl == 1.0
    assert result.projected_totals.affected_population == (
        result.baseline_totals.affected_population
    )


def test_every_proposal_carries_a_rationale_and_a_price():
    city = get_city()
    result = optimize(city, request_for(scenario_heat()))
    for proposal in result.selected:
        assert proposal.rationale
        assert proposal.cost_brl > 0
        assert proposal.expected_affected_population_avoided > 0


def test_rejected_proposals_are_only_the_ones_left_out():
    city = get_city()
    result = optimize(city, request_for(scenario_rain(), max_n=4))
    selected_ids = {(p.region_id, p.type) for p in result.selected}
    for proposal in result.rejected_budget:
        assert (proposal.region_id, proposal.type) not in selected_ids


def test_response_publishes_the_cost_assumptions():
    city = get_city()
    result = optimize(city, request_for(scenario_rain()))
    assert "hipótese" in result.cost_assumptions.lower()
    assert ASSUMPTION_NOTICE
    assert result.disclaimer


def test_quantities_are_physical_work_not_the_discounted_figure():
    """A rationale saying "1.500 m3" must mean 1.500 m3 of reservoir."""
    city = get_city()
    region = next(r for r in city.regions if r.road_count > 0)

    # A weaker intervention costs less but is not a smaller building.
    strong_cost, strong_qty = cost_for(InterventionType.SHELTER, region, 0.8, 40_000, 1.0)
    weak_cost, weak_qty = cost_for(InterventionType.SHELTER, region, 0.8, 40_000, 0.2)
    assert strong_cost > weak_cost
    assert strong_qty == weak_qty

    # And the reported quantity is the physical size, not the discounted figure.
    assert strong_qty == quantity_for(InterventionType.SHELTER, region, 0.8, 40_000)


def test_whole_units_are_whole_numbers():
    """Half a shelter bed or a third of a care post cannot be built."""
    city = get_city()
    for region in city.regions:
        for kind in (InterventionType.SHELTER, InterventionType.CARE_POST):
            quantity = quantity_for(kind, region, 0.8, region.metrics.population)
            assert quantity == int(quantity), f"{kind.value} sized to {quantity}"
            assert quantity >= 1.0


def test_care_post_rounds_up_rather_than_below_one():
    city = get_city()
    for region in city.regions:
        # Even a lightly exposed region gets at least one post.
        assert quantity_for(InterventionType.CARE_POST, region, 0.1, 1) == 1.0
