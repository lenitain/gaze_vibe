# GazeVibe 数据分析脚本

基于实验数据和系统日志的自动化分析。

## 用法

```bash
# 一键运行所有分析
./scripts/run.sh

# 或分别运行
cd scripts && uv run python analyze_experiment.py   # 实验数据
cd scripts && uv run python analyze_llm_logs.py      # LLM 调用日志
cd scripts && uv run python analyze_memory.py         # 记忆系统
```

## 输出

图表保存到 `docs/figures/`：

| 文件 | 来源 | 说明 |
|------|------|------|
| `dimension1_eye_effectiveness.svg` | experiment_data | 眼动指标有效性 |
| `dimension2_normalization.svg` | experiment_data | 归一化算法有效性 |
| `dimension4_ema_convergence.svg` | experiment_data | EMA 收敛分析 |
| `dimension5_persona_bias.svg` | experiment_data | Persona 偏差趋势 |
| `dimension6_mode_comparison.svg` | experiment_data | 模式对比分析 |
| `llm_token_trend.svg` | llm_calls_*.jsonl | Token 消耗趋势 |
| `memory_accumulation.svg` | items.jsonl | 记忆积累趋势 |

## 分析维度

### 实验数据 (analyze_experiment.py)
- 维度1: 眼动指标有效性
- 维度2: 归一化算法有效性
- 维度3: 调整分数预测能力（点二列相关）
- 维度4: EMA 收敛分析
- 维度5: Persona 偏差与偏好趋势
- 维度6: 模式对比（full vs manual vs control）

### LLM 日志 (analyze_llm_logs.py)
- Token 消耗统计与趋势
- 延迟分布（平均/中位/P95）
- 成功/重试率
- 调用者分布

### 记忆系统 (analyze_memory.py)
- 记忆类型分布（semantic/episodic/procedural）
- 置信度分析
- 记忆积累趋势
- Persona 偏好信号分布
