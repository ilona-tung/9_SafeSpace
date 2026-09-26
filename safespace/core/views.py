from django.http import HttpResponse
from django.template import loader
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import ListView
from django.db.models import Count
from django.contrib.auth.models import User

from .models import Quest, Reward


def home(request):
    return render(request, "core/home.html")


def quest_list_manual(request):
    quests = Quest.objects.all()

    template = loader.get_template("core/quest_list.html")

    context = {
        "quests": quests
    }

    output = template.render(context, request)

    return HttpResponse(output)


def quest_list_render(request):
    # GET search
    query = request.GET.get("q", "")

    quests = Quest.objects.all()

    if query:
        quests = quests.filter(
            title__icontains=query
        )

    # Total number of quests
    total_quests = Quest.objects.count()

    # Grouped aggregation:
    # Count how many distinct users have completed each quest
    quest_summary = Quest.objects.annotate(
        user_count=Count(
            "completions__user",
            distinct=True
        )
    )

    context = {
        "quests": quests,
        "query": query,
        "total_quests": total_quests,
        "quest_summary": quest_summary,
    }

    return render(
        request,
        "core/quest_list.html",
        context
    )


def reward_list_render(request):
    rewards = Reward.objects.all()

    return render(
        request,
        "core/reward_list.html",
        {"rewards": rewards}
    )


def quest_detail(request, pk):
    quest = get_object_or_404(
        Quest,
        pk=pk
    )

    return render(
        request,
        "core/quest_detail.html",
        {"quest": quest}
    )

# user_list
def user_list(request):
    # POST search
    query = request.POST.get("q", "")

    users = User.objects.all()

    if query:
        users = users.filter(
            username__icontains=query
        )

    # Relationship-spanning query:
    # Find users who have completed at least one quest
    users_with_completions = User.objects.filter(
        quest_completions__quest__isnull=False
    ).distinct()

    return render(
        request,
        "core/users.html",
        {
            "users": users,
            "query": query,
            "users_with_completions": users_with_completions,
        }
    )


class QuestListBaseView(View):
    def get(self, request):
        return render(
            request,
            "core/quest_list.html",
            context={
                "quests": Quest.objects.all()
            }
        )


class QuestListGenericView(ListView):
    model = Quest
    template_name = "core/quest_list.html"
    context_object_name = "quests"