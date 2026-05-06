import { IGNORE_DIRS, CODE_EXTENSIONS, MAX_FILE_SIZE } from '../config.js'

export class FileIndexer {
  constructor() {
    this.files = []
    this.rootHandle = null
  }

  async indexDirectory(dirHandle, path = '') {
    this.rootHandle = dirHandle
    this.files = []

    await this._scanDirectory(dirHandle, path)
    return this.files
  }

  async _scanDirectory(dirHandle, currentPath) {
    for await (const entry of dirHandle.values()) {
      const entryPath = currentPath ? `${currentPath}/${entry.name}` : entry.name

      if (entry.kind === 'directory') {
        if (!IGNORE_DIRS.has(entry.name)) {
          await this._scanDirectory(entry, entryPath)
        }
      } else if (entry.kind === 'file') {
        const ext = this._getExtension(entry.name)
        if (CODE_EXTENSIONS.has(ext)) {
          try {
            const file = await entry.getFile()
            if (file.size <= MAX_FILE_SIZE) {
              const content = await file.text()
              this.files.push({
                name: entry.name,
                path: entryPath,
                ext,
                size: file.size,
                content,
                handle: entry
              })
            }
          } catch (err) {
            console.warn(`Failed to read file ${entryPath}:`, err)
          }
        }
      }
    }
  }

  _getExtension(filename) {
    const lastDot = filename.lastIndexOf('.')
    return lastDot === -1 ? '' : filename.slice(lastDot).toLowerCase()
  }

  getFiles() {
    return this.files
  }

  getFileByPath(path) {
    return this.files.find(f => f.path === path)
  }

  async writeFile(path, content) {
    const file = this.getFileByPath(path)
    if (!file || !file.handle) {
      throw new Error(`File not found: ${path}`)
    }

    const writable = await file.handle.createWritable()
    await writable.write(content)
    await writable.close()

    file.content = content
  }
}

export default new FileIndexer()
