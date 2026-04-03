<script setup>
import L from 'leaflet'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

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
const mapShell = ref(null)
const isFullscreen = ref(false)

let map
let currentBaseLayer
let crossingLayer
let highRiskLayer
let selectedZoneLayer
let userLayer
let areaLayer
let hasFitBounds = false

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
})

onBeforeUnmount(() => {
  document.removeEventListener('fullscreenchange', handleFullscreenChange)
  map?.off('click', handleMapClick)
  map?.remove()
})

watch(
  () => props.mapMode,
  () => {
    if (!map) return
    updateBaseLayer()
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
  setTimeout(() => map?.invalidateSize(), 50)
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

    <div ref="mapRoot" class="map-root"></div>
  </div>
</template>
