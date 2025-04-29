#!/bin/bash

# 启动aria2c服务
echo "正在启动aria2c服务..."
CONFIG_DIR="/app/aria2"
mkdir -p $CONFIG_DIR

# 如果配置文件不存在，创建默认配置
if [ ! -f "$CONFIG_DIR/aria2.conf" ]; then
    echo "创建aria2默认配置文件..."
    cat > "$CONFIG_DIR/aria2.conf" << EOF
# 基本配置
dir=/root/downloads
disable-ipv6=true
enable-rpc=true
rpc-allow-origin-all=true
rpc-listen-all=true
rpc-listen-port=6800

# 连接设置
max-concurrent-downloads=5
continue=true
max-connection-per-server=10
min-split-size=10M
split=10
max-overall-download-limit=0
max-download-limit=0
max-overall-upload-limit=0
max-upload-limit=0
lowest-speed-limit=0
timeout=60
max-tries=5
retry-wait=0

# RPC相关设置
rpc-max-request-size=10M
EOF

    # 从环境变量或配置文件获取RPC密钥
    if [ -f "/app/db/config.yml" ]; then
        RPC_SECRET=$(grep "RPC_SECRET" /app/db/config.yml | cut -d ":" -f2 | tr -d ' ')
        echo "rpc-secret=$RPC_SECRET" >> "$CONFIG_DIR/aria2.conf"
    fi
fi

# 后台启动aria2c
aria2c --conf-path="$CONFIG_DIR/aria2.conf" -D

# 检查rclone配置
if [ ! -f "/root/.config/rclone/rclone.conf" ]; then
    echo "警告: 未找到rclone配置文件，请确保已上传rclone.conf到项目的rclone目录"
    # 创建配置目录（如果不存在）
    mkdir -p /root/.config/rclone
else
    echo "rclone配置文件已找到"
    # 检查是否有可用的远程配置
    if rclone listremotes &> /dev/null; then
        echo "rclone远程配置已找到:"
        rclone listremotes
    else
        echo "警告: rclone配置文件存在但未找到有效的远程配置，上传到OneDrive功能可能无法正常工作"
    fi
fi

# 启动主应用
echo "正在启动主应用..."
python3 -u app.py
