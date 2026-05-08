from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_inbox, name="chat_inbox"),
    path("<int:pk>/", views.chat_detail, name="chat_detail"),
    path("<int:pk>/send/", views.chat_send, name="chat_send"),
    path("<int:pk>/poll/", views.chat_poll, name="chat_poll"),
    path("start/", views.chat_start, name="chat_start"),
    path("unread/", views.chat_unread, name="chat_unread"),
]
