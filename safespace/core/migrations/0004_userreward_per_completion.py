from django.db import migrations, models


def award_past_completions(apps, schema_editor):
    """
    Give every completed quest its rewards, one copy per completion.

    Rewards that were added by hand (no unlocked_by_completion) are
    linked to a matching completion first, so they are not doubled.
    """

    QuestCompletion = apps.get_model("core", "QuestCompletion")
    UserReward = apps.get_model("core", "UserReward")

    completions = (
        QuestCompletion.objects
        .filter(completed_status=True)
        .order_by("quest_date", "id")
    )

    for completion in completions:
        for reward in completion.quest.possible_rewards.all():
            if UserReward.objects.filter(
                unlocked_by_completion=completion,
                reward=reward,
            ).exists():
                continue

            unlinked = UserReward.objects.filter(
                user_id=completion.user_id,
                reward=reward,
                unlocked_by_completion__isnull=True,
            ).first()

            if unlinked:
                unlinked.unlocked_by_completion = completion
                unlinked.save(update_fields=["unlocked_by_completion"])
            else:
                UserReward.objects.create(
                    user_id=completion.user_id,
                    reward=reward,
                    unlocked_by_completion=completion,
                )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_remove_quest_location_delete_location"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="userreward",
            name="unique_user_reward",
        ),
        migrations.AddConstraint(
            model_name="userreward",
            constraint=models.UniqueConstraint(
                fields=["unlocked_by_completion", "reward"],
                name="unique_reward_per_completion",
            ),
        ),
        migrations.RunPython(award_past_completions, migrations.RunPython.noop),
    ]
