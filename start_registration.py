from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.context import FSMContext

from app.db import (
    db_get_user_by_tg, db_create_or_update_user_base,
    db_set_user_phone_and_otp, db_mark_user_verified, db_get_default_address
)
from app.keyboards import main_menu_kb, contact_kb
from app.utils import normalize_phone, format_address, make_otp_code, hash_otp
from app.states import Reg
from app.config import ADMIN_TG_IDS, OTP_TTL_MINUTES
from app.sms import send_sms

router = Router()

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    user = await db_get_user_by_tg(message.from_user.id)
    if user and user.get("is_verified"):
        is_admin = message.from_user.id in ADMIN_TG_IDS
        await state.clear()
        await message.answer("Добро пожаловать! Выберите действие:", reply_markup=main_menu_kb(is_admin))
        return

    if not user:
        cancel_kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True)
        await message.answer("Привет! Давайте зарегистрируемся.\nВведите ваше имя:", reply_markup=cancel_kb)
        await state.set_state(Reg.waiting_name)
        return

    await message.answer(
        "Для продолжения подтвердите номер телефона. Отправьте контакт кнопкой ниже или введите номер.",
        reply_markup=contact_kb()
    )
    await state.set_state(Reg.waiting_phone)

@router.message(Command("cancel"))
@router.message(F.text.casefold() == "отмена")
async def cancel(message: Message, state: FSMContext):
    is_admin = message.from_user.id in ADMIN_TG_IDS
    await state.clear()
    await message.answer("Действие отменено. Главное меню:", reply_markup=main_menu_kb(is_admin))

@router.message(Reg.waiting_name)
async def reg_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("Имя слишком короткое. Введите ещё раз или нажмите «Отмена».")
        return
    await db_create_or_update_user_base(message.from_user.id, name)
    await message.answer("Отправьте ваш номер телефона (кнопкой ниже) или введите вручную.", reply_markup=contact_kb())
    await state.set_state(Reg.waiting_phone)

@router.message(Reg.waiting_phone)
async def reg_phone(message: Message, state: FSMContext):
    raw = message.contact.phone_number if (message.contact and message.contact.phone_number) else (message.text or "")
    phone = normalize_phone(raw)
    if not phone:
        await message.answer("Не удалось распознать номер. Попробуйте снова или нажмите «Отмена».")
        return

    code = make_otp_code()
    ok = await send_sms(phone, f"Ваш код подтверждения: {code}")
    if not ok:
        await message.answer("Не удалось отправить SMS. Попробуйте позже.")
        return

    expires = (datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES)).isoformat()
    await db_set_user_phone_and_otp(
        tg_id=message.from_user.id,
        phone=phone,
        otp_code_hash=hash_otp(code),
        expires_iso=expires
    )
    await message.answer("Код отправлен по SMS. Введите код цифрами:")
    await state.set_state(Reg.waiting_otp)

@router.message(Reg.waiting_otp)
async def reg_otp(message: Message, state: FSMContext):
    code = (message.text or "").strip()
    user = await db_get_user_by_tg(message.from_user.id)
    if not user or not user.get("otp_code_hash"):
        await state.clear()
        await message.answer("Сессия подтверждения не найдена. Начните заново: /start")
        return
    try:
        exp = datetime.fromisoformat(user["otp_expires_at"]) if user.get("otp_expires_at") else None
    except:
        exp = None
    if not exp or exp < datetime.utcnow():
        await state.clear()
        await message.answer("Срок действия кода истёк. Запросите код ещё раз: /start")
        return
    if hash_otp(code) != user["otp_code_hash"]:
        await message.answer("Неверный код. Попробуйте ещё раз.")
        return

    await db_mark_user_verified(message.from_user.id)
    await state.clear()
    is_admin = message.from_user.id in ADMIN_TG_IDS
    await message.answer("Телефон подтверждён! Добро пожаловать.", reply_markup=main_menu_kb(is_admin))

@router.message(F.text == "Мой профиль")
async def my_profile(message: Message):
    user = await db_get_user_by_tg(message.from_user.id)
    if not user:
        await message.answer("Вы ещё не зарегистрированы. Нажмите /start.")
        return
    addr = await db_get_default_address(user["id"])
    addr_text = format_address(addr) if addr else "Адрес не указан"
    status = "подтверждён" if user.get("is_verified") else "не подтверждён"
    await message.answer(
        f"Профиль:\n— Имя: {user['name']}\n— Телефон: {user['phone']} ({status})\n— Адрес по умолчанию: {addr_text}"
    )
