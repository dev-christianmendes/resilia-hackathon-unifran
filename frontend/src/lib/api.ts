import type {
  City,
  CopilotResponse,
  Intervention,
  InterventionCatalogueItem,
  ScenarioParams,
  SimulationComparison,
  SimulationResult,
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

  simulate: (scenario: ScenarioParams, interventions: Intervention[]) =>
    request<SimulationResult>('/api/simulate', {
      method: 'POST',
      body: JSON.stringify({ scenario, interventions }),
    }),

  compare: (scenario: ScenarioParams, interventions: Intervention[]) =>
    request<SimulationComparison>('/api/compare', {
      method: 'POST',
      body: JSON.stringify({ scenario, interventions }),
    }),

  copilot: (scenario: ScenarioParams, interventions: Intervention[], question: string) =>
    request<CopilotResponse>('/api/copilot', {
      method: 'POST',
      body: JSON.stringify({ scenario, interventions, question }),
    }),
}
