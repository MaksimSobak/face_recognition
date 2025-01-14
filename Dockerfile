# Используем базовый образ с Python 3.10
FROM python:3.10-slim

# Установка необходимых системных инструментов
RUN apt-get update && apt-get install -y \
    cmake \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файлы проекта в контейнер
COPY . .

# Устанавливаем зависимости Python
RUN pip install --upgrade pip setuptools wheel
COPY requirements.txt .
RUN pip install --no-cache-dir --ignore-installed -r requirements.txt


# Команда для запуска приложения
CMD ["python", "bot.py"]
