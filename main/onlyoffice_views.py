import json
import os
import hashlib
import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

from .models import Deed


ALLOWED_EXTS = {".docx", ".doc", ".odt", ".rtf"}


def _abs_url(request, path: str) -> str:
    # Nginx/Gunicorn proxy bo‘lsa, build_absolute_uri to‘g‘ri ishlashi uchun:
    # settings.py da USE_X_FORWARDED_HOST va SECURE_PROXY_SSL_HEADER yoqilgan bo‘lishi kerak (pastda beraman)
    return request.build_absolute_uri(path)


def _ds_url(request) -> str:
    host = (request.get_host() or "").split(":")[0].lower()
    if host in ("127.0.0.1", "localhost"):
        return (getattr(settings, "ONLYOFFICE_DS_URL_LOCAL", "http://127.0.0.1")).rstrip("/")
    return (getattr(settings, "ONLYOFFICE_DS_URL_PROD", "http://127.0.0.1")).rstrip("/")


def _make_doc_key(deed: Deed) -> str:
    # date_edit auto_now -> har saqlanganda key yangilanadi
    ts = 0
    if getattr(deed, "date_edit", None):
        ts = int(deed.date_edit.timestamp())
    raw = f"deed:{deed.pk}:{ts}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@login_required
def deed_docx_edit(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)

    if not deed.file:
        raise Http404("DOCX fayl topilmadi")

    filename = os.path.basename(deed.file.name or "document.docx")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTS:
        raise Http404("Faqat Word hujjatlar")

    file_url = _abs_url(request, deed.file.url)
    callback_url = _abs_url(request, reverse("onlyoffice_callback", args=[deed.pk]))

    employee = getattr(request.user, "employee", None)
    user_id = str(request.user.pk)
    user_name = (getattr(employee, "full_name", None) or request.user.get_username() or "User")

    config = {
        "document": {
            "fileType": ext.lstrip("."),      # docx/doc/odt/rtf
            "key": _make_doc_key(deed),
            "title": filename,
            "url": file_url,
        },
        "documentType": "word",
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": callback_url,
            "user": {"id": user_id, "name": user_name},
        },
    }

    return render(request, "main/deed_edit.html", {
        "deed": deed,
        "ds_url": _ds_url(request),
        "config_json": json.dumps(config),
        "file_url": file_url,
        "callback_url": callback_url,
    })


@csrf_exempt
def onlyoffice_callback(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)

    try:
        data = json.loads((request.body or b"{}").decode("utf-8"))
    except Exception:
        return JsonResponse({"error": 1})

    # status ba’zan str bo‘lib keladi
    try:
        status = int(data.get("status"))
    except Exception:
        status = None

    url = data.get("url")

    # 2 = ready for saving, 6 = forceSave (agar yoqilgan bo‘lsa)
    if status in (2, 6) and url:
        try:
            r = requests.get(url, timeout=120)
            r.raise_for_status()

            # overwrite
            with open(deed.file.path, "wb") as f:
                f.write(r.content)

            deed.save()  # date_edit yangilanadi
            return JsonResponse({"error": 0})
        except Exception:
            return JsonResponse({"error": 1})

    return JsonResponse({"error": 0})
