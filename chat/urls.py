from django.urls import path

from . import meeting_views, views

urlpatterns = [
    path("", views.chat_page, name="chat_page"),
    path("meetings/", meeting_views.meetings_page, name="meetings_page"),
    path("meetings/create/", meeting_views.meeting_create, name="meeting_create"),
    path("meetings/<int:pk>/cancel/", meeting_views.meeting_cancel, name="meeting_cancel"),
    path("meetings/<int:pk>/finish/", meeting_views.meeting_finish, name="meeting_finish"),
    path("api/conversations/", views.chat_conversations, name="chat_conversations"),
    path("api/contacts/", views.chat_contacts, name="chat_contacts"),
    path("api/open/", views.chat_open, name="chat_open"),
    path("api/create-group/", views.chat_create_group, name="chat_create_group"),
    path("api/<int:conversation_id>/messages/", views.chat_messages, name="chat_messages"),
    path("api/<int:conversation_id>/send/", views.chat_send, name="chat_send"),
    path("api/<int:conversation_id>/hide/", views.chat_hide, name="chat_hide"),
    path("api/<int:conversation_id>/members/", views.chat_group_members, name="chat_group_members"),
    path("api/<int:conversation_id>/members/add/", views.chat_group_add_members, name="chat_group_add_members"),
    path("api/<int:conversation_id>/members/<int:member_id>/remove/", views.chat_group_remove_member, name="chat_group_remove_member"),
    path("api/<int:conversation_id>/members/<int:member_id>/admin/", views.chat_group_set_admin, name="chat_group_set_admin"),
    path("api/message/<int:message_id>/edit/", views.chat_edit, name="chat_edit"),
    path("api/message/<int:message_id>/delete/", views.chat_delete, name="chat_delete"),
]
