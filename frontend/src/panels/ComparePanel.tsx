import type { SimulationComparison } from '../types'
import { formatNumber, formatSigned } from '../lib/theme'
import { Panel } from '../components/ui'

export function ComparePanel({ comparison }: { comparison: SimulationComparison | null }) {
  if (!comparison) {
    return (
      <Panel title="Comparação" subtitle="Antes e depois da intervenção">
        <p className="text-xs text-slate-500">
          Adicione ao menos uma intervenção e execute a re-simulação para comparar os dois
          cenários.
        </p>
      </Panel>
    )
  }

  const { baseline, mitigated, delta, per_region } = comparison
  const max = Math.max(baseline.affected_population, mitigated.affected_population, 1)

  const rows = [
    {
      label: 'População afetada',
      before: baseline.affected_population,
      after: mitigated.affected_population,
      change: delta.affected_population,
      pct: delta.affected_population_pct,
    },
    {
      label: 'Vias comprometidas',
      before: baseline.compromised_roads,
      after: mitigated.compromised_roads,
      change: delta.compromised_roads,
      pct: delta.compromised_roads_pct,
    },
    {
      label: 'Equip. críticos',
      before: baseline.critical_facilities_affected,
      after: mitigated.critical_facilities_affected,
      change: delta.critical_facilities_affected,
      pct: delta.critical_facilities_affected_pct,
    },
  ]

  return (
    <Panel
      title="Comparação"
      subtitle="Estimativas do modelo antes e depois da intervenção"
      action={
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
            delta.affected_population < 0
              ? 'bg-emerald-500/20 text-emerald-300'
              : 'bg-slate-700 text-slate-300'
          }`}
        >
          {formatSigned(delta.affected_population)} pessoas
        </span>
      }
    >
      <div className="space-y-3">
        <div className="space-y-2">
          {rows.map((row) => (
            <div key={row.label}>
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-slate-300 uppercase">{row.label}</span>
                <span
                  className={`font-mono text-[11px] ${
                    row.change < 0 ? 'text-emerald-400' : 'text-slate-400'
                  }`}
                >
                  {row.pct > 0 ? '+' : ''}
                  {row.pct.toFixed(1)}%
                </span>
              </div>
              <Bar label="ANTES" value={row.before} max={max} color="#64748b" />
              <Bar label="DEPOIS" value={row.after} max={max} color="#22c55e" />
            </div>
          ))}
        </div>

        <div>
          <h4 className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
            Por região
          </h4>
          <ul className="mt-1.5 space-y-1">
            {per_region.map((row) => (
              <li
                key={row.region_id}
                className="flex items-center justify-between gap-2 rounded-md border border-slate-800/70 bg-slate-950/50 px-2.5 py-1.5 text-xs"
              >
                <span className="truncate text-slate-300">{row.region_name}</span>
                <span className="flex shrink-0 items-center gap-2 font-mono text-[11px]">
                  <span className="text-slate-500">
                    {formatNumber(row.affected_before)} → {formatNumber(row.affected_after)}
                  </span>
                  <span
                    className={
                      row.delta_pct < 0 ? 'w-12 text-right text-emerald-400' : 'w-12 text-right text-slate-500'
                    }
                  >
                    {row.delta_pct > 0 ? '+' : ''}
                    {row.delta_pct.toFixed(0)}%
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <p className="text-[11px] leading-relaxed text-slate-500">
          Os números acima são estimativas produzidas pelo modelo de simulação da POC e não
          constituem previsão operacional.
        </p>
      </div>
    </Panel>
  )
}

function Bar({
  label,
  value,
  max,
  color,
}: {
  label: string
  value: number
  max: number
  color: string
}) {
  const width = max > 0 ? Math.max(2, (value / max) * 100) : 2
  return (
    <div className="mt-0.5 flex items-center gap-2">
      <span className="w-12 shrink-0 text-[10px] tracking-wider text-slate-500">{label}</span>
      <span className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-800">
        <span
          className="block h-full rounded-full transition-[width] duration-500"
          style={{ width: `${width}%`, backgroundColor: color }}
        />
      </span>
      <span className="w-14 shrink-0 text-right font-mono text-[11px] text-slate-200">
        {formatNumber(value)}
      </span>
    </div>
  )
}
