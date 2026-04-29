FROM python:3.10-slim

# جلوگیری از سوالات interactive
ENV DEBIAN_FRONTEND=noninteractive

# نصب ابزارهای ضروری
RUN apt-get update && apt-get install -y \
    curl \
    ffmpeg \
    ca-certificates \
    gnupg \
    && apt-get clean

# نصب Node.js نسخه پایدار (18 LTS) - بسیار مهم برای yt-dlp
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean

# نصب جدیدترین yt-dlp
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
    -o /usr/local/bin/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

# ایجاد مسیر کاری
WORKDIR /app

# نصب پکیج‌های پایتون
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# کپی پروژه
COPY . .

# پاکسازی نهایی
RUN rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

CMD ["python", "main.py"]
