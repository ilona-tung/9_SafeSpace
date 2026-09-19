from django.contrib import admin
from django.contrib.auth.models import Group

from .models import (
    Quest,
    QuestCompletion,
    Reward,
    Journal,
    Forum,
    Friendship,
    UserReward,
)

from .forms import JournalAdminForm

admin.site.unregister(Group)


admin.site.register(Quest)
admin.site.register(QuestCompletion)
admin.site.register(Reward)


@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    form = JournalAdminForm


admin.site.register(Forum)
admin.site.register(Friendship)
admin.site.register(UserReward)