# PROGRESS: 多轮回答 - 一次提问，系统自动分多次回答

## 目标

眼动追踪场景。用户**问一次**，系统**自动回复多次**：
- 第 1 次回答：覆盖问题的一个方面（短，不需滚动）
- 第 2 次回答：覆盖另一个方面（短，不需滚动）
- 第 3 次...
- 用户全程只看，零交互
- 每轮由系统自动触发（不需用户再次输入）

这样每轮的眼动数据质量高（内容短，用户不滚动），且覆盖全面。

## 问题：当前实现为什么不行

当前后端 `recursive_split_answer()` + `/api/ask-v2` SSE 的做法：

```
用户提问
  │
  ▼
generate_single_answer() → 生成完整长回答（A/B 各一份）
  │
  ▼
call_ai_to_split(完整回答) → 让 AI 把"已生成的回答"反向拆成子任务
  │
  ▼
每个子任务 → 递归 generate_single_answer(子任务prompt) → 重新生成
```

三个致命缺陷：

1. **拆的是回答，不是问题**：`call_ai_to_split()` 把 AI 刚写出来的代码喂给 AI，让 AI"反向工程"出子任务。AI 擅长写代码，不擅长拆自己写的答案。结果：JSON 格式失败、子任务重叠、遗漏内容。

2. **先写全文再重写**：先生成了完整长回答（浪费 2 次 API），再拆成子任务重新生成（每子任务又 2 次 API）。5 子任务 = 13 次调用，且子任务之间不一致（因为重新生成的代码和原文不同）。

3. **递归爆炸**：深度 3 层 + 每层 2 次 API + 每子任务可再递归 → 调用数的组合爆炸。

## 方案：拆用户问题，不拆 AI 回答

核心思路变了：

```
❌ Plan A: 用户问题 → AI 生成完整回答 → AI 拆回答 → 重新生成每段
✅ 正确做法: 用户问题 → AI 拆成子问题 → 对每个子问题生成回答（每轮回答都是独立生成的，互相一致）
```

子问题是"规划"层面的东西——把"实现用户认证系统"拆成 ["创建 User 模型", "添加注册接口", "添加登录接口"]。AI 擅长这个（规划问题比拆答案简单得多）。

### 流程

```
用户提问: "实现一个用户认证系统"
  │
  ▼
后端 split_user_question()
  │  调用 DeepSeek, 系统 prompt:
  │  "把用户的编程问题拆成 2-4 个独立子问题,
  │   每个子问题有明确的代码输出, 回答控制在 20 行内"
  │
  ├─ 子问题 1: "创建 User 模型 with email/password"
  ├─ 子问题 2: "实现注册端点 with 输入验证"
  ├─ 子问题 3: "实现登录端点 with JWT"
  └─ 子问题 4: "添加密码重置流程"
  │
  ▼
对每个子问题，generate_dual_answers(子问题, 上下文)
  ├─ 子问题 1 → answerA_1, answerB_1
  ├─ 子问题 2 → answerA_2, answerB_2  (带上前一步摘要)
  ├─ 子问题 3 → answerA_3, answerB_3
  └─ 子问题 4 → answerA_4, answerB_4
  │
  ▼
通过 SSE 流式返回多个 chunk（保持 Plan A 的 SSE 格式不变）:
  event: chunk → data: {index:0, total:4, answerA:"...", answerB:"...", hint:"User 模型"}
  event: chunk → data: {index:1, total:4, answerA:"...", answerB:"...", hint:"注册接口"}
  event: chunk → data: {index:2, total:4, answerA:"...", answerB:"...", hint:"登录接口"}
  event: chunk → data: {index:3, total:4, answerA:"...", answerB:"...", hint:"密码重置"}
  event: done → data: {success: true}
  │
  ▼
前端逐轮展示（已有逻辑不变）:
  chunk 到达 → push 到 answerChunksA/B
  answerA.value = chunks 拼接
  AnswerPanel 用 displaySegmentsA 渲染多个 segment-block
  每轮有淡入动画
```

### 关键区别

| | Plan A（递归 AI 拆分） | 正确做法 |
|---|---|---|
| 拆什么 | 拆 AI 生成的回答 | 拆用户的问题 |
| 怎么拆 | `call_ai_to_split(answer)` — 让 AI 反推子任务 | `split_user_question(prompt)` — 让 AI 做规划 |
| 子任务来源 | 从完整回答反向提取 | 从用户问题正向规划 |
| 一致性 | 差（子任务是重新生成的，和原文不同） | 好（每个子问题独立生成但共享上下文） |
| 成本 | 2(原始)+1(拆分)+2N(子任务) | 1(拆分)+2N(子任务) |
| 递归 | 深度 3 层，可组合爆炸 | 无递归，扁平列表 |

## 实现细节

### backend/app.py 改动

**新增函数**：
```python
def split_user_question(prompt, context_files, max_sub_questions=4):
    """
    把用户问题拆成多个子问题。

    参数:
        prompt: 用户原始问题
        context_files: 项目文件上下文
        max_sub_questions: 最多拆成几个子问题

    返回:
        [{id: str, prompt: str, contextHint: str, dependsOn: str}, ...]
        失败时返回 None
    """

    split_system = """
    你是一个任务规划助手。用户的编程问题需要从多个角度回答。
    请将用户的问题拆成 2-{max} 个独立子问题。

    要求:
    1. 每个子问题专注一个具体方面
    2. 每个子问题的 AI 回答应较短（不超过 20 行代码 + 5 行说明）
    3. 子问题之间保持逻辑顺序
    4. 不要遗漏重要方面
    5. 每个子问题应该独立的、可回答的

    输出 JSON 格式:
    [
      {{"id": "1", "prompt": "请实现...", "contextHint": "核心函数", "dependsOn": ""}},
      {{"id": "2", "prompt": "请添加...", "contextHint": "边界处理", "dependsOn": "1"}}
    ]
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": split_system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        json_match = re.search(r"\[[\s\S]*\]", raw)
        if json_match:
            return json.loads(json_match.group())[:max_sub_questions]
        return None
    except Exception as e:
        print(f"问题拆分失败: {e}")
        return None
```

**修改 `/api/ask`**：
```python
@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.json
    prompt = data.get("prompt", "")
    context_files = data.get("contextFiles", [])
    experiment_mode = data.get("experimentMode", "full")
    eye_data = data.get("eyeData")

    if not prompt:
        return jsonify({"error": "请输入问题"}), 400

    sub_questions = split_user_question(prompt, context_files)

    # 不需要拆分 → 直接返回单个回答
    if not sub_questions:
        result = generate_dual_answers(prompt, context_files, eye_data)
        result["experimentMode"] = experiment_mode
        result["segments"] = []
        return jsonify(result)

    # 需要拆分 → 依次生成每个子问题
    segments = []
    prev_summary = None

    for sq in sub_questions:
        sub_prompt = sq["prompt"]
        if prev_summary and sq.get("dependsOn"):
            sub_prompt = f"上一步: {prev_summary}\n\n当前: {sub_prompt}"

        # 携带上下文（原始问题 + 项目文件）
        full_prompt = f"原始问题: {prompt}\n\n当前子任务: {sub_prompt}"
        result = generate_dual_answers(full_prompt, context_files, eye_data)

        segments.append({
            "id": sq["id"],
            "hint": sq.get("contextHint", ""),
            "answerA": result.get("answerA", ""),
            "answerB": result.get("answerB", ""),
            "success": result.get("success", False),
        })

        if result.get("success"):
            preview = result.get("answerB", result.get("answerA", ""))
            prev_summary = preview[:200] + "..." if len(preview) > 200 else preview

    # 也返回完整拼接
    full_a = "\n\n---\n\n".join(s["answerA"] for s in segments if s["answerA"])
    full_b = "\n\n---\n\n".join(s["answerB"] for s in segments if s["answerB"])

    return jsonify({
        "answerA": full_a,
        "answerB": full_b,
        "segments": segments,
        "success": True,
        "experimentMode": experiment_mode,
    })
```

注意：如果 `sub_questions` 只有 1 个，或者拆分失败，退化为直接返回单次回答（`segments: []`，前端按旧逻辑渲染）。

**删除内容**：
- `recursive_split_answer()` — 不再递归
- `call_ai_to_split()` — 不再拆 AI 回答
- `MIN_SPLIT_THRESHOLD` — 不再需要
- `MAX_SUB_TASKS` — 不再需要
- `estimate_lines()` — 不再需要估算（每轮由 prompt 保证短）
- `generate_single_answer()` — 不再需要（子问题用 generate_dual_answers）
- `/api/ask-v2` 路由 — SSE 逻辑移到 `/api/ask` 内部

### frontend/src/App.vue

现有 SSE 接收逻辑基本可以复用，但做简化：

- `handleSubmit` 只用 `/api/ask`
- 如果返回 `segments.length > 0`，设 `answerSegmentsA/B` 为分段
- 如果返回 `segments.length === 0`，按旧逻辑渲染单次回答
- 删除 `answerChunksA/B` 独立数组（segments 代替）

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

    let eyeData = null
    // 眼动数据收集保持不变...

    const response = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt, contextFiles,
        experimentMode: experimentMode.value,
        eyeData
      })
    })
    const data = await response.json()

    answerA.value = data.answerA || ''
    answerB.value = data.answerB || ''

    if (data.segments && data.segments.length > 1) {
      answerSegmentsA.value = data.segments.map(s => ({
        id: s.id, contextHint: s.hint, content: s.answerA
      }))
      answerSegmentsB.value = data.segments.map(s => ({
        id: s.id, contextHint: s.hint, content: s.answerB
      }))
    }
  } finally {
    isLoading.value = false
  }
}
```

### frontend/src/components/AnswerPanel.vue

保留两种渲染模式（已有）：

1. **segments 模式**（`displaySegmentsA/B` 有值）→ 逐轮展示，每轮含 text + code blocks
2. **flat 模式**（单次回答）→ 旧逻辑：stripCodeBlocks + codeBlocks 分离

bug 修复：segment 内容应保留代码 fence（每个 segment 是完整 markdown），但需要干净渲染。当前问题在于 `v-html` 不能渲染 markdown。需要改用 markdown 渲染库（如 `marked`）或保留 code fence 解析。

## 前端渲染修复

当前 segments 用 `v-html` 渲染 seg.content（原始 markdown），结果代码 fence 以纯文本显示。修复：

```
选项 A: 轻量 markdown 渲染（如 marked.js）
选项 B: segment 内容已经够短，后端保证短到可不渲染 markdown
        直接用 <pre> 或 white-space: pre-wrap 展示
选项 C: 每个 segment 再拆成 text/code block 子段
```

推荐选项 A 或 B（选项 C 太复杂）。选 A 的话加 `marked` 依赖。

## 文件改动清单

| 文件 | 改动 |
|------|------|
| `backend/app.py` | 新增 `split_user_question()`；删除 `recursive_split_answer()`, `call_ai_to_split()`, `MIN_SPLIT_THRESHOLD`, `MAX_SUB_TASKS`, `estimate_lines()`, `generate_single_answer()`, `/api/ask-v2`；修改 `/api/ask` 返回 segments |
| `frontend/src/App.vue` | 删除 SSE 相关；`handleSubmit` 只用 `/api/ask`；segments → answerSegmentsA/B |
| `frontend/src/components/AnswerPanel.vue` | 保留双模式；修复 seg.content 渲染（加 marked 或 pre-wrap） |
| `frontend/package.json` | 可能加 `marked` 依赖 |

## 里程碑

- [x] Phase 1: 后端 `split_user_question()` 实现 + `/api/ask` 修改
- [x] Phase 2: 删除旧递归拆分代码
- [x] Phase 3: 前端简化（删除 SSE，调 `/api/ask`）
- [x] Phase 4: 前端展示修复（segment 内容干净渲染）
- [x] Phase 5: 验证 — 问题自动拆 2-4 轮，每轮短到不需滚动
  - [x] Phase 5a: 清理前端死代码（answerChunksA/B, 未用工具文件）
  - [x] Phase 5b: 编写测试脚本验证 split_user_question() — 4/4 测试通过（3-4 子问题/每次）
  - [x] Phase 5c: 修复 segments 模式重复代码块渲染，验证前端展示
  - [x] Phase 5d: 删除死代码 — ask_batch() 路由, code_refactor.py

## 依赖

```
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5
```

Phase 2 可以和 Phase 1 一起做。Phase 4 需要等 Phase 3 确定 seg.content 格式。
