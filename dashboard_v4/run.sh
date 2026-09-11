#!/bin/zsh
# Serve the build board on http://127.0.0.1:8765 and refresh status.json every 60 s.
# Both processes are niced; the collector takes about a second per pass.
cd "$(dirname "$0")"
PORT=${PORT:-8765}
if ! lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  (nohup nice -n 15 python3 -m http.server $PORT --bind 127.0.0.1 > server.log 2>&1 &)
  echo "serving on http://127.0.0.1:$PORT/"
else
  echo "port $PORT already served"
fi
if ! pgrep -f "dashboard_v4/collect_loop" >/dev/null 2>&1; then
  cat > collect_loop.sh <<'EOF'
#!/bin/zsh
cd "$(dirname "$0")"
while true; do nice -n 15 python3 collect.py >> collect.log 2>&1; sleep 60; done
EOF
  chmod +x collect_loop.sh
  (nohup ./collect_loop.sh > /dev/null 2>&1 &)
  echo "collector loop started (every 60 s)"
else
  echo "collector loop already running"
fi
