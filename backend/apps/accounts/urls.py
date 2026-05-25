from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('register/', views.register),
    path('login/', views.login),
    path('token/refresh/', TokenRefreshView.as_view()),
    path('me/', views.me),
    path('org/', views.update_org),
    path('analysts/', views.list_analysts),
    path('analysts/add/', views.add_analyst),
    path('analysts/<uuid:analyst_id>/remove/', views.remove_analyst),
]
