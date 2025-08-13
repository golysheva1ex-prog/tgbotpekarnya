from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.config import ADMIN_TG_IDS
from app.db import (
    db_get_user_active_orders, db_set_order_status, db_get_setting, db_set_setting,
    db_list_products_admin, db_create_product, db_set_product_available, db_update_product_price,
    db_get_product, db_update_product_title, db_delete_product, db_update_product_photo,
    db_get_or_create_general_category_id
)
from app.keyboards import admin_kb, admin_products_kb, admin_product_actions_kb
from app.utils import format_address, make_unique_sku
import json
import re

router = Router()

class AddProductFSM(StatesGroup):
    product_title = State()
    product_price = State()
    product_photo = State()

class EditProductFSM(StatesGroup):
    waiting_new_title = State()
    waiting_new_price = State()
    waiting_new_photo = State()

@router.message(F.text == "Админ")
async def admin_menu(message: Message):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа.")
        return
    await message.answer("Админ-меню:", reply_markup=admin_kb())

@router.callback_query(F.data == "adm:back")
async def adm_back(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    await cb.message.edit_text("Админ-меню:", reply_markup=admin_kb())

# ------- Добавление товара (без категорий) -------
@router.callback_query(F.data == "adm:add_product")
async def adm_add_product_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    await cb.message.edit_text("Введите название товара (текстом):")
    await state.set_state(AddProductFSM.product_title)

@router.message(AddProductFSM.product_title)
async def adm_product_title(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа."); return
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("Название слишком короткое. Введите снова.")
        return
    await state.update_data(product_title=title)
    await message.answer("Введите цену в рублях (целое число), например 79:")
    await state.set_state(AddProductFSM.product_price)

@router.message(AddProductFSM.product_price)
async def adm_product_price(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа."); return
    digits = re.sub(r"\D", "", message.text or "")
    if not digits:
        await message.answer("Введите целое число, например 79.")
        return
    await state.update_data(price_minor=int(digits) * 100)
    await message.answer("Отправьте фото товара одним сообщением или напишите «Пропустить».")
    await state.set_state(AddProductFSM.product_photo)

@router.message(AddProductFSM.product_photo, F.photo)
async def adm_product_photo_set(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await _finalize_create_product(message, state, photo_file_id=file_id)

@router.message(AddProductFSM.product_photo)
async def adm_product_photo_skip_or_error(message: Message, state: FSMContext):
    text = (message.text or "").strip().lower()
    if text in ("пропустить", "skip"):
        await _finalize_create_product(message, state, photo_file_id=None)
    else:
        await message.answer("Это не фото. Пришлите фото или напишите «Пропустить».")

async def _finalize_create_product(message: Message, state: FSMContext, photo_file_id: str | None):
    data = await state.get_data()
    title = data.get("product_title")
    price_minor = data.get("price_minor")
    sku = await make_unique_sku(title)
    cat_id = await db_get_or_create_general_category_id()  # служебная категория
    prod_id = await db_create_product(cat_id=cat_id, title=title, price_minor=price_minor, sku=sku, available=1, photo_file_id=photo_file_id)
    await state.clear()
    p = await db_get_product(prod_id)
    await message.answer(
        f"Товар добавлен:\n— Название: {p['title']}\n— Цена: {p['price_minor']/100:.2f} ₽\n— SKU: {p['sku']}\n— Фото: {'есть' if p.get('photo_file_id') else 'нет'}",
        reply_markup=admin_kb()
    )

# ------- Список товаров и действия -------
@router.callback_query(F.data == "adm:list_products")
async def adm_list_products(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prods = await db_list_products_admin(limit=50)
    await cb.message.edit_text("Товары (последние 50):", reply_markup=admin_products_kb(prods))

@router.callback_query(F.data.regexp(r"^adm:prod:\d+$"))
async def adm_product_actions(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prod_id = int(cb.data.split(":")[2])
    p = await db_get_product(prod_id)
    if not p:
        await cb.answer("Товар не найден", show_alert=True); return
    text = (
        f"Товар #{p['id']}\n"
        f"Название: {p['title']}\n"
        f"Цена: {p['price_minor']/100:.2f} ₽\n"
        f"Фото: {'есть' if p.get('photo_file_id') else 'нет'}\n"
        f"Статус: {'ON' if p['available'] else 'OFF'}"
    )
    await cb.message.edit_text(text, reply_markup=admin_product_actions_kb(p["id"], p["available"]))

@router.callback_query(F.data.startswith("adm:prod:rename:"))
async def adm_product_rename_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prod_id = int(cb.data.split(":")[3])
    await state.update_data(prod_id=prod_id)
    await cb.message.edit_text("Введите новое название товара:")
    await state.set_state(EditProductFSM.waiting_new_title)

@router.message(EditProductFSM.waiting_new_title)
async def adm_product_rename_finish(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа."); return
    title = (message.text or "").strip()
    if len(title) < 2:
        await message.answer("Название слишком короткое. Введите снова.")
        return
    data = await state.get_data()
    await db_update_product_title(data["prod_id"], title)
    await state.clear()
    await message.answer("Название товара обновлено.", reply_markup=admin_kb())

@router.callback_query(F.data.startswith("adm:prod:price:"))
async def adm_product_price_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prod_id = int(cb.data.split(":")[3])
    await state.update_data(prod_id=prod_id)
    await cb.message.edit_text("Введите новую цену в рублях (целое число):")
    await state.set_state(EditProductFSM.waiting_new_price)

@router.message(EditProductFSM.waiting_new_price)
async def adm_product_price_finish(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа."); return
    digits = re.sub(r"\D","", message.text or "")
    if not digits:
        await message.answer("Введите целое число, например 79.")
        return
    data = await state.get_data()
    await db_update_product_price(data["prod_id"], int(digits)*100)
    await state.clear()
    await message.answer("Цена обновлена.", reply_markup=admin_kb())

@router.callback_query(F.data.startswith("adm:prod:photo:"))
async def adm_product_photo_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prod_id = int(cb.data.split(":")[3])
    await state.update_data(prod_id=prod_id)
    await cb.message.edit_text("Пришлите новое фото для товара одним сообщением.")
    await state.set_state(EditProductFSM.waiting_new_photo)

@router.message(EditProductFSM.waiting_new_photo, F.photo)
async def adm_product_photo_finish(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа."); return
    file_id = message.photo[-1].file_id
    data = await state.get_data()
    await db_update_product_photo(data["prod_id"], file_id)
    await state.clear()
    await message.answer("Фото обновлено.", reply_markup=admin_kb())

@router.callback_query(F.data.startswith("adm:prod:photo_del:"))
async def adm_product_photo_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prod_id = int(cb.data.split(":")[3])
    await db_update_product_photo(prod_id, None)
    await cb.answer("Фото удалено.", show_alert=True)

@router.callback_query(F.data.startswith("adm:prod:toggle:"))
async def adm_product_toggle(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prod_id = int(cb.data.split(":")[3])
    p = await db_get_product(prod_id)
    if not p:
        await cb.answer("Товар не найден", show_alert=True); return
    new_av = 0 if p["available"] else 1
    await db_set_product_available(prod_id, new_av)
    p = await db_get_product(prod_id)
    text = (
        f"Товар #{p['id']}\nНазвание: {p['title']}\n"
        f"Цена: {p['price_minor']/100:.2f} ₽\nФото: {'есть' if p.get('photo_file_id') else 'нет'}\n"
        f"Статус: {'ON' if p['available'] else 'OFF'}"
    )
    await cb.message.edit_text(text, reply_markup=admin_product_actions_kb(p["id"], p["available"]))

@router.callback_query(F.data.startswith("adm:prod:delete:"))
async def adm_product_delete(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    prod_id = int(cb.data.split(":")[3])
    await db_delete_product(prod_id)
    prods = await db_list_products_admin(limit=50)
    await cb.message.edit_text("Товар удалён. Список:", reply_markup=admin_products_kb(prods))

# ------- Заказы и тариф -------
@router.callback_query(F.data == "adm:orders")
async def adm_orders(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    from app.db import db_get_user_active_orders
    orders = await db_get_user_active_orders()
    if not orders:
        await cb.message.edit_text("Активных заказов нет.", reply_markup=admin_kb())
        return
    lines = []
    for o in orders:
        addr = json.loads(o.get("address_snapshot") or "{}")
        addr_txt = format_address(addr) if addr else "Самовывоз"
        lines.append(f"#{o['id']} | {o['status']} | {o['total_minor']/100:.2f} ₽ | {o['name']} {o['phone']} | {addr_txt}")
    text = "Заказы:\n" + "\n".join(lines)[:3500] + "\n\nСменить статус: /set <id> <status>"
    await cb.message.edit_text(text, reply_markup=admin_kb())

@router.message(Command("set"))
async def admin_set_status(message: Message):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа."); return
    parts = (message.text or "").split()
    if len(parts) != 3:
        await message.answer("Использование: /set <order_id> <status>\nСтатусы: confirming, preparing, delivering, delivered, canceled")
        return
    try:
        oid = int(parts[1])
    except:
        await message.answer("order_id должен быть числом.")
        return
    status = parts[2]
    if status not in ("confirming","preparing","delivering","delivered","canceled"):
        await message.answer("Неверный статус.")
        return
    await db_set_order_status(oid, status)
    await message.answer(f"Статус заказа #{oid} изменён на {status}.")

@router.callback_query(F.data == "adm:tariff")
async def adm_tariff(cb: CallbackQuery):
    if cb.from_user.id not in ADMIN_TG_IDS:
        await cb.answer("Нет доступа", show_alert=True); return
    fee_minor = int(await db_get_setting("courier_fee_minor", "15000"))
    fee_rub = fee_minor // 100
    await cb.message.edit_text(f"Текущий тариф курьера: {fee_rub} ₽.\nОтправьте команду: /tariff <руб>")

@router.message(Command("tariff"))
async def adm_tariff_set(message: Message):
    if message.from_user.id not in ADMIN_TG_IDS:
        await message.answer("Нет доступа."); return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Использование: /tariff <руб>, например /tariff 150")
        return
    digits = re.sub(r"\D","", parts[1])
    if not digits:
        await message.answer("Введите число, например 150.")
        return
    fee_minor = int(digits) * 100
    await db_set_setting("courier_fee_minor", str(fee_minor))
    await message.answer(f"Тариф обновлён: {int(digits)} ₽")
