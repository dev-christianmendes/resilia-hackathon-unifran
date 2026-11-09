import type { Region, RegionResult } from '../types'

/** Most region labels shown at once (the selected and hovered regions always get one). */
export const MAX_LABELS = 5

/*
 * Labels are drei `<Html>` with `distanceFactor`, so they scale with the scene and each
 * card covers a roughly fixed patch of ground. Measured on the default camera:
 * a card is ~6.6 px per character + 36 px of padding wide, at ~37 px per km across,
 * and ~46 px tall at ~21 px per km in depth (the camera tilt shortens that axis).
 */
export const LABEL_CHAR_WIDTH_M = 180
export const LABEL_PADDING_M = 1000
export const LABEL_DEPTH_M = 2400

/** Ground width, in meters, covered by a label card showing `name`. */
export function labelWidthM(name: string): number {
  return name.length * LABEL_CHAR_WIDTH_M + LABEL_PADDING_M
}

interface Placed {
  region: Region
  width: number
}

function overlaps(a: Placed, b: Placed): boolean {
  return (
    Math.abs(a.region.centroid.x - b.region.centroid.x) < (a.width + b.width) / 2 &&
    Math.abs(a.region.centroid.y - b.region.centroid.y) < LABEL_DEPTH_M
  )
}

/**
 * Picks the regions that get a floating label: the selected and hovered regions first,
 * then the riskiest ones, skipping any whose card would overlap a label already placed.
 * `nameOf` must return the text the card shows, since it sets the card width.
 */
export function labelRegions(
  regions: Region[],
  results: Record<string, RegionResult>,
  selectedId: string | null,
  hoveredId: string | null,
  nameOf: (region: Region) => string = (region) => region.name,
): Region[] {
  const pinned = (region: Region) => region.id === selectedId || region.id === hoveredId
  const ranked = [...regions].sort((a, b) => (results[b.id]?.risk ?? 0) - (results[a.id]?.risk ?? 0))
  const placed: Placed[] = []
  for (const region of [...regions.filter(pinned), ...ranked]) {
    if (placed.some((item) => item.region.id === region.id)) continue
    const candidate = { region, width: labelWidthM(nameOf(region)) }
    if (!pinned(region)) {
      if (placed.length >= MAX_LABELS) continue
      if (placed.some((other) => overlaps(candidate, other))) continue
    }
    placed.push(candidate)
  }
  return placed.map((item) => item.region)
}
