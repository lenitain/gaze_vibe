# GazeVibe 对比实验设计方案

## 1. 概述

### 1.1 实验目的
验证基于眼动追踪的AI编程助手个性化推荐系统的有效性。通过充分利用6步骤眼动数据处理链路的所有指标，从多个维度证明系统的可用性和有效性。

### 1.2 研究问题

**主问题**：眼动追踪数据能否有效用于AI编程助手的个性化推荐？

**子问题**：
1. 眼动指标能否准确反映用户的认知状态和偏好？
2. 归一化算法能否消除答案长度差异带来的偏差？
3. 调整分数能否预测用户的最终选择？
4. EMA长期建模能否稳定收敛用户偏好？
5. Prompt调整参数能否有效改变AI回答风格？
6. 不同实验模式（full/manual/control）是否存在显著差异？

### 1.3 实验设计类型
**单组前后测设计** + **自动化测试验证**

- 不需要招募大量被试
- 利用已有56条实验数据进行分析
- 通过API自动化测试验证端到端效果

---

## 2. 数据来源

### 2.1 已有数据

**文件**：`backend/experiment_data.jsonl`

**数据量**：56条记录

**字段说明**：

```json
{
  "experimentMode": "full|manual|control",
  "preference": {
    "finalChoice": "A|B",
    "timeOnA": 12345,
    "timeOnB": 6789,
    "leftToRight": 3,
    "rightToLeft": 2
  },
  "eyeMetrics": {
    // 完整的眼动指标（见2.2节）
  },
  "adjustments": {
    "detail_score": 0.538,
    "explanation_score": 0.431,
    "round_count": 1
  },
  "timestamp": "2026-04-08T16:05:42.706170"
}
```

### 2.2 眼动指标分类

#### 2.2.1 时间分配类指标

| 指标 | 说明 | 来源 |
|------|------|------|
| timeOnA | 在详细解答区域的总注视时长(ms) | 前端累计 |
| timeOnB | 在简洁解答区域的总注视时长(ms) | 前端累计 |
| totalDurationA | WebGazer统计的A区域总时长 | EyeTracker |
| totalDurationB | WebGazer统计的B区域总时长 | EyeTracker |
| decisionLatency | 从问题展示到做出选择的总时间 | EyeTracker |

#### 2.2.2 扫视模式类指标

| 指标 | 说明 | 来源 |
|------|------|------|
| saccadeCount | 区域切换次数 | EyeTracker |
| directionRatio | A→B切换占比 (A→B / 总切换) | EyeTracker |
| regressionRate | 回视率 (B→A / 总切换) | EyeTracker |
| leftToRight | 左→右切换次数 | 前端计数 |
| rightToLeft | 右→左切换次数 | 前端计数 |

#### 2.2.3 认知负荷类指标

| 指标 | 说明 | 来源 |
|------|------|------|
| fixationDurationVariance | 注视时长方差 | EyeTracker |
| meanSwitchInterval | 平均切换间隔(ms) | EyeTracker |
| switchIntervalDecay | 切换间隔衰减比 | EyeTracker |

#### 2.2.4 决策预测类指标

| 指标 | 说明 | 来源 |
|------|------|------|
| gazeBias | 注视偏向 (timeOnA / 总时长) | EyeTracker |
| firstFixationRegion | 首看区域 (A或B) | EyeTracker |
| firstFixationDuration | 首看时长(ms) | EyeTracker |
| lastFixationRegion | 最后注视区域 | EyeTracker |

#### 2.2.5 注意力动力学类指标

| 指标 | 说明 | 来源 |
|------|------|------|
| tau | 信息熵 (注意力分配均匀度) | EyeTracker |
| tauHistory | 信息熵随时间变化序列 | EyeTracker |
| explorationRatio | 探索比例 (前1/3时间扫视占比) | EyeTracker |
| finalAttentionFocus | 最终注意力分布 {A: ms, B: ms} | EyeTracker |
| entropyChangeRate | 熵变化率 | EyeTracker |

### 2.3 处理后指标（6步骤链路）

#### 步骤3：实时调整分数

| 指标 | 计算公式 | 说明 |
|------|---------|------|
| normalized_gaze_bias | timePerCharA / (timePerCharA + timePerCharB) | 按字符数归一化的注视偏向 |
| regression_score | 1 - regressionRate | 回视率得分 |
| switch_score | 1 - switch_freq_normalized | 切换频率得分 |
| final_focus_ratio | finalFocusA / (finalFocusA + finalFocusB) | 最终注意力比例 |
| first_score | 首看区域及时长转换 | 首看得分 |
| variance_adjusted | 注视方差调整 | 方差调整得分 |
| detail_score | 0.5×gaze_bias + 0.3×regression + 0.2×switch | 详细程度得分 |
| explanation_score | 0.4×focus + 0.3×first + 0.3×variance | 解释vs代码得分 |

#### 步骤4：EMA长期模型

| 指标 | 说明 |
|------|------|
| long_term_detail | EMA平滑后的详细程度偏好 |
| long_term_explanation | EMA平滑后的解释vs代码偏好 |

#### 步骤5：最终调整分数

| 指标 | 说明 |
|------|------|
| beta | 实时权重（随轮次递减） |
| final_detail | 最终详细程度得分 |
| final_explanation | 最终解释vs代码得分 |

---

## 3. 验证维度与方法

### 3.1 验证维度 1：眼动指标有效性

**目的**：验证眼动指标能否准确反映用户的认知状态和偏好

#### 3.1.1 时间分配指标验证

**假设**：用户最终选择的区域，应该有更长的注视时间

**方法**：
1. 对每条数据，比较 `finalChoice` 与 `timeOnA/timeOnB`
2. 如果 finalChoice = A，则 timeOnA 应 > timeOnB
3. 计算一致性比例

**指标**：
- 选择-时间一致性率 = 符合假设的数据条数 / 总条数
- 预期：> 70%

**可视化**：
- 散点图：x=timeOnA-timeOnB, y=finalChoice(A=1, B=0)
- 箱线图：按finalChoice分组的timeOnA分布

#### 3.1.2 扫视模式指标验证

**假设**：不同认知状态下，扫视模式应有差异

**分析内容**：
1. saccadeCount与决策时间的关系（高认知负荷→多切换）
2. regressionRate与finalChoice的关系（高回视率→可能选择简洁答案）
3. directionRatio的分布（偏向A还是B）

**指标**：
- 相关系数：saccadeCount vs decisionLatency
- 分组比较：regressionRate在A选择组vsB选择组的差异

**可视化**：
- 相关系数热力图
- 小提琴图：按finalChoice分组的regressionRate分布

#### 3.1.3 认知负荷指标验证

**假设**：高认知负荷对应更高的fixationDurationVariance和更短的meanSwitchInterval

**分析内容**：
1. fixationDurationVariance与saccadeCount的关系
2. meanSwitchInterval与decisionLatency的关系
3. switchIntervalDecay的变化趋势

**指标**：
- 相关系数矩阵
- 因子分析（可选）

**可视化**：
- 相关性热力图
- 散点图矩阵

#### 3.1.4 决策预测指标验证

**假设**：gazeBias能预测finalChoice

**方法**：
1. 以gazeBias为自变量，finalChoice为因变量
2. 做逻辑回归或简单分类
3. 计算预测准确率

**指标**：
- 逻辑回归系数和p值
- 分类准确率
- AUC（可选）

**可视化**：
- 逻辑回归曲线
- ROC曲线（可选）

---

### 3.2 验证维度 2：归一化算法有效性

**目的**：验证按字符数归一化能否消除答案长度差异带来的偏差

#### 3.2.1 问题背景

**问题**：如果答案A很长（如3000字符），答案B很短（如500字符），用户可能因为A内容多而看A更久，但这不代表用户"偏好"A。

**解决方案**：按字符数归一化，计算每字符的注视时间

#### 3.2.2 验证方法

**数据准备**：
- 提取每条数据的 answerALength, answerBLength
- 计算原始 gazeBias 和归一化后的 normalized_gaze_bias

**分析内容**：
1. 比较原始gazeBias vs normalized_gaze_bias
2. 分析长度差异大的case（lenA/lenB > 2 或 < 0.5）
3. 计算归一化前后与finalChoice的一致性变化

**指标**：
- 长度差异大的case数量
- 归一化前一致性率
- 归一化后一致性率
- 一致性提升幅度

**可视化**：
- 对比图：原始gazeBias vs 归一化后（按长度差异分组）
- 差异分布图：归一化前后偏差的变化

---

### 3.3 验证维度 3：调整分数预测能力

**目的**：验证6个子指标能否有效预测用户选择

#### 3.3.1 单指标预测能力

**方法**：对每个子指标，计算与finalChoice的相关性

| 子指标 | 预期相关性 | 验证方法 |
|--------|-----------|---------|
| normalized_gaze_bias | 正相关（偏向A→选A） | 点二列相关 |
| regression_score | 负相关（高回视→可能选B） | 点二列相关 |
| switch_score | 负相关（频繁切换→可能选B） | 点二列相关 |
| final_focus_ratio | 正相关（最终看A→选A） | 点二列相关 |
| first_score | 正相关（首看A→选A） | 点二列相关 |
| variance_adjusted | 弱相关（犹豫程度） | 点二列相关 |

#### 3.3.2 综合预测模型

**方法**：以6个子指标为自变量，finalChoice为因变量，做逻辑回归

**指标**：
- 模型整体显著性（似然比检验）
- 各变量的系数和p值
- 模型预测准确率
- 伪R²（Nagelkerke）

#### 3.3.3 权重验证

**当前权重设计**：
```
detail_score = 0.5×gaze_bias + 0.3×regression + 0.2×switch
explanation_score = 0.4×focus + 0.3×first + 0.3×variance
```

**验证方法**：
- 使用逻辑回归的标准化系数作为"最优权重"
- 比较当前权重 vs 最优权重的预测效果
- 如果差异不大，说明当前权重设计合理

---

### 3.4 验证维度 4：EMA收敛性

**目的**：验证EMA长期建模能否稳定收敛用户偏好

#### 3.4.1 收敛速度分析

**数据**：long_term_detail 和 long_term_explanation 随轮次的变化

**方法**：
1. 对每个用户（如果有多轮数据），绘制学习曲线
2. 计算收敛轮次（连续2轮变化 < 0.05）
3. 分析α=0.3的合理性

**指标**：
- 平均收敛轮次
- 收敛后波动范围
- 不同α值的收敛速度对比

#### 3.4.2 敏感性分析

**方法**：测试不同α值（0.1, 0.2, 0.3, 0.4, 0.5）的收敛效果

**指标**：
- 各α值下的收敛轮次
- 收敛后稳定性
- 对噪声的鲁棒性

**可视化**：
- 多条学习曲线对比
- α值-收敛速度关系图

---

### 3.5 验证维度 5：Prompt调整效果

**目的**：验证调整参数能否有效改变AI回答风格

#### 3.5.1 实验设计

**测试问题**：固定一个编程问题（如"如何实现二叉树遍历？"）

**测试参数组合**：

| 编号 | detail_score | explanation_score | 预期效果 |
|------|-------------|-------------------|---------|
| T1 | 0.5 | 0.5 | 基准（无调整） |
| T2 | 0.8 | 0.5 | 更详细 |
| T3 | 0.2 | 0.5 | 更简洁 |
| T4 | 0.5 | 0.8 | 更多解释 |
| T5 | 0.5 | 0.2 | 更多代码 |

**每组测试**：生成3-5次回答，取平均

#### 3.5.2 评估指标

**定量指标**：

| 指标 | 计算方法 | 预期变化 |
|------|---------|---------|
| 回答字符数 | len(answer) | T2 > T1 > T3 |
| 代码块数量 | count(\`\`\`) | T5 > T4 |
| 解释性词汇密度 | count("因为", "原因", "原理") / 总词数 | T4 > T5 |
| 代码行数 | 代码块中的行数 | T5 > T4 |

**定性指标**（可选）：
- 人工评分（1-5分）：详细程度、解释清晰度
- 人工标注：是否符合参数意图

#### 3.5.3 统计分析

**方法**：
- 单因素方差分析（ANOVA）：不同detail_score组的字符数差异
- 事后检验：Tukey HSD

**指标**：
- F统计量和p值
- 效应量（η²）
- 事后检验的显著性

---

### 3.6 验证维度 6：模式对比分析

**目的**：比较三种实验模式的差异

#### 3.6.1 数据分组

| 模式 | 说明 | 现有数据量 |
|------|------|-----------|
| full | 眼动追踪 + 自动选择 | ~40条 |
| manual | 眼动追踪 + 手动选择 | ~14条 |
| control | 无眼动追踪 | 1条 |

**注意**：control模式数据不足，需要补充采集

#### 3.6.2 对比指标

**行为指标**：

| 指标 | full | manual | control |
|------|------|--------|---------|
| 平均决策时间 | ? | ? | ? |
| A选择比例 | ? | ? | ? |
| B选择比例 | ? | ? | ? |

**眼动指标**（仅full和manual）：

| 指标 | full | manual |
|------|------|--------|
| 平均saccadeCount | ? | ? |
| 平均gazeBias | ? | ? |
| 平均tau | ? | ? |
| 平均regressionRate | ? | ? |

#### 3.6.3 统计分析

**方法**：
- 独立样本t检验：full vs manual的眼动指标差异
- 卡方检验：选择比例的差异

**指标**：
- t值和p值
- 效应量（Cohen's d）
- 置信区间

---

## 4. 实验流程

### 4.1 数据分析流程

```
1. 加载experiment_data.jsonl
2. 数据预处理
   - 清洗无效数据（totalTime < 2000ms）
   - 提取所有指标
   - 按experimentMode分组
3. 验证维度1：眼动指标有效性
   - 时间分配相关性分析
   - 扫视模式分析
   - 认知负荷分析
4. 验证维度2：归一化算法有效性
   - 长度差异case分析
   - 归一化前后对比
5. 验证维度3：调整分数预测能力
   - 单指标相关性
   - 逻辑回归建模
6. 验证维度4：EMA收敛性
   - 学习曲线绘制
   - 敏感性分析
7. 验证维度5：Prompt调整效果
   - API自动化测试
   - 回答风格分析
8. 验证维度6：模式对比
   - 描述性统计
   - 显著性检验
9. 生成可视化图表
10. 撰写分析报告
```

### 4.2 补充数据采集（可选）

如果需要补充control模式数据：

1. 切换到control模式
2. 完成3-5个编程任务
3. 记录用户选择
4. 保存到experiment_data.jsonl

---

## 5. 预期结果

### 5.1 验证维度1预期

- 时间分配与选择一致性率 > 70%
- saccadeCount与decisionLatency正相关（r > 0.3）
- gazeBias对finalChoice有显著预测作用（p < 0.05）

### 5.2 验证维度2预期

- 归一化前后一致性率提升 > 5%
- 长度差异大的case，归一化效果更明显

### 5.3 验证维度3预期

- normalized_gaze_bias和final_focus_ratio预测能力最强
- 综合模型准确率 > 65%

### 5.4 验证维度4预期

- EMA在3-5轮内收敛
- α=0.3的收敛速度适中

### 5.5 验证维度5预期

- T2组字符数显著大于T3组（p < 0.05）
- T5组代码块数量多于T4组

### 5.6 验证维度6预期

- full模式有眼动数据，manual模式也有
- control模式无法使用眼动指标进行个性化

---

## 6. 局限性与讨论

### 6.1 数据量限制

- 现有56条数据，部分指标统计效力有限
- control模式只有1条数据，无法做有意义的对比

### 6.2 外部效度

- 数据来自有限的用户群体
- 编程任务的类型可能影响结果

### 6.3 眼动追踪精度

- WebGazer的预测精度有限（约100-200像素误差）
- 区域划分方式（左/右）可能过于简单

### 6.4 未来工作

- 增加更多被试和任务类型
- 优化眼动追踪算法
- 引入更复杂的个性化策略

---

## 7. 代码实现指南

### 7.1 数据分析脚本

**文件**：`scripts/analyze_experiment.py`

**功能**：
- 加载experiment_data.jsonl
- 计算各验证维度的指标
- 生成可视化图表
- 输出统计检验结果

### 7.2 API测试脚本

**文件**：`scripts/test_prompt_adjustment.py`

**功能**：
- 固定测试问题
- 遍历不同参数组合
- 调用/api/ask接口
- 分析回答风格差异

### 7.3 可视化输出

**目录**：`docs/figures/`

**文件**：
- `correlation_heatmap.png`：相关性热力图
- `gaze_bias_vs_choice.png`：注视偏向vs选择散点图
- `ema_convergence.png`：EMA收敛曲线
- `prompt_adjustment_effect.png`：Prompt调整效果对比
- `mode_comparison.png`：模式对比柱状图

---

## 8. 论文写作建议

### 8.1 第3章结构

```
3 实验验证
  3.1 实验环境与数据
      3.1.1 实验环境配置
      3.1.2 数据采集与预处理
  3.2 眼动指标有效性验证
      3.2.1 时间分配指标分析
      3.2.2 扫视模式指标分析
      3.2.3 认知负荷指标分析
  3.3 个性化算法验证
      3.3.1 归一化算法有效性
      3.3.2 调整分数预测能力
      3.3.3 EMA收敛性分析
  3.4 端到端效果验证
      3.4.1 Prompt调整效果测试
      3.4.2 模式对比分析
  3.5 本章小结
```

### 8.2 关键图表

1. **表3-1**：眼动指标分类汇总表
2. **图3-1**：6步骤数据处理流程图
3. **图3-2**：相关性热力图
4. **表3-2**：各指标与finalChoice的相关系数
5. **图3-3**：EMA收敛曲线
6. **表3-3**：Prompt调整效果对比
7. **图3-4**：模式对比柱状图

### 8.3 统计报告模板

```
【描述性统计】
- 样本量：N = 56
- 平均决策时间：M = xxx ms, SD = xxx ms
- A选择比例：xx%

【相关性分析】
- gazeBias与finalChoice：r = xxx, p = xxx
- saccadeCount与decisionLatency：r = xxx, p = xxx

【回归分析】
- 模型显著性：χ² = xxx, p = xxx
- 预测准确率：xx%
- 伪R² = xxx

【方差分析】
- F统计量：F(x, xx) = xxx, p = xxx
- 效应量：η² = xxx
```

---

## 附录

### A. 指标计算公式汇总

**归一化注视偏向**：
```
timePerCharA = timeOnA / answerALength
timePerCharB = timeOnB / answerBLength
normalized_gaze_bias = timePerCharA / (timePerCharA + timePerCharB)
```

**详细程度得分**：
```
detail_score = 0.5 × normalized_gaze_bias 
             + 0.3 × (1 - regressionRate) 
             + 0.2 × (1 - switch_freq_normalized)
```

**解释vs代码得分**：
```
explanation_score = 0.4 × final_focus_ratio 
                  + 0.3 × first_score 
                  + 0.3 × variance_adjusted
```

**EMA更新**：
```
long_term = α × current_score + (1 - α) × long_term
α = 0.3
```

### B. 数据字段完整列表

参见2.2节和2.3节的详细说明。

### C. 统计检验方法选择指南

| 数据类型 | 比较类型 | 推荐方法 |
|---------|---------|---------|
| 连续变量 | 两组比较 | 独立样本t检验 |
| 连续变量 | 多组比较 | 单因素ANOVA |
| 分类变量 | 独立性检验 | 卡方检验 |
| 两个连续变量 | 相关性 | Pearson相关 |
| 一个分类一个连续 | 预测 | 逻辑回归 |
