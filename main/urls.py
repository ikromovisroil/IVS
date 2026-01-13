from django.urls import path
from .views import *
from .ajax_views import *

urlpatterns = [
    path("", home, name="home"),
    path('profil/', profil, name='profil'),
    path('index/', index, name='index'),
    path('barn/', barn, name='barn'),

    # NOTIFIKATSIYA
    path('deed/seen/', deed_mark_seen, name="deed_mark_seen"),
    path('order/seen/', order_mark_seen, name="order_mark_seen"),
    path("deed/<int:pk>/action/", deed_action, name="deed_action"),
    path("deedconsent_action/<int:pk>/action/", deedconsent_action, name="deedconsent_action"),

    # CONTACT
    path('contact/', contact, name='contact'),
    path("get_employee_files/", get_employee_files, name="get_employee_files"),
    path("get-dep-employees/", get_department_employees, name="get_dep_employees"),


    # DEED
    path('deed_post/', deed_post, name='deed_post'),

    # TECHNICS
    path('technics/', technics, name='technics'),
    path('technics/<slug:slug>/', technics, name='technics'),

    # FILTER AJAX
    path('ajax/load-departments/', ajax_load_departments, name='ajax_load_departments'),
    path('ajax/load-directorate/', ajax_load_directorate, name='ajax_load_directorate'),
    path('ajax/load-division/', ajax_load_division, name='ajax_load_division'),
    path("ajax/employees/", ajax_load_employees, name="ajax_load_employees"),


    # ORGANIZATION
    path('organization/<slug:slug>/', organization, name='organization'),

    # DOCUMENT
    path('document/', document_get, name='document_get'),
    path('document/document_post/', document_post, name='document_post'),
    path('document/technics_count/', get_technics_count, name='get_technics_count'),

    # AKT
    path('akt/', akt_get, name='akt_get'),
    path('akt/akt_post/', akt_post, name='akt_post'),

    # SENDER
    path('svod/', svod_get, name='svod_get'),
    path('svod/akt_post/', svod_post, name='svod_post'),

    # Reestr
    path('reestr/', reestr_get, name='reestr_get'),
    path('reestr/reestr_post/', reestr_post, name='reestr_post'),

    # ZAYAVKA
    path('order_sender/', order_sender, name='order_sender'),
    path('order_receiver/', order_receiver, name='order_receiver'),
    path('order_post/', order_post, name='order_post'),
    path('ordermaterial_post/', ordermaterial_post, name='ordermaterial_post'),
    path('order/finish/<int:pk>/', order_finish, name='order_finish'),
    path('order/rejected/<int:pk>/', order_rejected, name='order_rejected'),
    path("order/approved/", order_approved, name="order_approved"),
    path("get_goals/<int:topic_id>/", get_goals, name="get_goals"),

    # SSO
    path("sso/start/", sso_start_page, name="sso_start_page"),     # JS: PKCE va redirect
    path("sso/callback/", sso_callback_page, name="sso_callback"), # JS: code ni olib exchange ga yuboradi
    path("sso/exchange/", sso_exchange_and_finish, name="sso_exchange_and_finish"),

]
