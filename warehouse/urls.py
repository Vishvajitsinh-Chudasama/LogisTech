from django.urls import path
from . import views

urlpatterns = [
    path('', views.generate_bins, name='root_generate_bins'),
    path('ingest/', views.ingest, name='ingest'),
    path('process_queue/', views.process_queue, name='process_queue'),
    path('optimize_load/', views.optimize_load, name='optimize_load'),
    path('unload_truck/', views.unload_truck, name='unload_truck'),
    path('view_status/', views.view_status, name='view_status'),
]