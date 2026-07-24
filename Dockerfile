FROM python:3.12

RUN apt-get update && apt-get install -y \
    wget \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libcurl4 \
    libdbus-1-3 \
    libexpat1 \
    libgbm1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libvulkan1 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils

WORKDIR /code/review_parser

ENV PYTHONDONTWRITEBYTECODE 1

COPY requirements.txt /code/review_parser/

RUN pip install --no-cache-dir -r requirements.txt
RUN python -m playwright install chromium

COPY . /code/
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]