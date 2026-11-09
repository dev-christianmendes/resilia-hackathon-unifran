import { describe, expect, it } from 'vitest'
import { square } from '../test/fixtures'
import type { RegionResult } from '../types'
import { LABEL_DEPTH_M, MAX_LABELS, labelRegions, labelWidthM } from './labels'

function risk(id: string, value: number): RegionResult {
  return {
    region_id: id,
    risk: value,
    risk_level: value > 0.62 ? 'high' : 'moderate',
    baseline_risk: value,
    affected_population: 0,
    compromised_roads: 0,
    critical_facilities_affected: 0,
    factors: {},
    mitigations_applied: [],
  }
}

const ids = (list: { id: string }[]) => list.map((region) => region.id)

describe('labelWidthM', () => {
  it('grows with the name', () => {
    expect(labelWidthM('Córrego do Matadouro Velho · Área 046')).toBeGreaterThan(labelWidthM('Curso sem nome · Área 036'))
  })
})

describe('labelRegions', () => {
  const far = 50_000

  it('labels the riskiest regions first', () => {
    const regions = [square('a', 'A', 0, 0), square('b', 'B', far, 0), square('c', 'C', far * 2, 0)]
    const results = { a: risk('a', 0.3), b: risk('b', 0.9), c: risk('c', 0.6) }
    expect(ids(labelRegions(regions, results, null, null))).toEqual(['b', 'c', 'a'])
  })

  it('skips a card that would overlap a riskier one (real case: Cubatão 001 × 039)', () => {
    const regions = [square('001', 'Córrego Cubatão · Área 001', 0, 0), square('039', 'Córrego Cubatão · Área 039', 1314, 694)]
    const results = { '001': risk('001', 0.72), '039': risk('039', 0.7) }
    expect(ids(labelRegions(regions, results, null, null))).toEqual(['001'])
  })

  it('uses the card width: a long name collides where a short one fits (real case: Bagres 041 × Matadouro 046)', () => {
    // 5.1 km across, 1.5 km in depth: the long Matadouro card still reached the Bagres card.
    const bagres = square('041', 'Córrego dos Bagres · Área 041', 5067, 0)
    const results = { '041': risk('041', 0.72), long: risk('long', 0.63), short: risk('short', 0.63) }
    const long = square('long', 'Córrego do Matadouro Velho · Área 046', 0, 1535)
    const short = square('short', 'Mata · 1', 0, 1535)
    expect(ids(labelRegions([bagres, long], results, null, null))).toEqual(['041'])
    expect(ids(labelRegions([bagres, short], results, null, null))).toEqual(['041', 'short'])
  })

  it('keeps cards that are apart in depth', () => {
    const regions = [square('a', 'A', 0, 0), square('b', 'B', 0, LABEL_DEPTH_M + 1)]
    const results = { a: risk('a', 0.9), b: risk('b', 0.8) }
    expect(ids(labelRegions(regions, results, null, null))).toEqual(['a', 'b'])
  })

  it('measures the text the card shows, not the raw region name', () => {
    const regions = [square('a', 'A', 0, 0), square('b', 'B', 2500, 0)]
    const results = { a: risk('a', 0.9), b: risk('b', 0.8) }
    expect(ids(labelRegions(regions, results, null, null))).toEqual(['a', 'b'])
    const shown = (region: { id: string }) => `Córrego com nome comprido · Área ${region.id}`
    expect(ids(labelRegions(regions, results, null, null, shown))).toEqual(['a'])
  })

  it('always labels the selected and hovered regions, even when they overlap', () => {
    const regions = [square('top', 'A', 0, 0), square('sel', 'B', 10, 10), square('hov', 'C', 20, 20)]
    const results = { top: risk('top', 0.9), sel: risk('sel', 0.1), hov: risk('hov', 0.1) }
    expect(ids(labelRegions(regions, results, 'sel', 'hov'))).toEqual(['sel', 'hov'])
  })

  it(`never shows more than ${MAX_LABELS} automatic labels`, () => {
    const regions = Array.from({ length: 10 }, (_, i) => square(`r${i}`, `R${i}`, i * far, 0))
    const results = Object.fromEntries(regions.map((region, i) => [region.id, risk(region.id, 1 - i / 10)]))
    expect(labelRegions(regions, results, null, null)).toHaveLength(MAX_LABELS)
  })
})
