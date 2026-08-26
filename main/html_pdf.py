import logging
import os

import pymupdf
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Deed, DeedConsent
from .utils import sign_pdf_inplace

logger = logging.getLogger(__name__)


class HtmlPdfError(Exception):
    pass


# ─── Umumiy CSS (bo'linish/page-break qoidalari, ikkala dvigatel uchun ham) ───

_COMMON_CSS = """
    html, body { background-color: #fff; }
    table { border-collapse: collapse; width: 100%; }
    thead { display: table-header-group; }
    tr { page-break-inside: avoid; break-inside: avoid; }
    td, th { page-break-inside: avoid; }
"""


def _get_wkhtmltopdf_path():
    path = getattr(settings, "WKHTMLTOPDF_PATH", "") or ""
    return path.strip()


def _ensure_wkhtmltopdf():
    path = _get_wkhtmltopdf_path()

    if not path:
        raise HtmlPdfError("WKHTMLTOPDF_PATH env yoki settingsda berilmagan")

    if not os.path.exists(path):
        raise HtmlPdfError(f'wkhtmltopdf topilmadi: "{path}"')

    return path


def _read_existing_file_bytes(deed):
    file_field = getattr(deed, "file", None)
    if not file_field or not getattr(file_field, "name", None):
        return None
    try:
        if not file_field.storage.exists(file_field.name):
            return None
        file_field.open("rb")
        try:
            return file_field.read()
        finally:
            file_field.close()
    except Exception:
        logger.warning(
            "Deed #%s uchun mavjud faylni o'qib bo'lmadi", getattr(deed, "id", None),
            exc_info=True,
        )
        return None


def _html_to_pdf_bytes_weasyprint(body_html: str, orientation: str) -> bytes:
    from weasyprint import HTML, CSS

    page_size = "A4 portrait" if orientation == "Portrait" else "A4 landscape"

    css = CSS(string=f"""
        @page {{
            size: {page_size};
            margin-top: 15mm;
            margin-right: 10mm;
            margin-bottom: 25mm;
            margin-left: 15mm;
        }}
        {_COMMON_CSS}
    """)

    html = (
        "<!doctype html>"
        "<html>"
        "<head><meta charset='utf-8'></head>"
        f"<body>{body_html}</body>"
        "</html>"
    )

    try:
        pdf_bytes = HTML(string=html).write_pdf(stylesheets=[css])
    except Exception as e:
        raise HtmlPdfError(f"PDF qilishda xatolik (weasyprint): {e}")

    if not pdf_bytes:
        raise HtmlPdfError("PDF hosil bo'lmadi (weasyprint bo'sh qaytdi).")

    return pdf_bytes


def _html_to_pdf_bytes_wkhtmltopdf(body_html: str, orientation: str) -> bytes:
    import pdfkit

    wkhtmltopdf_path = _ensure_wkhtmltopdf()
    config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)

    html = (
        "<!doctype html>"
        "<html>"
        "<head><meta charset='utf-8'>"
        f"<style>{_COMMON_CSS}</style>"
        "</head>"
        f"<body>{body_html}</body>"
        "</html>"
    )

    options = {
        "encoding": "UTF-8",
        "page-size": "A4",
        "orientation": orientation,
        "disable-smart-shrinking": "",
        "zoom": "1.0",
        "dpi": "150",
        "print-media-type": "",
        "enable-local-file-access": "",
        "margin-top": "15mm",
        "margin-right": "10mm",
        "margin-bottom": "25mm",
        "margin-left": "15mm",
        "load-error-handling": "ignore",
        "load-media-error-handling": "ignore",
    }

    try:
        pdf_bytes = pdfkit.from_string(
            html,
            False,
            options=options,
            configuration=config,
        )
    except Exception as e:
        raise HtmlPdfError(f"PDF qilishda xatolik (wkhtmltopdf): {e}")

    if not pdf_bytes:
        raise HtmlPdfError("PDF hosil bo'lmadi (pdfkit bo'sh qaytdi).")

    return pdf_bytes


def html_to_pdf_bytes(body_html: str, orientation: str = "Portrait") -> bytes:

    body_html = (body_html or "").strip()
    if not body_html:
        raise HtmlPdfError("Body bo'sh — PDF qilib bo'lmaydi")

    engine = getattr(settings, "PDF_ENGINE", "weasyprint")

    if engine == "wkhtmltopdf":
        return _html_to_pdf_bytes_wkhtmltopdf(body_html, orientation)

    return _html_to_pdf_bytes_weasyprint(body_html, orientation)


def deed_to_pdf_bytes(deed) -> bytes:
    body = (getattr(deed, "body", "") or "").strip()

    if not body:
        existing_bytes = _read_existing_file_bytes(deed)
        if existing_bytes:
            return existing_bytes
        raise HtmlPdfError("Body bo'sh — PDF qilib bo'lmaydi")

    # False = Landscape, True = Portrait
    orientation = "Portrait" if deed.status == "document" else "Landscape"

    return html_to_pdf_bytes(body, orientation=orientation)


def add_text_watermark_pdf_bytes(pdf_bytes: bytes, text: str) -> bytes:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    try:
        for page in doc:
            rect = page.rect

            diagonal = (rect.width ** 2 + rect.height ** 2) ** 0.5
            fontsize = int(diagonal / 18)

            text_width = pymupdf.get_text_length(text, fontname="helv", fontsize=fontsize)

            x = (rect.width - text_width) / 2
            y = rect.height / 2

            center = pymupdf.Point(rect.width / 2, rect.height / 2)
            matrix = pymupdf.Matrix(1, 1).prerotate(45)

            page.insert_text(
                (x, y),
                text,
                fontsize=fontsize,
                color=(0.3, 0.3, 0.3),
                overlay=True,
                fill_opacity=0.12,
                morph=(center, matrix),
            )

        out = doc.tobytes(deflate=True)
    finally:
        doc.close()
    return out


def _create_deed_for_order(order, request=None):
    html_body = render_to_string("main/order_agrement_deed.html", {
        "order": order,
        "today": timezone.now(),
    })
    with transaction.atomic():
        deed = Deed(
            organization=order.sender.organization,
            sender=order.sender,
            status_sender="approved",
            date_sender=order.date_accepted,
            receiver=order.user,
            status_receiver="approved",
            date_receiver=order.date_approved,
            body=html_body,
            order=order,
            status="petition",
        )

        try:
            pdf_bytes = deed_to_pdf_bytes(deed)
        except HtmlPdfError as e:
            logger.error("Order #%s uchun Deed PDF yaratilmadi: %s", order.id, e)
            raise

        deed.file.save(f"order_{order.id}.pdf", ContentFile(pdf_bytes), save=False)
        deed.save()

        if order.receiver_id:
            DeedConsent.objects.create(
                deed=deed,
                employee=order.receiver,
                status="approved",
            )

        try:
            sign_pdf_inplace(
                deed.file.path,
                request,
                approver_name=order.sender.full_name,
                deed_id=deed.id,
            )
        except Exception as e:
            logger.error("Deed #%s ga QR/imzo urishda xatolik: %s", deed.id, e)
            raise

    return deed