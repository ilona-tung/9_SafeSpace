from datetime import date
import json
import csv

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

from .models import Quest, Reward, Journal, QuestCompletion, Forum

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
from datetime import datetime

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
            ),        }
    )


# ============================================================
# Part 1.2 - Vega-Lite JSON Spec Downloads
# ============================================================

def vega_spec_download(request, chart):
    """
    Download a chart's Vega-Lite spec as a .json file.
    The data URL is made absolute so the spec also works
    when pasted into the online Vega-Lite editor.
    """

    if chart == "bar":
        spec = vega_bar_spec()
        spec["data"]["url"] = request.build_absolute_uri(spec["data"]["url"])
        filename = "bar_chart.json"
    else:
        spec = vega_line_spec(
            request.build_absolute_uri("/api/completion-timeline/")
        )
        filename = "line_chart.json"

    response = JsonResponse(spec, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


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

# ============================================================
# Part 2 - External API (OpenStreetMap Nominatim, keyless)
# ============================================================

def geocode(query):
    """
    Look up a place name with Nominatim.
    Returns the best match, or None if nothing was found.
    Raises requests.RequestException if the service fails.
    The result is used for this request only and never saved.
    """

    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": query,
            "format": "json",
            "limit": 1,
            "addressdetails": 1,
        },
        headers={"User-Agent": "SafeSpace-UIUC-Project (student project, INFO490)"},
        timeout=5,
    )
    r.raise_for_status()
    output_full = r.json()

    if not output_full:
        return None

    place = output_full[0]
    address = place.get("address", {})

    # "US-IL" -> "IL"
    state_code = address.get("ISO3166-2-lvl4", "").split("-")[-1]

    return {
        "display_name": place.get("display_name"),
        "lat": float(place["lat"]),
        "lon": float(place["lon"]),
        "city": address.get("city") or address.get("town") or address.get("village"),
        "state": address.get("state"),
        "state_code": state_code,
    }


def location_search(request):
    """
    Return the external location data for ?q= as-is.
    """

    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"error": "No location provided"}, status=400)

    try:
        place = geocode(query)
    except requests.RequestException:
        return JsonResponse({"error": "Location service unavailable"}, status=502)

    if place is None:
        return JsonResponse({"error": "Location not found"}, status=404)

    return JsonResponse({"query": query, **place})


# ============================================================
# Part 2 - Triangulate location API with Forum posts
# ============================================================

def forum_summary(posts):
    """
    Post count, distinct users, and posts per group for a list of posts.
    """

    group_counts = {}

    for post in posts:
        group_counts[post.group] = group_counts.get(post.group, 0) + 1

    return {
        "post_count": len(posts),
        "user_count": len({post.user_id for post in posts}),
        "groups": [
            {"group": group, "post_count": count}
            for group, count in sorted(group_counts.items(), key=lambda item: -item[1])
        ],
    }


def forum_nearby_api(request):
    """
    Resolve ?q= (a city, zip code, or landmark) with the location API,
    then find forum communities in the same city and the same state.

    Forum.location is written as "City, ST" (e.g. "Champaign, IL").
    The external data is only used to match posts; nothing is stored.
    """

    if request.method != "GET":
        return JsonResponse(
            {"error": "GET requests only."},
            status=405
        )

    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"error": "No location provided"}, status=400)

    try:
        place = geocode(query)
    except requests.RequestException:
        return JsonResponse({"error": "Location service unavailable"}, status=502)

    if place is None:
        return JsonResponse({"error": "Location not found"}, status=404)

    return JsonResponse({"query": query, **match_forums(place)})


def match_forums(place):
    """
    Triangulate a resolved place with Forum posts: find the posts in
    the same city and the same state, and the state's share of all posts.
    """

    posts = list(Forum.objects.exclude(location=""))

    same_city = []
    same_state = []

    for post in posts:
        parts = [part.strip().lower() for part in post.location.split(",")]
        city = parts[0]
        state = parts[-1] if len(parts) > 1 else ""

        in_state = state in {
            (place["state"] or "").lower(),
            place["state_code"].lower(),
        }

        if in_state:
            same_state.append(post)

            if place["city"] and city == place["city"].lower():
                same_city.append(post)

    return {
        "resolved_place": place,
        "total_posts_with_location": len(posts),
        "same_city": forum_summary(same_city),
        "same_state": forum_summary(same_state),
        "state_share": round(len(same_state) / len(posts), 2) if posts else 0,
    }


def forum_nearby_page(request):
    """
    HTML version of forum_nearby_api with a search form.
    """

    query = request.GET.get("q", "").strip()
    context = {"query": query}

    if query:
        try:
            place = geocode(query)
        except requests.RequestException:
            context["error"] = "The location service is unavailable. Please try again."
        else:
            if place is None:
                context["error"] = f'No place found for "{query}".'
            else:
                context.update(match_forums(place))

    return render(request, "core/forum_nearby.html", context)


# ============================================================
# Reports & Data Exports
# ============================================================

def reports_view(request):
    """
    Renders the summary reports page with totals and grouped summaries.
    """
    total_users = User.objects.count()

    # Active completers: Users who have completed at least one quest
    active_completers = User.objects.filter(
        quest_completions__completed_status=True
    ).distinct().count()

    inactive_completers = total_users - active_completers

    # Quests completed per user (ordered from highest to lowest)
    quests_per_user = (
        User.objects.annotate(
            completed_count=Count(
                "quest_completions",
                filter=Q(quest_completions__completed_status=True),
                distinct=True
            )
        )
        .order_by("-completed_count", "username")
    )

    context = {
        "total_users": total_users,
        "active_completers": active_completers,
        "inactive_completers": inactive_completers,
        "quests_per_user": quests_per_user,
    }
    return render(request, "core/reports.html", context)


def export_users_csv(request):
    """
    Generates and returns a downloadable CSV export of users (ordered).
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"users_{timestamp}.csv"

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    # First row = column headers
    writer.writerow(["ID", "Username", "Email", "Date Joined", "Quests Completed"])

    users = User.objects.all().order_by("id")
    for user in users:
        completed_count = user.quest_completions.filter(completed_status=True).count()
        writer.writerow([
            user.id,
            user.username,
            user.email,
            user.date_joined.strftime("%Y-%m-%d %H:%M:%S") if user.date_joined else "",
            completed_count
        ])

    return response


def export_users_json(request):
    """
    Generates and returns pretty JSON with metadata and all records.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    filename = f"users_{timestamp}.json"

    users_qs = User.objects.all().order_by("id")

    users_data = []
    for user in users_qs:
        completed_quests = list(
            user.quest_completions.filter(completed_status=True)
            .values_list("quest__title", flat=True)
        )
        users_data.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "date_joined": user.date_joined.isoformat() if user.date_joined else None,
            "completed_quests": completed_quests,
        })

    data = {
        "generated_at": datetime.now().isoformat(),
        "record_count": users_qs.count(),
        "users": users_data,  # Matches model/user records
    }

    response = JsonResponse(data, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
