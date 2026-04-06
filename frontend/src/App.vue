<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
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

const showFolderSelector = ref(true)
const projectFolder = ref(null)
const fileIndexer = new FileIndexer()
const indexedFiles = ref([])

const selectedFile = ref(null)
const showFileExplorer = ref(true)

const answerA = ref('')
const answerB = ref('')
const isLoading = ref(false)

const userPreference = ref({
  timeOnA: 0,
  timeOnB: 0,
  leftToRight: 0,
  rightToLeft: 0,
  finalChoice: null
})

const choiceSaved = ref(false)

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
  isLoading.value = true

  try {
    const relevantFiles = selectRelevantFiles(prompt, indexedFiles.value)
    const contextFiles = formatFilesForPrompt(relevantFiles)

    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt,
        preference: userPreference.value,
        contextFiles
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

async function handleChoice(side) {
  userPreference.value.finalChoice = side
  if (eyeTrackerRef.value) {
    eyeTrackerRef.value.stopTracking()
    isEyeTracking.value = false
  }

  try {
    await fetch('/api/preference', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ preference: userPreference.value })
    })
    choiceSaved.value = true
    setTimeout(() => { choiceSaved.value = false }, 3000)
  } catch (err) {
    console.error('Save preference failed:', err)
  }
}

function handleEyeData(data) {
  if (data.region === 'A') {
    userPreference.value.timeOnA += data.duration
  } else if (data.region === 'B') {
    userPreference.value.timeOnB += data.duration
  }
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
        ~/{{ projectFolder.name }}
      </p>
    </header>

    <main class="main">
      <div class="sidebar" v-if="showFileExplorer && !showFolderSelector">
        <FileTree
          :files="indexedFiles"
          @select="handleFileSelect"
        />
      </div>

      <div class="content-area">
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

        <div v-if="!answerA && !answerB && !selectedFile" class="welcome">
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
      </div>
    </main>

    <EyeTracker 
      ref="eyeTrackerRef"
      @data="handleEyeData"
      @region-switch="handleRegionSwitch"
    />

    <transition name="fade">
      <div v-if="choiceSaved" class="toast">偏好已保存</div>
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
}

.header {
  text-align: center;
  padding: 20px 0;
  border-bottom: 1px solid var(--bg3);
}

.header h1 {
  font-size: 28px;
  color: var(--blue);
}

.subtitle {
  color: var(--grey1);
  margin-top: 8px;
}

.project-name {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 8px;
  color: var(--aqua);
  font-size: 14px;
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
  gap: 12px;
}

.explorer-toggle {
  display: flex;
  justify-content: flex-start;
}

.explorer-toggle button {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg1);
  border: 1px solid var(--bg3);
  border-radius: 6px;
  color: var(--grey1);
  font-size: 12px;
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
  font-size: 24px;
  margin-bottom: 16px;
  color: var(--fg);
}

.welcome p {
  color: var(--grey1);
}

.welcome .hint {
  margin-top: 24px;
  padding: 12px 24px;
  background: var(--bg1);
  border-radius: 8px;
  font-size: 14px;
  color: var(--aqua);
}

.toast {
  position: fixed;
  bottom: 80px;
  right: 20px;
  padding: 10px 20px;
  background: var(--green);
  color: var(--bg0);
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  z-index: 200;
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
