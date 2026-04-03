<script setup>
import { computed, onMounted, ref } from 'vue'
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
  <section class="admin-board admin-board--dashboard">
    <section class="admin-overview-bar content-card">
      <div>
        <p class="micro-label">Bảng điều hành</p>
        <h3>Trung tâm vận hành dữ liệu đường sắt Biên Hòa</h3>
        <p class="body-copy">
          Theo dõi nhanh hồ sơ, cảnh báo chất lượng, nhật ký thay đổi và xuất báo cáo cho đội vận hành.
        </p>
      </div>

      <div class="toolbar-actions">
        <button
          class="primary-button"
          :disabled="downloading === 'crossings'"
          @click="downloadReport('crossings')"
        >
          {{ downloading === 'crossings' ? 'Đang xuất...' : 'Xuất danh mục điểm' }}
        </button>
        <button
          class="secondary-button"
          :disabled="downloading === 'quality'"
          @click="downloadReport('quality')"
        >
          {{ downloading === 'quality' ? 'Đang xuất...' : 'Xuất chất lượng dữ liệu' }}
        </button>
      </div>
    </section>

    <MetricCards :summary="summary" />

    <div class="admin-dashboard-grid admin-dashboard-grid--dense">
      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Cảnh báo chất lượng</p>
            <h3>{{ overview.qualityAlerts?.length || 0 }} mục cần rà soát</h3>
          </div>
        </div>

        <div class="stack-list">
          <div
            v-for="alert in overview.qualityAlerts?.slice(0, 6)"
            :key="`${alert.type}-${alert.crossing_id}-${alert.title}`"
            class="stack-item"
          >
            <strong>{{ alert.title }}</strong>
            <span>{{ alert.detail }}</span>
          </div>
        </div>
      </section>

      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Nhật ký thay đổi</p>
            <h3>Hoạt động gần nhất</h3>
          </div>
        </div>

        <div class="stack-list">
          <div v-for="log in overview.auditLogs?.slice(0, 6)" :key="log.id" class="stack-item">
            <strong>{{ log.summary }}</strong>
            <span>{{ log.username }} · {{ log.created_at }}</span>
          </div>
        </div>
      </section>

      <section class="content-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Ưu tiên xử lý</p>
            <h3>Điểm cần can thiệp sớm</h3>
          </div>
        </div>

        <div class="stack-list">
          <div v-for="item in overview.crossings?.slice(0, 6)" :key="item.id" class="stack-item">
            <strong>{{ item.name }}</strong>
            <span>Mức độ: {{ riskLabel(item.risk_level) }}</span>
            <span>Điểm rủi ro: {{ item.risk_score }}</span>
          </div>
        </div>
      </section>
    </div>

    <section class="content-card">
      <div class="section-head">
        <div>
          <p class="micro-label">Ma trận quyền</p>
          <h3>Vai trò và khả năng truy cập</h3>
        </div>
      </div>

      <div class="admin-permission-grid">
        <div v-for="(permissions, role) in overview.permissionMatrix" :key="role" class="stack-item">
          <strong>{{ roleLabel(role) }}</strong>
          <span>{{ permissions.join(', ') }}</span>
        </div>
      </div>
    </section>
  </section>
</template>
