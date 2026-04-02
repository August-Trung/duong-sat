import { reactive } from 'vue'
import {
  fetchCrossingDetail,
  fetchCrossings,
  fetchLayers,
  fetchSummary,
  fetchIncidents,
  fetchSchedules,
} from '../api'

export const publicState = reactive({
  summary: {},
  layers: { riskLevels: [], barrierTypes: [] },
  crossings: [],
  schedules: [],
  incidents: [],
  selectedCrossingId: null,
  selectedCrossing: null,
  loading: false,
  detailLoading: false,
  locating: false,
  error: '',
  userLocation: null,
  areaAlert: {
    center: null,
    label: '',
    source: '',
    radiusMeters: 1500,
  },
  lastFiltersKey: '',
})

export const publicFilters = reactive({
  q: '',
  risk_level: '',
  barrier_type: '',
  district: '',
  sort_by: 'risk',
  radius_meters: 0,
  only_nearby: false,
  only_recent_incidents: false,
  only_unprotected: false,
})

let detailRequestId = 0

function buildApiFilters(filters = {}) {
  return {
    q: filters.q || '',
    risk_level: filters.risk_level || '',
    barrier_type: filters.barrier_type || '',
  }
}

function filtersKey(filters = {}) {
  return JSON.stringify(buildApiFilters(filters))
}

export async function loadPublicOverview(filters = {}) {
  const nextKey = filtersKey(filters)
  publicState.loading = true
  publicState.error = ''

  try {
    const [summary, layers, crossings, schedules, incidents] = await Promise.all([
      fetchSummary(),
      fetchLayers(),
      publicState.lastFiltersKey === nextKey
        ? Promise.resolve(publicState.crossings)
        : fetchCrossings(buildApiFilters(filters)),
      fetchSchedules(120),
      fetchIncidents(120),
    ])

    publicState.summary = summary
    publicState.layers = layers
    publicState.crossings = crossings
    publicState.schedules = schedules
    publicState.incidents = incidents
    publicState.lastFiltersKey = nextKey

    if (crossings.length && !crossings.some((item) => item.id === publicState.selectedCrossingId)) {
      publicState.selectedCrossingId = crossings[0].id
      await loadCrossingDetail(publicState.selectedCrossingId)
    } else if (!crossings.length) {
      publicState.selectedCrossingId = null
      publicState.selectedCrossing = null
    }
  } catch (error) {
    publicState.error = error.message
  } finally {
    publicState.loading = false
  }
}

export async function loadCrossingDetail(id) {
  if (!id) return
  const requestId = ++detailRequestId
  publicState.detailLoading = true
  publicState.error = ''

  try {
    publicState.selectedCrossingId = id
    const detail = await fetchCrossingDetail(id)
    if (requestId === detailRequestId) {
      publicState.selectedCrossing = detail
    }
  } catch (error) {
    if (requestId === detailRequestId) {
      publicState.error = error.message
    }
  } finally {
    if (requestId === detailRequestId) {
      publicState.detailLoading = false
    }
  }
}

export function updatePublicFilters(patch = {}) {
  Object.assign(publicFilters, patch)
}

export function resetPublicFilters() {
  Object.assign(publicFilters, {
    q: '',
    risk_level: '',
    barrier_type: '',
    district: '',
    sort_by: 'risk',
    radius_meters: 0,
    only_nearby: false,
    only_recent_incidents: false,
    only_unprotected: false,
  })
}

export async function locateUser() {
  if (!navigator.geolocation) {
    throw new Error('Trình duyệt không hỗ trợ định vị.')
  }

  publicState.locating = true
  publicState.error = ''

  try {
    const getPosition = (options) =>
      new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject, options)
      })

    let position = await getPosition({
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 0,
    })

    if ((position.coords.accuracy || 0) > 1000) {
      position = await getPosition({
        enableHighAccuracy: false,
        timeout: 8000,
        maximumAge: 0,
      })
    }

    publicState.userLocation = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy,
      label: 'Vị trí của tôi',
      capturedAt: new Date().toISOString(),
      source: 'gps',
    }

    return publicState.userLocation
  } catch (error) {
    const message = error?.message || 'Không thể lấy vị trí hiện tại.'
    publicState.error = message
    throw new Error(message)
  } finally {
    publicState.locating = false
  }
}

export function setUserLocation(location, options = {}) {
  if (!location) return
  publicState.userLocation = {
    latitude: Number(location.latitude),
    longitude: Number(location.longitude),
    accuracy: options.accuracy ?? 0,
    label: options.label || 'Vị trí của tôi (chỉnh tay)',
    capturedAt: new Date().toISOString(),
    source: options.source || 'manual',
  }
}

export function setAreaAlertCenter(center, label = '', source = 'manual') {
  if (!center) return
  publicState.areaAlert.center = {
    latitude: center.latitude,
    longitude: center.longitude,
  }
  publicState.areaAlert.label = label
  publicState.areaAlert.source = source
}

export function setAreaAlertRadius(radiusMeters) {
  publicState.areaAlert.radiusMeters = Number(radiusMeters) || 1500
}

export function useSelectedCrossingAsArea() {
  if (!publicState.selectedCrossing) return
  setAreaAlertCenter(
    publicState.selectedCrossing,
    publicState.selectedCrossing.name || 'Điểm đang chọn',
    'selected'
  )
}

export function useUserLocationAsArea() {
  if (!publicState.userLocation) return
  publicState.selectedCrossingId = null
  publicState.selectedCrossing = null
  setAreaAlertCenter(publicState.userLocation, 'Vị trí của tôi', 'user')
}

export function clearAreaAlert() {
  publicState.areaAlert.center = null
  publicState.areaAlert.label = ''
  publicState.areaAlert.source = ''
}
