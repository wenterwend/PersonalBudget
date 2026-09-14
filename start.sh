#!/bin/bash
# Exit cleanly on stop (Ctrl+C)
trap 'kill $(jobs -p)' EXIT

echo "Starting FastAPI Backend on port 8000..."
.venv/bin/uvicorn src.backend.main:app --port 8000 &

echo "Starting SvelteKit Frontend on port 5173..."
(cd src/frontend && npm run dev) &

wait
