<script setup>
import { ref, watch, computed } from 'vue'
import { parseCodeBlocks, extractFilePath } from '../utils/codeParser.js'
import DiffPreview from './DiffPreview.vue'

const props = defineProps({
  answerA: String,
  answerB: String,
  isLoading: Boolean,
  files: Array
})

const emit = defineEmits(['choice', 'apply-change', 'unapply-change', 'diff-toggle'])

const selectedSide = ref(null)
const codeBlocksA = ref([])
const codeBlocksB = ref([])
const diffState = ref(null)
const pendingChanges = ref(new Map())

const regionAId = 'answer-region-a'
const regionBId = 'answer-region-b'

watch(() => props.answerA, (text) => {
  if (text) {
    codeBlocksA.value = parseCodeBlocks(text).map(block => ({
      ...block,
      filePath: extractFilePath(block, text, props.files || [])
    }))
  } else {
    codeBlocksA.value = []
  }
}, { immediate: true })

watch(() => props.answerB, (text) => {
  if (text) {
    codeBlocksB.value = parseCodeBlocks(text).map(block => ({
      ...block,
      filePath: extractFilePath(block, text, props.files || [])
    }))
  } else {
    codeBlocksB.value = []
  }
}, { immediate: true })

function selectA() {
  selectedSide.value = 'A'
  emit('choice', 'A')
}

function selectB() {
  selectedSide.value = 'B'
  emit('choice', 'B')
}

function handleBlockClick(block, source) {
  if (!block.filePath) return

  const existing = pendingChanges.value.get(block.filePath)

  if (existing && existing.source === source) {
    pendingChanges.value.delete(block.filePath)
    emit('unapply-change', { filePath: block.filePath })
    return
  }

  const file = props.files?.find(f => f.path === block.filePath)
  if (!file) return

  diffState.value = {
    filePath: block.filePath,
    originalContent: file.content,
    newContent: block.code,
    source
  }
  emit('diff-toggle', true)
}

function hideDiff() {
  diffState.value = null
  emit('diff-toggle', false)
}

function applyChange() {
  if (!diffState.value) return

  const { filePath, newContent, source } = diffState.value
  pendingChanges.value.set(filePath, { content: newContent, source })

  emit('apply-change', {
    filePath,
    content: newContent
  })

  hideDiff()
}

function getBlockStatus(filePath) {
  return pendingChanges.value.get(filePath) || null
}

function getBlockBtnClass(filePath, source) {
  const status = pendingChanges.value.get(filePath)
  if (!status) return ''
  if (status.source === source) return 'pending'
  return 'other-side'
}

function getBlockBtnText(filePath, source) {
  const status = pendingChanges.value.get(filePath)
  if (!status) return '应用到文件'
  if (status.source === source) return '已暂存 (点击取消)'
  return '另一版本已暂存'
}

defineExpose({
  regionAId,
  regionBId,
  getBlockStatus,
  commitAll: () => {
    pendingChanges.value.clear()
  }
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
        <template v-else>
          <pre>{{ answerA || '等待输入问题...' }}</pre>
          <div v-if="codeBlocksA.length > 0" class="code-blocks">
            <div
              v-for="(block, index) in codeBlocksA"
              :key="index"
              class="code-block"
            >
              <div class="block-header">
                <span class="block-lang">{{ block.lang || 'code' }}</span>
                <span v-if="block.filePath" class="block-file">{{ block.filePath }}</span>
                <button
                  v-if="block.filePath"
                  class="apply-btn"
                  :class="getBlockBtnClass(block.filePath, 'A')"
                  :disabled="getBlockStatus(block.filePath)?.source === 'B'"
                  @click="handleBlockClick(block, 'A')"
                >
                  {{ getBlockBtnText(block.filePath, 'A') }}
                </button>
              </div>
            </div>
          </div>
        </template>
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
        <template v-else>
          <pre>{{ answerB || '等待输入问题...' }}</pre>
          <div v-if="codeBlocksB.length > 0" class="code-blocks">
            <div
              v-for="(block, index) in codeBlocksB"
              :key="index"
              class="code-block"
            >
              <div class="block-header">
                <span class="block-lang">{{ block.lang || 'code' }}</span>
                <span v-if="block.filePath" class="block-file">{{ block.filePath }}</span>
                <button
                  v-if="block.filePath"
                  class="apply-btn"
                  :class="getBlockBtnClass(block.filePath, 'B')"
                  :disabled="getBlockStatus(block.filePath)?.source === 'A'"
                  @click="handleBlockClick(block, 'B')"
                >
                  {{ getBlockBtnText(block.filePath, 'B') }}
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
      <button
        class="choose-btn"
        @click="selectB"
        :disabled="!answerB || isLoading"
      >
        选择此答案
      </button>
    </div>

    <DiffPreview
      v-if="diffState"
      :file-path="diffState.filePath"
      :original-content="diffState.originalContent"
      :new-content="diffState.newContent"
      :on-apply="applyChange"
      :on-cancel="hideDiff"
    />
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
  padding: 5px 14px;
  border-radius: 4px;
  font-size: var(--font-sm);
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
  font-size: var(--font-base);
  line-height: 1.7;
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

.code-blocks {
  margin-top: 16px;
  border-top: 1px solid var(--bg3);
  padding-top: 12px;
}

.code-block {
  margin-bottom: 8px;
}

.block-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg2);
  border-radius: 6px;
}

.block-lang {
  font-size: var(--font-xs);
  color: var(--grey1);
  padding: 2px 8px;
  background: var(--bg3);
  border-radius: 4px;
}

.block-file {
  font-size: var(--font-xs);
  color: var(--aqua);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.apply-btn {
  padding: 4px 10px;
  background: var(--green);
  color: var(--bg0);
  border: none;
  border-radius: 4px;
  font-size: var(--font-xs);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}

.apply-btn:hover:not(:disabled) {
  background: var(--aqua);
}

.apply-btn.pending {
  background: var(--yellow);
  color: var(--bg0);
}

.apply-btn.pending:hover {
  background: var(--red);
}

.apply-btn.other-side {
  background: var(--bg3);
  color: var(--grey1);
  cursor: not-allowed;
}

.choose-btn {
  margin: 12px 16px;
  padding: 12px 18px;
  background: var(--blue);
  color: var(--bg0);
  border: none;
  border-radius: 6px;
  font-size: var(--font-base);
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
