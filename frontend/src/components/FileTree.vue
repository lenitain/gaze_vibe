<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  files: Array
})

const emit = defineEmits(['select'])

const expandedDirs = ref(new Set())
const selectedFile = ref(null)

const tree = computed(() => {
  if (!props.files || props.files.length === 0) return []

  const root = {}

  for (const file of props.files) {
    const parts = file.path.split('/')
    let current = root

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isFile = i === parts.length - 1
      const path = parts.slice(0, i + 1).join('/')

      if (!current[part]) {
        current[part] = {
          name: part,
          path,
          isFile,
          children: isFile ? null : {}
        }
      }

      if (!isFile) {
        current = current[part].children
      }
    }
  }

  function toArray(obj) {
    return Object.values(obj)
      .sort((a, b) => {
        if (a.isFile !== b.isFile) return a.isFile ? 1 : -1
        return a.name.localeCompare(b.name)
      })
      .map(item => ({
        ...item,
        children: item.children ? toArray(item.children) : null
      }))
  }

  return toArray(root)
})

function toggleDir(path) {
  if (expandedDirs.value.has(path)) {
    expandedDirs.value.delete(path)
  } else {
    expandedDirs.value.add(path)
  }
}

function selectFile(file) {
  selectedFile.value = file.path
  emit('select', file)
}

function getIcon(name) {
  const ext = name.split('.').pop().toLowerCase()
  const icons = {
    vue: '',
    js: '',
    ts: '',
    jsx: '⚛',
    tsx: '⚛',
    json: '{ }',
    css: '',
    scss: '',
    html: '',
    md: '',
    py: '',
    rs: '',
    go: '',
    yaml: '',
    yml: '',
    toml: '',
    sh: '$',
    sql: ' ',
    git: ''
  }
  return icons[ext] || ''
}
</script>

<template>
  <div class="file-tree">
    <div class="tree-header">
      <span class="header-title">项目文件</span>
      <span class="file-count" v-if="files">{{ files.length }} 个文件</span>
    </div>

    <div class="tree-content" v-if="tree.length > 0">
      <FileTreeNode
        v-for="node in tree"
        :key="node.path"
        :node="node"
        :expanded-dirs="expandedDirs"
        :selected-file="selectedFile"
        :depth="0"
        @toggle="toggleDir"
        @select="selectFile"
      />
    </div>

    <div class="empty" v-else>
      <p>暂无文件</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'FileTreeNode'
}
</script>

<script setup>
const props = defineProps({
  node: Object,
  expandedDirs: Set,
  selectedFile: String,
  depth: Number
})

const emit = defineEmits(['toggle', 'select'])

function handleToggle() {
  emit('toggle', props.node.path)
}

function handleSelect() {
  if (props.node.isFile) {
    emit('select', props.node)
  }
}

function handleChildToggle(path) {
  emit('toggle', path)
}

function handleChildSelect(file) {
  emit('select', file)
}

function getIcon(name) {
  const ext = name.split('.').pop().toLowerCase()
  const icons = {
    vue: '',
    js: '',
    ts: '',
    jsx: '⚛',
    tsx: '⚛',
    json: '{ }',
    css: '',
    scss: '',
    html: '',
    md: '',
    py: '',
    rs: '',
    go: '',
    yaml: '',
    yml: '',
    toml: '',
    sh: '$',
    sql: ' '
  }
  return icons[ext] || ''
}
</script>

<template>
  <div class="tree-node">
    <div
      class="node-row"
      :class="{ selected: node.isFile && selectedFile === node.path }"
      :style="{ paddingLeft: depth * 16 + 8 + 'px' }"
      @click="node.isFile ? handleSelect() : handleToggle()"
    >
      <span v-if="!node.isFile" class="arrow" :class="{ expanded: expandedDirs.has(node.path) }">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 18l6-6-6-6" />
        </svg>
      </span>
      <span v-else class="arrow-spacer"></span>

      <span class="icon">{{ getIcon(node.name) }}</span>
      <span class="name">{{ node.name }}</span>
    </div>
  </div>
</template>

<style scoped>
.file-tree {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg0);
  border-radius: 8px;
  overflow: hidden;
}

.tree-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg1);
  border-bottom: 1px solid var(--bg3);
}

.header-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--fg);
}

.file-count {
  font-size: 11px;
  color: var(--grey1);
}

.tree-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--grey1);
  font-size: 13px;
}

.tree-node {
  user-select: none;
}

.node-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.node-row:hover {
  background: var(--bg2);
}

.node-row.selected {
  background: var(--bg-blue);
}

.arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  color: var(--grey1);
  transition: transform 0.15s;
}

.arrow.expanded {
  transform: rotate(90deg);
}

.arrow-spacer {
  width: 16px;
}

.icon {
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.name {
  font-size: 13px;
  color: var(--fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
