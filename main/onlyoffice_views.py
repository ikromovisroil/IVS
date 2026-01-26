# app/onlyoffice_views.py
import hashlib
import json
import os
import time

import jwt
import requests

from django.conf import settings
from django.http import FileResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Deed

DOCX_FIELD = "file"  # sizda docx_file bo'lsa => "docx_file"


def _get_docx(deed: Deed):
    f = getattr(deed, DOCX_FIELD, None)
    if not f:
        raise ValueError(f"Deed.{DOCX_FIELD} topilmadi!")
    return f


def _public_url(path: str) -> str:
    # settings.PUBLIC_BASE_URL oxirida / bo‘lmasin
    base = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}{path}"


def _stable_doc_key(deed: Deed, docx_path: str, docx_name: str) -> str:
    """
    OnlyOffice `document.key` barqaror bo‘lishi kerak.
    Fayl o'zgarsa — key ham o'zgaradi.
    """
    try:
        mtime = os.path.getmtime(docx_path)
    except FileNotFoundError:
        mtime = time.time()

    src = f"deed:{deed.id}:{docx_name}:{mtime}"
    return hashlib.sha256(src.encode("utf-8")).hexdigest()


# ----------------------------
# Oddiy sahifalar: list + create blank
# ----------------------------
def deed_list(request):
    deeds = Deed.objects.order_by("-id")
    return render(request, "main/deed_list.html", {"deeds": deeds})


def deed_create_blank(request):
    """
    0 dan blank docx yaratib beradi (minimal).
    Real loyihada: template docx’dan ko‘chirasiz yoki upload qilasiz.
    """
    from django.core.files.base import ContentFile

    deed = Deed.objects.create(title="Yangi hujjat")

    # Minimal docx skeleton (Word ochadi)
    # Bu haqiqiy DOCX zip format, lekin minimal usul sifatida:
    # Siz yaxshisi tayyor "blank.docx" faylni static’dan copy qiling.
    # Hozir esa eng oson yo'l: tayyor blank.docx ni diskda tuting.
    blank_path = os.path.join(os.path.dirname(__file__), "blank.docx")
    if not os.path.exists(blank_path):
        # Agar blank.docx bo'lmasa — xatolik chiqarmasdan oddiy "upload qiling" degan variant.
        # Siz bir marta blank.docx yaratib shu papkaga qo'yib qo'ying.
        return HttpResponseForbidden("blank.docx topilmadi. app/blank.docx qo'ying!")

    with open(blank_path, "rb") as bf:
        deed.file.save(f"deed_{deed.id}.docx", ContentFile(bf.read()), save=True)

    return redirect("deed_edit", pk=deed.id)


# ----------------------------
# OnlyOffice Editor sahifasi
# ----------------------------
def deed_edit(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    if not docx or not getattr(docx, "path", None) or not os.path.exists(docx.path):
        return HttpResponseForbidden("DOCX fayl topilmadi!")

    file_url = _public_url(f"/onlyoffice/file/{deed.id}/")
    callback_url = _public_url(f"/onlyoffice/callback/{deed.id}/")

    doc_key = _stable_doc_key(deed, docx.path, docx.name)

    config = {
        "document": {
            "fileType": "docx",
            "key": doc_key,
            "title": os.path.basename(docx.name),
            "url": file_url,
        },
        "documentType": "word",
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": callback_url,
            "user": {
                "id": str(request.user.id) if request.user.is_authenticated else "0",
                "name": request.user.username if request.user.is_authenticated else "Guest",
            },
            # ixtiyoriy: qaytish tugmasi (OnlyOffice ichidagi)
            "customization": {
                "forcesave": True,  # save ko‘proq ishonchli
            },
        },
    }

    token = jwt.encode(config, settings.ONLYOFFICE_JWT_SECRET, algorithm="HS256")

    return render(request, "main/deed_edit.html", {
        "docserver": settings.ONLYOFFICE_DS_URL.rstrip("/"),
        "config_json": json.dumps(config),
        "token": token,
    })


# ----------------------------
# DocumentServer docx ni yuklab oladigan endpoint
# ----------------------------
def onlyoffice_file(request, pk):
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    if not docx or not os.path.exists(docx.path):
        return HttpResponseForbidden("File not found")

    # ixtiyoriy: faqat LAN ip ruxsat
    # ip = request.META.get("REMOTE_ADDR")
    # if ip not in ["192.168.120.142", "127.0.0.1", "172.17.0.1", "172.18.0.1"]:
    #     return HttpResponseForbidden("Forbidden")

    return FileResponse(open(docx.path, "rb"), as_attachment=False, filename=os.path.basename(docx.name))


# ----------------------------
# Callback: Save bosilganda keladi
# ----------------------------
@csrf_exempt
@require_http_methods(["POST"])
def onlyoffice_callback(request, pk):
    """
    OnlyOffice Save bo‘lganda POST qiladi.
    status==2: document saved, url dan docx ni yuklab olamiz.
    """
    deed = get_object_or_404(Deed, pk=pk)
    docx = _get_docx(deed)

    # ✅ JWT tekshirish (DocumentServer JWT yoqilgan bo'lsa)
    # Ko‘pincha Authorization: Bearer <token> keladi.
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        bearer = auth.split(" ", 1)[1].strip()
        try:
            jwt.decode(bearer, settings.ONLYOFFICE_JWT_SECRET, algorithms=["HS256"])
        except Exception:
            return JsonResponse({"error": 1})

    data = json.loads(request.body.decode("utf-8") or "{}")
    status = data.get("status")

    # status 2 bo'lsa saqlangan
    if status == 2:
        download_url = data.get("url")
        if not download_url:
            return JsonResponse({"error": 1})

        r = requests.get(download_url, timeout=120)
        r.raise_for_status()

        # Serverdagi docx ni yangilaymiz
        with open(docx.path, "wb") as f:
            f.write(r.content)

        deed.save()
        return JsonResponse({"error": 0})

    # boshqa statuslarda ham error=0 qaytaramiz
    return JsonResponse({"error": 0})
