import { useMemo } from 'react'
import { Html, Line } from '@react-three/drei'
import { Shape } from 'three'
import type { Region } from '../types'
import { METERS_TO_UNITS, elevationToHeight, polygonToScene } from '../lib/geo'
import { RISK_COLORS, formatNumber, riskFromColorLevel } from '../lib/theme'

const REGION_BASE = METERS_TO_UNITS * 40

interface TerrainProps {
  regions: Region[]
  showRisk: boolean
  showCriticalAreas: boolean
  showTerrain: boolean
  showPopulation: boolean
  riskByRegion: Record<string, number>
  selectedRegionId: string | null
  onSelect: (id: string) => void
}

export function Terrain({
  regions,
  showRisk,
  showCriticalAreas,
  showTerrain,
  showPopulation,
  riskByRegion,
  selectedRegionId,
  onSelect,
}: TerrainProps) {
  const shapes = useMemo(
    () => regions.map((region) => ({ region, shape: regionShape(region) })),
    [regions],
  )

  return (
    <group>
      {showTerrain && (
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow>
          <planeGeometry args={[METERS_TO_UNITS * 12000, METERS_TO_UNITS * 12000]} />
          <meshStandardMaterial color="#0b1016" roughness={1} metalness={0} />
        </mesh>
      )}

      {shapes.map(({ region, shape }) => {
        const y = elevationToHeight(region.metrics.elevation_m) + REGION_BASE
        const risk = riskByRegion[region.id] ?? 0
        const selected = region.id === selectedRegionId
        const fill = showRisk
          ? RISK_COLORS[riskFromColorLevel(risk)]
          : showCriticalAreas
            ? region.metrics.flood_risk >= 0.7
              ? '#7f1d1d'
              : '#1e293b'
            : '#1e293b'
        const outline = polygonToScene(region.polygon)

        return (
          <group key={region.id}>
            <mesh
              position={[0, y, 0]}
              rotation={[-Math.PI / 2, 0, 0]}
              onClick={(event) => {
                event.stopPropagation()
                onSelect(region.id)
              }}
              onPointerOver={() => {
                document.body.style.cursor = 'pointer'
              }}
              onPointerOut={() => {
                document.body.style.cursor = 'auto'
              }}
            >
              <shapeGeometry args={[shape]} />
              <meshStandardMaterial
                color={fill}
                transparent
                opacity={showRisk || showCriticalAreas ? 0.65 : 0.32}
                roughness={0.85}
                metalness={0.05}
                emissive={selected ? fill : '#000000'}
                emissiveIntensity={selected ? 0.6 : 0}
              />
            </mesh>

            {selected && (
              <Line
                points={outline.map(([x, z]) => [x, y + 0.06, z])}
                color="#38bdf8"
                lineWidth={2.5}
              />
            )}
            <Line
              points={outline.map(([x, z]) => [x, y + 0.02, z])}
              color={selected ? '#7dd3fc' : '#3f4a5a'}
              lineWidth={selected ? 3 : 1.2}
            />

            {showPopulation && (
              <Html
                position={[
                  region.centroid.x * METERS_TO_UNITS,
                  y + 4,
                  region.centroid.y * METERS_TO_UNITS,
                ]}
                center
                distanceFactor={90}
                style={{ pointerEvents: 'none' }}
              >
                <div className="rounded-md border border-white/15 bg-slate-900/85 px-2 py-1 text-[11px] font-semibold whitespace-nowrap text-slate-100">
                  {formatNumber(region.metrics.population)}
                </div>
              </Html>
            )}
          </group>
        )
      })}
    </group>
  )
}

function regionShape(region: Region): Shape {
  const shape = new Shape()
  region.polygon.forEach((point, index) => {
    const x = point.x * METERS_TO_UNITS
    const y = -point.y * METERS_TO_UNITS
    if (index === 0) shape.moveTo(x, y)
    else shape.lineTo(x, y)
  })
  shape.closePath()
  return shape
}
