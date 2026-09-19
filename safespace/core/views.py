from django.http import HttpResponse
from django.template import loader
from .models import Quest

def quest_list_manual(request):
    quests = Quest.objects.all()
    template = loader.get_template("core/quest_list.html")
    context = {"quests": quests}
    output = template.render(context, request)
    return HttpResponse(output)



from django.shortcuts import render

def quest_list_render(request):
    quests = Quest.objects.all()
    return render(request, "core/quest_list.html", {"quests": quests})