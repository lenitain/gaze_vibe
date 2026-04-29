# PROGRESS: 回答显示优化 - 智能截断与强制代码块

## 问题

1. **截断逻辑死板**：当前 `isFileApplicable()` 过滤掉 < 2 行的代码块，导致短代码也被过滤
2. **Diff 按钮空内容**：有 filePath 但代码被过滤，点击"暂存修改"后 DiffPreview 显示空内容
3. **滚动条问题**：目标是不需要滚动条就能看完答案，但当前无动态截断逻辑
4. **代码块缺失**：不管答案多短，每次改动都必须有代码修改（必须有 diff）

## 目标

- 智能截断：根据面板可用高度动态调整显示内容，无滚动条
- 强制代码块：每次 AI 回答必须包含可应用的代码块，DiffPreview 不能为空
- 短代码不过滤：即使只有 1 行代码，只要有 filePath 就显示

## 实现步骤

### Phase 1: 修复 isFileApplicable 过滤逻辑

**文件**: `frontend/src/utils/codeParser.js`

改动：
- 移除 `lines.length < 2` 的过滤条件
- 只要有 `filePath`，就保留代码块（不论长度）
- 无 filePath 的代码块仍按原逻辑过滤

```javascript
export function isFileApplicable(block, hasFilePath = false) {
  // 有文件路径的代码块始终显示（即使只有1行）
  if (hasFilePath) return true

  const code = block.code
  const lines = code.split('\n')

  // 无路径的代码块需要 >= 2 行
  if (lines.length < 2) return false

  // ... 其余过滤逻辑不变
}
```

### Phase 2: 智能截断显示

**文件**: `frontend/src/components/AnswerPanel.vue`

改动：
- 监听面板高度，计算可用显示空间
- 根据内容长度动态决定是否显示全部内容
- 超出高度时截断文本，保留所有代码块
- 添加"展开/收起"按钮（仅在内容被截断时显示）

```javascript
const panelHeight = ref(0)
const contentRef = ref(null)
const isTruncated = ref(false)

function measureContent() {
  if (!contentRef.value) return
  const container = contentRef.value.parentElement
  const availableHeight = container.clientHeight - 100 // 减去 header 和 button
  const contentHeight = contentRef.value.scrollHeight
  isTruncated.value = contentHeight > availableHeight
}
```

### Phase 3: 后端确保代码块存在

**文件**: `backend/app.py`

改动：
- 在 system prompt 中强调必须包含代码块
- 如果 AI 回答没有代码块，自动追加提示让 AI 重新生成

```python
system_a += "\n\n重要：你的回答必须包含至少一个代码块（用 ``` 包裹），并标注对应的文件路径。"

system_b += "\n\n重要：你的回答必须包含至少一个代码块（用 ``` 包裹），并标注对应的文件路径。"
```

### Phase 4: 前端代码块强制检查

**文件**: `frontend/src/App.vue`

改动：
- 在收到 API 回答后，检查是否有可用代码块
- 如果没有代码块，显示提示信息但不阻塞

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `frontend/src/utils/codeParser.js` | 小改 | 修复 isFileApplicable，短代码不被过滤 |
| `frontend/src/components/AnswerPanel.vue` | 中改 | 智能截断，展开/收起按钮 |
| `backend/app.py` | 小改 | system prompt 强调必须包含代码块 |

## 验证标准

1. ✓ 短代码块（1行）有 filePath 时不被过滤
2. ✓ DiffPreview 按钮点击后显示完整 diff 内容
3. ✓ 内容超出面板高度时自动截断，无滚动条
4. ✓ 截断时显示"展开"按钮，点击可查看全部
5. ✓ 代码块始终完整显示，不被截断
