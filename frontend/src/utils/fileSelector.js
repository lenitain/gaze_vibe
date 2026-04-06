const MAX_SELECTED_FILES = 5
const MAX_CONTENT_LENGTH = 50000 // 50KB total content

export function selectRelevantFiles(question, files) {
  if (!files || files.length === 0) return []

  const keywords = extractKeywords(question)
  if (keywords.length === 0) {
    return files.slice(0, MAX_SELECTED_FILES)
  }

  const scored = files.map(file => ({
    file,
    score: calculateScore(file, keywords, question)
  }))

  scored.sort((a, b) => b.score - a.score)

  const selected = []
  let totalLength = 0

  for (const { file } of scored) {
    if (selected.length >= MAX_SELECTED_FILES) break
    if (totalLength + file.content.length > MAX_CONTENT_LENGTH) break
    if (file.score > 0 || selected.length === 0) {
      selected.push(file)
      totalLength += file.content.length
    }
  }

  return selected
}

function extractKeywords(question) {
  const stopWords = new Set([
    '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '他', '她', '它', '们', '那', '些', '什么', '怎么', '为什么', '哪',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
    'may', 'might', 'can', 'shall', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
    'by', 'from', 'as', 'into', 'through', 'during', 'before', 'after', 'above',
    'below', 'between', 'under', 'again', 'further', 'then', 'once', 'here',
    'there', 'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
    'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only',
    'own', 'same', 'so', 'than', 'too', 'very', 'just', 'because', 'but',
    'and', 'or', 'if', 'while', 'what', 'which', 'who', 'this', 'that', 'these', 'those'
  ])

  const words = question
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fff]/g, ' ')
    .split(/\s+/)
    .filter(w => w.length > 1 && !stopWords.has(w))

  return [...new Set(words)]
}

function calculateScore(file, keywords, question) {
  let score = 0
  const lowerContent = file.content.toLowerCase()
  const lowerName = file.name.toLowerCase()
  const lowerPath = file.path.toLowerCase()
  const lowerQuestion = question.toLowerCase()

  for (const keyword of keywords) {
    if (lowerName.includes(keyword)) {
      score += 10
    }
    if (lowerPath.includes(keyword)) {
      score += 5
    }

    const contentMatches = (lowerContent.match(new RegExp(keyword, 'g')) || []).length
    score += Math.min(contentMatches, 20)
  }

  if (lowerQuestion.includes('component') || lowerQuestion.includes('组件')) {
    if (file.ext === '.vue' || file.ext === '.jsx' || file.ext === '.tsx') {
      score += 15
    }
  }

  if (lowerQuestion.includes('style') || lowerQuestion.includes('样式') || lowerQuestion.includes('css')) {
    if (file.ext === '.css' || file.ext === '.scss' || file.ext === '.less') {
      score += 15
    }
  }

  if (lowerQuestion.includes('config') || lowerQuestion.includes('配置')) {
    if (file.ext === '.json' || file.ext === '.yaml' || file.ext === '.yml' || file.ext === '.toml') {
      score += 15
    }
  }

  if (lowerQuestion.includes('api') || lowerQuestion.includes('接口') || lowerQuestion.includes('route')) {
    if (file.path.includes('api') || file.path.includes('route') || file.path.includes('controller')) {
      score += 15
    }
  }

  if (file.name === 'index.js' || file.name === 'index.ts' || file.name === 'main.js') {
    score += 5
  }

  if (file.name === 'README.md') {
    score += 3
  }

  if (file.name === 'package.json' || file.name === 'requirements.txt' || file.name === 'Cargo.toml') {
    score += 3
  }

  return score
}

export function formatFilesForPrompt(files) {
  return files.map(file => ({
    path: file.path,
    name: file.name,
    content: file.content
  }))
}
