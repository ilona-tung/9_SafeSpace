import json
from collections import Counter

from django import forms
from django.db import transaction
from django.db.models import Q

from .models import Journal, JournalSticker, Reward, UserReward


class JournalAdminForm(forms.ModelForm):
    """
    Admin form for Journal.

    Ensures that users can only decorate their journal entries
    with UserReward objects that belong to them.
    """

    class Meta:
        model = Journal
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        user = cleaned_data.get("user")
        decorations = cleaned_data.get("decorations")

        if user and decorations:
            invalid_rewards = decorations.exclude(user=user)

            if invalid_rewards.exists():
                raise forms.ValidationError(
                    "You can only use rewards earned by the journal's user."
                )

        return cleaned_data

class JournalEditorForm(forms.Form):
    """
    Saves a decorated journal page from the drag-and-drop editor.

    The editor sends the page layout as JSON:
        {"background": 2, "frame": null, "font": 5,
         "stickers": [{"reward": 1, "x": 80, "y": 30, "rotation": 8, "scale": 1}]}

    Users can only use rewards they own, and each placed sticker
    uses up one unused copy of that sticker.
    Unlimited rewards belong to everyone and are never used up.
    """

    MAX_STICKERS = 40

    content = forms.CharField(
        widget=forms.Textarea,
        error_messages={"required": "Write something before saving your entry."},
    )

    layout = forms.CharField(
        widget=forms.HiddenInput,
        required=False,
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_layout(self):
        raw = self.cleaned_data.get("layout") or "{}"

        try:
            layout = json.loads(raw)
        except ValueError:
            raise forms.ValidationError("The page layout could not be read.")

        if not isinstance(layout, dict) or not isinstance(layout.get("stickers", []), list):
            raise forms.ValidationError("The page layout could not be read.")

        owned = UserReward.objects.filter(user=self.user)

        cleaned = {}

        for slot in ["background", "frame", "font"]:
            reward_id = layout.get(slot)

            if reward_id is None:
                cleaned[slot] = None
                continue

            reward = Reward.objects.filter(
                Q(pk__in=owned.values("reward")) | Q(unlimited=True),
                pk=reward_id if isinstance(reward_id, int) else None,
                item_type=slot,
            ).first()

            if reward is None:
                raise forms.ValidationError(f"You can only use a {slot} you have earned.")

            cleaned[slot] = reward

        stickers = layout.get("stickers", [])

        if len(stickers) > self.MAX_STICKERS:
            raise forms.ValidationError(f"A page can have at most {self.MAX_STICKERS} stickers.")

        cleaned["stickers"] = []

        for sticker in stickers:
            try:
                cleaned["stickers"].append({
                    "reward_id": int(sticker["reward"]),
                    "x": clamp(float(sticker["x"]), 0, 100),
                    "y": clamp(float(sticker["y"]), 0, 100),
                    "rotation": int(float(sticker.get("rotation", 0))) % 360,
                    "scale": clamp(float(sticker.get("scale", 1)), 0.5, 2.5),
                })
            except (KeyError, TypeError, ValueError, OverflowError):
                raise forms.ValidationError("The page layout could not be read.")

        # Each sticker uses up one unused copy, except unlimited stickers
        needed = Counter(sticker["reward_id"] for sticker in cleaned["stickers"])
        unlimited = set(
            Reward.objects
            .filter(pk__in=needed, item_type="sticker", unlimited=True)
            .values_list("pk", flat=True)
        )

        for reward_id, count in needed.items():
            if reward_id in unlimited:
                continue

            available = owned.filter(
                reward_id=reward_id,
                reward__item_type="sticker",
                placement__isnull=True,
            ).count()

            if count > available:
                raise forms.ValidationError("You don't have enough copies of one of those stickers.")

        cleaned["unlimited"] = unlimited
        return cleaned

    @transaction.atomic
    def save(self):
        layout = self.cleaned_data["layout"]

        journal = Journal.objects.create(
            user=self.user,
            content=self.cleaned_data["content"],
            background=layout["background"],
            frame=layout["frame"],
            font=layout["font"],
        )

        unlimited = layout["unlimited"]

        for layer, sticker in enumerate(layout["stickers"]):
            copy = None

            if sticker["reward_id"] not in unlimited:
                copy = UserReward.objects.filter(
                    user=self.user,
                    reward_id=sticker["reward_id"],
                    placement__isnull=True,
                ).first()

            JournalSticker.objects.create(
                journal=journal,
                reward_id=sticker["reward_id"],
                user_reward=copy,
                x=sticker["x"],
                y=sticker["y"],
                rotation=sticker["rotation"],
                scale=sticker["scale"],
                layer=layer,
            )

        return journal


def clamp(value, low, high):
    if value != value:  # NaN
        raise ValueError("not a number")

    return min(high, max(low, value))
