"""Local metric projection and elevation sampling.

The twin keeps two coordinate systems side by side:

* ``lat`` / ``lng`` — the real geodetic position, WGS84 (EPSG:4326).
* ``x`` / ``y`` — a local metric plane in metres, used by the renderer and
  by every distance calculation.

The local plane is an equirectangular approximation centred on the city, which
is accurate to well under a metre across the ~14 km urban extent of Franca and
avoids the precision loss that a single global projection introduces on small
areas. The projected CRS is declared in :class:`~app.schemas.CityModel.crs` so
a consumer never has to guess which plane the numbers belong to.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas import ElevationGrid

# WGS84 mean radii. Equirectangular needs a single metres-per-degree factor
# per axis; these are the standard values for a latitude/longitude pair.
METERS_PER_DEG_LAT = 111_132.92
METRES_PER_DEGREE_LONGITUDE_AT_EQUATOR = 111_412.84


def meters_per_degree_longitude(lat: float) -> float:
    """Metres in one degree of longitude at the given latitude."""
    return METRES_PER_DEGREE_LONGITUDE_AT_EQUATOR * math.cos(math.radians(lat))


class LocalProjection:
    """Equirectangular projection anchored at ``(origin_lat, origin_lng)``."""

    def __init__(self, origin_lat: float, origin_lng: float) -> None:
        self.origin_lat = origin_lat
        self.origin_lng = origin_lng
        self._meters_per_deg_lng = meters_per_degree_longitude(origin_lat)

    @property
    def meters_per_deg_lng(self) -> float:
        return self._meters_per_deg_lng

    def to_xy(self, lat: float, lng: float) -> tuple[float, float]:
        """Project geodetic coordinates to local metres.

        ``x`` grows east, ``y`` grows north, matching the renderer convention.
        """
        x = (lng - self.origin_lng) * self._meters_per_deg_lng
        y = (lat - self.origin_lat) * METERS_PER_DEG_LAT
        return x, y

    def to_latlng(self, x: float, y: float) -> tuple[float, float]:
        """Inverse of :meth:`to_xy`."""
        lat = self.origin_lat + y / METERS_PER_DEG_LAT
        lng = self.origin_lng + x / self._meters_per_deg_lng
        return lat, lng


def bilinear_sample(grid: list[list[float]], cols: int, rows: int, u: float, v: float) -> float:
    """Sample a row-major elevation grid at continuous grid coordinates.

    ``u`` indexes columns (west to east) and ``v`` indexes rows (north to
    south). Coordinates outside the grid clamp to the edge, which keeps
    callers on the city boundary from having to special-case themselves.
    """
    if cols <= 1 or rows <= 1:
        return grid[0][0] if grid and grid[0] else 0.0

    x = min(max(u, 0.0), cols - 1.0)
    y = min(max(v, 0.0), rows - 1.0)
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    x1, y1 = min(x0 + 1, cols - 1), min(y0 + 1, rows - 1)
    fx, fy = x - x0, y - y0

    top = grid[y0][x0] * (1 - fx) + grid[y0][x1] * fx
    bottom = grid[y1][x0] * (1 - fx) + grid[y1][x1] * fx
    return top * (1 - fy) + bottom * fy


class ElevationField:
    """Bilinear height lookup over a real DEM, addressed in local metres."""

    def __init__(
        self,
        grid: list[list[float]],
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
    ) -> None:
        self.grid = grid
        self.rows = len(grid)
        self.cols = len(grid[0]) if grid else 0
        self.min_x = min_x
        self.min_y = min_y
        self.max_x = max_x
        self.max_y = max_y
        self.span_x = max_x - min_x
        self.span_y = max_y - min_y

    @classmethod
    def from_model(cls, model: ElevationGrid) -> ElevationField:
        rows, cols = model.rows, model.cols
        values = model.values
        grid = [values[r * cols : (r + 1) * cols] for r in range(rows)]
        return cls(
            grid,
            model.min_x,
            model.min_y,
            model.max_x,
            model.max_y,
        )

    def elevation_at(self, x: float, y: float) -> float:
        """Height in metres at a local-plane position, in whole metres."""
        if self.rows == 0 or self.cols == 0 or self.span_x == 0 or self.span_y == 0:
            return 0.0
        u = (x - self.min_x) / self.span_x * (self.cols - 1)
        v = (self.max_y - y) / self.span_y * (self.rows - 1)
        return round(bilinear_sample(self.grid, self.cols, self.rows, u, v), 1)

    def slope_degrees(self, x: float, y: float, spacing: float = 60.0) -> float:
        """Ground slope from a finite difference across the DEM, in degrees.

        Computed on the DEM rather than declared, so the twin reports the real
        terrain gradient at a point instead of an assumed constant.
        """
        dx = self.elevation_at(x + spacing, y) - self.elevation_at(x - spacing, y)
        dy = self.elevation_at(x, y + spacing) - self.elevation_at(x, y - spacing)
        rise = math.hypot(dx, dy)
        return round(math.degrees(math.atan2(rise, 2 * spacing)), 2)


def point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test for a single closed ring."""
    inside = False
    count = len(ring)
    for i in range(count):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % count]
        if (y1 > y) != (y2 > y):
            t = (y - y1) / (y2 - y1) if y2 != y1 else 0.0
            if x < x1 + t * (x2 - x1):
                inside = not inside
    return inside


def polygon_centroid(ring: list[tuple[float, float]]) -> tuple[float, float]:
    """Area-weighted centroid of a closed ring, falling back to the mean."""
    count = len(ring)
    if count == 0:
        return 0.0, 0.0
    if count < 3:
        return sum(p[0] for p in ring) / count, sum(p[1] for p in ring) / count

    twice_area = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(count):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % count]
        cross = x1 * y2 - x2 * y1
        twice_area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross

    if abs(twice_area) < 1e-9:
        return sum(p[0] for p in ring) / count, sum(p[1] for p in ring) / count
    return cx / (3 * twice_area), cy / (3 * twice_area)


def polygon_area(ring: list[tuple[float, float]]) -> float:
    """Absolute area of a closed ring, in square metres."""
    count = len(ring)
    if count < 3:
        return 0.0
    twice_area = 0.0
    for i in range(count):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % count]
        twice_area += x1 * y2 - x2 * y1
    return abs(twice_area) / 2.0


def resample_polyline(
    points: list[tuple[float, float]], max_segment: float
) -> list[tuple[float, float]]:
    """Insert vertices so no segment is longer than ``max_segment``.

    Long straight OSM ways look identical to a coarse polyline once the map is
    tilted in 3D; subdividing keeps them hugging the terrain.
    """
    if len(points) < 2 or max_segment <= 0:
        return points
    out: list[tuple[float, float]] = [points[0]]
    for (x1, y1), (x2, y2) in zip(points, points[1:], strict=False):
        length = math.hypot(x2 - x1, y2 - y1)
        steps = int(math.ceil(length / max_segment)) if length > 0 else 0
        for step in range(1, steps + 1):
            t = step / steps
            out.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return out
