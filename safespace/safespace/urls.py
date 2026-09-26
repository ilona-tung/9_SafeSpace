from django.contrib import admin
from django.urls import path
from core import views


urlpatterns = [

    # Admin
    path("admin/",admin.site.urls),

    # Home
    path("",views.home,name="home"),
    path("register/", views.RegisterView.as_view(), name="register"),
    # Quests
    path("quests/",views.quest_list_render,name="quest_list"),
    path("quests/quest-completion-chart.png",views.quest_completion_chart,name="quest_completion_chart"),
    path("quests/<int:pk>/",views.quest_detail,name="quest_detail"),
    path("users/",views.user_list,name="user_list"),
    path("users/<int:pk>/",views.user_detail,name="user_detail"),
    path("rewards/",views.reward_list_render,name="reward_list"),
    path("rewards/render/",views.reward_list_render,name="reward_list_render"),
    path("journals/",views.journal_list,name="journal_list"),
    path("responses/http/", views.http_response_example,name="http_response_example"),
    path("responses/json/", views.json_response_example,name="json_response_example"),
]