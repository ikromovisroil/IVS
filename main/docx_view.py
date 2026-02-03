import os
from django.http import JsonResponse, FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from .models import Deed
from django.shortcuts import render

def wopi_file(request, pk):
    deed = get_object_or_404(Deed, pk=pk)

    if not deed.file:
        return JsonResponse({"error": "file not attached"}, status=400)

    return JsonResponse({
        "BaseFileName": os.path.basename(deed.file.name),
        "Size": deed.file.size,
        "UserCanWrite": True,
        "Version": "1.0",
    })

def wopi_contents(request, pk):
    deed = get_object_or_404(Deed, pk=pk)

    if not deed.file:
        return HttpResponse("file not attached", status=400)

    if request.method == "GET":
        return FileResponse(open(deed.file.path, "rb"))

    if request.method == "POST":
        with open(deed.file.path, "wb") as f:
            f.write(request.body)
        return HttpResponse(status=200)

    return HttpResponse(status=405)

def deed_edit(request, pk):
    deed = get_object_or_404(Deed, pk=pk)

    wopi_src = request.build_absolute_uri(f"/wopi/files/{deed.id}/")
    # Collabora URL (same domain, /collabora/)
    collabora_url = (
        "https://report.imv.uz/collabora/loleaflet/dist/loleaflet.html"
        f"?WOPISrc={wopi_src}"
    )
    return render(request, "main/deed_edit.html", {"collabora_url": collabora_url})
