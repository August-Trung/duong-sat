<script setup>
import { computed, onMounted, reactive } from 'vue'
import Scene3DCanvas from '../components/Scene3DCanvas.vue'
import { fetchScene3DManifest } from '../api'

const state = reactive({
  loading: true,
  error: '',
  manifest: null,
})

const totals = computed(() => {
  const result = {
    crossings: 0,
    roads: 0,
    railways: 0,
    buildings: 0,
    landuse: 0,
    water: 0,
    powerlines: 0,
  }

  for (const tile of state.manifest?.tiles || []) {
    result.crossings += tile.featureCounts.crossings
    result.roads += tile.featureCounts.roads
    result.railways += tile.featureCounts.railways
    result.buildings += tile.featureCounts.buildings
    result.landuse += tile.featureCounts.landuse
    result.water += tile.featureCounts.water
    result.powerlines += tile.featureCounts.powerlines
  }

  return result
})

async function loadScene() {
  state.loading = true
  state.error = ''
  try {
    state.manifest = await fetchScene3DManifest()
  } catch (error) {
    state.error = error.message
  } finally {
    state.loading = false
  }
}

onMounted(loadScene)
</script>

<template>
  <section class="page-grid">
    <div class="section-banner scene3d-banner">
      <div>
        <p class="eyebrow">Three.js Production Scene</p>
        <h3>Scene 3D theo tile cho đường bộ, đường sắt, mặt nước, landuse và địa hình</h3>
        <p class="muted-copy">
          Trang này tải manifest trước rồi stream dần từng tile OSM và terrain theo camera.
          Giữ chuột trái để di chuyển, chuột phải để xoay. Tên đường thật sẽ được in lặp trực tiếp trên mặt đường
          ở các tuyến có tên hoặc mã đường.
        </p>
        <p v-if="state.manifest && totals.powerlines === 0" class="muted-copy">
          Dữ liệu scene hiện chưa có tuyến điện thật, nên renderer chưa thể đặt trụ điện lên bản đồ dù asset đã sẵn sàng.
        </p>
      </div>
      <div class="scene3d-stats">
        <article class="metric-card">
          <span class="metric-label">Crossings</span>
          <strong class="metric-value">{{ totals.crossings }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">Roads</span>
          <strong class="metric-value">{{ totals.roads }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">Railways</span>
          <strong class="metric-value">{{ totals.railways }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">Buildings</span>
          <strong class="metric-value">{{ totals.buildings }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">Landuse</span>
          <strong class="metric-value">{{ totals.landuse }}</strong>
        </article>
        <article class="metric-card">
          <span class="metric-label">Water</span>
          <strong class="metric-value">{{ totals.water }}</strong>
        </article>
      </div>
    </div>

    <section class="map-surface scene3d-surface">
      <div class="surface-header">
        <div>
          <p class="eyebrow">Streaming Renderer</p>
          <h3>Renderer Three.js với tile streaming, LOD và lớp OSM thật</h3>
        </div>
      </div>

      <div v-if="state.loading" class="empty-state">Đang tải manifest 3D...</div>
      <div v-else-if="state.error" class="error-box">{{ state.error }}</div>
      <template v-else>
        <Scene3DCanvas :manifest="state.manifest" />
        <div class="scene3d-footnote">
          <strong>Hiện có</strong>
          <span>DEM theo tile, building multipolygon, đường bộ, đường sắt, landuse, water và nhãn tên đường thật.</span>
          <span v-if="totals.powerlines > 0">Có dữ liệu tuyến điện để dựng trụ và dây điện.</span>
          <span v-else>Chưa có dữ liệu tuyến điện thật trong scene export hiện tại.</span>
          <span>Scene {{ state.manifest.sceneHash }}</span>
        </div>
      </template>
    </section>
  </section>
</template>
