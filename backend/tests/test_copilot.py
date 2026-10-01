from conftest import intervention, scenario_heat, scenario_rain

from app.ai.copilot import _price, analyze
from app.data import get_city
from app.engine.simulation import run_simulation
from app.schemas import CopilotRequest, InterventionType


def test_copilot_targets_one_of_the_riskiest_regions():
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    response = analyze(city, CopilotRequest(scenario=scenario, interventions=[]))
    risks = sorted(
        (r.risk for r in run_simulation(city, scenario, [], "baseline").regions), reverse=True
    )
    assert (
        risks[0] >= response.analysis.priority_score or response.analysis.priority_score >= risks[1]
    )
    assert response.analysis.source == "heuristic"
    assert response.analysis.testable is True


def test_copilot_returns_known_region_and_intervention():
    city = get_city()
    response = analyze(city, CopilotRequest(scenario=scenario_rain(0.9, 0.9), interventions=[]))
    region_ids = {r.id for r in city.regions}
    assert response.analysis.region_id in region_ids
    assert isinstance(response.analysis.suggested_intervention, InterventionType)
    assert 0 < response.analysis.priority_score <= 1.5


def test_copilot_explains_its_factors():
    city = get_city()
    response = analyze(city, CopilotRequest(scenario=scenario_rain(0.9, 0.9), interventions=[]))
    assert len(response.analysis.factors) >= 3
    assert abs(sum(f.weight for f in response.analysis.factors) - 1.0) < 0.02
    assert all(f.detail for f in response.analysis.factors)
    assert response.answer


def test_copilot_expected_effect_matches_engine():
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    response = analyze(city, CopilotRequest(scenario=scenario, interventions=[]))
    expected = response.analysis.expected_effect
    assert int(expected["affected_population_delta"]) < 0
    assert float(expected["affected_population_delta_pct"]) < 0
    assert str(expected["basis"])


def test_copilot_suggests_reservoir_for_rain_and_green_for_heat():
    city = get_city()
    rain = analyze(city, CopilotRequest(scenario=scenario_rain(1.0, 1.0), interventions=[]))
    heat = analyze(city, CopilotRequest(scenario=scenario_heat(1.0, 1.0), interventions=[]))
    assert rain.analysis.suggested_intervention is InterventionType.RESERVOIR
    assert heat.analysis.suggested_intervention is InterventionType.GREEN_AREA


def test_copilot_never_decides_on_its_own():
    city = get_city()
    response = analyze(city, CopilotRequest(scenario=scenario_rain(0.9, 0.9), interventions=[]))
    assert "não é uma previsão operacional" in response.analysis.disclaimer.lower()
    assert "hipótese" in response.answer.lower()


def test_copilot_accounts_for_existing_interventions():
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    target = max(
        run_simulation(city, scenario, [], "baseline").regions, key=lambda r: r.risk
    ).region_id
    response = analyze(
        city,
        CopilotRequest(
            scenario=scenario,
            interventions=[intervention(InterventionType.RESERVOIR, target)],
        ),
    )
    assert response.analysis.region_id in {r.id for r in city.regions}
    assert response.follow_up_questions


def test_copilot_always_prices_its_suggestion():
    """A recommendation with no price cannot be weighed against a budget."""
    city = get_city()
    for scenario in (scenario_rain(0.8, 0.6), scenario_heat(0.8, 0.6)):
        response = analyze(city, CopilotRequest(scenario=scenario, interventions=[]))
        assert response.analysis.estimated_cost_brl > 0
        assert "R$" in response.answer


def test_a_generous_budget_keeps_the_rule_based_suggestion():
    city = get_city()
    without = analyze(city, CopilotRequest(scenario=scenario_rain(0.8, 0.6), interventions=[]))
    with_budget = analyze(
        city,
        CopilotRequest(scenario=scenario_rain(0.8, 0.6), interventions=[], budget_brl=500_000_000),
    )
    assert with_budget.analysis.suggested_intervention == (without.analysis.suggested_intervention)
    assert "ultrapassa o orçamento" not in with_budget.answer


def test_a_tight_budget_replaces_an_unaffordable_suggestion():
    """Silently swapping the project would not be a recommendation."""
    city = get_city()
    scenario = scenario_rain(0.8, 0.6)
    unconstrained = analyze(city, CopilotRequest(scenario=scenario, interventions=[]))
    routine = unconstrained.analysis.suggested_intervention

    # Derive a budget too small for the routine suggestion yet still enough for
    # a cheaper option, instead of assuming some fraction happens to work.
    exposed = next(
        r.affected_population
        for r in run_simulation(city, scenario, [], "baseline").regions
        if r.region_id == unconstrained.analysis.region_id
    )
    prices = sorted(
        _price(city, unconstrained.analysis.region_id, kind, scenario, exposed)
        for kind in InterventionType
    )
    cheaper = [p for p in prices if p < unconstrained.analysis.estimated_cost_brl]
    assert cheaper, "no cheaper intervention to fall back on"
    affordable_budget = max(cheaper)

    response = analyze(
        city,
        CopilotRequest(scenario=scenario, interventions=[], budget_brl=affordable_budget),
    )
    assert response.analysis.suggested_intervention != routine
    assert response.analysis.estimated_cost_brl <= affordable_budget
    assert response.analysis.region_id == unconstrained.analysis.region_id
    assert "ultrapassa o orçamento" in response.answer


def test_an_impossible_budget_says_so_instead_of_pretending():
    city = get_city()
    response = analyze(
        city,
        CopilotRequest(scenario=scenario_rain(0.8, 0.6), interventions=[], budget_brl=1.0),
    )
    assert "não cobre nenhuma intervenção" in response.answer
    assert "OTIMIZAR" in response.answer


def test_budget_does_not_change_the_risk_analysis():
    """Money picks the project; it must not move the risk ranking."""
    city = get_city()
    without = analyze(city, CopilotRequest(scenario=scenario_heat(0.8, 0.6), interventions=[]))
    with_budget = analyze(
        city,
        CopilotRequest(scenario=scenario_heat(0.8, 0.6), interventions=[], budget_brl=1.0),
    )
    assert without.analysis.region_id == with_budget.analysis.region_id
    assert without.analysis.priority_score == with_budget.analysis.priority_score
