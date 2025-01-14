import asyncio
import face_recognition
from concurrent.futures import ThreadPoolExecutor
import cv2
from project_files.database_connection import load_database
import os
from aiogram import Bot, Dispatcher
from aiogram.types import Message, FSInputFile
from project_files import config
import numpy as np
import uuid
import tempfile
from PIL import Image
from project_files.database_connection import save_new_face
from project_files.interface import get_next_unknown_face_filename

UNKNOWN_FACES_DIR = config.UNKNOWN_FACES
TOKEN = config.BOT_TOKEN
bot = Bot(token=TOKEN)
dp = Dispatcher()
FIXED_SIZE = (300, 300)
os.makedirs(UNKNOWN_FACES_DIR, exist_ok=True)
detected_unknown_encodings = []
current_tolerance = 0.6

async def register_new_face_from_user(chat_id, face_encoding, image_path):
    name = await wait_for_user_input(chat_id)
    if name:
        save_new_face(name, face_encoding)
        await bot.send_message(chat_id, f"Лицо '{name}' успешно зарегистрировано!")

async def wait_for_user_input(chat_id):
    user_input = None

    @dp.message(lambda message: message.chat.id == chat_id)
    async def capture_input(message: Message):
        nonlocal user_input
        user_input = message.text

    while user_input is None:
        await asyncio.sleep(1)

    return user_input

async def recognize_faces_on_frame(frame, known_encodings, known_names):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        # Выполняем распознавание лиц в отдельном потоке
        face_locations, face_encodings = await loop.run_in_executor(
            executor, lambda: (face_recognition.face_locations(frame), face_recognition.face_encodings(frame))
        )

        results = []
        for face_encoding, face_location in zip(face_encodings, face_locations):
            # Сравниваем лица
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=current_tolerance)
            name = "Неизвестно"

            if True in matches:
                match_index = matches.index(True)
                name = known_names[match_index]

            # Добавляем результат в список
            results.append((name, face_location))

        # Возвращаем результаты распознавания
        return results


async def recognize_faces_async(frame, known_encodings, known_names):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as executor:
        face_locations, face_encodings = await loop.run_in_executor(
            executor, lambda: (face_recognition.face_locations(frame), face_recognition.face_encodings(frame))
        )
        results = []
        for face_encoding, face_location in zip(face_encodings, face_locations):
            matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=current_tolerance)
            name = "Неизвестно"
            if True in matches:
                match_index = matches.index(True)
                name = known_names[match_index]
            results.append((name, face_location, face_encoding))
        return results

async def recognize_and_register_faces(chat_id):
    database = load_database()
    known_encodings = database["encodings"]
    known_names = database["names"]

    video_capture = cv2.VideoCapture(config.RTSP_URL)
    if not video_capture.isOpened():
        await bot.send_message(chat_id, "Не удалось открыть камеру!")
        return

    await bot.send_message(chat_id, "Начинается распознавание. Нажмите 'q' для выхода из режима распознавания.")

    while True:
        ret, frame = video_capture.read()
        if not ret:
            await bot.send_message(chat_id, "Ошибка при захвате кадра.")
            break

        # Конвертация кадра в RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Асинхронное распознавание лиц
        results = await recognize_faces_async(frame_rgb, known_encodings, known_names)

        for name, (top, right, bottom, left), face_encoding in results:
            # Отображение рамки и имени
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 1)

            if name == "Неизвестно":
                # Проверка на уникальность лица
                is_unique = True
                for file in os.listdir(UNKNOWN_FACES_DIR):
                    existing_image_path = os.path.join(UNKNOWN_FACES_DIR, file)
                    existing_image = face_recognition.load_image_file(existing_image_path)
                    existing_encodings = face_recognition.face_encodings(existing_image)

                    if existing_encodings and np.linalg.norm(
                            face_encoding - existing_encodings[0]) <= current_tolerance:
                        is_unique = False
                        break

                if is_unique:
                    face_image_rgb = frame_rgb[top:bottom, left:right]
                    face_image_path = os.path.join(UNKNOWN_FACES_DIR, get_next_unknown_face_filename())

                    cv2.imwrite(face_image_path, cv2.cvtColor(face_image_rgb, cv2.COLOR_RGB2BGR))

                    await bot.send_photo(chat_id, FSInputFile(face_image_path),
                                         caption="Обнаружено новое неизвестное лицо.")

        cv2.imshow("Recognition - Press 'q' to quit", frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()

    await bot.send_message(chat_id, "Распознавание завершено.")

async def process_uploaded_video(video_path, chat_id):
    output_dir = os.path.join(config.FRAMES_FROM_VIDEOS, f"processed_frames_{chat_id}_{int(asyncio.get_event_loop().time())}")
    os.makedirs(output_dir, exist_ok=True)

    video_capture = cv2.VideoCapture(video_path)
    frame_rate = int(video_capture.get(cv2.CAP_PROP_FPS))
    frame_index = 0
    recognized_faces = set()

    while video_capture.isOpened():
        ret, frame = video_capture.read()
        if not ret:
            break

        # Обработка каждого 5-го кадра
        if frame_index % 5 == 0:
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

            face_locations = face_recognition.face_locations(rgb_frame)

            for (top, right, bottom, left) in face_locations:
                face_identifier = (top, right, bottom, left)

                if face_identifier not in recognized_faces:
                    recognized_faces.add(face_identifier)
                    color = (0, 255, 0)
                    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

            frame_filename = f"frame_{frame_index}.jpg"
            frame_path = os.path.join(output_dir, frame_filename)
            cv2.imwrite(frame_path, frame)

        frame_index += 1

    video_capture.release()

    await bot.send_message(chat_id, f"Обработка видео завершена. Кадры сохранены в директорию: {output_dir}")

async def process_uploaded_photo(photo_path, chat_id):
    database = load_database()
    known_encodings = np.array(database["encodings"])
    known_names = database["names"]
    unknown_face_counter = 0

    image = face_recognition.load_image_file(photo_path)
    face_locations = face_recognition.face_locations(image)
    face_encodings = face_recognition.face_encodings(image, face_locations)

    # Загружаем изображение в OpenCV формате (BGR)
    image_for_drawing = cv2.imread(photo_path)

    for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(known_encodings, face_encoding, tolerance=current_tolerance)
        face_distances = face_recognition.face_distance(known_encodings, face_encoding)
        best_match_index = np.argmin(face_distances) if matches else -1

        top, right, bottom, left = face_location
        color = (0, 255, 0) if True in matches else (0, 0, 255)

        if True in matches:
            name = known_names[best_match_index]
            cv2.putText(image_for_drawing, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        else:
            name = "Неизвестно"

        cv2.rectangle(image_for_drawing, (left, top), (right, bottom), color, 2)

        if name == "Неизвестно":
            is_new_face = True
            for file in os.listdir(UNKNOWN_FACES_DIR):
                existing_image_path = os.path.join(UNKNOWN_FACES_DIR, file)
                existing_image = face_recognition.load_image_file(existing_image_path)
                existing_encodings = face_recognition.face_encodings(existing_image)

                if existing_encodings and np.linalg.norm(face_encoding - existing_encodings[0]) <= current_tolerance:
                    is_new_face = False
                    break

            if is_new_face:
                # Извлекаем и сохраняем неизвестное лицо
                unknown_face = image[top:bottom, left:right]

                # OpenCV требует BGR для сохранения, поэтому конвертируем обратно
                unknown_face_path = os.path.join(
                    UNKNOWN_FACES_DIR, f"unknown_face_{uuid.uuid4()}.jpg"
                )
                cv2.imwrite(unknown_face_path, cv2.cvtColor(unknown_face, cv2.COLOR_RGB2BGR))

                # Отправляем изображение пользователю
                await bot.send_photo(chat_id, FSInputFile(unknown_face_path),
                                     caption="Обнаружено неизвестное лицо.")

            unknown_face_counter += 1

    image_rgb = cv2.cvtColor(image_for_drawing, cv2.COLOR_BGR2RGB)

    temp_output_path = os.path.join(tempfile.gettempdir(), "processed_photo.jpg")
    cv2.imwrite(temp_output_path, cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))

    await bot.send_photo(chat_id, FSInputFile(temp_output_path), caption="Результат обработки фотографии.")

async def resize_image_to_fixed_size(image_path, output_path, size=FIXED_SIZE):
    with Image.open(image_path) as img:
        img.thumbnail(size, Image.Resampling.LANCZOS)

        new_image = Image.new("RGB", size, (0, 0, 0))

        offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
        new_image.paste(img, offset)

        new_image.save(output_path, "JPEG")
