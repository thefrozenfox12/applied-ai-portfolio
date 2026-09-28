#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
: "${REVIEW_API_KEY:?Set REVIEW_API_KEY to your provider key}"
: "${REVIEW_BASE_URL:?Set REVIEW_BASE_URL to your model API base URL}"
python3 pipeline.py prepare
python3 pipeline.py spotcheck
python3 pipeline.py binary
python3 pipeline.py three_class
python3 experiments.py all
python3 emotions.py all
python3 analysis.py
python3 verify_results.py
python3 dashboard.py
python3 report.py
