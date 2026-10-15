"""
Lavozimlar (Rank) bilan ishlash.

Tashqi tizimda har bir shtat birligi alohida `position_id` oladi, shuning uchun bir xil nomli lavozim (masalan,
"bosh mutaxassis") yuzlab turli kod bilan keladi. Bunday kodlar `RankCode` jadvali orqali **bitta** `Rank` ga bog'lanadi:
sinxronizatsiya kod bo'yicha shu jadvaldan qidiradi, shuning uchun lavozimlarni birlashtirish xodimlarni lavozimsiz
qoldirmaydi.
"""
import re

from .models import Rank, RankCode

# Apostrofning turli ko'rinishlari (ʼ ʻ ‘ ’ ` ´ ...) bitta belgiga keltiriladi
_APOSTROPHES = re.compile("[ʼʻʽʹ‘’‛′´`]+")


def normalize_rank_name(name):
    """Lavozim nomini solishtirish uchun: kichik harf, bir xil apostrof, ortiqcha bo'sh joysiz."""
    value = _APOSTROPHES.sub("'", (name or "").lower())
    value = re.sub(r"'+", "'", value)
    return " ".join(value.split())


def rank_for_code(code):
    """Tashqi tizim kodiga mos lavozim: avval `RankCode` jadvali, keyin eski `Rank.code`."""
    code = str(code or "").strip()
    if not code:
        return None
    link = RankCode.objects.select_related("rank").filter(code=code).first()
    if link:
        return link.rank
    return Rank.objects.filter(code=code).first()


def get_or_create_rank(code, name):
    """
    Kod bo'yicha lavozimni qaytaradi. Topilmasa, nomi (normallashtirilgan) bir xil lavozimga yangi kodni bog'laydi,
    u ham bo'lmasa yangi lavozim yaratadi. Shu bilan yangi takrorlar paydo bo'lmaydi.
    Qaytaradi: (Rank, yangi_yaratildimi).
    """
    code = str(code or "").strip()
    name = (name or "").strip()
    rank = rank_for_code(code)
    if rank:
        return rank, False

    if name:
        wanted = normalize_rank_name(name)
        rank = (
            Rank.objects.filter(name__iexact=name).order_by("id").first()
            or next((r for r in Rank.objects.only("id", "name").order_by("id")
                     if normalize_rank_name(r.name) == wanted), None)
        )
        if rank:
            if code:
                RankCode.objects.get_or_create(code=code, defaults={"rank": rank})
            return rank, False

    rank = Rank.objects.create(code=code or None, name=name or f"Lavozim-{code}")
    if code:
        RankCode.objects.get_or_create(code=code, defaults={"rank": rank})
    return rank, True
