import django.db.models.deletion
from django.db import migrations, models


# Sticker designs: (reward name, file, quest that unlocks it)
STICKERS = [
    ("Stay Hydrated Sticker", "rewards/stickers/StayHydrated.png", "Drink 2000 c.c. of water"),
    ("Take a Walk Sticker", "rewards/stickers/Walk.png", "Take a walk"),
    ("Read a Book Sticker", "rewards/stickers/Read.png", "Read a book"),
    ("Say Hi Sticker", "rewards/stickers/SayHi.png", "Say hi to an old friend"),
    ("Sweet Dreams Sticker", "rewards/stickers/SleepEarly.png", "Go to bed before 10 p.m."),
    ("Day Dreamer Sticker", "rewards/stickers/GoToBed.png", "Observe the clouds"),
]

WELCOME_STICKER = ("You're a Star Sticker", "rewards/stickers/NewUser.png")


def fill_placement_rewards(apps, schema_editor):
    """
    Existing placements all used a copy, so copy its reward over.
    """

    JournalSticker = apps.get_model("core", "JournalSticker")

    for placement in JournalSticker.objects.select_related("user_reward"):
        placement.reward_id = placement.user_reward.reward_id
        placement.save(update_fields=["reward"])


def add_stickers(apps, schema_editor):
    """
    Add the new sticker designs and give users one copy for every
    quest they already completed (like migration 0004).
    """

    Quest = apps.get_model("core", "Quest")
    QuestCompletion = apps.get_model("core", "QuestCompletion")
    Reward = apps.get_model("core", "Reward")
    UserReward = apps.get_model("core", "UserReward")

    for name, asset, quest_title in STICKERS:
        reward, _ = Reward.objects.update_or_create(
            name=name,
            item_type="sticker",
            defaults={"asset": asset},
        )

        quest = Quest.objects.filter(title=quest_title).first()

        if quest is None:
            continue

        reward.quests.add(quest)

        for completion in QuestCompletion.objects.filter(quest=quest, completed_status=True):
            UserReward.objects.get_or_create(
                user_id=completion.user_id,
                reward=reward,
                unlocked_by_completion=completion,
            )

    name, asset = WELCOME_STICKER
    Reward.objects.update_or_create(
        name=name,
        item_type="sticker",
        defaults={"asset": asset, "unlimited": True},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_journal_decorating"),
    ]

    operations = [
        migrations.AddField(
            model_name="reward",
            name="unlimited",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Every user always has this reward and can use it "
                    "as many times as they like (e.g. the welcome sticker)."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="journalsticker",
            name="user_reward",
            field=models.OneToOneField(
                blank=True,
                help_text="The sticker copy used up by this placement (empty for unlimited stickers).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="placement",
                to="core.userreward",
            ),
        ),
        migrations.AddField(
            model_name="journalsticker",
            name="reward",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="placements",
                to="core.reward",
            ),
        ),
        migrations.RunPython(fill_placement_rewards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="journalsticker",
            name="reward",
            field=models.ForeignKey(
                help_text="The sticker shown on the page.",
                limit_choices_to={"item_type": "sticker"},
                on_delete=django.db.models.deletion.PROTECT,
                related_name="placements",
                to="core.reward",
            ),
        ),
        migrations.RunPython(add_stickers, migrations.RunPython.noop),
    ]
