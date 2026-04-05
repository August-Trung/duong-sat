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
  <EntityCrudPanel title="Bài viết" eyebrow="Gán bài viết theo điểm giao cắt" :items="adminState.overview.articles || []"
    :empty-form="emptyForm" :normalize="normalize" :create-action="createArticle" :update-action="updateArticle"
    :delete-action="deleteArticle" :refresh-action="loadAdminOverview" list-key="title"
    list-subtitle-key="crossing_name" :list-subtitle-formatter="subtitleText"
    :can-edit="hasPermission('articles:write')" :can-delete="hasPermission('articles:delete')"
    submit-label-create="Tạo bài viết" submit-label-update="Lưu gán bài viết">
    <template #form="{ form }">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Điểm giao cắt liên quan</label>
          <select v-model="form.crossing_id"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none appearance-none">
            <option value="">Chưa gán điểm</option>
            <option v-for="item in adminState.overview.crossings" :key="item.id" :value="item.id">
              {{ item.name }} ({{ item.code }})
            </option>
          </select>
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tiêu đề bài viết</label>
          <input v-model="form.title"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="Nhập tiêu đề..." />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Nguồn tin</label>
          <input v-model="form.source_name"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Nhà xuất bản</label>
          <input v-model="form.publisher"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">URL bài gốc</label>
          <input v-model="form.url"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="https://..." />
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Ảnh đại diện (URL)</label>
          <input v-model="form.image_url"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
            placeholder="https://..." />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Ngày xuất bản</label>
          <input v-model="form.published_at" type="date"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Điểm mức độ (0-10)</label>
          <input v-model="form.severity_score" type="number" min="0" max="10"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
        </div>

        <div class="space-y-2 md:col-span-2">
          <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tóm tắt nội dung</label>
          <textarea v-model="form.summary" rows="4"
            class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none resize-none"
            placeholder="Nhập tóm tắt..."></textarea>
        </div>
      </div>
    </template>
  </EntityCrudPanel>
</template>
