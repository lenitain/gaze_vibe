<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  diffOpen: {
    type: Boolean,
    default: false
  },
  diffOpenSide: {
    type: String,
    default: null
  }
})

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

// 用于响应式更新的总时长
let displayDuration = ref(0)
let durationUpdateTimer = null

// 当前显示的区域（考虑 diff 状态）
const displayRegion = computed(() => {
  if (props.diffOpen && props.diffOpenSide) {
    return props.diffOpenSide
  }
  return currentRegion.value
})

// 格式化时长显示
const formattedDuration = computed(() => {
  const total = displayDuration.value
  if (total >= 1000) {
    return (total / 1000).toFixed(1) + 'k'
  }
  return total.toString()
})

// 启动时长更新定时器
function startDurationUpdate() {
  if (durationUpdateTimer) return
  durationUpdateTimer = setInterval(() => {
    if (isTracking.value && regionStartTime) {
      const currentElapsed = Date.now() - regionStartTime
      // 当 diff 打开时，显示 diffOpenSide 对应的时长
      if (props.diffOpen && props.diffOpenSide) {
        if (props.diffOpenSide === 'A') {
          displayDuration.value = totalDurationA + currentElapsed + totalDurationB
        } else {
          displayDuration.value = totalDurationA + totalDurationB + currentElapsed
        }
      } else {
        displayDuration.value = totalDurationA + totalDurationB + currentElapsed
      }
    } else {
      displayDuration.value = totalDurationA + totalDurationB
    }
  }, 100) // 每 100ms 更新一次
}

// 停止时长更新定时器
function stopDurationUpdate() {
  if (durationUpdateTimer) {
    clearInterval(durationUpdateTimer)
    durationUpdateTimer = null
  }
}

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
  // 当 diff 打开时，数据归到 diffOpenSide
  if (props.diffOpen && props.diffOpenSide) {
    if (regionStartTime) {
      const duration = Date.now() - regionStartTime
      if (duration > 0) {
        if (props.diffOpenSide === 'A') {
          totalDurationA += duration
        } else {
          totalDurationB += duration
        }
        emit('data', { region: props.diffOpenSide, duration })
      }
    }
    regionStartTime = null
    return
  }

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

        // 当 diff 打开时，不进行区域判断，直接返回
        // 数据会在 flushRegion 时归到 diffOpenSide
        if (props.diffOpen) return

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

    // 重置显示时长
    displayDuration.value = 0

    // 启动时长更新定时器
    startDurationUpdate()

    const videoEl = document.getElementById('webgazerVideoFeed')
    if (videoEl) {
      videoEl.style.display = 'block'
      videoEl.width = 160
      videoEl.height = 120
    }

    const videoContainer = document.getElementById('webgazerVideoContainer')
    if (videoContainer) {
      videoContainer.style.display = 'block'
      videoContainer.style.width = '160px'
      videoContainer.style.height = '120px'
    }

    console.log('追踪已启动')
  } catch (err) {
    cameraError.value = '启动失败: ' + (err.message || err)
  }
}

function stopTracking() {
  // 停止时长更新定时器
  stopDurationUpdate()

  if (webgazer) {
    flushRegion()
    lastFixationRegion.value = currentRegion.value
    decisionLatency.value = Date.now() - trackingStartTime

    // 更新最终显示时长
    displayDuration.value = totalDurationA + totalDurationB

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
})

defineExpose({
  startTracking,
  stopTracking,
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
    <div v-else class="tracker-display" :class="{ active: isTracking }">
      <!-- 区域指示器 -->
      <div class="region-indicator">
        <div 
          class="region-bar region-a" 
          :class="{ active: displayRegion === 'A' }"
          :style="{ opacity: displayRegion === 'A' ? 1 : 0.3 }"
        ></div>
        <div 
          class="region-bar region-b" 
          :class="{ active: displayRegion === 'B' }"
          :style="{ opacity: displayRegion === 'B' ? 1 : 0.3 }"
        ></div>
      </div>
      
      <!-- 时长显示 -->
      <div class="duration-display">
        <span class="duration-value" :class="{ 'pulse': isTracking }">
          {{ formattedDuration }}
        </span>
        <span class="duration-unit">ms</span>
      </div>
      
      <!-- 状态文字 -->
      <div class="status-text">
        {{ isTracking ? (displayRegion === 'A' ? '详细' : displayRegion === 'B' ? '简洁' : '...') : '待机' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.eye-tracker {
  position: fixed;
  top: 52px;
  right: 20px;
  z-index: 100;
}

.tracker-display {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--bg1);
  border-radius: 12px;
  border: 1px solid var(--bg3);
  transition: all 0.3s ease;
}

.tracker-display.active {
  border-color: var(--blue);
  box-shadow: 0 0 12px rgba(115, 162, 217, 0.2);
}

/* 区域指示器 */
.region-indicator {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.region-bar {
  width: 24px;
  height: 6px;
  border-radius: 3px;
  transition: all 0.2s ease;
}

.region-bar.region-a {
  background: var(--blue);
}

.region-bar.region-b {
  background: var(--green);
}

.region-bar.active {
  opacity: 1 !important;
  box-shadow: 0 0 8px currentColor;
  animation: bar-pulse 1s infinite;
}

@keyframes bar-pulse {
  0%, 100% { transform: scaleX(1); }
  50% { transform: scaleX(1.2); }
}

/* 时长显示 */
.duration-display {
  display: flex;
  align-items: baseline;
  gap: 2px;
}

.duration-value {
  font-size: var(--font-lg);
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  color: var(--fg);
  min-width: 40px;
  text-align: right;
}

.duration-value.pulse {
  animation: value-pulse 0.5s infinite;
}

@keyframes value-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.duration-unit {
  font-size: var(--font-xs);
  color: var(--grey1);
}

/* 状态文字 */
.status-text {
  font-size: var(--font-sm);
  color: var(--grey1);
  min-width: 28px;
  text-align: center;
}

.tracker-display.active .status-text {
  color: var(--fg);
}

/* 错误状态 */
.error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--bg1);
  border-radius: 12px;
  border: 1px solid var(--red);
  font-size: var(--font-sm);
  color: var(--red);
}

.retry-btn {
  padding: 4px 10px;
  background: var(--red);
  color: var(--bg0);
  border: none;
  border-radius: 4px;
  font-size: var(--font-xs);
  cursor: pointer;
}

.retry-btn:hover {
  opacity: 0.8;
}
</style>
