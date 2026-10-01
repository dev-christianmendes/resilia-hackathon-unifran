from fastapi.testclient import TestClient

from app.main import app
from app.schemas import CopilotRequest, ScenarioParams, ScenarioType

client = TestClient(app)

RAIN = {"type": "extreme_rain", "intensity": 0.8, "duration": 0.6}


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_city_payload_is_complete():
    payload = client.get("/api/city").json()
    assert payload["regions"]
    assert payload["roads"]
    assert payload["buildings"]
    assert payload["trees"]
    assert payload["waterways"]
    assert payload["facilities"]
    assert payload["elevation"]["values"]
    assert payload["vulnerability_points"]
    assert payload["sources"]
    # Sub-basins traced from the drainage network, so the outlines are real
    # catchment boundaries rather than fixed boxes.
    for region in payload["regions"]:
        assert len(region["polygon"]) >= 3
        assert "vegetation_index" in region["metrics"]
        assert region["metrics"]["population_is_estimated"] is True


def test_catalogue_lists_all_interventions():
    items = client.get("/api/interventions/catalogue").json()
    types = {item["type"] for item in items}
    assert types == {
        "green_area",
        "reservoir",
        "shelter",
        "alternate_route",
        "care_post",
    }
    for item in items:
        assert item["label"]
        assert 0 < item["default_impact_factor"] <= 1


def test_simulate_baseline():
    city = client.get("/api/city").json()
    payload = client.post("/api/simulate", json={"scenario": RAIN, "interventions": []}).json()
    assert payload["label"] == "baseline"
    assert payload["totals"]["affected_population"] > 0
    assert len(payload["regions"]) == len(city["regions"])
    for region in payload["regions"]:
        assert 0 <= region["risk"] <= 1
        assert region["factors"]


def test_simulate_with_intervention_is_labelled_mitigated():
    city = client.get("/api/city").json()
    region = max(city["regions"], key=lambda r: r["metrics"]["flood_risk"])
    intervention = {
        "id": "int-api-1",
        "type": "reservoir",
        "region_id": region["id"],
        "location": region["centroid"],
        "impact_factor": 0.8,
    }
    payload = client.post(
        "/api/simulate", json={"scenario": RAIN, "interventions": [intervention]}
    ).json()
    assert payload["label"] == "mitigated"
    assert payload["interventions"]


def test_compare_endpoint():
    city = client.get("/api/city").json()
    region = city["regions"][0]
    intervention = {
        "id": "int-api-2",
        "type": "reservoir",
        "region_id": region["id"],
        "location": region["centroid"],
        "impact_factor": 0.8,
    }
    payload = client.post(
        "/api/compare", json={"scenario": RAIN, "interventions": [intervention]}
    ).json()
    assert payload["baseline"]["affected_population"] > payload["mitigated"]["affected_population"]
    assert len(payload["per_region"]) == len(city["regions"])


def test_copilot_endpoint():
    payload = client.post(
        "/api/copilot",
        json=CopilotRequest(
            scenario=ScenarioParams(type=ScenarioType.EXTREME_RAIN, intensity=0.8, duration=0.6)
        ).model_dump(),
    ).json()
    assert payload["analysis"]["region_id"]
    assert payload["analysis"]["suggested_intervention"]
    assert payload["answer"]


def test_run_returns_both_halves_consistently():
    """The two halves must come from one call, not two racing ones."""
    scenario = ScenarioParams(type=ScenarioType.EXTREME_RAIN, intensity=0.8, duration=0.6)
    baseline_only = client.post(
        "/api/run", json={"scenario": scenario.model_dump(), "interventions": []}
    ).json()

    assert baseline_only["total_cost_brl"] == 0
    assert baseline_only["within_budget"] is True
    assert (
        baseline_only["baseline"]["totals"]["affected_population"]
        == baseline_only["mitigated"]["totals"]["affected_population"]
    )
    assert baseline_only["comparison"]["delta"]["affected_population"] == 0
    # Both halves are the same run, so the ids match too.
    assert baseline_only["baseline"]["id"] == baseline_only["mitigated"]["id"]


def test_run_marks_over_budget_interventions():
    scenario = ScenarioParams(type=ScenarioType.EXTREME_RAIN, intensity=0.8, duration=0.6)
    city_region = client.get("/api/city").json()["regions"][0]
    intervention = {
        "id": "int-caro",
        "type": "reservoir",
        "region_id": city_region["id"],
        "location": city_region["centroid"],
        "impact_factor": 0.75,
        "cost_brl": 9_000_000.0,
    }

    within = client.post(
        "/api/run",
        json={
            "scenario": scenario.model_dump(),
            "interventions": [intervention],
            "budget_brl": 10_000_000.0,
        },
    ).json()
    assert within["within_budget"] is True
    assert within["total_cost_brl"] == 9_000_000.0
    assert within["mitigated"]["label"] == "mitigated"
    assert within["comparison"]["delta"]["affected_population"] < 0

    over = client.post(
        "/api/run",
        json={
            "scenario": scenario.model_dump(),
            "interventions": [intervention],
            "budget_brl": 1_000.0,
        },
    ).json()
    assert over["within_budget"] is False


def test_run_without_budget_is_always_within_budget():
    scenario = ScenarioParams(type=ScenarioType.HEAT_WAVE, intensity=0.5, duration=0.4)
    payload = client.post(
        "/api/run", json={"scenario": scenario.model_dump(), "interventions": []}
    ).json()
    assert payload["budget_brl"] is None
    assert payload["within_budget"] is True


def test_optimize_endpoint():
    scenario = ScenarioParams(type=ScenarioType.EXTREME_RAIN, intensity=0.8, duration=0.6)
    payload = client.post(
        "/api/optimize",
        json={"scenario": scenario.model_dump(), "budget_brl": 20_000_000, "max_interventions": 5},
    ).json()

    assert payload["selected"]
    assert payload["spent_brl"] <= 20_000_000
    assert payload["affected_population_avoided"] > 0
    assert payload["binding_constraint"] in {"budget", "max_interventions"}
    assert payload["cost_assumptions"]
    for proposal in payload["selected"]:
        assert proposal["region_name"]
        assert proposal["rationale"]
        assert proposal["cost_brl"] > 0


def test_optimize_rejects_a_zero_budget():
    scenario = ScenarioParams(type=ScenarioType.EXTREME_RAIN, intensity=0.8, duration=0.6)
    response = client.post(
        "/api/optimize", json={"scenario": scenario.model_dump(), "budget_brl": 0}
    )
    assert response.status_code == 422


def test_costs_catalogue_is_published():
    payload = client.get("/api/costs/catalogue").json()
    priced = [row for row in payload if row["type"] != "notice"]
    assert {row["type"] for row in priced} == {
        "green_area",
        "reservoir",
        "shelter",
        "alternate_route",
        "care_post",
    }
    for row in priced:
        assert row["unit_cost_brl"] > 0
        assert row["minimum_brl"] <= row["maximum_brl"]
    assert any("notice" in row for row in payload)


def test_out_of_range_intensity_is_rejected():
    response = client.post(
        "/api/simulate",
        json={"scenario": {"type": "extreme_rain", "intensity": 1.5, "duration": 0.6}},
    )
    assert response.status_code == 422


def test_unknown_scenario_type_is_rejected():
    response = client.post(
        "/api/simulate",
        json={"scenario": {"type": "meteor_strike", "intensity": 0.5, "duration": 0.5}},
    )
    assert response.status_code == 422


def test_scenarios_catalogue():
    items = client.get("/api/scenarios").json()
    assert {item["type"] for item in items} == {"extreme_rain", "heat_wave"}
