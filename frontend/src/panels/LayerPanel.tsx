import type { LayerKey } from '../types'
import { LAYER_META, LAYER_PRESETS } from '../lib/theme'
import { Panel } from '../components/ui'

export function LayerPanel({
  layers,
  onToggle,
  onPreset,
}: {
  layers: Record<LayerKey, boolean>
  onToggle: (key: LayerKey) => void
  onPreset: (name: string) => void
}) {
  const keys = Object.keys(LAYER_META) as LayerKey[]

  return (
    <Panel title="Camadas" subtitle="O que aparece na cidade 3D">
      <div className="mb-3 flex flex-wrap gap-1.5">
        {Object.keys(LAYER_PRESETS).map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => onPreset(name)}
            className="rounded-full border border-slate-700 px-2 py-1 text-[10px] text-slate-300 hover:border-sky-400 hover:text-sky-200"
          >
            {name}
          </button>
        ))}
      </div>
      <ul className="space-y-1">
        {keys.map((key) => {
          const meta = LAYER_META[key]
          const active = layers[key]
          return (
            <li key={key}>
              <button
                type="button"
                onClick={() => onToggle(key)}
                className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${
                  active
                    ? 'bg-sky-500/10 text-sky-200 ring-1 ring-sky-500/40'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                <span
                  className={`flex size-4 shrink-0 items-center justify-center rounded border text-[10px] ${
                    active ? 'border-sky-400 bg-sky-500 text-slate-950' : 'border-slate-600'
                  }`}
                >
                  {active ? '✓' : ''}
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium">{meta.label}</span>
                  <span className="block truncate text-[11px] text-slate-500">{meta.hint}</span>
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </Panel>
  )
}
