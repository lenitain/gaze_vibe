# GazeVibe 工程化重构规划（参考 pi 架构）

基于对 pi (`/home/lenitain/.cloned/pi-main`) 架构的深入分析，以下是 GazeVibe 需要学习并落地的工程化改造。

---

## pi 的关键架构模式

| 模式 | pi 实现 | GazeVibe 现状 |
|------|---------|--------------|
| **Storage 抽象** | `SessionStorage<T>` 接口 + JsonlSessionStorage / InMemorySessionStorage | 纯内存无接口（persona_state.py 硬编码 dict，memory 硬编码 list） |
| **事件系统** | `AgentEvent` 联合类型（agent_start/turn_start/message/tool_call/agent_end） | SSE 事件协议虽定义但无类型事件流消费 |
| **Tool 系统** | `AgentTool<T>` + TypeBox JSON Schema + execute handler + onUpdate 流式回调 | tool_agent.py 半成品，不支持真正的 function calling 循环 |
| **Session 树** | Tree 结构（entry→parentId→leafId），支持分支、compaction、label | 扁平 conversationHistory[] 数组，无版本/分支概念 |
| **Result 类型** | `Result<T,E> = {ok:true, value} | {ok:false, error}` 显式错误处理 | 到处 raise/try-except，异常链路不清晰 |
| **测试体系** | vitest + 完善的 harness/mock 测试 | 仅 2 个 Python 单测，无集成测试 |

---

## 重构计划（分阶段）

### 第一阶段：基础设施（Storage 抽象 + Result 类型）

#### 1.1 引入 Result 类型

新建 `backend/result.py`，统一所有返回值风格（不可用 types.py 因与标准库冲突）：

```python
@dataclass
class Ok[T]:
    value: T

@dataclass
class Err[E]:
    error: E

type Result[T, E] = Ok[T] | Err[E]

def ok[T](value: T) -> Ok[T]: ...
def err[E](error: E) -> Err[E]: ...
def unwrap[T,E](r: Result[T,E]) -> T: ...
```

**改动文件**: 新增 `backend/result.py`
**涉及模块**: 所有现有模块逐步迁移

#### 1.2 Storage 抽象接口

```python
class Storage[TMetadata]:
    async def get_metadata(self) -> TMetadata: ...
    async def set_metadata(self, meta: TMetadata): ...

class MemoryStorage[TMetadata](Storage[TMetadata]):
    # 纯内存，进程退出即清空

class JsonlStorage[TMetadata](Storage[TMetadata]):
    # 可选的持久化后端（需时启用）
```

**现有数据实体** → 各自实现 Storage：

| 实体 | 当前存储方式 | 改为 |
|------|------------|------|
| PersonaState | 内存 dict `_in_memory_states` | `Storage[PersonaState]` |
| Memory items | 内存 list | `Storage[list[MemoryItem]]` |
| EyeProcessor state | 全局单例 `eye_processor` | `Storage[EyeState]` |
| 实验日志 | 无（已移除） | 可选 `Storage[ExperimentRecord]` |

**改动文件**: 新增 `backend/storage/__init__.py`, `backend/storage/memory.py`, `backend/storage/jsonl.py`, `backend/storage/types.py`
**涉及模块**: `persona_state.py`, `memory/store.py`, `app.py`, `eye_tracker_processor.py`

---

### 第二阶段：事件系统 + Session 管理

#### 2.1 结构化事件系统

参考 pi 的 `AgentEvent`，给 GazeVibe 的 SSE 协议加上事件流消费：

```python
@dataclass
class SessionStart: ...
@dataclass  
class TurnStart: ...
@dataclass
class MessageStart: ...
@databclass
class MessageDelta: ...
@dataclass
class MessageEnd: ...
@dataclass
class ToolCallExec: ...
@dataclass
class EyeAdjustment: ...
@dataclass
class SessionEnd: ...
```

**改动文件**: `backend/sse_events.py`
**涉及**: `app.py` 中 SSE generate() 函数改为事件驱动的 EventStream 模式

#### 2.2 Session 树

替代当前扁平的 `conversationHistory[]`：

```python
class SessionEntry:
    id: str
    parent_id: str | None
    type: Literal["message", "eye_data", "choice", "persona_change", ...]
    timestamp: str
    data: dict

class Session:
    storage: Storage[SessionMetadata]
    
    async def append(self, entry: SessionEntry) -> str: ...
    async def get_branch(self) -> list[SessionEntry]: ...
    async def build_context(self) -> list[dict]: ...
```

**改动文件**: 新增 `backend/session.py`
**涉及**: `app.py` 替代当前的 `conversationHistory` + SSE 生成

---

### 第三阶段：工具系统重构（后端静默执行，SSE 协议不变）

#### 3.1 设计原则 —— 参考 pi 的 hideThinking 模式

```
pi hideThinking:
  后端 ──→ 生成 thinking + text ──→ SSE ──→ 前端检查 hideThinking 标记
                ↑                          │
          照常生成 thinking            true→显示 "Thinking..." 标签
                                      false→显示实际 thinking 内容

GazeVibe hideToolCalls:
  后端 ──→ Agent Loop 执行工具 ──→ 最终文本 ──→ SSE ──→ 前端展示最终答案
                ↑                                      │
           照常跑工具循环                       不知道后端执行了工具
                                                     （只有 loading 动画）
```

**关键原则**：SSE 协议不变，前端完全不需要知道工具循环的存在。  
后端 Agent Loop 取代当前的单次 LLM 调用，但对外接口一致——输入 prompt，输出文本。

#### 3.2 实现方式

当前 `generate_dual_answers()` 内：

```python
# 当前：单次 LLM 调用
response_a = llm_client.generate(system_prompt=prompt_a, user_prompt=prompt)
answer_a = response_a.text
```

改为：

```python
# 改为：Agent Loop 静默执行
agent = AgentLoop(tools, llm_client, max_turns=6)
result_a = agent.run(system_prompt=prompt_a, user_prompt=prompt)
answer_a = result_a.text  # 最终文本，中间 tool_call 对调用方不可见
```

`/api/ask` 端点的 SSE generate() 函数完全不变——它只关心拿到 `answer_a` / `answer_b`，不关心它们是怎么生成的。

#### 3.3 SSE 协议无变化

```
segment_start → text_delta × N → text_end → eye_adjustment → done
```

前端 `App.vue` / `AnswerPanel.vue` **零改动**。

#### 3.4 Loading 状态

工具循环可能比单次 LLM 调用耗时更长。前端已有 `isLoading` spinner：

```
AI 思考中... ◎ ← 这个 spinner 在工具循环期间保持旋转
```

无需新增 UI 元素。如果希望给用户更明确的反馈，后端可在工具循环期间定期推送 SSE event：

```python
# 可选的进度提示（用于长时间工具循环）
yield {"type": "progress", "status": "正在读取文件..."}
yield {"type": "progress", "status": "正在修改代码..."}
```

前端可选地消费这些事件显示简短文字（但不影响答案面板布局）。

---

### 第四阶段：测试体系

#### 4.1 单元测试

为 Storage、Session、Tool 系统添加 pytest 测试，参考 pi 的 `storage.test.ts`:

```
tests/
  test_storage.py      # MemoryStorage 增删改查
  test_session.py      # Session 树构建 + context 构建
  test_tool_agent.py   # Tool 注册 + 执行
  test_eye_tracker.py  # EMA 计算（已有但需完善）
  test_persona.py      # 收敛 + 反转 + 眼动调制
```

#### 4.2 集成测试

参考 pi 的 `e2e.test.ts`，建立端到端测试：

```
test_e2e.py  # 模拟完整对话：提问→生成答案→眼动→选择→Persona更新
```

---

## 实施顺序

```
Phase 1: Storage 抽象
  ├── backend/result.py (Result 类型)
  ├── backend/storage/types.py (Storage 接口)
  ├── backend/storage/memory.py (MemoryStorage)
  └── 模块逐步迁移到 Storage

Phase 2: 事件系统
  ├── backend/sse_events.py 重构（事件联合类型）
  ├── backend/session.py (Session 树)
  └── app.py SSE 生成改为 EventStream 模式

Phase 3: 工具系统
  ├── 新增 pydantic 依赖
  ├── backend/tool.py (统一 Tool 定义)
  └── backend/agent_loop.py (完整 function calling 循环)

Phase 4: 测试
  ├── tests/ 目录
  ├── test_storage.py
  ├── test_session.py
  └── test_e2e.py
```
