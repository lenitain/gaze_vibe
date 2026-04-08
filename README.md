# GazeVibe

眼动追踪 AI 编程助手。同一个问题生成两份不同风格的回答（详细 vs 简洁），通过眼动追踪捕捉用户阅读偏好，基于偏好优化后续回答。

## 技术栈

- **前端**: Vue 3 + Vite (bun)
- **后端**: Python Flask + DeepSeek API
- **眼动追踪**: WebGazer.js (摄像头基础，2 区域精度)

## 快速开始

```bash
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
│   │   ├── App.vue                      # 根组件，状态管理
│   │   ├── main.js
│   │   ├── components/
│   │   │   ├── AnswerPanel.vue          # 双答案面板 + 代码暂存
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
│   │   │   └── fileSelector.js          # 关键词匹配选取相关文件
│   │   └── styles/
│   │       └── everforest.css           # Everforest 主题变量
│   └── index.html
├── backend/
│   ├── app.py                           # Flask 服务，DeepSeek API 调用
│   ├── .env                             # DEEPSEEK_API_KEY
│   ├── run.sh                           # 一键启动脚本
│   └── requirements.txt
└── README.md
```

## 核心流程

### 双答案生成

后端对同一问题发起两次 DeepSeek API 调用，使用不同的 system prompt：

- **Answer A** — 详细导师风格：分析问题，给出完整代码和解释
- **Answer B** — 简洁助手风格：简短说明，只给修改后的代码

### 代码应用工作流

1. `codeParser.js` 从 AI 回答中解析代码块，`extractFilePath` 匹配到项目文件
2. 匹配到文件的代码块显示「暂存修改」按钮；未匹配的仅展示代码预览
3. 点击「暂存修改」→ DiffPreview 弹窗 → 点击「应用修改」暂存 → 按钮变为红色「已暂存 (取消)」
4. 点击「选择此答案」→ 将该面板暂存的文件写入磁盘

每个面板独立管理暂存状态：`fileChangesA` / `fileChangesB`。文件通过 `_stagedBy` 标记来源（A 或 B），`handleChoice(side)` 只写入对应面板暂存的文件。

### 眼动追踪

WebGazer 初始化一次，每个会话 `resume()` / `pause()`。追踪指标：

- 各区域（详细/简洁）停留时长
- 左右切换次数

DiffPreview 打开期间，眼动数据归属到打开 diff 的对应面板。

## 浏览器兼容性

File System Access API（`window.showDirectoryPicker`）需要 Chrome 86+。

## 主题

Everforest Dark Medium。字体大小 1.5x 缩放（`--font-xs` = 18px）。颜色变量见 `src/styles/everforest.css`。
