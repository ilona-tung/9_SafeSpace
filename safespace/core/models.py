from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse


class Quest(models.Model):
    """
    Quests for the users to complete, sorted by categories.
    """

    CATEGORY_CHOICES = [
        ("learning", "Learning"),
        ("budgeting", "Budgeting"),
        ("diet", "Diet & Wellness"),
        ("social", "Social"),
        ("general", "General Self-Care"),
        ("exploration", "Exploration"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=120)

    description = models.TextField(blank=True)

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )

    custom_category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Only used if category is set to 'Other'."
    )

    class Meta:
        ordering = ["category", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["title", "category"],
                name="unique_quest_title_per_category"
            )
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("quest_detail", kwargs={"pk": self.pk})

    def display_category(self):
        if self.category == "other" and self.custom_category:
            return self.custom_category

        return self.get_category_display()


class QuestCompletion(models.Model):
    """
    Records that a specific user selected a specific quest on a specific
    date and tracks whether the quest was completed.
    A completed quest can automatically unlock rewards associated with that quest.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="quest_completions"
    )

    quest = models.ForeignKey(
        Quest,
        on_delete=models.PROTECT,
        related_name="completions",
        help_text=(
            "Protected so historical completion records are preserved "
            "if a quest is deleted."
        )
    )

    completed_status = models.BooleanField(
        default=False
    )

    quest_date = models.DateField(
        help_text="Date the user chose or started this quest."
    )

    completed_date = models.DateField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-quest_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "quest", "quest_date"],
                name="unique_completion_per_user_per_day"
            )
        ]

    def __str__(self):
        return f"{self.user} — {self.quest} ({self.quest_date})"

    def award_rewards(self):
        """
        Award every reward associated with this quest to the user
        when the quest has been completed.
        """

        if not self.completed_status:
            return

        rewards = self.quest.possible_rewards.all()

        for reward in rewards:
            UserReward.objects.get_or_create(
                user=self.user,
                reward=reward,
                defaults={
                    "unlocked_by_completion": self
                }
            )


class Reward(models.Model):
    """
    Rewards such as a sticker, font, frame, or background, can be associated
    with quests that may unlock them, and can be used in decorating journals
    """

    ITEM_TYPE_CHOICES = [
        ("sticker", "Sticker"),
        ("font", "Font"),
        ("frame", "Frame"),
        ("background", "Background"),
    ]

    name = models.CharField(
        max_length=100
    )

    item_type = models.CharField(
        max_length=20,
        choices=ITEM_TYPE_CHOICES
    )

    quests = models.ManyToManyField(
        Quest,
        blank=True,
        related_name="possible_rewards",
        help_text="Quests that can potentially unlock this reward."
    )

    class Meta:
        ordering = ["item_type", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "item_type"],
                name="unique_reward_definition"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_item_type_display()})"


class UserReward(models.Model):
    """
    The user's reward collection when they completed the quests.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="rewards",
        help_text="The user who earned this reward."
    )

    reward = models.ForeignKey(
        Reward,
        on_delete=models.PROTECT,
        related_name="earned_by",
        help_text="The reward earned by the user."
    )

    unlocked_by_completion = models.ForeignKey(
        QuestCompletion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unlocked_rewards",
        limit_choices_to={"completed_status": True},
        help_text="The completed quest that unlocked this reward."
    )

    unlocked_time = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-unlocked_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "reward"],
                name="unique_user_reward"
            )
        ]

    def __str__(self):
        return f"{self.user} — {self.reward}"

    def clean(self):
        """
        Validate that the reward belongs to the user, the quest was
        completed, and the completed quest is allowed to unlock the corresponding reward.
        """

        if self.unlocked_by_completion:
            if self.unlocked_by_completion.user_id != self.user_id:
                raise ValidationError(
                    "The quest completion must belong to the same user "
                    "who receives the reward."
                )

            if not self.unlocked_by_completion.completed_status:
                raise ValidationError(
                    "The quest completion must be completed before "
                    "it can unlock a reward."
                )

            if not self.reward.quests.filter(
                id=self.unlocked_by_completion.quest_id
            ).exists():
                raise ValidationError(
                    f"The quest '{self.unlocked_by_completion.quest}' "
                    f"cannot unlock the reward '{self.reward}'. "
                    "Please select a reward associated with this quest."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Journal(models.Model):
    """
    Users document and decorate their journals with the rewards they received when completing quests here.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="journals"
    )

    content = models.TextField()

    time = models.DateTimeField(
        auto_now_add=True
    )

    decorations = models.ManyToManyField(
        UserReward,
        blank=True,
        related_name="used_in_journals",
        help_text="Cosmetic rewards earned by this user and used to decorate the journal."
    )

    class Meta:
        ordering = ["-time"]

    def __str__(self):
        return f"{self.user} — {self.time:%Y-%m-%d %H:%M}"


class Forum(models.Model):
    """
    Represents a community for the users to interact and connect with each other.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="forum_posts"
    )

    group = models.CharField(
        max_length=120,
        help_text="Community or group that this post belongs to."
    )

    content = models.TextField()

    location = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional city or area associated with the post."
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.group} ({self.created_at:%Y-%m-%d}) — by {self.user}"


class Friendship(models.Model):
    """
    Represents a friendship request or connection between two users.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
    ]

    user_from = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friendship_requests_sent"
    )

    user_to = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="friendship_requests_received"
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="pending"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user_from", "user_to"],
                name="unique_friend_request"
            )
        ]

    def __str__(self):
        return (
            f"{self.user_from} -> "
            f"{self.user_to} ({self.status})"
        )

    def clean(self):
        """
        Prevent a user from sending a friendship request to themselves.
        """

        if self.user_from_id == self.user_to_id:
            raise ValidationError(
                "A user cannot send a friendship request to themselves."
            )