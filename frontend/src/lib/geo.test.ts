import { describe, expect, it } from 'vitest'
import { point, square } from '../test/fixtures'
import type { Region } from '../types'
import { elevationToHeight, nearestRegion, pointInRegion, regionAt, sortRegionsByName, toScene } from './geo'

/** U-shaped region: the notch between the arms (x 40..60, y 40..100) is outside. */
const uShape: Region = {
  ...square('u', 'U', 0, 0),
  polygon: [
    point(0, 0), point(100, 0), point(100, 100), point(60, 100),
    point(60, 40), point(40, 40), point(40, 100), point(0, 100),
  ],
}

describe('pointInRegion', () => {
  const region = square('r1', 'Centro', 0, 0)

  it('accepts a point inside a square', () => {
    expect(pointInRegion(region, 50, 50)).toBe(true)
  })

  it('rejects points to the left, right, above and below', () => {
    expect(pointInRegion(region, -10, 50)).toBe(false)
    expect(pointInRegion(region, 110, 50)).toBe(false)
    expect(pointInRegion(region, 50, 110)).toBe(false)
    expect(pointInRegion(region, 50, -10)).toBe(false)
  })

  it('handles concave regions', () => {
    expect(pointInRegion(uShape, 20, 70)).toBe(true)
    expect(pointInRegion(uShape, 80, 70)).toBe(true)
    expect(pointInRegion(uShape, 50, 70)).toBe(false)
    expect(pointInRegion(uShape, 50, 20)).toBe(true)
  })
})

describe('regionAt / nearestRegion', () => {
  const west = square('w', 'Oeste', 0, 0)
  const east = square('e', 'Leste', 200, 0)

  it('returns the region that contains the point', () => {
    expect(regionAt([west, east], 250, 50)?.id).toBe('e')
    expect(regionAt([west, east], 50, 50)?.id).toBe('w')
  })

  it('returns null in the gap between regions, where nearestRegion still answers', () => {
    expect(regionAt([west, east], 160, 50)).toBeNull()
    expect(nearestRegion([west, east], 160, 50)?.id).toBe('e')
    expect(nearestRegion([], 0, 0)).toBeNull()
  })
})

describe('scene helpers', () => {
  it('converts metres to scene units', () => {
    expect(toScene(1500, -200)).toEqual([15, -2])
  })

  it('maps the 720 m reference elevation to height 0', () => {
    expect(elevationToHeight(720)).toBe(0)
    expect(elevationToHeight(1020)).toBeCloseTo(3.6)
  })

  it('sorts names with pt-BR collation without mutating the input', () => {
    const regions = [square('1', 'Vila Ésio', 0, 0), square('2', 'Estação', 0, 0), square('3', 'Centro', 0, 0)]
    expect(sortRegionsByName(regions).map((r) => r.name)).toEqual(['Centro', 'Estação', 'Vila Ésio'])
    expect(regions[0].name).toBe('Vila Ésio')
  })
})
