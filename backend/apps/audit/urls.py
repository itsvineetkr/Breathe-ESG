from django.urls import path
from . import views

urlpatterns = [
    path('logs/', views.list_audit_logs),
]
