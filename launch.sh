#!/bin/bash
# Exit cleanly on stop
trap 'kill $(jobs -p)' EXIT

# Start backend & frontend
cd /home/wend/all/code/budget
.venv/bin/uvicorn src.backend.main:app --port 8000 &
(cd src/frontend && npm run dev) &

# Wait 2 seconds for server boot, then open default web browser
sleep 2
xdg-open http://localhost:5173

wait
