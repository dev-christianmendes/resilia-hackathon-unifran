import { useMemo } from 'react'
import { Instance, Instances, useCursor } from '@react-three/drei'
import type { Building } from '../types'
import { METERS_TO_UNITS, elevationToHeight } from '../lib/geo'

const REGION_BASE = METERS_TO_UNITS * 40

const USE_COLORS: Record<Building['use'], string> = {
  residential: '#94a3b8',
  commercial: '#64748b',
  industrial: '#475569',
  public: '#7dd3fc',
}

export function Buildings({
  buildings,
  elevationById,
}: {
  buildings: Building[]
  elevationById: Record<string, number>
}) {
  useCursor(false)

  const items = useMemo(
    () =>
      buildings.map((building) => ({
        id: building.id,
        position: [
          building.location.x * METERS_TO_UNITS,
          elevationToHeight(elevationById[building.region_id] ?? 0) +
            REGION_BASE +
            building.height * METERS_TO_UNITS * 0.5,
          building.location.y * METERS_TO_UNITS,
        ] as [number, number, number],
        scale: [
          building.width * METERS_TO_UNITS,
          building.height * METERS_TO_UNITS,
          building.depth * METERS_TO_UNITS,
        ] as [number, number, number],
        color: USE_COLORS[building.use],
      })),
    [buildings, elevationById],
  )

  return (
    <Instances limit={1200} range={items.length} castShadow receiveShadow frustumCulled>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial roughness={0.75} metalness={0.08} />
      {items.map((item) => (
        <Instance key={item.id} position={item.position} scale={item.scale} color={item.color} />
      ))}
    </Instances>
  )
}
