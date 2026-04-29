# PROGRESS: 长回答自动拆分重构

## 状态：已完成 ✓

## 目标

取消"上一页/下一页"翻页机制。长回答自动拆分成多次API调用，用户无感。

## 核心需求

1. **多次回答**：一个用户问题 → 多次LLM API调用 → 多个回答片段
2. **用户无感**：拆分对用户透明，感觉是自然的多次回答
3. **智能切分**：
   - 可切分的代码段 → 直接按函数/模块切分
   - 不可切分的大函数 → 先让LLM重构，再切分

## 已实现架构

```
用户问题 → 前端 splitQuestion() 判断是否需要拆分
               ↓
        拆分成子问题列表 (最多3个)
               ↓
        单问题: /api/ask  多问题: /api/ask-batch
               ↓
        前端 mergeAnswers() + createSegments() 整合
               ↓
        AnswerPanel 连续显示所有片段，无翻页
```

## 实际实现

### Phase 1: 问题拆分逻辑 ✓

**文件**: `frontend/src/utils/questionSplitter.js` (已创建)

拆分策略：
1. **单文件修改**：不拆分，直接调用 `/api/ask`
2. **多文件修改**：按文件拆分，每个文件一个子问题
3. **大函数重构**：>50行代码块 → 先重构再应用

检测方法：
- `extractFileReferences()`: 提取文件引用（如 `file.js`, `修改 xxx.py`）
- `detectMultiFileIntent()`: 检测多文件修改意图关键词
- `detectLargeCodeBlock()`: 检测 >50 行的大代码块

### Phase 2: 后端批量API支持 ✓

**文件**: `backend/app.py` (已修改)

新增路由：
- `POST /api/ask-batch`：接收子问题列表，批量调用API
- 支持 `dependsOn` 依赖关系，传递前一步摘要作为上下文
- 支持 `isRefactor` 标记，自动触发代码重构

**文件**: `backend/code_refactor.py` (已创建)

功能：
- `refactor_large_code()`: 调用LLM将大函数拆分成小函数
- `should_refactor()`: 判断代码块是否需要重构（>50行）

### Phase 3: 前端整合显示 ✓

**文件**: `frontend/src/components/AnswerPanel.vue` (已修改)

改动：
- 移除 `splitAnswer` 导入和分页逻辑
- 移除 `currentSegmentA/B`、`prevSegment/nextSegment` 函数
- 移除"上一段/下一段"按钮
- 新增 `answerSegmentsA` / `answerSegmentsB` props
- 连续显示所有片段，每个片段用虚线分隔
- 显示片段数量标签（如 "3 个片段"）

### Phase 4: 代码重构支持 ✓

集成在 `/api/ask-batch` 中：
- 检测 `isRefactor: true` 的子问题
- 自动调用 `refactor_large_code()` 进行重构
- 重构结果作为下一步的输入

### Phase 5: 眼动数据适配 ✓

**文件**: `frontend/src/App.vue` (已修改)

改动：
- 导入 `splitQuestion` 和 `mergeAnswers`
- `handleSubmit()` 根据子问题数量选择 API
- 眼动数据同时传递给 `/api/ask` 和 `/api/ask-batch`
- 批量响应后重置眼动追踪状态

## 文件改动清单

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `frontend/src/utils/questionSplitter.js` | 新建 | 问题拆分逻辑 |
| `frontend/src/utils/answerMerger.js` | 新建 | 多次回答整合 |
| `frontend/src/components/AnswerPanel.vue` | 大改 | 移除分页，支持多次回答显示 |
| `frontend/src/App.vue` | 中改 | 适配批量API调用 |
| `backend/app.py` | 中改 | 新增批量API和代码重构 |
| `backend/code_refactor.py` | 新建 | 代码重构逻辑 |

## 验证标准

1. ✓ 用户提交问题后，无翻页按钮
2. ✓ 长回答自动拆分成多个片段连续显示
3. ✓ 眼动数据正确收集（无翻页干扰）
4. ✓ 代码重构功能正常工作

## 已解决的风险点

1. **API成本**：限制最大拆分次数为3次
2. **响应时间**：串行调用，但用户无感知（连续显示）
3. **拆分质量**：大函数先重构再拆分
4. **上下文丢失**：传递前一个子问题的摘要作为上下文 (`dependsOn` 机制)
