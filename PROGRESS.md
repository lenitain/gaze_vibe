# GazeVibe 项目进度

## 当前状态 (2026-05-06)

### 已完成
- [x] 前后端基础架构（Vue 3 + Flask）
- [x] 双答案生成（详细 vs 简洁）
- [x] 眼动追踪集成（WebGazer.js）
- [x] A/B 实验模式（full / manual / control）
- [x] EMA 眼动偏好建模（6 步骤处理）
- [x] SSE 流式分段推送
- [x] 问题分割（子问题生成）
- [x] 文件上下文（File System Access API）
- [x] 代码块解析与应用工作流
- [x] 实验数据分析脚本（scripts/）

### 本次优化 (prompt-engineering-optimize)
- [x] 创建 AGENTS.md — 项目开发规则
- [x] 创建 PROGRESS.md — 进度跟踪
- [x] 提取 system prompts 到独立文件 `backend/prompts/`
- [x] 重构 `app.py` — 结构化 prompt 加载
- [x] 统一前后端配置（config.py / config.js 同步注释）

### 待办
- [ ] .env 示例文件（已从 git 排除但无模板）
- [ ] 前端眼动指标发送优化（避免 SSE 中重复传递）
- [ ] `EyeTrackerProcessor` 单元测试
- [ ] backend `test_split.py` 完善
- [ ] experiment_data.jsonl 数据清理策略
- [ ] FileViewer 与代码应用工作流边界情况处理
