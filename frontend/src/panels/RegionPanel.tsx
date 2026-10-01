import type { Region, RegionResult, SimulationTotals } from '../types'
import { FACILITY_META, RISK_COLORS, RISK_LABELS, formatPercent } from '../lib/theme'
import { Panel } from '../components/ui'

function toneFor(region: Region, result: RegionResult | null) {
  if (result) return result.risk_level
  if (region.metrics.flood_risk >= 0.7) return 'high'
  if (region.metrics.flood_risk >= 0.4) return 'moderate'
  return 'low'
}

export function RegionPanel({
  regions,
  selected,
  result,
  results,
  totals,
  onSelectRegion,
}: {
  regions: Region[]
  selected: Region | null
  result: RegionResult | null
  results: Record<string, RegionResult>
  totals: SimulationTotals | null
  onSelectRegion: (id: string) => void
}) {
  return (
    <Panel
      title="Regiões"
      subtitle={selected ? 'Clique em outro polígono para comparar' : 'Selecione uma região na cidade'}
    >
      <ul className="mb-3 grid grid-cols-2 gap-1.5">
        {regions.map((region) => {
          const active = region.id === selected?.id
          const regionResult = results[region.id] ?? null
          const tone = toneFor(region, regionResult)
          return (
            <li key={region.id}>
              <button
                type="button"
                onClick={() => onSelectRegion(region.id)}
                aria-pressed={active}
                className={`w-full rounded-lg border px-2.5 py-1.5 text-left text-xs transition-colors ${
                  active
                    ? 'border-sky-500 bg-sky-500/10 text-sky-100'
                    : 'border-slate-800 text-slate-300 hover:border-slate-600'
                }`}
              >
                <span className="flex items-center gap-1.5">
                  <span
                    className="size-2 shrink-0 rounded-full"
                    style={{ backgroundColor: RISK_COLORS[tone] }}
                  />
                  <span className="truncate font-medium">{region.name}</span>
                </span>
                {regionResult && (
                  <span className="mt-0.5 block text-[10px] text-slate-500">
                    {regionResult.affected_population.toLocaleString('pt-BR')} afetados
                  </span>
                )}
              </button>
            </li>
          )
        })}
      </ul>

      {selected ? <RegionDetail region={selected} result={result} totals={totals} /> : null}
    </Panel>
  )
}

function RegionDetail({
  region,
  result,
  totals,
}: {
  region: Region
  result: RegionResult | null
  totals: SimulationTotals | null
}) {
  const m = region.metrics
  const tone = toneFor(region, result)

  return (
    <div className="space-y-3 border-t border-slate-800 pt-3">
      <header>
        <h3 className="text-base font-semibold text-slate-100">{region.name}</h3>
        <div className="mt-1 flex items-center gap-2">
          <span
            className="rounded-full px-2 py-0.5 text-[10px] font-semibold text-slate-950"
            style={{ backgroundColor: RISK_COLORS[tone] }}
          >
            {RISK_LABELS[tone]}
          </span>
          <span className="text-[11px] text-slate-500">
            cota {m.elevation_m} m · {m.historical_events} eventos registrados
          </span>
        </div>
      </header>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
        <Row label="População estimada" value={m.population.toLocaleString('pt-BR')} />
        <Row label="Densidade" value={`${m.population_density.toLocaleString('pt-BR')} hab/km²`} />
        <Row label="Cobertura vegetal" value={formatPercent(m.vegetation_index)} />
        <Row label="Impermeabilidade" value={formatPercent(m.impermeability)} />
        <Row label="Risco de alagamento (base)" value={formatPercent(m.flood_risk)} />
        <Row label="Exposição térmica (base)" value={formatPercent(m.heat_exposure)} />
        <Row label="Vulnerabilidade social" value={formatPercent(m.vulnerability)} />
      </dl>

      <div>
        <h4 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
          Infraestrutura
        </h4>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {region.facilities.map((facility) => (
            <span
              key={facility.id}
              className="inline-flex items-center gap-1 rounded-md border border-slate-800 bg-slate-950/60 px-1.5 py-0.5 text-[11px] text-slate-300"
            >
              <span style={{ color: FACILITY_META[facility.type]?.color }}>{FACILITY_META[facility.type]?.icon}</span>
              {FACILITY_META[facility.type]?.label}
            </span>
          ))}
          <span className="inline-flex items-center gap-1 rounded-md border border-slate-800 bg-slate-950/60 px-1.5 py-0.5 text-[11px] text-slate-300">
            🛣 {region.road_count} vias
          </span>
        </div>
      </div>

      {result ? (
        <div>
          <h4 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Impacto estimado
          </h4>
          <ul className="mt-1.5 space-y-1 text-xs text-slate-200">
            <li className="flex justify-between">
              <span className="text-slate-400">Pessoas</span>
              <span className="font-mono">
                {result.affected_population.toLocaleString('pt-BR')}
              </span>
            </li>
            <li className="flex justify-between">
              <span className="text-slate-400">Vias comprometidas</span>
              <span className="font-mono">{result.compromised_roads}</span>
            </li>
            <li className="flex justify-between">
              <span className="text-slate-400">Equipamentos críticos</span>
              <span className="font-mono">{result.critical_facilities_affected}</span>
            </li>
            <li className="flex justify-between">
              <span className="text-slate-400">Risco no cenário</span>
              <span className="font-mono">{result.risk.toFixed(2)}</span>
            </li>
            {result.risk !== result.baseline_risk && (
              <li className="flex justify-between text-emerald-400">
                <span>Risco antes da intervenção</span>
                <span className="font-mono">{result.baseline_risk.toFixed(2)}</span>
              </li>
            )}
          </ul>

          {result.mitigations_applied.length > 0 && (
            <ul className="mt-2 space-y-1">
              {result.mitigations_applied.map((label) => (
                <li key={label} className="text-[11px] text-emerald-300">
                  ✓ {label}
                </li>
              ))}
            </ul>
          )}

          <div className="mt-2">
            <h4 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
              Fatores do modelo
            </h4>
            <FactorList factors={result.factors} />
          </div>
        </div>
      ) : totals ? null : (
        <p className="text-xs text-slate-500">
          Execute uma simulação para ver o impacto estimado nesta região.
        </p>
      )}
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-slate-800/60 pb-1">
      <dt className="text-slate-400">{label}</dt>
      <dd className="font-mono text-slate-100">{value}</dd>
    </div>
  )
}

const FACTOR_LABELS: Record<string, string> = {
  hazard: 'Intensidade do evento',
  drainage_deficit: 'Déficit de drenagem',
  storage_capacity: 'Capacidade de armazenamento',
  terrain_susceptibility: 'Susceptibilidade do terreno',
  social_vulnerability: 'Vulnerabilidade social',
  runoff: 'Escoamento superficial',
  shade_deficit: 'Déficit de sombra',
  thermal_mass: 'Massa térmica do solo',
  heat_exposure: 'Exposição térmica',
  heat_load: 'Carga térmica',
}

function FactorList({ factors }: { factors: Record<string, number> }) {
  const entries = Object.entries(factors)
    .filter(([key]) => key !== 'risk')
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  return (
    <ul className="mt-1.5 space-y-1">
      {entries.map(([key, value]) => (
        <li key={key} className="flex items-center gap-2">
          <span className="w-32 shrink-0 truncate text-[11px] text-slate-400">
            {FACTOR_LABELS[key] ?? key}
          </span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-800">
            <span
              className="block h-full rounded-full bg-gradient-to-r from-sky-500 to-cyan-300"
              style={{ width: `${Math.min(100, value * 100)}%` }}
            />
          </span>
          <span className="w-10 text-right font-mono text-[11px] text-slate-300">
            {value.toFixed(2)}
          </span>
        </li>
      ))}
    </ul>
  )
}
