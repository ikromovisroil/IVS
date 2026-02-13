import os
import shutil
import platform
import pdfkit


class HtmlPdfError(Exception):
    pass


def _find_wkhtmltopdf_path() -> str:
    """
    Windows + Linux/Mac uchun wkhtmltopdf yo'lini topadi.
    1) ENV: WKHTMLTOPDF_PATH bo'lsa - o'shani oladi
    2) Windows: odatiy 2ta joyni tekshiradi
    3) Linux: PATH ichidan (shutil.which) topadi
    """
    # 1) ENV dan olish (eng yaxshi usul)
    env_path = (os.environ.get("WKHTMLTOPDF_PATH") or "").strip()
    if env_path:
        if os.path.exists(env_path):
            return env_path
        raise HtmlPdfError(f'ENV WKHTMLTOPDF_PATH berilgan, lekin topilmadi: "{env_path}"')

    system = platform.system().lower()

    # 2) Windows default joylar
    if "windows" in system:
        candidates = [
            r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe",
            r"C:\Program Files (x86)\wkhtmltopdf\bin\wkhtmltopdf.exe",
        ]
        for p in candidates:
            if os.path.exists(p):
                return p

        # Windowsda PATH ichidan ham qidiramiz
        p = shutil.which("wkhtmltopdf")
        if p:
            return p

        raise HtmlPdfError(
            "wkhtmltopdf topilmadi.\n"
            "Windows: wkhtmltopdf o‘rnating yoki ENV WKHTMLTOPDF_PATH ni to‘g‘ri bering.\n"
            "Masalan: C:\\Program Files\\wkhtmltopdf\\bin\\wkhtmltopdf.exe"
        )

    # 3) Linux/Mac: PATH ichidan topish
    p = shutil.which("wkhtmltopdf")
    if p:
        return p

    # Linuxda keng tarqalgan joylarni ham tekshiramiz
    candidates = ["/usr/bin/wkhtmltopdf", "/usr/local/bin/wkhtmltopdf"]
    for c in candidates:
        if os.path.exists(c):
            return c

    raise HtmlPdfError(
        "wkhtmltopdf topilmadi.\n"
        "Linux: `sudo apt install wkhtmltopdf` qiling yoki ENV WKHTMLTOPDF_PATH bering."
    )


def _get_pdfkit_config() -> pdfkit.configuration:
    wkhtml_path = _find_wkhtmltopdf_path()
    return pdfkit.configuration(wkhtmltopdf=wkhtml_path)


def deed_to_pdf_bytes(deed) -> bytes:
    body = (getattr(deed, "body", "") or "").strip()
    if not body:
        raise HtmlPdfError("Body bo‘sh — PDF qilib bo‘lmaydi.")

    # ✅ False = Portrait, True = Landscape (siz aytgandek)
    ft = bool(getattr(deed, "file_type", False))
    orientation = "Landscape" if ft else "Portrait"

    config = _get_pdfkit_config()

    html = (
        "<!doctype html>"
        "<html><head><meta charset='utf-8'></head>"
        f"<body>{body}</body></html>"
    )

    options = {
        "encoding": "UTF-8",
        "page-size": "A4",
        "orientation": orientation,

        # Masshtab va sifat
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
