<script setup>
import L from 'leaflet'
import { onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Object,
    required: true,
  },
  crossings: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['update:modelValue'])
const mapRoot = ref(null)
let map
let markers
let selectedMarker

onMounted(() => {
  map = L.map(mapRoot.value, { zoomControl: false }).setView([10.95, 106.84], 12)
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors',
  }).addTo(map)
  L.control.zoom({ position: 'topright' }).addTo(map)
  markers = L.layerGroup().addTo(map)
  selectedMarker = L.layerGroup().addTo(map)
  map.on('click', (event) => {
    emit('update:modelValue', {
      latitude: Number(event.latlng.lat.toFixed(6)),
      longitude: Number(event.latlng.lng.toFixed(6)),
    })
  })
  render()
})

watch(
  () => [props.crossings, props.modelValue],
  () => {
    if (!map) return
    render()
  },
  { deep: true }
)

function render() {
  markers.clearLayers()
  selectedMarker.clearLayers()

  props.crossings.forEach((item) => {
    if (!item.latitude || !item.longitude) return
    L.circleMarker([item.latitude, item.longitude], {
      radius: 4,
      color: '#2563eb',
      weight: 1,
      fillColor: '#60a5fa',
      fillOpacity: 0.55,
    })
      .bindTooltip(item.name)
      .addTo(markers)
  })

  if (props.modelValue.latitude && props.modelValue.longitude) {
    L.marker([props.modelValue.latitude, props.modelValue.longitude]).addTo(selectedMarker)
    map.setView([props.modelValue.latitude, props.modelValue.longitude], Math.max(map.getZoom(), 14))
  }
}
</script>

<template>
  <div ref="mapRoot" class="picker-map-root"></div>
</template>
