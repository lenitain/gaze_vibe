#!/bin/bash
# GazeVibe 后端启动

cd "$(dirname "$0")"

# 检查 venv
if [ ! -f ".venv/bin/python" ]; then
    echo "创建虚拟环境..."
    uv venv
fi

# 安装依赖
echo "安装依赖..."
uv pip install -r requirements.txt -q 2>/dev/null || uv pip install -r requirements.txt -q

# 直接启动（不走 uv run，避免 pyproject.toml 构建）
echo "启动后端服务..."
exec .venv/bin/python app.py
