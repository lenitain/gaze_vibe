<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const emit = defineEmits(['data', 'region-switch'])

let webgazer = null
let isTracking = ref(false)
let lastRegion = ref(null)
let lastTimestamp = ref(null)
let cameraReady = ref(false)
let cameraError = ref('')
let gazeCount = ref(0)

async function initWebGazer() {
  if (typeof window.webgazer === 'undefined') {
    console.warn('WebGazer 脚本未加载，等待...')
    await new Promise(r => setTimeout(r, 500))
    return initWebGazer()
  }

  webgazer = window.webgazer

  webgazer.setGazeListener((data, elapsedTime) => {
    if (!data) return

    gazeCount.value++
    const x = data.x
    const y = data.y
    const currentTime = Date.now()

    const region = getRegion(x, y)

    if (region) {
      if (lastRegion.value && lastRegion.value !== region) {
        const duration = lastTimestamp.value ? currentTime - lastTimestamp.value : 0

        if (duration > 0) {
          emit('data', {
            region: lastRegion.value,
            duration: duration
          })
        }

        emit('region-switch')
      }

      lastRegion.value = region
      lastTimestamp.value = currentTime
    }
  })

  webgazer.saveDataAcrossSessions = true

  console.log('WebGazer 初始化完成')
}

function getRegion(x, y) {
  if (x < window.innerWidth / 2) return 'A'
  return 'B'
}

async function startTracking() {
  cameraError.value = ''

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true })
    stream.getTracks().forEach(t => t.stop())
    console.log('摄像头权限已获取')
  } catch (err) {
    cameraError.value = '请允许摄像头权限后重试'
    console.error('摄像头权限拒绝:', err)
    return
  }

  if (!webgazer) {
    console.log('初始化 WebGazer...')
    await initWebGazer()
  }

  console.log('webgazer 实例:', !!webgazer)

  if (webgazer) {
    try {
      console.log('调用 webgazer.begin()...')
      await webgazer.begin()
      isTracking.value = true
      cameraReady.value = true
      gazeCount.value = 0
      cameraError.value = ''
      console.log('眼动追踪已启动')
    } catch (err) {
      const msg = err && err.message ? err.message : String(err)
      cameraError.value = '启动失败: ' + msg
      console.error('webgazer.begin() 失败:', err)
    }
  } else {
    cameraError.value = 'WebGazer 加载失败，请刷新页面'
    console.error('webgazer 为 null')
  }
}

function stopTracking() {
  if (webgazer) {
    webgazer.pause()
    isTracking.value = false

    if (lastRegion.value && lastTimestamp.value) {
      const duration = Date.now() - lastTimestamp.value
      if (duration > 0) {
        emit('data', {
          region: lastRegion.value,
          duration: duration
        })
      }
    }

    lastRegion.value = null
    lastTimestamp.value = null

    console.log('眼动追踪已停止，共收到', gazeCount.value, '次注视数据')
  }
}

function startCalibration() {
  if (!webgazer) {
    cameraError.value = 'WebGazer 未初始化'
    return
  }
  webgazer.showPredictionPoints(true)
  console.log('校准模式：请看屏幕上的不同位置，绿点表示系统预测的注视点')
}

onMounted(() => {
  setTimeout(initWebGazer, 1000)
})

onUnmounted(() => {
  stopTracking()
  if (webgazer) {
    webgazer.end()
  }
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
    <div v-else class="status" :class="{ active: isTracking }">
      <span class="dot"></span>
      <span>{{ isTracking ? `追踪中 (${gazeCount})` : '等待启动' }}</span>
    </div>

    <button
      v-if="!isTracking && !cameraError"
      @click="startCalibration"
      class="calibrate-btn"
    >
      校准
    </button>
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
  background: #252526;
  border-radius: 20px;
  z-index: 100;
}

.status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #888;
}

.status.active {
  color: #4fc3f7;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #555;
}

.status.active .dot {
  background: #4fc3f7;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.calibrate-btn {
  padding: 6px 12px;
  background: #333;
  color: #fff;
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.2s;
}

.calibrate-btn:hover {
  background: #444;
}

.error {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #ef5350;
}

.retry-btn {
  padding: 2px 8px;
  background: #ef5350;
  color: #fff;
  border: none;
  border-radius: 3px;
  font-size: 11px;
  cursor: pointer;
}
</style>
