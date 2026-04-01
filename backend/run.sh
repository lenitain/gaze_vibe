#!/bin/bash
# 使用 uv 运行 GazeVibe 后端

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

# 运行应用
echo "启动后端服务..."
uv run python app.py
