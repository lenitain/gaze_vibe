# Pre-task: Fix experiment_data.jsonl 采集 + 生成合成数据 ✅

## 完成情况

### Step 1: 修改 backend 数据采集 ✅
- [x] 在 `config.py` 添加 `EXPERIMENT_DATA_PATH`
- [x] 在 `app.py` save_preference() 重写实验数据采集逻辑
  - [x] 捕获处理前/处理后 EMA 状态 (`preUpdate` / `postUpdate`)
  - [x] 捕获 Persona 状态快照（深拷贝）
  - [x] 预计算衍生指标（normalizedGazeBias, lengthRatio, totalTime）
  - [x] 捕获前端 emaBias, confidence, decisionTime
  - [x] 写入 experiment_data.jsonl
- [x] 通过 EXPERIMENT_DATA_PATH 统一管理文件路径

### Step 2: 前端字段发送 ✅
- [x] 前端已发送 `emaBias`, `confidence`, `decisionTime`（后端之前忽略，现在已捕获）
- [x] 后端现在正确捕获前端所有字段

### Step 3: 生成合成实验数据 ✅
- [x] 写 `scripts/generate_synthetic_data.py`
- [x] 覆盖 5 个场景 A~E（210 条记录）
- [x] 正确的归一化逻辑：原始 gazeBias 受长度偏移，归一化后消除偏差
- [x] 所有 6 个分析维度正常输出

### 下一步
1. 使用合成数据分析结果优化论文中的占位符（XX.X%）
2. 修改 analyze_experiment.py 支持新的 `preUpdate/postUpdate` 字段
3. 全面优化论文文本质量
