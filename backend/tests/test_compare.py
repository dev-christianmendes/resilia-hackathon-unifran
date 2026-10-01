from conftest import intervention, scenario_rain

from app.data import get_city
from app.engine.interventions import normalize
from app.engine.simulation import compare, run_simulation
from app.schemas import Intervention, InterventionType, ScenarioParams, ScenarioType


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


def test_comparison_reuses_a_baseline_it_was_given():
    """A caller holding the baseline should not pay for it twice."""
    city = get_city()
    scenario = ScenarioParams(type=ScenarioType.EXTREME_RAIN, intensity=0.8, duration=0.6)
    baseline = run_simulation(city, scenario, [], "baseline")

    reused = compare(city, scenario, [], baseline)
    fresh = compare(city, scenario, [])

    assert reused.baseline == fresh.baseline == baseline.totals
    assert reused.delta == fresh.delta


def test_reused_and_fresh_comparisons_agree():
    city = get_city()
    scenario = ScenarioParams(type=ScenarioType.HEAT_WAVE, intensity=0.7, duration=0.5)
    intervention = normalize(
        Intervention(
            id="int-1",
            type=InterventionType.GREEN_AREA,
            region_id=city.regions[0].id,
            location=city.regions[0].centroid,
            impact_factor=0.75,
            cost_brl=1_000_000,
        )
    )
    baseline = run_simulation(city, scenario, [], "baseline")
    assert (
        compare(city, scenario, [intervention], baseline).delta
        == compare(city, scenario, [intervention]).delta
    )
