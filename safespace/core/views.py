# http
from django.http import HttpResponse
from django.template import loader
from .models import Quest, Reward

def quest_list_manual(request):
    quests = Quest.objects.all()
    template = loader.get_template("core/quest_list.html")
    context = {"quests": quests}
    output = template.render(context, request)
    return HttpResponse(output)


# render
from django.shortcuts import render

def quest_list_render(request):
    quests = Quest.objects.all()
    return render(request, "core/quest_list.html", {"quests": quests})

def reward_list_render(request):
    rewards = Reward.objects.all()
    return render(request, "core/reward_list.html", {"rewards": rewards})


# base cbv
from django.views import View

class QuestListBaseView(View):
    def get(self, request):
        return render(
            request,
            'core/quest_list.html',
            context={'quests': Quest.objects.all()}
        )

# generic cbv
from django.views.generic import ListView

class QuestListGenericView(ListView):
    model = Quest
    template_name = 'core/quest_list.html'
    context_object_name = 'quests'

