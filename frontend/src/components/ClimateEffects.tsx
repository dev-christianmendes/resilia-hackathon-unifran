import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import * as THREE from 'three'
import type { Region, ScenarioType } from '../types'
import { METERS_TO_UNITS, elevationToHeight } from '../lib/geo'
import { RISK_COLORS, riskFromColorLevel } from '../lib/theme'

const REGION_BASE = METERS_TO_UNITS * 40
const RAIN_COUNT = 1400

/** Deterministic pseudo-random so the rain field is stable across re-renders. */
function rainField(): Float32Array {
  const spread = METERS_TO_UNITS * 7000
  const data = new Float32Array(RAIN_COUNT * 3)
  let seed = 20240517
  const next = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648
    return seed / 2147483648
  }
  for (let i = 0; i < RAIN_COUNT; i += 1) {
    data[i * 3] = (next() - 0.5) * spread
    data[i * 3 + 1] = next() * 420
    data[i * 3 + 2] = (next() - 0.5) * spread
  }
  return data
}

/** Heavy rain: a falling particle field over the whole city. */
export function RainEffect({ intensity }: { intensity: number }) {
  const points = useRef<THREE.Points>(null)
  const positions = useMemo(() => rainField(), [])

  useFrame((_, delta) => {
    if (!points.current) return
    const array = points.current.geometry.attributes.position.array as Float32Array
    const fall = 260 * (0.4 + intensity)
    for (let i = 1; i < array.length; i += 3) {
      array[i] -= delta * fall
      if (array[i] < -20) array[i] = 420
    }
    points.current.geometry.attributes.position.needsUpdate = true
  })

  if (intensity <= 0.01) return null

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color="#7dd3fc"
        size={1.1}
        transparent
        opacity={0.25 + intensity * 0.45}
        sizeAttenuation
        depthWrite={false}
      />
    </points>
  )
}

/** Standing water pooled inside the regions the engine marked as flooded. */
export function FloodOverlay({
  regions,
  riskByRegion,
  visible,
}: {
  regions: Region[]
  riskByRegion: Record<string, number>
  visible: boolean
}) {
  const flood = useMemo(
    () =>
      regions
        .map((region) => ({ region, risk: riskByRegion[region.id] ?? 0 }))
        .filter(({ risk }) => risk >= 0.34)
        .sort((a, b) => b.risk - a.risk),
    [regions, riskByRegion],
  )

  if (!visible) return null

  return (
    <group>
      {flood.map(({ region, risk }) => {
        const y = elevationToHeight(region.metrics.elevation_m) + REGION_BASE + 0.4
        const level = riskFromColorLevel(risk) === 'high' ? 1.6 : 0.8
        const shape = new THREE.Shape()
        region.polygon.forEach((point, index) => {
          const x = point.x * METERS_TO_UNITS
          const y2 = -point.y * METERS_TO_UNITS
          if (index === 0) shape.moveTo(x, y2)
          else shape.lineTo(x, y2)
        })
        shape.closePath()
        return (
          <mesh key={region.id} position={[0, y + level, 0]} rotation={[-Math.PI / 2, 0, 0]}>
            <shapeGeometry args={[shape]} />
            <meshStandardMaterial
              color={RISK_COLORS[riskFromColorLevel(risk)]}
              transparent
              opacity={0.28 + risk * 0.3}
              roughness={0.15}
              metalness={0.5}
            />
          </mesh>
        )
      })}
    </group>
  )
}

/** Heat wave: a warm haze plus a sun marker, no water on the ground. */
export function HeatEffect({
  regions,
  riskByRegion,
  intensity,
  visible,
  scenarioType,
}: {
  regions: Region[]
  riskByRegion: Record<string, number>
  intensity: number
  visible: boolean
  scenarioType: ScenarioType
}) {
  const sun = useRef<THREE.Mesh>(null)
  const hottest = useMemo(
    () =>
      [...regions].sort(
        (a, b) => (riskByRegion[b.id] ?? 0) - (riskByRegion[a.id] ?? 0),
      )[0],
    [regions, riskByRegion],
  )
  /** The haze has to clear the highest peak or it renders underground. */
  const ceiling = useMemo(() => {
    const highest = Math.max(...regions.map((r) => elevationToHeight(r.metrics.elevation_m)))
    return (Number.isFinite(highest) ? highest : REGION_BASE) + REGION_BASE + 4
  }, [regions])

  useFrame(({ clock }) => {
    if (!sun.current) return
    const pulse = 1 + Math.sin(clock.elapsedTime * 1.6) * 0.06
    sun.current.scale.setScalar(pulse)
  })

  if (!visible || scenarioType !== 'heat_wave' || !hottest) return null

  return (
    <group>
      <mesh
        ref={sun}
        position={[
          hottest.centroid.x * METERS_TO_UNITS,
          elevationToHeight(hottest.metrics.elevation_m) + REGION_BASE + 26,
          -hottest.centroid.y * METERS_TO_UNITS,
        ]}
      >
        <sphereGeometry args={[6, 20, 20]} />
        <meshBasicMaterial color="#fb923c" transparent opacity={0.55 + intensity * 0.35} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, ceiling, 0]}>
        <planeGeometry args={[METERS_TO_UNITS * 9000, METERS_TO_UNITS * 9000]} />
        <meshBasicMaterial color="#f97316" transparent opacity={0.06 + intensity * 0.14} />
      </mesh>
    </group>
  )
}

/** Lightweight visual cues for hazards that do not need a full particle system. */
export function HazardEffect({
  scenarioType,
  intensity,
  visible,
}: {
  scenarioType: ScenarioType
  intensity: number
  visible: boolean
}) {
  if (!visible || intensity <= 0.01 || scenarioType === 'extreme_rain' || scenarioType === 'heat_wave') {
    return null
  }

  const color =
    scenarioType === 'hailstorm'
      ? '#60a5fa'
      : scenarioType === 'windstorm'
        ? '#14b8a6'
        : '#ef4444'

  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, REGION_BASE + 22, 0]}>
      <planeGeometry args={[METERS_TO_UNITS * 9000, METERS_TO_UNITS * 9000]} />
      <meshBasicMaterial color={color} transparent opacity={0.025 + intensity * 0.08} />
    </mesh>
  )
}
