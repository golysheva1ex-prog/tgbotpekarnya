from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.db import (
    db_get_user_by_tg, db_get_or_create_cart, db_get_cart_items,
    db_update_order_totals, db_get_setting, db_get_order_basic, db_set_order_checkout,
    db_clear_cart, db_get_product, db_list_products_public, db_add_item_to_cart
)
from app.keyboards import products_list_kb, product_detail_kb, cart_kb

router = Router()

PAGE_SIZE = 10

@router.message(F.text == "Каталог")
async def show_catalog(message: Message):
    items, total = await db_list_products_public(page=1, page_size=PAGE_SIZE)
    if not total:
        await message.answer("Каталог пуст. Обратитесь к администратору.")
        return
    await message.answer("Выберите товар:", reply_markup=products_list_kb(items, 1, total, PAGE_SIZE))

@router.callback_query(F.data.startswith("plist:"))
async def paged_list(cb: CallbackQuery):
    try:
        page = int(cb.data.split(":")[1])
    except:
        page = 1
    page = max(1, page)
    items, total = await db_list_products_public(page=page, page_size=PAGE_SIZE)
    if not total:
        await cb.answer("Каталог пуст.", show_alert=True); return
    await cb.message.edit_text("Выберите товар:", reply_markup=products_list_kb(items, page, total, PAGE_SIZE))

@router.callback_query(F.data.startswith("view:"))
async def view_item(cb: CallbackQuery):
    # формат: view:<prod_id>:p:<page>
    parts = cb.data.split(":")
    prod_id = int(parts[1])
    page = int(parts[3]) if len(parts) > 3 else 1
    p = await db_get_product(prod_id)
    if not p or not p["available"]:
        await cb.answer("Товар недоступен", show_alert=True)
        return
    text = f"📦 {p['title']}\nЦена: {p['price_minor']/100:.2f} ₽"
    kb = product_detail_kb(prod_id=p["id"], page=page)
    if p.get("photo_file_id"):
        await cb.message.answer_photo(photo=p["photo_file_id"], caption=text, reply_markup=kb)
        await cb.answer()
    else:
        await cb.message.edit_text(text, reply_markup=kb)

@router.callback_query(F.data.startswith("add:"))
async def add_item(cb: CallbackQuery):
    prod_id = int(cb.data.split(":")[1])
    p = await db_get_product(prod_id)
    if not p or not p["available"]:
        await cb.answer("Товар недоступен", show_alert=True)
        return
    user = await db_get_user_by_tg(cb.from_user.id)
    if not user:
        await cb.answer("Сначала зарегистрируйтесь: /start", show_alert=True)
        return
    order_id = await db_get_or_create_cart(user["id"])
    await db_add_item_to_cart(order_id, p["sku"], p["title"], p["price_minor"])
    await db_update_order_totals(order_id, 0)
    await cb.answer("Добавлено в корзину")

@router.message(F.text == "Корзина")
async def cart(message: Message):
    user = await db_get_user_by_tg(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь: /start")
        return
    order_id = await db_get_or_create_cart(user["id"])
    items = await db_get_cart_items(order_id)
    if not items:
        await message.answer("Корзина пуста. Откройте «Каталог» и добавьте товары.")
        return
    subtotal = sum(i["unit_price_minor"] * i["qty"] for i in items)
    lines = ["Корзина:"]
    for it in items:
        lines.append(f"- {it['title']} x{it['qty']} = {(it['unit_price_minor']*it['qty'])/100:.2f} ₽")
    lines.append(f"Итого по товарам: {subtotal/100:.2f} ₽")
    await message.answer("\n".join(lines), reply_markup=cart_kb(True))

@router.callback_query(F.data == "cart_clear")
async def cart_clear(cb: CallbackQuery):
    user = await db_get_user_by_tg(cb.from_user.id)
    if not user:
        await cb.answer("Сначала /start", show_alert=True)
        return
    order_id = await db_get_or_create_cart(user["id"])
    await db_clear_cart(order_id)
    items, total = await db_list_products_public(page=1, page_size=PAGE_SIZE)
    await cb.message.edit_text("Корзина очищена.", reply_markup=products_list_kb(items, 1, total, PAGE_SIZE))

@router.callback_query(F.data == "checkout")
async def checkout(cb: CallbackQuery):
    user = await db_get_user_by_tg(cb.from_user.id)
    if not user:
        await cb.answer("Сначала /start", show_alert=True)
        return
    order_id = await db_get_or_create_cart(user["id"])
    items = await db_get_cart_items(order_id)
    if not items:
        await cb.answer("Корзина пуста.", show_alert=True)
        return
    courier_fee_minor = int(await db_get_setting("courier_fee_minor", "15000"))
    await db_update_order_totals(order_id, 0)
    from app.keyboards import delivery_kb
    await cb.message.edit_text("Выберите способ доставки:", reply_markup=delivery_kb(courier_fee_minor))

@router.callback_query(F.data.startswith("deliv:"))
async def select_delivery(cb: CallbackQuery):
    from app.db import db_get_default_address, db_get_order_basic
    from app.utils import format_address

    kind = cb.data.split(":")[1]  # pickup/courier
    user = await db_get_user_by_tg(cb.from_user.id)
    order_id = await db_get_or_create_cart(user["id"])
    courier_fee_minor = int(await db_get_setting("courier_fee_minor", "15000"))

    addr_snap = None
    if kind == "courier":
        addr = await db_get_default_address(user["id"])
        if not addr:
            await cb.answer("Сначала укажите адрес доставки в меню «Адрес доставки».", show_alert=True)
            return
        addr_snap = {
            "address_line": addr["address_line"],
            "apt": addr.get("apt"),
            "entrance": addr.get("entrance"),
            "floor": addr.get("floor"),
            "comment": addr.get("comment")
        }
        await db_update_order_totals(order_id, courier_fee_minor)
    else:
        await db_update_order_totals(order_id, 0)

    order = await db_get_order_basic(order_id)
    items = await db_get_cart_items(order_id)
    lines = ["Заказ к подтверждению:"]
    for it in items:
        lines.append(f"- {it['title']} x{it['qty']} = {(it['unit_price_minor']*it['qty'])/100:.2f} ₽")
    lines.append(f"Товары: {order['subtotal_minor']/100:.2f} ₽")
    lines.append(f"Доставка: {order['delivery_fee_minor']/100:.2f} ₽ ({'Курьер' if kind=='courier' else 'Самовывоз'})")
    lines.append(f"Итого: {order['total_minor']/100:.2f} ₽")
    if addr_snap:
        lines.append("Адрес: " + format_address(addr_snap))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подтвердить заказ", callback_data=f"confirm:{kind}")],
        [InlineKeyboardButton(text="Назад к каталогу", callback_data="plist:1")]
    ])
    await cb.message.edit_text("\n".join(lines), reply_markup=kb)

@router.callback_query(F.data.startswith("confirm:"))
async def confirm_order(cb: CallbackQuery):
    kind = cb.data.split(":")[1]
    user = await db_get_user_by_tg(cb.from_user.id)
    order_id = await db_get_or_create_cart(user["id"])
    from app.db import db_get_default_address
    addr = await db_get_default_address(user["id"]) if kind == "courier" else None
    await db_set_order_checkout(order_id, kind, addr)
    order = await db_get_order_basic(order_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Оплатить онлайн (демо)", callback_data="demo_pay")],
        [InlineKeyboardButton(text="Статус заказа (демо)", callback_data="demo_status")]
    ])
    await cb.message.edit_text(
        f"Заказ #{order_id} оформлен и отправлен на подтверждение.\n"
        f"Статус: {order['status']}.\n"
        f"Итого к оплате: {order['total_minor']/100:.2f} ₽.",
        reply_markup=kb
    )
