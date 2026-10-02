#!/bin/bash
# start.sh: one command to set up (first time only) and run JobFisher.
# Usage (from Terminal, inside this folder):   bash start.sh
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  echo "First run: creating a virtual environment (venv) and installing dependencies..."
  python3 -m venv venv
  ./venv/bin/pip install --upgrade pip >/dev/null
  ./venv/bin/pip install -r requirements.txt
fi

./venv/bin/python app.py
