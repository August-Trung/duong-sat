<script setup>
import EntityCrudPanel from '../shared/EntityCrudPanel.vue'
import { adminState, loadAdminOverview } from '../stores/adminData'
import { createIncident, deleteIncident, updateIncident } from '../api'
import { hasPermission } from '../stores/auth'

function emptyForm() {
  return {
    crossing_id: '',
    title: '',
    incident_date: '',
    severity_level: 'high',
    casualties: 0,
    injured_count: 0,
    description: '',
    source_url: '',
  }
}

function normalize(form) {
  return {
    ...form,
    crossing_id: form.crossing_id === '' ? null : Number(form.crossing_id),
    casualties: Number(form.casualties || 0),
    injured_count: Number(form.injured_count || 0),
  }
}
</script>

<template>
  <EntityCrudPanel title="Sự cố" eyebrow="Quản lý sự cố" :items="adminState.overview.incidents" :empty-form="emptyForm"
    :normalize="normalize" :create-action="createIncident" :update-action="updateIncident"
    :delete-action="deleteIncident" :refresh-action="loadAdminOverview" list-key="title"
    list-subtitle-key="crossing_name" :can-edit="hasPermission('incidents:write')"
    :can-delete="hasPermission('incidents:delete')">
    <template #form="{ form }">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Điểm giao cắt liên quan</label>
          <select v-model="form.crossing_id"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none appearance-none">
            <option value="">Không gắn điểm</option>
            <option v-for="item in adminState.overview.crossings" :key="item.id" :value="item.id">
              {{ item.name }} ({{ item.code }})
            </option>
          </select>
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tiêu đề sự cố</label>
          <input v-model="form.title"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="VD: Va chạm tàu hỏa..." />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Ngày xảy ra</label>
          <input v-model="form.incident_date" type="date"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Mức độ nghiêm trọng</label>
          <select v-model="form.severity_level"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none appearance-none">
            <option value="very_high">Rất cao</option>
            <option value="high">Cao</option>
            <option value="medium">Trung bình</option>
            <option value="low">Thấp</option>
          </select>
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Số người tử vong</label>
          <input v-model="form.casualties" type="number" min="0"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Số người bị thương</label>
          <input v-model="form.injured_count" type="number" min="0"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Mô tả chi tiết</label>
          <textarea v-model="form.description" rows="4"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none resize-none"
            placeholder="Nhập mô tả sự cố..."></textarea>
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">URL nguồn tin</label>
          <input v-model="form.source_url"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="https://..." />
        </div>
      </div>
    </template>
  </EntityCrudPanel>
</template>
