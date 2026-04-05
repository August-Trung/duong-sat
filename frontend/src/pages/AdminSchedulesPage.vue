<script setup>
import EntityCrudPanel from '../shared/EntityCrudPanel.vue'
import { adminState, loadAdminOverview } from '../stores/adminData'
import { createSchedule, deleteSchedule, updateSchedule } from '../api'
import { hasPermission } from '../stores/auth'

function emptyForm() {
  return {
    source_name: 'Admin',
    source_url: 'manual',
    route_name: 'Tuyến chính',
    direction: 'Sài Gòn - Hà Nội',
    station_name: 'Biên Hòa',
    km: '',
    train_no: '',
    pass_time: '',
    day_offset: 0,
    raw_time_text: '',
  }
}

function normalize(form) {
  return {
    ...form,
    km: form.km === '' ? null : Number(form.km),
    day_offset: Number(form.day_offset || 0),
    raw_time_text: form.raw_time_text || form.pass_time,
  }
}
</script>

<template>
  <EntityCrudPanel title="Giờ tàu" eyebrow="Quản lý lịch tàu" :items="adminState.overview.schedules"
    :empty-form="emptyForm" :normalize="normalize" :create-action="createSchedule" :update-action="updateSchedule"
    :delete-action="deleteSchedule" :refresh-action="loadAdminOverview" list-key="train_no"
    list-subtitle-key="station_name" :can-edit="hasPermission('schedules:write')"
    :can-delete="hasPermission('schedules:delete')">
    <template #form="{ form }">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Mã hiệu tàu</label>
          <input v-model="form.train_no"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="VD: SE1, SE3..." />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Giờ qua ga/điểm</label>
          <input v-model="form.pass_time"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="HH:mm (VD: 08:35)" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tên ga / Điểm dừng</label>
          <input v-model="form.station_name"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Lý trình (KM)</label>
          <input v-model="form.km" type="number" step="0.1"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tên tuyến đường</label>
          <input v-model="form.route_name"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Hướng di chuyển</label>
          <input v-model="form.direction"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="VD: Sài Gòn - Hà Nội" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Ngày cộng thêm</label>
          <input v-model="form.day_offset" type="number"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Nguồn dữ liệu</label>
          <input v-model="form.source_name"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">URL nguồn (nếu có)</label>
          <input v-model="form.source_url"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="https://..." />
        </div>
      </div>
    </template>
  </EntityCrudPanel>
</template>
