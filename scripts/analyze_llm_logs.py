"""
LLM 调用日志分析

分析 LLMClient 调用记录：token 消耗、延迟分布、重试率、工具调用模式。
输出图表到 docs/figures/。
"""

import json
import sys
from pathlib import Path

import pandas as pd

FIGURES_DIR = Path(__file__).parent.parent / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def find_logs() -> list[Path]:
    """查找所有 log 文件"""
    log_dir = Path(__file__).parent.parent / "backend" / "logs"
    return sorted(log_dir.glob("llm_calls_*.jsonl"))


def load_logs() -> pd.DataFrame:
    """加载所有 log"""
    files = find_logs()
    if not files:
        print("  未找到 LLM 调用日志")
        sys.exit(0)

    records = []
    for f in files:
        for line in f.read_text(encoding="utf-8").strip().split("\n"):
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return pd.DataFrame(records)


def analyze(df: pd.DataFrame):
    """执行分析"""
    print("=" * 60)
    print("  LLM 调用日志分析")
    print("=" * 60)
    print(f"  总调用数: {len(df)}")

    # 成功率
    success_rate = df["success"].mean() if "success" in df.columns else 1.0
    print(f"  成功率: {success_rate:.1%}")

    # Token 统计
    if "total_tokens" in df.columns:
        total = df["total_tokens"].sum()
        avg = df["total_tokens"].mean()
        print(f"  总 Token: {total:,}")
        print(f"  平均 Token/次: {avg:.0f}")
        print(f"  输入 Token: {df['input_tokens'].sum():,}")
        print(f"  输出 Token: {df['output_tokens'].sum():,}")

    # 延迟
    if "latency_ms" in df.columns:
        print("\n  延迟 (ms):")
        print(f"    平均: {df['latency_ms'].mean():.0f}")
        print(f"    中位: {df['latency_ms'].median():.0f}")
        print(f"    P95:  {df['latency_ms'].quantile(0.95):.0f}")
        print(f"    最大: {df['latency_ms'].max():.0f}")

    # 重试
    if "retry_count" in df.columns:
        retries = df[df["retry_count"] > 0]
        print(f"\n  重试次数: {len(retries)} ({len(retries)/len(df)*100:.1f}%)")

    # 调用者分布
    if "caller" in df.columns:
        print("\n  调用者分布:")
        for caller, count in df["caller"].value_counts().items():
            print(f"    {caller}: {count} 次 ({count/len(df)*100:.1f}%)")

    # 按时间分析 token 趋势
    if "timestamp" in df.columns:
        df_ts = df.copy()
        df_ts["timestamp"] = pd.to_datetime(df_ts["timestamp"])
        df_ts = df_ts.sort_values("timestamp")
        df_ts["cumul_tokens"] = df_ts["total_tokens"].cumsum()

        df_ts["cumul_tokens"].plot(
            title="Cumulative Token Usage Over Time",
            xlabel="Call Sequence",
            ylabel="Total Tokens",
        )
        import matplotlib.pyplot as plt
        plt.tight_layout()
        path = FIGURES_DIR / "llm_token_trend.svg"
        plt.savefig(path, format="svg")
        plt.close()
        print(f"\n  Token 趋势图: {path}")

    # 输出/输入比分布
    if "output_tokens" in df.columns and "input_tokens" in df.columns:
        df["ratio"] = df["output_tokens"] / (df["input_tokens"] + 1)
        print("\n  输出/输入比:")
        print(f"    平均: {df['ratio'].mean():.2f}")
        print(f"    中位: {df['ratio'].median():.2f}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    data = load_logs()
    if not data.empty:
        analyze(data)
