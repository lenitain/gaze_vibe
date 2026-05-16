/**
 * Persona 状态 I/O
 *
 * persona_state.json 存储在项目根目录，由前端读写。
 * 后端处理时仅作为数据变换，不涉及文件 I/O。
 */

const STATE_FILE = 'persona_state.json'

/**
 * 从项目目录加载 Persona 状态
 * @param {FileSystemDirectoryHandle} dirHandle
 * @returns {Promise<object|null>} state dict，不存在则返回 null
 */
export async function loadPersonaState(dirHandle) {
  try {
    const fileHandle = await dirHandle.getFileHandle(STATE_FILE)
    const file = await fileHandle.getFile()
    const text = await file.text()
    return JSON.parse(text)
  } catch {
    return null
  }
}

/**
 * 保存 Persona 状态到项目目录
 * @param {FileSystemDirectoryHandle} dirHandle
 * @param {object} state
 */
export async function savePersonaState(dirHandle, state) {
  try {
    const fileHandle = await dirHandle.getFileHandle(STATE_FILE, { create: true })
    const writable = await fileHandle.createWritable()
    await writable.write(JSON.stringify(state, null, 2))
    await writable.close()
  } catch (err) {
    console.error('保存 persona_state.json 失败:', err)
  }
}

/**
 * 删除 Persona 状态文件（重置时用）
 * @param {FileSystemDirectoryHandle} dirHandle
 */
export async function removePersonaState(dirHandle) {
  try {
    await dirHandle.removeEntry(STATE_FILE)
  } catch {
    // 文件不存在忽略
  }
}
