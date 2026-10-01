import type {
  City,
  CopilotResponse,
  CostCatalogueItem,
  Intervention,
  InterventionCatalogueItem,
  OptimizeResponse,
  RunResponse,
  ScenarioParams,
} from '../types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const detail = await response.text().catch(() => '')
    throw new Error(`API ${response.status} em ${path}${detail ? `: ${detail.slice(0, 200)}` : ''}`)
  }
  return (await response.json()) as T
}

export const api = {
  city: () => request<City>('/api/city'),

  catalogue: () => request<InterventionCatalogueItem[]>('/api/interventions/catalogue'),

  /**
   * Baseline and mitigated in one call. Two separate calls could answer out of
   * order and leave the panel showing a mitigated result beside a baseline from
   * a different scenario.
   */
  run: (scenario: ScenarioParams, interventions: Intervention[], budget?: number) =>
    request<RunResponse>('/api/run', {
      method: 'POST',
      body: JSON.stringify({
        scenario,
        interventions,
        ...(budget === undefined ? {} : { budget_brl: budget }),
      }),
    }),

  optimize: (
    scenario: ScenarioParams,
    budget: number,
    maxInterventions?: number,
    allowedTypes?: Intervention['type'][],
  ) =>
    request<OptimizeResponse>('/api/optimize', {
      method: 'POST',
      body: JSON.stringify({
        scenario,
        budget_brl: budget,
        ...(maxInterventions === undefined ? {} : { max_interventions: maxInterventions }),
        ...(allowedTypes ? { allowed_types: allowedTypes } : {}),
      }),
    }),

  costs: () => request<CostCatalogueItem[]>('/api/costs/catalogue'),

  copilot: (
    scenario: ScenarioParams,
    interventions: Intervention[],
    question: string,
    budget?: number,
  ) =>
    request<CopilotResponse>('/api/copilot', {
      method: 'POST',
      body: JSON.stringify({
        scenario,
        interventions,
        question,
        ...(budget === undefined ? {} : { budget_brl: budget }),
      }),
    }),
}
