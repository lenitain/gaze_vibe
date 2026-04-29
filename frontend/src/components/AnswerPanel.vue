<script setup>
import { ref, computed, watch } from 'vue'
import { parseCodeBlocks, extractFilePath, stripCodeBlocks, isFileApplicable } from '../utils/codeParser.js'

const props = defineProps({
  answerA: String,
  answerB: String,
  isLoading: Boolean,
  files: Array,
  preferredSide: String,
  autoMode: Boolean,
  confidence: Number,
  answerSegmentsA: Array,
  answerSegmentsB: Array
})

const emit = defineEmits(['choice'])

const selectedSide = ref(null)
const choiceDisabled = ref(false)
let autoSelected = false
const overridden = ref(false)
const effectiveAutoMode = computed(() => props.autoMode && !overridden.value)

const expandedA = ref(true)
const expandedB = ref(true)

const displayTextA = computed(() => props.answerA ? answerTextA.value : '')

const displayTextB = computed(() => props.answerB ? answerTextB.value : '')

const displaySegmentsA = computed(() => (props.answerSegmentsA && props.answerSegmentsA.length > 1) ? props.answerSegmentsA : null)

const displaySegmentsB = computed(() => (props.answerSegmentsB && props.answerSegmentsB.length > 1) ? props.answerSegmentsB : null)

const hasSegments = computed(() =>
  (props.answerSegmentsA && props.answerSegmentsA.length > 1) ||
  (props.answerSegmentsB && props.answerSegmentsB.length > 1)
)

watch(() => props.autoMode, (isAuto) => {
  if (isAuto && props.preferredSide && !selectedSide.value && !autoSelected) {
    selectedSide.value = props.preferredSide
    choiceDisabled.value = true
    autoSelected = true
    overridden.value = false
  }
}, { immediate: true })

function handleOverride() {
  selectedSide.value = null
  choiceDisabled.value = false
  autoSelected = false
  overridden.value = true
}

const regionAId = 'answer-region-a'
const regionBId = 'answer-region-b'

const allResolvedBlocks = computed(() => {
  const fileIndex = props.files || []
  const usedPathsMap = { A: new Set(), B: new Set() }
  const results = []

  function resolveAnswer(answer, source) {
    if (!answer) return
    const usedPaths = usedPathsMap[source]
    const rawBlocks = parseCodeBlocks(answer)

    for (let index = 0; index < rawBlocks.length; index++) {
      const block = rawBlocks[index]
      const blockId = `${source}-${index}`
      const lang = (block.lang || '').toLowerCase()

      const isTerminal = ['bash', 'sh', 'shell', 'powershell', 'cmd', 'zsh', 'fish', 'console', 'terminal', 'bat'].includes(lang)

      let autoPath = null
      if (!isTerminal) {
        autoPath = extractFilePath(block, answer, fileIndex)

        if (!autoPath && lang) {
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
          const exts = langExtMap[lang]
          if (exts) {
            const match = fileIndex.find(f => exts.includes(f.path.split('.').pop().toLowerCase()))
            if (match) autoPath = match.path
          }
        }

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

      if (isTerminal) continue
      if (!isFileApplicable(block, !!filePath)) continue
      if (filePath && usedPaths.has(filePath)) continue

      if (filePath) usedPaths.add(filePath)

      results.push({
        ...block,
        blockId,
        filePath,
        autoMatched: !!autoPath,
        source
      })    }
  }

  resolveAnswer(props.answerA, 'A')
  resolveAnswer(props.answerB, 'B')

  if (fileIndex.length > 0) {
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

    for (const source of ['A', 'B']) {
      const usedPaths = usedPathsMap[source]
      const panelBlocks = results.filter(b => b.source === source)
      const hasPath = panelBlocks.some(b => b.filePath)
      if (hasPath) continue

      const noPathBlock = panelBlocks.find(b => !b.filePath && b.lang && langExtMap[b.lang.toLowerCase()])
      if (noPathBlock) {
        const exts = langExtMap[noPathBlock.lang.toLowerCase()]
        const match = fileIndex.find(f => exts.includes(f.path.split('.').pop().toLowerCase()))
        if (match && !usedPaths.has(match.path)) {
          noPathBlock.filePath = match.path
          noPathBlock.autoMatched = true
          usedPaths.add(match.path)
        }
      }
    }
  }

  return results
})

const codeBlocksA = computed(() => allResolvedBlocks.value.filter(b => b.source === 'A'))
const codeBlocksB = computed(() => allResolvedBlocks.value.filter(b => b.source === 'B').map(b => ({ ...b, _panel: 'B' })))

const answerTextA = computed(() => props.answerA ? stripCodeBlocks(props.answerA) : '')
const answerTextB = computed(() => props.answerB ? stripCodeBlocks(props.answerB) : '')

function selectA() {
  selectedSide.value = 'A'
  choiceDisabled.value = true
  emit('choice', 'A')
}

function selectB() {
  selectedSide.value = 'B'
  choiceDisabled.value = true
  emit('choice', 'B')
}

function getChooseBtnText(side) {
  if (choiceDisabled.value) {
    if (selectedSide.value === side) {
      return '已选择'
    }
    return '未选择'
  }
  return '选择此答案'
}

defineExpose({
  regionAId,
  regionBId,
  codeBlocksA,
  codeBlocksB,
  resetChoice() {
    selectedSide.value = null
    choiceDisabled.value = false
    autoSelected = false
    overridden.value = false
  }
})
</script>

<template>
  <div class="answer-panel">
    <div
      class="answer-col"
      :id="regionAId"
      :class="{
        selected: selectedSide === 'A',
        hidden: choiceDisabled && selectedSide !== 'A' && !effectiveAutoMode,
        collapsed: effectiveAutoMode && preferredSide === 'B',
        expanded: effectiveAutoMode && preferredSide === 'A'
      }"
    >
      <div class="answer-header">
        <span class="badge detailed">详细解答</span>
        <span v-if="codeBlocksA.length > 0" class="block-count">{{ codeBlocksA.length }} 个文件</span>
        <span v-if="hasSegments && answerSegmentsA && answerSegmentsA.length > 1" class="segment-count">{{ answerSegmentsA.length }} 个片段</span>
        <span v-if="preferredSide === 'A' && !effectiveAutoMode" class="preference-hint">推断偏好</span>
      </div>
      <div class="answer-content" :class="{ selected: selectedSide === 'A' }">
        <div v-if="isLoading" class="loading">
          <div class="spinner"></div>
          <span>生成中...</span>
        </div>
        <template v-else>
          <div v-if="!answerA" class="placeholder">等待输入问题...</div>
          <template v-else>
            <template v-if="displaySegmentsA">
              <div class="text-container">
                <div
                  v-for="(seg, idx) in displaySegmentsA"
                  :key="seg.id || idx"
                  class="segment-block"
                >
                  <div v-if="seg.contextHint" class="segment-hint">{{ seg.contextHint }}</div>
                  <div class="answer-text" v-html="seg.content"></div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="text-container">
                <div class="answer-text" v-html="displayTextA"></div>
              </div>
            </template>

            <div v-if="codeBlocksA.length > 0" class="code-blocks">
              <div
                v-for="block in codeBlocksA"
                :key="block.blockId"
                class="code-block"
              >
                <div class="block-header">
                  <span class="block-lang">{{ block.lang || 'code' }}</span>
                  <span v-if="block.filePath" class="block-file">{{ block.filePath }}</span>
                </div>
                <div class="block-code">
                  <pre>{{ block.code }}</pre>
                </div>
              </div>
            </div>
          </template>
        </template>
      </div>
      <button
        class="choose-btn"
        :class="{ selected: selectedSide === 'A' }"
        @click="selectA"
        :disabled="!answerA || isLoading || choiceDisabled"
      >
        {{ getChooseBtnText('A') }}
      </button>
    </div>

    <div class="divider" :class="{ hidden: choiceDisabled && !autoMode }"></div>

    <div
      class="answer-col"
      :id="regionBId"
      :class="{
        selected: selectedSide === 'B',
        hidden: choiceDisabled && selectedSide !== 'B' && !autoMode,
        collapsed: autoMode && preferredSide === 'A',
        expanded: autoMode && preferredSide === 'B'
      }"
    >
      <div class="answer-header">
        <span class="badge concise">简洁解答</span>
        <span v-if="codeBlocksB.length > 0" class="block-count">{{ codeBlocksB.length }} 个文件</span>
        <span v-if="hasSegments && answerSegmentsB && answerSegmentsB.length > 1" class="segment-count">{{ answerSegmentsB.length }} 个片段</span>
        <span v-if="preferredSide === 'B' && !autoMode" class="preference-hint">推断偏好</span>
      </div>
      <div class="answer-content" :class="{ selected: selectedSide === 'B' }">
        <div v-if="isLoading" class="loading">
          <div class="spinner"></div>
          <span>生成中...</span>
        </div>
        <template v-else>
          <div v-if="!answerB" class="placeholder">等待输入问题...</div>
          <template v-else>
            <template v-if="displaySegmentsB">
              <div class="text-container">
                <div
                  v-for="(seg, idx) in displaySegmentsB"
                  :key="seg.id || idx"
                  class="segment-block"
                >
                  <div v-if="seg.contextHint" class="segment-hint">{{ seg.contextHint }}</div>
                  <div class="answer-text" v-html="seg.content"></div>
                </div>
              </div>
            </template>
            <template v-else>
              <div class="text-container">
                <div class="answer-text" v-html="displayTextB"></div>
              </div>
            </template>

            <div v-if="codeBlocksB.length > 0" class="code-blocks">
              <div
                v-for="block in codeBlocksB"
                :key="block.blockId"
                class="code-block"
              >
                <div class="block-header">
                  <span class="block-lang">{{ block.lang || 'code' }}</span>
                  <span v-if="block.filePath" class="block-file">{{ block.filePath }}</span>
                </div>
                <div class="block-code">
                  <pre>{{ block.code }}</pre>
                </div>
              </div>
            </div>
          </template>
        </template>
      </div>
      <button
        class="choose-btn"
        :class="{ selected: selectedSide === 'B' }"
        @click="selectB"
        :disabled="!answerB || isLoading || choiceDisabled"
      >
        {{ getChooseBtnText('B') }}
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
  overflow-y: auto;
  transition: all 0.4s ease;
}

.answer-col.hidden {
  flex: 0;
  width: 0;
  opacity: 0;
  overflow: hidden;
  padding: 0;
  margin: 0;
}

.answer-col.selected {
  flex: 1;
}

.answer-col.collapsed {
  flex: 0.3;
  min-width: 200px;
}

.answer-col.expanded {
  flex: 0.7;
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

.segment-count {
  font-size: var(--font-xs);
  color: var(--aqua);
  padding: 2px 8px;
  background: var(--bg-aqua);
  border-radius: 4px;
}

.preference-hint {
  font-size: var(--font-xs);
  color: var(--yellow);
  padding: 2px 8px;
  background: var(--bg-yellow);
  border-radius: 4px;
}

.divider {
  width: 2px;
  background: var(--bg3);
  transition: all 0.4s ease;
}

.divider.hidden {
  width: 0;
  opacity: 0;
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

.block-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg2);
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

.block-code {
  padding: 12px;
  background: var(--bg0);
  border-top: 1px solid var(--bg3);
  max-height: 300px;
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

.choose-btn:disabled {
  background: var(--bg3);
  color: var(--grey1);
  cursor: not-allowed;
}

.choose-btn.selected {
  background: var(--green);
  cursor: default;
}

.choose-btn.selected:disabled {
  background: var(--green);
  color: var(--bg0);
}
</style>
