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
import { Button, EmptyState, RiskLegend, Stepper } from './components/ui'

const STAGES: { id: Stage; label: string; hint: string; title: string; description: string }[] = [
  { id: 'observe', label: 'OBSERVAR', hint: 'Conheça a cidade', title: 'Observe a cidade', description: 'Explore o mapa e selecione uma região para entender seus pontos fortes e vulnerabilidades.' },
  { id: 'simulate', label: 'SIMULAR', hint: 'Teste um evento', title: 'Simule um evento extremo', description: 'Escolha um cenário e veja onde a cidade pode sofrer mais.' },
  { id: 'mitigate', label: 'MITIGAR', hint: 'Teste uma solução', title: 'Escolha como agir', description: 'Adicione uma intervenção e veja o efeito esperado no cenário.' },
  { id: 'compare', label: 'COMPARAR', hint: 'Veja o resultado', title: 'Compare antes e depois', description: 'Confira o que mudou e quais regiões mais se beneficiaram.' },
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
    actions.applySuggestion()
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

  const stage = state.stage
  const stageIndex = STAGES.findIndex((item) => item.id === stage)
  const activeStage = STAGES[stageIndex] ?? STAGES[0]
  const canNavigate = (id: string) => {
    if (id === 'observe') return true
    if (id === 'simulate') return Boolean(state.city)
    if (id === 'mitigate') return Boolean(state.current)
    return Boolean(state.comparison)
  }

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

        <Stepper
          steps={STAGES}
          current={stage}
          canNavigate={canNavigate}
          onChange={(id) => actions.setStage(id as Stage)}
        />

        <Button variant="ghost" onClick={actions.reset}>
          Reiniciar
        </Button>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[320px_1fr_360px]">
        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto border-r border-slate-800 p-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-4 py-3">
            <div className="text-[10px] font-semibold tracking-widest text-sky-300 uppercase">
              Passo {stageIndex + 1} de {STAGES.length}
            </div>
            <h2 className="mt-1 text-lg font-semibold text-slate-100">{activeStage.title}</h2>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">{activeStage.description}</p>
          </div>

          {stage === 'observe' && (
            <RegionPanel
              regions={city.regions}
              selected={selectedRegion}
              result={selectedResult}
              results={resultsByRegion}
              totals={state.current?.totals ?? null}
              onSelectRegion={actions.selectRegion}
            />
          )}
          {stage === 'simulate' && (
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
          )}
          {stage === 'mitigate' && (
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
          )}
          {stage === 'compare' && <ComparePanel comparison={state.comparison} />}

          <div className="mt-auto flex gap-2">
            <Button
              variant="ghost"
              disabled={stageIndex <= 0}
              onClick={() => actions.setStage(STAGES[stageIndex - 1].id)}
              className="flex-1"
            >
              Voltar
            </Button>
            <Button
              disabled={stageIndex >= STAGES.length - 1 || !canNavigate(STAGES[stageIndex + 1].id)}
              onClick={() => actions.setStage(STAGES[stageIndex + 1].id)}
              className="flex-1"
            >
              Próximo
            </Button>
          </div>
        </aside>

        <main className="relative min-h-0">
          <CityScene
            regions={city.regions}
            boundary={city.boundary}
            buildings={city.buildings}
            roads={city.roads}
            trees={city.trees}
            waterways={city.waterways}
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

          <div className="absolute top-3 left-3 rounded-lg border border-slate-700 bg-slate-950/85 px-3 py-2 shadow-lg">
            <div className="mb-1 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
              Nível de risco
            </div>
            <RiskLegend />
          </div>

          <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2 text-[11px] text-slate-400">
            Arraste para orbitar · scroll para aproximar · clique em uma região
          </div>
        </main>

        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto border-l border-slate-800 p-3">
          {selectedRegion ? (
            <RegionPanel
              regions={[]}
              selected={selectedRegion}
              result={selectedResult}
              results={resultsByRegion}
              totals={state.current?.totals ?? null}
              onSelectRegion={actions.selectRegion}
            />
          ) : (
            <EmptyState
              title="Selecione uma região"
              description="Clique em um território no mapa para ver os indicadores e entender o risco local."
            />
          )}
          {stage === 'mitigate' && (
            <CopilotPanel
              copilot={copilot}
              onAsk={(question) => void actions.askCopilot(question)}
              onApplySuggestion={handleApplySuggestion}
              disabled={!state.current}
            />
          )}
          {stage !== 'compare' && <LayerPanel layers={layers} onToggle={actions.toggleLayer} />}
        </aside>
      </div>
    </div>
  )
}
