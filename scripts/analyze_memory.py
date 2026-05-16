"""
记忆系统分析

分析 MemoryStore 数据：记忆类型分布、检索模式、收敛速度、Persona 演化。
输出图表到 docs/figures/。
"""

import json
import sys
from pathlib import Path

import pandas as pd

FIGURES_DIR = Path(__file__).parent.parent / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def find_memory_data() -> Path | None:
    """查找记忆数据文件"""
    path = Path(__file__).parent.parent / "backend" / "memory_data" / "items.jsonl"
    return path if path.exists() else None


def load_memories() -> pd.DataFrame:
    """加载记忆数据"""
    path = find_memory_data()
    if not path:
        print("  未找到记忆数据（请先运行应用以产生数据）")
        sys.exit(0)

    records = []
    for line in path.read_text(encoding="utf-8").strip().split("\n"):
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return pd.DataFrame(records)


def analyze(df: pd.DataFrame):
    """执行分析"""
    print("=" * 60)
    print("  记忆系统分析")
    print("=" * 60)
    print(f"  总记忆数: {len(df)}")

    # 类型分布
    if "type" in df.columns:
        print("\n  记忆类型分布:")
        for t, count in df["type"].value_counts().items():
            print(f"    {t}: {count} ({count/len(df)*100:.1f}%)")

    # 置信度分布
    if "confidence" in df.columns:
        confs = df["confidence"]
        print("\n  置信度:")
        print(f"    平均: {confs.mean():.3f}")
        print(f"    范围: {confs.min():.3f} ~ {confs.max():.3f}")

    # 按时间的记忆创建趋势
    if "created_at" in df.columns:
        df_ts = df.copy()
        df_ts["created_at"] = pd.to_datetime(df_ts["created_at"])
        df_ts = df_ts.sort_values("created_at")
        df_ts["cumulative"] = range(1, len(df_ts) + 1)

        df_ts.set_index("created_at")["cumulative"].plot(
            title="Memory Accumulation Over Time",
            xlabel="Time",
            ylabel="Total Memories",
        )
        import matplotlib.pyplot as plt
        plt.tight_layout()
        path = FIGURES_DIR / "memory_accumulation.svg"
        plt.savefig(path, format="svg")
        plt.close()
        print(f"\n  记忆积累图: {path}")

    # Persona 偏好信号分析（episodic 记忆）
    episodic = df[df["type"] == "episodic"]
    if not episodic.empty and "persona" in episodic.columns:
        print("\n  Persona 偏好分布 (episodic):")
        for p, count in episodic["persona"].value_counts().items():
            print(f"    Persona {p}: {count} 次")

    # Semantic 事实提取
    semantic = df[df["type"] == "semantic"]
    if not semantic.empty:
        print("\n  Semantic 事实:")
        for _, row in semantic.iterrows():
            print(f"    - {row.get('content', '')[:80]}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    data = load_memories()
    if not data.empty:
        analyze(data)
