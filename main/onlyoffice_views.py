# app/onlyoffice_views.py
import json
import os
import time
import jwt
import requests

from django.conf import settings
from django.http import JsonResponse, FileResponse, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Deed

DOCX_FIELD = "file"  # <<< sizda docx field nomi boshqacha bo‘lsa shu yerini almashtiring


def _get_docx(deed: Deed):
    f = getattr(deed, DOCX_FIELD, None)
    if not f:
        raise ValueError(f"Deed modelida '{DOCX_FIELD}' field topilmadi!")
    return f


def _public_base_url(request):
    # Siz foydalanyotgan asosiy domen (report.imv.uz)
    # callback ham shu orqali keladi
    return "https://report.imv.uz"


def deed_edit(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    base = _public_base_url(request)

    file_url = f"{base}/onlyoffice/file/{deed.id}/"
    callback_url = f"{base}/onlyoffice/callback/{deed.id}/"

    # ✅ STABIL KEY (time.time() YO‘Q!)
    # Fayl o‘zgarganda (mtime) o‘zgaradi, lekin har refreshda emas
    st = os.stat(docx.path)
    key = f"deed-{deed.id}-{st.st_size}-{int(st.st_mtime)}"

    config = {
        "document": {
            "fileType": "docx",
            "key": key,
            "title": os.path.basename(docx.name) or "document.docx",
            "url": file_url,
        },
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": callback_url,
            "user": {
                "id": str(getattr(request.user, "id", "0")),
                "name": getattr(request.user, "username", "user"),
            },
            "customization": {
                "forcesave": True,  # Saqlashni kuchaytiradi
            },
        },
    }

    token = jwt.encode(config, settings.ONLYOFFICE_JWT_SECRET, algorithm="HS256")

    # qaysi sahifaga qaytish (masalan ro‘yxat)
    back_url = request.GET.get("back") or request.META.get("HTTP_REFERER") or "/"

    return render(request, "onlyoffice/deed_edit.html", {
        "docserver": settings.ONLYOFFICE_DS_URL,
        "config_json": json.dumps(config),
        "token": token,
        "back_url": back_url,
    })


def onlyoffice_file(request, pk):
    """
    OnlyOffice docx’ni shu URL’dan yuklab oladi.
    Login talab qilmaymiz (aks holda 302 bo‘ladi va docx o‘rniga HTML ketadi).
    Xohlasangiz IP check yoqing.
    """
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    # ✅ ixtiyoriy: faqat ichki tarmoqdan ruxsat (yoqmoqchi bo‘lsangiz uncomment)
    # ip = request.META.get("REMOTE_ADDR")
    # allowed = {"127.0.0.1", "192.168.120.142", "172.17.0.1", "172.18.0.1"}
    # if ip not in allowed:
    #     return HttpResponseForbidden("Forbidden")

    return FileResponse(open(docx.path, "rb"), as_attachment=False, filename=os.path.basename(docx.name))


@csrf_exempt
@require_http_methods(["POST"])
def onlyoffice_callback(request, pk):
    """
    OnlyOffice save qilganda POST qiladi.
    status==2 bo‘lsa url’dan yuklab olib docx.path ga yozamiz.
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

        # 🔴 deed.save() ni key’ga bog‘lamadik, shuning uchun reload bo‘lmaydi
        return JsonResponse({"error": 0})

    return JsonResponse({"error": 0})
