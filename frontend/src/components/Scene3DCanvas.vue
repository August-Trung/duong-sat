<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { MTLLoader } from 'three/examples/jsm/loaders/MTLLoader.js'
import { fetchScene3DTile } from '../api'

const MAX_TILE_CACHE = 18
const ROAD_LABEL_PRIORITY = new Set(['motorway', 'trunk', 'primary', 'secondary', 'tertiary'])

const props = defineProps({
  manifest: {
    type: Object,
    required: true,
  },
})

const root = ref(null)
const loadingState = reactive({
  activeTiles: 0,
  cachedTiles: 0,
})
const selectedFeature = ref(null)
const interactionState = reactive({
  dragging: false,
})

let renderer
let camera
let scene
let controls
let frameId = 0
let tileRoot
let pointer
let raycaster
let highlightedObject = null
let syncQueued = false
let syncInFlight = false
let pointerDownStart = null
let movedDuringPointer = false

const tileCache = new Map()
const tileGroups = new Map()
const inflightTiles = new Map()
const textureCache = new Map()
let lastTileSignature = ''
const assetLibrary = {
  ready: false,
  tower: null,
  trees: [],
}

const imageLoader = new THREE.TextureLoader()

const TILE_COLORS = {
  terrain: '#ece4d3',
  rail: '#3b434d',
  water: '#6fa7d8',
  landuse: '#8faa70',
  buildingWall: '#f3f1eb',
  buildingRoof: '#ffffff',
  roadOutline: '#ffffff',
  roadEdge: '#a1a6ab',
  roadSurface: '#7b8087',
  roadCenter: '#f6f1dc',
  roadText: '#fffdf6',
  roadTextStroke: '#1f2328',
}
const VEGETATION_KINDS = new Set(['forest', 'grass', 'meadow', 'park', 'orchard', 'scrub', 'wood'])

function metersPerDegreeLat() {
  return 111320
}

function metersPerDegreeLng(latitude) {
  return 111320 * Math.cos((latitude * Math.PI) / 180)
}

function projectPoint(longitude, latitude, elevation = 0, center) {
  const x = (longitude - center.longitude) * metersPerDegreeLng(center.latitude)
  const z = -(latitude - center.latitude) * metersPerDegreeLat()
  return new THREE.Vector3(x, elevation, z)
}

function unprojectPoint(x, z, center) {
  return {
    longitude: center.longitude + x / (metersPerDegreeLng(center.latitude) || 1),
    latitude: center.latitude - z / metersPerDegreeLat(),
  }
}

function setStaticModelProps(object) {
  object.traverse?.((child) => {
    if (child.isMesh) {
      child.castShadow = false
      child.receiveShadow = false
      if (child.material) {
        const materials = Array.isArray(child.material) ? child.material : [child.material]
        materials.forEach((material) => {
          material.transparent = material.transparent || false
          material.depthWrite = true
        })
      }
    }
  })
  return object
}

function normalizeModelHeight(object, targetHeight) {
  const bounds = new THREE.Box3().setFromObject(object)
  const size = bounds.getSize(new THREE.Vector3())
  const currentHeight = size.y || 1
  const scale = targetHeight / currentHeight
  object.scale.multiplyScalar(scale)
  object.updateMatrixWorld(true)
  const scaledBounds = new THREE.Box3().setFromObject(object)
  object.position.y -= scaledBounds.min.y
  return object
}

function cloneAsset(object) {
  return object.clone(true)
}

function loadGLTFModel(url) {
  return new Promise((resolve, reject) => {
    new GLTFLoader().load(
      url,
      (gltf) => resolve(gltf.scene),
      undefined,
      reject
    )
  })
}

function loadOBJWithMTL(baseUrl, name) {
  return new Promise((resolve, reject) => {
    const mtlLoader = new MTLLoader()
    mtlLoader.setPath(baseUrl)
    mtlLoader.load(
      `${name}.mtl`,
      (materials) => {
        materials.preload()
        const objLoader = new OBJLoader()
        objLoader.setMaterials(materials)
        objLoader.setPath(baseUrl)
        objLoader.load(
          `${name}.obj`,
          (object) => resolve(object),
          undefined,
          reject
        )
      },
      undefined,
      reject
    )
  })
}

async function loadSceneAssets() {
  if (assetLibrary.ready) return assetLibrary

  const tasks = []
  tasks.push(
    loadGLTFModel('/assets/scene3d/transmission_tower.glb')
      .then((tower) => {
        setStaticModelProps(tower)
        normalizeModelHeight(tower, 32)
        assetLibrary.tower = tower
      })
      .catch(() => {
        assetLibrary.tower = null
      })
  )

  const treeBase = '/assets/scene3d/nature_kit/Models/OBJ format/'
  const treeNames = ['tree_palmDetailedTall', 'tree_oak', 'tree_pineTallA_detailed']
  for (const treeName of treeNames) {
    tasks.push(
      loadOBJWithMTL(treeBase, treeName)
        .then((tree) => {
          setStaticModelProps(tree)
          normalizeModelHeight(tree, treeName.includes('palm') ? 14 : 11)
          assetLibrary.trees.push(tree)
        })
        .catch(() => {})
    )
  }

  await Promise.all(tasks)
  assetLibrary.ready = true
  return assetLibrary
}

function manifestFocusCenter() {
  if (!props.manifest?.tiles?.length) {
    return props.manifest?.center || { longitude: 0, latitude: 0 }
  }

  const dataTiles = props.manifest.tiles.filter((tile) =>
    ['crossings', 'roads', 'railways', 'buildings', 'landuse', 'water', 'powerlines'].some(
      (key) => (tile.featureCounts?.[key] || 0) > 0
    )
  )
  const sourceTiles = dataTiles.length ? dataTiles : props.manifest.tiles
  const bounds = sourceTiles.reduce(
    (acc, tile) => ({
      west: Math.min(acc.west, tile.bounds.west),
      south: Math.min(acc.south, tile.bounds.south),
      east: Math.max(acc.east, tile.bounds.east),
      north: Math.max(acc.north, tile.bounds.north),
    }),
    {
      west: Number.POSITIVE_INFINITY,
      south: Number.POSITIVE_INFINITY,
      east: Number.NEGATIVE_INFINITY,
      north: Number.NEGATIVE_INFINITY,
    }
  )

  return {
    longitude: (bounds.west + bounds.east) / 2,
    latitude: (bounds.south + bounds.north) / 2,
  }
}

function sampleTerrainElevation(longitude, latitude, terrain) {
  if (!terrain?.elevations?.length) return 0
  const { west, south, east, north } = terrain.bounds
  const clampedX = Math.min(1, Math.max(0, (longitude - west) / (east - west || 1)))
  const clampedY = Math.min(1, Math.max(0, (latitude - south) / (north - south || 1)))
  const col = Math.round(clampedX * (terrain.width - 1))
  const row = Math.round((1 - clampedY) * (terrain.height - 1))
  return terrain.elevations[row]?.[col] ?? 0
}

function cachedTexture(key, factory) {
  if (textureCache.has(key)) return textureCache.get(key)
  const texture = factory()
  textureCache.set(key, texture)
  return texture
}

function imageTexture(key, url, options = {}) {
  return cachedTexture(key, () => {
    const texture = imageLoader.load(url)
    texture.wrapS = options.wrapS ?? THREE.RepeatWrapping
    texture.wrapT = options.wrapT ?? THREE.RepeatWrapping
    if (options.repeat) {
      texture.repeat.set(options.repeat[0], options.repeat[1])
    }
    texture.colorSpace = THREE.SRGBColorSpace
    texture.anisotropy = 8
    return texture
  })
}

function roadLabelTexture(text) {
  return cachedTexture(`road-label:${text}`, () => {
    const canvas = document.createElement('canvas')
    const context = canvas.getContext('2d')
    canvas.width = 1024
    canvas.height = 192
    context.clearRect(0, 0, canvas.width, canvas.height)
    context.lineJoin = 'round'
    context.lineCap = 'round'
    context.font = '700 84px "Be Vietnam Pro", sans-serif'
    context.textAlign = 'center'
    context.textBaseline = 'middle'
    context.strokeStyle = TILE_COLORS.roadTextStroke
    context.lineWidth = 18
    context.strokeText(text, canvas.width / 2, canvas.height / 2)
    context.fillStyle = TILE_COLORS.roadText
    context.fillText(text, canvas.width / 2, canvas.height / 2)
    const texture = new THREE.CanvasTexture(canvas)
    texture.needsUpdate = true
    texture.anisotropy = 8
    return texture
  })
}

function grassTexture() {
  return imageTexture(
    'terrain-grass',
    '/assets/scene3d/nature_kit/Isometric/ground_grass_NE.png',
    { repeat: [52, 52] }
  )
}

function landuseTexture(kind = 'grass') {
  if (kind === 'orchard') {
    return imageTexture(
      'landuse-orchard',
      '/assets/scene3d/nature_kit/Isometric/ground_grass_SE.png',
      { repeat: [30, 30] }
    )
  }
  if (kind === 'meadow' || kind === 'grass' || kind === 'park') {
    return imageTexture(
      `landuse-${kind}`,
      '/assets/scene3d/nature_kit/Isometric/grass_NE.png',
      { repeat: [36, 36] }
    )
  }
  return grassTexture()
}

function treeBillboardTexture(kind = 'forest') {
  const spriteByKind = {
    orchard: '/assets/scene3d/nature_kit/Isometric/tree_palmDetailedTall_NE.png',
    park: '/assets/scene3d/nature_kit/Isometric/tree_oak_NE.png',
    grass: '/assets/scene3d/nature_kit/Isometric/tree_default_NE.png',
    meadow: '/assets/scene3d/nature_kit/Isometric/tree_default_NE.png',
    scrub: '/assets/scene3d/nature_kit/Isometric/tree_small_NE.png',
    wood: '/assets/scene3d/nature_kit/Isometric/tree_pineTallA_detailed_NE.png',
    forest: '/assets/scene3d/nature_kit/Isometric/tree_pineTallA_detailed_NE.png',
  }
  return imageTexture(`tree:${kind}`, spriteByKind[kind] || spriteByKind.forest, {
    repeat: [1, 1],
    wrapS: THREE.ClampToEdgeWrapping,
    wrapT: THREE.ClampToEdgeWrapping,
  })
}

function isRealRoadName(name) {
  if (!name) return false
  const normalized = name.toLowerCase()
  return !normalized.startsWith('way-') && !normalized.startsWith('road-') && !normalized.startsWith('unnamed')
}

function shouldShowRoadLabel(road, lod) {
  if (!isRealRoadName(road?.name)) return false
  if (lod === 'far') return false
  if (lod === 'mid') return ROAD_LABEL_PRIORITY.has(road.kind)
  return !['service', 'footway', 'track', 'path', 'steps', 'pedestrian'].includes(road.kind)
}

function shouldRenderRoadAtLod(road, lod) {
  if (lod === 'far') {
    return !['service', 'footway', 'track', 'path', 'steps', 'pedestrian'].includes(road.kind)
  }
  if (lod === 'mid') {
    return !['service', 'footway', 'track', 'path', 'steps', 'pedestrian'].includes(road.kind)
  }
  return true
}

function shouldRenderBuildingAtLod(lod, index) {
  if (lod === 'far') return false
  if (lod === 'mid') return index < 36
  return index < 72
}

function shouldRenderLanduseAtLod(lod) {
  return true
}

function shouldRenderWaterLabelAtLod(lod) {
  return lod === 'near'
}

function setPickMetadata(object3d, type, feature, tileId) {
  object3d.userData.pickable = true
  object3d.userData.featureType = type
  object3d.userData.feature = feature
  object3d.userData.tileId = tileId
  object3d.traverse?.((child) => {
    child.userData.pickable = true
    child.userData.featureType = type
    child.userData.feature = feature
    child.userData.tileId = tileId
  })
  return object3d
}

function tileDistanceBand(distance) {
  if (distance < 180) return 'near'
  if (distance < 420) return 'mid'
  return 'far'
}

function ringCountForDistance(distance) {
  return distance < 180 ? 1 : 1
}

function maxVisibleTiles(distance) {
  if (distance < 180) return 8
  if (distance < 420) return 9
  return 9
}

function makeLabel(anchor, text, center, terrain) {
  if (!anchor || !text) return null
  const elevation = sampleTerrainElevation(anchor.longitude, anchor.latitude, terrain) + 7
  const position = projectPoint(anchor.longitude, anchor.latitude, elevation, center)
  const texture = roadLabelTexture(text)
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false, depthTest: false })
  const width = Math.max(40, Math.min(160, text.length * 5.2))
  const sprite = new THREE.Sprite(material)
  sprite.position.copy(position)
  sprite.scale.set(width, 16, 1)
  return sprite
}

function makeLinearFeatureMesh(feature, center, terrain, options = {}) {
  const radius = options.radius ?? 1.6
  const color = options.color ?? '#6e7177'
  const tubularSegments = options.tubularSegments ?? 40
  const points = feature.centerline.map((point) =>
    projectPoint(
      point.longitude,
      point.latitude,
      sampleTerrainElevation(point.longitude, point.latitude, terrain) + (options.altitudeOffset ?? 0.2),
      center
    )
  )
  if (points.length < 2) return null
  const curve = new THREE.CatmullRomCurve3(points)
  const geometry = new THREE.TubeGeometry(curve, Math.max(tubularSegments, points.length * 4), radius, 8, false)
  return new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({
      color,
      roughness: 0.94,
      metalness: options.metalness ?? 0.02,
    })
  )
}

function makeLinearFeatureLine(feature, center, terrain, options = {}) {
  const points = feature.centerline.map((point) =>
    projectPoint(
      point.longitude,
      point.latitude,
      sampleTerrainElevation(point.longitude, point.latitude, terrain) + (options.altitudeOffset ?? 0.2),
      center
    )
  )
  if (points.length < 2) return null
  return new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineBasicMaterial({ color: options.color ?? '#4b5563', transparent: true, opacity: options.opacity ?? 1 })
  )
}

function roadVisual(road, lod) {
  const palette = {
    motorway: { surface: '#7b7f84', edge: '#e9edf2', outline: '#969ca3' },
    trunk: { surface: '#7d8286', edge: '#ebeff4', outline: '#949aa1' },
    primary: { surface: '#80858b', edge: '#eef1f5', outline: '#99a0a8' },
    secondary: { surface: '#898f95', edge: '#edf0f2', outline: '#a3a9af' },
    tertiary: { surface: '#91979e', edge: '#edf0f3', outline: '#a9afb6' },
    residential: { surface: '#969ca2', edge: '#eff2f4', outline: '#aeb4bb' },
    service: { surface: '#a4a9af', edge: '#eceff1', outline: '#b4bac0' },
    unclassified: { surface: '#989da4', edge: '#edf0f3', outline: '#acb2ba' },
  }
  const visual = palette[road.kind] || palette.unclassified
  const widthScale = lod === 'far' ? 0.62 : lod === 'mid' ? 0.82 : 1
  return {
    surfaceColor: visual.surface,
    edgeColor: visual.edge,
    outlineColor: visual.outline,
    widthScale,
  }
}

function hashString(value) {
  let hash = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index)
    hash = Math.imul(hash, 16777619)
  }
  return hash >>> 0
}

function seededRandom(seed) {
  let value = seed >>> 0
  return () => {
    value = (1664525 * value + 1013904223) >>> 0
    return value / 4294967296
  }
}

function pointInRing2D(point, ring) {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i].longitude
    const yi = ring[i].latitude
    const xj = ring[j].longitude
    const yj = ring[j].latitude
    const intersects = yi > point.latitude !== yj > point.latitude
      && point.longitude < ((xj - xi) * (point.latitude - yi)) / ((yj - yi) || 1e-9) + xi
    if (intersects) inside = !inside
  }
  return inside
}

function pointInPolygonFeature(point, feature) {
  if (!pointInRing2D(point, feature.footprint)) return false
  for (const hole of feature.holes || []) {
    if (pointInRing2D(point, hole)) return false
  }
  return true
}

function polygonGeoBounds(feature) {
  const longitudes = feature.footprint.map((point) => point.longitude)
  const latitudes = feature.footprint.map((point) => point.latitude)
  return {
    west: Math.min(...longitudes),
    east: Math.max(...longitudes),
    south: Math.min(...latitudes),
    north: Math.max(...latitudes),
  }
}

function createRibbonGeometry(points, halfWidth) {
  if (points.length < 2) return null
  const left = []
  const right = []

  for (let index = 0; index < points.length; index += 1) {
    const current = points[index]
    const prev = points[Math.max(0, index - 1)]
    const next = points[Math.min(points.length - 1, index + 1)]
    const direction = new THREE.Vector2(next.x - prev.x, next.z - prev.z)
    if (direction.lengthSq() === 0) {
      direction.set(1, 0)
    } else {
      direction.normalize()
    }
    const normal = new THREE.Vector2(-direction.y, direction.x)
    left.push(new THREE.Vector3(current.x + normal.x * halfWidth, current.y, current.z + normal.y * halfWidth))
    right.push(new THREE.Vector3(current.x - normal.x * halfWidth, current.y, current.z - normal.y * halfWidth))
  }

  const positions = []
  for (let index = 0; index < points.length - 1; index += 1) {
    const a = left[index]
    const b = right[index]
    const c = left[index + 1]
    const d = right[index + 1]
    positions.push(a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z)
    positions.push(c.x, c.y, c.z, b.x, b.y, b.z, d.x, d.y, d.z)
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
  geometry.computeVertexNormals()
  return geometry
}

function lineLength(points) {
  let total = 0
  for (let index = 1; index < points.length; index += 1) {
    total += points[index - 1].distanceTo(points[index])
  }
  return total
}

function samplePolylineMarkers(points, spacing, maxMarkers = 4) {
  if (points.length < 2) return []
  const totalLength = lineLength(points)
  if (totalLength < spacing * 0.75) return []

  const markers = []
  const startOffset = Math.min(spacing * 0.55, totalLength * 0.22)
  let target = startOffset
  let accumulated = 0

  for (let index = 1; index < points.length && markers.length < maxMarkers; index += 1) {
    const previous = points[index - 1]
    const current = points[index]
    const segmentLength = previous.distanceTo(current)
    while (target <= accumulated + segmentLength && markers.length < maxMarkers) {
      const t = (target - accumulated) / (segmentLength || 1)
      const point = previous.clone().lerp(current, t)
      const angle = Math.atan2(current.z - previous.z, current.x - previous.x)
      markers.push({ point, angle })
      target += spacing
    }
    accumulated += segmentLength
  }

  return markers
}

function makeRoadLabelPlane(text, marker) {
  const texture = roadLabelTexture(text)
  const material = new THREE.MeshBasicMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
    depthTest: true,
    alphaTest: 0.08,
    polygonOffset: true,
    polygonOffsetFactor: -2,
    polygonOffsetUnits: -2,
  })
  const width = Math.max(22, Math.min(96, text.length * 3.6))
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(width, 5.2), material)
  mesh.rotation.x = -Math.PI / 2
  mesh.rotation.z = -marker.angle
  mesh.position.copy(marker.point)
  mesh.position.y += 0.12
  mesh.renderOrder = 12
  return mesh
}

function makeRoadNameMarkers(road, points, lod) {
  if (!shouldShowRoadLabel(road, lod)) return []
  const spacing = lod === 'near' ? 85 : 130
  const maxMarkers = lod === 'near' ? 6 : 3
  return samplePolylineMarkers(points, spacing, maxMarkers)
}

function makeRoadCenterDashes(road, points) {
  if (!['motorway', 'trunk', 'primary', 'secondary'].includes(road.kind)) return null
  const markers = samplePolylineMarkers(points, 22, 28)
  if (!markers.length) return null
  const dashLength = Math.max(3.2, Math.min(6.5, (road.widthMeters || 10) * 0.42))
  const dashWidth = 0.42
  const material = new THREE.MeshBasicMaterial({ color: TILE_COLORS.roadCenter, transparent: true, opacity: 0.96 })
  const group = new THREE.Group()
  for (const marker of markers) {
    const dash = new THREE.Mesh(new THREE.PlaneGeometry(dashLength, dashWidth), material)
    dash.rotation.x = -Math.PI / 2
    dash.rotation.z = -marker.angle
    dash.position.copy(marker.point)
    dash.position.y += 0.18
    group.add(dash)
  }
  return group
}

function makeRoadRibbon(road, center, terrain, options = {}) {
  const points = road.centerline.map((point) =>
    projectPoint(
      point.longitude,
      point.latitude,
      sampleTerrainElevation(point.longitude, point.latitude, terrain) + (options.altitudeOffset ?? 0.18),
      center
    )
  )
  const widthScale = options.widthScale ?? 1
  const outlineHalfWidth = Math.max((road.widthMeters || 8) * 0.56 * widthScale, 1.2)
  const edgeHalfWidth = Math.max(outlineHalfWidth - 0.36, outlineHalfWidth * 0.92)
  const surfaceHalfWidth = Math.max(edgeHalfWidth - 0.62, edgeHalfWidth * 0.84)
  const outlineGeometry = createRibbonGeometry(points, outlineHalfWidth)
  const edgeGeometry = createRibbonGeometry(points, edgeHalfWidth)
  const surfaceGeometry = createRibbonGeometry(points, surfaceHalfWidth)
  if (!outlineGeometry || !edgeGeometry || !surfaceGeometry) return null

  const group = new THREE.Group()
  group.add(
    new THREE.Mesh(
      outlineGeometry,
      new THREE.MeshBasicMaterial({ color: options.outlineColor || TILE_COLORS.roadOutline })
    )
  )
  const edgeMesh = new THREE.Mesh(
    edgeGeometry,
    new THREE.MeshBasicMaterial({ color: options.edgeColor || TILE_COLORS.roadEdge })
  )
  edgeMesh.position.y += 0.025
  group.add(edgeMesh)

  const innerMesh = new THREE.Mesh(
    surfaceGeometry,
    new THREE.MeshBasicMaterial({ color: options.surfaceColor || TILE_COLORS.roadSurface })
  )
  innerMesh.position.y += 0.06
  group.add(innerMesh)

  const centerDashes = makeRoadCenterDashes(road, points)
  if (centerDashes) group.add(centerDashes)

  const roadLabels = makeRoadNameMarkers(road, points, options.lod || 'near')
  for (const marker of roadLabels) {
    group.add(makeRoadLabelPlane(road.name, marker))
  }

  return group
}

function makeTreeGroup(feature, center, terrain, lod) {
  if (!VEGETATION_KINDS.has(feature.kind)) return null
  if (lod === 'far') return null

  const bounds = polygonGeoBounds(feature)
  const random = seededRandom(hashString(feature.id || feature.name || feature.kind || 'landuse'))
  const samples = []
  const densityByKind = {
    forest: lod === 'near' ? 30 : 14,
    wood: lod === 'near' ? 26 : 12,
    orchard: lod === 'near' ? 22 : 10,
    park: lod === 'near' ? 18 : 9,
    meadow: lod === 'near' ? 12 : 6,
    grass: lod === 'near' ? 10 : 5,
    scrub: lod === 'near' ? 8 : 4,
  }
  const targetCount = densityByKind[feature.kind] || (lod === 'near' ? 12 : 6)
  let attempts = 0

  while (samples.length < targetCount && attempts < targetCount * 12) {
    attempts += 1
    const longitude = bounds.west + (bounds.east - bounds.west) * random()
    const latitude = bounds.south + (bounds.north - bounds.south) * random()
    const point = { longitude, latitude }
    if (pointInPolygonFeature(point, feature)) {
      samples.push(point)
    }
  }

  if (!samples.length) return null

  const group = new THREE.Group()
  const useTreeAssets = assetLibrary.trees.length > 0 && lod === 'near'
  const texture = useTreeAssets ? null : treeBillboardTexture(feature.kind)
  const spriteMaterial = useTreeAssets
    ? null
    : new THREE.SpriteMaterial({
        map: texture,
        transparent: true,
        alphaTest: 0.18,
        depthWrite: false,
      })

  for (const sample of samples) {
    const baseElevation = sampleTerrainElevation(sample.longitude, sample.latitude, terrain)
    const position = projectPoint(sample.longitude, sample.latitude, baseElevation, center)
    const scale = 0.8 + random() * 0.85
    const width = 7.5 * scale
    const height = 10.5 * scale

    if (useTreeAssets) {
      const template = assetLibrary.trees[Math.floor(random() * assetLibrary.trees.length)]
      const tree = cloneAsset(template)
      tree.position.copy(position)
      tree.rotation.y = random() * Math.PI * 2
      tree.scale.multiplyScalar(scale)
      group.add(tree)
    } else {
      const sprite = new THREE.Sprite(spriteMaterial)
      sprite.position.copy(position)
      sprite.position.y += height * 0.46
      sprite.scale.set(width, height, 1)
      group.add(sprite)
      const shadow = new THREE.Mesh(
        new THREE.CircleGeometry(width * 0.32, 12),
        new THREE.MeshBasicMaterial({ color: '#546246', transparent: true, opacity: 0.18, depthWrite: false })
      )
      shadow.rotation.x = -Math.PI / 2
      shadow.position.copy(position)
      shadow.position.y += 0.04
      group.add(shadow)
    }
  }

  return group
}

function makePowerTowerMesh(heightMeters, lod) {
  if (assetLibrary.tower) {
    const tower = cloneAsset(assetLibrary.tower)
    const scale = heightMeters / 36
    tower.scale.multiplyScalar(scale)
    tower.rotation.y = Math.PI / 2
    return tower
  }

  const group = new THREE.Group()
  const material = new THREE.MeshStandardMaterial({ color: '#47515a', roughness: 0.72, metalness: 0.2 })
  const legRadius = lod === 'near' ? 0.22 : 0.18
  const legSpread = lod === 'near' ? 2.1 : 1.7
  const topSpread = legSpread * 0.34
  const legHeight = heightMeters

  const legPositions = [
    [-legSpread, 0, -legSpread],
    [legSpread, 0, -legSpread],
    [-legSpread, 0, legSpread],
    [legSpread, 0, legSpread],
  ]

  for (const [x, , z] of legPositions) {
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(legRadius, legRadius * 1.25, legHeight, 6), material)
    leg.position.set(x * 0.58, legHeight / 2, z * 0.58)
    leg.rotation.z = x < 0 ? 0.05 : -0.05
    leg.rotation.x = z < 0 ? -0.04 : 0.04
    group.add(leg)
  }

  const levels = lod === 'near' ? [0.2, 0.4, 0.6, 0.8] : [0.28, 0.56, 0.82]
  levels.forEach((ratio) => {
    const y = legHeight * ratio
    const width = THREE.MathUtils.lerp(legSpread, topSpread, ratio) * 2.1
    const beamX = new THREE.Mesh(new THREE.BoxGeometry(width, 0.16, 0.16), material)
    beamX.position.set(0, y, 0)
    group.add(beamX)
    const beamZ = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.16, width), material)
    beamZ.position.set(0, y, 0)
    group.add(beamZ)

    const braceLength = Math.sqrt((width * 0.42) ** 2 + (legHeight * 0.16) ** 2)
    for (const sign of [-1, 1]) {
      const brace = new THREE.Mesh(new THREE.BoxGeometry(0.1, braceLength, 0.1), material)
      brace.position.set(sign * width * 0.18, y, 0)
      brace.rotation.z = sign * 0.58
      group.add(brace)
    }
  })

  const crossarmWidth = lod === 'near' ? 8.5 : 7
  const crossarm = new THREE.Mesh(new THREE.BoxGeometry(crossarmWidth, 0.18, 0.24), material)
  crossarm.position.set(0, legHeight * 0.76, 0)
  group.add(crossarm)

  const toparm = new THREE.Mesh(new THREE.BoxGeometry(crossarmWidth * 0.65, 0.14, 0.18), material)
  toparm.position.set(0, legHeight * 0.9, 0)
  group.add(toparm)

  return group
}

function shapeFromPolygon(feature, center, terrain) {
  const shape = new THREE.Shape()
  feature.footprint.forEach((point, index) => {
    const projected = projectPoint(
      point.longitude,
      point.latitude,
      sampleTerrainElevation(point.longitude, point.latitude, terrain),
      center
    )
    if (index === 0) {
      shape.moveTo(projected.x, projected.z)
    } else {
      shape.lineTo(projected.x, projected.z)
    }
  })

  for (const hole of feature.holes || []) {
    const holePath = new THREE.Path()
    hole.forEach((point, index) => {
      const projected = projectPoint(
        point.longitude,
        point.latitude,
        sampleTerrainElevation(point.longitude, point.latitude, terrain),
        center
      )
      if (index === 0) {
        holePath.moveTo(projected.x, projected.z)
      } else {
        holePath.lineTo(projected.x, projected.z)
      }
    })
    shape.holes.push(holePath)
  }

  return shape
}

function footprintBounds(feature, center) {
  const xs = []
  const zs = []
  feature.footprint.forEach((point) => {
    const projected = projectPoint(point.longitude, point.latitude, 0, center)
    xs.push(projected.x)
    zs.push(projected.z)
  })
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minZ: Math.min(...zs),
    maxZ: Math.max(...zs),
  }
}

function makePolygonSurface(feature, center, terrain, options = {}) {
  if (feature.geometryType === 'line') {
    return makeLinearFeatureLine(
      { centerline: feature.centerline },
      center,
      terrain,
      { color: options.color, altitudeOffset: options.altitudeOffset ?? 0.15 }
    )
  }

  const shape = shapeFromPolygon(feature, center, terrain)
  const geometry = new THREE.ShapeGeometry(shape)
  geometry.rotateX(-Math.PI / 2)
  const mesh = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({
      color: options.color ?? feature.color ?? '#a9c984',
      map: options.map || null,
      roughness: options.roughness ?? 0.98,
      transparent: options.transparent ?? false,
      opacity: options.opacity ?? 1,
    })
  )
  mesh.position.y += options.altitudeOffset ?? 0.05
  return mesh
}

function makeBuildingMesh(building, center, terrain, lod) {
  if (lod === 'far') {
    const bounds = footprintBounds(building, center)
    const width = Math.max(8, bounds.maxX - bounds.minX)
    const depth = Math.max(8, bounds.maxZ - bounds.minZ)
    const height = Math.max(6, Math.min(building.heightMeters, 20))
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(width, height, depth),
      new THREE.MeshStandardMaterial({ color: building.wallColor || TILE_COLORS.buildingWall, roughness: 0.92 })
    )
    mesh.position.set((bounds.minX + bounds.maxX) / 2, height / 2, (bounds.minZ + bounds.maxZ) / 2)
    return mesh
  }

  const shape = shapeFromPolygon(building, center, terrain)
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth: lod === 'mid' ? Math.min(building.heightMeters, 14) : Math.min(building.heightMeters, 22),
    bevelEnabled: false,
    curveSegments: lod === 'near' ? 6 : 3,
  })
  geometry.rotateX(-Math.PI / 2)
  const group = new THREE.Group()
  const wallMesh = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({
      color: building.wallColor || TILE_COLORS.buildingWall,
      roughness: 0.9,
    })
  )
  wallMesh.position.y += 0.08
  group.add(wallMesh)

  const roofGeometry = new THREE.ShapeGeometry(shape)
  roofGeometry.rotateX(-Math.PI / 2)
  const roofMesh = new THREE.Mesh(
    roofGeometry,
    new THREE.MeshStandardMaterial({
      color: building.roofColor || TILE_COLORS.buildingRoof,
      roughness: 0.84,
      metalness: 0.02,
    })
  )
  roofMesh.position.y += Math.min(building.heightMeters, lod === 'mid' ? 14 : 22) + 0.24
  group.add(roofMesh)
  return group
}

function makeCrossingMarker(crossing, center, terrain, lod) {
  const group = new THREE.Group()
  const baseElevation = sampleTerrainElevation(crossing.longitude, crossing.latitude, terrain)
  const position = projectPoint(crossing.longitude, crossing.latitude, baseElevation, center)
  const colorMap = {
    very_high: '#d7263d',
    high: '#f08a24',
    medium: '#f3c64d',
    low: '#1c9c6b',
    unknown: '#94a3b8',
  }

  const radius = lod === 'far' ? 2.1 : 3.3
  const base = new THREE.Mesh(
    new THREE.CylinderGeometry(radius, radius, lod === 'far' ? 1.2 : 1.8, 16),
    new THREE.MeshStandardMaterial({ color: colorMap[crossing.riskLevel] || colorMap.unknown })
  )
  base.position.copy(position)
  base.position.y += lod === 'far' ? 0.6 : 0.9
  group.add(base)

  if (lod !== 'far') {
    const beacon = new THREE.Mesh(
      new THREE.ConeGeometry(2.1, 6, 12),
      new THREE.MeshStandardMaterial({ color: '#f8fafc', emissive: '#94a3b8', emissiveIntensity: 0.15 })
    )
    beacon.position.copy(position)
    beacon.position.y += 5
    group.add(beacon)
  }

  return group
}

function makePowerline(powerline, center, terrain, lod) {
  const group = new THREE.Group()

  if (lod !== 'far') {
    powerline.towers.forEach((tower) => {
      const terrainElevation = sampleTerrainElevation(tower.longitude, tower.latitude, terrain)
      const position = projectPoint(tower.longitude, tower.latitude, terrainElevation, center)
      const towerMesh = makePowerTowerMesh(tower.heightMeters, lod)
      towerMesh.position.copy(position)
      group.add(towerMesh)
    })
  }

  powerline.wires.forEach((wire) => {
    const points = wire.points.map((point) =>
      projectPoint(
        point.longitude,
        point.latitude,
        sampleTerrainElevation(point.longitude, point.latitude, terrain) + (point.elevation || 0),
        center
      )
    )
    group.add(
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(points),
        new THREE.LineBasicMaterial({ color: '#2f3438' })
      )
    )
  })

  return group
}

function makeTerrainMesh(terrain, center) {
  if (!terrain?.elevations?.length || terrain.width < 2 || terrain.height < 2) return null

  const { west, south, east, north } = terrain.bounds
  const southWest = projectPoint(west, south, 0, center)
  const northEast = projectPoint(east, north, 0, center)
  const widthMeters = Math.abs(northEast.x - southWest.x)
  const depthMeters = Math.abs(northEast.z - southWest.z)
  const geometry = new THREE.PlaneGeometry(widthMeters, depthMeters, terrain.width - 1, terrain.height - 1)
  const positions = geometry.attributes.position
  const flattened = terrain.elevations.flat()

  for (let index = 0; index < positions.count; index += 1) {
    positions.setZ(index, flattened[index] || 0)
  }

  geometry.rotateX(-Math.PI / 2)
  geometry.computeVertexNormals()

  return new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({
      color: TILE_COLORS.terrain,
      map: grassTexture(),
      roughness: 0.98,
      metalness: 0,
    })
  )
}

function buildTileGroup(tile, lod) {
  const center = props.manifest.center
  const terrain = tile.terrain
  const tileId = tile.tile.id
  const group = new THREE.Group()
  group.userData = { tileId, lod }

  const terrainMesh = makeTerrainMesh(terrain, center)
  if (terrainMesh) group.add(terrainMesh)

  if (shouldRenderLanduseAtLod(lod)) {
    tile.landuse?.forEach((feature, index) => {
      const mesh = makePolygonSurface(feature, center, terrain, {
        color: feature.color || TILE_COLORS.landuse,
        map: landuseTexture(feature.kind),
        altitudeOffset: 0.06,
        opacity: lod === 'near' ? 0.78 : lod === 'mid' ? 0.68 : 0.52,
      })
      if (mesh) group.add(setPickMetadata(mesh, 'landuse', feature, tileId))
      if ((lod === 'near' && index < 18) || (lod === 'mid' && index < 8)) {
        const vegetation = makeTreeGroup(feature, center, terrain, lod)
        if (vegetation) group.add(vegetation)
      }
    })
  }

  tile.water?.forEach((feature) => {
    const mesh =
      feature.geometryType === 'line'
        ? makeLinearFeatureLine(feature, center, terrain, { color: feature.color || TILE_COLORS.water, altitudeOffset: 0.12 })
        : makePolygonSurface(feature, center, terrain, {
            color: feature.color || TILE_COLORS.water,
            altitudeOffset: 0.12,
            opacity: 0.88,
          })
    if (mesh) group.add(setPickMetadata(mesh, 'water', feature, tileId))
    if (shouldRenderWaterLabelAtLod(lod) && feature.labelAnchor && feature.name) {
      const label = makeLabel(feature.labelAnchor, feature.name, center, terrain)
      if (label) group.add(label)
    }
  })

  tile.roads?.forEach((road) => {
    if (!shouldRenderRoadAtLod(road, lod)) return
    const visual = roadVisual(road, lod)
    const mesh = makeRoadRibbon(road, center, terrain, {
      lod,
      outlineColor: visual.outlineColor,
      edgeColor: visual.edgeColor,
      surfaceColor: visual.surfaceColor,
      altitudeOffset: 0.26,
      widthScale: visual.widthScale,
    })
    if (mesh) group.add(setPickMetadata(mesh, 'road', road, tileId))
  })

  tile.railways?.forEach((railway) => {
    const mesh =
      lod === 'near'
        ? makeLinearFeatureMesh(railway, center, terrain, {
            color: TILE_COLORS.rail,
            radius: Math.max(railway.widthMeters / 5, 1.2),
            tubularSegments: Math.max(18, railway.centerline.length * 4),
            altitudeOffset: 0.32,
            metalness: 0.08,
          })
        : makeLinearFeatureLine(railway, center, terrain, {
            color: TILE_COLORS.rail,
            opacity: lod === 'mid' ? 0.95 : 0.82,
            altitudeOffset: 0.28,
          })
    if (mesh) group.add(setPickMetadata(mesh, 'railway', railway, tileId))
    if (lod === 'near' && railway.name && railway.labelAnchor) {
      const label = makeLabel(railway.labelAnchor, railway.name, center, terrain)
      if (label) group.add(label)
    }
  })

  tile.buildings?.forEach((building, index) => {
    if (!shouldRenderBuildingAtLod(lod, index)) return
    const mesh = makeBuildingMesh(building, center, terrain, lod)
    if (mesh) group.add(setPickMetadata(mesh, 'building', building, tileId))
  })

  tile.powerlines?.forEach((powerline) => {
    group.add(setPickMetadata(makePowerline(powerline, center, terrain, lod), 'powerline', powerline, tileId))
  })

  tile.crossings?.forEach((crossing) => {
    group.add(setPickMetadata(makeCrossingMarker(crossing, center, terrain, lod), 'crossing', crossing, tileId))
  })

  return group
}

function touchTileCache(tileId, tile) {
  if (tileCache.has(tileId)) {
    tileCache.delete(tileId)
  }
  tileCache.set(tileId, tile)
}

function pruneTileCache() {
  const visibleIds = new Set(tileGroups.keys())
  while (tileCache.size > MAX_TILE_CACHE) {
    const oldestKey = tileCache.keys().next().value
    if (!oldestKey) break
    if (visibleIds.has(oldestKey)) {
      const tile = tileCache.get(oldestKey)
      tileCache.delete(oldestKey)
      tileCache.set(oldestKey, tile)
      continue
    }
    tileCache.delete(oldestKey)
  }
  loadingState.cachedTiles = tileCache.size
}

async function ensureTileLoaded(tileId) {
  if (tileCache.has(tileId)) {
    const tile = tileCache.get(tileId)
    touchTileCache(tileId, tile)
    return tile
  }
  if (inflightTiles.has(tileId)) return inflightTiles.get(tileId)

  const request = fetchScene3DTile(tileId)
    .then((tile) => {
      touchTileCache(tileId, tile)
      inflightTiles.delete(tileId)
      pruneTileCache()
      return tile
    })
    .catch((error) => {
      inflightTiles.delete(tileId)
      throw error
    })

  inflightTiles.set(tileId, request)
  return request
}

function tileCoords(tileId) {
  const [, x, y] = tileId.split('_')
  return { x: Number(x), y: Number(y) }
}

function desiredTilesFromCamera() {
  if (!props.manifest?.center || !controls || !camera) return []
  const distance = camera.position.distanceTo(controls.target)
  const centerGeo = unprojectPoint(controls.target.x, controls.target.z, props.manifest.center)
  const tileSize = props.manifest.tileSizeDegrees
  const targetX = Math.floor(centerGeo.longitude / tileSize)
  const targetY = Math.floor(centerGeo.latitude / tileSize)
  const ringCount = ringCountForDistance(distance)
  const wanted = []

  props.manifest.tiles.forEach((tile) => {
    const coords = tileCoords(tile.id)
    if (Math.abs(coords.x - targetX) <= ringCount && Math.abs(coords.y - targetY) <= ringCount) {
      const hasRenderableData = ['crossings', 'roads', 'railways', 'buildings', 'landuse', 'water', 'powerlines'].some(
        (key) => (tile.featureCounts?.[key] || 0) > 0
      )
      if (!hasRenderableData) return
      const tileCenter = projectPoint(tile.center.longitude, tile.center.latitude, 0, props.manifest.center)
      const tileDistance = tileCenter.distanceTo(controls.target)
      wanted.push({
        id: tile.id,
        distance: tileDistance,
        lod: tileDistanceBand(tileDistance + distance * 0.2),
      })
    }
  })

  wanted.sort((a, b) => a.distance - b.distance)
  return wanted.slice(0, maxVisibleTiles(distance))
}

async function syncVisibleTiles() {
  if (!tileRoot || !props.manifest?.tiles?.length || syncInFlight) return
  syncInFlight = true

  try {
    const desiredTiles = desiredTilesFromCamera()
    const signature = desiredTiles.map((tile) => `${tile.id}:${tile.lod}`).join('|')
    if (signature === lastTileSignature) return
    lastTileSignature = signature
    loadingState.activeTiles = desiredTiles.length

    const nextVisibleIds = new Set(desiredTiles.map((tile) => tile.id))

    for (const [tileId, group] of tileGroups.entries()) {
      if (!nextVisibleIds.has(tileId)) {
        tileRoot.remove(group)
        tileGroups.delete(tileId)
      }
    }

    for (const meta of desiredTiles) {
      const tile = await ensureTileLoaded(meta.id)
      const existing = tileGroups.get(meta.id)
      if (existing && existing.userData.lod === meta.lod) continue
      if (existing) {
        tileRoot.remove(existing)
        tileGroups.delete(meta.id)
      }
      const group = buildTileGroup(tile, meta.lod)
      tileRoot.add(group)
      tileGroups.set(meta.id, group)
    }

    pruneTileCache()
  } finally {
    syncInFlight = false
  }
}

function queueTileSync() {
  if (syncQueued) return
  syncQueued = true
  requestAnimationFrame(async () => {
    syncQueued = false
    await syncVisibleTiles()
  })
}

function clearHighlight() {
  if (!highlightedObject) return
  const material = highlightedObject.material
  if (material?.emissive && highlightedObject.userData.originalEmissive !== undefined) {
    material.emissive.setHex(highlightedObject.userData.originalEmissive)
  }
  highlightedObject = null
}

function applyHighlight(object) {
  clearHighlight()
  if (!object?.material?.emissive) return
  object.userData.originalEmissive = object.material.emissive.getHex()
  object.material.emissive.setHex(0x2563eb)
  highlightedObject = object
}

function featureSummary(type, feature, tileId) {
  const base = { type, tileId }
  if (type === 'crossing') {
    return { ...base, title: feature.name || feature.code, subtitle: `${feature.riskLevel} • ${feature.riskScore}`, coords: `${feature.longitude}, ${feature.latitude}` }
  }
  if (type === 'building') {
    return { ...base, title: feature.name || feature.kind || 'Building', subtitle: `${feature.heightMeters} m`, coords: `${feature.footprint.length} points` }
  }
  if (type === 'road' || type === 'railway') {
    return { ...base, title: feature.name || feature.kind, subtitle: `${feature.kind} • ${feature.widthMeters} m`, coords: `${feature.centerline.length} points` }
  }
  if (type === 'powerline') {
    return { ...base, title: feature.name || 'Powerline', subtitle: `${feature.voltageClass || 'unknown'} • ${feature.towers.length} towers`, coords: `${feature.wires.length} wire sets` }
  }
  if (type === 'water' || type === 'landuse') {
    return { ...base, title: feature.name || feature.kind, subtitle: feature.geometryType || 'polygon', coords: `${feature.footprint?.length || feature.centerline?.length || 0} points` }
  }
  return { ...base, title: type, subtitle: '', coords: '' }
}

function pickFeature(event) {
  if (!renderer || !camera || !tileRoot) return
  const bounds = renderer.domElement.getBoundingClientRect()
  pointer.x = ((event.clientX - bounds.left) / bounds.width) * 2 - 1
  pointer.y = -((event.clientY - bounds.top) / bounds.height) * 2 + 1
  raycaster.setFromCamera(pointer, camera)
  const intersections = raycaster.intersectObjects(tileRoot.children, true)
  const hit = intersections.find((entry) => entry.object.userData.pickable)

  if (!hit) {
    selectedFeature.value = null
    clearHighlight()
    return
  }

  const pickable = hit.object
  selectedFeature.value = featureSummary(
    pickable.userData.featureType,
    pickable.userData.feature,
    pickable.userData.tileId
  )
  applyHighlight(pickable)
}

function onPointerDown(event) {
  pointerDownStart = { x: event.clientX, y: event.clientY }
  movedDuringPointer = false
  interactionState.dragging = true
  root.value?.classList.add('is-dragging')
}

function onPointerMove(event) {
  if (!pointerDownStart) return
  const distance = Math.hypot(event.clientX - pointerDownStart.x, event.clientY - pointerDownStart.y)
  if (distance > 6) movedDuringPointer = true
}

function onPointerUp(event) {
  root.value?.classList.remove('is-dragging')
  interactionState.dragging = false
  if (pointerDownStart && !movedDuringPointer) {
    pickFeature(event)
  }
  pointerDownStart = null
  movedDuringPointer = false
}

function resizeRenderer() {
  if (!root.value || !renderer || !camera) return
  const width = root.value.clientWidth
  const height = root.value.clientHeight
  renderer.setSize(width, height)
  camera.aspect = width / height
  camera.updateProjectionMatrix()
}

function animate() {
  frameId = requestAnimationFrame(animate)
  controls?.update()
  renderer?.render(scene, camera)
}

function initializeScene() {
  scene = new THREE.Scene()
  scene.background = new THREE.Color('#ece4d6')
  scene.fog = new THREE.Fog('#ece4d6', 420, 3200)

  camera = new THREE.PerspectiveCamera(55, 1, 0.1, 10000)
  camera.position.set(180, 220, 320)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setPixelRatio(window.devicePixelRatio)
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.05
  renderer.shadowMap.enabled = true
  root.value.appendChild(renderer.domElement)

  pointer = new THREE.Vector2()
  raycaster = new THREE.Raycaster()

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.enablePan = true
  controls.screenSpacePanning = false
  controls.panSpeed = 1.15
  controls.zoomSpeed = 1.1
  controls.rotateSpeed = 0.82
  controls.mouseButtons.LEFT = THREE.MOUSE.PAN
  controls.mouseButtons.MIDDLE = THREE.MOUSE.DOLLY
  controls.mouseButtons.RIGHT = THREE.MOUSE.ROTATE
  const focusCenter = manifestFocusCenter()
  const focusPoint = projectPoint(focusCenter.longitude, focusCenter.latitude, 0, props.manifest.center)
  controls.target.copy(focusPoint)
  camera.position.set(focusPoint.x + 180, 220, focusPoint.z + 320)
  controls.maxPolarAngle = Math.PI * 0.49
  controls.minPolarAngle = Math.PI * 0.08
  controls.minDistance = 60
  controls.maxDistance = 2600
  controls.addEventListener('change', () => {
    queueTileSync()
  })

  scene.add(new THREE.HemisphereLight('#fff9ed', '#cabfa8', 1.22))
  const dir = new THREE.DirectionalLight('#ffffff', 1.08)
  dir.position.set(240, 280, 140)
  scene.add(dir)

  tileRoot = new THREE.Group()
  scene.add(tileRoot)
  renderer.domElement.addEventListener('pointerdown', onPointerDown)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerup', onPointerUp)
  renderer.domElement.addEventListener('pointerleave', onPointerUp)
}

function disposeScene() {
  tileCache.clear()
  inflightTiles.clear()
  tileGroups.clear()
  lastTileSignature = ''
  selectedFeature.value = null
  clearHighlight()
}

onMounted(async () => {
  initializeScene()
  resizeRenderer()
  await loadSceneAssets()
  lastTileSignature = ''
  await syncVisibleTiles()
  animate()
  window.addEventListener('resize', resizeRenderer)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeRenderer)
  renderer?.domElement?.removeEventListener('pointerdown', onPointerDown)
  renderer?.domElement?.removeEventListener('pointermove', onPointerMove)
  renderer?.domElement?.removeEventListener('pointerup', onPointerUp)
  renderer?.domElement?.removeEventListener('pointerleave', onPointerUp)
  cancelAnimationFrame(frameId)
  controls?.dispose()
  renderer?.dispose()
  disposeScene()
})

watch(
  () => props.manifest,
  async () => {
    if (!scene || !props.manifest?.tiles?.length) return
    const focusCenter = manifestFocusCenter()
    const focusPoint = projectPoint(focusCenter.longitude, focusCenter.latitude, 0, props.manifest.center)
    controls?.target.copy(focusPoint)
    camera?.position.set(focusPoint.x + 180, 220, focusPoint.z + 320)
    lastTileSignature = ''
    await syncVisibleTiles()
    resizeRenderer()
  },
  { deep: true }
)
</script>

<template>
  <div class="scene3d-shell">
    <div ref="root" class="scene3d-root"></div>
    <div class="scene3d-overlay">
      <strong>Tile streaming</strong>
      <span>{{ loadingState.activeTiles }} tile active</span>
      <span>{{ loadingState.cachedTiles }} tile cached</span>
      <span>Kéo chuột trái để di chuyển, chuột phải để xoay</span>
    </div>
    <div v-if="selectedFeature" class="scene3d-selection">
      <strong>{{ selectedFeature.title }}</strong>
      <span>{{ selectedFeature.type }} · {{ selectedFeature.tileId }}</span>
      <span>{{ selectedFeature.subtitle }}</span>
      <span>{{ selectedFeature.coords }}</span>
    </div>
  </div>
</template>
