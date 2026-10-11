#!/usr/bin/env python3
"""
Use 1: Python script - quest report with simple aggregations.

Calls the public SafeSpace API (no login needed), prints every quest,
then aggregates the data: totals per category and the most / least
popular quests.
"""

import os
from collections import defaultdict

import requests

API_URL = os.environ.get(
    "SAFESPACE_API_URL",
    "https://ilona.pythonanywhere.com/api/quest-summary/",
)


def fetch_quests():
    """GET the public API and return its JSON list."""
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def main():
    print(f"API: {API_URL}")

    try:
        quests = fetch_quests()
    except requests.RequestException as exc:
        print(f"Could not reach the API: {exc}")
        return 1

    print(f"Fetched {len(quests)} quests\n")

    # 1. The data we received
    print("Quests")
    print("-" * 66)
    print(f"{'Quest':<30} {'Category':<20} {'Users':>6}")
    for item in quests:
        print(f"{item['quest']:<30} {item['category']:<20} {item['user_count']:>6}")

    # 2. Aggregation: total completions per category
    per_category = defaultdict(int)
    for item in quests:
        per_category[item["category"]] += item["user_count"]

    total = sum(per_category.values())

    print("\nCompletions per category")
    print("-" * 66)
    for category, count in sorted(per_category.items(), key=lambda pair: -pair[1]):
        share = count / total * 100 if total else 0
        print(f"{category:<30} {count:>6}  ({share:.1f}%)")
    print(f"{'Total':<30} {total:>6}")

    # 3. Most and least popular quests (ties are all listed)
    counts = [item["user_count"] for item in quests]
    most = [item["quest"] for item in quests if item["user_count"] == max(counts)]
    least = [item["quest"] for item in quests if item["user_count"] == min(counts)]

    print("\nHighlights")
    print("-" * 66)
    print(f"Most popular:  {', '.join(most)} ({max(counts)} users)")
    print(f"Least popular: {', '.join(least)} ({min(counts)} users)")
    print(f"Average:       {total / len(quests):.1f} users per quest")

    not_started = [item["quest"] for item in quests if item["user_count"] == 0]
    if not_started:
        print(f"Nobody has tried yet: {', '.join(not_started)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
