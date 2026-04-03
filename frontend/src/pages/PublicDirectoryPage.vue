<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { loadCrossingDetail, publicFilters, publicState } from '../stores/publicData'
import {
  applyCrossingFilters,
  formatDistance,
  haversineDistanceMeters,
  incidentsForCrossing,
  riskSummaryForCrossing,
  schedulesForCrossing,
} from '../utils/publicHelpers'

const router = useRouter()

const filteredRows = computed(() =>
  applyCrossingFilters(publicState.crossings, publicFilters, {
    incidents: publicState.incidents,
    distanceSource: publicState.userLocation || publicState.areaAlert.center,
  })
)

const groupedRows = computed(() => {
  const priority = filteredRows.value.slice(0, 3)
  const regular = filteredRows.value.slice(3)
  return { priority, regular }
})

const selectedRecentIncidents = computed(() =>
  incidentsForCrossing(publicState.selectedCrossing, publicState.incidents, 90)
)

const selectedSchedules = computed(() =>
  schedulesForCrossing(publicState.selectedCrossing, publicState.schedules, 6)
)

const selectedRiskSummary = computed(() =>
  riskSummaryForCrossing(publicState.selectedCrossing, publicState.incidents, publicState.schedules)
)

function riskLabel(level) {
  return {
    very_high: 'Rất cao',
    high: 'Cao',
    medium: 'Trung bình',
    low: 'Thấp',
    unknown: 'Chưa xác định',
  }[level] || level
}

function crossingDistance(crossing) {
  return formatDistance(
    haversineDistanceMeters(publicState.userLocation || publicState.areaAlert.center, crossing)
  )
}

async function openCrossingDetail(id) {
  await loadCrossingDetail(id)
  router.push({ name: 'public-crossing-detail', params: { id } })
}
</script>

<template>
  <section class="directory-board">
    <section class="feature-strip">
      <article
        v-for="item in groupedRows.priority"
        :key="item.id"
        class="feature-card"
        @click="openCrossingDetail(item.id)"
      >
        <div class="feature-card__head">
          <span class="micro-label">Ưu tiên theo bộ lọc</span>
          <span class="risk-chip compact" :class="item.risk_level">{{ riskLabel(item.risk_level) }}</span>
        </div>
        <h3>{{ item.name }}</h3>
        <p>{{ item.address || `${item.district}, ${item.city}` }}</p>
        <div class="feature-card__meta">
          <span>{{ item.code }}</span>
          <span>{{ crossingDistance(item) }}</span>
        </div>
      </article>
    </section>

    <div class="directory-layout">
      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Danh mục trực quan</p>
            <h3>{{ filteredRows.length }} điểm phù hợp</h3>
          </div>
        </div>

        <div class="catalog-grid">
          <button
            v-for="item in groupedRows.regular"
            :key="item.id"
            class="catalog-card"
            :class="{ active: item.id === publicState.selectedCrossingId }"
            @click="openCrossingDetail(item.id)"
          >
            <div class="catalog-card__top">
              <span class="risk-chip compact" :class="item.risk_level">{{ riskLabel(item.risk_level) }}</span>
              <small>{{ crossingDistance(item) }}</small>
            </div>
            <strong>{{ item.name }}</strong>
            <span class="catalog-card__code">{{ item.code }}</span>
            <span class="catalog-card__address">{{ item.address || `${item.district}, ${item.city}` }}</span>
            <div class="catalog-card__bottom">
              <small>{{ item.barrier_type || 'Đang cập nhật' }}</small>
              <small>{{ item.risk_score }} điểm</small>
            </div>
          </button>
        </div>

        <div v-if="!filteredRows.length" class="empty-note">
          Không có điểm nào khớp với bộ lọc hiện tại.
        </div>
      </section>

      <aside class="story-rail">
        <section class="content-card sticky-panel">
          <div class="section-head">
            <div>
              <p class="micro-label">Hồ sơ điểm</p>
              <h3>{{ publicState.selectedCrossing?.name || 'Chọn một điểm để xem chi tiết' }}</h3>
            </div>
          </div>

          <template v-if="publicState.selectedCrossing">
            <div class="data-grid">
              <article class="data-card">
                <span>Mã điểm</span>
                <strong>{{ publicState.selectedCrossing.code }}</strong>
              </article>
              <article class="data-card">
                <span>Loại giao cắt</span>
                <strong>{{ publicState.selectedCrossing.crossing_type || 'Đang cập nhật' }}</strong>
              </article>
              <article class="data-card">
                <span>Rào chắn</span>
                <strong>{{ publicState.selectedCrossing.barrier_type || 'Đang cập nhật' }}</strong>
              </article>
              <article class="data-card">
                <span>Khoảng cách</span>
                <strong>{{ crossingDistance(publicState.selectedCrossing) }}</strong>
              </article>
            </div>

            <article class="content-block">
              <h4>Tóm tắt rủi ro</h4>
              <div class="stack-list">
                <div class="stack-item stack-item--highlight">
                  <strong>{{ selectedRiskSummary.label }}</strong>
                  <span>{{ selectedRiskSummary.message }}</span>
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Lịch tàu gần nhất</h4>
              <div class="stack-list">
                <div
                  v-for="schedule in selectedSchedules"
                  :key="`${schedule.id}-${schedule.pass_time}`"
                  class="stack-item"
                >
                  <strong>{{ schedule.pass_time }}</strong>
                  <span>{{ schedule.train_no }} · {{ schedule.direction }}</span>
                </div>
                <div v-if="!selectedSchedules.length" class="empty-note">
                  Chưa có dữ liệu lịch tàu gần nhất.
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Sự cố trong 90 ngày</h4>
              <div class="stack-list">
                <div v-for="incident in selectedRecentIncidents" :key="incident.id" class="stack-item">
                  <strong>{{ incident.title }}</strong>
                  <span>{{ incident.incident_date || 'Không rõ ngày' }}</span>
                </div>
                <div v-if="!selectedRecentIncidents.length" class="empty-note">
                  Chưa ghi nhận sự cố phù hợp.
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Ghi chú</h4>
              <p class="body-copy">{{ publicState.selectedCrossing.notes || 'Chưa có ghi chú bổ sung.' }}</p>
            </article>

            <div class="toolbar-actions">
              <button
                class="primary-button"
                type="button"
                @click="openCrossingDetail(publicState.selectedCrossing.id)"
              >
                Mở hồ sơ 360
              </button>
            </div>
          </template>

          <div v-else class="empty-note">
            Chọn một thẻ trong danh mục để xem hồ sơ điểm, lịch tàu và dữ liệu sự cố.
          </div>
        </section>
      </aside>
    </div>
  </section>
</template>
