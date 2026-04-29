# PROGRESS: 长回答自动拆分重构

## 目标

取消"上一页/下一页"翻页机制。长回答自动拆分成多次API调用，用户无感。

## 核心需求

1. **多次回答**：一个用户问题 → 多次LLM API调用 → 多个回答片段
2. **用户无感**：拆分对用户透明，感觉是自然的多次回答
3. **智能切分**：
   - 可切分的代码段 → 直接按函数/模块切分
   - 不可切分的大函数 → 先让LLM重构，再切分

## 当前架构

```
用户问题 → 后端 generate_dual_answers() → 2次API调用 → answerA + answerB
                                                        ↓
                                          前端 splitAnswer() 按代码块切分
                                                        ↓
                                          翻页浏览 (上一段/下一段)
```

## 目标架构

```
用户问题 → 前端判断是否需要拆分 → 拆分成子问题列表
                                       ↓
                              后端 /api/ask-batch (多次调用)
                                       ↓
                              前端整合多个回答 → 连续显示，无翻页
```

## 实现步骤

### Phase 1: 问题拆分逻辑

**文件**: `frontend/src/utils/questionSplitter.js` (新建)

功能：
- 分析用户问题的复杂度
- 如果问题涉及多个文件/模块，拆分成子问题
- 每个子问题独立调用API

拆分策略：
1. **单文件修改**：不拆分，直接调用
2. **多文件修改**：按文件拆分，每个文件一个子问题
3. **大函数重构**：先调用API重构函数，再拆分

### Phase 2: 后端批量API支持

**文件**: `backend/app.py` (修改)

新增路由：
- `POST /api/ask-batch`：接收子问题列表，批量调用API
- 支持流式响应（SSE），实时返回每个子问题的结果

```python
@app.route("/api/ask-batch", methods=["POST"])
def ask_batch():
    """批量处理子问题"""
    data = request.json
    sub_questions = data.get("subQuestions", [])
    
    results = []
    for sq in sub_questions:
        result = generate_dual_answers(sq["prompt"], sq.get("contextFiles"))
        results.append({
            "id": sq["id"],
            "answerA": result["answerA"],
            "answerB": result["answerB"],
        })
    
    return jsonify({"results": results})
```

### Phase 3: 前端整合显示

**文件**: `frontend/src/components/AnswerPanel.vue` (修改)

改动：
- 移除 `splitAnswer` 相关逻辑
- 移除 `currentSegmentA/B`、`prevSegment/nextSegment` 函数
- 移除"上一段/下一段"按钮
- 新增 `answerSegments` 数组，存储多次API调用的结果
- 连续显示所有片段，无分页

显示逻辑：
```javascript
// 原来
const segmentsA = computed(() => splitAnswer(props.answerA))
const currentSegmentA = ref(0)

// 改为
const answerSegmentsA = ref([])  // 多次API调用的结果列表
const answerSegmentsB = ref([])
```

### Phase 4: 代码重构支持

**文件**: `backend/app.py` (修改)

新增函数：
```python
def refactor_large_code(code_block, context_files):
    """
    如果代码块太大，调用LLM重构
    返回重构后的多个小函数
    """
    system_prompt = """你是一个代码重构专家。
    请将以下大函数拆分成多个小函数，每个小函数职责单一。
    返回格式：
    ```javascript
    // 函数1: xxx
    function func1() {}
    
    // 函数2: xxx
    function func2() {}
    ```
    """
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"请重构以下代码:\n\n```javascript\n{code_block}\n```"},
        ],
    )
    
    return response.choices[0].message.content
```

### Phase 5: 眼动数据适配

**文件**: `frontend/src/App.vue` (修改)

改动：
- 眼动数据收集逻辑需要适配多次回答
- 每个子问题的眼动数据独立收集
- 汇总后发送给后端

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

1. 用户提交问题后，无翻页按钮
2. 长回答自动拆分成多个片段连续显示
3. 眼动数据正确收集（无翻页干扰）
4. 代码重构功能正常工作

## 风险点

1. **API成本**：多次调用增加成本
2. **响应时间**：串行调用变慢
3. **拆分质量**：自动拆分可能破坏代码完整性
4. **上下文丢失**：多次调用之间上下文不连续

## 缓解措施

1. 限制最大拆分次数（如3次）
2. 使用SSE流式响应，边生成边显示
3. 拆分后让LLM验证代码完整性
4. 传递前一个子问题的摘要作为上下文
