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
const MAX_LOCATION_ACCURACY_METERS = 5000
const DESIRED_LOCATION_ACCURACY_METERS = 1000
const LOCATION_WATCH_WINDOW_MS = 15000
const HIGH_ACCURACY_TIMEOUT_MS = 12000
const LOW_ACCURACY_TIMEOUT_MS = 8000

function normalizePositionSample(position) {
  const latitude = Number(position?.coords?.latitude)
  const longitude = Number(position?.coords?.longitude)
  const accuracy = Number(position?.coords?.accuracy || 0)

  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return null
  }

  return { position, latitude, longitude, accuracy }
}

function pickBetterPosition(currentBest, candidate) {
  if (!candidate) return currentBest
  if (!currentBest) return candidate

  const currentAccuracy = currentBest.accuracy > 0 ? currentBest.accuracy : Number.POSITIVE_INFINITY
  const candidateAccuracy = candidate.accuracy > 0 ? candidate.accuracy : Number.POSITIVE_INFINITY

  if (candidateAccuracy < currentAccuracy) return candidate
  if (candidateAccuracy > currentAccuracy) return currentBest

  const currentTimestamp = Number(currentBest.position?.timestamp || 0)
  const candidateTimestamp = Number(candidate.position?.timestamp || 0)
  return candidateTimestamp >= currentTimestamp ? candidate : currentBest
}

function getPosition(options) {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, options)
  })
}

function watchBestPosition({
  desiredAccuracy = DESIRED_LOCATION_ACCURACY_METERS,
  watchWindowMs = LOCATION_WATCH_WINDOW_MS,
} = {}) {
  return new Promise((resolve, reject) => {
    let bestSample = null
    let settled = false
    let lastError = null
    let watchId = null

    const finalize = () => {
      if (settled) return
      settled = true
      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId)
      }

      if (bestSample) {
        resolve(bestSample.position)
        return
      }

      reject(lastError || new Error('\u004b\u0068\u00f4\u006e\u0067\u0020\u0074\u0068\u1ec3\u0020\u006c\u1ea5\u0079\u0020\u0076\u1ecb\u0020\u0074\u0072\u00ed\u0020\u0068\u0069\u1ec7\u006e\u0020\u0074\u1ea1\u0069\u002e'))
    }

    const timerId = window.setTimeout(finalize, watchWindowMs)

    const handleSuccess = (position) => {
      const sample = normalizePositionSample(position)
      if (!sample) return

      bestSample = pickBetterPosition(bestSample, sample)
      if (bestSample.accuracy > 0 && bestSample.accuracy <= desiredAccuracy) {
        window.clearTimeout(timerId)
        finalize()
      }
    }

    const handleError = (error) => {
      lastError = error
    }

    watchId = navigator.geolocation.watchPosition(handleSuccess, handleError, {
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: HIGH_ACCURACY_TIMEOUT_MS,
    })
  })
}

async function readBestAvailablePosition() {
  let bestSample = null
  let lastError = null

  const collect = (position) => {
    bestSample = pickBetterPosition(bestSample, normalizePositionSample(position))
  }

  const attempts = [
    getPosition({
      enableHighAccuracy: true,
      timeout: HIGH_ACCURACY_TIMEOUT_MS,
      maximumAge: 0,
    }),
    watchBestPosition({
      desiredAccuracy: DESIRED_LOCATION_ACCURACY_METERS,
      watchWindowMs: LOCATION_WATCH_WINDOW_MS,
    }),
    getPosition({
      enableHighAccuracy: false,
      timeout: LOW_ACCURACY_TIMEOUT_MS,
      maximumAge: 30000,
    }),
  ]

  const results = await Promise.allSettled(attempts)

  for (const result of results) {
    if (result.status === 'fulfilled') {
      collect(result.value)
      continue
    }

    lastError = result.reason
  }

  if (bestSample) {
    return bestSample.position
  }

  throw lastError || new Error('\u004b\u0068\u00f4\u006e\u0067\u0020\u0074\u0068\u1ec3\u0020\u006c\u1ea5\u0079\u0020\u0076\u1ecb\u0020\u0074\u0072\u00ed\u0020\u0068\u0069\u1ec7\u006e\u0020\u0074\u1ea1\u0069\u002e')
}

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

export function clearPublicError() {
  publicState.error = ''
}

export async function locateUser() {
  if (!navigator.geolocation) {
    throw new Error('Trình duyệt không hỗ trợ định vị.')
  }

  publicState.locating = true
  publicState.error = ''

  try {
    const position = await readBestAvailablePosition()

    const accuracy = Number(position.coords.accuracy || 0)
    if (accuracy > MAX_LOCATION_ACCURACY_METERS) {
      throw new Error('Vị trí hiện tại chưa đủ chính xác. Hãy bật GPS chính xác cao hoặc chọn vị trí trên bản đồ.')
    }

    publicState.userLocation = {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy,
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
