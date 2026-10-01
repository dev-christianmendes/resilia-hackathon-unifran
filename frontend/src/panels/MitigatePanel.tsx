import { useState } from 'react'
import type {
  Intervention,
  InterventionCatalogueItem,
  InterventionType,
  Region,
} from '../types'
import { INTERVENTION_META } from '../lib/theme'
import { Button, Panel } from '../components/ui'

export function MitigatePanel({
  regions,
  interventions,
  catalogue,
  placement,
  hasSimulation,
  busy,
  onStartPlacement,
  onCancelPlacement,
  onRemove,
  onImpactFactorChange,
  onResimulate,
}: {
  regions: Region[]
  interventions: Intervention[]
  catalogue: InterventionCatalogueItem[]
  placement: Intervention | null
  hasSimulation: boolean
  busy: boolean
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
          <Button variant="success" onClick={handlePlace} className="w-full">
            + Adicionar intervenção
          </Button>
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
