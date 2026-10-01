import { useRef } from 'react'
import { Html, useCursor } from '@react-three/drei'
import { useFrame } from '@react-three/fiber'
import type { Group } from 'three'
import type { Intervention } from '../types'
import { METERS_TO_UNITS, elevationToHeight } from '../lib/geo'
import { INTERVENTION_META } from '../lib/theme'

const REGION_BASE = METERS_TO_UNITS * 40

interface Props {
  interventions: Intervention[]
  elevationById: Record<string, number>
  onSelectRegion: (id: string) => void
}

export function Interventions({ interventions, elevationById, onSelectRegion }: Props) {
  useCursor(false)

  return (
    <group>
      {interventions.map((intervention) => {
        const meta = INTERVENTION_META[intervention.type]
        const y =
          elevationToHeight(elevationById[intervention.region_id] ?? 0) + REGION_BASE + 1
        return (
          <group
            key={intervention.id}
            position={[
              intervention.location.x * METERS_TO_UNITS,
              y,
              -intervention.location.y * METERS_TO_UNITS,
            ]}
            onClick={(event) => {
              event.stopPropagation()
              onSelectRegion(intervention.region_id)
            }}
          >
            <mesh castShadow>
              <cylinderGeometry args={[2.6, 2.6, 1.2, 20]} />
              <meshStandardMaterial
                color={meta.color}
                emissive={meta.color}
                emissiveIntensity={0.6}
                roughness={0.3}
                metalness={0.2}
              />
            </mesh>
            <mesh position={[0, 1.4, 0]}>
              <torusGeometry args={[1.9, 0.35, 12, 24]} />
              <meshBasicMaterial color={meta.color} />
            </mesh>
            <Html center distanceFactor={80} position={[0, 5, 0]} style={{ pointerEvents: 'none' }}>
              <div
                className="rounded border px-1.5 py-0.5 text-[10px] font-semibold whitespace-nowrap text-slate-950"
                style={{ backgroundColor: meta.color }}
              >
                {meta.icon} {meta.label}
              </div>
            </Html>
          </group>
        )
      })}
    </group>
  )
}

/** Pulsing marker shown while the user is choosing where to place an intervention. */
export function PlacementGhost({ label }: { label: string }) {
  const group = useRef<Group>(null)
  useCursor(true)

  useFrame(({ clock }) => {
    if (group.current) {
      const scale = 1 + Math.sin(clock.elapsedTime * 3.2) * 0.09
      group.current.scale.setScalar(scale)
    }
  })

  return (
    <group ref={group}>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[3.2, 4.4, 32]} />
        <meshBasicMaterial color="#38bdf8" transparent opacity={0.75} side={2} />
      </mesh>
      <Html center distanceFactor={90} position={[0, 9, 0]} style={{ pointerEvents: 'none' }}>
        <div className="rounded bg-sky-500 px-2 py-1 text-[11px] font-semibold whitespace-nowrap text-slate-950">
          Clique na cidade para posicionar {label}
        </div>
      </Html>
    </group>
  )
}
