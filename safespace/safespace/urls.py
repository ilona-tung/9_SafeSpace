from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path
from core import views


urlpatterns = [

    # Admin
    path("admin/",admin.site.urls),

    # Home
    path("",views.home,name="home"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    # Quests
    path("quests/",views.quest_list_render,name="quest_list"),
    path("quests/quest-completion-chart.png",views.quest_completion_chart,name="quest_completion_chart"),
    path("quests/<int:pk>/",views.quest_detail,name="quest_detail"),
    path("quests/<int:pk>/complete/", views.complete_quest, name="complete_quest"),
    path("users/",views.user_list,name="user_list"),
    path("users/<int:pk>/",views.user_detail,name="user_detail"),
    path("rewards/",views.reward_list_render,name="reward_list"),
    path("rewards/render/",views.reward_list_render,name="reward_list_render"),
    path("journals/",views.journal_list,name="journal_list"),
    path("journals/new/", views.journal_new, name="journal_new"),
    path("responses/http/", views.http_response_example,name="http_response_example"),
    path("responses/json/", views.json_response_example,name="json_response_example"),
    path("api/quest-summary/",views.quest_summary_api,name="quest_summary_api"),
    path("api/completion-timeline/",views.completion_timeline_api,name="completion_timeline_api"),
    path("api/location/", views.location_search, name = "location_search"),
    path("forums/nearby/", views.forum_nearby_page, name="forum_nearby_page"),
    path("api/forum-nearby/", views.forum_nearby_api, name="forum_nearby_api"),
    path("vega-lite/",views.vega_lite_charts,name="vega_lite_charts"),
    path("vega-lite/bar.png",views.vega_bar_png,name="vega_bar_png"),
    path("vega-lite/completion-timeline.png",views.vega_line_png,name="vega_line_png"),
    path("vega-lite/bar.json", views.vega_spec_download, {"chart": "bar"}, name="vega_bar_json"),
    path("vega-lite/completion-timeline.json", views.vega_spec_download, {"chart": "line"}, name="vega_line_json"),
    path("reports/", views.reports_view, name="reports_page"),
    path("export/csv/", views.export_users_csv, name="export_users_csv"),
    path("export/json/", views.export_users_json, name="export_users_json"),
]