<script setup>
import { ref, onMounted } from 'vue'

const emit = defineEmits(['select'])

const isSupported = ref(true)
const isLoading = ref(false)
const error = ref('')
const folderName = ref('')

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
