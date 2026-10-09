#!/usr/bin/env python3
"""Download the public API and save the results to an Excel workbook or CSV."""

import csv
import os
from pathlib import Path

import requests

API_URL = os.environ.get("SAFESPACE_API_URL", "http://127.0.0.1:8000/api/quest-summary/")
OUTPUT_PATH = Path(os.environ.get("SAFESPACE_OUTPUT_FILE", "quest_summary.xlsx"))


def export_with_openpyxl(data):
    try:
        from openpyxl import Workbook
    except ImportError:
        return False

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Quest Summary"
    sheet.append(["Quest", "Category", "User Count"])

    for row in data:
        sheet.append([row.get("quest", ""), row.get("category", ""), row.get("user_count", 0)])

    workbook.save(OUTPUT_PATH)
    print(f"Saved Excel workbook to {OUTPUT_PATH}")
    return True


def export_as_csv(data):
    csv_path = OUTPUT_PATH.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Quest", "Category", "User Count"])
        for row in data:
            writer.writerow([row.get("quest", ""), row.get("category", ""), row.get("user_count", 0)])

    print(f"Saved CSV file to {csv_path}")


def main():
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Failed to call {API_URL}: {exc}")
        print("Start the app first: python manage.py runserver")
        return 1

    data = response.json()
    if not export_with_openpyxl(data):
        export_as_csv(data)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
