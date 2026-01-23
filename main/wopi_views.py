import os
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.http import JsonResponse, Http404, HttpResponse, FileResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt

from .models import Deed


# -----------------------------
# Token helpers
# -----------------------------
_signer = TimestampSigner(salt="wopi-access")


def make_wopi_token(user_id: int, file_id: int) -> str:
    raw = f"{user_id}:{file_id}"
    return _signer.sign(raw)


def parse_wopi_token(token: str, expected_file_id: int) -> int:
    """
    Return user_id if OK; raise if invalid/expired.
    """
    max_age = getattr(settings, "WOPI_TOKEN_MAX_AGE_SECONDS", 3600)
    raw = _signer.unsign(token, max_age=max_age)  # raises SignatureExpired/BadSignature
    user_id_s, file_id_s = raw.split(":", 1)
    if int(file_id_s) != int(expected_file_id):
        raise BadSignature("file mismatch")
    return int(user_id_s)


def get_access_token(request):
    # WOPI spec: access_token query param
    return (request.GET.get("access_token") or "").strip()


def wopi_auth_or_403(request, file_id: int):
    token = get_access_token(request)
    if not token:
        return None, HttpResponseForbidden("No access_token")
    try:
        user_id = parse_wopi_token(token, expected_file_id=file_id)
        return user_id, None
    except SignatureExpired:
        return None, HttpResponseForbidden("Token expired")
    except BadSignature:
        return None, HttpResponseForbidden("Bad token")


# -----------------------------
# LOCK helpers (cache)
# -----------------------------
def _lock_key(file_id: int) -> str:
    return f"wopi:lock:{file_id}"


def _get_lock(file_id: int):
    return cache.get(_lock_key(file_id))


def _set_lock(file_id: int, lock_value: str, ttl=3600):
    cache.set(_lock_key(file_id), lock_value, ttl)


def _del_lock(file_id: int):
    cache.delete(_lock_key(file_id))


# -----------------------------
# Editor page
# -----------------------------
@login_required
def deed_edit_docx(request, pk: int):
    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("DOCX yo‘q")

    # TODO: permission: faqat ruxsatli user ochsin
    # Masalan:
    # if request.user.employee != deed.user: return HttpResponseForbidden()

    # WOPI src
    wopi_src = request.build_absolute_uri(f"/wopi/files/{deed.pk}")
    wopi_src_enc = quote(wopi_src, safe="")

    token = make_wopi_token(request.user.id, deed.pk)

    # Collabora URL: /cool/loleaflet/.../wopi/files/<id>?WOPISrc=...&access_token=...
    # Eng ko‘p ishlatiladigan ko‘rinish:
    collabora = settings.COLLABORA_URL.rstrip("/")
    iframe_url = (
        f"{collabora}/cool/loleaflet.html?"
        f"WOPISrc={wopi_src_enc}&access_token={quote(token)}"
    )

    return render(request, "main/deed_edit.html", {
        "deed": deed,
        "iframe_url": iframe_url,
    })


# -----------------------------
# WOPI: CheckFileInfo
# GET /wopi/files/<id>
# -----------------------------
@csrf_exempt
def wopi_check_file_info(request, pk: int):
    user_id, err = wopi_auth_or_403(request, pk)
    if err:
        return err

    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("DOCX yo‘q")

    path = deed.file.path
    if not os.path.exists(path):
        raise Http404("Fayl topilmadi")

    st = os.stat(path)
    file_name = os.path.basename(path)

    # Minimal required fields
    data = {
        "BaseFileName": file_name,
        "Size": st.st_size,
        "Version": str(int(st.st_mtime)),  # oddiy version
        "OwnerId": str(getattr(deed, "user_id", "") or "owner"),
        "UserId": str(user_id),
        "UserFriendlyName": "User",

        # edit ruxsatlari
        "UserCanWrite": True,
        "SupportsUpdate": True,
        "SupportsLocks": True,

        # (ixtiyoriy)
        "ReadOnly": False,
    }
    return JsonResponse(data)


# -----------------------------
# WOPI: file contents
# GET  /wopi/files/<id>/contents  => returns file bytes
# POST /wopi/files/<id>/contents  => saves file bytes (PutFile)
# Also handles LOCK/UNLOCK/REFRESH via X-WOPI-Override headers
# -----------------------------
@csrf_exempt
def wopi_file_contents(request, pk: int):
    user_id, err = wopi_auth_or_403(request, pk)
    if err:
        return err

    deed = get_object_or_404(Deed, pk=pk)
    if not deed.file:
        raise Http404("DOCX yo‘q")

    path = deed.file.path
    if not os.path.exists(path):
        raise Http404("Fayl topilmadi")

    # Handle LOCK operations
    override = (request.headers.get("X-WOPI-Override") or "").upper()
    req_lock = request.headers.get("X-WOPI-Lock")

    # Collabora LOCK/UNLOCK/REFRESH_LOCK/GET_LOCK kabi override yuboradi
    if override in ("LOCK", "UNLOCK", "REFRESH_LOCK", "GET_LOCK"):
        current = _get_lock(pk)

        if override == "GET_LOCK":
            resp = HttpResponse(status=200)
            if current:
                resp["X-WOPI-Lock"] = current
            return resp

        if not req_lock:
            # Lock header bo‘lmasa conflict
            resp = HttpResponse(status=409)
            if current:
                resp["X-WOPI-Lock"] = current
            return resp

        if override == "LOCK":
            if current and current != req_lock:
                resp = HttpResponse(status=409)
                resp["X-WOPI-Lock"] = current
                return resp
            _set_lock(pk, req_lock, ttl=settings.WOPI_TOKEN_MAX_AGE_SECONDS)
            return HttpResponse(status=200)

        if override == "REFRESH_LOCK":
            if current != req_lock:
                resp = HttpResponse(status=409)
                if current:
                    resp["X-WOPI-Lock"] = current
                return resp
            _set_lock(pk, req_lock, ttl=settings.WOPI_TOKEN_MAX_AGE_SECONDS)
            return HttpResponse(status=200)

        if override == "UNLOCK":
            if current != req_lock:
                resp = HttpResponse(status=409)
                if current:
                    resp["X-WOPI-Lock"] = current
                return resp
            _del_lock(pk)
            return HttpResponse(status=200)

    # GET: download file
    if request.method == "GET":
        return FileResponse(open(path, "rb"), as_attachment=False, filename=os.path.basename(path))

    # POST: save file bytes (PutFile)
    if request.method == "POST":
        # If there is a lock, require it
        current = _get_lock(pk)
        if current and req_lock and current != req_lock:
            resp = HttpResponse(status=409)
            resp["X-WOPI-Lock"] = current
            return resp
        if current and not req_lock:
            resp = HttpResponse(status=409)
            resp["X-WOPI-Lock"] = current
            return resp

        # Save uploaded content
        try:
            with open(path, "wb") as f:
                f.write(request.body)
        except Exception:
            return HttpResponse(status=500)

        # WOPI expects version sometimes
        resp = HttpResponse(status=200)
        resp["X-WOPI-ItemVersion"] = str(int(os.stat(path).st_mtime))
        return resp

    return HttpResponse(status=405)
