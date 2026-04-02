<script setup>
import { computed, reactive } from 'vue'
import { publicFilters, publicState } from '../stores/publicData'
import {
  applyCrossingFilters,
  crossingsInsideArea,
  formatDistance,
  haversineDistanceMeters,
  incidentsForCrossing,
} from '../utils/publicHelpers'

const incidentFilters = reactive({
  q: '',
  severity: '',
})

const filteredCrossings = computed(() =>
  applyCrossingFilters(publicState.crossings, publicFilters, {
    incidents: publicState.incidents,
    distanceSource: publicState.userLocation || publicState.areaAlert.center,
  })
)

const topHazards = computed(() => filteredCrossings.value.slice(0, 6))

const timelineIncidents = computed(() => {
  const query = incidentFilters.q.trim().toLowerCase()
  return publicState.incidents
    .filter((incident) => {
      if (incidentFilters.severity && incident.severity_level !== incidentFilters.severity) return false
      if (!query) return true
      return [incident.title, incident.crossing_name, incident.description]
        .filter(Boolean)
        .join(' ')
        .toLowerCase()
        .includes(query)
    })
    .slice(0, 24)
})

const areaMatches = computed(() => crossingsInsideArea(filteredCrossings.value, publicState.areaAlert))
const areaIncidentCount = computed(() =>
  areaMatches.value.reduce(
    (total, crossing) => total + incidentsForCrossing(crossing, publicState.incidents, 30).length,
    0
  )
)

function distanceToCrossing(crossing) {
  return formatDistance(
    haversineDistanceMeters(publicState.userLocation || publicState.areaAlert.center, crossing)
  )
}

function severityLabel(level) {
  return {
    very_high: 'Rất cao',
    high: 'Cao',
    medium: 'Trung bình',
    low: 'Thấp',
  }[level] || 'Chưa rõ'
}
</script>

<template>
  <section class="insight-board">
    <section class="insight-hero">
      <article class="content-card content-card--highlight">
        <p class="micro-label">Điểm nóng nổi bật</p>
        <h3>{{ topHazards[0]?.name || 'Chưa có dữ liệu nổi bật' }}</h3>
        <p class="body-copy">
          {{ topHazards[0]?.address || `${topHazards[0]?.district || 'Biên Hòa'}, ${topHazards[0]?.city || ''}` }}
        </p>
        <div v-if="topHazards[0]" class="hero-inline-stats">
          <span class="soft-badge">{{ topHazards[0].risk_score }} điểm rủi ro</span>
          <span class="soft-badge soft-badge--accent">{{ distanceToCrossing(topHazards[0]) }}</span>
        </div>
      </article>

      <article class="content-card">
        <p class="micro-label">Cảnh báo khu vực</p>
        <h3>{{ areaMatches.length }} điểm trong vùng quan tâm</h3>
        <p class="body-copy">
          Có {{ areaIncidentCount }} sự cố được ghi nhận trong 30 ngày gần nhất quanh vùng đang theo dõi.
        </p>
        <div class="hero-inline-stats">
          <span class="soft-badge">{{ publicState.areaAlert.label || 'Chưa chọn tâm cảnh báo' }}</span>
        </div>
      </article>
    </section>

    <div class="insight-layout">
      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Ưu tiên kiểm soát</p>
            <h3>Danh sách rủi ro cao</h3>
          </div>
        </div>

        <div class="priority-list">
          <article v-for="item in topHazards" :key="item.id" class="priority-row">
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ item.district }}, {{ item.city }} · {{ distanceToCrossing(item) }}</span>
            </div>
            <div class="priority-row__side">
              <span class="risk-chip compact" :class="item.risk_level">{{ item.risk_score }}</span>
            </div>
          </article>
        </div>
      </section>

      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Theo dõi khu vực</p>
            <h3>Điểm nằm trong bán kính cảnh báo</h3>
          </div>
        </div>

        <div class="stack-list">
          <div v-for="item in areaMatches.slice(0, 8)" :key="item.id" class="stack-item">
            <strong>{{ item.name }}</strong>
            <span>{{ item.address || item.district }} · {{ item.risk_score }} điểm</span>
          </div>
          <div v-if="!areaMatches.length" class="empty-note">
            Chưa có vùng quan tâm để phân tích. Hãy chọn vị trí hoặc một điểm trên bản đồ.
          </div>
        </div>
      </section>
    </div>

    <section class="content-card">
      <div class="section-head">
        <div>
          <p class="micro-label">Timeline sự cố</p>
          <h3>Dòng thời gian mới nhất</h3>
        </div>
      </div>

      <div class="filter-row">
        <label class="field">
          <span>Tìm theo tiêu đề hoặc điểm</span>
          <input v-model="incidentFilters.q" placeholder="Tên điểm, tiêu đề sự cố..." />
        </label>

        <label class="field field--compact">
          <span>Mức độ</span>
          <select v-model="incidentFilters.severity">
            <option value="">Tất cả</option>
            <option value="very_high">Rất cao</option>
            <option value="high">Cao</option>
            <option value="medium">Trung bình</option>
            <option value="low">Thấp</option>
          </select>
        </label>
      </div>

      <div class="timeline-grid">
        <article v-for="incident in timelineIncidents" :key="incident.id" class="timeline-card">
          <div class="timeline-card__head timeline-card__head--stacked">
            <small>{{ incident.incident_date || 'Không rõ ngày' }}</small>
            <span class="soft-badge">{{ severityLabel(incident.severity_level) }}</span>
          </div>
          <strong>{{ incident.title }}</strong>
          <p>{{ incident.crossing_name || 'Chưa gắn điểm giao cắt' }}</p>
        </article>
        <div v-if="!timelineIncidents.length" class="empty-note">
          Không có sự cố phù hợp với bộ lọc hiện tại.
        </div>
      </div>
    </section>
  </section>
</template>
