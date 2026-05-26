from django.urls import path
from . import views

urlpatterns = [
    path('records/', views.list_records),
    path('records/bulk-review/', views.bulk_review),
    path('records/<uuid:pk>/', views.record_detail),
    path('records/<uuid:pk>/review/', views.review_record),
    path('reports/', views.reports),
]
