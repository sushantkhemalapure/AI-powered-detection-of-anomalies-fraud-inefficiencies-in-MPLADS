#!/usr/bin/env bash
# One-shot setup + run for the MPLADS Sentinel platform.
# Usage:  ./run.sh
set -e

cd "$(dirname "$0")/backend"

if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

source venv/bin/activate
echo "Installing dependencies..."
pip install -q -r requirements.txt

echo "Importing the bundled MPLADS allocation dataset..."
python data_loader.py

echo "Training the unsupervised allocation-pattern model..."
python -m ml.train

echo ""
echo "Starting server on http://localhost:5000"
python app.py
