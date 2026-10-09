from datetime import date
import json
import csv
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.views import View
from django.views.generic import ListView
from django.views.generic.edit import FormView
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import Quest, Reward, Journal, QuestCompletion, Forum, UserReward
from .forms import JournalEditorForm

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
    """
    Home page. Everyone (even logged out) sees the quest chart,
    which loads its data from the public quest-summary API.
    """

    spec = vega_bar_spec()
    spec["width"] = "container"
    spec["height"] = 200
    spec["title"] = {"text": "Quests in SafeSpace", "fontSize": 15}
    spec["encoding"]["x"]["title"] = None

    return render(request, "core/home.html", {"quest_chart_spec": spec})


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
# Login protection for JSON APIs
# ============================================================

def api_login_required(view):
    """
    Like login_required, but APIs answer with a JSON 401 error
    instead of redirecting to the HTML login page.
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Login required."},
                status=401
            )

        return view(request, *args, **kwargs)

    return wrapper


def admin_required(view):
    """
    Only admins (staff users) may open this page.
    SafeSpace is not a competition, so regular users
    never see reports that compare users.
    """

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied

        return view(request, *args, **kwargs)

    return wrapper


def regular_user_required(view):
    """
    Personal features (like the journal) are for regular users,
    not for admin accounts.
    """

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.is_staff:
            raise PermissionDenied

        return view(request, *args, **kwargs)

    return wrapper


def api_admin_required(view):
    """
    Admin-only JSON APIs: 401 when logged out, 403 for regular users.
    """

    @api_login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse(
                {"error": "Admins only."},
                status=403
            )

        return view(request, *args, **kwargs)

    return wrapper


# ============================================================
# Part 1.1 - Database-backed JSON API
# ============================================================

def quest_summary_data():
    """
    Each quest with its category and the number of distinct
    users who completed it. No usernames are included.
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

    return [
        {
            "quest": quest.title,
            "category": quest.display_category(),
            "user_count": quest.user_count,
        }
        for quest in quest_summary
    ]


def quest_summary_api(request):
    """
    Public API (A5 Part 3): no login needed.
    Return each quest, its category, and the number of
    distinct users who completed it.
    """

    if request.method != "GET":
        return JsonResponse(
            {"error": "GET requests only."},
            status=405
        )

    response = JsonResponse(quest_summary_data(), safe=False)

    # Let the online Vega-Lite editor (another website) read this API
    response["Access-Control-Allow-Origin"] = "*"
    return response


# ============================================================
# Part 1.2 - Database-backed JSON API for Line Chart
# ============================================================

@api_admin_required
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

@method_decorator(never_cache, name="dispatch")
class RegisterView(FormView):
    template_name = "core/register.html"
    form_class = UserCreationForm
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        # Already logged in (e.g. after pressing Back): go home instead
        if request.user.is_authenticated:
            return redirect("home")

        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        form = self.get_form()

        if form.is_valid():
            return self.form_valid(form)

        return self.form_invalid(form)

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
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


@login_required
def quest_list_render(request):

    # GET search
    query = request.GET.get("q", "")

    quests = Quest.objects.all()

    if query:
        quests = quests.filter(
            title__icontains=query
        )

    context = quest_list_context(
        query,
        quests
    )

    context["completed_today"] = completed_today_ids(request.user)

    return render(
        request,
        "core/quest_list.html",
        context
    )


def completed_today_ids(user):
    """
    IDs of the quests this user has completed today.
    """

    if not user.is_authenticated:
        return set()

    return set(
        QuestCompletion.objects.filter(
            user=user,
            quest_date=timezone.localdate(),
            completed_status=True,
        ).values_list("quest_id", flat=True)
    )


# ============================================================
# Journals
# ============================================================

@regular_user_required
def journal_list(request):
    """
    Show the logged-in user's own decorated journal entries.
    """

    journals = (
        request.user.journals
        .select_related("background", "frame", "font")
        .prefetch_related("stickers__reward")
    )

    return render(
        request,
        "core/journal_list.html",
        {
            "journals": journals,
            "font_rewards": font_rewards(),
        }
    )


@regular_user_required
def journal_new(request):
    """
    Drag-and-drop editor for writing and decorating a new journal page.
    """

    if request.method == "POST":
        form = JournalEditorForm(request.POST, user=request.user)

        if form.is_valid():
            form.save()

            messages.success(request, "Journal entry saved.")
            return redirect("journal_list")
    else:
        form = JournalEditorForm(user=request.user)

    return render(
        request,
        "core/journal_editor.html",
        {
            "form": form,
            "editor_rewards": editor_rewards(request.user),
            "font_rewards": font_rewards(),
            "today": timezone.localdate(),
        }
    )


def font_rewards():
    """
    Font rewards that have a font file, for the @font-face rules.
    """

    return Reward.objects.filter(item_type="font").exclude(asset="")


def editor_rewards(user):
    """
    The user's rewards for the editor's tray, grouped by type.
    Sticker counts only include copies that are not on a page yet.
    Unlimited rewards are available to everyone, with count None.
    """

    owned = (
        Reward.objects
        .filter(
            Q(pk__in=UserReward.objects.filter(user=user).values("reward"))
            | Q(unlimited=True)
        )
        .exclude(asset="")
        .annotate(
            owned_count=Count("earned_by", filter=Q(earned_by__user=user)),
            unused_count=Count(
                "earned_by",
                filter=Q(earned_by__user=user, earned_by__placement__isnull=True)
            ),
        )
        .order_by("name")
    )

    groups = {"sticker": [], "background": [], "frame": [], "font": []}

    for reward in owned:
        groups[reward.item_type].append({
            "id": reward.pk,
            "name": reward.name,
            "url": static(reward.asset),
            "count": (
                None if reward.unlimited
                else reward.unused_count if reward.item_type == "sticker"
                else reward.owned_count
            ),
        })

    return groups


# ============================================================
# Existing Matplotlib Chart
# ============================================================

@admin_required
def quest_completion_chart(request):
    """
    Generate a vertical bar chart showing how many
    distinct users have completed each quest.
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

# Colors from style.css (dark slate, sage, journal pink, lavender)
# plus soft sticker colors, so every category gets its own color
SAFESPACE_CATEGORY_COLORS = [
    "#324841", "#ADC2AF", "#E8B4B8", "#9C95C9",
    "#F2C46D", "#7FB3D5", "#8A8490",
]

SAFESPACE_CHART_STYLE = {
    "font": 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    "view": {"stroke": None},
    "title": {
        "color": "#324841",
        "fontSize": 18,
        "fontWeight": 700,
        "anchor": "start",
        "offset": 14,
    },
    "axis": {
        "labelColor": "#392D35",
        "titleColor": "#324841",
        "labelFontSize": 12,
        "titleFontSize": 13,
        "titleFontWeight": 600,
        "domainColor": "#ADC2AF",
        "tickColor": "#ADC2AF",
        "gridColor": "#E4E2F3",
    },
    "axisX": {"grid": False},
    "legend": {
        "labelColor": "#392D35",
        "titleColor": "#324841",
        "labelFontSize": 12,
        "titleFontSize": 13,
        "symbolType": "circle",
    },
}


def vega_bar_spec():
    """
    Vega-Lite specification for the quest bar chart,
    colored by category.

    Data comes from the public JSON API.
    """

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v6.json",

        "title": "Quests in SafeSpace",

        "background": "#ffffff",

        "padding": 16,

        # SafeSpace look: same font and colors as style.css
        "config": SAFESPACE_CHART_STYLE,

        "width": 700,

        "height": 400,

        "data": {
            "url": "/api/quest-summary/"
        },

        "mark": {
            "type": "bar",
            "cornerRadiusTopLeft": 6,
            "cornerRadiusTopRight": 6
        },

        "encoding": {

            "x": {
                "field": "quest",
                "type": "nominal",
                "sort": "-y",
                "title": "Quest",

                "scale": {
                    "paddingInner": 0.45
                },

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

            "color": {
                "field": "category",
                "type": "nominal",
                "title": "Category",

                "scale": {
                    "range": SAFESPACE_CATEGORY_COLORS
                },

                "legend": {
                    "orient": "bottom",
                    "direction": "horizontal",
                    "columns": 3
                }
            },

            "tooltip": [
                {
                    "field": "quest",
                    "type": "nominal",
                    "title": "Quest"
                },
                {
                    "field": "category",
                    "type": "nominal",
                    "title": "Category"
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

@admin_required
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

@admin_required
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

@admin_required
def vega_bar_png(request):
    """
    Return the Vega-Lite bar chart as PNG.

    The HTML version uses the database-backed API URL.
    For server-side PNG rendering, the database data is
    provided directly to vl_convert.
    """

    data = quest_summary_data()

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


@admin_required
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

@login_required
def reward_list_render(request):
    rewards = Reward.objects.all()

    if request.user.is_staff:
        # Admins see how each reward is used across the whole system
        rewards = rewards.prefetch_related("quests").annotate(
            times_earned=Count("earned_by", distinct=True),
            owner_count=Count("earned_by__user", distinct=True),
            times_placed=Count("placements", distinct=True),
        )
    else:
        rewards = rewards.annotate(
            owned_count=Count(
                "earned_by",
                filter=Q(earned_by__user=request.user)
            ),
            used_count=Count(
                "earned_by",
                filter=Q(earned_by__user=request.user, earned_by__placement__isnull=False)
            ),
        )

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

@login_required
def quest_detail(request, pk):

    quest = get_object_or_404(
        Quest,
        pk=pk
    )

    context = {
        "quest": quest,
        "completed_today": quest.pk in completed_today_ids(request.user),
    }

    if not request.user.is_staff:
        context["times_completed"] = quest.completions.filter(
            user=request.user,
            completed_status=True,
        ).count()

    return render(
        request,
        "core/quest_detail.html",
        context
    )


@regular_user_required
@require_POST
def complete_quest(request, pk):
    """
    Mark a quest as completed today for the logged-in user.

    Quests are daily: each day gets its own QuestCompletion.
    A completion that is already marked completed is never changed.
    """

    quest = get_object_or_404(
        Quest,
        pk=pk
    )

    today = timezone.localdate()

    completion, created = QuestCompletion.objects.get_or_create(
        user=request.user,
        quest=quest,
        quest_date=today,
        defaults={
            "completed_status": True,
            "completed_date": today,
        }
    )

    if not created and completion.completed_status:
        messages.info(request, f"You already completed \"{quest}\" today.")
        return redirect(quest)

    if not created:
        # The quest was started today but not finished yet
        completion.completed_status = True
        completion.completed_date = today
        completion.save()

    new_rewards = completion.award_rewards()

    message = f"Nice work! You completed \"{quest}\"."

    if new_rewards:
        names = ", ".join(str(user_reward.reward) for user_reward in new_rewards)
        message += f" You earned: {names}."

    messages.success(request, message)

    return redirect(quest)


# ============================================================
# Users
# ============================================================

@admin_required
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


@admin_required
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


@api_login_required
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


@api_login_required
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


@login_required
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

@admin_required
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


@admin_required
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


@admin_required
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
