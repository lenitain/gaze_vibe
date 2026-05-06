// Confidence inference (App.vue)
export const ALPHA = 0.3
export const MIN_EYE_TIME = 2000
export const STRONG_WEIGHT = 0.7

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
