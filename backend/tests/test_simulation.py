from conftest import intervention, scenario_heat, scenario_rain

from app.data import get_city
from app.data.geo import polygon_area
from app.engine.simulation import _adjacency, risk_level_of, run_simulation
from app.schemas import InterventionType


def test_city_is_deterministic():
    first = get_city()
    second = get_city()
    assert [r.name for r in first.regions] == [r.name for r in second.regions]
    assert [r.metrics.population for r in first.regions] == [
        r.metrics.population for r in second.regions
    ]


def test_regions_follow_the_real_hydrology():
    """Sub-basins must be named after real watercourses and cover the terrain."""
    city = get_city()
    names = {r.name for r in city.regions}
    assert any("Córrego" in n or "Ribeirão" in n for n in names), names
    assert any(len(r.polygon) > 8 for r in city.regions), "contornos muito simplificados"
    total_area = sum(polygon_area([(p.x, p.y) for p in r.polygon]) for r in city.regions)
    assert total_area > 50_000_000, f"sub-bacias cobrem apenas {total_area / 1e6:.1f} km2"


def test_population_preserves_the_ibge_total():
    city = get_city()
    total = sum(r.metrics.population for r in city.regions)
    assert total == 365_494, "a soma das sub-bacias deve fechar com o IBGE"
    assert max(r.metrics.population for r in city.regions) < total, "população não pode concentrar"
    assert min(r.metrics.population for r in city.regions) >= 0


def test_elevation_comes_from_the_dem():
    city = get_city()
    assert city.elevation is not None
    values = city.elevation.values
    assert min(values) > 700 and max(values) < 1100, "relevo fora de Franca"
    for region in city.regions:
        assert region.metrics.elevation_min_m <= region.metrics.elevation_max_m
    assert len({round(r.metrics.elevation_m) for r in city.regions}) > 20


def test_documented_vulnerability_points_land_in_regions():
    city = get_city()
    assert len(city.vulnerability_points) == 5
    attributed = sum(r.metrics.historical_events for r in city.regions)
    assert attributed == len(city.vulnerability_points), "pontos do plano ficaram de fora"
    for point in city.vulnerability_points:
        assert point.reference
        assert point.severity > 0


def test_every_region_has_infrastructure():
    city = get_city()
    for region in city.regions:
        assert 0 <= region.metrics.vegetation_index <= 1
        assert 0 <= region.metrics.impermeability <= 1
        assert 0 <= region.metrics.flood_risk <= 1
        assert 0 <= region.metrics.heat_exposure <= 1
        assert region.metrics.elevation_min_m <= region.metrics.elevation_m
        assert region.metrics.elevation_m <= region.metrics.elevation_max_m
    # Peripheral sub-basins genuinely have no mapped street or public facility,
    # so the guarantee is about the city, not about every single region.
    assert any(r.facilities for r in city.regions)
    assert any(r.road_count > 0 for r in city.regions)
    assert sum(len(r.facilities) for r in city.regions) == len(city.facilities)


def test_risk_increases_with_intensity():
    city = get_city()
    low = run_simulation(city, scenario_rain(0.3, 0.3), [], "baseline")
    high = run_simulation(city, scenario_rain(1.0, 1.0), [], "baseline")
    assert high.totals.affected_population > low.totals.affected_population
    assert high.totals.high_risk_regions > low.totals.high_risk_regions


def test_risk_increases_with_duration():
    city = get_city()
    short = run_simulation(city, scenario_rain(0.8, 0.2), [], "baseline")
    long = run_simulation(city, scenario_rain(0.8, 1.0), [], "baseline")
    assert long.totals.affected_population > short.totals.affected_population


def test_extreme_scenario_reaches_high_risk_regions():
    city = get_city()
    result = run_simulation(city, scenario_rain(1.0, 1.0), [], "baseline")
    assert result.totals.high_risk_regions >= 2
    assert any(r.risk_level.value == "high" for r in result.regions)


def test_heat_wave_spares_vegetated_regions():
    city = get_city()
    heat = run_simulation(city, scenario_heat(0.9, 0.9), [], "baseline")
    heat_by_id = {r.region_id: r.risk for r in heat.regions}

    greenest = max(city.regions, key=lambda r: r.metrics.vegetation_index)
    barest = min(city.regions, key=lambda r: r.metrics.vegetation_index)
    assert heat_by_id[greenest.id] < heat_by_id[barest.id]
    assert heat.totals.affected_population > 0


def test_green_area_reduces_heat_risk():
    city = get_city()
    scenario = scenario_heat(0.9, 0.9)
    baseline = run_simulation(city, scenario, [], "baseline")
    target = max(baseline.regions, key=lambda r: r.risk)
    mitigated = run_simulation(
        city, scenario, [intervention(InterventionType.GREEN_AREA, target.region_id)], "mitigated"
    )
    after = next(r for r in mitigated.regions if r.region_id == target.region_id)
    assert after.risk < target.risk


def test_heat_wave_exposes_health_equipment():
    city = get_city()
    heat = run_simulation(city, scenario_heat(1.0, 1.0), [], "baseline")
    assert heat.totals.critical_facilities_affected > 0
    assert heat.totals.service_pressure_index > 0


def test_intervention_reduces_risk_in_target_region():
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    baseline = run_simulation(city, scenario, [], "baseline")
    target = max(baseline.regions, key=lambda r: r.risk)
    mitigated = run_simulation(
        city, scenario, [intervention(InterventionType.RESERVOIR, target.region_id)], "mitigated"
    )
    before = next(r for r in baseline.regions if r.region_id == target.region_id)
    after = next(r for r in mitigated.regions if r.region_id == target.region_id)
    assert after.risk < before.risk
    assert after.baseline_risk == before.risk
    assert after.mitigations_applied


def test_intervention_spills_over_to_neighbours_for_hydraulic_works():
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    baseline = run_simulation(city, scenario, [], "baseline")
    # A reach with the most neighbours, so the spill-over has somewhere to go.
    neighbours = _adjacency(city)
    target = max(city.regions, key=lambda r: len(neighbours[r.id]))
    assert neighbours[target.id], "nenhuma regiao tem vizinhas para testar"
    mitigated = run_simulation(
        city, scenario, [intervention(InterventionType.RESERVOIR, target.id)], "mitigated"
    )
    changed = [
        r
        for r in mitigated.regions
        if r.risk < next(b.risk for b in baseline.regions if b.region_id == r.region_id)
    ]
    assert len(changed) > 1, "reservatório deveria alcançar regiões vizinhas"


def test_shelter_reduces_exposure_only_in_its_own_region():
    """A shelter changes who is directly exposed; it does not drain water."""
    city = get_city()
    scenario = scenario_rain(0.9, 0.9)
    baseline = run_simulation(city, scenario, [], "baseline")
    target = max(baseline.regions, key=lambda r: r.affected_population)
    assert target.affected_population > 0
    mitigated = run_simulation(
        city, scenario, [intervention(InterventionType.SHELTER, target.region_id)], "mitigated"
    )
    changed = [
        r.region_id
        for r in mitigated.regions
        if r.affected_population
        < next(b.affected_population for b in baseline.regions if b.region_id == r.region_id)
    ]
    assert changed == [target.region_id]
    risks_unchanged = all(
        r.risk == next(b.risk for b in baseline.regions if b.region_id == r.region_id)
        for r in mitigated.regions
    )
    assert risks_unchanged


def test_totals_never_exceed_city_population():
    city = get_city()
    for intensity in (0.0, 0.5, 1.0):
        result = run_simulation(city, scenario_rain(intensity, intensity), [], "baseline")
        assert result.totals.affected_population <= sum(r.metrics.population for r in city.regions)


def test_zero_intensity_produces_no_damage():
    city = get_city()
    result = run_simulation(city, scenario_rain(0.0, 0.0), [], "baseline")
    assert result.totals.affected_population == 0
    assert result.totals.compromised_roads == 0
    assert all(r.risk_level is not None for r in result.regions)


def test_risk_level_thresholds():
    assert risk_level_of(0.9).value == "high"
    assert risk_level_of(0.62).value == "high"
    assert risk_level_of(0.45).value == "moderate"
    assert risk_level_of(0.05).value == "low"
