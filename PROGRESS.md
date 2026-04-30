# PROGRESS: 递归分片 - 自动多次回复，无需滚动条

## 状态：已实现（待测试验证）

## 目标

眼动追踪场景，用户问一次，系统**自动**多次回复，每次回答短到不需要滚动条。用户全程只看，零交互。

## 核心流程：递归拆分

```
用户提问
  │
  ▼
AI生成完整回答
  │
  ├─ 回答够短（能放进面板）→ 直接展示给用户 ✓
  │
  └─ 回答太长 → 调AI把回答拆成子任务
                   │
                   ├─ 子任务1 → AI生成回答 → 检查长短
                   │              ├─ 够短 → 展示 ✓
                   │              └─ 太长 → 再拆（递归）
                   │
                   ├─ 子任务2 → 同上
                   │
                   └─ 子任务3 → 同上
```

终止条件：每个回答渲染后不超出 `.answer-content` 可用高度。

## "多小"的判定标准

根据前端实际 CSS 计算（`--font-scale: 0.7`）：

| 元素 | 实际字号 | 行高 |
|------|----------|------|
| 正文 `--font-base` | 10.5px | ~17px |
| 代码 `--font-xs` | 8.4px | ~13px |

`.answer-content` 可用高度 = `.answer-col` 高度 - header(34px) - chooseBtn(60px)

| 视口高度 | .answer-col | .answer-content | 可容文本行 | 可容代码行 |
|----------|-------------|-----------------|------------|------------|
| 900px | ~640px | ~606px | ~35行 | ~46行 |
| 700px | ~440px | ~406px | ~23行 | ~31行 |
| 500px（极端） | ~240px | ~206px | ~12行 | ~15行 |

**判定规则**：估算渲染高度 > `.answer-content` 高度 → 需要拆分

另外，`.block-code` 有 `max-height: 300px; overflow-y: auto`，**单个代码块也不能超过300px**（≈23行代码）。这个也要纳入检查。

## 当前问题

1. `questionSplitter.js` 切用户输入，不管输出长度
2. `code_refactor.py` 重构用户代码，和回答长度无关
3. 前端截断是视觉遮盖
4. 无递归拆分机制

---

## Phase 规划

### Phase 1: 后端 - 递归拆分引擎

**文件**: `backend/app.py`

新增函数 `recursive_split_answer(prompt, context_files, max_lines, depth=0)`:

```
def recursive_split_answer(prompt, context_files, max_lines, depth=0):
    if depth > 3:  # 防止无限递归
        return [generate_single_answer(prompt, context_files)]

    answer = generate_single_answer(prompt, context_files)

    if estimate_lines(answer) <= max_lines:
        return [answer]  # 够短，直接返回

    # 太长，调AI拆成子任务
    sub_tasks = call_ai_to_split(answer, max_lines)

    results = []
    for task in sub_tasks:
        # 递归：对每个子任务再生成回答，再检查
        sub_results = recursive_split_answer(
            task["prompt"], context_files, max_lines, depth + 1
        )
        results.extend(sub_results)

    return results
```

关键子函数：

**`estimate_lines(answer_text)`**: 估算回答渲染行数
- 文本部分：按中文35字/行、英文80字/行折算
- 代码块：直接取代码行数 + padding
- 综合返回总渲染高度(px)

**`call_ai_to_split(answer, max_lines)`**: 调AI把长回答拆成子任务
- system prompt: "把以下回答拆成多个独立的小步骤，每个步骤的AI回答不超过N行代码+M行文字。输出JSON数组。"
- 返回 `[{prompt, contextHint}, ...]`

**新增接口 `/api/ask-v2`**:
- 接收 `{prompt, contextFiles, viewportHeight}`（前端传面板高度）
- `max_lines = viewportHeight / 17`（按文本行高算）
- 调用 `recursive_split_answer`
- 用 SSE 流式返回每个子结果

**SSE 流式格式**:
```
event: chunk
data: {"index": 0, "total": 3, "answerA": "...short...", "answerB": "...short...", "hint": "核心实现"}

event: chunk
data: {"index": 1, "total": 3, "answerA": "...short...", "answerB": "...short...", "hint": "边界处理"}

event: chunk
data: {"index": 2, "total": 3, "answerA": "...short...", "answerB": "...short...", "hint": "测试用例"}

event: done
data: {"success": true}
```

**拆分用 system prompt**:
```
你是一个任务拆分助手。以下是一个编程问题的完整回答，但它太长了。
请将其拆分成多个独立的小任务，使得每个小任务的AI回答都能控制在指定行数内。

要求：
1. 每个小任务独立可答，有明确的代码输出
2. 小任务之间如果有依赖，标记 dependsOn
3. 每个任务的回答不超过 {max_code_lines} 行代码 + {max_text_lines} 行说明文字
4. 保持原回答的完整性，不要遗漏内容

输出JSON格式：
[
  {"id": "1", "prompt": "请实现...", "contextHint": "核心函数", "dependsOn": ""},
  {"id": "2", "prompt": "请添加...", "contextHint": "边界处理", "dependsOn": "1"}
]
```

**验收**:
- 简单问题（10行回答）→ 不拆分，1个chunk
- 中等问题（40行回答）→ 拆成2个chunk
- 复杂问题（100行回答）→ 递归拆成3-5个chunk
- 每个chunk渲染后不超出面板高度

---

### Phase 2: 后端 - prompt长度约束

**文件**: `backend/app.py`

- `system_a` / `system_b` 添加硬性长度指令
  - `"每次回答代码不超过15行，说明文字不超过3行"`
- `max_tokens` 从 3000 降到 1200（子任务回答更短）
- `generate_single_answer` 接受 `max_tokens` 参数，子任务调用时传更小值

**验收**: 单次AI回答的代码块不超过15行

---

### Phase 3: 前端 - 接收分片 + 自动展示

**文件**: `frontend/src/App.vue`, `frontend/src/components/AnswerPanel.vue`

`App.vue` 改动:
- `handleSubmit` 改用 `/api/ask-v2`
- 传 `viewportHeight` 给后端（从 AnswerPanel 获取）
- 用 `fetch` + `ReadableStream` 接收 SSE
- `answerChunksA = ref([])` / `answerChunksB = ref([])` 存分片
- `answerA` / `answerB` 改为 computed：chunks 拼接
- 每收到一个 chunk，自动 push，前端自动展示

`AnswerPanel.vue` 改动:
- 用 `ResizeObserver` 监控 `.answer-content` 可用高度
- 暴露 `contentHeight` 给父组件
- 接收 `chunksA` / `chunksB` 而不是完整 answer
- `v-for` 渲染每个 chunk
- chunk 之间有分隔线 + 上下文提示（如"步骤1: 核心函数"）
- 新 chunk 出现时有淡入动画
- `.answer-col` 的 `overflow-y` 改为 `auto`（多个chunk叠加后可滚动，但每个chunk本身不超面板）

**注意**：多chunk叠加后内容会超出面板高度，这是可接受的——
- 每个chunk本身短到不需要滚动
- 多个chunk叠加后的整体滚动是"翻阅历史"，不是"在一个chunk内滚动"
- 或者限制只显示最近N个chunk，更早的折叠

**验收**:
- 复杂问题自动分成多个chunk依次出现
- 每个chunk内部无滚动条
- chunk出现有动画

---

### Phase 4: 滚动条清理

- `.answer-col` 保持 `overflow-y: auto`（多chunk需要整体可滚动）
- `.block-code` 的 `max-height` 从 300px 改为更小值（如200px）或移除限制（由后端分片控制）
- 确认 `.block-code` 单独也不会出现滚动条（后端拆分保证代码块不超过23行）

---

## 文件改动计划

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `backend/app.py` | **大改** | 递归拆分引擎、SSE接口、prompt约束 |
| `frontend/src/App.vue` | 中改 | SSE接收、chunks状态管理 |
| `frontend/src/components/AnswerPanel.vue` | 中改 | 多chunk展示、ResizeObserver暴露高度 |

## 依赖关系

```
Phase 1 (后端递归拆分) → Phase 2 (prompt约束) → Phase 3 (前端接收展示) → Phase 4 (滚动条清理)
```

## 里程碑

- [x] Phase 1: 后端递归拆分引擎 + SSE
- [x] Phase 2: prompt长度约束
- [x] Phase 3: 前端自动展示多chunk
- [x] Phase 4: 滚动条清理

## 当前提交记录

| 提交 | 说明 |
|------|------|
| 522f775 | isFileApplicable 修复 |
| e792a51 | 智能截断（已废弃，仅视觉遮盖） |
| 7640250 | 后端代码块保证 |
| 5d52151 | 前端代码块检查 |
