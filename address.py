from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from app.db import db_get_user_by_tg, db_set_default_address
from app.states import Addr
from app.utils import format_address

router = Router()

@router.message(F.text == "Адрес доставки")
async def address_menu(message: Message, state: FSMContext):
    user = await db_get_user_by_tg(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    await message.answer("Отправьте адрес (улица и дом) или нажмите «Отмена».")
    await state.set_state(Addr.address_line)

@router.message(Addr.address_line)
async def addr_line(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 5:
        await message.answer("Похоже на слишком короткий адрес. Введите улицу и дом.")
        return
    await state.update_data(address_line=text)
    await message.answer("Квартира/офис (или «Нет»):")
    await state.set_state(Addr.apt)

@router.message(Addr.apt)
async def addr_apt(message: Message, state: FSMContext):
    val = (message.text or "").strip()
    await state.update_data(apt=None if val.lower() == "нет" else val)
    await message.answer("Подъезд (или «Нет»):")
    await state.set_state(Addr.entrance)

@router.message(Addr.entrance)
async def addr_entrance(message: Message, state: FSMContext):
    val = (message.text or "").strip()
    await state.update_data(entrance=None if val.lower() == "нет" else val)
    await message.answer("Этаж (или «Нет»):")
    await state.set_state(Addr.floor)

@router.message(Addr.floor)
async def addr_floor(message: Message, state: FSMContext):
    val = (message.text or "").strip()
    await state.update_data(floor=None if val.lower() == "нет" else val)
    await message.answer("Комментарий курьеру (или «Нет»):")
    await state.set_state(Addr.comment)

@router.message(Addr.comment)
async def addr_comment(message: Message, state: FSMContext):
    val = (message.text or "").strip()
    data = await state.get_data()
    addr = {
        "address_line": data.get("address_line", ""),
        "apt": data.get("apt"),
        "entrance": data.get("entrance"),
        "floor": data.get("floor"),
        "comment": None if val.lower() == "нет" else val if val else None
    }
    user = await db_get_user_by_tg(message.from_user.id)
    await db_set_default_address(user["id"], addr)
    await state.clear()
    await message.answer("Адрес сохранён как адрес по умолчанию:\n" + format_address(addr))
