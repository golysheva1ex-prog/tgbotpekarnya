from aiogram.fsm.state import State, StatesGroup

class Reg(StatesGroup):
    waiting_name = State()
    waiting_phone = State()

class Addr(StatesGroup):
    address_line = State()
    apt = State()
    entrance = State()
    floor = State()
    comment = State()

class AdminStates(StatesGroup):
    waiting_tariff = State()
    waiting_catalog_url = State()
from aiogram.fsm.state import State, StatesGroup

class Reg(StatesGroup):
    waiting_name = State()
    waiting_phone = State()
    waiting_otp = State()      # добавили состояние для ввода кода

# остальные StatesGroup без изменений
