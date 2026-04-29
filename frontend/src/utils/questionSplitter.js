const MAX_SPLITS = 3

function extractFileReferences(prompt) {
  const filePatterns = [
    /(?:文件|file|File)\s*[:\s]+\s*([^\s,，。]+\.[a-zA-Z]+)/g,
    /(?:修改|修改|更新|update|fix|修复|重构|refactor)\s+([^\s,，。]+\.[a-zA-Z]+)/g,
    /`([^`]+\.[a-zA-Z]+)`/g,
    /(?:在|in|from)\s+([^\s,，。]+\.[a-zA-Z]+)/g,
  ]

  const files = new Set()
  for (const pattern of filePatterns) {
    let match
    while ((match = pattern.exec(prompt)) !== null) {
      const file = match[1]
      if (file && !file.includes('http') && !file.includes('```')) {
        files.add(file)
      }
    }
  }
  return [...files]
}

function detectMultiFileIntent(prompt) {
  const indicators = [
    /(?:多个|多个|所有|all|each|every)\s*(?:文件|file)/i,
    /(?:分别|分别|各自|separately)\s*(?:修改|修改|更新|update)/i,
    /(?:和|and|,|，)\s*(?:修改|修改|更新|update)/i,
    /(?:文件|file)\s*(?:列表|list|们|s)/i,
    /(?:同时|simultaneously|together)\s*(?:修改|修改|更新|update)/i,
  ]

  return indicators.some(pattern => pattern.test(prompt))
}

function splitByFiles(prompt, files) {
  if (files.length <= 1) return null
  if (!detectMultiFileIntent(prompt)) return null

  const subQuestions = files.map((file, index) => ({
    id: `file-${index}`,
    prompt: `请对文件 ${file} 进行以下修改:\n\n${prompt}\n\n(仅针对 ${file} 文件)`,
    contextHint: `专注于文件: ${file}`,
    fileTarget: file,
  }))

  return subQuestions.slice(0, MAX_SPLITS)
}

function detectLargeCodeBlock(prompt) {
  const codeBlockRegex = /```[\w]*\n([\s\S]*?)```/g
  let match
  const codeBlocks = []

  while ((match = codeBlockRegex.exec(prompt)) !== null) {
    const code = match[1]
    const lines = code.split('\n').length
    if (lines > 50) {
      codeBlocks.push({ code, lines })
    }
  }

  return codeBlocks
}

function splitByComplexity(prompt) {
  const largeBlocks = detectLargeCodeBlock(prompt)

  if (largeBlocks.length === 0) return null

  const subQuestions = []

  subQuestions.push({
    id: 'refactor-0',
    prompt: `请先重构以下代码，将大函数拆分成多个小函数:\n\n${largeBlocks[0].code}`,
    contextHint: '代码重构阶段',
    isRefactor: true,
  })

  subQuestions.push({
    id: 'apply-0',
    prompt: `基于重构后的代码，请完成以下任务:\n\n${prompt}`,
    contextHint: '应用修改阶段',
    dependsOn: 'refactor-0',
  })

  return subQuestions.slice(0, MAX_SPLITS)
}

export function splitQuestion(prompt, contextFiles = []) {
  if (!prompt || typeof prompt !== 'string') {
    return [{ id: 'main', prompt, contextHint: '原始问题' }]
  }

  const files = extractFileReferences(prompt)
  const fileSubQuestions = splitByFiles(prompt, files)
  if (fileSubQuestions) return fileSubQuestions

  const complexitySubQuestions = splitByComplexity(prompt)
  if (complexitySubQuestions) return complexitySubQuestions

  return [{ id: 'main', prompt, contextHint: '原始问题' }]
}

export function getSplitCount(prompt, contextFiles = []) {
  return splitQuestion(prompt, contextFiles).length
}
