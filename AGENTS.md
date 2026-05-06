# GazeVibe 开发规则

## 会话风格

- 保持回答简短、技术化
- 无表情符号、无废话填充
- 中文技术文档风格，直接但礼貌

## 代码质量

- **Python 后端**: 使用类型注解，Pydantic 模型优先于裸 dict
- **Vue 前端**: 使用 `<script setup>` + Composition API
- 前后端配置常量保持同步 (`config.py` / `config.js`)
- 所有 `except` 必须有具体异常类型，不要裸 `except:`
- 眼动数据处理逻辑变化前必须验证对 `EyeTrackerProcessor` 状态机的影响
- 修改 SSE 事件格式前必须同步前后端解析逻辑

## Prompt 管理

- 所有 LLM system prompt 存放在 `backend/prompts/` 目录
- 每个 prompt 使用 Markdown 文件 + frontmatter 元数据
- 不要在 `app.py` 中硬编码长 prompt 字符串
- 修改 prompt 后更新对应的 frontmatter `version` 字段

## 命令

- 后端测试: `cd backend && python -m pytest test_*.py -v`
- 前端测试: `cd frontend && bunx vitest run`
- 一键启动: `./dev.sh`
- 眼动处理器测试: `cd backend && python -c "from eye_tracker_processor import EyeTrackerProcessor; p=EyeTrackerProcessor(); r=p.process({'timeOnA':5000,'timeOnB':3000,'answerALength':500,'answerBLength':300,'saccadeCount':10,'regressionRate':0.1,'firstFixationRegion':'A','firstFixationDuration':1200,'fixationDurationVariance':200000,'finalAttentionFocus':{'A':2000,'B':1000}}); print(r['valid'], r['detail_score'])"`
- 创建 prompt 后运行 `cd backend && python -c "from prompts import load_prompt; print('OK')"` 验证加载

## 配置管理

- `backend/config.py` 是后端常量单源
- `frontend/src/config.js` 是前端常量单源
- 两边的 ALPHA、MIN_EYE_TIME 等共享常量必须保持数值一致
- 修改配置后检查两边是否同步

## 实验模式

- `full`: 眼动追踪 + 自动选择（置信度 >= 0.8 自动应用）
- `manual`: 眼动追踪 + 手动选择
- `control`: 无眼动追踪，纯手动选择
- 切换模式时必须重置 EMA 模型（`/api/eye-model/reset`）
- 新增指标必须更新所有模式的处理逻辑

## 提交规则

- 每个改动前基于当前分支创建新分支（用户名 lenitain）
- NEVER 使用 `git add .` 或 `git add -A`
- 只 stage 自己改动的文件
- commit message 格式: `类型(模块): 中文描述`
  - 类型: feat / fix / refactor / docs / config
  - 模块: backend / frontend / prompts / scripts
  - 示例: `feat(backend): 提取 system prompt 到独立文件`
- 提交前运行相关测试

## 性能注意事项

- 眼动数据在 `/api/ask` SSE 流中传递，需注意序列化开销
- `EyeTrackerProcessor._extract_metrics()` 处理大量指标字段，避免不必要字段
- 前端 `EyeTracker.vue` 的 `getAllMetrics()` 应在 `stopTracking()` 时调用一次，而不是流式调用
