# Changelog

所有重要变更均记录在此文件。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### Added
- Persona 系统：双答案人格化（稳健派 / 现代派）
- Persona 动态调整：EMA 收束 + 收敛后随机探索
- Persona 状态按项目名隔离，存于项目根目录
- 眼动处理器单维度 persona_bias 合并
- CI/CD：GitHub Actions + 统一测试运行器
- 代码质量：ruff / biome 配置
- 项目管理：.env.example / CHANGELOG / Issue & PR 模板
- 测试完善：眼动处理器 14 个单元测试

### Changed
- 从双维度（detail/explanation）改为单维度（persona_bias）
- `build_dual_answer_prompts()` 默认使用人格化 prompt
- PromptBuilder 支持注入 Persona 对象
- eye_tracker_processor 新增 persona_bias EMA
