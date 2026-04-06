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
const diffState = ref(null)
const fileChanges = ref(new Map())

const regionAId = 'answer-region-a'
const regionBId = 'answer-region-b'

const allCodeBlocks = computed(() => {
  const blocksA = props.answerA ? parseCodeBlocks(props.answerA) : []
  const blocksB = props.answerB ? parseCodeBlocks(props.answerB) : []

  const fileBlocks = new Map()

  for (const block of blocksA) {
    const filePath = extractFilePath(block, props.answerA, props.files || [])
    if (filePath && !fileBlocks.has(filePath)) {
      fileBlocks.set(filePath, {
        ...block,
        filePath,
        source: 'A'
      })
    }
  }

  for (const block of blocksB) {
    const filePath = extractFilePath(block, props.answerB, props.files || [])
    if (filePath && !fileBlocks.has(filePath)) {
      fileBlocks.set(filePath, {
        ...block,
        filePath,
        source: 'B'
      })
    }
  }

  return fileBlocks
})

const codeBlocksA = computed(() => {
  const blocks = []
  allCodeBlocks.value.forEach((block, filePath) => {
    if (block.source === 'A') {
      blocks.push(block)
    }
  })
  return blocks
})

const codeBlocksB = computed(() => {
  const blocks = []
  allCodeBlocks.value.forEach((block, filePath) => {
    if (block.source === 'B') {
      blocks.push(block)
    }
  })
  return blocks
})

function selectA() {
  selectedSide.value = 'A'
  emit('choice', 'A')
}

function selectB() {
  selectedSide.value = 'B'
  emit('choice', 'B')
}

function handleBlockClick(block) {
  if (!block.filePath) return

  const existing = fileChanges.value.get(block.filePath)

  if (existing) {
    fileChanges.value.delete(block.filePath)
    emit('unapply-change', { filePath: block.filePath })
    return
  }

  const file = props.files?.find(f => f.path === block.filePath)
  if (!file) return

  diffState.value = {
    filePath: block.filePath,
    originalContent: file.content,
    newContent: block.code
  }
  emit('diff-toggle', true)
}

function hideDiff() {
  diffState.value = null
  emit('diff-toggle', false)
}

function applyChange() {
  if (!diffState.value) return

  const { filePath, newContent } = diffState.value
  fileChanges.value.set(filePath, { content: newContent })

  emit('apply-change', {
    filePath,
    content: newContent
  })

  hideDiff()
}

function getBlockStatus(filePath) {
  return fileChanges.value.get(filePath) || null
}

function getBtnClass(filePath) {
  return fileChanges.value.has(filePath) ? 'pending' : ''
}

function getBtnText(filePath) {
  return fileChanges.value.has(filePath) ? '已暂存 (点击取消)' : '应用到文件'
}

defineExpose({
  regionAId,
  regionBId,
  getBlockStatus,
  commitAll: () => {
    fileChanges.value.clear()
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
                <span class="block-file">{{ block.filePath }}</span>
                <button
                  class="apply-btn"
                  :class="getBtnClass(block.filePath)"
                  @click="handleBlockClick(block)"
                >
                  {{ getBtnText(block.filePath) }}
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
                <span class="block-file">{{ block.filePath }}</span>
                <button
                  class="apply-btn"
                  :class="getBtnClass(block.filePath)"
                  @click="handleBlockClick(block)"
                >
                  {{ getBtnText(block.filePath) }}
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

.apply-btn:hover {
  background: var(--aqua);
}

.apply-btn.pending {
  background: var(--yellow);
  color: var(--bg0);
}

.apply-btn.pending:hover {
  background: var(--red);
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
