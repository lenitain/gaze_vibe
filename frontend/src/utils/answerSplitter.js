export function splitAnswer(text) {
  if (!text) return []

  const segments = []
  const codeBlockRegex = /```(\w*)\s*\n([\s\S]*?)```/g

  let lastIndex = 0
  let match

  while ((match = codeBlockRegex.exec(text)) !== null) {
    const beforeText = text.slice(lastIndex, match.index).trim()
    if (beforeText) {
      segments.push({ type: 'text', content: beforeText })
    }

    segments.push({
      type: 'code',
      lang: match[1] || '',
      code: match[2].trim(),
      fullMatch: match[0]
    })

    lastIndex = match.index + match[0].length
  }

  const remainingText = text.slice(lastIndex).trim()
  if (remainingText) {
    segments.push({ type: 'text', content: remainingText })
  }

  return segments
}

export function getSegmentCount(text) {
  return splitAnswer(text).length
}
