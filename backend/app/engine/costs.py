"""Cost model for the budget-constrained optimiser.

Every number here is an **order-of-magnitude hypothesis**, not a quote. They are
kept in one module so a real orçamento can replace them without touching the
optimiser, and so the UI can show the user which assumption drove a proposal.

Sizing rule: each type is priced per unit, and the unit is scaled by whatever the
intervention actually has to serve — the people the model says will be exposed,
the runoff the impermeable area produces, the roads that need a detour. Two caps
keep the sizing physically sane: a city cannot plant an unbounded park, and no
municipal shelter holds more than it can staff.

A flat price per intervention would make the optimiser indifferent to how big the
exposed region is, which is the opposite of what a budget expresses.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas import InterventionType, Region


@dataclass(frozen=True)
class CostModel:
    """Price of one unit of work, plus the smallest and largest sensible job."""

    unit: str
    unit_cost_brl: float
    minimum_brl: float
    maximum_brl: float
    unit_label: str


# Planting and 5 years of maintenance, per m². Bulk planting is cheaper per m²
# than a pocket park, but not by much, so a single rate is honest.
PLANT_COST_PER_M2 = 65.0
# Sized against the exposed population, not the region area: municipal green
# area standards are per capita (PLANT_M2_PER_CAPITA is in the range Brazilian
# planos directrices use), so a dense exposed region justifies more planting.
PLANT_M2_PER_CAPITA = 12.0
# Even a region with no exposure gets a small pocket park, not zero.
MIN_PLANT_M2 = 1_500.0
# 10 ha is already a large park for one sub-basin; past this the sizing is not
# credible and the cap, not the exposure, would be deciding.
PLANTABLE_CAP_M2 = 100_000.0

# Detention volume, per m³ of stored runoff, including earthwork, inlet and
# outlet structures.
RESERVOIR_COST_PER_M3 = 120.0
RESERVOIR_CAP_M3 = 90_000.0
RUNOFF_COEFFICIENT = 0.85
DESIGN_INTENSITY_MM_H = 45.0
SAFETY_FACTOR = 1.5

# One hosted bed, including fit-out and 12 months of operation.
BED_COST_BRL = 7_400.0
# A shelter covers part of the exposed population; it does not house everyone.
SHELTER_COVERAGE = 0.15
# Shelters are neighbourhood-scale, not stadium-scale: a single site beyond a
# few hundred beds is not what a municipality staffs. The cap is also what
# keeps the optimiser building a distributed network instead of one giant
# facility in the most exposed basin.
SHELTER_CAP_BEDS = 400.0

# One km of detour: resurfacing, signage and a stormwater gallery.
ROUTE_COST_PER_KM = 2_900_000.0
# A detour serves the corridors that actually fail, not the whole street
# network of a sub-basin.
ROUTE_CAP_KM = 6.0
METRES_PER_ROAD = 180.0

# One staffed post with vehicle, for 12 months.
CARE_POST_COST_BRL = 1_150_000.0
# People a single post absorbs before the municipality needs another one.
PEOPLE_PER_CARE_POST = 12_000.0
CARE_POST_CAP = 8.0

COSTS: dict[InterventionType, CostModel] = {
    InterventionType.GREEN_AREA: CostModel(
        unit="m2 plantados e mantidos por 5 anos",
        unit_cost_brl=PLANT_COST_PER_M2,
        minimum_brl=120_000.0,
        maximum_brl=PLANTABLE_CAP_M2 * PLANT_COST_PER_M2,
        unit_label="m2",
    ),
    InterventionType.RESERVOIR: CostModel(
        unit="m3 de capacidade de amortecimento, com obra civil",
        unit_cost_brl=RESERVOIR_COST_PER_M3,
        minimum_brl=650_000.0,
        maximum_brl=RESERVOIR_CAP_M3 * RESERVOIR_COST_PER_M3,
        unit_label="m3",
    ),
    InterventionType.SHELTER: CostModel(
        unit="cama de acolhimento operada por 12 meses",
        unit_cost_brl=BED_COST_BRL,
        minimum_brl=180_000.0,
        maximum_brl=SHELTER_CAP_BEDS * BED_COST_BRL,
        unit_label="camas",
    ),
    InterventionType.ALTERNATE_ROUTE: CostModel(
        unit="km de via recapeada e sinalizada, com galeria",
        unit_cost_brl=ROUTE_COST_PER_KM,
        minimum_brl=900_000.0,
        maximum_brl=ROUTE_CAP_KM * ROUTE_COST_PER_KM,
        unit_label="km",
    ),
    InterventionType.CARE_POST: CostModel(
        unit="posto de atendimento com equipe e veículo por 12 meses",
        unit_cost_brl=CARE_POST_COST_BRL,
        minimum_brl=CARE_POST_COST_BRL,
        maximum_brl=CARE_POST_CAP * CARE_POST_COST_BRL,
        unit_label="posto",
    ),
}

ASSUMPTION_NOTICE = (
    "Custos são hipóteses de ordem de grandeza para um município brasileiro de "
    "365 mil habitantes, não cotações. Substitua COSTS por dados do orçamento real."
)


def region_area_m2(region: Region) -> float:
    """Shoelace area in m², recomputed from the published vertices.

    Duplicated instead of imported from ``app.data.geo`` on purpose: the engine
    must stay free of the data layer, so a client can reuse the optimiser with
    its own Region objects.
    """
    total = 0.0
    count = len(region.polygon)
    for i in range(count):
        current = region.polygon[i]
        following = region.polygon[(i + 1) % count]
        total += current.x * following.y - following.x * current.y
    return abs(total) / 2.0


def quantity_for(
    kind: InterventionType,
    region: Region,
    scenario_intensity: float,
    affected_population: int,
) -> float:
    """How much of the unit this region actually needs, given the scenario.

    ``affected_population`` is what the engine already computed for this region
    under this scenario. Sizing people-serving work against the total population
    would build shelters nobody is forecast to need.
    """
    if kind is InterventionType.GREEN_AREA:
        return min(
            PLANTABLE_CAP_M2,
            max(MIN_PLANT_M2, affected_population * PLANT_M2_PER_CAPITA),
        )

    if kind is InterventionType.RESERVOIR:
        # Only the sealed fraction produces runoff worth storing.
        sealed_area = region_area_m2(region) * region.metrics.impermeability
        runoff_m3 = (
            sealed_area
            * RUNOFF_COEFFICIENT
            * (DESIGN_INTENSITY_MM_H / 1000.0)
            * max(0.1, scenario_intensity)
            * SAFETY_FACTOR
        )
        return min(RESERVOIR_CAP_M3, runoff_m3)

    if kind is InterventionType.SHELTER:
        return min(SHELTER_CAP_BEDS, max(1.0, affected_population * SHELTER_COVERAGE))

    if kind is InterventionType.ALTERNATE_ROUTE:
        metres = max(METRES_PER_ROAD, region.road_count * METRES_PER_ROAD)
        return min(ROUTE_CAP_KM, max(0.6, metres / 1000.0))

    return min(CARE_POST_CAP, max(1.0, affected_population / PEOPLE_PER_CARE_POST))


def cost_for(
    kind: InterventionType,
    region: Region,
    scenario_intensity: float,
    affected_population: int,
    impact_factor: float,
) -> tuple[float, float]:
    """Return ``(cost_brl, quantity)`` for one intervention on one region.

    A weaker intervention is proportionally less work but never free, which is
    why the scaling is ``0.55 + 0.45 * impact_factor`` and not a bare product.
    """
    model = COSTS[kind]
    quantity = quantity_for(kind, region, scenario_intensity, affected_population)
    scaled = quantity * (0.55 + 0.45 * impact_factor)
    cost = model.unit_cost_brl * scaled
    cost = max(model.minimum_brl, min(model.maximum_brl, cost))
    return round(cost, 2), round(scaled, 2)


def catalogue() -> list[dict[str, object]]:
    """The cost table, published so the UI can show what drove each proposal."""
    rows: list[dict[str, object]] = [
        {
            "type": kind.value,
            "unit": model.unit,
            "unit_cost_brl": model.unit_cost_brl,
            "minimum_brl": model.minimum_brl,
            "maximum_brl": model.maximum_brl,
            "unit_label": model.unit_label,
        }
        for kind, model in COSTS.items()
    ]
    rows.append({"type": "notice", "notice": ASSUMPTION_NOTICE})
    return rows
