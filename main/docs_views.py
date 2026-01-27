import hashlib
import json
import os
import time

import jwt
import requests

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Deed


def _abs_url(request, path: str) -> str:
    # nginx https bo‘lsa, settings'dagi SECURE_PROXY_SSL_HEADER sabab https beradi
    return request.build_absolute_uri(path)


def _file_ext(name: str) -> str:
    return (os.path.splitext(name)[1] or "").lower().lstrip(".")


def _doc_key(deed: Deed) -> str:
    """
    OnlyOffice "key" — dokument versiyasi o‘zgarganda o‘zgarishi kerak.
    Eng sodda: file mtime + pk.
    """
    try:
        mtime = int(os.path.getmtime(deed.file.path))
    except Exception:
        mtime = int(time.time())
    raw = f"deed:{deed.pk}:{mtime}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _jwt_token(payload: dict) -> str:
    secret = getattr(settings, "ONLYOFFICE_JWT_SECRET", "")
    if not secret:
        return ""
    # pyjwt 2.x -> str qaytaradi
    return jwt.encode(payload, secret, algorithm="HS256")


@login_required
def onlyoffice_file(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("File not found")

    # DocServer bu URL ni chaqirib docx’ni oladi
    resp = FileResponse(open(deed.file.path, "rb"))
    resp["Content-Disposition"] = f'attachment; filename="{os.path.basename(deed.file.name)}"'
    return resp


@login_required
def deed_edit(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("File not found")

    docserver = getattr(settings, "ONLYOFFICE_DOCSERVER", "").rstrip("/")
    if not docserver:
        raise Http404("ONLYOFFICE_DOCSERVER is not set")

    filename = os.path.basename(deed.file.name)
    ext = _file_ext(filename) or "docx"

    file_url = _abs_url(request, f"/onlyoffice/file/{deed.pk}/")
    callback_url = _abs_url(request, f"/onlyoffice/callback/{deed.pk}/")

    config = {
        "documentType": "word",
        "document": {
            "title": filename,
            "url": file_url,
            "fileType": ext,
            "key": _doc_key(deed),
        },
        "editorConfig": {
            "mode": "edit",
            "callbackUrl": callback_url,
            "user": {
                "id": str(request.user.id),
                "name": getattr(request.user, "username", "user"),
            },
            "customization": {
                "forcesave": True,
                "autosave": True,
                "compactToolbar": False,
            },
        },
    }

    token = ""
    if getattr(settings, "ONLYOFFICE_JWT_SECRET", ""):
        token = _jwt_token(config)

    return render(
        request,
        "main/deed_edit.html",
        {
            "deed": deed,
            "docserver": docserver,
            "config_json": json.dumps(config),
            "token": token,
        },
    )


@csrf_exempt
@require_http_methods(["POST"])
def onlyoffice_callback(request, pk: int):
    """
    OnlyOffice status:
      2 = MustSave
      6 = MustForceSave
    Shu statuslarda data.url bo‘ladi -> docx’ni yuklab olamiz va serverga overwrite qilamiz.
    """
    deed = get_object_or_404(Deed, pk=pk)

    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return JsonResponse({"error": 1})

    status = data.get("status")
    if status in (2, 6):
        new_file_url = data.get("url")
        if not new_file_url:
            return JsonResponse({"error": 1})

        try:
            r = requests.get(new_file_url, stream=True, timeout=120)
            r.raise_for_status()

            os.makedirs(os.path.dirname(deed.file.path), exist_ok=True)
            with open(deed.file.path, "wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk:
                        f.write(chunk)

            deed.save(update_fields=["updated_at"])
        except Exception:
            return JsonResponse({"error": 1})

    return JsonResponse({"error": 0})
