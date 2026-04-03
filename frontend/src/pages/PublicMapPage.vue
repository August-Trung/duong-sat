<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import MapPanel from '../components/MapPanel.vue'
import {
  clearPublicError,
  loadCrossingDetail,
  locateUser,
  publicFilters,
  publicState,
  setAreaAlertRadius,
  setUserLocation,
  useSelectedCrossingAsArea,
  useUserLocationAsArea,
} from '../stores/publicData'
import {
  applyCrossingFilters,
  crossingsInsideArea,
  describeUserLocation,
  formatCoordinate,
  formatDistance,
  haversineDistanceMeters,
  incidentsForCrossing,
  nearestCrossings,
  riskSummaryForCrossing,
  safetyGuidance,
  schedulesForCrossing,
} from '../utils/publicHelpers'

const router = useRouter()
const mapMode = reactive({ value: 'light' })
const visibleLevels = reactive({
  very_high: true,
  high: true,
  medium: true,
  low: true,
  unknown: true,
})
const overlays = reactive({
  crossings: true,
  highRiskOnly: true,
  warningZones: true,
})
const uiState = reactive({
  pickingLocation: false,
})
const toastMessage = ref('')

let toastTimer = null

const distanceSource = computed(
  () => publicState.userLocation || publicState.areaAlert.center || publicState.selectedCrossing
)

const filteredCrossings = computed(() =>
  applyCrossingFilters(publicState.crossings, publicFilters, {
    incidents: publicState.incidents,
    distanceSource: distanceSource.value,
  })
)

const nearest = computed(() => nearestCrossings(filteredCrossings.value, publicState.userLocation, 5))
const areaMatches = computed(() => crossingsInsideArea(filteredCrossings.value, publicState.areaAlert))
const areaIncidents = computed(() =>
  publicState.incidents.filter((incident) =>
    areaMatches.value.some((crossing) => {
      const incidentCrossingId = incident.crossing_id ?? incident.crossingId
      return incidentCrossingId
        ? incidentCrossingId === crossing.id
        : incident.crossing_name === crossing.name
    })
  )
)
const selectedUpcomingSchedules = computed(() =>
  schedulesForCrossing(publicState.selectedCrossing, publicState.schedules, 4)
)
const selectedRecentIncidents = computed(() =>
  incidentsForCrossing(publicState.selectedCrossing, publicState.incidents, 60).slice(0, 5)
)
const selectedNearby = computed(() => {
  if (!publicState.selectedCrossing) return []
  return nearestCrossings(publicState.crossings, publicState.selectedCrossing, 4).filter(
    (item) => item.id !== publicState.selectedCrossingId
  )
})
const selectedGuidance = computed(() =>
  safetyGuidance(publicState.selectedCrossing, publicState.incidents)
)
const selectedRiskSummary = computed(() =>
  riskSummaryForCrossing(publicState.selectedCrossing, publicState.incidents, publicState.schedules)
)
const highlightedIds = computed(() => [
  ...nearest.value.map((item) => item.id),
  ...areaMatches.value.map((item) => item.id),
])

function showToast(message) {
  toastMessage.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toastMessage.value = ''
    clearPublicError()
  }, 4200)
}

function dismissToast() {
  if (toastTimer) clearTimeout(toastTimer)
  toastMessage.value = ''
  clearPublicError()
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

function severityLabel(level) {
  return {
    very_high: 'Rất cao',
    high: 'Cao',
    medium: 'Trung bình',
    low: 'Thấp',
  }[level] || 'Chưa rõ'
}

function distanceToCrossing(crossing) {
  return formatDistance(haversineDistanceMeters(distanceSource.value, crossing))
}

async function locateAndUseArea() {
  try {
    await locateUser()
    useUserLocationAsArea()
  } catch {
    // Shared state already stores the message.
  }
}

function enableManualLocationPick() {
  uiState.pickingLocation = true
}

function applyPickedLocation(location) {
  setUserLocation(location, {
    label: 'Vị trí của tôi (chỉnh tay)',
    source: 'manual',
  })
  useUserLocationAsArea()
  uiState.pickingLocation = false
}

async function openCrossingDetail(id) {
  await loadCrossingDetail(id)
  router.push({ name: 'public-crossing-detail', params: { id } })
}

watch(
  () => publicState.error,
  (value) => {
    if (value) showToast(value)
  }
)

onBeforeUnmount(() => {
  if (toastTimer) clearTimeout(toastTimer)
})
</script>

<template>
  <section class="experience-grid">
    <section class="map-stage">
      <div v-if="toastMessage" class="map-toast map-toast--error" role="alert">
        <div>
          <strong>Không thể định vị</strong>
          <span>{{ toastMessage }}</span>
        </div>
        <button class="map-toast__close" type="button" @click="dismissToast">Đóng</button>
      </div>

      <div class="section-head">
        <div>
          <p class="micro-label">Không gian trực quan</p>
          <h3>Bản đồ điều hướng rủi ro theo khu vực</h3>
        </div>

        <div class="toolbar-pillset">
          <label
            v-for="level in ['very_high', 'high', 'medium', 'low']"
            :key="level"
            class="switch-pill"
          >
            <input v-model="visibleLevels[level]" type="checkbox" />
            <span>{{ riskLabel(level) }}</span>
          </label>
        </div>
      </div>

      <div class="map-stage__toolbar">
        <div class="toolbar-pillset">
          <label class="switch-pill">
            <input v-model="overlays.crossings" type="checkbox" />
            <span>Điểm giao cắt</span>
          </label>
          <label class="switch-pill">
            <input v-model="overlays.highRiskOnly" type="checkbox" />
            <span>Nhấn điểm nguy hiểm</span>
          </label>
          <label class="switch-pill">
            <input v-model="overlays.warningZones" type="checkbox" />
            <span>Vùng cảnh báo</span>
          </label>
        </div>

        <div class="toolbar-actions">
          <label class="field field--compact map-toolbar__radius">
            <span>Bán kính</span>
            <select
              :value="publicState.areaAlert.radiusMeters"
              @change="setAreaAlertRadius($event.target.value)"
            >
              <option :value="800">800 m</option>
              <option :value="1500">1.5 km</option>
              <option :value="3000">3 km</option>
              <option :value="5000">5 km</option>
            </select>
          </label>

          <button class="primary-button" type="button" @click="locateAndUseArea">
            Dùng vị trí của tôi
          </button>
          <button class="secondary-button" type="button" @click="enableManualLocationPick">
            {{ uiState.pickingLocation ? 'Chạm lên bản đồ để chọn vị trí' : 'Chọn vị trí trên bản đồ' }}
          </button>
          <button
            class="secondary-button"
            type="button"
            :disabled="!publicState.selectedCrossing"
            @click="useSelectedCrossingAsArea"
          >
            Dùng điểm đang chọn làm tâm
          </button>
        </div>

        <div v-if="publicState.userLocation || uiState.pickingLocation" class="map-toolbar__feedback">
          <p v-if="uiState.pickingLocation">Chạm lên bản đồ để chọn một vị trí làm tâm theo dõi.</p>
          <p v-else-if="publicState.userLocation">
            Đang dùng:
            {{ formatCoordinate(publicState.userLocation.latitude) }},
            {{ formatCoordinate(publicState.userLocation.longitude) }}
            <span v-if="describeUserLocation(publicState.userLocation)">
              · {{ describeUserLocation(publicState.userLocation) }}
            </span>
          </p>
        </div>
      </div>

      <MapPanel
        :crossings="filteredCrossings"
        :selected-id="publicState.selectedCrossingId"
        :selected-crossing="publicState.selectedCrossing"
        :visible-levels="visibleLevels"
        :map-mode="mapMode.value"
        :overlays="overlays"
        :user-location="publicState.userLocation"
        :area-alert="publicState.areaAlert"
        :highlighted-ids="highlightedIds"
        :pick-location-mode="uiState.pickingLocation"
        @select="loadCrossingDetail"
        @change-mode="mapMode.value = $event"
        @pick-location="applyPickedLocation"
      />
    </section>

    <aside class="story-rail">
      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Điểm neo hiện tại</p>
            <h3>{{ publicState.selectedCrossing?.name || 'Chọn một điểm trên bản đồ' }}</h3>
          </div>
          <span
            v-if="publicState.selectedCrossing"
            class="risk-chip"
            :class="publicState.selectedCrossing.risk_level"
          >
            {{ riskLabel(publicState.selectedCrossing.risk_level) }} ·
            {{ publicState.selectedCrossing.risk_score }}
          </span>
        </div>

        <template v-if="publicState.selectedCrossing">
          <div class="data-grid">
            <article class="data-card">
              <span>Địa chỉ</span>
              <strong>{{ publicState.selectedCrossing.address || 'Đang cập nhật' }}</strong>
            </article>
            <article class="data-card">
              <span>Khoảng cách</span>
              <strong>{{ distanceToCrossing(publicState.selectedCrossing) }}</strong>
            </article>
            <article class="data-card">
              <span>Tin liên quan</span>
              <strong>{{ publicState.selectedCrossing.evidence?.article_count ?? 0 }}</strong>
            </article>
            <article class="data-card">
              <span>Rào chắn</span>
              <strong>{{ publicState.selectedCrossing.barrier_type || 'Đang cập nhật' }}</strong>
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
            <h4>Khuyến nghị an toàn</h4>
            <div class="stack-list">
              <div v-for="tip in selectedGuidance" :key="tip" class="stack-item">
                <strong>{{ tip }}</strong>
              </div>
            </div>
          </article>

          <article class="content-block">
            <h4>Chuyến tàu sắp tới</h4>
            <div class="stack-list">
              <div
                v-for="schedule in selectedUpcomingSchedules"
                :key="`${schedule.id}-${schedule.pass_time}`"
                class="stack-item"
              >
                <strong>{{ schedule.pass_time }}</strong>
                <span>
                  {{ schedule.train_no }} · {{ schedule.direction }}
                  <template v-if="schedule.eta_label"> · {{ schedule.eta_label }}</template>
                </span>
              </div>
              <div v-if="!selectedUpcomingSchedules.length" class="empty-note">
                Chưa có dữ liệu lịch tàu gần nhất.
              </div>
            </div>
          </article>

          <article class="content-block">
            <h4>Sự cố gần đây</h4>
            <div class="stack-list">
              <div v-for="incident in selectedRecentIncidents" :key="incident.id" class="stack-item">
                <strong>{{ incident.title }}</strong>
                <span class="meta-line">{{ incident.incident_date || 'Không rõ ngày' }}</span>
                <span class="meta-line">Mức độ: {{ severityLabel(incident.severity_level) }}</span>
              </div>
              <div v-if="!selectedRecentIncidents.length" class="empty-note">
                Chưa ghi nhận sự cố gần đây tại điểm này.
              </div>
            </div>
          </article>

          <div class="toolbar-actions">
            <button
              class="primary-button"
              type="button"
              @click="openCrossingDetail(publicState.selectedCrossing.id)"
            >
              Xem chi tiết điểm
            </button>
          </div>
        </template>

        <div v-else class="empty-note">
          Hãy chọn một điểm trên bản đồ để xem chi tiết điểm, lịch tàu và khuyến nghị an toàn.
        </div>
      </section>

      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Gợi ý theo vị trí</p>
            <h3>Điểm gần bạn</h3>
          </div>
        </div>

        <div class="stack-list">
          <button
            v-for="item in nearest"
            :key="item.id"
            class="list-button"
            @click="openCrossingDetail(item.id)"
          >
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ formatDistance(item.distanceMeters) }} · {{ item.address || item.district }}</span>
            </div>
            <span class="risk-chip compact" :class="item.risk_level">{{ riskLabel(item.risk_level) }}</span>
          </button>
          <div v-if="!nearest.length" class="empty-note">Bật vị trí để xem danh sách gần bạn.</div>
        </div>
      </section>

      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Theo dõi khu vực</p>
            <h3>{{ areaMatches.length }} điểm trong vùng quan tâm</h3>
          </div>
          <span v-if="publicState.areaAlert.label" class="soft-badge">
            {{ publicState.areaAlert.label }}
          </span>
        </div>

        <div class="stack-list">
          <button
            v-for="item in areaMatches.slice(0, 6)"
            :key="item.id"
            class="list-button"
            @click="openCrossingDetail(item.id)"
          >
            <div>
              <strong>{{ item.name }}</strong>
              <span>{{ item.address || item.district }} · {{ distanceToCrossing(item) }}</span>
            </div>
            <small>{{ item.risk_score }}</small>
          </button>
          <div v-if="!areaMatches.length" class="empty-note">
            Dùng vị trí hiện tại hoặc điểm đang chọn để bật theo dõi khu vực.
          </div>
          <div v-else-if="areaIncidents.length" class="info-banner">
            Có {{ areaIncidents.length }} sự cố xuất hiện trong vùng quan tâm hiện tại.
          </div>
        </div>
      </section>

      <section v-if="publicState.selectedCrossing" class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Lân cận</p>
            <h3>Điểm gần điểm đang chọn</h3>
          </div>
        </div>

        <div class="stack-list">
          <button
            v-for="crossing in selectedNearby"
            :key="crossing.id"
            class="list-button"
            @click="openCrossingDetail(crossing.id)"
          >
            <div>
              <strong>{{ crossing.name }}</strong>
              <span>{{ formatDistance(crossing.distanceMeters) }}</span>
            </div>
          </button>
          <div v-if="!selectedNearby.length" class="empty-note">
            Không có đủ điểm lân cận để gợi ý thêm.
          </div>
        </div>
      </section>
    </aside>
  </section>
</template>
