# Използваме лека версия на Python 3.11
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg flac && rm -rf /var/lib/apt/lists/*

# Настройваме работната директория вътре в контейнера
WORKDIR /app

# Копираме requirements и инсталираме зависимостите
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копираме целия код на приложението
COPY . .

# Отваряме порт 8000
EXPOSE 8000

# Команда за стартиране на сървъра
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]