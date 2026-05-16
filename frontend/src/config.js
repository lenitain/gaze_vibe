// ===== 与后端 config.py 共享的常量 =====
// ⚠️ 修改以下数值时，必须同步更新 backend/config.py

// Confidence inference (App.vue)
export const ALPHA = 0.3           // 与 backend/config.py ALPHA 同步
export const MIN_EYE_TIME = 2000   // 与 backend/config.py MIN_EYE_TIME 同步
export const STRONG_WEIGHT = 0.7

// ===== 纯前端常量（无需同步后端） =====

// File selector (fileSelector.js)
export const MAX_SELECTED_FILES = 5
export const MAX_CONTENT_LENGTH = 50000 // 50KB total content

// File indexer (fileIndexer.js)
export const IGNORE_DIRS = new Set([
  'node_modules',
  '.git',
  'dist',
  'build',
  '.next',
  '.nuxt',
  '__pycache__',
  '.venv',
  'venv',
  '.env',
  '.idea',
  '.vscode',
])

export const CODE_EXTENSIONS = new Set([
  '.js', '.jsx', '.ts', '.tsx',
  '.vue', '.svelte',
  '.py', '.rb', '.go', '.rs',
  '.java', '.c', '.cpp', '.h',
  '.css', '.scss', '.less',
  '.html', '.htm',
  '.json', '.yaml', '.yml', '.toml',
  '.md', '.txt',
  '.sh', '.bash',
  '.sql',
  '.graphql', '.gql',
])

export const MAX_FILE_SIZE = 1024 * 1024 // 1MB

// Eye tracker (EyeTracker.vue)
export const DEBOUNCE_THRESHOLD = 80

// Persona 名称（与 backend/personas/ YAML 中的 name 字段一致）
export const PERSONA_A_NAME = '稳健派'
export const PERSONA_B_NAME = '现代派'

// 界面缩放
// 修改数值即可整体调整 UI 大小
// 1.0 = 原始大小, 0.7 = 70%
export const FONT_SCALE = 1
