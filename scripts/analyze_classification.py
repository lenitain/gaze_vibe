#!/usr/bin/env python3
"""
维度分类准确率分析脚本（场景 E）

分析 LLM 分类和关键词回退两种策略在各个工程决策维度上的准确率。

输入：手动记录的 CSV 文件（路径由用户指定）
  格式: question, expected_dim, llm_result, keyword_result, scene_id
  示例: "我想加缓存库","ecosystem_maturity","ecosystem_maturity,dependency_philosophy","ecosystem_maturity","E"

输出：classification_accuracy.svg
  - 子图1: 每个维度的 LLM vs 关键词 准确率柱状图
  - 子图2: LLM 分类混淆矩阵热图
  - 子图3: 关键词分类混淆矩阵热图
"""

import json
import csv
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).parent.parent
FIGURES_DIR = PROJECT_ROOT / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# 所有 10 个维度
ALL_DIMS = [
    "ecosystem_maturity",
    "correctness_strategy",
    "error_handling",
    "edge_case_coverage",
    "testing_strategy",
    "dependency_philosophy",
    "naming_style",
    "documentation_depth",
    "abstraction_timing",
    "performance_priority",
]

DIMS_LABEL = {
    "ecosystem_maturity": "生态成熟度",
    "correctness_strategy": "正确性策略",
    "error_handling": "错误处理",
    "edge_case_coverage": "边界覆盖",
    "testing_strategy": "测试策略",
    "dependency_philosophy": "依赖哲学",
    "naming_style": "命名风格",
    "documentation_depth": "文档深度",
    "abstraction_timing": "抽象时机",
    "performance_priority": "性能优先级",
}


def prompt_template_csv() -> str:
    """打印 CSV 模板"""
    return """# 维度分类实验记录表（场景 E）
# 将以下内容保存为 classification_log.csv，每轮填一行
# question,expected_dim,llm_result,keyword_result
# llm_result 和 keyword_result 是从后端日志读取的维度列表（逗号分隔）
#
我想在我的Rust项目里加缓存库,moka还是chachacache,ecosystem_maturity,ecosystem_maturity,dependency_philosophy,ecosystem_maturity
"""


def load_csv(path: str) -> pd.DataFrame:
    """加载分类记录 CSV"""
    if not Path(path).exists():
        print(f"错误: 文件不存在 {path}")
        print("\n提示: 请先创建分类记录 CSV 文件，格式为:")
        print("  question,expected_dim,llm_result,keyword_result")
        print("\n运行 --template 可查看模板")
        sys.exit(1)

    df = pd.read_csv(path)
    required = ["question", "expected_dim"]
    for col in required:
        if col not in df.columns:
            print(f"错误: CSV 缺少必要列 '{col}'")
            sys.exit(1)

    print(f"  加载 {len(df)} 条分类记录")
    return df


def compute_accuracy(df: pd.DataFrame) -> dict:
    """计算每个维度的准确率"""
    results = {}
    for dim in ALL_DIMS:
        dim_df = df[df["expected_dim"] == dim]
        if len(dim_df) == 0:
            continue

        llm_hits = 0
        kw_hits = 0
        total = len(dim_df)

        for _, row in dim_df.iterrows():
            # LLM 分类结果
            llm_result = str(row.get("llm_result", "")).strip()
            llm_dims = [d.strip() for d in llm_result.split(",") if d.strip()]
            if dim in llm_dims:
                llm_hits += 1

            # 关键词分类结果
            kw_result = str(row.get("keyword_result", "")).strip()
            kw_dims = [d.strip() for d in kw_result.split(",") if d.strip()]
            if dim in kw_dims:
                kw_hits += 1

        results[dim] = {
            "total": total,
            "llm_hits": llm_hits,
            "kw_hits": kw_hits,
            "llm_accuracy": llm_hits / total if total > 0 else 0,
            "kw_accuracy": kw_hits / total if total > 0 else 0,
        }

    return results


def compute_confusion_matrix(df: pd.DataFrame, result_col: str) -> np.ndarray:
    """计算混淆矩阵"""
    n = len(ALL_DIMS)
    matrix = np.zeros((n, n), dtype=int)

    for _, row in df.iterrows():
        expected = row["expected_dim"]
        if expected not in ALL_DIMS:
            continue
        expected_idx = ALL_DIMS.index(expected)

        result_str = str(row.get(result_col, "")).strip()
        result_dims = [d.strip() for d in result_str.split(",") if d.strip()]

        for pred_dim in result_dims:
            if pred_dim in ALL_DIMS:
                pred_idx = ALL_DIMS.index(pred_dim)
                matrix[expected_idx][pred_idx] += 1

    return matrix


def analyze_and_plot():
    print("=" * 60)
    print("  维度分类准确率分析（场景 E）")
    print("=" * 60)

    # 检查是否有 --template 参数
    if "--template" in sys.argv:
        print(prompt_template_csv())
        return

    # 获取 CSV 路径
    csv_path = sys.argv[1] if len(sys.argv) > 1 else str(
        PROJECT_ROOT / "backend" / "classification_log.csv"
    )
    print(f"  CSV 文件: {csv_path}")

    df = load_csv(csv_path)

    # 计算准确率
    results = compute_accuracy(df)
    print(f"\n  有效维度数: {len(results)}")

    # 计算混淆矩阵
    llm_matrix = compute_confusion_matrix(df, "llm_result")
    kw_matrix = compute_confusion_matrix(df, "keyword_result")

    # ===== 绘图 =====
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle("维度分类准确率分析", fontsize=14, fontweight="bold")

    # ===== 子图 1: 准确率柱状图 =====
    ax = axes[0, 0]
    dims_with_data = sorted(results.keys(), key=lambda d: DIMS_LABEL.get(d, d))
    labels = [DIMS_LABEL.get(d, d) for d in dims_with_data]
    llm_acc = [results[d]["llm_accuracy"] * 100 for d in dims_with_data]
    kw_acc = [results[d]["kw_accuracy"] * 100 for d in dims_with_data]

    x = np.arange(len(dims_with_data))
    width = 0.35
    bars1 = ax.bar(x - width / 2, llm_acc, width, label="LLM 分类", color="#4a90e2")
    bars2 = ax.bar(x + width / 2, kw_acc, width, label="关键词回退", color="#e24a4a")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("准确率 (%)")
    ax.set_ylim(0, 105)
    ax.set_title("各维度分类准确率对比")
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)

    # 在柱上标数字
    for bar, val in zip(bars1, llm_acc):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%", ha="center", fontsize=7)
    for bar, val in zip(bars2, kw_acc):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f}%", ha="center", fontsize=7)

    # ===== 子图 2: 总体准确率对比 =====
    ax = axes[0, 1]
    all_llm = [results[d]["llm_hits"] for d in dims_with_data]
    all_kw = [results[d]["kw_hits"] for d in dims_with_data]
    all_total = [results[d]["total"] for d in dims_with_data]
    overall_llm = sum(all_llm) / sum(all_total) if sum(all_total) > 0 else 0
    overall_kw = sum(all_kw) / sum(all_total) if sum(all_total) > 0 else 0

    bar_colors = ["#4a90e2", "#e24a4a"]
    bars = ax.bar(["LLM 分类", "关键词回退"], [overall_llm * 100, overall_kw * 100],
                  color=bar_colors)
    ax.set_ylabel("总体准确率 (%)")
    ax.set_ylim(0, 105)
    ax.set_title("总体准确率对比")
    for bar, val in zip(bars, [overall_llm * 100, overall_kw * 100]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.1f}%", ha="center", fontsize=11, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    # ===== 子图 3: LLM 混淆矩阵热图 =====
    ax = axes[1, 0]
    short_labels = [DIMS_LABEL.get(d, d)[:4] for d in ALL_DIMS]
    im = ax.imshow(llm_matrix, cmap="Blues", aspect="auto")

    # 标注数字
    for i in range(len(ALL_DIMS)):
        for j in range(len(ALL_DIMS)):
            val = llm_matrix[i][j]
            if val > 0:
                ax.text(j, i, str(val), ha="center", va="center",
                        fontsize=8, color="white" if val > llm_matrix.max() / 2 else "black")

    ax.set_xticks(range(len(ALL_DIMS)))
    ax.set_yticks(range(len(ALL_DIMS)))
    ax.set_xticklabels(short_labels, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(short_labels, fontsize=7)
    ax.set_xlabel("预测维度")
    ax.set_ylabel("实际维度")
    ax.set_title("LLM 分类混淆矩阵")
    plt.colorbar(im, ax=ax, shrink=0.6)

    # ===== 子图 4: 关键词混淆矩阵热图 =====
    ax = axes[1, 1]
    im = ax.imshow(kw_matrix, cmap="Reds", aspect="auto")

    for i in range(len(ALL_DIMS)):
        for j in range(len(ALL_DIMS)):
            val = kw_matrix[i][j]
            if val > 0:
                ax.text(j, i, str(val), ha="center", va="center",
                        fontsize=8, color="white" if val > kw_matrix.max() / 2 else "black")

    ax.set_xticks(range(len(ALL_DIMS)))
    ax.set_yticks(range(len(ALL_DIMS)))
    ax.set_xticklabels(short_labels, rotation=45, ha="right", fontsize=7)
    ax.set_yticklabels(short_labels, fontsize=7)
    ax.set_xlabel("预测维度")
    ax.set_ylabel("实际维度")
    ax.set_title("关键词回退混淆矩阵")
    plt.colorbar(im, ax=ax, shrink=0.6)

    plt.tight_layout()
    path = FIGURES_DIR / "classification_accuracy.svg"
    plt.savefig(path, format="svg", dpi=150)
    plt.close()
    print(f"\n  图表已保存: {path}")

    # 打印数值摘要
    print("\n  各维度准确率:")
    print(f"  {'维度':<12s} {'样本':>4s} {'LLM':>8s} {'关键词':>8s}")
    print("  " + "-" * 34)
    for dim in dims_with_data:
        r = results[dim]
        label = DIMS_LABEL.get(dim, dim)
        print(f"  {label:<12s} {r['total']:>4d} {r['llm_accuracy']*100:>7.0f}% {r['kw_accuracy']*100:>7.0f}%")

    print(f"\n  总体准确率:")
    print(f"    LLM 分类:   {overall_llm*100:.1f}% ({sum(all_llm)}/{sum(all_total)})")
    print(f"    关键词回退: {overall_kw*100:.1f}% ({sum(all_kw)}/{sum(all_total)})")


if __name__ == "__main__":
    analyze_and_plot()
