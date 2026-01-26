import hashlib
import hmac
import os
import time
from urllib.parse import urlencode, quote

import requests
from xml.etree import ElementTree as ET

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Deed


def _abs_url(request, path: str) -> str:
    return request.build_absolute_uri(path)


def _make_access_token(deed_id: int, user_id: int | None, ttl_seconds: int = 3600) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = f"{deed_id}.{user_id or 0}.{exp}"
    sig = hmac.new(
        settings.WOPI_TOKEN_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{sig}"


def _verify_access_token(token: str, deed_id: int) -> bool:
    try:
        a, b, c, sig = token.split(".")
        did = int(a)
        exp = int(c)
        if did != int(deed_id):
            return False
        if exp < int(time.time()):
            return False

        payload = f"{a}.{b}.{c}"
        expected = hmac.new(
            settings.WOPI_TOKEN_SECRET.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, sig)
    except Exception:
        return False


def _collabora_edit_url_for_docx() -> str:
    """
    Collabora discovery dan docx uchun edit urlsrc ni olib beradi.
    settings.COLLABORA_URL misol:
      - http://10.10.1.25:9980
      - https://collabora.example.uz
    """
    discovery_url = settings.COLLABORA_URL.rstrip("/") + "/hosting/discovery"
    r = requests.get(discovery_url, timeout=10)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    # discovery XML da action ext="docx" name="edit"
    for action in root.iter():
        if action.tag.endswith("action"):
            ext = action.attrib.get("ext")
            name = action.attrib.get("name")
            if ext == "docx" and name == "edit":
                return action.attrib["urlsrc"]

    # fallback: docx topilmasa
    raise RuntimeError("Collabora discovery ichidan docx edit urlsrc topilmadi")


def collabora_editor(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("DOCX fayl topilmadi")

    user_id = getattr(getattr(request, "user", None), "id", None)
    token = _make_access_token(deed.id, user_id, ttl_seconds=3600)

    # ✅ WOPISrc bu /wopi/files/<id> bo‘lishi shart (CheckFileInfo endpoint)
    wopi_src = _abs_url(request, reverse("wopi_file_info", args=[deed.id]))

    # Collabora discovery urlsrc odatda shunaqa bo‘ladi:
    # https://collabora.../browser/XYZ/cool.html?WOPISrc=<WOPISrc>&...
    urlsrc = _collabora_edit_url_for_docx()

    # urlsrc ichida odatda WOPISrc=<...> bo‘sh joy bilan keladi.
    # Biz WOPISrc ni URL-encode qilib joylaymiz:
    # urlsrc dagi "<...>" qismiga to‘g‘ridan-to‘g‘ri biriktiramiz.
    # Eng oddiy: urlsrc ga WOPISrc qiymatini qo‘shib yuborish:
    qs = urlencode({
        "WOPISrc": wopi_src,
        "access_token": token,
    })

    # urlsrc ba’zan allaqachon ? bilan tugaydi
    if "?" in urlsrc:
        editor_url = urlsrc + qs
    else:
        editor_url = urlsrc + "?" + qs

    return render(request, "main/deed_edit.html", {"deed": deed, "editor_url": editor_url})


@csrf_exempt
@require_http_methods(["GET"])
def wopi_check_file_info(request, pk: int):
    token = request.GET.get("access_token", "")
    if not _verify_access_token(token, pk):
        return HttpResponseForbidden("Bad token")

    deed = get_object_or_404(Deed, pk=pk)
    file_path = deed.file.path
    if not os.path.exists(file_path):
        raise Http404("File not found")

    stat = os.stat(file_path)

    data = {
        "BaseFileName": os.path.basename(file_path),
        "Size": stat.st_size,
        "Version": str(int(stat.st_mtime)),
        "OwnerId": "IVS",
        "UserId": str(getattr(getattr(request, "user", None), "id", "0")),
        "UserFriendlyName": getattr(getattr(request, "user", None), "username", "IVS User"),

        "UserCanWrite": True,
        "ReadOnly": False,

        # Collabora bilan yaxshi ishlashi uchun:
        "SupportsUpdate": True,
        "SupportsLocks": False,
    }
    return JsonResponse(data)


@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def wopi_file_contents(request, pk: int):
    token = request.GET.get("access_token", "")
    if not _verify_access_token(token, pk):
        return HttpResponseForbidden("Bad token")

    deed = get_object_or_404(Deed, pk=pk)
    file_path = deed.file.path
    if not os.path.exists(file_path):
        raise Http404("File not found")

    if request.method == "GET":
        with open(file_path, "rb") as f:
            content = f.read()
        resp = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        resp["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
        resp["X-WOPI-ItemVersion"] = str(int(os.stat(file_path).st_mtime))
        return resp

    # ✅ Collabora ko‘pincha POST yuboradi va header orqali override qiladi:
    # X-WOPI-Override: PUT
    override = (request.headers.get("X-WOPI-Override") or "").upper()
    if request.method in ("PUT", "POST") and override in ("PUT", ""):
        new_content = request.body
        if not new_content:
            return JsonResponse({"error": "Empty body"}, status=400)

        tmp_path = file_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(new_content)
        os.replace(tmp_path, file_path)

        stat = os.stat(file_path)
        resp = JsonResponse({"Status": "OK", "Version": str(int(stat.st_mtime))})
        resp["X-WOPI-ItemVersion"] = str(int(stat.st_mtime))
        return resp

    return JsonResponse({"error": "Unsupported operation"}, status=400)
