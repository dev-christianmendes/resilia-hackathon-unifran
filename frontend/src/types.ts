export type ScenarioType =
  | 'extreme_rain'
  | 'heat_wave'
  | 'hailstorm'
  | 'windstorm'
  | 'wildfire'

export type InterventionType =
  | 'green_area'
  | 'reservoir'
  | 'shelter'
  | 'alternate_route'
  | 'care_post'

export type RiskLevel = 'high' | 'moderate' | 'low'

export type FacilityType = 'hospital' | 'school' | 'health_center' | 'emergency_base'

export type LayerKey =
  | 'buildings'
  | 'roads'
  | 'terrain'
  | 'vegetation'
  | 'criticalAreas'
  | 'facilities'
  | 'risk'
  | 'population'
  | 'emergencyRoutes'

export interface Point {
  x: number
  y: number
  lat: number | null
  lng: number | null
}

export interface RegionMetrics {
  population: number
  population_density: number
  vegetation_index: number
  impermeability: number
  drainage_clogging: number
  flood_risk: number
  heat_exposure: number
  elevation_m: number
  vulnerability: number
  historical_events: number
}

export interface Facility {
  id: string
  name: string
  type: FacilityType
  region_id: string
  location: Point
  capacity: number
  critical: boolean
}

export interface Road {
  id: string
  name: string
  region_id: string
  path: Point[]
  class_: 'arterial' | 'collector' | 'local'
  critical: boolean
}

export interface Building {
  id: string
  region_id: string
  location: Point
  width: number
  depth: number
  height: number
  floors: number
  use: 'residential' | 'commercial' | 'industrial' | 'public'
}

export interface Tree {
  id: string
  region_id: string
  location: Point
  radius: number
  height: number
}

export interface Region {
  id: string
  name: string
  polygon: Point[]
  centroid: Point
  metrics: RegionMetrics
  road_count: number
  facilities: Facility[]
}

export interface City {
  id: string
  name: string
  bounds: { min_x: number; max_x: number; min_y: number; max_y: number }
  /** Official IBGE municipal outline, as an open ring. */
  boundary: Point[]
  regions: Region[]
  roads: Road[]
  waterways: Waterway[]
  vulnerability_points: VulnerabilityPoint[]
  buildings: Building[]
  trees: Tree[]
}

export interface Waterway {
  id: string
  name: string | null
  kind: 'river' | 'stream' | 'canal' | 'ditch'
  path: Point[]
  width_m: number
  osm_id: string | null
  source: string
}

export interface VulnerabilityPoint {
  id: string
  name: string
  kind: 'flood' | 'erosion' | 'heat' | 'infrastructure'
  location: Point
  severity: number
  street: string | null
  waterway: string | null
  evidence: string
  source: string
  reference: string | null
}

export interface ScenarioParams {
  type: ScenarioType
  intensity: number
  duration: number
}

export interface Intervention {
  id: string
  type: InterventionType
  region_id: string
  location: Point
  impact_factor: number
}

export interface RegionResult {
  region_id: string
  risk: number
  risk_level: RiskLevel
  baseline_risk: number
  affected_population: number
  compromised_roads: number
  critical_facilities_affected: number
  factors: Record<string, number>
  mitigations_applied: string[]
}

export interface SimulationTotals {
  affected_population: number
  compromised_roads: number
  critical_facilities_affected: number
  high_risk_regions: number
  population_exposure_index: number
  service_pressure_index: number
}

export interface SimulationResult {
  id: string
  scenario: ScenarioParams
  interventions: Intervention[]
  label: 'baseline' | 'mitigated'
  totals: SimulationTotals
  regions: RegionResult[]
}

export interface ComparisonDelta {
  affected_population: number
  affected_population_pct: number
  compromised_roads: number
  compromised_roads_pct: number
  critical_facilities_affected: number
  critical_facilities_affected_pct: number
  service_pressure_index: number
}

export interface ComparisonRow {
  region_id: string
  region_name: string
  risk_before: number
  risk_after: number
  affected_before: number
  affected_after: number
  delta_pct: number
}

export interface SimulationComparison {
  scenario: ScenarioParams
  baseline: SimulationTotals
  mitigated: SimulationTotals
  delta: ComparisonDelta
  per_region: ComparisonRow[]
}

export interface InterventionCatalogueItem {
  type: InterventionType
  label: string
  description: string
  default_impact_factor: number
  effects: Record<string, number>
}

export interface RunResponse {
  scenario: ScenarioParams
  baseline: SimulationResult
  mitigated: SimulationResult
  comparison: SimulationComparison
  total_cost_brl: number
  budget_brl: number | null
  within_budget: boolean
}

export interface ProposedIntervention {
  label: string
  type: InterventionType
  region_id: string
  region_name: string
  location: Point
  impact_factor: number
  cost_brl: number
  expected_affected_population_avoided: number
  rationale: string
}

export interface OptimizeResponse {
  scenario: ScenarioParams
  selected: ProposedIntervention[]
  rejected_budget: ProposedIntervention[]
  spent_brl: number
  budget_brl: number
  remaining_brl: number
  binding_constraint: 'budget' | 'max_interventions'
  affected_population_avoided: number
  risk_reduction_pct: number
  baseline_totals: SimulationTotals
  projected_totals: SimulationTotals
  cost_assumptions: string
  disclaimer: string
}

/** One row of the published cost table. */
export interface CostCatalogueItem {
  type: string
  unit: string
  unit_label: string
  unit_cost_brl: number
  minimum_brl: number
  maximum_brl: number
}

/** Trailing row of the cost table carrying the disclaimer. */
export interface CostNotice {
  type: 'notice'
  notice: string
}

export type CostCatalogueRow = CostCatalogueItem | CostNotice

export function isCostNotice(row: CostCatalogueRow): row is CostNotice {
  return row.type === 'notice'
}

export interface CopilotFactor {
  label: string
  weight: number
  detail: string
}

export interface CopilotRecommendation {
  region_id: string
  region_name: string
  priority_score: number
  headline: string
  factors: CopilotFactor[]
  suggested_intervention: InterventionType
  rationale: string
  estimated_cost_brl: number
  expected_effect: Record<string, number | string>
  testable: boolean
  disclaimer: string
  source: 'llm' | 'heuristic'
}

export interface CopilotResponse {
  analysis: CopilotRecommendation
  answer: string
  follow_up_questions: string[]
}

export type Stage = 'observe' | 'simulate' | 'mitigate' | 'compare'
