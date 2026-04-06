<script setup>
import { ref, computed } from 'vue'
import { parseCodeBlocks, extractFilePath, stripCodeBlocks, isFileApplicable } from '../utils/codeParser.js'
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
const expandedBlocks = ref(new Set())

const regionAId = 'answer-region-a'
const regionBId = 'answer-region-b'

const allResolvedBlocks = computed(() => {
  const fileIndex = props.files || []
  const usedPaths = new Set()
  const results = []

  function resolveAnswer(answer, source) {
    if (!answer) return
    const rawBlocks = parseCodeBlocks(answer)

    for (let index = 0; index < rawBlocks.length; index++) {
      const block = rawBlocks[index]
      const blockId = `${source}-${index}`
      const lang = (block.lang || '').toLowerCase()

      const isTerminal = ['bash', 'sh', 'shell', 'powershell', 'cmd', 'zsh', 'fish', 'console', 'terminal', 'bat'].includes(lang)

      let autoPath = null
      if (!isTerminal) {
        autoPath = extractFilePath(block, answer, fileIndex)
        if (autoPath && lang) {
          const ext = autoPath.split('.').pop().toLowerCase()
          const langExtMap = {
            javascript: ['js', 'mjs', 'cjs'], typescript: ['ts', 'mts', 'cts'],
            jsx: ['jsx'], tsx: ['tsx'], python: ['py'], rust: ['rs'],
            go: ['go'], java: ['java'], kotlin: ['kt'], swift: ['swift'],
            ruby: ['rb'], php: ['php'], html: ['html', 'htm'], css: ['css'],
            scss: ['scss'], less: ['less'], json: ['json'], yaml: ['yaml', 'yml'],
            toml: ['toml'], xml: ['xml'], sql: ['sql'], c: ['c'], cpp: ['cpp', 'cc', 'cxx'],
            h: ['h'], hpp: ['hpp'], csharp: ['cs'], dart: ['dart'], lua: ['lua'],
            r: ['r'], scala: ['scala'], vue: ['vue'], svelte: ['svelte'],
          }
          const validExts = langExtMap[lang]
          if (validExts && !validExts.includes(ext)) {
            autoPath = null
          }
        }
      }

      const filePath = autoPath

      if (!filePath) continue
      if (!isFileApplicable(block)) continue
      if (usedPaths.has(filePath)) continue

      if (filePath) usedPaths.add(filePath)

      results.push({
        ...block,
        blockId,
        filePath,
        autoMatched: !!autoPath,
        source
      })
    }
  }

  resolveAnswer(props.answerA, 'A')
  resolveAnswer(props.answerB, 'B')
  return results
})

const codeBlocksA = computed(() => allResolvedBlocks.value.filter(b => b.source === 'A'))
const codeBlocksB = computed(() => allResolvedBlocks.value.filter(b => b.source === 'B'))

const answerTextA = computed(() => props.answerA ? stripCodeBlocks(props.answerA) : '')
const answerTextB = computed(() => props.answerB ? stripCodeBlocks(props.answerB) : '')

const stagedCount = computed(() => fileChanges.value.size)

function selectA() {
  selectedSide.value = 'A'
  emit('choice', 'A')
}

function selectB() {
  selectedSide.value = 'B'
  emit('choice', 'B')
}

function toggleBlock(blockId) {
  if (expandedBlocks.value.has(blockId)) {
    expandedBlocks.value.delete(blockId)
  } else {
    expandedBlocks.value.add(blockId)
  }
}

function isBlockExpanded(blockId) {
  return expandedBlocks.value.has(blockId)
}

function handleApplyClick(block) {
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
  emit('apply-change', { filePath, content: newContent })
  hideDiff()
}

function getBtnClass(filePath) {
  return fileChanges.value.has(filePath) ? 'pending' : ''
}

function getBtnText(filePath) {
  return fileChanges.value.has(filePath) ? '已暂存 (取消)' : '暂存修改'
}

function getChooseBtnText() {
  if (stagedCount.value > 0) {
    return `选择此答案 (${stagedCount.value} 个文件待提交)`
  }
  return '选择此答案'
}

defineExpose({
  regionAId,
  regionBId,
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
        <span v-if="codeBlocksA.length > 0" class="block-count">{{ codeBlocksA.length }} 个文件</span>
      </div>
      <div class="answer-content" :class="{ selected: selectedSide === 'A' }">
        <div v-if="isLoading" class="loading">
          <div class="spinner"></div>
          <span>生成中...</span>
        </div>
        <template v-else>
          <div v-if="answerTextA" class="answer-text">{{ answerTextA }}</div>
          <div v-if="!answerA" class="placeholder">等待输入问题...</div>
          <div v-if="codeBlocksA.length > 0" class="code-blocks">
            <div
              v-for="block in codeBlocksA"
              :key="block.blockId"
              class="code-block"
              :class="{ staged: block.filePath && fileChanges.has(block.filePath) }"
            >
              <div class="block-header" @click="toggleBlock(block.blockId)">
                <span class="toggle-icon">{{ isBlockExpanded(block.blockId) ? '▼' : '▶' }}</span>
                <span class="block-lang">{{ block.lang || 'code' }}</span>
                <span class="block-file">{{ block.filePath }}</span>
                <span v-if="fileChanges.has(block.filePath)" class="staged-badge">已暂存</span>
                <button
                  class="apply-btn"
                  :class="getBtnClass(block.filePath)"
                  @click.stop="handleApplyClick(block)"
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
        :class="{ 'has-staged': stagedCount > 0 }"
        @click="selectA"
        :disabled="!answerA || isLoading"
      >
        {{ getChooseBtnText() }}
      </button>
    </div>

    <div class="divider"></div>

    <div class="answer-col" :id="regionBId">
      <div class="answer-header">
        <span class="badge concise">简洁解答</span>
        <span v-if="codeBlocksB.length > 0" class="block-count">{{ codeBlocksB.length }} 个文件</span>
      </div>
      <div class="answer-content" :class="{ selected: selectedSide === 'B' }">
        <div v-if="isLoading" class="loading">
          <div class="spinner"></div>
          <span>生成中...</span>
        </div>
        <template v-else>
          <div v-if="answerTextB" class="answer-text">{{ answerTextB }}</div>
          <div v-if="!answerB" class="placeholder">等待输入问题...</div>
          <div v-if="codeBlocksB.length > 0" class="code-blocks">
            <div
              v-for="block in codeBlocksB"
              :key="block.blockId"
              class="code-block"
              :class="{ staged: block.filePath && fileChanges.has(block.filePath) }"
            >
              <div class="block-header" @click="toggleBlock(block.blockId)">
                <span class="toggle-icon">{{ isBlockExpanded(block.blockId) ? '▼' : '▶' }}</span>
                <span class="block-lang">{{ block.lang || 'code' }}</span>
                <span class="block-file">{{ block.filePath }}</span>
                <span v-if="fileChanges.has(block.filePath)" class="staged-badge">已暂存</span>
                <button
                  class="apply-btn"
                  :class="getBtnClass(block.filePath)"
                  @click.stop="handleApplyClick(block)"
                >
                  {{ getBtnText(block.filePath) }}
                </button>
              </div>
              <div v-if="isBlockExpanded(block.blockId)" class="block-code">
                <pre>{{ block.code }}</pre>
              </div>
            </div>
          </div>
        </template>
      </div>
      <button
        class="choose-btn"
        :class="{ 'has-staged': stagedCount > 0 }"
        @click="selectB"
        :disabled="!answerB || isLoading"
      >
        {{ getChooseBtnText() }}
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
  display: flex;
  align-items: center;
  gap: 10px;
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

.block-count {
  font-size: var(--font-xs);
  color: var(--grey1);
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

.answer-text {
  margin-bottom: 16px;
}

.placeholder {
  color: var(--grey1);
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
  margin-top: 8px;
  border-top: 1px solid var(--bg3);
  padding-top: 12px;
}

.code-block {
  margin-bottom: 8px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--bg3);
}

.code-block.staged {
  border-color: var(--yellow);
}

.block-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg2);
  cursor: pointer;
  transition: background 0.15s;
}

.block-header:hover {
  background: var(--bg3);
}

.toggle-icon {
  font-size: 10px;
  color: var(--grey1);
  width: 14px;
  text-align: center;
  flex-shrink: 0;
}

.block-lang {
  font-size: var(--font-xs);
  color: var(--grey1);
  padding: 2px 8px;
  background: var(--bg3);
  border-radius: 4px;
  flex-shrink: 0;
}

.block-file {
  font-size: var(--font-xs);
  color: var(--aqua);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.staged-badge {
  font-size: 11px;
  color: var(--bg0);
  background: var(--yellow);
  padding: 1px 6px;
  border-radius: 3px;
  flex-shrink: 0;
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
  flex-shrink: 0;
}

.apply-btn:hover {
  background: var(--aqua);
}

.apply-btn.pending {
  background: var(--red);
  color: var(--bg0);
}

.apply-btn.pending:hover {
  opacity: 0.85;
}

.block-code {
  padding: 12px;
  background: var(--bg0);
  border-top: 1px solid var(--bg3);
  max-height: 400px;
  overflow-y: auto;
}

.block-code pre {
  margin: 0;
  font-size: var(--font-xs);
  line-height: 1.5;
  white-space: pre;
  color: var(--fg);
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

.choose-btn.has-staged {
  background: var(--green);
}

.choose-btn.has-staged:hover:not(:disabled) {
  background: var(--aqua);
}

.choose-btn:disabled {
  background: var(--bg3);
  color: var(--grey1);
  cursor: not-allowed;
}
</style>
