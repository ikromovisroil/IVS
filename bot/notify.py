import logging

logger = logging.getLogger(__name__)


def send_telegram_message(chat_id: int | None, text: str, reply_markup: dict | None = None) -> None:
    """Haqiqiy yuborish Celery worker'da, orqa fonda bajariladi
    (`main.tasks.send_telegram_message_task`) - chaqirgan view/joy
    Telegram API javobini kutib turmasligi uchun."""
    if not chat_id:
        return

    from main.tasks import send_telegram_message_task

    send_telegram_message_task.delay(chat_id, text, reply_markup)


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
