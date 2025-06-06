FROM python:3.13-slim


# 安装 ffmpeg 和依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    gcc \
    python3-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


COPY ./ /opt/app
WORKDIR /opt/app

# 安装依赖
RUN pip install --upgrade pip
RUN pip install -r requirements.txt



