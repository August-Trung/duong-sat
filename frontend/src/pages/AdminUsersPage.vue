<script setup>
import { computed } from 'vue'
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

<template>
  <section class="admin-board">
    <section class="admin-mini-grid">
      <article class="content-card user-summary-card">
        <p class="micro-label">Quản trị quyền</p>
        <h3>{{ users.length }} tài khoản nội bộ</h3>
        <p class="body-copy">
          Phân quyền theo 4 vai trò để tách rõ nhập liệu, kiểm duyệt, quản trị và chỉ xem.
        </p>
      </article>

      <article class="content-card user-role-card">
        <div class="user-role-card__grid">
          <div class="inline-stat">
            <span>Admin</span>
            <strong>{{ roleSummary.admin }}</strong>
          </div>
          <div class="inline-stat">
            <span>Editor</span>
            <strong>{{ roleSummary.editor }}</strong>
          </div>
          <div class="inline-stat">
            <span>Reviewer</span>
            <strong>{{ roleSummary.reviewer }}</strong>
          </div>
          <div class="inline-stat">
            <span>Viewer</span>
            <strong>{{ roleSummary.viewer }}</strong>
          </div>
        </div>
      </article>
    </section>

    <EntityCrudPanel
      title="Người dùng và phân quyền"
      eyebrow="Quản lý truy cập"
      :items="users"
      :empty-form="emptyForm"
      :normalize="normalize"
      :create-action="createUser"
      :update-action="updateUser"
      :delete-action="deleteBlocked"
      :refresh-action="loadAdminOverview"
      list-key="full_name"
      list-subtitle-key="role"
      :list-subtitle-formatter="roleLabel"
      submit-label-create="Tạo người dùng"
      submit-label-update="Cập nhật quyền"
      :can-delete="false"
    >
      <template #form="{ form }">
        <div class="form-grid">
          <label class="field"><span>Tài khoản</span><input v-model="form.username" /></label>
          <label class="field"><span>Họ tên</span><input v-model="form.full_name" /></label>
          <label class="field">
            <span>Vai trò</span>
            <select v-model="form.role">
              <option value="admin">Quản trị hệ thống</option>
              <option value="editor">Biên tập dữ liệu</option>
              <option value="reviewer">Kiểm duyệt dữ liệu</option>
              <option value="viewer">Chỉ xem</option>
            </select>
          </label>
          <label class="field"><span>Mật khẩu mới</span><input v-model="form.password" type="password" /></label>
          <label class="field">
            <span>Trạng thái</span>
            <select v-model="form.is_active">
              <option :value="true">Đang hoạt động</option>
              <option :value="false">Ngừng hoạt động</option>
            </select>
          </label>
        </div>
      </template>
    </EntityCrudPanel>
  </section>
</template>
