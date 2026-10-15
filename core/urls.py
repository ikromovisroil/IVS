from django.urls import path

from . import views

urlpatterns = [
    path("notifications/", views.notifications_page, name="notifications_page"),
    path("notifications/count/", views.notifications_count, name="notifications_count"),
    path("notifications/read-all/", views.notifications_read_all, name="notifications_read_all"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
]
