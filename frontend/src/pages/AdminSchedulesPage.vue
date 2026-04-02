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
  <EntityCrudPanel
    title="Giờ tàu"
    eyebrow="Quản lý lịch tàu"
    :items="adminState.overview.schedules"
    :empty-form="emptyForm"
    :normalize="normalize"
    :create-action="createSchedule"
    :update-action="updateSchedule"
    :delete-action="deleteSchedule"
    :refresh-action="loadAdminOverview"
    list-key="train_no"
    list-subtitle-key="station_name"
    :can-edit="hasPermission('schedules:write')"
    :can-delete="hasPermission('schedules:delete')"
  >
    <template #form="{ form }">
      <div class="form-grid">
        <label class="field"><span>Tên tuyến</span><input v-model="form.route_name" /></label>
        <label class="field"><span>Hướng</span><input v-model="form.direction" /></label>
        <label class="field"><span>Ga</span><input v-model="form.station_name" /></label>
        <label class="field"><span>Mã tàu</span><input v-model="form.train_no" /></label>
        <label class="field"><span>Giờ qua</span><input v-model="form.pass_time" placeholder="08:35" /></label>
        <label class="field"><span>KM</span><input v-model="form.km" type="number" /></label>
        <label class="field"><span>Ngày cộng thêm</span><input v-model="form.day_offset" type="number" /></label>
        <label class="field"><span>Nguồn</span><input v-model="form.source_name" /></label>
        <label class="field field-wide"><span>URL nguồn</span><input v-model="form.source_url" /></label>
      </div>
    </template>
  </EntityCrudPanel>
</template>
