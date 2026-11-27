#!/usr/bin/env bash
# Reproduce the grounding & evaluation results (no API calls). Run from the repository root.
set -euo pipefail
python -m pytest -q
python -m src.experiments.run_grounding_evaluation > /dev/null
python -m src.experiments.run_stage1_grounding > /dev/null
python -m src.experiments.run_answer_evaluation > /dev/null
python -m src.experiments.run_error_analysis > /dev/null
python -m src.reporting.generate_tables > /dev/null
python -m src.reporting.generate_plots
echo "done: see results/tables/all_tables.md and results/plots/"
