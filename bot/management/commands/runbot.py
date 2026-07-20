import asyncio
import logging
import os

from asgiref.sync import sync_to_async
from django.core.management.base import BaseCommand

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    CallbackQuery,
)

from bot.services import (
    find_employee_by_pinfl, link_telegram_chat, get_employee_by_chat_id,
    unlink_telegram_chat, get_menu_flags,
    list_available_goals, create_order, list_my_orders,
    rate_order, list_pending_ratings, receive_order,
)

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# FSM holatlar
# ---------------------------------------------------------------------------

class AuthStates(StatesGroup):
    waiting_pinfl = State()


class OrderStates(StatesGroup):
    choosing_goal = State()
    typing_message = State()


# ---------------------------------------------------------------------------
# Menyu
# ---------------------------------------------------------------------------

def main_menu(menu_flags) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📝 Ariza yuborish")],
        [KeyboardButton(text="📋 Mening arizalarim")],
        [KeyboardButton(text="🚪 Chiqish")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def goals_keyboard(goals) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=g.name, callback_data=f"goal:{g.id}")]
        for g in goals
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Faqat 1-5 baho - "Bekor qilish" tugmasi YO'Q."""
    stars = [
        InlineKeyboardButton(text=str(i), callback_data=f"rate:{order_id}:{i}")
        for i in range(1, 6)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[stars])


async def _send_main_menu(message: Message, employee, greeting: str):
    menu_flags = await sync_to_async(get_menu_flags)(employee)
    await message.answer(greeting, reply_markup=main_menu(menu_flags))


# ---------------------------------------------------------------------------
# /start - PINFL orqali bog'lash
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)

    if employee:
        await _send_main_menu(message, employee, f"Salom, {employee.full_name}!")
        return

    await state.set_state(AuthStates.waiting_pinfl)
    await message.answer(
        "Xush kelibsiz! Tizimga kirish uchun PINFL raqamingizni (14 ta raqam) kiriting:",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(StateFilter(AuthStates.waiting_pinfl))
async def process_pinfl(message: Message, state: FSMContext):
    pinfl = (message.text or "").strip()
    employee = await sync_to_async(find_employee_by_pinfl)(pinfl)

    if not employee:
        await message.answer(
            "PINFL topilmadi yoki noto'g'ri. Qaytadan urinib ko'ring (14 ta raqam)."
        )
        return

    await sync_to_async(link_telegram_chat)(employee, message.chat.id)
    await state.clear()
    await _send_main_menu(message, employee, f"Muvaffaqiyatli bog'landi! Salom, {employee.full_name}.")


async def _require_employee(message: Message, state: FSMContext):
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)
    if not employee:
        await state.set_state(AuthStates.waiting_pinfl)
        await message.answer(
            "Sessiya topilmadi. Iltimos PINFL raqamingizni qayta kiriting:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return None
    return employee


@router.message(F.text == "🚪 Chiqish")
async def cmd_logout(message: Message, state: FSMContext):
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)
    if employee:
        await sync_to_async(unlink_telegram_chat)(employee)
    await state.clear()
    await message.answer("Bog'lanish uzildi. Qayta kirish uchun /start bosing.",
                          reply_markup=ReplyKeyboardRemove())


# ---------------------------------------------------------------------------
# ARIZA YUBORISH
# ---------------------------------------------------------------------------

@router.message(F.text == "📝 Ariza yuborish")
async def cmd_new_order(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return

    goals = await sync_to_async(list_available_goals)(employee)
    if not goals:
        await message.answer("Hozircha ariza turi mavjud emas.")
        return

    await state.set_state(OrderStates.choosing_goal)
    await message.answer("Ariza turini tanlang:", reply_markup=goals_keyboard(goals))


@router.callback_query(StateFilter(OrderStates.choosing_goal), F.data.startswith("goal:"))
async def process_goal_choice(callback: CallbackQuery, state: FSMContext):
    goal_id = int(callback.data.split(":")[1])
    await state.update_data(goal_id=goal_id)
    await state.set_state(OrderStates.typing_message)
    await callback.message.edit_reply_markup()
    await callback.message.answer("Ariza matnini (izohni) yozing:")
    await callback.answer()


@router.message(StateFilter(OrderStates.typing_message))
async def process_order_message(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return

    data = await state.get_data()
    goal_id = data.get("goal_id")

    result = await sync_to_async(create_order)(employee, goal_id, message.text)
    await state.clear()

    text = f"✅ {result.message} (№{result.order.id})" if result.ok else f"⚠️ {result.message}"
    await _send_main_menu(message, employee, text)


# ---------------------------------------------------------------------------
# MENING ARIZALARIM
# ---------------------------------------------------------------------------

STATUS_LABELS = {
    "viewed": "Yangi", "process": "Jarayonda", "finished": "Tayyorlandi",
    "approved": "Tasdiqlandi", "accepted": "Qabul qilindi",
    "canceled": "Bekor qilindi", "rejected": "Rad etildi",
}


@router.message(F.text == "📋 Mening arizalarim")
async def cmd_my_orders(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return

    orders = await sync_to_async(list_my_orders)(employee)
    if not orders:
        await message.answer("Sizda hali ariza yo'q.")
        return

    lines = [
        f"#{o.id} — {o.goal.name if o.goal else '-'} — "
        f"{STATUS_LABELS.get(o.status, o.status)}"
        for o in orders
    ]
    await message.answer("\n".join(lines))

    pending = await sync_to_async(list_pending_ratings)(employee)
    for o in pending:
        text = (
            f"#{o.id} — {o.goal.name if o.goal else '-'}\n"
            f"Bajardi: {o.receiver.full_name if o.receiver else '-'}\n\n"
            f"Iltimos, xizmatni baholang:"
        )
        await message.answer(text, reply_markup=rating_keyboard(o.id))


# ---------------------------------------------------------------------------
# BAHOLASH (ATM) - faqat 1-5, bekor qilish yo'q
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("rate:"))
async def cb_rate(callback: CallbackQuery):
    _, order_id, rating = callback.data.split(":")
    employee = await sync_to_async(get_employee_by_chat_id)(callback.message.chat.id)
    if not employee:
        await callback.answer("Sessiya tugagan, /start bosing", show_alert=True)
        return

    result = await sync_to_async(rate_order)(employee, int(order_id), int(rating))
    await callback.answer(result.message, show_alert=not result.ok)
    if result.ok:
        await callback.message.edit_reply_markup()


# ---------------------------------------------------------------------------
# OMBOR ARIZASI - TASDIQLANGANDAN KEYIN "QABUL QILDIM"
# (bildirishnoma orqali kelgan tugmadan bosiladi)
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("receive:"))
async def cb_receive(callback: CallbackQuery):
    logger.info("cb_receive chaqirildi: %s", callback.data)
    _, order_id = callback.data.split(":")
    employee = await sync_to_async(get_employee_by_chat_id)(callback.message.chat.id)
    if not employee:
        await callback.answer("Sessiya tugagan, /start bosing", show_alert=True)
        return

    result = await sync_to_async(receive_order)(employee, int(order_id))
    logger.info("receive_order natijasi: ok=%s, message=%s", result.ok, result.message)

    await callback.answer(result.message, show_alert=not result.ok)
    if result.ok:
        await callback.message.edit_reply_markup()


# ---------------------------------------------------------------------------
# Django management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Telegram botni ishga tushiradi (aiogram, polling rejimida)"

    def handle(self, *args, **options):
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not token:
            self.stderr.write(self.style.ERROR(
                "TELEGRAM_BOT_TOKEN .env faylda topilmadi"
            ))
            return
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("bot_debug.log", encoding="utf-8"),
            ],
        )
        asyncio.run(self._run(token))

    async def _run(self, token: str):
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(router)

        self.stdout.write(self.style.SUCCESS("Bot ishga tushdi (polling)..."))
        await dp.start_polling(bot)