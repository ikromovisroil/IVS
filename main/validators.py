import os
import magic
from django.core.exceptions import ValidationError

# Fayl hajmi chegarasi (10 MB)
MAX_FILE_SIZE = 10 * 1024 * 1024

# Ruxsat etilgan kengaytma va unga mos MIME turlari (kengaytma bilan mos kelishi shart)
ALLOWED_EXTENSION_MIME_MAP = {
    '.pdf': 'application/pdf',
}


def validate_file_extension(value):
    """
    Yuklangan faylni 3 bosqichda tekshiradi:
    1) Kengaytma (extension)
    2) Haqiqiy fayl kontenti (magic bytes) — client yuborgan Content-Type headeriga ishonilmaydi
    3) Fayl hajmi
    """

    # --- 1) Kengaytma tekshiruvi ---
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ALLOWED_EXTENSION_MIME_MAP:
        raise ValidationError("Faqat PDF fayl yuklash mumkin!")

    # --- 2) Hajm tekshiruvi (kontentni o'qishdan oldin, keraksiz katta faylni o'qimaslik uchun) ---
    if value.size > MAX_FILE_SIZE:
        raise ValidationError("Fayl 10 MB dan katta bo'lishi mumkin emas!")

    if value.size == 0:
        raise ValidationError("Bo'sh fayl yuklab bo'lmaydi!")

    # --- 3) Haqiqiy kontentni tekshirish (client yuborgan content_type ga ISHONILMAYDI) ---
    try:
        current_pos = value.tell()
    except (AttributeError, OSError):
        current_pos = None

    file_start = value.read(2048)

    # Pointer'ni albatta boshiga qaytarish kerak — aks holda fayl saqlanganda
    # bo'sh yoki kesilgan holda yoziladi.
    if current_pos is not None:
        value.seek(current_pos)
    else:
        value.seek(0)

    try:
        real_mime = magic.from_buffer(file_start, mime=True)
    except Exception:
        raise ValidationError("Fayl mazmunini aniqlab bo'lmadi, fayl buzilgan bo'lishi mumkin.")

    expected_mime = ALLOWED_EXTENSION_MIME_MAP[ext]
    if real_mime != expected_mime:
        raise ValidationError(
            "Fayl mazmuni PDF formatiga mos kelmayapti (fayl buzilgan yoki soxta bo'lishi mumkin)."
        )