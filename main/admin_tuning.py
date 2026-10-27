"""Admin ro'yxatlari katta jadvallarda qotib qolmasligi uchun umumiy sozlamalar (config/urls.py da bir marta chaqiriladi)."""
from django.contrib import admin

APPS = {"main", "chat", "core"}
PER_PAGE = 50


def lighten_admin():
    """Har bir ro'yxatda: ko'pi bilan PER_PAGE qator, qatorlar sonini alohida COUNT bilan hisoblamaslik,
    va list_display dagi bog'langan maydonlar (FK) uchun select_related (har qator uchun alohida so'rov ketmasin)."""
    for model, ma in admin.site._registry.items():
        if model._meta.app_label not in APPS:
            continue
        ma.list_per_page = min(ma.list_per_page, PER_PAGE)
        ma.show_full_result_count = False
        if ma.list_select_related:
            continue
        related = []
        for name in ma.list_display:
            if not isinstance(name, str):
                continue
            try:
                field = model._meta.get_field(name)
            except Exception:
                continue
            if field.is_relation and (field.many_to_one or field.one_to_one) and field.concrete:
                related.append(name)
        if related:
            ma.list_select_related = tuple(related)
