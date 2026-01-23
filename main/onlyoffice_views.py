# app/onlyoffice_views.py
import json
import os
import jwt
import requests

from django.conf import settings
from django.http import JsonResponse, FileResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Deed


# ✅ Deed modelidagi docx field nomi:
DOCX_FIELD = "file"  # agar sizda docx_file bo'lsa => "docx_file"


def _abs(request, path: str) -> str:
    return request.build_absolute_uri(path)


def _get_docx(deed: Deed):
    f = getattr(deed, DOCX_FIELD, None)
    if not f:
        raise ValueError(f"Deed.{DOCX_FIELD} topilmadi!")
    return f


def deed_edit(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    base = "http://192.168.120.142:8000"  # ✅ LAN IP

    file_url = f"{base}/onlyoffice/file/{deed.id}/"
    callback_url = f"{base}/onlyoffice/callback/{deed.id}/"

    config = {
        "document": {
            "fileType": "docx",
            "key": f"deed-{deed.id}",
            "title": os.path.basename(docx.name),
            "url": file_url,
        },
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": callback_url,
            "user": {"id": str(request.user.id), "name": request.user.username},
        },
    }

    token = jwt.encode(config, settings.ONLYOFFICE_JWT_SECRET, algorithm="HS256")
    return render(request, "onlyoffice/deed_edit.html", {
        "docserver": settings.ONLYOFFICE_DS_URL,
        "config_json": json.dumps(config),
        "token": token,
    })



def onlyoffice_file(request, pk):
    """
    DocumentServer docx'ni yuklab olishi uchun endpoint.
    Xohlasangiz IP bo‘yicha cheklab qo‘ying (pastdagi komment).
    """
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    # ✅ ixtiyoriy: faqat ichki IP’lardan ruxsat
    # ip = request.META.get("REMOTE_ADDR")
    # if ip not in ["192.168.120.142", "172.17.0.1", "172.18.0.1", "127.0.0.1"]:
    #     return HttpResponseForbidden("Forbidden")

    return FileResponse(open(docx.path, "rb"), as_attachment=False, filename=os.path.basename(docx.name))


@csrf_exempt
@require_http_methods(["POST"])
def onlyoffice_callback(request, pk):
    """
    OnlyOffice "Save" qilganda shu yerga POST qiladi.
    status == 2 bo‘lsa: url dan docx ni yuklab olib, serverdagi faylni yangilaymiz.
    """
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    data = json.loads(request.body.decode("utf-8") or "{}")
    status = data.get("status")

    if status == 2:
        download_url = data.get("url")
        if not download_url:
            return JsonResponse({"error": 1})

        r = requests.get(download_url, timeout=120)
        r.raise_for_status()

        with open(docx.path, "wb") as f:
            f.write(r.content)

        # agar Deed’da updated_at bo‘lsa yangilanadi, bo‘lmasa ham zarar yo‘q
        deed.save()
        return JsonResponse({"error": 0})

    return JsonResponse({"error": 0})
