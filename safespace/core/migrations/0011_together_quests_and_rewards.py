from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# Together quests: done with a friend (one invites, the other accepts).
# (title, description)
TOGETHER_QUESTS = [
    ("Swap a book or song recommendation", "Share a book or song you love with a friend, and ask for one back."),
    ("Walk for 30 minutes together", "Go for a 30-minute walk with a friend and catch up."),
    ("Have lunch together", "Share a meal with a friend, in person or on a video call."),
    ("Watch a movie together", "Pick a movie, watch it with a friend, then talk about it."),
]

# New rewards (placeholder art in static/rewards/, replaceable by file name)
# (name, item_type, asset)
NEW_REWARDS = [
    ("Sunset Background", "background", "rewards/backgrounds/sunset.svg"),
    ("Notebook Grid Background", "background", "rewards/backgrounds/notebook.svg"),
    ("Coins Background", "background", "rewards/backgrounds/coins.svg"),
    ("Fruit Background", "background", "rewards/backgrounds/fruit.svg"),
    ("Map Background", "background", "rewards/backgrounds/map.svg"),
    ("Leaf Frame", "frame", "rewards/frames/leaf.svg"),
    ("Star Frame", "frame", "rewards/frames/star.svg"),
    ("Friendship Frame", "frame", "rewards/frames/friendship.svg"),
    ("Patrick Hand Font", "font", "rewards/fonts/patrick-hand.woff2"),
    ("Indie Flower Font", "font", "rewards/fonts/indie-flower.woff2"),
    ("Shadows Into Light Font", "font", "rewards/fonts/shadows-into-light.woff2"),
    ("Book Swap Sticker", "sticker", "rewards/stickers/BookSwap.svg"),
    ("Walk Together Sticker", "sticker", "rewards/stickers/WalkTogether.svg"),
    ("Lunch Together Sticker", "sticker", "rewards/stickers/LunchTogether.svg"),
    ("Movie Night Sticker", "sticker", "rewards/stickers/MovieNight.svg"),
]

# Which quest unlocks which rewards (quests that already had rewards keep them)
# quest title: [(reward name, item_type), ...]
QUEST_REWARDS = {
    # General Self-Care
    "Take 3 deep breaths": [("Sunset Background", "background")],
    "Take a 10-minute screen break": [("Sunset Background", "background")],
    "Listen to a favorite song": [("Indie Flower Font", "font")],
    "Tidy your desk": [("Cloud Background", "background")],
    "Plan tomorrow's to-do list": [("Patrick Hand Font", "font")],

    # Diet & Wellness
    "Eat a piece of fruit": [("Fruit Background", "background")],
    "Cook a simple meal": [("Fruit Background", "background")],
    "Stretch for 5 minutes": [("Leaf Frame", "frame")],

    # Exploration
    "Take a different route home": [("Map Background", "background")],
    "Try a food you have never had": [("Map Background", "background")],
    "Visit a new café or park": [("Nature Background", "background"), ("Leaf Frame", "frame")],

    # Learning
    "Learn 5 new words in another language": [("Patrick Hand Font", "font")],
    "Study for 25 minutes with a timer": [("Notebook Grid Background", "background")],
    "Watch a short educational video": [("Star Frame", "frame")],

    # Budgeting
    "Set a small savings goal": [("Coins Background", "background")],
    "Skip one unplanned purchase": [("Star Frame", "frame")],
    "Write down today's spending": [("Shadows Into Light Font", "font")],

    # Social
    "Call a family member": [("Smily face frame", "frame")],
    "Send a kind message to a classmate": [("Indie Flower Font", "font")],
    "Thank someone today": [("Smily face frame", "frame")],

    # Together
    "Swap a book or song recommendation": [("Book Swap Sticker", "sticker"), ("Friendship Frame", "frame")],
    "Walk for 30 minutes together": [("Walk Together Sticker", "sticker"), ("Friendship Frame", "frame")],
    "Have lunch together": [("Lunch Together Sticker", "sticker"), ("Friendship Frame", "frame")],
    "Watch a movie together": [("Movie Night Sticker", "sticker"), ("Friendship Frame", "frame")],
}


def add_quests_and_rewards(apps, schema_editor):
    Quest = apps.get_model("core", "Quest")
    Reward = apps.get_model("core", "Reward")

    for title, description in TOGETHER_QUESTS:
        Quest.objects.get_or_create(
            title=title,
            category="together",
            defaults={"description": description},
        )

    for name, item_type, asset in NEW_REWARDS:
        Reward.objects.get_or_create(
            name=name,
            item_type=item_type,
            defaults={"asset": asset},
        )

    # Skips quests or rewards that don't exist in this database
    for title, rewards in QUEST_REWARDS.items():
        quest = Quest.objects.filter(title=title).first()

        if quest is None:
            continue

        for name, item_type in rewards:
            reward = Reward.objects.filter(name=name, item_type=item_type).first()

            if reward is not None:
                reward.quests.add(quest)


def remove_quests_and_rewards(apps, schema_editor):
    """
    Removes the links, then the new rewards nobody earned
    and the Together quests nobody completed.
    """

    Quest = apps.get_model("core", "Quest")
    Reward = apps.get_model("core", "Reward")

    for title, rewards in QUEST_REWARDS.items():
        for name, item_type in rewards:
            for reward in Reward.objects.filter(name=name, item_type=item_type):
                reward.quests.remove(*Quest.objects.filter(title=title))

    for name, item_type, _ in NEW_REWARDS:
        Reward.objects.filter(name=name, item_type=item_type, earned_by__isnull=True).delete()

    Quest.objects.filter(
        category="together",
        completions__isnull=True,
        together_invites__isnull=True,
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0010_profile"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="quest",
            name="category",
            field=models.CharField(
                choices=[
                    ("learning", "Learning"),
                    ("budgeting", "Budgeting"),
                    ("diet", "Diet & Wellness"),
                    ("social", "Social"),
                    ("general", "General Self-Care"),
                    ("exploration", "Exploration"),
                    ("together", "Together"),
                    ("other", "Other"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="TogetherInvite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted")], default="pending", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("from_completion", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="core.questcompletion")),
                ("from_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="together_invites_sent", to=settings.AUTH_USER_MODEL)),
                ("quest", models.ForeignKey(limit_choices_to={"category": "together"}, on_delete=django.db.models.deletion.PROTECT, related_name="together_invites", to="core.quest")),
                ("to_completion", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to="core.questcompletion")),
                ("to_user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="together_invites_received", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status", "pending")),
                        fields=("from_user", "to_user", "quest"),
                        name="one_pending_together_invite",
                    )
                ],
            },
        ),
        migrations.RunPython(add_quests_and_rewards, remove_quests_and_rewards),
    ]
