<script setup>
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { logout, authState, hasPermission } from '../stores/auth'
import { adminState, loadAdminOverview } from '../stores/adminData'

const route = useRoute()
const router = useRouter()
const currentUser = computed(() => authState.user)
const canManageUsers = computed(() => hasPermission('users:manage'))

onMounted(async () => {
  await loadAdminOverview()
})

async function handleLogout() {
  await logout()
  router.push('/admin/login')
}
</script>

<template>
  <div class="admin-shell admin-shell--modern">
    <aside class="admin-sidebar admin-sidebar--modern">
      <div class="admin-brand">
        <div class="brand-mark">RW</div>
        <div>
          <p class="micro-label">Khu điều hành nội bộ</p>
          <h1>RailWatch Admin</h1>
        </div>
      </div>

      <p class="body-copy">
        Quản trị dữ liệu điểm giao cắt, lịch tàu và sự cố với bố cục tập trung vào thao tác nhanh.
      </p>

      <nav class="admin-nav">
        <RouterLink class="nav-pill nav-pill--block" :class="{ active: route.name === 'admin-dashboard' }" to="/admin">
          Tổng quan
        </RouterLink>
        <RouterLink
          class="nav-pill nav-pill--block"
          :class="{ active: route.name === 'admin-crossings' }"
          to="/admin/crossings"
        >
          Điểm giao cắt
        </RouterLink>
        <RouterLink
          class="nav-pill nav-pill--block"
          :class="{ active: route.name === 'admin-schedules' }"
          to="/admin/schedules"
        >
          Giờ tàu
        </RouterLink>
        <RouterLink
          class="nav-pill nav-pill--block"
          :class="{ active: route.name === 'admin-incidents' }"
          to="/admin/incidents"
        >
          Sự cố
        </RouterLink>
        <RouterLink
          v-if="canManageUsers"
          class="nav-pill nav-pill--block"
          :class="{ active: route.name === 'admin-users' }"
          to="/admin/users"
        >
          Người dùng
        </RouterLink>
        <RouterLink class="nav-pill nav-pill--block nav-pill--ghost" to="/">
          Xem giao diện công khai
        </RouterLink>
      </nav>

      <section class="content-card admin-profile-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Tài khoản</p>
            <h3>{{ currentUser?.full_name || 'Quản trị viên' }}</h3>
          </div>
          <span class="soft-badge soft-badge--accent">{{ currentUser?.role || 'admin' }}</span>
        </div>
        <p class="body-copy">{{ currentUser?.username }}</p>
        <div class="hero-inline-stats">
          <span class="soft-badge">{{ adminState.overview.crossings?.length || 0 }} hồ sơ</span>
          <span class="soft-badge">{{ adminState.overview.incidents?.length || 0 }} sự cố</span>
        </div>
        <button class="primary-button" type="button" @click="handleLogout">Đăng xuất</button>
      </section>
    </aside>

    <main class="admin-main admin-main--modern">
      <header class="content-card admin-header-card">
        <div class="section-head">
          <div>
            <p class="micro-label">Quản trị dữ liệu</p>
            <h2>Điều hành điểm giao cắt, giờ tàu và sự cố</h2>
          </div>
          <span v-if="adminState.loading" class="soft-badge">Đang đồng bộ dữ liệu...</span>
          <span v-else class="soft-badge soft-badge--accent">Khu vực chỉ dành cho quản trị</span>
        </div>
      </header>

      <RouterView />
    </main>
  </div>
</template>
