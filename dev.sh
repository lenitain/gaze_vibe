#!/bin/bash

cleanup() {
    echo ""
    echo "停止服务..."
    kill $(jobs -p) 2>/dev/null
    wait
    exit 0
}

trap cleanup SIGINT SIGTERM

cd "$(dirname "$0")"

echo "启动 GazeVibe..."

(cd backend && bash run.sh) &
(cd frontend && bun run dev) &

wait
