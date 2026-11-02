"""
Hujjatni imzolovchi (sender/receiver) sifatida tasdiqlash — FaceID uchun. E-IMZO oqimidagi (main/sso_views.py:eimzo_return)
sender/receiver tasdiqlash bilan bir xil natija: holat `approved`, oxirgi imzoda PDF qayta yig'ilib QR bilan imzolanadi.
"""
import logging
import secrets

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .html_pdf import deed_to_pdf_bytes
from .models import Deed
from .utils import sign_pdf_inplace

logger = logging.getLogger(__name__)


class SigningError(Exception):
    def __init__(self, message, code="SIGNING_ERROR"):
        super().__init__(message)
        self.code = code


def finalize_pdf(deed_id: int, approver_name: str) -> None:
    """To'liq imzolangan hujjat PDF'ini qayta yig'ib, QR/imzo uradi (eimzo_return dagi bilan bir xil)."""
    deed = Deed.objects.get(pk=deed_id)
    pdf_bytes = deed_to_pdf_bytes(deed)
    if deed.file:
        deed.file.delete(save=False)
    pdf_name = f"akt_{timezone.now().strftime('%Y%m%d')}_{secrets.token_urlsafe(6)}.pdf"
    deed.file.save(pdf_name, ContentFile(pdf_bytes), save=True)
    sign_pdf_inplace(pdf_path=deed.file.path, request=None, approver_name=approver_name, deed_id=deed.pk)


def approve_as_signer(deed_id: int, employee, role: str, message: str = "") -> bool:
    """
    Qaytaradi: hujjat to'liq imzolandimi. Xodim shu hujjatning `role` (sender|receiver) imzolovchisi bo'lishi va
    holati `viewed` bo'lishi shart; allaqachon tasdiqlangan bo'lsa — hech narsa o'zgarmaydi (takroriy chaqiruv xavfsiz).
    """
    if role not in ("sender", "receiver"):
        raise SigningError("Rol noto'g'ri", "BAD_ROLE")

    with transaction.atomic():
        deed = Deed.objects.select_for_update().get(pk=deed_id)
        if (deed.sender_id if role == "sender" else deed.receiver_id) != employee.id:
            raise SigningError("Siz bu hujjatning imzolovchisi emassiz", "NOT_SIGNER")

        current = deed.status_sender if role == "sender" else deed.status_receiver
        if current == "rejected":
            raise SigningError("Hujjat rad etilgan", "DEED_REJECTED")
        if current == "viewed":
            now = timezone.now()
            if role == "sender":
                deed.status_sender, deed.message_sender, deed.date_sender = "approved", message or "", now
                deed.save(update_fields=["status_sender", "message_sender", "date_sender"])
            else:
                deed.status_receiver, deed.message_receiver, deed.date_receiver = "approved", message or "", now
                deed.save(update_fields=["status_receiver", "message_receiver", "date_receiver"])
        else:
            return False   # allaqachon tasdiqlangan: PDF qayta yig'ilmaydi

        is_final = deed.status_sender == "approved" and (deed.receiver_id is None or deed.status_receiver == "approved")

    if is_final:
        try:
            finalize_pdf(deed_id, getattr(employee, "full_name", None) or str(employee))
        except Exception:  # HtmlPdfError, TimeoutError va boshqalar
            # Tasdiq saqlangan; PDF xatosi E-IMZO oqimidagidek tasdiqni bekor qilmaydi
            logger.exception("FaceID: PDF yig'ish/imzolash xatosi (deed=%s)", deed_id)
    return is_final
