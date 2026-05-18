# GazeVibe

眼动追踪 AI 编程助手。同一问题生成两份不同风格的回答，通过眼动追踪和 **多维 Persona 建模** 捕捉用户编程偏好，持续优化后续回答。

## 技术栈

- **前端**: Vue 3 + Vite (bun) + WebGazer.js + MediaPipe FaceMesh
- **后端**: Python Flask + DeepSeek API + Numpy
- **眼动建模**: EMA 指数移动平均 + 10 维工程偏好收敛
- **数据分析**: pandas, numpy, matplotlib, seaborn, scipy
- **代码质量**: Ruff (Python), Biome (JS), pytest, vitest, GitHub Actions CI

## 快速开始

```bash
# 一键启动（推荐）
./dev.sh

# 或分别启动
# 前端
cd frontend && bun install && bun run dev   # http://localhost:5173

# 后端
cd backend && bash run.sh                    # http://localhost:8000

# 健康检查
curl http://localhost:8000/api/health
```

API Key 配置在 `backend/.env`（`DEEPSEEK_API_KEY`），参考 `.env.example` 复制。

## 目录结构

```
gaze-vibe/
├── frontend/
│   ├── src/
│   │   ├── App.vue                       # 根组件：对话历史、SSE 流式、模式切换
│   │   ├── config.js                     # 前端常量（与 backend/config.py 同步）
│   │   ├── main.js
│   │   ├── components/
│   │   │   ├── AnswerPanel.vue           # 双答案面板 + 代码块解析 + 偏好聚焦框
│   │   │   ├── ChatInput.vue             # 输入框
│   │   │   ├── EyeTracker.vue            # WebGazer 眼动追踪（含 MediaPipe Fallback）
│   │   │   ├── FolderSelector.vue        # 文件夹选择器（File System Access API）
│   │   │   ├── FileTree.vue              # 覆盖层文件树
│   │   │   ├── FileTreeNode.vue          # 文件树节点
│   │   │   └── FileViewer.vue            # 文件内容查看器
│   │   ├── utils/
│   │   │   ├── codeParser.js             # 代码块解析、文件路径提取
│   │   │   ├── errors.js                 # 结构化错误处理
│   │   │   ├── fileIndexer.js            # File System Access API 目录扫描
│   │   │   ├── fileSelector.js           # 关键词匹配选取相关文件
│   │   │   └── __tests__/                # 前端单元测试
│   │   └── styles/
│   │       └── everforest.css            # Everforest Dark Medium 主题
│   ├── public/mediapipe/                  # MediaPipe FaceMesh WASM 模型
│   ├── dist/                             # Vite 构建产物
│   └── index.html
├── backend/
│   ├── app.py                            # Flask 主服务（SSE 流式 API）
│   ├── config.py                         # 后端常量（与 frontend/config.js 同步）
│   ├── llm_client.py                     # 统一 LLM 客户端（retry/fallback/streaming）
│   ├── llm_logger.py                     # LLM 调用日志（JSONL + 会话统计）
│   ├── prompt_builder.py                 # 链式 Prompt 组装器
│   ├── persona_loader.py                 # Persona YAML 定义加载器（10 维工程偏好）
│   ├── persona_state.py                  # 多维 Persona 收敛引擎（维度级 EMA）
│   ├── eye_tracker_processor.py          # 眼动数据处理器（EMA 平滑）
│   ├── agent_loop.py                     # 多轮 Tool Calling 代理
│   ├── tool_agent.py                     # 代码应用 Agent（文件读写/搜索工具）
│   ├── schema.py                         # Pydantic 结构化输出 Schema
│   ├── sse_events.py                     # SSE 流式事件协议
│   ├── vector_utils.py                   # Embedding + 余弦相似度
│   ├── errors.py                         # 统一错误处理
│   ├── personas/                         # Persona YAML 定义
│   │   ├── 稳健派.yaml
│   │   └── 现代派.yaml
│   ├── persona_states/                   # Persona 状态持久化（按项目名隔离）
│   ├── prompts/                          # System Prompt Markdown 文件
│   │   ├── system_a.md                   # Answer A 基础指令
│   │   ├── system_b.md                   # Answer B 基础指令
│   │   ├── system_split.md               # 问题分割指令
│   │   └── adjustment_template.md        # 眼动调整模板
│   ├── memory/                           # RAG 记忆系统
│   │   ├── types.py                      # 三层记忆模型（semantic/episodic/procedural）
│   │   ├── store.py                      # 记忆存储（Numpy + JSONL）
│   │   ├── extractor.py                  # 语义记忆提取（LLM 抽取事实）
│   │   └── retrieval.py                  # 汇聚式检索（稠密+稀疏 RRF 融合）
│   ├── memory_data/                      # 记忆数据持久化目录
│   ├── .env                              # DEEPSEEK_API_KEY
│   ├── run.sh                            # 后端启动脚本
│   ├── requirements.txt                  # 依赖
│   └── pyproject.toml                    # 项目元数据 + Ruff 配置
├── scripts/
│   ├── analyze_experiment.py             # 实验数据分析（6 验证维度）
│   ├── analyze_llm_logs.py               # LLM 调用日志分析
│   ├── analyze_memory.py                 # 记忆系统分析
│   ├── analyze_persona.py                # Persona 状态演化分析
│   ├── run.sh                            # 一键运行所有分析
│   └── README.md                         # 分析脚本文档
├── .github/
│   ├── workflows/ci.yml                  # GitHub Actions CI
│   ├── ISSUE_TEMPLATE/                   # Bug/Feature Issue 模板
│   └── PULL_REQUEST_TEMPLATE.md          # PR 模板
├── docs/figures/                         # 分析图表输出
├── dev.sh                                # 开发环境一键启动
├── LICENSE                               # AGPL-3.0
├── PROGRESS.md
└── README.md
```

## 核心功能

### 双答案生成

后端对同一问题发起两次 DeepSeek API 调用，各使用不同的 **Persona** system prompt：

| 面板 | Persona | 风格 |
|------|---------|------|
| **Answer A** | 稳健派 | 注释丰富、讲解详细、工程健壮 |
| **Answer B** | 现代派 | 精简干练、无注释、开发者体验优先 |

Persona 由 10 个工程维度定义（见 Persona 系统）。

### 实验模式

支持三种 A/B 实验模式，通过 UI 切换：

| 模式 | 眼动追踪 | 自动选择 | 用途 |
|------|----------|----------|------|
| `full` | ✓ | ✓ (置信度≥0.8 时) | 完整实验：眼动 + 自动偏好学习 |
| `manual` | ✓ | ✗ | 手动模式：眼动辅助，用户手动选择 |
| `control` | ✗ | ✗ | 对照组：无眼动，纯手动选择 |

前端通过置信度推断自动显示偏好聚焦框。

### 智能眼动建模

基于 EMA (指数移动平均) 的用户偏好建模：

- **实时调整**: 基于当前轮次眼动数据计算调整分数
- **长期建模**: 使用 EMA (α=0.3) 平滑用户偏好
- **置信度推断**: 根据数据成熟度和偏好强度计算置信度
- **聚焦框**: 置信度≥0.5 时显示蓝色聚焦框作为视觉预判

眼动指标映射到两个维度：
- `detail_score`: 详细程度偏好 (0=简洁, 1=详细)
- `explanation_score`: 解释 vs 代码偏好 (0=代码优先, 1=解释优先)

### Persona 多维收敛系统

核心创新：将用户偏好建模从单一人格派系提升为 **10 维工程决策偏好**，每轮用户选择后各维度独立演化。

**维度**（按优先级排列）：

| 维度 | 说明 | 稳健派 | 现代派 |
|------|------|--------|--------|
| 生态成熟度 | 工具/库的生态选择 | 只看最稳的 (5) | 敢于尝试新的 (2) |
| 正确性策略 | 类型安全 vs 运行时覆盖 | 编译器扼杀 (5) | 不迷信类型 (2) |
| 错误处理 | 错误类型 vs anyhow | 自定义错误 (5) | anyhow+? (1) |
| 边界覆盖 | 边缘情况处理程度 | 全部处理 (5) | 先跑通 (1) |
| 测试策略 | 单元测试 vs 集成测试 | 全覆盖 (5) | property-based (2) |
| 依赖哲学 | 加依赖 vs 自包含 | 慎重加 (4) | 不造轮子 (2) |
| 命名风格 | 短名 vs 语义长名 | 语义化 (4) | 短名优先 (2) |
| 文档深度 | 类型即文档 vs 完整 doc | 必有文档 (4) | 类型即文档 (1) |
| 抽象时机 | DRY 驱动 vs 等多次重复 | 适度抽象 (3) | 重复即抽象 (2) |
| 性能优先级 | 可读性 vs 极致性能 | 适度 (3) | benchmark 驱动 (5) |

**收敛机制**：
- 每轮用户选择后，选中侧不变，未选中侧各维度独立 **EMA 收束** 向选中侧
- 各维度独立检测收敛，收敛后 A/B 共用同一分值（侧间差异消失）
- 收敛后有连续反转信号则解除收敛（收敛衰减），重新拉开差距
- 各维度调整速度独立配置，核心工程决策维度收敛快
- **眼动置信度调制调整速度**：眼动数据（persona_bias + 置信度）动态调制各维度 EMA alpha——眼动明确偏所选侧时加速收敛，犹豫或方向矛盾时保守收敛
- 所有维度收敛后进入随机探索模式

### LLM 维度分类

每轮用户问题自动判断涉及哪些 Persona 维度（两级回退）：
1. **LLM 分类**：用 DeepSeek 分析问题语义，精确匹配维度
2. **关键词回退**：正则关键词匹配

### 问题分割

自动检测复杂问题或多文件修改，分割为子问题：

- 多文件修改 → 按文件分割（最多 4 个）
- 支持依赖关系（前一步结果传递）
- SSE 分段推送，每段独立显示

### RAG 记忆系统

三层记忆模型（参考 RagFlow Convergent Context Engine）：

| 类型 | 说明 | 示例 |
|------|------|------|
| **semantic** | 用户项目的长期事实 | "项目使用 Rust + actix-web" |
| **episodic** | 会话事件 | "用户偏好 Persona A" |
| **procedural** | 跨会话隐性偏好模式 | （预留） |

汇聚式检索管线：
1. Query 改写 — 关键词扩展
2. 双路召回 — 稠密 (Embedding) + 稀疏 (关键词 BM25)
3. RRF 融合 — Reciprocal Rank Fusion
4. 注入 — 格式化为 LLM 上下文

### 对话历史

- 每轮对话保存到 `conversationHistory`
- 历史记录中显示已选中的 Persona 面板
- 回看时选择按钮锁定，只展示被选侧

### 代码应用工作流

1. `codeParser.js` 从 AI 回答中解析代码块
2. `extractFilePath` 匹配到项目文件（多种路径识别策略）
3. 侧边栏「文件」按钮打开覆盖层文件树
4. 选择侧按钮 — 将该面板代码块写入磁盘（File System Access API）

### 智能截断

- 文本超过 200px 时自动截断（保留 8 行）
- 代码块始终完整显示，不被截断
- 无滚动条设计

### 错误提示

结构化错误处理系统（`errors.js`）：
- API 错误 / 文件写入错误 / 未知错误
- Toast 提示栏：偏好保存为绿色，API 错误为红色，文件错误为黄色

## 配置

### 后端常量（`backend/config.py`）

所有硬编码集中配置，与 `frontend/src/config.js` 共享关键值（`ALPHA`、`MIN_EYE_TIME`）。

| 分组 | 关键配置 | 默认值 |
|------|----------|--------|
| 眼动 | `ALPHA`、`MIN_EYE_TIME` | 0.3, 2000ms |
| LLM | `LLM_MODEL`、`MAX_RETRIES` | deepseek-chat, 2 |
| Agent | `AGENT_MAX_TURNS` | 6 |
| 答案 | `ANSWER_TEMPERATURE`、`MAX_TOKENS` | 0.7, 3000 |
| 拆分 | `SPLIT_MAX_SUB_QUESTIONS` | 4 |
| 记忆 | `MEMORY_TOP_K`、`MEMORY_DATA_DIR` | 5, memory_data |

### 前端常量（`frontend/src/config.js`）

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `FONT_SCALE` | 1 | 界面整体缩放（0.7=70%） |
| `PERSONA_A_NAME` | 稳健派 | 面板 A 标签 |
| `PERSONA_B_NAME` | 现代派 | 面板 B 标签 |
| `DEBOUNCE_THRESHOLD` | 80ms | 眼动抖动过滤阈值 |

### Persona 定义（`backend/personas/*.yaml`）

每个 Persona 包含：
- `identity`: 身份描述（转成 system prompt 第一部分）
- `scores`: 10 个维度的 1~5 分值
- `anchor_decisions`: 具体场景的锚定决策（可选）

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ask` | POST | SSE 流式：问题分割 + RAG检索 + 双答案生成 |
| `/api/ask-batch` | POST | 批量子问题处理 |
| `/api/preference` | POST | 保存用户偏好 + Persona 收敛 + 眼动建模 |
| `/api/eye-model` | GET | 获取眼动模型状态 |
| `/api/eye-model/reset` | POST | 重置眼动模型 + Persona + 记忆 |
| `/api/stats` | GET | LLM 调用 + 眼动 + 项目统计 |
| `/api/health` | GET | 健康检查 |

## SSE 流式事件协议

后端通过 Server-Sent Events 分段推送答案，事件类型：

| 事件 | 说明 |
|------|------|
| `segment_start` | 子问题开始 |
| `text_delta` | 文本增量 |
| `text_end` | 文本块结束 |
| `segment_end` | 子问题结束 |
| `eye_adjustment` | 眼动调整状态更新 |
| `done` | 全部完成 |
| `error` | 错误 |

## 实验数据分析

```bash
# 一键运行所有分析
./scripts/run.sh
```

分析维度：
1. **维度1**: 眼动指标有效性（时间分配、扫视模式、认知负荷、决策预测）
2. **维度2**: 归一化算法有效性（长度差异处理）
3. **维度3**: 调整分数预测能力（点二列相关）
4. **维度4**: EMA 收敛分析
5. **维度5**: Persona 偏差与偏好趋势
6. **维度6**: 模式对比（full vs manual vs control）

额外分析脚本：
- `analyze_llm_logs.py` — Token 消耗、延迟分布、重试率
- `analyze_memory.py` — 记忆类型分布、置信度、积累趋势
- `analyze_persona.py` — Persona 维度收敛演化、跨项目对比

输出 SVG 图表到 `docs/figures/`。

## LLM 调用日志

所有 LLM 调用记录到 `backend/logs/llm_calls_{timestamp}.jsonl`：
- 每次调用的完整请求/响应预览
- Token 用量精确追踪
- 延迟、成功率、重试次数
- 调用来源标识

```python
# 查看会话统计
from llm_logger import LLMLogger
logger = LLMLogger("logs")
summary = logger.session_summary()
# → {"total_calls": 12, "successful": 12, "total_tokens": 8542, "avg_latency_ms": 1234.5}
```

## 测试

```bash
# 后端测试
cd backend && python -m pytest -v

# 前端测试
cd frontend && bun test
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`)：
- **backend**: ruff lint → pytest
- **frontend**: biome lint → vite build

## 浏览器兼容性

- 眼动追踪需要摄像头权限
- File System Access API（`window.showDirectoryPicker`）需要 Chrome 86+ / Edge 86+

## 主题

Everforest Dark Medium。字体大小由 `FONT_SCALE` 统一缩放。颜色变量见 `src/styles/everforest.css`。

## 许可证

[AGPL-3.0](LICENSE)
