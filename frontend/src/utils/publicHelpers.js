export function normalizeText(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase()
    .trim()
}

export function haversineDistanceMeters(a, b) {
  if (!a?.latitude || !a?.longitude || !b?.latitude || !b?.longitude) {
    return Number.POSITIVE_INFINITY
  }

  const toRadians = (degrees) => (degrees * Math.PI) / 180
  const earthRadius = 6371000
  const dLat = toRadians(b.latitude - a.latitude)
  const dLng = toRadians(b.longitude - a.longitude)
  const lat1 = toRadians(a.latitude)
  const lat2 = toRadians(b.latitude)
  const sinLat = Math.sin(dLat / 2)
  const sinLng = Math.sin(dLng / 2)
  const value = sinLat * sinLat + Math.cos(lat1) * Math.cos(lat2) * sinLng * sinLng

  return 2 * earthRadius * Math.atan2(Math.sqrt(value), Math.sqrt(1 - value))
}

export function formatDistance(distanceMeters) {
  if (!Number.isFinite(distanceMeters)) return 'Chưa có khoảng cách'
  if (distanceMeters < 1000) return `${Math.round(distanceMeters)} m`
  return `${(distanceMeters / 1000).toFixed(distanceMeters >= 10000 ? 0 : 1)} km`
}

export function formatCoordinate(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(5) : 'n/a'
}

export function sortByRiskThenName(items) {
  const rank = { very_high: 0, high: 1, medium: 2, low: 3, unknown: 4 }
  return [...items].sort((left, right) => {
    const rankDelta = (rank[left.risk_level] ?? 99) - (rank[right.risk_level] ?? 99)
    if (rankDelta !== 0) return rankDelta
    return String(left.name || '').localeCompare(String(right.name || ''), 'vi')
  })
}

export function isRecentDate(dateValue, days = 30) {
  if (!dateValue) return false
  const date = new Date(dateValue)
  if (Number.isNaN(date.getTime())) return false
  return date.getTime() >= Date.now() - days * 24 * 60 * 60 * 1000
}

export function crossingSearchText(crossing) {
  return [
    crossing?.name,
    crossing?.code,
    crossing?.address,
    crossing?.district,
    crossing?.city,
    crossing?.ward,
    crossing?.manager_name,
  ]
    .filter(Boolean)
    .join(' ')
}

export function schedulesForCrossing(crossing, schedules = [], limit = 4) {
  const crossingName = normalizeText(crossing?.name)
  const crossingCode = normalizeText(crossing?.code)
  return schedules
    .filter((schedule) => {
      const scheduleCrossingId = schedule.crossing_id ?? schedule.crossingId
      if (scheduleCrossingId && scheduleCrossingId === crossing?.id) return true
      const blob = normalizeText([
        schedule.crossing_name,
        schedule.crossing_code,
        schedule.note,
        schedule.notes,
      ].join(' '))
      return Boolean(
        (crossingName && blob.includes(crossingName)) ||
          (crossingCode && blob.includes(crossingCode))
      )
    })
    .slice(0, limit)
}

export function incidentsForCrossing(crossing, incidents = [], days = null) {
  const crossingName = normalizeText(crossing?.name)
  const crossingCode = normalizeText(crossing?.code)
  return incidents.filter((incident) => {
    const incidentCrossingId = incident.crossing_id ?? incident.crossingId
    const matchById = incidentCrossingId && incidentCrossingId === crossing?.id
    const blob = normalizeText([
      incident.crossing_name,
      incident.crossing_code,
      incident.title,
      incident.description,
    ].join(' '))
    const matchByText = Boolean(
      (crossingName && blob.includes(crossingName)) ||
        (crossingCode && blob.includes(crossingCode))
    )
    if (!(matchById || matchByText)) return false
    return days ? isRecentDate(incident.incident_date, days) : true
  })
}

export function buildSearchSuggestions(crossings = [], query = '', limit = 6) {
  const normalizedQuery = normalizeText(query)
  if (!normalizedQuery) return []
  return crossings
    .filter((crossing) => normalizeText(crossingSearchText(crossing)).includes(normalizedQuery))
    .slice(0, limit)
}

export function applyCrossingFilters(crossings = [], filters = {}, context = {}) {
  const query = normalizeText(filters.q)
  const district = normalizeText(filters.district)
  const barrier = normalizeText(filters.barrier_type)
  const risk = normalizeText(filters.risk_level)
  const radiusMeters = Number(filters.radius_meters || 0)
  const onlyNearby = Boolean(filters.only_nearby)
  const onlyRecentIncidents = Boolean(filters.only_recent_incidents)
  const onlyNoBarrier = Boolean(filters.only_unprotected)
  const sourcePoint = context.distanceSource

  let result = crossings.filter((crossing) => {
    if (query && !normalizeText(crossingSearchText(crossing)).includes(query)) return false
    if (district && normalizeText(crossing.district) !== district) return false
    if (barrier && normalizeText(crossing.barrier_type) !== barrier) return false
    if (risk && normalizeText(crossing.risk_level) !== risk) return false
    if (onlyNoBarrier && !['khong_co', 'none', 'không có'].includes(normalizeText(crossing.barrier_type))) {
      return false
    }

    if ((onlyNearby || radiusMeters > 0) && sourcePoint) {
      const distance = haversineDistanceMeters(sourcePoint, crossing)
      if (!Number.isFinite(distance)) return false
      if (radiusMeters > 0 && distance > radiusMeters) return false
      if (onlyNearby && distance > (radiusMeters || 2000)) return false
    }

    if (onlyRecentIncidents) {
      const count = incidentsForCrossing(crossing, context.incidents || [], 30).length
      if (!count) return false
    }

    return true
  })

  if (filters.sort_by === 'distance' && sourcePoint) {
    result = [...result].sort(
      (left, right) =>
        haversineDistanceMeters(sourcePoint, left) - haversineDistanceMeters(sourcePoint, right)
    )
  } else if (filters.sort_by === 'name') {
    result = [...result].sort((left, right) =>
      String(left.name || '').localeCompare(String(right.name || ''), 'vi')
    )
  } else {
    result = sortByRiskThenName(result)
  }

  return result
}

export function nearestCrossings(crossings = [], sourcePoint, limit = 5) {
  if (!sourcePoint) return []
  return crossings
    .filter((crossing) => Number.isFinite(haversineDistanceMeters(sourcePoint, crossing)))
    .map((crossing) => ({
      ...crossing,
      distanceMeters: haversineDistanceMeters(sourcePoint, crossing),
    }))
    .sort((left, right) => left.distanceMeters - right.distanceMeters)
    .slice(0, limit)
}

export function crossingsInsideArea(crossings = [], area) {
  if (!area?.center || !area?.radiusMeters) return []
  return crossings.filter(
    (crossing) => haversineDistanceMeters(area.center, crossing) <= area.radiusMeters
  )
}

export function safetyGuidance(crossing, incidents = []) {
  const risk = normalizeText(crossing?.risk_level)
  const recentCount = incidentsForCrossing(crossing, incidents, 30).length
  const notes = []

  if (risk === 'very_high' || risk === 'high') {
    notes.push('Giảm tốc độ và quan sát kỹ hai phía trước khi đi qua giao cắt.')
  }
  if (['khong_co', 'none', 'không có'].includes(normalizeText(crossing?.barrier_type))) {
    notes.push('Điểm này không có rào chắn, nên dừng hẳn trước khi băng qua.')
  }
  if (recentCount > 0) {
    notes.push(`Đã có ${recentCount} sự cố gần đây, nên tránh giờ tàu cao điểm nếu có thể.`)
  }
  if (!notes.length) {
    notes.push('Theo dõi biển báo hiện trường và kiểm tra lịch tàu trước khi di chuyển.')
  }

  return notes
}
