# http
from django.http import HttpResponse
from django.template import loader
from .models import Quest, Reward


# Home page
from django.shortcuts import render

def home(request):
    return render(request, "core/home.html")


# Manual template loading
def quest_list_manual(request):
    quests = Quest.objects.all()
    template = loader.get_template("core/quest_list.html")
    context = {"quests": quests}
    output = template.render(context, request)
    return HttpResponse(output)


# Render
def quest_list_render(request):
    quests = Quest.objects.all()
    return render(request, "core/quest_list.html", {"quests": quests})


def reward_list_render(request):
    rewards = Reward.objects.all()
    return render(request, "core/reward_list.html", {"rewards": rewards})


# Base CBV
from django.views import View

class QuestListBaseView(View):
    def get(self, request):
        return render(
            request,
            'core/quest_list.html',
            context={'quests': Quest.objects.all()}
        )


# Generic CBV
from django.views.generic import ListView

class QuestListGenericView(ListView):
    model = Quest
    template_name = 'core/quest_list.html'
    context_object_name = 'quests'