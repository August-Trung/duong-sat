<script setup>
import { computed, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import MetricCards from '../components/MetricCards.vue'
import {
  loadCrossingDetail,
  loadPublicOverview,
  locateUser,
  publicFilters,
  publicState,
  resetPublicFilters,
  updatePublicFilters,
} from '../stores/publicData'
import { buildSearchSuggestions } from '../utils/publicHelpers'

const route = useRoute()

const districtOptions = computed(() =>
  [...new Set(publicState.crossings.map((item) => item.district).filter(Boolean))].sort((a, b) =>
    String(a).localeCompare(String(b), 'vi')
  )
)

const suggestions = computed(() => buildSearchSuggestions(publicState.crossings, publicFilters.q, 5))
const isDetailRoute = computed(() => route.name === 'public-crossing-detail')
const isMapRoute = computed(() => route.name === 'public-map')
const isSceneRoute = computed(() => route.name === 'public-scene-3d')
const showDiscoveryChrome = computed(() => !isDetailRoute.value && !isMapRoute.value && !isSceneRoute.value)

const activeSection = computed(() => {
  if (route.name === 'public-scene-3d') return 'Map 3D'
  if (route.name === 'public-crossing-detail') return 'Chi tiết điểm'
  if (route.name === 'public-directory') return 'Danh mục'
  if (route.name === 'public-insights') return 'Cảnh báo'
  return 'Bản đồ'
})

watch(
  () => [publicFilters.q, publicFilters.risk_level, publicFilters.barrier_type],
  async () => {
    await loadPublicOverview(publicFilters)
    if (isDetailRoute.value && route.params.id) {
      await loadCrossingDetail(Number(route.params.id))
    }
  },
  { immediate: true }
)

watch(
  () => route.params.id,
  async (value) => {
    if (!isDetailRoute.value || !value) return
    await loadCrossingDetail(Number(value))
  }
)

function applySuggestion(suggestion) {
  updatePublicFilters({ q: suggestion.name || suggestion.code || '' })
}

async function handleLocateUser() {
  try {
    await locateUser()
    if (!publicFilters.radius_meters) {
      updatePublicFilters({ radius_meters: 2000, only_nearby: true, sort_by: 'distance' })
    }
  } catch {
    // Error text is already stored in state.
  }
}

function clearFilters() {
  resetPublicFilters()
}
</script>

<template>
  <div
    class="public-shell"
    :class="{ 'public-shell--detail': isDetailRoute, 'public-shell--map': isMapRoute }"
  >
    <header class="public-header">
      <div class="public-header__brand">
        <div class="brand-mark">BH</div>
        <div>
          <p class="micro-label">Giám sát giao cắt đường sắt</p>
          <h1>Bien Hoa Rail Watch</h1>
        </div>
      </div>

      <nav class="public-header__nav">
        <RouterLink class="nav-pill" :class="{ active: route.name === 'public-map' }" to="/">
          Bản đồ
        </RouterLink>
        <RouterLink
          class="nav-pill"
          :class="{ active: route.name === 'public-directory' }"
          to="/directory"
        >
          Danh mục
        </RouterLink>
        <RouterLink
          class="nav-pill"
          :class="{ active: route.name === 'public-insights' }"
          to="/insights"
        >
          Cảnh báo
        </RouterLink>
        <RouterLink
          class="nav-pill"
          :class="{ active: route.name === 'public-scene-3d' }"
          to="/scene-3d"
        >
          Map 3D
        </RouterLink>
      </nav>

      <div class="public-header__meta">
        <span class="soft-badge">{{ publicState.crossings.length }} điểm</span>
        <span class="soft-badge soft-badge--accent">{{ activeSection }}</span>
      </div>
    </header>

    <main class="public-main">
      <section v-if="showDiscoveryChrome" class="overview-strip content-card">
        <div class="overview-strip__lead">
          <p class="micro-label">Điều phối công khai</p>
          <h2>Giám sát giao cắt đường sắt theo khu vực</h2>
          <p class="body-copy">
            Tra cứu nhanh điểm giao cắt, bài tin liên quan, cảnh báo và lịch tàu gần nhất trên cùng một màn hình.
          </p>
        </div>

        <div class="overview-strip__stats">
          <MetricCards :summary="publicState.summary" />
        </div>
      </section>

      <section v-if="showDiscoveryChrome" class="command-deck command-deck--compact">
        <div class="command-deck__header">
          <label class="field field--search">
            <span>Tìm nhanh điểm giao cắt</span>
            <input
              :value="publicFilters.q"
              placeholder="Tên điểm, mã điểm, địa chỉ hoặc khu vực"
              @input="updatePublicFilters({ q: $event.target.value })"
            />
          </label>

          <div class="command-deck__quick-actions">
            <button
              class="primary-button"
              type="button"
              :disabled="publicState.locating"
              @click="handleLocateUser"
            >
              {{ publicState.locating ? 'Đang định vị...' : 'Dùng vị trí của tôi' }}
            </button>
            <button class="secondary-button" type="button" @click="clearFilters">Đặt lại</button>
          </div>
        </div>

        <div v-if="publicFilters.q && suggestions.length" class="suggestion-strip">
          <button
            v-for="suggestion in suggestions"
            :key="suggestion.id"
            class="suggestion-chip"
            type="button"
            @click="applySuggestion(suggestion)"
          >
            <strong>{{ suggestion.name }}</strong>
            <span>{{ suggestion.code }} · {{ suggestion.district || suggestion.city }}</span>
          </button>
        </div>

        <div class="command-deck__filters">
          <label class="field">
            <span>Mức nguy hiểm</span>
            <select
              :value="publicFilters.risk_level"
              @change="updatePublicFilters({ risk_level: $event.target.value })"
            >
              <option value="">Tất cả</option>
              <option value="very_high">Rất cao</option>
              <option value="high">Cao</option>
              <option value="medium">Trung bình</option>
              <option value="low">Thấp</option>
            </select>
          </label>

          <label class="field">
            <span>Rào chắn</span>
            <select
              :value="publicFilters.barrier_type"
              @change="updatePublicFilters({ barrier_type: $event.target.value })"
            >
              <option value="">Tất cả</option>
              <option value="co_gac">Có gác</option>
              <option value="tu_dong">Tự động</option>
              <option value="khong_co">Không có</option>
            </select>
          </label>

          <label class="field">
            <span>Khu vực</span>
            <select
              :value="publicFilters.district"
              @change="updatePublicFilters({ district: $event.target.value })"
            >
              <option value="">Toàn Biên Hòa</option>
              <option v-for="district in districtOptions" :key="district" :value="district">
                {{ district }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>Sắp xếp</span>
            <select
              :value="publicFilters.sort_by"
              @change="updatePublicFilters({ sort_by: $event.target.value })"
            >
              <option value="risk">Theo rủi ro</option>
              <option value="distance">Theo khoảng cách</option>
              <option value="name">Theo tên</option>
            </select>
          </label>
        </div>

        <div class="command-deck__actions">
          <div class="toggle-cluster">
            <label class="switch-pill">
              <input
                :checked="publicFilters.only_nearby"
                type="checkbox"
                @change="updatePublicFilters({ only_nearby: $event.target.checked })"
              />
              <span>Gần tôi</span>
            </label>

            <label class="switch-pill">
              <input
                :checked="publicFilters.only_recent_incidents"
                type="checkbox"
                @change="updatePublicFilters({ only_recent_incidents: $event.target.checked })"
              />
              <span>Có sự cố gần đây</span>
            </label>

            <label class="switch-pill">
              <input
                :checked="publicFilters.only_unprotected"
                type="checkbox"
                @change="updatePublicFilters({ only_unprotected: $event.target.checked })"
              />
              <span>Không có rào chắn</span>
            </label>
          </div>

          <div class="action-strip">
            <label class="field field--compact">
              <span>Bán kính quan tâm</span>
              <select
                :value="publicFilters.radius_meters"
                @change="updatePublicFilters({ radius_meters: Number($event.target.value) || 0 })"
              >
                <option :value="0">Không giới hạn</option>
                <option :value="1000">1 km</option>
                <option :value="2000">2 km</option>
                <option :value="3000">3 km</option>
                <option :value="5000">5 km</option>
              </select>
            </label>
          </div>
        </div>

        <div class="status-strip">
          <p v-if="publicState.userLocation">
            Đang dùng vị trí hiện tại để tính khoảng cách và gợi ý điểm gần nhất.
          </p>
          <p v-else>
            Bật vị trí hoặc dùng bộ lọc để thu hẹp nhanh các điểm cần theo dõi.
          </p>
          <p v-if="publicState.error" class="error-text">{{ publicState.error }}</p>
        </div>
      </section>

      <section v-else-if="isDetailRoute" class="detail-context-bar">
        <div>
          <p class="micro-label">Đang xem chi tiết</p>
          <strong>Chi tiết điểm giao cắt</strong>
        </div>
      </section>

      <RouterView />
    </main>
  </div>
</template>
