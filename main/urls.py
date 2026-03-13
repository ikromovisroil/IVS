from django.urls import path
from .views import *
from .ajax_views import *
from .ajax_xlsx import *
from .sso_views import *

urlpatterns = [
    path("", home, name="home"),
    path('profil/', profil, name='profil'),
    path('emp_status/', emp_status, name='emp_status'),
    path('technics_get/', technics_get, name='technics_get'),
    path('tex_status/', tex_status, name='tex_status'),

    #texnikalar
    path('barn_tex/', barn_tex, name='barn_tex'),
    path("barn_tex/create/", technics_create, name="technics_create"),
    path("barn_tex/delete/", technics_delete, name="technics_delete"),
    path("barn_tex/attach/", technics_attach, name="technics_attach"),
    path("barn_tex/<int:pk>/update/", technics_update, name="technics_update"),
    path("barn_tex/extra_tex_attach/", extra_tex_attach, name="extra_tex_attach"),
    path("barn_tex/extra_tex_detach/", extra_tex_detach, name="extra_tex_detach"),

    # texnikalar
    path('extra_tex/', extra_tex, name='extra_tex'),
    path("extra_tex/create/", extra_tex_create, name="extra_tex_create"),
    path("extra_tex/delete/", extra_tex_delete, name="extra_tex_delete"),
    path("extra_tex/attach/", extra_tex_attach, name="extra_tex_attach"),
    path("extra_tex/<int:pk>/update/", extra_tex_update, name="extra_tex_update"),

    # materialar
    path('barn_mat/', barn_mat, name='barn_mat'),
    path("barn_mat/create/", material_create, name="material_create"),
    path("barn_mat/update/<int:pk>/", material_update, name="material_update"),
    path("barn_mat/attach/", material_attach, name="material_attach"),
    path("barn_mat/delete/", material_delete, name="material_delete"),


    # NOTIFIKATSIYA
    path('deed/seen/', deed_mark_seen, name="deed_mark_seen"),
    path('order/seen/', order_mark_seen, name="order_mark_seen"),
    path("deed/<int:pk>/action/", deed_action, name="deed_action"),
    path("deedconsent_action/<int:pk>/action/", deedconsent_action, name="deedconsent_action"),
    path("deed/status/<str:code>/", deed_status, name="deed_status"),


    # CONTACT
    path('contact/', contact, name='contact'),
    path('contact/arxiv/', contact_arxiv, name='contact_arxiv'),
    path('contact_user/', contact_user, name='contact_user'),
    path('contact_user/arxiv/', contact_user_arxiv, name='contact_user_arxiv'),
    path('contact_agrement/', contact_agrement, name='contact_agrement'),
    path('contact_agrement/arxiv/', contact_agrement_arxiv, name='contact_agrement_arxiv'),
    path("get-dep-employees/", get_department_employees, name="get_dep_employees"),


    # FILTER AJAX
    path('ajax/load-departments/', ajax_load_departments, name='ajax_load_departments'),
    path('ajax/load-directorate/', ajax_load_directorate, name='ajax_load_directorate'),
    path('ajax/load-division/', ajax_load_division, name='ajax_load_division'),
    path("ajax/employees-org/", ajax_employees_org, name="ajax_employees_org"),
    path("ajax/ajax_agreements_employees/", ajax_agreements_employees, name="ajax_agreements_employees"),
    path("ajax/akt-materials/", ajax_akt_materials, name="ajax_akt_materials"),
    path("ajax/svod_materials/", ajax_svod_materials, name="ajax_svod_materials"),
    path("ajax/reestr_materials/", ajax_reestr_materials, name="ajax_reestr_materials"),
    path("ajax/ajax_document/", ajax_document_preview, name="ajax_document_preview"),
    path("ajax/dep_signatory/", ajax_dep_signatory, name="ajax_dep_signatory"),
    path("ajax/dep_negotiator/", ajax_dep_negotiator, name="ajax_dep_negotiator"),
    path("ordermaterial/<int:pk>/delete/", ordermaterial_delete, name="ordermaterial_delete"),
    path("ajax/search-tex/", ajax_search_tex, name="ajax_search_tex"),

    # DOCUMENT
    path('document/', document_get, name='document_get'),
    path('document/document_post/', document_post, name='document_post'),

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
    path("order_sender/decide/<int:pk>/", order_decide, name="order_decide"),
    path('order_sender_arxiv/', order_sender_arxiv, name='order_sender_arxiv'),
    path('order_receiver/', order_receiver, name='order_receiver'),
    path('order_receiver/accepted/<int:pk>/', order_accepted, name='order_accepted'),
    path('order_receiver_activ/', order_receiver_activ, name='order_receiver_activ'),
    path('order_receiver_arxiv/', order_receiver_arxiv, name='order_receiver_arxiv'),
    path('order_receiver/order_receiver_deed/<int:pk>/', order_receiver_deed, name='order_receiver_deed'),
    path('order_receiver/order_receiver_deed_post/', order_receiver_deed_post, name='order_receiver_deed_post'),
    path('order_accepted/<int:pk>/', order_accepted, name='order_accepted'),
    path('order_post/', order_post, name='order_post'),
    path('ordermaterial_post/', ordermaterial_post, name='ordermaterial_post'),
    path("order/approved/", order_approved, name="order_approved"),

    # SSO
    path("sso/login/", login_page, name="login_page"),
    path("sso/start/login/", sso_start_login, name="sso_start_login"),
    path("sso/start/approve/", sso_start_approve, name="sso_start_approve"),
    path("sso/start/", sso_start, name="sso_start"),
    path("sso/callback/", sso_callback, name="sso_callback"),
    path("sso/exchange/", sso_exchange, name="sso_exchange"),
    path("sso/eimzo-return/", eimzo_return, name="eimzo_return"),
    path("sso/logout/", logout, name="logout"),

    path("deed/<int:pk>/edit/", deed_edit, name="deed_edit"),

    # egzel
    path("export/technics_xlsx/", export_technics_xlsx, name="export_technics_xlsx"),
    path("export/material_xlsx/", export_material_xlsx, name="export_material_xlsx"),
]
