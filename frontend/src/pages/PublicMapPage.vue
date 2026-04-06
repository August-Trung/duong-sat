<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  ShieldAlert,
  Navigation,
  MapPin,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Search,
  Layers,
  Maximize2,
  MousePointer2,
  X,
} from 'lucide-vue-next'
import { toAssetUrl } from '../api'
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
  buildSearchSuggestions,
  describeUserLocation,
  formatDistance,
  haversineDistanceMeters,
  incidentsForCrossing,
  riskSummaryForCrossing,
  upcomingSchedulesForCrossing,
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
  showMapSearchResults: false,
})
const toastMessage = ref('')
const selectedPreviewIndex = ref(0)
const mapSearchQuery = ref('')

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

const selectedRecentIncidents = computed(() =>
  incidentsForCrossing(publicState.selectedCrossing, publicState.incidents, 60).slice(0, 5)
)
const selectedRiskSummary = computed(() =>
  riskSummaryForCrossing(publicState.selectedCrossing, publicState.incidents, publicState.schedules)
)
const selectedUpcomingTrain = computed(() =>
  upcomingSchedulesForCrossing(publicState.selectedCrossing, publicState.schedules, 1)[0] ?? null
)
const selectedArticlesCount = computed(() => publicState.selectedCrossing?.articles?.length ?? 0)
const selectedImages = computed(() => publicState.selectedCrossing?.images ?? [])
const selectedPreviewImage = computed(() => selectedImages.value[selectedPreviewIndex.value] ?? null)
const highlightedIds = computed(() => [])
const mapSearchSuggestions = computed(() =>
  buildSearchSuggestions(publicState.crossings, mapSearchQuery.value, 6)
)

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

function barrierLabel(value) {
  return {
    co_gac: 'Có người gác',
    tu_dong: 'Tự động',
    can_gat: 'Cần gạt',
    khong_co: 'Không có rào chắn',
  }[value] || value || 'N/A'
}

function formatShortAddress(crossing) {
  if (!crossing) return 'Biên Hòa, Đồng Nai'
  return (
    crossing.address ||
    [crossing.ward, crossing.district, crossing.city].filter(Boolean).join(', ') ||
    'Biên Hòa, Đồng Nai'
  )
}

function formatTrainTime(dateValue) {
  return new Intl.DateTimeFormat('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(dateValue)
}

function nextTrainPrimary() {
  if (!selectedUpcomingTrain.value?.nextPassAt) {
    return 'Chưa có dữ liệu'
  }

  const trainNo = selectedUpcomingTrain.value.train_no || 'Tàu'
  return `${trainNo} · ${formatTrainTime(selectedUpcomingTrain.value.nextPassAt)}`
}

function nextTrainSecondary() {
  if (!selectedUpcomingTrain.value?.nextPassAt) {
    return ''
  }

  const diffMinutes = Math.round((selectedUpcomingTrain.value.nextPassAt.getTime() - Date.now()) / 60000)
  if (diffMinutes <= 0) return '(Đang đi qua)'
  if (diffMinutes < 60) return `(${diffMinutes} phút nữa)`

  const hours = Math.floor(diffMinutes / 60)
  const minutes = diffMinutes % 60
  if (minutes === 0) return `(${hours} giờ nữa)`
  return `(${hours} giờ ${minutes} phút nữa)`
}

function distanceToCrossing(crossing) {
  return formatDistance(haversineDistanceMeters(distanceSource.value, crossing))
}

function selectPreviewImage(index) {
  selectedPreviewIndex.value = index
}

function showPreviousImage() {
  if (!selectedImages.value.length) return
  selectedPreviewIndex.value =
    (selectedPreviewIndex.value - 1 + selectedImages.value.length) % selectedImages.value.length
}

function showNextImage() {
  if (!selectedImages.value.length) return
  selectedPreviewIndex.value = (selectedPreviewIndex.value + 1) % selectedImages.value.length
}

function openMapSearchResults() {
  uiState.showMapSearchResults = true
}

function closeMapSearchResults() {
  window.setTimeout(() => {
    uiState.showMapSearchResults = false
  }, 120)
}

function selectMapSearchResult(crossing) {
  if (!crossing) return
  mapSearchQuery.value = crossing.code ? `${crossing.name} (${crossing.code})` : crossing.name || ''
  uiState.showMapSearchResults = false
  loadCrossingDetail(crossing.id)
}

function submitMapSearch() {
  selectMapSearchResult(mapSearchSuggestions.value[0] ?? null)
}

function clearMapSearch() {
  mapSearchQuery.value = ''
  uiState.showMapSearchResults = false
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

function openCrossingDetail(id) {
  router.push({ name: 'public-crossing-detail', params: { id } })
}

watch(
  () => publicState.error,
  (value) => {
    if (value) showToast(value)
  }
)

watch(
  () => publicState.selectedCrossingId,
  () => {
    selectedPreviewIndex.value = 0
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
          class="bg-danger-soft border border-danger/20 p-4 rounded-2xl shadow-2xl flex items-center gap-4 backdrop-blur-xl"
        >
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
        >
          <template #top-left>
            <div class="relative w-full">
              <form
                class="flex items-center gap-3 px-4 py-3 bg-white/95 backdrop-blur-xl border border-line rounded-2xl shadow-lg"
                @submit.prevent="submitMapSearch"
              >
                <Search :size="18" class="text-soft flex-shrink-0" />
                <input
                  v-model="mapSearchQuery"
                  type="text"
                  placeholder="Tìm theo tên hoặc mã điểm giao"
                  class="flex-1 bg-transparent outline-none text-sm font-medium text-text placeholder:text-soft/80"
                  @focus="openMapSearchResults"
                  @blur="closeMapSearchResults"
                />
                <button
                  v-if="mapSearchQuery"
                  type="button"
                  class="text-soft hover:text-text transition-colors"
                  @click="clearMapSearch"
                >
                  <X :size="16" />
                </button>
              </form>

              <div
                v-if="uiState.showMapSearchResults && mapSearchQuery.trim()"
                class="mt-2 bg-white/95 backdrop-blur-xl border border-line rounded-2xl shadow-2xl overflow-hidden"
              >
                <button
                  v-for="crossing in mapSearchSuggestions"
                  :key="crossing.id"
                  type="button"
                  class="w-full px-4 py-3 text-left hover:bg-bg-strong/70 transition-colors border-b border-line last:border-b-0"
                  @mousedown.prevent="selectMapSearchResult(crossing)"
                >
                  <strong class="block text-sm font-bold text-text">{{ crossing.name }}</strong>
                  <span class="text-[10px] font-bold text-soft uppercase tracking-wider">
                    {{ crossing.code || 'Không có mã' }}
                  </span>
                </button>

                <div
                  v-if="!mapSearchSuggestions.length"
                  class="px-4 py-4 text-xs font-medium text-soft"
                >
                  Không tìm thấy điểm phù hợp
                </div>
              </div>
            </div>
          </template>
        </MapPanel>

        <div
          v-if="publicState.userLocation || uiState.pickingLocation"
          class="absolute bottom-6 left-6 z-[1000] max-w-[calc(100%-3rem)]"
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
        </div>

        <div
          v-if="publicState.selectedCrossing"
          class="bg-white p-5 rounded-[16px] border border-line shadow-sm relative overflow-hidden group transition-all hover:shadow-xl hover:shadow-black/5"
        >
          <div class="absolute top-0 left-0 w-1.5 h-full" :class="'bg-' + publicState.selectedCrossing.risk_level"></div>

          <div class="flex items-start justify-between gap-3 mb-4">
            <div class="min-w-0">
              <h4 class="text-[1.35rem] leading-tight font-black text-text mb-1 group-hover:text-brand transition-colors line-clamp-2">
                {{ publicState.selectedCrossing.name }}
              </h4>
              <p class="text-[11px] text-soft flex items-start gap-1 line-clamp-2">
                <MapPin :size="12" />
                {{ formatShortAddress(publicState.selectedCrossing) }}
              </p>
            </div>
            <div
              class="px-2.5 py-1 text-[9px] font-black rounded-xl uppercase tracking-wider whitespace-nowrap shrink-0"
              :class="'badge-risk-' + publicState.selectedCrossing.risk_level"
            >
              {{ riskLabel(publicState.selectedCrossing.risk_level) }}
            </div>
          </div>

          <div class="grid grid-cols-3 gap-2.5 mb-4">
            <div class="p-2.5 bg-bg-strong/50 rounded-[10px] border border-line min-h-[82px]">
              <span class="text-[8px] font-bold text-soft uppercase tracking-widest block mb-1">Khoảng cách</span>
              <span class="text-xs font-black text-text">{{ distanceToCrossing(publicState.selectedCrossing) }}</span>
            </div>
            <div class="p-2.5 bg-bg-strong/50 rounded-[10px] border border-line min-h-[82px]">
              <span class="text-[8px] font-bold text-soft uppercase tracking-widest block mb-1">Rào chắn</span>
              <span class="text-xs font-black text-text">{{ barrierLabel(publicState.selectedCrossing.barrier_type) }}</span>
            </div>
            <div class="p-2.5 bg-bg-strong/50 rounded-[10px] border border-line min-h-[82px]">
              <span class="text-[8px] font-bold text-soft uppercase tracking-widest block mb-1">Tàu sắp tới</span>
              <span class="text-xs font-black text-text block">{{ nextTrainPrimary() }}</span>
              <span v-if="nextTrainSecondary()" class="text-[10px] font-semibold text-soft">
                {{ nextTrainSecondary() }}
              </span>
            </div>
          </div>

          <div class="p-3 bg-brand-soft rounded-[10px] border border-brand/10 mb-4">
            <div class="flex items-center gap-2 mb-1.5 text-brand">
              <ShieldAlert :size="16" />
              <strong class="text-xs uppercase tracking-wider">{{ selectedRiskSummary.label }}</strong>
            </div>
            <p class="text-[10px] text-brand-strong leading-relaxed font-medium line-clamp-2">
              {{ selectedRiskSummary.reasons[0] || selectedRiskSummary.message }}
            </p>
          </div>

          <div class="flex items-center gap-2.5 mb-4">
            <div class="flex-1 px-3 py-2.5 bg-bg-strong/50 rounded-[10px] border border-line">
              <span class="text-[8px] font-bold text-soft uppercase tracking-wider block mb-1">Sự cố</span>
              <div class="flex items-baseline gap-2">
                <span class="text-lg font-black text-text">{{ selectedRecentIncidents.length }}</span>
                <span class="text-[10px] font-semibold text-soft">trong 60 ngày</span>
              </div>
            </div>
            <div class="flex-1 px-3 py-2.5 bg-bg-strong/50 rounded-[10px] border border-line">
              <span class="text-[8px] font-bold text-soft uppercase tracking-wider block mb-1">Bài tin</span>
              <div class="flex items-baseline gap-2">
                <span class="text-lg font-black text-text">{{ selectedArticlesCount }}</span>
                <span class="text-[10px] font-semibold text-soft">bài liên quan</span>
              </div>
            </div>
          </div>

          <div v-if="selectedPreviewImage" class="mb-4">
            <div class="relative w-full rounded-[12px] overflow-hidden border border-line bg-bg-strong">
              <img
                :src="toAssetUrl(selectedPreviewImage.url)"
                :alt="selectedPreviewImage.caption || publicState.selectedCrossing.name"
                class="w-full h-36 object-cover"
                referrerpolicy="no-referrer"
              />

              <template v-if="selectedImages.length > 1">
                <button
                  type="button"
                  @click="showPreviousImage"
                  class="absolute left-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 backdrop-blur text-text shadow-lg flex items-center justify-center hover:bg-white transition-colors"
                >
                  <ChevronLeft :size="18" />
                </button>
                <button
                  type="button"
                  @click="showNextImage"
                  class="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-white/90 backdrop-blur text-text shadow-lg flex items-center justify-center hover:bg-white transition-colors"
                >
                  <ChevronRight :size="18" />
                </button>
                <div class="absolute bottom-3 left-1/2 -translate-x-1/2 px-3 py-1 bg-black/45 text-white rounded-full text-[10px] font-black tracking-wide">
                  {{ selectedPreviewIndex + 1 }}/{{ selectedImages.length }}
                </div>
              </template>
            </div>

            <div v-if="selectedImages.length > 1" class="flex items-center justify-center gap-2 mt-3">
              <button
                v-for="(image, index) in selectedImages"
                :key="image.id || image.url"
                type="button"
                @click="selectPreviewImage(index)"
                class="h-2.5 rounded-full transition-all"
                :class="selectedPreviewIndex === index ? 'w-6 bg-brand' : 'w-2.5 bg-line hover:bg-soft/40'"
                :aria-label="`Xem ảnh ${index + 1}`"
              />
            </div>
          </div>

          <button
            @click="openCrossingDetail(publicState.selectedCrossing.id)"
            class="w-full py-3.5 bg-brand text-white rounded-[10px] font-bold text-sm shadow-lg shadow-brand/20 hover:bg-brand-dark transition-all flex items-center justify-center gap-2"
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
