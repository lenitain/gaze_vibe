#!/usr/bin/env python3
"""
反转实验分析脚本（场景 D）

分析偏好反转场景中的数据：
1. detail_score / explanation_score 在反转前后的变化曲线
2. Persona 维度 A/B 差距在反转前后的演化
3. 反转检测延迟、解除收敛时间、重新收敛时间的标注

输入：experiment_data.jsonl（按 scene_id=="D" 过滤）
     persona_states/*.log.jsonl（状态变更日志）
输出：reversal_analysis.svg
"""

import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

PROJECT_ROOT = Path(__file__).parent.parent
FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

DIMS_LABEL = {
    "ecosystem_maturity": "生态成熟度",
    "correctness_strategy": "正确性策略",
    "naming_style": "命名风格",
    "documentation_depth": "文档深度",
    "error_handling": "错误处理",
    "edge_case_coverage": "边界覆盖",
    "dependency_philosophy": "依赖哲学",
    "abstraction_timing": "抽象时机",
    "testing_strategy": "测试策略",
    "performance_priority": "性能优先级",
}


def load_experiment_data() -> pd.DataFrame:
    """加载实验数据"""
    path = PROJECT_ROOT / "backend" / "experiment_data.jsonl"
    if not path.exists():
        print("错误: experiment_data.jsonl 不存在")
        sys.exit(1)

    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return pd.DataFrame(records)


def load_persona_log(project: str = "test_proj") -> list[dict]:
    """加载 Persona 状态变更日志"""
    path = PROJECT_ROOT / "backend" / "persona_states" / f"{project}.log.jsonl"
    if not path.exists():
        print(f"  注意: persona 日志 {path} 不存在，将跳过维度分析")
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").strip().split("\n")
        if line
    ]


def analyze_and_plot():
    print("=" * 60)
    print("  反转实验分析（场景 D）")
    print("=" * 60)

    # 加载数据
    df = load_experiment_data()
    raw_count = len(df)
    print(f"  实验数据: {raw_count} 条")

    # 提取字段
    df["finalChoice"] = df["preference"].apply(lambda p: p.get("finalChoice"))
    df["detail_score"] = df["adjustments"].apply(
        lambda a: a.get("detail_score", 0.5) if isinstance(a, dict) else 0.5
    )
    df["explanation_score"] = df["adjustments"].apply(
        lambda a: a.get("explanation_score", 0.5) if isinstance(a, dict) else 0.5
    )
    df["persona_bias"] = df["adjustments"].apply(
        lambda a: a.get("persona_bias", 0.5) if isinstance(a, dict) else 0.5
    )
    df["round_count"] = df["adjustments"].apply(
        lambda a: a.get("round_count", 0) if isinstance(a, dict) else 0
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # 按时间排序
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 尝试按 scene_id 过滤，如果没有则用全部数据
    if "scene_id" in df.columns:
        rev_df = df[df["scene_id"] == "D"].copy()
        if len(rev_df) == 0:
            print("  有 scene_id 列但无 scene_id==D 的数据，使用全部数据")
            rev_df = df.copy()
    else:
        rev_df = df.copy()

    total_rounds = len(rev_df)
    print(f"  有效轮次: {total_rounds}")

    if total_rounds < 10:
        print("  数据不足 10 轮，无法分析反转")
        return

    # 找出反转点：从选 A 切到选 B 的位置
    choices = rev_df["finalChoice"].values
    reversal_idx = None
    for i in range(1, len(choices)):
        if choices[i-1] == "A" and choices[i] == "B":
            reversal_idx = i
            break

    print(f"  反转点: 第 {reversal_idx} 轮" if reversal_idx else "  未检测到反转")

    # 加载 Persona 日志
    persona_log = load_persona_log()
    dim_names = list(DIMS_LABEL.keys())

    # ===== 绘图 =====
    fig, axes = plt.subplots(3, 1, figsize=(12, 12))
    fig.suptitle("偏好反转实验分析（场景 D）", fontsize=14, fontweight="bold")

    # ===== 子图 1: detail_score + explanation_score =====
    ax = axes[0]
    rounds = range(1, total_rounds + 1)
    ax.plot(rounds, rev_df["detail_score"].values, "o-", label="detail_score",
            color="#e24a4a", linewidth=1.8, markersize=4)
    ax.plot(rounds, rev_df["explanation_score"].values, "s--", label="explanation_score",
            color="#4a90e2", linewidth=1.8, markersize=4)
    ax.axhline(y=0.5, color="gray", linestyle=":", alpha=0.5, label="中性值 (0.5)")

    # 标注反转点
    if reversal_idx:
        ax.axvline(x=reversal_idx, color="orange", linewidth=2, linestyle="-",
                   alpha=0.8, label=f"反转点 (第{reversal_idx}轮)")
        # 标注反转检测点（反转后第3轮）
        detect_idx = reversal_idx + 3
        if detect_idx <= total_rounds:
            ax.axvline(x=detect_idx, color="green", linewidth=2, linestyle="--",
                       alpha=0.8, label=f"反转检测 (第{detect_idx}轮)")

    ax.set_xlabel("轮次")
    ax.set_ylabel("分数")
    ax.set_title("偏好分数反转曲线")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.2)

    # ===== 子图 2: Persona Bias + 选择方向 =====
    ax = axes[1]
    ax.plot(rounds, rev_df["persona_bias"].values, "o-", color="#7f6db0",
            linewidth=1.8, markersize=4, label="persona_bias (0=现代派, 1=稳健派)")

    # 标注选择方向
    for i in range(total_rounds):
        c = choices[i]
        if c == "A":
            ax.scatter(i + 1, 1.05, marker="^", color="#e24a4a", s=20, alpha=0.6)
        elif c == "B":
            ax.scatter(i + 1, -0.05, marker="v", color="#4a90e2", s=20, alpha=0.6)

    if reversal_idx:
        ax.axvline(x=reversal_idx, color="orange", linewidth=2, linestyle="-", alpha=0.8)

    ax.set_xlabel("轮次")
    ax.set_ylabel("Persona Bias")
    ax.set_ylim(-0.1, 1.1)
    ax.set_title("Persona 偏差与选择方向（▲=选A，▼=选B）")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.2)

    # ===== 子图 3: 关键维度的 A/B 差距演化（从 persona 日志）=====
    ax = axes[2]
    if persona_log:
        # 提取精选维度的差距
        selected_dims = ["error_handling", "ecosystem_maturity", "naming_style", "testing_strategy"]
        selected_labels = [DIMS_LABEL.get(d, d) for d in selected_dims]
        colors = plt.cm.Set1(np.linspace(0, 0.8, len(selected_dims)))

        for dim, label, color in zip(selected_dims, selected_labels, colors):
            gaps = []
            steps = []
            for i, record in enumerate(persona_log):
                a_scores = record.get("persona_a_scores", {})
                b_scores = record.get("persona_b_scores", {})
                a_val = a_scores.get(dim, 3.0)
                b_val = b_scores.get(dim, 3.0)
                gaps.append(abs(a_val - b_val))
                steps.append(i + 1)

            ax.plot(steps, gaps, "o-", label=label, color=color,
                    linewidth=1.5, markersize=3, alpha=0.8)

        ax.axhline(y=0.5, color="gray", linestyle=":", alpha=0.5, label="收敛阈值 (0.5)")
        ax.set_xlabel("选择次数")
        ax.set_ylabel("|A - B| 差距")
        ax.set_title("精选维度 A/B 分数差距演化")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.2)
    else:
        ax.text(0.5, 0.5, "Persona 日志数据不可用\n运行实验后自动生成",
                ha="center", va="center", transform=ax.transAxes, fontsize=12,
                color="gray", style="italic")
        ax.set_title("维度 A/B 差距演化（等待实验数据）")

    plt.tight_layout()
    path = FIGURES_DIR / "reversal_analysis.svg"
    plt.savefig(path, format="svg", dpi=150)
    plt.close()
    print(f"\n  图表已保存: {path}")

    # 打印数值摘要
    print("\n  数值摘要:")
    if reversal_idx:
        pre_rev = rev_df.iloc[:reversal_idx]
        post_rev = rev_df.iloc[reversal_idx:]
        print(f"    反转前 detail_score 均值: {pre_rev['detail_score'].mean():.4f}")
        print(f"    反转后 detail_score 均值: {post_rev['detail_score'].mean():.4f}")
        print(f"    反转前 persona_bias 均值: {pre_rev['persona_bias'].mean():.4f}")
        print(f"    反转后 persona_bias 均值: {post_rev['persona_bias'].mean():.4f}")

        # 检测延迟
        detect_delay = 3  # UNCONVERGE_THRESHOLD
        print(f"    反转检测延迟: {detect_delay} 轮（UNCONVERGE_THRESHOLD）")

    print(f"    总轮次数: {total_rounds}")


if __name__ == "__main__":
    analyze_and_plot()
