<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  answerA: String,
  answerB: String,
  isLoading: Boolean
})

const emit = defineEmits(['choice'])

const selectedSide = ref(null)

// 提供给 EyeTracker 识别的区域 ID
const regionAId = 'answer-region-a'
const regionBId = 'answer-region-b'

function selectA() {
  selectedSide.value = 'A'
  emit('choice', 'A')
}

function selectB() {
  selectedSide.value = 'B'
  emit('choice', 'B')
}

// 暴露区域元素 ID 给父组件
defineExpose({
  regionAId,
  regionBId
})
</script>

<template>
  <div class="answer-panel">
    <div class="answer-col" :id="regionAId">
      <div class="answer-header">
        <span class="badge detailed">详细解答</span>
      </div>
      <div class="answer-content" :class="{ selected: selectedSide === 'A' }">
        <div v-if="isLoading" class="loading">
          <div class="spinner"></div>
          <span>生成中...</span>
        </div>
        <pre v-else>{{ answerA || '等待输入问题...' }}</pre>
      </div>
      <button 
        class="choose-btn" 
        @click="selectA"
        :disabled="!answerA || isLoading"
      >
        选择此答案
      </button>
    </div>

    <div class="divider"></div>

    <div class="answer-col" :id="regionBId">
      <div class="answer-header">
        <span class="badge concise">简洁解答</span>
      </div>
      <div class="answer-content" :class="{ selected: selectedSide === 'B' }">
        <div v-if="isLoading" class="loading">
          <div class="spinner"></div>
          <span>生成中...</span>
        </div>
        <pre v-else>{{ answerB || '等待输入问题...' }}</pre>
      </div>
      <button 
        class="choose-btn" 
        @click="selectB"
        :disabled="!answerB || isLoading"
      >
        选择此答案
      </button>
    </div>
  </div>
</template>

<style scoped>
.answer-panel {
  flex: 1;
  display: flex;
  gap: 16px;
  overflow: hidden;
  margin-bottom: 16px;
}

.answer-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg1);
  border-radius: 12px;
  overflow: hidden;
}

.answer-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--bg3);
}

.badge {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.badge.detailed {
  background: var(--bg-blue);
  color: var(--blue);
}

.badge.concise {
  background: var(--bg-green);
  color: var(--green);
}

.answer-content {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--fg);
}

.answer-content.selected {
  border: 2px solid var(--aqua);
}

.answer-content pre {
  margin: 0;
}

.loading {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--grey1);
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--bg3);
  border-top-color: var(--blue);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.divider {
  width: 2px;
  background: var(--bg3);
}

.choose-btn {
  margin: 12px 16px;
  padding: 10px 16px;
  background: var(--blue);
  color: var(--bg0);
  border: none;
  border-radius: 6px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.choose-btn:hover:not(:disabled) {
  background: var(--aqua);
  transform: translateY(-1px);
}

.choose-btn:disabled {
  background: var(--bg3);
  color: var(--grey1);
  cursor: not-allowed;
}
</style>
