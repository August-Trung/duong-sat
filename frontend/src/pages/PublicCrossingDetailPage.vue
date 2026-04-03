<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { toAssetUrl } from '../api'
import { loadCrossingDetail, loadPublicOverview, locateUser, publicFilters, publicState } from '../stores/publicData'
import {
  fieldRouteGuidance,
  forecastWindowForCrossing,
  formatCoordinate,
  formatDistance,
  haversineDistanceMeters,
  incidentsForCrossing,
  qualityAlertsForPublic,
  riskSummaryForCrossing,
  safetyGuidance,
  upcomingSchedulesForCrossing,
} from '../utils/publicHelpers'

const route = useRoute()
const uiState = reactive({
  fieldMode: false,
})

const crossingId = computed(() => Number(route.params.id || 0))
const crossing = computed(() => publicState.selectedCrossing)
const riskSummary = computed(() =>
  riskSummaryForCrossing(crossing.value, publicState.incidents, publicState.schedules)
)
const forecast = computed(() =>
  forecastWindowForCrossing(crossing.value, publicState.schedules, 30)
)
const recentIncidents = computed(() =>
  incidentsForCrossing(crossing.value, publicState.incidents, 120).slice(0, 6)
)
const upcomingSchedules = computed(() =>
  upcomingSchedulesForCrossing(crossing.value, publicState.schedules, 6)
)
const qualityAlerts = computed(() =>
  qualityAlertsForPublic(crossing.value, publicState.schedules)
)
const safetyNotes = computed(() =>
  safetyGuidance(crossing.value, publicState.incidents)
)
const routeNotes = computed(() =>
  fieldRouteGuidance(publicState.userLocation, crossing.value, publicState.crossings)
)
const distanceToCrossing = computed(() =>
  formatDistance(haversineDistanceMeters(publicState.userLocation, crossing.value))
)

function barrierLabel(value) {
  return {
    co_gac: 'Có người gác',
    tu_dong: 'Tự động',
    can_gat: 'Cần gạt',
    khong_co: 'Không có rào chắn',
  }[value] || value || 'Đang cập nhật'
}

function verificationLabel(value) {
  return {
    draft: 'Bản nháp',
    surveyed: 'Đã khảo sát',
    verified: 'Đã xác minh',
  }[value] || value || 'Đang cập nhật'
}

function formatWhen(dateValue) {
  const date = dateValue instanceof Date ? dateValue : new Date(dateValue)
  if (Number.isNaN(date.getTime())) return 'Không rõ thời điểm'
  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    day: '2-digit',
    month: '2-digit',
  }).format(date)
}

async function ensureCrossingLoaded(id) {
  if (!id) return
  if (!publicState.crossings.length || !publicState.schedules.length || !publicState.incidents.length) {
    await loadPublicOverview(publicFilters)
  }
  if (publicState.selectedCrossingId !== id || !publicState.selectedCrossing) {
    await loadCrossingDetail(id)
  }
}

async function useLiveLocation() {
  try {
    await locateUser()
  } catch {
    // Error is stored in shared state.
  }
}

function syncFieldModeFromViewport() {
  if (typeof window === 'undefined') return
  if (window.innerWidth <= 720) {
    uiState.fieldMode = true
  }
}

onMounted(async () => {
  syncFieldModeFromViewport()
  window.addEventListener('resize', syncFieldModeFromViewport)
  await ensureCrossingLoaded(crossingId.value)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncFieldModeFromViewport)
})

watch(crossingId, async (id) => {
  await ensureCrossingLoaded(id)
})
</script>

<template>
  <section class="crossing-detail-page" :class="{ 'is-field-mode': uiState.fieldMode }">
    <section class="content-card crossing-detail-hero">
      <div class="section-head crossing-detail-hero__head">
        <div>
          <p class="micro-label">Hồ sơ điểm giao cắt</p>
          <h3>{{ crossing?.name || 'Đang tải hồ sơ điểm' }}</h3>
          <p class="body-copy">
            Xem trạng thái rào chắn, mức rủi ro, lịch tàu gần nhất, ảnh hiện trường và hướng dẫn
            an toàn trên cùng một màn hình.
          </p>
        </div>

        <div class="toolbar-actions">
          <RouterLink class="secondary-button" to="/">Quay lại bản đồ</RouterLink>
          <button class="secondary-button" type="button" @click="uiState.fieldMode = !uiState.fieldMode">
            {{ uiState.fieldMode ? 'Tắt chế độ hiện trường' : 'Bật chế độ hiện trường' }}
          </button>
          <button class="primary-button" type="button" :disabled="publicState.locating" @click="useLiveLocation">
            {{ publicState.locating ? 'Đang định vị...' : 'Dùng vị trí của tôi' }}
          </button>
        </div>
      </div>

      <div v-if="crossing" class="crossing-summary-banner">
        <div>
          <span class="risk-chip" :class="crossing.risk_level">{{ riskSummary.label }}</span>
          <strong>{{ riskSummary.message }}</strong>
        </div>
        <span class="soft-badge soft-badge--accent">Điểm rủi ro {{ crossing.risk_score }}</span>
      </div>
    </section>

    <div class="crossing-detail-grid">
      <section class="story-rail">
        <section class="content-card">
          <div v-if="publicState.detailLoading" class="empty-note">Đang tải hồ sơ chi tiết...</div>

          <template v-else-if="crossing">
            <div class="data-grid crossing-detail-topgrid">
              <article class="data-card">
                <span>Mã điểm</span>
                <strong>{{ crossing.code }}</strong>
              </article>
              <article class="data-card">
                <span>Rào chắn</span>
                <strong>{{ barrierLabel(crossing.barrier_type) }}</strong>
              </article>
              <article class="data-card">
                <span>Trạng thái hồ sơ</span>
                <strong>{{ verificationLabel(crossing.verification_status) }}</strong>
              </article>
              <article class="data-card">
                <span>Khoảng cách</span>
                <strong>{{ distanceToCrossing }}</strong>
              </article>
            </div>

            <div v-if="publicState.userLocation" class="info-banner">
              Vị trí hiện tại:
              {{ formatCoordinate(publicState.userLocation.latitude) }},
              {{ formatCoordinate(publicState.userLocation.longitude) }}
              <span v-if="publicState.userLocation.accuracy">
                · sai số {{ formatDistance(publicState.userLocation.accuracy) }}
              </span>
            </div>

            <article class="content-block">
              <h4>Tóm tắt rủi ro dễ hiểu</h4>
              <div class="stack-list">
                <div class="stack-item stack-item--highlight">
                  <strong>{{ riskSummary.label }}</strong>
                  <span>{{ riskSummary.message }}</span>
                </div>
                <div
                  v-for="reason in riskSummary.reasons"
                  :key="reason"
                  class="stack-item"
                >
                  <strong>{{ reason }}</strong>
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Dự báo thời điểm cần chú ý</h4>
              <div class="forecast-panel">
                <div class="inline-stat">
                  <span>{{ forecast.windowMinutes }} phút tới</span>
                  <strong>{{ forecast.count }} chuyến</strong>
                </div>
                <div class="inline-stat">
                  <span>Chuyến gần nhất</span>
                  <strong>{{ forecast.nextPassAt ? formatWhen(forecast.nextPassAt) : 'Chưa rõ' }}</strong>
                </div>
              </div>

              <div class="stack-list">
                <div
                  v-for="schedule in forecast.schedules"
                  :key="`${schedule.id}-${schedule.pass_time}`"
                  class="stack-item"
                >
                  <strong>{{ schedule.pass_time }} · {{ schedule.train_no }}</strong>
                  <span>{{ schedule.direction }} · {{ schedule.station_name }}</span>
                </div>
                <div v-if="!forecast.schedules.length" class="empty-note">
                  Chưa ghi nhận chuyến tàu nào trong 30 phút tới cho điểm này.
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Ảnh hiện trường</h4>
              <div v-if="crossing.images?.length" class="detail-image-grid">
                <article
                  v-for="image in crossing.images.slice(0, uiState.fieldMode ? 4 : 6)"
                  :key="image.id"
                  class="detail-image-card"
                >
                  <img :src="toAssetUrl(image.url)" :alt="image.original_name" />
                  <div class="detail-image-card__meta">
                    <strong>{{ image.original_name }}</strong>
                    <span>{{ image.is_cover ? 'Ảnh đại diện' : 'Ảnh bổ sung' }}</span>
                  </div>
                </article>
              </div>
              <div v-else class="empty-note">
                Chưa có ảnh hiện trường cho điểm này.
              </div>
            </article>

            <article class="content-block">
              <h4>Cảnh báo chất lượng dữ liệu</h4>
              <div class="stack-list">
                <div v-for="alert in qualityAlerts" :key="alert" class="stack-item">
                  <strong>{{ alert }}</strong>
                </div>
                <div v-if="!qualityAlerts.length" class="info-banner">
                  Hồ sơ hiện đủ dữ liệu cơ bản để người dùng tra cứu nhanh tại hiện trường.
                </div>
              </div>
            </article>
          </template>

          <div v-else class="empty-note">
            Không tìm thấy hồ sơ điểm giao cắt này.
          </div>
        </section>
      </section>

      <aside class="story-rail">
        <section class="content-card sticky-panel crossing-detail-side">
          <template v-if="crossing">
            <article class="content-block">
              <h4>Hướng dẫn an toàn</h4>
              <div class="stack-list">
                <div v-for="note in safetyNotes" :key="note" class="stack-item">
                  <strong>{{ note }}</strong>
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Lộ trình an toàn cơ bản</h4>
              <div class="stack-list">
                <div v-for="note in routeNotes" :key="note" class="stack-item">
                  <strong>{{ note }}</strong>
                </div>
                <div v-if="!publicState.userLocation" class="empty-note">
                  Bật vị trí để hệ thống gợi ý các điểm rủi ro cao nên tránh khi tiếp cận.
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Lịch tàu gần nhất</h4>
              <div class="stack-list">
                <div
                  v-for="schedule in upcomingSchedules"
                  :key="`${schedule.id}-${schedule.pass_time}`"
                  class="stack-item"
                >
                  <strong>{{ formatWhen(schedule.nextPassAt) }}</strong>
                  <span>{{ schedule.train_no }} · {{ schedule.direction }}</span>
                </div>
                <div v-if="!upcomingSchedules.length" class="empty-note">
                  Chưa có lịch tàu khả dụng cho điểm này.
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Sự cố gần đây</h4>
              <div class="stack-list">
                <div v-for="incident in recentIncidents" :key="incident.id" class="stack-item">
                  <strong>{{ incident.title }}</strong>
                  <span>{{ incident.incident_date || 'Không rõ ngày' }}</span>
                </div>
                <div v-if="!recentIncidents.length" class="empty-note">
                  Chưa ghi nhận sự cố gần đây cho điểm này.
                </div>
              </div>
            </article>

            <article class="content-block">
              <h4>Thông tin hiện trường</h4>
              <div class="stack-list">
                <div class="stack-item">
                  <strong>{{ crossing.address || 'Chưa cập nhật địa chỉ' }}</strong>
                  <span>{{ crossing.ward || crossing.district || crossing.city || 'Biên Hòa' }}</span>
                </div>
                <div class="stack-item">
                  <strong>{{ crossing.manager_name || 'Chưa có người phụ trách' }}</strong>
                  <span>{{ crossing.manager_phone || 'Chưa có số liên hệ' }}</span>
                </div>
                <div class="stack-item">
                  <strong>{{ crossing.notes || 'Chưa có ghi chú bổ sung' }}</strong>
                </div>
              </div>
            </article>
          </template>
        </section>
      </aside>
    </div>

    <div v-if="crossing" class="crossing-detail-mobile-bar">
      <RouterLink class="secondary-button" to="/">Bản đồ</RouterLink>
      <button class="secondary-button" type="button" @click="uiState.fieldMode = !uiState.fieldMode">
        {{ uiState.fieldMode ? 'Gọn hơn' : 'Hiện trường' }}
      </button>
      <button class="primary-button" type="button" :disabled="publicState.locating" @click="useLiveLocation">
        {{ publicState.locating ? 'Đang định vị...' : 'Định vị' }}
      </button>
    </div>
  </section>
</template>
