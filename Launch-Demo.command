#!/bin/bash
# Field Intelligence — double-click launcher (macOS).
# Starts the local application and opens it in your browser.
# No credentials are stored in this file. If a .env file exists next to it,
# its contents are loaded so the live Claude Q&A panel is enabled.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required. Install it from https://www.python.org/downloads/"
  read -r -p "Press Return to close."
  exit 1
fi

if [ -f .env ]; then
  set -a; . ./.env; set +a
  echo "Loaded .env — live Claude Q&A enabled."
else
  echo "No .env found — running without live Claude Q&A. Everything else works."
fi

echo "Starting Field Intelligence. Close this window or press Ctrl-C to stop."
python3 demo_ui/serve.py
