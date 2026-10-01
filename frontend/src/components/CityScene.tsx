import { useCallback, useMemo, useState } from 'react'
import { Canvas, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls, PerspectiveCamera } from '@react-three/drei'
import type {
  Building,
  Facility,
  Intervention,
  LayerKey,
  Point,
  Region,
  RegionResult,
  Road,
  ScenarioType,
  SimulationResult,
  Tree,
  Waterway,
} from '../types'
import { METERS_TO_UNITS, regionAt } from '../lib/geo'
import { Buildings } from './Buildings'
import { Facilities, RegionLabel } from './Facilities'
import { FloodOverlay, HeatEffect, RainEffect } from './ClimateEffects'
import { Interventions, PlacementGhost } from './Interventions'
import { Roads, Vegetation, Waterways } from './CityGeometry'
import { Terrain } from './Terrain'

const REGION_BASE = METERS_TO_UNITS * 40
/** Large enough to stay under the camera at any zoom level used by the demo. */
const PLANE_SIZE = 400
/** One shared height for the placement plane and its ghost, so the ring the
 * user aims at is exactly the surface the click lands on. */
const PLACEMENT_PLANE_Y = REGION_BASE + 4

interface SceneProps {
  regions: Region[]
  boundary: Point[]
  buildings: Building[]
  roads: Road[]
  trees: Tree[]
  waterways: Waterway[]
  facilities: Facility[]
  interventions: Intervention[]
  result: SimulationResult | null
  scenarioType: ScenarioType
  intensity: number
  layers: Record<LayerKey, boolean>
  selectedRegionId: string | null
  placement: Intervention | null
  onSelectRegion: (id: string | null) => void
  onPlace: (x: number, y: number) => void
}

export function CityScene(props: SceneProps) {
  const { scenarioType } = props
  return (
    <Canvas
      shadows
      dpr={[1, 1.75]}
      gl={{ antialias: true, powerPreference: 'high-performance' }}
      onPointerMissed={() => props.onSelectRegion(null)}
      className="h-full w-full"
    >
      <color attach="background" args={['#05080d']} />
      <fog attach="fog" args={['#05080d', 160, 460]} />
      <PerspectiveCamera makeDefault position={[0, 165, 205]} fov={45} near={1} far={3000} />
      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.08}
        minDistance={45}
        maxDistance={430}
        maxPolarAngle={Math.PI / 2.1}
        target={[0, 0, 0]}
      />

      <hemisphereLight args={['#93c5fd', '#0f172a', scenarioType === 'heat_wave' ? 0.95 : 0.65]} />
      <directionalLight
        position={[90, 170, 70]}
        intensity={scenarioType === 'heat_wave' ? 2.5 : 1.6}
        color={scenarioType === 'heat_wave' ? '#fdba74' : '#e2e8f0'}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-camera-far={600}
        shadow-camera-left={-160}
        shadow-camera-right={160}
        shadow-camera-top={160}
        shadow-camera-bottom={-160}
      />

      <CityContents {...props} />
    </Canvas>
  )
}

function CityContents({
  regions,
  boundary,
  buildings,
  roads,
  trees,
  waterways,
  facilities,
  interventions,
  result,
  scenarioType,
  intensity,
  layers,
  selectedRegionId,
  placement,
  onSelectRegion,
  onPlace,
}: SceneProps) {
  const elevationById = useMemo(
    () => Object.fromEntries(regions.map((r) => [r.id, r.metrics.elevation_m])),
    [regions],
  )

  const riskByRegion = useMemo(
    () => Object.fromEntries((result?.regions ?? []).map((r) => [r.region_id, r.risk])),
    [result],
  )

  const riskByFacilityId = useMemo(() => {
    const map: Record<string, number> = {}
    if (!result) return map
    for (const regionResult of result.regions) {
      const region = regions.find((r) => r.id === regionResult.region_id)
      for (const facility of region?.facilities ?? []) {
        map[facility.id] = regionResult.risk
      }
    }
    return map
  }, [result, regions])

  const resultByRegion = useMemo(() => {
    const map: Record<string, RegionResult> = {}
    for (const regionResult of result?.regions ?? []) map[regionResult.region_id] = regionResult
    return map
  }, [result])

  const regionForWaterway = useMemo(() => {
    const map: Record<string, string> = {}
    for (const waterway of waterways) {
      const point = waterway.path[Math.floor(waterway.path.length / 2)]
      if (!point) continue
      let closest: Region | null = null
      let distance = Number.POSITIVE_INFINITY
      for (const region of regions) {
        const next = Math.hypot(region.centroid.x - point.x, region.centroid.y - point.y)
        if (next < distance) {
          closest = region
          distance = next
        }
      }
      if (closest) map[waterway.id] = closest.id
    }
    return map
  }, [regions, waterways])

  const [placementPoint, setPlacementPoint] = useState<[number, number, number] | null>(null)
  const [hoveredRegionId, setHoveredRegionId] = useState<string | null>(null)

  const handleClick = useCallback(
    (event: ThreeEvent<MouseEvent>) => {
      event.stopPropagation()
      const x = event.point.x / METERS_TO_UNITS
      const y = -event.point.z / METERS_TO_UNITS
      if (placement) {
        onPlace(x, y)
        return
      }
      onSelectRegion(regionAt(regions, x, y)?.id ?? null)
    },
    [placement, onPlace, onSelectRegion, regions],
  )

  const hasResult = result !== null

  return (
    <group onClick={handleClick}>
      <Terrain
        regions={regions}
        boundary={boundary}
        showRisk={layers.risk && hasResult}
        showCriticalAreas={layers.criticalAreas}
        showTerrain={layers.terrain}
        showPopulation={layers.population}
        riskByRegion={riskByRegion}
        selectedRegionId={selectedRegionId}
        onSelect={onSelectRegion}
        onHover={setHoveredRegionId}
      />

      {layers.buildings && <Buildings buildings={buildings} elevationById={elevationById} />}
      {layers.roads && (
        <Roads
          roads={roads}
          elevationById={elevationById}
          showEmergencyRoutes={layers.emergencyRoutes}
        />
      )}
      {layers.vegetation && <Vegetation trees={trees} elevationById={elevationById} />}
      <Waterways
        waterways={waterways}
        riskByRegion={riskByRegion}
        regionForWaterway={regionForWaterway}
        visible={layers.terrain || layers.risk}
      />
      {layers.facilities && (
        <Facilities
          facilities={facilities}
          elevationById={elevationById}
          riskByFacilityId={riskByFacilityId}
          onSelect={onSelectRegion}
        />
      )}

      <Interventions
        interventions={interventions}
        elevationById={elevationById}
        onSelectRegion={onSelectRegion}
      />

      {hasResult && scenarioType === 'extreme_rain' && (
        <>
          <RainEffect intensity={intensity} />
          <FloodOverlay regions={regions} riskByRegion={riskByRegion} visible={layers.risk} />
        </>
      )}
      {hasResult && scenarioType === 'heat_wave' && (
        <HeatEffect
          regions={regions}
          riskByRegion={riskByRegion}
          intensity={intensity}
          visible={layers.risk}
          scenarioType={scenarioType}
        />
      )}

      {layers.terrain && (
        <gridHelper
          args={[METERS_TO_UNITS * 6000, 30, '#1e293b', '#0f1727']}
          position={[0, REGION_BASE - 0.15, 0]}
        />
      )}

      {labelRegions(regions, resultByRegion, selectedRegionId, hoveredRegionId).map((region) => (
        <Html
          key={region.id}
          position={[region.centroid.x * METERS_TO_UNITS, 16, -region.centroid.y * METERS_TO_UNITS]}
          center
          distanceFactor={190}
          style={{ pointerEvents: 'none' }}
        >
          <div className="pointer-events-auto">
            <button
              type="button"
              // drei renders <Html> into a portal above the canvas; without this the
              // click bubbles to the R3F container and clears the selection.
              onClick={(event) => {
                event.stopPropagation()
                onSelectRegion(region.id)
              }}
              className="cursor-pointer"
            >
              <RegionLabel
                name={friendlyRegionName(region.name)}
                result={resultByRegion[region.id] ?? null}
                selected={region.id === selectedRegionId}
              />
            </button>
          </div>
        </Html>
      ))}

      {placement && (
        <>
          <PlacementGhost label="a intervenção" point={placementPoint} />
          <mesh
            rotation={[-Math.PI / 2, 0, 0]}
            position={[0, PLACEMENT_PLANE_Y, 0]}
            onPointerMove={(event) => {
              setPlacementPoint([event.point.x, PLACEMENT_PLANE_Y, event.point.z])
            }}
            onPointerOut={() => {
              setPlacementPoint(null)
              document.body.style.cursor = 'auto'
            }}
            onClick={(event) => {
              event.stopPropagation()
              onPlace(event.point.x / METERS_TO_UNITS, -event.point.z / METERS_TO_UNITS)
            }}
            onPointerOver={() => {
              document.body.style.cursor = 'crosshair'
            }}
          >
            <planeGeometry args={[PLANE_SIZE, PLANE_SIZE]} />
            <meshBasicMaterial transparent opacity={0} depthWrite={false} />
          </mesh>
        </>
      )}
    </group>
  )
}

function labelRegions(
  regions: Region[],
  results: Record<string, RegionResult>,
  selectedId: string | null,
  hoveredId: string | null,
): Region[] {
  const ranked = [...regions].sort(
    (a, b) => (results[b.id]?.risk ?? 0) - (results[a.id]?.risk ?? 0),
  )
  const labels: Region[] = []
  for (const region of ranked) {
    if (region.id !== selectedId && region.id !== hoveredId && labels.length >= 7) continue
    const overlaps = labels.some(
      (other) => Math.hypot(region.centroid.x - other.centroid.x, region.centroid.y - other.centroid.y) < 180,
    )
    if (overlaps && region.id !== selectedId && region.id !== hoveredId) continue
    labels.push(region)
  }
  return labels
}

function friendlyRegionName(name: string): string {
  const base = name.replace(/\s+\(\d+\)$/, '')
  return base === "Curso d'água sem nome" ? 'Curso sem nome' : base
}
