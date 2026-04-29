export function parseCodeBlocks(text) {
  const blocks = []
  const regex = /```(\w*)\s*\n([\s\S]*?)```/g

  let match
  while ((match = regex.exec(text)) !== null) {
    const lang = match[1] || ''
    const code = match[2].trim()

    if (code) {
      blocks.push({
        lang,
        code,
        start: match.index,
        end: match.index + match[0].length
      })
    }
  }

  return blocks
}

export function extractFilePath(block, text, nearbyFiles) {
  const beforeBlock = text.slice(Math.max(0, block.start - 200), block.start)
  const lines = beforeBlock.split('\n').reverse()

  for (const line of lines.slice(0, 5)) {
    const fileMatch = line.match(/(?:文件|file|path|修改|update|edit)[:\s]*[`"']?([^\s`"']+\.\w+)[`"']?/i)
    if (fileMatch) {
      const candidate = fileMatch[1]
      const matched = nearbyFiles.find(f => f.path.endsWith(candidate) || f.name === candidate)
      if (matched) return matched.path
    }

    const pathMatch = line.match(/(?:src\/|\.\/|\/)([\w\/]+\.\w+)/i)
    if (pathMatch) {
      const candidate = pathMatch[0]
      const matched = nearbyFiles.find(f => f.path === candidate || f.path.endsWith(candidate))
      if (matched) return matched.path
    }
  }

  for (const line of lines.slice(0, 5)) {
    const matched = nearbyFiles.find(f => {
      const name = f.name.replace(/\.\w+$/, '')
      return line.toLowerCase().includes(name.toLowerCase())
    })
    if (matched) return matched.path
  }

  const firstLine = block.code.split('\n')[0].trim()
  if (/\.\w{1,5}$/.test(firstLine) && !/[=;({\[]/.test(firstLine)) {
    const matched = nearbyFiles.find(f =>
      f.path.endsWith(firstLine) || f.path === firstLine || f.name === firstLine
    )
    if (matched) return matched.path
  }

  return null
}

export function isFileApplicable(block, hasFilePath = false) {
  if (hasFilePath) return true

  const code = block.code
  const lines = code.split('\n')

  if (lines.length < 2) return false

  if (/^(npm|yarn|pnpm|bun|pip|cargo|go)\s/.test(code)) return false
  if (/^(mkdir|cd|ls|cp|mv|rm|cat|echo|chmod)\s/.test(code)) return false
  if (/^(git|docker|kubectl)\s/.test(code)) return false

  if (/Compiling |Finished |Running |Download |Downloaded |Installing |error\[/.test(code)) return false
  if (/^\s*at\s+\S+:\d+:\d+/m.test(code)) return false
  if (/Error:|Warning:|Traceback|panic:/.test(code)) return false

  if (/^(import|from|require|use|mod)\s/.test(code)) return true
  if (/^(export|module\.exports|pub)\s/.test(code)) return true
  if (/^\s*(function|class|interface|type|const|let|var|def|fn|struct|enum)\s/m.test(code)) return true
  if (/^\s*(public|private|protected|async|static)\s/m.test(code)) return true
  if (/=>\s*[{(]/.test(code) || /\{\s*$/.test(code)) return true
  if (/^\s*\/\//.test(code) || /^\s*#/.test(code)) return true
  if (/[=;{}]\s*$/.test(code)) return true
  if (/^\s*\w+\s*=\s*/.test(code)) return true

  return false
}

export function stripCodeBlocks(text) {
  return text.replace(/```(\w*)\s*\n[\s\S]*?```/g, '').replace(/\n{3,}/g, '\n\n').trim()
}

export function generateDiff(original, modified) {
  const origLines = original.split('\n')
  const modLines = modified.split('\n')
  const diff = []

  let i = 0, j = 0

  while (i < origLines.length || j < modLines.length) {
    if (i < origLines.length && j < modLines.length && origLines[i] === modLines[j]) {
      diff.push({ type: 'unchanged', line: origLines[i], lineNum: i + 1 })
      i++
      j++
    } else {
      const findMatch = (startI, startJ) => {
        for (let k = startI; k < Math.min(startI + 3, origLines.length); k++) {
          for (let l = startJ; l < Math.min(startJ + 3, modLines.length); l++) {
            if (origLines[k] === modLines[l]) return { i: k, j: l }
          }
        }
        return null
      }

      const match = findMatch(i, j)

      if (match && match.i > i) {
        while (i < match.i) {
          diff.push({ type: 'removed', line: origLines[i], lineNum: i + 1 })
          i++
        }
      } else if (match && match.j > j) {
        while (j < match.j) {
          diff.push({ type: 'added', line: modLines[j], lineNum: null })
          j++
        }
      } else {
        if (i < origLines.length) {
          diff.push({ type: 'removed', line: origLines[i], lineNum: i + 1 })
          i++
        }
        if (j < modLines.length) {
          diff.push({ type: 'added', line: modLines[j], lineNum: null })
          j++
        }
      }
    }
  }

  return diff
}
