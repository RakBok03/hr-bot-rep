from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def main_menu_reply(resize_keyboard: bool = True) -> ReplyKeyboardMarkup:
    buttons = [
        [KeyboardButton(text="Оставить заявку")],
        [KeyboardButton(text="Обратная связь")],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=resize_keyboard)

