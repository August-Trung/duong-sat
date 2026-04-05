<script setup>
import { reactive, ref } from 'vue'
import {
  Plus, Edit2, Trash2, RotateCcw,
  CheckCircle2, AlertCircle, Search,
  Database, LayoutGrid, List as ListIcon,
  ChevronRight, Loader2
} from 'lucide-vue-next'

const props = defineProps({
  title: { type: String, required: true },
  eyebrow: { type: String, required: true },
  items: { type: Array, required: true },
  emptyForm: { type: Function, required: true },
  normalize: { type: Function, required: true },
  createAction: { type: Function, required: true },
  updateAction: { type: Function, required: true },
  deleteAction: { type: Function, required: true },
  refreshAction: { type: Function, required: true },
  listKey: { type: String, required: true },
  listSubtitleKey: { type: String, required: true },
  listSubtitleFormatter: { type: Function, default: null },
  canEdit: { type: Boolean, default: true },
  canDelete: { type: Boolean, default: true },
  submitLabelCreate: { type: String, default: 'Tạo mới' },
  submitLabelUpdate: { type: String, default: 'Lưu thay đổi' },
})

const editingId = ref(null)
const error = ref('')
const busy = ref(false)
const searchQuery = ref('')
const form = reactive(props.emptyForm())

function startEdit(item) {
  editingId.value = item.id
  Object.assign(form, props.emptyForm(), item)
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function reset() {
  editingId.value = null
  Object.assign(form, props.emptyForm())
  error.value = ''
}

async function submit() {
  if (!props.canEdit) return
  busy.value = true
  error.value = ''
  try {
    const payload = props.normalize(form)
    if (editingId.value) await props.updateAction(editingId.value, payload)
    else await props.createAction(payload)
    await props.refreshAction()
    reset()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function removeRow(id) {
  if (!props.canDelete) return
  if (!confirm('Xóa bản ghi này?')) return
  busy.value = true
  try {
    await props.deleteAction(id)
    await props.refreshAction()
    if (editingId.value === id) reset()
  } finally {
    busy.value = false
  }
}

function subtitleText(item) {
  const value = item[props.listSubtitleKey]
  return props.listSubtitleFormatter ? props.listSubtitleFormatter(value, item) : value
}

const filteredItems = computed(() => {
  if (!searchQuery.value) return props.items
  const q = searchQuery.value.toLowerCase()
  return props.items.filter(item => {
    const main = String(item[props.listKey] || '').toLowerCase()
    const sub = String(item[props.listSubtitleKey] || '').toLowerCase()
    return main.includes(q) || sub.includes(q)
  })
})

import { computed } from 'vue'
</script>

<template>
  <div class="entity-crud-panel space-y-8">
    <!-- Header Card -->
    <div
      class="bg-white p-8 rounded-3xl border border-line shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
      <div class="flex items-center gap-5">
        <div class="w-14 h-14 rounded-2xl bg-brand-soft text-brand flex items-center justify-center shadow-inner">
          <Database :size="28" />
        </div>
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span class="px-2 py-0.5 bg-brand-soft text-brand text-[10px] font-bold rounded uppercase tracking-wider">{{
              eyebrow }}</span>
            <span class="w-1 h-1 bg-soft rounded-full"></span>
            <span class="text-soft text-xs font-medium">{{ items.length }} bản ghi</span>
          </div>
          <h1 class="text-2xl font-bold text-text">{{ title }}</h1>
        </div>
      </div>

      <div class="relative w-full md:w-72">
        <Search class="absolute left-4 top-1/2 -translate-y-1/2 text-soft" :size="18" />
        <input v-model="searchQuery" type="text" placeholder="Tìm kiếm nhanh..."
          class="w-full pl-11 pr-4 py-3 bg-bg-strong text-text placeholder:text-soft border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <!-- Form Section -->
      <div
        class="lg:col-span-5 bg-white rounded-3xl border border-line shadow-sm overflow-hidden sticky top-[var(--header-height)]">
        <div class="p-6 border-b border-line flex items-center justify-between bg-bg-strong/30">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-white text-brand flex items-center justify-center shadow-sm">
              <Plus v-if="!editingId" :size="20" />
              <Edit2 v-else :size="20" />
            </div>
            <h3 class="font-bold text-text">{{ editingId ? 'Chỉnh sửa bản ghi' : 'Tạo bản ghi mới' }}</h3>
          </div>
          <button v-if="editingId" @click="reset"
            class="p-2 text-soft hover:text-brand hover:bg-brand-soft rounded-lg transition-all">
            <RotateCcw :size="18" />
          </button>
        </div>

        <div class="p-8 space-y-6">
          <slot name="form" :form="form" />

          <div v-if="error" class="p-4 bg-danger-soft border border-danger/10 rounded-2xl flex items-start gap-3">
            <AlertCircle class="text-danger shrink-0 mt-0.5" :size="18" />
            <p class="text-xs font-medium text-danger leading-relaxed">{{ error }}</p>
          </div>

          <div class="flex items-center gap-3 pt-4">
            <button
              class="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-brand text-white rounded-2xl font-bold hover:bg-brand-dark transition-all shadow-lg shadow-brand/20 disabled:opacity-50"
              :disabled="busy || !canEdit" @click="submit">
              <Loader2 v-if="busy" :size="18" class="animate-spin" />
              <CheckCircle2 v-else :size="18" />
              {{ busy ? 'Đang xử lý...' : editingId ? submitLabelUpdate : submitLabelCreate }}
            </button>
            <button
              class="px-6 py-3 bg-bg-strong text-text rounded-2xl font-bold hover:bg-line transition-all disabled:opacity-50"
              :disabled="busy" @click="reset">
              Hủy
            </button>
          </div>
        </div>
      </div>

      <!-- List Section -->
      <div class="lg:col-span-7 bg-white rounded-3xl border border-line shadow-sm overflow-hidden">
        <div class="p-6 border-b border-line flex items-center justify-between">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-bg-strong text-soft flex items-center justify-center">
              <ListIcon :size="20" />
            </div>
            <h3 class="font-bold text-text">Danh sách dữ liệu</h3>
          </div>
          <span class="text-xs font-bold text-soft uppercase tracking-wider">{{ filteredItems.length }} kết quả</span>
        </div>

        <div class="divide-y divide-line max-h-[700px] overflow-y-auto custom-scrollbar">
          <div v-if="!filteredItems.length" class="flex flex-col items-center justify-center py-20 text-center">
            <div class="w-16 h-16 rounded-full bg-bg-strong flex items-center justify-center mb-4">
              <Search :size="32" class="text-soft/40" />
            </div>
            <p class="text-soft font-bold">Không tìm thấy bản ghi nào phù hợp</p>
          </div>

          <article v-for="item in filteredItems" :key="item.id"
            class="p-6 hover:bg-bg-strong/50 transition-all group flex items-center justify-between gap-4">
            <div class="flex-1 min-w-0">
              <h4 class="font-bold text-text group-hover:text-brand transition-colors truncate">{{ item[listKey] }}</h4>
              <p class="text-xs text-soft mt-1 truncate">{{ subtitleText(item) || 'Chưa có thông tin bổ sung' }}</p>
            </div>

            <div class="flex items-center gap-2 opacity-70 group-hover:opacity-100 transition-opacity">
              <button class="p-2.5 text-soft hover:text-brand hover:bg-brand-soft rounded-xl transition-all"
                :disabled="!canEdit" @click="startEdit(item)" title="Chỉnh sửa">
                <Edit2 :size="18" />
              </button>
              <button class="p-2.5 text-soft hover:text-danger hover:bg-danger-soft rounded-xl transition-all"
                :disabled="!canDelete" @click="removeRow(item.id)" title="Xóa">
                <Trash2 :size="18" />
              </button>
              <div class="w-px h-4 bg-line mx-1"></div>
              <ChevronRight :size="18" class="text-soft/60" />
            </div>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.entity-crud-panel,
.entity-crud-panel :is(h1, h2, h3, h4, p, span, label, option) {
  color: var(--text);
}

.entity-crud-panel :is(input, select, textarea) {
  color: var(--text);
  -webkit-text-fill-color: var(--text);
}

.entity-crud-panel :is(input, select, textarea)::placeholder {
  color: var(--text-soft);
  opacity: 1;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 10px;
}
</style>
