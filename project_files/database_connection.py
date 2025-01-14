import psycopg2
from project_files import config
import numpy as np

# Функция для загрузки базы данных
def load_database():
    names = []
    encodings = []

    try:
        # Используем контекстный менеджер для соединения и курсора
        with psycopg2.connect(host=config.HOST, dbname=config.DB_NAME, user=config.USERNAME, password=config.PASSWORD) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT name, encoding FROM faces")
                records = cursor.fetchall()

                # Обрабатываем данные из базы данных
                for name, encoding_bytes in records:
                    names.append(name)
                    encodings.append(np.frombuffer(encoding_bytes))  # Преобразуем из байтов в массив numpy

    except psycopg2.Error as e:
        print(f"Ошибка при работе с базой данных: {e}")

    return {"encodings": encodings, "names": names}

# Функция для сохранения нового лица
def save_new_face(name, encoding):
    try:
        encoding_bytes = encoding.tobytes()

        with psycopg2.connect(host=config.HOST, dbname=config.DB_NAME, user=config.USERNAME, password=config.PASSWORD) as connection:
            with connection.cursor() as cursor:
                # Проверяем, существует ли уже имя в базе
                cursor.execute("SELECT 1 FROM faces WHERE name = %s", (name,))
                if cursor.fetchone():
                    # Если имя уже существует, не добавляем новое лицо
                    print(f"Лицо с именем {name} уже существует.")
                else:
                    # Если имя не существует, вставляем в базу
                    cursor.execute("INSERT INTO faces (name, encoding) VALUES (%s, %s)", (name, encoding_bytes))
                    connection.commit()
                    print(f"Лицо '{name}' успешно зарегистрировано!")
    except psycopg2.Error as e:
        print(f"Ошибка при сохранении нового лица: {e}")
