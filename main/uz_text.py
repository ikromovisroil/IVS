"""O'zbekcha matnda o' va g' belgisidan keyingi apostrof yagona ko'rinishga keltiriladi: o‘ va g‘ (U+2018).

Ro'yxatdagi (nom, F.I.Sh. va h.k.) maydonlar saqlashda avtomatik tuzatiladi (main/signals.py).
Hujjat matni (HTML) uchun alohida: main/sanitizers.py.
"""
import re

_APOS = "'ʻʼ‘’`´"
_OG = re.compile(rf"(?<=[oOgG])[{_APOS}](?=[A-Za-z])")

# model nomi -> tuzatiladigan matn maydonlari
NORMALIZED_FIELDS = {
    "Organization": ("name",),
    "Region": ("name",),
    "Department": ("name",),
    "Directorate": ("name",),
    "Division": ("name",),
    "Rank": ("name",),
    "Employee": ("last_name", "first_name", "father_name"),
    "Goal": ("name",),
    "Group": ("name",),
    "Category": ("name",),
    "Contract": ("name",),
    "Unit": ("name",),
    "MaterialCategory": ("name",),
    "StructureCategory": ("name",),
    "Material": ("name",),
    "Technics": ("name",),
    "Structure": ("name",),
}


def normalize_og(text):
    """"Po'latov" -> "Po‘latov", "o'g'li" -> "o‘g‘li", "G'aznachilik" -> "G‘aznachilik". Boshqa matnga tegmaydi."""
    return _OG.sub("‘", text) if text else text
