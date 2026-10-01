"""Urban Copilot.

Two interchangeable backends behind one interface:

* `heuristic` — deterministic analysis derived from the same factors the
  simulation engine uses. Always available, fully offline, used for tests
  and as the demo fallback.
* `llm` — OpenAI-compatible chat completion with a JSON-schema response.
  Enabled only when `URBAN_COPILOT_API_KEY` is set.

The LLM never decides: it is instructed to return a testable hypothesis that
the user validates by re-running the simulation.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from app.engine.costs import ASSUMPTION_NOTICE, cost_for
from app.engine.simulation import (
    FACTOR_LABELS,
    INTERVENTION_LABELS,
    compare,
    run_simulation,
)
from app.schemas import (
    CityModel,
    CopilotFactor,
    CopilotRecommendation,
    CopilotRequest,
    CopilotResponse,
    Intervention,
    InterventionType,
    ScenarioParams,
    ScenarioType,
    SimulationResult,
)

SYSTEM_PROMPT = """Você é o Urban Copilot de uma plataforma de Digital Twin urbano
para resiliência climática.

Regras:
- Você NÃO decide e NÃO executa nada. Você propõe uma HIPÓTESE testável.
- Use exclusivamente os fatores e números fornecidos no contexto. Nunca invente dados.
- Justifique com os fatores de maior peso do modelo de simulação.
- Sempre indique a região priorizada e UMA intervenção sugerida.
- Escreva em português do Brasil, de forma curta e técnica.
- Sempre inclua a ressalva de que o resultado é uma estimativa da POC, não uma previsão operacional.
"""

RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "urban_copilot_recommendation",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "region_id",
            "priority_score",
            "headline",
            "factors",
            "suggested_intervention",
            "rationale",
            "answer",
        ],
        "properties": {
            "region_id": {"type": "string"},
            "priority_score": {"type": "number"},
            "headline": {"type": "string"},
            "factors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["label", "weight", "detail"],
                    "properties": {
                        "label": {"type": "string"},
                        "weight": {"type": "number"},
                        "detail": {"type": "string"},
                    },
                },
            },
            "suggested_intervention": {
                "type": "string",
                "enum": [k.value for k in InterventionType],
            },
            "rationale": {"type": "string"},
            "answer": {"type": "string"},
            "follow_up_questions": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    },
}

FOLLOW_UPS = [
    "Qual o efeito de aumentar a intensidade do cenário?",
    "E se eu combinar um reservatório com uma área verde?",
    "Quais equipamentos críticos estão mais expostos?",
]

# Detail the engine's canonical factor names do not carry. Everything else comes
# from app.engine.simulation.FACTOR_LABELS, so a factor has one name in the
# product instead of one per module.
FACTOR_DETAIL: dict[str, str] = {
    "drainage_deficit": "impermeabilidade do solo combinada à cobertura vegetal",
    "runoff": "escoamento superficial gerado pela chuva",
    "storage_capacity": "capacidade de armazenamento de água existente",
    "heat_exposure": "exposição térmica histórica da região",
}

# Dominant factor -> intervention that addresses it. Ordered by specificity, and
# scoped per scenario so a heat wave never gets a drainage answer.
_SUGGESTION_RULES: dict[ScenarioType, list[tuple[tuple[str, ...], InterventionType]]] = {
    ScenarioType.EXTREME_RAIN: [
        (("drainage_deficit", "runoff", "storage_capacity"), InterventionType.RESERVOIR),
        (("terrain_susceptibility",), InterventionType.RESERVOIR),
        (("social_vulnerability",), InterventionType.SHELTER),
    ],
    ScenarioType.HEAT_WAVE: [
        (("shade_deficit", "thermal_mass"), InterventionType.GREEN_AREA),
        (("heat_exposure", "heat_load"), InterventionType.CARE_POST),
        (("social_vulnerability",), InterventionType.SHELTER),
    ],
}


_SCENARIO_LABELS: dict[ScenarioType, str] = {
    ScenarioType.EXTREME_RAIN: "chuva extrema",
    ScenarioType.HEAT_WAVE: "onda de calor",
}


def _pt_br(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _factor_sort_key(item: tuple[str, float]) -> float:
    return -item[1]


def _price(
    city: CityModel,
    region_id: str,
    intervention_type: InterventionType,
    scenario: ScenarioParams,
    affected_population: int,
) -> float:
    """Cost of one intervention on one region, from the shared cost model."""
    from app.engine.interventions import DEFAULTS

    region = next(r for r in city.regions if r.id == region_id)
    cost, _ = cost_for(
        intervention_type,
        region,
        scenario.intensity,
        affected_population,
        DEFAULTS[intervention_type],
    )
    return cost


def _expected_effect(
    city: CityModel,
    scenario: ScenarioParams,
    result: SimulationResult,
    region_id: str,
    intervention_type: InterventionType,
) -> dict[str, float | str]:
    """Re-run the engine with the suggested intervention instead of guessing."""
    from app.engine.interventions import DEFAULTS, place

    region = next(r for r in city.regions if r.id == region_id)
    candidate = place(
        intervention_type,
        region_id,
        region.centroid,
        DEFAULTS[intervention_type],
        index=len(result.interventions) + 1,
    )
    trial_interventions = [*result.interventions, candidate]
    diff = compare(city, scenario, trial_interventions)
    return {
        "affected_population_delta": int(diff.delta.affected_population),
        "affected_population_delta_pct": diff.delta.affected_population_pct,
        "compromised_roads_delta": int(diff.delta.compromised_roads),
        "region_risk_after": next(
            row["risk_after"] for row in diff.per_region if row["region_id"] == region_id
        ),
        "basis": (
            f"projeção do motor para {INTERVENTION_LABELS[intervention_type]} "
            f"(fator {DEFAULTS[intervention_type]:.2f}) em {region.name}"
        ),
    }


def _brl(value: float) -> str:
    """Money as the user reads it, not as a float."""
    if value >= 1_000_000:
        return f"{value / 1_000_000:,.1f} mi".replace(".", ",")
    if value >= 1_000:
        return f"{value / 1_000:,.0f} mil".replace(".", ",")
    return f"{value:,.0f}".replace(".", ",")


def _fit_to_budget(
    city: CityModel,
    scenario: ScenarioParams,
    result: SimulationResult,
    region_id: str,
    suggestion: InterventionType,
    budget_brl: float | None,
) -> tuple[InterventionType, float, str]:
    """Keep the suggestion if it is affordable, else name what the budget buys.

    The rule-based suggestion is deliberately not replaced silently. If it does
    not fit, the user is told both the price they would need and which cheaper
    work the same budget does buy in the same region, because a recommendation
    that quietly swaps the project is not a recommendation.
    """
    region_result = next(r for r in result.regions if r.region_id == region_id)
    # Always price against the exposure the engine reported for this region. The
    # people-serving types size on it, so a price built on anything else would
    # not be the same number once a budget arrives.
    suggested_cost = _price(
        city, region_id, suggestion, scenario, region_result.affected_population
    )
    if budget_brl is None:
        return suggestion, suggested_cost, ""

    if suggested_cost <= budget_brl:
        return suggestion, suggested_cost, ""

    affordable: list[tuple[float, float, InterventionType]] = []
    for candidate in InterventionType:
        if candidate is suggestion:
            continue
        cost = _price(city, region_id, candidate, scenario, region_result.affected_population)
        if cost <= budget_brl:
            gain = _expected_effect(city, scenario, result, region_id, candidate)[
                "affected_population_delta"
            ]
            affordable.append((float(gain) / cost, cost, candidate))

    if not affordable:
        cheapest = min(
            (
                _price(city, region_id, c, scenario, region_result.affected_population),
                c,
            )
            for c in InterventionType
        )
        note = (
            f"O orçamento de R$ {_brl(budget_brl)} não cobre nenhuma intervenção "
            f"nesta região. A mais barata é {INTERVENTION_LABELS[cheapest[1]]} a "
            f"R$ {_brl(cheapest[0])}. Use OTIMIZAR para montar um portfólio dentro do orçamento."
        )
        return suggestion, suggested_cost, note

    _, cost, best = max(affordable, key=lambda item: item[0])
    note = (
        f"A sugestão habitual ({INTERVENTION_LABELS[suggestion]}) custa "
        f"R$ {_brl(suggested_cost)} e ultrapassa o orçamento de R$ {_brl(budget_brl)}. "
        f"Com esse valor, a alternativa mais eficiente na mesma região é "
        f"{INTERVENTION_LABELS[best]} por R$ {_brl(cost)}. "
        f"Use OTIMIZAR para comparar o portfólio completo."
    )
    return best, cost, note


def _build_recommendation(
    city: CityModel,
    scenario: ScenarioParams,
    result: SimulationResult,
    budget_brl: float | None = None,
) -> tuple[CopilotRecommendation, str]:
    regions = {r.id: r for r in city.regions}
    scored: list[tuple[str, float, list[CopilotFactor]]] = []

    for region_result in result.regions:
        region = regions[region_result.region_id]
        factors = sorted(region_result.factors.items(), key=_factor_sort_key)
        top = factors[:4]
        weight_total = sum(w for _, w in top) or 1.0
        copilot_factors = [
            CopilotFactor(
                label=key,
                weight=round(weight / weight_total, 3),
                detail=FACTOR_DETAIL.get(key, FACTOR_LABELS.get(key, key)),
            )
            for key, weight in top
        ]
        priority = (
            region_result.risk * 0.45
            + region_result.affected_population / max(1, region.metrics.population) * 0.3
            + (region_result.critical_facilities_affected * 0.08)
            + min(0.15, region.metrics.historical_events * 0.015)
        )
        scored.append((region.id, priority, copilot_factors))

    scored.sort(key=lambda item: -item[1])
    top_region_id, top_priority, top_factors = scored[0]
    top_region = regions[top_region_id]
    top_result = next(r for r in result.regions if r.region_id == top_region_id)

    factor_keys = {f.label for f in top_factors}
    suggestion = _SUGGESTION_RULES[scenario.type][-1][1]
    for keys, candidate in _SUGGESTION_RULES[scenario.type]:
        if factor_keys & set(keys):
            suggestion = candidate
            break

    suggestion, cost_brl, budget_note = _fit_to_budget(
        city,
        scenario,
        result,
        top_region_id,
        suggestion,
        budget_brl,
    )

    expected = _expected_effect(city, scenario, result, top_region_id, suggestion)

    factor_lines = "\n".join(f"• {f.detail} (peso {f.weight:.2f})" for f in top_factors)
    answer = (
        f"Maior concentração de risco: {top_region.name}\n\n"
        f"Principais fatores:\n{factor_lines}\n\n"
        f"Intervenção sugerida: {INTERVENTION_LABELS[suggestion]}\n"
        f"Custo estimado: R$ {_brl(cost_brl)}"
        + (f" (orçamento de R$ {_brl(budget_brl)})" if budget_brl else "")
        + "\n\n"
        + (f"{budget_note}\n\n" if budget_note else "")
        + "Esta é uma hipótese do modelo. Use SIMULAR para medir o efeito real no cenário."
    )
    headline = (
        f"{top_region.name} concentra o maior risco "
        f"({top_result.risk_level.value}, risco {top_result.risk:.2f})"
    )
    affected = _pt_br(top_result.affected_population)
    rationale = (
        f"A região apresenta {affected} pessoas potencialmente afetadas, "
        f"{top_result.compromised_roads} vias comprometidas e "
        f"{top_result.critical_facilities_affected} equipamento(s) crítico(s) exposto(s) "
        f"no cenário de {_SCENARIO_LABELS[scenario.type]} com intensidade {scenario.intensity:.0%} "
        f"e duração {scenario.duration:.0%}. "
        f"Os fatores de maior peso são {_describe(top_factors)}."
    )

    return CopilotRecommendation(
        region_id=top_region_id,
        region_name=top_region.name,
        priority_score=round(top_priority, 3),
        headline=headline,
        factors=top_factors,
        suggested_intervention=suggestion,
        rationale=rationale,
        estimated_cost_brl=cost_brl,
        expected_effect=expected,
        source="heuristic",
    ), answer


def _describe(factors: list[CopilotFactor]) -> str:
    return ", ".join(
        FACTOR_DETAIL.get(f.label, FACTOR_LABELS.get(f.label, f.label)) for f in factors[:3]
    )


def _context(
    city: CityModel,
    scenario: ScenarioParams,
    result: SimulationResult,
    interventions: list[Intervention],
    recommendation: CopilotRecommendation | None = None,
) -> str:
    regions = {r.id: r for r in city.regions}
    rows = []
    for region_result in sorted(result.regions, key=lambda r: -r.risk):
        region = regions[region_result.region_id]
        rows.append(
            {
                "region_id": region.id,
                "name": region.name,
                "population": region.metrics.population,
                "impermeability": region.metrics.impermeability,
                "vegetation_index": region.metrics.vegetation_index,
                "vulnerability": region.metrics.vulnerability,
                "flood_risk": region.metrics.flood_risk,
                "heat_exposure": region.metrics.heat_exposure,
                "road_count": region.road_count,
                "facilities": [
                    {"name": f.name, "type": f.type.value, "critical": f.critical}
                    for f in region.facilities
                ],
                "risk": region_result.risk,
                "risk_level": region_result.risk_level.value,
                "affected_population": region_result.affected_population,
                "compromised_roads": region_result.compromised_roads,
                "critical_facilities_affected": region_result.critical_facilities_affected,
                "factors": region_result.factors,
            }
        )

    return json.dumps(
        {
            "scenario": scenario.model_dump(),
            "totals": result.totals.model_dump(),
            "interventions": [i.model_dump() for i in interventions],
            "cost_assumptions": ASSUMPTION_NOTICE,
            "recommendation": recommendation.model_dump() if recommendation else None,
            "regions": rows,
        },
        ensure_ascii=False,
    )


def _call_llm(prompt: str) -> dict[str, Any] | None:
    api_key = os.getenv("URBAN_COPILOT_API_KEY")
    if not api_key:
        return None
    base_url = os.getenv("URBAN_COPILOT_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("URBAN_COPILOT_MODEL", "gpt-4o-mini")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": RESPONSE_SCHEMA,
        },
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
        return json.loads(body["choices"][0]["message"]["content"])
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError, json.JSONDecodeError):
        return None


def _coerce_llm_output(
    raw: dict[str, Any],
    city: CityModel,
    scenario: ScenarioParams,
    fallback: CopilotRecommendation,
) -> CopilotResponse:
    regions = {r.id: r for r in city.regions}
    requested = raw.get("region_id")
    region_id: str = (
        requested if isinstance(requested, str) and requested in regions else fallback.region_id
    )
    region = regions[region_id]

    try:
        suggestion = InterventionType(raw["suggested_intervention"])
    except (KeyError, ValueError):
        suggestion = fallback.suggested_intervention

    factors: list[CopilotFactor] = []
    for item in raw.get("factors", []) or []:
        try:
            factors.append(
                CopilotFactor(
                    label=str(item["label"])[:64],
                    weight=float(item.get("weight", 0.0)),
                    detail=str(item.get("detail", ""))[:240],
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not factors:
        factors = fallback.factors

    recommendation = CopilotRecommendation(
        region_id=region_id,
        region_name=region.name,
        priority_score=float(
            raw.get("priority_score", fallback.priority_score) or fallback.priority_score
        ),
        headline=str(raw.get("headline", fallback.headline))[:200],
        factors=factors[:5],
        suggested_intervention=suggestion,
        rationale=str(raw.get("rationale", fallback.rationale))[:1200],
        expected_effect=fallback.expected_effect,
        source="llm",
    )
    answer = str(raw.get("answer") or fallback.rationale)[:2000]
    follow_ups = [str(q)[:160] for q in (raw.get("follow_up_questions") or FOLLOW_UPS)][:4]
    return CopilotResponse(analysis=recommendation, answer=answer, follow_up_questions=follow_ups)


def analyze(city: CityModel, request: CopilotRequest) -> CopilotResponse:
    scenario = request.scenario
    result = run_simulation(
        city, scenario, request.interventions, "mitigated" if request.interventions else "baseline"
    )
    recommendation, heuristic_answer = _build_recommendation(
        city, scenario, result, request.budget_brl
    )
    comparison = compare(city, scenario, request.interventions) if request.interventions else None

    prompt_parts = [
        f"Pergunta do usuário: {request.question}",
        "Contexto da simulação (JSON):",
        _context(city, scenario, result, request.interventions, recommendation),
    ]
    if request.budget_brl is not None:
        prompt_parts.append(
            f"Orçamento disponível do usuário: R$ {_brl(request.budget_brl)}. "
            f"A sugestão regional custa R$ {_brl(recommendation.estimated_cost_brl)} "
            "e esses valores são hipóteses de custo, não cotações. "
            "Se a sugestão não couber, diga isso e aponte a alternativa mais "
            "eficiente dentro do orçamento em vez de trocar a obra em silêncio."
        )
    if comparison is not None:
        prompt_parts.append(
            "Efeito das intervenções já inseridas (antes -> depois): "
            + json.dumps(
                {
                    "affected_population": [
                        comparison.baseline.affected_population,
                        comparison.mitigated.affected_population,
                    ],
                    "compromised_roads": [
                        comparison.baseline.compromised_roads,
                        comparison.mitigated.compromised_roads,
                    ],
                },
                ensure_ascii=False,
            )
        )
    prompt_parts.append(
        "Responda priorizando a região com maior risco. "
        "Níveis de risco: high >= 0.62, moderate >= 0.34, low < 0.34."
    )

    raw = _call_llm("\n\n".join(prompt_parts))
    if raw is not None:
        return _coerce_llm_output(raw, city, scenario, recommendation)

    return CopilotResponse(
        analysis=recommendation,
        answer=heuristic_answer,
        follow_up_questions=FOLLOW_UPS,
    )
