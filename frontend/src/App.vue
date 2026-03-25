<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import AnswerPanel from './components/AnswerPanel.vue'
import ChatInput from './components/ChatInput.vue'
import EyeTracker from './components/EyeTracker.vue'

const isEyeTracking = ref(false)
const eyeTrackerRef = ref(null)

const answerA = ref('')
const answerB = ref('')
const isLoading = ref(false)

const userPreference = ref({
  firstLooked: null,
  timeOnA: 0,
  timeOnB: 0,
  switchCount: 0,
  finalChoice: null
})

async function handleSubmit(prompt) {
  isLoading.value = true
  
  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        prompt,
        preference: userPreference.value
      })
    })
    
    const data = await response.json()
    answerA.value = data.answerA
    answerB.value = data.answerB
    
    if (eyeTrackerRef.value) {
      eyeTrackerRef.value.startTracking()
      isEyeTracking.value = true
    }
  } catch (err) {
    console.error('Error:', err)
  } finally {
    isLoading.value = false
  }
}

function handleChoice(side) {
  userPreference.value.finalChoice = side
  if (eyeTrackerRef.value) {
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
  }
  
  console.log('User choice:', side, 'Preference data:', userPreference.value)
}

function handleEyeData(data) {
  if (data.region === 'A') {
    userPreference.value.timeOnA += data.duration
  } else if (data.region === 'B') {
    userPreference.value.timeOnB += data.duration
  }
}

function handleRegionSwitch() {
  userPreference.value.switchCount++
}
</script>

<template>
  <div class="container">
    <header class="header">
      <h1>GazeVibe</h1>
      <p class="subtitle">眼动追踪 AI 编程助手</p>
    </header>

    <main class="main">
      <div v-if="!answerA && !answerB" class="welcome">
        <h2>欢迎使用 GazeVibe</h2>
        <p>输入你的编程问题，获取双份不同风格的回答</p>
        <p class="hint">系统会通过眼动追踪分析你的阅读偏好，优化后续回答</p>
      </div>

      <AnswerPanel
        v-if="answerA || answerB"
        :answerA="answerA"
        :answerB="answerB"
        :is-loading="isLoading"
        @choice="handleChoice"
      />

      <ChatInput 
        :disabled="isLoading" 
        @submit="handleSubmit" 
      />
    </main>

    <EyeTracker 
      ref="eyeTrackerRef"
      @data="handleEyeData"
      @region-switch="handleRegionSwitch"
    />
  </div>
</template>

<style scoped>
.container {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.header {
  text-align: center;
  padding: 20px 0;
  border-bottom: 1px solid #333;
}

.header h1 {
  font-size: 28px;
  color: #4fc3f7;
}

.subtitle {
  color: #888;
  margin-top: 8px;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
}

.welcome h2 {
  font-size: 24px;
  margin-bottom: 16px;
}

.welcome p {
  color: #aaa;
}

.welcome .hint {
  margin-top: 24px;
  padding: 12px 24px;
  background: #2a2a2a;
  border-radius: 8px;
  font-size: 14px;
  color: #4fc3f7;
}
</style>
