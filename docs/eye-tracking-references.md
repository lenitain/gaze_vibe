# 眼动追踪理论依据与文献参考

## 概述

本文档整理了眼动指标到回答调整映射的理论依据，涵盖决策心理学、阅读心理学、认知负荷理论和信息搜索行为等领域。

---

## 1. 注视与偏好 (Gaze and Preference)

### 1.1 Gaze Cascade Effect

**核心发现**：人们倾向于注视他们最终会选择的选项，且注视会强化偏好。

**文献**：
- Shimojo, S., Simion, C., Shimojo, E., & Scheier, C. (2003). Gaze bias both reflects and influences preference. *Nature Neuroscience*, 6(12), 1317-1322.
  - DOI: 10.1038/nn1150
  - **关键结论**：注视偏差不仅反映偏好，还会主动影响偏好形成。在决策前 1-2 秒，注视会逐渐偏向最终选择的选项。

- Simion, C., & Shimojo, S. (2007). Interrupting the cascade: Orienting contributes to decision making. *Journal of Vision*, 7(6), 1-12.
  - **关键结论**：人为中断注视可以改变决策结果，证明了注视与偏好的因果关系。

**应用映射**：
```
gazeBias → detail_score (注视偏向A区域 → 偏好详细解答)
finalAttentionFocus → explanation_score (最终注视位置 → 最终偏好)
```

### 1.2 Value-Based Decision Making

**核心发现**：注视时长与选项的主观价值正相关。

**文献**：
- Krajbich, I., Armel, C., & Rangel, A. (2010). Visual fixations and the computation and comparison of value in simple choice. *Nature Neuroscience*, 13(10), 1292-1298.
  - DOI: 10.1038/nn.2635
  - **关键结论**：注意力漂移扩散模型 (Attentional Drift-Diffusion Model)：注视时长影响价值计算，注视越久的选项被选择的概率越高。

- Krajbich, I., & Rangel, A. (2011). Multialternative drift-diffusion model predicts the relationship between visual fixations and choice in value-based decisions. *PNAS*, 108(33), 13852-13857.
  - **关键结论**：扩展模型到多选项场景，验证了注视模式对决策的预测能力。

**应用映射**：
```
timeOnA/timeOnB → gazeBias → detail_score
firstFixationDuration → explanation_score (首看时长反映初始兴趣)
```

---

## 2. 回视与认知负荷 (Regression and Cognitive Load)

### 2.1 Eye Movements in Reading

**核心发现**：回视是阅读理解困难的指标，表示读者在重新处理之前的信息。

**文献**：
- Rayner, K. (1998). Eye movements in reading and information processing: 20 years of research. *Psychological Bulletin*, 124(3), 372-422.
  - DOI: 10.1037/0033-2909.124.3.372
  - **关键结论**：回视率约 10-15% 是正常阅读，超过此比例表示理解困难或文本复杂。

- Rayner, K. (2009). Eye movements and attention in reading, scene perception, and visual search. *Quarterly Journal of Experimental Psychology*, 62(8), 1457-1506.
  - **关键结论**：回视频率与文本难度、读者能力、任务要求相关。

**应用映射**：
```
regressionRate → detail_score (高回视率 → 内容太复杂 → 降低详细度)
```

### 2.2 Regression in Problem Solving

**核心发现**：在复杂任务中，回视表示认知修正过程。

**文献**：
- Henderson, J. M., & Ferreira, F. (2004). The interface of language, vision, and action: Eye movements and the visual world. *Psychology Press*.
  - **关键结论**：回视是认知系统在处理不一致信息时的修正机制。

**应用映射**：
```
regressionRate → 认知负荷指标 → 调整回答复杂度
```

---

## 3. 认知负荷理论 (Cognitive Load Theory)

### 3.1 基础理论

**核心发现**：认知负荷过高会损害学习效果，需要优化信息呈现方式。

**文献**：
- Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. *Cognitive Science*, 12(2), 257-285.
  - DOI: 10.1207/s15516709cog1202_4
  - **关键结论**：提出认知负荷理论，区分内在负荷、外在负荷和相关负荷。

- Paas, F., Renkl, A., & Sweller, J. (2003). Cognitive load theory and instructional design: Recent developments. *Educational Psychologist*, 38(1), 1-4.
  - **关键结论**：认知负荷测量方法包括主观量表、生理指标（瞳孔、心率）和行为指标（眼动）。

**应用映射**：
```
saccadeCount / elapsed_time → switchFrequency → detail_score
fixationDurationVariance → explanation_score (方差大 = 犹豫)
```

### 3.2 Eye Tracking as Cognitive Load Indicator

**核心发现**：眼动指标可以作为认知负荷的客观测量。

**文献**：
- Van Gog, T., & Scheiter, K. (2010). Eye tracking as a tool to study and enhance multimedia learning. *Learning and Instruction*, 20(2), 95-99.
  - **关键结论**：注视次数、注视时长、扫视模式与认知负荷相关。

- Krejtz, K., Duchowski, A., Krejtz, I., Szarkowska, A., & Kopacz, A. (2016). Discerning ambient/focal attention with coefs of variation of fixation durations. *ACM Symposium on Applied Perception*.
  - **关键结论**：注视时长的变异系数 (Coefficient of Variation) 可区分环境注意力和焦点注意力。

**应用映射**：
```
fixationDurationVariance → 认知负荷 → explanation_score
meanSwitchInterval → 信息处理速度 → detail_score
```

---

## 4. 信息搜索行为 (Information Search Behavior)

### 4.1 Information Foraging Theory

**核心发现**：信息搜索遵循最优觅食理论，存在探索-利用权衡。

**文献**：
- Pirolli, P., & Card, S. (1999). Information foraging. *Psychological Review*, 106(4), 643-675.
  - DOI: 10.1037/0033-295X.106.4.643
  - **关键结论**：信息搜索者在探索新信息源和利用已知信息源之间权衡。

- Fu, W. T., & Pirolli, P. (2007). SNIF-ACT: A cognitive model of user navigation on the World Wide Web. *Human-Computer Interaction*, 22(4), 355-412.
  - **关键结论**：搜索行为从探索逐渐转向利用，信息线索价值影响导航决策。

**应用映射**：
```
explorationRatio → 搜索阶段判断 (早期探索多 → 还在寻找 → 保持平衡)
switchIntervalDecay → 收敛过程 (间隔变长 → 趋于稳定 → 维持当前风格)
```

### 4.2 Entropy and Information Gain

**核心发现**：信息熵可以度量搜索的不确定性，熵降低表示收敛。

**文献**：
- Najemnik, J., & Geisler, W. S. (2005). Optimal eye movement strategies in visual search. *Nature*, 434(7031), 387-391.
  - DOI: 10.1038/nature03390
  - **关键结论**：眼动策略最大化信息增益，符合贝叶斯最优搜索。

- Yang, S. C., Lengyel, M., & Wolpert, D. M. (2016). Active sensing in the categorization of visual patterns. *eLife*, 5, e12215.
  - **关键结论**：注视模式与信息增益最大化一致，支持主动感知理论。

**应用映射**：
```
tau (信息熵) → 收敛程度判断
entropyChangeRate → 决策进程
```

---

## 5. 扫视与注意力转换 (Saccade and Attention Shift)

### 5.1 Saccade as Attention Shift

**核心发现**：扫视反映了注意力的重新分配。

**文献**：
- Deubel, H., & Schneider, W. X. (1996). Saccade target selection and object recognition: Evidence for a common attentional mechanism. *Vision Research*, 36(12), 1827-1837.
  - **关键结论**：扫视目标选择与注意力转移共享机制。

- Henderson, J. M. (2003). Human gaze control during real-world scene perception. *Trends in Cognitive Sciences*, 7(11), 498-504.
  - **关键结论**：扫视模式反映了视觉信息的优先级处理。

**应用映射**：
```
directionRatio → 扫视方向偏好 (A→B多 → 对简洁更感兴趣)
saccadeCount → 注意力转换频率 → 认知负荷
```

### 5.2 First Fixation and Decision Priority

**核心发现**：首次注视位置反映认知优先级。

**文献**：
- Theeuwes, J., & Godijn, R. (2001). Attentional and oculomotor capture. *Attention, capture and selection*, 121-149.
  - **关键结论**：首次注视受到自上而下和自下而上因素的共同影响。

- Orquin, J. L., & Loose, S. M. (2013). Attention and choice: A review on eye movements in decision making. *Acta Psychologica*, 144(1), 190-206.
  - **关键结论**：首次注视与决策相关，但预测能力弱于累积注视。

**应用映射**：
```
firstFixationRegion → 初始兴趣指标 (辅助判断)
firstFixationDuration → 初始兴趣强度
```

---

## 6. 综合模型参考

### 6.1 Attentional Drift-Diffusion Model (aDDM)

**核心发现**：将注视纳入决策的数学模型。

**文献**：
- Krajbich, I., Armel, C., & Rangel, A. (2010). Visual fixations and the computation and comparison of value in simple choice. *Nature Neuroscience*, 13(10), 1292-1298.
- Tavares, G., Perona, P., & Rangel, A. (2017). The attentional drift diffusion model of simple perceptual decision-making. *Frontiers in Neuroscience*, 11, 468.

**模型核心**：
```
dV = (V_A - V_B) * (1 + θ * gazing_A) + noise
```
其中 gazing_A 是是否注视A选项，θ 是注意力增益参数。

**应用参考**：
```
我们的 detail_score 计算借鉴了 aDDM 的加权累积思想
```

### 6.2 Gaze-Based Preference Inference

**核心发现**：眼动数据可以推断隐含偏好。

**文献**：
- Glaholt, M. G., & Reingold, E. M. (2009). The time course of gaze behaviour in comparative judgment. *Canadian Journal of Experimental Psychology*, 63(2), 79-88.
  - **关键结论**：总注视时长比首次注视更好地预测偏好。

- Schulte-Mecklenbeck, M., Johnson, J. G., Böckenholt, U., Goldstein, D. G., Russo, J. E., Sullivan, N. J., & Willemsen, M. C. (2017). Process-tracing methods in decision making: On growing up in the 70s. *Current Directions in Psychological Science*, 26(5), 442-450.
  - **关键结论**：过程追踪方法（包括眼动）可以揭示决策的隐含过程。

**应用映射**：
```
gazeBias = timeOnA / (timeOnA + timeOnB) → 偏好强度
多个指标的加权组合 → 综合偏好推断
```

---

## 7. 指标权重依据

基于上述文献，各指标的权重设定依据：

| 指标 | 权重来源 | 置信度 |
|------|----------|--------|
| `gazeBias` 0.5 | Shimojo 2003, Krajbich 2010 | 高 |
| `regressionRate` 0.3 | Rayner 1998 | 高 |
| `switchFrequency` 0.2 | Sweller 1988, Van Gog 2010 | 中 |
| `finalAttentionFocus` 0.4 | Shimojo 2003 | 高 |
| `firstFixationDuration` 0.3 | Glaholt 2009 | 中 |
| `fixationDurationVariance` 0.3 | Krejtz 2016 | 中 |

### 置信度说明
- **高**：有多项研究支持，效应量显著
- **中**：有研究支持，但效应量较小或研究数量有限
- **低**：理论推断，缺乏直接实验证据

---

## 8. 待验证假设

以下映射基于理论推断，需要实验验证：

1. **`switchIntervalDecay` → detail_score**：假设切换间隔变长表示用户趋于稳定，但可能也表示用户在犹豫。

2. **`explorationRatio` → explanation_score**：假设早期探索多表示用户在寻找信息，但可能也表示用户对两种风格都感兴趣。

3. **长期模型的衰减因子 β**：假设用户偏好会随时间收敛，但未找到直接文献支持。

---

## 参考文献列表

1. Shimojo, S., Simion, C., Shimojo, E., & Scheier, C. (2003). Gaze bias both reflects and influences preference. *Nature Neuroscience*, 6(12), 1317-1322.

2. Krajbich, I., Armel, C., & Rangel, A. (2010). Visual fixations and the computation and comparison of value in simple choice. *Nature Neuroscience*, 13(10), 1292-1298.

3. Rayner, K. (1998). Eye movements in reading and information processing: 20 years of research. *Psychological Bulletin*, 124(3), 372-422.

4. Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. *Cognitive Science*, 12(2), 257-285.

5. Pirolli, P., & Card, S. (1999). Information foraging. *Psychological Review*, 106(4), 643-675.

6. Van Gog, T., & Scheiter, K. (2010). Eye tracking as a tool to study and enhance multimedia learning. *Learning and Instruction*, 20(2), 95-99.

7. Henderson, J. M. (2003). Human gaze control during real-world scene perception. *Trends in Cognitive Sciences*, 7(11), 498-504.

8. Orquin, J. L., & Loose, S. M. (2013). Attention and choice: A review on eye movements in decision making. *Acta Psychologica*, 144(1), 190-206.

9. Glaholt, M. G., & Reingold, E. M. (2009). The time course of gaze behaviour in comparative judgment. *Canadian Journal of Experimental Psychology*, 63(2), 79-88.

10. Najemnik, J., & Geisler, W. S. (2005). Optimal eye movement strategies in visual search. *Nature*, 434(7031), 387-391.

---

*文档创建时间: 2024*
*项目: GazeVibe*
