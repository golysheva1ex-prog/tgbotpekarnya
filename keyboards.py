from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from math import ceil

def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Каталог"), KeyboardButton(text="Корзина")],
        [KeyboardButton(text="Адрес доставки"), KeyboardButton(text="Мой профиль")],
        [KeyboardButton(text="Оплатить онлайн"), KeyboardButton(text="Помощь")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="Админ")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def contact_kb() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="Поделиться телефоном", request_contact=True)],
        [KeyboardButton(text="Отмена")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def products_list_kb(items: list[dict], page: int, total: int, page_size: int) -> InlineKeyboardMarkup:
    rows = []
    for it in items:
        price_rub = it["price_minor"] // 100
        rows.append([InlineKeyboardButton(
            text=f"🔍 {it['title']} — {price_rub} ₽",
            callback_data=f"view:{it['id']}:p:{page}"
        )])
    # Пагинация
    pages = max(1, ceil(total / max(1, page_size)))
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"plist:{page-1}"))
    if page < pages:
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"plist:{page+1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="Каталог пуст", callback_data="noop")]])

def product_detail_kb(prod_id: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить в корзину", callback_data=f"add:{prod_id}")],
        [InlineKeyboardButton(text="Назад к списку", callback_data=f"plist:{page}")]
    ])

def cart_kb(has_items: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_items:
        rows.append([InlineKeyboardButton(text="Оформить заказ", callback_data="checkout")])
        rows.append([InlineKeyboardButton(text="Очистить корзину", callback_data="cart_clear")])
    rows.append([InlineKeyboardButton(text="Назад к каталогу", callback_data="plist:1")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def delivery_kb(courier_fee_minor: int) -> InlineKeyboardMarkup:
    fee_rub = courier_fee_minor // 100
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Самовывоз (0 ₽)", callback_data="deliv:pickup")],
        [InlineKeyboardButton(text=f"Курьер ({fee_rub} ₽ по городу)", callback_data="deliv:courier")]
    ])

def admin_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить товар", callback_data="adm:add_product")],
        [InlineKeyboardButton(text="Список товаров", callback_data="adm:list_products")],
        [InlineKeyboardButton(text="Заказы в работе", callback_data="adm:orders")],
        [InlineKeyboardButton(text="Тариф доставки", callback_data="adm:tariff")]
    ])

def admin_products_kb(products: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for p in products:
        status = "ON" if p["available"] else "OFF"
        price = int(round(p["price_minor"] / 100))
        rows.append([InlineKeyboardButton(
            text=f"#{p['id']} {p['title']} — {price} ₽ [{status}]",
            callback_data=f"adm:prod:{p['id']}"
        )])
    if not rows:
        rows = [[InlineKeyboardButton(text="Нет товаров", callback_data="noop")]]
    rows.append([InlineKeyboardButton(text="Назад (Админ)", callback_data="adm:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def admin_product_actions_kb(prod_id: int, available: int) -> InlineKeyboardMarkup:
    toggle_text = "Выключить (OFF)" if available else "Включить (ON)"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить название", callback_data=f"adm:prod:rename:{prod_id}")],
        [InlineKeyboardButton(text="Изменить цену", callback_data=f"adm:prod:price:{prod_id}")],
        [InlineKeyboardButton(text="Изменить картинку", callback_data=f"adm:prod:photo:{prod_id}")],
        [InlineKeyboardButton(text="Удалить картинку", callback_data=f"adm:prod:photo_del:{prod_id}")],
        [InlineKeyboardButton(text=toggle_text, callback_data=f"adm:prod:toggle:{prod_id}")],
        [InlineKeyboardButton(text="Удалить товар навсегда", callback_data=f"adm:prod:delete:{prod_id}")],
        [InlineKeyboardButton(text="Назад к списку", callback_data="adm:list_products")]
    ])
