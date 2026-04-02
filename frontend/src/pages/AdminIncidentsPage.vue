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
  <EntityCrudPanel
    title="Sự cố"
    eyebrow="Quản lý sự cố"
    :items="adminState.overview.incidents"
    :empty-form="emptyForm"
    :normalize="normalize"
    :create-action="createIncident"
    :update-action="updateIncident"
    :delete-action="deleteIncident"
    :refresh-action="loadAdminOverview"
    list-key="title"
    list-subtitle-key="crossing_name"
    :can-edit="hasPermission('incidents:write')"
    :can-delete="hasPermission('incidents:delete')"
  >
    <template #form="{ form }">
      <div class="form-grid">
        <label class="field">
          <span>Điểm giao cắt</span>
          <select v-model="form.crossing_id">
            <option value="">Không gắn điểm</option>
            <option v-for="item in adminState.overview.crossings" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select>
        </label>
        <label class="field"><span>Tiêu đề</span><input v-model="form.title" /></label>
        <label class="field"><span>Ngày sự cố</span><input v-model="form.incident_date" type="date" /></label>
        <label class="field">
          <span>Mức độ</span>
          <select v-model="form.severity_level">
            <option value="very_high">Rất cao</option>
            <option value="high">Cao</option>
            <option value="medium">Trung bình</option>
            <option value="low">Thấp</option>
          </select>
        </label>
        <label class="field"><span>Tử vong</span><input v-model="form.casualties" type="number" min="0" /></label>
        <label class="field"><span>Bị thương</span><input v-model="form.injured_count" type="number" min="0" /></label>
        <label class="field field-wide"><span>Mô tả</span><textarea v-model="form.description"></textarea></label>
        <label class="field field-wide"><span>URL nguồn</span><input v-model="form.source_url" /></label>
      </div>
    </template>
  </EntityCrudPanel>
</template>
