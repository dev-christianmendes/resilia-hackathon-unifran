import { describe, expect, it } from 'vitest'
import { city, intervention, result } from '../test/fixtures'
import { initialState, interventionsEqual, isStale, reducer, type AppState } from './appState'

function withCity(): AppState {
  return reducer(initialState, { type: 'loadCity', value: city() })
}

describe('reducer', () => {
  it('loadCity resets state but keeps the chosen scenario', () => {
    const dirty: AppState = {
      ...initialState,
      scenario: { type: 'heat_wave', intensity: 0.3, duration: 0.2 },
      interventions: [intervention('a')],
      stage: 'mitigate',
    }
    const next = reducer(dirty, { type: 'loadCity', value: city() })
    expect(next.city?.name).toBe('Franca')
    expect(next.scenario.type).toBe('heat_wave')
    expect(next.interventions).toEqual([])
    expect(next.stage).toBe('observe')
  })

  it('clamps intensity and duration to [0, 1]', () => {
    let state = reducer(initialState, { type: 'setIntensity', value: 1.7 })
    state = reducer(state, { type: 'setDuration', value: -0.4 })
    expect(state.scenario.intensity).toBe(1)
    expect(state.scenario.duration).toBe(0)
  })

  it('setScenarioType clears a previous error', () => {
    const state = reducer({ ...initialState, error: 'falhou' }, { type: 'setScenarioType', value: 'wildfire' })
    expect(state.scenario.type).toBe('wildfire')
    expect(state.error).toBeNull()
  })

  it('a run without interventions becomes the baseline and moves to simulate', () => {
    const run = result()
    const state = reducer(withCity(), { type: 'runSimulation', result: run })
    expect(state.baseline).toBe(run)
    expect(state.current).toBe(run)
    expect(state.stage).toBe('simulate')
  })

  it('a mitigated run keeps the existing baseline', () => {
    const baseline = result()
    const mitigated = result([intervention('a')])
    let state = reducer(withCity(), { type: 'runSimulation', result: baseline })
    state = reducer(state, { type: 'runSimulation', result: mitigated })
    expect(state.baseline).toBe(baseline)
    expect(state.current).toBe(mitigated)
    expect(state.stage).toBe('mitigate')
  })

  it('adding an intervention moves to mitigate; removing it keeps the others', () => {
    let state = reducer(withCity(), { type: 'addIntervention', value: intervention('a') })
    state = reducer(state, { type: 'addIntervention', value: intervention('b') })
    expect(state.stage).toBe('mitigate')
    state = reducer(state, { type: 'removeIntervention', id: 'a' })
    expect(state.interventions.map((i) => i.id)).toEqual(['b'])
  })

  it('blocks stages whose prerequisites are missing', () => {
    expect(reducer(initialState, { type: 'setStage', value: 'simulate' }).stage).toBe('observe')
    expect(reducer(withCity(), { type: 'setStage', value: 'simulate' }).stage).toBe('simulate')
    expect(reducer(withCity(), { type: 'setStage', value: 'mitigate' }).stage).toBe('observe')
    expect(reducer(withCity(), { type: 'setStage', value: 'compare' }).stage).toBe('observe')
  })

  it('setError stops the busy indicator', () => {
    const state = reducer({ ...initialState, busy: true }, { type: 'setError', value: 'API fora do ar' })
    expect(state.busy).toBe(false)
    expect(state.error).toBe('API fora do ar')
  })

  it('placement sets the intervention being positioned and can be cancelled', () => {
    let state = reducer(withCity(), { type: 'startPlacement', value: intervention('p') })
    expect(state.placement?.id).toBe('p')
    expect(state.stage).toBe('mitigate')
    state = reducer(state, { type: 'cancelPlacement' })
    expect(state.placement).toBeNull()
  })

  it('reset keeps the city and scenario only', () => {
    let state = reducer(withCity(), { type: 'setIntensity', value: 0.95 })
    state = reducer(state, { type: 'addIntervention', value: intervention('a') })
    state = reducer(state, { type: 'reset' })
    expect(state.city).not.toBeNull()
    expect(state.scenario.intensity).toBe(0.95)
    expect(state.interventions).toEqual([])
  })
})

describe('interventionsEqual', () => {
  it('ignores order and the id assigned by the client', () => {
    const a = [intervention('1', { region_id: 'r1' }), intervention('2', { region_id: 'r2' })]
    const b = [intervention('x', { region_id: 'r2' }), intervention('y', { region_id: 'r1' })]
    expect(interventionsEqual(a, b)).toBe(true)
  })

  it('detects a changed impact factor or a different count', () => {
    expect(interventionsEqual([intervention('1')], [intervention('1', { impact_factor: 0.5 })])).toBe(false)
    expect(interventionsEqual([intervention('1')], [])).toBe(false)
  })
})

describe('isStale', () => {
  it('is false without a result', () => {
    expect(isStale(initialState)).toBe(false)
  })

  it('is true after the scenario changes', () => {
    let state = reducer(withCity(), { type: 'runSimulation', result: result() })
    expect(isStale(state)).toBe(false)
    state = reducer(state, { type: 'setIntensity', value: 0.95 })
    expect(isStale(state)).toBe(true)
  })

  it('is true after an intervention is added to a fresh result', () => {
    let state = reducer(withCity(), { type: 'runSimulation', result: result() })
    state = reducer(state, { type: 'addIntervention', value: intervention('a') })
    expect(isStale(state)).toBe(true)
  })
})
