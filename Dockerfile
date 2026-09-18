# BOSS Auto Reply Bot — Docker 镜像
# 支持 x86_64 和 ARM64
# 构建: docker build -t boss-bot .
# 运行: docker compose up -d

FROM python:3.12-slim

WORKDIR /app

# 安装 Chromium + 中文字体
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    procps \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/chromium /usr/bin/google-chrome

ENV PYTHONUNBUFFERED=1 \
    CHROME_PATH=/usr/bin/chromium \
    TZ=Asia/Shanghai

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.org/simple/

COPY . .

RUN mkdir -p messages logs accounts cookie_backups

EXPOSE 5001

CMD ["python", "-m", "boss_bot"]
