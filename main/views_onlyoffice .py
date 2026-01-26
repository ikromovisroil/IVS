# main/views_onlyoffice.py
import hashlib
import hmac
import json
import os
import time

import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt

try:
    import jwt
except Exception:
    jwt = None

from .models import Deed


def _abs_url(request, path: str) -> str:
    return request.build_absolute_uri(path)


def _ext(name: str) -> str:
    return (os.path.splitext(name)[1] or "").lower().strip(".")


def _hmac_token(deed_id: int, exp_ts: int) -> str:
    """
    token = HMAC_SHA256(secret, f"{id}:{exp}")
    """
    secret = settings.ONLYOFFICE["DOWNLOAD_TOKEN_SECRET"].encode("utf-8")
    msg = f"{deed_id}:{exp_ts}".encode("utf-8")
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _verify_hmac_token(deed_id: int, exp_ts: int, token: str) -> bool:
    if exp_ts < int(time.time()):
        return False
    good = _hmac_token(deed_id, exp_ts)
    return hmac.compare_digest(good, token or "")


def _oo_jwt(payload: dict) -> str:
    only = settings.ONLYOFFICE
    if not only.get("JWT_ENABLED"):
        return ""
    if jwt is None:
        raise RuntimeError("pyjwt o'rnatilmagan. pip install pyjwt")
    return jwt.encode(payload, only["JWT_SECRET"], algorithm="HS256")


@login_required
def deed_edit(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("DOCX fayl topilmadi")

    only = settings.ONLYOFFICE
    docserver = only["DOCSERVER_URL"].rstrip("/")

    # DocumentServer docx ni yuklab olishi uchun tokenli url beramiz
    exp = int(time.time()) + 60 * 30  # 30 minut
    token = _hmac_token(deed.pk, exp)
    file_url = _abs_url(request, reverse("onlyoffice_file", args=[deed.pk])) + f"?exp={exp}&token={token}"

    callback_url = _abs_url(request, reverse("onlyoffice_callback", args=[deed.pk]))

    # key: fayl yangilanganda o'zgarsin
    key_src = f"{deed.pk}:{deed.date_edit.timestamp()}:{deed.file.name}"
    key = hashlib.sha256(key_src.encode("utf-8")).hexdigest()

    config = {
        "document": {
            "fileType": _ext(deed.file.name) or "docx",
            "key": key,
            "title": os.path.basename(deed.file.name),
            "url": file_url,
        },
        "documentType": "word",
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": callback_url,
            "user": {
                "id": str(request.user.id),
                "name": (request.user.get_full_name() or request.user.username),
            },
            "customization": {
                "forcesave": True,
            },
        },
    }

    token_jwt = ""
    if only.get("JWT_ENABLED"):
        token_jwt = _oo_jwt(config)

    # editor yopilganda qayerga qaytsin
    return_url = request.GET.get("return") or "/"

    return render(request, "main/deed_edit.html", {
        "docserver": docserver,
        "config_json": json.dumps(config),
        "jwt_token": token_jwt,
        "return_url": return_url,
    })


def onlyoffice_file(request, pk: int):
    """
    DocumentServer shu endpointdan docx ni yuklab oladi.
    Login talab qilinmaydi, lekin token+exp tekshiriladi.
    """
    deed = get_object_or_404(Deed, pk=pk)

    exp = request.GET.get("exp", "")
    token = request.GET.get("token", "")
    if not exp.isdigit():
        return HttpResponse("Bad token", status=403)

    exp_i = int(exp)
    if not _verify_hmac_token(deed.pk, exp_i, token):
        return HttpResponse("Bad token", status=403)

    if not deed.file:
        raise Http404("Fayl yo'q")

    # Faylni qaytaramiz
    deed.file.open("rb")
    data = deed.file.read()
    deed.file.close()

    resp = HttpResponse(
        data,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    resp["Content-Disposition"] = f'inline; filename="{os.path.basename(deed.file.name)}"'
    return resp


@csrf_exempt
def onlyoffice_callback(request, pk: int):
    """
    DocumentServer -> callback
    status=2 (yoki 6/7) bo'lsa url beradi, biz uni yuklab olib Deed.file ga saqlaymiz.
    """
    deed = get_object_or_404(Deed, pk=pk)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": 1})

    only = settings.ONLYOFFICE

    # Agar JWT yoqqan bo'lsa, DS callback ham token yuboradi (ba'zan payload.token)
    if only.get("JWT_ENABLED"):
        tok = payload.get("token") or request.headers.get("Authorization", "").replace("Bearer ", "").strip()
        if not tok:
            return JsonResponse({"error": 1})
        try:
            jwt.decode(tok, only["JWT_SECRET"], algorithms=["HS256"])
        except Exception:
            return JsonResponse({"error": 1})

    status = payload.get("status")
    # 2 = saqlash kerak; 6/7 = forcesave holatlari
    if status in (2, 6, 7):
        url = payload.get("url")
        if url:
            try:
                r = requests.get(url, timeout=120)
                r.raise_for_status()
                new_name = os.path.basename(deed.file.name) or f"deed_{deed.pk}.docx"
                deed.file.save(new_name, ContentFile(r.content), save=True)
            except Exception:
                return JsonResponse({"error": 1})

    return JsonResponse({"error": 0})
