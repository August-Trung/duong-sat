<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  MapPin, ShieldAlert, ChevronRight,
  Search, Filter, LayoutGrid, List,
  Clock, AlertCircle, Train, Info
} from 'lucide-vue-next'
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
const viewMode = ref('list')

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

function openCrossingDetail(id) {
  router.push({ name: 'public-crossing-detail', params: { id } })
}
</script>

<template>
  <div class="directory-page space-y-10 pb-20">
    <!-- Featured Strip -->
    <section v-if="groupedRows.priority.length" class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <article v-for="item in groupedRows.priority" :key="item.id"
        class="group bg-white p-6 rounded-3xl border border-line shadow-sm hover:shadow-xl hover:shadow-black/5 transition-all cursor-pointer relative overflow-hidden"
        @click="openCrossingDetail(item.id)">
        <div class="absolute top-0 left-0 w-1 h-full" :class="'bg-' + item.risk_level"></div>
        <div class="flex items-center justify-between mb-4">
          <span class="px-2 py-0.5 bg-brand-soft text-brand text-[10px] font-bold rounded uppercase tracking-wider">Ưu
            tiên theo bộ lọc</span>
          <span class="px-2 py-0.5 text-[10px] font-bold rounded uppercase tracking-wider"
            :class="'badge-risk-' + item.risk_level">
            {{ riskLabel(item.risk_level) }}
          </span>
        </div>
        <h3 class="text-lg font-bold text-text mb-1 group-hover:text-brand transition-colors">{{ item.name }}</h3>
        <p class="text-xs text-soft mb-4 flex items-center gap-1">
          <MapPin :size="12" />
          {{ item.address || `${item.district}, ${item.city}` }}
        </p>
        <div class="flex items-center justify-between pt-4 border-t border-line">
          <span class="text-[10px] font-bold text-soft font-mono">#{{ item.code }}</span>
          <span class="text-[10px] font-bold text-brand uppercase tracking-wider flex items-center gap-1">
            {{ crossingDistance(item) }}
            <ChevronRight :size="12" />
          </span>
        </div>
      </article>
    </section>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-10">
      <!-- Catalog Section -->
      <section class="lg:col-span-8 space-y-6">
        <div class="flex items-center justify-between">
          <div>
            <h2 class="text-xl font-bold text-text">Danh mục điểm giao cắt</h2>
            <p class="text-xs text-soft font-medium uppercase tracking-wider">{{ filteredRows.length }} điểm phù hợp</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              class="p-2 border border-line rounded-lg transition-all"
              :class="viewMode === 'grid' ? 'bg-brand text-white shadow-lg shadow-brand/20' : 'bg-white text-soft hover:text-brand'"
              @click="viewMode = 'grid'"
            >
              <LayoutGrid :size="18" />
            </button>
            <button
              class="p-2 rounded-lg transition-all"
              :class="viewMode === 'list' ? 'bg-brand text-white shadow-lg shadow-brand/20' : 'bg-white border border-line text-soft hover:text-brand'"
              @click="viewMode = 'list'"
            >
              <List :size="18" />
            </button>
          </div>
        </div>

        <div
          class="gap-4"
          :class="viewMode === 'grid' ? 'grid grid-cols-1 sm:grid-cols-2' : 'flex flex-col'"
        >
          <button v-for="item in groupedRows.regular" :key="item.id"
            class="group bg-white p-5 rounded-2xl border border-line shadow-sm hover:border-brand/20 hover:shadow-lg hover:shadow-black/5 transition-all text-left relative overflow-hidden"
            :class="[
              viewMode === 'list' ? 'flex items-center justify-between gap-4' : '',
              { 'ring-2 ring-brand ring-offset-2': item.id === publicState.selectedCrossingId },
            ]"
            @click="openCrossingDetail(item.id)">
            <div class="flex items-center justify-between mb-3" :class="viewMode === 'list' ? 'mb-0 flex-1 order-2' : ''">
              <span class="px-2 py-0.5 text-[9px] font-bold rounded uppercase tracking-wider"
                :class="'badge-risk-' + item.risk_level">
                {{ riskLabel(item.risk_level) }}
              </span>
              <span class="text-[10px] font-bold text-soft">{{ crossingDistance(item) }}</span>
            </div>
            <strong class="block font-bold text-text mb-1 group-hover:text-brand transition-colors truncate"
              :class="viewMode === 'list' ? 'mb-0 order-1 w-56 shrink-0' : ''">{{
              item.name }}</strong>
            <span class="block text-[10px] font-bold text-soft font-mono mb-2" :class="viewMode === 'list' ? 'mb-0 order-3' : ''">#{{ item.code }}</span>
            <p class="text-xs text-soft mb-4 line-clamp-1" :class="viewMode === 'list' ? 'mb-0 order-4 flex-1' : ''">{{ item.address || `${item.district}, ${item.city}` }}</p>
            <div class="flex items-center justify-between pt-3 border-t border-line" :class="viewMode === 'list' ? 'pt-0 border-t-0 order-5 w-32 shrink-0' : ''">
              <span class="text-[10px] font-bold text-soft uppercase tracking-wider">{{ item.barrier_type || 'Đang cập nhật' }}</span>
              <span class="text-[10px] font-bold text-text">{{ item.risk_score }} điểm</span>
            </div>
          </button>
        </div>

        <div v-if="!filteredRows.length"
          class="flex flex-col items-center justify-center py-20 text-center bg-white rounded-3xl border-2 border-dashed border-line">
          <Search :size="48" class="text-soft/20 mb-4" />
          <p class="text-soft font-bold">Không tìm thấy điểm nào khớp với bộ lọc hiện tại.</p>
          <button @click="resetPublicFilters" class="mt-4 text-brand font-bold text-sm hover:underline">Xóa bộ
            lọc</button>
        </div>
      </section>

      <!-- Preview Sidebar -->
      <aside class="lg:col-span-4 space-y-8">
        <div class="bg-white rounded-3xl border border-line shadow-sm overflow-hidden sticky top-24">
          <div class="p-6 border-b border-line flex items-center gap-3 bg-bg-strong/30">
            <div class="w-10 h-10 rounded-xl bg-white text-brand flex items-center justify-center shadow-sm">
              <Info :size="20" />
            </div>
            <h3 class="font-bold text-text">Chi tiết nhanh</h3>
          </div>

          <div v-if="publicState.selectedCrossing" class="p-6 space-y-8">
            <div>
              <h4 class="text-xl font-bold text-text mb-1">{{ publicState.selectedCrossing.name }}</h4>
              <p class="text-xs text-soft flex items-center gap-1">
                <MapPin :size="12" /> {{ publicState.selectedCrossing.address || publicState.selectedCrossing.district
                }}
              </p>
            </div>

            <div class="grid grid-cols-2 gap-3">
              <div class="p-3 bg-bg-strong rounded-xl">
                <span class="text-[10px] font-bold text-soft uppercase block mb-1">Mã điểm</span>
                <span class="text-xs font-bold font-mono">{{ publicState.selectedCrossing.code }}</span>
              </div>
              <div class="p-3 bg-bg-strong rounded-xl">
                <span class="text-[10px] font-bold text-soft uppercase block mb-1">Rào chắn</span>
                <span class="text-xs font-bold">{{ publicState.selectedCrossing.barrier_type || 'N/A' }}</span>
              </div>
            </div>

            <div class="p-4 bg-brand-soft rounded-2xl">
              <div class="flex items-center gap-2 mb-2 text-brand">
                <ShieldAlert :size="18" />
                <strong class="text-sm">{{ selectedRiskSummary.label }}</strong>
              </div>
              <p class="text-xs text-brand-strong leading-relaxed">{{ selectedRiskSummary.message }}</p>
            </div>

            <div class="space-y-4">
              <h5 class="text-[10px] font-bold text-soft uppercase tracking-widest flex items-center gap-2">
                <Train :size="14" /> Lịch tàu gần nhất
              </h5>
              <div class="space-y-2">
                <div v-for="schedule in selectedSchedules" :key="`${schedule.id}-${schedule.pass_time}`"
                  class="p-3 bg-bg-strong rounded-xl flex items-center justify-between">
                  <span class="text-xs font-bold text-text">{{ schedule.pass_time }}</span>
                  <span class="text-[10px] font-bold text-soft uppercase">{{ schedule.train_no }} · {{
                    schedule.direction }}</span>
                </div>
                <div v-if="!selectedSchedules.length" class="text-xs text-soft italic py-2">
                  Chưa có dữ liệu lịch tàu.
                </div>
              </div>
            </div>

            <div class="space-y-4">
              <h5 class="text-[10px] font-bold text-soft uppercase tracking-widest flex items-center gap-2">
                <AlertCircle :size="14" /> Sự cố (90 ngày)
              </h5>
              <div class="space-y-2">
                <div v-for="incident in selectedRecentIncidents" :key="incident.id"
                  class="p-3 bg-danger-soft/30 border border-danger/10 rounded-xl">
                  <p class="text-xs font-bold text-danger mb-1">{{ incident.title }}</p>
                  <p class="text-[10px] text-danger/60">{{ incident.incident_date || 'Không rõ ngày' }}</p>
                </div>
                <div v-if="!selectedRecentIncidents.length" class="text-xs text-soft italic py-2">
                  Chưa ghi nhận sự cố.
                </div>
              </div>
            </div>

            <button
              class="w-full py-3 bg-brand text-white rounded-2xl font-bold text-sm hover:bg-brand-dark transition-all shadow-lg shadow-brand/20 flex items-center justify-center gap-2"
              @click="openCrossingDetail(publicState.selectedCrossing.id)">
              Xem hồ sơ đầy đủ
              <ChevronRight :size="18" />
            </button>
          </div>

          <div v-else class="p-12 text-center">
            <div class="w-16 h-16 rounded-full bg-bg-strong flex items-center justify-center mx-auto mb-4 text-soft">
              <List :size="32" />
            </div>
            <p class="text-sm text-soft font-medium">Chọn một điểm trong danh mục để xem chi tiết nhanh.</p>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
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

.line-clamp-1 {
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
