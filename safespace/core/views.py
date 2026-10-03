from datetime import date
import json

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

from .models import Quest, Reward, Journal, QuestCompletion

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO

import vl_convert as vlc
import requests

# ============================================================
# Home
# ============================================================

def home(request):
    return render(request, "core/home.html")


# ============================================================
# Response Examples
# ============================================================

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


# ============================================================
# Part 1.1 - Database-backed JSON API
# ============================================================

def quest_summary_api(request):
    """
    Return the number of distinct users who completed
    each quest.
    """

    if request.method != "GET":
        return JsonResponse(
            {"error": "GET requests only."},
            status=405
        )

    quest_summary = Quest.objects.annotate(
        user_count=Count(
            "completions__user",
            filter=Q(
                completions__completed_status=True
            ),
            distinct=True
        )
    )

    data = [
        {
            "quest": quest.title,
            "user_count": quest.user_count,
        }
        for quest in quest_summary
    ]

    return JsonResponse(data, safe=False)


# ============================================================
# Part 1.2 - Database-backed JSON API for Line Chart
# ============================================================

def completion_timeline_api(request):
    """
    Return the number of distinct users who completed
    each quest on each day during September 2026.
    """

    if request.method != "GET":
        return JsonResponse(
            {"error": "GET requests only."},
            status=405
        )

    start_date = date(2026, 9, 25)
    end_date = date(2026, 10, 1)

    completion_summary = (
        QuestCompletion.objects
        .filter(
            completed_status=True,
            completed_date__range=(start_date, end_date)
        )
        .values(
            "completed_date",
            "quest__title"
        )
        .annotate(
            user_count=Count(
                "user",
                distinct=True
            )
        )
        .order_by(
            "completed_date",
            "quest__title"
        )
    )

    data = [
        {
            "date": item["completed_date"].isoformat(),
            "quest": item["quest__title"],
            "user_count": item["user_count"],
        }
        for item in completion_summary
    ]

    return JsonResponse(data, safe=False)


# ============================================================
# Registration
# ============================================================

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


# ============================================================
# Quest List
# ============================================================

def quest_list_manual(request):
    quests = Quest.objects.all()

    template = loader.get_template(
        "core/quest_list.html"
    )

    context = {
        "quests": quests
    }

    output = template.render(
        context,
        request
    )

    return HttpResponse(output)


def quest_list_context(query, quests):
    return {
        "quests": quests,
        "query": query,
        "total_quests": Quest.objects.count(),
        "quest_summary": Quest.objects.annotate(
            user_count=Count(
                "completions__user",
                filter=Q(
                    completions__completed_status=True
                ),
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
        quest_list_context(
            query,
            quests
        )
    )


# ============================================================
# Journals
# ============================================================

def journal_list(request):
    journals = Journal.objects.all()

    return render(
        request,
        "core/journal_list.html",
        {
            "journals": journals
        }
    )


# ============================================================
# Existing Matplotlib Chart
# ============================================================

def quest_completion_chart(request):
    """
    Generate a vertical bar chart showing how many
    distinct users have completed each quest.
    """

    quest_summary = Quest.objects.annotate(
        user_count=Count(
            "completions__user",
            distinct=True
        )
    )

    quest_names = [
        quest.title
        for quest in quest_summary
    ]

    user_counts = [
        quest.user_count
        for quest in quest_summary
    ]

    fig, ax = plt.subplots(
        figsize=(7, 4.5)
    )

    ax.bar(
        quest_names,
        user_counts,
        color="#324841"
    )

    ax.set_title(
        "Users Who Completed Each Quest"
    )

    ax.set_xlabel(
        "Quest"
    )

    ax.set_ylabel(
        "Number of Users"
    )

    plt.xticks(
        rotation=35,
        ha="right",
        fontsize=8
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()

    buffer = BytesIO()

    plt.savefig(
        buffer,
        format="png",
        bbox_inches="tight"
    )

    plt.close(fig)

    buffer.seek(0)

    return HttpResponse(
        buffer.getvalue(),
        content_type="image/png"
    )


# ============================================================
# Part 1.2 - Vega-Lite Bar Chart
# ============================================================

def vega_bar_spec():
    """
    Vega-Lite specification for the aggregated
    quest completion bar chart.

    Data comes from the internal JSON API.
    """

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",

        "title": "Users Who Completed Each Quest",

        "width": 700,

        "height": 400,

        "data": {
            "url": "/api/quest-summary/"
        },

        "mark": {
            "type": "bar"
        },

        "encoding": {

            "x": {
                "field": "quest",
                "type": "nominal",
                "sort": "-y",
                "title": "Quest",

                "axis": {
                    "labelAngle": -35
                },

            },

            "y": {
                "field": "user_count",
                "type": "quantitative",
                "title": "Number of Users",

                "scale": {
                    "zero": True
                }
            },

            "tooltip": [
                {
                    "field": "quest",
                    "type": "nominal",
                    "title": "Quest"
                },
                {
                    "field": "user_count",
                    "type": "quantitative",
                    "title": "Users"
                }
            ]
        }
    }


# ============================================================
# Part 1.2 - Vega-Lite Interactive Line Chart
# ============================================================

def vega_line_spec(api_url="/api/completion-timeline/"):
    """
    Vega-Lite line chart showing the number of users
    completing each quest over time.

    The API URL can be relative for browser rendering
    or absolute for server-side PNG rendering.
    """

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",

        "title": "Users Completing Each Quest Over Time",

        "width": 700,

        "height": 400,

        "data": {
            "url": api_url
        },

        # ----------------------------------------------------
        # Interactive quest selection
        # ----------------------------------------------------

        "params": [
            {
                "name": "quest_selection",

                "select": {
                    "type": "point",
                    "fields": ["quest"]
                },

                "bind": "legend"
            }
        ],

        # ----------------------------------------------------
        # Line chart
        # ----------------------------------------------------

        "mark": {
            "type": "line",
            "point": True
        },

        "encoding": {

            "x": {
                "field": "date",
                "type": "temporal",
                "title": "Date",
                "scale": {
                    "type": "utc"
                },
                "axis": {
                    "format": "%b %d",
                    "tickCount": "day"
                }
            },

            "y": {
                "field": "user_count",
                "type": "quantitative",
                "title": "Number of Users",

                "scale": {
                    "zero": True
                }
            },

            "color": {
                "field": "quest",
                "type": "nominal",
                "title": "Quest"
            },

            "tooltip": [
                {
                    "field": "date",
                    "type": "temporal",
                    "title": "Date",
                    "format": "%Y-%m-%d"
                },
                {
                    "field": "quest",
                    "type": "nominal",
                    "title": "Quest"
                },
                {
                    "field": "user_count",
                    "type": "quantitative",
                    "title": "Users"
                }
            ]
        }
    }


# ============================================================
# Part 1.2 - Vega-Lite Chart Page
# ============================================================

def vega_lite_charts(request):
    """
    Render a page containing both Vega-Lite charts.
    """

    return render(
        request,
        "core/vega_lite_charts.html",
        {
            "bar_spec": json.dumps(
                vega_bar_spec()
            ),

            "line_spec": json.dumps(
                vega_line_spec()
            ),
        }
    )


# ============================================================
# Part 1.2 - Vega-Lite PNG Endpoints
# ============================================================

def vega_bar_png(request):
    """
    Return the Vega-Lite bar chart as PNG.

    The HTML version uses the database-backed API URL.
    For server-side PNG rendering, the database data is
    provided directly to vl_convert.
    """

    quest_summary = Quest.objects.annotate(
        user_count=Count(
            "completions__user",
            filter=Q(
                completions__completed_status=True
            ),
            distinct=True
        )
    )

    data = [
        {
            "quest": quest.title,
            "user_count": quest.user_count,
        }
        for quest in quest_summary
    ]

    spec = vega_bar_spec()

    spec["data"] = {
        "values": data
    }

    png = vlc.vegalite_to_png(
        json.dumps(spec),
        scale=2
    )

    return HttpResponse(
        png,
        content_type="image/png"
    )


def vega_line_png(request):
    """
    Return the Vega-Lite line chart as PNG.

    The HTML version uses the database-backed API URL.
    For server-side PNG rendering, we provide the same
    database data directly to vl_convert so that it does
    not need to make a request back to the Django server.
    """

    start_date = date(2026, 9, 25)
    end_date = date(2026, 10, 1)

    completion_summary = (
        QuestCompletion.objects
        .filter(
            completed_status=True,
            completed_date__range=(start_date, end_date)
        )
        .values(
            "completed_date",
            "quest__title"
        )
        .annotate(
            user_count=Count(
                "user",
                distinct=True
            )
        )
        .order_by(
            "completed_date",
            "quest__title"
        )
    )

    data = [
        {
            "date": item["completed_date"].isoformat(),
            "quest": item["quest__title"],
            "user_count": item["user_count"],
        }
        for item in completion_summary
    ]

    # Create the same Vega-Lite specification,
    # but provide the database data directly for
    # server-side PNG rendering.

    spec = vega_line_spec()

    spec["data"] = {
        "values": data
    }

    png = vlc.vegalite_to_png(
        json.dumps(spec),
        scale=2
    )

    return HttpResponse(
        png,
        content_type="image/png"
    )


# ============================================================
# Rewards
# ============================================================

def reward_list_render(request):
    rewards = Reward.objects.all()

    return render(
        request,
        "core/reward_list.html",
        {
            "rewards": rewards
        }
    )


# ============================================================
# Quest Detail
# ============================================================

def quest_detail(request, pk):

    quest = get_object_or_404(
        Quest,
        pk=pk
    )

    return render(
        request,
        "core/quest_detail.html",
        {
            "quest": quest
        }
    )


# ============================================================
# Users
# ============================================================

def user_list(request):

    # GET search
    query = request.GET.get(
        "q",
        ""
    )

    # Alphabetical ordering
    users = User.objects.all().order_by(
        "first_name",
        "last_name",
        "username"
    )

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
    ).distinct().order_by(
        "first_name",
        "last_name",
        "username"
    )

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


# ============================================================
# Class-Based Views
# ============================================================

class QuestListBaseView(View):

    def get(self, request):

        query = request.GET.get(
            "q",
            ""
        )

        quests = Quest.objects.all()

        if query:
            quests = quests.filter(
                title__icontains=query
            )

        return render(
            request,
            "core/quest_list.html",
            quest_list_context(
                query,
                quests
            )
        )


class QuestListGenericView(ListView):

    model = Quest

    template_name = "core/quest_list.html"

    context_object_name = "quests"

    def get_queryset(self):

        query = self.request.GET.get(
            "q",
            ""
        )

        quests = super().get_queryset()

        if query:
            quests = quests.filter(
                title__icontains=query
            )

        return quests

    def get_context_data(self, **kwargs):

        context = super().get_context_data(
            **kwargs
        )

        query = self.request.GET.get(
            "q",
            ""
        )

        context.update(
            quest_list_context(
                query,
                context["quests"]
            )
        )

        return context

def location_search(request):
    query = request.GET.get("q", "")

    if not query:
        return JsonResponse({"error": "No location provided"}, status=400)

    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": "SafeSpace-UIUC-Project (student project, INFO490)"},
        timeout=5,
    )
    r.raise_for_status()
    output_full = r.json()
    if not output_full:
        return JsonResponse({"error": "Location not found"}, status=404)

    place = output_full[0]
    output_polished = {
        "query": query,
        "display_name": place.get("display_name"),
        "lat": place.get("lat"),
        "lon": place.get("lon"),
    }
    return JsonResponse(output_polished)