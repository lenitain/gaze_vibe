<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import AnswerPanel from './components/AnswerPanel.vue'
import ChatInput from './components/ChatInput.vue'
import EyeTracker from './components/EyeTracker.vue'
import FolderSelector from './components/FolderSelector.vue'
import FileTree from './components/FileTree.vue'
import FileViewer from './components/FileViewer.vue'
import { FileIndexer } from './utils/fileIndexer.js'
import { selectRelevantFiles, formatFilesForPrompt } from './utils/fileSelector.js'

const isEyeTracking = ref(false)
const eyeTrackerRef = ref(null)
const answerPanelRef = ref(null)

const showFolderSelector = ref(true)
const projectFolder = ref(null)
const fileIndexer = new FileIndexer()
const indexedFiles = ref([])

const selectedFile = ref(null)
const showFileExplorer = ref(true)
const isLoading = ref(false)
const answerA = ref('')
const answerB = ref('')
const currentQuestion = ref('')
const userPreference = ref({ finalChoice: null, timeOnA: 0, timeOnB: 0, leftToRight: 0, rightToLeft: 0 })
const diffOpen = ref(false)
const diffOpenSide = ref(null)
const savedToast = ref('')
const choiceSaved = ref(false)

// Confidence inference
const ALPHA = 0.3
const MIN_EYE_TIME = 2000
const STRONG_WEIGHT = 0.7
const emaBias = ref(0.5)
const roundCount = ref(0)
const decisionStartTime = ref(null)
const confidence = computed(() => {
  const raw = Math.min(1, Math.abs(emaBias.value - 0.5) * 4)
  const maturity = Math.min(1, roundCount.value / 3)
  return raw * maturity
})
const preferredSide = computed(() => {
  if (confidence.value < 0.5) return null
  return emaBias.value > 0.5 ? 'A' : 'B'
})
const autoMode = computed(() =>
  experimentMode.value === 'full' && confidence.value >= 0.8
)

function updateConfidence(eyeTimeA, eyeTimeB, explicitChoice) {
  const totalEye = eyeTimeA + eyeTimeB
  if (totalEye > MIN_EYE_TIME) {
    const rawBias = eyeTimeA / totalEye
    emaBias.value = ALPHA * rawBias + (1 - ALPHA) * emaBias.value
  }
  if (explicitChoice === 'A') {
    emaBias.value = STRONG_WEIGHT * 1.0 + (1 - STRONG_WEIGHT) * emaBias.value
  } else if (explicitChoice === 'B') {
    emaBias.value = STRONG_WEIGHT * 0.0 + (1 - STRONG_WEIGHT) * emaBias.value
  }
  roundCount.value++
}

// A/B测试模式：full=眼动+自动选择，manual=眼动+手动选择，control=无眼动
const experimentModes = ['full', 'manual', 'control']
const experimentMode = ref('full')
const isTreatment = computed(() => experimentMode.value !== 'control')

function toggleMode() {
  const idx = experimentModes.indexOf(experimentMode.value)
  experimentMode.value = experimentModes[(idx + 1) % experimentModes.length]

  // 切换到对照组时停止眼动追踪
  if (experimentMode.value === 'control' && eyeTrackerRef.value) {
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
  }
}

function handleFileSelect(file) {
  selectedFile.value = file
}

async function handleFolderSelect(dirHandle) {
  projectFolder.value = dirHandle
  showFolderSelector.value = false

  try {
    indexedFiles.value = await fileIndexer.indexDirectory(dirHandle)
    console.log(`Indexed ${indexedFiles.value.length} files from ${dirHandle.name}`)
  } catch (err) {
    console.error('Failed to index directory:', err)
  }
}

async function handleSubmit(prompt) {
  currentQuestion.value = prompt
  isLoading.value = true
  answerPanelRef.value?.resetChoice()

  try {
    const relevantFiles = selectRelevantFiles(prompt, indexedFiles.value)
    const contextFiles = formatFilesForPrompt(relevantFiles)

    // 收集眼动数据
    let eyeData = null
    if (eyeTrackerRef.value && isEyeTracking.value) {
      // 停止当前追踪并获取数据
      eyeTrackerRef.value.stopTracking()
      isEyeTracking.value = false

      // 获取详细眼动指标
      eyeData = {
        timeOnA: userPreference.value.timeOnA,
        timeOnB: userPreference.value.timeOnB,
        leftToRight: userPreference.value.leftToRight,
        rightToLeft: userPreference.value.rightToLeft,
        ...eyeTrackerRef.value.getAllMetrics()
      }
    }

    const requestBody = {
      prompt,
      contextFiles,
      experimentMode: experimentMode.value,
      eyeData  // 新增：发送眼动数据
    }

    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(requestBody)
    })
    
    const data = await response.json()
    answerA.value = data.answerA
    answerB.value = data.answerB

    // 显示后端调整结果
    if (data.eyeProcessing && data.eyeProcessing.valid) {
      console.log('眼动调整结果:', data.eyeProcessing)
    }

    // 重置眼动数据用于下一轮
    userPreference.value.timeOnA = 0
    userPreference.value.timeOnB = 0
    userPreference.value.leftToRight = 0
    userPreference.value.rightToLeft = 0
    decisionStartTime.value = Date.now()
    
    // 启动新一轮追踪
    if (experimentMode.value === 'full' && eyeTrackerRef.value) {
      eyeTrackerRef.value.startTracking()
      isEyeTracking.value = true
    }
  } catch (err) {
    console.error('Error:', err)
  } finally {
    isLoading.value = false
  }
}

async function handleChoice(side) {
  userPreference.value.finalChoice = side
  const decisionTime = decisionStartTime.value
    ? Date.now() - decisionStartTime.value
    : null

  updateConfidence(0, 0, side)
  
  // 收集详细眼动指标
  let eyeMetrics = null
  if (eyeTrackerRef.value && isEyeTracking.value) {
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
    eyeMetrics = eyeTrackerRef.value.getAllMetrics()
  }

  const apiPromise = fetch('/api/preference', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      preference: userPreference.value,
      experimentMode: experimentMode.value,
      emaBias: emaBias.value,
      confidence: confidence.value,
      decisionTime,
      eyeMetrics  // 新增：发送详细眼动指标
    })
  }).then(() => {
    choiceSaved.value = true
    setTimeout(() => { choiceSaved.value = false }, 3000)
  }).catch(err => {
    console.error('Save preference failed:', err)
  })

  const writePromise = (async () => {
    let savedCount = 0
    for (const file of indexedFiles.value) {
      if (file._originalContent && file._stagedBy === side) {
        try {
          await fileIndexer.writeFile(file.path, file.content)
          delete file._originalContent
          delete file._stagedBy
          savedCount++
        } catch (err) {
          console.error(`写入文件失败: ${file.path}`, err)
        }
      }
    }
    if (savedCount > 0) {
      savedToast.value = `已保存 ${savedCount} 个文件的修改`
      setTimeout(() => { savedToast.value = '' }, 3000)
    }
    if (answerPanelRef.value) {
      answerPanelRef.value.commitAll(side)
    }
  })()

  await apiPromise
  writePromise
}

async function handleApplyChange({ filePath, content, source }) {
  const file = indexedFiles.value.find(f => f.path === filePath)
  if (file) {
    file._originalContent = file.content
    file._stagedBy = source
    file.content = content
  }

  if (selectedFile.value?.path === filePath) {
    selectedFile.value = { ...selectedFile.value, content }
  }
}

function handleUnapplyChange({ filePath }) {
  const file = indexedFiles.value.find(f => f.path === filePath)
  if (file && file._originalContent) {
    file.content = file._originalContent
    delete file._originalContent
    delete file._stagedBy
  }

  if (selectedFile.value?.path === filePath) {
    const originalFile = indexedFiles.value.find(f => f.path === filePath)
    if (originalFile) {
      selectedFile.value = { ...selectedFile.value, content: originalFile.content }
    }
  }
}

function handleDiffToggle(isOpen, side) {
  diffOpen.value = isOpen
  diffOpenSide.value = isOpen ? side : null
}

function handleEyeData(data) {
  if (diffOpen.value) {
    if (diffOpenSide.value === 'A') {
      userPreference.value.timeOnA += data.duration
    } else if (diffOpenSide.value === 'B') {
      userPreference.value.timeOnB += data.duration
    }
    return
  }

  if (data.region === 'A') {
    userPreference.value.timeOnA += data.duration
  } else if (data.region === 'B') {
    userPreference.value.timeOnB += data.duration
  }
}

function handleRegionSwitch({ from, to }) {
  if (diffOpen.value) return

  if (from === 'A' && to === 'B') {
    userPreference.value.leftToRight++
  } else if (from === 'B' && to === 'A') {
    userPreference.value.rightToLeft++
  }
}
</script>

<template>
  <div class="container">
    <FolderSelector
      v-if="showFolderSelector"
      @select="handleFolderSelect"
    />

    <header class="header">
      <h1>GazeVibe</h1>
      <p class="subtitle">眼动追踪 AI 编程助手</p>
      <p v-if="projectFolder" class="project-name">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
        {{ projectFolder.name }}
      </p>
      <div class="experiment-toggle">
        <span class="toggle-label">
          实验模式:
          {{ experimentMode === 'full' ? '完整' : experimentMode === 'manual' ? '手动' : '对照' }}
        </span>
        <button 
          @click.stop="toggleMode" 
          :class="['toggle-btn', experimentMode]"
        >
          {{ experimentMode === 'full' ? '眼动+自动' : experimentMode === 'manual' ? '眼动+手动' : '对照组' }}
        </button>
      </div>
    </header>

    <main class="main">
      <div class="sidebar" v-if="showFileExplorer && !showFolderSelector">
        <FileTree
          :files="indexedFiles"
          @select="handleFileSelect"
        />
      </div>

      <div class="content-area">
        <div class="main-content">
          <div class="explorer-toggle" v-if="!showFolderSelector">
            <button @click="showFileExplorer = !showFileExplorer" :class="{ active: showFileExplorer }">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              文件
            </button>
          </div>

          <FileViewer
            v-if="selectedFile && showFileExplorer"
            :file="selectedFile"
            class="file-viewer"
          />

          <div v-if="!currentQuestion && !answerA && !answerB && !selectedFile" class="welcome">
            <h2>欢迎使用 GazeVibe</h2>
            <p>输入你的编程问题，获取双份不同风格的回答</p>
            <p class="hint">系统会通过眼动追踪分析你的阅读偏好，优化后续回答</p>
          </div>

          <div v-if="currentQuestion" class="user-message">
            <div class="user-bubble">{{ currentQuestion }}</div>
            <div v-if="isLoading" class="waiting-indicator">
              <div class="spinner"></div>
              <span>AI 思考中...</span>
            </div>
          </div>

          <AnswerPanel
            v-if="answerA || answerB"
            ref="answerPanelRef"
            :answerA="answerA"
            :answerB="answerB"
            :is-loading="isLoading"
            :files="indexedFiles"
            :preferred-side="preferredSide"
            :auto-mode="autoMode"
            :confidence="confidence"
            @choice="handleChoice"
            @apply-change="handleApplyChange"
            @unapply-change="handleUnapplyChange"
            @diff-toggle="handleDiffToggle"
          />
        </div>

        <ChatInput
          :disabled="isLoading"
          @submit="handleSubmit"
        />
      </div>
    </main>

    <EyeTracker 
      v-show="isTreatment"
      ref="eyeTrackerRef"
      :diff-open="diffOpen"
      :diff-open-side="diffOpenSide"
      @data="handleEyeData"
      @region-switch="handleRegionSwitch"
    />

    <transition name="fade">
      <div v-if="savedToast" class="toast toast-success">{{ savedToast }}</div>
    </transition>

    <transition name="fade">
      <div v-if="choiceSaved" class="toast toast-pref">偏好已保存</div>
    </transition>
  </div>
</template>

<style scoped>
.container {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px;
  background: var(--bg0);
  color: var(--fg);
  font-size: var(--font-base);
}

.header {
  text-align: center;
  padding: 20px 0;
  border-bottom: 1px solid var(--bg3);
}

.header h1 {
  font-size: var(--font-4xl);
  color: var(--blue);
}

.subtitle {
  color: var(--grey1);
  margin-top: 8px;
  font-size: var(--font-lg);
}

.project-name {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
  color: var(--aqua);
  font-size: var(--font-sm);
}

.experiment-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 12px;
}

.toggle-label {
  font-size: var(--font-sm);
  color: var(--grey1);
}

.toggle-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 4px;
  font-size: var(--font-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn.treatment {
  background: var(--blue);
  color: var(--bg0);
}

.toggle-btn.full {
  background: var(--blue);
  color: var(--bg0);
}

.toggle-btn.manual {
  background: var(--aqua);
  color: var(--bg0);
}

.toggle-btn.control {
  background: var(--bg3);
  color: var(--fg);
}

.toggle-btn:hover {
  opacity: 0.85;
}

.main {
  flex: 1;
  display: flex;
  overflow: hidden;
  gap: 16px;
}

.sidebar {
  width: 280px;
  flex-shrink: 0;
  overflow: hidden;
}

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

.explorer-toggle {
  display: flex;
  justify-content: flex-start;
}

.explorer-toggle button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: var(--bg1);
  border: 1px solid var(--bg3);
  border-radius: 6px;
  color: var(--grey1);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.explorer-toggle button:hover {
  background: var(--bg2);
  color: var(--fg);
}

.explorer-toggle button.active {
  background: var(--bg-blue);
  border-color: var(--blue);
  color: var(--blue);
}

.file-viewer {
  flex: 1;
  min-height: 0;
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
  font-size: var(--font-3xl);
  margin-bottom: 16px;
  color: var(--fg);
}

.welcome p {
  color: var(--grey1);
  font-size: var(--font-lg);
}

.welcome .hint {
  margin-top: 24px;
  padding: 12px 24px;
  background: var(--bg1);
  border-radius: 8px;
  font-size: var(--font-base);
  color: var(--aqua);
}

.user-message {
  padding: 8px 0;
}

.user-bubble {
  display: inline-block;
  max-width: 80%;
  padding: 12px 18px;
  background: var(--bg-blue);
  border: 1px solid var(--blue);
  border-radius: 12px;
  border-bottom-left-radius: 4px;
  color: var(--fg);
  font-size: var(--font-base);
  line-height: 1.6;
  word-break: break-word;
}

.waiting-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
  padding-left: 4px;
  color: var(--grey1);
  font-size: var(--font-sm);
}

.waiting-indicator .spinner {
  width: 18px;
  height: 18px;
  border: 2px solid var(--bg3);
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.toast {
  position: fixed;
  right: 20px;
  padding: 10px 20px;
  background: var(--green);
  color: var(--bg0);
  border-radius: 6px;
  font-size: var(--font-sm);
  font-weight: 500;
  z-index: 200;
}

.toast-success {
  bottom: 80px;
}

.toast-pref {
  bottom: 130px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
