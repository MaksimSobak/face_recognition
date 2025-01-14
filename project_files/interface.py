from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from project_files.config import UNKNOWN_FACES
import os
UNKNOWN_FACES_DIR = UNKNOWN_FACES

def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Change Tolerance", callback_data="change_tolerance"),
        InlineKeyboardButton(text="Show Stats", callback_data="show_stats"),
        InlineKeyboardButton(text="Current tolerance", callback_data="show_current_tolerance"),
    )
    builder.row(
        InlineKeyboardButton(text="Show Unknown Faces", callback_data="show_unknown_faces"),
    )
    return builder.as_markup()

def get_tolerance_menu():
    builder = InlineKeyboardBuilder()
    for tol in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]:
        builder.button(text=f"Tolerance {tol}", callback_data=f"set_tolerance_{tol}")
    builder.adjust(2)
    return builder.as_markup()

def get_next_unknown_face_filename():
    import re
    existing_files = os.listdir(UNKNOWN_FACES_DIR)
    numbers = []
    for f in existing_files:
        match = re.search(r'_(\d+)\.', f)
        if match:
            numbers.append(int(match.group(1)))

    next_number = max(numbers, default=0) + 1
    return f"unknown_face_{next_number}.jpg"