<script setup>
import { ShieldAlert, AlertTriangle, FileText, MapPin, Activity, TrendingUp } from 'lucide-vue-next'

defineProps({
  summary: {
    type: Object,
    required: true,
  },
})
</script>

<template>
  <div class="metrics-grid grid grid-cols-2 lg:grid-cols-4 gap-6">
    <!-- Total Crossings -->
    <div
      class="bg-white p-6 rounded-[32px] border border-line shadow-sm hover:shadow-xl hover:shadow-black/5 transition-all group">
      <div class="flex items-center justify-between mb-6">
        <div
          class="w-12 h-12 rounded-2xl bg-brand-soft text-brand flex items-center justify-center group-hover:scale-110 transition-transform">
          <MapPin :size="24" />
        </div>
        <span class="text-[10px] font-black text-soft uppercase tracking-widest">Tổng điểm</span>
      </div>
      <div>
        <div class="text-3xl font-black text-text leading-none mb-1 tracking-tighter">{{ summary.total_crossings ?? 0 }}
        </div>
        <div class="text-[10px] font-bold text-soft uppercase tracking-wider">Giao cắt đường sắt</div>
      </div>
    </div>

    <!-- Very High Risk -->
    <div
      class="bg-white p-6 rounded-[32px] border border-line shadow-sm hover:shadow-xl hover:shadow-black/5 transition-all group relative overflow-hidden">
      <div class="absolute top-0 left-0 w-1.5 h-full bg-danger"></div>
      <div class="flex items-center justify-between mb-6">
        <div
          class="w-12 h-12 rounded-2xl bg-danger-soft text-danger flex items-center justify-center group-hover:scale-110 transition-transform">
          <ShieldAlert :size="24" />
        </div>
        <span class="text-[10px] font-black text-soft uppercase tracking-widest">Rất cao</span>
      </div>
      <div>
        <div class="text-3xl font-black text-danger leading-none mb-1 tracking-tighter">{{ summary.very_high_count ?? 0
          }}</div>
        <div class="text-[10px] font-bold text-soft uppercase tracking-wider">Rủi ro rất cao</div>
      </div>
    </div>

    <!-- High Risk -->
    <div
      class="bg-white p-6 rounded-[32px] border border-line shadow-sm hover:shadow-xl hover:shadow-black/5 transition-all group relative overflow-hidden">
      <div class="absolute top-0 left-0 w-1.5 h-full bg-warning"></div>
      <div class="flex items-center justify-between mb-6">
        <div
          class="w-12 h-12 rounded-2xl bg-warning-soft text-warning flex items-center justify-center group-hover:scale-110 transition-transform">
          <AlertTriangle :size="24" />
        </div>
        <span class="text-[10px] font-black text-soft uppercase tracking-widest">Nguy hiểm</span>
      </div>
      <div>
        <div class="text-3xl font-black text-warning leading-none mb-1 tracking-tighter">{{ summary.high_count ?? 0 }}
        </div>
        <div class="text-[10px] font-bold text-soft uppercase tracking-wider">Rủi ro cao</div>
      </div>
    </div>

    <!-- Articles -->
    <div
      class="bg-white p-6 rounded-[32px] border border-line shadow-sm hover:shadow-xl hover:shadow-black/5 transition-all group">
      <div class="flex items-center justify-between mb-6">
        <div
          class="w-12 h-12 rounded-2xl bg-accent-soft text-accent flex items-center justify-center group-hover:scale-110 transition-transform">
          <FileText :size="24" />
        </div>
        <span class="text-[10px] font-black text-soft uppercase tracking-widest">Tin tức</span>
      </div>
      <div>
        <div class="text-3xl font-black text-text leading-none mb-1 tracking-tighter">{{ summary.article_count ?? 0 }}
        </div>
        <div class="text-[10px] font-bold text-soft uppercase tracking-wider">Bài viết liên quan</div>
      </div>
    </div>
  </div>
</template>
