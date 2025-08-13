from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

@router.message(F.text == "Оплатить онлайн")
async def pay_placeholder(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Перейти к оплате (демо)", callback_data="demo_pay")],
        [InlineKeyboardButton(text="Проверить статус (демо)", callback_data="demo_status")]
    ])
    await message.answer("Онлайн-оплата в демо-режиме. Реальный эквайринг будет подключён позже.", reply_markup=kb)

@router.callback_query(F.data == "demo_pay")
async def demo_pay(cb: CallbackQuery):
    await cb.answer("Демонстрация: оплата не подключена.", show_alert=True)

@router.callback_query(F.data == "demo_status")
async def demo_status(cb: CallbackQuery):
    await cb.answer("Демонстрация: заказ ожидает обработки.", show_alert=True)
