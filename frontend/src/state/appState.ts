import type {
  City,
  Intervention,
  RunResponse,
  ScenarioParams,
  SimulationComparison,
  SimulationResult,
  Stage,
} from '../types'

export type Action =
  | { type: 'loadCity'; value: City }
  | { type: 'setScenarioType'; value: ScenarioParams['type'] }
  | { type: 'setIntensity'; value: number }
  | { type: 'setDuration'; value: number }
  | { type: 'runSimulation'; result: SimulationResult }
  | { type: 'addIntervention'; value: Intervention }
  | { type: 'setInterventions'; value: Intervention[] }
  | { type: 'removeIntervention'; id: string }
  | { type: 'setComparison'; value: SimulationComparison | null }
  | { type: 'setRunTotals'; value: RunResponse }
  | { type: 'setStage'; value: Stage }
  | { type: 'selectRegion'; id: string | null }
  | { type: 'startPlacement'; value: Intervention }
  | { type: 'cancelPlacement' }
  | { type: 'setBusy'; value: boolean }
  | { type: 'setError'; value: string | null }
  | { type: 'reset' }

export interface AppState {
  city: City | null
  scenario: ScenarioParams
  /** Last run without interventions — the "antes" of the comparison. */
  baseline: SimulationResult | null
  /** Last run shown in the 3D scene, with or without interventions. */
  current: SimulationResult | null
  /** Cost and budget verdict of the last /api/run, shown next to the result. */
  runTotals: RunResponse | null
  interventions: Intervention[]
  comparison: SimulationComparison | null
  stage: Stage
  selectedRegionId: string | null
  /** Intervention being positioned on the map, if any. */
  placement: Intervention | null
  error: string | null
  busy: boolean
}

export const initialState: AppState = {
  city: null,
  scenario: { type: 'extreme_rain', intensity: 0.8, duration: 0.6 },
  baseline: null,
  current: null,
  runTotals: null,
  interventions: [],
  comparison: null,
  stage: 'observe',
  selectedRegionId: null,
  placement: null,
  error: null,
  busy: false,
}

function stageFor(interventions: Intervention[], hasResult: boolean): Stage {
  if (interventions.length > 0) return 'mitigate'
  return hasResult ? 'simulate' : 'observe'
}

function canEnterStage(state: AppState, stage: Stage): boolean {
  if (stage === 'observe') return true
  if (stage === 'simulate') return Boolean(state.city)
  if (stage === 'mitigate') return Boolean(state.current)
  return Boolean(state.comparison)
}

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'loadCity':
      return {
        ...initialState,
        city: action.value,
        scenario: state.scenario,
        selectedRegionId: null,
      }

    case 'setScenarioType':
      return { ...state, scenario: { ...state.scenario, type: action.value }, error: null }

    case 'setIntensity':
      return { ...state, scenario: { ...state.scenario, intensity: clamp01(action.value) } }

    case 'setDuration':
      return { ...state, scenario: { ...state.scenario, duration: clamp01(action.value) } }

    case 'runSimulation': {
      const mitigated = action.result.interventions.length > 0
      return {
        ...state,
        current: action.result,
        baseline: mitigated ? (state.baseline ?? action.result) : action.result,
        stage: mitigated ? 'mitigate' : 'simulate',
        error: null,
      }
    }

    case 'addIntervention': {
      const interventions = [...state.interventions, action.value]
      return { ...state, interventions, stage: stageFor(interventions, Boolean(state.current)) }
    }

    case 'setInterventions':
      return { ...state, interventions: action.value }

    case 'removeIntervention': {
      const interventions = state.interventions.filter((i) => i.id !== action.id)
      return { ...state, interventions }
    }

    case 'setComparison':
      return { ...state, comparison: action.value }

    case 'setRunTotals':
      return {
        ...state,
        runTotals: action.value,
        baseline: action.value.baseline,
      }

    case 'setStage':
      return canEnterStage(state, action.value) ? { ...state, stage: action.value } : state

    case 'selectRegion':
      return { ...state, selectedRegionId: action.id }

    case 'startPlacement':
      return { ...state, placement: action.value, stage: 'mitigate' }

    case 'cancelPlacement':
      return { ...state, placement: null }

    case 'setBusy':
      return { ...state, busy: action.value }

    case 'setError':
      return { ...state, error: action.value, busy: false }

    case 'reset':
      return { ...initialState, city: state.city, scenario: state.scenario }

    default:
      return state
  }
}

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value))
}

export function scenarioEquals(a: ScenarioParams, b: ScenarioParams): boolean {
  return a.type === b.type && a.intensity === b.intensity && a.duration === b.duration
}

/**
 * Identity of an intervention for staleness purposes. The engine fills in a
 * cost, so a field-by-field compare would report every result as stale.
 */
function interventionKey(intervention: Intervention): string {
  const { type, region_id, location, impact_factor } = intervention
  return `${type}|${region_id}|${location.x.toFixed(1)}|${location.y.toFixed(1)}|${impact_factor}`
}

export function interventionsEqual(a: Intervention[], b: Intervention[]): boolean {
  if (a.length !== b.length) return false
  const left = a.map(interventionKey).sort()
  const right = b.map(interventionKey).sort()
  return left.every((key, index) => key === right[index])
}

/**
 * True when the visible result no longer matches what is on screen.
 *
 * Both halves matter: a changed scenario invalidates the numbers, and so does
 * adding or removing an intervention, since the visible result is the
 * combination of the two.
 */
export function isStale(state: AppState): boolean {
  if (!state.current) return false
  if (!scenarioEquals(state.current.scenario, state.scenario)) return true
  return !interventionsEqual(state.current.interventions, state.interventions)
}
