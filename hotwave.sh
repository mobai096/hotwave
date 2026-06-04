#!/usr/bin/env bash
# 🌊 Hot Wave 启动脚本
# 用法: ./hotwave.sh [command]

set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/../hot-daily/.venv"
export PYTHONPATH="$DIR/../hot-daily/src:$PYTHONPATH"
export PATH="$VENV/bin:$PATH"

CMD="${1:-chat}"

exec "$VENV/bin/python3" -m hotwave "$CMD" --config "$DIR/config.yaml"
