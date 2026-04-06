<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const emit = defineEmits(['data', 'region-switch'])

let webgazer = null
let isTracking = ref(false)
let cameraReady = ref(false)
let cameraError = ref('')
let gazeCount = ref(0)
let isInitialized = ref(false)

let currentRegion = ref(null)
let regionStartTime = null

let isCalibrating = ref(false)
let calibrationPoints = []
let calibrationIndex = ref(0)

const CALIBRATION_LAYOUT = [
  { x: 0.1, y: 0.1 }, { x: 0.5, y: 0.1 }, { x: 0.9, y: 0.1 },
  { x: 0.1, y: 0.5 }, { x: 0.5, y: 0.5 }, { x: 0.9, y: 0.5 },
  { x: 0.1, y: 0.9 }, { x: 0.5, y: 0.9 }, { x: 0.9, y: 0.9 },
]

async function initWebGazer() {
  if (typeof window.webgazer === 'undefined') {
    await new Promise(r => setTimeout(r, 500))
    return initWebGazer()
  }

  webgazer = window.webgazer
  webgazer.saveDataAcrossSessions = false
  webgazer.showPredictionPoints(false)

  console.log('WebGazer 初始化完成')
}

function getRegion(x) {
  const w = window.innerWidth
  const third = w / 3

  if (currentRegion.value === 'A') {
    if (x > third * 2) return 'B'
    return 'A'
  }
  if (currentRegion.value === 'B') {
    if (x < third) return 'A'
    return 'B'
  }
  return x < w / 2 ? 'A' : 'B'
}

function flushRegion() {
  if (currentRegion.value && regionStartTime) {
    const duration = Date.now() - regionStartTime
    if (duration > 0) {
      emit('data', { region: currentRegion.value, duration })
    }
  }
  regionStartTime = null
}

async function startTracking() {
  cameraError.value = ''

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    stream.getTracks().forEach(t => t.stop())
  } catch (err) {
    cameraError.value = '请允许摄像头权限后重试'
    return
  }

  if (!webgazer) {
    await initWebGazer()
  }

  if (!webgazer) {
    cameraError.value = 'WebGazer 加载失败，请刷新页面'
    return
  }

  try {
    if (!isInitialized.value) {
      await webgazer.begin()
      webgazer.removeMouseEventListeners()
      webgazer.showPredictionPoints(false)

      webgazer.setGazeListener((data) => {
        if (!data) return
        gazeCount.value++

        const region = getRegion(data.x)

        if (region !== currentRegion.value) {
          flushRegion()
          const from = currentRegion.value
          currentRegion.value = region
          regionStartTime = Date.now()
          if (from) {
            emit('region-switch', { from, to: region })
          }
        }
      })

      isInitialized.value = true
    } else {
      await webgazer.resume()
    }

    webgazer.showPredictionPoints(true)
    isTracking.value = true
    cameraReady.value = true
    gazeCount.value = 0
    currentRegion.value = null
    regionStartTime = null

    const videoEl = document.getElementById('webgazerVideoFeed')
    if (videoEl) videoEl.style.display = 'block'

    const videoContainer = document.getElementById('webgazerVideoContainer')
    if (videoContainer) videoContainer.style.display = 'block'

    console.log('追踪已启动')
  } catch (err) {
    cameraError.value = '启动失败: ' + (err.message || err)
  }
}

function stopTracking() {
  if (webgazer) {
    flushRegion()
    webgazer.pause()
    webgazer.showPredictionPoints(false)
    isTracking.value = false
    currentRegion.value = null

    const videoEl = document.getElementById('webgazerVideoFeed')
    if (videoEl) videoEl.style.display = 'none'

    const videoContainer = document.getElementById('webgazerVideoContainer')
    if (videoContainer) videoContainer.style.display = 'none'
  }
}

function startCalibration() {
  if (!webgazer) {
    cameraError.value = 'WebGazer 未初始化'
    return
  }

  if (!isTracking.value) {
    startTracking().then(() => {
      if (isTracking.value) beginCalibration()
    })
  } else {
    beginCalibration()
  }
}

function beginCalibration() {
  isCalibrating.value = true
  calibrationIndex.value = 0
  calibrationPoints = CALIBRATION_LAYOUT.map(p => ({
    x: Math.round(p.x * window.innerWidth),
    y: Math.round(p.y * window.innerHeight),
    clicks: 0
  }))
  webgazer.showPredictionPoints(true)
}

function handleCalibrationClick(point, index) {
  if (index !== calibrationIndex.value) return
  point.clicks++

  webgazer.recordScreenPosition(point.x, point.y, 'click')
  console.log(`校准点 ${index} 第 ${point.clicks} 次点击，坐标: (${point.x}, ${point.y})`)

  if (point.clicks >= 3) {
    calibrationIndex.value++
    if (calibrationIndex.value >= calibrationPoints.length) {
      finishCalibration()
    }
  }
}

function finishCalibration() {
  isCalibrating.value = false
  webgazer.showPredictionPoints(false)
  console.log('校准完成，校准点数:', webgazer.getStoredPoints ? webgazer.getStoredPoints().length : '未知')
}

onMounted(() => {
  setTimeout(initWebGazer, 1000)
})

onUnmounted(() => {
  stopTracking()
  if (webgazer) webgazer.end()
})

defineExpose({
  startTracking,
  stopTracking,
  startCalibration,
  isTracking
})
</script>

<template>
  <div class="eye-tracker">
    <div v-if="cameraError" class="error">
      {{ cameraError }}
      <button @click="startTracking" class="retry-btn">重试</button>
    </div>
    <div v-else class="status" :class="{ active: isTracking, 'region-a': currentRegion === 'A', 'region-b': currentRegion === 'B' }">
      <span class="dot"></span>
      <span>{{ isTracking ? `追踪中 - ${currentRegion === 'A' ? '详细解答' : currentRegion === 'B' ? '简洁解答' : '...'}` : '等待启动' }}</span>
    </div>

    <button
      v-if="!isTracking && !cameraError"
      @click="startCalibration"
      class="calibrate-btn"
    >
      校准
    </button>
  </div>

  <div v-if="isCalibrating" class="calibration-overlay">
    <div
      v-for="(point, index) in calibrationPoints"
      :key="index"
      class="calib-point"
      :class="{
        active: index === calibrationIndex,
        done: index < calibrationIndex
      }"
      :style="{ left: point.x + 'px', top: point.y + 'px' }"
      @click="handleCalibrationClick(point, index)"
    >
      <span v-if="index === calibrationIndex" class="click-hint">{{ point.clicks }}/3</span>
    </div>
    <div class="calib-tip">依次点击每个圆点（每个点 3 次）</div>
  </div>
</template>

<style scoped>
.eye-tracker {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--bg1);
  border-radius: 20px;
  z-index: 100;
}

.status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-sm);
  color: var(--grey1);
}

.status.active { color: var(--blue); }

.status.region-a { color: var(--blue); }
.status.region-b { color: var(--green); }

.status.region-a .dot { background: var(--blue); animation: pulse 2s infinite; }
.status.region-b .dot { background: var(--green); animation: pulse 2s infinite; }

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--bg3);
}

.status.active .dot {
  background: var(--blue);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.calibrate-btn {
  padding: 8px 14px;
  background: var(--bg3);
  color: var(--fg);
  border: none;
  border-radius: 4px;
  font-size: var(--font-sm);
  cursor: pointer;
  transition: background 0.2s;
}

.calibrate-btn:hover { background: var(--bg4); }

.error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--font-sm);
  color: var(--red);
}

.retry-btn {
  padding: 4px 10px;
  background: var(--red);
  color: var(--bg0);
  border: none;
  border-radius: 3px;
  font-size: var(--font-xs);
  cursor: pointer;
}

.calibration-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 300;
}

.calib-point {
  position: absolute;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--bg3);
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.calib-point.active {
  background: var(--blue);
  cursor: pointer;
  pointer-events: auto;
  animation: calib-pulse 1s infinite;
}

.calib-point.done {
  background: var(--green);
}

@keyframes calib-pulse {
  0%, 100% { transform: translate(-50%, -50%) scale(1); }
  50% { transform: translate(-50%, -50%) scale(1.2); }
}

.click-hint {
  font-size: var(--font-xs);
  color: var(--bg0);
  font-weight: bold;
}

.calib-tip {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  color: var(--fg);
  font-size: var(--font-base);
  background: var(--bg1);
  padding: 10px 20px;
  border-radius: 6px;
}
</style>
