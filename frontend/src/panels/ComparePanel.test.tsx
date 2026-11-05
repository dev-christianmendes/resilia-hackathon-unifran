import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { overallEffect } from '../lib/theme'
import { comparison } from '../test/fixtures'
import { ComparePanel } from './ComparePanel'

function barWidths(): string[] {
  return Array.from(document.querySelectorAll<HTMLElement>('span[style]')).map((el) => el.style.width)
}

describe('ComparePanel', () => {
  it('asks for a re-simulation when there is nothing to compare', () => {
    render(<ComparePanel comparison={null} />)
    expect(screen.getByText(/execute a re-simulação/i)).toBeInTheDocument()
  })

  it('shows the reduction as a positive "menos" headline', () => {
    render(<ComparePanel comparison={comparison()} />)
    expect(screen.getByText('25% menos pessoas afetadas')).toBeInTheDocument()
    expect(screen.queryByText(/-25% menos/)).not.toBeInTheDocument()
  })

  it('scales each indicator on its own, so roads are not dwarfed by population', () => {
    render(<ComparePanel comparison={comparison()} />)
    // population 200k → 150k, roads 300 → 150, facilities 12 → 9
    expect(barWidths()).toEqual(['100%', '75%', '100%', '50%', '100%', '75%'])
  })

  it('lists the per-region breakdown', () => {
    render(<ComparePanel comparison={comparison()} />)
    expect(screen.getByText('Centro')).toBeInTheDocument()
    expect(screen.getByText('-40%')).toBeInTheDocument()
  })

  it('moves the highlight between ANTES and DEPOIS with the slider', () => {
    render(<ComparePanel comparison={comparison()} />)
    const slider = screen.getByLabelText('Posição da comparação antes e depois')
    const after = screen.getAllByText('DEPOIS')[0].parentElement!
    expect(after).toHaveClass('bg-emerald-950/60')
    fireEvent.change(slider, { target: { value: '10' } })
    expect(after).not.toHaveClass('bg-emerald-950/60')
  })
})

describe('overallEffect', () => {
  it('describes reductions, increases and no change', () => {
    expect(overallEffect(-32.4)).toBe('32% menos pessoas afetadas')
    expect(overallEffect(12.6)).toBe('13% mais pessoas afetadas')
    expect(overallEffect(0.2)).toBe('Sem variação nas pessoas afetadas')
  })
})
