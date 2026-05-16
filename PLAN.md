# GazeVibe 工程优化全景图

## 核心改造（PROGRESS.md）

AI 工程架构升级 — 从裸 API 调用升级为有完整架构的 AI 应用。

| Phase | 内容 | 优先级 |
|-------|------|--------|
| 1 | LLM 客户端层（retry/streaming/token tracking） | P0 |
| 2 | 动态 Prompt 组装（Prompt Builder） | P0 |
| 3 | 结构化输出（Function Calling） | P1 |
| 4 | 代码应用 Agent（Tool Calling） | P2 |
| 5 | 流式事件协议 | P3 |
| 6 | 上下文管理与日志 | P3 |

## 边缘优化（边角料）

基础设施类，非 AI 工程核心但提升开发体验。

### A. CI/CD

| 任务 | 文件 | 说明 |
|------|------|------|
| GitHub Actions CI | `.github/workflows/ci.yml` | push/PR 自动 lint + test |
| 统一测试运行器 | `test.sh` | 环境隔离，参考 pi-main `test.sh` |

### B. 代码质量

| 任务 | 文件 | 说明 |
|------|------|------|
| Python lint 配置 | `backend/pyproject.toml` | ruff 配置 |
| 前端 lint 完善 | `frontend/biome.json` | biome 规则细化 |
| 提交前检查 | `.husky/pre-commit` | 自动 lint + test |

### C. 项目管理

| 任务 | 文件 | 说明 |
|------|------|------|
| 环境变量模板 | `backend/.env.example` | 从 `.env` 脱敏复制 |
| 变更日志 | `CHANGELOG.md` | 结构化记录 |
| Issue 模板 | `.github/ISSUE_TEMPLATE/` | bug / feature 模板 |
| PR 模板 | `.github/PULL_REQUEST_TEMPLATE.md` | PR 描述模板 |

### D. 测试完善

| 任务 | 文件 | 说明 |
|------|------|------|
| pytest 配置 | `backend/pytest.ini` | 覆盖率等 |
| 眼动处理器测试 | `backend/test_eye_tracker.py` | 核心单元测试 |
| 现有测试完善 | `backend/test_split.py` | 修复已知问题 |

### E. 工程美化

| 任务 | 文件 | 说明 |
|------|------|------|
| `requirements.txt` → `pyproject.toml` | `backend/pyproject.toml` | 现代化依赖声明 |
| `.gitignore` 完善 | `.gitignore` | 覆盖更多场景 |
| 脚本目录优化 | `scripts/` | 分类管理 |

---

## 关系说明

核心改造（PROGRESS.md）和边缘优化（本文件）互不依赖，可并行推进。
优先做核心改造，边缘优化穿插进行。
