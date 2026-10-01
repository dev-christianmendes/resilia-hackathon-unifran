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
