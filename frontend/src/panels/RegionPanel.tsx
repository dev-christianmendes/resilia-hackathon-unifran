import type { Region, RegionResult, SimulationTotals } from '../types'
import { FACILITY_META, RISK_COLORS, RISK_LABELS, formatPercent } from '../lib/theme'
import { Button, Panel, RiskBadge, Tooltip } from '../components/ui'
import { useMemo, useState } from 'react'

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
  const [query, setQuery] = useState('')
  const [showAll, setShowAll] = useState(false)
  const ranked = useMemo(
    () =>
      [...regions]
        .sort((a, b) => (results[b.id]?.risk ?? b.metrics.flood_risk) - (results[a.id]?.risk ?? a.metrics.flood_risk))
        .filter((region) => friendlyName(region.name).toLocaleLowerCase('pt-BR').includes(query.toLocaleLowerCase('pt-BR'))),
    [query, regions, results],
  )
  const visible = showAll ? ranked : ranked.slice(0, 5)

  return (
    <Panel
      title="Mais críticas"
      subtitle={selected ? 'Selecione outra região para comparar' : 'Comece por uma área no topo da lista'}
    >
      <div className="mb-3 space-y-2">
        <input
          aria-label="Buscar região"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar região..."
          className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 outline-none focus:border-sky-400"
        />
        <ul className="space-y-1.5">
        {visible.map((region, index) => {
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
                <span className="flex items-center justify-between gap-2">
                  <span className="flex min-w-0 items-center gap-2">
                    <span className="text-[10px] font-bold text-slate-500">{index + 1}</span>
                    <span className="truncate font-medium">{friendlyName(region.name)}</span>
                  </span>
                  <RiskBadge level={tone} />
                </span>
                {regionResult && (
                  <span className="mt-0.5 block text-[10px] text-slate-500">
                    {reasonFor(region, regionResult)}
                  </span>
                )}
              </button>
            </li>
          )
        })}
        </ul>
        <Button variant="ghost" className="w-full text-xs" onClick={() => setShowAll((value) => !value)}>
          {showAll ? 'Mostrar só as 5 principais' : `Ver todas (${ranked.length})`}
        </Button>
      </div>

      {selected ? <RegionDetail region={selected} result={result} totals={totals} /> : null}
    </Panel>
  )
}

function friendlyName(name: string): string {
  const base = name.replace(/\s+\(\d+\)$/, '')
  return base === "Curso d'água sem nome" ? 'Curso sem nome' : base
}

function reasonFor(region: Region, result: RegionResult): string {
  if (result.compromised_roads > 0) return `${result.compromised_roads} vias podem ficar bloqueadas`
  if (region.metrics.impermeability >= 0.6) return 'alta impermeabilização do solo'
  if (region.metrics.vulnerability >= 0.6) return 'maior vulnerabilidade social'
  return `${result.affected_population.toLocaleString('pt-BR')} pessoas expostas`
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
        <Row
          label="Impermeabilidade"
          value={formatPercent(m.impermeability)}
          hint="Quanto do solo está coberto por construções ou pavimento. Quanto maior, menos água infiltra."
        />
        <Row label="Risco de alagamento (base)" value={formatPercent(m.flood_risk)} />
        <Row
          label="Obstrução da drenagem"
          value={formatPercent(m.drainage_clogging)}
          hint="Estimativa de quanto resíduos, pavimento e baixa infiltração podem reduzir o escoamento da água."
        />
        <Row label="Exposição térmica (base)" value={formatPercent(m.heat_exposure)} />
        <Row
          label="Vulnerabilidade social"
          value={formatPercent(m.vulnerability)}
          hint="Estimativa de quantas pessoas podem ter mais dificuldade para se proteger ou se recuperar."
        />
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

function Row({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2 border-b border-slate-800/60 pb-1">
      <dt className="text-slate-400">
        {hint ? (
          <Tooltip label={hint}>
            <span className="cursor-help border-b border-dotted border-slate-500">{label} ?</span>
          </Tooltip>
        ) : (
          label
        )}
      </dt>
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
