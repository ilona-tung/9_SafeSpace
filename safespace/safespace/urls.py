"""
URL configuration for safespace project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),path('rewards/', views.reward_list_render, name='reward_list_render'),
    path('quests/', views.quest_list_manual, name='quest_list_manual'),
    path('quests/render/', views.quest_list_render, name='quest_list_render'),
    path('rewards/render/', views.reward_list_render, name='reward_list_render'),
    path('quests/cbv-base/', views.QuestListBaseView.as_view(), name='quest_cbv_base'),
    path('quests/cbv-generic/', views.QuestListGenericView.as_view(), name='quest_cbv_generic'),
]