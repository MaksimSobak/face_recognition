from project_files.recognition_algorythm import recognize_and_register_faces, UNKNOWN_FACES_DIR, process_uploaded_video, process_uploaded_photo, resize_image_to_fixed_size
from project_files.database_connection import load_database, save_new_face
from project_files.interface import get_main_menu, get_tolerance_menu
import face_recognition
import os
import tempfile
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from project_files import config

unknown_faces_state = {}

TOKEN = config.BOT_TOKEN
bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def start_handler(message: Message):
    await message.answer(
        "Добро пожаловать! Используйте команду:\n"
        "/recognize - распознавание лиц с камеры.\n"
        "Отправьте фото для анализа готовых изображений.",
        parse_mode="html",
        reply_markup=get_main_menu()
    )


@dp.callback_query(lambda c: c.data == "change_tolerance")
async def change_tolerance_callback(callback: types.CallbackQuery):
    await callback.message.answer("Выберите значение tolerance:", reply_markup=get_tolerance_menu())
    await callback.answer()

# unknown_faces_state = {}

@dp.callback_query(lambda c: c.data == "show_unknown_faces")
async def show_unknown_faces_callback(callback: types.CallbackQuery):
    unknown_faces_files = sorted(os.listdir(UNKNOWN_FACES_DIR))

    if not unknown_faces_files:
        await callback.message.answer("Нет неизвестных лиц в базе.")
        await callback.answer()
        return

    unknown_faces_state[callback.message.chat.id] = {
        "files": unknown_faces_files,
        "index": 0
    }

    await send_unknown_face(callback.message.chat.id)
    await callback.answer()

async def send_unknown_face(chat_id):
    state = unknown_faces_state.get(chat_id)
    if not state:
        return

    files = state["files"]
    index = state["index"]

    current_face_path = os.path.join(UNKNOWN_FACES_DIR, files[index])

    temp_resized_path = os.path.join(tempfile.gettempdir(), f"resized_{files[index]}")

    await resize_image_to_fixed_size(current_face_path, temp_resized_path)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Previous", callback_data="previous_face"),
            InlineKeyboardButton(text="Next", callback_data="next_face")
        ],
        [
            InlineKeyboardButton(text="Add Person", callback_data="add_person"),
            InlineKeyboardButton(text="Delete Photo", callback_data="delete_photo")
        ]
    ])

    # Отправляем фото
    await bot.send_photo(chat_id, FSInputFile(temp_resized_path), reply_markup=keyboard)


@dp.callback_query(lambda c: c.data == "delete_photo")
async def delete_photo_callback(callback: types.CallbackQuery):
    state = unknown_faces_state.get(callback.message.chat.id)
    if not state:
        await callback.answer("Нет состояния для удаления.")
        return

    files = state["files"]
    index = state["index"]

    # Удаляем текущее изображение
    current_face_path = os.path.join(UNKNOWN_FACES_DIR, files[index])
    os.remove(current_face_path)

    # Убираем файл из состояния
    del files[index]

    # Обновляем индекс, чтобы не выйти за границы
    if files:
        state["index"] %= len(files)
        await send_unknown_face(callback.message.chat.id)
    else:
        # Если файлов больше нет
        del unknown_faces_state[callback.message.chat.id]
        await callback.message.answer("Все фотографии удалены.")

    await callback.answer("Фотография успешно удалена.")


@dp.callback_query(lambda c: c.data == "next_face")
async def next_face_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    state = unknown_faces_state.get(chat_id)

    if not state:
        await callback.message.answer("Нет изображений для переключения.")
        await callback.answer()
        return

    state["index"] = (state["index"] + 1) % len(state["files"])

    # Отправляем новое изображение
    await send_unknown_face(chat_id)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "previous_face")
async def previous_face_callback(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    state = unknown_faces_state.get(chat_id)

    if not state:
        await callback.message.answer("Нет изображений для переключения.")
        await callback.answer()
        return

    state["index"] = (state["index"] - 1) % len(state["files"])

    # Отправляем новое изображение
    await send_unknown_face(chat_id)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "add_person")
async def add_person_callback(callback: types.CallbackQuery):
    user_id = callback.message.chat.id
    state = unknown_faces_state.get(user_id)

    if not state:
        await callback.message.answer("Нет активного изображения для добавления.")
        await callback.answer()
        return

    await callback.message.answer("Введите имя человека на изображении:")
    await callback.answer()

    @dp.message(lambda message: message.chat.id == user_id)
    async def capture_name(message: Message):
        # Получаем текущий файл
        state = unknown_faces_state.get(user_id)
        if not state:
            await message.answer("Произошла ошибка. Попробуйте ещё раз.")
            return

        current_face_path = os.path.join(UNKNOWN_FACES_DIR, state["files"][state["index"]])

        image = face_recognition.load_image_file(current_face_path)
        face_encodings = face_recognition.face_encodings(image)

        if len(face_encodings) != 1:
            await message.answer("Не удалось определить лицо. Убедитесь, что изображение содержит только одно лицо.")
            return

        face_encoding = face_encodings[0]
        save_new_face(message.text, face_encoding)

        # Удаляем изображение из папки и обновляем состояние
        os.remove(current_face_path)
        del state["files"][state["index"]]

        if not state["files"]:
            del unknown_faces_state[user_id]
            await message.answer("Все неизвестные лица обработаны.")
        else:
            state["index"] %= len(state["files"])  # Обновляем индекс
            await send_unknown_face(user_id)

        await message.answer(f"Лицо '{message.text}' успешно добавлено в базу данных!")


@dp.callback_query(lambda c: c.data.startswith("set_tolerance_"))
async def set_tolerance_callback(callback: types.CallbackQuery):
    global current_tolerance
    current_tolerance = float(callback.data.split("_")[-1])
    await callback.message.answer(f"Tolerance изменён на {current_tolerance}")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "show_current_tolerance")
async def show_current_tolerance(callback: types.CallbackQuery):
    await callback.answer()  # Отвечаем на callback, чтобы Telegram не показывал ошибки
    await callback.message.answer(f"Current tolerance: {current_tolerance}")

@dp.callback_query(lambda c: c.data == "show_stats")
async def show_stats_callback(callback: types.CallbackQuery):
    database = load_database()
    num_faces = len(database["names"])
    await callback.message.answer(f"Количество зарегистрированных лиц: {num_faces}")
    await callback.answer()

@dp.message(lambda message: message.text == "/recognize")
async def recognize_command(message: Message):
    await message.answer("Начинаю распознавание лиц...")
    await recognize_and_register_faces(message.chat.id)

@dp.message(lambda message: message.video)
async def handle_video(message: Message):
    # Проверяем размер файла
    video = message.video
    if video.file_size > 50 * 1024 * 1024:  # 50 МБ в байтах
        await message.answer("Видео слишком большое. Пожалуйста, отправьте файл размером не более 50 МБ.")
        return

    await message.answer("Получил видео, начинаю обработку...")

    video_file = await bot.get_file(video.file_id)
    temp_dir = tempfile.gettempdir()
    local_video_path = os.path.join(temp_dir, os.path.basename(video_file.file_path))
    await bot.download_file(video_file.file_path, local_video_path)

    await process_uploaded_video(local_video_path, message.chat.id)

@dp.message(lambda message: message.photo)
async def handle_photo(message: Message):
    await message.answer("Получил фото, начинаю обработку...")
    photo = message.photo[-1]

    photo_file = await bot.get_file(photo.file_id)
    temp_dir = tempfile.gettempdir()
    local_photo_path = os.path.join(temp_dir, os.path.basename(photo_file.file_path))
    await bot.download(photo_file, destination=local_photo_path)

    await process_uploaded_photo(local_photo_path, message.chat.id)

async def on_shutdown(dp):
    await bot.close()

if __name__ == "__main__":
    dp.run_polling(bot, on_shutdown=on_shutdown)
    print("Bot is running...")
