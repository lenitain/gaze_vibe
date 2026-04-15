#!/usr/bin/env python3
"""
GazeVibe 实验数据分析脚本

基于实验设计方案，实现6个验证维度的分析：
1. 眼动指标有效性验证
2. 归一化算法有效性验证
3. 调整分数预测能力验证
4. EMA收敛性验证
5. Prompt调整效果验证（需API测试）
6. 模式对比分析
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from scipy.stats import pointbiserialr, ttest_ind
import warnings

warnings.filterwarnings("ignore")

# 设置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


class ExperimentAnalyzer:
    """实验数据分析器"""

    def __init__(self, data_path: str):
        self.data_path = data_path
        self.df = None
        # 获取项目根目录
        project_root = Path(data_path).parent.parent
        self.figures_dir = project_root / "docs" / "figures"
        self.figures_dir.mkdir(parents=True, exist_ok=True)

    def load_data(self) -> pd.DataFrame:
        """加载并预处理实验数据"""
        print("=" * 60)
        print("  加载实验数据")
        print("=" * 60)

        records = []
        with open(self.data_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        print(f"  跳过无效行: {e}")

        print(f"  加载 {len(records)} 条原始记录")

        self.df = pd.DataFrame(records)
        self._preprocess_data()

        print(f"  有效数据: {len(self.df)} 条")
        print()

        return self.df

    def _preprocess_data(self):
        """数据预处理"""
        # 清洗无效数据
        self.df["totalTime"] = self.df["preference"].apply(
            lambda p: p.get("timeOnA", 0) + p.get("timeOnB", 0)
        )
        self.df = self.df[self.df["totalTime"] >= 2000].copy()

        # 提取preference字段
        self.df["finalChoice"] = self.df["preference"].apply(
            lambda p: p.get("finalChoice", None)
        )
        self.df["timeOnA"] = self.df["preference"].apply(lambda p: p.get("timeOnA", 0))
        self.df["timeOnB"] = self.df["preference"].apply(lambda p: p.get("timeOnB", 0))
        self.df["leftToRight"] = self.df["preference"].apply(
            lambda p: p.get("leftToRight", 0)
        )
        self.df["rightToLeft"] = self.df["preference"].apply(
            lambda p: p.get("rightToLeft", 0)
        )

        # 提取eyeMetrics
        self.df["hasEyeMetrics"] = self.df["eyeMetrics"].notna()

        def safe_get(metrics, key, default=None):
            if metrics is None or not isinstance(metrics, dict):
                return default
            return metrics.get(key, default)

        eye_columns = [
            "tau",
            "gazeBias",
            "regressionRate",
            "saccadeCount",
            "directionRatio",
            "firstFixationRegion",
            "firstFixationDuration",
            "lastFixationRegion",
            "fixationDurationVariance",
            "meanSwitchInterval",
            "switchIntervalDecay",
            "decisionLatency",
            "explorationRatio",
            "entropyChangeRate",
            "totalDurationA",
            "totalDurationB",
        ]

        for col in eye_columns:
            self.df[col] = self.df["eyeMetrics"].apply(lambda x: safe_get(x, col))

        self.df["finalFocusA"] = self.df["eyeMetrics"].apply(
            lambda x: (
                safe_get(x, "finalAttentionFocus", {}).get("A", 0)
                if isinstance(x, dict)
                else 0
            )
        )
        self.df["finalFocusB"] = self.df["eyeMetrics"].apply(
            lambda x: (
                safe_get(x, "finalAttentionFocus", {}).get("B", 0)
                if isinstance(x, dict)
                else 0
            )
        )

        # 提取adjustments
        self.df["detail_score"] = self.df["adjustments"].apply(
            lambda x: x.get("detail_score", 0.5) if isinstance(x, dict) else 0.5
        )
        self.df["explanation_score"] = self.df["adjustments"].apply(
            lambda x: x.get("explanation_score", 0.5) if isinstance(x, dict) else 0.5
        )
        self.df["round_count"] = self.df["adjustments"].apply(
            lambda x: x.get("round_count", 0) if isinstance(x, dict) else 0
        )

        # answer长度
        self.df["answerALength"] = self.df["answerALength"].fillna(0)
        self.df["answerBLength"] = self.df["answerBLength"].fillna(0)

        self._calculate_derived_metrics()

    def _calculate_derived_metrics(self):
        """计算衍生指标"""

        def check_consistency(row):
            if pd.isna(row["finalChoice"]):
                return None
            if row["timeOnA"] > row["timeOnB"]:
                return row["finalChoice"] == "A"
            elif row["timeOnB"] > row["timeOnA"]:
                return row["finalChoice"] == "B"
            return None

        self.df["choiceTimeConsistent"] = self.df.apply(check_consistency, axis=1)

        def calc_normalized_gaze_bias(row):
            if pd.isna(row.get("gazeBias")):
                return None
            time_a = row["timeOnA"]
            time_b = row["timeOnB"]
            len_a = max(1, row.get("answerALength", 1))
            len_b = max(1, row.get("answerBLength", 1))
            time_per_char_a = time_a / len_a
            time_per_char_b = time_b / len_b
            total = time_per_char_a + time_per_char_b
            return time_per_char_a / total if total > 0 else 0.5

        self.df["normalizedGazeBias"] = self.df.apply(calc_normalized_gaze_bias, axis=1)

        self.df["switchFrequency"] = self.df.apply(
            lambda row: (
                row["saccadeCount"] / (row["totalTime"] / 1000)
                if row["totalTime"] > 0 and not pd.isna(row["saccadeCount"])
                else 0
            ),
            axis=1,
        )

    def analyze_dimension1_eye_effectiveness(self):
        """验证维度1：眼动指标有效性"""
        print("=" * 60)
        print("  验证维度1：眼动指标有效性")
        print("=" * 60)

        eye_df = self.df[self.df["hasEyeMetrics"]].copy()
        if len(eye_df) == 0:
            print("  警告: 无眼动指标数据")
            return

        print(f"  有眼动指标的数据: {len(eye_df)} 条")
        print()

        # 1.1 时间分配指标
        print("  1.1 时间分配指标验证")
        print("  " + "-" * 40)
        consistency_rate = eye_df["choiceTimeConsistent"].mean()
        print(f"  选择-时间一致性率: {consistency_rate:.2%}")
        print(
            f"  预期: > 70%，实际: {'✓ 达标' if consistency_rate > 0.7 else '✗ 未达标'}"
        )
        print()

        # 1.2 扫视模式指标
        print("  1.2 扫视模式指标验证")
        print("  " + "-" * 40)
        valid_data = eye_df.dropna(subset=["saccadeCount", "decisionLatency"])
        if len(valid_data) > 2:
            corr, p_value = stats.pearsonr(
                valid_data["saccadeCount"], valid_data["decisionLatency"]
            )
            print(
                f"  saccadeCount vs decisionLatency: r = {corr:.3f}, p = {p_value:.4f}"
            )
            print(f"  预期: r > 0.3，实际: {'✓ 达标' if corr > 0.3 else '✗ 未达标'}")

        a_group = eye_df[eye_df["finalChoice"] == "A"]["regressionRate"].dropna()
        b_group = eye_df[eye_df["finalChoice"] == "B"]["regressionRate"].dropna()
        if len(a_group) > 0 and len(b_group) > 0:
            print(f"  A选择组 regressionRate: {a_group.mean():.3f}")
            print(f"  B选择组 regressionRate: {b_group.mean():.3f}")
        print()

        # 1.3 认知负荷指标
        print("  1.3 认知负荷指标验证")
        print("  " + "-" * 40)
        corr_cols = [
            "saccadeCount",
            "fixationDurationVariance",
            "meanSwitchInterval",
            "decisionLatency",
        ]
        corr_df = eye_df[corr_cols].dropna()
        if len(corr_df) > 2:
            corr_matrix = corr_df.corr()
            print("  相关性矩阵:")
            print(corr_matrix.to_string())
        print()

        # 1.4 决策预测指标
        print("  1.4 决策预测指标验证")
        print("  " + "-" * 40)
        valid_gaze = eye_df.dropna(subset=["gazeBias", "finalChoice"])
        if len(valid_gaze) > 2:
            valid_gaze = valid_gaze.copy()
            valid_gaze["choice_numeric"] = (valid_gaze["finalChoice"] == "A").astype(
                int
            )
            corr, p_val = pointbiserialr(
                valid_gaze["gazeBias"], valid_gaze["choice_numeric"]
            )
            print(f"  gazeBias 与 finalChoice: r = {corr:.3f}, p = {p_val:.4f}")
            print(f"  预期: p < 0.05，实际: {'✓ 显著' if p_val < 0.05 else '✗ 不显著'}")
        print()

        self._plot_dimension1(eye_df)

    def _plot_dimension1(self, eye_df):
        """维度1可视化"""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle("维度1：眼动指标有效性验证", fontsize=14)

        ax = axes[0, 0]
        valid = eye_df.dropna(subset=["finalChoice"])
        if len(valid) > 0:
            valid = valid.copy()
            valid["choice_numeric"] = (valid["finalChoice"] == "A").astype(int)
            valid["time_diff"] = valid["timeOnA"] - valid["timeOnB"]
            ax.scatter(valid["time_diff"], valid["choice_numeric"], alpha=0.6)
            ax.set_xlabel("timeOnA - timeOnB (ms)")
            ax.set_ylabel("finalChoice (A=1, B=0)")
            ax.set_title("时间差异 vs 选择")
            ax.axhline(y=0.5, color="r", linestyle="--", alpha=0.5)

        ax = axes[0, 1]
        a_data = eye_df[eye_df["finalChoice"] == "A"]["timeOnA"].dropna()
        b_data = eye_df[eye_df["finalChoice"] == "B"]["timeOnA"].dropna()
        if len(a_data) > 0 and len(b_data) > 0:
            ax.boxplot([a_data, b_data], labels=["选择A", "选择B"])
            ax.set_ylabel("timeOnA (ms)")
            ax.set_title("timeOnA 分布（按选择分组）")

        ax = axes[1, 0]
        corr_cols = ["saccadeCount", "gazeBias", "regressionRate", "decisionLatency"]
        corr_data = eye_df[corr_cols].dropna()
        if len(corr_data) > 2:
            corr_matrix = corr_data.corr()
            sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", center=0, ax=ax)
            ax.set_title("眼动指标相关性热力图")

        ax = axes[1, 1]
        reg_a = eye_df[eye_df["finalChoice"] == "A"]["regressionRate"].dropna()
        reg_b = eye_df[eye_df["finalChoice"] == "B"]["regressionRate"].dropna()
        if len(reg_a) > 0 and len(reg_b) > 0:
            ax.violinplot([reg_a, reg_b], positions=[1, 2])
            ax.set_xticks([1, 2])
            ax.set_xticklabels(["选择A", "选择B"])
            ax.set_ylabel("regressionRate")
            ax.set_title("回视率分布（按选择分组）")

        plt.tight_layout()
        plt.savefig(self.figures_dir / "dimension1_eye_effectiveness.png", dpi=150)
        plt.close()
        print(f"  图表已保存: {self.figures_dir / 'dimension1_eye_effectiveness.png'}")
        print()

    def analyze_dimension2_normalization(self):
        """验证维度2：归一化算法有效性"""
        print("=" * 60)
        print("  验证维度2：归一化算法有效性")
        print("=" * 60)

        valid_df = self.df[
            self.df["hasEyeMetrics"]
            & (self.df["answerALength"] > 0)
            & (self.df["answerBLength"] > 0)
        ].copy()

        if len(valid_df) == 0:
            print("  警告: 无有效数据")
            return

        print(f"  有效数据: {len(valid_df)} 条")
        print()

        valid_df["lengthRatio"] = valid_df["answerALength"] / valid_df["answerBLength"]
        valid_df["lengthDiff"] = abs(valid_df["lengthRatio"] - 1)

        large_diff = valid_df[
            (valid_df["lengthRatio"] > 2) | (valid_df["lengthRatio"] < 0.5)
        ]
        print(f"  长度差异大的case: {len(large_diff)} 条")
        print()

        print("  原始 gazeBias vs 归一化后:")
        print(f"  原始 gazeBias 均值: {valid_df['gazeBias'].mean():.3f}")
        print(f"  归一化后均值: {valid_df['normalizedGazeBias'].mean():.3f}")
        print()

        def calc_consistency(df, bias_col):
            consistent = 0
            total = 0
            for _, row in df.iterrows():
                if pd.isna(row[bias_col]) or pd.isna(row["finalChoice"]):
                    continue
                total += 1
                if row[bias_col] > 0.5 and row["finalChoice"] == "A":
                    consistent += 1
                elif row[bias_col] < 0.5 and row["finalChoice"] == "B":
                    consistent += 1
            return consistent / total if total > 0 else 0

        orig = calc_consistency(valid_df, "gazeBias")
        norm = calc_consistency(valid_df, "normalizedGazeBias")
        print(f"  原始一致性率: {orig:.2%}")
        print(f"  归一化后一致性率: {norm:.2%}")
        print(f"  一致性提升: {norm - orig:.2%}")
        print()

        if len(large_diff) > 0:
            orig_diff = calc_consistency(large_diff, "gazeBias")
            norm_diff = calc_consistency(large_diff, "normalizedGazeBias")
            print("  长度差异大的case:")
            print(f"    原始一致性率: {orig_diff:.2%}")
            print(f"    归一化后一致性率: {norm_diff:.2%}")
            print(f"    提升: {norm_diff - orig_diff:.2%}")
        print()

        self._plot_dimension2(valid_df)

    def _plot_dimension2(self, valid_df):
        """维度2可视化"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle("维度2：归一化算法有效性验证", fontsize=14)

        ax = axes[0]
        if len(valid_df) > 0:
            valid_df["diff_group"] = pd.cut(
                valid_df["lengthDiff"],
                bins=[0, 0.5, 1, float("inf")],
                labels=["小", "中", "大"],
            )
            groups, labels = [], []
            for name in ["小", "中", "大"]:
                g = valid_df[valid_df["diff_group"] == name]
                if len(g) > 0:
                    groups.append(
                        [g["gazeBias"].mean(), g["normalizedGazeBias"].mean()]
                    )
                    labels.append(name)
            if groups:
                x = np.arange(len(groups))
                width = 0.35
                ax.bar(x - width / 2, [g[0] for g in groups], width, label="原始")
                ax.bar(x + width / 2, [g[1] for g in groups], width, label="归一化")
                ax.set_xticks(x)
                ax.set_xticklabels(labels)
                ax.set_xlabel("长度差异程度")
                ax.set_ylabel("gazeBias")
                ax.set_title("原始 vs 归一化（按长度差异分组）")
                ax.legend()

        ax = axes[1]
        if len(valid_df) > 0:
            diff = valid_df["gazeBias"] - valid_df["normalizedGazeBias"]
            ax.hist(diff.dropna(), bins=20, edgecolor="black")
            ax.axvline(x=0, color="r", linestyle="--")
            ax.set_xlabel("原始 - 归一化")
            ax.set_ylabel("频数")
            ax.set_title("归一化前后偏差分布")

        plt.tight_layout()
        plt.savefig(self.figures_dir / "dimension2_normalization.png", dpi=150)
        plt.close()
        print(f"  图表已保存: {self.figures_dir / 'dimension2_normalization.png'}")
        print()

    def analyze_dimension3_prediction(self):
        """验证维度3：调整分数预测能力"""
        print("=" * 60)
        print("  验证维度3：调整分数预测能力")
        print("=" * 60)

        valid_df = self.df[self.df["round_count"] > 0].copy()
        if len(valid_df) == 0:
            print("  警告: 无调整分数数据")
            return

        print(f"  有效数据: {len(valid_df)} 条")
        print()

        print("  3.1 单指标预测能力")
        print("  " + "-" * 40)

        valid_df["choice_numeric"] = (valid_df["finalChoice"] == "A").astype(int)
        for col, name in [
            ("detail_score", "详细程度得分"),
            ("explanation_score", "解释vs代码得分"),
        ]:
            data = valid_df.dropna(subset=[col, "choice_numeric"])
            if len(data) > 2:
                corr, p_val = pointbiserialr(data[col], data["choice_numeric"])
                print(f"  {name}: r = {corr:.3f}, p = {p_val:.4f}")
                print(f"    {'✓ 显著' if p_val < 0.05 else '✗ 不显著'}")
        print()

        print("  3.2 调整分数描述性统计")
        print("  " + "-" * 40)
        print(
            f"  detail_score: M = {valid_df['detail_score'].mean():.3f}, SD = {valid_df['detail_score'].std():.3f}"
        )
        print(
            f"  explanation_score: M = {valid_df['explanation_score'].mean():.3f}, SD = {valid_df['explanation_score'].std():.3f}"
        )
        print()

    def analyze_dimension4_ema_convergence(self):
        """验证维度4：EMA收敛性"""
        print("=" * 60)
        print("  验证维度4：EMA收敛性")
        print("=" * 60)

        valid_df = self.df[self.df["round_count"] > 0].copy()
        if len(valid_df) == 0:
            print("  警告: 无EMA数据")
            return

        print(f"  有效数据: {len(valid_df)} 条")
        print()

        valid_df = valid_df.sort_values("timestamp")

        print("  4.1 EMA收敛性分析")
        print("  " + "-" * 40)

        detail_scores = valid_df["detail_score"].values
        explanation_scores = valid_df["explanation_score"].values

        if len(detail_scores) > 1:
            detail_changes = np.abs(np.diff(detail_scores))
            explanation_changes = np.abs(np.diff(explanation_scores))

            detail_converged = np.where(detail_changes < 0.05)[0]
            explanation_converged = np.where(explanation_changes < 0.05)[0]

            if len(detail_converged) > 0:
                print(f"  detail_score 收敛轮次: 第 {detail_converged[0] + 2} 轮")
            else:
                print("  detail_score: 未收敛")

            if len(explanation_converged) > 0:
                print(
                    f"  explanation_score 收敛轮次: 第 {explanation_converged[0] + 2} 轮"
                )
            else:
                print("  explanation_score: 未收敛")

            if len(detail_converged) > 0:
                post = detail_scores[detail_converged[0] :]
                print(
                    f"  detail_score 收敛后波动: [{post.min():.3f}, {post.max():.3f}]"
                )
        print()

        self._plot_dimension4(valid_df)

    def _plot_dimension4(self, valid_df):
        """维度4可视化"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle("维度4：EMA收敛性分析", fontsize=14)

        ax = axes[0]
        if len(valid_df) > 0:
            ax.plot(valid_df["detail_score"].values, marker="o", label="detail_score")
            ax.axhline(y=0.5, color="r", linestyle="--", alpha=0.5, label="基准线")
            ax.set_xlabel("轮次")
            ax.set_ylabel("score")
            ax.set_title("detail_score 学习曲线")
            ax.legend()

        ax = axes[1]
        if len(valid_df) > 0:
            ax.plot(
                valid_df["explanation_score"].values,
                marker="o",
                label="explanation_score",
            )
            ax.axhline(y=0.5, color="r", linestyle="--", alpha=0.5, label="基准线")
            ax.set_xlabel("轮次")
            ax.set_ylabel("score")
            ax.set_title("explanation_score 学习曲线")
            ax.legend()

        plt.tight_layout()
        plt.savefig(self.figures_dir / "dimension4_ema_convergence.png", dpi=150)
        plt.close()
        print(f"  图表已保存: {self.figures_dir / 'dimension4_ema_convergence.png'}")
        print()

    def analyze_dimension6_mode_comparison(self):
        """验证维度6：模式对比分析"""
        print("=" * 60)
        print("  验证维度6：模式对比分析")
        print("=" * 60)

        mode_counts = self.df["experimentMode"].value_counts()
        print("  数据分布:")
        for mode, count in mode_counts.items():
            print(f"    {mode}: {count} 条")
        print()

        print("  6.1 行为指标对比")
        print("  " + "-" * 40)
        for mode in mode_counts.index:
            mode_df = self.df[self.df["experimentMode"] == mode]
            print(f"  {mode}:")
            print(f"    平均决策时间: {mode_df['totalTime'].mean():.0f} ms")
            a_rate = (mode_df["finalChoice"] == "A").mean()
            print(f"    A选择比例: {a_rate:.1%}")
            print(f"    B选择比例: {1 - a_rate:.1%}")
        print()

        if "full" in mode_counts.index and "manual" in mode_counts.index:
            print("  6.2 眼动指标对比 (full vs manual)")
            print("  " + "-" * 40)
            for col in [
                "saccadeCount",
                "gazeBias",
                "tau",
                "regressionRate",
                "decisionLatency",
            ]:
                full_data = self.df[
                    (self.df["experimentMode"] == "full") & self.df[col].notna()
                ][col]
                manual_data = self.df[
                    (self.df["experimentMode"] == "manual") & self.df[col].notna()
                ][col]
                if len(full_data) > 0 and len(manual_data) > 0:
                    print(f"  {col}:")
                    print(f"    full: {full_data.mean():.3f} (n={len(full_data)})")
                    print(
                        f"    manual: {manual_data.mean():.3f} (n={len(manual_data)})"
                    )
                    if len(full_data) > 1 and len(manual_data) > 1:
                        t_stat, p_val = ttest_ind(full_data, manual_data)
                        print(f"    t检验: t = {t_stat:.3f}, p = {p_val:.4f}")
        print()

        self._plot_dimension6()

    def _plot_dimension6(self):
        """维度6可视化"""
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        fig.suptitle("维度6：模式对比分析", fontsize=14)

        ax = axes[0]
        mode_groups = self.df.groupby("experimentMode")["totalTime"].mean()
        if len(mode_groups) > 0:
            mode_groups.plot(kind="bar", ax=ax)
            ax.set_ylabel("平均决策时间 (ms)")
            ax.set_title("各模式平均决策时间")
            ax.set_xticklabels(ax.get_xticklabels(), rotation=0)

        ax = axes[1]
        modes, rates = [], []
        for mode in self.df["experimentMode"].unique():
            mode_df = self.df[self.df["experimentMode"] == mode]
            modes.append(mode)
            rates.append((mode_df["finalChoice"] == "A").mean())
        if rates:
            ax.bar(modes, rates)
            ax.set_ylabel("A选择比例")
            ax.set_title("各模式A选择比例")
            ax.set_xticklabels(modes, rotation=0)

        plt.tight_layout()
        plt.savefig(self.figures_dir / "dimension6_mode_comparison.png", dpi=150)
        plt.close()
        print(f"  图表已保存: {self.figures_dir / 'dimension6_mode_comparison.png'}")
        print()

    def generate_summary_report(self):
        """生成汇总报告"""
        print("=" * 60)
        print("  实验数据分析汇总报告")
        print("=" * 60)
        print()

        print("  【描述性统计】")
        print(f"  - 样本量: N = {len(self.df)}")
        print(
            f"  - 平均决策时间: M = {self.df['totalTime'].mean():.0f} ms, SD = {self.df['totalTime'].std():.0f} ms"
        )
        a_rate = (self.df["finalChoice"] == "A").mean()
        print(f"  - A选择比例: {a_rate:.1%}")
        print()

        print("  【模式分布】")
        for mode, count in self.df["experimentMode"].value_counts().items():
            print(f"  - {mode}: {count} 条 ({count / len(self.df):.1%})")
        print()

        eye_coverage = self.df["hasEyeMetrics"].mean()
        print(f"  【眼动数据覆盖率】: {eye_coverage:.1%}")
        print()

        print("  分析完成！")
        print(f"  图表保存在: {self.figures_dir}/")


def main():
    """主函数"""
    # 获取项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    data_path = project_root / "backend" / "experiment_data.jsonl"

    if not data_path.exists():
        print(f"错误: 数据文件不存在: {data_path}")
        sys.exit(1)

    analyzer = ExperimentAnalyzer(data_path)
    analyzer.load_data()

    analyzer.analyze_dimension1_eye_effectiveness()
    analyzer.analyze_dimension2_normalization()
    analyzer.analyze_dimension3_prediction()
    analyzer.analyze_dimension4_ema_convergence()
    analyzer.analyze_dimension6_mode_comparison()

    analyzer.generate_summary_report()


if __name__ == "__main__":
    main()
