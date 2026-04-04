<script setup>
import EntityCrudPanel from '../shared/EntityCrudPanel.vue'
import { adminState, loadAdminOverview } from '../stores/adminData'
import { createArticle, deleteArticle, updateArticle } from '../api'
import { hasPermission } from '../stores/auth'

function emptyForm() {
  return {
    crossing_id: '',
    source_name: 'Admin',
    title: '',
    url: '',
    external_url: '',
    image_url: '',
    publisher: '',
    published_at: '',
    summary: '',
    matched_query: '',
    location_hint: '',
    severity_score: 0,
  }
}

function normalize(form) {
  return {
    ...form,
    crossing_id: form.crossing_id === '' ? null : Number(form.crossing_id),
    external_url: form.external_url || null,
    image_url: form.image_url || null,
    publisher: form.publisher || null,
    published_at: form.published_at || null,
    summary: form.summary || null,
    matched_query: form.matched_query || null,
    location_hint: form.location_hint || null,
    severity_score: Number(form.severity_score || 0),
  }
}

function subtitleText(_, item) {
  return item.crossing_name || item.publisher || item.location_hint || 'Chưa gán điểm giao cắt'
}
</script>

<template>
  <EntityCrudPanel
    title="Bài viết"
    eyebrow="Gán bài viết theo điểm giao cắt"
    :items="adminState.overview.articles"
    :empty-form="emptyForm"
    :normalize="normalize"
    :create-action="createArticle"
    :update-action="updateArticle"
    :delete-action="deleteArticle"
    :refresh-action="loadAdminOverview"
    list-key="title"
    list-subtitle-key="crossing_name"
    :list-subtitle-formatter="subtitleText"
    :can-edit="hasPermission('articles:write')"
    :can-delete="hasPermission('articles:delete')"
    submit-label-create="Tạo bài viết"
    submit-label-update="Lưu gán bài viết"
  >
    <template #form="{ form }">
      <div class="form-grid">
        <label class="field">
          <span>Điểm giao cắt</span>
          <select v-model="form.crossing_id">
            <option value="">Chưa gán điểm</option>
            <option v-for="item in adminState.overview.crossings" :key="item.id" :value="item.id">
              {{ item.name }}
            </option>
          </select>
        </label>
        <label class="field"><span>Nguồn</span><input v-model="form.source_name" /></label>
        <label class="field field-wide"><span>Tiêu đề</span><input v-model="form.title" /></label>
        <label class="field field-wide"><span>URL bài gốc</span><input v-model="form.url" /></label>
        <label class="field field-wide"><span>External URL</span><input v-model="form.external_url" /></label>
        <label class="field field-wide"><span>Ảnh đại diện</span><input v-model="form.image_url" /></label>
        <label class="field"><span>Nhà xuất bản</span><input v-model="form.publisher" /></label>
        <label class="field"><span>Published At</span><input v-model="form.published_at" /></label>
        <label class="field"><span>Matched Query</span><input v-model="form.matched_query" /></label>
        <label class="field"><span>Location Hint</span><input v-model="form.location_hint" /></label>
        <label class="field"><span>Điểm mức độ</span><input v-model="form.severity_score" type="number" min="0" /></label>
        <label class="field field-wide"><span>Tóm tắt</span><textarea v-model="form.summary"></textarea></label>
      </div>
    </template>
  </EntityCrudPanel>
</template>
