import { useState } from 'react'
import type { CopilotState } from '../state/useCityTwin'
import { INTERVENTION_META, formatBRL, formatNumber } from '../lib/theme'
import { Button, Panel } from '../components/ui'

const SUGGESTED_QUESTION = 'Onde devo priorizar uma intervenção neste cenário?'

export function CopilotPanel({
  copilot,
  onAsk,
  onApplySuggestion,
  disabled,
}: {
  copilot: CopilotState
  onAsk: (question: string) => void
  onApplySuggestion: () => void
  disabled: boolean
}) {
  const [question, setQuestion] = useState(SUGGESTED_QUESTION)

  return (
    <Panel
      title="Urban Copilot"
      subtitle="Análise explicável — a IA propõe, você simula"
      action={
        copilot.source ? (
          <span className="rounded-full border border-slate-700 px-2 py-0.5 text-[10px] text-slate-400">
            {copilot.source === 'llm' ? 'LLM' : 'heurístico'}
          </span>
        ) : null
      }
    >
      <div className="space-y-3">
        <form
          onSubmit={(event) => {
            event.preventDefault()
            onAsk(question)
          }}
          className="space-y-2"
        >
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            rows={2}
            className="w-full resize-none rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 placeholder:text-slate-600"
            placeholder="Pergunte sobre o cenário atual…"
          />
          <Button type="submit" disabled={copilot.loading || disabled} className="w-full">
            {copilot.loading ? 'Analisando…' : 'ANALISAR CENÁRIO'}
          </Button>
        </form>

        {!copilot.analysis && !copilot.answer && (
          <p className="text-[11px] text-slate-500">
            O Copilot recebe o cenário, as regiões afetadas, a infraestrutura e as intervenções
            existentes. Ele devolve uma hipótese com os fatores que a sustentam.
          </p>
        )}

        {copilot.analysis && (
          <div className="space-y-2.5">
            <div className="rounded-lg border border-sky-800/70 bg-sky-950/40 px-3 py-2.5">
              <div className="text-[10px] font-semibold tracking-wider text-sky-300 uppercase">
                Análise do cenário
              </div>
              <p className="mt-1 text-sm font-semibold text-slate-100">
                {copilot.analysis.headline}
              </p>
              <p className="mt-1 text-[11px] text-slate-400">
                Prioridade {copilot.analysis.priority_score.toFixed(2)} ·{' '}
                {copilot.analysis.region_name}
              </p>
            </div>

            <div>
              <h4 className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
                Principais fatores
              </h4>
              <ul className="mt-1 space-y-1">
                {copilot.analysis.factors.map((factor) => (
                  <li key={factor.label} className="flex items-start gap-2 text-[11px]">
                    <span className="text-slate-500">•</span>
                    <span className="flex-1 text-slate-300">{factor.detail}</span>
                    <span className="font-mono text-slate-500">
                      {(factor.weight * 100).toFixed(0)}%
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
                Intervenção sugerida
              </h4>
              <div className="mt-1 flex items-center justify-between gap-2 rounded-lg border border-emerald-800/60 bg-emerald-950/30 px-3 py-2">
                <span className="text-xs font-semibold text-emerald-200">
                  {INTERVENTION_META[copilot.analysis.suggested_intervention].icon}{' '}
                  {INTERVENTION_META[copilot.analysis.suggested_intervention].label}
                </span>
                <Button variant="success" onClick={onApplySuggestion}>
                  SIMULAR
                </Button>
              </div>
              <div className="mt-1 flex items-baseline justify-between gap-2 px-3 text-[11px] text-slate-400">
                <span>Custo estimado</span>
                <span className="font-mono text-slate-200">
                  {formatBRL(copilot.analysis.estimated_cost_brl)}
                </span>
              </div>
              <ExpectedEffect effect={copilot.analysis.expected_effect} />
            </div>

            <p className="text-[11px] leading-relaxed text-slate-400">
              {copilot.analysis.rationale}
            </p>
            <p className="rounded-md border border-slate-800 bg-slate-950/60 px-2.5 py-1.5 text-[10px] text-slate-500">
              {copilot.analysis.disclaimer}
            </p>
          </div>
        )}

        {copilot.answer && copilot.analysis && (
          <details className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
            <summary className="cursor-pointer text-[11px] font-medium text-slate-300">
              Resposta completa
            </summary>
            <pre className="mt-1.5 font-sans text-[11px] leading-relaxed whitespace-pre-wrap text-slate-400">
              {copilot.answer}
            </pre>
          </details>
        )}

        {copilot.followUps.length > 0 && (
          <div>
            <h4 className="text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
              Perguntas sugeridas
            </h4>
            <ul className="mt-1 space-y-1">
              {copilot.followUps.map((followUp) => (
                <li key={followUp}>
                  <button
                    type="button"
                    onClick={() => {
                      setQuestion(followUp)
                      onAsk(followUp)
                    }}
                    className="w-full rounded-lg border border-slate-800 px-2.5 py-1.5 text-left text-[11px] text-slate-300 hover:border-sky-700 hover:text-sky-200"
                  >
                    {followUp}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </Panel>
  )
}

function ExpectedEffect({ effect }: { effect: Record<string, number | string> }) {
  const delta = Number(effect.affected_population_delta ?? 0)
  const pct = Number(effect.affected_population_delta_pct ?? 0)
  if (!delta) return null
  return (
    <p className="mt-1.5 text-[11px] text-slate-400">
      Efeito estimado:{' '}
      <span className={delta < 0 ? 'text-emerald-400' : 'text-slate-300'}>
        {formatNumber(Math.abs(delta))} pessoas a menos ({Math.abs(pct).toFixed(1)}%)
      </span>
      . {typeof effect.basis === 'string' ? effect.basis : ''}
    </p>
  )
}


