from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.shortcuts import get_object_or_404, render
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import Quest, Reward, Journal

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO


def home(request):
    return render(request, "core/home.html")


def http_response_example(request):
    return HttpResponse(
        "SafeSpace response example\n"
        "message: Hello from SafeSpace\n"
        "quest_count: 3\n",
        content_type="text/plain",
    )


def json_response_example(request):
    return JsonResponse({
        "message": "Hello from SafeSpace",
        "quest_count": 3,
    })


class RegisterView(FormView):
    template_name = "core/register.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("home")

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


def quest_list_manual(request):
    quests = Quest.objects.all()

    template = loader.get_template("core/quest_list.html")

    context = {
        "quests": quests
    }

    output = template.render(context, request)

    return HttpResponse(output)


def quest_list_context(query, quests):
    return {
        "quests": quests,
        "query": query,
        "total_quests": Quest.objects.count(),
        "quest_summary": Quest.objects.annotate(
            user_count=Count(
                "completions__user",
                filter=Q(completions__completed_status=True),
                distinct=True,
            )
        ),
    }


def quest_list_render(request):
    # GET search
    query = request.GET.get("q", "")

    quests = Quest.objects.all()

    if query:
        quests = quests.filter(
            title__icontains=query
        )

    return render(
        request,
        "core/quest_list.html",
        quest_list_context(query, quests)
    )

def journal_list(request):
    journals = Journal.objects.all()

    return render(
        request,
        "core/journal_list.html",
        {"journals": journals}
    )

def quest_completion_chart(request):
    """
    Generate a vertical bar chart showing how many
    distinct users have completed each quest.
    """

    # ORM aggregation
    quest_summary = Quest.objects.annotate(
        user_count=Count(
            "completions__user",
            distinct=True
        )
    )

    # Prepare chart data
    quest_names = [
        quest.title
        for quest in quest_summary
    ]

    user_counts = [
        quest.user_count
        for quest in quest_summary
    ]

    # Create a small vertical bar chart
    fig, ax = plt.subplots(
        figsize=(7, 4.5)
    )

    # One consistent color
    ax.bar(
        quest_names,
        user_counts,
        color="#324841"
    )

    # Title and labels
    ax.set_title(
        "Users Who Completed Each Quest"
    )

    ax.set_xlabel(
        "Quest"
    )

    ax.set_ylabel(
        "Number of Users"
    )

    # Rotate long quest names
    plt.xticks(rotation=35, ha="right",fontsize=8)

    # Remove unnecessary borders
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Make sure everything fits
    plt.tight_layout()

    # Store image in memory
    buffer = BytesIO()

    plt.savefig(
        buffer,
        format="png",
        bbox_inches="tight"
    )

    # Close figure to release memory
    plt.close(fig)

    # Return PNG
    buffer.seek(0)

    return HttpResponse(
        buffer.getvalue(),
        content_type="image/png"
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


def user_list(request):

    # GET search
    query = request.GET.get("q", "")

    # Alphabetical ordering
    users = User.objects.all().order_by("first_name","last_name","username")

    if query:
        users = users.filter(
            Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(username__icontains=query)
        )

    # Relationship-spanning query:
    # Find users who have completed at least one quest
    users_with_completions = User.objects.filter(
        quest_completions__quest__isnull=False
    ).distinct().order_by("first_name","last_name","username")

    return render(
        request,
        "core/users.html",
        {
            "users": users,
            "query": query,
            "users_with_completions": users_with_completions,
        }
    )


def user_detail(request, pk):

    user = get_object_or_404(
        User,
        pk=pk
    )

    # Only show completed quests
    completed_quests = Quest.objects.filter(
        completions__user=user,
        completions__completed_status=True
    ).distinct().order_by(
        "category",
        "title"
    )

    return render(
        request,
        "core/user_detail.html",
        {
            "user": user,
            "completed_quests": completed_quests,
        }
    )


class QuestListBaseView(View):
    def get(self, request):
        query = request.GET.get("q", "")
        quests = Quest.objects.all()
        if query:
            quests = quests.filter(title__icontains=query)

        return render(
            request,
            "core/quest_list.html",
            quest_list_context(query, quests)
        )


class QuestListGenericView(ListView):
    model = Quest
    template_name = "core/quest_list.html"
    context_object_name = "quests"

    def get_queryset(self):
        query = self.request.GET.get("q", "")
        quests = super().get_queryset()
        if query:
            quests = quests.filter(title__icontains=query)
        return quests

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get("q", "")
        context.update(quest_list_context(query, context["quests"]))
        return context