<script setup>
import { ref, watch, computed } from 'vue'

const props = defineProps({
  file: Object
})

const content = ref('')
const lineCount = computed(() => content.value.split('\n').length)

watch(() => props.file, async (newFile) => {
  if (newFile && newFile.content) {
    content.value = newFile.content
  } else {
    content.value = ''
  }
}, { immediate: true })
</script>

<template>
  <div class="file-viewer">
    <div class="viewer-header" v-if="file">
      <span class="file-path">{{ file.path }}</span>
      <span class="line-info">{{ lineCount }} 行</span>
    </div>

    <div class="viewer-content" v-if="file">
      <div class="line-numbers">
        <span v-for="n in lineCount" :key="n">{{ n }}</span>
      </div>
      <pre class="code-content">{{ content }}</pre>
    </div>

    <div class="empty" v-else>
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
          <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
        </svg>
      </div>
      <p>从左侧选择文件查看内容</p>
    </div>
  </div>
</template>

<style scoped>
.file-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg0);
  border-radius: 8px;
  overflow: hidden;
}

.viewer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg1);
  border-bottom: 1px solid var(--bg3);
}

.file-path {
  font-size: 13px;
  color: var(--fg);
  font-family: 'Fira Code', 'Consolas', monospace;
}

.line-info {
  font-size: 11px;
  color: var(--grey1);
}

.viewer-content {
  flex: 1;
  display: flex;
  overflow: auto;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.line-numbers {
  display: flex;
  flex-direction: column;
  padding: 16px 12px;
  background: var(--bg1);
  border-right: 1px solid var(--bg3);
  text-align: right;
  user-select: none;
  color: var(--grey0);
  font-size: 12px;
}

.line-numbers span {
  line-height: 1.6;
}

.code-content {
  flex: 1;
  padding: 16px;
  margin: 0;
  white-space: pre;
  color: var(--fg);
  background: transparent;
}

.empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--grey1);
}

.empty-icon {
  color: var(--bg3);
}

.empty p {
  font-size: 14px;
}
</style>
