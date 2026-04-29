FROM python:3.10-slim

# پکیج‌های لازم سیستم
RUN apt-get update && apt-get install -y \
    nodejs \
    npm \
    ffmpeg \
    curl \
    && apt-get clean

# نصب yt-dlp آخرین نسخه
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
