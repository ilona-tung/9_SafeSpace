#!/usr/bin/env python3
"""
Use 2: Statistical analysis in a notebook (pandas).

Loads the public SafeSpace API into a pandas DataFrame and calculates
summary statistics, each quest's share, and totals per category,
then draws a bar chart.

"""

# %% 1. Load the public API into a DataFrame
import os

import matplotlib.pyplot as plt
import pandas as pd
import requests

API_URL = os.environ.get(
    "SAFESPACE_API_URL",
    "https://ilona.pythonanywhere.com/api/quest-summary/",
)

response = requests.get(API_URL, timeout=10)
response.raise_for_status()

df = pd.DataFrame(response.json())
print(f"API: {API_URL}")
print(f"Loaded {len(df)} rows with columns {list(df.columns)}\n")
print(df.to_string(index=False))

# %% 2. Summary statistics of completions per quest
stats = df["user_count"].describe()

print("\nSummary statistics (users per quest)")
print(f"Quests:   {int(stats['count'])}")
print(f"Total:    {df['user_count'].sum()}")
print(f"Mean:     {stats['mean']:.2f}")
print(f"Median:   {df['user_count'].median():.1f}")
print(f"Std dev:  {stats['std']:.2f}")
print(f"Min:      {int(stats['min'])}")
print(f"Max:      {int(stats['max'])}")

# %% 3. Each quest's share of all completions
df["share_%"] = (df["user_count"] / df["user_count"].sum() * 100).round(1)
df["vs_average"] = (df["user_count"] - df["user_count"].mean()).round(1)

print("\nQuests ranked by popularity")
print(df.sort_values("user_count", ascending=False).to_string(index=False))

# %% 4. Totals per category
by_category = (
    df.groupby("category")
    .agg(quests=("quest", "count"), total_users=("user_count", "sum"), avg_users=("user_count", "mean"))
    .round(1)
    .sort_values("total_users", ascending=False)
)

print("\nPer category")
print(by_category.to_string())

# %% 5. Chart: users per quest, colored by category
colors = ["#324841", "#ADC2AF", "#E8B4B8", "#9C95C9", "#F2C46D", "#7FB3D5", "#8A8490"]
category_color = {
    category: colors[i % len(colors)]
    for i, category in enumerate(sorted(df["category"].unique()))
}

ranked = df.sort_values("user_count", ascending=False)

fig, ax = plt.subplots(figsize=(9, 4.5))
ax.bar(ranked["quest"], ranked["user_count"], color=[category_color[c] for c in ranked["category"]])
ax.axhline(df["user_count"].mean(), color="#392D35", linestyle="--", linewidth=1, label="Average")
ax.set_title("Users who completed each SafeSpace quest")
ax.set_ylabel("Users")
ax.tick_params(axis="x", rotation=30)
plt.setp(ax.get_xticklabels(), ha="right")

handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in category_color.values()]
ax.legend(handles + [ax.get_lines()[0]], list(category_color) + ["Average"], fontsize=8)

fig.tight_layout()
fig.savefig("quest_statistics.png", dpi=150)
print("\nSaved chart to quest_statistics.png")
plt.show()
