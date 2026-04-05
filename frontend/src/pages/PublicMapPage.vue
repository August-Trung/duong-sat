<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Map as MapIcon,
  ShieldAlert,
  Navigation,
  MapPin,
  ChevronRight,
  AlertCircle,
  Layers,
  Maximize2,
  MousePointer2,
  X,
  Activity,
} from 'lucide-vue-next'
import MapPanel from '../components/MapPanel.vue'
import {
  clearPublicError,
  loadCrossingDetail,
  locateUser,
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
  formatDistance,
  haversineDistanceMeters,
  incidentsForCrossing,
  nearestCrossings,
  riskSummaryForCrossing,
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
  applyCrossingFilters(publicState.crossings, publicState.filters ?? {}, {
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
  <div class="map-page max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-1 lg:grid-cols-12 gap-8">
    <transition name="toast">
      <div v-if="toastMessage" class="fixed top-28 left-1/2 -translate-x-1/2 z-[2000] w-full max-w-md px-4">
        <div
          class="bg-danger-soft border border-danger/20 p-4 rounded-2xl shadow-2xl flex items-center gap-4 backdrop-blur-xl">
          <div class="w-10 h-10 rounded-xl bg-danger text-white flex items-center justify-center flex-shrink-0">
            <AlertCircle :size="20" />
          </div>
          <div class="flex-1">
            <strong class="block text-sm font-bold text-danger">Lỗi hệ thống</strong>
            <p class="text-xs text-danger/80">{{ toastMessage }}</p>
          </div>
          <button @click="dismissToast" class="p-2 hover:bg-danger/10 rounded-lg text-danger transition-colors">
            <X :size="18" />
          </button>
        </div>
      </div>
    </transition>

    <section class="lg:col-span-12">
      <div class="bg-white p-5 rounded-[32px] border border-line shadow-sm flex flex-col gap-4">
        <div class="flex flex-col xl:flex-row xl:items-center justify-between gap-4">
          <div class="flex flex-wrap items-center gap-4">
            <div class="flex items-center gap-1 bg-bg-strong p-1.5 rounded-2xl border border-line">
              <button
                @click="overlays.crossings = !overlays.crossings"
                class="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all"
                :class="overlays.crossings ? 'bg-white text-brand shadow-sm' : 'text-soft hover:text-text'"
              >
                <MapPin :size="16" />
                <span>Điểm giao</span>
              </button>
              <button
                @click="overlays.highRiskOnly = !overlays.highRiskOnly"
                class="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all"
                :class="overlays.highRiskOnly ? 'bg-white text-brand shadow-sm' : 'text-soft hover:text-text'"
              >
                <ShieldAlert :size="16" />
                <span>Rủi ro cao</span>
              </button>
              <button
                @click="overlays.warningZones = !overlays.warningZones"
                class="flex items-center gap-2 px-4 py-2.5 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all"
                :class="overlays.warningZones ? 'bg-white text-brand shadow-sm' : 'text-soft hover:text-text'"
              >
                <Layers :size="16" />
                <span>Vùng cảnh báo</span>
              </button>
            </div>

            <div class="flex items-center gap-3 px-5 py-2.5 bg-bg-strong/50 border border-line rounded-2xl">
              <span class="text-[10px] font-bold text-soft uppercase tracking-widest">Bán kính:</span>
              <select
                :value="publicState.areaAlert.radiusMeters"
                @change="setAreaAlertRadius($event.target.value)"
                class="bg-transparent outline-none text-xs font-black text-text cursor-pointer"
              >
                <option :value="800">800 m</option>
                <option :value="1500">1.5 km</option>
                <option :value="3000">3 km</option>
                <option :value="5000">5 km</option>
              </select>
            </div>
          </div>

          <div class="flex flex-wrap items-center gap-3">
            <button
              @click="locateAndUseArea"
              class="flex-1 sm:flex-none px-6 py-3 bg-brand text-white rounded-2xl font-bold text-xs shadow-lg shadow-brand/20 hover:bg-brand-dark transition-all flex items-center justify-center gap-2"
            >
              <Navigation :size="16" />
              Vị trí của tôi
            </button>
            <button
              @click="enableManualLocationPick"
              class="flex-1 sm:flex-none px-6 py-3 rounded-2xl font-bold text-xs transition-all flex items-center justify-center gap-2 border"
              :class="
                uiState.pickingLocation
                  ? 'bg-brand-soft text-brand border border-brand/20 shadow-lg shadow-brand/5'
                  : 'bg-bg-strong text-soft hover:bg-line border border-line'
              "
            >
              <MousePointer2 :size="16" />
              {{ uiState.pickingLocation ? 'Đang chọn...' : 'Chọn vị trí' }}
            </button>
            <button
              @click="useSelectedCrossingAsArea"
              :disabled="!publicState.selectedCrossing"
              class="flex-1 sm:flex-none px-6 py-3 bg-bg-strong text-soft rounded-2xl font-bold text-xs hover:bg-line border border-line disabled:opacity-30 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
            >
              <Maximize2 :size="16" />
              Dùng điểm chọn
            </button>
          </div>
        </div>

        <div class="w-full bg-bg-strong/40 p-1.5 rounded-2xl border border-line flex flex-wrap items-center gap-2">
          <button
            v-for="level in ['very_high', 'high', 'medium', 'low']"
            :key="level"
            @click="visibleLevels[level] = !visibleLevels[level]"
            class="flex-1 min-w-[120px] px-4 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition-all"
            :class="
              visibleLevels[level]
                ? 'bg-' + level + ' text-white shadow-md'
                : 'bg-white text-soft hover:bg-bg-strong'
            "
          >
            {{ riskLabel(level) }}
          </button>
        </div>
      </div>
    </section>

    <section class="lg:col-span-8">
      <div class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden relative h-[680px]">
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

        <div
          v-if="publicState.userLocation || uiState.pickingLocation"
          class="absolute bottom-6 z-[1000] max-w-[calc(100%-3rem)]"
          :class="publicState.selectedCrossing ? 'right-6 left-auto' : 'left-6 right-auto'"
        >
          <div
            class="px-4 py-2 bg-white/90 backdrop-blur-xl border border-line rounded-2xl shadow-xl text-[10px] font-black uppercase tracking-wider flex items-center gap-3"
          >
            <div class="w-2 h-2 rounded-full bg-brand animate-ping"></div>
            <span v-if="uiState.pickingLocation" class="text-brand">Chạm lên bản đồ để chọn tâm theo dõi</span>
            <span v-else class="text-text">
              Đang theo dõi: {{ describeUserLocation(publicState.userLocation) || 'Vị trí hiện tại' }}
            </span>
          </div>
        </div>
      </div>
    </section>

    <aside class="lg:col-span-4 space-y-8">
      <section class="space-y-4">
        <div class="flex items-center justify-between px-1">
          <h3 class="text-[10px] font-bold text-soft uppercase tracking-widest">Điểm đang chọn</h3>
          <div
            v-if="publicState.selectedCrossing"
            class="px-2 py-0.5 text-[9px] font-black rounded uppercase tracking-wider"
            :class="'badge-risk-' + publicState.selectedCrossing.risk_level"
          >
            {{ riskLabel(publicState.selectedCrossing.risk_level) }}
          </div>
        </div>

        <div
          v-if="publicState.selectedCrossing"
          class="bg-white p-6 rounded-[32px] border border-line shadow-sm relative overflow-hidden group transition-all hover:shadow-xl hover:shadow-black/5"
        >
          <div class="absolute top-0 left-0 w-1.5 h-full" :class="'bg-' + publicState.selectedCrossing.risk_level"></div>
          <h4 class="text-xl font-black text-text mb-1 group-hover:text-brand transition-colors">
            {{ publicState.selectedCrossing.name }}
          </h4>
          <p class="text-xs text-soft mb-6 flex items-center gap-1">
            <MapPin :size="12" />
            {{ publicState.selectedCrossing.address || 'Biên Hòa, Đồng Nai' }}
          </p>

          <div class="grid grid-cols-2 gap-3 mb-6">
            <div class="p-3 bg-bg-strong/50 rounded-2xl border border-line">
              <span class="text-[9px] font-bold text-soft uppercase tracking-widest block mb-1">Khoảng cách</span>
              <span class="text-xs font-black text-text">{{ distanceToCrossing(publicState.selectedCrossing) }}</span>
            </div>
            <div class="p-3 bg-bg-strong/50 rounded-2xl border border-line">
              <span class="text-[9px] font-bold text-soft uppercase tracking-widest block mb-1">Rào chắn</span>
              <span class="text-xs font-black text-text">{{ publicState.selectedCrossing.barrier_type || 'N/A' }}</span>
            </div>
          </div>

          <div class="p-4 bg-brand-soft rounded-2xl border border-brand/10 mb-8">
            <div class="flex items-center gap-2 mb-2 text-brand">
              <ShieldAlert :size="18" />
              <strong class="text-xs uppercase tracking-wider">{{ selectedRiskSummary.label }}</strong>
            </div>
            <p class="text-[11px] text-brand-strong leading-relaxed font-medium">{{ selectedRiskSummary.message }}</p>
          </div>

          <button
            @click="openCrossingDetail(publicState.selectedCrossing.id)"
            class="w-full py-4 bg-brand text-white rounded-2xl font-bold text-sm shadow-lg shadow-brand/20 hover:bg-brand-dark transition-all flex items-center justify-center gap-2"
          >
            Xem chi tiết đầy đủ
            <ChevronRight :size="18" />
          </button>
        </div>

        <div v-else class="bg-white p-10 rounded-[32px] border-2 border-dashed border-line text-center">
          <div class="w-16 h-16 rounded-full bg-bg-strong mx-auto mb-4 flex items-center justify-center text-soft/30">
            <MousePointer2 :size="32" />
          </div>
          <p class="text-xs text-soft font-bold leading-relaxed">
            Chọn một điểm trên bản đồ để xem thông tin chi tiết
          </p>
        </div>
      </section>

      <section class="space-y-4">
        <h3 class="text-[10px] font-bold text-soft uppercase tracking-widest px-1">Điểm lân cận</h3>
        <div class="space-y-3">
          <button
            v-for="item in nearest"
            :key="item.id"
            @click="loadCrossingDetail(item.id)"
            class="w-full bg-white p-4 rounded-2xl border border-line shadow-sm flex items-center justify-between hover:border-brand/20 hover:shadow-lg hover:shadow-black/5 transition-all text-left group"
          >
            <div class="flex items-center gap-4">
              <div
                class="w-10 h-10 rounded-xl bg-bg-strong text-soft group-hover:text-brand transition-colors flex items-center justify-center"
              >
                <MapPin :size="20" />
              </div>
              <div>
                <strong class="block text-sm font-bold text-text group-hover:text-brand transition-colors">
                  {{ item.name }}
                </strong>
                <span class="text-[10px] font-bold text-soft uppercase tracking-wider">
                  {{ formatDistance(item.distanceMeters) }}
                </span>
              </div>
            </div>
            <div class="w-2 h-2 rounded-full" :class="'bg-' + item.risk_level"></div>
          </button>
          <div
            v-if="!nearest.length"
            class="text-xs text-soft p-8 text-center italic bg-bg-strong/30 rounded-2xl border border-dashed border-line"
          >
            Bật vị trí để xem các điểm gần bạn
          </div>
        </div>
      </section>

      <section class="space-y-4">
        <div class="flex items-center justify-between px-1">
          <h3 class="text-[10px] font-bold text-soft uppercase tracking-widest">Giám sát vùng</h3>
          <span
            v-if="areaMatches.length"
            class="px-2 py-0.5 bg-brand-soft text-brand text-[9px] font-black rounded uppercase tracking-wider"
          >
            {{ areaMatches.length }} điểm
          </span>
        </div>

        <div class="bg-surface-dark rounded-[32px] p-6 text-white shadow-xl shadow-black/10 relative overflow-hidden">
          <div class="absolute top-0 right-0 w-32 h-32 bg-brand/10 rounded-full -mr-16 -mt-16 blur-2xl"></div>
          <div class="relative z-10">
            <div class="flex items-center gap-4 mb-6">
              <div class="w-10 h-10 rounded-xl bg-brand flex items-center justify-center shadow-lg shadow-brand/20">
                <Activity :size="20" />
              </div>
              <div>
                <strong class="block text-sm font-bold">Vùng quan tâm</strong>
                <span class="text-[10px] text-white/40 uppercase font-black tracking-widest">
                  {{ publicState.areaAlert.label || 'Chưa xác định' }}
                </span>
              </div>
            </div>

            <div v-if="areaIncidents.length" class="p-3 bg-danger/10 border border-danger/20 rounded-xl mb-6">
              <p class="text-[11px] font-bold text-danger flex items-center gap-2">
                <AlertCircle :size="14" />
                {{ areaIncidents.length }} sự cố trong vùng
              </p>
            </div>

            <div class="space-y-2 max-h-[240px] overflow-y-auto pr-2 custom-scrollbar">
              <button
                v-for="item in areaMatches.slice(0, 10)"
                :key="item.id"
                @click="loadCrossingDetail(item.id)"
                class="w-full flex items-center justify-between p-3 rounded-xl hover:bg-white/5 text-left transition-colors group"
              >
                <span class="text-xs font-medium text-white/80 group-hover:text-white truncate pr-4">
                  {{ item.name }}
                </span>
                <span
                  class="text-[9px] font-black px-2 py-1 rounded bg-white/10 text-white/60 group-hover:text-white transition-colors"
                >
                  {{ item.risk_score }} PTS
                </span>
              </button>
            </div>

            <div v-if="!areaMatches.length" class="text-xs text-white/30 text-center py-10 italic">
              Chưa có điểm nào trong vùng theo dõi
            </div>
          </div>
        </div>
      </section>
    </aside>
  </div>
</template>

<style scoped>
@reference "../styles.css";

.bg-very_high {
  background-color: var(--danger);
}

.bg-high {
  background-color: var(--warning);
}

.bg-medium {
  background-color: #f59e0b;
}

.bg-low {
  background-color: var(--success);
}

.badge-risk-very_high {
  @apply bg-danger text-white;
}

.badge-risk-high {
  @apply bg-warning text-white;
}

.badge-risk-medium {
  @apply bg-amber-500 text-white;
}

.badge-risk-low {
  @apply bg-success text-white;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: rgba(255, 255, 255, 0.05);
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.2);
  border-radius: 10px;
}

.toast-enter-active,
.toast-leave-active {
  transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.toast-enter-from {
  opacity: 0;
  transform: translate(-50%, -20px);
}

.toast-leave-to {
  opacity: 0;
  transform: translate(-50%, -20px);
}
</style>
