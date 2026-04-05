<template>
  <div class="admin-users space-y-8">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div class="bg-white p-8 rounded-3xl border border-line shadow-sm flex items-center gap-6">
        <div class="w-16 h-16 rounded-2xl bg-brand-soft text-brand flex items-center justify-center shadow-inner">
          <User :size="32" />
        </div>
        <div>
          <h3 class="text-2xl font-bold text-text">{{ users.length }} Tài khoản</h3>
          <p class="text-soft text-sm font-medium">Quản lý truy cập và phân quyền hệ thống nội bộ.</p>
        </div>
      </div>

      <div class="bg-white p-8 rounded-3xl border border-line shadow-sm grid grid-cols-4 gap-4">
        <div class="text-center">
          <p class="text-[10px] font-bold text-soft uppercase tracking-wider mb-1">Admin</p>
          <p class="text-xl font-bold text-text">{{ roleSummary.admin }}</p>
        </div>
        <div class="text-center">
          <p class="text-[10px] font-bold text-soft uppercase tracking-wider mb-1">Editor</p>
          <p class="text-xl font-bold text-text">{{ roleSummary.editor }}</p>
        </div>
        <div class="text-center">
          <p class="text-[10px] font-bold text-soft uppercase tracking-wider mb-1">Reviewer</p>
          <p class="text-xl font-bold text-text">{{ roleSummary.reviewer }}</p>
        </div>
        <div class="text-center">
          <p class="text-[10px] font-bold text-soft uppercase tracking-wider mb-1">Viewer</p>
          <p class="text-xl font-bold text-text">{{ roleSummary.viewer }}</p>
        </div>
      </div>
    </div>

    <EntityCrudPanel title="Danh sách người dùng" eyebrow="Phân quyền truy cập" :items="users" :empty-form="emptyForm"
      :normalize="normalize" :create-action="createUser" :update-action="updateUser" :delete-action="deleteBlocked"
      :refresh-action="loadAdminOverview" list-key="full_name" list-subtitle-key="role"
      :list-subtitle-formatter="roleLabel" submit-label-create="Tạo người dùng" submit-label-update="Cập nhật quyền"
      :can-delete="false">
      <template #form="{ form }">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div class="space-y-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tên đăng nhập</label>
            <input v-model="form.username"
              class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
              placeholder="VD: admin_01" />
          </div>

          <div class="space-y-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Họ và tên</label>
            <input v-model="form.full_name"
              class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
              placeholder="VD: Nguyễn Văn A" />
          </div>

          <div class="space-y-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Vai trò hệ thống</label>
            <select v-model="form.role"
              class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none appearance-none">
              <option value="admin">Quản trị hệ thống</option>
              <option value="editor">Biên tập dữ liệu</option>
              <option value="reviewer">Kiểm duyệt dữ liệu</option>
              <option value="viewer">Chỉ xem</option>
            </select>
          </div>

          <div class="space-y-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Mật khẩu (để trống nếu không
              đổi)</label>
            <input v-model="form.password" type="password"
              class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
              placeholder="••••••••" />
          </div>

          <div class="space-y-2 md:col-span-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Trạng thái tài khoản</label>
            <select v-model="form.is_active"
              class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none appearance-none">
              <option :value="true">Đang hoạt động</option>
              <option :value="false">Ngừng hoạt động</option>
            </select>
          </div>
        </div>
      </template>
    </EntityCrudPanel>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { User, Shield, Users, Lock } from 'lucide-vue-next'
import EntityCrudPanel from '../shared/EntityCrudPanel.vue'
import { adminState, loadAdminOverview } from '../stores/adminData'
import { createUser, updateUser } from '../api'

function emptyForm() {
  return {
    username: '',
    full_name: '',
    role: 'viewer',
    password: '',
    is_active: true,
  }
}

function normalize(form) {
  return {
    ...form,
    password: form.password || undefined,
  }
}

function roleLabel(value) {
  return {
    admin: 'Quản trị hệ thống',
    editor: 'Biên tập dữ liệu',
    reviewer: 'Kiểm duyệt dữ liệu',
    viewer: 'Chỉ xem',
  }[value] || value
}

const users = computed(() => adminState.overview.users || [])

const roleSummary = computed(() => ({
  admin: users.value.filter((item) => item.role === 'admin').length,
  editor: users.value.filter((item) => item.role === 'editor').length,
  reviewer: users.value.filter((item) => item.role === 'reviewer').length,
  viewer: users.value.filter((item) => item.role === 'viewer').length,
}))

async function deleteBlocked() {
  throw new Error('Chưa hỗ trợ xóa người dùng. Hãy chuyển trạng thái sang ngừng hoạt động.')
}
</script>
