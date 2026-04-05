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

export function describeUserLocation(location) {
  if (!location) return ''
  const accuracy = Number(location.accuracy || 0)

  if (location.source === 'manual') {
    return 'Vị trí chọn thủ công'
  }

  if (!accuracy) {
    return ''
  }

  if (accuracy > 5000) {
    return 'Độ chính xác thấp'
  }

  return `Sai số ${formatDistance(accuracy)}`
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
  const embeddedSchedules = Array.isArray(crossing?.schedules) ? crossing.schedules : []
  if (embeddedSchedules.length) {
    return embeddedSchedules.slice(0, limit)
  }

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

function parseScheduleMoment(schedule, now = new Date()) {
  const timeText = String(schedule?.pass_time || '').trim()
  const match = timeText.match(/^(\d{1,2}):(\d{2})$/)
  if (!match) return null

  const hours = Number(match[1])
  const minutes = Number(match[2])
  if (!Number.isFinite(hours) || !Number.isFinite(minutes)) return null

  const candidate = new Date(now)
  candidate.setSeconds(0, 0)
  candidate.setHours(hours, minutes, 0, 0)
  candidate.setDate(candidate.getDate() + Number(schedule?.day_offset || 0))

  if (candidate.getTime() < now.getTime() - 5 * 60 * 1000) {
    candidate.setDate(candidate.getDate() + 1)
  }

  return candidate
}

export function upcomingSchedulesForCrossing(crossing, schedules = [], limit = 6, now = new Date()) {
  return schedulesForCrossing(crossing, schedules, 40)
    .map((schedule) => ({
      ...schedule,
      nextPassAt: parseScheduleMoment(schedule, now),
    }))
    .filter((schedule) => schedule.nextPassAt)
    .sort((left, right) => left.nextPassAt - right.nextPassAt)
    .slice(0, limit)
}

export function forecastWindowForCrossing(crossing, schedules = [], windowMinutes = 30, now = new Date()) {
  const windowMs = windowMinutes * 60 * 1000
  const upcoming = upcomingSchedulesForCrossing(crossing, schedules, 20, now)
  const withinWindow = upcoming.filter(
    (schedule) => schedule.nextPassAt.getTime() - now.getTime() <= windowMs
  )

  return {
    count: withinWindow.length,
    windowMinutes,
    nextPassAt: upcoming[0]?.nextPassAt || null,
    schedules: withinWindow,
  }
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

export function riskSummaryForCrossing(crossing, incidents = [], schedules = []) {
  const reasons = []
  const riskScore = Number(crossing?.risk_score || 0)
  const barrier = normalizeText(crossing?.barrier_type)
  const recentIncidentCount = incidentsForCrossing(crossing, incidents, 90).length
  const forecast = forecastWindowForCrossing(crossing, schedules, 30)
  const dailyScheduleCount =
    Number(crossing?.evidence?.schedule_count || 0) || schedulesForCrossing(crossing, schedules, 20).length

  if (['khong_co', 'none', 'khong co', 'khĂ´ng cĂ³'].includes(barrier)) {
    reasons.push('không có rào chắn')
  } else if (['tu_dong', 'can_gat'].includes(barrier)) {
    reasons.push('cần quan sát kỹ trạng thái rào chắn')
  }

  if (recentIncidentCount >= 2) {
    reasons.push(`đã có ${recentIncidentCount} sự cố gần đây`)
  } else if (recentIncidentCount === 1) {
    reasons.push('đã có sự cố gần đây')
  }

  if (forecast.count >= 2) {
    reasons.push(`${forecast.windowMinutes} phút tới có ${forecast.count} chuyến qua`)
  } else if (forecast.count === 1) {
    reasons.push('sắp có tàu đi qua')
  }

  if (dailyScheduleCount >= 12) {
    reasons.push('mật độ tàu cao')
  }

  if (!crossing?.manager_name) {
    reasons.push('chưa có người phụ trách rõ ràng')
  }

  let tone = 'Thấp'
  if (crossing?.risk_level === 'very_high' || riskScore >= 85) tone = 'Rất nguy hiểm'
  else if (crossing?.risk_level === 'high' || riskScore >= 65) tone = 'Nguy hiểm cao'
  else if (crossing?.risk_level === 'medium' || riskScore >= 40) tone = 'Cần chú ý'

  return {
    label: tone,
    score: riskScore,
    reasons,
    message: reasons.length ? `${tone} vì ${reasons.join(' + ')}` : `${tone} theo dữ liệu hiện có`,
  }
}

export function qualityAlertsForPublic(crossing, schedules = []) {
  if (!crossing) return []

  const alerts = []
  if (!crossing.latitude || !crossing.longitude) {
    alerts.push('Thiếu tọa độ, vị trí trên bản đồ có thể chưa chính xác.')
  }
  if (!crossing.images?.length) {
    alerts.push('Chưa có ảnh hiện trường để đối chiếu nhanh tại chỗ.')
  }
  if (!schedulesForCrossing(crossing, schedules, 4).length) {
    alerts.push('Chưa liên kết đủ lịch tàu gần nhất cho điểm này.')
  }
  if (normalizeText(crossing.verification_status) !== 'verified') {
    alerts.push('Hồ sơ chưa ở trạng thái xác minh hoàn tất.')
  }
  if (!crossing.manager_name) {
    alerts.push('Chưa có thông tin đơn vị hoặc người phụ trách hiện trường.')
  }
  return alerts
}

export function fieldRouteGuidance(userLocation, targetCrossing, crossings = []) {
  if (!userLocation || !targetCrossing) return []

  const hazardCandidates = crossings
    .filter((item) => item.id !== targetCrossing.id)
    .map((item) => ({
      ...item,
      distanceFromUser: haversineDistanceMeters(userLocation, item),
      distanceFromTarget: haversineDistanceMeters(targetCrossing, item),
    }))
    .filter(
      (item) =>
        Number.isFinite(item.distanceFromUser) &&
        item.distanceFromUser <= 1600 &&
        ['very_high', 'high'].includes(item.risk_level)
    )
    .sort((left, right) => left.distanceFromUser - right.distanceFromUser)
    .slice(0, 3)

  const notes = []

  if (hazardCandidates.length) {
    notes.push(
      `Ưu tiên tránh ${hazardCandidates
        .map((item) => item.name)
        .join(', ')} vì đang là các điểm rủi ro cao gần lộ trình tiếp cận.`
    )
  }

  if (['very_high', 'high'].includes(targetCrossing.risk_level)) {
    notes.push('Nên tiếp cận từ tuyến đường có tầm nhìn thoáng và dừng quan sát trước khi qua giao cắt.')
  }

  if (normalizeText(targetCrossing.barrier_type) === 'khong_co') {
    notes.push('Vì điểm đích không có rào chắn, nên ưu tiên băng qua ở giao cắt có bảo vệ gần nhất nếu có thể.')
  }

  if (!notes.length) {
    notes.push('Giữ tốc độ thấp khi tiếp cận và ưu tiên các điểm qua đường có rào chắn hoặc có người gác.')
  }

  return notes
}
