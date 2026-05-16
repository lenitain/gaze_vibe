# GazeVibe AI 工程化优化

## 问题诊断

当前架构 = 裸 API 调用：

```
用户提问 → app.py → client.chat.completions.create() → 返回文本
```

对比 pi-main（AI Agent）：

```
用户提问 → Agent Loop → System Prompt 动态组装 → Tool Calling → 流式事件 → 上下文管理 → 完成
```

核心差距不在 CI/lint/changelog，在于**完全没有 AI 工程架构**。

> 注：此前眼动项目要求生成内容必须限制在屏幕范围内，此约束已解除，不再需要考虑。

---

## 改造总结

### Phase 1: LLM 客户端层 ✅

`backend/llm_client.py` — 统一 LLM 调用接口：
- `generate()` / `generate_stream()` — 非流式/流式生成
- `generate_structured()` — 支持 Pydantic 模型 / dict schema 的结构化输出
- 自动 retry (指数退避) + fallback 模型链
- Token 用量精确追踪 (`TokenTracker`)
- 调用记录回调 (`on_record`)
- 超时控制、异常分类处理

### Phase 2: 动态 System Prompt 组装 ✅

`backend/prompt_builder.py` — 链式 PromptBuilder：
- `.with_eye_adjustment()` — 眼动偏好动态注入
- `.with_context()` — 项目文件上下文
- `.with_history()` — 对话历史
- `.with_note()` / `.with_output_schema()` — 自由说明
- `build_dual_answer_prompts()` — 一次性构建 A/B prompt

### Phase 3: 结构化输出 ✅

`backend/schemas.py` — Pydantic 输出 schema：
- `DualAnswer` / `SingleAnswer` / `CodeBlock` — 双答案结构化格式
- `SubQuestions` / `AnswerSegment` — 问题分割
- `schema_to_function()` — 自动将 Pydantic 模型转为 function calling schema
- `extract_structured_response()` — function calling 失败时从文本 fallback 解析

### Phase 4: 代码应用 Agent ✅

`backend/tool_agent.py` — 文件操作工具集：
- `read_file` — 读取项目文件（防止路径穿越）
- `write_file` — 创建/覆盖文件（自动创建目录）
- `search_code` — 项目代码搜索（智能排除非源码目录）
- `list_files` — 列出目录结构

### Phase 5: 流式事件协议 ✅

`backend/sse_events.py` — 细粒度事件类型：
- `segment_start` / `segment_end` — 子问题生命周期
- `text_delta` / `text_end` — 逐块文本推送
- `eye_adjustment` — 眼动状态实时更新
- `done` / `error` — 完成/错误事件
- 前端 App.vue 解析逻辑已同步更新

### Phase 6: 上下文管理与日志 ✅

`backend/llm_logger.py` — LLM 调用日志：
- JSONL 持久化（按会话分文件）
- 会话级统计摘要（调用数/token/延迟）
- `truncate_context()` — 上下文窗口截断
- `estimate_tokens()` — 粗略 token 估算

---

## 眼动追踪在各 Phase 中的融合

```
用户提问
  │
  ├─ 附带当前眼动数据 (前端 EyeTracker.vue)
  │
  ▼
LLMClient ──→ ① 调用前传入眼动上下文
  │
  ▼
PromptBuilder ──→ ② with_eye_adjustment() 注入 system prompt
  │
  ▼
StructuredOutput ──→ ③ 精确长度回报 → 眼动归一化更准
  │
  ▼
SSE 流推送 ──→ ④ eye_adjustment 事件推送到前端
  │
  ▼
前端展示答案
  │
  ├─ EyeTracker.vue 继续采集注视数据
  │
  ▼
/preference 保存 ──→ ⑤ EyeTrackerProcessor EMA 更新
  │
  ▼
PromptBuilder (下次调用) ──→ ⑥ 使用更新后的长期模型
```

---

## 文件清单

| 文件 | 说明 | Phase |
|------|------|-------|
| `backend/llm_client.py` | 统一 LLM 调用客户端 | 1 |
| `backend/prompt_builder.py` | 链式 prompt 组装器 | 2 |
| `backend/schemas.py` | Pydantic 输出结构定义 | 3 |
| `backend/tool_agent.py` | 文件操作工具 + agent | 4 |
| `backend/sse_events.py` | SSE 事件类型与序列化 | 5 |
| `backend/llm_logger.py` | LLM 调用日志 + 上下文管理 | 6 |
| `backend/app.py` | 重构：集成所有新模块 | 全部 |
| `frontend/src/App.vue` | 更新 SSE 事件解析逻辑 | 5 |

## 验证

- 所有新模块 Python 导入 ✓
- PromptBuilder 眼动/上下文组装 ✓
- Schema 转换（Pydantic → function calling） ✓
- SSE 事件序列化 ✓
- LLMLogger 记录/统计 ✓
- 上下文截断 ✓
- app.py 启动 + 路由 ✓
- EyeTrackerProcessor 兼容 ✓
