<script setup>
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard, MapPin, Train, AlertCircle,
  Users, ExternalLink, LogOut, ShieldCheck,
  Bell, Settings, Search, Menu, X, FileText,
  ChevronRight
} from 'lucide-vue-next'
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
  if (!confirm('Đăng xuất khỏi phiên quản trị hiện tại?')) return
  await logout()
  router.push('/admin/login')
}
</script>

<template>
  <div class="admin-layout flex min-h-screen bg-bg font-sans selection:bg-brand/10 selection:text-brand">
    <!-- Sidebar -->
    <aside
      class="admin-sidebar w-72 bg-surface-dark text-white flex flex-col sticky top-0 h-screen z-50 shadow-2xl shadow-black/20">
      <div class="p-8 flex items-center gap-4 border-b border-white/5">
        <div class="w-12 h-12 rounded-2xl bg-brand flex items-center justify-center shadow-xl shadow-brand/20">
          <ShieldCheck :size="28" />
        </div>
        <div>
          <h2 class="font-black text-xl leading-tight tracking-tight">RailWatch</h2>
          <p class="text-[10px] font-bold text-white/40 uppercase tracking-widest mt-0.5">Admin Control</p>
        </div>
      </div>

      <nav class="flex-1 p-6 flex flex-col gap-1 overflow-y-auto custom-scrollbar">
        <div class="px-3 mb-4">
          <span class="text-[10px] font-black text-white/40 uppercase tracking-[0.2em]">Menu chính</span>
        </div>

        <RouterLink to="/admin" class="admin-nav-item group" exact-active-class="active">
          <div
            class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors icon-container">
            <LayoutDashboard :size="18" />
          </div>
          <span class="flex-1">Tổng quan</span>
          <ChevronRight :size="14" class="opacity-0 group-hover:opacity-40 transition-opacity" />
        </RouterLink>

        <RouterLink to="/admin/crossings" class="admin-nav-item group" exact-active-class="active">
          <div
            class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors icon-container">
            <MapPin :size="18" />
          </div>
          <span class="flex-1">Điểm giao cắt</span>
          <ChevronRight :size="14" class="opacity-0 group-hover:opacity-40 transition-opacity" />
        </RouterLink>

        <RouterLink to="/admin/schedules" class="admin-nav-item group" exact-active-class="active">
          <div
            class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors icon-container">
            <Train :size="18" />
          </div>
          <span class="flex-1">Lịch trình tàu</span>
          <ChevronRight :size="14" class="opacity-0 group-hover:opacity-40 transition-opacity" />
        </RouterLink>

        <RouterLink to="/admin/incidents" class="admin-nav-item group" exact-active-class="active">
          <div
            class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors icon-container">
            <AlertCircle :size="18" />
          </div>
          <span class="flex-1">Báo cáo sự cố</span>
          <ChevronRight :size="14" class="opacity-0 group-hover:opacity-40 transition-opacity" />
        </RouterLink>

        <RouterLink to="/admin/articles" class="admin-nav-item group" exact-active-class="active">
          <div
            class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors icon-container">
            <FileText :size="18" />
          </div>
          <span class="flex-1">Bài viết & Tin tức</span>
          <ChevronRight :size="14" class="opacity-0 group-hover:opacity-40 transition-opacity" />
        </RouterLink>

        <div v-if="canManageUsers" class="mt-10 px-3 mb-4">
          <span class="text-[10px] font-black text-white/40 uppercase tracking-[0.2em]">Hệ thống</span>
        </div>

        <RouterLink v-if="canManageUsers" to="/admin/users" class="admin-nav-item group" exact-active-class="active">
          <div
            class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center group-hover:bg-white/10 transition-colors icon-container">
            <Users :size="18" />
          </div>
          <span class="flex-1">Người dùng</span>
          <ChevronRight :size="14" class="opacity-0 group-hover:opacity-40 transition-opacity" />
        </RouterLink>

        <div class="mt-auto pt-8 border-t border-white/5">
          <RouterLink to="/" class="admin-nav-item text-white/40 hover:text-white hover:bg-white/5">
            <div class="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center">
              <ExternalLink :size="18" />
            </div>
            <span>Xem trang chủ</span>
          </RouterLink>
        </div>
      </nav>

      <div class="p-6 bg-white/5 border-t border-white/5">
        <div class="flex items-center gap-4">
          <div
            class="w-12 h-12 rounded-2xl bg-brand-soft text-brand flex items-center justify-center font-black text-lg shadow-inner">
            {{ currentUser?.full_name?.charAt(0) || 'A' }}
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-black truncate tracking-tight">{{ currentUser?.full_name || 'Admin' }}</p>
            <p class="text-[10px] text-white/40 truncate uppercase font-black tracking-widest mt-0.5">{{
              currentUser?.role || 'Staff' }}</p>
          </div>
          <button @click="handleLogout"
            class="w-10 h-10 flex items-center justify-center hover:bg-danger/10 rounded-xl text-white/20 hover:text-danger transition-all">
            <LogOut :size="20" />
          </button>
        </div>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="admin-content-tone flex-1 flex flex-col min-w-0 text-text">
      <header
        class="h-20 bg-white/80 backdrop-blur-xl border-b border-line flex items-center justify-between px-10 sticky top-0 z-40">
        <div class="flex items-center gap-6">
          <h2 class="font-black text-2xl text-text tracking-tight">{{ route.meta.title || 'Bảng điều khiển' }}</h2>
          <div v-if="adminState.loading"
            class="flex items-center gap-2 px-3 py-1.5 bg-brand-soft text-brand rounded-full text-[10px] font-black tracking-wider border border-brand/10">
            <span class="w-2 h-2 bg-brand rounded-full animate-pulse"></span>
            ĐANG ĐỒNG BỘ...
          </div>
        </div>

        <div class="flex items-center gap-6">
          <div class="relative hidden md:block group">
            <Search
              class="absolute left-4 top-1/2 -translate-y-1/2 text-soft group-focus-within:text-brand transition-colors"
              :size="18" />
            <input type="text" placeholder="Tìm kiếm nhanh..."
              class="pl-12 pr-4 py-3 bg-bg-strong/50 border border-transparent rounded-2xl text-sm font-bold focus:bg-white focus:border-brand/20 focus:ring-4 focus:ring-brand/5 outline-none transition-all w-72" />
          </div>
          <div class="flex items-center gap-2">
            <button
              class="w-11 h-11 flex items-center justify-center text-soft hover:text-brand hover:bg-brand-soft rounded-2xl transition-all relative group">
              <Bell :size="22" />
              <span
                class="absolute top-3 right-3 w-2.5 h-2.5 bg-danger rounded-full border-2 border-white group-hover:scale-110 transition-transform"></span>
            </button>
            <button
              class="w-11 h-11 flex items-center justify-center text-soft hover:text-brand hover:bg-brand-soft rounded-2xl transition-all">
              <Settings :size="22" />
            </button>
          </div>
        </div>
      </header>

      <main class="p-10 flex-1 text-text">
        <RouterView v-slot="{ Component }">
          <transition name="admin-fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-nav-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-radius: 16px;
  color: rgba(255, 255, 255, 0.6);
  font-weight: 800;
  font-size: 0.8125rem;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  margin-bottom: 4px;
}

.admin-nav-item:hover {
  background-color: rgba(255, 255, 255, 0.03);
  color: rgba(255, 255, 255, 0.8);
  transform: translateX(4px);
}

.admin-nav-item.active {
  background-color: var(--brand);
  color: white;
  box-shadow: 0 10px 25px -5px rgba(15, 92, 62, 0.4);
}

.admin-nav-item.active .icon-container {
  background-color: rgba(255, 255, 255, 0.2);
}

.admin-sidebar {
  background: linear-gradient(180deg, #164232 0%, #1a4a38 100%);
  border-color: rgba(255, 255, 255, 0.06);
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 10px;
}

.admin-fade-enter-active,
.admin-fade-leave-active {
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.admin-fade-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.admin-fade-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}
</style>
