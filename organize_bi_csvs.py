#!/usr/bin/env python3
"""Organize Opta BI CSV files into a competition/season folder structure."""
import csv
import os
import re
import shutil

from data_paths import COMPETITION_ROOT, CSV_DIR, ensure_data_dirs, list_csv_files


def slugify(value):
    text = (value or "").strip().lower().replace("&", "and")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "unknown"


def season_label(raw):
    year = str(raw or "").strip()
    return year if year.isdigit() and len(year) == 4 else "unknown"


def classify(comp_name):
    name = (comp_name or "").lower()
    if "league one" in name:
        if "d1" in name:
            return ("league_one", "d1")
        if "d2" in name:
            return ("league_one", "d2")
        if "d3" in name:
            return ("league_one", "d3")
        return ("league_one", "other")
    if "super rugby" in name:
        return ("super_rugby", "main")
    if "urc" in name:
        return ("urc", "main")
    if "top 14" in name:
        return ("top14", "main")
    if "international" in name or "test match" in name:
        return ("international", "main")
    return (slugify(comp_name), "main")


def main():
    ensure_data_dirs()
    copied = 0
    skipped = 0
    for path in list_csv_files(CSV_DIR):
        try:
            with open(path, encoding="utf-8-sig", newline="") as fh:
                row = next(csv.DictReader(fh), None) or {}
        except Exception:
            skipped += 1
            continue
        comp_group, division = classify(row.get("competitionName"))
        season = season_label(row.get("season"))
        target_dir = os.path.join(COMPETITION_ROOT, comp_group, division, season)
        os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(path, os.path.join(target_dir, os.path.basename(path)))
        copied += 1
    print(f"organized {copied} csv files into {COMPETITION_ROOT}")
    if skipped:
        print(f"skipped {skipped} unreadable files")


if __name__ == "__main__":
    main()
