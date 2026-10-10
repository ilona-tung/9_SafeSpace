#!/usr/bin/env python3
"""Notebook-friendly analysis of the SafeSpace completion timeline API.

This script fetches the protected timeline endpoint, turns the JSON into a
pandas DataFrame, and calculates summary statistics that are convenient for a
Jupyter notebook or quick exploration.
"""

import os
from pathlib import Path

import requests

try:
    import pandas as pd
    import matplotlib.pyplot as plt
except ImportError as exc:
    raise SystemExit(
        "This notebook-style analysis requires pandas and matplotlib. "
        f"Install them with: pip install pandas matplotlib\nOriginal error: {exc}"
    ) from exc

BASE_URL = os.environ.get("SAFESPACE_BASE_URL", "http://127.0.0.1:8000")
API_URL = f"{BASE_URL.rstrip('/')}/api/completion-timeline/"
OUTPUT_DIR = Path("data")
OUTPUT_DIR.mkdir(exist_ok=True)


def fetch_timeline():
    """Return the JSON payload from the protected timeline API."""
    # The endpoint is protected, so this example assumes the app is already
    # running in a logged-in browser session or the project uses a Django test
    # user context. For quick notebook use, you can also paste the JSON response
    # directly into a DataFrame.
    response = requests.get(API_URL, timeout=10)
    response.raise_for_status()
    return response.json()


def build_dataframe(raw_data):
    """Convert the API payload into a pandas DataFrame."""
    df = pd.DataFrame(raw_data)
    if df.empty:
        return df

    df["date"] = pd.to_datetime(df["date"])
    df["user_count"] = pd.to_numeric(df["user_count"], errors="coerce").fillna(0).astype(int)
    return df


def summarize(df):
    """Compute useful notebook-friendly statistics."""
    summary = {}

    if df.empty:
        return {
            "rows": 0,
            "unique_dates": 0,
            "unique_quests": 0,
            "total_users": 0,
            "avg_users_per_day_quest": 0,
            "max_users_in_a_day_quest": 0,
            "top_quest": None,
        }

    grouped_by_quest = df.groupby("quest")["user_count"].sum().sort_values(ascending=False)

    summary = {
        "rows": int(len(df)),
        "unique_dates": int(df["date"].nunique()),
        "unique_quests": int(df["quest"].nunique()),
        "total_users": int(df["user_count"].sum()),
        "avg_users_per_day_quest": round(float(df["user_count"].mean()), 2),
        "max_users_in_a_day_quest": int(df["user_count"].max()),
        "top_quest": grouped_by_quest.index[0] if not grouped_by_quest.empty else None,
        "quest_totals": grouped_by_quest,
    }
    return summary


def plot_results(df):
    """Create a small bar chart of quest totals for notebook display."""
    if df.empty:
        print("No timeline data available to plot.")
        return

    quest_totals = df.groupby("quest")["user_count"].sum().sort_values(ascending=False)
    ax = quest_totals.plot(kind="bar", figsize=(10, 5), color="steelblue")
    ax.set_title("Total users completing each quest")
    ax.set_xlabel("Quest")
    ax.set_ylabel("Users")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.show()


def main():
    try:
        raw_data = fetch_timeline()
    except requests.RequestException as exc:
        print(f"Could not load timeline data from {API_URL}: {exc}")
        print("Make sure the Django app is running and you are authenticated for this endpoint.")
        return 1

    df = build_dataframe(raw_data)
    if df.empty:
        print("The timeline API returned no data.")
        return 0

    stats = summarize(df)
    print("Timeline API summary")
    print("-" * 40)
    print(f"Rows: {stats['rows']}")
    print(f"Unique dates: {stats['unique_dates']}")
    print(f"Unique quests: {stats['unique_quests']}")
    print(f"Total user completions: {stats['total_users']}")
    print(f"Average users per day/quest: {stats['avg_users_per_day_quest']}")
    print(f"Max users in a day/quest: {stats['max_users_in_a_day_quest']}")
    print(f"Top quest: {stats['top_quest']}")
    print()
    print("Quest totals:")
    print(stats["quest_totals"])

    csv_path = OUTPUT_DIR / "completion_timeline_analysis.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nSaved analysis data to {csv_path}")

    # Notebook-friendly plot: uncomment when running inside a notebook or use
    # this function manually in a Jupyter cell.
    # plot_results(df)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
