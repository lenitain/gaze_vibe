<script setup>
import { ref, computed } from 'vue'
import FileTreeNode from './FileTreeNode.vue'

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
</style>
