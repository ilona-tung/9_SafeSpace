from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include
from core import views


urlpatterns = [

    # Admin
    path("admin/",admin.site.urls),

    # Home
    path("",views.home,name="home"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path('accounts/', include('allauth.urls')),
    # Quests
    path("quests/",views.quest_list_render,name="quest_list"),
    path("quests/suggest/", views.quest_suggest, name="quest_suggest"),
    path("quests/quest-completion-chart.png",views.quest_completion_chart,name="quest_completion_chart"),
    path("quests/<int:pk>/",views.quest_detail,name="quest_detail"),
    path("quests/<int:pk>/complete/", views.complete_quest, name="complete_quest"),
    path("quests/<int:pk>/invite/", views.together_invite, name="together_invite"),
    path("invites/<int:pk>/accept/", views.together_accept, name="together_accept"),
    path("invites/<int:pk>/decline/", views.together_decline, name="together_decline"),
    path("users/",views.user_list,name="user_list"),
    path("users/<int:pk>/",views.user_detail,name="user_detail"),
    path("profile/", views.profile_me, name="profile_me"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("people/", views.people_search, name="people_search"),
    path("people/<str:username>/", views.profile_view, name="profile_view"),
    path("people/<str:username>/friend/add/", views.friend_add, name="friend_add"),
    path("people/<str:username>/friend/accept/", views.friend_accept, name="friend_accept"),
    path("people/<str:username>/friend/decline/", views.friend_decline, name="friend_decline"),
    path("people/<str:username>/friend/remove/", views.friend_remove, name="friend_remove"),
    path("rewards/",views.reward_list_render,name="reward_list"),
    path("rewards/render/",views.reward_list_render,name="reward_list_render"),
    path("journals/",views.journal_list,name="journal_list"),
    path("journals/new/", views.journal_new, name="journal_new"),
    path("journals/<int:pk>/", views.journal_detail, name="journal_detail"),
    path("journals/<int:pk>/delete/", views.journal_delete, name="journal_delete"),
    path("responses/http/", views.http_response_example,name="http_response_example"),
    path("responses/json/", views.json_response_example,name="json_response_example"),
    path("api/quest-summary/",views.quest_summary_api,name="quest_summary_api"),
    path("api/completion-timeline/",views.completion_timeline_api,name="completion_timeline_api"),
    path("api/location/", views.location_search, name = "location_search"),
    path("forums/", views.forum_list, name="forum_list"),
    path("forums/new/", views.forum_new, name="forum_new"),
    path("forums/<int:pk>/", views.forum_detail, name="forum_detail"),
    path("forums/<int:pk>/join/", views.forum_join, name="forum_join"),
    path("forums/<int:pk>/leave/", views.forum_leave, name="forum_leave"),
    path("forums/<int:pk>/delete/", views.forum_delete, name="forum_delete"),
    path("forums/<int:pk>/post/", views.post_create, name="post_create"),
    path("forums/posts/<int:pk>/reply/", views.reply_create, name="reply_create"),
    path("forums/posts/<int:pk>/delete/", views.post_delete, name="post_delete"),
    path("forums/replies/<int:pk>/delete/", views.reply_delete, name="reply_delete"),
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