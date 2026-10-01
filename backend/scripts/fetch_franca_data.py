#!/usr/bin/env python3
"""One-off ingestion of real Franca/SP data into versioned fixtures.

Run manually; the API never calls this and never touches the network.

    python -m scripts.fetch_franca_data            # fill missing layers
    python -m scripts.fetch_franca_data --force    # refetch everything

Every layer is cached as raw JSON under ``backend/.cache/franca`` so a rerun is
cheap and a failure in one layer never discards the others. Nothing here is
invented: a layer that cannot be fetched is reported and left out, and the
builder in ``app/data/franca.py`` only publishes what actually arrived.

Sources
    boundary / demography : IBGE
    waterways, roads, buildings, place names : OpenStreetMap (ODbL)
    elevation : AWS Terrain Tiles, Terrarium encoding over SRTM
    vulnerability points : Plano de Contingencia de Defesa Civil de Franca
"""

from __future__ import annotations

import gzip
import json
import math
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
CACHE = BACKEND / ".cache" / "franca"
FIXTURES = BACKEND / "app" / "data" / "fixtures" / "franca"

USER_AGENT = "city-twin-franca/1.0 (RESILIA hackatown; one-off public-data import)"

IBGE_MALHAS = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{code}"
IBGE_CITY = "https://servicodados.ibge.gov.br/cidades-e-estados/sp/franca.html"
AWS_TERRARIUM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
PLAN_DEFESA_CIVIL = (
    "https://www3.franca.sp.gov.br/pdf/"
    "20260316140411_69b8380b3cf8d_PLANO_DE_CONTING_NCIA_DE_DEFESA_CIVIL_-_PER_ODOS_CHUVOSOS_.pdf"
)

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Franca/SP urbanised extent (IBGE: 82.34 km2) with a margin, so the twin shows
# the built-up area rather than the 605.679 km2 of the whole municipality.
URBAN_BBOX = {"min_lat": -20.608, "max_lat": -20.469, "min_lng": -47.465, "max_lng": -47.337}
ORIGIN_LAT = -20.5386
ORIGIN_LNG = -47.4008

GRID_COLS = 288
GRID_ROWS = 256
DEM_ZOOM = 14

IBGE_CODE = "3516200"

# Documented in the municipal civil defence plan. Every entry needs an OSM way
# whose name can be found, otherwise the point is reported as unresolved and
# left out rather than being placed at an invented coordinate.
DOCUMENTED_FLOOD_POINTS: list[dict[str, Any]] = [
    {
        "id": "vp-helio-palermo",
        "name": "Av. Doutor Helio Palermo / Corrego dos Bagres",
        "street": "Avenida Doutor Hélio Palermo",
        "waterway": "Córrego dos Bagres",
        "severity": 0.9,
        "evidence": (
            "Alagamento recorrente na Av. Hélio Palermo, no Córrego dos Bagres, "
            "entre o Pronto Socorro Infantil e a junção com o Córrego das Maritacas "
            "(trecho Major Nicácio / Av. Evangelista Lima)."
        ),
    },
    {
        "id": "vp-antonio-barbosa",
        "name": "Av. Doutor Antonio Barbosa Filho (apos Ponte General Telles)",
        "street": "Avenida Doutor Antônio Barbosa Filho",
        "waterway": None,
        "severity": 0.78,
        "evidence": (
            "Ponto de alagamento na Av. Antônio Barbosa Filho após a Ponte General Telles."
        ),
    },
    {
        "id": "vp-ismael-alonso",
        "name": "Av. Dr. Ismael Alonso y Alonso / viaduto Major Nicacio (Cubatao)",
        "street": "Avenida Doutor Ismael Alonso Y Alonso",
        "waterway": "Córrego Cubatão",
        "severity": 0.85,
        "evidence": (
            "Alagamento na Av. Dr. Ismael Alonso y Alonso, junto ao viaduto "
            "Major Nicácio sobre o Córrego Cubatão e à rotatória Chevrolet."
        ),
    },
    {
        "id": "vp-sao-vicente",
        "name": "Av. Sao Vicente (antes da Lagoa do Castelinho)",
        "street": "Avenida São Vicente",
        "waterway": None,
        "severity": 0.8,
        "evidence": ("Alagamento na Av. São Vicente antes da Lagoa do Castelinho."),
    },
    {
        "id": "vp-adhemar-de-barros",
        "name": "Av. Adhemar Pereira de Barros (drenagem deficiente)",
        "street": "Avenida Adhemar Pereira de Barros",
        "waterway": None,
        "severity": 0.72,
        "evidence": ("Drenagem deficiente e formacao de pocoes na Av. Adhemar de Barros."),
    },
]

# Verified against the IBGE city panel. Kept as constants because the aggregate
# API that would serve them per municipality is not reachable from this host;
# the source URL travels with them so they can be re-fetched and re-checked.
IBGE_DEMOGRAPHY = {
    "ibge_code": IBGE_CODE,
    "municipality": "Franca",
    "uf": "SP",
    "region": "Sudeste",
    "biome": "Cerrado",
    "area_km2": 605.679,
    "urbanised_area_km2": 82.34,
    "population_2022": 352536,
    "population_estimate_2025": 365494,
    "population_density_hab_km2": 582.05,
    "reference": IBGE_CITY,
}


# --------------------------------------------------------------------------- #
# transport
# --------------------------------------------------------------------------- #


def _get(url: str, timeout: int = 120, binary: bool = False) -> Any:
    """GET that transparently copes with servers that ignore Accept-Encoding.

    The IBGE malha service answers gzip even when no encoding is requested,
    which would otherwise blow up the utf-8 decode.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        payload = response.read()
        if (
            response.headers.get("Content-Encoding", "").lower() == "gzip"
            or payload[:2] == b"\x1f\x8b"
        ):
            payload = gzip.decompress(payload)
        return payload if binary else payload.decode("utf-8")


def overpass(query: str, *, attempts: int = 5, timeout: int = 180) -> dict[str, Any]:
    """Run an Overpass QL query, rotating mirrors and backing off on failure."""
    last: Exception | None = None
    for attempt in range(attempts):
        endpoint = OVERPASS_ENDPOINTS[attempt % len(OVERPASS_ENDPOINTS)]
        try:
            body = urllib.parse.urlencode({"data": query}).encode()
            request = urllib.request.Request(
                endpoint, data=body, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = exc
            wait = min(20, 3 * (attempt + 1))
            print(f"    overpass {endpoint.split('/')[2]} falhou ({exc}); {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"Overpass indisponivel apos {attempts} tentativas: {last}")


# --------------------------------------------------------------------------- #
# minimal PNG reader (Terrarium tiles are 8-bit, non-interlaced)
# --------------------------------------------------------------------------- #


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def decode_png_rgb(data: bytes) -> tuple[int, int, bytes]:
    """Decode an 8-bit non-interlaced PNG into ``(width, height, rgb_bytes)``."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("assinatura PNG invalida")

    offset = 8
    width = height = 0
    bit_depth = colour_type = interlace = 0
    idat = bytearray()

    while offset < len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        offset += 12 + length

        if kind == b"IHDR":
            width, height, bit_depth, colour_type, _, _, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
        elif kind == b"IDAT":
            idat += payload
        elif kind == b"IEND":
            break

    if bit_depth != 8:
        raise ValueError(f"bit depth {bit_depth} nao suportado")
    if interlace != 0:
        raise ValueError("PNG entrelacado nao suportado")
    channels = {0: 1, 2: 3, 4: 2, 6: 4}.get(colour_type)
    if channels is None:
        raise ValueError(f"color type {colour_type} nao suportado")

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    out = bytearray(stride * height)
    previous = bytearray(stride)

    pos = 0
    for row in range(height):
        filter_type = raw[pos]
        pos += 1
        line = bytearray(raw[pos : pos + stride])
        pos += stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up_left = previous[i - channels] if i >= channels else 0
                line[i] = (line[i] + _paeth(left, previous[i], up_left)) & 0xFF
        elif filter_type != 0:
            raise ValueError(f"filtro PNG {filter_type} desconhecido")
        out[row * stride : (row + 1) * stride] = line
        previous = line

    if channels >= 3:
        rgb = bytearray(width * height * 3)
        for i in range(width * height):
            rgb[i * 3 : i * 3 + 3] = out[i * channels : i * channels + 3]
    else:  # grayscale -> replicate
        rgb = bytearray(width * height * 3)
        for i in range(width * height):
            value = out[i * channels]
            rgb[i * 3 : i * 3 + 3] = bytes((value, value, value))

    return width, height, bytes(rgb)


def terrarium_elevation(rgb: bytes) -> list[float]:
    """Terrarium decoding: ``(R * 256 + G + B / 256) - 32768``."""
    out: list[float] = []
    for i in range(0, len(rgb), 3):
        out.append(rgb[i] * 256 + rgb[i + 1] + rgb[i + 2] / 256 - 32768)
    return out


# --------------------------------------------------------------------------- #
# geometry helpers
# --------------------------------------------------------------------------- #


def meters_per_degree_longitude(lat: float) -> float:
    return 111412.84 * math.cos(math.radians(lat))


def project(lat: float, lng: float) -> tuple[float, float]:
    x = (lng - ORIGIN_LNG) * meters_per_degree_longitude(ORIGIN_LAT)
    y = (lat - ORIGIN_LAT) * 111132.92
    return round(x, 2), round(y, 2)


def in_bbox(lat: float, lng: float, bbox: dict[str, float] | None = None) -> bool:
    box = bbox or URBAN_BBOX
    return box["min_lat"] <= lat <= box["max_lat"] and box["min_lng"] <= lng <= box["max_lng"]


def ring_area_m2(ring: list[list[float]]) -> float:
    """Shoelace area of a closed lon/lat ring, projected locally first."""
    projected = [project(lat, lng) for lat, lng in ring]
    total = 0.0
    count = len(projected)
    for i in range(count):
        x1, y1 = projected[i]
        x2, y2 = projected[(i + 1) % count]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def modelled_coverage_pct(ring: list[list[float]]) -> float:
    """Share of the municipality that falls inside the modelled DEM window.

    The DEM and every derived layer are clipped to URBAN_BBOX, while the IBGE
    municipal outline is the whole territory. Publishing the ratio turns a
    silent mismatch into a stated limitation.
    """
    municipality = ring_area_m2(ring)
    if municipality <= 0:
        return 0.0
    window = [
        project(URBAN_BBOX["min_lat"], URBAN_BBOX["min_lng"]),
        project(URBAN_BBOX["min_lat"], URBAN_BBOX["max_lng"]),
        project(URBAN_BBOX["max_lat"], URBAN_BBOX["max_lng"]),
        project(URBAN_BBOX["max_lat"], URBAN_BBOX["min_lng"]),
    ]
    min_x = min(x for x, _ in window)
    max_x = max(x for x, _ in window)
    min_y = min(y for _, y in window)
    max_y = max(y for _, y in window)

    # Sample the window on a lattice and keep the points the outline contains.
    step = 60.0
    cols = int((max_x - min_x) / step)
    rows = int((max_y - min_y) / step)
    if cols <= 0 or rows <= 0:
        return 0.0

    outline = [project(lat, lng) for lat, lng in ring]
    inside = 0
    for i in range(cols):
        x = min_x + (i + 0.5) * step
        for j in range(rows):
            y = min_y + (j + 0.5) * step
            if point_in_ring(x, y, outline):
                inside += 1
    covered = inside * step * step
    return round(covered / municipality * 100.0, 1)


def pt_pct(value: float) -> str:
    """Percent with a comma, matching the pt-BR text of SOURCES.md."""
    return f"{value:.1f}".replace(".", ",")


def point_in_ring(x: float, y: float, ring: list[tuple[float, float]]) -> bool:
    inside = False
    count = len(ring)
    for i in range(count):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % count]
        if (y1 > y) != (y2 > y):
            cut = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < cut:
                inside = not inside
    return inside


def bbox_clause(bbox: dict[str, float] | None = None) -> str:
    box = bbox or URBAN_BBOX
    return f"({box['min_lat']},{box['min_lng']},{box['max_lat']},{box['max_lng']})"


# --------------------------------------------------------------------------- #
# layers
# --------------------------------------------------------------------------- #


def cached(name: str, force: bool):
    """Return the cached path for a layer, or None when absent."""
    path = CACHE / f"{name}.json"
    return None if (force or not path.exists()) else path


def write_cache(name: str, payload: dict[str, Any]) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def load(name: str) -> dict[str, Any]:
    return json.loads((CACHE / f"{name}.json").read_text(encoding="utf-8"))


def fetch_boundary(force: bool) -> dict[str, Any]:
    if cached("boundary", force):
        return load("boundary")
    url = f"{IBGE_MALHAS.format(code=IBGE_CODE)}?qualidade=maxima&formato=application/vnd.geo+json"
    print(f"  boundary <- IBGE {url}")
    data = json.loads(_get(url))
    if data.get("type") != "FeatureCollection" or not data.get("features"):
        raise RuntimeError("IBGE devolveu malha vazia")
    write_cache("boundary", data)
    return data


def _ways(
    query: str, label: str, force: bool, attempts: int = 5, allow_empty: bool = False
) -> list[dict[str, Any]]:
    path = cached(label, force)
    if path:
        return load(label)["elements"]
    print(f"  {label} <- Overpass")
    data = overpass(query, attempts=attempts)
    if not data.get("elements"):
        if not allow_empty:
            raise RuntimeError(f"{label}: Overpass devolveu 0 elementos")
        data = {"elements": []}
    write_cache(label, data)
    return load(label)["elements"]


def fetch_waterways(force: bool) -> list[dict[str, Any]]:
    # Relations are deliberately excluded: they make this query time out on the
    # public mirrors and the urban watercourses of Franca are mapped as ways.
    query = (
        "[out:json][timeout:180];"
        f'way["waterway"~"^(stream|river|canal|ditch)$"]{bbox_clause()};'
        "out body geom;"
    )
    return _ways(query, "waterways", force)


def fetch_roads(force: bool) -> list[dict[str, Any]]:
    query = (
        "[out:json][timeout:180];("
        f'way["highway"~"^(primary|secondary|trunk|tertiary)$"]{bbox_clause()};'
        ");out body geom;"
    )
    return _ways(query, "roads", force)


def fetch_buildings(force: bool) -> list[dict[str, Any]]:
    query = f'[out:json][timeout:240];way["building"]{bbox_clause()};out body geom;'
    return _ways(query, "buildings", force)


GREEN_LANDUSE = {"forest", "grass", "meadow", "orchard", "vineyard", "farmland", "village_green"}
BUILT_LANDUSE = {
    "residential",
    "industrial",
    "commercial",
    "retail",
    "construction",
    "railway",
    "quarry",
}
GREEN_NATURAL = {"wood", "scrub", "grassland", "wetland", "heath"}


def bbox_tiles(bbox: dict[str, float], rows: int, cols: int) -> list[dict[str, float]]:
    """Split a bbox into a grid of smaller ones.

    A single area-wide landuse query times out on the public mirrors because
    farmland and forest multipolygons carry thousands of nodes; querying small
    tiles keeps each response inside the server's budget.
    """
    tiles: list[dict[str, float]] = []
    lat_step = (bbox["max_lat"] - bbox["min_lat"]) / rows
    lng_step = (bbox["max_lng"] - bbox["min_lng"]) / cols
    for r in range(rows):
        for c in range(cols):
            tiles.append(
                {
                    "min_lat": round(bbox["min_lat"] + r * lat_step, 6),
                    "max_lat": round(bbox["min_lat"] + (r + 1) * lat_step, 6),
                    "min_lng": round(bbox["min_lng"] + c * lng_step, 6),
                    "max_lng": round(bbox["min_lng"] + (c + 1) * lng_step, 6),
                }
            )
    return tiles


def _tiled_ways(
    label: str, force: bool, builder, rows: int = 3, cols: int = 3
) -> list[dict[str, Any]]:
    """Run a per-tile Overpass query and merge the results.

    Splitting the area keeps each response small enough for the public mirrors;
    a tile that never answers becomes a reported gap instead of losing the rest.
    """
    seen: set[tuple[str, int]] = set()
    collected: list[dict[str, Any]] = []
    missing: list[int] = []
    tiles = bbox_tiles(URBAN_BBOX, rows=rows, cols=cols)
    for index, tile in enumerate(tiles, start=1):
        print(f"  {label} tile {index}/{len(tiles)}")
        try:
            # A tile with no mapped amenities is a valid empty answer, not a gap.
            ways = _ways(builder(tile), f"{label}_{index}", force, attempts=7, allow_empty=True)
        except RuntimeError as exc:
            missing.append(index)
            print(f"    tile {index} indisponivel: {exc}")
            continue
        for way in ways:
            key = (str(way.get("type")), int(way["id"]))
            if key in seen:
                continue
            seen.add(key)
            collected.append(way)
        print(f"    acumulado: {len(collected)}")

    if not collected:
        raise RuntimeError(f"{label}: nenhum elemento obtido")

    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{label}.json").write_text(
        json.dumps({"elements": collected, "missing_tiles": missing}, ensure_ascii=False),
        encoding="utf-8",
    )
    if missing:
        print(f"  ! {label} com tiles faltantes {missing}; reexecute para completar")
    return collected


def fetch_landuse(force: bool) -> list[dict[str, Any]]:
    """Green and built cover, so vegetation and imperviousness use real polygons.

    Relations are skipped on purpose: combined relation queries time out on the
    public mirrors. The area is walked tile by tile for the same reason.
    """
    alternation = "|".join(sorted(GREEN_LANDUSE | BUILT_LANDUSE))
    natural = "|".join(sorted(GREEN_NATURAL))

    def builder(tile: dict[str, float]) -> str:
        return (
            f"[out:json][timeout:120];("
            f'way["landuse"~"^({alternation})$"]{bbox_clause(tile)};'
            f'way["natural"~"^({natural})$"]{bbox_clause(tile)};'
            f'way["leisure"~"^(park|garden|nature_reserve)$"]{bbox_clause(tile)};'
            ");out body geom;"
        )

    return _tiled_ways("landuse", force, builder)


SERVICE_AMENITIES = {
    "hospital": "hospital",
    "clinic": "health_center",
    "doctors": "health_center",
    "school": "school",
    "college": "school",
    "kindergarten": "school",
    "fire_station": "emergency_base",
}


def fetch_facilities(force: bool) -> list[dict[str, Any]]:
    """Health and education services mapped in OSM, for the service-pressure index."""

    def builder(tile: dict[str, float]) -> str:
        alternation = "|".join(sorted(SERVICE_AMENITIES))
        return (
            f"[out:json][timeout:120];("
            f'nwr["amenity"~"^({alternation})$"]{bbox_clause(tile)};'
            ");out body geom;"
        )

    return _tiled_ways("facilities", force, builder)


def fetch_dem(force: bool) -> tuple[list[float], dict[str, float]]:
    """Assemble the elevation grid from Terrarium tiles over the urban bbox."""
    if cached("elevation", force):
        data = load("elevation")
        return data["values"], data["meta"]

    def tile_xy(lat: float, lng: float, zoom: int) -> tuple[int, int]:
        n = 2**zoom
        xtile = int((lng + 180.0) / 360.0 * n)
        lat_rad = math.radians(lat)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return xtile, ytile

    x0, y_top = tile_xy(URBAN_BBOX["max_lat"], URBAN_BBOX["min_lng"], DEM_ZOOM)
    x1, y_bottom = tile_xy(URBAN_BBOX["min_lat"], URBAN_BBOX["max_lng"], DEM_ZOOM)
    cols, rows = x1 - x0 + 1, y_bottom - y_top + 1
    print(f"  elevation <- AWS Terrarium z{DEM_ZOOM} tiles x[{x0}..{x1}] y[{y_top}..{y_bottom}]")

    mosaic = [[0.0] * (cols * 256) for _ in range(rows * 256)]
    fetched = 0
    for ty in range(y_top, y_bottom + 1):
        for tx in range(x0, x1 + 1):
            url = AWS_TERRARIUM.format(z=DEM_ZOOM, x=tx, y=ty)
            try:
                width, height, rgb = decode_png_rgb(_get(url, timeout=90, binary=True))
                values = terrarium_elevation(rgb)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                print(f"    tile {DEM_ZOOM}/{tx}/{ty} falhou: {exc}")
                continue
            for py in range(height):
                src = py * width
                dst_y = (ty - y_top) * 256 + py
                if dst_y >= len(mosaic):
                    continue
                row = mosaic[dst_y]
                for px in range(width):
                    dst_x = (tx - x0) * 256 + px
                    if dst_x < len(row):
                        row[dst_x] = values[src + px]
            fetched += 1
            time.sleep(0.05)

    if not fetched:
        raise RuntimeError("nenhum tile de elevação foi baixado")

    flat = [v for row in mosaic for v in row]
    valid = [v for v in flat if -500 < v < 5000]
    if not valid:
        raise RuntimeError("elevação invalida em todos os tiles")
    fallback = sum(valid) / len(valid)

    # Resample the mosaic onto the grid the API publishes.
    values: list[float] = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            sx = min(cols * 256 - 1, int(c / GRID_COLS * cols * 256))
            sy = min(rows * 256 - 1, int(r / GRID_ROWS * rows * 256))
            v = mosaic[sy][sx]
            values.append(round(v if -500 < v < 5000 else fallback, 1))

    min_x, _ = project(URBAN_BBOX["max_lat"], URBAN_BBOX["min_lng"])
    _, max_y = project(URBAN_BBOX["max_lat"], URBAN_BBOX["min_lng"])
    _, min_y = project(URBAN_BBOX["min_lat"], URBAN_BBOX["min_lng"])
    max_x, _ = project(URBAN_BBOX["min_lat"], URBAN_BBOX["max_lng"])

    meta = {
        "rows": GRID_ROWS,
        "cols": GRID_COLS,
        "min_x": round(min_x, 2),
        "min_y": round(min_y, 2),
        "max_x": round(max_x, 2),
        "max_y": round(max_y, 2),
        "resolution_m": round((max_x - min_x) / GRID_COLS, 1),
        "tiles_fetched": fetched,
        "tiles_expected": cols * rows,
        "zoom": DEM_ZOOM,
        "min_elevation_m": round(min(valid), 1),
        "max_elevation_m": round(max(valid), 1),
        "source": "AWS Terrain Tiles (Terrarium / SRTM)",
    }
    write_cache("elevation", {"values": values, "meta": meta})
    return values, meta


def resolve_vulnerability_points(roads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Geolocate the documented flood points onto real OSM street geometry."""
    out: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for spec in DOCUMENTED_FLOOD_POINTS:
        street = spec["street"]
        matches = [
            way
            for way in roads
            if (way.get("tags") or {}).get("name", "").strip().casefold() == street.casefold()
        ]
        if not matches:
            matches = [
                way
                for way in roads
                if street.casefold() in (way.get("tags") or {}).get("name", "").casefold()
            ]
        points: list[tuple[float, float]] = []
        for way in matches:
            for geom in way.get("geometry", []):
                lat, lng = float(geom["lat"]), float(geom["lon"])
                if in_bbox(lat, lng):
                    points.append((lat, lng))
        if not points:
            unresolved.append(street)
            continue

        # Midpoint of the in-bbox span: stable and independent of way order.
        lat_mid = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
        lng_mid = (min(p[1] for p in points) + max(p[1] for p in points)) / 2
        nearest = min(points, key=lambda p: (p[0] - lat_mid) ** 2 + (p[1] - lng_mid) ** 2)
        out.append(
            {
                **spec,
                "location": {"lat": round(nearest[0], 6), "lng": round(nearest[1], 6)},
                "street_osm": street,
                "geometry_matched": len(points),
            }
        )

    if unresolved:
        print(f"  ! pontos nao resolvidos (omitidos, sem coordenada inventada): {unresolved}")
    return out


# --------------------------------------------------------------------------- #
# fixture writing
# --------------------------------------------------------------------------- #


def dump(name: str, payload: Any) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    path = FIXTURES / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    size_kb = path.stat().st_size / 1024
    print(f"  -> {path.relative_to(BACKEND)} ({size_kb:.0f} KB)")


def write_sources(
    elevation_meta: dict[str, Any], counts: dict[str, int], coverage_pct: float
) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Fontes dos dados de Franca/SP",
        "",
        "Gerado por `python -m scripts.fetch_franca_data`. Não editar à mão:",
        "reexecute o script para atualizar os dados e a data de coleta.",
        "",
        f"Coletado em: {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} (UTC)",
        "",
        "| Camada | Provedor | Dataset | Licença |",
        "| --- | --- | --- | --- |",
        "| Limite municipal | IBGE | API de Malhas (qualidade máxima, GeoJSON) | "
        "CC-BY-SA 4.0 / uso público |",
        "| Demografia | IBGE | Painel de Cidades (Franca/SP) | CC-BY-SA 4.0 |",
        "| Hidrografia | OpenStreetMap | `waterway` stream/river/canal/ditch | ODbL |",
        "| Sistema viario | OpenStreetMap | `highway` primary/secondary/trunk/tertiary | ODbL |",
        "| Edificações | OpenStreetMap | `building` | ODbL |",
        "| Cobertura do solo | OpenStreetMap | `landuse`, `natural`, `leisure` | ODbL |",
        "| Equipamentos públicos | OpenStreetMap | `amenity` hospital/clinic/school | ODbL |",
        "| Relevo | AWS Terrain Tiles | Terrarium sobre SRTM | CC-BY / uso público |",
        "| Pontos vulneráveis | Prefeitura de Franca | Plano de Contingência de "
        "Defesa Civil | Documento público municipal |",
        "",
        "## Contagens",
        "",
    ]
    for key, value in counts.items():
        lines.append(f"- **{key}**: {value}")
    lines += [
        "",
        "## Relevo",
        "",
        f"- Zoom {elevation_meta['zoom']}, {elevation_meta['tiles_fetched']}/"
        f"{elevation_meta['tiles_expected']} tiles obtidos",
        f"- Altitude mínima {elevation_meta['min_elevation_m']} m, "
        f"máxima {elevation_meta['max_elevation_m']} m",
        f"- Resolução da grade publicada {elevation_meta['resolution_m']} m",
        "",
        "## Pontos vulneráveis",
        "",
        "As coordenadas são geolocalizadas no nível da via (OSM) a partir do nome",
        "citado no plano municipal. `severity` é qualitativa e vem do documento;",
        "o texto em `evidence` é a transcrição da fonte.",
        "",
        "## Limitações conhecidas",
        "",
        "As regiões do twin são **sub-bacias hidrográficas**, não bairros: Franca",
        "não tem divisão territorial oficial publicada pelo IBGE.",
        "",
        f"**O modelo cobre {pt_pct(coverage_pct)}% da área do município.** O limite do IBGE",
        "tem 605,679 km², mas o DEM e todas as camadas derivadas são recortados pela",
        "janela urbana em `URBAN_BBOX`. As sub-bacias são, portanto, as sub-bacias",
        "que caem nessa janela, não a partição territorial do município.",
        "",
        "- A população é rateada pela densidade real de edificações (OSM) e cada",
        "  região carrega `population_is_estimated: true`. A soma fecha com o total",
        "  municipal por construção, o que pressupõe que toda a população do",
        f"  município está dentro da janela modelada ({pt_pct(coverage_pct)}% da área).",
        "  A periferia não é representada: ler as sub-bacias como cobertura do",
        "  município inteiro superestima a densidade em todo o território.",
        "- A vulnerabilidade social é um proxy por densidade de tecido urbano,",
        "  não renda por setor censitário, que não está disponível aqui.",
        "- A janela do DEM é um retângulo e o município não é: os cantos dela",
        "  caem fora de Franca. As sub-bacias afetadas não são recortadas, porque",
        "  uma bacia é unidade hidrológica e cortá-la por linha administrativa",
        "  distorceria a partição. Elas carregam `within_municipality: false`.",
        "- A impermeabilidade usa comprimento de rua por km2 como aproximação de",
        "  área selada, porque a cobertura de edificações do OSM é esparsa.",
        "- `landuse_coverage` informa quanto da região o OSM mapeia; os índices de",
        "  vegetação e área construída leem só o que está mapeado.",
        "- As unidades oficiais de risco potencial de erosão (DWG) não são",
        "  georreferenciadas aqui: nenhum ponto de erosão é publicado.",
        "- As fontes divergem no nome da terceira Colina, então o relevo não é",
        "  rotulado.",
        "- Dados externos não são chamados em runtime; a API lê apenas estes",
        "  fixtures versionados.",
        "",
        "## Referências",
        "",
        f"- IBGE Cidades Franca/SP: {IBGE_CITY}",
        f"- IBGE Malhas município {IBGE_CODE}: {IBGE_MALHAS.format(code=IBGE_CODE)}",
        "- AWS Terrain Tiles: https://registry.opendata.aws/terrain-tiles/",
        f"- Plano de Contingência de Defesa Civil: {PLAN_DEFESA_CIVIL}",
        "",
    ]
    (FIXTURES / "SOURCES.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> {(FIXTURES / 'SOURCES.md').relative_to(BACKEND)}")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #


@dataclass
class Report:
    layers: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def main(force: bool) -> int:
    report = Report()
    print(f"Franca/SP -> fixtures (origin {ORIGIN_LAT}, {ORIGIN_LNG})")

    print("\n[1/8] limite municipal")
    try:
        boundary = fetch_boundary(force)
        geometry = boundary["features"][0]["geometry"]
        rings = geometry["coordinates"]
        # GeoJSON nests Polygon as [ring,...] and MultiPolygon as [polygon,...].
        outer = rings[0] if geometry["type"] == "Polygon" else rings[0][0]
        polygon = [[round(lat, 6), round(lng, 6)] for lng, lat in outer]
        dump("boundary", {"type": "Polygon", "coordinates": polygon, "ibge_code": IBGE_CODE})
        report.layers["boundary"] = f"{len(polygon)} vertices"
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"boundary: {exc}")
        print(f"  ! boundary falhou: {exc}")

    print("\n[2/8] hidrografia")
    waterways: list[dict[str, Any]] = []
    try:
        waterways = fetch_waterways(force)
        dump(
            "waterways",
            [
                {
                    "osm_id": way["id"],
                    "name": (way.get("tags") or {}).get("name"),
                    "kind": (way.get("tags") or {}).get("waterway"),
                    "geometry": [
                        [round(float(g["lat"]), 6), round(float(g["lon"]), 6)]
                        for g in way.get("geometry", [])
                    ],
                }
                for way in waterways
                if way.get("geometry")
            ],
        )
        report.layers["waterways"] = f"{len(waterways)} ways"
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"waterways: {exc}")
        print(f"  ! waterways falhou: {exc}")

    print("\n[3/8] sistema viario")
    roads: list[dict[str, Any]] = []
    try:
        roads = fetch_roads(force)
        dump(
            "roads",
            [
                {
                    "osm_id": way["id"],
                    "name": (way.get("tags") or {}).get("name") or "Via sem nome",
                    "highway": (way.get("tags") or {}).get("highway"),
                    "lanes": (way.get("tags") or {}).get("lanes"),
                    "oneway": (way.get("tags") or {}).get("oneway"),
                    "geometry": [
                        [round(float(g["lat"]), 6), round(float(g["lon"]), 6)]
                        for g in way.get("geometry", [])
                    ],
                }
                for way in roads
                if way.get("geometry")
            ],
        )
        report.layers["roads"] = f"{len(roads)} ways"
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"roads: {exc}")
        print(f"  ! roads falhou: {exc}")

    print("\n[4/8] edificacoes")
    buildings: list[dict[str, Any]] = []
    try:
        buildings = fetch_buildings(force)
        dump(
            "buildings",
            [
                {
                    "osm_id": way["id"],
                    "levels": (way.get("tags") or {}).get("building:levels"),
                    "geometry": [
                        [round(float(g["lat"]), 6), round(float(g["lon"]), 6)]
                        for g in way.get("geometry", [])
                    ],
                }
                for way in buildings
                if len(way.get("geometry", [])) >= 4
            ],
        )
        report.layers["buildings"] = f"{len(buildings)} ways"
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"buildings: {exc}")
        print(f"  ! buildings falhou: {exc}")

    print("\n[5/8] cobertura do solo (landuse/natural)")
    landuse: list[dict[str, Any]] = []
    try:
        landuse = fetch_landuse(force)
        dump(
            "landuse",
            [
                {
                    "osm_id": way["id"],
                    "tag": next(
                        (
                            t
                            for t in ("landuse", "natural", "leisure")
                            if t in (way.get("tags") or {})
                        ),
                        None,
                    ),
                    "value": next(
                        (
                            (way.get("tags") or {}).get(t)
                            for t in ("landuse", "natural", "leisure")
                            if t in (way.get("tags") or {})
                        ),
                        None,
                    ),
                    "geometry": [
                        [round(float(g["lat"]), 6), round(float(g["lon"]), 6)]
                        for g in way.get("geometry", [])
                    ],
                }
                for way in landuse
                if len(way.get("geometry", [])) >= 4
            ],
        )
        report.layers["landuse"] = f"{len(landuse)} polygons"
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"landuse: {exc}")
        print(f"  ! landuse falhou: {exc}")

    print("\n[6/8] equipamentos publicos (OSM)")
    facilities: list[dict[str, Any]] = []
    try:
        facilities = fetch_facilities(force)
        dump(
            "facilities",
            [
                {
                    "osm_id": way["id"],
                    "osm_type": way.get("type"),
                    "name": (way.get("tags") or {}).get("name"),
                    "amenity": (way.get("tags") or {}).get("amenity"),
                    "emergency": (way.get("tags") or {}).get("emergency"),
                    "lat": (float(way["lat"]) if way.get("type") == "node" else None),
                    "lon": (float(way["lon"]) if way.get("type") == "node" else None),
                    "geometry": (
                        [
                            [round(float(g["lat"]), 6), round(float(g["lon"]), 6)]
                            for g in way.get("geometry", [])
                        ]
                        if way.get("geometry")
                        else None
                    ),
                }
                for way in facilities
            ],
        )
        report.layers["facilities"] = f"{len(facilities)} elements"
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"facilities: {exc}")
        print(f"  ! facilities falhou: {exc}")

    print("\n[7/8] relevo (DEM)")
    elevation_meta: dict[str, Any] = {}
    try:
        values, elevation_meta = fetch_dem(force)
        dump("elevation", {**elevation_meta, "values": values})
        report.layers["elevation"] = f"{GRID_ROWS}x{GRID_COLS} cells"
    except Exception as exc:  # noqa: BLE001
        report.errors.append(f"elevation: {exc}")
        print(f"  ! elevation falhou: {exc}")

    print("\n[8/8] pontos vulneraveis")
    points: list[dict[str, Any]] = []
    if roads:
        try:
            points = resolve_vulnerability_points(roads)
            dump(
                "vulnerability_points",
                [
                    {
                        "id": p["id"],
                        "name": p["name"],
                        "kind": "flood",
                        "severity": p["severity"],
                        "street": p["street"],
                        "waterway": p["waterway"],
                        "evidence": p["evidence"],
                        "source": "Prefeitura de Franca - Plano de Contingencia de Defesa Civil",
                        "reference": PLAN_DEFESA_CIVIL,
                        "location": p["location"],
                    }
                    for p in points
                ],
            )
            report.layers["vulnerability_points"] = (
                f"{len(points)}/{len(DOCUMENTED_FLOOD_POINTS)} resolvidos"
            )
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"vulnerability_points: {exc}")

    dump("metadata", {**IBGE_DEMOGRAPHY, "urban_bbox": URBAN_BBOX, "dem": elevation_meta})

    if elevation_meta:
        coverage = 0.0
        try:
            stored = json.loads((FIXTURES / "boundary.json").read_text(encoding="utf-8"))
            coverage = modelled_coverage_pct(stored["coordinates"])
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"coverage: {exc}")
        write_sources(
            elevation_meta,
            {
                "Vertices do limite": report.layers.get("boundary", "?"),
                "Cursos d'agua": report.layers.get("waterways", "?"),
                "Vias": report.layers.get("roads", "?"),
                "Edificacoes": report.layers.get("buildings", "?"),
                "Cobertura do solo": report.layers.get("landuse", "?"),
                "Equipamentos publicos": report.layers.get("facilities", "?"),
                "Celulas do DEM": report.layers.get("elevation", "?"),
                "Pontos vulneraveis": report.layers.get("vulnerability_points", "?"),
                "Area do municipio": "605,679 km2 (IBGE Malhas)",
                "Area modelada": f"{pt_pct(coverage)}% do municipio (janela URBAN_BBOX)",
            },
            coverage,
        )

    print("\n--- resumo ---")
    for key, value in report.layers.items():
        print(f"  {key}: {value}")
    if report.errors:
        print("\nerros:")
        for error in report.errors:
            print(f"  - {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(force="--force" in sys.argv))
