#!/usr/bin/env python3
"""Shared local data paths for Kubota Spears Analytics.

The project keeps code and generated reports in the repo, while raw BI CSVs and
the generated SQLite database live under the local-only ``data/`` directory.
Environment variables may override the defaults when needed.
"""
import glob
import os

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.path.abspath(
    os.environ.get("KUBOTA_DATA_ROOT", os.path.join(REPO_ROOT, "data"))
)
CSV_DIR = os.path.abspath(
    os.environ.get("KUBOTA_CSV_DIR", os.path.join(DATA_ROOT, "BI Scouting"))
)
COMPETITION_ROOT = os.path.abspath(
    os.environ.get("KUBOTA_COMPETITION_ROOT", os.path.join(DATA_ROOT, "competitions"))
)
DB_PATH = os.path.abspath(
    os.environ.get("KUBOTA_DB_PATH", os.path.join(DATA_ROOT, "rugby.db"))
)
OUTPUT_DIR = REPO_ROOT


def ensure_data_dirs():
    """Create local-only data directories when missing."""
    os.makedirs(DATA_ROOT, exist_ok=True)
    os.makedirs(CSV_DIR, exist_ok=True)
    os.makedirs(COMPETITION_ROOT, exist_ok=True)


def list_csv_files(root_dir=None):
    """Return CSV files under ``root_dir``, supporting flat and nested layouts."""
    base = os.path.abspath(root_dir or DATA_ROOT)
    direct = glob.glob(os.path.join(base, "*.csv"))
    nested = glob.glob(os.path.join(base, "**", "*.csv"), recursive=True)
    files = sorted(set(os.path.abspath(p) for p in (direct + nested)))
    picked = {}
    for path in sorted(files, key=lambda p: ("BI Scouting" in p, len(p), p)):
        if not os.path.isfile(path):
            continue
        picked.setdefault(os.path.basename(path), path)
    return sorted(picked.values())
