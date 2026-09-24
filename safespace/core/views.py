#http
from django.http import HttpResponse
from django.template import loader
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import ListView

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
    quests = Quest.objects.all()

    return render(
        request,
        "core/quest_list.html",
        {"quests": quests}
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