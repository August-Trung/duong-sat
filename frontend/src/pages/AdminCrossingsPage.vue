<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import {
  Plus, Search, Filter, MoreVertical,
  Edit2, Trash2, Eye, Check, X,
  Upload, Image as ImageIcon, FileJson,
  ChevronLeft, ChevronRight, Maximize2,
  Star, ArrowUp, ArrowDown, Download,
  MapPin, Shield, AlertTriangle, Info,
  Loader2, CheckCircle2, AlertCircle,
  Clock, User, Navigation, Camera,
  FileDown, Activity
} from 'lucide-vue-next'
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
  <div class="admin-crossings space-y-8 pb-20">
    <!-- Header & Bulk Actions -->
    <div
      class="bg-white p-8 rounded-3xl border border-line shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-6">
      <div class="flex items-center gap-5">
        <div class="w-14 h-14 rounded-2xl bg-brand-soft text-brand flex items-center justify-center shadow-inner">
          <MapPin :size="28" />
        </div>
        <div>
          <div class="flex items-center gap-2 mb-1">
            <span
              class="px-2 py-0.5 bg-brand-soft text-brand text-[10px] font-bold rounded uppercase tracking-wider">Quản
              lý hạ tầng</span>
            <span class="w-1 h-1 bg-soft rounded-full"></span>
            <span class="text-soft text-xs font-medium">{{ rows.length }} điểm giao cắt</span>
          </div>
          <h1 class="text-2xl font-bold text-text">Danh mục điểm giao cắt</h1>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-3">
        <div class="flex items-center bg-bg-strong rounded-2xl p-1 border border-line/50">
          <select v-model="bulkAction"
            class="bg-transparent text-xs font-bold px-4 py-2 outline-none border-r border-line">
            <option value="set_verification_status">Đổi trạng thái</option>
            <option value="assign_manager">Gán quản lý</option>
            <option value="export_csv">Xuất CSV</option>
            <option v-if="canDelete" value="soft_delete">Ẩn bản ghi</option>
          </select>

          <template v-if="bulkAction === 'set_verification_status'">
            <select v-model="bulkValue" class="bg-transparent text-xs font-bold px-4 py-2 outline-none">
              <option value="draft">Bản nháp</option>
              <option value="surveyed">Đã khảo sát</option>
              <option value="verified">Đã xác minh</option>
            </select>
          </template>
          <template v-else-if="bulkAction === 'assign_manager'">
            <input v-model="bulkValue" placeholder="Tên..."
              class="bg-transparent text-xs font-bold px-4 py-2 outline-none w-32" />
          </template>
        </div>

        <button
          class="flex items-center gap-2 px-5 py-2.5 bg-brand text-white rounded-xl font-bold text-sm hover:bg-brand-dark transition-all shadow-lg shadow-brand/20 disabled:opacity-50"
          :disabled="!selectedIds.length" @click="applyBulkAction">
          <Check :size="18" />
          Áp dụng ({{ selectedIds.length }})
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <!-- List Section -->
      <div
        class="lg:col-span-5 bg-white rounded-3xl border border-line shadow-sm overflow-hidden flex flex-col max-h-[800px]">
        <div class="p-6 border-b border-line flex items-center justify-between bg-bg-strong/30">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-white text-brand flex items-center justify-center shadow-sm">
              <ListIcon :size="20" />
            </div>
            <h3 class="font-bold text-text">Danh sách điểm</h3>
          </div>
          <div class="relative">
            <Search class="absolute left-3 top-1/2 -translate-y-1/2 text-soft" :size="14" />
            <input type="text" placeholder="Lọc nhanh..."
              class="pl-9 pr-4 py-2 bg-white border border-line rounded-xl text-xs font-medium outline-none focus:border-brand/20 transition-all w-40" />
          </div>
        </div>

        <div class="flex-1 overflow-y-auto custom-scrollbar divide-y divide-line">
          <article v-for="item in rows" :key="item.id"
            class="p-4 hover:bg-bg-strong/50 transition-all group flex items-center gap-4"
            :class="{ 'bg-brand-soft/20': selectedProfile?.id === item.id }">
            <div class="shrink-0">
              <input :checked="selectedIds.includes(item.id)" type="checkbox"
                class="w-5 h-5 rounded-lg border-line text-brand focus:ring-brand transition-all cursor-pointer"
                @change="toggleSelection(item.id)" />
            </div>

            <div class="flex-1 min-w-0 cursor-pointer" @click="loadProfile(item.id)">
              <h4 class="font-bold text-text group-hover:text-brand transition-colors truncate">{{ item.name }}</h4>
              <div class="flex items-center gap-2 mt-1">
                <span class="text-[10px] font-bold text-soft font-mono">#{{ item.code }}</span>
                <span class="w-1 h-1 bg-line rounded-full"></span>
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider" :class="{
                  'bg-brand-soft text-brand': item.verification_status === 'verified',
                  'bg-warning-soft text-warning': item.verification_status === 'surveyed',
                  'bg-bg-strong text-soft': item.verification_status === 'draft'
                }">
                  {{ verificationLabel(item.verification_status) }}
                </span>
              </div>
            </div>

            <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button @click="startEdit(item)"
                class="p-2 text-soft hover:text-brand hover:bg-brand-soft rounded-lg transition-all" title="Sửa">
                <Edit2 :size="16" />
              </button>
              <button @click="removeCrossing(item.id)"
                class="p-2 text-soft hover:text-danger hover:bg-danger-soft rounded-lg transition-all" title="Ẩn">
                <Trash2 :size="16" />
              </button>
            </div>
          </article>
        </div>
      </div>

      <!-- Form Section -->
      <div class="lg:col-span-7 bg-white rounded-3xl border border-line shadow-sm overflow-hidden">
        <div class="p-6 border-b border-line flex items-center justify-between bg-bg-strong/30">
          <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-white text-brand flex items-center justify-center shadow-sm">
              <Plus v-if="!editingId" :size="20" />
              <Edit2 v-else :size="20" />
            </div>
            <h3 class="font-bold text-text">{{ editingId ? 'Chỉnh sửa điểm giao cắt' : 'Tạo điểm mới' }}</h3>
          </div>
          <button v-if="editingId" @click="resetForm"
            class="p-2 text-soft hover:text-brand hover:bg-brand-soft rounded-lg transition-all">
            <RotateCcw :size="18" />
          </button>
        </div>

        <div class="p-8 space-y-8">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Mã điểm</label>
              <input v-model="form.code"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
                placeholder="VD: BH-001" />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tên điểm</label>
              <input v-model="form.name"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
                placeholder="VD: Đường ngang Km 1695+410" />
            </div>
            <div class="space-y-2 md:col-span-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Địa chỉ</label>
              <input v-model="form.address"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none"
                placeholder="Số nhà, tên đường..." />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Phường/Xã</label>
              <input v-model="form.ward"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Quận/Huyện</label>
              <input v-model="form.district"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Vĩ độ (Lat)</label>
              <input v-model="form.latitude" type="number" step="0.000001"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Kinh độ (Lng)</label>
              <input v-model="form.longitude" type="number" step="0.000001"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Trạng thái hồ sơ</label>
              <select v-model="form.verification_status"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none appearance-none">
                <option value="draft">Bản nháp</option>
                <option value="surveyed">Đã khảo sát</option>
                <option value="verified">Đã xác minh</option>
              </select>
            </div>
            <div class="space-y-2">
              <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Người quản lý</label>
              <input v-model="form.manager_name"
                class="w-full px-4 py-3 bg-bg-strong border-transparent focus:bg-white focus:border-brand/20 rounded-2xl text-sm font-medium transition-all outline-none" />
            </div>
          </div>

          <div class="space-y-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Chọn vị trí trên bản
              đồ</label>
            <div class="rounded-2xl overflow-hidden border border-line">
              <CoordinatePickerMap :model-value="{ latitude: form.latitude, longitude: form.longitude }"
                :crossings="rows" @update:model-value="
                  ({ latitude, longitude }) => {
                    form.latitude = latitude
                    form.longitude = longitude
                  }
                " />
            </div>
          </div>

          <div class="flex items-center gap-3 pt-4 border-t border-line">
            <button
              class="flex-1 flex items-center justify-center gap-2 px-6 py-3 bg-brand text-white rounded-2xl font-bold hover:bg-brand-dark transition-all shadow-lg shadow-brand/20 disabled:opacity-50"
              :disabled="busy || !canEdit" @click="submitForm">
              <Loader2 v-if="busy" :size="18" class="animate-spin" />
              <CheckCircle2 v-else :size="18" />
              {{ busy ? 'Đang xử lý...' : editingId ? 'Lưu thay đổi' : 'Tạo điểm mới' }}
            </button>
            <button
              class="px-6 py-3 bg-bg-strong text-text rounded-2xl font-bold hover:bg-line transition-all disabled:opacity-50"
              :disabled="busy" @click="resetForm">
              Hủy
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Profile & Gallery Section -->
    <div v-if="selectedProfile" ref="profileSectionRef" class="grid grid-cols-1 lg:grid-cols-12 gap-8">
      <div class="lg:col-span-8 bg-white rounded-3xl border border-line shadow-sm overflow-hidden">
        <div
          class="p-8 border-b border-line flex flex-col md:flex-row md:items-center justify-between gap-6 bg-bg-strong/30">
          <div class="flex items-center gap-5">
            <div class="w-14 h-14 rounded-2xl bg-white text-brand flex items-center justify-center shadow-sm">
              <Info :size="28" />
            </div>
            <div>
              <div class="flex items-center gap-2 mb-1">
                <span
                  class="px-2 py-0.5 bg-brand-soft text-brand text-[10px] font-bold rounded uppercase tracking-wider">Hồ
                  sơ chi tiết</span>
                <span class="text-soft text-xs font-bold font-mono">#{{ selectedProfile.code }}</span>
              </div>
              <h2 class="text-2xl font-bold text-text">{{ selectedProfile.name }}</h2>
            </div>
          </div>

          <div class="flex items-center gap-3">
            <button v-if="canUpload && pendingFiles.length"
              class="flex items-center gap-2 px-4 py-2 bg-brand text-white rounded-xl font-bold text-xs hover:bg-brand-dark transition-all shadow-lg shadow-brand/20"
              @click="uploadPendingFiles">
              <Upload :size="14" /> Tải {{ pendingFiles.length }} ảnh
            </button>
            <button v-if="canUpload"
              class="flex items-center gap-2 px-4 py-2 bg-white border border-line text-text rounded-xl font-bold text-xs hover:bg-bg-strong transition-all"
              @click="hiddenFileInput?.click()">
              <Plus :size="14" /> Thêm ảnh
            </button>
          </div>
        </div>

        <div class="p-8 space-y-10">
          <!-- Gallery Stage -->
          <div v-if="selectedProfileImages.length" class="space-y-6">
            <div class="relative aspect-video bg-bg-strong rounded-3xl overflow-hidden group border border-line">
              <img v-if="activeCarouselImage" :src="imageSrc(activeCarouselImage)"
                :alt="activeCarouselImage.original_name" class="w-full h-full object-cover"
                @click="openLightbox(activeCarouselImage)" />

              <div
                class="absolute inset-0 flex items-center justify-between px-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <button @click="prevCarousel"
                  class="w-10 h-10 rounded-full bg-white/90 text-text shadow-lg flex items-center justify-center hover:bg-white transition-all">
                  <ChevronLeft :size="20" />
                </button>
                <button @click="nextCarousel"
                  class="w-10 h-10 rounded-full bg-white/90 text-text shadow-lg flex items-center justify-center hover:bg-white transition-all">
                  <ChevronRight :size="20" />
                </button>
              </div>

              <div class="absolute bottom-6 left-6 right-6 flex items-center justify-between">
                <div class="px-4 py-2 bg-black/60 backdrop-blur-md rounded-xl text-white">
                  <p class="text-[10px] font-bold uppercase tracking-wider opacity-60">Tên file</p>
                  <p class="text-xs font-bold">{{ activeCarouselImage?.original_name }}</p>
                </div>
                <div class="flex items-center gap-2">
                  <button @click="setCoverImage(activeCarouselImage.id)"
                    class="p-2.5 bg-white/90 backdrop-blur-md text-text hover:text-brand rounded-xl transition-all shadow-lg"
                    title="Đặt làm ảnh bìa">
                    <Star :size="18" :class="{ 'fill-brand text-brand': activeCarouselImage?.is_cover }" />
                  </button>
                  <button @click="removeImage(activeCarouselImage.id)"
                    class="p-2.5 bg-white/90 backdrop-blur-md text-danger rounded-xl transition-all shadow-lg"
                    title="Xóa ảnh">
                    <Trash2 :size="18" />
                  </button>
                </div>
              </div>
            </div>

            <!-- Thumbnails -->
            <div class="flex items-center gap-3 overflow-x-auto pb-4 custom-scrollbar">
              <div v-for="(image, index) in selectedProfileImages" :key="image.id"
                class="shrink-0 w-24 aspect-square rounded-xl overflow-hidden border-2 cursor-pointer transition-all relative group"
                :class="index === activeCarouselIndex ? 'border-brand shadow-lg scale-105' : 'border-transparent opacity-60 hover:opacity-100'"
                @click="selectCarouselImage(index)">
                <img :src="imageSrc(image)" class="w-full h-full object-cover" />
                <div
                  class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-1">
                  <button @click.stop="moveImage(index, -1)" class="p-1 bg-white rounded text-text hover:text-brand">
                    <ArrowUp :size="12" />
                  </button>
                  <button @click.stop="moveImage(index, 1)" class="p-1 bg-white rounded text-text hover:text-brand">
                    <ArrowDown :size="12" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div v-else
            class="flex flex-col items-center justify-center py-20 text-center bg-bg-strong/50 rounded-3xl border-2 border-dashed border-line">
            <Camera :size="48" class="text-soft/40 mb-4" />
            <p class="text-soft font-bold">Chưa có ảnh hiện trường cho điểm này</p>
            <button @click="hiddenFileInput?.click()" class="mt-4 text-brand font-bold text-sm hover:underline">Tải ảnh
              ngay</button>
          </div>

          <!-- Pending Files -->
          <div v-if="pendingFiles.length" class="space-y-4">
            <div class="flex items-center justify-between">
              <h4 class="font-bold text-text flex items-center gap-2">
                <Upload :size="18" /> Ảnh chờ tải lên
              </h4>
              <button @click="releasePendingFiles" class="text-xs font-bold text-danger hover:underline">Hủy tất
                cả</button>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div v-for="image in pendingFiles" :key="image.id"
                class="relative aspect-square rounded-2xl overflow-hidden group border border-line">
                <img :src="image.previewUrl" class="w-full h-full object-cover" />
                <div
                  class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                  <button @click="removePendingFile(image.id)" class="p-2 bg-danger text-white rounded-xl shadow-lg">
                    <X :size="16" />
                  </button>
                </div>
                <div class="absolute bottom-2 left-2 right-2 px-2 py-1 bg-black/40 backdrop-blur-sm rounded-lg">
                  <p class="text-[8px] text-white font-bold truncate">{{ image.name }}</p>
                </div>
              </div>
            </div>
          </div>

          <!-- Dropzone -->
          <div v-if="canUpload"
            class="p-10 rounded-3xl border-2 border-dashed border-line bg-bg-strong/30 flex flex-col items-center justify-center text-center transition-all cursor-pointer hover:bg-bg-strong/50 hover:border-brand/20"
            :class="{ 'border-brand bg-brand-soft/20': dragActive }" @dragenter.prevent="onDragEnter"
            @dragover.prevent="dragActive = true" @dragleave="onDragLeave" @drop.prevent="onDropFiles"
            @click="hiddenFileInput?.click()">
            <div class="w-16 h-16 rounded-2xl bg-white text-brand flex items-center justify-center shadow-sm mb-4">
              <ImageIcon :size="32" />
            </div>
            <h4 class="font-bold text-text mb-1">Kéo thả ảnh vào đây</h4>
            <p class="text-soft text-xs">Hoặc bấm để chọn file từ thiết bị (Hỗ trợ JPG, PNG, WEBP)</p>
          </div>
        </div>
      </div>

      <!-- Side Info (Right) -->
      <div class="lg:col-span-4 space-y-8">
        <!-- Quality Alerts -->
        <div class="bg-white rounded-3xl border border-line shadow-sm overflow-hidden">
          <div class="p-6 border-b border-line flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-danger-soft text-danger flex items-center justify-center">
              <ShieldAlert :size="20" />
            </div>
            <h3 class="font-bold text-text">Cảnh báo dữ liệu</h3>
          </div>
          <div class="p-6 space-y-4">
            <div v-if="!selectedProfile.quality_alerts?.length"
              class="flex flex-col items-center justify-center py-8 text-center">
              <CheckCircle2 :size="32" class="text-brand/20 mb-2" />
              <p class="text-soft text-xs font-bold">Hồ sơ đạt chuẩn</p>
            </div>
            <div v-for="alert in selectedProfile.quality_alerts" :key="alert.title"
              class="p-4 bg-danger-soft/30 rounded-2xl border border-danger/10">
              <p class="text-sm font-bold text-danger mb-1">{{ alert.title }}</p>
              <p class="text-xs text-danger/70 leading-relaxed">{{ alert.detail }}</p>
            </div>
          </div>
        </div>

        <!-- Audit Logs -->
        <div class="bg-white rounded-3xl border border-line shadow-sm overflow-hidden">
          <div class="p-6 border-b border-line flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-brand-soft text-brand flex items-center justify-center">
              <Activity :size="20" />
            </div>
            <h3 class="font-bold text-text">Lịch sử thay đổi</h3>
          </div>
          <div class="p-2 max-h-[400px] overflow-y-auto custom-scrollbar">
            <div v-for="log in selectedProfile.audit_logs" :key="log.id"
              class="p-4 hover:bg-bg-strong rounded-2xl transition-all">
              <p class="text-sm font-bold text-text mb-1">{{ log.summary }}</p>
              <div class="flex items-center gap-2 text-[10px] font-bold text-soft uppercase tracking-wider">
                <span class="flex items-center gap-1">
                  <User :size="10" /> {{ log.username }}
                </span>
                <span class="w-1 h-1 bg-line rounded-full"></span>
                <span>{{ log.created_at }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Import Section -->
        <div class="bg-surface-dark rounded-3xl p-8 text-white shadow-2xl shadow-black/10">
          <div class="flex items-center gap-4 mb-6">
            <div class="w-12 h-12 rounded-2xl bg-white/10 flex items-center justify-center">
              <FileJson :size="24" class="text-brand" />
            </div>
            <div>
              <h3 class="text-xl font-bold">Import JSON</h3>
              <p class="text-white/40 text-sm">Nhập dữ liệu hàng loạt</p>
            </div>
          </div>

          <textarea v-model="importText"
            class="w-full h-32 bg-white/5 border border-white/10 rounded-2xl p-4 text-xs font-mono text-white/80 outline-none focus:border-brand/40 transition-all mb-4"
            placeholder='[{"code":"BH-001", ...}]'></textarea>

          <button @click="submitImport"
            class="w-full py-3 bg-brand text-white rounded-2xl font-bold text-sm hover:bg-brand-dark transition-all shadow-lg shadow-brand/20">
            Bắt đầu Import
          </button>

          <div v-if="importMessage"
            class="mt-4 p-3 bg-brand/20 border border-brand/30 rounded-xl text-xs font-bold text-brand text-center">
            {{ importMessage }}
          </div>
          <div v-if="importError"
            class="mt-4 p-3 bg-danger/20 border border-danger/30 rounded-xl text-xs font-bold text-danger text-center">
            {{ importError }}
          </div>
        </div>
      </div>
    </div>

    <!-- Lightbox -->
    <div v-if="lightboxImage"
      class="fixed inset-0 z-[100] bg-black/95 backdrop-blur-xl flex items-center justify-center p-6 md:p-12"
      @click.self="closeLightbox">
      <button @click="closeLightbox"
        class="absolute top-8 right-8 w-12 h-12 rounded-full bg-white/10 text-white hover:bg-white/20 transition-all flex items-center justify-center">
        <X :size="24" />
      </button>

      <div class="max-w-5xl w-full h-full flex flex-col items-center justify-center gap-8">
        <div class="relative w-full flex-1 flex items-center justify-center">
          <img :src="imageSrc(lightboxImage)" class="max-w-full max-h-full object-contain rounded-2xl shadow-2xl" />
        </div>

        <div
          class="w-full bg-white/10 backdrop-blur-md p-6 rounded-3xl border border-white/10 flex items-center justify-between">
          <div>
            <h4 class="text-white font-bold text-xl">{{ lightboxImage.original_name || lightboxImage.name }}</h4>
            <p class="text-white/40 text-sm">Tải lên bởi {{ lightboxImage.uploaded_by_name || 'Hệ thống' }}</p>
          </div>
          <div class="flex items-center gap-3">
            <button class="p-3 bg-white/10 text-white hover:bg-white/20 rounded-2xl transition-all">
              <Download :size="20" />
            </button>
            <button class="p-3 bg-white/10 text-white hover:bg-white/20 rounded-2xl transition-all">
              <Maximize2 :size="20" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <input ref="hiddenFileInput" type="file" multiple accept="image/*" class="hidden" @change="handleFileInput" />
  </div>
</template>

<style scoped>
.custom-scrollbar::-webkit-scrollbar {
  width: 4px;
  height: 4px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 10px;
}
</style>
