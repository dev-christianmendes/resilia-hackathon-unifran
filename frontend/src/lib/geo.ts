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

/**
 * Even-odd ray casting: a horizontal ray from (x, y) towards +x crosses the
 * outline an odd number of times only when the point is inside.
 */
export function pointInRegion(region: Region, x: number, y: number): boolean {
  const polygon = region.polygon
  let inside = false
  for (let index = 0, prev = polygon.length - 1; index < polygon.length; prev = index++) {
    const p = polygon[index]
    const q = polygon[prev]
    if (p.y > y === q.y > y) continue
    const edgeX = p.x + ((y - p.y) / (q.y - p.y)) * (q.x - p.x)
    if (x < edgeX) inside = !inside
  }
  return inside
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

/** Regions in alphabetical order (pt-BR collation). */
export function sortRegionsByName(regions: Region[]): Region[] {
  return [...regions].sort((a, b) => a.name.localeCompare(b.name, 'pt-BR'))
}

export function polygonToScene(points: Point[]): [number, number][] {
  return points.map((p) => toScene(p.x, p.y))
}

export function regionCentre(region: Region): [number, number] {
  return toScene(region.centroid.x, region.centroid.y)
}
