from django import forms
from .models import Journal


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