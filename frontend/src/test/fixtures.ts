import type {
  City,
  Intervention,
  Point,
  Region,
  SimulationComparison,
  SimulationResult,
  SimulationTotals,
} from '../types'

export function point(x: number, y: number): Point {
  return { x, y, lat: null, lng: null }
}

export function square(id: string, name: string, x0: number, y0: number, size = 100): Region {
  return {
    id,
    name,
    polygon: [point(x0, y0), point(x0 + size, y0), point(x0 + size, y0 + size), point(x0, y0 + size)],
    centroid: point(x0 + size / 2, y0 + size / 2),
    metrics: {
      population: 1000,
      population_density: 10,
      vegetation_index: 0.3,
      impermeability: 0.6,
      drainage_clogging: 0.2,
      flood_risk: 0.4,
      heat_exposure: 0.5,
      elevation_m: 1000,
      vulnerability: 0.4,
      historical_events: 1,
    },
    road_count: 3,
    facilities: [],
  }
}

export function city(regions: Region[] = [square('r1', 'Centro', 0, 0)]): City {
  return {
    id: 'franca',
    name: 'Franca',
    bounds: { min_x: 0, max_x: 100, min_y: 0, max_y: 100 },
    boundary: [],
    regions,
    roads: [],
    waterways: [],
    vulnerability_points: [],
    buildings: [],
    trees: [],
  }
}

export function intervention(id: string, overrides: Partial<Intervention> = {}): Intervention {
  return {
    id,
    type: 'reservoir',
    region_id: 'r1',
    location: point(10, 20),
    impact_factor: 0.8,
    ...overrides,
  }
}

export function totals(overrides: Partial<SimulationTotals> = {}): SimulationTotals {
  return {
    affected_population: 100_000,
    compromised_roads: 200,
    critical_facilities_affected: 10,
    high_risk_regions: 4,
    population_exposure_index: 0.5,
    service_pressure_index: 0.4,
    ...overrides,
  }
}

export function result(interventions: Intervention[] = [], overrides: Partial<SimulationResult> = {}): SimulationResult {
  return {
    id: `run-${interventions.length}`,
    scenario: { type: 'extreme_rain', intensity: 0.8, duration: 0.6 },
    interventions,
    label: interventions.length > 0 ? 'mitigated' : 'baseline',
    totals: totals(),
    regions: [],
    ...overrides,
  }
}

export function comparison(): SimulationComparison {
  return {
    scenario: { type: 'extreme_rain', intensity: 0.95, duration: 0.9 },
    baseline: totals({ affected_population: 200_000, compromised_roads: 300, critical_facilities_affected: 12 }),
    mitigated: totals({ affected_population: 150_000, compromised_roads: 150, critical_facilities_affected: 9 }),
    delta: {
      affected_population: -50_000,
      affected_population_pct: -25,
      compromised_roads: -150,
      compromised_roads_pct: -50,
      critical_facilities_affected: -3,
      critical_facilities_affected_pct: -25,
      service_pressure_index: -0.1,
    },
    per_region: [
      {
        region_id: 'r1',
        region_name: 'Centro',
        risk_before: 0.8,
        risk_after: 0.5,
        affected_before: 20_000,
        affected_after: 12_000,
        delta_pct: -40,
      },
    ],
  }
}
