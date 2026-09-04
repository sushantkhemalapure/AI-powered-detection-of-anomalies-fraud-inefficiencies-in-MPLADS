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

if [ ! -f "data/mplads.db" ]; then
  echo "Generating synthetic MPLADS dataset..."
  python data_generator.py --works 3200 --anomaly-rate 0.09
fi

if [ ! -f "ml/artifacts/isolation_forest.joblib" ]; then
  echo "Training the risk-detection pipeline..."
  python -m ml.train
fi

echo ""
echo "Starting server on http://localhost:5000"
python app.py
