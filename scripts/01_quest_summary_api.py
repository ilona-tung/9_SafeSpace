#!/usr/bin/env python3
"""Fetch the public SafeSpace quest summary API and print a simple report."""

import os
import requests

API_URL = os.environ.get("SAFESPACE_API_URL", "http://127.0.0.1:8000/api/quest-summary/")


def main():
    try:
        response = requests.get(API_URL, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"Failed to call the API at {API_URL}: {exc}")
        print("Start the app with: python manage.py runserver")
        return 1

    data = response.json()
    print(f"Fetched {len(data)} quest records from {API_URL}")
    print("\nQuest summary:")

    for item in data:
        quest = item.get("quest", "Unknown")
        category = item.get("category", "Unknown")
        user_count = item.get("user_count", 0)
        print(f"- {quest:<30} | {category:<20} | {user_count} users")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
