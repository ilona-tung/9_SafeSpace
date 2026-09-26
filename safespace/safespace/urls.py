from django.contrib import admin
from django.urls import path
from core import views


urlpatterns = [

    # Admin
    path(
        "admin/",
        admin.site.urls
    ),

    # Home
    path(
        "",
        views.home,
        name="home"
    ),

    # Quests
    path(
        "quests/",
        views.quest_list_render,
        name="quest_list"
    ),

    path(
        "quests/render/",
        views.quest_list_render,
        name="quest_list_render"
    ),

    path(
        "quests/cbv-base/",
        views.QuestListBaseView.as_view(),
        name="quest_cbv_base"
    ),

    path(
        "quests/cbv-generic/",
        views.QuestListGenericView.as_view(),
        name="quest_cbv_generic"
    ),

    path(
        "quests/<int:pk>/",
        views.quest_detail,
        name="quest_detail"
    ),

    # Users
    path(
        "users/",
        views.user_list,
        name="user_list"
    ),

    path(
        "users/<int:pk>/",
        views.user_detail,
        name="user_detail"
    ),

    # Rewards
    path(
        "rewards/",
        views.reward_list_render,
        name="reward_list"
    ),

    path(
        "rewards/render/",
        views.reward_list_render,
        name="reward_list_render"
    ),
]