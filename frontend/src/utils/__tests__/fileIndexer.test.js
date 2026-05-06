import { describe, it, expect, vi } from 'vitest'
import { FileIndexer } from '../fileIndexer.js'

describe('FileIndexer structure', () => {
  it('creates an empty index', () => {
    const idx = new FileIndexer()
    expect(idx.getFiles()).toEqual([])
    expect(idx.rootHandle).toBeNull()
  })

  it('getFiles returns current files array', () => {
    const idx = new FileIndexer()
    idx.files = [{ name: 'a.js' }]
    expect(idx.getFiles()).toHaveLength(1)
  })

  it('getFileByPath returns matching file', () => {
    const idx = new FileIndexer()
    idx.files = [{ path: 'src/a.js' }]
    expect(idx.getFileByPath('src/a.js')).toBeDefined()
    expect(idx.getFileByPath('nope.js')).toBeUndefined()
  })

  it('writeFile throws when file not found', async () => {
    const idx = new FileIndexer()
    await expect(idx.writeFile('missing.js', 'content')).rejects.toThrow('File not found')
  })

  it('_getExtension returns lowercase extension', () => {
    const idx = new FileIndexer()
    expect(idx._getExtension('App.Vue')).toBe('.vue')
    expect(idx._getExtension('noext')).toBe('')
    expect(idx._getExtension('a.b.c.js')).toBe('.js')
  })
})
