# GazeVibe 实验数据分析脚本

基于实验设计方案，实现6个验证维度的自动化分析。

## 使用方法

```bash
# 一键运行（使用 uv 管理依赖）
./scripts/run.sh
```

## 输出

脚本会在终端输出各维度的分析结果，并在 `docs/figures/` 目录下生成可视化图表：

- `dimension1_eye_effectiveness.png` - 眼动指标有效性验证
- `dimension2_normalization.png` - 归一化算法有效性验证
- `dimension4_ema_convergence.png` - EMA收敛性分析
- `dimension6_mode_comparison.png` - 模式对比分析

## 分析维度

### 维度1：眼动指标有效性验证

- 时间分配指标验证（选择-时间一致性率）
- 扫视模式指标验证（saccadeCount vs decisionLatency）
- 认知负荷指标验证（相关性分析）
- 决策预测指标验证（gazeBias 预测 finalChoice）

### 维度2：归一化算法有效性验证

- 长度差异case分析
- 原始gazeBias vs 归一化后对比
- 归一化前后一致性率变化

### 维度3：调整分数预测能力验证

- 单指标预测能力（点二列相关）
- 调整分数描述性统计

### 维度4：EMA收敛性分析

- 收敛速度分析
- 收敛后波动范围

### 维度6：模式对比分析

- 行为指标对比（决策时间、选择比例）
- 眼动指标对比（full vs manual）
- 统计显著性检验

## 依赖

使用 uv 自动管理依赖，无需手动安装。依赖项：
- pandas
- numpy
- matplotlib
- seaborn
- scipy
