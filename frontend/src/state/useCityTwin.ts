import { useCallback, useEffect, useMemo, useReducer, useState } from 'react'
import { api } from '../lib/api'
import { DEFAULT_BUDGET_BRL, DEFAULT_LAYERS, LAYER_PRESETS } from '../lib/theme'
import type {
  CopilotRecommendation,
  Intervention,
  InterventionType,
  LayerKey,
  CostCatalogueRow,
  OptimizeResponse,
  Point,
  RegionResult,
  ScenarioType,
  Stage,
} from '../types'
import { initialState, isStale, reducer } from './appState'

export interface CopilotState {
  loading: boolean
  answer: string | null
  analysis: CopilotRecommendation | null
  followUps: string[]
  source: 'llm' | 'heuristic' | null
  question: string
}

const initialCopilot: CopilotState = {
  loading: false,
  answer: null,
  analysis: null,
  followUps: [],
  source: null,
  question: '',
}

export interface OptimizerState {
  loading: boolean
  result: OptimizeResponse | null
  error: string | null
}

const initialOptimizer: OptimizerState = { loading: false, result: null, error: null }

export function useCityTwin() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>(DEFAULT_LAYERS)
  const [copilot, setCopilot] = useState<CopilotState>(initialCopilot)
  const [budget, setBudget] = useState<number>(DEFAULT_BUDGET_BRL)
  const [optimizer, setOptimizer] = useState<OptimizerState>(initialOptimizer)
  const [costs, setCosts] = useState<CostCatalogueRow[]>([])

  useEffect(() => {
    let cancelled = false
    void api
      .city()
      .then((city) => {
        if (!cancelled) dispatch({ type: 'loadCity', value: city })
      })
      .catch((error: unknown) => {
        if (!cancelled) dispatch({ type: 'setError', value: describeError(error) })
      })
    // The price table is a reference, not a result: a failure here must not
    // block the city itself.
    void api
      .costs()
      .then((rows) => {
        if (!cancelled) setCosts(rows)
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const runSimulation = useCallback(
    async (interventions?: Intervention[]) => {
      const active = interventions ?? state.interventions
      dispatch({ type: 'setBusy', value: true })
      dispatch({ type: 'setError', value: null })
      try {
        const run = await api.run(state.scenario, active, budget ?? undefined)
        dispatch({ type: 'runSimulation', result: run.mitigated })
        // With nothing placed there is no comparison to show; an all-zero
        // panel would only invite the reader to compare nothing with nothing.
        dispatch({ type: 'setComparison', value: active.length === 0 ? null : run.comparison })
        dispatch({ type: 'setRunTotals', value: run })
      } catch (error) {
        dispatch({ type: 'setError', value: describeError(error) })
      } finally {
        dispatch({ type: 'setBusy', value: false })
      }
    },
    [budget, state.scenario, state.interventions],
  )

  const addIntervention = useCallback(
    (
      type: InterventionType,
      location: Point,
      regionId: string,
      impactFactor: number,
    ): Intervention => {
      const intervention: Intervention = {
        id: `int-${type}-${Date.now()}`,
        type,
        region_id: regionId,
        location,
        impact_factor: impactFactor,
      }
      dispatch({ type: 'addIntervention', value: intervention })
      return intervention
    },
    [],
  )

  const removeIntervention = useCallback((id: string) => {
    dispatch({ type: 'removeIntervention', id })
  }, [])

  const setInterventions = useCallback((value: Intervention[]) => {
    dispatch({ type: 'setInterventions', value })
  }, [])

  const askCopilot = useCallback(
    async (question: string) => {
      setCopilot((prev) => ({ ...prev, loading: true, question }))
      try {
        const response = await api.copilot(
          state.scenario,
          state.interventions,
          question,
          budget,
        )
        setCopilot({
          loading: false,
          answer: response.answer,
          analysis: response.analysis,
          followUps: response.follow_up_questions,
          source: response.analysis.source,
          question,
        })
      } catch (error) {
        setCopilot((prev) => ({
          ...prev,
          loading: false,
          answer: `Não consegui consultar o Urban Copilot: ${describeError(error)}`,
        }))
      }
    },
    [budget, state.scenario, state.interventions],
  )

  const applySuggestion = useCallback((): Intervention | null => {
    const suggestion = copilot.analysis
    const city = state.city
    if (!suggestion || !city) return null
    const region = city.regions.find((r) => r.id === suggestion.region_id)
    if (!region) return null
    return addIntervention(suggestion.suggested_intervention, region.centroid, region.id, 0.75)
  }, [copilot.analysis, state.city, addIntervention])

  /**
   * Ask the engine for the portfolio that buys the most protected people for
   * the budget, then show it for review. Nothing is applied without the user
   * seeing it first.
   */
  const optimize = useCallback(
    async (maxInterventions?: number) => {
      setOptimizer((prev) => ({ ...prev, loading: true, error: null }))
      try {
        const result = await api.optimize(state.scenario, budget, maxInterventions)
        setOptimizer({ loading: false, result, error: null })
        return result
      } catch (error) {
        const message = describeError(error)
        setOptimizer({ loading: false, result: null, error: message })
        return null
      }
    },
    [budget, state.scenario],
  )

  const applyOptimizerResult = useCallback(() => {
    const selected = optimizer.result?.selected ?? []
    if (selected.length === 0) return
    setInterventions(
      selected.map((proposal, index) => ({
        id: `int-opt-${index}-${proposal.region_id}-${proposal.type}`,
        type: proposal.type,
        region_id: proposal.region_id,
        location: proposal.location,
        impact_factor: proposal.impact_factor,
      })),
    )
  }, [optimizer.result, setInterventions])

  const reset = useCallback(() => {
    dispatch({ type: 'reset' })
    setCopilot(initialCopilot)
    setOptimizer(initialOptimizer)
  }, [])

  const setScenarioType = useCallback((type: ScenarioType) => {
    dispatch({ type: 'setScenarioType', value: type })
  }, [])

  const setIntensity = useCallback((value: number) => {
    dispatch({ type: 'setIntensity', value })
  }, [])

  const setDuration = useCallback((value: number) => {
    dispatch({ type: 'setDuration', value })
  }, [])

  const setStage = useCallback((stage: Stage) => {
    dispatch({ type: 'setStage', value: stage })
  }, [])

  const selectRegion = useCallback((id: string | null) => {
    dispatch({ type: 'selectRegion', id })
  }, [])

  const startPlacement = useCallback((intervention: Intervention) => {
    dispatch({ type: 'startPlacement', value: intervention })
  }, [])

  const cancelPlacement = useCallback(() => {
    dispatch({ type: 'cancelPlacement' })
  }, [])

  const toggleLayer = useCallback((key: LayerKey) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }))
  }, [])

  const setLayerPreset = useCallback((name: string) => {
    const preset = LAYER_PRESETS[name]
    if (preset) setLayers(preset)
  }, [])

  const selectedRegion = useMemo(
    () => state.city?.regions.find((r) => r.id === state.selectedRegionId) ?? null,
    [state.city, state.selectedRegionId],
  )

  const selectedResult =
    state.current?.regions.find((r) => r.region_id === state.selectedRegionId) ?? null

  const regionResults = state.current?.regions
  const resultsByRegion = useMemo(() => {
    const map: Record<string, RegionResult> = {}
    for (const regionResult of regionResults ?? []) map[regionResult.region_id] = regionResult
    return map
  }, [regionResults])

  return {
    state,
    city: state.city,
    selectedRegion,
    selectedResult,
    resultsByRegion,
    stale: isStale(state),
    layers,
    copilot,
    budget,
    setBudget,
    optimizer,
    optimize,
    applyOptimizerResult,
    costs,
    actions: {
      runSimulation,
      addIntervention,
      removeIntervention,
      setInterventions,
      askCopilot,
      applySuggestion,
      reset,
      setScenarioType,
      setIntensity,
      setDuration,
      setStage,
      selectRegion,
      startPlacement,
      cancelPlacement,
      toggleLayer,
      setLayerPreset,
    } satisfies Record<string, unknown>,
  }
}

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
