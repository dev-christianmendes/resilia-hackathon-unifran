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
