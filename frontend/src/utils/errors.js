/**
 * 结构化错误处理工具
 *
 * 提供统一错误类型、创建和显示函数，
 * 替代各处散落的 errorMessage + setTimeout 模式。
 */

export const ErrorTypes = {
  API: 'api',
  FILE: 'file',
  UNKNOWN: 'unknown',
}

const ERROR_DEFAULTS = {
  [ErrorTypes.API]: { duration: 5000, icon: 'API' },
  [ErrorTypes.FILE]: { duration: 8000, icon: '文件' },
  [ErrorTypes.UNKNOWN]: { duration: 5000, icon: '错误' },
}

/**
 * 创建结构化错误对象
 * @param {string} type - ErrorTypes 之一
 * @param {string} message - 用户可见的错误信息
 * @param {object} [details] - 额外调试信息
 * @returns {{ type: string, message: string, details?: object }}
 */
export function createError(type, message, details) {
  return { type, message, details }
}

/**
 * 检查值是否结构化错误对象
 */
export function isError(val) {
  return val && typeof val === 'object' && 'type' in val && 'message' in val
}

/**
 * 获取错误类型的默认配置
 */
export function getErrorConfig(type) {
  return ERROR_DEFAULTS[type] || ERROR_DEFAULTS[ErrorTypes.UNKNOWN]
}

/**
 * 从 Error 实例或字符串创建 ApiError
 * @param {Error|string} err
 * @param {string} [endpoint]
 * @returns {{ type: string, message: string, details?: object }}
 */
export function fromApiError(err, endpoint) {
  const message = err instanceof Error ? err.message : String(err)
  return createError(ErrorTypes.API, message, endpoint ? { endpoint } : undefined)
}

/**
 * 从文件写入错误创建 FileError
 * @param {number} failCount
 * @param {string} [detail]
 * @returns {{ type: string, message: string, details?: object }}
 */
export function fromFileError(failCount, detail) {
  const message = `${failCount} 个文件写入失败`
  return createError(ErrorTypes.FILE, message, detail ? { detail } : undefined)
}
