import type { InterventionType, LayerKey, RiskLevel } from '../types'

export const RISK_COLORS: Record<RiskLevel, string> = {
  high: '#ef4444',
  moderate: '#f59e0b',
  low: '#22c55e',
}

export const RISK_LABELS: Record<RiskLevel, string> = {
  high: 'Risco alto',
  moderate: 'Risco moderado',
  low: 'Baixo risco',
}

export const SCENARIO_META = {
  extreme_rain: {
    label: 'Chuva extrema',
    icon: '🌧',
    description: 'Alagamentos, bloqueio de vias e isolamento de regiões.',
    effect: 'Efeito na cena: chuva intensa e áreas alagadas',
  },
  heat_wave: {
    label: 'Onda de calor',
    icon: '🔥',
    description: 'Exposição térmica, baixa cobertura vegetal e pressão sobre a saúde.',
    effect: 'Efeito na cena: sombreamento vermelho e solo ressecado',
  },
} as const

export const INTERVENTION_META: Record<
  InterventionType,
  { label: string; icon: string; color: string; description: string }
> = {
  green_area: {
    label: 'Área verde',
    icon: '🌿',
    color: '#22c55e',
    description: 'Aumenta a cobertura vegetal e a permeabilidade do solo.',
  },
  reservoir: {
    label: 'Reservatório',
    icon: '🟦',
    color: '#38bdf8',
    description: 'Acumula o excedente de escoamento e reduz o pico de vazão.',
  },
  shelter: {
    label: 'Abrigo',
    icon: '🏕',
    color: '#f472b6',
    description: 'Reduz a população diretamente exposta dentro da região.',
  },
  alternate_route: {
    label: 'Rota alternativa',
    icon: '🛣',
    color: '#a78bfa',
    description: 'Desvia o tráfego das vias expostas durante o evento.',
  },
  care_post: {
    label: 'Ponto de atendimento',
    icon: '🏥',
    color: '#fbbf24',
    description: 'Distribui a demanda sobre os equipamentos de saúde da região.',
  },
}

export const FACILITY_META: Record<string, { label: string; color: string; icon: string }> = {
  hospital: { label: 'Hospital', color: '#ef4444', icon: '🏥' },
  emergency_base: { label: 'Base de emergência', color: '#f97316', icon: '🚨' },
  health_center: { label: 'UBS', color: '#fbbf24', icon: '⚕️' },
  school: { label: 'Escola', color: '#38bdf8', icon: '🏫' },
}

export const DEFAULT_LAYERS: Record<LayerKey, boolean> = {
  terrain: true,
  roads: true,
  buildings: true,
  vegetation: true,
  facilities: true,
  criticalAreas: true,
  risk: true,
  population: false,
  emergencyRoutes: false,
}

export const LAYER_META: Record<LayerKey, { label: string; hint: string }> = {
  terrain: { label: 'Terreno', hint: 'Relevo e hipsometria' },
  roads: { label: 'Ruas', hint: 'Malha viária e vias críticas' },
  buildings: { label: 'Edificações', hint: 'Volume construido' },
  vegetation: { label: 'Vegetação', hint: 'Cobertura vegetal' },
  facilities: { label: 'Equipamentos públicos', hint: 'Hospitais, escolas e UBS' },
  criticalAreas: { label: 'Áreas críticas', hint: 'Polígonos de risco base' },
  risk: { label: 'Risco climático', hint: 'Resultado da simulação' },
  population: { label: 'População', hint: 'Rótulos por região' },
  emergencyRoutes: { label: 'Rotas de emergência', hint: 'Eixos viários prioritários' },
}

export function riskFromColorLevel(risk: number): RiskLevel {
  if (risk >= 0.62) return 'high'
  if (risk >= 0.34) return 'moderate'
  return 'low'
}

const numberFormat = new Intl.NumberFormat('pt-BR')

export function formatNumber(value: number): string {
  return numberFormat.format(Math.round(value))
}

export function formatPercent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits)}%`
}

export function formatSigned(value: number): string {
  const rounded = Math.round(value)
  return `${rounded > 0 ? '+' : ''}${numberFormat.format(rounded)}`
}

/** Money as the user reads it: R$ 1,2 mi rather than 1200000. */
export function formatBRL(value: number): string {
  const abs = Math.abs(value)
  if (abs >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toLocaleString('pt-BR', {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })} mi`
  }
  if (abs >= 1_000) {
    return `R$ ${(value / 1_000).toLocaleString('pt-BR', { maximumFractionDigits: 0 })} mil`
  }
  return `R$ ${value.toLocaleString('pt-BR', { maximumFractionDigits: 0 })}`
}

/**
 * Starting budget for the mitigation step. Large enough to buy several
 * neighbourhood-scale works, which is the size that actually moves the model.
 */
export const DEFAULT_BUDGET_BRL = 5_000_000

/** Budget presets offered in the UI, in reais. */
export const BUDGET_PRESETS = [
  { value: 1_000_000, label: 'R$ 1 mi' },
  { value: 5_000_000, label: 'R$ 5 mi' },
  { value: 20_000_000, label: 'R$ 20 mi' },
  { value: 50_000_000, label: 'R$ 50 mi' },
]
