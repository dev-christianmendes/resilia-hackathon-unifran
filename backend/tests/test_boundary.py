"""The municipal outline, and the gap between it and the modelled window.

The IBGE outline is the whole territory while every derived layer is clipped to
URBAN_BBOX. Both facts have to stay visible, because reading the sub-basins as
the whole municipality is the most tempting wrong reading of this dataset.
"""

from app.data import get_city
from app.data.geo import point_in_ring, polygon_area

# IBGE Malhas metadata for município 3516200, area in km².
IBGE_MUNICIPAL_AREA_KM2 = 605.679

# Share of the municipality the DEM window covers. Measured by
# scripts/fetch_franca_data.py::modelled_coverage_pct, published in SOURCES.md.
MODELLED_COVERAGE_PCT = 32.4

# Tolerance for the local equirectangular plane against the official figure.
AREA_TOLERANCE_KM2 = 8.0


def test_boundary_is_published():
    city = get_city()
    assert len(city.boundary) > 100
    assert all(point.lat is not None and point.lng is not None for point in city.boundary)


def test_boundary_ring_is_not_closed_duplicated():
    """Region polygons are open rings; the boundary must match that convention.

    GeoJSON repeats the first vertex to close the ring. Publishing it verbatim
    would hand the consumer a zero-length segment to draw.
    """
    city = get_city()
    first, last = city.boundary[0], city.boundary[-1]
    assert (first.x, first.y) != (last.x, last.y)


def test_boundary_area_matches_ibge():
    """The projection must not distort the municipal area.

    A 0.3% agreement with the official figure is what an equirectangular plane
    anchored at the city centre should produce; a larger gap would mean the
    ring was read in the wrong axis order.
    """
    city = get_city()
    area_km2 = polygon_area([(p.x, p.y) for p in city.boundary]) / 1e6
    assert abs(area_km2 - IBGE_MUNICIPAL_AREA_KM2) < AREA_TOLERANCE_KM2


def test_regions_outside_the_boundary_are_flagged():
    """No region may silently claim to be part of Franca.

    The DEM window is a rectangle and the municipality is not, so a few
    border sub-basins extrapolate the territory. They are flagged rather than
    clipped, because a catchment is a hydrological unit.
    """
    city = get_city()
    ring = [(p.x, p.y) for p in city.boundary]

    for region in city.regions:
        probes = [(region.centroid.x, region.centroid.y)]
        probes += [(point.x, point.y) for point in region.polygon]
        truly_inside = all(point_in_ring(x, y, ring) for x, y in probes)
        assert region.within_municipality is truly_inside


def test_the_flagged_area_is_negligible():
    """Pins the size of the leak so it cannot grow unnoticed.

    Widen URBAN_BBOX far enough and this starts to matter; at 0.08% of the
    population it is a labelling issue, not a data error.
    """
    city = get_city()
    flagged = [r for r in city.regions if not r.within_municipality]
    assert flagged, "expected the rectangular window to overshoot somewhere"

    flagged_population = sum(r.metrics.population for r in flagged)
    total_population = sum(r.metrics.population for r in city.regions)
    assert flagged_population / total_population < 0.01


def test_modelled_window_is_a_minority_of_the_municipality():
    """Pins the asymmetry so it cannot be quietly widened or hidden.

    If this ever fails because coverage genuinely grew, the population
    apportionment and the docs in SOURCES.md both need revisiting: the model
    currently spreads the full municipal population inside this window.
    """
    city = get_city()
    window = city.bounds
    window_area_m2 = (window["max_x"] - window["min_x"]) * (window["max_y"] - window["min_y"])
    municipality_area_m2 = polygon_area([(p.x, p.y) for p in city.boundary])
    coverage_pct = window_area_m2 / municipality_area_m2 * 100.0
    assert abs(coverage_pct - MODELLED_COVERAGE_PCT) < 3.0
    assert coverage_pct < 50.0


def test_boundary_reaches_beyond_the_dem_grid():
    """The outline must be larger than the window, or the test above is moot."""
    city = get_city()
    xs = [p.x for p in city.boundary]
    ys = [p.y for p in city.boundary]
    window = city.bounds
    assert max(xs) > window["max_x"]
    assert min(xs) < window["min_x"]
    assert max(ys) > window["max_y"]
    assert min(ys) < window["min_y"]
