"""AI Yordamchi javob generatori.

Hozircha Anthropic API kaliti ulanmagan - shu sabab statik, xushmuomala
javob qaytaradi. API kalit (.env dagi ANTHROPIC_API_KEY) qo'shilgach, bu
funksiya Claude'ga (huquqqa mos "tool"lar bilan) chaqiruv qiladigan qilib
almashtiriladi.
"""
import os

from main.models import Employee
from .models import Conversation


def generate_ai_reply(employee: Employee, conversation: Conversation, user_message: str) -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return (
            "AI Yordamchi hali to'liq sozlanmagan (API kalit kiritilmagan). "
            "Tez orada bu yerdan arizalaringiz holati va hujjatlar haqida "
            "so'rashingiz mumkin bo'ladi."
        )

    # TODO: Anthropic API chaqiruvi + employee ruxsatlariga mos "tool"lar
    # (masalan: xodimning o'z arizalari holati, hujjat turlari FAQ).
    return "AI javobi hali ishlab chiqilmoqda."
