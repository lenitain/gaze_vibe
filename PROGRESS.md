# PROGRESS

## 已完成：多轮回答重构

### 目标

眼动追踪场景。用户**问一次**，系统**自动回复多次**：
- 第 1 次回答：覆盖问题的一个方面（短，不需滚动）
- 第 2 次回答：覆盖另一个方面（短，不需滚动）
- 第 3 次...
- 用户全程只看，零交互
- 每轮由系统自动触发（不需用户再次输入）

这样每轮的眼动数据质量高（内容短，用户不滚动），且覆盖全面。

### 历史：旧方案问题

旧后端 `recursive_split_answer()` + `/api/ask-v2` SSE 做法三个致命缺陷：

1. **拆的是回答，不是问题**：`call_ai_to_split()` 把 AI 刚写出来的代码喂给 AI，让 AI"反向工程"出子任务。AI 擅长写代码，不擅长拆自己写的答案。结果：JSON 格式失败、子任务重叠、遗漏内容。
2. **先写全文再重写**：先生成了完整长回答（浪费 2 次 API），再拆成子任务重新生成（每子任务又 2 次 API）。5 子任务 = 13 次调用，且子任务之间不一致。
3. **递归爆炸**：深度 3 层 + 每层 2 次 API + 每子任务可再递归。

### 正确方案：拆用户问题，不拆 AI 回答

```
❌ Plan A: 用户问题 → AI 生成完整回答 → AI 拆回答 → 重新生成每段
✅ 正确做法: 用户问题 → AI 拆成子问题 → 对每个子问题生成回答
```

后端 `split_user_question()` 用 DeepSeek 把用户问题拆成 2-4 个子问题，然后顺序生成每个子问题的 A/B 双答案，后一题携带前一题摘要作为上下文。

### 已完成的里程碑

- [x] Phase 1: 后端 `split_user_question()` 实现 + `/api/ask` 修改
- [x] Phase 2: 删除旧递归拆分代码
- [x] Phase 3: 前端简化（删除 SSE，调 `/api/ask`）
- [x] Phase 4: 前端展示修复（segment 内容干净渲染）
- [x] Phase 5: 验证 — 4/4 测试通过，死代码清理完毕

---

## 当前项目状态（2026-05-02 审计）

### 架构总览

```
frontend/                          backend/
  Vue 3 + Vite (plain JS)           Python Flask
  port 5173                          port 8000
  vite proxy /api/* → :8000
```

关键依赖：`vue 3.4`, `marked 15`, `webgazer`（前端）；`flask`, `openai`（后端）。

### 核心数据流

```
用户提问 → App.vue.handleSubmit()
  → selectRelevantFiles()（关键词匹配索引文件）
  → POST /api/ask { prompt, contextFiles, eyeData }
    → split_user_question()（DeepSeek 拆成子问题）
    → 每个子问题 generate_dual_answers()（A/B 各一次 DeepSeek 调用）
  ← { answerA, answerB, segments[], success }
  → parseCodeBlocks() 提取代码块
  → AnswerPanel 渲染 segments（多轮）或 flat（单次）
  → WebGazer 追踪眼动 → userPreference 更新
  → 用户点"选择此答案" → handleChoice(side)
    → 写代码文件到磁盘
    → POST /api/preference { preference, eyeMetrics }
```

### 文件结构

```
frontend/src/
├── App.vue                    # 根组件，~580 行，状态管理中心
├── components/
│   ├── AnswerPanel.vue        # 双答案面板，~611 行
│   ├── ChatInput.vue          # 输入框
│   ├── DiffPreview.vue        # DIFF 预览弹窗（未使用/死代码）
│   ├── EyeTracker.vue         # WebGazer 眼动追踪，~701 行
│   ├── FileTree.vue           # 侧边栏文件树
│   ├── FileTreeNode.vue       # 递归树节点
│   ├── FileViewer.vue         # 文件内容查看器
│   └── FolderSelector.vue     # 文件夹选择器
├── utils/
│   ├── codeParser.js          # 代码块解析、路径提取、diff
│   ├── fileIndexer.js         # File System Access API 目录扫描
│   └── fileSelector.js        # 关键词相关文件选择
└── styles/
    └── everforest.css         # CSS 变量（Everforest Dark Medium）

backend/
├── app.py                     # Flask 主服务，~438 行
├── eye_tracker_processor.py   # 眼动数据处理 + EMA 建模，~472 行
├── test_split.py              # split_user_question 测试
└── requirements.txt           # flask, flask-cors, openai, python-dotenv
```

### 实验模式

| mode | 眼动追踪 | 自动选择 | 说明 |
|------|---------|---------|------|
| full | 是 | 是 | 完整实验，置信度>=0.8 自动选 |
| manual | 是 | 否 | 采集数据，用户手动选 |
| control | 否 | 否 | 基线模式 |

---

## 已知 Bug（按优先级排序）

### P0 - segments 与 code blocks 互斥（影响核心功能）

**已修复（Phase 6）**：删除了 `!displaySegmentsA` / `!displaySegmentsB` 守卫条件，code blocks 现在始终显示。

视觉上 segment 内的 markdown 渲染和 `.code-blocks` 区可能有重复代码块，但后者提供了结构化文件路径标头，对「选择此答案」写盘流程有价值，属于可接受取舍。

### P0 - AGENTS.md 与实际代码严重脱节

AGENTS.md 描述的 `fileChanges` Maps、`_stagedBy` 标记、暂存/取消/应用修改交互流程、DiffPreview 弹窗——**这些在代码中不存在**。实际 `AnswerPanel.vue` 只有「选择此答案」按钮直接写盘。

**需要决定**：要么删文档匹配代码，要么实现文档描述的功能。

### P1 - 眼动追踪数据累积错误

`EyeTracker.vue:232-246` `calculateFinalAttention()` 中：
```js
elapsed = Date.now() - regionStartTime
```
`regionStartTime` 只设一次，每次 flush 时 `elapsed` 持续增长，导致 `totalFocus` 每次累加错误值。每个 flush 应该只加当次时长，而不是累计时长。

### P1 - 无意义条件分支

`EyeTracker.vue:63-68`：
```js
if (props.diffOpenSide === 'A')
  displayDuration = totalDurationA + currentElapsed + totalDurationB
else
  displayDuration = totalDurationA + totalDurationB + currentElapsed
```
两个分支数学上完全等价，条件无意义。

### P2 - 字体缩放与文档矛盾

`everforest.css` 中 `--font-scale: 0.7` 实际缩小字体（xs=8.4px, base=10.5px），AGENTS.md 却说 "1.5x scaled"。要么改代码要么改文档。

### P2 - region 切换三区问题

`EyeTracker.vue` `getRegion()` 用 `w/3` 和 `w*2/3` 划分屏幕，但只映射 A/B 两个 region。中间出现停留区不触发切换，用户可能在中间区域看而系统不切换偏好。

### P2 - 眼动数据提交时序

`App.vue` 中 `timeOnA/timeOnB` 等数据在 API 响应到达后才 reset（`lines 172-175`）。快速连续提交时会携带上一轮的残留值。

### P3 - v-html XSS 风险

AI 输出通过 `marked` 渲染后用 `v-html` 插入 DOM。理论上 AI 输出可能包含恶意 HTML。

### P3 - 无错误边界

API 失败、文件写入失败仅在 console.log 输出，用户无感知。DeepSeek API 调用失败时 `split_user_question` 返回 `None` 退化为单次回答，前端不知道拆分失败。

### P3 - FileTreeNode.vue 有 emoji

违反 AGENTS.md "no emojis in code" 规则。

### P3 - DiffPreview.vue 死代码

`DiffPreview.vue` 存在于文件系统但从未被任何组件 import。

---

## 下一阶段开发计划

### Phase 6: 修复 segments + code blocks 互斥 ✅

已修复：删除了 `!displaySegmentsA` / `!displaySegmentsB` 守卫条件。

### Phase 7: 正确实现 Code Apply Workflow

根据 AGENTS.md 描述（或简化版）：
1. 每个代码块有「暂存修改」按钮 → 弹出 DiffPreview
2. DiffPreview 显示原始文件 vs 新代码的 diff
3. 用户确认后文件写入磁盘
4. 取消暂存可回滚

或者简化：删除 AGENTS.md 中不存在的功能描述，保持当前直接写盘流程。

### Phase 8: 修复眼动追踪数据 bug ✅

1. [x] `calculateFinalAttention()` 只用最后 30% 时段的数据计算最终注视分布
2. [x] 修复 `EyeTracker.vue:63-68` 无用条件分支
3. [x] 修复 region 切换三区问题 — `getRegion()` 改为纯 50/50 分割，消除中间死区

### Phase 9: 同步文档与代码

1. 更新 AGENTS.md 与实际代码一致
2. 删除 README 中已不存在的文件引用
3. 修复字体缩放代码或文档

### Phase 10: 错误处理与健壮性

1. API 失败时前端显示错误提示
2. 文件写入失败时通知用户
3. XSS 防护（DOMPurify 或 sanitize）

---

## 如何运行

```bash
# 前端
cd frontend && bun install && bun run dev   # localhost:5173

# 后端（使用现成 venv）
backend/.venv/bin/python backend/app.py       # localhost:8000
# 或
cd backend && bash run.sh

# 健康检查
curl http://localhost:8000/api/health
```

后端没有 `pip`，使用 `uv` 或直接 `.venv/bin/python`。API 密钥在 `backend/.env`。
