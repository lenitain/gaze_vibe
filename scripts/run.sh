#!/bin/bash
# GazeVibe 数据分析 — 一键运行所有分析脚本

cd "$(dirname "$0")"

# 检查 uv 是否安装
if ! command -v uv &> /dev/null; then
    echo "错误: uv 未安装"
    echo "请先安装 uv: https://github.com/astral-sh/uv#installation"
    exit 1
fi

# 创建虚拟环境（如果不存在）
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境..."
    uv venv
fi

# 安装依赖
echo "安装依赖..."
uv pip install -r requirements.txt

echo ""
echo "========================================"
echo "  GazeVibe 数据分析"
echo "========================================"
echo ""

# 运行实验数据分析（眼动指标验证）
echo "1/6: 实验数据分析..."
uv run python analyze_experiment.py

# 运行 LLM 调用日志分析
echo "2/6: LLM 调用日志分析..."
uv run python analyze_llm_logs.py

# 运行记忆系统分析
echo "3/6: 记忆系统分析..."
uv run python analyze_memory.py

# 运行 Persona 系统分析
echo "4/6: Persona 系统分析..."
uv run python analyze_persona.py

# 运行反转实验分析（场景 D）
echo "5/6: 反转实验分析..."
uv run python analyze_reversal.py

# 运行维度分类准确率分析（场景 E）— 需要 classification_log.csv
echo "6/6: 维度分类准确率分析..."
if [ -f "../backend/classification_log.csv" ]; then
    uv run python analyze_classification.py "../backend/classification_log.csv"
else
    echo "  跳过: 未找到 classification_log.csv"
    echo "  提示: 运行场景 E 后, 将记录保存到 backend/classification_log.csv"
fi

echo ""
echo "所有分析完成！图表已保存到 docs/figures/"
