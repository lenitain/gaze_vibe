import { describe, it, expect } from 'vitest'
import {
  parseCodeBlocks,
  extractFilePath,
  isFileApplicable,
  stripCodeBlocks,
  generateDiff,
} from '../codeParser.js'

describe('parseCodeBlocks', () => {
  it('extracts a single code block', () => {
    const text = '```js\nconst x = 1\n```'
    const blocks = parseCodeBlocks(text)
    expect(blocks).toHaveLength(1)
    expect(blocks[0]).toMatchObject({ lang: 'js', code: 'const x = 1' })
  })

  it('skips empty code blocks', () => {
    const text = '```js\n```\n```py\nx = 1\n```'
    const blocks = parseCodeBlocks(text)
    expect(blocks).toHaveLength(1)
    expect(blocks[0].lang).toBe('py')
  })

  it('extracts multiple code blocks', () => {
    const text = 'a\n```vue\n<template></template>\n```\nb\n```py\nprint(1)\n```'
    const blocks = parseCodeBlocks(text)
    expect(blocks).toHaveLength(2)
    expect(blocks[0].lang).toBe('vue')
    expect(blocks[1].lang).toBe('py')
  })

  it('returns empty array for text with no code blocks', () => {
    expect(parseCodeBlocks('just text')).toHaveLength(0)
    expect(parseCodeBlocks('')).toHaveLength(0)
  })

  it('captures start and end positions', () => {
    const text = 'prefix\n```css\n.a {}\n```\nsuffix'
    const blocks = parseCodeBlocks(text)
    expect(blocks[0].start).toBeGreaterThan(0)
    expect(blocks[0].end).toBe(blocks[0].start + '```css\n.a {}\n```'.length)
  })
})

describe('extractFilePath', () => {
  const files = [
    { path: 'src/App.vue', name: 'App.vue' },
    { path: 'src/utils/helper.js', name: 'helper.js' },
    { path: 'index.html', name: 'index.html' },
  ]

  it('finds file from explicit label before block', () => {
    const text = '修改文件: src/App.vue\n```vue\n<template></template>\n```'
    const block = { start: text.indexOf('```'), code: '<template></template>' }
    expect(extractFilePath(block, text, files)).toBe('src/App.vue')
  })

  it('finds file from path-like pattern', () => {
    const text = '检查 ./src/utils/helper.js\n```js\nconst x = 1\n```'
    const block = { start: text.indexOf('```'), code: 'const x = 1' }
    expect(extractFilePath(block, text, files)).toBe('src/utils/helper.js')
  })

  it('returns null when no file matches', () => {
    const text = 'some text\n```js\nconst x = 1\n```'
    const block = { start: text.indexOf('```'), code: 'const x = 1' }
    expect(extractFilePath(block, text, files)).toBeNull()
  })

  it('matches by first line of code if it looks like a filename', () => {
    const text = 'update:\n```js\nApp.vue\nconst x = 1\n```'
    const block = { start: text.indexOf('```'), code: 'App.vue\nconst x = 1' }
    expect(extractFilePath(block, text, files)).toBe('src/App.vue')
  })
})

describe('isFileApplicable', () => {
  it('rejects code under 2 lines', () => {
    expect(isFileApplicable({ code: 'const x = 1' }, false)).toBe(false)
  })

  it('rejects shell commands', () => {
    const cases = ['npm install', 'yarn add', 'pip install', 'cargo build', 'bun run dev']
    for (const cmd of cases) {
      expect(isFileApplicable({ code: cmd + '\n' }, false)).toBe(false)
    }
  })

  it('rejects git/docker/kubectl commands', () => {
    const cases = ['git commit -m "x"', 'docker build .', 'kubectl get pods']
    for (const cmd of cases) {
      expect(isFileApplicable({ code: cmd + '\n' }, false)).toBe(false)
    }
  })

  it('rejects compiler output and error traces', () => {
    const traces = [
      'Compiling foo v1.0\nFinished dev',
      'Error: something broke\n  at foo.js:1:2',
      'Traceback (most recent call last):\n  File "x.py"',
    ]
    for (const code of traces) {
      expect(isFileApplicable({ code }, false)).toBe(false)
    }
  })

  it('accepts import statements', () => {
    expect(isFileApplicable({ code: 'import { ref } from "vue"\nconst x = 1' }, false)).toBe(true)
  })

  it('accepts function/class definitions', () => {
    const cases = [
      'function foo() {\n  return 1\n}',
      'const fn = () => {\n  return 1\n}',
      'class Foo {\n  constructor() {}\n}',
    ]
    for (const code of cases) {
      expect(isFileApplicable({ code }, false)).toBe(true)
    }
  })

  it('always returns true when hasFilePath is true', () => {
    expect(isFileApplicable({ code: 'npm install' }, true)).toBe(true)
  })
})

describe('stripCodeBlocks', () => {
  it('removes all code blocks, keeps one newline gap', () => {
    const text = 'some\n```js\nx\n```\ntext'
    expect(stripCodeBlocks(text)).toBe('some\n\ntext')
  })

  it('collapses 3+ newlines to 2', () => {
    const text = 'a\n```js\nx\n```\n\n\n\nb'
    expect(stripCodeBlocks(text)).toBe('a\n\nb')
  })

  it('returns empty string for empty input', () => {
    expect(stripCodeBlocks('')).toBe('')
  })
})

describe('generateDiff', () => {
  it('produces unchanged lines for identical content', () => {
    const diff = generateDiff('a\nb\nc', 'a\nb\nc')
    expect(diff.every(d => d.type === 'unchanged')).toBe(true)
    expect(diff).toHaveLength(3)
  })

  it('marks removed lines', () => {
    const diff = generateDiff('a\nb\nc', 'a\nc')
    expect(diff.find(d => d.type === 'removed')?.line).toBe('b')
  })

  it('marks added lines', () => {
    const diff = generateDiff('a\nc', 'a\nb\nc')
    expect(diff.find(d => d.type === 'added')?.line).toBe('b')
  })
})
