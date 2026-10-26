#!/usr/bin/env bash
set -euo pipefail
PORT=8000
if command -v lsof >/dev/null 2>&1; then
  lsof -ti tcp:"$PORT" | xargs -r kill
elif command -v fuser >/dev/null 2>&1; then
  fuser -k "$PORT"/tcp || true
else
  echo "No supported process killer found. Stop the uvicorn process manually on port $PORT." >&2
  exit 1
fi
