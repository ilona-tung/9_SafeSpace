from django.db import migrations


# More small, doable quests so the AI suggestions have real choices.
# (title, category, description)
NEW_QUESTS = [
    # Diet & Wellness
    ("Stretch for 5 minutes", "diet", "Loosen up your neck, shoulders and back."),
    ("Eat a piece of fruit", "diet", "A small, fresh snack for your body."),
    ("Cook a simple meal", "diet", "Make something warm for yourself, however simple."),

    # General Self-Care
    ("Take 3 deep breaths", "general", "Breathe in slowly, hold, and breathe out. Repeat 3 times."),
    ("Take a 10-minute screen break", "general", "Put your phone and laptop away and rest your eyes."),
    ("Tidy your desk", "general", "A clear space can help a busy mind."),
    ("Listen to a favorite song", "general", "Give yourself a few minutes of music you love."),
    ("Plan tomorrow's to-do list", "general", "Write down 3 things for tomorrow so you can let them go tonight."),

    # Learning
    ("Learn 5 new words in another language", "learning", "Pick any language you are curious about."),
    ("Watch a short educational video", "learning", "Learn one new thing in under 15 minutes."),
    ("Study for 25 minutes with a timer", "learning", "One focused session, then a short break."),

    # Social
    ("Send a kind message to a classmate", "social", "A short message can brighten someone's day."),
    ("Call a family member", "social", "Catch up with someone who cares about you."),
    ("Thank someone today", "social", "Tell someone what you appreciate about them."),

    # Budgeting
    ("Write down today's spending", "budgeting", "Notice where your money went, without judging."),
    ("Skip one unplanned purchase", "budgeting", "Wait a day before buying something you did not plan."),
    ("Set a small savings goal", "budgeting", "Choose an amount and a reason to save for."),

    # Exploration
    ("Visit a new café or park", "exploration", "Discover a new place nearby."),
    ("Take a different route home", "exploration", "See your neighborhood from a new angle."),
    ("Try a food you have never had", "exploration", "Be curious and taste something new."),
]


def add_quests(apps, schema_editor):
    Quest = apps.get_model("core", "Quest")

    for title, category, description in NEW_QUESTS:
        Quest.objects.get_or_create(
            title=title,
            category=category,
            defaults={"description": description},
        )


def remove_quests(apps, schema_editor):
    """
    Only removes new quests that nobody has completed yet.
    """

    Quest = apps.get_model("core", "Quest")

    for title, category, _ in NEW_QUESTS:
        Quest.objects.filter(title=title, category=category, completions__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_journal_summary"),
    ]

    operations = [
        migrations.RunPython(add_quests, remove_quests),
    ]
