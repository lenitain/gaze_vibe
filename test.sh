#!/usr/bin/env bash
set -euo pipefail

# GazeVibe 统一测试运行器
# 用法: ./test.sh [backend|frontend|all]

MODE="${1:-all}"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "═ GazeVibe Test Runner ═"

if [[ "$MODE" == "backend" || "$MODE" == "all" ]]; then
    echo ""
    echo "── Backend ──"
    cd "$ROOT_DIR/backend"
    if [ ! -d ".venv" ]; then
        echo "请运行: cd backend && uv venv && uv pip install -r requirements.txt"
        exit 1
    fi
    echo "Lint (ruff)..."
    .venv/bin/python -m ruff check .
    echo "Test (pytest)..."
    .venv/bin/python -m pytest -v
    echo "✓ Backend passed"
fi

if [[ "$MODE" == "frontend" || "$MODE" == "all" ]]; then
    echo ""
    echo "── Frontend ──"
    cd "$ROOT_DIR/frontend"
    echo "Lint (biome)..."
    bunx biome check src/
    echo "Build..."
    bun run build
    echo "✓ Frontend passed"
fi

echo ""
echo "═ All checks passed ═"
