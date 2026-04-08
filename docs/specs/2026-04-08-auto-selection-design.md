# 设计方案：风格固定 + 自动选择

## 问题

当前 `/api/ask` 将用户偏好传给 DeepSeek，两个 system prompt 都被修改，导致两份回答风格趋同，丧失差异化价值。

## 方案

AI 的两个 system prompt 永远不变，差异化保证。眼动追踪只用来推断"用户想选哪个"，而非"告诉 AI 怎么改"。

## 推算算法

### 输入信号

| 信号 | 来源 | 权重 |
|---|---|---|
| eyeBias | EyeTracker timeOnA/timeOnB | 0.3（噪声大） |
| explicitChoice | 用户点击选择按钮 | 1.0（强信号） |
| decisionLatency | 回答出现到选择的时间 | 0.1（辅助） |

### 计算流程

```javascript
// 每轮结束后
const totalEye = timeOnA + timeOnB
if (totalEye > 2000) {  // 至少看 2 秒，过滤噪声
  const rawBias = timeOnA / totalEye
  emaBias = α * rawBias + (1 - α) * emaBias
}

// 用户显式选择时（强信号）
if (side === 'A') emaBias = 0.7 * 1.0 + 0.3 * emaBias
else              emaBias = 0.7 * 0.0 + 0.3 * emaBias

// 置信度
confidence = min(1, |emaBias - 0.5| * 4) * min(1, roundCount / 3)
```

### 参数

- α = 0.3（EMA 平滑系数）
- 最短注视时间 = 2s（过滤 WebGazer 噪声）
- 最小轮数 = 3（防止冷启动误判）
- 衰减：连续 2 轮无眼动数据，confidence 每轮衰减 20%

### UI 状态

| confidence | 行为 |
|---|---|
| < 0.5 | 双面板等大，正常选择按钮 |
| 0.5 ~ 0.8 | 双面板等大，显示"推断偏好: {X}" + 确认/否决 |
| ≥ 0.8 | 偏好侧 70%，另一侧 30% 折叠，自动选中，可手动改 |

## 后端改动

- 删除 `/api/ask` 中对 preference 的使用（system prompt 追加逻辑）
- 保留 `/api/preference` 端点（记录实验数据）
- 保留前端传 preference 字段（后端忽略，方便将来恢复）

## 实验设计

三组对比：

| 组 | 眼动 | 自动选择 | 测什么 |
|---|---|---|---|
| A: 眼动+自动 | 开 | 开 | 完整效果 |
| B: 眼动+手动 | 开 | 关 | 推断准确性 |
| C: 无眼动 | 关 | 关 | 基线 |

experimentMode 从 2 值（treatment/control）扩展为 3 值（full/manual/control）。

### 测量指标

1. **推断准确率**：B 组中系统推断与用户最终选择一致的比例
2. **决策时间**：A 组 vs C 组的平均选择时间
3. **置信度收敛速度**：多少轮达到 0.8
4. **推翻率**：A 组中用户推翻自动选择的比例

数据记录在 `experiment_data.jsonl`，每行包含 `emaBias`、`confidence`、`decisionTime`、`override` 字段。
