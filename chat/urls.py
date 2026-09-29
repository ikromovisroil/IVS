from django.urls import path

from . import views

urlpatterns = [
    path("", views.chat_page, name="chat_page"),
    path("api/conversations/", views.chat_conversations, name="chat_conversations"),
    path("api/contacts/", views.chat_contacts, name="chat_contacts"),
    path("api/open/", views.chat_open, name="chat_open"),
    path("api/<int:conversation_id>/messages/", views.chat_messages, name="chat_messages"),
    path("api/<int:conversation_id>/send/", views.chat_send, name="chat_send"),
    path("api/message/<int:message_id>/edit/", views.chat_edit, name="chat_edit"),
    path("api/message/<int:message_id>/delete/", views.chat_delete, name="chat_delete"),
]
