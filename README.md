# GazeVibe

眼动追踪 AI 编程助手。同一个问题生成两份不同风格的回答（详细 vs 简洁），通过眼动追踪捕捉用户阅读偏好，基于偏好优化后续回答。

## 技术栈

- **前端**: Vue 3 + Vite (bun)
- **后端**: Python Flask + DeepSeek API
- **眼动追踪**: WebGazer.js (摄像头基础，2 区域精度)
- **数据分析**: pandas, numpy, matplotlib, seaborn, scipy

## 快速开始

```bash
# 一键启动（推荐）
./dev.sh

# 或分别启动
# 前端
cd frontend && bun install && bun run dev   # http://localhost:5173

# 后端（使用已有 venv）
backend/.venv/bin/python backend/app.py      # http://localhost:8000
# 或: cd backend && bash run.sh

# 健康检查
curl http://localhost:8000/api/health
```

后端没有 `pip`，请直接使用 venv 或 `uv`。

API Key 配置在 `backend/.env`（`DEEPSEEK_API_KEY`），已从 git 排除。

## 目录结构

```
gaze-vibe/
├── frontend/
│   ├── src/
│   │   ├── App.vue                      # 根组件，状态管理，实验模式切换
│   │   ├── main.js
│   │   ├── components/
│   │   │   ├── AnswerPanel.vue          # 双答案面板 + 代码暂存 + 智能截断
│   │   │   ├── ChatInput.vue            # 输入框
│   │   │   ├── DiffPreview.vue          # 修改预览弹窗
│   │   │   ├── EyeTracker.vue           # WebGazer 眼动追踪
│   │   │   ├── FolderSelector.vue       # 文件夹选择器
│   │   │   ├── FileTree.vue             # 侧边栏文件树
│   │   │   ├── FileTreeNode.vue         # 文件树节点
│   │   │   └── FileViewer.vue           # 文件内容查看器
│   │   ├── utils/
│   │   │   ├── codeParser.js            # 代码块解析、文件路径提取、diff
│   │   │   ├── fileIndexer.js           # File System Access API 目录扫描
│   │   │   ├── fileSelector.js          # 关键词匹配选取相关文件
│   │   │   ├── questionSplitter.js      # 问题分割（多文件/复杂度）
│   │   │   ├── answerMerger.js          # 子问题答案合并
│   │   │   └── answerSplitter.js        # 答案文本/代码分割
│   │   └── styles/
│   │       └── everforest.css           # Everforest 主题变量
│   └── index.html
├── backend/
│   ├── app.py                           # Flask 服务，DeepSeek API 调用
│   ├── eye_tracker_processor.py         # 眼动数据处理器（EMA 平滑）
│   ├── code_refactor.py                 # 大函数自动重构
│   ├── experiment_data.jsonl            # 实验数据记录
│   ├── .env                             # DEEPSEEK_API_KEY
│   ├── run.sh                           # 一键启动脚本
│   └── requirements.txt
├── scripts/
│   ├── analyze_experiment.py            # 实验数据分析脚本
│   ├── run.sh                           # 一键运行分析
│   └── requirements.txt
├── docs/
│   ├── figures/                         # 分析图表 (SVG)
│   └── superpowers/                     # 扩展功能规划
├── dev.sh                               # 开发环境一键启动
├── AGENTS.md                            # AI 助手指南
├── PROGRESS.md                          # 项目进度记录
└── README.md
```

## 核心功能

### 双答案生成

后端对同一问题发起两次 DeepSeek API 调用，使用不同的 system prompt：

- **Answer A** — 注释丰富、讲解详细的代码风格
- **Answer B** — 精简干练、无注释的代码风格

### 实验模式

支持三种 A/B 测试模式，通过 UI 切换：

| 模式 | 眼动追踪 | 自动选择 | 用途 |
|------|----------|----------|------|
| `full` | ✓ | ✓ | 完整实验：眼动 + 自动偏好学习 |
| `manual` | ✓ | ✗ | 手动模式：眼动辅助，用户手动选择 |
| `control` | ✗ | ✗ | 对照组：无眼动，纯手动选择 |

### 智能眼动建模

基于 EMA (指数移动平均) 的用户偏好建模：

- **实时调整**: 基于当前轮次眼动数据计算调整分数
- **长期建模**: 使用 EMA (α=0.3) 平滑用户偏好
- **置信度推断**: 根据数据成熟度和偏好强度计算置信度
- **自动模式**: 置信度 ≥ 0.8 时自动应用偏好

眼动指标映射到两个维度：
- `detail_score`: 详细程度偏好 (0=简洁, 1=详细)
- `explanation_score`: 解释 vs 代码偏好 (0=代码优先, 1=解释优先)

### 问题分割

自动检测多文件修改或复杂代码块，分割为子问题：

- 多文件修改 → 按文件分割 (最多 3 个)
- 大代码块 (>50行) → 重构 + 应用两阶段
- 子问题支持依赖关系（前一步结果传递）

### 代码应用工作流

1. `codeParser.js` 从 AI 回答中解析代码块，`extractFilePath` 匹配到项目文件
2. 匹配到文件的代码块显示「暂存修改」按钮；未匹配的仅展示代码预览
3. 点击「暂存修改」→ DiffPreview 弹窗 → 点击「应用修改」暂存 → 按钮变为红色「已暂存 (取消)」
4. 点击「选择此答案」→ 将该面板暂存的文件写入磁盘

每个面板独立管理暂存状态：`fileChangesA` / `fileChangesB`。文件通过 `_stagedBy` 标记来源（A 或 B），`handleChoice(side)` 只写入对应面板暂存的文件。

### 智能截断

- 文本超过 200px 时自动截断（保留 8 行）
- 代码块始终完整显示，不被截断
- 提供"展开全文 / 收起"切换按钮
- 无滚动条设计

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/ask` | POST | 单问题双答案生成 |
| `/api/ask-batch` | POST | 批量子问题处理 |
| `/api/preference` | POST | 保存用户偏好数据 |
| `/api/eye-model` | GET | 获取眼动模型状态 |
| `/api/eye-model/reset` | POST | 重置眼动模型 |
| `/api/health` | GET | 健康检查 |

## 实验数据分析

```bash
# 一键运行分析
./scripts/run.sh
```

分析维度：
1. 眼动指标有效性 (时间分配、扫视模式、认知负荷、决策预测)
2. 归一化算法有效性 (长度差异处理)
3. 调整分数预测能力
4. EMA 收敛分析
5. 模式对比分析 (full vs manual vs control)

输出 SVG 图表到 `docs/figures/`。

## 浏览器兼容性

File System Access API（`window.showDirectoryPicker`）需要 Chrome 86+。

## 主题

Everforest Dark Medium。字体大小 1.5x 缩放（`--font-xs` = 18px）。颜色变量见 `src/styles/everforest.css`。