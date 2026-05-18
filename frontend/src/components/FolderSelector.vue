<script setup>
import { ref, onMounted } from 'vue'

const emit = defineEmits(['select', 'setProjectRoot'])

const isSupported = ref(true)
const isLoading = ref(false)
const error = ref('')
const folderName = ref('')
const projectRoot = ref('')
const rootError = ref('')
const rootSaving = ref(false)

onMounted(() => {
  if (!('showDirectoryPicker' in window)) {
    isSupported.value = false
    error.value = '你的浏览器不支持文件系统访问 API，请使用 Chrome 或 Edge'
  }
})

async function selectFolder() {
  if (!isSupported.value) return

  isLoading.value = true
  error.value = ''

  try {
    const dirHandle = await window.showDirectoryPicker({
      mode: 'readwrite'
    })

    folderName.value = dirHandle.name
    emit('select', dirHandle)
  } catch (err) {
    if (err.name === 'AbortError') {
      error.value = '已取消选择'
    } else {
      error.value = `选择文件夹失败: ${err.message}`
    }
  } finally {
    isLoading.value = false
  }
}

async function saveProjectRoot() {
  const path = projectRoot.value.trim()
  if (!path) {
    rootError.value = '请输入项目路径'
    return
  }
  rootSaving.value = true
  rootError.value = ''
  try {
    const res = await fetch('/api/project-root', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectRoot: path }),
    })
    const data = await res.json()
    if (data.success) {
      emit('setProjectRoot', data.projectRoot)
    } else {
      rootError.value = data.error || '设置失败'
    }
  } catch (e) {
    rootError.value = `请求失败: ${e.message}`
  } finally {
    rootSaving.value = false
  }
}
</script>

<template>
  <div class="folder-selector">
    <div class="selector-content">
      <div class="icon">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
        </svg>
      </div>

      <h2>选择项目文件夹</h2>
      <p class="description">选择一个本地项目文件夹，AI 将分析其中的代码并回答你的问题</p>

      <button
        class="select-btn"
        :disabled="!isSupported || isLoading"
        @click="selectFolder"
      >
        <span v-if="isLoading" class="loading"></span>
        <span v-else>{{ folderName || '选择文件夹' }}</span>
      </button>

      <p v-if="error" class="error">{{ error }}</p>

      <!-- 项目路径输入（用于后端文件读写） -->
      <div class="root-input-section">
        <p class="root-label">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
            <line x1="16" y1="13" x2="8" y2="13"/>
            <line x1="16" y1="17" x2="8" y2="17"/>
            <polyline points="10 9 9 9 8 9"/>
          </svg>
          项目文件系统路径（AI 可读写文件的根目录）
        </p>
        <div class="root-input-row">
          <input
            v-model="projectRoot"
            type="text"
            class="root-input"
            placeholder="例如: /home/user/my-project"
            @keyup.enter="saveProjectRoot"
          />
          <button
            class="root-save-btn"
            :disabled="rootSaving || !projectRoot.trim()"
            @click="saveProjectRoot"
          >
            <span v-if="rootSaving" class="mini-loading"></span>
            <span v-else>应用</span>
          </button>
        </div>
        <p v-if="rootError" class="error root-error">{{ rootError }}</p>
        <p class="root-hint">浏览器不暴露完整路径，手动填入以便后端读写文件（如 /home/lenitain/.projects/test4gaze）</p>
      </div>

      <p class="hint">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 16v-4M12 8h.01" />
        </svg>
        需要 Chrome 86+ 或 Edge 86+
      </p>
    </div>
  </div>
</template>

<style scoped>
.folder-selector {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.selector-content {
  background: var(--bg0);
  border-radius: 12px;
  padding: 48px;
  text-align: center;
  max-width: 480px;
  width: 90%;
}

.icon {
  color: var(--blue);
  margin-bottom: 24px;
}

h2 {
  font-size: var(--font-3xl);
  margin-bottom: 12px;
  color: var(--fg);
}

.description {
  color: var(--grey1);
  margin-bottom: 32px;
  line-height: 1.6;
  font-size: var(--font-lg);
}

.select-btn {
  background: var(--blue);
  color: var(--bg0);
  border: none;
  padding: 16px 36px;
  font-size: var(--font-lg);
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 200px;
}

.select-btn:hover:not(:disabled) {
  background: var(--aqua);
  transform: translateY(-1px);
}

.select-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading {
  display: inline-block;
  width: 20px;
  height: 20px;
  border: 2px solid transparent;
  border-top-color: var(--bg0);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.error {
  color: var(--red);
  margin-top: 16px;
  font-size: var(--font-sm);
}

.root-input-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--bg1);
  text-align: left;
}

.root-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--grey1);
  font-size: var(--font-sm);
  margin-bottom: 8px;
}

.root-input-row {
  display: flex;
  gap: 8px;
}

.root-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid var(--bg1);
  border-radius: 6px;
  background: var(--bg0);
  color: var(--fg);
  font-size: var(--font-md);
  font-family: monospace;
}

.root-input:focus {
  outline: none;
  border-color: var(--blue);
}

.root-save-btn {
  background: var(--blue);
  color: var(--bg0);
  border: none;
  padding: 10px 20px;
  font-size: var(--font-md);
  font-weight: 500;
  border-radius: 6px;
  cursor: pointer;
  white-space: nowrap;
}

.root-save-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.root-error {
  margin-top: 8px;
  font-size: var(--font-sm);
}

.root-hint {
  margin-top: 8px;
  color: var(--grey0);
  font-size: var(--font-xs);
  line-height: 1.4;
}

.mini-loading {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid transparent;
  border-top-color: var(--bg0);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  vertical-align: middle;
}

.hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-top: 24px;
  color: var(--grey0);
  font-size: var(--font-sm);
}
</style>
