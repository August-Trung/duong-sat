<script setup>
import L from 'leaflet'
import maplibregl from 'maplibre-gl'
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { fetchScene3DManifest, fetchScene3DTile } from '../api'

const props = defineProps({
  crossings: { type: Array, required: true },
  selectedId: { type: Number, default: null },
  selectedCrossing: { type: Object, default: null },
  visibleLevels: { type: Object, required: true },
  mapMode: { type: String, default: 'standard' },
  overlays: { type: Object, required: true },
  userLocation: { type: Object, default: null },
  areaAlert: { type: Object, default: null },
  highlightedIds: { type: Array, default: () => [] },
  pickLocationMode: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'change-mode', 'pick-location'])
const mapRoot = ref(null)
const mapRoot3d = ref(null)
const mapShell = ref(null)
const isFullscreen = ref(false)

let map
let map3d
let currentBaseLayer
let crossingLayer
let highRiskLayer
let selectedZoneLayer
let userLayer
let areaLayer
let hasFitBounds = false
let sceneManifest = null
let sceneSyncTimer = null
let sceneSyncRequestId = 0
const sceneTileCache = new Map()

const MAPTILER_KEY = import.meta.env.VITE_MAPTILER_KEY || ''
const VIEWPORT_PADDING_DEGREES = 0.02
const DEFAULT_PITCH = 66
const DEFAULT_BEARING = -22
const DEFAULT_TERRAIN_EXAGGERATION = 1.7

const levelColors = {
  very_high: '#df6a7d',
  high: '#f0a552',
  medium: '#f5ca72',
  low: '#48a17c',
  unknown: '#9ca9b7',
}

function riskLabel(level) {
  return {
    very_high: 'Rất cao',
    high: 'Cao',
    medium: 'Trung bình',
    low: 'Thấp',
    unknown: 'Chưa xác định',
  }[level] || level
}

const baseLayers = {
  standard: () =>
    L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO',
      maxNativeZoom: 20,
      maxZoom: 21,
    }),
  osm: () =>
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap contributors',
      maxNativeZoom: 19,
      maxZoom: 21,
    }),
  topo: () =>
    L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenTopoMap contributors',
      maxNativeZoom: 17,
      maxZoom: 21,
    }),
  dark: () =>
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO',
      maxNativeZoom: 20,
      maxZoom: 21,
    }),
  light: () =>
    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; OpenStreetMap, &copy; CARTO',
      maxNativeZoom: 20,
      maxZoom: 21,
    }),
  satellite: () =>
    L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        attribution: 'Tiles &copy; Esri',
        maxNativeZoom: 19,
        maxZoom: 21,
      }
    ),
}

onMounted(() => {
  map = L.map(mapRoot.value, {
    zoomControl: false,
    minZoom: 11,
    maxZoom: 21,
  }).setView([10.95, 106.84], 12)

  L.control.zoom({ position: 'topright' }).addTo(map)
  crossingLayer = L.layerGroup().addTo(map)
  highRiskLayer = L.layerGroup().addTo(map)
  selectedZoneLayer = L.layerGroup().addTo(map)
  userLayer = L.layerGroup().addTo(map)
  areaLayer = L.layerGroup().addTo(map)

  updateBaseLayer()
  renderLayers()
  map.on('click', handleMapClick)
  document.addEventListener('fullscreenchange', handleFullscreenChange)
  if (props.mapMode === 'three-d') {
    initialize3DMap()
  }
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  map?.off('click', handleMapClick)
  map?.remove()
  if (sceneSyncTimer) window.clearTimeout(sceneSyncTimer)
  map3d?.remove()
})

watch(
  () => props.mapMode,
  async (mode) => {
    if (!map) return
    if (mode === 'three-d') {
      await nextTick()
      initialize3DMap()
      setTimeout(() => map3d?.resize(), 50)
      return
    }
    updateBaseLayer()
    setTimeout(() => map.invalidateSize(), 50)
  }
)

watch(
  () => [
    props.crossings,
    props.selectedId,
    props.visibleLevels,
    props.overlays,
    props.userLocation,
    props.areaAlert,
    props.highlightedIds,
  ],
  () => {
    if (!crossingLayer) return
    renderLayers()
  },
  { deep: true }
)

watch(
  () => props.userLocation,
  (location) => {
    if (!map || !location?.latitude || !location?.longitude) return
    hasFitBounds = true
    map.flyTo([location.latitude, location.longitude], Math.max(map.getZoom(), 15), {
      animate: true,
      duration: 0.8,
    })
  },
  { deep: true }
)

watch(
  () => props.selectedCrossing,
  (crossing) => {
    if (!map3d || props.mapMode !== 'three-d' || !crossing?.latitude || !crossing?.longitude) return
    map3d.flyTo({
      center: [crossing.longitude, crossing.latitude],
      zoom: Math.max(map3d.getZoom(), 15),
      pitch: DEFAULT_PITCH,
      bearing: DEFAULT_BEARING,
      essential: true,
    })
  },
  { deep: true }
)

watch(
  () => props.userLocation,
  (location) => {
    if (!map3d || props.mapMode !== 'three-d' || !location?.latitude || !location?.longitude) return
    map3d.flyTo({
      center: [location.longitude, location.latitude],
      zoom: Math.max(map3d.getZoom(), 15),
      pitch: DEFAULT_PITCH,
      bearing: DEFAULT_BEARING,
      essential: true,
    })
  },
  { deep: true }
)

watch(
  () => props.areaAlert,
  (area) => {
    if (!map3d || props.mapMode !== 'three-d' || !area?.center?.latitude || !area?.center?.longitude) return
    if (area.source !== 'user') return
    map3d.flyTo({
      center: [area.center.longitude, area.center.latitude],
      zoom: Math.max(map3d.getZoom(), 14),
      pitch: DEFAULT_PITCH,
      bearing: DEFAULT_BEARING,
      essential: true,
    })
  },
  { deep: true }
)

watch(
  () => [
    props.crossings,
    props.visibleLevels,
    props.highlightedIds,
    props.selectedId,
    props.overlays.crossings,
    props.userLocation,
    props.areaAlert,
  ],
  () => {
    if (!map3d) return
    applyGeoJson3d('scene-crossings', toPublicCrossingFeatures(props.crossings))
    applyGeoJson3d('scene-user-location', toUserLocationFeatures())
    applyGeoJson3d('scene-user-accuracy', toUserAccuracyFeatures())
    applyGeoJson3d('scene-area-center', toAreaCenterFeatures())
    applyGeoJson3d('scene-area-radius', toAreaRadiusFeatures())
  },
  { deep: true }
)

watch(
  () => props.areaAlert,
  (area) => {
    if (!map || !area?.center?.latitude || !area?.center?.longitude) return
    if (area.source !== 'user') return
    hasFitBounds = true
    map.flyTo([area.center.latitude, area.center.longitude], Math.max(map.getZoom(), 14), {
      animate: true,
      duration: 0.8,
    })
  },
  { deep: true }
)

function updateBaseLayer() {
  if (props.mapMode === 'three-d') return
  if (currentBaseLayer) {
    map.removeLayer(currentBaseLayer)
  }
  const factory = baseLayers[props.mapMode] || baseLayers.standard
  currentBaseLayer = factory()
  currentBaseLayer.addTo(map)
}

function suppressDoubleClickZoom(layer) {
  layer.on('dblclick', (event) => {
    L.DomEvent.stop(event)
  })
  return layer
}

function renderLayers() {
  crossingLayer.clearLayers()
  highRiskLayer.clearLayers()
  selectedZoneLayer.clearLayers()
  userLayer.clearLayers()
  areaLayer.clearLayers()

  const visible = props.crossings.filter(
    (item) => item.latitude && item.longitude && props.visibleLevels[item.risk_level] !== false
  )

  const highlightedSet = new Set(props.highlightedIds)
  const bounds = []

  if (props.userLocation?.latitude && props.userLocation?.longitude) {
    const latlng = [props.userLocation.latitude, props.userLocation.longitude]
    suppressDoubleClickZoom(
      L.circleMarker(latlng, {
      radius: 8,
      color: '#ffffff',
      weight: 3,
      fillColor: '#3b82f6',
        fillOpacity: 1,
      })
    )
      .bindPopup('Vị trí của tôi')
      .addTo(userLayer)
    L.circle(latlng, {
      radius: Math.max(50, props.userLocation.accuracy || 120),
      color: '#3b82f6',
      weight: 1,
      fillColor: '#93c5fd',
      fillOpacity: 0.12,
      interactive: false,
    }).addTo(userLayer)
  }

  if (props.areaAlert?.center?.latitude && props.areaAlert?.center?.longitude) {
    const latlng = [props.areaAlert.center.latitude, props.areaAlert.center.longitude]
    L.circle(latlng, {
      radius: props.areaAlert.radiusMeters || 1500,
      color: '#3b82f6',
      weight: 1.2,
      fillColor: '#bfdbfe',
      fillOpacity: 0.1,
      interactive: false,
    }).addTo(areaLayer)
    suppressDoubleClickZoom(
      L.circleMarker(latlng, {
      radius: 5,
      color: '#3b82f6',
      weight: 2,
      fillColor: '#ffffff',
        fillOpacity: 1,
      })
    )
      .bindPopup(props.areaAlert.label || 'Vùng quan tâm')
      .addTo(areaLayer)
  }

  visible.forEach((crossing) => {
    const isSelected = crossing.id === props.selectedId
    const isHighRisk = ['very_high', 'high'].includes(crossing.risk_level)
    const isHighlighted = highlightedSet.has(crossing.id)

    if (props.overlays.warningZones && isSelected) {
      L.circle([crossing.latitude, crossing.longitude], {
        radius: 220,
        color: '#3b82f6',
        weight: 1.2,
        fillColor: '#93c5fd',
        fillOpacity: 0.12,
        interactive: false,
      }).addTo(selectedZoneLayer)
    }

    if (props.overlays.crossings) {
      const marker = suppressDoubleClickZoom(L.circleMarker([crossing.latitude, crossing.longitude], {
        radius: isHighlighted ? 10 : Math.max(6, Math.min(14, 6 + Math.floor((crossing.risk_score || 0) / 40))),
        color: isSelected ? '#ffffff' : isHighlighted ? '#2563eb' : '#4d6176',
        weight: isSelected ? 2.5 : isHighlighted ? 2 : 1.1,
        fillColor: levelColors[crossing.risk_level] || levelColors.unknown,
        fillOpacity: 0.92,
      }))
      marker.bindPopup(
        `<strong>${crossing.name}</strong><br/>Mức độ: ${riskLabel(crossing.risk_level)}<br/>Điểm rủi ro: ${crossing.risk_score}`
      )
      marker.on('click', () => {
        marker.openPopup()
        emit('select', crossing.id)
      })
      marker.addTo(crossingLayer)
    }

    if (props.overlays.highRiskOnly && isHighRisk) {
      L.circleMarker([crossing.latitude, crossing.longitude], {
        radius: isHighlighted ? 18 : 15,
        color: '#ef4444',
        weight: 1,
        fillOpacity: 0,
        interactive: false,
      }).addTo(highRiskLayer)
    }

    bounds.push([crossing.latitude, crossing.longitude])
  })

  if (!hasFitBounds && bounds.length) {
    map.fitBounds(bounds, { padding: [28, 28] })
    hasFitBounds = true
  }
}

function handleMapClick(event) {
  if (!props.pickLocationMode) return
  emit('pick-location', {
    latitude: event.latlng.lat,
    longitude: event.latlng.lng,
  })
}

async function toggleFullscreen() {
  if (!mapShell.value) return
  if (document.fullscreenElement === mapShell.value) {
    await document.exitFullscreen()
    return
  }
  await mapShell.value.requestFullscreen()
}

function handleFullscreenChange() {
  isFullscreen.value = document.fullscreenElement === mapShell.value
  setTimeout(() => {
    map?.invalidateSize()
    map3d?.resize()
  }, 50)
}

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
    layers: [{ id: 'carto-raster', type: 'raster', source: 'carto' }],
  }
}

function current3DStyle() {
  if (MAPTILER_KEY) {
    return `https://api.maptiler.com/maps/streets-v2/style.json?key=${MAPTILER_KEY}`
  }
  return createFallbackStyle()
}

function emptyFeatureCollection() {
  return { type: 'FeatureCollection', features: [] }
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

function source3d(name) {
  return map3d?.getSource(name)
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

function toPublicCrossingFeatures(items) {
  return (items || [])
    .filter(
      (item) =>
        item?.latitude &&
        item?.longitude &&
        props.visibleLevels[item.risk_level] !== false &&
        props.overlays.crossings
    )
    .map((item) => ({
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [Number(item.longitude), Number(item.latitude)],
      },
      properties: {
        id: item.id,
        code: item.code,
        name: item.name,
        riskLevel: item.risk_level,
        riskScore: item.risk_score,
        selected: item.id === props.selectedId,
        highlighted: props.highlightedIds.includes(item.id),
      },
    }))
}

function toUserLocationFeatures() {
  if (!props.userLocation?.latitude || !props.userLocation?.longitude) return []

  return [
    {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [Number(props.userLocation.longitude), Number(props.userLocation.latitude)],
      },
      properties: {
        label: props.userLocation.label || 'Vị trí của tôi',
      },
    },
  ]
}

function toUserAccuracyFeatures() {
  if (!props.userLocation?.latitude || !props.userLocation?.longitude) return []

  const radiusMeters = Math.max(50, Number(props.userLocation.accuracy || 120))
  const polygon = createCirclePolygon(props.userLocation, radiusMeters)
  if (!polygon?.length) return []

  return [
    {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [polygon] },
      properties: {
        label: props.userLocation.label || 'Vị trí của tôi',
      },
    },
  ]
}

function toAreaCenterFeatures() {
  if (!props.areaAlert?.center?.latitude || !props.areaAlert?.center?.longitude) return []

  return [
    {
      type: 'Feature',
      geometry: {
        type: 'Point',
        coordinates: [
          Number(props.areaAlert.center.longitude),
          Number(props.areaAlert.center.latitude),
        ],
      },
      properties: {
        label: props.areaAlert.label || 'Vùng quan tâm',
      },
    },
  ]
}

function toAreaRadiusFeatures() {
  if (!props.areaAlert?.center?.latitude || !props.areaAlert?.center?.longitude) return []

  const radiusMeters = Number(props.areaAlert.radiusMeters || 1500)
  const polygon = createCirclePolygon(props.areaAlert.center, radiusMeters)
  if (!polygon?.length) return []

  return [
    {
      type: 'Feature',
      geometry: { type: 'Polygon', coordinates: [polygon] },
      properties: {
        label: props.areaAlert.label || 'Vùng quan tâm',
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

function ensureSceneSources() {
  ;[
    'scene-crossings',
    'scene-roads',
    'scene-railways',
    'scene-buildings',
    'scene-landuse',
    'scene-water',
    'scene-user-location',
    'scene-user-accuracy',
    'scene-area-center',
    'scene-area-radius',
  ]
    .forEach((name) => {
      if (!source3d(name)) {
        map3d.addSource(name, { type: 'geojson', data: emptyFeatureCollection() })
      }
    })
}

function ensureSceneLayers() {
  const layers = [
    {
      id: 'scene-water',
      type: 'fill',
      source: 'scene-water',
      paint: { 'fill-color': ['coalesce', ['get', 'color'], '#72b1e0'], 'fill-opacity': 0.62 },
    },
    {
      id: 'scene-landuse',
      type: 'fill',
      source: 'scene-landuse',
      paint: { 'fill-color': ['coalesce', ['get', 'color'], '#9cc7a1'], 'fill-opacity': 0.3 },
    },
    {
      id: 'scene-road-casing',
      type: 'line',
      source: 'scene-roads',
      paint: {
        'line-color': '#6f7983',
        'line-opacity': 0.9,
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, ['max', 2.5, ['/', ['coalesce', ['get', 'widthMeters'], 7], 1.6]], 16, ['max', 8, ['/', ['coalesce', ['get', 'widthMeters'], 7], 1.05]]],
      },
    },
    {
      id: 'scene-roads',
      type: 'line',
      source: 'scene-roads',
      paint: {
        'line-color': '#f7f4ee',
        'line-opacity': 1,
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, ['max', 1.4, ['/', ['coalesce', ['get', 'widthMeters'], 7], 2.2]], 16, ['max', 6.5, ['/', ['coalesce', ['get', 'widthMeters'], 7], 1.35]]],
      },
    },
    {
      id: 'scene-railways-casing',
      type: 'line',
      source: 'scene-railways',
      paint: { 'line-color': '#f4f1e8', 'line-opacity': 0.95, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 2.6, 15, 7.8] },
    },
    {
      id: 'scene-railways',
      type: 'line',
      source: 'scene-railways',
      paint: { 'line-color': '#183b54', 'line-opacity': 1, 'line-width': ['interpolate', ['linear'], ['zoom'], 11, 1.6, 15, 5.2] },
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
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 12, 16, 20],
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
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['zoom'],
          11,
          ['case', ['boolean', ['get', 'highlighted'], false], 10, ['boolean', ['get', 'selected'], false], 9, 7],
          16,
          ['case', ['boolean', ['get', 'highlighted'], false], 14, ['boolean', ['get', 'selected'], false], 12, 10.5],
        ],
        'circle-color': ['match', ['get', 'riskLevel'], 'very_high', '#d6455d', 'high', '#cd8c1c', 'medium', '#d8a93a', 'low', '#2f8f6f', '#4d6176'],
        'circle-stroke-width': ['case', ['boolean', ['get', 'selected'], false], 3, 2],
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
      id: 'scene-area-radius',
      type: 'fill',
      source: 'scene-area-radius',
      paint: {
        'fill-color': '#bfdbfe',
        'fill-opacity': 0.1,
      },
    },
    {
      id: 'scene-area-radius-outline',
      type: 'line',
      source: 'scene-area-radius',
      paint: {
        'line-color': '#3b82f6',
        'line-width': 1.3,
        'line-opacity': 0.9,
      },
    },
    {
      id: 'scene-area-center',
      type: 'circle',
      source: 'scene-area-center',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 11, 5, 16, 7],
        'circle-color': '#ffffff',
        'circle-stroke-width': 2,
        'circle-stroke-color': '#3b82f6',
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
    if (!map3d.getLayer(layer.id)) {
      map3d.addLayer(layer)
    }
  })
}

function applyGeoJson3d(name, features) {
  source3d(name)?.setData({ type: 'FeatureCollection', features })
}

function paddedViewportBounds3d() {
  const bounds = map3d.getBounds()
  return {
    west: bounds.getWest() - VIEWPORT_PADDING_DEGREES,
    south: bounds.getSouth() - VIEWPORT_PADDING_DEGREES,
    east: bounds.getEast() + VIEWPORT_PADDING_DEGREES,
    north: bounds.getNorth() + VIEWPORT_PADDING_DEGREES,
  }
}

function squareDistance(a, b) {
  return (a.longitude - b.longitude) ** 2 + (a.latitude - b.latitude) ** 2
}

function intersectsBounds(a, b) {
  return !(a.east < b.west || a.west > b.east || a.north < b.south || a.south > b.north)
}

function desiredTiles3d() {
  if (!map3d || !sceneManifest?.tiles?.length) return []
  const viewport = paddedViewportBounds3d()
  const center = map3d.getCenter()
  const zoom = map3d.getZoom()
  const maxVisibleTiles = zoom >= 15 ? 14 : zoom >= 14 ? 10 : zoom >= 13 ? 8 : 6
  return sceneManifest.tiles
    .filter((tile) => intersectsBounds(tile.bounds, viewport))
    .sort((left, right) => squareDistance(left.center, center) - squareDistance(right.center, center))
    .slice(0, maxVisibleTiles)
}

async function ensureTileLoaded3d(tileMeta) {
  if (sceneTileCache.has(tileMeta.id)) return sceneTileCache.get(tileMeta.id)
  const payload = await fetchScene3DTile(tileMeta.id)
  sceneTileCache.set(tileMeta.id, payload)
  return payload
}

function queueSceneSync() {
  if (sceneSyncTimer) window.clearTimeout(sceneSyncTimer)
  sceneSyncTimer = window.setTimeout(() => {
    syncSceneViewport().catch(() => {})
  }, 120)
}

async function syncSceneViewport() {
  if (!map3d || !sceneManifest) return
  const requestId = ++sceneSyncRequestId
  const tiles = desiredTiles3d()
  const payloads = await Promise.all(tiles.map((tile) => ensureTileLoaded3d(tile)))
  if (requestId !== sceneSyncRequestId) return
  applyGeoJson3d('scene-roads', payloads.flatMap((tile) => toLineFeatures(tile.roads, 'road')))
  applyGeoJson3d('scene-railways', payloads.flatMap((tile) => toLineFeatures(tile.railways, 'railway')))
  applyGeoJson3d('scene-buildings', payloads.flatMap((tile) => toPolygonFeatures(tile.buildings, 'building')))
  applyGeoJson3d('scene-landuse', payloads.flatMap((tile) => toPolygonFeatures(tile.landuse, 'landuse')))
  applyGeoJson3d('scene-water', payloads.flatMap((tile) => toPolygonFeatures(tile.water, 'water')))
  applyGeoJson3d('scene-crossings', toPublicCrossingFeatures(props.crossings))
  applyGeoJson3d('scene-user-location', toUserLocationFeatures())
  applyGeoJson3d('scene-user-accuracy', toUserAccuracyFeatures())
  applyGeoJson3d('scene-area-center', toAreaCenterFeatures())
  applyGeoJson3d('scene-area-radius', toAreaRadiusFeatures())
}

function setupScenePopup() {
  map3d.on('click', 'scene-crossings', (event) => {
    const feature = event.features?.[0]
    if (!feature) return
    const crossingId = Number(feature.properties?.id)
    if (Number.isFinite(crossingId)) {
      emit('select', crossingId)
    }
    const [longitude, latitude] = feature.geometry.coordinates
    new maplibregl.Popup({ closeButton: true, closeOnClick: true })
      .setLngLat([longitude, latitude])
      .setHTML(
        `<strong>${feature.properties?.name || 'Điểm giao cắt'}</strong><br/>Mã: ${feature.properties?.code || 'n/a'}<br/>Mức độ: ${feature.properties?.riskLevel || 'unknown'}<br/>Điểm rủi ro: ${feature.properties?.riskScore || 0}`
      )
      .addTo(map3d)
  })
  map3d.on('mouseenter', 'scene-crossings', () => {
    map3d.getCanvas().style.cursor = 'pointer'
  })
  map3d.on('mouseleave', 'scene-crossings', () => {
    map3d.getCanvas().style.cursor = ''
  })
}

function focusBienHoa3d() {
  const crossingTiles = (sceneManifest?.tiles || []).filter((tile) => (tile.featureCounts?.crossings || 0) > 0)
  const focusTiles = crossingTiles.length ? crossingTiles : sceneManifest?.tiles || []
  if (!focusTiles.length) return
  const bounds = focusTiles.reduce(
    (acc, tile) => ({
      west: Math.min(acc.west, tile.bounds.west),
      south: Math.min(acc.south, tile.bounds.south),
      east: Math.max(acc.east, tile.bounds.east),
      north: Math.max(acc.north, tile.bounds.north),
    }),
    { west: Number.POSITIVE_INFINITY, south: Number.POSITIVE_INFINITY, east: Number.NEGATIVE_INFINITY, north: Number.NEGATIVE_INFINITY }
  )
  map3d.fitBounds(
    [
      [bounds.west, bounds.south],
      [bounds.east, bounds.north],
    ],
    { padding: 40, pitch: DEFAULT_PITCH, bearing: DEFAULT_BEARING, maxZoom: 14.6, duration: 0 }
  )
}

function enableMapTilerTerrain() {
  if (!MAPTILER_KEY || map3d.getSource('maptiler-terrain')) return
  map3d.addSource('maptiler-terrain', {
    type: 'raster-dem',
    url: `https://api.maptiler.com/tiles/terrain-rgb-v2/tiles.json?key=${MAPTILER_KEY}`,
    tileSize: 256,
  })
  map3d.setTerrain({ source: 'maptiler-terrain', exaggeration: DEFAULT_TERRAIN_EXAGGERATION })
}

function configureLighting() {
  if (typeof map3d?.setLight !== 'function') return
  map3d.setLight({
    anchor: 'map',
    color: '#fff4d6',
    intensity: 0.42,
    position: [1.4, 210, 38],
  })
}

async function initialize3DMap() {
  if (map3d || !mapRoot3d.value) return
  sceneManifest = await fetchScene3DManifest()
  map3d = new maplibregl.Map({
    container: mapRoot3d.value,
    style: current3DStyle(),
    center: [sceneManifest.center.longitude, sceneManifest.center.latitude],
    zoom: 13.2,
    pitch: DEFAULT_PITCH,
    bearing: DEFAULT_BEARING,
    antialias: true,
  })
  map3d.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
  map3d.on('load', async () => {
    ensureSceneSources()
    ensureSceneLayers()
    setupScenePopup()
    enableMapTilerTerrain()
    configureLighting()
    focusBienHoa3d()
    await syncSceneViewport()
  })
  map3d.on('moveend', queueSceneSync)
}
</script>

<template>
  <div ref="mapShell" class="map-shell" :class="{ fullscreen: isFullscreen }">
    <button class="map-fab" type="button" @click="toggleFullscreen">
      {{ isFullscreen ? 'Thu nhỏ' : 'Toàn màn hình' }}
    </button>

    <div class="map-fab-group">
      <button
        class="mode-chip"
        :class="{ active: mapMode === 'standard' }"
        type="button"
        @click="emit('change-mode', 'standard')"
      >
        Chuẩn
      </button>
      <button
        class="mode-chip"
        :class="{ active: mapMode === 'osm' }"
        type="button"
        @click="emit('change-mode', 'osm')"
      >
        OpenStreetMap
      </button>
      <button
        class="mode-chip"
        :class="{ active: mapMode === 'light' }"
        type="button"
        @click="emit('change-mode', 'light')"
      >
        Sáng
      </button>
      <button
        class="mode-chip"
        :class="{ active: mapMode === 'dark' }"
        type="button"
        @click="emit('change-mode', 'dark')"
      >
        Tối
      </button>
      <button
        class="mode-chip"
        :class="{ active: mapMode === 'satellite' }"
        type="button"
        @click="emit('change-mode', 'satellite')"
      >
        Vệ tinh
      </button>
      <button
        class="mode-chip"
        :class="{ active: mapMode === 'three-d' }"
        type="button"
        @click="emit('change-mode', 'three-d')"
      >
        Map 3D
      </button>
      <button
        class="mode-chip"
        :class="{ active: mapMode === 'topo' }"
        type="button"
        @click="emit('change-mode', 'topo')"
      >
        Địa hình
      </button>
    </div>

    <section v-if="selectedCrossing" class="map-focus-card">
      <div class="map-focus-card__header">
        <div>
          <p class="micro-label">Điểm đang chọn</p>
          <h3>{{ selectedCrossing.name }}</h3>
        </div>
        <span class="risk-chip" :class="selectedCrossing.risk_level">
          {{ riskLabel(selectedCrossing.risk_level) }} · {{ selectedCrossing.risk_score }}
        </span>
      </div>

      <div class="map-focus-card__grid">
        <article class="focus-meta">
          <span>Địa chỉ</span>
          <strong>{{ selectedCrossing.address || 'Đang cập nhật' }}</strong>
        </article>
        <article class="focus-meta">
          <span>Quản lý</span>
          <strong>{{ selectedCrossing.manager_name || 'Chưa có' }}</strong>
        </article>
        <article class="focus-meta">
          <span>Bài tin</span>
          <strong>{{ selectedCrossing.evidence?.article_count ?? 0 }}</strong>
        </article>
        <article class="focus-meta">
          <span>Sự cố</span>
          <strong>{{ selectedCrossing.incidents?.length ?? 0 }}</strong>
        </article>
      </div>
    </section>

    <div v-show="mapMode !== 'three-d'" ref="mapRoot" class="map-root"></div>
    <div v-show="mapMode === 'three-d'" ref="mapRoot3d" class="map-root scene3d-map scene3d-map--embedded"></div>
  </div>
</template>
