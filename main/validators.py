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
