<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import {
  ArrowLeft, MapPin, Shield, AlertTriangle,
  Clock, Train, Info, Phone, User,
  Navigation, Camera,
  FileText, ShieldAlert, CheckCircle2,
  ChevronRight, Calendar, Share2, Loader2,
  Activity, TrendingUp, AlertCircle
} from 'lucide-vue-next'
import { Motion } from '@motionone/vue'
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
const forecast60 = computed(() =>
  forecastWindowForCrossing(crossing.value, publicState.schedules, 60)
)
const forecast120 = computed(() =>
  forecastWindowForCrossing(crossing.value, publicState.schedules, 120)
)
const recentIncidents = computed(() =>
  incidentsForCrossing(crossing.value, publicState.incidents, 120).slice(0, 6)
)
const upcomingSchedules = computed(() =>
  upcomingSchedulesForCrossing(crossing.value, publicState.schedules, 10)
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
const forecastDensity = computed(() => [
  { label: '30 phút', value: forecast.value.count, tone: 'bg-brand-soft text-brand' },
  { label: '60 phút', value: forecast60.value.count, tone: 'bg-warning-soft text-warning' },
  { label: '120 phút', value: forecast120.value.count, tone: 'bg-danger-soft text-danger' },
])
const sourceFacts = computed(() => {
  if (!crossing.value) return []
  return [
    { label: 'Nguồn tọa độ', value: crossing.value.coordinate_source || 'Đang cập nhật' },
    { label: 'Khảo sát gần nhất', value: crossing.value.surveyed_at || 'Chưa có' },
    { label: 'Xác minh cuối', value: crossing.value.verified_at || 'Chưa xác minh' },
    { label: 'Mã tham chiếu', value: crossing.value.source_reference || 'Không có', mono: true },
  ]
})
const contactCards = computed(() => {
  if (!crossing.value) return []
  return [
    {
      label: 'Người phụ trách',
      value: crossing.value.manager_name || 'Đang cập nhật',
      icon: User,
    },
    {
      label: 'Số điện thoại',
      value: crossing.value.manager_phone || 'Đang cập nhật',
      icon: Phone,
      href: crossing.value.manager_phone ? `tel:${crossing.value.manager_phone}` : '',
    },
  ]
})

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

function hasOpenableUrl(value) {
  return /^https?:\/\//i.test(String(value || ''))
}

function articleUrl(article) {
  return article?.external_url || article?.url || ''
}

function hasUsefulArticleImage(article) {
  const value = String(article?.image_url || '').trim()
  return /^https?:\/\//i.test(value)
}

function articleSnippet(article) {
  const text = String(article?.summary || '').replace(/\s+/g, ' ').trim()
  if (!text) return 'Chưa có đoạn trích ngắn cho bài viết này.'
  return text.length > 140 ? `${text.slice(0, 140).trim()}...` : text
}

function incidentSeverityLabel(value) {
  return {
    very_high: 'Rất nghiêm trọng',
    high: 'Nghiêm trọng',
    medium: 'Cảnh báo',
    low: 'Theo dõi',
  }[value] || 'Theo dõi'
}

function incidentSeverityClass(value) {
  return {
    very_high: 'bg-danger text-white',
    high: 'bg-danger/15 text-danger',
    medium: 'bg-warning-soft text-warning',
    low: 'bg-brand-soft text-brand',
  }[value] || 'bg-bg-strong text-soft'
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
  <div class="crossing-detail-page bg-bg min-h-screen pb-24 md:pb-12">
    <!-- Hero Header -->
    <div class="bg-white border-b border-line sticky top-[var(--header-height)] z-30 shadow-sm">
      <div class="max-w-7xl mx-auto px-6 py-8">
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div class="flex items-start gap-6">
            <RouterLink to="/"
              class="mt-1 w-12 h-12 flex items-center justify-center bg-bg-strong hover:bg-brand hover:text-white rounded-2xl text-soft transition-all shadow-sm">
              <ArrowLeft :size="24" />
            </RouterLink>
            <div>
              <div class="flex items-center gap-3 mb-2">
                <span
                  class="px-3 py-1 bg-brand-soft text-brand text-[10px] font-black rounded-lg uppercase tracking-wider">Chi
                  tiết điểm giao cắt</span>
                <span v-if="crossing?.code"
                  class="text-soft text-xs font-black font-mono tracking-widest bg-bg-strong px-2 py-0.5 rounded-md">#{{
                    crossing.code }}</span>
              </div>
              <h1 class="text-4xl font-black text-text mb-2 tracking-tight">{{ crossing?.name || 'Đang tải...' }}</h1>
              <div class="flex flex-wrap items-center gap-6 text-soft text-sm font-bold">
                <span class="flex items-center gap-2">
                  <MapPin :size="16" class="text-brand" /> {{ crossing?.address || 'Biên Hòa, Đồng Nai' }}
                </span>
                <span v-if="publicState.userLocation" class="flex items-center gap-2 text-brand">
                  <Navigation :size="16" /> Cách đây {{ distanceToCrossing }}
                </span>
              </div>
            </div>
          </div>

          <div class="flex flex-wrap gap-3">
            <button @click="useLiveLocation"
              class="flex items-center gap-3 px-6 py-3 bg-brand text-white rounded-2xl font-black text-sm hover:bg-brand-dark transition-all disabled:opacity-50 shadow-lg shadow-brand/20"
              :disabled="publicState.locating">
              <Navigation :size="18" :class="{ 'animate-pulse': publicState.locating }" />
              {{ publicState.locating ? 'Đang định vị...' : 'Cập nhật vị trí' }}
            </button>
            <button
              class="w-12 h-12 flex items-center justify-center bg-bg-strong text-soft hover:text-brand rounded-2xl transition-all border border-line">
              <Share2 :size="20" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="max-w-7xl mx-auto px-6 py-10">
      <div v-if="publicState.detailLoading" class="flex flex-col items-center justify-center py-32">
        <div class="relative w-20 h-20 mb-6">
          <div class="absolute inset-0 rounded-3xl bg-brand/10 animate-ping"></div>
          <div
            class="relative w-20 h-20 rounded-3xl bg-brand text-white flex items-center justify-center shadow-xl shadow-brand/20">
            <Loader2 class="animate-spin" :size="40" />
          </div>
        </div>
        <p class="text-text font-black uppercase tracking-widest text-sm">Đang tải dữ liệu hiện trường...</p>
      </div>

      <div v-else-if="crossing" class="grid grid-cols-1 lg:grid-cols-12 gap-10">
        <!-- Main Content (Left) -->
        <div class="lg:col-span-8 space-y-10">
          <!-- Risk Banner -->
          <Motion :initial="{ opacity: 0, y: 20 }" :animate="{ opacity: 1, y: 0 }"
            class="p-10 rounded-[40px] border flex flex-col md:flex-row items-center gap-10 shadow-2xl shadow-black/5 relative overflow-hidden"
            :class="{
              'bg-danger-soft border-danger/20': crossing.risk_level === 'very_high',
              'bg-warning-soft border-warning/20': crossing.risk_level === 'high' || crossing.risk_level === 'medium',
              'bg-brand-soft border-brand/20': !['very_high', 'high', 'medium'].includes(crossing.risk_level)
            }">
            <div class="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -mr-32 -mt-32 blur-3xl"></div>

            <div class="w-24 h-24 rounded-[32px] flex items-center justify-center shrink-0 shadow-xl" :class="{
              'bg-danger text-white shadow-danger/20': crossing.risk_level === 'very_high',
              'bg-warning text-white shadow-warning/20': crossing.risk_level === 'high' || crossing.risk_level === 'medium',
              'bg-brand text-white shadow-brand/20': !['very_high', 'high', 'medium'].includes(crossing.risk_level)
            }">
              <ShieldAlert v-if="crossing.risk_level === 'very_high'" :size="48" />
              <AlertTriangle v-else-if="crossing.risk_level === 'high' || crossing.risk_level === 'medium'"
                :size="48" />
              <CheckCircle2 v-else :size="48" />
            </div>

            <div class="flex-1 text-center md:text-left relative z-10">
              <h3 class="text-2xl font-black mb-3 tracking-tight"
                :class="crossing.risk_level === 'very_high' ? 'text-danger' : 'text-text'">
                {{ riskSummary.label }}
              </h3>
              <p class="text-[13px] font-bold text-text/70 leading-relaxed max-w-lg">{{ riskSummary.message }}</p>
              <div class="flex flex-wrap gap-2 mt-6 justify-center md:justify-start">
                <span v-for="reason in riskSummary.reasons" :key="reason"
                  class="px-4 py-1.5 bg-white/60 backdrop-blur-md rounded-xl text-[10px] font-black uppercase tracking-wider text-text/60 border border-white/40">
                  {{ reason }}
                </span>
              </div>
            </div>

            <div
              class="shrink-0 text-center px-8 py-6 bg-white/60 backdrop-blur-md rounded-[32px] border border-white/60 shadow-sm relative z-10">
              <p class="text-[10px] font-black text-soft uppercase tracking-widest mb-1">Risk Score</p>
              <p class="text-4xl font-black text-text tracking-tighter">{{ crossing.risk_score }}</p>
            </div>
          </Motion>

          <!-- Quick Stats Grid -->
          <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div v-for="(stat, idx) in [
              { label: 'Rào chắn', value: barrierLabel(crossing.barrier_type), icon: Shield },
              { label: 'Hồ sơ', value: verificationLabel(crossing.verification_status), icon: FileText },
              { label: 'Tọa độ', value: `${formatCoordinate(crossing.latitude)}, ${formatCoordinate(crossing.longitude)}`, icon: MapPin, mono: true },
              { label: 'Quản lý', value: crossing.manager_name || 'N/A', icon: User }
            ]" :key="idx"
              class="bg-white p-6 rounded-3xl border border-line shadow-sm hover:shadow-xl hover:shadow-black/5 transition-all group">
              <div
                class="w-8 h-8 rounded-lg bg-bg-strong text-soft group-hover:bg-brand-soft group-hover:text-brand transition-all flex items-center justify-center mb-4">
                <component :is="stat.icon" :size="16" />
              </div>
              <p class="text-[10px] font-bold text-soft uppercase tracking-widest mb-1">{{ stat.label }}</p>
              <p class="font-black text-text truncate" :class="{ 'font-mono text-[10px] tracking-tighter': stat.mono }">
                {{ stat.value }}</p>
            </div>
          </div>

          <!-- Forecast Section -->
          <div class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden">
            <div class="p-8 border-b border-line flex items-center justify-between bg-bg-strong/30">
              <div class="flex items-center gap-4">
                <div
                  class="w-12 h-12 rounded-2xl bg-brand text-white flex items-center justify-center shadow-lg shadow-brand/20">
                  <Clock :size="24" />
                </div>
                <div>
                  <h3 class="font-black text-text text-lg tracking-tight">Dự báo lịch tàu</h3>
                  <p class="text-[10px] font-bold text-soft uppercase tracking-widest">30 phút tới</p>
                </div>
              </div>
              <div class="text-right">
                <p class="text-[10px] font-bold text-soft uppercase tracking-widest mb-1">Chuyến tiếp theo</p>
                <p class="text-sm font-black text-brand tracking-tight">{{ forecast.nextPassAt ?
                  formatWhen(forecast.nextPassAt) : 'N/A' }}</p>
              </div>
            </div>
            <div class="p-8">
              <div class="grid grid-cols-3 gap-3 mb-6">
                <div v-for="bucket in forecastDensity" :key="bucket.label"
                  class="rounded-3xl p-4 border border-line bg-white shadow-sm">
                  <p class="text-[10px] font-black text-soft uppercase tracking-widest mb-2">{{ bucket.label }}</p>
                  <div class="flex items-center justify-between gap-3">
                    <p class="text-2xl font-black text-text tracking-tight">{{ bucket.value }}</p>
                    <span class="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest"
                      :class="bucket.tone">chuyến</span>
                  </div>
                </div>
              </div>
              <div v-if="upcomingSchedules.length" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div v-for="schedule in upcomingSchedules.slice(0, 6)" :key="`${schedule.id}-${schedule.pass_time}`"
                    class="p-5 bg-bg-strong rounded-3xl border border-transparent hover:border-brand/20 hover:bg-white hover:shadow-xl hover:shadow-black/5 transition-all flex items-center gap-5 group">
                    <div
                      class="w-14 h-14 rounded-2xl bg-white flex flex-col items-center justify-center shadow-sm group-hover:shadow-brand/10 transition-all">
                      <Train :size="24" class="text-brand mb-1" />
                      <span class="text-[9px] font-black text-soft tracking-tighter">{{ schedule.train_no }}</span>
                    </div>
                    <div class="min-w-0">
                      <p class="text-lg font-black text-text tracking-tight">{{ schedule.pass_time }}</p>
                      <p class="text-[11px] text-soft font-bold uppercase tracking-wider">{{ schedule.direction }} · {{
                        schedule.station_name }}</p>
                      <p class="text-[11px] text-text/60 font-semibold mt-1">Dự kiến qua {{ formatWhen(schedule.nextPassAt)
                      }}</p>
                    </div>
                  </div>
                </div>
                <div class="rounded-[32px] border border-line bg-bg-strong/40 p-5">
                  <div class="flex items-center gap-3 mb-4">
                    <Activity :size="18" class="text-brand" />
                    <p class="text-[11px] font-black text-soft uppercase tracking-widest">Chuỗi dự báo kế tiếp</p>
                  </div>
                  <div class="space-y-3">
                    <div v-for="schedule in upcomingSchedules.slice(0, 10)" :key="`timeline-${schedule.id}-${schedule.pass_time}`"
                      class="flex items-center justify-between gap-4 text-sm">
                      <div class="min-w-0">
                        <p class="font-black text-text truncate">{{ schedule.train_no }} · {{ schedule.direction }}</p>
                        <p class="text-soft text-[11px] font-semibold">{{ schedule.station_name }}</p>
                      </div>
                      <p class="text-brand font-black whitespace-nowrap">{{ schedule.pass_time }}</p>
                    </div>
                  </div>
                </div>
              </div>
              <div v-else class="flex flex-col items-center justify-center py-16 text-center">
                <div class="w-16 h-16 rounded-full bg-bg-strong flex items-center justify-center mb-4 text-soft/30">
                  <Clock :size="32" />
                </div>
                <p class="text-soft text-xs font-bold uppercase tracking-widest">Không có chuyến tàu nào trong 30 phút
                  tới.</p>
              </div>
            </div>
          </div>

          <!-- Photos Section -->
          <div class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden">
            <div class="p-8 border-b border-line flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-2xl bg-brand-soft text-brand flex items-center justify-center">
                  <Camera :size="24" />
                </div>
                <h3 class="font-black text-text text-lg tracking-tight">Ảnh hiện trường</h3>
              </div>
              <span
                class="px-3 py-1 bg-bg-strong rounded-full text-[10px] font-black text-soft uppercase tracking-wider">{{
                  crossing.images?.length || 0 }} ảnh</span>
            </div>
            <div class="p-8">
              <div v-if="crossing.images?.length" class="grid grid-cols-2 md:grid-cols-3 gap-6">
                <div v-for="image in crossing.images" :key="image.id"
                  class="group relative aspect-[4/3] rounded-3xl overflow-hidden bg-bg-strong cursor-pointer shadow-sm hover:shadow-2xl transition-all">
                  <img :src="toAssetUrl(image.url)" :alt="image.caption || image.original_name"
                    class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                    referrerpolicy="no-referrer" />
                  <div
                    class="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-6">
                    <p class="text-white text-[10px] font-black uppercase tracking-widest">{{ image.is_cover ? 'Ảnh đại diện' : 'Ảnh hiện trường' }}</p>
                    <p v-if="image.caption" class="text-white/80 text-[11px] font-semibold mt-2 leading-relaxed">
                      {{ image.caption }}
                    </p>
                  </div>
                </div>
              </div>
              <div v-else
                class="flex flex-col items-center justify-center py-20 text-center bg-bg-strong/30 rounded-[32px] border-2 border-dashed border-line">
                <Camera :size="48" class="text-soft/20 mb-4" />
                <p class="text-soft text-xs font-bold uppercase tracking-widest">Chưa có ảnh hiện trường cho điểm này.
                </p>
              </div>
            </div>
          </div>

          <!-- Incident Timeline -->
          <div v-if="recentIncidents.length" class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden">
            <div class="p-8 border-b border-line flex items-center justify-between bg-bg-strong/30">
              <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-2xl bg-danger-soft text-danger flex items-center justify-center">
                  <AlertTriangle :size="24" />
                </div>
                <div>
                  <h3 class="font-black text-text text-lg tracking-tight">Sự cố và ghi nhận gần đây</h3>
                  <p class="text-[10px] font-bold text-soft uppercase tracking-widest">120 ngày gần nhất</p>
                </div>
              </div>
              <span class="px-3 py-1 bg-white rounded-full text-[10px] font-black text-soft uppercase tracking-wider">
                {{ recentIncidents.length }} bản ghi
              </span>
            </div>
            <div class="p-8 space-y-4">
              <div v-for="incident in recentIncidents" :key="incident.id"
                class="rounded-[32px] border border-line p-5 bg-bg-strong/40">
                <div class="flex flex-wrap items-center gap-3 mb-3">
                  <span class="px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest"
                    :class="incidentSeverityClass(incident.severity_level)">
                    {{ incidentSeverityLabel(incident.severity_level) }}
                  </span>
                  <span class="text-[11px] font-bold text-soft uppercase tracking-widest">
                    {{ formatWhen(incident.incident_date) }}
                  </span>
                </div>
                <h4 class="text-base font-black text-text tracking-tight mb-2">{{ incident.title }}</h4>
                <p class="text-[13px] text-soft leading-relaxed font-medium">
                  {{ incident.description || 'Chưa có mô tả chi tiết cho bản ghi này.' }}
                </p>
              </div>
            </div>
          </div>

          <!-- Articles Section -->
          <div v-if="crossing.articles?.length" class="space-y-6">
            <div class="flex items-center gap-4 px-2">
              <div class="w-12 h-12 rounded-2xl bg-brand-soft text-brand flex items-center justify-center">
                <FileText :size="24" />
              </div>
              <h3 class="font-black text-text text-2xl tracking-tight">Tin tức liên quan</h3>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
              <a v-for="article in crossing.articles" :key="article.url"
                :href="hasOpenableUrl(articleUrl(article)) ? articleUrl(article) : undefined" target="_blank"
                class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden hover:shadow-2xl hover:shadow-black/5 transition-all group flex flex-col">
                <div v-if="hasUsefulArticleImage(article)" class="aspect-video overflow-hidden bg-bg-strong relative">
                  <img :src="toAssetUrl(article.image_url)" :alt="article.title"
                    class="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                    referrerpolicy="no-referrer" />
                  <div class="absolute top-4 left-4">
                    <span
                      class="px-3 py-1 bg-white/90 backdrop-blur-md text-text text-[9px] font-black rounded-lg uppercase tracking-widest shadow-sm">{{
                        article.publisher || 'Tin tức' }}</span>
                  </div>
                </div>
                <div class="p-8 flex-1 flex flex-col">
                  <div class="flex items-center gap-2 mb-4 text-soft text-[10px] font-bold uppercase tracking-widest">
                    <Calendar :size="12" />
                    <span v-if="article.published_at">{{ formatWhen(article.published_at) }}</span>
                  </div>
                  <h4
                    class="text-lg font-black text-text mb-4 group-hover:text-brand transition-colors line-clamp-2 tracking-tight">
                    {{ article.title }}</h4>
                  <p class="text-soft text-[13px] line-clamp-3 leading-relaxed font-medium mb-6">{{
                    articleSnippet(article) }}</p>
                  <div
                    class="mt-auto pt-4 flex items-center gap-2 text-brand text-[10px] font-black uppercase tracking-widest group-hover:gap-3 transition-all">
                    Đọc bài viết
                    <ChevronRight :size="14" />
                  </div>
                </div>
              </a>
            </div>
          </div>
        </div>

        <!-- Sidebar (Right) -->
        <div class="lg:col-span-4 space-y-8">
          <!-- Safety Guidance -->
          <div
            class="bg-surface-dark rounded-[40px] p-10 text-white shadow-2xl shadow-black/20 relative overflow-hidden">
            <div class="absolute top-0 right-0 w-48 h-48 bg-brand/10 rounded-full -mr-24 -mt-24 blur-3xl"></div>

            <div class="relative z-10">
              <div class="flex items-center gap-4 mb-8">
                <div
                  class="w-12 h-12 rounded-2xl bg-brand text-white flex items-center justify-center shadow-lg shadow-brand/20">
                  <Shield :size="24" />
                </div>
                <h3 class="font-black text-lg tracking-tight">Hướng dẫn an toàn</h3>
              </div>
              <div class="space-y-4">
                <div v-for="note in safetyNotes" :key="note"
                  class="flex items-start gap-4 p-5 bg-white/5 rounded-3xl border border-white/10 group hover:bg-white/10 transition-colors">
                  <div class="mt-1.5 w-2 h-2 rounded-full bg-brand shrink-0 shadow-lg shadow-brand/50"></div>
                  <p
                    class="text-[13px] font-bold leading-relaxed text-white/80 group-hover:text-white transition-colors">
                    {{ note }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Route Guidance -->
          <div class="bg-white rounded-[40px] p-10 border border-line shadow-sm">
            <div class="flex items-center gap-4 mb-8">
              <div class="w-12 h-12 rounded-2xl bg-brand-soft text-brand flex items-center justify-center">
                <Navigation :size="24" />
              </div>
              <h3 class="font-black text-text text-lg tracking-tight">Lộ trình tiếp cận</h3>
            </div>
            <div class="space-y-4">
              <div v-if="!publicState.userLocation"
                class="p-8 bg-bg-strong rounded-[32px] text-center border border-line">
                <p class="text-soft text-xs font-bold leading-relaxed mb-6">Bật vị trí để nhận gợi ý lộ trình tránh các
                  điểm rủi ro cao.</p>
                <button @click="useLiveLocation"
                  class="text-[10px] font-black text-brand uppercase tracking-widest hover:underline">Kích hoạt định
                  vị</button>
              </div>
              <div v-else v-for="note in routeNotes" :key="note"
                class="flex items-start gap-4 p-5 bg-bg-strong rounded-3xl border border-transparent hover:border-line transition-all">
                <div class="mt-1.5 w-2 h-2 rounded-full bg-brand shrink-0"></div>
                <p class="text-[13px] font-bold text-text leading-relaxed">{{ note }}</p>
              </div>
            </div>
          </div>

          <!-- Contact Info -->
          <div class="bg-white rounded-[40px] p-10 border border-line shadow-sm">
            <h3 class="font-black text-text text-lg tracking-tight mb-8">Thông tin liên hệ</h3>
            <div class="space-y-8">
              <div v-for="card in contactCards" :key="card.label" class="flex items-center gap-5">
                <div class="w-12 h-12 rounded-2xl bg-bg-strong flex items-center justify-center text-soft">
                  <component :is="card.icon" :size="24" />
                </div>
                <div class="min-w-0">
                  <p class="text-[10px] font-black text-soft uppercase tracking-widest mb-0.5">{{ card.label }}</p>
                  <a v-if="card.href" :href="card.href" class="text-sm font-black text-brand hover:underline">
                    {{ card.value }}
                  </a>
                  <p v-else class="text-sm font-black text-text">{{ card.value }}</p>
                </div>
              </div>
              <div class="grid grid-cols-3 gap-3">
                <a href="tel:113"
                  class="rounded-2xl bg-bg-strong border border-line px-4 py-3 text-center text-[10px] font-black uppercase tracking-widest text-text hover:border-brand hover:text-brand transition-all">
                  113
                </a>
                <a href="tel:114"
                  class="rounded-2xl bg-bg-strong border border-line px-4 py-3 text-center text-[10px] font-black uppercase tracking-widest text-text hover:border-brand hover:text-brand transition-all">
                  114
                </a>
                <a href="tel:115"
                  class="rounded-2xl bg-bg-strong border border-line px-4 py-3 text-center text-[10px] font-black uppercase tracking-widest text-text hover:border-brand hover:text-brand transition-all">
                  115
                </a>
              </div>
              <div v-if="crossing.notes" class="pt-6 border-t border-line">
                <p class="text-[10px] font-black text-soft uppercase tracking-widest mb-3">Ghi chú hiện trường</p>
                <div class="p-4 bg-bg-strong rounded-2xl">
                  <p class="text-[11px] text-soft leading-relaxed font-medium">{{ crossing.notes }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Data Provenance -->
          <div class="bg-white rounded-[40px] p-10 border border-line shadow-sm">
            <div class="flex items-center gap-4 mb-8">
              <div class="w-12 h-12 rounded-2xl bg-brand-soft text-brand flex items-center justify-center">
                <Info :size="24" />
              </div>
              <div>
                <h3 class="font-black text-text text-lg tracking-tight">Nguồn dữ liệu</h3>
                <p class="text-[10px] font-black text-soft uppercase tracking-widest">Xuất xứ và xác minh hồ sơ</p>
              </div>
            </div>
            <div class="space-y-4">
              <div v-for="fact in sourceFacts" :key="fact.label"
                class="rounded-3xl border border-line bg-bg-strong/40 p-4">
                <p class="text-[10px] font-black text-soft uppercase tracking-widest mb-2">{{ fact.label }}</p>
                <p class="text-sm font-black text-text break-all"
                  :class="{ 'font-mono text-[11px] tracking-tight': fact.mono }">
                  {{ fact.value }}
                </p>
              </div>
              <div v-if="crossing.verification_notes" class="rounded-3xl border border-warning/20 bg-warning-soft/50 p-4">
                <div class="flex items-center gap-3 mb-3">
                  <TrendingUp :size="16" class="text-warning" />
                  <p class="text-[10px] font-black text-warning uppercase tracking-widest">Lưu ý xác minh</p>
                </div>
                <p class="text-[12px] text-text/70 leading-relaxed font-semibold">{{ crossing.verification_notes }}</p>
              </div>
            </div>
          </div>

          <!-- Quality Alerts (Sidebar) -->
          <div v-if="qualityAlerts.length" class="bg-danger-soft/30 rounded-[40px] p-10 border border-danger/10">
            <div class="flex items-center gap-4 mb-6">
              <div
                class="w-10 h-10 rounded-xl bg-danger text-white flex items-center justify-center shadow-lg shadow-danger/20">
                <AlertCircle :size="20" />
              </div>
              <h3 class="font-black text-danger text-lg tracking-tight">Cảnh báo dữ liệu</h3>
            </div>
            <div class="space-y-3">
              <p v-for="alert in qualityAlerts" :key="alert"
                class="text-[11px] font-black text-danger/80 flex items-center gap-3 bg-white/40 p-3 rounded-xl border border-danger/5">
                <span class="w-1.5 h-1.5 bg-danger rounded-full shrink-0"></span>
                {{ alert }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="flex flex-col items-center justify-center py-32 text-center">
        <div class="w-24 h-24 rounded-[40px] bg-bg-strong flex items-center justify-center mb-8 text-soft/20">
          <MapPin :size="48" />
        </div>
        <h3 class="text-2xl font-black text-text mb-3 tracking-tight">Không tìm thấy điểm giao cắt</h3>
        <p class="text-soft text-sm font-bold mb-10 max-w-xs mx-auto">Dữ liệu có thể đã bị gỡ bỏ hoặc ID không chính xác
          trong hệ thống.</p>
        <RouterLink to="/"
          class="px-8 py-4 bg-brand text-white rounded-2xl font-black text-sm shadow-xl shadow-brand/20 hover:bg-brand-dark transition-all">
          Quay lại bản đồ</RouterLink>
      </div>
    </div>

    <!-- Mobile Bottom Bar -->
    <div v-if="crossing"
      class="md:hidden fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-xl border-t border-line p-5 z-50 flex items-center gap-4 shadow-2xl">
      <RouterLink to="/"
        class="flex-1 flex items-center justify-center gap-3 py-4 bg-bg-strong text-text rounded-2xl font-black text-sm border border-line">
        <MapPin :size="20" /> Bản đồ
      </RouterLink>
      <button @click="useLiveLocation"
        class="flex-1 flex items-center justify-center gap-3 py-4 bg-brand text-white rounded-2xl font-black text-sm shadow-xl shadow-brand/20">
        <Navigation :size="20" /> Định vị
      </button>
    </div>
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

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.line-clamp-3 {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
