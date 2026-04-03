<script setup>
import maplibregl from 'maplibre-gl'
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { fetchScene3DManifest, fetchScene3DTile } from '../api'

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY || ''
const VIEWPORT_PADDING_DEGREES = 0.02
const DEFAULT_PITCH = 66
const DEFAULT_BEARING = -22
const DEFAULT_TERRAIN_EXAGGERATION = 1.7

const mapRoot = ref(null)

const state = reactive({
  loading: true,
  error: '',
  manifest: null,
  loadedTiles: 0,
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

function toCrossingFeatures(items) {
  return (items || [])
    .map((item) => {
      const point = coordinate(item)
      if (!point) return null

      return {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: point },
        properties: {
          id: item.id,
          code: item.code,
          name: item.name,
          riskLevel: item.riskLevel,
          riskScore: item.riskScore,
        },
      }
    })
    .filter(Boolean)
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

function updateRenderedStats(payloads) {
  state.rendered = payloads.reduce(
    (acc, tile) => {
      acc.crossings += tile.crossings?.length || 0
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
}

async function syncViewportData() {
  if (!map || !state.manifest) return

  const requestId = ++syncRequestId
  const tiles = desiredTiles()
  const payloads = await Promise.all(tiles.map((tile) => ensureTileLoaded(tile)))
  if (requestId !== syncRequestId) return

  state.loadedTiles = tileCache.size
  updateRenderedStats(payloads)

  applyGeoJson('scene-crossings', payloads.flatMap((tile) => toCrossingFeatures(tile.crossings)))
  applyGeoJson('scene-roads', payloads.flatMap((tile) => toLineFeatures(tile.roads, 'road')))
  applyGeoJson('scene-railways', payloads.flatMap((tile) => toLineFeatures(tile.railways, 'railway')))
  applyGeoJson('scene-buildings', payloads.flatMap((tile) => toPolygonFeatures(tile.buildings, 'building')))
  applyGeoJson('scene-landuse', payloads.flatMap((tile) => toPolygonFeatures(tile.landuse, 'landuse')))
  applyGeoJson('scene-water', payloads.flatMap((tile) => toPolygonFeatures(tile.water, 'water')))
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
        `<strong>${name || 'Điểm giao cắt'}</strong><br/>Mã: ${code || 'n/a'}<br/>Mức độ: ${
          riskLevel || 'unknown'
        }<br/>Điểm rủi ro: ${riskScore || 0}`
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
    state.manifest = await fetchScene3DManifest()
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

onBeforeUnmount(() => {
  if (syncTimer) window.clearTimeout(syncTimer)
  map?.remove()
})
</script>

<template>
  <section class="page-grid scene3d-page">
    <section class="map-surface scene3d-surface">
      <div v-if="state.loading" class="empty-state">Đang tải manifest và khởi tạo MapLibre...</div>
      <div v-else-if="state.error" class="error-box">{{ state.error }}</div>
      <div v-else ref="mapRoot" class="scene3d-map"></div>
    </section>
  </section>
</template>
