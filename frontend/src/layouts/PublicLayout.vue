<script setup>
import { computed, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import {
  Map, LayoutGrid, BarChart3, Info, ShieldAlert,
  Search, Navigation, RotateCcw, MapPin, ChevronLeft,
  Loader2, Bell, User, Menu, X
} from 'lucide-vue-next'
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
const isFullWidthRoute = computed(() => isMapRoute.value || isSceneRoute.value)
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
  <div class="public-shell min-h-screen bg-bg flex flex-col font-sans selection:bg-brand/10 selection:text-brand">
    <!-- Header -->
    <header class="sticky top-0 z-50 bg-white/80 backdrop-blur-xl border-b border-line">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">
        <RouterLink to="/" class="flex items-center gap-3 group">
          <div
            class="w-10 h-10 rounded-xl bg-brand text-white flex items-center justify-center shadow-lg shadow-brand/20 group-hover:scale-110 transition-transform">
            <ShieldAlert :size="24" />
          </div>
          <div class="hidden sm:block">
            <h1 class="text-xl font-black text-text tracking-tight leading-none">RailWatch</h1>
            <p class="text-[10px] font-bold text-soft uppercase tracking-widest mt-1">Biên Hòa Monitoring</p>
          </div>
        </RouterLink>

        <nav class="hidden md:flex items-center gap-1 bg-bg-strong/50 p-1 rounded-2xl border border-line">
          <RouterLink to="/" class="nav-link" exact-active-class="active">
            <Map :size="18" />
            <span>Bản đồ</span>
          </RouterLink>
          <RouterLink :to="{ name: 'public-scene-3d' }" class="nav-link" exact-active-class="active">
            <LayoutGrid :size="18" />
            <span>3D Scene</span>
          </RouterLink>
          <RouterLink :to="{ name: 'public-directory' }" class="nav-link" exact-active-class="active">
            <Info :size="18" />
            <span>Danh mục</span>
          </RouterLink>
          <RouterLink :to="{ name: 'public-insights' }" class="nav-link" exact-active-class="active">
            <BarChart3 :size="18" />
            <span>Phân tích</span>
          </RouterLink>
        </nav>

        <div class="flex items-center gap-4">
          <div
            class="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-brand-soft text-brand rounded-full text-[10px] font-black tracking-wider border border-brand/10">
            <span class="w-2 h-2 bg-brand rounded-full animate-pulse"></span>
            {{ publicState.crossings.length }} ĐIỂM THEO DÕI
          </div>
          <RouterLink to="/admin/login"
            class="w-10 h-10 rounded-full bg-bg-strong text-soft flex items-center justify-center hover:bg-brand hover:text-white transition-all border border-line">
            <User :size="20" />
          </RouterLink>
        </div>
      </div>
    </header>

    <main :class="[
      'flex-1 w-full mx-auto transition-all duration-500',
      isFullWidthRoute ? 'max-w-none px-0 py-0' : 'max-w-7xl px-4 sm:px-6 lg:px-8 py-10'
    ]">
      <!-- Discovery Chrome (Search & Filters) -->
      <section v-if="showDiscoveryChrome" class="space-y-10 mb-16">
        <div class="bg-surface-dark rounded-[40px] p-10 text-white shadow-2xl shadow-black/10 relative overflow-hidden">
          <div class="absolute top-0 right-0 w-96 h-96 bg-brand/10 rounded-full -mr-48 -mt-48 blur-3xl"></div>
          <div class="relative z-10 flex flex-col lg:flex-row gap-12 items-center">
            <div class="flex-1 space-y-6">
              <span
                class="inline-block px-3 py-1 bg-white/10 rounded-full text-[10px] font-bold uppercase tracking-widest text-white/60 border border-white/5">Hệ
                thống công khai</span>
              <h2 class="text-4xl sm:text-5xl font-black tracking-tight leading-[1.1]">Giám sát rủi ro <br /><span
                  class="text-brand">đường sắt Biên Hòa</span></h2>
              <p class="text-white/60 text-lg max-w-2xl leading-relaxed">
                Cung cấp thông tin thời gian thực về các điểm giao cắt, cảnh báo nguy hiểm, lịch trình tàu và dữ liệu sự
                cố để đảm bảo an toàn giao thông.
              </p>
            </div>
            <div class="w-full lg:w-auto">
              <MetricCards :summary="publicState.summary" />
            </div>
          </div>
        </div>

        <div class="bg-white rounded-[32px] p-8 border border-line shadow-sm space-y-8">
          <div class="flex flex-col lg:flex-row gap-6 items-end">
            <div class="flex-1 w-full">
              <label class="block text-[10px] font-bold text-soft uppercase tracking-widest mb-2 ml-1">Tìm kiếm điểm
                giao cắt</label>
              <div class="relative group">
                <Search
                  class="absolute left-4 top-1/2 -translate-y-1/2 text-soft group-focus-within:text-brand transition-colors"
                  :size="20" />
                <input :value="publicFilters.q"
                  class="w-full pl-12 pr-4 py-4 rounded-2xl border border-line bg-bg-strong/30 focus:bg-white focus:ring-4 focus:ring-brand/5 focus:border-brand/20 transition-all outline-none font-medium text-text"
                  placeholder="Tên điểm, mã điểm, địa chỉ hoặc khu vực..."
                  @input="updatePublicFilters({ q: $event.target.value })" />
              </div>
            </div>
            <div class="flex gap-3 w-full lg:w-auto">
              <button
                class="flex-1 lg:flex-none px-6 py-4 bg-brand text-white rounded-2xl font-bold text-sm shadow-lg shadow-brand/20 hover:bg-brand-dark transition-all flex items-center justify-center gap-2 disabled:opacity-50"
                type="button" :disabled="publicState.locating" @click="handleLocateUser">
                <Navigation v-if="!publicState.locating" :size="18" />
                <Loader2 v-else class="animate-spin" :size="18" />
                {{ publicState.locating ? 'Đang định vị...' : 'Vị trí của tôi' }}
              </button>
              <button
                class="px-6 py-4 bg-bg-strong text-soft rounded-2xl font-bold text-sm hover:bg-line transition-all flex items-center justify-center gap-2"
                type="button" @click="clearFilters">
                <RotateCcw :size="18" />
                Đặt lại
              </button>
            </div>
          </div>

          <!-- Suggestions -->
          <div v-if="publicFilters.q && suggestions.length"
            class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <button v-for="suggestion in suggestions" :key="suggestion.id"
              class="p-4 bg-bg-strong/30 border border-line rounded-2xl flex items-center gap-4 text-left hover:border-brand/20 hover:bg-white hover:shadow-lg hover:shadow-black/5 transition-all"
              type="button" @click="applySuggestion(suggestion)">
              <div class="w-10 h-10 rounded-xl bg-white text-brand flex items-center justify-center shadow-sm">
                <MapPin :size="20" />
              </div>
              <div>
                <strong class="block font-bold text-sm text-text">{{ suggestion.name }}</strong>
                <span class="text-[10px] font-bold text-soft uppercase tracking-wider">{{ suggestion.code }} · {{
                  suggestion.district }}</span>
              </div>
            </button>
          </div>

          <!-- Advanced Filters -->
          <div class="pt-8 border-t border-line grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
            <div class="space-y-2">
              <span class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Mức nguy hiểm</span>
              <select :value="publicFilters.risk_level"
                class="w-full px-4 py-3 bg-bg-strong/30 border border-line rounded-xl text-xs font-bold outline-none focus:border-brand/20 transition-all"
                @change="updatePublicFilters({ risk_level: $event.target.value })">
                <option value="">Tất cả mức độ</option>
                <option value="very_high">Rất cao</option>
                <option value="high">Cao</option>
                <option value="medium">Trung bình</option>
                <option value="low">Thấp</option>
              </select>
            </div>

            <div class="space-y-2">
              <span class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Loại rào chắn</span>
              <select :value="publicFilters.barrier_type"
                class="w-full px-4 py-3 bg-bg-strong/30 border border-line rounded-xl text-xs font-bold outline-none focus:border-brand/20 transition-all"
                @change="updatePublicFilters({ barrier_type: $event.target.value })">
                <option value="">Tất cả loại</option>
                <option value="co_gac">Có gác</option>
                <option value="tu_dong">Tự động</option>
                <option value="khong_co">Không có</option>
              </select>
            </div>

            <div class="space-y-2">
              <span class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Khu vực</span>
              <select :value="publicFilters.district"
                class="w-full px-4 py-3 bg-bg-strong/30 border border-line rounded-xl text-xs font-bold outline-none focus:border-brand/20 transition-all"
                @change="updatePublicFilters({ district: $event.target.value })">
                <option value="">Toàn Biên Hòa</option>
                <option v-for="district in districtOptions" :key="district" :value="district">
                  {{ district }}
                </option>
              </select>
            </div>

            <div class="space-y-2">
              <span class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Sắp xếp</span>
              <select :value="publicFilters.sort_by"
                class="w-full px-4 py-3 bg-bg-strong/30 border border-line rounded-xl text-xs font-bold outline-none focus:border-brand/20 transition-all"
                @change="updatePublicFilters({ sort_by: $event.target.value })">
                <option value="risk">Mức độ rủi ro</option>
                <option value="distance">Khoảng cách</option>
                <option value="name">Tên điểm (A-Z)</option>
              </select>
            </div>
          </div>

          <div class="pt-8 border-t border-line flex flex-col md:flex-row items-center justify-between gap-6">
            <div class="flex flex-wrap gap-6">
              <label class="flex items-center gap-3 cursor-pointer group">
                <div class="relative">
                  <input :checked="publicFilters.only_nearby" type="checkbox" class="peer sr-only"
                    @change="updatePublicFilters({ only_nearby: $event.target.checked })" />
                  <div class="w-10 h-5 bg-bg-strong rounded-full peer-checked:bg-brand transition-all"></div>
                  <div
                    class="absolute left-1 top-1 w-3 h-3 bg-white rounded-full peer-checked:translate-x-5 transition-all shadow-sm">
                  </div>
                </div>
                <span class="text-xs font-bold text-text group-hover:text-brand transition-colors">Điểm gần tôi</span>
              </label>

              <label class="flex items-center gap-3 cursor-pointer group">
                <div class="relative">
                  <input :checked="publicFilters.only_recent_incidents" type="checkbox" class="peer sr-only"
                    @change="updatePublicFilters({ only_recent_incidents: $event.target.checked })" />
                  <div class="w-10 h-5 bg-bg-strong rounded-full peer-checked:bg-danger transition-all"></div>
                  <div
                    class="absolute left-1 top-1 w-3 h-3 bg-white rounded-full peer-checked:translate-x-5 transition-all shadow-sm">
                  </div>
                </div>
                <span class="text-xs font-bold text-text group-hover:text-danger transition-colors">Có sự cố gần
                  đây</span>
              </label>
            </div>

            <div class="flex items-center gap-4 bg-bg-strong/50 px-4 py-2 rounded-2xl border border-line">
              <span class="text-[10px] font-bold text-soft uppercase tracking-widest">Bán kính:</span>
              <select class="bg-transparent text-xs font-black text-text outline-none cursor-pointer"
                :value="publicFilters.radius_meters"
                @change="updatePublicFilters({ radius_meters: Number($event.target.value) || 0 })">
                <option :value="0">Không giới hạn</option>
                <option :value="1000">1 km</option>
                <option :value="2000">2 km</option>
                <option :value="3000">3 km</option>
                <option :value="5000">5 km</option>
              </select>
            </div>
          </div>
        </div>
      </section>

      <section v-else-if="isDetailRoute" class="flex items-center justify-between mb-10">
        <div class="flex items-center gap-6">
          <button @click="$router.back()"
            class="w-12 h-12 rounded-2xl bg-white border border-line text-soft flex items-center justify-center hover:bg-bg-strong transition-all shadow-sm">
            <ChevronLeft :size="24" />
          </button>
          <div>
            <h2 class="text-2xl font-black text-text tracking-tight">Chi tiết điểm giao cắt</h2>
            <p class="text-xs text-soft font-bold uppercase tracking-widest mt-1">Thông tin kỹ thuật & rủi ro</p>
          </div>
        </div>
        <div
          class="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-success-soft text-success rounded-full text-[10px] font-black tracking-wider border border-success/10">
          <span class="w-2 h-2 bg-success rounded-full animate-pulse"></span>
          DỮ LIỆU THỜI GIAN THỰC
        </div>
      </section>

      <RouterView v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-line py-12 mt-20">
      <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div class="flex flex-col md:flex-row justify-between items-center gap-8">
          <div class="flex items-center gap-3 opacity-40 grayscale hover:grayscale-0 transition-all">
            <ShieldAlert :size="24" />
            <span class="text-lg font-black tracking-tight">RailWatch</span>
          </div>
          <p class="text-xs text-soft font-medium">
            &copy; 2026 Hệ thống Giám sát An toàn Đường sắt. Phát triển bởi AIS.
          </p>
          <div class="flex gap-8">
            <a href="#"
              class="text-[10px] font-bold text-soft uppercase tracking-widest hover:text-brand transition-colors">Điều
              khoản</a>
            <a href="#"
              class="text-[10px] font-bold text-soft uppercase tracking-widest hover:text-brand transition-colors">Bảo
              mật</a>
            <a href="#"
              class="text-[10px] font-bold text-soft uppercase tracking-widest hover:text-brand transition-colors">Liên
              hệ</a>
          </div>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
@reference "../styles.css";

.nav-link {
  @apply flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-bold text-soft transition-all hover:text-text;
}

.nav-link.active {
  @apply bg-brand text-white shadow-sm;
}

.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.3s ease, transform 0.3s ease;
}

.page-fade-enter-from {
  opacity: 0;
  transform: translateY(10px);
}

.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
