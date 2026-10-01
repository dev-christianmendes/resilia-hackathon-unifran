from conftest import intervention, scenario_rain

from app.data import get_city
from app.engine.simulation import compare, run_simulation
from app.schemas import InterventionType


def riskiest_region_id() -> str:
    """The region the current scenario hurts most, so tests follow the data."""
    city = get_city()
    baseline = run_simulation(city, scenario_rain(0.9, 0.9), [], "baseline")
    return max(baseline.regions, key=lambda r: r.risk).region_id


def test_comparison_reports_reduction():
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    interventions = [intervention(InterventionType.RESERVOIR, riskiest_region_id())]
    result = compare(city, scenario, interventions)
    assert result.baseline.affected_population > result.mitigated.affected_population
    assert result.delta.affected_population < 0
    assert result.delta.affected_population_pct < 0


def test_comparison_without_interventions_is_flat():
    city = get_city()
    result = compare(city, scenario_rain(0.9, 0.9), [])
    assert result.delta.affected_population == 0
    assert result.delta.affected_population_pct == 0


def test_comparison_covers_every_region():
    city = get_city()
    result = compare(city, scenario_rain(0.9, 0.9), [])
    assert len(result.per_region) == len(city.regions)
    for row in result.per_region:
        assert row["region_name"]
        assert row["risk_before"] == row["risk_after"]


def test_stronger_intervention_yields_better_outcome():
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    target = riskiest_region_id()
    weak = compare(city, scenario, [intervention(InterventionType.RESERVOIR, target, 0.3)])
    strong = compare(city, scenario, [intervention(InterventionType.RESERVOIR, target, 1.0)])
    assert strong.mitigated.affected_population < weak.mitigated.affected_population
