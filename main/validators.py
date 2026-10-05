import os
from django.core.exceptions import ValidationError

def validate_file_extension(value):
    # 1) Fayl kengaytmasi
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf']

    if ext not in valid_extensions:
        raise ValidationError("Faqat PDF fayl yuklash mumkin!")

    # 2) MIME TYPES (haqiqiy fayl turi)
    valid_mime = [
        'application/pdf',
    ]

    # content_type tekshiramiz
    if hasattr(value, 'content_type') and value.content_type not in valid_mime:
        raise ValidationError("Fayl formati to‘g‘ri emas yoki buzilgan!")

    # 3) Fayl hajmi
    if value.size > 10 * 1024 * 1024:  # 10 MB
        raise ValidationError("Fayl 10 MB dan katta bo‘lishi mumkin emas!")


ATTACHMENT_MIME_BY_EXT = {
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".xls": {"application/vnd.ms-excel"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}


def validate_attachment_extension(value):
    """Hujjat ilovasi: PDF, Word (.doc/.docx) yoki Excel (.xls/.xlsx), 10 MB gacha."""
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ATTACHMENT_MIME_BY_EXT:
        raise ValidationError("Faqat PDF, Word (.doc, .docx) yoki Excel (.xls, .xlsx) fayl yuklash mumkin!")

    # Brauzer yuborgan tur kengaytmaga mos bo'lishi kerak.
    # "application/octet-stream" ni ba'zi brauzerlar eski Office fayllari uchun yuboradi.
    content_type = getattr(value, "content_type", None)
    if content_type and content_type != "application/octet-stream"             and content_type not in ATTACHMENT_MIME_BY_EXT[ext]:
        raise ValidationError("Fayl formati kengaytmasiga mos emas yoki buzilgan!")

    if value.size > 10 * 1024 * 1024:  # 10 MB
        raise ValidationError("Fayl 10 MB dan katta bo‘lishi mumkin emas!")


MATERIAL_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")
MATERIAL_IMAGE_MAX_BYTES = 5 * 1024 * 1024


def validate_material_image(value):
    """Material rasmi: faqat JPG/PNG, 5 MB gacha va haqiqatan rasm bo'lishi shart.

    HEIC/WEBP/SVG va boshqalar brauzerlarda ko'rinmaydi yoki xavfli, shuning uchun rad etiladi.
    """
    from PIL import Image

    ext = os.path.splitext(value.name)[1].lower()
    if ext not in MATERIAL_IMAGE_EXTENSIONS:
        raise ValidationError(
            "Rasm faqat JPG yoki PNG formatida bo'lishi kerak "
            "(iPhone'da HEIC bo'lsa: Sozlamalar → Kamera → Formatlar → «Eng mos»)."
        )
    if value.size > MATERIAL_IMAGE_MAX_BYTES:
        raise ValidationError("Rasm 5 MB dan katta bo'lishi mumkin emas!")
    try:
        value.seek(0)
        with Image.open(value) as img:
            img.verify()
            fmt = (img.format or "").upper()
    except Exception:
        raise ValidationError("Fayl buzilgan yoki rasm emas!")
    finally:
        value.seek(0)
    if fmt not in ("JPEG", "PNG"):
        raise ValidationError("Rasm faqat JPG yoki PNG formatida bo'lishi kerak!")
