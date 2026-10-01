import type { LayerKey } from '../types'
import { LAYER_META } from '../lib/theme'
import { Panel } from '../components/ui'

export function LayerPanel({
  layers,
  onToggle,
}: {
  layers: Record<LayerKey, boolean>
  onToggle: (key: LayerKey) => void
}) {
  const keys = Object.keys(LAYER_META) as LayerKey[]

  return (
    <Panel title="Camadas" subtitle="O que aparece na cidade 3D">
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
