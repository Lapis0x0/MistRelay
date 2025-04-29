# MistRelay

基于Telegram机器人的aria2下载控制系统，支持OneDrive自动上传

## 一、特点

1. 基于电报机器人控制aria2，可自行设置下载完成后的处理方式
2. 支持下载完成后通过rclone自动上传到OneDrive
3. 支持`批量`添加http、磁力、种子下载
4. 支持自定义目录下载，使用 /path 命令设置
5. 自己实现`aria2c` `jsonrpc`调用，增加断开重连功能
6. 命令 /web 获取在线ariaNg web控制地址，方便跳转
7. 下载实时进度、上传实时进度显示
8. Docker一键部署，集成aria2和rclone

## 二、如何安装

### 1. 配置文件设置

下载项目到本地：

```bash
git clone https://github.com/Lapis0x0/MistRelay.git
cd MistRelay
```

重命名 `db/config.example.yml` 为 `config.yml` 并设置参数：

```yaml
API_ID: xxxx                      # Telegram API ID
API_HASH: xxxxxxxx                # Telegram API Hash
BOT_TOKEN: xxxx:xxxxxxxxxxxx      # Telegram Bot Token
ADMIN_ID: 管理员ID                 # 管理员的Telegram ID
FORWARD_ID: 文件转发目标id          # 可选，文件转发目标ID

# 上传设置
UP_TELEGRAM: false                # 是否上传到电报
UP_ONEDRIVE: true                 # 是否启用rclone上传到OneDrive

# rclone配置
RCLONE_REMOTE: onedrive           # rclone配置的远程名称
RCLONE_PATH: /Downloads           # OneDrive上的目标路径

# aria2c设置（Docker集成后可使用默认值）
RPC_SECRET: xxxxxxx               # RPC密钥（建议修改为自定义密钥）
RPC_URL: localhost:6800/jsonrpc   # 使用Docker部署时必须使用localhost或127.0.0.1

# 代理设置（可选）
PROXY_IP:                         # 代理IP，不需要则留空
PROXY_PORT:                       # 代理端口，不需要则留空

# 自动删除本地文件设置
AUTO_DELETE_AFTER_UPLOAD: true    # 是否在成功上传到OneDrive后自动删除本地文件
```

### 2. 配置rclone

将rclone配置文件（rclone.conf）放入项目的rclone目录中：

```bash
# 如果还没有rclone目录，先创建一个
mkdir -p rclone

# 安装rclone（如果尚未安装）
curl https://rclone.org/install.sh | sudo bash

# 配置rclone
rclone config

# 将生成的配置文件复制到项目的rclone目录
cp ~/.config/rclone/rclone.conf ./rclone/
```

### 3. 关于aria2c配置

项目已经在Docker中集成了aria2c，您只需要在config.yml中设置：

- `RPC_SECRET`: 这是aria2c的RPC密钥，用于安全访问。建议修改为自定义的强密码。
- `RPC_URL`: 使用Docker部署时必须使用localhost或127.0.0.1，端口号保持默认值6800即可。

启动容器后，aria2c会自动配置并运行，您不需要单独安装或配置aria2c。

### 4. 关于自动删除本地文件

项目支持在文件成功上传到OneDrive后自动删除本地文件，以节省存储空间：

- `AUTO_DELETE_AFTER_UPLOAD`: 设置为true时，文件成功上传到OneDrive后会自动删除本地文件；设置为false时，保留本地文件。

**注意**：
- 只有在文件成功上传到OneDrive后才会删除本地文件
- 如果上传失败或中断，本地文件会保留
- 对于大文件，系统会等待上传完全成功后才删除本地文件，不用担心上传过程中文件被删除

### 5. 关于OneDrive上传速度优化

项目已经针对OneDrive上传速度进行了优化，使用了以下rclone参数：

- `--transfers 32`: 增加并行传输数量
- `--checkers 16`: 增加并行检查数量
- `--onedrive-chunk-size 64M`: 增加OneDrive上传分块大小
- `--buffer-size 64M`: 增加缓冲区大小
- `--drive-pacer-min-sleep 10ms`: 减少API请求间隔
- `--drive-pacer-burst 1000`: 增加爆发限制

这些优化参数可以显著提高上传速度，特别是对于大文件。如果您仍然遇到上传速度慢的问题，可能是由于以下原因：

1. 服务器到OneDrive的网络连接质量
2. Microsoft对API请求的限制
3. 服务器CPU或内存资源限制

### 6. 使用Docker部署

安装Docker和Docker Compose：

```bash
curl -fsSL get.docker.com -o get-docker.sh && sh get-docker.sh && systemctl enable docker && systemctl start docker
```

构建并启动容器：

```bash
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f --tail=4000
```

### 7.如何更新项目

当有新版本发布时，您可以按照以下步骤更新项目：

1. 备份您的配置文件和rclone配置：

```bash
# 备份配置文件
cp db/config.yml db/config.yml.backup
# 备份rclone配置
cp rclone/rclone.conf rclone/rclone.conf.backup
```

2. 拉取最新代码：

```bash
# 获取最新代码
git pull

# 如果有冲突，可以先重置本地修改
# git reset --hard
# git pull
```

3. 重新构建并启动容器：

```bash
# 停止并删除旧容器
docker compose down

# 重新构建并启动
docker compose up -d --build
```

4. 检查日志确认一切正常：

```bash
docker compose logs -f
```

如果更新后出现问题，您可以恢复备份的配置文件，然后重新构建容器。

### 8.使用方法

1. 在Telegram中找到您的机器人并发送 `/start` 命令
2. 使用 `/help` 查看帮助信息
3. 发送HTTP链接、磁力链接或种子文件开始下载
4. 使用菜单按钮管理下载任务
5. 使用 `/path` 命令设置下载目录
6. 使用 `/web` 命令获取ariaNg在线控制地址

### 9.命令列表

- `/start` - 开始使用
- `/help` - 查看帮助
- `/info` - 查看系统信息
- `/web` - 获取ariaNg在线地址
- `/path [目录]` - 设置下载目录

### 10.菜单功能

- ⬇️正在下载 - 查看正在下载的任务
- ⌛️ 正在等待 - 查看等待中的任务
- ✅ 已完成/停止 - 查看已完成或停止的任务
- ⏸️暂停任务 - 暂停选中的任务
- ▶️恢复任务 - 恢复选中的任务
- ❌ 删除任务 - 删除选中的任务
- ❌ ❌ 清空已完成/停止 - 清空所有已完成或停止的任务

## 三、应用截图

/help 查看帮助

![img.png](./img.png)

## 四、致谢

https://github.com/HouCoder/tele-aria2

https://github.com/jw-star/aria2bot

## 五、未来计划
[] 支持重命名文件
[] 更清晰、强大的菜单键
[] 支持通过大模型来自动管理文件列表
