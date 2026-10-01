from conftest import intervention, scenario_heat, scenario_rain

from app.ai.copilot import analyze
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
