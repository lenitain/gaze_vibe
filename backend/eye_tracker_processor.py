"""
眼动数据处理器

基于注意力相关研究，将眼动指标映射到回答调整维度：
- 详细程度 (detail_score)
- 解释 vs 代码 (explanation_score)

理论依据参考: docs/eye-tracking-references.md
"""

import json
from datetime import datetime
from typing import Optional


class EyeTrackerProcessor:
    """
    眼动数据处理器

    实现：
    1. 实时调整：基于当前轮次眼动数据计算调整分数
    2. 长期建模：使用 EMA 平滑用户偏好
    """

    # EMA 平滑系数
    ALPHA = 0.3
    # 长期模型初始值
    INITIAL_DETAIL = 0.5
    INITIAL_EXPLANATION = 0.5
    # 最小眼动时长阈值 (ms)
    MIN_EYE_TIME = 2000

    def __init__(self):
        # 长期模型
        self.long_term_detail = self.INITIAL_DETAIL
        self.long_term_explanation = self.INITIAL_EXPLANATION
        # 轮次计数
        self.round_count = 0
        # 历史记录
        self.history = []

    def process(self, eye_data: dict) -> dict:
        """
        处理眼动数据，返回调整参数

        Args:
            eye_data: 前端传来的眼动数据

        Returns:
            dict: 包含实时分数、长期分数、最终分数和思考过程
        """
        self.round_count += 1
        timestamp = datetime.now().isoformat()

        # 记录思考过程
        thoughts = []
        thoughts.append(f"=== 第 {self.round_count} 轮眼动数据处理 ===")
        thoughts.append(f"时间: {timestamp}")
        thoughts.append("")

        # 1. 解析原始数据
        thoughts.append("【步骤 1】解析原始眼动数据")
        raw_metrics = self._extract_metrics(eye_data)
        for key, value in raw_metrics.items():
            thoughts.append(
                f"  - {key}: {value:.4f}"
                if isinstance(value, float)
                else f"  - {key}: {value}"
            )
        thoughts.append("")

        # 2. 检查数据有效性
        thoughts.append("【步骤 2】检查数据有效性")
        is_valid = self._validate_data(raw_metrics)
        if not is_valid:
            thoughts.append("  - 眼动数据不足 (总时长 < 2000ms)，跳过本轮调整")
            thoughts.append("  - 维持长期模型不变")
            thoughts.append("")
            return {
                "valid": False,
                "thoughts": thoughts,
                "detail_score": self.long_term_detail,
                "explanation_score": self.long_term_explanation,
            }
        thoughts.append("  - 数据有效 ✓")
        thoughts.append("")

        # 3. 计算实时调整分数
        thoughts.append("【步骤 3】计算实时调整分数")
        current_scores = self._calculate_current_scores(raw_metrics, thoughts)
        thoughts.append("")

        # 4. 更新长期模型
        thoughts.append("【步骤 4】更新长期模型 (EMA)")
        self._update_long_term_model(current_scores, thoughts)
        thoughts.append("")

        # 5. 计算最终分数
        thoughts.append("【步骤 5】计算最终调整分数")
        final_scores = self._calculate_final_scores(thoughts)
        thoughts.append("")

        # 6. 解释调整含义
        thoughts.append("【步骤 6】调整含义解释")
        self._explain_adjustments(final_scores, thoughts)
        thoughts.append("")

        # 保存历史
        record = {
            "round": self.round_count,
            "timestamp": timestamp,
            "raw_metrics": raw_metrics,
            "current_scores": current_scores,
            "long_term": {
                "detail": self.long_term_detail,
                "explanation": self.long_term_explanation,
            },
            "final_scores": final_scores,
        }
        self.history.append(record)

        return {
            "valid": True,
            "thoughts": thoughts,
            **final_scores,
            "current_scores": current_scores,
        }

    def _extract_metrics(self, eye_data: dict) -> dict:
        """提取眼动指标"""
        return {
            "timeOnA": eye_data.get("timeOnA", 0),
            "timeOnB": eye_data.get("timeOnB", 0),
            "leftToRight": eye_data.get("leftToRight", 0),
            "rightToLeft": eye_data.get("rightToLeft", 0),
            # 答案字符数，用于归一化
            "answerALength": eye_data.get("answerALength", 1),
            "answerBLength": eye_data.get("answerBLength", 1),
            # 从 EyeTracker.getAllMetrics() 传来的详细指标
            "gazeBias": eye_data.get("gazeBias", 0.5),
            "regressionRate": eye_data.get("regressionRate", 0),
            "saccadeCount": eye_data.get("saccadeCount", 0),
            "directionRatio": eye_data.get("directionRatio", 0.5),
            "firstFixationRegion": eye_data.get("firstFixationRegion", None),
            "firstFixationDuration": eye_data.get("firstFixationDuration", 0),
            "lastFixationRegion": eye_data.get("lastFixationRegion", None),
            "fixationDurationVariance": eye_data.get("fixationDurationVariance", 0),
            "meanSwitchInterval": eye_data.get("meanSwitchInterval", 0),
            "switchIntervalDecay": eye_data.get("switchIntervalDecay", 0),
            "explorationRatio": eye_data.get("explorationRatio", 0),
            "finalAttentionFocus": eye_data.get(
                "finalAttentionFocus", {"A": 0, "B": 0}
            ),
            "tau": eye_data.get("tau", 0),
            "entropyChangeRate": eye_data.get("entropyChangeRate", 0),
            "decisionLatency": eye_data.get("decisionLatency", 0),
            "totalDurationA": eye_data.get("totalDurationA", 0),
            "totalDurationB": eye_data.get("totalDurationB", 0),
        }

    def _validate_data(self, metrics: dict) -> bool:
        """检查数据是否足够进行分析"""
        total_time = metrics["timeOnA"] + metrics["timeOnB"]
        return total_time >= self.MIN_EYE_TIME

    def _calculate_current_scores(self, metrics: dict, thoughts: list) -> dict:
        """
        计算当前轮次的调整分数

        维度 1: 详细程度 (detail_score)
        - gazeBias (0.5): 偏向详细解答 (按字符数归一化)
        - regressionRate (0.3): 高认知负荷 -> 降低详细度
        - switchFrequency (0.2): 频繁切换 -> 降低详细度

        维度 2: 解释 vs 代码 (explanation_score)
        - finalAttentionFocus (0.4): 最终注视位置
        - firstFixationDuration (0.3): 首看时长
        - fixationDurationVariance (0.3): 注视方差 (犹豫程度)
        """
        # ===== 维度 1: 详细程度 =====
        thoughts.append("  [维度 1] 详细程度 (detail_score)")

        # gazeBias: 越偏向 A (详细) -> 分数越高
        # 按字符数归一化：timePerChar = time / length
        time_on_a = metrics["timeOnA"]
        time_on_b = metrics["timeOnB"]
        len_a = max(1, metrics["answerALength"])  # 避免除零
        len_b = max(1, metrics["answerBLength"])

        time_per_char_a = time_on_a / len_a
        time_per_char_b = time_on_b / len_b
        total_time_per_char = time_per_char_a + time_per_char_b

        if total_time_per_char > 0:
            normalized_gaze_bias = time_per_char_a / total_time_per_char
        else:
            normalized_gaze_bias = 0.5

        thoughts.append(f"    原始数据:")
        thoughts.append(f"      timeOnA = {time_on_a}ms, answerALength = {len_a} 字符")
        thoughts.append(f"      timeOnB = {time_on_b}ms, answerBLength = {len_b} 字符")
        thoughts.append(f"    归一化计算:")
        thoughts.append(
            f"      timePerCharA = {time_on_a} / {len_a} = {time_per_char_a:.4f} ms/char"
        )
        thoughts.append(
            f"      timePerCharB = {time_on_b} / {len_b} = {time_per_char_b:.4f} ms/char"
        )
        thoughts.append(
            f"      normalizedGazeBias = {time_per_char_a:.4f} / ({time_per_char_a:.4f} + {time_per_char_b:.4f}) = {normalized_gaze_bias:.4f}"
        )
        thoughts.append(
            f"      → 解释: 单位内容注视偏向 {'详细解答' if normalized_gaze_bias > 0.5 else '简洁解答'}"
        )
        thoughts.append(
            f"      → 权重贡献: {normalized_gaze_bias:.4f} × 0.5 = {normalized_gaze_bias * 0.5:.4f}"
        )

        # regressionRate: 高认知负荷 -> 降低详细度
        regression = metrics["regressionRate"]
        regression_score = 1 - regression
        thoughts.append(f"    regressionRate = {regression:.4f}")
        thoughts.append(
            f"      → 解释: 回视率{'较高，认知负荷大' if regression > 0.2 else '正常'}"
        )
        thoughts.append(f"      → 转换: 1 - {regression:.4f} = {regression_score:.4f}")
        thoughts.append(
            f"      → 权重贡献: {regression_score:.4f} × 0.3 = {regression_score * 0.3:.4f}"
        )

        # switchFrequency: 频繁切换 -> 降低详细度
        total_time = (metrics["timeOnA"] + metrics["timeOnB"]) / 1000  # 转换为秒
        saccade_count = metrics["saccadeCount"]
        switch_freq = saccade_count / total_time if total_time > 0 else 0
        switch_freq_normalized = min(1.0, switch_freq / 5)  # 归一化，5次/秒为上限
        switch_score = 1 - switch_freq_normalized
        thoughts.append(f"    switchFrequency = {switch_freq:.2f} 次/秒")
        thoughts.append(
            f"      → 解释: 切换频率{'较高' if switch_freq > 2 else '正常'}"
        )
        thoughts.append(
            f"      → 归一化: min(1, {switch_freq:.2f}/5) = {switch_freq_normalized:.4f}"
        )
        thoughts.append(
            f"      → 转换: 1 - {switch_freq_normalized:.4f} = {switch_score:.4f}"
        )
        thoughts.append(
            f"      → 权重贡献: {switch_score:.4f} × 0.2 = {switch_score * 0.2:.4f}"
        )

        # 加权计算
        detail_score = (
            0.5 * normalized_gaze_bias + 0.3 * regression_score + 0.2 * switch_score
        )
        thoughts.append(f"    ────────────────────────────")
        thoughts.append(f"    detail_score = {detail_score:.4f}")
        thoughts.append(
            f"    (0.5 × {normalized_gaze_bias:.4f} + 0.3 × {regression_score:.4f} + 0.2 × {switch_score:.4f})"
        )

        # ===== 维度 2: 解释 vs 代码 =====
        thoughts.append("")
        thoughts.append("  [维度 2] 解释 vs 代码 (explanation_score)")

        # finalAttentionFocus: 最终看哪里
        final_focus = metrics["finalAttentionFocus"]
        total_focus = final_focus["A"] + final_focus["B"]
        if total_focus > 0:
            final_focus_ratio = final_focus["A"] / total_focus
        else:
            final_focus_ratio = 0.5
        thoughts.append(
            f"    finalAttentionFocus = A:{final_focus['A']}ms, B:{final_focus['B']}ms"
        )
        thoughts.append(
            f"      → 解释: 最终注意力偏向 {'详细解释' if final_focus_ratio > 0.5 else '简洁代码'}"
        )
        thoughts.append(f"      → 计算: {final_focus_ratio:.4f}")
        thoughts.append(
            f"      → 权重贡献: {final_focus_ratio:.4f} × 0.4 = {final_focus_ratio * 0.4:.4f}"
        )

        # firstFixationDuration: 首看时长
        first_duration = metrics["firstFixationDuration"]
        first_region = metrics["firstFixationRegion"]
        first_duration_normalized = min(1.0, first_duration / 3000)  # 3秒为上限
        if first_region == "A":
            first_score = first_duration_normalized
        elif first_region == "B":
            first_score = 1 - first_duration_normalized
        else:
            first_score = 0.5
        thoughts.append(
            f"    firstFixation = {first_region}区域, 时长{first_duration}ms"
        )
        thoughts.append(
            f"      → 解释: 首先注视{'详细解答' if first_region == 'A' else '简洁解答'}"
        )
        thoughts.append(
            f"      → 归一化: min(1, {first_duration}/3000) = {first_duration_normalized:.4f}"
        )
        thoughts.append(
            f"      → 转换: {'直接使用' if first_region == 'A' else '1 - '}{first_duration_normalized:.4f} = {first_score:.4f}"
        )
        thoughts.append(
            f"      → 权重贡献: {first_score:.4f} × 0.3 = {first_score * 0.3:.4f}"
        )

        # fixationDurationVariance: 犹豫程度
        variance = metrics["fixationDurationVariance"]
        variance_normalized = min(1.0, variance / 1000000)  # 归一化
        variance_score = 1 - variance_normalized  # 方差大 -> 犹豫 -> 保持平衡 (0.5)
        variance_adjusted = 0.5 + (variance_score - 0.5) * 0.5  # 向 0.5 收敛
        thoughts.append(f"    fixationDurationVariance = {variance:.2f}")
        thoughts.append(
            f"      → 解释: 注视方差{'较大，用户在犹豫' if variance > 500000 else '正常'}"
        )
        thoughts.append(
            f"      → 归一化: min(1, {variance:.2f}/1000000) = {variance_normalized:.4f}"
        )
        thoughts.append(
            f"      → 转换: 0.5 + ((1 - {variance_normalized:.4f}) - 0.5) × 0.5 = {variance_adjusted:.4f}"
        )
        thoughts.append(
            f"      → 权重贡献: {variance_adjusted:.4f} × 0.3 = {variance_adjusted * 0.3:.4f}"
        )

        # 加权计算
        explanation_score = (
            0.4 * final_focus_ratio + 0.3 * first_score + 0.3 * variance_adjusted
        )
        thoughts.append(f"    ────────────────────────────")
        thoughts.append(f"    explanation_score = {explanation_score:.4f}")
        thoughts.append(
            f"    (0.4 × {final_focus_ratio:.4f} + 0.3 × {first_score:.4f} + 0.3 × {variance_adjusted:.4f})"
        )

        return {
            "detail_score": detail_score,
            "explanation_score": explanation_score,
            "components": {
                "gaze_bias": normalized_gaze_bias,
                "regression_score": regression_score,
                "switch_score": switch_score,
                "final_focus_ratio": final_focus_ratio,
                "first_score": first_score,
                "variance_adjusted": variance_adjusted,
            },
        }

    def _update_long_term_model(self, current_scores: dict, thoughts: list):
        """使用 EMA 更新长期模型"""
        alpha = self.ALPHA

        # 更新 detail_score
        old_detail = self.long_term_detail
        self.long_term_detail = (
            alpha * current_scores["detail_score"] + (1 - alpha) * self.long_term_detail
        )
        thoughts.append(f"  detail_score EMA 更新:")
        thoughts.append(
            f"    公式: {alpha} × {current_scores['detail_score']:.4f} + (1 - {alpha}) × {old_detail:.4f}"
        )
        thoughts.append(f"    结果: {self.long_term_detail:.4f}")

        # 更新 explanation_score
        old_explanation = self.long_term_explanation
        self.long_term_explanation = (
            alpha * current_scores["explanation_score"]
            + (1 - alpha) * self.long_term_explanation
        )
        thoughts.append(f"  explanation_score EMA 更新:")
        thoughts.append(
            f"    公式: {alpha} × {current_scores['explanation_score']:.4f} + (1 - {alpha}) × {old_explanation:.4f}"
        )
        thoughts.append(f"    结果: {self.long_term_explanation:.4f}")

    def _calculate_final_scores(self, thoughts: list) -> dict:
        """
        计算最终分数

        使用 β 加权混合实时分数和长期模型
        β 随轮次增加而降低 (越后期越依赖长期模型)
        """
        # β 从 0.7 逐渐降低到 0.3
        beta = max(0.3, 0.7 - (self.round_count - 1) * 0.1)
        beta = min(0.7, beta)

        # 混合当前轮次和长期模型
        # 注意：这里我们只用长期模型，因为当前轮次已经在 EMA 中被考虑了
        # 但为了展示效果，我们使用加权混合
        final_detail = self.long_term_detail
        final_explanation = self.long_term_explanation

        thoughts.append(f"  β (实时权重) = {beta:.2f}")
        thoughts.append(f"  最终分数 = 长期模型 (已通过 EMA 融合实时数据)")
        thoughts.append(f"    detail_score = {final_detail:.4f}")
        thoughts.append(f"    explanation_score = {final_explanation:.4f}")

        return {
            "detail_score": final_detail,
            "explanation_score": final_explanation,
            "beta": beta,
            "round_count": self.round_count,
        }

    def _explain_adjustments(self, final_scores: dict, thoughts: list):
        """解释调整含义"""
        detail = final_scores["detail_score"]
        explanation = final_scores["explanation_score"]

        # 详细程度解释
        if detail > 0.6:
            detail_desc = "更详细 (增加解释、示例、完整代码)"
        elif detail < 0.4:
            detail_desc = "更简洁 (精简解释、只给核心代码)"
        else:
            detail_desc = "保持平衡"

        # 解释 vs 代码解释
        if explanation > 0.6:
            explanation_desc = "偏向解释 (增加原理解释、设计思路)"
        elif explanation < 0.4:
            explanation_desc = "偏向代码 (减少解释、直接给代码)"
        else:
            explanation_desc = "保持平衡"

        thoughts.append(f"  详细程度: {detail:.4f} → {detail_desc}")
        thoughts.append(f"  解释/代码: {explanation:.4f} → {explanation_desc}")

    def get_prompt_adjustments(self) -> dict:
        """
        获取用于调整 system prompt 的参数

        返回值可用于后端调整 AI 回答的风格
        """
        return {
            "detail_score": self.long_term_detail,
            "explanation_score": self.long_term_explanation,
            "round_count": self.round_count,
        }

    def to_dict(self) -> dict:
        """导出状态 (用于持久化)"""
        return {
            "long_term_detail": self.long_term_detail,
            "long_term_explanation": self.long_term_explanation,
            "round_count": self.round_count,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EyeTrackerProcessor":
        """从字典恢复状态"""
        processor = cls()
        processor.long_term_detail = data.get("long_term_detail", cls.INITIAL_DETAIL)
        processor.long_term_explanation = data.get(
            "long_term_explanation", cls.INITIAL_EXPLANATION
        )
        processor.round_count = data.get("round_count", 0)
        processor.history = data.get("history", [])
        return processor


def print_thoughts(thoughts: list):
    """打印思考过程"""
    print("\n" + "=" * 60)
    print("  眼动数据处理 - 思考过程")
    print("=" * 60)
    for thought in thoughts:
        print(thought)
    print("=" * 60 + "\n")
