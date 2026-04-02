<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const form = reactive({
  username: 'admin',
  password: 'admin123',
})
const error = ref('')
const loading = ref(false)

async function submit() {
  loading.value = true
  error.value = ''
  try {
    await login(form.username, form.password)
    router.push(route.query.next || '/admin')
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-shell">
    <div class="login-surface">
      <div class="login-brand">
        <p class="eyebrow">Khu vực quản trị</p>
        <h1>Điều hành dữ liệu với giao diện dành riêng cho quản trị</h1>
        <p>Đăng nhập để quản lý điểm giao cắt, điều phối giờ tàu và xác nhận hồ sơ sự cố.</p>
      </div>

      <section class="login-card">
        <h2>Đăng nhập quản trị</h2>
        <label class="field">
          <span>Tài khoản</span>
          <input v-model="form.username" />
        </label>
        <label class="field">
          <span>Mật khẩu</span>
          <input v-model="form.password" type="password" />
        </label>
        <button class="primary-button full-width" :disabled="loading" @click="submit">
          {{ loading ? 'Đang đăng nhập...' : 'Vào trang quản trị' }}
        </button>
        <p v-if="error" class="error-box">{{ error }}</p>
        <p class="muted-copy">Tài khoản mặc định: admin/admin123, viewer/viewer123.</p>
      </section>
    </div>
  </div>
</template>
