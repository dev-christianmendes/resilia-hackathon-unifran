"""Franca/SP as a real city model, assembled from versioned public-data fixtures.

Nothing here is synthesised. Every polygon, height and street name comes from a
fixture produced by ``scripts/fetch_franca_data.py``, whose provenance is
written to ``fixtures/franca/SOURCES.md``.

Two derived quantities are *computed* rather than observed, and are flagged in
the payload so nobody mistakes them for measurement:

* ``population`` is apportioned across the regions from the IBGE municipal
  total, weighted by real building count. ``population_is_estimated`` is true.
* ``vulnerability`` and the vegetation / imperviousness indices are indexes
  built from named real inputs (green polygons, road density, distance to
  watercourse, DEM). ``vulnerability_is_estimated`` and ``landuse_coverage``
  publish how much of each region those indexes actually rest on.

The regions are sub-basins: the urban extent is partitioned by which real
watercourse drains each point, which is the unit that matters for both flood
scenarios. Franca has no official IBGE neighbourhoods, so naming regions after
real watercourses is both truthful and hydrologically meaningful.
"""

from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, NamedTuple

from app.data.geo import (
    ElevationField,
    LocalProjection,
    point_in_ring,
    polygon_area,
    polygon_centroid,
    resample_polyline,
)
from app.schemas import (
    Building,
    CityModel,
    CoordinateReferenceSystem,
    DataSource,
    ElevationGrid,
    Facility,
    FacilityType,
    Point,
    Region,
    RegionMetrics,
    Road,
    Tree,
    VulnerabilityPoint,
    Waterway,
)

FIXTURES = Path(__file__).parent / "fixtures" / "franca"

# Must stay identical to scripts/fetch_franca_data.py: the fixtures are stored in
# WGS84 and projected against this origin.
ORIGIN_LAT = -20.5386
ORIGIN_LNG = -47.4008

# Partition grid for the sub-basins. Coarse on purpose: the boundaries follow
# drainage divides, not a raster, so the polygons are intentionally blocky.
PARTITION_COLS = 72
PARTITION_ROWS = 64

# Minimum watercourse length that earns its own sub-basin.
MIN_CHANNEL_LENGTH_M = 700.0
# Above this a channel is cut into reaches so one creek cannot swallow the city.
MAX_REACH_LENGTH_M = 2200.0
# Cells further than this from every channel are attached to the nearest one.
MAX_DRAINAGE_DISTANCE_M = 4500.0

BUCKET_SIZE_M = 500.0

# Storey height used when OSM has no building:levels. Stated as an assumption
# rather than pretended data.
ASSUMED_STOREY_M = 3.2
ASSUMED_FLOORS_WITHOUT_LEVELS = 2

GREEN_LANDUSE = {"forest", "grass", "meadow", "orchard", "vineyard", "village_green", "garden"}
GREEN_NATURAL = {"wood", "scrub", "grassland", "heath"}
GREEN_LEISURE = {"park", "nature_reserve"}
BUILT_LANDUSE = {
    "residential",
    "industrial",
    "commercial",
    "retail",
    "construction",
    "railway",
    "quarry",
    "village_green",
}

WaterwayKind = Literal["river", "stream", "canal", "ditch"]
RoadClass = Literal["arterial", "collector", "local"]
VulnerabilityKind = Literal["flood", "erosion", "heat", "infrastructure"]


WATERWAY_WIDTH_M: dict[str, tuple[WaterwayKind, float]] = {
    "river": ("river", 18.0),
    "stream": ("stream", 5.0),
    "canal": ("canal", 7.0),
    "ditch": ("ditch", 2.0),
}
ROAD_CLASS: dict[str, RoadClass] = {
    "trunk": "arterial",
    "primary": "arterial",
    "secondary": "collector",
    "tertiary": "local",
}

FACILITY_TYPES = {
    "hospital": (FacilityType.HOSPITAL, 420),
    "clinic": (FacilityType.HEALTH_CENTER, 180),
    "doctors": (FacilityType.HEALTH_CENTER, 120),
    "school": (FacilityType.SCHOOL, 600),
    "college": (FacilityType.SCHOOL, 900),
    "kindergarten": (FacilityType.SCHOOL, 200),
    "fire_station": (FacilityType.EMERGENCY_BASE, 180),
}

BUILDING_USES = {
    "house": "residential",
    "residential": "residential",
    "apartments": "residential",
    "dormitory": "residential",
    "commercial": "commercial",
    "retail": "commercial",
    "office": "commercial",
    "industrial": "industrial",
    "warehouse": "industrial",
    "factory": "industrial",
    "school": "public",
    "hospital": "public",
    "church": "public",
    "public": "public",
    "government": "public",
    "civic": "public",
}

# Buildings per km2 that counts as a fully built-up block, used both as the
# index ceiling and to invert the index when apportioning population.
BUILDING_DENSITY_REFERENCE = 220.0

# Road length per km2 that counts as fully built-up, used to turn the real
# street network into an imperviousness index.
ROAD_DENSITY_REFERENCE = 18_000.0


class Reach(NamedTuple):
    """One stretch of a real watercourse, used as a sub-basin seed."""

    waterway_id: str
    name: str
    kind: WaterwayKind
    order: int
    points: list[tuple[float, float]]


def _vulnerability_kind(raw: object) -> VulnerabilityKind:
    value = str(raw or "flood")
    if value == "erosion":
        return "erosion"
    if value == "heat":
        return "heat"
    if value == "infrastructure":
        return "infrastructure"
    return "flood"


def _load(name: str) -> Any:
    path = FIXTURES / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _to_point(projection: LocalProjection, x: float, y: float) -> Point:
    lat, lng = projection.to_latlng(x, y)
    return Point(x=round(x, 2), y=round(y, 2), lat=round(lat, 6), lng=round(lng, 6))


def _project_ring(
    projection: LocalProjection, ring: list[list[float]]
) -> list[tuple[float, float]]:
    return [projection.to_xy(lat, lng) for lat, lng in ring]


# --------------------------------------------------------------------------- #
# watercourses
# --------------------------------------------------------------------------- #


def _build_waterways(projection: LocalProjection) -> list[Waterway]:
    raw = _load("waterways") or []
    waterways: list[Waterway] = []
    for index, item in enumerate(raw):
        geometry = item.get("geometry") or []
        if len(geometry) < 2:
            continue
        projected = [projection.to_xy(lat, lng) for lat, lng in geometry]
        projected = resample_polyline(projected, 45.0)
        kind, width = WATERWAY_WIDTH_M.get(str(item.get("kind") or ""), ("stream", 5.0))
        waterways.append(
            Waterway(
                id=f"ww-{index:03d}",
                name=item.get("name"),
                kind=kind,
                path=[_to_point(projection, x, y) for x, y in projected],
                width_m=width,
                osm_id=str(item.get("osm_id")) if item.get("osm_id") else None,
            )
        )
    return waterways


def _build_reaches(waterways: list[Waterway], projection: LocalProjection) -> list[Reach]:
    """Cut the real channels into reaches long enough to seed a sub-basin."""
    reaches: list[Reach] = []
    for waterway in waterways:
        points = [(p.x, p.y) for p in waterway.path]
        if len(points) < 2:
            continue
        length = sum(
            math.hypot(x2 - x1, y2 - y1)
            for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False)
        )
        if length < MIN_CHANNEL_LENGTH_M:
            continue

        segments = max(1, int(math.ceil(length / MAX_REACH_LENGTH_M)))
        step = max(1, len(points) // segments)
        for s in range(segments):
            chunk = (
                points[s * step : (s + 1) * step + 1] if s < segments - 1 else points[s * step :]
            )
            if len(chunk) < 2:
                continue
            # Thin the seed points: the assignment only needs to know roughly
            # where the channel is, and the coarse grid keeps every channel.
            stride = max(1, len(chunk) // 60)
            thinned = chunk[::stride]
            if thinned[-1] != chunk[-1]:
                thinned.append(chunk[-1])
            label = waterway.name or "Curso d'água sem nome"
            reaches.append(
                Reach(
                    waterway_id=waterway.id,
                    name=label,
                    kind=waterway.kind,
                    order=len(reaches),
                    points=thinned,
                )
            )
    return reaches


def _bucket_points(reaches: list[Reach]) -> dict[tuple[int, int], list[tuple[int, float, float]]]:
    buckets: dict[tuple[int, int], list[tuple[int, float, float]]] = {}
    for reach in reaches:
        for x, y in reach.points:
            key = (int(math.floor(x / BUCKET_SIZE_M)), int(math.floor(y / BUCKET_SIZE_M)))
            buckets.setdefault(key, []).append((reach.order, x, y))
    return buckets


# --------------------------------------------------------------------------- #
# sub-basins
# --------------------------------------------------------------------------- #


class Partition(NamedTuple):
    labels: list[int]  # reach index per cell, -1 when unassigned
    cols: int
    rows: int
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    def cell_bounds(self, col: int, row: int) -> tuple[float, float, float, float]:
        w = (self.max_x - self.min_x) / self.cols
        h = (self.max_y - self.min_y) / self.rows
        x0 = self.min_x + col * w
        y0 = self.min_y + row * h
        return x0, y0, x0 + w, y0 + h


def _partition_by_drainage(
    reaches: list[Reach],
    elevation: ElevationField,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
) -> Partition:
    """Send every point to the channel it would actually drain into.

    Steeper ground is cheaper to flow across, so the distance to a channel is
    discounted by the local slope taken from the real DEM. That is what makes
    the resulting regions behave like catchments instead of a Voronoi sketch.
    """
    buckets = _bucket_points(reaches)
    labels: list[int] = []
    cell_w = (max_x - min_x) / PARTITION_COLS
    cell_h = (max_y - min_y) / PARTITION_ROWS

    for row in range(PARTITION_ROWS):
        for col in range(PARTITION_COLS):
            x = min_x + (col + 0.5) * cell_w
            y = max_y - (row + 0.5) * cell_h
            bx, by = int(math.floor(x / BUCKET_SIZE_M)), int(math.floor(y / BUCKET_SIZE_M))

            slope = elevation.slope_degrees(x, y)
            # 0.15 per degree: gentle ground drains cheaply, steep ground costs more.
            slope_factor = 1.0 + 0.15 * slope

            best_label = -1
            best_cost = float("inf")
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for reach_index, px, py in buckets.get((bx + dx, by + dy), ()):
                        distance = math.hypot(px - x, py - y)
                        if distance > MAX_DRAINAGE_DISTANCE_M:
                            continue
                        cost = distance * slope_factor
                        if cost < best_cost:
                            best_cost, best_label = cost, reach_index
            labels.append(best_label)

    return Partition(
        labels=labels,
        cols=PARTITION_COLS,
        rows=PARTITION_ROWS,
        min_x=min_x,
        min_y=min_y,
        max_x=max_x,
        max_y=max_y,
    )


def _trace_region_loops(
    partition: Partition, cells: set[tuple[int, int]]
) -> list[list[tuple[float, float]]]:
    """Closed boundary loops of a cell set, as local (x, y) pairs.

    Each cell emits its four edges only where the neighbour belongs to another
    region, giving a directed edge set with the interior on the left. Chaining
    those edges into every closed loop is what makes the outline exact.

    The graph is built on integer lattice corners, never on metres. Adjacent
    cells share a corner that floats disagree about, since
    ``min_x + c * w + w != min_x + (c + 1) * w``, and one mismatched key is
    enough to strand a whole outline as a two-point stub.
    """
    edges: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for col, row in cells:
        south = partition.rows - 1 - row
        corners = ((col, south), (col + 1, south), (col + 1, south + 1), (col, south + 1))
        # Neighbour across each edge. Row 0 is the northern row, so the south
        # edge of a cell faces row + 1 and the north edge faces row - 1.
        neighbours = ((col, row + 1), (col + 1, row), (col, row - 1), (col - 1, row))
        for i in range(4):
            ncol, nrow = neighbours[i]
            inside = (
                0 <= ncol < partition.cols
                and 0 <= nrow < partition.rows
                and partition.labels[nrow * partition.cols + ncol]
                == partition.labels[row * partition.cols + col]
            )
            if inside:
                continue
            edges.setdefault(corners[i], []).append(corners[(i + 1) % 4])

    width = (partition.max_x - partition.min_x) / partition.cols
    height = (partition.max_y - partition.min_y) / partition.rows

    def to_metres(corner: tuple[int, int]) -> tuple[float, float]:
        return (partition.min_x + corner[0] * width, partition.min_y + corner[1] * height)

    loops: list[list[tuple[float, float]]] = []
    limit = len(edges) * 4 + 8
    while edges:
        start = next(iter(edges))
        loop = [start]
        current = start
        heading = 0.0
        for _ in range(limit):
            options = edges.get(current)
            if not options:
                break
            # A vertex where two regions touch diagonally has two outgoing
            # edges. Taking the most clockwise one keeps the interior on the
            # left and stops the walk from stranding half the outline.
            if len(options) > 1:
                options.sort(key=lambda option: _turn_rank(current, option, heading))
            nxt = options.pop(0)
            if not options:
                del edges[current]
            if nxt == start:
                break
            heading = math.atan2(nxt[1] - current[1], nxt[0] - current[0])
            loop.append(nxt)
            current = nxt
        if len(loop) >= 3:
            loops.append(_drop_collinear([to_metres(corner) for corner in loop]))
    return loops


def _turn_rank(vertex: tuple[int, int], option: tuple[int, int], heading: float) -> float:
    """Sort key that prefers the sharpest clockwise turn from the heading."""
    angle = math.atan2(option[1] - vertex[1], option[0] - vertex[0])
    return -((heading - angle) % (2 * math.pi))


def _drop_collinear(ring: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Remove vertices that sit on a straight run, keeping the shape identical."""
    count = len(ring)
    kept: list[tuple[float, float]] = []
    for i in range(count):
        prev = ring[i - 1]
        current = ring[i]
        nxt = ring[(i + 1) % count]
        cross = (current[0] - prev[0]) * (nxt[1] - current[1]) - (current[1] - prev[1]) * (
            nxt[0] - current[0]
        )
        if cross:
            kept.append(current)
    return kept if len(kept) >= 3 else ring


def _region_polygon(
    partition: Partition, label: int
) -> tuple[list[tuple[float, float]], list[tuple[int, int]]]:
    """Outer ring of one region plus the cells it actually contains.

    A region can split into separate clusters where its channel leaves the
    mapped area, so only the cells inside the largest loop are kept. Without
    that the metrics would average over cells the outline does not cover.
    """
    cells = {
        (col, row)
        for row in range(partition.rows)
        for col in range(partition.cols)
        if partition.labels[row * partition.cols + col] == label
    }
    if not cells:
        return [], []
    loops = _trace_region_loops(partition, cells)
    if not loops:
        return [], []
    outer = max(loops, key=polygon_area)
    inside = []
    for col, row in cells:
        x0, y0, x1, y1 = partition.cell_bounds(col, partition.rows - 1 - row)
        if point_in_ring((x0 + x1) / 2, (y0 + y1) / 2, outer):
            inside.append((col, row))
    return outer, inside


def _road_density(partition: Partition, projection: LocalProjection) -> list[float]:
    """Metres of real street per cell, the index behind built-up density."""
    raw = _load("roads") or []
    per_cell = [0.0] * (partition.cols * partition.rows)
    for item in raw:
        geometry = item.get("geometry") or []
        if len(geometry) < 2:
            continue
        projected = [projection.to_xy(lat, lng) for lat, lng in geometry]
        for (x1, y1), (x2, y2) in zip(projected, projected[1:], strict=False):
            step = math.hypot(x2 - x1, y2 - y1)
            if step == 0:
                continue
            steps = max(1, int(step / 120.0))
            for s in range(steps + 1):
                t = s / steps
                x = x1 + (x2 - x1) * t
                y = y1 + (y2 - y1) * t
                col = int(
                    (x - partition.min_x) / (partition.max_x - partition.min_x) * partition.cols
                )
                row = int(
                    (partition.max_y - y) / (partition.max_y - partition.min_y) * partition.rows
                )
                if 0 <= col < partition.cols and 0 <= row < partition.rows:
                    per_cell[row * partition.cols + col] += step / (steps + 1)
    return per_cell


# --------------------------------------------------------------------------- #
# region metrics
# --------------------------------------------------------------------------- #


def _build_regions(
    projection: LocalProjection,
    elevation: ElevationField,
    grid: ElevationGrid,
    reaches: list[Reach],
    partition: Partition,
    road_density: list[float],
    waterways: list[Waterway],
    population_total: int,
) -> list[Region]:
    region_cells: dict[int, list[int]] = {}
    for index, label in enumerate(partition.labels):
        region_cells.setdefault(label, []).append(index)

    # Count real buildings per cell once, to apportion the IBGE total.
    buildings_raw = _load("buildings") or []
    buildings_per_cell = [0.0] * (partition.cols * partition.rows)
    for item in buildings_raw:
        geometry = item.get("geometry") or []
        if not geometry:
            continue
        projected = [projection.to_xy(lat, lng) for lat, lng in geometry]
        cx = sum(p[0] for p in projected) / len(projected)
        cy = sum(p[1] for p in projected) / len(projected)
        col = int((cx - partition.min_x) / (partition.max_x - partition.min_x) * partition.cols)
        row = int((partition.max_y - cy) / (partition.max_y - partition.min_y) * partition.rows)
        if 0 <= col < partition.cols and 0 <= row < partition.rows:
            buildings_per_cell[row * partition.cols + col] += 1.0

    channel_points = [(p.x, p.y) for waterway in waterways for p in waterway.path]
    vulnerability_raw = _load("vulnerability_points") or []

    # First pass: geometry and raw measurements, before landuse is attributed.
    shapes: list[dict[str, Any]] = []
    per_name: dict[str, int] = {}
    for label in sorted(region_cells):
        if label < 0 or len(region_cells[label]) < 4:
            continue
        reach = reaches[label]
        polygon, inside = _region_polygon(partition, label)
        if len(polygon) < 3 or len(inside) < 4:
            continue
        # A long creek is cut into several reaches, so repeat the real name and
        # number it: "Ribeirao dos Bagres (2)" stays traceable to the data.
        seen = per_name.get(reach.name, 0) + 1
        per_name[reach.name] = seen
        shapes.append(
            {
                "label": label,
                "name": reach.name if seen == 1 else f"{reach.name} ({seen})",
                "polygon": polygon,
                "cells": [row * partition.cols + col for col, row in inside],
                "area": max(1.0, polygon_area(polygon)),
                "buildings": sum(
                    buildings_per_cell[row * partition.cols + col] for col, row in inside
                ),
                "road_length": sum(road_density[row * partition.cols + col] for col, row in inside),
                "elevations": [],
                "slopes": [],
            }
        )

    for shape in shapes:
        for index in shape["cells"]:
            col = index % partition.cols
            row = index // partition.cols
            x0, y0, x1, y1 = partition.cell_bounds(col, partition.rows - 1 - row)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            shape["elevations"].append(elevation.elevation_at(cx, cy))
            shape["slopes"].append(elevation.slope_degrees(cx, cy))

    green_areas, built_areas = _landcover_areas(projection, [s["polygon"] for s in shapes])

    regions: list[Region] = []
    densities: list[float] = []
    for index, shape in enumerate(shapes):
        polygon = shape["polygon"]
        centroid_x, centroid_y = polygon_centroid(polygon)
        area = shape["area"]
        elevations = shape["elevations"]
        slopes = shape["slopes"]

        nearest_channel = min(
            (math.hypot(cx - centroid_x, cy - centroid_y) for cx, cy in channel_points),
            default=9999.0,
        )

        vegetation = min(1.0, green_areas[index] / area)
        built_share = min(1.0, built_areas[index] / area)
        # How much of the sub-basin OSM landuse actually covers, so the green
        # and built indices above can be read as partial rather than complete.
        landuse_coverage = min(1.0, (green_areas[index] + built_areas[index]) / area)
        # Real street network density stands in for sealed surface, because
        # OSM building coverage in Franca is far too sparse to measure it.
        density_index = min(
            1.0, shape["road_length"] / max(1.0, area / 1_000_000) / ROAD_DENSITY_REFERENCE
        )
        impermeability = round(max(built_share, density_index), 3)

        mean_elevation = sum(elevations) / len(elevations)
        relief = max(elevations) - min(elevations)
        mean_slope = sum(slopes) / len(slopes)

        documented = [
            item
            for item in vulnerability_raw
            if point_in_ring(
                *projection.to_xy(float(item["location"]["lat"]), float(item["location"]["lng"])),
                polygon,
            )
        ]
        documented_severity = max((item["severity"] for item in documented), default=0.0)

        proximity = max(0.0, 1.0 - nearest_channel / 1200.0)
        slope_drainage = max(0.0, 1.0 - mean_slope / 14.0)
        low_relief = max(0.0, 1.0 - relief / 60.0)
        flood_risk = min(
            1.0,
            0.40 * proximity + 0.20 * slope_drainage + 0.15 * low_relief + 0.25 * impermeability,
        )
        if documented_severity:
            flood_risk = min(1.0, flood_risk + 0.20 * documented_severity)

        # Social weight stands in for IBGE sector income, which is not available
        # at this granularity here; denser built fabric is the honest proxy.
        density_per_km2 = shape["buildings"] / (area / 1_000_000)
        densities.append(density_per_km2)
        vulnerability = min(1.0, 0.5 * impermeability + 0.5 * min(1.0, density_per_km2 / 60.0))
        heat_exposure = min(
            1.0,
            max(0.0, 0.55 * (1.0 - vegetation) + 0.30 * impermeability + 0.15 * proximity),
        )
        regions.append(
            Region(
                id=f"region-{shape['label']:03d}",
                name=shape["name"],
                polygon=[_to_point(projection, x, y) for x, y in polygon],
                centroid=_to_point(projection, centroid_x, centroid_y),
                metrics=RegionMetrics(
                    population=0,
                    population_is_estimated=True,
                    population_density=0.0,
                    vegetation_index=round(vegetation, 3),
                    impermeability=impermeability,
                    flood_risk=round(flood_risk, 3),
                    heat_exposure=round(heat_exposure, 3),
                    elevation_m=round(mean_elevation, 1),
                    elevation_min_m=round(min(elevations), 1),
                    elevation_max_m=round(max(elevations), 1),
                    slope_deg=round(mean_slope, 2),
                    waterway_proximity_m=round(nearest_channel, 1),
                    building_footprint_ratio=round(
                        min(1.0, density_per_km2 / BUILDING_DENSITY_REFERENCE), 3
                    ),
                    landuse_coverage=round(landuse_coverage, 3),
                    vulnerability=round(vulnerability, 3),
                    vulnerability_is_estimated=True,
                    historical_events=len(documented),
                ),
            )
        )

    _apportion_population(regions, densities, population_total)
    return regions


def _apportion_population(
    regions: list[Region], densities: list[float], population_total: int
) -> None:
    """Split the IBGE municipal total by measured building density.

    Franca has no official neighbourhood divisions, so the twin cannot read a
    population per region. Weighting by real building count per km2 keeps the
    city total equal to the IBGE figure while still following where people
    actually live. The weight is the raw density, not the clamped index, since
    the clamp would flatten every dense sub-basin to the same weight.
    """
    weights = [max(0.05, density) for density in densities]
    total_weight = sum(weights)
    if total_weight <= 0 or population_total <= 0:
        return
    for region, weight in zip(regions, weights, strict=False):
        population = int(round(population_total * weight / total_weight))
        region.metrics.population = population
        xs = [p.x for p in region.polygon]
        ys = [p.y for p in region.polygon]
        area_km2 = max(0.001, polygon_area(list(zip(xs, ys, strict=False))) / 1_000_000)
        region.metrics.population_density = round(population / area_km2, 1)


# --------------------------------------------------------------------------- #
# roads, buildings, facilities, trees
# --------------------------------------------------------------------------- #


def _build_roads(projection: LocalProjection, regions: list[Region]) -> list[Road]:
    raw = _load("roads") or []
    roads: list[Road] = []
    for index, item in enumerate(raw):
        geometry = item.get("geometry") or []
        if len(geometry) < 2:
            continue
        projected = resample_polyline([projection.to_xy(lat, lng) for lat, lng in geometry], 60.0)
        highway = str(item.get("highway") or "tertiary")
        roads.append(
            Road(
                id=f"road-{index:04d}",
                name=item.get("name") or "Via sem nome",
                region_id="",
                path=[_to_point(projection, x, y) for x, y in projected],
                class_=ROAD_CLASS.get(highway, "local"),
                critical=highway in {"trunk", "primary"},
                osm_id=str(item.get("osm_id")) if item.get("osm_id") else None,
            )
        )

    # A road is exposed in every region it crosses, so it counts once per region.
    counts: dict[str, int] = {region.id: 0 for region in regions}
    for road in roads:
        owners: dict[str, int] = {}
        for point in road.path:
            region = _region_at(regions, point.x, point.y)
            if region:
                owners[region.id] = owners.get(region.id, 0) + 1
        if owners:
            road.region_id = max(owners, key=lambda k: owners[k])
            for region_id in owners:
                counts[region_id] += 1
    for region in regions:
        region.road_count = counts.get(region.id, 0)
    return roads


def _landcover_areas(
    projection: LocalProjection,
    polygons: list[list[tuple[float, float]]],
) -> tuple[list[float], list[float]]:
    """Green and built square metres per region, from real OSM landuse.

    Sampling cell centres fails here: a typical Franca park is about 50 m
    across while a sub-basin cell is about 185 m, so no centre ever lands
    inside one and every green index comes out zero. Each polygon's real area
    is therefore attributed to the sub-basin holding its centroid, which keeps
    the areas exact and only approximates the boundary assignment.
    """
    green_area = [0.0] * len(polygons)
    built_area = [0.0] * len(polygons)

    for item in _load("landuse") or []:
        tag = item.get("tag")
        value = item.get("value")
        if tag == "landuse" and value in GREEN_LANDUSE:
            target = green_area
        elif tag == "landuse" and value in BUILT_LANDUSE and value not in GREEN_LANDUSE:
            target = built_area
        elif (tag == "natural" and value in GREEN_NATURAL) or (
            tag == "leisure" and value in GREEN_LEISURE
        ):
            target = green_area
        else:
            continue

        geometry = item.get("geometry") or []
        if len(geometry) < 3:
            continue
        ring = _project_ring(projection, geometry)
        if len(ring) < 3:
            continue
        area = polygon_area(ring)
        if area <= 0:
            continue
        cx, cy = polygon_centroid(ring)
        for index, region_ring in enumerate(polygons):
            if not point_in_ring(cx, cy, region_ring):
                continue
            target[index] += area
            break

    return green_area, built_area


def _region_at(regions: list[Region], x: float, y: float) -> Region | None:
    """Region owning a point, tested against the real polygon.

    A bounding-box-only test would mis-assign points, because sub-basin
    polygons are staircase shapes whose boxes overlap heavily.
    """
    for region in regions:
        ring = [(p.x, p.y) for p in region.polygon]
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        if not (min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys)):
            continue
        if point_in_ring(x, y, ring):
            return region
    return None


def _build_buildings(projection: LocalProjection, regions: list[Region]) -> list[Building]:
    raw = _load("buildings") or []
    buildings: list[Building] = []
    for index, item in enumerate(raw):
        geometry = item.get("geometry") or []
        if len(geometry) < 4:
            continue
        projected = [projection.to_xy(lat, lng) for lat, lng in geometry]
        xs = [p[0] for p in projected]
        ys = [p[1] for p in projected]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        region = _region_at(regions, cx, cy)

        levels_raw = item.get("levels")
        try:
            floors = max(1, int(float(levels_raw))) if levels_raw else ASSUMED_FLOORS_WITHOUT_LEVELS
        except (TypeError, ValueError):
            floors = ASSUMED_FLOORS_WITHOUT_LEVELS
        height = round(floors * ASSUMED_STOREY_M, 2)

        buildings.append(
            Building(
                id=f"bld-{index:04d}",
                region_id=region.id if region else "",
                location=_to_point(projection, cx, cy),
                width=round(max(8.0, max(xs) - min(xs)), 1),
                depth=round(max(8.0, max(ys) - min(ys)), 1),
                height=height,
                floors=floors,
                use=BUILDING_USES.get(item.get("use") or "", "residential"),  # type: ignore[arg-type]
                osm_id=str(item.get("osm_id")) if item.get("osm_id") else None,
            )
        )
    return buildings


def _nearest_region(regions: list[Region], x: float, y: float) -> Region | None:
    """Closest region by centroid, for points the partition left unassigned.

    Facilities sitting just outside a traced outline would otherwise vanish
    from the model, which silently under-reports service capacity.
    """
    best: Region | None = None
    best_distance = float("inf")
    for region in regions:
        distance = math.hypot(region.centroid.x - x, region.centroid.y - y)
        if distance < best_distance:
            best_distance = distance
            best = region
    return best


def _build_facilities(projection: LocalProjection, regions: list[Region]) -> list[Facility]:
    raw = _load("facilities") or []
    facilities: list[Facility] = []
    for index, item in enumerate(raw):
        amenity = item.get("amenity")
        if not amenity or amenity not in FACILITY_TYPES:
            continue
        if item.get("lat") is not None and item.get("lon") is not None:
            lat, lng = float(item["lat"]), float(item["lon"])
        else:
            geometry = item.get("geometry") or []
            if not geometry:
                continue
            lat = sum(p[0] for p in geometry) / len(geometry)
            lng = sum(p[1] for p in geometry) / len(geometry)
        x, y = projection.to_xy(lat, lng)
        region = _region_at(regions, x, y) or _nearest_region(regions, x, y)
        facility_type, capacity = FACILITY_TYPES[amenity]
        facilities.append(
            Facility(
                id=f"fac-{index:04d}",
                name=item.get("name") or f"Equipamento {amenity.replace('_', ' ')}",
                type=facility_type,
                region_id=region.id if region else "",
                location=_to_point(projection, x, y),
                capacity=capacity,
                critical=amenity in {"hospital", "fire_station"},
            )
        )
    for region in regions:
        region.facilities = [f for f in facilities if f.region_id == region.id]
    return facilities


def _build_trees(projection: LocalProjection, regions: list[Region]) -> list[Tree]:
    """Seed trees on real green landcover, deterministically.

    Position is taken from the real polygons; only the jitter inside a polygon
    is a seeded random draw so the same city comes back on every run.
    """
    rng = random.Random(20240517)
    raw = _load("landuse") or []
    trees: list[Tree] = []
    index = 0
    for item in raw:
        tag, value = item.get("tag"), item.get("value")
        is_green = (
            (tag == "landuse" and value in GREEN_LANDUSE)
            or (tag == "natural" and value in GREEN_NATURAL)
            or (tag == "leisure" and value in GREEN_LEISURE)
        )
        if not is_green:
            continue
        geometry = item.get("geometry") or []
        if len(geometry) < 4:
            continue
        projected = [projection.to_xy(lat, lng) for lat, lng in geometry]
        ring = [(x, y) for x, y in projected]
        min_x, max_x = min(p[0] for p in ring), max(p[0] for p in ring)
        min_y, max_y = min(p[1] for p in ring), max(p[1] for p in ring)
        count = min(14, 2 + len(geometry) // 12)
        for _ in range(count):
            x = rng.uniform(min_x, max_x)
            y = rng.uniform(min_y, max_y)
            if not point_in_ring(x, y, ring):
                continue
            region = _region_at(regions, x, y)
            trees.append(
                Tree(
                    id=f"tree-{index:04d}",
                    region_id=region.id if region else "",
                    location=_to_point(projection, x, y),
                    radius=round(rng.uniform(2.2, 4.5), 2),
                    height=round(rng.uniform(5.0, 11.0), 2),
                )
            )
            index += 1
    return trees


def _build_vulnerability_points(
    projection: LocalProjection, regions: list[Region]
) -> list[VulnerabilityPoint]:
    raw = _load("vulnerability_points") or []
    points: list[VulnerabilityPoint] = []
    for item in raw:
        lat = float(item["location"]["lat"])
        lng = float(item["location"]["lng"])
        x, y = projection.to_xy(lat, lng)
        points.append(
            VulnerabilityPoint(
                id=item["id"],
                name=item["name"],
                kind=_vulnerability_kind(item.get("kind")),
                location=_to_point(projection, x, y),
                severity=float(item.get("severity", 0.5)),
                street=item.get("street"),
                waterway=item.get("waterway"),
                evidence=item.get("evidence", ""),
                source=item.get("source", ""),
                reference=item.get("reference"),
            )
        )
    return points


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #


def _sources(retrieved: str) -> list[DataSource]:
    return [
        DataSource(
            layer="boundary",
            provider="IBGE",
            dataset="API de Malhas, municipio 3516200",
            reference="https://servicodados.ibge.gov.br/api/v3/malhas/municipios/3516200",
            licence="CC-BY-SA 4.0",
            retrieved_at=retrieved,
            detail="Limite municipal de Franca/SP",
        ),
        DataSource(
            layer="waterways",
            provider="OpenStreetMap",
            dataset="waterway=stream|river|canal|ditch",
            reference="https://www.openstreetmap.org",
            licence="ODbL",
            retrieved_at=retrieved,
        ),
        DataSource(
            layer="roads",
            provider="OpenStreetMap",
            dataset="highway=primary|secondary|trunk|tertiary",
            reference="https://www.openstreetmap.org",
            licence="ODbL",
            retrieved_at=retrieved,
        ),
        DataSource(
            layer="buildings",
            provider="OpenStreetMap",
            dataset="building",
            reference="https://www.openstreetmap.org",
            licence="ODbL",
            retrieved_at=retrieved,
        ),
        DataSource(
            layer="landuse",
            provider="OpenStreetMap",
            dataset="landuse|natural|leisure",
            reference="https://www.openstreetmap.org",
            licence="ODbL",
            retrieved_at=retrieved,
        ),
        DataSource(
            layer="facilities",
            provider="OpenStreetMap",
            dataset="amenity=hospital|clinic|doctors|school|fire_station",
            reference="https://www.openstreetmap.org",
            licence="ODbL",
            retrieved_at=retrieved,
        ),
        DataSource(
            layer="elevation",
            provider="AWS Terrain Tiles",
            dataset="Terrarium sobre SRTM",
            reference="https://registry.opendata.aws/terrain-tiles/",
            licence="CC-BY",
            retrieved_at=retrieved,
            detail="SRTM 30 m, amostrado em grade regular",
        ),
        DataSource(
            layer="vulnerability_points",
            provider="Prefeitura de Franca",
            dataset="Plano de Contingencia de Defesa Civil",
            licence="Documento publico municipal",
            retrieved_at=retrieved,
            detail="Pontos de alagamento citados no plano, coordenadas vias de OSM",
        ),
    ]


@lru_cache(maxsize=1)
def get_franca_city() -> CityModel:
    metadata = _load("metadata") or {}
    projection = LocalProjection(ORIGIN_LAT, ORIGIN_LNG)

    elevation_payload = _load("elevation") or {}
    values = elevation_payload.get("values") or []
    if not values:
        raise RuntimeError("fixture de elevacao ausente: rode scripts/fetch_franca_data")
    cols = int(elevation_payload["cols"])
    rows = int(elevation_payload["rows"])
    grid = ElevationGrid(
        rows=rows,
        cols=cols,
        values=[float(v) for v in values],
        min_x=float(elevation_payload["min_x"]),
        min_y=float(elevation_payload["min_y"]),
        max_x=float(elevation_payload["max_x"]),
        max_y=float(elevation_payload["max_y"]),
        resolution_m=float(elevation_payload.get("resolution_m", 0.0)),
        source=elevation_payload.get("source", "AWS Terrain Tiles"),
    )
    elevation = ElevationField.from_model(grid)

    waterways = _build_waterways(projection)
    reaches = _build_reaches(waterways, projection)
    if not reaches:
        raise RuntimeError("nenhum curso d'agua apto para sub-bacias no fixture")

    partition = _partition_by_drainage(
        reaches,
        elevation,
        grid.min_x,
        grid.min_y,
        grid.max_x,
        grid.max_y,
    )
    road_density = _road_density(partition, projection)

    regions = _build_regions(
        projection,
        elevation,
        grid,
        reaches,
        partition,
        road_density,
        waterways,
        int(metadata.get("population_estimate_2025", 0)),
    )
    if not regions:
        raise RuntimeError("particao por drenagem nao produziu nenhuma regiao")

    roads = _build_roads(projection, regions)
    buildings = _build_buildings(projection, regions)
    # Facilities are exposed both at city level and inside each region, so the
    # panels can filter by region without a second lookup and nothing is lost.
    facilities = _build_facilities(projection, regions)
    trees = _build_trees(projection, regions)
    vulnerability = _build_vulnerability_points(projection, regions)

    for region in regions:
        if not region.facilities:
            region.facilities = []

    return CityModel(
        id="franca-sp",
        name="Franca/SP",
        ibge_code=metadata.get("ibge_code"),
        crs=CoordinateReferenceSystem(
            name="Franca/SP local (equirretangular ancorada na origem da cidade)",
            projection="EPSG:4326 -> plano local em metros",
            origin_lat=ORIGIN_LAT,
            origin_lng=ORIGIN_LNG,
        ),
        bounds={
            "min_x": grid.min_x,
            "min_y": grid.min_y,
            "max_x": grid.max_x,
            "max_y": grid.max_y,
        },
        regions=regions,
        roads=roads,
        waterways=waterways,
        facilities=facilities,
        buildings=buildings,
        trees=trees,
        elevation=grid,
        vulnerability_points=vulnerability,
        sources=_sources("versionado em app/data/fixtures/franca/SOURCES.md"),
        reference_scale_m=1000.0,
    )
