from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ScenarioType(str, Enum):
    EXTREME_RAIN = "extreme_rain"
    HEAT_WAVE = "heat_wave"


class InterventionType(str, Enum):
    GREEN_AREA = "green_area"
    RESERVOIR = "reservoir"
    SHELTER = "shelter"
    ALTERNATE_ROUTE = "alternate_route"
    CARE_POST = "care_post"


class FacilityType(str, Enum):
    HOSPITAL = "hospital"
    SCHOOL = "school"
    HEALTH_CENTER = "health_center"
    EMERGENCY_BASE = "emergency_base"


class RiskLevel(str, Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"


class Point(BaseModel):
    x: float = Field(description="Posição no eixo leste-oeste, em metros")
    y: float = Field(description="Posição no eixo norte-sul, em metros")
    lat: float | None = None
    lng: float | None = None


class CoordinateReferenceSystem(BaseModel):
    """Declares which plane the ``x``/``y`` numbers on every Point belong to.

    The city is stored geodetically (WGS84) and rendered in a local metric
    plane. Both facts are published so a client never has to infer them.
    """

    name: str
    projection: str
    units: str = "metre"
    origin_lat: float
    origin_lng: float


class DataSource(BaseModel):
    """Provenance record for one input that shaped the city."""

    layer: str
    provider: str
    dataset: str
    reference: str | None = None
    licence: str | None = None
    retrieved_at: str
    detail: str | None = None


class ElevationGrid(BaseModel):
    """Regular DEM grid stored row-major, north row first, in whole metres."""

    rows: int
    cols: int
    values: list[float]
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    resolution_m: float
    source: str
    vertical_exaggeration: float = Field(default=1.0, ge=1.0)


class Waterway(BaseModel):
    """A real surface watercourse, kept separate from the road network.

    Keeping streams out of ``Road`` is what lets the engine reason about
    distance-to-water and overtopping instead of mistaking a creek for a street.
    """

    id: str
    name: str | None = None
    kind: Literal["river", "stream", "canal", "ditch"]
    path: list[Point]
    width_m: float = 0.0
    osm_id: str | None = None
    source: str = "OpenStreetMap"


class VulnerabilityPoint(BaseModel):
    """A documented exposure site.

    Every instance must carry the document it came from; a vulnerability that
    cannot be traced back to a source is not published by this API.
    """

    id: str
    name: str
    kind: Literal["flood", "erosion", "heat", "infrastructure"]
    location: Point
    severity: float = Field(ge=0, le=1)
    street: str | None = None
    waterway: str | None = None
    evidence: str = Field(description="Trecho da fonte que descreve o ponto")
    source: str
    reference: str | None = None


class Facility(BaseModel):
    id: str
    name: str
    type: FacilityType
    region_id: str
    location: Point
    capacity: int = Field(description="Capacidade de atendimento estimada")
    critical: bool = True


class Road(BaseModel):
    id: str
    name: str
    region_id: str
    path: list[Point]
    class_: Literal["arterial", "collector", "local"] = "collector"
    critical: bool = False
    osm_id: str | None = None
    source: str = "OpenStreetMap"


class Building(BaseModel):
    id: str
    region_id: str
    location: Point
    width: float
    depth: float
    height: float
    floors: int
    use: Literal["residential", "commercial", "industrial", "public"] = "residential"
    osm_id: str | None = None


class Tree(BaseModel):
    id: str
    region_id: str
    location: Point
    radius: float
    height: float


class RegionMetrics(BaseModel):
    """Indicadores de vulnerabilidade used by the simulation engine.

    Elevation, slope and waterway distance are measured on the real DEM and the
    real hydrography. ``population_is_estimated`` stays true wherever the
    population was apportioned from a municipal total instead of read from a
    sector-level count.
    """

    population: int
    population_is_estimated: bool = True
    population_density: float
    vegetation_index: float = Field(ge=0, le=1)
    impermeability: float = Field(ge=0, le=1)
    flood_risk: float = Field(ge=0, le=1)
    heat_exposure: float = Field(ge=0, le=1)
    elevation_m: float = Field(description="Elevação média medida no DEM, em metros")
    elevation_min_m: float = 0.0
    elevation_max_m: float = 0.0
    slope_deg: float = 0.0
    waterway_proximity_m: float = Field(description="Distância ao curso d'água real mais próximo")
    building_footprint_ratio: float = Field(default=0.0, ge=0, le=1)
    landuse_coverage: float = Field(
        default=0.0,
        ge=0,
        le=1,
        description="Fração da região classificada por polígonos de cobertura do solo",
    )
    vulnerability: float = Field(ge=0, le=1)
    vulnerability_is_estimated: bool = True
    historical_events: int = Field(ge=0)


class Region(BaseModel):
    id: str
    name: str
    polygon: list[Point]
    centroid: Point
    metrics: RegionMetrics
    road_count: int = 0
    facilities: list[Facility] = Field(default_factory=list)
    within_municipality: bool = Field(
        default=True,
        description=(
            "Falso quando algum vértice ou o centroide cai fora do limite do IBGE. "
            "A janela do DEM é um retângulo e o município não é retangular, então "
            "algumas sub-bacias da borda extrapolam o território."
        ),
    )


class CityModel(BaseModel):
    id: str
    name: str
    ibge_code: str | None = None
    crs: CoordinateReferenceSystem
    bounds: dict[str, float]
    boundary: list[Point] = Field(
        default_factory=list,
        description=(
            "Limite municipal em anel fechado, no mesmo plano local das demais "
            "camadas. Lista vazia apenas quando a fonte não foi ingerida."
        ),
    )
    regions: list[Region]
    roads: list[Road]
    waterways: list[Waterway] = Field(default_factory=list)
    facilities: list[Facility] = Field(default_factory=list)
    buildings: list[Building]
    trees: list[Tree]
    elevation: ElevationGrid | None = None
    vulnerability_points: list[VulnerabilityPoint] = Field(default_factory=list)
    sources: list[DataSource] = Field(default_factory=list)
    reference_scale_m: float = Field(
        default=1000.0,
        description="Referência de escala desenhada no mapa, em metros reais",
    )


class ScenarioParams(BaseModel):
    type: ScenarioType
    intensity: float = Field(ge=0, le=1)
    duration: float = Field(ge=0, le=1)


class Intervention(BaseModel):
    id: str
    type: InterventionType
    region_id: str
    location: Point
    impact_factor: float = Field(ge=0, le=1)
    cost_brl: float = Field(default=0.0, ge=0, description="Custo estimado em reais")
    label: str | None = None
    area_m2: float | None = Field(default=None, ge=0)


class RegionResult(BaseModel):
    region_id: str
    risk: float
    risk_level: RiskLevel
    baseline_risk: float
    affected_population: int
    compromised_roads: int
    critical_facilities_affected: int
    factors: dict[str, float]
    mitigations_applied: list[str] = Field(default_factory=list)


class SimulationTotals(BaseModel):
    affected_population: int
    compromised_roads: int
    critical_facilities_affected: int
    high_risk_regions: int
    population_exposure_index: float
    service_pressure_index: float


class SimulationResult(BaseModel):
    id: str
    scenario: ScenarioParams
    interventions: list[Intervention]
    label: Literal["baseline", "mitigated"]
    totals: SimulationTotals
    regions: list[RegionResult]


class ComparisonDelta(BaseModel):
    affected_population: int
    affected_population_pct: float
    compromised_roads: int
    compromised_roads_pct: float
    critical_facilities_affected: int
    critical_facilities_affected_pct: float
    service_pressure_index: float


class SimulationComparison(BaseModel):
    scenario: ScenarioParams
    baseline: SimulationTotals
    mitigated: SimulationTotals
    delta: ComparisonDelta
    per_region: list[dict[str, float | int | str]]


class SimulateRequest(BaseModel):
    scenario: ScenarioParams
    interventions: list[Intervention] = Field(default_factory=list)


class CompareRequest(BaseModel):
    scenario: ScenarioParams
    interventions: list[Intervention] = Field(default_factory=list)


class RunRequest(BaseModel):
    """Single call that returns the baseline and the mitigated run together.

    The UI used to fire /simulate and /compare in parallel, which could paint a
    mitigated result next to a baseline from a different request. One endpoint
    returning both halves removes the race by construction.
    """

    scenario: ScenarioParams
    interventions: list[Intervention] = Field(default_factory=list)
    budget_brl: float | None = Field(default=None, ge=0)


class RunResponse(BaseModel):
    scenario: ScenarioParams
    baseline: SimulationResult
    mitigated: SimulationResult
    comparison: SimulationComparison
    total_cost_brl: float
    budget_brl: float | None = None
    within_budget: bool = True


class OptimizeRequest(BaseModel):
    scenario: ScenarioParams
    budget_brl: float = Field(gt=0)
    max_interventions: int = Field(default=5, ge=1, le=12)
    allowed_types: list[InterventionType] | None = None


class ProposedIntervention(BaseModel):
    type: InterventionType
    region_id: str
    region_name: str
    label: str
    location: Point
    cost_brl: float
    impact_factor: float
    expected_affected_population_avoided: int
    expected_risk_reduction: float
    rationale: str


class OptimizeResponse(BaseModel):
    scenario: ScenarioParams
    budget_brl: float
    spent_brl: float
    remaining_brl: float
    baseline_totals: SimulationTotals
    projected_totals: SimulationTotals
    affected_population_avoided: int
    risk_reduction_pct: float
    selected: list[ProposedIntervention]
    rejected_budget: list[ProposedIntervention]
    method: str = "knapsack-gain-per-real"
    disclaimer: str = (
        "Estimativa do modelo da POC sob restrição orçamentária. "
        "Não substitui estudo de dimensionamento nem/licitação de obra."
    )


class CopilotRequest(BaseModel):
    scenario: ScenarioParams
    interventions: list[Intervention] = Field(default_factory=list)
    budget_brl: float | None = Field(default=None, ge=0)
    question: str = "Onde devo priorizar uma intervenção neste cenário?"


class CopilotFactor(BaseModel):
    label: str
    weight: float
    detail: str


class CopilotRecommendation(BaseModel):
    region_id: str
    region_name: str
    priority_score: float
    headline: str
    factors: list[CopilotFactor]
    suggested_intervention: InterventionType
    rationale: str
    estimated_cost_brl: float = 0.0
    expected_effect: dict[str, float | str]
    testable: bool = True
    disclaimer: str = (
        "Hipótese gerada pelo modelo de simulação da POC. "
        "Não é uma previsão operacional: valide com o Urban Copilot e simule antes de decidir."
    )
    source: Literal["llm", "heuristic"] = "heuristic"


class CopilotResponse(BaseModel):
    analysis: CopilotRecommendation
    answer: str
    follow_up_questions: list[str] = Field(default_factory=list)
