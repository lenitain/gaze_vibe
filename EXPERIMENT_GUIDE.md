# GazeVibe 实验操作指南

运行 5 个实验场景（A~E）获取真实数据，替换 `graduate_paper.md` 中的合成数据占位值。

---

## 准备工作

### 1. 启动系统

```bash
cd /home/lenitain/.projects/gaze_vibe
./dev.sh
```

前端 → http://localhost:5173
后端 → http://localhost:8000

### 2. 清理旧数据（每次新场景前执行）

```bash
# 删除旧实验数据（新场景自动追加，建议场景间备份）
rm backend/experiment_data.jsonl
```

### 3. 确认数据写入

每轮选择后，检查 `backend/experiment_data.jsonl` 是否有新行追加：

```bash
tail -1 backend/experiment_data.jsonl | python -m json.tool | head -10
```

### 4. 常用检查命令

```bash
# 实验数据行数
wc -l backend/experiment_data.jsonl

# 后端日志（看到眼动处理和 Persona 状态）
# 终端窗口有实时日志输出

# 运行分析脚本
cd scripts && bash run.sh
```

---

## 场景 A：偏好收敛（50 轮，约 45-60 分钟）

**目标**：验证 EMA 模型的收敛性能和反转检测机制。

### 操作步骤

1. 浏览器打开 http://localhost:5173
2. 选择任意项目文件夹（如 gaze_vibe 自身）
3. 确认模式为 **full**（界面右上角显示「眼动+自动」）
4. **前 30 轮**：每次都选 **A（稳健派）**
   - 每题等后端 SSP 流推送完成后阅读
   - 自然阅读，读够后点击 A 侧面板
5. **后 20 轮**（第 31~50 轮）：每次都选 **B（现代派）**
   - 观察系统何时检测到「反转」（日志中 `⚠ 反转累计 3/3 → 解除收敛`）
6. 每轮使用通用编程问题即可，例如：

```python
# 可用问题（随机挑，不需要特定维度）
"Python 里列表推导式和 map/filter 哪个更好？"
"Rust 的 Clone trait 什么时候该用？什么时候避免？"
"JavaScript 的 async/await 和 Promise.then() 哪个可读性更高？"
"怎么设计一个线程安全的缓存？"
"ORM 和手写 SQL 各有什么优缺点？"
```

### 验证要点

- ✅ 前 30 轮：log 中 `detail_score` 是否朝 >0.5 收敛
- ✅ 第 21~30 轮：EMA 是否稳定在 0.6~0.8
- ✅ 第 31~33 轮：出现 `反转累计 1/3 → 2/3 → 3/3`
- ✅ 第 33+ 轮：`解除收敛` 后重新朝 B 侧收敛

---

## 场景 B：模式对比（60 轮，约 50-70 分钟）

**目标**：比较 full / manual / control 三种模式下的行为差异。

### 操作步骤

1. 准备 **10 个通用编程问题**，记录在表格中
2. 分 3 轮运行，每轮 20 次：

| 轮次 | 模式 | 切换方法 | 说明 |
|------|------|---------|------|
| 第 1~20 | **full** | 默认 | 眼动+推断提示 |
| 第 21~40 | **manual** | 点击右上角切换到「眼动+手动」 | 眼动追踪开启，不显示推断提示 |
| 第 41~60 | **control** | 点击切换到「对照组」 | 彻底关闭眼动追踪 |

3. 每轮 **用同一套 10 个问题循环两次**（确保每个问题在每个模式下出现 2 次）
4. 每次选择后，立即记录当前模式、选择了 A 还是 B、大概耗时

### 验证要点

- ✅ full 模式平均决策时间是否最短
- ✅ control 模式的 A/B 选择比例是否接近 50%（无偏好偏向）
- ✅ full 与 manual 的眼动指标（saccadeCount 等）无显著差异

---

## 场景 C：归一化效果（30 轮，约 25-35 分钟）

**目标**：验证答案长度差异大时归一化算法的效果。

### 操作步骤

1. **前 15 轮**：提问时在 prompt 末尾追加 `[请给出非常详细的解答]`
   - 这将让稳健派（A）回答变得极长
   - 现代派（B）回答保持简洁
   - 预期 `lengthRatio = lenA/lenB` 达到 3~5
2. **后 15 轮**：提问时不加特殊指令
   - 预期 `lengthRatio` 在 1~2.5 之间
3. 每轮按自己真实偏好选择 A 或 B

### 验证要点

- ✅ 前 15 轮 `lengthRatio` 是否显著 > 后 15 轮
- ✅ 归一化后的一致性率是否高于原始（特别是前 15 轮）
- ✅ 原始 gazeBias 是否系统性偏大（>0.6），归一化后回归 0.5 附近

### 记录模板

每轮在后端日志中查看：

```bash
# 从日志中提取长度比
grep "answerALength" backend/experiment_data.jsonl | tail -1
```

也可运行分析脚本查看分组统计：

```bash
cd scripts && uv run python analyze_experiment.py | grep "归一化"
```

---

## 场景 D：偏好反转（40 轮，约 35-50 分钟）

**目标**：精确标定反转检测阈值。

### 操作步骤

1. 确保模式为 **full**
2. **前 20 轮**：每次都选 **A（稳健派）**
   - 让 EMA 模型稳定收敛，Persona 维度固化
3. **第 21 轮起**：每次都选 **B（现代派）**
   - 目标是触发反转检测（UNCONVERGE_THRESHOLD=3）
4. 记录关键事件：

| 轮次 | 事件 | 日志关键字 |
|------|------|-----------|
| 21 | 首次选 B | 检查是否有 `反转累计 1/3` |
| 22 | 第二次选 B | `反转累计 2/3` |
| 23 | 第三次选 B | `⚠ 反转累计 3/3 → 解除收敛` |
| 24+ | 重新收敛 | 观察 gap 变化 |

### 验证要点

- ✅ 反转检测延迟 = 3 轮
- ✅ 解除收敛时 gap 拉开到 1.0（UNCONVERGE_DELTA）
- ✅ 5-8 轮后重新在新方向上收敛

---

## 场景 E：维度分类（30 轮，约 30-40 分钟）

**目标**：评估 LLM 和关键词维度分类的准确率。

### 操作步骤

1. 确保模式为 **full**
2. 按论文附录中的 **30 个测试问题** 顺序提问（每个维度 3 题）
3. 每轮提问后，立即查看后端日志中的维度分类结果

### 数据记录

打开第二个终端，实时捕获分类结果：

```bash
# 创建分类日志文件
echo "dim,question_id,llm_result,keyword_result,llm_hit,keyword_hit" > backend/classification_log.csv
```

每轮提问后，从终端日志中找到类似输出：

```
LLM 维度分类: ['error_handling', 'correctness_strategy']
  错误处理: 用户问题中提到了'panic'和'Result'...
```

记录到 CSV：

```bash
# 手动追加一行到 CSV
echo "error_handling,1,"error_handling,correctness_strategy","error_handling",✓,✓" >> backend/classification_log.csv
```

记录格式（5 列）：

| 维度名 | 问题编号 | LLM结果列表 | 关键词结果列表 | LLM命中 | 关键词命中 |
|--------|---------|------------|---------------|---------|-----------|
| ecosystem_maturity | 1 | [ecosystem_maturity] | [ecosystem_maturity] | ✓ | ✓ |
| ecosystem_maturity | 2 | [ecosystem_maturity] | [] | ✓ | ✗ |
| error_handling | 1 | [error_handling, correctness] | [] | ✓ | ✗ |

### 验证要点

- ✅ LLM 分类总体准确率 > 80%
- ✅ 关键词分类在语义模糊时准确率低于 LLM
- ✅ 混淆矩阵显示：相邻维度（如错误处理/正确性策略）最容易混淆

---

## 数据导出与分析

### 全部场景完成后

```bash
cd scripts && bash run.sh
```

输出文件：

| 文件 | 内容 |
|------|------|
| `docs/figures/dimension1_eye_effectiveness.svg` | 眼动指标有效性 |
| `docs/figures/dimension2_normalization.svg` | 归一化算法 |
| `docs/figures/dimension3_prediction_power.svg` | 调整分数预测力 |
| `docs/figures/dimension4_ema_convergence.svg` | EMA 收敛曲线 |
| `docs/figures/dimension5_persona_bias.svg` | Persona 偏差趋势 |
| `docs/figures/dimension6_mode_comparison.svg` | 模式对比 |
| `docs/figures/reversal_analysis.svg` | 反转分析 |
| `docs/figures/classification_accuracy.svg` | 维度分类（需 CSV） |

### 更新论文

用真实数据替换 `graduate_paper.md` 中对应表格的数值：

1. 从 `bash run.sh` 的输出中提取：
   - 一致性率 → 表 5.2 (gazeBias)
   - 归一化提升 → 表 5.8
   - 收敛轮次 → 表 5.12
   - 反转检测 → 表 5.13
   - 模式对比 → 表 5.14, 5.15
   - 描述性统计 → 附录 B.1
   - ANOVA → 附录 B.2
2. 更新摘要中的关键数值
3. 更新 6.2 研究创新点中的数字

---

## 常见问题

### Q: 眼动追踪没反应？
- 检查浏览器是否允许摄像头权限
- 刷新页面重新校准 WebGazer（点击屏幕上的校准点）
- 控制台看 `console.log` 是否有 WebGazer 错误

### Q: experiment_data.jsonl 为空？
- 确保先选择答案（点 A 或 B），不选不会触发 `/api/preference`
- 检查后端终端是否有 `保存实验数据失败` 的错误输出
- 确认 `backend/` 目录可写

### Q: 某场景中断了怎么办？
- 记录已中断的轮次编号
- 删除 `experiment_data.jsonl` 重新开始该场景
- 或追加剩余轮次（分析脚本会自动过滤无效记录）

### Q: 如何检查数据质量？
```bash
# 总记录数
wc -l backend/experiment_data.jsonl

# 各场景记录数
grep -o '"scene_id":"[A-E]"' backend/experiment_data.jsonl | sort | uniq -c

# 有效眼动数据占比
python -c "
import json
valid = sum(1 for l in open('backend/experiment_data.jsonl') if json.loads(l).get('eyeMetrics'))
total = sum(1 for _ in open('backend/experiment_data.jsonl'))
print(f'眼动数据覆盖率: {valid}/{total} = {valid/total*100:.0f}%')
"
```
