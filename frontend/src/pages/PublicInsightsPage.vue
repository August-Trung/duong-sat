<script setup>
import { computed, reactive } from 'vue'
import {
  AlertTriangle, ShieldAlert, Activity,
  TrendingUp, Search, Filter, Clock,
  AlertCircle, MapPin, ChevronRight,
  BarChart3, PieChart
} from 'lucide-vue-next'
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
  <div class="insights-page space-y-10 pb-20">
    <!-- Hero Insights -->
    <section class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <article
        class="bg-surface-dark rounded-3xl p-8 text-white shadow-2xl shadow-black/10 relative overflow-hidden group">
        <div
          class="absolute top-0 right-0 w-32 h-32 bg-brand/10 rounded-full -mr-16 -mt-16 blur-3xl group-hover:bg-brand/20 transition-all">
        </div>
        <div class="relative z-10">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 rounded-xl bg-brand flex items-center justify-center">
              <ShieldAlert :size="20" />
            </div>
            <span class="text-xs font-bold uppercase tracking-widest text-white/60">Điểm nóng rủi ro</span>
          </div>
          <h3 class="text-2xl font-bold mb-2">{{ topHazards[0]?.name || 'Chưa có dữ liệu' }}</h3>
          <p class="text-white/60 text-sm mb-8 leading-relaxed">
            {{ topHazards[0]?.address || `${topHazards[0]?.district || 'Biên Hòa'}, ${topHazards[0]?.city || ''}` }}
          </p>
          <div v-if="topHazards[0]" class="flex items-center gap-3">
            <span class="px-3 py-1 bg-white/10 rounded-full text-[10px] font-bold uppercase tracking-wider">{{
              topHazards[0].risk_score }} điểm rủi ro</span>
            <span class="px-3 py-1 bg-brand rounded-full text-[10px] font-bold uppercase tracking-wider">{{
              distanceToCrossing(topHazards[0]) }}</span>
          </div>
        </div>
      </article>

      <article class="bg-white rounded-3xl p-8 border border-line shadow-sm relative overflow-hidden group">
        <div
          class="absolute top-0 right-0 w-32 h-32 bg-warning-soft rounded-full -mr-16 -mt-16 blur-3xl group-hover:bg-warning/10 transition-all">
        </div>
        <div class="relative z-10">
          <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 rounded-xl bg-warning-soft text-warning flex items-center justify-center">
              <AlertTriangle :size="20" />
            </div>
            <span class="text-xs font-bold uppercase tracking-widest text-soft">Cảnh báo khu vực</span>
          </div>
          <h3 class="text-2xl font-bold text-text mb-2">{{ areaMatches.length }} điểm trong vùng quan tâm</h3>
          <p class="text-soft text-sm mb-8 leading-relaxed">
            Có {{ areaIncidentCount }} sự cố được ghi nhận trong 30 ngày gần nhất quanh vùng đang theo dõi.
          </p>
          <div class="flex items-center gap-3">
            <span class="px-3 py-1 bg-bg-strong rounded-full text-[10px] font-bold text-soft uppercase tracking-wider">
              {{ publicState.areaAlert.label || 'Chưa chọn tâm cảnh báo' }}
            </span>
          </div>
        </div>
      </article>
    </section>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-10">
      <!-- Priority List -->
      <section class="lg:col-span-7 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-brand-soft text-brand flex items-center justify-center">
            <TrendingUp :size="20" />
          </div>
          <div>
            <h3 class="font-bold text-text text-xl">Ưu tiên kiểm soát</h3>
            <p class="text-xs text-soft font-medium uppercase tracking-wider">Danh sách rủi ro cao nhất</p>
          </div>
        </div>

        <div class="bg-white rounded-3xl border border-line shadow-sm overflow-hidden">
          <div class="divide-y divide-line">
            <article v-for="item in topHazards" :key="item.id"
              class="p-5 hover:bg-bg-strong/50 transition-all group flex items-center justify-between">
              <div class="flex items-center gap-4">
                <div
                  class="w-10 h-10 rounded-xl bg-bg-strong flex items-center justify-center text-soft group-hover:text-brand transition-colors">
                  <MapPin :size="20" />
                </div>
                <div>
                  <strong class="block font-bold text-text group-hover:text-brand transition-colors">{{ item.name
                    }}</strong>
                  <span class="text-xs text-soft">{{ item.district }}, {{ item.city }} · {{ distanceToCrossing(item)
                    }}</span>
                </div>
              </div>
              <div class="flex items-center gap-4">
                <span class="text-sm font-black text-text">{{ item.risk_score }}</span>
                <div class="w-10 h-10 rounded-full flex items-center justify-center"
                  :class="'bg-' + item.risk_level + '-soft text-' + item.risk_level">
                  <ShieldAlert v-if="item.risk_level === 'very_high'" :size="18" />
                  <AlertTriangle v-else :size="18" />
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <!-- Area Stack -->
      <section class="lg:col-span-5 space-y-6">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-brand-soft text-brand flex items-center justify-center">
            <Activity :size="20" />
          </div>
          <div>
            <h3 class="font-bold text-text text-xl">Theo dõi khu vực</h3>
            <p class="text-xs text-soft font-medium uppercase tracking-wider">Điểm trong bán kính cảnh báo</p>
          </div>
        </div>

        <div class="bg-white rounded-3xl border border-line shadow-sm overflow-hidden">
          <div class="p-2 max-h-[480px] overflow-y-auto custom-scrollbar">
            <div v-for="item in areaMatches.slice(0, 12)" :key="item.id"
              class="p-4 hover:bg-bg-strong rounded-2xl transition-all flex items-center justify-between">
              <div>
                <strong class="block text-sm font-bold text-text">{{ item.name }}</strong>
                <span class="text-[10px] text-soft font-bold uppercase tracking-wider">{{ item.address || item.district
                  }}</span>
              </div>
              <span class="px-2 py-0.5 bg-bg-strong text-text text-[10px] font-bold rounded uppercase tracking-wider">{{
                item.risk_score }} PTS</span>
            </div>
            <div v-if="!areaMatches.length" class="flex flex-col items-center justify-center py-20 text-center">
              <div class="w-12 h-12 rounded-full bg-bg-strong flex items-center justify-center mb-4 text-soft/40">
                <BarChart3 :size="24" />
              </div>
              <p class="text-xs text-soft font-bold max-w-[200px] mx-auto">Chưa có vùng quan tâm để phân tích. Hãy chọn
                vị trí trên bản đồ.</p>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- Timeline Section -->
    <section class="space-y-8">
      <div class="flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-xl bg-brand-soft text-brand flex items-center justify-center">
            <Clock :size="20" />
          </div>
          <div>
            <h3 class="font-bold text-text text-xl">Timeline sự cố</h3>
            <p class="text-xs text-soft font-medium uppercase tracking-wider">Dòng thời gian mới nhất</p>
          </div>
        </div>

        <div class="flex flex-col md:flex-row gap-4 items-end">
          <div class="field">
            <span class="text-[10px] font-bold text-soft uppercase tracking-widest mb-1 block">Tìm kiếm</span>
            <div class="relative">
              <Search class="absolute left-3 top-1/2 -translate-y-1/2 text-soft" :size="14" />
              <input v-model="incidentFilters.q" placeholder="Tên điểm, tiêu đề..."
                class="pl-9 pr-4 py-2 bg-white border border-line rounded-xl text-xs font-medium outline-none focus:border-brand/20 transition-all w-60" />
            </div>
          </div>

          <div class="field">
            <span class="text-[10px] font-bold text-soft uppercase tracking-widest mb-1 block">Mức độ</span>
            <select v-model="incidentFilters.severity"
              class="px-4 py-2 bg-white border border-line rounded-xl text-xs font-bold outline-none focus:border-brand/20 transition-all">
              <option value="">Tất cả</option>
              <option value="very_high">Rất cao</option>
              <option value="high">Cao</option>
              <option value="medium">Trung bình</option>
              <option value="low">Thấp</option>
            </select>
          </div>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <article v-for="incident in timelineIncidents" :key="incident.id"
          class="bg-white p-6 rounded-3xl border border-line shadow-sm hover:shadow-xl hover:shadow-black/5 transition-all group">
          <div class="flex items-center justify-between mb-4">
            <span class="text-[10px] font-bold text-soft uppercase tracking-widest">{{ incident.incident_date || 'Không rõ ngày' }}</span>
            <span class="px-2 py-0.5 text-[9px] font-bold rounded uppercase tracking-wider"
              :class="'badge-risk-' + incident.severity_level">
              {{ severityLabel(incident.severity_level) }}
            </span>
          </div>
          <h4 class="font-bold text-text mb-2 group-hover:text-brand transition-colors line-clamp-2">{{ incident.title
            }}</h4>
          <div class="flex items-center gap-2 text-xs text-soft">
            <MapPin :size="14" />
            <span class="truncate">{{ incident.crossing_name || 'Chưa gắn điểm' }}</span>
          </div>
        </article>

        <div v-if="!timelineIncidents.length"
          class="md:col-span-2 lg:col-span-3 flex flex-col items-center justify-center py-20 text-center bg-white rounded-3xl border-2 border-dashed border-line">
          <AlertCircle :size="48" class="text-soft/20 mb-4" />
          <p class="text-soft font-bold">Không có sự cố phù hợp với bộ lọc hiện tại.</p>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 10px;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.bg-very_high-soft {
  background-color: var(--danger-soft);
}

.bg-high-soft {
  background-color: var(--warning-soft);
}

.bg-medium-soft {
  background-color: #fef3c7;
}

.bg-low-soft {
  background-color: var(--success-soft);
}

.text-very_high {
  color: var(--danger);
}

.text-high {
  color: var(--warning);
}

.text-medium {
  color: #f59e0b;
}

.text-low {
  color: var(--success);
}
</style>
