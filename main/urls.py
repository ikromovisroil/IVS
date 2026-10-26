"""
Server tomondagi qolgan manzillar. Asosiy interfeys — React (/app/), ma'lumot — /api/v1/.

Bu yerda faqat: bosh sahifa yo'naltirishi, SSO oqimi, QR kod bilan ochiladigan ommaviy sahifalar
(texnika va hujjat holati) va hisobot POST funksiyalari qaytaradigan `redirect("<nom>")` nomlari
(ular `spa_redirect` bilan yangi interfeysga o'tkazadi).
"""
from django.urls import path
from .sso_views import *
from .views import *

urlpatterns = [
    path("", home, name="home"),

    # Ommaviy sahifalar (QR kod / PDF ichidagi havolalar)
    path("technics/<int:pk>/", technics_detail, name="technics_detail"),
    path("deed/status/<str:code>/<int:pk>/", deed_status, name="deed_status"),

    # SSO
    path("sso/login/", login_page, name="login"),
    path("sso/start/login/", sso_start_login, name="sso_start_login"),
    path("sso/start/approve/", sso_start_approve, name="sso_start_approve"),
    path("sso/start/", sso_start, name="sso_start"),
    path("sso/callback/", sso_callback, name="sso_callback"),
    path("sso/exchange/", sso_exchange, name="sso_exchange"),
    path("sso/eimzo-return/", eimzo_return, name="eimzo_return"),
    path("sso/logout/", logout, name="logout"),

    # Eski sahifa manzillari → yangi interfeys (hisobot POST funksiyalari shu nomlarga redirect qiladi)
    path("files/", spa_redirect, name="files"),
    path("materil/service/", spa_redirect, name="material_service"),
    path("contact/user/", spa_redirect, name="contact_user"),
    path("document/", spa_redirect, name="document_get"),
    path("akt/", spa_redirect, name="akt_get"),
    path("svod/", spa_redirect, name="svod_get"),
    path("reestr/", spa_redirect, name="reestr_get"),
    path("service/", spa_redirect, name="service_get"),
    path("order/sender/", spa_redirect, name="order_sender"),
    path("order/receiver/", spa_redirect, name="order_receiver"),
    path("employee/", spa_redirect, name="employee"),
]
