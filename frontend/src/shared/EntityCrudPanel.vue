<script setup>
import { reactive, ref } from 'vue'

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
const form = reactive(props.emptyForm())

function startEdit(item) {
  editingId.value = item.id
  Object.assign(form, props.emptyForm(), item)
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
</script>

<template>
  <section class="admin-board">
    <section class="content-card">
      <div class="section-head">
        <div>
          <p class="micro-label">{{ eyebrow }}</p>
          <h3>{{ title }}</h3>
        </div>
        <span class="soft-badge soft-badge--accent">{{ items.length }} bản ghi</span>
      </div>
    </section>

    <div class="admin-entity-grid admin-entity-grid--modern">
      <section class="content-card editor-surface">
        <div class="section-head">
          <div>
            <p class="micro-label">Biểu mẫu</p>
            <h3>{{ editingId ? 'Chỉnh sửa bản ghi' : 'Tạo bản ghi mới' }}</h3>
          </div>
        </div>

        <slot name="form" :form="form" />

        <div class="toolbar-actions">
          <button class="primary-button" :disabled="busy" @click="submit">
            {{ busy ? 'Đang xử lý...' : editingId ? submitLabelUpdate : submitLabelCreate }}
          </button>
          <button class="secondary-button" :disabled="busy" @click="reset">Làm lại</button>
        </div>

        <p v-if="error" class="error-box">{{ error }}</p>
      </section>

      <section class="content-card registry-surface">
        <div class="section-head">
          <div>
            <p class="micro-label">Dữ liệu hiện có</p>
            <h3>Danh sách bản ghi</h3>
          </div>
        </div>

        <div class="stack-list admin-registry">
          <article v-for="item in items" :key="item.id" class="registry-row">
            <div>
              <strong>{{ item[listKey] }}</strong>
              <span>{{ subtitleText(item) || 'Đang cập nhật' }}</span>
            </div>
            <div class="toolbar-actions">
              <button class="secondary-button" :disabled="!canEdit" @click="startEdit(item)">Sửa</button>
              <button class="secondary-button danger-text" :disabled="!canDelete" @click="removeRow(item.id)">Xóa</button>
            </div>
          </article>
        </div>
      </section>
    </div>
  </section>
</template>
