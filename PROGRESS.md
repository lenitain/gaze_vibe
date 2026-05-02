# PROGRESS: 回答分割 Plan B - 后端规则切分 + 前端干净展示

## 目标

眼动追踪场景，用户问一次，每次回答短到不需要滚动条。用户全程只看，零交互。

核心思路：后端用**规则**（非递归 AI）切分回答 → 前端展示分段列表。

## 当前架构（Plan A: 递归 AI 拆分）

```
后端 /api/ask-v2 (SSE):
  recursive_split_answer()
    1. generate_single_answer()  → 2 次 DeepSeek 调用 (A/B)
    2. estimate_lines() 估算渲染高度
    3. 太长 → call_ai_to_split() → 再调 DeepSeek 把回答拆成子任务 JSON
    4. 每个子任务 → 递归回到步骤 1（最多深度 3 层，每层 2 次 API）

前端 App.vue:
  - 接收 SSE chunk 流
  - answerChunksA/B 存每个 chunk
  - 拼成 answerA/B 完整文本
  - 同时设 answerSegmentsA/B = chunks（>1 个时）

前端 AnswerPanel.vue:
  - 有 segments → 遍历 segments, v-html seg.content（原始 markdown）
  - 下面又渲染 codeBlocksA（从完整 answerA 解析）
  - 无 segments → stripCodeBlocks + codeBlocks 分开
```

当前状态：（自测）功能实现但效果差。

## 已发现问题

### 1. 递归拆分几乎不触发，触发了效果也差

- `max_lines = viewportHeight / 17`（700px 视口 → 41 行）
- `MIN_SPLIT_THRESHOLD = 2.0` → 82 行才触发拆分
- 系统 prompt 说"不超过 15 行代码 + 3 行文字"，但 AI 不遵守约束，常输出 50-200 行
- `call_ai_to_split` 用 AI 拆分 AI 回答 → 不稳定（JSON 格式可能失败、子任务重叠/遗漏）
- 子任务"重新生成"而非"切分原回答" → 丢失上下文、不一致、每子任务 2 次 API

### 2. API 成本爆炸

5 子任务 = 2(原始) + 1(拆分) + 10(子任务重新生成) = 13 次 DeepSeek 调用

### 3. Segment 展示 Bug

```html
<!-- segment 模式：v-html 展示原始 markdown（代码 fence ``` 当纯文本显示） -->
<div class="answer-text" v-html="seg.content"></div>
<!-- 下面又解析了一次代码块，用户看到两遍 -->
<div v-if="codeBlocksA.length > 0" class="code-blocks">...</div>
```

### 4. estimate_lines 不准确

只算行数 × 17px，忽略:
- answer-header (34px)
- choose-btn (~60px)
- `.block-code` 的 padding (24px)
- segment-block 之间的 border/margin

## Plan B: 后端规则切分

去掉 AI 递归拆分，改为纯规则切分。不重新生成，只拆分已有回答。

### 核心流程

```
后端 /api/ask:
  1. generate_dual_answers()  → 2 次 DeepSeek 调用 (A/B)
  2. split_answer(answer_text, max_lines) → 规则切分每个回答
  3. 返回 {answerA, answerB, segmentsA, segmentsB}
      - answerA/B = 原始完整文本（向后兼容）
      - segmentsA/B = [{type:'text',content}, {type:'code',lang,content}, ...]

前端 AnswerPanel.vue:
  - 有 segments → 渲染分段列表
     - text 段：纯文本（不含代码 fence）
     - code 段：代码卡片
  - 无 segments → flat 模式（stripCodeBlocks + codeBlocks）
  - 不重复，不交叉
```

### 切分规则（`split_answer`）

```
输入: answer_text (原始 markdown 字符串)
输出: segment[{type, content, lang?, code?}]

步骤:
1. 正则 /```(\w*)\s*\n([\s\S]*?)```/g 提取所有代码块
2. 在代码块之间 = 文本片（strip 代码 fence 后纯文本）
3. 遍历所有文本片和代码块，交替输出 segments
4. 文本片太长（>max_lines）→ 按双换行切分子段
5. max_lines = viewportHeight / 17 - 2（预留 header/button 空间）
```

### 移除内容

- 删除: `recursive_split_answer()`, `call_ai_to_split()`, `MIN_SPLIT_THRESHOLD`, `MAX_SUB_TASKS`
- 删除: `/api/ask-v2` SSE 端点
- 删除: `generate_single_answer()`（不再需要独立单次生成）
- 删除: 前端 `answerChunksA/B`、`answerSegmentsA/B` SSE 接收逻辑

## 文件改动

### backend/app.py

| 改动 | 说明 |
|------|------|
| 删除 `recursive_split_answer()` | 不再递归 |
| 删除 `call_ai_to_split()` | 不再用 AI 拆分 |
| 删除 `MIN_SPLIT_THRESHOLD`, `MAX_SUB_TASKS` | 不再需要 |
| 删除 `generate_single_answer()` | `/api/ask-v2` 专用，也将删除 |
| 删除 `/api/ask-v2` 路由 | SSE 端点移除 |
| 新增 `split_answer_into_segments(text, max_lines)` | 规则切分 |
| 改进 `estimate_lines()` | 更准确估算渲染高度 |
| 修改 `/api/ask` | 返回增加 `segmentsA`/`segmentsB` 字段 |

**`split_answer_into_segments` 签名**:
```python
def split_answer_into_segments(text, max_lines):
    """
    规则切分回答为 segments 列表。

    参数:
        text: 原始 markdown 回答
        max_lines: 每段最大行数（viewportHeight/17 - 2）

    返回:
        [{type: 'text', content: str}, {type: 'code', lang: str, content: str}, ...]

    规则:
    1. 正则解析所有 ```lang\ncode``` 代码块
    2. 代码块之间的文本 = 文本片（去掉 fence 和代码块内容）
    3. 文本片 > max_lines → 按双换行分拆
    4. 返回交替 segments
    """
```

**修改 `/api/ask`**:
```python
@app.route("/api/ask", methods=["POST"])
def ask():
    # ... 现有逻辑 ...
    viewport_height = data.get("viewportHeight", 700)
    max_lines = max(5, int(viewport_height / 17) - 2)

    segmentsA = split_answer_into_segments(result["answerA"], max_lines) if result.get("answerA") else []
    segmentsB = split_answer_into_segments(result["answerB"], max_lines) if result.get("answerB") else []

    result["segmentsA"] = segmentsA
    result["segmentsB"] = segmentsB
    return jsonify(result)
```

### frontend/src/App.vue

| 改动 | 说明 |
|------|------|
| 删除 `parseSSEStream()` | 不再需要 SSE |
| 删除 `askV2SSE()` | 不再需要 |
| 删除 `answerChunksA/B` ref | 不需要 |
| 删除 `answerSegmentsA/B` ref | 由后端返回 |
| 简化 `handleSubmit()` | 只用 `/api/ask`，传 `viewportHeight` |

**简化后的 `handleSubmit`**:
```js
async function handleSubmit(prompt) {
  currentQuestion.value = prompt
  isLoading.value = true
  answerPanelRef.value?.resetChoice()
  answerA.value = ''
  answerB.value = ''

  try {
    const relevantFiles = selectRelevantFiles(prompt, indexedFiles.value)
    const contextFiles = formatFilesForPrompt(relevantFiles)
    const viewportHeight = answerPanelRef.value?.contentHeight || 700

    // 眼动数据收集保持不变...
    let eyeData = null
    // ...

    const data = await (await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt, contextFiles, viewportHeight,
        experimentMode: experimentMode.value, eyeData
      })
    })).json()

    answerA.value = data.answerA
    answerB.value = data.answerB
    // segments 直接传给 AnswerPanel（通过 props）
  } finally {
    isLoading.value = false
  }
}
```

### frontend/src/components/AnswerPanel.vue

| 改动 | 说明 |
|------|------|
| 新增 props: `segmentsA`, `segmentsB` | 从后端接收分割结果 |
| 修改 template | segments 优先，flat 模式回退 |
| 修复 text segment 显示 | 纯文本，不含代码 fence |
| code segment 显示 | 已有 code-block 样式复用 |

**核心 template 变更**:
```html
<!-- segments 模式 -->
<template v-if="segmentsA && segmentsA.length > 1">
  <div v-for="(seg, i) in segmentsA" :key="i" class="segment-block">
    <div v-if="seg.type === 'text'" class="answer-text">{{ seg.content }}</div>
    <div v-else-if="seg.type === 'code'" class="code-block">
      <div class="block-header">
        <span class="block-lang">{{ seg.lang }}</span>
      </div>
      <div class="block-code"><pre>{{ seg.content }}</pre></div>
    </div>
  </div>
</template>
<!-- flat 模式回退（单 segment 或无 segments） -->
<template v-else>
  <div class="text-container">
    <div class="answer-text" v-html="displayTextA"></div>
  </div>
  <div v-if="codeBlocksA.length > 0" class="code-blocks">...</div>
</template>
```

### frontend/src/utils/answerSplitter.js

- 保留 `splitAnswer()` 作为前端回退（后端未返回 segments 时用）
- 修复：如果后端已返回 segments，前端不再重复解析

### frontend/src/utils/answerMerger.js

- 保留不动，remove 相关调用

## 里程碑

- [ ] Phase 1: 后端 `split_answer_into_segments` + 改进 `estimate_lines`
- [ ] Phase 2: 删除递归拆分代码（清理 `recursive_split_answer`、`call_ai_to_split`、`/api/ask-v2`、`generate_single_answer`）
- [ ] Phase 3: 前端简化（删除 SSE/Chunk 逻辑，接收 segments props）
- [ ] Phase 4: 前端展示修复（segments 模式干净渲染，不重复）
- [ ] Phase 5: 验证 — 简单回答不切分，中等回答切 2-3 段，每个段内无滚动条

## 依赖关系

```
Phase 1 (后端切分逻辑) → Phase 2 (清理) → Phase 3 (前端接收) → Phase 4 (前端展示) → Phase 5 (验证)
```

Phase 3 和 Phase 4 可并行。
Phase 2 可以和 Phase 1 一起做。
