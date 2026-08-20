from django.urls import path
from .ajax_views import *
from .ajax_xlsx import *
from .sso_views import *
from .order_views import *
from .views import *
from .push_views import *
from .sanitizers import *
urlpatterns = [
    # =========================
    # ASOSIY SAHIFALAR
    # =========================
    path("", home, name="home"),
    path("profil/", profil, name="profil"),
    path("emp_status/", emp_status, name="emp_status"),
    path("technics_get/", technics_get, name="technics_get"),
    path("tex_status/", tex_status, name="tex_status"),
    path("technics/<int:pk>/", technics_detail, name="technics_detail"),
    path("files/", files, name="files"),

    # =========================
    # TEXNIKALAR
    # =========================
    path("barn_tex/", barn_tex, name="barn_tex"),
    path("barn_tex/create/", technics_create, name="technics_create"),
    path("barn_tex/delete/", technics_delete, name="technics_delete"),
    path("barn_tex/attach/", technics_attach, name="technics_attach"),
    path("barn_tex/<int:pk>/update/", technics_update, name="technics_update"),
    path("barn_tex/download/<int:pk>/", technics_download, name="technics_download"),

    # Qo‘shimcha texnikalar
    path("barn_tex/extra_tex_attach/", extra_tex_attach, name="extra_tex_attach"),
    path("barn_tex/extra_tex_detach/", extra_tex_detach, name="extra_tex_detach"),

    path("extra_tex/", extra_tex, name="extra_tex"),
    path("extra_tex/create/", extra_tex_create, name="extra_tex_create"),
    path("extra_tex/delete/", extra_tex_delete, name="extra_tex_delete"),
    path("extra_tex/attach/", extra_tex_attach, name="extra_tex_attach"),
    path("extra_tex/<int:pk>/update/", extra_tex_update, name="extra_tex_update"),

    # =========================
    # MATERIALLAR
    # =========================
    path("barn_mat/", barn_mat, name="barn_mat"),
    path("barn_mat/create/", material_create, name="material_create"),
    path("barn_mat/update/<int:pk>/", material_update, name="material_update"),
    path("barn_mat/attach/", material_attach, name="material_attach"),
    path("barn_mat/delete/", material_delete, name="material_delete"),
    path("mat_post/", mat_post, name="mat_post"),
    path("mat_info/", mat_info, name="mat_info"),
    path("mat_arxiv/", mat_arxiv, name="mat_arxiv"),
    path("mat_arxiv/post/", mat_arxiv_post, name="mat_arxiv_post"),
    path("mat_arxiv/delete/<int:pk>/", mat_arxiv_delete, name="mat_arxiv_delete"),

    # =========================
    # NOTIFIKATSIYA / STATUS
    # =========================
    path("order/seen/", order_mark_seen, name="order_mark_seen"),
    path("deed/<int:pk>/action/", deed_action, name="deed_action"),
    path("deedconsent_action/<int:pk>/action/", deedconsent_action, name="deedconsent_action"),
    path("deed/status/<str:code>/<int:pk>/", deed_status, name="deed_status"),
    path("deed/<int:pk>/edit/", deed_edit, name="deed_edit"),

    # =========================
    # CONTACT
    # =========================
    path("contact/", contact, name="contact"),
    path("contact/arxiv/", contact_arxiv, name="contact_arxiv"),
    path("contact/user/", contact_user, name="contact_user"),
    path("contact/user/arxiv/", contact_user_arxiv, name="contact_user_arxiv"),
    path("contact/post/deed/", contact_post_deed, name="contact_post_deed"),
    path("contact/agrement/", contact_agrement, name="contact_agrement"),
    path("contact/agrement/arxiv/", contact_agrement_arxiv, name="contact_agrement_arxiv"),

    # =========================
    # AJAX / FILTER / DINAMIK
    # =========================
    path("material/cart/add/", add_material_to_cart, name="add_material_to_cart"),
    path("order/sender/basket/delete/", delete_material_from_cart, name="delete_material_from_cart"),

    path("ajax/load-departments/", ajax_load_departments, name="ajax_load_departments"),
    path("ajax/load-directorate/", ajax_load_directorate, name="ajax_load_directorate"),
    path("ajax/load-division/", ajax_load_division, name="ajax_load_division"),
    path("ajax/load-categories/", ajax_load_categories, name="ajax_load_categories"),

    path("ajax/employees-org/", ajax_employees_org, name="ajax_employees_org"),
    path("ajax/ajax_agreements_employees/", ajax_agreements_employees, name="ajax_agreements_employees"),
    path("ajax/get-dep-employees/", get_department_employees, name="get_dep_employees"),

    path("ajax/dep_signatory/", ajax_dep_signatory, name="ajax_dep_signatory"),
    path("ajax/dep_negotiator/", ajax_dep_negotiator, name="ajax_dep_negotiator"),

    path("ajax/akt-materials/", ajax_akt_materials, name="ajax_akt_materials"),
    path("ajax/svod_materials/", ajax_svod_materials, name="ajax_svod_materials"),
    path("ajax/reestr_materials/", ajax_reestr_materials, name="ajax_reestr_materials"),

    path("ajax/ajax_document/", ajax_document_preview, name="ajax_document_preview"),
    path("ajax/ordermaterial/<int:pk>/delete/", ordermaterial_delete, name="ordermaterial_delete"),
    path("ajax/search-tex/", ajax_search_tex, name="ajax_search_tex"),
    path("ajax/check-new/", order_check_new, name="order_check_new"),
    path("ajax/check-all/", order_check_all, name="order_check_all"),
    path("ajax/sender-technics/", ajax_sender_technics, name="ajax_sender_technics"),
    path('ajax/employees-org-user-region/', ajax_employees_org_user_region, name='ajax_employees_org_user_region'),
    path("deed/<int:deed_id>/toggle-user-edit/", toggle_user_edit, name="toggle_user_edit"),

    # =========================
    # HUJJATLAR
    # =========================
    path("document/", document_get, name="document_get"),
    path("document/post/", document_post, name="document_post"),

    # AKT
    path("akt/", akt_get, name="akt_get"),
    path("akt/post/", akt_post, name="akt_post"),

    # SVOD
    path("svod/", svod_get, name="svod_get"),
    path("svod/post/", svod_post, name="svod_post"),

    # REESTR
    path("reestr/", reestr_get, name="reestr_get"),
    path("reestr/post/", reest_post, name="reest_post"),

    # =========================
    # ZAYAVKA / ORDER create_order_sender_from   order_sender_user
    # =========================
    path("order/sender/", order_sender, name="order_sender"),
    path("order/sender/decide/<int:pk>/", order_decide, name="order_decide"),
    path("order/sender/arxiv/", order_sender_arxiv, name="order_sender_arxiv"),
    path("order/sender/user/", order_sender_user, name="order_sender_user"),

    path("order/sender/barn/", order_sender_barn, name="order_sender_barn"),
    path("order/sender/arxiv/barn/", order_sender_arxiv_barn, name="order_sender_arxiv_barn"),
    path("order/sender/decide/barn/<int:pk>/", order_decide_barn, name="order_decide_barn"),
    path("order/sender/material/barn/", order_sender_material_barn, name="order_sender_material_barn"),
    path("order/sender/basket/barn/", order_sender_basket_barn, name="order_sender_basket_barn"),
    path("order/sender/create/form/", create_order_sender_from, name="create_order_sender_from"),

    path("order/agrement/", order_agrement, name="order_agrement"),
    path("order/agrement/material/", order_agrement_material, name="order_agrement_material"),
    path("order/agrement/arxiv/", order_agrement_arxiv, name="order_agrement_arxiv"),

    path("order/receiver/barn/", order_receiver_barn, name="order_receiver_barn"),
    path("order/receiver/accepted/barn/<int:pk>/", order_accepted_barn, name="order_accepted_barn"),
    path("order/receiver/activ/barn/", order_receiver_activ_barn, name="order_receiver_activ_barn"),
    path("order/receiver/arxiv/barn/", order_receiver_arxiv_barn, name="order_receiver_arxiv_barn"),
    path("order/receiver/material/barn/", order_material_barn, name="order_material_barn"),

    path("order/receiver/", order_receiver, name="order_receiver"),
    path("order/receiver/accepted/<int:pk>/", order_accepted, name="order_accepted"),
    path("order/receiver/activ/", order_receiver_activ, name="order_receiver_activ"),
    path("order/receiver/arxiv/", order_receiver_arxiv, name="order_receiver_arxiv"),
    path("order/receiver/deed/<int:pk>/", order_receiver_deed, name="order_receiver_deed"),
    path("order/receiver/post/", order_receiver_deed_post, name="order_receiver_deed_post"),

    path("order/post/", order_post, name="order_post"),
    path("order/user/post/", order_user_post, name="order_user_post"),
    path("order/material/", order_material_post, name="order_material_post"),

    # =========================
    # SSO
    # =========================
    path("sso/login/", login_page, name="login"),
    path("sso/start/login/", sso_start_login, name="sso_start_login"),
    path("sso/start/approve/", sso_start_approve, name="sso_start_approve"),
    path("sso/start/", sso_start, name="sso_start"),
    path("sso/callback/", sso_callback, name="sso_callback"),
    path("sso/exchange/", sso_exchange, name="sso_exchange"),
    path("sso/eimzo-return/", eimzo_return, name="eimzo_return"),
    path("sso/logout/", logout, name="logout"),

    # =========================
    # EXPORT
    # =========================
    path("export/technics_xlsx/", export_technics_xlsx, name="export_technics_xlsx"),
    path("export/material_xlsx/", export_material_xlsx, name="export_material_xlsx"),

    path('employe/create/', employe_create, name='employe_create'),

    path("material/import/", material_import_page, name="material_import_page"),
    path("material/import/post/", material_import, name="material_import"),

    path("employee/", employee, name="employee"),
    path("employee/create/", employee_create, name="employee_create"),
    path("employee/update/", employee_update, name="employee_update"),
    path("employee/delete/", employee_delete, name="employee_delete"),
    path("employee/permission/", employee_permission, name="employee_permission"),

    path('sw.js', service_worker_js, name='service_worker_js'),
    path('ajax/push-subscribe/', save_push_subscription, name='save_push_subscription'),
    path('ajax/push-unsubscribe/', remove_push_subscription, name='remove_push_subscription'),
]

