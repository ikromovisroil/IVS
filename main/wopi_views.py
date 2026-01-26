import hashlib
import hmac
import os
import time
from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Deed  # senda Deed bor


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


# 1) Editor sahifa
def collabora_editor(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("DOCX fayl topilmadi")

    # Agar login bo‘lsa:
    user_id = getattr(getattr(request, "user", None), "id", None)
    token = _make_access_token(deed.id, user_id, ttl_seconds=3600)

    wopi_src = _abs_url(request, reverse("wopi_check_file_info", args=[deed.id]))
    qs = urlencode({"WOPISrc": wopi_src, "access_token": token})

    editor_url = f"{settings.COLLABORA_URL}/loleaflet/dist/loleaflet.html?{qs}"

    return render(request, "main/deed_edit.html", {"deed": deed, "editor_url": editor_url})


# 2) CheckFileInfo
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
        "UserId": "user",
        "UserFriendlyName": "IVS User",
        "UserCanWrite": True,
        "ReadOnly": False,
        "SupportsUpdate": True,
    }
    return JsonResponse(data)


# 3) GetFile + PutFile (Save) bitta endpointda
@csrf_exempt
@require_http_methods(["GET", "POST", "PUT"])
def wopi_file_contents(request, pk: int):
    token = request.GET.get("access_token", "")
    if not _verify_access_token(token, pk):
        return HttpResponseForbidden("Bad token")

    deed = get_object_or_404(Deed, pk=pk)
    file_path = deed.file.path

    if request.method == "GET":
        with open(file_path, "rb") as f:
            content = f.read()
        resp = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        resp["Content-Disposition"] = f'inline; filename="{os.path.basename(file_path)}"'
        return resp

    # Save
    new_content = request.body
    if not new_content:
        return JsonResponse({"error": "Empty body"}, status=400)

    tmp_path = file_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(new_content)
    os.replace(tmp_path, file_path)

    stat = os.stat(file_path)
    return JsonResponse({"Status": "OK", "Version": str(int(stat.st_mtime))})
