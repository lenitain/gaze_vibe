import { describe, it, expect } from 'vitest'
import { selectRelevantFiles, formatFilesForPrompt } from '../fileSelector.js'

function makeFile(name, path, content, ext) {
  return { name, path, ext: ext || path.split('.').pop(), size: content.length, content }
}

describe('selectRelevantFiles', () => {
  const files = [
    makeFile('App.vue', 'src/App.vue', '<template>vue component</template>', '.vue'),
    makeFile('style.css', 'src/style.css', 'body { color: red }', '.css'),
    makeFile('README.md', 'README.md', '# project', '.md'),
    makeFile('config.json', 'config.json', '{}', '.json'),
  ]

  it('returns empty array when no files given', () => {
    expect(selectRelevantFiles('question', [])).toHaveLength(0)
    expect(selectRelevantFiles('question', null)).toHaveLength(0)
    expect(selectRelevantFiles('question', undefined)).toHaveLength(0)
  })

  it('sorts by relevance: filename match ranked first', () => {
    const selected = selectRelevantFiles('vue component', files)
    expect(selected.length).toBeGreaterThanOrEqual(1)
    expect(selected[0].name).toBe('App.vue')
  })

  it('prefers css files when question mentions style/css', () => {
    const selected = selectRelevantFiles('change the style color', files)
    expect(selected[0].name).toBe('style.css')
  })

  it('returns at most 5 files when many are relevant', () => {
    const many = Array.from({ length: 10 }, (_, i) => makeFile(`mod${i}.js`, `src/mod${i}.js`, 'export function helper() {}'))
    const selected = selectRelevantFiles('helper function', many)
    expect(selected.length).toBeLessThanOrEqual(5)
  })

  it('respects total content limit (50KB)', () => {
    const big = [
      makeFile('big.js', 'big.js', 'x'.repeat(49000)),
      makeFile('small.js', 'small.js', 'y'),
      makeFile('also.js', 'also.js', 'z'),
    ]
    const selected = selectRelevantFiles('test', big)
    const totalLen = selected.reduce((s, f) => s + f.content.length, 0)
    expect(totalLen).toBeLessThanOrEqual(50000)
  })

  it('returns files with score > 0 or at least the top file', () => {
    const selected = selectRelevantFiles('unrelated query zzzzz', files)
    expect(selected.length).toBeGreaterThanOrEqual(1)
  })

  it('boosts vue files on component questions', () => {
    const mixed = [
      makeFile('helper.js', 'src/helper.js', 'function helper() {}'),
      makeFile('MyComp.vue', 'src/MyComp.vue', '<template>comp</template>', '.vue'),
    ]
    const selected = selectRelevantFiles('I need a new component', mixed)
    expect(selected[0].name).toBe('MyComp.vue')
  })

  it('boosts api-related files on api questions', () => {
    const mixed = [
      makeFile('helper.js', 'src/helper.js', 'function helper() {}'),
      makeFile('routes.js', 'src/api/routes.js', 'router.get("/")'),
    ]
    const selected = selectRelevantFiles('add an api endpoint', mixed)
    expect(selected[0].name).toBe('routes.js')
  })
})

describe('formatFilesForPrompt', () => {
  it('extracts path, name, content from each file', () => {
    const result = formatFilesForPrompt([{ path: 'a.js', name: 'a.js', content: 'x' }])
    expect(result[0]).toEqual({ path: 'a.js', name: 'a.js', content: 'x' })
  })

  it('handles empty array', () => {
    expect(formatFilesForPrompt([])).toHaveLength(0)
  })
})
