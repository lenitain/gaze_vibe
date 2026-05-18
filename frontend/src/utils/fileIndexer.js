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

  async _getFileHandle(path) {
    // 先在索引中找
    const file = this.getFileByPath(path)
    if (file?.handle) return file.handle

    // 不在索引中 → 新建文件（需要 rootHandle）
    if (!this.rootHandle) throw new Error('未选择项目目录，无法写入文件')

    const parts = path.split('/')
    let dirHandle = this.rootHandle

    // 逐层进入目录（自动创建不存在的目录）
    for (let i = 0; i < parts.length - 1; i++) {
      dirHandle = await dirHandle.getDirectoryHandle(parts[i], { create: true })
    }

    // 在最终目录中创建/获取文件
    return await dirHandle.getFileHandle(parts[parts.length - 1], { create: true })
  }

  async writeFile(path, content) {
    const handle = await this._getFileHandle(path)
    const writable = await handle.createWritable()
    await writable.write(content)
    await writable.close()

    // 更新内存中的内容
    const file = this.getFileByPath(path)
    if (file) file.content = content
  }
}

export default new FileIndexer()
