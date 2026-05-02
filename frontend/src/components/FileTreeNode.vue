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
    jsx: 'JSX',
    tsx: 'TSX',
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

    <div v-if="!node.isFile && expandedDirs.has(node.path)" class="children">
      <FileTreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :expanded-dirs="expandedDirs"
        :selected-file="selectedFile"
        :depth="depth + 1"
        @toggle="handleChildToggle"
        @select="handleChildSelect"
      />
    </div>
  </div>
</template>

<style scoped>
.tree-node {
  user-select: none;
}

.node-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
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
  width: 18px;
  height: 18px;
  color: var(--grey1);
  transition: transform 0.15s;
}

.arrow.expanded {
  transform: rotate(90deg);
}

.arrow-spacer {
  width: 18px;
}

.icon {
  font-size: var(--font-lg);
  width: 22px;
  text-align: center;
}

.name {
  font-size: var(--font-sm);
  color: var(--fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
