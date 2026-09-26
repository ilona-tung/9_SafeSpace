# P1-A3 Section 4 — Matplotlib Visualization

## 1. ORM-based aggregation
`views.py` line 73
Used Django ORM aggregation to count the distinct users who completed each quest:

```python
quest_summary = Quest.objects.annotate(
    user_count=Count("completions__user", distinct=True)
)
```

Then extracted the quest names and corresponding user counts:

```python
quest_names = [quest.title for quest in quest_summary]
user_counts = [quest.user_count for quest in quest_summary]
```

## 2. Matplotlib Bar Chart
`views.py` line 92
We created a vertical bar chart using Matplotlib:

```python
fig, ax = plt.subplots(figsize=(7, 4.5))

ax.bar(
    quest_names,
    user_counts,
    color="#324841"
)

ax.set_title("Users Who Completed Each Quest")
ax.set_xlabel("Quest")
ax.set_ylabel("Number of Users")

plt.xticks(rotation=35, ha="right", fontsize=8)

ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
```

## 3. Image Endpoint
`urls.py` line 15
The chart is called quest-completion-chart.png, and can also be seen in http://127.0.0.1:8000/quests/quest-completion-chart.png

```python
path(
    "quests/quest-completion-chart.png",
    views.quest_completion_chart,
    name="quest_completion_chart",
),
```

## 4. BytesIO Efficient Implementation
`views.py` line 131
```python
buffer = BytesIO()

plt.savefig(
    buffer,
    format="png",
    bbox_inches="tight"
)

plt.close(fig)

buffer.seek(0)

return HttpResponse(
    buffer.getvalue(),
    content_type="image/png"
)
```
