<script setup>
import { computed, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import MetricCards from '../components/MetricCards.vue'
import {
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

const activeSection = computed(() => {
  if (route.name === 'public-directory') return 'Danh mục điểm'
  if (route.name === 'public-insights') return 'Cảnh báo và sự cố'
  return 'Bản đồ trực quan'
})

watch(
  () => [publicFilters.q, publicFilters.risk_level, publicFilters.barrier_type],
  async () => {
    await loadPublicOverview(publicFilters)
  },
  { immediate: true }
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
  <div class="public-shell">
    <header class="public-header">
      <div class="public-header__brand">
        <div class="brand-mark">BH</div>
        <div>
          <p class="micro-label">Giám sát giao cắt đường sắt</p>
          <h1>Biên Hòa Rail Watch</h1>
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
      </nav>

      <div class="public-header__meta">
        <span class="soft-badge">{{ publicState.crossings.length }} điểm đang theo dõi</span>
        <span class="soft-badge soft-badge--accent">{{ activeSection }}</span>
      </div>
    </header>

    <main class="public-main">
      <section class="hero-panel">
        <div class="hero-panel__copy">
          <p class="micro-label">Nền tảng tra cứu công khai</p>
          <h2>Theo dõi điểm giao cắt, lịch tàu và các khu vực rủi ro tại Biên Hòa</h2>
          <p>
            Giao diện mới tập trung vào thao tác nhanh: tìm điểm, lọc theo mức nguy hiểm, xem
            điểm gần bạn và theo dõi sự cố mà không cần đi qua nhiều lớp màn hình.
          </p>
        </div>

        <div class="hero-panel__stats">
          <MetricCards :summary="publicState.summary" />
        </div>
      </section>

      <section class="command-deck">
        <div class="command-deck__primary">
          <label class="field field--search">
            <span>Tìm nhanh điểm giao cắt</span>
            <input
              :value="publicFilters.q"
              placeholder="Tên điểm, mã điểm, địa chỉ hoặc khu vực"
              @input="updatePublicFilters({ q: $event.target.value })"
            />
          </label>

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

            <button class="primary-button" type="button" :disabled="publicState.locating" @click="handleLocateUser">
              {{ publicState.locating ? 'Đang định vị...' : 'Dùng vị trí của tôi' }}
            </button>
            <button class="secondary-button" type="button" @click="clearFilters">Đặt lại</button>
          </div>
        </div>

        <div class="status-strip">
          <p v-if="publicState.userLocation">
            Đang dùng vị trí hiện tại để tính khoảng cách và gợi ý điểm gần nhất.
          </p>
          <p v-else>
            Bạn có thể bật vị trí hoặc dùng bộ lọc phía trên để tập trung vào nhóm điểm cần xem.
          </p>
          <p v-if="publicState.error" class="error-text">{{ publicState.error }}</p>
        </div>
      </section>

      <RouterView />
    </main>
  </div>
</template>
