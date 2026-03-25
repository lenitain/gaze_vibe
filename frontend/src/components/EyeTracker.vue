<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'

const emit = defineEmits(['data', 'region-switch'])

// WebGazer 实例
let webgazer = null
let isTracking = ref(false)
let lastRegion = ref(null)
let lastTimestamp = ref(null)
let isCalibrating = ref(false)

// 4象限区域映射
const regions = ref({
  A: null,  // 左半边
  B: null   // 右半边
})

// 初始化 WebGazer
async function initWebGazer() {
  if (typeof webgazer === 'undefined') {
    console.warn('WebGazer 未加载，等待...')
    setTimeout(initWebGazer, 500)
    return
  }

  webgazer = window.webgazer
  
  // 设置数据留存时间
  webgazer.setGazeListener((data, elapsedTime) => {
    if (data == null) return
    
    const x = data.x
    const y = data.y
    const currentTime = Date.now()
    
    // 判断所在的区域
    const region = getRegion(x, y)
    
    if (region) {
      // 检测区域切换
      if (lastRegion.value && lastRegion.value !== region) {
        const duration = lastTimestamp.value ? currentTime - lastTimestamp.value : 0
        
        // 发送上一个区域的数据
        if (duration > 0) {
          emit('data', {
            region: lastRegion.value,
            duration: duration
          })
        }
        
        // 触发区域切换事件
        emit('region-switch')
      }
      
      lastRegion.value = region
      lastTimestamp.value = currentTime
    }
  })
  
  // 保存数据用于分析
  webgazer.saveDataAcrossSessions = true
  
  console.log('WebGazer 初始化完成')
}

// 获取当前注视点所在的区域
function getRegion(x, y) {
  const windowWidth = window.innerWidth
  const windowHeight = window.innerHeight
  
  // 上下四象限
  const isLeft = x < windowWidth / 2
  const isTop = y < windowHeight / 2
  
  // 简单映射到左右两栏（忽略上下）
  // 实际场景中，用户主要在左右两个答案之间切换
  if (isLeft) {
    return 'A'
  } else {
    return 'B'
  }
}

// 启动追踪
async function startTracking() {
  if (!webgazer) {
    await initWebGazer()
  }
  
  if (webgazer) {
    try {
      await webgazer.begin()
      isTracking.value = true
      console.log('眼动追踪已启动')
    } catch (err) {
      console.error('启动眼动追踪失败:', err)
    }
  }
}

// 停止追踪
function stopTracking() {
  if (webgazer) {
    webgazer.pause()
    isTracking.value = false
    
    // 发送最后的数据
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
    
    console.log('眼动追踪已停止')
  }
}

// 开始校准
async function startCalibration() {
  isCalibrating.value = true
  // WebGazer 有内置的校准流程
  // 这里可以添加自定义的校准逻辑
  console.log('开始校准...')
}

onMounted(() => {
  // 延迟初始化，等待 WebGazer 脚本加载
  setTimeout(initWebGazer, 1000)
})

onUnmounted(() => {
  stopTracking()
  if (webgazer) {
    webgazer.end()
  }
})

// 暴露方法给父组件
defineExpose({
  startTracking,
  stopTracking,
  startCalibration,
  isTracking,
  isCalibrating
})
</script>

<template>
  <div class="eye-tracker">
    <div class="status" :class="{ active: isTracking }">
      <span class="dot"></span>
      <span>{{ isTracking ? '眼动追踪中' : '等待启动' }}</span>
    </div>
    
    <button 
      v-if="!isTracking" 
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
</style>
