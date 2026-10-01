/** City-space helpers. The backend works in metres with +y pointing north. */
import type { Point, Region } from '../types'

export const METERS_TO_UNITS = 0.01

export function toScene(x: number, y: number): [number, number] {
  return [x * METERS_TO_UNITS, y * METERS_TO_UNITS]
}

/** Height in scene units derived from real elevation, exaggerated for legibility. */
export function elevationToHeight(elevationM: number): number {
  return (elevationM - 720) * 0.012
}

export function pointInRegion(region: Region, x: number, y: number): boolean {
  return region.polygon.some(
    (p, index) => {
      const next = region.polygon[(index + 1) % region.polygon.length]
      const crosses = p.y > y !== next.y > y
      if (!crosses) return false
      const t = (y - p.y) / (next.y - p.y)
      const edgeX = p.x + t * (next.x - p.x)
      return x < edgeX
    },
  )
}

export function regionAt(regions: Region[], x: number, y: number): Region | null {
  return regions.find((region) => pointInRegion(region, x, y)) ?? null
}

export function nearestRegion(regions: Region[], x: number, y: number): Region | null {
  let best: Region | null = null
  let bestDistance = Number.POSITIVE_INFINITY
  for (const region of regions) {
    const distance = Math.hypot(region.centroid.x - x, region.centroid.y - y)
    if (distance < bestDistance) {
      bestDistance = distance
      best = region
    }
  }
  return best
}

/** Region ordered west to east so the region list reads like a map. */
export function sortRegionsByName(regions: Region[]): Region[] {
  return [...regions].sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
}

export function polygonToScene(points: Point[]): [number, number][] {
  return points.map((p) => toScene(p.x, p.y))
}

export function regionCentre(region: Region): [number, number] {
  return toScene(region.centroid.x, region.centroid.y)
}
