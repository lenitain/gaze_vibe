<script setup>
import { ref, computed } from 'vue'
import { generateDiff } from '../utils/codeParser.js'

const props = defineProps({
  filePath: String,
  originalContent: String,
  newContent: String,
  onApply: Function,
  onCancel: Function
})

const isApplying = ref(false)

const diff = computed(() => {
  if (!props.originalContent || !props.newContent) return []
  return generateDiff(props.originalContent, props.newContent)
})

const stats = computed(() => {
  let added = 0, removed = 0
  for (const d of diff.value) {
    if (d.type === 'added') added++
    if (d.type === 'removed') removed++
  }
  return { added, removed }
})

async function handleApply() {
  isApplying.value = true
  try {
    await props.onApply()
  } finally {
    isApplying.value = false
  }
}
</script>

<template>
  <div class="diff-overlay">
    <div class="diff-modal">
      <div class="diff-header">
        <h3>确认修改</h3>
        <span class="file-path">{{ filePath }}</span>
        <div class="stats">
          <span class="added">+{{ stats.added }}</span>
          <span class="removed">-{{ stats.removed }}</span>
        </div>
      </div>

      <div class="diff-content">
        <div
          v-for="(line, index) in diff"
          :key="index"
          class="diff-line"
          :class="line.type"
        >
          <span class="line-num">{{ line.lineNum || '' }}</span>
          <span class="line-prefix">{{ line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' ' }}</span>
          <span class="line-text">{{ line.line }}</span>
        </div>
      </div>

      <div class="diff-actions">
        <button class="cancel-btn" @click="onCancel">取消</button>
        <button class="apply-btn" @click="handleApply" :disabled="isApplying">
          {{ isApplying ? '应用中...' : '应用修改' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.diff-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 500;
}

.diff-modal {
  background: var(--bg0);
  border-radius: 12px;
  width: 90%;
  max-width: 800px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.diff-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 20px;
  background: var(--bg1);
  border-bottom: 1px solid var(--bg3);
}

.diff-header h3 {
  font-size: var(--font-lg);
  color: var(--fg);
  margin: 0;
}

.file-path {
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: var(--font-sm);
  color: var(--aqua);
  flex: 1;
}

.stats {
  display: flex;
  gap: 12px;
  font-size: var(--font-sm);
  font-family: 'Fira Code', 'Consolas', monospace;
}

.added { color: var(--green); }
.removed { color: var(--red); }

.diff-content {
  flex: 1;
  overflow-y: auto;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: var(--font-sm);
  line-height: 1.6;
}

.diff-line {
  display: flex;
  padding: 0 16px;
}

.diff-line.added {
  background: rgba(167, 192, 128, 0.15);
}

.diff-line.removed {
  background: rgba(230, 126, 128, 0.15);
}

.line-num {
  width: 40px;
  text-align: right;
  padding-right: 12px;
  color: var(--grey0);
  user-select: none;
  flex-shrink: 0;
}

.line-prefix {
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

.diff-line.added .line-prefix { color: var(--green); }
.diff-line.removed .line-prefix { color: var(--red); }

.line-text {
  flex: 1;
  white-space: pre;
  color: var(--fg);
}

.diff-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  background: var(--bg1);
  border-top: 1px solid var(--bg3);
}

.cancel-btn {
  padding: 10px 20px;
  background: var(--bg3);
  color: var(--fg);
  border: none;
  border-radius: 6px;
  font-size: var(--font-sm);
  cursor: pointer;
}

.cancel-btn:hover {
  background: var(--bg4);
}

.apply-btn {
  padding: 10px 20px;
  background: var(--green);
  color: var(--bg0);
  border: none;
  border-radius: 6px;
  font-size: var(--font-sm);
  font-weight: 500;
  cursor: pointer;
}

.apply-btn:hover:not(:disabled) {
  background: var(--aqua);
}

.apply-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
