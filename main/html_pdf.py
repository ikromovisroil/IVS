import os
import pdfkit
import pymupdf

# WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"

WKHTMLTOPDF_PATH = "/usr/bin/wkhtmltopdf"


class HtmlPdfError(Exception):
    pass


def _ensure_wkhtmltopdf():
    if not WKHTMLTOPDF_PATH or not os.path.exists(WKHTMLTOPDF_PATH):
        raise HtmlPdfError(f'wkhtmltopdf topilmadi: "{WKHTMLTOPDF_PATH}"')


def deed_to_pdf_bytes(deed) -> bytes:
    body = (getattr(deed, "body", "") or "").strip()
    if not body:
        raise HtmlPdfError("Body bo‘sh — PDF qilib bo‘lmaydi.")

    _ensure_wkhtmltopdf()

    # ✅ False = Portrait, True = Landscape
    ft = bool(getattr(deed, "file_type", False))
    orientation = "Portrait" if ft else "Landscape"

    config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

    # ✅ Hech qanday CSS qo‘shmaymiz — deed.body qanday bo‘lsa, shunday ketadi
    html = (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'></head>"
        f"<body>{body}</body></html>"
    )

    options = {
        "encoding": "UTF-8",
        "page-size": "A4",
        "orientation": orientation,

        # PDF “kichrayib ketmasin” uchun tavsiya
        "disable-smart-shrinking": "",
        "zoom": "1.0",
        "dpi": "150",

        "print-media-type": "",
        "enable-local-file-access": "",

        "margin-top": "10mm",
        "margin-right": "10mm",
        "margin-bottom": "25mm",
        "margin-left": "10mm",
    }

    try:
        pdf_bytes = pdfkit.from_string(
            html,
            False,
            options=options,
            configuration=config,
        )
    except Exception as e:
        raise HtmlPdfError(f"PDF qilishda xatolik: {e}")

    if not pdf_bytes:
        raise HtmlPdfError("PDF hosil bo‘lmadi (pdfkit bo‘sh qaytdi).")

    return pdf_bytes


def add_text_watermark_pdf_bytes(pdf_bytes: bytes, text: str) -> bytes:
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

    for page in doc:
        rect = page.rect

        diagonal = (rect.width**2 + rect.height**2) ** 0.5
        fontsize = int(diagonal / 18)

        text_width = pymupdf.get_text_length(text, fontsize=fontsize)

        x = (rect.width - text_width) / 2
        y = rect.height / 2

        center = pymupdf.Point(rect.width / 2, rect.height / 2)
        matrix = pymupdf.Matrix(1, 1).prerotate(45)

        page.insert_text(
            (x, y),
            text,
            fontsize=fontsize,
            color=(0.3, 0.3, 0.3),   # to‘q kulrang
            overlay=True,
            fill_opacity=0.12,      # 🔥 juda shaffof
            morph=(center, matrix),
        )

    out = doc.tobytes(deflate=True)
    doc.close()
    return out