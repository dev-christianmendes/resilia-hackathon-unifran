import { Html } from '@react-three/drei'
import type { Facility, RegionResult } from '../types'
import { METERS_TO_UNITS, elevationToHeight } from '../lib/geo'
import { FACILITY_META, RISK_COLORS, riskFromColorLevel } from '../lib/theme'

const REGION_BASE = METERS_TO_UNITS * 40

export function Facilities({
  facilities,
  elevationById,
  riskByFacilityId,
  onSelect,
}: {
  facilities: Facility[]
  elevationById: Record<string, number>
  riskByFacilityId: Record<string, number>
  onSelect: (regionId: string) => void
}) {
  return (
    <group>
      {facilities.map((facility) => {
        const meta = FACILITY_META[facility.type]
        const y =
          elevationToHeight(elevationById[facility.region_id] ?? 0) + REGION_BASE + 3.4
        const risk = riskByFacilityId[facility.id]
        const color = risk !== undefined ? RISK_COLORS[riskFromColorLevel(risk)] : meta.color

        return (
          <group
            key={facility.id}
            position={[facility.location.x * METERS_TO_UNITS, y, -facility.location.y * METERS_TO_UNITS]}
            onClick={(event) => {
              event.stopPropagation()
              onSelect(facility.region_id)
            }}
            onPointerOver={() => {
              document.body.style.cursor = 'pointer'
            }}
            onPointerOut={() => {
              document.body.style.cursor = 'auto'
            }}
          >
            <mesh castShadow>
              <octahedronGeometry args={[1.9, 0]} />
              <meshStandardMaterial
                color={color}
                emissive={color}
                emissiveIntensity={facility.critical ? 0.7 : 0.25}
                roughness={0.4}
              />
            </mesh>
            {facility.critical && (
              <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2.4, 0]}>
                <ringGeometry args={[2.6, 3.4, 24]} />
                <meshBasicMaterial color={color} transparent opacity={0.55} side={2} />
              </mesh>
            )}
            <Html center distanceFactor={70} position={[0, 4.5, 0]} style={{ pointerEvents: 'none' }}>
              <div className="rounded border border-white/10 bg-slate-950/90 px-1.5 py-0.5 text-[10px] font-medium whitespace-nowrap text-slate-100">
                {meta.icon} {facility.name}
              </div>
            </Html>
          </group>
        )
      })}
    </group>
  )
}

/** Plain markup — the caller must wrap this in drei's `<Html>`. */
export function RegionLabel({
  name,
  result,
  selected,
}: {
  name: string
  result: RegionResult | null
  selected: boolean
}) {
  const color = result ? RISK_COLORS[result.risk_level] : '#64748b'
  return (
    <div
      className={`rounded-lg border px-2.5 py-1.5 text-center whitespace-nowrap backdrop-blur-sm transition-colors ${
        selected ? 'border-sky-400 bg-sky-950/90' : 'border-white/10 bg-slate-950/80'
      }`}
    >
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-100">
        <span className="inline-block size-2 rounded-full" style={{ backgroundColor: color }} />
        {name}
      </div>
      {result && (
        <div className="text-[10px] text-slate-400">
          risco {result.risk.toFixed(2)} · {result.affected_population.toLocaleString('pt-BR')}{' '}
          afetados
        </div>
      )}
    </div>
  )
}
