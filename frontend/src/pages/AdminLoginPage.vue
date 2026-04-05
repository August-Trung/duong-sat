<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../stores/auth'
import { ShieldAlert, Lock, User, ArrowRight, Loader2 } from 'lucide-vue-next'

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
  <div
    class="min-h-screen bg-bg flex items-center justify-center p-4 sm:p-6 lg:p-8 font-sans selection:bg-brand/10 selection:text-brand relative overflow-hidden">
    <!-- Decorative Background -->
    <div class="absolute top-0 left-0 w-full h-full pointer-events-none overflow-hidden">
      <div class="absolute top-[-10%] right-[-10%] w-[40%] h-[40%] bg-brand/5 rounded-full blur-[120px]"></div>
      <div class="absolute bottom-[-10%] left-[-10%] w-[40%] h-[40%] bg-accent/5 rounded-full blur-[120px]"></div>
    </div>

    <div class="w-full max-w-5xl grid lg:grid-cols-2 gap-12 items-center relative z-10">
      <!-- Brand Section -->
      <div class="hidden lg:block space-y-8">
        <div class="flex items-center gap-4">
          <div
            class="w-14 h-14 rounded-2xl bg-brand text-white flex items-center justify-center shadow-xl shadow-brand/20">
            <ShieldAlert :size="32" />
          </div>
          <div>
            <h1 class="text-3xl font-black text-text tracking-tight leading-none">RailWatch</h1>
            <p class="text-xs font-bold text-soft uppercase tracking-widest mt-1">Biên Hòa Monitoring</p>
          </div>
        </div>

        <div class="space-y-6">
          <h2 class="text-5xl font-black text-text leading-[1.1] tracking-tight">
            Điều hành dữ liệu <br />
            <span class="text-brand">thông minh & an toàn</span>
          </h2>
          <p class="text-lg text-soft leading-relaxed max-w-md">
            Hệ thống quản trị tập trung cho phép kiểm soát toàn bộ mạng lưới giao cắt đường sắt,
            điều phối lịch trình và phản ứng nhanh với các sự cố thực tế.
          </p>
        </div>

        <div class="grid grid-cols-2 gap-6 pt-8">
          <div class="p-6 bg-white rounded-[32px] border border-line shadow-sm">
            <div class="text-2xl font-black text-text mb-1 tracking-tighter">100%</div>
            <div class="text-[10px] font-bold text-soft uppercase tracking-wider">Thời gian thực</div>
          </div>
          <div class="p-6 bg-white rounded-[32px] border border-line shadow-sm">
            <div class="text-2xl font-black text-text mb-1 tracking-tighter">24/7</div>
            <div class="text-[10px] font-bold text-soft uppercase tracking-wider">Hỗ trợ kỹ thuật</div>
          </div>
        </div>
      </div>

      <!-- Login Card -->
      <div class="bg-white p-8 sm:p-12 rounded-[48px] border border-line shadow-2xl shadow-black/5 space-y-10">
        <div class="space-y-2">
          <div class="lg:hidden flex items-center gap-3 mb-6">
            <div
              class="w-10 h-10 rounded-xl bg-brand text-white flex items-center justify-center shadow-lg shadow-brand/20">
              <ShieldAlert :size="24" />
            </div>
            <h1 class="text-xl font-black text-text tracking-tight">RailWatch</h1>
          </div>
          <h3 class="text-3xl font-black text-text tracking-tight">Đăng nhập</h3>
          <p class="text-sm font-medium text-soft">Vui lòng nhập thông tin quản trị viên để tiếp tục.</p>
        </div>

        <form @submit.prevent="submit" class="space-y-6">
          <div class="space-y-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Tài khoản</label>
            <div class="relative group">
              <User
                class="absolute left-4 top-1/2 -translate-y-1/2 text-soft group-focus-within:text-brand transition-colors"
                :size="20" />
              <input v-model="form.username" type="text"
                class="w-full pl-12 pr-4 py-4 rounded-2xl border border-line bg-bg-strong/30 focus:bg-white focus:ring-4 focus:ring-brand/5 focus:border-brand/20 transition-all outline-none font-bold text-text"
                placeholder="Tên đăng nhập" required />
            </div>
          </div>

          <div class="space-y-2">
            <label class="text-[10px] font-bold text-soft uppercase tracking-widest ml-1">Mật khẩu</label>
            <div class="relative group">
              <Lock
                class="absolute left-4 top-1/2 -translate-y-1/2 text-soft group-focus-within:text-brand transition-colors"
                :size="20" />
              <input v-model="form.password" type="password"
                class="w-full pl-12 pr-4 py-4 rounded-2xl border border-line bg-bg-strong/30 focus:bg-white focus:ring-4 focus:ring-brand/5 focus:border-brand/20 transition-all outline-none font-bold text-text"
                placeholder="••••••••" required />
            </div>
          </div>

          <div v-if="error"
            class="p-4 bg-danger-soft border border-danger/10 rounded-2xl flex items-center gap-3 text-danger text-sm font-bold animate-shake">
            <ShieldAlert :size="18" />
            {{ error }}
          </div>

          <button type="submit" :disabled="loading"
            class="w-full py-5 bg-brand text-white rounded-2xl font-black text-sm shadow-xl shadow-brand/20 hover:bg-brand-dark hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:hover:scale-100">
            <span v-if="!loading">Vào trang quản trị</span>
            <span v-else>Đang xác thực...</span>
            <ArrowRight v-if="!loading" :size="20" />
            <Loader2 v-else class="animate-spin" :size="20" />
          </button>
        </form>

        <div class="pt-8 border-t border-line">
          <div class="p-4 bg-bg-strong/50 rounded-2xl border border-line">
            <p class="text-[10px] font-bold text-soft uppercase tracking-widest leading-relaxed">
              Tài khoản mặc định: <br />
              <span class="text-text">admin / admin123</span> (Quản trị) <br />
              <span class="text-text">viewer / viewer123</span> (Xem dữ liệu)
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes shake {

  0%,
  100% {
    transform: translateX(0);
  }

  25% {
    transform: translateX(-4px);
  }

  75% {
    transform: translateX(4px);
  }
}

.animate-shake {
  animation: shake 0.2s ease-in-out 0s 2;
}
</style>
