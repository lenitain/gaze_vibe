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

let lastSwitchTime = null
let lastSwitchFrom = null
const DEBOUNCE_THRESHOLD = 80

let totalDurationA = 0
let totalDurationB = 0
let tau = ref(0)

// 时间序列类指标
let firstFixationRegion = ref(null)
let firstFixationDuration = ref(0)
let lastFixationRegion = ref(null)
let trackingStartTime = null

// 扫视模式类指标
let saccadeCount = ref(0)
let abSwitchCount = 0
let baSwitchCount = 0
let regressionCount = 0
let switchHistory = []

// 认知负荷类指标
let fixationDurations = []
let switchIntervals = []
let previousSwitchTime = null

// 决策预测类指标
let gazeBias = ref(0)
let decisionLatency = ref(0)

// 注意力动力学指标
let explorationRatio = ref(0)
let finalAttentionFocus = ref({ A: 0, B: 0 })
let tauHistory = []

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
      if (currentRegion.value === 'A') {
        totalDurationA += duration
      } else {
        totalDurationB += duration
      }
      
      fixationDurations.push(duration)
      
      // 记录首看区域和首注视时长
      if (!firstFixationRegion.value) {
        firstFixationRegion.value = currentRegion.value
        firstFixationDuration.value = duration
      }
      
      emit('data', { region: currentRegion.value, duration })
      calculateAllMetrics()
    }
  }
  regionStartTime = null
}

function calculateAllMetrics() {
  calculateTau()
  calculateGazeBias()
  calculateExplorationRatio()
  calculateFinalAttention()
}

function calculateTau() {
  const total = totalDurationA + totalDurationB
  if (total === 0) {
    tau.value = 0
    return
  }
  
  const pA = totalDurationA / total
  const pB = totalDurationB / total
  
  const entropyA = pA > 0 ? pA * Math.log(pA) : 0
  const entropyB = pB > 0 ? pB * Math.log(pB) : 0
  
  tau.value = -(entropyA + entropyB)
  tauHistory.push(tau.value)
}

function calculateGazeBias() {
  const total = totalDurationA + totalDurationB
  if (total === 0) {
    gazeBias.value = 0.5
    return
  }
  gazeBias.value = totalDurationA / total
}

function calculateExplorationRatio() {
  const total = saccadeCount.value
  if (total === 0) {
    explorationRatio.value = 0
    return
  }
  
  // 前1/3时间的扫视次数 vs 后2/3时间
  const now = Date.now()
  const elapsed = now - trackingStartTime
  const oneThirdTime = elapsed / 3
  
  const earlySwitches = switchHistory.filter(t => t - trackingStartTime < oneThirdTime).length
  explorationRatio.value = earlySwitches / total
}

function calculateFinalAttention() {
  const now = Date.now()
  const elapsed = now - regionStartTime
  const totalSession = now - trackingStartTime
  
  // 计算最后30%时间的注视分布
  if (totalSession > 0 && currentRegion.value) {
    const finalDuration = elapsed
    if (currentRegion.value === 'A') {
      finalAttentionFocus.value.A += finalDuration
    } else {
      finalAttentionFocus.value.B += finalDuration
    }
  }
}

function getFixationDurationVariance() {
  if (fixationDurations.length === 0) return 0
  const mean = fixationDurations.reduce((a, b) => a + b, 0) / fixationDurations.length
  const variance = fixationDurations.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / fixationDurations.length
  return variance
}

function getMeanSwitchInterval() {
  if (switchIntervals.length === 0) return 0
  return switchIntervals.reduce((a, b) => a + b, 0) / switchIntervals.length
}

function getSwitchIntervalDecay() {
  if (switchIntervals.length < 4) return 0
  
  const half = Math.floor(switchIntervals.length / 2)
  const firstHalf = switchIntervals.slice(0, half)
  const secondHalf = switchIntervals.slice(half)
  
  const meanFirst = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length
  const meanSecond = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length
  
  // 返回衰减比：正数表示变慢，负数表示变快
  return (meanSecond - meanFirst) / meanFirst
}

function getRegressionRate() {
  if (saccadeCount.value === 0) return 0
  return regressionCount / saccadeCount.value
}

function getDirectionRatio() {
  if (abSwitchCount + baSwitchCount === 0) return 0.5
  return abSwitchCount / (abSwitchCount + baSwitchCount)
}

function getEntropyChangeRate() {
  if (tauHistory.length < 2) return 0
  const first = tauHistory[0]
  const last = tauHistory[tauHistory.length - 1]
  return last - first
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
          const now = Date.now()
          
          // 检测抖动：如果刚从A切换到B，又马上切回A（或反过来），且总时长<80ms
          if (lastSwitchFrom === region && lastSwitchTime) {
            const switchDuration = now - lastSwitchTime
            if (switchDuration < DEBOUNCE_THRESHOLD) {
              // 这是抖动，不切换，时长计入当前区域
              lastSwitchTime = null
              lastSwitchFrom = null
              return
            }
          }
          
          // 正常切换
          flushRegion()
          const from = currentRegion.value
          currentRegion.value = region
          regionStartTime = now
          lastSwitchTime = now
          lastSwitchFrom = from
          
          // 记录扫视数据
          saccadeCount.value++
          switchHistory.push(now)
          
          // 统计扫视方向
          if (from === 'A' && region === 'B') {
            abSwitchCount++
          } else if (from === 'B' && region === 'A') {
            baSwitchCount++
            regressionCount++ // B→A视为回视
          }
          
          // 记录转换间隔
          if (previousSwitchTime) {
            const interval = now - previousSwitchTime
            switchIntervals.push(interval)
          }
          previousSwitchTime = now
          
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
    lastSwitchTime = null
    lastSwitchFrom = null
    totalDurationA = 0
    totalDurationB = 0
    tau.value = 0
    
    // 重置时间序列指标
    firstFixationRegion.value = null
    firstFixationDuration.value = 0
    lastFixationRegion.value = null
    trackingStartTime = Date.now()
    
    // 重置扫视模式指标
    saccadeCount.value = 0
    abSwitchCount = 0
    baSwitchCount = 0
    regressionCount = 0
    switchHistory = []
    
    // 重置认知负荷指标
    fixationDurations = []
    switchIntervals = []
    previousSwitchTime = null
    
    // 重置决策预测指标
    gazeBias.value = 0
    decisionLatency.value = 0
    
    // 重置注意力动力学指标
    explorationRatio.value = 0
    finalAttentionFocus.value = { A: 0, B: 0 }
    tauHistory = []

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
    lastFixationRegion.value = currentRegion.value
    decisionLatency.value = Date.now() - trackingStartTime
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

function getAllMetrics() {
  return {
    // 信息熵
    tau: tau.value,
    
    // 时间序列类
    firstFixationRegion: firstFixationRegion.value,
    firstFixationDuration: firstFixationDuration.value,
    lastFixationRegion: lastFixationRegion.value,
    
    // 扫视模式类
    saccadeCount: saccadeCount.value,
    directionRatio: getDirectionRatio(),
    regressionRate: getRegressionRate(),
    
    // 认知负荷类
    fixationDurationVariance: getFixationDurationVariance(),
    meanSwitchInterval: getMeanSwitchInterval(),
    switchIntervalDecay: getSwitchIntervalDecay(),
    
    // 决策预测类
    gazeBias: gazeBias.value,
    decisionLatency: decisionLatency.value,
    
    // 注意力动力学
    explorationRatio: explorationRatio.value,
    finalAttentionFocus: finalAttentionFocus.value,
    entropyChangeRate: getEntropyChangeRate(),
    
    // 原始数据
    totalDurationA,
    totalDurationB,
    tauHistory: tauHistory.slice()
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

  // WebGazer 在 body 上创建的固定定位元素可能残留，强制清理
  const ids = [
    'webgazerVideoFeed',
    'webgazerVideoContainer',
    'webgazerFaceFeedbackBox',
    'webgazerFaceOverlay',
    'webgazerGazeDot',
    'webgazerCanvas',
  ]
  ids.forEach(id => {
    const el = document.getElementById(id)
    if (el) el.remove()
  })
  // 也清理可能残留的覆盖层
  document.querySelectorAll('.calibration-overlay').forEach(el => el.remove())
})

defineExpose({
  startTracking,
  stopTracking,
  startCalibration,
  isTracking,
  tau,
  getAllMetrics
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
  top: 20px;
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
