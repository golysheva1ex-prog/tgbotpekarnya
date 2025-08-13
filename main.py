import asyncio
from aiogram import Bot, Dispatcher

from app.config import BOT_TOKEN, DEFAULT_COURIER_FEE_RUB
from app.db import init_db
from app.handlers import (
    start_registration, address, catalog_cart, payments_demo, admin, help as help_h
)

async def main():
    await init_db(default_courier_fee_rub=DEFAULT_COURIER_FEE_RUB)

    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    # если когда-то включали webhook — снимем, чтобы polling не конфликтовал
    await bot.delete_webhook(drop_pending_updates=True)

    dp.include_routers(
        start_registration.router,
        address.router,
        catalog_cart.router,
        payments_demo.router,
        admin.router,
        help_h.router,
    )

    print("Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
