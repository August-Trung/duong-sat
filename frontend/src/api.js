const API_BASE = import.meta.env.DEV
  ? import.meta.env.VITE_API_BASE_LOCAL || '/api'
  : import.meta.env.VITE_API_BASE_HOST || '/api'
const TOKEN_KEY = 'railway-risk-token'

function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function getAssetBase() {
  return API_BASE.replace(/\/api\/?$/, '')
}

export function toAssetUrl(path) {
  if (!path) return ''
  if (/^https?:\/\//.test(path)) return path
  return `${getAssetBase()}${path.startsWith('/') ? path : `/${path}`}`
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

async function request(path, options = {}) {
  const token = getToken()
  const isFormData = options.body instanceof FormData
  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(options.headers || {}),
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  })

  if (response.status === 204) {
    return null
  }

  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('text/csv')) {
    const blob = await response.blob()
    if (!response.ok) throw new Error(`API error: ${response.status}`)
    return blob
  }

  if (!contentType.includes('application/json')) {
    const rawText = await response.text()
    const looksLikeHtml = /^\s*</.test(rawText)
    if (looksLikeHtml) {
      throw new Error(
        'API đang trả về HTML thay vì JSON. Production hiện chưa trỏ đúng backend /api.'
      )
    }
    throw new Error(`API trả về content-type không hợp lệ: ${contentType || 'unknown'}`)
  }

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.detail || `API error: ${response.status}`)
  }
  return data
}

export function fetchSummary() {
  return request('/summary')
}

export function fetchLayers() {
  return request('/layers')
}

export function fetchCrossings(params = {}) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') search.set(key, value)
  })
  const query = search.toString()
  return request(`/crossings${query ? `?${query}` : ''}`)
}

export function fetchCrossingDetail(id) {
  return request(`/crossings/${id}`)
}

export function fetchSchedules(limit = 100) {
  return request(`/schedules?limit=${limit}`)
}

export function fetchIncidents(limit = 100) {
  return request(`/incidents?limit=${limit}`)
}

export function fetchScene3DManifest() {
  return request('/scene3d/manifest')
}

export function fetchScene3DTile(tileId) {
  return request(`/scene3d/tiles/${tileId}`)
}

export function login(username, password) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logout() {
  return request('/auth/logout', { method: 'POST' })
}

export function fetchMe() {
  return request('/auth/me')
}

export function fetchAdminOverview() {
  return request('/admin/overview')
}

export function fetchQualityAlerts() {
  return request('/admin/quality-alerts')
}

export function fetchAuditLogs(limit = 50) {
  return request(`/admin/audit-logs?limit=${limit}`)
}

export function fetchCrossingProfile(id) {
  return request(`/admin/crossings/${id}/profile`)
}

export function createCrossing(payload) {
  return request('/admin/crossings', { method: 'POST', body: JSON.stringify(payload) })
}

export function importCrossings(payload) {
  return request('/admin/crossings/import', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateCrossing(id, payload) {
  return request(`/admin/crossings/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

export function bulkCrossings(payload) {
  return request('/admin/crossings/bulk', { method: 'POST', body: JSON.stringify(payload) })
}

export function deleteCrossing(id) {
  return request(`/admin/crossings/${id}`, { method: 'DELETE' })
}

export function uploadCrossingImages(id, files) {
  const body = new FormData()
  Array.from(files || []).forEach((file) => body.append('files', file))
  return request(`/admin/crossings/${id}/images`, { method: 'POST', body })
}

export function deleteCrossingImage(crossingId, imageId) {
  return request(`/admin/crossings/${crossingId}/images/${imageId}`, { method: 'DELETE' })
}

export function updateCrossingImages(crossingId, payload) {
  return request(`/admin/crossings/${crossingId}/images`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function createSchedule(payload) {
  return request('/admin/schedules', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateSchedule(id, payload) {
  return request(`/admin/schedules/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

export function deleteSchedule(id) {
  return request(`/admin/schedules/${id}`, { method: 'DELETE' })
}

export function createIncident(payload) {
  return request('/admin/incidents', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateIncident(id, payload) {
  return request(`/admin/incidents/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

export function deleteIncident(id) {
  return request(`/admin/incidents/${id}`, { method: 'DELETE' })
}

export function createArticle(payload) {
  return request('/admin/articles', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateArticle(id, payload) {
  return request(`/admin/articles/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

export function deleteArticle(id) {
  return request(`/admin/articles/${id}`, { method: 'DELETE' })
}

export function fetchUsers() {
  return request('/admin/users')
}

export function createUser(payload) {
  return request('/admin/users', { method: 'POST', body: JSON.stringify(payload) })
}

export function updateUser(id, payload) {
  return request(`/admin/users/${id}`, { method: 'PUT', body: JSON.stringify(payload) })
}

export function downloadCrossingsReport() {
  return request('/admin/reports/crossings.csv')
}

export function downloadQualityReport() {
  return request('/admin/reports/quality.csv')
}
