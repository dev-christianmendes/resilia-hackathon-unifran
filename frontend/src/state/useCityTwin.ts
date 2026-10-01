import { useCallback, useEffect, useMemo, useReducer, useState } from 'react'
import { api } from '../lib/api'
import { DEFAULT_LAYERS } from '../lib/theme'
import type {
  CopilotRecommendation,
  Intervention,
  InterventionType,
  LayerKey,
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

export function useCityTwin() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>(DEFAULT_LAYERS)
  const [copilot, setCopilot] = useState<CopilotState>(initialCopilot)

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
        if (active.length === 0) {
          const baseline = await api.simulate(state.scenario, [])
          dispatch({ type: 'runSimulation', result: baseline })
          dispatch({ type: 'setComparison', value: null })
          return
        }
        const [result, comparison] = await Promise.all([
          api.simulate(state.scenario, active),
          api.compare(state.scenario, active),
        ])
        dispatch({ type: 'runSimulation', result })
        dispatch({ type: 'setComparison', value: comparison })
      } catch (error) {
        dispatch({ type: 'setError', value: describeError(error) })
      } finally {
        dispatch({ type: 'setBusy', value: false })
      }
    },
    [state.scenario, state.interventions],
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
        const response = await api.copilot(state.scenario, state.interventions, question)
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
    [state.scenario, state.interventions],
  )

  const applySuggestion = useCallback((): Intervention | null => {
    const suggestion = copilot.analysis
    const city = state.city
    if (!suggestion || !city) return null
    const region = city.regions.find((r) => r.id === suggestion.region_id)
    if (!region) return null
    return addIntervention(suggestion.suggested_intervention, region.centroid, region.id, 0.75)
  }, [copilot.analysis, state.city, addIntervention])

  const reset = useCallback(() => {
    dispatch({ type: 'reset' })
    setCopilot(initialCopilot)
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
    } satisfies Record<string, unknown>,
  }
}

function describeError(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}
