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

echo "启动 GazeVibe..."

(cd backend && bash run.sh) &
pids+=($!)
(cd frontend && bun run dev) &
pids+=($!)

wait
