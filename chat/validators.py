import os

from django.core.exceptions import ValidationError

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS


def is_image_ext(name: str) -> bool:
    return os.path.splitext(name or "")[1].lower() in IMAGE_EXTENSIONS


def validate_chat_attachment(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            "Ruxsat etilgan fayl turlari: rasm (jpg, png), pdf, word, excel."
        )
    if value.size > 15 * 1024 * 1024:
        raise ValidationError("Fayl 15 MB dan katta bo'lishi mumkin emas!")
