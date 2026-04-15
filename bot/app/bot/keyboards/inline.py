from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_inline() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Статус заявки", callback_data="request_status")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def registration_button() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text="Зарегистрироваться", callback_data="register")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

