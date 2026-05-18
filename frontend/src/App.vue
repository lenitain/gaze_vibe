<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import AnswerPanel from './components/AnswerPanel.vue'
import ChatInput from './components/ChatInput.vue'
import EyeTracker from './components/EyeTracker.vue'
import FolderSelector from './components/FolderSelector.vue'
import FileTree from './components/FileTree.vue'
import FileViewer from './components/FileViewer.vue'
import { FileIndexer } from './utils/fileIndexer.js'
import { selectRelevantFiles, formatFilesForPrompt } from './utils/fileSelector.js'
import { parseCodeBlocks } from './utils/codeParser.js'
import { ALPHA, MIN_EYE_TIME, STRONG_WEIGHT, PERSONA_A_NAME, PERSONA_B_NAME, FONT_SCALE } from './config.js'
import { createError, fromApiError, fromFileError, ErrorTypes } from './utils/errors.js'

const isEyeTracking = ref(false)
const eyeTrackerRef = ref(null)
const answerPanelRef = ref(null)

const showFolderSelector = ref(true)
const projectName = ref('')
const projectFolder = ref(null)
const fileIndexer = new FileIndexer()
const indexedFiles = ref([])

const selectedFile = ref(null)
const showFileExplorer = ref(true)
const isLoading = ref(false)
const answerA = ref('')
const answerB = ref('')
const answerALength = ref(0)
const answerBLength = ref(0)
const answerSegmentsA = ref([])
const answerSegmentsB = ref([])
const abortController = ref(null)

// 临时累加器：SSE 流式期间累积数据，全部完成后才写入正式 ref
const _answerA = ref('')
const _answerB = ref('')
const _answerSegmentsA = ref([])
const _answerSegmentsB = ref([])

const currentQuestion = ref('')
const userPreference = ref({ finalChoice: null, timeOnA: 0, timeOnB: 0, leftToRight: 0, rightToLeft: 0 })
const conversationHistory = ref([])
const choiceSaved = ref(false)
const error = ref(null)

// Confidence inference (constants loaded from config.js)
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
  const prevMode = experimentMode.value
  const idx = experimentModes.indexOf(prevMode)
  experimentMode.value = experimentModes[(idx + 1) % experimentModes.length]

  // 切换模式时重置前后端建模状态，防止跨模式干扰
  emaBias.value = 0.5
  roundCount.value = 0
  fetch('/api/eye-model/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName: projectName.value })
  }).catch(() => {})

  // 停止当前追踪，等用户提交问题后再启动
  if (eyeTrackerRef.value) {
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
  }
}

function handleFileSelect(file) {
  selectedFile.value = file
}

async function handleFolderSelect(dirHandle) {
  projectFolder.value = dirHandle
  projectName.value = dirHandle.name
  showFolderSelector.value = false

  try {
    indexedFiles.value = await fileIndexer.indexDirectory(dirHandle)
    console.log(`Indexed ${indexedFiles.value.length} files from ${dirHandle.name}`)
  } catch (err) {
    console.error('Failed to index directory:', err)
  }
}


async function handleSubmit(prompt) {
  // 保存上一轮对话到历史
  if (currentQuestion.value && (answerA.value || answerB.value)) {
    const chosenSide = userPreference.value.finalChoice
    conversationHistory.value.push({
      question: currentQuestion.value,
      answerA: answerA.value,
      answerB: answerB.value,
      answerSegmentsA: [...answerSegmentsA.value],
      answerSegmentsB: [...answerSegmentsB.value],
      chosenSide,
      timestamp: Date.now(),
    })
  }

  currentQuestion.value = prompt
  isLoading.value = true
  answerPanelRef.value?.resetChoice()
  _answerA.value = ''
  _answerB.value = ''
  _answerSegmentsA.value = []
  _answerSegmentsB.value = []
  answerSegmentsA.value = []
  answerSegmentsB.value = []
  answerA.value = ''
  answerB.value = ''
  error.value = null

  const relevantFiles = selectRelevantFiles(prompt, indexedFiles.value)
  const contextFiles = formatFilesForPrompt(relevantFiles)

  // 只有上一轮有选择时才收集眼动数据，否则丢弃（用户未选择直接输入新问题）
  let eyeData = null
  const hadChoice = userPreference.value.finalChoice !== null
  if (hadChoice && eyeTrackerRef.value && isEyeTracking.value) {
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
    eyeData = {
      timeOnA: userPreference.value.timeOnA,
      timeOnB: userPreference.value.timeOnB,
      leftToRight: userPreference.value.leftToRight,
      rightToLeft: userPreference.value.rightToLeft,
      answerALength: answerALength.value,
      answerBLength: answerBLength.value,
      ...eyeTrackerRef.value.getAllMetrics()
    }
    userPreference.value.timeOnA = 0
    userPreference.value.timeOnB = 0
    userPreference.value.leftToRight = 0
    userPreference.value.rightToLeft = 0
  } else if (eyeTrackerRef.value && isEyeTracking.value) {
    // 无选择，停止追踪但不收集数据
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
    userPreference.value.timeOnA = 0
    userPreference.value.timeOnB = 0
    userPreference.value.leftToRight = 0
    userPreference.value.rightToLeft = 0
  }
  userPreference.value.finalChoice = null

  let eyeTrackingStarted = false
  abortController.value = new AbortController()

  try {
    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt, contextFiles,
        experimentMode: experimentMode.value,
        projectName: projectName.value,
        eyeData
      }),
      signal: abortController.value.signal
    })
    if (!response.ok) {
      throw new Error(`API 请求失败: ${response.status}`)
    }

    // 逐段读取 SSE 流（新事件协议）
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let segmentsArrived = 0
    // 当前累积的段落文本（用于分段显示）
    let currentSegId = ''
    let currentSegHint = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      // 按 SSE 双换行分割
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || '' // 保留最后一个不完整块

      for (const part of parts) {
        const dataLine = part.split('\n').find(l => l.startsWith('data: '))
        if (!dataLine) continue

        let parsed
        try {
          parsed = JSON.parse(dataLine.slice(6))
        } catch {
          continue
        }

        const eventType = parsed.type

        // --- segment_start: 子问题开始 ---
        if (eventType === 'segment_start') {
          currentSegId = parsed.id || ''
          currentSegHint = parsed.contextHint || ''
        }

        // --- text_delta: 文本增量（逐块推送，写入临时累加器） ---
        if (eventType === 'text_delta') {
          const style = parsed.style
          const text = parsed.text || ''
          if (style === 'detailed') {
            _answerA.value += text
          } else if (style === 'concise') {
            _answerB.value += text
          }
          answerALength.value = _answerA.value.length
          answerBLength.value = _answerB.value.length
        }

        // --- text_end: 文本块结束（写入临时累加器，不展示） ---
        if (eventType === 'text_end') {
          const style = parsed.style
          const segId = parsed.segmentId || currentSegId
          const segHint = currentSegHint

          if (style === 'detailed') {
            _answerSegmentsA.value = [..._answerSegmentsA.value, {
              id: segId,
              contextHint: segHint,
              content: parsed.fullText || _answerA.value
            }]
          } else if (style === 'concise') {
            _answerSegmentsB.value = [..._answerSegmentsB.value, {
              id: segId,
              contextHint: segHint,
              content: parsed.fullText || _answerB.value
            }]
          }
          segmentsArrived++
        }

        // --- segment_end: 子问题结束 ---
        if (eventType === 'segment_end') {
          // 重置段落缓存
          currentSegId = ''
          currentSegHint = ''
        }

        // --- eye_adjustment: 眼动状态更新 ---
        if (eventType === 'eye_adjustment') {
          console.log('[眼动状态]', parsed)
        }

        // --- done: 全部完成 → 一次性写入正式 ref，展示答案 ---
        if (eventType === 'done') {
          answerA.value = _answerA.value
          answerB.value = _answerB.value
          answerSegmentsA.value = _answerSegmentsA.value
          answerSegmentsB.value = _answerSegmentsB.value
          isLoading.value = false

          // 全部完成后才启动眼动追踪
          if (!eyeTrackingStarted && experimentMode.value !== 'control' && eyeTrackerRef.value && !isEyeTracking.value) {
            nextTick(() => {
              eyeTrackerRef.value.startTracking()
              isEyeTracking.value = true
              eyeTrackingStarted = true
              decisionStartTime.value = Date.now()
            })
          }
        }

        // --- error: 错误 ---
        if (eventType === 'error') {
          console.error('[SSE错误]', parsed.message)
          if (!error.value) {
            error.value = fromApiError(new Error(parsed.message || '未知错误'), '/api/ask')
          }
        }
      }
    }

    // 流结束，安全 fallback
    if (isLoading.value) isLoading.value = false

    if (segmentsArrived === 0) {
      throw new Error('未接收到任何回答')
    }

    const blocksA = parseCodeBlocks(answerA.value || '')
    const blocksB = parseCodeBlocks(answerB.value || '')
    if (blocksA.length === 0 && blocksB.length === 0) {
      console.warn('AI response contains no code blocks')
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      console.log('Generation stopped by user')
      return
    }
    console.error('Error:', err)
    error.value = fromApiError(err, '/api/ask')
    isLoading.value = false
  }
}

async function handleChoice(side) {
  userPreference.value.finalChoice = side
  const decisionTime = decisionStartTime.value
    ? Date.now() - decisionStartTime.value
    : null

  updateConfidence(0, 0, side)
  
  let eyeMetrics = null
  if (eyeTrackerRef.value && isEyeTracking.value) {
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
    eyeMetrics = eyeTrackerRef.value.getAllMetrics()
  }

  const blocks = side === 'A'
    ? answerPanelRef.value?.codeBlocksA
    : answerPanelRef.value?.codeBlocksB

  let writeResults = { ok: 0, fail: 0 }
  if (blocks) {
    const results = await Promise.allSettled(
      blocks.filter(b => b.filePath).map(b =>
        fileIndexer.writeFile(b.filePath, b.code)
      )
    )
    for (const r of results) {
      r.status === 'fulfilled' ? writeResults.ok++ : writeResults.fail++
    }
  }

  if (writeResults.fail > 0) {
    error.value = fromFileError(writeResults.fail)
  }

  fetch('/api/preference', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      preference: userPreference.value,
      experimentMode: experimentMode.value,
      projectName: projectName.value,
      currentQuestion: currentQuestion.value,
      emaBias: emaBias.value,
      confidence: confidence.value,
      decisionTime,
      eyeMetrics,
      answerALength: answerALength.value,
      answerBLength: answerBLength.value
    })
  }).then(() => {
    choiceSaved.value = true
    setTimeout(() => { choiceSaved.value = false }, 3000)
  }).catch(err => {
    console.error('Save preference failed:', err)
  })
}

function handleEyeData(data) {
  if (data.region === 'A') {
    userPreference.value.timeOnA += data.duration
  } else if (data.region === 'B') {
    userPreference.value.timeOnB += data.duration
  }
}

function stopGeneration() {
  if (abortController.value) {
    abortController.value.abort()
    abortController.value = null
  }
  isLoading.value = false
  _answerA.value = ''
  _answerB.value = ''
  _answerSegmentsA.value = []
  _answerSegmentsB.value = []
}

function handleRegionSwitch({ from, to }) {
  if (from === 'A' && to === 'B') {
    userPreference.value.leftToRight++
  } else if (from === 'B' && to === 'A') {
    userPreference.value.rightToLeft++
  }
}
</script>

<template>
  <div class="container" :style="{ '--font-scale': FONT_SCALE }">
    <FolderSelector
      v-if="showFolderSelector"
      @select="handleFolderSelect"
    />

    <header class="header">
      <div class="header-left">
        <h1>GazeVibe</h1>
        <button
          @click.stop="toggleMode"
          :class="['toggle-btn', experimentMode]"
        >
          {{ experimentMode === 'full' ? '眼动+自动' : experimentMode === 'manual' ? '眼动+手动' : '对照组' }}
        </button>
      </div>
    </header>

    <main class="main">
      <!-- 文件树: 覆盖层，保留输入框可见 -->
      <div v-if="showFileExplorer && !showFolderSelector" class="file-overlay" @click.self="showFileExplorer = false">
        <div class="file-drawer">
          <div class="file-drawer-header">
            <span class="file-drawer-title">项目文件</span>
            <button class="file-drawer-close" @click="showFileExplorer = false">✕</button>
          </div>
          <FileTree
            :files="indexedFiles"
            :project-folder="projectFolder"
            @select="(f) => { handleFileSelect(f); showFileExplorer = false; }"
          />
        </div>
      </div>

      <div class="content-area">
        <div class="chat-scroll">
          <!-- 历史对话 -->
          <div v-for="(item, idx) in conversationHistory" :key="idx" class="history-entry">
            <div class="user-message">
              <div class="user-bubble">{{ item.question }}</div>
            </div>
            <AnswerPanel
              :answerA="item.answerA"
              :answerB="item.answerB"
              :answerSegmentsA="item.answerSegmentsA"
              :answerSegmentsB="item.answerSegmentsB"
              :files="indexedFiles"
              :personaNameA="PERSONA_A_NAME"
              :personaNameB="PERSONA_B_NAME"
              :chosenSide="item.chosenSide"
            />
          </div>

          <!-- 当前对话 -->
          <template v-if="currentQuestion || answerA || answerB || isLoading">
            <div class="user-message">
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
              :answerSegmentsA="answerSegmentsA"
              :answerSegmentsB="answerSegmentsB"
              :personaNameA="PERSONA_A_NAME"
              :personaNameB="PERSONA_B_NAME"
              @choice="handleChoice"
            />
          </template>

          <!-- 空状态 -->
          <div v-if="!currentQuestion && !answerA && !answerB && conversationHistory.length === 0" class="welcome">
            <h2>欢迎使用 GazeVibe</h2>
            <p>输入你的编程问题，获取双份不同风格的回答</p>
            <p class="hint">系统会通过眼动追踪分析你的阅读偏好，优化后续回答</p>
          </div>
        </div>

        <div class="input-bar">
          <div class="explorer-toggle">
            <button @click="showFileExplorer = !showFileExplorer" :class="{ active: showFileExplorer }">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
              </svg>
              文件
            </button>
          </div>
          <ChatInput
            :disabled="isLoading"
            @submit="handleSubmit"
          />
          <button v-if="isLoading" class="stop-btn" @click="stopGeneration" title="停止生成">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
            停止
          </button>
        </div>

        <div v-if="selectedFile" class="file-viewer-overlay" @click.self="selectedFile = null">
          <FileViewer
            :file="selectedFile"
            class="file-viewer"
          />
        </div>
      </div>
    </main>

    <EyeTracker 
      v-show="isTreatment"
      ref="eyeTrackerRef"
      @data="handleEyeData"
      @region-switch="handleRegionSwitch"
    />

    <transition name="fade">
      <div v-if="choiceSaved" class="toast toast-pref">偏好已保存</div>
    </transition>
    <transition name="fade">
      <div v-if="error" :class="['toast', error.type === 'file' ? 'toast-warn' : 'toast-error']">{{ error.message }}</div>
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
  display: flex;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--bg3);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header h1 {
  font-size: var(--font-lg);
  color: var(--blue);
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

.content-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.chat-scroll {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding: 8px 12px;
}

.input-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--bg3);
  background: var(--bg0);
}

.explorer-toggle {
  flex-shrink: 0;
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
  white-space: nowrap;
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

/* 文件树覆盖层 */
.file-overlay {
  position: fixed;
  inset: 0;
  top: 48px;
  bottom: 0;
  z-index: 100;
  background: rgba(0, 0, 0, 0.4);
}

.file-drawer {
  width: 300px;
  height: 100%;
  background: var(--bg1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 2px 0 8px rgba(0,0,0,0.3);
}

.file-drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--bg3);
}

.file-drawer-title {
  font-size: var(--font-sm);
  font-weight: 600;
  color: var(--fg);
}

.file-drawer-close {
  background: none;
  border: none;
  color: var(--grey1);
  font-size: var(--font-lg);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
}

.file-drawer-close:hover {
  color: var(--fg);
}

.history-entry {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-viewer {
  flex: 1;
  min-height: 0;
}

.file-viewer-overlay {
  position: fixed;
  inset: 0;
  top: 48px;
  z-index: 200;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.file-viewer-overlay .file-viewer {
  max-width: 80vw;
  max-height: 80vh;
  background: var(--bg1);
  border-radius: 8px;
  padding: 16px;
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
  display: flex;
  justify-content: flex-end;
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

.stop-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--bg2);
  border: 1px solid var(--red);
  border-radius: 4px;
  color: var(--red);
  font-size: var(--font-xs);
  cursor: pointer;
  transition: all 0.15s;
}

.stop-btn:hover {
  background: var(--red);
  color: var(--bg0);
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

.toast-pref {
  bottom: 130px;
}

.toast-error {
  bottom: 90px;
  background: var(--red);
}

.toast-warn {
  bottom: 90px;
  background: var(--yellow);
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
