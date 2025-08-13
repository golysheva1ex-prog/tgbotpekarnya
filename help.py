from aiogram import Router, F
from aiogram.types import Message

router = Router()

@router.message(F.text == "Помощь")
async def help_menu(message: Message):
    await message.answer(
        "Помощь:\n"
        "— /start — начать, регистрация (имя + телефон).\n"
        "— Каталог — выберите категорию и добавляйте товары.\n"
        "— Корзина — просмотр и оформление.\n"
        "— Адрес доставки — сохраните адрес для курьера.\n"
        "— Оплатить онлайн — демо-кнопки, без реального списания.\n"
        "Статусы заказа: confirming → preparing → delivering → delivered.\n"
        "Админ-команды: /set <id> <status>, /tariff <руб>, /seturl <URL>, /refresh"
    )
