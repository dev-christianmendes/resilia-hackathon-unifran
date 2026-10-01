import { useState } from 'react'
import { isCostNotice } from '../types'
import type {
  CostCatalogueRow,
  Intervention,
  InterventionCatalogueItem,
  InterventionType,
  OptimizeResponse,
  Region,
} from '../types'
import { BUDGET_PRESETS, INTERVENTION_META, formatBRL, formatNumber } from '../lib/theme'
import { Button, Panel } from '../components/ui'

export function MitigatePanel({
  regions,
  interventions,
  catalogue,
  costs,
  placement,
  hasSimulation,
  busy,
  budget,
  optimizer,
  spentBrl,
  withinBudget,
  onBudgetChange,
  onOptimize,
  onApplyOptimizer,
  onStartPlacement,
  onCancelPlacement,
  onRemove,
  onImpactFactorChange,
  onResimulate,
}: {
  regions: Region[]
  interventions: Intervention[]
  catalogue: InterventionCatalogueItem[]
  costs: CostCatalogueRow[]
  placement: Intervention | null
  hasSimulation: boolean
  busy: boolean
  budget: number
  optimizer: { loading: boolean; result: OptimizeResponse | null; error: string | null }
  spentBrl: number | null
  withinBudget: boolean
  onBudgetChange: (value: number) => void
  onOptimize: () => void
  onApplyOptimizer: () => void
  onStartPlacement: (intervention: Intervention) => void
  onCancelPlacement: () => void
  onRemove: (id: string) => void
  onImpactFactorChange: (id: string, factor: number) => void
  onResimulate: () => void
}) {
  const [type, setType] = useState<InterventionType>('reservoir')
  const [regionId, setRegionId] = useState(regions[0]?.id ?? '')
  const [factor, setFactor] = useState(0.75)

  const items = catalogue.length
    ? catalogue
    : (Object.keys(INTERVENTION_META) as InterventionType[]).map((key) => ({
        type: key,
        label: INTERVENTION_META[key].label,
        description: INTERVENTION_META[key].description,
        default_impact_factor: 0.7,
        effects: {},
      }))

  const activeRegion = regions.find((r) => r.id === regionId) ?? regions[0]

  function handlePlace() {
    if (!activeRegion) return
    if (spentBrl !== null && !withinBudget) return
    onStartPlacement({
      id: `pending-${type}-${Date.now()}`,
      type,
      region_id: activeRegion.id,
      location: activeRegion.centroid,
      impact_factor: factor,
    })
  }

  return (
    <Panel title="Mitigação" subtitle="Insira intervenções e meça o efeito">
      <div className="space-y-4">
        <div data-testid="budget-block">
          <h4 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Orçamento disponível
          </h4>
          <div className="mt-1.5 grid grid-cols-4 gap-1.5">
            {BUDGET_PRESETS.map((preset) => (
              <button
                key={preset.value}
                type="button"
                onClick={() => onBudgetChange(preset.value)}
                className={`rounded-lg border px-1.5 py-1.5 text-[11px] font-semibold transition-colors ${
                  budget === preset.value
                    ? 'border-emerald-500 bg-emerald-500/10 text-emerald-300'
                    : 'border-slate-800 text-slate-400 hover:border-slate-600'
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>

          {spentBrl !== null && interventions.length > 0 && (
            <div
              className={`mt-2 rounded-lg border px-3 py-2 text-[11px] ${
                withinBudget
                  ? 'border-emerald-900 bg-emerald-950/40 text-emerald-200'
                  : 'border-red-900 bg-red-950/40 text-red-200'
              }`}
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-semibold">
                  {withinBudget ? 'Dentro do orçamento' : 'Acima do orçamento'}
                </span>
                <span className="font-mono">
                  {formatBRL(spentBrl)} / {formatBRL(budget)}
                </span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-800">
                <div
                  className={`h-full rounded-full ${
                    withinBudget ? 'bg-emerald-500' : 'bg-red-500'
                  }`}
                  style={{
                    width: `${Math.min(100, (spentBrl / Math.max(budget, 1)) * 100)}%`,
                  }}
                />
              </div>
            </div>
          )}

          <Button
            onClick={onOptimize}
            disabled={optimizer.loading || busy}
            className="mt-2 w-full"
            variant="ghost"
            testId="optimize-button"
          >
            {optimizer.loading ? 'Otimizando…' : '[ OTIMIZAR POR ORÇAMENTO ]'}
          </Button>

          {optimizer.error && (
            <p className="mt-1.5 text-[11px] text-red-400">{optimizer.error}</p>
          )}

          {optimizer.result && optimizer.result.selected.length > 0 && (
            <div
              data-testid="optimizer-result"
              className="mt-2 rounded-lg border border-emerald-900 bg-emerald-950/30 px-3 py-2"
            >
              <div className="flex items-baseline justify-between gap-2 text-[11px] text-emerald-200">
                <span className="font-semibold">
                  {optimizer.result.selected.length} obras em{' '}
                  {optimizer.result.selected.length &&
                    new Set(optimizer.result.selected.map((p) => p.region_id)).size}{' '}
                  regiões
                </span>
                <span className="font-mono">{formatBRL(optimizer.result.spent_brl)}</span>
              </div>
              <p className="mt-0.5 text-[11px] text-emerald-300/90">
                Evita {formatNumber(optimizer.result.affected_population_avoided)} pessoas
              </p>
              <p className="mt-1 text-[10px] text-slate-400">
                Limitado por{' '}
                {optimizer.result.binding_constraint === 'budget'
                  ? 'orcamento'
                  : 'número de obras'}{' '}
                • {formatBRL(optimizer.result.remaining_brl)} restantes
              </p>
              <ul className="mt-1.5 space-y-1">
                {optimizer.result.selected.map((proposal) => (
                  <li
                    key={`${proposal.region_id}-${proposal.type}`}
                    className="text-[10px] text-slate-400"
                  >
                    <span className="text-slate-200">{proposal.region_name}</span> —{' '}
                    {INTERVENTION_META[proposal.type].label} •{' '}
                    {formatBRL(proposal.cost_brl)} • evita{' '}
                    {formatNumber(proposal.expected_affected_population_avoided)}
                  </li>
                ))}
              </ul>
              <p className="mt-1.5 text-[10px] text-slate-500">
                {optimizer.result.cost_assumptions}
              </p>
              <Button onClick={onApplyOptimizer} variant="success" className="mt-2 w-full">
                Aplicar este portfólio
              </Button>
            </div>
          )}
        </div>

        {costs.length > 0 && (
          <details className="rounded-lg border border-slate-800 bg-slate-950/40 px-3 py-2">
            <summary className="cursor-pointer text-[11px] font-semibold text-slate-300">
              De onde vêm os preços
            </summary>
            <ul className="mt-1.5 space-y-1">
              {costs.map((cost) =>
                isCostNotice(cost) ? (
                  <li key={cost.type} className="text-[10px] text-slate-500">
                    {cost.notice}
                  </li>
                ) : (
                  <li key={cost.type} className="text-[10px] text-slate-500">
                    <span className="text-slate-300">{cost.unit_label}</span>:{' '}
                    {formatBRL(cost.unit_cost_brl)}/{cost.unit} • teto{' '}
                    {formatBRL(cost.maximum_brl)}
                  </li>
                ),
              )}
            </ul>
          </details>
        )}

        <div>
          <h4 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            + Intervenção
          </h4>
          <div className="mt-1.5 grid grid-cols-2 gap-1.5">
            {items.map((item) => {
              const meta = INTERVENTION_META[item.type]
              const active = type === item.type
              return (
                <button
                  key={item.type}
                  type="button"
                  onClick={() => {
                    setType(item.type)
                    setFactor(item.default_impact_factor)
                  }}
                  className={`rounded-lg border px-2.5 py-2 text-left text-xs transition-colors ${
                    active ? 'border-sky-500 bg-sky-500/10' : 'border-slate-800 hover:border-slate-600'
                  }`}
                >
                  <span className="block font-semibold text-slate-100">
                    {meta.icon} {item.label}
                  </span>
                  <span className="mt-0.5 block text-[10px] leading-snug text-slate-500">
                    {item.description}
                  </span>
                </button>
              )
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <label className="block text-xs text-slate-400">
            Região
            <select
              value={regionId}
              onChange={(event) => setRegionId(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-slate-100"
            >
              {regions.map((region) => (
                <option key={region.id} value={region.id}>
                  {region.name}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-xs text-slate-400">
            Fator de impacto
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={factor}
              onChange={(event) =>
                setFactor(Math.min(1, Math.max(0, Number(event.target.value))))
              }
              className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 font-mono text-xs text-slate-100"
            />
          </label>
        </div>

        {placement ? (
          <Button variant="ghost" onClick={onCancelPlacement} className="w-full">
            Cancelar posicionamento
          </Button>
        ) : (
          <Button
            variant="success"
            onClick={handlePlace}
            disabled={spentBrl !== null && !withinBudget}
            className="w-full"
          >
            {spentBrl !== null && !withinBudget ? 'Orçamento esgotado' : '+ Adicionar intervenção'}
          </Button>
        )}

        {spentBrl !== null && !withinBudget && (
          <p className="rounded-lg border border-red-800 bg-red-950/40 px-3 py-2 text-[11px] text-red-200">
            Esta configuração ultrapassa o orçamento. Remova uma intervenção ou aumente o limite
            antes de adicionar outra.
          </p>
        )}

        {placement && (
          <p className="rounded-lg border border-sky-800 bg-sky-950/40 px-3 py-2 text-[11px] text-sky-200">
            Clique em um ponto da cidade 3D para posicionar{' '}
            {INTERVENTION_META[placement.type].label}.
          </p>
        )}

        {interventions.length > 0 && (
          <div data-testid="intervention-list">
            <h4 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
              No cenário ({interventions.length})
            </h4>
            <ul className="mt-1.5 space-y-1.5">
              {interventions.map((intervention) => {
                const meta = INTERVENTION_META[intervention.type]
                const region = regions.find((r) => r.id === intervention.region_id)
                return (
                  <li
                    key={intervention.id}
                    className="rounded-lg border border-slate-800 bg-slate-950/60 px-2.5 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="flex items-center gap-1.5 text-xs font-medium text-slate-100">
                        <span
                          className="size-2 rounded-full"
                          style={{ backgroundColor: meta.color }}
                        />
                        {meta.icon} {meta.label}
                      </span>
                      <button
                        type="button"
                        onClick={() => onRemove(intervention.id)}
                        className="text-[11px] text-red-400 hover:text-red-300"
                      >
                        remover
                      </button>
                    </div>
                    <div className="mt-0.5 text-[10px] text-slate-500">
                      {region?.name ?? intervention.region_id}
                    </div>
                    <label className="mt-1.5 flex items-center gap-2 text-[10px] text-slate-500">
                      impacto
                      <input
                        type="range"
                        min={0}
                        max={100}
                        value={Math.round(intervention.impact_factor * 100)}
                        onChange={(event) =>
                          onImpactFactorChange(
                            intervention.id,
                            Number(event.target.value) / 100,
                          )
                        }
                        className="flex-1 accent-emerald-500"
                      />
                      <span className="w-8 text-right font-mono text-slate-300">
                        {Math.round(intervention.impact_factor * 100)}%
                      </span>
                    </label>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        <Button
          onClick={onResimulate}
          disabled={busy || interventions.length === 0}
          className="w-full"
        >
          {busy ? 'Re-simulando…' : '[ COMPARAR COM INTERVENÇÕES ]'}
        </Button>

        {!hasSimulation && (
          <p className="text-[11px] text-slate-500">
            Execute uma simulação primeiro para habilitar a comparação antes/depois.
          </p>
        )}
      </div>
    </Panel>
  )
}
