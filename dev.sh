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

# 后端: 检查 venv 和关键包
if [ ! -f "backend/.venv/bin/python" ]; then
    echo "[后] venv 不存在，请手动创建: cd backend && python3 -m venv .venv"
    echo "[后] 然后运行: .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# 检查关键包
backend_pkgs="flask openai pydantic"
missing=""
for pkg in $backend_pkgs; do
    if ! backend/.venv/bin/python -c "import $pkg" 2>/dev/null; then
        missing="$missing $pkg"
    fi
done
if [ -n "$missing" ]; then
    echo "[后] 缺失依赖:$missing，尝试安装..."
    backend/.venv/bin/pip install -r backend/requirements.txt -q
fi

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
