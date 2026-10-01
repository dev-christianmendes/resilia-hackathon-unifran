import { useCallback, useEffect, useState } from 'react'
import type { InterventionCatalogueItem, Stage } from './types'
import { api } from './lib/api'
import { nearestRegion, regionAt } from './lib/geo'
import { useCityTwin } from './state/useCityTwin'
import { CityScene } from './components/CityScene'
import { ComparePanel } from './panels/ComparePanel'
import { CopilotPanel } from './panels/CopilotPanel'
import { LayerPanel } from './panels/LayerPanel'
import { MitigatePanel } from './panels/MitigatePanel'
import { RegionPanel } from './panels/RegionPanel'
import { ScenarioPanel } from './panels/ScenarioPanel'
import { Button } from './components/ui'

const STAGES: { id: Stage; label: string; hint: string }[] = [
  { id: 'observe', label: 'OBSERVE', hint: 'Situação atual' },
  { id: 'simulate', label: 'SIMULATE', hint: 'Aplicar cenário' },
  { id: 'mitigate', label: 'MITIGATE', hint: 'Intervir e comparar' },
]

export default function App() {
  const twin = useCityTwin()
  const {
    state,
    city,
    actions,
    layers,
    copilot,
    selectedRegion,
    selectedResult,
    resultsByRegion,
    stale,
    budget,
    setBudget,
    optimizer,
    optimize,
    applyOptimizerResult,
    costs,
  } = twin
  const [catalogue, setCatalogue] = useState<InterventionCatalogueItem[]>([])
  const [rightTab, setRightTab] = useState<'region' | 'copilot'>('region')

  useEffect(() => {
    void api
      .catalogue()
      .then(setCatalogue)
      .catch(() => setCatalogue([]))
  }, [])

  const handlePlace = useCallback(
    (x: number, y: number) => {
      const pending = state.placement
      if (!pending || !city) return
      // Attribute the intervention to the clicked region, falling back to the nearest
      // one so a click near a border still registers instead of being discarded.
      const region = regionAt(city.regions, x, y) ?? nearestRegion(city.regions, x, y)
      if (!region) return
      actions.addIntervention(
        pending.type,
        { x, y, lat: null, lng: null },
        region.id,
        pending.impact_factor,
      )
      actions.selectRegion(region.id)
      actions.cancelPlacement()
    },
    [state.placement, city, actions],
  )

  const handleImpactFactorChange = useCallback(
    (id: string, factor: number) => {
      actions.setInterventions(
        state.interventions.map((item) =>
          item.id === id ? { ...item, impact_factor: factor } : item,
        ),
      )
    },
    [actions, state.interventions],
  )

  const handleApplySuggestion = useCallback(() => {
    const created = actions.applySuggestion()
    if (created) setRightTab('region')
  }, [actions])

  const { interventions } = state

  if (state.error && !city) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950 px-6 text-center">
        <h1 className="text-lg font-semibold text-slate-100">Não foi possível carregar a cidade</h1>
        <p className="max-w-md text-sm text-slate-400">{state.error}</p>
        <p className="max-w-md text-xs text-slate-500">
          Verifique se o backend está rodando em http://localhost:8000 e recarregue a página.
        </p>
        <Button onClick={() => window.location.reload()}>Tentar novamente</Button>
      </div>
    )
  }

  if (!city) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-sm text-slate-400">
        Carregando Digital Twin…
      </div>
    )
  }

  const stage = state.interventions.length > 0 ? 'mitigate' : state.stage

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-950 text-slate-100">
      <header className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-800 bg-slate-900/80 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <span className="rounded-md bg-sky-500 px-2 py-1 text-xs font-black tracking-widest text-slate-950">
            RESILIA
          </span>
          <div>
            <h1 className="text-sm leading-tight font-semibold">CITY TWIN</h1>
            <p className="text-[11px] text-slate-400">{city.name} · Digital Twin urbano</p>
          </div>
        </div>

        <nav className="flex items-center gap-1" aria-label="Etapas">
          {STAGES.map((item, index) => {
            const active = item.id === stage
            return (
              <div key={item.id} className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={() => actions.setStage(item.id)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold tracking-wider transition-colors ${
                    active
                      ? 'bg-sky-500 text-slate-950'
                      : 'border border-slate-700 text-slate-400 hover:text-slate-200'
                  }`}
                  title={item.hint}
                >
                  {item.label}
                </button>
                {index < STAGES.length - 1 && <span className="text-slate-700">→</span>}
              </div>
            )
          })}
        </nav>

        <Button variant="ghost" onClick={actions.reset}>
          Reiniciar
        </Button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[320px_1fr_360px]">
        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto border-r border-slate-800 p-3">
          <ScenarioPanel
            scenario={state.scenario}
            stage={stage}
            result={state.current}
            busy={state.busy}
            stale={stale}
            hasInterventions={interventions.length > 0}
            onScenarioType={actions.setScenarioType}
            onIntensity={actions.setIntensity}
            onDuration={actions.setDuration}
            onSimulate={() => void actions.runSimulation()}
          />
          <MitigatePanel
            regions={city.regions}
            interventions={interventions}
            catalogue={catalogue}
            costs={costs}
            placement={state.placement}
            hasSimulation={state.current !== null}
            busy={state.busy}
            budget={budget}
            optimizer={optimizer}
            spentBrl={state.runTotals?.total_cost_brl ?? null}
            withinBudget={state.runTotals?.within_budget ?? true}
            onBudgetChange={setBudget}
            onOptimize={() => void optimize()}
            onApplyOptimizer={applyOptimizerResult}
            onStartPlacement={actions.startPlacement}
            onCancelPlacement={actions.cancelPlacement}
            onRemove={actions.removeIntervention}
            onImpactFactorChange={handleImpactFactorChange}
            onResimulate={() => void actions.runSimulation()}
          />
          <LayerPanel layers={layers} onToggle={actions.toggleLayer} />
        </aside>

        <main className="relative min-h-0">
          <CityScene
            regions={city.regions}
            boundary={city.boundary}
            buildings={city.buildings}
            roads={city.roads}
            trees={city.trees}
            facilities={city.regions.flatMap((r) => r.facilities)}
            interventions={interventions}
            result={state.current}
            scenarioType={state.scenario.type}
            intensity={state.scenario.intensity}
            layers={layers}
            selectedRegionId={state.selectedRegionId}
            placement={state.placement}
            onSelectRegion={actions.selectRegion}
            onPlace={handlePlace}
          />

          {state.error && (
            <div className="absolute top-3 left-1/2 -translate-x-1/2 rounded-lg border border-red-800 bg-red-950/90 px-3 py-2 text-xs text-red-200">
              {state.error}
            </div>
          )}

          <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2 text-[11px] text-slate-400">
            Arraste para orbitar · scroll para aproximar · clique em uma região
          </div>
        </main>

        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto border-l border-slate-800 p-3">
          <div className="grid grid-cols-2 gap-1 rounded-lg border border-slate-800 bg-slate-900/70 p-1">
            <TabButton
              active={rightTab === 'region'}
              onClick={() => setRightTab('region')}
              label="Região"
            />
            <TabButton
              active={rightTab === 'copilot'}
              onClick={() => setRightTab('copilot')}
              label="Urban Copilot"
            />
          </div>

          {rightTab === 'region' ? (
            <>
              <RegionPanel
                regions={city.regions}
                selected={selectedRegion}
                result={selectedResult}
                results={resultsByRegion}
                totals={state.current?.totals ?? null}
                onSelectRegion={actions.selectRegion}
              />
              <ComparePanel comparison={state.comparison} />
            </>
          ) : (
            <CopilotPanel
              copilot={copilot}
              onAsk={(question) => void actions.askCopilot(question)}
              onApplySuggestion={handleApplySuggestion}
              disabled={!state.current}
            />
          )}
        </aside>
      </div>
    </div>
  )
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean
  onClick: () => void
  label: string
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-xs font-semibold transition-colors ${
        active ? 'bg-sky-500 text-slate-950' : 'text-slate-400 hover:text-slate-200'
      }`}
    >
      {label}
    </button>
  )
}
