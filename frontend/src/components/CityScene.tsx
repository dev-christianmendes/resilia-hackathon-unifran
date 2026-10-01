import { useCallback, useMemo } from 'react'
import { Canvas, type ThreeEvent } from '@react-three/fiber'
import { Html, OrbitControls, PerspectiveCamera } from '@react-three/drei'
import type {
  Building,
  Facility,
  Intervention,
  LayerKey,
  Region,
  RegionResult,
  Road,
  ScenarioType,
  SimulationResult,
  Tree,
} from '../types'
import { METERS_TO_UNITS, regionAt } from '../lib/geo'
import { Buildings } from './Buildings'
import { Facilities, RegionLabel } from './Facilities'
import { FloodOverlay, HeatEffect, RainEffect } from './ClimateEffects'
import { Interventions, PlacementGhost } from './Interventions'
import { Roads, Vegetation } from './CityGeometry'
import { Terrain } from './Terrain'

const REGION_BASE = METERS_TO_UNITS * 40
/** Large enough to stay under the camera at any zoom level used by the demo. */
const PLANE_SIZE = 400

interface SceneProps {
  regions: Region[]
  buildings: Building[]
  roads: Road[]
  trees: Tree[]
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
  buildings,
  roads,
  trees,
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
        showRisk={layers.risk && hasResult}
        showCriticalAreas={layers.criticalAreas}
        showTerrain={layers.terrain}
        showPopulation={layers.population}
        riskByRegion={riskByRegion}
        selectedRegionId={selectedRegionId}
        onSelect={onSelectRegion}
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

      {regions.map((region) => (
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
                name={region.name}
                result={resultByRegion[region.id] ?? null}
                selected={region.id === selectedRegionId}
              />
            </button>
          </div>
        </Html>
      ))}

      {placement && (
        <>
          <PlacementGhost label="a intervenção" />
          <mesh
            rotation={[-Math.PI / 2, 0, 0]}
            position={[0, REGION_BASE + 4, 0]}
            onClick={(event) => {
              event.stopPropagation()
              onPlace(event.point.x / METERS_TO_UNITS, -event.point.z / METERS_TO_UNITS)
            }}
            onPointerOver={() => {
              document.body.style.cursor = 'crosshair'
            }}
            onPointerOut={() => {
              document.body.style.cursor = 'auto'
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
