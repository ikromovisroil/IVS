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
    unlink_telegram_chat, save_employee_phone,
    is_worker_employee, is_client_employee, can_execute_orders,
    list_atm_goals, list_warehouse_goals, create_order, list_my_orders,
    rate_order, list_pending_ratings, receive_order,
    list_orders_to_execute, accept_order, finish_order,
    list_completed_orders,
)

logger = logging.getLogger(__name__)
router = Router()


# ---------------------------------------------------------------------------
# FSM holatlar
# ---------------------------------------------------------------------------

class AuthStates(StatesGroup):
    waiting_pinfl = State()
    waiting_phone = State()


class MenuStates(StatesGroup):
    main = State()
    atm_menu = State()
    warehouse_menu = State()


class OrderStates(StatesGroup):
    choosing_goal = State()
    typing_message = State()


# ---------------------------------------------------------------------------
# Menyu matnlari
# ---------------------------------------------------------------------------

TXT_ATM = "💻 Axborot texnologiyalari markazi"
TXT_WAREHOUSE = "🏛️ Iqtisodiyot va Moliya vazirligi"
TXT_LOGOUT = "🚪 CHIQISH"

TXT_NEW_ORDER = "📝 ARIZA YUBORISH"
TXT_MY_ORDERS = "📋 ARIZALARIM"
TXT_EXECUTE = "🛠 ARIZA BAJARISH"
TXT_HISTORY = "✅ BAJARILGAN ARIZALAR TARIXI"
TXT_BACK = "⬅️ ORQAGA QAYTISH"


# ---------------------------------------------------------------------------
# Menyu klaviaturalari
# ---------------------------------------------------------------------------

def main_menu(show_warehouse: bool) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=TXT_ATM)]]
    if show_warehouse:
        rows.append([KeyboardButton(text=TXT_WAREHOUSE)])
    rows.append([KeyboardButton(text=TXT_LOGOUT)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def section_menu(show_execute: bool) -> ReplyKeyboardMarkup:
    """ATM va Omborxona uchun bir xil tuzilishdagi menyu."""
    rows = [
        [KeyboardButton(text=TXT_NEW_ORDER)],
        [KeyboardButton(text=TXT_MY_ORDERS)],
    ]
    if show_execute:
        rows.append([KeyboardButton(text=TXT_EXECUTE)])
        rows.append([KeyboardButton(text=TXT_HISTORY)])
    rows.append([KeyboardButton(text=TXT_BACK)])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def phone_request_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamni ulashish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def goals_keyboard(goals) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=g.name, callback_data=f"goal:{g.id}")]
        for g in goals
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rating_keyboard(order_id: int) -> InlineKeyboardMarkup:
    stars = [
        InlineKeyboardButton(text=str(i), callback_data=f"rate:{order_id}:{i}")
        for i in range(1, 6)
    ]
    return InlineKeyboardMarkup(inline_keyboard=[stars])


def accept_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"accept:{order_id}"),
    ]])


def finish_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🏁 Yakunlash", callback_data=f"finish:{order_id}"),
    ]])


# ---------------------------------------------------------------------------
# Menyu yuborish yordamchilari (huquq/tashkilot turiga qarab dinamik)
# ---------------------------------------------------------------------------

async def _send_main_menu(message: Message, state: FSMContext, employee, greeting: str):
    show_warehouse = await sync_to_async(is_client_employee)(employee)
    await state.set_state(MenuStates.main)
    await message.answer(greeting, reply_markup=main_menu(show_warehouse))


async def _send_atm_menu(message: Message, state: FSMContext, employee, greeting: str):
    is_worker = await sync_to_async(is_worker_employee)(employee)
    can_exec = await sync_to_async(can_execute_orders)(employee)
    show_execute = is_worker and can_exec
    await state.set_state(MenuStates.atm_menu)
    await message.answer(greeting, reply_markup=section_menu(show_execute))


async def _send_warehouse_menu(message: Message, state: FSMContext, employee, greeting: str):
    is_client = await sync_to_async(is_client_employee)(employee)
    can_exec = await sync_to_async(can_execute_orders)(employee)
    show_execute = is_client and can_exec
    await state.set_state(MenuStates.warehouse_menu)
    await message.answer(greeting, reply_markup=section_menu(show_execute))


# ---------------------------------------------------------------------------
# /start - PINFL orqali bog'lash
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)

    if employee:
        await _send_main_menu(message, state, employee, f"Salom, {employee.full_name}!")
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

    # Agar xodimning telefon raqami bazada hali yo'q bo'lsa - Telegram
    # orqali (haqiqiy, tasdiqlangan) raqamni so'raymiz.
    has_phone = bool(getattr(employee, "phone", None))
    if not has_phone:
        await state.update_data(employee_id=employee.id)
        await state.set_state(AuthStates.waiting_phone)
        await message.answer(
            f"Muvaffaqiyatli bog'landi! Salom, {employee.full_name}.\n\n"
            f"Iltimos, telefon raqamingizni pastdagi tugma orqali ulashing:",
            reply_markup=phone_request_keyboard(),
        )
        return

    await _send_main_menu(
        message, state, employee, f"Muvaffaqiyatli bog'landi! Salom, {employee.full_name}."
    )


@router.message(StateFilter(AuthStates.waiting_phone), F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)
    if not employee:
        await state.set_state(AuthStates.waiting_pinfl)
        await message.answer(
            "Sessiya topilmadi. Iltimos PINFL raqamingizni qayta kiriting:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Xavfsizlik: faqat foydalanuvchining O'Z kontaktini qabul qilamiz -
    # boshqa birovning kontaktini forward qilib yuborishi mumkin emas.
    if message.contact.user_id and message.contact.user_id != message.from_user.id:
        await message.answer(
            "Iltimos, faqat O'ZINGIZNING telefon raqamingizni ulashing.",
        )
        return

    await sync_to_async(save_employee_phone)(employee, message.contact.phone_number)
    await message.answer("Rahmat! Telefon raqamingiz saqlandi.")
    await _send_main_menu(message, state, employee, "Asosiy menyu:")


@router.message(StateFilter(AuthStates.waiting_phone))
async def process_phone_skip(message: Message, state: FSMContext):
    # Agar foydalanuvchi tugma bosish o'rniga biror matn yozsa - o'tkazib
    # yuborish imkoniyati (majburiy emas).
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)
    if not employee:
        await state.set_state(AuthStates.waiting_pinfl)
        await message.answer(
            "Sessiya topilmadi. Iltimos PINFL raqamingizni qayta kiriting:",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    await _send_main_menu(message, state, employee, "Asosiy menyu:")


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


@router.message(F.text == TXT_LOGOUT)
async def cmd_logout(message: Message, state: FSMContext):
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)
    if employee:
        await sync_to_async(unlink_telegram_chat)(employee)
    await state.clear()
    await message.answer("Bog'lanish uzildi. Qayta kirish uchun /start bosing.",
                          reply_markup=ReplyKeyboardRemove())


# ---------------------------------------------------------------------------
# ASOSIY MENYU -> BO'LIMLARGA O'TISH
# ---------------------------------------------------------------------------

@router.message(StateFilter(MenuStates.main), F.text == TXT_ATM)
async def cmd_open_atm_menu(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return
    await _send_atm_menu(message, state, employee, "ATM bo'limi:")


@router.message(StateFilter(MenuStates.main), F.text == TXT_WAREHOUSE)
async def cmd_open_warehouse_menu(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return

    # Qo'shimcha himoya: worker xodim Omborxonaga kira olmaydi.
    is_client = await sync_to_async(is_client_employee)(employee)
    if not is_client:
        await message.answer("Sizga bu bo'lim mavjud emas.")
        return

    await _send_warehouse_menu(message, state, employee, "Omborxona bo'limi:")


@router.message(
    StateFilter(MenuStates.atm_menu, MenuStates.warehouse_menu),
    F.text == TXT_BACK,
)
async def cmd_back_to_main(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return
    await _send_main_menu(message, state, employee, "Asosiy menyu:")


# ---------------------------------------------------------------------------
# ARIZA YUBORISH: kategoriya tanlash -> izoh yozish -> bo'lim menyusiga qaytish
# ---------------------------------------------------------------------------

@router.message(StateFilter(MenuStates.atm_menu), F.text == TXT_NEW_ORDER)
async def cmd_new_order_atm(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return

    goals = await sync_to_async(list_atm_goals)(employee)
    if not goals:
        await message.answer("Hozircha ariza turi mavjud emas.")
        return

    await state.update_data(order_context="atm")
    await state.set_state(OrderStates.choosing_goal)
    await message.answer("Ariza turini (kategoriyasini) tanlang:", reply_markup=goals_keyboard(goals))


@router.message(StateFilter(MenuStates.warehouse_menu), F.text == TXT_NEW_ORDER)
async def cmd_new_order_warehouse(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return

    goals = await sync_to_async(list_warehouse_goals)(employee)
    if not goals:
        await message.answer("Sizning tashkilotingiz uchun hozircha ariza turi mavjud emas.")
        return

    await state.update_data(order_context="warehouse")
    await state.set_state(OrderStates.choosing_goal)
    await message.answer("Ariza turini (kategoriyasini) tanlang:", reply_markup=goals_keyboard(goals))


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
    context = data.get("order_context", "atm")

    result = await sync_to_async(create_order)(employee, goal_id, message.text, context=context)
    text = f"✅ {result.message} (№{result.order.id})" if result.ok else f"⚠️ {result.message}"
    await message.answer(text)

    if context == "warehouse":
        await _send_warehouse_menu(message, state, employee, "Omborxona bo'limi:")
    else:
        await _send_atm_menu(message, state, employee, "ATM bo'limi:")


# ---------------------------------------------------------------------------
# ARIZALARIM (ikkala bo'limda ham bir xil - yuboruvchi sifatida)
# ---------------------------------------------------------------------------

STATUS_LABELS = {
    "viewed": "Yangi", "process": "Jarayonda", "finished": "Tayyorlandi",
    "approved": "Tasdiqlandi", "accepted": "Qabul qilindi",
    "canceled": "Bekor qilindi", "rejected": "Rad etildi",
}


@router.message(StateFilter(MenuStates.atm_menu, MenuStates.warehouse_menu), F.text == TXT_MY_ORDERS)
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
# ARIZA BAJARISH (ikkala bo'limda ham, context bo'yicha ajratilgan)
# ---------------------------------------------------------------------------

def _format_order_card(o) -> str:
    """
    Ariza haqida to'liq, saytdagi ko'rinishga o'xshash ma'lumot kartochkasi.
    HTML formatida (bot ParseMode.HTML bilan ishga tushirilgan).
    """
    sender = o.sender

    rank_part = f" {sender.rank.name}" if sender and sender.rank else ""
    author = f"{sender.full_name}{rank_part}" if sender else "-"

    date_str = o.date_creat.strftime("%d.%m.%Y, %H:%M") if o.date_creat else "-"

    # Tashkilot ierarxiyasi - saytdagidek, mavjud bo'lgan darajalar
    # alohida qatorda ko'rsatiladi (bo'sh bo'lganlari tashlab ketiladi).
    org_lines = []
    if sender and sender.organization:
        org_lines.append(sender.organization.name)
    if sender and sender.department:
        org_lines.append(sender.department.name)
    if sender and sender.directorate:
        org_lines.append(sender.directorate.name)
    if sender and sender.division:
        org_lines.append(sender.division.name)
    org_text = "\n".join(org_lines) if org_lines else "-"

    phone = sender.phone if sender and sender.phone else "-"
    comment = o.message_sender or "-"
    goal_name = o.goal.name if o.goal else "-"
    status_text = STATUS_LABELS.get(o.status, o.status)

    return (
        f"<b>Ariza #{o.id}</b>\n\n"
        f"ℹ️ <b>Ariza holati:</b> {status_text}\n"
        f"🗓 <b>Ro'yxatga olingan sana:</b> {date_str}\n"
        f"👤 <b>Ariza muallifi:</b> {author}\n"
        f"🎯 <b>Ariza maqsadi:</b> {goal_name}\n"
        f"🏢 <b>Tashkilot:</b>\n{org_text}\n"
        f"📞 <b>Telefon raqami:</b> {phone}\n"
        f"💬 <b>Qo'shimcha ma'lumot:</b> {comment}"
    )


async def _show_execute_orders(message: Message, employee, context: str):
    can_exec = await sync_to_async(can_execute_orders)(employee)
    if not can_exec:
        await message.answer("Sizda arizalarni bajarish huquqi yo'q.")
        return

    orders = await sync_to_async(list_orders_to_execute)(employee, context=context)
    if not orders:
        await message.answer("Hozircha bajarilishi kerak bo'lgan ariza yo'q.")
        return

    for o in orders:
        # DIQQAT: sync_to_async shart emas - barcha kerakli bog'liq
        # obyektlar (sender, goal, organization va h.k.) list_orders_to_execute
        # ichida select_related orqali OLDINDAN yuklab olingan, shuning
        # uchun bu yerda qo'shimcha baza so'rovi yuz bermaydi.
        text = _format_order_card(o)
        if o.status == "viewed":
            await message.answer(text, reply_markup=accept_keyboard(o.id))
        else:
            await message.answer(text, reply_markup=finish_keyboard(o.id))


@router.message(StateFilter(MenuStates.atm_menu), F.text == TXT_EXECUTE)
async def cmd_execute_orders_atm(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return
    await _show_execute_orders(message, employee, context="atm")


@router.message(StateFilter(MenuStates.warehouse_menu), F.text == TXT_EXECUTE)
async def cmd_execute_orders_warehouse(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return
    await _show_execute_orders(message, employee, context="warehouse")


@router.callback_query(F.data.startswith("accept:"))
async def cb_accept(callback: CallbackQuery):
    _, order_id = callback.data.split(":")
    employee = await sync_to_async(get_employee_by_chat_id)(callback.message.chat.id)
    if not employee:
        await callback.answer("Sessiya tugagan, /start bosing", show_alert=True)
        return

    result = await sync_to_async(accept_order)(employee, int(order_id))
    await callback.answer(result.message, show_alert=not result.ok)

    if result.ok:
        # Ariza muvaffaqiyatli qabul qilindi - tugmani "Yakunlash"ga almashtiramiz.
        await callback.message.edit_reply_markup(reply_markup=finish_keyboard(int(order_id)))
    else:
        # Ariza ALLAQACHON boshqa ijrochi tomonidan olingan (yoki boshqa
        # sabab bilan mavjud emas). Bu xabar boshqa ijrochilarga OLDINDAN
        # yuborilgan "eski" xabar bo'lishi mumkin - shuning uchun tugmani
        # olib tashlaymiz, aks holda u "hali ham faol" ko'rinib, boshqa
        # ijrochilarni chalg'itadi va qayta-qayta bosishga undaydi.
        try:
            await callback.message.edit_text(
                callback.message.html_text + "\n\n⛔️ <i>Bu ariza allaqachon boshqa ijrochi tomonidan olingan.</i>",
                reply_markup=None,
            )
        except Exception:
            # Matn allaqachon bir xil bo'lsa yoki tahrirlab bo'lmasa - hech
            # bo'lmasa tugmani olib tashlashga urinamiz.
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass


@router.callback_query(F.data.startswith("finish:"))
async def cb_finish(callback: CallbackQuery):
    _, order_id = callback.data.split(":")
    employee = await sync_to_async(get_employee_by_chat_id)(callback.message.chat.id)
    if not employee:
        await callback.answer("Sessiya tugagan, /start bosing", show_alert=True)
        return

    result = await sync_to_async(finish_order)(employee, int(order_id))
    await callback.answer(result.message, show_alert=True)
    if not result.ok:
        return

    await callback.message.edit_reply_markup()

    order = result.order
    sender = order.sender
    sender_chat_id = getattr(sender, "telegram_chat", None) if sender else None

    if sender_chat_id:
        goal_name = order.goal.name if order.goal else "-"
        text = (
            f"✅ Arizangiz (#{order.id} — {goal_name}) bajarildi!\n\n"
            f"Iltimos, xizmat sifatini baholang:"
        )
        try:
            await callback.bot.send_message(
                sender_chat_id, text, reply_markup=rating_keyboard(order.id)
            )
        except Exception:
            logger.exception(
                "Yuboruvchiga (chat_id=%s) baholash xabari yuborilmadi (order=%s)",
                sender_chat_id, order.id,
            )


# ---------------------------------------------------------------------------
# BAJARILGAN ARIZALAR TARIXI (ikkala bo'limda ham, context bo'yicha)
# ---------------------------------------------------------------------------

async def _show_completed_orders(message: Message, employee, context: str):
    can_exec = await sync_to_async(can_execute_orders)(employee)
    if not can_exec:
        await message.answer("Sizda bu bo'limni ko'rish huquqi yo'q.")
        return

    orders = await sync_to_async(list_completed_orders)(employee, context=context)
    if not orders:
        await message.answer("Siz hali hech qanday arizani bajarmagansiz.")
        return

    lines = [
        f"#{o.id} — {o.goal.name if o.goal else '-'} — "
        f"{STATUS_LABELS.get(o.status, o.status)}"
        + (f" — baho: {o.rating}⭐" if o.rating else "")
        for o in orders
    ]
    await message.answer("\n".join(lines))


@router.message(StateFilter(MenuStates.atm_menu), F.text == TXT_HISTORY)
async def cmd_completed_orders_atm(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return
    await _show_completed_orders(message, employee, context="atm")


@router.message(StateFilter(MenuStates.warehouse_menu), F.text == TXT_HISTORY)
async def cmd_completed_orders_warehouse(message: Message, state: FSMContext):
    employee = await _require_employee(message, state)
    if not employee:
        return
    await _show_completed_orders(message, employee, context="warehouse")


# ---------------------------------------------------------------------------
# BAHOLASH - faqat 1-5, bekor qilish yo'q
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
# ZAXIRA (fallback) - hech qaysi handler'ga mos kelmagan xabarlar uchun.
# Bu handler ENG OXIRIDA turishi shart.
# ---------------------------------------------------------------------------

@router.message()
async def fallback_handler(message: Message, state: FSMContext):
    employee = await sync_to_async(get_employee_by_chat_id)(message.chat.id)
    if employee:
        await message.answer(
            "Kechirasiz, buyruq tushunarsiz yoki sessiya eskirgan. "
            "Iltimos /start bosing.",
        )
        await _send_main_menu(message, state, employee, "Asosiy menyu:")
    else:
        await state.set_state(AuthStates.waiting_pinfl)
        await message.answer(
            "Iltimos /start bosing yoki PINFL raqamingizni kiriting:",
            reply_markup=ReplyKeyboardRemove(),
        )


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
            force=True,
        )
        asyncio.run(self._run(token))

    async def _run(self, token: str):
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(router)

        self.stdout.write(self.style.SUCCESS("Bot ishga tushdi (polling)..."))
        await dp.start_polling(bot)