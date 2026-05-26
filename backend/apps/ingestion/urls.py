from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_file),
    path('sources/', views.list_datasources),
    path('sources/<uuid:pk>/', views.datasource_detail),
]
