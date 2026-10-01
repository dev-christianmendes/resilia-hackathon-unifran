import type { ScenarioParams, ScenarioType, Stage, SimulationResult } from '../types'
import { SCENARIO_META } from '../lib/theme'
import { Button, Panel, RiskLegend, Slider, Stat } from '../components/ui'

const SCENARIOS: ScenarioType[] = [
  'extreme_rain',
  'heat_wave',
  'hailstorm',
  'windstorm',
  'wildfire',
]

export function ScenarioPanel({
  scenario,
  stage,
  result,
  busy,
  stale,
  hasInterventions,
  onScenarioType,
  onIntensity,
  onDuration,
  onSimulate,
}: {
  scenario: ScenarioParams
  stage: Stage
  result: SimulationResult | null
  busy: boolean
  stale: boolean
  hasInterventions: boolean
  onScenarioType: (type: ScenarioType) => void
  onIntensity: (value: number) => void
  onDuration: (value: number) => void
  onSimulate: () => void
}) {
  const label = hasInterventions ? 'RE-SIMULAR' : 'SIMULAR'

  return (
    <Panel
      title="Cenário"
      subtitle="Escolha um evento e ajuste os parâmetros"
    >
      <div className="space-y-4">
        <div className="grid grid-cols-1 gap-2">
          {SCENARIOS.map((type) => {
            const meta = SCENARIO_META[type]
            const active = scenario.type === type
            return (
              <button
                key={type}
                type="button"
                onClick={() => onScenarioType(type)}
                className={`rounded-lg border px-3 py-2.5 text-left transition-colors ${
                  active
                    ? 'border-sky-500 bg-sky-500/10'
                    : 'border-slate-800 hover:border-slate-600'
                }`}
              >
                <span className="block text-base font-semibold text-slate-100">{meta.label}</span>
                <span className="mt-0.5 block text-[11px] leading-snug text-slate-400">
                  {meta.description}
                </span>
              </button>
            )
          })}
        </div>

        <div className="space-y-3">
          <Slider label="Intensidade do evento" value={scenario.intensity} onChange={onIntensity} />
          <div className="-mt-2 text-[11px] text-slate-500">{scaleLabel(scenario.intensity)} · valor do modelo {Math.round(scenario.intensity * 100)}%</div>
          <Slider label="Duração do evento" value={scenario.duration} onChange={onDuration} />
          <div className="-mt-2 text-[11px] text-slate-500">{scaleLabel(scenario.duration)} · duração relativa</div>
        </div>

        <Button onClick={onSimulate} disabled={busy} className="w-full">
          {busy ? 'Simulando…' : `[ ${label} ]`}
        </Button>

        {stale && result && (
          <p className="rounded-lg border border-amber-800/60 bg-amber-950/40 px-3 py-2 text-[11px] text-amber-200">
            Os parâmetros mudaram. Execute a simulação novamente para atualizar a cidade.
          </p>
        )}

        {result && (
          <>
            <p className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-2 text-sm leading-relaxed text-sky-950">
              Com {SCENARIO_META[scenario.type].label.toLocaleLowerCase('pt-BR')} a {Math.round(scenario.intensity * 100)}%,{' '}
              {result.totals.compromised_roads} vias podem ficar bloqueadas e{' '}
              {result.totals.critical_facilities_affected} equipamentos críticos podem ser afetados.
            </p>
            <RiskLegend />
            <div className="grid grid-cols-2 gap-2">
              <Stat
                testId="stat-affected-population"
                label="População afetada"
                value={result.totals.affected_population.toLocaleString('pt-BR')}
                tone="high"
              />
              <Stat
                testId="stat-compromised-roads"
                label="Vias comprometidas"
                value={result.totals.compromised_roads}
                tone="moderate"
              />
              <Stat
                testId="stat-critical-facilities"
                label="Equip. críticos"
                value={result.totals.critical_facilities_affected}
                tone="moderate"
              />
              <Stat
                testId="stat-high-risk-regions"
                label="Regiões críticas"
                value={result.totals.high_risk_regions}
                tone={result.totals.high_risk_regions > 0 ? 'high' : 'low'}
              />
            </div>
            <p className="text-[11px] leading-relaxed text-slate-500">
              {SCENARIO_META[scenario.type].effect}. Estimativas produzidas pelo modelo de
              simulação — não são previsões operacionais.
            </p>
          </>
        )}

        {stage === 'observe' && !result && (
          <p className="text-xs text-slate-500">
            Comece em <span className="text-slate-300">OBSERVE</span>: navegue pela cidade e
            clique em uma região para ver seus indicadores.
          </p>
        )}
      </div>
    </Panel>
  )
}

function scaleLabel(value: number): string {
  if (value < 0.25) return 'Fraca'
  if (value < 0.5) return 'Moderada'
  if (value < 0.75) return 'Forte'
  return 'Extrema'
}
