# PROGRESS: 回答显示优化 - 智能截断与强制代码块

## 状态：已完成 ✓

## 问题

1. **截断逻辑死板**：当前 `isFileApplicable()` 过滤掉 < 2 行的代码块，导致短代码也被过滤
2. **Diff 按钮空内容**：有 filePath 但代码被过滤，点击"暂存修改"后 DiffPreview 显示空内容
3. **滚动条问题**：目标是不需要滚动条就能看完答案，但当前无动态截断逻辑
4. **代码块缺失**：不管答案多短，每次改动都必须有代码修改（必须有 diff）

## 目标

- 智能截断：根据面板可用高度动态调整显示内容，无滚动条
- 强制代码块：每次 AI 回答必须包含可应用的代码块，DiffPreview 不能为空
- 短代码不过滤：即使只有 1 行代码，只要有 filePath 就显示

## 已实现

### Phase 1: 修复 isFileApplicable 过滤逻辑 ✓

**文件**: `frontend/src/utils/codeParser.js`

改动：
- `isFileApplicable(block, hasFilePath = false)` 新增 `hasFilePath` 参数
- 如果 `hasFilePath` 为 true，直接返回 true（不过滤）
- 无 filePath 的代码块仍按原逻辑过滤（需 >= 2 行）

**调用方更新**: `AnswerPanel.vue:114` 传递 `!!filePath` 参数

### Phase 2: 智能截断显示 ✓

**文件**: `frontend/src/components/AnswerPanel.vue`

改动：
- 新增 `expandedA/B` 和 `shouldTruncateA/B` refs
- 使用 `ResizeObserver` 监控文本容器高度
- 文本超过 200px 时自动截断（保留 8 行）
- 添加"展开全文 / 收起"切换按钮
- 代码块始终完整显示，不被截断
- 移除 `.answer-content` 的 `overflow-y: auto`

### Phase 3: 后端确保代码块存在 ✓

**文件**: `backend/app.py`

改动：
- `system_a` 和 `system_b` 都添加了代码块要求指令
- 强调回答必须包含至少一个代码块并标注文件路径

### Phase 4: 前端代码块强制检查 ✓

**文件**: `frontend/src/App.vue`

改动：
- 导入 `parseCodeBlocks` 函数
- 在 `handleSubmit` 收到回答后检查是否有代码块
- 无代码块时输出 `console.warn` 警告

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `frontend/src/utils/codeParser.js` | 小改 | 修复 isFileApplicable，短代码不被过滤 |
| `frontend/src/components/AnswerPanel.vue` | 中改 | 智能截断，展开/收起按钮 |
| `backend/app.py` | 小改 | system prompt 强调必须包含代码块 |
| `frontend/src/App.vue` | 小改 | 代码块存在性检查 |

## 验证标准

1. ✓ 短代码块（1行）有 filePath 时不被过滤
2. ✓ DiffPreview 按钮点击后显示完整 diff 内容
3. ✓ 内容超出面板高度时自动截断，无滚动条
4. ✓ 截断时显示"展开"按钮，点击可查看全部
5. ✓ 代码块始终完整显示，不被截断

## 完成状态

| Phase | 状态 | 提交 |
|-------|------|------|
| Phase 1: isFileApplicable | ✓ 完成 | 522f775 |
| Phase 2: 智能截断 | ✓ 完成 | e792a51 |
| Phase 3: 后端代码块保证 | ✓ 完成 | 7640250 |
| Phase 4: 前端代码块检查 | ✓ 完成 | 5d52151 |
