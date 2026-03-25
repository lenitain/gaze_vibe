# GazeVibe

基于眼动追踪和注意力机制的 AI 编程助手原型。

## 项目简介

模拟"豆包风格的双答案模式"：同一个问题生成两份不同风格的回答（详细 vs 简洁），通过眼动追踪捕捉用户阅读差异，基于阅读偏好优化后续回答。

## 技术栈

- **前端**: Vue 3 + Vite + WebGazer.js
- **后端**: Python Flask + OpenAI API
- **眼动追踪**: WebGazer.js (摄像头基础，4象限精度)

## 快速开始

### 1. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 配置 OpenAI API Key

```bash
# 方式1: 环境变量
export OPENAI_API_KEY="your-api-key"

# 方式2: 直接修改 app.py 中的 api_key
```

### 3. 启动后端

```bash
cd backend
python app.py
```

后端将在 http://localhost:8000 启动

### 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

前端将在 http://localhost:5173 启动

### 5. 使用

1. 打开浏览器访问 http://localhost:5173
2. 允许摄像头权限（用于眼动追踪）
3. 输入编程问题
4. 系统生成两个答案（详细/简洁）
5. 阅读时，眼动追踪自动记录阅读偏好
6. 选择一个答案，系统记录偏好用于优化下次回答

## 目录结构

```
gaze-vibe/
├── frontend/          # Vue 前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── AnswerPanel.vue    # 双答案面板
│   │   │   ├── EyeTracker.vue    # 眼动追踪组件
│   │   │   └── ChatInput.vue     # 输入框
│   │   ├── App.vue
│   │   └── main.js
│   └── index.html
├── backend/           # Python 后端
│   ├── app.py
│   └── requirements.txt
└── README.md
```

## 核心功能

### 眼动追踪

- 使用 WebGazer.js 进行浏览器端眼动追踪
- 4象限精度：区分左右两个答案区域
- 记录指标：
  - 首次注视区域
  - 各区域停留时长
  - 切换次数

### 偏好学习

- 根据用户选择的答案调整下次回答风格
- 根据阅读时长比例微调回答详细程度

## 注意事项

1. 眼动追踪需要摄像头权限
2. 首次使用建议进行校准以提高精度
3. 需要稳定的网络连接以调用 OpenAI API
4. 当前版本为原型，仅支持 OpenAI API

## 后续优化方向

- [ ] 支持 Claude API
- [ ] 支持本地 LLM (Ollama)
- [ ] 改进眼动追踪精度
- [ ] 增加 opencode 集成实现文件修改
- [ ] 增加用户实验数据收集功能
