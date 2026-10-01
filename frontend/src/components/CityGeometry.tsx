import { useMemo } from 'react'
import { Instance, Instances, Line } from '@react-three/drei'
import type { Road, Tree, Waterway } from '../types'
import { METERS_TO_UNITS, elevationToHeight } from '../lib/geo'

const REGION_BASE = METERS_TO_UNITS * 40

const ROAD_WIDTH: Record<Road['class_'], number> = {
  arterial: 26,
  collector: 16,
  local: 10,
}

const ROAD_COLOR: Record<Road['class_'], string> = {
  arterial: '#64748b',
  collector: '#4b5563',
  local: '#3f4650',
}

export function Roads({
  roads,
  elevationById,
  showEmergencyRoutes,
}: {
  roads: Road[]
  elevationById: Record<string, number>
  showEmergencyRoutes: boolean
}) {
  const drawn = useMemo(
    () =>
      roads.map((road) => ({
        road,
        points: road.path.map((point) => {
          const base = elevationToHeight(elevationById[road.region_id] ?? 0) + REGION_BASE
          return [
            point.x * METERS_TO_UNITS,
            base + 0.6,
            -point.y * METERS_TO_UNITS,
          ] as [number, number, number]
        }),
      })),
    [roads, elevationById],
  )

  return (
    <group>
      {drawn.map(({ road, points }) => (
        <Line
          key={road.id}
          points={points}
          color={showEmergencyRoutes && road.critical ? '#f59e0b' : ROAD_COLOR[road.class_]}
          lineWidth={ROAD_WIDTH[road.class_]}
        />
      ))}
    </group>
  )
}

export function Vegetation({
  trees,
  elevationById,
}: {
  trees: Tree[]
  elevationById: Record<string, number>
}) {
  const items = useMemo(
    () =>
      trees.map((tree) => {
        const base = elevationToHeight(elevationById[tree.region_id] ?? 0) + REGION_BASE
        const scale = METERS_TO_UNITS
        return {
          id: tree.id,
          position: [
            tree.location.x * scale,
            base + tree.height * scale * 0.5,
            -tree.location.y * scale,
          ] as [number, number, number],
          scale: [tree.radius * 2 * scale, tree.height * scale, tree.radius * 2 * scale] as [
            number,
            number,
            number,
          ],
        }
      }),
    [trees, elevationById],
  )

  return (
    <Instances limit={600} range={items.length} castShadow frustumCulled>
      <coneGeometry args={[0.5, 1, 6]} />
      <meshStandardMaterial color="#15803d" roughness={0.9} metalness={0} />
      {items.map((item) => (
        <Instance key={item.id} position={item.position} scale={item.scale} />
      ))}
    </Instances>
  )
}

export function Waterways({
  waterways,
  riskByRegion,
  regionForWaterway,
  visible,
}: {
  waterways: Waterway[]
  riskByRegion: Record<string, number>
  regionForWaterway: Record<string, string>
  visible: boolean
}) {
  if (!visible) return null
  return (
    <group>
      {waterways.map((waterway) => {
        const risk = riskByRegion[regionForWaterway[waterway.id] ?? ''] ?? 0
        const color = risk >= 0.62 ? '#f87171' : risk >= 0.34 ? '#fbbf24' : '#38bdf8'
        const width = Math.max(1.5, Math.min(7, waterway.width_m * METERS_TO_UNITS * 0.8))
        return (
          <Line
            key={waterway.id}
            points={waterway.path.map(
              (point) =>
                [
                  point.x * METERS_TO_UNITS,
                  REGION_BASE + 1.2,
                  -point.y * METERS_TO_UNITS,
                ] as [number, number, number],
            )}
            color={color}
            lineWidth={width}
            transparent
            opacity={0.8}
          />
        )
      })}
    </group>
  )
}
