export function mergeAnswers(results) {
  if (!results || results.length === 0) {
    return { answerA: '', answerB: '' }
  }

  if (results.length === 1) {
    return {
      answerA: results[0].answerA || '',
      answerB: results[0].answerB || '',
    }
  }

  const partsA = []
  const partsB = []

  for (let i = 0; i < results.length; i++) {
    const result = results[i]

    if (result.answerA) {
      if (results.length > 1) {
        partsA.push(`### 片段 ${i + 1}\n\n${result.answerA}`)
      } else {
        partsA.push(result.answerA)
      }
    }

    if (result.answerB) {
      if (results.length > 1) {
        partsB.push(`### 片段 ${i + 1}\n\n${result.answerB}`)
      } else {
        partsB.push(result.answerB)
      }
    }
  }

  return {
    answerA: partsA.join('\n\n---\n\n'),
    answerB: partsB.join('\n\n---\n\n'),
  }
}

export function createSegments(results) {
  if (!results || results.length === 0) return { segmentsA: [], segmentsB: [] }

  const segmentsA = []
  const segmentsB = []

  for (let i = 0; i < results.length; i++) {
    const result = results[i]

    if (result.answerA) {
      segmentsA.push({
        id: result.id || `seg-${i}`,
        index: i,
        content: result.answerA,
        contextHint: result.contextHint || '',
      })
    }

    if (result.answerB) {
      segmentsB.push({
        id: result.id || `seg-${i}`,
        index: i,
        content: result.answerB,
        contextHint: result.contextHint || '',
      })
    }
  }

  return { segmentsA, segmentsB }
}
