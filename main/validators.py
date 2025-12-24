import os
from django.core.exceptions import ValidationError

def validate_file_extension(value):
    # 1) Fayl kengaytmasi
    ext = os.path.splitext(value.name)[1].lower()
    valid_extensions = ['.pdf', '.docx']

    if ext not in valid_extensions:
        raise ValidationError("Faqat PDF, DOCX yoki XLSX yuklash mumkin!")

    # 2) MIME TYPES (haqiqiy fayl turi)
    valid_mime = [
        'application/pdf',

        # DOCX
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]

    # content_type tekshiramiz
    if hasattr(value, 'content_type') and value.content_type not in valid_mime:
        raise ValidationError("Fayl formati to‘g‘ri emas yoki buzilgan!")

    # 3) Fayl hajmi
    if value.size > 10 * 1024 * 1024:  # 10 MB
        raise ValidationError("Fayl 10 MB dan katta bo‘lishi mumkin emas!")
