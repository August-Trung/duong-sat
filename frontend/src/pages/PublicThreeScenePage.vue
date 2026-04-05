<script setup>
import maplibregl from 'maplibre-gl'
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  Box, Layers, Info, Map as MapIcon,
  Navigation, Zap, Shield, AlertCircle,
  Loader2, Maximize2, MousePointer2, Compass
} from 'lucide-vue-next'
import { fetchCrossings, fetchScene3DManifest, fetchScene3DTile } from '../api'
import { locateUser } from '../stores/publicData'

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY || ''
const VIEWPORT_PADDING_DEGREES = 0.02
const DEFAULT_PITCH = 66
const DEFAULT_BEARING = -22
const DEFAULT_TERRAIN_EXAGGERATION = 1.7

const mapRoot = ref(null)
const sceneShell = ref(null)

const state = reactive({
  loading: true,
  error: '',
  manifest: null,
  crossings: [],
  loadedTiles: 0,
  showStats: false,
  freeLook: false,
  fullscreen: false,
  locating: false,
  locationError: '',
  userLocation: null,
  rendered: {
    crossings: 0,
    roads: 0,
    railways: 0,
    buildings: 0,
    landuse: 0,
    water: 0,
  },
})

let map
let syncTimer = null
let syncRequestId = 0
const tileCache = new Map()

function createFallbackStyle() {
  return {
    version: 8,
    sources: {
      carto: {
        type: 'raster',
        tiles: ['https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png'],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap contributors, &copy; CARTO',
      },
    },
    layers: [
      {
        id: 'carto-raster',
        type: 'raster',
        source: 'carto',
      },
    ],
  }
}

function currentStyle() {
  if (MAPTILER_KEY) {
    return `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`
  }

  return createFallbackStyle()
}

function emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] }
}

function bienHoaFocusBounds() {
  if (state.crossings.length) {
    return state.crossings.reduce(
      (acc, crossing) => ({
        west: Math.min(acc.west, Number(crossing.longitude)),
        south: Math.min(acc.south, Number(crossing.latitude)),
        east: Math.max(acc.east, Number(crossing.longitude)),
        north: Math.max(acc.north, Number(crossing.latitude)),
      }),
      {
        west: Number.POSITIVE_INFINITY,
        south: Number.POSITIVE_INFINITY,
        east: Number.NEGATIVE_INFINITY,
        north: Number.NEGATIVE_INFINITY,
      }
    )
  }

  const crossingTiles = (state.manifest?.tiles || []).filter(
    (tile) => (tile.featureCounts?.crossings || 0) > 0
  )
  const focusTiles = crossingTiles.length ? crossingTiles : state.manifest?.tiles || []

  if (!focusTiles.length) return null

  return focusTiles.reduce(
    (acc, tile) => ({
      west: Math.min(acc.west, tile.bounds.west),
      south: Math.min(acc.south, tile.bounds.south),
      east: Math.max(acc.east, tile.bounds.east),
      north: Math.max(acc.north, tile.bounds.north),
    }),
    {
      west: Number.POSITIVE_INFINITY,
      south: Number.POSITIVE_INFINITY,
      east: Number.NEGATIVE_INFINITY,
      north: Number.NEGATIVE_INFINITY,
    }
  )
}

function squareDistance(a, b) {
  return (a.longitude - b.longitude) ** 2 + (a.latitude - b.latitude) ** 2
}

function intersectsBounds(a, b) {
  return !(a.east < b.west || a.west > b.east || a.north < b.south || a.south > b.north)
}

function pointInBounds(point, bounds) {
  const longitude = Number(point?.longitude)
  const latitude = Number(point?.latitude)
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return false

  return (
    longitude >= bounds.west &&
    longitude <= bounds.east &&
    latitude >= bounds.south &&
    latitude <= bounds.north
  )
}

function viewportBounds() {
  const bounds = map.getBounds()
  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  }
}

function paddedViewportBounds() {
  const bounds = map.getBounds()
  return {
    west: bounds.getWest() - VIEWPORT_PADDING_DEGREES,
    south: bounds.getSouth() - VIEWPORT_PADDING_DEGREES,
    east: bounds.getEast() + VIEWPORT_PADDING_DEGREES,
    north: bounds.getNorth() + VIEWPORT_PADDING_DEGREES,
  }
}

function desiredTiles() {
  if (!map || !state.manifest?.tiles?.length) return []

  const viewport = paddedViewportBounds()
  const center = map.getCenter()
  const zoom = map.getZoom()
  const maxVisibleTiles = zoom >= 15 ? 14 : zoom >= 14 ? 10 : zoom >= 13 ? 8 : 6

  return state.manifest.tiles
    .filter((tile) => intersectsBounds(tile.bounds, viewport))
    .sort(
      (left, right) =>
        squareDistance(left.center, center) - squareDistance(right.center, center)
    )
    .slice(0, maxVisibleTiles)
}

async function ensureTileLoaded(tileMeta) {
  if (tileCache.has(tileMeta.id)) {
    return tileCache.get(tileMeta.id)
  }

  const payload = await fetchScene3DTile(tileMeta.id)
  tileCache.set(tileMeta.id, payload)
  return payload
}

function coordinate(point) {
  const longitude = Number(point?.longitude)
  const latitude = Number(point?.latitude)
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return null
  return [longitude, latitude]
}

function closeRing(points) {
  const ring = points.filter(Boolean)
  if (ring.length < 3) return []

  const [firstLng, firstLat] = ring[0]
  const [lastLng, lastLat] = ring[ring.length - 1]
  if (firstLng !== lastLng || firstLat !== lastLat) {
    ring.push([firstLng, firstLat])
  }

  return ring.length >= 4 ? ring : []
}

function polygonCoordinates(feature) {
  const outer = closeRing((feature?.footprint || []).map(coordinate))
  if (!outer.length) return null

  const holes = (feature?.holes || [])
    .map((ring) => closeRing((ring || []).map(coordinate)))
    .filter((ring) => ring.length)

  return [outer, ...holes]
}

function metersToLatitudeDegrees(meters) {
  return meters / 111320
}

function metersToLongitudeDegrees(meters, latitude) {
  const cosine = Math.cos((latitude * Math.PI) / 180)
  const safeCosine = Math.max(Math.abs(cosine), 0.0001)
  return meters / (111320 * safeCosine)
}

function createCirclePolygon(center, radiusMeters, steps = 48) {
  const longitude = Number(center?.longitude)
  const latitude = Number(center?.latitude)
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) return null

  const coordinates = []
  for (let index = 0; index <= steps; index += 1) {
    const angle = (Math.PI * 2 * index) / steps
    const latOffset = metersToLatitudeDegrees(radiusMeters * Math.sin(angle))
    const lngOffset = metersToLongitudeDegrees(radiusMeters * Math.cos(angle), latitude)
    coordinates.push([longitude + lngOffset, latitude + latOffset])
  }

  return coordinates
}

function toCrossingFeatures(items) {
  return (items || [])
    .map((item) => {
      const point = item?.centerline ? coordinate(item) : [Number(item?.longitude), Number(item?.latitude)]
      if (!point || !Number.isFinite(point[0]) || !Number.isFinite(point[1])) return null

      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: point },
        properties: {
          id: item.id,
          code: item.code,
          name: item.name,
          riskLevel: item.riskLevel || item.risk_level,
          riskScore: item.riskScore || item.risk_score,
        },
      }
    })
    .filter(Boolean)
}

function toUserLocationFeatures() {
  if (!state.userLocation?.latitude || !state.userLocation?.longitude) return []

  return [
    {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [Number(state.userLocation.longitude), Number(state.userLocation.latitude)],
      },
      properties: {
        label: state.userLocation.label || 'Vị trí của tôi',
      },
    },
  ]
}

function toUserAccuracyFeatures() {
  if (!state.userLocation?.latitude || !state.userLocation?.longitude) return []

  const radiusMeters = Math.max(50, Number(state.userLocation.accuracy || 120))
  const polygon = createCirclePolygon(state.userLocation, radiusMeters)
  if (!polygon?.length) return []

  return [
    {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [polygon] },
      properties: {
        label: state.userLocation.label || 'Vị trí của tôi',
      },
    },
  ]
}

function toLineFeatures(items, featureType) {
  return (items || [])
    .map((item) => {
      const line = (item?.centerline || []).map(coordinate).filter(Boolean)
      if (line.length < 2) return null

      return {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: line },
        properties: {
          id: item.id,
          name: item.name || '',
          kind: item.kind || featureType,
          widthMeters: Number(item.widthMeters || (featureType === 'railway' ? 4 : 6)),
        },
      }
    })
    .filter(Boolean)
}

function toPolygonFeatures(items, featureType) {
  return (items || [])
    .map((item) => {
      const coordinates = polygonCoordinates(item)
      if (!coordinates) return null

      return {
        type: 'Feature',
        geometry: { type: 'Polygon', coordinates },
        properties: {
          id: item.id,
          name: item.name || '',
          kind: item.kind || featureType,
          color: item.color || '',
          heightMeters: Number(item.heightMeters || 0),
        },
      }
    })
    .filter(Boolean)
}

function source(name) {
  return map.getSource(name)
}

function ensureSceneSources() {
  const sources = [
    'scene-crossings',
    'scene-roads',
    'scene-railways',
    'scene-buildings',
    'scene-landuse',
    'scene-water',
    'scene-user-location',
    'scene-user-accuracy',
  ]

  sources.forEach((name) => {
    if (!source(name)) {
      map.addSource(name, {
        type: 'geojson',
        data: emptyFeatureCollection(),
      })
    }
  })
}

function ensureSceneLayers() {
  const layers = [
    {
      id: 'scene-water',
      type: 'fill',
      source: 'scene-water',
      paint: {
        'fill-color': ['coalesce', ['get', 'color'], '#72b1e0'],
        'fill-opacity': 0.62,
      },
    },
    {
      id: 'scene-landuse',
      type: 'fill',
      source: 'scene-landuse',
      paint: {
        'fill-color': ['coalesce', ['get', 'color'], '#9cc7a1'],
        'fill-opacity': 0.3,
      },
    },
    {
      id: 'scene-road-casing',
      type: 'line',
      source: 'scene-roads',
      paint: {
        'line-color': '#6f7983',
        'line-opacity': 0.9,
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          11,
          ['max', 2.5, ['/', ['coalesce', ['get', 'widthMeters'], 7], 1.6]],
          16,
          ['max', 8, ['/', ['coalesce', ['get', 'widthMeters'], 7], 1.05]],
        ],
      },
    },
    {
      id: 'scene-roads',
      type: 'line',
      source: 'scene-roads',
      paint: {
        'line-color': '#f7f4ee',
        'line-opacity': 1,
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          11,
          ['max', 1.4, ['/', ['coalesce', ['get', 'widthMeters'], 7], 2.2]],
          16,
          ['max', 6.5, ['/', ['coalesce', ['get', 'widthMeters'], 7], 1.35]],
        ],
      },
    },
    {
      id: 'scene-railways-casing',
      type: 'line',
      source: 'scene-railways',
      paint: {
        'line-color': '#f4f1e8',
        'line-opacity': 0.95,
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 2.6, 15, 7.8],
      },
    },
    {
      id: 'scene-railways',
      type: 'line',
      source: 'scene-railways',
      paint: {
        'line-color': '#183b54',
        'line-opacity': 1,
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 1.6, 15, 5.2],
      },
    },
    {
      id: 'scene-buildings',
      type: 'fill-extrusion',
      source: 'scene-buildings',
      minzoom: 12.5,
      paint: {
        'fill-extrusion-color': '#dccab1',
        'fill-extrusion-opacity': 0.95,
        'fill-extrusion-height': ['max', 4, ['coalesce', ['get', 'heightMeters'], 10]],
        'fill-extrusion-base': 0,
        'fill-extrusion-vertical-gradient': true,
      },
    },
    {
      id: 'scene-crossings-halo',
      type: 'circle',
      source: 'scene-crossings',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 10, 16, 18],
        'circle-color': 'rgba(214,69,93,0.18)',
        'circle-stroke-width': 2.5,
        'circle-stroke-color': 'rgba(255,255,255,0.92)',
      },
    },
    {
      id: 'scene-crossings',
      type: 'circle',
      source: 'scene-crossings',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 6, 16, 10.5],
        'circle-color': [
          'match',
          ['get', 'riskLevel'],
          'very_high',
          '#d6455d',
          'high',
          '#cd8c1c',
          'medium',
          '#d8a93a',
          'low',
          '#2f8f6f',
          '#4d6176',
        ],
        'circle-stroke-width': 2,
        'circle-stroke-color': '#ffffff',
      },
    },
    {
      id: 'scene-crossings-label',
      type: 'symbol',
      source: 'scene-crossings',
      minzoom: 13,
      layout: {
        'text-field': ['coalesce', ['get', 'code'], ['get', 'name']],
        'text-size': ['interpolate', ['linear'], ['zoom'], 13, 10, 16, 12],
        'text-offset': [0, 1.4],
        'text-anchor': 'top',
      },
      paint: {
        'text-color': '#14384a',
        'text-halo-color': 'rgba(255,255,255,0.95)',
        'text-halo-width': 1.2,
      },
    },
    {
      id: 'scene-user-accuracy',
      type: 'fill',
      source: 'scene-user-accuracy',
      paint: {
        'fill-color': '#93c5fd',
        'fill-opacity': 0.14,
      },
    },
    {
      id: 'scene-user-accuracy-outline',
      type: 'line',
      source: 'scene-user-accuracy',
      paint: {
        'line-color': '#3b82f6',
        'line-width': 1.2,
        'line-opacity': 0.9,
      },
    },
    {
      id: 'scene-user-location-halo',
      type: 'circle',
      source: 'scene-user-location',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 12, 16, 16],
        'circle-color': 'rgba(59,130,246,0.16)',
        'circle-stroke-width': 2,
        'circle-stroke-color': 'rgba(255,255,255,0.92)',
      },
    },
    {
      id: 'scene-user-location',
      type: 'circle',
      source: 'scene-user-location',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 6, 16, 8],
        'circle-color': '#3b82f6',
        'circle-stroke-width': 3,
        'circle-stroke-color': '#ffffff',
      },
    },
  ]

  layers.forEach((layer) => {
    if (!map.getLayer(layer.id)) {
      map.addLayer(layer)
    }
  })
}

function applyGeoJson(name, features) {
  source(name)?.setData({
    type: 'FeatureCollection',
    features,
  })
}

function updateRenderedStats(payloads, visibleTiles) {
  const bounds = viewportBounds()
  const crossingCount = state.crossings.filter((crossing) => pointInBounds(crossing, bounds)).length
  state.rendered = payloads.reduce(
    (acc, tile) => {
      acc.roads += tile.roads?.length || 0
      acc.railways += tile.railways?.length || 0
      acc.buildings += tile.buildings?.length || 0
      acc.landuse += tile.landuse?.length || 0
      acc.water += tile.water?.length || 0
      return acc
    },
    {
      crossings: 0,
      roads: 0,
      railways: 0,
      buildings: 0,
      landuse: 0,
      water: 0,
    }
  )
  state.rendered.crossings = crossingCount
  state.loadedTiles = visibleTiles.length
}

async function syncViewportData() {
  if (!map || !state.manifest) return

  const requestId = ++syncRequestId
  const tiles = desiredTiles()
  const payloads = await Promise.all(tiles.map((tile) => ensureTileLoaded(tile)))
  if (requestId !== syncRequestId) return

  updateRenderedStats(payloads, tiles)

  applyGeoJson('scene-crossings', toCrossingFeatures(state.crossings))
  applyGeoJson('scene-roads', payloads.flatMap((tile) => toLineFeatures(tile.roads, 'road')))
  applyGeoJson('scene-railways', payloads.flatMap((tile) => toLineFeatures(tile.railways, 'railway')))
  applyGeoJson('scene-buildings', payloads.flatMap((tile) => toPolygonFeatures(tile.buildings, 'building')))
  applyGeoJson('scene-landuse', payloads.flatMap((tile) => toPolygonFeatures(tile.landuse, 'landuse')))
  applyGeoJson('scene-water', payloads.flatMap((tile) => toPolygonFeatures(tile.water, 'water')))
  applyGeoJson('scene-user-location', toUserLocationFeatures())
  applyGeoJson('scene-user-accuracy', toUserAccuracyFeatures())
}

function queueViewportSync() {
  if (syncTimer) window.clearTimeout(syncTimer)
  syncTimer = window.setTimeout(() => {
    syncViewportData().catch((error) => {
      state.error = error.message || 'Không thể đồng bộ dữ liệu map 3D.'
    })
  }, 120)
}

function setupCrossingPopup() {
  map.on('click', 'scene-crossings', (event) => {
    const feature = event.features?.[0]
    if (!feature) return

    const [longitude, latitude] = feature.geometry.coordinates
    const { name, code, riskLevel, riskScore } = feature.properties
    new maplibregl.Popup({ closeButton: true, closeOnClick: true })
      .setLngLat([longitude, latitude])
      .setHTML(
        `<div class="p-2 min-w-[180px]">
          <h4 class="font-bold text-sm mb-1">${name || 'Điểm giao cắt'}</h4>
          <div class="flex flex-col gap-1 text-xs">
            <div class="flex justify-between">
              <span class="text-soft">Mã:</span>
              <span class="font-mono font-bold">${code || 'n/a'}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-soft">Mức độ:</span>
              <span class="font-bold ${riskLevel === 'very_high' ? 'text-danger' : 'text-brand'}">${riskLevel || 'unknown'}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-soft">Điểm rủi ro:</span>
              <span class="font-bold">${riskScore || 0}</span>
            </div>
          </div>
        </div>`
      )
      .addTo(map)
  })

  map.on('mouseenter', 'scene-crossings', () => {
    map.getCanvas().style.cursor = 'pointer'
  })

  map.on('mouseleave', 'scene-crossings', () => {
    map.getCanvas().style.cursor = ''
  })
}

function enableMapTilerTerrain() {
  if (!MAPTILER_KEY || map.getSource('maptiler-terrain')) return

  map.addSource('maptiler-terrain', {
    type: 'raster-dem',
    url: `https://api.maptiler.com/tiles/terrain-rgb-v2/tiles.json?key=${MAPTILER_KEY}`,
    tileSize: 256,
  })
  map.setTerrain({ source: 'maptiler-terrain', exaggeration: DEFAULT_TERRAIN_EXAGGERATION })
}

function configureLighting() {
  if (typeof map.setLight !== 'function') return

  map.setLight({
    anchor: 'map',
    color: '#fff4d6',
    intensity: 0.42,
    position: [1.4, 210, 38],
  })
}

function focusBienHoa() {
  const bounds = bienHoaFocusBounds()
  if (!bounds) return
  state.freeLook = false

  map.fitBounds(
    [
      [bounds.west, bounds.south],
      [bounds.east, bounds.north],
    ],
    {
      padding: 40,
      pitch: DEFAULT_PITCH,
      bearing: DEFAULT_BEARING,
      maxZoom: 14.6,
      duration: 0,
    }
  )
}

function toggleFreeLook() {
  if (!map) return

  state.freeLook = !state.freeLook
  if (state.freeLook) {
    map.easeTo({
      pitch: 48,
      bearing: 0,
      duration: 700,
      essential: true,
    })
    return
  }

  focusBienHoa()
}

async function toggleFullscreen() {
  if (!sceneShell.value) return

  if (document.fullscreenElement === sceneShell.value) {
    await document.exitFullscreen()
    return
  }

  await sceneShell.value.requestFullscreen()
}

function handleFullscreenChange() {
  state.fullscreen = document.fullscreenElement === sceneShell.value
  window.setTimeout(() => {
    map?.resize()
  }, 80)
}

async function locateAndFlyToUser() {
  if (!map || state.locating) return

  state.locating = true
  state.locationError = ''

  try {
    const location = await locateUser()
    state.userLocation = location

    applyGeoJson('scene-user-location', toUserLocationFeatures())
    applyGeoJson('scene-user-accuracy', toUserAccuracyFeatures())

    map.flyTo({
      center: [location.longitude, location.latitude],
      zoom: Math.max(map.getZoom(), 15),
      pitch: state.freeLook ? 48 : DEFAULT_PITCH,
      bearing: state.freeLook ? 0 : DEFAULT_BEARING,
      essential: true,
    })
  } catch (error) {
    state.locationError = error.message || 'Không thể lấy vị trí hiện tại.'
  } finally {
    state.locating = false
  }
}

function initializeMap() {
  if (map || !mapRoot.value || !state.manifest) return

  map = new maplibregl.Map({
    container: mapRoot.value,
    style: currentStyle(),
    center: [state.manifest.center.longitude, state.manifest.center.latitude],
    zoom: 13.2,
    pitch: DEFAULT_PITCH,
    bearing: DEFAULT_BEARING,
    antialias: true,
  })

  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')

  map.on('load', async () => {
    ensureSceneSources()
    ensureSceneLayers()
    setupCrossingPopup()
    enableMapTilerTerrain()
    configureLighting()
    focusBienHoa()
    await syncViewportData()
  })

  map.on('moveend', queueViewportSync)
}

async function loadScene() {
  state.loading = true
  state.error = ''

  try {
    const [manifest, crossings] = await Promise.all([fetchScene3DManifest(), fetchCrossings()])
    state.manifest = manifest
    state.crossings = crossings
    state.loading = false
    await nextTick()
    initializeMap()
  } catch (error) {
    state.error = error.message || 'Không thể tải scene 3D.'
  } finally {
    if (state.loading) {
      state.loading = false
    }
  }
}

onMounted(loadScene)

onMounted(() => {
  document.addEventListener('fullscreenchange', handleFullscreenChange)
})

onBeforeUnmount(() => {
  if (syncTimer) window.clearTimeout(syncTimer)
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  map?.remove()
})
</script>

<template>
  <div ref="sceneShell" class="scene3d-page relative w-full h-[calc(100vh-80px)] overflow-hidden bg-bg-strong"
    :class="{ 'h-screen': state.fullscreen }">
    <!-- Loading Overlay -->
    <div v-if="state.loading"
      class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-white/80 backdrop-blur-md">
      <div class="w-16 h-16 rounded-2xl bg-brand flex items-center justify-center shadow-xl shadow-brand/20 mb-6">
        <Loader2 class="text-white animate-spin" :size="32" />
      </div>
      <h3 class="text-xl font-bold text-text mb-2">Khởi tạo không gian 3D</h3>
      <p class="text-soft text-sm max-w-xs text-center">Đang tải manifest và dữ liệu địa hình MapLibre GL JS...</p>
    </div>

    <!-- Error Overlay -->
    <div v-else-if="state.error"
      class="absolute inset-0 z-50 flex flex-col items-center justify-center bg-white px-6 text-center">
      <div class="w-16 h-16 rounded-2xl bg-danger-soft flex items-center justify-center mb-6">
        <AlertCircle class="text-danger" :size="32" />
      </div>
      <h3 class="text-xl font-bold text-text mb-2">Lỗi khởi tạo</h3>
      <p class="text-soft text-sm mb-6 max-w-md">{{ state.error }}</p>
      <button @click="loadScene" class="primary-button">Thử lại</button>
    </div>

    <!-- Map Container -->
    <div ref="mapRoot" class="w-full h-full"></div>

    <!-- Floating UI Controls -->
    <div class="absolute top-8 left-8 z-40 flex flex-col gap-6 pointer-events-none">
      <!-- Scene Info Card -->
      <div
        class="pointer-events-auto bg-white/90 backdrop-blur-xl border border-line p-6 rounded-[32px] shadow-2xl shadow-black/10 w-80">
        <div class="flex items-center gap-4 mb-6">
          <div
            class="w-12 h-12 rounded-2xl bg-brand text-white flex items-center justify-center shadow-xl shadow-brand/20">
            <Box :size="24" />
          </div>
          <div>
            <h3 class="text-lg font-black text-text leading-tight">Digital Twin</h3>
            <p class="text-[10px] font-black text-soft uppercase tracking-widest">Biên Hòa 3D Engine</p>
          </div>
        </div>

        <div class="space-y-4">
          <div class="flex items-center justify-between text-xs">
            <span class="text-soft flex items-center gap-2 font-bold uppercase tracking-wider text-[9px]">
              <MapIcon :size="14" /> Khu vực:
            </span>
            <span class="font-black text-text">Biên Hòa, ĐN</span>
          </div>
          <div class="flex items-center justify-between text-xs">
            <span class="text-soft flex items-center gap-2 font-bold uppercase tracking-wider text-[9px]">
              <Layers :size="14" /> Tiles:
            </span>
            <span class="font-black text-brand">{{ state.loadedTiles }}</span>
          </div>
          <div class="flex items-center justify-between text-xs">
            <span class="text-soft flex items-center gap-2 font-bold uppercase tracking-wider text-[9px]">
              <Zap :size="14" /> Hiệu năng:
            </span>
            <span
              class="px-2 py-1 bg-brand-soft text-brand rounded-lg font-black text-[9px] uppercase tracking-wider">Tối
              ưu</span>
          </div>
        </div>

        <div class="mt-6 pt-5 border-t border-line">
          <button @click="state.showStats = !state.showStats"
            class="w-full flex items-center justify-center gap-2 py-3 bg-bg-strong hover:bg-line rounded-2xl text-xs font-black uppercase tracking-widest transition-all">
            <Info :size="16" />
            {{ state.showStats ? 'Ẩn chi tiết' : 'Xem thống kê' }}
          </button>
        </div>
      </div>

      <!-- Stats Panel (Conditional) -->
      <transition enter-active-class="transition duration-300 ease-out"
        enter-from-class="transform -translate-x-4 opacity-0" enter-to-class="transform translate-x-0 opacity-100"
        leave-active-class="transition duration-200 ease-in" leave-from-class="transform translate-x-0 opacity-100"
        leave-to-class="transform -translate-x-4 opacity-0">
        <div v-if="state.showStats"
          class="pointer-events-auto bg-surface-dark/90 backdrop-blur-md p-5 rounded-2xl shadow-2xl w-72 text-white">
          <h4 class="text-xs font-bold text-white/40 uppercase tracking-widest mb-4">Thống kê thực thể</h4>
          <div class="grid grid-cols-2 gap-3">
            <div class="bg-white/5 p-3 rounded-xl border border-white/10">
              <p class="text-[10px] text-white/40 mb-1">Giao cắt</p>
              <p class="text-lg font-bold">{{ state.rendered.crossings }}</p>
            </div>
            <div class="bg-white/5 p-3 rounded-xl border border-white/10">
              <p class="text-[10px] text-white/40 mb-1">Tòa nhà</p>
              <p class="text-lg font-bold">{{ state.rendered.buildings }}</p>
            </div>
            <div class="bg-white/5 p-3 rounded-xl border border-white/10">
              <p class="text-[10px] text-white/40 mb-1">Đường bộ</p>
              <p class="text-lg font-bold">{{ state.rendered.roads }}</p>
            </div>
            <div class="bg-white/5 p-3 rounded-xl border border-white/10">
              <p class="text-[10px] text-white/40 mb-1">Đường sắt</p>
              <p class="text-lg font-bold">{{ state.rendered.railways }}</p>
            </div>
          </div>
        </div>
      </transition>
      <div v-if="state.locationError"
        class="pointer-events-auto bg-danger-soft/95 border border-danger/15 text-danger p-4 rounded-2xl shadow-xl w-72 text-xs font-bold leading-relaxed">
        {{ state.locationError }}
      </div>
    </div>

    <!-- Bottom Controls -->
    <div
      class="absolute bottom-8 left-1/2 -translate-x-1/2 z-40 flex items-center gap-2 bg-white/90 backdrop-blur-md border border-line p-2 rounded-2xl shadow-2xl pointer-events-auto">
      <button @click="locateAndFlyToUser" :disabled="state.locating"
        class="flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all disabled:opacity-50 disabled:cursor-wait"
        :class="state.userLocation ? 'bg-brand text-white shadow-lg shadow-brand/20' : 'hover:bg-bg-strong text-soft hover:text-brand'">
        <Navigation :size="16" :class="state.userLocation ? 'text-white' : 'text-brand'" />
        {{ state.locating ? 'Đang định vị' : 'Vị trí của tôi' }}
      </button>
      <div class="w-px h-4 bg-line mx-1"></div>
      <button @click="focusBienHoa"
        class="flex items-center gap-2 px-4 py-2 hover:bg-bg-strong rounded-xl text-xs font-bold transition-all">
        <Compass :size="16" class="text-brand" />
        Mặc định
      </button>
      <div class="w-px h-4 bg-line mx-1"></div>
      <button @click="toggleFreeLook"
        class="p-2 rounded-xl transition-all"
        :class="state.freeLook ? 'bg-brand text-white shadow-lg shadow-brand/20' : 'text-soft hover:text-brand hover:bg-bg-strong'"
        title="Góc nhìn tự do">
        <MousePointer2 :size="18" />
      </button>
      <button @click="toggleFullscreen"
        class="p-2 rounded-xl transition-all"
        :class="state.fullscreen ? 'bg-brand text-white shadow-lg shadow-brand/20' : 'text-soft hover:text-brand hover:bg-bg-strong'"
        title="Toàn màn hình">
        <Maximize2 :size="18" />
      </button>
    </div>

    <!-- Map Legend (Bottom Right) -->
    <div class="absolute bottom-8 right-8 z-40 flex flex-col gap-2 pointer-events-none">
      <div class="pointer-events-auto bg-white/90 backdrop-blur-md border border-line p-4 rounded-2xl shadow-xl w-48">
        <h4 class="text-[10px] font-bold text-soft uppercase tracking-widest mb-3">Chú giải rủi ro</h4>
        <div class="space-y-2">
          <div class="flex items-center gap-3">
            <div class="w-3 h-3 rounded-full bg-danger shadow-sm shadow-danger/40"></div>
            <span class="text-xs font-medium">Rất cao</span>
          </div>
          <div class="flex items-center gap-3">
            <div class="w-3 h-3 rounded-full bg-warning shadow-sm shadow-warning/40"></div>
            <span class="text-xs font-medium">Cao</span>
          </div>
          <div class="flex items-center gap-3">
            <div class="w-3 h-3 rounded-full bg-brand shadow-sm shadow-brand/40"></div>
            <span class="text-xs font-medium">An toàn</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style>
/* MapLibre Popup Customization */
.maplibregl-popup-content {
  padding: 0;
  border-radius: 12px;
  border: 1px solid var(--line);
  box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
}

.maplibregl-popup-close-button {
  padding: 4px 8px;
  font-size: 16px;
  color: var(--soft);
  outline: none !important;
}

.maplibregl-popup-close-button:hover {
  background: transparent;
  color: var(--danger);
}

.maplibregl-ctrl-group {
  border: 1px solid var(--line) !important;
  border-radius: 12px !important;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden;
}

.maplibregl-ctrl-group button {
  width: 36px !important;
  height: 36px !important;
}
</style>
