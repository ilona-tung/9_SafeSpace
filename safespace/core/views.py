from collections import Counter
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
from django.urls import reverse, reverse_lazy
from urllib.parse import urlencode
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from .models import Quest, Reward, Journal, QuestCompletion, Forum, Post, Reply, UserReward, Profile, Friendship, TogetherInvite
from .forms import FeelingForm, JournalEditorForm, ForumForm, PostForm, NameForm, BioForm
from . import ai
from .welcome import generate_welcome_message

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

HOME_CHART_QUESTS = 6


def home(request):
    """
    Home page. Everyone (even logged out) sees the quest chart,
    which loads its data from the public quest-summary API.
    """

    spec = vega_bar_spec()
    spec["width"] = "container"
    spec["height"] = 200
    spec["title"] = {"text": "Top 6 quests in SafeSpace", "fontSize": 15}
    spec["encoding"]["x"]["title"] = None

    # Only the 6 most completed quests, so the small chart stays readable
    spec["transform"] = [
        {
            "window": [{"op": "row_number", "as": "rank"}],
            "sort": [
                {"field": "user_count", "order": "descending"},
                {"field": "quest", "order": "ascending"},
            ],
        },
        {"filter": f"datum.rank <= {HOME_CHART_QUESTS}"},
    ]

    context = {"quest_chart_spec": spec}
    if request.user.is_authenticated:
        context["welcome_message"] = generate_welcome_message(request.user)

    return render(request, "core/home.html", context)


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
        # Google login (allauth) adds a second backend, so say which one
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
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

    # Solo and Together quests are shown in separate sections
    context["solo_quests"] = quests.exclude(category=Quest.TOGETHER)
    context["together_quests"] = quests.filter(category=Quest.TOGETHER)

    if not request.user.is_staff:
        context["feeling_form"] = FeelingForm(user=request.user)
        # Shown once, right after asking: one quest per input
        context["ai_result"] = request.session.pop(AI_RESULT_KEY, None)

    return render(
        request,
        "core/quest_list.html",
        context
    )


# ============================================================
# AI Quest Suggestions (local Hugging Face model)
# ============================================================

AI_RESULT_KEY = "ai_quest_suggestion"


@regular_user_required
@require_POST
def quest_suggest(request):
    """
    The user writes how they feel and/or picks one of their journal
    entries; the local LLM (core/ai.py) suggests one of our quests.
    One quest per input: the result is shown once on the Quests page.
    """

    form = FeelingForm(request.POST, user=request.user)

    if not form.is_valid():
        messages.error(request, "Write how you feel (up to 300 characters), or choose a journal entry.")
        return redirect(reverse("quest_list") + "#ask-safespace")

    feeling = form.cleaned_data["feeling"]
    journal = form.cleaned_data["journal"]
    result = ai.suggest_quest(request.user, feeling, journal=journal)
    quest = result["quest"]

    request.session[AI_RESULT_KEY] = {
        "feeling": feeling,
        "journal_label": form.fields["journal"].label_from_instance(journal) if journal else "",
        "message": result["message"],
        "status": result["status"],
        "quest_title": quest.title if quest else "",
        "quest_url": quest.get_absolute_url() if quest else "",
    }

    return redirect(reverse("quest_list") + "#ask-safespace")


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
    The logged-in user's own journal entries as small cards.
    Click a card to open the full decorated page.
    """

    journals = (
        request.user.journals
        .select_related("background")
        .prefetch_related("stickers__reward")
    )

    return render(
        request,
        "core/journal_list.html",
        {"journals": journals}
    )


@regular_user_required
def journal_detail(request, pk):
    """
    One full decorated journal page. Users can only open their own.
    """

    journal = get_object_or_404(
        Journal.objects
        .select_related("background", "frame", "font")
        .prefetch_related("stickers__reward"),
        pk=pk,
        user=request.user,
    )

    return render(
        request,
        "core/journal_detail.html",
        {
            "journal": journal,
            "font_rewards": font_rewards(),
        }
    )


@regular_user_required
@require_POST
def journal_delete(request, pk):
    """
    Delete one of the user's own journal entries.
    Stickers placed on it are freed and can be used again.
    """

    journal = get_object_or_404(
        Journal,
        pk=pk,
        user=request.user,
    )

    journal.delete()

    messages.success(request, "Journal entry deleted. Its stickers are back in your rewards.")
    return redirect("journal_list")


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
        rewards = rewards.annotate(
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

    # Grouped by type on the page: stickers first, then backgrounds, frames, fonts
    # (annotated queries ignore the model's default ordering)
    type_order = {"sticker": 0, "background": 1, "frame": 2, "font": 3}
    rewards = sorted(
        rewards.prefetch_related("quests"),
        key=lambda reward: (type_order.get(reward.item_type, 9), reward.name),
    )

    # Collection progress: unlimited rewards count as collected
    collected = sum(
        1 for reward in rewards
        if reward.unlimited or getattr(reward, "owned_count", 0)
    )

    return render(
        request,
        "core/reward_list.html",
        {
            "rewards": rewards,
            "collected": collected,
            "font_rewards": font_rewards(),
        }
    )


# ============================================================
# Quest Detail
# ============================================================

# Quests work on the honor system, so rewards are capped per day:
# extra completions still count, but don't earn more stickers.
DAILY_REWARD_LIMIT = 3


def rewards_left_today(user):
    """
    How many more quest completions can earn rewards today.
    Only completions that actually unlocked a reward count.
    """

    rewarded_today = (
        QuestCompletion.objects
        .filter(user=user, completed_date=timezone.localdate(), unlocked_rewards__isnull=False)
        .distinct()
        .count()
    )

    return max(DAILY_REWARD_LIMIT - rewarded_today, 0)


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
        context["rewards_left"] = rewards_left_today(request.user)
        context["daily_reward_limit"] = DAILY_REWARD_LIMIT

        if quest.is_together:
            context["friends"] = Friendship.friends_of(request.user)
            context["sent_invites"] = (
                request.user.together_invites_sent
                .filter(quest=quest, status="pending")
                .select_related("to_user")
            )

    return render(
        request,
        "core/quest_detail.html",
        context
    )


def complete_today(user, quest):
    """
    Mark `quest` as completed today for `user` and award its rewards,
    within the daily reward limit.

    Returns (completion, already_done, new_rewards, hit_limit).
    """

    today = timezone.localdate()

    completion, created = QuestCompletion.objects.get_or_create(
        user=user,
        quest=quest,
        quest_date=today,
        defaults={
            "completed_status": True,
            "completed_date": today,
        }
    )

    if not created and completion.completed_status:
        return completion, True, [], False

    # Checked before saving, so this completion isn't counted yet
    can_earn_rewards = rewards_left_today(user) > 0

    if not created:
        # The quest was started today but not finished yet
        completion.completed_status = True
        completion.completed_date = today
        completion.save()

    new_rewards = completion.award_rewards() if can_earn_rewards else []
    hit_limit = not can_earn_rewards and quest.possible_rewards.exists()

    return completion, False, new_rewards, hit_limit


def reward_message(new_rewards, hit_limit):
    if hit_limit:
        return (
            f" You've earned rewards from {DAILY_REWARD_LIMIT} quests today, "
            "which is today's limit. New rewards unlock again tomorrow."
        )

    if new_rewards:
        names = ", ".join(str(user_reward.reward) for user_reward in new_rewards)
        return f" You earned: {names}."

    return ""


@regular_user_required
@require_POST
def complete_quest(request, pk):
    """
    Mark a quest as completed today for the logged-in user.

    Quests are daily: each day gets its own QuestCompletion.
    A completion that is already marked completed is never changed.
    Only the first DAILY_REWARD_LIMIT rewarded completions each day earn rewards.
    Together quests can't be completed alone: they need an accepted invite.
    """

    quest = get_object_or_404(
        Quest,
        pk=pk
    )

    if quest.is_together:
        messages.error(request, "This is a Together quest: invite a friend to complete it with you.")
        return redirect(quest)

    _, already_done, new_rewards, hit_limit = complete_today(request.user, quest)

    if already_done:
        messages.info(request, f"You already completed \"{quest}\" today.")
        return redirect(quest)

    messages.success(request, f"Nice work! You completed \"{quest}\"." + reward_message(new_rewards, hit_limit))

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
# Profiles
# ============================================================

PROFILE_RECENT_JOURNALS = 3
PROFILE_RECENT_REWARDS = 6
PROFILE_RECENT_QUESTS = 5
PROFILE_RECENT_TOGETHER = 5
PEOPLE_SEARCH_LIMIT = 50


def joined_forums(user):
    return (
        user.forums
        .annotate(member_count=Count("members", distinct=True), post_count=Count("posts", distinct=True))
        .order_by("name")
    )


@login_required
def profile_me(request):
    """
    The logged-in user's own profile: basic info plus their recent
    journals, rewards, quests and forums, each linking to its full page.
    """

    me = request.user
    forums = joined_forums(me)

    context = {
        "person": me,
        "profile": Profile.for_user(me),
        "forums": forums,
        "joined_ids": {forum.pk for forum in forums},
    }

    # Admin accounts don't use journals, quests or rewards
    if not me.is_staff:
        completions = me.quest_completions.filter(completed_status=True)

        context.update({
            "quest_count": completions.count(),
            "reward_count": me.rewards.count(),
            "journal_count": me.journals.count(),
            "recent_journals": (
                me.journals.order_by("-time")
                .select_related("background")
                .prefetch_related("stickers__reward")[:PROFILE_RECENT_JOURNALS]
            ),
            "recent_rewards": me.rewards.select_related("reward")[:PROFILE_RECENT_REWARDS],
            "recent_quests": (
                completions.select_related("quest")
                .order_by("-completed_date", "-pk")[:PROFILE_RECENT_QUESTS]
            ),

            # Friends and Together quests
            "friends": Friendship.friends_of(me),
            "friend_requests": me.friendship_requests_received.filter(status="pending").select_related("user_from"),
            "sent_requests": me.friendship_requests_sent.filter(status="pending").select_related("user_to"),
            "invites_received": me.together_invites_received.filter(status="pending").select_related("quest", "from_user"),
            "invites_sent": me.together_invites_sent.filter(status="pending").select_related("quest", "to_user"),
            "together": together_history(me)[:PROFILE_RECENT_TOGETHER],
        })

    return render(request, "core/profile.html", context)


@login_required
def profile_view(request, username):
    """
    Someone else's public profile: only basic info and the forums
    they joined (forums are public anyway). Never their journals,
    rewards, quests or email.
    """

    person = get_object_or_404(User, username=username, is_active=True)

    # Your own profile opens the full version, unless you ask to preview
    # what others see
    preview = person == request.user and request.GET.get("preview") == "1"

    if person == request.user and not preview:
        return redirect("profile_me")

    forums = joined_forums(person)
    joined_ids = set(request.user.forums.values_list("pk", flat=True))

    # Friend button state, and what you two did together (friends only)
    friendship = Friendship.between(request.user, person)
    can_friend = not preview and not request.user.is_staff and not person.is_staff

    if friendship is None:
        friend_state = "none"
    elif friendship.status == "accepted":
        friend_state = "friends"
    elif friendship.user_from == request.user:
        friend_state = "sent"
    else:
        friend_state = "received"

    together = together_history(request.user, person) if friend_state == "friends" and not preview else []

    return render(
        request,
        "core/profile_public.html",
        {
            "person": person,
            "profile": Profile.for_user(person),
            "forums": forums,
            "joined_ids": joined_ids,
            "preview": preview,
            "can_friend": can_friend,
            "friend_state": friend_state,
            "together": together,
        }
    )


@login_required
def profile_edit(request):

    profile = Profile.for_user(request.user)

    if request.method == "POST":
        name_form = NameForm(request.POST, instance=request.user)
        bio_form = BioForm(request.POST, instance=profile)

        if name_form.is_valid() and bio_form.is_valid():
            name_form.save()
            bio_form.save()
            messages.success(request, "Profile updated.")
            return redirect("profile_me")
    else:
        name_form = NameForm(instance=request.user)
        bio_form = BioForm(instance=profile)

    return render(
        request,
        "core/profile_edit.html",
        {"name_form": name_form, "bio_form": bio_form}
    )


@login_required
def people_search(request):
    """
    Find other users by username or name. Results only link
    to public profiles.
    """

    query = request.GET.get("q", "").strip()
    people = User.objects.none()

    if query:
        people = (
            User.objects
            .filter(is_active=True)
            .exclude(pk=request.user.pk)
            .filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
            .select_related("profile")
            .order_by("username")[:PEOPLE_SEARCH_LIMIT]
        )

    return render(
        request,
        "core/people.html",
        {"query": query, "people": people}
    )


# ============================================================
# Friends
# ============================================================

def back_to(request, fallback):
    """
    Go back to the page the form was on (only pages on this site).
    """

    next_url = request.POST.get("next", "")

    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)

    return redirect(fallback)


def other_user(request, username):
    """
    The regular user a friend button is about (not yourself, not an admin).
    """

    person = get_object_or_404(User, username=username, is_active=True, is_staff=False)

    if person == request.user:
        raise PermissionDenied

    return person


@regular_user_required
@require_POST
def friend_add(request, username):
    """
    Send a friend request. If they already asked you, this accepts it.
    """

    person = other_user(request, username)
    friendship = Friendship.between(request.user, person)

    if friendship is None:
        Friendship.objects.create(user_from=request.user, user_to=person)
        messages.success(request, f"Friend request sent to {person.username}.")
    elif friendship.status == "accepted":
        messages.info(request, f"You and {person.username} are already friends.")
    elif friendship.user_from == person:
        friendship.status = "accepted"
        friendship.save()
        messages.success(request, f"You and {person.username} are now friends.")
    else:
        messages.info(request, f"You already sent {person.username} a request.")

    return back_to(request, reverse("profile_view", args=[person.username]))


@regular_user_required
@require_POST
def friend_accept(request, username):
    person = other_user(request, username)
    friendship = get_object_or_404(Friendship, user_from=person, user_to=request.user, status="pending")

    friendship.status = "accepted"
    friendship.save()
    messages.success(request, f"You and {person.username} are now friends.")

    return back_to(request, reverse("profile_view", args=[person.username]))


@regular_user_required
@require_POST
def friend_decline(request, username):
    """
    Decline a request you received, or cancel one you sent.
    No one is notified, and either person can ask again later.
    """

    person = other_user(request, username)
    Friendship.objects.filter(
        Q(user_from=person, user_to=request.user) | Q(user_from=request.user, user_to=person),
        status="pending",
    ).delete()

    return back_to(request, reverse("profile_view", args=[person.username]))


@regular_user_required
@require_POST
def friend_remove(request, username):
    """
    Unfriend. Pending Together invites between the two are removed too.
    """

    person = other_user(request, username)
    Friendship.objects.filter(
        Q(user_from=person, user_to=request.user) | Q(user_from=request.user, user_to=person),
        status="accepted",
    ).delete()
    # Two simple deletes: an OR filter here trips an SQLite planner bug
    # with the partial unique index on pending invites
    for sender, receiver in [(person, request.user), (request.user, person)]:
        TogetherInvite.objects.filter(from_user=sender, to_user=receiver, status="pending").delete()
    messages.info(request, f"You and {person.username} are no longer friends.")

    return back_to(request, reverse("profile_view", args=[person.username]))


# ============================================================
# Together quests
# ============================================================

def together_history(user, other=None):
    """
    Accepted Together invites of `user` (only the ones with `other`, if given),
    newest first, with each person's own rewards.
    """

    invites = TogetherInvite.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status="accepted",
    )

    if other is not None:
        invites = invites.filter(Q(from_user=other) | Q(to_user=other))

    invites = invites.select_related("quest", "from_user", "to_user").prefetch_related(
        "from_completion__unlocked_rewards__reward",
        "to_completion__unlocked_rewards__reward",
    ).order_by("-accepted_at")

    return invites


@regular_user_required
@require_POST
def together_invite(request, pk):
    """
    Invite a friend to do a Together quest with you.
    """

    quest = get_object_or_404(Quest, pk=pk, category=Quest.TOGETHER)
    friend = Friendship.friends_of(request.user).filter(username=request.POST.get("friend", "")).first()

    if friend is None:
        messages.error(request, "Choose one of your friends to invite.")
    elif TogetherInvite.objects.filter(from_user=request.user, to_user=friend, quest=quest, status="pending").exists():
        messages.info(request, f"You already invited {friend.username} to this quest.")
    else:
        TogetherInvite.objects.create(from_user=request.user, to_user=friend, quest=quest)
        messages.success(request, f"Invite sent! When {friend.username} accepts, the quest is completed for both of you.")

    return redirect(quest)


@regular_user_required
@require_POST
def together_accept(request, pk):
    """
    Accept an invite: the quest is completed today for both people,
    and each gets rewards within their own daily limit.
    """

    invite = get_object_or_404(TogetherInvite, pk=pk, to_user=request.user, status="pending")

    if Friendship.between(invite.from_user, request.user) is None:
        invite.delete()
        messages.error(request, "You're no longer friends, so this invite was removed.")
        return back_to(request, reverse("profile_me"))

    from_completion, _, _, _ = complete_today(invite.from_user, invite.quest)
    to_completion, already_done, new_rewards, hit_limit = complete_today(request.user, invite.quest)

    invite.status = "accepted"
    invite.accepted_at = timezone.now()
    invite.from_completion = from_completion
    invite.to_completion = to_completion
    invite.save()

    message = f"You and {invite.from_user.username} completed \"{invite.quest}\" together!"

    if already_done:
        message += " You had already completed it today, so no new rewards for you."
    else:
        message += reward_message(new_rewards, hit_limit)

    messages.success(request, message)

    return back_to(request, reverse("profile_me"))


@regular_user_required
@require_POST
def together_decline(request, pk):
    """
    Decline an invite you received, or cancel one you sent.
    """

    get_object_or_404(
        TogetherInvite.objects.filter(Q(to_user=request.user) | Q(from_user=request.user)),
        pk=pk,
        status="pending",
    ).delete()

    return back_to(request, reverse("profile_me"))


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
# Forums: communities users join, with posts and replies
# ============================================================

@login_required
def forum_list(request):
    """
    Forums page: the forums the user joined, and the ones they haven't
    joined yet. Search by name, filter by category, or search near a place.

    "Near" looks the place up with the OpenStreetMap location API, then
    shows forums in the same city and elsewhere in the same state, plus
    the post statistics from match_forums.
    """

    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    near = request.GET.get("near", "").strip()

    forums = Forum.objects.annotate(
        member_count=Count("members", distinct=True),
        post_count=Count("posts", distinct=True),
    )

    if query:
        forums = forums.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        )

    if category in dict(Quest.CATEGORY_CHOICES):
        forums = forums.filter(category=category)

    joined_ids = set(request.user.forums.values_list("pk", flat=True))

    context = {
        "joined": [forum for forum in forums if forum.pk in joined_ids],
        "discover": [forum for forum in forums if forum.pk not in joined_ids],
        "joined_ids": joined_ids,
        "query": query,
        "category": category,
        "near": near,
        "categories": Quest.CATEGORY_CHOICES,
    }

    if near:
        try:
            place = geocode(near)
        except requests.RequestException:
            context["near_error"] = "The location service is unavailable. Please try again."
        else:
            if place is None:
                context["near_error"] = f'No place found for "{near}".'
            else:
                matches = [(forum, location_match(forum.location, place)) for forum in forums]

                context.update(match_forums(place))
                context["in_city"] = [forum for forum, match in matches if match == "city"]
                context["in_state"] = [forum for forum, match in matches if match == "state"]

    return render(request, "core/forum_list.html", context)


@login_required
def forum_new(request):
    """
    Any logged-in user can start a forum. The creator joins it.
    """

    if request.method == "POST":
        form = ForumForm(request.POST)

        if form.is_valid():
            forum = form.save(commit=False)
            forum.created_by = request.user
            forum.save()
            forum.members.add(request.user)

            messages.success(request, f"Forum created: {forum.name}")
            return redirect(forum)
    else:
        form = ForumForm()

    return render(request, "core/forum_form.html", {"form": form})


def can_manage(user, owner_id):
    """
    The owner of a forum, post or reply can delete it. Admins can delete anything.
    """

    return user.is_staff or user.pk == owner_id


def is_member(user, forum):
    return forum.members.filter(pk=user.pk).exists()


@login_required
def forum_detail(request, pk):
    """
    One forum: its description, a Join/Leave button,
    and its posts with replies. Only members can post and reply.
    """

    forum = get_object_or_404(Forum, pk=pk)

    posts = (
        forum.posts
        .select_related("user")
        .prefetch_related("replies__user")
    )

    return render(
        request,
        "core/forum_detail.html",
        {
            "forum": forum,
            "posts": posts,
            "member_count": forum.members.count(),
            "is_member": is_member(request.user, forum),
            "can_manage": can_manage(request.user, forum.created_by_id),
            "post_form": PostForm(),
        }
    )


@login_required
@require_POST
def forum_join(request, pk):
    forum = get_object_or_404(Forum, pk=pk)
    forum.members.add(request.user)

    messages.success(request, f"You joined {forum.name}.")
    return redirect(forum)


@login_required
@require_POST
def forum_leave(request, pk):
    forum = get_object_or_404(Forum, pk=pk)
    forum.members.remove(request.user)

    messages.success(request, f"You left {forum.name}.")
    return redirect(forum)


@login_required
@require_POST
def forum_delete(request, pk):
    forum = get_object_or_404(Forum, pk=pk)

    if not can_manage(request.user, forum.created_by_id):
        raise PermissionDenied

    forum.delete()

    messages.success(request, f"Forum deleted: {forum.name}")
    return redirect("forum_list")


def save_post_text(request, create):
    """
    Validate a post or reply and save it with create(content).
    Crisis words don't block the post, but the author sees the 988 message.
    """

    form = PostForm(request.POST)

    if not form.is_valid():
        messages.error(request, form.errors["content"][0])
        return

    content = form.cleaned_data["content"]
    create(content)

    if ai.is_crisis(content):
        messages.warning(request, ai.CRISIS_MESSAGE)
    else:
        messages.success(request, "Posted.")


@login_required
@require_POST
def post_create(request, pk):
    forum = get_object_or_404(Forum, pk=pk)

    if not is_member(request.user, forum):
        messages.error(request, "Join this forum to post.")
        return redirect(forum)

    save_post_text(request, lambda content: Post.objects.create(
        user=request.user,
        forum=forum,
        content=content,
        location=forum.location,
    ))

    return redirect(forum)


@login_required
@require_POST
def reply_create(request, pk):
    post = get_object_or_404(Post.objects.select_related("forum"), pk=pk)

    if not is_member(request.user, post.forum):
        messages.error(request, "Join this forum to reply.")
        return redirect(post.forum)

    save_post_text(request, lambda content: Reply.objects.create(
        post=post,
        user=request.user,
        content=content,
    ))

    return redirect(f"{post.forum.get_absolute_url()}#post-{post.pk}")


@login_required
@require_POST
def post_delete(request, pk):
    post = get_object_or_404(Post.objects.select_related("forum"), pk=pk)

    if not can_manage(request.user, post.user_id):
        raise PermissionDenied

    post.delete()

    messages.success(request, "Post deleted.")
    return redirect(post.forum)


@login_required
@require_POST
def reply_delete(request, pk):
    reply = get_object_or_404(Reply.objects.select_related("post__forum"), pk=pk)

    if not can_manage(request.user, reply.user_id):
        raise PermissionDenied

    reply.delete()

    messages.success(request, "Reply deleted.")
    return redirect(f"{reply.post.forum.get_absolute_url()}#post-{reply.post_id}")


# ============================================================
# Part 2 - Triangulate location API with forum posts
# ============================================================

def forum_summary(posts):
    """
    Post count, distinct users, and posts per group for a list of posts.
    """

    group_counts = Counter(post.forum for post in posts)

    return {
        "post_count": len(posts),
        "user_count": len({post.user_id for post in posts}),
        "groups": [
            {"group": forum.name, "forum_id": forum.pk, "post_count": count}
            for forum, count in group_counts.most_common()
        ],
    }


@api_login_required
def forum_nearby_api(request):
    """
    Resolve ?q= (a city, zip code, or landmark) with the location API,
    then find forum posts in the same city and the same state.

    Post.location is written as "City, ST" (e.g. "Champaign, IL").
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


def location_match(location, place):
    """
    Compare a "City, ST" location with a resolved place.
    Returns "city" (same city and state), "state" (same state only) or None.
    """

    parts = [part.strip().lower() for part in location.split(",")]
    city = parts[0]
    state = parts[-1] if len(parts) > 1 else ""

    if state not in {(place["state"] or "").lower(), place["state_code"].lower()}:
        return None

    if place["city"] and city == place["city"].lower():
        return "city"

    return "state"


def match_forums(place):
    """
    Triangulate a resolved place with forum posts: find the posts in
    the same city and the same state, and the state's share of all posts.
    """

    posts = list(Post.objects.select_related("forum").exclude(location=""))

    same_city = []
    same_state = []

    for post in posts:
        match = location_match(post.location, place)

        if match:
            same_state.append(post)

            if match == "city":
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
    Forums Nearby is now part of the Forums page (the "Near" search box).
    Old links still work.
    """

    query = request.GET.get("q", "").strip()
    url = reverse("forum_list")

    return redirect(f"{url}?{urlencode({'near': query})}" if query else url)


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
