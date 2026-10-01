from fastapi import APIRouter

from app.ai.copilot import analyze
from app.data import get_city
from app.engine.costs import catalogue as cost_catalogue
from app.engine.costs import price_interventions
from app.engine.interventions import catalogue, normalize
from app.engine.optimize import optimize
from app.engine.simulation import compare, run_simulation
from app.schemas import (
    CityModel,
    CompareRequest,
    CopilotRequest,
    CopilotResponse,
    OptimizeRequest,
    OptimizeResponse,
    RunRequest,
    RunResponse,
    SimulateRequest,
    SimulationComparison,
    SimulationResult,
)

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/city", response_model=CityModel)
def city() -> CityModel:
    return get_city()


@router.get("/interventions/catalogue")
def interventions_catalogue() -> list[dict[str, object]]:
    return catalogue()


@router.get("/costs/catalogue")
def costs_catalogue() -> list[dict[str, object]]:
    """Unit prices and sizing caps behind every budget figure, published.

    The optimiser is only as trustworthy as these assumptions, so they are
    served next to the numbers they produce instead of hiding in the code.
    """
    return cost_catalogue()


@router.post("/run", response_model=RunResponse)
def run(payload: RunRequest) -> RunResponse:
    """Baseline and mitigated results in one response.

    The UI used to call /simulate and /compare in parallel, which could paint a
    mitigated result beside a baseline from a different request. Returning both
    halves together removes that race by construction.
    """
    city_model = get_city()
    baseline = run_simulation(city_model, payload.scenario, [], "baseline")
    interventions = price_interventions(
        city_model, payload.scenario, baseline, [normalize(i) for i in payload.interventions]
    )
    mitigated = (
        run_simulation(city_model, payload.scenario, interventions, "mitigated")
        if interventions
        else baseline
    )
    total_cost = round(sum(i.cost_brl for i in interventions), 2)

    return RunResponse(
        scenario=payload.scenario,
        baseline=baseline,
        mitigated=mitigated,
        comparison=compare(city_model, payload.scenario, interventions, baseline),
        total_cost_brl=total_cost,
        budget_brl=payload.budget_brl,
        within_budget=payload.budget_brl is None or total_cost <= payload.budget_brl,
    )


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_interventions(payload: OptimizeRequest) -> OptimizeResponse:
    return optimize(get_city(), payload)


@router.post("/simulate", response_model=SimulationResult)
def simulate(payload: SimulateRequest) -> SimulationResult:
    city_model = get_city()
    interventions = [normalize(i) for i in payload.interventions]
    label = "mitigated" if interventions else "baseline"
    return run_simulation(city_model, payload.scenario, interventions, label)  # type: ignore[arg-type]


@router.post("/compare", response_model=SimulationComparison)
def compare_scenarios(payload: CompareRequest) -> SimulationComparison:
    city_model = get_city()
    interventions = [normalize(i) for i in payload.interventions]
    return compare(city_model, payload.scenario, interventions)


@router.post("/copilot", response_model=CopilotResponse)
def copilot(payload: CopilotRequest) -> CopilotResponse:
    return analyze(get_city(), payload)


@router.get("/scenarios")
def scenarios() -> list[dict[str, object]]:
    return [
        {
            "type": "extreme_rain",
            "label": "Chuva extrema",
            "params": ["intensity", "duration"],
            "impacts": [
                "alagamentos",
                "bloqueio de vias",
                "isolamento de regiões",
                "equipamentos públicos afetados",
            ],
        },
        {
            "type": "heat_wave",
            "label": "Onda de calor",
            "params": ["intensity", "duration"],
            "impacts": [
                "exposição térmica",
                "baixa cobertura vegetal",
                "pressão sobre saúde",
                "necessidade de resfriamento",
            ],
        },
        {
            "type": "hailstorm",
            "label": "Granizo",
            "params": ["intensity", "duration"],
            "impacts": ["danos a coberturas", "equipamentos expostos", "interrupção de serviços"],
        },
        {
            "type": "windstorm",
            "label": "Ventania",
            "params": ["intensity", "duration"],
            "impacts": ["queda de árvores", "bloqueio de vias", "danos a edificações"],
        },
        {
            "type": "wildfire",
            "label": "Queimada de grande porte",
            "params": ["intensity", "duration"],
            "impacts": ["vegetação seca", "exposição à fumaça", "isolamento de regiões"],
        },
    ]
