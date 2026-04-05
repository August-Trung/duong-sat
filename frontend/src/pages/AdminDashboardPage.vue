<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  FileDown, AlertTriangle, Activity,
  TrendingUp, ShieldAlert, CheckCircle2,
  Clock, User, ArrowRight, Download,
  BarChart3, PieChart, Info, Loader2
} from 'lucide-vue-next'
import MetricCards from '../components/MetricCards.vue'
import { downloadCrossingsReport, downloadQualityReport } from '../api'
import { adminState } from '../stores/adminData'
import { loadPublicOverview, publicState } from '../stores/publicData'

const summary = computed(() => publicState.summary)
const overview = computed(() => adminState.overview)
const downloading = ref('')

onMounted(async () => {
  if (!summary.value.total_crossings) {
    await loadPublicOverview()
  }
})

function riskLabel(level) {
  return {
    very_high: 'Rất cao',
    high: 'Cao',
    medium: 'Trung bình',
    low: 'Thấp',
    unknown: 'Chưa xác định',
  }[level] || 'Chưa rõ'
}

function roleLabel(role) {
  return {
    admin: 'Quản trị hệ thống',
    editor: 'Biên tập dữ liệu',
    reviewer: 'Kiểm duyệt dữ liệu',
    viewer: 'Chỉ xem',
  }[role] || role
}

async function downloadReport(type) {
  downloading.value = type
  try {
    const blob = type === 'quality' ? await downloadQualityReport() : await downloadCrossingsReport()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = type === 'quality' ? 'bao-cao-chat-luong-du-lieu.csv' : 'bao-cao-diem-giao-cat.csv'
    link.click()
    URL.revokeObjectURL(url)
  } finally {
    downloading.value = ''
  }
}
</script>

<template>
  <div class="admin-dashboard space-y-10">
    <!-- Header Section -->
    <div
      class="flex flex-col lg:flex-row lg:items-center justify-between gap-8 bg-white p-10 rounded-[40px] border border-line shadow-sm relative overflow-hidden">
      <div class="absolute top-0 right-0 w-64 h-64 bg-brand/5 rounded-full -mr-32 -mt-32 blur-3xl"></div>
      <div class="max-w-2xl relative z-10">
        <div class="flex items-center gap-3 mb-4">
          <span
            class="px-3 py-1 bg-brand-soft text-brand text-[10px] font-black rounded-full uppercase tracking-widest border border-brand/10">Hệ
            thống vận hành</span>
          <span class="w-1.5 h-1.5 bg-line rounded-full"></span>
          <span class="text-soft text-xs font-bold uppercase tracking-wider">Cập nhật: {{ new
            Date().toLocaleDateString('vi-VN') }}</span>
        </div>
        <h1 class="text-4xl font-black text-text mb-4 tracking-tight">Trung tâm điều hành <span
            class="text-brand">RailWatch</span></h1>
        <p class="text-soft text-base leading-relaxed max-w-xl">
          Nền tảng quản trị dữ liệu an toàn đường sắt khu vực Biên Hòa. Theo dõi hồ sơ điểm giao cắt,
          giám sát chất lượng dữ liệu và điều phối đội ngũ vận hành hiện trường.
        </p>
      </div>

      <div class="flex flex-wrap gap-4 relative z-10">
        <button
          class="flex items-center gap-3 px-6 py-4 bg-brand text-white rounded-2xl font-black text-sm hover:bg-brand-dark transition-all shadow-xl shadow-brand/20 disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98]"
          :disabled="downloading === 'crossings'" @click="downloadReport('crossings')">
          <Download v-if="downloading !== 'crossings'" :size="20" />
          <Loader2 v-else :size="20" class="animate-spin" />
          {{ downloading === 'crossings' ? 'Đang xuất...' : 'Xuất danh mục' }}
        </button>
        <button
          class="flex items-center gap-3 px-6 py-4 bg-bg-strong text-text rounded-2xl font-black text-sm hover:bg-line transition-all disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98]"
          :disabled="downloading === 'quality'" @click="downloadReport('quality')">
          <FileDown v-if="downloading !== 'quality'" :size="20" />
          <Loader2 v-else :size="20" class="animate-spin" />
          {{ downloading === 'quality' ? 'Đang xuất...' : 'Báo cáo chất lượng' }}
        </button>
      </div>
    </div>

    <!-- Quick Stats -->
    <MetricCards :summary="summary" />

    <!-- Main Grid -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-10">
      <!-- Quality Alerts -->
      <div
        class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden flex flex-col group hover:shadow-xl hover:shadow-black/5 transition-all">
        <div class="p-8 border-b border-line flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div
              class="w-12 h-12 rounded-2xl bg-danger-soft text-danger flex items-center justify-center group-hover:scale-110 transition-transform">
              <ShieldAlert :size="24" />
            </div>
            <h3 class="font-black text-text tracking-tight">Cảnh báo chất lượng</h3>
          </div>
          <span class="px-3 py-1 bg-danger text-white text-[10px] font-black rounded-full uppercase tracking-widest">
            {{ overview.qualityAlerts?.length || 0 }} MỤC
          </span>
        </div>

        <div class="flex-1 p-4 overflow-y-auto max-h-[440px] custom-scrollbar">
          <div v-if="!overview.qualityAlerts?.length"
            class="flex flex-col items-center justify-center py-20 text-center">
            <div class="w-20 h-20 rounded-full bg-success-soft text-success flex items-center justify-center mb-6">
              <CheckCircle2 :size="40" />
            </div>
            <p class="text-soft font-bold uppercase tracking-widest text-xs">Dữ liệu hiện tại đạt chuẩn</p>
          </div>
          <div v-for="alert in overview.qualityAlerts?.slice(0, 10)"
            :key="`${alert.type}-${alert.crossing_id}-${alert.title}`"
            class="p-5 hover:bg-bg-strong rounded-3xl transition-all group/item cursor-default mb-2 last:mb-0">
            <div class="flex items-start gap-4">
              <div class="mt-1.5 w-2 h-2 rounded-full bg-danger flex-shrink-0"></div>
              <div>
                <p
                  class="text-sm font-black text-text group-hover/item:text-danger transition-colors leading-tight mb-1">
                  {{ alert.title }}</p>
                <p class="text-xs text-soft font-medium leading-relaxed">{{ alert.detail }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="p-6 border-t border-line bg-bg-strong/30">
          <button
            class="w-full py-3 bg-white border border-line rounded-xl text-[10px] font-black text-brand uppercase tracking-widest hover:bg-brand hover:text-white transition-all flex items-center justify-center gap-2">
            Xem tất cả cảnh báo
            <ArrowRight :size="14" />
          </button>
        </div>
      </div>

      <!-- Audit Logs -->
      <div
        class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden flex flex-col group hover:shadow-xl hover:shadow-black/5 transition-all">
        <div class="p-8 border-b border-line flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div
              class="w-12 h-12 rounded-2xl bg-brand-soft text-brand flex items-center justify-center group-hover:scale-110 transition-transform">
              <Activity :size="24" />
            </div>
            <h3 class="font-black text-text tracking-tight">Hoạt động hệ thống</h3>
          </div>
          <Clock :size="20" class="text-soft" />
        </div>

        <div class="flex-1 p-4 overflow-y-auto max-h-[440px] custom-scrollbar">
          <div v-for="log in overview.auditLogs?.slice(0, 10)" :key="log.id"
            class="p-5 border-b border-line last:border-0 hover:bg-bg-strong rounded-3xl transition-all mb-1 last:mb-0">
            <p class="text-sm font-black text-text mb-2 leading-tight">{{ log.summary }}</p>
            <div class="flex items-center gap-4 text-[10px] font-black text-soft uppercase tracking-widest">
              <span class="flex items-center gap-1.5">
                <User :size="12" class="text-brand" /> {{ log.username }}
              </span>
              <span class="w-1 h-1 bg-line rounded-full"></span>
              <span class="flex items-center gap-1.5">
                <Clock :size="12" /> {{ log.created_at }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Priority Crossings -->
      <div
        class="bg-white rounded-[40px] border border-line shadow-sm overflow-hidden flex flex-col group hover:shadow-xl hover:shadow-black/5 transition-all">
        <div class="p-8 border-b border-line flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div
              class="w-12 h-12 rounded-2xl bg-warning-soft text-warning flex items-center justify-center group-hover:scale-110 transition-transform">
              <TrendingUp :size="24" />
            </div>
            <h3 class="font-black text-text tracking-tight">Ưu tiên xử lý</h3>
          </div>
          <Info :size="20" class="text-soft" />
        </div>

        <div class="flex-1 p-4 overflow-y-auto max-h-[440px] custom-scrollbar">
          <div v-for="item in overview.crossings?.slice(0, 10)" :key="item.id"
            class="p-5 hover:bg-bg-strong rounded-3xl transition-all flex items-center justify-between group/item mb-2 last:mb-0">
            <div class="flex-1 min-w-0 pr-4">
              <p class="text-sm font-black text-text group-hover/item:text-brand transition-colors truncate mb-2">{{
                item.name }}</p>
              <div class="flex items-center gap-3">
                <span class="text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-widest border" :class="{
                  'bg-danger-soft text-danger border-danger/10': item.risk_level === 'very_high',
                  'bg-warning-soft text-warning border-warning/10': item.risk_level === 'high',
                  'bg-brand-soft text-brand border-brand/10': item.risk_level !== 'very_high' && item.risk_level !== 'high'
                }">
                  {{ riskLabel(item.risk_level) }}
                </span>
                <span class="text-[10px] font-black text-soft uppercase tracking-widest">Score: {{ item.risk_score
                  }}</span>
              </div>
            </div>
            <button
              class="w-10 h-10 flex items-center justify-center text-soft hover:text-brand hover:bg-brand-soft rounded-xl transition-all flex-shrink-0">
              <ArrowRight :size="18" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Permission Matrix -->
    <div class="bg-surface-dark rounded-[48px] p-12 text-white shadow-2xl shadow-black/20 relative overflow-hidden">
      <div class="absolute bottom-0 left-0 w-96 h-96 bg-brand/10 rounded-full -ml-48 -mb-48 blur-3xl"></div>
      <div class="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-8 mb-12">
        <div class="flex items-center gap-6">
          <div class="w-16 h-16 rounded-[24px] bg-white/10 flex items-center justify-center border border-white/5">
            <ShieldAlert :size="32" class="text-brand" />
          </div>
          <div>
            <h3 class="text-2xl font-black tracking-tight">Ma trận phân quyền</h3>
            <p class="text-white/40 text-sm font-medium mt-1">Cấu hình vai trò và khả năng truy cập hệ thống</p>
          </div>
        </div>
        <div
          class="px-4 py-2 bg-white/5 rounded-2xl border border-white/10 text-[10px] font-black uppercase tracking-[0.2em] text-white/60">
          Chế độ bảo mật cao
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative z-10">
        <div v-for="(permissions, role) in overview.permissionMatrix" :key="role"
          class="bg-white/5 border border-white/10 p-8 rounded-[32px] hover:bg-white/10 hover:border-brand/30 transition-all group">
          <div class="flex items-center justify-between mb-6">
            <h4 class="font-black text-brand tracking-tight text-lg">{{ roleLabel(role) }}</h4>
            <div class="w-6 h-6 rounded-full bg-brand/20 flex items-center justify-center text-brand">
              <CheckCircle2 :size="14" />
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <span v-for="perm in permissions" :key="perm"
              class="px-2.5 py-1.5 bg-white/5 rounded-lg text-[10px] font-black text-white/40 uppercase tracking-widest group-hover:text-white/80 transition-colors">
              {{ perm }}
            </span>
          </div>
        </div>
      </div>
    </div>
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
</style>
