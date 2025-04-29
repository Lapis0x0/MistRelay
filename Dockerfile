# Build stage
FROM python:3.11.3-slim-buster AS build

# Copy only the requirements file first to leverage Docker cache if it hasn't changed
COPY requirements.txt /app/requirements.txt

# Install dependencies in a temporary container
RUN python -m pip install --upgrade pip && \
    pip3 --no-cache-dir install --user -r /app/requirements.txt

FROM python:3.11.3-slim-buster

# 安装必要的工具和依赖
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg2 \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装aria2
RUN apt-get update && apt-get install -y aria2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装rclone
RUN curl -O https://downloads.rclone.org/rclone-current-linux-amd64.zip \
    && unzip rclone-current-linux-amd64.zip \
    && cd rclone-*-linux-amd64 \
    && cp rclone /usr/bin/ \
    && chmod 755 /usr/bin/rclone \
    && cd .. \
    && rm -rf rclone-*-linux-amd64 \
    && rm -f rclone-current-linux-amd64.zip

# Copy installed dependencies from the build stage
COPY --from=build /root/.local /root/.local

# Copy the rest of the application files
COPY . /app

WORKDIR /app

# 确保PATH包含.local/bin
ENV PATH=/root/.local/bin:$PATH

# 设置启动脚本权限
RUN chmod +x /app/start.sh

# 使用启动脚本
CMD ["/bin/bash", "-c", "set -e && /app/start.sh"]