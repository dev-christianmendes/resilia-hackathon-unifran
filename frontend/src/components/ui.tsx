import type { ReactNode } from 'react'

export function Panel({
  title,
  subtitle,
  action,
  children,
  className = '',
}: {
  title?: string
  subtitle?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section
      className={`rounded-xl border border-slate-800 bg-slate-900/70 backdrop-blur ${className}`}
    >
      {title && (
        <header className="flex items-start justify-between gap-3 border-b border-slate-800 px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold tracking-wide text-slate-100 uppercase">{title}</h2>
            {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className="px-4 py-3">{children}</div>
    </section>
  )
}

export function Stat({
  label,
  value,
  hint,
  tone = 'neutral',
  testId,
}: {
  label: string
  value: ReactNode
  hint?: string
  tone?: 'neutral' | 'high' | 'moderate' | 'low' | 'good'
  testId?: string
}) {
  const tones: Record<string, string> = {
    neutral: 'text-slate-100',
    high: 'text-red-400',
    moderate: 'text-amber-400',
    low: 'text-emerald-400',
    good: 'text-emerald-400',
  }
  return (
    <div
      className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2"
      data-testid={testId}
    >
      <div className="text-[10px] font-medium tracking-wider text-slate-400 uppercase">{label}</div>
      <div className={`text-lg leading-tight font-semibold ${tones[tone]}`} data-role="stat-value">
        {value}
      </div>
      {hint && <div className="text-[11px] text-slate-500">{hint}</div>}
    </div>
  )
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  disabled = false,
  type = 'button',
  className = '',
  testId,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'ghost' | 'danger' | 'success'
  disabled?: boolean
  type?: 'button' | 'submit'
  className?: string
  testId?: string
}) {
  const variants: Record<string, string> = {
    primary: 'bg-sky-500 text-slate-950 hover:bg-sky-400 disabled:bg-slate-700 disabled:text-slate-400',
    ghost: 'border border-slate-700 text-slate-200 hover:border-sky-500 hover:text-sky-300',
    danger: 'border border-red-800 text-red-300 hover:bg-red-950/40',
    success: 'bg-emerald-500 text-slate-950 hover:bg-emerald-400',
  }
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg px-3 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed ${variants[variant]} ${className}`}
      data-testid={testId}
    >
      {children}
    </button>
  )
}

export function Slider({
  label,
  value,
  onChange,
  suffix = '%',
}: {
  label: string
  value: number
  onChange: (value: number) => void
  suffix?: string
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label className="text-xs font-medium text-slate-300">{label}</label>
        <span className="font-mono text-xs text-sky-300">
          {Math.round(value * 100)}
          {suffix}
        </span>
      </div>
      <input
        aria-label={label}
        type="range"
        min={0}
        max={100}
        value={Math.round(value * 100)}
        onChange={(event) => onChange(Number(event.target.value) / 100)}
        className="mt-1.5 w-full accent-sky-500"
      />
      <div className="mt-1 flex justify-between text-[10px] text-slate-500">
        <span>██████████</span>
        <span>░░░░░░</span>
      </div>
    </div>
  )
}

export function RiskLegend() {
  const items = [
    { color: '#ef4444', label: 'Alto' },
    { color: '#f59e0b', label: 'Moderado' },
    { color: '#22c55e', label: 'Baixo' },
  ]
  return (
    <div className="flex flex-wrap items-center gap-3 text-xs text-slate-300">
      {items.map((item) => (
        <span key={item.label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-full" style={{ backgroundColor: item.color }} />
          {item.label}
        </span>
      ))}
    </div>
  )
}

export function RiskBadge({
  level,
  label,
}: {
  level: 'high' | 'moderate' | 'low'
  label?: string
}) {
  const styles = {
    high: 'border-red-400/50 bg-red-500/15 text-red-200',
    moderate: 'border-amber-400/50 bg-amber-500/15 text-amber-200',
    low: 'border-emerald-400/50 bg-emerald-500/15 text-emerald-200',
  }
  const labels = { high: 'Alto', moderate: 'Moderado', low: 'Baixo' }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-semibold ${styles[level]}`}>
      <span aria-hidden="true">{level === 'high' ? '!' : level === 'moderate' ? '⚠' : '✓'}</span>
      {label ?? `Risco ${labels[level]}`}
    </span>
  )
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-700 bg-slate-950/40 px-4 py-5 text-center">
      <p className="text-sm font-medium text-slate-200">{title}</p>
      <p className="mt-1 text-xs leading-relaxed text-slate-400">{description}</p>
    </div>
  )
}

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden w-56 -translate-x-1/2 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-left text-[11px] leading-relaxed text-slate-200 shadow-xl group-hover:block group-focus-within:block"
      >
        {label}
      </span>
    </span>
  )
}

export function Stepper({
  steps,
  current,
  canNavigate,
  onChange,
}: {
  steps: { id: string; label: string; hint: string }[]
  current: string
  canNavigate: (id: string) => boolean
  onChange: (id: string) => void
}) {
  return (
    <nav aria-label="Progresso do fluxo" className="flex items-center gap-1">
      {steps.map((step, index) => {
        const active = step.id === current
        const enabled = canNavigate(step.id)
        return (
          <div key={step.id} className="flex items-center gap-1">
            <button
              type="button"
              disabled={!enabled}
              aria-current={active ? 'step' : undefined}
              title={enabled ? step.hint : `Complete o passo anterior: ${step.hint}`}
              onClick={() => onChange(step.id)}
              className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold tracking-wide transition-colors ${
                active
                  ? 'bg-sky-400 text-slate-950'
                  : enabled
                    ? 'border border-slate-700 text-slate-300 hover:border-sky-500 hover:text-sky-200'
                    : 'cursor-not-allowed border border-slate-800 text-slate-600'
              }`}
            >
              <span className="mr-1 opacity-60">{index + 1}</span>
              {step.label}
            </button>
            {index < steps.length - 1 && <span className="text-slate-700">→</span>}
          </div>
        )
      })}
    </nav>
  )
}

export function MetricBar({
  label,
  value,
  max,
  before,
  color = '#38bdf8',
}: {
  label: string
  value: number
  max: number
  before?: number
  color?: string
}) {
  const ratio = max > 0 ? Math.min(1, value / max) : 0
  const beforeRatio = before !== undefined && max > 0 ? Math.min(1, before / max) : null
  return (
    <div>
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-slate-300 uppercase">{label}</span>
        <span className="font-mono text-slate-100">
          {value.toLocaleString('pt-BR')}
          {before !== undefined && before !== value && (
            <span className="ml-1 text-slate-500">← {before.toLocaleString('pt-BR')}</span>
          )}
        </span>
      </div>
      <div className="relative mt-1 h-2.5 overflow-hidden rounded-full bg-slate-800">
        {beforeRatio !== null && (
          <div
            className="absolute inset-y-0 left-0 rounded-full bg-slate-600"
            style={{ width: `${beforeRatio * 100}%` }}
          />
        )}
        <div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{ width: `${ratio * 100}%`, backgroundColor: color }}
        />
      </div>
    </div>
  )
}
