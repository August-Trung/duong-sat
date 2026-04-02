<script setup>
defineProps({
  summary: {
    type: Object,
    required: true,
  },
})
</script>

<template>
  <section class="metrics-ribbon">
    <article class="metric-tile">
      <span class="metric-tile__label">Điểm giao cắt</span>
      <strong class="metric-tile__value">{{ summary.total_crossings ?? 0 }}</strong>
    </article>
    <article class="metric-tile metric-tile--danger">
      <span class="metric-tile__label">Rất nguy hiểm</span>
      <strong class="metric-tile__value">{{ summary.very_high_count ?? 0 }}</strong>
    </article>
    <article class="metric-tile metric-tile--warning">
      <span class="metric-tile__label">Nguy hiểm cao</span>
      <strong class="metric-tile__value">{{ summary.high_count ?? 0 }}</strong>
    </article>
    <article class="metric-tile metric-tile--mint">
      <span class="metric-tile__label">Bài tin liên quan</span>
      <strong class="metric-tile__value">{{ summary.article_count ?? 0 }}</strong>
    </article>
  </section>
</template>
