import logging
import os

import requests

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def _token() -> str | None:
    return os.getenv("TELEGRAM_BOT_TOKEN")


def send_telegram_message(chat_id: int | None, text: str, reply_markup: dict | None = None) -> None:
    if not chat_id:
        return

    token = _token()
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN topilmadi - bildirishnoma yuborilmadi")
        return

    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(
            TELEGRAM_API_URL.format(token=token, method="sendMessage"),
            json=payload,
            timeout=5,
        )
        if not resp.ok:
            logger.warning("Telegram xabar yuborilmadi (chat_id=%s): %s", chat_id, resp.text)
    except requests.RequestException:
        logger.exception("Telegram xabar yuborishda tarmoq xatosi (chat_id=%s)", chat_id)


def rating_markup(order_id: int) -> dict:
    """Faqat 1-5 baho tugmalari - "Bekor qilish" YO'Q,
    ATM arizasi bajarilgandan keyin bekor qilib bo'lmaydi, faqat baholanadi."""
    return {
        "inline_keyboard": [
            [
                {"text": str(i), "callback_data": f"rate:{order_id}:{i}"}
                for i in range(1, 6)
            ],
        ]
    }


def barn_approved_markup(order_id: int) -> dict:
    """Ombor (client) arizasi TASDIQLANGANDA - "Qabul qildim" tugmasi."""
    return {
        "inline_keyboard": [[
            {"text": "✅ Qabul qildim", "callback_data": f"receive:{order_id}"},
        ]]
    }