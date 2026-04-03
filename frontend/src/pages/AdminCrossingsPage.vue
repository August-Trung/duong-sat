<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import CoordinatePickerMap from '../components/CoordinatePickerMap.vue'
import {
  bulkCrossings,
  createCrossing,
  deleteCrossing,
  deleteCrossingImage,
  fetchCrossingProfile,
  importCrossings,
  toAssetUrl,
  updateCrossing,
  updateCrossingImages,
  uploadCrossingImages,
} from '../api'
import { adminState, loadAdminOverview } from '../stores/adminData'
import { hasPermission } from '../stores/auth'

const importText = ref('')
const importError = ref('')
const importMessage = ref('')
const pageError = ref('')
const busy = ref(false)
const savingGallery = ref(false)
const selectedIds = ref([])
const bulkAction = ref('set_verification_status')
const bulkValue = ref('verified')
const selectedProfile = ref(null)
const profileLoading = ref(false)
const dragActive = ref(false)
const pendingFiles = ref([])
const lightboxImage = ref(null)
const hiddenFileInput = ref(null)
const activeCarouselIndex = ref(0)
const profileSectionRef = ref(null)

const form = reactive(emptyForm())
const editingId = ref(null)

const canEdit = computed(() => hasPermission('crossings:create') || hasPermission('crossings:update'))
const canDelete = computed(() => hasPermission('crossings:delete'))
const canUpload = computed(() => hasPermission('images:upload'))

const rows = computed(() => adminState.overview.crossings || [])
const selectedProfileImages = computed(() => selectedProfile.value?.images || [])
const activeCarouselImage = computed(() => selectedProfileImages.value[activeCarouselIndex.value] || null)

watch(selectedProfileImages, (images) => {
  if (!images.length) {
    activeCarouselIndex.value = 0
    return
  }
  if (activeCarouselIndex.value > images.length - 1) {
    activeCarouselIndex.value = 0
  }
})

function emptyForm() {
  return {
    code: '',
    name: '',
    address: '',
    ward: '',
    district: '',
    city: 'Đồng Nai',
    latitude: '',
    longitude: '',
    crossing_type: 'duong_ngang_hop_phap',
    barrier_type: 'co_gac',
    manager_name: '',
    manager_phone: '',
    verification_status: 'draft',
    coordinate_source: '',
    source_reference: '',
    verification_notes: '',
    surveyed_at: '',
    verified_at: '',
    notes: '',
  }
}

function normalize(formValue) {
  return {
    ...formValue,
    latitude: formValue.latitude === '' ? null : Number(formValue.latitude),
    longitude: formValue.longitude === '' ? null : Number(formValue.longitude),
    surveyed_at: formValue.surveyed_at || null,
    verified_at: formValue.verified_at || null,
  }
}

function verificationLabel(value) {
  return {
    draft: 'Bản nháp',
    surveyed: 'Đã khảo sát',
    verified: 'Đã xác minh',
  }[value] || value
}

function resetForm() {
  editingId.value = null
  Object.assign(form, emptyForm())
}

async function revealProfileSection() {
  await nextTick()
  profileSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadProfile(id) {
  profileLoading.value = true
  pageError.value = ''
  try {
    selectedProfile.value = await fetchCrossingProfile(id)
    activeCarouselIndex.value = 0
    await revealProfileSection()
  } catch (error) {
    pageError.value = error.message
  } finally {
    profileLoading.value = false
  }
}

function startEdit(item) {
  editingId.value = item.id
  Object.assign(form, emptyForm(), item)
  loadProfile(item.id)
}

async function submitForm() {
  if (!canEdit.value) return
  busy.value = true
  pageError.value = ''
  try {
    const payload = normalize(form)
    const result = editingId.value
      ? await updateCrossing(editingId.value, payload)
      : await createCrossing(payload)
    await loadAdminOverview()
    resetForm()
    await loadProfile(result.id)
  } catch (error) {
    pageError.value = error.message
  } finally {
    busy.value = false
  }
}

async function removeCrossing(id) {
  if (!canDelete.value || !confirm('Ẩn bản ghi này?')) return
  busy.value = true
  try {
    await deleteCrossing(id)
    await loadAdminOverview()
    if (selectedProfile.value?.id === id) {
      selectedProfile.value = null
    }
  } catch (error) {
    pageError.value = error.message
  } finally {
    busy.value = false
  }
}

function toggleSelection(id) {
  if (selectedIds.value.includes(id)) {
    selectedIds.value = selectedIds.value.filter((item) => item !== id)
  } else {
    selectedIds.value = [...selectedIds.value, id]
  }
}

async function applyBulkAction() {
  if (!selectedIds.value.length) return
  pageError.value = ''
  try {
    const result = await bulkCrossings({
      ids: selectedIds.value,
      action: bulkAction.value,
      value:
        bulkAction.value === 'assign_manager' || bulkAction.value === 'set_verification_status'
          ? bulkValue.value
          : undefined,
    })
    if (result instanceof Blob) {
      const url = URL.createObjectURL(result)
      const link = document.createElement('a')
      link.href = url
      link.download = 'crossings-selected.csv'
      link.click()
      URL.revokeObjectURL(url)
    } else {
      await loadAdminOverview()
      if (selectedProfile.value?.id) {
        await loadProfile(selectedProfile.value.id)
      }
    }
  } catch (error) {
    pageError.value = error.message
  }
}

async function submitImport() {
  importError.value = ''
  importMessage.value = ''
  try {
    const payload = JSON.parse(importText.value)
    if (!Array.isArray(payload)) {
      throw new Error('JSON import phải là một mảng bản ghi.')
    }
    const result = await importCrossings(payload)
    await loadAdminOverview()
    importMessage.value = `Đã import ${result.imported} bản ghi`
  } catch (error) {
    importError.value = error.message
  }
}

function filePreviewItem(file) {
  return {
    id: `${file.name}-${file.size}-${file.lastModified}`,
    file,
    name: file.name,
    size: file.size,
    previewUrl: URL.createObjectURL(file),
    isPending: true,
  }
}

function releasePendingFiles() {
  pendingFiles.value.forEach((item) => URL.revokeObjectURL(item.previewUrl))
  pendingFiles.value = []
}

function appendPendingFiles(fileList) {
  const next = Array.from(fileList || [])
    .filter((file) => file.type.startsWith('image/'))
    .map(filePreviewItem)

  const existingIds = new Set(pendingFiles.value.map((item) => item.id))
  pendingFiles.value = [...pendingFiles.value, ...next.filter((item) => !existingIds.has(item.id))]
}

function handleFileInput(event) {
  appendPendingFiles(event.target.files)
  event.target.value = ''
}

function onDragEnter() {
  dragActive.value = true
}

function onDragLeave(event) {
  if (!event.currentTarget.contains(event.relatedTarget)) {
    dragActive.value = false
  }
}

function onDropFiles(event) {
  dragActive.value = false
  appendPendingFiles(event.dataTransfer?.files)
}

function removePendingFile(id) {
  const current = pendingFiles.value.find((item) => item.id === id)
  if (current) {
    URL.revokeObjectURL(current.previewUrl)
  }
  pendingFiles.value = pendingFiles.value.filter((item) => item.id !== id)
}

async function uploadPendingFiles() {
  if (!selectedProfile.value?.id || !pendingFiles.value.length) return
  try {
    await uploadCrossingImages(
      selectedProfile.value.id,
      pendingFiles.value.map((item) => item.file)
    )
    releasePendingFiles()
    await loadProfile(selectedProfile.value.id)
    await loadAdminOverview()
  } catch (error) {
    pageError.value = error.message
  }
}

async function removeImage(imageId) {
  if (!selectedProfile.value?.id) return
  try {
    await deleteCrossingImage(selectedProfile.value.id, imageId)
    await loadProfile(selectedProfile.value.id)
    await loadAdminOverview()
  } catch (error) {
    pageError.value = error.message
  }
}

function openLightbox(image) {
  lightboxImage.value = image
}

function closeLightbox() {
  lightboxImage.value = null
}

function imageSrc(image) {
  return image.previewUrl || toAssetUrl(image.url)
}

function selectCarouselImage(index) {
  activeCarouselIndex.value = index
}

function moveImage(fromIndex, step) {
  if (!selectedProfile.value?.images?.length) return
  const toIndex = fromIndex + step
  if (toIndex < 0 || toIndex >= selectedProfile.value.images.length) return
  const next = [...selectedProfile.value.images]
  const [moved] = next.splice(fromIndex, 1)
  next.splice(toIndex, 0, moved)
  selectedProfile.value = { ...selectedProfile.value, images: next }
  activeCarouselIndex.value = toIndex
}

async function saveGallery(coverImageId = activeCarouselImage.value?.id || null) {
  if (!selectedProfile.value?.id) return
  savingGallery.value = true
  pageError.value = ''
  try {
    await updateCrossingImages(selectedProfile.value.id, {
      cover_image_id: coverImageId,
      items: selectedProfileImages.value.map((image, index) => ({
        id: image.id,
        sort_order: index,
      })),
    })
    await loadProfile(selectedProfile.value.id)
    await loadAdminOverview()
  } catch (error) {
    pageError.value = error.message
  } finally {
    savingGallery.value = false
  }
}

function setCoverImage(imageId) {
  saveGallery(imageId)
}

function nextCarousel() {
  if (!selectedProfileImages.value.length) return
  activeCarouselIndex.value = (activeCarouselIndex.value + 1) % selectedProfileImages.value.length
}

function prevCarousel() {
  if (!selectedProfileImages.value.length) return
  activeCarouselIndex.value =
    (activeCarouselIndex.value - 1 + selectedProfileImages.value.length) %
    selectedProfileImages.value.length
}

onBeforeUnmount(() => {
  releasePendingFiles()
})
</script>

<template>
  <section class="admin-board admin-board--crossings">
    <section class="content-card">
      <div class="section-head">
        <div>
          <p class="micro-label">Điểm giao cắt</p>
          <h3>Chi tiết điểm, thao tác hàng loạt và ảnh hiện trường</h3>
        </div>
        <span class="soft-badge soft-badge--accent">{{ rows.length }} bản ghi</span>
      </div>

      <div class="toolbar-actions">
        <label class="field field--compact">
          <span>Thao tác</span>
          <select v-model="bulkAction">
            <option value="set_verification_status">Đổi trạng thái</option>
            <option value="assign_manager">Gán người quản lý</option>
            <option value="export_csv">Xuất CSV đã chọn</option>
            <option v-if="canDelete" value="soft_delete">Ẩn bản ghi</option>
            <option v-if="canDelete" value="restore">Khôi phục</option>
          </select>
        </label>

        <label v-if="bulkAction === 'set_verification_status'" class="field field--compact">
          <span>Giá trị</span>
          <select v-model="bulkValue">
            <option value="draft">Bản nháp</option>
            <option value="surveyed">Đã khảo sát</option>
            <option value="verified">Đã xác minh</option>
          </select>
        </label>

        <label v-if="bulkAction === 'assign_manager'" class="field">
          <span>Người quản lý</span>
          <input v-model="bulkValue" placeholder="Tên người phụ trách" />
        </label>

        <button class="primary-button" @click="applyBulkAction">
          Áp dụng cho {{ selectedIds.length }} mục
        </button>
      </div>
    </section>

    <div class="admin-crossings-grid">
      <section class="content-card admin-crossings-list">
        <div class="section-head">
          <div>
            <p class="micro-label">Danh sách</p>
            <h3>Chọn điểm để xem chi tiết</h3>
          </div>
        </div>

        <div class="stack-list admin-registry admin-registry--dense">
          <article v-for="item in rows" :key="item.id" class="registry-row registry-row--compact">
            <div class="registry-row__select">
              <input
                :checked="selectedIds.includes(item.id)"
                type="checkbox"
                @change="toggleSelection(item.id)"
              />
              <div>
                <strong>{{ item.name }}</strong>
                <span>{{ item.code }} · {{ verificationLabel(item.verification_status) }}</span>
              </div>
            </div>

            <div class="toolbar-actions">
              <button class="secondary-button" @click="loadProfile(item.id)">Chi tiết</button>
              <button class="secondary-button" :disabled="!canEdit" @click="startEdit(item)">Sửa</button>
              <button
                class="secondary-button danger-text"
                :disabled="!canDelete"
                @click="removeCrossing(item.id)"
              >
                Ẩn
              </button>
            </div>
          </article>
        </div>
      </section>

      <section class="content-card admin-crossings-form">
        <div class="section-head">
          <div>
            <p class="micro-label">Biểu mẫu</p>
            <h3>{{ editingId ? 'Chỉnh sửa điểm giao cắt' : 'Tạo điểm giao cắt mới' }}</h3>
          </div>
        </div>

        <div class="form-grid">
          <label class="field"><span>Mã</span><input v-model="form.code" /></label>
          <label class="field"><span>Tên điểm</span><input v-model="form.name" /></label>
          <label class="field"><span>Địa chỉ</span><input v-model="form.address" /></label>
          <label class="field"><span>Phường</span><input v-model="form.ward" /></label>
          <label class="field"><span>Quận/Huyện</span><input v-model="form.district" /></label>
          <label class="field"><span>Tỉnh/Thành</span><input v-model="form.city" /></label>
          <label class="field"><span>Vĩ độ</span><input v-model="form.latitude" type="number" step="0.000001" /></label>
          <label class="field"><span>Kinh độ</span><input v-model="form.longitude" type="number" step="0.000001" /></label>
          <label class="field">
            <span>Trạng thái</span>
            <select v-model="form.verification_status">
              <option value="draft">Bản nháp</option>
              <option value="surveyed">Đã khảo sát</option>
              <option value="verified">Đã xác minh</option>
            </select>
          </label>
          <label class="field"><span>Người quản lý</span><input v-model="form.manager_name" /></label>
          <label class="field"><span>Nguồn tọa độ</span><input v-model="form.coordinate_source" /></label>
          <label class="field"><span>Tham chiếu</span><input v-model="form.source_reference" /></label>
          <label class="field field-wide"><span>Ghi chú xác minh</span><textarea v-model="form.verification_notes"></textarea></label>
          <label class="field field-wide"><span>Ghi chú chung</span><textarea v-model="form.notes"></textarea></label>
          <div class="field field-wide">
            <span>Chọn tọa độ trên bản đồ</span>
            <CoordinatePickerMap
              :model-value="{ latitude: form.latitude, longitude: form.longitude }"
              :crossings="rows"
              @update:model-value="
                ({ latitude, longitude }) => {
                  form.latitude = latitude
                  form.longitude = longitude
                }
              "
            />
          </div>
        </div>

        <div class="toolbar-actions">
          <button class="primary-button" :disabled="busy || !canEdit" @click="submitForm">
            {{ busy ? 'Đang xử lý...' : editingId ? 'Lưu thay đổi' : 'Tạo mới' }}
          </button>
          <button class="secondary-button" @click="resetForm">Làm lại</button>
        </div>
      </section>
    </div>

    <div ref="profileSectionRef" class="admin-crossings-grid admin-crossings-grid--profile">
      <section class="content-card admin-profile-card-large">
        <div class="section-head">
          <div>
            <p class="micro-label">Chi tiết điểm</p>
            <h3>{{ selectedProfile?.name || 'Chọn một điểm để xem chi tiết' }}</h3>
          </div>
        </div>

        <div v-if="profileLoading" class="empty-note">Đang tải hồ sơ điểm...</div>

        <template v-else-if="selectedProfile">
          <div class="admin-profile-overview">
            <div class="data-grid">
              <article class="data-card"><span>Mã</span><strong>{{ selectedProfile.code }}</strong></article>
              <article class="data-card"><span>Trạng thái</span><strong>{{ verificationLabel(selectedProfile.verification_status) }}</strong></article>
              <article class="data-card"><span>Rủi ro</span><strong>{{ selectedProfile.risk_score }} điểm</strong></article>
              <article class="data-card"><span>Người quản lý</span><strong>{{ selectedProfile.manager_name || 'Chưa có' }}</strong></article>
            </div>
          </div>

          <article class="content-block">
            <div class="section-head">
              <div>
                <p class="micro-label">Ảnh hiện trường</p>
                <h3>{{ selectedProfileImages.length + pendingFiles.length }} ảnh hiển thị</h3>
              </div>

              <div class="toolbar-actions">
                <button
                  v-if="canUpload && pendingFiles.length"
                  class="primary-button"
                  @click="uploadPendingFiles"
                >
                  Tải {{ pendingFiles.length }} ảnh
                </button>
                <button
                  v-if="canUpload && selectedProfileImages.length"
                  class="secondary-button"
                  :disabled="savingGallery"
                  @click="saveGallery()"
                >
                  {{ savingGallery ? 'Đang lưu...' : 'Lưu thứ tự ảnh' }}
                </button>
                <button
                  v-if="canUpload && pendingFiles.length"
                  class="secondary-button"
                  @click="releasePendingFiles"
                >
                  Bỏ chọn
                </button>
                <button
                  v-if="canUpload"
                  class="secondary-button"
                  type="button"
                  @click="hiddenFileInput?.click()"
                >
                  Chọn file
                </button>
              </div>
            </div>

            <input
              ref="hiddenFileInput"
              class="hidden-file-input"
              multiple
              type="file"
              accept="image/*"
              @change="handleFileInput"
            />

            <div
              v-if="canUpload"
              class="dropzone"
              :class="{ active: dragActive }"
              @dragenter.prevent="onDragEnter"
              @dragover.prevent="dragActive = true"
              @dragleave="onDragLeave"
              @drop.prevent="onDropFiles"
            >
              <strong>Kéo ảnh vào đây để tải nhiều file cùng lúc</strong>
              <span>Hoặc bấm “Chọn file” để thêm ảnh cho điểm giao cắt này.</span>
            </div>

            <div v-if="selectedProfileImages.length" class="gallery-panel">
              <div class="gallery-stage">
                <button class="gallery-stage__nav" type="button" @click="prevCarousel">&#8249;</button>
                <article class="gallery-stage__frame">
                  <img
                    v-if="activeCarouselImage"
                    :src="imageSrc(activeCarouselImage)"
                    :alt="activeCarouselImage.original_name"
                    @click="openLightbox(activeCarouselImage)"
                  />
                </article>
                <button class="gallery-stage__nav" type="button" @click="nextCarousel">&#8250;</button>
              </div>

              <div v-if="activeCarouselImage" class="gallery-stage__meta">
                <div>
                  <strong>
                    {{ activeCarouselImage.original_name }}
                    <span v-if="activeCarouselImage.is_cover" class="soft-badge">Ảnh đại diện</span>
                  </strong>
                  <span>{{ activeCarouselImage.uploaded_by_name || 'Không rõ người tải' }}</span>
                </div>
                <div class="toolbar-actions">
                  <button class="secondary-button" @click="openLightbox(activeCarouselImage)">Xem lớn</button>
                  <button
                    v-if="canUpload && !activeCarouselImage.is_cover"
                    class="secondary-button"
                    :disabled="savingGallery"
                    @click="setCoverImage(activeCarouselImage.id)"
                  >
                    Đặt làm ảnh đại diện
                  </button>
                  <button
                    class="secondary-button danger-text"
                    @click="removeImage(activeCarouselImage.id)"
                  >
                    Xóa ảnh
                  </button>
                </div>
              </div>

              <div class="gallery-strip">
                <article
                  v-for="(image, index) in selectedProfileImages"
                  :key="image.id"
                  class="gallery-thumb"
                  :class="{ active: index === activeCarouselIndex }"
                >
                  <img :src="imageSrc(image)" :alt="image.original_name" @click="selectCarouselImage(index)" />
                  <div class="gallery-thumb__meta">
                    <strong>{{ index + 1 }}</strong>
                    <span>{{ image.is_cover ? 'Đại diện' : 'Thư viện' }}</span>
                  </div>
                  <div class="gallery-thumb__actions">
                    <button class="secondary-button" :disabled="index === 0 || savingGallery" @click="moveImage(index, -1)">
                      Lên
                    </button>
                    <button
                      class="secondary-button"
                      :disabled="index === selectedProfileImages.length - 1 || savingGallery"
                      @click="moveImage(index, 1)"
                    >
                      Xuống
                    </button>
                  </div>
                </article>
              </div>
            </div>

            <div v-if="pendingFiles.length" class="content-block">
              <h4>Ảnh chờ tải lên</h4>
              <div class="image-grid image-grid--compact">
                <article
                  v-for="image in pendingFiles"
                  :key="image.id"
                  class="image-card image-card--preview"
                >
                  <img :src="image.previewUrl" :alt="image.name" @click="openLightbox(image)" />
                  <div class="image-card__meta">
                    <strong>{{ image.name }}</strong>
                    <span>{{ Math.round(image.size / 1024) }} KB</span>
                    <button class="secondary-button danger-text" @click="removePendingFile(image.id)">
                      Bỏ ảnh
                    </button>
                  </div>
                </article>
              </div>
            </div>

            <div v-if="!selectedProfileImages.length" class="empty-note">Chưa có ảnh cho điểm này.</div>
          </article>

          <div class="admin-profile-sections">
            <article class="content-block content-block--panel">
              <h4>Cảnh báo chất lượng dữ liệu</h4>
              <div class="stack-list">
                <div
                  v-for="alert in selectedProfile.quality_alerts || []"
                  :key="alert.type + alert.title"
                  class="stack-item"
                >
                  <strong>{{ alert.title }}</strong>
                  <span>{{ alert.detail }}</span>
                </div>
              </div>
            </article>

            <article class="content-block content-block--panel">
              <h4>Nhật ký thay đổi</h4>
              <div class="stack-list">
                <div v-for="log in selectedProfile.audit_logs || []" :key="log.id" class="stack-item">
                  <strong>{{ log.summary }}</strong>
                  <span>{{ log.username }} · {{ log.created_at }}</span>
                </div>
              </div>
            </article>
          </div>
        </template>
      </section>

      <section class="content-card admin-crossings-import">
        <div class="section-head">
          <div>
            <p class="micro-label">Import hàng loạt</p>
            <h3>Nhập danh sách điểm giao cắt bằng JSON</h3>
          </div>
        </div>

        <label class="field">
          <span>Dán JSON array đã chuẩn hóa</span>
          <textarea
            v-model="importText"
            class="import-box"
            placeholder='[{"code":"BH-001","name":"...","latitude":10.9,"longitude":106.8,"verification_status":"verified"}]'
          ></textarea>
        </label>

        <div class="toolbar-actions">
          <button class="primary-button" @click="submitImport">Import vào hệ thống</button>
        </div>

        <p v-if="importMessage" class="success-box">{{ importMessage }}</p>
        <p v-if="importError" class="error-box">{{ importError }}</p>
        <p v-if="pageError" class="error-box">{{ pageError }}</p>
      </section>
    </div>

    <div v-if="lightboxImage" class="lightbox" @click.self="closeLightbox">
      <button class="lightbox__close" type="button" @click="closeLightbox">Đóng</button>
      <div class="lightbox__content">
        <img
          :src="imageSrc(lightboxImage)"
          :alt="lightboxImage.name || lightboxImage.original_name"
        />
        <div class="lightbox__meta">
          <strong>{{ lightboxImage.name || lightboxImage.original_name }}</strong>
          <span v-if="lightboxImage.uploaded_by_name">{{ lightboxImage.uploaded_by_name }}</span>
        </div>
      </div>
    </div>
  </section>
</template>
