#!/bin/bash

cd "$(dirname "$0")"

pids=()

cleanup() {
    echo ""
    echo "停止服务..."
    for pid in "${pids[@]}"; do
        kill -- -$(ps -o pgid= -p "$pid" 2>/dev/null | tr -d ' ') 2>/dev/null
    done
    wait 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

# ===== 依赖检查 =====

echo "检查依赖..."

# 后端: 检查 uv 和 venv
if ! which uv &>/dev/null; then
    echo "[后] uv 未安装，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

cd backend

if [ ! -f ".venv/bin/python" ]; then
    echo "[后] venv 不存在，使用 uv 创建..."
    uv venv
fi

# 检查并同步依赖
if [ ! -f ".venv/bin/python" ]; then
    echo "[后] 无法创建 venv，请手动: cd backend && uv venv"
    exit 1
fi

echo "[后] 同步依赖..."
uv pip sync requirements.txt -q 2>/dev/null || uv pip install -r requirements.txt -q

cd ..

# 前端: 检查 node_modules
if [ ! -d "frontend/node_modules" ]; then
    echo "[前] node_modules 不存在，运行 bun install..."
    (cd frontend && bun install) || {
        echo "bun install 失败，请手动运行: cd frontend && bun install"
        exit 1
    }
fi

# 检查关键前端包
if [ ! -f "frontend/node_modules/.bin/vite" ]; then
    echo "[前] vite 未安装，运行 bun install..."
    (cd frontend && bun install) || {
        echo "bun install 失败"
        exit 1
    }
fi

echo "依赖检查通过，启动服务..."
echo ""

# ===== 启动 =====

(cd backend && bash run.sh) &
pids+=($!)
(cd frontend && bun run dev) &
pids+=($!)

wait
