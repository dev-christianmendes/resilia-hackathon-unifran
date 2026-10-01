from fastapi import APIRouter

from app.ai.copilot import analyze
from app.data import get_city
from app.engine.interventions import catalogue, normalize
from app.engine.simulation import compare, run_simulation
from app.schemas import (
    CityModel,
    CompareRequest,
    CopilotRequest,
    CopilotResponse,
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
    ]
